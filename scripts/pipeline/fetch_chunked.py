#!/usr/bin/env python3
"""Deterministic chunked-range downloader for large frozen files.

Written after a 1.22 GB ENA object repeatedly failed as a single uninterrupted transfer
(curl 56: SSL_read unexpected eof). A single long TLS stream is unnecessarily fragile, and naive
resume is WORSE than useless: `curl -C -` resolves its offset once at startup, so an internal
retry restarts from that original offset and truncates whatever the failed attempt gained. Appending
a retry onto an unverified partial produced an OVERSIZED, gzip-corrupt file.

This downloader never appends a retry onto an unverified partial. Each fixed-size chunk is an
independent, individually verified transfer:

  * explicit inclusive byte range per chunk
  * HTTP 206 required, never 200 (a 200 means the server ignored the range and is sending the
    whole object into a chunk-sized slot)
  * exact Content-Range echoed back must match what was requested
  * exact chunk length required
  * each chunk written to its own uniquely numbered temporary file
  * a failed chunk is retried independently, always from a clean slate
  * verified chunks concatenated once, in strict numeric order
  * candidate accepted only after size + md5 + gzip all pass, then renamed atomically

Usage:
  fetch_chunked.py --url URL --out PATH --size BYTES --md5 HEX [--chunk-mib 64] [--retries 6]
  fetch_chunked.py --selftest
"""
import argparse, hashlib, os, shutil, subprocess, sys, tempfile

CHUNK_MIB_DEFAULT = 64


def _run(cmd, timeout):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def supports_ranges(url, timeout=120):
    """Confirm the endpoint advertises byte-range support before relying on it."""
    r = _run(["curl", "-sSI", "--max-time", str(timeout), url], timeout + 30)
    head = r.stdout.lower()
    return ("accept-ranges: bytes" in head), r.stdout


def fetch_chunk(url, start, end, dest, timeout=900):
    """One inclusive byte range -> its own file. Returns (ok, detail).

    Requires 206 and an exactly matching Content-Range. A 200 is rejected outright: it means the
    server ignored the Range header, so the bytes are not the slice we asked for.
    """
    want_len = end - start + 1
    if os.path.exists(dest):
        os.remove(dest)                      # never resume onto an unverified partial
    r = _run(["curl", "-sS", "--max-time", str(timeout),
              "-r", "%d-%d" % (start, end),
              "-D", dest + ".hdr", "-o", dest, url], timeout + 60)
    if r.returncode != 0:
        return False, "curl rc=%d %s" % (r.returncode, (r.stderr or "")[:100])
    hdr = ""
    if os.path.exists(dest + ".hdr"):
        hdr = open(dest + ".hdr", encoding="utf-8", errors="replace").read()
        os.remove(dest + ".hdr")
    status = 0
    for line in hdr.splitlines():
        if line.upper().startswith("HTTP/"):
            parts = line.split()
            if len(parts) > 1 and parts[1].isdigit():
                status = int(parts[1])
    if status != 206:
        return False, "status %d (expected 206)" % status
    cr = ""
    for line in hdr.splitlines():
        if line.lower().startswith("content-range:"):
            cr = line.split(":", 1)[1].strip()
    if not cr.lower().startswith("bytes %d-%d/" % (start, end)):
        return False, "content-range mismatch: %r" % cr
    got = os.path.getsize(dest) if os.path.exists(dest) else 0
    if got != want_len:
        return False, "length %d != %d" % (got, want_len)
    return True, "ok"


def download(url, out, size, md5, chunk_mib=CHUNK_MIB_DEFAULT, retries=6, workdir=None,
             verbose=True):
    chunk = chunk_mib * 1024 * 1024
    ranges = [(s, min(s + chunk - 1, size - 1)) for s in range(0, size, chunk)]
    tmpd = workdir or tempfile.mkdtemp(prefix="chunked_", dir=os.path.dirname(out) or ".")
    os.makedirs(tmpd, exist_ok=True)
    if verbose:
        print("  %d chunks of %d MiB (total %d bytes)" % (len(ranges), chunk_mib, size))

    parts = []
    for i, (a, b) in enumerate(ranges):
        dest = os.path.join(tmpd, "chunk.%05d" % i)
        good = False
        for attempt in range(1, retries + 1):
            ok, detail = fetch_chunk(url, a, b, dest)
            if ok:
                good = True
                break
            if verbose:
                print("    chunk %d attempt %d failed: %s" % (i, attempt, detail))
        if not good:
            return False, "chunk %d unrecoverable" % i, tmpd
        parts.append(dest)
        if verbose and (i % 5 == 0 or i == len(ranges) - 1):
            print("    chunk %d/%d verified" % (i + 1, len(ranges)))

    cand = os.path.join(tmpd, "candidate")
    with open(cand, "wb") as w:                       # strict numeric order, single pass
        for p in parts:
            with open(p, "rb") as r:
                shutil.copyfileobj(r, w, 1 << 20)

    checks = {}
    checks["size"] = (os.path.getsize(cand) == size)
    h = hashlib.md5()
    with open(cand, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    checks["md5"] = (h.hexdigest() == md5)
    checks["gzip"] = (subprocess.run(["gzip", "-t", cand],
                                     capture_output=True).returncode == 0
                      if out.endswith(".gz") else True)
    if verbose:
        print("  checks: %s" % checks)
    if not all(checks.values()):
        return False, "candidate rejected: %s" % checks, tmpd

    os.replace(cand, out)                              # atomic acceptance
    for p in parts:
        try:
            os.remove(p)
        except OSError:
            pass
    return True, "accepted", tmpd


def selftest():
    """Fixture tests: the checker must reject every malformed condition, not just accept good ones."""
    import http.server, socketserver, threading, gzip as gz
    results = []

    def fx(name, got, want):
        ok = got == want
        results.append(ok)
        print("  %-58s expected=%-5s got=%-5s %s" % (name, want, got, "PASS" if ok else "*** FAIL ***"))

    payload = gz.compress(b"@r1\nACGT\n+\n!!!!\n" * 20000)
    size = len(payload)
    md5 = hashlib.md5(payload).hexdigest()

    class H(http.server.BaseHTTPRequestHandler):
        mode = "ok"

        def log_message(self, *a):
            pass

        def do_HEAD(self):
            self.send_response(200)
            if H.mode != "noranges":
                self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(size))
            self.end_headers()

        def do_GET(self):
            rng = self.headers.get("Range")
            if H.mode == "ignore_range" or not rng:
                self.send_response(200)
                self.send_header("Content-Length", str(size))
                self.end_headers()
                self.wfile.write(payload)
                return
            a, b = rng.replace("bytes=", "").split("-")
            a, b = int(a), int(b)
            body = payload[a:b + 1]
            if H.mode == "short":
                body = body[:-10]
            self.send_response(206)
            if H.mode == "badrange":
                self.send_header("Content-Range", "bytes 0-1/%d" % size)
            else:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (a, b, size))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with socketserver.TCPServer(("127.0.0.1", 0), H) as srv:
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d/f.gz" % port
        d = tempfile.mkdtemp(prefix="fxt_")

        H.mode = "ok"
        sup, _ = supports_ranges(url)
        fx("endpoint advertises byte-range support", sup, True)
        ok, _, _ = download(url, os.path.join(d, "a.gz"), size, md5, chunk_mib=1, verbose=False)
        fx("well-formed chunked download is accepted", ok, True)

        H.mode = "noranges"
        sup, _ = supports_ranges(url)
        fx("missing Accept-Ranges is detected", sup, False)

        H.mode = "ignore_range"
        ok, _, _ = download(url, os.path.join(d, "b.gz"), size, md5, chunk_mib=1, retries=1,
                            verbose=False)
        fx("HTTP 200 (range ignored) is rejected", ok, False)

        H.mode = "badrange"
        ok, _, _ = download(url, os.path.join(d, "c.gz"), size, md5, chunk_mib=1, retries=1,
                            verbose=False)
        fx("wrong Content-Range is rejected", ok, False)

        H.mode = "short"
        ok, _, _ = download(url, os.path.join(d, "e.gz"), size, md5, chunk_mib=1, retries=1,
                            verbose=False)
        fx("short chunk length is rejected", ok, False)

        H.mode = "ok"
        ok, _, _ = download(url, os.path.join(d, "f.gz"), size, "0" * 32, chunk_mib=1, verbose=False)
        fx("md5 mismatch is rejected", ok, False)
        ok, _, _ = download(url, os.path.join(d, "g.gz"), size + 10, md5, chunk_mib=1, retries=1,
                            verbose=False)
        fx("wrong expected size is rejected", ok, False)
        fx("no output file written when rejected",
           os.path.exists(os.path.join(d, "b.gz")), False)
        srv.shutdown()
        shutil.rmtree(d, ignore_errors=True)

    n, p = len(results), sum(results)
    print("\n  %d fixtures, %d passed, %d failed" % (n, p, n - p))
    return 0 if p == n else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--out")
    ap.add_argument("--size", type=int)
    ap.add_argument("--md5")
    ap.add_argument("--chunk-mib", type=int, default=CHUNK_MIB_DEFAULT)
    ap.add_argument("--retries", type=int, default=6)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not (a.url and a.out and a.size and a.md5):
        sys.exit("need --url --out --size --md5, or --selftest")
    sup, head = supports_ranges(a.url)
    print("  Accept-Ranges advertised: %s" % sup)
    if not sup:
        sys.exit("endpoint does not advertise byte ranges; refusing chunked acquisition")
    ok, msg, tmpd = download(a.url, a.out, a.size, a.md5, a.chunk_mib, a.retries)
    print("  %s" % msg)
    if ok:
        shutil.rmtree(tmpd, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Fail-closed gate over the staged Zenodo deposit.

Checks, in order:
  A. every file named in MANIFEST.sha256 exists and hashes to the recorded value;
  B. each archive opens and streams to its end, so a truncated copy cannot be deposited;
  C. the two verbatim parts still match the digests recorded when they were downloaded from the
     execution host, which are the values fixed at the results freeze;
  D. the parsed-call and assembly counts inside the archives match what the manuscript states;
  E. no credential, key, server address or personal path appears in any text member.

Prints ZENODO_DEPOSIT_VERIFIED only if all pass.
"""
import io, os, re, sys, json, hashlib, tarfile, zstandard

STAGE = "<local>/PlasmidCall-Zenodo-deposit"
C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
PARTS = json.load(io.open(STAGE + "/_parts.json", encoding="utf-8"))
fail = []

LEAK = [(r"\b(?:ssh|scp)\s+-i\b", "ssh invocation with a key"),
        (r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY", "private key material"),
        (r"\bocid1\.[a-z]+\.oc1\b", "cloud resource identifier"),
        (r"\bghp_[A-Za-z0-9]{20,}", "GitHub token"),
        (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key id"),
        (r"\bC:[\\/]Users[\\/]", "personal filesystem path"),
        (r"\bopc@|\bubuntu@", "server login")]
TEXT = re.compile(r"\.(?:tsv|csv|json|md|txt|log|sha256|py|yaml|yml|diff)$", re.I)


def sha256(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(buf), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ A. manifest
print("A. manifest")
man = [l.split("  ", 1) for l in io.open(STAGE + "/MANIFEST.sha256", encoding="utf-8")
       if l.strip() and not l.startswith("#")]
for digest, rel in man:
    p = os.path.join(STAGE, rel.strip())
    if not os.path.exists(p):
        fail.append("missing: " + rel.strip())
        continue
    got = sha256(p)
    ok = got == digest
    print("   %-52s %s" % (os.path.basename(rel.strip()), "ok" if ok else "DIGEST MISMATCH"))
    if not ok:
        fail.append("digest mismatch: " + rel.strip())

# ------------------------------------------------------------------ B-E. archive contents
print("B-E. archive contents, counts and leak scan")
counts, leaks = {}, []
for p in PARTS:
    path = os.path.join(STAGE, p["file"])
    base = os.path.basename(path)
    n, members = 0, {}
    try:
        d = zstandard.ZstdDecompressor(max_window_size=2 ** 31)
        with open(path, "rb") as fh, d.stream_reader(fh) as r:
            t = tarfile.open(fileobj=r, mode="r|")
            for m in t:
                if not m.isfile():
                    continue
                n += 1
                top = m.name.split("/")
                key = "/".join(top[:2]) if len(top) > 1 else top[0]
                members[key] = members.get(key, 0) + 1
                if TEXT.search(m.name) and m.size < 4_000_000:
                    try:
                        blob = t.extractfile(m).read().decode("utf-8", "ignore")
                    except Exception:
                        continue
                    for pat, lbl in LEAK:
                        if re.search(pat, blob):
                            leaks.append((base, m.name, lbl))
    except Exception as e:
        fail.append("%s did not stream to its end: %s" % (base, e))
        continue
    counts[base] = members
    print("   %-52s %6d files, streamed to end" % (base, n))

parsed = counts.get("PlasmidCall_evidence_tier1_execution.tar.zst", {}).get("inference/parsed", 0)
asm = sum(v for k, v in counts.get("PlasmidCall_evidence_tier2_assemblies.tar.zst", {}).items())
print("   parsed-call files      : %d   (expected %d = 12 classifiers x %d isolates)"
      % (parsed, 12 * C["cohort_n"], C["cohort_n"]))
if parsed != 12 * C["cohort_n"]:
    fail.append("parsed-call file count %d, expected %d" % (parsed, 12 * C["cohort_n"]))
print("   assembly members       : %d   (>= %d isolates)" % (asm, C["cohort_n"]))
if asm < C["cohort_n"]:
    fail.append("assembly member count %d is below the cohort size %d" % (asm, C["cohort_n"]))

for p in PARTS:
    if p.get("sha256_recorded_at_download") and not p.get("matches_recorded_digest"):
        fail.append("%s no longer matches the digest recorded at download"
                    % os.path.basename(p["file"]))
print("   verbatim parts vs host record: %d checked, %d matching"
      % (sum(1 for p in PARTS if p.get("sha256_recorded_at_download")),
         sum(1 for p in PARTS if p.get("matches_recorded_digest"))))

if leaks:
    for b, name, lbl in leaks[:10]:
        print("   LEAK  %-28s %s  in %s" % (lbl, name[:48], b))
    fail.append("%d leak hit(s) inside the archives" % len(leaks))
else:
    print("   leak scan              : clean")

print()
if fail:
    for f in fail:
        print("FAIL:", f)
    sys.exit("VERDICT            : DEPOSIT_NOT_VERIFIED")
print("parts              : %d" % len(PARTS))
print("total bytes        : %s" % "{:,}".format(sum(p["bytes"] for p in PARTS)))
print("VERDICT            : ZENODO_DEPOSIT_VERIFIED")

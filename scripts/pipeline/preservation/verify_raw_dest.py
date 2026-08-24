#!/usr/bin/env python3
"""Task 1 post-transfer: verify EVERY destination file against the server-side SHA-256 manifest.

Requirement is zero absent files and zero checksum mismatches. Writes a preservation receipt
recording source and destination paths, file count, byte count and verification UTC.
"""
import concurrent.futures as cf
import datetime, hashlib, io, json, os, sys

SP = os.environ.get("P111_WORKDIR", ".")
MAN = os.path.join(SP, "RAW_AS_EXECUTED_MANIFEST.sha256")
DEST = r"E:\AMR_Evidence_Data\P1.11\raw_as_executed"
SRC = "/work"
OUT = os.path.join(DEST, "PRESERVATION_RECEIPT.json")

entries = []
for line in io.open(MAN, encoding="utf-8"):
    line = line.rstrip("\n")
    if not line:
        continue
    h, _, p = line.partition("  ")
    if h and p:
        entries.append((h, p))
print("manifest entries: %d" % len(entries))


def check(e):
    h, rel = e
    fp = os.path.join(DEST, rel.replace("/", os.sep))
    if not os.path.exists(fp):
        return ("ABSENT", rel, None)
    d = hashlib.sha256()
    try:
        with open(fp, "rb") as f:
            for b in iter(lambda: f.read(1 << 22), b""):
                d.update(b)
    except OSError as ex:
        return ("UNREADABLE", rel, str(ex))
    g = d.hexdigest()
    return ("OK", rel, g) if g == h else ("MISMATCH", rel, g)


absent, mismatch, unreadable = [], [], []
nbytes = 0
done = 0
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    for st, rel, g in ex.map(check, entries, chunksize=64):
        done += 1
        if st == "ABSENT":
            absent.append(rel)
        elif st == "MISMATCH":
            mismatch.append(rel)
        elif st == "UNREADABLE":
            unreadable.append(rel)
        else:
            try:
                nbytes += os.path.getsize(os.path.join(DEST, rel.replace("/", os.sep)))
            except OSError:
                pass
        if done % 5000 == 0:
            print("  verified %d/%d ..." % (done, len(entries)))

utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
print("\n=== VERIFICATION ===")
print("  files in manifest    : %d" % len(entries))
print("  verified OK          : %d" % (len(entries) - len(absent) - len(mismatch) - len(unreadable)))
print("  ABSENT               : %d" % len(absent))
print("  CHECKSUM MISMATCH    : %d" % len(mismatch))
print("  UNREADABLE           : %d" % len(unreadable))
print("  verified bytes       : %d (%.2f GiB)" % (nbytes, nbytes / 2**30))
for lbl, lst in (("ABSENT", absent), ("MISMATCH", mismatch), ("UNREADABLE", unreadable)):
    for x in lst[:10]:
        print("    %-11s %s" % (lbl, x))

rec = {
    "record": "P1.11 raw-as-executed preservation",
    "verification_utc": utc,
    "source_host": "OCI PortabilityRisk",
    "source_root": SRC,
    "destination_root": DEST,
    "manifest": "RAW_AS_EXECUTED_MANIFEST.sha256 (relative paths, generated on the source host)",
    "file_count": len(entries),
    "byte_count": nbytes,
    "gib": round(nbytes / 2**30, 2),
    "verified_ok": len(entries) - len(absent) - len(mismatch) - len(unreadable),
    "absent": len(absent), "checksum_mismatch": len(mismatch), "unreadable": len(unreadable),
    "absent_list": absent[:200], "mismatch_list": mismatch[:200],
    "result": "PASS" if not (absent or mismatch or unreadable) else "FAIL",
    "contents": [
        "79 sealed input assemblies (p112/assemblies)",
        "raw outputs from all 12 panel tools (p112/inference/native)",
        "AMRFinderPlus raw outputs (p112/annotation)",
        ".done and .failed state markers (p112/inference/state)",
        "all attempt logs (p112/inference/logs, p112/logs)",
        "original and stale receipts, and reconciled status (p112/inference/receipts, p112/receipts)",
        "parser inputs and outputs, call-table inputs (p112/inference/parsed, env/run)",
        "truth references, GBFF, assembly reports, md5checksums (p112/truth_hold)",
        "corrected truth execution (p112/truth, p112/truth_corrected)",
        "initial defective GenBank truth execution (p112/INITIAL_REFSEQ_ONLY_AUDIT)",
        "runner scripts and environment receipts (p112/env, p112/scripts)",
        "input FASTQ reads (p112/raw) -- included because 4 of 79 isolates are SRA_ONLY with no "
        "published FASTQ checksum, so their reads are not byte-reproducible from any recorded digest",
        "pre-truth cohort screen and ANI matrices (p111/screen), sealed cohort manifests (p111/manifests)",
    ],
    "deliberate_exclusions": {
        "p112/ARCHIVE_P1.11": "preserved separately as P1.11_ARCHIVE.tar.zst, verified",
        "p112/POSTTRUTH/images": "preserved separately as p112_all_images.tar.zst, verified",
        "p111/tools/sratoolkit*": "third-party public binary distribution (SRA Toolkit 3.1.1)",
        "docker build cache": "94.22 GB, regenerable, not an artefact",
        "/tmp scratch": "not referenced by any receipt or manifest",
    },
    "threshold_gate": "53.76 GiB transferred, below the standing 100 GB approval threshold",
}
io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(rec, indent=1) + "\n")
print("\n  receipt: %s" % OUT)
print("  RESULT: %s" % rec["result"])
sys.exit(0 if rec["result"] == "PASS" else 1)

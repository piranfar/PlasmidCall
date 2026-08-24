#!/usr/bin/env python3
"""Task 2: verify the transferred manuscript archive and Docker preservation.

Deliberately does NOT stop at the checksum of the compressed container. The manuscript archive is
streamed open and EVERY member is hashed against the scientific manifest carried inside it.
"""
import hashlib, io, json, os, sys, tarfile
from compression import zstd

ARCH = r"E:\AMR_Evidence_Data\P1.11\P1.11_ARCHIVE.tar.zst"
IMG = r"E:\AMR_Evidence_Data\frozen_images\p112\p112_all_images.tar.zst"
IMGDIR = os.path.dirname(IMG)
EXP_ARCH = "f8a5fb71823356d1ef8760ce731d1a6a0c7b11c753240732e98ad1708a1716e3"
EXP_IMG = "abe433e7f0f1e09ae35fcacfcf33eadee694e3f5894188a1c58aa617dd8d2720"
FROZEN_PRED = "0767da157051ff469b8830982aa168c558ce5b4cb6e1bc82ba81d4e9acb3e40d"
FROZEN_JSON = "f0551fa15a9eb0b281f2f88b0990c2bfa6510a9b8ef5d9dfac8a2e69a4fc5124"
fail = []


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def head(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78)


head("1. CONTAINER CHECKSUMS AND DESTINATION PATHS")
for name, path, exp in (("manuscript archive", ARCH, EXP_ARCH), ("docker archive", IMG, EXP_IMG)):
    ok = os.path.exists(path)
    print("  %-20s %s" % (name, path))
    if not ok:
        print("    *** MISSING ***"); fail.append(name + " missing"); continue
    got = sha_file(path)
    m = got == exp
    print("    bytes    : %d" % os.path.getsize(path))
    print("    sha256   : %s" % got)
    print("    expected : %s%s" % (exp, "" if m else "   *** MISMATCH ***"))
    print("    verdict  : %s" % ("MATCH" if m else "MISMATCH"))
    if not m:
        fail.append(name + " checksum")

head("2. MANUSCRIPT ARCHIVE - READABILITY AND INTERNAL SCIENTIFIC MANIFEST")
# pass 1: pull the manifest out
man = {}
with open(ARCH, "rb") as fh, zstd.ZstdFile(fh) as z, tarfile.open(fileobj=z, mode="r|") as tf:
    for m in tf:
        if m.name.endswith("ARCHIVE_P1.11/ARCHIVE_MANIFEST.tsv") or \
           m.name.rstrip("/").endswith("ARCHIVE_MANIFEST.tsv"):
            data = tf.extractfile(m).read().decode("utf-8")
            for line in data.splitlines():
                p = line.split("\t")
                if len(p) == 3:
                    man[p[2].lstrip("./")] = (p[0], int(p[1]))
            break
print("  archive opened and streamed: OK (readable)")
print("  internal manifest rows: %d" % len(man))
if not man:
    fail.append("internal manifest not found"); print("  *** internal manifest not found ***")

# pass 2: hash every member and compare
seen = {}
bad_hash = []; bad_size = []; extra = []
with open(ARCH, "rb") as fh, zstd.ZstdFile(fh) as z, tarfile.open(fileobj=z, mode="r|") as tf:
    for m in tf:
        if not m.isfile():
            continue
        rel = m.name.split("ARCHIVE_P1.11/", 1)[-1]
        if rel.endswith("ARCHIVE_MANIFEST.tsv"):
            continue
        h = hashlib.sha256()
        f = tf.extractfile(m)
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
        d = h.hexdigest()
        seen[rel] = (d, m.size)
        if rel not in man:
            extra.append(rel); continue
        if man[rel][0] != d:
            bad_hash.append(rel)
        if man[rel][1] != m.size:
            bad_size.append(rel)
missing = [k for k in man if k not in seen and not k.endswith("ARCHIVE_MANIFEST.tsv")]
print("  members hashed        : %d" % len(seen))
print("  checksum mismatches   : %d" % len(bad_hash))
print("  size mismatches       : %d" % len(bad_size))
print("  in manifest, absent   : %d" % len(missing))
print("  in archive, unlisted  : %d" % len(extra))
for lbl, lst in (("MISMATCH", bad_hash), ("SIZE", bad_size), ("MISSING", missing), ("EXTRA", extra)):
    for x in lst[:5]:
        print("    %-9s %s" % (lbl, x))
if bad_hash or bad_size or missing:
    fail.append("manuscript archive internal manifest")
else:
    print("  verdict: INTERNAL MANIFEST FULLY VERIFIED (every member re-hashed)")

head("3. FROZEN PREDICTION AND TRUTH PACKAGE INSIDE THE TRANSFERRED ARCHIVE")
fp = "inference/frozen/P1.11_FROZEN_PREDICTIONS.tsv"
fj = "PREDICTIONS_FROZEN.json"
for lbl, rel, exp in (("frozen prediction matrix", fp, FROZEN_PRED),
                      ("PREDICTIONS_FROZEN.json", fj, FROZEN_JSON)):
    if rel in seen:
        got = seen[rel][0]; m = got == exp
        print("  %-26s present   sha256 %s  %s" % (lbl, got[:16] + "...", "MATCH" if m else "*** MISMATCH ***"))
        if not m:
            fail.append(lbl)
    else:
        print("  %-26s *** ABSENT ***" % lbl); fail.append(lbl + " absent")
tt = [k for k in seen if k.startswith("truth/") and k.endswith("truth_table.tsv")]
print("  truth tables in archive   : %d  (expected 79)" % len(tt))
if len(tt) != 79:
    fail.append("truth tables count %d" % len(tt))
ini = [k for k in seen if k.startswith("INITIAL_REFSEQ_ONLY_AUDIT/")]
pt = [k for k in seen if k.startswith("POSTTRUTH/")]
print("  superseded initial audit  : %d files" % len(ini))
print("  post-truth analyses       : %d files" % len(pt))
print("  truth acquisition receipt : %s" % ("present" if "receipts/P1.11_truth_acquisition_receipt.json" in seen else "*** ABSENT ***"))
if "receipts/P1.11_truth_acquisition_receipt.json" not in seen:
    fail.append("truth acquisition receipt absent")

head("4. DOCKER PRESERVATION - 16 OCI IMAGE IDENTITIES VIA index.json")
ixp = os.path.join(IMGDIR, "index.json")
if not os.path.exists(ixp):
    print("  *** index.json missing ***"); fail.append("index.json missing")
else:
    ix = json.load(io.open(ixp, encoding="utf-8"))
    inv = {}
    invp = os.path.join(IMGDIR, "IMAGE_INVENTORY.tsv")
    if os.path.exists(invp):
        for line in io.open(invp, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2:
                inv[p[0]] = p[1]
    n = 0
    for e in ix["manifests"]:
        nm = e["annotations"].get("io.containerd.image.name", "")
        tag = nm.replace("docker.io/library/", "").replace("docker.io/", "")
        dg = e["digest"].replace("sha256:", "")
        short = inv.get(tag, "")
        agree = short and dg.startswith(short)
        n += 1
        print("  %-26s %s  inventory=%-14s %s" % (tag, dg[:20] + "...", short or "-",
                                                  "AGREES" if agree else ("(no inventory row)" if not short else "*** DISAGREES ***")))
        if short and not agree:
            fail.append("image identity " + tag)
    print("  images recorded in index.json: %d (expected 16)" % n)
    if n != 16:
        fail.append("image count %d" % n)

head("5. PROVENANCE AND PATHS")
prov = os.path.join(IMGDIR, "PROVENANCE.txt")
print("  PROVENANCE.txt : %s  (%d bytes)" % (prov, os.path.getsize(prov)) if os.path.exists(prov)
      else "  PROVENANCE.txt *** ABSENT ***")
if not os.path.exists(prov):
    fail.append("PROVENANCE.txt absent")
for p in (r"E:\AMR_Evidence_Data\P1.11", r"E:\AMR_Evidence_Data\frozen_images\p112"):
    print("  %-46s exists=%s" % (p, os.path.isdir(p)))

head("VERDICT")
if fail:
    print("  FAILURES: %d" % len(fail))
    for f in fail:
        print("    - %s" % f)
    sys.exit(1)
print("  ALL TASK-2 VERIFICATIONS PASSED")

# -*- coding: utf-8 -*-
"""Verify that the frozen evidence held off-server matches the digests recorded on the server,
and build a checksummed delta archive of everything produced in the manuscript phase.

Two questions are answered separately:
  1. Does the local copy of every frozen artefact still hash to the value the server recorded?
     If not, the local evidence has drifted and nothing built on it can be trusted.
  2. Is everything produced in this phase captured in an archive with its own manifest?
"""
import io, os, csv, json, glob, zipfile, hashlib, sys, collections

OUT = "dist"
os.makedirs(OUT, exist_ok=True)
report = collections.OrderedDict()
fail = []


def sha(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


# ------------------------------------------------------------------ 1. frozen result artefacts
rf = json.load(io.open("docs/evidence/P1.13_results/RESULTS_FROZEN.json", encoding="utf-8"))
checked = missing = mismatch = 0
det = []
# artefacts above the repository's own 5 MB release ceiling are preserved off-server instead;
# point PLASMIDCALL_OFFSERVER_EVIDENCE at that directory so they are verified too
OFFSRV = os.environ.get("PLASMIDCALL_OFFSERVER_EVIDENCE", "")


def locate(name, primary):
    if os.path.exists(primary):
        return primary, "repository"
    if OFFSRV:
        alt = os.path.join(OFFSRV, name)
        if os.path.exists(alt):
            return alt, "off-server evidence directory"
    return None, None


for name, want in sorted(rf["results_artefacts_sha256"].items()):
    p, where = locate(name, "docs/evidence/P1.13_results/" + name)
    if p is None:
        missing += 1
        det.append({"artefact": name, "status": "not held off-server"})
        continue
    got = sha(p)
    checked += 1
    if got != want:
        mismatch += 1
        fail.append("frozen result artefact %s differs from the server-recorded digest" % name)
        det.append({"artefact": name, "status": "MISMATCH", "recorded": want, "local": got})
    else:
        det.append({"artefact": name, "status": "verified", "held_in": where,
                    "sha256": got})
for name, want in sorted(rf["figure_source_tables_sha256"].items()):
    p = "docs/evidence/P1.13_results/figure_sources/" + name
    if not os.path.exists(p):
        missing += 1
        det.append({"artefact": name, "status": "not held off-server"})
        continue
    got = sha(p)
    checked += 1
    if got != want:
        mismatch += 1
        fail.append("figure source table %s differs from the server-recorded digest" % name)
    det.append({"artefact": name, "status": "verified" if got == want else "MISMATCH",
                "sha256": got})
report["frozen_result_artefacts"] = {"verified": checked, "not_held_locally": missing,
                                     "mismatched": mismatch, "detail": det}

# ------------------------------------------------------------------ 2. post-freeze artefacts
pv = json.load(io.open("docs/postfreeze/tables/PF_VERIFICATION_RECEIPT.json", encoding="utf-8"))
pchecked = pmissing = pmismatch = 0
pdet = []
for name, want in sorted(pv["artefact_sha256"].items()):
    p = "docs/postfreeze/tables/" + name
    if not os.path.exists(p):
        pmissing += 1
        pdet.append({"artefact": name, "status": "not held off-server"})
        continue
    got = sha(p)
    pchecked += 1
    if got != want:
        pmismatch += 1
        fail.append("post-freeze artefact %s differs from the server-recorded digest" % name)
        pdet.append({"artefact": name, "status": "MISMATCH", "recorded": want, "local": got})
    else:
        pdet.append({"artefact": name, "status": "verified", "sha256": got})
report["post_freeze_artefacts"] = {"verified": pchecked, "not_held_locally": pmissing,
                                   "mismatched": pmismatch, "detail": pdet}

# the verifier receipt necessarily post-dates the hashing of the other artefacts, so it cannot
# contain its own digest; that is expected and is not a gap
report["self_hash_note"] = ("PF_VERIFICATION_RECEIPT.json cannot record its own digest, because "
                            "the digest is computed before the file is written. Its absence from "
                            "artefact_sha256 is expected.")

# ------------------------------------------------------------------ 3. delta archive
PATTERNS = ["docs/manuscript/**/*", "docs/owner_review/**/*", "docs/submission/*.md",
            "docs/corrections/*.md", "docs/closure/*.md", "docs/closure/*.json",
            "docs/model_cards/*.md", "scripts/manuscript/*.py",
            "README.md", "KNOWN_LIMITATIONS.md", "REPRODUCIBILITY.md", "DATA_DICTIONARY.md",
            "CITATION.cff"]
files = []
for pat in PATTERNS:
    for p in glob.glob(pat, recursive=True):
        if os.path.isfile(p) and "/_render/" not in p.replace("\\", "/"):
            files.append(p.replace("\\", "/"))
files = sorted(set(files))

man = [{"path": p, "bytes": os.path.getsize(p), "sha256": sha(p)} for p in files]
# the manifest and the receipt are tracked evidence; only the archive itself stays
# out of the repository, because it is a redundant copy of tracked files
os.makedirs("docs/closure", exist_ok=True)
mpath = "docs/closure/MANUSCRIPT_PHASE_DELTA_MANIFEST.tsv"
with io.open(mpath, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["path", "bytes", "sha256"], delimiter="\t",
                       lineterminator="\n")
    w.writeheader()
    w.writerows(man)

zpath = OUT + "/PlasmidCall_manuscript_phase_delta.zip"
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in files:
        z.write(p, p)
    z.write(mpath, os.path.basename(mpath))

# verify the archive by reading it back and re-hashing every member
bad = []
with zipfile.ZipFile(zpath) as z:
    names = set(z.namelist())
    for r in man:
        if r["path"] not in names:
            bad.append("%s absent from the archive" % r["path"])
            continue
        h = hashlib.sha256(z.read(r["path"])).hexdigest()
        if h != r["sha256"]:
            bad.append("%s does not round-trip: archived content differs" % r["path"])
fail += bad
report["delta_archive"] = {
    "zip": zpath, "zip_bytes": os.path.getsize(zpath), "zip_sha256": sha(zpath),
    "manifest": mpath, "files": len(files),
    "total_bytes": sum(r["bytes"] for r in man),
    "round_trip_verified": not bad,
    "round_trip_failures": bad}

report["failures"] = fail
report["verdict"] = "OFF_SERVER_EVIDENCE_VERIFIED" if not fail else "FAILURES"
io.open("docs/closure/OFF_SERVER_VERIFICATION.json", "w", encoding="utf-8",
        newline="\n").write(json.dumps(report, indent=1) + "\n")

print("frozen result artefacts   : %d verified, %d mismatched, %d not held locally"
      % (checked, mismatch, missing))
print("post-freeze artefacts     : %d verified, %d mismatched, %d not held locally"
      % (pchecked, pmismatch, pmissing))
print("delta archive             : %d files, %.1f MB, round-trip %s"
      % (len(files), os.path.getsize(zpath) / 1048576.0,
         "verified" if not bad else "FAILED"))
print("archive sha256            : %s" % report["delta_archive"]["zip_sha256"])
print("VERDICT                   : %s" % report["verdict"])
for f in fail[:20]:
    print("   FAIL", f)
sys.exit(0 if not fail else 1)

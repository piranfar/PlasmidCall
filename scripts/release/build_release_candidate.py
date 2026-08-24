# -*- coding: utf-8 -*-
"""Build the v1.0.0 release candidate: manifest, checksums, zip. Uploads nothing."""
import io, os, csv, json, hashlib, zipfile, subprocess

R = "<local>/amr-evidence-warehouse"
os.chdir(R)

def sha(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()

tracked = [p for p in subprocess.run(["git", "ls-files"], capture_output=True,
                                     text=True).stdout.splitlines() if p]
# The release candidate carries the repository (code, models, docs, evidence records).
# Bulk artefacts stay out and are listed in the release matrix with their destinations.
# RELEASE_MANIFEST.tsv and CHECKSUMS.sha256 describe the OTHER files. A manifest cannot record
# its own hash: the hash is computed before the file is written, so any self-entry is guaranteed
# stale. They are carried in the archive but excluded from the hashed inventory, and the
# verification step skips them for the same reason.
SELF = {"RELEASE_MANIFEST.tsv", "CHECKSUMS.sha256"}
inc = [p for p in tracked if os.path.exists(p) and p not in SELF]

rows = []
for p in inc:
    top = p.split("/")[0]
    cls = {"scripts": "code", "models": "frozen model", "docs": "documentation/evidence"}.get(top, "repository metadata")
    rows.append({"path": p, "class": cls, "size_bytes": os.path.getsize(p), "sha256": sha(p)})

with io.open("RELEASE_MANIFEST.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["path", "class", "size_bytes", "sha256"], delimiter="\t")
    w.writeheader()
    w.writerows(rows)

with io.open("CHECKSUMS.sha256", "w", encoding="utf-8", newline="\n") as f:
    for r in rows:
        f.write("%s  %s\n" % (r["sha256"], r["path"]))

total = sum(r["size_bytes"] for r in rows)
print("manifest rows: %d | total %.1f MB" % (len(rows), total / 1048576.0))

os.makedirs("dist", exist_ok=True)
zp = "dist/PLASMIDCALL_RELEASE_CANDIDATE_v1.0.0.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for r in rows:
        z.write(r["path"], "PlasmidCall-1.0.0/" + r["path"])
    z.write("RELEASE_MANIFEST.tsv", "PlasmidCall-1.0.0/RELEASE_MANIFEST.tsv")
    z.write("CHECKSUMS.sha256", "PlasmidCall-1.0.0/CHECKSUMS.sha256")

zs = sha(zp)
io.open(zp + ".sha256", "w", encoding="utf-8", newline="\n").write(
    "%s  %s\n" % (zs, os.path.basename(zp)))
print("release candidate: %s" % zp)
print("  size   : %d bytes (%.1f MB)" % (os.path.getsize(zp), os.path.getsize(zp) / 1048576.0))
print("  sha256 : %s" % zs)

# verify the zip round-trips
bad = 0
with zipfile.ZipFile(zp) as z:
    names = set(z.namelist())
    for r in rows:
        n = "PlasmidCall-1.0.0/" + r["path"]
        if r["path"] in SELF:
            continue
        if n not in names:
            bad += 1
            continue
        d = hashlib.sha256()
        with z.open(n) as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                d.update(c)
        if d.hexdigest() != r["sha256"]:
            bad += 1
            print("  MISMATCH", n)
print("  verification: %d files, %d mismatches" % (len(rows), bad))

zj = {
 "title": "PlasmidCall: failure-aware selective prediction of plasmid-origin contigs in short-read bacterial assemblies",
 "upload_type": "software",
 "version": "1.0.0",
 "creators": [{"name": "Piranfar, Vahhab"}],
 "description": ("PlasmidCall classifies whether a contig from a short-read draft assembly is of "
                 "plasmid origin, combining twelve existing plasmid/chromosome classifiers - "
                 "including cases where they disagree or fail - and abstaining where the evidence "
                 "does not support a confident call. This record contains the frozen models, the "
                 "sealed P1.13 external-validation prediction artefacts, the complete provenance "
                 "record and the pipeline code. The unit of prediction is a contig, not a "
                 "reconstructed plasmid."),
 "keywords": ["antimicrobial resistance", "plasmid", "contig classification",
              "selective prediction", "abstention", "bacterial genomics", "reproducibility"],
 "access_right": "open",
 "license": "TBD-OWNER-SELECTION",
}
io.open(".zenodo.json", "w", encoding="utf-8", newline="\n").write(json.dumps(zj, indent=1) + "\n")
print("wrote .zenodo.json (license placeholder pending owner selection)")

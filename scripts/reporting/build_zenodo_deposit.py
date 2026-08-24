# -*- coding: utf-8 -*-
"""Assemble the Zenodo deposition for the study's derived data.

Purpose. The manuscript's Data availability statement promises a Zenodo archive holding the large
derived artefacts. Until that archive exists with a DOI, the statement resolves to a placeholder,
which is both a submission risk and an unfulfillable promise to a reader.

Design decisions, stated because they constrain what a reader gets:

  * Raw sequencing reads are NOT deposited. They are public archive data, cited by accession with
    per-file checksums, and the manuscript says they are not redistributed. Nothing here changes
    that.
  * The two existing tier archives are deposited byte-for-byte as they were built, not repackaged.
    Repackaging would break the digests already recorded in the frozen results record, and a
    reader could no longer check a download against the value fixed at the results freeze.
  * The complete execution record, whose bulk is 31 GB of native tool output, is prepared as a
    separate optional part. It is not needed to reproduce any number in the manuscript; the parsed
    calls in Tier 1 are. Splitting it lets the owner obtain a DOI immediately and add the bulk
    later as a new version under the same concept DOI.
  * Nothing is uploaded, published or minted by this script. It stages files and writes the
    metadata and instructions for the owner to act on.

Outputs a staging directory OUTSIDE the git repository, because the repository must not take bulk
data, and a manifest with a SHA-256 for every file.
"""
import io, os, re, sys, json, glob, time, shutil, hashlib, tarfile, subprocess

SRC = "<local>/Portability-server-files"
OUT = "<local>/PlasmidCall-Zenodo-deposit"
REPO = os.path.abspath(".")
CANON = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                          encoding="utf-8"))["values"]

# a deposit is published data; it gets the same leak gate the submission packages get
LEAK = [
 (r"\b(?:ssh|scp)\s+-i\b", "ssh invocation with a key"),
 (r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY", "private key material"),
 (r"\bocid1\.[a-z]+\.oc1\b", "cloud resource identifier"),
 (r"\bghp_[A-Za-z0-9]{20,}", "GitHub token"),
 (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key id"),
 (r"\bC:[\\/]Users[\\/]", "personal filesystem path"),
 (r"\bE:[\\/]Github", "personal filesystem path"),
 (r"\bopc@|\bubuntu@", "server login"),
 (r"/work\b", "server mount path"),
]


def sha256(path, buf=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(buf)
            if not b:
                return h.hexdigest()
            h.update(b)


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return "%.1f %s" % (n, u)
        n /= 1024.0


def scan(path):
    """Return leak hits in a text file; binary and huge files are skipped by the caller."""
    try:
        t = io.open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return []
    return [(lbl, m.group(0)[:60]) for pat, lbl in LEAK for m in re.finditer(pat, t)]


if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT + "/parts")

# ---------------------------------------------------------------- 1. tier archives, verbatim
print("staging the tier archives as built")
PARTS = []
for src, dst, role in (
    ("P113_TIER1_EVIDENCE.tar.zst", "PlasmidCall_evidence_tier1_execution.tar.zst",
     "parsed tool calls, execution receipts, resistance-gene annotation, provenance and the "
     "frozen prediction table"),
    ("P113_TIER2_ASSEMBLIES.tar.zst", "PlasmidCall_evidence_tier2_assemblies.tar.zst",
     "the 150 genome assemblies produced in this study, with their assembly graphs and logs"),
):
    s = os.path.join(SRC, src)
    assert os.path.exists(s), "missing source archive: " + s
    d = OUT + "/parts/" + dst
    shutil.copy2(s, d)
    PARTS.append({"file": "parts/" + dst, "bytes": os.path.getsize(d),
                  "sha256": sha256(d), "contents": role, "repackaged": False})
    print("   %-52s %s" % (dst, human(os.path.getsize(d))))

# ---------------------------------------------------------------- 2. evaluation tables
print("packing the evaluation tables")
EVAL = sorted(glob.glob(SRC + "/evaluation/*.tsv"))
assert EVAL, "no evaluation tables found"
d = OUT + "/parts/PlasmidCall_evidence_tier3_evaluation.tar.zst"
tmp = OUT + "/_tier3.tar"
with tarfile.open(tmp, "w") as t:
    for f in EVAL:
        t.add(f, arcname="evaluation/" + os.path.basename(f))
    fp = SRC + "/_extracted/P1.13_FROZEN_PREDICTIONS.tsv"
    if os.path.exists(fp):
        t.add(fp, arcname="evaluation/FROZEN_PREDICTIONS.tsv")
subprocess.run([sys.executable, "-c",
                "import zstandard,sys,shutil\n"
                "c=zstandard.ZstdCompressor(level=19)\n"
                "src,dst=sys.argv[1],sys.argv[2]\n"
                "fi=open(src,'rb');fo=open(dst,'wb')\n"
                "c.copy_stream(fi,fo);fi.close();fo.close()", tmp, d], check=True)
os.remove(tmp)
PARTS.append({"file": "parts/" + os.path.basename(d), "bytes": os.path.getsize(d),
              "sha256": sha256(d),
              "contents": "the joined truth-prediction table, the per-contig error catalogue, the "
                          "unresolved-truth characterisation, the sensitivity analysis, the "
                          "tool-output accounting and the frozen prediction table",
              "repackaged": True})
print("   %-52s %s" % (os.path.basename(d), human(os.path.getsize(d))))

# ---------------------------------------------------------------- 3. published results
print("packing every table, figure source and number behind the manuscript")
d = OUT + "/parts/PlasmidCall_published_results.tar.zst"
tmp = OUT + "/_results.tar"
INCLUDE = [("docs/manuscript/tables", "tables"),
           ("docs/manuscript/figures/source_data", "figure_source_data"),
           ("docs/manuscript/supplementary_data", "supplementary_data")]
SINGLE = ["docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
          "docs/manuscript/PLASMIDCALL_CANONICAL_TABLES.json",
          "docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json",
          "docs/manuscript/PLASMIDCALL_CLAIM_AUDIT.tsv",
          "docs/manuscript/PLASMIDCALL_CLAIM_TO_EVIDENCE_MATRIX.tsv",
          "docs/closure/P113_CANONICAL_ARTEFACT_INVENTORY.tsv",
          "docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md",
          "docs/closure/PLASMIDCALL_INTENDED_USE.md"]
leaks, n_files = [], 0
with tarfile.open(tmp, "w") as t:
    for srcdir, arc in INCLUDE:
        if not os.path.isdir(srcdir):
            continue
        for f in sorted(glob.glob(srcdir + "/*")):
            if os.path.isfile(f):
                leaks += [(f, a, b) for a, b in scan(f)]
                t.add(f, arcname="%s/%s" % (arc, os.path.basename(f)))
                n_files += 1
    for f in SINGLE:
        if os.path.exists(f):
            leaks += [(f, a, b) for a, b in scan(f)]
            t.add(f, arcname="records/" + os.path.basename(f))
            n_files += 1
subprocess.run([sys.executable, "-c",
                "import zstandard,sys\n"
                "c=zstandard.ZstdCompressor(level=19)\n"
                "src,dst=sys.argv[1],sys.argv[2]\n"
                "fi=open(src,'rb');fo=open(dst,'wb')\n"
                "c.copy_stream(fi,fo);fi.close();fo.close()", tmp, d], check=True)
os.remove(tmp)
PARTS.append({"file": "parts/" + os.path.basename(d), "bytes": os.path.getsize(d),
              "sha256": sha256(d),
              "contents": "every main and supplementary table, the machine-readable source data "
                          "behind every figure, the canonical number set recording the frozen "
                          "file and field each manuscript value was read from, the claim audit "
                          "and the intended-use and non-claims records",
              "repackaged": True})
print("   %-52s %s  (%d files)" % (os.path.basename(d), human(os.path.getsize(d)), n_files))

if leaks:
    for f, lbl, hit in leaks[:12]:
        print("   LEAK %-28s %s  %s" % (lbl, f, hit))
    sys.exit("refusing to stage a deposit containing %d leak hits" % len(leaks))
print("   leak scan: clean over %d text files" % n_files)

json.dump(PARTS, io.open(OUT + "/_parts.json", "w", encoding="utf-8"), indent=1)
print("\nstaged %d parts, %s total" % (len(PARTS), human(sum(p["bytes"] for p in PARTS))))

# -*- coding: utf-8 -*-
"""Make the availability statements exact about which artefacts live where, and record the two
large frozen tables in the public release matrix."""
import io, csv, json

# ------------------------------------------------------------------ 1. availability statement
P = "docs/manuscript/PLASMIDCALL_MANUSCRIPT_FINAL.md"
s = io.open(P, encoding="utf-8").read()
old = """All derived data supporting the findings of this study are available in the project repository at
*[public URL to be supplied on release]*, archived at Zenodo under DOI *[to be supplied]*. These
comprise: the sealed cohort manifest with all accessions and per-file checksums; the frozen
prediction table and its freeze receipt; the parsed tool-call table; the joined truth–prediction
table; every metric, stratified, comparator and post-freeze table reported here; per-contig error
catalogues; execution receipts; the frozen design and all amendments; and the verification receipts.
Each file is listed with its SHA-256 digest in the release manifest."""
new = """All derived data supporting the findings of this study are available in the project repository at
*[public URL to be supplied on release]* and in its Zenodo archive under DOI *[to be supplied]*.
The division between the two is by file size only, and every file in either location is listed
with its SHA-256 digest in the release manifest.

**In the repository:** the sealed cohort manifest with all accessions and per-file checksums; every
metric, stratified, comparator, matched-denominator, resistance-gene and post-freeze table reported
here; the predictor inventory; the primary-endpoint record; the frozen design and all amendments;
the prediction-freeze and truth-join receipts; both verification receipts; the machine-readable
source data behind every figure and table; and the canonical number set, which records for every
value in this manuscript the frozen file and field it was read from.

**In the Zenodo archive, because of size:** the frozen prediction table (19,320 rows), the parsed
tool-call table (231,841 rows), the joined truth–prediction table (19,320 rows), the per-contig
error catalogue (3,336 rows), the 150 assemblies, the 1,950 per-unit execution receipts and the
native tool outputs. The digests of all of these are recorded in the frozen results record held in
the repository, so any copy can be checked against the value fixed at the results freeze."""
assert s.count(old) == 1
s = s.replace(old, new)
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("availability statement made exact")

# ------------------------------------------------------------------ 2. release matrix
Q = "docs/release/PUBLIC_RELEASE_MATRIX.tsv"
rows = list(csv.DictReader(io.open(Q, encoding="utf-8"), delimiter="\t"))
cols = list(rows[0].keys())
have = {r["artefact"] for r in rows}
template = dict((c, "") for c in cols)
NEW = [
 {"artefact": "Joined truth-prediction table (19,320 rows)",
  "scientific_role": "the scored table every reported metric is computed from",
  "proposed_destination": "Zenodo archive (too large for the git repository)",
  "release_status": "release", "license": "CC BY 4.0",
  "redistribution_basis": "derived from public sequence data; contains no third-party database "
                          "content",
  "sensitivity": "none", "size": "19,320 rows",
  "checksum_source": "RESULTS_FROZEN.json results_artefacts_sha256",
  "required_citation": "this study", "release_blocker": "none"},
 {"artefact": "Per-contig error catalogue (3,336 rows)",
  "scientific_role": "every false positive and false negative with its covariates",
  "proposed_destination": "Zenodo archive (too large for the git repository)",
  "release_status": "release", "license": "CC BY 4.0",
  "redistribution_basis": "derived from public sequence data",
  "sensitivity": "none", "size": "3,336 rows",
  "checksum_source": "RESULTS_FROZEN.json results_artefacts_sha256",
  "required_citation": "this study", "release_blocker": "none"},
 {"artefact": "Result metric tables (primary, comparator, stratified, matched, ARG, inventory)",
  "scientific_role": "the reported results",
  "proposed_destination": "git repository", "release_status": "release", "license": "CC BY 4.0",
  "redistribution_basis": "derived from public sequence data", "sensitivity": "none",
  "size": "< 100 KB total",
  "checksum_source": "RESULTS_FROZEN.json results_artefacts_sha256 + RELEASE_MANIFEST.tsv",
  "required_citation": "this study", "release_blocker": "none"},
 {"artefact": "Post-freeze analysis tables (24 files)",
  "scientific_role": "secondary, sensitivity, exploratory and integrity analyses",
  "proposed_destination": "git repository", "release_status": "release", "license": "CC BY 4.0",
  "redistribution_basis": "derived from public sequence data", "sensitivity": "none",
  "size": "< 1 MB total",
  "checksum_source": "PF_VERIFICATION_RECEIPT.json artefact_sha256",
  "required_citation": "this study", "release_blocker": "none"},
 {"artefact": "Manuscript package (manuscript, preprint, SI, figures, source data)",
  "scientific_role": "the reported work and everything needed to check it",
  "proposed_destination": "git repository", "release_status": "release",
  "license": "CC BY 4.0 for documentation and figures; MIT for code",
  "redistribution_basis": "own work", "sensitivity": "none", "size": "~20 MB",
  "checksum_source": "dist/MANUSCRIPT_PHASE_DELTA_MANIFEST.tsv",
  "required_citation": "this study", "release_blocker": "owner approval to make public"},
]
added = 0
for r in NEW:
    if r["artefact"] in have:
        continue
    row = dict(template)
    row.update({k: v for k, v in r.items() if k in cols})
    rows.append(row)
    added += 1
with io.open(Q, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
    w.writeheader()
    w.writerows(rows)
print("release matrix: %d artefacts added (now %d rows)" % (added, len(rows)))

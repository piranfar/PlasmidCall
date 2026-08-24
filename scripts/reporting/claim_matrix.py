# -*- coding: utf-8 -*-
"""Regenerate the claim-to-evidence matrix from the verified claim audit.

The previous version carried a cohort-selection cascade that is not reproducible from the frozen
artefacts held in this repository. It is replaced by the funnel that is reproducible, and the
matrix is now derived from the same claim list the manuscript verifier checks.
"""
import io, csv, json, os, hashlib

OUT = "docs/manuscript/PLASMIDCALL_CLAIM_TO_EVIDENCE_MATRIX.tsv"
AUD = "docs/manuscript/PLASMIDCALL_CLAIM_AUDIT.tsv"
CAN = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                        encoding="utf-8"))
prov = CAN["provenance"]
hashes = CAN["values"]["source_file_sha256"]

# map a source artefact name to the file it lives in, so a reader can find and hash it
def locate(name):
    for p in hashes:
        if os.path.basename(p) == name or name in p:
            return p, hashes[p][:16]
    for p in ("docs/evidence/P1.13_results/" + name, "docs/postfreeze/tables/" + name,
              "docs/evidence/P1.13_provenance/" + name, "docs/manuscript/" + name):
        if os.path.exists(p):
            h = hashlib.sha256(io.open(p, "rb").read()).hexdigest()
            return p, h[:16]
    return "", ""


rows = []
for r in csv.DictReader(io.open(AUD, encoding="utf-8"), delimiter="\t"):
    srcs = [s.strip() for s in r["source"].replace(";", "+").split("+") if s.strip()]
    paths, hs = [], []
    for s in srcs:
        base = s.split()[0]
        p, h = locate(base)
        if p:
            paths.append(p)
            hs.append(h)
    rows.append({
        "claim_id": r["id"],
        "claim": r["claim"],
        "manuscript_location": r["loc"],
        "category": r["category"],
        "evidential_status": r["status"],
        "denominator": r["denominator"],
        "estimate": r["estimate"],
        "interval_95": r["ci"],
        "source_artefact": r["source"],
        "artefact_paths": " ; ".join(paths),
        "artefact_sha256_prefix": " ; ".join(hs),
        "reproduce_with": "python scripts/manuscript/build_canonical_numbers.py; "
                          "python scripts/manuscript/claim_audit.py",
        "verbatim_anchor_present_in_manuscript": r["anchor_found_in_manuscript"],
        "wording_fully_supported": r["supported"],
        "permission_status": "released",
    })

COLS = ["claim_id", "claim", "manuscript_location", "category", "evidential_status",
        "denominator", "estimate", "interval_95", "source_artefact", "artefact_paths",
        "artefact_sha256_prefix", "reproduce_with",
        "verbatim_anchor_present_in_manuscript", "wording_fully_supported", "permission_status"]
with io.open(OUT, "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=COLS, delimiter="\t", lineterminator="\n", restval="")
    w.writeheader()
    w.writerows(rows)
print("claim-to-evidence matrix: %d claims, %d with a resolved artefact path"
      % (len(rows), sum(1 for r in rows if r["artefact_paths"])))

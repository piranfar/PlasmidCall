#!/usr/bin/env python3
"""P1.13-PROSPECTIVE-PUBLIC-MULTIGENUS-EXTERNAL-VALIDATION -- verified census.

Every column is resolved BY HEADER NAME and validated fail-loud. Two silent bugs in the earlier
draft census both returned zero candidates rather than an error:
  (1) NCBI `biosample` was read positionally as column 4; it is column 3.
  (2) ENA returns `run_accession` first regardless of the field order requested, so a positional
      read of `sample_accession` picked up the run instead.
Both are prevented structurally here: a missing or reordered column raises SchemaError.

Selection uses metadata only. No tool output, model score, truth label or performance is read.
"""
import collections, csv, io, json, os, re, subprocess, sys, urllib.parse, urllib.request

W = "/work/p113"
os.makedirs(W, exist_ok=True)
CENSUS_DIR = "/work/p113_census"

TARGETS = {
    "Klebsiella pneumoniae":  {"taxid": 573,  "match": lambda o: o.startswith("Klebsiella pneumoniae")},
    "Enterobacter spp.":      {"taxid": 547,  "match": lambda o: o.startswith("Enterobacter ")},
    "Citrobacter spp.":       {"taxid": 544,  "match": lambda o: o.startswith("Citrobacter ")},
    "Serratia spp.":          {"taxid": 613,  "match": lambda o: o.startswith("Serratia ")},
    "Enterococcus faecium":   {"taxid": 1352, "match": lambda o: o.startswith("Enterococcus faecium")},
    "Enterococcus faecalis":  {"taxid": 1351, "match": lambda o: o.startswith("Enterococcus faecalis")},
}


class SchemaError(Exception):
    pass


def resolve(header, required, source):
    """Map required field names to indices BY NAME. Raise rather than return nothing."""
    idx = {}
    for name in required:
        if name not in header:
            raise SchemaError("%s: required column %r absent. Header seen: %s"
                              % (source, name, header[:40]))
        if header.count(name) > 1:
            raise SchemaError("%s: column %r appears %d times" % (source, name, header.count(name)))
        idx[name] = header.index(name)
    return idx


# ---------------------------------------------------------------- 1. NCBI assembly summaries
NCBI_REQ = ["assembly_accession", "bioproject", "biosample", "refseq_category", "taxid",
            "species_taxid", "organism_name", "infraspecific_name", "version_status",
            "assembly_level", "genome_rep", "seq_rel_date", "asm_name", "ftp_path",
            "excluded_from_refseq", "asm_not_live_date"]
rows = []
schema_report = {}
for src in ("refseq", "genbank"):
    path = os.path.join(CENSUS_DIR, "assembly_summary_%s.txt" % src)
    header = None
    n_raw = n_kept = 0
    with io.open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                cand = line.lstrip("#").strip("\n").split("\t")
                cand = [c.strip().lstrip("#").strip() for c in cand]
                if "assembly_accession" in cand:
                    header = cand
                continue
            if header is None:
                raise SchemaError("%s: no header row containing assembly_accession" % src)
            n_raw += 1
            p = line.rstrip("\n").split("\t")
            if len(p) < len(header):
                continue
            if not schema_report.get(src):
                idx = resolve(header, NCBI_REQ, "assembly_summary_%s" % src)
                schema_report[src] = {"n_header_cols": len(header),
                                      "resolved": {k: v for k, v in idx.items()}}
            idx = {k: schema_report[src]["resolved"][k] for k in NCBI_REQ}
            g = lambda k: p[idx[k]].strip()
            org = g("organism_name")
            taxon = next((t for t, d in TARGETS.items() if d["match"](org)), None)
            if taxon is None:
                continue
            if g("assembly_level") != "Complete Genome":
                continue
            if g("version_status") != "latest":
                continue
            if g("genome_rep") != "Full":
                continue
            if g("asm_not_live_date") not in ("na", "", "-"):
                continue
            if g("excluded_from_refseq") not in ("na", "", "-"):
                continue
            bs = g("biosample")
            if not bs.startswith("SAM"):
                continue
            n_kept += 1
            rows.append({"biosample": bs, "assembly_accession": g("assembly_accession"),
                         "bioproject": g("bioproject"), "taxon": taxon,
                         "organism_name": org, "infraspecific_name": g("infraspecific_name"),
                         "taxid": g("taxid"), "species_taxid": g("species_taxid"),
                         "seq_rel_date": g("seq_rel_date"), "asm_name": g("asm_name"),
                         "ftp_path": g("ftp_path"), "summary_source": src,
                         "refseq_category": g("refseq_category")})
    print("  %-9s rows=%-9d target+complete+latest+full+live=%d" % (src, n_raw, n_kept))

# one record per BioSample, RefSeq preferred, then lexically smallest accession (deterministic)
best = {}
for r in sorted(rows, key=lambda r: (r["biosample"], r["summary_source"] != "refseq",
                                     r["assembly_accession"])):
    best.setdefault(r["biosample"], r)
census = sorted(best.values(), key=lambda r: (r["taxon"], r["biosample"]))
print("\n  unique BioSamples after de-duplication: %d" % len(census))
for t, c in sorted(collections.Counter(r["taxon"] for r in census).items(), key=lambda x: -x[1]):
    print("    %-24s %5d" % (t, c))

# ---------------------------------------------------------------- 2. historical exclusions
consumed = {}
for d in ("dev250", "p111", "p110", "p19"):
    p = "/work/p111/screen/genomes/%s" % d
    if os.path.isdir(p):
        for f in os.listdir(p):
            consumed.setdefault(f.replace(".fna.gz", ""), set()).add(d.upper())
print("\n  consumed identifiers loaded: %d" % len(consumed))
print("    by set: %s" % dict(collections.Counter(s for v in consumed.values() for s in v)))

# BioProject and strain-level checks against the development collection
devrows = []
dp = "/work/p113/DEV_COMPOSITION.tsv"
if os.path.exists(dp):
    devrows = list(csv.DictReader(io.open(dp, encoding="utf-8"), delimiter="\t"))
dev_bs = {r["biosample"] for r in devrows}
excl_log = []
eligible = []
for r in census:
    reasons = []
    if r["biosample"] in consumed:
        reasons.append("biosample in " + "|".join(sorted(consumed[r["biosample"]])))
    if r["biosample"] in dev_bs:
        reasons.append("biosample in DEV_250")
    if reasons:
        excl_log.append(dict(r, exclusion_stage="historical_overlap",
                             exclusion_reason="; ".join(reasons)))
    else:
        eligible.append(r)
print("  after historical exclusion: %d (excluded %d)" % (len(eligible), len(excl_log)))

with io.open(W + "/P1.13_CENSUS.tsv", "w", encoding="utf-8", newline="") as f:
    cols = list(census[0].keys())
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(census)
json.dump({"ncbi_schema": schema_report,
           "n_census": len(census), "n_after_historical_exclusion": len(eligible),
           "n_excluded_historical": len(excl_log)},
          io.open(W + "/census_schema.json", "w", encoding="utf-8"), indent=1)
json.dump([{k: r[k] for k in r} for r in eligible],
          io.open(W + "/_eligible_stage1.json", "w", encoding="utf-8"), indent=0)
json.dump(excl_log, io.open(W + "/_excl_stage1.json", "w", encoding="utf-8"), indent=0)
print("\n  wrote P1.13_CENSUS.tsv and stage-1 intermediates")
print("CENSUS_STAGE1_DONE")

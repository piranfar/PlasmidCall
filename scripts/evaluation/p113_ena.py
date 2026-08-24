#!/usr/bin/env python3
"""P1.13 stage 2 -- ENA read linkage, resolved BY RETURNED HEADER NAME with fail-loud validation.

ENA does not honour the order of the `fields` parameter, so every field is located by name in the
response header. A missing or renamed field raises rather than silently yielding nothing.
"""
import collections, csv, io, json, os, subprocess, sys, urllib.parse

W = "/work/p113"
CENSUS_DIR = "/work/p113_census"
TAXIDS = {573: "Klebsiella pneumoniae", 547: "Enterobacter spp.", 544: "Citrobacter spp.",
          613: "Serratia spp.", 1352: "Enterococcus faecium", 1351: "Enterococcus faecalis"}
REQ = ["sample_accession", "run_accession", "instrument_platform", "instrument_model",
       "library_layout", "library_source", "library_strategy", "library_selection",
       "read_count", "base_count", "fastq_ftp", "fastq_md5", "fastq_bytes", "study_accession"]


class SchemaError(Exception):
    pass


def ena(taxid):
    q = ("tax_tree(%d) AND instrument_platform=ILLUMINA AND library_layout=PAIRED "
         "AND library_source=GENOMIC AND library_strategy=WGS" % taxid)
    url = "https://www.ebi.ac.uk/ena/portal/api/search?" + urllib.parse.urlencode(
        {"result": "read_run", "query": q, "fields": ",".join(REQ),
         "format": "tsv", "limit": "0"})
    out = subprocess.run(["curl", "-sSG", "--max-time", "900", "--retry", "2", url],
                         capture_output=True, text=True).stdout
    lines = out.splitlines()
    if not lines:
        raise SchemaError("taxid %d: empty ENA response" % taxid)
    header = lines[0].split("\t")
    missing = [f for f in REQ if f not in header]
    if missing:
        raise SchemaError("taxid %d: ENA response missing fields %s. Header: %s"
                          % (taxid, missing, header))
    idx = {f: header.index(f) for f in REQ}          # BY NAME, never by requested order
    recs = []
    for ln in lines[1:]:
        p = ln.split("\t")
        if len(p) < len(header):
            continue
        g = lambda k: p[idx[k]].strip()
        if not g("sample_accession").startswith("SAM"):
            continue
        if g("instrument_platform") != "ILLUMINA":       # verified, not assumed from the query
            continue
        if g("library_layout") != "PAIRED":
            continue
        if g("library_source") != "GENOMIC":             # excludes METAGENOMIC libraries
            continue
        if g("library_strategy") != "WGS":
            continue
        if ";" not in g("fastq_ftp"):                    # two mates present
            continue
        if g("fastq_ftp").count(";") != g("fastq_md5").count(";"):
            continue
        try:
            rc = int(g("read_count") or 0); bc = int(g("base_count") or 0)
        except ValueError:
            continue
        if rc <= 0 or bc <= 0:
            continue
        recs.append({f: g(f) for f in REQ})
    return header, recs


allrec = []
hdr_seen = {}
for t, name in TAXIDS.items():
    h, r = ena(t)
    hdr_seen[str(t)] = h
    allrec.extend(r)
    print("  taxid %-5d %-24s usable runs: %6d   (cumulative %d)" % (t, name, len(r), len(allrec)))

by_sample = collections.defaultdict(list)
for r in allrec:
    by_sample[r["sample_accession"]].append(r)
print("\n  distinct BioSamples with a usable Illumina WGS paired run: %d" % len(by_sample))

# genome_size by assembly, for coverage estimation, resolved by header name
gs = {}
for src in ("refseq", "genbank"):
    p = os.path.join(CENSUS_DIR, "assembly_summary_%s.txt" % src)
    header = None
    with io.open(p, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                c = [x.strip().lstrip("#").strip() for x in line.lstrip("#").strip("\n").split("\t")]
                if "assembly_accession" in c:
                    header = c
                continue
            if header is None:
                continue
            if "genome_size" not in header or "biosample" not in header:
                raise SchemaError("%s: genome_size/biosample absent from header" % src)
            q = line.rstrip("\n").split("\t")
            if len(q) < len(header):
                continue
            b = q[header.index("biosample")].strip()
            v = q[header.index("genome_size")].strip()
            if b.startswith("SAM") and v.isdigit():
                gs.setdefault(b, int(v))

elig = json.load(io.open(W + "/_eligible_stage1.json", encoding="utf-8"))
joined = []
no_reads = []
for r in elig:
    runs = by_sample.get(r["biosample"])
    if not runs:
        no_reads.append(dict(r, exclusion_stage="no_reads",
                             exclusion_reason="no ENA Illumina WGS PAIRED GENOMIC run for this BioSample"))
        continue
    g = gs.get(r["biosample"], 0)
    # deterministic run rule, frozen here: highest base_count, then lexically smallest run accession
    runs = sorted(runs, key=lambda x: (-int(x["base_count"]), x["run_accession"]))
    top = runs[0]
    covg = (int(top["base_count"]) / g) if g else 0.0
    joined.append(dict(r, genome_size=g, n_runs_available=len(runs),
                       run_accession=top["run_accession"],
                       study_accession=top["study_accession"],
                       instrument_model=top["instrument_model"],
                       library_selection=top["library_selection"],
                       read_count=top["read_count"], base_count=top["base_count"],
                       fastq_ftp=top["fastq_ftp"], fastq_md5=top["fastq_md5"],
                       fastq_bytes=top["fastq_bytes"],
                       estimated_coverage=round(covg, 1)))
print("  eligible with reads: %d   (without: %d)" % (len(joined), len(no_reads)))

MIN_COV = 30.0
lowcov = [dict(r, exclusion_stage="low_coverage",
               exclusion_reason="estimated coverage %.1fx below the frozen 30x floor"
                                % r["estimated_coverage"])
          for r in joined if r["estimated_coverage"] < MIN_COV]
joined = [r for r in joined if r["estimated_coverage"] >= MIN_COV]
print("  after the 30x minimum-coverage floor: %d (dropped %d)" % (len(joined), len(lowcov)))

for lbl, sub in (("all", joined),
                 (">=2024", [r for r in joined if r["seq_rel_date"][:4] >= "2024"]),
                 (">=2023", [r for r in joined if r["seq_rel_date"][:4] >= "2023"])):
    c = collections.Counter(r["taxon"] for r in sub)
    print("\n  pool %s: %d" % (lbl, len(sub)))
    for t in sorted(TAXIDS.values()):
        print("    %-24s %5d" % (t, c.get(t, 0)))

json.dump(joined, io.open(W + "/_eligible_stage2.json", "w", encoding="utf-8"), indent=0)
json.dump(no_reads + lowcov, io.open(W + "/_excl_stage2.json", "w", encoding="utf-8"), indent=0)
json.dump({"ena_headers": hdr_seen, "min_coverage": MIN_COV,
           "run_selection_rule": "highest base_count, then lexically smallest run_accession",
           "n_with_reads": len(joined) + len(lowcov), "n_low_coverage": len(lowcov)},
          io.open(W + "/ena_schema.json", "w", encoding="utf-8"), indent=1)
print("\nENA_STAGE2_DONE")

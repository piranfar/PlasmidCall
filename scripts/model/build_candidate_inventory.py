#!/usr/bin/env python3
"""P1.10-F: build the candidate inventory for the strictly independent validation cohort.
Metadata only - no sequence downloads. Writes the inventory + ledger to the P1.10 data directory."""
import json, time, urllib.request, urllib.parse, csv, os, sys, datetime
import xml.etree.ElementTree as ET

OUT = r"E:/AMR_Evidence_Data/P1.9_cleanroom/p110"
os.makedirs(OUT, exist_ok=True)
EUT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
TOOL = "tool=amr_evidence_warehouse_p110&email=vahab.p@gmail.com"
DATE_FLOOR = "2025/09/11"          # day after the newest frozen panel DB (PlasmidFinder DB 2025-09-10)

P19 = {"SAMD00056131","SAMN02991226","SAMN04014847","SAMN04014852","SAMN04014855",
       "SAMN04014856","SAMN04014858","SAMN04014860"}
DEV = set()
with open(r"<local>/amr-evidence-warehouse/docs/plans/P1.9_development_benchmark_accessions.csv") as f:
    for r in csv.DictReader(f):
        if r.get("BioSample"): DEV.add(r["BioSample"].strip())

def get(url, tries=5):
    for a in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r: return r.read()
        except Exception as e:
            if a == tries - 1: raise
            time.sleep(3 * (a + 1))

# ---- 1. enumerate E. coli complete RefSeq genomes released on/after the floor
# NOTE: esearch on db=assembly has no usable release-date range field ([ASRD] rejects ':'),
# so the whole E. coli complete-genome set is enumerated and the date floor is applied client-side.
term = 'txid562[Organism:exp] AND "complete genome"[Assembly Level] AND "latest refseq"[filter]'
q = EUT + "esearch.fcgi?db=assembly&term=" + urllib.parse.quote(term) + "&usehistory=y&retmode=json&" + TOOL
d = json.loads(get(q))["esearchresult"]
count = int(d["count"]); webenv = d["webenv"]; qk = d["querykey"]
print(f"[1] E. coli complete RefSeq assemblies (all): {count}; date floor {DATE_FLOOR} applied client-side", flush=True)

# ---- 2. esummary in pages
recs = []
for start in range(0, count, 200):
    u = (EUT + f"esummary.fcgi?db=assembly&WebEnv={webenv}&query_key={qk}&retstart={start}"
         f"&retmax=200&retmode=json&" + TOOL)
    js = json.loads(get(u))["result"]
    for uid in js.get("uids", []):
        r = js[uid]
        meta = r.get("meta", "")
        def stat(cat):
            k = f'<Stat category="{cat}" sequence_tag="all">'
            if k in meta:
                try: return int(meta.split(k)[1].split("<")[0])
                except Exception: return None
            return None
        recs.append({
            "assembly_accession": r.get("assemblyaccession"),
            "biosample": r.get("biosampleaccn"),
            "bioproject": r.get("gb_bioprojects", [{}])[0].get("bioprojectaccn") if r.get("gb_bioprojects") else r.get("bioprojectaccn", ""),
            "strain": (r.get("biosource", {}) or {}).get("infraspecieslist", [{}])[0].get("sub_value", "") if (r.get("biosource", {}) or {}).get("infraspecieslist") else "",
            "organism": r.get("organism", ""),
            "submitter": r.get("submitterorganization", ""),
            "assembly_release_date": (r.get("asmreleasedate_refseq") or r.get("seqreleasedate") or "")[:10],
            "assembly_level": r.get("assemblystatus", ""),
            "n_chromosome": stat("chromosome_count"),
            "n_plasmid": stat("non_chromosome_replicon_count"),
            "total_length": stat("total_length"),
            "ftppath_refseq": r.get("ftppath_refseq", ""),
        })
    print(f"    esummary {min(start+200,count)}/{count}", flush=True); time.sleep(0.4)
print(f"[2] summarised: {len(recs)}", flush=True)

# ---- 3. filters
def keep(r):
    return (r["biosample"] and r["biosample"].startswith("SAM")
            and (r["n_plasmid"] or 0) >= 1
            and (r["n_chromosome"] or 0) == 1
            and r["biosample"] not in P19 and r["biosample"] not in DEV
            and r["assembly_release_date"] >= "2025-09-11")
pool = [r for r in recs if keep(r)]
excl = {"no_plasmid": sum(1 for r in recs if (r["n_plasmid"] or 0) < 1),
        "not_single_chromosome": sum(1 for r in recs if (r["n_chromosome"] or 0) != 1),
        "in_P1.9": sum(1 for r in recs if r["biosample"] in P19),
        "in_development_250": sum(1 for r in recs if r["biosample"] in DEV),
        "date_below_floor": sum(1 for r in recs if r["assembly_release_date"] < "2025-09-11")}
print(f"[3] pool after replicon/date/overlap filters: {len(pool)}   exclusions: {excl}", flush=True)

# ---- 4. Illumina paired reads on the SAME BioSample (ENA portal)
bs = sorted({r["biosample"] for r in pool})
reads = {}
for i in range(0, len(bs), 90):
    chunk = bs[i:i+90]
    qq = "(" + " OR ".join(f'sample_accession="{b}"' for b in chunk) + ') AND instrument_platform="ILLUMINA" AND library_layout="PAIRED"'
    url = ("https://www.ebi.ac.uk/ena/portal/api/search?result=read_run&format=tsv&limit=0"
           "&fields=sample_accession,run_accession,instrument_model,library_source,library_strategy,base_count,fastq_ftp,fastq_bytes"
           "&query=" + urllib.parse.quote(qq))
    try:
        txt = get(url).decode()
        for row in csv.DictReader(txt.splitlines(), delimiter="\t"):
            if row.get("library_source") == "GENOMIC" and row.get("library_strategy") in ("WGS", "WGA") and row.get("fastq_ftp"):
                reads.setdefault(row["sample_accession"], []).append(row)
    except Exception as e:
        print("    ENA batch error", e, flush=True)
    print(f"    ENA {min(i+90,len(bs))}/{len(bs)}", flush=True); time.sleep(0.4)
print(f"[4] BioSamples with public Illumina PAIRED WGS runs: {len(reads)}", flush=True)

qualifying = []
for r in pool:
    rr = reads.get(r["biosample"])
    if not rr: continue
    rr = sorted(rr, key=lambda x: -int(x.get("base_count") or 0))
    best = rr[0]
    q = dict(r)
    q.update({"run_accessions": ";".join(x["run_accession"] for x in rr),
              "primary_run": best["run_accession"], "instrument": best["instrument_model"],
              "base_count": best.get("base_count", ""), "fastq_bytes": best.get("fastq_bytes", ""),
              "fastq_ftp": best.get("fastq_ftp", ""), "n_runs": len(rr)})
    qualifying.append(q)
print(f"[5] QUALIFYING CANDIDATES: {len(qualifying)}", flush=True)

cols = ["biosample","assembly_accession","bioproject","organism","strain","submitter",
        "assembly_release_date","assembly_level","n_chromosome","n_plasmid","total_length",
        "primary_run","run_accessions","n_runs","instrument","base_count","fastq_bytes","fastq_ftp","ftppath_refseq"]
with open(f"{OUT}/P1.10F_candidate_inventory.tsv","w",newline="",encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore"); w.writeheader()
    for r in sorted(qualifying, key=lambda x: (x["submitter"], x["assembly_release_date"])): w.writerow(r)
with open(f"{OUT}/P1.10F_exclusion_ledger.json","w") as f:
    json.dump({"utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "date_floor": "2025-09-11",
               "date_floor_rationale": "day after the newest frozen panel database (PlasmidFinder DB tag 2.2.0 = commit 2025-09-10); "
                                       "all other panel DBs are older, so no candidate's own closed plasmids can be inside any frozen tool database",
               "esearch_term": term, "assemblies_returned": count, "summarised": len(recs),
               "exclusions": excl, "pool_after_filters": len(pool),
               "biosamples_with_illumina_paired_wgs": len(reads), "qualifying": len(qualifying),
               "distinct_bioprojects": len({r["bioproject"] for r in qualifying}),
               "distinct_submitters": len({r["submitter"] for r in qualifying})}, f, indent=1)
print("distinct BioProjects:", len({r["bioproject"] for r in qualifying}),
      " distinct submitters:", len({r["submitter"] for r in qualifying}))
print("total plasmid replicons across candidates:", sum(r["n_plasmid"] for r in qualifying))

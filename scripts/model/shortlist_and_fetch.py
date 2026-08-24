#!/usr/bin/env python3
"""P1.10-F step 2: diversity-capped shortlist of candidates, then fetch genome FASTA for the
shortlist AND for all 250 development isolates, for the sequence-level independence screen.
Selection uses ONLY metadata (submitter/project/date/replicon structure) - never any tool or
Model 1 prediction, and never any expected outcome."""
import csv, json, os, time, urllib.request, urllib.parse, hashlib, datetime, random

OUT = r"E:/AMR_Evidence_Data/P1.9_cleanroom/p110"
GEN = OUT + "/genomes"; os.makedirs(GEN + "/candidates", exist_ok=True); os.makedirs(GEN + "/dev250", exist_ok=True)
EUT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"; TOOL = "tool=amr_p110&email=vahab.p@gmail.com"
SHORTLIST_N = 80           # screened; the final cohort is chosen from those that pass independence
PER_SUBMITTER = 3          # diversity cap
PER_BIOPROJECT = 3

def get(u, tries=5):
    for a in range(tries):
        try:
            with urllib.request.urlopen(u, timeout=180) as r: return r.read()
        except Exception:
            if a == tries - 1: raise
            time.sleep(3 * (a + 1))

rows = list(csv.DictReader(open(f"{OUT}/P1.10F_candidate_inventory.tsv", encoding="utf-8"), delimiter="\t"))
# deterministic diversity-capped selection: sort by (release date desc, biosample) then cap
rows.sort(key=lambda r: (r["assembly_release_date"], r["biosample"]), reverse=True)
sub_n, proj_n, short = {}, {}, []
for r in rows:
    s, p = r["submitter"], r["bioproject"]
    if sub_n.get(s, 0) >= PER_SUBMITTER or proj_n.get(p, 0) >= PER_BIOPROJECT: continue
    sub_n[s] = sub_n.get(s, 0) + 1; proj_n[p] = proj_n.get(p, 0) + 1
    short.append(r)
    if len(short) >= SHORTLIST_N: break
print(f"shortlist: {len(short)}  submitters={len(sub_n)}  bioprojects={len(proj_n)}", flush=True)
with open(f"{OUT}/P1.10F_shortlist.tsv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter="\t"); w.writeheader(); w.writerows(short)

def fetch_fna(ftp, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 10000: return True
    base = ftp.rstrip("/").split("/")[-1]
    url = ftp.replace("ftp://", "https://") + "/" + base + "_genomic.fna.gz"
    try:
        open(dest, "wb").write(get(url)); return True
    except Exception as e:
        print("   FAIL", dest, e); return False

print("fetching candidate genomes ...", flush=True)
ok = 0
for i, r in enumerate(short, 1):
    if fetch_fna(r["ftppath_refseq"], f"{GEN}/candidates/{r['biosample']}.fna.gz"): ok += 1
    if i % 20 == 0: print(f"   {i}/{len(short)}", flush=True)
print(f"candidate genomes fetched: {ok}/{len(short)}", flush=True)

# ---- development 250: resolve BioSample -> assembly ftp, then fetch
dev = [r["BioSample"].strip() for r in csv.DictReader(
        open(r"<local>/amr-evidence-warehouse/docs/plans/P1.9_development_benchmark_accessions.csv"))
       if r.get("BioSample")]
print(f"resolving {len(dev)} development BioSamples -> assemblies ...", flush=True)
ftp_by_bs, uid_by_bs = {}, {}
for i in range(0, len(dev), 40):
    chunk = dev[i:i+40]
    term = " OR ".join(f"{b}[Accession]" for b in chunk)
    js = json.loads(get(EUT + "esearch.fcgi?db=biosample&term=" + urllib.parse.quote(term) + "&retmax=100&retmode=json&" + TOOL))
    uids = js["esearchresult"]["idlist"]
    if not uids: continue
    link = json.loads(get(EUT + "elink.fcgi?dbfrom=biosample&db=assembly&retmode=json&" + TOOL +
                          "".join(f"&id={u}" for u in uids)))
    aids = []
    for ls in link.get("linksets", []):
        for db in ls.get("linksetdbs", []):
            if db.get("linkname") == "biosample_assembly": aids += db.get("links", [])
    if aids:
        for j in range(0, len(aids), 150):
            su = json.loads(get(EUT + "esummary.fcgi?db=assembly&id=" + ",".join(aids[j:j+150]) + "&retmode=json&" + TOOL))["result"]
            for uid in su.get("uids", []):
                a = su[uid]; bs = a.get("biosampleaccn")
                f = a.get("ftppath_refseq") or a.get("ftppath_genbank")
                if bs and f:
                    # prefer the most contiguous assembly per BioSample
                    rank = {"Complete Genome": 0, "Chromosome": 1, "Scaffold": 2, "Contig": 3}.get(a.get("assemblystatus"), 4)
                    cur = ftp_by_bs.get(bs)
                    if cur is None or rank < cur[1]: ftp_by_bs[bs] = (f, rank)
    print(f"   resolved {min(i+40,len(dev))}/{len(dev)}  mapped={len(ftp_by_bs)}", flush=True); time.sleep(0.4)
print(f"development BioSamples with an assembly ftp: {len(ftp_by_bs)}/{len(dev)}", flush=True)

print("fetching development genomes ...", flush=True)
okd = 0
for i, (bs, (f, _)) in enumerate(sorted(ftp_by_bs.items()), 1):
    if fetch_fna(f, f"{GEN}/dev250/{bs}.fna.gz"): okd += 1
    if i % 25 == 0: print(f"   {i}/{len(ftp_by_bs)}", flush=True)
print(f"development genomes fetched: {okd}/{len(ftp_by_bs)}", flush=True)

json.dump({"utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "shortlist_n": len(short), "shortlist_submitters": len(sub_n), "shortlist_bioprojects": len(proj_n),
           "per_submitter_cap": PER_SUBMITTER, "per_bioproject_cap": PER_BIOPROJECT,
           "candidate_genomes_fetched": ok, "dev_biosamples_resolved": len(ftp_by_bs),
           "dev_genomes_fetched": okd,
           "selection_rule": "metadata only: sort by release date desc then BioSample, cap 3 per submitter and 3 per BioProject; "
                             "no tool output, no Model 1 prediction and no expected outcome participates"},
          open(f"{OUT}/P1.10F_fetch_receipt.json", "w"), indent=1)
print("done")

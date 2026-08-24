#!/usr/bin/env python3
"""P1.13 deterministic single-isolate replacement for a technically excluded isolate.

Applies the ALREADY FROZEN selection rule from env/p113_select.py, unchanged:
  1. eligibility and historical-overlap exclusions (already applied upstream)
  2. drop any candidate with ANI >= 99.5 to ANY consumed genome
  3. prioritise the most recent permitted release year (2024+ before 2023)
  4. farthest-point genomic selection on the frozen distance (100 - ANI), skani 0.2.2 --min-af 15
  5. assembly accession lexical order as the final deterministic tie-breaker

The 24 surviving isolates of the affected taxon are held FIXED and exactly ONE additional isolate
is drawn. Re-running the whole taxon greedily would churn other members, which would change more
of the cohort than the single technical exclusion requires.

Truth-blind: reads no plasmid count, truth, ARG content, tool output, model score or any assembly
outcome. The excluded isolate is removed for a documented contamination finding only.
"""
import collections, csv, hashlib, io, json, os, sys

W = "/work/p113"
THRESH = 99.5
EXCLUDED = "SAMN26198730"
TAXON = "Enterococcus faecalis"


def sha(p):
    d = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def bs(path):
    return os.path.basename(path).replace(".fna.gz", "")


# ---- rebuild the pool exactly as the frozen selector did -------------------------------------
rows = json.load(io.open(W + "/_eligible_stage2.json", encoding="utf-8"))
pool = {r["biosample"]: r for r in rows if r["seq_rel_date"][:4] >= "2023"}

avail = {}
for ln in io.open(W + "/file_availability.tsv", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) >= 5:
        avail[p[0]] = p[4]
for k in list(pool):
    if avail.get(k) != "OK":
        pool.pop(k)

worst = {}
for ln in io.open(W + "/screen/p113_vs_consumed.tsv", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) < 3 or p[0].startswith("Ref_file"):
        continue
    try:
        ani = float(p[2])
    except ValueError:
        continue
    q, r = bs(p[1]), bs(p[0])
    cur = worst.get(q)
    if cur is None or ani > cur[0]:
        worst[q] = (ani, r)
for k in list(pool):
    w = worst.get(k)
    if w and w[0] >= THRESH:
        pool.pop(k)

pair = collections.defaultdict(dict)
for ln in io.open(W + "/screen/p113_vs_p113.tsv", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) < 3 or p[0].startswith("Ref_file"):
        continue
    try:
        ani = float(p[2])
    except ValueError:
        continue
    a, b = bs(p[0]), bs(p[1])
    if a == b:
        continue
    pair[a][b] = max(pair[a].get(b, 0.0), ani)
    pair[b][a] = max(pair[b].get(a, 0.0), ani)


def dist(a, b):
    """Frozen distance. Pairs skani did not report are below --min-af 15, i.e. maximally distant."""
    return 100.0 - pair.get(a, {}).get(b, 0.0)


# ---- current cohort --------------------------------------------------------------------------
cohort = []
with io.open(W + "/P1.13_SELECTED_COHORT_v2.tsv", encoding="utf-8") as f:
    hdr = f.readline().rstrip("\n").split("\t")
    for line in f:
        cohort.append(dict(zip(hdr, line.rstrip("\n").split("\t"))))
selected_all = {r["biosample"] for r in cohort}
kept = [r for r in cohort if r["biosample"] != EXCLUDED]
chosen = [r["biosample"] for r in kept if r.get("taxon") == TAXON]

print("cohort before        : %d" % len(cohort))
print("excluded             : %s (%s)" % (EXCLUDED, TAXON))
print("%s retained: %d" % (TAXON, len(chosen)))

# ---- candidate set: same taxon, eligible, not already used, not the excluded isolate ----------
cand = {k: v for k, v in pool.items()
        if v.get("taxon") == TAXON and k not in selected_all}
poolA = sorted([k for k in cand if cand[k]["seq_rel_date"][:4] >= "2024"],
               key=lambda k: cand[k]["assembly_accession"])
poolB = sorted([k for k in cand if cand[k]["seq_rel_date"][:4] == "2023"],
               key=lambda k: cand[k]["assembly_accession"])
print("available candidates : 2024+=%d  2023=%d" % (len(poolA), len(poolB)))

pick, year_pool, rejected_for_ani = None, None, []
for from_pool, tag in ((poolA, "2024+"), (poolB, "2023 fallback")):
    avail_set = list(from_pool)
    while avail_set and pick is None:
        best = None
        for k in avail_set:
            d = min(dist(k, s) for s in chosen)
            key = (-d, cand[k]["assembly_accession"])     # farthest first, then lexical
            if best is None or key < best[0]:
                best = (key, k)
        c = best[1]
        if min(dist(c, s) for s in chosen) <= (100.0 - THRESH):
            rejected_for_ani.append(c)
            avail_set = [k for k in avail_set if k != c]
            continue
        pick, year_pool = c, tag
    if pick:
        break

if pick is None:
    print("NO ELIGIBLE REPLACEMENT AVAILABLE")
    sys.exit(2)

md = min(dist(pick, s) for s in chosen)
print("selected replacement : %s" % pick)
print("  assembly_accession : %s" % cand[pick]["assembly_accession"])
print("  release date       : %s  (%s pool)" % (cand[pick]["seq_rel_date"], year_pool))
print("  min distance to the 24 retained: %.4f  (= ANI %.4f)" % (md, 100.0 - md))
print("  candidates skipped for ANI >= %.1f: %d" % (THRESH, len(rejected_for_ani)))

out = {
    "excluded_isolate": EXCLUDED,
    "taxon": TAXON,
    "retained_in_taxon": len(chosen),
    "candidates_considered": {"2024_plus": len(poolA), "2023": len(poolB)},
    "skipped_for_ani_independence": rejected_for_ani,
    "selected_replacement": pick,
    "selected_assembly_accession": cand[pick]["assembly_accession"],
    "selected_release_date": cand[pick]["seq_rel_date"],
    "selected_year_pool": year_pool,
    "min_distance_to_retained": round(md, 6),
    "equivalent_min_ani": round(100.0 - md, 6),
    "rule": "frozen: eligibility, ANI<99.5 vs consumed and vs selected, most recent year pool "
            "first, farthest-point on 100-ANI, assembly accession lexical tie-break",
    "inputs": {
        "_eligible_stage2.json": sha(W + "/_eligible_stage2.json"),
        "file_availability.tsv": sha(W + "/file_availability.tsv"),
        "screen/p113_vs_consumed.tsv": sha(W + "/screen/p113_vs_consumed.tsv"),
        "screen/p113_vs_p113.tsv": sha(W + "/screen/p113_vs_p113.tsv"),
        "P1.13_ELIGIBLE_POOL.tsv": sha(W + "/P1.13_ELIGIBLE_POOL.tsv"),
        "cohort_before": sha(W + "/P1.13_SELECTED_COHORT_v2.tsv"),
    },
    "truth_blind": "no plasmid count, truth, ARG content, tool output, model score or assembly "
                   "outcome was read in selection",
}
io.open(W + "/P1.13_REPLACEMENT_SELECTION.json", "w", encoding="utf-8").write(
    json.dumps(out, indent=1) + "\n")

# ---- write the amended cohort ---------------------------------------------------------------
newrow = dict(cand[pick])
tmpl = kept[0]
row = {}
for k in hdr:
    row[k] = newrow.get(k, "")
row["biosample"] = pick
row["taxon"] = TAXON
missing = [k for k in hdr if not row[k]]
print("  fields not present in the eligible-pool record: %s" % (missing or "none"))
io.open(W + "/P1.13_REPLACEMENT_ROW_GAPS.json", "w", encoding="utf-8").write(
    json.dumps({"missing_fields": missing, "biosample": pick}, indent=1) + "\n")
print("\nreplacement selection written to P1.13_REPLACEMENT_SELECTION.json")
print("run accession and file metadata must now be resolved from ENA before the cohort is amended")

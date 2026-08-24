#!/usr/bin/env python3
"""P1.13 stage 5 -- deterministic, truth-blind cohort selection.

Order of criteria, exactly as frozen in the design:
  1. all eligibility and historical-overlap exclusions already applied upstream
  2. drop any candidate with ANI >= 99.5 to ANY consumed genome (development, P1.9, P1.10, P1.11)
  3. prioritise the most recent permitted release year: the 2024+ pool is exhausted before 2023
  4. farthest-point genomic selection using the frozen distance (skani 0.2.2, --min-af 15)
  5. assembly accession lexical order as the final deterministic tie-breaker

Nothing derived from plasmid count, truth, ARG content, tool output or model score is read.
"""
import collections, csv, io, json, os, sys

W = "/work/p113"
THRESH = 99.5
TARGET_PER_TAXON = 25
TAXA = ["Klebsiella pneumoniae", "Enterobacter spp.", "Citrobacter spp.", "Serratia spp.",
        "Enterococcus faecium", "Enterococcus faecalis"]


def bs(path):
    return os.path.basename(path).replace(".fna.gz", "")


rows = json.load(io.open(W + "/_eligible_stage2.json", encoding="utf-8"))
pool = {r["biosample"]: r for r in rows if r["seq_rel_date"][:4] >= "2023"}
print("pool 2023+ : %d" % len(pool))

# file availability gate
avail = {}
for ln in io.open(W + "/file_availability.tsv", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) >= 5:
        avail[p[0]] = p[4]
excl = []
for k in list(pool):
    if avail.get(k) != "OK":
        excl.append(dict(pool[k], exclusion_stage="file_availability",
                         exclusion_reason="assembly report / genomic FASTA / GBFF not all present"))
        pool.pop(k)
print("after file-availability gate: %d" % len(pool))

# ---- ANI vs consumed
worst = {}
n = 0
for ln in io.open(W + "/screen/p113_vs_consumed.tsv", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) < 3 or p[0].startswith("Ref_file"):
        continue
    n += 1
    try:
        ani = float(p[2])
    except ValueError:
        continue
    q, r = bs(p[1]), bs(p[0])
    cur = worst.get(q)
    if cur is None or ani > cur[0]:
        worst[q] = (ani, r)
print("consumed-comparison rows: %d ; candidates with any reported neighbour: %d" % (n, len(worst)))
drop = 0
for k in list(pool):
    w = worst.get(k)
    if w and w[0] >= THRESH:
        excl.append(dict(pool[k], exclusion_stage="ani_vs_consumed",
                         exclusion_reason="ANI %.4f >= %.1f to consumed genome %s" % (w[0], THRESH, w[1])))
        pool.pop(k); drop += 1
print("dropped for ANI >= %.1f against consumed: %d ; remaining %d" % (THRESH, drop, len(pool)))

# ---- within-pool pairwise ANI
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
    """Frozen distance. Pairs skani did not report are below its --min-af 15 floor, i.e. far."""
    return 100.0 - pair.get(a, {}).get(b, 0.0)


selected = {}
notes = []
for tax in TAXA:
    cand = {k: v for k, v in pool.items() if v["taxon"] == tax}
    poolA = sorted([k for k, v in cand.items() if v["seq_rel_date"][:4] >= "2024"],
                   key=lambda k: cand[k]["assembly_accession"])
    poolB = sorted([k for k, v in cand.items() if v["seq_rel_date"][:4] == "2023"],
                   key=lambda k: cand[k]["assembly_accession"])
    chosen = []
    used_fallback = 0

    def take(from_pool, tag):
        global used_fallback
        avail_set = [k for k in from_pool if k not in chosen]
        while len(chosen) < TARGET_PER_TAXON and avail_set:
            if not chosen:
                pick = avail_set[0]                      # deterministic seed: lexical accession
            else:
                best = None
                for k in avail_set:
                    d = min(dist(k, s) for s in chosen)
                    key = (-d, cand[k]["assembly_accession"])   # farthest first, then lexical
                    if best is None or key < best[0]:
                        best = (key, k)
                pick = best[1]
            # enforce independence within the taxon against everything already chosen
            if chosen and min(dist(pick, s) for s in chosen) <= (100.0 - THRESH):
                avail_set = [k for k in avail_set if k != pick]
                notes.append({"biosample": pick, "taxon": tax,
                              "exclusion_stage": "ani_within_p113",
                              "exclusion_reason": "ANI >= %.1f to an already-selected isolate" % THRESH})
                continue
            chosen.append(pick)
            if tag == "2023_fallback":
                used_fallback += 1
            avail_set = [k for k in avail_set if k != pick]

    take(poolA, "2024_primary")
    deficit_after_A = TARGET_PER_TAXON - len(chosen)
    if deficit_after_A > 0:
        take(poolB, "2023_fallback")
    for k in chosen:
        selected[k] = dict(cand[k], selection_taxon=tax,
                           selection_year_pool=("2024+" if cand[k]["seq_rel_date"][:4] >= "2024"
                                                else "2023 fallback"))
    print("  %-24s pool2024=%-4d pool2023=%-4d selected=%-3d fallback_used=%-3d %s"
          % (tax, len(poolA), len(poolB), len(chosen), used_fallback,
             "" if len(chosen) == TARGET_PER_TAXON else "*** DEFICIT %d ***"
             % (TARGET_PER_TAXON - len(chosen))))
    for k in cand:
        if k not in selected:
            if not any(x.get("biosample") == k for x in notes):
                notes.append({"biosample": k, "taxon": tax, "exclusion_stage": "not_selected",
                              "exclusion_reason": "eligible and independent but not chosen by the "
                                                  "farthest-point rule within the 25-isolate target"})

print("\nTOTAL SELECTED: %d / 150" % len(selected))

cols = ["biosample", "assembly_accession", "bioproject", "taxon", "organism_name",
        "infraspecific_name", "taxid", "species_taxid", "seq_rel_date", "asm_name", "ftp_path",
        "summary_source", "refseq_category", "genome_size", "n_runs_available", "run_accession",
        "study_accession", "instrument_model", "library_selection", "read_count", "base_count",
        "fastq_ftp", "fastq_md5", "fastq_bytes", "estimated_coverage", "selection_year_pool"]
with io.open(W + "/P1.13_SELECTED_COHORT.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for k in sorted(selected, key=lambda k: (selected[k]["taxon"], k)):
        w.writerow(selected[k])
with io.open(W + "/P1.13_ELIGIBLE_POOL.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols[:-1], delimiter="\t", lineterminator="\n",
                       extrasaction="ignore")
    w.writeheader()
    for k in sorted(pool):
        w.writerow(pool[k])
ecols = ["biosample", "taxon", "exclusion_stage", "exclusion_reason"]
with io.open(W + "/P1.13_EXCLUSION_LOG.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=ecols, delimiter="\t", lineterminator="\n",
                       extrasaction="ignore")
    w.writeheader()
    for r in excl + notes:
        w.writerow({k: r.get(k, "") for k in ecols})

# ---- independence audit on the selected set
mx_c = max((worst[k][0] for k in selected if k in worst), default=None)
within = []
sl = sorted(selected)
for i, a in enumerate(sl):
    for b in sl[i + 1:]:
        if selected[a]["taxon"] == selected[b]["taxon"]:
            v = pair.get(a, {}).get(b, 0.0)
            if v:
                within.append(v)
audit = {"n_selected": len(selected),
         "per_taxon": dict(collections.Counter(selected[k]["taxon"] for k in selected)),
         "year_pool": dict(collections.Counter(selected[k]["selection_year_pool"] for k in selected)),
         "max_ANI_to_any_consumed_genome": round(mx_c, 4) if mx_c else None,
         "all_below_99.5_vs_consumed": (mx_c is None or mx_c < THRESH),
         "max_within_taxon_ANI_among_selected": round(max(within), 4) if within else None,
         "all_below_99.5_within_taxon": (not within or max(within) < THRESH),
         "n_eligible_pool": len(pool), "n_excluded": len(excl) + len(notes)}
json.dump(audit, io.open(W + "/_independence_audit.json", "w", encoding="utf-8"), indent=1)
print(json.dumps(audit, indent=1))
print("SELECT_STAGE5_DONE")

#!/usr/bin/env python3
"""Assemble the 47-isolate probe dataset: continuous features + frozen categorical calls +
frozen v1.1 M2_score + truth + population membership.

v1.1's M2_score is taken as already computed by each cohort's frozen evaluation. It is NOT
recomputed, refitted or recalibrated here - v1.1 is the fixed comparator.
"""
import csv, os, json, collections

OUT = os.path.dirname(os.path.abspath(__file__))
B = r"E:/AMR_Evidence_Data/P1.9_cleanroom"
TOOLS12 = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
           "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
SRC = {
    "P1.9":  {"contig": B + "/p19c4/evaluation/P1.9C4_model1_contig_table.tsv",
              "matrix": B + "/p19c4/extracted/inference/P1.9C4_prediction_matrix.tsv"},
    "P1.10": {"contig": B + "/p110/evaluation/P1.10_model1_contig_table.tsv",
              "matrix": B + "/p110/oci_results/extracted/inference/P1.10_prediction_matrix.tsv"},
}


def truthy(x):
    return str(x).strip().lower() in ("true", "1")


feat = {}
for r in csv.DictReader(open(os.path.join(OUT, "probe_features_raw.tsv"), encoding="utf-8"), delimiter="\t"):
    feat[(r["sample"], r["contig_id"])] = r
print("feature rows: %d" % len(feat))

rows = []
missing_score = collections.Counter()
for coh, cfg in SRC.items():
    ct = {(r["sample"], r["contig_id"]): r
          for r in csv.DictReader(open(cfg["contig"], encoding="utf-8"), delimiter="\t")}
    mx = {(r["sample"], r["contig_id"]): r
          for r in csv.DictReader(open(cfg["matrix"], encoding="utf-8"), delimiter="\t")}
    print("%s: contig table %d, matrix %d" % (coh, len(ct), len(mx)))
    for k, c in ct.items():
        f = feat.get(k)
        if f is None:
            missing_score["%s:no_features" % coh] += 1
            continue
        m = mx.get(k, {})
        row = {"cohort": coh, "sample": k[0], "contig_id": k[1]}
        # ---- frozen v1.1 comparator, taken as-is
        try:
            row["v11_M2_score"] = float(c["M2_score"])
        except (KeyError, ValueError, TypeError):
            missing_score["%s:no_M2_score" % coh] += 1
            continue
        row["v11_M0_call"] = c.get("M0_call", "")
        # ---- truth and populations
        row["truth_bin"] = c.get("truth_bin", "")
        row["is_resolved"] = int(truthy(c.get("is_resolved", "")))
        row["arg_bearing"] = int(truthy(c.get("ARG_bearing_bool", "")))
        row["final_truth_label"] = c.get("final_truth_label", "")
        # ---- frozen categorical calls
        for t in TOOLS12:
            row["cat_" + t] = m.get(t, "")
        # ---- continuous + structural + state
        for kk, vv in f.items():
            if kk in ("cohort", "sample", "contig_id"):
                continue
            row[kk] = vv
        rows.append(row)

print("joined rows: %d" % len(rows))
if missing_score:
    print("  dropped:", dict(missing_score))

# population flags
for r in rows:
    res = r["is_resolved"] == 1
    r["in_CP2"] = int(res)
    r["in_CP1"] = int(res and r["arg_bearing"] == 1)

cols = list(rows[0].keys())
p = os.path.join(OUT, "probe_dataset.tsv")
with open(p, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
    w.writeheader(); w.writerows(rows)

by = collections.Counter((r["cohort"], r["in_CP2"], r["in_CP1"]) for r in rows)
print("\nPOPULATIONS")
for coh in ("P1.9", "P1.10"):
    cp2 = [r for r in rows if r["cohort"] == coh and r["in_CP2"]]
    cp1 = [r for r in rows if r["cohort"] == coh and r["in_CP1"]]
    def pn(v):
        return sum(1 for r in v if r["truth_bin"] == "1"), sum(1 for r in v if r["truth_bin"] == "0")
    a, b = pn(cp2); c, d = pn(cp1)
    print("  %-6s isolates=%2d  CP2 n=%-5d (plasmid %-4d chrom %-5d)  CP1 n=%-4d (plasmid %-4d chrom %d)"
          % (coh, len({r["sample"] for r in rows if r["cohort"] == coh}), len(cp2), a, b, len(cp1), c, d))
tot2 = [r for r in rows if r["in_CP2"]]; tot1 = [r for r in rows if r["in_CP1"]]
print("  TOTAL  isolates=%d  CP2 n=%d  CP1 n=%d" % (len({r["sample"] for r in rows}), len(tot2), len(tot1)))
print("\nwrote %s (%d cols)" % (p, len(cols)))

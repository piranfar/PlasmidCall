#!/usr/bin/env python3
"""Species-controlled cross-cohort comparison.

The earlier transferability analysis compared our 79 E. coli against the prior benchmark's
Enterobacterales column, which spans several genera — so cohort change and species narrowing were
confounded. Their per-contig table (ST23) carries the sample identifier, so their E. coli isolates
can be isolated and the comparison run E. coli vs E. coli on both sides.

Their metrics are RECOMPUTED here from their own per-contig calls, using our metric code, so any
difference cannot come from a difference in how the metric was calculated.
"""
import collections, csv, glob, io, json, math, os, sys
import numpy as np

P = "/work/p112"
D = P + "/POSTTRUTH/differentiation"
N_BOOT, SEED = 4000, 20260821
CONF = {"n": 7244, "TP": 942, "FP": 33, "TN": 6002, "FN": 267}
TOOLS = ["PlaScope", "PlasmidEC", "Plasmer", "gplas2", "MOB-recon", "Platon", "HyAsP",
         "RFPlasmid", "PLASMe", "plASgraph2", "geNomad", "PlasmidFinder"]


def rd(p):
    return csv.DictReader(io.open(p, encoding="utf-8", errors="replace"), delimiter="\t")


def prf(y, c):
    y = np.asarray(y); c = np.asarray(c)
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    fn = int(((c == 0) & (y == 1)).sum())
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if (p and r and p + r > 0) else None
    return p, r, f


def agg(y, g, c):
    """Per-isolate metric, median, isolate-bootstrap CI — the prior benchmark's aggregation."""
    iso = sorted(set(g.tolist())); V = {"prec": [], "rec": [], "F1": []}
    for s in iso:
        m = g == s
        p, r, f = prf(y[m], c[m])
        if p is not None: V["prec"].append(p)
        if r is not None: V["rec"].append(r)
        if f is not None: V["F1"].append(f)
    rng = np.random.default_rng(SEED); out = {}
    for k, v in V.items():
        if not v:
            out[k] = None; continue
        v = np.array(v)
        bs = [np.median(rng.choice(v, size=len(v), replace=True)) for _ in range(N_BOOT)]
        out[k] = (round(float(np.median(v)) * 100, 1),
                  [round(float(np.percentile(bs, 2.5)) * 100, 1),
                   round(float(np.percentile(bs, 97.5)) * 100, 1)])
    pooled = prf(y, c)
    out["pooled"] = tuple(round(x * 100, 1) if x is not None else None for x in pooled)
    out["n_isolates"] = len(iso); out["n_contigs"] = int(len(y))
    return out


def tocall(v):
    v = (v or "").strip().lower()
    return 1 if v == "plasmid" else (0 if v == "chromosome" else -1)


# ---------------------------------------------------------------- ours
predk = {(r["sample"], r["contig_id"]): r for r in
         rd(P + "/inference/frozen/P1.11_FROZEN_PREDICTIONS.tsv")}
truth = {}
for f in sorted(glob.glob(P + "/truth/*/truth_table.tsv")):
    for r in rd(f):
        truth[(r["sample"], r["contig_id"])] = r
keys = sorted(k for k, r in predk.items()
              if r["is_eligible_ge_1kb"] == "1"
              and truth.get(k, {}).get("final_truth_label") in ("plasmid", "chromosome"))
oy = np.array([1 if truth[k]["final_truth_label"] == "plasmid" else 0 for k in keys])
og = np.array([k[0] for k in keys])
oc12 = np.array([1 if predk[k]["v12_call"] == "plasmid_selected"
                 else (0 if predk[k]["v12_score_state"] == "available" else -1) for k in keys])
t_ = lambda tp: (int(((oc12 == 1) & (oy == 1)).sum()), int(((oc12 == 1) & (oy == 0)).sum()),
                 int(((oc12 == 0) & (oy == 0)).sum()), int(((oc12 == 0) & (oy == 1)).sum()))
a, b, c, d = t_(0)
if {"n": len(keys), "TP": a, "FP": b, "TN": c, "FN": d} != CONF:
    sys.exit("REFUSING: confirmatory not reproduced")
print("  GATE PASS\n")
ours = {t: np.array([tocall(predk[k][t]) for k in keys]) for t in TOOLS}

# ---------------------------------------------------------------- theirs
rows = list(rd(D + "/teixeira_percontig.tsv"))
print("  their per-contig rows: %d" % len(rows))


def subset(pred):
    sel = [r for r in rows if pred(r)]
    y = np.array([1 if r["truth"] == "plasmid" else 0 for r in sel])
    g = np.array([r["biosample"] for r in sel])
    return sel, y, g


groups = {
    "their E. coli": lambda r: r["species"].startswith("Escherichia"),
    "their Enterobacterales (all)": lambda r: r["taxon"] == "Enterobacterales",
    "their Enterobacterales excl. E. coli": lambda r: (r["taxon"] == "Enterobacterales"
                                                       and not r["species"].startswith("Escherichia")),
    "their Enterococcus": lambda r: r["taxon"] == "Enterococcus",
}
res = {}
for gname, f in groups.items():
    sel, y, g = subset(f)
    res[gname] = {t: agg(y, g, np.array([tocall(r["call_" + t]) for r in sel])) for t in TOOLS}
    res[gname]["_n"] = {"contigs": len(sel), "isolates": len(set(g.tolist())),
                        "truth_plasmid": int(y.sum())}
ourres = {t: agg(oy, og, ours[t]) for t in TOOLS}
ourres["_n"] = {"contigs": len(keys), "isolates": len(set(og.tolist())),
                "truth_plasmid": int(oy.sum())}

# ---------------------------------------------------------------- compare
out = []
for t in TOOLS:
    te = res["their E. coli"][t]; ta = res["their Enterobacterales (all)"][t]; ou = ourres[t]
    row = {"tool": t,
           "their_Ecoli_F1": te["F1"][0] if te["F1"] else None,
           "their_Ecoli_F1_CI": str(te["F1"][1]) if te["F1"] else "",
           "our_Ecoli_F1": ou["F1"][0] if ou["F1"] else None,
           "our_Ecoli_F1_CI": str(ou["F1"][1]) if ou["F1"] else "",
           "delta_F1_species_controlled": (round(ou["F1"][0] - te["F1"][0], 1)
                                           if te["F1"] and ou["F1"] else None),
           "their_Enterobacterales_F1": ta["F1"][0] if ta["F1"] else None,
           "delta_F1_uncontrolled": (round(ou["F1"][0] - ta["F1"][0], 1)
                                     if ta["F1"] and ou["F1"] else None),
           "their_Ecoli_prec": te["prec"][0] if te["prec"] else None,
           "our_Ecoli_prec": ou["prec"][0] if ou["prec"] else None,
           "delta_prec_species_controlled": (round(ou["prec"][0] - te["prec"][0], 1)
                                             if te["prec"] and ou["prec"] else None),
           "their_Ecoli_rec": te["rec"][0] if te["rec"] else None,
           "our_Ecoli_rec": ou["rec"][0] if ou["rec"] else None,
           "delta_rec_species_controlled": (round(ou["rec"][0] - te["rec"][0], 1)
                                            if te["rec"] and ou["rec"] else None)}
    out.append(row)
out.sort(key=lambda r: -(r["their_Ecoli_F1"] or 0))
with io.open(D + "/P1.11_species_controlled_transfer.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys()), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(out)


def spear(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return round(float(np.corrcoef(ra, rb)[0, 1]), 4)


ctrl = [abs(r["delta_F1_species_controlled"]) for r in out
        if r["delta_F1_species_controlled"] is not None]
unc = [abs(r["delta_F1_uncontrolled"]) for r in out if r["delta_F1_uncontrolled"] is not None]
summary = {
    "label": "EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT / species-controlled transfer",
    "what_this_removes": ("the earlier comparison used their Enterobacterales column, which spans "
                          "several genera, so cohort change and species narrowing were confounded. "
                          "Their per-contig table carries the sample identifier, so their 15 "
                          "E. coli isolates can be isolated and the comparison run E. coli vs "
                          "E. coli."),
    "their_metrics_recomputed_here": ("from their own per-contig calls using this project's metric "
                                      "code and aggregation, so no difference can arise from how "
                                      "the metric was computed"),
    "cohorts": {"their E. coli": res["their E. coli"]["_n"], "our E. coli (P1.11)": ourres["_n"],
                "their Enterobacterales (all)": res["their Enterobacterales (all)"]["_n"],
                "their Enterococcus": res["their Enterococcus"]["_n"]},
    "species_controlled": {
        "spearman_rank_correlation_F1": spear([r["their_Ecoli_F1"] for r in out],
                                              [r["our_Ecoli_F1"] for r in out]),
        "mean_abs_delta_F1_pp": round(float(np.mean(ctrl)), 2),
        "median_abs_delta_F1_pp": round(float(np.median(ctrl)), 2),
        "max_abs_delta_F1_pp": round(float(np.max(ctrl)), 2)},
    "uncontrolled_for_reference": {
        "mean_abs_delta_F1_pp": round(float(np.mean(unc)), 2),
        "max_abs_delta_F1_pp": round(float(np.max(unc)), 2)},
    "per_tool": out,
    "table": "differentiation/P1.11_species_controlled_transfer.tsv"}
io.open(D + "/P1.11_SPECIES_CONTROLLED_TRANSFER.json", "w", encoding="utf-8",
        newline="\n").write(json.dumps(summary, indent=1, default=str) + "\n")

print("  cohorts: theirs E. coli %s | ours %s" % (res["their E. coli"]["_n"], ourres["_n"]))
print("\n  %-14s %8s %8s %8s   %8s %8s   (pp)" %
      ("tool", "their", "ours", "dF1", "dPrec", "dRec"))
for r in out:
    print("  %-14s %8s %8s %+8.1f   %+8.1f %+8.1f"
          % (r["tool"], r["their_Ecoli_F1"], r["our_Ecoli_F1"], r["delta_F1_species_controlled"],
             r["delta_prec_species_controlled"], r["delta_rec_species_controlled"]))
s = summary["species_controlled"]
print("\n  SPECIES-CONTROLLED : rho=%s  mean|dF1|=%s pp  max=%s pp"
      % (s["spearman_rank_correlation_F1"], s["mean_abs_delta_F1_pp"], s["max_abs_delta_F1_pp"]))
print("  uncontrolled       : mean|dF1|=%s pp  max=%s pp"
      % (summary["uncontrolled_for_reference"]["mean_abs_delta_F1_pp"],
         summary["uncontrolled_for_reference"]["max_abs_delta_F1_pp"]))
print("\n  their E. coli vs their Enterobacterales-excl-E.coli (within their own cohort):")
for t in TOOLS[:6]:
    a = res["their E. coli"][t]["F1"]; b = res["their Enterobacterales excl. E. coli"][t]["F1"]
    if a and b:
        print("    %-14s E.coli %5.1f   other Entero %5.1f   diff %+5.1f" % (t, a[0], b[0], a[0]-b[0]))

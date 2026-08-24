#!/usr/bin/env python3
"""P1.11 SEPARATE exploratory set -- kept apart from the accepted post-truth analyses so it can be
dropped wholesale without touching anything else.

Output goes ONLY to p112/POSTTRUTH/exploratory_v2/. Nothing here is merged into
P1.11_POSTTRUTH_FINDINGS.md, the manuscript tables, or the positioning receipt.

  A. copy-number proxy  -- performance vs assembly coverage, and coverage ratio to the isolate's
                           own chromosomal baseline (a standard plasmid-copy-number estimator)
  B. large replicons    -- do errors concentrate on large plasmid replicons?
  C. replicon recovery  -- recovery per PLASMID REPLICON rather than per contig

Results are reported as measured, favourable or not.
"""
import collections, csv, glob, io, json, math, os, sys
import numpy as np

P = "/work/p112"
OUT = P + "/POSTTRUTH/exploratory_v2"
LABEL = "EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT / SEPARATE CANDIDATE SET"
N_BOOT, SEED = 4000, 20260821
CONF = {"n": 7244, "TP": 942, "FP": 33, "TN": 6002, "FN": 267}
os.makedirs(OUT, exist_ok=True)


def rd(p):
    return csv.DictReader(io.open(p, encoding="utf-8", errors="replace"), delimiter="\t")


def fnum(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def mets(y, c):
    y = np.asarray(y); c = np.asarray(c)
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    tn = int(((c == 0) & (y == 0)).sum()); fn = int(((c == 0) & (y == 1)).sum())
    ppv = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * ppv * rec / (ppv + rec) if (ppv and rec and ppv + rec > 0) else None
    return {"n": int(len(y)), "n_truth_positive": int((y == 1).sum()), "TP": tp, "FP": fp,
            "TN": tn, "FN": fn, "selective_PPV": ppv, "selective_recall": rec, "selective_F1": f1}


def boot(y, g, c):
    y = np.asarray(y); g = np.asarray(g); c = np.asarray(c); iso = sorted(set(g.tolist()))
    if len(iso) < 2:
        return {"note": "fewer than 2 isolates"}
    idx = {i: np.where(g == i)[0] for i in iso}
    rng = np.random.default_rng(SEED); Pp = []; Rr = []
    for _ in range(N_BOOT):
        r = np.concatenate([idx[i] for i in rng.choice(iso, size=len(iso), replace=True)])
        m = mets(y[r], c[r])
        if m["selective_PPV"] is not None: Pp.append(m["selective_PPV"])
        if m["selective_recall"] is not None: Rr.append(m["selective_recall"])
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4),
                   round(float(np.percentile(v, 97.5)), 4)] if v else None
    return {"PPV_ci95": q(Pp), "recall_ci95": q(Rr), "n_boot": N_BOOT, "seed": SEED}


def stable(m):
    ev = m["TP"] + m["FP"] + m["TN"] + m["FN"]
    return ev >= 20 and 0 < m["n_truth_positive"] < ev


# ---------------------------------------------------------------- load
predk = {(r["sample"], r["contig_id"]): r for r in
         rd(P + "/inference/frozen/P1.11_FROZEN_PREDICTIONS.tsv")}
truth = {}
for f in sorted(glob.glob(P + "/truth/*/truth_table.tsv")):
    for r in rd(f):
        truth[(r["sample"], r["contig_id"])] = r
keys = sorted(k for k, r in predk.items()
              if r["is_eligible_ge_1kb"] == "1"
              and truth.get(k, {}).get("final_truth_label") in ("plasmid", "chromosome"))
y = np.array([1 if truth[k]["final_truth_label"] == "plasmid" else 0 for k in keys])
g = np.array([k[0] for k in keys])
L = np.array([int(predk[k]["contig_length"]) for k in keys])
cov = np.array([fnum(truth[k].get("coverage")) if fnum(truth[k].get("coverage")) is not None
                else np.nan for k in keys])
c12 = np.array([1 if predk[k]["v12_call"] == "plasmid_selected"
                else (0 if predk[k]["v12_score_state"] == "available" else -1) for k in keys])
crt = np.array([1 if predk[k]["router_call"] != "not_selected" else 0 for k in keys])
m0 = mets(y, c12)
got = {"n": len(keys), "TP": m0["TP"], "FP": m0["FP"], "TN": m0["TN"], "FN": m0["FN"]}
if got != CONF:
    sys.exit("REFUSING: confirmatory not reproduced: %s" % got)
print("  GATE PASS %s" % got)

R = {"label": LABEL, "status": "SEPARATE CANDIDATE SET -- not merged into the accepted analyses",
     "note": ("Produced after the accepted post-truth set was frozen and committed. Kept in its own "
              "directory so it can be dropped in full without disturbing anything else. Results are "
              "reported as measured, whether or not they favour the model."),
     "confirmatory_reproduced": got}

# ================================================================ A. copy-number proxy
ok = np.isfinite(cov)
print("  contigs with a coverage value: %d/%d" % (int(ok.sum()), len(keys)))
# per-isolate chromosomal baseline: median coverage of that isolate's >=10kb chromosome contigs
base = {}
for s in sorted(set(g.tolist())):
    m = (g == s) & (y == 0) & (L >= 10000) & ok
    if m.sum() >= 3:
        base[s] = float(np.median(cov[m]))
ratio = np.array([(cov[i] / base[g[i]]) if (ok[i] and g[i] in base and base[g[i]] > 0) else np.nan
                  for i in range(len(keys))])
rok = np.isfinite(ratio)
A = {"definition": {
        "coverage": "assembly depth for the contig, from the frozen truth table",
        "coverage_ratio": ("contig coverage divided by the median coverage of that isolate's own "
                           ">=10 kb truth-chromosome contigs -- a standard per-isolate plasmid "
                           "copy-number proxy; it is NOT a measured copy number"),
        "isolates_with_a_usable_baseline": len(base),
        "contigs_with_a_ratio": int(rok.sum())},
     "coverage_ratio_by_truth_class": {}}
for lbl, m in (("truth_plasmid", (y == 1) & rok), ("truth_chromosome", (y == 0) & rok)):
    v = ratio[m]
    A["coverage_ratio_by_truth_class"][lbl] = {
        "n": int(m.sum()), "median": round(float(np.median(v)), 3),
        "p25": round(float(np.percentile(v, 25)), 3), "p75": round(float(np.percentile(v, 75)), 3),
        "min": round(float(v.min()), 3), "max": round(float(v.max()), 3)}
# performance across copy-number-proxy bands, among truth positives especially
BANDS = [("<0.5x (sub-chromosomal)", -1e9, 0.5), ("0.5-<1.5x (~single copy)", 0.5, 1.5),
         ("1.5-<4x", 1.5, 4.0), ("4-<15x", 4.0, 15.0), (">=15x (high copy)", 15.0, 1e9)]
A["performance_by_copy_number_proxy"] = {}
for nm, lo, hi in BANDS:
    m = rok & (ratio >= lo) & (ratio < hi)
    mm = mets(y[m], c12[m])
    d = {"n_contigs": int(m.sum()), "n_isolates": len(set(g[m].tolist()))}
    d.update(mm)
    if stable(mm):
        d["bootstrap"] = boot(y[m], g[m], c12[m])
    else:
        d["estimate_suppressed"] = True
        d["reason"] = "fewer than 20 evaluable contigs, or a truth class absent"
    A["performance_by_copy_number_proxy"][nm] = d
# the direct question: are FNs low-copy?
fn_m = rok & (y == 1) & (c12 == 0)
tp_m = rok & (y == 1) & (c12 == 1)
A["false_negatives_versus_true_positives_among_truth_plasmids"] = {
    "FN_n": int(fn_m.sum()), "TP_n": int(tp_m.sum()),
    "FN_coverage_ratio_median": round(float(np.median(ratio[fn_m])), 3) if fn_m.sum() else None,
    "TP_coverage_ratio_median": round(float(np.median(ratio[tp_m])), 3) if tp_m.sum() else None,
    "FN_coverage_ratio_IQR": [round(float(np.percentile(ratio[fn_m], 25)), 3),
                              round(float(np.percentile(ratio[fn_m], 75)), 3)] if fn_m.sum() else None,
    "TP_coverage_ratio_IQR": [round(float(np.percentile(ratio[tp_m], 25)), 3),
                              round(float(np.percentile(ratio[tp_m], 75)), 3)] if tp_m.sum() else None}
if fn_m.sum() > 5 and tp_m.sum() > 5:
    a = ratio[fn_m]; b = ratio[tp_m]
    # rank-sum effect size (probability a random FN has lower ratio than a random TP)
    allv = np.concatenate([a, b]); order = np.argsort(allv, kind="mergesort")
    rk = np.empty(len(allv)); rk[order] = np.arange(1, len(allv) + 1)
    ra = rk[:len(a)].sum()
    auc_ = (ra - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))
    A["false_negatives_versus_true_positives_among_truth_plasmids"]["P_FN_ratio_lower_than_TP"] = \
        round(1 - float(auc_), 4)
    A["false_negatives_versus_true_positives_among_truth_plasmids"]["interpretation"] = (
        "probability that a randomly chosen missed plasmid contig has a LOWER copy-number proxy "
        "than a randomly chosen recovered one. 0.5 means no relationship. Descriptive; no "
        "hypothesis test was prespecified.")
R["A_copy_number_proxy"] = A

# ================================================================ B. large replicons
rep = collections.defaultdict(lambda: {"contigs": [], "bp": 0})
for i, k in enumerate(keys):
    if y[i] != 1:
        continue
    h = (truth[k].get("best_plasmid_hit") or "").strip()
    if not h:
        continue
    rep[h]["contigs"].append(i); rep[h]["bp"] += int(L[i])
sizes = sorted((v["bp"] for v in rep.values()))
B = {"definition": ("plasmid replicons are grouped by best_plasmid_hit in the frozen truth table; "
                    "replicon size is approximated by the total assembled bp assigned to it, which "
                    "is a LOWER BOUND on the true replicon length"),
     "n_replicons": len(rep),
     "assembled_bp_per_replicon": {
         "median": int(np.median(sizes)) if sizes else None,
         "p25": int(np.percentile(sizes, 25)) if sizes else None,
         "p75": int(np.percentile(sizes, 75)) if sizes else None,
         "max": int(max(sizes)) if sizes else None},
     "performance_by_replicon_size": {}}
RB = [("<10 kb", 0, 10000), ("10-<50 kb", 10000, 50000), ("50-<100 kb", 50000, 100000),
      ("100-<200 kb", 100000, 200000), (">=200 kb", 200000, 10**12)]
for nm, lo, hi in RB:
    idxs = [i for h, v in rep.items() if lo <= v["bp"] < hi for i in v["contigs"]]
    if not idxs:
        B["performance_by_replicon_size"][nm] = {"n_contigs": 0, "n_replicons": 0}
        continue
    m = np.zeros(len(keys), bool); m[idxs] = True
    tp = int((c12[m] == 1).sum()); fn = int((c12[m] == 0).sum())
    B["performance_by_replicon_size"][nm] = {
        "n_replicons": sum(1 for v in rep.values() if lo <= v["bp"] < hi),
        "n_contigs": int(m.sum()), "recovered_TP": tp, "missed_FN": fn,
        "contig_level_recall": round(tp / (tp + fn), 4) if tp + fn else None}
R["B_large_replicons"] = B

# ================================================================ C. per-replicon recovery
rows = []
for h, v in sorted(rep.items(), key=lambda x: -x[1]["bp"]):
    idxs = v["contigs"]
    n = len(idxs)
    rec_c = sum(1 for i in idxs if c12[i] == 1)
    rec_bp = sum(int(L[i]) for i in idxs if c12[i] == 1)
    rt_c = sum(1 for i in idxs if crt[i] == 1)
    iso = sorted({keys[i][0] for i in idxs})
    rows.append({"replicon": h, "isolates": ";".join(iso), "n_isolates": len(iso),
                 "n_contigs": n, "assembled_bp": v["bp"],
                 "contigs_recovered_v12": rec_c, "bp_recovered_v12": rec_bp,
                 "contig_recovery_fraction": round(rec_c / n, 4),
                 "bp_recovery_fraction": round(rec_bp / v["bp"], 4) if v["bp"] else None,
                 "contigs_recovered_router": rt_c,
                 "state": ("complete" if rec_c == n else ("partial" if rec_c else "missed"))})
with io.open(OUT + "/P1.11_replicon_recovery.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(rows)
st = collections.Counter(r["state"] for r in rows)
det = [r for r in rows if r["bp_recovery_fraction"] is not None and r["bp_recovery_fraction"] >= 0.5]
C = {"unit": "plasmid replicon, not contig",
     "n_replicons": len(rows),
     "replicon_states": dict(st),
     "fully_recovered_fraction": round(st.get("complete", 0) / len(rows), 4) if rows else None,
     "at_least_one_contig_recovered": round(
         (st.get("complete", 0) + st.get("partial", 0)) / len(rows), 4) if rows else None,
     "replicons_with_at_least_half_their_bp_recovered": len(det),
     "fraction_with_at_least_half_bp": round(len(det) / len(rows), 4) if rows else None,
     "median_bp_recovery_fraction": round(float(np.median(
         [r["bp_recovery_fraction"] for r in rows if r["bp_recovery_fraction"] is not None])), 4),
     "interpretation": ("A replicon counts as detected in practice if ANY of its contigs is "
                        "flagged, because that is what triggers follow-up in surveillance. "
                        "Complete per-contig recovery is a much stricter bar and is reported "
                        "separately."),
     "table": "exploratory_v2/P1.11_replicon_recovery.tsv"}
# single-contig vs multi-contig replicons
sc = [r for r in rows if r["n_contigs"] == 1]
mc = [r for r in rows if r["n_contigs"] > 1]
for nm, sub in (("single_contig_replicons", sc), ("multi_contig_replicons", mc)):
    if sub:
        C[nm] = {"n": len(sub),
                 "fully_recovered": sum(1 for r in sub if r["state"] == "complete"),
                 "any_contig_recovered": sum(1 for r in sub if r["state"] != "missed"),
                 "missed_entirely": sum(1 for r in sub if r["state"] == "missed")}
R["C_replicon_level_recovery"] = C

with io.open(OUT + "/P1.11_EXPLORATORY_V2.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(R, f, indent=1, default=str); f.write("\n")

print("\n== A. copy-number proxy ==")
print("  ratio median  plasmid %s  chromosome %s"
      % (A["coverage_ratio_by_truth_class"]["truth_plasmid"]["median"],
         A["coverage_ratio_by_truth_class"]["truth_chromosome"]["median"]))
fv = A["false_negatives_versus_true_positives_among_truth_plasmids"]
print("  missed plasmid contigs  median ratio %s (IQR %s)" % (fv["FN_coverage_ratio_median"], fv["FN_coverage_ratio_IQR"]))
print("  recovered               median ratio %s (IQR %s)" % (fv["TP_coverage_ratio_median"], fv["TP_coverage_ratio_IQR"]))
print("  P(missed has lower copy proxy than recovered) = %s" % fv.get("P_FN_ratio_lower_than_TP"))
for nm, d in A["performance_by_copy_number_proxy"].items():
    print("    %-26s n=%-5s pos=%-4s recall=%s" % (nm, d["n_contigs"], d["n_truth_positive"],
                                                   d.get("selective_recall")))
print("\n== B. replicon size ==")
for nm, d in B["performance_by_replicon_size"].items():
    print("    %-13s replicons=%-4s contigs=%-5s recall=%s"
          % (nm, d.get("n_replicons"), d.get("n_contigs"), d.get("contig_level_recall")))
print("\n== C. replicon-level recovery ==")
print("  replicons %d | states %s" % (C["n_replicons"], C["replicon_states"]))
print("  any contig recovered: %s | fully: %s | >=50%% bp: %s"
      % (C["at_least_one_contig_recovered"], C["fully_recovered_fraction"],
         C["fraction_with_at_least_half_bp"]))
for nm in ("single_contig_replicons", "multi_contig_replicons"):
    if nm in C:
        print("  %-26s %s" % (nm, C[nm]))
print("\n  wrote %s" % OUT)

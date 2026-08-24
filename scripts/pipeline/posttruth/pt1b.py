#!/usr/bin/env python3
"""P1.11 EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT -- section 1b: quantitative leakage audit.

Section 1 established that ZERO retained isolates were excluded for near-identity, because the
sealed cohort was declustered before truth existed. That is a design fact, not a measurement. This
module measures the quantity a reviewer actually needs: how genomically far each retained isolate
is from every development / previously-consumed genome, and whether performance depends on it.

Distances are RECOVERED from the pre-truth skani screen. Nothing is recomputed or re-aligned.
"""
import collections, csv, glob, io, json, math, os, sys
import numpy as np

P = "/work/p112"; S = "/work/p111"
OUT = P + "/POSTTRUTH"; LABEL = "EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT"
N_BOOT, SEED = 4000, 20260821
CONF = {"n": 7244, "TP": 942, "FP": 33, "TN": 6002, "FN": 267}
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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
    return {"n_eligible": int(len(y)), "n_evaluable": tp + fp + tn + fn,
            "n_truth_positive": int((y == 1).sum()), "TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "selective_PPV": ppv, "selective_recall": rec, "selective_F1": f1,
            "specificity": tn / (tn + fp) if tn + fp else None}


def boot(y, g, c):
    y = np.asarray(y); g = np.asarray(g); c = np.asarray(c); iso = sorted(set(g.tolist()))
    if len(iso) < 2:
        return {"note": "fewer than 2 isolates; CI not computed"}
    idx = {i: np.where(g == i)[0] for i in iso}
    rng = np.random.default_rng(SEED); Pp = []; Rr = []
    for _ in range(N_BOOT):
        r = np.concatenate([idx[i] for i in rng.choice(iso, size=len(iso), replace=True)])
        m = mets(y[r], c[r])
        if m["selective_PPV"] is not None: Pp.append(m["selective_PPV"])
        if m["selective_recall"] is not None: Rr.append(m["selective_recall"])
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4),
                   round(float(np.percentile(v, 97.5)), 4)] if v else None
    return {"PPV_ci95": q(Pp), "recall_ci95": q(Rr), "n_boot": N_BOOT, "seed": SEED,
            "resampling_unit": "isolate"}


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
c12 = np.array([1 if predk[k]["v12_call"] == "plasmid_selected"
                else (0 if predk[k]["v12_score_state"] == "available" else -1) for k in keys])
m0 = mets(y, c12)
got = {"n": len(keys), "TP": m0["TP"], "FP": m0["FP"], "TN": m0["TN"], "FN": m0["FN"]}
if got != CONF:
    sys.exit("REFUSING: confirmatory result not reproduced: %s" % got)
print("  GATE PASS %s" % got)
cohort = sorted(set(g.tolist()))
cset = set(cohort)


def bs(path):
    return os.path.basename(path).split(".")[0]


# ---------------------------------------------------------------- recovered ANI
MINAF = 15.0
best_ext = {}   # retained isolate -> best neighbour OUTSIDE P1.11 (development / consumed)
best_int = {}   # retained isolate -> best neighbour INSIDE the retained 79
n_ext_rows = n_int_rows = 0
for path, ext in ((S + "/screen/p111_vs_consumed.tsv", True),
                  (S + "/screen/p111_vs_p111.tsv", False)):
    for r in rd(path):
        rf, qf = bs(r["Ref_file"]), bs(r["Query_file"])
        ani = fnum(r["ANI"]); afr = fnum(r["Align_fraction_ref"]); afq = fnum(r["Align_fraction_query"])
        if ani is None:
            continue
        rc = os.path.basename(os.path.dirname(r["Ref_file"]))
        qc = os.path.basename(os.path.dirname(r["Query_file"]))
        if ext:
            n_ext_rows += 1
            for me, other, oc in ((qf, rf, rc), (rf, qf, qc)):
                if me in cset and other not in cset:
                    cur = best_ext.get(me)
                    if cur is None or ani > cur["ani_percent"]:
                        best_ext[me] = {"neighbour": other, "neighbour_cohort": oc,
                                        "ani_percent": ani, "align_fraction_ref": afr,
                                        "align_fraction_query": afq}
        else:
            n_int_rows += 1
            if rf == qf or rf not in cset or qf not in cset:
                continue
            for me, other in ((qf, rf), (rf, qf)):
                cur = best_int.get(me)
                if cur is None or ani > cur["ani_percent"]:
                    best_int[me] = {"neighbour": other, "ani_percent": ani,
                                    "align_fraction_ref": afr, "align_fraction_query": afq}

per = []
for s in cohort:
    e = best_ext.get(s); i = best_int.get(s)
    per.append({"isolate": s,
                "max_ANI_to_a_development_or_consumed_genome": (e or {}).get("ani_percent"),
                "nearest_external_genome": (e or {}).get("neighbour"),
                "nearest_external_cohort": (e or {}).get("neighbour_cohort"),
                "external_align_fraction_query": (e or {}).get("align_fraction_query"),
                "external_detected_above_screen_floor": e is not None,
                "max_ANI_to_another_P1.11_isolate": (i or {}).get("ani_percent"),
                "nearest_P1.11_isolate": (i or {}).get("neighbour"),
                "internal_detected_above_screen_floor": i is not None,
                "n_eligible_contigs": int((g == s).sum()),
                "n_truth_plasmid_contigs": int(y[g == s].sum())})
with io.open(OUT + "/P1.11_leakage_distance_per_isolate.tsv", "w", encoding="utf-8",
             newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(per[0].keys()), delimiter="\t", lineterminator="\n",
                       restval="")
    w.writeheader(); w.writerows(per)

ext_vals = [p["max_ANI_to_a_development_or_consumed_genome"] for p in per
            if p["max_ANI_to_a_development_or_consumed_genome"] is not None]
int_vals = [p["max_ANI_to_another_P1.11_isolate"] for p in per
            if p["max_ANI_to_another_P1.11_isolate"] is not None]


def summ(v):
    if not v:
        return {"n": 0, "note": "no pair reported above the screen's alignment-fraction floor"}
    a = np.array(v)
    return {"n": len(v), "min": round(float(a.min()), 4), "p25": round(float(np.percentile(a, 25)), 4),
            "median": round(float(np.median(a)), 4), "p75": round(float(np.percentile(a, 75)), 4),
            "max": round(float(a.max()), 4), "mean": round(float(a.mean()), 4)}


BANDS = [("<97.0", -1.0, 97.0), ("97.0-<98.0", 97.0, 98.0), ("98.0-<99.0", 98.0, 99.0),
         ("99.0-<99.5", 99.0, 99.5), (">=99.5 (above the frozen independence threshold)", 99.5, 101.0)]
strat = {}
for nm, lo, hi in BANDS:
    iso = {p["isolate"] for p in per
           if p["max_ANI_to_a_development_or_consumed_genome"] is not None
           and lo <= p["max_ANI_to_a_development_or_consumed_genome"] < hi}
    m = np.array([k[0] in iso for k in keys])
    d = {"n_isolates": len(iso), "isolates": sorted(iso), "n_contigs": int(m.sum())}
    if m.sum():
        mm = mets(y[m], c12[m]); d.update(mm)
        if mm["n_evaluable"] >= 20 and 0 < mm["n_truth_positive"] < mm["n_evaluable"]:
            d["bootstrap"] = boot(y[m], g[m], c12[m])
        else:
            d["estimate_suppressed"] = True
            d["reason"] = "fewer than 20 evaluable contigs, or a truth class is absent"
    strat[nm] = d
nod = {p["isolate"] for p in per if p["max_ANI_to_a_development_or_consumed_genome"] is None}
m = np.array([k[0] in nod for k in keys])
d = {"n_isolates": len(nod), "isolates": sorted(nod), "n_contigs": int(m.sum()),
     "meaning": ("no external genome was reported for this isolate by the screen, i.e. no "
                 "development or consumed genome aligned to it above the screen's --min-af 15 "
                 "floor. This is a lower bound on distance, not an ANI of zero.")}
if m.sum():
    mm = mets(y[m], c12[m]); d.update(mm)
    if mm["n_evaluable"] >= 20 and 0 < mm["n_truth_positive"] < mm["n_evaluable"]:
        d["bootstrap"] = boot(y[m], g[m], c12[m])
strat["no external neighbour reported"] = d

# is performance related to distance? Spearman on per-isolate accuracy, descriptive only.
acc = []
for p in per:
    v = p["max_ANI_to_a_development_or_consumed_genome"]
    if v is None:
        continue
    m2 = (g == p["isolate"]) & (c12 >= 0)
    if m2.sum() == 0:
        continue
    acc.append((v, float((c12[m2] == y[m2]).mean()), m2.sum()))
rho = None
if len(acc) >= 3:
    a = np.array([x[0] for x in acc]); b = np.array([x[1] for x in acc])
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() > 0 and rb.std() > 0:
        rho = round(float(np.corrcoef(ra, rb)[0, 1]), 4)

R = {"label": LABEL, "section": "1b -- quantitative genomic-distance leakage audit",
     "result_id": "P1.11-CORRECTED-TRUTH-ALL79", "confirmatory_reproduced": got,
     "why_this_exists": ("Section 1 found that zero retained isolates carry a near-identical "
                         "development neighbour. That is a consequence of declustering the cohort "
                         "before truth existed, so it is a design fact rather than a measurement. "
                         "This section measures the actual genomic distance instead."),
     "provenance": {"source": "RECOVERED pre-truth skani screen; no alignment was recomputed",
                    "within_cohort_file": "p111/screen/p111_vs_p111.tsv",
                    "vs_consumed_file": "p111/screen/p111_vs_consumed.tsv",
                    "method": "skani 0.2.2, --min-af 15",
                    "pairs_read_external": n_ext_rows, "pairs_read_internal": n_int_rows,
                    "ani_scale": "percent (0-100); the frozen independence threshold 0.995 is 99.5%",
                    "reporting_floor_caveat": ("skani only reports a pair when the aligned fraction "
                                               "reaches --min-af 15. An isolate with no reported "
                                               "neighbour is therefore BELOW that floor, which is a "
                                               "lower bound on distance and not an ANI of zero.")},
     "external_distance_summary_percent_ANI": summ(ext_vals),
     "internal_distance_summary_percent_ANI": summ(int_vals),
     "n_isolates": len(cohort),
     "n_isolates_with_a_reported_external_neighbour": len(ext_vals),
     "n_isolates_with_no_reported_external_neighbour": len(cohort) - len(ext_vals),
     "n_isolates_at_or_above_the_frozen_independence_threshold_99.5":
         sum(1 for v in ext_vals if v >= 99.5),
     "n_internal_pairs_at_or_above_99.5": sum(1 for v in int_vals if v >= 99.5),
     "performance_by_distance_to_development_data": strat,
     "spearman_rho_isolate_accuracy_versus_max_external_ANI": {
         "rho": rho, "n_isolates": len(acc),
         "interpretation": ("descriptive only. A rho near zero indicates no monotone relationship "
                            "between an isolate's genomic proximity to development data and how "
                            "accurately PlasmidCall classifies its contigs. No hypothesis test is "
                            "reported and none was prespecified.")},
     "per_isolate_table": "POSTTRUTH/P1.11_leakage_distance_per_isolate.tsv"}
with io.open(OUT + "/P1.11_POSTTRUTH_SECTION_1B_LEAKAGE.json", "w", encoding="utf-8",
             newline="\n") as f:
    json.dump(R, f, indent=1, default=str); f.write("\n")
print("  external neighbours reported for %d/%d isolates" % (len(ext_vals), len(cohort)))
print("  external ANI: %s" % summ(ext_vals))
print("  internal ANI: %s" % summ(int_vals))
print("  >=99.5 external: %d | >=99.5 internal: %d"
      % (sum(1 for v in ext_vals if v >= 99.5), sum(1 for v in int_vals if v >= 99.5)))
print("  spearman rho (accuracy vs external ANI) = %s over %d isolates" % (rho, len(acc)))
for k2, v2 in strat.items():
    print("    %-52s iso=%-3s contigs=%-5s PPV=%s recall=%s"
          % (k2, v2.get("n_isolates"), v2.get("n_contigs"),
             v2.get("selective_PPV"), v2.get("selective_recall")))

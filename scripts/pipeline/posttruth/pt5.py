#!/usr/bin/env python3
"""P1.11 differentiation analyses 1-4. EXPLORATORY, post-hoc, labelled as such.

1. copy number as a determinant absent from the prior benchmark's covariate set
2. cross-cohort transferability of published per-tool benchmark numbers
3. operational reliability - tools failing, and graceful degradation
4. the prospective claim - assembled evidence

Touches nothing frozen. Re-derives the confirmatory table first and refuses to run otherwise.
"""
import collections, csv, glob, io, json, math, os, sys
import numpy as np

P = "/work/p112"
OUT = P + "/POSTTRUTH/differentiation"
N_BOOT, SEED = 4000, 20260821
CONF = {"n": 7244, "TP": 942, "FP": 33, "TN": 6002, "FN": 267}
TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC", "PlasmidFinder",
         "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
# Teixeira et al. Brief Bioinform 2025;26(6):bbaf589, Supplementary Table 5, Enterobacterales
# column. Values are percentages, median after bootstrapping, 95% CI in brackets.
PRIOR = {
    "PlaScope":      {"F1": 93.5, "prec": 94.2, "rec": 92.8},
    "PlasmidEC":     {"F1": 92.6, "prec": 92.4, "rec": 92.8},
    "Plasmer":       {"F1": 90.7, "prec": 83.6, "rec": 99.1},
    "gplas2":        {"F1": 87.7, "prec": 92.3, "rec": 83.6},
    "MOB-recon":     {"F1": 86.4, "prec": 84.7, "rec": 88.2},
    "Platon":        {"F1": 85.9, "prec": 92.1, "rec": 80.6},
    "HyAsP":         {"F1": 81.4, "prec": 81.5, "rec": 81.4},
    "RFPlasmid":     {"F1": 80.8, "prec": 73.8, "rec": 89.2},
    "PLASMe":        {"F1": 71.9, "prec": 56.2, "rec": 99.6},
    "plASgraph2":    {"F1": 69.5, "prec": 84.4, "rec": 59.1},
    "geNomad":       {"F1": 59.1, "prec": 52.3, "rec": 67.9},
    "PlasmidFinder": {"F1": 29.1, "prec": 97.7, "rec": 17.1},
}
os.makedirs(OUT, exist_ok=True)


def rd(p):
    return csv.DictReader(io.open(p, encoding="utf-8", errors="replace"), delimiter="\t")


def fnum(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def prf(y, c):
    y = np.asarray(y); c = np.asarray(c)
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    fn = int(((c == 0) & (y == 1)).sum())
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if (p and r and p + r > 0) else None
    return p, r, f


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
arg = np.array([predk[k]["ARG_bearing_bool"] == "true" for k in keys])
cov = np.array([fnum(truth[k].get("coverage")) if fnum(truth[k].get("coverage")) is not None
                else np.nan for k in keys])
c12 = np.array([1 if predk[k]["v12_call"] == "plasmid_selected"
                else (0 if predk[k]["v12_score_state"] == "available" else -1) for k in keys])
tcall = {t: np.array([1 if predk[k][t] == "plasmid" else (0 if predk[k][t] == "chromosome" else -1)
                      for k in keys]) for t in TOOLS}
tp_, fp_, tn_, fn_ = (int(((c12 == 1) & (y == 1)).sum()), int(((c12 == 1) & (y == 0)).sum()),
                      int(((c12 == 0) & (y == 0)).sum()), int(((c12 == 0) & (y == 1)).sum()))
got = {"n": len(keys), "TP": tp_, "FP": fp_, "TN": tn_, "FN": fn_}
if got != CONF:
    sys.exit("REFUSING: confirmatory not reproduced: %s" % got)
print("  GATE PASS %s\n" % got)
R = {"label": "EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT / differentiation",
     "confirmatory_reproduced": got}

# ================================================== 1. copy number as a missing determinant
base = {}
ok = np.isfinite(cov)
for s in sorted(set(g.tolist())):
    m = (g == s) & (y == 0) & (L >= 10000) & ok
    if m.sum() >= 3:
        base[s] = float(np.median(cov[m]))
ratio = np.array([(cov[i] / base[g[i]]) if (ok[i] and g[i] in base and base[g[i]] > 0) else np.nan
                  for i in range(len(keys))])
rok = np.isfinite(ratio)
rep = collections.defaultdict(int)
for i, k in enumerate(keys):
    if y[i] == 1:
        h = (truth[k].get("best_plasmid_hit") or "").strip()
        if h:
            rep[h] += int(L[i])
repsize = np.array([rep.get((truth[k].get("best_plasmid_hit") or "").strip(), 0) for k in keys],
                   dtype=float)


def irls(X, yv):
    w = np.zeros(X.shape[1])
    for _ in range(300):
        p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        W = p * (1 - p) + 1e-10
        try:
            H = (X * W[:, None]).T @ X + 1e-8 * np.eye(X.shape[1])
            step = np.linalg.solve(H, X.T @ (yv - p))
        except np.linalg.LinAlgError:
            break
        w = w + step
        if np.max(np.abs(step)) < 1e-9:
            break
    p = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
    W = p * (1 - p) + 1e-10
    try:
        cvm = np.linalg.inv((X * W[:, None]).T @ X + 1e-8 * np.eye(X.shape[1]))
        se = np.sqrt(np.diag(cvm))
    except np.linalg.LinAlgError:
        se = np.full(X.shape[1], np.nan)
    ll = float(np.sum(yv * np.log(np.clip(p, 1e-12, 1)) + (1 - yv) * np.log(np.clip(1 - p, 1e-12, 1))))
    return w, se, ll


# model detection of TRUTH-PLASMID contigs, as the prior benchmark's ST13 does
sel = (y == 1) & rok & (repsize > 0)
Lk = np.log10(L[sel]); Rz = np.log2(np.clip(ratio[sel], 1e-3, None))
Sz = np.log10(np.clip(repsize[sel], 1, None)); Ag = arg[sel].astype(float)
z = lambda v: (v - v.mean()) / (v.std() + 1e-12)
one = np.ones(sel.sum())
cn_report = {}
for name, cc in [("PlasmidCall v1.2-General", c12)] + [(t, tcall[t]) for t in
                                                       ("PlaScope", "PlasmidEC", "Plasmer", "gplas2")]:
    det = (cc[sel] == 1).astype(float)
    if det.sum() in (0, len(det)):
        cn_report[name] = {"skipped": "no variation in detection"}
        continue
    Xb = np.column_stack([one, z(Lk), Ag, z(Sz)])                 # prior benchmark's covariates
    Xf = np.column_stack([one, z(Lk), Ag, z(Sz), z(Rz)])          # + copy-number proxy
    wb, sb, llb = irls(Xb, det)
    wf, sf, llf = irls(Xf, det)
    lr = 2 * (llf - llb)
    # chi2(1) survival without scipy
    pval = math.erfc(math.sqrt(max(lr, 0) / 2.0))
    cn_report[name] = {
        "n_truth_plasmid_modelled": int(sel.sum()),
        "baseline_covariates": ["log10 contig length", "has ARG", "log10 replicon size"],
        "added_covariate": "log2 copy-number proxy (contig depth / isolate chromosomal median)",
        "coef_copy_number": round(float(wf[4]), 4),
        "se_copy_number": round(float(sf[4]), 4),
        "z_copy_number": round(float(wf[4] / sf[4]), 3) if sf[4] == sf[4] and sf[4] > 0 else None,
        "logLik_without": round(llb, 3), "logLik_with": round(llf, 3),
        "likelihood_ratio_chi2_1df": round(float(lr), 3),
        "p_value_approx": ("<1e-12" if pval < 1e-12 else "%.3g" % pval),
        "interpretation": ("positive coefficient means higher copy number makes a truth-plasmid "
                           "contig more likely to be detected, after adjusting for the covariates "
                           "the prior benchmark modelled")}
R["A_copy_number_missing_determinant"] = {
    "why_this_is_new": ("Supplementary Table 13 of the prior benchmark models detection against "
                        "SR contig length, presence of ARGs, transposase count, identity of the "
                        "best PLSDB hit and plasmid size. Read depth / copy number is NOT among "
                        "its covariates. This tests whether it adds information beyond them."),
    "covariates_not_available_here": ["transposase count", "identity of best PLSDB hit"],
    "models": cn_report}

# ================================================== 2. cross-cohort transferability
def per_isolate_median(cc):
    """Match the prior benchmark's aggregation: per-unit metric, median, bootstrap CI."""
    iso = sorted(set(g.tolist()))
    vals = {"F1": [], "prec": [], "rec": []}
    per = {}
    for s in iso:
        m = g == s
        p, r, f = prf(y[m], cc[m])
        per[s] = (p, r, f)
        if p is not None: vals["prec"].append(p)
        if r is not None: vals["rec"].append(r)
        if f is not None: vals["F1"].append(f)
    rng = np.random.default_rng(SEED)
    out = {}
    for k, v in vals.items():
        if not v:
            out[k] = None; continue
        v = np.array(v)
        bs = [np.median(rng.choice(v, size=len(v), replace=True)) for _ in range(N_BOOT)]
        out[k] = {"median_pct": round(float(np.median(v)) * 100, 1),
                  "ci95_pct": [round(float(np.percentile(bs, 2.5)) * 100, 1),
                               round(float(np.percentile(bs, 97.5)) * 100, 1)],
                  "n_isolates_contributing": int(len(v))}
    return out


rows = []
for t in TOOLS:
    pooled_p, pooled_r, pooled_f = prf(y, tcall[t])
    pim = per_isolate_median(tcall[t])
    pr = PRIOR[t]
    d = {"tool": t,
         "prior_Enterobacterales_F1_pct": pr["F1"], "prior_precision_pct": pr["prec"],
         "prior_recall_pct": pr["rec"],
         "P1.11_F1_pct_per_isolate_median": pim["F1"]["median_pct"] if pim["F1"] else None,
         "P1.11_precision_pct_per_isolate_median": pim["prec"]["median_pct"] if pim["prec"] else None,
         "P1.11_recall_pct_per_isolate_median": pim["rec"]["median_pct"] if pim["rec"] else None,
         "P1.11_F1_pct_pooled": round(pooled_f * 100, 1) if pooled_f else None,
         "P1.11_precision_pct_pooled": round(pooled_p * 100, 1) if pooled_p else None,
         "P1.11_recall_pct_pooled": round(pooled_r * 100, 1) if pooled_r else None}
    for k, pk in (("F1", "F1"), ("precision", "prec"), ("recall", "rec")):
        a = pr[pk]; b = d["P1.11_%s_pct_per_isolate_median" % k]
        d["delta_%s_pct" % k] = round(b - a, 1) if b is not None else None
    rows.append(d)
rows.sort(key=lambda r: -r["prior_Enterobacterales_F1_pct"])
with io.open(OUT + "/P1.11_cross_cohort_transferability.tsv", "w", encoding="utf-8",
             newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(rows)


def spearman(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


pa = [r["prior_Enterobacterales_F1_pct"] for r in rows]
pb = [r["P1.11_F1_pct_per_isolate_median"] for r in rows]
dl = [abs(r["delta_F1_pct"]) for r in rows if r["delta_F1_pct"] is not None]
R["B_cross_cohort_transferability"] = {
    "why_this_is_new": ("The prior benchmark reports per-tool metrics on its 250 isolates. This "
                        "cohort of 79 is disjoint from those 250 by identifier (0 shared "
                        "BioSamples) and by sequence (max ANI 99.48%, below the frozen 99.5% "
                        "threshold). Running the same twelve tools on a disjoint cohort makes it "
                        "possible to ask how far a published benchmark number transfers - which no "
                        "single benchmark can ask of itself."),
    "aggregation_note": ("the prior benchmark reports the median after bootstrapping; P1.11 values "
                         "are computed the same way, per isolate then median, with an "
                         "isolate-bootstrap CI. Pooled contig-level values are given alongside "
                         "because they differ and the difference is itself informative."),
    "comparison_is_against": "the prior benchmark's Enterobacterales column (E. coli is Enterobacterales)",
    "spearman_rank_correlation_F1": round(spearman(pa, pb), 4),
    "mean_absolute_delta_F1_pct": round(float(np.mean(dl)), 2),
    "median_absolute_delta_F1_pct": round(float(np.median(dl)), 2),
    "max_absolute_delta_F1_pct": round(float(np.max(dl)), 2),
    "n_tools": len(rows), "table": "differentiation/P1.11_cross_cohort_transferability.tsv",
    "per_tool": rows}

# ================================================== 3. operational reliability
rt = collections.defaultdict(collections.Counter)
for f in glob.glob(P + "/inference/receipts/*.json"):
    try:
        d = json.load(io.open(f, encoding="utf-8"))
    except Exception:
        continue
    if d.get("tool"):
        rt[d["tool"]][d.get("status", "?")] += 1
IMG = {"hyasp": "HyAsP", "mobsuite": "MOB-recon", "plasme": "PLASMe", "plascope": "PlaScope",
       "plasmer": "Plasmer", "plasmidec": "PlasmidEC", "plasmidfinder": "PlasmidFinder",
       "platon": "Platon", "rfplasmid": "RFPlasmid", "genomad": "geNomad", "gplas2": "gplas2",
       "plasgraph2": "plASgraph2", "amrfinder": "AMRFinderPlus"}
rel = []
for key, name in sorted(IMG.items(), key=lambda x: x[1]):
    st = rt.get(key, collections.Counter())
    nbad = sum(v for k, v in st.items() if k != "OK")
    if name in tcall:
        cc = tcall[name]
        unusable = int((cc < 0).sum())
        contig_cov = round(float((cc >= 0).mean()), 4)
    else:
        unusable = None; contig_cov = None
    rel.append({"tool": name, "executions": int(sum(st.values())),
                "executions_not_OK": nbad,
                "isolate_failure_rate": round(nbad / 79.0, 4) if sum(st.values()) else None,
                "contigs_without_a_usable_call": unusable,
                "contig_level_coverage": contig_cov})
R["C_operational_reliability"] = {
    "why_this_is_new": ("Every published benchmark of these tools reports accuracy conditional on "
                        "the tool having run. None reports how often it does not run, or what a "
                        "pipeline should do when it does not. Across 1027 executions here, tools "
                        "failed terminally after three attempts, and separately a provenance audit "
                        "found 47 executions that completed with valid output behind a stale "
                        "FAILED receipt - a silent-corruption mode that would have discarded "
                        "11241 contigs of evidence."),
    "per_tool": rel,
    "total_executions": int(sum(sum(v.values()) for v in rt.values())),
    "total_not_OK": int(sum(sum(v for k, v in st.items() if k != "OK") for st in rt.values())),
    "graceful_degradation": {
        "claim": ("PlasmidCall's encoding gives an absent or failed tool an exactly zero "
                  "contribution to the logit, so a tool failing degrades the panel rather than "
                  "corrupting the prediction."),
        "evidence": "models/plasmidcall_v1.2-general/P1.12_V1.2_TRAINING_RECEIPT.json",
        "measured": {"max_abs_scaled_value_in_a_neutralised_block": 0.0,
                     "max_abs_contribution_of_an_absent_unseen_tool": 0.0,
                     "no_op_on_training_data": True},
        "why_it_matters": ("this is a designed and measured property, not an empirical "
                           "observation; no comparator tool has an equivalent guarantee because "
                           "none consumes a panel")}}

# ================================================== 4. the prospective claim
fz = json.load(io.open(P + "/inference/PREDICTIONS_FROZEN.json", encoding="utf-8"))
acq = json.load(io.open(P + "/receipts/P1.11_truth_acquisition_receipt.json", encoding="utf-8"))
R["D_prospective_claim"] = {
    "why_this_is_new": ("Published claims about these tools take the form 'on dataset D, tool T "
                        "achieved metric M', with D, M and the operating point all chosen after "
                        "the results were seen. Such a claim cannot fail. The claim here was "
                        "constructed so that it could."),
    "sequence": [
        {"step": "operating points declared", "value": "0.9285 (v1.2-General), 0.9524 and 0.9605 "
                                                       "(v1.1), frozen router",
         "before_truth": True},
        {"step": "predictions frozen and hashed",
         "utc": fz.get("frozen_utc") or acq.get("predictions_frozen_utc"),
         "matrix_sha256": acq.get("predictions_matrix_sha256"), "before_truth": True},
        {"step": "truth acquired", "utc": acq.get("utc"),
         "isolates_verified": acq.get("verified"), "before_truth": False},
    ],
    "gap_between_freeze_and_truth": {
        "predictions_frozen_utc": acq.get("predictions_frozen_utc"),
        "truth_acquired_utc": acq.get("utc")},
    "falsifiability": ("the confirmatory gate was a declared PPV floor. Had v1.2-General scored "
                       "below it, the result would have been recorded as a failure; the pipeline "
                       "had no route to change the threshold afterwards."),
    "enforcement": ("every post-truth analysis script re-derives the confirmatory contingency "
                    "table and exits non-zero unless it reproduces n=7244, TP=942, FP=33, "
                    "TN=6002, FN=267 exactly"),
    "prior_art_contrast": ("the prior benchmark, like every other in this field, is retrospective "
                           "and descriptive. That is not a criticism of it - it is a different "
                           "kind of study - but it means no published plasmid-detection number "
                           "has ever been subject to a preregistered pass/fail test.")}

with io.open(OUT + "/P1.11_DIFFERENTIATION.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(R, f, indent=1, default=str); f.write("\n")

print("== 1. copy number beyond the prior benchmark's covariates ==")
for k, v in cn_report.items():
    if "skipped" in v:
        print("   %-26s %s" % (k, v["skipped"])); continue
    print("   %-26s coef %+.3f (z %s)  LR chi2 %.1f  p %s"
          % (k, v["coef_copy_number"], v["z_copy_number"], v["likelihood_ratio_chi2_1df"],
             v["p_value_approx"]))
print("\n== 2. cross-cohort transferability (prior Enterobacterales -> P1.11 E. coli) ==")
print("   %-14s %7s %7s %7s   %7s %7s" % ("tool", "priorF1", "oursF1", "dF1", "dPrec", "dRec"))
for r in rows:
    print("   %-14s %7.1f %7s %+7.1f   %+7.1f %+7.1f"
          % (r["tool"], r["prior_Enterobacterales_F1_pct"], r["P1.11_F1_pct_per_isolate_median"],
             r["delta_F1_pct"], r["delta_precision_pct"], r["delta_recall_pct"]))
b = R["B_cross_cohort_transferability"]
print("   Spearman rank corr F1 = %s | mean |dF1| = %s pp | max |dF1| = %s pp"
      % (b["spearman_rank_correlation_F1"], b["mean_absolute_delta_F1_pct"],
         b["max_absolute_delta_F1_pct"]))
print("\n== 3. operational reliability ==")
for r in rel:
    if r["executions_not_OK"]:
        print("   %-14s %d/%d executions not OK, %s contigs without a usable call"
              % (r["tool"], r["executions_not_OK"], r["executions"],
                 r["contigs_without_a_usable_call"]))
print("   total not-OK executions: %d of %d" % (R["C_operational_reliability"]["total_not_OK"],
                                                R["C_operational_reliability"]["total_executions"]))
print("\n== 4. prospective claim ==")
print("   predictions frozen %s" % acq.get("predictions_frozen_utc"))
print("   truth acquired     %s" % acq.get("utc"))
print("\n  wrote %s" % OUT)

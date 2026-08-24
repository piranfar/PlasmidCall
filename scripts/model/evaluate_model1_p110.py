#!/usr/bin/env python3
"""P1.10 LOCKED EVALUATION of Model 1 on the strictly independent 39-isolate E. coli cohort.

Written and hashed BEFORE predictions are joined to truth.

Governing documents
  docs/plans/P1.10_COHORT_AND_EVALUATION_CONTRACT.yaml
  docs/plans/P1.10_COPRIMARY_POPULATIONS_AMENDMENT.yaml
  docs/plans/P1.10A_DEPLOYMENT_OPERATING_POINT_AMENDMENT.yaml
  docs/contracts/MODEL1_OUTPUT_CONTRACT_v1.0.yaml

What differs from the P1.9C4 evaluation, and why
  1. OPERATING POINTS ARE FROZEN INPUTS, NOT RE-DERIVED. P1.9C4 re-derived its threshold from an
     inner-OOF pass over the development set and evaluated at that single-fit value (0.9776), which
     is stricter than every development fold threshold - the threshold-realisation defect the audit
     found. Here the standard operating point 0.9605 (median of the five development fold
     thresholds) and the very-high-confidence point 0.9776 are read in as constants. Nothing about
     them is computed from, or tuned on, P1.10.
  2. TWO UNCONDITIONAL CO-PRIMARY POPULATIONS. CP1 (core-ARG-bearing, >=1 kb, truth-resolved) and
     CP2 (all truth-resolved >=1 kb). Both are declared primary in advance; neither may replace or
     demote the other after its composition is seen. Each gets its own MET / NOT MET verdict against
     PPV >= 0.95 AND recall > 0.50. They are never pooled.
  3. THE TWO-STAGE / REJECTOR CASCADE IS NOT EVALUATED. The contract names the model under test as
     frozen M0 and frozen M2 only. The audit established the cascade as prior art (development
     script 07_p16.py, experiment 2) that already failed both targets; re-running it here would
     recreate a known-failed lineage and invite a post-hoc winner.
  4. not_selected SEMANTICS ARE CARRIED THROUGH. M2_score < 0.9605 means "no positive plasmid
     evidence at the deployment threshold", NOT a positive chromosome call. It counts as
     not-detected for recall, and every specificity/TN figure for M2 carries that caveat.
  5. The continuous M2_score is always retained and emitted per contig.

usage: evaluate_model1_p110.py <pred_matrix.tsv> <arg_bearing.tsv> <truth_dir> <predictions.xlsx> <cohort.tsv> <outdir>
"""
import sys, os, json, math, hashlib, warnings, datetime
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

PRED, ARG, TRUTH, XL, COHORT, OUT = sys.argv[1:7]
os.makedirs(OUT, exist_ok=True)

SEED = 20260816
NBOOT = 10000
ABST = {"unknown", "unclassified", "repeat"}
TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC", "PlasmidFinder",
         "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]

# ---- frozen operating points (development-derived; NOT computed here)
THR_STANDARD = 0.9605
THR_VHC = 0.9776
FOLD_THRESHOLDS = [0.9732, 0.9605, 0.9378, 0.9718, 0.9524]
ALL_OPERATING_POINTS = sorted(set(FOLD_THRESHOLDS + [THR_VHC]))   # the six development-derived points
LEAVE_OUT_TOOLS = ["MOB-recon", "PLASMe", "geNomad"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ frozen feature construction
# verbatim from development 05_models.py / P1.9C4 as-executed; featureset F_full_no_taxon
def build_features(df, tools):
    V = df[tools].astype(str)
    Vv = V.where(~V.isin(ABST))
    df = df.copy()
    df["n_valid"] = Vv.notna().sum(axis=1)
    df["n_plasmid"] = Vv.eq("plasmid").sum(axis=1)
    df["n_chrom"] = Vv.eq("chromosome").sum(axis=1)
    df["n_abstain"] = len(tools) - df["n_valid"]
    df["frac_plasmid"] = df["n_plasmid"] / df["n_valid"].replace(0, np.nan)
    df["frac_chrom"] = df["n_chrom"] / df["n_valid"].replace(0, np.nan)
    df["agreement"] = np.maximum(df["frac_plasmid"], df["frac_chrom"])
    df["log10_len"] = np.log10(df["SR contig length"].clip(lower=1))
    df["log10_nsr"] = np.log10(df["Number of SR contigs"].clip(lower=1))
    for t in tools:
        df["abst_" + t] = V[t].isin(ABST).astype(int)
    return df


COUNT_NUM = ["n_valid", "n_plasmid", "n_chrom", "n_abstain", "frac_plasmid", "frac_chrom", "agreement"]
LEN_NUM = ["SR contig length", "log10_len"]
FRAG_NUM = ["log10_nsr"]


def make_pipe(tools):
    fs = dict(cat=tools, num=COUNT_NUM + LEN_NUM + FRAG_NUM, extra=["abst_" + t for t in tools])
    tr = [("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), fs["cat"]),
          ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
           fs["num"] + fs["extra"])]
    return Pipeline([("prep", ColumnTransformer(tr, remainder="drop")),
                     ("clf", HistGradientBoostingClassifier(max_depth=3, max_iter=200,
                                                            learning_rate=0.06, min_samples_leaf=25,
                                                            l2_regularization=1.0, random_state=SEED))])


# ------------------------------------------------------------------ development set: fit M2 ONCE
det = pd.read_excel(XL, sheet_name="Plasmid Detection", engine="openpyxl")
gt = pd.read_excel(XL, sheet_name="Ground-truth", engine="openpyxl")
asm = pd.read_excel(XL, sheet_name="Assembly Statistics", engine="openpyxl")
K = ["Sample ID", "SR contig ID"]
dev = gt.merge(det, on=K, validate="1:1").merge(asm[K + ["Number of SR contigs"]], on=K, validate="1:1")
dev = dev[dev["SR contig has ARGs"].eq(True)].copy().reset_index(drop=True)
assert len(dev) == 1460, "development ARG-bearing rows must be 1460, got %d" % len(dev)
dev = build_features(dev, TOOLS)
ydev = dev["Ground-truth class"].eq("plasmid").astype(int).values
gdev = dev["Sample ID"].values

models = {}
m2 = make_pipe(TOOLS)
m2.fit(dev, ydev)
models["full_panel"] = (m2, TOOLS)
for lo in LEAVE_OUT_TOOLS:                      # predeclared leave-one-tool-out sensitivity
    sub_tools = [t for t in TOOLS if t != lo]
    d2 = build_features(dev.drop(columns=[c for c in dev.columns if c.startswith("abst_")]), sub_tools)
    mm = make_pipe(sub_tools)
    mm.fit(d2, ydev)
    models["leave_out_" + lo] = (mm, sub_tools)

fitrec = {"dev_rows": int(len(dev)), "dev_sha256": sha(XL), "seed": SEED,
          "estimator": "HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.06, "
                       "min_samples_leaf=25, l2_regularization=1.0, random_state=20260816)",
          "featureset": "F_full_no_taxon",
          "fit_policy": "fitted ONCE on the full 1460-row development set; no P1.10 data of any kind "
                        "enters the fit, the calibration or the thresholds",
          "operating_points_are_inputs": {"standard": THR_STANDARD, "very_high_confidence": THR_VHC,
                                          "source": "P1.10A amendment; median of the five development "
                                                    "fold thresholds, and the single-fit value"},
          "threshold_derivation_performed_here": False,
          "leave_one_tool_out_models": LEAVE_OUT_TOOLS}

# ------------------------------------------------------------------ target cohort: join only here
pm = pd.read_csv(PRED, sep="\t", dtype=str)
arg = pd.read_csv(ARG, sep="\t", dtype=str)
coh = pd.read_csv(COHORT, sep="\t", dtype=str)
assert len(coh) == 39, "cohort must be 39 isolates, got %d" % len(coh)
# each retained isolate is one independent genome cluster (declustered at ANI 99.5)
CLUSTERS = {b: b for b in coh["biosample"]}

tt = []
for s in sorted(os.listdir(TRUTH)):
    f = os.path.join(TRUTH, s, "truth_table.tsv")
    if os.path.exists(f):
        tt.append(pd.read_csv(f, sep="\t", dtype=str))
truth = pd.concat(tt, ignore_index=True)

df = pm.merge(truth[["sample", "contig_id", "contig_length", "final_truth_label",
                     "best_chromosome_hit", "best_plasmid_hit", "flags"]]
              .rename(columns={"contig_length": "truth_len"}),
              on=["sample", "contig_id"], how="left", validate="1:1")
assert df["final_truth_label"].notna().all(), "identifier mismatch: contigs without truth"
assert (df["contig_length"].astype(int) == df["truth_len"].astype(int)).all(), "contig length mismatch"
df = df.merge(arg[["sample", "contig_id", "ARG_bearing", "n_qualifying_determinants",
                   "ARG_bearing_p19c4_rule"]],
              on=["sample", "contig_id"], how="left", validate="1:1")
assert df["ARG_bearing"].notna().all(), "identifier mismatch: contigs without ARG annotation"
assert set(df["sample"]) <= set(CLUSTERS), "samples outside the frozen cohort: %r" % (
    set(df["sample"]) - set(CLUSTERS))

df["SR contig length"] = df["contig_length"].astype(int)
nsr = df[df["SR contig length"] >= 1000].groupby("sample").size()
df["Number of SR contigs"] = df["sample"].map(nsr).astype(float)
df["tool_FAILED"] = df[TOOLS].eq("FAILED").any(axis=1)
df["tool_MISSING"] = df[TOOLS].eq("MISSING").any(axis=1)
df["failed_or_missing"] = df["tool_FAILED"] | df["tool_MISSING"]

X = df.copy()
for t in TOOLS:
    X[t] = X[t].replace({"FAILED": "unknown", "MISSING": "unknown"})   # scored as abstention AND flagged
X = build_features(X, TOOLS)

# ---- M0: frozen unfitted rule, three-state
m0_call = np.where((X["n_valid"] > 0) & (X["agreement"].values >= 0.90),
                   (X["n_plasmid"] >= X["n_chrom"]).astype(int).values, -1)
# ---- M2: frozen fitted model, continuous score, thresholded at the frozen operating points
p_m2 = models["full_panel"][0].predict_proba(X)[:, 1]
df["M0_call"] = m0_call
df["M2_score"] = p_m2
df["M2_call"] = (p_m2 >= THR_STANDARD).astype(int)
df["M2_call_vhc"] = (p_m2 >= THR_VHC).astype(int)
df["M2_output_class"] = np.where(p_m2 >= THR_VHC, "very_high_confidence_plasmid",
                                 np.where(p_m2 >= THR_STANDARD, "supported_plasmid", "not_selected"))
for lo in LEAVE_OUT_TOOLS:
    mm, st = models["leave_out_" + lo]
    Xl = build_features(df.copy().assign(**{t: X[t] for t in st}), st)
    df["M2_score_leave_out_" + lo] = mm.predict_proba(Xl)[:, 1]
    df["M2_call_leave_out_" + lo] = (df["M2_score_leave_out_" + lo] >= THR_STANDARD).astype(int)
for t in TOOLS:
    df["tool_%s_call" % t] = X[t].map({"plasmid": 1, "chromosome": 0}).fillna(-1).astype(int)

# ------------------------------------------------------------------ populations and buckets
df["truth_bin"] = df["final_truth_label"].map({"plasmid": 1, "chromosome": 0})
df["is_resolved"] = df["final_truth_label"].isin(["plasmid", "chromosome"]) & (df["SR contig length"] >= 1000)
df["ARG_bearing_bool"] = df["ARG_bearing"].astype(str).str.upper().isin(["TRUE", "1"])
df["genome_cluster"] = df["sample"].map(CLUSTERS)


def bucket(r):
    if r["SR contig length"] < 1000:
        return "below_1kb"
    if r["final_truth_label"] == "ambiguous":
        return "ambiguous"
    if r["final_truth_label"] == "unmapped":
        return "unmapped"
    if r["final_truth_label"] not in ("plasmid", "chromosome"):
        return "other_unresolved"
    return "resolved_core_ARG" if r["ARG_bearing_bool"] else "non_core_ARG_resolved"


df["bucket"] = df.apply(bucket, axis=1)

# THE TWO CO-PRIMARY POPULATIONS - declared in advance, neither replaces the other
POPULATIONS = {
    "CP1_core_ARG": df[df["is_resolved"] & df["ARG_bearing_bool"]],
    "CP2_all_resolved": df[df["is_resolved"]],
}


# ------------------------------------------------------------------ metrics
def metrics(y, call):
    y = np.asarray(y).astype(int)
    call = np.asarray(call).astype(int)
    tp = int(((call == 1) & (y == 1)).sum())
    fp = int(((call == 1) & (y == 0)).sum())
    tn = int(((call == 0) & (y == 0)).sum())
    fn = int(((call == 0) & (y == 1)).sum())
    un = int((call < 0).sum())
    n = len(y)
    npos = int((y == 1).sum())
    nneg = n - npos
    d = lambda a, b: (a / b) if b else None
    ppv = d(tp, tp + fp)
    rec = d(tp, npos)
    spec = d(tn, nneg) if nneg else None
    f1 = (2 * ppv * rec / (ppv + rec)) if (ppv and rec and (ppv + rec)) else \
        (0.0 if (ppv is not None and rec is not None) else None)
    ba = ((rec or 0) + (spec or 0)) / 2 if (rec is not None and spec is not None) else None
    den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = ((tp * tn - fp * fn) / den) if den else None
    return {"n": n, "n_plasmid_truth": npos, "n_chromosome_truth": nneg,
            "TP": tp, "FP": fp, "TN": tn, "FN": fn, "unresolved_abstained": un,
            "plasmid_PPV": ppv, "plasmid_recall": rec, "specificity": spec, "F1": f1,
            "balanced_accuracy": ba, "MCC": mcc,
            "prediction_coverage": d(tp + fp + tn + fn, n), "abstention_rate": d(un, n),
            "recall_among_covered": d(tp, tp + fn) if (tp + fn) else None}


def boot(sub, callcol):
    keys = ("plasmid_PPV", "plasmid_recall", "F1", "MCC", "balanced_accuracy",
            "specificity", "prediction_coverage")
    cl = sub["genome_cluster"].values
    ids = sorted(set(cl))
    rng = np.random.default_rng(SEED)
    idx = {c: np.where(cl == c)[0] for c in ids}
    out = {k: [] for k in keys}
    for _ in range(NBOOT):
        pick = rng.choice(ids, size=len(ids), replace=True)
        rows = np.concatenate([idx[c] for c in pick])
        m = metrics(sub["truth_bin"].values[rows], sub[callcol].values[rows])
        for k in keys:
            out[k].append(m[k] if m[k] is not None else np.nan)
    return {k: {"lo": float(np.nanpercentile(v, 2.5)), "hi": float(np.nanpercentile(v, 97.5)),
                "n_clusters": len(ids),
                "note": "informational; never a pass/fail gate"} for k, v in out.items()}


results = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "phase": "P1.10 strictly independent validation",
           "inputs": {"pred_matrix": {"path": PRED, "sha256": sha(PRED)},
                      "arg_bearing": {"path": ARG, "sha256": sha(ARG)},
                      "development_set": {"path": XL, "sha256": sha(XL)},
                      "cohort": {"path": COHORT, "sha256": sha(COHORT)},
                      "truth_dir": TRUTH},
           "m2_fit": fitrec,
           "operating_points": {"standard": THR_STANDARD, "very_high_confidence": THR_VHC,
                                "all_development_derived": ALL_OPERATING_POINTS},
           "not_selected_semantics": "M2_score < 0.9605 = no positive plasmid evidence at the "
                                     "deployment threshold. NOT a positive chromosome call. It counts "
                                     "as not-detected for recall; every M2 specificity/TN figure "
                                     "inherits this caveat.",
           "co_primary_rule": "CP1 and CP2 are both primary, declared before execution. Neither "
                              "replaces or demotes the other. Results are never pooled.",
           "n_contigs_total": int(len(df)),
           "buckets_all_contigs": df["bucket"].value_counts().to_dict(),
           "tool_failure_summary": {"contigs_with_any_FAILED": int(df["tool_FAILED"].sum()),
                                    "contigs_with_any_MISSING": int(df["tool_MISSING"].sum())},
           "populations": {}, "per_sample": {}, "per_genome_cluster": {},
           "per_plasmid_replicon_event": {}, "threshold_sensitivity": {},
           "leave_one_tool_out": {}, "tool_coverage": {}}

CALLS = {"M0": "M0_call", "M2_standard_0.9605": "M2_call", "M2_very_high_confidence_0.9776": "M2_call_vhc"}
for t in TOOLS:
    CALLS["tool_" + t] = "tool_%s_call" % t

for pname, sub in POPULATIONS.items():
    blk = {"definition": ("truth-resolved contigs >=1kb that are core-ARG-bearing "
                          "(type AMR, subtype AMR, scope core, class != EFFLUX)")
           if pname == "CP1_core_ARG" else "all truth-resolved contigs >=1kb",
           "role": "CO-PRIMARY",
           "n": int(len(sub)), "n_plasmid": int(sub["truth_bin"].sum()),
           "n_chromosome": int((sub["truth_bin"] == 0).sum()),
           "n_genome_clusters": int(sub["genome_cluster"].nunique()),
           "n_isolates": int(sub["sample"].nunique()),
           "contig_length_bp": {"min": int(sub["SR contig length"].min()) if len(sub) else None,
                                "median": float(sub["SR contig length"].median()) if len(sub) else None,
                                "max": int(sub["SR contig length"].max()) if len(sub) else None},
           "n_flagged_failed_or_missing": int(sub["failed_or_missing"].sum()),
           "models": {}}
    for mname, col in CALLS.items():
        m = metrics(sub["truth_bin"], sub[col])
        if mname in ("M0", "M2_standard_0.9605"):
            m["cluster_bootstrap_95"] = boot(sub, col)
            if sub["failed_or_missing"].any():
                m["sensitivity_excluding_flagged"] = metrics(
                    sub.loc[~sub["failed_or_missing"], "truth_bin"],
                    sub.loc[~sub["failed_or_missing"], col])
        blk["models"][mname] = m
    # the frozen target verdict, stated independently for this population
    for mname in ("M0", "M2_standard_0.9605"):
        m = blk["models"][mname]
        met = (m["plasmid_PPV"] is not None and m["plasmid_PPV"] >= 0.95
               and m["plasmid_recall"] is not None and m["plasmid_recall"] > 0.50)
        m["target_PPV>=0.95_AND_recall>0.50"] = "MET" if met else "NOT_MET"
    results["populations"][pname] = blk

    results["per_sample"][pname] = {s: {mn: metrics(g["truth_bin"], g[c])
                                        for mn, c in CALLS.items() if mn in ("M0", "M2_standard_0.9605")}
                                    for s, g in sub.groupby("sample")}
    results["per_genome_cluster"][pname] = {c: {mn: metrics(g["truth_bin"], g[cc])
                                                for mn, cc in CALLS.items()
                                                if mn in ("M0", "M2_standard_0.9605")}
                                            for c, g in sub.groupby("genome_cluster")}

    # plasmid-replicon-event level
    ev = {}
    for mn in ("M0", "M2_standard_0.9605"):
        c = CALLS[mn]
        e = {"plasmid_replicons_total": 0, "plasmid_replicons_with_TP": 0,
             "plasmid_replicons_fully_missed": 0, "replicons_with_FP": 0}
        s2 = sub.copy()
        s2["rep"] = np.where(s2["truth_bin"] == 1,
                             s2["best_plasmid_hit"].astype(str).str.split(":").str[0],
                             s2["best_chromosome_hit"].astype(str).str.split(":").str[0])
        s2["key"] = s2["sample"] + "|" + s2["rep"].astype(str)
        for k, g in s2.groupby("key"):
            y = g["truth_bin"].values
            cl = g[c].values
            if (y == 1).all():
                e["plasmid_replicons_total"] += 1
                if ((cl == 1) & (y == 1)).any():
                    e["plasmid_replicons_with_TP"] += 1
                else:
                    e["plasmid_replicons_fully_missed"] += 1
            if ((cl == 1) & (y == 0)).any():
                e["replicons_with_FP"] += 1
        e["replicon_level_recall"] = (e["plasmid_replicons_with_TP"] / e["plasmid_replicons_total"]
                                      if e["plasmid_replicons_total"] else None)
        ev[mn] = e
    results["per_plasmid_replicon_event"][pname] = ev

    # predeclared threshold-sensitivity curve over all six development-derived operating points
    results["threshold_sensitivity"][pname] = {
        ("%.4f" % t): metrics(sub["truth_bin"], (sub["M2_score"].values >= t).astype(int))
        for t in ALL_OPERATING_POINTS}
    # predeclared leave-one-tool-out sensitivity, at the standard operating point
    results["leave_one_tool_out"][pname] = {
        lo: metrics(sub["truth_bin"], sub["M2_call_leave_out_" + lo]) for lo in LEAVE_OUT_TOOLS}

for t in TOOLS:
    results["tool_coverage"][t] = {"all_contigs": df[t].value_counts().to_dict(),
                                   "resolved_ge1kb": df[df["is_resolved"]][t].value_counts().to_dict()}

json.dump(results, open(os.path.join(OUT, "P1.10_model1_results.json"), "w"), indent=1, default=float)
df.to_csv(os.path.join(OUT, "P1.10_model1_contig_table.tsv"), sep="\t", index=False)
rows = []
for pname in POPULATIONS:
    for s, mm in results["per_sample"][pname].items():
        for mn, m in mm.items():
            rows.append({"population": pname, "sample": s, "model": mn,
                         **{k: v for k, v in m.items() if not isinstance(v, dict)}})
pd.DataFrame(rows).to_csv(os.path.join(OUT, "P1.10_model1_per_sample.tsv"), sep="\t", index=False)

print(json.dumps({p: {"n": results["populations"][p]["n"],
                      "n_plasmid": results["populations"][p]["n_plasmid"],
                      "n_chromosome": results["populations"][p]["n_chromosome"],
                      **{mn: {k: results["populations"][p]["models"][mn][k]
                              for k in ("TP", "FP", "TN", "FN", "plasmid_PPV", "plasmid_recall",
                                        "target_PPV>=0.95_AND_recall>0.50")}
                         for mn in ("M0", "M2_standard_0.9605")}}
                  for p in POPULATIONS}, indent=1, default=float))

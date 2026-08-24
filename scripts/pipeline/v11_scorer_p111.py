#!/usr/bin/env python3
"""P2 - truth-blind PlasmidCall v1.1 scorer for P1.11.

v1.1 has no persisted estimator: scripts/p1_10/evaluate_model1_p110.py refits it on the sealed
1,460-row development bundle at evaluation time. This script reproduces that procedure EXACTLY,
persists the fitted estimator so P1.11 evaluation never silently refits it, and validates the
reconstruction against the historical P1.10 implementation before any P1.11 row is scored.

TRUTH-BLIND. It reads the development bundle and a P1.11 contig table's PREDICTION-SIDE columns
only. It never opens P1.11 truth, a reference genome, ANI output, a label, or any outcome-dependent
quantity, and a guard refuses truth-looking input paths.

Nothing is tuned or selected on P1.11. The fit uses the development bundle alone.

  fit       verify the bundle checksum, refit, persist the estimator and a reconstruction receipt
  validate  compare the reconstruction against the historical P1.10 scores, fail closed on any
            unexplained discrepancy
  score     emit a finite score plus an explicit availability state for every eligible contig

Usage:
  v11_scorer_p111.py fit      --dev-bundle XLSX --out-model PKL --receipt JSON
  v11_scorer_p111.py validate --model PKL --historical TSV --receipt JSON
  v11_scorer_p111.py score    --model PKL --contig-table TSV --out TSV
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

# ---------------------------------------------------------------- LOCKED, verbatim from P1.10
SEED = 20260816
ABST = {"unknown", "unclassified", "repeat"}
TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC", "PlasmidFinder",
         "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
V11_THRESHOLD, V11_HIGH = 0.9524, 0.9605
DEV_BUNDLE_SHA256 = "db558a6775f473662369fb1c358f28530f85883ea3767beb807d031d2646e091"
SOURCE_SCRIPT = "scripts/p1_10/evaluate_model1_p110.py"

COUNT_NUM = ["n_valid", "n_plasmid", "n_chrom", "n_abstain", "frac_plasmid", "frac_chrom",
             "agreement"]
LEN_NUM = ["SR contig length", "log10_len"]
FRAG_NUM = ["log10_nsr"]

# Declared IN ADVANCE. sklearn/numpy/pandas versions match those that produced P1.10, the seed is
# fixed and the estimator is deterministic, so exact equality is expected. The tolerance exists to
# make "exact" falsifiable, not to absorb drift.
SCORE_TOLERANCE = 1e-12

FORBIDDEN_INPUT_TOKENS = ("truth_hold", "truth_table", "_assembly_report", ".gbff", ".paf",
                          "/truth/", "\\truth\\", "ani_cluster")
TRUTH_COLUMNS = ("truth_bin", "final_truth_label", "truth_len", "best_plasmid_hit",
                 "best_chromosome_hit", "Ground-truth class")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def guard(*paths):
    for p in paths:
        if p and any(t in str(p).lower() for t in FORBIDDEN_INPUT_TOKENS):
            sys.exit("REFUSING: input path looks truth-derived: %s" % p)


# ---------------------------------------------------------------- frozen feature construction
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


def make_pipe(tools):
    fs = dict(cat=tools, num=COUNT_NUM + LEN_NUM + FRAG_NUM, extra=["abst_" + t for t in tools])
    tr = [("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), fs["cat"]),
          ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]),
           fs["num"] + fs["extra"])]
    return Pipeline([("prep", ColumnTransformer(tr, remainder="drop")),
                     ("clf", HistGradientBoostingClassifier(max_depth=3, max_iter=200,
                                                            learning_rate=0.06,
                                                            min_samples_leaf=25,
                                                            l2_regularization=1.0,
                                                            random_state=SEED))])


def feature_order(tools):
    """The exact column order the ColumnTransformer consumes."""
    return {"categorical": list(tools),
            "numeric": COUNT_NUM + LEN_NUM + FRAG_NUM + ["abst_" + t for t in tools]}


# ---------------------------------------------------------------- fit
def fit(dev_bundle):
    guard(dev_bundle)
    got = sha(dev_bundle)
    if got != DEV_BUNDLE_SHA256:
        sys.exit("REFUSING: development bundle hashes %s, expected the sealed %s"
                 % (got, DEV_BUNDLE_SHA256))
    det = pd.read_excel(dev_bundle, sheet_name="Plasmid Detection", engine="openpyxl")
    gt = pd.read_excel(dev_bundle, sheet_name="Ground-truth", engine="openpyxl")
    asm = pd.read_excel(dev_bundle, sheet_name="Assembly Statistics", engine="openpyxl")
    K = ["Sample ID", "SR contig ID"]
    dev = gt.merge(det, on=K, validate="1:1").merge(asm[K + ["Number of SR contigs"]], on=K,
                                                    validate="1:1")
    dev = dev[dev["SR contig has ARGs"].eq(True)].copy().reset_index(drop=True)
    if len(dev) != 1460:
        sys.exit("REFUSING: development ARG-bearing rows must be 1460, got %d" % len(dev))
    dev = build_features(dev, TOOLS)
    ydev = dev["Ground-truth class"].eq("plasmid").astype(int).values
    pipe = make_pipe(TOOLS)
    pipe.fit(dev, ydev)
    Xd = pipe.named_steps["prep"].transform(dev)
    return pipe, {"dev_rows": int(len(dev)), "dev_sha256": got,
                  "design_matrix_shape": list(Xd.shape),
                  "n_positive": int(ydev.sum()), "n_negative": int((1 - ydev).sum())}


# ---------------------------------------------------------------- score
def score_frame(df, tools=TOOLS):
    """Prediction-side feature frame. FAILED/MISSING are recoded to 'unknown' exactly as P1.10
    did - scored as abstention AND flagged separately - never as a negative."""
    leaked = [c for c in df.columns if c in TRUTH_COLUMNS]
    if leaked:
        sys.exit("REFUSING: truth column(s) present in the scoring frame: %s" % leaked)
    X = df.copy()
    for t in tools:
        X[t] = X[t].replace({"FAILED": "unknown", "MISSING": "unknown"})
    return build_features(X, tools)


def score(pipe, df):
    """Returns (scores, availability, reasons). A row that cannot be scored abstains."""
    n = len(df)
    scores = np.full(n, np.nan)
    avail = np.zeros(n, dtype=bool)
    reasons = [""] * n
    if n == 0:
        return scores, avail, reasons
    missing_cols = [c for c in TOOLS + ["SR contig length", "Number of SR contigs"]
                    if c not in df.columns]
    if missing_cols:
        return scores, avail, ["absent_required_column:%s" % ",".join(missing_cols)] * n
    bad = []
    for c in ("SR contig length", "Number of SR contigs"):
        v = pd.to_numeric(df[c], errors="coerce")
        bad.append(~np.isfinite(v.to_numpy(dtype=float)))
    malformed = bad[0] | bad[1]
    ok_idx = np.where(~malformed)[0]
    for i in np.where(malformed)[0]:
        reasons[i] = "malformed_numeric_value"
    if len(ok_idx):
        sub = df.iloc[ok_idx].copy()
        # A malformed cell anywhere in the column leaves it object-dtype even after the offending
        # rows are dropped, and np.log10 then fails on the survivors. Coerce the two numeric
        # columns explicitly. Every surviving row is already known finite, so this cannot change a
        # well-formed score - guarded by the historical-equivalence test.
        for _c in ("SR contig length", "Number of SR contigs"):
            sub[_c] = pd.to_numeric(sub[_c], errors="coerce").astype(float)
        X = score_frame(sub)
        p = pipe.predict_proba(X)[:, 1]
        for k, i in enumerate(ok_idx):
            if np.isfinite(p[k]):
                scores[i], avail[i] = float(p[k]), True
            else:
                reasons[i] = "non_finite_model_output"
    return scores, avail, reasons


def classify(s, a):
    if not a:
        return "model_abstain"
    return ("high_confidence_plasmid" if s >= V11_HIGH
            else "plasmid_selected" if s >= V11_THRESHOLD else "not_selected")


# ---------------------------------------------------------------- validation vs P1.10
def validate_historical(pipe, historical_tsv):
    guard(historical_tsv)
    h = pd.read_csv(historical_tsv, sep="\t", dtype=str)
    if "M2_score" not in h.columns:
        sys.exit("REFUSING: historical table has no M2_score column")
    hist = h["M2_score"].astype(float).to_numpy()
    d = h.copy()
    d["SR contig length"] = pd.to_numeric(d["SR contig length"], errors="coerce")
    d["Number of SR contigs"] = pd.to_numeric(d["Number of SR contigs"], errors="coerce")
    # drop truth columns before scoring so the scorer's own guard is exercised honestly
    d = d.drop(columns=[c for c in d.columns if c in TRUTH_COLUMNS], errors="ignore")
    s, a, _ = score(pipe, d)
    n_cmp = int(a.sum())
    diff = np.abs(s[a] - hist[a])
    mx = float(diff.max()) if n_cmp else None
    exact = int((diff == 0).sum()) if n_cmp else 0
    cls_hist = np.array([classify(v, True) for v in hist[a]])
    cls_new = np.array([classify(v, True) for v in s[a]])
    return {"n_historical_rows": int(len(h)), "n_compared": n_cmp,
            "n_exactly_equal": exact,
            "max_abs_difference": mx,
            "tolerance_declared_in_advance": SCORE_TOLERANCE,
            "within_tolerance": (mx is not None and mx <= SCORE_TOLERANCE),
            "exact_equality_achieved": (mx == 0.0) if mx is not None else False,
            "n_classification_mismatches": int((cls_hist != cls_new).sum()),
            "classifications_identical": bool((cls_hist == cls_new).all())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["fit", "validate", "score"])
    ap.add_argument("--dev-bundle")
    ap.add_argument("--model")
    ap.add_argument("--out-model")
    ap.add_argument("--historical")
    ap.add_argument("--contig-table")
    ap.add_argument("--out")
    ap.add_argument("--receipt")
    a = ap.parse_args()
    import pickle

    if a.mode == "fit":
        pipe, info = fit(a.dev_bundle)
        with open(a.out_model, "wb") as f:
            pickle.dump({"pipeline": pipe, "tools": TOOLS, "seed": SEED,
                         "feature_order": feature_order(TOOLS),
                         "thresholds": {"standard": V11_THRESHOLD, "high_confidence": V11_HIGH},
                         "dev_sha256": info["dev_sha256"]}, f)
        rec = {"receipt": "PlasmidCall v1.1 reconstruction", "built_utc": utc(),
               "development_bundle": a.dev_bundle,
               "development_bundle_sha256": info["dev_sha256"],
               "development_bundle_matches_sealed": info["dev_sha256"] == DEV_BUNDLE_SHA256,
               "source_script": SOURCE_SCRIPT,
               "source_script_sha256": sha(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                        "..", "p1_10",
                                                        "evaluate_model1_p110.py")),
               "scorer": "scripts/p1_12/v11_scorer_p111.py",
               "scorer_sha256": sha(os.path.abspath(__file__)),
               "serialized_estimator": a.out_model,
               "serialized_estimator_sha256": sha(a.out_model),
               "seed": SEED, "featureset": "F_full_no_taxon",
               "estimator": ("HistGradientBoostingClassifier(max_depth=3, max_iter=200, "
                             "learning_rate=0.06, min_samples_leaf=25, l2_regularization=1.0, "
                             "random_state=20260816)"),
               "feature_order": feature_order(TOOLS),
               "fit_policy": ("refit ONLY on the sealed 1,460-row development bundle; no P1.11 "
                              "data, truth, reference, ANI output or label enters the fit"),
               "environment": {"python": platform.python_version(),
                               "sklearn": sklearn.__version__,
                               "numpy": np.__version__, "pandas": pd.__version__,
                               "platform": platform.platform()},
               **info}
        json.dump(rec, open(a.receipt, "w", encoding="utf-8"), indent=1)
        print("  fitted on %d development rows" % info["dev_rows"])
        print("  design matrix: %s" % info["design_matrix_shape"])
        print("  bundle sha256 matches sealed: %s" % rec["development_bundle_matches_sealed"])
        print("  estimator -> %s  (%s)" % (a.out_model, rec["serialized_estimator_sha256"][:16]))
        print("  receipt   -> %s" % a.receipt)
        sys.exit(0)

    B = pickle.load(open(a.model, "rb"))
    pipe = B["pipeline"]

    if a.mode == "validate":
        v = validate_historical(pipe, a.historical)
        for k, val in v.items():
            print("  %-34s %s" % (k, val))
        ok = v["within_tolerance"] and v["classifications_identical"]
        print("  VERDICT: %s" % ("EQUIVALENT" if ok else "*** DISCREPANCY - FAIL CLOSED ***"))
        if a.receipt:
            r = json.load(open(a.receipt, encoding="utf-8"))
            r["historical_validation"] = v
            r["historical_validation_verdict"] = "EQUIVALENT" if ok else "DISCREPANCY"
            json.dump(r, open(a.receipt, "w", encoding="utf-8"), indent=1)
        sys.exit(0 if ok else 3)

    # ---- score
    guard(a.contig_table, a.out)
    df = pd.read_csv(a.contig_table, sep="\t", dtype=str)
    df = df.drop(columns=[c for c in df.columns if c in TRUTH_COLUMNS], errors="ignore")
    if "SR contig length" not in df.columns and "contig_length" in df.columns:
        df["SR contig length"] = pd.to_numeric(df["contig_length"], errors="coerce")
    if "Number of SR contigs" not in df.columns:
        L = pd.to_numeric(df.get("SR contig length"), errors="coerce")
        nsr = df.assign(_L=L)[lambda x: x["_L"] >= 1000].groupby("sample").size()
        df["Number of SR contigs"] = df["sample"].map(nsr).astype(float)
    s, av, why = score(pipe, df)
    with open(a.out, "w", encoding="utf-8", newline="") as f:
        f.write("sample\tcontig_id\tM2_score\tv11_score_state\tv11_call\tabstention_reason\n")
        for i in range(len(df)):
            f.write("%s\t%s\t%s\t%s\t%s\t%s\n"
                    % (df["sample"].iloc[i], df["contig_id"].iloc[i],
                       ("%.17g" % s[i]) if av[i] else "",
                       "available" if av[i] else "model_abstain",
                       classify(s[i], av[i]),
                       "" if av[i] else (why[i] or "score_unavailable")))
    print("  scored %d rows: %d available, %d model_abstain -> %s"
          % (len(df), int(av.sum()), int((~av).sum()), a.out))
    sys.exit(0)


if __name__ == "__main__":
    main()

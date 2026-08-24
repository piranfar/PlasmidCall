#!/usr/bin/env python3
"""P1.10-B: independent reproduction of the authoritative development M2 (and M0) results.
Replicates the frozen procedure of 05_models.py exactly. READ-ONLY with respect to the
preserved development bundle; writes nothing into it. Emits a machine-readable receipt."""
import json, hashlib, platform, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
import sklearn

BUNDLE = r"E:/AMR_Evidence_Data/P1.9_cleanroom/model1_development_bundle"
XL = BUNDLE + "/predictions.xlsx"
SEED = 20260816; NFOLD = 5; MIN_POS_CALLS = 10; PPV_TARGET = 0.95
ABST = {"unknown", "unclassified", "repeat"}

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""): h.update(b)
    return h.hexdigest()

det = pd.read_excel(XL, sheet_name="Plasmid Detection", engine="openpyxl")
gt  = pd.read_excel(XL, sheet_name="Ground-truth", engine="openpyxl")
asm = pd.read_excel(XL, sheet_name="Assembly Statistics", engine="openpyxl")
sp  = pd.read_excel(XL, sheet_name="Species", engine="openpyxl")
K = ["Sample ID", "SR contig ID"]; TOOLS = [c for c in det.columns if c not in K]
df = (gt.merge(det, on=K, validate="1:1")
        .merge(asm[K + ["Number of SR contigs"]], on=K, validate="1:1")
        .merge(sp, on="Sample ID", how="left"))
e = df[df["SR contig has ARGs"].eq(True)].copy().reset_index(drop=True)
y = e["Ground-truth class"].eq("plasmid").astype(int).values
groups = e["Sample ID"].values

V = e[TOOLS].astype(str); Vv = V.where(~V.isin(ABST))
e["n_valid"] = Vv.notna().sum(axis=1); e["n_plasmid"] = Vv.eq("plasmid").sum(axis=1)
e["n_chrom"] = Vv.eq("chromosome").sum(axis=1); e["n_abstain"] = len(TOOLS) - e["n_valid"]
e["frac_plasmid"] = e["n_plasmid"] / e["n_valid"].replace(0, np.nan)
e["frac_chrom"] = e["n_chrom"] / e["n_valid"].replace(0, np.nan)
e["agreement"] = np.maximum(e["frac_plasmid"], e["frac_chrom"])
e["log10_len"] = np.log10(e["SR contig length"].clip(lower=1))
e["log10_nsr"] = np.log10(e["Number of SR contigs"].clip(lower=1))
for t in TOOLS: e["abst_" + t] = V[t].isin(ABST).astype(int)
COUNT_NUM = ["n_valid", "n_plasmid", "n_chrom", "n_abstain", "frac_plasmid", "frac_chrom", "agreement"]
LEN_NUM = ["SR contig length", "log10_len"]; FRAG_NUM = ["log10_nsr"]
ABST_IND = ["abst_" + t for t in TOOLS]
FS = dict(cat=TOOLS, num=COUNT_NUM + LEN_NUM + FRAG_NUM, extra=ABST_IND)

def make_pipe(fs, model):
    tr = []
    if fs["cat"]: tr.append(("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), fs["cat"]))
    if fs["num"] + fs["extra"]:
        tr.append(("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), fs["num"] + fs["extra"]))
    return Pipeline([("prep", ColumnTransformer(tr, remainder="drop")), ("clf", model)])

HGB = lambda: HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.06,
        min_samples_leaf=25, l2_regularization=1.0, random_state=SEED)

def pick_threshold(p_inner, y_inner, target=PPV_TARGET, min_pos=MIN_POS_CALLS):
    best = None
    for thr in np.unique(np.round(p_inner, 4)):
        sel = p_inner >= thr
        if sel.sum() < min_pos: continue
        if y_inner[sel].mean() >= target: best = thr; break
    return 1.01 if best is None else float(best)

def sel_metrics(yv, call):
    tp = int(((call == 1) & (yv == 1)).sum()); fp = int(((call == 1) & (yv == 0)).sum())
    tn = int(((call == 0) & (yv == 0)).sum()); fn = int(((call == 0) & (yv == 1)).sum())
    un = int((call < 0).sum()); d = lambda a, b: (a / b) if b else float("nan")
    return dict(TP=tp, FP=fp, TN=tn, FN=fn, unresolved=un, plasmid_PPV=d(tp, tp + fp),
                plasmid_recall=d(tp, int((yv == 1).sum())), coverage=d(tp + fp + tn + fn, len(yv)))

outer = StratifiedGroupKFold(n_splits=NFOLD, shuffle=True, random_state=SEED)
FOLDS = list(outer.split(e, y, groups=groups))
for i, (tr, va) in enumerate(FOLDS):
    assert not (set(groups[tr]) & set(groups[va])), "ISOLATE LEAK fold %d" % i

oof_p = np.full(len(e), np.nan); oof_thr = np.full(len(e), np.nan); fold_thr = []
for f, (tr, va) in enumerate(FOLDS):
    Xtr, Xva = e.iloc[tr], e.iloc[va]; ytr = y[tr]
    inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=SEED + f)
    p_in = np.full(len(tr), np.nan)
    for itr, iva in inner.split(Xtr, ytr, groups=groups[tr]):
        assert not (set(groups[tr][itr]) & set(groups[tr][iva]))
        m = make_pipe(FS, HGB()); m.fit(Xtr.iloc[itr], ytr[itr])
        p_in[iva] = m.predict_proba(Xtr.iloc[iva])[:, 1]
    thr = pick_threshold(p_in, ytr); fold_thr.append(round(thr, 4))
    m = make_pipe(FS, HGB()); m.fit(Xtr, ytr)
    oof_p[va] = m.predict_proba(Xva)[:, 1]; oof_thr[va] = thr
call = np.where(oof_p >= oof_thr, 1, 0)
M2 = sel_metrics(y, call)
agree = e["agreement"].values; lab = (e["n_plasmid"] >= e["n_chrom"]).astype(int).values
M0 = sel_metrics(y, np.where((e["n_valid"] > 0) & (agree >= 0.90), lab, -1))

AUTH_M2 = dict(TP=189, FP=13, TN=1167, FN=91, PPV=0.9356435643564357, recall=0.675, coverage=1.0)
AUTH_M0 = dict(TP=104, FP=5, TN=1117, FN=0, unresolved=234, PPV=0.9541284403669725, recall=0.37142857142857144)
AUTH_THR = [0.9732, 0.9605, 0.9378, 0.9718, 0.9524]
med = float(np.median(fold_thr))

rec = {
 "artifact": "P1.10B_DEV_M2_REPRODUCTION_RECEIPT",
 "utc": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
 "input": {"predictions_xlsx": XL, "sha256": sha(XL),
           "sheets_used": ["Plasmid Detection", "Ground-truth", "Assembly Statistics", "Species"],
           "rows_all": int(len(df)), "rows_ARG_bearing": int(len(e)),
           "target_plasmid": int(y.sum()), "target_chromosome": int((y == 0).sum()),
           "isolate_grouping_units": int(pd.Series(groups).nunique())},
 "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                 "pandas": pd.__version__, "numpy": np.__version__},
 "spec": {"estimator": "HistGradientBoostingClassifier(max_depth=3,max_iter=200,learning_rate=0.06,min_samples_leaf=25,l2_regularization=1.0)",
          "featureset": "F_full_no_taxon", "seed": SEED,
          "outer": "StratifiedGroupKFold(5,shuffle,random_state=SEED)",
          "inner": "StratifiedGroupKFold(4,shuffle,random_state=SEED+fold)", "group": "Sample ID",
          "threshold_rule": "smallest thr with inner-OOF PPV>=0.95 and >=10 positive calls",
          "class_orientation": "predict_proba[:,1] == P(plasmid); y = (Ground-truth class == 'plasmid')",
          "target_coding": "plasmid=1, chromosome=0",
          "abstention_vocabulary": sorted(ABST),
          "feature_order": TOOLS + COUNT_NUM + LEN_NUM + FRAG_NUM + ABST_IND},
 "reproduced": {"M2": M2, "M0": M0, "fold_thresholds": fold_thr, "fold_threshold_median": med},
 "authoritative": {"M2": AUTH_M2, "M0": AUTH_M0, "fold_thresholds": AUTH_THR, "fold_threshold_median": 0.9605},
}
rec["verdict"] = {
 "M2_confusion_matrix_exact": (M2["TP"], M2["FP"], M2["TN"], M2["FN"]) == (189, 13, 1167, 91),
 "M2_PPV_exact": abs(M2["plasmid_PPV"] - AUTH_M2["PPV"]) < 1e-12,
 "M2_recall_exact": abs(M2["plasmid_recall"] - AUTH_M2["recall"]) < 1e-12,
 "M0_exact": (M0["TP"], M0["FP"], M0["TN"], M0["FN"], M0["unresolved"]) == (104, 5, 1117, 0, 234),
 "fold_thresholds_exact": fold_thr == AUTH_THR,
 "median_is_0_9605": abs(med - 0.9605) < 1e-12,
}
rec["verdict"]["ALL_PASS"] = all(rec["verdict"].values())
print(json.dumps(rec, indent=1, default=float))

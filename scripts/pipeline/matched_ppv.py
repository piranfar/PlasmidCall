#!/usr/bin/env python3
"""Corrected diagnostic: MATCHED-PPV comparison of A / B / C and feature increments.

The previous comparison was invalid: B and C were compared at separately selected, unconstrained
thresholds. The objective is constrained - maximise recall SUBJECT TO PPV >= 0.95 - so candidates
must be compared on their precision-recall frontiers at matched precision.

Two numbers are reported for every candidate and they mean different things:
  frontier_*  threshold swept on the out-of-fold scores themselves. This is a FRONTIER COMPARISON,
              not a performance claim: sweeping on the evaluation scores is optimistic.
  nested_*    threshold chosen inside the inner training folds only, never seeing the held-out
              isolate. This is the honest performance estimate.
"""
import csv, json, os, collections, warnings
import numpy as np
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupKFold

OUT = os.path.dirname(os.path.abspath(__file__))
SEED = 20260821
ABST = {"unknown", "unclassified", "repeat"}
TOOLS12 = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
           "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
PLATON = ["platon_rds", "platon_protein_score", "platon_orfs", "platon_replication",
          "platon_mobilization", "platon_orit", "platon_conjugation", "platon_amr",
          "platon_rrna", "platon_plasmid_hits", "platon_circular"]
MOB = ["mob_is_plasmid", "mob_has_bin", "mob_rep_types", "mob_relaxase", "mob_circular", "mob_gc"]
STRUCT = ["length", "depth", "circular", "gfa_degree", "gfa_component_size"]
OTHERCONT = ["genomad_plasmid", "genomad_chrom", "genomad_virus", "pg2_plasmid", "pg2_chrom",
             "rf_votes_plasmid", "rf_votes_chrom", "rf_frac_plasmid",
             "plascope_best", "plascope_second", "plascope_nhits", "plascope_hit_frac",
             "pf_max_identity", "pf_n_hits"]
ALLCONT = STRUCT + OTHERCONT + PLATON + MOB

rows = [r for r in csv.DictReader(open(os.path.join(OUT, "probe_dataset.tsv"), encoding="utf-8"),
                                  delimiter="\t")]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def subset(pop, cohorts):
    R = [r for r in rows if r[pop] == "1" and r["truth_bin"] not in ("", "nan")
         and r["cohort"] in cohorts]
    y = np.array([int(float(r["truth_bin"])) for r in R])
    g = np.array([r["sample"] for r in R])
    v11 = np.array([float(r["v11_M2_score"]) for r in R])
    return R, y, g, v11


def cat_block(R):
    cat = np.array([[r["cat_" + t] for t in TOOLS12] for r in R], dtype=object)
    oh = OneHotEncoder(handle_unknown="ignore", sparse_output=False).fit(cat)
    A = np.isin(cat, list(ABST)).astype(float)
    valid = (~np.isin(cat, list(ABST) + ["FAILED", "MISSING", ""])).astype(float)
    npl = (cat == "plasmid").sum(1, keepdims=True).astype(float)
    nch = (cat == "chromosome").sum(1, keepdims=True).astype(float)
    nv = valid.sum(1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        fp = np.where(nv > 0, npl / nv, 0.0); fc = np.where(nv > 0, nch / nv, 0.0)
    return np.hstack([oh.transform(cat), A, npl, nch, nv, fp, fc, np.maximum(fp, fc)])


def cont_block(R, cols):
    X = np.array([[num(r[c]) for c in cols] for r in R], dtype=float)
    ind = np.array([[1.0 if r["_platon_state"] == "no_hit" else 0.0,
                     1.0 if r["_plasmidfinder_state"] == "no_hit" else 0.0] for r in R])
    return np.hstack([X, ind])


def mk():
    return Pipeline([("i", SimpleImputer(strategy="median", add_indicator=True)),
                     ("s", StandardScaler()),
                     ("c", LogisticRegression(max_iter=4000, random_state=SEED))])


def pick(p, y, target=0.95, mc=10):
    for t in np.unique(np.round(p, 4)):
        s = p >= t
        if s.sum() < mc:
            continue
        if y[s].mean() >= target:
            return float(t)
    return 1.01


def oof(X, y, g):
    """leave-one-isolate-out OOF scores + inner-fold-selected thresholds"""
    p = np.full(len(y), np.nan); thr = np.full(len(y), np.nan)
    for h in sorted(set(g)):
        tr = g != h; te = ~tr
        if len(set(y[tr])) < 2:
            continue
        Xt, yt, gt = X[tr], y[tr], g[tr]
        pin = np.full(len(yt), np.nan)
        for a, b in GroupKFold(n_splits=min(4, len(set(gt)))).split(Xt, yt, groups=gt):
            if len(set(yt[a])) < 2:
                continue
            m = mk(); m.fit(Xt[a], yt[a]); pin[b] = m.predict_proba(Xt[b])[:, 1]
        ok = ~np.isnan(pin)
        t = pick(pin[ok], yt[ok]) if ok.sum() > 20 else 0.5
        m = mk(); m.fit(Xt, yt)
        p[te] = m.predict_proba(X[te])[:, 1]; thr[te] = t
    return p, thr


def frontier(p, y, ppv_floor=0.95):
    """max recall at PPV >= floor, sweeping threshold on the OOF scores (optimistic; a frontier)"""
    best = (0.0, None, None, None)
    for t in np.unique(np.round(p, 4)):
        s = p >= t
        if s.sum() < 10:
            continue
        ppv = y[s].mean()
        if ppv >= ppv_floor:
            rec = y[s].sum() / max(1, y.sum())
            if rec > best[0]:
                best = (rec, float(t), float(ppv), int(s.sum()))
    return {"recall": best[0], "threshold": best[1], "ppv": best[2], "n_called": best[3]}


def at_ppv(p, y, target):
    return frontier(p, y, target)


def nested_metrics(p, thr, y):
    ok = ~np.isnan(p)
    c = np.zeros(len(y), int); c[ok] = (p[ok] >= thr[ok]).astype(int)
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    fn = int(((c == 0) & (y == 1)).sum())
    return {"TP": tp, "FP": fp, "FN": fn,
            "PPV": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "median_threshold": float(np.nanmedian(thr))}, c


def boot_paired(y, g, cA, cB, n=4000):
    """cluster bootstrap over isolates for the paired recall difference (B - A)"""
    iso = sorted(set(g)); idx = {i: np.where(g == i)[0] for i in iso}
    rng = np.random.default_rng(SEED); out = []
    for _ in range(n):
        pick_ = rng.choice(iso, size=len(iso), replace=True)
        r = np.concatenate([idx[i] for i in pick_])
        pos = y[r].sum()
        if pos == 0:
            continue
        out.append(((cB[r] == 1) & (y[r] == 1)).sum() / pos - ((cA[r] == 1) & (y[r] == 1)).sum() / pos)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)), float(np.median(out))


SETS = {}
def register(name, fn):
    SETS[name] = fn


register("B_categorical", lambda R: cat_block(R))
register("C_continuous_all", lambda R: cont_block(R, ALLCONT))
register("cat+platon", lambda R: np.hstack([cat_block(R), cont_block(R, PLATON)]))
register("cat+platon+mob", lambda R: np.hstack([cat_block(R), cont_block(R, PLATON + MOB)]))
register("cat+allcont", lambda R: np.hstack([cat_block(R), cont_block(R, ALLCONT)]))
register("platon_only", lambda R: cont_block(R, PLATON))
register("mob_only", lambda R: cont_block(R, MOB))
register("struct_only", lambda R: cont_block(R, STRUCT))
register("graph_only", lambda R: cont_block(R, ["gfa_degree", "gfa_component_size"]))

report = {}
for label, cohorts in (("ALL47", {"P1.9", "P1.10"}), ("P1.10_only", {"P1.10"}), ("P1.9_only", {"P1.9"})):
    for pop in ("in_CP2", "in_CP1"):
        R, y, g, v11 = subset(pop, cohorts)
        if len(set(g)) < 5 or y.sum() < 10:
            continue
        key = "%s|%s" % (label, pop)
        blk = {"n": len(y), "isolates": len(set(g)), "plasmid": int(y.sum()),
               "chrom": int((y == 0).sum())}
        # ---- A: frozen v1.1, fixed threshold, never refitted
        cA = (v11 >= 0.9524).astype(int)
        tp = int(((cA == 1) & (y == 1)).sum()); fp = int(((cA == 1) & (y == 0)).sum())
        fn = int(((cA == 0) & (y == 1)).sum())
        blk["A_v11_frozen"] = {"nested": {"TP": tp, "FP": fp, "FN": fn,
                                          "PPV": tp / (tp + fp) if tp + fp else None,
                                          "recall": tp / (tp + fn) if tp + fn else None,
                                          "median_threshold": 0.9524},
                               "frontier_ppv95": frontier(v11, y),
                               "at_ppv": {str(t): at_ppv(v11, y, t) for t in (0.95, 0.96, 0.97, 0.98)}}
        for name, fn_ in SETS.items():
            X = fn_(R)
            p, thr = oof(X, y, g)
            nm, cB = nested_metrics(p, thr, y)
            lo, hi, md = boot_paired(y, g, cA, cB)
            blk[name] = {"nested": nm,
                         "frontier_ppv95": frontier(p, y),
                         "at_ppv": {str(t): at_ppv(p, y, t) for t in (0.95, 0.96, 0.97, 0.98)},
                         "paired_recall_diff_vs_v11": {"median": md, "ci95": [lo, hi]},
                         "_scores": p.tolist(), "_thr": thr.tolist()}
        report[key] = blk
        print("\n===== %s   n=%d  isolates=%d  plasmid=%d" % (key, len(y), len(set(g)), int(y.sum())), flush=True)
        print("  %-18s | nested PPV/recall | frontier@PPV>=0.95 recall (thr) | paired d-recall [95pct CI]" % "candidate")
        for name in ["A_v11_frozen"] + list(SETS):
            b = blk[name]; nn = b["nested"]; fr = b["frontier_ppv95"]
            pd_ = b.get("paired_recall_diff_vs_v11")
            print("  %-18s | %.4f / %.4f       | %.4f (%.4f)            | %s" %
                  (name, nn["PPV"] or 0, nn["recall"] or 0, fr["recall"], fr["threshold"] or 0,
                   ("%+.3f [%+.3f,%+.3f]" % (pd_["median"], pd_["ci95"][0], pd_["ci95"][1])) if pd_ else "-"), flush=True)

json.dump(report, open(os.path.join(OUT, "matched_ppv_results.json"), "w"), indent=1)
print("\nwrote matched_ppv_results.json")

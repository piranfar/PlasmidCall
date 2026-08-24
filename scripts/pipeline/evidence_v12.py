#!/usr/bin/env python3
"""Regenerate every recorded piece of v1.2-General evidence under the FROZEN encoding.

Every number written into a freeze artifact is produced by the same encode()/apply_neutrality()
path the deployed model uses.

Two different questions are answered separately and must not be conflated:
  5a  FEATURE ABLATION      remove a tool from the panel and REFIT. "How much information does
                            this tool carry?"
  5b  FAILURE SENSITIVITY   keep the FROZEN model and feed the tool as unavailable, with
                            neutrality applied. "What happens if it fails in deployment?"
"""
import csv, json, os, sys, warnings, collections
import numpy as np
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freeze_v12 import (encode, make_estimator, mets, pick_threshold, TOOL_ORDER, VOCAB,
                        FEATURES, FROZEN_THRESHOLD, PPV_TARGET, SEED, OUT, FREEZE,
                        apply_neutrality, observed_states, neutral_from_pipeline, tool_block)

rows = [r for r in csv.DictReader(open(os.path.join(OUT, "probe_dataset.tsv"), encoding="utf-8"),
                                  delimiter="\t")]


def load(cohorts, pop):
    R = [r for r in rows if r[pop] == "1" and r["cohort"] in cohorts
         and r["truth_bin"] not in ("", "nan")]
    y = np.array([int(float(r["truth_bin"])) for r in R])
    g = np.array([r["sample"] for r in R])
    v11 = np.array([float(r["v11_M2_score"]) for r in R])
    calls = np.array([[r["cat_" + t] for t in TOOL_ORDER] for r in R], dtype=object)
    return R, y, g, v11, encode(calls), calls


def loio(X, y, g):
    p = np.full(len(y), np.nan)
    for h in sorted(set(g)):
        tr = g != h
        m = make_estimator(); m.fit(X[tr], y[tr]); p[~tr] = m.predict_proba(X[~tr])[:, 1]
    return p


def frontier(p, y, floor):
    best = (0.0, None, None, None)
    for t in np.unique(np.round(p, 4)):
        s = p >= t
        if s.sum() < 10:
            continue
        if y[s].mean() >= floor:
            rec = y[s].sum() / max(1, y.sum())
            if rec > best[0]:
                best = (rec, float(t), float(y[s].mean()), int(s.sum()))
    return {"recall": best[0], "threshold": best[1], "ppv": best[2], "n_called": best[3]}


R, y, g, v11, X, CALLS = load({"P1.10"}, "in_CP2")
OBS = observed_states(CALLS)
p = loio(X, y, g)
c = (p >= FROZEN_THRESHOLD).astype(int)
cA = (v11 >= 0.9524).astype(int)
EV = {}

# ---------------------------------------------------------------- 1. per-isolate paired detail
per = []
for h in sorted(set(g)):
    m = g == h
    pos = int(y[m].sum())
    rn = ((c[m] == 1) & (y[m] == 1)).sum() / pos if pos else None
    ro = ((cA[m] == 1) & (y[m] == 1)).sum() / pos if pos else None
    per.append({"sample": h, "n_contigs": int(m.sum()), "n_plasmid": pos,
                "v11_recall": ro, "v12_recall": rn, "delta": (rn - ro) if pos else None,
                "v11_FP": int(((cA[m] == 1) & (y[m] == 0)).sum()),
                "v12_FP": int(((c[m] == 1) & (y[m] == 0)).sum())})
imp = [x for x in per if x["delta"] is not None and x["delta"] > 0]
wor = [x for x in per if x["delta"] is not None and x["delta"] < 0]
tie = [x for x in per if x["delta"] is not None and x["delta"] == 0]
EV["per_isolate"] = {"improved": len(imp), "worsened": len(wor), "unchanged": len(tie),
                     "isolates_with_plasmid": len(imp) + len(wor) + len(tie),
                     "worsened_detail": wor,
                     "median_v11_recall": float(np.median([x["v11_recall"] for x in per if x["n_plasmid"]])),
                     "median_v12_recall": float(np.median([x["v12_recall"] for x in per if x["n_plasmid"]]))}
with open(os.path.join(FREEZE, "P1.12_V1.2_PER_ISOLATE.tsv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(per[0]), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(per)
print("PER-ISOLATE  improved=%d worsened=%d unchanged=%d (of %d with >=1 plasmid)"
      % (len(imp), len(wor), len(tie), len(imp) + len(wor) + len(tie)))
for x in wor:
    print("   worsened: %s  n_plasmid=%d  v1.1 %.4f -> v1.2 %.4f  (FP %d -> %d)"
          % (x["sample"], x["n_plasmid"], x["v11_recall"], x["v12_recall"], x["v11_FP"], x["v12_FP"]))

# ---------------------------------------------------------------- 2. cluster bootstrap
iso = sorted(set(g)); idx = {i: np.where(g == i)[0] for i in iso}
rng = np.random.default_rng(SEED)
dR, dP, aP, aR = [], [], [], []
for _ in range(4000):
    s = rng.choice(iso, size=len(iso), replace=True)
    r = np.concatenate([idx[i] for i in s])
    pos = y[r].sum()
    if pos == 0:
        continue
    nn = (c[r] == 1).sum(); no = (cA[r] == 1).sum()
    if nn == 0 or no == 0:
        continue
    rn = ((c[r] == 1) & (y[r] == 1)).sum() / pos; ro = ((cA[r] == 1) & (y[r] == 1)).sum() / pos
    pn = ((c[r] == 1) & (y[r] == 1)).sum() / nn; po = ((cA[r] == 1) & (y[r] == 1)).sum() / no
    dR.append(rn - ro); dP.append(pn - po); aP.append(pn); aR.append(rn)
q = lambda v, a: float(np.percentile(v, a))
EV["cluster_bootstrap"] = {
    "n_resamples": len(dR),
    "v12_PPV": {"median": q(aP, 50), "ci95": [q(aP, 2.5), q(aP, 97.5)]},
    "v12_recall": {"median": q(aR, 50), "ci95": [q(aR, 2.5), q(aR, 97.5)]},
    "delta_recall_vs_v11": {"median": q(dR, 50), "ci95": [q(dR, 2.5), q(dR, 97.5)]},
    "delta_PPV_vs_v11": {"median": q(dP, 50), "ci95": [q(dP, 2.5), q(dP, 97.5)]},
    "P_delta_recall_gt_0": float(np.mean(np.array(dR) > 0)),
    "P_PPV_ge_0.95": float(np.mean(np.array(aP) >= 0.95))}
b = EV["cluster_bootstrap"]
print("\nCLUSTER BOOTSTRAP (4000, over isolates)")
print("  v1.2 PPV    %.4f [%.4f, %.4f]" % (b["v12_PPV"]["median"], b["v12_PPV"]["ci95"][0], b["v12_PPV"]["ci95"][1]))
print("  v1.2 recall %.4f [%.4f, %.4f]" % (b["v12_recall"]["median"], b["v12_recall"]["ci95"][0], b["v12_recall"]["ci95"][1]))
print("  d-recall    %+.4f [%+.4f, %+.4f]   P(d>0)=%.4f"
      % (b["delta_recall_vs_v11"]["median"], b["delta_recall_vs_v11"]["ci95"][0],
         b["delta_recall_vs_v11"]["ci95"][1], b["P_delta_recall_gt_0"]))
print("  d-PPV       %+.4f [%+.4f, %+.4f]   P(PPV>=0.95)=%.4f"
      % (b["delta_PPV_vs_v11"]["median"], b["delta_PPV_vs_v11"]["ci95"][0],
         b["delta_PPV_vs_v11"]["ci95"][1], b["P_PPV_ge_0.95"]))

# ---------------------------------------------------------------- 3. strata
def numcol(name):
    out = []
    for r in R:
        try:
            out.append(float(r.get(name, "")))
        except (TypeError, ValueError):
            out.append(np.nan)
    return np.array(out)


def strat(name, mask):
    if mask.sum() == 0 or y[mask].sum() == 0:
        return None
    return {"stratum": name, "n": int(mask.sum()), "n_plasmid": int(y[mask].sum()),
            "v11_recall": float(((cA[mask] == 1) & (y[mask] == 1)).sum() / y[mask].sum()),
            "v12_recall": float(((c[mask] == 1) & (y[mask] == 1)).sum() / y[mask].sum()),
            "v12_PPV": (float(y[mask][c[mask] == 1].mean()) if (c[mask] == 1).sum() else None)}


L = numcol("length"); circ = numcol("circular"); deg = numcol("gfa_degree")
S = [x for x in [strat("length_1-10kb", (L >= 1000) & (L < 10000)),
                 strat("length_10-50kb", (L >= 10000) & (L < 50000)),
                 strat("length_>=50kb", L >= 50000),
                 strat("circular", circ == 1), strat("linear", circ == 0),
                 strat("gfa_isolated_deg0", deg == 0), strat("gfa_connected_deg>0", deg > 0)] if x]
EV["strata"] = S
with open(os.path.join(FREEZE, "P1.12_V1.2_STRATA.tsv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(S[0]), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(S)
print("\nSTRATA (v1.1 recall -> v1.2 recall)")
for x in S:
    print("  %-22s n=%-5d pos=%-4d  %.4f -> %.4f   v1.2 PPV=%s"
          % (x["stratum"], x["n"], x["n_plasmid"], x["v11_recall"], x["v12_recall"],
             "%.4f" % x["v12_PPV"] if x["v12_PPV"] is not None else "n/a"))

# ---------------------------------------------------------------- 4. permutation audit
perm = []
for k in range(20):
    rp = np.random.default_rng(SEED + k)
    ys = y.copy()
    for h in set(g):
        m = np.where(g == h)[0]; ys[m] = rp.permutation(y[m])
    mm = mets(ys, (loio(X, ys, g) >= FROZEN_THRESHOLD).astype(int))
    perm.append({"replicate": k, "PPV": mm["PPV"], "recall": mm["recall"]})
pv = [x["recall"] or 0.0 for x in perm]
EV["permutation_audit"] = {"n_replicates": len(perm), "scheme": "labels shuffled within isolate",
                           "max_recall": float(max(pv)), "mean_recall": float(np.mean(pv)),
                           "observed_recall": mets(y, c)["recall"], "replicates": perm}
print("\nPERMUTATION AUDIT (20 within-isolate shuffles)  max recall=%.4f  mean=%.4f  vs observed %.4f"
      % (max(pv), np.mean(pv), mets(y, c)["recall"]))

# ---------------------------------------------------------------- 5a. feature ablation (refit)
abl = []
base = mets(y, c)
for j, t in enumerate(TOOL_ORDER):
    ca = CALLS.copy(); ca[:, j] = "MISSING"
    ma = mets(y, (loio(encode(ca), y, g) >= FROZEN_THRESHOLD).astype(int))
    abl.append({"tool_removed": t, "PPV": ma["PPV"], "recall": ma["recall"],
                "delta_PPV": ma["PPV"] - base["PPV"], "delta_recall": ma["recall"] - base["recall"]})
abl.sort(key=lambda x: x["delta_recall"])
EV["ablation_refit_single_tool_removal"] = abl
with open(os.path.join(FREEZE, "P1.12_V1.2_ABLATION.tsv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(abl[0]), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(abl)
print("\nFEATURE ABLATION (tool removed from the panel and model REFITTED), threshold %.4f"
      % FROZEN_THRESHOLD)
print("  base PPV=%.4f recall=%.4f" % (base["PPV"], base["recall"]))
for x in abl:
    print("  -%-14s PPV=%.4f (%+.4f)  recall=%.4f (%+.4f)"
          % (x["tool_removed"], x["PPV"], x["delta_PPV"], x["recall"], x["delta_recall"]))

# ---------------------------------------------------------------- 5b. deployment failure
def loio_fail(fail_idx):
    """leave-one-isolate-out; at SCORING time the named tools are unavailable, neutrality applied"""
    p_ = np.full(len(y), np.nan)
    cf = CALLS.copy()
    for j in fail_idx:
        cf[:, j] = "MISSING"
    Xf = encode(cf)
    for h in sorted(set(g)):
        tr = g != h
        m = make_estimator(); m.fit(X[tr], y[tr])
        Xn = apply_neutrality(Xf[~tr], cf[~tr], neutral_from_pipeline(m), OBS)
        p_[~tr] = m.predict_proba(Xn)[:, 1]
    return p_


fail1 = []
for j, t in enumerate(TOOL_ORDER):
    mf = mets(y, (loio_fail([j]) >= FROZEN_THRESHOLD).astype(int))
    fail1.append({"tool_unavailable": t, "PPV": mf["PPV"], "recall": mf["recall"],
                  "delta_PPV": mf["PPV"] - base["PPV"],
                  "delta_recall": mf["recall"] - base["recall"]})
fail1.sort(key=lambda x: x["delta_recall"])
EV["deployment_single_tool_failure"] = fail1
print("\nDEPLOYMENT FAILURE SENSITIVITY (frozen model, tool unavailable, neutrality applied)")
for x in fail1:
    print("  x%-14s PPV=%.4f (%+.4f)  recall=%.4f (%+.4f)"
          % (x["tool_unavailable"], x["PPV"], x["delta_PPV"], x["recall"], x["delta_recall"]))

worst_order = [TOOL_ORDER.index(x["tool_unavailable"]) for x in fail1]
multi = []
for k in (2, 3, 4, 6):
    mf = mets(y, (loio_fail(worst_order[:k]) >= FROZEN_THRESHOLD).astype(int))
    multi.append({"n_tools_unavailable": k, "tools": [TOOL_ORDER[j] for j in worst_order[:k]],
                  "PPV": mf["PPV"], "recall": mf["recall"],
                  "n_positive_calls": mf["TP"] + mf["FP"],
                  "delta_PPV": (mf["PPV"] - base["PPV"]) if mf["PPV"] is not None else None,
                  "delta_recall": mf["recall"] - base["recall"],
                  "note": ("model makes NO positive calls at all"
                           if (mf["TP"] + mf["FP"]) == 0 else "")})
EV["deployment_multi_tool_failure"] = multi
print("\nMULTI-TOOL FAILURE (worst-first, frozen model)")
for x in multi:
    pv = ("%.4f (%+.4f)" % (x["PPV"], x["delta_PPV"])) if x["PPV"] is not None else "undefined"
    print("  %2d unavailable  PPV=%-18s recall=%.4f (%+.4f)  calls=%d %s"
          % (x["n_tools_unavailable"], pv, x["recall"], x["delta_recall"],
             x["n_positive_calls"], x["note"]))
    print("       %s" % ", ".join(x["tools"]))
with open(os.path.join(FREEZE, "P1.12_V1.2_FAILURE_SENSITIVITY.tsv"), "w", newline="",
          encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(fail1[0]), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(fail1)

# ---------------------------------------------------------------- 6. matched-PPV frontier
fr = {}
for floor in (0.95, 0.96, 0.97, 0.98, 0.99):
    fr["%.2f" % floor] = {"v1.2_general": frontier(p, y, floor), "v1.1_frozen": frontier(v11, y, floor)}
EV["matched_ppv_frontier"] = fr
print("\nMATCHED-PPV FRONTIER (threshold swept on OOF scores - a frontier, not a claim)")
for k, v in fr.items():
    a_, b_ = v["v1.2_general"], v["v1.1_frozen"]
    print("  floor %s | v1.2 %.4f (%s) | v1.1 %.4f (%s)"
          % (k, a_["recall"], "%.4f" % a_["threshold"] if a_["threshold"] else " n/a ",
             b_["recall"], "%.4f" % b_["threshold"] if b_["threshold"] else " n/a "))

# ---------------------------------------------------------------- 7. CP1
R1, y1, g1, v111, X1, _ = load({"P1.10"}, "in_CP1")
p1 = loio(X1, y1, g1)
m12 = mets(y1, (p1 >= FROZEN_THRESHOLD).astype(int))
m11 = mets(y1, (v111 >= 0.9524).astype(int))
m11h = mets(y1, (v111 >= 0.9605).astype(int))
EV["CP1_domain"] = {"n": int(len(y1)), "n_plasmid": int(y1.sum()),
                    "v12_general_on_CP1": m12, "v11_at_0.9524": m11, "v11_at_0.9605": m11h}
print("\nCP1 n=%d pos=%d -- the empirical basis for the router" % (len(y1), int(y1.sum())))
print("  v1.2-General @0.9285 : PPV=%.4f recall=%.4f" % (m12["PPV"] or 0, m12["recall"] or 0))
print("  v1.1         @0.9524 : PPV=%.4f recall=%.4f" % (m11["PPV"] or 0, m11["recall"] or 0))
print("  v1.1         @0.9605 : PPV=%.4f recall=%.4f" % (m11h["PPV"] or 0, m11h["recall"] or 0))

json.dump(EV, open(os.path.join(FREEZE, "P1.12_V1.2_EVIDENCE.json"), "w"), indent=1)
print("\nwrote P1.12_V1.2_EVIDENCE.json")

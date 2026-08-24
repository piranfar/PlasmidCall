#!/usr/bin/env python3
"""P1.11 FINAL EVALUATION - confirmatory, prespecified-secondary and exploratory.

Every definition comes from artefacts frozen BEFORE truth access:
  docs/plans/P1.11_PROSPECTIVE_EVALUATION_AMENDMENT.yaml   analyses A/A2/B/C, gates
  docs/plans/P1.11_SELECTIVE_CLASSIFICATION_ADDENDUM.yaml  selective estimand, coverage gate
  docs/plans/P1.11_PRE_TRUTH_EVALUATION_ADDENDUM.yaml      tools, F1, pairing, AUROC/AUPRC,
                                                           calibration, strata, hierarchy
No threshold is searched. No subgroup, comparator or estimand is introduced here.
"""
import collections
import csv
import glob
import io
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p111_tool_evaluation as TE

FROZEN = "E:/AMR_Evidence_Data/P1.9_cleanroom/p111_FROZEN/P1.11_FROZEN_PREDICTIONS.tsv"
TRUTHD = "E:/AMR_Evidence_Data/P1.9_cleanroom/p111_truth/truth"
OUT = "E:/AMR_Evidence_Data/P1.9_cleanroom/p111_RESULTS"

V12_T, V11_T, V11_H = 0.9285, 0.9524, 0.9605
N_BOOT, SEED = 4000, 20260821
PPV_FLOOR, RECALL_FLOOR = 0.95, 0.50
LEN_BINS = [("1-<2kb", 1000, 2000), ("2-<5kb", 2000, 5000),
            ("5-<10kb", 5000, 10000), (">=10kb", 10000, None)]


def f1(p, r):
    return (2 * p * r / (p + r)) if (p is not None and r is not None and (p + r) > 0) else None


def mets(y, c, npos_all=None):
    """c: 1 positive, 0 negative, -1 abstain."""
    y = np.asarray(y); c = np.asarray(c)
    m = c >= 0
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    tn = int(((c == 0) & (y == 0)).sum()); fn = int(((c == 0) & (y == 1)).sum())
    ppv = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    spec = tn / (tn + fp) if (tn + fp) else None
    npa = int((y == 1).sum()) if npos_all is None else npos_all
    return {"n_eligible": int(len(y)), "n_evaluable": int(m.sum()),
            "n_abstain": int((~m).sum()),
            "coverage": float(m.sum()) / len(y) if len(y) else None,
            "abstention_rate": float((~m).sum()) / len(y) if len(y) else None,
            "TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "selective_PPV": ppv, "selective_recall": rec, "specificity": spec,
            "selective_F1": f1(ppv, rec),
            "n_truth_positive_all": npa,
            "deployment_yield": (tp / npa) if npa else None}


def boot_ci(y, g, c, stat="all"):
    y = np.asarray(y); g = np.asarray(g); c = np.asarray(c)
    iso = sorted(set(g)); idx = {i: np.where(g == i)[0] for i in iso}
    rng = np.random.default_rng(SEED)
    P, R, S, F, C, D = [], [], [], [], [], []
    for _ in range(N_BOOT):
        s = rng.choice(iso, size=len(iso), replace=True)
        r = np.concatenate([idx[i] for i in s])
        m = mets(y[r], c[r])
        if m["selective_PPV"] is not None: P.append(m["selective_PPV"])
        if m["selective_recall"] is not None: R.append(m["selective_recall"])
        if m["specificity"] is not None: S.append(m["specificity"])
        if m["selective_F1"] is not None: F.append(m["selective_F1"])
        C.append(m["coverage"])
        if m["deployment_yield"] is not None: D.append(m["deployment_yield"])
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None
    return {"PPV_ci95": q(P), "recall_ci95": q(R), "specificity_ci95": q(S),
            "F1_ci95": q(F), "coverage_ci95": q(C), "deployment_yield_ci95": q(D),
            "P_PPV_ge_0.95": float(np.mean(np.array(P) >= PPV_FLOOR)) if P else None,
            "P_recall_gt_0.50": float(np.mean(np.array(R) > RECALL_FLOOR)) if R else None,
            "n_boot": N_BOOT, "seed": SEED, "unit": "isolate", "interval": "percentile 2.5/97.5"}


def paired(y, g, cA, cB, nameA, nameB):
    """Common-support paired comparison. Restricted to rows evaluable by BOTH."""
    y = np.asarray(y); g = np.asarray(g); cA = np.asarray(cA); cB = np.asarray(cB)
    m = (cA >= 0) & (cB >= 0)
    yy, gg, a, b = y[m], g[m], cA[m], cB[m]
    mA, mB = mets(yy, a), mets(yy, b)
    iso = sorted(set(gg)); idx = {i: np.where(gg == i)[0] for i in iso}
    rng = np.random.default_rng(SEED)
    D = collections.defaultdict(list)
    for _ in range(N_BOOT):
        s = rng.choice(iso, size=len(iso), replace=True)
        r = np.concatenate([idx[i] for i in s])
        x, z = mets(yy[r], a[r]), mets(yy[r], b[r])
        for k in ("selective_PPV", "selective_recall", "specificity", "selective_F1",
                  "coverage", "deployment_yield"):
            if x[k] is not None and z[k] is not None:
                D[k].append(x[k] - z[k])
    out = {"comparison": "%s minus %s" % (nameA, nameB),
           "common_support_denominator": int(m.sum()),
           "denominator_note": ("rows evaluable by BOTH methods; each method's own selective "
                                "metrics elsewhere use its own denominator"),
           nameA: mA, nameB: mB, "deltas": {}}
    for k, v in D.items():
        out["deltas"]["delta_" + k.replace("selective_", "")] = {
            "point": (mA[k] - mB[k]) if (mA[k] is not None and mB[k] is not None) else None,
            "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None,
            "P_delta_gt_0": float(np.mean(np.array(v) > 0)) if v else None}
    out["P_delta_note"] = ("descriptive bootstrap probability, NOT a frequentist p-value and not "
                           "an uncorrected significance claim")
    return out


def auroc_auprc(y, s):
    y = np.asarray(y); s = np.asarray(s, dtype=float)
    m = np.isfinite(s)
    y, s = y[m], s[m]
    if len(set(y.tolist())) < 2:
        return None, None
    o = np.argsort(-s); y = y[o]; s = s[o]
    P, N = int(y.sum()), int((1 - y).sum())
    # AUROC via rank statistic with tie handling
    r = np.empty(len(s)); i = 0
    asc = np.argsort(s); ss = s[asc]; ya = y[asc]
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        r[i:j + 1] = (i + j) / 2.0 + 1
        i = j + 1
    auroc = (r[ya == 1].sum() - P * (P + 1) / 2.0) / (P * N)
    tp = np.cumsum(y); fp = np.cumsum(1 - y)
    prec = tp / np.maximum(tp + fp, 1); rec = tp / P
    auprc = float(np.sum(np.diff(np.concatenate([[0.0], rec])) * prec))
    return float(auroc), auprc


def boot_auc(y, g, s):
    y = np.asarray(y); g = np.asarray(g); s = np.asarray(s, dtype=float)
    iso = sorted(set(g)); idx = {i: np.where(g == i)[0] for i in iso}
    rng = np.random.default_rng(SEED); A, B = [], []
    for _ in range(N_BOOT):
        k = rng.choice(iso, size=len(iso), replace=True)
        r = np.concatenate([idx[i] for i in k])
        a, b = auroc_auprc(y[r], s[r])
        if a is not None: A.append(a)
        if b is not None: B.append(b)
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None
    return q(A), q(B)


def calibration(y, s, g):
    y = np.asarray(y); s = np.asarray(s, dtype=float); g = np.asarray(g)
    m = np.isfinite(s); y, s, g = y[m], s[m], g[m]
    brier = float(np.mean((s - y) ** 2))
    eps = 1e-12
    lo = np.log(np.clip(s, eps, 1 - eps) / (1 - np.clip(s, eps, 1 - eps)))
    # calibration slope/intercept: logistic regression of y on the logit, no refit of the model
    def fit(lo, y):
        b0, b1 = 0.0, 1.0
        for _ in range(200):
            z = b0 + b1 * lo; p = 1 / (1 + np.exp(-z)); w = np.maximum(p * (1 - p), 1e-9)
            r = y - p
            X = np.column_stack([np.ones_like(lo), lo])
            H = X.T @ (X * w[:, None]); Gd = X.T @ r
            try: d = np.linalg.solve(H + 1e-9 * np.eye(2), Gd)
            except Exception: break
            b0 += d[0]; b1 += d[1]
            if abs(d).max() < 1e-10: break
        return float(b0), float(b1)
    b0, b1 = fit(lo, y)
    o = np.argsort(s); n = len(s); bins = np.array_split(o, 10)
    rel, ece = [], 0.0
    for b in bins:
        if len(b) == 0: continue
        mf, of = float(s[b].mean()), float(y[b].mean())
        rel.append({"n": int(len(b)), "mean_score": mf, "observed_fraction": of})
        ece += (len(b) / n) * abs(of - mf)
    iso = sorted(set(g)); idx = {i: np.where(g == i)[0] for i in iso}
    rng = np.random.default_rng(SEED); Br, B0, B1 = [], [], []
    for _ in range(N_BOOT):
        k = rng.choice(iso, size=len(iso), replace=True)
        r = np.concatenate([idx[i] for i in k])
        Br.append(float(np.mean((s[r] - y[r]) ** 2)))
        try:
            x0, x1 = fit(lo[r], y[r]); B0.append(x0); B1.append(x1)
        except Exception: pass
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None
    return {"analysis": "EMPIRICAL SCORE CALIBRATION - frozen scores, no recalibration",
            "naming_note": ("the frozen scores are not asserted to be calibrated probabilities"),
            "brier": brier, "brier_ci95": q(Br),
            "calibration_intercept": b0, "intercept_ci95": q(B0),
            "calibration_slope": b1, "slope_ci95": q(B1),
            "ECE_10_equal_frequency_bins": float(ece), "reliability_table": rel,
            "recalibration_applied": False}


def main():
    os.makedirs(OUT, exist_ok=True)
    pred = {(r["sample"], r["contig_id"]): r for r in
            csv.DictReader(io.open(FROZEN, encoding="utf-8"), delimiter="\t")}
    truth = {}
    for f in sorted(glob.glob(TRUTHD + "/*/truth_table.tsv")):
        for r in csv.DictReader(io.open(f, encoding="utf-8"), delimiter="\t"):
            truth[(r["sample"], r["contig_id"])] = r
    calls = {}
    CT = ("E:/AMR_Evidence_Data/P1.9_cleanroom/p111_builder_inputs/p112/inference/"
          "P1.11_call_table_reconciled.tsv")
    for r in csv.DictReader(io.open(CT, encoding="utf-8"), delimiter="\t"):
        calls.setdefault((r["sample"], r["contig_id"]), {})[r["tool"]] = (
            r["model1_code"], r.get("provenance_state", ""))

    keys = [k for k in pred if pred[k]["is_eligible_ge_1kb"] == "1"
            and truth[k]["final_truth_label"] in ("plasmid", "chromosome")]
    keys.sort()
    y = np.array([1 if truth[k]["final_truth_label"] == "plasmid" else 0 for k in keys])
    g = np.array([k[0] for k in keys])
    L = np.array([float(pred[k]["contig_length"]) for k in keys])
    arg = np.array([pred[k]["ARG_bearing_bool"] == "true" for k in keys])

    def bcall(col):
        return np.array([int(pred[k][col]) if pred[k][col] != "" else -1 for k in keys])

    def score(col):
        return np.array([float(pred[k][col]) if pred[k][col] != "" else np.nan for k in keys])

    c12, c11, c11h = bcall("v12_call_bool_0_9285"), bcall("v11_call_bool_0_9524"), bcall("v11_call_bool_0_9605")
    crt = bcall("router_call_bool")
    s12, s11 = score("v12_score"), score("v11_score")
    srt = np.array([float(pred[k]["router_score"]) if pred[k]["router_score"] != "" else np.nan
                    for k in keys])
    cp1 = arg

    R = {"meta": {"n_eligible_ge_1kb": sum(1 for k in pred if pred[k]["is_eligible_ge_1kb"] == "1"),
                  "n_truth_resolved_CP2": len(keys),
                  "n_truth_positive": int(y.sum()), "n_truth_negative": int((1 - y).sum()),
                  "n_isolates_with_resolved": len(set(g)),
                  "n_CP1": int(cp1.sum()),
                  "n_CP1_positive": int(y[cp1].sum()),
                  "bootstrap": {"n": N_BOOT, "seed": SEED, "unit": "isolate",
                                "interval": "percentile 2.5/97.5"}}}

    # ---------------- CONFIRMATORY
    A = mets(y, c12); A.update({"bootstrap": boot_ci(y, g, c12)})
    A["gate"] = {"rule": "selective_PPV >= 0.95 AND selective_recall > 0.50",
                 "PPV_met": A["selective_PPV"] is not None and A["selective_PPV"] >= PPV_FLOOR,
                 "recall_met": A["selective_recall"] is not None and A["selective_recall"] > RECALL_FLOOR}
    A["gate"]["verdict"] = "PASS" if (A["gate"]["PPV_met"] and A["gate"]["recall_met"]) else "FAIL"
    B1 = mets(y[cp1], c11[cp1]); B1["bootstrap"] = boot_ci(y[cp1], g[cp1], c11[cp1])
    B2 = mets(y[cp1], c11h[cp1]); B2["bootstrap"] = boot_ci(y[cp1], g[cp1], c11h[cp1])
    C = mets(y, crt); C["bootstrap"] = boot_ci(y, g, crt)
    R["CONFIRMATORY"] = {
        "A_primary_v1.2-General_CP2_at_0.9285": A,
        "B_secondary_v1.1_CP1_at_0.9524": B1,
        "B_secondary_v1.1_CP1_at_0.9605_high_confidence": B2,
        "C_routed_deployment_CP2": C,
        "A2_failure_inclusive_sensitivity": {
            "note": ("model coverage is 100% on CP2, so the failure-inclusive population is "
                     "identical to the primary population; reported for completeness"),
            "identical_to_primary": True}}

    # ---------------- 12 TOOLS (1A method-specific)
    tool_calls = {}
    for t in TE.TOOLS:
        ev = []
        for k in keys:
            code = calls.get(k, {}).get(t, ("MISSING", ""))[0]
            st = TE.eval_state(code)
            ev.append(1 if st == TE.POSITIVE else (0 if st == TE.NEGATIVE else -1))
        tool_calls[t] = np.array(ev)
    R["PRESPECIFIED_SECONDARY"] = {"tools_1A_method_specific": {"CP2": {}, "CP1": {}}}
    for t in TE.TOOLS:
        m = mets(y, tool_calls[t]); m["bootstrap"] = boot_ci(y, g, tool_calls[t])
        R["PRESPECIFIED_SECONDARY"]["tools_1A_method_specific"]["CP2"][t] = m
        m1 = mets(y[cp1], tool_calls[t][cp1])
        R["PRESPECIFIED_SECONDARY"]["tools_1A_method_specific"]["CP1"][t] = m1
    for nm, cc in (("v1.2-General@0.9285", c12), ("v1.1@0.9524", c11),
                   ("v1.1@0.9605", c11h), ("router", crt)):
        R["PRESPECIFIED_SECONDARY"]["tools_1A_method_specific"]["CP2"][nm] = mets(y, cc)
        R["PRESPECIFIED_SECONDARY"]["tools_1A_method_specific"]["CP1"][nm] = mets(y[cp1], cc[cp1])

    # ---------------- 1B pairwise common support
    pw = {}
    for t in TE.TOOLS:
        pw["v1.2-General_vs_" + t] = paired(y, g, c12, tool_calls[t], "v1.2-General", t)
        pw["router_vs_" + t] = paired(y, g, crt, tool_calls[t], "router", t)
    pw["v1.2-General_vs_v1.1@0.9524"] = paired(y, g, c12, c11, "v1.2-General", "v1.1@0.9524")
    pw["router_vs_v1.2-General"] = paired(y, g, crt, c12, "router", "v1.2-General")
    pw["router_vs_v1.1@0.9524"] = paired(y, g, crt, c11, "router", "v1.1@0.9524")
    R["PRESPECIFIED_SECONDARY"]["pairwise_1B_common_support"] = pw

    # ---------------- AUROC / AUPRC / calibration
    disc, cal = {}, {}
    for nm, s in (("v1.2-General", s12), ("v1.1", s11), ("router_selected_score", srt)):
        a, p = auroc_auprc(y, s)
        ca, cp = boot_auc(y, g, s)
        disc[nm] = {"AUROC": a, "AUROC_ci95": ca, "AUPRC": p, "AUPRC_ci95": cp,
                    "n": int(np.isfinite(s).sum()),
                    "note": "threshold-independent; NOT used to select any P1.11 threshold"}
        cal[nm] = calibration(y, s, g)
    R["PRESPECIFIED_SECONDARY"]["discrimination"] = disc
    R["PRESPECIFIED_SECONDARY"]["calibration"] = cal

    # ---------------- EXPLORATORY strata
    def sub(mask, label, extra=None):
        n = int(mask.sum())
        if n == 0:
            return {"stratum": label, "n_eligible": 0, "suppressed": True,
                    "reason": "no contigs"}
        m = mets(y[mask], c12[mask])
        d = {"stratum": label, "n_eligible": n, "n_isolates": len(set(g[mask])),
             "n_truth_positive": int(y[mask].sum()), "coverage": m["coverage"],
             "selective_PPV": m["selective_PPV"], "selective_recall": m["selective_recall"],
             "TP": m["TP"], "FP": m["FP"], "TN": m["TN"], "FN": m["FN"]}
        both = len(set(y[mask].tolist())) == 2
        if m["n_evaluable"] < 20 or not both:
            d["suppressed_estimate"] = True
            d["suppression_reason"] = ("fewer than 20 evaluable contigs" if m["n_evaluable"] < 20
                                       else "lacks one truth class")
            d["selective_PPV"] = None; d["selective_recall"] = None
        if extra: d.update(extra)
        return d
    ex = {"status": "EXPLORATORY - non-gating, cannot replace confirmatory analyses",
          "model": "v1.2-General at 0.9285"}
    provOK = np.array([calls.get(k, {}).get("MOB-recon", ("", ""))[1] == "OK" for k in keys])
    provREC = np.array([calls.get(k, {}).get("MOB-recon", ("", ""))[1] == "RECOVERED_OK"
                        for k in keys])
    ex["mobrecon_provenance"] = [sub(provOK, "MOB-recon OK"), sub(provREC, "MOB-recon RECOVERED_OK")]
    six = {"SAMD00521018", "SAMN51205863", "SAMN29503401", "SAMN29503705",
           "SAMN38448533", "SAMN53649220"}
    insix = np.array([k[0] in six for k in keys])
    ex["six_incomplete_tool_evidence_isolates"] = [
        sub(insix, "the six incomplete-tool-evidence isolates"),
        sub(~insix, "all other isolates")]
    ex["ARG_bearing"] = [sub(cp1, "ARG-bearing (CP1)"), sub(~cp1, "non-ARG (CP2 minus CP1)")]
    ex["length_bins"] = [sub((L >= lo) if hi is None else ((L >= lo) & (L < hi)), nm)
                         for nm, lo, hi in LEN_BINS]
    acc = {}
    rec_acq = json.load(io.open("E:/AMR_Evidence_Data/P1.9_cleanroom/p111_truth/receipts/"
                                "P1.11_truth_acquisition_receipt.json", encoding="utf-8"))
    per = next((v for v in rec_acq.values() if isinstance(v, list) and v and
                isinstance(v[0], dict)), [])
    srcmap = {x["biosample"]: x.get("reference_source") for x in per}
    for s_ in ("refseq", "genbank"):
        mk = np.array([srcmap.get(k[0]) == s_ for k in keys])
        acc[s_] = sub(mk, "truth source %s" % s_)
    ex["truth_source"] = acc
    R["EXPLORATORY"] = ex

    with io.open(os.path.join(OUT, "P1.11_FINAL_RESULTS.json"), "w", encoding="utf-8",
                 newline="\n") as f:
        json.dump(R, f, indent=1)
        f.write("\n")
    print(json.dumps({"A": {k: A[k] for k in ("n_evaluable", "TP", "FP", "TN", "FN",
                                              "selective_PPV", "selective_recall",
                                              "selective_F1", "coverage")},
                      "gate": A["gate"]["verdict"]}, indent=1))
    print("  results -> %s" % os.path.join(OUT, "P1.11_FINAL_RESULTS.json"))


if __name__ == "__main__":
    main()

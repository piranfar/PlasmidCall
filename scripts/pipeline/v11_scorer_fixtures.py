#!/usr/bin/env python3
"""P2 production-path fixtures for the reconstructed PlasmidCall v1.1 scorer.

All twelve predeclared classes, run through the PRODUCTION functions in v11_scorer_p111.py. No
test-only reimplementation. No truth is read: the historical-equivalence class compares against the
stored M2_score column of the P1.10 contig table, which is a PREDICTION, not a truth label.

Usage:  python v11_scorer_fixtures.py [--model PKL] [--out receipt.json]
"""
import argparse
import json
import os
import pickle
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import v11_scorer_p111 as S                       # production scorer

R = []
HIST = "E:/AMR_Evidence_Data/P1.9_cleanroom/p110/evaluation/P1.10_model1_contig_table.tsv"


def fx(name, got, want):
    ok = got == want
    R.append({"fixture": name, "expected": str(want), "observed": str(got), "pass": ok})
    print("  %-66s want=%-14s got=%-14s %s"
          % (name, want, got, "PASS" if ok else "*** FAIL ***"))
    return ok


def row(calls, length=5000, nsr=100, sample="S1", cid="c1"):
    d = {"sample": sample, "contig_id": cid,
         "SR contig length": length, "Number of SR contigs": nsr}
    for i, t in enumerate(S.TOOLS):
        d[t] = calls[i] if isinstance(calls, (list, tuple)) else calls
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(HERE, "..", "..", "models",
                                                    "plasmidcall_v1.1",
                                                    "plasmidcall_v1_1_m2.pkl"))
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "docs", "evidence",
                                                  "P1.11_V11_SCORER_FIXTURES.json"))
    a = ap.parse_args()
    B = pickle.load(open(a.model, "rb"))
    pipe = B["pipeline"]

    print("P1.11 v1.1 SCORER FIXTURES - production path\n")

    # ---------------------------------------------------------- 1. valid ordinary rows
    print(" 1  valid ordinary rows")
    df = pd.DataFrame([row(["plasmid"] * 12, cid="c1"),
                       row(["chromosome"] * 12, cid="c2"),
                       row(["plasmid"] * 6 + ["chromosome"] * 6, cid="c3")])
    s, av, why = S.score(pipe, df)
    fx("1  every ordinary row is scored", int(av.sum()), 3)
    fx("1b every score is finite and in [0,1]",
       bool(np.all(np.isfinite(s)) and np.all((s >= 0) & (s <= 1))), True)
    fx("1c unanimous plasmid scores above unanimous chromosome", bool(s[0] > s[1]), True)

    # ---------------------------------------------------------- 2. boundary scores
    print("\n 2  boundary scores")
    fx("2  exactly at the standard threshold -> plasmid_selected",
       S.classify(S.V11_THRESHOLD, True), "plasmid_selected")
    fx("2b one ulp below the standard threshold -> not_selected",
       S.classify(np.nextafter(S.V11_THRESHOLD, 0), True), "not_selected")
    fx("2c exactly at the high-confidence threshold -> high_confidence_plasmid",
       S.classify(S.V11_HIGH, True), "high_confidence_plasmid")
    fx("2d one ulp below high-confidence -> plasmid_selected",
       S.classify(np.nextafter(S.V11_HIGH, 0), True), "plasmid_selected")
    fx("2e a boundary score is never an abstention",
       S.classify(S.V11_THRESHOLD, True) == "model_abstain", False)

    # ---------------------------------------------------------- 3-4. missing / failed tool blocks
    print("\n 3-4 missing and failed direct-tool blocks")
    dfm = pd.DataFrame([row(["MISSING"] * 12, cid="allmiss"),
                        row(["plasmid"] * 6 + ["MISSING"] * 6, cid="halfmiss"),
                        row(["FAILED"] * 12, cid="allfail"),
                        row(["plasmid"] * 6 + ["FAILED"] * 6, cid="halffail")])
    sm, avm, _ = S.score(pipe, dfm)
    fx("3  all-MISSING row still receives a finite score (locked behaviour)",
       bool(avm[0] and np.isfinite(sm[0])), True)
    fx("3b partially-MISSING row is scored", bool(avm[1]), True)
    fx("4  all-FAILED row still receives a finite score (locked behaviour)",
       bool(avm[2] and np.isfinite(sm[2])), True)
    fx("4b partially-FAILED row is scored", bool(avm[3]), True)
    fx("3c/4c missing or failed tool evidence is NOT a model abstention",
       int((~avm).sum()), 0)
    Xf = S.score_frame(dfm.copy())
    fx("4d FAILED/MISSING are recoded to 'unknown' exactly as P1.10 did",
       bool((Xf[S.TOOLS].iloc[0] == "unknown").all()), True)
    fx("4e the abstention indicator flags them separately",
       int(Xf["abst_HyAsP"].iloc[0]), 1)

    # ---------------------------------------------------------- 5. malformed numeric values
    print("\n 5  malformed numeric values")
    bad = pd.DataFrame([row(["plasmid"] * 12, cid="ok"),
                        row(["plasmid"] * 12, length="abc", cid="badlen"),
                        row(["plasmid"] * 12, nsr=float("nan"), cid="badnsr"),
                        row(["plasmid"] * 12, length=float("inf"), cid="inflen")])
    sb, avb, whyb = S.score(pipe, bad)
    fx("5  malformed length -> model_abstain", bool(~avb[1]), True)
    fx("5b NaN contig count -> model_abstain", bool(~avb[2]), True)
    fx("5c infinite length -> model_abstain", bool(~avb[3]), True)
    fx("5d the reason is recorded, not pooled", whyb[1], "malformed_numeric_value")
    fx("5e a malformed row never becomes a Boolean negative",
       S.classify(sb[1], avb[1]), "model_abstain")
    fx("5f the well-formed row alongside them is still scored", bool(avb[0]), True)

    # ---------------------------------------------------------- 6. absent required columns
    print("\n 6  absent required columns")
    miss = pd.DataFrame([row(["plasmid"] * 12)]).drop(columns=["PlaScope"])
    sM, avM, whyM = S.score(pipe, miss)
    fx("6  absent required column -> every row abstains", int(avM.sum()), 0)
    fx("6b the missing column is named in the reason",
       "PlaScope" in whyM[0] and whyM[0].startswith("absent_required_column"), True)
    miss2 = pd.DataFrame([row(["plasmid"] * 12)]).drop(columns=["Number of SR contigs"])
    _, avM2, whyM2 = S.score(pipe, miss2)
    fx("6c absent numeric column also abstains", int(avM2.sum()), 0)

    # ---------------------------------------------------------- 7. reordered columns
    print("\n 7  reordered columns")
    base = pd.DataFrame([row(["plasmid"] * 6 + ["chromosome"] * 6, cid="c1")])
    shuf = base[list(reversed(list(base.columns)))]
    s1, a1, _ = S.score(pipe, base)
    s2, a2, _ = S.score(pipe, shuf)
    fx("7  column order does not change the score", float(s1[0]), float(s2[0]))
    fx("7b feature order is pinned by name, not position",
       B["feature_order"]["categorical"], S.TOOLS)

    # ---------------------------------------------------------- 8. duplicate contig keys
    print("\n 8  duplicate contig keys")
    dup = pd.DataFrame([row(["plasmid"] * 12, cid="dup"), row(["plasmid"] * 12, cid="dup")])
    sd, ad, _ = S.score(pipe, dup)
    fx("8  duplicate keys are scored identically, not merged", float(sd[0]), float(sd[1]))
    fx("8b duplicate keys are detectable downstream (both rows retained)", len(sd), 2)

    # ---------------------------------------------------------- 9-10. annotation independence
    print("\n 9-10 annotation states do not affect the v1.1 score")
    ann = pd.DataFrame([dict(row(["plasmid"] * 12, cid="zero_hit"),
                             annotation_state="ok", ARG_bearing_bool="false"),
                        dict(row(["plasmid"] * 12, cid="ann_fail"),
                             annotation_state="failed", ARG_bearing_bool="NA")])
    sa, aa, _ = S.score(pipe, ann)
    fx("9  zero-hit but successfully completed annotation is scored", bool(aa[0]), True)
    fx("10 annotation failure does not suppress the v1.1 score", bool(aa[1]), True)
    fx("9b/10b the score is identical regardless of annotation state",
       float(sa[0]), float(sa[1]))

    # ---------------------------------------------------------- 11. determinism
    print("\n11  deterministic repeat execution")
    r1, _, _ = S.score(pipe, base)
    r2, _, _ = S.score(pipe, base)
    fx("11 repeat scoring of the same frame is bit-identical", float(r1[0]), float(r2[0]))
    p2, info2 = S.fit("E:/AMR_Evidence_Data/P1.9_cleanroom/model1_development_bundle/"
                      "predictions.xlsx")
    rr, _, _ = S.score(p2, base)
    fx("11b an independent refit reproduces the same score bit-for-bit",
       float(r1[0]), float(rr[0]))
    fx("11c the refit sees the same design matrix", info2["design_matrix_shape"], [1460, 51])

    # ---------------------------------------------------------- 12. historical equivalence
    print("\n12  historical-score equivalence vs P1.10")
    if os.path.exists(HIST):
        v = S.validate_historical(pipe, HIST)
        fx("12 every historical row was scored", v["n_compared"], v["n_historical_rows"])
        fx("12b max |difference| is exactly zero", v["max_abs_difference"], 0.0)
        fx("12c all rows exactly equal", v["n_exactly_equal"], v["n_compared"])
        fx("12d within the tolerance declared in advance", v["within_tolerance"], True)
        fx("12e classifications identical", v["classifications_identical"], True)
        fx("12f zero classification mismatches", v["n_classification_mismatches"], 0)
    else:
        fx("12 historical table available", os.path.exists(HIST), True)

    # ---------------------------------------------------------- truth isolation
    print("\n    truth isolation")
    leak = pd.DataFrame([dict(row(["plasmid"] * 12), truth_bin=1)])
    caught = False
    try:
        S.score_frame(leak.copy())
    except SystemExit:
        caught = True
    fx("   a truth column in the scoring frame is refused", caught, True)
    guarded = False
    try:
        S.guard("/data/p112/truth_hold/x.tsv")
    except SystemExit:
        guarded = True
    fx("   a truth-derived input path is refused", guarded, True)

    n, p = len(R), sum(1 for r in R if r["pass"])
    print("\n  %d fixtures, %d passed, %d failed" % (n, p, n - p))
    rec = {"suite": "P1.11 v1.1 scorer fixtures",
           "module_under_test": "scripts/p1_12/v11_scorer_p111.py",
           "exercises_production_functions": True, "truth_consumed": False,
           "predeclared_classes_covered": 12,
           "n_fixtures": n, "n_passed": p, "n_failed": n - p,
           "verdict": "PASS" if p == n else "FAIL", "fixtures": R}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=1)
        f.write("\n")
    print("  receipt: %s" % os.path.abspath(a.out))
    sys.exit(0 if p == n else 1)


if __name__ == "__main__":
    main()

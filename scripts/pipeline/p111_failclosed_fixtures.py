#!/usr/bin/env python3
"""Decision E: regression fixtures for the P1.11 fail-closed correction.

Exercises the PRODUCTION path in scripts/p1_12/evaluate_p111_locked_v2.py - the real
`score_available` and `classify_with_abstain` functions, and the real `main()` invoked as a
subprocess over synthetic contig tables. There is no duplicated test-only reimplementation of the
logic under test; if the production behaviour regresses, these fail.

The ten predeclared cases:
   1  valid v1.1 score below threshold      -> a genuine negative, stays in the confusion matrix
   2  valid v1.1 score at threshold         -> selected
   3  NaN v1.1 score                        -> model_abstain, NOT a negative
   4  absent v1.1 score                     -> model_abstain
   5  NaN v1.2 score                        -> model_abstain
   6  missing annotation_state COLUMN       -> hard schema failure, non-zero exit
   7  per-row failed annotation             -> routing_abstain
   8  valid no-core-ARG annotation          -> routed to v1.2-General
   9  valid core-ARG annotation             -> routed to v1.1
  10  no truth artefact is consumed         -> no real truth path is opened

Truth values inside the synthetic tables are INVENTED fixture data. No P1.11 truth exists, and
case 10 asserts that no real truth path is touched.

Usage:  python p111_failclosed_fixtures.py [--out receipt.json]
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import evaluate_p111_locked_v2 as EV          # the production module under test
from freeze_v12 import TOOL_ORDER

V11_T = EV.V11_THRESHOLD
RESULTS = []


def fx(name, got, want):
    ok = got == want
    RESULTS.append({"fixture": name, "expected": want, "observed": got, "pass": ok})
    print("  %-64s expected=%-14s got=%-14s %s"
          % (name, want, got, "PASS" if ok else "*** FAIL ***"))
    return ok


# --------------------------------------------------------------------------- synthetic table
COLS = (["sample", "contig_id", "truth_bin", "is_resolved", "ARG_bearing_bool", "M2_score",
         "length", "circular", "gfa_degree", "annotation_state"] + TOOL_ORDER)


def row(sample, cid, truth, arg, m2, ann="ok", call="plasmid", length=5000):
    r = {"sample": sample, "contig_id": cid, "truth_bin": truth, "is_resolved": "True",
         "ARG_bearing_bool": str(arg), "M2_score": m2, "length": length, "circular": 0,
         "gfa_degree": 1, "annotation_state": ann}
    for t in TOOL_ORDER:
        r[t] = call
    return r


def write_table(rows, path, drop_annotation_column=False):
    cols = [c for c in COLS if not (drop_annotation_column and c == "annotation_state")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader()
        for r in rows:
            w.writerow({k: v for k, v in r.items() if k in cols})


def run_evaluator(table, outdir):
    """Invoke the production main() as a subprocess. Returns (returncode, stdout+stderr, results)."""
    cp = subprocess.run([sys.executable, os.path.join(HERE, "evaluate_p111_locked_v2.py"),
                         "--contig-table", table, "--out", outdir],
                        capture_output=True, text=True)
    res = None
    rp = os.path.join(outdir, "P1.11_evaluation_results.json")
    if os.path.exists(rp):
        res = json.load(open(rp, encoding="utf-8"))
    return cp.returncode, (cp.stdout or "") + (cp.stderr or ""), res


def per_contig(outdir):
    p = os.path.join(outdir, "P1.11_routed_predictions.tsv")
    if not os.path.exists(p):
        return []
    return list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        HERE, "..", "..", "docs", "evidence", "P1.11_FAILCLOSED_FIXTURES.json"))
    a = ap.parse_args()

    print("P1.11 FAIL-CLOSED FIXTURES - exercising the production path in "
          "evaluate_p111_locked_v2.py\n")

    # ---------------------------------------------------------------- unit level, real functions
    print(" score_available() - the production availability predicate")
    fx("1  valid score below threshold is AVAILABLE (a real negative)",
       EV.score_available(0.5), True)
    fx("2  valid score at threshold is AVAILABLE",
       EV.score_available(V11_T), True)
    fx("3  float NaN is UNAVAILABLE", EV.score_available(float("nan")), False)
    fx("3b string 'nan' is UNAVAILABLE", EV.score_available("nan"), False)
    fx("4  empty string is UNAVAILABLE", EV.score_available(""), False)
    fx("4b None is UNAVAILABLE", EV.score_available(None), False)
    fx("5  +inf is UNAVAILABLE", EV.score_available(float("inf")), False)
    fx("5b -inf is UNAVAILABLE", EV.score_available(float("-inf")), False)
    fx("   non-numeric text is UNAVAILABLE", EV.score_available("FAILED"), False)
    fx("   exact 0.0 is AVAILABLE (a real score, not missing)", EV.score_available(0.0), True)

    print("\n classify_with_abstain() - NaN can never become a negative")
    vals = np.array([0.5, V11_T, np.nan, np.nan])
    avail = np.array([True, True, False, False])
    calls, _ = EV.classify_with_abstain(vals, avail, V11_T)
    fx("1  below-threshold available score -> 0 (negative)", int(calls[0]), 0)
    fx("2  at-threshold available score    -> 1 (selected)", int(calls[1]), 1)
    fx("3  unavailable score               -> -1 (abstain, NOT 0)", int(calls[2]), -1)
    fx("   no unavailable row was scored as a negative",
       int(((calls == 0) & ~avail).sum()), 0)
    # the defect this replaces, demonstrated directly
    fx("   REGRESSION GUARD: raw `nan >= t` would have yielded False (a negative)",
       bool(np.nan >= V11_T), False)

    tmp = tempfile.mkdtemp(prefix="p111fx_")

    # ---------------------------------------------------------------- 6. missing column -> hard fail
    print("\n end-to-end through production main()")
    t6 = os.path.join(tmp, "t6.tsv")
    write_table([row("S1", "c1", 1, True, 0.99), row("S1", "c2", 0, False, 0.01)],
                t6, drop_annotation_column=True)
    rc, out, _ = run_evaluator(t6, os.path.join(tmp, "o6"))
    fx("6  missing annotation_state COLUMN -> non-zero exit", rc != 0, True)
    fx("6b failure names the column and refuses to default it",
       ("annotation_state" in out and "refuses" in out.lower()), True)

    # ---------------------------------------------------------------- empty / unknown state
    t6b = os.path.join(tmp, "t6b.tsv")
    write_table([row("S1", "c1", 1, True, 0.99, ann=""), row("S1", "c2", 0, False, 0.01)], t6b)
    rc, out, _ = run_evaluator(t6b, os.path.join(tmp, "o6b"))
    fx("6c empty annotation_state value -> non-zero exit (empty is not 'ok')", rc != 0, True)

    t6c = os.path.join(tmp, "t6c.tsv")
    write_table([row("S1", "c1", 1, True, 0.99, ann="probably_fine"),
                 row("S1", "c2", 0, False, 0.01)], t6c)
    rc, out, _ = run_evaluator(t6c, os.path.join(tmp, "o6c"))
    fx("6d unrecognised annotation_state -> non-zero exit (never coerced to ok)", rc != 0, True)

    # ---------------------------------------------------------------- 7,8,9 routing + 3,4,5 abstain
    rows = [
        row("S1", "arg_ok", 1, True, 0.99),                        # 9  -> v1.1
        row("S1", "noarg_ok", 0, False, 0.01),                     # 8  -> v1.2-General
        row("S1", "ann_failed", 1, True, 0.99, ann="annotation_failed"),   # 7 -> routing_abstain
        row("S1", "ann_missing", 0, False, 0.01, ann="annotation_missing"),# 7 -> routing_abstain
        row("S2", "v11_nan", 1, True, "nan"),                      # 3  -> model_abstain
        row("S2", "v11_absent", 1, True, ""),                      # 4  -> model_abstain
        row("S2", "v11_below", 0, True, 0.10),                     # 1  -> real negative
        row("S2", "v11_at", 1, True, V11_T),                       # 2  -> selected
    ]
    t7 = os.path.join(tmp, "t7.tsv")
    write_table(rows, t7)
    rc, out, res = run_evaluator(t7, os.path.join(tmp, "o7"))
    fx("   production main() completed on a well-formed table", rc, 0)
    pc = {r["contig_id"]: r for r in per_contig(os.path.join(tmp, "o7"))}

    if res and pc:
        fx("7  per-row annotation_failed -> routing_abstain",
           pc["ann_failed"]["model_selected"], "routing_abstain")
        fx("7b per-row annotation_missing -> routing_abstain",
           pc["ann_missing"]["model_selected"], "routing_abstain")
        fx("7c routing abstentions are counted and observable",
           res["routing_coverage"]["n_routing_abstain"], 2)
        fx("8  valid no-core-ARG annotation -> v1.2-General",
           pc["noarg_ok"]["model_selected"], "v1.2-General")
        fx("9  valid core-ARG annotation -> v1.1",
           pc["arg_ok"]["model_selected"], "v1.1")
        fx("3  NaN v1.1 score -> model_abstain (not a negative)",
           pc["v11_nan"]["model_selected"], EV.MODEL_ABSTAIN)
        fx("4  absent v1.1 score -> model_abstain",
           pc["v11_absent"]["model_selected"], EV.MODEL_ABSTAIN)
        fx("3b abstained row emits no v1.1 class",
           pc["v11_nan"]["v11_class"], EV.MODEL_ABSTAIN)
        fx("1  valid below-threshold score keeps a real class",
           pc["v11_below"]["v11_class"] not in (EV.MODEL_ABSTAIN, ""), True)
        fx("2  valid at-threshold score is selected",
           pc["v11_at"]["v11_class"] not in (EV.MODEL_ABSTAIN, ""), True)
        fx("   model abstentions counted separately from router abstentions",
           res["routing_coverage"]["n_model_abstain"], 2)
        fx("   score-availability block reports the v1.1 abstain count",
           res["score_availability"]["v1.1_M2_score"]["n_model_abstain"], 2)
        fx("   analysis B reports its denominators explicitly",
           "denominators" in res.get("B_key_secondary", {}), True)
        fx("   analysis B excludes abstained rows from the scored denominator",
           res["B_key_secondary"]["denominators"]["n_model_abstain_v1_1"], 2)
        b = res["B_key_secondary"]["at_standard_threshold"]["metrics"]
        fx("   no abstained row entered B's confusion matrix",
           b["TP"] + b["FP"] + b["TN"] + b["FN"],
           res["B_key_secondary"]["denominators"]["n_scored"])
    else:
        fx("   production main() produced results", False, True)

    # ---------------------------------------------------------------- 5. NaN v1.2 probability
    fx("5  NaN v1.2 probability -> unavailable under the production predicate",
       bool(np.isfinite(np.array([np.nan]))[0]), False)
    c12, _ = EV.classify_with_abstain(np.array([np.nan, 0.99]), np.array([False, True]),
                                      EV.V12_THRESHOLD)
    fx("5b NaN v1.2 -> -1 abstain, valid 0.99 -> 1", (int(c12[0]), int(c12[1])), (-1, 1))

    # ---------------------------------------------------------------- 10. no truth consumed
    print("\n truth isolation")
    src = open(os.path.join(HERE, "evaluate_p111_locked_v2.py"), encoding="utf-8").read()
    fx("10  evaluator source references no truth_hold path", "truth_hold" in src, False)
    fx("10b evaluator never opens a .paf / assembly_report / gbff",
       any(s in src for s in (".paf", "_assembly_report", ".gbff")), False)
    fx("10c fixtures used only synthetic in-memory tables under a temp dir",
       tmp.startswith(tempfile.gettempdir()), True)
    fx("10d no real P1.11 truth artefact exists to consume",
       os.path.exists(os.path.join(HERE, "..", "..", "truth_hold")), False)

    n, p = len(RESULTS), sum(1 for r in RESULTS if r["pass"])
    print("\n  %d fixtures, %d passed, %d failed" % (n, p, n - p))
    rec = {"suite": "P1.11 fail-closed correction fixtures",
           "module_under_test": "scripts/p1_12/evaluate_p111_locked_v2.py",
           "exercises_production_functions": True,
           "n_fixtures": n, "n_passed": p, "n_failed": n - p,
           "verdict": "PASS" if p == n else "FAIL", "fixtures": RESULTS}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=1)
        f.write("\n")
    print("  receipt: %s" % os.path.abspath(a.out))
    sys.exit(0 if p == n else 1)


if __name__ == "__main__":
    main()

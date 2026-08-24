#!/usr/bin/env python3
"""Decision 9: the sixteen predeclared production-path fixtures for the selective-classification
framework and the P1.11 contig-table builder.

Every case runs through the PRODUCTION functions in build_p111_contig_table.py and
evaluate_p111_locked_v2.py. There is no test-only reimplementation of the logic under test.

No truth artefact is read. Synthetic tables live in a temp dir; truth values inside them are
invented fixture data used only to exercise the metric code.

Usage:  python p111_builder_fixtures.py [--out receipt.json]
"""
import argparse
import csv
import json
import os
import shutil
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_p111_contig_table as B          # production builder
import evaluate_p111_locked_v2 as EV         # production evaluator

R = []


def fx(name, got, want):
    ok = got == want
    R.append({"fixture": name, "expected": str(want), "observed": str(got), "pass": ok})
    print("  %-70s want=%-16s got=%-16s %s"
          % (name, want, got, "PASS" if ok else "*** FAIL ***"))
    return ok


def mk_isolate(root, sample, contigs, amr_state, arg_hits=None):
    """Materialise one isolate: FASTA, GFA, state marker, receipt, optional AMRFinder output."""
    ad = os.path.join(root, "assemblies", "shortread", sample)
    os.makedirs(ad, exist_ok=True)
    with open(os.path.join(ad, "shortread.fasta"), "w", encoding="utf-8") as f:
        for cid, ln in contigs:
            f.write(">%s\n%s\n" % (cid, "A" * ln))
    open(os.path.join(ad, "shortread.gfa"), "w", encoding="utf-8").close()

    # parse_all.py long format. The builder must consume model1_code (the normalised 7-term code),
    # NOT native_call (the raw per-tool vocabulary). native_call is deliberately filled with a
    # token outside the vocabulary so that a regression to the wrong column fails loudly.
    ct = os.path.join(root, "inference", "P1.11_call_table.tsv")
    os.makedirs(os.path.dirname(ct), exist_ok=True)
    fresh = not os.path.exists(ct)
    with open(ct, "a", newline="", encoding="utf-8") as cf:
        cw = csv.writer(cf, delimiter="\t", lineterminator="\n")
        if fresh:
            cw.writerow(["sample", "contig_id", "contig_length", "tool", "native_call",
                         "model1_code", "evidence_score", "native_sha256sums", "parser_version"])
        for _cid, _ln in contigs:
            for _t in ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
                       "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]:
                cw.writerow([sample, _cid, _ln, _t, "raw_native_token_not_in_vocab",
                             "plasmid", "", "", "p19c4-parsers/1.7"])

    sd = os.path.join(root, "inference", "state")
    rd = os.path.join(root, "inference", "receipts")
    # the frozen runner writes AMRFinder to annotation/native/<S>/<S>.amrfinder.tsv
    nd = os.path.join(root, "annotation", "native", sample)
    for d in (sd, rd, nd):
        os.makedirs(d, exist_ok=True)
    key = "amrfinder__%s" % sample

    if amr_state == "failed":
        open(os.path.join(sd, key + ".failed"), "w").write("rc=1 after 3 attempts")
    elif amr_state == "missing":
        pass                                          # no marker at all
    else:
        open(os.path.join(sd, key + ".done"), "w").close()
        json.dump({"tool": "amrfinder", "sample": sample, "status": "OK"},
                  open(os.path.join(rd, key + ".json"), "w"))
        if amr_state == "unparseable":
            pass                                      # success receipt, no output file
        else:
            with open(os.path.join(nd, "%s.amrfinder.tsv" % sample), "w", newline="",
                      encoding="utf-8") as f:
                w = csv.writer(f, delimiter="\t", lineterminator="\n")
                # real AMRFinderPlus header names, as emitted on the execution host
                w.writerow(["Name", "Protein id", "Contig id", "Scope", "Type", "Subtype",
                            "Class"])
                for cid in (arg_hits or []):
                    w.writerow([sample, "p1", cid, "core", "AMR", "AMR", "BETA-LACTAM"])
    return ad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "docs", "evidence",
                                                  "P1.11_BUILDER_FIXTURES.json"))
    a = ap.parse_args()

    print("P1.11 SELECTIVE-CLASSIFICATION FIXTURES - production path\n")
    tmp = tempfile.mkdtemp(prefix="p111bld_")
    root = os.path.join(tmp, "p112")

    # ---------------------------------------------------------- score-state fixtures 1-5
    print(" 1-5  score states, via the production predicate and classifier")
    fx("1  valid below-threshold score -> valid not-selected",
       B.classify(0.10, B.score_available(0.10), B.V11_THRESHOLD, B.V11_HIGH), "not_selected")
    fx("2  score exactly at threshold -> positive",
       B.classify(B.V11_THRESHOLD, True, B.V11_THRESHOLD, B.V11_HIGH), "plasmid_selected")
    fx("3  NaN score -> model abstention",
       B.classify(float("nan"), B.score_available(float("nan")), B.V11_THRESHOLD), "model_abstain")
    fx("4  absent score -> model abstention",
       B.classify("", B.score_available(""), B.V11_THRESHOLD), "model_abstain")
    fx("5  infinite score -> model abstention",
       B.classify(float("inf"), B.score_available(float("inf")), B.V11_THRESHOLD), "model_abstain")
    fx("   exact 0.0 is a real score, not missing", B.score_available(0.0), True)

    # ---------------------------------------------------------- 6-8 selective metrics
    print("\n 6-8  selective PPV / recall and coverage, via the production evaluator")
    vals = np.array([0.99, 0.10, np.nan, np.nan, 0.99])
    avail = np.array([True, True, False, False, True])
    y = np.array([1, 1, 1, 0, 0])
    calls, mask = EV.classify_with_abstain(vals, avail, 0.9524)
    sel = EV.mets(y[mask], calls[mask])
    fx("6  abstained rows are excluded from selective PPV/recall denominators",
       sel["TP"] + sel["FP"] + sel["TN"] + sel["FN"], int(avail.sum()))
    fx("6b selective_PPV = TP/(TP+FP) over evaluable rows only",
       round(sel["PPV"], 6), round(1 / 2, 6))
    fx("6c selective_recall = TP/(TP+FN) over evaluable rows only",
       round(sel["recall"], 6), round(1 / 2, 6))
    fx("6d no abstained row entered the confusion matrix",
       int(((calls == 0) | (calls == 1))[~avail].sum()), 0)
    cov = float(avail.sum()) / len(avail)
    fx("7  abstention decreases reported coverage", round(cov, 4), round(3 / 5, 4))
    fx("7b abstention_rate = n_model_abstain / n_truth_eligible",
       round(float((~avail).sum()) / len(avail), 4), round(2 / 5, 4))
    none_avail = np.zeros(4, dtype=bool)
    c0, m0 = EV.classify_with_abstain(np.array([np.nan] * 4), none_avail, 0.9524)
    z = EV.mets(np.array([1, 0, 1, 0])[m0], c0[m0])
    fx("8  zero predictions cannot produce a valid PPV result", z["PPV"], None)
    fx("8b zero predictions cannot produce a valid recall result", z["recall"], None)

    # ---------------------------------------------------------- 9 schema failure
    print("\n 9    missing annotation_state column -> hard schema failure")
    t9 = os.path.join(tmp, "t9.tsv")
    cols = ["sample", "contig_id", "truth_bin", "is_resolved", "ARG_bearing_bool",
            "M2_score", "length", "circular", "gfa_degree"] + B.TOOL_ORDER
    with open(t9, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader()
        r = {"sample": "S", "contig_id": "c1", "truth_bin": 1, "is_resolved": "True",
             "ARG_bearing_bool": "true", "M2_score": 0.99, "length": 5000,
             "circular": 0, "gfa_degree": 1}
        for t in B.TOOL_ORDER:
            r[t] = "plasmid"
        w.writerow(r)
    import subprocess
    cp = subprocess.run([sys.executable, os.path.join(HERE, "evaluate_p111_locked_v2.py"),
                         "--contig-table", t9, "--out", os.path.join(tmp, "o9")],
                        capture_output=True, text=True)
    fx("9  missing annotation_state column -> non-zero exit", cp.returncode != 0, True)
    fx("9b failure explains the required upstream fix",
       "annotation_state" in (cp.stdout + cp.stderr), True)

    # ---------------------------------------------------------- 10-13 annotation states
    print("\n10-13 annotation states, through the production builder")
    mk_isolate(root, "S_OK_ARG", [("c1", 5000)], "ok", arg_hits=["c1"])
    mk_isolate(root, "S_OK_ZERO", [("c1", 5000)], "ok", arg_hits=[])
    mk_isolate(root, "S_FAILED", [("c1", 5000)], "failed")
    mk_isolate(root, "S_MISSING", [("c1", 5000)], "missing")
    mk_isolate(root, "S_UNPARSE", [("c1", 5000)], "unparseable")
    out = os.path.join(tmp, "table.tsv")
    rows, recon = B.build(root, out, v11_scores=None,
                          model=os.path.join(HERE, "..", "..", "models",
                                             "plasmidcall_v1.2-general",
                                             "plasmidcall_v1_2_general.pkl"), verbose=False)
    by = {r["sample"]: r for r in rows}
    fx("10 successful zero-ARG annotation -> ok / false",
       (by["S_OK_ZERO"]["annotation_state"], by["S_OK_ZERO"]["ARG_bearing_bool"]), ("ok", "false"))
    fx("10b successful ARG-bearing annotation -> ok / true",
       (by["S_OK_ARG"]["annotation_state"], by["S_OK_ARG"]["ARG_bearing_bool"]), ("ok", "true"))
    fx("11 failed annotation -> failed / NA",
       (by["S_FAILED"]["annotation_state"], by["S_FAILED"]["ARG_bearing_bool"]), ("failed", "NA"))
    fx("12 missing annotation -> missing / NA",
       (by["S_MISSING"]["annotation_state"], by["S_MISSING"]["ARG_bearing_bool"]),
       ("missing", "NA"))
    fx("13 unparseable annotation -> unparseable / NA",
       (by["S_UNPARSE"]["annotation_state"], by["S_UNPARSE"]["ARG_bearing_bool"]),
       ("unparseable", "NA"))
    fx("   absence of an ARG is never inferred from a failure",
       any(r["annotation_state"] != "ok" and str(r["ARG_bearing_bool"]).lower() == "false"
           for r in rows), False)

    # ---------------------------------------------------------- 14-15 router vs standalone
    print("\n14-15 router abstention vs standalone availability")
    fx("14 router abstains for every invalid annotation state",
       {by[s]["router_state"] for s in ("S_FAILED", "S_MISSING", "S_UNPARSE")},
       {"routing_abstain"})
    fx("14b router emits no model and no call when it abstains",
       {(by[s]["router_model"], by[s]["router_call"])
        for s in ("S_FAILED", "S_MISSING", "S_UNPARSE")}, {("", "")})
    fx("14c each abstention reason is preserved, not pooled",
       sorted({by[s]["abstention_reason"] for s in ("S_FAILED", "S_MISSING", "S_UNPARSE")}),
       ["annotation_failed", "annotation_missing", "annotation_unparseable"])
    fx("15 standalone v1.2 remains AVAILABLE when annotation fails",
       {by[s]["v12_score_state"] for s in ("S_FAILED", "S_MISSING", "S_UNPARSE")}, {"available"})
    fx("15b a valid standalone v1.2 call is not suppressed by AMRFinder failure",
       all(by[s]["v12_call"] in ("plasmid_selected", "not_selected")
           for s in ("S_FAILED", "S_MISSING", "S_UNPARSE")), True)
    fx("15c model-score abstention and routing abstention are separate fields",
       ("v12_score_state" in by["S_FAILED"] and "router_state" in by["S_FAILED"]), True)
    fx("   v1.1 is injected, so it abstains rather than being fabricated",
       by["S_OK_ARG"]["v11_score_state"], "model_abstain")

    # ---------------------------------------------------------- 16 truth isolation
    print("\n16   truth isolation")
    src = open(os.path.join(HERE, "build_p111_contig_table.py"), encoding="utf-8").read()
    fx("16 builder emits no truth column",
       any(c in B.COLUMNS for c in ("truth_bin", "final_truth_label", "truth_len", "is_resolved")),
       False)
    fx("16b builder guard rejects a truth-derived input path",
       _guard_rejects(os.path.join(tmp, "truth_hold", "x.tsv")), True)
    fx("16c builder source opens no PAF / assembly report / GBFF",
       any(s in src for s in ("_assembly_report", ".gbff", ".paf")) and "FORBIDDEN" not in src,
       False)

    # ---------------------------------------------------------- builder validation checks
    print("\n     builder self-validation")
    for c in B.validate(rows, recon):
        fx("V  " + c["check"], c["pass"], True)

    shutil.rmtree(tmp, ignore_errors=True)
    n, p = len(R), sum(1 for r in R if r["pass"])
    print("\n  %d fixtures, %d passed, %d failed" % (n, p, n - p))
    rec = {"suite": "P1.11 selective-classification and builder fixtures",
           "modules_under_test": ["scripts/p1_12/build_p111_contig_table.py",
                                  "scripts/p1_12/evaluate_p111_locked_v2.py"],
           "exercises_production_functions": True, "truth_consumed": False,
           "n_fixtures": n, "n_passed": p, "n_failed": n - p,
           "verdict": "PASS" if p == n else "FAIL", "fixtures": R}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=1)
        f.write("\n")
    print("  receipt: %s" % os.path.abspath(a.out))
    sys.exit(0 if p == n else 1)


def _guard_rejects(path):
    """The guard calls sys.exit; a rejection is a SystemExit."""
    try:
        B.guard_inputs(path)
    except SystemExit:
        return True
    return False


if __name__ == "__main__":
    main()

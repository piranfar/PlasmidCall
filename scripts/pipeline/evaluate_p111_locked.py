#!/usr/bin/env python3
"""LOCKED P1.11 evaluation script. Written and hashed BEFORE any P1.11 outcome is observed.

This script fits nothing, selects nothing and searches no threshold. It loads the frozen
v1.2-General estimator, applies the frozen router, and reports the three predeclared analyses.

  0  COMPLETENESS GATE     critical-tool availability across the prespecified isolates. PlaScope
                            is critical: its absence takes recall from 0.7764 to 0.2013, below the
                            primary floor. Below 95% coverage the run is OPERATIONALLY
                            INCONCLUSIVE - neither PASS nor FAIL.
  A  PRIMARY CONFIRMATORY   v1.2-General on CP2 at the fixed threshold 0.9285, over the
                            complete-critical-panel isolates. PASS requires PPV >= 0.95 AND
                            recall > 0.50. Gating.
  A2 SENSITIVITY            the same analysis including critical-tool-failed isolates. Reported
                            whenever any critical failure occurred. Never replaces A.
  B  KEY SECONDARY          v1.1 on CP1 at 0.9524, plus the 0.9605 high-confidence band.
                            Non-gating: reported whatever it shows.
  C  ROUTED DEPLOYMENT      the two-domain system across every predeclared stratum.

Any deviation from this script invalidates the confirmatory claim. If a bug is found after P1.11
outcomes are known, the fix is reported as a deviation - the original result stands in the record.

Usage:  python evaluate_p111_locked.py --contig-table <tsv> --out <dir>
"""
import argparse, csv, json, os, pickle, sys, hashlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from freeze_v12 import encode, predict, TOOL_ORDER
import plasmidcall_router as RT

V12_THRESHOLD = 0.9285
V11_THRESHOLD = 0.9524
V11_HIGH = 0.9605
PRIMARY_PPV_FLOOR = 0.95
PRIMARY_RECALL_FLOOR = 0.50
N_BOOT = 4000
BOOT_SEED = 20260821

# ---------------------------------------------------------------- prespecified completeness gate
CRITICAL_TOOLS = ["PlaScope"]
CRITICAL_COVERAGE_MIN = 0.95
N_PRESPECIFIED_ISOLATES = 79
UNAVAILABLE_STATES = {"FAILED", "MISSING", ""}
# PlasmidFinder/FAILED was observed during training and carries a defined learned encoding, so it
# is permitted and is NOT treated as a panel-health failure. Every other tool preserves explicit
# FAILED/MISSING states, which are recorded but do not gate unless the tool is critical.
PERMITTED_TRAINED_FAILURE_STATES = {"PlasmidFinder": {"FAILED"}}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def mets(y, c):
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    tn = int(((c == 0) & (y == 0)).sum()); fn = int(((c == 0) & (y == 1)).sum())
    return {"n": int(len(y)), "n_plasmid": int(y.sum()), "TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "PPV": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "specificity": tn / (tn + fp) if tn + fp else None}


def boot(y, g, c, seed=BOOT_SEED, n=N_BOOT):
    """cluster bootstrap over isolates -> 95% CI for PPV and recall"""
    iso = sorted(set(g)); idx = {i: np.where(g == i)[0] for i in iso}
    rng = np.random.default_rng(seed); P, Rc = [], []
    for _ in range(n):
        s = rng.choice(iso, size=len(iso), replace=True)
        r = np.concatenate([idx[i] for i in s])
        yy, cc = y[r], c[r]
        tp = ((cc == 1) & (yy == 1)).sum(); fp = ((cc == 1) & (yy == 0)).sum()
        fn = ((cc == 0) & (yy == 1)).sum()
        if tp + fp:
            P.append(tp / (tp + fp))
        if tp + fn:
            Rc.append(tp / (tp + fn))
    q = lambda v, a: float(np.percentile(v, a)) if v else None
    return {"PPV_ci95": [q(P, 2.5), q(P, 97.5)], "recall_ci95": [q(Rc, 2.5), q(Rc, 97.5)],
            "P_PPV_ge_floor": float(np.mean(np.array(P) >= PRIMARY_PPV_FLOOR)) if P else None}


def truthy(x):
    return str(x).strip().lower() in ("true", "1")


def numeric(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contig-table", required=True,
                    help="P1.11 contig table: sample, contig_id, truth_bin, is_resolved, "
                         "ARG_bearing_bool, M2_score, length, circular, gfa_degree, and the 12 "
                         "frozen tool call columns")
    ap.add_argument("--model", default=os.path.join(HERE, "..", "..", "models",
                                                    "plasmidcall_v1.2-general",
                                                    "plasmidcall_v1_2_general.pkl"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--tool-state", default=None,
                    help="optional TSV: sample, tool, state (OK/FAILED/MISSING), retries. Takes "
                         "precedence over inference from the contig table.")
    ap.add_argument("--preflight-receipt", default=None,
                    help="P1.12_PREFLIGHT_RECEIPT.json, hashed into the results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    B = pickle.load(open(a.model, "rb"))
    assert B["threshold"] == V12_THRESHOLD, "frozen model carries a different threshold"
    assert B["tool_order"] == TOOL_ORDER, "frozen model carries a different tool order"
    assert "neutral_raw" in B and "observed_states" in B, "frozen model lacks the neutrality maps"

    rows = [r for r in csv.DictReader(open(a.contig_table, encoding="utf-8"), delimiter="\t")]
    R = [r for r in rows if truthy(r.get("is_resolved")) and r.get("truth_bin") not in ("", "nan", None)]
    if not R:
        sys.exit("no resolved contigs with truth in %s" % a.contig_table)

    y = np.array([int(float(r["truth_bin"])) for r in R])
    g = np.array([r["sample"] for r in R])
    arg = np.array([truthy(r.get("ARG_bearing_bool")) for r in R])
    v11 = np.array([numeric(r.get("M2_score")) for r in R])
    calls = np.array([[r.get(t, "MISSING") or "MISSING" for t in TOOL_ORDER] for r in R], dtype=object)

    # ---- frozen inference. No fitting anywhere in this file.
    # predict() applies missing-tool neutrality: any tool in a state not observed during training
    # has its block imputed to the training means so it contributes exactly zero. Scoring the raw
    # encoding directly would let an absent tool shift the logit by up to ~3 units.
    p12 = predict(B, calls)
    c12 = (p12 >= V12_THRESHOLD).astype(int)
    c11 = (v11 >= V11_THRESHOLD).astype(int)
    c11h = (v11 >= V11_HIGH).astype(int)

    # Routing. A contig whose ARG annotation failed or was never attempted is ABSTAINED on: it
    # receives no final routed class and is counted separately, never folded into either domain.
    ann_ok = np.array([str(r.get("annotation_state", "ok")).strip().lower()
                       not in ("annotation_failed", "annotation_missing", "failed", "missing")
                       for r in R])

    # ================================================================ 0. COMPLETENESS GATE
    # A tool is AVAILABLE for an isolate when it produced a usable call on at least one contig of
    # that isolate. An explicit tool-state table, when supplied, takes precedence over inference
    # from the contig table.
    tool_state = {}
    if a.tool_state and os.path.exists(a.tool_state):
        for r in csv.DictReader(open(a.tool_state, encoding="utf-8"), delimiter="\t"):
            tool_state[(r["sample"], r["tool"])] = str(r.get("state", "")).strip().upper()

    isolates = sorted(set(g))
    crit_ok, crit_fail = {}, {}
    for t in CRITICAL_TOOLS:
        j = TOOL_ORDER.index(t)
        ok = set()
        for h in isolates:
            m = g == h
            if (h, t) in tool_state:
                if tool_state[(h, t)] == "OK":
                    ok.add(h)
                continue
            vals = {str(v).strip() for v in calls[m, j]}
            if vals - UNAVAILABLE_STATES:
                ok.add(h)
        crit_ok[t] = ok
        crit_fail[t] = [h for h in isolates if h not in ok]

    complete = np.array([all(h in crit_ok[t] for t in CRITICAL_TOOLS) for h in g])
    n_complete_iso = len({h for h in isolates if all(h in crit_ok[t] for t in CRITICAL_TOOLS)})
    coverage = n_complete_iso / N_PRESPECIFIED_ISOLATES
    gate_met = coverage >= CRITICAL_COVERAGE_MIN
    any_crit_failure = n_complete_iso < len(isolates)

    RES = {"threshold_v12": V12_THRESHOLD, "threshold_v11": V11_THRESHOLD,
           "threshold_v11_high_confidence": V11_HIGH,
           "model_sha256": sha(a.model), "script_sha256": sha(os.path.abspath(__file__)),
           "n_isolates": int(len(set(g))), "n_resolved_contigs": int(len(y)),
           "no_refitting": True, "no_threshold_search": True}

    RES["completeness_gate"] = {
        "critical_tools": CRITICAL_TOOLS,
        "rationale": ("PlaScope absence takes v1.2-General recall from 0.7764 to 0.2013 on the "
                      "development cohort, below the 0.50 primary floor"),
        "n_prespecified_isolates": N_PRESPECIFIED_ISOLATES,
        "n_isolates_present": len(isolates),
        "n_isolates_complete_critical_panel": n_complete_iso,
        "critical_coverage": coverage,
        "critical_coverage_min": CRITICAL_COVERAGE_MIN,
        "gate_met": bool(gate_met),
        "critical_failures_by_tool": {t: crit_fail[t] for t in CRITICAL_TOOLS},
        "n_contigs_affected_by_critical_failure": int((~complete).sum()),
        "permitted_trained_failure_states": {k: sorted(v) for k, v in
                                             PERMITTED_TRAINED_FAILURE_STATES.items()},
        "reported_independently_of_truth": True,
        "preflight_receipt": a.preflight_receipt,
        "preflight_receipt_sha256": (sha(a.preflight_receipt)
                                     if a.preflight_receipt and os.path.exists(a.preflight_receipt)
                                     else None)}

    # Panel health for every tool, truth-independent.
    panel = []
    for j, t in enumerate(TOOL_ORDER):
        nf = nm = 0
        iso_unavail = []
        for h in isolates:
            m = g == h
            vals = {str(v).strip() for v in calls[m, j]}
            nf += int("FAILED" in vals); nm += int("MISSING" in vals)
            if not (vals - UNAVAILABLE_STATES):
                iso_unavail.append(h)
        panel.append({"tool": t, "critical": t in CRITICAL_TOOLS,
                      "n_isolates_with_any_FAILED": nf, "n_isolates_with_any_MISSING": nm,
                      "n_isolates_unavailable": len(iso_unavail),
                      "isolates_unavailable": iso_unavail,
                      "permitted_trained_failure_state": t in PERMITTED_TRAINED_FAILURE_STATES})
    RES["panel_health"] = panel

    # ================================================================ A. PRIMARY CONFIRMATORY
    # Evaluated over the COMPLETE-CRITICAL-PANEL isolates only. Isolates whose critical tool failed
    # are preserved and reported, never discarded or relabelled, and appear in the A2 sensitivity
    # analysis below.
    cp2 = complete
    mA = mets(y[cp2], c12[cp2]); bA = boot(y[cp2], g[cp2], c12[cp2]) if cp2.sum() else None
    passed = (gate_met and mA["PPV"] is not None and mA["PPV"] >= PRIMARY_PPV_FLOOR
              and mA["recall"] is not None and mA["recall"] > PRIMARY_RECALL_FLOOR)
    if not gate_met:
        verdict = "OPERATIONALLY INCONCLUSIVE"
    else:
        verdict = "PASS" if passed else "FAIL"
    RES["A_primary_confirmatory"] = {
        "population": ("CP2 - all truth-resolved contigs >= 1 kb, complete-critical-panel "
                       "isolates only"),
        "model": "v1.2-General",
        "threshold": V12_THRESHOLD, "metrics": mA, "bootstrap": bA,
        "pass_rule": "PPV >= %.2f AND recall > %.2f" % (PRIMARY_PPV_FLOOR, PRIMARY_RECALL_FLOOR),
        "completeness_gate_met": bool(gate_met),
        "PPV_met": bool(mA["PPV"] is not None and mA["PPV"] >= PRIMARY_PPV_FLOOR),
        "recall_met": bool(mA["recall"] is not None and mA["recall"] > PRIMARY_RECALL_FLOOR),
        "VERDICT": verdict, "gating": True,
        "inconclusive_rule": ("critical-tool coverage below %.0f%% of the %d prespecified isolates "
                              "makes the run OPERATIONALLY INCONCLUSIVE: the frozen operating point "
                              "was never fairly tested, so the result is neither PASS nor FAIL"
                              % (CRITICAL_COVERAGE_MIN * 100, N_PRESPECIFIED_ISOLATES))}

    # ---------------- A2. failure-inclusive sensitivity analysis
    if any_crit_failure:
        mA2 = mets(y, c12)
        RES["A2_failure_inclusive_sensitivity"] = {
            "population": "CP2 including critical-tool-failed isolates",
            "metrics": mA2, "bootstrap": boot(y, g, c12),
            "n_isolates_included": len(isolates),
            "n_isolates_with_critical_failure": len(isolates) - n_complete_iso,
            "gating": False,
            "note": ("Reported alongside the primary, never in place of it. Isolates whose "
                     "critical tool failed are scored here on an incomplete panel, which the "
                     "frozen operating point was not characterised for.")}
    else:
        RES["A2_failure_inclusive_sensitivity"] = {
            "not_applicable": "no critical-tool failure occurred"}

    # ================================================================ B. KEY SECONDARY
    argok = arg & ann_ok          # CP1 membership requires the annotation to have succeeded
    mB = mets(y[argok], c11[argok]); mBh = mets(y[argok], c11h[argok])
    RES["B_key_secondary"] = {
        "population": "CP1 - truth-resolved core-ARG-bearing contigs >= 1 kb", "model": "v1.1",
        "at_standard_threshold": {"threshold": V11_THRESHOLD, "metrics": mB,
                                  "bootstrap": boot(y[argok], g[argok], c11[argok])},
        "at_high_confidence_threshold": {"threshold": V11_HIGH, "metrics": mBh,
                                         "bootstrap": boot(y[argok], g[argok], c11h[argok])},
        "excluded_annotation_failed": int((arg & ~ann_ok).sum()),
        "gating": False,
        "note": "Reported as observed. This analysis does not gate the primary verdict."}

    # ================================================================ C. ROUTED DEPLOYMENT
    routed = np.where(arg, c11, c12)
    model_used = np.where(arg, "v1.1", "v1.2-General")
    model_used = np.where(ann_ok, model_used, "routing_abstain")
    n_abstain = int((~ann_ok).sum())
    RES["routing_coverage"] = {
        "n_contigs": int(len(y)),
        "n_routed_v1.1": int((model_used == "v1.1").sum()),
        "n_routed_v1.2_general": int((model_used == "v1.2-General").sum()),
        "n_routing_abstain": n_abstain,
        "abstain_fraction": n_abstain / len(y) if len(y) else None,
        "note": "abstentions are excluded from routed metrics and reported separately"}
    L = np.array([numeric(r.get("length")) for r in R])
    circ = np.array([numeric(r.get("circular")) for r in R])
    deg = np.array([numeric(r.get("gfa_degree")) for r in R])
    STRATA = [("overall", ann_ok),
              ("CP1_arg_bearing", arg & ann_ok), ("CP2_non_arg", (~arg) & ann_ok),
              ("length_1-10kb", (L >= 1000) & (L < 10000) & ann_ok),
              ("length_10-50kb", (L >= 10000) & (L < 50000) & ann_ok),
              ("length_>=50kb", (L >= 50000) & ann_ok),
              ("circular", (circ == 1) & ann_ok), ("linear", (circ == 0) & ann_ok),
              ("gfa_isolated_deg0", (deg == 0) & ann_ok),
              ("gfa_connected_deg>0", (deg > 0) & ann_ok)]
    strat = []
    for name, m in STRATA:
        if m.sum() == 0:
            strat.append({"stratum": name, "n": 0, "note": "empty in this cohort"})
            continue
        d = {"stratum": name}
        d.update(mets(y[m], routed[m]))
        d["note"] = ""
        d["n_routed_v1.1"] = int((model_used[m] == "v1.1").sum())
        d["n_routed_v1.2"] = int((model_used[m] == "v1.2-General").sum())
        d["n_routing_abstain"] = int((model_used[m] == "routing_abstain").sum())
        strat.append(d)
    # The abstained contigs are reported as a COUNT ONLY. They carry no routed class, so no PPV or
    # recall is defined for them; emitting one would invent a decision the router declined to make.
    ab = ~ann_ok
    strat.append({"stratum": "routing_abstain", "n": int(ab.sum()),
                  "n_plasmid": int(y[ab].sum()),
                  "TP": None, "FP": None, "TN": None, "FN": None,
                  "PPV": None, "recall": None, "specificity": None,
                  "n_routed_v1.1": 0, "n_routed_v1.2": 0,
                  "n_routing_abstain": int(ab.sum()),
                  "note": "no routed class issued; metrics undefined by construction"})
    RES["C_routed_deployment"] = {
        "routing_rule": ("core_arg_present -> v1.1; core_arg_absent -> v1.2-General; "
                         "annotation_failed or annotation_missing -> routing_abstain"),
        "scores_pooled": False, "strata": strat, "gating": False}

    # ---- per-contig record, full provenance
    perp = os.path.join(a.out, "P1.11_routed_predictions.tsv")
    with open(perp, "w", newline="", encoding="utf-8") as f:
        cols = (["sample", "contig_id", "truth_bin", "ARG_bearing_bool", "routed_class",
                 "model_selected", "routing_reason", "v11_score", "v11_class",
                 "v12_probability", "v12_class", "length", "circular", "gfa_degree"]
                + ["call_" + t for t in TOOL_ORDER]
                + ["n_tools_failed", "n_tools_missing", "annotation_state"])
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader()
        for i, r in enumerate(R):
            tc = {t: calls[i][j] for j, t in enumerate(TOOL_ORDER)}
            rec = {"sample": r["sample"], "contig_id": r.get("contig_id", ""),
                   "truth_bin": int(y[i]), "ARG_bearing_bool": bool(arg[i]),
                   "routed_class": (RT.ROUTING_ABSTAIN if not ann_ok[i] else
                                    (RT.classify_v11(v11[i]) if arg[i]
                                     else RT.classify_v12(p12[i]))),
                   "model_selected": model_used[i],
                   "routing_reason": ("annotation_failed_routing_abstain" if not ann_ok[i]
                                      else ("core_arg_present" if arg[i] else "core_arg_absent")),
                   "v11_score": v11[i], "v11_class": RT.classify_v11(v11[i]),
                   "v12_probability": p12[i], "v12_class": RT.classify_v12(p12[i]),
                   "length": r.get("length", ""), "circular": r.get("circular", ""),
                   "gfa_degree": r.get("gfa_degree", ""),
                   "n_tools_failed": sum(1 for t in TOOL_ORDER if tc[t] == "FAILED"),
                   "n_tools_missing": sum(1 for t in TOOL_ORDER if tc[t] == "MISSING"),
                   "annotation_state": r.get("annotation_state", "ok")}
            for t in TOOL_ORDER:
                rec["call_" + t] = tc[t]
            w.writerow(rec)

    json.dump(RES, open(os.path.join(a.out, "P1.11_evaluation_results.json"), "w"), indent=1)

    print("P1.11 EVALUATION - frozen models, no refitting, no threshold search")
    print("  isolates=%d  resolved contigs=%d" % (RES["n_isolates"], RES["n_resolved_contigs"]))
    cg = RES["completeness_gate"]
    print("\n0. COMPLETENESS GATE - critical tools: %s" % ", ".join(CRITICAL_TOOLS))
    print("   complete-critical-panel isolates: %d / %d prespecified = %.1f%% (minimum %.0f%%)"
          % (cg["n_isolates_complete_critical_panel"], cg["n_prespecified_isolates"],
             100 * cg["critical_coverage"], 100 * cg["critical_coverage_min"]))
    print("   contigs affected by critical failure: %d"
          % cg["n_contigs_affected_by_critical_failure"])
    for t in CRITICAL_TOOLS:
        f = cg["critical_failures_by_tool"][t]
        print("   %s unavailable on %d isolate(s)%s"
              % (t, len(f), (": " + ", ".join(f[:8])) if f else ""))
    print("   GATE: %s" % ("MET" if cg["gate_met"] else "NOT MET -> OPERATIONALLY INCONCLUSIVE"))
    print("\nA. PRIMARY CONFIRMATORY (gating) - v1.2-General, CP2, threshold %.4f" % V12_THRESHOLD)
    print("   PPV    = %s   [%s]  (floor %.2f)  %s"
          % (fmt(mA["PPV"]), ci(bA["PPV_ci95"]), PRIMARY_PPV_FLOOR,
             "MET" if RES["A_primary_confirmatory"]["PPV_met"] else "NOT MET"))
    print("   recall = %s   [%s]  (floor >%.2f) %s"
          % (fmt(mA["recall"]), ci(bA["recall_ci95"]), PRIMARY_RECALL_FLOOR,
             "MET" if RES["A_primary_confirmatory"]["recall_met"] else "NOT MET"))
    print("   VERDICT: %s" % RES["A_primary_confirmatory"]["VERDICT"])
    a2 = RES["A2_failure_inclusive_sensitivity"]
    if "metrics" in a2:
        print("\nA2. FAILURE-INCLUSIVE SENSITIVITY (non-gating, %d isolate(s) with critical failure)"
              % a2["n_isolates_with_critical_failure"])
        print("   PPV = %s   recall = %s" % (fmt(a2["metrics"]["PPV"]), fmt(a2["metrics"]["recall"])))
    print("\nB. KEY SECONDARY (non-gating) - v1.1, CP1")
    print("   @%.4f  PPV=%s recall=%s" % (V11_THRESHOLD, fmt(mB["PPV"]), fmt(mB["recall"])))
    print("   @%.4f  PPV=%s recall=%s" % (V11_HIGH, fmt(mBh["PPV"]), fmt(mBh["recall"])))
    print("\nC. ROUTED DEPLOYMENT (non-gating)")
    rc = RES["routing_coverage"]
    print("   routing coverage: v1.1 %d, v1.2-General %d, ABSTAIN %d (%.2f%% of resolved contigs)"
          % (rc["n_routed_v1.1"], rc["n_routed_v1.2_general"], rc["n_routing_abstain"],
             100.0 * (rc["abstain_fraction"] or 0.0)))
    for d in strat:
        if d.get("n", 0) == 0:
            print("   %-22s empty" % d["stratum"]); continue
        if d["PPV"] is None and d["recall"] is None:
            print("   %-22s n=%-5d pos=%-4d %s" % (d["stratum"], d["n"], d["n_plasmid"], d["note"]))
            continue
        print("   %-22s n=%-5d pos=%-4d PPV=%s recall=%s  (v1.1 %d / v1.2 %d / abstain %d)"
              % (d["stratum"], d["n"], d["n_plasmid"], fmt(d["PPV"]), fmt(d["recall"]),
                 d["n_routed_v1.1"], d["n_routed_v1.2"], d["n_routing_abstain"]))
    print("\nwrote %s" % a.out)


def fmt(v):
    return "%.4f" % v if v is not None else "  n/a "


def ci(v):
    return "%.4f, %.4f" % (v[0], v[1]) if v and v[0] is not None else "n/a"


if __name__ == "__main__":
    main()

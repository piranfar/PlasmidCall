#!/usr/bin/env python3
"""LOCKED P1.11 evaluation script, v3 - SELECTIVE CLASSIFIER.

Supersedes evaluate_p111_locked_v2.py, which is PRESERVED UNCHANGED. Issued before prediction
freeze and before truth acquisition, under
docs/plans/P1.11_SELECTIVE_CLASSIFICATION_ADDENDUM.yaml.

PlasmidCall is evaluated as a SELECTIVE CLASSIFIER. When a required model score is unavailable the
model issues no classification at all - neither plasmid nor chromosome. Those rows are excluded
from the PPV and recall denominators. This is the DECLARED ESTIMAND for a selective prediction
system, not an adjustment applied to a full-coverage estimand:

    selective_PPV    = TP / (TP + FP)
    selective_recall = TP / (TP + FN)

with TP, FP, TN and FN defined ONLY among rows on which that model issued a valid score. Because a
selective classifier can otherwise meet a target by declining to predict, coverage and abstention
are CO-REPORTED operational quantities and are subject to a separately frozen coverage gate.

Unchanged from v2: estimator, coefficients, feature encoding, thresholds (0.9285 / 0.9524 /
0.9605), endpoints, PASS/FAIL rules, populations, bootstrap seed, strata definitions, the
critical-tool gate.

v2 header follows.

LOCKED P1.11 evaluation script, v2 - FAIL-CLOSED CORRECTION.

Supersedes scripts/p1_12/evaluate_p111_locked.py
(sha256 a3fd13242349af8b851a58507ecb3f5a1e0ba2fa5e05d8c668c44446303c596d), which is PRESERVED
UNCHANGED. Issued after panel inference began and BEFORE prediction freeze, truth acquisition,
truth mapping, joining or scoring. See docs/plans/P1.11_PROVENANCE_AND_FAILCLOSED_CORRECTION.yaml.

Corrections, both fail-closed:
  C  an unavailable model score (absent / empty / non-numeric / NaN / infinite) is no longer
     silently compared with >= and turned into a NEGATIVE prediction. It becomes an explicit
     `model_abstain`, is excluded from that model's TP/FP/TN/FN, is counted with its own
     denominator, and is retained in the failure-inclusive view.
  D  `annotation_state` is REQUIRED in the input schema with a validated vocabulary. The previous
     permissive default silently treated every contig as annotated, so routing_abstain could
     never fire.

Unchanged: estimator, coefficients, feature encoding, thresholds (0.9285 / 0.9524 / 0.9605),
endpoints, PASS/FAIL rules, populations, bootstrap seed, strata definitions.

Original header follows.

LOCKED P1.11 evaluation script. Written and hashed BEFORE any P1.11 outcome is observed.

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

# ---------------------------------------------------------------- fail-closed schema (Decision D)
# The vocabulary the P1.11 contig table must emit for annotation_state. Anything outside it is a
# hard error: an unrecognised state must never be silently coerced to "annotated successfully".
ANNOTATION_STATE_OK = {"ok", "annotated", "success", "succeeded"}
ANNOTATION_STATE_UNAVAILABLE = {"annotation_failed", "annotation_missing", "failed", "missing",
                                "unavailable", "error"}
ANNOTATION_STATE_VOCAB = ANNOTATION_STATE_OK | ANNOTATION_STATE_UNAVAILABLE

# ---------------------------------------------------------------- fail-closed scores (Decision C)
MODEL_ABSTAIN = "model_abstain"

# ---------------------------------------------------------------- selective-classification estimand
SELECTIVE_ESTIMAND = (
    "selective_PPV = TP/(TP+FP) and selective_recall = TP/(TP+FN), with TP/FP/TN/FN defined only "
    "among score-evaluable, truth-eligible contigs. Rows on which the model issued no score carry "
    "no classification and are excluded from both denominators. Coverage and abstention are "
    "co-reported and gated separately.")
LENGTH_STRATA = [("1-10kb", 1000, 10000), ("10-50kb", 10000, 50000), (">=50kb", 50000, None)]


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


def coverage_block(R, g, avail, y=None, reasons=None, species=None, L=None):
    """Every mandated coverage and abstention quantity for one model.

    y is passed only AFTER truth is joined; before that the truth-stratified view is reported as
    pending rather than fabricated.
    """
    n_elig = int(len(R))
    n_eval = int(avail.sum())
    n_abst = int((~avail).sum())
    out = {
        "estimand": SELECTIVE_ESTIMAND,
        "n_truth_eligible": n_elig,
        "n_score_evaluable": n_eval,
        "n_model_abstain": n_abst,
        "coverage": (n_eval / n_elig) if n_elig else None,
        "abstention_rate": (n_abst / n_elig) if n_elig else None,
        "formulae": {"coverage": "n_score_evaluable / n_truth_eligible",
                     "abstention_rate": "n_model_abstain / n_truth_eligible"},
    }

    # ---- by isolate
    per_iso = {}
    for iso in sorted(set(g)):
        m = (g == iso)
        ne, na = int(avail[m].sum()), int((~avail[m]).sum())
        per_iso[iso] = {"n_truth_eligible": int(m.sum()), "n_score_evaluable": ne,
                        "n_model_abstain": na,
                        "coverage": (ne / int(m.sum())) if m.sum() else None}
    out["coverage_by_isolate"] = per_iso
    cov_vals = [v["coverage"] for v in per_iso.values() if v["coverage"] is not None]
    if cov_vals:
        s = sorted(cov_vals)
        out["coverage_by_isolate_distribution"] = {
            "n_isolates": len(s), "min": s[0], "max": s[-1],
            "median": s[len(s) // 2],
            "p05": s[max(0, int(0.05 * len(s)) - 1)],
            "p25": s[max(0, int(0.25 * len(s)) - 1)],
            "mean": sum(s) / len(s)}
    out["n_isolates_zero_coverage"] = sum(1 for v in per_iso.values() if v["n_score_evaluable"] == 0)
    out["n_isolates_partial_coverage"] = sum(
        1 for v in per_iso.values()
        if 0 < v["n_score_evaluable"] < v["n_truth_eligible"])
    out["n_isolates_full_coverage"] = sum(
        1 for v in per_iso.values()
        if v["n_truth_eligible"] and v["n_score_evaluable"] == v["n_truth_eligible"])

    # ---- by species
    if species is not None:
        bysp = {}
        for sp in sorted(set(species)):
            m = (species == sp)
            ne = int(avail[m].sum())
            bysp[str(sp)] = {"n_truth_eligible": int(m.sum()), "n_score_evaluable": ne,
                             "coverage": (ne / int(m.sum())) if m.sum() else None}
        out["coverage_by_species"] = bysp
    else:
        out["coverage_by_species"] = "species not supplied in the contig table"

    # ---- by contig-length stratum
    if L is not None:
        byl = {}
        for name, lo, hi in LENGTH_STRATA:
            m = (L >= lo) if hi is None else ((L >= lo) & (L < hi))
            ne = int(avail[m].sum())
            byl[name] = {"n_truth_eligible": int(m.sum()), "n_score_evaluable": ne,
                         "coverage": (ne / int(m.sum())) if m.sum() else None}
        out["coverage_by_length_stratum"] = byl

    # ---- by truth, only once truth exists
    if y is not None:
        byt = {}
        for lab, v in (("plasmid", 1), ("chromosome", 0)):
            m = (y == v)
            ne = int(avail[m].sum())
            byt[lab] = {"n_truth_eligible": int(m.sum()), "n_score_evaluable": ne,
                        "coverage": (ne / int(m.sum())) if m.sum() else None}
        out["coverage_by_truth"] = byt
    else:
        out["coverage_by_truth"] = "PENDING - reported only after truth is joined"

    # ---- every abstention reason, never pooled
    if reasons is not None:
        tally = {}
        for i, ok in enumerate(avail):
            if not ok:
                r = str(reasons[i]) if reasons[i] else "score_unavailable"
                tally[r] = tally.get(r, 0) + 1
        out["abstention_reasons"] = tally
        out["abstention_reasons_note"] = "reasons are reported individually and never pooled"
    return out


def truthy(x):
    return str(x).strip().lower() in ("true", "1")


def numeric(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def score_available(v):
    """Decision C. True only for a genuinely usable score.

    A valid score BELOW threshold is a real negative and must stay in the confusion matrix.
    An UNAVAILABLE score is not a negative and must not enter it. The two are indistinguishable
    once `np.nan >= t` has quietly evaluated to False, which is the defect this replaces.
    """
    if v is None:
        return False
    s = str(v).strip()
    if s == "" or s.lower() in ("na", "nan", "none", "null", "-"):
        return False
    try:
        f = float(s)
    except (TypeError, ValueError):
        return False
    return bool(np.isfinite(f))


def classify_with_abstain(vals, avail, threshold):
    """Threshold only where the score is available; elsewhere emit MODEL_ABSTAIN.

    Returns (calls, mask) where `calls` is int 0/1 with -1 at abstained positions and `mask`
    selects the rows that may legitimately enter a confusion matrix.
    """
    calls = np.full(len(vals), -1, dtype=int)
    if avail.any():
        calls[avail] = (np.asarray(vals, dtype=float)[avail] >= threshold).astype(int)
    return calls, avail


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
    # Decision C: availability is established BEFORE any comparison, from the raw cell.
    v11_avail = np.array([score_available(r.get("M2_score")) for r in R])
    v11 = np.array([numeric(r.get("M2_score")) for r in R])
    calls = np.array([[r.get(t, "MISSING") or "MISSING" for t in TOOL_ORDER] for r in R], dtype=object)

    # ---- frozen inference. No fitting anywhere in this file.
    # predict() applies missing-tool neutrality: any tool in a state not observed during training
    # has its block imputed to the training means so it contributes exactly zero. Scoring the raw
    # encoding directly would let an absent tool shift the logit by up to ~3 units.
    p12 = predict(B, calls)
    # Decision C, applied to BOTH models. predict() should always yield a finite probability; if it
    # does not, that row abstains rather than silently scoring as a negative.
    v12_avail = np.isfinite(np.asarray(p12, dtype=float))
    c12, _ = classify_with_abstain(p12, v12_avail, V12_THRESHOLD)
    c11, _ = classify_with_abstain(v11, v11_avail, V11_THRESHOLD)
    c11h, _ = classify_with_abstain(v11, v11_avail, V11_HIGH)
    RES_SCORE_AVAILABILITY = {
        "v1.1_M2_score": {"n_total": int(len(R)), "n_available": int(v11_avail.sum()),
                          "n_model_abstain": int((~v11_avail).sum())},
        "v1.2_probability": {"n_total": int(len(R)), "n_available": int(v12_avail.sum()),
                             "n_model_abstain": int((~v12_avail).sum())},
        "rule": ("an absent, empty, non-numeric, NaN or infinite score is model_abstain: excluded "
                 "from that model's TP/FP/TN/FN, counted separately, never a negative call")}

    # Routing. A contig whose ARG annotation failed or was never attempted is ABSTAINED on: it
    # receives no final routed class and is counted separately, never folded into either domain.
    # Decision D. The column is REQUIRED. The previous permissive default read a missing column
    # as "every contig annotated successfully", which silently disabled routing_abstain entirely.
    if not any("annotation_state" in r for r in rows):
        sys.exit("SCHEMA ERROR: the contig table has no 'annotation_state' column. This "
                 "evaluator refuses to run without it, because defaulting it to 'ok' would "
                 "silently route contigs with unavailable ARG annotation to v1.1/v1.2 and report "
                 "zero abstentions. The upstream contig-table builder must emit annotation_state "
                 "per contig, derived from the amrfinder per-sample run state "
                 "(inference/state/amrfinder__<sample>.done|.failed). Permitted vocabulary: %s"
                 % sorted(ANNOTATION_STATE_VOCAB))
    raw_ann = [str(r.get("annotation_state", "")).strip().lower() for r in R]
    blank = [i for i, v in enumerate(raw_ann) if v == ""]
    if blank:
        sys.exit("SCHEMA ERROR: annotation_state is empty on %d of %d rows (first at index %d). "
                 "An empty state is not 'ok'; it is unrecorded. Emit an explicit value from %s."
                 % (len(blank), len(R), blank[0], sorted(ANNOTATION_STATE_VOCAB)))
    unknown = sorted({v for v in raw_ann if v not in ANNOTATION_STATE_VOCAB})
    if unknown:
        sys.exit("SCHEMA ERROR: unrecognised annotation_state value(s) %s. Permitted: %s. An "
                 "unrecognised state is never coerced to 'ok'." % (unknown,
                                                                   sorted(ANNOTATION_STATE_VOCAB)))
    ann_ok = np.array([v in ANNOTATION_STATE_OK for v in raw_ann])

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
    # CP1 membership requires the annotation to have succeeded. Decision C additionally removes
    # rows whose v1.1 score is unavailable: those are reported with their own denominator rather
    # than being scored as negatives.
    argok_all = arg & ann_ok
    argok = argok_all & v11_avail
    mB = mets(y[argok], c11[argok]); mBh = mets(y[argok], c11h[argok])
    RES["B_key_secondary"] = {
        "population": "CP1 - truth-resolved core-ARG-bearing contigs >= 1 kb", "model": "v1.1",
        "at_standard_threshold": {"threshold": V11_THRESHOLD, "metrics": mB,
                                  "bootstrap": boot(y[argok], g[argok], c11[argok])},
        "at_high_confidence_threshold": {"threshold": V11_HIGH, "metrics": mBh,
                                         "bootstrap": boot(y[argok], g[argok], c11h[argok])},
        "excluded_annotation_failed": int((arg & ~ann_ok).sum()),
        "denominators": {
            "n_CP1_after_annotation_filter": int(argok_all.sum()),
            "n_scored": int(argok.sum()),
            "n_model_abstain_v1_1": int((argok_all & ~v11_avail).sum()),
            "rule": ("metrics use n_scored as the denominator; model_abstain rows are excluded "
                     "from TP/FP/TN/FN and reported here, never counted as negatives")},
        "gating": False,
        "note": "Reported as observed. This analysis does not gate the primary verdict."}

    # ================================================================ C. ROUTED DEPLOYMENT
    routed = np.where(arg, c11, c12)
    model_used = np.where(arg, "v1.1", "v1.2-General")
    model_used = np.where(ann_ok, model_used, "routing_abstain")
    # Decision C in the routed system: a contig routed to a model whose score is unavailable
    # carries no class either. It abstains on the MODEL rather than on the ROUTER, and the two
    # reasons are reported separately so they are never conflated.
    routed_score_avail = np.where(arg, v11_avail, v12_avail)
    model_used = np.where(ann_ok & ~routed_score_avail, MODEL_ABSTAIN, model_used)
    scored_mask = ann_ok & routed_score_avail
    n_abstain = int((~ann_ok).sum())
    n_model_abstain = int((ann_ok & ~routed_score_avail).sum())
    RES["score_availability"] = RES_SCORE_AVAILABILITY
    RES["estimand"] = {
        "framework": "selective classification",
        "definition": SELECTIVE_ESTIMAND,
        "primary_quantities": ["selective_PPV", "selective_recall"],
        "note": ("a model that issues no score issues no classification; such rows are outside "
                 "both denominators by construction, which is why coverage is gated separately")}

    _species = None
    if R and any("species" in r or "organism" in r for r in R):
        _species = np.array([str(r.get("species") or r.get("organism") or "") for r in R])
    _reasons = np.array([str(r.get("abstention_reason", "")) for r in R]) if R else None
    # contig length for the length-stratified coverage view; the stratum-building L used by the
    # routed strata is derived identically a few lines below and the two always agree.
    _L = np.array([numeric(r.get("length")) for r in R])

    # ---------------- tool-evidence completeness: SEPARATE from model coverage.
    # A finite v1.2 score does NOT imply the expected tool evidence was available: the locked model
    # maps missing/failed tool blocks to finite predictions by design. Incomplete evidence is
    # therefore reported here and is NEVER reinterpreted as model abstention.
    _UNAVAIL = {"FAILED", "MISSING", ""}
    _tool_avail = {t: np.array([str(calls[i][j]).strip() not in _UNAVAIL
                                for i in range(len(R))]) for j, t in enumerate(TOOL_ORDER)}
    _n_expected = len(R) * len(TOOL_ORDER)
    _n_avail = int(sum(int(v.sum()) for v in _tool_avail.values()))
    _by_tool = {t: {"n_expected": len(R), "n_available": int(v.sum()),
                    "fraction_available": (int(v.sum()) / len(R)) if len(R) else None,
                    "n_FAILED": int(sum(1 for i in range(len(R))
                                        if str(calls[i][TOOL_ORDER.index(t)]).strip() == "FAILED")),
                    "n_MISSING": int(sum(1 for i in range(len(R))
                                         if str(calls[i][TOOL_ORDER.index(t)]).strip() == "MISSING"))}
                for t, v in _tool_avail.items()}
    _per_iso_tools = {}
    for iso in sorted(set(g)):
        m = (g == iso)
        av = int(sum(int(v[m].sum()) for v in _tool_avail.values()))
        exp = int(m.sum()) * len(TOOL_ORDER)
        _per_iso_tools[iso] = {"n_expected": exp, "n_available": av,
                               "fraction_available": (av / exp) if exp else None,
                               "n_tools_fully_available": int(sum(1 for v in _tool_avail.values()
                                                                  if v[m].all()))}
    _crit = np.array([True] * len(R))
    for ct in CRITICAL_TOOLS:
        if ct in _tool_avail:
            _crit = _crit & _tool_avail[ct]
    RES["tool_evidence_completeness"] = {
        "status": ("SEPARATE from model coverage. Reported because a finite model score does not "
                   "imply the expected tool evidence was available."),
        "not_model_abstention": ("incomplete tool evidence is NOT reinterpreted as model "
                                 "abstention while the locked model returns a finite score"),
        "gated_by": ("the PlaScope critical-tool gate and the predeclared tool-completeness "
                     "checks - NOT by the coverage gate"),
        "n_expected_tool_outputs": _n_expected,
        "n_available_tool_outputs": _n_avail,
        "fraction_available_overall": (_n_avail / _n_expected) if _n_expected else None,
        "by_tool": _by_tool,
        "by_isolate": _per_iso_tools,
        "by_critical_tool_stratum": {
            "critical_tools": CRITICAL_TOOLS,
            "n_contigs_with_critical_available": int(_crit.sum()),
            "n_contigs_with_critical_unavailable": int((~_crit).sum()),
            "fraction_critical_available": (int(_crit.sum()) / len(R)) if len(R) else None},
        "by_annotation_state_stratum": {
            st: int(sum(1 for v in raw_ann if v == st)) for st in sorted(set(raw_ann))},
    }

    RES["coverage_and_abstention"] = {
        "v1.2-General": coverage_block(R, g, v12_avail, None, _reasons, _species, _L),
        "v1.1": coverage_block(R, g, v11_avail, None, _reasons, _species, _L),
        "router": {
            "n_truth_eligible": int(len(R)),
            "n_routed": int(scored_mask.sum()),
            "n_routing_abstain": int((~ann_ok).sum()),
            "n_model_abstain": int((ann_ok & ~routed_score_avail).sum()),
            "routed_coverage": (int(scored_mask.sum()) / len(R)) if len(R) else None,
            "note": ("routing abstention (annotation unavailable) and model abstention (score "
                     "unavailable) are separate quantities and are never combined")}}

    # ---------------- deployment yield: DESCRIPTIVE, never a replacement for the primary metrics
    _pos12 = int(((c12 == 1) & v12_avail).sum())
    _pos11 = int(((c11 == 1) & v11_avail).sum())
    _per_iso_pos = {}
    for iso in sorted(set(g)):
        m = (g == iso)
        _per_iso_pos[iso] = {
            "n_contigs": int(m.sum()),
            "n_positive_v1.2": int(((c12 == 1) & v12_avail & m).sum()),
            "n_positive_v1.1": int(((c11 == 1) & v11_avail & m).sum()),
            "positive_call_yield_v1.2": (int(((c12 == 1) & v12_avail & m).sum()) / int(m.sum()))
            if m.sum() else None}
    RES["deployment_yield_secondary"] = {
        "status": "DESCRIPTIVE - does not replace the selective primary metrics",
        "n_eligible_contigs": int(len(R)),
        "fraction_receiving_valid_score": {
            "v1.2-General": (int(v12_avail.sum()) / len(R)) if len(R) else None,
            "v1.1": (int(v11_avail.sum()) / len(R)) if len(R) else None},
        "fraction_receiving_positive_plasmid_call": {
            "v1.2-General": (_pos12 / len(R)) if len(R) else None,
            "v1.1": (_pos11 / len(R)) if len(R) else None},
        "fraction_abstained": {
            "v1.2-General": (int((~v12_avail).sum()) / len(R)) if len(R) else None,
            "v1.1": (int((~v11_avail).sum()) / len(R)) if len(R) else None},
        "positive_call_yield_per_isolate": _per_iso_pos,
        "routed_coverage_after_annotation_failures": {
            "n_routed": int(scored_mask.sum()),
            "n_routing_abstain": int((~ann_ok).sum()),
            "fraction_routed": (int(scored_mask.sum()) / len(R)) if len(R) else None}}
    # Decision C: analyses A and A2 report the v1.2 abstention denominator too, so that
    # TP+FP+TN+FN can always be reconciled against the reported n. Without this, an A-block n could
    # exceed its own confusion-matrix total with nothing saying why.
    for _k in ("A_primary_confirmatory", "A2_failure_inclusive_sensitivity"):
        if isinstance(RES.get(_k), dict) and "not_applicable" not in RES[_k]:
            RES[_k]["denominators"] = {
                "n_model_abstain_v1_2": int((~v12_avail).sum()),
                "rule": ("model_abstain rows carry no v1.2 class and are excluded from "
                         "TP/FP/TN/FN; n may therefore exceed TP+FP+TN+FN by this count")}
    RES["routing_coverage"] = {
        "n_contigs": int(len(y)),
        "n_routed_v1.1": int((model_used == "v1.1").sum()),
        "n_routed_v1.2_general": int((model_used == "v1.2-General").sum()),
        "n_routing_abstain": n_abstain,
        "n_model_abstain": n_model_abstain,
        "abstain_fraction": n_abstain / len(y) if len(y) else None,
        "model_abstain_fraction": n_model_abstain / len(y) if len(y) else None,
        "note": ("router abstentions (annotation unavailable) and model abstentions (score "
                 "unavailable) are both excluded from routed metrics and reported separately; "
                 "neither is ever counted as a negative call")}
    L = np.array([numeric(r.get("length")) for r in R])
    circ = np.array([numeric(r.get("circular")) for r in R])
    deg = np.array([numeric(r.get("gfa_degree")) for r in R])
    # Strata are computed over rows that carry an actual routed class: annotation available AND
    # the routed model's score available. Stratum definitions themselves are unchanged.
    STRATA = [("overall", scored_mask),
              ("CP1_arg_bearing", arg & scored_mask), ("CP2_non_arg", (~arg) & scored_mask),
              ("length_1-10kb", (L >= 1000) & (L < 10000) & scored_mask),
              ("length_10-50kb", (L >= 10000) & (L < 50000) & scored_mask),
              ("length_>=50kb", (L >= 50000) & scored_mask),
              ("circular", (circ == 1) & scored_mask), ("linear", (circ == 0) & scored_mask),
              ("gfa_isolated_deg0", (deg == 0) & scored_mask),
              ("gfa_connected_deg>0", (deg > 0) & scored_mask)]
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
                + ["n_tools_failed", "n_tools_missing", "annotation_state",
                   "v11_score_state", "v12_score_state"])
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader()
        for i, r in enumerate(R):
            tc = {t: calls[i][j] for j, t in enumerate(TOOL_ORDER)}
            rec = {"sample": r["sample"], "contig_id": r.get("contig_id", ""),
                   "truth_bin": int(y[i]), "ARG_bearing_bool": bool(arg[i]),
                   "routed_class": (RT.ROUTING_ABSTAIN if not ann_ok[i]
                                    else MODEL_ABSTAIN if not routed_score_avail[i]
                                    else (RT.classify_v11(v11[i]) if arg[i]
                                          else RT.classify_v12(p12[i]))),
                   "model_selected": model_used[i],
                   "routing_reason": ("annotation_unavailable_routing_abstain" if not ann_ok[i]
                                      else "score_unavailable_model_abstain"
                                      if not routed_score_avail[i]
                                      else ("core_arg_present" if arg[i]
                                            else "core_arg_absent")),
                   "v11_score": (v11[i] if v11_avail[i] else ""),
                   "v11_class": (RT.classify_v11(v11[i]) if v11_avail[i] else MODEL_ABSTAIN),
                   "v12_probability": (p12[i] if v12_avail[i] else ""),
                   "v12_class": (RT.classify_v12(p12[i]) if v12_avail[i] else MODEL_ABSTAIN),
                   "length": r.get("length", ""), "circular": r.get("circular", ""),
                   "gfa_degree": r.get("gfa_degree", ""),
                   "n_tools_failed": sum(1 for t in TOOL_ORDER if tc[t] == "FAILED"),
                   "n_tools_missing": sum(1 for t in TOOL_ORDER if tc[t] == "MISSING"),
                   "annotation_state": raw_ann[i],
                   "v11_score_state": ("available" if v11_avail[i] else MODEL_ABSTAIN),
                   "v12_score_state": ("available" if v12_avail[i] else MODEL_ABSTAIN)}
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

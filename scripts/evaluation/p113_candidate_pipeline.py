#!/usr/bin/env python3
"""P1.13 (derived from the frozen P1.11 pipeline by name substitution only) - build, score and gate the P1.13 candidate predictions. TRUTH-BLIND.

Runs the LOCKED production components in order and stops at the coverage gate. It never creates
PREDICTIONS_FROZEN.json, never acquires truth, and never performs the prediction-to-truth join.

  1  build the contig table with the locked builder (pass 1, no v1.1 scores)
  2  score v1.1 with the persisted, equivalence-validated estimator
  3  rebuild with v1.1 scores injected -> the candidate contig table
  4  apply the frozen coverage gate
  5  determinism check: rebuild and compare checksums
  6  emit a CANDIDATE_ONLY_NOT_FROZEN manifest

Usage:
  p111_candidate_pipeline.py --root DIR --outdir DIR
"""
import argparse
import csv
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

# ---------------------------------------------------------------- FROZEN coverage gate
GATE = {
    "v1.2-General": {"overall": 0.99, "per_isolate": 0.95},
    "v1.1": {"overall": 0.95, "per_isolate": 0.90},
    "router": {"routed": 0.95},
    "isolates_with_zero_coverage_max": 0,
}
GATE_SOURCE = "docs/plans/P1.11_SELECTIVE_CLASSIFICATION_ADDENDUM.yaml (coverage_gate, FROZEN)"


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_lf(p):
    return hashlib.sha256(open(p, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def run(cmd, label):
    cp = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    print("  [%s] exit=%d" % (label, cp.returncode))
    if cp.returncode != 0:
        print((cp.stdout or "")[-1500:])
        print((cp.stderr or "")[-1500:])
    return cp


def coverage_from_table(rows):
    """Model coverage and tool-evidence completeness, computed from the candidate table itself."""
    import collections
    TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
             "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
    UNAVAIL = {"FAILED", "MISSING", ""}
    elig = [r for r in rows if int(float(r["contig_length"])) >= 1000]
    out = {"n_all_contigs": len(rows), "n_eligible_ge_1kb": len(elig)}

    def block(state_col):
        per = collections.defaultdict(lambda: [0, 0])
        na = 0
        for r in elig:
            s = r["sample"]
            per[s][0] += 1
            if r[state_col] == "available":
                per[s][1] += 1
                na += 1
        cov = {s: (v[1] / v[0]) if v[0] else None for s, v in per.items()}
        vals = sorted(v for v in cov.values() if v is not None)
        return {"n_eligible": len(elig), "n_score_evaluable": na,
                "n_model_abstain": len(elig) - na,
                "coverage": (na / len(elig)) if elig else None,
                "abstention_rate": ((len(elig) - na) / len(elig)) if elig else None,
                "per_isolate_coverage": cov,
                "min_per_isolate": vals[0] if vals else None,
                "median_per_isolate": vals[len(vals) // 2] if vals else None,
                "n_isolates": len(cov),
                "n_isolates_zero_coverage": sum(1 for v in cov.values() if v == 0),
                "n_isolates_below_0_95": sum(1 for v in cov.values() if v is not None and v < 0.95),
                "n_isolates_below_0_90": sum(1 for v in cov.values() if v is not None and v < 0.90)}

    out["model_coverage"] = {"v1.2-General": block("v12_score_state"),
                             "v1.1": block("v11_score_state")}
    routed = sum(1 for r in elig if r["router_state"] == "routed")
    out["router"] = {"n_eligible": len(elig), "n_routed": routed,
                     "n_routing_abstain": len(elig) - routed,
                     "routed_coverage": (routed / len(elig)) if elig else None}

    # ---- tool-evidence completeness: a SEPARATE quantity from model coverage
    per_tool, per_iso = {}, collections.defaultdict(lambda: [0, 0])
    for t in TOOLS:
        av = sum(1 for r in elig if str(r[t]).strip() not in UNAVAIL)
        per_tool[t] = {"n_expected": len(elig), "n_available": av,
                       "fraction_available": (av / len(elig)) if elig else None,
                       "n_FAILED": sum(1 for r in elig if str(r[t]).strip() == "FAILED"),
                       "n_MISSING": sum(1 for r in elig if str(r[t]).strip() == "MISSING")}
    for r in elig:
        per_iso[r["sample"]][0] += len(TOOLS)
        per_iso[r["sample"]][1] += sum(1 for t in TOOLS if str(r[t]).strip() not in UNAVAIL)
    n_exp = len(elig) * len(TOOLS)
    n_av = sum(v["n_available"] for v in per_tool.values())
    out["tool_evidence_completeness"] = {
        "note": ("SEPARATE from model coverage. A finite model score does not imply the expected "
                 "tool evidence was available."),
        "n_expected": n_exp, "n_available": n_av,
        "fraction_available": (n_av / n_exp) if n_exp else None,
        "by_tool": per_tool,
        "by_isolate": {s: {"n_expected": v[0], "n_available": v[1],
                           "fraction_available": (v[1] / v[0]) if v[0] else None}
                       for s, v in per_iso.items()}}
    out["annotation_state_distribution"] = dict(
        collections.Counter(r["annotation_state"] for r in elig))
    out["ARG_bearing_bool_distribution"] = dict(
        collections.Counter(str(r["ARG_bearing_bool"]) for r in elig))
    out["abstention_reasons"] = dict(
        collections.Counter(r["abstention_reason"] for r in elig if r["abstention_reason"]))
    out["router_call_distribution"] = dict(
        collections.Counter(r["router_call"] for r in elig))
    out["v12_call_distribution"] = dict(collections.Counter(r["v12_call"] for r in elig))
    out["v11_call_distribution"] = dict(collections.Counter(r["v11_call"] for r in elig))
    return out


def apply_gate(cov):
    res, failures = {}, []
    for m in ("v1.2-General", "v1.1"):
        b = cov["model_coverage"][m]
        g = GATE[m]
        okO = b["coverage"] is not None and b["coverage"] >= g["overall"]
        below = sum(1 for v in b["per_isolate_coverage"].values()
                    if v is not None and v < g["per_isolate"])
        okI = below == 0
        res[m] = {"overall_coverage": b["coverage"], "overall_min": g["overall"],
                  "overall_pass": okO,
                  "min_per_isolate": b["min_per_isolate"], "per_isolate_min": g["per_isolate"],
                  "n_isolates_below_min": below, "per_isolate_pass": okI,
                  "n_isolates_zero_coverage": b["n_isolates_zero_coverage"],
                  "zero_coverage_pass": b["n_isolates_zero_coverage"] <= GATE[
                      "isolates_with_zero_coverage_max"],
                  "verdict": "PASS" if (okO and okI and b["n_isolates_zero_coverage"] == 0)
                             else "COVERAGE-INCONCLUSIVE"}
        if res[m]["verdict"] != "PASS":
            failures.append(m)
    rb = cov["router"]
    okr = rb["routed_coverage"] is not None and rb["routed_coverage"] >= GATE["router"]["routed"]
    res["router"] = {"routed_coverage": rb["routed_coverage"],
                     "routed_min": GATE["router"]["routed"],
                     "verdict": "PASS" if okr else "COVERAGE-INCONCLUSIVE"}
    if not okr:
        failures.append("router")
    res["overall_verdict"] = "PASS" if not failures else "COVERAGE-INCONCLUSIVE"
    res["failed_gates"] = failures
    res["gate_source"] = GATE_SOURCE
    res["thresholds_applied"] = GATE
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    MODEL12 = os.path.join(REPO, "models", "plasmidcall_v1.2-general",
                           "plasmidcall_v1_2_general.pkl")
    MODEL11 = os.path.join(REPO, "models", "plasmidcall_v1.1", "plasmidcall_v1_1_m2.pkl")
    t1 = os.path.join(a.outdir, "pass1_contig_table.tsv")
    v11 = os.path.join(a.outdir, "P1.13_v11_scores.tsv")
    final = os.path.join(a.outdir, "P1.13_candidate_contig_table.tsv")
    valj = os.path.join(a.outdir, "P1.13_builder_validation.json")

    print("STEP 1  build (pass 1, no v1.1 scores)")
    run([sys.executable, "build_p113_contig_table.py", "--root", a.root, "--out", t1,
         "--model", MODEL12, "--validation-out", valj], "build-1")

    print("STEP 2  score v1.1 with the persisted estimator")
    run([sys.executable, "v11_scorer_p111.py", "score", "--model", MODEL11,
         "--contig-table", t1, "--out", v11], "v11-score")

    print("STEP 3  rebuild with v1.1 injected -> candidate table")
    run([sys.executable, "build_p113_contig_table.py", "--root", a.root, "--out", final,
         "--model", MODEL12, "--v11-scores", v11, "--validation-out", valj], "build-2")

    rows = list(csv.DictReader(io.open(final, encoding="utf-8"), delimiter="\t"))
    print("  candidate table: %d rows" % len(rows))

    print("STEP 4  coverage and the frozen gate")
    cov = coverage_from_table(rows)
    gate = apply_gate(cov)
    for m in ("v1.2-General", "v1.1"):
        r = gate[m]
        print("  %-14s coverage=%.4f (min %.2f)  min/iso=%.4f (min %.2f)  below=%d  -> %s"
              % (m, r["overall_coverage"] or 0, r["overall_min"], r["min_per_isolate"] or 0,
                 r["per_isolate_min"], r["n_isolates_below_min"], r["verdict"]))
    print("  %-14s routed=%.4f (min %.2f) -> %s"
          % ("router", gate["router"]["routed_coverage"] or 0, gate["router"]["routed_min"],
             gate["router"]["verdict"]))
    print("  OVERALL: %s" % gate["overall_verdict"])

    print("STEP 5  determinism")
    t3 = os.path.join(a.outdir, "_determinism_rebuild.tsv")
    run([sys.executable, "build_p113_contig_table.py", "--root", a.root, "--out", t3,
         "--model", MODEL12, "--v11-scores", v11], "build-3")
    det = (sha(final) == sha(t3))
    print("  rebuild identical: %s" % det)
    if os.path.exists(t3):
        os.remove(t3)

    print("STEP 6  candidate manifest")
    man = {
        "manifest": "P1.13 prediction-freeze candidate",
        "status": "CANDIDATE_ONLY_NOT_FROZEN",
        "not_frozen_statement": ("PREDICTIONS_FROZEN.json has NOT been created. No truth has been "
                                 "acquired, joined or scored. This manifest is a proposal awaiting "
                                 "explicit owner approval."),
        "generated_utc": utc(),
        "counts": {"n_all_contigs": cov["n_all_contigs"],
                   "n_eligible_ge_1kb": cov["n_eligible_ge_1kb"],
                   "n_isolates": cov["model_coverage"]["v1.2-General"]["n_isolates"]},
        "coverage_gate": gate,
        "model_coverage": {m: {k: v for k, v in cov["model_coverage"][m].items()
                               if k != "per_isolate_coverage"}
                           for m in cov["model_coverage"]},
        "tool_evidence_completeness": cov["tool_evidence_completeness"],
        "annotation_state_distribution": cov["annotation_state_distribution"],
        "ARG_bearing_bool_distribution": cov["ARG_bearing_bool_distribution"],
        "abstention_reasons": cov["abstention_reasons"],
        "call_distributions": {"v1.2-General": cov["v12_call_distribution"],
                               "v1.1": cov["v11_call_distribution"],
                               "router": cov["router_call_distribution"]},
        "deterministic_rebuild_identical": det,
        "checksums": {
            "candidate_contig_table": sha(final),
            "v11_scores": sha(v11),
            "builder": sha_lf(os.path.join(HERE, "build_p113_contig_table.py")),
            "v11_scorer": sha_lf(os.path.join(HERE, "v11_scorer_p111.py")),
            "v11_estimator": sha(MODEL11),
            "v12_estimator": sha(MODEL12),
            "evaluator_v3": sha_lf(os.path.join(HERE, "evaluate_p111_locked_v3.py")),
            "router": sha_lf(os.path.join(HERE, "plasmidcall_router.py")),
            "encoding_freeze_v12": sha_lf(os.path.join(HERE, "freeze_v12.py")),
            "addendum": sha_lf(os.path.join(REPO, "docs", "plans",
                                            "P1.11_SELECTIVE_CLASSIFICATION_ADDENDUM.yaml")),
            "cohort_v3": "874b0924deffef948dd50e00ee5c77c91d773354de4a1bb936162e4fec294205",
        },
        "thresholds": {"v1.2-General": 0.9285, "v1.1_standard": 0.9524,
                       "v1.1_high_confidence": 0.9605},
        "software": {"python": platform.python_version(), "platform": platform.platform()},
        "truth_state": {"PREDICTIONS_FROZEN_json": "ABSENT",
                        "truth_acquired": False, "truth_joined": False, "truth_scored": False},
    }
    try:
        import sklearn, numpy, pandas
        man["software"].update({"sklearn": sklearn.__version__, "numpy": numpy.__version__,
                                "pandas": pandas.__version__})
    except Exception:
        pass
    mp = os.path.join(a.outdir, "P1.13_PREDICTION_FREEZE_CANDIDATE_MANIFEST.json")
    with open(mp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, indent=1)
        f.write("\n")
    json.dump(cov, open(os.path.join(a.outdir, "P1.11_coverage_report.json"), "w",
                        encoding="utf-8"), indent=1)
    print("  manifest: %s" % mp)
    print("  manifest sha256: %s" % sha(mp))
    print("  candidate table sha256: %s" % sha(final))
    sys.exit(0 if gate["overall_verdict"] == "PASS" else 4)


if __name__ == "__main__":
    main()

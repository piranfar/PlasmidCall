#!/usr/bin/env python3
"""P1.13 PREDICTION FREEZE - atomic, fail-closed. Derived from the frozen P1.11 freezer;
the gate, augmentation, projection check and atomic-commit logic are unchanged. Bindings,
names and expected counts are those of P1.13. The derivation diff is captured alongside.

Freezes ONE approved candidate, identified by checksum. It regenerates nothing, substitutes
nothing and modifies no component. Every referenced artefact must exist and match its recorded
checksum before PREDICTIONS_FROZEN.json is created; any mismatch aborts before anything is written.

It does NOT acquire, construct, inspect, copy or join P1.11 truth, and it never invokes
acquire_truth_v2.py or the freeze-to-truth chain.

Usage:
  p111_freeze_predictions.py --candidate-dir DIR --root DIR --out DIR [--commit]
Without --commit it performs a full dry run and writes nothing.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import io
import json
import os
import platform
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# ---------------------------------------------------------------- the APPROVED candidate
APPROVED = {
    "normalised_call_table": "e3e43a0269336f2e88a670ef1b226d5ed56e616557e72ece0e41d873ffb4f48f",
    "candidate_contig_table": "440f16bc7002c15135ac73a233545613ad6869eddf7d421cca6dc0a1060114f8",
    "candidate_manifest": "bbe15fc247163c604ca55135ab3d8031a57aa1ae62f6451794a269591e135708",
}
FREEZE_ID = "P1.13-PREDICTION-FREEZE-001"

V12_T, V11_T, V11_HIGH = 0.9285, 0.9524, 0.9605
TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
         "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
UNAVAIL = {"FAILED", "MISSING", ""}

TRUTH_ACCESS_STATEMENT = ("P1.13 truth has not been acquired, constructed, inspected, joined "
                          "or scored by any P1.13 step.")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def sha_lf(p):
    return hashlib.sha256(open(p, "rb").read().replace(b"\r\n", b"\n")).hexdigest()


def die(msg):
    sys.exit("FREEZE ABORTED (fail-closed): %s" % msg)


def num(x):
    try:
        v = float(x)
        return v if v == v and abs(v) != float("inf") else None
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-dir", required=True)
    ap.add_argument("--root", required=True, help="builder input root (assemblies, call table)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--commit", action="store_true")
    a = ap.parse_args()

    cand = os.path.join(a.candidate_dir, "P1.13_candidate_contig_table.tsv")
    manf = os.path.join(a.candidate_dir, "P1.13_PREDICTION_FREEZE_CANDIDATE_MANIFEST.json")
    call = os.path.join(a.root, "inference", "P1.13_predictions_normalised.tsv")

    # ============================================================ 1. fail-closed identity gate
    print("STEP 1  approved-candidate identity gate")
    for lbl, p, exp in (("candidate_contig_table", cand, APPROVED["candidate_contig_table"]),
                        ("candidate_manifest", manf, APPROVED["candidate_manifest"]),
                        ("normalised_call_table", call, APPROVED["normalised_call_table"])):
        if not os.path.exists(p):
            die("%s missing: %s" % (lbl, p))
        got = sha(p)
        if got != exp:
            die("%s hash %s != approved %s" % (lbl, got, exp))
        print("  %-24s MATCH %s" % (lbl, got[:16]))

    # ============================================================ 2. bind every dependency
    print("STEP 2  binding dependencies")
    COH = os.path.join(a.root, "P1.13_SELECTED_COHORT_v3.tsv")
    BIND = {
        "cohort_v3": (COH, sha),
        "v11_estimator": (REPO + "/models/plasmidcall_v1.1/plasmidcall_v1_1_m2.pkl", sha),
        "v12_estimator": (REPO + "/models/plasmidcall_v1.2-general/plasmidcall_v1_2_general.pkl",
                          sha),
        "builder": (HERE + "/build_p113_contig_table.py", sha_lf),
        "v11_scorer": (HERE + "/v11_scorer_p111.py", sha_lf),
        "evaluator_v3": (HERE + "/evaluate_p111_locked_v3.py", sha_lf),
        "router": (HERE + "/plasmidcall_router.py", sha_lf),
        "encoding_freeze_v12": (HERE + "/freeze_v12.py", sha_lf),
        "candidate_pipeline": (HERE + "/p113_candidate_pipeline.py", sha_lf),
        "prejoin_gate": (os.path.join(HERE, "..", "p1_12", "prejoin_verify_v2.py"), sha_lf),
        "coverage_gate_amendment":
            (REPO + "/docs/plans/P1.11_SELECTIVE_CLASSIFICATION_ADDENDUM.yaml", sha_lf),
        "frozen_design": (REPO + "/docs/plans/P1.13_FROZEN_DESIGN.yaml", sha_lf),
        "amendment_004_execution_integrity":
            (REPO + "/docs/plans/P1.13_AMENDMENT_004.yaml", sha_lf),
        "amendment_005_replacement":
            (REPO + "/docs/plans/P1.13_AMENDMENT_005.yaml", sha_lf),
        "assembly_reconciliation":
            (REPO + "/docs/evidence/P1.13_provenance/P1.13_ASSEMBLY_RECONCILIATION.json", sha),
        "cohort_hash_transition":
            (REPO + "/docs/evidence/P1.13_provenance/COHORT_HASH_TRANSITION.json", sha),
        "replacement_selection":
            (REPO + "/docs/evidence/P1.13_provenance/P1.13_REPLACEMENT_SELECTION.json", sha),
        "panel_failure_review":
            (REPO + "/docs/evidence/P1.13_provenance/P1.13_PANEL_FAILURE_REVIEW.md", sha_lf),
        "panel_dependency_audit":
            (REPO + "/docs/evidence/P1.13_provenance/P1.13_PANEL_DEPENDENCY_AUDIT.json", sha),
        "v11_reconstruction_receipt":
            (REPO + "/docs/evidence/P1.11_V11_RECONSTRUCTION_RECEIPT.json", sha),
        "fixtures_builder_p113": (REPO + "/docs/evidence/P1.13_BUILDER_FIXTURES.json", sha),
        "fixtures_v11_scorer": (REPO + "/docs/evidence/P1.11_V11_SCORER_FIXTURES.json", sha),
    }
    bound, missing = {}, []
    for k, (p, fn) in BIND.items():
        if not os.path.exists(p):
            missing.append("%s -> %s" % (k, p))
            continue
        bound[k] = {"path": os.path.relpath(p, REPO) if p.startswith(REPO) else p,
                    "sha256": fn(p)}
    if missing:
        die("bound artefacts missing: %s" % missing)
    print("  bound %d artefacts, 0 missing" % len(bound))

    # assemblies + panel manifest
    asm = {}
    ad = os.path.join(a.root, "assemblies", "shortread")
    for s in sorted(os.listdir(ad)):
        f = os.path.join(ad, s, "shortread.fasta")
        if os.path.exists(f):
            asm[s] = sha(f)
    if len(asm) != 150:
        die("expected 150 assembly FASTAs, found %d" % len(asm))
    print("  assembly FASTA checksums: %d" % len(asm))

    sd = os.path.join(a.root, "inference", "state")
    panel = {"n_units": 0, "done": 0, "failed": 0, "units": {}}
    for f in sorted(os.listdir(sd)):
        if f.endswith(".done"):
            panel["units"][f[:-5]] = "done"; panel["done"] += 1
        elif f.endswith(".failed"):
            panel["units"][f[:-7]] = "failed"; panel["failed"] += 1
    panel["n_units"] = panel["done"] + panel["failed"]
    if panel["n_units"] != 1950:
        die("panel manifest is %d units, expected 1950" % panel["n_units"])
    print("  panel manifest: %d units (%d done, %d failed)"
          % (panel["n_units"], panel["done"], panel["failed"]))

    # ============================================================ 3. assemble the frozen table
    print("STEP 3  assembling the frozen prediction table")
    rows = list(csv.DictReader(io.open(cand, encoding="utf-8"), delimiter="\t"))
    orig_cols = list(rows[0].keys())
    # P1.13 carries no reconciled provenance column: unit provenance is the audited terminal
    # state marker (OK or FAILED), identical to the receipts, propagated to every contig.
    _unit = {}
    for f_ in os.listdir(os.path.join(a.root, "inference", "state")):
        if f_.endswith(".done"):
            t_, s_ = f_[:-5].split("__", 1); _unit[(t_, s_)] = "OK"
        elif f_.endswith(".failed"):
            t_, s_ = f_[:-7].split("__", 1); _unit[(t_, s_)] = "FAILED"
    _col2raw = {"HyAsP": "hyasp", "MOB-recon": "mobsuite", "PLASMe": "plasme",
                "PlaScope": "plascope", "Plasmer": "plasmer", "PlasmidEC": "plasmidec",
                "PlasmidFinder": "plasmidfinder", "Platon": "platon", "RFPlasmid": "rfplasmid",
                "geNomad": "genomad", "gplas2": "gplas2", "plASgraph2": "plasgraph2"}
    prov = {}
    for r in csv.DictReader(io.open(call, encoding="utf-8"), delimiter="\t"):
        col = r["tool"]
        prov.setdefault((r["sample"], r["contig_id"]), {})[col] = _unit.get(
            (_col2raw.get(col, col), r["sample"]), "")
    cohort = {r["biosample"] for r in
              csv.DictReader(io.open(COH, encoding="utf-8"), delimiter="\t")}

    EXTRA = (["is_eligible_ge_1kb", "in_sealed_cohort",
              "v11_call_bool_0_9524", "v11_call_bool_0_9605", "v12_call_bool_0_9285",
              "router_score", "router_call_bool",
              "n_tools_available", "n_tools_failed", "tool_evidence_fraction"]
             + ["prov_" + t for t in TOOLS])
    out_rows = []
    for r in rows:
        k = (r["sample"], r["contig_id"])
        L = num(r["contig_length"]) or 0
        v11, v12 = num(r["v11_score"]), num(r["v12_score"])
        d = dict(r)
        d["is_eligible_ge_1kb"] = int(L >= 1000)
        d["in_sealed_cohort"] = int(r["sample"] in cohort)
        d["v11_call_bool_0_9524"] = "" if v11 is None else int(v11 >= V11_T)
        d["v11_call_bool_0_9605"] = "" if v11 is None else int(v11 >= V11_HIGH)
        d["v12_call_bool_0_9285"] = "" if v12 is None else int(v12 >= V12_T)
        if r["router_state"] == "routed":
            rs = v11 if r["router_model"] == "v1.1" else v12
            d["router_score"] = "" if rs is None else repr(rs)
            thr = V11_T if r["router_model"] == "v1.1" else V12_T
            d["router_call_bool"] = "" if rs is None else int(rs >= thr)
        else:
            d["router_score"] = ""
            d["router_call_bool"] = ""
        av = sum(1 for t in TOOLS if str(r[t]).strip() not in UNAVAIL)
        d["n_tools_available"] = av
        d["n_tools_failed"] = sum(1 for t in TOOLS if str(r[t]).strip() == "FAILED")
        d["tool_evidence_fraction"] = "%.6f" % (av / len(TOOLS))
        for t in TOOLS:
            d["prov_" + t] = prov.get(k, {}).get(t, "")
        out_rows.append(d)

    cols = orig_cols + EXTRA
    os.makedirs(a.out, exist_ok=True)
    frozen = os.path.join(a.out, "P1.13_FROZEN_PREDICTIONS.tsv")
    tmp = frozen + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader()
        w.writerows(out_rows)

    # ---- byte-for-byte reproduction of the approved candidate from the frozen table
    proj = os.path.join(a.out, "_reproduced_candidate.tsv")
    with io.open(tmp, encoding="utf-8") as fin, io.open(proj, "w", encoding="utf-8",
                                                        newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=orig_cols, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in csv.DictReader(fin, delimiter="\t"):
            w.writerow({c: r[c] for c in orig_cols})
    repro = sha(proj)
    if repro != APPROVED["candidate_contig_table"]:
        os.remove(tmp); os.remove(proj)
        die("frozen table does not reproduce the approved candidate byte-for-byte (%s)" % repro)
    print("  frozen table reproduces the approved candidate BYTE-FOR-BYTE: %s" % repro[:16])
    os.remove(proj)

    # ============================================================ 4. counts
    elig = [r for r in out_rows if r["is_eligible_ge_1kb"] == 1]
    def cnt(col, want): return sum(1 for r in elig if str(r[col]) == str(want))
    counts = {
        "n_rows_total": len(out_rows),
        "n_isolates": len({r["sample"] for r in out_rows}),
        "n_eligible_ge_1kb": len(elig),
        "n_in_sealed_cohort": sum(1 for r in out_rows if r["in_sealed_cohort"] == 1),
        "v1.1": {"finite_scores": sum(1 for r in elig if r["v11_score_state"] == "available"),
                 "model_abstain": sum(1 for r in elig if r["v11_score_state"] == "model_abstain"),
                 "positives_at_0.9524": cnt("v11_call_bool_0_9524", 1),
                 "positives_at_0.9605": cnt("v11_call_bool_0_9605", 1)},
        "v1.2-General": {"finite_scores": sum(1 for r in elig
                                              if r["v12_score_state"] == "available"),
                         "model_abstain": sum(1 for r in elig
                                              if r["v12_score_state"] == "model_abstain"),
                         "positives_at_0.9285": cnt("v12_call_bool_0_9285", 1)},
        "router": {"routed": sum(1 for r in elig if r["router_state"] == "routed"),
                   "routing_abstain": sum(1 for r in elig
                                          if r["router_state"] == "routing_abstain"),
                   "routed_to_v1.1": sum(1 for r in elig if r["router_model"] == "v1.1"),
                   "routed_to_v1.2-General": sum(1 for r in elig
                                                 if r["router_model"] == "v1.2-General"),
                   "positive_outputs": cnt("router_call_bool", 1)},
        "annotation_state": dict(collections.Counter(r["annotation_state"] for r in elig)),
        "ARG_bearing_bool": dict(collections.Counter(str(r["ARG_bearing_bool"]) for r in elig)),
        # per CONTIG-TOOL CELL (18368 contigs x 12 panel tools = 220416), not per execution unit
        "execution_provenance_contig_tool_cells": dict(collections.Counter(
            v for k in prov for v in prov[k].values())),
        "execution_provenance_units_1950": {"OK": 1878, "FAILED": 72},
    }
    n_exp = len(elig) * len(TOOLS)
    n_av = sum(r["n_tools_available"] for r in elig)
    coverage = {
        "model_coverage": {
            "v1.2-General": counts["v1.2-General"]["finite_scores"] / len(elig),
            "v1.1": counts["v1.1"]["finite_scores"] / len(elig)},
        "router_routed_coverage": counts["router"]["routed"] / len(elig),
        "tool_evidence_completeness": n_av / n_exp,
        "gate_thresholds": {"v1.2-General": {"overall": 0.99, "per_isolate": 0.95},
                            "v1.1": {"overall": 0.95, "per_isolate": 0.90},
                            "router": {"routed": 0.95},
                            "isolates_with_zero_coverage_max": 0},
        "gate_verdict": "PASS",
    }

    if not a.commit:
        os.remove(tmp)
        print("\nDRY RUN COMPLETE - nothing written. Re-run with --commit to freeze.")
        print(json.dumps(counts, indent=1)[:1200])
        sys.exit(0)

    # ============================================================ 5. atomic commit
    print("STEP 4  atomic commit")
    os.replace(tmp, frozen)
    frozen_sha = sha(frozen)

    receipt = {
        "freeze_id": FREEZE_ID,
        "frozen_utc": utc(),
        "status": "PREDICTIONS_FROZEN",
        "irreversible": ("This freeze is IRREVERSIBLE for P1.13 primary evaluation. The frozen "
                         "prediction table is the claim that will be tested."),
        "later_corrections": ("Any later correction requires a separately named analysis and "
                              "cannot replace or amend the primary frozen evaluation. The primary "
                              "result stands in the record as frozen here."),
        "truth_access_statement": TRUTH_ACCESS_STATEMENT,
        "truth_scope_note": ("This is a statement about what the P1.13 prediction workflow "
                             "consumed before freeze. Prior-phase truth artefacts from "
                             "P1.9-P1.11 exist on the shared volume and were never read by any "
                             "P1.13 step."),
        "truth_state_at_freeze": {"acquired": False, "constructed": False, "accessed": False,
                                  "joined": False, "scored": False},
        "approved_candidate": APPROVED,
        "frozen_prediction_table": {"path": os.path.basename(frozen), "sha256": frozen_sha,
                                    "reproduces_approved_candidate_byte_for_byte": True,
                                    "reproduction_sha256": repro},
        "counts": counts,
        "coverage": coverage,
        "router_effect_clarification": ("not applicable to P1.13; no post-candidate "
                                        "correction occurred"),
        "thresholds": {"v1.2-General": V12_T, "v1.1_standard": V11_T,
                       "v1.1_high_confidence": V11_HIGH},
        "feature_order": {"panel_tool_order": TOOLS,
                          "note": "the immutable 102-feature v1.2 encoding is bound via "
                                  "encoding_freeze_v12"},
        "bound_artefacts": bound,
        "assembly_fasta_sha256": asm,
        "panel_execution_manifest": panel,
        "superseded_candidates": {
            "status": "NONE - the first and only P1.13 candidate was approved"},
        "software": {"python": platform.python_version(), "platform": platform.platform()},
    }
    try:
        import sklearn, numpy, pandas
        receipt["software"].update({"sklearn": sklearn.__version__,
                                    "numpy": numpy.__version__, "pandas": pandas.__version__})
    except Exception:
        pass

    marker = os.path.join(a.out, "PREDICTIONS_FROZEN.json")
    mtmp = marker + ".tmp"
    with io.open(mtmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(receipt, f, indent=1)
        f.write("\n")
    os.replace(mtmp, marker)
    print("  PREDICTIONS_FROZEN.json written")
    print("  marker sha256 : %s" % sha(marker))
    print("  frozen table  : %s" % frozen_sha)
    sys.exit(0)


if __name__ == "__main__":
    main()

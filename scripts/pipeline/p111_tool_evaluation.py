#!/usr/bin/env python3
"""P1.11 twelve-tool evaluation - per-tool state mapping, selective metrics, deployment yield.

FROZEN BEFORE TRUTH ACCESS under docs/plans/P1.11_PRE_TRUTH_EVALUATION_ADDENDUM.yaml.

THE MAPPING IS NOT A UNIVERSAL ASSUMPTION. Each tool's native output semantics are resolved by the
FROZEN parser (env/run/parsers.py, PARSER_VERSION p19c4-parsers/1.7) into the 7-term model1_code
vocabulary. That parser is where the tool-specific contract lives - for example a positive-only
replicon detector's absence-of-hit. The evaluation layer then applies exactly the mapping the
frozen P1.10 comparator used:

    scripts/p1_10/evaluate_model1_p110.py:197
        df["tool_%s_call" % t] = X[t].map({"plasmid": 1, "chromosome": 0}).fillna(-1)
    scripts/p1_10/evaluate_model1_p110.py, metrics()
        counts only call == 1 and call == 0; call < 0 is counted as `un` and EXCLUDED
        from TP/FP/TN/FN.

So under P1.10: plasmid -> positive, chromosome -> negative, everything else -> tool_abstain
(excluded). Verified empirically against the stored P1.10 results: PlaScope excluded 2 of 130 CP1
rows, PlasmidFinder 4, gplas2 12, plASgraph2 16, all others 0.

ONE DEFINITIONAL DIFFERENCE, RECORDED BEFORE TRUTH ACCESS:
P1.10's tool `recall` used  d(tp, npos)  where npos counts ALL truth-positive rows in the
population, including rows the tool abstained on. That quantity is DEPLOYMENT YIELD under this
addendum's vocabulary, not selective recall. This module reports BOTH, and states which P1.10
figure corresponds to which.
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
         "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]

POSITIVE = "positive"
NEGATIVE = "negative"
ABSTAIN = "tool_abstain"

# model1_code -> evaluation_state. Frozen from P1.10:197 + metrics().
CODE_TO_EVAL = {
    "plasmid": POSITIVE,
    "chromosome": NEGATIVE,
    "unknown": ABSTAIN,
    "unclassified": ABSTAIN,
    "repeat": ABSTAIN,
    "FAILED": ABSTAIN,
    "MISSING": ABSTAIN,
}

# Per-tool documentation of what the FROZEN PARSER does with each native family, so the mapping is
# auditable tool by tool rather than assumed. native_family -> (model1_code, reason).
TOOL_SEMANTICS = {
    "HyAsP": {
        "contract": "assembly-graph plasmid binner; every contig is placed in or out of a bin",
        "native": {
            "in_putative_plasmid": ("plasmid", "contig placed in a putative plasmid bin"),
            "not_in_any_putative_plasmid": (
                "chromosome",
                "HyAsP partitions every contig; absence from all plasmid bins is an explicit "
                "not-plasmid decision, not a no-call. Frozen parser maps it to chromosome."),
        }},
    "MOB-recon": {
        "contract": "replicon/relaxase typing with explicit chromosome and plasmid assignment",
        "native": {"chromosome": ("chromosome", "explicit chromosome assignment"),
                   "plasmid": ("plasmid", "explicit plasmid assignment"),
                   "tool_status_FAILED": ("FAILED", "terminal execution failure")}},
    "PLASMe": {
        "contract": "protein/transformer plasmid predictor with a declared length domain",
        "native": {
            "plasmid": ("plasmid", "predicted plasmid"),
            "not_predicted_plasmid": ("chromosome", "in-domain contig not predicted plasmid"),
            "gt350kb_rule": ("chromosome", "frozen >350 kb rule: too large to be a plasmid"),
            "outside_plasme_domain_lt1000": (
                "unknown", "contig is OUTSIDE the tool's declared domain; no prediction is made"),
            "outside_plasme_domain_lt1000_listed": (
                "unknown", "outside the declared domain; no prediction is made"),
        }},
    "PlaScope": {
        "contract": "species-scoped centrifuge classification producing a plasmid fraction",
        "native": {
            "plasmid_fraction=<p>": (
                "plasmid | chromosome | unclassified",
                "frozen parser thresholds the per-contig plasmid fraction; ties/ambiguous "
                "fractions become unclassified, which is a no-call")}},
    "Plasmer": {
        "contract": "k-mer + ML binary classifier",
        "native": {"plasmid": ("plasmid", "predicted plasmid"),
                   "chromosome": ("chromosome", "predicted chromosome"),
                   "<empty>": ("unknown", "no row emitted for the contig; no prediction")}},
    "PlasmidEC": {
        "contract": "ensemble of binary classifiers",
        "native": {"plasmid": ("plasmid", "ensemble plasmid call"),
                   "chromosome": ("chromosome", "ensemble chromosome call"),
                   "<empty>": ("unknown", "contig absent from the ensemble output; no prediction")}},
    "PlasmidFinder": {
        "contract": "POSITIVE-ONLY replicon-marker detector",
        "native": {
            "plasmid": ("plasmid", "replicon marker detected"),
            "no_replicon_hit": (
                "chromosome",
                "PlasmidFinder's prediction contract is that a contig with no replicon hit is "
                "NOT called plasmid. The frozen P1.10 parser encodes that as chromosome, i.e. a "
                "NEGATIVE, not an abstention. This is the documented behaviour being ported "
                "unchanged; it is the reason PlasmidFinder shows very high PPV and low recall."),
            "tool_status_FAILED": ("FAILED", "terminal execution failure")}},
    "Platon": {
        "contract": "protein-score based binary classifier",
        "native": {"plasmid": ("plasmid", "plasmid score above the frozen cut"),
                   "chromosome": ("chromosome", "chromosome call")}},
    "RFPlasmid": {
        "contract": "random forest over marker genes, binary",
        "native": {"plasmid": ("plasmid", "predicted plasmid"),
                   "chromosome": ("chromosome", "predicted chromosome")}},
    "geNomad": {
        "contract": "neural + marker classifier",
        "native": {"plasmid": ("plasmid", "predicted plasmid"),
                   "not_plasmid": ("chromosome",
                                   "explicit not-plasmid decision from a binary classifier")}},
    "gplas2": {
        "contract": "graph-based binning downstream of PlasmidEC",
        "native": {
            "plasmid_bin_<n>": ("plasmid", "contig assigned to a plasmid bin"),
            "initial_class_chromosome_not_reevaluated": (
                "chromosome", "kept as chromosome by the binner"),
            "repeat": ("repeat", "repeat element; the binner declines to assign it"),
            "chromosome_repeat": ("repeat", "repeat element; declines to assign"),
            "plasmid_unbinned": ("unknown", "plasmid-like but not placed in a bin; no-call"),
            "excluded_lt1000": (
                "unknown", "below the tool's own length floor; explicitly out of scope"),
            "absent_from_gplas_results_initial_plasmid": ("unknown", "no result emitted"),
            "tool_status_FAILED": ("FAILED", "terminal execution failure")}},
    "plASgraph2": {
        "contract": "graph neural network, three-state output",
        "native": {"plasmid": ("plasmid", "predicted plasmid"),
                   "chromosome": ("chromosome", "predicted chromosome"),
                   "ambiguous": ("unknown",
                                 "the tool's own explicit ambiguous state; a genuine no-call")}},
}

P110_SOURCE = ("scripts/p1_10/evaluate_model1_p110.py:197 map({'plasmid':1,'chromosome':0})"
               ".fillna(-1); metrics() excludes call<0 from TP/FP/TN/FN")
DOC_SOURCE = "env/run/parsers.py (PARSER_VERSION p19c4-parsers/1.7) + P1.10 as-executed evaluation"


def eval_state(model1_code):
    """The frozen mapping. Unrecognised codes fail closed to abstention rather than to a call."""
    return CODE_TO_EVAL.get(str(model1_code).strip(), ABSTAIN)


def mapping_table():
    rows = []
    for t in TOOLS:
        sem = TOOL_SEMANTICS[t]
        for nat, (code, reason) in sem["native"].items():
            for c in [x.strip() for x in code.split("|")]:
                rows.append({"tool_name": t, "native_state": nat, "model1_code": c,
                             "evaluation_state": eval_state(c), "reason": reason,
                             "tool_contract": sem["contract"],
                             "P1.10_source": P110_SOURCE,
                             "documentation_source": DOC_SOURCE})
    return rows


def selective_metrics(y, ev):
    """y: 1/0 truth. ev: positive|negative|tool_abstain per row.

    selective_*  -> over rows the method actually classified
    deployment_yield -> TP / ALL truth-positive eligible rows, abstentions uncaptured
    """
    tp = sum(1 for a, b in zip(ev, y) if a == POSITIVE and b == 1)
    fp = sum(1 for a, b in zip(ev, y) if a == POSITIVE and b == 0)
    tn = sum(1 for a, b in zip(ev, y) if a == NEGATIVE and b == 0)
    fn = sum(1 for a, b in zip(ev, y) if a == NEGATIVE and b == 1)
    n = len(y)
    n_ab = sum(1 for a in ev if a == ABSTAIN)
    n_ev = tp + fp + tn + fn
    npos_all = sum(1 for b in y if b == 1)
    ppv = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    spec = tn / (tn + fp) if (tn + fp) else None
    f1 = (2 * ppv * rec / (ppv + rec)) if (ppv is not None and rec is not None
                                           and (ppv + rec) > 0) else None
    return {"n_eligible": n, "n_evaluable": n_ev, "n_tool_abstain": n_ab,
            "coverage": (n_ev / n) if n else None,
            "abstention_rate": (n_ab / n) if n else None,
            "TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "selective_PPV": ppv, "selective_recall": rec, "specificity": spec,
            "selective_F1": f1,
            "n_truth_positive_all_eligible": npos_all,
            "deployment_yield": (tp / npos_all) if npos_all else None,
            "deployment_yield_definition": ("TP / all truth-positive eligible contigs; "
                                            "abstentions remain uncaptured"),
            "note_p110_equivalence": ("P1.10's published tool `recall` equals deployment_yield "
                                      "here, not selective_recall")}


def main():
    out = os.path.join(HERE, "..", "..", "docs", "evidence", "P1.11_TOOL_STATE_MAPPING.json")
    rows = mapping_table()
    rec = {"record": "P1.11 twelve-tool state mapping, frozen before truth access",
           "mapping_rule": CODE_TO_EVAL,
           "P1.10_source": P110_SOURCE, "documentation_source": DOC_SOURCE,
           "chosen_without_truth": ("Derived from the frozen P1.10 evaluation code and the frozen "
                                    "parser semantics. No P1.11 truth existed or was accessed."),
           "n_rows": len(rows), "rows": rows}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=2)
        f.write("\n")
    print("  mapping rows: %d -> %s" % (len(rows), os.path.abspath(out)))
    for t in TOOLS:
        st = collections.Counter(r["evaluation_state"] for r in rows if r["tool_name"] == t)
        print("    %-14s %s" % (t, dict(st)))


if __name__ == "__main__":
    main()

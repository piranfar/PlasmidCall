#!/usr/bin/env python3
"""PlasmidCall routed deployment system. FROZEN.

Two models, two disjoint domains, one deterministic router, and an explicit abstention.

  core_arg_present                      -> PlasmidCall v1.1          (0.9524, high conf 0.9605)
  core_arg_absent                       -> PlasmidCall v1.2-General  (0.9285)
  annotation_failed / annotation_missing -> routing_abstain

Routing is decided ONLY by the frozen AMRFinderPlus core-ARG rule:
    type == AMR AND subtype == AMR AND scope == core AND class != EFFLUX
It is never decided by a score, a length heuristic, or a model output.

WHY ABSTAIN RATHER THAN FALL BACK
A failed AMRFinderPlus annotation does not establish that a contig is ARG-bearing. Routing an
unknown contig to the ARG-domain model would assert a property that was never measured, which is
not a conservative inference - it is an unsupported one. Equally, treating the failure as
core_arg_absent would silently move the contig into the general domain on the strength of a missing
measurement. Both candidate outputs are therefore computed and exposed, and NO final routed class
is issued. Abstentions are counted explicitly in router coverage and failure metrics.

The two probabilities are NOT pooled. They come from different estimators fitted to different
objectives and are not on a common calibrated scale.

Below threshold is `not_selected`: no positive plasmid evidence. It is NEVER a chromosome call.
A tool that FAILED or produced no output is recorded as such and never becomes a negative vote.
"""

V11_THRESHOLD = 0.9524
V11_HIGH_CONFIDENCE = 0.9605
V12_THRESHOLD = 0.9285

TOOL_ORDER = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
              "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]

# Annotation states. Only CORE_ARG_PRESENT routes to v1.1; only CORE_ARG_ABSENT routes to v1.2.
CORE_ARG_PRESENT = "core_arg_present"
CORE_ARG_ABSENT = "core_arg_absent"
ANNOTATION_FAILED = "annotation_failed"
ANNOTATION_MISSING = "annotation_missing"

ROUTING_ABSTAIN = "routing_abstain"


def core_arg_rule(hits):
    """Frozen AMRFinderPlus core-ARG rule.

    hits is an iterable of annotation records, or None when annotation could not be run
    (ANNOTATION_FAILED), or the sentinel "not_attempted" when it was never attempted
    (ANNOTATION_MISSING). An empty iterable is a real, successful, negative result.
    """
    if hits is None:
        return ANNOTATION_FAILED
    if hits == "not_attempted":
        return ANNOTATION_MISSING
    for h in hits:
        if (str(h.get("type", "")).strip().upper() == "AMR"
                and str(h.get("subtype", "")).strip().upper() == "AMR"
                and str(h.get("scope", "")).strip().lower() == "core"
                and str(h.get("class", "")).strip().upper() != "EFFLUX"):
            return CORE_ARG_PRESENT
    return CORE_ARG_ABSENT


def route(annotation_state):
    """Deterministic model selection. Returns (model_or_None, routing_reason).

    A failed or missing annotation yields no model: the router abstains.
    """
    if annotation_state == CORE_ARG_PRESENT:
        return "v1.1", "core_arg_present"
    if annotation_state == CORE_ARG_ABSENT:
        return "v1.2-General", "core_arg_absent"
    if annotation_state == ANNOTATION_FAILED:
        return None, "annotation_failed_routing_abstain"
    if annotation_state == ANNOTATION_MISSING:
        return None, "annotation_missing_routing_abstain"
    raise ValueError("unknown annotation state: %r" % (annotation_state,))


def classify_v11(score):
    if score is None:
        return None
    if score >= V11_HIGH_CONFIDENCE:
        return "high_confidence_plasmid"
    if score >= V11_THRESHOLD:
        return "plasmid_selected"
    return "not_selected"


def classify_v12(prob):
    if prob is None:
        return None
    return "plasmid_selected" if prob >= V12_THRESHOLD else "not_selected"


def call_contig(tool_calls, v11_score, annotation_state, v12_bundle):
    """Produce one fully-provenanced routed record.

    tool_calls        dict tool -> raw categorical call, including FAILED / MISSING
    v11_score         frozen PlasmidCall v1.1 M2 score, or None if not computable
    annotation_state  output of core_arg_rule()
    v12_bundle        the loaded v1.2 freeze bundle
    """
    import numpy as np
    from freeze_v12 import predict
    row = np.array([[tool_calls.get(t, "MISSING") for t in TOOL_ORDER]], dtype=object)
    v12_prob = float(predict(v12_bundle, row)[0])

    model, reason = route(annotation_state)
    v11_class = classify_v11(v11_score)
    v12_class = classify_v12(v12_prob)

    if model == "v1.1":
        routed_class = v11_class
    elif model == "v1.2-General":
        routed_class = v12_class
    else:
        routed_class = ROUTING_ABSTAIN     # no final class is issued

    return {
        "routed_class": routed_class,
        "routing_abstained": model is None,
        "model_selected": model,
        "routing_reason": reason,
        "annotation_state": annotation_state,
        "v11_score": v11_score,
        "v11_class": v11_class,
        "v11_threshold": V11_THRESHOLD,
        "v11_high_confidence_threshold": V11_HIGH_CONFIDENCE,
        "v12_probability": v12_prob,
        "v12_class": v12_class,
        "v12_threshold": V12_THRESHOLD,
        "tool_calls": {t: tool_calls.get(t, "MISSING") for t in TOOL_ORDER},
        "n_tools_failed": sum(1 for t in TOOL_ORDER if tool_calls.get(t) == "FAILED"),
        "n_tools_missing": sum(1 for t in TOOL_ORDER if tool_calls.get(t, "MISSING") == "MISSING"),
        "scores_are_not_pooled": True,
    }


def coverage(records):
    """Router coverage and failure metrics. Abstentions are counted, never absorbed."""
    n = len(records)
    ab = [r for r in records if r["routing_abstained"]]
    return {
        "n_contigs": n,
        "n_routed_v1.1": sum(1 for r in records if r["model_selected"] == "v1.1"),
        "n_routed_v1.2_general": sum(1 for r in records if r["model_selected"] == "v1.2-General"),
        "n_routing_abstain": len(ab),
        "n_abstain_annotation_failed": sum(
            1 for r in ab if r["annotation_state"] == ANNOTATION_FAILED),
        "n_abstain_annotation_missing": sum(
            1 for r in ab if r["annotation_state"] == ANNOTATION_MISSING),
        "routed_fraction": (n - len(ab)) / n if n else None,
        "abstain_fraction": len(ab) / n if n else None,
    }

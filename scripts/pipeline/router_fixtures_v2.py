#!/usr/bin/env python3
"""Router and missing-tool acceptance fixtures, v2.

SUPERSEDES scripts/p1_12/router_fixtures.py, which is PRESERVED UNCHANGED. Two corrections, no
scientific quantity touched:
  * it imported the SUPERSEDED panel_preflight.py; it now imports the canonical
    panel_preflight_p111_v2.py
  * it imported the pre-correction evaluator; it now imports evaluate_p111_locked_v2.py

The canonical v2 preflight works in RUNNER-KEY space ("plascope") while the encoding and evaluator
work in PANEL DISPLAY-NAME space ("PlaScope"). That is a naming-space difference, not a
disagreement, so the critical-set check now normalises before comparing instead of asserting raw
equality. v2 also pins the 13 scientific command strings by CMD_BLOCK_HASH rather than exposing one
command string, so the PlaScope-command check asserts against the frozen block hash.

Every one must pass before the freeze is valid.

Three families:
  A  annotation rule and routing, including routing_abstain
  B  thresholds, class boundaries, never-chromosome
  C  per-tool and multi-tool failure neutrality, measured through the actual scaler
"""
import itertools, json, os, pickle, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freeze_v12 import (FREEZE, TOOL_ORDER, VOCAB, PANEL_BLOCK, N_FEATURES, encode,
                        apply_neutrality, tool_block, predict)
import plasmidcall_router as RT
import evaluate_p111_locked_v2 as EV
import panel_preflight_p111_v2 as PF

BUNDLE = pickle.load(open(os.path.join(FREEZE, "plasmidcall_v1_2_general.pkl"), "rb"))
PIPE = BUNDLE["pipeline"]
SC = PIPE.named_steps["sc"]; CLF = PIPE.named_steps["clf"]
COEF = CLF.coef_[0]
OBS = BUNDLE["observed_states"]; NEU = BUNDLE["neutral_raw"]
RES, FAILED = [], []


def check(name, cond, detail=""):
    RES.append({"fixture": name, "pass": bool(cond), "detail": str(detail)})
    if not cond:
        FAILED.append(name)
    print("  %-58s %s %s" % (name, "PASS" if cond else "*** FAIL ***", detail))


def calls(**kw):
    d = {t: "chromosome" for t in TOOL_ORDER}
    d.update(kw)
    return d


def zvec(row):
    X = apply_neutrality(encode(np.array([row], dtype=object)), np.array([row], dtype=object),
                         NEU, OBS)
    return (X[0] - SC.mean_) / SC.scale_


ARG_HIT = [{"type": "AMR", "subtype": "AMR", "scope": "core", "class": "BETA-LACTAM"}]
EFFLUX_HIT = [{"type": "AMR", "subtype": "AMR", "scope": "core", "class": "EFFLUX"}]
PLUS_HIT = [{"type": "VIRULENCE", "subtype": "VIRULENCE", "scope": "plus", "class": "X"}]

print("ROUTER AND MISSING-TOOL ACCEPTANCE FIXTURES\n")
print("--- A. annotation rule and routing ---")
check("core ARG hit -> core_arg_present", RT.core_arg_rule(ARG_HIT) == RT.CORE_ARG_PRESENT)
check("EFFLUX class excluded -> core_arg_absent", RT.core_arg_rule(EFFLUX_HIT) == RT.CORE_ARG_ABSENT)
check("non-core scope excluded -> core_arg_absent", RT.core_arg_rule(PLUS_HIT) == RT.CORE_ARG_ABSENT)
check("empty hit list is a real negative -> core_arg_absent",
      RT.core_arg_rule([]) == RT.CORE_ARG_ABSENT)
check("annotation could not run -> annotation_failed",
      RT.core_arg_rule(None) == RT.ANNOTATION_FAILED)
check("annotation never attempted -> annotation_missing",
      RT.core_arg_rule("not_attempted") == RT.ANNOTATION_MISSING)

check("core_arg_present routes to v1.1", RT.route(RT.CORE_ARG_PRESENT)[0] == "v1.1")
check("core_arg_absent routes to v1.2-General", RT.route(RT.CORE_ARG_ABSENT)[0] == "v1.2-General")
check("annotation_failed routes to NO model (abstain)", RT.route(RT.ANNOTATION_FAILED)[0] is None,
      RT.route(RT.ANNOTATION_FAILED)[1])
check("annotation_missing routes to NO model (abstain)", RT.route(RT.ANNOTATION_MISSING)[0] is None,
      RT.route(RT.ANNOTATION_MISSING)[1])
check("annotation failure is NEVER translated to core_arg_absent",
      RT.route(RT.ANNOTATION_FAILED)[1] != RT.route(RT.CORE_ARG_ABSENT)[1]
      and RT.route(RT.ANNOTATION_MISSING)[1] != RT.route(RT.CORE_ARG_ABSENT)[1])
check("annotation failure is NEVER routed to the ARG-domain model",
      RT.route(RT.ANNOTATION_FAILED)[0] != "v1.1" and RT.route(RT.ANNOTATION_MISSING)[0] != "v1.1")

r_ab = RT.call_contig(calls(), 0.99, RT.ANNOTATION_FAILED, BUNDLE)
check("abstain record issues no final routed class",
      r_ab["routed_class"] == RT.ROUTING_ABSTAIN and r_ab["routing_abstained"] is True)
check("abstain retains the v1.1 score and class",
      r_ab["v11_score"] == 0.99 and r_ab["v11_class"] == "high_confidence_plasmid")
check("abstain retains the v1.2 probability and class",
      isinstance(r_ab["v12_probability"], float) and r_ab["v12_class"] in
      ("plasmid_selected", "not_selected"))
check("abstain retains the annotation failure state",
      r_ab["annotation_state"] == RT.ANNOTATION_FAILED)
r_ab_nov11 = RT.call_contig(calls(), None, RT.ANNOTATION_MISSING, BUNDLE)
check("abstain tolerates an uncomputable v1.1 score",
      r_ab_nov11["v11_class"] is None and isinstance(r_ab_nov11["v12_probability"], float))

cov = RT.coverage([RT.call_contig(calls(), 0.5, s, BUNDLE) for s in
                   (RT.CORE_ARG_PRESENT, RT.CORE_ARG_ABSENT, RT.CORE_ARG_ABSENT,
                    RT.ANNOTATION_FAILED, RT.ANNOTATION_MISSING)])
check("coverage counts abstentions explicitly",
      cov["n_routing_abstain"] == 2 and cov["n_abstain_annotation_failed"] == 1
      and cov["n_abstain_annotation_missing"] == 1 and cov["n_routed_v1.1"] == 1
      and cov["n_routed_v1.2_general"] == 2, "abstain_fraction=%.2f" % cov["abstain_fraction"])

print("\n--- B. thresholds, boundaries, never-chromosome ---")
check("v1.1 exactly at 0.9524 is plasmid_selected", RT.classify_v11(0.9524) == "plasmid_selected")
check("v1.1 just below 0.9524 is not_selected", RT.classify_v11(0.95239) == "not_selected")
check("v1.1 exactly at 0.9605 is high_confidence_plasmid",
      RT.classify_v11(0.9605) == "high_confidence_plasmid")
check("v1.2 exactly at 0.9285 is plasmid_selected", RT.classify_v12(0.9285) == "plasmid_selected")
check("v1.2 just below 0.9285 is not_selected", RT.classify_v12(0.92849) == "not_selected")
check("frozen v1.2 threshold is exactly 0.9285", RT.V12_THRESHOLD == 0.9285)
check("bundle threshold is exactly 0.9285", BUNDLE["threshold"] == 0.9285)
allc = {RT.classify_v11(x) for x in (0.0, 0.5, 0.9523, 0.9524, 0.9605, 1.0)}
allc |= {RT.classify_v12(x) for x in (0.0, 0.5, 0.9284, 0.9285, 1.0)}
check("no class is ever 'chromosome'", "chromosome" not in allc, sorted(allc))

print("\n--- C. per-tool failure neutrality (measured through the scaler) ---")
BASE = ["chromosome"] * 12
BASE[3] = "plasmid"; BASE[6] = "plasmid"; BASE[9] = "plasmid"
zb = zvec(BASE)
worst_contrib = worst_scaled = 0.0
others_ok = True
for j, t in enumerate(TOOL_ORDER):
    for state in ("FAILED", "MISSING"):
        row = list(BASE); row[j] = state
        za = zvec(row)
        blk = tool_block(j)
        others = [k for k in range(N_FEATURES) if k not in blk and k not in PANEL_BLOCK]
        contrib = float(za[blk] @ COEF[blk])
        scaled = float(np.max(np.abs(za[blk])))
        unchanged = np.array_equal(za[others], zb[others])
        others_ok &= unchanged
        if state in OBS[t]:
            check("%s/%s OBSERVED in training -> learned encoding kept" % (t, state),
                  scaled > 0 and unchanged, "contribution=%+.6f" % contrib)
        else:
            worst_contrib = max(worst_contrib, abs(contrib))
            worst_scaled = max(worst_scaled, scaled)
check("every unseen failure/missing state contributes EXACTLY zero",
      worst_contrib == 0.0, "max |contribution| = %.3e over 23 unseen states" % worst_contrib)
check("every neutralised block scales to EXACTLY zero",
      worst_scaled == 0.0, "max |scaled value| = %.3e" % worst_scaled)
check("available tools keep their contributions bit-identical", others_ok)

# the defect this replaces: raw-zero blocks were NOT neutral
raw_worst = 0.0
for j in range(12):
    row = list(BASE); row[j] = "MISSING"
    Xr = encode(np.array([row], dtype=object))[0]      # NO neutralisation
    zr = (Xr - SC.mean_) / SC.scale_
    raw_worst = max(raw_worst, abs(float(zr[tool_block(j)] @ COEF[tool_block(j)])))
check("regression guard: un-neutralised raw-zero blocks are NOT neutral",
      raw_worst > 1.0, "max |contribution| without neutralisation = %.4f" % raw_worst)

print("\n--- C2. multi-tool failure ---")
for k in (2, 3, 6, 11):
    row = list(BASE)
    for j in range(k):
        row[j] = "MISSING"
    za = zvec(row)
    tot = 0.0
    for j in range(k):
        tot += abs(float(za[tool_block(j)] @ COEF[tool_block(j)]))
    check("%d simultaneous tool failures contribute exactly zero" % k, tot == 0.0,
          "sum |contribution| = %.3e" % tot)
allmiss = ["MISSING"] * 12
p_all = float(predict(BUNDLE, np.array([allmiss], dtype=object))[0])
check("all 12 tools MISSING yields a probability, not a crash", isinstance(p_all, float))
check("all 12 tools MISSING is not_selected (no positive evidence)",
      RT.classify_v12(p_all) == "not_selected", "p=%.6f" % p_all)
allfail = ["FAILED"] * 12
p_af = float(predict(BUNDLE, np.array([allfail], dtype=object))[0])
check("all 12 tools FAILED is not_selected", RT.classify_v12(p_af) == "not_selected",
      "p=%.6f" % p_af)
check("out-of-vocabulary call is treated as unavailable, not as a vote",
      float(predict(BUNDLE, np.array([["gibberish"] * 12], dtype=object))[0]) == p_all)

print("\n--- C3. failure states are recorded, orientation, provenance ---")
r_f = RT.call_contig(calls(PlaScope="FAILED"), 0.10, RT.CORE_ARG_ABSENT, BUNDLE)
r_m = RT.call_contig(calls(PlaScope="MISSING"), 0.10, RT.CORE_ARG_ABSENT, BUNDLE)
check("FAILED and MISSING are recorded as distinct states",
      (r_f["n_tools_failed"], r_f["n_tools_missing"]) == (1, 0)
      and (r_m["n_tools_failed"], r_m["n_tools_missing"]) == (0, 1))
check("an unseen FAILED is never converted into a chromosome vote",
      r_f["v12_probability"] != RT.call_contig(calls(), 0.10, RT.CORE_ARG_ABSENT,
                                               BUNDLE)["v12_probability"])
r_plas = RT.call_contig({t: "plasmid" for t in TOOL_ORDER}, 0.99, RT.CORE_ARG_ABSENT, BUNDLE)
r_chrom = RT.call_contig({t: "chromosome" for t in TOOL_ORDER}, 0.01, RT.CORE_ARG_ABSENT, BUNDLE)
check("higher probability means more plasmid-like",
      r_plas["v12_probability"] > r_chrom["v12_probability"],
      "%.6f > %.6f" % (r_plas["v12_probability"], r_chrom["v12_probability"]))
check("unanimous plasmid is selected", r_plas["v12_class"] == "plasmid_selected")
check("unanimous chromosome is not_selected", r_chrom["v12_class"] == "not_selected")
need = {"routed_class", "routing_abstained", "model_selected", "routing_reason",
        "annotation_state", "v11_score", "v11_class", "v12_probability", "v12_class",
        "tool_calls", "v11_threshold", "v12_threshold", "n_tools_failed", "n_tools_missing"}
check("every required provenance field is retained", need <= set(r_plas),
      sorted(need - set(r_plas)))
check("all 12 tool calls are retained verbatim", len(r_plas["tool_calls"]) == 12)
check("scores are never pooled", r_plas["scores_are_not_pooled"] is True)
r_cp1 = RT.call_contig({t: "chromosome" for t in TOOL_ORDER}, 0.99, RT.CORE_ARG_PRESENT, BUNDLE)
check("ARG-bearing contig takes the v1.1 class even when v1.2 disagrees",
      r_cp1["routed_class"] == r_cp1["v11_class"] == "high_confidence_plasmid"
      and r_cp1["v12_class"] == "not_selected")
r_gen = RT.call_contig({t: "plasmid" for t in TOOL_ORDER}, 0.01, RT.CORE_ARG_ABSENT, BUNDLE)
check("non-ARG contig takes the v1.2 class even when v1.1 disagrees",
      r_gen["routed_class"] == r_gen["v12_class"] == "plasmid_selected"
      and r_gen["v11_class"] == "not_selected")

_DR = {"HyAsP": "hyasp", "MOB-recon": "mobsuite", "PLASMe": "plasme", "PlaScope": "plascope",
       "Plasmer": "plasmer", "PlasmidEC": "plasmidec", "PlasmidFinder": "plasmidfinder",
       "Platon": "platon", "RFPlasmid": "rfplasmid", "geNomad": "genomad", "gplas2": "gplas2",
       "plASgraph2": "plasgraph2"}

print("\n--- D. critical-tool completeness gate ---")
import math
check("PlaScope is the prespecified critical tool", EV.CRITICAL_TOOLS == ["PlaScope"])
check("evaluator and preflight name the SAME critical tool across naming spaces",
      {_DR[t] for t in EV.CRITICAL_TOOLS} == set(PF.CRITICAL_TOOLS),
      "evaluator=%s (panel display names), preflight=%s (runner keys)"
      % (EV.CRITICAL_TOOLS, PF.CRITICAL_TOOLS))
check("minimum critical coverage is 95%", EV.CRITICAL_COVERAGE_MIN == 0.95
      and PF.CRITICAL_COVERAGE_MIN == 0.95)
check("denominator is the 79 prespecified isolates", EV.N_PRESPECIFIED_ISOLATES == 79
      and PF.N_PRESPECIFIED_ISOLATES == 79)
_min_iso = math.ceil(EV.CRITICAL_COVERAGE_MIN * EV.N_PRESPECIFIED_ISOLATES)
check("gate arithmetic: 76 of 79 meets the minimum, 75 does not",
      _min_iso == 76 and (76 / 79) >= 0.95 and (75 / 79) < 0.95, "minimum = %d isolates" % _min_iso)
check("at most two retries, identical frozen image/db/command/parameters", PF.MAX_RETRIES == 2)
check("PlasmidFinder/FAILED remains permitted (observed, learned encoding)",
      "FAILED" in EV.PERMITTED_TRAINED_FAILURE_STATES.get("PlasmidFinder", set())
      and "FAILED" in OBS["PlasmidFinder"])
check("no other tool has a permitted trained failure state",
      set(EV.PERMITTED_TRAINED_FAILURE_STATES) == {"PlasmidFinder"})
check("FAILED and MISSING count as unavailable for the gate",
      {"FAILED", "MISSING"} <= EV.UNAVAILABLE_STATES)
check("an unavailable critical tool is never silently treated as a vote",
      "" in EV.UNAVAILABLE_STATES)
check("the 13 frozen scientific command strings are pinned by block hash",
      PF.CMD_BLOCK_HASH == "44f8d17d0b406fccae57423c5111cf55",
      "CMD_BLOCK_HASH=%s" % PF.CMD_BLOCK_HASH)
check("preflight pins the frozen parser version", PF.FROZEN_PARSER_VERSION == "p19c4-parsers/1.7")
# The panel display names (used by the encoding, TOOL_ORDER and the evaluator) and the runner keys
# (used by run_tool.sh, the state markers and the v2 preflight) are two naming spaces for the same
# twelve tools. The mapping is not a string transform - MOB-recon is invoked as "mobsuite" - so it
# is stated explicitly here rather than inferred.
DISPLAY_TO_RUNNER = {"HyAsP": "hyasp", "MOB-recon": "mobsuite", "PLASMe": "plasme",
                     "PlaScope": "plascope", "Plasmer": "plasmer", "PlasmidEC": "plasmidec",
                     "PlasmidFinder": "plasmidfinder", "Platon": "platon",
                     "RFPlasmid": "rfplasmid", "geNomad": "genomad", "gplas2": "gplas2",
                     "plASgraph2": "plasgraph2"}
check("the display-name -> runner-key map covers all 12 panel tools exactly",
      set(DISPLAY_TO_RUNNER) == set(TOOL_ORDER))
check("preflight covers all 12 panel tools plus amrfinder (13 runner keys)",
      set(DISPLAY_TO_RUNNER.values()) | {"amrfinder"} == set(PF.TOOL_TO_IMAGE),
      "%d runner keys" % len(PF.TOOL_TO_IMAGE))
check("every panel tool is classified as external-DB or embedded-DB, none omitted",
      set(PF.EXTERNAL_DB_TOOLS) | set(PF.EMBEDDED_DB_TOOLS) == set(PF.TOOL_TO_IMAGE))
check("no P1.11 fixture imports the superseded preflight",
      "panel_preflight_p111_v2" in PF.__file__ or PF.__name__ == "panel_preflight_p111_v2",
      PF.__name__)

json.dump({"n": len(RES), "n_failed": len(FAILED), "failed": FAILED, "fixtures": RES},
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs",
                            "evidence", "P1.11_ROUTER_FIXTURES_v2.json"), "w"), indent=1)
print("\n%d fixtures, %d failed" % (len(RES), len(FAILED)))
if FAILED:
    sys.exit(1)

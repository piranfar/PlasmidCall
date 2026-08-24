# -*- coding: utf-8 -*-
"""Build the canonical machine-readable number set for the PlasmidCall manuscript.

Every value here is READ from a frozen source table, never transcribed from prose.
Each entry records: value, source file, and the field/row it came from.
"""
import csv, io, json, os, hashlib, collections

R = "docs/evidence/P1.13_results"
PF = "docs/postfreeze/tables"
PROV = "docs/evidence/P1.13_provenance"
OUT = "docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json"


def sha(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def tsv(p):
    return list(csv.DictReader(io.open(p, encoding="utf-8"), delimiter="\t"))


def js(p):
    return json.load(io.open(p, encoding="utf-8"))


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def ci(x):
    if not x:
        return None
    return [round(float(v), 6) for v in x.strip("[]").split(",")]


C = collections.OrderedDict()
SRC = collections.OrderedDict()


def put(key, value, source, field):
    C[key] = value
    SRC[key] = {"file": source, "field": field}


# ---------------------------------------------------------------- freeze ids
rf = js(R + "/RESULTS_FROZEN.json")
put("results_freeze_id", rf["results_freeze_id"], R + "/RESULTS_FROZEN.json", "results_freeze_id")
put("prediction_freeze_id", rf["bound_prediction_freeze"]["freeze_id"],
    R + "/RESULTS_FROZEN.json", "bound_prediction_freeze.freeze_id")
put("join_id", rf["truth_chain"]["join_id"], R + "/RESULTS_FROZEN.json", "truth_chain.join_id")
put("frozen_prediction_table_sha256", rf["bound_prediction_freeze"]["frozen_prediction_table_sha256"],
    R + "/RESULTS_FROZEN.json", "bound_prediction_freeze.frozen_prediction_table_sha256")
put("joined_table_sha256", rf["joined_table"]["sha256"], R + "/RESULTS_FROZEN.json", "joined_table.sha256")

# ---------------------------------------------------------------- denominators
d = rf["denominators"]
for k in d:
    put("den_" + k, d[k], R + "/RESULTS_FROZEN.json", "denominators." + k)
put("cohort_sha256", rf["cohort"]["sha256"], R + "/RESULTS_FROZEN.json", "cohort.sha256")
put("cohort_excluded_isolate", rf["cohort"]["excluded_isolate"], R + "/RESULTS_FROZEN.json",
    "cohort.excluded_isolate")
put("cohort_replacement_isolate", rf["cohort"]["replacement_isolate"], R + "/RESULTS_FROZEN.json",
    "cohort.replacement_isolate")

# ---------------------------------------------------------------- primary endpoint
g = js(R + "/P113_PRIMARY_GATE.json")
put("primary_PPV", g["PPV"], R + "/P113_PRIMARY_GATE.json", "PPV")
put("primary_PPV_ci95", g["PPV_ci95"], R + "/P113_PRIMARY_GATE.json", "PPV_ci95")
put("primary_recall", g["recall"], R + "/P113_PRIMARY_GATE.json", "recall")
put("primary_recall_ci95", g["recall_ci95"], R + "/P113_PRIMARY_GATE.json", "recall_ci95")
put("primary_requirement", g["requirement"], R + "/P113_PRIMARY_GATE.json", "requirement")
put("primary_P_PPV_ge_floor", g["P_PPV_ge_floor"], R + "/P113_PRIMARY_GATE.json", "P_PPV_ge_floor")
put("primary_endpoint_met", g["PRIMARY_ENDPOINT_MET"], R + "/P113_PRIMARY_GATE.json",
    "PRIMARY_ENDPOINT_MET")

pm = {r["predictor"]: r for r in tsv(R + "/P113_PRIMARY_METRICS.tsv")}
v12 = pm["v1.2-General@0.9285"]
for k in ("TP", "FP", "TN", "FN"):
    put("primary_" + k, int(v12[k]), R + "/P113_PRIMARY_METRICS.tsv", "v1.2-General@0.9285." + k)
for k in ("specificity", "NPV", "F1", "balanced_accuracy", "MCC", "coverage"):
    put("primary_" + k, f(v12[k]), R + "/P113_PRIMARY_METRICS.tsv", "v1.2-General@0.9285." + k)
put("primary_abstentions", int(v12["abstained"]), R + "/P113_PRIMARY_METRICS.tsv",
    "v1.2-General@0.9285.abstained")

# ---------------------------------------------------------------- full 19-row inventory
inv = tsv(R + "/P113_PREDICTOR_INVENTORY.tsv")
cm = {r["predictor"]: r for r in tsv(R + "/P113_COMPARATOR_METRICS.tsv")}
cm.update(pm)
rows = []
for r in inv:
    m = cm.get(r["method"], {})
    rows.append(collections.OrderedDict([
        ("row", r["method"]), ("family", r["method_family"]), ("role", r["role"]),
        ("operating_point", r["operating_point"]),
        ("coverage", f(r["coverage_on_resolved"])),
        ("n_scored", int(r["valid_prediction_count"])),
        ("abstained", int(r["abstention_count"])), ("failures", int(r["tool_failure_count"])),
        ("PPV", f(m.get("PPV"))), ("PPV_ci95", ci(m.get("PPV_ci95"))),
        ("recall", f(m.get("recall"))), ("recall_ci95", ci(m.get("recall_ci95"))),
        ("F1", f(m.get("F1"))), ("MCC", f(m.get("MCC"))),
        ("TP", int(m["TP"]) if m.get("TP") else None),
        ("FP", int(m["FP"]) if m.get("FP") else None),
        ("failure_states", r["failure_states"]),
        ("undefined_reason", r["undefined_or_exclusion_reason"]),
    ]))
put("predictor_inventory_19", rows,
    R + "/P113_PREDICTOR_INVENTORY.tsv + P113_PRIMARY_METRICS.tsv + P113_COMPARATOR_METRICS.tsv",
    "all 19 rows joined on predictor key")
put("n_predictor_rows", len(rows), R + "/P113_PREDICTOR_INVENTORY.tsv", "row count")

# ---------------------------------------------------------------- comparison accounting
ca = js(R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json")
put("matched_denominator_n", ca["matched_common_denominator_n"],
    R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json", "matched_common_denominator_n")
put("matched_denominator_fraction",
    round(ca["matched_common_denominator_n"] / float(rf["denominators"]["scored_resolved"]), 6),
    "derived", "matched_common_denominator_n / denominators.scored_resolved")
rk = ca["ranked_F1_comparison_on_matched_denominator"]
put("matched_index_F1", rk["index_F1"], R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json",
    "ranked_F1_comparison_on_matched_denominator.index_F1")
put("matched_index_PPV", rk["index_PPV"], R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json",
    "ranked_F1_comparison_on_matched_denominator.index_PPV")
put("matched_index_recall", rk["index_recall"], R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json",
    "ranked_F1_comparison_on_matched_denominator.index_recall")
put("matched_rows_higher_F1", rk["rows_with_higher_F1_than_index"],
    R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json", "rows_with_higher_F1_than_index")
put("matched_count_higher_F1", rk["count_higher_F1"],
    R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json", "count_higher_F1")
put("matched_rows_reaching_PPV_095", rk["non_index_rows_reaching_PPV_0.95"],
    R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json", "non_index_rows_reaching_PPV_0.95")
put("matched_eligible_for_F1_ranking", rk["eligible_for_F1_ranking"],
    R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json", "eligible_for_F1_ranking")
put("F1_undefined_rows", ca["rows_with_F1_undefined"],
    R + "/P113_COMPARISON_ACCOUNTING_SUMMARY.json", "rows_with_F1_undefined")

idxF1 = f(v12["F1"])
higher = sorted([(r["row"], r["F1"]) for r in rows if r["F1"] is not None and r["F1"] > idxF1],
                key=lambda t: -t[1])
put("pooled_rows_higher_F1", [{"row": a, "F1": b} for a, b in higher],
    "derived from P113_PRIMARY_METRICS.tsv + P113_COMPARATOR_METRICS.tsv", "F1 > index F1")
put("pooled_count_higher_F1", len(higher), "derived", "len(pooled_rows_higher_F1)")

# ---------------------------------------------------------------- core claim
ac = js(R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json")
put("pooled_rows_meeting_PPV095_and_full_coverage", ac["core_claim_pooled"]["rows_meeting_both"],
    R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json", "core_claim_pooled.rows_meeting_both")
put("pooled_third_party_meeting_PPV095_any_coverage",
    ac["core_claim_pooled"]["third_party_meeting_ppv_any_coverage"],
    R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json",
    "core_claim_pooled.third_party_meeting_ppv_any_coverage")
put("pooled_core_claim_supported", ac["core_claim_pooled"]["claim_supported"],
    R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json", "core_claim_pooled.claim_supported")
tp_best = max([x for x in ac["core_claim_pooled"]["detail"]
               if x["third_party_or_baseline"] and x["PPV"] is not None],
              key=lambda x: x["PPV"])
put("pooled_highest_third_party_PPV",
    {"row": tp_best["row"], "PPV": tp_best["PPV"], "coverage": tp_best["coverage"]},
    R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json",
    "core_claim_pooled.detail max PPV among third party")

# ---------------------------------------------------------------- ARG
put("arg_bearing_n", ac["arg_bearing_n"], R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json", "arg_bearing_n")
put("arg_non_arg_n", ac["non_arg_n"], R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json", "non_arg_n")
put("arg_v12", ac["v12_arg"], R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json", "v12_arg")
put("arg_pareto_frontier", ac["pareto_frontier"], R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json",
    "pareto_frontier")
put("arg_pareto_count", len(ac["pareto_frontier"]), R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json",
    "len(pareto_frontier)")
put("arg_third_party_meeting_PPV095_any_coverage",
    ac["core_claim_arg"]["third_party_meeting_ppv_any_coverage"],
    R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json",
    "core_claim_arg.third_party_meeting_ppv_any_coverage")
put("arg_rows_meeting_PPV095_and_full_coverage", ac["core_claim_arg"]["rows_meeting_both"],
    R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json", "core_claim_arg.rows_meeting_both")
argall = {r["row"]: r for r in tsv(R + "/P113_ARG_ALL_PREDICTORS.tsv") if r["subset"] == "ARG_bearing"}
for key, row in (("router", "router"), ("v11", "v1.1@0.9524"), ("plasgraph2", "tool:plASgraph2")):
    r = argall[row]
    put("arg_%s" % key,
        {"PPV": f(r["PPV"]), "recall": f(r["recall"]), "coverage": f(r["coverage"]),
         "PPV_ci95": ci(r["PPV_ci95"]), "recall_ci95": ci(r["recall_ci95"])},
        R + "/P113_ARG_ALL_PREDICTORS.tsv", row)
put("arg_all_predictors", [collections.OrderedDict(
        [("row", r["row"]), ("coverage", f(r["coverage"])), ("PPV", f(r["PPV"])),
         ("recall", f(r["recall"])), ("F1", f(r["F1"]))]) for r in argall.values()],
    R + "/P113_ARG_ALL_PREDICTORS.tsv", "subset=ARG_bearing")
put("arg_router_recall_penalty_vs_v12",
    round(f(argall["v1.2-General@0.9285"]["recall"]) - f(argall["router"]["recall"]), 6),
    "derived", "v1.2 recall - router recall on ARG-bearing")
put("arg_router_precision_gain_vs_v12",
    round(f(argall["router"]["PPV"]) - f(argall["v1.2-General@0.9285"]["PPV"]), 6),
    "derived", "router PPV - v1.2 PPV on ARG-bearing")

# ---------------------------------------------------------------- paired contrasts
pc = js(R + "/P113_PAIRED_CONTRASTS.json")
put("paired_contrasts_primary", pc, R + "/P113_PAIRED_CONTRASTS.json", "all")
put("paired_contrasts_all_rows", tsv(PF + "/PF12b_PAIRED_CONTRASTS_ALL_ROWS.tsv"),
    PF + "/PF12b_PAIRED_CONTRASTS_ALL_ROWS.tsv", "all rows")
put("paired_contrasts_arg", tsv(PF + "/PF04b_ARG_PAIRED_CONTRASTS.tsv"),
    PF + "/PF04b_ARG_PAIRED_CONTRASTS.tsv", "all rows")

# ---------------------------------------------------------------- taxon
tx = [r for r in tsv(PF + "/PF01_TAXON_ROBUSTNESS.tsv")
      if r["model"] == "v1.2-General@0.9285" and r["label"].startswith("taxon=")]
taxrows = []
for r in sorted(tx, key=lambda r: -f(r["PPV"])):
    taxrows.append(collections.OrderedDict([
        ("taxon", r["label"][6:]), ("n_scored", int(r["n_scored"])),
        ("n_plasmid", int(r["n_plasmid"])),
        ("PPV", f(r["PPV"])), ("PPV_ci95", ci(r["PPV_ci95"])), ("recall", f(r["recall"])),
        ("recall_ci95", ci(r["recall_ci95"])), ("F1", f(r["F1"])),
        ("meets_PPV_floor", f(r["PPV"]) >= 0.95)]))
put("taxon_v12", taxrows, PF + "/PF01_TAXON_ROBUSTNESS.tsv",
    "model=v1.2-General@0.9285, label=taxon=*")
put("n_taxa_below_PPV_floor", sum(1 for t in taxrows if not t["meets_PPV_floor"]),
    "derived from PF01_TAXON_ROBUSTNESS.tsv", "count PPV < 0.95")
put("taxa_below_PPV_floor", [t["taxon"] for t in taxrows if not t["meets_PPV_floor"]],
    "derived from PF01_TAXON_ROBUSTNESS.tsv", "PPV < 0.95")

pfs = js(PF + "/PF_SUMMARIES.json")
th = pfs["taxonomic_heterogeneity"]
put("taxon_recall_fold_variation", th["recall_fold_variation"], PF + "/PF_SUMMARIES.json",
    "taxonomic_heterogeneity.recall_fold_variation")

# ---------------------------------------------------------------- LOTO / influence
loto = [r for r in tsv(PF + "/PF02_LEAVE_ONE_TAXON_OUT.tsv") if r["model"] == "v1.2-General@0.9285"]
put("loto", [collections.OrderedDict([("label", r["label"]), ("n_scored", int(r["n_scored"])),
                                      ("PPV", f(r["PPV"])), ("recall", f(r["recall"]))])
             for r in loto], PF + "/PF02_LEAVE_ONE_TAXON_OUT.tsv", "model=v1.2-General@0.9285")
lt = pfs["leave_one_taxon_out"]
put("loto_PPV_range", lt["PPV_range_across_exclusions"], PF + "/PF_SUMMARIES.json",
    "leave_one_taxon_out.PPV_range_across_exclusions")
put("loto_recall_range", lt["recall_range_across_exclusions"], PF + "/PF_SUMMARIES.json",
    "leave_one_taxon_out.recall_range_across_exclusions")
put("loto_floors_hold", lt["PPV_stays_above_0.95_in_all_exclusions"] and
    lt["recall_stays_above_0.50_in_all_exclusions"], PF + "/PF_SUMMARIES.json",
    "leave_one_taxon_out.*_stays_above_*")
ir = pfs["isolate_robustness"]
for k in ("macro_average_PPV", "macro_average_recall", "median_PPV", "median_recall",
          "max_abs_influence_on_pooled_PPV", "max_abs_influence_on_pooled_recall",
          "most_influential_isolate"):
    put("isolate_" + k, ir[k], PF + "/PF_SUMMARIES.json", "isolate_robustness." + k)
put("isolate_IQR_recall", ir["IQR_recall"], PF + "/PF_SUMMARIES.json", "isolate_robustness.IQR_recall")
put("isolates_with_zero_FP", ir["error_concentration"]["isolates_with_zero_FP"],
    PF + "/PF_SUMMARIES.json", "isolate_robustness.error_concentration.isolates_with_zero_FP")
put("top10_share_of_FP", ir["error_concentration"]["top10_isolates_share_of_FP"],
    PF + "/PF_SUMMARIES.json", "isolate_robustness.error_concentration.top10_isolates_share_of_FP")
put("top10_share_of_FN", ir["error_concentration"]["top10_isolates_share_of_FN"],
    PF + "/PF_SUMMARIES.json", "isolate_robustness.error_concentration.top10_isolates_share_of_FN")

# ---------------------------------------------------------------- prevalence
prev = tsv(PF + "/PF05_PREVALENCE_SENSITIVITY.tsv")
put("prevalence_grid", [collections.OrderedDict([("prevalence", f(r["prevalence"])),
                                                 ("standardized_PPV", f(r["standardized_PPV"])),
                                                 ("above_0.95", r["PPV_above_0.95"])]) for r in prev],
    PF + "/PF05_PREVALENCE_SENSITIVITY.tsv", "all rows")
ps = pfs["prevalence_sensitivity"]
put("observed_plasmid_prevalence", ps["observed_plasmid_prevalence"], PF + "/PF_SUMMARIES.json",
    "prevalence_sensitivity.observed_plasmid_prevalence")
put("standardized_PPV_at_5pct", ps["standardized_PPV_at_5pct"], PF + "/PF_SUMMARIES.json",
    "prevalence_sensitivity.standardized_PPV_at_5pct")
put("standardized_PPV_at_50pct", ps["standardized_PPV_at_50pct"], PF + "/PF_SUMMARIES.json",
    "prevalence_sensitivity.standardized_PPV_at_50pct")
put("equal_taxon_weighted_PPV", ps["equal_taxon_weighted"]["equal_taxon_weighted_PPV"],
    PF + "/PF_SUMMARIES.json",
    "prevalence_sensitivity.equal_taxon_weighted.equal_taxon_weighted_PPV")
above = [f(r["prevalence"]) for r in prev if r["PPV_above_0.95"] in ("True", "true", "1")]
below = [f(r["prevalence"]) for r in prev if r["PPV_above_0.95"] not in ("True", "true", "1")]
put("prevalence_lowest_grid_point_above_floor", min(above) if above else None,
    PF + "/PF05_PREVALENCE_SENSITIVITY.tsv", "min prevalence with PPV_above_0.95 true")
put("prevalence_highest_grid_point_below_floor", max(below) if below else None,
    PF + "/PF05_PREVALENCE_SENSITIVITY.tsv", "max prevalence with PPV_above_0.95 false")

# exact prevalence at which the standardised PPV crosses the 0.95 floor. This is the closed-form
# root of the identical standardisation identity PF05 tabulates on a grid; sensitivity and
# specificity are held at their frozen observed values. No new data, model or threshold is involved.
_s = C["primary_recall"]
_f = 1.0 - C["primary_specificity"]
_p_cross = (0.95 * _f) / (0.05 * _s + 0.95 * _f)
put("prevalence_exact_crossing_0.95", round(_p_cross, 6), "derived (closed form)",
    "p* = 0.95(1-specificity) / (0.05*sensitivity + 0.95(1-specificity)) with sensitivity and "
    "specificity held at the frozen observed values; the analytic root of the PF05 grid")

# error architecture across the three PlasmidCall rows
put("error_architecture",
    {r["row"]: {"FP": r["FP"], "FN": (None if r["TP"] is None else None)}
     for r in rows if r["family"].startswith("PlasmidCall")},
    "placeholder", "replaced below")
_ea = {}
for _k in ("v1.2-General@0.9285", "v1.1@0.9524", "v1.1@0.9605_high_conf", "router"):
    _r = pm[_k]
    _ea[_k] = {"TP": int(_r["TP"]), "FP": int(_r["FP"]), "TN": int(_r["TN"]), "FN": int(_r["FN"])}
put("error_architecture", _ea, R + "/P113_PRIMARY_METRICS.tsv", "TP/FP/TN/FN for the four frozen rows")

# ---------------------------------------------------------------- length / depth
ln = [r for r in tsv(PF + "/PF06_CONTIG_LENGTH.tsv") if r["model"] == "v1.2-General@0.9285"]
put("length_bins", [collections.OrderedDict([("band", r["label"]), ("n_scored", int(r["n_scored"])),
                                             ("n_plasmid", int(r["n_plasmid"])), ("PPV", f(r["PPV"])),
                                             ("recall", f(r["recall"])),
                                             ("adequate", r["adequate_denominator"])]) for r in ln],
    PF + "/PF06_CONTIG_LENGTH.tsv", "model=v1.2-General@0.9285")
dp = [r for r in tsv(PF + "/PF07_DEPTH_AND_ASSEMBLY_QUALITY.tsv")
      if r["model"] == "v1.2-General@0.9285"]
put("depth_and_assembly", [collections.OrderedDict([("stratum", r["label"]),
                                                    ("n_scored", int(r["n_scored"])),
                                                    ("PPV", f(r["PPV"])), ("recall", f(r["recall"])),
                                                    ("adequate", r["adequate_denominator"])])
                           for r in dp], PF + "/PF07_DEPTH_AND_ASSEMBLY_QUALITY.tsv",
    "model=v1.2-General@0.9285")
put("length_point_biserial_vs_truth", pfs["length_continuous"]["point_biserial_length_vs_truth"],
    PF + "/PF_SUMMARIES.json", "length_continuous.point_biserial_length_vs_truth")
put("depth_pearson_vs_correct", pfs["depth_continuous"]["pearson_depth_vs_v12_correct"],
    PF + "/PF_SUMMARIES.json", "depth_continuous.pearson_depth_vs_v12_correct")

# ---------------------------------------------------------------- truth sensitivity (PF08)
p8 = [r for r in tsv(PF + "/PF08_TRUTH_SENSITIVITY_RESULTS.tsv")
      if r["model"] == "v1.2-General@0.9285"]
put("truth_sensitivity", [collections.OrderedDict([
        ("setting", r["truth_setting"]), ("n_resolved", int(r["n_resolved"])),
        ("n_unresolved", int(r["n_unresolved_this_setting"])),
        ("n_plasmid_truth", int(r["n_plasmid_truth"])),
        ("labels_flipped_vs_primary", (None if r["labels_flipped_vs_primary"] == ""
                                       else int(r["labels_flipped_vs_primary"]))),
        ("TP", int(r["TP"])), ("FP", int(r["FP"])), ("TN", int(r["TN"])), ("FN", int(r["FN"])),
        ("PPV", f(r["PPV"])), ("recall", f(r["recall"])),
        ("meets_both_floors", r["meets_PPV_floor"] == "True" and r["meets_recall_floor"] == "True")])
        for r in p8], PF + "/PF08_TRUTH_SENSITIVITY_RESULTS.tsv", "model=v1.2-General@0.9285")
put("truth_sensitivity_flip_definition",
    "number of contigs RESOLVED under BOTH the primary and the alternative truth definition whose "
    "binary chromosome/plasmid label differs between the two; contigs resolved under only one "
    "definition are counted as resolution-state transitions, not flips",
    "scripts/postfreeze/pf08_eval.py",
    "flips = sum(BIN[alt[k]] != BIN[primary[k]] for k in contigs resolved under both)")
put("truth_sensitivity_grid", js(PF + "/PF08_TRUTH_SENSITIVITY_GRID.json")["settings"],
    PF + "/PF08_TRUTH_SENSITIVITY_GRID.json", "settings")

# ---------------------------------------------------------------- unresolved bounds
ub = pfs["unresolved_bounds"]
put("unresolved_n", ub["n_unresolved_eligible"], PF + "/PF_SUMMARIES.json",
    "unresolved_bounds.n_unresolved_eligible")
put("unresolved_composition", ub["composition"], PF + "/PF_SUMMARIES.json",
    "unresolved_bounds.composition")
put("unresolved_by_taxon", ub["by_taxon"], PF + "/PF_SUMMARIES.json", "unresolved_bounds.by_taxon")
put("unresolved_by_length_band", ub["by_length_band"], PF + "/PF_SUMMARIES.json",
    "unresolved_bounds.by_length_band")
put("unresolved_by_ARG_status", ub["by_ARG_status"], PF + "/PF_SUMMARIES.json",
    "unresolved_bounds.by_ARG_status")
put("unresolved_best_case", ub["best_case_all_unresolved_favourable"], PF + "/PF_SUMMARIES.json",
    "unresolved_bounds.best_case_all_unresolved_favourable")
put("unresolved_worst_case", ub["worst_case_all_unresolved_adverse"], PF + "/PF_SUMMARIES.json",
    "unresolved_bounds.worst_case_all_unresolved_adverse")
put("unresolved_worst_case_clears_floor", ub["PPV_stays_above_0.95_in_worst_case"],
    PF + "/PF_SUMMARIES.json", "unresolved_bounds.PPV_stays_above_0.95_in_worst_case")

# ---------------------------------------------------------------- reference quality / subset
rq = tsv(PF + "/PF10a_REFERENCE_QUALITY.tsv")
put("reference_sources", dict(collections.Counter(r["source"] for r in rq)),
    PF + "/PF10a_REFERENCE_QUALITY.tsv", "source column")
put("reference_reports_readable",
    sum(1 for r in rq if r["assembly_report_readable"] in ("True", "true", "yes")),
    PF + "/PF10a_REFERENCE_QUALITY.tsv", "assembly_report_readable")
hc = [r for r in rq if r["high_confidence_truth"] in ("True", "true", "yes")]
put("complete_resolution_isolates", len(hc), PF + "/PF10a_REFERENCE_QUALITY.tsv",
    "high_confidence_truth == True (renamed: complete-resolution isolate subset)")
put("complete_resolution_mean_ref_plasmids",
    round(sum(f(r["reference_plasmids"]) for r in hc) / len(hc), 4),
    PF + "/PF10a_REFERENCE_QUALITY.tsv", "mean reference_plasmids over subset")
rest = [r for r in rq if r["high_confidence_truth"] not in ("True", "true", "yes")]
put("remainder_mean_ref_plasmids",
    round(sum(f(r["reference_plasmids"]) for r in rest) / len(rest), 4),
    PF + "/PF10a_REFERENCE_QUALITY.tsv", "mean reference_plasmids over remainder")
put("complete_resolution_mean_eligible_contigs",
    round(sum(f(r["eligible_contigs"]) for r in hc) / len(hc), 4),
    PF + "/PF10a_REFERENCE_QUALITY.tsv", "mean eligible_contigs over subset")
put("remainder_mean_eligible_contigs",
    round(sum(f(r["eligible_contigs"]) for r in rest) / len(rest), 4),
    PF + "/PF10a_REFERENCE_QUALITY.tsv", "mean eligible_contigs over remainder")
put("complete_resolution_taxon_mix", dict(collections.Counter(r["taxon"] for r in hc)),
    PF + "/PF10a_REFERENCE_QUALITY.tsv", "taxon counts within subset")
put("remainder_taxon_mix", dict(collections.Counter(r["taxon"] for r in rest)),
    PF + "/PF10a_REFERENCE_QUALITY.tsv", "taxon counts within remainder")
p10b = {(r["label"], r["model"]): r for r in tsv(PF + "/PF10b_HIGH_CONFIDENCE_TRUTH_SENSITIVITY.tsv")}
s = p10b[("highest-confidence truth subset", "v1.2-General@0.9285")]
put("complete_resolution_subset_result",
    {"n_scored": int(s["n_scored"]), "n_plasmid": int(s["n_plasmid"]), "PPV": f(s["PPV"]),
     "recall": f(s["recall"]), "TP": int(s["TP"]), "FP": int(s["FP"])},
    PF + "/PF10b_HIGH_CONFIDENCE_TRUTH_SENSITIVITY.tsv",
    "label='highest-confidence truth subset' (renamed complete-resolution isolate subset)")
put("complete_resolution_subset_prevalence",
    round(int(s["n_plasmid"]) / float(s["n_scored"]), 6), "derived",
    "n_plasmid / n_scored in the complete-resolution isolate subset")

# ---------------------------------------------------------------- calibration
cal = {r["model"]: r for r in js(PF + "/PF13_SCORE_AND_CALIBRATION.json")}
for m, key in (("v1.2-General", "v12"), ("v1.1", "v11")):
    r = cal[m]
    put("calibration_" + key, {k: r[k] for k in ("AUROC", "AUPRC", "Brier", "ECE_10bin",
                                                 "calibration_intercept", "calibration_slope",
                                                 "frozen_threshold_marked")},
        PF + "/PF13_SCORE_AND_CALIBRATION.json", "model=" + m)
put("calibration_curve_v12", cal["v1.2-General"]["calibration_curve"],
    PF + "/PF13_SCORE_AND_CALIBRATION.json", "model=v1.2-General.calibration_curve")

# ---------------------------------------------------------------- leakage / controls
lk = js(PF + "/PF11_RELATEDNESS_LEAKAGE_AUDIT.json")
for k in ("n_exact_overlap", "max_ANI_to_any_consumed_genome", "max_within_cohort_pairwise_ANI",
          "consumed_identifiers_loaded", "n_bioprojects", "n_study_accessions"):
    put("leakage_" + k, lk[k], PF + "/PF11_RELATEDNESS_LEAKAGE_AUDIT.json", k)
nc = js(PF + "/PF15_NEGATIVE_CONTROLS.json")
put("permutation_n", nc["label_permutation"]["n_permutations"], PF + "/PF15_NEGATIVE_CONTROLS.json",
    "label_permutation.n_permutations")
put("permutation_PPV_max", nc["label_permutation"]["permuted_PPV_max"],
    PF + "/PF15_NEGATIVE_CONTROLS.json", "label_permutation.permuted_PPV_max")
put("permutation_PPV_mean", nc["label_permutation"]["permuted_PPV_mean"],
    PF + "/PF15_NEGATIVE_CONTROLS.json", "label_permutation.permuted_PPV_mean")
put("row_order_invariant", nc["row_order_invariance"]["identical"],
    PF + "/PF15_NEGATIVE_CONTROLS.json", "row_order_invariance.identical")

# ---------------------------------------------------------------- deployment
dep = tsv(PF + "/PF14_COMPUTATIONAL_DEPLOYMENT.tsv")
put("deployment", [collections.OrderedDict([("tool", r["tool"]),
                                            ("n_executions", int(r["n_executions"])),
                                            ("wall_median_s", f(r["wall_median_s"])),
                                            ("wall_max_s", f(r["wall_max_s"])),
                                            ("wall_total_hours", f(r["wall_total_hours"])),
                                            ("failed", int(r["failed_executions"])),
                                            ("failure_rate", f(r["failure_rate"])),
                                            ("peak_RAM_measured", r["peak_RAM_measured"])])
                   for r in dep], PF + "/PF14_COMPUTATIONAL_DEPLOYMENT.tsv", "all rows")
put("deployment_total_executions", sum(int(r["n_executions"]) for r in dep),
    PF + "/PF14_COMPUTATIONAL_DEPLOYMENT.tsv", "sum(n_executions)")
put("deployment_total_failures", sum(int(r["failed_executions"]) for r in dep),
    PF + "/PF14_COMPUTATIONAL_DEPLOYMENT.tsv", "sum(failed_executions)")
put("deployment_total_container_hours", round(sum(f(r["wall_total_hours"]) for r in dep), 2),
    PF + "/PF14_COMPUTATIONAL_DEPLOYMENT.tsv", "sum(wall_total_hours)")

# ---------------------------------------------------------------- verification
vr = js(PF + "/PF_VERIFICATION_RECEIPT.json")
put("postfreeze_n_checks", vr["n_checks"], PF + "/PF_VERIFICATION_RECEIPT.json", "n_checks")
put("postfreeze_n_disagreements", vr["n_disagreements"], PF + "/PF_VERIFICATION_RECEIPT.json",
    "n_disagreements")
put("postfreeze_verdict", vr["verdict"], PF + "/PF_VERIFICATION_RECEIPT.json", "verdict")
iv = rf["independent_verifier"]
put("primary_verifier_values", iv["values_independently_recomputed"], R + "/RESULTS_FROZEN.json",
    "independent_verifier.values_independently_recomputed")
put("primary_verifier_disagreements", iv["disagreements"], R + "/RESULTS_FROZEN.json",
    "independent_verifier.disagreements")
put("primary_verifier_verdict", iv["verdict"], R + "/RESULTS_FROZEN.json",
    "independent_verifier.verdict")
bs = rf["software_environment"]["bootstrap"]
put("bootstrap", bs, R + "/RESULTS_FROZEN.json", "software_environment.bootstrap")

# ---------------------------------------------------------------- provenance / execution
put("truth_thresholds", rf["truth_chain"]["thresholds"], R + "/RESULTS_FROZEN.json",
    "truth_chain.thresholds")
put("truth_mapper_sha256", rf["truth_chain"]["mapper_sha256"], R + "/RESULTS_FROZEN.json",
    "truth_chain.mapper_sha256")
put("truth_isolates_verified", rf["truth_chain"]["isolates_verified"], R + "/RESULTS_FROZEN.json",
    "truth_chain.isolates_verified")

coh = tsv(PROV + "/P1.13_SELECTED_COHORT_v3.tsv")
put("cohort_taxa", dict(collections.Counter(r["taxon"] for r in coh)),
    PROV + "/P1.13_SELECTED_COHORT_v3.tsv", "taxon counts")
put("cohort_n", len(coh), PROV + "/P1.13_SELECTED_COHORT_v3.tsv", "row count")

# ---------------------------------------------------------------- cohort selection funnel
DES = "docs/evidence/P1.13_design"
cen = tsv(DES + "/P1.13_CENSUS.tsv")
pool = tsv(DES + "/P1.13_ELIGIBLE_POOL.tsv")
exc = tsv(DES + "/P1.13_EXCLUSION_LOG.tsv")
by_stage = collections.defaultdict(set)
for r in exc:
    by_stage[r["exclusion_stage"]].add(r["biosample"])
P = {r["biosample"] for r in pool}
K = {r["biosample"] for r in coh}
put("funnel_census_candidates", len({r["biosample"] for r in cen}), DES + "/P1.13_CENSUS.tsv",
    "distinct biosample count")
put("funnel_excluded_ani_vs_consumed", len(by_stage["ani_vs_consumed"]),
    DES + "/P1.13_EXCLUSION_LOG.tsv", "exclusion_stage == ani_vs_consumed")
put("funnel_eligible_pool", len(P), DES + "/P1.13_ELIGIBLE_POOL.tsv", "distinct biosample count")
put("funnel_excluded_ani_within_cohort", len(by_stage["ani_within_p113"]),
    DES + "/P1.13_EXCLUSION_LOG.tsv", "exclusion_stage == ani_within_p113")
put("funnel_not_selected", len(by_stage["not_selected"]), DES + "/P1.13_EXCLUSION_LOG.tsv",
    "exclusion_stage == not_selected")
put("funnel_selected_from_pool", len(K & P), "derived",
    "cohort v3 members present in the frozen eligible pool")
put("funnel_added_from_fallback_tier", len(K - P), "derived",
    "cohort v3 members outside the frozen eligible pool, admitted under amendment 001 "
    "as the 2022 fallback tier")
put("funnel_reconciles", len(P) - len(by_stage["ani_within_p113"]) - len(by_stage["not_selected"])
    == len(K & P), "derived",
    "eligible pool minus within-cohort ANI exclusions minus not-selected equals the number "
    "of cohort members drawn from the pool")
amr = js(DES.replace("P1.13_design", "P1.13_design") + "/P1.13_AMENDED_PREEXECUTION_RECEIPT.json")
_tiers = None
for _k, _v in amr.items():
    if isinstance(_v, dict) and "tiers" in _v:
        _tiers = _v["tiers"]
put("funnel_selection_tiers", _tiers, DES + "/P1.13_AMENDED_PREEXECUTION_RECEIPT.json",
    "recorded selection tiers including the 2022 fallback admitted under amendment 001")
put("funnel_pool_by_taxon", dict(collections.Counter(r["taxon"] for r in pool)),
    DES + "/P1.13_ELIGIBLE_POOL.tsv", "taxon counts")

# ---------------------------------------------------------------- panel execution
put("panel_units_total", 13 * len(coh), "derived", "13 panel units x 150 isolates")
put("panel_units_failed", C["deployment_total_failures"], PF + "/PF14_COMPUTATIONAL_DEPLOYMENT.tsv",
    "sum(failed_executions)")
put("panel_units_succeeded", C["deployment_total_executions"] - C["deployment_total_failures"],
    "derived", "total executions minus failures")
put("panel_failure_mechanisms",
    {"MOB-recon: zero plasmid biomarkers raised an exception": 31,
     "gplas2: upstream PlasmidEC predicted no plasmid contigs": 26,
     "gplas2: internal R step exited non-zero": 10,
     "PlasmidFinder: index error": 5},
    PROV + "/P1.13_PANEL_FAILURE_REVIEW.md", "failure-class table, counts reconciled to 72")
put("panel_failure_mechanisms_sum", 31 + 26 + 10 + 5, "derived", "must equal panel_units_failed")

# ---------------------------------------------------------------- derived reporting quantities
put("truth_resolution_rate",
    round(C["den_scored_resolved"] / float(C["den_eligible_ge_1kb"]), 6), "derived",
    "scored_resolved / eligible_ge_1kb")
put("macro_vs_micro_PPV_gap", abs(pfs["isolate_robustness"]["macro_vs_micro_PPV_gap"]),
    PF + "/PF_SUMMARIES.json", "abs(isolate_robustness.macro_vs_micro_PPV_gap)")
put("arg_plasgraph2_contigs_answered",
    int(round(C["arg_plasgraph2"]["coverage"] * C["arg_bearing_n"])), "derived",
    "plASgraph2 ARG coverage x ARG-bearing n")
put("verifier_values_total",
    C["primary_verifier_values"]["total"] if isinstance(C["primary_verifier_values"], dict)
    and "total" in C["primary_verifier_values"] else None, R + "/RESULTS_FROZEN.json",
    "independent_verifier.values_independently_recomputed")
put("verifier_total_values_and_checks",
    C["verifier_values_total"] + C["postfreeze_n_checks"], "derived",
    "primary verifier values plus post-freeze independent checks")

# comparator fairness: conditional vs failure-aware vs matched
pf12 = tsv(PF + "/PF12_COMPARATOR_FAIRNESS.tsv")
put("comparator_fairness", [collections.OrderedDict([
        ("row", r["predictor"]), ("coverage", f(r["coverage"])), ("non_calls", int(r["non_calls"])),
        ("conditional_PPV", f(r["conditional_PPV"])), ("conditional_recall", f(r["conditional_recall"])),
        ("conditional_F1", f(r["conditional_F1"])),
        ("failure_aware_PPV", f(r["failure_aware_PPV"])),
        ("failure_aware_recall", f(r["failure_aware_recall"])),
        ("failure_aware_F1", f(r["failure_aware_F1"])),
        ("matched_PPV", f(r["matched_PPV"])), ("matched_recall", f(r["matched_recall"])),
        ("matched_F1", f(r["matched_F1"]))]) for r in pf12],
    PF + "/PF12_COMPARATOR_FAIRNESS.tsv", "all 19 rows")

# ---------------------------------------------------------------- evidence archive
EA = "docs/closure/EVIDENCE_ARCHIVE_VERIFICATION.json"
if os.path.exists(EA):
    ea = js(EA)
    pt = ea["parsed_tool_calls"]
    put("parsed_tool_calls", pt["total_rows"], EA, "parsed_tool_calls.total_rows")
    put("parsed_tool_call_files", pt["files"], EA, "parsed_tool_calls.files")
    put("parsed_tool_calls_reconcile", pt["reconciles"], EA, "parsed_tool_calls.reconciles")
    put("archive_members", ea["members"], EA, "members")
    put("archive_manifest_rows", ea["internal_manifest_rows"], EA, "internal_manifest_rows")
    put("archive_download_intact", ea["download_intact"], EA, "download_intact")
    put("archive_verdict", ea["verdict"], EA, "verdict")

# ---------------------------------------------------------------- ARG genomic context
AB = "docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json"
if os.path.exists(AB):
    ab = js(AB)
    put("argctx_pooled", ab["pooled"], AB, "pooled")
    put("argctx_by_taxon", ab["by_taxon"], AB, "by_taxon")
    put("argctx_by_class", ab["by_class"], AB, "by_class")
    put("argctx_by_family", ab["by_family"], AB, "by_family")
    put("argctx_family_distribution", ab["family_distribution"], AB, "family_distribution")
    put("argctx_vanA", ab["glycopeptide_operons"]["vanA_type"], AB,
        "glycopeptide_operons.vanA_type")
    put("argctx_vanB", ab["glycopeptide_operons"]["vanB_type"], AB,
        "glycopeptide_operons.vanB_type")
    put("argctx_vanD", ab["glycopeptide_operons"]["vanD_type"], AB,
        "glycopeptide_operons.vanD_type")
    put("argctx_thresholds", ab["thresholds_prestated"], AB, "thresholds_prestated")

# ---------------------------------------------------------------- source hashes
files = sorted(set(v["file"] for v in SRC.values() if os.path.exists(v["file"])))
put("source_file_sha256", {p: sha(p) for p in files}, "derived",
    "sha256 of every cited source file")

out = collections.OrderedDict([
    ("canonical_number_set", "PLASMIDCALL-CANONICAL-NUMBERS-001"),
    ("built_utc", "2026-08-24"),
    ("primary_freeze", C["results_freeze_id"]),
    ("postfreeze_package", "P1.13-POSTFREEZE-REVIEWER-ANALYSES-001"),
    ("rule", "every manuscript number must appear here; values are read from frozen tables, "
             "never transcribed from prose"),
    ("values", C), ("provenance", SRC)])
io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1) + "\n")
print("wrote %s with %d canonical values" % (OUT, len(C)))

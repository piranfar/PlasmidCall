#!/usr/bin/env python3
"""P1.11 EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT -- section 6: manuscript-ready outputs.

Builds the main-text confirmatory table, the twelve-tool comparison, the supplementary tables and
the figure-ready data. Presentation follows the frozen presentation_rules of
docs/plans/P1.11_PRE_TRUTH_EVALUATION_ADDENDUM.yaml: confirmatory estimands lead, secondary and
exploratory results follow and are labelled, and no new composite ranking is invented.
"""
import collections, csv, glob, io, json, math, os, sys
import numpy as np

P = "/work/p112"; S = "/work/p111"
OUT = P + "/POSTTRUTH"; TB = OUT + "/manuscript"
LABEL = "EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT"
N_BOOT, SEED = 4000, 20260821
TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC", "PlasmidFinder",
         "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
CONF = {"n": 7244, "TP": 942, "FP": 33, "TN": 6002, "FN": 267}
os.makedirs(TB, exist_ok=True)


def rd(p):
    return csv.DictReader(io.open(p, encoding="utf-8", errors="replace"), delimiter="\t")


def fnum(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def mets(y, c):
    y = np.asarray(y); c = np.asarray(c)
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    tn = int(((c == 0) & (y == 0)).sum()); fn = int(((c == 0) & (y == 1)).sum())
    ppv = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * ppv * rec / (ppv + rec) if (ppv and rec and ppv + rec > 0) else None
    npos = int((y == 1).sum()); nev = tp + fp + tn + fn
    return {"n_eligible": int(len(y)), "n_evaluable": nev, "n_abstain": int(len(y)) - nev,
            "coverage": nev / len(y) if len(y) else None, "n_truth_positive": npos,
            "TP": tp, "FP": fp, "TN": tn, "FN": fn, "selective_PPV": ppv, "selective_recall": rec,
            "specificity": tn / (tn + fp) if tn + fp else None, "selective_F1": f1,
            "deployment_yield": tp / npos if npos else None}


def boot(y, g, c):
    y = np.asarray(y); g = np.asarray(g); c = np.asarray(c); iso = sorted(set(g.tolist()))
    idx = {i: np.where(g == i)[0] for i in iso}; rng = np.random.default_rng(SEED)
    acc = collections.defaultdict(list)
    for _ in range(N_BOOT):
        r = np.concatenate([idx[i] for i in rng.choice(iso, size=len(iso), replace=True)])
        m = mets(y[r], c[r])
        for k in ("selective_PPV", "selective_recall", "selective_F1", "specificity",
                  "deployment_yield", "coverage"):
            if m[k] is not None:
                acc[k].append(m[k])
    return {k: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
            for k, v in acc.items() if v}


def fmt(v, nd=4):
    return "" if v is None else ("%.*f" % (nd, v))


def ci(d, k):
    v = d.get(k)
    return "" if not v else "[%.4f, %.4f]" % (v[0], v[1])


def wtsv(path, rows, cols=None):
    cols = cols or list(rows[0].keys())
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader(); w.writerows(rows)


# ---------------------------------------------------------------- load
predk = {(r["sample"], r["contig_id"]): r for r in
         rd(P + "/inference/frozen/P1.11_FROZEN_PREDICTIONS.tsv")}
truth = {}
for f in sorted(glob.glob(P + "/truth/*/truth_table.tsv")):
    for r in rd(f):
        truth[(r["sample"], r["contig_id"])] = r
prov = collections.defaultdict(dict)
for r in rd(P + "/inference/P1.11_call_table_reconciled.tsv"):
    prov[r["tool"]][(r["sample"], r["contig_id"])] = r["provenance_state"]
keys = sorted(k for k, r in predk.items()
              if r["is_eligible_ge_1kb"] == "1"
              and truth.get(k, {}).get("final_truth_label") in ("plasmid", "chromosome"))
y = np.array([1 if truth[k]["final_truth_label"] == "plasmid" else 0 for k in keys])
g = np.array([k[0] for k in keys])
L = np.array([int(predk[k]["contig_length"]) for k in keys])
arg = np.array([predk[k]["ARG_bearing_bool"] == "true" for k in keys])
s12 = np.array([fnum(predk[k]["v12_score"]) for k in keys], dtype=float)
s11 = np.array([fnum(predk[k]["v11_score"]) for k in keys], dtype=float)
POS = {"plasmid_selected", "high_confidence_plasmid"}
c12 = np.array([1 if predk[k]["v12_call"] == "plasmid_selected"
                else (0 if predk[k]["v12_score_state"] == "available" else -1) for k in keys])
c11 = np.array([1 if predk[k]["v11_call"] in POS
                else (0 if predk[k]["v11_score_state"] == "available" else -1) for k in keys])
c11h = np.array([1 if predk[k]["v11_call"] == "high_confidence_plasmid"
                 else (0 if predk[k]["v11_score_state"] == "available" else -1) for k in keys])
crt = np.array([1 if predk[k]["router_call"] in POS
                else (0 if predk[k]["router_state"] == "routed" else -1) for k in keys])
tcall = {t: np.array([1 if predk[k][t] == "plasmid" else (0 if predk[k][t] == "chromosome" else -1)
                      for k in keys]) for t in TOOLS}
m0 = mets(y, c12)
got = {"n": len(keys), "TP": m0["TP"], "FP": m0["FP"], "TN": m0["TN"], "FN": m0["FN"]}
if got != CONF:
    sys.exit("REFUSING: confirmatory result not reproduced: %s" % got)
print("  GATE PASS %s" % got)
s15 = json.load(io.open(OUT + "/P1.11_POSTTRUTH_SECTIONS_1_5.json", encoding="utf-8"))
s1b = json.load(io.open(OUT + "/P1.11_POSTTRUTH_SECTION_1B_LEAKAGE.json", encoding="utf-8"))

# ---------------------------------------------------------------- Table 1: confirmatory
METHODS = [("PlasmidCall v1.2-General", "0.9285", c12, "CONFIRMATORY primary"),
           ("PlasmidCall router (v1.2-General / v1.1)", "frozen router", crt, "CONFIRMATORY"),
           ("PlasmidCall v1.1", "0.9524 (standard)", c11, "CONFIRMATORY"),
           ("PlasmidCall v1.1", "0.9605 (high-confidence)", c11h, "CONFIRMATORY")]
t1 = []
for nm, th, cc, tier in METHODS:
    m = mets(y, cc); b = boot(y, g, cc)
    t1.append({"method": nm, "operating_point": th, "evidence_tier": tier,
               "n_eligible": m["n_eligible"], "n_evaluable": m["n_evaluable"],
               "coverage": fmt(m["coverage"]), "n_truth_positive": m["n_truth_positive"],
               "TP": m["TP"], "FP": m["FP"], "TN": m["TN"], "FN": m["FN"],
               "selective_PPV": fmt(m["selective_PPV"]), "selective_PPV_CI95": ci(b, "selective_PPV"),
               "selective_recall": fmt(m["selective_recall"]),
               "selective_recall_CI95": ci(b, "selective_recall"),
               "selective_F1": fmt(m["selective_F1"]), "selective_F1_CI95": ci(b, "selective_F1"),
               "specificity": fmt(m["specificity"]), "deployment_yield": fmt(m["deployment_yield"])})
wtsv(TB + "/Table1_confirmatory_primary_result.tsv", t1)

# ---------------------------------------------------------------- Table 2: twelve tools
t2 = []
for t in TOOLS:
    m = mets(y, tcall[t]); b = boot(y, g, tcall[t])
    pv = collections.Counter(prov.get(t, {}).get(k, "") for k in keys)
    t2.append({"method": t, "kind": "comparator tool", "evidence_tier": "PRESPECIFIED_SECONDARY",
               "n_eligible": m["n_eligible"], "n_evaluable": m["n_evaluable"],
               "n_tool_abstain": m["n_abstain"], "coverage": fmt(m["coverage"]),
               "TP": m["TP"], "FP": m["FP"], "TN": m["TN"], "FN": m["FN"],
               "selective_PPV": fmt(m["selective_PPV"]), "selective_PPV_CI95": ci(b, "selective_PPV"),
               "selective_recall": fmt(m["selective_recall"]),
               "selective_recall_CI95": ci(b, "selective_recall"),
               "selective_F1": fmt(m["selective_F1"]), "specificity": fmt(m["specificity"]),
               "deployment_yield": fmt(m["deployment_yield"]),
               "deployment_yield_note": "comparable with the P1.10 published tool `recall`",
               "provenance_OK": pv.get("OK", 0), "provenance_RECOVERED_OK": pv.get("RECOVERED_OK", 0),
               "provenance_FAILED": pv.get("FAILED", 0)})
for nm, th, cc, _tier in METHODS[:2]:
    m = mets(y, cc); b = boot(y, g, cc)
    t2.append({"method": "%s @ %s" % (nm, th), "kind": "PlasmidCall",
               "evidence_tier": "CONFIRMATORY", "n_eligible": m["n_eligible"],
               "n_evaluable": m["n_evaluable"], "n_tool_abstain": m["n_abstain"],
               "coverage": fmt(m["coverage"]), "TP": m["TP"], "FP": m["FP"], "TN": m["TN"],
               "FN": m["FN"], "selective_PPV": fmt(m["selective_PPV"]),
               "selective_PPV_CI95": ci(b, "selective_PPV"),
               "selective_recall": fmt(m["selective_recall"]),
               "selective_recall_CI95": ci(b, "selective_recall"),
               "selective_F1": fmt(m["selective_F1"]), "specificity": fmt(m["specificity"]),
               "deployment_yield": fmt(m["deployment_yield"]), "deployment_yield_note": "",
               "provenance_OK": "", "provenance_RECOVERED_OK": "", "provenance_FAILED": ""})
t2.sort(key=lambda r: (r["kind"] != "PlasmidCall", -(fnum(r["selective_F1"]) or -1)))
wtsv(TB + "/Table2_twelve_tool_comparison.tsv", t2)

# ---------------------------------------------------------------- Table 3: paired common support
t3 = []
for t in TOOLS:
    cc = tcall[t]; b = (c12 >= 0) & (cc >= 0)
    ma = mets(y[b], c12[b]); mb = mets(y[b], cc[b])
    iso = sorted(set(g[b].tolist())); idx = {i: np.where(g[b] == i)[0] for i in iso}
    rng = np.random.default_rng(SEED)
    yb = y[b]; ab = c12[b]; bb = cc[b]; dP = []; dR = []; dF = []
    for _ in range(N_BOOT):
        r = np.concatenate([idx[i] for i in rng.choice(iso, size=len(iso), replace=True)])
        x = mets(yb[r], ab[r]); z = mets(yb[r], bb[r])
        if x["selective_PPV"] is not None and z["selective_PPV"] is not None:
            dP.append(x["selective_PPV"] - z["selective_PPV"])
        if x["selective_recall"] is not None and z["selective_recall"] is not None:
            dR.append(x["selective_recall"] - z["selective_recall"])
        if x["selective_F1"] is not None and z["selective_F1"] is not None:
            dF.append(x["selective_F1"] - z["selective_F1"])
    q = lambda v: "[%.4f, %.4f]" % (np.percentile(v, 2.5), np.percentile(v, 97.5)) if v else ""
    pg = lambda v: fmt(float(np.mean(np.array(v) > 0))) if v else ""
    t3.append({"comparator": t, "common_support_n": int(b.sum()),
               "v1.2_PPV": fmt(ma["selective_PPV"]), "comparator_PPV": fmt(mb["selective_PPV"]),
               "delta_PPV": fmt((ma["selective_PPV"] or 0) - (mb["selective_PPV"] or 0)),
               "delta_PPV_CI95": q(dP), "P_delta_PPV_gt_0_descriptive": pg(dP),
               "v1.2_recall": fmt(ma["selective_recall"]),
               "comparator_recall": fmt(mb["selective_recall"]),
               "delta_recall": fmt((ma["selective_recall"] or 0) - (mb["selective_recall"] or 0)),
               "delta_recall_CI95": q(dR), "P_delta_recall_gt_0_descriptive": pg(dR),
               "v1.2_F1": fmt(ma["selective_F1"]), "comparator_F1": fmt(mb["selective_F1"]),
               "delta_F1": fmt((ma["selective_F1"] or 0) - (mb["selective_F1"] or 0)),
               "delta_F1_CI95": q(dF),
               "delta_coverage": fmt((ma["coverage"] or 0) - (mb["coverage"] or 0)),
               "note": ("bootstrap probabilities are DESCRIPTIVE, not frequentist p-values, and "
                        "carry no multiplicity correction across this panel")})
wtsv(TB + "/Table3_paired_common_support_comparisons.tsv", t3)

# ---------------------------------------------------------------- Table 4: ARG surveillance
a = s15["ARG_plasmid_surveillance_yield"]
t4 = []
for t in TOOLS:
    v = a["per_comparator_on_ARG_contigs"][t]; m = v["metrics"]
    t4.append({"method": t, "ARG_contigs_evaluated": m["n_evaluable"],
               "plasmid_borne_ARG_contigs_recovered": v["true_plasmid_ARG_contigs_recovered"],
               "share_of_plasmid_borne_ARG_recovered": fmt(v["share_of_all_true_plasmid_ARG_contigs"]),
               "chromosomal_ARG_contigs_mislocalised_to_plasmid":
                   v["chromosomal_ARG_contigs_this_tool_called_plasmid"],
               "selective_PPV": fmt(m["selective_PPV"]), "selective_recall": fmt(m["selective_recall"]),
               "selective_F1": fmt(m["selective_F1"])})
am = arg
for nm, cc in (("PlasmidCall v1.2-General @0.9285", c12), ("PlasmidCall router", crt)):
    m = mets(y[am], cc[am])
    t4.append({"method": nm, "ARG_contigs_evaluated": m["n_evaluable"],
               "plasmid_borne_ARG_contigs_recovered": m["TP"],
               "share_of_plasmid_borne_ARG_recovered": fmt(m["deployment_yield"]),
               "chromosomal_ARG_contigs_mislocalised_to_plasmid": m["FP"],
               "selective_PPV": fmt(m["selective_PPV"]), "selective_recall": fmt(m["selective_recall"]),
               "selective_F1": fmt(m["selective_F1"])})
wtsv(TB + "/Table4_ARG_localisation_yield.tsv", t4)
t4b = [dict({"drug_class": k}, **{kk: vv for kk, vv in v.items()})
       for k, v in a["by_drug_class"].items()]
wtsv(TB + "/Table4b_ARG_yield_by_drug_class.tsv", t4b)
t4c = [{"determinant_family": k, "n_ARG_contigs": v["n_ARG_contigs"],
        "n_truth_plasmid": v["n_truth_plasmid"],
        "n_plasmid_recovered_v1.2": v["n_truth_plasmid_recovered_by_v1.2"],
        "n_plasmid_recovered_router": v["n_truth_plasmid_recovered_by_router"],
        "n_truth_chromosome": v["n_truth_chromosome"], "n_isolates": len(v["isolates"]),
        "genes_observed": ";".join(v["genes_observed"])}
       for k, v in a["clinically_focused_determinants"].items()]
wtsv(TB + "/Table4c_clinically_focused_determinants.tsv", t4c)

# ---------------------------------------------------------------- Supp: strata
sup = []
for nm, m in (("length 1-<2kb", (L >= 1000) & (L < 2000)), ("length 2-<5kb", (L >= 2000) & (L < 5000)),
              ("length 5-<10kb", (L >= 5000) & (L < 10000)), ("length >=10kb", L >= 10000),
              ("ARG-bearing", arg), ("non-ARG", ~arg)):
    mm = mets(y[m], c12[m]); ok = mm["n_evaluable"] >= 20 and 0 < mm["n_truth_positive"] < mm["n_evaluable"]
    b = boot(y[m], g[m], c12[m]) if ok else {}
    sup.append({"stratum": nm, "tier": "EXPLORATORY", "n_contigs": int(m.sum()),
                "n_isolates": len(set(g[m].tolist())), "n_truth_positive": mm["n_truth_positive"],
                "coverage": fmt(mm["coverage"]), "TP": mm["TP"], "FP": mm["FP"], "TN": mm["TN"],
                "FN": mm["FN"], "selective_PPV": fmt(mm["selective_PPV"]) if ok else "",
                "selective_PPV_CI95": ci(b, "selective_PPV"),
                "selective_recall": fmt(mm["selective_recall"]) if ok else "",
                "selective_recall_CI95": ci(b, "selective_recall"),
                "estimate_suppressed_as_unstable": "" if ok else "yes"})
pv = prov.get("MOB-recon", {})
for nm, m in (("MOB-recon provenance OK", np.array([pv.get(k) == "OK" for k in keys])),
              ("MOB-recon provenance RECOVERED_OK",
               np.array([pv.get(k) == "RECOVERED_OK" for k in keys])),
              ("MOB-recon provenance FAILED", np.array([pv.get(k) == "FAILED" for k in keys]))):
    mm = mets(y[m], c12[m]); ok = mm["n_evaluable"] >= 20 and 0 < mm["n_truth_positive"] < mm["n_evaluable"]
    b = boot(y[m], g[m], c12[m]) if ok else {}
    sup.append({"stratum": nm, "tier": "EXPLORATORY", "n_contigs": int(m.sum()),
                "n_isolates": len(set(g[m].tolist())), "n_truth_positive": mm["n_truth_positive"],
                "coverage": fmt(mm["coverage"]), "TP": mm["TP"], "FP": mm["FP"], "TN": mm["TN"],
                "FN": mm["FN"], "selective_PPV": fmt(mm["selective_PPV"]) if ok else "",
                "selective_PPV_CI95": ci(b, "selective_PPV"),
                "selective_recall": fmt(mm["selective_recall"]) if ok else "",
                "selective_recall_CI95": ci(b, "selective_recall"),
                "estimate_suppressed_as_unstable": "" if ok else "yes"})
rsrc = {x["biosample"] if "biosample" in x else x.get("sample"): x.get("reference_source", "")
        for x in json.load(io.open(P + "/receipts/P1.11_truth_acquisition_receipt.json",
                                   encoding="utf-8"))["per_isolate"]}
for src in sorted(set(rsrc.values())):
    m = np.array([rsrc.get(k[0]) == src for k in keys])
    mm = mets(y[m], c12[m]); ok = mm["n_evaluable"] >= 20 and 0 < mm["n_truth_positive"] < mm["n_evaluable"]
    b = boot(y[m], g[m], c12[m]) if ok else {}
    sup.append({"stratum": "truth reference source: %s" % src, "tier": "EXPLORATORY (descriptive)",
                "n_contigs": int(m.sum()), "n_isolates": len(set(g[m].tolist())),
                "n_truth_positive": mm["n_truth_positive"], "coverage": fmt(mm["coverage"]),
                "TP": mm["TP"], "FP": mm["FP"], "TN": mm["TN"], "FN": mm["FN"],
                "selective_PPV": fmt(mm["selective_PPV"]) if ok else "",
                "selective_PPV_CI95": ci(b, "selective_PPV"),
                "selective_recall": fmt(mm["selective_recall"]) if ok else "",
                "selective_recall_CI95": ci(b, "selective_recall"),
                "estimate_suppressed_as_unstable": "" if ok else "yes"})
wtsv(TB + "/TableS1_exploratory_strata.tsv", sup)

d3 = s15["tool_disagreement_and_model_value_added"]
ss = []
for k, v in d3["vote_strata"].items():
    for lab, mk in (("PlasmidCall v1.2-General", "PlasmidCall_v1.2-General"),
                    ("PlasmidCall router", "PlasmidCall_router"),
                    ("PlasmidCall v1.1 @0.9524", "PlasmidCall_v1.1_0.9524")):
        m = v[mk]
        ss.append({"panel_plasmid_votes": k, "n_contigs": v["n_contigs"],
                   "n_truth_positive": v["n_truth_positive"],
                   "truth_positive_rate": fmt(v["truth_positive_rate"]), "method": lab,
                   "TP": m["TP"], "FP": m["FP"], "TN": m["TN"], "FN": m["FN"],
                   "selective_PPV": fmt(m["selective_PPV"]),
                   "selective_recall": fmt(m["selective_recall"]),
                   "selective_F1": fmt(m["selective_F1"])})
wtsv(TB + "/TableS2_performance_by_panel_vote_stratum.tsv", ss)

e = s15["error_taxonomy"]
es = []
for dim in ("by_length_bin", "by_ARG_state", "by_vote_entropy_band", "by_reference_source",
            "by_mobrecon_provenance", "by_assembly_fragmentation"):
    d = e[dim]
    for lvl in sorted(set(list(d["all"]) + list(d["FP"]) + list(d["FN"]))):
        es.append({"dimension": dim.replace("by_", ""), "level": lvl,
                   "n_errors": d["all"].get(lvl, 0), "n_FP": d["FP"].get(lvl, 0),
                   "n_FN": d["FN"].get(lvl, 0)})
for dim in ("by_truth_decision_reason", "by_circularity", "by_species"):
    for lvl, n in sorted(e[dim].items()):
        es.append({"dimension": dim.replace("by_", ""), "level": lvl, "n_errors": n,
                   "n_FP": "", "n_FN": ""})
wtsv(TB + "/TableS3_error_taxonomy_summary.tsv", es)

r5 = s15["runtime_and_resources"]
rs = []
for k, v in sorted(r5["by_component"].items(), key=lambda x: -(x[1]["wall_seconds_total"] or 0)):
    note = ""
    if k == "MOB-recon":
        pvc = collections.Counter(prov.get("MOB-recon", {}).get(k2, "") for k2 in keys)
        note = ("execution receipts recorded %s not-OK; a truth-blind provenance audit established "
                "that 47 of those executions completed and produced valid output with a stale "
                "FAILED receipt. Reconciled contig-level provenance on the evaluated set: %s. "
                "The receipt status is reported here unaltered; the reconciled state is what the "
                "evaluation used."
                % (sum(c for s2, c in v["status_counts"].items() if s2 != "OK"), dict(pvc)))
    rs.append({"component": k, "n_executions": v["n_executions"],
               "status_counts": json.dumps(v["status_counts"]),
               "wall_seconds_median": v["wall_seconds_median"],
               "wall_seconds_IQR": "%s-%s" % tuple(v["wall_seconds_IQR"]),
               "wall_seconds_max": v["wall_seconds_max"], "wall_hours_total": v["wall_hours_total"],
               "cpu_hours_at_declared_8cpu_allocation": v["cpu_hours_at_the_declared_8_cpu_allocation"],
               "peak_RAM": "not recorded", "cpu_time": "not recorded",
               "native_output_bytes": v["native_output_bytes"], "note": note})
rs.append({"component": "TOTAL (13 components x 79 isolates)",
           "n_executions": r5["totals"]["n_executions"], "status_counts": "",
           "wall_seconds_median": "", "wall_seconds_IQR": "", "wall_seconds_max": "",
           "wall_hours_total": r5["totals"]["wall_hours"],
           "cpu_hours_at_declared_8cpu_allocation":
               r5["totals"]["cpu_hours_at_the_declared_8_cpu_allocation"],
           "peak_RAM": "not recorded", "cpu_time": "not recorded", "native_output_bytes": "",
           "note": ("summed per-execution wall time; the panel ran concurrently so elapsed time was "
                    "lower. CPU-hours are an allocation-based upper bound (--cpus=8), not a "
                    "measurement.")})
wtsv(TB + "/TableS4_runtime_and_resources.tsv", rs)

pc = []
for k, v in sorted(r5["performance_versus_cost"].items(),
                   key=lambda x: -(x[1]["selective_F1"] or -1)):
    pc.append({"method": k, "selective_F1": fmt(v["selective_F1"]),
               "selective_PPV": fmt(v["selective_PPV"]), "selective_recall": fmt(v["selective_recall"]),
               "coverage": fmt(v["coverage"]), "deployment_yield": fmt(v["deployment_yield"]),
               "wall_seconds_median": v["wall_seconds_median"],
               "cpu_hours_at_8cpu": v["cpu_hours_at_8_cpu"] if "cpu_hours_at_8_cpu" in v else "",
               "operational_failure_rate": fmt(v["operational_failure_rate"]),
               "note": v.get("cost_note", "")})
wtsv(TB + "/TableS5_performance_versus_computational_cost.tsv", pc)

lk = []
for r in rd(OUT + "/P1.11_leakage_distance_per_isolate.tsv"):
    lk.append(r)
wtsv(TB + "/TableS6_genomic_distance_to_development_data.tsv", lk)

cal = []
for mdl in ("v1.2-General", "v1.1 M2_score"):
    x = s15["discrimination_and_calibration"][mdl]
    for b in x["reliability_table"]:
        cal.append({"model": mdl, "bin": b["bin"], "n": b["n"], "mean_score": b["mean_score"],
                    "observed_positive_fraction": b["observed_positive_fraction"]})
wtsv(TB + "/TableS7_calibration_reliability.tsv", cal)
disc = [{"model": m, "n": s15["discrimination_and_calibration"][m]["n"],
         "AUROC": s15["discrimination_and_calibration"][m]["AUROC"],
         "AUROC_CI95": ci({"a": s15["discrimination_and_calibration"][m]["AUROC_ci95"]}, "a"),
         "AUPRC": s15["discrimination_and_calibration"][m]["AUPRC"],
         "AUPRC_CI95": ci({"a": s15["discrimination_and_calibration"][m]["AUPRC_ci95"]}, "a"),
         "Brier": s15["discrimination_and_calibration"][m]["Brier"],
         "calibration_intercept": s15["discrimination_and_calibration"][m]["calibration_intercept"],
         "calibration_slope": s15["discrimination_and_calibration"][m]["calibration_slope"],
         "ECE_10_bins": s15["discrimination_and_calibration"][m]["ECE_10_equal_frequency_bins"],
         "recalibration_applied": "none"}
        for m in ("v1.2-General", "v1.1 M2_score")]
wtsv(TB + "/TableS8_discrimination_and_calibration.tsv", disc)

# ---------------------------------------------------------------- figure data
fig = []
for i, k in enumerate(keys):
    fig.append({"isolate": k[0], "contig_id": k[1], "contig_length": int(L[i]),
                "truth": "plasmid" if y[i] == 1 else "chromosome",
                "v12_score": predk[k]["v12_score"], "v11_score": predk[k]["v11_score"],
                "v12_call_at_0.9285": int(c12[i]), "router_call": int(crt[i]),
                "ARG_bearing": "true" if arg[i] else "false",
                "n_panel_plasmid_votes": predk[k]["n_plasmid"],
                "n_panel_chromosome_votes": predk[k]["n_chrom"],
                "n_panel_abstain": predk[k]["n_abstain"]})
wtsv(TB + "/FigureData_score_distribution.tsv", fig)


def curves(sc, name):
    ok = np.isfinite(sc); yy = y[ok]; ss = sc[ok]
    o = np.argsort(-ss, kind="mergesort"); yy = yy[o]; ss = ss[o]
    tp = np.cumsum(yy); fp = np.cumsum(1 - yy)
    npos = yy.sum(); nneg = len(yy) - npos
    out = []
    step = max(1, len(ss) // 2000)
    for i in range(0, len(ss), step):
        out.append({"model": name, "threshold": "%.10g" % ss[i], "TPR_recall": "%.6f" % (tp[i] / npos),
                    "FPR": "%.6f" % (fp[i] / nneg), "precision": "%.6f" % (tp[i] / (tp[i] + fp[i]))})
    return out


wtsv(TB + "/FigureData_roc_pr_curves.tsv", curves(s12, "v1.2-General") + curves(s11, "v1.1"))
print("  wrote %d manuscript files -> %s" % (len(os.listdir(TB)), TB))
for f in sorted(os.listdir(TB)):
    print("    %-56s %8d bytes" % (f, os.path.getsize(os.path.join(TB, f))))

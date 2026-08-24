#!/usr/bin/env python3
"""Promote the copy-number / replicon-size / replicon-recovery analyses into the accepted
post-truth set: emit manuscript tables S9-S11 and fold the JSON into the main analysis record.

They remain EXPLORATORY and post-hoc; promotion changes where they live, not their evidence tier.
"""
import collections, csv, io, json, os, shutil, sys

P = "/work/p112"
PT = P + "/POSTTRUTH"
EX = PT + "/exploratory_v2"
TB = PT + "/manuscript"


def wtsv(path, rows, cols=None):
    cols = cols or list(rows[0].keys())
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader(); w.writerows(rows)


def fmt(v, nd=4):
    return "" if v is None else ("%.*f" % (nd, v))


d = json.load(io.open(EX + "/P1.11_EXPLORATORY_V2.json", encoding="utf-8"))
A = d["A_copy_number_proxy"]; B = d["B_large_replicons"]; C = d["C_replicon_level_recovery"]

# ---------------------------------------------------------------- S9 copy-number proxy
s9 = []
for nm, v in A["performance_by_copy_number_proxy"].items():
    b = v.get("bootstrap", {})
    s9.append({"copy_number_proxy_band": nm, "tier": "EXPLORATORY",
               "n_contigs": v["n_contigs"], "n_isolates": v["n_isolates"],
               "n_truth_positive": v["n_truth_positive"],
               "TP": v["TP"], "FP": v["FP"], "TN": v["TN"], "FN": v["FN"],
               "selective_PPV": fmt(v["selective_PPV"]),
               "selective_PPV_CI95": ("[%.4f, %.4f]" % tuple(b["PPV_ci95"])) if b.get("PPV_ci95") else "",
               "selective_recall": fmt(v["selective_recall"]),
               "selective_recall_CI95": ("[%.4f, %.4f]" % tuple(b["recall_ci95"])) if b.get("recall_ci95") else "",
               "estimate_suppressed": "yes" if v.get("estimate_suppressed") else ""})
fv = A["false_negatives_versus_true_positives_among_truth_plasmids"]
s9.append({"copy_number_proxy_band": "-- summary --", "tier": "EXPLORATORY",
           "n_contigs": "", "n_isolates": "", "n_truth_positive": "",
           "TP": "missed n=%s" % fv["FN_n"], "FP": "recovered n=%s" % fv["TP_n"],
           "TN": "missed median ratio %s" % fv["FN_coverage_ratio_median"],
           "FN": "recovered median ratio %s" % fv["TP_coverage_ratio_median"],
           "selective_PPV": "", "selective_PPV_CI95": "",
           "selective_recall": "P(missed lower)=%s" % fv.get("P_FN_ratio_lower_than_TP"),
           "selective_recall_CI95": "0.5 = no relationship; descriptive",
           "estimate_suppressed": ""})
wtsv(TB + "/TableS9_performance_by_plasmid_copy_number_proxy.tsv", s9)

# ---------------------------------------------------------------- S10 replicon size
s10 = [{"replicon_size_band_assembled_bp": nm, "tier": "EXPLORATORY",
        "n_replicons": v.get("n_replicons", 0), "n_contigs": v.get("n_contigs", 0),
        "recovered_TP": v.get("recovered_TP", ""), "missed_FN": v.get("missed_FN", ""),
        "contig_level_recall": fmt(v.get("contig_level_recall")),
        "note": ("indicative only, few replicons" if v.get("n_replicons", 0) < 10 else "")}
       for nm, v in B["performance_by_replicon_size"].items()]
wtsv(TB + "/TableS10_recall_by_replicon_size.tsv", s10)

# ---------------------------------------------------------------- S11 replicon recovery
st = C["replicon_states"]
s11 = [
    {"metric": "plasmid replicons evaluated", "value": C["n_replicons"], "fraction": "",
     "note": "grouped by best_plasmid_hit in the frozen truth table"},
    {"metric": "at least one contig recovered", "value": st.get("complete", 0) + st.get("partial", 0),
     "fraction": fmt(C["at_least_one_contig_recovered"]),
     "note": "operative for surveillance: one flagged contig triggers follow-up"},
    {"metric": "fully recovered (every contig)", "value": st.get("complete", 0),
     "fraction": fmt(C["fully_recovered_fraction"]),
     "note": "strict criterion; must be reported beside the figure above"},
    {"metric": "at least 50% of assembled bp recovered",
     "value": C["replicons_with_at_least_half_their_bp_recovered"],
     "fraction": fmt(C["fraction_with_at_least_half_bp"]), "note": ""},
    {"metric": "median per-replicon bp recovery", "value": C["median_bp_recovery_fraction"],
     "fraction": "", "note": "half of all plasmid replicons recovered completely by base pairs"},
    {"metric": "missed entirely", "value": st.get("missed", 0),
     "fraction": fmt(st.get("missed", 0) / C["n_replicons"]), "note": ""},
]
for nm, key in (("single-contig replicons", "single_contig_replicons"),
                ("multi-contig replicons", "multi_contig_replicons")):
    v = C.get(key)
    if not v:
        continue
    s11 += [
        {"metric": "%s: n" % nm, "value": v["n"], "fraction": "", "note": ""},
        {"metric": "%s: fully recovered" % nm, "value": v["fully_recovered"],
         "fraction": fmt(v["fully_recovered"] / v["n"]), "note": ""},
        {"metric": "%s: any contig recovered" % nm, "value": v["any_contig_recovered"],
         "fraction": fmt(v["any_contig_recovered"] / v["n"]),
         "note": ("mechanically easier to satisfy when a replicon is split across many contigs"
                  if "multi" in key else "")},
        {"metric": "%s: missed entirely" % nm, "value": v["missed_entirely"], "fraction": "",
         "note": ""}]
wtsv(TB + "/TableS11_replicon_level_recovery.tsv", s11)

# ---------------------------------------------------------------- fold into the main record
main = PT + "/P1.11_POSTTRUTH_SECTIONS_1_5.json"
m = json.load(io.open(main, encoding="utf-8"))
m["copy_number_replicon_size_and_replicon_recovery"] = {
    "tier": "EXPLORATORY (post-hoc; produced after the accepted set was first frozen)",
    "promoted_from": "the separate candidate set, on explicit instruction",
    "promotion_changes_location_not_evidence_tier": True,
    "A_copy_number_proxy": A, "B_large_replicons": B, "C_replicon_level_recovery": C}
io.open(main, "w", encoding="utf-8", newline="\n").write(json.dumps(m, indent=1, default=str) + "\n")

# relocate the per-replicon table beside the other per-row tables, retire the separate dir
shutil.copy2(EX + "/P1.11_replicon_recovery.tsv", PT + "/P1.11_replicon_recovery.tsv")
shutil.copy2(EX + "/P1.11_EXPLORATORY_V2.json", PT + "/P1.11_POSTTRUTH_COPYNUMBER_AND_REPLICON.json")
shutil.rmtree(EX)

print("  wrote TableS9 / TableS10 / TableS11")
print("  folded into %s" % os.path.basename(main))
print("  separate candidate directory retired; contents now in the accepted set")
print("  manuscript tables now: %d" % len(os.listdir(TB)))
for f in sorted(os.listdir(TB)):
    print("    %s" % f)

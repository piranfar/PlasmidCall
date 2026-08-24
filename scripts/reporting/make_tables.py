# -*- coding: utf-8 -*-
"""Build the four main-text tables from the frozen sources.

Emits a machine-readable .tsv per table (submitted as Source Data) and a rendered markdown
block that is inserted into the manuscript.
"""
import csv, io, json, os, collections, hashlib

R = "docs/evidence/P1.13_results"
PF = "docs/postfreeze/tables"
OUT = "docs/manuscript/tables"
os.makedirs(OUT, exist_ok=True)


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
    return [float(v) for v in x.strip("[]").split(",")]


def fmt(v, d=4):
    return "" if v is None else ("%%.%df" % d) % v


def fmtci(c, d=4):
    return "" if not c else "%s–%s" % (fmt(c[0], d), fmt(c[1], d))


def comma(n):
    return "{:,}".format(int(n))


canon = js("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json")["values"]
inv = tsv(R + "/P113_PREDICTOR_INVENTORY.tsv")
prim = {r["predictor"]: r for r in tsv(R + "/P113_PRIMARY_METRICS.tsv")}
comp = {r["predictor"]: r for r in tsv(R + "/P113_COMPARATOR_METRICS.tsv")}
comp.update(prim)
fair = {r["predictor"]: r for r in tsv(PF + "/PF12_COMPARATOR_FAIRNESS.tsv")}
argall = {r["row"]: r for r in tsv(R + "/P113_ARG_ALL_PREDICTORS.tsv")
          if r["subset"] == "ARG_bearing"}
pareto = {d["row"] for d in js(R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json")["pareto_frontier"]}
rq = tsv(PF + "/PF10a_REFERENCE_QUALITY.tsv")
tx01 = tsv(PF + "/PF01_TAXON_ROBUSTNESS.tsv")

NAMES = {"v1.2-General@0.9285": "PlasmidCall v1.2-General",
         "v1.1@0.9524": "PlasmidCall v1.1", "v1.1@0.9605_high_conf": "PlasmidCall v1.1",
         "router": "PlasmidCall router",
         "baseline:majority_vote": "panel majority vote (baseline)",
         "baseline:any_tool_plasmid": "any-tool-plasmid (baseline)",
         "baseline:all_chromosome": "all-chromosome (baseline)"}
FILES = []


def emit(name, cols, rows, md_cols, md_rows, caption):
    p = "%s/%s.tsv" % (OUT, name)
    with io.open(p, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader()
        w.writerows(rows)
    md = ["| " + " | ".join(md_cols) + " |",
          "|" + "|".join(["---"] * len(md_cols)) + "|"]
    for r in md_rows:
        md.append("| " + " | ".join(str(x) for x in r) + " |")
    mp = "%s/%s.md" % (OUT, name)
    io.open(mp, "w", encoding="utf-8", newline="\n").write(
        "**%s**\n\n" % caption + "\n".join(md) + "\n")
    for q in (p, mp):
        FILES.append({"file": q, "bytes": os.path.getsize(q),
                      "sha256": hashlib.sha256(io.open(q, "rb").read()).hexdigest()})
    print("  %-34s %d rows" % (name, len(rows)))


# ---------------------------------------------------------------- Table 1
print("Table 1 - cohort composition and truth resolution")
agg = collections.OrderedDict()
for r in rq:
    a = agg.setdefault(r["taxon"], {"isolates": 0, "eligible": 0, "resolved": 0, "unresolved": 0})
    a["isolates"] += 1
    a["eligible"] += int(r["eligible_contigs"])
    a["resolved"] += int(r["resolved_contigs"])
    a["unresolved"] += int(r["unresolved_contigs"])
taxmap = {t["taxon"]: t for t in canon["taxon_v12"]}
t1_rows, t1_md = [], []
tot = collections.Counter()
for t in sorted(agg, key=lambda k: -taxmap[k]["PPV"]):
    a = agg[t]
    pl = taxmap[t]["n_plasmid"]
    ch = taxmap[t]["n_scored"] - pl
    t1_rows.append({"taxon": t, "isolates": a["isolates"], "eligible_contigs": a["eligible"],
                    "truth_resolved": a["resolved"], "unresolved": a["unresolved"],
                    "chromosomal": ch, "plasmid_derived": pl,
                    "plasmid_fraction_of_resolved": round(pl / float(a["resolved"]), 6)})
    t1_md.append([("*%s*" % t) if "spp." not in t else ("*%s* spp." % t.replace(" spp.", "")),
                  a["isolates"], comma(a["eligible"]), comma(a["resolved"]),
                  comma(a["unresolved"]), comma(ch), comma(pl),
                  "%.3f" % (pl / float(a["resolved"]))])
    for k, v in (("isolates", a["isolates"]), ("eligible", a["eligible"]),
                 ("resolved", a["resolved"]), ("unresolved", a["unresolved"]),
                 ("chrom", ch), ("plas", pl)):
        tot[k] += v
t1_rows.append({"taxon": "TOTAL", "isolates": tot["isolates"], "eligible_contigs": tot["eligible"],
                "truth_resolved": tot["resolved"], "unresolved": tot["unresolved"],
                "chromosomal": tot["chrom"], "plasmid_derived": tot["plas"],
                "plasmid_fraction_of_resolved": round(tot["plas"] / float(tot["resolved"]), 6)})
t1_md.append(["**Total**", "**%d**" % tot["isolates"], "**%s**" % comma(tot["eligible"]),
              "**%s**" % comma(tot["resolved"]), "**%s**" % comma(tot["unresolved"]),
              "**%s**" % comma(tot["chrom"]), "**%s**" % comma(tot["plas"]),
              "**%.3f**" % (tot["plas"] / float(tot["resolved"]))])
assert tot["resolved"] == canon["den_scored_resolved"], tot["resolved"]
assert tot["eligible"] == canon["den_eligible_ge_1kb"]
assert tot["plas"] == canon["den_truth_plasmid"]
emit("Table1_cohort_and_truth",
     ["taxon", "isolates", "eligible_contigs", "truth_resolved", "unresolved", "chromosomal",
      "plasmid_derived", "plasmid_fraction_of_resolved"], t1_rows,
     ["Taxon", "Isolates", "Eligible contigs", "Truth-resolved", "Unresolved", "Chromosomal",
      "Plasmid-derived", "Plasmid fraction"], t1_md,
     "Table 1 | Sealed cohort composition and truth resolution by taxon.")

# ---------------------------------------------------------------- Table 2
print("Table 2 - complete 19-row predictor inventory")
t2_rows, t2_md = [], []
for r in inv:
    k = r["method"]
    m = comp.get(k, {})
    fr = fair.get(k, {})
    t2_rows.append({
        "row": k, "family": r["method_family"], "operating_point": r["operating_point"],
        "role": r["role"], "coverage": f(r["coverage_on_resolved"]),
        "non_calls": int(r["abstention_count"]), "failure_states": r["failure_states"],
        "conditional_PPV": f(m.get("PPV")), "conditional_PPV_ci95": m.get("PPV_ci95", ""),
        "conditional_recall": f(m.get("recall")), "conditional_recall_ci95": m.get("recall_ci95", ""),
        "conditional_F1": f(m.get("F1")),
        "failure_aware_PPV": f(fr.get("failure_aware_PPV")),
        "failure_aware_recall": f(fr.get("failure_aware_recall")),
        "failure_aware_F1": f(fr.get("failure_aware_F1")),
        "matched_n": fr.get("matched_n", ""), "matched_PPV": f(fr.get("matched_PPV")),
        "matched_recall": f(fr.get("matched_recall")), "matched_F1": f(fr.get("matched_F1")),
        "undefined_or_exclusion_reason": r["undefined_or_exclusion_reason"]})
    nm = NAMES.get(k, k.replace("tool:", "").replace("baseline:", ""))
    if k.startswith("v1.1"):
        nm += " @ " + ("0.9524" if "9524" in k else "0.9605")
    cond = fmt(f(m.get("PPV"))) or "undefined"
    t2_md.append([nm, "%.4f" % f(r["coverage_on_resolved"]), comma(r["abstention_count"]),
                  cond, fmtci(ci(m.get("PPV_ci95"))) or "—",
                  fmt(f(m.get("recall"))), fmt(f(m.get("F1"))) or "undefined",
                  fmt(f(fr.get("failure_aware_PPV"))) or "undefined",
                  fmt(f(fr.get("matched_PPV"))) or "undefined",
                  fmt(f(fr.get("matched_F1"))) or "undefined"])
assert len(t2_rows) == 19
emit("Table2_predictor_inventory",
     ["row", "family", "operating_point", "role", "coverage", "non_calls", "failure_states",
      "conditional_PPV", "conditional_PPV_ci95", "conditional_recall", "conditional_recall_ci95",
      "conditional_F1", "failure_aware_PPV", "failure_aware_recall", "failure_aware_F1",
      "matched_n", "matched_PPV", "matched_recall", "matched_F1",
      "undefined_or_exclusion_reason"], t2_rows,
     ["Predictor", "Coverage", "Non-calls", "PPV (conditional)", "95% CI", "Recall", "F1",
      "PPV (failure-aware)", "PPV (matched)", "F1 (matched)"], t2_md,
     "Table 2 | Complete frozen predictor inventory, all 19 rows, under three accountings.")

# ---------------------------------------------------------------- Table 3
print("Table 3 - ARG-bearing subset")
t3_rows, t3_md = [], []
for r in inv:
    k = r["method"]
    a = argall.get(k)
    if not a:
        continue
    t3_rows.append({"row": k, "coverage": f(a["coverage"]), "n_scored": int(a["n_scored"]),
                    "TP": int(a["TP"]), "FP": int(a["FP"]), "TN": int(a["TN"]), "FN": int(a["FN"]),
                    "PPV": f(a["PPV"]), "PPV_ci95": a["PPV_ci95"], "recall": f(a["recall"]),
                    "recall_ci95": a["recall_ci95"], "F1": f(a["F1"]),
                    "on_pareto_frontier": k in pareto})
    nm = NAMES.get(k, k.replace("tool:", "").replace("baseline:", ""))
    if k.startswith("v1.1"):
        nm += " @ " + ("0.9524" if "9524" in k else "0.9605")
    t3_md.append([nm, "%.4f" % f(a["coverage"]), fmt(f(a["PPV"])) or "undefined",
                  fmtci(ci(a["PPV_ci95"])) or "—", fmt(f(a["recall"])),
                  fmtci(ci(a["recall_ci95"])) or "—", fmt(f(a["F1"])) or "undefined",
                  "yes" if k in pareto else "no"])
emit("Table3_arg_bearing",
     ["row", "coverage", "n_scored", "TP", "FP", "TN", "FN", "PPV", "PPV_ci95", "recall",
      "recall_ci95", "F1", "on_pareto_frontier"], t3_rows,
     ["Predictor", "Coverage", "PPV", "95% CI", "Recall", "95% CI", "F1", "Pareto"], t3_md,
     "Table 3 | Performance on the %d resistance-gene-bearing contigs, all 19 rows."
     % canon["arg_bearing_n"])

# ---------------------------------------------------------------- Table 4
print("Table 4 - taxon-stratified, three frozen strategies")
t4_rows, t4_md = [], []
by = collections.defaultdict(dict)
for r in tx01:
    if r["label"].startswith("taxon="):
        by[r["label"][6:]][r["model"]] = r
order = [t["taxon"] for t in canon["taxon_v12"]]
for t in order:
    for mk in ("v1.2-General@0.9285", "v1.1@0.9524", "router"):
        r = by[t].get(mk)
        if not r:
            continue
        t4_rows.append({"taxon": t, "model": mk, "n_scored": int(r["n_scored"]),
                        "n_plasmid": int(r["n_plasmid"]), "TP": int(r["TP"]), "FP": int(r["FP"]),
                        "TN": int(r["TN"]), "FN": int(r["FN"]), "PPV": f(r["PPV"]),
                        "PPV_ci95": r["PPV_ci95"], "recall": f(r["recall"]),
                        "recall_ci95": r["recall_ci95"], "specificity": f(r["specificity"]),
                        "NPV": f(r["NPV"]), "F1": f(r["F1"]),
                        "adequate_denominator": r["adequate_denominator"],
                        "meets_PPV_floor": f(r["PPV"]) >= 0.95})
        nm = NAMES[mk] + (" @ 0.9524" if mk == "v1.1@0.9524" else "")
        t4_md.append([("*%s*" % t) if "spp." not in t else ("*%s* spp." % t.replace(" spp.", "")),
                      nm, comma(r["n_scored"]), comma(r["n_plasmid"]),
                      fmt(f(r["PPV"])), fmtci(ci(r["PPV_ci95"])),
                      fmt(f(r["recall"])), fmtci(ci(r["recall_ci95"])),
                      fmt(f(r["specificity"])), fmt(f(r["F1"])),
                      r["adequate_denominator"]])
emit("Table4_taxon_stratified",
     ["taxon", "model", "n_scored", "n_plasmid", "TP", "FP", "TN", "FN", "PPV", "PPV_ci95",
      "recall", "recall_ci95", "specificity", "NPV", "F1", "adequate_denominator",
      "meets_PPV_floor"], t4_rows,
     ["Taxon", "Strategy", "n", "Plasmid", "PPV", "95% CI", "Recall", "95% CI", "Specificity",
      "F1", "Adequate n"], t4_md,
     "Table 4 | Taxon-stratified performance of the three frozen PlasmidCall strategies.")


# ---------------------------------------------------------------- Table 5
print("Table 5 - genomic context of resistance determinants")
ab = js("docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json")
t5_rows, t5_md = [], []


def t5_add(group, items, namer=lambda d: d["stratum"]):
    for d in items:
        t5_rows.append({"grouping": group, "stratum": d["stratum"], "contigs": d["contigs"],
                        "plasmid_derived": d["plasmid_derived"], "chromosomal": d["chromosomal"],
                        "plasmid_fraction": d["plasmid_fraction"]})
        t5_md.append([group, namer(d), comma(d["contigs"]), comma(d["plasmid_derived"]),
                      comma(d["chromosomal"]), "%.3f" % d["plasmid_fraction"]])


p = ab["pooled"]
t5_rows.append({"grouping": "all", "stratum": "all resistance-gene-bearing contigs",
                "contigs": p["contigs"], "plasmid_derived": p["plasmid_derived"],
                "chromosomal": p["chromosomal"], "plasmid_fraction": p["plasmid_fraction"]})
t5_md.append(["all", "**all resistance-gene-bearing contigs**", "**%s**" % comma(p["contigs"]),
              "**%s**" % comma(p["plasmid_derived"]), "**%s**" % comma(p["chromosomal"]),
              "**%.3f**" % p["plasmid_fraction"]])
t5_add("taxon", ab["by_taxon"],
       lambda d: ("*%s* spp." % d["stratum"].replace(" spp.", "")) if "spp." in d["stratum"]
                 else "*%s*" % d["stratum"])
t5_add("antimicrobial class", ab["by_class"],
       lambda d: d["stratum"].lower().replace("beta-lactam", "β-lactam"))
for k, v in (("vanA-type", ab["glycopeptide_operons"]["vanA_type"]),
             ("vanB-type", ab["glycopeptide_operons"]["vanB_type"]),
             ("vanD-type", ab["glycopeptide_operons"]["vanD_type"])):
    if not v:
        continue
    t5_rows.append({"grouping": "glycopeptide operon", "stratum": k, "contigs": v["contigs"],
                    "plasmid_derived": v["plasmid_derived"],
                    "chromosomal": v["contigs"] - v["plasmid_derived"],
                    "plasmid_fraction": v["plasmid_fraction"]})
    t5_md.append(["glycopeptide operon", "*%s*-type (%d genes)" % (k[:4], v["n_genes"]),
                  comma(v["contigs"]), comma(v["plasmid_derived"]),
                  comma(v["contigs"] - v["plasmid_derived"]), "%.3f" % v["plasmid_fraction"]])

emit("Table5_arg_genomic_context",
     ["grouping", "stratum", "contigs", "plasmid_derived", "chromosomal", "plasmid_fraction"],
     t5_rows,
     ["Grouping", "Stratum", "Contigs", "Plasmid-derived", "Chromosomal", "Plasmid fraction"],
     t5_md,
     "Table 5 | Genomic context of resistance determinants across the six taxa.")

# every value printed in a main table is registered as canonical, with its source table
CANON_TABLES = {
 "table1_cohort_and_truth": {"rows": t1_rows,
   "source": "PF10a_REFERENCE_QUALITY.tsv aggregated by taxon + PF01_TAXON_ROBUSTNESS.tsv"},
 "table2_predictor_inventory": {"rows": t2_rows,
   "source": "P113_PREDICTOR_INVENTORY.tsv + P113_PRIMARY_METRICS.tsv + "
             "P113_COMPARATOR_METRICS.tsv + PF12_COMPARATOR_FAIRNESS.tsv"},
 "table3_arg_bearing": {"rows": t3_rows,
   "source": "P113_ARG_ALL_PREDICTORS.tsv + P113_ARG_PARETO_AND_CORE_CLAIM.json"},
 "table4_taxon_stratified": {"rows": t4_rows, "source": "PF01_TAXON_ROBUSTNESS.tsv"},
 "table5_arg_genomic_context": {"rows": t5_rows,
   "source": "PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json, itself read from PF04_ARG_COMPLETE.tsv"},
}
io.open("docs/manuscript/PLASMIDCALL_CANONICAL_TABLES.json", "w", encoding="utf-8",
        newline="\n").write(json.dumps(
    {"canonical_table_set": "PLASMIDCALL-CANONICAL-TABLES-001", "built_utc": "2026-08-24",
     "rule": "every number printed in a main-text table appears here with its source table",
     "values": CANON_TABLES}, indent=1) + "\n")

io.open(OUT + "/TABLE_CHECKSUMS.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps({"generated_utc": "2026-08-24", "files": FILES}, indent=1) + "\n")
print("\n%d table files written" % len(FILES))

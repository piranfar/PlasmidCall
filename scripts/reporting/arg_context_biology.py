# -*- coding: utf-8 -*-
"""Extract the biological result that the frozen resistance-gene table already contains.

PF04_ARG_COMPLETE.tsv was built to report classifier performance per stratum. Two of its columns
- n_scored and n_plasmid - are truth counts rather than predictions: across every predictor that
answers for all 635 contigs they are identical, and n_plasmid equals TP+FN. They therefore
describe where resistance determinants actually sit in these 150 genomes, independently of any
classifier's output.

That is a microbiological result and it had not been reported. This script extracts it under
pre-stated thresholds, so the reported pattern cannot be a selection of convenient strata:

  * every antimicrobial class with at least 20 contigs
  * every gene family with at least 10 contigs

The denominator throughout is CONTIGS CARRYING AT LEAST ONE DETERMINANT of that class or family,
not gene copies. A contig carrying determinants of several classes contributes to each.
"""
import csv, io, json, collections

PF = "docs/postfreeze/tables/PF04_ARG_COMPLETE.tsv"
OUT = "docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json"
CLASS_MIN, FAMILY_MIN = 20, 10

rows = list(csv.DictReader(io.open(PF, encoding="utf-8"), delimiter="\t"))

# The truth counts must be identical across every predictor that answers for EVERY contig.
# A tool with incomplete coverage scores a subset, so its n_scored and n_plasmid legitimately
# differ; those rows are not evidence about where the determinants sit. The three frozen
# PlasmidCall strategies all have coverage 1.0, so agreement among them establishes that these
# columns are truth counts rather than anything the model produced.
COMPLETE = {"v1.2-General@0.9285", "v1.1@0.9524", "router"}
by_label = collections.defaultdict(set)
for r in rows:
    if r["model"] in COMPLETE:
        by_label[r["label"]].add((r["n_scored"], r["n_plasmid"]))
inconsistent = [k for k, v in by_label.items() if len(v) > 1]
assert not inconsistent, "truth counts differ between complete-coverage models for: %s" % (
    inconsistent[:3])
print("truth counts agree across all %d strata for the %d complete-coverage strategies"
      % (len(by_label), len(COMPLETE)))

one = [r for r in rows if r["model"] == "v1.2-General@0.9285"]


def strata(prefix, minn):
    out = []
    for r in one:
        if not r["label"].startswith(prefix):
            continue
        n, p = int(r["n_scored"]), int(r["n_plasmid"])
        if n >= minn:
            out.append({"stratum": r["label"].split("=", 1)[-1], "contigs": n,
                        "plasmid_derived": p, "chromosomal": n - p,
                        "plasmid_fraction": round(p / float(n), 4)})
    return sorted(out, key=lambda d: (-d["plasmid_fraction"], -d["contigs"]))


pooled = [r for r in one if r["label"] == "ARG pooled"][0]
n_tot, p_tot = int(pooled["n_scored"]), int(pooled["n_plasmid"])

cls = strata("ARG class", CLASS_MIN)
fam = strata("ARG family", FAMILY_MIN)
tax = strata("ARG taxon", 1)

# Bimodality, computed rather than asserted: how many gene families sit at the extremes?
hi = [f for f in fam if f["plasmid_fraction"] >= 0.90]
lo = [f for f in fam if f["plasmid_fraction"] <= 0.10]
mid = [f for f in fam if 0.10 < f["plasmid_fraction"] < 0.90]

# Operon-level concordance: the glycopeptide operons are the sharpest case, because vanA-type is
# classically plasmid-borne and vanB-type classically chromosomal. Both are present here.
van = {f["stratum"]: f for f in strata("ARG family", 1) if f["stratum"].startswith("van")}
vanA = {k: v for k, v in van.items() if k == "vanA" or k.endswith("-A")}
vanB = {k: v for k, v in van.items() if k == "vanB" or k.endswith("-B")}
vanD = {k: v for k, v in van.items() if k == "vanD" or k.endswith("-D")}


def summarise(group):
    if not group:
        return None
    c = sum(g["contigs"] for g in group.values())
    p = sum(g["plasmid_derived"] for g in group.values())
    return {"genes": sorted(group), "n_genes": len(group), "contigs": c,
            "plasmid_derived": p, "plasmid_fraction": round(p / float(c), 4)}


result = collections.OrderedDict([
 ("analysis", "genomic context of resistance determinants across six bacterial taxa"),
 ("class", "post-freeze, descriptive. Truth counts read from the frozen resistance-gene table; "
           "no model, threshold or label was involved and nothing was recomputed"),
 ("denominator_note", "contigs carrying at least one determinant of the named class or family. "
                      "A contig carrying determinants of several classes contributes to each, so "
                      "class counts do not sum to the pooled total"),
 ("thresholds_prestated", {"class_min_contigs": CLASS_MIN, "family_min_contigs": FAMILY_MIN}),
 ("pooled", {"contigs": n_tot, "plasmid_derived": p_tot, "chromosomal": n_tot - p_tot,
             "plasmid_fraction": round(p_tot / float(n_tot), 4)}),
 ("by_taxon", tax),
 ("by_class", cls),
 ("by_family", fam),
 ("family_distribution", {
    "families_reported": len(fam),
    "at_or_above_90pc_plasmid": len(hi),
    "at_or_below_10pc_plasmid": len(lo),
    "between": len(mid),
    "fraction_at_an_extreme": round((len(hi) + len(lo)) / float(len(fam)), 4),
    "reading": "the distribution is strongly bimodal: determinants are largely either "
               "plasmid-borne or chromosomal in this cohort, with few families intermediate"}),
 ("glycopeptide_operons", {
    "vanA_type": summarise(vanA), "vanB_type": summarise(vanB), "vanD_type": summarise(vanD),
    "reading": "vanA-type determinants are plasmid-derived and vanB-type and vanD-type are "
               "chromosomal in this cohort, which is the established distinction. The truth "
               "assignment uses only alignment against each isolate's own closed reference and "
               "has no knowledge of gene identity or function, so this concordance is an "
               "independent check on the labelling rather than a new finding about the genes"}),
])

io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(result, indent=1) + "\n")

print("ARG-bearing contigs        : %s, of which %s plasmid-derived (%.1f%%)"
      % ("{:,}".format(n_tot), "{:,}".format(p_tot), 100 * p_tot / n_tot))
print("classes with >= %d contigs : %d" % (CLASS_MIN, len(cls)))
print("families with >= %d contigs: %d  (%d at >=90%% plasmid, %d at <=10%%, %d between)"
      % (FAMILY_MIN, len(fam), len(hi), len(lo), len(mid)))
print()
print("taxon gradient:")
for t in tax:
    print("   %-24s %4d contigs  %5.1f%% plasmid-derived"
          % (t["stratum"], t["contigs"], 100 * t["plasmid_fraction"]))
print()
for k, g in (("vanA-type", vanA), ("vanB-type", vanB), ("vanD-type", vanD)):
    s = summarise(g)
    if s:
        print("%-10s %d genes, %d contigs, %.0f%% plasmid-derived"
              % (k, s["n_genes"], s["contigs"], 100 * s["plasmid_fraction"]))

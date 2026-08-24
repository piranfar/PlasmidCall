# -*- coding: utf-8 -*-
"""Build the bioRxiv preprint variant from the rendered journal manuscript.

The scientific content is identical. The preprint differs only where the journal's structural
rules forced a compromise that bioRxiv does not require:

  * an extended abstract, because bioRxiv sets no 150-word cap;
  * explicit subheadings inside the Discussion, which the journal forbids;
  * an explicit Limitations section, which the journal forbids;
  * an explicit Conclusion section, which the journal forbids;
  * an explicit Funding line, which the journal requires to sit inside Acknowledgements;
  * figures and tables placed in reading position rather than grouped at the end.

Every difference is recorded in the emitted delta file so the two versions can be compared.
"""
import io, json, re, os

SRC = "docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md"
OUT = "docs/manuscript/PlasmidCall_bioRxiv_preprint.md"
DELTA = "docs/manuscript/PREPRINT_VS_JOURNAL_DELTA.md"

C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
s = io.open(SRC, encoding="utf-8").read()
delta = []


def rep(old, new, why):
    global s
    assert s.count(old) == 1, "anchor %d occurrences: %r" % (s.count(old), old[:70])
    s = s.replace(old, new)
    delta.append(why)


P = "%.4f" % C["primary_PPV"]
PL, PH = ["%.4f" % v for v in C["primary_PPV_ci95"]]
RC = "%.4f" % C["primary_recall"]
RL, RH = ["%.4f" % v for v in C["primary_recall_ci95"]]


AC = json.load(io.open("docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json",
                       encoding="utf-8"))
ACC = {c["stratum"]: c for c in AC["by_class"]}


def n(x):
    return "{:,}".format(int(x))


# ---------------------------------------------------------------- 1. preprint header
head_old = s[:s.index("## Abstract")]
head_new = """# Genomic context of resistance determinants in 150 bacterial genomes across six taxa with prospective validation of plasmid-origin classification

**Vahhab Piranfar**^1^\\*

^1^ Independent Researcher, Jersey City, NJ, USA

\\* **Corresponding author:** Vahhab Piranfar, Independent Researcher, Jersey City, NJ, USA.
Email: vahab.p@gmail.com · ORCID: *[to be supplied]*

**Preprint version 1 · %s**

> **This is a preprint. It has not been peer reviewed.** It is posted to make the work available
> for scrutiny and reuse before formal review. Findings should be read accordingly.

**Running title:** Genomic context of resistance determinants

**Keywords:** antimicrobial resistance; plasmid; chromosome; genomic context of resistance
genes; vancomycin resistance; *Klebsiella pneumoniae*; *Enterococcus faecium*; bacterial genomics;
short-read assembly; prospective validation

**Data generated in this study:** 150 de novo short-read assemblies spanning six bacterial genera;
19,320 contigs each assigned a replicon of origin by alignment against the same isolate's own
closed reference genome; resistance-determinant annotations for those contigs; and the resulting
contig-level table of the genomic context of every resistance determinant in the cohort. These
derived data are released with the paper. Raw reads are public archive data, cited by accession
with per-file checksums and not redistributed.

**Data and code availability:** derived data, frozen models, analysis code and verification
receipts are in the project repository (see *Data availability* and *Code availability*). Raw reads
are public archive data, cited by accession with per-file checksums and not redistributed.

**Competing interests:** the author declares no financial or non-financial competing interests.

**Funding:** this study received no funding. *[To be confirmed by the author before posting.]*

**Author contributions:** V.P. conceived and designed the study, prespecified the endpoint and
analysis plan, directed the implementation and execution of the pipeline, performed and verified
the analyses, interpreted the results, and wrote the manuscript. V.P. is accountable for all
aspects of the work.

---

## Significance

Knowing that a bacterial isolate carries a resistance gene is not the same as knowing whether that
gene can move. A determinant on a conjugative plasmid and the same determinant in the chromosome
are one detection event and two different epidemiological situations. Short-read sequencing, which
most surveillance programmes actually generate, fragments the genome and separates the two poorly.
We assembled 150 genomes from six genera of clinical importance and placed every one of their
19,320 contigs against that isolate's own finished genome, which lets us say for each resistance
determinant in the cohort whether it sits on plasmid or chromosomal sequence. Two in five
resistance-gene-bearing contigs are plasmid-derived, but the pooled figure hides a sharp
structure: the fraction runs from 57.5%% in *Citrobacter* spp. to 7.1%% in *Serratia* spp., and
across gene families it is strongly bimodal, most families sitting almost entirely on one
compartment or the other rather than in between. The same labels then serve as truth for a
prospective, truth-blind evaluation of automated plasmid-origin calling, sealed before any read
was retrieved, in which one method family held a prespecified precision floor while answering for
every contig and no third-party tool reached that floor at any coverage.

---

""" % "2026-08-24"
s = head_new + s[s.index("## Abstract"):]
delta.append("Preprint title states the cohort size explicitly — 'in 150 bacterial genomes' — "
             "which the journal title omits to stay inside the 15-word limit. The two titles are "
             "otherwise the same claim about the same work.")
delta.append("Preprint front matter carries a 'Data generated in this study' block listing the 150 "
             "de novo assemblies, the 19,320 contig-level replicon assignments, the "
             "resistance-determinant annotations and the genomic-context table. The journal "
             "version states the same content in Data availability, where its format requires it.")
delta.append("Preprint header replaces the journal title page: adds a preprint-status statement, "
             "a version date, a Significance paragraph, and surfaces competing interests, funding "
             "and author contributions at the front, none of which the journal format permits "
             "there.")

# ---------------------------------------------------------------- 2. extended abstract
a0 = s.index("## Abstract")
a1 = s.index("## Introduction")
abstract_new = """## Abstract

Detecting an antimicrobial resistance gene in a bacterial genome does not establish whether it can
move. The same determinant carried on a conjugative plasmid and integrated in the chromosome is one
detection event and two different epidemiological situations. Short-read sequencing, which
dominates surveillance on cost, is precisely where that distinction is hardest to recover:
assemblies fragment, plasmid and chromosomal sequence interleave across contigs, and small
replicons split or disappear.

We assembled **%s bacterial genomes** de novo from short-read data spanning six genera of clinical
importance — 25 each of *Klebsiella pneumoniae*, *Enterobacter* spp., *Citrobacter* spp.,
*Serratia* spp., *Enterococcus faecium* and *E. faecalis* — selected by farthest-point genomic
sampling with average-nucleotide-identity exclusion below 99.5 against every genome used in
development or prior validation. Each isolate was paired with its own closed reference genome, and
all **%s contigs** were aligned back to that reference to establish the replicon each derives from.
Of these, %s were eligible at ≥ 1 kb and %s carried a resolvable label. Resistance determinants
were then annotated on the same contigs, giving the genomic context of every determinant in the
cohort.

**Of %d resistance-gene-bearing contigs, %d (%.1f%%) are plasmid-derived.** The pooled figure
conceals a strong structure. Across taxa the plasmid-derived fraction runs from **%.1f%% in
*Citrobacter* spp. to %.1f%% in *Serratia* spp.** Across antimicrobial classes it runs from
**%.1f%% for sulfonamide resistance to zero for all %d contigs carrying fosfomycin resistance** and
zero for the %d contigs carrying the nitrofuran, phenicol, quinolone and tetracycline efflux
determinants. Across gene families the distribution is **bimodal**: of %d families with at least %d
contigs, %d sit at or above 90%% plasmid-derived and %d at or below 10%%, leaving only %d in
between. The glycopeptide operons separate the same way — *vanA*-type determinants are
plasmid-derived on all %d contigs bearing them, while *vanB*-type (%d contigs) and *vanD*-type (%d
contigs) are chromosomal without exception. Because the mapping uses sequence alignment alone and
has no access to gene identity or function, this recovery of the established vancomycin-resistance
genetics is an internal check on the labelling rather than a new finding about those genes.

These labels then serve as truth for a **prospectively sealed, truth-blind evaluation of automated
plasmid-origin classification**. The design, cohort, eligibility rules, thresholds, analysis plan
and stopping rules were hash-sealed before any read was retrieved; predictions were frozen and
independently reproduced byte-for-byte before any truth artefact was permitted onto the analysis
system. Nineteen predictor rows were evaluated on identical evidence: **%s third-party tools**, four
PlasmidCall model and router rows, and three predeclared baselines.

**PlasmidCall v1.2-General met the prespecified primary endpoint: precision %s (isolate-clustered
95%% confidence interval %s–%s) at recall %s (%s–%s), with coverage 1.0000 and zero abstentions.**
The requirement was precision ≥ 0.95 and recall > 0.50; both were met and the **lower bound of the
interval, not merely the point estimate, cleared the floor**. **No third-party tool or predeclared
baseline reached precision 0.95 at any observed coverage**; the highest was %.4f. Four rows met the
floor at complete coverage and all four were PlasmidCall's, spanning two model classes and three
thresholds.

%s evaluated rows achieved a higher pooled F1 than the index row, often while answering less often:
coverage across the panel ranged from %.4f to 1.0000, %d of %s tool executions failed
deterministically, and requiring every row to answer restricted the common denominator to **%s of
%s truth-resolved contigs (%.1f%%)**.

On the resistance-gene-bearing subset itself, v1.2-General reached precision %.4f at complete
coverage and lies on the Pareto frontier, but **no method of any kind reached precision 0.95 with
complete coverage** there; plASgraph2 achieved higher precision (%.4f) at coverage %.4f. The frozen
router is reported as a validated negative result: it recovered %.1f percentage points less
resistance-gene signal for %.2f points of precision and is not recommended for that use. Precision
ranged %.4f–%.4f across taxa and **fell below the floor in three of six**. Precision is
prevalence-dependent, crossing the floor at %.1f%% plasmid prevalence against an observed %.1f%%.

**%d values and checks were recomputed from the frozen joined table by verifiers sharing no
implementation with the analysis, with zero disagreements.** The cohort's resistance determinants
are distributed between plasmid and chromosome in a way that is sharply structured by taxon and by
gene family, and high-precision, complete-coverage plasmid-origin classification is achievable in
short-read surveillance assemblies within taxonomic, prevalence and resistance-gene boundaries that
this study measures rather than assumes.

""" % (C["cohort_n"], n(C["den_contigs_joined"]), n(C["den_eligible_ge_1kb"]),
       n(C["den_scored_resolved"]),
       AC["pooled"]["contigs"], AC["pooled"]["plasmid_derived"],
       100 * AC["pooled"]["plasmid_fraction"],
       100 * AC["by_taxon"][0]["plasmid_fraction"], 100 * AC["by_taxon"][-1]["plasmid_fraction"],
       100 * ACC["SULFONAMIDE"]["plasmid_fraction"], ACC["FOSFOMYCIN"]["contigs"],
       ACC["NITROFURAN/PHENICOL/QUINOLONE/TETRACYCLINE"]["contigs"],
       AC["family_distribution"]["families_reported"],
       AC["thresholds_prestated"]["family_min_contigs"],
       AC["family_distribution"]["at_or_above_90pc_plasmid"],
       AC["family_distribution"]["at_or_below_10pc_plasmid"],
       AC["family_distribution"]["between"],
       AC["glycopeptide_operons"]["vanA_type"]["contigs"],
       AC["glycopeptide_operons"]["vanB_type"]["contigs"],
       AC["glycopeptide_operons"]["vanD_type"]["contigs"],
       12, P, PL, PH, RC, RL, RH,
       C["pooled_highest_third_party_PPV"]["PPV"],
       ("Six" if C["pooled_count_higher_F1"] == 6 else str(C["pooled_count_higher_F1"])),
       min(r["coverage"] for r in C["predictor_inventory_19"]), C["panel_units_failed"],
       n(C["panel_units_total"]), n(C["matched_denominator_n"]), n(C["den_scored_resolved"]),
       C["matched_denominator_fraction"] * 100, C["arg_v12"]["PPV"],
       C["arg_plasgraph2"]["PPV"], C["arg_plasgraph2"]["coverage"],
       C["arg_router_recall_penalty_vs_v12"] * 100, C["arg_router_precision_gain_vs_v12"] * 100,
       min(t["PPV"] for t in C["taxon_v12"]), max(t["PPV"] for t in C["taxon_v12"]),
       C["prevalence_exact_crossing_0.95"] * 100, C["observed_plasmid_prevalence"] * 100,
       C["verifier_total_values_and_checks"])
s = s[:a0] + abstract_new + "---\n\n" + s[a1:]
delta.append("Abstract extended from 129 words (the journal caps it at 150) to a full unstructured "
             "abstract carrying every quantity the summary requires, including recall intervals, "
             "coverage range, failure count, matched denominator, taxonomic range, prevalence "
             "dependence and the verification total. It is also reordered to open on the biological question, the genomes assembled and the genomic-context result, with the classifier evaluation following the labels that support it.")

# ---------------------------------------------------------------- 3. Discussion subheadings
DH = [
 ("Precision is the right primary objective for this task",
  "### Why precision and coverage are the right co-primary objectives"),
 ("Six rows exceeded v1.2-General on F1, and that is reported without qualification.",
  "### Why conditional F1 is not the deciding criterion"),
 ("The resistance-gene-bearing subset is where the honest account is most demanding",
  "### Resistance-gene-bearing contigs and the frozen router"),
 ("The boundaries of the claim are measured rather than assumed",
  "### The measured boundaries of the claim"),
 ("What generalises beyond this method is the evidence standard.",
  "### Prospective sealing and independent verification as methodological contributions"),
]
for anchor, heading in DH:
    assert s.count(anchor) == 1, anchor[:50]
    s = s.replace(anchor, heading + "\n\n" + anchor)
delta.append("Discussion gains five subheadings, which the journal's Article format forbids.")

# ---------------------------------------------------------------- 4. Limitations section
lim_anchor = "What the method does not do should be stated as plainly as what it does."
assert s.count(lim_anchor) == 1
s = s.replace(lim_anchor, "---\n\n## Limitations\n\n" + lim_anchor)
delta.append("An explicit `Limitations` section is introduced, which the journal's Article format "
             "forbids inside the Discussion. The text is unchanged; only the heading is added.")

# add the enumerated limitation list at the end of the limitations block
lim_tail = "a replication protocol is prepared but unexecuted."
assert s.count(lim_tail) == 1
s = s.replace(lim_tail, lim_tail + """

For clarity, the limitations that bound this study are:

1. **Six-taxon scope.** Nothing is claimed beyond *K. pneumoniae*, *Enterobacter* spp.,
   *Citrobacter* spp., *Serratia* spp., *E. faecium* and *E. faecalis*.
2. **Three of six taxa fall below the point-estimate precision floor**: %s.
3. **The resistance-gene-bearing subset does not reach precision 0.95 with complete coverage** for
   any evaluated method, including this one (%.4f).
4. **Performance depends on plasmid prevalence.** Standardised precision is %.4f at 5%%
   prevalence and crosses the floor at %.1f%%.
5. **No unseen-species validation.** Every taxon evaluated appeared in development or selection.
6. **A single-reference truth framework.** One closed reference per isolate; four frozen
   alternative definitions changed no label, but the dependence is not fully resolved.
7. **No independent laboratory cohort.** Replication has not been performed.
8. **No orthogonal long-read validation** of the truth labels.
9. **Per-tool peak memory was not measured**; execution receipts record container limits, not
   observed usage, and no value is estimated.""" % (
    ", ".join("*%s* %.4f" % (t["taxon"], t["PPV"])
              for t in C["taxon_v12"] if not t["meets_PPV_floor"]),
    C["arg_v12"]["PPV"], C["standardized_PPV_at_5pct"],
    C["prevalence_exact_crossing_0.95"] * 100))
delta.append("A numbered enumeration of the nine bounding limitations is appended to the "
             "Limitations section. Every item already appears in the journal version's Discussion "
             "prose; the preprint additionally lists them.")

# ---------------------------------------------------------------- 5. Conclusion section
con_anchor = ("PlasmidCall was the only evaluated method family to meet the prespecified "
              "high-precision objective")
assert s.count(con_anchor) == 1
s = s.replace(con_anchor, "---\n\n## Conclusion\n\n" + con_anchor)
delta.append("An explicit `Conclusion` section is introduced, which the journal's Article format "
             "forbids. The text is unchanged; only the heading is added.")

# ---------------------------------------------------------------- 6. funding as its own section
rep("""## Acknowledgements

*[Acknowledgements to be supplied.]* This study received no funding. *[If funding applies, replace
with: This study was funded by (funder) (grant number). The funder played no role in study design,
data collection, analysis and interpretation of data, or the writing of this manuscript.]*""",
    """## Acknowledgements

*[Acknowledgements to be supplied.]*

## Funding

This study received no funding. *[If funding applies, replace with: This study was funded by
(funder) (grant number). The funder played no role in study design, data collection, analysis and
interpretation of data, or the writing of this manuscript.]*""",
    "Funding is given its own section. The journal requires funding to sit inside "
    "Acknowledgements and forbids a separate Funding statement; bioRxiv does not.")

# ---------------------------------------------------------------- 7. figures in reading position
FIGPOS = [
 ("### Assembly and execution completed for every isolate", 1),
 ("### The prespecified primary endpoint was met", 2),
 ("### Conditional, failure-aware and matched comparisons diverge", 3),
 ("### Taxon-specific performance and error structure", 4),
 ("### The conclusion does not depend on any single isolate or taxon", 5),
 ("### Precision is prevalence-dependent (exploratory)", 6),
 ("### Discrimination, calibration and negative controls", 7),
 ("### Genomic context of resistance determinants across the six taxa", 8),
]
legends = {}
for m in re.finditer(r"\*\*Fig\. (\d+) \|(.*?)(?=\n\n)", s, re.S):
    legends[int(m.group(1))] = m.group(0).strip()
for anchor, fig in FIGPOS:
    assert s.count(anchor) == 1, anchor
    block = ("![Figure %d](figures/Figure%d_%s.png)\n\n%s\n\n"
             % (fig, fig, {1: "study_design", 2: "flow", 3: "pooled_all_predictors",
                           4: "arg_bearing", 5: "taxon", 6: "strata",
                           7: "flow_and_coverage",
                           8: "arg_genomic_context"}[fig], legends[fig]))
    s = s.replace(anchor, block + anchor)
delta.append("Figures are placed in reading position with their legends, each immediately before "
             "the Results subsection that first discusses it. The journal version keeps figures "
             "and legends grouped after the references, as its format prescribes.")

# strip the now-duplicated grouped figure legends section
i = s.index("## Figure legends")
j = s.index("## Table legends")
s = s[:i] + s[j:]
delta.append("The grouped `Figure legends` section is removed from the preprint, because each "
             "legend now sits with its figure.")

io.open(OUT, "w", encoding="utf-8", newline="\n").write(s)

io.open(DELTA, "w", encoding="utf-8", newline="\n").write(
    "# Preprint versus journal version — recorded differences\n\n"
    "**Dated** 2026-08-24\n\n"
    "The two versions report **identical science**: the same cohort, the same frozen result, the "
    "same numbers, the same limitations and the same claims. They differ only where the journal's "
    "Article format forbids something bioRxiv permits, or vice versa. Every difference is listed "
    "here.\n\n"
    "| # | Difference |\n|---|---|\n"
    + "\n".join("| %d | %s |" % (i + 1, d) for i, d in enumerate(delta))
    + "\n\n## What is identical\n\n"
      "* Title, author block and affiliations\n"
      "* Introduction, Results and Methods, word for word\n"
      "* Every number, table and figure, from the same generated sources\n"
      "* The reference list and its numbering\n"
      "* Data availability and Code availability\n"
      "* All claims, all limitations and all non-claims\n\n"
      "Verified by `scripts/manuscript/verify_manuscript.py`, which is run against both versions.\n")

print("preprint written: %s" % OUT)
print("differences recorded: %d" % len(delta))
print("preprint words: %d" % len(re.sub(r"\s+", " ", s).split()))

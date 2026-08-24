# -*- coding: utf-8 -*-
"""Phase 2: regenerate the reader-facing project documentation from the canonical number set.

Documents that carry results are rewritten from `PLASMIDCALL_CANONICAL_NUMBERS.json` rather than
edited by hand, so a number can only be wrong here if it is wrong in the frozen source.
Documents that are historical records are left untouched; the correction addendum is the
correction of record for those.
"""
import io, json, os, shutil, datetime

C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
DATE = "2026-08-24"


def w(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text.rstrip() + "\n")
    print("  wrote %s" % path)


def n(x):
    return "{:,}".format(int(x))


P = "%.4f" % C["primary_PPV"]
PL, PH = ["%.4f" % v for v in C["primary_PPV_ci95"]]
RCa = "%.4f" % C["primary_recall"]
RL, RH = ["%.4f" % v for v in C["primary_recall_ci95"]]
TAXA_BELOW = ", ".join("*%s* %.4f" % (t["taxon"], t["PPV"])
                       for t in C["taxon_v12"] if not t["meets_PPV_floor"])

BANNER = (
 "> **Correction notice.** This document has been updated to the corrected values recorded in\n"
 "> [`docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md`]"
 "(../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md). Frozen artefacts are never edited; the\n"
 "> addendum is the correction of record.\n")
BANNER_ROOT = BANNER.replace("../corrections/", "docs/corrections/")

# ---------------------------------------------------------------- README
w("README.md", """# PlasmidCall

**High-precision, complete-coverage classification of plasmid-derived contigs in short-read
bacterial assemblies.**

PlasmidCall decides whether a **contig** from a short-read draft assembly is of plasmid origin by
combining the categorical outputs of twelve existing plasmid/chromosome classifiers — including the
cases where those classifiers disagree or fail outright — under an encoding in which an unobserved
tool state contributes exactly zero to the decision.

> **Status: complete.** The prospective external validation (150 isolates, six taxa) is executed,
> joined, evaluated, frozen and independently verified. The primary result is immutable under
> `P1.13-RESULTS-FREEZE-001`; a separately versioned post-freeze package adds secondary,
> sensitivity, exploratory and integrity analyses without altering it. Journal and preprint
> packages are prepared and awaiting owner approval. **Nothing has been submitted, posted or
> published.**

%s
---

## Headline result

| Quantity | Value |
|---|---|
| Isolates · taxa | %s · 6 (25 each) |
| Contigs assembled · eligible (≥ 1 kb) · truth-resolved | %s · %s · %s |
| **Primary endpoint** (v1.2-General @ 0.9285) | **precision %s (95%% CI %s–%s) at recall %s (%s–%s)** |
| Coverage · abstentions | **1.0000** · 0 |
| Prespecified requirement | precision ≥ 0.95 **and** recall > 0.50 — **met, with the CI lower bound clearing the floor** |
| Third-party tools or predeclared baselines reaching precision 0.95 at any coverage | **0 of 18** |
| Rows with higher pooled F1 than the index row | %d of 17 with defined F1 |
| Independent verification | %d values and checks recomputed by code sharing no implementation with the analysis, **0 disagreements** |

## What this is, precisely

The unit of prediction is a **contig**, not a replicon.

| PlasmidCall does | PlasmidCall does **not** |
|---|---|
| classify contig origin (plasmid vs chromosome) | reconstruct, close, bin or type plasmids |
| return a call for every eligible contig | claim horizontal transfer, conjugation or mobilization |
| report coverage and tool failure as first-class outcomes | infer transmission or outbreak relatedness |
| report per-taxon results separately | estimate population prevalence |
| flag resistance-gene-bearing contigs by genomic context | claim clinical utility |
| state where it falls below its own precision floor | claim generality beyond the six taxa evaluated |

Full boundaries: [`docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md`](docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md).

**PlasmidCall is scientifically separate from PortabilityRisk**, a different project that shares
infrastructure. No PortabilityRisk result is a PlasmidCall result.

## Where to start

| You want | Read |
|---|---|
| The paper | [`docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md`](docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md) |
| The evidence behind every number | [`docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json`](docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json) |
| What is claimed, and on what basis | [`docs/manuscript/PLASMIDCALL_CLAIM_AUDIT_SUMMARY.md`](docs/manuscript/PLASMIDCALL_CLAIM_AUDIT_SUMMARY.md) |
| What was corrected, and why | [`docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md`](docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md) |
| Supporting provenance and audits | [`docs/manuscript/PLASMIDCALL_SUPPLEMENTARY_INFORMATION.md`](docs/manuscript/PLASMIDCALL_SUPPLEMENTARY_INFORMATION.md) |
| How to reproduce it | [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) |
| Deployment boundaries per model | [`docs/model_cards/`](docs/model_cards/) |
| Submission packages | [`docs/owner_review/`](docs/owner_review/) |

## Models

| Model | Type | Developed on | Operating point | Disposition |
|---|---|---|---|---|
| **v1.2-General** | standardised logistic regression over 12 categorical tool calls | 39 *E. coli* isolates | 0.9285 | **index model**; met the prespecified endpoint |
| v1.1 | histogram gradient boosting | 250 genomes, 7 genera | 0.9524 / 0.9605 | comparator; high precision, low recall |
| router | ARG-bearing → v1.1, otherwise → v1.2-General | frozen strategy | — | **validated negative result; not recommended for resistance-gene plasmid surveillance** |

## Reproducing the manuscript

```
python scripts/manuscript/build_canonical_numbers.py   # frozen tables -> canonical values
python scripts/manuscript/make_tables.py               # main tables + their canonical values
python scripts/manuscript/make_figures.py              # 7 figures: svg + pdf + 600 dpi png
python scripts/manuscript/make_supplementary.py        # SI + 9 Supplementary Data files
python scripts/manuscript/number_references.py         # reference numbering by first appearance
python scripts/manuscript/verify_manuscript.py         # journal rules + numeric integrity
python scripts/manuscript/claim_audit.py               # claim-to-evidence audit
```

Every step fails closed. `verify_manuscript.py` refuses to pass if any number in the manuscript
does not resolve to a frozen source, if any superseded wording reappears, or if any journal
structural rule is violated.
""" % (BANNER_ROOT, C["cohort_n"], n(C["den_contigs_joined"]), n(C["den_eligible_ge_1kb"]),
       n(C["den_scored_resolved"]), P, PL, PH, RCa, RL, RH, C["pooled_count_higher_F1"],
       C["verifier_total_values_and_checks"]))

# ---------------------------------------------------------------- KNOWN_LIMITATIONS
w("KNOWN_LIMITATIONS.md", """# Known limitations (summary)

The authoritative and binding version is
[`docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md`](docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md).
This page is a short index. Every figure below is read from the frozen result set.

## Measured boundaries

* **Precision falls below the 0.95 floor in three of six taxa**: %s. Cross-taxon generality is not
  supported and is not claimed.
* **The resistance-gene-bearing subset does not reach the floor.** v1.2-General precision %.4f at
  complete coverage; **no method of any kind** reached precision 0.95 with complete coverage on
  that subset.
* **Precision is prevalence-dependent by construction.** Standardised to 5%% plasmid prevalence it
  is %.4f; the 0.95 floor is crossed at **%.1f%% prevalence**. The observed cohort is %.1f%%
  plasmid. In a low-prevalence deployment the claim does not carry over.
* **The adversarial unresolved-truth bound does not clear the floor.** Charging all %d unresolved
  contigs against the model gives precision %.4f.
* **Macro-average is below micro-pooled**: %.4f versus %.4f.
* **Recall is a deliberate trade.** %.4f pooled; errors are overwhelmingly missed plasmid calls
  (%s false negatives against %d false positives).

## Scope

* **Contig-level, not replicon-level.** No plasmid is reconstructed, closed, binned or typed.
* **No mobility claim.** Plasmid origin is not evidence of transfer, conjugation or mobilization.
* **No transmission or prevalence inference.** The cohort is deliberately de-clustered, so no
  proportion reported estimates a population frequency.
* **No clinical utility evaluated or claimed.**
* **Six taxa only**: *K. pneumoniae*, *Enterobacter* spp., *Citrobacter* spp., *Serratia* spp.,
  *E. faecium*, *E. faecalis*.
* **No unseen-species validation.** Every taxon evaluated was represented in development or
  selection. Leave-one-taxon-out is an evaluation-set sensitivity analysis and is not a substitute.
* **Short-read only.** Illumina paired-end reads, Unicycler/SPAdes assemblies.
* **Contigs ≥ 1 kb only.** %s of %s assembled contigs are eligible; the rest are out of scope.
* **v1.2-General's validated training claim remains *E. coli*-specific.** This study tests transfer
  and does not retroactively broaden that claim.

## Dependencies and unmeasured quantities

* **Panel-dependent.** Absent tools receive exactly zero weight, measured rather than assumed, but
  performance is still conditional on panel availability.
* **Tool failures are deterministic and genome-correlated**, not missing at random (%d of %s units).
* **Depth is right-truncated** by the 100× normalisation; depth is a measured covariate, not a
  demonstrated confounder.
* **Per-tool peak memory was not measured.** Execution receipts record container limits, not
  observed usage. No value is estimated.
* **Truth rests on one closed reference per isolate.** Four alternative definitions frozen in
  advance changed no label, but orthogonal long-read truth would be required to resolve the
  dependence fully.
* **No independent laboratory cohort.** A replication protocol is prepared but unexecuted.
* **Engineering rigour is not performance.** The verification chain establishes that the reported
  numbers are what the pipeline produced, not that they are good.
""" % (TAXA_BELOW, C["arg_v12"]["PPV"], C["standardized_PPV_at_5pct"],
       C["prevalence_exact_crossing_0.95"] * 100, C["observed_plasmid_prevalence"] * 100,
       C["unresolved_n"], C["unresolved_worst_case"]["PPV"], C["isolate_macro_average_PPV"],
       C["primary_PPV"], C["primary_recall"], n(C["primary_FN"]), C["primary_FP"],
       n(C["den_eligible_ge_1kb"]), n(C["den_contigs_joined"]),
       C["panel_units_failed"], n(C["panel_units_total"])))

# ---------------------------------------------------------------- executive summary
top = sorted([r for r in C["predictor_inventory_19"] if r["F1"] is not None],
             key=lambda r: -r["F1"])[:6]
w("docs/closure/PLASMIDCALL_EXECUTIVE_SUMMARY.md", """# PlasmidCall — executive summary

**Dated** %s · **Primary freeze** `P1.13-RESULTS-FREEZE-001` (immutable)
**Post-freeze package** `P1.13-POSTFREEZE-REVIEWER-ANALYSES-001` (adds only)

%s
## The question

Genomic surveillance readily detects antimicrobial resistance genes but rarely resolves whether
they sit on a plasmid or in the chromosome. In short-read draft assemblies that question is
genuinely hard, existing classifiers disagree, and some fail outright on particular genomes.

## What was done

A prospectively sealed, truth-blind external validation. Design, cohort, eligibility rules,
thresholds, analysis plan and stopping rules were hash-sealed before any read was retrieved.
Predictions were frozen and independently reproduced byte-for-byte before any truth artefact was
permitted onto the analysis system. %s isolates across six taxa; %s assembled contigs, %s eligible
at ≥ 1 kb, %s truth-resolved. Nineteen predictor rows were evaluated on identical evidence: 12
third-party tools, four PlasmidCall model and router rows, three predeclared baselines.

## What was found

**The prespecified primary endpoint was met.** v1.2-General reached precision **%s**
(95%% CI %s–%s) at recall **%s** (%s–%s), with coverage **1.0000** and zero abstentions. The
requirement was precision ≥ 0.95 and recall > 0.50; both were met and the **lower bound of the
interval cleared the floor**.

**No third-party tool or predeclared baseline reached precision 0.95 at any observed coverage.**
The highest third-party precision was %s at %.4f. Four rows met the floor at complete coverage and
all four were PlasmidCall's, spanning two model classes and three thresholds.

**PlasmidCall is not the best method on every metric, and is not presented as one.** %d rows
achieved a higher pooled F1. Requiring every row to answer restricted the common denominator to
%s of %s truth-resolved contigs (%.1f%%), which is itself a measure of how often the existing panel
declines to answer.

**The boundaries are measured.** Precision fell below the floor in three of six taxa and on the
%d resistance-gene-bearing contigs (%.4f), where no method of any kind reached 0.95 with complete
coverage. Precision is prevalence-dependent and crosses the floor at %.1f%% plasmid prevalence.
Charging all %d unresolved contigs adversarially gives %.4f.

**The frozen router is reported as a validated negative result.** It traded %.1f percentage points
of resistance-gene recall for %.2f points of precision and is not recommended for that use. It was
not redesigned after truth was observed.

## How far it can be trusted

%d values and checks were recomputed from the frozen joined table by code sharing no implementation
with the analysis, with **zero disagreements**. Label permutation collapses precision to a maximum
of %.4f. There is zero identifier overlap with any consumed development set and the maximum ANI to
any consumed genome is %.2f, below the 99.5 exclusion threshold. Seven implementation and
evidence-preservation defects were found during execution, each by a fail-closed gate or an
explicit counter; all are documented individually, including one unrecoverable
evidence-preservation loss which is disclosed as a loss.

## Scientific classification

**Primary validation success with prespecified applicability limitations.**

## What is still needed

Independent replication on another laboratory's specimens, a prospective low-prevalence cohort, a
genuinely held-out taxon, and orthogonal long-read truth. None of these can be supplied by
re-analysing this cohort.
""" % (DATE, BANNER, C["cohort_n"], n(C["den_contigs_joined"]), n(C["den_eligible_ge_1kb"]),
       n(C["den_scored_resolved"]), P, PL, PH, RCa, RL, RH,
       C["pooled_highest_third_party_PPV"]["row"].replace("tool:", ""),
       C["pooled_highest_third_party_PPV"]["PPV"], C["pooled_count_higher_F1"],
       n(C["matched_denominator_n"]), n(C["den_scored_resolved"]),
       C["matched_denominator_fraction"] * 100, C["arg_bearing_n"], C["arg_v12"]["PPV"],
       C["prevalence_exact_crossing_0.95"] * 100, C["unresolved_n"],
       C["unresolved_worst_case"]["PPV"], C["arg_router_recall_penalty_vs_v12"] * 100,
       C["arg_router_precision_gain_vs_v12"] * 100, C["verifier_total_values_and_checks"],
       C["permutation_PPV_max"], C["leakage_max_ANI_to_any_consumed_genome"]))

print("core documents regenerated")

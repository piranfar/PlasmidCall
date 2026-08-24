# -*- coding: utf-8 -*-
"""Phase 2, part 2: model cards, limitations, intended use, citation metadata, project state,
and the surgical corrections to documents that are records rather than regenerable summaries."""
import io, json, os, csv

C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
DATE = "2026-08-24"


def w(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text.rstrip() + "\n")
    print("  wrote %s" % path)


def patch(path, pairs, banner=None, must=True):
    s = io.open(path, encoding="utf-8").read()
    applied = 0
    for old, new in pairs:
        cnt = s.count(old)
        if cnt == 0:
            if must:
                print("   !! anchor absent in %s: %r" % (path, old[:60]))
            continue
        s = s.replace(old, new)
        applied += cnt
    if banner and banner.split("\n")[0] not in s:
        lines = s.split("\n")
        k = 1
        while k < len(lines) and lines[k].strip() == "":
            k += 1
        while k < len(lines) and lines[k].strip() != "":
            k += 1
        s = "\n".join(lines[:k + 1] + [banner] + lines[k + 1:])
    io.open(path, "w", encoding="utf-8", newline="\n").write(s)
    print("  patched %s (%d substitutions)" % (path, applied))


def n(x):
    return "{:,}".format(int(x))


BAN = ("> **Correction notice.** Values in this document follow\n"
       "> [`PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).\n"
       "> Frozen artefacts are never edited; the addendum is the correction of record.\n")
BAN_RES = BAN.replace("../corrections/", "../../corrections/")
TAX = C["taxon_v12"]

# ---------------------------------------------------------------- model card v1.2
w("docs/model_cards/MODEL_CARD_v1.2-General.md", """# Model card — PlasmidCall v1.2-General

**Status** frozen · **Threshold** 0.9285 (frozen before this validation; never re-derived)
**Role** index model · **Validation** prospectively sealed, truth-blind, 150 isolates, six taxa

%s
## Intended use

Classify whether a contig of at least 1 kb from a short-read bacterial draft assembly is of
**plasmid origin**, for surveillance triage under a declared precision requirement, in the six taxa
evaluated, at plasmid prevalence above roughly %.0f%%.

## Not intended for

Plasmid reconstruction, binning or typing. Inference of mobility, horizontal transfer, conjugation
or transposition. Transmission or outbreak inference. Population prevalence estimation. Clinical
decision-making. Taxa outside the six evaluated. Long-read or hybrid input. Contigs below 1 kb.
Deployments where sensitivity rather than precision is the governing objective.

## Architecture and inputs

Standardised logistic regression over the **categorical calls of 12 panel classifiers**, under an
immutable 102-feature encoding. Inputs are the normalised seven-term vocabulary — `chromosome`,
`plasmid`, `unknown`, `unclassified`, `repeat`, `FAILED`, `MISSING`. **Direct-block neutrality:** a
tool in a state never seen in training contributes exactly 0.0 to the logit. Measured on the frozen
model, not assumed; maximum absolute contribution 0.0.

## Training data

39 *Escherichia coli* isolates. **The validated training claim is therefore *E. coli*-specific.**
This validation tests transfer to other taxa; it does not retroactively broaden the training claim.

## Verified performance (150 isolates, %s truth-resolved contigs)

| Metric | Value | 95%% CI (isolate-clustered, 4,000 replicates) |
|---|---|---|
| **Precision (PPV)** | **%.4f** | %.4f–%.4f |
| Recall | %.4f | %.4f–%.4f |
| Specificity | %.4f | — |
| NPV | %.4f | — |
| F1 | %.4f | — |
| Balanced accuracy | %.4f | — |
| MCC | %.4f | — |
| **Coverage** | **1.0000** | zero abstentions |
| AUROC · AUPRC | %.4f · %.4f | — |
| Brier · 10-bin ECE | %.4f · %.4f | — |

Met the prespecified endpoint (precision ≥ 0.95 **and** recall > 0.50) with the interval lower
bound above the floor. %d evaluated rows achieved a higher pooled F1; **no third-party tool or
predeclared baseline reached precision 0.95 at any observed coverage**.

## Applicability boundaries (measured, not assumed)

* Precision ≥ %.4f in every taxon but **below 0.95 in three of six**: %s. Recall ranges
  %.4f–%.4f.
* **Resistance-gene-bearing subset (n = %d): precision %.4f** — below the floor — at recall %.4f
  and complete coverage. plASgraph2 achieved higher precision (%.4f) at coverage %.4f.
* **Prevalence-dependent**: standardised precision %.4f at 5%% plasmid prevalence, crossing the
  0.95 floor at %.1f%%. Observed cohort prevalence %.1f%%.
* Macro-average across isolates %.4f versus micro-pooled %.4f.
* Depth is right-truncated by the 100× normalisation; depth is a measured covariate, not a
  demonstrated confounder.
* Performance is conditional on panel availability.

## Failure behaviour

Errors are overwhelmingly false negatives (%s FN against %d FP): precision-protective by design.
Absent or failed tools reduce the evidence available but never inject a phantom signal. The model
does not abstain: it returned a call for every eligible contig in the validation cohort.

## Robustness

Both floors hold under removal of any single taxon from evaluation (precision %.4f–%.4f) and the
maximum influence of any single isolate on pooled precision is %.5f. Four alternative truth
definitions frozen before re-mapping changed no contig's label. Label permutation collapses
precision to a maximum of %.4f.

## Provenance

Estimator digest bound in the prediction-freeze receipt. Environment: Python 3.14.6,
scikit-learn 1.9.0, numpy 2.5.0, pandas 3.0.3.
""" % (BAN, C["prevalence_exact_crossing_0.95"] * 100, n(C["den_scored_resolved"]),
       C["primary_PPV"], C["primary_PPV_ci95"][0], C["primary_PPV_ci95"][1],
       C["primary_recall"], C["primary_recall_ci95"][0], C["primary_recall_ci95"][1],
       C["primary_specificity"], C["primary_NPV"], C["primary_F1"],
       C["primary_balanced_accuracy"], C["primary_MCC"],
       C["calibration_v12"]["AUROC"], C["calibration_v12"]["AUPRC"],
       C["calibration_v12"]["Brier"], C["calibration_v12"]["ECE_10bin"],
       C["pooled_count_higher_F1"], min(t["PPV"] for t in TAX),
       ", ".join("*%s* %.4f" % (t["taxon"], t["PPV"]) for t in TAX if not t["meets_PPV_floor"]),
       min(t["recall"] for t in TAX), max(t["recall"] for t in TAX),
       C["arg_bearing_n"], C["arg_v12"]["PPV"], C["arg_v12"]["recall"],
       C["arg_plasgraph2"]["PPV"], C["arg_plasgraph2"]["coverage"],
       C["standardized_PPV_at_5pct"], C["prevalence_exact_crossing_0.95"] * 100,
       C["observed_plasmid_prevalence"] * 100, C["isolate_macro_average_PPV"], C["primary_PPV"],
       n(C["primary_FN"]), C["primary_FP"], C["loto_PPV_range"][0], C["loto_PPV_range"][1],
       C["isolate_max_abs_influence_on_pooled_PPV"], C["permutation_PPV_max"]))

# ---------------------------------------------------------------- model card v1.1
E = C["error_architecture"]
inv = {r["row"]: r for r in C["predictor_inventory_19"]}
w("docs/model_cards/MODEL_CARD_v1.1.md", """# Model card — PlasmidCall v1.1

**Status** frozen · **Thresholds** 0.9524 (standard) and 0.9605 (high-confidence), neither
re-derived · **Role** comparator

%s
## Intended use

The same contig-origin classification task as v1.2-General, at a deliberately more conservative
operating point. Appropriate where a very low false-positive rate matters more than recall and the
user accepts recovering roughly one plasmid contig in four.

## Not intended for

Everything listed as out of scope for v1.2-General, and additionally any use where recall matters:
its recall in this validation is below the 0.50 floor the study prespecified.

## Architecture and training data

Histogram-based gradient boosting over a 250-genome development set spanning seven genera.

## Verified performance (%s truth-resolved contigs)

| Operating point | Precision | 95%% CI | Recall | 95%% CI | Coverage |
|---|---|---|---|---|---|
| 0.9524 (standard) | %.4f | %.4f–%.4f | %.4f | %.4f–%.4f | 1.0000 |
| 0.9605 (high-confidence) | %.4f | %.4f–%.4f | %.4f | %.4f–%.4f | 1.0000 |

Both operating points exceed the 0.95 precision floor at complete coverage. **Neither meets the
prespecified recall floor of 0.50**, which is why v1.1 is a comparator and not the index model.

Discrimination and calibration: AUROC %.4f, AUPRC %.4f, Brier %.4f, 10-bin ECE %.4f. Calibration
is materially worse than v1.2-General's.

## Failure behaviour

Errors are almost entirely false negatives: %s FN against %d FP at 0.9524, and %s against %d at
0.9605.

## Provenance

Frozen before this validation. No threshold was re-derived here.
""" % (BAN, n(C["den_scored_resolved"]),
       inv["v1.1@0.9524"]["PPV"], inv["v1.1@0.9524"]["PPV_ci95"][0],
       inv["v1.1@0.9524"]["PPV_ci95"][1], inv["v1.1@0.9524"]["recall"],
       inv["v1.1@0.9524"]["recall_ci95"][0], inv["v1.1@0.9524"]["recall_ci95"][1],
       inv["v1.1@0.9605_high_conf"]["PPV"], inv["v1.1@0.9605_high_conf"]["PPV_ci95"][0],
       inv["v1.1@0.9605_high_conf"]["PPV_ci95"][1], inv["v1.1@0.9605_high_conf"]["recall"],
       inv["v1.1@0.9605_high_conf"]["recall_ci95"][0],
       inv["v1.1@0.9605_high_conf"]["recall_ci95"][1],
       C["calibration_v11"]["AUROC"], C["calibration_v11"]["AUPRC"],
       C["calibration_v11"]["Brier"], C["calibration_v11"]["ECE_10bin"],
       n(E["v1.1@0.9524"]["FN"]), E["v1.1@0.9524"]["FP"],
       n(E["v1.1@0.9605_high_conf"]["FN"]), E["v1.1@0.9605_high_conf"]["FP"]))

# ---------------------------------------------------------------- router card
w("docs/model_cards/MODEL_CARD_router_NOT_RECOMMENDED.md", """# Model card — PlasmidCall router

## NOT RECOMMENDED for resistance-gene plasmid surveillance

**Status** frozen · **Disposition** validated negative result · **Not redesigned after truth**

%s
## What it is

A frozen two-domain routing strategy: contigs carrying an annotated resistance determinant are
routed to v1.1; all other contigs are routed to v1.2-General. Contigs whose resistance annotation
failed are abstained on and counted separately.

## Why it is published as a failure

The router was frozen before truth, evaluated exactly as frozen, and found wanting on the subset it
was designed to protect. It is reported rather than removed, and it was **not** redesigned after
the result was seen, because redesigning it would forfeit the prospective standard the study exists
to uphold.

## Verified performance

| Set | Precision | Recall | Coverage |
|---|---|---|---|
| Pooled (%s contigs) | %.4f | %.4f | 1.0000 |
| **Resistance-gene-bearing (%d contigs)** | **%.4f** | **%.4f** | 1.0000 |
| v1.2-General on the same resistance-gene subset, for comparison | %.4f | %.4f | 1.0000 |

On the resistance-gene-bearing subset the router recovers **%.1f percentage points less** than
v1.2-General — roughly one third as much plasmid-borne resistance-gene signal — in exchange for
**%.2f points** of precision. Neither reaches the 0.95 precision floor on that subset.

## Recommendation

**Do not use the router for resistance-gene plasmid surveillance.** Where a precision floor governs
and coverage must be complete, use v1.2-General and apply the boundaries in its model card. The
router remains in the inventory as a reported negative result, not as a recommended configuration.
""" % (BAN, n(C["den_scored_resolved"]), inv["router"]["PPV"], inv["router"]["recall"],
       C["arg_bearing_n"], C["arg_router"]["PPV"], C["arg_router"]["recall"],
       C["arg_v12"]["PPV"], C["arg_v12"]["recall"],
       C["arg_router_recall_penalty_vs_v12"] * 100,
       C["arg_router_precision_gain_vs_v12"] * 100))

# ---------------------------------------------------------------- intended use
w("docs/closure/PLASMIDCALL_INTENDED_USE.md", """# PlasmidCall — intended-use statement

**Dated** %s · Binds the frozen result `P1.13-RESULTS-FREEZE-001`.

%s
## Intended use

PlasmidCall v1.2-General is intended to classify whether an individual contig of at least 1 kb,
from an Illumina short-read bacterial draft assembly, is of **plasmid origin**, in order to
establish the genomic context of antimicrobial resistance determinants for **surveillance triage**.

It is intended for use where:

1. the deployment objective is a **precision floor** rather than maximal sensitivity or F1;
2. an answer is required for **every** contig, so a method that declines to answer is unacceptable;
3. the organism is one of the six taxa evaluated — *Klebsiella pneumoniae*, *Enterobacter* spp.,
   *Citrobacter* spp., *Serratia* spp., *Enterococcus faecium*, *Enterococcus faecalis*;
4. plasmid prevalence among eligible contigs is above roughly **%.0f%%**;
5. the twelve-tool panel is available, since the model consumes its categorical calls.

## Intended user

A genomic-surveillance laboratory or bioinformatics group with the capacity to run the twelve-tool
panel in pinned container images and to interpret contig-level output.

## Explicitly out of scope

| Out of scope | Why |
|---|---|
| Plasmid reconstruction, closing, binning or typing | the unit of prediction is a contig |
| Mobility, conjugation, horizontal transfer | not measured and not inferable from origin |
| Transmission, outbreak relatedness, epidemiological linkage | not measured |
| Population prevalence estimation | the cohort is deliberately de-clustered |
| Clinical decision-making | no clinical utility has been evaluated |
| Taxa outside the six evaluated | no unseen-species validation exists |
| Low-prevalence settings below ~%.0f%% plasmid content | the precision claim does not carry over |
| Resistance-gene-bearing contigs where a 0.95 precision floor is mandatory | precision is %.4f on that subset, below the floor, and **no method reached 0.95 with complete coverage** there |
| Contigs below 1 kb, long-read or hybrid assemblies | outside the evaluated eligibility rule |
| Deployments where sensitivity governs | recall is %.4f; a high-recall tool is the better choice |

## Required reporting when used

A user reporting PlasmidCall output should state the taxon, the plasmid prevalence of the material,
the panel completeness achieved, and whether the contigs in question carry resistance determinants,
because each of these changes the applicable precision estimate.

## Status

Validated once, prospectively, on public isolates by the developing group. **Independent
replication on another laboratory's specimens has not been performed.** Until it has, deployment
should be treated as evaluation rather than as established practice.
""" % (DATE, BAN, C["prevalence_exact_crossing_0.95"] * 100,
       C["prevalence_exact_crossing_0.95"] * 100, C["arg_v12"]["PPV"], C["primary_recall"]))

# ---------------------------------------------------------------- citation metadata
w("CITATION.cff", """cff-version: 1.2.0
message: "If you use PlasmidCall or its validation data, please cite the preprint below."
title: "PlasmidCall: high-precision complete-coverage classification of plasmid-derived contigs"
abstract: >-
  Prospectively sealed, truth-blind external validation of plasmid-origin classification across
  150 isolates and six bacterial taxa, comparing 12 third-party tools within a frozen 19-row
  predictor inventory. The prespecified endpoint (positive predictive value >= 0.95 and recall
  > 0.50) was met at %s (95%% CI %s-%s) precision and %s recall with complete coverage; no
  third-party tool or predeclared baseline reached 0.95 precision at any observed coverage.
type: software
authors:
  - family-names: Piranfar
    given-names: Vahhab
    email: vahab.p@gmail.com
    orcid: "https://orcid.org/PLACEHOLDER-TO-BE-SUPPLIED"
    affiliation: "PLACEHOLDER - to be supplied"
version: "1.2-General"
date-released: "%s"
license: MIT
repository-code: "PLACEHOLDER - public URL to be supplied on release"
keywords:
  - antimicrobial resistance
  - plasmid
  - contig classification
  - bacterial genomics
  - prospective validation
  - external validation
  - short-read assembly
  - genomic surveillance
preferred-citation:
  type: article
  title: >-
    Genomic context of resistance determinants across six bacterial taxa with prospective classifier validation
  authors:
    - family-names: Piranfar
      given-names: Vahhab
  year: 2026
  journal: "bioRxiv"
  doi: "PLACEHOLDER - assigned on posting"
""" % ("%.4f" % C["primary_PPV"], "%.4f" % C["primary_PPV_ci95"][0],
       "%.4f" % C["primary_PPV_ci95"][1], "%.4f" % C["primary_recall"], DATE))

# ---------------------------------------------------------------- project state
w("docs/closure/P113_CURRENT_STATE.json", json.dumps({
    "project": "PlasmidCall",
    "as_of_utc": DATE,
    "phase": "manuscript and submission packages prepared; awaiting owner approval",
    "primary_freeze": {"id": C["results_freeze_id"], "status": "IMMUTABLE", "modified": False},
    "post_freeze_package": {"id": "P1.13-POSTFREEZE-REVIEWER-ANALYSES-001",
                            "relationship": "adds only", "verdict": C["postfreeze_verdict"]},
    "correction_addendum": {"id": "P1.13-CORRECTION-ADDENDUM-001",
                            "file": "docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md",
                            "corrections": 5, "wording_corrections": 8,
                            "frozen_artefacts_edited": False},
    "primary_endpoint": {"met": True, "PPV": C["primary_PPV"], "PPV_ci95": C["primary_PPV_ci95"],
                         "recall": C["primary_recall"], "recall_ci95": C["primary_recall_ci95"],
                         "coverage": 1.0, "abstentions": 0},
    "scientific_classification":
        "Primary validation success with prespecified applicability limitations",
    "verification": {"values_and_checks": C["verifier_total_values_and_checks"],
                     "disagreements": 0},
    "deliverables_prepared": {
        "journal_package": "docs/owner_review/NPJ_AMR_SUBMISSION",
        "preprint_package": "docs/owner_review/BIORXIV_PREPRINT",
        "documentation": "updated to the correction addendum",
        "figures": 7, "main_tables": 4, "supplementary_tables": 18,
        "supplementary_data_files": 9, "references": 38},
    "actions_not_taken": [
        "nothing submitted to any journal",
        "nothing posted to any preprint server",
        "no repository made public",
        "no DOI minted",
        "no collaborator contacted",
        "no raw reads deleted",
        "no server terminated"],
    "owner_decisions_outstanding": "docs/owner_review/OWNER_DECISIONS.md",
}, indent=1))

# ---------------------------------------------------------------- surgical patches
print("surgical corrections")
patch("docs/evidence/P1.13_results/P113_FINAL_EVALUATION_REPORT.md",
      [("| MCC | 0.7674 | — |", "| MCC | 0.7614 | — |"),
       ("| **v1.2-General** | 1.000 | **0.9770** | 0.6631 | 0.7900 | 0.7674 |",
        "| **v1.2-General** | 1.000 | **0.9770** | 0.6631 | 0.7900 | 0.7614 |")],
      banner=BAN_RES)

patch("docs/postfreeze/PLASMIDCALL_POSTFREEZE_PACKAGE_SUMMARY.md",
      [("standardised PPV is **0.8767 at 5% prevalence** and falls below 0.95 somewhere\n"
        "between roughly 15% and 20% prevalence.",
        "standardised PPV is **0.8767 at 5% prevalence**. On the frozen grid it clears 0.95 at 15%\n"
        "and fails at 10%; the closed-form root of the same identity places the crossing at\n"
        "**12.3% prevalence**."),
       ("**PF10b — highest-confidence truth subset: PPV 0.9081**",
        "**PF10b — complete-resolution isolate subset (formerly \"highest-confidence truth "
        "subset\"): PPV 0.9081**"),
       ("| | High-confidence subset | Remainder |",
        "| | Complete-resolution subset | Remainder |")],
      banner=BAN.replace("../corrections/", "../corrections/"))

patch("docs/postfreeze/PLASMIDCALL_INTERNAL_REVIEW_MATRIX.md",
      [("PPV is **0.8767 at 5% prevalence**, and falls below the 0.95 floor below roughly\n"
        "15–20% prevalence.",
        "PPV is **0.8767 at 5% prevalence**. The frozen grid clears 0.95 at 15% and fails at 10%;\n"
        "the closed-form root places the crossing at **12.3% prevalence**."),
       ("defines a **prediction-blind** highest-confidence subset",
        "defines a **prediction-blind** complete-resolution isolate subset")],
      banner=BAN.replace("../corrections/", "../corrections/"))

print("done")

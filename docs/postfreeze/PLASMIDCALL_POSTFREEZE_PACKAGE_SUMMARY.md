# P1.13-POSTFREEZE-REVIEWER-ANALYSES-001 — package summary

**Dated** 2026-08-24 · **Verification** `POSTFREEZE_VERIFIER_PASS` — 34 independent checks, **0 disagreements**
**Primary freeze** `P1.13-RESULTS-FREEZE-001` — **immutable and unmodified**

> **Correction notice.** Values in this document follow
> [`PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

This package **adds only**. It does not alter the frozen primary result, its tables, endpoints,
models, thresholds, router, cohort or truth labels. Every analysis is classified below.

---

## Classification

| Class | Analyses |
|---|---|
| **Secondary** | PF01 taxon robustness · PF04 ARG complete · PF06 contig length · PF07 depth & assembly quality · PF13 score/calibration |
| **Sensitivity** | PF02 leave-one-taxon-out · PF03 isolate influence · PF08 truth definition · PF09 unresolved bounds · PF10 reference quality |
| **Exploratory / post hoc** | PF05 prevalence standardisation · PF12 comparator fairness · PF13b score distributions |
| **Integrity audit** | PF11 relatedness/leakage · PF15 negative controls |
| **Descriptive** | PF14 computational deployment |

---

## Findings that STRENGTHEN the paper

**The conclusion does not depend on any single taxon (PF02).** Excluding each taxon in turn from
*evaluation* (no retraining), pooled PPV ranges 0.9649–0.9839 and recall 0.5981–0.7194. **Both
floors hold under every exclusion**, including removal of *K. pneumoniae*, the strongest taxon
(PPV 0.9649, recall 0.5981). This is **not** unseen-species validation and is not described as such.

**No single isolate drives the result (PF03).** Maximum absolute leave-one-isolate-out influence on
pooled PPV is **0.00356**. Macro-average PPV across 150 isolates is 0.9572 — lower than the
micro-pooled 0.9770, as expected when large isolates dominate, but still above the floor.

**The endpoint survives every frozen alternative truth definition (PF08).** A four-point grid was
frozen *before* any mapping ran: stricter (identity 0.97 / coverage 0.85), permissive (0.90 / 0.70),
and ambiguity margins 0.05 and 0.15. All four mapped 150/150 isolates. PPV ranges 0.9769–0.9770 and
recall 0.6628–0.6631, with **zero label flips** relative to the primary. Both floors are met in all
five settings. No favourable threshold was selected.

**Discrimination and calibration are strong (PF13).** v1.2-General: **AUROC 0.9873, AUPRC 0.9646**,
Brier 0.0256, 10-bin ECE 0.0068. Frozen thresholds are marked on the curves; no new threshold
was chosen.

**Negative controls behave correctly (PF15).** Label permutation collapses PPV from 0.9770 to a
maximum of **0.2709** across 200 permutations. Row-order shuffling leaves metrics bit-identical.
Zero duplicate contig IDs, zero excluded-isolate leakage, all rows in the sealed cohort.

**No leakage or near-clonality (PF11).** Zero exact identifier overlap with any consumed set;
**maximum ANI to any consumed genome 99.48**, below the 99.5 exclusion threshold; **zero
within-cohort pairs at ANI ≥ 99.5**. Assemblies and existing ANI only — no reads re-downloaded.

**Comparator advantage on F1 is partly an artefact of not answering (PF12).** Conditional,
failure-aware and matched performance are reported separately per row, with the F1 inflation
attributable to restricted evaluable output made explicit.

---

## Findings that WEAKEN or BOUND the claims

**1. Precision falls below the floor in THREE of six taxa, not two.** *Citrobacter* 0.9462,
*Enterobacter* 0.9358, *E. faecalis* 0.9130. **This corrects an error in my own earlier prose**;
the stratified tables were always right. All manuscript text is corrected. The frozen receipt's
`classification_basis` block carries the wrong value 2 and is **not edited** — the erratum is
recorded in `PF_VERIFICATION_RECEIPT.json` as the correction of record.

**2. The precision claim is prevalence-dependent (PF05).** Holding sensitivity and specificity at
observed values, standardised PPV is **0.8767 at 5% prevalence**. On the frozen grid it clears 0.95 at 15%
and fails at 10%; the closed-form root of the same identity places the crossing at
**12.3% prevalence**. The observed cohort is 23.9% plasmid. **In a
low-prevalence deployment the 0.95 claim does not carry over.** The frozen observed-cohort endpoint
is unchanged; the standardised grid is reported alongside it.

**3. The adversarial unresolved-truth bound breaks the floor (PF09).** If all 413 unresolved
eligible contigs are charged against the model, PPV falls to **0.9055**. The best case is 0.9860.
The primary analysis excludes unresolved contigs, as prespecified, and never coerces them — but the
worst-case bound does not clear 0.95 and is now stated.

**4. Macro-average is materially below micro-pooled.** 0.9572 vs 0.9770. Isolates are not equally
weighted in the pooled figure; both are now reported.

**5. Sparse ARG strata cannot support conclusions.** Of 182 ARG family/class strata, most carry
denominators too small to interpret and are flagged `suppressed_sparse` rather than reported as
findings. Only ~10 antimicrobial classes have usable denominators.

---

## A sensitivity analysis that failed, and why it is reported anyway

**PF10b — complete-resolution isolate subset (formerly "highest-confidence truth subset"): PPV 0.9081** (59 isolates, 1,753 contigs) versus 0.9769
on all resolved contigs. Taken at face value this looks like the primary result inflating.

It is not, and the reason is a **flaw in my own subset definition**. Requiring *zero unresolved
contigs* selected a systematically unusual subset:

| | Complete-resolution subset | Remainder |
|---|---|---|
| Mean reference plasmids | **0.85** | 3.74 |
| Mean eligible contigs | 29.7 | 88.3 |
| *K. pneumoniae* (PPV 0.9982) | **1 isolate** | 24 |
| *Enterobacter* + *E. faecalis* (PPV 0.9358 / 0.9130) | **33 isolates** | 17 |

The subset is plasmid-poor (lower prevalence → lower PPV by construction) and skewed towards the
weakest taxa while excluding almost all of the strongest. The definition was prediction-blind, but
it was **not** taxon- or prevalence-balanced, so it confounds truth quality with case mix.

**It is reported rather than discarded**, with this explanation, because a reviewer will construct
exactly this subset and should find our own analysis of it already present. A defensible
alternative would stratify or match on taxon and plasmid content; that is stated as future work
rather than run now, because building it after seeing 0.9081 would be outcome-driven design.

---

## Analyses infeasible with existing data

| Analysis | Why |
|---|---|
| Per-tool **peak RAM** | receipts record container memory *limits* (24g), not observed RSS. Not invented — recorded as NOT MEASURED |
| Per-tool **database sizes** | databases are bundled inside pinned images; per-database sizes were never recorded separately |
| **Unseen-species** generalisation | every taxon here appears in development or selection. Requires a genuinely held-out taxon |
| **Low-prevalence** empirical validation | bounded analytically by PF05; needs a prospective low-prevalence cohort |
| **Orthogonal long-read truth** | one closed reference per isolate; independent truth needs new sequencing |

---

## Verification

`PF_VERIFICATION_RECEIPT.json`: 34 independent checks recomputed from the frozen joined table by
code that does not share implementation with the post-freeze scripts. **Zero disagreements.**
Denominators reconcile exactly (19,320 / 9,784 / 9,371 / 413 / 150 isolates / 635 ARG-bearing).
Frozen inputs re-verified by hash. All 23 post-freeze artefacts hashed. Every analysis carries an
explicit prespecified/secondary/sensitivity/exploratory label.

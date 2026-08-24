# PlasmidCall — internal reviewer simulation

**Package** `P1.13-POSTFREEZE-REVIEWER-ANALYSES-001` · **Dated** 2026-08-24
**Primary freeze** `P1.13-RESULTS-FREEZE-001` — immutable, unmodified by anything below.

> **Correction notice.** Values in this document follow
> [`PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

Three documented review passes. Each concern is stated as a reviewer would state it, answered from
evidence, and where evidence did not already exist a defensible analysis was run. No analysis here
was run to improve a number, and none altered the primary endpoint.

---

## Pass A — statistical reviewer

**A1. "PPV depends on prevalence. Your cohort is 23.9% plasmid; in a low-prevalence setting the
precision claim evaporates."**
Valid and now quantified (PF05). Holding sensitivity and specificity at observed values and
re-standardising: PPV is **0.8767 at 5% prevalence**. The frozen grid clears 0.95 at 15% and fails at 10%;
the closed-form root places the crossing at **12.3% prevalence**. **This bounds the claim and is now stated in the manuscript.** The frozen
endpoint remains the observed-cohort value; the standardised grid is reported alongside it, not
instead of it.

**A2. "Contigs within an isolate are not independent."**
Addressed from the outset. Every interval is an isolate-clustered bootstrap (4,000 replicates,
seed 20260821), and all prespecified contrasts are paired within isolate. Naive contig-level
intervals were never used.

**A3. "Your pooled result could be driven by one large or unusual isolate."**
Tested (PF03). Leave-one-isolate-out: **maximum absolute influence on pooled PPV is 0.00356**
(SAMN29503689). Macro-average PPV across isolates is 0.9572 versus micro-pooled 0.9770 — the gap
is real and now reported, and macro still clears the floor.

**A4. "Errors are probably concentrated in a handful of isolates."**
Quantified in PF03a/PF03b, including per-isolate FP/FN and the ten worst contributors of each.
No influential isolate was removed; the primary analysis is unchanged.

**A5. "Six of nineteen rows beat you on F1. Why is your method better?"**
It is not better on F1, and the manuscript says so. The prespecified objective was precision ≥ 0.95
with an answer for every contig. PF12 separates conditional, failure-aware and matched performance
and shows where higher F1 comes from restricted evaluable output.

**A6. "Multiple comparisons across 19 rows and many strata."**
Acknowledged. One prespecified primary endpoint is confirmatory; everything else is secondary or
exploratory and labelled as such. No multiplicity-adjusted claim of superiority is made, and sparse
strata carry an explicit instability flag rather than a smoothed interval.

**A7. "Is your model calibrated, or just well-thresholded?"**
Now measured (PF13): v1.2-General **AUROC 0.9873, AUPRC 0.9646**, with Brier score, ECE, and
calibration intercept/slope reported and the frozen thresholds marked. No new threshold selected.

**A8. "Show me the negative controls."**
PF15. Label permutation collapses PPV from **0.9770 to a maximum of 0.2709** across 200
permutations. Row-order shuffling leaves metrics bit-identical. Zero duplicate contig IDs, zero
excluded-isolate leakage, all rows in the sealed cohort.

---

## Pass B — plasmid-bioinformatics reviewer

**B1. "Your truth is minimap2 against one reference. Change the thresholds and your labels change."**
The fair version of this concern, now tested (PF08). A four-point grid was **frozen before any
mapping ran** — stricter (id 0.97/cov 0.85), permissive (0.90/0.70), and margins 0.05 and 0.15 —
and all four are reported regardless of outcome. Results in `PF08_TRUTH_SENSITIVITY_RESULTS.tsv`.
No favourable threshold was selected and the primary definition is unchanged.

**B2. "413 unresolved contigs is convenient. What if they are the hard cases?"**
They are, and that is the point of reporting them. PF09 characterises all 413 by class, taxon,
length, depth, ARG status, predicted class, routing pathway and tool agreement, and computes
adversarial bounds. **In the worst case — every unresolved contig charged against the model —
PPV falls to 0.9055, below the floor.** That is a genuine bound on the claim and is now stated.

**B3. "Contig origin is not plasmid reconstruction."**
Agreed, and stated throughout as an explicit non-claim. Tools that do attempt binning or
reconstruction (MOB-recon, gplas2, HyAsP) are consumed for contig-level evidence only, and their
reconstruction performance is not evaluated or claimed.

**B4. "Short contigs are where everyone fails. Are you hiding behind long ones?"**
PF06 uses non-outcome-optimised bins (1–<2, 2–<5, 5–<10, 10–<50, ≥50 kb) with full metrics and
uncertainty, plus length as a continuous exploratory covariate. Nothing is hidden; the 1 kb
eligibility floor is the frozen P1.12 convention, not a choice made here.

**B5. "Your references vary in quality. Some are GenBank, some may have unresolved replicons."**
PF10 characterises every reference by source, replicon counts, completeness and mapping-ambiguity
rate, and defines a **prediction-blind** complete-resolution isolate subset (59 of 150 isolates, 1,753
contigs) on which the principal metrics are recomputed as sensitivity.

**B6. "Enterococcus is a hard case and you may be leaning on Klebsiella."**
Tested (PF02). Leave-one-taxon-out: excluding *K. pneumoniae* — the strongest taxon — pooled PPV
is **0.9649**, still above the floor, and recall 0.5981, still above 0.50. **The conclusion does
not depend on any single taxon.** This is not unseen-species validation and is not described as such.

**B7. "Are any of your evaluation isolates near-clonal with development data?"**
PF11, using assemblies and existing ANI only, no re-download. **Zero exact identifier overlap**
with any consumed set; **maximum ANI to any consumed genome 99.48**, below the 99.5 exclusion
threshold; **zero within-cohort pairs at ANI ≥ 99.5**. BioProject clustering is reported.

**B8. "plASgraph2 beat you on ARG precision."**
It did — 0.9563 versus 0.9409 — and the manuscript states it, together with the fact that
plASgraph2 answered for 92.1% of ARG contigs while v1.2-General answered for all of them. Ten of
nineteen rows are Pareto-optimal, so Pareto membership alone is not claimed as superiority.

---

## Pass C — sceptical *npj AMR* reviewer

**C1. "Is this a methods paper dressed as an AMR paper?"**
The evaluated endpoint is the genomic context of resistance determinants, the ARG-bearing subset is
analysed in its own right by taxon, ARG family and antimicrobial class, and the operational
recommendation is a surveillance recommendation. The AMR content is the point, not the framing.

**C2. "You claim 'first'. Prove it."**
A documented audit of 15 studies against seven explicit criteria, with databases and search dates
recorded. **Multi-species benchmarking of this tool class is not novel** — a 2025 *Briefings in
Bioinformatics* benchmark exists — and the claim was rescoped accordingly. What no audited study
combines is prospective sealing, truth-blind evaluation and independent deterministic verification.
The wording is "to our knowledge", and Scopus/Web of Science are recorded as not searched.

**C3. "Recall of 0.66 means you miss a third of plasmid contigs. Is that useful?"**
Honest answer: it is a deliberate trade. The design fixed precision as the objective because a
confidently wrong context assignment is costlier than an abstention in triage. Errors are
overwhelmingly false negatives (755 FN vs 35 FP). Users needing sensitivity should prefer a
high-recall tool and accept the precision cost — the frontier is published so that choice is
informed.

**C4. "Your own router is a failure. Why should I trust the rest?"**
Because it is reported as a failure rather than removed. It was frozen before truth, evaluated, and
found to trade 49.62 points of ARG recall for 0.85 points of precision. It was **not** redesigned
after seeing the result. That is the evidence standard working, and it is the reason to trust the
result that did succeed.

**C5. "Would this change what a surveillance lab does on Monday?"**
Where a precision floor governs, yes: it is the only evaluated approach meeting 0.95 with an answer
for every contig. Where sensitivity governs, no, and the paper says so. The deployment boundaries —
three of six taxa below the floor, the ARG subset below the floor, prevalence dependence — are
stated so the answer can be worked out per setting rather than assumed.

**C6. "Seven implementation defects. How do I know the results are right?"**
Because each was caught by a fail-closed gate or an explicit counter, not by inspection, and each
is documented with its failed run. The results are independently re-derived by a verifier sharing
no code with the evaluation (385 values, zero disagreements), the frozen table hash is re-verified
at every stage, and label permutation destroys performance as it must. One defect is an
evidence-preservation loss (TC7) and is disclosed as unrecoverable rather than described as
preserved.

---

## Concerns that remain open

| # | Concern | Status |
|---|---|---|
| O1 | Performance in a genuinely low-prevalence deployment | **bounded, not resolved.** Requires a prospective low-prevalence cohort |
| O2 | Generalisation to taxa outside the six evaluated | **not claimed.** Requires new data |
| O3 | Unseen-species generalisation | **not tested and not claimable** — every taxon here was present in development or selection |
| O4 | Truth from a single reference per isolate | mitigated by PF08/PF10; fully resolving it needs orthogonal long-read truth |
| O5 | Independent replication on another laboratory's specimens | protocol prepared, not executed |
| O6 | Per-tool peak RAM | **not measured** — receipts record container limits, not observed RSS. Not invented |

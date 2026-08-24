# P1.11 differentiation analyses

`EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT`. Post-hoc. Nothing frozen is touched; each script
re-derives the confirmatory contingency table and refuses to run unless it reproduces
`n=7244, TP=942, FP=33, TN=6002, FN=267` exactly.

These four exist because the prior benchmark — Teixeira et al., Brief Bioinform 2025;26(6):bbaf589
— already covers most descriptive strata (ARG-bearing contigs in its ST17, base-pair and
fully-classified plasmid recovery in ST6, contig length and plasmid size in ST13, assembly
contiguity in ST12/ST20, incompatibility group and mobility type in ST8–ST11). Adding another
descriptive stratum would duplicate it. These four ask questions that benchmark cannot ask of
itself.

## A. Copy number is a determinant its covariate set omits

ST13 models detection against SR contig length, presence of ARGs, transposase count, identity of
the best PLSDB hit, and plasmid size. **Read depth / copy number is not among them.** Adding a
per-isolate copy-number proxy (contig depth ÷ median depth of that isolate's own ≥10 kb chromosomal
contigs) to a model already containing contig length, ARG status and replicon size improves fit
significantly for four of five methods tested.

Transposase count and PLSDB hit identity were not available here, so this is an addition to their
covariate set, not a replacement for their model.

## B. Rank order transfers across cohorts; absolute numbers do not

The 79-isolate P1.11 cohort is disjoint from their 250 by identifier (0 shared BioSamples) and by
sequence (max ANI 99.48 %, below the frozen 99.5 % threshold). Running the same twelve tools on it
allows a question no single benchmark can ask of itself: how far does a published number transfer?

- Spearman rank correlation of per-tool F1: **0.958**
- Mean |ΔF1| **4.2 pp**, max **13.1 pp** (PLASMe)
- Mean ΔF1 **+0.33 pp** — the movement is scatter, not systematic bias in F1
- Precision rose on E. coli for **10 of 12** tools (mean +3.7 pp), consistent with the prior
  benchmark's own finding that database representation drives detection. The two exceptions,
  PLASMe (−14.5 pp) and geNomad (−7.6 pp), were already the least precise.

P1.11 values are computed the prior benchmark's way — per unit, median, bootstrap CI — so the
comparison is like-for-like. Pooled contig-level values are reported alongside.

**Confound, stated plainly:** their Enterobacterales column spans several genera; P1.11 is
*E. coli* only. The shift therefore conflates cohort change with species narrowing, and cannot be
attributed to one alone.

## C. Operational reliability

Every published benchmark of these tools reports accuracy conditional on the tool having run. None
reports how often it does not. Across 1,027 executions: 55 not-OK. Two distinct modes matter and
are separated here — **execution failure** (the tool did not produce output) and **abstention**
(the tool ran and declined to call), because they have different consequences for a pipeline.

MOB-recon's 49 not-OK receipts require the annotation carried in the JSON: a truth-blind provenance
audit established that 47 of those executions completed with valid output behind a stale FAILED
receipt. That is a silent-corruption mode which would have discarded 11,241 contigs of evidence had
the receipt been trusted.

PlasmidCall's encoding gives an absent or failed tool an exactly zero contribution to the logit —
measured, not asserted (`max_abs_contribution_of_an_absent_unseen_tool = 0.0` in the training
receipt). No comparator has an equivalent property, because none consumes a panel.

## D. The prospective claim

Published claims here take the form "on dataset D, tool T achieved M", with D, M and the operating
point chosen after the results were seen. Such a claim cannot fail. This one was built so it could:
operating points declared, predictions frozen and hashed at 2026-08-22T04:55:11Z, truth acquired at
05:21:42Z, and a declared pass/fail gate with no route to change the threshold afterwards.

This is not a criticism of the prior benchmark, which is a different kind of study. It is the
observation that no published plasmid-detection number has been subject to a preregistered
pass/fail test.

## Files

| File | Contents |
|---|---|
| `P1.11_DIFFERENTIATION.json` | all four analyses, machine-readable |
| `P1.11_cross_cohort_transferability.tsv` | per-tool prior vs P1.11, both aggregations, deltas |

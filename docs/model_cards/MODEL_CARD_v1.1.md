# Model card — PlasmidCall v1.1

**Status** frozen · **Thresholds** 0.9524 (standard) and 0.9605 (high-confidence), neither
re-derived · **Role** comparator

> **Correction notice.** Values in this document follow
> [`PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

## Intended use

The same contig-origin classification task as v1.2-General, at a deliberately more conservative
operating point. Appropriate where a very low false-positive rate matters more than recall and the
user accepts recovering roughly one plasmid contig in four.

## Not intended for

Everything listed as out of scope for v1.2-General, and additionally any use where recall matters:
its recall in this validation is below the 0.50 floor the study prespecified.

## Architecture and training data

Histogram-based gradient boosting over a 250-genome development set spanning seven genera.

## Verified performance (9,371 truth-resolved contigs)

| Operating point | Precision | 95% CI | Recall | 95% CI | Coverage |
|---|---|---|---|---|---|
| 0.9524 (standard) | 0.9706 | 0.9493–0.9883 | 0.2798 | 0.2064–0.3546 | 1.0000 |
| 0.9605 (high-confidence) | 0.9707 | 0.9495–0.9883 | 0.2512 | 0.1828–0.3222 | 1.0000 |

Both operating points exceed the 0.95 precision floor at complete coverage. **Neither meets the
prespecified recall floor of 0.50**, which is why v1.1 is a comparator and not the index model.

Discrimination and calibration: AUROC 0.9777, AUPRC 0.9337, Brier 0.0496, 10-bin ECE 0.0383. Calibration
is materially worse than v1.2-General's.

## Failure behaviour

Errors are almost entirely false negatives: 1,614 FN against 19 FP at 0.9524, and 1,678 against 17 at
0.9605.

## Provenance

Frozen before this validation. No threshold was re-derived here.

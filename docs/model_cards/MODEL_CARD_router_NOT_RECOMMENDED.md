# Model card — PlasmidCall router

## NOT RECOMMENDED for resistance-gene plasmid surveillance

**Status** frozen · **Disposition** validated negative result · **Not redesigned after truth**

> **Correction notice.** Values in this document follow
> [`PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

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
| Pooled (9,371 contigs) | 0.9812 | 0.6042 | 1.0000 |
| **Resistance-gene-bearing (635 contigs)** | **0.9494** | **0.2820** | 1.0000 |
| v1.2-General on the same resistance-gene subset, for comparison | 0.9409 | 0.7782 | 1.0000 |

On the resistance-gene-bearing subset the router recovers **49.6 percentage points less** than
v1.2-General — roughly one third as much plasmid-borne resistance-gene signal — in exchange for
**0.85 points** of precision. Neither reaches the 0.95 precision floor on that subset.

## Recommendation

**Do not use the router for resistance-gene plasmid surveillance.** Where a precision floor governs
and coverage must be complete, use v1.2-General and apply the boundaries in its model card. The
router remains in the inventory as a reported negative result, not as a recommended configuration.

# PlasmidCall — intended-use statement

**Dated** 2026-08-24 · Binds the frozen result `P1.13-RESULTS-FREEZE-001`.

> **Correction notice.** Values in this document follow
> [`PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

## Intended use

PlasmidCall v1.2-General is intended to classify whether an individual contig of at least 1 kb,
from an Illumina short-read bacterial draft assembly, is of **plasmid origin**, in order to
establish the genomic context of antimicrobial resistance determinants for **surveillance triage**.

It is intended for use where:

1. the deployment objective is a **precision floor** rather than maximal sensitivity or F1;
2. an answer is required for **every** contig, so a method that declines to answer is unacceptable;
3. the organism is one of the six taxa evaluated — *Klebsiella pneumoniae*, *Enterobacter* spp.,
   *Citrobacter* spp., *Serratia* spp., *Enterococcus faecium*, *Enterococcus faecalis*;
4. plasmid prevalence among eligible contigs is above roughly **12%**;
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
| Low-prevalence settings below ~12% plasmid content | the precision claim does not carry over |
| Resistance-gene-bearing contigs where a 0.95 precision floor is mandatory | precision is 0.9409 on that subset, below the floor, and **no method reached 0.95 with complete coverage** there |
| Contigs below 1 kb, long-read or hybrid assemblies | outside the evaluated eligibility rule |
| Deployments where sensitivity governs | recall is 0.6631; a high-recall tool is the better choice |

## Required reporting when used

A user reporting PlasmidCall output should state the taxon, the plasmid prevalence of the material,
the panel completeness achieved, and whether the contigs in question carry resistance determinants,
because each of these changes the applicable precision estimate.

## Status

Validated once, prospectively, on public isolates by the developing group. **Independent
replication on another laboratory's specimens has not been performed.** Until it has, deployment
should be treated as evaluation rather than as established practice.

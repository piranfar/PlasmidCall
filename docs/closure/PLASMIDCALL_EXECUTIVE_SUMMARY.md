# PlasmidCall — executive summary

**Dated** 2026-08-24 · **Primary freeze** `P1.13-RESULTS-FREEZE-001` (immutable)
**Post-freeze package** `P1.13-POSTFREEZE-REVIEWER-ANALYSES-001` (adds only)

> **Correction notice.** This document has been updated to the corrected values recorded in
> [`docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md). Frozen artefacts are never edited; the
> addendum is the correction of record.

## The question

Genomic surveillance readily detects antimicrobial resistance genes but rarely resolves whether
they sit on a plasmid or in the chromosome. In short-read draft assemblies that question is
genuinely hard, existing classifiers disagree, and some fail outright on particular genomes.

## What was done

A prospectively sealed, truth-blind external validation. Design, cohort, eligibility rules,
thresholds, analysis plan and stopping rules were hash-sealed before any read was retrieved.
Predictions were frozen and self-re-executed twice byte-for-byte by the same operator,
with no second participant, before any truth artefact was
permitted onto the analysis system. 150 isolates across six taxa; 19,320 assembled contigs, 9,784 eligible
at ≥ 1 kb, 9,371 truth-resolved. Nineteen predictor rows were evaluated on identical evidence: 12
third-party tools, four PlasmidCall model and router rows, three predeclared baselines.

## What was found

**The cohort's resistance determinants were placed against each isolate's own finished
genome, and their distribution is sharply structured.** Of 635 resistance-gene-bearing contigs, **266
(41.9%) are plasmid-derived**. Across taxa the fraction runs from 57.4% in *Citrobacter* spp. to
7.1% in *Serratia* spp.; across antimicrobial classes from 93.5% for sulfonamide resistance to
zero of 48 contigs carrying fosfomycin resistance; and across gene families the distribution is
bimodal, with 15 of 40 assessable families at or above 90% and 14 at or below 10%. *vanA*-type
determinants are plasmid-derived on all 98 contigs carrying them while *vanB*- and *vanD*-type are
chromosomal on all 19. This is a **post-freeze descriptive analysis of the frozen truth labels**.
It is not a prevalence estimate — the cohort is de-clustered by design — and a plasmid-derived
contig is a statement about location, not mobility. The *van* separation is reported as an internal
check on the labelling, not as new genetics: the mapping has no access to gene identity or function
and recovers the distinction blind.

**The prespecified primary endpoint was met.** v1.2-General reached precision **0.9770**
(95% CI 0.9642–0.9872) at recall **0.6631** (0.6205–0.7052), with coverage **1.0000** and zero abstentions. The
requirement was precision ≥ 0.95 and recall > 0.50; both were met and the **lower bound of the
interval cleared the floor**.

**No third-party tool or predeclared baseline reached precision 0.95 at any observed coverage.**
The highest third-party precision was Platon at 0.9363. Four rows met the floor at complete coverage and
all four were PlasmidCall's, spanning two model classes and three thresholds.

**PlasmidCall is not the best method on every metric, and is not presented as one.** Six rows
achieved a higher pooled F1. Requiring every row to answer restricted the common denominator to
4,233 of 9,371 truth-resolved contigs (45.2%), which is itself a measure of how often the existing panel
declines to answer.

**The boundaries are measured.** Precision fell below the floor in three of six taxa and on the
635 resistance-gene-bearing contigs (0.9409), where no method of any kind reached 0.95 with complete
coverage. Precision is prevalence-dependent and crosses the floor at 12.3% plasmid prevalence.
Charging all 413 unresolved contigs adversarially gives 0.9055.

**The frozen router is reported as a validated negative result.** It traded 49.6 percentage points
of resistance-gene recall for 0.85 points of precision and is not recommended for that use. It was
not redesigned after truth was observed.

## How far it can be trusted

419 values and checks were recomputed from the frozen joined table by code sharing no implementation
with the analysis, with **zero disagreements**. Label permutation collapses precision to a maximum
of 0.2709. There is zero identifier overlap with any consumed development set and the maximum ANI to
any consumed genome is 99.48, below the 99.5 exclusion threshold. Seven implementation and
evidence-preservation defects were found during execution, each by a fail-closed gate or an
explicit counter; all are documented individually, including one unrecoverable
evidence-preservation loss which is disclosed as a loss.

## Scientific classification

**Primary validation success with prespecified applicability limitations.**

## Where the evidence lives

The complete evidence tree as it stood at the prediction freeze — 87,962 files, 14.4 GiB compressed —
has been transferred off the execution host and re-hashed there: the whole-archive digest matches
the value recorded on the host, its internal manifest covers every one of its other members, and
the frozen prediction table extracted from inside it is byte-identical to the digest bound in the
results freeze, with 19,320 data rows exactly matching the frozen contig count. The two tier archives
and the 604-row read manifest verify likewise. Parsed tool calls reconcile exactly:
1,800 files = 12 classifiers x 150 isolates, 231,840 calls = 12 x 19,320 contigs.

**Two artefacts remain only on the execution host.** The archive was built before truth acquisition
was authorised, so it contains no post-truth output. `P113_TRUTH_JOINED.tsv` — the scored table
every reported metric is computed from — and `P113_ERROR_CATALOGUE.tsv` were created afterwards and
were never added to it. Both must be copied off before the host is terminated. Their digests are
recorded in the frozen results record, so their loss would be detectable but not repairable.

## What is still needed

Independent replication on another laboratory's specimens, a prospective low-prevalence cohort, a
genuinely held-out taxon, and orthogonal long-read truth. None of these can be supplied by
re-analysing this cohort.

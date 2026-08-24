# PlasmidCall — limitations and non-claims

**Dated** 2026-08-24 · **Status** validation complete, primary result frozen and independently verified
**Binds** `P1.13-RESULTS-FREEZE-001` and the post-freeze package
`P1.13-POSTFREEZE-REVIEWER-ANALYSES-001`

> **Correction notice.** Values follow
> [`../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

This document is binding. Where it and any other document disagree about what is claimed, this
document governs.

---

## 1. Non-claims

These are things PlasmidCall does **not** do. None of them is a limitation to be lifted by more
data; they are outside what a contig-origin classifier can establish.

| Non-claim | Statement |
|---|---|
| Plasmid reconstruction | No plasmid is reconstructed, closed, binned or typed. The unit of prediction is a contig. Tools in the panel that do attempt reconstruction are consumed for contig-level evidence only, and their reconstruction performance is neither evaluated nor claimed. |
| Mobility | Plasmid origin is not evidence of conjugation, mobilization, transposition or horizontal transfer. No mobility assay was performed. |
| Transmission | Nothing here supports inference about outbreak relatedness, epidemiological linkage or spread. |
| Population prevalence | The cohort is deliberately de-clustered at ANI < 99.5, so no proportion reported estimates a population frequency. |
| Clinical utility | No clinical outcome was measured. No clinical validation was performed and none is claimed. |
| Universality | Nothing is claimed beyond the six taxa evaluated. |
| Unseen species | No taxon evaluated was absent from development or selection. Leave-one-taxon-out removes taxa from **evaluation only**; it is not unseen-species validation. |
| Best-on-every-metric | 6 evaluated rows achieved a higher pooled F1 than the index model. PlasmidCall is not the best method by F1 and is not presented as one. |
| Highest ARG precision | On the resistance-gene-bearing subset plASgraph2 achieved higher precision (0.9563, coverage 0.9213) than v1.2-General (0.9409, complete coverage). |
| First multi-species benchmark | Multi-species benchmarking of this tool class is **not** novel; a 2025 benchmark of 12 detection and four reconstruction tools already exists and is cited. |

## 2. Measured boundaries of the validated claim

| Boundary | Measurement |
|---|---|
| **Taxa below the precision floor** | **three of six**: *Citrobacter spp.* 0.9462, *Enterobacter spp.* 0.9358, *Enterococcus faecalis* 0.9130 |
| **Recall varies more than 1.8-fold across taxa** | 0.4468 (*Enterococcus faecalis*) to 0.8136 (*Klebsiella pneumoniae*) |
| **Resistance-gene-bearing subset** | precision 0.9409 at complete coverage — below the floor. **No method of any kind** reached precision 0.95 with complete coverage on that subset |
| **Prevalence dependence** | standardised precision 0.8767 at 5% plasmid prevalence; the 0.95 floor is crossed at **12.3%**. Observed cohort 23.9% |
| **Adversarial unresolved-truth bound** | charging all 413 unresolved contigs against the model gives precision 0.9055, below the floor |
| **Macro versus micro** | isolate-macro precision 0.9572 against micro-pooled 0.9770 |
| **Recall** | 0.6631 pooled; 755 false negatives against 35 false positives |
| **Complete-resolution isolate subset** | precision 0.9082, attributable to that subset's plasmid-poor and taxonomically skewed composition (prevalence 0.0747) rather than to truth quality |

## 3. Scope of the evidence

* Illumina paired-end short reads; Unicycler/SPAdes assemblies. No long-read or hybrid input.
* Contigs of at least 1 kb: 9,784 of 19,320 assembled contigs are eligible.
* 9,371 truth-resolved contigs scored; 413 unresolved contigs excluded and never coerced.
* One closed reference genome per isolate. Four alternative truth definitions frozen before
  re-mapping changed no contig's label, but resolving the single-reference dependence fully would
  require orthogonal long-read truth.
* v1.2-General's validated training claim remains *E. coli*-specific. This study tests transfer.
* Performance is conditional on availability of the twelve-tool panel.
* Tool failures are deterministic and genome-correlated, not missing at random: 72 of 1,950 units.
* Depth is right-truncated by the 100× normalisation. Depth is a measured covariate, not a
  demonstrated confounder.

## 4. Not measured

| Quantity | Why it is absent |
|---|---|
| Per-tool peak resident memory | execution receipts record the container memory **limit**, not observed usage. No value is estimated or reported |
| Per-database sizes | databases are bundled inside pinned images and per-database sizes were never recorded separately |
| Empirical low-prevalence performance | bounded analytically; requires a prospective low-prevalence cohort |
| Unseen-species generalisation | requires a genuinely held-out taxon |
| Orthogonal truth | requires new long-read sequencing |

## 5. Evidence-preservation gap

The two failed truth-acquisition runs' server-side logs were overwritten by a truncating
redirection and **no longer exist**. Their digests, byte sizes and modification timestamps were
never computed and cannot be computed now. **These logs are not preserved, not recovered and not
reconstructed**, and no hash, size or timestamp for them is asserted anywhere. The failure text
quoted in the correction record comes from the contemporaneous session execution record and is
identified as such.

## 6. What would change these boundaries

Independent replication on another laboratory's specimens; a prospective low-prevalence cohort; a
taxon genuinely absent from development; orthogonal long-read truth. None of these can be supplied
by further analysis of this cohort, and no further computation on the existing data would move any
boundary above.

## 7. Standing caution

Engineering rigour is not performance. The verification chain establishes that the reported numbers
are what the pipeline produced from the frozen inputs. It does not establish that they are good
enough for any particular deployment; that judgement belongs to the deploying laboratory and
depends on the taxon, the prevalence and the resistance-gene context stated above.

## Non-claims attaching to the genomic-context analysis

Added 2026-08-24 with the genomic-context result. These are stated so the result cannot be read
past its evidence.

* **Not a prevalence estimate.** The cohort was de-clustered by farthest-point sampling with an ANI
  exclusion threshold. Its composition was chosen to spread genomic diversity, not to represent any
  population, so no proportion reported here estimates a prevalence in any setting.
* **Not a mobility claim.** A plasmid-derived contig is a statement about which replicon a sequence
  aligns to. No conjugation, transfer, mobilization or host-range experiment was performed, none is
  inferred, and no determinant is described as transferable on this evidence.
* **Contigs, not gene copies.** The unit throughout is the contig carrying at least one determinant
  of a group. A contig carrying determinants of several classes contributes to each, so class
  counts do not sum to the pooled total and no count should be read as a gene-copy number.
* **Not new genetics.** The separation of *vanA*-type from *vanB*- and *vanD*-type determinants,
  and of acquired β-lactamases from chromosomal cephalosporinases, has been established for
  decades. It is reported here as an internal check that the truth labelling recovers known
  structure without access to gene identity or function — not as a discovery.
* **Not prespecified.** The analysis was defined after the results freeze, is labelled post-freeze
  throughout, and is not part of the primary or secondary endpoint set. Its two stratum thresholds
  (20 contigs for a class, 10 for a family) were fixed before the strata were inspected and are
  recorded in the analysis output.
* **Not a taxon-level biological explanation.** Part of the taxonomic gradient is compositional:
  the genera at the low end contribute determinants that are intrinsic chromosomal features of
  those organisms. The gradient is not evidence that plasmids are differently available to those
  genera.

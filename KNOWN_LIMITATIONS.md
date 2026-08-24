# Known limitations (summary)

The authoritative and binding version is
[`docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md`](docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md).
This page is a short index. Every figure below is read from the frozen result set.

## Measured boundaries

* **Precision falls below the 0.95 floor in three of six taxa**: *Citrobacter spp.* 0.9462, *Enterobacter spp.* 0.9358, *Enterococcus faecalis* 0.9130. Cross-taxon generality is not
  supported and is not claimed.
* **The resistance-gene-bearing subset does not reach the floor.** v1.2-General precision 0.9409 at
  complete coverage; **no method of any kind** reached precision 0.95 with complete coverage on
  that subset.
* **Precision is prevalence-dependent by construction.** Standardised to 5% plasmid prevalence it
  is 0.8767; the 0.95 floor is crossed at **12.3% prevalence**. The observed cohort is 23.9%
  plasmid. In a low-prevalence deployment the claim does not carry over.
* **The adversarial unresolved-truth bound does not clear the floor.** Charging all 413 unresolved
  contigs against the model gives precision 0.9055.
* **Macro-average is below micro-pooled**: 0.9572 versus 0.9770.
* **Recall is a deliberate trade.** 0.6631 pooled; errors are overwhelmingly missed plasmid calls
  (755 false negatives against 35 false positives).

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
* **Contigs ≥ 1 kb only.** 9,784 of 19,320 assembled contigs are eligible; the rest are out of scope.
* **v1.2-General's validated training claim remains *E. coli*-specific.** This study tests transfer
  and does not retroactively broaden that claim.

## Dependencies and unmeasured quantities

* **Panel-dependent.** Absent tools receive exactly zero weight, measured rather than assumed, but
  performance is still conditional on panel availability.
* **Tool failures are deterministic and genome-correlated**, not missing at random (72 of 1,950 units).
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

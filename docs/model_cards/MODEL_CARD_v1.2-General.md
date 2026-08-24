# Model card — PlasmidCall v1.2-General

**Status** frozen · **Threshold** 0.9285 (frozen before this validation; never re-derived)
**Role** index model · **Validation** prospectively sealed, truth-blind, 150 isolates, six taxa

> **Correction notice.** Values in this document follow
> [`PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

## Intended use

Classify whether a contig of at least 1 kb from a short-read bacterial draft assembly is of
**plasmid origin**, for surveillance triage under a declared precision requirement, in the six taxa
evaluated, at plasmid prevalence above roughly 12%.

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

## Verified performance (150 isolates, 9,371 truth-resolved contigs)

| Metric | Value | 95% CI (isolate-clustered, 4,000 replicates) |
|---|---|---|
| **Precision (PPV)** | **0.9770** | 0.9642–0.9872 |
| Recall | 0.6631 | 0.6205–0.7052 |
| Specificity | 0.9951 | — |
| NPV | 0.9038 | — |
| F1 | 0.7900 | — |
| Balanced accuracy | 0.8291 | — |
| MCC | 0.7614 | — |
| **Coverage** | **1.0000** | zero abstentions |
| AUROC · AUPRC | 0.9873 · 0.9646 | — |
| Brier · 10-bin ECE | 0.0256 · 0.0068 | — |

Met the prespecified endpoint (precision ≥ 0.95 **and** recall > 0.50) with the interval lower
bound above the floor. 6 evaluated rows achieved a higher pooled F1; **no third-party tool or
predeclared baseline reached precision 0.95 at any observed coverage**.

## Applicability boundaries (measured, not assumed)

* Precision ≥ 0.9130 in every taxon but **below 0.95 in three of six**: *Citrobacter spp.* 0.9462, *Enterobacter spp.* 0.9358, *Enterococcus faecalis* 0.9130. Recall ranges
  0.4468–0.8136.
* **Resistance-gene-bearing subset (n = 635): precision 0.9409** — below the floor — at recall 0.7782
  and complete coverage. plASgraph2 achieved higher precision (0.9563) at coverage 0.9213.
* **Prevalence-dependent**: standardised precision 0.8767 at 5% plasmid prevalence, crossing the
  0.95 floor at 12.3%. Observed cohort prevalence 23.9%.
* Macro-average across isolates 0.9572 versus micro-pooled 0.9770.
* Depth is right-truncated by the 100× normalisation; depth is a measured covariate, not a
  demonstrated confounder.
* Performance is conditional on panel availability.

## Failure behaviour

Errors are overwhelmingly false negatives (755 FN against 35 FP): precision-protective by design.
Absent or failed tools reduce the evidence available but never inject a phantom signal. The model
does not abstain: it returned a call for every eligible contig in the validation cohort.

## Robustness

Both floors hold under removal of any single taxon from evaluation (precision 0.9649–0.9839) and the
maximum influence of any single isolate on pooled precision is 0.00356. Four alternative truth
definitions frozen before re-mapping changed no contig's label. Label permutation collapses
precision to a maximum of 0.2709.

## Provenance

Estimator digest bound in the prediction-freeze receipt. Environment: Python 3.14.6,
scikit-learn 1.9.0, numpy 2.5.0, pandas 3.0.3.

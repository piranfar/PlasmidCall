# PlasmidCall — signed correction addendum

**Addendum ID** `P1.13-CORRECTION-ADDENDUM-001`
**Dated** 2026-08-24
**Binds** primary freeze `P1.13-RESULTS-FREEZE-001` · post-freeze package
`P1.13-POSTFREEZE-REVIEWER-ANALYSES-001`

---

## Standing rule

**Frozen artefacts are never edited.** Where a frozen record or a derived summary carries a wrong
value, the frozen file retains its original content and this addendum is the correction of record.
Every reader-facing document — manuscript, Supplementary Information, model cards, closure reports,
release material — follows this addendum. Preserved historical records (the frozen JSON receipts,
the superseded drafts under `docs/superseded/`, and the original post-freeze artefacts) retain
their original wording deliberately, so that the correction is auditable rather than invisible.

None of the corrections below changes a prediction, a truth label, a threshold, a model, the
router, cohort membership, an eligibility rule or the primary endpoint. The primary endpoint
remains met, with the confidence-interval lower bound clearing the prespecified floor.

---

## E1 — three taxa fall below the precision floor, not two

| | |
|---|---|
| **Where the error is** | `RESULTS_FROZEN.json` → `classification_basis.taxa_below_PPV_floor`, and every prose summary derived from that field |
| **Wrong value** | 2 |
| **Correct value** | **3** |
| **The three taxa** | *Citrobacter* spp. 0.9462 · *Enterobacter* spp. 0.9358 · *Enterococcus faecalis* 0.9130 |
| **Basis** | the stratified tables were always correct. Recomputation from the frozen joined table by the independent verifier returns 3, and the check `taxa below 0.95 PPV floor` in `PF_VERIFICATION_RECEIPT.json` records the recomputed value 3 against the published 3 |
| **Frozen file** | **not edited** |
| **Affects the primary endpoint** | no |
| **Applied in** | manuscript, Supplementary Information, model cards, executive summary, technical closure report, cover letter, limitations statement, claim-to-evidence matrix |

## E2 — Matthews correlation coefficient 0.7614, not 0.7674

| | |
|---|---|
| **Where the error is** | an internal evaluation report; the value quoted in early manuscript drafts |
| **Wrong value** | 0.7674 |
| **Correct value** | **0.7614** |
| **Basis** | `P113_PRIMARY_METRICS.tsv` has always stored 0.7614058602604906 for `v1.2-General@0.9285`. Recomputation from the frozen confusion matrix (TP 1,486 · FP 35 · TN 7,095 · FN 755) gives the identical value |
| **Frozen file** | correct as frozen; only the prose was wrong |
| **Affects the primary endpoint** | no |
| **Applied in** | manuscript, technical closure report, evaluation report |

## E3 — the prevalence crossing is 12.3%, not "between roughly 15% and 20%"

| | |
|---|---|
| **Where the error is** | prose in the post-freeze package summary and the internal review matrix |
| **Wrong statement** | the 0.95 floor "is not retained below roughly 15% and 20% prevalence" |
| **Correct statement** | on the frozen prevalence grid the standardised precision clears 0.95 at 15% (0.9597) and fails at 10% (0.9375); the closed-form root of the same standardisation identity, with sensitivity and specificity held at their frozen observed values, places the crossing at **12.3% plasmid prevalence** |
| **Basis** | `PF05_PREVALENCE_SENSITIVITY.tsv`; the closed form is *p\** = 0.95(1 − specificity) / (0.05 × sensitivity + 0.95(1 − specificity)) |
| **Frozen file** | the grid is correct as frozen; only the prose reading of it was wrong |
| **Affects the primary endpoint** | no. It sharpens a stated bound rather than changing an estimate |
| **Applied in** | manuscript, Supplementary Information, limitations statement, post-freeze package summary |

## E4 — an interpretive string in a post-freeze artefact contradicts its own data

| | |
|---|---|
| **Where the error is** | `PF_SUMMARIES.json` → `unresolved_bounds.interpretation` |
| **Wrong statement** | that "the primary endpoint's precision survives the adversarial bound" |
| **Correct statement** | in the adversarial bound, precision falls to **0.9055** and **does not** clear the 0.95 floor |
| **Basis** | the numeric fields of the same artefact are correct and already record `worst_case_all_unresolved_adverse.PPV = 0.9055…` and `PPV_stays_above_0.95_in_worst_case: false`. The independent post-freeze verifier checks both fields and agrees with them. Only the derived prose string is wrong |
| **Frozen file** | **not edited**, because editing it would invalidate the artefact digest recorded in `PF_VERIFICATION_RECEIPT.json` |
| **Affects the primary endpoint** | no. The primary analysis excludes unresolved contigs as prespecified and never coerces them |
| **Applied in** | manuscript, Supplementary Information, post-freeze package summary, limitations statement |

## E5 — "highest-confidence truth subset" renamed to "complete-resolution isolate subset"

| | |
|---|---|
| **Where the term appears** | `PF10b_HIGH_CONFIDENCE_TRUTH_SENSITIVITY.tsv` (`label` column and filename), the post-freeze package summary, the internal review matrix |
| **Old name** | highest-confidence truth subset |
| **New name** | **complete-resolution isolate subset** |
| **Why** | the subset is defined by a prediction-blind property of the isolate — *every* eligible contig resolved to a single replicon class — not by any measure of truth quality. The old name invited the reading that higher-quality truth lowers precision, which the data do not support |
| **What the data show** | precision on the subset is 0.9082 versus 0.9770 on all resolved contigs. The subset carries a mean of 0.85 reference plasmids per isolate against 3.74 in the remainder and 29.7 against 88.3 eligible contigs, giving a plasmid prevalence of 7.5% against 23.9% in the whole cohort. Because precision falls with prevalence by construction, the difference is attributable to cohort composition. The subset also contains one *K. pneumoniae* isolate against 24 in the remainder while over-representing the two weakest taxa |
| **Required interpretation** | **cohort-composition sensitivity, not evidence that higher-confidence truth reduces performance** |
| **Frozen file** | **not edited**; the filename and `label` value are retained so the artefact digest stays valid. The mapping old-name → new-name is recorded here |
| **Affects the primary endpoint** | no |
| **Applied in** | manuscript, Supplementary Information, post-freeze package summary, internal review matrix, limitations statement |

## E6 — the parsed tool-call table holds 231,840 calls, not 231,841

| | |
|---|---|
| **Where the error is** | prose in an internal determinism report and in early manuscript drafts |
| **Wrong value** | 231,841 rows |
| **Correct value** | **231,840** parsed tool calls |
| **Basis** | recounted directly from the downloaded evidence archive, whose whole-archive SHA-256 matches the value recorded on the execution host. The parsed calls are stored as one file per classifier per isolate: **1,800 files = 12 classifiers × 150 isolates**, each carrying exactly one row per contig. 12 × 19,320 = **231,840**, which reconciles exactly with the frozen contig count. The figure 231,841 is the *line* count of a single concatenated table, one header plus 231,840 data rows |
| **Frozen file** | the parsed files are correct as frozen; only the prose count was wrong |
| **Affects the primary endpoint** | no |
| **Why it is an improvement, not just a fix** | 231,840 is derivable from two frozen quantities rather than transcribed, so it cannot drift |
| **Applied in** | manuscript Data availability, Supplementary Information, this addendum |

## E7 — the joined truth table was listed for off-server preservation but never transferred

| | |
|---|---|
| **Where the error is** | `PLASMIDCALL_SHUTDOWN_SAFE_RECEIPT.json` → `offserver_preservation` |
| **What it implies** | the block lists four items. Three carry `"verified": true`. The fourth, `joined_truth_table`, carries a destination path and a SHA-256 but **no verification flag**. Read quickly, the block reads as a preservation record for all four |
| **What is actually true** | the three archives **did** transfer and now verify byte-exact off-server. **`P113_TRUTH_JOINED.tsv` did not transfer**, and `P113_ERROR_CATALOGUE.tsv` is not listed in the block at all. Both exist only on the execution host |
| **Basis** | the downloaded set was re-hashed against the receipt: `P1.13_EVIDENCE_ARCHIVE.tar.zst`, `P113_TIER1_EVIDENCE.tar.zst`, `P113_TIER2_ASSEMBLIES.tar.zst` and `P1.13_READS_MANIFEST.sha256` all match; the joined truth table is absent. A full streaming pass over the 87,962 archive members confirms the archive predates truth acquisition — the only occurrence of the word truth in it is the marker file `PREDICTIONS_FROZEN_AWAITING_TRUTH_AUTHORIZATION` |
| **Frozen file** | the receipt is a signed record and is **not edited**. This entry is the correction of record |
| **Affects the primary endpoint** | no. It affects **reproducibility**, not the result |
| **Why it matters** | `P113_TRUTH_JOINED.tsv` is the scored table from which every reported metric is computed, and the table both independent verifiers re-derived their 419 values from. Without it, a third party can check the derived metric tables but cannot re-derive them from the scored data. The Data availability statement promises it in the archived release |
| **Required action** | copy `P113_TRUTH_JOINED.tsv` and `P113_ERROR_CATALOGUE.tsv` off the execution host **before** terminating it. Their digests are recorded in `RESULTS_FROZEN.json`, so loss would be detectable but not repairable |
| **Applied in** | `EVIDENCE_ARCHIVE_VERIFICATION.json`, `OWNER_DECISIONS.md`, the executive summary |
| **RESOLVED** | **2026-08-24.** Both files, and three further evaluation artefacts that were also absent from the repository, were copied off the execution host and verified byte-exact against both the host digest and — where bound — the results freeze. A full comparison of the host's `evaluation/` and `evaluation_postfreeze/` directories against the repository now shows **43 identical, 5 recovered, 0 differing, 0 missing**. All 19 frozen result artefacts are held off-server. The four files under the repository's 5 MB release ceiling are committed; `P113_TRUTH_JOINED.tsv` (8.7 MB) is preserved in the off-server evidence set and remains Zenodo-destined, exactly as the Data availability statement already describes |
| **Also recovered** | `P113_UNRESOLVED_TRUTH_CHARACTERISATION.tsv` (413 rows, the evaluation-phase characterisation, superseded in content by the enriched post-freeze `PF09a` but retained), `P113_TOOL_OUTPUT_ACCOUNTING.tsv` (per-tool call composition including explicit failure states) and `P113_SENSITIVITY_ANALYSIS.tsv` (the prespecified evaluation-phase sensitivity scenarios). The first two are now Supplementary Data 10 and 11. None was previously in the repository and none is bound in the results freeze, so their absence had not been detectable by digest |

---

## Wording corrections applied across all reader-facing documents

These are not numeric errors but claim-scope corrections required before submission.

| # | Superseded wording | Required wording | Reason |
|---|---|---|---|
| W1 | "the first multi-species benchmark" | "**to our knowledge**, the first evaluation in this tool class to combine prospective prediction sealing, truth-blind multi-taxon external validation and independent deterministic verification" | multi-species benchmarking of this tool class is **not** novel; a 2025 benchmark of 12 detection and 4 reconstruction tools already exists and is cited. Scopus and Web of Science were not searched, so the claim is hedged |
| W2 | describing v1.2-General as the highest-precision method for resistance-gene-bearing contigs | plASgraph2 achieved higher precision on that subset (**0.9563** at coverage 0.9213) than v1.2-General (0.9409 at complete coverage), with closely comparable recall (0.7675 vs 0.7782) | the claim was false as written |
| W3 | treating Pareto-frontier membership as superiority | **ten of nineteen** rows are Pareto-optimal on the resistance-gene subset, so membership alone is not evidence of superiority and is not claimed as such | |
| W4 | "zero label flips" without definition | a **label flip** is a contig RESOLVED under both the primary and an alternative truth definition whose binary chromosome/plasmid class differs. Resolution-state transitions between RESOLVED and UNRESOLVED are counted separately and are visible in the changing denominator (9,371 → 9,362 / 9,378 / 9,371 / 9,370) | the phrase is meaningless without the state comparison |
| W5 | "no comparator reached PPV 0.95" stated unscoped | "**no third-party tool or predeclared baseline** reached precision 0.95 at any observed coverage **on the pooled truth-resolved set**". On the resistance-gene subset plASgraph2 **did** exceed 0.95 precision, at incomplete coverage | the unscoped form is false on the ARG subset |
| W6 | reporting only the conditional comparison | conditional, failure-aware and matched-denominator performance are **distinct** and are reported separately for every row. The matched common denominator is **4,233 of 9,371 truth-resolved contigs, 45.2%** | |
| W7 | presenting post-freeze analyses alongside the primary result without labelling | every post-freeze analysis is labelled secondary, sensitivity, exploratory or integrity audit, is introduced under an explicit statement that it is post-freeze, and is **never** presented as a prespecified primary endpoint | |
| W8 | describing the lost acquisition logs as preserved or reconstructed | the two failed-run acquisition logs are **not preserved, not recovered and not reconstructed**. No hash, size or timestamp for either is asserted, and none may be constructed | |

---

## Verification of this addendum

Every corrected value in this document was read from the frozen source table named in its **Basis**
row by the canonical extractor, and is present in `PLASMIDCALL_CANONICAL_NUMBERS.json` with its
source file and field. The manuscript verifier fails closed if any superseded wording in the table
above reappears in a reader-facing document, and if any number in the manuscript does not resolve
to a canonical source.

| Check | Result |
|---|---|
| Superseded wording absent from the manuscript and Supplementary Information | enforced by `scripts/manuscript/verify_manuscript.py` |
| Every manuscript number resolves to a frozen source | enforced, 556 distinct numbers |
| Frozen artefacts unmodified | digests re-verified; `RESULTS_FROZEN.json` and all post-freeze artefacts unchanged |
| Primary endpoint unchanged | PPV 0.9770 (95% CI 0.9642–0.9872), recall 0.6631 (0.6205–0.7052), coverage 1.0000 |

**Signed for the record by the author.** This addendum is versioned with the release and is cited
from the manuscript's Supplementary Information (Supplementary Note 13).

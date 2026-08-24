# PlasmidCall — final technical report

**Version** 2.0 · **Dated** 2026-08-24 (UTC) · **Status** validation complete; primary result frozen, joined, evaluated and independently verified

> **Status update (version 2.0).** This report was written while predictions were frozen and truth
> was not authorised, so its result sections carried explicit `[AWAITING TRUTH AUTHORIZATION]`
> placeholders. Truth has since been authorised, acquired, joined once and evaluated against the
> prespecified endpoint, and the result is frozen. **For all results, read the manuscript
> ([`../manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md`](../manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md)),
> the executive summary and the correction addendum ([`../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md)).**
> The execution and provenance sections of this report remain accurate and are unchanged.
> The placeholders are retained deliberately: they are the record that no result was
> estimated, imputed or inferred before truth existed.

**Freeze** `P1.13-PREDICTION-FREEZE-001`
**Audience** an expert auditor who did not follow the development history

Every quantitative statement below is traceable to a canonical machine-readable artefact listed in
`P113_CANONICAL_ARTEFACT_INVENTORY.tsv`. Where a number would require truth, it is marked
`[AWAITING TRUTH AUTHORIZATION]` and is **not** estimated, imputed or inferred.

---

## 1. Scientific question and intended use

Antimicrobial-resistance surveillance from short-read genomes routinely establishes *that* a
resistance determinant is present, but not *where* it sits. The same gene carried on a plasmid and
on the chromosome implies different things for how it may persist and be shared between lineages.
In draft short-read assemblies the distinction is frequently unresolved: the assembly is
fragmented, plasmid and chromosomal sequence are interleaved across contigs, and no single contig
is self-evidently one or the other.

PlasmidCall addresses one narrowly scoped task:

> given a contig from a short-read draft assembly, and the outputs of a panel of existing
> plasmid/chromosome classifiers, decide whether that **contig** is of plasmid origin — and, where
> the evidence does not support a confident decision, decline to decide.

The intended use is **surveillance triage of ARG-bearing contigs**: flagging which resistance
determinants sit in a plasmid context, with a declared precision requirement and an explicit
notion of when the method does not apply.

## 2. Explicit non-claims

PlasmidCall does **not** claim, and this report must not be read as claiming:

* **whole-plasmid reconstruction.** The unit of prediction is a contig, not a replicon. No plasmid
  is assembled, closed, binned or typed. Contig-origin classification and plasmid reconstruction
  are different tasks with different error modes.
* **horizontal transfer, conjugation, mobilization or transposition.** Plasmid origin is a
  statement about genomic context in one assembly. It is not evidence that a determinant moved,
  can move, or has moved between cells or lineages.
* **epidemiological spread or transmission.** No isolate relatedness, outbreak, or transmission
  inference is made.
* **clinical utility.** No clinical outcome, treatment decision or patient-level inference is
  supported by this work.
* **population prevalence.** The cohort is a deliberately structured, genomically de-clustered
  selection, not a random or representative sample of any population.
* **universality across bacteria.** Evaluation covers six taxa; nothing is claimed beyond them,
  and per-taxon results are reported separately precisely so that failures are visible.

PlasmidCall is scientifically separate from **PortabilityRisk**, a different project on the same
infrastructure. PortabilityRisk may be cited as conceptual background only. No PortabilityRisk
result is a PlasmidCall result.

## 3. Development history and model lineage

| Phase | Role |
|---|---|
| DEV_250 | development set, 250 isolates spanning 7 genera. Source of the v1.1 development bundle. |
| P1.9 / P1.9C4 | cleanroom panel execution; origin of the frozen runner and parser lineage. |
| P1.10 | 39-isolate phase; frozen parser and runner derived here by path substitution. |
| P1.11 | first independent prospective validation, 79 isolates. Prediction freeze `P1.11-PREDICTION-FREEZE-001`. |
| P1.12 | v1.2-General training and freeze (`freeze_v12.py`); truth pipeline; post-truth analyses. |
| **P1.13** | **this study — second, larger, prospective public multigenus external validation, 150 isolates.** |

Two models and one router are frozen:

* **v1.1 ("M2")** — a HistGradientBoosting classifier developed on the DEV_250 bundle (7 genera).
  It has no persisted estimator in its original form; for P1.11 it was refit from the sealed
  development bundle by `v11_scorer_p111.py`, validated against the historical P1.10
  implementation, and persisted so that no downstream phase silently refits it.
* **v1.2-General** — a standardised logistic regression over the categorical calls of 12 panel
  tools, trained in P1.12 on 39 *E. coli* isolates. Its validated claim is *E. coli*-specific by
  construction; P1.11 and P1.13 test how far it transfers.
* **the router** — a two-domain operating strategy that sends ARG-bearing contigs to the
  high-precision v1.1 pathway and all other eligible contigs to v1.2-General.

**Separation boundary:** no P1.13 sequence, metadata or truth was used to train, select, calibrate
or tune any model. No model was modified at any point in P1.13.

## 4. Datasets and separation boundaries

P1.13 eligibility required a Complete Genome reference assembly, usable paired Illumina WGS,
release date satisfying the frozen taxon date rule, and **no prior use in any development,
calibration or validation phase**. Historical exclusion sets loaded: DEV_250, P1.9, P1.10, P1.11
(583 identifiers), checked on BioSample, assembly accession, BioProject, organism and genomic
similarity.

Genomic independence was enforced with skani 0.2.2 at `--min-af 15`, dropping any candidate with
ANI ≥ 99.5 to any consumed genome **and** to any already-selected P1.13 isolate. Selection then
proceeded by farthest-point genomic selection on the frozen distance `100 − ANI`, most recent
permitted release year first, with assembly accession lexical order as the deterministic
tie-breaker. Nothing derived from plasmid count, truth, ARG content, tool output, model score or
expected performance entered selection.

## 5. Tool panel and rationale

Twelve contig-classification tools plus AMRFinderPlus, executed as 13 units per isolate:

`HyAsP · MOB-recon (MOB-suite) · PLASMe · PlaScope · Plasmer · PlasmidEC · PlasmidFinder · Platon ·
RFPlasmid · geNomad · gplas2 · plASgraph2` and `AMRFinderPlus` for ARG annotation.

The panel is deliberately heterogeneous — replicon-based, k-mer/ML-based, graph-based and
homology-based approaches — because the scientific premise is that no single classifier is
adequate alone and that their *disagreements and failures* are themselves informative. gplas2
consumes PlasmidEC output and therefore runs after it.

## 6. v1.1, v1.2-General and router definitions

* **v1.1** consumes the frozen development-derived feature set and returns a continuous score;
  thresholds 0.9524 (standard) and 0.9605 (high-confidence).
* **v1.2-General** consumes the 12 categorical tool calls under an immutable 102-feature encoding
  and returns a continuous score; threshold 0.9285.
* **Direct-block neutrality:** a tool in a state never observed during training has its feature
  block imputed to training means, so it contributes exactly 0.0 to the logit. This was measured,
  not assumed (`max_abs_contribution_of_an_absent_unseen_tool = 0.0`). Scoring the raw encoding
  directly would let an absent tool shift the logit by up to ≈3 units.
* **Router:** ARG-bearing eligible contigs → v1.1 at its thresholds; all other eligible contigs →
  v1.2-General at 0.9285. A contig whose ARG annotation failed or was never attempted is
  **abstained** on: it receives no routed class and is counted separately, never folded into
  either domain.

## 7. Feature definitions and eligibility rules

The seven-term normalized call vocabulary is `chromosome, plasmid, unknown, unclassified, repeat,
FAILED, MISSING`. `FAILED` and `MISSING` are preserved as explicit states and never silently
recoded as a negative call.

**Eligibility:** contigs ≥ 1,000 bp (`MINLEN = 1000`, inherited unchanged from the frozen P1.12
convention, not introduced here). In P1.13: 19,320 contigs total, **9,784 eligible**.

`ARG_bearing_bool` is nullable by design: true/false only when `annotation_state == ok`; for
failed, missing or unparseable annotation it is NA, never false. Absence of an ARG is never
inferred from an annotation failure.

## 8. Frozen thresholds and abstention logic

| Model | Threshold | Frozen in |
|---|---|---|
| v1.2-General | 0.9285 | P1.12 |
| v1.1 standard | 0.9524 | P1.10/P1.11 |
| v1.1 high-confidence | 0.9605 | P1.10/P1.11 |

No threshold was re-derived, tuned or selected at any point in P1.13. Abstention has two distinct
and separately recorded mechanisms: **model abstention** (no finite score available) and **routing
abstention** (annotation state not `ok`). In P1.13 both were zero — see §20.

## 9. P1.13 cohort construction

150 isolates, **25 in each of six taxa**: *Klebsiella pneumoniae*, *Enterobacter* spp.,
*Citrobacter* spp., *Serratia* spp., *Enterococcus faecium*, *Enterococcus faecalis*.

*Enterococcus* is described as **a hard Gram-positive validation domain with historically
underrepresented plasmids and reduced tool performance** — not as fully out-of-distribution, since
*Enterococcus* isolates were present in model development.

Census and filtering: 6,458 NCBI target genomes → 6,449 after historical exclusion → 1,816 with
usable Illumina paired WGS → 1,777 after the 30× coverage floor → 811 in the 2023+ pool with full
file availability. *Serratia* fell 3 short of 25 under the 2023-only date rule; this was recorded
as `decision_required_from_operator` and resolved by an explicit owner amendment (Amendment 001)
rather than unilaterally.

Final cohort v3 sha256 `874b0924deffef948dd50e00ee5c77c91d773354de4a1bb936162e4fec294205`.

## 10. Contamination diagnosis and deterministic replacement

`SAMN26198730` (*E. faecalis*, GCF_040586835.1) was **rejected by the fail-closed assembly gate**:
10,224,257 bp across 2,993 contigs against a declared genome of 2,819,902 bp, at 179× raw depth —
so not a coverage artefact.

A truth-blind taxonomic screen used the **already frozen** method (skani 0.2.2 from the pinned
`p19c2-cleanroom:1.0` image, `--min-af 15`):

| Evidence | Result |
|---|---|
| ANI to its own declared reference | 99.97 % — identity is *correct* |
| Aligned fraction of the reference | 95.75 % — the declared genome is nearly fully present |
| Aligned fraction of the assembly | **26.98 %** — only a quarter of the assembly is that genome |
| Reference-free GC | bimodal: 26.1 % of sequence at GC < 40 (*E. faecalis* ≈ 37.5 %), **73.9 % at median GC 59.6** |

Two methodologically independent lines agree to within one percentage point (26.98 % vs 26.1 %):
roughly three quarters of the assembly is foreign DNA. Of 835 pool references, the 93 that match
are all *E. faecalis* strains matching the same correct quarter; nothing accounts for the foreign
majority.

Only whole-assembly aggregate statistics were computed. **No per-contig replicon assignment, no
chromosome or plasmid label, and no truth artefact was derived, read or stored.**

The isolate and all of its outputs are **retained** as a documented technical exclusion. The
replacement applied the frozen selection rule unchanged, holding the 24 surviving *E. faecalis*
isolates fixed and drawing exactly one isolate. All 9 candidates in the preferred 2024+ pool were
within ANI 99.5 of an already-selected isolate and were skipped, so selection fell through to the
2023 pool — the same fallback behaviour already recorded for *Serratia*. Selected
`SAMN37639065` (GCF_032681005.1), ANI 99.02 to its nearest retained neighbour.

## 11. Raw-read acquisition and MD5 validation

All reads were fetched from ENA and verified against the ENA-declared MD5 for every file.
Final state: **150/150 verified, 0 failed.**

Two files initially failed and exposed a real defect (§ Timeline, DEFECT 1). One was truncated;
the other returned at **exactly the declared byte length with the wrong content** — a size or
record-count check would have passed it. HEAD requests confirmed ENA served the correct lengths,
so this was local transfer corruption, not a data-availability defect, and neither isolate left
the cohort.

## 12. Exact R1/R2 read-ID pairing validation

Count equality between R1 and R2 does not prove pairing: two files can hold identical record
counts while carrying different reads, or the same reads permuted. The count-only guard was
replaced (Amendment 003) with **position-by-position comparison of normalized read identifiers**,
carried as a streaming SHA-256 digest so no large intermediate is required.

Normalization removes only the legitimate mate marker (a trailing `/1` or `/2`, or the Illumina
whitespace mate field); nothing else about the identifier is altered. Checks fail closed on
truncation, a missing `+` line, sequence/quality length mismatch, duplicate identifiers, or any
positional mismatch. 15/15 fixtures pass, including a production-path test proving that seqkit run
separately on R1 and R2 at a fixed seed selects identical record positions — demonstrated, not
assumed. Every isolate is validated before and after downsampling, and both digests are recorded.

## 13. Deterministic downsampling and achieved depth

Target 100×, seed 20260821, `seqkit sample -p <fraction>` in the frozen `p19c2-normalize:1.0`
image. Coverage is recomputed from retained sequence **bases**, never from file size. Isolates
already below target are retained in full.

Achieved analysis depth over 150 isolates: **94 downsampled** to 99.85–100.06×, **56 retained in
full**; min 34.61×, p25 79.81×, median 99.93×, max 100.06×.

Depth is frozen as a **prediction-side covariate**, non-gating, with predeclared strata based only
on already-frozen technical thresholds:

| Stratum | n |
|---|---|
| 30–<50× | 8 |
| 50–<75× | 24 |
| 75–<100× | 24 |
| ≥100× (within sampling tolerance) | 94 |

A ±0.5× tolerance applies **at the 100× target boundary only**, because proportional sampling
lands the target at 99.85–100.06× and a naive `≥100` test misfiles most downsampled isolates
(computing 8/24/92/26 instead). Under the tolerance all 94 downsampled isolates classify
at-target and **zero** genuinely-below-target isolates are promoted. Depth is a **measured
covariate, not a demonstrated confounder**; no association has been measured, and none will be
claimed before it is.

## 14. Assembly pipeline and QC

Unicycler v0.5.1 (SPAdes 3.15.5) in short-read mode, `-t 8 --keep 1`, in the pinned
`p19c2-cleanroom:1.0` image (`sha256:59230d354a2aab46936beb9460417cc16357a23d429806e0f9b40bef7f0aea20`).

**Acceptance is fail-closed with atomic publication.** An assembly is a *candidate* until every
check passes; the assembler writes only into an attempt-specific staging directory, validation
runs against the staged artefact, validated files move to the final path with an atomic rename,
and the `.done` marker is written **last** — so a marker can never exist without a validated
artefact behind it. Required checks: frozen input/run identity; passed raw MD5 receipt; passed
exact ID-stream validation; passed coverage floor; SHA-256 of the exact reads fed to the
assembler; assembler input is a real file, never a symlink; image digest and exact command; exit
code 0; non-empty FASTA and GFA; valid FASTA structure; unique contig identifiers; total length
inside a plausibility band; final artefact hashes; and exactly one terminal state per isolate.

The plausibility band (0.70–1.30 × the isolate's own declared genome size) is **newly predeclared**
here and stated as such: the frozen design lists assembly quality and contig length as prespecified
*secondary analyses* but defines no numeric total-length rule. It is a gross-implausibility
detector for a failed or contaminated assembly, **not** an assembly-quality metric, and is not used
to judge assembly quality anywhere.

Result: **150/150 accepted.** Global reconciliation verdict PASS — 0 rejected, 0 missing states, 0
`.done`/`.failed` conflicts, 0 unvalidated publications, 0 hash mismatches, nothing left staged.
All **4/4 predeclared deterministic-rerun pilots are byte-identical**, establishing that the
assembler is reproducible on these inputs.

## 15. Temporary-storage amendment and filesystem protections

Amendment 002 routed all tool scratch to dedicated per-unit temporary directories after a 13-unit
production-path preflight; RAM tmpfs was explicitly not used for large tool workloads. Frozen
free-space reserves of 20 GiB (`/`), 30 GiB (`/data`) and 30 GiB (`/work`) were enforced by a
guard that halts the runner before a reserve is breached, checked at every phase boundary and
every 20–25 units. No reserve was breached at any point.

## 16. Twelve-tool panel plus AMRFinder execution

1,950 units = 13 × 150. Each unit runs in its pinned image with read-only input and database
mounts, its own output directory, a dedicated temp mount, and **no truth mount**. Every unit
writes a receipt recording tool, sample, exit code, status, start/end UTC, wall seconds, image
tag, image id, the exact docker command, temp bytes used, and the mount statement. Retry policy is
frozen at up to 3 attempts with identical image, database and command.

Terminal state: **1,878 OK, 72 FAILED**, zero units unaccounted for.

## 17. The 72 deterministic tool-internal failures

Every failure is deterministic, tool-internal and genome-dependent, reproduced identically across
all three attempts with identical image, database and command. **None is an infrastructure
failure**, and none is counted as a biological failure.

| Class | Units | Mechanism | Precedent |
|---|---|---|---|
| MOB-recon: zero plasmid biomarkers → `ValueError: No objects to concatenate` | 31 | all four biomarker BLAST frames empty; pandas raises on concatenating nothing | P1.12: 49/79 MOB-recon FAILED, same mechanism |
| gplas2: upstream PlasmidEC predicted no plasmid contigs | 26 | explicit tool message "No plasmids are predicted, so gplas can't do anything" | the frozen P1.12 parser has an explicit rule for contigs absent from gplas2 output |
| gplas2: internal R step `gplas_coocurrence_repeats.R` (rule `gplas_coocurr_repeats`, `otherclassifiers.smk:253`) exits 1 | 10 | identical RuleException in all 10 logs | tool-internal on these assembly graphs |
| PlasmidFinder: `IndexError: list index out of range` | 5 | identical traceback in all 5 logs | P1.12: 4/79 PlasmidFinder FAILED, same mechanism |

Taxon distribution is recorded but **not interpreted** here: tool failure rates by taxon are a
prespecified secondary analysis and will be evaluated only after truth is authorized and joined.

Each failed unit maps to `FAILED` in the frozen vocabulary for that tool-isolate pair at parsing
time; direct-block neutrality means an absent tool contributes exactly 0.0 to the logit. Overall
tool-evidence completeness across eligible contig × tool cells is **0.98136** (227,051 OK vs 4,789
FAILED cells).

## 18. Dependency, image and database audit

All 1,950 receipts were audited: **13 distinct images, exactly one image id per image across the
entire run, zero drift**, and every id matches the frozen host image. No tool, database or image
changed mid-run.

## 19. Parsing and byte-identity reconstruction

Parsing used the frozen P1.12 `parsers.py` **byte-identically** (sha256 `68599a94af066f2d…`,
parser version `p19c4-parsers/1.7`); `parse_all.py` was derived by path substitution only (10
changed lines). Output: **231,841 rows**, 19,320 contigs × 12 tools, sha256
`e3e43a0269336f2e88a670ef1b226d5ed56e616557e72ece0e41d873ffb4f48f`, **byte-identical across two
independent passes**.

Normalized call distribution: chromosome 145,426 · plasmid 41,378 · unknown 30,377 · unclassified
8,777 · FAILED 4,789 · repeat 1,093.

## 20. Prediction construction and freeze

The candidate was built by the locked P1.11 chain, in the **identical environment recorded in the
P1.11 freeze receipt** (python 3.14.6, scikit-learn 1.9.0, numpy 2.5.0, pandas 3.0.3): build pass 1
without v1.1 scores → score v1.1 with the persisted, equivalence-validated estimator → rebuild with
v1.1 injected → apply the frozen coverage gate → determinism check → candidate manifest.

The builder and candidate pipeline were derived from the frozen P1.11 components **by name
substitution only** (8 and 20 changed lines, diffs captured); the v1.1 scorer, `freeze_v12`
encoder, router and evaluators are **byte-identical copies**. **48/48 builder fixtures pass**
against the derivation, including a fixture asserting that no truth field or reference-derived
contig label is consumed.

| Candidate | Value |
|---|---|
| Contigs / eligible / isolates | 19,320 / 9,784 / 150 |
| Coverage gate | **PASS** — v1.2-General 1.0000, v1.1 1.0000, router 1.0000; 0 isolates below minimum |
| Model abstention | 0 (both models) |
| Routing abstention | 0 |
| v1.2-General positives @0.9285 | 1,641 |
| v1.1 positives @0.9524 / @0.9605 | 715 / 644 |
| Router: → v1.1 / → v1.2-General | 658 / 9,126 |
| Router positive outputs | 1,490 |
| ARG-bearing (annotation ok) | 658 true / 9,126 false |
| Deterministic rebuild | byte-identical |

**Freeze `P1.13-PREDICTION-FREEZE-001`** was executed by a freezer derived from the frozen P1.11
freezer with gate, augmentation, projection and atomic-commit logic unchanged. It gates on three
approved hashes, binds **22 artefacts** (both estimators, encoder, router, builder, pipeline,
cohort v3, amendments 004/005, reconciliation, failure review, dependency audit and more), embeds
all 150 per-isolate assembly hashes and the full 1,950-unit panel manifest, and wrote
`PREDICTIONS_FROZEN.json` atomically.

| | |
|---|---|
| Frozen table | `3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80` |
| Freeze receipt | `98e7902ac09bcb54c759c119d6e273ce2474179fd908dee423b69ba414a9b482` |
| Reproduces approved candidate | byte-for-byte, verified **twice** — by the freezer's own projection and by an independently written projection |
| Fresh rebuild from raw inputs | byte-identical |
| Git commit at freeze | `cf7f417032c2` |

## 21. Truth separation and unblinding chronology

| Date (UTC) | Event |
|---|---|
| through 2026-08-23 | design, cohort, acquisition, assembly, panel, parsing, candidate construction — **all truth-blind** |
| 2026-08-23 | candidate reached `CANDIDATE_ONLY_NOT_FROZEN`; owner approval granted for that exact candidate by hash |
| 2026-08-23/24 | freeze executed and independently verified; `PREDICTIONS_FROZEN.json` created atomically |
| 2026-08-24 | marker `P1.13_PREDICTIONS_FROZEN_AWAITING_TRUTH_AUTHORIZATION` planted; **still active** |

**Truth has never been acquired, constructed, inspected, joined or scored by any P1.13 step.** The
truth-side chain (`acquire_truth_v2.py`) refuses to run without `PREDICTIONS_FROZEN.json`, so truth
was absent from the workflow for the whole of assembly and inference — not merely unmounted. Truth
unblinding is **not** authorized; a project-closure instruction does not confer it.

## 22. Final evaluation

`[AWAITING TRUTH AUTHORIZATION]` — Phase 2 is blocked. No primary or secondary metric,
confusion matrix, comparator result or error catalogue exists, and none will be produced or
estimated before an explicit owner authorization naming this freeze id.

## 23. Limitations and applicability boundaries

See `PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md`. In brief: contig-level not replicon-level; six
taxa only; short-read draft assemblies only; performance conditional on panel availability, whose
completeness here is 0.98136; *Enterococcus* is a hard domain; v1.2-General's training claim is
*E. coli*-specific; depth is right-truncated by design (the 100× normalisation caps but cannot
raise depth); and the 30–<50× stratum holds only 8 isolates and cannot support a reliable
stratum-specific estimate.

## 24. Reproducibility and archival status

* **Evidence archive** `P1.13_EVIDENCE_ARCHIVE.tar.zst`, 15,427,604,570 bytes, sha256
  `76201303af2a0322c03bb5e570d3174c20465736535ca089d2e4b9e235dd85d2`, with an internal 87,961-row
  per-file manifest and **full streaming content verification** (87,961 ok / 0 bad / 0 extra / 0
  missing; no sampling). 751 container-owned scratch files under `p113/tmp/` were unreadable by the
  archiving user and are excluded identically from manifest and archive; the list is preserved and
  verified to touch no evidence path. Nothing was deleted.
* **Reads** are not duplicated (a second 86 GiB copy would breach the frozen reserves). They remain
  in place with a complete 604-row per-file SHA-256 manifest
  (`f42a193f1d675c8935923408560c012f6bb632b2b7dac734d304ebdf41c1dbdd`), were ENA-MD5-verified at
  acquisition, and are publicly re-fetchable by run accession.
* **Determinism demonstrated at three levels:** parsing byte-identical across two passes; the
  candidate byte-identical on rebuild; 4/4 assembly rerun pilots byte-identical.

## 25. Remaining work and decisions

| # | Item | Owner decision required |
|---|---|---|
| 1 | Truth unblinding for `P1.13-PREDICTION-FREEZE-001` | **yes** — explicit authorization naming the freeze id |
| 2 | Rotate the SSH key exposed in the 2026-08-23 transcript (still authenticates) | **yes** |
| 3 | Software/data licence — none frozen in the repository | **yes** — options prepared, selection required |
| 4 | Public release, Zenodo deposition, DOI minting | **yes** — after the release audit |
| 5 | Server termination | blocked on the local archive copy completing; owner action in any case |
| 6 | Independent Columbia pilot | **yes** — no contact made or authorized |

# Data dictionary

Field definitions for the canonical P1.13 tables. Column order in each file is authoritative;
this document explains meaning, not layout.

"Zenodo Part n" refers to the data deposit, doi:10.5281/zenodo.22086357 (CC BY 4.0):

| Part | File in the deposit |
|---|---|
| Part 1 | `PlasmidCall_evidence_tier1_execution.tar.zst` |
| Part 2 | `PlasmidCall_evidence_tier2_assemblies.tar.zst` |
| Part 3 | `PlasmidCall_evidence_tier3_evaluation.tar.zst` |
| Part 4 | `PlasmidCall_published_results.tar.zst` |

## 1. Cohort: `P1.13_SELECTED_COHORT_v3.tsv` (150 rows, 26 columns)

In this repository at `docs/evidence/P1.13_provenance/`, and at the top level of Zenodo Part 1.

| Field | Meaning |
|---|---|
| `biosample` | NCBI BioSample accession; the isolate's primary key throughout the project |
| `assembly_accession` | RefSeq/GenBank Complete Genome assembly accession for the isolate |
| `bioproject`, `study_accession` | parent project identifiers |
| `taxon` | one of the six frozen study taxa |
| `organism_name`, `infraspecific_name`, `taxid`, `species_taxid` | NCBI taxonomy as declared |
| `seq_rel_date` | assembly release date; drives the frozen year-pool rule |
| `asm_name`, `ftp_path`, `summary_source`, `refseq_category` | assembly provenance |
| `genome_size` | declared reference genome size (bp); denominator for coverage and the plausibility band |
| `n_runs_available`, `run_accession` | sequencing runs; selection rule = highest base_count, then lexically smallest accession |
| `instrument_model`, `library_selection` | platform metadata; Illumina paired WGS required |
| `read_count`, `base_count` | as declared by ENA |
| `fastq_ftp`, `fastq_md5`, `fastq_bytes` | retrieval URLs and per-file integrity values (`;`-separated, R1 then R2) |
| `estimated_coverage` | ENA-declared estimate. **Not** the analysis depth; see the depth covariate table |
| `selection_year_pool` | `2024+` or `2023 fallback`; records which pool the isolate came from |

## 2. Normalised panel calls (231,840 rows)

Zenodo Part 1 holds these as 1,800 per-sample files, `inference/parsed/<runner>/<biosample>.tsv`
(150 isolates by 12 tools). Concatenated in the frozen order they give the long table
`P1.13_predictions_normalised.tsv`: 231,840 rows (19,320 contigs by 12 tools), sha256
`e3e43a0269336f2e88a670ef1b226d5ed56e616557e72ece0e41d873ffb4f48f`. That table itself is not
in the deposit. Rebuild it from the repository root with the command below. The script
refuses to write inside the folder it reads.

```bash
python scripts/parsers/parse_outputs.py --from-long <Part 1>/inference/parsed \
  --long <output folder>/P1.13_predictions_normalised.tsv
```

Long format: one row per contig and tool. The frozen parser that writes these files is in
`scripts/parsers/`; `docs/PARSING.md` describes it.

| Field | Meaning |
|---|---|
| `sample`, `contig_id`, `contig_length` | contig identity and length in bp |
| `tool` | display name of the panel tool (e.g. `MOB-recon`, `plASgraph2`) |
| `native_call` | the tool's own label, or the parser rule that fired (for example `tool_status_FAILED`) |
| `model1_code` | normalised call in the frozen 7-term vocabulary: `chromosome`, `plasmid`, `unknown`, `unclassified`, `repeat`, `FAILED`, `MISSING` |
| `evidence_score` | tool-native score where one exists; blank otherwise |
| `native_sha256sums` | sha256 of the run's `<tool>__<sample>.SHA256SUMS` receipt, which lists the digests of the native output files; binds the row to the execution |
| `parser_version` | frozen parser version (`p19c4-parsers/1.7`) |

`FAILED` means the tool's run did not succeed, or its mandatory output was absent or malformed.
The parser writes `FAILED` for every contig of that sample and tool when the run receipt's status
is not `OK` (`native_call` = `tool_status_<status>`), when no receipt exists
(`tool_status_NOT_RUN`), or when the output cannot be parsed (`parse_error`). In P1.13 all 4,789
`FAILED` calls came from the 72 failed runs (`tool_status_FAILED`).

`MISSING` is never written by the parser. It is assigned only when the long table is turned into
one row per contig and a contig has no call for a tool. The frozen P1.13 tables hold no
`MISSING` call.

Neither `FAILED` nor `MISSING` is ever silently recoded as a negative call.

## 3. Frozen predictions: `P1.13_FROZEN_PREDICTIONS.tsv` (19,320 rows, 61 columns)

In Zenodo Part 1 (`frozen/P1.13_FROZEN_PREDICTIONS.tsv`) and, as the same bytes, in Zenodo
Part 3 (`evaluation/FROZEN_PREDICTIONS.tsv`); sha256
`3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80`.

Wide format: one row per contig. Columns 1 to 39 reproduce the approved candidate table
byte-for-byte.

| Field group | Meaning |
|---|---|
| `sample`, `contig_id`, `contig_length`, `circular`, `gfa_degree` | contig identity and assembly-graph context |
| 12 tool columns (`HyAsP` to `plASgraph2`) | the normalised call from each panel tool |
| `n_valid`, `n_plasmid`, `n_chrom`, `n_abstain`, `frac_plasmid`, `frac_chrom`, `agreement` | panel consensus summaries |
| `v11_score`, `v11_score_state`, `v11_call` | v1.1 score, availability state, and categorical call |
| `v12_score`, `v12_score_state`, `v12_call` | v1.2-General equivalents |
| `annotation_state` | `ok`, `failed`, `missing` or `unparseable` for AMRFinderPlus on that isolate |
| `ARG_bearing_bool` | **nullable**: true/false only when `annotation_state == ok`; NA otherwise. Absence of an ARG is never inferred from a failure |
| `n_qualifying_determinants` | count of core ARG determinants on the contig |
| `router_state`, `router_model`, `router_call` | `routed`/`routing_abstain`; which model was used; the routed call |
| `abstention_reason` | why a contig has no decision, where applicable |
| `is_score_evaluable_v11` / `_v12` | whether a finite score exists for that model |
| `is_eligible_ge_1kb` | contig length at least 1,000 bp (the frozen eligibility rule) |
| `in_sealed_cohort` | contig belongs to an isolate in frozen cohort v3 |
| `v11_call_bool_0_9524`, `v11_call_bool_0_9605`, `v12_call_bool_0_9285` | thresholded boolean calls at the frozen thresholds |
| `router_score`, `router_call_bool` | the routed model's score and its boolean call |
| `n_tools_available`, `n_tools_failed`, `tool_evidence_fraction` | per-contig panel completeness |
| `prov_<tool>` (12) | execution provenance for that contig and tool: `OK` or `FAILED`, from the audited terminal unit state |

## 4. Downsampling receipts: `receipts/down__<biosample>.json` (Zenodo Part 1)

Per isolate: raw and retained pair counts, total bases, **both normalized ID-stream SHA-256
digests**, the sampling fraction, the frozen seed, and coverage recomputed from bases at both
stages. `count_only_check` is recorded as `PROHIBITED and not used`.

## 5. Assembly acceptance receipts: `receipts/asm__<biosample>.json` (Zenodo Part 1)

Per isolate: frozen run identity, MD5 receipt state, exact ID-stream validation state, coverage
floor state, SHA-256 of the exact reads fed to the assembler, assembler image id and exact
command, attempt number, exit code, assembly metrics (contigs, total length, N50, longest,
eligible contigs of at least 1 kb, length ratio, plausibility band), the clean-run
verification, and the final artefact hashes.

## 6. Depth covariate: `P1.13_DEPTH_COVARIATE.csv` (150 rows)

In this repository at `docs/evidence/P1.13_provenance/`, and at the top level of Zenodo Part 1.

| Field | Meaning |
|---|---|
| `biosample` | isolate |
| `raw_depth` | depth recomputed from raw sequenced bases divided by declared genome size |
| `retained_depth` | same, after downsampling: the **analysis depth** |
| `mode` | `downsampled` or `passthrough` (already below target, retained in full) |
| `stratum` | predeclared: `30_to_50x`, `50_to_75x`, `75_to_100x`, `ge_100x` (0.5x tolerance at the 100x boundary only) |

---

## Result artefacts

These files hold the reported numbers, tables and figure data. They were built in the author's
working repository, where they sat in `docs/manuscript/` with a `PLASMIDCALL_` prefix. Here they
are in `docs/results/` without the prefix. Zenodo Part 4 holds copies as deposited in version
1.0.0. Claim C27 of `CLAIM_TO_EVIDENCE_MATRIX.tsv` and of `CLAIM_AUDIT.tsv` was later corrected
here on GitHub (57.4%, not 57.5%), so those two files differ from their Part 4 copies
(`records/PLASMIDCALL_CLAIM_TO_EVIDENCE_MATRIX.tsv` and `records/PLASMIDCALL_CLAIM_AUDIT.tsv`).

| Artefact | Kind | Content |
|---|---|---|
| `docs/results/CANONICAL_NUMBERS.json` | JSON | every value used in reader-facing documents, each with the frozen file and field it was read from, plus SHA-256 of each source |
| `docs/results/CANONICAL_TABLES.json` | JSON | every value printed in a main table, with its source table |
| `docs/results/CLAIM_AUDIT.tsv` | TSV | one row per material claim: location, category, source, denominator, estimate, interval, status, support verdict, verbatim anchor |
| `docs/results/CLAIM_TO_EVIDENCE_MATRIX.tsv` | TSV | one row per claim with its evidential status, denominator, estimate, source artefact and SHA-256 prefix |
| `docs/results/ARG_CONTEXT_BIOLOGY.json` | JSON | the genomic-context analysis of resistance-gene-bearing contigs, pooled and by taxon, class and gene family |
| `docs/results/tables/Table[1-5]*.{tsv,md}` | TSV/Markdown | the five main tables, machine-readable and rendered; digests in `TABLE_CHECKSUMS.json` |
| `docs/results/figure_source_data/Figure[1-8]*_source_data.tsv` | TSV | the plotted values for each of the eight figures |
| `docs/results/supplementary_data/Supplementary_Data_[1-11].tsv` | TSV | the eleven Supplementary Data tables; digests in `SUPPLEMENTARY_DATA_CHECKSUMS.json` |
| `docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md` | Markdown | the correction of record for every value that a frozen artefact or an earlier summary states wrongly |

Not in this repository: the figure image files, the manuscript text, its verification report,
and the reference list with its audit. No manuscript is public.

Some rows of `CLAIM_AUDIT.tsv` and `CLAIM_TO_EVIDENCE_MATRIX.tsv` name the working-repository
paths (`docs/manuscript/PLASMIDCALL_<name>`, `scripts/manuscript/`). Read them as
`docs/results/<name>` and `scripts/reporting/`. `PLASMIDCALL_PRIOR_ART_FIRST_CLAIM_AUDIT.tsv`
has no public copy.

### Canonical-number record schema

| Field | Meaning |
|---|---|
| `values.<key>` | the value itself, at full stored precision |
| `provenance.<key>.file` | the frozen file it was read from, or `derived` |
| `provenance.<key>.field` | the field, row selector or derivation used |
| `values.source_file_sha256` | SHA-256 of every frozen file cited above |

### Evaluation artefacts recovered from the execution host (2026-08-24)

Five artefacts existed on the execution host but not in this repository. They were copied off and
verified byte-exact against the host digests and, where bound, against `RESULTS_FROZEN.json`.

| Artefact | Rows | Content | Held in |
|---|---|---|---|
| `P113_TRUTH_JOINED.tsv` | 19,320 | the scored truth-prediction table every reported metric is computed from, and the table both independent verifiers re-derived their values from | Zenodo Part 3 (`evaluation/P113_TRUTH_JOINED.tsv`, 9,135,239 bytes); above this repository's 5 MB file ceiling |
| `P113_ERROR_CATALOGUE.tsv` | 3,336 | every false positive and false negative with taxon, length, depth stratum, resistance-gene status, panel agreement and truth confidence | `docs/evidence/P1.13_results/`; Zenodo Part 3 |
| `P113_UNRESOLVED_TRUTH_CHARACTERISATION.tsv` | 413 | the evaluation-phase characterisation of the unresolved contigs. Superseded in content by the enriched post-freeze `PF09a_UNRESOLVED_TRUTH_CHARACTERISATION.tsv`, which adds routing pathway, tool agreement and panel availability. Both cover the same 413 contigs and are retained | `docs/evidence/P1.13_results/`; Zenodo Part 3 |
| `P113_TOOL_OUTPUT_ACCOUNTING.tsv` | 12 | per-tool output composition: plasmid, chromosome, unknown, unclassified, repeat, `FAILED` and `MISSING` counts, and coverage | `docs/evidence/P1.13_results/`; Zenodo Part 3; Supplementary Data 10 |
| `P113_SENSITIVITY_ANALYSIS.tsv` | 4 | the prespecified evaluation-phase sensitivity scenarios, including both adversarial treatments of the unresolved contigs | `docs/evidence/P1.13_results/`; Zenodo Part 3; Supplementary Data 11 |

**Denominator caveat for `P113_TOOL_OUTPUT_ACCOUNTING.tsv`.** Its `coverage` column is computed over
the **9,784 eligible** contigs. Every performance metric reported, including the coverage column
of Table 2 and Fig. 7b, is computed over the **9,371 truth-resolved** contigs. The two therefore
differ slightly for the tools that do not answer for every contig. For example, MOB-recon reads
0.9121 on the eligible base and 0.9087 on the truth-resolved base. Both are correct on their own
denominator; the truth-resolved base is the one the metrics use, because a contig without a
truth label cannot contribute to precision or recall.

The last three were not bound in the results freeze, so their absence from this repository had not
been detectable by digest. It was found by comparing the host's evaluation directories against the
repository file by file.

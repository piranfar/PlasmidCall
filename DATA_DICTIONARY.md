# Data dictionary

Field definitions for the canonical P1.13 tables. Column order in each file is authoritative;
this document explains meaning, not layout.

## 1. Cohort — `P1.13_SELECTED_COHORT_v3.tsv` (150 rows, 26 columns)

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
| `estimated_coverage` | ENA-declared estimate. **Not** the analysis depth — see the covariate table |
| `selection_year_pool` | `2024+` or `2023 fallback`; records which pool the isolate came from |

## 2. Normalised panel calls — `P1.13_predictions_normalised.tsv` (231,841 rows)

Long format: one row per contig × tool.

| Field | Meaning |
|---|---|
| `sample`, `contig_id`, `contig_length` | contig identity and length in bp |
| `tool` | display name of the panel tool (e.g. `MOB-recon`, `plASgraph2`) |
| `native_call` | the tool's own output string, unmodified |
| `model1_code` | normalised call in the frozen 7-term vocabulary: `chromosome`, `plasmid`, `unknown`, `unclassified`, `repeat`, `FAILED`, `MISSING` |
| `evidence_score` | tool-native score where one exists; blank otherwise |
| `native_sha256sums` | hash of the tool's raw output manifest, binding this row to the execution |
| `parser_version` | frozen parser version (`p19c4-parsers/1.7`) |

`FAILED` means the tool ran and failed deterministically. `MISSING` means no output existed.
Neither is ever silently recoded as a negative call.

## 3. Frozen predictions — `P1.13_FROZEN_PREDICTIONS.tsv` (19,320 rows, 62 columns)

Wide format: one row per contig. Columns 1–39 reproduce the approved candidate byte-for-byte.

| Field group | Meaning |
|---|---|
| `sample`, `contig_id`, `contig_length`, `circular`, `gfa_degree` | contig identity and assembly-graph context |
| 12 tool columns (`HyAsP` … `plASgraph2`) | the normalised call from each panel tool |
| `n_valid`, `n_plasmid`, `n_chrom`, `n_abstain`, `frac_plasmid`, `frac_chrom`, `agreement` | panel consensus summaries |
| `v11_score`, `v11_score_state`, `v11_call` | v1.1 score, availability state, and categorical call |
| `v12_score`, `v12_score_state`, `v12_call` | v1.2-General equivalents |
| `annotation_state` | `ok`, `failed`, `missing` or `unparseable` for AMRFinder on that isolate |
| `ARG_bearing_bool` | **nullable**: true/false only when `annotation_state == ok`; NA otherwise. Absence of an ARG is never inferred from a failure |
| `n_qualifying_determinants` | count of core ARG determinants on the contig |
| `router_state`, `router_model`, `router_call` | `routed`/`routing_abstain`; which model was used; the routed call |
| `abstention_reason` | why a contig has no decision, where applicable |
| `is_score_evaluable_v11` / `_v12` | whether a finite score exists for that model |
| `is_eligible_ge_1kb` | contig length ≥ 1,000 bp (the frozen eligibility rule) |
| `in_sealed_cohort` | contig belongs to an isolate in frozen cohort v3 |
| `v11_call_bool_0_9524`, `v11_call_bool_0_9605`, `v12_call_bool_0_9285` | thresholded boolean calls at the frozen thresholds |
| `router_score`, `router_call_bool` | the routed model's score and its boolean call |
| `n_tools_available`, `n_tools_failed`, `tool_evidence_fraction` | per-contig panel completeness |
| `prov_<tool>` (12) | execution provenance for that contig × tool: `OK` or `FAILED`, from the audited terminal unit state |

## 4. Downsampling receipts — `receipts/down__<biosample>.json`

Per isolate: raw and retained pair counts, total bases, **both normalized ID-stream SHA-256
digests**, the sampling fraction, the frozen seed, and coverage recomputed from bases at both
stages. `count_only_check` is recorded as `PROHIBITED and not used`.

## 5. Assembly acceptance receipts — `receipts/asm__<biosample>.json`

Per isolate: frozen run identity, MD5 receipt state, exact ID-stream validation state, coverage
floor state, SHA-256 of the exact reads fed to the assembler, assembler image id and exact
command, attempt number, exit code, assembly metrics (contigs, total length, N50, longest,
eligible contigs ≥1 kb, length ratio, plausibility band), the clean-run verification, and the
final artefact hashes.

## 6. Depth covariate — `P1.13_DEPTH_COVARIATE.csv` (150 rows)

| Field | Meaning |
|---|---|
| `biosample` | isolate |
| `raw_depth` | depth recomputed from raw sequenced bases ÷ declared genome size |
| `retained_depth` | same, after downsampling — the **analysis depth** |
| `mode` | `downsampled` or `passthrough` (already below target, retained in full) |
| `stratum` | predeclared: `30_to_50x`, `50_to_75x`, `75_to_100x`, `ge_100x` (±0.5× tolerance at the 100× boundary only) |

---

## Manuscript artefacts

| Artefact | Kind | Content |
|---|---|---|
| `docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json` | JSON | every value used in reader-facing documents, each with the frozen file and field it was read from, plus SHA-256 of each source |
| `docs/manuscript/PLASMIDCALL_CANONICAL_TABLES.json` | JSON | every value printed in a main-text table, with its source table |
| `docs/manuscript/PLASMIDCALL_MANUSCRIPT_FINAL.md` | Markdown | manuscript source; carries `{{citation_key}}` markers rather than numbers |
| `docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md` | Markdown | manuscript with references numbered by first appearance; the version to read |
| `docs/manuscript/PLASMIDCALL_MANUSCRIPT_VERIFICATION.json` | JSON | structural, numeric and wording verification report |
| `docs/manuscript/PLASMIDCALL_CLAIM_AUDIT.tsv` | TSV | one row per material claim: location, category, source, denominator, estimate, interval, status, support verdict, verbatim anchor |
| `docs/manuscript/PLASMIDCALL_REFERENCES.{md,bib,ris}` | Markdown/BibTeX/RIS | verified reference list in three forms |
| `docs/manuscript/PLASMIDCALL_REFERENCE_AUDIT.tsv` | TSV | per-field verification of every reference against PubMed, Crossref or the publisher |
| `docs/manuscript/tables/Table[1-4]*.{tsv,md}` | TSV/Markdown | main tables, machine-readable and rendered |
| `docs/manuscript/figures/Figure[1-7]*.{svg,pdf,png}` | SVG/PDF/PNG | editable, publication and 600 dpi raster forms |
| `docs/manuscript/figures/source_data/*.tsv` | TSV | the plotted values for each figure |
| `docs/manuscript/figures/FIGURE_CHECKSUMS.json` | JSON | SHA-256 and byte size of every figure file |
| `docs/manuscript/supplementary_data/Supplementary_Data_[1-9].tsv` | TSV | oversized tables supplied separately, per the journal's Supplementary Data rule |
| `docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md` | Markdown | the correction of record for every value that a frozen artefact or an earlier summary states wrongly |

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
| `P113_TRUTH_JOINED.tsv` | 19,320 | the scored truth–prediction table every reported metric is computed from, and the table both independent verifiers re-derived their values from | off-server evidence set and the Zenodo archive; 8.7 MB, above this repository's 5 MB release ceiling |
| `P113_ERROR_CATALOGUE.tsv` | 3,336 | every false positive and false negative with taxon, length, depth stratum, resistance-gene status, panel agreement and truth confidence | `docs/evidence/P1.13_results/` |
| `P113_UNRESOLVED_TRUTH_CHARACTERISATION.tsv` | 413 | the evaluation-phase characterisation of the unresolved contigs. Superseded in content by the enriched post-freeze `PF09a_UNRESOLVED_TRUTH_CHARACTERISATION.tsv`, which adds routing pathway, tool agreement and panel availability. Both cover the same 413 contigs and are retained | `docs/evidence/P1.13_results/` |
| `P113_TOOL_OUTPUT_ACCOUNTING.tsv` | 12 | per-tool output composition: plasmid, chromosome, unknown, unclassified, repeat, `FAILED` and `MISSING` counts, and coverage | `docs/evidence/P1.13_results/`; Supplementary Data 10 |
| `P113_SENSITIVITY_ANALYSIS.tsv` | 4 | the prespecified evaluation-phase sensitivity scenarios, including both adversarial treatments of the unresolved contigs | `docs/evidence/P1.13_results/`; Supplementary Data 11 |

**Denominator caveat for `P113_TOOL_OUTPUT_ACCOUNTING.tsv`.** Its `coverage` column is computed over
the **9,784 eligible** contigs. Every performance metric reported in the manuscript, including the
coverage column of Table 2 and Fig. 7b, is computed over the **9,371 truth-resolved** contigs. The
two therefore differ slightly for the tools that do not answer for every contig — for example
MOB-recon reads 0.9121 on the eligible base and 0.9087 on the truth-resolved base. Both are correct
on their own denominator; the truth-resolved base is the one the metrics use, because a contig
without a truth label cannot contribute to precision or recall.

The last three were not bound in the results freeze, so their absence from this repository had not
been detectable by digest. It was found by comparing the host's evaluation directories against the
repository file by file.

# Reproducibility guide

This project distinguishes three things that are often conflated:

| Level | Meaning | Status |
|---|---|---|
| **Preserved evidence** | artefacts recording what actually ran; never regenerated | frozen, hash-bound |
| **Deterministically regenerable** | rebuild from preserved inputs reproduces byte-identical output | demonstrated at three levels, and re-checked from the public deposit (below) |
| **Re-executable** | rerun the whole pipeline from raw reads | possible, but needs the pinned images and databases; about 43 container wall-clock hours for the 12 classifiers plus AMRFinderPlus over 150 isolates (at most about 350 CPU-hours at the 8-CPU allocation; not measured), plus assembly time |

The panel cost is the sum of `wall_total_hours` over the 1,950 units in
`docs/postfreeze/tables/PF14_COMPUTATIONAL_DEPLOYMENT.tsv` (43.4 hours).

## What is shown to be deterministic

1. **Parsing.** 231,840 rows (19,320 contigs by 12 tools), byte-identical across two independent
   passes. The frozen parser and a command-line driver for it are in `scripts/parsers/`
   (`docs/PARSING.md`).
2. **Candidate construction.** Byte-identical on rebuild; verified again at freeze time, by an
   independently written projection of the frozen table, and on 2026-09-28 from the public data
   deposit (next section).
3. **Assembly.** 4/4 predeclared rerun pilots byte-identical, so Unicycler/SPAdes is
   reproducible on these inputs at fixed thread count.

## Reproducing the frozen predictions from the data deposit

The inputs are Parts 1 and 2 of the data deposit, doi:10.5281/zenodo.22086357:
`PlasmidCall_evidence_tier1_execution.tar.zst` (parsed calls, run receipts and state markers,
AMRFinderPlus outputs, the approved candidate and the frozen table) and
`PlasmidCall_evidence_tier2_assemblies.tar.zst` (the 150 assemblies). You also need the
prediction environment in `INSTALLATION.md` section 1.

The scripts in `scripts/evaluation/` are the frozen copies that ran. They expect the author's
working-repository layout, in which `docs/design/` was `docs/plans/` and
`scripts/pipeline/prejoin_verify_v2.py` sat in `scripts/p1_12/`. Step 1 recreates those two
paths. Do this in a scratch copy of the repository, for example a second `git clone`, so your
working clone does not change. Run every step from the root of that copy.

```bash
W="$HOME/plasmidcall_repro"                  # an empty working folder outside the repository
mkdir -p "$W"
export P112_FREEZE="$W/freeze"
export PYTHONDONTWRITEBYTECODE=1

# 1. the two paths the frozen scripts expect
mkdir -p docs/plans scripts/p1_12
cp docs/design/*.yaml docs/plans/
cp scripts/pipeline/prejoin_verify_v2.py scripts/p1_12/

# 2. Parts 1 and 2 of the data deposit
for f in PlasmidCall_evidence_tier1_execution.tar.zst PlasmidCall_evidence_tier2_assemblies.tar.zst; do
  curl -L -o "$W/$f" "https://zenodo.org/records/22086357/files/$f?download=1"
done
sha256sum "$W"/*.tar.zst
# 4531ff03c25a020016d0d31f41bcea4c47c7b7fdb5adfef7ee94771b1f053c65  PlasmidCall_evidence_tier1_execution.tar.zst
# 0d66b4315d54deb79c5b7de2d47f4bb06d9c6aa08b83a9ca2a90e101ff5a72e6  PlasmidCall_evidence_tier2_assemblies.tar.zst
python -c "import sys,tarfile; tarfile.open(sys.argv[1],'r:zst').extractall(sys.argv[2],filter='data')" \
  "$W/PlasmidCall_evidence_tier1_execution.tar.zst" "$W/part1"
python -c "import sys,tarfile; tarfile.open(sys.argv[1],'r:zst').extractall(sys.argv[2],filter='data')" \
  "$W/PlasmidCall_evidence_tier2_assemblies.tar.zst" "$W/part2"

# 3. the input tree the builder expects
R="$W/root"
mkdir -p "$R/inference/state" "$R/annotation"
mv "$W/part2/assemblies" "$R/assemblies"
mv "$W/part1/inference/parsed" "$W/part1/inference/receipts" "$R/inference/"
for t in mobsuite platon rfplasmid plascope plasmidec plasmidfinder genomad plasme plasmer \
         gplas2 plasgraph2 hyasp amrfinder; do
  mv "$W/part1/state/${t}__"* "$R/inference/state/"
done
mv "$W/part1/annotation/native" "$R/annotation/native"
cp "$W/part1/P1.13_SELECTED_COHORT_v3.tsv" "$R/"

# 4. the long call table, from the 1,800 per-sample files
python scripts/parsers/parse_outputs.py --from-long "$R/inference/parsed" \
  --long "$R/inference/P1.13_predictions_normalised.tsv"

# 5. build, score and gate the candidate
python scripts/evaluation/p113_candidate_pipeline.py --root "$R" --outdir "$W/candidate"

# 6. freeze the approved candidate: dry run, then commit into the working folder
python scripts/evaluation/p113_freeze_predictions.py --candidate-dir "$W/part1/candidate" \
  --root "$R" --out "$W/frozen"
python scripts/evaluation/p113_freeze_predictions.py --candidate-dir "$W/part1/candidate" \
  --root "$R" --out "$W/frozen" --commit

sha256sum "$R/inference/P1.13_predictions_normalised.tsv" \
  "$W/candidate/P1.13_candidate_contig_table.tsv" "$W/frozen/P1.13_FROZEN_PREDICTIONS.tsv"
```

Notes on the layout steps:

* Part 1 keeps all run markers in one `state/` folder. The builder and the freeze read only the
  1,950 panel and AMRFinderPlus markers from `inference/state/`. The acquisition, downsampling
  and assembly markers (`acquire__`, `down__`, `asm__`) stay behind; with them the freeze stops
  with "panel manifest is 2400 units, expected 1950".
* The long call table is not in the deposit as one file. Step 4 concatenates the per-sample
  files in the frozen order.
* Step 6 uses the approved candidate in Part 1 (`candidate/`), because the freeze checks the
  candidate manifest against its approved digest
  (`bbe15fc247163c604ca55135ab3d8031a57aa1ae62f6451794a269591e135708`). The manifest that step 5
  writes carries a time stamp, so its digest differs. Its candidate table does not.

Expected:

| Output | sha256 |
|---|---|
| long call table (step 4) | `e3e43a0269336f2e88a670ef1b226d5ed56e616557e72ece0e41d873ffb4f48f` |
| candidate table (step 5) | `440f16bc7002c15135ac73a233545613ad6869eddf7d421cca6dc0a1060114f8` |
| frozen prediction table (step 6, `--commit`) | `3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80` |

Step 5 also reports the coverage gate as PASS at 1.0000 for v1.2-General, v1.1 and the router,
and `rebuild identical: True`. The dry run in step 6 ends with `DRY RUN COMPLETE - nothing
written`. The `PREDICTIONS_FROZEN.json` that `--commit` writes differs from the frozen receipt in
its time stamp and software fields.

These steps were run on 2026-09-28 on Windows 11 with the section 1 environment, with the two
archives taken from a local copy whose sha256 matched the deposit's `MANIFEST.sha256`. All three
digests above matched.

**If your hashes differ**, check the prediction environment first (`INSTALLATION.md` section 1):
pickle loading and float serialisation are version-sensitive. A hash difference is a real
signal, not noise. Investigate rather than proceeding.

## Re-executing the panel from raw reads

1. Retrieve reads by run accession from ENA. Verify them against
   `docs/evidence/P1.13_provenance/P1.13_READS_MANIFEST.sha256` and the per-file MD5s in the
   cohort table.
2. Obtain the pinned images. Their digests, versions, git commits and databases are in
   `SOFTWARE_AND_DATABASE_VERSIONS.tsv`. Images carrying third-party databases are **not**
   redistributed, and the Dockerfiles are not published. An image rebuilt from the pins will not
   have the recorded digest.
3. `scripts/evaluation/p113_run.sh` is the runner as executed, with `p113_tool.sh` for each tool
   command. It expects a Linux host with the run tree at `/work/p113`, read staging at
   `/data/p113_reads` and the tool databases under `/work/p19c4/db`, all hard-coded. It is
   fail-closed throughout: it refuses to start on a cohort hash change, halts before breaching
   free-space reserves, validates read pairing exactly, enforces the 30x floor, and accepts an
   assembly only through the atomic gate.

`scripts/evaluation/p113_pairing_fixtures.py` belongs to this route. It needs Docker with
`p19c2-normalize:1.0` for two of its cases, and it writes its receipt to the hard-coded path
`/work/p113/P1.13_PAIRING_FIXTURES.json`.

## What cannot be reproduced from this repository alone

* Raw reads: public ENA data, not redistributed; retrievable by accession.
* Tool databases and images: third-party, redistribution restricted; digests, versions and
  database identities are provided.
* The bulk evidence: the parsed calls, the assemblies and the run receipts are in the Zenodo
  deposit (doi:10.5281/zenodo.22086357), Parts 1 and 2.
* Reference-derived truth labels: in Zenodo Part 3 (`evaluation/P113_TRUTH_JOINED.tsv`, 19,320
  rows); the closed reference genomes are public and cited by accession in Supplementary Data 1.
* The native tool outputs, about 31 GB: retained by the author and available on request. No
  reported value depends on them.
* The truth-construction and evaluation scripts of P1.13: `p113_acquire_truth.py`,
  `p113_truth_pipeline.py`, `p113_truth_map.sh`, `p113_join.py`, `p113_evaluate.py`,
  `p113_strata.py` and `p113_final_analyses.py`. Their SHA-256 digests are recorded in
  `docs/evidence/P1.13_results/RESULTS_FROZEN.json` (`scripts_sha256`), but no copy with those
  digests survived the retirement of the execution host, so they cannot be published. Their
  outputs are deposited: the joined truth table is in Zenodo Part 3, and the reported numbers,
  tables and figures are rebuilt from the deposited tables as described below.

## Fixtures and tests

These need only this repository; `QUICKSTART.md` runs them.

* `python scripts/evaluation/p113_builder_fixtures.py --out <file outside the repository>` gives
  48/48, with no bulk data. One fixture asserts that no truth field or reference-derived contig
  label is consumed by the builder. The receipt is byte-identical to
  `docs/evidence/P1.13_BUILDER_FIXTURES.json`. Without `--out`, the script overwrites
  `docs/evidence/P1.11_BUILDER_FIXTURES.json`, the receipt of an earlier phase.
* `python tests/test_plasmidcall_score.py` checks the standalone scorer against the frozen
  scores. The default run checks a 200-row fixture; the full 19,320-contig check runs when it is
  given the P1.13 table from the data deposit (`scripts/score/README.md`).
  `python scripts/parsers/tests/test_parse_outputs.py` checks the parser.

---

## Reproducing the reported numbers, tables and figures

The scripts in `scripts/reporting/` built every reported number, table, figure and
Supplementary Data file. They ran in the author's working repository and read and write its
layout: `docs/manuscript/PLASMIDCALL_<name>` there is `docs/results/<name>` here, and
`docs/manuscript/tables/`, `figures/source_data/` and `supplementary_data/` are
`docs/results/tables/`, `figure_source_data/` and `supplementary_data/`. The manuscript text is
not public.

| Step | Script | What it does |
|---|---|---|
| 1 | `scripts/reporting/build_canonical_numbers.py` | reads the frozen result and post-freeze tables and emits the canonical number set (`docs/results/CANONICAL_NUMBERS.json` here), recording for every value the source file and field it came from, plus a SHA-256 of each source |
| 2 | `scripts/reporting/make_tables.py` | builds the five main tables and registers every printed value in the canonical table set; asserts that the per-taxon totals reconcile to the frozen denominators |
| 3 | `scripts/reporting/make_figures.py` | regenerates all eight figures as editable SVG, publication PDF and 600 dpi PNG, with a machine-readable source-data table and a checksum manifest |
| 4 | `scripts/reporting/make_supplementary.py` | assembles the Supplementary Information and the eleven Supplementary Data files |
| 5 | `scripts/reporting/build_references.py` | emits the reference list, BibTeX, RIS and the per-field verification table |
| 6 | `scripts/reporting/number_references.py` | assigns reference numbers strictly in order of first appearance and fails closed on an unknown key or an uncited entry |
| 7 | `scripts/reporting/verify_manuscript.py` | checks the journal's structural rules, that every numeric literal resolves to a canonical source, that no superseded wording appears, and that reference numbering is complete |
| 8 | `scripts/reporting/claim_audit.py` | enumerates every material claim with its source, denominator, estimate, interval and status, and verifies each claim's verbatim anchor is present in the manuscript |
| 9 | `scripts/reporting/render_documents.py` | renders DOCX and PDF for the journal and preprint packages |

Checked here on 2026-09-28, in a scratch copy of the repository with
`docs/results/ARG_CONTEXT_BIOLOGY.json` copied to
`docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json`, and `MPLCONFIGDIR` set to a scratch
folder:

* Step 1 gives the canonical number set with its 188 values and their provenance. Compared
  with `docs/results/CANONICAL_NUMBERS.json`, 187 values and all provenance entries are
  identical. The 188th, `values.source_file_sha256`, differs in 2 of its 34 entries. `P1.13_AMENDED_PREEXECUTION_RECEIPT.json` was path-substituted at release
  (`docs/release/RELEASE_PATH_SUBSTITUTION.tsv`). For
  `docs/closure/EVIDENCE_ARCHIVE_VERIFICATION.json` the record holds the digest of an earlier
  version of that file.
* Step 2 gives all eleven files in `docs/results/tables/` and `CANONICAL_TABLES.json`
  byte-identical.
* Step 3 gives the eight figure source-data files byte-identical to
  `docs/results/figure_source_data/`. The figure image files are not in this repository, so they
  were not compared. matplotlib was 3.11.1.
* Step 4 stops: it needs `PLASMIDCALL_PRIOR_ART_FIRST_CLAIM_AUDIT.tsv`, which is not public.
* Step 5 runs on its own, but its outputs (the reference list and its audit) are not in this
  repository, so there was nothing to compare. Steps 6 to 9 need the manuscript text, which is
  not public.

The Supplementary Data files in `docs/results/supplementary_data/` are therefore preserved
outputs, with digests in `SUPPLEMENTARY_DATA_CHECKSUMS.json`, not regenerated here.

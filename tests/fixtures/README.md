# Test fixtures

Two tables used by `tests/test_plasmidcall_score.py`. Each holds scorer inputs and the frozen
expected outputs. Both are tab-separated, UTF-8, with LF line endings.

## p113_score_fixture.tsv

200 rows from 89 samples of the public P1.13 frozen prediction table.

| Item | Value |
|---|---|
| Source file | `P1.13_FROZEN_PREDICTIONS.tsv` (19,320 rows, 61 columns) |
| Source location | Zenodo [10.5281/zenodo.22086357](https://doi.org/10.5281/zenodo.22086357), archive `PlasmidCall_evidence_tier1_execution.tar.zst`, member `frozen/P1.13_FROZEN_PREDICTIONS.tsv` |
| Source sha256 | `3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80` |
| Where that digest is recorded | `docs/evidence/P1.13_results/RESULTS_FROZEN.json` (`frozen_prediction_table_sha256`) and `docs/evidence/P1.13_provenance/P1.13_PREDICTIONS_FROZEN_RECEIPT.json` |
| Archive sha256 | `4531ff03c25a020016d0d31f41bcea4c47c7b7fdb5adfef7ee94771b1f053c65` (`MANIFEST.sha256` of the deposit) |
| Fixture sha256 | `a29ed1c27265e92ab77e1e304b80796e3c9d13de2a1868ff78febc425735c0b5` |
| Made by | `python tests/fixtures/make_p113_fixture.py --table P1.13_FROZEN_PREDICTIONS.tsv` |

The rows are chosen by a fixed rule, described in `make_p113_fixture.py`. They cover every tool
state that occurs in the source, every combination of router model and router call, every
combination of v1.1 and v1.2-General call, the three scores nearest each threshold on both
sides, and contigs below and at or above 1 kb with and without a resistance gene. The source has
no `MISSING` call, no contig without a chromosome or plasmid vote, and no annotation other than
`ok`. The synthetic fixture covers those.

Columns are copied verbatim from the source: `sample`, `contig_id`, `contig_length`, the 12 tool
calls, `annotation_state`, `ARG_bearing_bool`, and the expected `v11_score`, `v11_score_state`,
`v11_call`, `v12_score`, `v12_score_state`, `v12_call`, `router_state`, `router_model`,
`router_call` and `abstention_reason`. One column is added: `n_contigs_ge_1kb`, the number of
contigs of at least 1 kb in the sample in the full source table. v1.1 needs it because the
fixture holds only some contigs of each sample.

## synthetic_rules_fixture.tsv

194 invented contigs in 7 invented samples (`SYN01` to `SYN07`). No real sequence, call or
annotation is used.

| Item | Value |
|---|---|
| Fixture sha256 | `4608c9b60c72e16cb1dc4c41974fdfd219062a02e430620a0df8355869bd4af7` |
| Made by | `python tests/fixtures/make_synthetic_fixture.py` |
| Expected outputs from | the frozen production chain, unchanged: `scripts/evaluation/build_p113_contig_table.py` (pass 1), `scripts/evaluation/v11_scorer_p111.py score`, `build_p113_contig_table.py` (pass 2, v1.1 injected), with the frozen pickles in `models/` |
| Environment used | Python 3.14.6, numpy 2.5.0, scikit-learn 1.9.0, pandas 3.0.3, Windows 11 |

It covers each tool in each of the 7 states on two base panels, contigs with no chromosome or
plasmid vote (all `MISSING`, all `FAILED`, all abstaining, and mixtures), failed, missing and
unparseable annotations, and a sample whose contigs are all below 1 kb, so that v1.1 abstains.
The samples hold all their contigs, so the scorer counts contigs of at least 1 kb from the table.

## Regenerating

Both scripts write the fixture next to themselves by default, or to `--out PATH`. Run them with
`PYTHONDONTWRITEBYTECODE=1`. The P1.13 script needs only the Python standard library and refuses
a source whose sha256 differs. The synthetic script needs scikit-learn 1.9.0, numpy 2 or later
and pandas. It runs the frozen scripts as child processes with `P112_FREEZE` set to a temporary
directory, and deletes that directory when it ends. Both reproduced the committed files byte for
byte when they were made.

## Licence

The repository's single licence rule applies here. The two scripts in this directory,
`make_p113_fixture.py` and `make_synthetic_fixture.py`, are code, under MIT (`LICENSE`), like
every `.py`, `.sh` and `.diff` file. Everything else in this directory, the two fixture tables and this
README, is under CC BY 4.0 (`LICENSE-DATA`). `p113_score_fixture.tsv` is a subset of the Zenodo
deposit above, released under CC BY 4.0, and keeps attribution to that deposit.

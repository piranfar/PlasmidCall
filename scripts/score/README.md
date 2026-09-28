# Standalone scorer

`plasmidcall_score.py` scores a table of panel-tool calls with the frozen PlasmidCall models. It
needs no assemblies, no directory tree and no training data. It reads one tab-separated table
and writes one.

| Model | Option | Needs | Threshold(s) |
|---|---|---|---|
| v1.2-General | always | numpy | 0.9285 |
| v1.1 | `--v11` | scikit-learn 1.9.0 exactly, numpy 2 or later, pandas | 0.9524 standard, 0.9605 high confidence |
| router | `--router` (implies `--v11`) | as v1.1 | as the model it routes to |

v1.2-General is read from `models/plasmidcall_v1.2-general/P1.12_V1.2_MODEL_PORTABLE.json`. It
does not load a pickle and does not import scikit-learn. v1.1 is loaded from
`models/plasmidcall_v1.1/plasmidcall_v1_1_m2.pkl`. The scorer checks the scikit-learn and numpy
versions and the file's sha256 before it unpickles anything, and stops with an error if either
check fails. Each model file is checked against its frozen sha256 before it is used.

## Usage

```bash
python scripts/score/plasmidcall_score.py --input calls.tsv --output scores.tsv
python scripts/score/plasmidcall_score.py --input calls.tsv --output scores.tsv --v11
python scripts/score/plasmidcall_score.py --input calls.tsv --output scores.tsv --router \
    --receipt run_receipt.json
```

`--output -` writes to standard output. `--receipt` writes a JSON record of the input and output
sha256, the model digests, the call counts and the software versions. The exit code is 0 on
success and 2 on invalid input, a failed model check or an unsupported environment.

## Input

One row per contig, with a header row. Columns may be in any order. Other columns are ignored.

| Column | Needed for | Values |
|---|---|---|
| `sample`, `contig_id` | always | text. Each pair must be unique. |
| `HyAsP`, `MOB-recon`, `PLASMe`, `PlaScope`, `Plasmer`, `PlasmidEC`, `PlasmidFinder`, `Platon`, `RFPlasmid`, `geNomad`, `gplas2`, `plASgraph2` | always | `chromosome`, `plasmid`, `unknown`, `unclassified`, `repeat`, `FAILED`, `MISSING` |
| `length_bp` (or `contig_length`) | v1.1, router | contig length in bp |
| `n_contigs_ge_1kb` | optional, v1.1 | number of contigs of at least 1 kb in the sample's whole assembly |
| `ARG_bearing_bool` | router | `true`, `false` or `NA` |
| `annotation_state` | optional, router | `ok`, `failed`, `missing`, `unparseable` |

Any other tool value stops the run. Use `MISSING` for a tool that gave no output for a contig
and `FAILED` for a tool run that failed. Neither is ever read as a chromosome vote.

v1.1 also uses the number of contigs of at least 1 kb in the sample. Without an
`n_contigs_ge_1kb` column this count is taken from the input table, so the table must then hold
every contig of at least 1 kb of each sample. A subset gives different v1.1 scores. See
`models/plasmidcall_v1.1/V1.1_INPUT_SPEC.md`.

For the router, a row with `annotation_state` other than `ok` gets no routed call. Without an
`annotation_state` column, `ARG_bearing_bool` = `NA` is read as `missing`. A row with
`annotation_state` = `ok` and `ARG_bearing_bool` = `NA`, or with a failed annotation and a
`true` or `false` flag, stops the run.

## Output

`sample`, `contig_id`, then, as in the frozen P1.13 tables:

* v1.1 (with `--v11`): `n_contigs_ge_1kb` (the count used), `v11_score`, `v11_score_state`,
  `v11_call`
* v1.2-General: `v12_score`, `v12_score_state`, `v12_call`
* router (with `--router`): `annotation_state`, `ARG_bearing_bool`, `router_state`,
  `router_model`, `router_call`, `abstention_reason`

Score states are `available` or `model_abstain`. Calls are `plasmid_selected`, `not_selected`,
`high_confidence_plasmid` (v1.1 only) or `model_abstain`. `not_selected` means no positive
plasmid evidence. It is never a chromosome call. Router states are `routed` or
`routing_abstain`. Scores are written as the shortest decimal that reads back to the same
double, as in the frozen tables.

## What reproduces what

The scorer re-implements the frozen rules without importing the frozen modules:

* v1.2-General: `encode`, `apply_neutrality` and `predict` in `scripts/evaluation/freeze_v12.py`,
  including the rule for a contig with no chromosome or plasmid vote and the neutrality of a
  state not seen in training. Each row is scored on its own, as the frozen builder did.
* v1.1: `build_features`, `score_frame` and `score` in `scripts/evaluation/v11_scorer_p111.py`.
* router: the routing block of `scripts/evaluation/build_p113_contig_table.py`.

On the public P1.13 frozen prediction table (19,320 contigs, Zenodo
[10.5281/zenodo.22086357](https://doi.org/10.5281/zenodo.22086357)), with Python 3.14.6,
numpy 2.5.0, scikit-learn 1.9.0 and pandas 3.0.3 on Windows 11, the scorer gives the frozen
`v12_score` and `v11_score` strings exactly on every row, and no call, state or router
disagreement. `tests/test_plasmidcall_score.py` checks this on a 200-row fixture, and on the full
table when it is given the file.

## Tests

```bash
python tests/test_plasmidcall_score.py
python tests/test_plasmidcall_score.py --p113-table P1.13_FROZEN_PREDICTIONS.tsv
```

The v1.1 and router tests are skipped, not failed, when scikit-learn 1.9.0 is not installed.
With pytest: `python -m pytest -p no:cacheprovider tests`.

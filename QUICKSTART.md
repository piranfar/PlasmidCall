# Quickstart

Runs in a few minutes on a laptop. No containers, no bulk data, and no network access once the
three packages are installed.

The commands are for a bash shell (Linux, macOS, or Git Bash on Windows). Run them from the root
of your clone. Everything they write goes to a folder next to the clone, so no tracked file
changes. On Windows, clone to a short path or use `git -c core.longpaths=true clone`, because
some paths in the repository are long.

## 1. Set up

```bash
python -m venv ../plasmidcall-venv
source ../plasmidcall-venv/bin/activate      # Git Bash on Windows: source ../plasmidcall-venv/Scripts/activate
pip install "scikit-learn==1.9.0" "numpy==2.5.0" "pandas==3.0.3"

OUT="$PWD/../plasmidcall_quickstart"
mkdir -p "$OUT"
export P112_FREEZE="$OUT/freeze"
export PYTHONDONTWRITEBYTECODE=1
```

`P112_FREEZE` matters: importing `scripts/evaluation/freeze_v12.py` creates a directory, and
without this variable it would be a default path from the original workstation (see
`INSTALLATION.md`). `PYTHONDONTWRITEBYTECODE=1` stops Python writing `__pycache__` folders into
the clone. The versions are the ones the frozen artefacts were produced with; `INSTALLATION.md`
explains why they matter.

## 2. Check the release

```bash
# the standalone scorer against frozen P1.13 scores and synthetic edge cases
python tests/test_plasmidcall_score.py

# the frozen panel-output parser on a synthetic input tree
python scripts/parsers/tests/test_parse_outputs.py

# 48 fixtures through the production contig-table builder
python scripts/evaluation/p113_builder_fixtures.py --out "$OUT/P1.13_BUILDER_FIXTURES.json"
cmp "$OUT/P1.13_BUILDER_FIXTURES.json" docs/evidence/P1.13_BUILDER_FIXTURES.json && echo "fixture receipt identical"

# release readiness: secrets, personal paths, large files, artefact hashes, claims
python scripts/release/release_check.py
```

Expected:

* scorer tests: `18 passed, 1 skipped, 0 failed`. The skipped test needs the full P1.13
  prediction table from the data deposit; `scripts/score/README.md` shows how to pass it.
* parser self-test: `19 checks, 19 passed, 0 failed`.
* builder fixtures: `48 fixtures, 48 passed, 0 failed`, and `fixture receipt identical`. The
  receipt is byte-identical to the frozen `docs/evidence/P1.13_BUILDER_FIXTURES.json`.
* release check: it needs a git clone, because it scans the files that git tracks. It exits 0
  only when every category is 0. On v1.1.0 it reports 0 findings: `TOTAL FINDINGS: 0` and
  `VERDICT: PASS`. It also lists, without counting them as findings, the frozen files whose
  released bytes differ from the recorded digest only by a documented release change (line
  endings or path substitution); `docs/release/RELEASE_PATH_SUBSTITUTION.md` explains each
  difference. Its personal-path check is narrow. It matches only `C:\Users\<name>` and
  `/home/<name>`, and only in the top-level documents and `scripts/release/`. Frozen files still
  contain other absolute paths from the original workstation and the execution host; the Known
  issues in `docs/closure/RELEASE_STATUS_2026-09.md` describe them.

Always pass `--out` to the fixture script. Without it, the script writes its receipt to
`docs/evidence/P1.11_BUILDER_FIXTURES.json`, which is the tracked receipt of an earlier phase,
and overwrites it. If that happens, restore it with
`git checkout -- docs/evidence/P1.11_BUILDER_FIXTURES.json`.

## 3. Score your own panel calls

PlasmidCall scores the calls of 12 plasmid classifiers on each contig. First try the scorer on
the 200-contig fixture shipped with the tests:

```bash
python scripts/score/plasmidcall_score.py --input tests/fixtures/p113_score_fixture.tsv \
  --output "$OUT/fixture_scores.tsv" --router
```

It prints `scored 200 rows from 89 samples` and the call counts. v1.2-General is scored from
the portable model with numpy only; `--v11` adds v1.1 and `--router` adds the routed call.

For your own assemblies, run the 12 tools with the versions and commands in
`SOFTWARE_AND_DATABASE_VERSIONS.tsv` and `scripts/evaluation/p113_tool.sh`. Then parse their
native outputs into calls and score them:

```bash
ASSEMBLIES=/path/to/assemblies     # ASSEMBLIES/<sample>/shortread.fasta
NATIVE=/path/to/native             # NATIVE/<runner key>/<sample>/..., one folder per tool
python scripts/parsers/parse_outputs.py --assemblies "$ASSEMBLIES" --native "$NATIVE" \
  --status-from-outputs --wide "$OUT/calls_wide.tsv" --summary "$OUT/parse_summary.json"
python scripts/score/plasmidcall_score.py --input "$OUT/calls_wide.tsv" \
  --output "$OUT/scores.tsv" --v11 --receipt "$OUT/score_receipt.json"
```

* The runner keys are `mobsuite platon rfplasmid plascope plasmidec plasmidfinder genomad
  plasme plasmer gplas2 plasgraph2 hyasp`. If you have run receipts like the frozen runs, pass
  `--receipts DIR` instead of `--status-from-outputs`. `docs/PARSING.md` gives the input
  layout, the seven call states, and when a call is `FAILED` or `MISSING`.
* v1.1 uses the number of contigs of at least 1 kb in each sample, so keep every contig of a
  sample in the table. The parser does this.
* `--router` also needs an `ARG_bearing_bool` column from AMRFinderPlus, which the parser does
  not add. See `scripts/score/README.md`.
* `models/README.md` describes both models, their thresholds, training data and file digests.
  `models/plasmidcall_v1.1/V1.1_INPUT_SPEC.md` gives the exact v1.1 inputs.

Read `KNOWN_LIMITATIONS.md` before using the scores. In particular, the validated training claim
of v1.2-General is *E. coli*-specific, and precision fell below 0.95 in three of the six
evaluated taxa.

## What needs more than this repository

* Rebuilding the frozen P1.13 predictions needs Parts 1 and 2 of the data deposit
  (doi:10.5281/zenodo.22086357). `REPRODUCIBILITY.md` gives the tested steps.
* Re-running the 12-tool panel needs the pinned images and their databases, which are not
  redistributed. `SOFTWARE_AND_DATABASE_VERSIONS.tsv` gives their digests, versions and database
  identities.

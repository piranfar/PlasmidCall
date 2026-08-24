# Quickstart

Runs in a few minutes on a laptop. No containers, no bulk data, no network access.

```bash
python -m venv .venv && .venv\Scripts\activate
pip install "scikit-learn==1.9.0" "numpy==2.5.0" "pandas==3.0.3"

# 1. builder fixtures — 48 cases through the production builder
python scripts/p1_13/p113_builder_fixtures.py

# 2. exact read-pair validation fixtures
python scripts/p1_13/p113_pairing_fixtures.py     # requires docker for 2 of 15 cases

# 3. release readiness: secrets, paths, large files, artefact hashes
python scripts/release/release_check.py
```

Expected: `48 fixtures, 48 passed, 0 failed`, and a release check reporting `0` findings in every
category.

## Scoring a contig table with the frozen model

```bash
python scripts/p1_13/build_p113_contig_table.py \
  --root <root with assemblies/, inference/, annotation/> \
  --out  my_contig_table.tsv \
  --model models/plasmidcall_v1.2-general/plasmidcall_v1_2_general.pkl
```

The builder is truth-blind by construction: a guard refuses any input path that looks
truth-derived, and a fixture asserts that no truth field or reference-derived contig label is
consumed.

## What you cannot do from this repository alone

Re-run the 12-tool panel — that needs the pinned images and their databases, which are not
redistributable. Use the recipes and digests in `SOFTWARE_AND_DATABASE_VERSIONS.tsv`.

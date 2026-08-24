# Installation

Two environments are involved and they are deliberately separate.

## 1. Analysis environment (candidate construction, freezing, evaluation)

This is the environment recorded in the P1.11 and P1.13 freeze receipts. Reproducing frozen
artefacts **byte-identically** requires matching it:

| Component | Version |
|---|---|
| Python | 3.14.6 |
| scikit-learn | 1.9.0 |
| numpy | 2.5.0 |
| pandas | 3.0.3 |
| platform | Windows 11 (26200) |

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install "scikit-learn==1.9.0" "numpy==2.5.0" "pandas==3.0.3"
```

Different versions may still run, but pickle compatibility and floating-point serialisation are
**not** guaranteed to reproduce the frozen hashes. If your hashes differ, check this first.

## 2. Execution environment (panel, assembly)

Every tool runs in a pinned container. Nothing is installed on the host. Images are identified by
immutable digest in `SOFTWARE_AND_DATABASE_VERSIONS.tsv`.

```bash
docker image inspect p19c2-cleanroom:1.0 --format '{{.Id}}'
# must equal sha256:59230d354a2aab46936beb9460417cc16357a23d429806e0f9b40bef7f0aea20
```

Requirements: Docker, ~64 CPU cores and 125 GiB RAM for the full panel at 8 concurrent units, and
free space respecting the frozen reserves (20 GiB `/`, 30 GiB data volumes).

**Images containing third-party databases are not redistributed.** Build or pull recipes and
immutable digests are provided instead; see `THIRD_PARTY_LICENSE_AND_REDISTRIBUTION_AUDIT.tsv`.

## 3. Fixture-only environment

To run the fixture suite you need **only** section 1. No containers, no bulk data, no network.
See `QUICKSTART.md`.

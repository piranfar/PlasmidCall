# Installation

Three environments are involved. They are deliberately separate.

**Windows:** clone to a short path, or use `git -c core.longpaths=true clone`, because some paths
in the repository are long enough to exceed the Windows path limit inside a deep folder.

## 1. Prediction environment (candidate construction and prediction freeze)

This is the environment recorded in the P1.11 and P1.13 prediction freeze receipts. Reproducing
the frozen prediction artefacts **byte-identically** requires matching it:

| Component | Version |
|---|---|
| Python | 3.14.6 |
| scikit-learn | 1.9.0 |
| numpy | 2.5.0 |
| pandas | 3.0.3 |
| platform | Windows 11 (build 26200) |

```bash
python -m venv .venv
source .venv/bin/activate          # Linux or macOS
# source .venv/Scripts/activate    # Git Bash on Windows
# .venv\Scripts\Activate.ps1       # PowerShell on Windows
pip install "scikit-learn==1.9.0" "numpy==2.5.0" "pandas==3.0.3"
```

Both model pickles need scikit-learn 1.9.0 exactly and numpy 2 or later. Other versions may
still run parts of the code, but pickle loading and floating-point serialisation are **not**
guaranteed to reproduce the frozen hashes. If your hashes differ, check this first.
`models/README.md` gives the model digests and the pickle safety notes.

The standalone scorer (`scripts/score/plasmidcall_score.py`) needs only numpy for v1.2-General.
It needs scikit-learn 1.9.0 and pandas only for v1.1 and the router. The parser
(`scripts/parsers/parse_outputs.py`) uses the Python standard library only.

**Import side effect.** `scripts/evaluation/freeze_v12.py` creates a directory when it is
imported. By default this is a Windows drive path from the original workstation; on Linux or
macOS it becomes a relative folder under the current directory. The builder, the fixtures and
the candidate pipeline import it. Set `P112_FREEZE` to a scratch folder before running them:

```bash
export P112_FREEZE="$HOME/plasmidcall_scratch/freeze"
```

## 2. Evaluation environment (truth join, metrics, bootstrap)

The truth join, the metrics and the bootstrap ran on Linux x86_64 with Python 3.10.12 and numpy
2.2.6, as recorded in `docs/evidence/P1.13_results/RESULTS_FROZEN.json`
(`software_environment`). The contig-to-reference alignment used minimap2 2.28-r1209 inside
`p19c2-cleanroom:1.0`.

## 3. Execution environment (panel, assembly)

Every tool ran in a pinned container. Nothing was installed on the host.
`SOFTWARE_AND_DATABASE_VERSIONS.tsv` gives, for every image, the immutable digest, the tool
version and git commit, and the database identity (Zenodo record, file and md5, or the git tag
of a database built into the image). The versions were read from the lockfiles and commit
records inside the images that ran. `docs/release/IMAGE_VERSION_RECEIPT_2026-09-28.txt` records
each read-only command and its output.

```bash
docker image inspect p19c2-cleanroom:1.0 --format '{{.Id}}'
# must equal sha256:59230d354a2aab46936beb9460417cc16357a23d429806e0f9b40bef7f0aea20
```

`scripts/evaluation/p113_run.sh` ran 8 units at a time by default (`SLOTS=8`). The recorded
commands limit each container to 8 CPUs and 24 GB of memory (40 GB for PLASMe and Plasmer).
Peak memory was not measured. The run also enforced the free-space reserves frozen in
`docs/design/P1.13_AMENDMENT_002.yaml` (20 GiB on `/`, 30 GiB on each data volume).

**Images containing third-party databases are not redistributed.** This repository gives the
image digests and the package pins, git commits and database identities instead. The build
files (Dockerfiles) are not in this repository or in the data deposit. A rebuild from the pins
will not give the same image digest, so the digests identify the images that ran but cannot be
used to check a rebuilt image. Third-party licences and citation obligations are listed in
`docs/release/THIRD_PARTY_LICENSE_AUDIT.tsv`. Each licence was read on 2026-09-28 at the tag or
commit that ran, where upstream has one; `LICENSE_REVIEW.md` summarises the results.

## 4. What the quick checks need

`QUICKSTART.md` needs only section 1: no containers, no bulk data and no network access after
the packages are installed.

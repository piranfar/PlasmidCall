# PlasmidCall

[![Software DOI](https://img.shields.io/badge/software%20DOI-10.6084%2Fm9.figshare.34018380-blue.svg)](https://doi.org/10.6084/m9.figshare.34018380)
[![Data DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22086356.svg)](https://doi.org/10.5281/zenodo.22086356)
[![Code licence: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Data licence: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATA)

Code, frozen models and derived data for a study of **where antimicrobial resistance
determinants sit in bacterial genomes**, and of how well automated methods recover that
placement from short-read assemblies.

> No article describing this work has been published yet, and nothing here has been peer
> reviewed. The software DOI above archives the releases of this repository on Figshare. The
> data DOI belongs to the data deposit and resolves to its latest version.
> The deposit holds no model files and is not an archive of this repository's code. Its Part 1
> does hold as-executed copies of the P1.13 run scripts, including the frozen parser, under
> CC BY 4.0. The models and the maintained code are in this repository.

## The study in one paragraph

150 bacterial genomes were assembled de novo from public short-read data across six
bacterial taxa of clinical importance, three defined at species level and three at genus
level. Each isolate was paired with its own closed reference genome, and the 9,784 of 19,320
assembled contigs that met the 1 kb eligibility floor were aligned back to that reference to
establish the replicon each derives from; 9,371 of them resolved to a single replicon class. Resistance determinants were annotated on the same contigs. Those labels then
served as truth for a prospectively sealed, truth-blind evaluation of 12 third-party
classifiers and three predeclared baselines: the design, cohort, thresholds and analysis plan
were hash-sealed before any read was retrieved, and predictions were frozen and self-re-executed
twice by the same operator, with no second participant, before any truth artefact reached
the analysis system.

## Principal result

Of **635 resistance-gene-bearing contigs, 266 (41.9%) are plasmid-derived**. The proportion
runs from 57.4% in *Citrobacter* spp. to 7.1% in *Serratia* spp., and across gene families the distribution is
bimodal: of 40 families with at least 10 contigs, 15 sit at or above 90%
plasmid-derived and 14 at or below 10%. These are truth counts obtained by alignment and do
not depend on any classifier.

On the evaluation, PlasmidCall v1.2-General met its prespecified endpoint — precision 0.9770
(95% CI 0.9642–0.9872) at recall 0.6631, coverage 1.0000 — and no third-party tool or predeclared
baseline reached precision 0.95 at any observed coverage. Six evaluated rows achieved a higher
pooled F1, and precision fell below the floor in three of the six taxa. Separately from the
endpoint above, the frozen two-domain router — not the classifier — is reported as a
validated negative result. Those limits are in `KNOWN_LIMITATIONS.md` and are not
footnotes to the claim; they are part of it.

## Layout

```
scripts/pipeline/     acquisition, assembly, classifier-panel execution, the v1.2-General fit
                      (freeze_v12.py), the v1.1 scorer, the router and the contig-table builder
scripts/evaluation/   P1.13 execution: builder, candidate pipeline and prediction freeze
scripts/model/        the v1.1 development scripts (P1.10)
scripts/parsers/      the frozen panel-output parser and parse_outputs.py
scripts/score/        standalone scorer: v1.2-General with numpy only; v1.1 and the router optional
scripts/reporting/    tables, figures and the manuscript build
scripts/release/      release checks
tests/                scorer tests and their fixtures
models/               the frozen v1.1 and v1.2-General models and the portable model
docs/design/          the frozen design and every amendment, in the order they were made
docs/evidence/        execution and verification receipts
docs/results/         every reported table, figure source data, and the canonical number set
docs/postfreeze/      analyses defined after the results freeze, labelled as such
docs/closure/         technical report, intended use, limitations and non-claims
docs/release/         release matrix, licence audit and the record of release-time path changes
```

The P1.13 truth-construction and evaluation scripts are recorded by digest but did not survive
the retirement of the execution host; `REPRODUCIBILITY.md` says what replaces them.

## Scoring contigs with PlasmidCall

PlasmidCall takes the calls of twelve plasmid classifiers on each contig and returns a score
and a call. `scripts/parsers/parse_outputs.py` turns the classifiers' native outputs into those
calls with the frozen parser (`docs/PARSING.md`). `scripts/score/plasmidcall_score.py` scores
them: v1.2-General from the portable JSON with numpy only, and v1.1 and the router when
scikit-learn 1.9.0 is installed. On the 19,320 contigs of the public P1.13 evaluation, the
scorer reproduces the frozen v1.2-General, v1.1 and router outputs exactly. `tests/` checks
this on all 19,320 contigs when given the P1.13 table from the data deposit; the default run
checks a 200-row fixture. Model files, digests and inputs are described in `models/README.md`.

## Tracing a published number

`docs/results/CANONICAL_NUMBERS.json` records, for **every** numerical value in the manuscript,
the frozen source file and the field within it that the value was read from, together with that
source's SHA-256. `docs/results/CLAIM_AUDIT.tsv` lists each material claim with its location,
denominator, estimate, interval, evidential status and supporting artefact. Claims marked
post-freeze were defined after the results freeze and are not part of the prespecified endpoint
set.

## What is not here

**Raw sequencing reads.** Public archive data, cited by run, sample and assembly accession with
the MD5 of every file as verified at acquisition, in
`docs/results/supplementary_data/Supplementary_Data_1.tsv`. Not redistributed.

**The bulk evidence.** The parsed classifier calls, the 150 assemblies, the execution receipts
and the joined truth table are in the Zenodo data deposit, doi:10.5281/zenodo.22086357
(version 1.0.0), which is the citable archive for the data. The deposit holds no model files
and is not an archive of this repository's code. Its Part 1 does hold as-executed copies of the
P1.13 run scripts, including the frozen parser, under CC BY 4.0.
The native unparsed tool outputs, about 31 GB, are retained by the author and available on
request; no published value depends on them.

## Limits on interpretation

Read `docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md` before reusing these numbers. In
short: the cohort was deliberately de-clustered and is **not a prevalence estimate**; a
plasmid-derived contig is a statement about **location, not mobility**, and no transfer or
conjugation was measured; the unit is the **contig, not the gene copy**; and the separation of
*vanA*-type from *vanB*- and *vanD*-type determinants is reported as an internal check that the
labelling recovers known structure blind, **not as new genetics**.

## Licences

One rule covers every file in this repository.

| What | Licence |
|---|---|
| Code and models: every `.py`, `.sh` and `.diff` file anywhere in the repository, and the model files under `models/` other than Markdown | **MIT**, see `LICENSE` |
| Everything else: documentation, tables, fixtures and metadata | **CC BY 4.0**, see `LICENSE-DATA` |
| Raw reads | not ours to license; public archive records, cited by accession |
| Third-party programs run here | their own; read on 2026-09-28 at the tag or commit that ran, where upstream has one; see `LICENSE_REVIEW.md` and `docs/release/THIRD_PARTY_LICENSE_AUDIT.tsv` |

## Citation

Cite this software by the DOI of the release you used. Release v1.1.0 is
**https://doi.org/10.6084/m9.figshare.34018380.v1**; 10.6084/m9.figshare.34018380 resolves to
the latest archived release. `CITATION.cff` gives the full metadata. Cite the data deposit by
its version DOI, **https://doi.org/10.5281/zenodo.22086357** (version 1.0.0). The concept DOI
10.5281/zenodo.22086356 resolves to the latest version of the deposit.

## Getting started

`INSTALLATION.md`, then `QUICKSTART.md`. `REPRODUCIBILITY.md` describes what can be reproduced
from this repository alone and what needs the Zenodo deposit. To score your own contigs, start
with `docs/PARSING.md` and `models/README.md`.

# Licence review

Reviewed 2026-09-28 for release v1.1.0. This file records what the licence files say. It is not
legal advice.

## What this repository licenses

One rule covers every file.

| What | Licence |
|---|---|
| Code and models: every `.py`, `.sh` and `.diff` file anywhere in the repository, and the model files under `models/` other than Markdown | MIT, see `LICENSE` |
| Everything else: documentation, tables, fixtures and metadata | CC BY 4.0, see `LICENSE-DATA` |

The frozen panel-output parser in `scripts/parsers/frozen/` is original code of this project. It
reads the output files of the classifiers and copies no third-party code. For the PlaScope
column it re-implements, in Python, the aggregation rule of plasmidEC's
`transform_centrifuge_output.R`. plasmidEC is under the MIT licence, and `docs/PARSING.md`
credits the rule.

`tests/fixtures/p113_score_fixture.tsv` is a subset of the P1.13 frozen prediction table, which
is already public in the data deposit (doi:10.5281/zenodo.22086357, CC BY 4.0).

## What this repository does not redistribute

No third-party program, container image or database is included. The twelve classifiers,
Centrifuge, AMRFinderPlus, BLAST+, Unicycler and SPAdes, skani, minimap2 and SeqKit were run from
pinned container images and are cited, not redistributed. Raw sequencing reads are public
archive data, cited by accession.

The licence of each of these programs was read on 2026-09-28 from its upstream repository, at
the tag or commit that ran where upstream has one. No source tag matches the Plasmer image, so
the Plasmer default branch and the LICENSE file inside the image were read. For BLAST+, the
public domain notice on the default branch of the NCBI C++ Toolkit was read, with the licence
field of the BLAST+ conda package in `p19c2-cleanroom:1.0` and `p19c4-hyasp:1.0`.
`docs/release/THIRD_PARTY_LICENSE_AUDIT.tsv` gives each result and its source.
`docs/release/IMAGE_VERSION_RECEIPT_2026-09-28.txt` records the requests and their output
(section D).

## Points for anyone who re-runs the panel

- geNomad is distributed under a Lawrence Berkeley National Laboratory licence titled
  "ACADEMIC, INTERNAL, RESEARCH & DEVELOPMENT, NON-COMMERCIAL USE ONLY, LICENSE". The same
  licence file is at tag v1.7.1, the version that ran, and on the default branch. Its
  condition (4) reads:

  > Use of the software, in source or binary form is for INTERNAL USE, RESEARCH & DEVELOPMENT,
  > NON-COMMERCIAL USE, purposes ONLY. User must be an accredited academic institution. All
  > commercial use rights for the software are reserved by Berkeley Lab. A separate commercial
  > use license is available from Berkeley Lab at IPO@lbl.gov

  Its other conditions require redistributions to keep the copyright notice, the conditions and
  the disclaimer (1, 2); forbid use of the Berkeley Lab names to endorse derived products without
  written permission (3); require the user to indemnify Berkeley Lab and the U.S. Government (5);
  and grant Berkeley Lab and the U.S. Government a licence to any enhancements the user makes (6).
  The full text is at https://github.com/apcamargo/genomad/blob/v1.7.1/LICENSE. geNomad and its
  database are not redistributed here. Anyone who runs the full panel must obtain geNomad from
  upstream under this licence.
- PLASMe and plASgraph2 have no licence file at the top level of their upstream repositories at
  the tags that ran (v1.1 and v1.0.0). They were run here and are not redistributed. Obtain them
  from upstream and check their terms.
- PlasmidFinder has no licence file at tag 2.0.1. Its README.md at that tag states the Apache
  License, Version 2.0.
- The GPL-licensed programs (Platon, RFPlasmid, gplas2, Centrifuge and Unicycler under GPL-3.0,
  and SPAdes under GPL-2.0) were run as separate programs inside their images. PlaScope's own
  script (GPL-3.0) was not run: Centrifuge ran directly on the PlaScope database. Nothing in this
  repository links to or copies their code.

## Pickled models

`models/plasmidcall_v1.1/plasmidcall_v1_1_m2.pkl` and
`models/plasmidcall_v1.2-general/plasmidcall_v1_2_general.pkl` are Python pickles. Loading a
pickle executes code. Load only files whose SHA-256 matches `models/README.md`. The v1.2-General
model is also provided as `P1.12_V1.2_MODEL_PORTABLE.json`, which needs no pickle.

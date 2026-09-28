# Release status, September 2026

**Dated** 2026-09-28. **Prepared for** release v1.1.0. **Author** Vahhab Piranfar, Independent
Researcher, Jersey City, NJ, USA (ORCID 0000-0003-3653-5739).

This note records the public state of the project. It supersedes the release statements in the
dated records listed below. It changes no frozen record.

## Public state, checked on 2026-09-28

| Item | State |
|---|---|
| Code repository | github.com/piranfar/PlasmidCall. Public. Created on 2026-08-24. The v1.0.0 content is commit `5f746ed`; the last change before v1.1.0 is commit `e062dc0` (2026-08-27). No git tag and no GitHub release existed before v1.1.0. |
| Data deposit | Zenodo, doi:10.5281/zenodo.22086357 (version 1.0.0; concept doi:10.5281/zenodo.22086356). A dataset under CC BY 4.0, published on 2026-08-24. It holds six files: four archives (Parts 1 to 4, named in `DATA_DICTIONARY.md`), `MANIFEST.sha256` and `README.md`. |
| What the deposit holds | Derived data and evaluation evidence: parsed calls, run receipts, AMRFinderPlus outputs, the approved candidate, the frozen predictions, the 150 assemblies, the joined truth table and the published results. It holds no model files. Part 1 (`env/`) also holds as-executed copies of the P1.13 run scripts, including the frozen parser, under the deposit's CC BY 4.0. |
| Software DOI | Figshare, doi:10.6084/m9.figshare.34018380.v1 (release v1.1.0, published on 2026-09-28); 10.6084/m9.figshare.34018380 resolves to the latest archived release. The item holds one file, `PlasmidCall-1.1.0.zip` (2,491,526 bytes, SHA-256 `a2218569...`), the tree of tag `v1.1.0`. Figshare shows one licence per item, MIT; `LICENSE` and `LICENSE-DATA` inside the zip set the licence of each file. The DOI was minted after the tag, so the copy of this note inside the release says "None yet". |
| Licences | One rule. Code and models, meaning every `.py`, `.sh` and `.diff` file and the model files under `models/` other than Markdown: MIT (`LICENSE`). Everything else, including documentation, tables, fixtures and metadata: CC BY 4.0 (`LICENSE-DATA`). |
| Manuscript | None is public. |

## Dated records that describe an earlier state

These files are records of their date and are kept as written, except for the two line edits
the table describes.

| Record | What it says | Current fact |
|---|---|---|
| `docs/closure/P113_CURRENT_STATE.json` | `actions_not_taken`: no repository made public, no DOI minted. `deliverables_prepared`: 7 figures, 4 main tables, 9 Supplementary Data files | The repository is public and the data DOI exists (above). The released results have 8 figures (source data), 5 main tables and 11 Supplementary Data files in `docs/results/`. |
| `docs/closure/PLASMIDCALL_FINAL_TECHNICAL_REPORT.md`, section 25 | licence, public release and DOI still to be decided | Decided as above. A banner now says so. One existing line was also edited in v1.1.0: the version 2.0 status block linked to the manuscript file, which is not public, so that link now points to `docs/results/` and the executive summary. On 2026-09-28, at the owner's request, two rows of the section 25 open-items table (items 2 and 6) were removed. They concerned the execution host, retired on 2026-09-19, and a collaboration that did not take place. |
| `docs/closure/PROJECT_STATE_RECONCILIATION.md` | state of 2026-08-24, before truth was authorised; names the private working repository | A banner now says so. One existing line was also edited in v1.1.0: the repository line now adds "(private working repository; not publicly accessible)", because readers cannot open that URL. On 2026-09-28, at the owner's request, the text of section 4 was removed. It concerned the execution host, retired on 2026-09-19. |
| `docs/closure/PLASMIDCALL_TIMELINE.tsv`, `docs/evidence/P1.13_provenance/P1.13_PREDICTIONS_READY_FOR_FREEZE_APPROVAL` | parsed call table of 231,841 rows | 231,840 rows; the extra line is the header (correction addendum, E6). |
| `docs/closure/MANUSCRIPT_PHASE_DELTA_MANIFEST.tsv` | digests of the documentation files as of the manuscript phase, under working-repository paths | Several of those files were corrected in v1.1.0, so their digests differ. Use the release's `CHECKSUMS.sha256` for current digests. |
| `docs/results/ASSET_INDEX.tsv` | figures and tables blocked, awaiting truth | Superseded by `docs/results/tables/` and `docs/results/figure_source_data/`. |
| `docs/release/PUBLIC_RELEASE_MATRIX.tsv` | the pre-release plan | Updated in v1.1.0 with the actual status, licence and a `released_location` column. |

## What v1.1.0 adds

* `scripts/parsers/`: the frozen panel-output parser, byte-identical to the copy that ran, with a
  command-line driver and a self-test. `docs/PARSING.md` describes it.
* `scripts/score/` and `tests/`: a standalone scorer for tables of panel calls, and its tests
  and fixtures.
* `models/README.md` and `models/plasmidcall_v1.1/V1.1_INPUT_SPEC.md`: model descriptions,
  digests and the exact v1.1 inputs.
* `docs/release/RELEASE_PATH_SUBSTITUTION.tsv` and `.md`: every byte difference that the
  v1.0.0 build introduced (line endings and path substitution), with original and released
  digests.
* Corrected documentation: working commands and paths in `QUICKSTART.md` and
  `REPRODUCIBILITY.md`; the environments in `INSTALLATION.md`; digests, versions and database
  identities for every tool in `SOFTWARE_AND_DATABASE_VERSIONS.tsv`; row counts, file locations
  and the `FAILED` and `MISSING` definitions in `DATA_DICTIONARY.md`; the replication status in
  `KNOWN_LIMITATIONS.md`; claim C27 in `docs/results/CLAIM_TO_EVIDENCE_MATRIX.tsv` (57.4%, not
  57.5%: 54 of 94 contigs).
* `scripts/reporting/claim_audit.py`: it printed 57.5% for C27 because it rounded the stored
  fraction 0.5745 a second time. It now computes the percentage from the counts, so the corrected
  matrix is again the output of its generator (next section).
* `docs/release/IMAGE_VERSION_RECEIPT_2026-09-28.txt`: the read-only commands, and their output,
  behind the versions, commits and database identities in `SOFTWARE_AND_DATABASE_VERSIONS.tsv`
  and the licence sources in `docs/release/THIRD_PARTY_LICENSE_AUDIT.tsv`.
* The licence audit now covers Centrifuge and BLAST+, and gives the tag or commit at which each
  licence was read.

## Reproduction checks run on 2026-09-28

On Windows 11 with Python 3.14.6, scikit-learn 1.9.0, numpy 2.5.0 and pandas 3.0.3:

* From Parts 1 and 2 of the data deposit and this repository alone, the steps in
  `REPRODUCIBILITY.md` rebuilt the long call table (`e3e43a02...`), the candidate table
  (`440f16bc...`) and the frozen prediction table (`3bc733c0...`), each byte-identical to the
  recorded digest.
* `scripts/reporting/build_canonical_numbers.py` gave 187 of the 188 canonical values identical
  to `docs/results/CANONICAL_NUMBERS.json`. The 188th, `values.source_file_sha256`, differs in 2
  of 34 entries: one source file was path-substituted at release, and for
  `docs/closure/EVIDENCE_ARCHIVE_VERIFICATION.json` the record holds the digest of an earlier
  version of that file. `make_tables.py` and `make_figures.py` reproduced the eleven table files
  and the eight figure source-data files byte for byte.
* The `QUICKSTART.md` commands ran as written in a copy of the repository: scorer tests 18
  passed and 1 skipped, parser self-test 19 of 19, builder fixtures 48 of 48 with a receipt
  byte-identical to `docs/evidence/P1.13_BUILDER_FIXTURES.json`.
* `scripts/reporting/claim_audit.py` and `claim_matrix.py` were run in a scratch copy laid out as
  the working repository, with the manuscript text that the audit checks (not public). The
  unchanged `claim_audit.py` reproduced the released `docs/results/CLAIM_AUDIT.tsv` and, through
  `claim_matrix.py`, the v1.0.0 matrix (57.5%), byte for byte. The corrected `claim_audit.py`
  gave `docs/results/CLAIM_TO_EVIDENCE_MATRIX.tsv` byte for byte (sha256 `9c695766...`) and the
  audit table now in `docs/results/CLAIM_AUDIT.tsv`, which differs from v1.0.0 only in the C27
  claim text (57.4%).

## Result of `scripts/release/release_check.py`

The checker scans the files git tracks, so it must run in a git clone. Outside a clone it scans
no text file and reports only the inventory hash and required-document checks. On a v1.1.0 clone
it reports 0 findings: every category is 0, `TOTAL FINDINGS: 0`, `VERDICT: PASS`. Any finding
it reports there is new.

It also lists, without counting them as findings, the frozen inventory files whose released
bytes differ from the recorded digest only by a documented release change: line endings or path
substitution, recorded in `docs/release/RELEASE_PATH_SUBSTITUTION.tsv`. The frozen inventory
keeps the digests from before the v1.0.0 build and is not edited.

Its personal-path check matches only `C:\Users\<name>` and `/home/<name>`, and only in the
top-level documents and `scripts/release/`. It does not report the absolute paths that frozen
files keep (next section).

## Known issues not fixed in v1.1.0

* The frozen scripts in `scripts/evaluation/` and `scripts/reporting/` use the working-repository
  layout (`docs/plans/`, `scripts/p1_12/`, `docs/manuscript/`). `REPRODUCIBILITY.md` gives the
  mapping and the steps that work.
* Importing `scripts/evaluation/freeze_v12.py` creates a directory at a default path unless
  `P112_FREEZE` is set.
* `scripts/evaluation/p113_builder_fixtures.py` without `--out` overwrites the tracked
  `docs/evidence/P1.11_BUILDER_FIXTURES.json`.
* `scripts/evaluation/p113_pairing_fixtures.py` writes its receipt to a hard-coded path of the
  execution host.
* Some frozen files keep absolute paths from the original workstation or the execution host,
  for example a default data path in `scripts/evaluation/freeze_v12.py`, the `canonical_path`
  column of `docs/closure/P113_CANONICAL_ARTEFACT_INVENTORY.tsv`, and `/data/trace-arg`, the
  default root of the frozen driver `scripts/parsers/frozen/parse_all.py`. They are frozen and
  not edited.
* `docs/results/CLAIM_AUDIT.tsv` row C27 keeps the manuscript's own wording (57.5%) in its
  anchor column by design, because that column quotes the manuscript. Its claim text says 57.4%,
  the correct value.
* The deposited `README.md` of the data deposit (version 1.0.0) keeps three statements that the
  record description corrected: "six genera" (there are five genera and six taxa), "all 19,320
  assembled contigs were aligned" (the 9,784 contigs of at least 1 kb were aligned), and "57.5%"
  (57.4%). Its `MANIFEST.sha256` covers the four archives only, and its paths carry a `parts/`
  prefix, so `sha256sum -c MANIFEST.sha256` fails unless the archives are placed in a folder
  named `parts/`. Files in a published Zenodo record can change only in a new version.
* The Dockerfiles of the panel images are not published. The image digests, package pins, git
  commits and database identities are.

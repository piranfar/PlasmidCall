# Release path substitution record

**Dated** 2026-09-28. Covers every file tracked at commit `e062dc0`, the public state before v1.1.0.
Author: Vahhab Piranfar, Independent Researcher, Jersey City, NJ, USA (ORCID 0000-0003-3653-5739).

## What the table is

`RELEASE_PATH_SUBSTITUTION.tsv` lists every file tracked at commit `e062dc0` whose released bytes
differ from its original, and every file the release build wrote itself: 115 of the 472 tracked
files. Each row gives the SHA-256 of the original bytes and of the released bytes, and says how the
two differ. The other 357 tracked files are byte-identical to their originals and are not listed.

The original is the file as the v1.0.0 build read it from the author's private working repository
on 2026-08-24. The released bytes are the file at commit `e062dc0`.

The v1.0.0 build (commit `5f746ed`) changed file bytes in two ways and did not record either:

1. It wrote every text file back with LF line endings. A file that had CRLF endings lost one byte
   per line. Binary files (the two `.pkl` models) were copied unchanged.
2. It replaced local path prefixes with neutral ones, by five rules applied in order.

It also moved files into a new layout (see below) and wrote seven files that have no original.

## Columns

| Column | Content |
|---|---|
| `path` | path in this repository |
| `original_sha256` | SHA-256 of the original bytes; `NA` for a file written by the release build |
| `released_sha256` | SHA-256 of the file at commit `e062dc0` |
| `difference_type` | one of the values below |
| `substitution` | what changed, with occurrence counts |
| `note` | records in this repository that hold the digest, and anything unusual |

| `difference_type` | Files | Meaning |
|---|---|---|
| `line_endings` | 34 | CRLF became LF; nothing else changed |
| `path_substitution` | 69 | path prefixes were replaced; nothing else changed |
| `path_substitution+line_endings` | 4 | both of the above |
| `other` | 1 | flagged: `docs/closure/PLASMIDCALL_EXECUTIVE_SUMMARY.md`, edited after v1.0.0 |
| `release_generated` | 7 | written by the release build; no original |

In total 108 files differ from their original. 107 of them differ only by line endings, path
substitution or both. The one exception is the flagged file. It was byte-identical to its original
at v1.0.0. Commit `aaa550f` then changed two sentences.

## Substitution tokens

The table names each replaced prefix by a token. The two execution-host prefixes are given here.
They were already public: the as-executed scripts in Part 1 of the data deposit (`env/`) hold them
unchanged. The Windows prefixes are withheld.

| Token | Original prefix | Replaced by | Occurrences | Files | Stands for |
|---|---|---|---|---|---|
| `HOST_ROOT` | `/mnt/tah/trace-arg` | `/work` | 158 | 53 | the project directory on the execution host |
| `HOST_MOUNT` | `/mnt/tah` | `/work` | 35 | 16 | the execution host's mount point alone |
| `WIN_PROJECTS[/]` | withheld | `<local>` | 9 | 8 | a drive letter and the local projects folder, with `/` |
| `WIN_PROJECTS[\]` | withheld | `<local>` | 3 | 3 | the same prefix, with `\` |
| `WIN_USER[/]` | withheld | `<local>` | 1 | 1 | a drive letter and a Windows user-profile folder, with `/` |
| `WIN_USER[\]` | withheld | `<local>` | 3 | 2 | the same prefix, with `\` |

The build applied `HOST_ROOT` first and `HOST_MOUNT` second. A fifth rule, for a shorter form of
the projects folder, matched nothing. In all, 73 files had at least one prefix replaced and 38
files lost CRLF endings.

Each `HOST_ROOT` replacement shortens a file by 13 bytes, and each `HOST_MOUNT` replacement by 3.
For example, `P1.13_ARCHIVE_NOTE.md` has 1,513 bytes originally and 1,500 released: one
`HOST_ROOT`.

In 13 files one token came from more than one source. There the `substitution` field adds the
order. `order of /work: RRML` lists every `/work` in the released file from the top: `R` is
`HOST_ROOT`, `M` is `HOST_MOUNT`, and `L` is a `/work` that was already in the original.
`order of <local>:` does the same with `U\`, `U/`, `P\`, `P/` and `L`, separated by spaces.

Of the 73 path-substituted files, 60 name only `HOST_ROOT` and `HOST_MOUNT`. The other 13 name a
Windows prefix.

## Layout changes

Frozen records name files by their original location. The build moved these:

| Original location | Released location |
|---|---|
| `scripts/p1_12/` | `scripts/pipeline/` |
| `scripts/p1_13/` | `scripts/evaluation/` |
| `scripts/p1_10/` | `scripts/model/` |
| `scripts/p1_9/` | `scripts/support/` |
| `scripts/manuscript/` | `scripts/reporting/` |
| `docs/plans/` | `docs/design/` |
| `docs/manuscript/tables/` | `docs/results/tables/` |
| `docs/manuscript/figures/source_data/` | `docs/results/figure_source_data/` |
| `docs/manuscript/supplementary_data/` | `docs/results/supplementary_data/` |
| `docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json` | `docs/results/CANONICAL_NUMBERS.json` |
| `docs/manuscript/PLASMIDCALL_CANONICAL_TABLES.json` | `docs/results/CANONICAL_TABLES.json` |
| `docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json` | `docs/results/ARG_CONTEXT_BIOLOGY.json` |
| `docs/manuscript/PLASMIDCALL_CLAIM_AUDIT.tsv` | `docs/results/CLAIM_AUDIT.tsv` |
| `docs/manuscript/PLASMIDCALL_CLAIM_TO_EVIDENCE_MATRIX.tsv` | `docs/results/CLAIM_TO_EVIDENCE_MATRIX.tsv` |
| `docs/manuscript/PLASMIDCALL_MANUSCRIPT_ASSET_INDEX.tsv` | `docs/results/ASSET_INDEX.tsv` |
| `docs/release/THIRD_PARTY_LICENSE_AND_REDISTRIBUTION_AUDIT.tsv` | `docs/release/THIRD_PARTY_LICENSE_AUDIT.tsv` |

Every other file kept its path. `scripts/release/release_check.py` holds the same map.

## How release_check.py uses this record

`scripts/release/release_check.py` compares files in the repository with
`docs/closure/P113_CANONICAL_ARTEFACT_INVENTORY.tsv`. The inventory holds the digests of the
original bytes. The checker does not take this record on trust.

For each inventory row it looks for the file at the recorded path, then at the released path
given by the layout map above. A row whose path is on the author's evidence store is checked
against a copy of the same name in `docs/evidence/P1.13_provenance/`, when one ships. If the
file's digest differs from the inventory, the checker reads the file's row in this table and
rebuilds the original bytes itself:

- `line_endings`: it turns every LF into CRLF.
- `path_substitution` or `path_substitution+line_endings` that names only `HOST_ROOT` and
  `HOST_MOUNT`: it puts the host prefix back in place of each `/work`, in the recorded order,
  and then turns LF into CRLF if the row also lists `CRLF->LF`.

The file passes only when the rebuilt bytes have the inventory digest and the row's
`original_sha256` is that same digest. The checker then lists it as a release change that was
reversed and matched. Anything else is a `hash_mismatch` finding: a file with no row, a row of
another type, a row that needs a Windows prefix, or rebuilt bytes with another digest.

On the v1.1.0 tree the inventory has 35 rows, and the checker reports no `hash_mismatch`:

- 21 match as released: 11 at the recorded path, 8 at the released path, and 2 as copies in
  `docs/evidence/P1.13_provenance/`.
- 9 match after the release change is reversed. They are listed below.
- 5 name files on the evidence store that have no copy in this repository. One of them,
  `PREDICTIONS_FROZEN.json`, has the same digest as
  `docs/evidence/P1.13_provenance/P1.13_PREDICTIONS_FROZEN_RECEIPT.json`, which the checker
  verifies under its own row.

| File | Inventory (original) | Released | Release change | Reversed by |
|---|---|---|---|---|
| `models/plasmidcall_v1.2-general/P1.12_V1.2_MODEL_PORTABLE.json` | `0fbb44c9...`, 13,110 bytes | `b2f00ee8...`, 12,247 bytes | CRLF to LF, 863 lines | LF to CRLF |
| `docs/evidence/P1.13_provenance/P1.13_DEPTH_COVARIATE.csv` | `9395a094...`, 7,191 bytes | `ebd7babd...`, 7,040 bytes | CRLF to LF, 151 lines | LF to CRLF |
| `docs/evidence/P1.13_provenance/P1.13_ARCHIVE_NOTE.md` | `6e8f72f8...`, 1,513 bytes | `420a9f57...`, 1,500 bytes | one `HOST_ROOT` | `/work` to `/mnt/tah/trace-arg` |
| `docs/evidence/P1.13_provenance/P1.13_builder_validation.json` | `fd12f228...`, 21,191 bytes | `03f13c09...`, 20,055 bytes | CRLF to LF, 1,136 lines | LF to CRLF |
| `docs/design/P1.13_AMENDMENT_004.yaml` | `dd3847db...`, 20,222 bytes | `f0b90c33...`, 20,219 bytes | one `HOST_MOUNT` | `/work` to `/mnt/tah` |
| `scripts/evaluation/freeze_v12.py` | `15db49b2...`, 17,950 bytes | `dbcdd951...`, 17,584 bytes | CRLF to LF, 366 lines | LF to CRLF |
| `scripts/evaluation/p113_run.sh` | `620d3e6b...`, 12,772 bytes | `d76170a3...`, 12,747 bytes | one `HOST_ROOT` and four `HOST_MOUNT`, order `RMMMM` | each `/work` to its prefix |
| `scripts/evaluation/p113_assembly_accept.py` | `d32f5442...`, 10,072 bytes | `5bbdd5fd...`, 10,059 bytes | one `HOST_ROOT` | `/work` to `/mnt/tah/trace-arg` |
| `scripts/evaluation/p113_asm_reconcile.py` | `9f036d71...`, 7,207 bytes | `acac03d4...`, 7,194 bytes | one `HOST_ROOT` | `/work` to `/mnt/tah/trace-arg` |

The first three sit at the path the inventory records. The inventory names
`P1.13_builder_validation.json` on the evidence store, and it names the other five by their
original location (`docs/plans/`, `scripts/p1_13/`). `freeze_v12.py` ships twice, in
`scripts/pipeline/` and `scripts/evaluation/`, with the same bytes.

For `P1.12_V1.2_MODEL_PORTABLE.json`, `docs/evidence/P1.11_PRE_JOIN_HASH_RECEIPT_v2.json` records
both forms: `sha256_worktree` is the original CRLF digest and `sha256_canonical_lf` is the released
digest. The CRLF digests in `docs/evidence/P1.12_PRE_JOIN_HASH_RECEIPT.md` are also digests of the
original CRLF files.

If any of these files changes, the rebuilt bytes no longer have the inventory digest, and the
checker reports a `hash_mismatch`. Writing the new digest into this table does not change that.

## No frozen value changed

No frozen file was edited to make this record, and no digest in any frozen record was changed.
Frozen records keep the digests of the original bytes. This table adds the link from each of those
digests to the released bytes.

Of the 108 files that differ, 54 have their original digest in at least one record in this
repository. Counted in files of this repository, the records that hold the most are
`docs/evidence/P1.12_PRE_JOIN_HASH_RECEIPT.md` (19 files),
`docs/evidence/P1.11_PRE_JOIN_HASH_RECEIPT_v2.json` (12),
`docs/closure/P113_CANONICAL_ARTEFACT_INVENTORY.tsv` (10),
`docs/evidence/P1.11_PREFLIGHT_SUPERSESSION_MANIFEST.json` (9) and
`docs/closure/MANUSCRIPT_PHASE_DELTA_MANIFEST.tsv` (7). The `note` column names the records for
each file.

## How to verify

Check out commit `e062dc0`, or read a file with `git show e062dc0:<path>`. A file changed in v1.1.0
or later no longer matches `released_sha256`.

1. A tracked file not in the table is byte-identical to its original. Where a record in this
   repository holds its digest, `sha256sum <path>` matches that record. One exception is known;
   see Limits.
2. `line_endings`: turn every LF into CRLF and hash the result. It equals `original_sha256`.

   ```
   python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read().replace(b'\n', b'\r\n')).hexdigest())" <path>
   ```

   Every original that had CRLF used it on every line, so this reversal is exact. Anyone can run
   this check.
3. `path_substitution` and `path_substitution+line_endings`: replace each token in the released
   text with its original prefix. Where an `order of` field is present, walk the token's
   occurrences from the top and apply the listed source to each, leaving `L` unchanged. Otherwise
   every occurrence of the token has the one listed source, and the count must match. If the field
   also lists `CRLF->LF`, turn every LF into CRLF. Hash the result. Anyone can run this check for
   the 60 files that name only `HOST_ROOT` and `HOST_MOUNT`, with the prefixes given above. For a
   file with one token and no `order of` field, one line is enough:

   ```
   python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read().replace(b'/work', b'/mnt/tah/trace-arg')).hexdigest())" docs/evidence/P1.13_provenance/P1.13_ARCHIVE_NOTE.md
   ```

   This prints `6e8f72f8...`, the digest in the inventory. Use `b'/mnt/tah'` for a `HOST_MOUNT`
   row. The 13 files that name a Windows prefix need the withheld prefix, so only the author can
   check them.
4. `other`: `git show 5f746ed:docs/closure/PLASMIDCALL_EXECUTIVE_SUMMARY.md | sha256sum` equals
   `original_sha256`. `git diff 5f746ed e062dc0 -- docs/closure/PLASMIDCALL_EXECUTIVE_SUMMARY.md`
   shows the later edit.
5. `release_generated`: there is no original to compare.

The author ran steps 1 to 3 on 2026-09-28 against the originals, with every prefix. All 107
reversible rows matched `original_sha256`, and the 357 unlisted files matched their originals byte
for byte. None failed. The other 8 rows cannot be reversed by design. Steps 2 and 3 were then run
again on the files at `e062dc0` with only the public host prefixes: the 34 `line_endings` rows and
the 60 host-only rows all matched `original_sha256`.

## Limits

- For 37 files the original is the working repository's commit from the build day, because those
  files changed there later. Two are in the table (`scripts/reporting/number_references.py` and
  `scripts/reporting/write_zenodo_metadata.py`); 35 are unlisted identical files. For 35 of the 37
  the same digest is in `docs/closure/MANUSCRIPT_PHASE_DELTA_MANIFEST.tsv`. For
  `scripts/reporting/make_preprint.py` and `scripts/reporting/write_zenodo_metadata.py` no record
  holds the digest, so the line endings of the copy the build read cannot be confirmed
  independently.
- `docs/closure/OFF_SERVER_VERIFICATION.json` is not in the table: the build did not change it.
  `docs/closure/MANUSCRIPT_PHASE_DELTA_MANIFEST.tsv` records it under the same path and size,
  8,108 bytes, but with another digest (`4490a0b5...`; the file is `10fbd622...`). No record in
  this repository explains the difference, so step 1 fails for this file, and its digest cannot be
  tied to that record.
- Step 3 for the 13 files that name a Windows prefix depends on the withheld prefixes.
- The table records only what the five rules and the line-ending rewrite changed.

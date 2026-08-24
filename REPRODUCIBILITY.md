# Reproducibility guide

This project distinguishes three things that are often conflated:

| Level | Meaning | Status |
|---|---|---|
| **Preserved evidence** | artefacts recording what actually ran; never regenerated | frozen, hash-bound |
| **Deterministically regenerable** | rebuild from preserved inputs reproduces byte-identical output | demonstrated at three levels |
| **Re-executable** | rerun the whole pipeline from raw reads | possible, but needs the pinned images and ~30 CPU-hours |

## What is proven deterministic

1. **Parsing** — 231,841 rows, byte-identical across two independent passes.
2. **Candidate construction** — byte-identical on rebuild; verified again at freeze time, and once
   more by an independently written projection of the frozen table.
3. **Assembly** — 4/4 predeclared rerun pilots byte-identical, so Unicycler/SPAdes is reproducible
   on these inputs at fixed thread count.

## Reproducing the frozen predictions from preserved inputs

Requires the analysis environment in `INSTALLATION.md` §1 and the preserved `assemblies/`,
`inference/` and `annotation/` trees from the evidence archive.

```bash
python scripts/p1_13/p113_candidate_pipeline.py --root <evidence root> --outdir <out>
```

Expected: candidate table sha256
`440f16bc7002c15135ac73a233545613ad6869eddf7d421cca6dc0a1060114f8`, coverage gate PASS at 1.0000
for v1.2-General, v1.1 and the router, deterministic rebuild identical.

```bash
python scripts/p1_13/p113_freeze_predictions.py \
  --candidate-dir <out> --root <evidence root> --out <frozen>
```

Without `--commit` this is a full dry run that writes nothing and re-verifies every gate.

**If your hashes differ**, check the analysis environment first (§1 of `INSTALLATION.md`):
pickle and float serialisation are version-sensitive. A hash difference is a real signal, not
noise — investigate rather than proceeding.

## Re-executing the panel from raw reads

1. Retrieve reads by run accession from ENA; verify against `P1.13_READS_MANIFEST.sha256` and the
   per-file MD5s in the cohort table.
2. Obtain the pinned images by digest (`SOFTWARE_AND_DATABASE_VERSIONS.tsv`). Images carrying
   third-party databases are **not** redistributed; build or pull them per their own licences.
3. Run `scripts/p1_13/p113_run.sh`. It is fail-closed throughout: it refuses to start on a cohort
   hash change, halts before breaching free-space reserves, validates read pairing exactly,
   enforces the 30× floor, and accepts an assembly only through the atomic gate.

Expect roughly 30 CPU-hours for the panel plus assembly time.

## What cannot be reproduced from this repository alone

* Raw reads (public ENA data, not redistributed — retrievable by accession).
* Tool databases (third-party, redistribution restricted — recipes and digests provided).
* Truth (never acquired; not part of any released artefact at this time).

## Fixtures

`python scripts/p1_13/p113_builder_fixtures.py` → 48/48, no bulk data needed. One fixture asserts
that no truth field or reference-derived contig label is consumed by the builder.

---

## Reproducing the manuscript, figures and tables

Every number in the manuscript is generated from the frozen tables by versioned code. The pipeline
below is deterministic and fails closed at each step.

| Step | Script | What it does |
|---|---|---|
| 1 | `scripts/manuscript/build_canonical_numbers.py` | reads the frozen result and post-freeze tables and emits `docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json`, recording for every value the source file and field it came from, plus a SHA-256 of each source |
| 2 | `scripts/manuscript/make_tables.py` | builds the four main tables and registers every printed value in `PLASMIDCALL_CANONICAL_TABLES.json`; asserts that the per-taxon totals reconcile to the frozen denominators |
| 3 | `scripts/manuscript/make_figures.py` | regenerates all seven figures as editable SVG, publication PDF and 600 dpi PNG, with a machine-readable source-data table and a checksum manifest |
| 4 | `scripts/manuscript/make_supplementary.py` | assembles the Supplementary Information and the nine Supplementary Data files |
| 5 | `scripts/manuscript/build_references.py` | emits the reference list, BibTeX, RIS and the per-field verification table |
| 6 | `scripts/manuscript/number_references.py` | assigns reference numbers strictly in order of first appearance and fails closed on an unknown key or an uncited entry |
| 7 | `scripts/manuscript/verify_manuscript.py` | checks the journal's structural rules, that every numeric literal resolves to a canonical source, that no superseded wording appears, and that reference numbering is complete |
| 8 | `scripts/manuscript/claim_audit.py` | enumerates every material claim with its source, denominator, estimate, interval and status, and verifies each claim's verbatim anchor is present in the manuscript |
| 9 | `scripts/manuscript/render_documents.py` | renders DOCX and PDF for the journal and preprint packages |

Run them in order from the repository root. Step 7 exits non-zero on any violation, so it is safe
to use as a gate in CI.

**What is not reproducible from this repository alone.** The raw sequencing reads are public but
not redistributed here; they are retrievable by the accessions and MD5 checksums in Supplementary
Data 1. The classifier container images bundle third-party databases whose licences do not permit
redistribution; immutable image digests and build recipes are provided instead.

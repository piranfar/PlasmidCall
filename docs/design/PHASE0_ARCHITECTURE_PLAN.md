# Phase 0 Architecture Plan — AMR Evidence Warehouse

**Status:** DRAFT — revision 4. Not approved, not implemented, not committed.
**Date drafted:** 2026-08-15. **Revised:** 2026-08-16 (rev. 2), 2026-08-16 (rev. 3, independent-review defects), 2026-08-16 (rev. 4, storage-state / D3 boundary / baseline note).
**Open design questions:** **27 total — 5 OPEN (Q13, Q24, Q25, Q26, Q27), 22 RESOLVED IN PROPOSAL** (`DATA_MODEL_PROPOSAL.md` §22).
**Assumed minimum PostgreSQL version:** **15** — see `DATA_MODEL_PROPOSAL.md` §19.2 and decision D9.
**Repository:** `amr-evidence-warehouse`, branch `main`, at commit `f7e42eb`.
**Repository visibility:** **PRIVATE** — decision **D1 resolved 2026-08-16** (option (a), make private). This is the only decision with owner approval.
**Governing documents:** [`AGENTS.md`](../../AGENTS.md), [`docs/PROJECT_GOVERNANCE.md`](../PROJECT_GOVERNANCE.md).
**Companion drafts:** [`docs/LEGACY_SOURCE_INVENTORY.md`](../LEGACY_SOURCE_INVENTORY.md), [`docs/DATA_MODEL_PROPOSAL.md`](../DATA_MODEL_PROPOSAL.md).

This document defines *what will be built* and *what must be decided first*. It does not implement anything. No database exists. No data have been copied.

**Cross-reference convention.** Internal references use **section identifiers** (§9.2) and **stable decision/criterion/stop identifiers** (D3, A8, S11). Line numbers are not used as internal references, because they are invalidated by every edit. Line-number citations to *external* files are retained where they point at a specific sentence in an unchanging governance document.

---

## 0. Evidence labels and status markers

`CONFIRMED` · `SUPPORTED BUT INCOMPLETE` · `NOT DOCUMENTED` · `CONTRADICTED` · `CANNOT DETERMINE`

Applied to statements about the legacy estate. Design content carries one of:

- `PROPOSED` — a design position in this draft, not approved.
- `PROPOSED — OWNER APPROVAL PENDING` — a recommended decision outcome (§12).
- `APPROVED` — used **only** for D1.
- `FUTURE PHASE — NOT AUTHORIZED` — architecture recorded for planning; explicitly not enabled (§18, §19, §20).

---

## 1. Phase 0 scope

### 1.1 In scope

| # | Workstream | Output |
|---|---|---|
| S1 | Architecture specification | This document |
| S2 | Legacy source inventory | `docs/LEGACY_SOURCE_INVENTORY.md` |
| S3 | Normalized evidence data model | `docs/DATA_MODEL_PROPOSAL.md` |
| S4 | Versioned schema + migrations | `db/migrations/` (Phase 0C) |
| S5 | Controlled ingestion of legacy artifacts | Raw + staging + evidence layers populated with receipts |
| S6 | Reconciliation of conflicting legacy artifacts | Conflict register, not silent resolution |
| S7 | Eligibility contract engine | `contracts/<name>/v<N>/` evaluated against evidence |
| S8 | Cohort snapshot generator | Immutable, hashed, receipted exports |
| S9 | Test and validation harness | Schema, invariant, reconciliation, and round-trip tests |
| S10 | Phase 0 completion demonstration | `PROJECT_GOVERNANCE.md` §13 criterion satisfied |

### 1.2 Explicitly out of scope for Phase 0

Out of scope, and prohibited until a later phase is authorized:

- Training, fitting, tuning, scoring, or re-running Model 1 or Model 2. (`AGENTS.md:15`)
- Any modification to `mobility-aware-amr-mic-private` worktrees or to `mobility-aware-amr-emergence`. (`PROJECT_GOVERNANCE.md:186`)
- New literature searches, new NCBI queries, new downloads, new author contact.
- Continuous or scheduled evidence discovery of any kind (§19).
- Installing or running GROBID, OCR, or any document-parsing tool (§20).
- Building a public website, public API, or public release (§18).
- Creating or enabling any GitHub Actions workflow (§21).
- Changing any scientific eligibility criterion of Model 1 or Model 2.
- Publishing or pushing.
- Deciding *which* of two conflicting legacy artifacts is scientifically correct. Phase 0 records the conflict; adjudication is a separate authorized task.
- Reproducing or storing publisher full text, sequence data, or any artifact whose rights decision does not permit it (§11.2).

**Note on visibility.** Changing repository visibility was previously listed here as out of scope. D1 was subsequently authorized and executed as a single narrowly scoped operation. Visibility is now **PRIVATE** and is not to be revisited. Further visibility changes remain out of scope.

### 1.3 What Phase 0 is *not* allowed to conclude

Phase 0 must not conclude that data are scarce, that a search was exhaustive, that a determinant is absent, or that an exclusion was correct. Those are Phase 1+ scientific questions and require evidence Phase 0 is explicitly not gathering. (`PROJECT_GOVERNANCE.md:11`, `:153`, `:170`, `:217`)

**Corollary added in revision 2.** The absence of a file, a row, or a record in the legacy estate is a fact about the *estate*, never about biology or about the literature. An unfound artifact is `NOT DOCUMENTED` or `CANNOT DETERMINE`, never "absent".

---

## 2. Milestones and dependencies

```
0A  Architecture + inventory + data model        (this deliverable, revision 2)
     │  D1 APPROVED. D2–D11 pending.
     ▼
0B  Contract formalisation
     - eligibility contract file format
     - controlled vocabulary registry
     - conflict taxonomy
     - rights-decision taxonomy (§11.2)
     - locator-type registry and per-contract locator requirements
     │
     ▼
0C  Schema implementation
     - SQL migrations, empty database, tests green, no data
     │  blocked by: D9
     ▼
0D  Raw layer capture (read-only from source repos)
     - content-addressed capture of permitted artifact classes
     - capture receipts; NO parsing, NO interpretation
     │  blocked by: D3 (scoped, per artifact class), D4, D6, D7, D9
     ▼
0E  Staging layer
     - parse each raw artifact to typed rows, preserving raw source fragments
     │  blocked by: D11
     ▼
0F  Evidence layer
     - normalize into the entity model
     - identity resolution as *assertions*, not merges
     - conflict detection and registration
     │  RAG component blocked by: D10 (proposed: defer)
     ▼
0G  Reconciliation
     - reconcile across artifacts, branches, and the two model programs
     - produce reconciliation report; do NOT resolve silently
     │  adjudication step blocked by: D5
     ▼
0H  Eligibility layer
     - encode Model 1 primary/secondary and Model 2 v1/v2 as contracts
     - evaluate against evidence; reconcile against historical decisions
     │  blocked by: D8
     ▼
0I  Cohort layer
     - regenerate legacy cohorts; reconcile per A8
     ▼
0J  Completion demonstration (PROJECT_GOVERNANCE.md §13)
```

**Hard dependencies.** 0C depends on 0A approval and D9. 0D depends on scoped D3 authorization *and* a rights decision for each artifact class (§11.2) — these are independent gates, see §12.1. 0F depends on the conflict taxonomy from 0B. 0I depends on 0G. 0J depends on everything.

**Future phases, not scheduled and not authorized:** public release architecture (§18), continuous ingestion (§19), GROBID parsing (§20).

---

## 3. Acceptance criteria

Phase 0 is complete when **all** of the following hold. Each is a test, not an opinion.

| ID | Criterion | Verification |
|---|---|---|
| A1 | Every captured legacy artifact has a raw-layer record with source repository/worktree, branch, HEAD-at-capture, path, SHA-256, byte size, capture timestamp, provenance class, and a capture receipt | `source_file` completeness query; zero rows with NULL in any of those columns |
| A2 | No raw artifact was modified after capture | Re-hash every raw object; compare to the **external** integrity baseline (§7.5), not to a regenerable in-database manifest |
| A3 | Every evidence assertion has at least one locator, or a registered provenance defect | See A3 strategy, §3.1 |
| A4 | Original bytes are preserved in the raw object where storage is authorized; every phenotype observation carries a verbatim Unicode fragment plus a hash-and-locator anchor, and preserves method, platform, standard, value, sign, unit, bounds, and censoring separately | See A4 strategy, §3.2 |
| A5 | No S/I/R, disk zone, Etest, VITEK, or agar-dilution value was written into a BMD MIC field, and no modality was converted into a BMD MIC | Modality-partition invariant test; see `DATA_MODEL_PROPOSAL.md` §5 |
| A6 | Missing / not-searched / searched-and-absent / failed / insufficient-quality / ambiguous / conflicting / not-applicable are distinct stored states | Enumeration coverage test over every `observation_status` column |
| A7 | Every conflicting artifact pair or set is registered as a `conflict` row; none was silently dropped | Reconciliation report count = conflict table count, per class |
| A8 | Each legacy cohort is reconciled at seven defined levels with a defined outcome per level | See A8 protocol, §3.3 |
| A9 | Every A8 outcome other than `exact_match` has a written cause | Reconciliation report completeness check |
| A10 | A new eligibility contract, written after ingestion, produces a new cohort with no new search and no raw-data modification | The `PROJECT_GOVERNANCE.md:239` criterion |
| A11 | No genome, publisher full text, credential, or rights-restricted artifact is tracked in Git, and no artifact exceeding the size policy is tracked | Pre-commit check + release-readiness script |
| A12 | Model 1 and Model 2 legacy outputs are stored as *model outputs*, never as source evidence | Type constraint; no evidence-layer view exposes them |
| A13 | **Both directions** of registry integrity hold: every reference resolves to a registered entity (schema-enforced), **and** every referenced registry row has exactly one correctly typed concrete child (trigger- and audit-enforced) | Constraint inspection **plus** negative tests A13-N1…N5 **plus** a zero-row membership audit (§7.6) |
| A14 | No evidence row was ever updated after insert | Append-only enforcement test: no `UPDATE` grant on evidence tables; supersession is a separate relation (§7.4) |

### 3.1 A3 strategy — enforceable locator coverage

**The previous formulation was wrong.** It read *"FK constraint + `NOT NULL` on provenance"*. That does not work: locators live in a separate relation (`provenance_locator`), so a `NOT NULL` foreign key on `provenance` proves an assertion has a *provenance record*, not that the provenance record has *at least one locator*. A one-to-many cardinality minimum of 1 is not expressible as a column constraint in PostgreSQL.

`PROPOSED` — three mechanisms in combination:

1. **Deferred-constraint transaction discipline.** Assertion, provenance, and at least one locator are written in one transaction. A `DEFERRABLE INITIALLY DEFERRED` constraint trigger fires at `COMMIT` and rejects any `provenance` row with zero `provenance_locator` children. This makes a locator-less assertion **non-committable**, not merely discouraged.
2. **Explicit defect escape hatch.** Where a source genuinely offers no locator, the writer must insert a `provenance_defect` row (`defect_type='no_locator_available'`, with a reason). The deferred trigger accepts *either* ≥1 locator *or* ≥1 registered defect — never neither. This preserves the estate's real situation (decisions recorded without primary locators) as **visible and countable** rather than silently absent.
3. **Acceptance test.** `A3-T1`: for every assertion table, `COUNT(*)` where the entity has neither a locator nor a defect **must be 0**, run as a full-table audit at the end of each ingestion phase. `A3-T2`: a negative test attempts to commit a locator-less, defect-less assertion and **must fail**.

**Reported metric, not just a pass/fail:** the ratio of assertions carrying a real locator to those carrying a defect is a headline number in every ingestion receipt. A run that passes A3 entirely by registering defects has passed the test and failed the intent, and the receipt must make that visible.

### 3.2 A4 strategy — preservation, not reconstruction

**The previous formulation was wrong.** It read *"Round-trip test: reconstruct the source cell string from stored fields"*. Reconstruction is not preservation. A round-trip test proves the parser is invertible for the cases tested; it does not preserve whitespace, Unicode form, footnote markers, trailing annotations, or anything the parser did not model. If the parser is wrong, reconstruction reproduces the parser's belief, not the source.

`PROPOSED`:

1. **Original source bytes are preserved immutably in the raw object** — in the content-addressed object store under object lock — **when storage is authorized** (rights, §11.2; and D3 for capture). This, not any database column, is what "preservation" means.
2. **The observation is anchored by source hash plus a typed locator.** `source_file.sha256` identifies the bytes; `provenance_locator` identifies the cell, row, node, or region within them. Together they make the fragment re-readable from the original bytes independently of any parse.
3. **`raw_cell_text` is a verbatim Unicode representation**, mandatory and immutable — the source fragment as decoded, with `≤`, `*`, footnote markers, and trailing annotations retained, none stripped or normalised. `NOT NULL`, no `UPDATE` grant.
4. **Byte-level verification is performed against the raw object, never against the `TEXT` column.** A PostgreSQL `TEXT` column is not byte-preserving: encoding, byte-order marks, Unicode normalisation form, and line endings are all lost or normalised in the decode, and two different byte sequences can decode to identical text. Any claim about bytes is tested by re-hashing the object against the capture receipt in the external baseline (§7.5).
5. **Reference-only sources cannot claim a byte-level round trip.** Where `current_storage_state.status = 'reference_only'` — publisher PDFs, genome payloads, git-ignored raw trees — the Warehouse holds a declared hash, size, and locator but not the bytes. Byte-level verification is possible **only while the referenced bytes remain available and hash-verifiable at their external location**; once an `unavailable` event is appended (external referent unreachable) or a `lost` event is appended (our own object missing or failing re-hash), any prior byte-level claim becomes unverifiable and must be reported as such, not assumed to still hold. Storage state is derived from the append-only `storage_status_event` relation (`DATA_MODEL_PROPOSAL.md` §4.2.1); no field is ever rewritten.
6. **Round-trip is an additional test, not the criterion.** `A4-T1`: parse → fields → re-render must equal `raw_cell_text` for every fixture; a mismatch is a parser defect to fix or an artifact to quarantine (stop condition S6). `A4-T2`: `raw_cell_text` is never NULL and never equals a normalised value where the source differed. `A4-T3`: for every artifact whose `current_storage_state.status = 'stored'`, re-hashing the raw object matches the capture receipt; a mismatch appends a `lost` (or `quarantined`) storage event and raises stop condition **S2** rather than rewriting anything.
7. **Atomic field preservation** is verified separately: method, platform, standard, standard version, value, sign, unit, lower bound, upper bound, bound inclusivity, censoring type, replicate, and locator each occupy their own column (`DATA_MODEL_PROPOSAL.md` §5).

### 3.3 A8 protocol — reconciliation at seven levels

**The previous formulation was vague** (*"reconciles… at row, isolate, study, drug, and censoring-class counts"* — "reconcile" undefined). Replaced with explicit levels and explicit permitted outcomes.

**Levels.** Every legacy cohort regeneration is reconciled at all seven:

| L | Level | Compared |
|---|---|---|
| L1 | **Artifact** | Regenerated export vs legacy export: SHA-256, byte size, row count, column set |
| L2 | **Study** | Set of study identifiers present; symmetric difference enumerated |
| L3 | **Isolate** | Set of isolate identities present; symmetric difference enumerated |
| L4 | **Observation** | Set of individual measurements present, keyed on (isolate, drug, assay, source locator); symmetric difference enumerated |
| L5 | **Drug** | Set of drugs and per-drug observation counts |
| L6 | **Censoring class** | Counts by `exact` / `left` / `right` / `interval` / `not_applicable` |
| L7 | **Cohort membership** | The admitted/held/excluded partition, per record, with reason codes |

**Permitted outcomes per level** — one of exactly four, recorded explicitly:

| Outcome | Meaning | Requires |
|---|---|---|
| `exact_match` | Identical at this level | Nothing further |
| `explained_difference` | Differs, and the cause is identified and written | A named cause, a locator, and a statement of which side is correct *or* that both are defensible |
| `registered_legacy_defect` | Differs because the legacy artifact has a defect (duplicate columns, silent overwrite, near-duplicate ambiguity) | A `conflict` or `schema_defect` row; the legacy artifact is **not** corrected |
| `cannot_determine` | Differs and the cause is not establishable from available evidence | An explicit statement of what evidence would be needed |

**`cannot_determine` is a permitted outcome, not a failure.** Forcing every difference into an explanation would manufacture false causes. A8 passes when every level of every cohort has a recorded outcome and A9 is satisfied for all non-`exact_match` outcomes.

**A8 caveat, retained.** Exact byte-level reproduction of legacy cohorts is *not* expected. Legacy cohorts were produced by scripts with their own environments. L1 `exact_match` is a bonus; L4 and L7 are the levels that matter scientifically.

---

## 4. Proposed directory structure

`PROPOSED`. Nothing below exists yet.

```
amr-evidence-warehouse/
├── AGENTS.md
├── README.md
├── LICENSE                          # decision D2 — future release only
├── COPYRIGHT.md
├── DATA_RIGHTS.md                   # rights boundary; supersedes a simple DATA_LICENSE
├── docs/
│   ├── PROJECT_GOVERNANCE.md
│   ├── LEGACY_SOURCE_INVENTORY.md
│   ├── DATA_MODEL_PROPOSAL.md
│   ├── CONFLICT_REGISTER.md         # 0G output
│   ├── RECONCILIATION_REPORT.md     # 0G/0I output, structured per A8 levels
│   ├── PROVENANCE_DEFECT_REGISTER.md
│   └── plans/
│       └── PHASE0_ARCHITECTURE_PLAN.md
├── contracts/                       # versioned eligibility contracts; append-only
│   ├── model1_primary/v1/
│   ├── model1_secondary/v1/
│   ├── model2_assay_aware/v1/
│   └── model2_assay_aware/v2/
├── rights/                          # rights decisions per source and artifact class
├── db/
│   ├── migrations/                  # forward-only, numbered
│   ├── views/                       # current-state views built on NOT EXISTS (§7.4)
│   └── seeds/                       # controlled vocabularies only
├── ingest/
│   ├── capture/                     # fetch-and-hash; no parsing
│   ├── staging/                     # per-source-format parsers
│   └── evidence/                    # normalizers into the entity model
├── reconcile/
├── eligibility/
├── cohorts/
├── integrity/                       # external baseline tooling (§7.5)
├── tests/
│   ├── schema/ · invariants/ · reconciliation/ · fixtures/
├── manifests/                       # signed manifests + capture receipts (tracked)
└── tools/
    └── check_release_readiness.py
```

**Not in Git, by design** (`PROJECT_GOVERNANCE.md:117`):

```
warehouse_store/
├── raw/<sha256[0:2]>/<sha256>          # content-addressed, object-lock protected
├── parquet/<table>/<snapshot_id>/      # analytical projections
└── vector/<index_version>/             # RAG index (deferred, D10)
```

Deferred, documented in §18–§20 but **not created in Phase 0**: `release/`, `pipeline/`, `parsers/grobid/`, `.github/workflows/`.

---

## 5. The five evidence layers

Per `PROJECT_GOVERNANCE.md:99-105`.

### 5.1 Raw
Byte-identical captures, addressed by SHA-256. **Immutable, write-once.** A correction is a new object. Stored in the object store under object-lock or equivalent (§7.5), never in Git, never in PostgreSQL. PostgreSQL holds the `source_file` metadata row. Contains no interpretation.

### 5.2 Staging
Typed rows parsed from raw objects, each retaining its **raw source fragment** alongside any parsed value (A4). A parse never destroys information. `">8"` retains `raw_cell_text=">8"` plus parsed sign and value; `"8-16"` is a range, never a point. Every coercion failure becomes a `staging_warning` row. Rebuildable from raw; a parser fix creates a new staging version with its own receipt.

### 5.3 Evidence
Normalized facts and assertions with provenance. Facts are stored *without* reference to any analysis — no "excluded" flag, no "primary" flag. Identifiers are never merged (§7.6). Disagreements produce `conflict` rows. **Strictly append-only:** no `UPDATE`, no `DELETE`. Corrections are new assertions plus an append-only supersession record (§7.4).

### 5.4 Eligibility
Evaluations of a versioned contract against evidence at a database snapshot. Derived and reproducible, never authored. The same observation carries many evaluations — one per contract version — and a record refused by one contract and admitted by another is normal.

### 5.5 Cohorts
Immutable, hashed snapshots with full receipts per `PROJECT_GOVERNANCE.md:190-200`. Never manually edited. Parquet in the object store; manifest and receipt in Git. Regenerable from (contract version, snapshot id, generator version).

**Layer boundary invariant.** Information flows raw → staging → evidence → eligibility → cohorts and never backwards. No process may write to a lower layer based on a higher-layer conclusion. A cohort build that "fixes" an MIC value is a defect, not a convenience.

---

## 6. Storage responsibilities

| Concern | Technology | Rationale | Not used for |
|---|---|---|---|
| Canonical structured evidence, assertions, provenance, conflicts, evaluations | **PostgreSQL** | Referential integrity; constraint enforcement of governance invariants | Large blobs, sequence, full text, oversized JSONB |
| Immutable raw artifacts, genomes, publisher files, large tables | **Object storage, content-addressed, object-lock** | Automatic deduplication; external integrity baseline | Anything requiring query or join |
| Analytical projections, cohort snapshots, wide feature tables | **Parquet** | Columnar, typed, reproducible from the database | The authoritative record — always derived |
| Document retrieval for candidate extraction | **Vector index** (deferred, D10) | Locating passages | Ground truth |
| Code, schema, contracts, tests, manifests, receipts, rights decisions | **Git** | Review, history, diff, and an immutable receipt anchor (§7.5) | Genomes, publisher full text, credentials, large raw data |

### 6.1 Sizing evidence

`CONFIRMED` measurements from the inventory: largest single legacy artifact 14,233,173 bytes (12,843 rows); 18 tracked files over 1 MB in the Model 1 estate; git-excluded raw trees declared at 26 GB + 1.1 GB (`SUPPORTED BUT INCOMPLETE` — declared, not measured).

**These are current-estate figures and must not be read as the design target.** See §17 for the scale the model is designed to.

### 6.2 RAG responsibilities and boundary

RAG is confined to **candidate generation**. Required flow (`PROJECT_GOVERNANCE.md:125`):

```
retrieval → candidate extraction → exact locator → validation → accepted | conflicting | unresolved assertion
```

A RAG-derived assertion enters evidence only with `extraction_method='rag'`, a resolvable typed locator (§7.7), and `verification_state='unverified'`. Promotion to `verified` requires re-reading the raw object at the locator. Similarity score is stored as diagnostic metadata and **never** used in an eligibility predicate. The index is derived and disposable.

`PROPOSED` per D10: **defer RAG implementation beyond Phase 0.**

---

## 7. Provenance, integrity, and referential design

### 7.1 Content addressing

Every raw artifact is stored under its SHA-256. The same bytes reachable from four branches yield **one** stored object and **four** `source_file` rows. `recovered_literature_expansion_v8.tsv` (`sha256=bd7d82a7…5e62d`, 155,331 B, `CONFIRMED` by direct computation in two locations) is thereby represented as one object shared by two model programs, rather than as an accidental duplicate.

### 7.2 The provenance chain

```
assertion
  └── provenance (extraction method, tool version, date, extractor identity, verification state)
        └── provenance_locator  (1..n, typed — §7.7)     ⎫ at least one of these
        └── provenance_defect   (0..n, registered)        ⎭ two branches must exist (A3)
              └── source_file (sha256, bytes, media type, capture context)
                    └── source (repository/worktree | DOI/PMID | API endpoint | manual entry)
```

### 7.3 Why the legacy estate forces this

Two observed failures make a weaker design unacceptable:

1. **Manifest-refreeze laundering** (`CONFIRMED`). A committed result artifact was overwritten, the overwrite was committed, and the integrity manifest was then regenerated over the corrupted file — so the manifest verified the corruption against itself. The source's own finding: *"A regenerable integrity record cannot detect a change that was baked in before it was regenerated."* → §7.5.
2. **Exclusions without primary locators** (`SUPPORTED BUT INCOMPLETE`). Reported in an unprovenanced working file; the underlying receipt exists but was not independently opened. → A3's defect register makes this state explicit rather than invisible.

### 7.4 Genuine append-only supersession

**The previous design was wrong.** It required setting `superseded_by_amendment_id` on the superseded row — an `UPDATE` to an allegedly immutable row. A table that must be updated to record supersession is not append-only.

`PROPOSED` — supersession is a **separate append-only relation**:

```
assertion_supersession(
    supersession_id,
    superseded_entity_id     FK → evidence_entity,      -- what is being superseded
    superseding_entity_id    FK → evidence_entity NULL, -- NULL for pure withdrawal/retraction
    supersession_type        enum,
    reason                   NOT NULL,
    evidence_provenance_id   FK NULL,
    authorised_by            NOT NULL,
    created_at               NOT NULL
)
```

Nothing in the original assertion is ever written again.

**Reversal — the revision 2 defect, corrected.** Revision 2 claimed an erroneous supersession could be reversed by "a supersession of the supersession record". That was impossible under its own design: `assertion_supersession` is not an `evidence_entity`, has no registry row and no `entity_kind`, and so could not be the target of the relation's own composite foreign key. With no reversal available, a mistaken supersession would have hidden a correct assertion **permanently**, leaving only `UPDATE` or `DELETE` as remedies — both prohibited.

**Chosen pattern: a separate append-only status-event relation** (`DATA_MODEL_PROPOSAL.md` §2.3). The alternative — making each supersession an `evidence_entity` that can itself be superseded — is rejected because it entangles operational lifecycle records with scientific evidence in one registry and makes the §7.6 membership audit recurse through lifecycle rows.

```
supersession_status_event(
    status_event_id,
    supersession_id  FK → assertion_supersession,
    event_seq        bigint,                        -- monotonic per supersession
    event_type       enum: asserted | reversed | reaffirmed,
    reason           NOT NULL,
    authorised_by    NOT NULL,
    created_at       NOT NULL,
    UNIQUE (supersession_id, event_seq)
)
```

Every supersession is created with exactly one `asserted` event at `event_seq = 1`, enforced by a deferred trigger. Reversal appends `reversed`; a reversal found wrong appends `reaffirmed`. Depth is unbounded; every step is an insert. Ordering is by `event_seq`, not timestamp, so "the latest event" is total and deterministic under clock skew and same-transaction writes.

Current state is a **view over *active* supersessions only**:

```sql
CREATE VIEW active_supersession AS
SELECT s.* FROM assertion_supersession s
JOIN (SELECT DISTINCT ON (supersession_id) supersession_id, event_type
      FROM supersession_status_event ORDER BY supersession_id, event_seq DESC) l
  USING (supersession_id)
WHERE l.event_type IN ('asserted','reaffirmed');

CREATE VIEW current_assertion AS
SELECT a.* FROM assertion a
WHERE  NOT EXISTS (
         SELECT 1 FROM active_supersession s      -- active, not merely present
         WHERE  s.superseded_entity_id = a.evidence_entity_id
       );
```

**A supersession that has itself been reversed no longer hides its target.** The anti-join stops matching and the original assertion returns to the current view, with the assertion row, the supersession row, and every status event all preserved exactly as written. `DATA_MODEL_PROPOSAL.md` §2.6 gives the worked A→B→reversal→A demonstration: **zero updates, zero deletes**, and every intermediate state reconstructible by filtering on `event_seq`.

**Six distinguished supersession types**, each with different semantics:

| Type | Meaning | Superseding row required? | Original remains queryable as |
|---|---|---|---|
| `correction` | The stored value misread the source; the source is unchanged | Yes | An incorrect transcription |
| `supersession` | A newer, better-evidenced assertion replaces an older one; both were defensible when made | Yes | Historically valid |
| `retraction` | The assertion should never have been made; its basis was invalid | No | Retracted, not merely old |
| `adjudication` | A human resolved a registered `conflict` in favour of one side | Yes (the winning side) | The non-adjudicated alternative, still visible |
| `duplicate_declaration` | Two rows describe the same fact; one is designated canonical | Yes (the canonical row) | A duplicate, not an independent observation |
| `withdrawal` | The assertion is withdrawn pending re-evidence; no replacement exists yet | No | Withdrawn, awaiting resolution |

`duplicate_declaration` matters specifically for independence claims: `PROJECT_GOVERNANCE.md:217` forbids treating separate rows as independent samples without support, and a duplicate declaration is exactly that support, recorded rather than assumed.

### 7.5 Integrity baselines outside the database

`PROPOSED` — database receipts are retained, but **at least one integrity baseline must live outside the mutable database**. Three layers, all required:

1. **Signed manifest in Git.** Each capture and cohort build emits a manifest (path → sha256 → bytes → capture context) that is committed. Git history is append-only in practice and independently reviewable. Manifests are **signed** where a signing key is available.
2. **Object storage with object lock / WORM retention.** Raw objects are written once under a retention policy that refuses overwrite and deletion for the retention window. A hash mismatch then indicates storage corruption, not silent replacement.
3. **Capture receipts written once, never regenerated.** A receipt records what was true at capture time. It is never recomputed from current state.

**Anti-laundering rule, stated as a prohibition:** *no integrity baseline may be regenerated from the artifacts it is supposed to verify.* Verification always compares current state against a record created **before** the change under test, held in a store the changing process cannot rewrite. Violation is stop condition **S2**.

**Hash domains are defined separately.** See [`docs/HASH_AND_LINE_ENDING_POLICY.md`](../HASH_AND_LINE_ENDING_POLICY.md), which distinguishes the **raw source artifact**, **object-store**, **canonical Git-content**, and **working-tree** hash domains, and requires every manifest and receipt to name the domain it records rather than a bare `sha256`.

### 7.6 Referential integrity — no polymorphic dangling references

**The previous design was wrong.** It used untyped `subject_type` + `subject_id` pairs on `linkage_assertion`, `screening_decision`, `eligibility_evaluation`, `conflict`, `amendment`, and provenance targets. PostgreSQL cannot enforce a foreign key against a column pair whose target table varies by row, so **a dangling reference was representable**. That violates A13.

`PROPOSED` — **central `evidence_entity` registry with genuine foreign keys**, using class-table inheritance, plus **typed junction tables** where a relationship must be restricted to particular kinds.

```
evidence_entity(
    evidence_entity_id  PK,
    entity_kind         enum NOT NULL,
    created_at,
    UNIQUE (evidence_entity_id, entity_kind)     -- enables composite FKs below
)
```

Every assertable entity's own table takes `evidence_entity_id` as **both its primary key and a foreign key** to the registry, and carries a generated `entity_kind` constant:

```
phenotype_observation(
    evidence_entity_id PK REFERENCES evidence_entity(evidence_entity_id),
    entity_kind  GENERATED ALWAYS AS ('phenotype_observation') STORED,
    FOREIGN KEY (evidence_entity_id, entity_kind)
        REFERENCES evidence_entity(evidence_entity_id, entity_kind),
    ...
)
```

A referencing table then gets a **real FK plus a kind restriction**:

```
eligibility_evaluation(
    ...,
    subject_entity_id  NOT NULL,
    subject_kind       NOT NULL,
    FOREIGN KEY (subject_entity_id, subject_kind)
        REFERENCES evidence_entity(evidence_entity_id, entity_kind),
    CHECK (subject_kind IN ('phenotype_observation','genotype_observation',
                            'isolate','genome_asset','study'))
)
```

The composite foreign key guarantees the referent **exists**; the `CHECK` guarantees it is of an **allowed kind**. Neither is bypassable by application code.

**Application to the six required cases:**

| Case | Pattern | Enforcement |
|---|---|---|
| **Linkage assertions** | **Typed junction tables**, one per relation family, because linkage semantics differ by pair type. `identifier_linkage(identifier_a_id, identifier_b_id)` with plain FKs to `identifier`; `observation_genome_linkage(phenotype_observation_id, genome_asset_id)`; `isolate_identifier_linkage(isolate_id, identifier_id)` | Plain two-column FKs. No polymorphism at all. Strongest typing where it matters most, because a mis-typed linkage is exactly the failure `PROJECT_GOVERNANCE.md:129` warns about |
| **Screening decisions** | Registry FK + kind restriction to `{study, search_result, source_file}` | Composite FK + CHECK |
| **Eligibility evaluations** | Registry FK + kind restriction to `{phenotype_observation, genotype_observation, isolate, genome_asset, study}` | Composite FK + CHECK |
| **Conflicts** | `conflict` header row + **`conflict_participant`** child table, one row per participant, each with a registry FK. Supports 2..n participants (the matrix v1–v4 chain is one four-way conflict, not three pairs) | Composite FK per participant; `CHECK (participant_count >= 2)` enforced by deferred trigger |
| **Amendments / supersessions** | `assertion_supersession` with two registry FKs (§7.4); `superseding_entity_id` nullable only where the type permits | Composite FKs; `CHECK` tying nullability to `supersession_type` |
| **Provenance locators** | `provenance_locator` has a plain FK to `provenance`; `provenance` has a plain FK to `source_file`. The *assertion→provenance* link is a registry FK with a kind restriction to assertable kinds | Plain FKs down the chain; composite FK upward |

**Result — qualified.** The composite foreign keys above enforce **one direction only**: a concrete child must point at a correctly typed registry row. They do **not** enforce that every registry row has a concrete child, and revision 2's claim that "no dangling entity reference is representable" was therefore an overclaim. A registry row can be inserted with a kind and no evidence, and a Pattern A reference to it satisfies every declared constraint while pointing at nothing — a semantic dangling reference.

**Both directions are required, and the reverse direction is not a schema property.** `DATA_MODEL_PROPOSAL.md` §1.5 specifies the enforcement: a `DEFERRABLE INITIALLY DEFERRED` constraint trigger on `evidence_entity` that requires exactly one concrete child at `COMMIT` (so a registry-only row never becomes visible and therefore never becomes referenceable); a data-driven `entity_kind_table_map` so an unregistered kind fails loudly rather than skipping the check; and a registry-to-concrete **membership audit** run at the end of every ingestion phase and before every cohort build, which must return zero orphan and zero multi-homed rows. Negative tests **A13-N1…N5** and positive test **A13-P1** verify it.

The audit exists because triggers can be dropped, disabled, or bypassed by a privileged bulk load, and §17 permits bulk ingestion: **the audit is the check of record; the triggers are the fast fence.**

Until those are implemented and passing, the accurate statement is: *the child→registry direction is enforced by foreign key; the registry→child direction is enforced by deferred trigger and audit, and is a claim about the implementation rather than about the schema alone.* The unqualified form of the claim is withdrawn.

### 7.7 Typed locators, contract-specific requirements

**The previous design was wrong.** It imposed a single global precision ordering (`cell > row > table > section > page > document`) and implied a universal floor. That ordering is incoherent across media: an XPath into a JATS table cell and a sentence offset in a discussion section are not comparable on one scale, and a figure panel has no position in that hierarchy at all.

`PROPOSED` — **typed locators with no global ordering**, and **per-contract requirements**:

```
provenance_locator(
    locator_id PK,
    provenance_id FK NOT NULL,
    locator_type enum NOT NULL,
    locator_payload JSONB NOT NULL,   -- shape validated per type
    resolves_to_source_file_id FK
)
```

**Locator types:**

| Type | Payload shape |
|---|---|
| `tabular_cell` | `{sheet?, table_index, row, column_name, column_index?}` |
| `tabular_row` | `{table_index, row}` |
| `document_text` | `{page?, section?, paragraph?, sentence?, char_start?, char_end?}` |
| `figure` | `{figure_number, panel?, caption_ref?}` |
| `supplementary_item` | `{item_label, item_filename?, inner_locator?}` |
| `xml_node` | `{xpath}` |
| `json_pointer` | `{pointer}` |
| `file_line` | `{path, line_start, line_end?}` |
| `record_field` | `{accession, database, field, retrieved_at}` |
| `image_region` | `{page, bbox}` — for OCR provenance (§20) |

**Requirements are contract-specific, not global.** Each eligibility contract declares which locator types it accepts for which evidence kinds:

```json
"locator_requirements": {
  "phenotype_observation": {"any_of": ["tabular_cell", "record_field", "supplementary_item"]},
  "screening_decision":    {"any_of": ["document_text", "tabular_row", "record_field"]}
}
```

A Model 1 primary contract may demand `tabular_cell` for MICs. A descriptive contract may accept `document_text`. Neither is "more precise" in the abstract; they are appropriate to different claims.

**Every assertion must carry an appropriate locator or a registered `provenance_defect`** (A3). Defect types: `no_locator_available`, `locator_unresolvable`, `source_file_absent`, `locator_type_unsupported_by_parser`, `legacy_import_no_locator`.

---

## 8. Migration strategy

### 8.1 Principles

1. **Read-only at source.** Capture reads bytes; it never writes, checks out, rebases, or stages anything in a source repository.
2. **Rights before bytes.** No artifact is captured until a rights decision exists for it (§11.2). This is independent of D3 (§12.1).
3. **Capture the version chain, not the winner.** Matrix v1–v4 are four artifacts. All four are captured. "v4 is authoritative" is an *assertion with a source*, not a filter.
4. **Newest is not authoritative** (`PROJECT_GOVERNANCE.md:174-182`). Authority is a recorded, scoped property (§9.3, D5).
5. **Capture context, not just commit.** Tracked and untracked artifacts get different but equally complete provenance (§8.5, S11).

### 8.2 Order of capture

```
1. Contracts, schemas, controlled vocabularies      (define the target vocabulary)
2. Receipts and manifests                           (they name what else exists)
3. Search registers and acquisition manifests       (the discovery frame)
4. Screening / exclusion ledgers                    (decisions, with their contracts)
5. Phenotype observations
6. Identifiers and linkage tables
7. Genome assets and capability metadata
8. Genotype observations (determinant calls)
9. Context assertions
10. Historical eligibility decisions (as decisions, not truth)
11. Cohort exports (as snapshots of the past)
12. Model outputs (quarantined, §8.3)
13. Reports and narrative documents
```

Receipts before data turns every later capture into a *checked* assertion.

### 8.3 Model outputs are not source evidence

`model1/results/**` (76 files), `model1/figures/**` (15 files), and every metrics/predictions/ablation/headline artifact are captured with `artifact_class='model_output'` and are structurally barred from evidence-layer views. A predicted MIC is not reachable from a query returning observed MICs.

### 8.4 Reference-only artifacts

Publisher PDFs/DOCX/XML; genome FASTA/GBFF/FASTQ/SRA payloads; the git-ignored raw trees; DUA-gated datasets never obtained. For these the warehouse stores identifier, declared hash, declared size, locator, rights decision, and retrieval instruction — not the bytes. See D4 (hybrid).

### 8.5 Untracked files at source — provenance without a commit

**The previous stop condition S11 was wrong.** It required *"a source, commit, path, and hash"* for every artifact. An untracked working file **has no commit containing it** — demanding one would force either a false commit attribution or a wrongful rejection. Two real artifacts are affected: `model1-context-mic/DATA_DISCOVERY_AND_ELIGIBILITY_AUDIT.md` (53,151 B) and `genotype-phenotype-mobility/two-model-roadmap.mhtml` (63,572 B).

`PROPOSED` — untracked working files are capturable with a **distinct, complete provenance shape**:

| Field | Tracked artifact | Untracked working file |
|---|---|---|
| `source_repository` | required | required |
| `worktree_path` | required | required |
| `branch` | required | required (branch checked out at capture) |
| `source_commit` | the commit containing the file | **NULL — prohibited to populate** |
| `head_at_capture` | = `source_commit` | required (repo HEAD when captured; the file is *not* in it) |
| `relative_path` | required | required |
| `sha256`, `byte_size` | required | required |
| `file_mtime`, `captured_at` | recorded | **required** |
| `provenance_class` | `committed` | `untracked_working_file` |
| `verification_state` | may reach `verified` | `unverified` until corroborated by a tracked artifact |
| `authority_state` | per `authority_assertion` | **`never_authoritative`**, permanently |

A `CHECK` enforces that `provenance_class='untracked_working_file'` implies `source_commit IS NULL` — a false commit attribution is not representable.

**Neither falsely attributed nor rejected for being untracked.** The audit document contains substantive claims (screening attrition, search recall) and at least one independently falsified claim (`audit/data/` being git-ignored — it is tracked, 111 files, `CONFIRMED`). Both facts are preservable under this shape.

### 8.6 What migration will *not* do

- It will not choose between matrix v2 and matrix v4.
- It will not apply the "retired" label as a delete.
- It will not repair the duplicate-column header in `exact_mic_balanced_round5_repository_selection.tsv`; it captures as-is and registers a `schema_defect`.
- It will not backfill a missing method, standard, or unit.
- It will not drop zero-row tables; a header-only table is evidence that a process ran and produced nothing.
- It will not convert any assay modality into a BMD MIC.

---

## 9. Reconciliation strategy

Reconciliation *detects and registers* disagreement. It does not resolve it.

### 9.1 Reconciliation classes

| Class | Definition | Observed example |
|---|---|---|
| **R1 Version chain** | Successive versions of one logical artifact | `bmd_matrix` v1(1,000) → v2(1,000) → v3(3,398) → v4(4,552) rows |
| **R2 Near-duplicate** | Same schema, same row count, different bytes | `master_source_exclusion_ledger_v1_1` vs `_v1_2`: 1,804 rows each, 52 bytes apart |
| **R3 Schema drift** | Same logical table, changed columns | census v8_amrfinder(28) → v8_1(35, adds `v8_on_plasmid`) → v8_2(34, drops it) |
| **R4 Cross-branch content conflict** | Same path, different content across branches | `CLAUDE.md`, `DATA_REGISTRY.md`, `LESSONS_LEARNED.md` |
| **R5 Cross-project disposition** | Same observation, opposite eligibility verdicts | PMID 40239923 / isolate 724942 |
| **R6 Document/data disagreement** | A document states a count the data contradict | `PROJECT_STATUS.md` names v2 authoritative; `CLAUDE.md` retires v2 |
| **R7 Internal numeric inconsistency** | Two statements of one quantity | 6,298 "edges" vs 6,373 "rows" |
| **R8 Declared-vs-measured** | A receipt's declared count differs from the file | To be tested at 0D; none confirmed yet |
| **R9 Missing referent** | An artifact referenced but absent | `eskape_mic_inventory.tsv` |

### 9.2 Procedure

1. Compute each artifact's hash, row count, and header.
2. Compute the row-level symmetric difference on a natural key where one exists.
3. Classify per §9.1.
4. Write a `conflict` header row and one `conflict_participant` row per artifact (§7.6).
5. Write a human-readable entry to `docs/CONFLICT_REGISTER.md`.
6. **Stop.** Do not select a winner.

### 9.3 Authority is an assertion, and it is scoped

`authority_assertion(artifact_entity_id, status, scope, asserted_by_source_file_id, locator, asserted_at)`.

**`scope` is mandatory.** Authority is analysis- and contract-specific, never global. "Matrix v4 is authoritative" is meaningless without "for which analysis, under which contract version". Contradictory assertions coexist; a query for "the authoritative matrix" returns the assertions, not a row, until an adjudication is recorded as its own assertion with the user as source. See D5.

### 9.4 R5 is not a defect

A record refused by Model 1 and admitted by Model 2 is **correct behaviour** under `PROJECT_GOVERNANCE.md:42`. Registered as a conflict with `severity_at_detection='informational'` plus a `conflict_resolution_event` of type `declared_not_resolvable`; the derived `current_conflict_state` view then reads `not_resolvable` (`DATA_MODEL_PROPOSAL.md` §12.1.1).

---

## 10. Testing strategy

| Tier | Tests | Runs when |
|---|---|---|
| **T1 Schema** | Migrations apply to an empty database; every declared constraint exists; no `UPDATE` grant on evidence tables | Every commit |
| **T2 Invariant** | Governance rules as constraints: no censored value stored as exact; no modality in a foreign field; no assay pooling; append-only enforcement (A14, including that no `UPDATE` grant exists on any evidence table) | Every commit |
| **T2b Registry integrity** | **Negative** tests A13-N1…N5 (registry-only row must fail at `COMMIT`; kind mismatch must fail; two concrete children must fail; reference to a childless entity must fail; bulk-loaded orphan must be caught by audit) and positive test A13-P1 | Every commit |
| **T2c Membership audit** | Registry-to-concrete audit returns **zero** orphan rows and **zero** multi-homed rows | End of every ingestion phase; before every cohort build |
| **T2d Supersession reversal** | The A→B→reversal→A sequence (`DATA_MODEL_PROPOSAL.md` §2.6) executes with zero `UPDATE` and zero `DELETE`, and `current_*` views return A at the end | Every commit |
| **T2e Nullable uniqueness** | No `UNIQUE` constraint contains a nullable column unless declared `NULLS NOT DISTINCT` or backed by a generated non-null key; a duplicate-insert negative test exists per such constraint | Every migration |
| **T3 Parser preservation** | `raw_cell_text` non-null and byte-faithful; round-trip as an *additional* check (A4) | Every commit |
| **T4 Capture receipt** | Re-computed hash, row count, and header match the **external** baseline (§7.5) | Every capture |
| **T5 Reconciliation** | Every known conflict class is detected; a seeded synthetic conflict is detected | Every capture |
| **T6 Contract evaluation** | Each contract over a fixture set produces expected admissions, refusals, **and refusal reasons** | Every contract change |
| **T7 Cohort reproduction** | Two builds from the same (contract, snapshot, generator) yield identical hashes | Every cohort build |
| **T8 Legacy reconciliation** | A8's seven levels, four outcomes, per cohort | Phase 0I |
| **T9 Negative tests** | Every admission rule has a test proving it **refuses** something (`M2:CONTRIBUTING.md`: *"Never make a record admissible by loosening a check."*) | Every rule change |
| **T10 Release readiness** | No credential, genome, publisher file, absolute machine path, or rights-restricted artifact tracked | Pre-commit; pre-any-release |
| **T11 Locator coverage** | A3-T1 and A3-T2 | Every ingestion phase |

**Fixtures rule:** tiny and synthetic. Real evidence never enters `tests/fixtures/`.

**CI note:** these tiers describe *what* is tested, not *when CI runs*. CI scheduling policy is §21, and no workflow exists or is to be created in Phase 0.

---

## 11. Security, rights, and confidentiality boundaries

### 11.1 Repository confidentiality — D1, resolved

`CONFIRMED` as of 2026-08-16:

| Repository | Remote | Visibility |
|---|---|---|
| `amr-evidence-warehouse` | `github.com/piranfar/amr-evidence-warehouse` | **PRIVATE** (`isPrivate: true`) |
| `mobility-aware-amr-mic-private` (4 worktrees) | `github.com/piranfar/mobility-aware-amr-mic-private` | **PRIVATE** |
| `mobility-aware-amr-emergence` | *no remote configured* | unpublished |

D1 was resolved to option (a). Stop condition **S3** is cleared: the three Phase 0A drafts are no longer blocked from commit on confidentiality grounds. Visibility is not to be revisited.

**D1 did not resolve anything else.** See §12.1.

### 11.2 Rights and access — a multidimensional decision, not a boolean

**The previous design was wrong.** It used a single `redistribution_permitted` boolean on `source`. That conflates at least eight independent permissions, and it produces exactly the wrong default: an artifact that may be *read and processed* but not *redistributed* would be marked `FALSE` and effectively become unusable, while an artifact that may be redistributed but is under embargo would be marked `TRUE` and released early.

`PROPOSED` — a `rights_decision` entity, versioned, one or more per (source, artifact class), with these **independent** dimensions:

| Dimension | Values |
|---|---|
| `storage_permission` | `permitted` · `permitted_local_only` · `prohibited` · `requires_review` · `unknown` |
| `processing_permission` (incl. text and data mining) | `permitted` · `permitted_non_commercial` · `prohibited` · `requires_review` · `unknown` |
| `redistribution_permission` | `permitted` · `permitted_with_attribution` · `prohibited` · `requires_review` · `unknown` |
| `publication_permission` (may the artifact itself be published) | `permitted` · `prohibited` · `requires_review` · `unknown` |
| `derived_data_publication_permission` (may facts extracted from it be published) | `permitted` · `permitted_aggregated_only` · `prohibited` · `requires_review` · `unknown` |
| `access_classification` | `public` · `licensed` · `contractual` · `confidential` · `restricted_personal` |
| `embargo_until` | date NULL |
| `contractual_control` | `none` · `dua` · `publisher_agreement` · `institutional` · `unknown`, with `agreement_reference` |
| `review_state` | `decided` · `requires_review` · `escalated` · `unknown` |

**A source may be processable without being redistributable.** This is the normal case for publisher full text: `storage_permission='permitted_local_only'`, `processing_permission='permitted'`, `redistribution_permission='prohibited'`, `derived_data_publication_permission='permitted_aggregated_only'`. Under a boolean, that artifact could not be represented at all.

**`unknown` and `requires_review` are first-class and are not permissions.** A capture may not proceed on `unknown`. Default on ingestion of an unclassified source is `requires_review`, which **blocks** capture until a decision is recorded.

**Observed rights positions to encode** (`CONFIRMED`): `model1-context-mic:COPYRIGHT.md` — all rights reserved, no open-source licence granted, third-party content disclaimed. `mobility-aware-amr-emergence:DATA_LICENSE.md` — Apache-2.0 covers *code and schemas only*; *"No open data licence is applied to the derived table… This is a decision, not an oversight."* Vivli/ATLAS/SENTRY — `contractual_control='dua'`, never obtained, `access_classification='contractual'`.

### 11.3 Security

- Credentials read only from environment (`NCBI_API_KEY`, `NCBI_EMAIL`, `ELSEVIER_API_KEY`); never printed, persisted, or captured. Any raw API response is scrubbed of the key before hashing, and the scrub is recorded.
- Database credentials in environment or a secret manager; never in Git, never in a receipt.
- The object store must not be readable beyond the warehouse boundary where it holds `access_classification` above `public`.
- **`NOT DOCUMENTED`:** neither source project declares a PHI/consent/IRB policy; incidental patient-adjacent narrative text exists. A sensitive-data statement should be written in 0B rather than assumed. `access_classification='restricted_personal'` exists for it.

---

## 12. Decisions requiring owner approval

**D1 is APPROVED** (2026-08-16, resolved to option (a): repository made PRIVATE).

**D2–D11 remain UNAPPROVED as execution authorities.** Revision 2 records a recommended outcome for each, marked `PROPOSED — OWNER APPROVAL PENDING`. Recording a recommendation is not approval, and no recommendation below authorizes any action.

### 12.1 D1 versus D3 versus rights — three independent permissions

**These must not be collapsed into one.** Revision 1 partially conflated them; corrected here.

| Control | Question it answers | Scope | Status |
|---|---|---|---|
| **D1 — Confidentiality** | Can warehouse *content* be seen by people outside the project? | The warehouse repository's exposure and publication risk | **APPROVED** — PRIVATE |
| **D3 — Extraction and capture authorization** | May the warehouse *read source content to produce ingestible structured output*, and *copy source bytes into the object store*? | **D3 governs reading source content for Activity 2 extraction and copying source bytes for Activity 3 capture. It does not govern Activity 1 read-only inspection.** Scoped per artifact class | **PENDING** |
| **Rights policy (§11.2)** | May *these particular bytes* be stored, processed, redistributed, or published at all, given their licence, contract, or embargo? | Per source and artifact class, independent of both above | **PENDING per artifact class** |

**All three must be satisfied for any given artifact.** A private repository (D1 ✓) does not make a publisher PDF storable. Owner authorization to ingest (D3 ✓) does not override a DUA. And a permissive rights decision does not authorize reading bytes the owner has not released. Worked case:

> A publisher PDF cited in the Model 2 source manifest. D1 ✓ (warehouse is private). D3 — would need to cover the artifact class "publisher full text", which the recommended scoped authorization **excludes**. Rights — `storage_permission='permitted_local_only'`, `redistribution_permission='prohibited'`. **Outcome: not captured.** The warehouse holds its hash, size, and locator as a reference-only record. Three independent gates, one of which alone would have given the wrong answer.

### 12.2 D2 — Licence for warehouse code

**Question.** What licence applies to warehouse code, and what statement governs data rights?

**Options.** (a) Apache-2.0 for code + separate explicit data-rights statement; (b) all rights reserved for both; (c) defer, add no `LICENSE`.

**`PROPOSED — OWNER APPROVAL PENDING`: option (a)** — Apache-2.0 for warehouse code **in a future release**, with an explicit, separate data-rights statement in `DATA_RIGHTS.md`. **The code licence grants no rights whatsoever in any data, derived table, or extracted fact.** This mirrors the Model 2 precedent, which is the only defensible position given that neither source project owns the third-party content it references.

**Consequences.** (a) enables method reuse and citation while keeping the data boundary explicit; the boundary must be stated or users will assume the code licence covers the tables. (b) blocks external code reuse. (c) is legally near-equivalent to (b) but invites misreading.

**Authorizes.** Nothing in Phase 0. Relevant only at a future release (§18).
**Blocking.** Not blocking for 0B–0J. Blocking for any release.
**Depends on it.** §4 (`LICENSE`, `DATA_RIGHTS.md`), §11.2, §18, tier T10.

### 12.3 D3 — Authorization to read and copy source bytes for ingestion

#### 12.3.0 What D3 governs, and what it does not

Revision 2 stated D3 as "authorization to read bytes", which was too broad: read literally, it implied that the completed Phase 0A inventory had been unauthorized. **It was not.** Revision 3 corrected that but replaced it with a different error — a **header-versus-row** rule:

> *"Reading a header line to record a schema is activity 1. Reading the rows beneath it to create observations is activity 2."*

**That rule is withdrawn in revision 4.** It is unworkable, and the Phase 0A inventory itself would have violated it. Counting rows, detecting schema drift, finding the three duplicated column names in `exact_mic_balanced_round5_repository_selection.tsv`, noticing that `exclusion_census_audit_v1_1.tsv` is header-only, and verifying a receipt's fields **all require looking past the header**, and all are audit, not extraction. A rule that forbids reading any row makes auditing the estate impossible.

**The boundary is purpose, output, and scope — never header versus row.**

#### Activity 1 — read-only inspection

*Limited observation for governance or audit purposes.* Permitted, where necessary for that purpose:

- reading headers;
- **sampling rows**;
- **counting rows**;
- identifying duplicate columns, schema drift, or malformed structure;
- checking hashes and byte sizes;
- **opening a receipt to verify specific named claims**;
- confirming the existence, shape, or emptiness of an artifact.

Requirements — all four must hold:

1. **No structured evidence row and no extraction candidate is created.** Observations are recorded as *inventory findings in a document*, not as ingestible structured content.
2. **No source bytes are copied into the Warehouse or object store.**
3. **No scientific eligibility conclusion is silently made.** An inspection may record that an artifact exists and what shape it has; it may not decide what is admissible (that is stop condition **S10**).
4. **The inspection's scope and purpose are recorded** — what was examined, why, and how much.

**Phase 0A's already-authorized inventory work remains valid in full.** Nothing in D3, in either its revision-2 or revision-3 form, retroactively invalidates it.

#### Activity 2 — extraction

*Reading source content for the purpose of producing ingestible structured content:* extraction candidates, normalized observations, evidence assertions, linkage candidates, or any other structured output destined for a warehouse relation.

**Requires a separate, explicit D3 artifact-class authorization plus an applicable rights decision** permitting processing.

#### Activity 3 — capture

*Copying source bytes into the Warehouse or object store.*

**Requires a separate, explicit D3 artifact-class authorization plus `storage_permission` under the rights model** (§11.2). The result is recorded as a `storage_status_event` (`DATA_MODEL_PROPOSAL.md` §4.2.1).

#### Five clarifications, stated explicitly

1. **The distinction is purpose, output, and scope — not header versus row.**
2. **Inspecting a limited number of rows does not automatically become extraction.** Reading 20 rows of a 16,294-row table to characterise its schema and spot a defect is inspection.
3. **Reading an entire table in order to populate candidate or evidence rows is extraction** — regardless of how few rows survive.
4. **Opening a receipt to verify named fields may be Activity 1** and does not itself authorize ingestion. The concrete pending case: `master_source_exclusion_ledger_v1_2_receipt.json` is claimed to record `verified_exclusions_with_a_primary_locator: 0`, currently `SUPPORTED BUT INCOMPLETE` because the receipt was not opened. Opening it to confirm two named fields, recording the result in the inventory, and upgrading the label to `CONFIRMED` or `CONTRADICTED` is inspection — it creates no warehouse evidence and requires no D3 grant.
5. **D3 does not retroactively invalidate Phase 0A inventory inspection.**

#### The reclassification rule

**If an inspection begins producing reusable structured facts, or exceeds its declared audit scope, it must stop and be reclassified as extraction** — and may not continue without a D3 authorization and a rights decision. Two concrete triggers: writing inspection output into a machine-readable file intended for later ingestion, and reading systematically through an artifact rather than sampling it. Scope creep here is a stop condition, not a judgement call.

**Stop condition S4 blocks Activities 2 and 3 without authorization. It does not block Activity 1**, and did not apply to the Phase 0A inspection.

#### 12.3.1 The decision

**Question.** May the warehouse read source bytes for parsing/extraction (activity 2) and copy them into the object store (activity 3), and under what scope?

**Options.** (a) blanket authorization; (b) withhold entirely (metadata and references only); (c) scoped authorization by named artifact class.

**`PROPOSED — OWNER APPROVAL PENDING`: option (c)** — scoped ingestion authorization only, granted **per named artifact class** and **conditional on a recorded rights decision for that class**. Not a blanket authorization.

Proposed class scoping, for owner review:

| Artifact class | Recommended | Rationale |
|---|---|---|
| Contracts, schemas, controlled vocabularies | capture | Small, project-owned, define the vocabulary |
| Receipts, manifests, protocol snapshots | capture | Project-owned; needed for A2/T4 |
| Derived evidence tables (matrices, censuses, ledgers, linkage, context) | capture | The substance of the warehouse; project-owned |
| Cohort exports | capture | Needed for A8 |
| Extracted publication tables (`audit/data/processed/**`) | **requires review** | Derived from publisher XML; rights decision needed first |
| Reference sequences (`audit/data/reference/**`) | **requires review** | Third-party; terms not recorded |
| Model outputs | capture, quarantined | Needed for completeness; barred from evidence |
| Narrative reports and status documents | capture | Project-owned |
| Draft author-enquiry emails | **exclude** | Name real researchers; no ingestion purpose |
| Full-text evidence extracts (e.g. `confirmatory_seed_fulltext_evidence.txt`) | **exclude pending review** | Possible copyrighted excerpt |
| Binary artifacts not yet opened (`.docx`, `.npz`, `.mhtml`) | **requires review** | Contents `CANNOT DETERMINE` |
| Genome/sequence payloads, publisher PDFs, git-ignored raw trees | reference-only | Rights and size |

> **D3 explicit statement, required by the revision instruction:**
> **Approval of this architectural recommendation would still not authorize ingestion.** Endorsing "scoped authorization is the right *shape*" is a design agreement, not a grant. Before any source byte is read or copied, a **separate, explicit, scoped artifact-class authorization** must be issued naming the classes, and a rights decision must exist for each. Until then stop condition **S4** remains active.

**Consequences.** (a) is fastest and least safe — it would sweep in author emails, full-text extracts, and unreviewed binaries. (b) makes A1/A2 unsatisfiable and leaves the warehouse dependent on the private repos surviving unchanged. (c) requires the class list to be settled in 0B; slower, and correct.

**Authorizes.** 0D, per class, only when separately granted.
**Blocking.** **YES** for 0D and everything after.
**Depends on it.** 0D→0J; A1, A2, A8.

### 12.4 D4 — Copy versus reference-in-place

**Question.** Does ingestion copy bytes into the warehouse object store, or reference source artifacts in place by (repository, HEAD-at-capture, path, hash)?

**Options.** (a) copy everything; (b) reference everything; (c) hybrid.

**`PROPOSED — OWNER APPROVAL PENDING`: option (c)** — hybrid. **Content-addressed copies for permitted, high-value evidence artifacts; reference-only for restricted or impractical artifacts.** `current_storage_state.status ∈ {stored, reference_only, unavailable, lost, quarantined}` already carries this, derived from the append-only `storage_status_event` relation rather than from a mutable column (`DATA_MODEL_PROPOSAL.md` §4.2.1).

**Consequences.** (a) satisfies A2 and §5.1 immutability but would duplicate ~27 GB and would capture artifacts rights policy forbids storing. (b) is cheap but fragile: a rebase, branch deletion, or worktree removal silently breaks the warehouse — and `mobility-aware-amr-emergence` has **no remote at all** and exists in exactly one place on disk (`CONFIRMED`). (c) matches the rights model: `storage_permission` decides which branch each artifact takes.

**Authorizes.** The 0D storage architecture. **Blocking** for 0D. Not blocking for 0B or 0C.

### 12.5 D5 — Authority adjudication for the three cross-branch conflicts

**Question.** Does the `feature/model1-context-mic` version of `CLAUDE.md`, `DATA_REGISTRY.md`, and `LESSONS_LEARNED.md` supersede the versions on `agent/candidate-024` and `feature/assay-aware-emergence-risk`?

**Options.** (a) yes, globally; (b) no; (c) leave unadjudicated; (d) scoped adjudication.

**`PROPOSED — OWNER APPROVAL PENDING`: option (d)** — **matrix v4 and census v8.2 are authoritative *only for the current Model 1 analysis*.** Matrix v2 and the withdrawn census versions remain **historical / retired, not deleted**. **Authority is analysis- and contract-specific, never global** (§9.3, `authority_assertion.scope` mandatory).

This is a recommendation about the *form* the adjudication should take. **The scientific adjudication itself remains the owner's**, and nothing here decides whether the underlying Model 1 gate is open or closed. Stop condition **S10** still applies to any attempt to answer that question.

**Consequences.** (a) risks a global claim that would be wrong for a Model 2 or descriptive analysis that legitimately uses different artifacts. (b) inverts the current working assumption of one worktree. (c) is architecturally supported (§9.3) and lets Phase 0 complete without D5, but leaves cohort work ambiguous. (d) preserves both records and confines the claim to where evidence supports it.

**Authorizes.** 0G's adjudication step to record an `assertion_supersession` of type `adjudication`.
**Blocking.** **YES** for 0G adjudication. **NOT** blocking for 0G detection — reconciliation registers the conflict regardless (§9).

### 12.6 D6 — Ingestion baseline

**Question.** Which source commits constitute the capture baseline?

**Options.** (a) the four recorded branch tips (§13); (b) `main` (`dacba51`), which lacks 536–649 files.

**`PROPOSED — OWNER APPROVAL PENDING`: option (a)** — the four recorded branch tips are the proposed capture baseline, **each preserved independently**. No branch is merged, flattened, or preferred at capture; the three cross-branch content conflicts are captured as four distinct `source_file` rows and registered as an R4 conflict.

**Consequences.** (a) captures the complete estate and makes A7 meaningful. (b) loses 536–649 files including all of `model1/` and the entire Model 2 contract tree, rendering A7 and A8 largely vacuous.

**Authorizes.** 0D. **Blocking** for 0D. Also fixes the **S1** comparison baseline (§13).

### 12.7 D7 — Untracked working files

**Question.** How are `DATA_DISCOVERY_AND_ELIGIBILITY_AUDIT.md` and `two-model-roadmap.mhtml` treated?

**Options.** (a) capture as unverified, never authoritative; (b) exclude; (c) require commit at source — **unavailable**, would modify a read-only repository.

**`PROPOSED — OWNER APPROVAL PENDING`: option (a)** — capture both as **unverified, non-authoritative captured artifacts** under the untracked provenance shape of §8.5, with `source_commit` NULL and `authority_state='never_authoritative'`.

**Consequences.** (a) preserves substantive claims while permanently marking them; the audit document contains at least one independently falsified claim and a 10-item action list directed at future work, and must never be read as an instruction. (b) loses the only document bridging the two model programs.

**Authorizes.** 0D, narrowly. **Blocking** for 0D for these two files.

### 12.8 D8 — Historical eligibility decisions

**Question.** Are Model 1's historical eligibility decisions captured as decisions, re-derived from contracts, or both?

**Options.** (a) capture only; (b) re-derive only; (c) both, with reconciliation.

**`PROPOSED — OWNER APPROVAL PENDING`: option (c)** — **preserve historical decisions and independently re-derive eligibility, then reconcile.** Divergences are registered as conflicts, not resolved.

**Consequences.** (a) cannot test whether a decision followed its own stated contract. (b) discards the fact that a human decided something, and discards the 1,576 `candidate_not_screened` rows as facts about screening *effort* rather than about candidates. (c) produces contradictions **by design**; every one becomes a conflict row and must not be silently resolved (**S5**).

**Authorizes.** 0H. **Blocking** for 0H.

### 12.9 D9 — Deployment target

**Question.** Where do PostgreSQL and the object store run?

**Options.** (a) local instance; (b) containerized local; (c) managed/cloud.

**`PROPOSED — OWNER APPROVAL PENDING`: option (b)** — **local-first pilot using containerized PostgreSQL **15 or later** and a local content-addressed object store, with external backup. No deployment yet.**

**Version floor.** `DATA_MODEL_PROPOSAL.md` §19.2 requires `UNIQUE NULLS NOT DISTINCT` on `rights_decision`, introduced in **PostgreSQL 15**. If D9 selects a pre-15 target, `rights_decision` must instead be split into whole-source and per-artifact-class relations, and §19.2 revised — the constraint is not to be quietly weakened. Containerization pins the version and makes the environment reproducible in a receipt; local-first keeps confidential and rights-restricted content inside the existing boundary; external backup satisfies §16's zero-loss requirement for raw objects.

**Consequences.** (a) simplest, least reproducible. (b) reproducible, no new confidentiality surface, no new cost; object-lock semantics must be emulated locally (§7.5) and verified. (c) gives real WORM and managed backup but moves confidential content into a new boundary and adds cost and contractual review.

**Authorizes.** 0C and 0D. **Blocking** for both — **the only decision blocking 0C.**
**Depends on it.** §16 in full; recovery objectives remain `PROPOSED, pending D9`.

### 12.10 D10 — RAG in Phase 0

**Question.** Is the RAG index built during Phase 0?

**Options.** (a) build now; (b) defer.

**`PROPOSED — OWNER APPROVAL PENDING`: option (b)** — **defer RAG implementation beyond Phase 0.** RAG is not required for the completion criterion in `PROJECT_GOVERNANCE.md` §13.

> **Citation correction.** Revision 1 justified this as *"not needed for the §13 completion criterion"*, which read as a reference to §13 of *this* document (stop conditions). The completion criterion is in **`PROJECT_GOVERNANCE.md` §13**. Corrected here; the ambiguity is recorded rather than silently removed.

**Consequences.** (a) adds scope; RAG output would enter as unverified candidates under §6.2. (b) keeps Phase 0 focused; the RAG boundary rules remain specified and unimplemented.

**Authorizes.** 0F's RAG component. **Blocking** for that component only; 0F's evidence normalization does not depend on it.

### 12.11 D11 — Header-defective and zero-row artifacts

**Question.** Are defective and empty artifacts captured as-is with defect registration, or excluded?

**Options.** (a) capture as-is, register defects; (b) exclude.

**`PROPOSED — OWNER APPROVAL PENDING`: option (a)** — **capture header-defective and zero-row artifacts as-is and register defects.** No file is repaired at capture (§8.6).

**Consequences.** (a) preserves `exact_mic_balanced_round5_repository_selection.tsv` (25 header fields, three duplicated names) and the three zero-row tables; a header-only table is evidence that a process ran and produced nothing. (b) loses that evidence and would make `NOT DOCUMENTED` indistinguishable from "never happened".

**Authorizes.** 0E. **Blocking** for 0E.

---

## 13. Explicit stop conditions

Work halts immediately and reports, rather than proceeding, if any of the following occurs:

**S1 — Source mutation.** `git status`, branch, or HEAD in any source worktree differs from the state recorded in §14, other than by changes the owner made. The source repositories are read-only.

**S2 — Integrity baseline violation.** A re-hash of an artifact declared frozen does not match the **external** baseline (§7.5); **or** any process attempts to regenerate an integrity baseline from the artifacts it verifies. Do not re-freeze. Do not regenerate the manifest.

**S3 — Confidentiality.** Any operation that would expose warehouse content beyond the private boundary, or any attempt to revisit repository visibility. *(D1 is resolved; committing the three drafts is no longer blocked by S3.)*

**S4 — Extraction or capture without authorization.** Any operation that would **read source content in order to produce ingestible structured output** (Activity 2 — extraction candidates, normalized observations, evidence assertions, linkage candidates) or **copy source bytes into the Warehouse or object store** (Activity 3) before a **scoped artifact-class authorization** under D3 **and** a recorded rights decision (§11.2) both exist for that class.

**S4 does not block Activity 1, read-only inspection** — which may read headers, sample rows, count rows, detect schema defects, check hashes, and open a receipt to verify named claims, provided it creates no structured evidence, copies no bytes, makes no silent eligibility conclusion, and records its scope and purpose. The Phase 0A inventory was Activity 1 and remains valid.

**S4 also fires on reclassification:** if an inspection begins producing reusable structured facts or exceeds its declared audit scope, it must stop and be treated as extraction. See §12.3.0.

**S5 — Silent conflict resolution.** Any process that would select one of two conflicting artifacts without a recorded adjudication.

**S6 — Information loss at parse.** Any parser that cannot preserve the raw source fragment, or whose round-trip fails. The parser is fixed or the artifact is quarantined; the value is never silently coerced.

**S7 — Assay pooling or modality conversion.** Any code path that would place a non-BMD measurement in a BMD field, convert S/I/R or a zone diameter to a concentration, collapse a censored bound to a point, or treat a PCR negative as genome-wide absence.

**S8 — Model execution.** Any invocation that would fit, tune, score, or re-run Model 1 or Model 2. Prohibited for all of Phase 0.

**S9 — New acquisition.** Any network call performing a new literature search, NCBI query, or download. Includes any continuous or scheduled discovery (§19).

**S10 — Scope creep into adjudication.** If reconciliation reveals a scientific question, stop and report it as an owner decision. Phase 0 does not answer scientific questions.

**S11 — Missing or falsified provenance.** An artifact enters the warehouse only with a complete provenance record **of the shape appropriate to its class** (§8.5): tracked artifacts require a source commit; untracked working files require repository, worktree, branch, HEAD-at-capture, path, SHA-256, size, mtime, capture time, `provenance_class='untracked_working_file'`, and `authority_state='never_authoritative'`, with `source_commit` NULL. **Attributing an untracked file to a commit that does not contain it is itself a stop condition.** An artifact is not rejected merely for being untracked; it is rejected for having no complete provenance of any valid shape, and is then reported as unprovenanced.

**S12 — Governance conflict.** If this plan and `PROJECT_GOVERNANCE.md` disagree, governance wins and this plan is amended.

**S13 — Unauthorized future-phase work.** Any attempt to build a public release or API (§18), enable continuous ingestion (§19), install or run GROBID/OCR (§20), or create or enable a CI workflow (§21).

**S14 — Rights violation.** Any capture, processing, or export of an artifact whose rights decision is `unknown`, `requires_review`, or prohibits that specific operation (§11.2).

---

## 14. State of the world at drafting

Recorded so that **S1** can be checked. Read-only queries; branch tips unchanged between 2026-08-15 and 2026-08-16.

| Repository / worktree | Branch | Commit | Working tree |
|---|---|---|---|
| `amr-evidence-warehouse` | `main` | `f7e42eb57cc0431e33b0576f5be10a51ad10ad2c` | 3 untracked Phase 0A drafts |
| `genotype-phenotype-mobility` | `agent/candidate-024` | `5285b44f33a0ec807a03b0617456397eb9748bfa` | 1 untracked: `two-model-roadmap.mhtml` |
| `model1-context-mic` | `feature/model1-context-mic` | `a13d4e9f2e84a5c32d528969a6367bc764df3ea3` | 1 untracked: `DATA_DISCOVERY_AND_ELIGIBILITY_AUDIT.md` |
| `assay-aware-emergence-risk` | `feature/assay-aware-emergence-risk` | `b3d439ad88ac4e14da1ad97437dfd7bf7b519634` | clean |
| `mobility-aware-amr-emergence` | `feature/public-sampling-frame` | `5fad4ef2075b8675fba5624103795e5e7e075979` | 1 untracked: `~WRL1004.tmp` |

The first four are **worktrees of one repository** (`mobility-aware-amr-mic-private`), sharing `main` at `dacba512ebbf7319cf40af5819556bf1bc0fd60d` and forking from `archive/first-thesis-mic-context` at `388285fc48753c59efbc718a6d4bab0582cc975c`. `CONFIRMED`.

**The table above is the 2026-08-15 baseline and is retained unrewritten.** Subsequent observed changes are appended below as dated notes, never merged into the original rows.

### 14.1 Baseline events

**Update observed 2026-08-16.** `mobility-aware-amr-emergence` no longer contains the untracked `~WRL1004.tmp` file recorded on 2026-08-15. HEAD remains `5fad4ef`; no tracked file is modified, and the working tree is now clean (`git status --porcelain --untracked-files=all` returns empty; `git diff --stat HEAD` returns empty). The file name is consistent with a temporary Microsoft Word lock file, but **the actor and the exact removal mechanism were not observed: `CANNOT DETERMINE`.** No Warehouse agent claims to have removed it. The original baseline is retained rather than rewritten.

### 14.2 How S1 treats a baseline change

Stop condition **S1** is not uniform across artifact classes. Three cases:

| Case | Treatment |
|---|---|
| **Tracked source mutation** — a tracked file modified, a branch tip moved, a commit rewritten | **Stop condition.** Halt and report before any further work |
| **Unexpected change to an untracked *substantive research artifact*** — e.g. `DATA_DISCOVERY_AND_ELIGIBILITY_AUDIT.md` or `two-model-roadmap.mhtml` appearing, changing, or disappearing | **Stop condition pending review.** These carry substantive claims (§8.5) and their disappearance would destroy the only copy |
| **Disappearance of an untracked temporary lock or editor file** — e.g. `~WRL1004.tmp` | **Recorded as a baseline event** in §14.1. Not a stop condition. It does not rewrite the earlier baseline, and **actor attribution remains `CANNOT DETERMINE`** unless directly observed |

In every case the rule is the same: **append a dated note; never edit the historical baseline.** Attributing an unobserved action to a named actor — the owner, an editor, or an agent — is prohibited; where the actor was not observed, the record says so.

---

## 15. What this plan does not yet contain

- No SQL. Migrations are 0C and require D9 plus approval of the entity model.
- No backup implementation (§16 states expectations; implementation depends on D9).
- No cost or timeline estimate.
- No public release, API, continuous ingestion, GROBID, or CI implementation — §§18–21 are architecture only.
- No adjudication of any scientific question.

---

## 16. Backup and recovery expectations

| Layer | Loss tolerance | Recovery path |
|---|---|---|
| Raw objects | **Zero** — the only irreplaceable layer once source repos change | Off-site replica of the content-addressed store under object lock; scheduled integrity sweep re-hashing every object against the external baseline (§7.5) |
| PostgreSQL evidence | Zero for assertions; adjudications and supersessions are **not** re-derivable | Daily logical dump + WAL archiving; dumps hashed, retained ≥90 days; restore rehearsed at least once in Phase 0 |
| Staging | Rebuildable from raw | Rebuild is the recovery path |
| Eligibility evaluations | Rebuildable from (contract, snapshot) | No separate backup, provided contracts are in Git |
| Cohort snapshots | **Zero** — a cohort backing a scientific claim must remain retrievable | Parquet + manifest replicated with the raw store; manifest and receipt in Git |
| Vector index | Fully disposable | Rebuild from raw |
| Git repository | Low | Remote plus local clones |

**Recovery objectives (`PROPOSED`, pending D9):** RPO 24 h for the database, 0 for raw objects. RTO 1 working day.

**Non-negotiable:** a restore must reproduce receipts and hashes exactly against the external baseline. Disagreement rejects the restore — **S2**.

---

## 17. Scale assumptions

**The previous assumption was wrong.** Revision 1 stated the largest table would hold 10⁴–10⁵ rows and that "performance is not a design driver". That is the size of the *current legacy estate*, not of the warehouse. One artifact alone contributes 12,843 rows; the estate contributes on the order of 10⁵ evidence rows before any locator, extraction candidate, or pipeline event is counted — and locators are one-to-many on assertions, extraction candidates are many-to-one on validated evidence, and continuous ingestion (§19) multiplies all of it.

`PROPOSED` — design for **millions to tens of millions** of rows in the largest relations: `provenance_locator`, `extraction_candidate`, `genotype_observation`, `pipeline_event`, `fetch_attempt`, `dedup_assertion`. Addressed **conceptually only**; nothing is implemented.

| Concern | Position |
|---|---|
| **Indexing** | Cover the join paths that matter: `(subject_entity_id, subject_kind)` on every registry-referencing table; `(sha256)` on `source_file`; `(isolate_id, drug_id, assay_id)` on observations; `(provenance_id)` on locators; partial indexes for `NOT EXISTS` supersession views. Avoid indexing wide JSONB payloads; index extracted scalar columns instead |
| **Bulk ingestion** | `COPY` into staging, set-based transforms into evidence, batched transactions with per-batch receipts. Never row-at-a-time application loops. Constraints stay enabled — a bulk load that requires dropping constraints is not permitted, because the constraints *are* the governance |
| **Partition candidates** | `provenance_locator`, `extraction_candidate`, `fetch_attempt`, and `pipeline_event` by capture/ingestion time; `genotype_observation` by `detection_run_id` or detection epoch. Evidence assertions are **not** partitioned by analysis, which would smuggle eligibility into physical layout |
| **Normalized transactional core** | The evidence layer stays normalized. Denormalization happens only in derived projections |
| **Analytical Parquet projections** | Wide, denormalized, columnar exports built from the core for analysis. Always derived, always hashed, never authoritative |
| **Oversized JSONB** | JSONB is for genuinely heterogeneous small payloads (locator shapes, predicate specs, receipts). **Raw API payloads, TEI documents, and full text do not go in JSONB** — they go to the object store, addressed by hash, with the row holding the hash. A hard size guideline and a test are proposed for 0C |
| **Raw payload retention** | Retention is a policy per source and rights decision, not a default-forever. Raw payloads are retained under object lock for the declared window; the *receipt* is retained permanently even where the payload is not |

---

## 18. `FUTURE PHASE — NOT AUTHORIZED` · Public release architecture

Recorded for planning. **No public release, website, or API is built, designed in detail, or enabled in Phase 0.** Stop condition **S13** applies.

### 18.1 The mandatory pipeline

**The private warehouse is never directly exposed.** There is no configuration in which a public reader queries the evidence database.

```
Private evidence warehouse
  → rights-filtered, versioned public release
    → read-only public database / API
      → scientific website and approved downloads
```

Each arrow is a **projection with a decision**, not a permission grant. Content crosses only by being copied into a new, narrower store.

### 18.2 The release invariant

> **No evidence becomes public merely because it exists in the Warehouse. Public exposure requires an explicit, versioned release decision, rights review, and a public-safe projection.**

Corollaries: absence from a release is not evidence of anything; a release is a snapshot, never a live mirror; withdrawing a release does not delete warehouse evidence; and no unadjudicated conflict, `unverified` assertion, or `requires_review` rights state may be released without an explicit decision naming it.

### 18.3 Proposed entities (`FUTURE PHASE — NOT AUTHORIZED`)

| Entity | Purpose | Key fields |
|---|---|---|
| `public_identifier` | A stable, citable identifier minted for a released item; **never** a warehouse primary key | `public_id` (opaque, stable), `entity_kind`, `internal_entity_id` FK, `minted_at`, `status`, `resolver_path` |
| `access_policy` | Named, versioned rule set determining what a given audience may see | `policy_id`, `policy_version`, `audience`, `rules` (JSONB), `derived_from_rights_dimensions` |
| `public_release` | One versioned release event | `release_id`, `release_version`, `title`, `snapshot_id` FK, `access_policy_id` FK, `rights_review_id` FK, `decided_by`, `decided_at`, `status ∈ {draft, approved, published, withdrawn}` |
| `public_release_item` | One item included in a release | `release_id` FK, `public_id` FK, `internal_entity_id` FK, `projection_rule_id`, `redaction_decision_id` FK NULL |
| `release_manifest` | Hashes of every released artifact | `release_id` FK, `entries` (path → sha256 → bytes), `manifest_sha256`, `signature` |
| `redaction_decision` | What was withheld or transformed, and why | `redaction_id`, `subject_entity_id` FK, `redaction_type ∈ {withheld, generalised, aggregated, masked}`, `reason_code`, `rights_dimension_invoked`, `decided_by` |
| `citation_rendering` | How a released item is to be cited, including upstream attribution | `public_id` FK, `citation_text`, `attribution_chain` (JSONB), `licence_statement`, `version` |
| `withdrawal_notice` | A public, permanent record that something was withdrawn | `notice_id`, `release_id` FK, `public_id` FK, `reason`, `effective_at`, `supersedes_public_id` NULL |
| `dataset_release` / `dataset_version` | A citable dataset product with its own version line | `dataset_id`, `dataset_version`, `release_id` FK, `doi` NULL, `changelog` |
| `api_version` | A versioned read-only API contract | `api_version`, `status ∈ {alpha, current, deprecated, retired}`, `schema_digest`, `sunset_at` |

**Withdrawal is append-only too.** A withdrawn release is marked and a `withdrawal_notice` is published; the release row is never deleted, because citations may already point at it.

**Explicitly out of Phase 0:** website frontend, API implementation, authentication, hosting, DOI registration, and any decision about what *would* be released.

---

## 19. `FUTURE PHASE — NOT AUTHORIZED` · Continuous Evidence Ingestion Pipeline

Recorded for planning. **Continuous discovery is prohibited in Phase 0** by §1.2 and stop condition **S9**. **No search was performed and none will be.**

### 19.1 The boundary that must never collapse

```
discovered candidate  ≠  extracted candidate assertion  ≠  validated evidence assertion
```

Three distinct populations with three distinct tables. A discovered record is a *search result*, not a fact. An extraction is a *proposal*, not a fact. Only validation against a resolvable locator in a captured raw object produces an evidence assertion. Counting extraction candidates as evidence would inflate every count in the warehouse and is the single largest risk of automated ingestion.

### 19.2 Proposed components (`FUTURE PHASE — NOT AUTHORIZED`)

| Component | Purpose |
|---|---|
| `source_connector` | A versioned adapter for one source (PubMed, PMC, NCBI Datasets, ENA, BV-BRC…), with its API version, auth mode, and rate policy |
| `query_registry` | The **exact** query text, filters, and parameters, registered and hashed **before** execution — the estate's own preregistration discipline |
| `ingestion_cursor` / `checkpoint` | Resumable position per (connector, query): page token, high-water mark, last successful timestamp. Prevents both gaps and silent re-ingestion |
| `fetch_attempt` | One request: URL, parameters, timestamp, HTTP status, retry count, payload bytes, payload SHA-256, outcome. Failures are recorded, not retried into invisibility |
| **rights pre-check** | A **blocking** gate evaluated **before** retrieval: if the rights decision for the source is `unknown`, `requires_review`, or prohibits storage/processing, the fetch does not occur. No "fetch now, decide later" |
| `raw_payload_receipt` | The capture receipt for the retrieved bytes, written once to the external baseline (§7.5) |
| `parsing_run` | One parse of one raw payload: parser, version, configuration, input hash, output hash, warnings |
| `extraction_candidate` | A proposed fact with a typed locator and a `confidence_diagnostic` — **not** evidence |
| `validation_queue` / `validation_decision` | Human or rule-based promotion of a candidate to an evidence assertion, or its rejection, with reason |
| `dedup_assertion` | An assertion that two records describe the same thing, with rule id and key — never a silent merge (§7.4 `duplicate_declaration`) |
| `dead_letter_item` | A payload or candidate that could not be processed, retained with its error. Never dropped |
| `schema_change_event` | A detected change in an upstream API or file schema, which **pauses** the connector rather than silently mis-parsing |
| `pipeline_health_event` | Rate limiting, quota exhaustion, latency, error bursts |
| `recall_audit` | Sentinel-based assessment of what a query *failed* to find. Currently **zero exist** in the estate (`CONFIRMED`); no search may be called exhaustive without one (`PROJECT_GOVERNANCE.md:153`) |

### 19.3 Invariants for the future pipeline

- Nothing is fetched before its rights pre-check passes.
- Every query is registered and hashed before execution.
- A failed fetch is a recorded fact, never an absence.
- A schema change pauses ingestion; it never degrades silently.
- Discovery breadth must exceed final eligibility (`PROJECT_GOVERNANCE.md:153`); new searches supplement, never replace, historical ones.

---

## 20. `FUTURE PHASE — NOT AUTHORIZED` · GROBID and document parsing

Recorded for planning. **GROBID is not installed, not downloaded, not configured, and not run.** Stop condition **S13** applies.

### 20.1 Source preference order — GROBID is fourth

Structured sources are always preferred, because every step down this list loses fidelity and adds inference:

1. **Publisher / PMC structured XML** (JATS) — authoritative table structure; `xml_node` locators via XPath.
2. **Supplementary CSV / XLSX / TSV** — already tabular; `tabular_cell` locators.
3. **Structured HTML** — recoverable table structure; `xml_node` or `tabular_cell` locators.
4. **PDF with GROBID** — structure is *inferred*; `document_text` and `figure` locators, with table extraction unreliable (§20.3).
5. **OCR for image-only documents** — structure and characters both inferred; `image_region` locators; lowest fidelity.

A parse from level *n* is never preferred over an available parse from level *n−1*, and the level used is recorded on every candidate.

### 20.2 GROBID output is never verified evidence

GROBID produces a **parse artifact** (TEI XML) and, downstream, **extraction candidates**. Neither is an evidence assertion. Promotion requires the §19.1 validation step against a resolvable locator. `extraction_method='grobid'` and `verification_state='unverified'` are mandatory on anything it produces.

### 20.3 What must be recorded per parse (`FUTURE PHASE — NOT AUTHORIZED`)

| Field | Why |
|---|---|
| `grobid_version`, `model_version` | Output changes between versions; a candidate is only reproducible against a pinned pair |
| `container_image_digest` | The image digest, not a tag — tags move |
| `input_pdf_sha256` | Binds the parse to exact input bytes |
| `tei_output_sha256`, `tei_object_uri` | TEI goes to the object store, **not** into JSONB (§17) |
| `parsing_configuration` | Consolidation flags, model selection, header/fulltext mode |
| `locator_mapping` | How TEI coordinates map to `document_text` / `figure` / `image_region` locators, so a candidate points at the source and not merely at the TEI |
| `rights_to_process`, `rights_to_retain_text` | **Separate dimensions** (§11.2). A PDF may be processable while its extracted text may not be retained or published |
| `table_extraction_limitations` | Recorded per parse. GROBID's table handling is weaker than its bibliographic and section handling; multi-row headers, `colspan` groupings, and footnote-qualified cells are where the estate has already been burned — the observed case where 16 of 19 columns sat under a `colspan` header reading *VITEK result* is exactly the failure a naive PDF table extraction would reproduce |
| `validation_state` | `unvalidated` → `validated` → `rejected`, with reason |

**Consequence of the `colspan` case:** no PDF-derived MIC candidate may be promoted to evidence without a human or rule confirming the **method attribution per drug**, because that is precisely the information PDF table extraction most reliably loses.

---

## 21. CI budget and workflow policy

Operational policy, governance-compatible. **This section does not authorize CI implementation in Phase 0A.**

**Observed state** (`CONFIRMED`, 2026-08-16, read-only): **zero** GitHub Actions workflows registered; **zero** historical workflow runs (`total_count: 0`); no `.github/` directory on disk, in git history, or on the remote; Actions permissions `{"enabled": true, "allowed_actions": "all"}`.

**Policy:**

1. **No workflow is to be created or enabled during this revision** or any Phase 0A work. `.github/workflows/` is not created.
2. **No GitHub Actions workflow runs on `push`.** No `on: push` trigger is permitted in any workflow, for any job, at any cost. There is no cheap-check exemption.
3. **No GitHub Actions workflow runs on `pull_request`.** No `on: pull_request` or `on: pull_request_target` trigger is permitted.
4. **Scheduled GitHub Actions may run only on Sundays.** Any `on: schedule` cron expression must restrict the day-of-week field to Sunday (`0` or `SUN`). A cron without a Sunday-restricted day-of-week field is a policy violation regardless of its hour.
5. **Manual dispatch is allowed only on Sundays.** `workflow_dispatch` exists but is not to be invoked on any other day. The restriction is on the operator; where enforceable, a workflow should additionally guard its first step on the runner's day-of-week and exit early otherwise.
6. **The Sunday restriction applies equally to expensive and inexpensive GitHub-hosted workflows.** Cost is not a criterion. A one-second lint job and a full reconciliation run are subject to the same rule, because the policy is about *when GitHub-hosted CI runs at all*, not about how much any one job costs.
7. **Cheap checks may run locally at any time**, on any day — `git diff --check`, linting, markdown reference validation, schema tests, the full test suite. Local execution is unrestricted and is the expected default during development. The Sunday rule governs **GitHub Actions only**.
8. **Before any workflow is added, estimate its expected private-repository Actions-minute consumption** and record the estimate alongside the workflow. A private repository meters Actions minutes where a public one does not — a consideration created by the D1 resolution.
9. **Workflow creation requires separate owner authorization.** This policy is not that authorization.
10. **Pin third-party actions to immutable commit SHAs**, never to tags or branches. Tags move; SHAs do not.
11. Actions settings, billing, spending limits, runner configuration, and retention are **not** to be modified. Actions is currently enabled and is neither to be enabled nor disabled.

> **Correction to revision 2.** Revision 2 stated that "cheap, fast checks may be considered for push triggers only after a cost estimate". That contradicted the owner's Sundays-only policy and is **withdrawn**. Push- and pull-request-triggered GitHub Actions are prohibited outright; cheap checks belong on the local machine, where they are unrestricted.

Violation of any of the above is stop condition **S13**.

---

## 22. Review checklist for this draft

- [ ] §1 scope matches owner intent for Phase 0
- [ ] §3 acceptance criteria — A3, A4, A8 strategies are enforceable as written
- [ ] §7.4 append-only supersession has no update path
- [ ] §7.6 referential design admits no dangling reference (A13)
- [ ] §7.7 typed locators cover every source form in the estate
- [ ] §11.2 rights dimensions are the right set
- [ ] §12 decisions D2–D11 recommendations are acceptable **as recommendations**
- [ ] §12.3 D3's separation of architectural agreement from ingestion authorization is understood
- [ ] §13 stop conditions, including revised S11 and new S13/S14, are sufficient
- [ ] §17 scale targets are realistic
- [ ] §18–§20 future architecture is complete enough to plan against, and clearly not authorized
- [ ] §21 CI policy is acceptable — in particular that **no** GitHub Actions workflow may run on push or pull_request, at any cost
- [ ] §12.3.0's three-way separation (inspection / extraction / capture) matches owner intent, and the narrow receipt-verification grant is acceptable
- [ ] `DATA_MODEL_PROPOSAL.md` §19.1 lifecycle-field register — every status is immutable-at-creation or event-derived, with no third option
- [ ] `DATA_MODEL_PROPOSAL.md` §19.2 nullable-UNIQUE audit, and the **PostgreSQL ≥ 15** minimum it implies for D9
- [ ] `DATA_MODEL_PROPOSAL.md` §4.2.1 storage-state design — five statuses, mandatory initial event, `current_storage_state` derived, and the separation of storage state from rights
- [ ] §12.3.0's Activity 1/2/3 boundary is workable in practice, in particular that row sampling and receipt verification are inspection
- [ ] §14.1/§14.2 baseline-event handling — append a dated note, never rewrite, actor `CANNOT DETERMINE` unless observed
- [ ] `❓Q25`'s event-sequence allocation applies to **all four** event relations, not just supersession

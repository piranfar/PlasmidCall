# PlasmidCall / P1.13 — project state reconciliation

**Dated** 2026-08-24 (UTC) · **Phase** 0 of the scientific-closure programme
**Repository** `https://github.com/piranfar/amr-evidence-warehouse` (private working repository; not publicly accessible) · branch `main`

> **Superseded, 2026-09-28.** This is a dated record of the state on 2026-08-24 and is kept
> as written, except that the repository line above now notes that the working repository is
> private and the text of section 4 was removed (see `docs/closure/RELEASE_STATUS_2026-09.md`). The commits it cites are in the private working repository. Truth has since
> been authorised, joined and evaluated, and the results are frozen
> (`docs/evidence/P1.13_results/RESULTS_FROZEN.json`). The public repository is
> github.com/piranfar/PlasmidCall, and the derived data are at doi:10.5281/zenodo.22086357.
> For the current status, read [`RELEASE_STATUS_2026-09.md`](RELEASE_STATUS_2026-09.md).
> The parsed call table holds 231,840 rows, not 231,841 (correction addendum, E6).

## 1. Repository state

| Item | State |
|---|---|
| Local HEAD | `03d2c7a` — "Archive the P1.13 server evidence and record the freeze-time state" |
| Remote HEAD (`origin/main`) | `03d2c7a` — identical; local and remote are in sync |
| Working tree | 38 untracked files, all pre-existing P1.9-era working documents (plans, evidence drafts) that predate this closure programme; none is a P1.13 artefact. Classified in Phase 4. No tracked file is modified. |
| Evidentiary commits | never amended, squashed or rewritten. The P1.13 chain is `da5b7a0 → 48e330a → e5ae86f → da84fa0 → cf7f417 → 647fd48 → 03d2c7a`. |

## 2. P1.13 terminal state (verified, not recalled)

| Artefact | State | Identity |
|---|---|---|
| Cohort v3 | frozen, 150 isolates, 25 per taxon | sha256 `874b0924deffef948dd50e00ee5c77c91d773354de4a1bb936162e4fec294205` |
| Replacement amendment | Amendment 005: SAMN26198730 excluded (contamination confirmed two independent ways), SAMN37639065 selected by the frozen deterministic rule | committed `e5ae86f` |
| Accepted assemblies | 150/150 under the fail-closed atomic gate; reconciliation PASS (0 rejected, 0 missing, 0 conflicts); 4/4 deterministic-rerun pilots byte-identical | per-isolate hashes bound in the freeze receipt |
| Panel units | 1,950/1,950 terminal: 1,878 OK, 72 deterministic tool-internal failures, all reviewed and classified; none infrastructure | `P1.13_PANEL_FAILURE_REVIEW.md` |
| Dependency audit | 1,950/1,950 receipts on the 13 frozen image ids, one id per image, zero drift | `P1.13_PANEL_DEPENDENCY_AUDIT.json` |
| Parsed call table | 231,841 rows, 19,320 contigs × 12 tools, byte-identical across two passes | sha256 `e3e43a0269336f2e88a670ef1b226d5ed56e616557e72ece0e41d873ffb4f48f` |
| Candidate contig table | 19,320 contigs, 9,784 eligible ≥1 kb, coverage 1.0000 ×3, deterministic rebuild byte-identical | sha256 `440f16bc7002c15135ac73a233545613ad6869eddf7d421cca6dc0a1060114f8` |
| Candidate manifest | `CANDIDATE_ONLY_NOT_FROZEN` at approval time | sha256 `bbe15fc247163c604ca55135ab3d8031a57aa1ae62f6451794a269591e135708` |
| **Prediction freeze** | **COMPLETE** — `P1.13-PREDICTION-FREEZE-001`, atomic, independently verified twice (fresh rebuild from raw inputs; independently written projection) | table `3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80`; receipt `98e7902ac09bcb54c759c119d6e273ce2474179fd908dee423b69ba414a9b482` |
| **Truth access** | **NONE, at any point.** No truth acquired, constructed, inspected, joined or scored. Unblinding is NOT authorized; the closure order explicitly does not confer it. | stop marker below |
| Stop markers | `P1.13_PREDICTIONS_READY_FOR_FREEZE_APPROVAL` (superseded by the freeze) and `P1.13_PREDICTIONS_FROZEN_AWAITING_TRUTH_AUTHORIZATION` (ACTIVE) | on server and in `docs/evidence/P1.13_provenance/` |

## 3. Server evidence archive and transfer status

| Item | State |
|---|---|
| Server archive | `/work/P1.13_EVIDENCE_ARCHIVE.tar.zst`, 15,427,604,570 bytes, sha256 `76201303af2a0322c03bb5e570d3174c20465736535ca089d2e4b9e235dd85d2` |
| Server-side verification | zstd stream integrity OK; FULL streaming re-hash of every member against the 87,961-row internal manifest: 87,961 ok, 0 bad, 0 extra, 0 missing (no sampling) |
| Documented exclusion | 751 container-owned scratch files under `p113/tmp/` (unreadable by the archiving user), verified to touch no evidence path; list preserved. Nothing deleted. |
| Reads | 86 GiB in place under `/data/p113_reads` (not duplicated: a second copy breaches the frozen 30 GiB reserves). Complete 604-row per-file sha256 manifest `f42a193f1d675c8935923408560c012f6bb632b2b7dac734d304ebdf41c1dbdd`; all raw files ENA-md5-verified at acquisition and publicly re-fetchable by run accession. |
| Local transfer | IN PROGRESS: 8 parts of ≤1.9 GiB each with per-part server hashes; ~10.7 of 14.37 GiB landed at reconciliation time; a resumable byte-offset fetch continues in the background. Reassembly must match the full archive sha256 before the local copy is called complete. |
| **Server termination** | **NOT yet safe.** Blocked solely on the local archive copy completing and hash-matching. The standing owner rule ("never terminate the instance or delete the Block Volume") also remains in force; termination is an owner action in any case. |

## 4. SSH key exposure status

Removed on 2026-09-28 at the owner's request. The execution host was retired on 2026-09-19.

## 5. Companion artefacts

* `P113_CANONICAL_ARTEFACT_INVENTORY.tsv` — one row per canonical artefact with role, path,
  size, sha256, producing stage, status, sensitivity/release class, reproduction-required flag.
* `P113_CURRENT_STATE.json` — machine-readable form of this reconciliation.

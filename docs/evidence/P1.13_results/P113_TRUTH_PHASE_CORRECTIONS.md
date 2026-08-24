# P1.13 truth- and evaluation-phase corrections — reconciled record

**Dated** 2026-08-24 · **Reconciled count: SEVEN**, not three and not five.

I previously recorded three. The owner identified five. Searching the complete server logs,
script backup inventory, decision record and session execution history reconciles the count to
**seven** distinct implementation-integrity corrections in the truth and evaluation phases.

**Every one is an implementation-integrity correction. None is a scientific protocol change.**
The following were not altered by any of them, and this is asserted per defect below:
scientific protocol · frozen predictions · truth labels · thresholds · cohort membership ·
models · router · eligibility rules.

Binding invariants, verified after all seven corrections:

| Invariant | Value | Verified |
|---|---|---|
| Frozen prediction table sha256 | `3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80` | unchanged, re-verified at join and at results freeze |
| Cohort v3 sha256 | `874b0924deffef948dd50e00ee5c77c91d773354de4a1bb936162e4fec294205` | unchanged |
| Isolates | 150 | unchanged |
| Thresholds | 0.9285 / 0.9524 / 0.9605 | never re-derived |
| Truth labels | 7,130 chromosome · 2,241 plasmid · 413 unresolved | never coerced, never edited |

---

## TC1 — freeze-status representation mismatch

| | |
|---|---|
| **When** | 2026-08-24 ~04:05 UTC |
| **Affected execution** | first invocation of `p113_acquire_truth.py` |
| **Failed output** | `REFUSING: predictions status is 'PREDICTIONS_FROZEN', not FROZEN.` — acquisition refused, 0 isolates fetched |
| **Cause** | the derived acquirer inherited P1.11's gate, which tested `status == "FROZEN"`. P1.11's operational marker carried `status: "FROZEN"` with `freeze_status_detail: "PREDICTIONS_FROZEN"`; the P1.13 freezer writes `status: "PREDICTIONS_FROZEN"` directly. Two representations of one state. |
| **Correction** | explicit allowlist `{"FROZEN", "PREDICTIONS_FROZEN"}` so anything else — notably `CANDIDATE_ONLY_NOT_FROZEN` — still fails closed. The gate was simultaneously **strengthened**, not merely relaxed: it now also binds the authorised `freeze_id`, re-hashes the frozen prediction table against the authorisation, and requires the receipt to assert truth-blindness at freeze time. |
| **Rerun evidence** | `logs/acquire_truth.log`: `freeze identity verified: P1.13-PREDICTION-FREEZE-001 / table 3bc733c0adab6e38` |
| **Proof of no scientific change** | the gate is a precondition on *whether* truth may be acquired. No prediction, label, threshold or cohort row is read or written by it. The frozen table hash was re-verified by the gate itself and matched. |

## TC2 — cohort-v3 truth-acquisition schema mismatch causing a silent zero

| | |
|---|---|
| **When** | 2026-08-24 ~04:07 UTC |
| **Affected execution** | second invocation of `p113_acquire_truth.py` |
| **Failed output** | receipt `{"isolates": 150, "verified": 0, "incomplete": 0}`, `TRUTH_ACQUISITION_INCOMPLETE`, `truth_hold` empty. **Zero verified with zero failures** — the most dangerous shape a failure can take. |
| **Cause** | the acquirer read `ftppath_refseq` / `ftppath_genbank`, columns of the P1.11 sealed cohort. Cohort v3 carries `ftp_path` + `summary_source`. `dict.get()` returned empty for all 150 rows and the loop `continue`d past every isolate without raising. |
| **Correction** | fail-loud `REQUIRED_COLUMNS` schema check that aborts (`exit 4`) on a missing or renamed column, on any blank `ftp_path`, or on an unrecognised `summary_source`; plus explicit mapping onto the v3 schema (149 refseq, 1 genbank). |
| **Rerun evidence** | `cohort schema verified: 150 rows, every one with ftp_path and a known summary_source`, then 150 × `VERIFIED`, `TRUTH_ACQUISITION_COMPLETE`. |
| **Proof of no scientific change** | no truth existed on the host when this was detected, so no label could have been affected. The path used per isolate is taken from the **frozen cohort record**; nothing was re-resolved from NCBI after predictions existed. |
| **Note** | this is the third silent-zero-from-schema-mismatch in this programme (two earlier ones in candidate discovery). The fail-loud check is the standing remedy. |

## TC3 — missing byte-identical helper module during mapping

| | |
|---|---|
| **When** | 2026-08-24 04:13:24 UTC |
| **Affected execution** | first full truth-mapping run, **all 150 isolates** |
| **Failed output** | `logs/truth_map.log`: `truth mapping: ok=0 failed=150`, `TRUTH MAPPING GATE FAILED (ok=0 bad=150, require 150/0)`; every per-isolate log ends `ModuleNotFoundError: No module named 'p111_accession_resolution'` |
| **Cause** | the mapper is a byte-identical copy of the frozen P1.12 pipeline and imports a sibling helper that lived only in the P1.12 script directory. |
| **Correction** | `p111_accession_resolution.py` copied into `p113/env/` **byte-identically** (sha `b007a20c1fe5f993` on both sides). The mapper itself was not modified. |
| **Rerun evidence** | `truth mapping: ok=150 failed=0`, `TRUTH_MAP_GATE_PASSED`. Both runs are retained in `logs/truth_map.log` (two `granting READ` blocks). |
| **Proof of no scientific change** | the failed run produced **no** `truth_table.tsv` for any isolate, so no label existed to be affected. The mapper's thresholds (identity 0.95, coverage 0.80, margin 0.10, minlen 1000) and its sha256 are unchanged, and it remains byte-identical to the frozen P1.12 mapper. `truth_hold` lockdown was correctly restored to 700 even on the failed run. |

## TC4 — stale pre-Amendment-005 depth covariate table

| | |
|---|---|
| **When** | 2026-08-24 ~04:47 UTC |
| **Affected execution** | first invocation of `p113_strata.py` |
| **Failed output** | `KeyError: 'SAMN37639065'` — stratification aborted before writing any output |
| **Cause** | `P1.13_DEPTH_COVARIATE.csv` was generated before Amendment 005. It still listed the excluded isolate `SAMN26198730` and lacked the replacement `SAMN37639065`. |
| **Correction** | regenerated from the 150 current downsample receipts and restricted to cohort v3; verified `in cohort not in receipts: none`, `in receipts not in cohort: none`. |
| **Rerun evidence** | strata recomputed as 8 / 24 / 24 / 94 with modes 56 passthrough / 94 downsampled; replacement present. |
| **Proof of no scientific change** | the stratum boundaries are the already-frozen technical thresholds with the declared ±0.5× tolerance at the 100× boundary only. **Counts are identical to the pre-correction values (8/24/24/94)** because the replacement isolate fell in the same depth stratum as the excluded one. No depth value was recomputed or altered; the table was rebuilt from receipts that predate truth access. |

## TC5 — case-sensitive Boolean mismatch producing an empty ARG-bearing stratum

| | |
|---|---|
| **When** | 2026-08-24 ~04:52 UTC |
| **Affected execution** | `p113_strata.py`, ARG-bearing stratum only |
| **Failed output** | the `=== ARG-bearing ===` section printed **no rows** — an empty stratum with no error raised |
| **Cause** | the filter compared `ARG_bearing_bool == "True"`; the column stores lowercase `true` / `false`. |
| **Correction** | case-normalised comparison (`str(x).strip().lower()`). |
| **Rerun evidence** | ARG-bearing n = 635 with v1.2-General PPV 0.9409 / recall 0.7782 and router 0.9494 / 0.2820. |
| **Proof of no scientific change** | this defect **suppressed** an analysis rather than distorting one. No other stratum, metric or label was touched. Its correction is material to the conclusion — the ARG-bearing result is now central and is reported in the abstract. |

## TC6 — matched-denominator inventory omitted the three frozen baselines

| | |
|---|---|
| **When** | 2026-08-24, identified during owner reconciliation |
| **Affected execution** | first invocation of `p113_final_analyses.py` |
| **Failed output** | matched-denominator table built over 16 predictors (4 model/router rows + 12 tools), omitting `majority_vote`, `any_tool_plasmid` and `all_chromosome` |
| **Cause** | the matched-comparison predictor dictionary was assembled from the model and tool sets and did not include the predeclared baselines, which existed in the pooled comparator table. |
| **Correction** | all three baselines added, giving the complete **19-row** inventory; plus a new explicit `P113_PREDICTOR_INVENTORY.tsv` recording, per method, its class, frozen status, evaluable denominator, failure states, matched-denominator inclusion and any ineligibility reason. |
| **Rerun evidence** | see `P113_MATCHED_DENOMINATOR_METRICS.tsv` and `P113_PREDICTOR_INVENTORY.tsv` |
| **Proof of no scientific change** | a matched comparison is a **secondary/exploratory** analysis. The primary endpoint, its denominator and its interpretation are computed from the pooled analysis, which always contained all 19 rows. No frozen method was collapsed, and the degenerate `all_chromosome` baseline is retained and reported as PPV-undefined rather than dropped. |

## TC7 — the acquisition log was overwritten by successive runs

| | |
|---|---|
| **When** | discovered 2026-08-24 during this reconciliation |
| **Affected execution** | `p113_acquire_truth.py`, runs 1 and 2 |
| **Failed output** | **the failure text for TC1 and TC2 is no longer on the server.** The launcher redirected with `>` rather than `>>`, so each rerun truncated `logs/acquire_truth.log`. It now contains only the successful third run. |
| **Cause** | log truncation in the launch command, not in the script. |
| **Correction** | the failure outputs are preserved in the session execution record and are quoted verbatim in TC1 and TC2 above. The truth **mapping** log used `>>` and correctly retains both the failed and successful runs. Future launches must append. |
| **Proof of no scientific change** | a logging-retention defect. It affects the completeness of the evidence trail, not any artefact, label or metric. |
| **Disclosure** | recorded here rather than concealed. This is a genuine gap in the preservation guarantee: I asserted that failed executions are preserved, and for the two acquisition failures the server-side log is not. |

---

## Reconciliation summary

| # | Defect | Phase | Class | Scientific impact |
|---|---|---|---|---|
| TC1 | freeze-status representation mismatch | truth acquisition | implementation integrity | none |
| TC2 | cohort-v3 schema mismatch → silent zero | truth acquisition | implementation integrity | none |
| TC3 | missing byte-identical helper module | truth mapping | implementation integrity | none |
| TC4 | stale pre-Amendment-005 depth table | stratification | implementation integrity | none |
| TC5 | case-sensitive Boolean → empty stratum | stratification | implementation integrity | none (suppressed an analysis) |
| TC6 | matched inventory omitted 3 baselines | evaluation | implementation integrity | none (secondary analysis) |
| TC7 | acquisition log truncated by rerun | logging | evidence-preservation defect | none |

**Scientific protocol changes in the truth and evaluation phases: ZERO.**

No model was retrained, refit or retuned after truth access. No threshold was changed or
re-derived. No router was redesigned. No isolate was replaced or excluded on the basis of an
outcome. No eligibility rule was modified. No unresolved truth label was coerced. No
leave-one-species-out or other post-truth modelling was performed.

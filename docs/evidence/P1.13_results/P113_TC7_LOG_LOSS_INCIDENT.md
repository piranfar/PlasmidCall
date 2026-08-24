# TC7 — incident record: truth-acquisition failure logs overwritten

**Dated** 2026-08-24 (contemporaneous with discovery) · **Class** evidence-preservation defect
**Status** LOSS — not preserved, not recovered, not reconstructed

---

## What happened

The truth-acquisition launcher used **truncating redirection**:

```
setsid nohup python3 env/p113_acquire_truth.py > logs/acquire_truth.log 2>&1 < /dev/null &
```

`>` truncates. `p113_acquire_truth.py` was invoked three times. Each invocation truncated
`logs/acquire_truth.log` and wrote from byte zero. **The server-side logs of the two failed runs
were overwritten and no longer exist.**

## What is lost

* The original `logs/acquire_truth.log` produced by acquisition run 1 (the freeze-status refusal,
  TC1).
* The original `logs/acquire_truth.log` produced by acquisition run 2 (the silent-zero schema
  mismatch, TC2).
* **The SHA-256 values, byte sizes and modification timestamps of those two files are
  unavailable.** They were never computed before the files were overwritten, and they cannot be
  computed now. No hash, size or timestamp for either lost file is asserted anywhere in this
  project's records, and none may be constructed.

## What survives

| Surviving evidence | Nature |
|---|---|
| Session execution record | the assistant/operator session in which the failing commands were run and their console output was returned |
| Observed error text | **a transcription from that session record** — see the explicit caveat below |
| Script versions | `env/p113_acquire_truth.py` in its corrected form, plus the derivation diff `provenance/DERIVATION_TRUTH_CHAIN.diff` showing what was changed from the frozen P1.11 acquirer |
| Successful rerun artefacts | `logs/acquire_truth.log` for run 3 (the successful run), `receipts/P1.13_truth_acquisition_receipt.json` (150 verified / 0 incomplete), and the 150 `truth_hold/<isolate>/` artefact sets with their NCBI md5 verifications |

## Caveat on the quoted error text — read this before citing it

The error strings quoted for TC1 and TC2 in `P113_TRUTH_PHASE_CORRECTIONS.md`:

```
REFUSING: predictions status is 'PREDICTIONS_FROZEN', not FROZEN.
{"isolates": 150, "verified": 0, "incomplete": 0}
TRUTH_ACQUISITION_INCOMPLETE
```

are a **transcription from the surviving session record**. They are **not** a recovered original
log file, **not** a reconstruction of one, and **not** byte-verifiable against anything. They
should be read as a contemporaneous human-and-tool-readable account of what was observed, at the
evidentiary level of a lab notebook entry — not at the level of the hash-bound artefacts that
constitute the rest of this project's provenance.

Nothing in this project claims those two log files are preserved.

## Scope of the limitation

**Affected:** execution-provenance *completeness* for the truth-acquisition phase. A future auditor
can verify what the corrected acquirer does, that it succeeded, and what it produced — but cannot
independently re-verify the byte content of the two failure runs.

**Not affected**, each independently hash-verified after the corrections:

| Artefact | Status |
|---|---|
| Frozen predictions | `3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80`, re-verified at join and at results freeze |
| Cohort v3 | `874b0924deffef948dd50e00ee5c77c91d773354de4a1bb936162e4fec294205` |
| Acquired truth files | 150 isolates × 3 artefacts, each verified against NCBI's own `md5checksums.txt` at acquisition |
| Truth mapping outputs | 150 `truth_table.tsv`, each hashed individually in the results freeze |
| Joined truth–prediction labels | `P113_TRUTH_JOINED.tsv`, hashed; join performed exactly once |
| Evaluated results | all metric tables hashed; independently re-derived by a verifier sharing no code with the evaluation |

The two lost files were **console logs of runs that produced no scientific artefact**. Run 1 fetched
nothing (refused at the gate). Run 2 fetched nothing (`truth_hold` was empty; 0 verified). No truth
file, label, prediction or metric traces to either run.

## Correction going forward

Launchers in this project must append (`>>`), not truncate (`>`). The truth **mapping** launcher
already used `>>` and correctly retains both its failed (150/150 failed) and successful (150/150
ok) runs in `logs/truth_map.log`, which is the behaviour the acquisition launcher should have had.

## Disclosure note

I had previously asserted that failed executions are preserved. For these two runs that assertion
was **false on the server**, and this record exists to correct it rather than to soften it.

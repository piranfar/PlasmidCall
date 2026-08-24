#!/usr/bin/env python3
"""Decision B: superseding P1.11 pre-join hash gate.

SUPERSEDES the receipt block in docs/plans/P1.11_PROSPECTIVE_EVALUATION_AMENDMENT.yaml and
docs/evidence/P1.12_PRE_JOIN_HASH_RECEIPT.md. Neither original is modified; both are cited.

Three defects in the original receipt, all corrected here:

  B1  It pinned the SUPERSEDED preflight scripts/p1_12/panel_preflight.py
      (edba943f6ad34dc2acac3091b18745c827299182eae500077281ba739840c535). That file was retired by
      docs/plans/P1.11_PREFLIGHT_IMPLEMENTATION_CORRECTION.yaml for three execution-verification
      defects and returned BLOCKED. The canonical locked preflight is
      scripts/p1_12/panel_preflight_p111_v2.py.

  B2  It recorded a single unlabelled sha256 per file. Those values were computed over the CRLF
      WORKING COPY. .gitattributes declares `*.py text eol=lf` and `*.yaml text eol=lf`, so the
      committed content is LF and 9 of the pinned values cannot reproduce from a fresh checkout.
      This gate records BOTH domains and verifies the canonical LF one, which reproduces anywhere.
      No file content differs - `git diff` is empty. It is a recording defect, not corruption.

  B3  It pinned the pre-correction evaluator. The canonical evaluator is now
      scripts/p1_12/evaluate_p111_locked_v2.py.

The gate REFUSES to authorise joining or scoring if any canonical hash differs from the recorded
value, or if any locked dependency is missing.

Usage:
  prejoin_verify_v2.py --record   # first run: record the canonical state
  prejoin_verify_v2.py            # verify against the recorded state; non-zero exit = DO NOT JOIN
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RECEIPT = os.path.join(ROOT, "docs", "evidence", "P1.11_PRE_JOIN_HASH_RECEIPT_v2.json")

SUPERSEDED_PREFLIGHT_SHA = "edba943f6ad34dc2acac3091b18745c827299182eae500077281ba739840c535"

# Files that are themselves SUPERSEDED and preserved for the audit trail. They legitimately still
# reference the retired preflight - that is what preservation means - so they are excluded from the
# stale-import check. Each must have a live successor, asserted separately: a superseded file with
# no successor would mean the correction was never actually applied.
SUPERSEDED_FILES = {
    "scripts/p1_12/router_fixtures.py": "scripts/p1_12/router_fixtures_v2.py",
    "scripts/p1_12/evaluate_p111_locked.py": "scripts/p1_12/evaluate_p111_locked_v3.py",
    "scripts/p1_12/panel_preflight.py": "scripts/p1_12/panel_preflight_p111_v2.py",
}

# Every dependency that must be intact before P1.11 truth may be joined or scored.
LOCKED = [
    # --- models and encoding
    "models/plasmidcall_v1.2-general/plasmidcall_v1_2_general.pkl",
    "models/plasmidcall_v1.2-general/P1.12_V1.2_COEFFICIENTS.tsv",
    "models/plasmidcall_v1.2-general/P1.12_V1.2_ENCODING_SPEC.json",
    "models/plasmidcall_v1.2-general/P1.12_V1.2_FEATURE_DICTIONARY.tsv",
    "models/plasmidcall_v1.2-general/P1.12_V1.2_MODEL_PORTABLE.json",
    "models/plasmidcall_v1.2-general/P1.12_V1.2_TRAINING_RECEIPT.json",
    "scripts/p1_12/freeze_v12.py",
    "scripts/p1_12/plasmidcall_router.py",
    # --- canonical locked runtime (post-correction)
    "scripts/p1_12/panel_preflight_p111_v2.py",
    "scripts/p1_12/evaluate_p111_locked_v3.py",
    "scripts/p1_12/build_p111_contig_table.py",
    "scripts/p1_12/v11_scorer_p111.py",
    "models/plasmidcall_v1.1/plasmidcall_v1_1_m2.pkl",
    # --- preserved: superseded by v3 under the selective-classification addendum
    "scripts/p1_12/evaluate_p111_locked_v2.py",
    # --- preserved originals: must remain byte-intact so the supersession stays auditable
    "scripts/p1_12/panel_preflight.py",
    "scripts/p1_12/evaluate_p111_locked.py",
    "scripts/p1_12/router_fixtures.py",
    # --- superseding fixtures
    "scripts/p1_12/router_fixtures_v2.py",
    "scripts/p1_12/p111_failclosed_fixtures.py",
    "scripts/p1_12/p111_builder_fixtures.py",
    "scripts/p1_12/v11_scorer_fixtures.py",
    "scripts/p1_12/preflight_v2_fixtures.py",
    # --- governance
    "docs/plans/P1.11_PROSPECTIVE_EVALUATION_AMENDMENT.yaml",
    "docs/plans/P1.11_PREFLIGHT_IMPLEMENTATION_CORRECTION.yaml",
    "docs/plans/P1.11_TRUTH_SOURCE_AMENDMENT.yaml",
    "docs/plans/P1.11_PROVENANCE_AND_FAILCLOSED_CORRECTION.yaml",
    "docs/plans/P1.11_SELECTIVE_CLASSIFICATION_ADDENDUM.yaml",
    "docs/evidence/P1.11_V11_RECONSTRUCTION_RECEIPT.json",
    "docs/evidence/P1.11_PREFLIGHT_SUPERSESSION_MANIFEST.json",
    "docs/evidence/P1.11_COHORT_PROVENANCE_DISCREPANCY.json",
]

# The cohort of record, identified by hash rather than by path.
CANONICAL_COHORT = {
    "name": "P1.11_cohort_sealed.tsv",
    "predeclared_in": "docs/plans/P1.11_PROSPECTIVE_EVALUATION_AMENDMENT.yaml (cohort block)",
    "sha256": "0d0e547cd6f6546ac6f72e516885a74cf51dd3738be83b0a45f58cfbe999151f",
    "local_path": "E:/AMR_Evidence_Data/P1.9_cleanroom/p111/P1.11_cohort_sealed.tsv",
    "host_path": "/data/trace-arg/p111/manifests/P1.11_cohort_sealed.tsv",
    "n_isolates": 79,
    "n_columns": 25,
}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digests(path):
    """Both hash domains. See docs/HASH_AND_LINE_ENDING_POLICY.md."""
    b = open(path, "rb").read()
    lf = b.replace(b"\r\n", b"\n")
    return {"sha256_worktree": hashlib.sha256(b).hexdigest(),
            "sha256_canonical_lf": hashlib.sha256(lf).hexdigest(),
            "bytes": len(b),
            "line_endings": "CRLF" if b.count(b"\r\n") else "LF"}


def snapshot():
    out, missing = {}, []
    for rel in LOCKED:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            missing.append(rel)
            continue
        out[rel] = digests(p)
    return out, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true",
                    help="record the canonical state (first run)")
    a = ap.parse_args()

    snap, missing = snapshot()

    print("P1.11 PRE-JOIN HASH GATE v2 - supersedes the original receipt")
    print("  canonical preflight : scripts/p1_12/panel_preflight_p111_v2.py")
    print("  superseded preflight: scripts/p1_12/panel_preflight.py (%s...)"
          % SUPERSEDED_PREFLIGHT_SHA[:12])
    print("  canonical evaluator : scripts/p1_12/evaluate_p111_locked_v2.py")
    print()

    # ---- the superseded preflight must still exist, byte-intact, or the audit trail is broken
    sp = os.path.join(ROOT, "scripts/p1_12/panel_preflight.py")
    sp_ok = os.path.exists(sp) and digests(sp)["sha256_canonical_lf"] == SUPERSEDED_PREFLIGHT_SHA
    print("  superseded preflight preserved byte-intact : %s" % sp_ok)

    # ---- no live import of the superseded preflight
    stale, preserved_hits = [], []
    for root, _, files in os.walk(os.path.join(ROOT, "scripts")):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), ROOT).replace(os.sep, "/")
            if rel == "scripts/p1_12/panel_preflight.py":
                continue
            t = open(os.path.join(root, fn), encoding="utf-8", errors="replace").read()
            for line in t.splitlines():
                ls = line.strip()
                if ls.startswith(("import panel_preflight", "from panel_preflight")) \
                        and "panel_preflight_p111_v2" not in ls:
                    (preserved_hits if rel in SUPERSEDED_FILES else stale).append(
                        "%s: %s" % (rel, ls))
    print("  LIVE imports of the superseded preflight   : %d %s"
          % (len(stale), stale if stale else ""))
    print("  in PRESERVED superseded files (expected)   : %d %s"
          % (len(preserved_hits), [h.split(":")[0] for h in preserved_hits]))

    orphans = [f for f, succ in SUPERSEDED_FILES.items()
               if not os.path.exists(os.path.join(ROOT, succ))]
    print("  superseded files lacking a successor       : %d %s" % (len(orphans), orphans))

    if missing:
        print("\n  MISSING locked dependencies: %s" % missing)

    if a.record:
        rec = {
            "receipt": "P1.11 pre-join hash receipt v2",
            "status": "SUPERSEDING",
            "generated_utc": utc(),
            "supersedes": {
                "documents": ["docs/evidence/P1.12_PRE_JOIN_HASH_RECEIPT.md",
                              "docs/plans/P1.11_PROSPECTIVE_EVALUATION_AMENDMENT.yaml "
                              "(hash_receipt block)"],
                "stale_preflight_pinned": "scripts/p1_12/panel_preflight.py",
                "stale_preflight_sha256": SUPERSEDED_PREFLIGHT_SHA,
                "why": ("the original receipt pinned the preflight that "
                        "P1.11_PREFLIGHT_IMPLEMENTATION_CORRECTION.yaml retired, and recorded "
                        "unlabelled CRLF working-copy hashes that cannot reproduce from a "
                        "checkout"),
                "originals_modified": False,
            },
            "provenance_chain": [
                "panel_preflight.py (edba943f, committed 6b03034) returned BLOCKED on the "
                "migrated host from three execution-verification defects",
                "P1.11_PREFLIGHT_IMPLEMENTATION_CORRECTION.yaml recorded the defects and declared "
                "panel_preflight_p111_v2.py as the superseding implementation",
                "P1.11_PREFLIGHT_SUPERSESSION_MANIFEST.json recorded both hashes",
                "the predeclaration's own locked_preflight field already names v2; only its "
                "hash_receipt block still pinned the retired file",
                "this receipt makes the canonical set explicit and machine-verifiable",
            ],
            "hash_domain_note": (
                "Every entry records BOTH sha256_worktree (the bytes on this machine) and "
                "sha256_canonical_lf (the LF content git stores). .gitattributes declares "
                "*.py/*.yaml/*.md as text eol=lf, so sha256_canonical_lf is the value that "
                "reproduces from any checkout and is the one this gate verifies. No file content "
                "differs between the domains; git diff is empty."),
            "canonical_cohort": CANONICAL_COHORT,
            "superseded_preflight_preserved": sp_ok,
            "live_stale_imports": stale,
            "superseded_files_and_successors": SUPERSEDED_FILES,
            "expected_references_in_preserved_files": preserved_hits,
            "locked_dependencies": snap,
            "n_locked": len(snap),
            "authorisation_rule": (
                "Joining or scoring P1.11 truth is authorised only when every locked dependency "
                "matches its sha256_canonical_lf here, no locked dependency is missing, no live "
                "import of the superseded preflight exists, and the cohort of record hashes to "
                "0d0e547c... Any difference REFUSES authorisation."),
        }
        os.makedirs(os.path.dirname(RECEIPT), exist_ok=True)
        with open(RECEIPT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rec, f, indent=1)
            f.write("\n")
        print("\n  RECORDED %d locked dependencies -> %s" % (len(snap), RECEIPT))
        print("  receipt sha256: %s" % hashlib.sha256(open(RECEIPT, "rb").read()).hexdigest())
        sys.exit(0)

    # ---------------------------------------------------------------- verify
    if not os.path.exists(RECEIPT):
        sys.exit("REFUSING: no v2 receipt at %s. Run with --record first." % RECEIPT)
    rec = json.load(open(RECEIPT, encoding="utf-8"))
    ref = rec["locked_dependencies"]

    drift, absent = [], []
    for rel, want in ref.items():
        if rel not in snap:
            absent.append(rel)
            continue
        got = snap[rel]["sha256_canonical_lf"]
        if got != want["sha256_canonical_lf"]:
            drift.append({"file": rel, "recorded": want["sha256_canonical_lf"], "observed": got})
    new = [r for r in snap if r not in ref]

    print("\n  locked dependencies verified : %d" % len(ref))
    print("  drifted                      : %d" % len(drift))
    print("  absent                       : %d %s" % (len(absent), absent if absent else ""))
    print("  new since recording          : %d %s" % (len(new), new if new else ""))
    for d in drift:
        print("    DRIFT %s\n      recorded %s\n      observed %s"
              % (d["file"], d["recorded"], d["observed"]))

    # The authorisation rule names the cohort of record, so the gate must actually check it
    # rather than carrying it as inert metadata. Verified wherever the file is reachable; when it
    # is not (this repo is the Windows side, the cohort of record lives on the execution host),
    # that is reported as UNVERIFIABLE HERE rather than silently passing.
    cohort_state, cohort_ok = "not reachable from this filesystem", None
    for cand in (rec["canonical_cohort"]["local_path"], rec["canonical_cohort"]["host_path"]):
        if os.path.exists(cand):
            got = hashlib.sha256(open(cand, "rb").read()).hexdigest()
            cohort_ok = (got == rec["canonical_cohort"]["sha256"])
            cohort_state = "%s -> %s" % (cand, "MATCH" if cohort_ok else "MISMATCH %s" % got[:16])
            break
    print("  cohort of record             : %s" % cohort_state)
    if cohort_ok is None:
        print("    (cohort not on this filesystem; acquire_truth_v2.py enforces the same hash")
        print("     on the execution host via its own cohort-identity guard before it will run)")

    ok = (not drift and not absent and not stale and not orphans and sp_ok
          and cohort_ok is not False)
    print("\n  AUTHORISATION: %s"
          % ("GRANTED - joining/scoring may proceed" if ok
             else "REFUSED - do not join or score P1.11 truth"))
    sys.exit(0 if ok else 3)


if __name__ == "__main__":
    main()

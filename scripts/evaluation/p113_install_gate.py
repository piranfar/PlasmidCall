#!/usr/bin/env python3
"""Insert the reconciliation gate between phase 3 and phase 4, and switch to cohort v3.

Run ONLY while the runner is stopped. Idempotent: re-running makes no further change.
"""
import io, os, shutil, subprocess, sys

P = "/work/p113"
os.chdir(P)

if subprocess.run(["pgrep", "-f", "[p]113_run.sh"], capture_output=True).returncode == 0:
    print("REFUSING: runner is alive")
    sys.exit(1)

p = "env/p113_run.sh"
s = io.open(p, encoding="utf-8").read()

if "RECONCILIATION before phase 4" in s:
    print("gate already installed")
else:
    shutil.copy(p, p + ".pre_reconcile_gate")
    anchor = 'say "PHASE 4 panel: 13 units x $SD isolates"'
    gate = '''# ------------------------------------------------------------------ reconciliation gate
# Operator rule 2026-08-23: the panel does not start unless every one of the 150 cohort isolates
# holds an accepted, validated, hash-checked assembly. Fail closed.
say "RECONCILIATION before phase 4"
if ! python3 "$P/env/p113_asm_reconcile.py" >> "$LOGD/reconcile.log" 2>&1; then
  say "RECONCILIATION FAILED - see P1.13_ASSEMBLY_RECONCILIATION.json and logs/reconcile.log"
  tail -25 "$LOGD/reconcile.log" 2>/dev/null | while IFS= read -r l; do say "  $l"; done
  exit 26
fi
say "RECONCILIATION PASSED: 150 accepted, validated assemblies"

''' + anchor
    assert s.count(anchor) == 1, "anchor count %d" % s.count(anchor)
    s = s.replace(anchor, gate)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("reconciliation gate installed before phase 4")

# switch every production reference to the amended cohort v3
changed = []
for f in ("env/p113_run.sh", "env/p113_assembly_accept.py", "env/p113_asm_reconcile.py"):
    t = io.open(f, encoding="utf-8").read()
    if "P1.13_SELECTED_COHORT_v2.tsv" in t:
        if not os.path.exists(f + ".pre_v3cohort"):
            shutil.copy(f, f + ".pre_v3cohort")
        io.open(f, "w", encoding="utf-8", newline="\n").write(
            t.replace("P1.13_SELECTED_COHORT_v2.tsv", "P1.13_SELECTED_COHORT_v3.tsv"))
        changed.append(f)
print("switched to cohort v3: %s" % (changed or "already on v3"))

assert subprocess.run(["bash", "-n", "env/p113_run.sh"]).returncode == 0
for f in ("env/p113_assembly_accept.py", "env/p113_asm_reconcile.py"):
    compile(io.open(f, encoding="utf-8").read(), f, "exec")
print("syntax OK")

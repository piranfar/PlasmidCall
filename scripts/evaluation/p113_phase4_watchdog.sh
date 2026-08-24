#!/usr/bin/env bash
# Stop the runner the moment it enters phase 4. Reconciliation at 150 must gate the panel, and
# the running script cannot be edited safely in place. Lets the final assembly complete first.
set -uo pipefail
P=/work/p113
cd "$P"
for i in $(seq 1 3000); do
  if ! pgrep -f "[p]113_run.sh" >/dev/null; then echo "$(date -u +%FT%TZ) runner exited on its own"; break; fi
  if grep -q "PHASE 4 panel" logs/p113_master.log 2>/dev/null; then
    echo "$(date -u +%FT%TZ) PHASE 4 detected - stopping runner before the panel does work"
    kill $(pgrep -f "[p]113_run.sh") 2>/dev/null; sleep 3
    kill -9 $(pgrep -f "[p]113_run.sh") 2>/dev/null
    for c in $(docker ps --format '{{.Names}}' | grep -E '^p113_' ); do docker rm -f "$c" >/dev/null 2>&1; done
    # any panel unit markers created in the gap are removed; the panel must start clean at 150
    rm -f state/*__SAM*.done.tmp 2>/dev/null
    break
  fi
  sleep 5
done
echo "accepted=$(ls state/asm__*.done 2>/dev/null|wc -l) rejected=$(ls state/asm__*.failed 2>/dev/null|wc -l)"
echo "runner: $(pgrep -f '[p]113_run.sh' >/dev/null && echo ALIVE || echo stopped)"
grep -E "PHASE 3 done|PHASE 4 panel" logs/p113_master.log | tail -2

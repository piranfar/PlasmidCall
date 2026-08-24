#!/usr/bin/env bash
# P1.11 12-tool panel inference, TRUTH-BLIND. Runs on the OCI host.
#
# Calls the P1.11 runner, which is the P1.10 runner derived BY PATH SUBSTITUTION ONLY:
#   /data/trace-arg/p112/env/run/run_tool.sh <tool> <sample>
# All 13 scientific CMD strings are byte-identical to P1.10 (verified: path-normalised hash
# fa6bcbc520107c3f81dba3750dc48bc1 on both). Container limits stay --memory=24g --cpus=8.
# Paths are hardcoded inside the runner, so it takes exactly two arguments.
#
# ORDERING CONSTRAINT, inherited from the frozen P1.10 driver:
#   gplas2 for a sample must not start until plasmidec for that SAME sample has finished, because
#   gplas2 consumes the plasmidEC output. Violating this silently corrupts gplas2 calls.
#
# RETRY RULE (prespecified, at most 2 retries): a tool that exits non-zero is retried at most twice
# with the IDENTICAL frozen image, database, command and parameters. Technical failure only. No
# patching, replacement or retuning. After the third failure the state is recorded as FAILED for
# that sample and the run continues - FAILED is preserved, never silently dropped and never
# converted to a negative call.
#
# STORAGE FLOOR, inherited from the frozen driver: stop rather than fill the volume.
#
# Usage: p111_infer.sh <slots> [samples...]
set -uo pipefail

ROOT=/data/trace-arg
P=$ROOT/p112
RUNNER=$P/env/run/run_tool.sh
SLOTS="${1:-4}"; shift || true
MAX_RETRY=2
TOOLS="mobsuite platon rfplasmid plascope plasmidfinder genomad plasme plasmer plasgraph2 hyasp amrfinder plasmidec gplas2"

# SINGLE-INSTANCE LOCK. Concurrent loops corrupted this phase once already: two loops raced on the
# same tool/sample, one succeeded and the frozen runner chmod'd its output read-only, the other then
# re-ran the same sample, could not rm -rf the read-only directory, and recorded a false FAILED.
# Samples ended up with BOTH a .done and a .failed marker. Never allow two loops.
LOCKFILE=$P/work/p111_infer.lock
exec 9>"$LOCKFILE" 2>/dev/null || { echo "cannot open lock"; exit 9; }
if ! flock -n 9; then
  echo "[$(date -u +%FT%TZ)] another p111_infer.sh already holds the lock; refusing to start a second loop"
  exit 9
fi

STATE=$P/inference/state
LOCKD=$P/work/slots_infer
LOGD=$P/inference/logs
mkdir -p "$STATE" "$LOCKD" "$LOGD" "$P/inference/receipts" "$P/inference/native"

say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOGD/p111_infer.log"; }

storage_ok() {
  local da ra
  da=$(df -B1 --output=avail /work | tail -1)
  ra=$(df -B1 --output=avail / | tail -1)
  if [ "$da" -lt $((60*1024*1024*1024)) ] || [ "$ra" -lt $((15*1024*1024*1024))  ]; then
    say "STORAGE_FLOOR data=$da root=$ra - stopping"
    touch "$P/inference/STORAGE_HOLD"
    return 1
  fi
  return 0
}

acquire_slot() {
  local i
  while true; do
    for (( i=0; i<SLOTS; i++ )); do
      if mkdir "$LOCKD/slot.$i" 2>/dev/null; then echo "$i"; return 0; fi
    done
    sleep 15
  done
}
release_slot() { rmdir "$LOCKD/slot.$1" 2>/dev/null || true; }

run_one() {
  local tool="$1" bs="$2" slot attempt=0 rc=0
  local st="$STATE/${tool}__${bs}"
  # .done wins: if a prior run succeeded, clear any stale .failed left by a racing loop.
  if [ -e "$st.done" ]; then rm -f "$st.failed"; return 0; fi
  [ -e "$st.failed" ] && return 0

  slot=$(acquire_slot)
  trap 'release_slot "$slot"' RETURN

  while [ "$attempt" -le "$MAX_RETRY" ]; do
    storage_ok || return 1
    # Two things make a stale output directory undeletable by this user:
    #   1. the frozen runner ends with `chmod -R a-w $OUT`, so the tree is read-only
    #   2. the tool writes inside the container as root, so subdirectories are root-owned
    # `chmod` as ubuntu cannot touch the root-owned parts, and the read-only parent blocks unlink.
    # sudo is required, and is used ONLY to clear our own stale output - never on frozen inputs.
    if [ -d "$P/inference/native/$tool/$bs" ]; then
      sudo chmod -R u+w "$P/inference/native/$tool/$bs" 2>/dev/null || true
      sudo rm -rf "$P/inference/native/$tool/$bs" 2>/dev/null ||         rm -rf "$P/inference/native/$tool/$bs" 2>/dev/null || true
    fi
    if [ -d "$P/inference/native/$tool/$bs" ]; then
      say "CANNOT CLEAR stale output for $tool/$bs - refusing to run on a dirty directory"
      echo "stale_output_not_clearable" > "$st.failed"; return 0
    fi
    local t0 t1; t0=$(date -u +%s); rc=0
    bash "$RUNNER" "$tool" "$bs" > "$LOGD/${tool}__${bs}.attempt${attempt}.log" 2>&1 || rc=$?
    t1=$(date -u +%s)

    if [ "$rc" -eq 0 ]; then
      rm -f "$st.failed"; touch "$st.done"
      say "OK     $tool/$bs (attempt $((attempt+1)), $((t1-t0))s)"
      return 0
    fi
    attempt=$((attempt+1))
    if [ "$attempt" -le "$MAX_RETRY" ]; then
      say "RETRY  $tool/$bs rc=$rc ($attempt of $MAX_RETRY, identical image/db/command/parameters)"
      sleep 20
    fi
  done

  echo "rc=$rc after $((MAX_RETRY+1)) attempts" > "$st.failed"
  say "FAILED $tool/$bs after $((MAX_RETRY+1)) attempts (rc=$rc) - state preserved"
  return 0
}

SAMPLES="$*"
[ -z "$SAMPLES" ] && SAMPLES=$(ls "$P/assemblies/shortread" 2>/dev/null)
NS=$(echo "$SAMPLES" | wc -w)
say "inference start: $NS samples x 13 tools, $SLOTS slots, runner=$RUNNER"
say "truth-blind: runner mounts only Product A (ro), tool DB (ro) and the tool output dir"

# plasmidec first for every sample, so gplas2 never overtakes its dependency
for t in $TOOLS; do
  [ "$t" = gplas2 ] && continue
  for s in $SAMPLES; do
    ( run_one "$t" "$s" ) &
    while [ "$(jobs -rp | wc -l)" -ge "$SLOTS" ]; do sleep 8; done
  done
done
wait
say "phase 1 complete (12 tools); starting gplas2 now that plasmidec is finished for all samples"

for s in $SAMPLES; do
  if [ -e "$STATE/plasmidec__${s}.done" ]; then
    ( run_one gplas2 "$s" ) &
    while [ "$(jobs -rp | wc -l)" -ge "$SLOTS" ]; do sleep 8; done
  else
    say "SKIP gplas2/$s - plasmidec did not succeed for this sample; dependency unmet"
    echo "plasmidec_dependency_unmet" > "$STATE/gplas2__${s}.failed"
  fi
done
wait

ok=$(ls "$STATE" 2>/dev/null | grep -c '\.done$' || true)
bad=$(ls "$STATE" 2>/dev/null | grep -c '\.failed$' || true)
say "inference complete: $ok done, $bad failed (FAILED states preserved for the record)"

miss=0
for s in $SAMPLES; do [ -e "$STATE/plascope__${s}.done" ] || miss=$((miss+1)); done
say "CRITICAL TOOL: PlaScope available on $((NS-miss)) of $NS samples (gate requires >= 76 of 79)"
exit 0

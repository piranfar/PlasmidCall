#!/usr/bin/env bash
# P1.13 master runner. Detached, restart-safe, resumable, truth-blind.
# Phases: guard -> acquire -> downsample -> assemble -> panel -> reconcile
# STOPS before parsing/prediction so the truth-blind gate is explicit.
# Never touches /data/pr_context, /data/pr_ani1, p19c4, p110, p112 or any frozen image.
set -uo pipefail
ROOT=/work
P=$ROOT/p113
STAGE=/data/p113_reads                      # raw + downsampled staging on PortabilityRisk_HDD
COHORT=$P/P1.13_SELECTED_COHORT_v3.tsv
ST=$P/state; LOGD=$P/logs; REC=$P/receipts
mkdir -p "$ST" "$LOGD" "$REC" "$P/tmp/host" "$P/tmp/assembly" "$P/tmp/tools" \
         "$STAGE/raw" "$STAGE/down" "$P/assemblies/shortread" "$P/inference/native" \
         "$P/inference/logs" "$P/inference/receipts" "$P/annotation/native"
export TMPDIR="$P/tmp/host" TMP="$P/tmp/host" TEMP="$P/tmp/host"

SLOTS=${SLOTS:-8}
SEED=20260821
TARGET_COV=100
TOOLS="mobsuite platon rfplasmid plascope plasmidfinder genomad plasme plasmer plasgraph2 hyasp amrfinder plasmidec gplas2"
NORMIMG=p19c2-normalize:1.0
ASMIMG=p19c2-cleanroom:1.0

# hard reserves, frozen in Amendment 002
declare -A RESERVE=( ["/"]=20 ["/data"]=30 ["/work"]=30 )

utc(){ date -u +%FT%TZ; }
say(){ echo "$(utc) $*" | tee -a "$LOGD/run.log"; }

exec 9>"$P/p113_run.lock"
if ! flock -n 9; then say "another p113_run.sh holds the lock; refusing a second loop"; exit 9; fi

free_gib(){ df -B1 --output=avail "$1" | tail -1 | awk '{printf "%.2f", $1/1073741824}'; }
guard(){
  local bad=0
  for m in / /data /work; do
    local f; f=$(free_gib "$m")
    if awk -v a="$f" -v r="${RESERVE[$m]}" 'BEGIN{exit !(a<r)}'; then
      say "RESOURCE STOP: $m has ${f} GiB free, below the frozen ${RESERVE[$m]} GiB reserve"; bad=1
    fi
  done
  [ "$bad" -eq 0 ] || { say "halting before the reserve is breached"; exit 20; }
}
disk_line(){ printf "/=%s /data=%s /work=%s" "$(free_gib /)" "$(free_gib /data)" "$(free_gib /work)"; }

# ------------------------------------------------------------------ cohort integrity
COHORT_SHA=$(sha256sum "$COHORT" | cut -d' ' -f1)
EXPECT_SHA=$(cat "$P/.cohort_sha" 2>/dev/null || echo "")
if [ -n "$EXPECT_SHA" ] && [ "$COHORT_SHA" != "$EXPECT_SHA" ]; then
  say "COHORT DRIFT: $COHORT sha256 changed since the last run. Refusing."; exit 21
fi
echo "$COHORT_SHA" > "$P/.cohort_sha"
N=$(( $(wc -l < "$COHORT") - 1 ))
say "P1.13 runner start | cohort $N isolates | sha256 ${COHORT_SHA:0:16} | slots $SLOTS | $(disk_line)"
[ "$N" -eq 150 ] || { say "ABORT: cohort is $N isolates, expected 150"; exit 22; }
guard

# ------------------------------------------------------------------ phase 1: acquire
say "PHASE 1 acquire"
acquire_one(){
  local bs=$1 run=$2 ftp=$3 md5s=$4
  local d="$STAGE/raw/$bs"; mkdir -p "$d"
  local i=1 ok=1
  IFS=';' read -ra U <<< "$ftp"; IFS=';' read -ra M <<< "$md5s"
  for k in "${!U[@]}"; do
    local url="https://${U[$k]#ftp://}"; url="${url#https://https://}"
    local fn; fn=$(basename "${U[$k]}"); local f="$d/$fn"; local want="${M[$k]}"
    [ ${#want} -ne 32 ] && { say "ABORT $bs/$fn: md5 field is not 32 chars"; return 1; }
    if [ -s "$f" ] && [ "$(md5sum "$f" | cut -d' ' -f1)" = "$want" ]; then continue; fi
    # A file that is present but fails md5 is CORRUPT, not partial. Resuming onto it with
    # -C - appends from the wrong logical offset and can yield a file of exactly the right
    # size with the wrong content, which no size check would catch. Discard and refetch from
    # byte zero, and re-check md5 inside the retry loop rather than only once at the end.
    [ -e "$f" ] && { say "  discarding unverified $bs/$fn, refetching from byte zero"; rm -f "$f"; }
    local a got
    for a in 1 2 3 4; do
      if curl -fsS --max-time 1800 -o "$f" "$url" 2>/dev/null; then
        got=$(md5sum "$f" 2>/dev/null | cut -d" " -f1)
        [ "$got" = "$want" ] && break
        say "  md5 mismatch for $bs/$fn on attempt $a, discarding and refetching"
      fi
      rm -f "$f"; sleep $((a*5))
    done
    got=$(md5sum "$f" 2>/dev/null | cut -d" " -f1)
    if [ "$got" != "$want" ]; then say "MD5 FAIL $bs/$fn got=$got want=$want"; ok=0; fi
  done
  [ "$ok" -eq 1 ] && touch "$ST/acquire__$bs.done" || touch "$ST/acquire__$bs.failed"
}
n=0
while IFS=$'\t' read -r bs asm bp tax org inf tid stid rel asmn ftpp src rc gsz nruns run study inst libsel rdc bcc fq md5 fbytes cov tier; do
  [ "$bs" = "biosample" ] && continue
  [ -e "$ST/acquire__$bs.done" ] && { n=$((n+1)); continue; }
  while (( $(jobs -rp | wc -l) >= 6 )); do sleep 5; done
  acquire_one "$bs" "$run" "$fq" "$md5" &
  n=$((n+1))
  if (( n % 25 == 0 )); then wait; guard; say "  acquire progress $n/$N | $(disk_line)"; fi
done < "$COHORT"
wait; guard
AD=$(ls "$ST"/acquire__*.done 2>/dev/null | wc -l); AF=$(ls "$ST"/acquire__*.failed 2>/dev/null | wc -l)
say "PHASE 1 done: verified $AD, failed $AF | $(disk_line)"
[ "$AD" -eq 150 ] || { say "ABORT: only $AD of 150 isolates verified"; exit 23; }

# ------------------------------------------------------------------ phase 2: downsample
say "PHASE 2 deterministic downsample to ${TARGET_COV}x, seed $SEED, with EXACT pairing validation"
say "  count equality alone is insufficient and is not used; every pair is validated by position-by-position normalized id"
DSLOTS=${DSLOTS:-12}
say "  running $DSLOTS isolates concurrently; each isolate is a pure function of its own reads, its own recomputed fraction and the frozen seed, so order cannot change any output"
dn=0
down_one(){
  local bs=$1 gsz=$2
  if python3 "$P/env/p113_downsample.py" "$bs" "$gsz" >> "$LOGD/downsample.log" 2>&1; then
    touch "$ST/down__$bs.done"; rm -f "$ST/down__$bs.failed"
  else
    touch "$ST/down__$bs.failed"
    say "DOWNSAMPLE/PAIRING FAILED $bs - see logs/downsample.log (fails closed, no assembly will use it)"
  fi
}
while IFS=$'	' read -r bs asm bp tax org inf tid stid rel asmn ftpp src rc gsz nruns run study inst libsel rdc bcc fq md5 fbytes cov tier; do
  [ "$bs" = "biosample" ] && continue
  [ -e "$ST/down__$bs.done" ] && continue
  while (( $(jobs -rp | wc -l) >= DSLOTS )); do sleep 5; done
  guard
  down_one "$bs" "$gsz" &
  dn=$((dn+1))
  (( dn % 24 == 0 )) && { wait; guard; say "  downsample progress $dn | $(disk_line)"; }
done < "$COHORT"
wait; guard
DD=$(ls "$ST"/down__*.done 2>/dev/null | wc -l); DF=$(ls "$ST"/down__*.failed 2>/dev/null | wc -l)
say "PHASE 2 done: validated $DD, failed $DF | $(disk_line)"
[ "$DD" -eq 150 ] || { say "ABORT: exact-pairing validation passed for only $DD of 150"; exit 24; }

# ------------------------------------------------------------------ phase 3: assemble
say "PHASE 3 assemble (frozen: unicycler -1 R1 -2 R2 -o /tmp/a -t 8 --keep 1)"
asm_one(){
  local bs=$1
  if [ ! -e "$ST/down__$bs.done" ]; then
    say "REFUSING to assemble $bs: downsampled pair has not passed exact id validation"
    touch "$ST/asm__$bs.failed"; return 1
  fi
  # attempt number is derived from durable per-attempt logs, so retries are never conflated
  local an; an=$(( $(ls "$LOGD"/asm__${bs}__attempt*.log 2>/dev/null | wc -l) + 1 ))
  # staging is attempt-specific: NOTHING is written to the final path before validation passes
  local sd="$P/assemblies/_staging/$bs/attempt$an"; rm -rf "$sd"; mkdir -p "$sd"; chmod 777 "$sd"
  # Attempt-specific scratch. A previous attempt's SPAdes graph must never be visible to a new
  # one: unicycler silently resumes from an existing graph, which would publish computation from
  # an interrupted run under a new attempt's provenance. A fresh path per attempt makes reuse
  # structurally impossible even if cleanup fails.
  local ta="$P/tmp/assembly/$bs/attempt$an"
  docker run --rm --user 0:0 -v "$P/tmp/assembly":/x --entrypoint sh "$ASMIMG"     -c "rm -rf /x/$bs/attempt$an" >/dev/null 2>&1
  mkdir -p "$ta"; chmod 777 "$ta"
  local CMD="set -e; unicycler -1 /reads/R1.fastq.gz -2 /reads/R2.fastq.gz -o /tmp/a -t 8 --keep 1; cp /tmp/a/assembly.fasta /out/shortread.fasta; cp /tmp/a/assembly.gfa /out/shortread.gfa; cp /tmp/a/unicycler.log /out/unicycler_shortread.log"
  docker run --rm --name "p113_asm_$bs" --memory=12g --cpus=8     -v "$STAGE/down/$bs":/reads:ro -v "$sd":/out -v "$ta":/tmp     -e TMPDIR=/tmp -e TMP=/tmp -e TEMP=/tmp "$ASMIMG" bash -c "$CMD"     > "$LOGD/asm__${bs}__attempt${an}.log" 2>&1
  local rc=$?
  # the container writes as uid 57439; the host user cannot unlink those files, so rm -rf here
  # fails silently. Remove the scratch with root privileges inside a container instead.
  docker run --rm --user 0:0 -v "$P/tmp/assembly":/x --entrypoint sh "$ASMIMG"     -c "rm -rf /x/$bs/attempt$an" >/dev/null 2>&1
  # fail-closed acceptance. The validator publishes atomically and writes .done LAST.
  if python3 "$P/env/p113_assembly_accept.py" "$bs" "$sd" "$rc" "$an" "$CMD" >> "$LOGD/accept.log" 2>&1; then
    rm -rf "$sd"
    if [ -e "$ST/asm__$bs.failed" ]; then
      mkdir -p "$P/provenance/historical_markers"
      mv "$ST/asm__$bs.failed" "$P/provenance/historical_markers/asm__${bs}.failed.superseded_by_attempt${an}"
    fi
  else
    mkdir -p "$P/provenance/attempts/$bs/attempt$an"
    cp -p "$LOGD/asm__${bs}__attempt${an}.log" "$P/provenance/attempts/$bs/attempt$an/" 2>/dev/null
    [ -d "$sd" ] && mv "$sd" "$P/provenance/attempts/$bs/attempt$an/rejected_output" 2>/dev/null
    touch "$ST/asm__$bs.failed"
    say "ASSEMBLY REJECTED $bs attempt $an rc=$rc - see logs/accept.log"
  fi
}
n=0
while IFS=$'\t' read -r bs rest; do
  [ "$bs" = "biosample" ] && continue
  [ -e "$ST/asm__$bs.done" ] && { n=$((n+1)); continue; }
  while (( $(jobs -rp | wc -l) >= SLOTS )); do sleep 15; done
  guard; asm_one "$bs" & n=$((n+1))
  # progress only. A full wait barrier here drains all 8 slots down to the slowest straggler
  # before refilling, which idles the machine for long stretches. Slot gating above already
  # bounds concurrency; the barrier adds nothing but latency.
  (( n % 20 == 0 )) && say "  assembly progress $n/$N accepted=$(ls "$ST"/asm__*.done 2>/dev/null | wc -l) | $(disk_line)"
done < "$COHORT"
wait; guard
SD=$(ls "$ST"/asm__*.done 2>/dev/null | wc -l); SF=$(ls "$ST"/asm__*.failed 2>/dev/null | wc -l)
say "PHASE 3 done: assembled $SD, failed $SF | $(disk_line)"

# ------------------------------------------------------------------ phase 4: panel
# ------------------------------------------------------------------ reconciliation gate
# Operator rule 2026-08-23: the panel does not start unless every one of the 150 cohort isolates
# holds an accepted, validated, hash-checked assembly. Fail closed.
say "RECONCILIATION before phase 4"
if ! python3 "$P/env/p113_asm_reconcile.py" >> "$LOGD/reconcile.log" 2>&1; then
  say "RECONCILIATION FAILED - see P1.13_ASSEMBLY_RECONCILIATION.json and logs/reconcile.log"
  tail -25 "$LOGD/reconcile.log" 2>/dev/null | while IFS= read -r l; do say "  $l"; done
  exit 26
fi
say "RECONCILIATION PASSED: 150 accepted, validated assemblies"

say "PHASE 4 panel: 13 units x $SD isolates"
MAX_RETRY=2
run_unit(){
  local tool=$1 bs=$2; local st="$ST/${tool}__${bs}"
  if [ -e "$st.done" ]; then rm -f "$st.failed"; return 0; fi
  [ -e "$st.failed" ] && return 0
  local attempt=0 rc=0
  while [ "$attempt" -le "$MAX_RETRY" ]; do
    local d="$P/inference/native/$tool/$bs"
    if [ -d "$d" ]; then sudo chmod -R u+w "$d" 2>/dev/null || true; sudo rm -rf "$d" 2>/dev/null || rm -rf "$d" 2>/dev/null || true; fi
    bash "$P/env/p113_tool.sh" "$tool" "$bs" >> "$LOGD/panel.log" 2>&1; rc=$?
    [ $rc -eq 0 ] && break
    attempt=$((attempt+1))
    [ "$attempt" -le "$MAX_RETRY" ] && say "  RETRY $tool/$bs rc=$rc ($attempt of $MAX_RETRY, identical image/db/command)"
  done
  [ $rc -eq 0 ] && touch "$st.done" || touch "$st.failed"
}
for tool in $TOOLS; do
  # gplas2 consumes plasmidEC output, so it must follow plasmidec
  n=0
  while IFS=$'\t' read -r bs rest; do
    [ "$bs" = "biosample" ] && continue
    [ -e "$ST/asm__$bs.done" ] || continue
    if [ "$tool" = "gplas2" ] && [ ! -e "$ST/plasmidec__$bs.done" ]; then continue; fi
    while (( $(jobs -rp | wc -l) >= SLOTS )); do sleep 10; done
    guard; run_unit "$tool" "$bs" & n=$((n+1))
    (( n % 25 == 0 )) && { wait; say "  $tool progress $n | $(disk_line)"; }
  done < "$COHORT"
  wait
  d=$(ls "$ST/${tool}__"*.done 2>/dev/null | wc -l); f=$(ls "$ST/${tool}__"*.failed 2>/dev/null | wc -l)
  say "  TOOL $tool complete: done=$d failed=$f | $(disk_line)"
done
guard

# ------------------------------------------------------------------ phase 5: reconcile
say "PHASE 5 global marker/receipt/output reconciliation"
python3 "$P/env/p113_reconcile.py" 2>&1 | tee -a "$LOGD/run.log"
say "RUNNER COMPLETE - truth-blind. No truth acquired, constructed, inspected or joined."
say "final disk: $(disk_line)"
echo "P113_RUN_COMPLETE"

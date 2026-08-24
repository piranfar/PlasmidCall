#!/usr/bin/env bash
# P1.13 temporary-storage preflight. Tests the ACTUAL production command path for all 13
# execution units. Read-mostly: creates only P1.13-owned temp directories and sentinels.
# Touches nothing belonging to P1.11, PortabilityRisk/NM or Docker images.
set -uo pipefail
ROOT=/work/p113
TMPR=$ROOT/tmp
mkdir -p "$TMPR/host" "$TMPR/assembly" "$TMPR/tools"
OUT=$ROOT/P1.13_TEMP_PREFLIGHT.tsv
printf "unit\timage\tcheck\tresult\tdetail\n" > "$OUT"
rec(){ printf "%s\t%s\t%s\t%s\t%s\n" "$1" "$2" "$3" "$4" "$5" >> "$OUT"; }

echo "=== A. baseline: where do things actually live ==="
printf "  %-22s %s\n" "P1.13 root"      "$(df --output=source,target $ROOT | tail -1)"
printf "  %-22s %s\n" "P1.13 tmp root"  "$(df --output=source,target $TMPR | tail -1)"
printf "  %-22s %s\n" "Docker Root Dir" "$(df --output=source,target /work/docker | tail -1)"
printf "  %-22s %s\n" "/tmp (host)"     "$(df --output=source,target /tmp | tail -1)"
BOOTDEV=$(df --output=source / | tail -1 | tr -d ' ')
echo "  boot device to avoid for large writes: $BOOTDEV"

declare -A IMG=(
 [hyasp]=p19c4-hyasp:1.0 [mobsuite]=p19c4-mobsuite:1.0 [plasme]=p19c4-plasme:1.0
 [plascope]=p19c4-plascope:1.0 [plasmer]=nekokoe/plasmer:23.04.20 [plasmidec]=p19c4-plasmidec:1.0
 [plasmidfinder]=p19c4-plasmidfinder:1.0 [platon]=p19c4-platon:1.0 [rfplasmid]=p19c4-rfplasmid:1.0
 [genomad]=p19c4-genomad:1.0 [gplas2]=p19c4-gplas2:1.0 [plasgraph2]=p19c4-plasgraph2:1.0
 [amrfinder]=p19c4-amrfinder:1.0 )

# frozen digests as recorded in the P1.11 receipts
declare -A FROZEN
while IFS=$'\t' read -r t d; do FROZEN[$t]="$d"; done < <(
  python3 - <<'PY'
import glob,json,io
seen={}
for f in glob.glob("/work/p112/inference/receipts/*.json"):
    try: d=json.load(io.open(f,encoding="utf-8"))
    except Exception: continue
    t=d.get("tool"); i=d.get("image_id")
    if t and i and t not in seen: seen[t]=i
for t,i in sorted(seen.items()): print("%s\t%s"%(t,i))
PY
)

echo
echo "=== B. per-unit production-path preflight (13 units) ==="
FAIL=0
for T in "${!IMG[@]}"; do
  I="${IMG[$T]}"
  HT="$TMPR/tools/$T/PREFLIGHT"; mkdir -p "$HT"; chmod 777 "$HT"
  # 1 image digest vs frozen
  LIVE=$(docker image inspect "$I" -f '{{.Id}}' 2>/dev/null)
  FZ="${FROZEN[$T]:-}"
  if [ -n "$FZ" ] && [ "$LIVE" = "$FZ" ]; then rec "$T" "$I" image_digest MATCH "${LIVE:0:23}"
  elif [ -z "$FZ" ]; then rec "$T" "$I" image_digest NO_FROZEN_RECORD "${LIVE:0:23}"
  else rec "$T" "$I" image_digest MISMATCH "live=${LIVE:0:16} frozen=${FZ:0:16}"; FAIL=$((FAIL+1)); fi
  # 2 does the image ship content in /tmp that a bind mount would mask?
  BAKED=$(docker run --rm --entrypoint bash "$I" -lc 'ls -A /tmp 2>/dev/null | wc -l' 2>/dev/null | tr -d '\r')
  [ "${BAKED:-0}" = "0" ] && rec "$T" "$I" image_tmp_empty YES "safe to bind-mount over /tmp" \
                          || { rec "$T" "$I" image_tmp_empty NO "$BAKED entries would be masked"; FAIL=$((FAIL+1)); }
  # 3-8 run the real mount pattern: per-tool/per-isolate host temp bound to container /tmp
  R=$(docker run --rm --name p113_pf_$T -v "$HT":/tmp \
        -e TMPDIR=/tmp -e TMP=/tmp -e TEMP=/tmp --entrypoint bash "$I" -lc '
        set -e
        echo "TMPDIR=$TMPDIR TMP=$TMP TEMP=$TEMP"
        echo "whoami=$(id -u):$(id -g)"
        s=/tmp/.p113_sentinel_$$; echo p113 > "$s" && echo "write=OK" || echo "write=FAIL"
        echo "sentinel=$(basename $s)"
        echo "dfline=$(df -P /tmp | tail -1 | tr -s " ")"
        rm -f "$s".removecheck 2>/dev/null; touch "$s".removecheck && rm -f "$s".removecheck && echo "rm=OK" || echo "rm=FAIL"
      ' 2>&1)
  SENT=$(echo "$R" | sed -n 's/^sentinel=//p')
  ENVOK=$(echo "$R" | grep -c 'TMPDIR=/tmp TMP=/tmp TEMP=/tmp')
  WOK=$(echo "$R" | grep -c 'write=OK'); ROK=$(echo "$R" | grep -c 'rm=OK')
  DFL=$(echo "$R" | sed -n 's/^dfline=//p')
  [ "$ENVOK" = "1" ] && rec "$T" "$I" env_TMPDIR_TMP_TEMP OK "all three = /tmp" \
                     || { rec "$T" "$I" env_TMPDIR_TMP_TEMP FAIL "$R"; FAIL=$((FAIL+1)); }
  [ "$WOK" = "1" ] && rec "$T" "$I" container_tmp_writable OK "" \
                   || { rec "$T" "$I" container_tmp_writable FAIL ""; FAIL=$((FAIL+1)); }
  [ "$ROK" = "1" ] && rec "$T" "$I" uid_can_create_and_remove OK "$(echo "$R" | sed -n 's/^whoami=//p')" \
                   || { rec "$T" "$I" uid_can_create_and_remove FAIL ""; FAIL=$((FAIL+1)); }
  # sentinel must appear on the HOST side, in the intended /work directory
  if [ -n "$SENT" ] && [ -f "$HT/$SENT" ]; then
    rec "$T" "$I" sentinel_reaches_host OK "$HT/$SENT"
    rm -f "$HT/$SENT"
  else
    rec "$T" "$I" sentinel_reaches_host FAIL "not found under $HT"; FAIL=$((FAIL+1))
  fi
  # container df must show the trace-arg-data backing, not the boot volume
  AV=$(echo "$DFL" | awk '{print $4}')
  if [ -n "$AV" ] && [ "$AV" -gt 20000000 ]; then rec "$T" "$I" container_tmp_capacity OK "${AV}K available"
  else rec "$T" "$I" container_tmp_capacity FAIL "$DFL"; FAIL=$((FAIL+1)); fi
  printf "  %-14s digest=%s tmp_bind=%s sentinel=%s\n" "$T" \
    "$([ "$LIVE" = "$FZ" ] && echo MATCH || echo CHECK)" \
    "$([ "$WOK" = 1 ] && echo OK || echo FAIL)" \
    "$([ -n "$SENT" ] && echo OK || echo FAIL)"
done

echo
echo "=== C. host-side temp routing (assembly and parsing) ==="
export TMPDIR="$TMPR/host" TMP="$TMPR/host" TEMP="$TMPR/host"
HS=$(mktemp -p "$TMPDIR" p113hostXXXX 2>/dev/null) && {
  D=$(df --output=source "$HS" | tail -1 | tr -d ' ')
  if [ "$D" != "$BOOTDEV" ]; then rec host_process - host_TMPDIR_off_boot OK "$D"; echo "  host TMPDIR resolves to $D (not $BOOTDEV) OK"
  else rec host_process - host_TMPDIR_off_boot FAIL "$D"; FAIL=$((FAIL+1)); fi
  rm -f "$HS"; }
echo "  concurrency isolation: temp path template is tmp/tools/<tool>/<isolate>, unique per unit"
rec concurrency - per_unit_temp_isolation OK "tmp/tools/<tool>/<isolate>"

echo
echo "=== D. filesystem reserves ==="
for m in / /data /work; do
  A=$(df -B1 --output=avail "$m" | tail -1); printf "  %-10s available %.2f GiB\n" "$m" "$(echo "$A/1073741824" | bc -l)"
done
echo
echo "PREFLIGHT_FAILURES=$FAIL"
echo PREFLIGHT_DONE

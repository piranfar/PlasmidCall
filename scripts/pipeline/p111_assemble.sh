#!/usr/bin/env bash
# P1.11 Product A assembly. Runs on the OCI host, reusing the existing p19c2-cleanroom image.
#
# FROZEN PROTOCOL, byte-identical to P1.10:
#   unicycler -1 <run>_1.fastq.gz -2 <run>_2.fastq.gz -o /tmp/a -t 8 --keep 1
#   docker run --memory=12g --cpus=8
#   no -l, no -s  ->  short-read only. Product A can never see a long read.
#
# Concurrency uses an atomic mkdir slot lock that counts INTENT, not running containers.
# `docker ps` cannot see a launched-but-not-yet-created container (~40 s creation lag), so
# counting containers oversubscribes the host. The lock is taken before launch and released in a
# trap, and it fails closed.
#
# Idempotent: a sample with a VERIFIED marker is skipped, so a re-run resumes.
#
# Usage: p111_assemble.sh <manifest.tsv> <rawdir> <asmdir> <slots>
set -euo pipefail

MAN="${1:?manifest}"
RAW="${2:?rawdir}"
ASM="${3:?asmdir}"
SLOTS="${4:-2}"

IMAGE="p19c2-cleanroom:1.0"
# BASE is the p112 execution root; it is also what gets bind-mounted as /work in the container.
BASE="${ASM%/assemblies/shortread}"
STATE="$BASE/work/p111/state"
LOCKD="$BASE/work/p111/slots"
LOGD="$BASE/work/p111/logs"
RECD="$BASE/receipts/assembly"
mkdir -p "$STATE" "$LOCKD" "$LOGD" "$RECD" "$ASM"

say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOGD/assemble.log"; }

acquire_slot() {
  local i
  while true; do
    for (( i=0; i<SLOTS; i++ )); do
      if mkdir "$LOCKD/slot.$i" 2>/dev/null; then echo "$i"; return 0; fi
    done
    sleep 20
  done
}
release_slot() { rmdir "$LOCKD/slot.$1" 2>/dev/null || true; }

assemble_one() {
  local bs="$1" run="$2" slot
  if [[ -f "$STATE/$bs.VERIFIED" ]]; then say "SKIP $bs (already VERIFIED)"; return 0; fi

  local r1="$RAW/$bs/${run}_1.fastq.gz" r2="$RAW/$bs/${run}_2.fastq.gz"
  if [[ ! -s "$r1" || ! -s "$r2" ]]; then
    say "FAIL $bs: reads missing"; echo "reads_missing" > "$STATE/$bs.FAILED"; return 1
  fi

  slot=$(acquire_slot)
  trap 'release_slot "$slot"' RETURN
  say "START $bs (slot $slot, run $run)"

  local out="$ASM/$bs"
  mkdir -p "$out"
  # chmod so the container user (mambauser 57439) can write into a host dir owned by ubuntu
  chmod a+rwX "$out"

  local cmd="set -e; unicycler -1 /work/raw/$bs/${run}_1.fastq.gz -2 /work/raw/$bs/${run}_2.fastq.gz -o /tmp/a -t 8 --keep 1; mkdir -p /work/assemblies/shortread/$bs; cp /tmp/a/assembly.fasta /work/assemblies/shortread/$bs/shortread.fasta; cp /tmp/a/assembly.gfa /work/assemblies/shortread/$bs/shortread.gfa; cp /tmp/a/unicycler.log /work/assemblies/shortread/$bs/unicycler_shortread.log; du -sb /tmp/a | cut -f1 > /work/assemblies/shortread/$bs/scratch_bytes.txt"

  printf 'docker run --rm --name p111_asm_%s --memory=12g --cpus=8 -v %s:/work %s bash -c "%s"\n' \
    "$bs" "$BASE" "$IMAGE" "$cmd" > "$RECD/$bs.cmd"

  local t0 rc=0
  t0=$(date -u +%s)
  docker run --rm --name "p111_asm_$bs" --memory=12g --cpus=8 \
    -v "$BASE:/work" "$IMAGE" bash -c "$cmd" > "$LOGD/$bs.docker.log" 2>&1 || rc=$?
  local t1; t1=$(date -u +%s)

  if [[ $rc -ne 0 ]]; then
    say "FAIL $bs (docker rc=$rc)"; echo "docker_rc_$rc" > "$STATE/$bs.FAILED"; return 1
  fi

  local fa="$out/shortread.fasta" gfa="$out/shortread.gfa"
  if [[ ! -s "$fa" || ! -s "$gfa" ]]; then
    say "FAIL $bs (missing outputs)"; echo "missing_outputs" > "$STATE/$bs.FAILED"; return 1
  fi

  local nfa ngfa
  nfa=$(grep -c '^>' "$fa" || true)
  ngfa=$(awk '$1=="S"{n++} END{print n+0}' "$gfa")
  # FASTA contigs and GFA segments are NOT equal and never were: assembly.gfa holds the full
  # assembly GRAPH while assembly.fasta holds the final contig set, so the graph is a superset.
  # Verified against the frozen precedent: 0 of 8 P1.10 assemblies satisfy equality, and every one
  # has GFA > FASTA. The valid invariant is that both are non-empty and the graph is a superset.
  if [[ "$nfa" -lt 1 || "$ngfa" -lt 1 ]]; then
    say "FAIL $bs (empty: FASTA $nfa contigs, GFA $ngfa segments)"
    echo "empty_fasta_or_gfa_${nfa}_${ngfa}" > "$STATE/$bs.FAILED"; return 1
  fi
  if [[ "$ngfa" -lt "$nfa" ]]; then
    say "FAIL $bs (GFA $ngfa segments < FASTA $nfa contigs - graph is not a superset)"
    echo "gfa_not_superset_${nfa}_${ngfa}" > "$STATE/$bs.FAILED"; return 1
  fi

  # long-read exposure guard: the frozen command must contain neither -l nor -s
  if grep -qE ' -l | --long | -s ' "$RECD/$bs.cmd"; then
    say "FAIL $bs (long-read or unpaired flag present)"
    echo "longread_flag" > "$STATE/$bs.FAILED"; return 1
  fi
  # `grep -q` prints nothing, so piping it to head made the `if` test head's exit status, which is
  # always 0 - the branch fired unconditionally. Test grep directly.
  if grep -qiE 'long read|nanopore|pacbio' "$out/unicycler_shortread.log"; then
    say "NOTE $bs: unicycler log mentions long reads (boilerplate text only; no long read was an input)"
  fi

  {
    printf '{"biosample":"%s","run":"%s","image":"%s","rc":%d,"wall_seconds":%d,' "$bs" "$run" "$IMAGE" "$rc" "$((t1-t0))"
    printf '"n_contigs_fasta":%d,"n_segments_gfa":%d,' "$nfa" "$ngfa"
    printf '"fasta_sha256":"%s","gfa_sha256":"%s",' "$(sha256sum "$fa" | cut -d' ' -f1)" "$(sha256sum "$gfa" | cut -d' ' -f1)"
    printf '"long_read_input":false,"unpaired_input":false,"protocol":"unicycler -1 R1 -2 R2 -o /tmp/a -t 8 --keep 1"}\n'
  } > "$RECD/$bs.json"

  echo "ok" > "$STATE/$bs.VERIFIED"
  say "DONE $bs ($((t1-t0))s, $nfa contigs)"
  return 0
}

mapfile -t PAIRS < <(awk -F'\t' 'NR>1 && $3==1 {print $1"\t"$2}' "$MAN" | sort -u)
say "assembly start: ${#PAIRS[@]} isolates, $SLOTS slots, image $IMAGE"

for p in "${PAIRS[@]}"; do
  bs="${p%%$'\t'*}"; run="${p##*$'\t'}"
  ( assemble_one "$bs" "$run" ) &
  while (( $(jobs -rp | wc -l) >= SLOTS )); do sleep 10; done
done
wait

ok=$(ls "$STATE" 2>/dev/null | grep -c '\.VERIFIED$' || true)
bad=$(ls "$STATE" 2>/dev/null | grep -c '\.FAILED$' || true)
say "assembly complete: $ok VERIFIED, $bad FAILED"
[[ "$bad" -gt 0 ]] && exit 1
exit 0

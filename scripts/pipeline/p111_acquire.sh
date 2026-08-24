#!/usr/bin/env bash
# P1.11 read acquisition. Runs on the OCI host. Reuses the existing volume and layout.
#
#   * Downloads ONLY the files named in the frozen P1.11 read manifest.
#   * Verifies every file against its recorded md5 BEFORE it is accepted.
#   * Handles the ENA-route isolates ONLY. The four sealed SRA_ONLY isolates are acquired by
#     p111_acquire_sra.sh via the approved prefetch -> fasterq-dump route; they are skipped here
#     and their absent ENA md5 is NOT an acquisition failure.
#   * Enforces a hard cumulative download ceiling. The job aborts rather than exceed it.
#   * Idempotent: an already-verified file is skipped, so a re-run resumes.
#
# Usage: p111_acquire.sh <manifest.tsv> <outdir> <limit_gb>
set -euo pipefail

MAN="${1:?manifest}"
OUT="${2:?outdir}"
LIMIT_GB="${3:-100}"
LIMIT_B=$(( LIMIT_GB * 1024 * 1024 * 1024 ))

mkdir -p "$OUT" "$OUT/../receipts/acquire"
REC="$OUT/../receipts/acquire"
LOG="$REC/acquire.log"

say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

used_bytes() { du -sb "$OUT" 2>/dev/null | cut -f1 || echo 0; }

# ---------------------------------------------------------------- main loop
say "acquisition start: manifest=$MAN out=$OUT limit=${LIMIT_GB}GB"
# CRITICAL: pre-filter to ENA rows with awk, never with `read`.
#
# Bash collapses RUNS of IFS whitespace, and TAB IS WHITESPACE even when IFS is set to only tab.
# The SRA_ONLY rows carry empty url and md5 fields, so their consecutive tabs collapsed and every
# later field shifted left: `route` came back empty instead of SRA_ONLY, the guard never fired, and
# an SRA-generated FASTQ was mistaken for a corrupt ENA download and deleted. awk does not collapse
# empty fields, so the split is done there and the loop only ever sees complete ENA rows.
ENA_MAN=$(mktemp)
trap 'rm -f "$ENA_MAN"' EXIT
awk -F'\t' 'NR>1 && $15=="ENA" && $16!="True" && $5!="" && $6!=""' "$MAN" > "$ENA_MAN"
n_sra=$(awk -F'\t' 'NR>1 && ($15=="SRA_ONLY" || $16=="True")' "$MAN" | wc -l)
say "manifest split: $(wc -l < "$ENA_MAN") ENA rows; $n_sra SRA_ONLY rows delegated to p111_acquire_sra.sh"

n_ok=0; n_skip=0; n_fail=0
while IFS=$'\t' read -r bs run mate fn url md5 bytes inst src strat layout rc bc ftpok route defer; do
  [[ -z "$bs" ]] && continue

  # Fail loudly rather than act on a mis-parsed row.
  if [[ "$route" != "ENA" || -z "$url" || ${#md5} -ne 32 ]]; then
    say "ABORT: malformed row for $bs/$fn (route=[$route] md5_len=${#md5}) - refusing to touch it"
    exit 4
  fi

  d="$OUT/$bs"; mkdir -p "$d"; f="$d/$fn"

  if [[ -s "$f" ]]; then
    got=$(md5sum "$f" | cut -d' ' -f1)
    if [[ "$got" == "$md5" ]]; then
      n_skip=$((n_skip+1)); continue
    fi
    say "re-downloading $bs/$fn (md5 mismatch on existing file)"
    rm -f "$f"
  fi

  cur=$(used_bytes)
  if (( cur + ${bytes:-0} > LIMIT_B )); then
    say "ABORT: downloading $fn would exceed the ${LIMIT_GB}GB ceiling (used $((cur/1024/1024/1024))GB)"
    exit 2
  fi

  say "GET $bs/$fn ($(( ${bytes:-0} / 1024 / 1024 )) MB)"
  # ENA drops the TLS connection mid-transfer on large files under sustained load
  # (curl 56: SSL_read unexpected eof). RESUME with -C - rather than restarting, and retry on any
  # error, not just HTTP status. Restarting a 1.2 GB file from zero simply fails the same way.
  ok=0
  for attempt in 1 2 3 4 5 6 7 8; do
    have=$(stat -c %s "$f" 2>/dev/null || echo 0)
    # An OVERSIZED partial means the file is poisoned: a resume appended onto a base that had been
    # truncated and rewritten, so the bytes no longer line up. Resuming again only compounds it.
    # Discard and start clean.
    if [[ -n "$bytes" && "$have" -gt "$bytes" ]]; then
      say "  oversize partial ($have > $bytes) - discarding and restarting clean"
      rm -f "$f"; have=0
    fi
    if [[ -n "$bytes" && "$have" -eq "$bytes" ]]; then ok=1; break; fi
    # NO internal --retry here. `-C -` resolves the resume offset ONCE at curl startup, so an
    # internal retry restarts from that original offset and TRUNCATES whatever the failed attempt
    # gained - progress oscillates instead of advancing. One attempt per iteration lets the outer
    # loop re-read the true file size and resume from it.
    curl -fsS -C - --max-time 1800 -o "$f" "$url" 2>/dev/null && { ok=1; break; }
    sleep 10
    grew=$(stat -c %s "$f" 2>/dev/null || echo 0)
    say "  attempt $attempt incomplete: $grew / ${bytes:-?} bytes, resuming"
    # if a whole attempt made no progress at all, the partial file may be poisoned; start clean
    [[ "$grew" == "$have" && "$attempt" -ge 4 ]] && { rm -f "$f"; say "  no progress; restarting clean"; }
  done
  if [[ "$ok" != "1" ]]; then
    say "FAIL download $bs/$fn"; n_fail=$((n_fail+1)); rm -f "$f"; continue
  fi

  got=$(md5sum "$f" | cut -d' ' -f1)
  if [[ "$got" != "$md5" ]]; then
    say "FAIL md5 $bs/$fn  want=$md5 got=$got"; n_fail=$((n_fail+1)); rm -f "$f"; continue
  fi
  gb=$(stat -c %s "$f")
  if [[ -n "$bytes" && "$gb" != "$bytes" ]]; then
    say "FAIL size $bs/$fn want=$bytes got=$gb"; n_fail=$((n_fail+1)); rm -f "$f"; continue
  fi
  n_ok=$((n_ok+1))
done < "$ENA_MAN"

say "ENA acquisition done: downloaded=$n_ok already_verified=$n_skip failed=$n_fail sra_deferred=$n_sra"
say "total on disk: $(( $(used_bytes) / 1024 / 1024 / 1024 )) GB of ${LIMIT_GB} GB"
[[ $n_fail -gt 0 ]] && exit 1
exit 0

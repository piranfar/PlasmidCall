#!/usr/bin/env bash
# Stream the P1.11 raw-as-executed set to the workstation in chunks.
# Chunked so a dropped SSH session costs one chunk, not the whole 53.76 GiB.
# Idempotent: re-running skips chunks whose files are already present and non-empty.
set -uo pipefail
K="${P111_SSH_KEY:?set P111_SSH_KEY to the private-key path}"
H="${P111_SSH_HOST:?set P111_SSH_HOST to user@host}"
SRC=/work
W=$SRC/p112/POSTTRUTH/preserve
DEST="E:/AMR_Evidence_Data/P1.11/raw_as_executed"
SP="${P111_WORKDIR:-.}"
CH="$SP/chunks"
mkdir -p "$DEST" "$CH"

# --- one round trip: bring the file list and the manifest down
scp -q -i "$K" -o StrictHostKeyChecking=no \
    $H:$W/filelist.txt $H:$W/RAW_AS_EXECUTED_MANIFEST.sha256 $H:$W/RAW_AS_EXECUTED_SIZES.tsv "$SP/"
echo "filelist rows: $(wc -l < "$SP/filelist.txt")"

rm -f "$CH"/chunk_*
split -l 2000 -d -a 3 "$SP/filelist.txt" "$CH/chunk_"
echo "chunks: $(ls "$CH"/chunk_* | wc -l)"

ok=0; fail=0; skipped=0
for cf in "$CH"/chunk_*; do
  c=$(basename "$cf")
  need=$(wc -l < "$cf")
  have=$(while IFS= read -r f; do [ -s "$DEST/$f" ] && echo x; done < "$cf" | wc -l)
  if [ "$have" -eq "$need" ]; then
    skipped=$((skipped+1)); printf "  %-12s SKIP (%d/%d)\n" "$c" "$have" "$need"; continue
  fi
  # send the chunk list up, then stream exactly those files
  scp -q -i "$K" -o StrictHostKeyChecking=no "$cf" $H:$W/$c
  done_ok=0
  for attempt in 1 2 3; do
    if ssh -i "$K" -o StrictHostKeyChecking=no -o ServerAliveInterval=30 $H \
         "cd $SRC && tar -cf - --files-from=$W/$c 2>/dev/null | pigz -1 -p 8" \
       | tar -xzf - -C "$DEST" 2>/dev/null; then
      ok=$((ok+1)); done_ok=1
      printf "  %-12s OK   (%d files, attempt %d)\n" "$c" "$need" "$attempt"; break
    fi
    printf "  %-12s retry %d\n" "$c" "$attempt"
  done
  [ "$done_ok" -eq 1 ] || { fail=$((fail+1)); printf "  %-12s FAILED\n" "$c"; }
done
echo "chunks ok=$ok skipped=$skipped failed=$fail"
[ "$fail" -eq 0 ] || exit 1
echo "TRANSFER_STREAM_DONE"

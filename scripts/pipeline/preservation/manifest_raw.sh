#!/usr/bin/env bash
# Finalise the raw-as-executed transfer set (now including p112/raw) and build a relative-path
# SHA-256 manifest on the server. Paths are relative to /work.
set -euo pipefail
B=/work
W=$B/p112/POSTTRUTH/preserve
cd "$B"

# p112/raw is now INCLUDED: 4 of 79 isolates are SRA_ONLY and carry no published FASTQ checksum,
# so their reads are not byte-reproducible from any recorded digest. Preserving only those four
# would leave an inconsistent archive, and the whole set stays under the 100 GB threshold.
grep -qx 'p112/raw' "$W/include_paths.txt" || echo 'p112/raw' >> "$W/include_paths.txt"

: > "$W/filelist.txt"
while IFS= read -r p; do
  [ -z "$p" ] && continue
  if [ -d "$p" ]; then find "$p" -type f -print >> "$W/filelist.txt"
  elif [ -f "$p" ]; then echo "$p" >> "$W/filelist.txt"; fi
done < "$W/include_paths.txt"
sort -u -o "$W/filelist.txt" "$W/filelist.txt"

N=$(wc -l < "$W/filelist.txt")
BYTES=$(tr '\n' '\0' < "$W/filelist.txt" | xargs -0 -n 500 stat -c%s | awk '{s+=$1} END{printf "%d", s+0}')
echo "=== FINAL TRANSFER SET ==="
printf "  files : %d\n  bytes : %d\n  GiB   : %.2f\n" "$N" "$BYTES" \
  "$(awk -v b=$BYTES 'BEGIN{print b/1073741824}')"
awk -v b="$BYTES" 'BEGIN{ if (b/1073741824 < 100) printf "  GATE  : %.2f GiB < 100 GB -> proceed\n", b/1073741824;
                          else printf "  GATE  : TRANSFER_EXCEEDS_100GB_AWAITING_APPROVAL\n" }'

echo "=== building SHA-256 manifest (relative paths) ==="
tr '\n' '\0' < "$W/filelist.txt" \
  | xargs -0 -P 8 -n 100 sha256sum \
  | sed 's|  \./|  |' \
  | sort -k2 > "$W/RAW_AS_EXECUTED_MANIFEST.sha256"
M=$(wc -l < "$W/RAW_AS_EXECUTED_MANIFEST.sha256")
echo "  manifest rows: $M   (filelist rows: $N)"
[ "$M" -eq "$N" ] || { echo "  *** ROW COUNT MISMATCH ***"; exit 1; }

# a size+path sidecar so the destination can detect truncation as well as corruption
while IFS= read -r f; do printf '%s\t%s\n' "$(stat -c%s "$f")" "$f"; done < "$W/filelist.txt" \
  > "$W/RAW_AS_EXECUTED_SIZES.tsv"
sha256sum "$W/RAW_AS_EXECUTED_MANIFEST.sha256" | sed 's|.*/||' > "$W/MANIFEST_OF_MANIFEST.sha256"
echo "  manifest sha256: $(cut -d' ' -f1 "$W/MANIFEST_OF_MANIFEST.sha256")"
echo "  source root    : $B"
echo "  generated_utc  : $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "MANIFEST_OK"

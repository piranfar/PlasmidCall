#!/usr/bin/env bash
# Final packaging of the manuscript archive, run ONCE after the raw-as-executed transfer is
# verified. Folds in the preservation receipt, drops the transient chunk splits, regenerates the
# manifest, verifies every row by full recomputation, and repacks.
set -euo pipefail
P=/work/p112
A=$P/ARCHIVE_P1.11
W=$P/POSTTRUTH/preserve

# transfer scaffolding: the chunk splits are mechanical slices of filelist.txt, fully derivable
rm -f "$W"/chunk_*
# keep filelist, the SHA-256 manifest, the sizes sidecar and the receipt -- those ARE the record
ls -la "$W" | sed 's/^/  /'

rsync -a --delete --exclude 'images/*.tar.zst' --exclude 'images/*.sha256' \
      "$P/POSTTRUTH/" "$A/POSTTRUTH/"

cd "$A"
TMP=$(mktemp /tmp/am.XXXXXX)
find . -type f ! -name 'ARCHIVE_MANIFEST.tsv' ! -name 'ARCHIVE_MANIFEST.tsv.*' -print0 \
  | sort -z | xargs -0 -P 8 -n 200 sha256sum \
  | while IFS= read -r l; do
      h=${l%% *}; f=${l#* }; f=${f# }
      printf '%s\t%s\t%s\n' "$h" "$(stat -c%s "$f")" "$f"
    done | sort -k3,3 > "$TMP"
mv "$TMP" "$A/ARCHIVE_MANIFEST.tsv"; chmod 644 "$A/ARCHIVE_MANIFEST.tsv"
echo "  manifest rows: $(wc -l < "$A/ARCHIVE_MANIFEST.tsv")"
grep -c 'ARCHIVE_MANIFEST' "$A/ARCHIVE_MANIFEST.tsv" 2>/dev/null || echo "  self-reference rows: 0"

bad=0; n=0
while IFS=$'\t' read -r h s f; do
  n=$((n+1))
  [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$h" ] && [ "$(stat -c%s "$f")" = "$s" ] || {
    echo "  MISMATCH $f"; bad=$((bad+1)); }
done < "$A/ARCHIVE_MANIFEST.tsv"
echo "  full recomputation: $n rows, mismatches $bad"
[ "$bad" -eq 0 ]

echo "  preservation receipt inside archive: $(ls "$A/POSTTRUTH/preserve/PRESERVATION_RECEIPT.json" 2>/dev/null || echo MISSING)"

cd "$P"
rm -f /work/P1.11_ARCHIVE.tar.zst /work/P1.11_ARCHIVE.tar.zst.sha256
tar -cf - ARCHIVE_P1.11 | zstd -T0 -10 -q -o /work/P1.11_ARCHIVE.tar.zst
cd /work
sha256sum P1.11_ARCHIVE.tar.zst | tee P1.11_ARCHIVE.tar.zst.sha256
stat -c '  bytes: %s' P1.11_ARCHIVE.tar.zst
echo FINAL_REPACK_OK

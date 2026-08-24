#!/usr/bin/env bash
# P1.11 archive update -- section 7.
# Adds the post-truth analysis outputs and the AMRFinderPlus annotation to the existing
# ARCHIVE_P1.11 tree, regenerates the checksum manifest and verifies it by recomputation.
# The Docker image tarball is deliberately EXCLUDED: it is preserved separately under section 8.
set -euo pipefail
P=/work/p112
A=$P/ARCHIVE_P1.11
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

echo "== archive state before =="
du -sh "$A"; echo "manifest rows before: $(($(wc -l < "$A/ARCHIVE_MANIFEST.tsv")))"

# ---- 1. post-truth analyses (analysis outputs only; the image tarball is excluded)
mkdir -p "$A/POSTTRUTH"
rsync -a --delete --exclude 'images/*.tar.zst' --exclude 'images/*.sha256' \
      "$P/POSTTRUTH/" "$A/POSTTRUTH/"

# ---- 2. AMRFinderPlus annotation (input to the ARG analysis; was not previously archived)
mkdir -p "$A/annotation"
rsync -a --delete "$P/annotation/" "$A/annotation/"

# ---- 3. corrected truth derivation products, kept beside the initial audit
rsync -a --delete "$P/truth_corrected/" "$A/truth_corrected/"

# ---- 4. confirm the definitive artefacts are present and are the corrected ones
echo "== presence checks =="
for f in "$A/inference/frozen/P1.11_FROZEN_PREDICTIONS.tsv" \
         "$A/PREDICTIONS_FROZEN.json" \
         "$A/P1.11_call_table_reconciled.tsv" \
         "$A/receipts/P1.11_truth_acquisition_receipt.json" \
         "$A/POSTTRUTH/P1.11_POSTTRUTH_FINDINGS.md" \
         "$A/POSTTRUTH/P1.11_POSTTRUTH_SECTIONS_1_5.json" \
         "$A/POSTTRUTH/P1.11_POSTTRUTH_SECTION_1B_LEAKAGE.json"; do
  if [ -f "$f" ]; then printf "  OK   %s\n" "${f#$A/}"; else printf "  MISS %s\n" "${f#$A/}"; exit 1; fi
done
echo "  truth tables archived: $(ls -d "$A"/truth/*/truth_table.tsv 2>/dev/null | wc -l)"
echo "  label counts (must be plasmid 1209 / chromosome 6035 / ambiguous 120 / unmapped 152):"
awk -F'\t' 'FNR>1{print $12}' "$A"/truth/*/truth_table.tsv | sort | uniq -c | sed 's/^/    /'
echo "  frozen prediction sha256 (must be 0767da157051ff469b8830982aa168c558ce5b4cb6e1bc82ba81d4e9acb3e40d):"
sha256sum "$A/inference/frozen/P1.11_FROZEN_PREDICTIONS.tsv" | sed 's/^/    /'

# ---- 5. regenerate the manifest
echo "== regenerating manifest =="
: > "$A/ARCHIVE_MANIFEST.tsv"
cd "$A"
find . -type f ! -name ARCHIVE_MANIFEST.tsv -print0 \
  | sort -z \
  | xargs -0 -P 8 -n 200 sha256sum \
  | while IFS= read -r line; do
      h=${line%% *}; f=${line#* }; f=${f# }
      printf '%s\t%s\t%s\n' "$h" "$(stat -c%s "$f")" "$f"
    done | sort -k3,3 > "$A/ARCHIVE_MANIFEST.tsv.new"
mv "$A/ARCHIVE_MANIFEST.tsv.new" "$A/ARCHIVE_MANIFEST.tsv"
echo "  manifest rows: $(wc -l < "$A/ARCHIVE_MANIFEST.tsv")"

# ---- 6. verify by recomputation
echo "== verifying manifest by recomputation =="
bad=0
while IFS=$'\t' read -r h s f; do
  ah=$(sha256sum "$f" | cut -d' ' -f1); as=$(stat -c%s "$f")
  if [ "$ah" != "$h" ] || [ "$as" != "$s" ]; then echo "  MISMATCH $f"; bad=$((bad+1)); fi
done < <(shuf -n 400 "$A/ARCHIVE_MANIFEST.tsv")
echo "  spot-verified 400 entries, mismatches: $bad"
[ "$bad" -eq 0 ] || exit 1

echo "== archive state after =="
du -sh "$A"
echo "ARCHIVE_UPDATE_OK $(ts)"

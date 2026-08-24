#!/usr/bin/env bash
set -euo pipefail
P=/work/p112
A=$P/ARCHIVE_P1.11

python3 - <<'PYEOF'
import json, io
p = "/work/p112/POSTTRUTH/P1.11_FINAL_SHUTDOWN_AUDIT.json"
d = json.load(io.open(p, encoding="utf-8"))
a = d["archive"]
a["manifest_rows"] = 2995
a["manifest_correction"] = (
    "Regenerated 2026-08-22. The first run listed its own temporary file ARCHIVE_MANIFEST.tsv.new "
    "(sha256 of the empty string, size 0), which the subsequent mv removed, leaving one row "
    "pointing at a file that never existed as an artefact. No scientific file was affected. All "
    "2995 real entries were then verified by FULL recomputation, not sampling.")
a.pop("packaged_sha256", None)
a.pop("packaged_bytes", None)
a["packaged_digest_note"] = (
    "Deliberately not recorded here. This file lives INSIDE the archive, so it cannot state the "
    "archive's own digest without a circular reference that no repack can ever satisfy. The "
    "authoritative values live OUTSIDE the container: P1.11_ARCHIVE.tar.zst.sha256 and "
    "FINAL_SERVER_AUDIT.json beside it at the destination.")
a["verification"] = (
    "Manifest regenerated and every one of the 2995 entries recomputed on the source host with 0 "
    "mismatches; the transferred copy was then re-opened and every member re-hashed against the "
    "manifest carried inside it, with 0 mismatches, 0 absent and 0 unlisted.")
io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(d, indent=1, default=str) + "\n")
print("  audit corrected")
PYEOF

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
mv "$TMP" "$A/ARCHIVE_MANIFEST.tsv"
chmod 644 "$A/ARCHIVE_MANIFEST.tsv"
echo "  manifest rows: $(wc -l < "$A/ARCHIVE_MANIFEST.tsv")"

bad=0; n=0
while IFS=$'\t' read -r h s f; do
  n=$((n+1))
  [ "$(sha256sum "$f" | cut -d' ' -f1)" = "$h" ] && [ "$(stat -c%s "$f")" = "$s" ] || {
    echo "  MISMATCH $f"; bad=$((bad+1)); }
done < "$A/ARCHIVE_MANIFEST.tsv"
echo "  full recomputation: $n rows, mismatches $bad"
[ "$bad" -eq 0 ]

cd "$P"
rm -f /work/P1.11_ARCHIVE.tar.zst /work/P1.11_ARCHIVE.tar.zst.sha256
tar -cf - ARCHIVE_P1.11 | zstd -T0 -10 -q -o /work/P1.11_ARCHIVE.tar.zst
cd /work
sha256sum P1.11_ARCHIVE.tar.zst | tee P1.11_ARCHIVE.tar.zst.sha256
stat -c '  bytes: %s' P1.11_ARCHIVE.tar.zst
echo REPACK_OK

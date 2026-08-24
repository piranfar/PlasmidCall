#!/usr/bin/env bash
# P1.11 raw-as-executed preservation: build the explicit transfer set, size it, and gate on the
# standing 100 GB approval threshold BEFORE moving anything.
set -euo pipefail
B=/work
W=$B/p112/POSTTRUTH/preserve
mkdir -p "$W"
cd "$B"

# ---- explicit include list, relative to /work -------------------------------------
# Everything below is either an as-executed scientific artefact or a file needed to reproduce
# parsing. Deliberate exclusions are recorded in EXCLUSIONS below.
: > "$W/include_paths.txt"
cat >> "$W/include_paths.txt" <<'EOF'
p112/assemblies
p112/inference/native
p112/inference/state
p112/inference/receipts
p112/inference/logs
p112/inference/parsed
p112/inference/frozen
p112/annotation
p112/truth
p112/truth_corrected
p112/truth_hold
p112/INITIAL_REFSEQ_ONLY_AUDIT
p112/receipts
p112/env
p112/scripts
p112/manifests
p112/logs
p112/work
p112/preflight
p112/preflight2
p111/manifests
p111/screen
p111/receipts
p111/logs
p111/pilot
p111/SCREEN_TS
EOF
# loose top-level files that are scientific artefacts
for f in p112/inference/P1.11_call_table_reconciled.tsv \
         p112/inference/P1.10_predictions_normalised.tsv \
         p112/inference/P1.10_parse_summary.json \
         p112/inference/PREDICTIONS_FROZEN.json \
         p112/plasmidcall_v1_2_general.pkl \
         p111/tools/apply_screen.py p111/tools/fastq_equivalence.py \
         p111/tools/fetch_candidates.py p111/tools/fetch_candidates.sh \
         p111/tools/run_screen.sh p111/tools/SRATOOLS_PATH; do
  [ -e "$f" ] && echo "$f" >> "$W/include_paths.txt"
done

# ---- enumerate every regular file in the set ---------------------------------------------------
: > "$W/filelist.txt"
while IFS= read -r p; do
  [ -z "$p" ] && continue
  if [ -d "$p" ]; then find "$p" -type f -print >> "$W/filelist.txt"
  elif [ -f "$p" ]; then echo "$p" >> "$W/filelist.txt"; fi
done < "$W/include_paths.txt"
sort -u -o "$W/filelist.txt" "$W/filelist.txt"

N=$(wc -l < "$W/filelist.txt")
BYTES=$(tr '\n' '\0' < "$W/filelist.txt" | xargs -0 stat -c%s 2>/dev/null | awk '{s+=$1} END{print s+0}')
GB=$(awk -v b="$BYTES" 'BEGIN{printf "%.2f", b/1073741824}')

echo "=== TRANSFER SET ==="
echo "  files: $N"
echo "  bytes: $BYTES  (${GB} GiB)"
echo
echo "=== per-top-level breakdown ==="
awk -F/ '{print $1"/"$2}' "$W/filelist.txt" | sort | uniq -c | sort -rn | head -30 | while read -r c d; do
  sz=$(grep -c . /dev/null; true)
  printf "  %-40s %6d files\n" "$d" "$c"
done
echo
echo "=== byte breakdown by top-level ==="
while IFS= read -r f; do printf '%s\t%s\n' "$(echo "$f" | cut -d/ -f1-2)" "$(stat -c%s "$f")"; done < "$W/filelist.txt" \
  | awk -F'\t' '{s[$1]+=$2} END{for(k in s) printf "  %-40s %12.2f MiB\n", k, s[k]/1048576}' | sort -k2 -rn
echo
echo "=== 100 GB THRESHOLD GATE ==="
awk -v g="$GB" 'BEGIN{ if (g < 100) printf "  %.2f GiB < 100 GB -> BELOW THRESHOLD, no approval stop required\n", g;
                       else printf "  %.2f GiB >= 100 GB -> TRANSFER_EXCEEDS_100GB_AWAITING_APPROVAL\n", g }'
echo
echo "=== DELIBERATE EXCLUSIONS ==="
cat <<'EOF'
  p112/raw                      32 GB of input FASTQ. NOT in the enumerated preservation list
                                (that list names "sealed input assemblies", not reads). Publicly
                                recoverable: the sealed cohort manifest records fastq_md5 and
                                fastq_ftp for every isolate, so the exact bytes are re-obtainable
                                and checksum-verifiable. Coverage verified separately below.
  p112/ARCHIVE_P1.11            already preserved off-host as P1.11_ARCHIVE.tar.zst (sha256
                                370a84a7...), verified. Copying the tree again would duplicate it.
  p112/POSTTRUTH/images         already preserved off-host as p112_all_images.tar.zst (sha256
                                abe433e7...), verified 16/16 image identities.
  p112/POSTTRUTH (analyses)     already preserved twice: inside the manuscript archive and in the
                                git working tree.
  p111/tools/sratoolkit*        303 MB third-party binary distribution (SRA Toolkit 3.1.1,
                                public download). The wrapper scripts ARE preserved.
  docker build cache            94.22 GB, regenerable, not an artefact.
  /tmp scratch                  not referenced by any receipt or manifest.
EOF
echo
echo "=== fastq recoverability check (justifies excluding p112/raw) ==="
awk -F'\t' 'NR>1{n++; if($19!="" && $19!="na") m++; if($20!="" && $20!="na") f++}
            END{printf "  isolates=%d  with fastq_md5=%d  with fastq_ftp=%d\n", n, m, f}' \
  "$B/p111/manifests/P1.11_cohort_independent.tsv"
echo
echo "=== destination free space must be checked on the workstation ==="
df -h /work | tail -1

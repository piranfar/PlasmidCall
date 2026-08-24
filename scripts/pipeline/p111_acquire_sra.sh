#!/usr/bin/env bash
# P1.11 acquisition for the four sealed SRA-ONLY isolates.
#
# APPROVED ROUTE: NCBI SRA via prefetch -> fasterq-dump --split-3, exactly as validated in the
# P1.11 equivalence and feasibility pilots (receipts/PILOT_SRA_ACQUISITION.txt).
#
#   * No ENA FASTQ mirror is required, sought, or treated as authoritative for these isolates.
#   * A missing ENA md5 is NOT an acquisition failure: no ENA rendition exists for them.
#   * The route is not changed without a provenance-based reason. If an ENA mirror has appeared
#     since screening it is DOCUMENTED for the record and the SRA route is still used.
#
# Recorded per isolate: SRA run accession, prefetch validation, .sra size and sha256, census
# sra_md5s where available, spot count, mate counts read/written, generated FASTQ sha256 and
# bytes, quality alphabet, and the acquisition route.
#
# sra-tools 3.1.1 is already installed on the host from the pilot:
#   /data/trace-arg/p111/tools/sratoolkit.3.1.1-ubuntu64/bin
#   tarball sha256 b668dbfa2e93041746d1c313691272aea4b9ea52b291d7afb79d46dc05367688
# No pinned image is modified.
#
# Usage: p111_acquire_sra.sh <sra_manifest.tsv> <outdir> <sratools_bin> <scratch>
set -euo pipefail

MAN="${1:?sra manifest}"
OUT="${2:?outdir}"
SRABIN="${3:-/data/trace-arg/p111/tools/sratoolkit.3.1.1-ubuntu64/bin}"
SCRATCH="${4:-/data/trace-arg/p112/scratch/sra}"

REC="$OUT/../receipts/acquire"
mkdir -p "$OUT" "$REC" "$SCRATCH"
LOG="$REC/acquire_sra.log"
OUTREC="$REC/P1.11_sra_acquisition_receipts.tsv"

say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }

if [[ ! -x "$SRABIN/prefetch" || ! -x "$SRABIN/fasterq-dump" ]]; then
  say "ERROR: sra-tools not found at $SRABIN"; exit 3
fi
say "sra-tools: $("$SRABIN/prefetch" --version 2>&1 | tr '\n' ' ')"

if [[ ! -s "$OUTREC" ]]; then
  printf 'biosample\trun_accession\troute\tprefetch_valid\tsra_bytes\tsra_sha256\tcensus_sra_md5s\texpected_spots\tobserved_spots\treads_read\treads_written\torphans\tfq1\tfq1_bytes\tfq1_sha256\tfq2\tfq2_bytes\tfq2_sha256\tqual_alphabet_size\tena_mirror_now_available\tutc\n' > "$OUTREC"
fi

n_ok=0; n_fail=0
while IFS=$'\t' read -r bs run spots census_md5; do
  [[ "$bs" == "biosample" || -z "$bs" ]] && continue

  d="$OUT/$bs"; mkdir -p "$d"
  f1="$d/${run}_1.fastq.gz"; f2="$d/${run}_2.fastq.gz"
  if [[ -s "$f1" && -s "$f2" ]] && grep -q "^$bs	$run	" "$OUTREC" 2>/dev/null; then
    say "SKIP $bs/$run (already acquired and receipted)"; n_ok=$((n_ok+1)); continue
  fi

  # ---- document whether an ENA mirror has appeared since screening. Documented only; the
  #      approved SRA route is used regardless.
  ena_now="unknown"
  if api=$(curl -fsS --max-time 60 "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=${run}&result=read_run&fields=fastq_ftp&format=tsv&download=false" 2>/dev/null); then
    if printf '%s' "$api" | sed -n '2p' | cut -f2 | grep -q 'fastq.gz'; then ena_now="yes"; else ena_now="no"; fi
  fi
  say "$bs/$run: ENA mirror now available = $ena_now (documented; approved SRA route used regardless)"

  # ---- 1. prefetch
  say "prefetch $run"
  rm -rf "$SCRATCH/$run"
  pf_log="$REC/${run}.prefetch.log"
  if ! "$SRABIN/prefetch" --max-size u --output-directory "$SCRATCH" "$run" > "$pf_log" 2>&1; then
    say "FAIL prefetch $run"; n_fail=$((n_fail+1)); continue
  fi
  sra_file=$(find "$SCRATCH/$run" -name "*.sra" -o -name "$run" -type f | head -1)
  [[ -z "$sra_file" ]] && sra_file="$SCRATCH/$run/$run.sra"
  if [[ ! -s "$sra_file" ]]; then
    say "FAIL prefetch $run (no .sra produced)"; n_fail=$((n_fail+1)); continue
  fi
  pf_valid=$(grep -qiE "is valid|was valid" "$pf_log" && echo "true" || echo "not_reported")
  sra_bytes=$(stat -c %s "$sra_file")
  sra_sha=$(sha256sum "$sra_file" | cut -d' ' -f1)
  say "  .sra $sra_bytes B sha256 ${sra_sha:0:16} valid=$pf_valid"

  # ---- 2. vdb-validate, where available
  if [[ -x "$SRABIN/vdb-validate" ]]; then
    "$SRABIN/vdb-validate" "$sra_file" > "$REC/${run}.vdb-validate.log" 2>&1 || \
      say "  NOTE vdb-validate returned non-zero for $run (logged)"
  fi

  # ---- 3. fasterq-dump --split-3, exactly as piloted
  say "fasterq-dump --split-3 $run"
  fq_log="$REC/${run}.fasterq.log"
  rm -f "$d/${run}"_*.fastq
  if ! "$SRABIN/fasterq-dump" --split-3 --threads 8 --outdir "$d" \
        --temp "$SCRATCH/tmp_$run" "$sra_file" > "$fq_log" 2>&1; then
    say "FAIL fasterq-dump $run"; n_fail=$((n_fail+1)); continue
  fi
  reads_read=$(grep -oP 'reads read\s*:\s*\K[0-9,]+' "$fq_log" | tr -d ',' | head -1)
  reads_written=$(grep -oP 'reads written\s*:\s*\K[0-9,]+' "$fq_log" | tr -d ',' | head -1)
  spots_obs=$(grep -oP 'spots read\s*:\s*\K[0-9,]+' "$fq_log" | tr -d ',' | head -1)
  : "${reads_read:=0}"; : "${reads_written:=0}"; : "${spots_obs:=0}"

  r1="$d/${run}_1.fastq"; r2="$d/${run}_2.fastq"; r0="$d/${run}.fastq"
  if [[ ! -s "$r1" || ! -s "$r2" ]]; then
    say "FAIL $run: fasterq-dump did not produce a mate pair"; n_fail=$((n_fail+1)); continue
  fi
  orphans=0
  if [[ -s "$r0" ]]; then
    orphans=$(( $(wc -l < "$r0") / 4 ))
    say "  NOTE $run: $orphans orphan reads in ${run}.fastq - recorded, NOT an assembly input"
    mv "$r0" "$d/${run}.orphans.fastq"
  fi

  if [[ "$spots_obs" != "0" && -n "$spots" && "$spots_obs" != "$spots" ]]; then
    say "  WARN $run: observed spots $spots_obs != census $spots"
  fi
  if [[ "$reads_read" != "$reads_written" ]]; then
    say "  WARN $run: reads read $reads_read != written $reads_written"
  fi

  # ---- 4. compress and receipt
  gzip -f "$r1" "$r2"
  b1=$(stat -c %s "$f1"); b2=$(stat -c %s "$f2")
  s1=$(sha256sum "$f1" | cut -d' ' -f1); s2=$(sha256sum "$f2" | cut -d' ' -f1)
  # awk stops itself rather than being SIGPIPEd by head: under `set -euo pipefail` a SIGPIPE
  # (exit 141) in this pipeline aborted the whole script after gzip but before the receipt.
  # Compute in a subshell WITHOUT pipefail, then keep only the first line. `{ ...; } || echo 0`
  # emitted BOTH values when SIGPIPE still tripped pipefail, embedding a newline in the TSV field.
  qa=$(set +o pipefail; zcat "$f1" 2>/dev/null | awk 'NR%4==0{print; n++} n>=4000{exit}'        | fold -w1 | sort -u | wc -l)
  qa=${qa%%$'
'*}; qa=${qa//[^0-9]/}; : "${qa:=0}"
  say "  ${run}_1 $b1 B sha256 ${s1:0:16} | ${run}_2 $b2 B sha256 ${s2:0:16} | qual alphabet $qa"

  printf '%s\t%s\tSRA_prefetch_fasterq-dump\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$bs" "$run" "$pf_valid" "$sra_bytes" "$sra_sha" "$census_md5" "$spots" "$spots_obs" \
    "$reads_read" "$reads_written" "$orphans" \
    "${run}_1.fastq.gz" "$b1" "$s1" "${run}_2.fastq.gz" "$b2" "$s2" "$qa" "$ena_now" \
    "$(date -u +%FT%TZ)" >> "$OUTREC"

  rm -rf "$SCRATCH/$run" "$SCRATCH/tmp_$run"
  n_ok=$((n_ok+1))
done < "$MAN"

say "SRA acquisition done: $n_ok ok, $n_fail failed"
say "receipts: $OUTREC"
[[ $n_fail -gt 0 ]] && exit 1
exit 0

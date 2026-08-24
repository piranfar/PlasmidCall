#!/usr/bin/env bash
# P1.13 stage 3 -- per-assembly file availability, then reference-genome retrieval for the ANI
# screen only. NO sequencing reads are downloaded and NO panel tool is executed here.
# One md5checksums.txt request per assembly establishes the presence of genomic FASTA, GBFF and
# assembly report together.
set -uo pipefail
W=/work/p113
G=$W/screen/genomes/p113
mkdir -p "$G" "$W/screen"
cd "$W"

python3 - <<'PY'
import json, io, os
W="/work/p113"
rows=json.load(io.open(W+"/_eligible_stage2.json",encoding="utf-8"))
pool=[r for r in rows if r["seq_rel_date"][:4] >= "2023"]
with io.open(W+"/pool_2023plus.tsv","w",encoding="utf-8",newline="\n") as f:
    for r in pool:
        f.write("%s\t%s\t%s\t%s\n"%(r["biosample"],r["assembly_accession"],r["taxon"],r["ftp_path"]))
print("pool 2023+: %d"%len(pool))
PY

echo "=== file availability (assembly report + genomic FASTA + GBFF) ==="
check_one() {
  bs="$1"; asm="$2"; tax="$3"; ftp="$4"
  base=$(basename "${ftp%/}")
  url="${ftp%/}/md5checksums.txt"
  url="${url/ftp:\/\//https://}"
  m=$(curl -sSL --max-time 45 --retry 2 "$url" 2>/dev/null)
  [ -z "$m" ] && { echo -e "$bs\t$asm\t$tax\t$ftp\tNO_MD5FILE\t\t\t"; return; }
  fa=$(echo "$m" | grep -c "${base}_genomic.fna.gz$"  || true)
  gb=$(echo "$m" | grep -c "${base}_genomic.gbff.gz$" || true)
  ar=$(echo "$m" | grep -c "${base}_assembly_report.txt$" || true)
  famd5=$(echo "$m" | awk -v p="./${base}_genomic.fna.gz" '$2==p{print $1}')
  if [ "$fa" -ge 1 ] && [ "$gb" -ge 1 ] && [ "$ar" -ge 1 ]; then st=OK; else st=INCOMPLETE; fi
  echo -e "$bs\t$asm\t$tax\t$ftp\t$st\tfna=$fa\tgbff=$gb\treport=$ar\t$famd5"
}
export -f check_one
: > file_availability.tsv
awk -F'\t' '{print $1"\t"$2"\t"$3"\t"$4}' pool_2023plus.tsv \
  | xargs -P 12 -I{} bash -c 'IFS=$'"'"'\t'"'"' read -r a b c d <<< "{}"; check_one "$a" "$b" "$c" "$d"' \
  >> file_availability.tsv 2>/dev/null
echo "  checked: $(wc -l < file_availability.tsv)"
awk -F'\t' '{c[$5]++} END{for(k in c) printf "    %-12s %d\n", k, c[k]}' file_availability.tsv

echo
echo "=== retrieve reference genomes for the ANI screen (FASTA only) ==="
ok=0; fail=0
while IFS=$'\t' read -r bs asm tax ftp st a b c md5; do
  [ "$st" = "OK" ] || continue
  out="$G/${bs}.fna.gz"
  [ -s "$out" ] && { ok=$((ok+1)); continue; }
  base=$(basename "${ftp%/}")
  url="${ftp%/}/${base}_genomic.fna.gz"; url="${url/ftp:\/\//https://}"
  if curl -sSL --fail --max-time 300 --retry 3 -o "$out" "$url" 2>/dev/null && [ -s "$out" ]; then
    ok=$((ok+1))
  else
    rm -f "$out"; fail=$((fail+1))
  fi
done < file_availability.tsv
echo "  genomes retrieved: $ok   failed: $fail"
du -sh "$G"
echo FILES_STAGE3_DONE

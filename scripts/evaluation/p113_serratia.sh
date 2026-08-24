#!/usr/bin/env bash
# P1.13 AMENDMENT 1 -- Serratia spp. release-date fallback extended to 2022.
# The frozen selection procedure is TIERED, so the 22 isolates already selected from the 2024+ and
# 2023 tiers are PRESERVED and only the 3 remaining positions are filled from 2022. No isolate is
# hand-picked; the same deterministic farthest-point rule is applied.
set -uo pipefail
W=/work/p113
G=$W/screen/genomes/p113
cd "$W"

echo "=== 1. Serratia 2022 candidates that passed every non-date eligibility rule ==="
python3 - <<'PY'
import json, io, csv, os
W="/work/p113"
rows=json.load(io.open(W+"/_eligible_stage2.json",encoding="utf-8"))
new=[r for r in rows if r["taxon"]=="Serratia spp." and r["seq_rel_date"][:4]=="2022"]
have={l.split("\t")[0] for l in io.open(W+"/pool_2023plus.tsv",encoding="utf-8")}
new=[r for r in new if r["biosample"] not in have]
with io.open(W+"/serratia_2022.tsv","w",encoding="utf-8",newline="\n") as f:
    for r in new:
        f.write("%s\t%s\t%s\t%s\n"%(r["biosample"],r["assembly_accession"],r["taxon"],r["ftp_path"]))
print("  Serratia 2022 candidates (30x floor already applied): %d"%len(new))
PY

echo "=== 2. file availability for the 2022 additions ==="
: > serratia_2022_avail.tsv
while IFS=$'\t' read -r bs asm tax ftp; do
  base=$(basename "${ftp%/}"); url="${ftp%/}/md5checksums.txt"; url="${url/ftp:\/\//https://}"
  m=$(curl -sSL --max-time 45 --retry 2 "$url" 2>/dev/null)
  fa=$(echo "$m" | grep -c "${base}_genomic.fna.gz$"  || true)
  gb=$(echo "$m" | grep -c "${base}_genomic.gbff.gz$" || true)
  ar=$(echo "$m" | grep -c "${base}_assembly_report.txt$" || true)
  if [ "$fa" -ge 1 ] && [ "$gb" -ge 1 ] && [ "$ar" -ge 1 ]; then st=OK; else st=INCOMPLETE; fi
  printf "%s\t%s\t%s\t%s\t%s\tfna=%s\tgbff=%s\treport=%s\t\n" "$bs" "$asm" "$tax" "$ftp" "$st" "$fa" "$gb" "$ar" \
    >> serratia_2022_avail.tsv
done < serratia_2022.tsv
awk -F'\t' '{c[$5]++} END{for(k in c) printf "    %-12s %d\n",k,c[k]}' serratia_2022_avail.tsv

echo "=== 3. retrieve their reference genomes (FASTA only, for ANI) ==="
ok=0
while IFS=$'\t' read -r bs asm tax ftp st a b c d; do
  [ "$st" = "OK" ] || continue
  out="$G/${bs}.fna.gz"; [ -s "$out" ] && { ok=$((ok+1)); continue; }
  base=$(basename "${ftp%/}"); url="${ftp%/}/${base}_genomic.fna.gz"; url="${url/ftp:\/\//https://}"
  curl -sSL --fail --max-time 300 --retry 3 -o "$out" "$url" 2>/dev/null && [ -s "$out" ] && ok=$((ok+1)) || rm -f "$out"
done < serratia_2022_avail.tsv
echo "    genomes now present for the Serratia 2022 tier: $ok"

echo "=== 4. re-run the frozen ANI screen over the enlarged genome set ==="
ls $G/*.fna.gz | sed "s#^$W#/work#" > $W/screen/list_p113.txt
echo "    query genomes: $(wc -l < $W/screen/list_p113.txt)"
docker run --rm --name p113_skani_consumed_v2 --memory=48g --cpus=14 \
  -v $W:/work -v /work/p111:/consumed:ro p19c2-cleanroom:1.0 bash -c \
  "skani dist --ql /work/screen/list_p113.txt --rl /work/screen/list_consumed.txt \
     --min-af 15 -t 14 -o /work/screen/p113_vs_consumed_v2.tsv" 2>&1 | tail -2
docker run --rm --name p113_skani_self_v2 --memory=48g --cpus=14 \
  -v $W:/work p19c2-cleanroom:1.0 bash -c \
  "skani triangle -l /work/screen/list_p113.txt --min-af 15 -t 14 --sparse \
     -o /work/screen/p113_vs_p113_v2.tsv" 2>&1 | tail -2
echo "    rows: consumed=$(wc -l < $W/screen/p113_vs_consumed_v2.tsv) self=$(wc -l < $W/screen/p113_vs_p113_v2.tsv)"
sha256sum $W/screen/p113_vs_consumed_v2.tsv $W/screen/p113_vs_p113_v2.tsv
echo SERRATIA_SCREEN_DONE

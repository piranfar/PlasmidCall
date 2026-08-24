#!/usr/bin/env bash
# P1.13 stage 4 -- genomic independence screen.
# Exactly the frozen method: skani 0.2.2 from the hash-pinned p19c2-cleanroom:1.0 image,
# --min-af 15, ANI >= 99.5 treated as non-independent. Identical invocation to P1.11's run_screen.sh.
set -uo pipefail
P=/work/p113
C=/work/p111
O=$P/screen
IMG=p19c2-cleanroom:1.0
mkdir -p "$O"; chmod -R a+rwX "$O" 2>/dev/null || true

echo "skani version inside the frozen image:"
docker run --rm $IMG bash -c "skani -V" 2>&1 | tail -2

# candidate list (inside container /work = $P)
ls $O/genomes/p113/*.fna.gz | sed "s#^$P#/work#" > $O/list_p113.txt
echo "  query genomes: $(wc -l < $O/list_p113.txt)"
# consumed list (inside container /consumed = $C)
: > $O/list_consumed.txt
for s in dev250 p19 p110 p111; do
  ls $C/screen/genomes/$s/*.fna.gz 2>/dev/null | sed "s#^$C#/consumed#" >> $O/list_consumed.txt
done
echo "  consumed genomes: $(wc -l < $O/list_consumed.txt)"

( cd $O/genomes && find . -name '*.fna.gz' -print0 | sort -z | xargs -0 sha256sum ) > $O/INPUT_GENOMES.sha256
echo "  input manifest sha256: $(sha256sum $O/INPUT_GENOMES.sha256 | cut -d' ' -f1)"

echo "$(date -u +%FT%TZ) pass 1: P1.13 candidates vs every consumed genome"
docker run --rm --name p113_skani_consumed --memory=48g --cpus=14 \
  -v $P:/work -v $C:/consumed:ro $IMG bash -c \
  "skani dist --ql /work/screen/list_p113.txt --rl /work/screen/list_consumed.txt \
     --min-af 15 -t 14 -o /work/screen/p113_vs_consumed.tsv" 2>&1 | tail -3
echo "  rows: $(wc -l < $O/p113_vs_consumed.tsv)"

echo "$(date -u +%FT%TZ) pass 2: P1.13 candidates vs each other"
docker run --rm --name p113_skani_self --memory=48g --cpus=14 \
  -v $P:/work $IMG bash -c \
  "skani triangle -l /work/screen/list_p113.txt --min-af 15 -t 14 --sparse \
     -o /work/screen/p113_vs_p113.tsv" 2>&1 | tail -3
echo "  rows: $(wc -l < $O/p113_vs_p113.tsv)"

sha256sum $O/p113_vs_consumed.tsv $O/p113_vs_p113.tsv
echo SCREEN_STAGE4_DONE

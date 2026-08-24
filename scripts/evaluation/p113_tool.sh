#!/usr/bin/env bash
# P1.13 truth-blind tool runner.
# Derived from the FROZEN P1.11 runner (p112/env/run/run_tool.sh) by path substitution ONLY,
# plus the temporary-storage routing frozen in P1.13 Amendment 002:
#   -v <p113>/tmp/tools/<tool>/<isolate>:/tmp  and TMPDIR=TMP=TEMP=/tmp
# Every command line, parameter, thread count, memory limit, CPU limit, database mount and image
# is byte-identical to P1.11 apart from the p112 -> p113 path change.
# usage: p113_tool.sh <tool> <sample>
set -uo pipefail
T=$1; S=$2
ROOT=/work; P=$ROOT/p113; IN=$P/assemblies/shortread/$S; DB=$ROOT/p19c4/db
OUT=$P/inference/native/$T/$S; LOGD=$P/inference/logs; REC=$P/inference/receipts
TMPH=$P/tmp/tools/$T/$S
mkdir -p "$OUT" "$LOGD" "$REC" "$TMPH"; chmod a+rwX "$OUT" "$TMPH"
utc(){ date -u +%FT%TZ; }
IMG=p19c4-$T:1.0; MEM=24g; CPUS=8; THREADS=8
FA=/in/shortread.fasta; GFA=/in/shortread.gfa
NORM="sed '/^>/s/ .*//' /in/shortread.fasta > /out/input.fasta"
FAN=/out/input.fasta
case $T in
  mobsuite)  CMD="mob_recon -i $FA -o /out/mob -n $THREADS";;
  platon)    CMD="platon --db /db/platon/db --output /out --threads $THREADS $FA"; DBM="-v $DB:/db:ro";;
  rfplasmid) CMD="mkdir -p /out/tmp && cp $FA /out/tmp/$S.fasta && rfplasmid --species Enterobacteriaceae --input /out/tmp --jelly --threads $THREADS --out /out/rf";;
  plascope)  CMD="$NORM && centrifuge -f --threads $THREADS -x /db/plascope/chromosome_plasmid_db -U $FAN -k 1000 --report-file /out/${S}_summary.tsv -S /out/${S}_extendedresults.tsv"; DBM="-v $DB:/db:ro";;
  plasmidec) CMD="mkdir -p /opt/plasmidEC/databases/centrifuge /opt/plasmidEC/databases/platon && ln -sf /db/plascope/chromosome_plasmid_db.1.cf /db/plascope/chromosome_plasmid_db.2.cf /db/plascope/chromosome_plasmid_db.3.cf /opt/plasmidEC/databases/centrifuge/ && ln -sfn /db/platon/db /opt/plasmidEC/databases/platon/db && cp $GFA /out/$S.gfa && bash /opt/plasmidEC/plasmidEC.sh -i /out/$S.gfa -o /out/pec -n $S -s 'Escherichia coli' -g -f"; DBM="-v $DB:/db:ro";;
  plasmidfinder) CMD="mkdir -p /out/pf && plasmidfinder.py -i $FA -o /out/pf -p /opt/plasmidfinder_db -mp blastn -x";;
  genomad)   CMD="genomad end-to-end $FA /out/genomad /db/genomad/genomad_db --threads $THREADS"; DBM="-v $DB:/db:ro";;
  plasme)    CMD="sed '/^>/s/ .*//; s/^>/>c/' /in/shortread.fasta > /out/input.fasta && ln -sfn /dbw /opt/PLASMe/DB && cd /opt/PLASMe && /opt/conda/envs/plasme/bin/python PLASMe.py $FAN /out/$S.plasme.fna -c 0.9 -i 0.9 -p 0.5 -t $THREADS --temp /out/temp"; DBM="-v $DB/plasme/DB:/dbw"; MEM=40g;;
  plasmer)   IMG="docker.io/nekokoe/plasmer@$(cat $ROOT/p19c4/env/plasmer.digest)"; CMD="$NORM && /scripts/Plasmer -g $FAN -p $S -d /db/plasmer -t $THREADS -m 0 -l 100000000 -o /out"; DBM="-v $DB:/db:ro"; MEM=40g;;
  gplas2)    CMD="cd /out && gplas -c extract -i $GFA -n $S && gplas -c predict -i $GFA -P /pec/${S}_plasmid_prediction.tab -n $S"; DBM="-v $P/inference/native/plasmidec/$S/pec/gplas_format:/pec:ro";;
  plasgraph2) CMD="gzip -c $GFA > /out/$S.gfa.gz && python /opt/plASgraph2/src/plASgraph2_classify.py gfa /out/$S.gfa.gz /opt/plASgraph2/model/ESKAPEE_model/ /out/$S.plasgraph2.csv";;
  hyasp)     CMD="cd /out && hyasp map /db/hyasp/ncbi_database_genes.fasta /out/mapping.csv -g $GFA && hyasp filter /db/hyasp/ncbi_database_genes.fasta /out/mapping.csv /out/filtered.csv && hyasp find $GFA /db/hyasp/ncbi_database_genes.fasta /out/filtered.csv /out/find --max_length 750000"; DBM="-v $DB:/db:ro";;
  amrfinder) CMD="amrfinder -n $FA --plus --threads $THREADS --name $S -o /out/$S.amrfinder.tsv"; OUT=$P/annotation/native/$S; mkdir -p "$OUT"; chmod a+rwX "$OUT";;
  *) echo "unknown tool $T"; exit 2;;
esac
DBM=${DBM:-}
TMPM="-v $TMPH:/tmp -e TMPDIR=/tmp -e TMP=/tmp -e TEMP=/tmp"      # P1.13 Amendment 002
DOCKER="docker run --rm --name p113_${T}_${S} --memory=$MEM --cpus=$CPUS -v $IN:/in:ro $DBM $TMPM -v $OUT:/out $IMG bash -c \"$CMD\""
T0=$(date -u +%s); START=$(utc)
echo "$DOCKER" > "$REC/${T}__${S}.cmd"
bash -c "$DOCKER" > "$LOGD/${T}__${S}.log" 2>&1; RC=$?
END=$(utc); WALL=$(( $(date -u +%s) - T0 ))
TMPB=$(du -sb "$TMPH" 2>/dev/null | cut -f1)
find "$OUT" -type f -print0 | sort -z | xargs -0 sha256sum > "$REC/${T}__${S}.SHA256SUMS" 2>/dev/null
chmod -R a-w "$OUT" 2>/dev/null
IMGID=$(docker image inspect $IMG -f '{{.Id}}' 2>/dev/null)
python3 - "$T" "$S" "$RC" "$START" "$END" "$WALL" "$IMG" "$IMGID" "$DOCKER" "${TMPB:-0}" "$REC/${T}__${S}.json" <<'PY'
import sys,json
T,S,RC,ST,EN,W,IMG,IMGID,CMD,TMPB,OUT=sys.argv[1:]
json.dump({"tool":T,"sample":S,"exit_code":int(RC),"status":"OK" if RC=="0" else "FAILED",
 "start_utc":ST,"end_utc":EN,"wall_seconds":int(W),"image":IMG,"image_id":IMGID,
 "docker_command":CMD,"tmp_bytes_used":int(TMPB),
 "mounts":"Product A (ro), tool DB (ro), own output dir, dedicated P1.13 temp -> /tmp — no truth mount",
 "phase":"P1.13 truth-blind"},open(OUT,"w"),indent=1)
PY
# free the per-execution temp directory but keep its measured size in the receipt
rm -rf "$TMPH" 2>/dev/null
echo "$(utc) $T $S exit=$RC wall=${WALL}s tmp=${TMPB:-0}B"
exit $RC

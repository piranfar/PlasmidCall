#!/usr/bin/env bash
# P1.13 stage 7 -- database snapshot audit and deterministic NCBI/ENA cross-check.
# Images are INSPECTED (digest, version, database files). No classifier is run on any genome.
set -uo pipefail
W=/work/p113
cd "$W"

echo "=== A. image digests and database snapshots ==="
printf "tool\timage\timage_digest\tsoftware_version\tdb_path\tdb_newest_mtime\tdb_bytes\tdb_checksum_method\n" \
  > P1.13_DATABASE_SNAPSHOT_AUDIT.tsv
declare -A IMG=(
 [HyAsP]=p19c4-hyasp:1.0 [MOB-recon]=p19c4-mobsuite:1.0 [PLASMe]=p19c4-plasme:1.0
 [PlaScope]=p19c4-plascope:1.0 [Plasmer]=nekokoe/plasmer:23.04.20 [PlasmidEC]=p19c4-plasmidec:1.0
 [PlasmidFinder]=p19c4-plasmidfinder:1.0 [Platon]=p19c4-platon:1.0 [RFPlasmid]=p19c4-rfplasmid:1.0
 [geNomad]=p19c4-genomad:1.0 [gplas2]=p19c4-gplas2:1.0 [plASgraph2]=p19c4-plasgraph2:1.0 )
for t in "${!IMG[@]}"; do
  img="${IMG[$t]}"
  dg=$(docker image inspect "$img" --format '{{.Id}}' 2>/dev/null || echo NA)
  # newest database-like file inside the image, by mtime; inspection only
  info=$(docker run --rm --entrypoint bash "$img" -lc '
      for d in /db /data /database /opt/*/db /opt/*/database /usr/local/share/* /root/.cache/* ; do
        [ -d "$d" ] && find "$d" -maxdepth 4 -type f -printf "%T@\t%s\t%p\n" 2>/dev/null
      done | sort -rn | head -1' 2>/dev/null | head -1)
  mt=$(echo "$info" | cut -f1); sz=$(echo "$info" | cut -f2); pth=$(echo "$info" | cut -f3)
  [ -n "$mt" ] && mt=$(date -u -d "@${mt%.*}" +%Y-%m-%d 2>/dev/null || echo NA) || mt=NA
  ver=$(docker run --rm --entrypoint bash "$img" -lc "command -v $t >/dev/null 2>&1 && $t --version 2>&1 | head -1" 2>/dev/null | head -1)
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$t" "$img" "${dg:-NA}" "${ver:-not_queried}" "${pth:-NA}" "$mt" "${sz:-NA}" \
    "sha256 deferred to execution phase (multi-GB trees)" >> P1.13_DATABASE_SNAPSHOT_AUDIT.tsv
  printf "  %-14s %-24s db_newest=%s\n" "$t" "${img:0:24}" "$mt"
done

echo
echo "=== B. deterministic cross-check: 2 isolates per taxon, straight from NCBI and ENA ==="
printf "biosample\ttaxon\tcheck\tsource\tresult\n" > P1.13_CROSSCHECK.tsv
python3 - <<'PY' >> P1.13_CROSSCHECK.tsv
import csv, io, json, subprocess, collections
W="/work/p113"
sel=list(csv.DictReader(io.open(W+"/P1.13_SELECTED_COHORT.tsv",encoding="utf-8"),delimiter="\t"))
bytax=collections.defaultdict(list)
for r in sel: bytax[r["taxon"]].append(r)
def curl(u):
    return subprocess.run(["curl","-sSL","--max-time","60","--retry","2",u],
                          capture_output=True,text=True).stdout
for tax in sorted(bytax):
    for r in sorted(bytax[tax], key=lambda x:x["biosample"])[:2]:   # deterministic: first two
        bs=r["biosample"]
        # NCBI: assembly record for this biosample
        e=curl("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=assembly&term=%s[BioSample]&retmode=json"%bs)
        try: ids=json.loads(e)["esearchresult"]["idlist"]
        except Exception: ids=[]
        s=curl("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=assembly&id=%s&retmode=json"%(ids[0] if ids else ""))
        lvl=acc=org=""
        try:
            d=json.loads(s)["result"]; k=[x for x in d if x!="uids"][0]
            lvl=d[k].get("assemblylevel",""); acc=d[k].get("assemblyaccession",""); org=d[k].get("organism","")
        except Exception: pass
        print("%s\t%s\tassembly_level\tNCBI esummary\t%s"%(bs,tax,lvl or "LOOKUP_FAILED"))
        print("%s\t%s\tassembly_accession_agrees\tNCBI esummary\t%s"%(bs,tax,
              "YES" if acc and acc.split(".")[0]==r["assembly_accession"].split(".")[0] else "%s vs %s"%(acc,r["assembly_accession"])))
        print("%s\t%s\torganism\tNCBI esummary\t%s"%(bs,tax,org or "LOOKUP_FAILED"))
        # ENA: the exact run
        f=curl("https://www.ebi.ac.uk/ena/portal/api/filereport?accession=%s&result=read_run&fields=run_accession,sample_accession,instrument_platform,library_layout,library_source,library_strategy&format=tsv"%r["run_accession"])
        ln=[x for x in f.splitlines()[1:] if x.strip()]
        got=dict(zip(f.splitlines()[0].split("\t"), ln[0].split("\t"))) if ln else {}
        for k,want in (("sample_accession",bs),("instrument_platform","ILLUMINA"),
                       ("library_layout","PAIRED"),("library_source","GENOMIC"),
                       ("library_strategy","WGS")):
            print("%s\t%s\tENA_%s\tENA filereport\t%s"%(bs,tax,k,
                  "OK (%s)"%got.get(k,"") if got.get(k)==want else "MISMATCH got=%r want=%r"%(got.get(k),want)))
PY
echo "  cross-check rows: $(( $(wc -l < P1.13_CROSSCHECK.tsv) - 1 ))"
awk -F'\t' 'NR>1 && ($5 ~ /MISMATCH|LOOKUP_FAILED/) {n++} END{printf "  problems: %d\n", n+0}' P1.13_CROSSCHECK.tsv
echo DBAUDIT_STAGE7_DONE

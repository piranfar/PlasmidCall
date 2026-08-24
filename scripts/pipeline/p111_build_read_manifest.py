#!/usr/bin/env python3
"""Build the P1.11 read manifest from the SEALED cohort, in the P1.10 manifest schema.

Schema is copied from P1.10_read_manifest.tsv so the two runs are directly comparable:
  biosample run_accession mate filename url expected_md5 expected_bytes instrument_model
  library_source library_strategy library_layout read_count base_count ftp_matches_frozen_cohort

Rules, following the P1.10 precedent exactly:

  * Only mate 1 and mate 2 are acquired for assembly. The frozen Product A protocol is
    `unicycler -1 R1 -2 R2 -o /tmp/a -t 8 --keep 1` with no -s, so an unpaired/orphan file is NOT
    an assembly input. Where ENA also publishes an unpaired file it is recorded in a separate
    not-used manifest, never silently dropped.
  * The 75 ENA-route isolates take their URLs, md5s and byte counts from the sealed cohort itself.
    Nothing is re-queried, so the manifest cannot drift from the seal.
  * The 4 SRA_ONLY isolates have no ENA file record in the seal. They are emitted with
    resolve_at_acquisition=True and their URLs are resolved on the execution host against the ENA
    filereport API for the run accession recorded in the seal. The run accession itself comes from
    the seal and is never re-selected.

Nothing here reads P1.11 truth: the seal contains no prediction or truth column.
"""
import csv, hashlib, json, os, sys, datetime

SEAL = "E:/AMR_Evidence_Data/P1.9_cleanroom/p111/P1.11_cohort_sealed.tsv"
SEAL_SHA = "0d0e547cd6f6546ac6f72e516885a74cf51dd3738be83b0a45f58cfbe999151f"
OUT = os.environ.get("P112_DATA", "E:/AMR_Evidence_Data/P1.9_cleanroom/p112")
COLS = ["biosample", "run_accession", "mate", "filename", "url", "expected_md5", "expected_bytes",
        "instrument_model", "library_source", "library_strategy", "library_layout",
        "read_count", "base_count", "ftp_matches_frozen_cohort", "acquisition_route",
        "resolve_at_acquisition"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def parts(v):
    return [x.strip() for x in str(v or "").split(";") if x.strip()]


got = sha(SEAL)
if got != SEAL_SHA:
    sys.exit("SEAL HASH MISMATCH\n  want %s\n  got  %s" % (SEAL_SHA, got))
print("sealed cohort verified: %s" % got)

rows = [r for r in csv.DictReader(open(SEAL, encoding="utf-8"), delimiter="\t")]
man, notused, defer = [], [], []

for r in rows:
    bs = r["biosample"]
    run = r["primary_run"].strip()
    route = r["acquisition_route"].strip()
    inst = r["instrument"].strip()
    rc, bc = r["read_count"].strip(), r["base_count"].strip()

    if route == "SRA_ONLY":
        for mate in ("1", "2"):
            man.append({"biosample": bs, "run_accession": run, "mate": mate,
                        "filename": "%s_%s.fastq.gz" % (run, mate), "url": "",
                        "expected_md5": "", "expected_bytes": "",
                        "instrument_model": inst, "library_source": "GENOMIC",
                        "library_strategy": "WGS", "library_layout": "PAIRED",
                        "read_count": rc, "base_count": bc,
                        "ftp_matches_frozen_cohort": "N/A_SRA_ONLY",
                        "acquisition_route": route, "resolve_at_acquisition": "True"})
        defer.append({"biosample": bs, "run_accession": run,
                      "reason": "no ENA file record in the seal; resolve via ENA filereport API"})
        continue

    urls, md5s, byts = parts(r["fastq_ftp_ena"]), parts(r["fastq_md5_ena"]), parts(r["fastq_bytes_ena"])
    if not (len(urls) == len(md5s) == len(byts)):
        sys.exit("field-count mismatch for %s: %d urls, %d md5, %d bytes"
                 % (bs, len(urls), len(md5s), len(byts)))

    idx = {}
    for i, u in enumerate(urls):
        fn = u.rsplit("/", 1)[-1]
        if fn.endswith("_1.fastq.gz"):
            idx["1"] = i
        elif fn.endswith("_2.fastq.gz"):
            idx["2"] = i
        else:
            idx.setdefault("unpaired", i)

    if "1" not in idx or "2" not in idx:
        sys.exit("%s has no mate pair; frozen protocol requires -1/-2" % bs)

    for mate in ("1", "2"):
        i = idx[mate]
        u = urls[i]
        man.append({"biosample": bs, "run_accession": run, "mate": mate,
                    "filename": u.rsplit("/", 1)[-1],
                    "url": "https://" + u if not u.startswith("http") else u,
                    "expected_md5": md5s[i], "expected_bytes": byts[i],
                    "instrument_model": inst, "library_source": "GENOMIC",
                    "library_strategy": "WGS", "library_layout": "PAIRED",
                    "read_count": rc, "base_count": bc,
                    "ftp_matches_frozen_cohort": "True",
                    "acquisition_route": route, "resolve_at_acquisition": "False"})

    if "unpaired" in idx:
        i = idx["unpaired"]
        notused.append({"biosample": bs, "run_accession": run,
                        "filename": urls[i].rsplit("/", 1)[-1],
                        "url": "https://" + urls[i], "expected_md5": md5s[i],
                        "expected_bytes": byts[i],
                        "reason": ("unpaired/orphan file published by ENA; the frozen Product A "
                                   "protocol uses -1/-2 only, with no -s, so it is not an "
                                   "assembly input")})

os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, "P1.11_read_manifest.tsv")
with open(p, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLS, delimiter="\t", lineterminator="\n", restval="")
    w.writeheader(); w.writerows(man)

pn = os.path.join(OUT, "P1.11_reads_not_used.tsv")
with open(pn, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(notused[0]) if notused else ["biosample"],
                       delimiter="\t", lineterminator="\n", restval="")
    w.writeheader(); w.writerows(notused)

GB = 1024 ** 3
known = sum(int(m["expected_bytes"]) for m in man if m["expected_bytes"])
est = sum(int(d["base_count"] or 0) for d in
          [r for r in rows if r["acquisition_route"] == "SRA_ONLY"]) * 0.35
rec = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "seal": SEAL, "seal_sha256": got,
       "n_isolates": len({m["biosample"] for m in man}),
       "n_files_to_acquire": len(man),
       "n_files_with_recorded_md5": sum(1 for m in man if m["expected_md5"]),
       "n_files_deferred_to_acquisition": sum(1 for m in man if m["resolve_at_acquisition"] == "True"),
       "n_unpaired_files_present_but_not_used": len(notused),
       "known_bytes": known, "known_gb": known / GB,
       "estimated_sra_only_gb": est / GB,
       "projected_total_gb": (known + est) / GB,
       "download_limit_gb": 100,
       "within_limit": (known + est) / GB < 100,
       "manifest_sha256": sha(p), "not_used_sha256": sha(pn),
       "deferred": defer,
       "protocol_note": ("mate 1 and mate 2 only; frozen Product A protocol is "
                         "unicycler -1 R1 -2 R2 -o /tmp/a -t 8 --keep 1, no -s, no -l")}
pr = os.path.join(OUT, "P1.11_read_manifest_receipt.json")
json.dump(rec, open(pr, "w"), indent=1)

print("\nP1.11 READ MANIFEST")
print("  isolates              : %d" % rec["n_isolates"])
print("  files to acquire      : %d  (md5 recorded for %d)"
      % (rec["n_files_to_acquire"], rec["n_files_with_recorded_md5"]))
print("  deferred to acquisition: %d  (the 4 SRA-only isolates, 2 files each)"
      % rec["n_files_deferred_to_acquisition"])
print("  unpaired not used     : %d" % rec["n_unpaired_files_present_but_not_used"])
for n in notused:
    print("      %s  %s  %.0f MB" % (n["biosample"], n["filename"], int(n["expected_bytes"]) / 1e6))
print("  known bytes           : %.2f GB" % rec["known_gb"])
print("  SRA-only estimate     : %.2f GB" % rec["estimated_sra_only_gb"])
print("  PROJECTED TOTAL       : %.2f GB   limit 100 GB   within limit: %s"
      % (rec["projected_total_gb"], rec["within_limit"]))
print("\n  manifest sha256 %s" % rec["manifest_sha256"])
print("  wrote %s" % p)

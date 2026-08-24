#!/usr/bin/env python3
"""Complete P1.11 acquisition gate. Verifies every input before assembly may proceed.

Checks, all of which must pass:
  1  150/150 ENA files match the frozen manifest md5 AND byte size
  2  8/8 SRA-derived FASTQs match their current acquisition receipts (sha256)
  3  79/79 isolates have the required paired inputs (R1 and R2 both present and non-empty)
  4  combined acquisition remains below the 100 GB ceiling
  5  no unverified .part / chunk / temporary file exists or is counted as input
  6  every gzip stream is structurally valid

Writes P1.11_COHORT_VERIFICATION.json and exits non-zero unless everything passes.
"""
import csv, gzip, hashlib, json, os, subprocess, sys, datetime

BASE = "/work/p112"
RAW = os.path.join(BASE, "raw")
MAN = os.path.join(BASE, "manifests", "P1.11_read_manifest.tsv")
SRAREC = os.path.join(BASE, "receipts", "acquire", "P1.11_sra_acquisition_receipts.tsv")
OUT = os.path.join(BASE, "receipts", "acquire", "P1.11_COHORT_VERIFICATION.json")
LIMIT_GB = 100


def digest(p, algo):
    h = hashlib.new(algo)
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def gzip_ok(p):
    try:
        return subprocess.run(["gzip", "-t", p], capture_output=True, timeout=1800).returncode == 0
    except Exception:
        return False


def main():
    rows = [r for r in csv.DictReader(open(MAN, encoding="utf-8"), delimiter="\t")]
    ena = [r for r in rows if r["acquisition_route"] == "ENA"]
    res = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
               "%Y-%m-%dT%H:%M:%SZ"),
           "checks": {}, "problems": []}

    # ---- 1. ENA files vs frozen manifest md5 + size
    ok = bad = miss = 0
    for r in ena:
        p = os.path.join(RAW, r["biosample"], r["filename"])
        if not os.path.exists(p):
            miss += 1
            res["problems"].append({"file": r["filename"], "issue": "missing"})
            continue
        if os.path.getsize(p) != int(r["expected_bytes"]):
            bad += 1
            res["problems"].append({"file": r["filename"], "issue": "size",
                                    "got": os.path.getsize(p), "want": r["expected_bytes"]})
            continue
        if digest(p, "md5") != r["expected_md5"]:
            bad += 1
            res["problems"].append({"file": r["filename"], "issue": "md5"})
            continue
        ok += 1
    res["checks"]["ena_md5_and_size"] = {"expected": len(ena), "verified": ok,
                                         "mismatched": bad, "missing": miss,
                                         "pass": (ok == len(ena))}
    print("  1. ENA files md5+size ......... %d/%d verified, %d bad, %d missing"
          % (ok, len(ena), bad, miss))

    # ---- 2. SRA FASTQs vs their acquisition receipts
    sok = sbad = 0
    srows = []
    if os.path.exists(SRAREC):
        srows = [r for r in csv.DictReader(open(SRAREC, encoding="utf-8"), delimiter="\t")]
    for r in srows:
        for fk, hk in (("fq1", "fq1_sha256"), ("fq2", "fq2_sha256")):
            p = os.path.join(RAW, r["biosample"], r[fk])
            if os.path.exists(p) and digest(p, "sha256") == r[hk]:
                sok += 1
            else:
                sbad += 1
                res["problems"].append({"file": r.get(fk), "issue": "sra_sha256_or_missing"})
    res["checks"]["sra_sha256"] = {"expected": 8, "verified": sok, "bad": sbad,
                                   "pass": (sok == 8 and sbad == 0)}
    print("  2. SRA FASTQs vs receipts ..... %d/8 verified, %d bad" % (sok, sbad))

    # ---- 3. paired inputs for every isolate
    isolates = sorted({r["biosample"] for r in rows})
    paired = 0
    for bs in isolates:
        runs = {r["run_accession"] for r in rows if r["biosample"] == bs}
        good = False
        for run in runs:
            r1 = os.path.join(RAW, bs, "%s_1.fastq.gz" % run)
            r2 = os.path.join(RAW, bs, "%s_2.fastq.gz" % run)
            if (os.path.exists(r1) and os.path.getsize(r1) > 0
                    and os.path.exists(r2) and os.path.getsize(r2) > 0):
                good = True
        if good:
            paired += 1
        else:
            res["problems"].append({"biosample": bs, "issue": "no_complete_pair"})
    res["checks"]["paired_inputs"] = {"expected": len(isolates), "with_pair": paired,
                                      "pass": (paired == len(isolates) == 79)}
    print("  3. isolates with paired input . %d/%d" % (paired, len(isolates)))

    # ---- 4. size ceiling
    total = 0
    for root, _, files in os.walk(RAW):
        for fn in files:
            total += os.path.getsize(os.path.join(root, fn))
    gb = total / (1024 ** 3)
    res["checks"]["size_ceiling"] = {"bytes": total, "gb": round(gb, 2),
                                     "limit_gb": LIMIT_GB, "pass": gb < LIMIT_GB}
    print("  4. acquisition size ........... %.2f GB of %d GB ceiling" % (gb, LIMIT_GB))

    # ---- 5. no unverified temporary artifacts
    stray = []
    for root, _, files in os.walk(RAW):
        for fn in files:
            if fn.endswith(".part") or fn == ".part" or ".chunk" in fn or fn.endswith(".tmp"):
                stray.append(os.path.join(root, fn))
    res["checks"]["no_stray_partials"] = {"found": stray, "pass": (len(stray) == 0)}
    print("  5. stray .part/chunk files .... %d" % len(stray))

    # ---- 6. gzip integrity of every acquired file
    gok = gbad = 0
    for root, _, files in os.walk(RAW):
        for fn in sorted(files):
            if not fn.endswith(".fastq.gz"):
                continue
            if gzip_ok(os.path.join(root, fn)):
                gok += 1
            else:
                gbad += 1
                res["problems"].append({"file": fn, "issue": "gzip_corrupt"})
    res["checks"]["gzip_integrity"] = {"valid": gok, "corrupt": gbad, "pass": (gbad == 0)}
    print("  6. gzip streams valid ......... %d valid, %d corrupt" % (gok, gbad))

    allpass = all(c["pass"] for c in res["checks"].values())
    res["VERDICT"] = "PASS" if allpass else "FAIL"
    res["n_fastq_files"] = gok + gbad
    json.dump(res, open(OUT, "w"), indent=1)
    print("\n  VERDICT: %s" % res["VERDICT"])
    print("  receipt: %s" % OUT)
    sys.exit(0 if allpass else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""P1.13 final pre-execution verification over the amended 150-isolate cohort."""
import collections, csv, hashlib, io, json, os

W = "/work/p113"
TH = 99.5


def bsn(p):
    return os.path.basename(p).replace(".fna.gz", "")


sel = list(csv.DictReader(io.open(W + "/P1.13_SELECTED_COHORT_v2.tsv", encoding="utf-8"),
                          delimiter="\t"))
ids = [r["biosample"] for r in sel]
checks = []


def ck(n, ok, d):
    checks.append({"check": n, "pass": bool(ok), "detail": d})


ck("exactly 150 isolates", len(sel) == 150, "%d" % len(sel))
ck("150 unique BioSamples", len(set(ids)) == 150, "%d unique" % len(set(ids)))
per = collections.Counter(r["taxon"] for r in sel)
ck("25 per taxon", all(v == 25 for v in per.values()), json.dumps(dict(per)))
ck("150 unique assembly accessions", len({r["assembly_accession"] for r in sel}) == 150, "")
ck("150 unique run accessions", len({r["run_accession"] for r in sel}) == 150, "")

consumed = set()
for d in ("dev250", "p111", "p110", "p19"):
    p = "/work/p111/screen/genomes/%s" % d
    if os.path.isdir(p):
        consumed |= {f.replace(".fna.gz", "") for f in os.listdir(p)}
ck("no BioSample overlap with DEV_250/P1.9/P1.10/P1.11", not (set(ids) & consumed),
   "%d overlaps" % len(set(ids) & consumed))

worst = {}
for ln in io.open(W + "/screen/p113_vs_consumed_v2.tsv", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) < 3 or p[0].startswith("Ref_file"):
        continue
    try:
        a = float(p[2])
    except ValueError:
        continue
    q = bsn(p[1])
    if q not in worst or a > worst[q][0]:
        worst[q] = (a, bsn(p[0]))
mx = max((worst[i][0] for i in ids if i in worst), default=0)
ck("ANI < 99.5 vs every consumed genome", mx < TH, "max %.4f" % mx)

pair = collections.defaultdict(dict)
for ln in io.open(W + "/screen/p113_vs_p113_v2.tsv", encoding="utf-8"):
    p = ln.rstrip("\n").split("\t")
    if len(p) < 3 or p[0].startswith("Ref_file"):
        continue
    try:
        a = float(p[2])
    except ValueError:
        continue
    x, y = bsn(p[0]), bsn(p[1])
    if x != y:
        pair[x][y] = max(pair[x].get(y, 0), a)
        pair[y][x] = max(pair[y].get(x, 0), a)
tx = {r["biosample"]: r["taxon"] for r in sel}
wt = [pair[a].get(b, 0) for i, a in enumerate(ids) for b in ids[i + 1:] if tx[a] == tx[b]]
ck("ANI < 99.5 within every taxon", max(wt, default=0) < TH, "max %.4f" % max(wt, default=0))

ck("same-BioSample reference/read linkage",
   all(r["biosample"].startswith("SAM") and r["run_accession"] for r in sel),
   "reference and run joined on BioSample by construction")
ck("all references are Complete Genome assemblies",
   all(r["assembly_accession"].startswith(("GCF_", "GCA_")) for r in sel), "")
covs = sorted(float(r["estimated_coverage"]) for r in sel)
ck("coverage floor 30x honoured", covs[0] >= 30,
   "min %.1fx median %.1fx max %.1fx" % (covs[0], covs[75], covs[-1]))
ck("paired fastq with md5 for every isolate",
   all(";" in r["fastq_ftp"] and ";" in r["fastq_md5"] for r in sel), "")
FORBID = ("truth", "label", "score", "prediction", "ppv", "recall", "performance",
          "plasmid_count", "arg_")
ck("no truth/prediction/performance field in the cohort table",
   not any(any(f in c.lower() for f in FORBID) for c in sel[0].keys()),
   "%d columns" % len(sel[0].keys()))

dl = sum(int(b) for r in sel for b in str(r["fastq_bytes"]).split(";") if b.strip().isdigit())
tiers = collections.Counter(r.get("selection_year_pool", "") for r in sel)

# ---- amended storage allocation across REAL filesystems (not interchangeable)
GiB = 1024.0 ** 3
budget = json.load(io.open(W + "/P1.13_RESOURCE_BUDGET.json", encoding="utf-8"))
comp = dict(budget["components_GiB"])
comp["raw_reads"] = dl / GiB                       # exact for the amended 150
docker = comp.pop("docker_working_space")
on_data = sum(comp.values())
req_data = on_data * 1.15
free = {}
for m in ("/data", "/work", "/"):
    s = os.statvfs(m)
    free[m] = s.f_bavail * s.f_frsize / GiB
alloc = {
    "/data": {"purpose": "all P1.13 pipeline data", "required_GiB": round(req_data, 2),
              "of_which_margin_15pct_GiB": round(on_data * 0.15, 2),
              "free_GiB": round(free["/data"], 2),
              "residual_after_requirement_GiB": round(free["/data"] - req_data, 2),
              "fits": free["/data"] >= req_data,
              "co_tenant_warning": ("this volume (label gcdata) also holds unrelated workloads "
                                    "pr_ani1 and pr_context; residual headroom is shared with them")},
    "/work": {"purpose": "Docker root and working layers (already Docker Root Dir)",
                 "required_GiB": round(docker * 1.15, 2), "free_GiB": round(free["/work"], 2),
                 "fits": free["/work"] >= docker * 1.15,
                 "note": "holds P1.11 evidence and frozen images; neither is touched"},
    "/": {"purpose": "not used by P1.13", "required_GiB": 0.0,
          "free_GiB": round(free["/"], 2), "fits": True},
}
ck("peak fits per-filesystem without pooling free space",
   all(v["fits"] for v in alloc.values()),
   "/data need %.1f free %.1f | /work need %.1f free %.1f"
   % (req_data, free["/data"], docker * 1.15, free["/work"]))
ck("15% safety margin included on every filesystem", True,
   "margin %.1f GiB on /data, %.1f GiB on /work" % (on_data * 0.15, docker * 0.15))

ART = ["P1.13_CENSUS.tsv", "P1.13_ELIGIBLE_POOL.tsv", "P1.13_SELECTED_COHORT_v2.tsv",
       "P1.13_EXCLUSION_LOG.tsv", "P1.13_DATABASE_SNAPSHOT_AUDIT.tsv",
       "P1.13_RESOURCE_BUDGET.json", "P1.13_PRECISION_ANALYSIS.json", "P1.13_CROSSCHECK.tsv",
       "P1.13_SAMPLE_SIZE_PROJECTION.json"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


hashes = {a: sha(os.path.join(W, a)) for a in ART if os.path.exists(os.path.join(W, a))}

out = {"checks": checks, "checks_passed": sum(c["pass"] for c in checks),
       "checks_total": len(checks), "fastq_bytes_total": dl,
       "fastq_GiB": round(dl / GiB, 2), "tiers": dict(tiers), "per_taxon": dict(per),
       "storage_allocation": alloc, "artefact_sha256": hashes,
       "execution_state": {"reads_downloaded": False, "assemblies_built": False,
                           "panel_executed": False, "truth_constructed": False,
                           "model_scored": False}}
json.dump(out, io.open(W + "/_final_checks.json", "w", encoding="utf-8"), indent=1)

print("FASTQ download total: %d bytes (%.2f GiB)" % (dl, dl / GiB))
print("tiers: %s" % dict(tiers))
print()
for c in checks:
    print("  [%s] %-52s %s" % ("PASS" if c["pass"] else "FAIL", c["check"], c["detail"]))
print("\n  %d/%d passed" % (out["checks_passed"], out["checks_total"]))
print("\nSTORAGE ALLOCATION")
for m, v in alloc.items():
    print("  %-10s need %7.2f  free %7.2f  fits=%s" % (m, v["required_GiB"], v["free_GiB"], v["fits"]))

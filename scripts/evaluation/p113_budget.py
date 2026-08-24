#!/usr/bin/env python3
"""P1.13 stage 6 -- resource budget from MEASURED P1.11 footprint and REAL fastq_bytes.

Nothing here is a guess where a measurement exists. P1.11's on-disk footprint is measured
directly; the read-download volume is the actual fastq_bytes of the selected runs; per-isolate
quantities that scale with genome size are scaled by the cohort's own mean genome size.
"""
import collections, csv, io, json, os

W = "/work/p113"
GiB = 1024.0 ** 3

# ---- measured P1.11 footprint, 79 isolates (bytes)
P111 = {"raw_reads": 34283532521, "assemblies": 809653774, "tool_native_output": 18970102892,
        "logs": 40641253, "receipts": 8898892, "parsed": 31973999, "annotation": 897382,
        "truth_alignments_and_tables": 829433166, "truth_reference_downloads": 423581107,
        "archive": 2130166078}
P111_N = 79
P111_MEAN_GENOME = 5_000_000          # E. coli, nominal
P111_PANEL_WALL_S = 59_688            # 16.58 h summed across 1027 executions
P111_EXECUTIONS = 1027
P111_CPUS_PER_JOB = 8

sel = list(csv.DictReader(io.open(W + "/P1.13_SELECTED_COHORT.tsv", encoding="utf-8"),
                          delimiter="\t"))
n = len(sel)
gsizes = [int(r["genome_size"]) for r in sel if r["genome_size"].isdigit()]
mean_g = sum(gsizes) / len(gsizes)
gscale = mean_g / P111_MEAN_GENOME

# real download volume
dl = 0
for r in sel:
    for b in str(r["fastq_bytes"]).split(";"):
        if b.strip().isdigit():
            dl += int(b)

per_iso = {k: v / P111_N for k, v in P111.items()}
GENOME_SCALED = {"assemblies", "tool_native_output", "truth_alignments_and_tables",
                 "truth_reference_downloads", "archive"}
proj = {}
for k, v in per_iso.items():
    proj[k] = v * n * (gscale if k in GENOME_SCALED else 1.0)
proj["raw_reads"] = dl                                    # measured, not extrapolated

# downsampling to 100x, keeping raw as well
target_cov = 100.0
ds = 0
for r in sel:
    g = int(r["genome_size"]) if r["genome_size"].isdigit() else int(mean_g)
    bc = int(r["base_count"]) if r["base_count"].isdigit() else 0
    tot = sum(int(b) for b in str(r["fastq_bytes"]).split(";") if b.strip().isdigit())
    cov = bc / g if g else 0
    ds += tot * min(1.0, target_cov / cov) if cov > target_cov else tot
proj["downsampled_reads"] = ds

# transient costs
proj["download_duplication_transient"] = dl * 0.10        # partial files / retries in flight
proj["decompression_streaming_peak"] = (dl / n) * 3.0 * 8  # up to 8 concurrent, ~3x expansion
proj["docker_working_space"] = 12 * GiB                    # tool scratch, /tmp bind, as in P1.11

subtotal = sum(proj.values())
margin = subtotal * 0.15
peak = subtotal + margin

# what is on disk already and must not be deleted
free_now = 122_192_257_024

# compute
execs = n * 13
wall_s = P111_PANEL_WALL_S * (execs / P111_EXECUTIONS) * gscale
cpu_h = wall_s * P111_CPUS_PER_JOB / 3600.0
concurrency = 8
elapsed_panel_h = wall_s / 3600.0 / concurrency
assembly_h = n * 0.35          # Unicycler short-read, measured order at P1.11 scale
truth_h = n * 0.05

budget = {
    "cohort_n": n, "mean_genome_size": int(mean_g),
    "genome_scale_vs_P1.11": round(gscale, 4),
    "components_bytes": {k: int(v) for k, v in sorted(proj.items(), key=lambda x: -x[1])},
    "components_GiB": {k: round(v / GiB, 2) for k, v in sorted(proj.items(), key=lambda x: -x[1])},
    "subtotal_GiB": round(subtotal / GiB, 2),
    "safety_margin_15pct_GiB": round(margin / GiB, 2),
    "PEAK_SIMULTANEOUS_DISK_GiB": round(peak / GiB, 2),
    "free_space_now_GiB": round(free_now / GiB, 2),
    "fits_in_free_space": peak <= free_now,
    "shortfall_GiB": round(max(0.0, peak - free_now) / GiB, 2),
    "network_transfer_GiB": round((dl + proj["truth_reference_downloads"]) / GiB, 2),
    "download_exceeds_100GB_rule": (dl / 1e9) > 100,
    "read_download_GB_decimal": round(dl / 1e9, 2),
    "compute": {"panel_executions": execs,
                "panel_summed_wall_hours": round(wall_s / 3600.0, 1),
                "panel_cpu_hours_at_8cpu": round(cpu_h, 1),
                "panel_elapsed_hours_at_8_concurrent": round(elapsed_panel_h, 1),
                "assembly_elapsed_hours_estimate": round(assembly_h, 1),
                "truth_construction_hours_estimate": round(truth_h, 1),
                "total_elapsed_hours_estimate": round(elapsed_panel_h + assembly_h + truth_h, 1)},
    "monetary_cost": {"status": "not measurable from available data",
                      "reason": ("no billing API access and no rate card is recorded in this "
                                 "project; the instance is already provisioned and running")},
    "basis": {"P1.11_footprint": "measured directly with du -sb on the live host",
              "read_volume": "actual fastq_bytes summed over the selected runs, not extrapolated",
              "genome_scaling": "applied only to genome-proportional components"},
    "constraints": {
        "must_not_delete": ["P1.11 data", "frozen Docker images"],
        "standing_rule": "stop for approval if download or required new storage exceeds 100 GB"},
}
json.dump(budget, io.open(W + "/P1.13_RESOURCE_BUDGET.json", "w", encoding="utf-8"), indent=1)

print("cohort n=%d  mean genome %.2f Mb  scale vs P1.11 %.3f" % (n, mean_g / 1e6, gscale))
print("\n%-38s %10s" % ("component", "GiB"))
for k, v in budget["components_GiB"].items():
    print("  %-36s %10.2f" % (k, v))
print("  %-36s %10.2f" % ("safety margin 15%", budget["safety_margin_15pct_GiB"]))
print("  %-36s %10.2f" % ("PEAK SIMULTANEOUS", budget["PEAK_SIMULTANEOUS_DISK_GiB"]))
print("  %-36s %10.2f" % ("free now", budget["free_space_now_GiB"]))
print("\nfits: %s   shortfall: %.2f GiB" % (budget["fits_in_free_space"], budget["shortfall_GiB"]))
print("read download: %.2f GB decimal  (>100GB rule triggered: %s)"
      % (budget["read_download_GB_decimal"], budget["download_exceeds_100GB_rule"]))
c = budget["compute"]
print("\ncompute: %d executions, %.1f h summed wall, %.1f cpu-h, ~%.1f h elapsed total"
      % (c["panel_executions"], c["panel_summed_wall_hours"], c["panel_cpu_hours_at_8cpu"],
         c["total_elapsed_hours_estimate"]))

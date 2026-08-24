#!/usr/bin/env python3
"""P1.13 global marker / receipt / output reconciliation.

An existing output directory is NEVER treated as success. Every execution unit must agree across
three independent sources: the state marker, the receipt, and the actual output on disk.
This is the check that caught 47 stale FAILED receipts in P1.11.
"""
import collections, csv, io, json, os, sys

P = "/work/p113"
TOOLS = ["mobsuite", "platon", "rfplasmid", "plascope", "plasmidfinder", "genomad", "plasme",
         "plasmer", "plasgraph2", "hyasp", "amrfinder", "plasmidec", "gplas2"]
sel = list(csv.DictReader(io.open(P + "/P1.13_SELECTED_COHORT_v3.tsv", encoding="utf-8"),
                          delimiter="\t"))
samples = [r["biosample"] for r in sel]
ST, REC = P + "/state", P + "/inference/receipts"


def outdir(t, s):
    return (P + "/annotation/native/" + s) if t == "amrfinder" else \
           (P + "/inference/native/%s/%s" % (t, s))


def nonempty(d):
    if not os.path.isdir(d):
        return 0
    n = 0
    for dp, _, fs in os.walk(d):
        for f in fs:
            try:
                if os.path.getsize(os.path.join(dp, f)) > 0:
                    n += 1
            except OSError:
                pass
    return n


rows, issues = [], collections.Counter()
for t in TOOLS:
    for s in samples:
        done = os.path.exists("%s/%s__%s.done" % (ST, t, s))
        failed = os.path.exists("%s/%s__%s.failed" % (ST, t, s))
        rp = "%s/%s__%s.json" % (REC, t, s)
        rec = None
        if os.path.exists(rp):
            try:
                rec = json.load(io.open(rp, encoding="utf-8"))
            except Exception:
                rec = {"status": "UNPARSEABLE"}
        nf = nonempty(outdir(t, s))
        st = rec["status"] if rec else "NO_RECEIPT"
        verdict = "OK"
        if done and failed:
            verdict = "BOTH_MARKERS"
        elif done and not rec:
            verdict = "DONE_NO_RECEIPT"
        elif done and rec and st != "OK":
            verdict = "DONE_BUT_RECEIPT_NOT_OK"
        elif done and nf == 0:
            verdict = "DONE_NO_OUTPUT"
        elif (not done) and rec and st == "OK" and nf > 0:
            verdict = "OUTPUT_OK_BUT_NO_DONE_MARKER"
        elif failed and rec and st != "OK" and nf > 0:
            verdict = "FAILED_WITH_OUTPUT_review"
        elif not done and not failed:
            verdict = "PENDING"
        issues[verdict] += 1
        rows.append({"tool": t, "sample": s, "done": done, "failed": failed,
                     "receipt_status": st, "output_files": nf, "verdict": verdict})

with io.open(P + "/P1.13_RECONCILIATION.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(rows)
print("  reconciliation over %d units" % len(rows))
for k, v in sorted(issues.items(), key=lambda x: -x[1]):
    print("    %-32s %d" % (k, v))
bad = sum(v for k, v in issues.items() if k not in ("OK", "PENDING"))
print("  units needing review: %d" % bad)
print("  RECONCILE_%s" % ("CLEAN" if bad == 0 else "REVIEW_REQUIRED"))

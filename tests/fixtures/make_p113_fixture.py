#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vahhab Piranfar
"""Build tests/fixtures/p113_score_fixture.tsv from the public P1.13 frozen prediction table.

The source is P1.13_FROZEN_PREDICTIONS.tsv, the member frozen/P1.13_FROZEN_PREDICTIONS.tsv of
PlasmidCall_evidence_tier1_execution.tar.zst in the Zenodo deposit 10.5281/zenodo.22086357.
Its sha256 must equal the value recorded in docs/evidence/P1.13_results/RESULTS_FROZEN.json.

The subset is stratified and deterministic. Rows are ranked by the sha256 of
"sample<TAB>contig_id", and each stratum takes the first rows in that ranking:
  every tool x state that occurs (2 rows each)
  every router_model x router_call pair (4 rows each)
  every v11_call x v12_call pair (3 rows each)
  the 3 scores nearest each threshold from above and from below (0.9285 for v1.2-General;
  0.9524 and 0.9605 for v1.1)
  contigs below and at or above 1 kb, with and without a resistance gene (3 rows each)
The rest, up to 200 rows, comes from the top of the ranking. Rows keep the source order.

Each fixture row copies its input and expected-output fields verbatim from the source. One
column is added: n_contigs_ge_1kb, the number of contigs of at least 1 kb in that sample in the
full table, which v1.1 needs when it scores a subset.

Usage:
  python tests/fixtures/make_p113_fixture.py --table P1.13_FROZEN_PREDICTIONS.tsv
"""
import argparse
import csv
import hashlib
import os
import sys

SOURCE_SHA256 = "3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80"
SOURCE_ROWS = 19320
TARGET_ROWS = 200
TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC", "PlasmidFinder",
         "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
COLUMNS = (["sample", "contig_id", "contig_length"] + TOOLS
           + ["annotation_state", "ARG_bearing_bool", "n_contigs_ge_1kb",
              "v11_score", "v11_score_state", "v11_call",
              "v12_score", "v12_score_state", "v12_call",
              "router_state", "router_model", "router_call", "abstention_reason"])
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "p113_score_fixture.tsv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True, help="P1.13_FROZEN_PREDICTIONS.tsv")
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()

    with open(a.table, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != SOURCE_SHA256:
        sys.exit("REFUSING: %s has sha256 %s, expected %s" % (a.table, digest, SOURCE_SHA256))
    with open(a.table, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if len(rows) != SOURCE_ROWS:
        sys.exit("REFUSING: %d rows, expected %d" % (len(rows), SOURCE_ROWS))

    nsr = {}
    for r in rows:
        if float(r["contig_length"]) >= 1000:
            nsr[r["sample"]] = nsr.get(r["sample"], 0) + 1

    def key(i):
        r = rows[i]
        return hashlib.sha256(("%s\t%s" % (r["sample"], r["contig_id"])).encode()).hexdigest()

    ranked = sorted(range(len(rows)), key=key)
    chosen = []

    def take(pred, k):
        n = 0
        for i in ranked:
            if n >= k:
                break
            if pred(rows[i]):
                if i not in chosen:
                    chosen.append(i)
                n += 1

    for t in TOOLS:
        for s in sorted({r[t] for r in rows}):
            take(lambda r, t=t, s=s: r[t] == s, 2)
    for m, c in sorted({(r["router_model"], r["router_call"]) for r in rows}):
        take(lambda r, m=m, c=c: r["router_model"] == m and r["router_call"] == c, 4)
    for c11, c12 in sorted({(r["v11_call"], r["v12_call"]) for r in rows}):
        take(lambda r, c11=c11, c12=c12: r["v11_call"] == c11 and r["v12_call"] == c12, 3)
    for col, thr in (("v12_score", 0.9285), ("v11_score", 0.9524), ("v11_score", 0.9605)):
        above = sorted((i for i in ranked if rows[i][col] and float(rows[i][col]) >= thr),
                       key=lambda i: (float(rows[i][col]) - thr, key(i)))[:3]
        below = sorted((i for i in ranked if rows[i][col] and float(rows[i][col]) < thr),
                       key=lambda i: (thr - float(rows[i][col]), key(i)))[:3]
        for i in above + below:
            if i not in chosen:
                chosen.append(i)
    for small in (True, False):
        for arg in ("true", "false"):
            take(lambda r, small=small, arg=arg: (float(r["contig_length"]) < 1000) == small
                 and r["ARG_bearing_bool"] == arg, 3)
    for i in ranked:
        if len(chosen) >= TARGET_ROWS:
            break
        if i not in chosen:
            chosen.append(i)

    with open(a.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(COLUMNS)
        for i in sorted(chosen):
            r = dict(rows[i])
            r["n_contigs_ge_1kb"] = str(nsr.get(r["sample"], 0))
            w.writerow([r[c] for c in COLUMNS])
    with open(a.out, "rb") as f:
        out_digest = hashlib.sha256(f.read()).hexdigest()
    print("source sha256 %s (%d rows)" % (digest, len(rows)))
    n_samples = len({rows[i]["sample"] for i in chosen})
    print("wrote %d rows from %d samples to %s" % (len(chosen), n_samples, os.path.basename(a.out)))
    print("fixture sha256 %s" % out_digest)


if __name__ == "__main__":
    main()

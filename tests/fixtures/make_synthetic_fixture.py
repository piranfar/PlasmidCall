#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vahhab Piranfar
"""Build tests/fixtures/synthetic_rules_fixture.tsv with the frozen production code.

The public P1.13 table has no MISSING call, no contig without a chromosome or plasmid vote
(n_valid == 0), and no failed, missing or unparseable annotation. This script makes invented
contigs that have them, then scores them with the frozen P1.13 production chain, unchanged:

  1  scripts/evaluation/build_p113_contig_table.py   pass 1, v1.2-General from the pickle
  2  scripts/evaluation/v11_scorer_p111.py score      v1.1 from the pickle
  3  scripts/evaluation/build_p113_contig_table.py   pass 2, v1.1 injected, router applied

This is the order of scripts/evaluation/p113_candidate_pipeline.py. The expected outputs in the
fixture are the output of step 3. No real sequence, call or annotation is used.

Contigs:
  SYN01, SYN02   two base panels; each tool in turn is set to each of the 7 states
  SYN03          annotation ok with no resistance gene; panels with no chromosome or plasmid
                 vote, including all MISSING, all FAILED and all abstaining
  SYN04          annotation failed
  SYN05          annotation missing (never run)
  SYN06          annotation unparseable (run marked done, no output file)
  SYN07          annotation ok, every contig below 1 kb, so v1.1 abstains for the sample

Needs scikit-learn 1.9.0, numpy 2.x and pandas, as the frozen scripts do. The frozen scripts
run as child processes with PYTHONDONTWRITEBYTECODE=1 and P112_FREEZE set to a temporary
directory, so nothing is written into the repository except the fixture.

Usage:
  python tests/fixtures/make_synthetic_fixture.py [--out PATH]
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
EVAL = os.path.join(REPO, "scripts", "evaluation")
V12_PKL = os.path.join(REPO, "models", "plasmidcall_v1.2-general", "plasmidcall_v1_2_general.pkl")
V11_PKL = os.path.join(REPO, "models", "plasmidcall_v1.1", "plasmidcall_v1_1_m2.pkl")
DEFAULT_OUT = os.path.join(HERE, "synthetic_rules_fixture.tsv")

TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC", "PlasmidFinder",
         "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
VOCAB = ["chromosome", "plasmid", "unknown", "unclassified", "repeat", "FAILED", "MISSING"]
LENGTHS = [500, 999, 1000, 1500, 5000, 20000, 150000]
COLUMNS = (["sample", "contig_id", "contig_length"] + TOOLS
           + ["annotation_state", "ARG_bearing_bool",
              "v11_score", "v11_score_state", "v11_call",
              "v12_score", "v12_score_state", "v12_call",
              "router_state", "router_model", "router_call", "abstention_reason"])

BASE_P = ["plasmid", "plasmid", "plasmid", "plasmid", "plasmid", "chromosome",
          "plasmid", "plasmid", "chromosome", "plasmid", "plasmid", "plasmid"]
BASE_C = ["chromosome", "chromosome", "unknown", "unclassified", "plasmid", "chromosome",
          "chromosome", "chromosome", "plasmid", "chromosome", "repeat", "chromosome"]
NO_VOTE = [
    ["MISSING"] * 12,
    ["FAILED"] * 12,
    ["unknown"] * 12,
    ["unknown", "FAILED", "unknown", "unclassified", "unknown", "unknown",
     "FAILED", "MISSING", "MISSING", "MISSING", "repeat", "unknown"],
    ["MISSING"] * 6 + ["FAILED"] * 6,
    ["chromosome"] + ["MISSING"] * 11,
]


def contigs():
    """(sample, annotation mode, [(contig_id, length, calls, arg_bearing)])"""
    out = []
    for sample, base in (("SYN01", BASE_P), ("SYN02", BASE_C)):
        rows, k = [], 0
        for j in range(len(TOOLS)):
            for v in VOCAB:
                calls = list(base)
                calls[j] = v
                k += 1
                rows.append(("c%03d" % k, LENGTHS[k % len(LENGTHS)], calls, k % 5 == 0))
        out.append((sample, "ok", rows))
    out.append(("SYN03", "ok_no_hits",
                [("c%03d" % (k + 1), LENGTHS[(k + 3) % len(LENGTHS)], calls, False)
                 for k, calls in enumerate(NO_VOTE)]))
    small = [("c001", 5000, BASE_P, True), ("c002", 800, BASE_C, False),
             ("c003", 20000, BASE_C, True), ("c004", 1000, NO_VOTE[0], False),
             ("c005", 150000, BASE_P, False)]
    out.append(("SYN04", "failed", small))
    out.append(("SYN05", "missing", small))
    out.append(("SYN06", "unparseable", small))
    out.append(("SYN07", "ok", [("c001", 900, BASE_P, True), ("c002", 999, BASE_C, True),
                                ("c003", 500, BASE_P, False), ("c004", 700, NO_VOTE[3], False),
                                ("c005", 950, BASE_C, False)]))
    return out


def write_root(root):
    asm = os.path.join(root, "assemblies", "shortread")
    state = os.path.join(root, "inference", "state")
    receipts = os.path.join(root, "inference", "receipts")
    annot = os.path.join(root, "annotation", "native")
    for d in (asm, state, receipts, annot):
        os.makedirs(d)
    calls_path = os.path.join(root, "inference", "P1.13_predictions_normalised.tsv")
    with open(calls_path, "w", encoding="utf-8", newline="") as cf:
        cw = csv.writer(cf, delimiter="\t", lineterminator="\n")
        cw.writerow(["sample", "contig_id", "tool", "model1_code"])
        for sample, mode, rows in contigs():
            os.makedirs(os.path.join(asm, sample))
            with open(os.path.join(asm, sample, "shortread.fasta"), "w", newline="\n") as fa:
                for cid, length, calls, _ in rows:
                    fa.write(">%s\n%s\n" % (cid, "A" * length))
            for cid, _, calls, _ in rows:
                for t, v in zip(TOOLS, calls):
                    cw.writerow([sample, cid, t, v])
            key = "amrfinder__%s" % sample
            if mode in ("ok", "ok_no_hits", "unparseable"):
                open(os.path.join(state, key + ".done"), "w").close()
                with open(os.path.join(receipts, key + ".json"), "w") as f:
                    json.dump({"status": "OK"}, f)
            elif mode == "failed":
                open(os.path.join(state, key + ".failed"), "w").close()
            if mode in ("ok", "ok_no_hits"):
                os.makedirs(os.path.join(annot, sample))
                with open(os.path.join(annot, sample, "%s.amrfinder.tsv" % sample), "w",
                          newline="\n") as f:
                    f.write("Contig id\tElement type\tElement subtype\tScope\tClass\n")
                    for cid, _, _, arg in rows:
                        if arg and mode == "ok":
                            f.write("%s\tAMR\tAMR\tcore\tBETA-LACTAM\n" % cid)


def run(cmd, env):
    cp = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=EVAL)
    if cp.returncode not in (0, 1):
        sys.stderr.write(cp.stdout[-2000:] + cp.stderr[-2000:])
        sys.exit("step failed: %s" % " ".join(os.path.basename(c) for c in cmd[1:3]))
    return cp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="plasmidcall_synth_")
    try:
        root = os.path.join(tmp, "root")
        work = os.path.join(tmp, "work")
        os.makedirs(work)
        write_root(root)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", P112_FREEZE=work,
                   P112_DATA=work)
        pass1 = os.path.join(work, "pass1.tsv")
        v11 = os.path.join(work, "v11.tsv")
        final = os.path.join(work, "final.tsv")
        py = sys.executable
        run([py, "build_p113_contig_table.py", "--root", root, "--out", pass1,
             "--model", V12_PKL], env)
        run([py, "v11_scorer_p111.py", "score", "--model", V11_PKL, "--contig-table", pass1,
             "--out", v11], env)
        run([py, "build_p113_contig_table.py", "--root", root, "--out", final,
             "--model", V12_PKL, "--v11-scores", v11], env)
        with open(final, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="\t"))
        with open(a.out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t", lineterminator="\n")
            w.writerow(COLUMNS)
            for r in rows:
                w.writerow([r[c] for c in COLUMNS])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(a.out, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    print("wrote %d rows to %s" % (len(rows), os.path.basename(a.out)))
    print("fixture sha256 %s" % digest)


if __name__ == "__main__":
    main()

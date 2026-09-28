#!/usr/bin/env python3
"""Self-test for scripts/parsers/parse_outputs.py against the frozen driver.

The test writes a small SYNTHETIC input tree to a temporary directory: two made-up samples,
hand-written native outputs in the formats the frozen parsers read, and run receipts. No study
data is used. It then

  1. runs the frozen driver, frozen/parse_all.py, unchanged, on that tree;
  2. runs parse_outputs.py on the same tree;
  3. requires the long table and every per-sample file to be byte-identical, and the per tool
     and sample summaries to be equal;
  4. checks 96 expected states, derived by hand from the rules in frozen/parsers.py, including
     each way a FAILED call arises;
  5. checks that MISSING arises only when a tool has no parsed call for a contig (--tools, and a
     pivot of an incomplete long table), that --from-long rebuilds the frozen long table from
     the per-sample files, and that --status-from-outputs agrees with the receipts on runs
     whose receipts say OK.

Usage: python -B scripts/parsers/tests/test_parse_outputs.py
Standard library only. Exit code 0 when every check passes.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PARSERS_DIR = os.path.dirname(HERE)
FROZEN_DIR = os.path.join(PARSERS_DIR, "frozen")
CLI = os.path.join(PARSERS_DIR, "parse_outputs.py")
PARSE_ALL = os.path.join(FROZEN_DIR, "parse_all.py")

TOOLS = ["mobsuite", "platon", "rfplasmid", "plascope", "plasmidec", "plasmidfinder", "genomad",
         "plasme", "plasmer", "gplas2", "plasgraph2", "hyasp"]
DISPLAY = {"hyasp": "HyAsP", "mobsuite": "MOB-recon", "plasme": "PLASMe", "plascope": "PlaScope",
           "plasmer": "Plasmer", "plasmidec": "PlasmidEC", "plasmidfinder": "PlasmidFinder",
           "platon": "Platon", "rfplasmid": "RFPlasmid", "genomad": "geNomad", "gplas2": "gplas2",
           "plasgraph2": "plASgraph2"}

# Synthetic contigs: id -> length. SYN_A contig 1 is above PLASMe's 350 kb rule, contig 4 is
# below 1 kb.
CONTIGS = {
    "SYN_A": [("1", 360000), ("2", 5000), ("3", 1200), ("4", 800), ("5", 2000)],
    "SYN_B": [("1", 3000), ("2", 1500), ("3", 900)],
}

# Expected model1_code per (sample, runner key), in contig order, derived by hand from
# frozen/parsers.py for the native outputs written below.
EXPECTED = {
    ("SYN_A", "mobsuite"): ["chromosome", "plasmid", "plasmid", "unknown", "unknown"],
    ("SYN_A", "platon"): ["chromosome", "plasmid", "unknown", "unknown", "chromosome"],
    ("SYN_A", "rfplasmid"): ["chromosome", "plasmid", "plasmid", "unknown", "unknown"],
    ("SYN_A", "plascope"): ["chromosome", "plasmid", "unclassified", "unclassified", "unclassified"],
    ("SYN_A", "plasmidec"): ["chromosome", "plasmid", "plasmid", "unknown", "chromosome"],
    ("SYN_A", "plasmidfinder"): ["chromosome", "plasmid", "chromosome", "chromosome", "chromosome"],
    ("SYN_A", "genomad"): ["chromosome", "plasmid", "plasmid", "chromosome", "chromosome"],
    ("SYN_A", "plasme"): ["chromosome", "plasmid", "chromosome", "unknown", "chromosome"],
    ("SYN_A", "plasmer"): ["chromosome", "plasmid", "unknown", "unknown", "unknown"],
    ("SYN_A", "gplas2"): ["chromosome", "plasmid", "unknown", "unknown", "repeat"],
    ("SYN_A", "plasgraph2"): ["chromosome", "plasmid", "unknown", "unknown", "unknown"],
    ("SYN_A", "hyasp"): ["chromosome", "plasmid", "chromosome", "chromosome", "chromosome"],
    ("SYN_B", "mobsuite"): ["FAILED"] * 3,        # receipt status FAILED
    ("SYN_B", "platon"): ["FAILED"] * 3,          # no receipt: NOT_RUN
    ("SYN_B", "rfplasmid"): ["FAILED"] * 3,       # malformed output: ParseError
    ("SYN_B", "plascope"): ["plasmid", "unclassified", "unclassified"],
    ("SYN_B", "plasmidec"): ["plasmid", "chromosome", "unknown"],
    ("SYN_B", "plasmidfinder"): ["FAILED"] * 3,   # mandatory file absent: ParseError
    ("SYN_B", "genomad"): ["plasmid", "chromosome", "chromosome"],
    ("SYN_B", "plasme"): ["plasmid", "chromosome", "unknown"],
    ("SYN_B", "plasmer"): ["plasmid", "unknown", "unknown"],
    ("SYN_B", "gplas2"): ["plasmid", "chromosome", "unknown"],
    ("SYN_B", "plasgraph2"): ["plasmid", "chromosome", "unknown"],
    ("SYN_B", "hyasp"): ["plasmid", "chromosome", "chromosome"],
}
EXPECTED_NATIVE = {
    ("SYN_B", "mobsuite"): "tool_status_FAILED",
    ("SYN_B", "platon"): "tool_status_NOT_RUN",
    ("SYN_B", "rfplasmid"): "parse_error",
    ("SYN_B", "plasmidfinder"): "parse_error",
    ("SYN_A", "plasme", "1"): "gt350kb_rule",
    ("SYN_A", "plasme", "4"): "outside_plasme_domain_lt1000_listed",
    ("SYN_A", "gplas2", "1"): "initial_class_chromosome_not_reevaluated",
    ("SYN_A", "plascope", "4"): "no_C_P_U_hits",
}

HEADER = ["sample", "contig_id", "contig_length", "tool", "native_call", "model1_code",
          "evidence_score", "native_sha256sums", "parser_version"]


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(text)


def seq(n):
    s = ("ACGT" * (n // 4 + 1))[:n]
    return "\n".join(s[i:i + 80] for i in range(0, n, 80)) + "\n"


def build_tree(root):
    base = os.path.join(root, "p113")
    asm = os.path.join(base, "assemblies", "shortread")
    nat = os.path.join(base, "inference", "native")
    rec = os.path.join(base, "inference", "receipts")
    for s, contigs in CONTIGS.items():
        w(os.path.join(asm, s, "shortread.fasta"),
          "".join(">%s length=%d depth=1.00x\n%s" % (c, L, seq(L)) for c, L in contigs))

    def receipt(tool, s, status="OK"):
        w(os.path.join(rec, "%s__%s.json" % (tool, s)),
          json.dumps({"tool": tool, "sample": s, "status": status}, indent=1) + "\n")

    # ---------------- SYN_A: every tool ran and wrote valid output
    s = "SYN_A"
    o = lambda t: os.path.join(nat, t, s)
    w(os.path.join(o("mobsuite"), "mob", "contig_report.txt"),
      "sample_id\tmolecule_type\tprimary_cluster_id\tsecondary_cluster_id\tcontig_id\tsize\n"
      "SYN_A\tchromosome\t-\t-\t1 length=360000\t360000\n"
      "SYN_A\tplasmid\tAA001\tAA001\t2 length=5000\t5000\n"
      "SYN_A\tplasmid\tAA002\tAA002\t3 length=1200\t1200\n")
    w(os.path.join(o("platon"), "SYN_A.plasmid.fasta"), ">2\nACGT\n")
    w(os.path.join(o("platon"), "SYN_A.chromosome.fasta"), ">1\nACGT\n>5\nACGT\n")
    w(os.path.join(o("rfplasmid"), "rf", "SYN_A", "prediction.csv"),
      '"",prediction,votes chromosomal,votes plasmid,contigID\n'
      '"1",c,0.95,0.05,1\n"2",p,0.1,0.9,2\n"3",p,0.3,0.7,3\n')
    w(os.path.join(o("plascope"), "SYN_A_extendedresults.tsv"),
      "readID\tseqID\ttaxID\tscore\t2ndBestScore\thitLength\tqueryLength\tnumMatches\n"
      + "".join("%s\tx\t%s\t100\t0\t50\t100\t1\n" % (c, tx) for c, tx in
                [("1", 2), ("1", 2), ("1", 2), ("2", 3), ("2", 3), ("2", 3),
                 ("3", 3), ("3", 2), ("4", 1)]))
    w(os.path.join(o("plasmidec"), "pec", "gplas_format", "SYN_A_plasmid_prediction.tab"),
      "Contig_name\tPrediction\tProb_Chromosome\tProb_Plasmid\n"
      "S1_LN:i:360000_dp:f:1.0\tChromosome\t0.99\t0.01\n"
      "S2_LN:i:5000_dp:f:3.0\tPlasmid\t0.1\t0.9\n"
      "S3_LN:i:1200_dp:f:2.0\tPlasmid\t0.3\t0.7\n"
      "S5_LN:i:2000_dp:f:1.0\tChromosome\t0.8\t0.2\n")
    w(os.path.join(o("plasmidfinder"), "pf", "results_tab.tsv"),
      "Database\tPlasmid\tIdentity\tQuery / Template length\tContig\tPosition in contig\tNote\tAccession number\n"
      "enterobacteriales\tIncFII\t100.0\t260 / 260\t2 length=5000\t10..270\t\tAY000000\n")
    w(os.path.join(o("genomad"), "genomad", "shortread_summary", "shortread_plasmid_summary.tsv"),
      "seq_name\tlength\ttopology\tn_genes\tgenetic_code\tplasmid_score\tfdr\tn_hallmarks\tconjugation_genes\tamr_genes\n"
      "2\t5000\tNo terminal repeats\t5\t11\t0.9900\tNA\t1\tNA\tNA\n"
      "3\t1200\tNo terminal repeats\t1\t11\t0.8100\tNA\t0\tNA\tNA\n")
    w(os.path.join(o("plasme"), "SYN_A.plasme.fna"), ">c2\nACGT\n>c4\nACGT\n")
    w(os.path.join(o("plasme"), "temp", "PLASMe_candidate.csv"),
      "order,query,identity,coverage,PLASMe,overlap\n1,c2,0.99,0.95,0.98,0\n2,c4,0.97,0.9,0.91,0\n3,c3,0.5,0.2,0.1,0\n")
    w(os.path.join(o("plasmer"), "results", "SYN_A.plasmer.predClass.tsv"),
      "1\tchromosome\n2\tplasmid\n3\tunclassified\n")
    w(os.path.join(o("gplas2"), "results", "SYN_A_results.tab"),
      "number Contig_name Prob_Chromosome Prob_Plasmid Prediction length coverage Bin\n"
      "2 S2_LN:i:5000_dp:f:3.0 0.1 0.9 Plasmid 5000 3.0 1\n"
      "3 S3_LN:i:1200_dp:f:2.0 0.3 0.7 Plasmid 1200 2.0 Unbinned\n"
      "5 S5_LN:i:2000_dp:f:1.0 0.5 0.5 Repeat 2000 1.0 Repeat\n")
    w(os.path.join(o("gplas2"), "results", "SYN_A_chromosome_repeats.tab"), "number Contig_name\n")
    w(os.path.join(o("plasgraph2"), "SYN_A.plasgraph2.csv"),
      "sample,contig,length,plasmid_score,chrom_score,label\n"
      "SYN_A,1,360000,0.01,0.99,chromosome\nSYN_A,2,5000,0.95,0.05,plasmid\n"
      "SYN_A,3,1200,0.6,0.6,ambiguous\nSYN_A,5,2000,0.1,0.1,unlabeled\n")
    w(os.path.join(o("hyasp"), "find", "putative_plasmid_contigs.fasta"), ">2|1_plasmid_1\nACGT\n")
    for t in TOOLS:
        receipt(t, s)
    w(os.path.join(rec, "genomad__SYN_A.SHA256SUMS"), "0" * 64 + "  genomad/shortread_summary/x.tsv\n")

    # ---------------- SYN_B: four tools fail, each in a different way
    s = "SYN_B"
    o = lambda t: os.path.join(nat, t, s)
    os.makedirs(o("mobsuite"))
    receipt("mobsuite", s, "FAILED")                   # run failed
    # platon: no receipt and no output                 -> NOT_RUN
    w(os.path.join(o("rfplasmid"), "rf", "SYN_B", "prediction.csv"),
      '"",prediction,votes chromosomal,votes plasmid,contigID\n"1",x,0.5,0.5,1\n')
    receipt("rfplasmid", s)                            # malformed output
    os.makedirs(os.path.join(o("plasmidfinder"), "pf"))
    receipt("plasmidfinder", s)                        # mandatory output absent
    w(os.path.join(o("plascope"), "SYN_B_extendedresults.tsv"),
      "readID\tseqID\ttaxID\tscore\t2ndBestScore\thitLength\tqueryLength\tnumMatches\n1\tx\t3\t100\t0\t50\t100\t1\n")
    w(os.path.join(o("plasmidec"), "pec", "gplas_format", "SYN_B_plasmid_prediction.tab"),
      "Contig_name\tPrediction\tProb_Chromosome\tProb_Plasmid\n"
      "S1_LN:i:3000_dp:f:5.0\tPlasmid\t0.1\t0.9\nS2_LN:i:1500_dp:f:1.0\tChromosome\t0.9\t0.1\n")
    w(os.path.join(o("genomad"), "genomad", "shortread_summary", "shortread_plasmid_summary.tsv"),
      "seq_name\tlength\ttopology\tn_genes\tgenetic_code\tplasmid_score\tfdr\tn_hallmarks\tconjugation_genes\tamr_genes\n"
      "1\t3000\tNo terminal repeats\t3\t11\t0.9500\tNA\t1\tNA\tNA\n")
    w(os.path.join(o("plasme"), "SYN_B.plasme.fna"), ">c1\nACGT\n")
    w(os.path.join(o("plasme"), "temp", "PLASMe_candidate.csv"),
      "order,query,identity,coverage,PLASMe,overlap\n1,c1,0.99,0.95,0.97,0\n")
    w(os.path.join(o("plasmer"), "results", "SYN_B.plasmer.predClass.tsv"), "1\tplasmid\n")
    w(os.path.join(o("gplas2"), "results", "SYN_B_results.tab"),
      "number Contig_name Prob_Chromosome Prob_Plasmid Prediction length coverage Bin\n"
      "1 S1_LN:i:3000_dp:f:5.0 0.1 0.9 Plasmid 3000 5.0 1\n")
    w(os.path.join(o("plasgraph2"), "SYN_B.plasgraph2.csv"),
      "sample,contig,length,plasmid_score,chrom_score,label\n"
      "SYN_B,1,3000,0.9,0.1,plasmid\nSYN_B,2,1500,0.1,0.9,chromosome\n")
    w(os.path.join(o("hyasp"), "find", "putative_plasmid_contigs.fasta"), ">1|1_plasmid_1\nACGT\n")
    for t in ("plascope", "plasmidec", "genomad", "plasme", "plasmer", "gplas2", "plasgraph2", "hyasp"):
        receipt(t, s)
    return asm, nat, rec


def read_bytes(p):
    with open(p, "rb") as f:
        return f.read()


def read_tsv(p):
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.reader(f, delimiter="\t"))


def run(cmd, env):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit("command failed (%d): %s" % (r.returncode, " ".join(cmd)))
    return r.stdout


class Checks:
    def __init__(self):
        self.n = 0
        self.failed = []

    def ok(self, name, cond, detail=""):
        self.n += 1
        if not cond:
            self.failed.append("%s %s" % (name, detail))
        print("%s  %s%s" % ("PASS" if cond else "FAIL", name, (" (" + detail + ")") if (detail and not cond) else ""))


def main():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    py = [sys.executable, "-B"]
    tmp = tempfile.mkdtemp(prefix="plasmidcall_parser_test_")
    ck = Checks()
    try:
        asm, nat, rec = build_tree(tmp)
        out = os.path.join(tmp, "out")
        os.makedirs(out)

        # 1. the frozen driver, unchanged. ROOT is argv[1]; it reads ROOT/p113/...
        run(py + [PARSE_ALL, tmp], env)
        inf = os.path.join(tmp, "p113", "inference")
        frozen_long = os.path.join(inf, "P1.13_predictions_normalised.tsv")
        with open(os.path.join(inf, "P1.13_parse_summary.json"), encoding="utf-8") as f:
            frozen_summary = json.load(f)

        # 2. this CLI on the same tree
        run(py + [CLI, "--assemblies", asm, "--native", nat, "--receipts", rec,
                  "--long", os.path.join(out, "long.tsv"), "--wide", os.path.join(out, "wide.tsv"),
                  "--per-sample-dir", os.path.join(out, "parsed"),
                  "--summary", os.path.join(out, "summary.json"), "--quiet"], env)

        # 3. byte identity with the frozen driver
        ck.ok("long table byte-identical to frozen parse_all.py",
              read_bytes(frozen_long) == read_bytes(os.path.join(out, "long.tsv")))
        n_same = n_files = 0
        for t in TOOLS:
            for s in CONTIGS:
                n_files += 1
                a = os.path.join(inf, "parsed", t, s + ".tsv")
                b = os.path.join(out, "parsed", t, s + ".tsv")
                n_same += int(os.path.exists(b) and read_bytes(a) == read_bytes(b))
        ck.ok("per-sample files byte-identical (%d of %d)" % (n_same, n_files), n_same == n_files == 24)
        with open(os.path.join(out, "summary.json"), encoding="utf-8") as f:
            mine = json.load(f)
        # parse_error messages quote the input path. On Windows the separators in that path can
        # differ between the two drivers, so they are normalised before comparing.
        norm = lambda d: {k: dict(v, parse_error=v["parse_error"].replace("\\", "/")) for k, v in d.items()}
        diff = sorted(k for k in set(mine["per_tool_sample"]) | set(frozen_summary["per_tool_sample"])
                      if norm(mine["per_tool_sample"]).get(k) != norm(frozen_summary["per_tool_sample"]).get(k))
        ck.ok("per tool and sample summary equal to frozen", not diff, "; ".join(diff))
        ck.ok("row count equal to frozen", mine["rows"] == frozen_summary["rows"] == 12 * 8)

        # 4. hand-derived expected states and native calls
        rows = read_tsv(frozen_long)
        ck.ok("frozen header", rows[0] == HEADER)
        got = {}
        native = {}
        for r in rows[1:]:
            got.setdefault((r[0], r[3]), []).append(r[5])
            native[(r[0], r[3], r[1])] = r[4]
        bad = []
        n_cells = 0
        for (s, t), want in EXPECTED.items():
            n_cells += len(want)
            if got.get((s, DISPLAY[t])) != want:
                bad.append("%s/%s: got %s want %s" % (s, t, got.get((s, DISPLAY[t])), want))
        ck.ok("%d expected states" % n_cells, not bad and n_cells == 96, "; ".join(bad))
        bad = []
        for k, want in EXPECTED_NATIVE.items():
            if len(k) == 2:
                vals = {native[(k[0], DISPLAY[k[1]], c)] for c, _ in CONTIGS[k[0]]}
                if vals != {want}:
                    bad.append("%s: %s" % (k, vals))
            elif native[(k[0], DISPLAY[k[1]], k[2])] != want:
                bad.append("%s: %s" % (k, native[(k[0], DISPLAY[k[1]], k[2])]))
        ck.ok("expected native_call values for FAILED and rule-based calls", not bad, "; ".join(bad))
        ck.ok("frozen driver emits no MISSING", all(r[5] != "MISSING" for r in rows[1:]))
        sums = {r[7] for r in rows[1:] if r[0] == "SYN_A" and r[3] == "geNomad"}
        ck.ok("native_sha256sums filled from the SHA256SUMS receipt", len(sums) == 1 and len(sums.pop()) == 64)

        # the wide table carries the same states, in the frozen tool order
        wide = read_tsv(os.path.join(out, "wide.tsv"))
        order = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC", "PlasmidFinder",
                 "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
        ck.ok("wide header in frozen tool order", wide[0] == ["sample", "contig_id", "contig_length"] + order)
        bad = []
        for r in wide[1:]:
            for j, tool in enumerate(order):
                t = [k for k, v in DISPLAY.items() if v == tool][0]
                i = [c for c, _ in CONTIGS[r[0]]].index(r[1])
                if r[3 + j] != EXPECTED[(r[0], t)][i]:
                    bad.append("%s %s %s" % (r[0], r[1], tool))
        ck.ok("wide table states match the long table", not bad and len(wide) == 1 + 8, "; ".join(bad))
        ck.ok("wide table has LF line ends", b"\r" not in read_bytes(os.path.join(out, "wide.tsv")))

        # 5. MISSING arises only when a tool has no parsed call
        run(py + [CLI, "--assemblies", asm, "--native", nat, "--receipts", rec, "--tools", "genomad,PlaScope",
                  "--wide", os.path.join(out, "wide_sub.tsv"), "--quiet"], env)
        sub = read_tsv(os.path.join(out, "wide_sub.tsv"))
        keep = {"geNomad", "PlaScope"}
        ok_missing = all((r[3 + j] == "MISSING") == (tool not in keep)
                         for r in sub[1:] for j, tool in enumerate(order))
        ck.ok("--tools: left-out tools are MISSING, kept tools are not", ok_missing and len(sub) == 9)

        piv = os.path.join(out, "wide_from_long.tsv")
        run(py + [CLI, "--from-long", frozen_long, "--wide", piv], env)
        ck.ok("pivot of the frozen long table equals the direct wide table",
              read_bytes(piv) == read_bytes(os.path.join(out, "wide.tsv")))
        rebuilt = os.path.join(out, "long_from_parsed.tsv")
        run(py + [CLI, "--from-long", os.path.join(inf, "parsed"), "--long", rebuilt], env)
        ck.ok("--from-long on the frozen per-sample files rebuilds the frozen long table",
              read_bytes(rebuilt) == read_bytes(frozen_long))
        part = os.path.join(out, "partial_long.tsv")
        with open(part, "w", encoding="utf-8", newline="") as f:
            wr = csv.writer(f, delimiter="\t")
            wr.writerow(HEADER)
            wr.writerows(r for r in rows[1:] if not (r[0] == "SYN_A" and r[1] == "3" and r[3] == "Platon"))
        piv2 = os.path.join(out, "wide_partial.tsv")
        run(py + [CLI, "--from-long", part, "--wide", piv2, "--assemblies", asm], env)
        p2 = read_tsv(piv2)
        cells = [(r[0], r[1], order[j]) for r in p2[1:] for j in range(12) if r[3 + j] == "MISSING"]
        ck.ok("pivot: MISSING exactly where a row is absent", cells == [("SYN_A", "3", "Platon")], str(cells))

        run(py + [CLI, "--assemblies", asm, "--native", nat, "--status-from-outputs",
                  "--long", os.path.join(out, "long_nr.tsv"), "--quiet"], env)
        nr = read_tsv(os.path.join(out, "long_nr.tsv"))
        a_rec = [r[:7] for r in rows[1:] if r[0] == "SYN_A"]
        a_nr = [r[:7] for r in nr[1:] if r[0] == "SYN_A"]
        ck.ok("--status-from-outputs equals receipts where every receipt says OK", a_rec == a_nr and len(a_rec) == 60)
        pl = {r[4] for r in nr[1:] if r[0] == "SYN_B" and r[3] == "Platon"}
        ck.ok("--status-from-outputs: absent output directory is FAILED (tool_status_NOT_RUN)",
              pl == {"tool_status_NOT_RUN"})

        ck.ok("no bytecode written next to the frozen files",
              not os.path.exists(os.path.join(FROZEN_DIR, "__pycache__")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%d checks, %d passed, %d failed" % (ck.n, ck.n - len(ck.failed), len(ck.failed)))
    return 1 if ck.failed else 0


if __name__ == "__main__":
    sys.exit(main())

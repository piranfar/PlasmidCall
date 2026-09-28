#!/usr/bin/env python3
"""Run the frozen PlasmidCall panel parser on native tool outputs.

The frozen parser is scripts/parsers/frozen/parsers.py (p19c4-parsers/1.7). It is imported
unchanged and never edited. The frozen driver, scripts/parsers/frozen/parse_all.py, hard-codes
its input and output paths and runs at import time, so it cannot be pointed at another directory
without editing it. This script repeats its per-tool, per-sample loop with paths taken from the
command line. For the same inputs it writes the same rows, in the same order, with the same bytes.
docs/PARSING.md describes the states, the input layout and how this equivalence was checked.

Two modes.

1. Parse native outputs (the frozen driver's job):

   parse_outputs.py --assemblies DIR --native DIR (--receipts DIR | --status-from-outputs)
                    [--long TSV] [--wide TSV] [--per-sample-dir DIR] [--summary JSON]
                    [--samples S1,S2,...] [--tools KEY,...] [--fasta-name NAME] [--quiet]

   Directory layouts (the ones the frozen runs used):
     --assemblies  <DIR>/<sample>/<fasta-name>        contig universe and lengths
                                                      (default name shortread.fasta)
     --native      <DIR>/<tool>/<sample>/...          each tool's native output directory
     --receipts    <DIR>/<tool>__<sample>.json        run status ("status": "OK" or other)
                   <DIR>/<tool>__<sample>.SHA256SUMS  optional; its sha256 fills native_sha256sums
   <tool> is the runner key: mobsuite platon rfplasmid plascope plasmidec plasmidfinder genomad
   plasme plasmer gplas2 plasgraph2 hyasp.

2. Combine existing long tables:

   parse_outputs.py --from-long PATH [PATH ...] [--wide TSV] [--long TSV]
                    [--assemblies DIR] [--samples ...]

   PATH is a long table written by the frozen driver or by mode 1, or a directory holding the
   frozen per-sample files <tool>/<sample>.tsv. --long writes their rows in the frozen order;
   --wide pivots them.

Outputs.
  --long            the frozen long table: sample, contig_id, contig_length, tool, native_call,
                    model1_code, evidence_score, native_sha256sums, parser_version. model1_code
                    is the seven-state call. Tab-separated with CRLF line ends, as the frozen
                    driver writes it.
  --wide            one row per contig: sample, contig_id, contig_length, then one column per
                    tool in the frozen scorer order (HyAsP ... plASgraph2). A contig with no
                    parsed call from a tool is MISSING. Tab-separated, LF line ends.
  --per-sample-dir  the frozen per-sample files <DIR>/<tool>/<sample>.tsv.
  --summary         per tool and sample: run status, parse error, count of each state.

Standard library only.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FROZEN_DIR = os.path.join(HERE, "frozen")

# The frozen files carry these digests. Any other bytes are not the frozen parser.
FROZEN_SHA256 = {
    "parsers.py": "68599a94af066f2dd1437de4ab307721ce8310399e0ba6fa91f2e559b65467b1",
    "parse_all.py": "b3230949b062c48b82c84a63debe4b5ef14cb04d294aa36c032b2fc91cbc0077",
}

# Long-table header, exactly as frozen/parse_all.py writes it.
HEADER = ["sample", "contig_id", "contig_length", "tool", "native_call", "model1_code",
          "evidence_score", "native_sha256sums", "parser_version"]

# Wide-table tool order: the order frozen into the v1.1 and v1.2-General encoders
# (TOOLS in scripts/evaluation/v11_scorer_p111.py, TOOL_ORDER in scripts/evaluation/freeze_v12.py).
TOOL_ORDER = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
              "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]

VOCAB = ("chromosome", "plasmid", "unknown", "unclassified", "repeat", "FAILED", "MISSING")


def die(msg, code=2):
    sys.stderr.write("parse_outputs: " + msg + "\n")
    sys.exit(code)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def load_frozen_parser():
    """Verify the frozen files byte for byte, then import parsers.py without writing bytecode."""
    for name, want in FROZEN_SHA256.items():
        p = os.path.join(FROZEN_DIR, name)
        if not os.path.isfile(p):
            die("frozen file not found: %s" % p)
        got = sha256_file(p)
        if got != want:
            die("frozen file %s has sha256 %s, expected %s. Restore the original bytes "
                "(a line-ending conversion is the usual cause) before parsing." % (name, got, want))
    sys.dont_write_bytecode = True
    sys.path.insert(0, FROZEN_DIR)
    import parsers  # noqa: E402  (frozen, byte-identical)
    if (set(parsers.TOOL_COLUMN.values()) != set(TOOL_ORDER)
            or set(parsers.PARSERS) != set(parsers.TOOL_COLUMN)):
        die("frozen parser tool set does not match the scorer tool order")
    return parsers


def contigs_of(fasta):
    """Contig id -> length, in file order. Same rule as contigs_of in frozen parse_all.py: the id
    is the first whitespace-separated token of the header; the length counts stripped sequence
    lines."""
    d = {}
    name = None
    with open(fasta, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            if line.startswith(">"):
                toks = line[1:].strip().split()
                if not toks:
                    die("empty FASTA header at line %d of %s" % (ln, fasta))
                name = toks[0]
                d[name] = 0
            else:
                if name is None:
                    if line.strip():
                        die("sequence before the first header in %s" % fasta)
                    continue
                d[name] += len(line.strip())
    return d


def inside(child, parent):
    child, parent = os.path.realpath(child), os.path.realpath(parent)
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def select_tools(P, spec):
    if not spec:
        return list(P.PARSERS)
    by_display = {v.lower(): k for k, v in P.TOOL_COLUMN.items()}
    want = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        key = tok.lower() if tok.lower() in P.PARSERS else by_display.get(tok.lower())
        if key is None:
            die("unknown tool %r. Use a runner key (%s) or a display name."
                % (tok, " ".join(P.PARSERS)))
        want.add(key)
    return [t for t in P.PARSERS if t in want]   # keep the frozen PARSERS order


def list_samples(asm_dir, fasta_name, subset):
    if not os.path.isdir(asm_dir):
        die("assemblies directory not found: %s" % asm_dir)
    samples = sorted(d for d in os.listdir(asm_dir) if os.path.isdir(os.path.join(asm_dir, d)))
    if subset:
        want = [s.strip() for s in subset.split(",") if s.strip()]
        absent = [s for s in want if s not in samples]
        if absent:
            die("samples not found under %s: %s" % (asm_dir, ", ".join(absent)))
        keep = set(want)
        samples = [s for s in samples if s in keep]
    if not samples:
        die("no sample directories under %s" % asm_dir)
    for s in samples:
        if not os.path.isfile(os.path.join(asm_dir, s, fasta_name)):
            die("no %s for sample %s" % (fasta_name, s))
    return samples


def run_status(tool, sample, native_dir, receipts_dir):
    """(status, native_sha256sums). With receipts this follows frozen parse_all.py exactly."""
    if receipts_dir is not None:
        rec = os.path.join(receipts_dir, "%s__%s.json" % (tool, sample))
        if os.path.exists(rec):
            with open(rec, encoding="utf-8") as f:
                doc = json.load(f)
            if "status" not in doc:
                die("receipt has no 'status' field: %s" % rec)
            status = doc["status"]
        else:
            status = "NOT_RUN"
        sums = os.path.join(receipts_dir, "%s__%s.SHA256SUMS" % (tool, sample))
        nsha = sha256_file(sums) if os.path.exists(sums) else ""
        return status, nsha
    # --status-from-outputs: no receipts; a tool counts as run when its output directory exists.
    ran = os.path.isdir(os.path.join(native_dir, tool, sample))
    return ("OK" if ran else "NOT_RUN"), ""


def parse_native(P, a):
    tools = select_tools(P, a.tools)
    samples = list_samples(a.assemblies, a.fasta_name, a.samples)
    for out in (a.long, a.wide, a.per_sample_dir, a.summary):
        if out and (inside(out, a.native) or inside(out, a.assemblies)
                    or (a.receipts and inside(out, a.receipts))):
            die("refusing to write %s inside an input directory" % out)

    long_f = long_w = None
    if a.long:
        long_f = open(a.long, "w", encoding="utf-8", newline="")
        long_w = csv.writer(long_f, delimiter="\t")      # csv default ends lines with CRLF, as frozen
        long_w.writerow(HEADER)

    native_root = a.native.rstrip("/\\") or a.native
    wide = {}            # (sample, contig) -> {display tool: state}
    contig_order = {}    # sample -> [(contig, length)] in FASTA order
    summary = {}
    n_rows = 0
    for t in tools:                      # frozen order: tools in parsers.PARSERS order,
        fn = P.PARSERS[t]
        disp = P.TOOL_COLUMN[t]
        for s in samples:                # then samples sorted, then contigs in FASTA order
            C = contigs_of(os.path.join(a.assemblies, s, a.fasta_name))
            contig_order.setdefault(s, list(C.items()))
            od = "%s/%s/%s" % (native_root, t, s)   # built as frozen parse_all.py builds it
            status, nsha = run_status(t, s, a.native, a.receipts)
            perr = ""
            if status != "OK":
                calls = {c: ("FAILED", "tool_status_%s" % status, "") for c in C}
            else:
                try:
                    calls = fn(od, C)
                except P.ParseError as e:
                    calls = {c: ("FAILED", "parse_error", "") for c in C}
                    perr = str(e)
                except Exception as e:  # the frozen driver stops here too
                    die("frozen parser for %s raised %s on sample %s: %s. The frozen driver "
                        "would also stop here. Inspect the native output."
                        % (t, type(e).__name__, s, e), 3)
            rows = []
            for c, L in C.items():
                code, nat, ev = calls[c]
                rows.append([s, c, L, disp, nat, code, ev, nsha, P.PARSER_VERSION])
                wide.setdefault((s, c), {})[disp] = code
            if a.per_sample_dir:
                d = os.path.join(a.per_sample_dir, t)
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, "%s.tsv" % s), "w", encoding="utf-8", newline="") as fo:
                    w = csv.writer(fo, delimiter="\t")
                    w.writerow(HEADER)
                    w.writerows(rows)
            if long_w:
                long_w.writerows(rows)
            n_rows += len(rows)
            cnt = {}
            for c in C:
                cnt[calls[c][0]] = cnt.get(calls[c][0], 0) + 1
            summary["%s|%s" % (t, s)] = {"tool_status": status, "parse_error": perr, "codes": cnt}
    if long_f:
        long_f.close()
    if a.wide:
        write_wide(a.wide, samples, contig_order, wide)
    if a.summary:
        with open(a.summary, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"generated_utc": datetime.datetime.now(datetime.timezone.utc)
                       .strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "parser_version": P.PARSER_VERSION,
                       "frozen_sha256": FROZEN_SHA256,
                       "status_source": "receipts" if a.receipts is not None else "output_directories",
                       "tools": [P.TOOL_COLUMN[t] for t in tools],
                       "samples": len(samples),
                       "rows": n_rows,
                       "per_tool_sample": summary}, f, indent=1)
            f.write("\n")
    report(summary, tools, P, n_rows, samples, a.quiet)


def report(summary, tools, P, n_rows, samples, quiet):
    if not quiet:
        for k, v in summary.items():
            print(k, v["tool_status"], json.dumps(v["codes"], sort_keys=True), v["parse_error"])
    print("parsed %d samples x %d tools: %d rows" % (len(samples), len(tools), n_rows))
    for t in tools:
        tot = {}
        for k, v in summary.items():
            if k.split("|", 1)[0] == t:
                for code, n in v["codes"].items():
                    tot[code] = tot.get(code, 0) + n
        print("  %-13s %s" % (P.TOOL_COLUMN[t],
                              " ".join("%s=%d" % (c, tot[c]) for c in VOCAB if c in tot)))


def write_wide(path, samples, contig_order, calls):
    n = 0
    states = {}
    with open(path, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, delimiter="\t", lineterminator="\n")
        w.writerow(["sample", "contig_id", "contig_length"] + TOOL_ORDER)
        for s in samples:
            for c, L in contig_order.get(s, []):
                tc = calls.get((s, c), {})
                vals = [tc.get(t, "MISSING") or "MISSING" for t in TOOL_ORDER]
                for v in vals:
                    states[v] = states.get(v, 0) + 1
                w.writerow([s, c, L] + vals)
                n += 1
    print("wide table: %d contigs; cells by state: %s"
          % (n, " ".join("%s=%d" % (v, states[v]) for v in VOCAB if v in states)))


def iter_long_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for f in sorted(files):
                    if f.endswith(".tsv"):
                        yield os.path.join(root, f)
        elif os.path.isfile(p):
            yield p
        else:
            die("not found: %s" % p)


def pivot_long(P, a):
    """Read long tables; write the wide table and/or the long table in the frozen row order."""
    rank = {P.TOOL_COLUMN[t]: i for i, t in enumerate(P.PARSERS)}
    calls = {}
    order = {}
    rows = []
    n_files = 0
    for path in iter_long_files(a.from_long):
        n_files += 1
        with open(path, encoding="utf-8", newline="") as f:
            rd = csv.reader(f, delimiter="	")
            head = next(rd, None)
            if head != HEADER:
                die("unexpected header in %s: %s" % (path, head))
            for row in rd:
                if not row:
                    continue
                if len(row) != len(HEADER):
                    die("row with %d fields in %s" % (len(row), path))
                s, c, L, tool, code = row[0], row[1], row[2], row[3], row[5]
                if tool not in TOOL_ORDER:
                    die("unknown tool %r in %s" % (tool, path))
                if code not in VOCAB:
                    die("state %r outside the seven-state vocabulary in %s" % (code, path))
                if tool in calls.setdefault((s, c), {}):
                    die("%s %s %s appears more than once (last seen in %s)" % (s, c, tool, path))
                calls[(s, c)][tool] = code
                rows.append((rank[tool], s, len(rows), row))
                seen = order.setdefault(s, {})
                if c not in seen:
                    seen[c] = L
    if n_files == 0:
        die("no long tables found")
    print("read %d long table file(s), %d rows" % (n_files, len(rows)))
    if a.assemblies:
        samples = list_samples(a.assemblies, a.fasta_name, a.samples)
        contig_order = {s: list(contigs_of(os.path.join(a.assemblies, s, a.fasta_name)).items())
                        for s in samples}
    else:
        samples = sorted(order)
        if a.samples:
            want = set(x.strip() for x in a.samples.split(",") if x.strip())
            samples = [s for s in samples if s in want]
        contig_order = {s: list(order[s].items()) for s in samples}
    if a.long:
        keep = set(samples)
        rows.sort(key=lambda r: r[:3])    # tools in PARSERS order, samples sorted, rows as read
        with open(a.long, "w", encoding="utf-8", newline="") as fo:
            w = csv.writer(fo, delimiter="	")   # CRLF, as frozen
            w.writerow(HEADER)
            w.writerows(r[3] for r in rows if r[1] in keep)
        print("long table: %d rows" % sum(1 for r in rows if r[1] in keep))
    if a.wide:
        write_wide(a.wide, samples, contig_order, calls)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Run the frozen PlasmidCall panel parser (p19c4-parsers/1.7) on native tool "
                    "outputs, or pivot its long table to the wide table. See docs/PARSING.md.")
    ap.add_argument("--assemblies", help="directory of <sample>/<fasta-name>")
    ap.add_argument("--native", help="directory of <tool>/<sample>/ native outputs")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--receipts",
                   help="directory of <tool>__<sample>.json run receipts (the frozen behaviour)")
    g.add_argument("--status-from-outputs", action="store_true",
                   help="no receipts: a tool counts as run when <native>/<tool>/<sample>/ exists")
    ap.add_argument("--from-long", nargs="+", metavar="PATH",
                    help="read existing long tables (files or per-sample directories) instead of "
                         "native outputs, and write --long and/or --wide from them")
    ap.add_argument("--long", help="write the frozen long table here")
    ap.add_argument("--wide", help="write the wide table (one column per tool) here")
    ap.add_argument("--per-sample-dir", help="write the frozen per-sample files <tool>/<sample>.tsv here")
    ap.add_argument("--summary", help="write a JSON summary here")
    ap.add_argument("--samples", help="comma-separated subset of samples (default: all)")
    ap.add_argument("--tools", help="comma-separated subset of tools (default: all 12); "
                                    "tools left out are MISSING in the wide table")
    ap.add_argument("--fasta-name", default="shortread.fasta",
                    help="assembly file name inside each sample directory (default shortread.fasta)")
    ap.add_argument("--quiet", action="store_true", help="omit the per tool and sample lines")
    a = ap.parse_args(argv)

    if a.from_long:
        if not (a.wide or a.long):
            die("--from-long needs --wide and/or --long")
        if a.native or a.receipts or a.status_from_outputs or a.per_sample_dir or a.tools:
            die("--from-long only reorders and pivots. It takes --long, --wide and, optionally, "
                "--assemblies, --samples and --fasta-name")
        pivot_long(load_frozen_parser(), a)
        return 0
    if not (a.assemblies and a.native):
        die("--assemblies and --native are required (or use --from-long)")
    if a.receipts is None and not a.status_from_outputs:
        die("give --receipts DIR, or --status-from-outputs when the tools were run without receipts")
    if not (a.long or a.wide or a.per_sample_dir):
        die("nothing to write: give --long, --wide and/or --per-sample-dir")
    if not os.path.isdir(a.native):
        die("native directory not found: %s" % a.native)
    if a.receipts is not None and not os.path.isdir(a.receipts):
        die("receipts directory not found: %s" % a.receipts)
    P = load_frozen_parser()
    parse_native(P, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())

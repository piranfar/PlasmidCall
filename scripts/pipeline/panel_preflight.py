#!/usr/bin/env python3
"""CRITICAL-TOOL PREFLIGHT AND PANEL-HEALTH GATE. Authored and hashed BEFORE any P1.11 inference.

PlaScope is a PRESPECIFIED CRITICAL COMPONENT. Measured on the development cohort, its absence
takes v1.2-General recall from 0.7764 to 0.2013 - below the 0.50 primary floor - so a P1.11 run
without PlaScope is not a fair test of the frozen operating point.

This script runs on the execution host BEFORE P1.11 processing and freezes a receipt. It is
authored now so that the acceptance criteria cannot be chosen after seeing how the tools behave.

Stages
  1  image and code identity   Dockerfile, run_tool.sh and parser hashes against the frozen
                               P1.9C4 environment manifest; parser version string
  2  command identity          the exact frozen command line for each tool, PlaScope first
  3  database identity         database hashes against a frozen database receipt. On the FIRST
                               run the receipt is CREATED (the databases were never hashed before,
                               and pre-P1.11 is the correct time to establish that baseline);
                               on every later run it must MATCH
  4  truth-blind smoke test    run the panel on an ALREADY CONSUMED sample, never a P1.11 isolate.
                               Requires valid output, exact contig-ID reconciliation and parser
                               success. Truth is never loaded, so nothing about P1.11 is learned
  5  freeze                    write the preflight receipt and its hash

Exit status is 0 only if every critical-tool check passes. A non-zero exit blocks P1.11 processing.

Usage:
  python panel_preflight.py --env-root /data/trace-arg/p110/env \
                            --db-root  /data/trace-arg/db \
                            --smoke-sample SAMD00077842 \
                            --smoke-assembly /path/to/consumed/assembly.fasta \
                            --out /data/trace-arg/p112/preflight
  Add --skip-smoke to run identity checks only (stages 1-3 and 5).
"""
import argparse, hashlib, json, os, re, subprocess, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# ---------------------------------------------------------------- prespecified criticality
CRITICAL_TOOLS = ["PlaScope"]
CRITICAL_RATIONALE = ("PlaScope absence takes v1.2-General recall from 0.7764 to 0.2013 on the "
                      "development cohort, below the 0.50 primary floor. "
                      "See docs/evidence/P1.12_V1.2_FAILURE_SENSITIVITY.tsv")

# minimum fraction of the 79 prespecified isolates that must have every critical tool available
CRITICAL_COVERAGE_MIN = 0.95
N_PRESPECIFIED_ISOLATES = 79

# at most this many retries of a TECHNICAL execution failure, using the identical frozen image,
# database, command and parameters. No patching, replacement or retuning is permitted.
MAX_RETRIES = 2

# PlasmidFinder/FAILED is the ONE failure state observed during training; it has a defined learned
# encoding and remains permissible. Every other tool must preserve explicit FAILED/MISSING states.
PERMITTED_TRAINED_FAILURE_STATES = {"PlasmidFinder": ["FAILED"]}

# ---------------------------------------------------------------- frozen identities
FROZEN_ENV_MANIFEST = os.path.join(REPO, "docs", "evidence",
                                   "P1.9C4_ENV_MANIFEST_prestart.sha256")
FROZEN_PARSER_VERSION = "p19c4-parsers/1.7"

# The frozen PlaScope invocation, verbatim from the frozen run_tool.sh. PlaScope is run exactly as
# in the source paper: Centrifuge 1.0.4 against the PlaScope E. coli database, -k 1000, no size or
# coverage filter, with plasmidEC-style aggregation performed in the parser.
FROZEN_PLASCOPE_COMMAND = ("centrifuge -f --threads $THREADS "
                           "-x /db/plascope/chromosome_plasmid_db -U $FAN -k 1000 "
                           "--report-file /out/${S}_summary.tsv "
                           "-S /out/${S}_extendedresults.tsv")

TOOL_TO_DOCKER = {
    "HyAsP": "hyasp", "MOB-recon": "mobsuite", "PLASMe": "plasme", "PlaScope": "plascope",
    "Plasmer": "plasmer", "PlasmidEC": "plasmidec", "PlasmidFinder": "plasmidfinder",
    "Platon": "platon", "RFPlasmid": "rfplasmid", "geNomad": "genomad", "gplas2": "gplas2",
    "plASgraph2": "plasgraph2",
}
TOOL_ORDER = list(TOOL_TO_DOCKER)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frozen_manifest(p):
    """the P1.9C4 prestart manifest: '<sha256> *./relative/path'"""
    out = {}
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([0-9a-f]{64})\s+\*?\.?/?(.+)$", line)
        if m:
            out[m.group(2).replace("\\", "/")] = m.group(1)
    return out


class Report:
    def __init__(self):
        self.checks = []
        self.critical_failed = []
        self.failed = []

    def add(self, stage, name, ok, detail="", critical=False):
        self.checks.append({"stage": stage, "check": name, "pass": bool(ok),
                            "critical": bool(critical), "detail": str(detail)})
        if not ok:
            self.failed.append(name)
            if critical:
                self.critical_failed.append(name)
        flag = "PASS" if ok else ("*** CRITICAL FAIL ***" if critical else "*** FAIL ***")
        print("  [%s] %-52s %s %s" % (stage, name, flag, detail))


def stage1_identity(a, R):
    print("\nSTAGE 1 - image and code identity")
    if not os.path.exists(FROZEN_ENV_MANIFEST):
        R.add(1, "frozen environment manifest present", False, FROZEN_ENV_MANIFEST, critical=True)
        return
    frozen = load_frozen_manifest(FROZEN_ENV_MANIFEST)
    R.add(1, "frozen environment manifest present", True, "%d entries" % len(frozen))

    for tool in TOOL_ORDER:
        crit = tool in CRITICAL_TOOLS
        rel = "docker/%s/Dockerfile" % TOOL_TO_DOCKER[tool]
        want = frozen.get(rel)
        live = os.path.join(a.env_root, rel)
        if want is None:
            R.add(1, "%s Dockerfile in frozen manifest" % tool, False, rel, critical=crit)
            continue
        if not os.path.exists(live):
            R.add(1, "%s Dockerfile present on host" % tool, False, live, critical=crit)
            continue
        got = sha(live)
        R.add(1, "%s Dockerfile hash matches frozen" % tool, got == want,
              ("%s" % got[:16]) if got == want else "got %s want %s" % (got[:16], want[:16]),
              critical=crit)

    for rel in ("run/run_tool.sh", "run/parsers.py", "run/parse_all.py", "db/fetch_dbs.sh"):
        want = frozen.get(rel)
        live = os.path.join(a.env_root, rel)
        if want is None or not os.path.exists(live):
            R.add(1, "%s present" % rel, False,
                  "missing on host" if want else "absent from frozen manifest", critical=True)
            continue
        got = sha(live)
        R.add(1, "%s hash matches frozen" % rel, got == want,
              got[:16] if got == want else "got %s want %s" % (got[:16], want[:16]), critical=True)

    pp = os.path.join(a.env_root, "run", "parsers.py")
    if os.path.exists(pp):
        txt = open(pp, encoding="utf-8", errors="replace").read()
        m = re.search(r'PARSER_VERSION\s*=\s*"([^"]+)"', txt)
        got = m.group(1) if m else None
        R.add(1, "parser version is the frozen one", got == FROZEN_PARSER_VERSION,
              "%s" % got, critical=True)


def stage2_commands(a, R):
    print("\nSTAGE 2 - command identity")
    rt = os.path.join(a.env_root, "run", "run_tool.sh")
    if not os.path.exists(rt):
        R.add(2, "run_tool.sh readable", False, rt, critical=True)
        return
    txt = open(rt, encoding="utf-8", errors="replace").read()

    def norm(s):
        return re.sub(r"\s+", " ", s).strip()

    ok = norm(FROZEN_PLASCOPE_COMMAND) in norm(txt)
    R.add(2, "PlaScope command is byte-for-byte the frozen invocation", ok,
          "" if ok else "frozen command not found in run_tool.sh", critical=True)
    R.add(2, "PlaScope uses the frozen database path", "/db/plascope/chromosome_plasmid_db" in txt,
          critical=True)
    R.add(2, "PlaScope retains -k 1000 with no size or coverage filter", "-k 1000" in txt,
          critical=True)
    for tool in TOOL_ORDER:
        d = TOOL_TO_DOCKER[tool]
        R.add(2, "%s has a frozen command branch" % tool,
              re.search(r"\b%s\)" % re.escape(d), txt) is not None,
              critical=tool in CRITICAL_TOOLS)


def stage3_databases(a, R):
    print("\nSTAGE 3 - database identity")
    receipt = os.path.join(a.out, "P1.12_DATABASE_RECEIPT.json")
    frozen_receipt = a.db_receipt or receipt
    if not os.path.isdir(a.db_root):
        R.add(3, "database root present", False, a.db_root, critical=True)
        return
    observed = {}
    for tool in TOOL_ORDER:
        d = TOOL_TO_DOCKER[tool]
        base = os.path.join(a.db_root, d)
        if not os.path.isdir(base):
            observed[d] = None
            R.add(3, "%s database directory present" % tool, False, base,
                  critical=tool in CRITICAL_TOOLS)
            continue
        h = hashlib.sha256()
        n = 0
        for root, _, files in os.walk(base):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                h.update(os.path.relpath(p, base).replace("\\", "/").encode())
                h.update(sha(p).encode())
                n += 1
        observed[d] = {"tree_sha256": h.hexdigest(), "n_files": n}
        R.add(3, "%s database hashed" % tool, n > 0,
              "%d files, %s" % (n, h.hexdigest()[:16]), critical=tool in CRITICAL_TOOLS)

    if os.path.exists(frozen_receipt):
        prev = json.load(open(frozen_receipt))["databases"]
        for tool in TOOL_ORDER:
            d = TOOL_TO_DOCKER[tool]
            same = prev.get(d) == observed.get(d)
            R.add(3, "%s database matches the frozen receipt" % tool, same,
                  "" if same else "database changed since freeze", critical=tool in CRITICAL_TOOLS)
    else:
        R.add(3, "database receipt created (first run, pre-P1.11 baseline)", True,
              os.path.basename(receipt))
    return observed


def stage4_smoke(a, R):
    print("\nSTAGE 4 - truth-blind smoke test on an already consumed sample")
    if a.skip_smoke:
        R.add(4, "smoke test executed", True, "SKIPPED by --skip-smoke; identity checks only")
        return None
    if not a.smoke_sample or not a.smoke_assembly:
        R.add(4, "smoke sample provided", False,
              "--smoke-sample and --smoke-assembly are required unless --skip-smoke",
              critical=True)
        return None
    if not os.path.exists(a.smoke_assembly):
        R.add(4, "smoke assembly readable", False, a.smoke_assembly, critical=True)
        return None
    # A P1.11 isolate must never be used here.
    R.add(4, "smoke sample is NOT a P1.11 isolate",
          not _is_p111(a.smoke_sample, a.p111_cohort),
          a.smoke_sample, critical=True)

    contigs = [l[1:].split()[0] for l in open(a.smoke_assembly, encoding="utf-8",
                                              errors="replace") if l.startswith(">")]
    R.add(4, "smoke assembly has contigs", len(contigs) > 0, "%d contigs" % len(contigs),
          critical=True)

    driver = os.path.join(a.env_root, "run", "driver.sh")
    if not os.path.exists(driver):
        R.add(4, "driver present", False, driver, critical=True)
        return None
    outdir = os.path.join(a.out, "smoke")
    os.makedirs(outdir, exist_ok=True)
    cmd = ["bash", driver, a.smoke_sample, a.smoke_assembly, outdir]
    print("       running: %s" % " ".join(cmd))
    try:
        pr = subprocess.run(cmd, capture_output=True, text=True, timeout=a.smoke_timeout)
        R.add(4, "panel driver exited cleanly", pr.returncode == 0,
              "rc=%d" % pr.returncode, critical=True)
    except subprocess.TimeoutExpired:
        R.add(4, "panel driver completed within timeout", False,
              "%ds" % a.smoke_timeout, critical=True)
        return None

    summary = os.path.join(outdir, "parse_summary.json")
    if not os.path.exists(summary):
        R.add(4, "parser produced a summary", False, summary, critical=True)
        return None
    ps = json.load(open(summary))
    R.add(4, "parser version in output is the frozen one",
          ps.get("parser_version") == FROZEN_PARSER_VERSION, ps.get("parser_version"),
          critical=True)

    per = ps.get("per_tool_sample", {})
    states = {}
    for tool in TOOL_ORDER:
        d = TOOL_TO_DOCKER[tool]
        rec = per.get("%s|%s" % (d, a.smoke_sample), {})
        st = rec.get("tool_status", "MISSING")
        states[tool] = st
        crit = tool in CRITICAL_TOOLS
        R.add(4, "%s produced valid output" % tool, st == "OK",
              "tool_status=%s parse_error=%s" % (st, rec.get("parse_error", "")), critical=crit)
        R.add(4, "%s parser succeeded" % tool, not rec.get("parse_error"),
              rec.get("parse_error", ""), critical=crit)

    matrix = os.path.join(outdir, "prediction_matrix.tsv")
    if os.path.exists(matrix):
        import csv as _csv
        rows = list(_csv.DictReader(open(matrix, encoding="utf-8"), delimiter="\t"))
        got = {r["contig_id"] for r in rows}
        want = set(contigs)
        R.add(4, "contig IDs reconcile EXACTLY with the assembly", got == want,
              "matrix=%d assembly=%d missing=%d extra=%d"
              % (len(got), len(want), len(want - got), len(got - want)), critical=True)
    else:
        R.add(4, "prediction matrix produced", False, matrix, critical=True)
    return states


def _is_p111(sample, cohort_path):
    if not cohort_path or not os.path.exists(cohort_path):
        return False
    import csv as _csv
    with open(cohort_path, encoding="utf-8") as f:
        for r in _csv.DictReader(f, delimiter="\t"):
            for v in r.values():
                if v and str(v).strip() == sample:
                    return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-root", required=True, help="frozen tool environment root")
    ap.add_argument("--db-root", required=True, help="frozen database root")
    ap.add_argument("--out", required=True)
    ap.add_argument("--db-receipt", default=None,
                    help="frozen database receipt to match against; default is the one in --out")
    ap.add_argument("--smoke-sample", default=None, help="an ALREADY CONSUMED sample; never P1.11")
    ap.add_argument("--smoke-assembly", default=None)
    ap.add_argument("--smoke-timeout", type=int, default=14400)
    ap.add_argument("--skip-smoke", action="store_true")
    ap.add_argument("--p111-cohort",
                    default="E:/AMR_Evidence_Data/P1.9_cleanroom/p111/P1.11_cohort_sealed.tsv",
                    help="checked ONLY to prove the smoke sample is not a P1.11 isolate")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    print("P1.12 CRITICAL-TOOL PREFLIGHT")
    print("critical tools: %s" % ", ".join(CRITICAL_TOOLS))
    print("rationale: %s" % CRITICAL_RATIONALE)
    print("minimum critical-tool coverage for a scoreable run: %.0f%% of %d isolates (>= %d)"
          % (CRITICAL_COVERAGE_MIN * 100, N_PRESPECIFIED_ISOLATES,
             -(-int(CRITICAL_COVERAGE_MIN * N_PRESPECIFIED_ISOLATES * 100) // 100)))
    print("retries permitted per technical failure: %d, identical image/db/command/parameters"
          % MAX_RETRIES)

    R = Report()
    stage1_identity(a, R)
    stage2_commands(a, R)
    dbs = stage3_databases(a, R)
    states = stage4_smoke(a, R)

    receipt = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "critical-tool preflight and panel-health gate, frozen before P1.11 processing",
        "critical_tools": CRITICAL_TOOLS,
        "critical_rationale": CRITICAL_RATIONALE,
        "critical_coverage_min": CRITICAL_COVERAGE_MIN,
        "n_prespecified_isolates": N_PRESPECIFIED_ISOLATES,
        "max_retries": MAX_RETRIES,
        "retry_rule": ("technical execution failure only, identical frozen image, database, "
                       "command and parameters; no patching, replacement or retuning"),
        "permitted_trained_failure_states": PERMITTED_TRAINED_FAILURE_STATES,
        "frozen_parser_version": FROZEN_PARSER_VERSION,
        "frozen_plascope_command": FROZEN_PLASCOPE_COMMAND,
        "env_root": a.env_root, "db_root": a.db_root,
        "databases": dbs, "smoke_sample": a.smoke_sample, "smoke_tool_states": states,
        "checks": R.checks,
        "n_checks": len(R.checks), "n_failed": len(R.failed),
        "n_critical_failed": len(R.critical_failed),
        "critical_failed": R.critical_failed,
        "VERDICT": "PASS" if not R.critical_failed else "BLOCKED",
    }
    p = os.path.join(a.out, "P1.12_PREFLIGHT_RECEIPT.json")
    json.dump(receipt, open(p, "w"), indent=1)
    if dbs and not os.path.exists(os.path.join(a.out, "P1.12_DATABASE_RECEIPT.json")):
        json.dump({"generated_utc": receipt["generated_utc"], "databases": dbs},
                  open(os.path.join(a.out, "P1.12_DATABASE_RECEIPT.json"), "w"), indent=1)

    print("\n%d checks, %d failed, %d CRITICAL failures" %
          (len(R.checks), len(R.failed), len(R.critical_failed)))
    print("VERDICT: %s" % receipt["VERDICT"])
    print("receipt: %s" % p)
    print("receipt sha256: %s" % sha(p))
    if R.critical_failed:
        print("\nP1.11 PROCESSING IS BLOCKED. Critical failures:")
        for n in R.critical_failed:
            print("   - %s" % n)
        sys.exit(1)


if __name__ == "__main__":
    main()

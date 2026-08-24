#!/usr/bin/env python3
"""P1.11 PREFLIGHT, v2. Supersedes panel_preflight.py for P1.11 execution verification.

The original scripts/p1_12/panel_preflight.py is PRESERVED UNCHANGED and remains hash-addressable
at edba943f6ad34dc2acac3091b18745c827299182eae500077281ba739840c535. It returned BLOCKED on the
migrated host because of three defects in the CHECKING SCRIPT, not in the environment. See
docs/plans/P1.11_PREFLIGHT_IMPLEMENTATION_CORRECTION.yaml.

  D1  it treated the P1.9C4 PRESTART manifest as the as-executed baseline. That snapshot predates
      the revisions that produced parser 1.7 and matches neither env tree on disk. v2 uses the
      P1.10 AS-EXECUTED manifest, which the migrated host matches 19/19.
  D2  it required an external db/<tool> directory for all 12 tools. Only 6 mount one; the rest
      carry their database inside the frozen image and mount no DBM at all. v2 checks the image ID
      and the retained init/install receipt for those instead.
  D3  it resolved Dockerfiles and fetch_dbs.sh from --env-root. Those live under p19c4/env while
      the runner P1.11 executes lives under p110/env. v2 resolves each artefact from the tree that
      holds it and records the exact source path used.

NOTHING SCIENTIFIC CHANGES HERE. Estimator, coefficients, threshold 0.9285, v1.1 0.9524/0.9605,
tool commands, images, databases, parsers, cohort, truth rules, endpoints and the PlaScope
operational gate are all untouched. This file only verifies.

Every check is a pure function taking explicit inputs so the fixture suite can drive it directly.

Usage:
  python3 panel_preflight_p111_v2.py --volume-root /work \
      --env-manifest <P1.10_ASEXECUTED_ENV_MANIFEST.json> \
      --identity-reference <P1.12_PRIOR_IDENTITY_REFERENCE.json> \
      --derived-receipt <P1.11_DERIVED_RUNNER_RECEIPT.json> \
      --smoke-sample SAMD00077842 --out <dir>
"""
import argparse, hashlib, json, os, re, subprocess, sys, datetime

# ---------------------------------------------------------------- frozen facts
CRITICAL_TOOLS = ["plascope"]
CRITICAL_COVERAGE_MIN = 0.95
N_PRESPECIFIED_ISOLATES = 79
MAX_RETRIES = 2
FROZEN_PARSER_VERSION = "p19c4-parsers/1.7"
EXPECTED_CALL_ROWS = 3636          # P1.10 rows for the smoke sample
CMD_BLOCK_HASH = "44f8d17d0b406fccae57423c5111cf55"   # sha256[:32] of the 13 path-normalised CMD strings

# 6 tools mount an external database; the rest carry theirs inside the frozen image.
EXTERNAL_DB_TOOLS = {"platon", "plascope", "genomad", "plasme", "plasmer", "hyasp"}
EMBEDDED_DB_TOOLS = {"mobsuite", "plasmidfinder", "rfplasmid", "plasgraph2", "gplas2",
                     "plasmidec", "amrfinder"}
# retained initialisation / install receipts proving the embedded database was built into the image
EMBEDDED_DB_RECEIPTS = {
    "mobsuite": ["mobsuite__mob_init.log"],
    "plasmidfinder": ["plasmidfinder__pf_db_install.log", "plasmidfinder__plasmidfinder_db.commit"],
    "rfplasmid": ["rfplasmid__rfplasmid_init.log"],
    "amrfinder": ["amrfinder__amrfinder_db_version.txt", "amrfinder__amrfinder_update.log"],
    "plasgraph2": ["plasgraph2__plasgraph2.commit"],
    "gplas2": ["gplas2__gplas2.commit"],
    "plasmidec": ["plasmidec__plasmidec.commit"],
}
TOOL_TO_IMAGE = {
    "hyasp": "p19c4-hyasp:1.0", "mobsuite": "p19c4-mobsuite:1.0", "plasme": "p19c4-plasme:1.0",
    "plascope": "p19c4-plascope:1.0", "plasmer": "nekokoe/plasmer:23.04.20",
    "plasmidec": "p19c4-plasmidec:1.0", "plasmidfinder": "p19c4-plasmidfinder:1.0",
    "platon": "p19c4-platon:1.0", "rfplasmid": "p19c4-rfplasmid:1.0",
    "genomad": "p19c4-genomad:1.0", "gplas2": "p19c4-gplas2:1.0",
    "plasgraph2": "p19c4-plasgraph2:1.0", "amrfinder": "p19c4-amrfinder:1.0",
}
DB_TO_TOOL = {
    "plascope_chromosome_plasmid_db.tar.gz": "plascope",
    "platon_db_v1.5.0.tar.gz": "platon", "genomad_db_v1.5.tar.gz": "genomad",
    "plasme_DB.zip": "plasme", "hyasp_ncbi_database_genes.fasta.bz2": "hyasp",
    "hyasp_plasmids.csv": "hyasp", "hyasp_ncbi_blacklist.txt": "hyasp",
    "plasmerMainDB.tar.xz": "plasmer", "customizedKraken2DB.tar.xz": "plasmer",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha_sorted_lines(p):
    with open(p, "rb") as f:
        lines = f.read().splitlines()
    h = hashlib.sha256()
    for ln in sorted(lines):
        h.update(ln); h.update(b"\n")
    return h.hexdigest()


def cmd_block_hash(run_tool_path, tag):
    """hash of the 13 CMD= scientific strings with the pXXX path token normalised away"""
    txt = open(run_tool_path, encoding="utf-8", errors="replace").read()
    cmds = re.findall(r'CMD="(.*)"', txt)
    norm = [re.sub(r"/p\d{3,4}", "/pXXX", c) for c in cmds]
    h = hashlib.sha256("\n".join(norm).encode()).hexdigest()
    return len(cmds), h[:32]


class Report:
    def __init__(self):
        self.checks = []; self.failed = []; self.critical = []

    def add(self, stage, name, state, detail="", critical=False):
        self.checks.append({"stage": stage, "check": name, "state": state,
                            "critical": bool(critical), "detail": str(detail)})
        if state != "PASS":
            self.failed.append(name)
            if critical:
                self.critical.append(name)
        flag = {"PASS": "PASS"}.get(state, "*** %s ***" % state)
        print("  [%s] %-58s %-14s %s" % (stage, name, flag, detail))
        return state == "PASS"


# ================================================================= pure checks (fixture-drivable)

def check_images(live_ids, want_ids, rep):
    """live_ids/want_ids: {tag: 16-hex}. Critical for the critical tools."""
    allok = True
    for tag, wid in sorted(want_ids.items()):
        tool = next((t for t, im in TOOL_TO_IMAGE.items() if im == tag), None)
        crit = tool in CRITICAL_TOOLS
        got = live_ids.get(tag)
        if got is None:
            allok &= rep.add("A", "%s present" % tag, "FAIL", "image absent", critical=crit)
        elif got == wid:
            rep.add("A", "%s matches as-executed id" % tag, "PASS", got, critical=crit)
        else:
            allok &= rep.add("A", "%s matches as-executed id" % tag, "FAIL",
                             "live %s want %s" % (got, wid), critical=crit)
    n = len(want_ids)
    allok &= rep.add("A", "all %d as-executed images present and matching" % n,
                     "PASS" if allok else "FAIL", "%d checked" % n, critical=True)
    return allok


def check_external_dbs(db_root, archives, rep):
    """External DBs: the 6 mounting tools need a directory; 9 archives need matching sha256."""
    allok = True
    for tool in sorted(EXTERNAL_DB_TOOLS):
        d = os.path.join(db_root, tool)
        crit = tool in CRITICAL_TOOLS
        allok &= rep.add("B", "%s external database directory present" % tool,
                         "PASS" if os.path.isdir(d) else "FAIL", d, critical=crit)
    for name, meta in sorted(archives.items()):
        tool = DB_TO_TOOL.get(name, "")
        crit = tool in CRITICAL_TOOLS
        p = os.path.join(db_root, name)
        if not os.path.exists(p):
            allok &= rep.add("B", "%s retained archive present" % name, "FAIL",
                             "not retained", critical=crit)
            continue
        got = sha(p)
        ok = got == meta["sha256"]
        allok &= rep.add("B", "%s sha256 matches prior record" % name, "PASS" if ok else "FAIL",
                         got[:16] if ok else "got %s want %s" % (got[:12], meta["sha256"][:12]),
                         critical=crit)
    return allok


def check_embedded_dbs(locks_dir, live_ids, rep):
    """Embedded DBs: no external directory is required. Verify image + retained init receipt."""
    allok = True
    for tool in sorted(EMBEDDED_DB_TOOLS):
        tag = TOOL_TO_IMAGE[tool]
        has_img = tag in live_ids
        allok &= rep.add("C", "%s image present (database embedded in image)" % tool,
                         "PASS" if has_img else "FAIL", tag)
        for rc in EMBEDDED_DB_RECEIPTS.get(tool, []):
            p = os.path.join(locks_dir, rc)
            allok &= rep.add("C", "%s retained receipt %s" % (tool, rc),
                             "PASS" if os.path.exists(p) else "FAIL", "")
        d = os.path.join(os.path.dirname(locks_dir.rstrip("/")), "db", tool)
        rep.add("C", "%s correctly has NO external database directory" % tool,
                "PASS" if not os.path.isdir(d) else "NOTE",
                "embedded-database tool; an external dir is not required")
    return allok


def check_env_files(env_root, manifest, rep):
    """19/19 against the P1.10 AS-EXECUTED manifest. Never the prestart snapshot."""
    files = manifest["files"]
    nok = nbad = nmiss = 0
    CRIT = {"run/run_tool.sh", "run/parsers.py", "run/parse_all.py", "run/driver.sh"}
    for rel, want in sorted(files.items()):
        live = os.path.join(env_root, rel)
        crit = rel in CRIT
        if not os.path.exists(live):
            nmiss += 1
            if crit:
                rep.add("D", "%s present" % rel, "FAIL", "absent", critical=True)
            continue
        got = sha(live)
        if got == want:
            nok += 1
            if crit:
                rep.add("D", "%s matches P1.10 as-executed" % rel, "PASS", got[:16], critical=True)
        else:
            nbad += 1
            rep.add("D", "%s matches P1.10 as-executed" % rel, "FAIL",
                    "got %s want %s" % (got[:12], want[:12]), critical=crit)
    ok = (nbad == 0 and nmiss == 0)
    rep.add("D", "P1.10 as-executed environment identical", "PASS" if ok else "FAIL",
            "%d/%d match, %d differ, %d missing" % (nok, len(files), nbad, nmiss), critical=True)
    return ok


def check_derived(derived_receipt, rep):
    """Derived P1.11 runner/parser: hashes match the frozen receipt AND commands are unchanged."""
    allok = True
    for key, meta in sorted(derived_receipt["derived"].items()):
        p = meta["path"]
        if not os.path.exists(p):
            allok &= rep.add("E", "derived %s present" % key, "FAIL", p, critical=True)
            continue
        got = sha(p)
        ok = got == meta["sha256"]
        allok &= rep.add("E", "derived %s matches frozen receipt" % key,
                         "PASS" if ok else "FAIL",
                         got[:16] if ok else "got %s want %s" % (got[:12], meta["sha256"][:12]),
                         critical=True)
    rt = derived_receipt["derived"].get("run_tool.sh", {}).get("path")
    if rt and os.path.exists(rt):
        n, h = cmd_block_hash(rt, "derived")
        allok &= rep.add("E", "all 13 scientific CMD strings byte-identical",
                         "PASS" if (n == 13 and h == CMD_BLOCK_HASH) else "FAIL",
                         "%d commands, hash %s" % (n, h), critical=True)
    pv = derived_receipt.get("parser_version")
    allok &= rep.add("E", "parser version unchanged",
                     "PASS" if pv == FROZEN_PARSER_VERSION else "FAIL", str(pv), critical=True)
    allok &= rep.add("E", "classification vocabulary unchanged",
                     "PASS" if derived_receipt.get("vocabulary_unchanged") else "FAIL",
                     ", ".join(derived_receipt.get("vocabulary", [])), critical=True)
    return allok


def check_replay(ref_dir, new_dir, sample, rep):
    """summary byte-compared; per-read output compared as a sorted record set (thread order varies)"""
    allok = True
    pairs = [("%s_summary.tsv" % sample, "ordered"),
             ("%s_extendedresults.tsv" % sample, "unordered")]
    for fn, kind in pairs:
        a = os.path.join(ref_dir, fn); b = os.path.join(new_dir, fn)
        if not (os.path.exists(a) and os.path.exists(b)):
            allok &= rep.add("F", "replay %s present" % fn, "FAIL", "missing", critical=True)
            continue
        if kind == "ordered":
            h1, h2 = sha(a), sha(b); label = "byte-identical to P1.10"
        else:
            h1, h2 = sha_sorted_lines(a), sha_sorted_lines(b)
            label = "record-set identical to P1.10 (order-insensitive)"
        ok = h1 == h2
        allok &= rep.add("F", "PlaScope replay %s %s" % (fn, label), "PASS" if ok else "FAIL",
                         h1[:16] if ok else "ref %s vs new %s" % (h1[:12], h2[:12]), critical=True)
    return allok


def check_calls(old_tsv, new_tsv, sample, rep, expected=EXPECTED_CALL_ROWS):
    import csv as _csv

    def load(p):
        d = {}
        with open(p, encoding="utf-8") as f:
            for r in _csv.DictReader(f, delimiter="\t"):
                if r.get("sample") != sample:
                    continue
                d[(r.get("tool"), r.get("contig_id"))] = r.get("call") or r.get("code")
        return d
    if not (os.path.exists(old_tsv) and os.path.exists(new_tsv)):
        return rep.add("H", "call tables present", "FAIL", "missing", critical=True)
    o, n = load(old_tsv), load(new_tsv)
    keys = set(o) | set(n)
    diff = [k for k in keys if o.get(k) != n.get(k)]
    ok = (len(diff) == 0 and len(keys) == expected)
    return rep.add("H", "parsed calls reproduce P1.10 exactly", "PASS" if ok else "FAIL",
                   "%d/%d identical, %d differ (expected %d rows)"
                   % (len(keys) - len(diff), len(keys), len(diff), expected), critical=True)


# ================================================================= main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--volume-root", required=True)
    ap.add_argument("--env-manifest", required=True)
    ap.add_argument("--identity-reference", required=True)
    ap.add_argument("--derived-receipt", required=True)
    ap.add_argument("--smoke-sample", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-smoke", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    V = a.volume_root.rstrip("/")

    # D3: resolve each artefact from the tree that actually holds it, and record the path used.
    paths = {
        "p110_env": os.path.join(V, "p110", "env"),
        "p19c4_env": os.path.join(V, "p19c4", "env"),
        "locks": os.path.join(V, "p19c4", "env", "locks"),
        "db_root": os.path.join(V, "p19c4", "db"),
        "p110_native": os.path.join(V, "p110", "inference", "native"),
        "p110_calls": os.path.join(V, "p110", "inference", "P1.10_predictions_normalised.tsv"),
        "p112_calls": os.path.join(V, "p112", "inference", "P1.10_predictions_normalised.tsv"),
        "p112_native": os.path.join(V, "p112", "inference", "native"),
    }
    rep = Report()
    print("P1.11 PREFLIGHT v2 - supersedes panel_preflight.py (edba943f...)")
    print("critical tools: %s ; gate >= %d of %d isolates\n"
          % (", ".join(CRITICAL_TOOLS),
             -(-int(CRITICAL_COVERAGE_MIN * N_PRESPECIFIED_ISOLATES * 100) // 100),
             N_PRESPECIFIED_ISOLATES))

    print("0. RESOLVED PATHS (D3 correction: recorded, not assumed)")
    for k, v in sorted(paths.items()):
        rep.add("0", "path %s" % k, "PASS" if os.path.exists(v) else "FAIL", v,
                critical=k in ("p110_env", "p19c4_env", "db_root", "locks"))

    ref = json.load(open(a.identity_reference))
    want_ids = ref["sources"]["as_executed_image_gate"]["images"]
    out = subprocess.run(["docker", "images", "--no-trunc",
                          "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"],
                         capture_output=True, text=True, timeout=180).stdout
    live_ids = {}
    for line in out.strip().split("\n"):
        p = line.split()
        if len(p) == 2 and p[1].startswith("sha256:"):
            live_ids[p[0]] = p[1][7:23]

    print("\nA. IMAGE IDENTITY (13 as-executed IDs)")
    check_images(live_ids, want_ids, rep)

    print("\nB. EXTERNAL DATABASES (D2: only the 6 tools that mount one)")
    check_external_dbs(paths["db_root"], ref["sources"]["database_archives"]["archives"], rep)

    print("\nC. EMBEDDED DATABASES (D2: image + retained init receipt, no external dir required)")
    check_embedded_dbs(paths["locks"], live_ids, rep)

    print("\nD. ENVIRONMENT IDENTITY (D1: P1.10 AS-EXECUTED baseline)")
    check_env_files(paths["p110_env"], json.load(open(a.env_manifest)), rep)

    print("\nE. DERIVED P1.11 RUNNER AND PARSER")
    check_derived(json.load(open(a.derived_receipt)), rep)

    print("\nF. PLASCOPE FUNCTIONAL REPLAY")
    check_replay(os.path.join(paths["p110_native"], "plascope", a.smoke_sample),
                 os.path.join(paths["p112_native"], "plascope", a.smoke_sample),
                 a.smoke_sample, rep)

    print("\nG. TRUTH-BLIND SMOKE TEST (consumed sample, 13 tools)")
    st = os.path.join(V, "p112", "inference", "state")
    tools = sorted(EXTERNAL_DB_TOOLS | EMBEDDED_DB_TOOLS)
    ndone = sum(1 for t in tools if os.path.exists(os.path.join(st, "%s__%s.done" % (t, a.smoke_sample))))
    rep.add("G", "13/13 tools completed on the consumed sample",
            "PASS" if ndone == 13 else "FAIL", "%d of 13 done" % ndone, critical=True)

    print("\nH. CALL REPRODUCTION")
    check_calls(paths["p110_calls"], paths["p112_calls"], a.smoke_sample, rep)

    receipt = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "implementation": "panel_preflight_p111_v2.py",
        "supersedes": {"file": "scripts/p1_12/panel_preflight.py",
                       "sha256": "edba943f6ad34dc2acac3091b18745c827299182eae500077281ba739840c535",
                       "reason": "three execution-verification defects; see "
                                 "docs/plans/P1.11_PREFLIGHT_IMPLEMENTATION_CORRECTION.yaml"},
        "resolved_paths": paths,
        "external_db_tools": sorted(EXTERNAL_DB_TOOLS),
        "embedded_db_tools": sorted(EMBEDDED_DB_TOOLS),
        "critical_tools": CRITICAL_TOOLS,
        "critical_coverage_min": CRITICAL_COVERAGE_MIN,
        "n_prespecified_isolates": N_PRESPECIFIED_ISOLATES,
        "max_retries": MAX_RETRIES,
        "scientific_parameters_changed": False,
        "n_checks": len(rep.checks), "n_failed": len(rep.failed),
        "n_critical_failed": len(rep.critical), "critical_failures": rep.critical,
        "checks": rep.checks,
        "VERDICT": "PASS" if not rep.critical else "BLOCKED",
    }
    p = os.path.join(a.out, "P1.11_PREFLIGHT_v2_RECEIPT.json")
    json.dump(receipt, open(p, "w"), indent=1)
    print("\n%d checks, %d not-PASS, %d CRITICAL" % (len(rep.checks), len(rep.failed), len(rep.critical)))
    print("VERDICT: %s" % receipt["VERDICT"])
    print("receipt: %s" % p)
    print("receipt sha256: %s" % sha(p))
    if rep.critical:
        sys.exit(1)


if __name__ == "__main__":
    main()

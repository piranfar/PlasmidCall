#!/usr/bin/env python3
"""Verify the LIVE execution host against the PRIOR-IDENTITY REFERENCE.

Runs on the OCI host, before the panel preflight. Additive to panel_preflight.py, which stays
byte-identical to the frozen commit; this script carries the checks that must compare against
records from earlier runs rather than against a baseline generated today.

  A  image identity      live `docker images` IDs vs the as-executed P1.10 stage-1 gate (13 images)
  B  database identity   retained source archives vs the P1.9C4 DB_RECEIPTS sha256.
  D  functional replay   the decisive check when an archive was not retained. The frozen tool is
                         re-run on a RETAINED, HASH-RECORDED P1.10 input and its output compared
                         byte-for-byte against the retained P1.10 output. Centrifuge is
                         deterministic given the same index and input, so a byte-identical result
                         proves the database index is the one P1.10 actually used. This is
                         stronger evidence of PRIOR identity than re-hashing an extracted tree,
                         which would only be a new baseline.

  A missing source archive is NOT the same as missing prior evidence. The evidence chain is
  reported explicitly per database:
     archive_sha256      direct, strongest
     functional_replay   direct tie to the P1.10 run, independent of archive retention
     extraction_record   fetch_dbs.sh pins the source md5 and the deterministic extraction
     acquisition_receipt DB_RECEIPTS.tsv records md5 expected == observed at download
  C  invocation identity live run_tool.sh command branches vs the frozen per-tool .cmd receipts

Exit non-zero if any CRITICAL check fails. PlaScope is the prespecified critical tool.

Usage:
  python verify_prior_identity.py --reference P1.12_PRIOR_IDENTITY_REFERENCE.json \
                                  --db-root /data/trace-arg/p19c4/db \
                                  --run-tool /data/trace-arg/p110/env/run/run_tool.sh \
                                  --out /data/trace-arg/p112/preflight
"""
import argparse, hashlib, json, os, re, subprocess, sys, datetime

CRITICAL_TOOLS = ["plascope"]

# Retained P1.10 native outputs used for the functional replay proof. Centrifuge writes a stable
# TSV given the same index and input; the summary file is compared, and the extended results are
# compared when present.
# `ordered` files are byte-compared. `unordered` files are compared as a SORTED MULTISET of lines,
# because centrifuge with --threads 8 emits per-read records in completion order, which varies
# between runs even with an identical index and input. Byte-comparing those would flag a false
# mismatch; comparing the record set still proves the index is identical, since any real database
# difference changes which records are produced, not merely their order.
REPLAY = {
    "plascope": {
        "input": "native/plascope/{s}/input.fasta",
        "ordered": ["native/plascope/{s}/{s}_summary.tsv"],
        "unordered": ["native/plascope/{s}/{s}_extendedresults.tsv"],
    },
}
TOOL_TO_IMAGE = {
    "hyasp": "p19c4-hyasp:1.0", "mobsuite": "p19c4-mobsuite:1.0", "plasme": "p19c4-plasme:1.0",
    "plascope": "p19c4-plascope:1.0", "plasmer": "nekokoe/plasmer:23.04.20",
    "plasmidec": "p19c4-plasmidec:1.0", "plasmidfinder": "p19c4-plasmidfinder:1.0",
    "platon": "p19c4-platon:1.0", "rfplasmid": "p19c4-rfplasmid:1.0",
    "genomad": "p19c4-genomad:1.0", "gplas2": "p19c4-gplas2:1.0",
    "plasgraph2": "p19c4-plasgraph2:1.0", "amrfinder": "p19c4-amrfinder:1.0",
}
# database archive -> the tool that consumes it
DB_TO_TOOL = {
    "plascope_chromosome_plasmid_db.tar.gz": "plascope",
    "platon_db_v1.5.0.tar.gz": "platon",
    "genomad_db_v1.5.tar.gz": "genomad",
    "plasme_DB.zip": "plasme",
    "hyasp_ncbi_database_genes.fasta.bz2": "hyasp",
    "hyasp_plasmids.csv": "hyasp",
    "hyasp_ncbi_blacklist.txt": "hyasp",
    "plasmerMainDB.tar.xz": "plasmer",
    "customizedKraken2DB.tar.xz": "plasmer",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha_sorted_lines(p):
    """hash of the sorted line multiset - order-insensitive, content-sensitive"""
    with open(p, "rb") as f:
        lines = f.read().splitlines()
    h = hashlib.sha256()
    for ln in sorted(lines):
        h.update(ln); h.update(b"\n")
    return h.hexdigest()


class R:
    def __init__(self):
        self.checks = []
        self.crit = []
        self.fail = []

    def add(self, stage, name, state, detail="", critical=False):
        """state: PASS | FAIL | NO_PRIOR_RECORD | NO_PRIOR_ARCHIVE_RETAINED"""
        self.checks.append({"stage": stage, "check": name, "state": state,
                            "critical": bool(critical), "detail": str(detail)})
        if state != "PASS":
            self.fail.append(name)
            if critical and state == "FAIL":
                self.crit.append(name)
        print("  [%s] %-56s %-26s %s" % (stage, name, state, detail))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--db-root", required=True)
    ap.add_argument("--archive-root", default=None,
                    help="where the downloaded source archives were kept, if retained")
    ap.add_argument("--run-tool", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--env-manifest", default=None,
                    help="P1.10_ASEXECUTED_ENV_MANIFEST.json - the correct baseline. The P1.9C4 "
                         "ENV_MANIFEST_prestart.sha256 is a PRESTART snapshot and predates the "
                         "revisions that produced parser 1.7, so it must NOT be used here.")
    ap.add_argument("--p110-native", default=None,
                    help="root holding the retained P1.10 native outputs (the dir containing "
                         "native/<tool>/<sample>/), enabling the functional replay proof")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ref = json.load(open(a.reference))
    rep = R()

    print("VERIFY LIVE HOST AGAINST PRIOR-IDENTITY REFERENCE")
    print("reference generated %s" % ref["generated_utc"])
    print("critical tools: %s\n" % ", ".join(CRITICAL_TOOLS))

    # ------------------------------------------------------------ A. image identity
    print("A. IMAGE IDENTITY  (vs the as-executed P1.10 stage-1 gate)")
    want = ref["sources"]["as_executed_image_gate"]["images"]
    try:
        out = subprocess.run(["docker", "images", "--no-trunc",
                              "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception as e:
        rep.add("A", "docker images readable", "FAIL", str(e)[:80], critical=True)
        out = ""
    live = {}
    for line in out.strip().split("\n"):
        p = line.split()
        if len(p) == 2 and p[1].startswith("sha256:"):
            live[p[0]] = p[1][7:23]
    for tag, wid in sorted(want.items()):
        tool = next((t for t, im in TOOL_TO_IMAGE.items() if im == tag), None)
        crit = tool in CRITICAL_TOOLS
        got = live.get(tag)
        if got is None:
            rep.add("A", "%s present on host" % tag, "FAIL", "image absent", critical=crit)
        elif got == wid:
            rep.add("A", "%s matches as-executed id" % tag, "PASS", got, critical=crit)
        else:
            rep.add("A", "%s matches as-executed id" % tag, "FAIL",
                    "live %s want %s" % (got, wid), critical=crit)

    # ------------------------------------------------------------ B. database identity
    print("\nB. DATABASE IDENTITY  (vs P1.9C4 DB_RECEIPTS sha256)")
    arcs = ref["sources"]["database_archives"]["archives"]
    roots = [r for r in (a.archive_root, a.db_root, os.path.join(a.db_root, "archives"),
                         os.path.dirname(a.db_root.rstrip("/"))) if r]
    for name, meta in sorted(arcs.items()):
        tool = DB_TO_TOOL.get(name, "")
        crit = tool in CRITICAL_TOOLS
        found = None
        for root in roots:
            cand = os.path.join(root, name)
            if os.path.exists(cand):
                found = cand
                break
        if found is None:
            # The archive was removed after extraction. Hashing the extracted tree now would
            # produce a NEW baseline, which is not evidence of prior identity. Say so plainly.
            rep.add("B", "%s prior sha256 verifiable" % name, "NO_PRIOR_ARCHIVE_RETAINED",
                    "archive not retained; extracted tree cannot prove prior identity",
                    critical=crit)
            continue
        if os.path.getsize(found) != meta["bytes"]:
            rep.add("B", "%s size matches prior record" % name, "FAIL",
                    "%d vs %d" % (os.path.getsize(found), meta["bytes"]), critical=crit)
            continue
        got = sha(found)
        rep.add("B", "%s sha256 matches prior record" % name,
                "PASS" if got == meta["sha256"] else "FAIL",
                got[:16] if got == meta["sha256"] else "got %s want %s"
                % (got[:16], meta["sha256"][:16]), critical=crit)

    # ------------------------------------------------------------ C. invocation identity
    # Verified by DIRECT FILE HASH against the P1.10 as-executed environment, not by token
    # matching. An earlier version compared a handful of tokens extracted from the frozen .cmd
    # receipts; that was fragile for tools whose command is mostly shell variables (mob_recon -i
    # $FA -o /out/mob -n $THREADS leaves almost nothing distinctive once run-specific parts are
    # stripped) and produced false mismatches. If run_tool.sh and the parsers are byte-identical
    # to what P1.10 executed, every command they generate is identical by construction.
    print("\nC. INVOCATION IDENTITY  (direct hash vs the P1.10 AS-EXECUTED environment)")
    if not a.env_manifest or not os.path.exists(a.env_manifest):
        rep.add("C", "P1.10 as-executed env manifest supplied", "NO_PRIOR_RECORD",
                "pass --env-manifest", critical=True)
    else:
        em = json.load(open(a.env_manifest))
        rep.add("C", "env manifest loaded", "PASS",
                "%d files, %s" % (em["n_files"], em["source"][:40]))
        envroot = os.path.dirname(os.path.dirname(os.path.abspath(a.run_tool)))
        CRIT_FILES = {"run/run_tool.sh", "run/parsers.py", "run/parse_all.py", "run/driver.sh"}
        nok = nbad = nmiss = 0
        for rel, want in sorted(em["files"].items()):
            live = os.path.join(envroot, rel)
            crit = rel in CRIT_FILES
            if not os.path.exists(live):
                nmiss += 1
                if crit:
                    rep.add("C", "%s present" % rel, "FAIL", "absent on host", critical=True)
                continue
            got = sha(live)
            if got == want:
                nok += 1
                if crit:
                    rep.add("C", "%s matches P1.10 as-executed" % rel, "PASS", got[:16],
                            critical=True)
            else:
                nbad += 1
                rep.add("C", "%s matches P1.10 as-executed" % rel, "FAIL",
                        "got %s want %s" % (got[:12], want[:12]), critical=crit)
        rep.add("C", "whole env tree identical to P1.10 as-executed",
                "PASS" if (nbad == 0 and nmiss == 0) else "FAIL",
                "%d match, %d differ, %d missing" % (nok, nbad, nmiss), critical=True)

        pp = os.path.join(envroot, "run", "parsers.py")
        if os.path.exists(pp):
            txt = open(pp, encoding="utf-8", errors="replace").read()
            m = re.search(r'PARSER_VERSION\s*=\s*"([^"]+)"', txt)
            got = m.group(1) if m else None
            rep.add("C", "parser version is the frozen one", "PASS" if got == "p19c4-parsers/1.7"
                    else "FAIL", str(got), critical=True)

    # PlaScope-specific invariants, kept as an explicit belt-and-braces check
    if os.path.exists(a.run_tool):
        txt = re.sub(r"\s+", " ", open(a.run_tool, encoding="utf-8", errors="replace").read())
        for tok in ("/db/plascope/chromosome_plasmid_db", "-k 1000", "centrifuge -f"):
            rep.add("C", "PlaScope frozen token %r" % tok, "PASS" if tok in txt else "FAIL",
                    critical=True)

    # ------------------------------------------------------------ D. functional replay
    print("\nD. FUNCTIONAL REPLAY  (frozen tool re-run on a retained P1.10 input)")
    replay_results = []
    if not a.p110_native or not os.path.isdir(a.p110_native):
        rep.add("D", "P1.10 native outputs available for replay", "NO_PRIOR_RECORD",
                "pass --p110-native to enable the replay proof", critical=False)
    else:
        import shutil
        for tool, spec in REPLAY.items():
            crit = tool in CRITICAL_TOOLS
            samples = sorted(os.listdir(os.path.join(a.p110_native, "native", tool))) \
                if os.path.isdir(os.path.join(a.p110_native, "native", tool)) else []
            if not samples:
                rep.add("D", "%s retained P1.10 outputs" % tool, "NO_PRIOR_RECORD",
                        "no retained outputs", critical=crit)
                continue
            smp = samples[0]
            inp = os.path.join(a.p110_native, spec["input"].format(s=smp))
            if not os.path.exists(inp):
                rep.add("D", "%s replay input present" % tool, "NO_PRIOR_RECORD", inp,
                        critical=crit)
                continue
            work = os.path.join(a.out, "replay", tool, smp)
            os.makedirs(work, exist_ok=True)
            os.chmod(work, 0o777)
            shutil.copy2(inp, os.path.join(work, "input.fasta"))
            img = TOOL_TO_IMAGE[tool]
            cmd = ("centrifuge -f --threads 8 -x /db/plascope/chromosome_plasmid_db "
                   "-U /out/input.fasta -k 1000 --report-file /out/%s_summary.tsv "
                   "-S /out/%s_extendedresults.tsv" % (smp, smp))
            dk = ["docker", "run", "--rm", "--name", "p112_replay_%s" % tool,
                  "--memory=24g", "--cpus=8",
                  "-v", "%s:/db:ro" % a.db_root, "-v", "%s:/out" % work,
                  img, "bash", "-c", cmd]
            try:
                pr = subprocess.run(dk, capture_output=True, text=True, timeout=3600)
                rcok = pr.returncode == 0
            except Exception as e:
                rcok = False
                pr = None
            if not rcok:
                rep.add("D", "%s replay executed" % tool, "FAIL",
                        (pr.stderr[-120:] if pr else "exception"), critical=crit)
                continue
            allsame = True
            for kind in ("ordered", "unordered"):
                for tmpl in spec.get(kind, []):
                    ref = os.path.join(a.p110_native, tmpl.format(s=smp))
                    new = os.path.join(work, os.path.basename(tmpl.format(s=smp)))
                    nm = os.path.basename(new)
                    if not os.path.exists(ref) or not os.path.exists(new):
                        allsame = False
                        rep.add("D", "%s replay output %s present" % (tool, nm),
                                "FAIL", "missing", critical=crit)
                        continue
                    if kind == "ordered":
                        h1, h2 = sha(ref), sha(new)
                        label = "byte-identical to P1.10"
                    else:
                        h1, h2 = sha_sorted_lines(ref), sha_sorted_lines(new)
                        label = "record-set identical to P1.10 (order-insensitive)"
                    same = h1 == h2
                    allsame &= same
                    rep.add("D", "%s replay %s %s" % (tool, nm, label),
                            "PASS" if same else "FAIL",
                            h1[:16] if same else "p110 %s vs replay %s" % (h1[:12], h2[:12]),
                            critical=crit)
            replay_results.append({"tool": tool, "sample": smp, "identical": allsame})
            if allsame:
                print("      -> %s database index is byte-for-byte the one P1.10 used" % tool)

    receipt = {
        "functional_replay": replay_results,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "reference_file": a.reference, "reference_sha256": sha(a.reference),
        "critical_tools": CRITICAL_TOOLS,
        "n_checks": len(rep.checks), "n_not_pass": len(rep.fail),
        "n_critical_fail": len(rep.crit), "critical_failures": rep.crit,
        "checks": rep.checks,
        "semantics": {
            "PASS": "verified against a record that predates this run",
            "FAIL": "contradicts the prior record",
            "NO_PRIOR_RECORD": "no prior evidence of this kind exists to compare against",
            "NO_PRIOR_ARCHIVE_RETAINED": ("the source archive was not kept. This is NOT the same "
                                          "as missing prior evidence: identity may still be "
                                          "established by the stage-D functional replay, which "
                                          "ties the live database directly to the P1.10 run. A "
                                          "tree hash generated now would be a new baseline and is "
                                          "never presented as proof of prior identity")},
        "evidence_chain_note": ("For each database the strongest available evidence is used: a "
                                "retained source archive hash (B), else a functional replay "
                                "against retained P1.10 outputs (D). The critical PlaScope "
                                "database must be established by at least one of these."),
        "VERDICT": "PASS" if not rep.crit else "BLOCKED"}
    crit_established = any(
        c["state"] == "PASS" and c["critical"] and c["stage"] in ("B", "D")
        for c in rep.checks)
    receipt["critical_database_identity_established"] = crit_established
    if not crit_established:
        receipt["VERDICT"] = "BLOCKED"
        print("\n*** CRITICAL: PlaScope database identity could not be established by either a "
              "retained archive hash or a functional replay. ***")
    p = os.path.join(a.out, "P1.12_PRIOR_IDENTITY_VERIFICATION.json")
    json.dump(receipt, open(p, "w"), indent=1)
    print("\n%d checks, %d not-PASS, %d CRITICAL failures"
          % (len(rep.checks), len(rep.fail), len(rep.crit)))
    print("VERDICT: %s" % receipt["VERDICT"])
    print("receipt: %s\nsha256: %s" % (p, sha(p)))
    if rep.crit or not receipt["critical_database_identity_established"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

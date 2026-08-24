#!/usr/bin/env python3
"""Fixture suite for panel_preflight_p111_v2.py.

Drives every check function with synthetic inputs and asserts it produces the RIGHT verdict for
both the good case and the failure case. A checker that cannot fail is not a check, so each
scenario has a negative twin.

Required coverage:
   1  all external-database tools present
   2  one required external database missing
   3  embedded-database tools with no external directory
   4  image-ID mismatch
   5  runner-command mismatch
   6  parser mismatch
   7  wrong environment path
   8  PlaScope replay match
   9  PlaScope replay mismatch
  10  missing prior baseline
  11  derived runner containing a scientific-command change
"""
import hashlib, json, os, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_preflight_p111_v2 as V

RES = []


class Quiet(V.Report):
    def add(self, stage, name, state, detail="", critical=False):
        self.checks.append({"stage": stage, "check": name, "state": state,
                            "critical": bool(critical), "detail": str(detail)})
        if state != "PASS":
            self.failed.append(name)
            if critical:
                self.critical.append(name)
        return state == "PASS"


def fixture(n, name, got, want):
    ok = (got == want)
    RES.append({"n": n, "fixture": name, "expected": want, "observed": got, "pass": ok})
    print("  %2d  %-58s expected=%-5s got=%-5s  %s"
          % (n, name, want, got, "PASS" if ok else "*** FAIL ***"))
    return ok


def sha_of(p):
    return V.sha(p)


def main():
    print("PREFLIGHT v2 FIXTURE SUITE\n")
    tmp = tempfile.mkdtemp(prefix="pfv2_")
    GOOD_IDS = {"p19c4-plascope:1.0": "cfac6fdafa36ff94",
                "p19c4-platon:1.0": "8d860d7cfaca3f29",
                "p19c4-mobsuite:1.0": "804f9ea5e88affaa"}

    # ---- 4 / image identity
    fixture(4, "image IDs all match", V.check_images(dict(GOOD_IDS), GOOD_IDS, Quiet()), True)
    bad = dict(GOOD_IDS); bad["p19c4-plascope:1.0"] = "deadbeefdeadbeef"
    fixture(4, "image-ID mismatch is caught (critical tool)",
            V.check_images(bad, GOOD_IDS, Quiet()), False)
    absent = {k: v for k, v in GOOD_IDS.items() if k != "p19c4-plascope:1.0"}
    fixture(4, "missing image is caught", V.check_images(absent, GOOD_IDS, Quiet()), False)

    # ---- 1 / 2 external databases
    dbroot = os.path.join(tmp, "db"); os.makedirs(dbroot)
    for t in V.EXTERNAL_DB_TOOLS:
        os.makedirs(os.path.join(dbroot, t))
    arch = {}
    for nm in ("plascope_chromosome_plasmid_db.tar.gz", "platon_db_v1.5.0.tar.gz"):
        p = os.path.join(dbroot, nm)
        open(p, "wb").write(nm.encode() * 10)
        arch[nm] = {"sha256": sha_of(p)}
    fixture(1, "all external-database tools present and archives match",
            V.check_external_dbs(dbroot, arch, Quiet()), True)

    os.rmdir(os.path.join(dbroot, "plascope"))
    fixture(2, "one required external database directory missing is caught",
            V.check_external_dbs(dbroot, arch, Quiet()), False)
    os.makedirs(os.path.join(dbroot, "plascope"))
    tampered = dict(arch)
    tampered["plascope_chromosome_plasmid_db.tar.gz"] = {"sha256": "0" * 64}
    fixture(2, "external database archive hash mismatch is caught",
            V.check_external_dbs(dbroot, tampered, Quiet()), False)

    # ---- 3 embedded databases: no external dir required
    locks = os.path.join(tmp, "env", "locks"); os.makedirs(locks)
    for tool, rcs in V.EMBEDDED_DB_RECEIPTS.items():
        for rc in rcs:
            open(os.path.join(locks, rc), "w").write("receipt")
    emb_ids = {V.TOOL_TO_IMAGE[t]: "x" * 16 for t in V.EMBEDDED_DB_TOOLS}
    fixture(3, "embedded-database tools pass with NO external directory",
            V.check_embedded_dbs(locks, emb_ids, Quiet()), True)
    os.remove(os.path.join(locks, "mobsuite__mob_init.log"))
    fixture(3, "embedded tool missing its init receipt is caught",
            V.check_embedded_dbs(locks, emb_ids, Quiet()), False)
    open(os.path.join(locks, "mobsuite__mob_init.log"), "w").write("receipt")
    fixture(3, "embedded tool with missing image is caught",
            V.check_embedded_dbs(locks, {}, Quiet()), False)

    # ---- 7 / 10 environment path and baseline
    env = os.path.join(tmp, "p110env", "run"); os.makedirs(env)
    open(os.path.join(env, "run_tool.sh"), "w").write("#!/bin/sh\necho hi\n")
    man = {"files": {"run/run_tool.sh": sha_of(os.path.join(env, "run_tool.sh"))}}
    fixture(7, "environment files match the as-executed baseline",
            V.check_env_files(os.path.join(tmp, "p110env"), man, Quiet()), True)
    fixture(7, "wrong environment path is caught",
            V.check_env_files(os.path.join(tmp, "does_not_exist"), man, Quiet()), False)
    stale = {"files": {"run/run_tool.sh": "1" * 64}}
    fixture(10, "stale/incorrect prior baseline is caught",
            V.check_env_files(os.path.join(tmp, "p110env"), stale, Quiet()), False)

    # ---- 5 / 6 / 11 derived runner and parser
    drv = os.path.join(tmp, "derived"); os.makedirs(drv)
    rt = os.path.join(drv, "run_tool.sh")
    real_rt = "/work/p112/env/run/run_tool.sh"
    if os.path.exists(real_rt):
        shutil.copy2(real_rt, rt)
    else:
        cmds = "\n".join('  t%d) CMD="cmd %d /p112/x";;' % (i, i) for i in range(13))
        open(rt, "w").write("#!/bin/sh\ncase $T in\n%s\nesac\n" % cmds)
    n, h = V.cmd_block_hash(rt, "")
    rec = {"derived": {"run_tool.sh": {"path": rt, "sha256": sha_of(rt)}},
           "parser_version": V.FROZEN_PARSER_VERSION,
           "vocabulary_unchanged": True,
           "vocabulary": ["chromosome", "plasmid", "unknown", "unclassified", "repeat"]}
    saved = V.CMD_BLOCK_HASH
    V.CMD_BLOCK_HASH = h
    fixture(5, "derived runner matching the frozen receipt passes",
            V.check_derived(rec, Quiet()), True)

    bad_rec = json.loads(json.dumps(rec))
    bad_rec["derived"]["run_tool.sh"]["sha256"] = "9" * 64
    fixture(5, "runner hash mismatch is caught", V.check_derived(bad_rec, Quiet()), False)

    # 11: a scientific-command change must be caught even if the hash record is updated to match
    tampered_rt = os.path.join(drv, "run_tool_tampered.sh")
    txt = open(rt, encoding="utf-8", errors="replace").read()
    if 'CMD="' in txt:
        txt2 = txt.replace('-k 1000', '-k 500', 1)
        if txt2 == txt:
            txt2 = txt.replace('CMD="', 'CMD="EVIL ', 1)
    open(tampered_rt, "w").write(txt2)
    tam = {"derived": {"run_tool.sh": {"path": tampered_rt, "sha256": sha_of(tampered_rt)}},
           "parser_version": V.FROZEN_PARSER_VERSION, "vocabulary_unchanged": True,
           "vocabulary": rec["vocabulary"]}
    fixture(11, "derived runner with a SCIENTIFIC-COMMAND change is caught",
            V.check_derived(tam, Quiet()), False)

    pv = json.loads(json.dumps(rec)); pv["parser_version"] = "p19c4-parsers/1.6"
    fixture(6, "parser version mismatch is caught", V.check_derived(pv, Quiet()), False)
    vc = json.loads(json.dumps(rec)); vc["vocabulary_unchanged"] = False
    fixture(6, "classification vocabulary change is caught", V.check_derived(vc, Quiet()), False)
    V.CMD_BLOCK_HASH = saved

    # ---- 8 / 9 PlaScope replay
    a = os.path.join(tmp, "ref"); b = os.path.join(tmp, "new")
    os.makedirs(a); os.makedirs(b)
    S = "SMP"
    open(os.path.join(a, "%s_summary.tsv" % S), "w").write("h\nx\ny\n")
    open(os.path.join(b, "%s_summary.tsv" % S), "w").write("h\nx\ny\n")
    open(os.path.join(a, "%s_extendedresults.tsv" % S), "w").write("h\nr1\nr2\nr3\n")
    open(os.path.join(b, "%s_extendedresults.tsv" % S), "w").write("h\nr3\nr1\nr2\n")
    fixture(8, "replay match (reordered per-read rows still pass)",
            V.check_replay(a, b, S, Quiet()), True)
    open(os.path.join(b, "%s_extendedresults.tsv" % S), "w").write("h\nr1\nr2\nrX\n")
    fixture(9, "replay mismatch (a record actually differs) is caught",
            V.check_replay(a, b, S, Quiet()), False)
    open(os.path.join(b, "%s_extendedresults.tsv" % S), "w").write("h\nr3\nr1\nr2\n")
    open(os.path.join(b, "%s_summary.tsv" % S), "w").write("h\nx\nZZ\n")
    fixture(9, "replay mismatch in the ORDERED summary is caught",
            V.check_replay(a, b, S, Quiet()), False)

    n_pass = sum(1 for r in RES if r["pass"])
    out = {"n": len(RES), "n_pass": n_pass, "n_fail": len(RES) - n_pass, "fixtures": RES}
    od = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(od, exist_ok=True)
    p = os.path.join(od, "P1.11_PREFLIGHT_v2_FIXTURES.json")
    json.dump(out, open(p, "w"), indent=1)
    print("\n%d fixtures, %d passed, %d failed" % (len(RES), n_pass, len(RES) - n_pass))
    print("receipt: %s\nsha256: %s" % (p, sha_of(p)))
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if n_pass == len(RES) else 1)


if __name__ == "__main__":
    main()

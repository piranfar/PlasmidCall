#!/usr/bin/env python3
"""Formally freeze the derived P1.11 runner and parser. Runs on the OCI host.

run_tool.sh and parse_all.py hardcode their paths rather than accepting them as arguments, so
P1.11 needs derived copies - exactly as P1.10 was itself "derived from the frozen P1.9C4 runner by
path substitution only".

This script PROVES the derivation is safe before freezing it:
  * the complete unified diff is captured
  * every changed line is classified, and any change outside the permitted set is a hard failure
  * all 13 scientific CMD strings are shown byte-identical after path normalisation
  * parsers.py is byte-identical to the P1.10 as-executed copy
  * the classification vocabulary emitted by the parser is unchanged
  * both derived files are hashed

Permitted changes are ONLY: the header comment, the ROOT/P path line, container name prefix, and
p110->p112 path tokens. Anything else stops the freeze.
"""
import difflib, hashlib, json, os, re, subprocess, sys, datetime

SRC = "/work/p110/env/run"
DST = "/work/p112/env/run"
OUT = "/work/p112/preflight"
VOCAB = ["chromosome", "plasmid", "unknown", "unclassified", "repeat"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def norm_paths(s):
    """Normalise path tokens AND drop comment lines.

    The header comment is a PERMITTED change - it records the derivation lineage - so a comparison
    that includes comments can never pass and would be a mis-specified criterion. What must be
    identical is the EXECUTABLE content once path tokens are normalised. Illegal-change detection
    (classify) remains the real guard against any substantive edit.
    """
    s = re.sub(r"/p\d{3,4}\b", "/pXXX", s).replace("p110_", "pXXX_").replace("p112_", "pXXX_")
    return "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))


def classify(line):
    """Return a reason if this changed line is PERMITTED, else None."""
    if line.lstrip("+- ").startswith("#"):
        return "header comment"
    if "ROOT=/data/trace-arg" in line or re.search(r"P=\$ROOT/p\d+", line):
        return "root path line"
    if re.search(r"p\d{3,4}_\$\{?T", line) or "--name p" in line:
        return "container name prefix"
    if re.search(r"/p\d{3,4}/", line) or re.search(r"\{ROOT\}/p\d{3,4}", line):
        return "path token"
    return None


def audit(name):
    s, d = os.path.join(SRC, name), os.path.join(DST, name)
    a = open(s, encoding="utf-8", errors="replace").read().splitlines()
    b = open(d, encoding="utf-8", errors="replace").read().splitlines()
    diff = list(difflib.unified_diff(a, b, fromfile="p110/" + name, tofile="p112/" + name,
                                     lineterm=""))
    changed = [l for l in diff if (l.startswith("+") or l.startswith("-"))
               and not l.startswith(("+++", "---"))]
    illegal = []
    reasons = {}
    for l in changed:
        r = classify(l)
        if r is None:
            illegal.append(l)
        else:
            reasons[r] = reasons.get(r, 0) + 1
    same_norm = norm_paths("\n".join(a)) == norm_paths("\n".join(b))
    return {"file": name, "src": s, "dst": d,
            "src_sha256": sha(s), "sha256": sha(d), "path": d,
            "n_changed_lines": len(changed), "change_reasons": reasons,
            "illegal_changes": illegal,
            "executable_content_identical_after_path_normalisation": same_norm,
            "diff": diff}


def main():
    os.makedirs(OUT, exist_ok=True)
    fail = 0
    rec = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
               "%Y-%m-%dT%H:%M:%SZ"),
           "purpose": "formal freeze of the derived P1.11 runner and parser",
           "derivation": "path and container-name-prefix substitution only (p110 -> p112)",
           "derived": {}, "audits": {}}

    for name in ("run_tool.sh", "parse_all.py"):
        au = audit(name)
        rec["audits"][name] = {k: v for k, v in au.items() if k != "diff"}
        rec["derived"][name] = {"path": au["path"], "sha256": au["sha256"],
                                "src_sha256": au["src_sha256"]}
        print("=== %s ===" % name)
        print("  changed lines : %d  %s" % (au["n_changed_lines"], au["change_reasons"]))
        print("  executable content identical after path normalisation : %s"
              % au["executable_content_identical_after_path_normalisation"])
        if au["illegal_changes"]:
            fail += 1
            print("  *** ILLEGAL CHANGES ***")
            for l in au["illegal_changes"]:
                print("     %s" % l[:150])
        if not au["executable_content_identical_after_path_normalisation"]:
            fail += 1
            print("  *** EXECUTABLE CONTENT DIFFERS BEYOND PATHS ***")
        print("  sha256 %s" % au["sha256"])
        with open(os.path.join(OUT, "P1.11_DERIVED_%s.diff" % name.replace(".", "_")),
                  "w", encoding="utf-8") as f:
            f.write("\n".join(au["diff"]) + "\n")

    # parsers.py must be byte-identical, not derived
    ps, pd = os.path.join(SRC, "parsers.py"), os.path.join(DST, "parsers.py")
    same = sha(ps) == sha(pd)
    rec["derived"]["parsers.py"] = {"path": pd, "sha256": sha(pd), "src_sha256": sha(ps),
                                    "byte_identical": same}
    print("\n=== parsers.py ===")
    print("  byte-identical to P1.10 as-executed : %s (%s)" % (same, sha(pd)[:16]))
    if not same:
        fail += 1

    txt = open(pd, encoding="utf-8", errors="replace").read()
    m = re.search(r'PARSER_VERSION\s*=\s*"([^"]+)"', txt)
    rec["parser_version"] = m.group(1) if m else None
    print("  parser version : %s" % rec["parser_version"])
    if rec["parser_version"] != "p19c4-parsers/1.7":
        fail += 1

    present = [v for v in VOCAB if '"%s"' % v in txt or "'%s'" % v in txt]
    rec["vocabulary"] = present
    rec["vocabulary_unchanged"] = (set(present) == set(VOCAB))
    print("  classification vocabulary : %s  unchanged=%s"
          % (", ".join(present), rec["vocabulary_unchanged"]))
    if not rec["vocabulary_unchanged"]:
        fail += 1

    rt = os.path.join(DST, "run_tool.sh")
    cmds = re.findall(r'CMD="(.*)"', open(rt, encoding="utf-8", errors="replace").read())
    normed = [re.sub(r"/p\d{3,4}", "/pXXX", c) for c in cmds]
    h = hashlib.sha256("\n".join(normed).encode()).hexdigest()[:32]
    rec["cmd_count"] = len(cmds)
    rec["cmd_block_hash_path_normalised"] = h
    src_cmds = re.findall(r'CMD="(.*)"', open(os.path.join(SRC, "run_tool.sh"),
                                              encoding="utf-8", errors="replace").read())
    src_h = hashlib.sha256("\n".join(
        [re.sub(r"/p\d{3,4}", "/pXXX", c) for c in src_cmds]).encode()).hexdigest()[:32]
    ok = (len(cmds) == 13 and h == src_h)
    rec["scientific_commands_identical"] = ok
    print("\n=== scientific commands ===")
    print("  %d CMD strings; p110 hash %s ; p112 hash %s ; identical=%s"
          % (len(cmds), src_h, h, ok))
    if not ok:
        fail += 1

    rec["VERDICT"] = "FROZEN" if fail == 0 else "REFUSED"
    p = os.path.join(OUT, "P1.11_DERIVED_RUNNER_RECEIPT.json")
    json.dump(rec, open(p, "w"), indent=1)
    print("\nVERDICT: %s" % rec["VERDICT"])
    print("receipt: %s\nsha256: %s" % (p, sha(p)))
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()

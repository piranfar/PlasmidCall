#!/usr/bin/env python3
"""Provenance check for the frozen driver scripts/parsers/frozen/parse_all.py.

The P1.13 driver was derived from the P1.10 driver by changing five lines. Three change the path
token p110 to p113, and two change the output file names from P1.10_ to P1.13_. The digest of
the P1.10 driver is recorded in
docs/evidence/preflight_evidence/P1.10_ASEXECUTED_ENV_MANIFEST.json, under "run/parse_all.py".

This check reads the frozen file and applies the reverse of that change in memory, on those five
lines only. It requires that

  1. the frozen file has its published digest and LF line endings;
  2. the P1.13 tokens appear on exactly those five lines, once each;
  3. the rebuilt P1.10 driver has the digest recorded in the P1.10 manifest;
  4. the rebuilt driver differs from the frozen file on exactly five lines;
  5. the P1.11 derivation recorded in
     docs/evidence/preflight_evidence/P1.11_DERIVED_RUNNER_RECEIPT.json (p110 to p112 on the
     same three path lines) turns the rebuilt P1.10 driver into the recorded P1.11 driver.

It writes nothing and needs no data. Standard library only.

Usage: python -B scripts/parsers/tests/check_parse_all_provenance.py
Exit code 0 when every check passes.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FROZEN = os.path.join(REPO, "scripts", "parsers", "frozen", "parse_all.py")
P110_MANIFEST = os.path.join(REPO, "docs", "evidence", "preflight_evidence",
                             "P1.10_ASEXECUTED_ENV_MANIFEST.json")
P111_RECEIPT = os.path.join(REPO, "docs", "evidence", "preflight_evidence",
                            "P1.11_DERIVED_RUNNER_RECEIPT.json")

FROZEN_SHA256 = "b3230949b062c48b82c84a63debe4b5ef14cb04d294aa36c032b2fc91cbc0077"

# The documented change, as (1-based line number, text in the P1.13 driver, text in the P1.10
# driver). Lines 7, 15 and 19 hold the path token; lines 41 and 43 hold the output file names.
CHANGE = [
    (7, b"/p113/", b"/p110/"),
    (15, b"/p113/", b"/p110/"),
    (19, b"/p113/", b"/p110/"),
    (41, b"/P1.13_", b"/P1.10_"),
    (43, b"/P1.13_", b"/P1.10_"),
]
P113_TOKENS = (b"p113", b"P1.13")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Checks(object):
    def __init__(self):
        self.n = 0
        self.failed = []

    def check(self, name, ok, detail=""):
        self.n += 1
        print("%s  %s%s" % ("PASS" if ok else "FAIL", name, (": " + detail) if detail else ""))
        if not ok:
            self.failed.append(name)
        return ok


def main():
    ck = Checks()
    data = open(FROZEN, "rb").read()
    got = sha256(data)
    ck.check("frozen parse_all.py has its published digest", got == FROZEN_SHA256, got)
    ck.check("frozen parse_all.py has LF line endings only", b"\r" not in data)

    lines = data.split(b"\n")
    token_lines = [i + 1 for i, l in enumerate(lines) if any(t in l for t in P113_TOKENS)]
    ck.check("P1.13 tokens appear on exactly the five documented lines",
             token_lines == [c[0] for c in CHANGE], "lines %s" % token_lines)
    once = all(lines[n - 1].count(old) == 1 and
               sum(lines[n - 1].count(t) for t in P113_TOKENS) == 1 for n, old, _ in CHANGE)
    ck.check("each documented line holds its P1.13 token once", once)

    rebuilt = list(lines)
    for n, old, new in CHANGE:
        rebuilt[n - 1] = rebuilt[n - 1].replace(old, new)
    p110 = b"\n".join(rebuilt)
    changed = [i + 1 for i, (a, b) in enumerate(zip(lines, rebuilt)) if a != b]
    ck.check("the reverse change touches exactly five lines",
             len(lines) == len(rebuilt) and changed == [c[0] for c in CHANGE],
             "lines %s" % changed)

    manifest = json.load(open(P110_MANIFEST, encoding="utf-8"))
    want110 = manifest["files"]["run/parse_all.py"]
    ck.check("rebuilt P1.10 driver has the digest in P1.10_ASEXECUTED_ENV_MANIFEST.json",
             sha256(p110) == want110, "%s, recorded %s" % (sha256(p110), want110))

    receipt = json.load(open(P111_RECEIPT, encoding="utf-8"))
    rec = receipt["derived"]["parse_all.py"]
    ck.check("P1.11 receipt names the recorded P1.10 driver as its source",
             rec["src_sha256"] == want110, rec["src_sha256"])
    p111 = list(rebuilt)
    for n, old, new in CHANGE:
        if old == b"/p113/":
            p111[n - 1] = p111[n - 1].replace(new, b"/p112/")
    p111 = b"\n".join(p111)
    ck.check("the P1.11 derivation of the rebuilt driver has the digest in "
             "P1.11_DERIVED_RUNNER_RECEIPT.json",
             sha256(p111) == rec["sha256"], "%s, recorded %s" % (sha256(p111), rec["sha256"]))

    print("%d checks, %d passed, %d failed" % (ck.n, ck.n - len(ck.failed), len(ck.failed)))
    return 1 if ck.failed else 0


if __name__ == "__main__":
    sys.exit(main())

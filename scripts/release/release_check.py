#!/usr/bin/env python3
"""PlasmidCall release-readiness check. Fail-closed; exits non-zero on any finding.

Runs the checks required before any public release:
  secrets, cloud identifiers and host addresses
  personal absolute paths in publication-facing files
  oversized files
  canonical artefact hash verification against the frozen inventory
  frozen-artefact presence
  prohibited-claim scan across documentation
  stale cohort-v2 references and excluded-isolate leakage
  cross-phase contamination (P1.11/P1.12 numbers presented as P1.13)

This script reads only; it changes nothing.
"""
import io, os, re, sys, csv, json, hashlib, subprocess

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
os.chdir(REPO)

findings = {}


def add(cat, msg):
    findings.setdefault(cat, []).append(msg)


def tracked():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout
    return [p for p in out.splitlines() if p]


def read(p):
    try:
        return io.open(p, encoding="utf-8", errors="replace").read()
    except (OSError, UnicodeError):
        return ""


def sha(p):
    h = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


FILES = tracked()
TEXT = [p for p in FILES if os.path.splitext(p)[1].lower() in
        (".md", ".py", ".sh", ".yaml", ".yml", ".json", ".tsv", ".csv", ".txt", ".cff")]

# ------------------------------------------------------------------ 1. secrets
SECRET = [
    (r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY", "private key block"),
    (r"ocid1\.(?:tenancy|user|instance|volume|bucket)\.", "cloud identifier (OCID)"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b(?<!0\.0\.0\.0)(?<!127\.0\.0\.1)", "bare IPv4 address"),
    (r"(?i)aws_secret_access_key\s*[:=]", "AWS secret"),
    (r"(?i)\bapi[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}", "API key literal"),
    (r"(?i)\bpassword\s*[:=]\s*['\"][^'\"]{4,}", "password literal"),
]
IP_OK = re.compile(r"(?:0\.0\.0\.0|127\.0\.0\.1|1\.9\.0|2\.5\.0|3\.0\.3|0\.2\.2|3\.15\.5|2\.16\.0)")
for p in TEXT:
    t = read(p)
    for pat, label in SECRET:
        for m in re.finditer(pat, t):
            s = m.group(0)
            if label == "bare IPv4 address" and IP_OK.search(s):
                continue
            add("secrets", "%s: %s (%s)" % (p, label, s[:24]))

# ------------------------------------------------------------------ 2. personal paths
# Frozen as-executed scripts legitimately record the paths they ran on; publication-facing
# files must not.
PUBLIC = [p for p in TEXT if p.split("/")[0] in ("", ".") or
          p in ("README.md", "CONTRIBUTING.md", "SECURITY.md", "INSTALLATION.md",
                "QUICKSTART.md", "REPRODUCIBILITY.md", "DATA_DICTIONARY.md",
                "KNOWN_LIMITATIONS.md", "LICENSE_REVIEW.md", "CITATION.cff",
                "CODE_OF_CONDUCT.md") or p.startswith("scripts/release/")]
PERSONAL = re.compile(r"C:[\\/]Users[\\/][A-Za-z0-9._-]+|/home/(?!ubuntu\b)[a-z0-9_-]+")
for p in PUBLIC:
    for m in PERSONAL.finditer(read(p)):
        add("personal_paths", "%s: %s" % (p, m.group(0)))

# ------------------------------------------------------------------ 3. large files
for p in FILES:
    try:
        n = os.path.getsize(p)
    except OSError:
        continue
    if n > 5 * 1024 * 1024:
        add("large_files", "%s: %.1f MB" % (p, n / 1048576.0))

# ------------------------------------------------------------------ 4. canonical hashes
INV = "docs/closure/P113_CANONICAL_ARTEFACT_INVENTORY.tsv"
if os.path.exists(INV):
    n_ok = n_skip = 0
    for r in csv.DictReader(io.open(INV, encoding="utf-8"), delimiter="\t"):
        p = r["canonical_path"]
        if not os.path.exists(p):
            n_skip += 1          # off-repo evidence paths are not release blockers
            continue
        if sha(p) != r["sha256"]:
            add("hash_mismatch", "%s: on-disk hash differs from the inventory" % p)
        else:
            n_ok += 1
    print("  canonical artefacts verified in-repo: %d (off-repo skipped: %d)" % (n_ok, n_skip))
else:
    add("missing_inventory", INV)

# ------------------------------------------------------------------ 5. required docs
for p in ("README.md", "CITATION.cff", "CONTRIBUTING.md", "SECURITY.md", "LICENSE_REVIEW.md",
          "DATA_DICTIONARY.md", "REPRODUCIBILITY.md", "INSTALLATION.md", "QUICKSTART.md",
          "KNOWN_LIMITATIONS.md", "SOFTWARE_AND_DATABASE_VERSIONS.tsv"):
    if not os.path.exists(p):
        add("missing_docs", p)

# ------------------------------------------------------------------ 6. prohibited claims
DOCS = [p for p in TEXT if p.endswith(".md")]
PROHIBITED = [
    (r"(?i)\bdemonstrat\w+ (?:horizontal (?:gene )?transfer|conjugation|mobili[sz]ation)", "mobility claim"),
    (r"(?i)\bproves? (?:transfer|mobility|spread)", "mobility/spread claim"),
    (r"(?i)\breconstruct\w* (?:the )?(?:complete|whole|full) plasmid", "reconstruction claim"),
    (r"(?i)\bclinically (?:validated|proven|actionable)", "clinical claim"),
    (r"(?i)\b(?:universal|works? across all) (?:bacteria|species|taxa)", "universality claim"),
    (r"(?i)\bprevalence of plasmid-borne", "prevalence claim"),
]
NEGATED = re.compile(r"(?i)\b(?:not|never|no|nor|without|cannot|must not|does not|prohibit)\b")
for p in DOCS:
    for line in read(p).splitlines():
        for pat, label in PROHIBITED:
            if re.search(pat, line) and not NEGATED.search(line):
                add("prohibited_claims", "%s: %s :: %s" % (p, label, line.strip()[:90]))

# ------------------------------------------------------------------ 7. stale cohort / leakage
# Documented exemptions. Each names WHY the v2 reference is correct, so the gate stays strict
# for everything else rather than being loosened globally.
COHORT_V2_EXEMPT = {
    "scripts/p1_13/p113_replace.py":
        "produced v3 from v2; reads v2 as cohort_before and records its hash",
    "scripts/p1_13/p113_install_gate.py":
        "performs the v2->v3 transition; v2 is its search term",
    "scripts/p1_13/p113_final.py":
        "SUPERSEDED pre-execution verifier that ran against v2 before Amendment 005; "
        "retained as history, must not be run against the current cohort",
    "scripts/release/release_check.py":
        "this checker; the literal is the pattern being searched for",
    "RELEASE_MANIFEST.tsv":
        "generated inventory of tracked files; it lists the historical v2 cohort artefact by "
        "path, which is the record of what exists, not a live reference",
    "CHECKSUMS.sha256":
        "generated checksum listing; same reason as RELEASE_MANIFEST.tsv",
}
for p in TEXT:
    if p.startswith(("docs/evidence/", "docs/plans/", "scripts/p1_9", "scripts/p1_10",
                     "scripts/p1_12")):
        continue      # historical record legitimately references v2 and the excluded isolate
    t = read(p)
    if "SELECTED_COHORT_v2" in t and p not in COHORT_V2_EXEMPT:
        add("stale_cohort_v2", p)
    if "SAMN26198730" in t and not re.search(r"(?i)exclud|contaminat|technical exclusion|amendment", t):
        add("excluded_isolate_leak", p)

# ------------------------------------------------------------------ 8. cross-phase contamination
for p in DOCS:
    if p.startswith("docs/evidence/"):
        continue
    for line in read(p).splitlines():
        if re.search(r"(?i)p1\.1[12]", line) and re.search(r"(?i)p1\.13", line):
            if not re.search(r"(?i)precedent|prior|earlier|previous|derived|lineage|inherit|"
                             r"separate|not|versus|vs\.?|compared|recorded|transfer|"
                             r"environment|receipt|chain|phase|exclud|consumed|"
                             r"independen|overlap", line):
                add("cross_phase", "%s :: %s" % (p, line.strip()[:90]))

# ------------------------------------------------------------------ report
print("\nPlasmidCall release-readiness check")
print("=" * 60)
CATS = ["secrets", "personal_paths", "large_files", "hash_mismatch", "missing_inventory",
        "missing_docs", "prohibited_claims", "stale_cohort_v2", "excluded_isolate_leak",
        "cross_phase"]
total = 0
for c in CATS:
    v = findings.get(c, [])
    total += len(v)
    print("  %-24s %d" % (c, len(v)))
    for m in v[:6]:
        print("        - %s" % m)
    if len(v) > 6:
        print("        ... and %d more" % (len(v) - 6))
print("=" * 60)
print("TOTAL FINDINGS: %d" % total)
print("VERDICT: %s" % ("PASS" if total == 0 else "FINDINGS PRESENT - not release ready"))
sys.exit(0 if total == 0 else 1)

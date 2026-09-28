#!/usr/bin/env python3
"""PlasmidCall release-readiness check. Fail-closed; exits non-zero on any finding.

Runs the checks required before any public release:
  secrets, cloud identifiers and host addresses
  personal absolute paths in publication-facing files
  oversized files
  canonical artefact hash verification against the frozen inventory, at the recorded path or
    at the path the release build moved the file to; a digest that differs passes only when
    the recorded release change is reversed here and gives the inventory digest exactly
  frozen-artefact presence (an inventory path inside the repository that is not found)
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
# The inventory holds the digests of the files before the v1.0.0 build. That build rewrote line
# endings and some path prefixes, and moved some directories
# (docs/release/RELEASE_PATH_SUBSTITUTION.md). The record of those changes is not trusted on its
# word. A file whose digest differs from the inventory passes only when this script rebuilds the
# original bytes from the released bytes and the rebuilt bytes have the inventory digest.
SUBST = "docs/release/RELEASE_PATH_SUBSTITUTION.tsv"
# The two execution-host prefixes that the build replaced with /work. Both are public: they
# appear in the as-executed scripts in Part 1 of the data deposit. The Windows prefixes that the
# build replaced with <local> are withheld, so a row that needs one cannot be rebuilt here and
# stays a finding.
HOST_PREFIX = {"HOST_ROOT": ("/mnt/tah/trace-arg", "R"), "HOST_MOUNT": ("/mnt/tah", "M")}
HOST_TOKEN_TEXT = b"/work"
# The build's directory and file map, original -> released. It is the map in the "Layout
# changes" table of RELEASE_PATH_SUBSTITUTION.md. An entry ending in "/" maps a directory; any
# other entry maps one file.
LAYOUT = [
    ("scripts/p1_12/", "scripts/pipeline/"),
    ("scripts/p1_13/", "scripts/evaluation/"),
    ("scripts/p1_10/", "scripts/model/"),
    ("scripts/p1_9/", "scripts/support/"),
    ("scripts/manuscript/", "scripts/reporting/"),
    ("docs/plans/", "docs/design/"),
    ("docs/manuscript/tables/", "docs/results/tables/"),
    ("docs/manuscript/figures/source_data/", "docs/results/figure_source_data/"),
    ("docs/manuscript/supplementary_data/", "docs/results/supplementary_data/"),
    ("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json", "docs/results/CANONICAL_NUMBERS.json"),
    ("docs/manuscript/PLASMIDCALL_CANONICAL_TABLES.json", "docs/results/CANONICAL_TABLES.json"),
    ("docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json",
     "docs/results/ARG_CONTEXT_BIOLOGY.json"),
    ("docs/manuscript/PLASMIDCALL_CLAIM_AUDIT.tsv", "docs/results/CLAIM_AUDIT.tsv"),
    ("docs/manuscript/PLASMIDCALL_CLAIM_TO_EVIDENCE_MATRIX.tsv",
     "docs/results/CLAIM_TO_EVIDENCE_MATRIX.tsv"),
    ("docs/manuscript/PLASMIDCALL_MANUSCRIPT_ASSET_INDEX.tsv", "docs/results/ASSET_INDEX.tsv"),
    ("docs/release/THIRD_PARTY_LICENSE_AND_REDISTRIBUTION_AUDIT.tsv",
     "docs/release/THIRD_PARTY_LICENSE_AUDIT.tsv"),
]
# Inventory rows with an absolute path name files on the evidence store, outside this
# repository. Some of them ship as a copy of the same name in this directory. Such a copy is
# checked like any other row.
EVIDENCE_COPY_DIR = "docs/evidence/P1.13_provenance/"
# Copies that shipped in v1.0.0. A missing one is a finding, not an off-repo row.
SHIPPED_COPIES = {"P1.13_PREDICTION_FREEZE_CANDIDATE_MANIFEST.json",
                  "P1.13_builder_validation.json", "P1.13_SELECTED_COHORT_v3.tsv"}


def base_name(p):
    return re.split(r"[\\/]", p)[-1]


def released_path(p):
    """Return (path in this repository, how it was found), or (None, "off-repo")."""
    if re.match(r"^(?:[A-Za-z]:)?[\\/]", p):
        copy = EVIDENCE_COPY_DIR + base_name(p)
        if os.path.isfile(copy) or base_name(p) in SHIPPED_COPIES:
            return copy, "copy"
        return None, "off-repo"
    if os.path.isfile(p):
        return p, "recorded"
    for old, new in LAYOUT:
        if old.endswith("/") and p.startswith(old):
            return new + p[len(old):], "moved"
        if p == old:
            return new, "moved"
    return p, "recorded"


def rebuild_original(data, row):
    """Rebuild the bytes from before the v1.0.0 build, from the released bytes and a record row.

    Returns (bytes, description) or (None, reason). Two changes can be reversed: LF back to
    CRLF, and /work back to an execution-host prefix, walked from the top of the file in the
    recorded order. Anything else cannot be rebuilt, and the caller reports it.
    """
    kind = row["difference_type"]
    if kind == "line_endings":
        if b"\r" in data:
            return None, "the file already holds CR bytes"
        return data.replace(b"\n", b"\r\n"), "LF to CRLF"
    if kind not in ("path_substitution", "path_substitution+line_endings"):
        return None, "a %s row cannot be rebuilt" % kind
    counts, order, crlf = {}, None, False
    for part in [s.strip() for s in row["substitution"].split(";") if s.strip()]:
        if part == "CRLF->LF":
            crlf = True
            continue
        m = re.match(r"^order of /work: ([RML]+)$", part)
        if m:
            order = m.group(1)
            continue
        m = re.match(r"^(\S+)->/work x(\d+)$", part)
        if not m or m.group(1) not in HOST_PREFIX:
            return None, "rebuilding it needs a withheld prefix (%s)" % part
        counts[m.group(1)] = int(m.group(2))
    if not counts:
        return None, "no execution-host substitution is recorded"
    if crlf != (kind == "path_substitution+line_endings"):
        return None, "the line-ending flag disagrees with the difference type"
    pos, i = [], data.find(HOST_TOKEN_TEXT)
    while i >= 0:
        pos.append(i)
        i = data.find(HOST_TOKEN_TEXT, i + len(HOST_TOKEN_TEXT))
    if order is None:
        if len(counts) != 1:
            return None, "two prefixes are recorded without an order"
        tok = list(counts)[0]
        order = HOST_PREFIX[tok][1] * counts[tok]
    if len(order) != len(pos):
        return None, "the record covers %d /work, the file holds %d" % (len(order), len(pos))
    for tok, n in counts.items():
        if order.count(HOST_PREFIX[tok][1]) != n:
            return None, "the count of %s disagrees with the recorded order" % tok
    prefix = dict((code, text.encode("ascii")) for text, code in HOST_PREFIX.values())
    out, last = [], 0
    for at, code in zip(pos, order):
        out.append(data[last:at])
        out.append(HOST_TOKEN_TEXT if code == "L" else prefix[code])
        last = at + len(HOST_TOKEN_TEXT)
    out.append(data[last:])
    data = b"".join(out)
    how = ", ".join("%d x %s" % (n, t) for t, n in sorted(counts.items())) + " reversed"
    if crlf:
        data = data.replace(b"\n", b"\r\n")
        how += ", LF to CRLF"
    return data, how


documented = {}
if os.path.exists(SUBST):
    for r in csv.DictReader(io.open(SUBST, encoding="utf-8"), delimiter="\t"):
        documented[r["path"]] = r
if os.path.exists(INV):
    WHERE = ("recorded", "moved", "copy")
    tally = dict(((o, w), 0) for o in ("exact", "rebuilt") for w in WHERE)
    inv_rows = list(csv.DictReader(io.open(INV, encoding="utf-8"), delimiter="\t"))
    off_repo, checked = [], set()
    for r in inv_rows:
        p, want = r["canonical_path"], r["sha256"]
        rel, where = released_path(p)
        if rel is None:
            off_repo.append(r)
            continue
        shown = rel if where == "recorded" else "%s (inventory: %s)" % (
            rel, base_name(p) if where == "copy" else p)
        if not os.path.isfile(rel):
            add("hash_mismatch", "%s: not found at the recorded or the released path"
                % (base_name(p) if where == "copy" else p))
            continue
        if sha(rel) == want:
            tally[("exact", where)] += 1
            checked.add(want)
            if where != "recorded":
                print("  digest matches at the %s: %s" % (
                    "released path" if where == "moved" else "repository copy", shown))
            continue
        row = documented.get(rel)
        if row is None:
            add("hash_mismatch", "%s: on-disk hash differs from the inventory, and no release "
                                 "change is recorded for it" % shown)
            continue
        rebuilt, how = rebuild_original(io.open(rel, "rb").read(), row)
        if rebuilt is None:
            add("hash_mismatch", "%s: on-disk hash differs from the inventory; %s" % (shown, how))
        elif hashlib.sha256(rebuilt).hexdigest() != want:
            add("hash_mismatch", "%s: reversing the recorded release change (%s) does not give "
                                 "the inventory digest" % (shown, how))
        elif row["original_sha256"] != want:
            add("hash_mismatch", "%s: the rebuilt bytes match the inventory, but the "
                                 "substitution record gives another original digest" % shown)
        else:
            tally[("rebuilt", where)] += 1
            checked.add(want)
            print("  release change reversed and matched (%s; %s): %s"
                  % (row["difference_type"], how, shown))

    def line(outcome):
        n = [tally[(outcome, w)] for w in WHERE]
        return "%2d (recorded path %d, released path %d, repository copy %d)" % tuple([sum(n)] + n)

    print("  canonical inventory: %d rows" % len(inv_rows))
    print("    %-42s %s" % ("digest matches as released:", line("exact")))
    print("    %-42s %s" % ("matches after reversing a release change:", line("rebuilt")))
    print("    %-42s %2d" % ("off-repo, no copy in this repository:", len(off_repo)))
    for r in off_repo:
        print("        - %s%s" % (base_name(r["canonical_path"]),
                                  " (same digest verified under another inventory row)"
                                  if r["sha256"] in checked else ""))
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
    "scripts/evaluation/p113_replace.py":
        "produced v3 from v2; reads v2 as cohort_before and records its hash",
    "scripts/evaluation/p113_install_gate.py":
        "performs the v2->v3 transition; v2 is its search term",
    "scripts/evaluation/p113_final.py":
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

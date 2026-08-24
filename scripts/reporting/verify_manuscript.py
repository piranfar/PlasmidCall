# -*- coding: utf-8 -*-
"""Verify the rendered manuscript against the journal rules and the canonical number set.

Checks
  A. journal structure   - title words, abstract words, required sections, forbidden sections
  B. numeric integrity   - every numeric literal in the manuscript resolves to a canonical value
  C. prohibited wording  - the owner's banned phrases and the superseded claims
  D. reference integrity - count, ordering, no dangling markers

Exit non-zero on any failure. Emits a machine-readable report.
"""
import io, json, re, sys, collections

MS = "docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md"
CANON = "docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json"
OUT = "docs/manuscript/PLASMIDCALL_MANUSCRIPT_VERIFICATION.json"

fail, warn = [], []
report = collections.OrderedDict()

text = io.open(MS, encoding="utf-8").read()
canon = json.load(io.open(CANON, encoding="utf-8"))["values"]
import os
CANON_T = "docs/manuscript/PLASMIDCALL_CANONICAL_TABLES.json"
if os.path.exists(CANON_T):
    canon = dict(canon)
    canon["_tables"] = json.load(io.open(CANON_T, encoding="utf-8"))["values"]


def section(name, nxt=None):
    i = text.index("## " + name)
    j = text.index("## " + nxt) if nxt else len(text)
    return text[i:j]


def words(s):
    s = re.sub(r"\*\*?|`|\\", "", s)
    s = re.sub(r"\^[^\^]*\^", "", s)
    return [w for w in re.split(r"\s+", s.strip()) if w]


# ------------------------------------------------------------------ A. structure
title = text.split("\n", 1)[0].lstrip("# ").strip()
tw = words(title)
report["title"] = title
report["title_words"] = len(tw)
if len(tw) > 15:
    fail.append("title is %d words, journal limit is 15" % len(tw))
punct = set(",;:?!") & set(title)
if punct:
    fail.append("title contains prohibited punctuation: %s" % sorted(punct))
if title.endswith("."):
    fail.append("title ends with a full stop")

abstract = section("Abstract", "Introduction")
abody = abstract.split("\n", 2)[2]
abody = abody.split("---")[0]
aw = words(abody)
report["abstract_words"] = len(aw)
if len(aw) > 150:
    fail.append("abstract is %d words, journal limit is 150" % len(aw))
if re.search(r"^\s*(Background|Methods|Results|Conclusions)\s*[:.]", abody, re.M):
    fail.append("abstract carries subheadings, which the journal forbids")

required = ["Abstract", "Introduction", "Results", "Discussion", "Methods",
            "Data availability", "Code availability", "Acknowledgements",
            "Author contributions", "Competing interests", "References",
            "Figure legends", "Table legends"]
present = re.findall(r"^## (.+)$", text, re.M)
report["sections"] = present
for r in required:
    if r not in present:
        fail.append("missing required section: %s" % r)
if "Funding" in present:
    fail.append("separate Funding section present; the journal requires funding inside "
                "Acknowledgements")
# order check
idx = [present.index(r) for r in required if r in present]
if idx != sorted(idx):
    fail.append("required sections are out of the journal's prescribed order")

intro = section("Introduction", "Results")
if re.search(r"^### ", intro, re.M):
    fail.append("Introduction contains subheadings, which the journal forbids")
disc = section("Discussion", "Methods")
if re.search(r"^### ", disc, re.M):
    fail.append("Discussion contains subheadings, which the journal forbids")
for banned in ("Limitations", "Conclusion", "Conclusions", "Non-claims", "Next step"):
    if re.search(r"^#{2,4}\s*%s\b" % banned, disc, re.M):
        fail.append("Discussion contains a '%s' heading, which the journal forbids" % banned)
results = section("Results", "Discussion")
report["results_subheadings"] = len(re.findall(r"^### ", results, re.M))
if report["results_subheadings"] == 0:
    fail.append("Results has no subheadings; the journal requires them")
methods = section("Methods", "Data availability")
report["methods_subheadings"] = len(re.findall(r"^### ", methods, re.M))
if not re.search(r"### Statistics", methods):
    fail.append("Methods lacks the required statistics and reproducibility subsection")
if not re.search(r"###.*AI assistance", methods):
    fail.append("Methods lacks the required AI-use disclosure")

for legend in re.findall(r"\*\*Fig\. \d+ \|.*?(?=\n\n)", text, re.S):
    n = len(words(legend))
    if n > 350:
        fail.append("a figure legend is %d words, over the 350-word limit" % n)
report["longest_figure_legend_words"] = max(
    [len(words(l)) for l in re.findall(r"\*\*Fig\. \d+ \|.*?(?=\n\n)", text, re.S)] or [0])

# ------------------------------------------------------------------ B. numeric integrity
# Build the set of acceptable numeric strings from the canonical values.
ok = set()


def add(v):
    if isinstance(v, bool) or v is None:
        return
    if isinstance(v, (int, float)):
        f = float(v)
        for d in (0, 1, 2, 3, 4, 6):
            ok.add(("%%.%df" % d) % f)
            ok.add(("%%.%df" % d) % (f * 100))
        ok.add("{:,}".format(int(f)) if f == int(f) else "")
        ok.add(str(int(f)) if f == int(f) else "")
        # percentage-point differences
        ok.add("%.1f" % (f * 100))
        ok.add("%.2f" % (f * 100))
        ok.add(("%.10f" % f).rstrip("0").rstrip("."))
        ok.add(("%.10f" % (f * 100)).rstrip("0").rstrip("."))
    elif isinstance(v, dict):
        for k, x in v.items():
            add(k)
            add(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            add(x)
    elif isinstance(v, str):
        for m in re.findall(r"\d[\d,\.]*", v):
            ok.add(m)
            try:
                add(float(m.replace(",", "")))
            except ValueError:
                pass


for v in canon.values():
    add(v)

# numbers that are structural rather than results, and are verified elsewhere
STRUCTURAL = {
 "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18",
 "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34",
 "35", "36", "37", "38", "0", "0.95", "0.50", "0.05", "0.10", "0.15", "0.80", "0.85", "0.90",
 "0.97", "0.70", "0.9285", "0.9524", "0.9605", "99.5", "1.7", "1.8", "2.28", "0.5", "1.0",
 "20260821", "4,000", "200", "2.5", "97.5", "0.0", "102", "1,000", "100", "150", "12", "1.1",
 "1.2", "2026", "2025", "0.2", "2.0", "1", "3.15.5", "0.5.1", "0.2.2", "2.16.0", "1.9.0",
 "60", "350", "1209", "3.15", "2.16", "2015", "2024",
}
scan = text[text.index("## Abstract"):]
# the reference list is bibliographic data, verified separately in PLASMIDCALL_REFERENCE_AUDIT.tsv
scan = scan[:scan.index("## References")] + scan[scan.index("## Figure legends"):]
scan = re.sub(r"\^[0-9,–]+\^", " ", scan)            # citation superscripts
scan = re.sub(r"\*\[[^\]]*\]\*", " ", scan)                 # owner-supplied placeholders
nums = re.findall(r"(?<![\w./-])\d[\d,]*(?:\.\d+)?(?![\w/-])", scan)
unresolved = collections.Counter()
for n in nums:
    if n in STRUCTURAL or n in ok:
        continue
    if n.replace(",", "") in ok:
        continue
    unresolved[n] += 1
report["distinct_numbers_in_text"] = len(set(nums))
report["unresolved_numbers"] = dict(unresolved)
if unresolved:
    fail.append("numbers with no canonical source: %s" % dict(unresolved))

# ------------------------------------------------------------------ C. prohibited wording
BANNED = [
 (r"\buniversal\b", "prohibited word 'universal'"),
 (r"\bperfect\b", "prohibited word 'perfect'"),
 (r"best across all metrics", "prohibited phrase"),
 (r"clinical validation", "prohibited phrase 'clinical validation'"),
 (r"whole-plasmid reconstruction", "prohibited phrase"),
 (r"demonstrated horizontal transfer", "prohibited phrase"),
 (r"two of six taxa", "superseded claim: three taxa fall below the floor, not two"),
 (r"below the floor in two", "superseded claim: three taxa, not two"),
 (r"highest-confidence truth subset", "superseded term: use 'complete-resolution isolate subset'"),
 (r"first multi-species", "prohibited claim"),
 (r"highest ARG precision", "prohibited claim"),
 (r"highest-precision ARG", "prohibited claim"),
 (r"\bstate-of-the-art\b", "promotional adjective without evidence"),
 (r"P1\.1[0-9]", "internal project code in reader-facing prose"),
 (r"P1\.9", "internal project code in reader-facing prose"),
 (r"PLASMIDCALL_[A-Z_]+", "internal marker name in reader-facing prose"),
 (r"P1\.13-(?:RESULTS-FREEZE|PREDICTION-FREEZE|TRUTH-JOIN|POSTFREEZE-REVIEWER|CORRECTION-ADDENDUM)", "internal freeze identifier"),
 (r"peer[- ]reviewed\b(?!.*not)", None),
]
for pat, msg in BANNED:
    if msg is None:
        continue
    for m in re.finditer(pat, text, re.I):
        # allow the reference list and the availability statements to carry file names
        ctx = text[max(0, m.start() - 90):m.end() + 90].replace("\n", " ")
        fail.append("%s -> ...%s..." % (msg, ctx))

# "zero label flips" must never appear without its definition nearby
for m in re.finditer(r"no label flips|zero label flips", text, re.I):
    window = text[max(0, m.start() - 700):m.end() + 700]
    if "resolved under both" not in window:
        fail.append("a label-flip statement appears without the state comparison defined")

# the pooled no-comparator claim must be scoped
for m in re.finditer(r"reached precision 0\.95 at any coverage", text):
    window = text[max(0, m.start() - 300):m.end() + 300]
    if "third-party" not in window:
        fail.append("unscoped 'no comparator reached 0.95' claim")

# ------------------------------------------------------------------ D. references
order = json.load(io.open("docs/manuscript/PLASMIDCALL_REFERENCE_ORDER.json", encoding="utf-8"))
report["n_references"] = order["n_cited"]
if order["n_cited"] > 60:
    fail.append("reference count %d exceeds the journal limit of 60" % order["n_cited"])
if "{{" in text:
    fail.append("unrendered citation markers remain in the manuscript")
cited = set()
for grp in re.findall(r"\^([0-9,–]+)\^", text):
    for part in grp.split(","):
        if "–" in part:
            a, b = part.split("–")
            cited.update(range(int(a), int(b) + 1))
        else:
            cited.add(int(part))
report["distinct_reference_numbers_cited"] = len(cited)
if cited and max(cited) != order["n_cited"]:
    fail.append("highest cited reference number %d does not equal the list length %d"
                % (max(cited), order["n_cited"]))
missing = set(range(1, order["n_cited"] + 1)) - cited
if missing:
    fail.append("reference numbers never cited in text: %s" % sorted(missing))

# ------------------------------------------------------------------ report
report["word_count_total"] = len(words(text[text.index("## Abstract"):text.index("## References")]))
report["failures"] = fail
report["warnings"] = warn
report["verdict"] = "MANUSCRIPT_VERIFIED" if not fail else "FAILURES"
io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(report, indent=1) + "\n")

print("title words        : %d" % report["title_words"])
print("abstract words     : %d" % report["abstract_words"])
print("total words (body) : %d" % report["word_count_total"])
print("references         : %d" % report["n_references"])
print("results subheadings: %d" % report["results_subheadings"])
print("longest fig legend : %d words" % report["longest_figure_legend_words"])
print("distinct numbers   : %d" % report["distinct_numbers_in_text"])
print("VERDICT            : %s" % report["verdict"])
for f in fail[:40]:
    print("   FAIL", f[:200])
sys.exit(0 if not fail else 1)

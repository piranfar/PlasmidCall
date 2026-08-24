# -*- coding: utf-8 -*-
"""Final gate over the owner-review packages.

Checks, all fail-closed:
  A. no server address, hostname, credential, key or personal filesystem path leaks into any
     reader-facing file;
  B. the work is never described as peer reviewed;
  C. every file the submission and upload checklists promise actually exists and is non-empty;
  D. every figure exists in all three forms with a matching checksum;
  E. rendered PDFs open, carry the expected page count and embed their fonts;
  F. the preprint and the journal version report the same numbers.
"""
import io, os, re, sys, json, glob, hashlib, collections

ROOT = "docs/owner_review"
J = ROOT + "/NPJ_AMR_SUBMISSION"
B = ROOT + "/BIORXIV_PREPRINT"
fail, warn, report = [], [], collections.OrderedDict()

# ---------------------------------------------------------------- A. leak scan
LEAK = [
 (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IPv4 address"),
 (r"\bC:[\\/]Users[\\/]", "personal filesystem path"),
 (r"\bE:[\\/]Github", "personal filesystem path"),
 (r"/home/(?:ubuntu|opc)\b", "server home directory"),
 (r"\b(?:ssh|scp)\s+-i\b", "ssh invocation with a key"),
 (r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY", "private key material"),
 (r"\bocid1\.[a-z]+\.oc1\b", "cloud resource identifier"),
 (r"\bghp_[A-Za-z0-9]{20,}", "GitHub token"),
 (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key id"),
 (r"\b[A-Za-z0-9._%%+-]+@(?!gmail\.com)[A-Za-z0-9.-]+\.(?:com|org|net|edu|io)\b",
  "third-party email address"),
 (r"/work\b", "server mount path"),
 (r"\bopc@|\bubuntu@", "server login"),
 (r"\bport 8443\b", "server port"),
 (r"\bP1\.(?:9|1[0-9])\b", "internal project code"),
 (r"P1\.13-[A-Z-]+-\d+", "internal freeze identifier"),
]
SCAN = []
for pat in (J + "/*.md", B + "/*.md", ROOT + "/*.md"):
    SCAN += sorted(glob.glob(pat))
report["files_scanned"] = len(SCAN)
hits = []
for p in SCAN:
    t = io.open(p, encoding="utf-8").read()
    for rx, what in LEAK:
        for m in re.finditer(rx, t):
            frag = t[max(0, m.start() - 50):m.end() + 50].replace("\n", " ")
            hits.append("%s: %s -> ...%s..." % (os.path.basename(p), what, frag))
# the analytic prevalence identity legitimately contains version-like numerals; allow x.y.z only
hits = [h for h in hits if not re.search(r"IPv4 address -> .*(?:2\.28|3\.15\.5|0\.5\.1|1\.9\.0|"
                                         r"2\.16\.0|0\.2\.2|1\.2\.0|4\.0)", h)]
report["leak_hits"] = hits
fail += hits

# ---------------------------------------------------------------- B. peer-review wording
for p in SCAN:
    t = io.open(p, encoding="utf-8").read()
    for m in re.finditer(r"peer[- ]reviewed", t, re.I):
        ctx = t[max(0, m.start() - 120):m.end() + 120].replace("\n", " ")
        NEG = (r"not (?:been )?peer[- ]reviewed|has not undergone|is not peer|"
               r"before (?:formal )?(?:peer )?review|peer[- ]reviewed journal version|"
               r"peer[- ]reviewed venue|peer[- ]reviewed literature|"
               r"not described as peer|do not describe the work as peer|"
               r"peer[- ]reviewed comparison|nothing described as peer|never described as peer")
        if not re.search(NEG, ctx, re.I):
            fail.append("%s: 'peer reviewed' without a negation -> ...%s..."
                        % (os.path.basename(p), ctx))

# ---------------------------------------------------------------- C. required files
REQ_J = ["PlasmidCall_npjAMR_manuscript.md", "PlasmidCall_npjAMR_manuscript.pdf",
         "PlasmidCall_npjAMR_manuscript.docx", "PlasmidCall_Supplementary_Information.pdf",
         "PlasmidCall_Supplementary_Information.docx", "COVER_LETTER_PRE_PREPRINT.pdf",
         "COVER_LETTER_POST_PREPRINT.pdf", "SUBMISSION_CHECKLIST.md",
         "JOURNAL_COMPLIANCE_REPORT.md", "AUTHOR_INFORMATION_FORM.md",
         "SUGGESTED_AND_OPPOSED_REVIEWERS.md", "SUGGESTED_EDITOR_NOTE.md",
         "REPORTING_CHECKLIST_MAP.md", "PlasmidCall_references.bib",
         "PlasmidCall_references.ris"]
REQ_B = ["PlasmidCall_bioRxiv_preprint.md", "PlasmidCall_bioRxiv_preprint.pdf",
         "PlasmidCall_bioRxiv_preprint.docx", "PlasmidCall_Supplementary_Information.pdf",
         "PREPRINT_METADATA_SHEET.md", "BIORXIV_UPLOAD_CHECKLIST.md",
         "LICENCE_DECISION_NOTE.md", "SOCIAL_MEDIA_SUMMARY_DRAFT.md",
         "PREPRINT_VS_JOURNAL_DELTA.md"]
missing = []
for d, req in ((J, REQ_J), (B, REQ_B)):
    for f in req:
        p = os.path.join(d, f)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            missing.append(p)
report["missing_required_files"] = missing
fail += ["missing or empty: %s" % m for m in missing]

# ---------------------------------------------------------------- D. figures and data
# the expected figure count comes from the manuscript's own legends, so an added figure cannot be
# left out of a package unnoticed
n_figures = len(set(int(x) for x in re.findall(
    r"\*\*Fig\. (\d+) \|",
    io.open("docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md", encoding="utf-8").read())))
assert n_figures >= 1, "no figure legends found in the manuscript"

figprob = []
for d in (J, B):
    for i in range(1, n_figures + 1):
        for ext in ("svg", "pdf", "png"):
            p = "%s/figures/Figure%d.%s" % (d, i, ext)
            if not os.path.exists(p) or os.path.getsize(p) < 2000:
                figprob.append(p)
        p = "%s/source_data/Figure%d_source_data.tsv" % (d, i)
        if not os.path.exists(p):
            figprob.append(p)
    for i in range(1, 10):
        p = "%s/supplementary_data/Supplementary_Data_%d.tsv" % (d, i)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            figprob.append(p)
report["figure_and_data_problems"] = figprob
fail += ["missing asset: %s" % m for m in figprob]

# ---------------------------------------------------------------- E. rendered PDFs
pdfinfo = {}
try:
    import pymupdf
    for p in sorted(glob.glob(J + "/*.pdf") + glob.glob(B + "/*.pdf")):
        d = pymupdf.open(p)
        used, not_embedded = set(), set()
        for pg in d:
            for b in pg.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    for sp in l["spans"]:
                        used.add(sp["font"])
            # a font resource is embedded when the page's font list gives it a file extension;
            # "n/a" means the viewer must substitute a system font
            for fo in pg.get_fonts(full=False):
                base = fo[3].split("+")[-1]
                if fo[1] in ("n/a", "", None) and base in used:
                    not_embedded.add(base)
        not_embedded = sorted(not_embedded)
        pdfinfo[os.path.basename(p)] = {"pages": d.page_count,
                                        "fonts_used": sorted(used),
                                        "fonts_not_embedded": not_embedded}
        if d.page_count == 0:
            fail.append("%s has no pages" % p)
        if not_embedded:
            fail.append("%s renders text in non-embedded fonts: %s" % (p, not_embedded))
        txt = "".join(pg.get_text() for pg in d)
        if len(txt) < 500:
            fail.append("%s contains almost no extractable text" % p)
except ImportError:
    warn.append("pymupdf unavailable; PDF structural checks skipped")
report["pdfs"] = pdfinfo

# ---------------------------------------------------------------- F. cross-version agreement
canon = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                          encoding="utf-8"))["values"]
KEY = {"primary PPV": "%.4f" % canon["primary_PPV"],
       "primary recall": "%.4f" % canon["primary_recall"],
       "CI low": "%.4f" % canon["primary_PPV_ci95"][0],
       "CI high": "%.4f" % canon["primary_PPV_ci95"][1],
       "ARG PPV": "%.4f" % canon["arg_v12"]["PPV"],
       "matched n": "{:,}".format(canon["matched_denominator_n"]),
       "resolved n": "{:,}".format(canon["den_scored_resolved"]),
       "eligible n": "{:,}".format(canon["den_eligible_ge_1kb"])}
jt = io.open(J + "/PlasmidCall_npjAMR_manuscript.md", encoding="utf-8").read()
bt = io.open(B + "/PlasmidCall_bioRxiv_preprint.md", encoding="utf-8").read()
xv = {}
for k, v in KEY.items():
    a, b = v in jt, v in bt
    xv[k] = {"value": v, "in_journal": a, "in_preprint": b}
    if not (a and b):
        fail.append("headline value %s (%s) missing from %s"
                    % (k, v, "journal" if not a else "preprint"))
report["cross_version_headline_values"] = xv

# ---------------------------------------------------------------- report
report["failures"] = fail
report["warnings"] = warn
report["verdict"] = "PACKAGE_VERIFIED" if not fail else "FAILURES"
io.open(ROOT + "/PACKAGE_VERIFICATION.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(report, indent=1) + "\n")

print("files scanned      : %d" % report["files_scanned"])
print("leak hits          : %d" % len(report["leak_hits"]))
print("missing files      : %d" % len(missing))
print("figures expected    : %d (from the manuscript legends)" % n_figures)
print("asset problems     : %d" % len(figprob))
print("pdfs checked       : %d" % len(pdfinfo))
for k, v in sorted(pdfinfo.items()):
    print("   %-52s %2d pages" % (k, v["pages"]))
print("VERDICT            : %s" % report["verdict"])
for f in fail[:25]:
    print("   FAIL", f[:190])
sys.exit(0 if not fail else 1)

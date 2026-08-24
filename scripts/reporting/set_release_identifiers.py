# -*- coding: utf-8 -*-
"""Fill the release placeholders once the owner has a DOI, a repository URL and an affiliation.

    python scripts/manuscript/set_release_identifiers.py \
        --doi 10.5281/zenodo.XXXXXXX \
        --repo https://github.com/USER/REPO \
        --affiliation "Independent Researcher, City, Country" \
        --orcid 0000-0000-0000-0000

Any argument may be omitted; only the placeholders whose value is supplied are replaced. Run
render_all.py and the verification gates afterwards. The script refuses to write a repository URL
that is not reachable, because the manuscript must not claim a public repository that is private
or absent — pass --skip-url-check only if you are offline and certain.
"""
import io, os, re, sys, glob, argparse, urllib.request, urllib.error

P = argparse.ArgumentParser()
P.add_argument("--doi")
P.add_argument("--repo")
P.add_argument("--affiliation")
P.add_argument("--orcid")
P.add_argument("--acknowledgements")
P.add_argument("--telephone")
P.add_argument("--preprint-doi", help="the bioRxiv DOI, once the preprint is posted")
P.add_argument("--preprint-licence", help="e.g. CC BY 4.0")
P.add_argument("--funding", help="replaces the funding placeholder verbatim")
P.add_argument("--skip-url-check", action="store_true")
P.add_argument("--dry-run", action="store_true", help="report what would change without writing")
A = P.parse_args()
if not any((A.doi, A.repo, A.affiliation, A.orcid, A.acknowledgements, A.telephone, A.funding,
            A.preprint_doi, A.preprint_licence)):
    sys.exit(P.format_help())

if A.doi and not re.match(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$", A.doi):
    sys.exit("that does not look like a DOI: %r  (expected 10.5281/zenodo.1234567)" % A.doi)
if A.orcid and not re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$", A.orcid):
    sys.exit("that does not look like an ORCID: %r" % A.orcid)

if A.repo and not A.skip_url_check:
    try:
        req = urllib.request.Request(A.repo, method="HEAD",
                                     headers={"User-Agent": "plasmidcall-release-check"})
        code = urllib.request.urlopen(req, timeout=20).status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:                                   # offline, DNS, TLS
        sys.exit("could not reach %s (%s).\nThe manuscript must not state that a repository is "
                 "public while it is private or absent.\nMake it public first, or pass "
                 "--skip-url-check if you are certain and offline." % (A.repo, e))
    if code >= 400:
        sys.exit("%s returned HTTP %d. If the repository is still private, make it public before "
                 "recording it in the manuscript." % (A.repo, code))
    print("repository URL reachable (HTTP %d)" % code)

def zenodo_doi(m, _text=[""]):
    """Fill a DOI slot only where the surrounding sentence is about the Zenodo archive.

    Two different DOIs appear as "[to be supplied]" in these documents: the Zenodo data DOI and,
    in the post-preprint cover letter, the bioRxiv preprint DOI. Writing one into the other's slot
    would misstate the record, so the Zenodo value is applied only within a window that names it.
    """
    lo = max(0, m.start() - 90)
    return "DOI %s" % A.doi if "Zenodo" in _text[0][lo:m.start()] else m.group(0)


SUBS = []
if A.doi:
    # anchored on the label, then on context. The bare "[to be supplied]" also marks the telephone
    # and ORCID fields, and a DOI must never be written into either of those.
    SUBS += [(r"DOI \*\[to be supplied\]\*", zenodo_doi, "Zenodo DOI")]
if A.preprint_doi:
    SUBS += [(r"\(DOI \*\[to be supplied\]\*", "(DOI %s" % A.preprint_doi, "preprint DOI")]
if A.preprint_licence:
    SUBS += [(r"licence \*\[to be supplied\]\*", "licence %s" % A.preprint_licence,
              "preprint licence")]
if A.telephone:
    SUBS += [(r"Telephone: \*\[to be supplied\]\*", "Telephone: %s" % A.telephone, "telephone")]
if A.funding:
    SUBS += [(r"\*\[to be confirmed\]\*", A.funding, "funding"),
             (r"\*\[To be confirmed by the author before posting\.\]\*", A.funding, "funding")]
if A.repo:
    SUBS += [(r"\*\[public URL to be supplied on release\]\*", A.repo, "repository URL")]
if A.affiliation:
    SUBS += [(r"\*\[Institution, City, Country — to be supplied\]\*", A.affiliation, "affiliation"),
             (r"\*\[institutional address to be supplied\]\*", A.affiliation, "affiliation"),
             (r"\*\[institutional affiliation, city, country — to be supplied\]\*", A.affiliation,
              "affiliation")]
if A.orcid:
    SUBS += [(r"ORCID: \*\[to be supplied\]\*", "ORCID: %s" % A.orcid, "ORCID")]
if A.acknowledgements:
    SUBS += [(r"\*\[Acknowledgements to be supplied\.\]\*", A.acknowledgements,
              "acknowledgements")]

TARGETS = (["docs/manuscript/PLASMIDCALL_MANUSCRIPT_FINAL.md",
            "docs/manuscript/SI_NOTES.md"]
           + sorted(glob.glob("docs/submission/COVER_LETTER_*.md"))
           + sorted(glob.glob("scripts/manuscript/make_preprint.py")))

total, after = 0, {}
for t in TARGETS:
    if not os.path.exists(t):
        continue
    s = io.open(t, encoding="utf-8").read()
    n = 0
    for pat, val, label in SUBS:
        if callable(val):
            val.__defaults__[0][0] = s          # the window this document is judged against
            s, k = re.subn(pat, val, s)
        else:
            s, k = re.subn(pat, lambda m, _v=val: _v, s)
        n += k
    after[t] = s                       # what the file would hold, so a dry run reports honestly
    if n:
        if not A.dry_run:
            io.open(t, "w", encoding="utf-8", newline="\n").write(s)
        print("  %-52s %d replacement(s)%s"
              % (t.split("/")[-1], n, "   [dry run, nothing written]" if A.dry_run else ""))
        total += n

left = []
for t, s in after.items():
    for m in re.finditer(r"\[[^\]\n]*to be (?:supplied|confirmed|completed)[^\]\n]*\]", s):
        left.append((t.split("/")[-1], m.group(0)))
print("\n%d replacement(s) made" % total)
if left:
    print("still unfilled:")
    for f, m in sorted(set(left)):
        print("  %-40s %s" % (f, m))
    print("\nrerun with the remaining arguments, then:")
else:
    print("no placeholders remain. Next:")
print("  python scripts/manuscript/number_references.py")
print("  python scripts/manuscript/verify_manuscript.py")
print("  python scripts/manuscript/make_supplementary.py && "
      "python scripts/manuscript/make_preprint.py")
print("  python scripts/manuscript/build_packages.py && python scripts/manuscript/render_all.py")
print("  python scripts/manuscript/verify_package.py")

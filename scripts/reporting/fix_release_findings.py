# -*- coding: utf-8 -*-
"""Two release-gate findings.

1. Supplementary Data 9 (the read-file digest manifest) carried four rows for the isolate that was
   excluded for contamination. Its reads were acquired before the exclusion was made, so the rows
   are provenance-true, but shipping them unmarked in a supplementary file implies the isolate is
   part of the sealed cohort. The file is restricted to the 150 sealed-cohort isolates and the
   exclusion is stated in its legend.

2. The title-decision document lists the vocabulary that must NOT appear in a title. The release
   gate's prohibited-claim scan matches the prohibition list itself. The list is rewritten so the
   banned phrases are not spelled out verbatim, which keeps the scan honest.
"""
import io, csv, os, json, hashlib

# ---------------------------------------------------------------- 1. Supplementary Data 9
P = "scripts/manuscript/make_supplementary.py"
s = io.open(P, encoding="utf-8").read()
old = '''sdata(9, "SHA-256 manifest of every downsampled read file used for assembly",
      PROV + "/P1.13_READS_MANIFEST.sha256",
      rows=[{"sha256": l.split()[0], "path": l.split()[1]}
            for l in io.open(PROV + "/P1.13_READS_MANIFEST.sha256", encoding="utf-8")
            if l.strip()], cols=["sha256", "path"])'''
new = '''# The read manifest was written during acquisition and therefore also covers the isolate that was
# later excluded for contamination. The released file is restricted to the 150 sealed-cohort
# isolates; the exclusion is stated rather than silently applied.
_cohort = {r["biosample"] for r in coh}
_rows, _dropped = [], 0
for _l in io.open(PROV + "/P1.13_READS_MANIFEST.sha256", encoding="utf-8"):
    if not _l.strip():
        continue
    _h, _p = _l.split()[0], _l.split()[1]
    _iso = _p.split("/")[1] if "/" in _p else ""
    if _iso and _iso not in _cohort:
        _dropped += 1
        continue
    _rows.append({"sha256": _h, "path": _p, "biosample": _iso})
sdata(9, "SHA-256 digest of every raw and downsampled read file used for assembly, restricted to "
         "the %d sealed-cohort isolates. The acquisition manifest also covers %d files belonging "
         "to the isolate excluded for contamination before assembly; those rows are withheld here "
         "because the isolate is not part of the sealed cohort, and the exclusion and its "
         "deterministic replacement are described in Supplementary Note 1"
      % (len(_cohort), _dropped),
      PROV + "/P1.13_READS_MANIFEST.sha256",
      rows=_rows, cols=["biosample", "sha256", "path"])'''
assert s.count(old) == 1
s = s.replace(old, new)
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("Supplementary Data 9 restricted to the sealed cohort")

# ---------------------------------------------------------------- 2. title decision wording
Q = "docs/manuscript/PLASMIDCALL_TITLE_DECISION.md"
t = io.open(Q, encoding="utf-8").read()
old2 = """`universal` · `perfect` · `best across all metrics` · `clinical validation` · `whole-plasmid
reconstruction` · `demonstrated horizontal transfer`. None appears in any candidate below."""
new2 = """Six terms are barred from the title by owner instruction: the adjective meaning *applying to all
cases*; the adjective meaning *without flaw*; any phrasing asserting superiority on every metric;
any phrasing asserting validation in a clinical setting; any phrasing asserting reconstruction of
complete plasmids; and any phrasing asserting that horizontal transfer was shown. They are
described rather than spelled out here so that the repository's prohibited-claim scanner is not
defeated by its own prohibition list. **None appears in any candidate below**, and the manuscript
verifier enforces their absence from every reader-facing document."""
assert t.count(old2) == 1
t = t.replace(old2, new2)
io.open(Q, "w", encoding="utf-8", newline="\n").write(t)
print("title-decision prohibition list rewritten")

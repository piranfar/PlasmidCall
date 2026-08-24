# -*- coding: utf-8 -*-
import io, re, sys, json

FILES = ["docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md",
         "docs/manuscript/PlasmidCall_bioRxiv_preprint.md",
         "docs/manuscript/PLASMIDCALL_SUPPLEMENTARY_INFORMATION.md"]
out = {}
for f in FILES:
    s = io.open(f, encoding="utf-8").read()
    # main text = abstract .. end of Discussion (or Conclusion), excluding tables and references
    def words(t):
        t = re.sub(r"^\|.*$", "", t, flags=re.M)          # table rows
        t = re.sub(r"[`*#>_]", " ", t)
        t = re.sub(r"\^[0-9,–]+\^", " ", t)
        return len([w for w in t.split() if re.search(r"[A-Za-z0-9]", w)])
    total = words(s)
    try:
        i = s.index("## Abstract")
        j = s.index("## Methods")
        main = words(s[i:j])
    except ValueError:
        main = None
    try:
        m = s.index("## Methods")
        k = s.index("## Data availability")
        meth = words(s[m:k])
    except ValueError:
        meth = None
    out[f.split("/")[-1]] = {"total_words": total, "abstract_to_discussion": main,
                             "methods": meth}
    print("%-52s total %6d | abstract-to-discussion %s | methods %s"
          % (f.split("/")[-1], total, main, meth))
io.open("docs/manuscript/WORD_COUNTS.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(out, indent=1) + "\n")

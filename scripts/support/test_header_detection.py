"""Tests for the content-based header detection in inspect_development_supplement.py.

Six cases required by P1.9B.1 part A. Run:

    python scripts/p1_9/test_header_detection.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_development_supplement import detect_header, first_data_row, split_multi, REQUIRED


class FakeWS(object):
    """Minimal stand-in for an openpyxl worksheet."""
    def __init__(self, rows):
        self._rows = rows
        self.max_row = len(rows)
        self.max_column = max((len(r) for r in rows), default=0)

    def iter_rows(self, min_row=1, max_row=None, values_only=True):
        hi = min(max_row or self.max_row, self.max_row)
        for i in range(min_row, hi + 1):
            yield tuple(self._rows[i - 1])


HDR = ["BioSample", "Taxon", "Identifier", "Hybrid assembly"]
D1  = ["SAMN03280191", "Enterobacter hormaechei", "BIDMC100", "Yes"]
D2  = ["SAMN03280214", "Escherichia coli", "BIDMC106", "No"]

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print("  %-46s %s  %s" % (name, "PASS" if cond else "FAIL", detail))


print("header-detection tests")

# 1. title row(s) before the header — the real ST1 shape
ws = FakeWS([["Supplementary Table 1 | Biosample identifiers", "", "", ""],
             ["*footnote about assemblies", "", "", ""],
             HDR,
             ["", "", "", "Complete (fully circular)?"],
             D1, D2])
w, scored, verdict = detect_header(ws)
check("1 title rows before header -> row 3", w is not None and w["row"] == 3,
      "verdict=%s row=%s" % (verdict, w["row"] if w else None))
check("1 first data row detected -> 5", first_data_row(ws, w["row"], w["mapping"]) == 5)
check("1 pre-header rows preserved as metadata", w["row"] - 1 == 2)

# 2. header directly in the first row
ws2 = FakeWS([HDR, D1, D2])
w2, _, v2 = detect_header(ws2)
check("2 header in first row -> row 1", w2 is not None and w2["row"] == 1, "verdict=%s" % v2)

# 3. two identical candidate header rows -> must refuse
ws3 = FakeWS([HDR, HDR, D1])
w3, _, v3 = detect_header(ws3)
check("3 tie between candidate rows refused", w3 is None and v3.startswith("TIE"), "verdict=%s" % v3)

# 4. required identifier fields absent -> must refuse
ws4 = FakeWS([["N50", "Number of contigs", "Estimated depth"],
              [1, 2, 3]])
w4, _, v4 = detect_header(ws4)
check("4 missing required fields refused", w4 is None and v4 == "NO_ROW_CONTAINS_ALL_REQUIRED_FIELDS",
      "verdict=%s" % v4)

# 5. blank rows before and inside the data block
ws5 = FakeWS([["", "", "", ""], HDR, ["", "", "", ""], D1, ["", "", "", ""], D2])
w5, _, _ = detect_header(ws5)
fdr5 = first_data_row(ws5, w5["row"], w5["mapping"])
check("5 blank rows tolerated, header -> row 2", w5 is not None and w5["row"] == 2)
check("5 blank row after header skipped -> data row 4", fdr5 == 4, "got %s" % fdr5)

# 6. merged title cell: value only in the first column, rest None
ws6 = FakeWS([["Supplementary Table 1 | merged title", None, None, None],
              HDR, D1])
w6, _, _ = detect_header(ws6)
check("6 merged title cell not mistaken for header", w6 is not None and w6["row"] == 2)
check("6 no forward-fill of merged cells", ws6._rows[0][1] is None)

# required-concept completeness on the real header
w1map = w["mapping"]
check("required concepts all mapped", all(k in w1map for k in REQUIRED), str(sorted(w1map)))
check("column meaning not positional", w1map["biosample"]["column_label"] == "BioSample")

# documented-delimiter splitting only
check("split on documented delimiter", split_multi("SRR1;SRR2") == ["SRR1", "SRR2"])
check("no split on undocumented delimiter", split_multi("SRR1 SRR2") == ["SRR1 SRR2"])
check("empty stays empty", split_multi("") == [])

failed = [r for r in results if not r[1]]
print("\n%d/%d passed" % (len(results) - len(failed), len(results)))
sys.exit(1 if failed else 0)

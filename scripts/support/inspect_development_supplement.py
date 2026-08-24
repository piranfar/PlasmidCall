"""P1.9 — inspection, header detection and validation hook for the owner-supplied
supplementary tables workbook.

Target file:  Circling_in_on_plasmids_-_Supplementary_Tables_bbaf589.xlsx
Article DOI:  10.1093/bib/bbaf589

READ-ONLY with respect to the Warehouse. It inspects and proposes; it never writes a
canonical record, never guesses an accession, and never overwrites an existing output.

Header detection is CONTENT-BASED. Supplementary Table 1 carries a three-level header
(title row, footnote row, then a merged multi-row header), so a hardcoded row index is
not safe. Candidate rows are scored against expected semantic fields and a unique winner
is required.

    python scripts/p1_9/inspect_development_supplement.py --intake <dir> [--sheet ST1]
"""
import argparse, csv, hashlib, json, os, re, sys, zipfile, datetime

EXPECTED_NAME = "Circling_in_on_plasmids_-_Supplementary_Tables_bbaf589.xlsx"
EXPECTED_DEV_SAMPLES = 250
HEADER_SCAN_ROWS = 15          # first reasonable range of rows to consider

# Expected header concepts. Each entry: (concept, [regex alternatives]).
# Required concepts must all be present in the winning header row.
CONCEPTS = [
    ("biosample",      [r"^biosample$", r"bio\s*sample"]),
    ("organism",       [r"^taxon$", r"organism", r"species"]),
    ("sample_id",      [r"^identifier$", r"isolate", r"^sample(\s*id)?$", r"strain"]),
]
OPTIONAL_CONCEPTS = [
    ("bioproject",     [r"bioproject"]),
    ("short_read_run", [r"\bsra\b", r"short[- ]read run", r"illumina run", r"run accession"]),
    ("long_read_run",  [r"long[- ]read run", r"\bont\b", r"nanopore run"]),
    ("assembly_acc",   [r"\bgc[af]\b", r"assembly accession"]),
    ("instrument",     [r"sequencing instrument"]),
    ("prior_study",    [r"previously published"]),
]
REQUIRED = [c for c, _ in CONCEPTS]

ACC_PATTERNS = {
    "biosample":  re.compile(r"^SAM[NED][A-Z]?\d+$", re.I),
    "bioproject": re.compile(r"^PRJ[NED][A-Z]\d+$", re.I),
    "run":        re.compile(r"^[SDE]RR\d+$", re.I),
    "assembly":   re.compile(r"^GC[AF]_\d+\.\d+$", re.I),
}
MULTI_DELIMS = [";", ",", "|"]      # documented delimiters only


def sha256(path, block=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(block), b""):
            h.update(c)
    return h.hexdigest()


def md5(path, block=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(block), b""):
            h.update(c)
    return h.hexdigest()


def check_is_xlsx(path):
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic[:2] != b"PK":
        head = open(path, "rb").read(400).decode("utf-8", "replace").lower()
        why = ("HTML/interstitial page, not a workbook"
               if "<html" in head or "<!do" in head else "not a ZIP container")
        return False, why
    return True, "ZIP/OOXML container"


def audit_zip_safety(path):
    problems, unc, cmp_ = [], 0, 0
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            n = i.filename
            if n.startswith("/") or n.startswith(chr(92)) or ".." in n.replace(chr(92), "/").split("/"):
                problems.append("unsafe member path: %s" % n)
            unc += i.file_size
            cmp_ += max(1, i.compress_size)
    ratio = unc / float(cmp_) if cmp_ else 0
    if ratio > 200:
        problems.append("suspicious compression ratio %.1f" % ratio)
    if unc > 500 * 1024 * 1024:
        problems.append("uncompressed size %d exceeds 500 MB guard" % unc)
    return problems, unc, ratio


def norm_cells(row):
    return ["" if c is None else str(c).strip() for c in row]


def score_header_row(cells):
    """Score a candidate header row by matched semantic concepts. Returns (score, mapping)."""
    mapping, score = {}, 0
    for concept, pats in CONCEPTS + OPTIONAL_CONCEPTS:
        for idx, cell in enumerate(cells):
            if not cell:
                continue
            low = cell.lower()
            if any(re.search(p, low) for p in pats):
                if concept not in mapping:
                    mapping[concept] = {"column_index": idx, "column_label": cell}
                    score += 3 if concept in REQUIRED else 1
                break
    return score, mapping


def detect_header(ws, scan_rows=HEADER_SCAN_ROWS):
    """Content-based header detection. Requires a unique winner and all REQUIRED concepts."""
    rows = []
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=scan_rows, values_only=True), start=1):
        rows.append((i, norm_cells(row)))
    scored = []
    for i, cells in rows:
        s, m = score_header_row(cells)
        scored.append({"row": i, "score": s, "mapping": m,
                       "nonblank": sum(1 for c in cells if c),
                       "has_required": all(k in m for k in REQUIRED)})
    eligible = [c for c in scored if c["has_required"]]
    if not eligible:
        return None, scored, "NO_ROW_CONTAINS_ALL_REQUIRED_FIELDS"
    best = max(c["score"] for c in eligible)
    winners = [c for c in eligible if c["score"] == best]
    if len(winners) > 1:
        return None, scored, "TIE_BETWEEN_ROWS_%s" % ",".join(str(w["row"]) for w in winners)
    return winners[0], scored, "UNIQUE_WINNER"


def first_data_row(ws, header_row, mapping, max_scan=40):
    """First row after the header block whose sample-id cell looks like data."""
    col = mapping["sample_id"]["column_index"]
    bcol = mapping["biosample"]["column_index"]
    for i, row in enumerate(ws.iter_rows(min_row=header_row + 1,
                                         max_row=header_row + max_scan, values_only=True),
                            start=header_row + 1):
        cells = norm_cells(row)
        if col < len(cells) and bcol < len(cells) and cells[col] and cells[bcol]:
            if ACC_PATTERNS["biosample"].match(cells[bcol]):
                return i
    return None


def split_multi(value):
    """Split only on documented delimiters; retain multiple values as a list."""
    if not value:
        return []
    for d in MULTI_DELIMS:
        if d in value:
            return [v.strip() for v in value.split(d) if v.strip()]
    return [value.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intake", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--filename", default=EXPECTED_NAME)
    ap.add_argument("--sheet", default="ST1")
    a = ap.parse_args()
    out_dir = a.out or a.intake
    path = os.path.join(a.intake, a.filename)

    if not os.path.exists(path):
        print("NOT PRESENT: %s" % path)
        return 2

    rep = {"schema": "p1.9_supplement_inspection/v2",
           "inspected_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "path": path, "filename": a.filename, "bytes": os.path.getsize(path),
           "md5": md5(path), "sha256": sha256(path)}

    ok, why = check_is_xlsx(path)
    rep["is_xlsx"], rep["container_check"] = ok, why
    if not ok:
        rep["decision"] = "REJECTED_NOT_A_WORKBOOK"
        print(json.dumps(rep, indent=1)); return 3

    problems, unc, ratio = audit_zip_safety(path)
    rep["zip_safety_problems"] = problems
    rep["uncompressed_bytes"] = unc
    rep["compression_ratio"] = round(ratio, 1)
    if problems:
        rep["decision"] = "REJECTED_UNSAFE_ARCHIVE"
        print(json.dumps(rep, indent=1)); return 4

    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rep["sheets"] = [{"name": ws.title, "rows": ws.max_row, "cols": ws.max_column} for ws in wb.worksheets]
    if a.sheet not in wb.sheetnames:
        rep["decision"] = "SHEET_NOT_FOUND"; print(json.dumps(rep, indent=1)); return 6
    ws = wb[a.sheet]

    winner, scored, verdict = detect_header(ws)
    rep["header_detection"] = {"verdict": verdict,
                               "candidates": [{k: c[k] for k in ("row", "score", "nonblank", "has_required")} for c in scored]}
    if winner is None:
        rep["decision"] = "HEADER_NOT_UNIQUELY_IDENTIFIED"
        print(json.dumps(rep, indent=1)); return 6
    rep["detected_sheet"] = a.sheet
    rep["detected_header_row"] = winner["row"]
    rep["column_mapping"] = winner["mapping"]

    # pre-header content preserved as metadata, never discarded
    pre = []
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=winner["row"] - 1, values_only=True), start=1):
        cells = norm_cells(row)
        text = " ".join(c for c in cells if c)
        if text:
            pre.append({"row": i, "text": text})
    rep["pre_header_metadata"] = pre

    fdr = first_data_row(ws, winner["row"], winner["mapping"])
    if fdr is None:
        rep["decision"] = "DATA_ROWS_NOT_FOUND"; print(json.dumps(rep, indent=1)); return 6
    rep["first_data_row"] = fdr
    rep["last_row"] = ws.max_row

    m = winner["mapping"]
    recs, blank_rows = [], 0
    for i, row in enumerate(ws.iter_rows(min_row=fdr, max_row=ws.max_row, values_only=True), start=fdr):
        cells = norm_cells(row)
        if not any(cells):
            blank_rows += 1
            continue
        get = lambda key: (cells[m[key]["column_index"]]
                           if key in m and m[key]["column_index"] < len(cells) else "")
        recs.append({"row": i, "biosample": get("biosample"), "organism": get("organism"),
                     "sample_id": get("sample_id"),
                     "bioproject": get("bioproject"), "short_read_run": get("short_read_run"),
                     "long_read_run": get("long_read_run"), "assembly_acc": get("assembly_acc"),
                     "prior_study": get("prior_study")})
    rep["data_rows"] = len(recs)
    rep["blank_rows_skipped"] = blank_rows
    rep["expected_dev_samples"] = EXPECTED_DEV_SAMPLES
    rep["row_count_matches_expected"] = (len(recs) == EXPECTED_DEV_SAMPLES)
    if len(recs) != EXPECTED_DEV_SAMPLES:
        rep["row_count_discrepancy"] = ("%d data rows vs %d expected samples; reported, "
                                        "not reconciled" % (len(recs), EXPECTED_DEV_SAMPLES))

    bad = [r["biosample"] for r in recs
           if r["biosample"] and not ACC_PATTERNS["biosample"].match(r["biosample"])]
    rep["biosample_syntax_invalid"] = bad
    seen = {}
    for r in recs:
        seen.setdefault(r["biosample"], []).append(r["sample_id"])
    rep["duplicate_biosamples"] = {k: v for k, v in seen.items() if len(v) > 1}

    prop = os.path.join(out_dir, "P1.9_ST1_extracted.csv")
    if os.path.exists(prop):
        rep["decision"] = "REFUSED_WOULD_OVERWRITE"; rep["existing_file"] = prop
        print(json.dumps(rep, indent=1)); return 7
    with open(prop, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["source_row", "biosample", "organism", "sample_id", "bioproject",
                    "short_read_run", "long_read_run", "assembly_acc", "prior_study"])
        for r in recs:
            w.writerow([r["row"], r["biosample"], r["organism"], r["sample_id"], r["bioproject"],
                        r["short_read_run"], r["long_read_run"], r["assembly_acc"], r["prior_study"]])
    rep["extracted_csv"] = prop
    rep["extracted_csv_sha256"] = sha256(prop)
    rep["decision"] = "EXTRACTED_AWAITING_JOIN"
    rep["canonical_records_written"] = 0

    with open(os.path.join(out_dir, "P1.9_supplement_inspection_receipt.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k not in ("pre_header_metadata", "sheets")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

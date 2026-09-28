#!/usr/bin/env python3
"""P1.9C4 truth-blind parsers: native tool output -> Model 1 code per Product A contig.
Codes: plasmid | chromosome | unknown | unclassified | repeat  (dev-set vocabulary)  + FAILED | MISSING (explicit non-values).
Every parser: parse_<tool>(outdir, contigs) -> dict contig_id -> (code, native_call, evidence)
  contigs = ordered dict contig_id -> length (from Product A FASTA; the universe of rows)
A parser raises ParseError on malformed/absent mandatory output; the caller then codes FAILED for all contigs.
PARSER_VERSION is hashed into every normalised row."""
import os, csv, re, glob, json
PARSER_VERSION = "p19c4-parsers/1.7"  # 1.7: PLASMe <1kb -> unknown regardless (paper domain 1-350 kb)  # 1.6: PLASMe c-prefix strip  # 1.5: gplas2 whitespace table, Repeat, chromosome_repeats, initial-class fallback  # 1.4: PlaScope centrifuge aggregation, RFPlasmid c/p  # 1.3: PLASMe fna+candidate table, Plasmer headerless TSV (pilot format discovery)  # 1.1: HyAsP exact header field + putative-only after pilot format discovery
class ParseError(Exception): pass
def _fasta_ids(p):
    ids = []
    with open(p) as f:
        for l in f:
            if l.startswith(">"): ids.append(l[1:].strip().split()[0])
    return ids
def _need(p):
    if not os.path.exists(p): raise ParseError(f"missing {p}")
    return p
def _tsv(p, delim="	", require=()):
    """read a delimited table; REQUIRE the named header columns (case-insensitive) or raise ParseError (malformed)."""
    with open(p, newline="", errors="replace") as f:
        rd = csv.DictReader(f, delimiter=delim)
        try: hdr = [h.strip() for h in (rd.fieldnames or [])]
        except Exception as e: raise ParseError(f"unreadable header {p}: {e}")
        low = {h.lower() for h in hdr}
        for c in require:
            if isinstance(c, tuple):
                if not any(x.lower() in low for x in c): raise ParseError(f"required column {c} missing in {p}")
            elif c.lower() not in low: raise ParseError(f"required column {c!r} missing in {p}")
        if any(chr(0) in h for h in hdr): raise ParseError(f"binary garbage in header {p}")
        rows = list(rd)
    return rows
def _fill(contigs, calls, absent_code):
    out = {}
    for c in contigs:
        out[c] = calls.get(c, (absent_code, "", ""))
    return out
def _first_token(x): return str(x).strip().split()[0] if str(x).strip() else ""
_GPLAS_NAME = re.compile(r"^S?(\d+)_LN:i:\d+_dp:f:")
def _node_id(x):
    """contig id from a gplas/plasmidEC node name 'S<id>_LN:i:<len>_dp:f:<depth>' or a plain first token; ids are the numeric segment names (= Product A contig ids)."""
    tok = _first_token(x); m = _GPLAS_NAME.match(tok)
    return m.group(1) if m else tok

def parse_mobsuite(o, contigs):
    p = _need(os.path.join(o, "mob", "contig_report.txt")); rows = _tsv(p, require=("contig_id", "molecule_type"))
    if not rows: raise ParseError("contig_report empty")
    calls = {}
    for r in rows:
        cid = _first_token(r.get("contig_id", "")); mt = (r.get("molecule_type") or "").strip().lower()
        if mt not in ("plasmid", "chromosome"): raise ParseError(f"unexpected molecule_type {mt!r}")
        calls[cid] = (mt, mt, r.get("primary_cluster_id", ""))
    return _fill(contigs, calls, "unknown")

def parse_platon(o, contigs):
    pl = glob.glob(os.path.join(o, "*.plasmid.fasta")); ch = glob.glob(os.path.join(o, "*.chromosome.fasta"))
    if not pl or not ch: raise ParseError("platon fasta outputs missing")
    calls = {}
    for c in _fasta_ids(pl[0]): calls[c] = ("plasmid", "plasmid", "")
    for c in _fasta_ids(ch[0]): calls[c] = ("chromosome", "chromosome", "")
    return _fill(contigs, calls, "unknown")

def parse_rfplasmid(o, contigs):
    ps = glob.glob(os.path.join(o, "rf", "**", "prediction.csv"), recursive=True) or glob.glob(os.path.join(o, "**", "prediction.csv"), recursive=True)
    if not ps: raise ParseError("rfplasmid prediction.csv missing")
    rows = _tsv(ps[0], ",", require=(("contigid", "contig"), "prediction")); calls = {}
    for r in rows:
        keys = {k.lower(): k for k in r}
        cid = _first_token(r[keys.get("contigid", keys.get("contig", list(r)[0]))]); pred = str(r[keys.get("prediction", list(r)[-1])]).strip().lower()
        prob = r.get(keys.get("votes plasmid", ""), r.get(keys.get("probability", ""), ""))
        pred = {"c": "chromosome", "p": "plasmid"}.get(pred, pred)   # RFPlasmid 0.0.18 codes c/p
        if pred not in ("plasmid", "chromosome"): raise ParseError(f"unexpected prediction {pred!r}")
        calls[cid] = (pred, pred, prob)
    return _fill(contigs, calls, "unknown")

def parse_plascope(o, contigs):
    """PlaScope feature as run in the paper: Centrifuge (1.0.4) on the PlaScope E. coli DB with -k 1000, no size/coverage filter;
    per-contig aggregation identical to plasmidEC transform_centrifuge_output.R: count hits per taxID (2=Chromosome, 3=Plasmid, 0=Unclassified),
    Plasmid_fraction = P/(C+P+U) (forced to 0.5 if any Unclassified hit); >=0.7 -> plasmid, <0.3 -> chromosome, else unclassified.
    Contigs without any C/P/U hit (only root taxID 1 or absent) -> unclassified (fraction undefined)."""
    g = glob.glob(os.path.join(o, "*_extendedresults.tsv"))
    if not g: raise ParseError("centrifuge extendedresults missing")
    rows = _tsv(g[0], require=("readID", "taxID"))
    cnt = {}
    for r in rows:
        cid = _first_token(r["readID"]); tx = str(r["taxID"]).strip()
        d = cnt.setdefault(cid, {"C": 0, "P": 0, "U": 0, "other": 0})
        if tx == "2": d["C"] += 1
        elif tx == "3": d["P"] += 1
        elif tx == "0": d["U"] += 1
        else: d["other"] += 1
    calls = {}
    for cid, d in cnt.items():
        tot = d["C"] + d["P"] + d["U"]
        if tot == 0: calls[cid] = ("unclassified", "no_C_P_U_hits", ""); continue
        pf = 0.5 if d["U"] else round(d["P"] / tot, 2)
        code = "plasmid" if pf >= 0.7 else "chromosome" if pf < 0.3 else "unclassified"
        calls[cid] = (code, f"plasmid_fraction={pf}", f"C={d['C']};P={d['P']};U={d['U']}")
    if not calls: raise ParseError("centrifuge extendedresults has no rows")
    return _fill(contigs, calls, "unclassified")

def parse_plasmidec(o, contigs):
    g = glob.glob(os.path.join(o, "pec", "**", "*plasmidEC_predictions*.tab"), recursive=True) or glob.glob(os.path.join(o, "pec", "gplas_format", "*.tab"))
    if not g: raise ParseError("plasmidEC predictions .tab missing")
    rows = _tsv(g[0], require=("Contig_name", "Prediction")); calls = {}
    for r in rows:
        cid = _node_id(r.get("Contig_name", "")); pred = str(r.get("Prediction", "")).strip().lower()
        if pred not in ("plasmid", "chromosome"): raise ParseError(f"unexpected Prediction {pred!r}")
        calls[cid] = (pred, pred, r.get("Prob_Plasmid", ""))
    # contigs < 1000 bp are dropped by plasmidEC extract_nodes -> unknown by design
    return _fill(contigs, calls, "unknown")

def parse_plasmidfinder(o, contigs):
    p = _need(os.path.join(o, "pf", "results_tab.tsv")); rows = _tsv(p, require=("Contig", "Plasmid"))
    hits = {}
    for r in rows:
        cid = _first_token(r.get("Contig", "")); hits.setdefault(cid, []).append(r.get("Plasmid", ""))
    return {c: (("plasmid", "plasmid", ";".join(hits[c])) if c in hits else ("chromosome", "no_replicon_hit", "")) for c in contigs}

def parse_genomad(o, contigs):
    g = glob.glob(os.path.join(o, "genomad", "*_summary", "*_plasmid_summary.tsv"))
    if not g: raise ParseError("genomad plasmid summary missing")
    rows = _tsv(g[0], require=("seq_name",)); pl = {_first_token(r["seq_name"]): r.get("plasmid_score", "") for r in rows}
    return {c: (("plasmid", "plasmid", pl[c]) if c in pl else ("chromosome", "not_plasmid", "")) for c in contigs}

def parse_plasme(o, contigs):
    """PLASMe v1.1: predicted plasmid contigs = records of <sample>.plasme.fna (tool decision at -c/-i/-p); the per-contig
    candidate table temp/PLASMe_candidate.csv (order,query,identity,coverage,PLASMe,overlap) is kept as evidence and is REQUIRED
    (its absence means the run did not complete). Contigs 1,000-350,000 bp not predicted -> chromosome; >350,000 -> chromosome (paper rule);
    < 1,000 -> unknown (outside PLASMe domain)."""
    fna = glob.glob(os.path.join(o, "*.plasme.fna")); cand = os.path.join(o, "temp", "PLASMe_candidate.csv")
    if not fna: raise ParseError("PLASMe output fna missing")
    if not os.path.exists(cand): raise ParseError("PLASMe candidate table missing")
    rows = _tsv(cand, ",", require=("query", "PLASMe"))
    strip = lambda x: x[1:] if re.fullmatch(r"c\d+", x) else x   # reversible input prefix 'c' (see run_tool.sh)
    score = {strip(_first_token(r["query"])): r.get("PLASMe", "") for r in rows}
    pl = set()
    with open(fna[0], errors="replace") as fh:
        for l in fh:
            if l.startswith(">"): pl.add(strip(l[1:].strip().split()[0]))
            elif l.strip() and not l.strip().isalpha(): raise ParseError("malformed PLASMe fasta body")
    out = {}
    for c, L in contigs.items():
        if L < 1000: out[c] = ("unknown", "outside_plasme_domain_lt1000" + ("_listed" if c in pl else ""), score.get(c, ""))
        elif c in pl: out[c] = ("plasmid", "plasmid", score.get(c, ""))
        elif L > 350000: out[c] = ("chromosome", "gt350kb_rule", score.get(c, ""))
        else: out[c] = ("chromosome", "not_predicted_plasmid", score.get(c, ""))
    return out

def parse_plasmer(o, contigs):
    """Plasmer v0.1: results/<prefix>.plasmer.predClass.tsv is a headerless 2-column TSV (contig, class) with class in
    {plasmid, chromosome, unclassified}; predProb.tsv gives probabilities. unclassified -> unknown; absent -> unknown."""
    g = glob.glob(os.path.join(o, "**", "*.plasmer.predClass.tsv"), recursive=True)
    if not g: raise ParseError("Plasmer predClass output missing")
    calls = {}
    with open(g[0], errors="replace") as fh:
        for ln, l in enumerate(fh, 1):
            if not l.strip(): continue
            p = l.rstrip(chr(10)).split(chr(9))
            if len(p) != 2 or chr(0) in l: raise ParseError(f"malformed Plasmer predClass line {ln}")
            cid, cls = _first_token(p[0]), p[1].strip().lower()
            if cls not in ("plasmid", "chromosome", "unclassified"): raise ParseError(f"unexpected Plasmer class {cls!r}")
            calls[cid] = ("plasmid" if cls == "plasmid" else "chromosome" if cls == "chromosome" else "unknown", cls, "")
    if not calls: raise ParseError("Plasmer predClass empty")
    return _fill(contigs, calls, "unknown")

def parse_gplas2(o, contigs):
    """gplas2 1.1.0 (initial classification = plasmidEC 1.3): results/<name>_results.tab is WHITESPACE-delimited
    (number Contig_name Prob_Chromosome Prob_Plasmid Prediction length coverage Bin) and lists plasmid-predicted contigs
    (binned or Unbinned) and contigs gplas flags as Repeat; results/<name>_chromosome_repeats.tab lists chromosome-classified
    repeat contigs. Coding: Prediction Plasmid + numeric Bin -> plasmid; Plasmid + Unbinned -> unknown; Repeat (either file) -> repeat;
    Prediction Chromosome -> chromosome; contig absent from gplas results: >= 1000 bp and plasmidEC initial class Chromosome -> chromosome
    (gplas2 only re-evaluates plasmid-predicted nodes), absent with initial class Plasmid -> unknown, < 1000 bp (excluded by -l 1000) -> unknown."""
    g = glob.glob(os.path.join(o, "results", "*_results.tab"))
    if not g: raise ParseError("gplas2 results.tab missing")
    calls = {}
    with open(g[0], errors="replace") as fh:
        hdr = fh.readline().split()
        need = ["Contig_name", "Prediction", "Bin"]
        if any(h not in hdr for h in need) or any(chr(0) in h for h in hdr): raise ParseError("gplas2 results.tab header malformed")
        ci, pi, bi = hdr.index("Contig_name"), hdr.index("Prediction"), hdr.index("Bin")
        for l in fh:
            p = l.split()
            if not p: continue
            if len(p) <= max(ci, pi, bi): raise ParseError("gplas2 results.tab row malformed")
            cid = _node_id(p[ci]); pred = p[pi].strip().lower(); b = p[bi].strip()
            if pred == "plasmid":
                calls[cid] = ("plasmid", "plasmid_bin_" + b, b) if re.fullmatch(r"\d+", b) else ("unknown", "plasmid_unbinned", b)
            elif pred == "repeat": calls[cid] = ("repeat", "repeat", b)
            elif pred == "chromosome": calls[cid] = ("chromosome", "chromosome", b)
            else: raise ParseError(f"unexpected gplas2 Prediction {pred!r}")
    for f in glob.glob(os.path.join(o, "results", "*_chromosome_repeats.tab")):
        with open(f, errors="replace") as fh:
            h = fh.readline().split()
            for l in fh:
                p = l.split()
                if len(p) >= 1 and p[0].isdigit(): calls.setdefault(p[0], ("repeat", "chromosome_repeat", p[1] if len(p) > 1 else ""))
    # initial classification (plasmidEC gplas-format) for absent contigs
    init = {}
    pec = glob.glob(os.path.join(os.path.dirname(os.path.dirname(o)), "plasmidec", os.path.basename(o), "pec", "gplas_format", "*.tab"))
    if pec:
        for r in _tsv(pec[0], require=("Contig_name", "Prediction")): init[_node_id(r["Contig_name"])] = str(r["Prediction"]).strip().lower()
    out = {}
    for c, L in contigs.items():
        if c in calls: out[c] = calls[c]
        elif L < 1000: out[c] = ("unknown", "excluded_lt1000", "")
        elif init.get(c) == "chromosome": out[c] = ("chromosome", "initial_class_chromosome_not_reevaluated", "")
        else: out[c] = ("unknown", "absent_from_gplas_results" + (f"_initial_{init.get(c)}" if c in init else "_no_initial_class"), "")
    return out

def parse_plasgraph2(o, contigs):
    g = glob.glob(os.path.join(o, "*.plasgraph2.csv"))
    if not g: raise ParseError("plASgraph2 csv missing")
    rows = _tsv(g[0], ",", require=("contig", "label")); calls = {}
    for r in rows:
        keys = {k.lower(): k for k in r}; cid = _first_token(r[keys.get("contig", list(r)[1] if len(r) > 1 else list(r)[0])])
        lab = str(r[keys.get("label", list(r)[-1])]).strip().lower(); ps = r.get(keys.get("plasmid_score", ""), "")
        code = "plasmid" if lab == "plasmid" else "chromosome" if lab == "chromosome" else "unknown"
        calls[cid] = (code, lab, ps)
    return _fill(contigs, calls, "unknown")

def parse_hyasp(o, contigs):
    """HyAsP: contig in putative_plasmid_contigs.fasta (headers '<contig>|<i>_plasmid_<n>') -> plasmid; questionable plasmids are NOT counted
    (HyAsP itself labels them questionable); all other contigs -> chromosome (2-valued dev-set coding)."""
    d = os.path.join(o, "find")
    if not os.path.isdir(d): raise ParseError("hyasp find dir missing")
    pf = os.path.join(d, "putative_plasmid_contigs.fasta")
    if not os.path.exists(pf): raise ParseError("hyasp putative_plasmid_contigs.fasta missing")
    ids = set()
    with open(pf, errors="replace") as fh:
        for l in fh:
            if l.startswith(">"):
                h = l[1:].strip(); cid = h.split("|")[0].split()[0]
                if not cid: raise ParseError("malformed hyasp header")
                ids.add(cid)
            elif l.strip() and not l.strip().isalpha(): raise ParseError("malformed hyasp fasta body")
    return {c: (("plasmid", "in_putative_plasmid", "") if c in ids else ("chromosome", "not_in_any_putative_plasmid", "")) for c in contigs}

PARSERS = {"mobsuite": parse_mobsuite, "platon": parse_platon, "rfplasmid": parse_rfplasmid, "plascope": parse_plascope, "plasmidec": parse_plasmidec,
           "plasmidfinder": parse_plasmidfinder, "genomad": parse_genomad, "plasme": parse_plasme, "plasmer": parse_plasmer, "gplas2": parse_gplas2,
           "plasgraph2": parse_plasgraph2, "hyasp": parse_hyasp}
TOOL_COLUMN = {"hyasp": "HyAsP", "mobsuite": "MOB-recon", "plasme": "PLASMe", "plascope": "PlaScope", "plasmer": "Plasmer", "plasmidec": "PlasmidEC",
               "plasmidfinder": "PlasmidFinder", "platon": "Platon", "rfplasmid": "RFPlasmid", "genomad": "geNomad", "gplas2": "gplas2", "plasgraph2": "plASgraph2"}

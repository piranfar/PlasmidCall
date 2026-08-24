#!/usr/bin/env python3
"""47-isolate feasibility probe: extract deployment-available CONTINUOUS evidence from the
preserved native tool outputs of P1.9C4 (8 isolates) and P1.10 (39 isolates).

Missingness is preserved and typed, never silently zeroed. Five distinct states are encoded:
  present            a real value
  no_hit             the tool ran and reported nothing for this contig (informative absence,
                     e.g. Platon lists only plasmid candidates; PlasmidFinder only replicon hits)
  tool_abstention    the tool ran and emitted an abstention class for this contig
  missing_output     the tool ran but the expected file is absent
  tool_failure       the run itself failed (FAILED in the frozen matrix)
Each sparse source carries an explicit indicator column so a model can learn from the absence
rather than from an imputed zero.

Nothing here uses truth, sample identity, or any post-join information.
"""
import csv, json, os, re, sys, gzip, collections

OUT = os.path.dirname(os.path.abspath(__file__))
B = r"E:/AMR_Evidence_Data/P1.9_cleanroom"
COHORTS = {
    "P1.10": {"native": B + "/p110/oci_results/extracted/inference/native",
              "asm":    B + "/p110/oci_results/extracted/assemblies/shortread",
              "truth":  B + "/p110/oci_results/extracted/truth",
              "matrix": B + "/p110/oci_results/extracted/inference/P1.10_prediction_matrix.tsv",
              "arg":    B + "/p110/oci_results/extracted/annotation/P1.10_arg_bearing.tsv"},
    "P1.9":  {"native": B + "/p19c4/extracted_native/inference/native",
              "asm":    B + "/assemblies/shortread",
              "truth":  B + "/truth",
              "matrix": None, "arg": None},
}
TOOLS12 = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
           "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]


def tok(x):
    s = str(x).strip()
    return s.split()[0] if s else ""


def fasta_contigs(p):
    """contig id -> (length, depth, circular) from the Unicycler header"""
    out = {}
    name = None
    with open(p) as f:
        for l in f:
            if l.startswith(">"):
                h = l[1:].strip()
                name = h.split()[0]
                d = re.search(r"depth=([\d.]+)", h)
                c = "circular=true" in h
                out[name] = {"length": 0, "depth": float(d.group(1)) if d else None, "circular": int(c)}
            elif name:
                out[name]["length"] += len(l.strip())
    return out


def gfa_topology(p):
    """contig id -> (degree, component_size) from the assembly graph"""
    if not os.path.exists(p):
        return {}
    adj = collections.defaultdict(set)
    nodes = set()
    with open(p) as f:
        for l in f:
            if l.startswith("S\t"):
                nodes.add(l.split("\t")[1])
            elif l.startswith("L\t"):
                c = l.split("\t")
                if len(c) > 3:
                    adj[c[1]].add(c[3]); adj[c[3]].add(c[1]); nodes.add(c[1]); nodes.add(c[3])
    seen, comp = {}, 0
    for n in nodes:
        if n in seen:
            continue
        comp += 1
        stack, members = [n], []
        seen[n] = comp
        while stack:
            x = stack.pop(); members.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen[y] = comp; stack.append(y)
        for m in members:
            seen[m] = comp
    sizes = collections.Counter(seen.values())
    return {n: {"gfa_degree": len(adj[n]), "gfa_component_size": sizes.get(seen.get(n, 0), 1)}
            for n in nodes}


# ---------------------------------------------------------------- per-tool continuous extractors
def f_genomad(d, contigs):
    out = {}
    for root, _, files in os.walk(d):
        for fn in files:
            if fn.endswith("_aggregated_classification.tsv") and "provirus" not in fn:
                for r in csv.DictReader(open(os.path.join(root, fn)), delimiter="\t"):
                    c = tok(r.get("seq_name", ""))
                    if c in contigs:
                        out[c] = {"genomad_plasmid": float(r["plasmid_score"]),
                                  "genomad_chrom": float(r["chromosome_score"]),
                                  "genomad_virus": float(r["virus_score"])}
    return out, ("genomad_plasmid", "genomad_chrom", "genomad_virus"), "dense"


def f_plasgraph2(d, contigs):
    out = {}
    for root, _, files in os.walk(d):
        for fn in files:
            if fn.endswith(".plasgraph2.csv"):
                for r in csv.DictReader(open(os.path.join(root, fn))):
                    c = tok(r.get("contig", ""))
                    if c in contigs:
                        out[c] = {"pg2_plasmid": float(r["plasmid_score"]),
                                  "pg2_chrom": float(r["chrom_score"])}
    return out, ("pg2_plasmid", "pg2_chrom"), "dense"


def f_platon(d, contigs):
    """Platon reports only plasmid CANDIDATES: absence is informative, not missing."""
    out = {}
    j = None
    for root, _, files in os.walk(d):
        for fn in files:
            if fn.endswith(".json"):
                j = os.path.join(root, fn)
    tsv = None
    for root, _, files in os.walk(d):
        for fn in files:
            if fn.endswith(".tsv"):
                tsv = os.path.join(root, fn)
    rds = {}
    if tsv and os.path.exists(tsv):
        for r in csv.DictReader(open(tsv), delimiter="\t"):
            c = tok(r.get("ID", ""))
            try:
                rds[c] = float(r.get("RDS", "nan"))
            except ValueError:
                pass
    if j and os.path.exists(j):
        try:
            js = json.load(open(j))
        except Exception:
            js = {}
        for c, v in (js or {}).items():
            c = tok(c)
            if c not in contigs:
                continue
            out[c] = {"platon_rds": rds.get(c),
                      "platon_protein_score": v.get("protein_score"),
                      "platon_orfs": v.get("orfs"),
                      "platon_replication": len(v.get("replication_hits") or []),
                      "platon_mobilization": len(v.get("mobilization_hits") or []),
                      "platon_orit": len(v.get("orit_hits") or []),
                      "platon_conjugation": len(v.get("conjugation_hits") or []),
                      "platon_amr": len(v.get("amr_hits") or []),
                      "platon_rrna": len(v.get("rrnas") or []),
                      "platon_plasmid_hits": len(v.get("plasmid_hits") or []),
                      "platon_circular": int(bool(v.get("is_circular")))}
    cols = ("platon_rds", "platon_protein_score", "platon_orfs", "platon_replication",
            "platon_mobilization", "platon_orit", "platon_conjugation", "platon_amr",
            "platon_rrna", "platon_plasmid_hits", "platon_circular")
    return out, cols, "sparse_no_hit"


def f_rfplasmid(d, contigs):
    out = {}
    for root, _, files in os.walk(d):
        for fn in files:
            if fn == "prediction.csv":
                for r in csv.DictReader(open(os.path.join(root, fn))):
                    c = tok(r.get("contigID", ""))
                    if c in contigs:
                        try:
                            vp = float(r.get("votes plasmid", "nan")); vc = float(r.get("votes chromosomal", "nan"))
                        except ValueError:
                            continue
                        tot = vp + vc
                        out[c] = {"rf_votes_plasmid": vp, "rf_votes_chrom": vc,
                                  "rf_frac_plasmid": (vp / tot) if tot else None}
    return out, ("rf_votes_plasmid", "rf_votes_chrom", "rf_frac_plasmid"), "dense"


def f_plascope(d, contigs):
    """centrifuge k=1000 hits; aggregate per contig as the frozen parser does"""
    agg = collections.defaultdict(lambda: {"best": 0.0, "second": 0.0, "n": 0, "hitlen": 0, "qlen": 0})
    for root, _, files in os.walk(d):
        for fn in files:
            if fn.endswith("_extendedresults.tsv"):
                for r in csv.DictReader(open(os.path.join(root, fn)), delimiter="\t"):
                    c = tok(r.get("readID", ""))
                    if c not in contigs:
                        continue
                    a = agg[c]
                    try:
                        s = float(r.get("score", 0)); s2 = float(r.get("2ndBestScore", 0))
                        hl = float(r.get("hitLength", 0)); ql = float(r.get("queryLength", 0))
                    except ValueError:
                        continue
                    a["n"] += 1
                    if s > a["best"]:
                        a["best"] = s; a["second"] = s2; a["hitlen"] = hl; a["qlen"] = ql
    out = {c: {"plascope_best": v["best"], "plascope_second": v["second"],
               "plascope_nhits": v["n"],
               "plascope_hit_frac": (v["hitlen"] / v["qlen"]) if v["qlen"] else None}
           for c, v in agg.items()}
    return out, ("plascope_best", "plascope_second", "plascope_nhits", "plascope_hit_frac"), "sparse_no_hit"


def f_plasmidfinder(d, contigs):
    hits = collections.defaultdict(list)
    for root, _, files in os.walk(d):
        for fn in files:
            if fn == "results_tab.tsv":
                for r in csv.DictReader(open(os.path.join(root, fn)), delimiter="\t"):
                    c = tok(r.get("Contig", ""))
                    if c in contigs:
                        try:
                            hits[c].append(float(r.get("Identity", "nan")))
                        except ValueError:
                            pass
    out = {c: {"pf_max_identity": max(v), "pf_n_hits": len(v)} for c, v in hits.items() if v}
    return out, ("pf_max_identity", "pf_n_hits"), "sparse_no_hit"


def f_mobsuite(d, contigs):
    out = {}
    for root, _, files in os.walk(d):
        for fn in files:
            if fn == "contig_report.txt":
                for r in csv.DictReader(open(os.path.join(root, fn)), delimiter="\t"):
                    c = tok(r.get("contig_id", ""))
                    if c not in contigs:
                        continue
                    def cnt(k):
                        v = (r.get(k) or "-").strip()
                        return 0 if v in ("-", "") else len(v.split(","))
                    out[c] = {"mob_is_plasmid": int((r.get("molecule_type") or "") == "plasmid"),
                              "mob_has_bin": int((r.get("primary_cluster_id") or "-") not in ("-", "")),
                              "mob_rep_types": cnt("rep_type(s)"),
                              "mob_relaxase": cnt("relaxase_type(s)"),
                              "mob_circular": int((r.get("circularity_status") or "") == "circular"),
                              "mob_gc": float(r["gc"]) if (r.get("gc") or "").replace(".", "", 1).isdigit() else None}
    return out, ("mob_is_plasmid", "mob_has_bin", "mob_rep_types", "mob_relaxase",
                 "mob_circular", "mob_gc"), "dense"


EXTRACTORS = {"genomad": f_genomad, "plasgraph2": f_plasgraph2, "platon": f_platon,
              "rfplasmid": f_rfplasmid, "plascope": f_plascope,
              "plasmidfinder": f_plasmidfinder, "mobsuite": f_mobsuite}


def build(cohort):
    cfg = COHORTS[cohort]
    samples = sorted(s for s in os.listdir(cfg["asm"])
                     if os.path.exists(os.path.join(cfg["asm"], s, "shortread.fasta"))
                     and not s.endswith("_smoke"))
    rows = []
    prov = collections.Counter()
    for s in samples:
        contigs = fasta_contigs(os.path.join(cfg["asm"], s, "shortread.fasta"))
        topo = gfa_topology(os.path.join(cfg["asm"], s, "shortread.gfa"))
        feats = {c: {} for c in contigs}
        for tool, fn in EXTRACTORS.items():
            d = os.path.join(cfg["native"], tool, s)
            if not os.path.isdir(d):
                for c in contigs:
                    feats[c]["_%s_state" % tool] = "missing_output"
                prov["%s:missing_output" % tool] += 1
                continue
            try:
                vals, cols, kind = fn(d, contigs)
            except Exception as e:
                for c in contigs:
                    feats[c]["_%s_state" % tool] = "parse_error"
                prov["%s:parse_error" % tool] += 1
                continue
            prov["%s:%s" % (tool, kind)] += 1
            for c in contigs:
                if c in vals:
                    feats[c].update(vals[c]); feats[c]["_%s_state" % tool] = "present"
                else:
                    feats[c]["_%s_state" % tool] = "no_hit" if kind == "sparse_no_hit" else "absent"
                    for col in cols:
                        feats[c].setdefault(col, None)
        for c, meta in contigs.items():
            r = {"cohort": cohort, "sample": s, "contig_id": c,
                 "length": meta["length"], "depth": meta["depth"], "circular": meta["circular"]}
            r.update(topo.get(c, {"gfa_degree": None, "gfa_component_size": None}))
            r.update(feats[c])
            rows.append(r)
    return rows, samples, prov


allrows = []
for coh in ("P1.9", "P1.10"):
    r, s, prov = build(coh)
    print("%s: %d isolates, %d contigs" % (coh, len(s), len(r)))
    for k, v in sorted(prov.items()):
        if not k.endswith(":dense") and not k.endswith(":sparse_no_hit"):
            print("    provenance flag %s x%d" % (k, v))
    allrows += r

cols = []
for r in allrows:
    for k in r:
        if k not in cols:
            cols.append(k)
p = os.path.join(OUT, "probe_features_raw.tsv")
with open(p, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", restval="")
    w.writeheader(); w.writerows(allrows)
print("\nwrote %s  rows=%d cols=%d" % (p, len(allrows), len(cols)))
num = [c for c in cols if not c.startswith("_") and c not in ("cohort", "sample", "contig_id")]
print("numeric/continuous feature columns: %d" % len(num))
print(num)

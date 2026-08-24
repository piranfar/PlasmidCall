#!/usr/bin/env python3
"""P1.11 EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT -- sections 1-5. Runs ON the execution host.

Reads only frozen / already-produced artefacts. Writes only under p112/POSTTRUTH/.
Nothing is retrained, recalibrated, re-thresholded or re-frozen. The confirmatory result is
re-derived first and asserted exactly; the script refuses to continue if it does not match.
"""
import collections, csv, glob, io, json, math, os, sys
import numpy as np

P = "/work/p112"; S = "/work/p111"
OUT = P + "/POSTTRUTH"; LABEL = "EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT"
N_BOOT, SEED = 4000, 20260821
TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC", "PlasmidFinder",
         "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
CONF = {"n": 7244, "TP": 942, "FP": 33, "TN": 6002, "FN": 267}
os.makedirs(OUT, exist_ok=True)


def rd(p):
    return csv.DictReader(io.open(p, encoding="utf-8", errors="replace"), delimiter="\t")


def fnum(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def mets(y, c):
    y = np.asarray(y); c = np.asarray(c)
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    tn = int(((c == 0) & (y == 0)).sum()); fn = int(((c == 0) & (y == 1)).sum())
    ppv = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    spec = tn / (tn + fp) if tn + fp else None
    f1 = 2 * ppv * rec / (ppv + rec) if (ppv and rec and ppv + rec > 0) else None
    npos = int((y == 1).sum()); nev = tp + fp + tn + fn
    return {"n_eligible": int(len(y)), "n_evaluable": nev, "n_abstain": int(len(y)) - nev,
            "coverage": round(nev / len(y), 4) if len(y) else None,
            "n_truth_positive": npos, "TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "selective_PPV": ppv, "selective_recall": rec, "specificity": spec, "selective_F1": f1,
            "deployment_yield": tp / npos if npos else None}


def boot(y, g, c):
    y = np.asarray(y); g = np.asarray(g); c = np.asarray(c); iso = sorted(set(g.tolist()))
    if len(iso) < 2:
        return {"note": "fewer than 2 isolates; CI not computed"}
    idx = {i: np.where(g == i)[0] for i in iso}
    rng = np.random.default_rng(SEED); Pp = []; Rr = []; Ff = []
    for _ in range(N_BOOT):
        r = np.concatenate([idx[i] for i in rng.choice(iso, size=len(iso), replace=True)])
        m = mets(y[r], c[r])
        if m["selective_PPV"] is not None: Pp.append(m["selective_PPV"])
        if m["selective_recall"] is not None: Rr.append(m["selective_recall"])
        if m["selective_F1"] is not None: Ff.append(m["selective_F1"])
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4),
                   round(float(np.percentile(v, 97.5)), 4)] if v else None
    return {"PPV_ci95": q(Pp), "recall_ci95": q(Rr), "F1_ci95": q(Ff),
            "n_boot": N_BOOT, "seed": SEED, "resampling_unit": "isolate"}


def stable(m):
    return m["n_evaluable"] >= 20 and 0 < m["n_truth_positive"] < m["n_evaluable"]


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s, dtype=float); ok = np.isfinite(s)
    y = y[ok]; s = s[ok]; npos = int(y.sum()); nneg = len(y) - npos
    if npos == 0 or nneg == 0:
        return None, None
    o = np.argsort(s, kind="mergesort"); ss = s[o]; yy = y[o]
    rk = np.empty(len(ss)); i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        rk[i:j + 1] = (i + j) / 2.0 + 1; i = j + 1
    auroc = (rk[yy == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg)
    o = np.argsort(-s, kind="mergesort"); yy = y[o]
    tp = np.cumsum(yy); fp = np.cumsum(1 - yy)
    prec = tp / (tp + fp); rec = tp / npos
    ap = float(np.sum(np.diff(np.concatenate([[0.0], rec])) * prec))
    return float(auroc), ap


# ------------------------------------------------------------------ load frozen artefacts
pred = list(rd(P + "/inference/frozen/P1.11_FROZEN_PREDICTIONS.tsv"))
predk = {(r["sample"], r["contig_id"]): r for r in pred}
truth = {}
for f in sorted(glob.glob(P + "/truth/*/truth_table.tsv")):
    for r in rd(f):
        truth[(r["sample"], r["contig_id"])] = r
mobprov = {}
for r in rd(P + "/inference/P1.11_call_table_reconciled.tsv"):
    if r["tool"] == "MOB-recon":
        mobprov[(r["sample"], r["contig_id"])] = r["provenance_state"]
acq = json.load(io.open(P + "/receipts/P1.11_truth_acquisition_receipt.json", encoding="utf-8"))
pi = acq["per_isolate"]


def gk(d, *names):
    for n in names:
        if n in d:
            return d[n]
    return ""


refsrc = {gk(x, "biosample", "sample"): gk(x, "reference_source", "source", "truth_source") for x in pi}
refacc = {gk(x, "biosample", "sample"): gk(x, "assembly_accession", "accession") for x in pi}
coh = {r["biosample"]: r for r in rd(S + "/manifests/P1.11_cohort_independent.tsv")}

keys = sorted(k for k, r in predk.items()
              if r["is_eligible_ge_1kb"] == "1"
              and truth.get(k, {}).get("final_truth_label") in ("plasmid", "chromosome"))
y = np.array([1 if truth[k]["final_truth_label"] == "plasmid" else 0 for k in keys])
g = np.array([k[0] for k in keys])
L = np.array([int(predk[k]["contig_length"]) for k in keys])
arg = np.array([predk[k]["ARG_bearing_bool"] == "true" for k in keys])
s12 = np.array([fnum(predk[k]["v12_score"]) if fnum(predk[k]["v12_score"]) is not None else np.nan
                for k in keys])
s11 = np.array([fnum(predk[k]["v11_score"]) if fnum(predk[k]["v11_score"]) is not None else np.nan
                for k in keys])
POS11 = {"plasmid_selected", "high_confidence_plasmid"}
c12 = np.array([1 if predk[k]["v12_call"] == "plasmid_selected"
                else (0 if predk[k]["v12_score_state"] == "available" else -1) for k in keys])
c11 = np.array([1 if predk[k]["v11_call"] in POS11
                else (0 if predk[k]["v11_score_state"] == "available" else -1) for k in keys])
c11h = np.array([1 if predk[k]["v11_call"] == "high_confidence_plasmid"
                 else (0 if predk[k]["v11_score_state"] == "available" else -1) for k in keys])
crt = np.array([1 if predk[k]["router_call"] in POS11
                else (0 if predk[k]["router_state"] == "routed" else -1) for k in keys])
tcall = {t: np.array([1 if predk[k][t] == "plasmid" else (0 if predk[k][t] == "chromosome" else -1)
                      for k in keys]) for t in TOOLS}

# ------------------------------------------------------------------ GATE
m0 = mets(y, c12)
got = {"n": len(keys), "TP": m0["TP"], "FP": m0["FP"], "TN": m0["TN"], "FN": m0["FN"]}
if got != CONF:
    sys.exit("REFUSING: confirmatory result not reproduced.\n  expected %s\n  got      %s" % (CONF, got))
print("  GATE PASS -- confirmatory reproduced exactly: %s" % got)

R = {"label": LABEL, "result_id": "P1.11-CORRECTED-TRUTH-ALL79",
     "status": ("EXPLORATORY post-truth analyses in support of a manuscript. They do not alter the "
                "frozen predictions, thresholds, confirmatory results or the principal gate, and no "
                "exploratory result may rescue or redefine a confirmatory claim."),
     "confirmatory_reproduced": got, "n_contigs": len(keys),
     "n_isolates": len(set(g.tolist())), "n_truth_positive": int(y.sum())}

# ================================================================== 1. population structure
species = collections.Counter(coh[s]["organism"] for s in sorted(set(g.tolist())) if s in coh)


def tsv(p):
    rows = [l.rstrip("\n").split("\t") for l in io.open(p, encoding="utf-8") if l.strip()]
    return rows[0], rows[1:]


ch, clon = tsv(S + "/screen/P1.11_internal_clonal_pairs.tsv")
xh, excl = tsv(S + "/screen/P1.11_exclusions_consumed.tsv")
kh, clus = tsv(S + "/screen/P1.11_internal_clusters.tsv")
cohort79 = set(coh)
pairs_in = [(r[0], r[1], fnum(r[2])) for r in clon
            if len(r) >= 3 and r[0] in cohort79 and r[1] in cohort79]
dev_near = collections.defaultdict(list)
for r in excl:
    if len(r) >= 4 and r[0] in cohort79:
        dev_near[r[0]].append({"linked_to": r[1], "cohort": r[2], "ani": fnum(r[3])})
consumed = set()
cf = S + "/screen/list_consumed.txt"
if os.path.exists(cf):
    for l in io.open(cf, encoding="utf-8"):
        b = os.path.basename(l.strip())
        if b:
            consumed.add(b.split(".")[0].split("_")[0])
exact = sorted(cohort79 & consumed)

R["population_structure"] = {
    "label": LABEL,
    "species": {"source": "sealed cohort `organism` field (NCBI assembly metadata)",
                "counts": dict(species), "n_species": len(species),
                "note": "the entire P1.11 cohort is one species; species stratification is degenerate"},
    "MLST": {"status": "NOT AVAILABLE",
             "reason": ("no MLST caller is installed on the execution host and no MLST image exists "
                        "in the frozen image set. Installing one would alter the frozen execution "
                        "environment after truth access. MLST is reported as not available; it is "
                        "not estimated or substituted."),
             "consequence": "lineage-stratified performance and lineage-based leakage cannot be computed"},
    "distance_matrix": {"provenance": "RECOVERED from the pre-truth cohort screen, not regenerated",
                        "within_cohort_file": "p111/screen/p111_vs_p111.tsv",
                        "vs_consumed_file": "p111/screen/p111_vs_consumed.tsv",
                        "method": "skani 0.2.2, --min-af 15",
                        "frozen_independence_threshold_ANI": 0.995,
                        "threshold_provenance": ("previously frozen in the P1.11 predeclaration; "
                                                 "reused unchanged, no new cutoff selected"),
                        "computed_before_truth_access": True},
    "near_clonal_within_P1.11": {
        "n_pairs_recorded_pre_declustering": len(clon),
        "n_pairs_with_both_members_in_the_final_79": len(pairs_in),
        "pairs": [{"a": a, "b": b, "ani_percent": v} for a, b, v in pairs_in]},
    "clusters_recorded": len(clus),
    "overlap_with_development_and_consumed_cohorts": {
        "exact_identifier_overlap": {
            "n": len(exact), "biosamples": exact,
            "method": "P1.11 BioSample identifiers intersected with the consumed-genome list"},
        "near_neighbours_at_ANI_ge_0.995": {
            "n_retained_isolates_with_at_least_one": len(dev_near),
            "detail": {k: v for k, v in sorted(dev_near.items())}}}}


def subset(mask, name, extra=None):
    mask = np.asarray(mask, dtype=bool)
    m = mets(y[mask], c12[mask])
    d = {"analysis": name, "n_contigs": int(mask.sum()), "n_isolates": len(set(g[mask].tolist()))}
    d.update({k: m[k] for k in ("n_truth_positive", "TP", "FP", "TN", "FN", "selective_PPV",
                                "selective_recall", "selective_F1", "coverage")})
    if stable(m):
        d["bootstrap"] = boot(y[mask], g[mask], c12[mask])
    else:
        d.update({"estimate_suppressed": True,
                  "reason": "fewer than 20 evaluable contigs, or a truth class is absent"})
    if extra:
        d.update(extra)
    return d


allm = np.ones(len(keys), bool)
drop_clonal = sorted({b for _a, b, _v in pairs_in})
withdev = set(dev_near)
sens = [subset(allm, "reference: all 79 sealed isolates"),
        subset([k[0] not in set(drop_clonal) for k in keys],
               "one representative per near-clonal pair retained",
               {"isolates_removed": drop_clonal}),
        subset([k[0] not in withdev for k in keys],
               "isolates with a near-genomic neighbour in a consumed cohort removed (ANI>=0.995)",
               {"n_isolates_removed": len(withdev), "isolates_removed": sorted(withdev)})]
big = species.most_common(1)[0] if species else ("", 0)
sens.append({"analysis": "largest species excluded", "not_estimable": True,
             "reason": ("the cohort is a single species (%s, %d/%d isolates); excluding it excludes "
                        "the whole cohort" % (big[0], big[1], len(set(g.tolist()))))})
sens.append({"analysis": "largest lineage excluded", "not_estimable": True,
             "reason": "MLST is not available on this host, so lineage cannot be defined"})
R["population_sensitivity"] = {"label": LABEL,
                               "model": "PlasmidCall v1.2-General at the frozen 0.9285",
                               "operating_point_unchanged": True, "analyses": sens}
R["species_stratified"] = {
    "label": LABEL,
    "rule_as_declared": "species with >=10 isolates AND both truth classes; remainder pooled as `other`",
    "outcome": "one qualifying stratum, identical to the whole cohort",
    "Escherichia coli": subset(allm, "Escherichia coli (= entire cohort)"),
    "other": {"n_isolates": 0, "note": "no isolate falls outside the qualifying species"}}

# ================================================================== 2. ARG-plasmid yield
amr = collections.defaultdict(list)
for f in glob.glob(P + "/annotation/native/*/*.amrfinder.tsv"):
    s = os.path.basename(os.path.dirname(f))
    for r in rd(f):
        amr[(s, (r.get("Contig id") or "").strip())].append(r)


def anyf(r, *names):
    for n in names:
        if r.get(n):
            return r[n]
    return ""


def joinset(h, *names):
    return ";".join(sorted({anyf(x, *names) for x in h} - {""}))


rows = []
kidx = {k: i for i, k in enumerate(keys)}
for i, k in enumerate(keys):
    if not arg[i]:
        continue
    h = amr.get(k, []); pr = predk[k]; t = truth[k]
    d = {"isolate": k[0], "species": coh.get(k[0], {}).get("organism", ""), "MLST": "not_available",
         "contig_id": k[1], "contig_length": int(L[i]), "circular": pr["circular"],
         "truth_label": t["final_truth_label"], "truth_decision_reason": t.get("decision_reason", ""),
         "best_plasmid_hit": t.get("best_plasmid_hit", ""),
         "best_chromosome_hit": t.get("best_chromosome_hit", ""),
         "reference_source": refsrc.get(k[0], ""), "reference_accession": refacc.get(k[0], ""),
         "v11_score": pr["v11_score"], "v11_call": pr["v11_call"],
         "v12_score": pr["v12_score"], "v12_call": pr["v12_call"],
         "router_model": pr["router_model"], "router_call": pr["router_call"],
         "n_tools_with_a_usable_call": pr["n_valid"], "n_tools_abstained": pr["n_abstain"],
         "tool_evidence_fraction": round(int(pr["n_valid"]) / 12.0, 4),
         "n_determinants": len(h),
         "gene_symbols": joinset(h, "Element symbol", "Gene symbol"),
         "drug_classes": joinset(h, "Class"), "subclasses": joinset(h, "Subclass"),
         "methods": joinset(h, "Method"),
         "closest_reference_accessions": joinset(h, "Closest reference accession"),
         "min_pct_identity": min([fnum(x.get("% Identity to reference")) or 0 for x in h] or [0]),
         "min_pct_coverage": min([fnum(x.get("% Coverage of reference")) or 0 for x in h] or [0])}
    for tl in TOOLS:
        d["call_" + tl] = pr[tl]
    d["mobrecon_provenance"] = mobprov.get(k, "")
    rows.append(d)
with io.open(OUT + "/P1.11_ARG_contig_table.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter="\t", lineterminator="\n",
                       restval="")
    w.writeheader(); w.writerows(rows)

am = arg; aY = y[am]
argrep = {"label": LABEL,
          "definition": "contigs flagged ARG_bearing_bool in the frozen prediction table",
          "n_ARG_contigs": int(am.sum()),
          "n_isolates_with_an_ARG_contig": len({r["isolate"] for r in rows}),
          "n_truth_plasmid": int(aY.sum()), "n_truth_chromosome": int((aY == 0).sum()),
          "PlasmidCall_v1.2_General_0.9285": mets(aY, c12[am]),
          "PlasmidCall_router": mets(aY, crt[am]),
          "PlasmidCall_v1.1_0.9524": mets(aY, c11[am]),
          "PlasmidCall_v1.1_0.9605": mets(aY, c11h[am])}
if stable(mets(aY, c12[am])):
    argrep["PlasmidCall_v1.2_General_0.9285"]["bootstrap"] = boot(aY, g[am], c12[am])
comp = {}
p12 = (c12[am] == 1) & (aY == 1)
for t in TOOLS:
    tc = tcall[t][am]; pt = (tc == 1) & (aY == 1); ab = (tc < 0) & (aY == 1)
    comp[t] = {"metrics": mets(aY, tc),
               "true_plasmid_ARG_contigs_recovered": int(pt.sum()),
               "share_of_all_true_plasmid_ARG_contigs":
                   round(float(pt.sum()) / int(aY.sum()), 4) if aY.sum() else None,
               "recovered_by_PlasmidCall_but_not_by_this_tool": int((p12 & ~pt).sum()),
               "of_which_this_tool_abstained": int((p12 & ab).sum()),
               "recovered_by_this_tool_but_not_by_PlasmidCall": int((pt & ~p12).sum()),
               "chromosomal_ARG_contigs_this_tool_called_plasmid": int(((tc == 1) & (aY == 0)).sum()),
               "chromosomal_ARG_contigs_PlasmidCall_called_plasmid":
                   int(((c12[am] == 1) & (aY == 0)).sum())}
argrep["per_comparator_on_ARG_contigs"] = comp
bycls = collections.defaultdict(lambda: {"n_contigs": 0, "n_plasmid": 0, "n_plasmid_recovered_v12": 0})
for r in rows:
    i = kidx[(r["isolate"], r["contig_id"])]
    for cl in [x for x in r["drug_classes"].split(";") if x]:
        b = bycls[cl]; b["n_contigs"] += 1
        b["n_plasmid"] += int(y[i] == 1)
        b["n_plasmid_recovered_v12"] += int(y[i] == 1 and c12[i] == 1)
for b in bycls.values():
    b["plasmid_fraction"] = round(b["n_plasmid"] / b["n_contigs"], 4) if b["n_contigs"] else None
    b["recovery_of_plasmid_borne"] = (round(b["n_plasmid_recovered_v12"] / b["n_plasmid"], 4)
                                      if b["n_plasmid"] else None)
argrep["by_drug_class"] = dict(sorted(bycls.items(), key=lambda x: -x[1]["n_contigs"]))
FOCUS = {"carbapenemase": ["KPC", "NDM", "OXA-48", "OXA-23", "OXA-181", "VIM", "IMP"],
         "ESBL_and_related_beta_lactamase": ["CTX-M", "SHV", "TEM", "PER", "VEB", "CMY", "DHA"],
         "colistin_mcr": ["MCR-"],
         "aminoglycoside_incl_16S_methylase": ["AAC(", "APH(", "ANT(", "AADA", "ARMA", "RMTB", "RMTC"],
         "fluoroquinolone_PMQR": ["QNR", "QEPA", "OQXA", "OQXB", "AAC(6')-IB-CR"]}
foc = {}
for fam, pats in FOCUS.items():
    sel = [r for r in rows if any(p in r["gene_symbols"].upper() for p in pats)]
    npl = [r for r in sel if r["truth_label"] == "plasmid"]
    foc[fam] = {"n_ARG_contigs": len(sel), "n_truth_plasmid": len(npl),
                "n_truth_plasmid_recovered_by_v1.2":
                    sum(1 for r in npl if r["v12_call"] == "plasmid_selected"),
                "n_truth_plasmid_recovered_by_router":
                    sum(1 for r in npl if r["router_call"] != "not_selected"),
                "n_truth_chromosome": len(sel) - len(npl),
                "genes_observed": sorted({x for r in sel for x in r["gene_symbols"].split(";") if x}),
                "isolates": sorted({r["isolate"] for r in sel}),
                "case_rows": sel}
argrep["clinically_focused_determinants"] = foc
argrep["framing"] = ("This is a localisation and surveillance-yield analysis. No claim of biological "
                     "novelty is made; establishing novelty would require a separate investigation "
                     "against a plasmid reference database, which is not performed here.")
R["ARG_plasmid_surveillance_yield"] = argrep

# ================================================================== 3. disagreement / value added
npl_v = np.array([sum(1 for t in TOOLS if tcall[t][i] == 1) for i in range(len(keys))])
nch_v = np.array([sum(1 for t in TOOLS if tcall[t][i] == 0) for i in range(len(keys))])
nab_v = np.array([sum(1 for t in TOOLS if tcall[t][i] < 0) for i in range(len(keys))])
ent = np.zeros(len(keys))
for i in range(len(keys)):
    tot = npl_v[i] + nch_v[i]
    if tot:
        p = npl_v[i] / tot
        ent[i] = 0.0 if p in (0.0, 1.0) else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
dis = {"label": LABEL,
       "vote_definition": ("number of the 12 tools emitting model1_code == plasmid; abstentions are "
                           "excluded from the vote total"),
       "disagreement_definition": ("binary Shannon entropy of the plasmid/chromosome vote split, "
                                   "abstentions excluded; 0 = unanimous, 1 = maximal disagreement. "
                                   "Defined from prediction-side artefacts only, never from truth."),
       "vote_strata": {}, "disagreement_quartiles": {}}
for nm, lo, hi in [("0-2", 0, 2), ("3-5", 3, 5), ("6-8", 6, 8), ("9-12", 9, 12)]:
    m = (npl_v >= lo) & (npl_v <= hi)
    e = {"n_contigs": int(m.sum()), "n_isolates": len(set(g[m].tolist())),
         "n_truth_positive": int(y[m].sum()),
         "truth_positive_rate": round(float(y[m].mean()), 4) if m.sum() else None,
         "PlasmidCall_v1.2-General": mets(y[m], c12[m]), "PlasmidCall_router": mets(y[m], crt[m]),
         "PlasmidCall_v1.1_0.9524": mets(y[m], c11[m])}
    for t in TOOLS:
        e["tool_" + t] = mets(y[m], tcall[t][m])
    if not stable(mets(y[m], c12[m])):
        e["estimate_suppressed"] = True
        e["reason"] = "fewer than 20 evaluable contigs, or a truth class is absent"
    dis["vote_strata"][nm] = e
qv = np.percentile(ent, [25, 50, 75])
for qi, (lo, hi) in enumerate([(-1.0, qv[0]), (qv[0], qv[1]), (qv[1], qv[2]), (qv[2], 2.0)]):
    m = (ent <= hi) if qi == 0 else ((ent > lo) & (ent <= hi))
    best = max(((t, mets(y[m], tcall[t][m])["selective_F1"]) for t in TOOLS),
               key=lambda x: (x[1] is not None, x[1] or 0))
    dis["disagreement_quartiles"]["Q%d" % (qi + 1)] = {
        "entropy_interval": [round(float(max(lo, 0.0)), 4), round(float(hi), 4)],
        "n_contigs": int(m.sum()), "n_truth_positive": int(y[m].sum()),
        "PlasmidCall_v1.2-General": mets(y[m], c12[m]),
        "PlasmidCall_router": mets(y[m], crt[m]),
        "best_single_tool_by_selective_F1_in_this_stratum": {"tool": best[0], "selective_F1": best[1]}}
maj = np.where(npl_v + nch_v > 0, (npl_v > nch_v).astype(int), -1)
hi = ent >= 0.8
va = {"majority_reference_rule": ("simple majority of plasmid vs chromosome votes with abstentions "
                                  "excluded; ties resolved to chromosome. Descriptive reference only "
                                  "-- NOT a voting rule fitted, tuned or selected on P1.11."),
      "majority_vote_overall": mets(y, maj),
      "high_disagreement_contigs_entropy_ge_0.8": int(hi.sum()),
      "high_disagreement_resolved_correctly_by_v1.2": int(((c12 == y) & hi & (c12 >= 0)).sum()),
      "high_disagreement_resolved_correctly_by_majority": int(((maj == y) & hi & (maj >= 0)).sum()),
      "majority_errors_corrected_by_v1.2":
          int(((maj != y) & (maj >= 0) & (c12 == y) & (c12 >= 0)).sum()),
      "errors_introduced_by_v1.2_where_majority_was_right":
          int(((maj == y) & (maj >= 0) & (c12 != y) & (c12 >= 0)).sum()),
      "unanimous_contigs_entropy_0": int((ent == 0).sum()),
      "v1.2_disagrees_with_a_unanimous_panel":
          int(((ent == 0) & (npl_v + nch_v > 0) & (c12 >= 0) & (c12 != maj)).sum())}
for nm, cc in [("PlaScope", tcall["PlaScope"]), ("PlasmidFinder", tcall["PlasmidFinder"]),
               ("Plasmer", tcall["Plasmer"]), ("geNomad", tcall["geNomad"]),
               ("MOB-recon", tcall["MOB-recon"]), ("majority_vote", maj),
               ("PlasmidCall_v1.1_0.9524", c11)]:
    b = (c12 >= 0) & (cc >= 0)
    va["incremental_versus_" + nm] = {
        "common_support_n": int(b.sum()),
        "v1.2_metrics_on_common_support": mets(y[b], c12[b]),
        "comparator_metrics_on_common_support": mets(y[b], cc[b]),
        "incremental_TP": int(((c12 == 1) & (y == 1) & (cc != 1) & b).sum()),
        "incremental_FP": int(((c12 == 1) & (y == 0) & (cc != 1) & b).sum()),
        "TP_lost_relative_to_comparator": int(((cc == 1) & (y == 1) & (c12 != 1) & b).sum()),
        "FP_avoided_relative_to_comparator": int(((cc == 1) & (y == 0) & (c12 != 1) & b).sum())}
dis["value_added"] = va
R["tool_disagreement_and_model_value_added"] = dis

# ================================================================== 4. error taxonomy
LB = [("1-<2kb", 1000, 2000), ("2-<5kb", 2000, 5000), ("5-<10kb", 5000, 10000),
      (">=10kb", 10000, None)]


def lbin(v):
    for nm, lo, hiv in LB:
        if v >= lo and (hiv is None or v < hiv):
            return nm
    return "<1kb"


ncontig = collections.Counter(g.tolist())
errs = []
for i, k in enumerate(keys):
    if c12[i] < 0 or c12[i] == y[i]:
        continue
    t = truth[k]; pr = predk[k]; h = amr.get(k, [])
    errs.append({
        "error_type": "FP" if c12[i] == 1 else "FN", "isolate": k[0],
        "species": coh.get(k[0], {}).get("organism", ""), "MLST": "not_available",
        "contig_id": k[1], "contig_length": int(L[i]), "length_bin": lbin(int(L[i])),
        "circular": pr["circular"], "gfa_degree": pr["gfa_degree"],
        "truth_label": t["final_truth_label"], "truth_decision_reason": t.get("decision_reason", ""),
        "truth_confidence_state": t.get("confidence_state", ""), "truth_flags": t.get("flags", ""),
        "chromosome_aligned_fraction": t.get("chromosome_aligned_fraction", ""),
        "plasmid_aligned_fraction": t.get("plasmid_aligned_fraction", ""),
        "unresolved_or_shared_fraction": t.get("unresolved_or_shared_fraction", ""),
        "competing_hit_count": t.get("competing_hit_count", ""),
        "best_chromosome_hit": t.get("best_chromosome_hit", ""),
        "best_plasmid_hit": t.get("best_plasmid_hit", ""),
        "assembly_coverage": t.get("coverage", ""),
        "ARG_bearing": "true" if arg[i] else "false",
        "ARG_genes": joinset(h, "Element symbol", "Gene symbol"),
        "v12_score": pr["v12_score"], "v11_score": pr["v11_score"], "v11_call": pr["v11_call"],
        "router_model": pr["router_model"], "router_call": pr["router_call"],
        "router_agreed_with_v12": "true" if (crt[i] == c12[i]) else "false",
        "n_tools_plasmid": int(npl_v[i]), "n_tools_chromosome": int(nch_v[i]),
        "n_tools_abstain": int(nab_v[i]), "vote_entropy": round(float(ent[i]), 4),
        "tool_evidence_fraction": round(int(pr["n_valid"]) / 12.0, 4),
        "tools_that_also_erred": ";".join(t_ for t_ in TOOLS
                                          if tcall[t_][i] >= 0 and tcall[t_][i] != y[i]),
        "tools_that_were_correct": ";".join(t_ for t_ in TOOLS
                                            if tcall[t_][i] >= 0 and tcall[t_][i] == y[i]),
        "mobrecon_provenance": mobprov.get(k, ""), "reference_source": refsrc.get(k[0], ""),
        "n_eligible_contigs_in_isolate": int(ncontig[k[0]])})
with io.open(OUT + "/P1.11_error_taxonomy.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(errs[0].keys()), delimiter="\t", lineterminator="\n",
                       restval="")
    w.writeheader(); w.writerows(errs)


def cnt(fn, sub=None):
    return dict(collections.Counter(fn(e) for e in errs if sub is None or e["error_type"] == sub))


def band(e):
    v = e["vote_entropy"]
    return ("unanimous(0)" if v == 0 else "low(<0.5)" if v < 0.5
            else "moderate(0.5-0.8)" if v < 0.8 else "high(>=0.8)")


def frag(e):
    n = e["n_eligible_contigs_in_isolate"]
    return "<50" if n < 50 else ("50-149" if n < 150 else ("150-299" if n < 300 else ">=300"))


def marg(e):
    v = fnum(e["unresolved_or_shared_fraction"])
    return "unresolved_or_shared>0.10" if (v is not None and v > 0.10) else "clear"


etax = {"label": LABEL, "n_errors": len(errs),
        "n_FP": sum(1 for e in errs if e["error_type"] == "FP"),
        "n_FN": sum(1 for e in errs if e["error_type"] == "FN"),
        "table": "POSTTRUTH/P1.11_error_taxonomy.tsv (one row per corrected v1.2-General FP and FN)",
        "by_length_bin": {"all": cnt(lambda e: e["length_bin"]),
                          "FP": cnt(lambda e: e["length_bin"], "FP"),
                          "FN": cnt(lambda e: e["length_bin"], "FN")},
        "by_species": cnt(lambda e: e["species"]),
        "by_ARG_state": {"all": cnt(lambda e: e["ARG_bearing"]),
                         "FP": cnt(lambda e: e["ARG_bearing"], "FP"),
                         "FN": cnt(lambda e: e["ARG_bearing"], "FN")},
        "by_reference_source": {"all": cnt(lambda e: e["reference_source"]),
                                "FP": cnt(lambda e: e["reference_source"], "FP"),
                                "FN": cnt(lambda e: e["reference_source"], "FN")},
        "by_mobrecon_provenance": {"all": cnt(lambda e: e["mobrecon_provenance"]),
                                   "FP": cnt(lambda e: e["mobrecon_provenance"], "FP"),
                                   "FN": cnt(lambda e: e["mobrecon_provenance"], "FN")},
        "by_vote_entropy_band": {"all": cnt(band), "FP": cnt(band, "FP"), "FN": cnt(band, "FN")},
        "by_truth_margin_proximity": {"all": cnt(marg), "FP": cnt(marg, "FP"), "FN": cnt(marg, "FN")},
        "by_truth_decision_reason": cnt(lambda e: e["truth_decision_reason"]),
        "by_assembly_fragmentation": {"all": cnt(frag), "FP": cnt(frag, "FP"), "FN": cnt(frag, "FN")},
        "by_circularity": cnt(lambda e: "circular" if e["circular"] == "1" else "linear"),
        "by_isolate": dict(sorted(collections.Counter(e["isolate"] for e in errs).items(),
                                  key=lambda x: -x[1])),
        "n_isolates_contributing_an_error": len({e["isolate"] for e in errs}),
        "errors_where_every_available_tool_also_erred":
            sum(1 for e in errs if e["tools_that_were_correct"] == ""),
        "errors_where_the_router_disagreed_with_v1.2":
            sum(1 for e in errs if e["router_agreed_with_v12"] == "false"),
        "interpretation": ("These are observed distributions. No causal explanation is asserted. "
                           "Candidate hypotheses are recorded separately for the Discussion and are "
                           "not tested here.")}
etax["cohort_baseline_for_comparison"] = {
    "length_bin": dict(collections.Counter(lbin(int(v)) for v in L)),
    "ARG": dict(collections.Counter("true" if a else "false" for a in arg)),
    "entropy_band": dict(collections.Counter(
        ("unanimous(0)" if v == 0 else "low(<0.5)" if v < 0.5
         else "moderate(0.5-0.8)" if v < 0.8 else "high(>=0.8)") for v in ent)),
    "reference_source": dict(collections.Counter(refsrc.get(k[0], "") for k in keys))}
etax["error_rate_within_each_stratum"] = {}
for nm, fn in (("length_bin", lambda i: lbin(int(L[i]))),
               ("ARG", lambda i: "true" if arg[i] else "false"),
               ("entropy_band", lambda i: ("unanimous(0)" if ent[i] == 0 else
                                           "low(<0.5)" if ent[i] < 0.5 else
                                           "moderate(0.5-0.8)" if ent[i] < 0.8 else "high(>=0.8)")),
               ("reference_source", lambda i: refsrc.get(keys[i][0], ""))):
    d = collections.defaultdict(lambda: [0, 0])
    for i in range(len(keys)):
        if c12[i] < 0:
            continue
        s = fn(i); d[s][0] += 1; d[s][1] += int(c12[i] != y[i])
    etax["error_rate_within_each_stratum"][nm] = {
        k2: {"n_evaluable": v[0], "n_errors": v[1], "error_rate": round(v[1] / v[0], 4)}
        for k2, v in sorted(d.items())}
R["error_taxonomy"] = etax

# ================================================================== 5. runtime and resources
IMG = {"hyasp": "HyAsP", "mobsuite": "MOB-recon", "plasme": "PLASMe", "plascope": "PlaScope",
       "plasmer": "Plasmer", "plasmidec": "PlasmidEC", "plasmidfinder": "PlasmidFinder",
       "platon": "Platon", "rfplasmid": "RFPlasmid", "genomad": "geNomad", "gplas2": "gplas2",
       "plasgraph2": "plASgraph2", "amrfinder": "AMRFinderPlus"}
rt = collections.defaultdict(list); st = collections.defaultdict(collections.Counter)
imgs = collections.defaultdict(set); nrec = collections.Counter()
for f in glob.glob(P + "/inference/receipts/*.json"):
    try:
        d = json.load(io.open(f, encoding="utf-8"))
    except Exception:
        continue
    t = d.get("tool")
    if not t:
        continue
    nrec[t] += 1
    st[t][d.get("status", "?")] += 1
    if d.get("image"):
        imgs[t].add(d["image"])
    w = fnum(d.get("wall_seconds"))
    if w is not None:
        rt[t].append(w)
sz = {}
nd = P + "/inference/native"
if os.path.isdir(nd):
    for t in os.listdir(nd):
        tot = 0
        for dp, _dn, fn in os.walk(os.path.join(nd, t)):
            for x in fn:
                try:
                    tot += os.path.getsize(os.path.join(dp, x))
                except OSError:
                    pass
        sz[t] = tot


def qq(v, a):
    return round(float(np.percentile(v, a)), 1) if v else None


rr = {"label": LABEL,
      "cpu_and_peak_memory": {
          "status": "not recorded",
          "reason": ("the frozen execution receipts record tool, sample, exit_code, status, "
                     "start_utc, end_utc, wall_seconds, image, image_id, docker_command and mounts. "
                     "No CPU-time or peak-RSS measurement was taken during execution. It is reported "
                     "as not recorded and is not estimated."),
          "declared_allocation_in_the_frozen_docker_command": {"cpus": 8, "memory_limit": "24g"}},
      "by_component": {}}
for t in sorted(nrec):
    v = rt.get(t, [])
    rr["by_component"][IMG.get(t, t)] = {
        "receipt_key": t, "n_executions": nrec[t], "n_isolates": 79,
        "status_counts": dict(st[t]), "images": sorted(imgs[t]),
        "wall_seconds_median": qq(v, 50), "wall_seconds_IQR": [qq(v, 25), qq(v, 75)],
        "wall_seconds_min": round(min(v), 1) if v else None,
        "wall_seconds_max": round(max(v), 1) if v else None,
        "wall_seconds_total": round(sum(v), 1) if v else None,
        "wall_hours_total": round(sum(v) / 3600, 3) if v else None,
        "cpu_hours_at_the_declared_8_cpu_allocation": round(sum(v) * 8 / 3600, 2) if v else None,
        "cpu_hours_caveat": "an allocation-based upper bound, not a measurement of CPU actually used",
        "native_output_bytes": sz.get(t), "peak_RAM": "not recorded", "cpu_time": "not recorded"}
tot_w = sum(sum(v) for v in rt.values())
rr["totals"] = {"n_executions": int(sum(nrec.values())), "wall_seconds": round(tot_w, 1),
                "wall_hours": round(tot_w / 3600, 2),
                "cpu_hours_at_the_declared_8_cpu_allocation": round(tot_w * 8 / 3600, 2),
                "note": ("sum of per-execution wall time; the panel ran with concurrency, so elapsed "
                         "time was lower")}
pv = {}
for t in TOOLS:
    key = [k2 for k2, v2 in IMG.items() if v2 == t][0]
    m = mets(y, tcall[t]); v = rt.get(key, [])
    nbad = int(sum(c for s2, c in st[key].items() if s2 != "OK"))
    pv[t] = {"selective_F1": m["selective_F1"], "selective_PPV": m["selective_PPV"],
             "selective_recall": m["selective_recall"], "coverage": m["coverage"],
             "deployment_yield": m["deployment_yield"],
             "wall_seconds_median": qq(v, 50), "wall_seconds_total": round(sum(v), 1) if v else None,
             "cpu_hours_at_8_cpu": round(sum(v) * 8 / 3600, 2) if v else None,
             "n_executions_not_OK": nbad, "operational_failure_rate": round(nbad / 79.0, 4)}
mm = mets(y, c12)
pv["PlasmidCall v1.2-General"] = {
    "selective_F1": mm["selective_F1"], "selective_PPV": mm["selective_PPV"],
    "selective_recall": mm["selective_recall"], "coverage": mm["coverage"],
    "deployment_yield": mm["deployment_yield"], "wall_seconds_median": None,
    "wall_seconds_total": None,
    "cost_note": ("PlasmidCall consumes the 12-tool panel as input; its own scoring cost is "
                  "negligible beside the panel, so its marginal runtime is not separately "
                  "meaningful. The relevant cost statement is the full-panel total above."),
    "n_executions_not_OK": None, "operational_failure_rate": None}
rr["performance_versus_cost"] = pv
R["runtime_and_resources"] = rr

# ================================================================== discrimination + calibration
def disc(sc):
    ok = np.isfinite(sc)
    a, ap = auc(y[ok], sc[ok])
    rng = np.random.default_rng(SEED); go = g[ok]; yo = y[ok]; so = sc[ok]
    iso = sorted(set(go.tolist())); idx = {i: np.where(go == i)[0] for i in iso}
    A = []; B = []
    for _ in range(N_BOOT):
        r = np.concatenate([idx[i] for i in rng.choice(iso, size=len(iso), replace=True)])
        x1, x2 = auc(yo[r], so[r])
        if x1 is not None:
            A.append(x1); B.append(x2)
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4),
                   round(float(np.percentile(v, 97.5)), 4)] if v else None
    o = np.argsort(so, kind="mergesort"); bins = [b for b in np.array_split(o, 10) if len(b)]
    rel = [{"bin": bi + 1, "n": int(len(b)), "mean_score": round(float(so[b].mean()), 6),
            "observed_positive_fraction": round(float(yo[b].mean()), 6)}
           for bi, b in enumerate(bins)]
    ece = float(sum(len(b) / len(so) * abs(so[b].mean() - yo[b].mean()) for b in bins))
    eps = 1e-12; cl = np.clip(so, eps, 1 - eps); lo_ = np.log(cl / (1 - cl))
    w = np.zeros(2); X = np.column_stack([np.ones(len(lo_)), lo_])
    for _ in range(200):
        p = 1 / (1 + np.exp(-X @ w)); Wd = p * (1 - p) + 1e-12
        try:
            w = w + np.linalg.solve((X * Wd[:, None]).T @ X + 1e-9 * np.eye(2), X.T @ (yo - p))
        except np.linalg.LinAlgError:
            break
    return {"n": int(ok.sum()), "AUROC": round(a, 4), "AUROC_ci95": q(A),
            "AUPRC": round(ap, 4), "AUPRC_ci95": q(B),
            "Brier": round(float(np.mean((so - yo) ** 2)), 6),
            "calibration_intercept": round(float(w[0]), 4),
            "calibration_slope": round(float(w[1]), 4),
            "ECE_10_equal_frequency_bins": round(ece, 6), "reliability_table": rel,
            "recalibration_applied": "none -- Platt scaling and isotonic regression are prohibited",
            "naming": "EMPIRICAL SCORE CALIBRATION of the frozen scores",
            "threshold_use": "threshold-independent; not used to select any P1.11 threshold"}


R["discrimination_and_calibration"] = {
    "label": "PRESPECIFIED_SECONDARY (pre-truth addendum sections 4-5)",
    "v1.2-General": disc(s12), "v1.1 M2_score": disc(s11)}

with io.open(OUT + "/P1.11_POSTTRUTH_SECTIONS_1_5.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(R, f, indent=1, default=str); f.write("\n")
print("  contigs %d | isolates %d | ARG %d | errors %d (FP %d / FN %d)"
      % (len(keys), len(set(g.tolist())), int(arg.sum()), len(errs), etax["n_FP"], etax["n_FN"]))
print("  species %s | MLST NOT AVAILABLE" % dict(species))
print("  clonal pairs both-in-79 %d | isolates w/ consumed near-neighbour %d | exact overlap %d"
      % (len(pairs_in), len(dev_near), len(exact)))
print("  AUROC v1.2 %s  v1.1 %s"
      % (R["discrimination_and_calibration"]["v1.2-General"]["AUROC"],
         R["discrimination_and_calibration"]["v1.1 M2_score"]["AUROC"]))
print("  wrote %s" % OUT)

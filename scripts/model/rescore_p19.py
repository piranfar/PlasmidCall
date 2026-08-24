#!/usr/bin/env python3
"""P1.10-D: re-score the EXISTING frozen P1.9 predictions at the development-derived deployment
operating points. Reads only frozen artifacts (P1.9C4 contig table + ARG determinants + truth).
No inference, no refit, no OCI. Writes results to the P1.10 output directory."""
import json, hashlib, math, os
import numpy as np, pandas as pd

P4 = r"E:/AMR_Evidence_Data/P1.9_cleanroom/p19c4"
OUT = r"E:/AMR_Evidence_Data/P1.9_cleanroom/p110"
os.makedirs(OUT, exist_ok=True)
STD, VHC = 0.9605, 0.9776
SENS = [0.9732, 0.9718, 0.9524, 0.9378]           # remaining development fold thresholds
DEV_LINKED = {"robertson-benchmark_ecol-SAMN04014847", "robertson-benchmark_ecol-SAMN04014852",
              "robertson-benchmark_ecol-SAMN04014855", "robertson-benchmark_ecol-SAMN04014856"}

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""): h.update(b)
    return h.hexdigest()

d = pd.read_csv(f"{P4}/evaluation/P1.9C4_model1_contig_table.tsv", sep="\t")
det = pd.read_csv(f"{P4}/extracted/annotation/P1.9C4_arg_determinants.tsv", sep="\t")
d["is_res"] = d["final_truth_label"].isin(["plasmid", "chromosome"]) & (d["contig_length"] >= 1000)
d["arg"] = d["ARG_bearing"].astype(str).str.upper().isin(["TRUE", "1"])
d["y"] = (d["final_truth_label"] == "plasmid").astype(int)
d["dev_linked"] = d["sample"].isin(DEV_LINKED)

# dev-parity core-ARG eligibility (audit correction 5): qualifying AND scope=core AND class != EFFLUX
q = det[(det["qualifying"].astype(str).str.upper() == "TRUE") &
        (det["scope"].astype(str).str.lower() == "core") &
        (det["class"].astype(str).str.upper() != "EFFLUX")]
core_keys = set(zip(q["sample"], q["contig_id"].astype(str)))
d["arg_core"] = [ (s, str(c)) in core_keys for s, c in zip(d["sample"], d["contig_id"]) ]

def metrics(sub, call):
    y = sub["y"].values; c = np.asarray(call)
    TP = int(((c == 1) & (y == 1)).sum()); FP = int(((c == 1) & (y == 0)).sum())
    TN = int(((c == 0) & (y == 0)).sum()); FN = int(((c == 0) & (y == 1)).sum())
    UN = int((c < 0).sum()); n = len(y); npos = int(y.sum()); nneg = n - npos
    f = lambda a, b: (a / b) if b else None
    ppv = f(TP, TP + FP); rec = f(TP, npos); spec = f(TN, TN + FP)
    f1 = (2 * ppv * rec / (ppv + rec)) if (ppv and rec) else (0.0 if ppv is not None and rec is not None else None)
    ba = ((rec or 0) + (spec or 0)) / 2 if (rec is not None and spec is not None) else None
    den = math.sqrt(float(TP + FP) * (TP + FN) * (TN + FP) * (TN + FN))
    mcc = ((TP * TN - FP * FN) / den) if den else None
    return {"n": n, "n_plasmid": npos, "n_chromosome": nneg, "TP": TP, "FP": FP, "TN": TN, "FN": FN,
            "abstained": UN, "PPV": ppv, "recall": rec, "specificity": spec, "F1": f1,
            "balanced_accuracy": ba, "MCC": mcc, "coverage": f(TP + FP + TN + FN, n),
            "abstention_rate": f(UN, n)}

def m2_call(sub, thr): return (sub["M2_score"].values >= thr).astype(int)

POPS = {
 "primary_ARG_resolved":        d[d.is_res & d.arg],
 "primary_coreARG_devparity":   d[d.is_res & d.arg_core],
 "secondary_all_resolved":      d[d.is_res],
}
STRATA = {"all_8_samples": lambda s: s,
          "dev_linked_4_samples": lambda s: s[s.dev_linked],
          "unlinked_4_samples": lambda s: s[~s.dev_linked]}

res = {"artifact": "P1.10D_P1.9_RESCORE", "utc": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
       "inputs": {"contig_table": {"path": f"{P4}/evaluation/P1.9C4_model1_contig_table.tsv",
                                   "sha256": sha(f"{P4}/evaluation/P1.9C4_model1_contig_table.tsv")},
                  "arg_determinants": {"path": f"{P4}/extracted/annotation/P1.9C4_arg_determinants.tsv",
                                       "sha256": sha(f"{P4}/extracted/annotation/P1.9C4_arg_determinants.tsv")}},
       "operating_points": {"standard": STD, "very_high_confidence": VHC, "sensitivity": SENS},
       "note": "post-hoc disclosed re-analysis (erratum); no target verdict claimed from P1.9",
       "populations": {}, "per_sample": {}, "per_replicon_event": {}, "deployment_classes": {}}

for pname, pop in POPS.items():
    res["populations"][pname] = {}
    for sname, sel in STRATA.items():
        sub = sel(pop)
        if len(sub) == 0: continue
        entry = {"models": {}}
        for lab, thr in [("M2@0.9605_standard", STD), ("M2@0.9776_very_high_confidence", VHC)] + \
                        [(f"M2@{t}_sensitivity", t) for t in SENS]:
            entry["models"][lab] = metrics(sub, m2_call(sub, thr))
        entry["models"]["M0_three_state"] = metrics(sub, sub["M0_call"].values)
        res["populations"][pname][sname] = entry

# per-sample at the standard threshold
for pname, pop in POPS.items():
    res["per_sample"][pname] = {}
    for s, g in pop.groupby("sample"):
        res["per_sample"][pname][s] = {"dev_linked": bool(g["dev_linked"].iloc[0]),
                                       "M2@0.9605": metrics(g, m2_call(g, STD)),
                                       "M0": metrics(g, g["M0_call"].values)}

# per-replicon / event at the standard threshold
for pname, pop in POPS.items():
    ev = {}
    for lab, call in [("M2@0.9605", m2_call(pop, STD)), ("M0", pop["M0_call"].values)]:
        p2 = pop.copy(); p2["call"] = call
        p2["rep"] = np.where(p2["y"] == 1, p2["best_plasmid_hit"].astype(str).str.split(":").str[0],
                                            p2["best_chromosome_hit"].astype(str).str.split(":").str[0])
        p2["key"] = p2["sample"] + "|" + p2["rep"]
        tot = wtp = wfn = wfp = 0
        for k, g in p2.groupby("key"):
            y = g["y"].values; c = g["call"].values
            if (y == 1).all():
                tot += 1
                if ((c == 1) & (y == 1)).any(): wtp += 1
                if ((c == 0) & (y == 1)).any(): wfn += 1
            if ((c == 1) & (y == 0)).any(): wfp += 1
        ev[lab] = {"plasmid_replicons_total": tot, "plasmid_replicons_with_TP": wtp,
                   "plasmid_replicons_with_FN": wfn, "replicons_with_FP": wfp}
    res["per_replicon_event"][pname] = ev

# deployment class distribution over ALL contigs (contract layer)
allc = d.copy()
cls = np.where(allc["M2_score"] >= VHC, "very_high_confidence_plasmid",
      np.where(allc["M2_score"] >= STD, "supported_plasmid", "not_selected"))
allc["deployment_class"] = cls
res["deployment_classes"]["all_2070_contigs"] = allc["deployment_class"].value_counts().to_dict()
for pname, pop in POPS.items():
    sub = allc.loc[pop.index]
    res["deployment_classes"][pname] = (sub.groupby(["deployment_class", "final_truth_label"])
                                        .size().unstack(fill_value=0).to_dict())

json.dump(res, open(f"{OUT}/P1.10D_p19_rescore_results.json", "w"), indent=1, default=float)
allc[["sample", "contig_id", "contig_length", "final_truth_label", "ARG_bearing", "arg_core",
      "M2_score", "deployment_class", "M0_call", "dev_linked"]].to_csv(
      f"{OUT}/P1.10D_p19_contig_deployment_table.tsv", sep="\t", index=False)

# console summary
print("=== P1.9 RE-SCORE (frozen M2_score; no inference rerun) ===")
for pname in POPS:
    a = res["populations"][pname]["all_8_samples"]["models"]
    p = POPS[pname]
    print(f"\n-- {pname}: n={len(p)} ({int(p['y'].sum())} plasmid / {int((p['y']==0).sum())} chromosome)")
    print(f"   {'operating point':<34}{'TP':>4}{'FP':>4}{'TN':>5}{'FN':>4}{'abst':>6}  {'PPV':>7}{'recall':>8}{'spec':>7}{'F1':>7}{'MCC':>7}")
    for lab in ["M2@0.9605_standard", "M2@0.9776_very_high_confidence"] + [f"M2@{t}_sensitivity" for t in SENS] + ["M0_three_state"]:
        m = a[lab]; g = lambda v: "  n/a " if v is None else f"{v:7.3f}"
        print(f"   {lab:<34}{m['TP']:>4}{m['FP']:>4}{m['TN']:>5}{m['FN']:>4}{m['abstained']:>6}  {g(m['PPV'])}{g(m['recall'])}{g(m['specificity'])}{g(m['F1'])}{g(m['MCC'])}")
print("\n=== stratification by genomic relatedness (standard 0.9605) ===")
for pname in POPS:
    print(f"-- {pname}")
    for sname in STRATA:
        if sname in res["populations"][pname]:
            m = res["populations"][pname][sname]["models"]["M2@0.9605_standard"]
            print(f"   {sname:<24} n={m['n']:>3} pl={m['n_plasmid']:>3}  TP={m['TP']:>3} FP={m['FP']:>2}  PPV={m['PPV'] if m['PPV'] is None else round(m['PPV'],3)} recall={round(m['recall'],3)}")
print("\n=== deployment classes over all 2,070 contigs ===")
print(res["deployment_classes"]["all_2070_contigs"])
print("\n=== per-replicon (standard) ===")
for pname in POPS: print(f"   {pname}: {res['per_replicon_event'][pname]}")
exp = res["populations"]["primary_ARG_resolved"]["all_8_samples"]["models"]["M2@0.9605_standard"]
print("\n=== CHECK vs the owner-stated expectation (TP=20 FP=0 PPV=1.000 recall=0.606) ===")
print(f"   recomputed: TP={exp['TP']} FP={exp['FP']} PPV={exp['PPV']:.4f} recall={exp['recall']:.4f}")
print("   AGREES" if (exp['TP'] == 20 and exp['FP'] == 0 and abs(exp['PPV'] - 1.0) < 1e-9
                      and abs(exp['recall'] - 0.606) < 0.001) else "   CONTRADICTION - investigate")

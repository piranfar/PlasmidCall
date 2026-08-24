#!/usr/bin/env python3
"""Independent verifier: rederives every proposed manuscript value from the canonical
truth-joined table, independently of the evaluation code that produced the metrics files.

It recomputes from P113_TRUTH_JOINED.tsv only, then compares against the published tables.
Any disagreement is a finding. Also enforces the leakage and substitution checks.
"""
import csv, io, json, math, os, sys, collections

D = os.environ.get("P113_EVAL", "E:/AMR_Evidence_Data/P1.13/evaluation")
V12_T, V11_T, V11_HIGH = 0.9285, 0.9524, 0.9605
TOOLS = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
         "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
findings = []


def f(msg):
    findings.append(msg)


rows = list(csv.DictReader(io.open(D + "/P113_TRUTH_JOINED.tsv", encoding="utf-8"), delimiter="\t"))
E = [r for r in rows if r["is_eligible_ge_1kb"] == "1"]
R = [r for r in E if r["truth_state"] == "RESOLVED"]

# ---- denominator reconciliation
print("== denominators ==")
print("  joined rows        : %d" % len(rows))
print("  eligible >=1kb     : %d" % len(E))
print("  resolved (scored)  : %d" % len(R))
print("  unresolved         : %d" % (len(E) - len(R)))
print("  isolates           : %d" % len({r["sample"] for r in rows}))
if len(rows) != 19320:
    f("joined rows %d != 19320" % len(rows))
if len(E) != 9784:
    f("eligible %d != 9784" % len(E))
if len(R) != 9371:
    f("resolved %d != 9371" % len(R))
if len({r["sample"] for r in rows}) != 150:
    f("isolates != 150")

# ---- exactly one terminal truth state and one terminal prediction state per contig
seen = collections.Counter((r["sample"], r["contig_id"]) for r in rows)
dupe = [k for k, v in seen.items() if v > 1]
if dupe:
    f("%d duplicated contigs in the joined table" % len(dupe))
bad_state = [r for r in rows if r["truth_state"] not in ("RESOLVED", "UNRESOLVED", "NO_TRUTH_MAPPING")]
if bad_state:
    f("%d contigs without exactly one terminal truth state" % len(bad_state))
bad_pred = [r for r in E if r["v12_score_state"] not in ("available", "model_abstain")]
if bad_pred:
    f("%d eligible contigs without a terminal v1.2 prediction state" % len(bad_pred))

# ---- leakage checks
if any(r["sample"] == "SAMN26198730" for r in rows):
    f("EXCLUDED ISOLATE SAMN26198730 present in the evaluation set")
if not any(r["sample"] == "SAMN37639065" for r in rows):
    f("replacement isolate SAMN37639065 absent from the evaluation set")
if any(r["in_sealed_cohort"] != "1" for r in rows):
    f("contigs present that are not in the sealed cohort")


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def M(sel, call):
    tp = fp = tn = fn = 0
    for r in sel:
        c = call(r)
        if c is None:
            continue
        t = int(r["truth_bin"])
        if c == 1 and t == 1: tp += 1
        elif c == 1 and t == 0: fp += 1
        elif c == 0 and t == 0: tn += 1
        elif c == 0 and t == 1: fn += 1
    d = lambda a, b: (a / b) if b else None
    ppv, rec = d(tp, tp + fp), d(tp, tp + fn)
    spec, npv = d(tn, tn + fp), d(tn, tn + fn)
    f1 = (2 * ppv * rec / (ppv + rec)) if (ppv and rec) else None
    den = math.sqrt((tp+fp)*(tp+fn)*(tn+fp)*(tn+fn))
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn, "PPV": ppv, "recall": rec,
            "specificity": spec, "NPV": npv, "F1": f1,
            "balanced_accuracy": ((rec+spec)/2) if (rec is not None and spec is not None) else None,
            "MCC": ((tp*tn-fp*fn)/den) if den else None,
            "n_scored": tp+fp+tn+fn}


def thr(col, t):
    def c(r):
        v = num(r[col])
        return None if v is None else int(v >= t)
    return c


def router_call(r):
    if r["router_state"] != "routed":
        return None
    v = num(r["router_score"])
    if v is None:
        return None
    return int(v >= (V11_T if r["router_model"] == "v1.1" else V12_T))


def tool_call(t):
    def c(r):
        x = r[t].strip()
        return 1 if x == "plasmid" else (0 if x == "chromosome" else None)
    return c


MINE = {
    "v1.2-General@0.9285": M(R, thr("v12_score", V12_T)),
    "v1.1@0.9524": M(R, thr("v11_score", V11_T)),
    "v1.1@0.9605_high_conf": M(R, thr("v11_score", V11_HIGH)),
    "router": M(R, router_call),
}
for t in TOOLS:
    MINE["tool:" + t] = M(R, tool_call(t))

# ---- compare against the published tables
pub = {}
for fn in ("P113_PRIMARY_METRICS.tsv", "P113_COMPARATOR_METRICS.tsv"):
    for r in csv.DictReader(io.open(D + "/" + fn, encoding="utf-8"), delimiter="\t"):
        pub[r["predictor"]] = r

print("\n== independent recomputation vs published ==")
KEYS = ["TP", "FP", "TN", "FN", "PPV", "recall", "specificity", "NPV", "F1",
        "balanced_accuracy", "MCC"]
n_cmp = n_dis = 0
for name, mine in sorted(MINE.items()):
    if name not in pub:
        f("published tables have no row for %s" % name)
        continue
    p = pub[name]
    for k in KEYS:
        n_cmp += 1
        a, b = mine[k], num(p.get(k, ""))
        if a is None and (b is None or p.get(k, "") == ""):
            continue
        if a is None or b is None:
            n_dis += 1
            f("%s.%s: mine=%s published=%s" % (name, k, a, p.get(k)))
            continue
        tolr = 0 if k in ("TP", "FP", "TN", "FN") else 1e-9
        if abs(a - b) > tolr:
            n_dis += 1
            f("%s.%s: mine=%.10f published=%.10f" % (name, k, a, b))
print("  values compared     : %d" % n_cmp)
print("  disagreements       : %d" % n_dis)

# ---- headline values used in the manuscript
g = json.load(io.open(D + "/P113_PRIMARY_GATE.json", encoding="utf-8"))
p12 = MINE["v1.2-General@0.9285"]
print("\n== headline manuscript values, recomputed ==")
print("  v1.2-General PPV    : %.4f  (gate file %.4f)" % (p12["PPV"], g["PPV"]))
print("  v1.2-General recall : %.4f  (gate file %.4f)" % (p12["recall"], g["recall"]))
if abs(p12["PPV"] - g["PPV"]) > 1e-9 or abs(p12["recall"] - g["recall"]) > 1e-9:
    f("primary gate values do not match independent recomputation")

arg = [r for r in R if r["ARG_bearing_bool"].strip().lower() == "true"]
a12, art = M(arg, thr("v12_score", V12_T)), M(arg, router_call)
print("  ARG-bearing n       : %d" % len(arg))
print("  ARG v1.2 PPV/recall : %.4f / %.4f" % (a12["PPV"], a12["recall"]))
print("  ARG router PPV/rec  : %.4f / %.4f" % (art["PPV"], art["recall"]))

print("\n== verdict ==")
if findings:
    print("FINDINGS: %d" % len(findings))
    for x in findings[:25]:
        print("   - %s" % x)
    sys.exit(1)
print("ZERO UNEXPLAINED DISAGREEMENTS")
print("VERIFIER_PASS")

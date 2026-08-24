#!/usr/bin/env python3
"""Projected power for the P1.11 primary confirmatory analysis. PLANNING ESTIMATES ONLY.

PASS rule (predeclared): v1.2-General on CP2 at fixed threshold 0.9285 achieves PPV >= 0.95 AND
recall > 0.50.

Method: cluster bootstrap. Draw N isolates with replacement from the 39 observed P1.10 isolates,
using their leave-one-isolate-out calls, then apply an explicit degradation model:
  rec_mult  multiplier on recall (0.90 = lose a tenth of the true positives v1.2 would have found)
  fp_mult   multiplier on the observed false-positive RATE among true negatives (1.50 = half again
            as many false positives per chromosomal contig)
The observed baseline rate is measured from the data and printed below; the multipliers are
assumptions, stated in auditable units so the projection can be checked rather than believed.

The binding constraint is PPV, not recall, in the intact-panel scenarios: recall clears its bar by
roughly 0.28 while PPV clears its floor by roughly 0.02. A sensitivity grid over fp_mult is
therefore included. Tool-failure scenarios invert this - there recall is what collapses.

TOOL FAILURE IS SIMULATED CORRECTLY HERE. An earlier version zeroed the tool's one-hot block,
which is NOT neutral after StandardScaler and badly understated the impact. The frozen model is now
fed the tool as unavailable through apply_neutrality(), which is what deployment would do.
"""
import csv, json, os, sys, warnings
import numpy as np
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freeze_v12 import (encode, make_estimator, mets, TOOL_ORDER, apply_neutrality,
                        observed_states, neutral_from_pipeline, FROZEN_THRESHOLD, SEED, OUT, FREEZE)

N_P111 = 79
N_BOOT = 4000
rows = [r for r in csv.DictReader(open(os.path.join(OUT, "probe_dataset.tsv"), encoding="utf-8"),
                                  delimiter="\t")]
R = [r for r in rows if r["in_CP2"] == "1" and r["cohort"] == "P1.10"
     and r["truth_bin"] not in ("", "nan")]
y = np.array([int(float(r["truth_bin"])) for r in R])
g = np.array([r["sample"] for r in R])
v11 = np.array([float(r["v11_M2_score"]) for r in R])
CALLS = np.array([[r["cat_" + t] for t in TOOL_ORDER] for r in R], dtype=object)
X = encode(CALLS)
OBS = observed_states(CALLS)


def loio_fail(fail_tools):
    """leave-one-isolate-out; at SCORING time the named tools are unavailable, neutrality applied"""
    p_ = np.full(len(y), np.nan)
    cf = CALLS.copy()
    for t in fail_tools:
        cf[:, TOOL_ORDER.index(t)] = "MISSING"
    Xf = encode(cf)
    for h in sorted(set(g)):
        tr = g != h
        m = make_estimator(); m.fit(X[tr], y[tr])
        Xn = apply_neutrality(Xf[~tr], cf[~tr], neutral_from_pipeline(m), OBS)
        p_[~tr] = m.predict_proba(Xn)[:, 1]
    return (p_ >= FROZEN_THRESHOLD).astype(int)


c_full = loio_fail([])
c_worst = loio_fail(["PlaScope"])          # worst single tool in the corrected sensitivity analysis
c_median = loio_fail(["geNomad"])          # a mid-severity tool
FP_BASE = float(((c_full == 1) & (y == 0)).sum() / max(1, (y == 0).sum()))

iso = sorted(set(g))
idx = {i: np.where(g == i)[0] for i in iso}


def simulate(c, n_iso, rec_mult, fp_mult, n_boot=N_BOOT, seed=SEED):
    tp_drop = 1.0 - rec_mult
    fp_add = FP_BASE * (fp_mult - 1.0)
    rng = np.random.default_rng(seed)
    ppvs, recs, passes = [], [], []
    for _ in range(n_boot):
        s = rng.choice(iso, size=n_iso, replace=True)
        r = np.concatenate([idx[i] for i in s])
        yy = y[r]; cc = c[r].copy()
        if tp_drop > 0:
            m = (cc == 1) & (yy == 1)
            cc[m] = (rng.random(int(m.sum())) >= tp_drop).astype(int)
        if fp_add > 0:
            m = (cc == 0) & (yy == 0)
            cc[m] = (rng.random(int(m.sum())) < fp_add).astype(int)
        tp = int(((cc == 1) & (yy == 1)).sum()); fp = int(((cc == 1) & (yy == 0)).sum())
        fn = int(((cc == 0) & (yy == 1)).sum())
        if tp + fn == 0:
            continue
        rec = tp / (tp + fn)
        # A run that makes no positive call has undefined PPV and cannot pass.
        ppv = (tp / (tp + fp)) if (tp + fp) else 0.0
        ppvs.append(ppv); recs.append(rec)
        passes.append((tp + fp) > 0 and ppv >= 0.95 and rec > 0.50)
    q = lambda v, a: float(np.percentile(v, a))
    return {"n_isolates": n_iso, "recall_multiplier": rec_mult, "fp_rate_multiplier": fp_mult,
            "n_resamples": len(passes),
            "PPV_median": q(ppvs, 50), "PPV_ci95": [q(ppvs, 2.5), q(ppvs, 97.5)],
            "recall_median": q(recs, 50), "recall_ci95": [q(recs, 2.5), q(recs, 97.5)],
            "P_PPV_ge_0.95": float(np.mean(np.array(ppvs) >= 0.95)),
            "P_recall_gt_0.50": float(np.mean(np.array(recs) > 0.50)),
            "P_PASS": float(np.mean(passes))}


SCEN = [
    ("expected", c_full, N_P111, 1.00, 1.00,
     "v1.2 behaves on P1.11 as it did out-of-fold on P1.10, complete 12-tool panel"),
    ("modest_degradation", c_full, N_P111, 0.90, 1.25,
     "lose a tenth of true positives; false-positive rate a quarter higher"),
    ("conservative_degradation", c_full, N_P111, 0.80, 1.75,
     "lose a fifth of true positives; false-positive rate three quarters higher"),
    ("sample_loss_15pct", c_full, 67, 0.90, 1.25,
     "modest degradation plus 15% isolate attrition (79 -> 67)"),
    ("single_tool_failure_worst", c_worst, N_P111, 1.00, 1.00,
     "PlaScope unavailable for every contig - worst single tool in the corrected analysis"),
    ("single_tool_failure_median", c_median, N_P111, 1.00, 1.00,
     "geNomad unavailable for every contig - a mid-severity tool"),
    ("median_tool_failure_plus_modest", c_median, N_P111, 0.90, 1.25,
     "geNomad unavailable AND modest degradation"),
]

out = {"observed_fp_rate_among_true_negatives": FP_BASE,
       "pass_rule": "PPV >= 0.95 AND recall > 0.50, CP2, threshold 0.9285",
       "planning_N": N_P111, "n_bootstrap": N_BOOT,
       "basis": "cluster bootstrap over the 39 P1.10 isolates, leave-one-isolate-out calls",
       "tool_failure_method": ("frozen model fed the tool as unavailable through apply_neutrality; "
                               "NOT a zeroed one-hot block"),
       "status": "PLANNING ESTIMATE ONLY - not evidence about v1.2 performance",
       "scenarios": {}}
print("PROJECTED POWER - P1.11 primary confirmatory (N=%d isolates)" % N_P111)
print("PASS = CP2 PPV >= 0.95 AND recall > 0.50 at fixed threshold 0.9285")
print("observed false-positive rate among true negatives: %.5f (%d FP / %d chromosomal contigs)\n"
      % (FP_BASE, int(((c_full == 1) & (y == 0)).sum()), int((y == 0).sum())))
print("  %-32s | PPV median [95%% CI]      | recall median [95%% CI]   | P(PASS)" % "scenario")
print("  " + "-" * 100)
for name, c, n, rm, fm, note in SCEN:
    r = simulate(c, n, rm, fm)
    r["description"] = note
    out["scenarios"][name] = r
    print("  %-32s | %.4f [%.4f, %.4f] | %.4f [%.4f, %.4f] | %.3f"
          % (name, r["PPV_median"], r["PPV_ci95"][0], r["PPV_ci95"][1],
             r["recall_median"], r["recall_ci95"][0], r["recall_ci95"][1], r["P_PASS"]))

cA = (v11 >= 0.9524).astype(int)
rv = simulate(cA, N_P111, 1.00, 1.00)
out["reference_v11_on_CP2_expected"] = rv
print("\n  %-32s | %.4f [%.4f, %.4f] | %.4f [%.4f, %.4f] | %.3f"
      % ("[ref] v1.1 on CP2 expected", rv["PPV_median"], rv["PPV_ci95"][0], rv["PPV_ci95"][1],
         rv["recall_median"], rv["recall_ci95"][0], rv["recall_ci95"][1], rv["P_PASS"]))

grid = []
print("\nSENSITIVITY GRID - P(PASS) at N=79, complete panel. Rows: recall x. Cols: FP-rate x.")
hdr = [1.00, 1.25, 1.50, 1.75, 2.00, 2.50]
print("  recall x |" + "".join("  fp x%.2f " % h for h in hdr))
for rm in (1.00, 0.95, 0.90, 0.85, 0.80):
    line = "  %.2f     |" % rm
    for fm in hdr:
        r = simulate(c_full, N_P111, rm, fm, n_boot=1500)
        grid.append({"recall_multiplier": rm, "fp_rate_multiplier": fm, "P_PASS": r["P_PASS"],
                     "PPV_median": r["PPV_median"], "recall_median": r["recall_median"]})
        line += "   %.3f  " % r["P_PASS"]
    print(line)
out["sensitivity_grid"] = grid
out["grid_note"] = ("With a complete panel, P(PASS) is governed almost entirely by the "
                    "false-positive-rate multiplier: recall has roughly 0.28 of headroom above its "
                    "0.50 bar while PPV has roughly 0.02 above its 0.95 floor. Tool failure "
                    "inverts this - there recall collapses and becomes the binding constraint.")

json.dump(out, open(os.path.join(FREEZE, "P1.12_V1.2_PROJECTED_POWER.json"), "w"), indent=1)
print("\nwrote P1.12_V1.2_PROJECTED_POWER.json")

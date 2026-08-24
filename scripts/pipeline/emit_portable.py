#!/usr/bin/env python3
"""Emit a portable, plain-text form of the frozen estimator and verify it reproduces the pickle.

A pickle is version-fragile: it can stop loading when scikit-learn moves. The frozen model is a
standardised logistic regression, so it can be written out in full as numbers and re-implemented in
a few lines. This file is the authoritative definition; the pickle is a convenience.

    1. encode the 12 categorical calls into 102 raw features
    2. for any tool in a state NOT observed during training, overwrite that tool's 8 columns with
       neutral_raw[tool] so the block scales to exactly zero
    3. z = intercept + sum_i coef_i * (x_i - mean_i) / scale_i
    4. p = 1 / (1 + exp(-z))

Step 2 is not optional. Without it an absent tool still shifts the logit by up to ~3 units, because
a raw zero becomes -mean/scale under the scaler.
"""
import json, os, pickle, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freeze_v12 import (FEATURES, TOOL_ORDER, VOCAB, FREEZE, encode, apply_neutrality,
                        tool_block, predict, FROZEN_THRESHOLD)

B = pickle.load(open(os.path.join(FREEZE, "plasmidcall_v1_2_general.pkl"), "rb"))
pipe = B["pipeline"]
imp = pipe.named_steps["imp"]; sc = pipe.named_steps["sc"]; clf = pipe.named_steps["clf"]

port = {
    "model": "PlasmidCall v1.2-General",
    "form": "standardised logistic regression over 12 categorical tool calls",
    "scoring": ["encode calls -> 102 raw features",
                "apply neutrality to any tool in a state not present in observed_states",
                "z = intercept + sum_i coef[i] * (x[i] - mean[i]) / scale[i]",
                "p = 1/(1+exp(-z))"],
    "threshold": FROZEN_THRESHOLD,
    "probability_orientation": "higher means more plasmid-like",
    "n_features": len(FEATURES),
    "feature_names": FEATURES,
    "tool_order": TOOL_ORDER,
    "vocabulary": VOCAB,
    "observed_states": B["observed_states"],
    "neutral_raw": B["neutral_raw"],
    "neutrality_rule": B["neutrality_rule"],
    "tool_block_columns": {t: tool_block(j) for j, t in enumerate(TOOL_ORDER)},
    "intercept": float(clf.intercept_[0]),
    "coef": [float(v) for v in clf.coef_[0]],
    "scaler_mean": [float(v) for v in sc.mean_],
    "scaler_scale": [float(v) for v in sc.scale_],
    "imputer_statistics": [float(v) for v in imp.statistics_],
    "imputer_note": ("median per feature; encode() never emits NaN so this is a no-op on "
                     "well-formed input and exists only as a guard against a malformed row"),
}


def score_portable(calls):
    X = apply_neutrality(encode(calls), calls, port["neutral_raw"], port["observed_states"])
    z = port["intercept"] + ((X - np.array(port["scaler_mean"])) /
                             np.array(port["scaler_scale"])) @ np.array(port["coef"])
    return 1.0 / (1.0 + np.exp(-z))


# ---- verify against the pickle: exhaustive single-tool perturbations, multi-tool failures,
#      random panels, and out-of-vocabulary input
rng = np.random.default_rng(20260821)
cases = []
for t_i in range(12):
    for v in VOCAB + ["gibberish", ""]:
        row = ["chromosome"] * 12; row[t_i] = v; cases.append(row)
for k in range(1, 13):
    row = ["plasmid"] * 12
    for j in range(k):
        row[j] = "MISSING"
    cases.append(list(row))
    row2 = ["plasmid"] * 12
    for j in range(k):
        row2[j] = "FAILED"
    cases.append(row2)
for _ in range(4000):
    cases.append(list(rng.choice(VOCAB, size=12)))
cases += [["plasmid"] * 12, ["chromosome"] * 12, ["FAILED"] * 12, ["MISSING"] * 12]
C = np.array(cases, dtype=object)
a = predict(B, C)
b = score_portable(C)
d = float(np.max(np.abs(a - b)))
agree = int(((a >= FROZEN_THRESHOLD) == (b >= FROZEN_THRESHOLD)).sum())
print("portable vs pickle over %d panels: max |dp| = %.3e ; identical calls %d/%d"
      % (len(cases), d, agree, len(cases)))
assert d < 1e-12 and agree == len(cases), "portable form does not reproduce the pickle"

port["verification"] = {"n_panels_checked": len(cases), "max_abs_probability_difference": d,
                        "identical_classifications": agree,
                        "coverage": "every single-tool state incl. out-of-vocabulary, 1-12 "
                                    "simultaneous FAILED/MISSING, 4000 random panels"}
p = os.path.join(FREEZE, "P1.12_V1.2_MODEL_PORTABLE.json")
json.dump(port, open(p, "w"), indent=1)
print("wrote", os.path.basename(p))

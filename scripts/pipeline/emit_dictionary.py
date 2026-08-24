#!/usr/bin/env python3
"""Emit the v1.2-General feature dictionary and the encoding specification."""
import csv, json, os, pickle, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from freeze_v12 import (FEATURES, TOOL_ORDER, VOCAB, ABSTAIN, NONVOTE, UNAVAILABLE,
                        FREEZE, OUT, encode, tool_block)

B = pickle.load(open(os.path.join(FREEZE, "plasmidcall_v1_2_general.pkl"), "rb"))
clf = B["pipeline"].named_steps["clf"]
sc = B["pipeline"].named_steps["sc"]
coef = clf.coef_[0]

rows = [r for r in csv.DictReader(open(os.path.join(OUT, "probe_dataset.tsv"), encoding="utf-8"),
                                  delimiter="\t")]
R = [r for r in rows if r["in_CP2"] == "1" and r["cohort"] == "P1.10"
     and r["truth_bin"] not in ("", "nan")]
X = encode(np.array([[r["cat_" + t] for t in TOOL_ORDER] for r in R], dtype=object))

DESC = {"n_plasmid": "count of tools voting plasmid",
        "n_chrom": "count of tools voting chromosome",
        "n_valid": "count of tools casting any vote (abstention, FAILED and MISSING excluded)",
        "frac_plasmid": "n_plasmid / n_valid, 0 when n_valid is 0",
        "frac_chrom": "n_chrom / n_valid, 0 when n_valid is 0",
        "agreement": "max(frac_plasmid, frac_chrom): how one-sided the panel is"}

out = []
for i, f in enumerate(FEATURES):
    if f.startswith("onehot__"):
        _, tool, state = f.split("__")
        kind = "one_hot"
        d = "1 when %s returned the call '%s', else 0" % (tool, state)
    elif f.startswith("abstain__"):
        tool = f.split("__")[1]; state = ""
        kind = "abstention_indicator"
        d = "1 when %s abstained (unknown / unclassified / repeat), else 0" % tool
    else:
        tool = state = ""
        kind = "panel_summary"
        d = DESC[f]
    col = X[:, i]
    out.append({"index": i, "feature_name": f, "kind": kind, "tool": tool, "state": state,
                "description": d,
                "train_min": float(col.min()), "train_max": float(col.max()),
                "train_mean": float(col.mean()),
                "train_nonzero": int((col != 0).sum()),
                "zero_variance_in_training": bool(col.std() == 0),
                "coefficient": float(coef[i]),
                "inert": bool(col.std() == 0 and coef[i] == 0.0)})

p = os.path.join(FREEZE, "P1.12_V1.2_FEATURE_DICTIONARY.tsv")
with open(p, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t", lineterminator="\n")
    w.writeheader(); w.writerows(out)

inert = [o["feature_name"] for o in out if o["inert"]]
print("feature dictionary: %d features, %d inert (zero variance in training, coefficient exactly 0)"
      % (len(out), len(inert)))
print("inert features:")
for n in inert:
    print("   ", n)

spec = {
    "encoding_version": "v1.2-General",
    "immutable": True,
    "n_features": len(FEATURES),
    "tool_order": TOOL_ORDER,
    "vocabulary": VOCAB,
    "vocabulary_note": ("Fixed at freeze time, NOT learned from data. A tool call outside this "
                        "vocabulary sets no one-hot column: it becomes an all-zero block, which is "
                        "an absent vote, never a negative one."),
    "abstention_states": sorted(ABSTAIN),
    "non_voting_states": sorted(NONVOTE - {""}) + ["<empty string>"],
    "block_layout": [
        {"block": "one_hot", "columns": "0..83",
         "rule": "index = tool_position * 7 + vocabulary_position"},
        {"block": "abstention_indicator", "columns": "84..95",
         "rule": "index = 84 + tool_position"},
        {"block": "panel_summary", "columns": "96..101",
         "order": ["n_plasmid", "n_chrom", "n_valid", "frac_plasmid", "frac_chrom", "agreement"]},
    ],
    "missingness_rule": (
        "FAILED and MISSING each occupy their own one-hot column and are excluded from n_valid. "
        "They are never converted into a chromosome vote. Only PlasmidFinder/FAILED occurs in the "
        "training data (218 CP2 contigs) and carries a fitted weight."),
    "neutrality_rule": (
        "A one-hot block set to raw zero is NOT neutral after StandardScaler: each column becomes "
        "(0 - mean)/scale, so an absent tool still shifts the logit - measured at up to 2.97 "
        "logits before correction, with an arbitrary per-tool sign. Therefore any tool in a state "
        "NOT observed during training has its 8 raw columns overwritten with the training means, "
        "so the post-scaling block is exactly 0.0 and its logit contribution is exactly 0.0. "
        "States observed in training keep their learned encoding. Neutralisation is a strict "
        "no-op on the training data."),
    "neutrality_scope": (
        "The tool block (7 one-hot + 1 abstention indicator) is made exactly neutral. The "
        "panel-summary block is NOT frozen: an absent tool is excluded from n_valid, so those "
        "features honestly report a smaller panel. That residual is measured and reported in "
        "P1.12_V1.2_NEUTRALITY_PROOF.json rather than hidden."),
    "division_by_zero_rule": "when n_valid == 0, frac_plasmid and frac_chrom are 0.0 by definition",
    "preprocessing": ["SimpleImputer(strategy=median, add_indicator=False)",
                      "StandardScaler()",
                      "LogisticRegression(max_iter=4000, C=1.0, solver=lbfgs, random_state=20260821)"],
    "preprocessing_note": ("The imputer is retained for schema stability. encode() never emits NaN, "
                           "so it is a no-op on well-formed input; it exists so that a malformed "
                           "upstream row degrades to the training median rather than crashing."),
    "probability_orientation": "predict_proba(...)[:, 1]; higher means more plasmid-like",
    "threshold": 0.9285,
    "class_rule": {"plasmid_selected": "probability >= 0.9285",
                   "not_selected": "probability < 0.9285 - no positive plasmid evidence; "
                                   "NEVER a chromosome call"},
}
json.dump(spec, open(os.path.join(FREEZE, "P1.12_V1.2_ENCODING_SPEC.json"), "w"), indent=1)
print("\nwrote P1.12_V1.2_FEATURE_DICTIONARY.tsv and P1.12_V1.2_ENCODING_SPEC.json")

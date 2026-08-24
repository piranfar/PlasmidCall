#!/usr/bin/env python3
"""Freeze PlasmidCall v1.2-General.

Encoding is IMMUTABLE: the tool order and the per-tool vocabulary are written here as constants,
not learned from data, so the feature vector is reproducible without the training set.

MISSING-TOOL NEUTRALITY
-----------------------
A one-hot block followed by StandardScaler is NOT neutral when set to raw zero. For each column
the scaler computes (x - mean) / scale, so a raw zero becomes -mean/scale, and the ordinary
categories of an absent tool still push the logit. Measured on the frozen model this reached
-2.97 logits for PlasmidFinder (p 0.712 -> 0.063), with an arbitrary per-tool sign. A zero
coefficient on the unseen FAILED column does not make the block neutral: the neighbouring
chromosome and plasmid columns carry the shift.

The rule implemented here:

  state OBSERVED in training for that tool   -> use the learned encoding exactly
  state NOT OBSERVED in training             -> impute that tool's raw block to its training means,
                                                so the post-scaling block is exactly 0.0 and its
                                                logit contribution is exactly 0.0

This covers unseen FAILED and MISSING states and, on the same principle, any unseen abstention
state: the model has no fitted knowledge of a state it never saw, so that state must not move the
score. Observed states keep their learned weight - PlasmidFinder/FAILED (218 CP2 contigs) is the
only one in this cohort.

Neutralisation is a no-op on the training data, where every state is observed by construction.
The fitted estimator is therefore bit-identical to one fitted without it, and clean complete-panel
metrics are unchanged.

The panel-summary block (n_valid and friends) is deliberately NOT frozen: an absent tool is
excluded from the valid-vote count, so those features honestly report a smaller panel. That
residual is measured and reported separately rather than hidden - see report_neutrality().

Final estimator is fitted on P1.10 CP2 only. P1.9 is excluded because the reported evidence, the
PPV target and the threshold were all derived P1.10-only (P1.9 carries reference/database overlap
risk and differs temporally). Threshold and estimator therefore rest on the same data.
"""
import csv, json, os, hashlib, warnings, pickle, collections
import numpy as np
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

# Training data lives in the data tree, not in Git: probe_dataset.tsv is 6.4 MB and the repository
# does not carry bulk data. Override either path with P112_DATA / P112_FREEZE.
OUT = os.environ.get("P112_DATA", "E:/AMR_Evidence_Data/P1.9_cleanroom/p112")
FREEZE = os.environ.get("P112_FREEZE", os.path.join(OUT, "freeze"))
os.makedirs(FREEZE, exist_ok=True)
SEED = 20260821
PPV_TARGET = 0.970
FROZEN_THRESHOLD = 0.9285

# ---------------------------------------------------------------- IMMUTABLE ENCODING
TOOL_ORDER = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
              "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]
VOCAB = ["chromosome", "plasmid", "unknown", "unclassified", "repeat", "FAILED", "MISSING"]
ABSTAIN = {"unknown", "unclassified", "repeat"}
UNAVAILABLE = {"FAILED", "MISSING", ""}
NONVOTE = ABSTAIN | UNAVAILABLE
NV = len(VOCAB)


def feature_names():
    n = []
    for t in TOOL_ORDER:
        for v in VOCAB:
            n.append("onehot__%s__%s" % (t, v))
    for t in TOOL_ORDER:
        n.append("abstain__%s" % t)
    n += ["n_plasmid", "n_chrom", "n_valid", "frac_plasmid", "frac_chrom", "agreement"]
    return n


FEATURES = feature_names()
N_FEATURES = len(FEATURES)
PANEL_BLOCK = list(range(12 * NV + 12, N_FEATURES))


def tool_block(j):
    """column indices owned by tool j: its 7 one-hot columns plus its abstention indicator"""
    return list(range(j * NV, (j + 1) * NV)) + [12 * NV + j]


def normalise_call(v):
    v = (v or "").strip()
    return v if v in VOCAB else ""


def encode(calls_matrix):
    """calls_matrix: (n, 12) of raw tool call strings in TOOL_ORDER. Returns (n, 102) raw features.

    This is the plain encoding. It does NOT apply missing-tool neutrality; call apply_neutrality
    afterwards for inference. Training data needs no neutralisation.
    """
    n = len(calls_matrix)
    X = np.zeros((n, N_FEATURES), dtype=float)
    for i, row in enumerate(calls_matrix):
        npl = nch = nval = 0
        for j in range(12):
            v = normalise_call(row[j])
            if v:
                X[i, j * NV + VOCAB.index(v)] = 1.0
            if v in ABSTAIN:
                X[i, 12 * NV + j] = 1.0
            if v and v not in NONVOTE:
                nval += 1
                if v == "plasmid":
                    npl += 1
                elif v == "chromosome":
                    nch += 1
        fp = npl / nval if nval else 0.0
        fc = nch / nval if nval else 0.0
        X[i, PANEL_BLOCK] = [npl, nch, nval, fp, fc, max(fp, fc)]
    return X


def observed_states(calls_matrix):
    """the set of states actually seen per tool in the training data"""
    obs = {t: set() for t in TOOL_ORDER}
    for row in calls_matrix:
        for j, t in enumerate(TOOL_ORDER):
            v = normalise_call(row[j])
            if v:
                obs[t].add(v)
    return {t: sorted(s) for t, s in obs.items()}


def apply_neutrality(X, calls_matrix, neutral_raw, observed):
    """Impute the block of any tool in an UNOBSERVED state to its training means.

    neutral_raw: {tool: [8 raw values]} taken from the fitted scaler's means, so the post-scaling
                 block is exactly zero.
    observed:    {tool: [states seen in training]}
    Returns a copy. Rows whose every tool is in an observed state are returned unchanged.
    """
    X = np.array(X, dtype=float, copy=True)
    for i, row in enumerate(calls_matrix):
        for j, t in enumerate(TOOL_ORDER):
            v = normalise_call(row[j])
            if v not in observed[t]:          # unseen state, including "" (absent / out of vocabulary)
                X[i, tool_block(j)] = neutral_raw[t]
    return X


def make_estimator():
    return Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=False)),
                     ("sc", StandardScaler()),
                     ("clf", LogisticRegression(max_iter=4000, C=1.0, solver="lbfgs",
                                                random_state=SEED))])


def neutral_from_pipeline(pipe):
    """the raw values that scale to exactly zero, per tool block"""
    m = pipe.named_steps["sc"].mean_
    return {t: [float(v) for v in m[tool_block(j)]] for j, t in enumerate(TOOL_ORDER)}


def predict(bundle, calls_matrix):
    """the ONE supported inference path: encode, neutralise, score"""
    X = apply_neutrality(encode(calls_matrix), calls_matrix,
                         bundle["neutral_raw"], bundle["observed_states"])
    return bundle["pipeline"].predict_proba(X)[:, 1]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def pick_threshold(p, y, target, min_calls=10):
    for t in np.unique(np.round(p, 4)):
        s = p >= t
        if s.sum() < min_calls:
            continue
        if y[s].mean() >= target:
            return float(t)
    return 1.01


def mets(y, c):
    tp = int(((c == 1) & (y == 1)).sum()); fp = int(((c == 1) & (y == 0)).sum())
    tn = int(((c == 0) & (y == 0)).sum()); fn = int(((c == 0) & (y == 1)).sum())
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "PPV": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "specificity": tn / (tn + fp) if tn + fp else None}


def report_neutrality(bundle, base_calls):
    """Measure the exact per-tool logit contribution when a tool becomes unavailable.

    The neutrality requirement is about the ABSENT TOOL'S OWN CONTRIBUTION, not about the logit
    staying put: removing an informative vote must move the score. Three quantities are measured:

      contribution_after      the absent tool's own contribution to the logit. MUST be exactly 0
                              for an unseen state. For an observed state it keeps its learned value.
      other_blocks_unchanged  every available tool's scaled features are bit-identical to the
                              reference panel, so available tools retain their normal contributions.
      dlogit_panel            the honest residual from n_valid falling by one. Reported, not
                              suppressed: freezing it would mean pretending an absent tool voted.
    """
    pipe = bundle["pipeline"]
    sc = pipe.named_steps["sc"]; clf = pipe.named_steps["clf"]
    coef = clf.coef_[0]

    def z(calls):
        X = apply_neutrality(encode(calls), calls, bundle["neutral_raw"],
                             bundle["observed_states"])
        return (X - sc.mean_) / sc.scale_

    zb = z(np.array([base_calls], dtype=object))[0]
    lb = float(clf.intercept_[0] + zb @ coef)
    rows = []
    for j, t in enumerate(TOOL_ORDER):
        for state in ("FAILED", "MISSING"):
            row = list(base_calls); row[j] = state
            za = z(np.array([row], dtype=object))[0]
            la = float(clf.intercept_[0] + za @ coef)
            blk = tool_block(j)
            others = [k for k in range(N_FEATURES) if k not in blk and k not in PANEL_BLOCK]
            rows.append({
                "tool": t, "state": state,
                "state_observed_in_training": state in bundle["observed_states"][t],
                "contribution_before": float(zb[blk] @ coef[blk]),
                "contribution_after": float(za[blk] @ coef[blk]),
                "max_abs_scaled_value_in_block": float(np.max(np.abs(za[blk]))),
                "other_blocks_unchanged": bool(np.array_equal(za[others], zb[others])),
                "dlogit_panel": float((za[PANEL_BLOCK] - zb[PANEL_BLOCK]) @ coef[PANEL_BLOCK]),
                "dlogit_total": la - lb,
                "p_before": 1 / (1 + np.exp(-lb)), "p_after": 1 / (1 + np.exp(-la))})
    return lb, rows


if __name__ == "__main__":
    # ------------------------------------------------------------ data
    rows = [r for r in csv.DictReader(open(os.path.join(OUT, "probe_dataset.tsv"),
                                           encoding="utf-8"), delimiter="\t")]
    R = [r for r in rows if r["in_CP2"] == "1" and r["cohort"] == "P1.10"
         and r["truth_bin"] not in ("", "nan")]
    y = np.array([int(float(r["truth_bin"])) for r in R])
    g = np.array([r["sample"] for r in R])
    calls = np.array([[r["cat_" + t] for t in TOOL_ORDER] for r in R], dtype=object)
    X = encode(calls)
    OBS = observed_states(calls)
    print("training data: %d contigs, %d isolates, %d plasmid, %d features"
          % (len(y), len(set(g)), int(y.sum()), X.shape[1]))
    print("observed states per tool:")
    for t in TOOL_ORDER:
        print("   %-14s %s" % (t, ", ".join(OBS[t])))

    # ------------------------------------------------------------ clean OOF reproduction
    p = np.full(len(y), np.nan)
    for h in sorted(set(g)):
        tr = g != h
        m = make_estimator(); m.fit(X[tr], y[tr]); p[~tr] = m.predict_proba(X[~tr])[:, 1]
    oof_thr = pick_threshold(p, y, PPV_TARGET)
    c = (p >= FROZEN_THRESHOLD).astype(int)
    M = mets(y, c)
    print("\nCLEAN OOF REPRODUCTION at the frozen threshold %.4f" % FROZEN_THRESHOLD)
    print("  PPV=%.4f recall=%.4f spec=%.4f  TP=%d FP=%d TN=%d FN=%d"
          % (M["PPV"], M["recall"], M["specificity"], M["TP"], M["FP"], M["TN"], M["FN"]))
    print("  threshold re-derived at PPV target %.3f: %.4f" % (PPV_TARGET, oof_thr))

    v11 = np.array([float(r["v11_M2_score"]) for r in R])
    cA = (v11 >= 0.9524).astype(int)
    MA = mets(y, cA)
    imp = wor = 0
    for h in sorted(set(g)):
        m = g == h
        if y[m].sum() == 0:
            continue
        rn = ((c[m] == 1) & (y[m] == 1)).sum() / y[m].sum()
        ro = ((cA[m] == 1) & (y[m] == 1)).sum() / y[m].sum()
        imp += rn > ro; wor += rn < ro
    print("  v1.1 comparator: PPV=%.4f recall=%.4f" % (MA["PPV"], MA["recall"]))
    print("  isolates improved=%d worsened=%d  recall gain=%+.4f"
          % (imp, wor, M["recall"] - MA["recall"]))

    # ------------------------------------------------------------ final fit
    final = make_estimator()
    final.fit(X, y)
    NEUTRAL = neutral_from_pipeline(final)
    bundle = {"pipeline": final, "feature_names": FEATURES, "tool_order": TOOL_ORDER,
              "vocab": VOCAB, "threshold": FROZEN_THRESHOLD, "ppv_target": PPV_TARGET,
              "seed": SEED, "observed_states": OBS, "neutral_raw": NEUTRAL,
              "neutrality_rule": ("unobserved state -> tool block imputed to training means -> "
                                  "post-scaling block exactly 0.0"),
              "trained_on": "P1.10 CP2 (39 isolates, %d contigs)" % len(y)}

    # neutralisation must be a strict no-op on training data
    Xn = apply_neutrality(X, calls, NEUTRAL, OBS)
    assert np.array_equal(X, Xn), "neutralisation altered the training matrix"
    print("\n  neutralisation is a strict no-op on training data: CONFIRMED")

    pin = final.predict_proba(X)[:, 1]
    Mi = mets(y, (pin >= FROZEN_THRESHOLD).astype(int))
    print("  in-sample PPV=%.4f recall=%.4f (not a performance claim)"
          % (Mi["PPV"], Mi["recall"]))

    # ------------------------------------------------------------ neutrality proof
    base = ["chromosome"] * 12
    base[3] = "plasmid"; base[6] = "plasmid"; base[9] = "plasmid"
    lb, nrows = report_neutrality(bundle, base)
    unseen = [r for r in nrows if not r["state_observed_in_training"]]
    seen = [r for r in nrows if r["state_observed_in_training"]]
    wb = max(abs(r["contribution_after"]) for r in unseen)
    wz = max(r["max_abs_scaled_value_in_block"] for r in unseen)
    wp = max(abs(r["dlogit_panel"]) for r in unseen)
    allother = all(r["other_blocks_unchanged"] for r in nrows)
    print("\nNEUTRALITY PROOF (reference panel logit %+.6f)" % lb)
    print("  unseen states checked: %d over 12 tools" % len(unseen))
    print("  max |scaled value| inside a neutralised block   : %.3e  (must be 0)" % wz)
    print("  max |contribution| of an absent unseen-state tool: %.3e  (must be 0)" % wb)
    print("  every available tool unchanged                  : %s" % allother)
    print("  max |dlogit_panel| (honest n_valid residual)    : %.6f" % wp)
    print("  reference contribution of those tools ranged    : %.4f to %.4f"
          % (min(r["contribution_before"] for r in unseen),
             max(r["contribution_before"] for r in unseen)))
    for r in seen:
        print("  observed state keeps its learned weight: %s/%s contribution=%+.6f"
              % (r["tool"], r["state"], r["contribution_after"]))
    assert wb < 1e-12 and wz < 1e-12 and allother, "neutrality violated"

    # ------------------------------------------------------------ serialise
    mp = os.path.join(FREEZE, "plasmidcall_v1_2_general.pkl")
    with open(mp, "wb") as f:
        pickle.dump(bundle, f, protocol=4)
    print("\n  serialized: %s  sha256=%s" % (os.path.basename(mp), sha(mp)))

    clf = final.named_steps["clf"]; sc = final.named_steps["sc"]
    coef = clf.coef_[0]
    order = np.argsort(-np.abs(coef))
    with open(os.path.join(FREEZE, "P1.12_V1.2_COEFFICIENTS.tsv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["rank", "feature_index", "feature_name", "coefficient", "abs_coefficient",
                    "scaler_mean", "scaler_scale"])
        for rank, i in enumerate(order, 1):
            w.writerow([rank, int(i), FEATURES[i], "%.10f" % coef[i], "%.10f" % abs(coef[i]),
                        "%.10f" % sc.mean_[i], "%.10f" % sc.scale_[i]])
    print("  intercept: %.10f" % clf.intercept_[0])
    print("\n  TOP 10 COEFFICIENTS (conditional multivariable weights, NOT standalone tool effects)")
    for rank, i in enumerate(order[:10], 1):
        print("   %2d  %-42s %+.5f" % (rank, FEATURES[i], coef[i]))

    json.dump({"clean_oof": M, "v11_comparator": MA, "in_sample_final": Mi,
               "threshold": FROZEN_THRESHOLD, "ppv_target": PPV_TARGET,
               "threshold_rederived_from_clean_oof": oof_thr,
               "isolates_improved": int(imp), "isolates_worsened": int(wor),
               "recall_gain": M["recall"] - MA["recall"],
               "observed_states": OBS,
               "neutrality": {"max_abs_scaled_in_neutralised_block": wz,
                              "max_abs_contribution_absent_unseen_tool": wb,
                              "all_available_tools_unchanged": allother,
                              "max_abs_dlogit_panel_unseen": wp,
                              "no_op_on_training_data": True},
               "n_features": int(X.shape[1]), "n_contigs": int(len(y)),
               "n_isolates": int(len(set(g))), "intercept": float(clf.intercept_[0]),
               "model_sha256": sha(mp), "seed": SEED},
              open(os.path.join(FREEZE, "P1.12_V1.2_TRAINING_RECEIPT.json"), "w"), indent=1)
    json.dump({"reference_panel": base, "reference_logit": lb, "rows": nrows},
              open(os.path.join(FREEZE, "P1.12_V1.2_NEUTRALITY_PROOF.json"), "w"), indent=1)
    print("\nwrote freeze artifacts to", FREEZE)

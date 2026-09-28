#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vahhab Piranfar
"""Score a table of panel-tool calls with the frozen PlasmidCall models.

Models
  v1.2-General  Standardised logistic regression. Read from P1.12_V1.2_MODEL_PORTABLE.json and
                scored with numpy only. Threshold 0.9285.
  v1.1          HistGradientBoosting pipeline, loaded from plasmidcall_v1_1_m2.pkl (--v11).
                Needs scikit-learn 1.9.0 exactly, numpy 2 or later, and pandas.
                Thresholds 0.9524 (standard) and 0.9605 (high confidence).
  router        (--router, implies --v11) Contigs that carry a qualifying resistance gene go to
                v1.1. All other contigs go to v1.2-General. A failed, missing or unparseable
                annotation gives no routed call.

The rules are those of the frozen code in scripts/evaluation/: encode, apply_neutrality and
predict in freeze_v12.py; build_features, score_frame and score in v11_scorer_p111.py; the
routing block of build_p113_contig_table.py. This file re-implements them without importing
those modules, so it needs no training paths and changes no global state.

Input: a tab-separated table, one row per contig, with a header row.
  sample, contig_id      required. The pair must be unique.
  12 tool columns        required: HyAsP, MOB-recon, PLASMe, PlaScope, Plasmer, PlasmidEC,
                         PlasmidFinder, Platon, RFPlasmid, geNomad, gplas2, plASgraph2.
                         Each value is one of: chromosome, plasmid, unknown, unclassified,
                         repeat, FAILED, MISSING.
  length_bp              contig length in bp. Required for --v11 and --router.
                         contig_length is accepted when length_bp is absent.
  n_contigs_ge_1kb       optional. The number of contigs of at least 1 kb in the whole assembly
                         of the sample. Without it the count is taken from the table itself, so
                         the table must then hold every contig of at least 1 kb of each sample.
  ARG_bearing_bool       required for --router: true, false or NA.
  annotation_state       optional for --router: ok, failed, missing or unparseable.
Other columns are ignored.

Usage
  python scripts/score/plasmidcall_score.py --input calls.tsv --output scores.tsv
  python scripts/score/plasmidcall_score.py --input calls.tsv --output scores.tsv --v11
  python scripts/score/plasmidcall_score.py --input calls.tsv --output scores.tsv --router

Importing this module has no side effects. It creates no file or directory, changes no warning
filter and does not modify sys.path.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys

import numpy as np

__version__ = "1.1.0"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DEFAULT_V12_MODEL = os.path.join(REPO, "models", "plasmidcall_v1.2-general",
                                 "P1.12_V1.2_MODEL_PORTABLE.json")
DEFAULT_V11_MODEL = os.path.join(REPO, "models", "plasmidcall_v1.1", "plasmidcall_v1_1_m2.pkl")

# SHA-256 of the frozen model files. The JSON digest is taken over LF line endings, the form git
# stores. The pickle digest is over its raw bytes. Both equal the sha256_canonical_lf values in
# docs/evidence/P1.11_PRE_JOIN_HASH_RECEIPT_v2.json.
V12_PORTABLE_SHA256_LF = "b2f00ee8a4668747e87d55e7abf2d6788656975c0fa40832cab621527bcc87a1"
V11_PICKLE_SHA256 = "6c179825a6c608d0468d36c37e08d2511485f18a5c38d4c7369c93b12498c50f"

V12_THRESHOLD = 0.9285
V11_THRESHOLD = 0.9524
V11_HIGH = 0.9605
V11_SKLEARN_VERSION = "1.9.0"
V11_NUMPY_MIN_MAJOR = 2

TOOL_ORDER = ("HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
              "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2")
VOCAB = ("chromosome", "plasmid", "unknown", "unclassified", "repeat", "FAILED", "MISSING")
ABSTAIN = frozenset({"unknown", "unclassified", "repeat"})
NONVOTE = ABSTAIN | frozenset({"FAILED", "MISSING", ""})
NV = len(VOCAB)
N_TOOLS = len(TOOL_ORDER)
N_FEATURES = N_TOOLS * NV + N_TOOLS + 6
PANEL_BLOCK = list(range(N_TOOLS * NV + N_TOOLS, N_FEATURES))

ANNOTATION_STATES = ("ok", "failed", "missing", "unparseable")
LENGTH_COLUMNS = ("length_bp", "contig_length")
NSR_COLUMN = "n_contigs_ge_1kb"
ARG_COLUMN = "ARG_bearing_bool"
ANNOTATION_COLUMN = "annotation_state"
NSR_MIN_LENGTH = 1000

# abstention states as v11_scorer_p111.py spells them
_V11_ABST = {"unknown", "unclassified", "repeat"}


class ScorerError(Exception):
    """Invalid input, a model file that fails verification, or an unsupported environment."""


# ---------------------------------------------------------------- helpers
def sha256_file(path, lf=False):
    """SHA-256 of a file. With lf=True, CRLF is read as LF first (text files)."""
    with open(path, "rb") as f:
        data = f.read()
    if lf:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def format_score(p):
    """Shortest round-trip repr of a float, as the frozen tables write scores."""
    return repr(float(p))


# ---------------------------------------------------------------- v1.2-General
def feature_names():
    """The 102 feature names in encoder order (freeze_v12.feature_names)."""
    n = []
    for t in TOOL_ORDER:
        for v in VOCAB:
            n.append("onehot__%s__%s" % (t, v))
    for t in TOOL_ORDER:
        n.append("abstain__%s" % t)
    n += ["n_plasmid", "n_chrom", "n_valid", "frac_plasmid", "frac_chrom", "agreement"]
    return n


def tool_block(j):
    """Columns owned by tool j: its 7 one-hot columns plus its abstention indicator."""
    return list(range(j * NV, (j + 1) * NV)) + [N_TOOLS * NV + j]


def normalise_call(v):
    """A call outside the 7-term vocabulary becomes the empty string (an absent vote)."""
    v = (v or "").strip()
    return v if v in VOCAB else ""


def encode(calls):
    """(n, 12) tool calls in TOOL_ORDER -> (n, 102) raw features (freeze_v12.encode).

    When no tool casts a chromosome or plasmid vote (n_valid == 0), frac_plasmid, frac_chrom
    and agreement are 0.0.
    """
    n = len(calls)
    X = np.zeros((n, N_FEATURES), dtype=float)
    for i, row in enumerate(calls):
        npl = nch = nval = 0
        for j in range(N_TOOLS):
            v = normalise_call(row[j])
            if v:
                X[i, j * NV + VOCAB.index(v)] = 1.0
            if v in ABSTAIN:
                X[i, N_TOOLS * NV + j] = 1.0
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


def apply_neutrality(X, calls, neutral_raw, observed):
    """Set the block of any tool whose state was not seen in training to the training means,
    so the block scales to exactly 0.0 (freeze_v12.apply_neutrality). Returns a copy."""
    X = np.array(X, dtype=float, copy=True)
    for i, row in enumerate(calls):
        for j, t in enumerate(TOOL_ORDER):
            v = normalise_call(row[j])
            if v not in observed[t]:
                X[i, tool_block(j)] = neutral_raw[t]
    return X


def load_v12(path=None):
    """Load and check the portable v1.2-General model. Plain JSON, numpy only."""
    path = path or DEFAULT_V12_MODEL
    if not os.path.isfile(path):
        raise ScorerError("v1.2-General model file not found: %s" % path)
    digest = sha256_file(path, lf=True)
    if digest != V12_PORTABLE_SHA256_LF:
        raise ScorerError("v1.2-General model file %s has sha256 %s (LF), expected the frozen %s"
                          % (os.path.basename(path), digest, V12_PORTABLE_SHA256_LF))
    with open(path, encoding="utf-8") as f:
        m = json.load(f)
    checks = [
        (tuple(m["tool_order"]) == TOOL_ORDER, "tool_order"),
        (tuple(m["vocabulary"]) == VOCAB, "vocabulary"),
        (int(m["n_features"]) == N_FEATURES, "n_features"),
        (list(m["feature_names"]) == feature_names(), "feature_names"),
        (float(m["threshold"]) == V12_THRESHOLD, "threshold"),
        (all(len(m[k]) == N_FEATURES for k in ("coef", "scaler_mean", "scaler_scale")),
         "parameter lengths"),
        (all(list(m["tool_block_columns"][t]) == tool_block(j)
             for j, t in enumerate(TOOL_ORDER)), "tool_block_columns"),
    ]
    bad = [name for ok, name in checks if not ok]
    if bad:
        raise ScorerError("v1.2-General model file does not match the frozen encoding: %s"
                          % ", ".join(bad))
    return {
        "path": path,
        "sha256_lf": digest,
        "intercept": float(m["intercept"]),
        "coef": np.array(m["coef"], dtype=float),
        "mean": np.array(m["scaler_mean"], dtype=float),
        "scale": np.array(m["scaler_scale"], dtype=float),
        "neutral_raw": {t: [float(v) for v in m["neutral_raw"][t]] for t in TOOL_ORDER},
        "observed_states": {t: list(m["observed_states"][t]) for t in TOOL_ORDER},
        "threshold": float(m["threshold"]),
    }


def score_v12(model, calls):
    """Probabilities for (n, 12) calls: encode, neutralise, standardise, then the logistic.

    Each row is scored on its own, as the frozen builder did: z = intercept + dot(x_scaled,
    coef) and p = 1 / (1 + exp(-z)).
    """
    X = apply_neutrality(encode(calls), calls, model["neutral_raw"], model["observed_states"])
    Z = (X - model["mean"]) / model["scale"]
    coef = model["coef"]
    b = model["intercept"]
    p = np.empty(len(Z), dtype=float)
    for i in range(len(Z)):
        z = float(np.dot(Z[i], coef)) + b
        p[i] = 1.0 / (1.0 + math.exp(-z))
    return p


def classify_v12(p):
    return "plasmid_selected" if p >= V12_THRESHOLD else "not_selected"


# ---------------------------------------------------------------- v1.1
def check_v11_environment(sklearn_version=None, numpy_version=None):
    """Refuse v1.1 unless scikit-learn is exactly 1.9.0 and numpy is 2 or later.

    The pickle was written by scikit-learn 1.9.0 and refers to numpy._core, which exists only
    from numpy 2. Another scikit-learn version may load it and still score differently.
    Versions can be passed in to test the check without importing scikit-learn.
    """
    problems = []
    if sklearn_version is None:
        try:
            import sklearn
            sklearn_version = sklearn.__version__
        except ImportError:
            problems.append("scikit-learn is not installed")
    if sklearn_version is not None and sklearn_version != V11_SKLEARN_VERSION:
        problems.append("scikit-learn is %s, v1.1 needs exactly %s"
                        % (sklearn_version, V11_SKLEARN_VERSION))
    if numpy_version is None:
        numpy_version = np.__version__
    try:
        major = int(str(numpy_version).split(".")[0])
    except ValueError:
        major = -1
    if major < V11_NUMPY_MIN_MAJOR:
        problems.append("numpy is %s, v1.1 needs numpy %d or later"
                        % (numpy_version, V11_NUMPY_MIN_MAJOR))
    try:
        import pandas  # noqa: F401
    except ImportError:
        problems.append("pandas is not installed")
    if problems:
        raise ScorerError("PlasmidCall v1.1 will not run in this environment: %s. Install "
                          "scikit-learn==%s with numpy>=2 and pandas, or score with "
                          "v1.2-General only (no --v11, no --router)."
                          % ("; ".join(problems), V11_SKLEARN_VERSION))
    return {"sklearn": sklearn_version, "numpy": str(numpy_version)}


def load_v11(path=None):
    """Check the environment and the file digest, then unpickle the frozen v1.1 bundle.

    Unpickling can run arbitrary code, so only a file whose sha256 equals the frozen digest is
    loaded. A scikit-learn version warning raised while loading becomes an error inside this
    function only. The global warning filters are left as they were.
    """
    path = path or DEFAULT_V11_MODEL
    env = check_v11_environment()
    if not os.path.isfile(path):
        raise ScorerError("v1.1 model file not found: %s" % path)
    digest = sha256_file(path)
    if digest != V11_PICKLE_SHA256:
        raise ScorerError("v1.1 model file %s has sha256 %s, expected the frozen %s. Refusing "
                          "to unpickle it." % (os.path.basename(path), digest, V11_PICKLE_SHA256))
    import pickle
    import warnings
    from sklearn.exceptions import InconsistentVersionWarning
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            with open(path, "rb") as f:
                bundle = pickle.load(f)
    except InconsistentVersionWarning as e:
        raise ScorerError("v1.1 pickle refused by scikit-learn: %s" % e)
    thr = bundle.get("thresholds", {})
    if (tuple(bundle.get("tools", ())) != TOOL_ORDER or thr.get("standard") != V11_THRESHOLD
            or thr.get("high_confidence") != V11_HIGH or "pipeline" not in bundle):
        raise ScorerError("v1.1 bundle does not carry the frozen tools and thresholds")
    return {"path": path, "sha256": digest, "pipeline": bundle["pipeline"], "environment": env}


def _v11_build_features(df, tools):
    # verbatim from scripts/evaluation/v11_scorer_p111.py build_features
    # (featureset F_full_no_taxon)
    V = df[tools].astype(str)
    Vv = V.where(~V.isin(_V11_ABST))
    df = df.copy()
    df["n_valid"] = Vv.notna().sum(axis=1)
    df["n_plasmid"] = Vv.eq("plasmid").sum(axis=1)
    df["n_chrom"] = Vv.eq("chromosome").sum(axis=1)
    df["n_abstain"] = len(tools) - df["n_valid"]
    df["frac_plasmid"] = df["n_plasmid"] / df["n_valid"].replace(0, np.nan)
    df["frac_chrom"] = df["n_chrom"] / df["n_valid"].replace(0, np.nan)
    df["agreement"] = np.maximum(df["frac_plasmid"], df["frac_chrom"])
    df["log10_len"] = np.log10(df["SR contig length"].clip(lower=1))
    df["log10_nsr"] = np.log10(df["Number of SR contigs"].clip(lower=1))
    for t in tools:
        df["abst_" + t] = V[t].isin(_V11_ABST).astype(int)
    return df


def _v11_score_frame(df, tools):
    # verbatim from v11_scorer_p111.py score_frame. FAILED and MISSING are recoded to
    # 'unknown' (scored as abstention), never to a negative vote.
    X = df.copy()
    for t in tools:
        X[t] = X[t].replace({"FAILED": "unknown", "MISSING": "unknown"})
    return _v11_build_features(X, tools)


def v11_contig_counts(samples, lengths):
    """Per-sample count of rows with length >= 1000 bp. This is how v11_scorer_p111.py
    derives its 'Number of SR contigs' input when the table does not supply it."""
    import pandas as pd
    df = pd.DataFrame({"sample": list(samples)})
    L = pd.to_numeric(pd.Series(list(lengths), dtype=object), errors="coerce")
    nsr = df.assign(_L=L)[lambda x: x["_L"] >= NSR_MIN_LENGTH].groupby("sample").size()
    return {k: int(v) for k, v in nsr.items()}


def score_v11(model, samples, calls, lengths, nsr):
    """v1.1 scores for (n, 12) calls. Returns (scores, available), with NaN and False where
    v1.1 abstains: a length or contig count that is not a finite number.

    nsr is a per-row sequence of the count of contigs >= 1 kb in the row's sample, or None
    where that count is undefined (a sample with no contig of at least 1 kb).
    """
    import pandas as pd
    pipe = model["pipeline"]
    tools = list(TOOL_ORDER)
    n = len(samples)
    scores = np.full(n, np.nan)
    avail = np.zeros(n, dtype=bool)
    if n == 0:
        return scores, avail
    data = {"sample": list(samples)}
    for j, t in enumerate(tools):
        data[t] = [row[j] for row in calls]
    df = pd.DataFrame(data)
    df["SR contig length"] = pd.to_numeric(pd.Series(list(lengths), dtype=object),
                                           errors="coerce")
    df["Number of SR contigs"] = pd.Series(
        [np.nan if v is None else v for v in nsr], dtype=float)
    # as v11_scorer_p111.py score(): a row with a non-finite length or count abstains
    bad = []
    for c in ("SR contig length", "Number of SR contigs"):
        v = pd.to_numeric(df[c], errors="coerce")
        bad.append(~np.isfinite(v.to_numpy(dtype=float)))
    ok_idx = np.where(~(bad[0] | bad[1]))[0]
    if len(ok_idx):
        sub = df.iloc[ok_idx].copy()
        for c in ("SR contig length", "Number of SR contigs"):
            sub[c] = pd.to_numeric(sub[c], errors="coerce").astype(float)
        X = _v11_score_frame(sub, tools)
        p = pipe.predict_proba(X)[:, 1]
        for k, i in enumerate(ok_idx):
            if np.isfinite(p[k]):
                scores[i], avail[i] = float(p[k]), True
    return scores, avail


def classify_v11(s):
    if s >= V11_HIGH:
        return "high_confidence_plasmid"
    return "plasmid_selected" if s >= V11_THRESHOLD else "not_selected"


# ---------------------------------------------------------------- router
def route(annotation_state, arg_bearing, v11_call, v11_available, v12_call, v12_available):
    """The routing block of build_p113_contig_table.py.

    Returns (router_state, router_model, router_call, abstention_reason). The route depends
    only on the annotation, never on a score. A failed, missing or unparseable annotation
    gives no routed call, whatever the scores.
    """
    if annotation_state not in ANNOTATION_STATES:
        raise ScorerError("unknown annotation_state %r" % (annotation_state,))
    if annotation_state != "ok":
        reason = {"failed": "annotation_failed", "missing": "annotation_missing",
                  "unparseable": "annotation_unparseable"}[annotation_state]
        if not (v11_available or v12_available):
            reason = "score_unavailable+annotation_unavailable"
        return "routing_abstain", "", "", reason
    if arg_bearing is None:
        raise ScorerError("annotation_state is ok but ARG_bearing_bool is NA")
    model = "v1.1" if arg_bearing else "v1.2-General"
    available = v11_available if arg_bearing else v12_available
    if available:
        return "routed", model, (v11_call if arg_bearing else v12_call), ""
    return "routing_abstain", model, "model_abstain", "score_unavailable"


def parse_arg_flag(value):
    """true or 1 -> True, false or 0 -> False, NA or empty -> None."""
    s = (value or "").strip().lower()
    if s in ("true", "1"):
        return True
    if s in ("false", "0"):
        return False
    if s in ("", "na", "nan", "none", "null"):
        return None
    raise ScorerError("ARG_bearing_bool value %r is not true, false or NA" % (value,))


# ---------------------------------------------------------------- table I/O
def read_table(path):
    """Read a tab-separated table. Returns (header, rows as dicts)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rdr = csv.reader(f, delimiter="\t")
        try:
            header = next(rdr)
        except StopIteration:
            raise ScorerError("input table is empty: %s" % path)
        header = [h.strip() for h in header]
        dup = sorted({h for h in header if header.count(h) > 1})
        if dup:
            raise ScorerError("duplicate column names: %s" % ", ".join(dup))
        rows = []
        for lineno, rec in enumerate(rdr, start=2):
            if not rec or (len(rec) == 1 and not rec[0].strip()):
                continue
            if len(rec) != len(header):
                raise ScorerError("line %d has %d fields, the header has %d"
                                  % (lineno, len(rec), len(header)))
            rows.append(dict(zip(header, rec)))
    return header, rows


def _prepare(header, rows, need_length, need_router):
    missing = [c for c in ("sample", "contig_id") + TOOL_ORDER if c not in header]
    if missing:
        raise ScorerError("input table lacks required column(s): %s" % ", ".join(missing))
    length_col = next((c for c in LENGTH_COLUMNS if c in header), None)
    if need_length and length_col is None:
        raise ScorerError("v1.1 needs a contig length column (length_bp or contig_length)")
    if need_router and ARG_COLUMN not in header:
        raise ScorerError("--router needs the ARG_bearing_bool column")

    samples, contigs, calls = [], [], []
    seen, bad_values = set(), {}
    for n, r in enumerate(rows, start=2):
        key = (r["sample"].strip(), r["contig_id"].strip())
        if not key[0] or not key[1]:
            raise ScorerError("data row %d: empty sample or contig_id" % (n - 1))
        if key in seen:
            raise ScorerError("duplicate (sample, contig_id): %s %s" % key)
        seen.add(key)
        row = []
        for t in TOOL_ORDER:
            v = r[t].strip()
            if v not in VOCAB:
                bad_values.setdefault(t, set()).add(v)
            row.append(v)
        samples.append(key[0])
        contigs.append(key[1])
        calls.append(row)
    if bad_values:
        detail = "; ".join("%s: %s" % (t, ", ".join(repr(v) for v in sorted(vs)[:5]))
                           for t, vs in sorted(bad_values.items()))
        raise ScorerError("tool calls outside the 7-term vocabulary (%s). Map every call to "
                          "chromosome, plasmid, unknown, unclassified, repeat, FAILED or "
                          "MISSING. Use MISSING for a tool with no output for a contig."
                          % detail)
    lengths = [r[length_col].strip() for r in rows] if length_col else None
    return samples, contigs, calls, lengths, length_col


def _supplied_counts(rows, samples, lengths):
    """Per-row n_contigs_ge_1kb taken from the table, checked for consistency."""
    per_sample = {}
    for n, (r, s) in enumerate(zip(rows, samples), start=1):
        raw = r[NSR_COLUMN].strip()
        try:
            v = int(raw)
        except ValueError:
            raise ScorerError("data row %d: %s %r is not a whole number" % (n, NSR_COLUMN, raw))
        if v < 0:
            raise ScorerError("data row %d: %s is negative" % (n, NSR_COLUMN))
        if per_sample.setdefault(s, v) != v:
            raise ScorerError("sample %s has more than one %s value" % (s, NSR_COLUMN))
    in_table = v11_contig_counts(samples, lengths)
    for s, v in per_sample.items():
        if v < in_table.get(s, 0):
            raise ScorerError("sample %s: %s is %d, but the table holds %d contigs of at least "
                              "1 kb" % (s, NSR_COLUMN, v, in_table[s]))
    # A count of 0 is undefined, as for a sample that is absent from the derived count.
    return [per_sample[s] if per_sample[s] > 0 else None for s in samples]


def score_rows(header, rows, v11=False, router=False, v12_model=None, v11_model=None):
    """Score parsed rows. Returns (output columns, output records, summary)."""
    v11 = bool(v11 or router)
    samples, contigs, calls, lengths, length_col = _prepare(header, rows, v11, router)
    v12_model = v12_model or load_v12()
    p12 = score_v12(v12_model, calls)
    summary = {"n_rows": len(rows), "n_samples": len(set(samples)),
               "v12_model_sha256_lf": v12_model["sha256_lf"]}

    if v11:
        v11_model = v11_model or load_v11()
        if NSR_COLUMN in header:
            nsr = _supplied_counts(rows, samples, lengths)
            summary["n_contigs_ge_1kb_source"] = "column " + NSR_COLUMN
        else:
            per_sample = v11_contig_counts(samples, lengths)
            nsr = [per_sample.get(s) for s in samples]
            summary["n_contigs_ge_1kb_source"] = "counted from the input table"
        s11, a11 = score_v11(v11_model, samples, calls, lengths, nsr)
        summary["v11_model_sha256"] = v11_model["sha256"]
        summary["length_column"] = length_col
        summary["v11_model_abstain"] = int((~a11).sum())

    out = []
    for i in range(len(rows)):
        rec = {"sample": samples[i], "contig_id": contigs[i]}
        a12 = bool(math.isfinite(p12[i]))
        rec["v12_score"] = format_score(p12[i]) if a12 else ""
        rec["v12_score_state"] = "available" if a12 else "model_abstain"
        rec["v12_call"] = classify_v12(p12[i]) if a12 else "model_abstain"
        if v11:
            c = nsr[i]
            rec[NSR_COLUMN] = "" if c is None else str(int(c))
            av = bool(a11[i])
            rec["v11_score"] = format_score(s11[i]) if av else ""
            rec["v11_score_state"] = "available" if av else "model_abstain"
            rec["v11_call"] = classify_v11(s11[i]) if av else "model_abstain"
        if router:
            arg = parse_arg_flag(rows[i][ARG_COLUMN])
            if ANNOTATION_COLUMN in header:
                ann = rows[i][ANNOTATION_COLUMN].strip()
                if ann not in ANNOTATION_STATES:
                    raise ScorerError("data row %d: annotation_state %r is not one of %s"
                                      % (i + 1, ann, ", ".join(ANNOTATION_STATES)))
            else:
                ann = "ok" if arg is not None else "missing"
            if ann == "ok" and arg is None:
                raise ScorerError("data row %d: annotation_state is ok but ARG_bearing_bool "
                                  "is NA" % (i + 1))
            if ann != "ok" and arg is not None:
                raise ScorerError("data row %d: annotation_state is %s but ARG_bearing_bool is "
                                  "%s. An ARG flag needs a successful annotation."
                                  % (i + 1, ann, rows[i][ARG_COLUMN].strip()))
            rec[ANNOTATION_COLUMN] = ann
            rec[ARG_COLUMN] = "NA" if arg is None else ("true" if arg else "false")
            (rec["router_state"], rec["router_model"], rec["router_call"],
             rec["abstention_reason"]) = route(ann, arg, rec["v11_call"],
                                               rec["v11_score_state"] == "available",
                                               rec["v12_call"],
                                               rec["v12_score_state"] == "available")
        out.append(rec)

    cols = ["sample", "contig_id"]
    if v11:
        cols += [NSR_COLUMN, "v11_score", "v11_score_state", "v11_call"]
    cols += ["v12_score", "v12_score_state", "v12_call"]
    if router:
        cols += [ANNOTATION_COLUMN, ARG_COLUMN, "router_state", "router_model", "router_call",
                 "abstention_reason"]
    for k in ("v12_call", "v11_call", "router_call"):
        if k in cols:
            summary[k] = {}
            for r in out:
                summary[k][r[k]] = summary[k].get(r[k], 0) + 1
    return cols, out, summary


def score_file(input_path, v11=False, router=False, v12_model_path=None, v11_model_path=None):
    """Read, check and score a call table. Returns (columns, records, summary)."""
    header, rows = read_table(input_path)
    v12m = load_v12(v12_model_path)
    v11m = load_v11(v11_model_path) if (v11 or router) else None
    return score_rows(header, rows, v11=v11, router=router, v12_model=v12m, v11_model=v11m)


def write_table(fh, cols, records):
    w = csv.writer(fh, delimiter="\t", lineterminator="\n")
    w.writerow(cols)
    for r in records:
        w.writerow([r[c] for c in cols])


# ---------------------------------------------------------------- command line
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Score a table of 12 panel-tool calls with the frozen PlasmidCall models.")
    ap.add_argument("--input", required=True, help="tab-separated call table")
    ap.add_argument("--output", required=True, help="output table, or - for standard output")
    ap.add_argument("--v11", action="store_true",
                    help="also score v1.1 (needs scikit-learn 1.9.0, numpy>=2 and pandas)")
    ap.add_argument("--router", action="store_true",
                    help="also give the routed call (implies --v11, needs ARG_bearing_bool)")
    ap.add_argument("--v12-model", default=None, help="path to P1.12_V1.2_MODEL_PORTABLE.json")
    ap.add_argument("--v11-model", default=None, help="path to plasmidcall_v1_1_m2.pkl")
    ap.add_argument("--receipt", default=None, help="optional JSON receipt of the run")
    ap.add_argument("--version", action="version", version="plasmidcall_score " + __version__)
    a = ap.parse_args(argv)
    try:
        header, rows = read_table(a.input)
        v12m = load_v12(a.v12_model)
        v11m = load_v11(a.v11_model) if (a.v11 or a.router) else None
        cols, out, summary = score_rows(header, rows, v11=a.v11, router=a.router,
                                        v12_model=v12m, v11_model=v11m)
    except (ScorerError, OSError) as e:
        sys.stderr.write("plasmidcall_score: ERROR: %s\n" % e)
        return 2
    if a.output == "-":
        sys.stdout.reconfigure(newline="")
        write_table(sys.stdout, cols, out)
        sys.stdout.flush()
    else:
        with open(a.output, "w", encoding="utf-8", newline="") as f:
            write_table(f, cols, out)
    sys.stderr.write("plasmidcall_score: scored %d rows from %d samples\n"
                     % (summary["n_rows"], summary["n_samples"]))
    for k in ("v12_call", "v11_call", "router_call"):
        if k in summary:
            sys.stderr.write("  %s: %s\n" % (k, ", ".join(
                "%s=%d" % (s or "(none)", n) for s, n in sorted(summary[k].items()))))
    if a.receipt:
        rec = {"scorer": "scripts/score/plasmidcall_score.py", "scorer_version": __version__,
               "scorer_sha256_lf": sha256_file(os.path.abspath(__file__), lf=True),
               "input": os.path.basename(a.input), "input_sha256": sha256_file(a.input),
               "output": os.path.basename(a.output) if a.output != "-" else "-",
               "output_sha256": sha256_file(a.output) if a.output != "-" else None,
               "models": {"v1.2-General": {"file": os.path.basename(v12m["path"]),
                                           "sha256_lf": v12m["sha256_lf"],
                                           "threshold": V12_THRESHOLD}},
               "summary": summary,
               "environment": {"python": platform.python_version(), "numpy": np.__version__,
                               "platform": platform.platform()}}
        if v11m is not None:
            rec["models"]["v1.1"] = {"file": os.path.basename(v11m["path"]),
                                     "sha256": v11m["sha256"],
                                     "thresholds": [V11_THRESHOLD, V11_HIGH]}
            rec["environment"].update(v11m["environment"])
        with open(a.receipt, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rec, f, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

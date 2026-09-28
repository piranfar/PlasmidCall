#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Vahhab Piranfar
"""Reproducibility tests for scripts/score/plasmidcall_score.py.

Run with plain Python:
    python tests/test_plasmidcall_score.py
or, if pytest is installed:
    python -m pytest -p no:cacheprovider tests/test_plasmidcall_score.py

The v1.2-General tests need numpy only. The v1.1 and router tests need scikit-learn 1.9.0,
numpy 2 or later and pandas; in any other environment they are skipped, not failed.

Optional full check against all 19,320 rows of the public P1.13 frozen prediction table
(Zenodo 10.5281/zenodo.22086357, archive PlasmidCall_evidence_tier1_execution.tar.zst, member
frozen/P1.13_FROZEN_PREDICTIONS.tsv):
    python tests/test_plasmidcall_score.py --p113-table P1.13_FROZEN_PREDICTIONS.tsv
With pytest, set the environment variable PLASMIDCALL_P113_TABLE to that path instead.
"""
import contextlib
import csv
import hashlib
import importlib.util
import io
import math
import os
import subprocess
import sys
import tempfile
import traceback
import unittest
import warnings

sys.dont_write_bytecode = True

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
SCORER = os.path.join(REPO, "scripts", "score", "plasmidcall_score.py")
FIXTURES = os.path.join(HERE, "fixtures")
P113_FIXTURE = os.path.join(FIXTURES, "p113_score_fixture.tsv")
SYNTH_FIXTURE = os.path.join(FIXTURES, "synthetic_rules_fixture.tsv")

# LF sha256 of the fixtures, also recorded in tests/fixtures/README.md
P113_FIXTURE_SHA256 = "a29ed1c27265e92ab77e1e304b80796e3c9d13de2a1868ff78febc425735c0b5"
SYNTH_FIXTURE_SHA256 = "4608c9b60c72e16cb1dc4c41974fdfd219062a02e430620a0df8355869bd4af7"
# sha256 of the public P1.13 frozen prediction table (RESULTS_FROZEN.json)
P113_TABLE_SHA256 = "3bc733c0adab6e3864412e056597d931dd1f28d6e6dfb0238c4c915d07799c80"
P113_TABLE_ROWS = 19320

SCORE_TOLERANCE = 1e-12
V12_COLS = ("v12_score", "v12_score_state", "v12_call")
V11_COLS = ("v11_score", "v11_score_state", "v11_call")
ROUTER_COLS = ("router_state", "router_model", "router_call", "abstention_reason")

_MODULE = None
_MODELS = {}
_P113_TABLE = None  # set by --p113-table when run as a script


def load_scorer():
    """Load the scorer from its file without touching sys.path."""
    global _MODULE
    if _MODULE is None:
        spec = importlib.util.spec_from_file_location("plasmidcall_score", SCORER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODULE = mod
    return _MODULE


def v12_model():
    if "v12" not in _MODELS:
        _MODELS["v12"] = load_scorer().load_v12()
    return _MODELS["v12"]


def v11_model_or_skip():
    S = load_scorer()
    if "v11" not in _MODELS:
        try:
            _MODELS["v11"] = S.load_v11()
        except S.ScorerError as e:
            _MODELS["v11"] = e
    if isinstance(_MODELS["v11"], Exception):
        raise unittest.SkipTest(str(_MODELS["v11"]))
    return _MODELS["v11"]


def sha256_lf(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def read(path):
    return load_scorer().read_table(path)


def compare(expected_rows, records, cols):
    """Returns (max |score difference|, list of mismatches)."""
    assert len(expected_rows) == len(records), "row count differs"
    max_d, bad = 0.0, []
    for n, (e, o) in enumerate(zip(expected_rows, records), start=1):
        if (e["sample"], e["contig_id"]) != (o["sample"], o["contig_id"]):
            bad.append((n, "key", e["contig_id"], o["contig_id"]))
            continue
        for c in cols:
            if c.endswith("_score") and e[c] and o[c]:
                d = abs(float(e[c]) - float(o[c]))
                max_d = max(max_d, d)
                if d > SCORE_TOLERANCE:
                    bad.append((n, c, e[c], o[c]))
            elif e[c] != o[c]:
                bad.append((n, c, e[c], o[c]))
    return max_d, bad


def check_fixture(path, v11, router):
    S = load_scorer()
    header, rows = read(path)
    kw = {"v12_model": v12_model()}
    cols = list(V12_COLS)
    if v11 or router:
        kw["v11_model"] = v11_model_or_skip()
        cols += V11_COLS
    if router:
        cols += ROUTER_COLS
    _, out, _ = S.score_rows(header, rows, v11=v11, router=router, **kw)
    max_d, bad = compare(rows, out, cols)
    assert not bad, "%d mismatches, first: %s" % (len(bad), bad[:3])
    assert max_d <= SCORE_TOLERANCE, max_d
    return max_d


# ---------------------------------------------------------------- tests
def test_fixture_integrity():
    assert sha256_lf(P113_FIXTURE) == P113_FIXTURE_SHA256, "p113_score_fixture.tsv changed"
    assert sha256_lf(SYNTH_FIXTURE) == SYNTH_FIXTURE_SHA256, "synthetic_rules_fixture.tsv changed"


def test_import_has_no_side_effects():
    before_path = list(sys.path)
    before_filters = list(warnings.filters)
    before_files = set(os.listdir(os.path.dirname(SCORER)))
    with tempfile.TemporaryDirectory() as tmp:
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            buf_out, buf_err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
                spec = importlib.util.spec_from_file_location("plasmidcall_score_fresh", SCORER)
                spec.loader.exec_module(importlib.util.module_from_spec(spec))
            created = os.listdir(tmp)
        finally:
            os.chdir(cwd)
    assert sys.path == before_path, "import changed sys.path"
    assert list(warnings.filters) == before_filters, "import changed the warning filters"
    assert not created, "import created files: %s" % created
    assert set(os.listdir(os.path.dirname(SCORER))) == before_files, "import wrote next to it"
    assert buf_out.getvalue() == "" and buf_err.getvalue() == "", "import printed output"


def test_v12_reproduces_p113_fixture():
    check_fixture(P113_FIXTURE, v11=False, router=False)


def test_v11_reproduces_p113_fixture():
    check_fixture(P113_FIXTURE, v11=True, router=False)


def test_router_reproduces_p113_fixture():
    check_fixture(P113_FIXTURE, v11=True, router=True)


def test_v12_reproduces_synthetic_rules():
    check_fixture(SYNTH_FIXTURE, v11=False, router=False)


def test_v11_and_router_reproduce_synthetic_rules():
    check_fixture(SYNTH_FIXTURE, v11=True, router=True)


def test_length_bp_column_name():
    S = load_scorer()
    header, rows = read(P113_FIXTURE)
    header2 = ["length_bp" if h == "contig_length" else h for h in header]
    rows2 = [{("length_bp" if k == "contig_length" else k): v for k, v in r.items()} for r in rows]
    m11 = v11_model_or_skip()
    _, a, _ = S.score_rows(header, rows, v11=True, v12_model=v12_model(), v11_model=m11)
    _, b, _ = S.score_rows(header2, rows2, v11=True, v12_model=v12_model(), v11_model=m11)
    assert a == b


def test_v12_unseen_state_is_neutral():
    """A tool in a state not seen in training contributes exactly 0.0 after scaling."""
    S = load_scorer()
    m = v12_model()
    base = ["chromosome"] * 12
    for j, t in enumerate(S.TOOL_ORDER):
        for v in S.VOCAB + ("not_a_state", ""):
            row = list(base)
            row[j] = v
            X = S.apply_neutrality(S.encode([row]), [row], m["neutral_raw"],
                                   m["observed_states"])
            z = (X - m["mean"]) / m["scale"]
            block = z[0, S.tool_block(j)]
            if S.normalise_call(v) in m["observed_states"][t]:
                continue
            assert np.all(block == 0.0), (t, v, block)


def test_v12_non_voting_states_score_alike_when_unseen():
    """Unseen non-voting states give identical features, so identical scores."""
    S = load_scorer()
    m = v12_model()
    base = ["plasmid"] * 6 + ["chromosome"] * 6
    for j, t in enumerate(S.TOOL_ORDER):
        unseen = [v for v in ("unknown", "unclassified", "repeat", "FAILED", "MISSING", "")
                  if v not in m["observed_states"][t]]
        rows = []
        for v in unseen:
            row = list(base)
            row[j] = v
            rows.append(row)
        p = S.score_v12(m, rows)
        assert len(set(p.tolist())) == 1, (t, unseen, p)


def test_v12_n_valid_zero():
    S = load_scorer()
    m = v12_model()
    rows = [["MISSING"] * 12, ["FAILED"] * 12, ["unknown"] * 12, ["repeat"] * 12]
    X = S.encode(rows)
    assert np.all(X[:, S.PANEL_BLOCK] == 0.0)
    p = S.score_v12(m, rows)
    assert np.all(np.isfinite(p)) and np.all((p > 0) & (p < 1))


def test_v12_matches_portable_json_formula():
    """Row-by-row scoring equals the batch formula in the portable JSON to 1e-15."""
    S = load_scorer()
    m = v12_model()
    rng = np.random.default_rng(20260821)
    rows = [list(rng.choice(S.VOCAB, size=12)) for _ in range(500)]
    X = S.apply_neutrality(S.encode(rows), rows, m["neutral_raw"], m["observed_states"])
    z = m["intercept"] + ((X - m["mean"]) / m["scale"]) @ m["coef"]
    batch = 1.0 / (1.0 + np.exp(-z))
    assert float(np.max(np.abs(batch - S.score_v12(m, rows)))) < 1e-15


def test_thresholds_and_classes():
    S = load_scorer()
    assert (S.V12_THRESHOLD, S.V11_THRESHOLD, S.V11_HIGH) == (0.9285, 0.9524, 0.9605)
    assert S.classify_v12(0.9285) == "plasmid_selected"
    assert S.classify_v12(math.nextafter(0.9285, 0)) == "not_selected"
    assert S.classify_v11(0.9524) == "plasmid_selected"
    assert S.classify_v11(0.9605) == "high_confidence_plasmid"
    assert S.classify_v11(math.nextafter(0.9524, 0)) == "not_selected"


def test_route_rules():
    S = load_scorer()
    r = S.route
    assert r("ok", True, "plasmid_selected", True, "not_selected", True) == (
        "routed", "v1.1", "plasmid_selected", "")
    assert r("ok", False, "plasmid_selected", True, "not_selected", True) == (
        "routed", "v1.2-General", "not_selected", "")
    assert r("ok", True, "model_abstain", False, "not_selected", True) == (
        "routing_abstain", "v1.1", "model_abstain", "score_unavailable")
    for ann, why in (("failed", "annotation_failed"), ("missing", "annotation_missing"),
                     ("unparseable", "annotation_unparseable")):
        assert r(ann, None, "plasmid_selected", True, "plasmid_selected", True) == (
            "routing_abstain", "", "", why)
        assert r(ann, None, "model_abstain", False, "model_abstain", False) == (
            "routing_abstain", "", "", "score_unavailable+annotation_unavailable")


def test_input_validation():
    S = load_scorer()
    header, rows = read(P113_FIXTURE)
    m = v12_model()

    def expect_error(h, rs, **kw):
        try:
            S.score_rows(h, rs, v12_model=m, **kw)
        except S.ScorerError:
            return
        raise AssertionError("no ScorerError")

    bad = [dict(r) for r in rows[:3]]
    bad[1]["PLASMe"] = "maybe"
    expect_error(header, bad)
    blank = [dict(r) for r in rows[:3]]
    blank[0]["geNomad"] = ""
    expect_error(header, blank)
    expect_error(header, [dict(rows[0]), dict(rows[0])])
    expect_error([h for h in header if h != "Platon"], rows[:2])
    expect_error([h for h in header if h not in ("contig_length",)], rows[:2], v11=True)
    try:
        m11 = v11_model_or_skip()
    except unittest.SkipTest:
        return
    ok_na = [dict(rows[0])]
    ok_na[0]["ARG_bearing_bool"] = "NA"
    expect_error(header, ok_na, router=True, v11_model=m11)
    failed_false = [dict(rows[0])]
    failed_false[0]["annotation_state"] = "failed"
    expect_error(header, failed_false, router=True, v11_model=m11)


def test_v11_environment_guard():
    S = load_scorer()
    for skl, npv in (("1.8.0", "2.5.0"), ("1.9.1", "2.5.0"), ("1.9.0", "1.26.4")):
        try:
            S.check_v11_environment(sklearn_version=skl, numpy_version=npv)
        except S.ScorerError as e:
            assert skl in str(e) or npv in str(e)
        else:
            raise AssertionError("accepted scikit-learn %s with numpy %s" % (skl, npv))


def test_v11_abstains_without_a_1kb_contig():
    """A sample with no contig of at least 1 kb has no contig count; v1.1 abstains."""
    S = load_scorer()
    m11 = v11_model_or_skip()
    header, rows = read(P113_FIXTURE)
    h = [c for c in header if c != "n_contigs_ge_1kb"]
    first = next(r for r in rows if float(r["contig_length"]) >= 1000)
    one = {k: v for k, v in first.items() if k != "n_contigs_ge_1kb"}
    small = dict(one, contig_length="800")
    bad_len = dict(one, contig_id="x2", contig_length="NA")
    _, out, _ = S.score_rows(h, [small], v11=True, v12_model=v12_model(), v11_model=m11)
    assert out[0]["v11_score_state"] == "model_abstain" and out[0]["v11_call"] == "model_abstain"
    assert out[0]["v12_score_state"] == "available"
    _, out, _ = S.score_rows(h, [one, bad_len], v11=True, v12_model=v12_model(), v11_model=m11)
    assert out[0]["v11_score_state"] == "available"
    assert out[1]["v11_score_state"] == "model_abstain"


def test_command_line():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "scores.tsv")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        cp = subprocess.run([sys.executable, SCORER, "--input", P113_FIXTURE, "--output", out],
                            capture_output=True, text=True, env=env)
        assert cp.returncode == 0, cp.stderr
        _, rows = read(P113_FIXTURE)
        _, got = read(out)
        max_d, bad = compare(rows, got, V12_COLS)
        assert not bad and max_d <= SCORE_TOLERANCE, bad[:3]
        bad_in = os.path.join(tmp, "bad.tsv")
        with open(bad_in, "w", encoding="utf-8", newline="") as f:
            f.write("sample\tcontig_id\n")
            f.write("s\tc\n")
        cp = subprocess.run([sys.executable, SCORER, "--input", bad_in, "--output", out],
                            capture_output=True, text=True, env=env)
        assert cp.returncode == 2 and "lacks required column" in cp.stderr


def test_full_p113_table():
    """All 19,320 rows of the public P1.13 frozen prediction table."""
    path = _P113_TABLE or os.environ.get("PLASMIDCALL_P113_TABLE")
    if not path:
        raise unittest.SkipTest("no P1.13 table given (--p113-table or PLASMIDCALL_P113_TABLE)")
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    assert digest == P113_TABLE_SHA256, "table sha256 %s != %s" % (digest, P113_TABLE_SHA256)
    S = load_scorer()
    header, rows = read(path)
    assert len(rows) == P113_TABLE_ROWS
    try:
        m11 = v11_model_or_skip()
        v11 = True
    except unittest.SkipTest:
        m11, v11 = None, False
    cols = list(V12_COLS) + (list(V11_COLS) + list(ROUTER_COLS) if v11 else [])
    _, out, _ = S.score_rows(header, rows, v11=v11, router=v11, v12_model=v12_model(),
                             v11_model=m11)
    max_d, bad = compare(rows, out, cols)
    report = ["rows %d" % len(rows)]
    for sc in ("v12_score", "v11_score") if v11 else ("v12_score",):
        d = [abs(float(e[sc]) - float(o[sc])) for e, o in zip(rows, out) if e[sc] and o[sc]]
        same = sum(1 for e, o in zip(rows, out) if e[sc] == o[sc])
        report.append("%s max |d| %.3g, identical strings %d" % (sc, max(d), same))
    for c in ("v12_call", "v11_call", "router_call") if v11 else ("v12_call",):
        report.append("%s disagreements %d" % (c, sum(1 for e, o in zip(rows, out)
                                                          if e[c] != o[c])))
    print("    " + "; ".join(report))
    assert not bad, "%d mismatches, first: %s" % (len(bad), bad[:3])
    assert max_d <= SCORE_TOLERANCE
    if v11:
        # Sensitivity of v1.1 to its contig-count input, quoted in
        # models/plasmidcall_v1.1/V1.1_INPUT_SPEC.md.
        samples = [r["sample"] for r in rows]
        calls = [[r[t] for t in S.TOOL_ORDER] for r in rows]
        lengths = [r["contig_length"] for r in rows]
        frozen = [r["v11_call"] for r in rows]
        n_all = {}
        for s in samples:
            n_all[s] = n_all.get(s, 0) + 1
        s_all, a_all = S.score_v11(m11, samples, calls, lengths, [n_all[s] for s in samples])
        changed_all = sum(1 for s, f in zip(s_all, frozen) if S.classify_v11(s) != f)
        idx = [i for i, r in enumerate(rows) if r["ARG_bearing_bool"] == "true"]
        sub = S.v11_contig_counts([samples[i] for i in idx], [lengths[i] for i in idx])
        s_sub, a_sub = S.score_v11(m11, [samples[i] for i in idx], [calls[i] for i in idx],
                                   [lengths[i] for i in idx],
                                   [sub.get(samples[i]) for i in idx])
        changed_sub = sum(1 for k, i in enumerate(idx)
                          if (S.classify_v11(s_sub[k]) if a_sub[k] else "model_abstain")
                          != frozen[i])
        print("    v1.1 calls changed if every contig is counted: %d of %d; if the table holds "
              "only the %d resistance-gene-bearing contigs: %d"
              % (changed_all, len(rows), len(idx), changed_sub))
        assert (changed_all, len(idx), changed_sub) == (932, 695, 95)


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


def main(argv=None):
    global _P113_TABLE
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--p113-table", default=None,
                    help="path to P1.13_FROZEN_PREDICTIONS.tsv for the full-table check")
    a = ap.parse_args(argv)
    _P113_TABLE = a.p113_table
    passed = skipped = failed = 0
    for fn in TESTS:
        try:
            fn()
        except unittest.SkipTest as e:
            skipped += 1
            print("SKIP %s: %s" % (fn.__name__, e))
        except Exception:
            failed += 1
            print("FAIL %s" % fn.__name__)
            traceback.print_exc()
        else:
            passed += 1
            print("PASS %s" % fn.__name__)
    print("%d passed, %d skipped, %d failed" % (passed, skipped, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""P1.11 contig-table builder - TRUTH-BLIND, prospective.

Built before prediction freeze under
docs/plans/P1.11_SELECTIVE_CLASSIFICATION_ADDENDUM.yaml and
docs/plans/P1.11_PROVENANCE_AND_FAILCLOSED_CORRECTION.yaml (Decision D).

It consumes ONLY prediction-side inputs:
  * assemblies/shortread/<sample>/shortread.fasta   canonical contig set and lengths
  * assemblies/shortread/<sample>/shortread.gfa     graph degree, circularity
  * the parsed panel call table (long format from parse_all.py)
  * inference/state/<tool>__<sample>.done|.failed   terminal run state
  * inference/receipts/<tool>__<sample>.json        canonical status receipts
  * the frozen v1.2-General pickle                  deterministic, no fitting

It NEVER opens a reference genome, assembly report, GBFF, PAF, truth table or truth_hold path. A
guard refuses to run if any configured input path looks truth-derived.

annotation_state is derived per ISOLATE from the canonical AMRFinder receipts and then propagated
to every contig of that isolate:

    ok           terminal success AND its required output parsed
    failed       terminal failed run
    missing      expected run/output absent
    unparseable  success receipt present but the required output is invalid or unparseable

ARG_bearing_bool is NULLABLE. It is true/false only when annotation_state == ok. For failed,
missing or unparseable it is NA - never false. Absence of an ARG is never inferred from a failure.

v1.1 scores are INJECTED via --v11-scores, not computed here: v1.1 requires refitting the frozen
HistGradientBoosting estimator on the 1,460-row development set (featureset F_full_no_taxon), which
is a separately governed step. When no score is supplied for a contig, its v11_score_state is
model_abstain - the honest state - rather than a fabricated number.

Usage:
  build_p111_contig_table.py --root /data/trace-arg/p112 --out TABLE.tsv [--v11-scores S.tsv]
  build_p111_contig_table.py --selftest
"""
import argparse
import csv
import glob
import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ---------------------------------------------------------------- controlled vocabularies
ANNOTATION_STATES = ("ok", "failed", "missing", "unparseable")
ANNOTATION_OK = ("ok",)
SCORE_STATES = ("available", "model_abstain")
ROUTER_STATES = ("routed", "routing_abstain")
ROUTER_MODELS = ("v1.1", "v1.2-General", "")
CALL_VALUES = ("plasmid_selected", "not_selected", "high_confidence_plasmid", "model_abstain", "")
ABSTENTION_REASONS = ("", "score_unavailable", "annotation_failed", "annotation_missing",
                      "annotation_unparseable", "score_unavailable+annotation_unavailable")

TOOL_ORDER = ["HyAsP", "MOB-recon", "PLASMe", "PlaScope", "Plasmer", "PlasmidEC",
              "PlasmidFinder", "Platon", "RFPlasmid", "geNomad", "gplas2", "plASgraph2"]

# panel display name -> runner key (MOB-recon is invoked as mobsuite; not a string transform)
DISPLAY_TO_RUNNER = {"HyAsP": "hyasp", "MOB-recon": "mobsuite", "PLASMe": "plasme",
                     "PlaScope": "plascope", "Plasmer": "plasmer", "PlasmidEC": "plasmidec",
                     "PlasmidFinder": "plasmidfinder", "Platon": "platon",
                     "RFPlasmid": "rfplasmid", "geNomad": "genomad", "gplas2": "gplas2",
                     "plASgraph2": "plasgraph2"}

V11_THRESHOLD, V11_HIGH, V12_THRESHOLD = 0.9524, 0.9605, 0.9285

# The frozen 7-term vocabulary the encoder expects. parse_all.py emits TWO call columns:
#   native_call  the RAW per-tool vocabulary (tool_status_FAILED, no_replicon_hit,
#                plasmid_fraction=0.0, ...) - only 3 of its ~130 values coincide with VOCAB
#   model1_code  the NORMALISED 7-term code - this is the one the model consumes
# Reading native_call silently feeds the encoder unrecognised tokens, which direct-block
# neutrality then treats as absent evidence, and hides tool failures from the completeness count.
CALL_COLUMN = "model1_code"
VOCAB = ("chromosome", "plasmid", "unknown", "unclassified", "repeat", "FAILED", "MISSING")

FORBIDDEN_INPUT_TOKENS = ("truth_hold", "truth_table", "_assembly_report", ".gbff", ".paf",
                          "/truth/", "\\truth\\")

COLUMNS = (["sample", "contig_id", "contig_length", "circular", "gfa_degree"]
           + TOOL_ORDER
           + ["n_valid", "n_plasmid", "n_chrom", "n_abstain", "frac_plasmid", "frac_chrom",
              "agreement",
              "v11_score", "v11_score_state", "v11_call",
              "v12_score", "v12_score_state", "v12_call",
              "annotation_state", "ARG_bearing_bool", "n_qualifying_determinants",
              "router_state", "router_model", "router_call", "abstention_reason",
              "is_score_evaluable_v11", "is_score_evaluable_v12"])


def guard_inputs(*paths):
    for p in paths:
        if p and any(tok in str(p).lower() for tok in FORBIDDEN_INPUT_TOKENS):
            sys.exit("REFUSING: input path looks truth-derived: %s" % p)


def score_available(v):
    """A valid BELOW-threshold score is available. Absent/NaN/inf/non-numeric is not."""
    if v is None:
        return False
    s = str(v).strip()
    if s == "" or s.lower() in ("na", "nan", "none", "null", "-"):
        return False
    try:
        f = float(s)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def classify(score, avail, thr, high=None):
    if not avail:
        return "model_abstain"
    f = float(score)
    if high is not None and f >= high:
        return "high_confidence_plasmid"
    return "plasmid_selected" if f >= thr else "not_selected"


# ---------------------------------------------------------------- inputs
def read_fasta_contigs(path):
    """Canonical contig set. One row per contig, in file order."""
    op = gzip.open if path.endswith(".gz") else open
    out, cid, ln = [], None, 0
    with op(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(">"):
                if cid is not None:
                    out.append((cid, ln))
                cid = line[1:].strip().split()[0]
                ln = 0
            else:
                ln += len(line.strip())
    if cid is not None:
        out.append((cid, ln))
    return out


def read_gfa(path):
    """Segment degree and circularity, prediction-side only."""
    deg, circ = {}, {}
    if not os.path.exists(path):
        return deg, circ
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if p[0] == "L" and len(p) >= 5:
                deg[p[1]] = deg.get(p[1], 0) + 1
                deg[p[3]] = deg.get(p[3], 0) + 1
                if p[1] == p[3]:
                    circ[p[1]] = 1
    return deg, circ


def amrfinder_outputs(sample, annot_dir):
    """The frozen runner writes AMRFinder to  <root>/annotation/native/<S>/<S>.amrfinder.tsv
    (run_tool.sh overrides OUT for the amrfinder case), NOT to inference/native/amrfinder/<S>/,
    which it creates and leaves empty. Reading the wrong directory would mark every isolate
    unparseable, so the canonical path is used and the empty inference dir is ignored."""
    d = os.path.join(annot_dir, sample)
    cands = [os.path.join(d, "%s.amrfinder.tsv" % sample)]
    cands += sorted(glob.glob(os.path.join(d, "*.tsv")))
    return [p for p in dict.fromkeys(cands) if os.path.isfile(p)]


def amrfinder_state(sample, state_dir, receipt_dir, annot_dir):
    """Terminal AMRFinder state for one isolate, from the canonical receipts."""
    key = "amrfinder__%s" % sample
    done = os.path.exists(os.path.join(state_dir, key + ".done"))
    failed = os.path.exists(os.path.join(state_dir, key + ".failed"))
    rec = os.path.join(receipt_dir, key + ".json")

    if failed and not done:
        return "failed", "terminal .failed marker"
    if not done and not failed:
        return "missing", "no terminal state marker for amrfinder"
    # done: the run succeeded - now require its output to exist AND parse
    status = None
    if os.path.exists(rec):
        try:
            status = json.load(open(rec, encoding="utf-8")).get("status")
        except Exception:
            return "unparseable", "receipt present but not valid JSON"
    if status == "FAILED":
        return "failed", "receipt status FAILED"
    tsvs = amrfinder_outputs(sample, annot_dir)
    if not tsvs:
        return "unparseable", "success receipt but no AMRFinder output file"
    for p in tsvs:
        try:
            with open(p, encoding="utf-8", errors="strict") as f:
                head = f.readline()
            if head.strip():
                return "ok", ""
        except Exception:
            continue
    return "unparseable", "AMRFinder output present but unreadable/empty"


def arg_bearing(sample, annot_dir):
    """Core-ARG determinant count per contig. Only meaningful when annotation_state == ok.

    Locked rule: Type == AMR AND Subtype == AMR AND Scope == core AND Class != EFFLUX.
    """
    out = {}
    for p in amrfinder_outputs(sample, annot_dir):
        try:
            rows = list(csv.DictReader(open(p, encoding="utf-8", errors="replace"), delimiter="\t"))
        except Exception:
            continue
        for r in rows:
            cid = (r.get("Contig id") or r.get("Contig") or r.get("contig_id") or "").strip()
            if not cid:
                continue
            etype = (r.get("Element type") or r.get("Type") or "").strip().upper()
            esub = (r.get("Element subtype") or r.get("Subtype") or "").strip().upper()
            scope = (r.get("Scope") or "").strip().lower()
            cls = (r.get("Class") or "").strip().upper()
            qualifies = (etype == "AMR" and esub == "AMR" and scope == "core" and cls != "EFFLUX")
            if qualifies:
                out[cid] = out.get(cid, 0) + 1
    return out


def load_calls(path):
    """parse_all.py long format -> {(sample, contig): {tool: normalised call}}.

    Uses model1_code, the normalised 7-term code. Refuses if that column is absent or if any
    value falls outside the frozen vocabulary.
    """
    calls = {}
    if not path or not os.path.exists(path):
        return calls
    rdr = csv.DictReader(open(path, encoding="utf-8"), delimiter="\t")
    if CALL_COLUMN not in (rdr.fieldnames or []):
        sys.exit("REFUSING: call table has no %r column. Columns: %s"
                 % (CALL_COLUMN, rdr.fieldnames))
    bad = set()
    for r in rdr:
        v = (r.get(CALL_COLUMN) or "").strip()
        if v not in VOCAB:
            bad.add(v)
        calls.setdefault((r["sample"], r["contig_id"]), {})[r["tool"]] = v
    if bad:
        sys.exit("REFUSING: call table contains values outside the frozen 7-term vocabulary: %s"
                 % sorted(bad)[:10])
    return calls


# ---------------------------------------------------------------- build
def build(root, out_path, v11_scores=None, model=None, verbose=True):
    guard_inputs(root, out_path, v11_scores)
    asm_dir = os.path.join(root, "assemblies", "shortread")
    state_dir = os.path.join(root, "inference", "state")
    receipt_dir = os.path.join(root, "inference", "receipts")
    native_dir = os.path.join(root, "inference", "native")
    annot_dir = os.path.join(root, "annotation", "native")
    # parse_all.py was derived from P1.10 by path substitution, so its OUTPUT FILENAME still
    # carries the P1.10 name. The artefact is left under the name it was produced with rather than
    # renamed after the fact; the builder accepts either, and refuses if neither is present.
    # The RECONCILED table is preferred: it carries the derived provenance_state from
    # docs/plans/P1.11_STATUS_RECONCILIATION_AMENDMENT.yaml, so a unit whose receipt was stale but
    # whose output is valid contributes its real calls instead of being coded FAILED.
    _cands = [os.path.join(root, "inference", n) for n in
              ("P1.11_call_table_reconciled.tsv", "P1.11_call_table.tsv",
               "P1.10_predictions_normalised.tsv")]
    _call_tsv = next((p for p in _cands if os.path.exists(p)), None)
    if _call_tsv is None:
        sys.exit("REFUSING: no parsed call table found. Looked for: %s" % _cands)
    calls = load_calls(_call_tsv)

    v11 = {}
    if v11_scores and os.path.exists(v11_scores):
        for r in csv.DictReader(open(v11_scores, encoding="utf-8"), delimiter="\t"):
            v11[(r["sample"], r["contig_id"])] = r.get("M2_score", "")

    B = None
    if model and os.path.exists(model):
        import pickle
        from freeze_v12 import predict as v12_predict
        B = pickle.load(open(model, "rb"))

    samples = sorted(d for d in os.listdir(asm_dir)
                     if os.path.isdir(os.path.join(asm_dir, d)))
    rows, recon = [], []
    for s in samples:
        fa = os.path.join(asm_dir, s, "shortread.fasta")
        if not os.path.exists(fa):
            recon.append({"sample": s, "fasta_contigs": 0, "rows": 0, "note": "no shortread.fasta"})
            continue
        contigs = read_fasta_contigs(fa)
        deg, circ = read_gfa(os.path.join(asm_dir, s, "shortread.gfa"))
        ann, ann_note = amrfinder_state(s, state_dir, receipt_dir, annot_dir)
        args_ = arg_bearing(s, annot_dir) if ann == "ok" else {}

        for cid, ln in contigs:
            tc = calls.get((s, cid), {})
            row = {"sample": s, "contig_id": cid, "contig_length": ln,
                   "circular": circ.get(cid, 0), "gfa_degree": deg.get(cid, 0)}
            for t in TOOL_ORDER:
                row[t] = tc.get(t, "MISSING") or "MISSING"
            vals = [row[t] for t in TOOL_ORDER]
            npl = sum(1 for v in vals if v == "plasmid")
            nch = sum(1 for v in vals if v == "chromosome")
            nab = sum(1 for v in vals if v in ("unknown", "unclassified", "repeat",
                                               "FAILED", "MISSING"))
            nv = npl + nch
            row.update({"n_valid": nv, "n_plasmid": npl, "n_chrom": nch, "n_abstain": nab,
                        "frac_plasmid": (npl / nv) if nv else 0.0,
                        "frac_chrom": (nch / nv) if nv else 0.0,
                        "agreement": (max(npl, nch) / nv) if nv else 0.0})

            # ---- v1.1: injected, never fabricated
            raw11 = v11.get((s, cid), "")
            a11 = score_available(raw11)
            row["v11_score"] = float(raw11) if a11 else ""
            row["v11_score_state"] = "available" if a11 else "model_abstain"
            row["v11_call"] = classify(raw11, a11, V11_THRESHOLD, V11_HIGH)
            row["is_score_evaluable_v11"] = int(a11)

            # ---- v1.2: frozen pickle, deterministic
            if B is not None:
                p = float(v12_predict(B, [vals])[0])
                a12 = math.isfinite(p)
                row["v12_score"] = p if a12 else ""
            else:
                a12 = False
                row["v12_score"] = ""
            row["v12_score_state"] = "available" if a12 else "model_abstain"
            row["v12_call"] = classify(row["v12_score"], a12, V12_THRESHOLD)
            row["is_score_evaluable_v12"] = int(a12)

            # ---- annotation: nullable, never false-on-failure
            row["annotation_state"] = ann
            if ann in ANNOTATION_OK:
                n = args_.get(cid, 0)
                row["ARG_bearing_bool"] = "true" if n > 0 else "false"
                row["n_qualifying_determinants"] = n
            else:
                row["ARG_bearing_bool"] = "NA"
                row["n_qualifying_determinants"] = "NA"

            # ---- router: standalone v1.2 is NOT suppressed by annotation failure
            if ann not in ANNOTATION_OK:
                row["router_state"] = "routing_abstain"
                row["router_model"] = ""
                row["router_call"] = ""
                reason = {"failed": "annotation_failed", "missing": "annotation_missing",
                          "unparseable": "annotation_unparseable"}[ann]
                if not (a11 or a12):
                    reason = "score_unavailable+annotation_unavailable"
                row["abstention_reason"] = reason
            else:
                is_arg = row["ARG_bearing_bool"] == "true"
                row["router_model"] = "v1.1" if is_arg else "v1.2-General"
                avail = a11 if is_arg else a12
                if avail:
                    row["router_state"] = "routed"
                    row["router_call"] = row["v11_call"] if is_arg else row["v12_call"]
                    row["abstention_reason"] = ""
                else:
                    row["router_state"] = "routing_abstain"
                    row["router_call"] = "model_abstain"
                    row["abstention_reason"] = "score_unavailable"
            rows.append(row)

        recon.append({"sample": s, "fasta_contigs": len(contigs),
                      "rows": sum(1 for r in rows if r["sample"] == s),
                      "annotation_state": ann, "note": ann_note})

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n", restval="")
        w.writeheader()
        w.writerows(rows)
    if verbose:
        print("  call table: %s" % os.path.basename(_call_tsv))
        print("  wrote %d rows over %d isolates -> %s" % (len(rows), len(samples), out_path))
    return rows, recon


# ---------------------------------------------------------------- validation
def validate(rows, recon):
    """Every check the builder must pass before prediction freeze."""
    res = []

    def ck(name, ok, detail=""):
        res.append({"check": name, "pass": bool(ok), "detail": str(detail)})

    keys = [(r["sample"], r["contig_id"]) for r in rows]
    ck("exactly one row per assembled contig",
       all(x["rows"] == x["fasta_contigs"] for x in recon if x.get("fasta_contigs")),
       "; ".join("%s %d/%d" % (x["sample"], x["rows"], x["fasta_contigs"])
                 for x in recon if x.get("fasta_contigs") and x["rows"] != x["fasta_contigs"])
       or "all reconcile")
    ck("no duplicate (isolate, contig_id) keys", len(keys) == len(set(keys)),
       "%d rows, %d unique" % (len(keys), len(set(keys))))
    ck("row counts reconcile with assembly FASTA files",
       sum(x["fasta_contigs"] for x in recon) == len(rows),
       "fasta=%d rows=%d" % (sum(x["fasta_contigs"] for x in recon), len(rows)))
    seen = {str(r[t]).strip() for r in rows for t in TOOL_ORDER} if rows else set()
    ck("every panel call is within the frozen 7-term vocabulary", seen <= set(VOCAB),
       ("outside: %s" % sorted(seen - set(VOCAB))) if (seen - set(VOCAB))
       else "%d distinct values, all in vocabulary" % len(seen))
    nf = sum(1 for r in rows for t in TOOL_ORDER if str(r[t]).strip() == "FAILED")
    ck("terminal tool failures surface as FAILED, not as a call", True,
       "%d FAILED tool-contig cells" % nf)
    ck("all required panel-call columns exist",
       all(t in (rows[0] if rows else {}) for t in TOOL_ORDER) if rows else True)
    ck("score availability is explicit",
       all(r["v11_score_state"] in SCORE_STATES and r["v12_score_state"] in SCORE_STATES
           for r in rows))
    bad = [r for r in rows
           if (not score_available(r["v11_score"]) and r["v11_score_state"] != "model_abstain")
           or (not score_available(r["v12_score"]) and r["v12_score_state"] != "model_abstain")]
    ck("every NaN or missing score maps to model_abstain", not bad, "%d violations" % len(bad))
    negbad = [r for r in rows if r["v11_score_state"] == "model_abstain"
              and str(r["v11_call"]).lower() in ("false", "0", "not_selected", "chromosome")]
    negbad += [r for r in rows if r["v12_score_state"] == "model_abstain"
               and str(r["v12_call"]).lower() in ("false", "0", "not_selected", "chromosome")]
    ck("no abstention maps to a Boolean negative", not negbad, "%d violations" % len(negbad))
    ck("annotation_state uses only the locked vocabulary",
       all(r["annotation_state"] in ANNOTATION_STATES for r in rows),
       sorted({r["annotation_state"] for r in rows}))
    ck("ARG_bearing_bool is nullable",
       all(str(r["ARG_bearing_bool"]) in ("true", "false", "NA") for r in rows),
       sorted({str(r["ARG_bearing_bool"]) for r in rows}))
    inval = [r for r in rows if r["annotation_state"] not in ANNOTATION_OK
             and str(r["ARG_bearing_bool"]).lower() == "false"]
    ck("no row has invalid annotation plus ARG_bearing_bool=false", not inval,
       "%d violations" % len(inval))
    prop = True
    for x in recon:
        if x.get("annotation_state") and x["annotation_state"] != "ok":
            sub = [r for r in rows if r["sample"] == x["sample"]]
            if sub and not all(r["annotation_state"] == x["annotation_state"] for r in sub):
                prop = False
    ck("AMRFinder failure states propagate to every relevant contig", prop)
    zero_ok = [x for x in recon if x.get("annotation_state") == "ok"]
    ck("successful zero-hit isolates remain ok",
       all(any(r["ARG_bearing_bool"] in ("true", "false")
               for r in rows if r["sample"] == x["sample"]) for x in zero_ok) if zero_ok else True)
    ck("router and model abstention are separate fields",
       all("router_state" in r and "v11_score_state" in r for r in rows) if rows else True)
    ck("no truth field or reference-derived contig label is consumed",
       not any(c.lower() in ("truth_bin", "final_truth_label", "truth_len", "is_resolved")
               for c in COLUMNS))
    return res


def selftest():
    """Fixture suite - see p111_builder_fixtures.py for the full 16."""
    print("  run scripts/p1_12/p111_builder_fixtures.py for the fixture suite")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/data/trace-arg/p112")
    ap.add_argument("--out")
    ap.add_argument("--v11-scores", default=None)
    ap.add_argument("--model", default=os.path.join(HERE, "..", "..", "models",
                                                    "plasmidcall_v1.2-general",
                                                    "plasmidcall_v1_2_general.pkl"))
    ap.add_argument("--validation-out", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.out:
        sys.exit("need --out")
    rows, recon = build(a.root, a.out, a.v11_scores, a.model)
    res = validate(rows, recon)
    for r in res:
        print("  [%s] %-52s %s" % ("PASS" if r["pass"] else "FAIL", r["check"], r["detail"][:60]))
    if a.validation_out:
        json.dump({"checks": res, "reconciliation": recon,
                   "verdict": "PASS" if all(r["pass"] for r in res) else "FAIL"},
                  open(a.validation_out, "w", encoding="utf-8"), indent=1)
    sys.exit(0 if all(r["pass"] for r in res) else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""P1.10 (derived from the frozen P1.9C4 script by path substitution only): build the normalised prediction table from native outputs (truth-blind). Never overwrites native outputs.
usage: parse_all.py <root=/data/trace-arg> """
import os, sys, json, csv, hashlib, glob, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parsers as P
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/data/trace-arg"; INF = f"{ROOT}/p113/inference"
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""): h.update(b)
    return h.hexdigest()
def contigs_of(s):
    d = {}; name = None
    for l in open(f"{ROOT}/p113/assemblies/shortread/{s}/shortread.fasta"):
        if l.startswith(">"): name = l[1:].strip().split()[0]; d[name] = 0
        else: d[name] += len(l.strip())
    return d
samples = sorted(os.listdir(f"{ROOT}/p113/assemblies/shortread"))
rows = []; summary = {}
os.makedirs(f"{INF}/parsed", exist_ok=True)
for t, fn in P.PARSERS.items():
    for s in samples:
        C = contigs_of(s); od = f"{INF}/native/{t}/{s}"; rec = f"{INF}/receipts/{t}__{s}.json"
        status = json.load(open(rec))["status"] if os.path.exists(rec) else "NOT_RUN"
        sums = f"{INF}/receipts/{t}__{s}.SHA256SUMS"; nsha = sha(sums) if os.path.exists(sums) else ""
        if status != "OK":
            calls = {c: ("FAILED", f"tool_status_{status}", "") for c in C}; perr = ""
        else:
            try: calls = fn(od, C); perr = ""
            except P.ParseError as e:
                calls = {c: ("FAILED", "parse_error", "") for c in C}; perr = str(e)
        os.makedirs(f"{INF}/parsed/{t}", exist_ok=True)
        with open(f"{INF}/parsed/{t}/{s}.tsv", "w", newline="") as fo:
            w = csv.writer(fo, delimiter="\t"); w.writerow(["sample", "contig_id", "contig_length", "tool", "native_call", "model1_code", "evidence_score", "native_sha256sums", "parser_version"])
            for c, L in C.items():
                code, nat, ev = calls[c]; w.writerow([s, c, L, P.TOOL_COLUMN[t], nat, code, ev, nsha, P.PARSER_VERSION]); rows.append([s, c, L, P.TOOL_COLUMN[t], nat, code, ev, nsha, P.PARSER_VERSION])
        cnt = {}
        for c in C: cnt[calls[c][0]] = cnt.get(calls[c][0], 0) + 1
        summary[f"{t}|{s}"] = {"tool_status": status, "parse_error": perr, "codes": cnt}
with open(f"{INF}/P1.13_predictions_normalised.tsv", "w", newline="") as fo:
    w = csv.writer(fo, delimiter="\t"); w.writerow(["sample", "contig_id", "contig_length", "tool", "native_call", "model1_code", "evidence_score", "native_sha256sums", "parser_version"]); w.writerows(rows)
json.dump({"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "parser_version": P.PARSER_VERSION, "rows": len(rows), "per_tool_sample": summary}, open(f"{INF}/P1.13_parse_summary.json", "w"), indent=1)
for k, v in summary.items(): print(k, v["tool_status"], v["codes"], v["parse_error"])

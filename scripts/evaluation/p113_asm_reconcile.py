#!/usr/bin/env python3
"""P1.13 global assembly reconciliation. Runs BEFORE phase 4 and stops the pipeline on any failure.

Derives exactly ONE effective state per isolate from the live markers, cross-checks every accepted
assembly against its receipt by recomputation, and refuses to pass on any inconsistency.

Truth-blind: reads no truth, label, ARG content, tool output or model score.
"""
import glob, hashlib, io, json, os, sys

P = "/work/p113"
COHORT = P + "/P1.13_SELECTED_COHORT_v3.tsv"
EXPECTED = 150
PILOTS = ["SAMN26796377", "SAMN29503689", "SAMN29503815", "SAMN47788335"]

problems = []
notes = []


def fail(msg):
    problems.append(msg)


def sha256(p):
    d = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def cohort():
    out = []
    with io.open(COHORT, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for line in f:
            out.append(dict(zip(hdr, line.rstrip("\n").split("\t"))))
    return out


def main():
    rows = cohort()
    if len(rows) != EXPECTED:
        fail("cohort holds %d isolates, expected %d" % (len(rows), EXPECTED))
    names = [r["biosample"] for r in rows]

    effective = {}
    for bs in names:
        done = os.path.exists(P + "/state/asm__%s.done" % bs)
        failed = os.path.exists(P + "/state/asm__%s.failed" % bs)
        if done and failed:
            fail("%s holds BOTH .done and .failed; state is ambiguous" % bs)
            effective[bs] = "CONFLICT"
        elif done:
            effective[bs] = "accepted"
        elif failed:
            effective[bs] = "rejected"
        else:
            effective[bs] = "MISSING"
            fail("%s has no terminal state" % bs)

    accepted = [b for b, v in effective.items() if v == "accepted"]

    # every accepted isolate must carry a complete, self-consistent receipt
    for bs in accepted:
        rp = P + "/receipts/asm__%s.json" % bs
        if not os.path.exists(rp):
            fail("%s accepted but has no validation receipt" % bs)
            continue
        try:
            rec = json.load(io.open(rp, encoding="utf-8"))
        except Exception as e:
            fail("%s receipt is unreadable: %s" % (bs, e))
            continue
        for k in ("frozen_run_identity", "raw_md5_receipt", "exact_id_stream_validation",
                  "coverage_floor", "assembler_input_sha256", "assembler", "exit_code",
                  "assembly_metrics", "assembly_sha256", "clean_run_verified"):
            if k not in rec:
                fail("%s receipt is missing required field %r" % (bs, k))
        fa = P + "/assemblies/shortread/%s/shortread.fasta" % bs
        if not os.path.isfile(fa):
            fail("%s accepted but final FASTA is absent" % bs)
            continue
        # output must resolve inside the P1.13 root
        rp_real = os.path.realpath(fa)
        if not rp_real.startswith(os.path.realpath(P) + os.sep):
            fail("%s final FASTA resolves outside the P1.13 root: %s" % (bs, rp_real))
        # hash must match the receipt by recomputation, not by trust
        want = rec.get("assembly_sha256", {}).get("shortread.fasta")
        if not want:
            fail("%s receipt records no FASTA hash" % bs)
        else:
            got = sha256(fa)
            if got != want:
                fail("%s final FASTA hash %s does not match receipt %s" % (bs, got[:16], want[:16]))
        # retry provenance: the accepted attempt must carry the frozen identity
        row = [r for r in rows if r["biosample"] == bs]
        if row and rec["frozen_run_identity"].get("run_accession") != row[0]["run_accession"]:
            fail("%s receipt run accession differs from the frozen cohort" % bs)

    # any final FASTA without an accepted state is an unvalidated publication
    for d in glob.glob(P + "/assemblies/shortread/*"):
        bs = os.path.basename(d)
        fa = os.path.join(d, "shortread.fasta")
        if os.path.isfile(fa) and effective.get(bs) != "accepted":
            fail("%s has a published FASTA but is not in an accepted state" % bs)

    # nothing may remain staged
    staged = [p for p in glob.glob(P + "/assemblies/_staging/*/*") if os.path.isdir(p)]
    if staged:
        fail("%d staging directories remain; publication is incomplete" % len(staged))

    # retry accounting, reported not judged
    retried = []
    for bs in accepted:
        n = len(glob.glob(P + "/logs/asm__%s__attempt*.log" % bs))
        rec_path = P + "/receipts/asm__%s.json" % bs
        att = None
        if os.path.exists(rec_path):
            try:
                att = json.load(io.open(rec_path, encoding="utf-8"))["assembler"]["attempt"]
            except Exception:
                pass
        if n > 1 or (att not in (None, "1", 1)):
            retried.append({"biosample": bs, "attempt_logs": n, "accepted_attempt": att})

    # deterministic rerun comparison against quarantined pre-atomic assemblies
    pilot = []
    for bs in PILOTS:
        q = P + "/provenance/preatomic_assemblies/%s/shortread.fasta" % bs
        f = P + "/assemblies/shortread/%s/shortread.fasta" % bs
        if os.path.isfile(q) and os.path.isfile(f):
            a, b = sha256(q), sha256(f)
            pilot.append({"biosample": bs, "identical": a == b,
                          "preatomic_sha256": a[:16], "reassembled_sha256": b[:16]})
        else:
            pilot.append({"biosample": bs, "identical": None,
                          "note": "comparison unavailable; one side absent"})
    notes.append("pilot comparison is descriptive: SPAdes is not contractually deterministic "
                 "across runs, so a difference is reported, not treated as a defect")

    report = {
        "expected_isolates": EXPECTED,
        "accepted": len(accepted),
        "rejected": sum(1 for v in effective.values() if v == "rejected"),
        "missing": sum(1 for v in effective.values() if v == "MISSING"),
        "conflicts": sum(1 for v in effective.values() if v == "CONFLICT"),
        "retried_isolates": retried,
        "deterministic_rerun_pilot": pilot,
        "notes": notes,
        "problems": problems,
        "effective_state": effective,
        "verdict": "PASS" if (not problems and len(accepted) == EXPECTED) else "STOP",
    }
    io.open(P + "/P1.13_ASSEMBLY_RECONCILIATION.json", "w", encoding="utf-8").write(
        json.dumps(report, indent=1) + "\n")

    print("expected           : %d" % EXPECTED)
    print("accepted           : %d" % len(accepted))
    print("rejected           : %d" % report["rejected"])
    print("missing state      : %d" % report["missing"])
    print("done+failed clash  : %d" % report["conflicts"])
    print("retried isolates   : %d" % len(retried))
    for p in pilot:
        print("pilot %-14s identical=%s" % (p["biosample"], p.get("identical")))
    if problems:
        print("PROBLEMS (%d):" % len(problems))
        for x in problems[:20]:
            print("   - %s" % x)
    print("VERDICT: %s" % report["verdict"])
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

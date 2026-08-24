#!/usr/bin/env python3
"""P1.13 pairing fixtures. Exercises the SAME production functions the runner calls.

Includes a production-path test of the real downsampling command: seqkit sample run separately on
R1 and R2 inside the frozen p19c2-normalize:1.0 image, with the frozen seed. Whether that preserves
pairing is DEMONSTRATED here, not assumed.
"""
import gzip, io, os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p113_pairing import validate_pair, normalize_id, PairError   # production module

SEED = 20260821
NORMIMG = "p19c2-normalize:1.0"
WORK = "/work/p113/fixtures"
results = []


def rec(name, expect, got, detail=""):
    ok = (expect == got)
    results.append({"fixture": name, "expect": expect, "got": got, "pass": ok, "detail": detail})
    print("  [%s] %-46s expect=%-6s got=%-6s %s"
          % ("PASS" if ok else "FAIL", name, expect, got, detail[:70]))
    return ok


def write_fq(path, records):
    op = gzip.open if path.endswith(".gz") else io.open
    with op(path, "wt") as f:
        for h, s, q in records:
            f.write("%s\n%s\n+\n%s\n" % (h, s, q))


def pair(r1, r2, **kw):
    try:
        validate_pair(r1, r2, **kw)
        return "OK"
    except PairError:
        return "FAIL"


def main():
    os.makedirs(WORK, exist_ok=True)
    d = tempfile.mkdtemp(dir=WORK, prefix="fx_")
    S, Q = "ACGTACGTAC", "IIIIIIIIII"
    base = [("@READ%04d" % i, S, Q) for i in range(1, 21)]

    # 1 correctly paired
    a, b = d + "/a1.fq", d + "/b1.fq"
    write_fq(a, base); write_fq(b, base)
    rec("correctly_paired", "OK", pair(a, b))

    # 2 equal counts, one mismatched id
    m = list(base); m[7] = ("@READ9999", S, Q)
    write_fq(b, m); rec("equal_counts_one_mismatched_id", "FAIL", pair(a, b))

    # 3 same ids, different order
    o = list(base); o[3], o[9] = o[9], o[3]
    write_fq(b, o); rec("same_ids_different_order", "FAIL", pair(a, b))

    # 4 missing mate
    write_fq(b, base[:-1]); rec("missing_mate", "FAIL", pair(a, b))

    # 5 duplicate id
    dup = list(base); dup[5] = dup[4]
    write_fq(a, dup); write_fq(b, dup); rec("duplicate_id", "FAIL", pair(a, b))

    # 6 /1 and /2 suffix normalisation
    write_fq(a, [("@READ%04d/1" % i, S, Q) for i in range(1, 21)])
    write_fq(b, [("@READ%04d/2" % i, S, Q) for i in range(1, 21)])
    rec("slash_mate_suffix_normalised", "OK", pair(a, b))

    # 7 Illumina whitespace mate field
    write_fq(a, [("@A001:2:FC:1:1101:%d:1 1:N:0:ATCG" % i, S, Q) for i in range(1, 21)])
    write_fq(b, [("@A001:2:FC:1:1101:%d:1 2:N:0:ATCG" % i, S, Q) for i in range(1, 21)])
    rec("illumina_whitespace_mate_field", "OK", pair(a, b))

    # 8 truncated FASTQ
    write_fq(a, base); write_fq(b, base)
    with io.open(b, "r") as f:
        txt = f.read()
    with io.open(b, "w") as f:
        f.write(txt[:-12])
    rec("truncated_fastq", "FAIL", pair(a, b))

    # 9 declared target count not met
    write_fq(a, base); write_fq(b, base)
    rec("retained_count_below_declared_target", "FAIL", pair(a, b, expect_count=25))
    rec("retained_count_equals_declared_target", "OK", pair(a, b, expect_count=20))

    # 10 independently sampled R1/R2 that retain different records
    write_fq(a, [base[i] for i in (0, 2, 4, 6, 8)])
    write_fq(b, [base[i] for i in (0, 2, 4, 6, 9)])
    rec("independent_sampling_retained_different_records", "FAIL", pair(a, b))

    # 11 malformed header
    write_fq(a, base)
    with io.open(b, "w") as f:
        f.write("READ0001 no at sign\n%s\n+\n%s\n" % (S, Q))
    rec("header_without_at_sign", "FAIL", pair(a, b))

    # ---- PRODUCTION PATH: does seqkit sample preserve pairing across separate invocations?
    print("\n  production-path test: seqkit sample, separate R1/R2 invocations, frozen seed")
    p1, p2 = d + "/prod_R1.fastq.gz", d + "/prod_R2.fastq.gz"
    big = [("@A001:2:FC:1:1101:%05d:1 %s:N:0:ATCG" % (i, "%d"), S, Q) for i in range(1, 2001)]
    write_fq(p1, [(h % 1, s, q) for h, s, q in big])
    write_fq(p2, [(h % 2, s, q) for h, s, q in big])
    rec("production_raw_pair_valid", "OK", pair(p1, p2))

    o1, o2 = d + "/ds_R1.fastq.gz", d + "/ds_R2.fastq.gz"
    cmd = ("seqkit sample -p 0.25 -s %d -o /w/%s /w/%s && "
           "seqkit sample -p 0.25 -s %d -o /w/%s /w/%s"
           % (SEED, os.path.basename(o1), os.path.basename(p1),
              SEED, os.path.basename(o2), os.path.basename(p2)))
    r = subprocess.run(["docker", "run", "--rm", "-v", d + ":/w", "-v", d + ":/tmp",
                        "-e", "TMPDIR=/tmp", "--entrypoint", "bash", NORMIMG, "-lc", cmd],
                       capture_output=True, text=True)
    if not (os.path.exists(o1) and os.path.exists(o2)):
        rec("seqkit_separate_invocations_preserve_pairing", "OK", "NO_OUTPUT", r.stderr[:120])
    else:
        got = pair(o1, o2)
        with gzip.open(o1, "rt") as fh:          # gzip, not raw bytes: the earlier count was wrong
            n1 = sum(1 for _ in fh) // 4
        rec("seqkit_separate_invocations_preserve_pairing", "OK", got,
            "retained %d of 2000 pairs at p=0.25" % n1)
        rec("seqkit_retention_is_proportional", "OK",
            "OK" if 400 <= n1 <= 600 else "FAIL", "retained %d, expected ~500" % n1)

    shutil.rmtree(d, ignore_errors=True)
    npass = sum(1 for x in results if x["pass"])
    print("\n  %d/%d fixtures passed" % (npass, len(results)))
    import json
    json.dump(results, io.open("/work/p113/P1.13_PAIRING_FIXTURES.json", "w",
                               encoding="utf-8"), indent=1)
    print("FIXTURES_%s" % ("CLEAN" if npass == len(results) else "FAILED"))
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

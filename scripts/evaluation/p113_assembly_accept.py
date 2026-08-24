#!/usr/bin/env python3
"""P1.13 fail-closed assembly acceptance with atomic publication.

An assembly is a candidate until every check below passes. Nothing is written to the final path
until validation has completed, the move to the final path is atomic, and the .done marker is
created LAST so a marker can never exist without a validated artefact behind it.

Truth-blind: no truth, label, ARG content, tool output or model score is read here.
"""
import hashlib, io, json, os, re, subprocess, sys

P = "/work/p113"
STAGE = "/data/p113_reads"
COHORT = P + "/P1.13_SELECTED_COHORT_v3.tsv"
MIN_COV = 30.0                 # frozen design: minimum_usable_coverage
MINLEN = 1000                  # frozen P1.12 convention: eligible contig length
LEN_LO, LEN_HI = 0.70, 1.30    # predeclared gross-implausibility band vs declared genome size
ASMIMG = "p19c2-cleanroom:1.0"

NUC = re.compile(r"[ACGTNacgtnRYKMSWBDHVrykmswbdhv]+")


class Reject(Exception):
    """Any failed check. Every path fails closed."""


def sha256(p):
    d = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            d.update(c)
    return d.hexdigest()


def cohort_row(bs):
    with io.open(COHORT, encoding="utf-8") as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for line in f:
            r = dict(zip(hdr, line.rstrip("\n").split("\t")))
            if r.get("biosample") == bs:
                return r
    raise Reject("biosample %s is not in the frozen cohort" % bs)


def parse_fasta(path):
    """Structural validation. Returns [(id, length)]. Fails closed on any malformation."""
    recs, cur, curlen = [], None, 0
    with io.open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.rstrip("\n").rstrip("\r")
            if line.startswith(">"):
                if cur is not None:
                    if curlen == 0:
                        raise Reject("contig %r has no sequence" % cur)
                    recs.append((cur, curlen))
                parts = line[1:].split()
                if not parts:
                    raise Reject("empty contig identifier at line %d" % ln)
                cur, curlen = parts[0], 0
            else:
                if cur is None:
                    raise Reject("sequence data before any header at line %d" % ln)
                if not line:
                    continue
                if not NUC.fullmatch(line):
                    raise Reject("non-nucleotide characters at line %d" % ln)
                curlen += len(line)
    if cur is None:
        raise Reject("no FASTA records found")
    if curlen == 0:
        raise Reject("contig %r has no sequence" % cur)
    recs.append((cur, curlen))
    return recs


def n50(lengths):
    s = sorted(lengths, reverse=True)
    half, run = sum(s) / 2.0, 0
    for L in s:
        run += L
        if run >= half:
            return L
    return 0


def validate(bs, attempt_dir, rc, attempt_no, command):
    row = cohort_row(bs)
    gsz = int(row["genome_size"])
    checks = {}

    # 1 frozen input / run identity
    checks["frozen_run_identity"] = {"biosample": bs, "run_accession": row["run_accession"],
                                     "genome_size": gsz}

    # 2 raw md5 receipt
    if not os.path.exists(P + "/state/acquire__%s.done" % bs):
        raise Reject("no passed raw md5 receipt for %s" % bs)
    checks["raw_md5_receipt"] = "passed"

    # 3 exact id-stream validation and 4 coverage floor, from the downsample receipt
    rp = P + "/receipts/down__%s.json" % bs
    if not os.path.exists(rp):
        raise Reject("no downsample receipt for %s" % bs)
    rec = json.load(io.open(rp, encoding="utf-8"))
    v = rec.get("validation", {})
    if not (v.get("raw_pair_exact_id_match") and v.get("downsampled_pair_exact_id_match")):
        raise Reject("downsample receipt does not record exact id-stream validation")
    if not os.path.exists(P + "/state/down__%s.done" % bs):
        raise Reject("no passed pairing-validation marker for %s" % bs)
    raw_cov = float(rec["raw"]["coverage_x"])
    if raw_cov < MIN_COV:
        raise Reject("raw coverage %.2fx below frozen floor %.1fx" % (raw_cov, MIN_COV))
    checks["exact_id_stream_validation"] = "passed"
    checks["coverage_floor"] = {"raw_cov": raw_cov, "floor": MIN_COV, "state": "passed"}
    checks["id_stream_sha256"] = {"raw": rec["raw"]["id_stream_sha256"],
                                  "retained": rec["retained"]["id_stream_sha256"]}

    # 5 hashes of the exact reads fed to the assembler
    d = os.path.join(STAGE, "down", bs)
    ins = {}
    for name in ("R1.fastq.gz", "R2.fastq.gz"):
        p = os.path.join(d, name)
        if os.path.islink(p):
            raise Reject("%s is a symlink; the container cannot resolve it" % p)
        if not os.path.isfile(p):
            raise Reject("missing assembler input %s" % p)
        ins[name] = sha256(p)
    checks["assembler_input_sha256"] = ins
    checks["input_mode"] = "downsampled" if rec["downsampled"] else "passthrough"

    # 6 image digest and exact command
    img_id = subprocess.run(["docker", "image", "inspect", ASMIMG, "--format", "{{.Id}}"],
                            capture_output=True, text=True).stdout.strip()
    if not img_id:
        raise Reject("cannot resolve assembler image digest for %s" % ASMIMG)
    checks["assembler"] = {"image": ASMIMG, "image_id": img_id, "command": command,
                           "attempt": attempt_no}

    # 7 exit code
    if rc != 0:
        raise Reject("assembler exit code %s" % rc)
    checks["exit_code"] = 0

    # 8-10 non-empty, structurally valid, unique contig identifiers
    fa = os.path.join(attempt_dir, "shortread.fasta")
    gfa = os.path.join(attempt_dir, "shortread.gfa")
    for p in (fa, gfa):
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            raise Reject("missing or empty %s" % os.path.basename(p))
    recs = parse_fasta(fa)
    ids = [c for c, _ in recs]
    if len(set(ids)) != len(ids):
        dup = sorted(set(i for i in ids if ids.count(i) > 1))
        raise Reject("duplicate contig identifiers: %s" % dup[:5])
    lengths = [L for _, L in recs]
    total = sum(lengths)

    # 11 gross-implausibility band against the isolate's own declared genome size
    lo, hi = LEN_LO * gsz, LEN_HI * gsz
    if not (lo <= total <= hi):
        raise Reject("total assembly length %d outside plausibility band %d-%d for declared "
                     "genome size %d" % (total, int(lo), int(hi), gsz))

    checks["assembly_metrics"] = {
        "contigs": len(recs), "total_length": total, "n50": n50(lengths),
        "longest": max(lengths),
        "eligible_contigs_ge_1000": sum(1 for L in lengths if L >= MINLEN),
        "declared_genome_size": gsz, "length_ratio": round(total / float(gsz), 4),
        "plausibility_band": [int(lo), int(hi)]}

    # 12 the assembler must have run from scratch. unicycler silently resumes from an existing
    # SPAdes graph, which would publish computation from an earlier, possibly interrupted run
    # under this attempt's provenance. Any evidence of reuse is a provenance violation.
    ulog = os.path.join(attempt_dir, "unicycler_shortread.log")
    if not os.path.isfile(ulog):
        raise Reject("assembler log absent; cannot establish that the run was clean")
    txt = io.open(ulog, encoding="utf-8", errors="replace").read()
    # also read the container's stdout for this attempt: on resume unicycler APPENDS to its own
    # log, so evidence can appear in either place. Both are checked.
    solog = P + "/logs/asm__%s__attempt%s.log" % (bs, attempt_no)
    if os.path.isfile(solog):
        txt += io.open(solog, encoding="utf-8", errors="replace").read()
    for marker in ("Will use this graph instead of running SPAdes",
                   "output directory already exists and files may be reused",
                   "files may be reused or overwritten"):
        if marker in txt:
            raise Reject("assembler reused pre-existing scratch (%r); this attempt did not "
                         "compute the assembly from the declared inputs" % marker)
    if "spades.py" not in txt and "SPAdes" not in txt:
        raise Reject("assembler log shows no SPAdes execution")
    checks["clean_run_verified"] = "no scratch reuse detected in assembler log"

    # 13 final artefact hashes
    checks["assembly_sha256"] = {"shortread.fasta": sha256(fa), "shortread.gfa": sha256(gfa)}
    return checks


def publish(bs, attempt_dir, checks):
    """Atomic: validated artefacts move into place, the marker is written LAST."""
    final = P + "/assemblies/shortread/" + bs
    os.makedirs(final, exist_ok=True)
    moved = []
    for name in ("shortread.fasta", "shortread.gfa", "unicycler_shortread.log"):
        src = os.path.join(attempt_dir, name)
        if os.path.exists(src):
            os.replace(src, os.path.join(final, name))   # atomic within one filesystem
            moved.append(name)
    checks["published"] = moved
    tmp = P + "/receipts/.asm__%s.json.tmp" % bs
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(checks, indent=1) + "\n")
    os.replace(tmp, P + "/receipts/asm__%s.json" % bs)
    open(P + "/state/asm__%s.done" % bs, "w").close()    # marker LAST
    return checks


if __name__ == "__main__":
    bs, attempt_dir, rc, attempt_no = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    command = sys.argv[5] if len(sys.argv) > 5 else ""
    try:
        c = validate(bs, attempt_dir, rc, attempt_no, command)
        c = publish(bs, attempt_dir, c)
    except Reject as e:
        print("ASM_REJECT %s attempt=%s : %s" % (bs, attempt_no, e))
        sys.exit(1)
    m = c["assembly_metrics"]
    print("ASM_ACCEPT %s attempt=%s contigs=%d total=%d n50=%d eligible=%d ratio=%.3f sha=%s"
          % (bs, attempt_no, m["contigs"], m["total_length"], m["n50"],
             m["eligible_contigs_ge_1000"], m["length_ratio"],
             c["assembly_sha256"]["shortread.fasta"][:16]))

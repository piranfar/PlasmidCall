#!/usr/bin/env python3
"""P1.13 validated deterministic downsampling for one isolate.

Order of operations, all fail-closed:
  1. validate the RAW pair exactly (position-by-position normalized ids, streaming digest)
  2. recompute achieved coverage from retained sequence bases, never from file size
  3. downsample with the frozen algorithm, seed and target - unchanged
  4. validate the DOWNSAMPLED pair exactly, including the retained-count declaration
  5. write a receipt carrying both digests

Nothing here changes the cohort, target depth, seed, sampling algorithm or selected reads.
"""
import glob, io, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p113_pairing import validate_pair, coverage_from_bases, PairError

P = "/work/p113"
STAGE = "/data/p113_reads"
NORMIMG = "p19c2-normalize:1.0"
SEED = 20260821
TARGET_COV = 100.0
MIN_USABLE_COV = 30.0   # frozen design, P1.13_FROZEN_DESIGN.yaml: minimum_usable_coverage


def run(bs, genome_size):
    raw = os.path.join(STAGE, "raw", bs)
    out = os.path.join(STAGE, "down", bs)
    os.makedirs(out, exist_ok=True)
    r1 = sorted(glob.glob(raw + "/*_1.fastq.gz"))
    r2 = sorted(glob.glob(raw + "/*_2.fastq.gz"))
    if len(r1) != 1 or len(r2) != 1:
        raise PairError("expected exactly one R1 and one R2 in %s, found %d/%d"
                        % (raw, len(r1), len(r2)))
    r1, r2 = r1[0], r2[0]

    # 1-2 raw pair validated exactly, coverage recomputed from bases
    pre = validate_pair(r1, r2)
    pre_cov = coverage_from_bases(pre["bases"], genome_size)
    # The frozen design declares a 30x minimum usable coverage. Selection used ENA's DECLARED
    # coverage estimate; this is the first point where coverage is recomputed from actual
    # sequenced bases. Enforce the frozen floor here rather than assembling an isolate that
    # does not meet the design's own eligibility contract.
    if pre_cov < MIN_USABLE_COV:
        raise PairError("recomputed raw coverage %.2fx is below the frozen minimum usable "
                        "coverage of %.1fx; this isolate does not satisfy the frozen "
                        "eligibility contract and is not assembled"
                        % (pre_cov, MIN_USABLE_COV))

    frac = min(1.0, TARGET_COV / pre_cov) if pre_cov > 0 else 1.0
    o1, o2 = out + "/R1.fastq.gz", out + "/R2.fastq.gz"

    if frac >= 1.0:
        # no downsampling: link the verified raw files, pairing already proven above
        for src, dst in ((r1, o1), (r2, o2)):
            if os.path.islink(dst) or os.path.exists(dst):
                os.remove(dst)
            # HARD link, not symlink: the assembly container mounts only down/<bs>, so an
            # absolute symlink into raw/ dangles inside the container. raw/ and down/ share a
            # filesystem, so a hard link costs no extra space and presents a real file.
            os.link(src, dst)
        post, downsampled = pre, False
    else:
        # per-isolate scratch: phase 2 runs concurrently, so a shared /tmp mount would
        # let two seqkit containers collide. Isolation here keeps each run independent.
        tmp = P + "/tmp/host/" + bs
        os.makedirs(tmp, exist_ok=True)
        cmd = ("seqkit sample -p %.6f -s %d -o /o/R1.fastq.gz /r/%s && "
               "seqkit sample -p %.6f -s %d -o /o/R2.fastq.gz /r/%s"
               % (frac, SEED, os.path.basename(r1), frac, SEED, os.path.basename(r2)))
        p = subprocess.run(["docker", "run", "--rm", "--memory=16g", "--cpus=4",
                            "-v", raw + ":/r:ro", "-v", out + ":/o", "-v", tmp + ":/tmp",
                            "-e", "TMPDIR=/tmp", "-e", "TMP=/tmp", "-e", "TEMP=/tmp",
                            "--entrypoint", "bash", NORMIMG, "-lc", cmd],
                           capture_output=True, text=True)
        if p.returncode != 0 or not (os.path.exists(o1) and os.path.exists(o2)):
            raise PairError("seqkit downsampling failed for %s: %s" % (bs, p.stderr[-300:]))
        # 4 exact validation of the downsampled pair; count declared from the R1 stream itself
        post = validate_pair(o1, o2)
        post2 = validate_pair(o1, o2, expect_count=post["pairs"])
        if post2["id_stream_sha256"] != post["id_stream_sha256"]:
            raise PairError("downsampled id-stream digest is not stable across two reads")
        downsampled = True

    post_cov = coverage_from_bases(post["bases"], genome_size)
    receipt = {
        "biosample": bs, "genome_size": genome_size,
        "raw": {"r1": os.path.basename(r1), "r2": os.path.basename(r2),
                "pairs": pre["pairs"], "bases": pre["bases"],
                "id_stream_sha256": pre["id_stream_sha256"],
                "coverage_x": round(pre_cov, 2)},
        "downsampled": downsampled, "fraction": round(frac, 6), "seed": SEED,
        "target_coverage_x": TARGET_COV,
        "algorithm": "seqkit sample -p <fraction> -s <seed>, frozen p19c2-normalize:1.0",
        "retained": {"pairs": post["pairs"], "bases": post["bases"],
                     "id_stream_sha256": post["id_stream_sha256"],
                     "coverage_x": round(post_cov, 2)},
        "validation": {
            "raw_pair_exact_id_match": True,
            "downsampled_pair_exact_id_match": True,
            "duplicate_normalized_ids": "none detected",
            "fastq_structure": "validated, fails closed on truncation or malformation",
            "retained_count_declared_and_verified": post["pairs"],
            "coverage_recomputed_from_retained_bases": True,
            "count_only_check": "PROHIBITED and not used"},
        "note": ("the retained pair count is a deterministic function of (input, fraction, seed) "
                 "under a proportion-based sampler; it is recorded and verified rather than "
                 "pre-specified as an integer"),
    }
    io.open(P + "/receipts/down__%s.json" % bs, "w", encoding="utf-8").write(
        json.dumps(receipt, indent=1) + "\n")
    return receipt


if __name__ == "__main__":
    bs, gsz = sys.argv[1], int(sys.argv[2])
    try:
        r = run(bs, gsz)
    except PairError as e:
        print("DOWNSAMPLE_FAIL %s : %s" % (bs, e)); sys.exit(1)
    print("DOWNSAMPLE_OK %s raw=%d pairs %.1fx -> retained=%d pairs %.1fx frac=%.4f digest=%s"
          % (bs, r["raw"]["pairs"], r["raw"]["coverage_x"], r["retained"]["pairs"],
             r["retained"]["coverage_x"], r["fraction"], r["retained"]["id_stream_sha256"][:16]))

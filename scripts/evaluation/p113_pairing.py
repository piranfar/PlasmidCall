#!/usr/bin/env python3
"""P1.13 exact read-pair validation. PRODUCTION module - the runner and the fixtures both use it.

Count equality does not prove pairing: two files can hold the same number of records and still
carry different reads, or the same reads in a different order. Every check here is on the exact
normalized identifier stream, compared position by position, and carried as a streaming digest so
no large intermediate file is required.

Normalization removes ONLY the legitimate mate marker:
  - a trailing "/1" or "/2"
  - the Illumina whitespace mate field, e.g. "@A00:1:... 1:N:0:ATCG" -> everything after the first
    whitespace is dropped
Nothing else about the identifier is altered.
"""
import gzip
import hashlib
import io
import re
import sys

MATE_SUFFIX = re.compile(r"/[12]$")


class PairError(Exception):
    """Raised for any structural or pairing defect. Every path fails closed."""


def normalize_id(header):
    """'@ID/1 1:N:0:X' -> 'ID'. Only the mate marker is removed."""
    if not header.startswith("@"):
        raise PairError("record header does not start with '@': %r" % header[:60])
    tok = header[1:].split(None, 1)[0]          # drop the Illumina whitespace mate field
    if not tok:
        raise PairError("empty read identifier in header %r" % header[:60])
    return MATE_SUFFIX.sub("", tok)             # drop a trailing /1 or /2


def _open(path):
    return gzip.open(path, "rt") if str(path).endswith(".gz") else io.open(path, "rt")


def stream_ids(path):
    """Yield normalized ids. Fails closed on truncated or malformed FASTQ."""
    with _open(path) as f:
        n = 0
        while True:
            h = f.readline()
            if not h:
                return
            h = h.rstrip("\n")
            seq = f.readline()
            plus = f.readline()
            qual = f.readline()
            if not seq or not plus or not qual:
                raise PairError("truncated FASTQ at record %d in %s" % (n + 1, path))
            seq = seq.rstrip("\n"); plus = plus.rstrip("\n"); qual = qual.rstrip("\n")
            if not plus.startswith("+"):
                raise PairError("record %d in %s: third line does not start with '+'" % (n + 1, path))
            if len(seq) != len(qual):
                raise PairError("record %d in %s: sequence %d and quality %d differ in length"
                                % (n + 1, path, len(seq), len(qual)))
            n += 1
            yield normalize_id(h), len(seq)


def validate_pair(r1, r2, expect_count=None, detect_duplicates=True):
    """Position-by-position exact comparison of the normalized id streams.

    Returns a dict with the streaming digest, record count and total bases.
    Raises PairError on the first defect.
    """
    d1, d2 = hashlib.sha256(), hashlib.sha256()
    seen = set() if detect_duplicates else None
    n = 0
    bases = 0
    g1, g2 = stream_ids(r1), stream_ids(r2)
    while True:
        a = next(g1, None)
        b = next(g2, None)
        if a is None and b is None:
            break
        if a is None:
            raise PairError("R1 exhausted at record %d while R2 continues (missing mate)" % (n + 1))
        if b is None:
            raise PairError("R2 exhausted at record %d while R1 continues (missing mate)" % (n + 1))
        ia, la = a
        ib, lb = b
        if ia != ib:
            raise PairError("identifier mismatch at record %d: R1=%r R2=%r" % (n + 1, ia, ib))
        if seen is not None:
            if ia in seen:
                raise PairError("duplicate normalized identifier %r at record %d" % (ia, n + 1))
            seen.add(ia)
        d1.update(ia.encode()); d1.update(b"\n")
        d2.update(ib.encode()); d2.update(b"\n")
        bases += la + lb
        n += 1
    if d1.hexdigest() != d2.hexdigest():
        raise PairError("normalized id-stream digests differ despite positionwise equality")
    if n == 0:
        raise PairError("no records found in %s / %s" % (r1, r2))
    if expect_count is not None and n != expect_count:
        raise PairError("retained pair count %d does not equal the declared deterministic target %d"
                        % (n, expect_count))
    return {"pairs": n, "bases": bases, "id_stream_sha256": d1.hexdigest()}


def coverage_from_bases(bases, genome_size):
    if not genome_size:
        raise PairError("genome size unavailable; cannot recompute coverage")
    return bases / float(genome_size)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: p113_pairing.py <R1> <R2> [expected_pairs] [genome_size]"); sys.exit(2)
    exp = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    try:
        r = validate_pair(sys.argv[1], sys.argv[2], expect_count=exp)
    except PairError as e:
        print("PAIRING_FAIL %s" % e); sys.exit(1)
    if len(sys.argv) > 4:
        r["coverage_x"] = round(coverage_from_bases(r["bases"], int(sys.argv[4])), 2)
    print("PAIRING_OK pairs=%d bases=%d digest=%s%s"
          % (r["pairs"], r["bases"], r["id_stream_sha256"][:16],
             (" coverage=%.2fx" % r["coverage_x"]) if "coverage_x" in r else ""))

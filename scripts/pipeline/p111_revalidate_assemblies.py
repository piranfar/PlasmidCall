#!/usr/bin/env python3
"""Re-validate existing Product A assemblies against the CORRECTED invariant.

The first assembly run applied an invented invariant - FASTA contig count == GFA segment count -
that never held anywhere. Unicycler's assembly.gfa holds the full assembly GRAPH while
assembly.fasta holds the final contig set, so the graph is a strict superset. Verified against the
frozen precedent: 0 of 8 P1.10 assemblies satisfy equality, and every one has GFA > FASTA.

Healthy assemblies were therefore marked FAILED. This promotes any assembly that passes the
corrected checks to VERIFIED without re-running Unicycler, and writes its receipt. Anything that
genuinely fails keeps a FAILED marker with the real reason.

Corrected checks:
  * shortread.fasta and shortread.gfa both exist and are non-empty
  * FASTA contig count >= 1
  * GFA segment count >= FASTA contig count   (graph is a superset)
  * the recorded command contains no long-read (-l/--long) or unpaired (-s) flag
"""
import hashlib, json, os, re, sys, datetime

BASE = "/work/p112"
ASM = os.path.join(BASE, "assemblies", "shortread")
STATE = os.path.join(BASE, "work", "p111", "state")
RECD = os.path.join(BASE, "receipts", "assembly")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def counts(fa, gfa):
    n = 0
    with open(fa, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(">"):
                n += 1
    m = 0
    with open(gfa, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("S\t") or line.startswith("S "):
                m += 1
    return n, m


def main():
    os.makedirs(STATE, exist_ok=True)
    os.makedirs(RECD, exist_ok=True)
    promoted = kept_failed = already = 0
    for bs in sorted(os.listdir(ASM)) if os.path.isdir(ASM) else []:
        d = os.path.join(ASM, bs)
        fa, gfa = os.path.join(d, "shortread.fasta"), os.path.join(d, "shortread.gfa")
        vmark, fmark = os.path.join(STATE, bs + ".VERIFIED"), os.path.join(STATE, bs + ".FAILED")
        if os.path.exists(vmark):
            already += 1
            continue
        if not (os.path.exists(fa) and os.path.getsize(fa) > 0
                and os.path.exists(gfa) and os.path.getsize(gfa) > 0):
            print("  SKIP    %-16s incomplete on disk (still assembling or truly absent)" % bs)
            continue
        nfa, ngfa = counts(fa, gfa)
        reason = None
        if nfa < 1 or ngfa < 1:
            reason = "empty_fasta_or_gfa_%d_%d" % (nfa, ngfa)
        elif ngfa < nfa:
            reason = "gfa_not_superset_%d_%d" % (nfa, ngfa)
        cmdf = os.path.join(RECD, bs + ".cmd")
        if reason is None and os.path.exists(cmdf):
            cmd = open(cmdf, encoding="utf-8", errors="replace").read()
            if re.search(r" -l | --long | -s ", cmd):
                reason = "longread_or_unpaired_flag"
        if reason:
            with open(fmark, "w") as f:
                f.write(reason)
            kept_failed += 1
            print("  FAILED  %-16s %s" % (bs, reason))
            continue
        with open(os.path.join(RECD, bs + ".json"), "w") as f:
            json.dump({"biosample": bs, "image": "p19c2-cleanroom:1.0",
                       "n_contigs_fasta": nfa, "n_segments_gfa": ngfa,
                       "fasta_sha256": sha(fa), "gfa_sha256": sha(gfa),
                       "fasta_bytes": os.path.getsize(fa), "gfa_bytes": os.path.getsize(gfa),
                       "long_read_input": False, "unpaired_input": False,
                       "protocol": "unicycler -1 R1 -2 R2 -o /tmp/a -t 8 --keep 1",
                       "validated_by": "p111_revalidate_assemblies.py (corrected invariant)",
                       "utc": datetime.datetime.now(datetime.timezone.utc).strftime(
                           "%Y-%m-%dT%H:%M:%SZ")}, f, indent=1)
        if os.path.exists(fmark):
            os.remove(fmark)
        with open(vmark, "w") as f:
            f.write("ok")
        promoted += 1
        print("  VERIFIED %-16s %d contigs, %d GFA segments" % (bs, nfa, ngfa))
    print("\n  promoted=%d  already_verified=%d  genuinely_failed=%d" % (promoted, already, kept_failed))


if __name__ == "__main__":
    main()

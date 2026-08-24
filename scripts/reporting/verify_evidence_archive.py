# -*- coding: utf-8 -*-
"""Verify the downloaded evidence archive against the digests recorded on the execution host.

The archive is a single .tar.zst holding the complete P1.13 evidence tree as it stood at the
prediction freeze. This script answers four questions and records the answers, including the
unfavourable one:

  1. Did the download arrive intact? Re-hash the whole archive against the recorded sha256.
  2. Does the sealed claim survive the round trip? Extract the frozen prediction table from
     inside the archive and check its digest against the value bound in the results freeze and
     named in the truth authorisation.
  3. Do the parsed tool calls reconcile? Count rows across every per-tool per-isolate parsed file
     and check the product against tools x isolates x contigs.
  4. What is NOT in the archive? The archive was built before truth was authorised, so the
     post-truth artefacts are absent. That is stated rather than left to be discovered.

The archive path is taken from PLASMIDCALL_EVIDENCE_ARCHIVE or the first argument; only the
archive's filename and digest are recorded, never a local path.
"""
import io, os, sys, json, tarfile, hashlib, collections, time

import zstandard as zstd

ARCHIVE = (os.environ.get("PLASMIDCALL_EVIDENCE_ARCHIVE")
           or (sys.argv[1] if len(sys.argv) > 1 else ""))
OUT = "docs/closure/EVIDENCE_ARCHIVE_VERIFICATION.json"
RF = json.load(io.open("docs/evidence/P1.13_results/RESULTS_FROZEN.json", encoding="utf-8"))

if not ARCHIVE or not os.path.exists(ARCHIVE):
    print("evidence archive not available on this machine; nothing verified.")
    print("point PLASMIDCALL_EVIDENCE_ARCHIVE at P1.13_EVIDENCE_ARCHIVE.tar.zst to run this.")
    sys.exit(0)

SIDE = os.path.join(os.path.dirname(ARCHIVE), os.path.basename(ARCHIVE) + ".sha256")
recorded = None
if os.path.exists(SIDE):
    recorded = io.open(SIDE, encoding="utf-8").read().split()[0]

fail, report = [], collections.OrderedDict()
report["archive"] = os.path.basename(ARCHIVE)
report["bytes"] = os.path.getsize(ARCHIVE)

# ------------------------------------------------------------------ 1. whole-archive digest
t0 = time.time()
h = hashlib.sha256()
with io.open(ARCHIVE, "rb") as f:
    for c in iter(lambda: f.read(1 << 24), b""):
        h.update(c)
got = h.hexdigest()
report["sha256"] = got
report["sha256_recorded_on_host"] = recorded
report["download_intact"] = (recorded is not None and got == recorded)
if recorded and got != recorded:
    fail.append("archive digest differs from the value recorded on the execution host")
print("archive digest   : %s (%s)" % (got[:16] + "…",
                                      "match" if report["download_intact"] else "NO MATCH"))

# ------------------------------------------------------------------ 2-4. one streaming pass
WANT = {"P1.13_FROZEN_PREDICTIONS.tsv":
        RF["bound_prediction_freeze"]["frozen_prediction_table_sha256"]}
POST_TRUTH = ["P113_TRUTH_JOINED.tsv", "P113_ERROR_CATALOGUE.tsv", "P113_PRIMARY_METRICS.tsv",
              "P113_COMPARATOR_METRICS.tsv", "RESULTS_FROZEN.json"]

members = 0
verified = {}
parsed_rows = collections.Counter()
parsed_files = collections.Counter()
seen_post_truth = []
manifest_rows = None

dctx = zstd.ZstdDecompressor(max_window_size=2 ** 31)
with io.open(ARCHIVE, "rb") as fh, dctx.stream_reader(fh) as r, \
        tarfile.open(fileobj=r, mode="r|") as tf:
    for m in tf:
        if not m.isfile():
            continue
        members += 1
        base = os.path.basename(m.name)
        if base in POST_TRUTH:
            seen_post_truth.append(m.name)
        if "/inference/parsed/" in m.name:
            tool = m.name.split("/inference/parsed/")[1].split("/")[0]
            data = tf.extractfile(m).read()
            n = data.count(b"\n") + (0 if not data or data.endswith(b"\n") else 1)
            parsed_rows[tool] += max(0, n - 1)
            parsed_files[tool] += 1
            continue
        if base in WANT and base not in verified:
            d = tf.extractfile(m).read()
            hh = hashlib.sha256(d).hexdigest()
            verified[base] = {"member": m.name, "bytes": len(d), "sha256": hh,
                              "recorded_in_results_freeze": WANT[base],
                              "matches": hh == WANT[base],
                              "data_rows": d.count(b"\n") - 1}
            if hh != WANT[base]:
                fail.append("%s inside the archive differs from the frozen digest" % base)
        if base == "P1.13_EVIDENCE_MANIFEST.sha256" and manifest_rows is None:
            manifest_rows = tf.extractfile(m).read().count(b"\n")

report["members"] = members
report["internal_manifest_rows"] = manifest_rows
report["internal_manifest_covers_all_other_members"] = (
    manifest_rows is not None and manifest_rows == members - 1)
report["frozen_artefacts_verified_from_inside_archive"] = verified

# parsed-call reconciliation
tools = len(parsed_files)
per_tool = sorted(set(parsed_rows.values()))
contigs = RF["denominators"]["contigs_joined"]
isolates = RF["denominators"]["isolates"]
report["parsed_tool_calls"] = {
    "tools": tools,
    "files": sum(parsed_files.values()),
    "rows_per_tool": per_tool,
    "total_rows": sum(parsed_rows.values()),
    "expected": tools * contigs,
    "reconciles": (len(per_tool) == 1 and per_tool[0] == contigs
                   and sum(parsed_files.values()) == tools * isolates),
    "derivation": "%d tools x %d isolates, each file carrying one row per contig, "
                  "%d tools x %d contigs = %d parsed calls"
                  % (tools, isolates, tools, contigs, tools * contigs)}
if not report["parsed_tool_calls"]["reconciles"]:
    fail.append("parsed tool calls do not reconcile to tools x contigs")

# what is absent, and why
report["post_truth_artefacts_absent"] = {
    "absent": [p for p in POST_TRUTH if not any(p in s for s in seen_post_truth)],
    "present": seen_post_truth,
    "reason": "the archive captures the evidence tree as it stood at the prediction freeze, "
              "before truth acquisition was authorised. Post-truth artefacts were created "
              "afterwards and were never added to it. The small ones are held in this "
              "repository; the joined truth-prediction table and the per-contig error "
              "catalogue exist only on the execution host, with their digests recorded in "
              "RESULTS_FROZEN.json.",
    "consequence": "terminating the execution host without first copying those two files would "
                   "lose the only extant copies. Their digests would survive, so the loss would "
                   "be detectable, but not repairable."}

# ------------------------------------------------------------------ 5. companion downloads
# The shutdown-safe receipt lists what was to be preserved off-server. Check each item that
# should sit beside the archive, and say plainly which listed item did not arrive.
DIR = os.path.dirname(ARCHIVE)
try:
    pres = json.load(io.open("docs/closure/PLASMIDCALL_SHUTDOWN_SAFE_RECEIPT.json",
                             encoding="utf-8"))["offserver_preservation"]
except Exception:
    pres = {}


def digest(p):
    hh = hashlib.sha256()
    with io.open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 24), b""):
            hh.update(c)
    return hh.hexdigest()


companions, absent = {}, []
for key, entry in pres.items():
    if key == "git_remote" or not isinstance(entry, dict) or "path" not in entry:
        continue
    base = os.path.basename(entry["path"])
    local = os.path.join(DIR, base)
    if not os.path.exists(local):
        absent.append({"item": key, "file": base, "sha256_recorded": entry["sha256"],
                       "receipt_asserted_verified": bool(entry.get("verified"))})
        continue
    if base == os.path.basename(ARCHIVE):
        companions[base] = {"item": key, "sha256": got, "matches": got == entry["sha256"]}
        continue
    d = digest(local)
    companions[base] = {"item": key, "bytes": os.path.getsize(local), "sha256": d,
                        "matches": d == entry["sha256"]}
    if d != entry["sha256"]:
        fail.append("%s differs from the digest recorded on the execution host" % base)

# the reads manifest is described in the archive note rather than the receipt
READS = os.path.join(DIR, "P1.13_READS_MANIFEST.sha256")
if os.path.exists(READS):
    d = digest(READS)
    companions["P1.13_READS_MANIFEST.sha256"] = {
        "item": "reads_manifest", "bytes": os.path.getsize(READS), "sha256": d,
        "rows": sum(1 for _ in io.open(READS, encoding="utf-8")),
        "matches": d == "f42a193f1d675c8935923408560c012f6bb632b2b7dac734d304ebdf41c1dbdd"}
    if not companions["P1.13_READS_MANIFEST.sha256"]["matches"]:
        fail.append("reads manifest differs from the digest recorded in the archive note")

report["companion_downloads_verified"] = companions
report["listed_for_preservation_but_absent"] = absent
report["only_on_the_execution_host"] = {
    "files": sorted(set([a["file"] for a in absent] +
                        report["post_truth_artefacts_absent"]["absent"])
                    - {os.path.basename(k) for k in companions}
                    - {"P113_PRIMARY_METRICS.tsv", "P113_COMPARATOR_METRICS.tsv",
                       "RESULTS_FROZEN.json"}),
    "note": "P113_PRIMARY_METRICS.tsv, P113_COMPARATOR_METRICS.tsv and RESULTS_FROZEN.json are "
            "absent from the archive but ARE held in this repository, so they are not at risk.",
    "why_it_matters": "P113_TRUTH_JOINED.tsv is the scored table from which every reported metric "
                      "is computed and against which both independent verifiers re-derived their "
                      "values. Without it a third party can check the derived metric tables but "
                      "cannot re-derive them from the scored data. P113_ERROR_CATALOGUE.tsv holds "
                      "the per-contig error records. Both have digests recorded in "
                      "RESULTS_FROZEN.json, so their loss would be detectable but not repairable.",
    "action": "copy both files off the execution host before terminating it."}
if report["only_on_the_execution_host"]["files"]:
    print("\nONLY ON THE EXECUTION HOST: %s"
          % ", ".join(report["only_on_the_execution_host"]["files"]))

report["elapsed_s"] = round(time.time() - t0, 1)
report["failures"] = fail
report["verdict"] = "EVIDENCE_ARCHIVE_VERIFIED" if not fail else "FAILURES"
io.open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(report, indent=1) + "\n")

print("members          : %s" % "{:,}".format(members))
print("internal manifest: %s rows, covers every other member: %s"
      % ("{:,}".format(manifest_rows or 0),
         report["internal_manifest_covers_all_other_members"]))
for k, v in verified.items():
    print("%-18s: %s, %s data rows"
          % (k[:18], "digest MATCHES the results freeze" if v["matches"] else "MISMATCH",
             "{:,}".format(v["data_rows"])))
print("parsed calls     : %s across %d files, %s"
      % ("{:,}".format(report["parsed_tool_calls"]["total_rows"]),
         report["parsed_tool_calls"]["files"],
         "reconciles" if report["parsed_tool_calls"]["reconciles"] else "DOES NOT RECONCILE"))
print("absent post-truth: %s" % ", ".join(report["post_truth_artefacts_absent"]["absent"]))
print("VERDICT          : %s" % report["verdict"])
for f in fail:
    print("   FAIL", f)
sys.exit(0 if not fail else 1)

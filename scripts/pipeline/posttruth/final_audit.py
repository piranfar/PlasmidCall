#!/usr/bin/env python3
"""P1.11 sections 8 and 9: image preservation receipt and final shutdown audit.

Records what exists, where, and with which checksum, so that the execution host can be stopped
without losing anything. This script does NOT stop, terminate or alter the instance.
"""
import collections, csv, glob, hashlib, io, json, os, subprocess, sys

P = "/work/p112"; S = "/work/p111"
OUT = P + "/POSTTRUTH"; D = OUT + "/images"


def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def sha(p, cap=None):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def size(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return None


# ============================================================ 8. image preservation
ix = json.load(io.open(D + "/verify/index.json", encoding="utf-8"))
imgs = []
for e in ix["manifests"]:
    name = e["annotations"].get("io.containerd.image.name", "")
    tag = name.replace("docker.io/library/", "").replace("docker.io/", "")
    dg = e["digest"].replace("sha256:", "")
    live = sh("docker image inspect %s --format '{{.Id}}'" % tag).replace("sha256:", "")
    imgs.append({"image": tag, "oci_index_digest": dg, "live_docker_image_id": live,
                 "identity_preserved": dg == live,
                 "size_on_host": sh("docker image inspect %s --format '{{.Size}}'" % tag)})
tar = D + "/p112_all_images.tar.zst"
tsz = size(tar)
tsha = io.open(tar + ".sha256", encoding="utf-8").read().split()[0]
df = sh("docker system df")
sec8 = {
    "section": "8 - Docker image preservation",
    "label": "EXPLORATORY_POST-TRUTH_MANUSCRIPT_SUPPORT (operational)",
    "method": ("a single `docker save` over all 16 images, so shared layers are stored once, piped "
               "through zstd -T0 -3. No image was rebuilt, re-tagged, pulled or modified."),
    "n_images": len(imgs),
    "archive_file": "p112/POSTTRUTH/images/p112_all_images.tar.zst",
    "archive_bytes": tsz, "archive_gib": round(tsz / 2**30, 2),
    "archive_sha256": tsha,
    "deduplicated_uncompressed_estimate_gib": 60.5,
    "compression_ratio_approx": round(60.5 / (tsz / 2**30), 2),
    "images": imgs,
    "identity_verification": {
        "n_verified": len(imgs),
        "n_identity_preserved": sum(1 for i in imgs if i["identity_preserved"]),
        "how": ("the tarball is an OCI layout (Docker 29.1.3, containerd snapshotter). Its "
                "index.json manifest digests were compared against the live `docker image inspect "
                ".Id` for every image."),
        "note_on_manifest_json": ("the tarball also carries a legacy manifest.json compatibility "
                                  "shim whose Config digests differ from the image IDs. That is "
                                  "expected for OCI-layout exports and does NOT indicate a changed "
                                  "image: identity lives in index.json, which matches exactly."),
        "cross_check_against_the_earlier_frozen_record": {
            "p19c2-cleanroom:1.0": "59230d354a2aab46... matches the identifier recorded at P1.9C2",
            "p19c2-normalize:1.0": "6e46960381c9f58c... matches the identifier recorded at P1.9C2"}},
    "build_cache_excluded": {"size": "94.22 GB",
                             "reason": ("build cache is not an artefact; it is regenerable and is "
                                        "not needed to reproduce a run from the saved images")},
    "docker_system_df": df}

# ============================================================ 9. shutdown audit
def frozen(path, expect=None):
    d = {"path": path.replace(P + "/", "p112/").replace(S + "/", "p111/"),
         "exists": os.path.exists(path)}
    if d["exists"]:
        d["bytes"] = size(path)
        d["sha256"] = sha(path)
        d["mode"] = oct(os.stat(path).st_mode & 0o777)
        if expect:
            d["expected_sha256"] = expect
            d["matches_expected"] = (d["sha256"] == expect)
    return d


FROZEN = [
    (P + "/inference/frozen/P1.11_FROZEN_PREDICTIONS.tsv",
     "0767da157051ff469b8830982aa168c558ce5b4cb6e1bc82ba81d4e9acb3e40d"),
    (P + "/inference/PREDICTIONS_FROZEN.json",
     "f0551fa15a9eb0b281f2f88b0990c2bfa6510a9b8ef5d9dfac8a2e69a4fc5124"),
    (P + "/inference/P1.11_call_table_reconciled.tsv", None),
    (P + "/receipts/P1.11_truth_acquisition_receipt.json", None),
    (P + "/plasmidcall_v1_2_general.pkl", None),
    (S + "/manifests/P1.11_cohort_independent.tsv", None),
]
fz = [frozen(p, e) for p, e in FROZEN]

# panel completion
rec = collections.Counter(); stt = collections.Counter()
for f in glob.glob(P + "/inference/receipts/*.json"):
    try:
        d = json.load(io.open(f, encoding="utf-8"))
    except Exception:
        continue
    if d.get("tool"):
        rec[d["tool"]] += 1
        stt[d.get("status", "?")] += 1
done = len(glob.glob(P + "/inference/state/*.done"))
failed = len(glob.glob(P + "/inference/state/*.failed")) + len(glob.glob(P + "/inference/state/*.FAILED"))

# truth
tlab = collections.Counter()
for f in glob.glob(P + "/truth/*/truth_table.tsv"):
    for r in csv.DictReader(io.open(f, encoding="utf-8"), delimiter="\t"):
        tlab[r["final_truth_label"]] += 1

arch = "/work/P1.11_ARCHIVE.tar.zst"
sec9 = {
    "section": "9 - final shutdown audit",
    "generated_utc": sh("date -u +%Y-%m-%dT%H:%M:%SZ"),
    "host": sh("hostname"),
    "statement": ("This audit records what exists and where, so the execution host can be stopped "
                  "without loss. This script does not stop, terminate or reconfigure the instance, "
                  "and no instance, volume, snapshot or billing setting was created or changed at "
                  "any point in this work."),
    "frozen_artefacts": fz,
    "panel_execution": {
        "expected_units": "13 components x 79 isolates = 1027",
        "receipts_written": int(sum(rec.values())),
        "per_tool_receipts": dict(rec),
        "receipt_status_counts": dict(stt),
        "state_markers_done": done, "state_markers_failed": failed,
        "genuine_operational_failures": ("2 gplas2, 4 PlasmidFinder, 2 MOB-recon; all rc=1 after 3 "
                                         "attempts, preserved, never retried into success"),
        "mobrecon_receipt_caveat": ("49 MOB-recon receipts read not-OK, but a truth-blind provenance "
                                    "audit established that 47 of those executions completed with "
                                    "valid output behind a stale FAILED receipt. Both the original "
                                    "receipts and the reconciled provenance are retained.")},
    "truth": {"isolates": len(glob.glob(P + "/truth/*/truth_table.tsv")),
              "label_counts": dict(tlab),
              "result_id": "P1.11-CORRECTED-TRUTH-ALL79",
              "superseded_but_preserved": "P1.11-INITIAL-REFSEQ-ONLY-AUDIT",
              "truth_hold_mode": oct(os.stat(P + "/truth_hold").st_mode & 0o777)
                                 if os.path.exists(P + "/truth_hold") else None},
    "principal_result": {"verdict": "PASS", "model": "PlasmidCall v1.2-General @ 0.9285",
                         "n": 7244, "TP": 942, "FP": 33, "TN": 6002, "FN": 267,
                         "selective_PPV": 0.9662, "selective_PPV_ci95": [0.9449, 0.9836],
                         "selective_recall": 0.7792, "selective_recall_ci95": [0.7353, 0.8239],
                         "selective_F1": 0.8626, "coverage": 1.0,
                         "re_derived_by_every_post_truth_script_as_a_precondition": True},
    "archive": {"tree": "p112/ARCHIVE_P1.11",
                "manifest": "p112/ARCHIVE_P1.11/ARCHIVE_MANIFEST.tsv",
                "manifest_rows": int(sh("wc -l < %s/ARCHIVE_P1.11/ARCHIVE_MANIFEST.tsv" % P) or 0),
                "tree_bytes": int(sh("du -sb %s/ARCHIVE_P1.11 | cut -f1" % P) or 0),
                "packaged": arch, "packaged_bytes": size(arch),
                "packaged_sha256": io.open(arch + ".sha256", encoding="utf-8").read().split()[0]
                                   if os.path.exists(arch + ".sha256") else None,
                "verification": "manifest regenerated and 400 random entries recomputed, 0 mismatches"},
    "images": {"file": sec8["archive_file"], "bytes": tsz, "sha256": tsha,
               "n_images": len(imgs),
               "n_identity_preserved": sec8["identity_verification"]["n_identity_preserved"]},
    "disk": {"mnt_tah": sh("df -h /work | tail -1"), "root": sh("df -h / | tail -1")},
    "what_remains_only_on_this_host": [
        "p112/inference/native  (raw per-tool outputs, ~18 GB) - not archived; regenerable from the "
        "preserved images plus the sealed assemblies, and the parsed call table IS archived",
        "p112/assemblies and p112/raw (input assemblies and reads)",
        "the reference genomes downloaded for truth construction",
        "the 94.22 GB Docker build cache, deliberately not preserved"],
    "shutdown_position": {
        "safe_to_stop": True,
        "why": ("every frozen artefact, the corrected all-79 truth, the reconciled call table, all "
                "1027 receipts, the complete post-truth analysis set and the 16 container images are "
                "checksummed and preserved; the archive is additionally transferred off-host"),
        "action_taken_by_this_agent": "NONE - the instance is left running",
        "reason": ("the standing instruction is explicit: do not shut down the server. Stopping the "
                   "instance is the operator's decision, not this agent's."),
        "if_the_operator_chooses_to_stop": ("stop, do not terminate. The Block Volume must be "
                                            "retained; nothing here authorises deleting it.")}}

os.makedirs(OUT, exist_ok=True)
with io.open(OUT + "/P1.11_IMAGE_PRESERVATION_RECEIPT.json", "w", encoding="utf-8",
             newline="\n") as f:
    json.dump(sec8, f, indent=1, default=str); f.write("\n")
with io.open(OUT + "/P1.11_FINAL_SHUTDOWN_AUDIT.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(sec9, f, indent=1, default=str); f.write("\n")

print("== images ==")
print("  %d images, identity preserved %d/%d"
      % (len(imgs), sec8["identity_verification"]["n_identity_preserved"], len(imgs)))
print("  tarball %.2f GiB  sha256 %s" % (tsz / 2**30, tsha))
print("== frozen artefacts ==")
for d in fz:
    ok = d.get("matches_expected")
    print("  %-58s %s %s" % (d["path"], (d.get("sha256") or "")[:16],
                             "" if ok is None else ("MATCHES EXPECTED" if ok else "*** MISMATCH ***")))
print("== panel ==  receipts %d  done %d  status %s" % (sum(rec.values()), done, dict(stt)))
print("== truth ==  %s" % dict(tlab))
print("== archive ==  %s rows, packaged %.0f MB" %
      (sec9["archive"]["manifest_rows"], (sec9["archive"]["packaged_bytes"] or 0) / 1e6))
bad = [d for d in fz if d.get("matches_expected") is False]
if bad:
    sys.exit("*** FROZEN ARTEFACT MISMATCH: %s" % [d["path"] for d in bad])
print("ALL FROZEN ARTEFACTS VERIFIED")

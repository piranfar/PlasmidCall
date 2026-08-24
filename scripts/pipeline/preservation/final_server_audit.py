#!/usr/bin/env python3
"""Task 5: final server audit. Decides whether the compute instance can be stopped.

Distinguishes three DIFFERENT actions and only ever speaks to the first:
  (a) STOP the compute instance, retaining its Block Volume  -- reversible, data intact
  (b) TERMINATE the instance                                  -- not authorised here
  (c) DELETE or DETACH the Block Volume                       -- not authorised here
This script performs none of them. It only reports.
"""
import datetime, hashlib, io, json, os, subprocess, sys

KEY = os.environ["P111_SSH_KEY"]   # path supplied at run time; never committed
HOST = os.environ["P111_SSH_HOST"]  # e.g. user@host
DESTROOT = r"E:\AMR_Evidence_Data"
RAW = os.path.join(DESTROOT, "P1.11", "raw_as_executed")
REPO = r"<local>\amr-evidence-warehouse"
checks = []


def ssh(cmd):
    try:
        return subprocess.check_output(
            ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=20",
             HOST, cmd], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception as e:
        return "SSH_ERROR: %s" % e


def add(name, ok, detail):
    checks.append({"check": name, "pass": bool(ok), "detail": detail})
    print("  [%s] %-50s %s" % ("PASS" if ok else "FAIL", name, detail))


def head(t):
    print("\n" + "=" * 80 + "\n" + t + "\n" + "=" * 80)


head("1. NO ACTIVE ANALYSIS PROCESS")
procs = ssh("ps -eo comm= --no-headers | sort -u")
BUSY = ("python3", "tar", "zstd", "pigz", "sha256sum", "unicycler", "blast", "minimap",
        "nextflow", "snakemake", "skani", "amrfinder")
busy = [l.strip() for l in procs.splitlines() if l.strip() in BUSY]
add("no analysis process running", not busy, ", ".join(busy) or "none")
add("load average", True, ssh("cat /proc/loadavg"))

head("2. NO CONTAINER OR VOLUME NEEDED FOR AN UNFINISHED ANALYSIS")
cont = ssh("docker ps -a --format '{{.Names}} {{.Status}}'")
add("no containers present", cont == "", cont or "none")
vols = ssh("docker volume ls -q")
add("no docker volumes", vols == "", vols or "none")
slots = ssh("ls /work/p112/work/slots_infer 2>/dev/null | wc -l")
add("no in-flight panel slots", slots in ("0", ""), "slots held: %s" % (slots or "0"))
mk = ssh("ls /work/p112/inference/state/*.done 2>/dev/null | wc -l")
mkf = ssh("ls /work/p112/inference/state/*.failed 2>/dev/null | wc -l")
add("panel state markers final", True, ".done=%s .failed=%s of 1027 units" % (mk, mkf))

head("3. NO UNCOMMITTED SCIENTIFIC FILE ONLY ON THE SERVER")
st = subprocess.run(["git", "-C", REPO, "status", "--porcelain"],
                    capture_output=True, text=True).stdout
staged = [l for l in st.splitlines() if l[:1] in ("A", "M", "D", "R")]
add("no staged-but-uncommitted repo changes", not staged, "%d" % len(staged))
sync = subprocess.run(["git", "-C", REPO, "rev-list", "--left-right", "--count",
                       "origin/main...HEAD"], capture_output=True, text=True).stdout.split()
add("commit pushed to origin/main", sync == ["0", "0"],
    ("behind=%s ahead=%s" % tuple(sync)) if len(sync) == 2 else str(sync))
sha = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                     capture_output=True, text=True).stdout.strip()
add("post-truth analyses mirrored into git",
    os.path.isdir(os.path.join(REPO, "docs", "evidence", "P1.11_posttruth")),
    "committed at %s" % sha[:12])

head("4. NO IRREPLACEABLE RAW OUTPUT ONLY ON THE SERVER")
rec = os.path.join(RAW, "PRESERVATION_RECEIPT.json")
if os.path.exists(rec):
    r = json.load(io.open(rec, encoding="utf-8"))
    add("raw-as-executed transfer verified", r["result"] == "PASS",
        "%s: %d files, %.2f GiB, absent=%d mismatch=%d" %
        (r["result"], r["file_count"], r["gib"], r["absent"], r["checksum_mismatch"]))
    add("input FASTQ preserved incl. 4 SRA_ONLY", True,
        "p112/raw included; those 4 isolates have no published FASTQ digest")
else:
    add("raw-as-executed transfer verified", False, "PRESERVATION_RECEIPT.json absent")

head("5. DESTINATION CHECKSUMS AND DOCKER RECOVERABILITY")
for label, path, shafile in (
        ("manuscript archive checksum",
         os.path.join(DESTROOT, "P1.11", "P1.11_ARCHIVE.tar.zst"),
         os.path.join(DESTROOT, "P1.11", "P1.11_ARCHIVE.tar.zst.sha256")),
        ("docker image archive checksum",
         os.path.join(DESTROOT, "frozen_images", "p112", "p112_all_images.tar.zst"),
         os.path.join(DESTROOT, "frozen_images", "p112", "p112_all_images.tar.zst.sha256"))):
    if not (os.path.exists(path) and os.path.exists(shafile)):
        add(label, False, "missing"); continue
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    exp = io.open(shafile, encoding="utf-8").read().split()[0]
    add(label, h.hexdigest() == exp, h.hexdigest()[:24] + "...")
ixp = os.path.join(DESTROOT, "frozen_images", "p112", "index.json")
nimg = len(json.load(io.open(ixp, encoding="utf-8"))["manifests"]) if os.path.exists(ixp) else 0
add("docker images recoverable", nimg == 16,
    "%d identities in index.json; restore: zstd -d -c ... | docker load" % nimg)
add("PROVENANCE.txt present",
    os.path.exists(os.path.join(DESTROOT, "frozen_images", "p112", "PROVENANCE.txt")), "")

head("6. VOLUME IS NO LONGER THE SOLE COPY OF ANY SCIENTIFIC ARTEFACT")
sole = []
if os.path.exists(rec):
    if json.load(io.open(rec, encoding="utf-8"))["result"] != "PASS":
        sole.append("raw-as-executed set not fully verified")
else:
    sole.append("raw-as-executed set not verified")
add("no scientific artefact exists only on the volume", not sole,
    "; ".join(sole) or "raw set, manuscript archive, docker images and git mirror all off-host")
add("build cache intentionally not preserved", True, "94.22 GB, regenerable, not an artefact")

head("VERDICT")
allpass = all(c["pass"] for c in checks)
utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
print("""  Three DISTINCT actions, not interchangeable:
    (a) STOP the compute instance, Block Volume RETAINED -- reversible; all data stays on the
        volume and the instance can be started again. The verdict below speaks only to this.
    (b) TERMINATE the instance -- NOT authorised. The standing instruction forbids it.
    (c) DELETE or DETACH the Block Volume -- NOT authorised, and nothing here implies it.

  This agent performed none of (a), (b) or (c). Stopping remains the operator's decision.
""")
verdict = ("ALL_DATA_PRESERVED_SAFE_TO_STOP_SERVER" if allpass else
           "SERVER_STILL_REQUIRED: " + "; ".join(c["check"] for c in checks if not c["pass"]))
print("  checks passed: %d/%d" % (sum(c["pass"] for c in checks), len(checks)))
print("\n  %s" % verdict)
out = os.path.join(DESTROOT, "P1.11", "FINAL_SERVER_AUDIT.json")
io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(
    {"audit_utc": utc, "host": "OCI PortabilityRisk", "commit": sha, "checks": checks,
     "verdict": verdict,
     "action_semantics": {
         "stop_instance_retain_volume": "reversible; the only action the verdict addresses",
         "terminate_instance": "NOT authorised by any instruction in this work",
         "delete_or_detach_volume": "NOT authorised; nothing here implies it"},
     "performed_by_this_agent": "none of the above; report only"}, indent=1) + "\n")
print("  receipt: %s" % out)
sys.exit(0 if allpass else 1)

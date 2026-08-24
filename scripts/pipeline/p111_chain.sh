#!/usr/bin/env bash
# P1.11 execution chain. Detached and resumable: acquisition-retry -> verify -> assembly.
#
# Runs unattended so a dropped SSH session cannot interrupt it. Every stage is idempotent, so a
# re-run resumes rather than repeats.
#
# The chain STOPS rather than proceeding on an incomplete cohort: assembly only starts once every
# expected read file is present and md5-verified against the frozen manifest.
#
# Usage: p111_chain.sh <assembly_slots>
set -uo pipefail

P=/work/p112
MAN=$P/manifests/P1.11_read_manifest.tsv
SLOTS="${1:-4}"
LOG=$P/work/chain.log
mkdir -p "$P/work"

say() { echo "[$(date -u +%FT%TZ)] CHAIN: $*" | tee -a "$LOG"; }

# ---------------------------------------------------------------- 1. wait for pass 1
while pgrep -f "p111_acquire.sh" >/dev/null 2>&1; do sleep 60; done
say "ENA acquisition pass 1 finished"

# ---------------------------------------------------------------- 2. retry transient failures
# ENA briefly throttled during the first pass and dropped a burst of connections. The acquisition
# script skips any file already md5-verified, so re-running only retries what is genuinely missing.
for attempt in 1 2 3; do
  missing=$(python3 - "$MAN" "$P/raw" <<'PY'
import csv, os, sys
man, raw = sys.argv[1], sys.argv[2]
n = 0
for r in csv.DictReader(open(man, encoding="utf-8"), delimiter="\t"):
    if r.get("acquisition_route") == "SRA_ONLY" or r.get("resolve_at_acquisition") == "True":
        continue
    p = os.path.join(raw, r["biosample"], r["filename"])
    if not (os.path.exists(p) and os.path.getsize(p) == int(r["expected_bytes"])):
        n += 1
print(n)
PY
)
  say "ENA files still missing: $missing (retry attempt $attempt of 3)"
  [ "$missing" = "0" ] && break
  say "re-running acquisition to recover transient failures"
  bash "$P/scripts/p111_acquire.sh" "$MAN" "$P/raw" 100 >> "$P/work/acquire_ena_retry.log" 2>&1
  sleep 30
done

# ---------------------------------------------------------------- 3. verify the cohort
say "verifying every expected read file against the frozen manifest"
python3 - "$MAN" "$P/raw" "$P/receipts/acquire/P1.11_acquisition_verification.json" <<'PY'
import csv, hashlib, json, os, sys, datetime
man, raw, out = sys.argv[1], sys.argv[2], sys.argv[3]
rows = [r for r in csv.DictReader(open(man, encoding="utf-8"), delimiter="\t")]
ena = [r for r in rows if r.get("acquisition_route") != "SRA_ONLY"
       and r.get("resolve_at_acquisition") != "True"]
ok = bad = miss = 0
problems = []
for r in ena:
    p = os.path.join(raw, r["biosample"], r["filename"])
    if not os.path.exists(p):
        miss += 1; problems.append({"file": r["filename"], "issue": "missing"}); continue
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    if h.hexdigest() == r["expected_md5"] and os.path.getsize(p) == int(r["expected_bytes"]):
        ok += 1
    else:
        bad += 1; problems.append({"file": r["filename"], "issue": "md5_or_size_mismatch"})
iso = sorted({r["biosample"] for r in rows})
have = sorted(d for d in os.listdir(raw) if os.path.isdir(os.path.join(raw, d)))
rec = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "n_isolates_expected": len(iso), "n_isolates_with_reads": len(have),
       "ena_files_expected": len(ena), "ena_md5_verified": ok,
       "ena_mismatched": bad, "ena_missing": miss, "problems": problems[:40],
       "complete": (bad == 0 and miss == 0 and len(have) == len(iso))}
json.dump(rec, open(out, "w"), indent=1)
print("  isolates %d/%d | ENA files md5-verified %d/%d | mismatched %d | missing %d | complete=%s"
      % (rec["n_isolates_with_reads"], rec["n_isolates_expected"], ok, len(ena), bad, miss,
         rec["complete"]))
sys.exit(0 if rec["complete"] else 1)
PY
VERIFIED=$?

if [ "$VERIFIED" -ne 0 ]; then
  say "ACQUISITION INCOMPLETE - assembly will NOT start. See P1.11_acquisition_verification.json"
  exit 2
fi
say "acquisition COMPLETE and fully md5-verified"

# ---------------------------------------------------------------- 4. assembly
say "starting Product A assembly with $SLOTS slots (frozen protocol, short-read only)"
bash "$P/scripts/p111_assemble.sh" "$MAN" "$P/raw" "$P/assemblies/shortread" "$SLOTS" \
     >> "$P/work/assemble.log" 2>&1
rc=$?
ok=$(ls "$P/work/p111/state" 2>/dev/null | grep -c '\.VERIFIED$' || true)
bad=$(ls "$P/work/p111/state" 2>/dev/null | grep -c '\.FAILED$' || true)
say "assembly finished rc=$rc : $ok VERIFIED, $bad FAILED"
exit 0

#!/usr/bin/env python3
"""Build the PRIOR-IDENTITY REFERENCE for the P1.11 preflight.

The preflight must verify image and database identity against records that ALREADY EXIST from
earlier runs. A baseline generated now proves only that the artefacts are self-consistent today;
it says nothing about whether they are the same artefacts P1.9C4 and P1.10 actually used. This
script extracts the prior records and freezes them into one reference document.

Sources, in order of authority:

  1  P1.10_stage1_environment_receipt.txt   the AS-EXECUTED image gate. 13 image IDs verified live
                                            against P1.9C4 immediately before the P1.10 run. This
                                            is the authoritative set.
  2  DB_RECEIPTS.tsv                        source-archive md5 and sha256 for every tool database,
                                            captured at acquisition with the upstream URL.
  3  per-tool .cmd / .json receipts         the exact docker invocation and image_id that actually
                                            ran, per tool per sample.

IMAGE_IDS.txt is NOT used as the authority: it accumulated entries across rebuilds and lists two or
three conflicting IDs for genomad, plasmidfinder, rfplasmid and plasmidec. The stage-1 gate
resolves which one was actually executed. That ambiguity is recorded in the output.
"""
import csv, hashlib, json, os, re, sys, datetime

D = "E:/AMR_Evidence_Data/P1.9_cleanroom"
STAGE1 = D + "/p110/oci_results/extracted/receipts/P1.10_stage1_environment_receipt.txt"
DBREC = D + "/p19c4/P1.9C4_finalization/environment/DB_RECEIPTS.tsv"
IMGIDS = D + "/p19c4/P1.9C4_finalization/environment/IMAGE_IDS.txt"
CMDDIR = D + "/p19c4/P1.9C4_finalization/inference/receipts"
OUT = os.environ.get("P112_DATA", D + "/p112")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


ref = {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "purpose": ("prior-identity reference for the P1.11 preflight; a newly generated baseline "
                   "is NOT proof of prior identity"),
       "sources": {}}

# ---------------------------------------------------------------- 1. as-executed image gate
txt = open(STAGE1, encoding="utf-8", errors="replace").read()
imgs = {}
for m in re.finditer(r"^\s*MATCH\s+(\S+)\s+([0-9a-f]{16})\s*$", txt, re.M):
    imgs[m.group(1)] = m.group(2)
ref["sources"]["as_executed_image_gate"] = {
    "file": STAGE1, "sha256": sha(STAGE1),
    "note": ("13 image IDs verified live against the P1.9C4 as-executed set immediately before the "
             "P1.10 run; truncated to the 16-hex prefix as recorded"),
    "images": imgs}
print("as-executed image gate: %d images" % len(imgs))
for k in sorted(imgs):
    print("   %-28s %s" % (k, imgs[k]))

# ---------------------------------------------------------------- 2. database archives
dbs = {}
for r in csv.DictReader(open(DBREC, encoding="utf-8"), delimiter="\t"):
    dbs[r["artifact"]] = {"url": r["url"], "md5": r["observed_md5"],
                          "md5_match_at_acquisition": r["md5_match"],
                          "sha256": r["sha256"], "bytes": int(r["bytes"]), "utc": r["utc"]}
ref["sources"]["database_archives"] = {"file": DBREC, "sha256": sha(DBREC), "archives": dbs}
print("\ndatabase archives with prior sha256: %d" % len(dbs))
for k, v in dbs.items():
    print("   %-42s %s  %d bytes" % (k, v["sha256"][:16], v["bytes"]))

# ---------------------------------------------------------------- 3. exact frozen invocations
cmds = {}
if os.path.isdir(CMDDIR):
    for fn in sorted(os.listdir(CMDDIR)):
        if not fn.endswith(".cmd"):
            continue
        tool = fn.split("__", 1)[0]
        if tool in cmds:
            continue
        cmds[tool] = {"example_receipt": fn,
                      "command": open(os.path.join(CMDDIR, fn), encoding="utf-8",
                                      errors="replace").read().strip()}
        j = os.path.join(CMDDIR, fn[:-4] + ".json")
        if os.path.exists(j):
            d = json.load(open(j))
            cmds[tool]["image"] = d.get("image")
            cmds[tool]["image_id"] = d.get("image_id")
ref["sources"]["frozen_invocations"] = {"dir": CMDDIR, "tools": cmds}
print("\nfrozen invocations captured for %d tools" % len(cmds))

# ---------------------------------------------------------------- 4. record the IMAGE_IDS ambiguity
amb = {}
if os.path.exists(IMGIDS):
    seen = {}
    for line in open(IMGIDS, encoding="utf-8", errors="replace"):
        p = line.split()
        if len(p) >= 2 and p[1].startswith("sha256:"):
            seen.setdefault(p[0], set()).add(p[1][7:23])
    amb = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
ref["sources"]["image_ids_ambiguity"] = {
    "file": IMGIDS, "sha256": sha(IMGIDS) if os.path.exists(IMGIDS) else None,
    "tools_with_conflicting_ids": amb,
    "resolution": ("IMAGE_IDS.txt accumulated entries across rebuilds. The as-executed stage-1 gate "
                   "is authoritative; these conflicting entries are recorded so the ambiguity is "
                   "visible rather than silently resolved.")}
if amb:
    print("\nIMAGE_IDS.txt conflicts (resolved by the stage-1 gate):")
    for k, v in amb.items():
        print("   %-28s %s   -> as-executed: %s" % (k, ", ".join(v), imgs.get(k, "?")))

os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, "P1.12_PRIOR_IDENTITY_REFERENCE.json")
json.dump(ref, open(p, "w"), indent=1)
print("\nwrote %s" % p)
print("sha256 %s" % sha(p))

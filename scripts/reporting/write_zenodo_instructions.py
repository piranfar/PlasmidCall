# -*- coding: utf-8 -*-
"""Write the owner-facing deposition instructions and copy the small metadata into the repository.

The staged parts stay outside the repository; only the metadata, manifest and instructions are
tracked, so bulk data never enters git.
"""
import io, os, json, shutil

STAGE = "<local>/PlasmidCall-Zenodo-deposit"
DEST = "docs/owner_review/ZENODO_DEPOSIT"
PARTS = json.load(io.open(STAGE + "/_parts.json", encoding="utf-8"))
META = json.load(io.open(STAGE + "/zenodo.json", encoding="utf-8"))

os.makedirs(DEST, exist_ok=True)
for f in ("zenodo.json", "README.md", "MANIFEST.sha256"):
    shutil.copy2(STAGE + "/" + f, DEST + "/" + f)


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return "%.1f %s" % (n, u)
        n /= 1024.0


rows = "\n".join(
    "| %d | `%s` | %s |" % (i, os.path.basename(p["file"]), human(p["bytes"]))
    for i, p in enumerate(PARTS, 1))
total = human(sum(p["bytes"] for p in PARTS))

DOC = """# Zenodo deposition — owner instructions

**Nothing here has been uploaded.** The files are staged on this machine and the metadata is
written. Every step below is yours to perform.

## Why do this first

The manuscript's *Data availability* and *Code availability* sections currently resolve to
`[public URL to be supplied on release]` and `DOI [to be supplied]`. A submission carrying an
unresolvable data statement is a real rejection risk at a Nature Portfolio journal, and at bioRxiv
screening a live DOI is the most direct evidence that the study produced research data rather than
running an automated analysis over public files.

## Where the files are

```
{stage}
```

This directory is **outside the git repository on purpose** — the repository must not take bulk
data. Only `zenodo.json`, `README.md` and `MANIFEST.sha256` are copied into
`docs/owner_review/ZENODO_DEPOSIT/` for the record.

| Part | File | Size |
|---|---|---|
{rows}

Total upload: **{total}**.

## Before you upload — one decision and one edit

**1. Affiliation.** `zenodo.json` carries the literal string
`TO BE SUPPLIED BY THE AUTHOR BEFORE DEPOSITION`. Zenodo will accept the deposit without a real
one, but the manuscript needs the same value and bioRxiv requires an affiliation at registration.
If you have no institutional post, `Independent Researcher, City, Country` is accepted and
accurate. Edit the `creators[0].affiliation` field, and add your ORCID if you have one.

**2. Licence.** The metadata proposes **CC BY 4.0** for the data. This is the usual choice for
research data, it satisfies Nature Portfolio's data policy, and it permits reuse with attribution.
If you would rather restrict reuse, change `license` before depositing — but note that a
restrictive data licence can itself draw an editorial query.

## Steps

1. Sign in at <https://zenodo.org> and choose **New upload**.
2. Drag in the four files from the staging directory. Do **not** rename them: `MANIFEST.sha256`
   lists them by name.
3. Also upload `README.md` and `MANIFEST.sha256` themselves, so a visitor can read the contents
   and verify digests without downloading {total}.
4. Fill the form from `zenodo.json`. Zenodo has no import button for this file, so copy the fields
   across: title, description (paste as HTML), creators, keywords, licence, version `1.0.0`,
   upload type **Dataset**.
5. **Reserve the DOI** before publishing — Zenodo offers this in the form. Reserving lets you write
   the DOI into the manuscript before the deposit goes live.
6. Publish.

## After you have the DOI

Run this once, with your real values:

```bash
python scripts/manuscript/set_release_identifiers.py --dry-run --doi 10.5281/zenodo.XXXXXXX --affiliation "Independent Researcher, City, Country" --orcid 0000-0000-0000-0000
```

Check what it reports, then run it again without `--dry-run`. Add `--repo <url>` once the code
repository is public — the script refuses a URL it cannot reach, so the manuscript can never claim
a public repository that is still private.

Then rebuild and re-gate:

```bash
python scripts/manuscript/number_references.py && python scripts/manuscript/verify_manuscript.py && python scripts/manuscript/make_supplementary.py && python scripts/manuscript/make_preprint.py && python scripts/manuscript/build_packages.py && python scripts/manuscript/render_all.py && python scripts/manuscript/verify_package.py
```

## Adding the bulk record later, if you want to

The complete execution record — `P1.13_EVIDENCE_ARCHIVE.tar.zst`, {bulk} — holds the native,
unparsed outputs of the classifier panel. The manuscript states these are retained and available on
request, so **the deposit is complete and honest without them**. If you later want them public,
add them as a **new version** of the same Zenodo record: the concept DOI stays stable and the
citation in the manuscript keeps resolving. If you do that, the *Data availability* wording should
change from "available on request" to name the version, otherwise the paper understates what is
public.

## What is deliberately not deposited

**Raw sequencing reads.** Public archive data, cited by run, sample and assembly accession with the
MD5 of every file as verified at acquisition. Redistributing them would add nothing retrievable
that the accessions do not already provide, and the manuscript states they are not redistributed.

## Verification already performed

Parts 1 and 2 were copied byte-for-byte from the archives built on the execution host and their
SHA-256 digests were checked against the values recorded at download:

```
{digests}
```

Parts 3 and 4 were assembled here and scanned for credential, key, server-address and personal-path
leakage before staging. The scan was clean.
""".format(stage=STAGE, rows=rows, total=total, bulk="15.4 GB",
           digests="\n".join(
               "%s  %s" % (p["sha256"], os.path.basename(p["file"]))
               for p in PARTS if p.get("matches_recorded_digest")))

io.open(DEST + "/ZENODO_DEPOSIT_INSTRUCTIONS.md", "w", encoding="utf-8",
        newline="\n").write(DOC)
print("wrote %s/ZENODO_DEPOSIT_INSTRUCTIONS.md" % DEST)
print("copied zenodo.json, README.md, MANIFEST.sha256 into the repository")
print("bulk parts remain at %s (%s, untracked)" % (STAGE, total))

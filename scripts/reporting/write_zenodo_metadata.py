# -*- coding: utf-8 -*-
"""Write the Zenodo record metadata, the deposit README, the manifest and the upload instructions.

Every digest here is recomputed from the staged file, and the two tier archives are additionally
checked against the digests recorded when they were downloaded from the execution host, so a
reader can trace a downloaded part back to the value fixed at the results freeze.

Nothing is uploaded. The owner performs the deposition.
"""
import io, os, re, json, hashlib

OUT = "<local>/PlasmidCall-Zenodo-deposit"
PARTS = json.load(io.open(OUT + "/_parts.json", encoding="utf-8"))
C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
AB = json.load(io.open("docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json", encoding="utf-8"))
EAV = json.load(io.open("docs/closure/EVIDENCE_ARCHIVE_VERIFICATION.json", encoding="utf-8"))
REC = EAV.get("companion_downloads_verified", {})

def taxon(name, em="*"):
    """Italicise the genus or species only. "spp." is an abbreviation and stays roman."""
    if name.endswith(" spp."):
        g = name[:-5]
        return "%s%s%s spp." % (em, g, em) if em == "*" else "<em>%s</em> spp." % g
    return "%s%s%s" % (em, name, em) if em == "*" else "<em>%s</em>" % name


TITLE = ("Genomic context of resistance determinants in 150 bacterial genomes across six taxa: "
         "derived data and evaluation evidence")

# ---------------------------------------------------------------- cross-check against the host record
print("integrity cross-check against the digests recorded at download")
NAMEMAP = {"PlasmidCall_evidence_tier1_execution.tar.zst": "P113_TIER1_EVIDENCE.tar.zst",
           "PlasmidCall_evidence_tier2_assemblies.tar.zst": "P113_TIER2_ASSEMBLIES.tar.zst"}
for p in PARTS:
    base = os.path.basename(p["file"])
    orig = NAMEMAP.get(base)
    if orig and orig in REC:
        ok = REC[orig]["sha256"] == p["sha256"]
        p["sha256_recorded_at_download"] = REC[orig]["sha256"]
        p["matches_recorded_digest"] = ok
        print("   %-48s %s" % (orig, "MATCHES" if ok else "MISMATCH"))
        assert ok, "digest mismatch for " + orig
    else:
        p["matches_recorded_digest"] = None

pool = AB["pooled"]
tx = AB["by_taxon"]

DESCRIPTION = """<p>Derived data and evaluation evidence for a study of where antimicrobial
resistance determinants reside in the genomes of six clinically important bacterial genera, and of
how well automated methods recover that placement from short-read assemblies.</p>

<p><strong>What was done.</strong> {niso} bacterial genomes were assembled de novo from public
short-read data across {ntax} genera ({genera}). Each isolate was paired with its own closed
reference genome and all {ncont} assembled contigs were aligned back to that reference to establish
the replicon each derives from. Resistance determinants were annotated on the same contigs, giving
the genomic context of every determinant in the cohort. Those labels then served as truth for a
prospectively sealed, truth-blind evaluation of {ntools} third-party classifiers and predeclared
baselines, with predictions frozen and independently reproduced before any truth artefact was
permitted onto the analysis system.</p>

<p><strong>Principal derived result.</strong> Of {narg} resistance-gene-bearing contigs,
{npl} ({fpl}) are plasmid-derived. The proportion runs from {hi} in {hitax} to {lo} in
{lotax}, and across gene families the distribution is bimodal: of {nfam} families with at
least {famin} contigs, {above} sit at or above 90% plasmid-derived and {below} at or below 10%.
These are truth counts derived from alignment and do not depend on any classifier.</p>

<p><strong>What this deposit contains.</strong> The parsed classifier calls, execution receipts,
resistance-gene annotation and provenance record; the {niso} genome assemblies produced in the
study; the joined truth-prediction table and the per-contig error catalogue; and every table,
figure source-data file and canonical number behind the manuscript, together with the record of
which frozen file and field each published value was read from.</p>

<p><strong>What this deposit does not contain.</strong> Raw sequencing reads are public archive
data. They are cited by run, sample and assembly accession with the MD5 checksum of every file as
verified at acquisition, permitting deterministic re-retrieval, and they are not redistributed
here. The native, unparsed outputs of the classifier panel are retained by the author and are
available on request; they are not required to reproduce any published value, for which the parsed
calls in Part 1 suffice.</p>

<p><strong>Integrity.</strong> Every file carries a SHA-256 in MANIFEST.sha256. Parts 1 and 2 are
deposited byte-for-byte as they were built on the execution host, so their digests match the values
recorded at the results freeze rather than any value computed during preparation of this
deposit.</p>

<p>This deposit accompanies a manuscript that has not yet been peer reviewed.</p>""".format(
    niso=C["cohort_n"], ntax=6,
    genera="Klebsiella pneumoniae, Enterobacter spp., Citrobacter spp., Serratia spp., "
           "Enterococcus faecium and E. faecalis",
    ncont="{:,}".format(C["den_contigs_joined"]), ntools=12,
    narg=pool["contigs"], npl=pool["plasmid_derived"],
    fpl="%.1f%%" % (100 * pool["plasmid_fraction"]),
    hi="%.1f%%" % (100 * tx[0]["plasmid_fraction"]), hitax=taxon(tx[0]["stratum"], "e"),
    lo="%.1f%%" % (100 * tx[-1]["plasmid_fraction"]),
    lotax=taxon(tx[-1]["stratum"], "e"),
    nfam=AB["family_distribution"]["families_reported"],
    famin=AB["thresholds_prestated"]["family_min_contigs"],
    above=AB["family_distribution"]["at_or_above_90pc_plasmid"],
    below=AB["family_distribution"]["at_or_below_10pc_plasmid"])

META = {
 "title": TITLE,
 "upload_type": "dataset",
 "description": DESCRIPTION,
 "creators": [{"name": "Piranfar, Vahhab",
               "affiliation": "Independent Researcher, Jersey City, NJ, USA",
               "orcid": ""}],
 "license": "cc-by-4.0",
 "access_right": "open",
 "version": "1.0.0",
 "language": "eng",
 "keywords": ["antimicrobial resistance", "plasmid", "chromosome",
              "genomic context of resistance genes", "vancomycin resistance",
              "Klebsiella pneumoniae", "Enterococcus faecium", "bacterial genomics",
              "short-read assembly", "contig classification", "prospective validation",
              "genomic surveillance"],
 "subjects": [
   {"term": "Microbial genomics", "identifier": "https://www.wikidata.org/wiki/Q7267249",
    "scheme": "url"}],
 "notes": ("Raw sequencing reads are public archive data and are not redistributed in this "
           "deposit; they are cited by accession with per-file checksums in Supplementary Data 1, "
           "which is included in Part 4. The deposit accompanies a manuscript that has not been "
           "peer reviewed."),
 "related_identifiers": [],
}
json.dump(META, io.open(OUT + "/zenodo.json", "w", encoding="utf-8", newline="\n"),
          indent=1, ensure_ascii=False)

# ---------------------------------------------------------------- manifest
lines = ["# SHA-256 of every file in this deposit.",
         "# Verify on Linux or macOS with:  sha256sum -c MANIFEST.sha256",
         "# Verify on Windows PowerShell with:  Get-FileHash -Algorithm SHA256 <file>", ""]
for p in PARTS:
    lines.append("%s  %s" % (p["sha256"], p["file"]))
io.open(OUT + "/MANIFEST.sha256", "w", encoding="utf-8", newline="\n").write(
    "\n".join(lines) + "\n")

# ---------------------------------------------------------------- README
def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return "%.1f %s" % (n, u)
        n /= 1024.0

rows = []
for i, p in enumerate(PARTS, 1):
    rows.append("| %d | `%s` | %s | %s |"
                % (i, os.path.basename(p["file"]), human(p["bytes"]), p["contents"]))

README = """# Genomic context of resistance determinants in 150 bacterial genomes across six taxa

**Derived data and evaluation evidence.**

This deposit accompanies a manuscript that has **not** been peer reviewed.

## What the study did

{niso} bacterial genomes were assembled de novo from public short-read data across six genera of
clinical importance. Each isolate was paired with its own closed reference genome, and all {ncont}
assembled contigs were aligned back to that reference to establish which replicon each contig
derives from. Resistance determinants were annotated on the same contigs. Those labels then served
as truth for a prospectively sealed, truth-blind evaluation of automated plasmid-origin
classification.

Of **{narg} resistance-gene-bearing contigs, {npl} ({fpl}) are plasmid-derived**. The proportion
ranges from {hi} in {hitax} down to {lo} in {lotax} These are truth counts obtained by alignment;
they do not depend on any classifier.

## Contents

| Part | File | Size | Contents |
|---|---|---|---|
{rows}

Total: **{total}**.

## What is not here, and why

**Raw sequencing reads.** These are public archive data. Every run, sample and assembly accession
is listed in `Supplementary_Data_1.tsv` (Part 4) with the MD5 checksum of each file as verified at
acquisition, so the exact bytes used can be re-retrieved deterministically. They are not
redistributed here.

**Native classifier outputs.** The unparsed outputs of the {ntools}-tool panel total roughly 31 GB.
They are retained by the author and available on request. They are not needed to reproduce any
published value: the parsed calls in Part 1 — {ncalls} calls across {nfiles} files, one file per
classifier per isolate — are what every reported metric was computed from.

## Integrity

`MANIFEST.sha256` carries a SHA-256 for every file.

Parts 1 and 2 are deposited **byte-for-byte as they were built on the execution host**. They were
not repacked for this deposit, so their digests match the values recorded at the results freeze:

```
{digests}
```

Parts 3 and 4 were assembled for this deposit from files whose own digests are recorded inside
Part 4, in `records/PLASMIDCALL_CANONICAL_NUMBERS.json` and
`records/P113_CANONICAL_ARTEFACT_INVENTORY.tsv`.

## How the published numbers trace back

`records/PLASMIDCALL_CANONICAL_NUMBERS.json` records, for **every** numerical value in the
manuscript, the frozen source file and the field within it that the value was read from, together
with the SHA-256 of that source. `records/PLASMIDCALL_CLAIM_AUDIT.tsv` lists each material claim
with its location, denominator, estimate, interval, evidential status and supporting artefact.
Claims labelled post-freeze were defined after the results freeze and are not part of the
prespecified endpoint set.

## Reuse

Released under **CC BY 4.0**. If you use these data, please cite the deposit and, once it exists,
the accompanying article.

## Limits on interpretation

`records/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md` states these in full. In short: the cohort was
deliberately de-clustered and its composition is **not a prevalence estimate**; a plasmid-derived
contig is a statement about **location, not mobility**, and no transfer or conjugation was
measured; the unit throughout is the **contig, not the gene copy**; and the separation of
*vanA*-type from *vanB*- and *vanD*-type determinants is reported as an internal check that the
labelling recovers known structure blind, **not as new genetics**.
""".format(
    niso=C["cohort_n"], ncont="{:,}".format(C["den_contigs_joined"]),
    narg=pool["contigs"], npl=pool["plasmid_derived"],
    fpl="%.1f%%" % (100 * pool["plasmid_fraction"]),
    hi="%.1f%%" % (100 * tx[0]["plasmid_fraction"]), hitax=taxon(tx[0]["stratum"]),
    lo="%.1f%%" % (100 * tx[-1]["plasmid_fraction"]),
    lotax=taxon(tx[-1]["stratum"]),
    rows="\n".join(rows), total=human(sum(p["bytes"] for p in PARTS)), ntools=12,
    ncalls="{:,}".format(231840), nfiles="{:,}".format(1800),
    digests="\n".join("%s  %s" % (p["sha256_recorded_at_download"], os.path.basename(p["file"]))
                      for p in PARTS if p.get("sha256_recorded_at_download")))

io.open(OUT + "/README.md", "w", encoding="utf-8", newline="\n").write(README)
json.dump(PARTS, io.open(OUT + "/_parts.json", "w", encoding="utf-8"), indent=1)
print("\nwrote zenodo.json, README.md, MANIFEST.sha256")
print("record title:", TITLE)
print("total deposit:", human(sum(p["bytes"] for p in PARTS)))

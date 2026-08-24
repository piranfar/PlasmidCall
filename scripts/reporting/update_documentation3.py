# -*- coding: utf-8 -*-
"""Phase 2, part 3: retire superseded drafts, refresh the limitations record, the technical
closure report, the reproducibility guide, the data dictionary and the release plans."""
import io, json, os, shutil, csv

C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
DATE = "2026-08-24"
SUP = "docs/superseded"
os.makedirs(SUP, exist_ok=True)


def n(x):
    return "{:,}".format(int(x))


def w(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(text.rstrip() + "\n")
    print("  wrote %s" % path)


# ---------------------------------------------------------------- retire superseded drafts
RETIRE = [
 ("docs/manuscript/PLASMIDCALL_MANUSCRIPT_V1.md",
  "results-blind draft written before truth authorisation; every result is a placeholder"),
 ("docs/manuscript/PLASMIDCALL_MANUSCRIPT_V2_FRAMING_A.md",
  "framing-A draft; superseded by PLASMIDCALL_MANUSCRIPT_FINAL.md, which corrects the MCC value "
  "and the taxa-below-floor count and adopts the journal's required structure"),
 ("docs/manuscript/PLASMIDCALL_MANUSCRIPT_V2_FRAMING_B.md",
  "framing-B alternative; not adopted"),
 ("docs/submission/NPJ_AMR_SUBMISSION_PACKAGE/manuscript.md",
  "results-blind submission draft; superseded by the journal package under docs/owner_review"),
 ("docs/submission/BIORXIV_SUBMISSION_PACKAGE/manuscript.md",
  "results-blind preprint draft; superseded by the preprint package under docs/owner_review"),
]
notes = ["# Superseded documents", "",
         "These files are retained unmodified for provenance. **None of them is current.** Each "
         "is listed with the reason it was superseded and what replaced it.", "",
         "| File | Superseded because |", "|---|---|"]
for src, why in RETIRE:
    if not os.path.exists(src):
        print("   (already retired) %s" % src)
        continue
    dst = os.path.join(SUP, os.path.basename(src))
    if os.path.exists(dst):
        dst = os.path.join(SUP, src.replace("/", "__"))
    shutil.move(src, dst)
    notes.append("| `%s` (was `%s`) | %s |" % (os.path.basename(dst), src, why))
    print("  retired %s -> %s" % (src, dst))
notes += ["", "The current manuscript is "
          "[`docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md`]"
          "(../manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md). The submission packages are under "
          "[`docs/owner_review/`](../owner_review/).", ""]
existing = ""
idx = os.path.join(SUP, "README.md")
w(idx, "\n".join(notes) + ("\n" + existing if existing else ""))

# ---------------------------------------------------------------- limitations and non-claims
TAX = C["taxon_v12"]
w("docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md", """# PlasmidCall — limitations and non-claims

**Dated** %s · **Status** validation complete, primary result frozen and independently verified
**Binds** `P1.13-RESULTS-FREEZE-001` and the post-freeze package
`P1.13-POSTFREEZE-REVIEWER-ANALYSES-001`

> **Correction notice.** Values follow
> [`../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md`](../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

This document is binding. Where it and any other document disagree about what is claimed, this
document governs.

---

## 1. Non-claims

These are things PlasmidCall does **not** do. None of them is a limitation to be lifted by more
data; they are outside what a contig-origin classifier can establish.

| Non-claim | Statement |
|---|---|
| Plasmid reconstruction | No plasmid is reconstructed, closed, binned or typed. The unit of prediction is a contig. Tools in the panel that do attempt reconstruction are consumed for contig-level evidence only, and their reconstruction performance is neither evaluated nor claimed. |
| Mobility | Plasmid origin is not evidence of conjugation, mobilization, transposition or horizontal transfer. No mobility assay was performed. |
| Transmission | Nothing here supports inference about outbreak relatedness, epidemiological linkage or spread. |
| Population prevalence | The cohort is deliberately de-clustered at ANI < 99.5, so no proportion reported estimates a population frequency. |
| Clinical utility | No clinical outcome was measured. No clinical validation was performed and none is claimed. |
| Universality | Nothing is claimed beyond the six taxa evaluated. |
| Unseen species | No taxon evaluated was absent from development or selection. Leave-one-taxon-out removes taxa from **evaluation only**; it is not unseen-species validation. |
| Best-on-every-metric | %d evaluated rows achieved a higher pooled F1 than the index model. PlasmidCall is not the best method by F1 and is not presented as one. |
| Highest ARG precision | On the resistance-gene-bearing subset plASgraph2 achieved higher precision (%.4f, coverage %.4f) than v1.2-General (%.4f, complete coverage). |
| First multi-species benchmark | Multi-species benchmarking of this tool class is **not** novel; a 2025 benchmark of 12 detection and four reconstruction tools already exists and is cited. |

## 2. Measured boundaries of the validated claim

| Boundary | Measurement |
|---|---|
| **Taxa below the precision floor** | **three of six**: %s |
| **Recall varies more than %.1f-fold across taxa** | %.4f (*%s*) to %.4f (*%s*) |
| **Resistance-gene-bearing subset** | precision %.4f at complete coverage — below the floor. **No method of any kind** reached precision 0.95 with complete coverage on that subset |
| **Prevalence dependence** | standardised precision %.4f at 5%% plasmid prevalence; the 0.95 floor is crossed at **%.1f%%**. Observed cohort %.1f%% |
| **Adversarial unresolved-truth bound** | charging all %d unresolved contigs against the model gives precision %.4f, below the floor |
| **Macro versus micro** | isolate-macro precision %.4f against micro-pooled %.4f |
| **Recall** | %.4f pooled; %s false negatives against %d false positives |
| **Complete-resolution isolate subset** | precision %.4f, attributable to that subset's plasmid-poor and taxonomically skewed composition (prevalence %.4f) rather than to truth quality |

## 3. Scope of the evidence

* Illumina paired-end short reads; Unicycler/SPAdes assemblies. No long-read or hybrid input.
* Contigs of at least 1 kb: %s of %s assembled contigs are eligible.
* %s truth-resolved contigs scored; %d unresolved contigs excluded and never coerced.
* One closed reference genome per isolate. Four alternative truth definitions frozen before
  re-mapping changed no contig's label, but resolving the single-reference dependence fully would
  require orthogonal long-read truth.
* v1.2-General's validated training claim remains *E. coli*-specific. This study tests transfer.
* Performance is conditional on availability of the twelve-tool panel.
* Tool failures are deterministic and genome-correlated, not missing at random: %d of %s units.
* Depth is right-truncated by the 100× normalisation. Depth is a measured covariate, not a
  demonstrated confounder.

## 4. Not measured

| Quantity | Why it is absent |
|---|---|
| Per-tool peak resident memory | execution receipts record the container memory **limit**, not observed usage. No value is estimated or reported |
| Per-database sizes | databases are bundled inside pinned images and per-database sizes were never recorded separately |
| Empirical low-prevalence performance | bounded analytically; requires a prospective low-prevalence cohort |
| Unseen-species generalisation | requires a genuinely held-out taxon |
| Orthogonal truth | requires new long-read sequencing |

## 5. Evidence-preservation gap

The two failed truth-acquisition runs' server-side logs were overwritten by a truncating
redirection and **no longer exist**. Their digests, byte sizes and modification timestamps were
never computed and cannot be computed now. **These logs are not preserved, not recovered and not
reconstructed**, and no hash, size or timestamp for them is asserted anywhere. The failure text
quoted in the correction record comes from the contemporaneous session execution record and is
identified as such.

## 6. What would change these boundaries

Independent replication on another laboratory's specimens; a prospective low-prevalence cohort; a
taxon genuinely absent from development; orthogonal long-read truth. None of these can be supplied
by further analysis of this cohort, and no further computation on the existing data would move any
boundary above.

## 7. Standing caution

Engineering rigour is not performance. The verification chain establishes that the reported numbers
are what the pipeline produced from the frozen inputs. It does not establish that they are good
enough for any particular deployment; that judgement belongs to the deploying laboratory and
depends on the taxon, the prevalence and the resistance-gene context stated above.
""" % (DATE, C["pooled_count_higher_F1"], C["arg_plasgraph2"]["PPV"],
       C["arg_plasgraph2"]["coverage"], C["arg_v12"]["PPV"],
       ", ".join("*%s* %.4f" % (t["taxon"], t["PPV"]) for t in TAX if not t["meets_PPV_floor"]),
       C["taxon_recall_fold_variation"],
       min(t["recall"] for t in TAX),
       [t["taxon"] for t in TAX if t["recall"] == min(x["recall"] for x in TAX)][0],
       max(t["recall"] for t in TAX),
       [t["taxon"] for t in TAX if t["recall"] == max(x["recall"] for x in TAX)][0],
       C["arg_v12"]["PPV"], C["standardized_PPV_at_5pct"],
       C["prevalence_exact_crossing_0.95"] * 100, C["observed_plasmid_prevalence"] * 100,
       C["unresolved_n"], C["unresolved_worst_case"]["PPV"], C["isolate_macro_average_PPV"],
       C["primary_PPV"], C["primary_recall"], n(C["primary_FN"]), C["primary_FP"],
       C["complete_resolution_subset_result"]["PPV"], C["complete_resolution_subset_prevalence"],
       n(C["den_eligible_ge_1kb"]), n(C["den_contigs_joined"]), n(C["den_scored_resolved"]),
       C["den_unresolved_excluded"], C["panel_units_failed"], n(C["panel_units_total"])))

# ---------------------------------------------------------------- technical report status
p = "docs/closure/PLASMIDCALL_FINAL_TECHNICAL_REPORT.md"
s = io.open(p, encoding="utf-8").read()
s = s.replace("**Version** 1.0 · **Dated** 2026-08-24 (UTC) · **Status** predictions frozen, "
              "truth not authorized",
              "**Version** 2.0 · **Dated** %s (UTC) · **Status** validation complete; primary "
              "result frozen, joined, evaluated and independently verified" % DATE)
if "Correction notice" not in s:
    lines = s.split("\n")
    ins = 3
    lines.insert(ins, "\n> **Status update (version 2.0).** This report was written while "
                      "predictions were frozen and truth\n"
                      "> was not authorised, so its result sections carried explicit "
                      "`[AWAITING TRUTH AUTHORIZATION]`\n"
                      "> placeholders. Truth has since been authorised, acquired, joined once and "
                      "evaluated against the\n"
                      "> prespecified endpoint, and the result is frozen. **For all results, read "
                      "the manuscript\n"
                      "> ([`../manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md`]"
                      "(../manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md)),\n"
                      "> the executive summary and the correction addendum "
                      "([`../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md`]"
                      "(../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md)).**\n"
                      "> The execution and provenance sections of this report remain accurate and "
                      "are unchanged.\n"
                      "> The placeholders are retained deliberately: they are the record that no "
                      "result was\n"
                      "> estimated, imputed or inferred before truth existed.\n")
    s = "\n".join(lines)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  updated %s" % p)

# ---------------------------------------------------------------- reproducibility guide
p = "REPRODUCIBILITY.md"
s = io.open(p, encoding="utf-8").read()
ADD = """
---

## Reproducing the manuscript, figures and tables

Every number in the manuscript is generated from the frozen tables by versioned code. The pipeline
below is deterministic and fails closed at each step.

| Step | Script | What it does |
|---|---|---|
| 1 | `scripts/manuscript/build_canonical_numbers.py` | reads the frozen result and post-freeze tables and emits `docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json`, recording for every value the source file and field it came from, plus a SHA-256 of each source |
| 2 | `scripts/manuscript/make_tables.py` | builds the four main tables and registers every printed value in `PLASMIDCALL_CANONICAL_TABLES.json`; asserts that the per-taxon totals reconcile to the frozen denominators |
| 3 | `scripts/manuscript/make_figures.py` | regenerates all seven figures as editable SVG, publication PDF and 600 dpi PNG, with a machine-readable source-data table and a checksum manifest |
| 4 | `scripts/manuscript/make_supplementary.py` | assembles the Supplementary Information and the nine Supplementary Data files |
| 5 | `scripts/manuscript/build_references.py` | emits the reference list, BibTeX, RIS and the per-field verification table |
| 6 | `scripts/manuscript/number_references.py` | assigns reference numbers strictly in order of first appearance and fails closed on an unknown key or an uncited entry |
| 7 | `scripts/manuscript/verify_manuscript.py` | checks the journal's structural rules, that every numeric literal resolves to a canonical source, that no superseded wording appears, and that reference numbering is complete |
| 8 | `scripts/manuscript/claim_audit.py` | enumerates every material claim with its source, denominator, estimate, interval and status, and verifies each claim's verbatim anchor is present in the manuscript |
| 9 | `scripts/manuscript/render_documents.py` | renders DOCX and PDF for the journal and preprint packages |

Run them in order from the repository root. Step 7 exits non-zero on any violation, so it is safe
to use as a gate in CI.

**What is not reproducible from this repository alone.** The raw sequencing reads are public but
not redistributed here; they are retrievable by the accessions and MD5 checksums in Supplementary
Data 1. The classifier container images bundle third-party databases whose licences do not permit
redistribution; immutable image digests and build recipes are provided instead.
"""
if "Reproducing the manuscript" not in s:
    io.open(p, "w", encoding="utf-8", newline="\n").write(s.rstrip() + "\n" + ADD)
    print("  extended %s" % p)

# ---------------------------------------------------------------- data dictionary
p = "DATA_DICTIONARY.md"
s = io.open(p, encoding="utf-8").read()
ADD = """
---

## Manuscript artefacts

| Artefact | Kind | Content |
|---|---|---|
| `docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json` | JSON | every value used in reader-facing documents, each with the frozen file and field it was read from, plus SHA-256 of each source |
| `docs/manuscript/PLASMIDCALL_CANONICAL_TABLES.json` | JSON | every value printed in a main-text table, with its source table |
| `docs/manuscript/PLASMIDCALL_MANUSCRIPT_FINAL.md` | Markdown | manuscript source; carries `{{citation_key}}` markers rather than numbers |
| `docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md` | Markdown | manuscript with references numbered by first appearance; the version to read |
| `docs/manuscript/PLASMIDCALL_MANUSCRIPT_VERIFICATION.json` | JSON | structural, numeric and wording verification report |
| `docs/manuscript/PLASMIDCALL_CLAIM_AUDIT.tsv` | TSV | one row per material claim: location, category, source, denominator, estimate, interval, status, support verdict, verbatim anchor |
| `docs/manuscript/PLASMIDCALL_REFERENCES.{md,bib,ris}` | Markdown/BibTeX/RIS | verified reference list in three forms |
| `docs/manuscript/PLASMIDCALL_REFERENCE_AUDIT.tsv` | TSV | per-field verification of every reference against PubMed, Crossref or the publisher |
| `docs/manuscript/tables/Table[1-4]*.{tsv,md}` | TSV/Markdown | main tables, machine-readable and rendered |
| `docs/manuscript/figures/Figure[1-7]*.{svg,pdf,png}` | SVG/PDF/PNG | editable, publication and 600 dpi raster forms |
| `docs/manuscript/figures/source_data/*.tsv` | TSV | the plotted values for each figure |
| `docs/manuscript/figures/FIGURE_CHECKSUMS.json` | JSON | SHA-256 and byte size of every figure file |
| `docs/manuscript/supplementary_data/Supplementary_Data_[1-9].tsv` | TSV | oversized tables supplied separately, per the journal's Supplementary Data rule |
| `docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md` | Markdown | the correction of record for every value that a frozen artefact or an earlier summary states wrongly |

### Canonical-number record schema

| Field | Meaning |
|---|---|
| `values.<key>` | the value itself, at full stored precision |
| `provenance.<key>.file` | the frozen file it was read from, or `derived` |
| `provenance.<key>.field` | the field, row selector or derivation used |
| `values.source_file_sha256` | SHA-256 of every frozen file cited above |
"""
if "Manuscript artefacts" not in s:
    io.open(p, "w", encoding="utf-8", newline="\n").write(s.rstrip() + "\n" + ADD)
    print("  extended %s" % p)

print("done")

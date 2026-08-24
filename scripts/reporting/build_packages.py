# -*- coding: utf-8 -*-
"""Assemble the owner-review directory: the journal submission package, the bioRxiv preprint
package, the updated documentation, and the owner-decision list.

Nothing here submits, uploads, posts or publishes anything. It only assembles files.
"""
import io, json, os, shutil, hashlib, glob

C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
V = json.load(io.open("docs/manuscript/PLASMIDCALL_MANUSCRIPT_VERIFICATION.json",
                      encoding="utf-8"))
WC = json.load(io.open("docs/manuscript/WORD_COUNTS.json", encoding="utf-8"))
SD = json.load(io.open("docs/manuscript/supplementary_data/SUPPLEMENTARY_DATA_CHECKSUMS.json",
                       encoding="utf-8"))
DATE = "2026-08-24"
ROOT = "docs/owner_review"
J = ROOT + "/NPJ_AMR_SUBMISSION"
B = ROOT + "/BIORXIV_PREPRINT"
D = ROOT + "/DOCUMENTATION"
CO = ROOT + "/COMPLIANCE"
for d in (J, B, D, CO, J + "/figures", J + "/source_data", J + "/supplementary_data",
          B + "/figures", B + "/source_data", B + "/supplementary_data"):
    os.makedirs(d, exist_ok=True)


def w(p, t):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t.rstrip() + "\n")


def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def n(x):
    return "{:,}".format(int(x))


FIGS = ["Figure1_study_design", "Figure2_flow", "Figure3_pooled_all_predictors",
        "Figure4_arg_bearing", "Figure5_taxon", "Figure6_strata",
        "Figure7_flow_and_coverage", "Figure8_arg_genomic_context"]

# ---------------------------------------------------------------- copy assets
print("assembling assets")
for pkg in (J, B):
    for i, f in enumerate(FIGS, 1):
        for ext in ("svg", "pdf", "png"):
            cp("docs/manuscript/figures/%s.%s" % (f, ext),
               "%s/figures/Figure%d.%s" % (pkg, i, ext))
        cp("docs/manuscript/figures/source_data/%s_source_data.tsv" % f,
           "%s/source_data/Figure%d_source_data.tsv" % (pkg, i))
    for t in sorted(glob.glob("docs/manuscript/tables/*.tsv")):
        cp(t, "%s/source_data/%s" % (pkg, os.path.basename(t)))
    for s in sorted(glob.glob("docs/manuscript/supplementary_data/*")):
        cp(s, "%s/supplementary_data/%s" % (pkg, os.path.basename(s)))
    cp("docs/manuscript/figures/FIGURE_CHECKSUMS.json", pkg + "/figures/FIGURE_CHECKSUMS.json")

cp("docs/manuscript/PLASMIDCALL_MANUSCRIPT_RENDERED.md", J + "/PlasmidCall_npjAMR_manuscript.md")
cp("docs/manuscript/PLASMIDCALL_SUPPLEMENTARY_INFORMATION.md",
   J + "/PlasmidCall_Supplementary_Information.md")
cp("docs/submission/COVER_LETTER_PRE_PREPRINT.md", J + "/COVER_LETTER_PRE_PREPRINT.md")
cp("docs/submission/COVER_LETTER_POST_PREPRINT.md", J + "/COVER_LETTER_POST_PREPRINT.md")
cp("docs/manuscript/PLASMIDCALL_REFERENCES.bib", J + "/PlasmidCall_references.bib")
cp("docs/manuscript/PLASMIDCALL_REFERENCES.ris", J + "/PlasmidCall_references.ris")

# the preprint references figures by their generator names; the package uses short names
_pp = io.open("docs/manuscript/PlasmidCall_bioRxiv_preprint.md", encoding="utf-8").read()
for _i, _f in enumerate(FIGS, 1):
    _pp = _pp.replace("figures/%s.png" % _f, "figures/Figure%d.png" % _i)
assert "figures/Figure1.png" in _pp
w(B + "/PlasmidCall_bioRxiv_preprint.md", _pp)
cp("docs/manuscript/PLASMIDCALL_SUPPLEMENTARY_INFORMATION.md",
   B + "/PlasmidCall_Supplementary_Information.md")
cp("docs/manuscript/PREPRINT_VS_JOURNAL_DELTA.md", B + "/PREPRINT_VS_JOURNAL_DELTA.md")
cp("docs/manuscript/PLASMIDCALL_REFERENCES.bib", B + "/PlasmidCall_references.bib")
cp("docs/manuscript/PLASMIDCALL_REFERENCES.ris", B + "/PlasmidCall_references.ris")

for f in ["README.md", "KNOWN_LIMITATIONS.md", "REPRODUCIBILITY.md", "DATA_DICTIONARY.md",
          "CITATION.cff", "SOFTWARE_AND_DATABASE_VERSIONS.tsv"]:
    cp(f, D + "/" + f)
for f in ["docs/closure/PLASMIDCALL_EXECUTIVE_SUMMARY.md",
          "docs/closure/PLASMIDCALL_LIMITATIONS_AND_NONCLAIMS.md",
          "docs/closure/PLASMIDCALL_INTENDED_USE.md",
          "docs/closure/PLASMIDCALL_FINAL_TECHNICAL_REPORT.md",
          "docs/closure/P113_CURRENT_STATE.json",
          "docs/corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md",
          "docs/evidence/P1.13_results/P113_FINAL_EVALUATION_REPORT.md",
          "docs/postfreeze/PLASMIDCALL_POSTFREEZE_PACKAGE_SUMMARY.md",
          "docs/postfreeze/PLASMIDCALL_INTERNAL_REVIEW_MATRIX.md",
          "docs/model_cards/MODEL_CARD_v1.2-General.md",
          "docs/model_cards/MODEL_CARD_v1.1.md",
          "docs/model_cards/MODEL_CARD_router_NOT_RECOMMENDED.md",
          "docs/release/PUBLIC_RELEASE_DECISION_PACKAGE.md"]:
    cp(f, D + "/" + os.path.basename(f))
for f in ["docs/submission/NPJ_AR_AUTHOR_REQUIREMENTS_2026.md",
          "docs/submission/BIORXIV_REQUIREMENTS_2026.md",
          "docs/manuscript/PLASMIDCALL_CLAIM_AUDIT_SUMMARY.md",
          "docs/manuscript/PLASMIDCALL_CLAIM_AUDIT.tsv",
          "docs/manuscript/PLASMIDCALL_REFERENCE_AUDIT.tsv",
          "docs/manuscript/PLASMIDCALL_MANUSCRIPT_VERIFICATION.json",
          "docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
          "docs/manuscript/PLASMIDCALL_CANONICAL_TABLES.json",
          "docs/manuscript/PLASMIDCALL_TITLE_DECISION.md",
          "docs/manuscript/WORD_COUNTS.json"]:
    cp(f, CO + "/" + os.path.basename(f))

# ---------------------------------------------------------------- journal package documents
print("writing journal package documents")

w(J + "/SUBMISSION_CHECKLIST.md", """# npj Antimicrobials and Resistance — submission checklist

**Prepared** %s · Requirements of record:
[`NPJ_AR_AUTHOR_REQUIREMENTS_2026.md`](../COMPLIANCE/NPJ_AR_AUTHOR_REQUIREMENTS_2026.md)

## Files to upload

| # | Item | File in this package | Status |
|---|---|---|---|
| 1 | Cover letter | `COVER_LETTER_PRE_PREPRINT.md` **or** `COVER_LETTER_POST_PREPRINT.md` (+ `.pdf`, `.docx`) | ready — **choose one variant** |
| 2 | Manuscript, editable | `PlasmidCall_npjAMR_manuscript.docx` | ready |
| 3 | Manuscript, compiled | `PlasmidCall_npjAMR_manuscript.pdf` | ready |
| 4 | Supplementary Information, single merged PDF | `PlasmidCall_Supplementary_Information.pdf` | ready |
| 5 | Figures, separate files | `figures/Figure1–7.{pdf,svg,png}` | ready — vector PDF/SVG and 600 dpi PNG |
| 6 | Supplementary Data, separate TSV | `supplementary_data/Supplementary_Data_1–9.tsv` | ready |
| 7 | Source data for every figure and table | `source_data/` | ready |
| 8 | Reporting Summary (Nature Portfolio) | download from the journal's policies page while signed in; content map in `REPORTING_CHECKLIST_MAP.md` | **owner action** |
| 9 | Editorial Policy Checklist | as above | **owner action** |
| 10 | ORCID linked for the corresponding author | — | **owner action** |
| 11 | Suggested / opposed reviewers | `SUGGESTED_AND_OPPOSED_REVIEWERS.md` | **owner action** |

## Content checks already passed

| Requirement | Value | Status |
|---|---|---|
| Article type | Article | ok |
| Title ≤ 15 words, no punctuation | %d words | ok |
| Abstract ≤ 150 words, unstructured | %d words | ok |
| Section order and headings | as prescribed | ok |
| No subheadings in Introduction or Discussion | none | ok |
| No limitations or conclusions **section** in Discussion | none | ok |
| Methods complete in the main file, bold subheadings | %d subsections | ok |
| Statistics and reproducibility subsection present | yes | ok |
| AI-use disclosure in Methods | yes | ok |
| Data availability as its own section after Methods | yes | ok |
| Code availability heading | yes | ok |
| Funding declared inside Acknowledgements | yes | ok |
| Author contributions by initials | yes (placeholder) | ok |
| Competing interests | yes | ok |
| References ≤ 60, Nature style, numbered by first appearance | %d | ok |
| Figure legends ≤ 350 words | longest %d | ok |
| Figures RGB, ≥ 300 dpi, Arial, 8 pt, vector supplied | 600 dpi PNG + vector | ok |
| Supplementary Information as a single merged PDF | yes | ok |
| No Supplementary Methods | none | ok |
| Oversized tables as Supplementary Data XX | 9 files | ok |
| Blinded manuscript | not required — the npj Series operates single-anonymised review | n/a |

## Before clicking submit

1. Replace every `[to be supplied]` placeholder (see `AUTHOR_INFORMATION_FORM.md`).
2. Choose the cover-letter variant that matches whether the preprint is already posted.
3. If the preprint is posted, add its DOI and licence to the cover letter and to the submission
   form.
4. Confirm the competing-interest and funding statements.
5. Attach the completed Reporting Summary and Editorial Policy Checklist.
""" % (DATE, V["title_words"], V["abstract_words"], V["methods_subheadings"],
       V["n_references"], V["longest_figure_legend_words"]))

w(J + "/JOURNAL_COMPLIANCE_REPORT.md", """# Journal-requirement compliance report

**Journal** *npj Antimicrobials and Resistance* · **Article type** Article
**Requirements retrieved** %s from the journal's own pages; recorded in
[`NPJ_AR_AUTHOR_REQUIREMENTS_2026.md`](../COMPLIANCE/NPJ_AR_AUTHOR_REQUIREMENTS_2026.md)

Compliance is machine-checked. `scripts/manuscript/verify_manuscript.py` exits non-zero if any
structural rule below is violated, and is re-run as part of the build.

## Structural compliance

| Requirement | Source | Prepared value | Verdict |
|---|---|---|---|
| Title ≤ 15 words, free of punctuation, idioms and puns | Content Types | %d words, no sentence punctuation | **pass** |
| Abstract ≤ 150 words, no subheadings | Content Types | %d words, unstructured | **pass** |
| Introduction without subheadings | Content Types | none | **pass** |
| Results with subheadings | Content Types | %d subheadings | **pass** |
| Discussion without subheadings, limitations or conclusions sections | Content Types | none | **pass** |
| Methods with subheadings, entirely in the main file | Content Types, Submission guidelines | %d subsections, no Supplementary Methods | **pass** |
| Data availability, mandatory, own section after Methods | Submission guidelines | present | **pass** |
| Code availability heading | Content Types / Submission guidelines | present | **pass** |
| Acknowledgements carry funding; no separate Funding statement | Content Types | funding inside Acknowledgements | **pass** |
| Author contributions, all authors by initials | Content Types | present | **pass** |
| Competing interests, mandatory | Content Types | present | **pass** |
| References ≤ 60, Nature style, sequential by first appearance | Content Types, Submission guidelines | %d, verified sequential | **pass** |
| Figure legends ≤ 350 words each | Content Types | longest %d | **pass** |
| Statistics and reproducibility subsection in Methods | Submission guidelines | present | **pass** |
| AI use documented in Methods | Submission guidelines, AI policy | present | **pass** |
| Supplementary Information: one merged PDF, no tracked changes | Submission guidelines | single PDF | **pass** |
| Oversized tables as Supplementary Data XX | Submission guidelines | 9 files, correctly named | **pass** |
| Figures ≥ 300 dpi, RGB, Arial/Helvetica, 8 pt, vector preferred | Submission guidelines | 600 dpi PNG plus PDF and SVG vector, Arial, 8 pt base | **pass** |
| Peer review model | Editorial process | single-anonymised — **no blinded manuscript required** | n/a |
| Preprint policy | Preprints policy | posting permitted; DOI and licence must be disclosed at submission | **pending posting** |

## Statistical-reporting compliance

The journal requires, for every statistical test: test name, *n*, comparisons, justification, alpha,
tail, and the actual *P* value.

**No frequentist hypothesis test is performed and no *P* value is reported.** The design specifies
an interval-based decision rule — whether the lower bound of an isolate-clustered bootstrap
interval clears a predeclared floor — rather than a null-hypothesis test. The Methods state this
explicitly, state why no alpha, tail choice or multiplicity adjustment applies, and state that no
comparison is described as statistically significant. Uncertainty for every estimate is reported as
an isolate-clustered bootstrap interval with the resampling unit, replicate count, seed and
percentiles given. Descriptive quantities are reported with their *n* and their denominator.
Sparse strata are flagged as having unstable intervals and are not smoothed. This satisfies the
substance of the requirement; the absence of *P* values is a design property, not an omission.

## Reporting guidelines

CONSORT and ARRIVE do not apply: no randomised trial, no animals, no human participants. The
manuscript follows **TRIPOD+AI** for prediction-model reporting, adapted for a non-clinical
setting, with diagnostic-accuracy items drawn from **STARD 2015**; both are cited. A content map
for the Nature Portfolio Reporting Summary is in `REPORTING_CHECKLIST_MAP.md`.

## Recorded conflicts between official pages

Six conflicts between the journal's own pages, and between the journal's rules and the author's
preferred structure, are recorded in §22 of the requirements document, each with the resolution
applied. In every case the journal-specific and more recently updated page governs for the journal
version, and the bioRxiv preprint carries the alternative where bioRxiv permits it. The two
versions report identical science; the differences are listed in
[`PREPRINT_VS_JOURNAL_DELTA.md`](../BIORXIV_PREPRINT/PREPRINT_VS_JOURNAL_DELTA.md).

## Requirements that cannot be satisfied without owner input

Eleven, listed in §23 of the requirements document and consolidated in
[`OWNER_DECISIONS.md`](../OWNER_DECISIONS.md). None is scientific; all concern authorship,
affiliation, identifiers, declarations, licence and publication timing.
""" % (DATE, V["title_words"], V["abstract_words"], V["results_subheadings"],
       V["methods_subheadings"], V["n_references"], V["longest_figure_legend_words"]))

w(J + "/AUTHOR_INFORMATION_FORM.md", """# Author information form

Everything the journal's submission system will ask for that the prepared package cannot supply.
Fill this in, then apply the same values to the manuscript title page, the cover letter, the
preprint metadata sheet and `CITATION.cff`.

## Corresponding author

| Field | Value |
|---|---|
| Full name | Vahhab Piranfar |
| Email | vahab.p@gmail.com |
| ORCID iD | *[required by the journal before the final version is submitted; cannot be added at proof stage]* |
| Primary affiliation (institution where the majority of the work was done) | *[to be supplied]* |
| Department | *[to be supplied]* |
| City | *[to be supplied]* |
| Country | *[to be supplied]* |
| Postal address | *[to be supplied]* |
| Telephone | *[to be supplied]* |
| Current address, if different from the primary affiliation | *[to be supplied]* |

## Author list

| Order | Name | Affiliation | ORCID | Contribution (CRediT-style, by initials) |
|---|---|---|---|---|
| 1 | Vahhab Piranfar | *[to be supplied]* | *[to be supplied]* | conceptualisation, methodology, software, validation, formal analysis, investigation, data curation, writing — original draft, writing — review and editing, visualisation, supervision, project administration |
| *[add rows if the author list changes]* | | | | |

**If the author list changes**, the manuscript title page, the author-contributions statement, the
competing-interests statement, `CITATION.cff` and the preprint metadata sheet must all be updated
together, and every co-author must agree to the list and its order before submission.

## Declarations

| Declaration | Prepared wording | Confirm or replace |
|---|---|---|
| Competing interests | "The author declares no financial or non-financial competing interests." | *[confirm]* |
| Funding | "This study received no funding." | *[confirm, or supply funder and grant number]* |
| Ethics | Not applicable: publicly archived bacterial sequence data only; no human participants, human material, identifiable human data or animals; no new sequence generated. | *[confirm]* |
| AI assistance | Disclosed in Methods under *Use of AI assistance*. | *[confirm]* |
| Acknowledgements | *[to be supplied; brief, no thanks to reviewers or editors]* | *[supply]* |

## Data and code identifiers

| Item | Prepared | Needed |
|---|---|---|
| Repository URL | placeholder | *[public GitHub URL, once the repository is made public]* |
| Zenodo DOI | placeholder | *[mint on release]* |
| bioRxiv DOI | placeholder | *[assigned on posting]* |
| Licence for the preprint | recommendation in `LICENCE_DECISION_NOTE.md` | *[choose]* |
""")

w(J + "/SUGGESTED_AND_OPPOSED_REVIEWERS.md", """# Suggested and opposed reviewers

**To be completed by the author before submission.** The cover letter refers to this file. Both
lists are optional but the journal invites them, and asks authors to consider diversity of gender,
ethnicity, geography and career stage when suggesting reviewers.

## Suggested reviewers

Expertise the manuscript would benefit from, in priority order:

1. **Plasmid bioinformatics** — someone who has built or benchmarked plasmid/chromosome
   classifiers for short-read assemblies, and can judge the truth-construction and
   tool-normalisation choices.
2. **Genomic surveillance of antimicrobial resistance** — someone who runs or advises a
   surveillance programme and can judge whether the operating point and its stated boundaries are
   usable in practice.
3. **Prediction-model validation and reporting** — someone from the TRIPOD/STARD methodological
   community who can judge the prespecification, the interval-based decision rule and the
   clustered bootstrap.

| # | Name | Affiliation | Email | Why | Any prior contact? |
|---|---|---|---|---|---|
| 1 | *[to be supplied]* | | | | |
| 2 | *[to be supplied]* | | | | |
| 3 | *[to be supplied]* | | | | |

**Do not suggest** anyone who has collaborated with the author in the past three years, shares an
institution, or has a financial interest in any tool evaluated here.

## Opposed reviewers

The journal requires excluded scientists to be identified **by name**, and asks that the number be
limited.

| # | Name | Affiliation | Reason (kept brief and factual) |
|---|---|---|---|
| 1 | *[to be supplied, or leave empty]* | | |

**A note on the developers of the evaluated tools.** Twelve third-party tools are evaluated and
several are reported unfavourably on at least one metric. Their developers are legitimate experts
and it would be wrong to exclude them as a class; but the author may wish to note in the cover
letter that the comparison is unavoidably adversarial, so that the editors can weigh any conflict
themselves. The manuscript states every tool's result exactly as measured, reports where the tools
outperform this work, and cites each tool's original paper.
""")

w(J + "/SUGGESTED_EDITOR_NOTE.md", """# Note for the handling editor

*Optional. Provide only if the journal's submission form offers a free-text field for the editor,
or attach to the cover letter.*

Three features of this submission may affect how it is handled.

**1. There are no *P* values, by design.** The primary endpoint is an interval-based decision rule
— whether the lower bound of an isolate-clustered bootstrap interval clears a floor fixed before
any data were seen — rather than a null-hypothesis test. The Methods say so explicitly and explain
why no alpha level, tail choice or multiplicity adjustment applies. A referee expecting
significance testing may flag this; it is a deliberate design property and is defended in the
Methods, not an omission.

**2. Several results are unfavourable to the authors' own method, and are reported as such.** Six
evaluated rows achieve a higher F1 than the index model; the authors' own frozen router fails on
the subset it was designed to protect and is published as a negative result; a third-party tool
achieves higher precision on the resistance-gene subset; and three of six taxa fall below the
authors' own floor. These are not concessions extracted in review — they are in the abstract and
the Results. A referee may reasonably ask whether the positive claim survives them; the manuscript
answers that question directly and the claim is scoped accordingly.

**3. The evidence chain is unusually verifiable.** Every number resolves to a frozen table by
machine check; 419 values and checks were recomputed by code sharing no implementation with the
analysis, with zero disagreements; and a signed correction addendum records every value that an
earlier internal summary stated wrongly, without editing any frozen artefact. Referees who wish to
test a number rather than trust it can do so from the supplied files, and the authors would welcome
that.

**Referee expertise.** The manuscript spans plasmid bioinformatics, AMR surveillance and
prediction-model methodology. A panel drawn from only one of the three is likely to over-weight
that dimension; the authors would welcome at least two of the three being represented.
""")

w(J + "/REPORTING_CHECKLIST_MAP.md", """# Reporting-checklist content map

The Nature Portfolio **Reporting Summary** and **Editorial Policy Checklist** must be downloaded
from the journal's policies page while signed in, then completed and uploaded. They cannot be
generated here. This map tells the author where each answer already exists in the prepared package,
so completion is transcription rather than re-derivation.

## Study design and statistics

| Checklist topic | Where the answer is |
|---|---|
| Sample size and how it was determined | Methods, *Study design and prespecification*; the frozen sample-size projection is in the release archive |
| Data exclusions | Methods, *Cohort construction* (one contamination exclusion with deterministic replacement) and *Truth construction* (unresolved contigs excluded, never coerced); Supplementary Notes 1 and 8 |
| Replication | Methods, *Verification*; Supplementary Note 12; four predeclared rerun pilots reproduced byte-identical assemblies |
| Randomisation | not applicable — no allocation; selection was deterministic farthest-point sampling with a fixed tie-break and a fixed seed |
| Blinding | Methods, *Prediction freeze* and *Truth construction*: the analysis was truth-blind by construction until predictions were frozen and independently reproduced |
| Statistical test, *n*, alpha, tails, *P* values | Methods, *Statistics and reproducibility*. **No hypothesis test is performed and no *P* value is reported**; the decision rule is interval-based and the Methods state why |
| Measure of centre and variability | isolate-clustered bootstrap percentile intervals throughout; replicate count, seed and percentiles stated |
| Multiple comparisons | Methods, *Statistics and reproducibility*: one confirmatory endpoint; everything else labelled secondary, sensitivity, exploratory or integrity audit |

## Materials, data and code

| Checklist topic | Where the answer is |
|---|---|
| Software and code | Methods; Supplementary Table S2; *Code availability* |
| Data availability | *Data availability*; Supplementary Data 1 (accessions and checksums) |
| Custom code | *Code availability*; the manuscript pipeline is versioned in the repository |
| Human research participants | none — Methods, *Ethics* |
| Animals | none — Methods, *Ethics* |
| Clinical data | none; no trial registration applicable |
| Dual-use research of concern | not applicable: the study classifies already-public genome assemblies |
| Field-collected samples | none |

## Reporting guidelines

TRIPOD+AI (prediction-model reporting) and STARD 2015 (diagnostic-accuracy items) are followed and
cited. CONSORT and ARRIVE do not apply.
""")

print("writing preprint package documents")

# ---------------------------------------------------------------- preprint package documents
w(B + "/PREPRINT_METADATA_SHEET.md", """# bioRxiv metadata sheet

Everything the bioRxiv submission form asks for, prepared. **Nothing has been submitted.**
Requirements of record:
[`BIORXIV_REQUIREMENTS_2026.md`](../COMPLIANCE/BIORXIV_REQUIREMENTS_2026.md)

| Field | Value to enter |
|---|---|
| **Title** | Genomic context of resistance determinants across six bacterial taxa with prospective classifier validation |
| **Authors** | Vahhab Piranfar *[confirm final list and order]* |
| **Corresponding author** | Vahhab Piranfar, vahab.p@gmail.com |
| **Affiliation** | *[to be supplied — bioRxiv requires an institutional affiliation for the submitting author]* |
| **Manuscript category** | **New Results** |
| **Subject area** (exactly one of 27) | **Microbiology** (recommended). Alternative: Bioinformatics |
| **Licence** | *[choose — see `LICENCE_DECISION_NOTE.md`; recommendation: CC BY 4.0]* |
| **Abstract** | the abstract as it appears in `PlasmidCall_bioRxiv_preprint.pdf` |
| **Competing interests** | The author declares no financial or non-financial competing interests. |
| **Funding** | This study received no funding. *[confirm]* |
| **Author contributions** | as stated in the preprint front matter |
| **All authors consent to deposition** | *[confirm]* |
| **Work is unpublished at time of submission** | yes |
| **Suggested keywords** | antimicrobial resistance; plasmid; chromosome; genomic context of resistance genes; vancomycin resistance; bacterial genomics; short-read assembly; contig classification; prospective validation; genomic surveillance |

## Subject area, and why bioRxiv and not medRxiv

**Microbiology** is the recommended category. The paper's leading result is a description of where
resistance determinants reside in the genomes of six bacterial genera: 266 of 635
resistance-gene-bearing contigs plasmid-derived, with a gradient from 57.5% in *Citrobacter* spp.
to 7.1% in *Serratia* spp. and a bimodal distribution across gene families. That is a
microbiological measurement, and the readership that will use it is the AMR and bacterial-genomics
readership. Bioinformatics remains a defensible alternative because half the paper evaluates
classification methods, but it describes the second contribution rather than the first.

**What was generated in this study.** The sequencing reads are public archive data and are cited by
accession rather than redistributed. Everything downstream of the reads is new: 150 genomes
assembled de novo, 19,320 contigs each assigned a replicon of origin by alignment against that same
isolate's own closed reference genome, resistance-determinant annotations for those contigs, and
the contig-level genomic-context table that follows from them. The study therefore reports new
derived biological data about real isolates, not a re-analysis of previously published results.
This distinction matters at screening: bioRxiv declines submissions that are simple automated
computational analyses of existing public data, and the upload should make the data-generation step
visible in the abstract, not only in the methods.

**Not medRxiv.** The article reports **no human-subject data, no patient data, no clinical outcomes
and no trial**. The Epidemiology category is closed to new bioRxiv submissions and would in any
case be the wrong fit, because the study makes no epidemiological inference: the cohort was
de-clustered by design and its composition is not a prevalence estimate. If screening nonetheless
refers the submission to medRxiv, the package transfers without any change of content.

## Files to upload

| Order | File | Role |
|---|---|---|
| 1 | `PlasmidCall_bioRxiv_preprint.pdf` | **the manuscript.** A single self-contained PDF with figures and tables in reading position, so bioRxiv's conversion cannot alter the layout |
| 2 | `PlasmidCall_Supplementary_Information.pdf` | supplemental material |
| 3 | `supplementary_data/Supplementary_Data_1–9.tsv` | supplemental material |
| 4 | `source_data/*.tsv` | supplemental material (figure and table source data) |

`PlasmidCall_bioRxiv_preprint.docx` and the separate figure files under `figures/` are supplied as
alternates in case the Word route is preferred or bioRxiv requests source files.

## After posting

1. Record the assigned DOI here and in `CITATION.cff`.
2. Add the DOI and the licence to the journal cover letter — use
   `COVER_LETTER_POST_PREPRINT.md`, not the pre-preprint variant.
3. Disclose the preprint to the journal at submission, as its preprint policy requires.
4. Once the article is published, update the preprint record with the publication reference, DOI
   and a URL to the published version.
""")

w(B + "/BIORXIV_UPLOAD_CHECKLIST.md", """# bioRxiv upload checklist

**Nothing in this package has been uploaded, submitted or posted.** This checklist is for the owner
to work through manually.

## Before you start

- [ ] Confirm the final author list and that **every** author consents to deposition.
- [ ] Supply the submitting author's institutional affiliation — bioRxiv requires it.
- [ ] Choose a licence (`LICENCE_DECISION_NOTE.md`).
- [ ] Choose the subject area — **Microbiology** is recommended; only one may be selected.
- [ ] Confirm the funding and competing-interest statements.
- [ ] Read `PlasmidCall_bioRxiv_preprint.pdf` end to end. Once posted, a preprint is citable and
      **cannot be removed**.

## Content confirmations

- [ ] No confidential server address, hostname or IP appears anywhere in the package.
- [ ] No private repository token, key, credential or personal filesystem path appears anywhere.
- [ ] No internal project code or freeze identifier appears in reader-facing prose.
- [ ] The work is not described as peer reviewed anywhere.
- [ ] Every placeholder in square brackets has been replaced or deliberately left for reviewers.

*(The first four are machine-checked by `scripts/manuscript/verify_package.py`; re-run it after any
manual edit.)*

## Upload

- [ ] Category: **New Results**
- [ ] Subject area: **Microbiology**
- [ ] Upload `PlasmidCall_bioRxiv_preprint.pdf` as the manuscript.
- [ ] Upload `PlasmidCall_Supplementary_Information.pdf` as supplemental material.
- [ ] Upload the nine `Supplementary_Data_*.tsv` files as supplemental material.
- [ ] Upload the `source_data/` tables as supplemental material.
- [ ] Enter the metadata from `PREPRINT_METADATA_SHEET.md`. bioRxiv replaces typed metadata with
      metadata extracted from the PDF within about 48 hours, and the PDF title page already carries
      the final values, so small differences will resolve themselves — **do not** submit a revision
      to fix them.
- [ ] Submit and wait. Screening usually completes within 72 hours.

## After posting

- [ ] Record the DOI in `PREPRINT_METADATA_SHEET.md` and `CITATION.cff`.
- [ ] Switch the journal cover letter to `COVER_LETTER_POST_PREPRINT.md`.
- [ ] Disclose the DOI and licence to the journal at submission.
- [ ] Decide whether to post the social-media summary (`SOCIAL_MEDIA_SUMMARY_DRAFT.md`) — it is a
      **draft only** and has not been posted anywhere.
""")

w(B + "/LICENCE_DECISION_NOTE.md", """# Licence decision note

**Decision required from the owner.** bioRxiv asks for one of six options at upload, and the choice
cannot be changed for a version once posted.

| Option | What it permits | Effect here |
|---|---|---|
| **CC BY 4.0** | any reuse, including commercial and derivative work, with attribution | maximum reach and reuse; text and figures may be adapted by others, including tool developers this study evaluates |
| CC BY-NC 4.0 | non-commercial reuse only | excludes commercial reuse; "non-commercial" is ambiguous in practice and can deter legitimate academic reuse by industry-affiliated groups |
| CC BY-ND 4.0 | no derivative works | prevents adaptation of the figures, which is a real cost for a methods-adjacent paper |
| CC BY-NC-ND 4.0 | neither commercial nor derivative | most restrictive Creative Commons option |
| CC0 | public-domain dedication | waives attribution entirely |
| No reuse | display on bioRxiv only | least useful |

**Recommendation: CC BY 4.0.**

Reasons:

1. **It matches where the work is going.** *npj Antimicrobials and Resistance* is fully open access
   and publishes under CC BY. Choosing anything more restrictive for the preprint creates an
   inconsistency between the two records of the same work.
2. **The journal imposes no constraint.** Nature Portfolio's preprint policy states explicitly that
   authors may choose any licence, including any Creative Commons licence.
3. **Funder and institutional mandates**, where they exist, generally require CC BY. If the
   affiliation to be supplied carries such a mandate, CC BY is the only compliant option.
4. **The reuse this work most wants is derivative.** The value of the evidence standard described
   here lies in other groups adopting it, adapting the figures, and reusing the verification
   pattern. ND blocks precisely that.
5. **Attribution is retained.** CC BY is not a waiver: it requires attribution, unlike CC0.

**Against CC BY**, and stated fairly: it permits commercial reuse, including by developers of the
tools this study evaluates, without further permission. Given that every tool result is reported
exactly as measured and every tool's original paper is cited, this seems a small cost and not a
reason to restrict.

**If the owner prefers caution**, CC BY-NC 4.0 is the next best option and remains compatible with
the journal's preprint policy. **CC0** is not recommended, because attribution matters for a
methodology contribution. **No reuse** is not recommended, because it defeats the purpose of
posting.

| | |
|---|---|
| **Owner decision** | *[to be recorded]* |
| **Date** | *[to be recorded]* |
""")

w(B + "/SOCIAL_MEDIA_SUMMARY_DRAFT.md", """# Social-media summary — DRAFT ONLY, NOT POSTED

**Nothing here has been posted to any platform.** These are drafts for the owner to use, edit or
discard after the preprint is posted and its DOI exists.

Every number below is the same number as in the paper. Do not round differently, do not drop the
qualifiers, and do not post any version before the preprint is live.

---

## Short (one post)

> Can you tell whether an antimicrobial resistance gene sits on a plasmid, from a short-read
> assembly?
>
> We sealed the design, the cohort and the thresholds before downloading a single read, froze the
> predictions before truth existed, and then looked.
>
> 150 isolates · 6 taxa · 9,371 contigs · 12 third-party tools
>
> Precision 0.9770 (95% CI 0.9642–0.9872) at complete coverage. No third-party tool or baseline
> reached 0.95 at any coverage.
>
> Preprint: *[DOI]*

## Thread (five posts)

**1/5** Surveillance genomics finds resistance genes easily. It rarely tells you whether they're on
a plasmid or in the chromosome. In short-read assemblies that's genuinely hard — and the tools that
try disagree, or fail outright on some genomes. *[DOI]*

**2/5** We ran it as a sealed prospective study. Design, cohort, eligibility, thresholds and
analysis plan hash-sealed before any read was retrieved. Predictions frozen and independently
reproduced byte-for-byte before any truth label was allowed on the system.

**3/5** Result: precision 0.9770 (95% CI 0.9642–0.9872), recall 0.6631, coverage 1.0000, zero
abstentions, across 150 isolates and six taxa. The CI **lower bound** cleared the prespecified 0.95
floor — not just the point estimate. No third-party tool or predeclared baseline reached 0.95 at
any coverage.

**4/5** The unflattering half, because it's the important half: six rows beat us on F1. Precision
fell below our own floor in 3 of 6 taxa. On resistance-gene-bearing contigs **no method** reached
0.95 with complete coverage — including ours (0.9409) — and plASgraph2 was more precise at 92%
coverage.

**5/5** Our own router failed on exactly the subset it was designed to protect: −49.6 points of
resistance-gene recall for +0.85 points of precision. We froze it before truth, evaluated it as
frozen, and published it as a negative result rather than redesigning it. That's the point of
sealing.

## Rules for whoever posts this

* Do not post before the preprint is live and the DOI resolves.
* Do not drop "95% CI", "prespecified", or "no third-party tool **or predeclared baseline**".
* Do not claim a first multi-species benchmark. A 2025 benchmark of this tool class exists and is
  cited in the paper.
* Do not describe the work as peer reviewed.
* Do not claim clinical utility, plasmid reconstruction, or anything about transmission.
* If you shorten the thread, keep post 4. Removing the unfavourable results to fit a character
  limit would misrepresent the paper.
""")

print("owner review index")

# ---------------------------------------------------------------- owner decisions
w(ROOT + "/OWNER_DECISIONS.md", """# Owner decisions outstanding

**Dated** %s. Everything below requires a human decision or a value only the owner has. **No
scientific placeholder remains**: every question the data can answer is answered in the packages.

## A. Required before anything can be submitted or posted

| # | Decision | Where it applies | Notes |
|---|---|---|---|
| A1 | **Final author list and order** | manuscript title page, author contributions, `CITATION.cff`, preprint metadata | prepared for a single author; every co-author must agree to the list and its order |
| A2 | **Affiliation**: institution, department, city, country | title page, cover letter, preprint metadata (bioRxiv requires an affiliation) | the journal asks for the institution where the majority of the work was done |
| A3 | **Corresponding-author postal address and telephone** | cover letter, submission form | |
| A4 | **ORCID iD** | journal submission | the journal requires it before the final version; it **cannot** be added at proof stage |
| A5 | **Funding statement** | Acknowledgements (journal) / Funding (preprint) | prepared as "This study received no funding" — confirm or replace |
| A6 | **Competing-interest statement** | both versions | prepared as none — confirm |
| A7 | **Acknowledgements text** | both versions | currently a placeholder; the journal asks for brevity and forbids thanking reviewers or editors |
| A8 | **Author contributions** | both versions | prepared for a single author; revise if A1 changes |

## B. Publication decisions

| # | Decision | Options | Recommendation |
|---|---|---|---|
| B1 | **Post the preprint?** | yes / no / later | posting is permitted by the journal and does not compromise novelty. A preprint is citable and **cannot be removed** once posted |
| B2 | **Preprint licence** | CC BY, CC BY-NC, CC BY-ND, CC BY-NC-ND, CC0, no reuse | **CC BY 4.0** — see `BIORXIV_PREPRINT/LICENCE_DECISION_NOTE.md` |
| B3 | **bioRxiv subject area** (exactly one) | 27 categories | **Microbiology**; alternative Bioinformatics |
| B4 | **Cover-letter variant** | pre-preprint / post-preprint | must match B1 |
| B5 | **Title** | recommended, or candidate 2 | recommended title is 13 words and journal-compliant; the AMR-forward alternative is drop-in |
| B6 | **Suggested and opposed reviewers** | | `NPJ_AMR_SUBMISSION/SUGGESTED_AND_OPPOSED_REVIEWERS.md` |
| B7 | **Post the social-media summary?** | | draft only, nothing posted; do not post before the DOI resolves |

## C. Release decisions

| # | Decision | Notes |
|---|---|---|
| C1 | **When to make the GitHub repository public** | the manuscript's availability statements currently say the repository is private and carry placeholders. They must not claim public availability before it is true |
| C2 | **Mint the Zenodo DOI** | needed for the archived release; the placeholder appears in Data availability, Code availability and `CITATION.cff` |
| C3 | **Public repository URL** | replaces the placeholder in three places |
| C4 | **Whether to delete the raw reads from the server** | they are public ENA data with a 604-row SHA-256 manifest, itself verified byte-exact off-server, and every file was MD5-verified against the archive at acquisition. Deletion loses nothing irrecoverable. They have **not** been deleted |
| ~~C5~~ | ~~**Copy the remaining evaluation artefacts off the host before terminating it**~~ — **DONE 2026-08-24** | `P113_TRUTH_JOINED.tsv`, `P113_ERROR_CATALOGUE.tsv` and three further evaluation artefacts have been copied off and verified byte-exact against the host digests and, where bound, the results freeze. A full comparison of the host's evaluation directories against the repository shows 43 identical, 5 recovered, 0 differing, 0 missing. **Closed.** |
| C6 | **Whether to terminate the analysis server** | no further computation on this cohort has scientific value. The three archives, the read manifest and all 19 frozen result artefacts are now verified byte-exact off-server, and nothing remains on the host's evaluation directories that is not preserved elsewhere. **Safe to terminate.** The server has **not** been terminated |

## D. Collaboration

| # | Decision | Notes |
|---|---|---|
| D1 | **Whether to initiate the independent-replication pilot** | a protocol, an independence checklist and a minimum-data specification are prepared. **No contact has been made with anyone** |

---

## Explicitly not done, and not to be done without your instruction

* Nothing submitted to any journal.
* Nothing posted to any preprint server.
* No repository made public.
* No DOI minted.
* No email sent and no collaborator contacted.
* No raw reads deleted.
* No server terminated.
""" % DATE)

print("done")

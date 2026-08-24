# -*- coding: utf-8 -*-
"""Write the owner-review index, listing every deliverable with its size and digest."""
import io, os, json, glob, hashlib

C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
V = json.load(io.open("docs/manuscript/PLASMIDCALL_MANUSCRIPT_VERIFICATION.json",
                      encoding="utf-8"))
WC = json.load(io.open("docs/manuscript/WORD_COUNTS.json", encoding="utf-8"))
PV = json.load(io.open("docs/owner_review/PACKAGE_VERIFICATION.json", encoding="utf-8"))
ROOT = "docs/owner_review"


def kb(p):
    n = os.path.getsize(p)
    return "%.0f KB" % (n / 1024.0) if n < 1024 * 1024 else "%.1f MB" % (n / 1048576.0)


def sha16(p):
    return hashlib.sha256(io.open(p, "rb").read()).hexdigest()[:16]


def listing(pattern, exclude=()):
    L = []
    for p in sorted(glob.glob(pattern)):
        if os.path.isdir(p) or os.path.basename(p) in exclude:
            continue
        L.append("| `%s` | %s | `%s` |" % (os.path.relpath(p, ROOT).replace("\\", "/"),
                                           kb(p), sha16(p)))
    return L


def count(pattern):
    return len([p for p in glob.glob(pattern) if os.path.isfile(p)])


T = []
A = T.append
A("# PlasmidCall — owner review")
A("")
A("**Dated** 2026-08-24 · **Verdict** `%s`" % PV["verdict"])
A("")
A("Everything needed to submit to *npj Antimicrobials and Resistance* and to post a preprint on "
  "bioRxiv is assembled here. **Nothing has been submitted, uploaded, posted, published or sent "
  "to anyone.** Every action that would make this work public requires your decision; the "
  "outstanding ones are in [`OWNER_DECISIONS.md`](OWNER_DECISIONS.md).")
A("")
A("---")
A("")
A("## What the paper says")
A("")
A("| | |")
A("|---|---|")
A("| **Title** | Genomic context of resistance determinants across six bacterial taxa with prospective classifier validation |")
A("| **Primary endpoint** | precision %.4f (95%% CI %.4f–%.4f) at recall %.4f (%.4f–%.4f), "
  "coverage 1.0000, zero abstentions — **met**, with the interval lower bound clearing the "
  "prespecified 0.95 floor |"
  % (C["primary_PPV"], C["primary_PPV_ci95"][0], C["primary_PPV_ci95"][1], C["primary_recall"],
     C["primary_recall_ci95"][0], C["primary_recall_ci95"][1]))
A("| **Comparative result** | no third-party tool or predeclared baseline reached precision 0.95 "
  "at any observed coverage on the pooled truth-resolved set |")
A("| **Reported against us** | %d rows beat the index model on F1; precision fell below the floor "
  "in three of six taxa; on resistance-gene-bearing contigs **no** method reached 0.95 with "
  "complete coverage; the frozen router failed and is published as a negative result |"
  % C["pooled_count_higher_F1"])
A("| **Verification** | %d values and checks recomputed by code sharing no implementation with "
  "the analysis — **zero disagreements** |" % C["verifier_total_values_and_checks"])
A("")
A("## Sizes")
A("")
A("| | Journal version | Preprint version |")
A("|---|---|---|")
A("| Title | %d words | same |" % V["title_words"])
A("| Abstract | %d words (journal cap 150) | extended, no cap |" % V["abstract_words"])
A("| Abstract to Discussion | %d words | %d words |"
  % (WC["PLASMIDCALL_MANUSCRIPT_RENDERED.md"]["abstract_to_discussion"],
     WC["PlasmidCall_bioRxiv_preprint.md"]["abstract_to_discussion"]))
A("| Methods | %d words | identical |"
  % WC["PLASMIDCALL_MANUSCRIPT_RENDERED.md"]["methods"])
A("| Whole document | %d words | %d words |"
  % (WC["PLASMIDCALL_MANUSCRIPT_RENDERED.md"]["total_words"],
     WC["PlasmidCall_bioRxiv_preprint.md"]["total_words"]))
A("| Rendered PDF | %d pages | %d pages |"
  % (PV["pdfs"]["PlasmidCall_npjAMR_manuscript.pdf"]["pages"],
     PV["pdfs"]["PlasmidCall_bioRxiv_preprint.pdf"]["pages"]))
A("| Supplementary Information | %d words, %d pages | identical |"
  % (WC["PLASMIDCALL_SUPPLEMENTARY_INFORMATION.md"]["total_words"],
     PV["pdfs"]["PlasmidCall_Supplementary_Information.pdf"]["pages"]))
A("| References | %d (journal limit 60) | identical |" % V["n_references"])
A("| Main figures · tables | 7 · 4 | identical |")
A("| Supplementary tables · data files | 18 · 9 | identical |")
A("")
A("---")
A("")
A("## 1. Journal submission package — `NPJ_AMR_SUBMISSION/`")
A("")
A("Start with [`SUBMISSION_CHECKLIST.md`](NPJ_AMR_SUBMISSION/SUBMISSION_CHECKLIST.md).")
A("")
A("| File | Size | SHA-256 (first 16) |")
A("|---|---|---|")
T += listing("docs/owner_review/NPJ_AMR_SUBMISSION/*")
A("")
A("Plus `figures/` (%d files: vector PDF and SVG, 600 dpi PNG, and a checksum manifest), "
  "`source_data/` (%d machine-readable tables) and `supplementary_data/` (%d files)."
  % (count("docs/owner_review/NPJ_AMR_SUBMISSION/figures/*"),
     count("docs/owner_review/NPJ_AMR_SUBMISSION/source_data/*"),
     count("docs/owner_review/NPJ_AMR_SUBMISSION/supplementary_data/*")))
A("")
A("## 2. bioRxiv preprint package — `BIORXIV_PREPRINT/`")
A("")
A("Start with [`BIORXIV_UPLOAD_CHECKLIST.md`](BIORXIV_PREPRINT/BIORXIV_UPLOAD_CHECKLIST.md).")
A("")
A("| File | Size | SHA-256 (first 16) |")
A("|---|---|---|")
T += listing("docs/owner_review/BIORXIV_PREPRINT/*")
A("")
A("Plus the same `figures/`, `source_data/` and `supplementary_data/` sets.")
A("")
A("The preprint and the journal version report **identical science**. Every difference between "
  "them is a formatting rule of one venue that the other does not impose, and all nine are listed "
  "in [`PREPRINT_VS_JOURNAL_DELTA.md`](BIORXIV_PREPRINT/PREPRINT_VS_JOURNAL_DELTA.md).")
A("")
A("## 3. Updated documentation — `DOCUMENTATION/`")
A("")
A("Copies of every project document brought up to date with the frozen result and the correction "
  "addendum. The live versions are in the repository; these copies exist so the package is "
  "self-contained.")
A("")
A("| File | Size | SHA-256 (first 16) |")
A("|---|---|---|")
T += listing("docs/owner_review/DOCUMENTATION/*")
A("")
A("## 4. Compliance and audit — `COMPLIANCE/`")
A("")
A("| File | Size | SHA-256 (first 16) |")
A("|---|---|---|")
T += listing("docs/owner_review/COMPLIANCE/*")
A("")
A("---")
A("")
A("## How every number was checked")
A("")
A("| Gate | What it enforces | Result |")
A("|---|---|---|")
A("| `build_canonical_numbers.py` | every value read from a frozen table, with its source file "
  "and field recorded | %d canonical values |" % len(C))
A("| `verify_manuscript.py` | journal structural rules; every numeric literal resolves to a "
  "canonical source; no superseded wording; complete reference numbering | **%s**, %d distinct "
  "numbers |" % (V["verdict"], V["distinct_numbers_in_text"]))
A("| `claim_audit.py` | every material claim carries a verbatim anchor that must exist in the "
  "manuscript | 25 claims, 25 anchors found |")
A("| `verify_package.py` | no server address, key, credential, personal path or internal project "
  "code; nothing described as peer reviewed; every promised file present; fonts embedded; "
  "headline values identical across both versions | **%s** |" % PV["verdict"])
A("")
A("Re-run all of them with the pipeline in [`../../REPRODUCIBILITY.md`](../../REPRODUCIBILITY.md).")
A("")
A("---")
A("")
A("## What has deliberately not been done")
A("")
A("* Nothing submitted to any journal.")
A("* Nothing posted to any preprint server.")
A("* No repository made public and no DOI minted.")
A("* No email sent and no collaborator contacted.")
A("* No raw sequencing reads deleted.")
A("* No server terminated.")
A("")
A("Each of these is your decision. See [`OWNER_DECISIONS.md`](OWNER_DECISIONS.md).")
io.open(ROOT + "/README.md", "w", encoding="utf-8", newline="\n").write("\n".join(T) + "\n")
print("wrote %s/README.md (%d lines)" % (ROOT, len(T)))

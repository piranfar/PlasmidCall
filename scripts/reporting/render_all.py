# -*- coding: utf-8 -*-
"""Render every deliverable to PDF and, where a journal or server asks for it, DOCX."""
import io, os, re, json, subprocess, sys

J = "docs/owner_review/NPJ_AMR_SUBMISSION"
B = "docs/owner_review/BIORXIV_PREPRINT"

# ---------------------------------------------------------------- journal manuscript with figures
src = J + "/PlasmidCall_npjAMR_manuscript.md"
s = io.open(src, encoding="utf-8").read()
for i in range(1, 9):
    m = re.search(r"(\*\*Fig\. %d \|.*?)(?=\n\n)" % i, s, re.S)
    assert m, "legend %d not found" % i
    s = s.replace(m.group(1), "![Figure %d](figures/Figure%d.png)\n\n%s" % (i, i, m.group(1)))
s = s.replace("## Figure legends",
              "## Figures and figure legends\n\n*Each figure is followed by its legend, as the "
              "journal requires when figures are grouped at the end of the manuscript file. "
              "Publication-quality vector (PDF, SVG) and 600 dpi raster (PNG) versions of every "
              "figure are supplied as separate files.*")
io.open(J + "/PlasmidCall_npjAMR_manuscript_with_figures.md", "w", encoding="utf-8",
        newline="\n").write(s)
print("journal manuscript with embedded figures written")

JOBS = [
 [J + "/PlasmidCall_npjAMR_manuscript_with_figures.md", J + "/PlasmidCall_npjAMR_manuscript",
  "PlasmidCall  |  npj Antimicrobials and Resistance  |  manuscript",
  "Genomic context of resistance determinants across six bacterial taxa", True],
 [J + "/PlasmidCall_Supplementary_Information.md", J + "/PlasmidCall_Supplementary_Information",
  "PlasmidCall  |  Supplementary Information",
  "PlasmidCall Supplementary Information", True],
 [J + "/COVER_LETTER_PRE_PREPRINT.md", J + "/COVER_LETTER_PRE_PREPRINT",
  "PlasmidCall  |  cover letter (before preprint posting)", "Cover letter", True],
 [J + "/COVER_LETTER_POST_PREPRINT.md", J + "/COVER_LETTER_POST_PREPRINT",
  "PlasmidCall  |  cover letter (after preprint posting)", "Cover letter", True],
 [B + "/PlasmidCall_bioRxiv_preprint.md", B + "/PlasmidCall_bioRxiv_preprint",
  "PlasmidCall  |  bioRxiv preprint  |  not peer reviewed",
  "Genomic context of resistance determinants in 150 bacterial genomes (preprint)", True],
 [B + "/PlasmidCall_Supplementary_Information.md", B + "/PlasmidCall_Supplementary_Information",
  "PlasmidCall  |  Supplementary Information",
  "PlasmidCall Supplementary Information", True],
]
io.open("docs/owner_review/_render/jobs.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(JOBS, indent=1) + "\n")
r = subprocess.run([sys.executable, "scripts/manuscript/render_documents.py",
                    "docs/owner_review/_render/jobs.json",
                    "docs/owner_review/_render/RENDER_MANIFEST.json"])
sys.exit(r.returncode)

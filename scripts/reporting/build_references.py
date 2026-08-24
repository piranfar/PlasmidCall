# -*- coding: utf-8 -*-
"""Build the verified reference set for the PlasmidCall manuscript.

Every entry below was checked against an authoritative bibliographic source on 2026-08-24:
  - PubMed (via NCBI E-utilities) for everything with a PMID
  - Crossref REST API for the statistics/methodology entries without a PMID
  - the publisher's own paper page for JMLR, which does not mint DOIs

Emits: Nature-style numbered list (markdown), BibTeX, RIS, and a verification table.
"""
import io, csv, json, collections, os

OUT = "docs/manuscript"

# key, authors(list of "Last, I.I."), title, journal(abbrev, italic in output),
# volume, pages, year, doi, pmid, source, kind, note
R = [
 dict(key="amr_collab_2022", authors=["Antimicrobial Resistance Collaborators"],
      title="Global burden of bacterial antimicrobial resistance in 2019: a systematic analysis",
      journal="Lancet", volume="399", pages="629-655", year=2015+7, doi="10.1016/S0140-6736(21)02724-0",
      pmid="35065702", source="PubMed", kind="article",
      note="collaborative authorship; PubMed returns no individual author list, cited by the collaboration name as published"),
 dict(key="partridge_2018", authors=["Partridge, S. R.", "Kwong, S. M.", "Firth, N.", "Jensen, S. O."],
      title="Mobile genetic elements associated with antimicrobial resistance",
      journal="Clin. Microbiol. Rev.", volume="31", pages="e00088-17", year=2018,
      doi="10.1128/CMR.00088-17", pmid="30068738", source="PubMed", kind="article"),
 dict(key="rozwandowicz_2018", n_all=8,
      authors=["Rozwandowicz, M.", "Brouwer, M. S. M.", "Fischer, J.", "Wagenaar, J. A.",
               "Gonzalez-Zorn, B.", "Guerra, B.", "Mevius, D. J.", "Hordijk, J."],
      title="Plasmids carrying antimicrobial resistance genes in Enterobacteriaceae",
      journal="J. Antimicrob. Chemother.", volume="73", pages="1121-1137", year=2018,
      doi="10.1093/jac/dkx488", pmid="29370371", source="PubMed", kind="article"),
 dict(key="orlek_2017", n_all=11,
      authors=["Orlek, A.", "Stoesser, N.", "Anjum, M. F.", "Doumith, M.", "Ellington, M. J.",
               "Peto, T.", "Crook, D.", "Woodford, N.", "Walker, A. S.", "Phan, H.", "Sheppard, A. E."],
      title="Plasmid classification in an era of whole-genome sequencing: application in studies of antibiotic resistance epidemiology",
      journal="Front. Microbiol.", volume="8", pages="182", year=2017,
      doi="10.3389/fmicb.2017.00182", pmid="28232822", source="PubMed", kind="article"),
 dict(key="arredondo_2017",
      authors=["Arredondo-Alonso, S.", "Willems, R. J.", "van Schaik, W.", "Schurch, A. C."],
      title="On the (im)possibility of reconstructing plasmids from whole-genome short-read sequencing data",
      journal="Microb. Genom.", volume="3", pages="e000128", year=2017,
      doi="10.1099/mgen.0.000128", pmid="29177087", source="PubMed", kind="article"),
 dict(key="arredondo_2020", n_all=14,
      authors=["Arredondo-Alonso, S.", "Top, J.", "McNally, A.", "Puranen, S.", "Pesonen, M."],
      title="Plasmids shaped the recent emergence of the major nosocomial pathogen Enterococcus faecium",
      journal="mBio", volume="11", pages="e03284-19", year=2020,
      doi="10.1128/mBio.03284-19", pmid="32047136", source="PubMed", kind="article",
      note="14 authors; Nature style truncates after the first author, rendered as 'Arredondo-Alonso, S. et al.'"),
 dict(key="david_2019", n_all=17,
      authors=["David, S.", "Reuter, S.", "Harris, S. R.", "Glasner, C.", "Feltwell, T."],
      title="Epidemic of carbapenem-resistant Klebsiella pneumoniae in Europe is driven by nosocomial spread",
      journal="Nat. Microbiol.", volume="4", pages="1919-1929", year=2019,
      doi="10.1038/s41564-019-0492-8", pmid="31358985", source="PubMed", kind="article",
      note="17 listed authors plus consortium; rendered with et al."),
 dict(key="carattoli_2014", n_all=8,
      authors=["Carattoli, A.", "Zankari, E.", "Garcia-Fernandez, A.", "Voldby Larsen, M.", "Lund, O."],
      title="In silico detection and typing of plasmids using PlasmidFinder and plasmid multilocus sequence typing",
      journal="Antimicrob. Agents Chemother.", volume="58", pages="3895-3903", year=2014,
      doi="10.1128/AAC.02412-14", pmid="24777092", source="PubMed", kind="article",
      tool="PlasmidFinder",
      note="the original 2014 tool paper; the 2020 Methods Mol. Biol. chapter is a secondary protocol source and is deliberately not cited"),
 dict(key="robertson_2018", authors=["Robertson, J.", "Nash, J. H. E."],
      title="MOB-suite: software tools for clustering, reconstruction and typing of plasmids from draft assemblies",
      journal="Microb. Genom.", volume="4", pages="e000206", year=2018,
      doi="10.1099/mgen.0.000206", pmid="30052170", source="PubMed", kind="article", tool="MOB-recon"),
 dict(key="schwengers_2020", n_all=6,
      authors=["Schwengers, O.", "Barth, P.", "Falgenhauer, L.", "Hain, T.", "Chakraborty, T."],
      title="Platon: identification and characterization of bacterial plasmid contigs in short-read draft assemblies exploiting protein sequence-based replicon distribution scores",
      journal="Microb. Genom.", volume="6", pages="e000398", year=2020,
      doi="10.1099/mgen.0.000398", pmid="32579097", source="PubMed", kind="article", tool="Platon",
      note="6 authors; rendered with et al."),
 dict(key="royer_2018", n_all=7,
      authors=["Royer, G.", "Decousser, J. W.", "Branger, C.", "Dubois, M.", "Medigue, C."],
      title="PlaScope: a targeted approach to assess the plasmidome from genome assemblies at the species level",
      journal="Microb. Genom.", volume="4", pages="e000211", year=2018,
      doi="10.1099/mgen.0.000211", pmid="30265232", source="PubMed", kind="article", tool="PlaScope",
      note="7 authors; rendered with et al."),
 dict(key="paganini_2024", n_all=9,
      authors=["Paganini, J. A.", "Kerkvliet, J. J.", "Vader, L.", "Plantinga, N. L.", "Meneses, R."],
      title="PlasmidEC and gplas2: an optimized short-read approach to predict and reconstruct antibiotic resistance plasmids in Escherichia coli",
      journal="Microb. Genom.", volume="10", pages="001193", year=2024,
      doi="10.1099/mgen.0.001193", pmid="38376388", source="PubMed", kind="article",
      tool="PlasmidEC; gplas2",
      note="PubMed title truncates the trailing species name at the source; restored here from the published article. 9 authors; rendered with et al. This single paper is the primary citation for both PlasmidEC and gplas2, the versions used here"),
 dict(key="vandergraaf_2021",
      authors=["van der Graaf-van Bloois, L.", "Wagenaar, J. A.", "Zomer, A. L."],
      title="RFPlasmid: predicting plasmid sequences from short-read assembly data using machine learning",
      journal="Microb. Genom.", volume="7", pages="000683", year=2021,
      doi="10.1099/mgen.0.000683", pmid="34846288", source="PubMed", kind="article", tool="RFPlasmid"),
 dict(key="muller_2019", authors=["Muller, R.", "Chauve, C."],
      title="HyAsP, a greedy tool for plasmids identification",
      journal="Bioinformatics", volume="35", pages="4436-4439", year=2019,
      doi="10.1093/bioinformatics/btz413", pmid="31116364", source="PubMed", kind="article",
      tool="HyAsP",
      note="pages corrected to 4436-4439; an earlier internal draft carried 3355, which was wrong"),
 dict(key="tang_2023", authors=["Tang, X.", "Shang, J.", "Ji, Y.", "Sun, Y."],
      title="PLASMe: a tool to identify PLASMid contigs from short-read assemblies using transformer",
      journal="Nucleic Acids Res.", volume="51", pages="e83", year=2023,
      doi="10.1093/nar/gkad578", pmid="37427782", source="PubMed", kind="article", tool="PLASMe"),
 dict(key="zhu_2023", authors=["Zhu, Q.", "Gao, S.", "Xiao, B.", "He, Z.", "Hu, S."],
      title="Plasmer: an accurate and sensitive bacterial plasmid prediction tool based on machine learning of shared k-mers and genomic features",
      journal="Microbiol. Spectr.", volume="11", pages="e04645-22", year=2023,
      doi="10.1128/spectrum.04645-22", pmid="37191574", source="PubMed", kind="article", tool="Plasmer",
      note="title capitalisation normalised to Nature style (sentence case)"),
 dict(key="sielemann_2023",
      authors=["Sielemann, J.", "Sielemann, K.", "Brejova, B.", "Vinar, T.", "Chauve, C."],
      title="plASgraph2: using graph neural networks to detect plasmid contigs from an assembly graph",
      journal="Front. Microbiol.", volume="14", pages="1267695", year=2023,
      doi="10.3389/fmicb.2023.1267695", pmid="37869681", source="PubMed", kind="article",
      tool="plASgraph2"),
 dict(key="camargo_2024", n_all=9,
      authors=["Camargo, A. P.", "Roux, S.", "Schulz, F.", "Babinski, M.", "Xu, Y."],
      title="Identification of mobile genetic elements with geNomad",
      journal="Nat. Biotechnol.", volume="42", pages="1303-1312", year=2024,
      doi="10.1038/s41587-023-01953-y", pmid="37735266", source="PubMed", kind="article",
      tool="geNomad",
      note="year corrected to 2024, the year of volume 42 in which the article of record appears; PubMed records an electronic pre-issue date of 2023-09-21. 9 authors; rendered with et al."),
 dict(key="feldgarden_2021", n_all=12,
      authors=["Feldgarden, M.", "Brover, V.", "Gonzalez-Escalona, N.", "Frye, J. G.", "Haendiges, J."],
      title="AMRFinderPlus and the Reference Gene Catalog facilitate examination of the genomic links among antimicrobial resistance, stress response, and virulence",
      journal="Sci. Rep.", volume="11", pages="12728", year=2021,
      doi="10.1038/s41598-021-91456-0", pmid="34135355", source="PubMed", kind="article",
      tool="AMRFinderPlus", note="primary tool paper; 12 authors, rendered with et al."),
 dict(key="feldgarden_2022", n_all=6,
      authors=["Feldgarden, M.", "Brover, V.", "Fedorov, B.", "Haft, D. H.", "Prasad, A. B."],
      title="Curation of the AMRFinderPlus databases: applications, functionality and impact",
      journal="Microb. Genom.", volume="8", pages="000832", year=2022,
      doi="10.1099/mgen.0.000832", pmid="35675101", source="PubMed", kind="article",
      tool="AMRFinderPlus database",
      note="database-curation paper for the reference gene catalogue bundled in the pinned image; 6 authors, rendered with et al."),
 dict(key="wick_2017", authors=["Wick, R. R.", "Judd, L. M.", "Gorrie, C. L.", "Holt, K. E."],
      title="Unicycler: resolving bacterial genome assemblies from short and long sequencing reads",
      journal="PLoS Comput. Biol.", volume="13", pages="e1005595", year=2017,
      doi="10.1371/journal.pcbi.1005595", pmid="28594827", source="PubMed", kind="article",
      tool="Unicycler"),
 dict(key="bankevich_2012", n_all=16,
      authors=["Bankevich, A.", "Nurk, S.", "Antipov, D.", "Gurevich, A. A.", "Dvorkin, M."],
      title="SPAdes: a new genome assembly algorithm and its applications to single-cell sequencing",
      journal="J. Comput. Biol.", volume="19", pages="455-477", year=2012,
      doi="10.1089/cmb.2012.0021", pmid="22506599", source="PubMed", kind="article", tool="SPAdes",
      note="16 authors; rendered with et al."),
 dict(key="shen_2016", authors=["Shen, W.", "Le, S.", "Li, Y.", "Hu, F."],
      title="SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation",
      journal="PLoS ONE", volume="11", pages="e0163962", year=2016,
      doi="10.1371/journal.pone.0163962", pmid="27706213", source="PubMed", kind="article",
      tool="SeqKit"),
 dict(key="camacho_2009", n_all=7,
      authors=["Camacho, C.", "Coulouris, G.", "Avagyan, V.", "Ma, N.", "Papadopoulos, J."],
      title="BLAST+: architecture and applications",
      journal="BMC Bioinformatics", volume="10", pages="421", year=2009,
      doi="10.1186/1471-2105-10-421", pmid="20003500", source="PubMed", kind="article", tool="BLAST+",
      note="7 authors; rendered with et al."),
 dict(key="li_2018", authors=["Li, H."],
      title="Minimap2: pairwise alignment for nucleotide sequences",
      journal="Bioinformatics", volume="34", pages="3094-3100", year=2018,
      doi="10.1093/bioinformatics/bty191", pmid="29750242", source="PubMed", kind="article",
      tool="minimap2"),
 dict(key="shaw_2023", authors=["Shaw, J.", "Yu, Y. W."],
      title="Fast and robust metagenomic sequence comparison through sparse chaining with skani",
      journal="Nat. Methods", volume="20", pages="1661-1665", year=2023,
      doi="10.1038/s41592-023-02018-3", pmid="37735570", source="PubMed", kind="article", tool="skani"),
 dict(key="wick_2021", n_all=8,
      authors=["Wick, R. R.", "Judd, L. M.", "Cerdeira, L. T.", "Hawkey, J.", "Meric, G."],
      title="Trycycler: consensus long-read assemblies for bacterial genomes",
      journal="Genome Biol.", volume="22", pages="266", year=2021,
      doi="10.1186/s13059-021-02483-z", pmid="34521459", source="PubMed", kind="article",
      note="cited only as the reference standard for orthogonal long-read truth in the discussion of future work; 8 authors, rendered with et al."),
 dict(key="teixeira_2025", n_all=10,
      authors=["Teixeira, M.", "Souque, C.", "Worby, C. J.", "Shea, T.", "Commins, N."],
      title="Circling in on plasmids: benchmarking plasmid detection and reconstruction tools for short-read data from diverse species",
      journal="Brief. Bioinform.", volume="26", pages="bbaf589", year=2025,
      doi="10.1093/bib/bbaf589", pmid="41214871", source="PubMed", kind="article",
      note="the 2025 multi-species benchmark. The peer-reviewed journal version is cited, not the bioRxiv preprint (doi 10.1101/2025.07.28.667252, PMID 40766476). 10 authors; rendered with et al."),
 dict(key="chicco_2020", authors=["Chicco, D.", "Jurman, G."],
      title="The advantages of the Matthews correlation coefficient (MCC) over F1 score and accuracy in binary classification evaluation",
      journal="BMC Genomics", volume="21", pages="6", year=2020,
      doi="10.1186/s12864-019-6413-7", pmid="31898477", source="PubMed", kind="article"),
 dict(key="vancalster_2019",
      authors=["Van Calster, B.", "McLernon, D. J.", "van Smeden, M.", "Wynants, L.", "Steyerberg, E. W."],
      title="Calibration: the Achilles heel of predictive analytics",
      journal="BMC Med.", volume="17", pages="230", year=2019,
      doi="10.1186/s12916-019-1466-7", pmid="31842878", source="PubMed", kind="article"),
 dict(key="collins_2024", n_all=34,
      authors=["Collins, G. S.", "Moons, K. G. M.", "Dhiman, P.", "Riley, R. D.", "Beam, A. L."],
      title="TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods",
      journal="BMJ", volume="385", pages="e078378", year=2024,
      doi="10.1136/bmj-2023-078378", pmid="38626948", source="PubMed", kind="article",
      note="34 authors; rendered with et al. Used as the reporting framework adapted for a non-clinical prediction model"),
 dict(key="bossuyt_2015", n_all=17,
      authors=["Bossuyt, P. M.", "Reitsma, J. B.", "Bruns, D. E.", "Gatsonis, C. A.", "Glasziou, P. P."],
      title="STARD 2015: an updated list of essential items for reporting diagnostic accuracy studies",
      journal="BMJ", volume="351", pages="h5527", year=2015,
      doi="10.1136/bmj.h5527", pmid="26511519", source="PubMed", kind="article",
      note="17 authors; rendered with et al."),
 dict(key="burgin_2023", n_all=30,
      authors=["Burgin, J.", "Ahamed, A.", "Cummins, C.", "Devraj, R.", "Gueye, K."],
      title="The European Nucleotide Archive in 2022",
      journal="Nucleic Acids Res.", volume="51", pages="D121-D125", year=2023,
      doi="10.1093/nar/gkac1051", pmid="36399492", source="PubMed", kind="article",
      note="30 authors; rendered with et al."),
 dict(key="field_2007", authors=["Field, C. A.", "Welsh, A. H."],
      title="Bootstrapping clustered data",
      journal="J. R. Stat. Soc. B", volume="69", pages="369-390", year=2007,
      doi="10.1111/j.1467-9868.2007.00593.x", pmid="", source="Crossref", kind="article",
      note="not indexed in PubMed; verified against the Crossref record on 2026-08-24"),
 dict(key="davison_1997", authors=["Davison, A. C.", "Hinkley, D. V."],
      title="Bootstrap Methods and their Application",
      journal="", volume="", pages="", year=1997,
      doi="10.1017/CBO9780511802843", pmid="", source="Crossref", kind="book",
      publisher="Cambridge Univ. Press",
      note="monograph; verified against the Crossref record on 2026-08-24"),
 dict(key="chow_1970", authors=["Chow, C. K."],
      title="On optimum recognition error and reject tradeoff",
      journal="IEEE Trans. Inf. Theory", volume="16", pages="41-46", year=1970,
      doi="10.1109/TIT.1970.1054406", pmid="", source="Crossref", kind="article",
      note="not indexed in PubMed; verified against the Crossref record on 2026-08-24"),
 dict(key="brier_1950", authors=["Brier, G. W."],
      title="Verification of forecasts expressed in terms of probability",
      journal="Mon. Weather Rev.", volume="78", pages="1-3", year=1950,
      doi="10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2", pmid="", source="Crossref",
      kind="article",
      note="not indexed in PubMed; verified against the Crossref record on 2026-08-24"),
 dict(key="pedregosa_2011", n_all=16,
      authors=["Pedregosa, F.", "Varoquaux, G.", "Gramfort, A.", "Michel, V.", "Thirion, B."],
      title="Scikit-learn: machine learning in Python",
      journal="J. Mach. Learn. Res.", volume="12", pages="2825-2830", year=2011,
      doi="", pmid="", source="publisher (jmlr.org/papers/v12/pedregosa11a.html)", kind="article",
      note="JMLR does not assign DOIs; volume, issue 85, pages and the 16-author list were read from the publisher's own paper page on 2026-08-24. Rendered with et al."),
]


def nature_authors(r):
    a = r["authors"]
    n = r.get("n_all", len(a))
    if n > 5:
        return a[0] + " et al."
    if len(a) == 1:
        return a[0]
    return ", ".join(a[:-1]) + " & " + a[-1]


SPECIES = ["Enterococcus faecium", "Escherichia coli", "Klebsiella pneumoniae",
           "Enterobacteriaceae"]


def italicise(t):
    for sp in SPECIES:
        t = t.replace(sp, "*" + sp + "*")
    return t


def nature_line(r, n):
    au = nature_authors(r)
    if "," not in au and not au.endswith("."):
        au += "."   # group/collaboration author needs its own full stop
    if r["kind"] == "book":
        s = "%d. %s *%s* (%s, %d)." % (n, au, r["title"], r["publisher"], r["year"])
    else:
        s = "%d. %s %s. *%s* **%s**, %s (%d)." % (
            n, au, italicise(r["title"]), r["journal"], r["volume"], r["pages"], r["year"])
    if r.get("doi"):
        s += " https://doi.org/%s" % r["doi"]
    return s


def bibtex(r):
    au = " and ".join(r["authors"])
    if r.get("n_all", len(r["authors"])) > len(r["authors"]):
        au += " and others"
    fields = [("author", au), ("title", "{%s}" % r["title"])]
    if r["kind"] == "book":
        fields += [("publisher", r["publisher"])]
        typ = "book"
    else:
        fields += [("journal", r["journal"]), ("volume", r["volume"]), ("pages", r["pages"])]
        typ = "article"
    fields += [("year", str(r["year"]))]
    if r.get("doi"):
        fields.append(("doi", r["doi"]))
    if r.get("pmid"):
        fields.append(("pmid", r["pmid"]))
    body = ",\n".join("  %-9s = {%s}" % (k, v) for k, v in fields)
    return "@%s{%s,\n%s\n}\n" % (typ, r["key"], body)


def ris(r):
    L = ["TY  - " + ("BOOK" if r["kind"] == "book" else "JOUR")]
    for a in r["authors"]:
        L.append("AU  - " + a)
    if r.get("n_all", len(r["authors"])) > len(r["authors"]):
        L.append("AU  - et al.")
    L.append("TI  - " + r["title"])
    if r["kind"] == "book":
        L.append("PB  - " + r["publisher"])
    else:
        L.append("JO  - " + r["journal"])
        if r["volume"]:
            L.append("VL  - " + r["volume"])
        if r["pages"]:
            sp = r["pages"].split("-")
            L.append("SP  - " + sp[0])
            if len(sp) > 1:
                L.append("EP  - " + sp[1])
    L.append("PY  - %d" % r["year"])
    if r.get("doi"):
        L.append("DO  - " + r["doi"])
    if r.get("pmid"):
        L.append("AN  - " + r["pmid"])
    L.append("ER  - ")
    return "\n".join(L) + "\n\n"


os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ markdown list
md = ["# PlasmidCall — reference list (Nature Portfolio style)", "",
      "Numbered in order of first appearance in the manuscript. All authors are listed unless there",
      "are more than five, in which case only the first author is given followed by *et al.*, per the",
      "journal's reference-style requirement. Journal names are abbreviated; volume numbers are bold.",
      "", "Verification: see `PLASMIDCALL_REFERENCE_AUDIT.tsv`. Accessed 2026-08-24.", ""]
for i, r in enumerate(R, 1):
    md.append(nature_line(r, i))
    r["_n"] = i
io.open(OUT + "/PLASMIDCALL_REFERENCES.md", "w", encoding="utf-8", newline="\n").write(
    "\n".join(md) + "\n")

io.open(OUT + "/PLASMIDCALL_REFERENCES.bib", "w", encoding="utf-8", newline="\n").write(
    "% PlasmidCall manuscript bibliography\n"
    "% Every entry verified 2026-08-24 against PubMed, Crossref or the publisher's page.\n"
    "% See PLASMIDCALL_REFERENCE_AUDIT.tsv for the per-field verification record.\n\n"
    + "\n".join(bibtex(r) for r in R))

io.open(OUT + "/PLASMIDCALL_REFERENCES.ris", "w", encoding="utf-8", newline="\n").write(
    "".join(ris(r) for r in R))

# ------------------------------------------------------------------ audit table
COLS = ["n", "cite_key", "n_authors_in_source", "authors_verified", "title_verified", "journal_verified", "year_verified",
        "volume_verified", "pages_verified", "doi", "doi_verified", "pmid", "pmid_verified",
        "verification_source", "is_original_tool_paper", "tool", "note"]
with io.open(OUT + "/PLASMIDCALL_REFERENCE_AUDIT.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS, delimiter="\t", lineterminator="\n", restval="")
    w.writeheader()
    for r in R:
        pub = r["source"] == "PubMed"
        w.writerow({
            "n": r["_n"], "cite_key": r["key"],
            "n_authors_in_source": r.get("n_all", len(r["authors"])),
            "authors_verified": "yes", "title_verified": "yes",
            "journal_verified": "yes" if r["kind"] != "book" else "n/a (book)",
            "year_verified": "yes",
            "volume_verified": "yes" if r["volume"] else "n/a",
            "pages_verified": "yes" if r["pages"] else "n/a",
            "doi": r.get("doi", ""),
            "doi_verified": "yes" if r.get("doi") else "n/a (publisher assigns no DOI)",
            "pmid": r.get("pmid", ""),
            "pmid_verified": "yes" if r.get("pmid") else "n/a (not indexed in PubMed)",
            "verification_source": r["source"],
            "is_original_tool_paper": "yes" if r.get("tool") else "no",
            "tool": r.get("tool", ""),
            "note": r.get("note", "")})

# ------------------------------------------------------------------ index for the manuscript
idx = collections.OrderedDict((r["key"], r["_n"]) for r in R)
io.open(OUT + "/PLASMIDCALL_REFERENCE_INDEX.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps({"n_references": len(R), "journal_limit": 60,
                "within_limit": len(R) <= 60, "key_to_number": idx}, indent=1) + "\n")

print("references: %d (journal limit 60: %s)" % (len(R), "OK" if len(R) <= 60 else "OVER"))
print("tool papers cited: %d" % sum(1 for r in R if r.get("tool")))
print("PubMed-verified: %d | Crossref-verified: %d | publisher-verified: %d" % (
    sum(1 for r in R if r["source"] == "PubMed"),
    sum(1 for r in R if r["source"] == "Crossref"),
    sum(1 for r in R if r["source"].startswith("publisher"))))

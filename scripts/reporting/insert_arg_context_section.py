# -*- coding: utf-8 -*-
"""Insert the resistance-gene genomic-context Results subsection into the manuscript source."""
import io, json

C = json.load(io.open("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json",
                      encoding="utf-8"))["values"]
P = "docs/manuscript/PLASMIDCALL_MANUSCRIPT_FINAL.md"
s = io.open(P, encoding="utf-8").read()

pool = C["argctx_pooled"]
tax = C["argctx_by_taxon"]
cls = {c["stratum"]: c for c in C["argctx_by_class"]}
fd = C["argctx_family_distribution"]
vA, vB, vD = C["argctx_vanA"], C["argctx_vanB"], C["argctx_vanD"]
TH = C["argctx_thresholds"]


def pc(x):
    return "%.1f%%" % (100 * x)


def n(x):
    return "{:,}".format(int(x))


EFFLUX = [k for k in cls if k.startswith("NITROFURAN")][0]
MLS = [k for k in cls if k.startswith("LINCOSAMIDE/MACROLIDE")][0]

section = """### Genomic context of resistance determinants across the six taxa

Establishing the truth labels also established, for every contig, whether the resistance
determinants it carries sit on a plasmid or in the chromosome. This is a property of the 150
genomes rather than of any classifier: the counts below are identical for every predictor that
answers for all {ntot} contigs, and derive only from alignment against each isolate's own closed
reference genome.

**{npl} of the {ntot} resistance-gene-bearing contigs were plasmid-derived ({fpl})**, the remaining
{nch} being chromosomal. The proportion differed more than eightfold across taxa, from {thi} in
*Citrobacter* spp. down to {tlo} in *Serratia* spp. (Table 5, Fig. 8a).

The proportion also separated sharply by antimicrobial class (Fig. 8b). Among the {ncls} classes
carrying at least {clsmin} contigs, determinants of sulfonamide ({sul}), quaternary-ammonium
({qac}), glycopeptide ({gly}), phenicol ({phe}) and lincosamide–macrolide–streptogramin ({mls})
resistance were predominantly plasmid-derived. At the other end, fosfomycin resistance and the
nitrofuran/phenicol/quinolone/tetracycline efflux group were **exclusively chromosomal — 0 of
{nfos} and 0 of {neff} contigs respectively**. β-Lactam determinants sat in between at {bla},
which reflects the heterogeneity of that class: it contains both acquired enzymes and the
species-specific chromosomal cephalosporinases.

At gene-family resolution the distribution is bimodal rather than graded. Of the {nfam} families
carrying at least {fammin} contigs, **{fhi} were at or above 90% plasmid-derived and {flo} at or
below 10%, leaving only {fmid} intermediate** — {fext} of families sat at one extreme or the other.

Glycopeptide resistance is the clearest case, because two operon types occur in the same cohort.
**The {vAg} vanA-type genes were plasmid-derived on all {vAc} contigs carrying them, while the
{vBg} vanB-type and {vDg} vanD-type genes were chromosomal on all {vBc} and {vDc} contigs**
(Fig. 8c). The same separation runs through the β-lactamases: acquired enzymes were overwhelmingly
plasmid-derived, whereas the species-specific chromosomal cephalosporinases of *Enterobacter*,
*Citrobacter* and *Serratia* were not found on a plasmid-derived contig at all.

This concordance needs stating precisely, because it is an internal check rather than a discovery.
The intrinsic-versus-acquired distinction it recovers has been established for decades. What is
informative is that the truth assignment reproduces it without being told: the mapping procedure
uses only sequence alignment against a closed reference and has no access to gene identity, gene
function, or any prior expectation about mobility. That it independently separates vanA from vanB,
and acquired β-lactamases from chromosomal cephalosporinases, is evidence that the labels against
which every classifier in this study was scored correspond to genomic reality.

Three limits apply to these proportions. They describe **contigs, not gene copies**: a contig
carrying determinants of several classes contributes to each, so class counts do not sum to the
pooled total. They describe **this deliberately de-clustered cohort** and are not prevalence
estimates for any population. And a plasmid-derived contig is a statement about **location, not
mobility** — no transfer, conjugation or mobilization was measured, and none is claimed.

""".format(
    ntot=n(pool["contigs"]), npl=n(pool["plasmid_derived"]), nch=n(pool["chromosomal"]),
    fpl=pc(pool["plasmid_fraction"]),
    thi=pc(tax[0]["plasmid_fraction"]), tlo=pc(tax[-1]["plasmid_fraction"]),
    ncls=len(cls), clsmin=TH["class_min_contigs"],
    sul=pc(cls["SULFONAMIDE"]["plasmid_fraction"]),
    qac=pc(cls["QUATERNARY AMMONIUM"]["plasmid_fraction"]),
    gly=pc(cls["GLYCOPEPTIDE"]["plasmid_fraction"]),
    phe=pc(cls["PHENICOL"]["plasmid_fraction"]),
    mls=pc(cls[MLS]["plasmid_fraction"]),
    nfos=cls["FOSFOMYCIN"]["contigs"], neff=cls[EFFLUX]["contigs"],
    bla=pc(cls["BETA-LACTAM"]["plasmid_fraction"]),
    nfam=fd["families_reported"], fammin=TH["family_min_contigs"],
    fhi=fd["at_or_above_90pc_plasmid"], flo=fd["at_or_below_10pc_plasmid"],
    fmid=fd["between"], fext=pc(fd["fraction_at_an_extreme"]),
    vAg=vA["n_genes"], vAc=vA["contigs"], vBg=vB["n_genes"], vDg=vD["n_genes"],
    vBc=vB["contigs"], vDc=vD["contigs"])

ANCHOR = "### Performance on resistance-gene-bearing contigs"
assert s.count(ANCHOR) == 1, s.count(ANCHOR)
s = s.replace(ANCHOR, section + ANCHOR)
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("inserted, %d words" % len(section.split()))

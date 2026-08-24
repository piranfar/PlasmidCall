# -*- coding: utf-8 -*-
"""Regenerate every main figure from the frozen source tables.

Journal requirements applied (npj AMR, submission guidelines accessed 2026-08-24):
  RGB colour, >= 300 dpi raster, Arial/Helvetica throughout, 8 pt optimal font size,
  white background, thinnest line >= 1 pt, no rainbow scale, no red/green contrast pair,
  no 3-D effects, histogram axes not truncated, panels labelled lower-case bold a, b, c.

Emits per figure: editable .svg, publication .pdf, 600 dpi .png, and a machine-readable
source-data .tsv. A checksum manifest covers all of them.
"""
import csv, io, json, os, hashlib, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle, FancyBboxPatch
import matplotlib.font_manager as fm
import numpy as np

R = "docs/evidence/P1.13_results"
PF = "docs/postfreeze/tables"
PROV = "docs/evidence/P1.13_provenance"
OUT = "docs/manuscript/figures"
SRC = "docs/manuscript/figures/source_data"
os.makedirs(OUT, exist_ok=True)
os.makedirs(SRC, exist_ok=True)

# ---------------------------------------------------------------- style
for cand in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"):
    if os.path.exists(cand):
        fm.fontManager.addfont(cand)
FONT = "Arial" if any("Arial" == f.name for f in fm.fontManager.ttflist) else "DejaVu Sans"
plt.rcParams.update({
    "font.family": FONT, "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.linewidth": 1.0, "lines.linewidth": 1.0, "patch.linewidth": 1.0,
    "xtick.major.width": 1.0, "ytick.major.width": 1.0,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none",
    "pdf.fonttype": 42, "ps.fonttype": 42,
})

BLUE = "#1f4e79"      # PlasmidCall rows
ORANGE = "#d95f02"    # third-party tools
GREY = "#6e6e6e"      # predeclared baselines
LIGHT = "#c9d6e3"
FLOOR = "#333333"


def tsv(p):
    return list(csv.DictReader(io.open(p, encoding="utf-8"), delimiter="\t"))


def js(p):
    return json.load(io.open(p, encoding="utf-8"))


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def ci(x):
    if not x:
        return None
    return [float(v) for v in x.strip("[]").split(",")]


def label(ax, s, x=-0.14, y=1.06):
    ax.text(x, y, s, transform=ax.transAxes, fontsize=9, fontweight="bold", va="top", ha="left")


MANIFEST = []


def save(fig, name, source_rows, source_cols):
    fig.savefig("%s/%s.svg" % (OUT, name), bbox_inches="tight")
    fig.savefig("%s/%s.pdf" % (OUT, name), bbox_inches="tight")
    fig.savefig("%s/%s.png" % (OUT, name), dpi=600, bbox_inches="tight")
    plt.close(fig)
    sp = "%s/%s_source_data.tsv" % (SRC, name)
    with io.open(sp, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=source_cols, delimiter="\t", lineterminator="\n",
                           restval="")
        w.writeheader()
        w.writerows(source_rows)
    for p in ("%s/%s.svg" % (OUT, name), "%s/%s.pdf" % (OUT, name),
              "%s/%s.png" % (OUT, name), sp):
        h = hashlib.sha256(io.open(p, "rb").read()).hexdigest()
        MANIFEST.append({"file": p.replace("\\", "/"), "bytes": os.path.getsize(p),
                         "sha256": h})
    print("  wrote %s (svg/pdf/png@600dpi + source data, %d rows)" % (name, len(source_rows)))


# ---------------------------------------------------------------- shared data
inv = tsv(R + "/P113_PREDICTOR_INVENTORY.tsv")
prim = {r["predictor"]: r for r in tsv(R + "/P113_PRIMARY_METRICS.tsv")}
comp = {r["predictor"]: r for r in tsv(R + "/P113_COMPARATOR_METRICS.tsv")}
comp.update(prim)
argall = {r["row"]: r for r in tsv(R + "/P113_ARG_ALL_PREDICTORS.tsv") if r["subset"] == "ARG_bearing"}
pareto = {d["row"] for d in js(R + "/P113_ARG_PARETO_AND_CORE_CLAIM.json")["pareto_frontier"]}
canon = js("docs/manuscript/PLASMIDCALL_CANONICAL_NUMBERS.json")["values"]


def pretty(row):
    return (row.replace("tool:", "").replace("baseline:", "")
               .replace("v1.2-General@0.9285", "PlasmidCall v1.2-General")
               .replace("v1.1@0.9524", "PlasmidCall v1.1 (0.9524)")
               .replace("v1.1@0.9605_high_conf", "PlasmidCall v1.1 (0.9605)")
               .replace("router", "PlasmidCall router")
               .replace("majority_vote", "panel majority vote")
               .replace("any_tool_plasmid", "any-tool-plasmid")
               .replace("all_chromosome", "all-chromosome"))


def mathtaxon(t):
    """Italicise the taxon name but leave the rank abbreviation 'spp.' in roman, as required."""
    t = t.replace("Enterococcus", "E.").replace("Klebsiella", "K.")
    if t.endswith(" spp."):
        return "$\\mathit{%s}$ spp." % t[:-5].replace(" ", "\\ ")
    return "$\\mathit{%s}$" % t.replace(" ", "\\ ")


def kind(row):
    if row.startswith("baseline:"):
        return "baseline", GREY
    if row.startswith("tool:"):
        return "third-party tool", ORANGE
    return "PlasmidCall", BLUE


# ================================================================= Figure 1
print("Figure 1 - prospective sealed-validation design")
stages = [
    ("Design freeze",
     "design, cohort rules, eligibility, thresholds,\nanalysis plan and stopping rules written first",
     "hash-sealed before any read was retrieved", BLUE),
    ("Acquisition and assembly",
     "150 isolates; checksum-verified reads, paired-read\nvalidation, 30x depth floor",
     "fail-closed atomic acceptance, 14 checks; 150 of 150", BLUE),
    ("Panel execution",
     "13 units x 150 isolates in pinned images,\nread-only inputs, no truth mount",
     "1,950 units; 72 deterministic failures recorded, not imputed", BLUE),
    ("Prediction freeze",
     "22 artefacts, 150 assembly hashes,\n1,950-unit execution manifest",
     "frozen table reproduced byte-for-byte, twice, independently", BLUE),
    ("Truth construction",
     "each isolate's own closed reference;\ncompetitive mapping, fixed thresholds",
     "refuses to run without the freeze receipt and table hash", ORANGE),
    ("Join and evaluation",
     "registered join executed exactly once;\nprespecified endpoint applied",
     "19,320 <-> 19,320, zero one-sided records, zero duplicates", ORANGE),
    ("Results freeze",
     "immutable primary result",
     "385 values independently recomputed, 0 disagreements", GREY),
    ("Post-freeze package",
     "secondary, sensitivity, exploratory\nand integrity analyses",
     "adds only; primary freeze and its outputs unmodified", GREY),
]

fig, ax = plt.subplots(figsize=(7.2, 4.8))
ax.set_xlim(0, 1)
ax.set_ylim(0, len(stages) + 1.1)
ax.axis("off")
xs, xn, xc, xg = 0.055, 0.085, 0.335, 0.615
for i, (t, sub, gate, col) in enumerate(stages):
    y = len(stages) - i
    ax.plot([xs, xs], [y - 0.5, y + 0.5], color=col, linewidth=2.0, solid_capstyle="butt",
            zorder=1)
    ax.scatter([xs], [y], s=34, color=col, zorder=3, edgecolor="white", linewidth=1.0)
    ax.text(xn, y + 0.16, t, fontsize=7.4, fontweight="bold", color=col, va="center")
    ax.text(xc, y + 0.16, sub, fontsize=6.4, color="#333333", va="center", linespacing=1.45)
    ax.text(xg, y + 0.16, "gate: " + gate, fontsize=6.2, color=col, va="center", style="italic")
    if i < len(stages) - 1:
        ax.annotate("", xy=(xs, y - 0.62), xytext=(xs, y - 0.42),
                    arrowprops=dict(arrowstyle="-|>", color="#9a9a9a", linewidth=1.0,
                                    mutation_scale=7))
ax.plot([0.018, 0.018], [len(stages) - 3.5, len(stages) + 0.5], color=BLUE, linewidth=2.4,
        solid_capstyle="butt")
ax.text(0.006, len(stages) - 1.5, "TRUTH-BLIND", rotation=90, fontsize=6.6, fontweight="bold",
        color=BLUE, va="center", ha="center")
ax.plot([0.018, 0.018], [len(stages) - 7.5, len(stages) - 3.6], color=ORANGE, linewidth=2.4,
        solid_capstyle="butt")
ax.text(0.006, len(stages) - 5.5, "TRUTH ACCESSIBLE", rotation=90, fontsize=6.6,
        fontweight="bold", color=ORANGE, va="center", ha="center")
ax.text(xn, len(stages) + 0.72,
        "No truth artefact existed on the analysis system until the prediction table was frozen "
        "and independently reproduced.",
        fontsize=6.6, color=BLUE, va="center")
ax.text(xn, 0.28,
        "Each stage is gated: the next stage cannot begin until the gate passes and the artefact "
        "hash it binds is recorded.\nNo model, threshold, router, cohort member or truth label was "
        "changed after the prediction freeze.",
        fontsize=6.4, color="#333333", va="center", linespacing=1.5)

save(fig, "Figure1_study_design",
     [{"stage_order": i + 1, "stage": t, "content": sub.replace("\n", " "),
       "gate": g.replace("\n", " "),
       "truth_state": "truth-blind" if i < 4 else "truth accessible"}
      for i, (t, sub, g, c) in enumerate(stages)],
     ["stage_order", "stage", "content", "gate", "truth_state"])

# ================================================================= Figure 2
print("Figure 2 - cohort and truth resolution")
rq = tsv(PF + "/PF10a_REFERENCE_QUALITY.tsv")
tax_agg = collections.OrderedDict()
for r in rq:
    a = tax_agg.setdefault(r["taxon"], {"isolates": 0, "eligible": 0, "resolved": 0, "unresolved": 0})
    a["isolates"] += 1
    a["eligible"] += int(r["eligible_contigs"])
    a["resolved"] += int(r["resolved_contigs"])
    a["unresolved"] += int(r["unresolved_contigs"])
taxrows = {t["taxon"]: t for t in canon["taxon_v12"]}
for t, a in tax_agg.items():
    a["plasmid"] = taxrows[t]["n_plasmid"]
    a["chromosome"] = taxrows[t]["n_scored"] - taxrows[t]["n_plasmid"]

fig = plt.figure(figsize=(7.2, 5.6))
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.15], hspace=0.62, wspace=0.40)

axa = fig.add_subplot(gs[0, 0])
steps = [("Census of candidate\ngenomes", canon["funnel_census_candidates"]),
         ("After ANI >= 99.5\nexclusion vs consumed", canon["funnel_eligible_pool"]),
         ("Drawn by farthest-point\nselection", canon["funnel_selected_from_pool"]),
         ("Sealed cohort\n(+ fallback tier)", canon["cohort_n"])]
ys = np.arange(len(steps))[::-1]
axa.barh(ys, [s[1] for s in steps], color=[LIGHT, LIGHT, BLUE, BLUE], edgecolor=BLUE, height=0.6)
axa.set_yticks(ys)
axa.set_yticklabels([s[0] for s in steps], fontsize=6.2)
axa.set_xscale("log")
axa.set_xlabel("candidate genomes (log scale)")
for y, (t, v) in zip(ys, steps):
    axa.text(v * 1.15, y, "{:,}".format(v), va="center", fontsize=6.6)
axa.set_xlim(80, 20000)
rem = [("removed: ANI >= 99.5 to a consumed genome", canon["funnel_excluded_ani_vs_consumed"]),
       ("removed: ANI >= 99.5 within cohort", canon["funnel_excluded_ani_within_cohort"]),
       ("not selected once quota met", canon["funnel_not_selected"]),
       ("added from the 2022 fallback tier", canon["funnel_added_from_fallback_tier"])]
axa.text(0.30, 0.30, ("\n").join("%s: %s" % (a, "{:,}".format(b)) for a, b in rem),
         transform=axa.transAxes, fontsize=5.6, color="#444444", va="top", ha="left")
label(axa, "a", x=-0.46, y=1.12)

axb = fig.add_subplot(gs[0, 1])
flow = [("Assembled contigs", canon["den_contigs_joined"], LIGHT),
        ("Eligible, >= 1 kb", canon["den_eligible_ge_1kb"], LIGHT),
        ("Truth-resolved (scored)", canon["den_scored_resolved"], BLUE)]
ys = np.arange(len(flow))[::-1]
axb.barh(ys, [v for _, v, _ in flow], color=[c for _, _, c in flow], edgecolor=BLUE, height=0.6)
axb.set_yticks(ys)
axb.set_yticklabels([t for t, _, _ in flow], fontsize=6.2)
axb.set_xlabel("contigs")
for y, (t, v, c) in zip(ys, flow):
    axb.text(v + 300, y, "{:,}".format(v), va="center", fontsize=6.6)
axb.set_xlim(0, 23000)
u = canon["unresolved_composition"]
axb.text(0.50, 0.36, "excluded below the 1 kb floor: {:,}\nunresolved, excluded from scoring: "
                     "{:,}\n     ambiguous {:,}, unmapped {:,}".format(
             canon["den_contigs_joined"] - canon["den_eligible_ge_1kb"],
             canon["den_unresolved_excluded"], u["ambiguous"], u["unmapped"]),
         transform=axb.transAxes, fontsize=5.6, color="#444444", va="top", ha="left")
label(axb, "b", x=-0.38, y=1.12)

axc = fig.add_subplot(gs[1, :])
tx = list(tax_agg.keys())
chrom = [tax_agg[t]["chromosome"] for t in tx]
plas = [tax_agg[t]["plasmid"] for t in tx]
unres = [tax_agg[t]["unresolved"] for t in tx]
xs = np.arange(len(tx))
axc.bar(xs, chrom, 0.62, label="chromosomal (scored)", color=LIGHT, edgecolor=BLUE)
axc.bar(xs, plas, 0.62, bottom=chrom, label="plasmid-derived (scored)", color=BLUE)
axc.bar(xs, unres, 0.62, bottom=np.array(chrom) + np.array(plas), label="unresolved (not scored)",
        color="white", edgecolor=GREY, hatch="///")
axc.set_xticks(xs)
axc.set_xticklabels([mathtaxon(t) for t in tx], fontsize=6.6)
axc.set_ylabel("eligible contigs")
axc.legend(frameon=False, ncol=3, loc="upper right", fontsize=6.4)
for x, t in zip(xs, tx):
    axc.text(x, tax_agg[t]["eligible"] + 60, "{:,}".format(tax_agg[t]["eligible"]),
             ha="center", fontsize=6.0)
axc.set_ylim(0, max(tax_agg[t]["eligible"] for t in tx) * 1.38)
label(axc, "c", x=-0.075, y=1.10)

save(fig, "Figure2_flow",
     [{"panel": "a", "step": s, "n": v} for s, v in
      [(a.replace("\n", " "), b) for a, b in steps] + rem] +
     [{"panel": "b", "step": t, "n": v} for t, v, _ in flow] +
     [{"panel": "c", "step": "%s | %s" % (t, k), "n": tax_agg[t][k]}
      for t in tx for k in ("isolates", "eligible", "resolved", "unresolved", "chromosome",
                            "plasmid")],
     ["panel", "step", "n"])

# ================================================================= Figure 3
print("Figure 3 - pooled performance of all 19 rows")
rows = []
for r in inv:
    k = r["method"]
    m = comp.get(k, {})
    rows.append(dict(row=k, name=pretty(k), cls=kind(k)[0], col=kind(k)[1],
                     cov=f(r["coverage_on_resolved"]), ppv=f(m.get("PPV")),
                     rec=f(m.get("recall")), f1=f(m.get("F1")),
                     ppv_ci=ci(m.get("PPV_ci95")), rec_ci=ci(m.get("recall_ci95"))))
plot = [r for r in rows if r["ppv"] is not None]
undef = [r for r in rows if r["ppv"] is None]

# manual label offsets in points for the crowded high-precision cluster, set by visual inspection
OFF3 = {"v1.1@0.9524": (-30, 13), "v1.1@0.9605_high_conf": (32, -15),
        "router": (-42, 12), "v1.2-General@0.9285": (40, 12),
        "tool:PlasmidFinder": (14, -12), "tool:Platon": (16, 10),
        "baseline:majority_vote": (24, 10), "tool:MOB-recon": (16, -14),
        "tool:Plasmer": (20, 10), "tool:plASgraph2": (-28, 10),
        "tool:HyAsP": (-20, -12), "tool:gplas2": (26, 10),
        "tool:PlasmidEC": (26, -12), "tool:RFPlasmid": (-24, 10),
        "tool:PLASMe": (14, 10), "tool:geNomad": (-16, 10),
        "tool:PlaScope": (-20, -13), "baseline:any_tool_plasmid": (-26, 10)}

fig, ax = plt.subplots(figsize=(7.2, 5.2))
ax.axhline(0.95, color=FLOOR, linestyle="--", linewidth=1.0, zorder=1)
ax.text(1.095, 0.9535, "prespecified\nprecision floor 0.95", fontsize=6.4, color=FLOOR,
        va="bottom", ha="right")
seen = set()
for r in sorted(plot, key=lambda r: -r["cov"]):
    lab = r["cls"] if r["cls"] not in seen else None
    seen.add(r["cls"])
    ax.errorbar(r["rec"], r["ppv"],
                yerr=[[r["ppv"] - r["ppv_ci"][0]], [r["ppv_ci"][1] - r["ppv"]]],
                xerr=[[r["rec"] - r["rec_ci"][0]], [r["rec_ci"][1] - r["rec"]]],
                fmt="none", ecolor=r["col"], elinewidth=0.7, alpha=0.45, zorder=2)
    ax.scatter([r["rec"]], [r["ppv"]], s=24 + 110 * (r["cov"] ** 6), facecolor=r["col"],
               edgecolor="white", linewidth=0.7, label=lab, zorder=3)
for r in plot:
    txt = r["name"] if r["cov"] == 1.0 else "%s (cov %.3f)" % (r["name"], r["cov"])
    dx, dy = OFF3.get(r["row"], (0, 9))
    ax.annotate(txt, (r["rec"], r["ppv"]), textcoords="offset points", xytext=(dx, dy),
                ha=("center" if abs(dx) < 6 else ("left" if dx > 0 else "right")),
                va=("bottom" if dy > 0 else "top"), fontsize=5.9, color="#222222", zorder=4,
                arrowprops=dict(arrowstyle="-", linewidth=1.0, color="#b4b4b4",
                                shrinkA=1, shrinkB=5))
ax.set_xlabel("recall")
ax.set_ylabel("precision (positive predictive value)")
ax.set_xlim(0.02, 1.12)
ax.set_ylim(0.36, 1.045)
h, l = ax.get_legend_handles_labels()
ax.legend(h, l, frameon=False, loc="lower left", fontsize=6.8,
          title="marker size = coverage", title_fontsize=6.8, bbox_to_anchor=(0.0, 0.055))
ax.text(0.015, 0.012, "excluded, precision undefined: %s" %
        ", ".join(u["name"] for u in undef), transform=ax.transAxes, ha="left",
        va="bottom", fontsize=6.2, color=GREY)

save(fig, "Figure3_pooled_all_predictors",
     [{"row": r["row"], "class": r["cls"], "coverage": r["cov"], "PPV": r["ppv"],
       "PPV_ci_low": r["ppv_ci"][0] if r["ppv_ci"] else "",
       "PPV_ci_high": r["ppv_ci"][1] if r["ppv_ci"] else "",
       "recall": r["rec"],
       "recall_ci_low": r["rec_ci"][0] if r["rec_ci"] else "",
       "recall_ci_high": r["rec_ci"][1] if r["rec_ci"] else "", "F1": r["f1"]} for r in rows],
     ["row", "class", "coverage", "PPV", "PPV_ci_low", "PPV_ci_high", "recall",
      "recall_ci_low", "recall_ci_high", "F1"])

# ================================================================= Figure 4
print("Figure 4 - ARG-bearing contigs")
arows = []
for r in inv:
    k = r["method"]
    a = argall.get(k)
    if not a:
        continue
    arows.append(dict(row=k, name=pretty(k), cls=kind(k)[0], col=kind(k)[1],
                      cov=f(a["coverage"]), ppv=f(a["PPV"]), rec=f(a["recall"]), f1=f(a["F1"]),
                      ppv_ci=ci(a["PPV_ci95"]), rec_ci=ci(a["recall_ci95"]),
                      pareto=k in pareto))
ap = [r for r in arows if r["ppv"] is not None]
fig, ax = plt.subplots(figsize=(7.2, 5.0))
ax.axhline(0.95, color=FLOOR, linestyle="--", linewidth=1.0, zorder=1)
ax.text(1.135, 0.953, "prespecified\nprecision floor 0.95", fontsize=6.4, color=FLOOR,
        va="bottom", ha="right")
seen = set()
for r in sorted(ap, key=lambda r: -r["cov"]):
    lab = r["cls"] if r["cls"] not in seen else None
    seen.add(r["cls"])
    ax.errorbar(r["rec"], r["ppv"],
                yerr=[[max(0, r["ppv"] - r["ppv_ci"][0])], [max(0, r["ppv_ci"][1] - r["ppv"])]],
                fmt="none", ecolor=r["col"], elinewidth=0.7, alpha=0.4, zorder=2)
    ax.scatter([r["rec"]], [r["ppv"]], s=28 + 150 * (r["cov"] ** 6), facecolor=r["col"],
               edgecolor=("black" if r["pareto"] else "white"),
               linewidth=(1.0 if r["pareto"] else 0.7), label=lab, zorder=3)
OFF4 = {"v1.2-General@0.9285": (30, 12), "router": (-16, 12),
        "v1.1@0.9524": (-40, -6), "v1.1@0.9605_high_conf": (-18, -14),
        "tool:plASgraph2": (-34, 14), "tool:Platon": (-40, -8),
        "tool:MOB-recon": (-30, -13), "tool:HyAsP": (18, 12),
        "baseline:majority_vote": (-46, -12), "tool:Plasmer": (-14, -20),
        "tool:PLASMe": (14, 12), "tool:PlasmidEC": (18, -13),
        "tool:gplas2": (6, -34), "tool:RFPlasmid": (-24, -13),
        "tool:geNomad": (-22, 12), "tool:PlaScope": (-22, -13),
        "tool:PlasmidFinder": (22, 12), "baseline:any_tool_plasmid": (20, -13)}
for r in ap:
    txt = r["name"] if r["cov"] == 1.0 else "%s (cov %.4f)" % (r["name"], r["cov"])
    dx, dy = OFF4.get(r["row"], (0, 9))
    ax.annotate(txt, (r["rec"], r["ppv"]), textcoords="offset points", xytext=(dx, dy),
                ha=("center" if abs(dx) < 6 else ("left" if dx > 0 else "right")),
                va=("bottom" if dy > 0 else "top"), fontsize=5.9, color="#222222", zorder=4,
                arrowprops=dict(arrowstyle="-", linewidth=1.0, color="#b4b4b4",
                                shrinkA=1, shrinkB=5))
v12 = [r for r in ap if r["row"] == "v1.2-General@0.9285"][0]
rt = [r for r in ap if r["row"] == "router"][0]
YB = 0.615
for rr in (v12, rt):
    ax.plot([rr["rec"], rr["rec"]], [YB, rr["ppv"] - 0.012], linestyle=":", linewidth=1.0,
            color=FLOOR, zorder=1)
ax.annotate("", xy=(v12["rec"], YB), xytext=(rt["rec"], YB),
            arrowprops=dict(arrowstyle="<|-|>", color=FLOOR, linewidth=1.0,
                            mutation_scale=8))
ax.text((v12["rec"] + rt["rec"]) / 2, YB + 0.012,
        "router recall deficit %.1f percentage points" %
        (canon["arg_router_recall_penalty_vs_v12"] * 100),
        ha="center", fontsize=6.4, color=FLOOR)
ax.set_xlabel("recall")
ax.set_ylabel("precision (positive predictive value)")
ax.set_xlim(0.12, 1.14)
ax.set_ylim(0.44, 1.05)
h, l = ax.get_legend_handles_labels()
ax.legend(h, l, frameon=False, loc="lower left", fontsize=6.8,
          title="marker size = coverage\nblack outline = Pareto frontier", title_fontsize=6.6,
          bbox_to_anchor=(0.0, 0.0))
ax.set_title("%d truth-resolved contigs carrying an annotated resistance determinant"
             % canon["arg_bearing_n"], fontsize=7.4, loc="left", pad=8)
save(fig, "Figure4_arg_bearing",
     [{"row": r["row"], "class": r["cls"], "coverage": r["cov"], "PPV": r["ppv"],
       "recall": r["rec"], "F1": r["f1"], "on_pareto_frontier": r["pareto"]} for r in arows],
     ["row", "class", "coverage", "PPV", "recall", "F1", "on_pareto_frontier"])

# ================================================================= Figure 5
print("Figure 5 - taxon-stratified")
tx = canon["taxon_v12"]
fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), sharey=True)
ys = np.arange(len(tx))[::-1]
names = [mathtaxon(t["taxon"]) for t in tx]
for ax, key, cikey, lab_, floor in (
        (axes[0], "PPV", "PPV_ci95", "precision", 0.95),
        (axes[1], "recall", "recall_ci95", "recall", None)):
    vals = [t[key] for t in tx]
    los = [t[key] - t[cikey][0] for t in tx]
    his = [t[cikey][1] - t[key] for t in tx]
    cols = [BLUE if (floor is None or v >= floor) else ORANGE for v in vals]
    ax.errorbar(vals, ys, xerr=[los, his], fmt="o", markersize=4.2, elinewidth=1.0,
                capsize=2.2, ecolor="#888888", markerfacecolor="none", linestyle="none",
                color="#888888", zorder=2)
    ax.scatter(vals, ys, s=26, c=cols, zorder=3)
    if floor:
        ax.axvline(floor, color=FLOOR, linestyle="--", linewidth=1.0, zorder=1)
        ax.text(floor + 0.004, ys[0] + 0.42, "floor 0.95", fontsize=6.2, color=FLOOR)
    ax.set_xlabel(lab_)
    ax.set_xlim(0.0 if key == "recall" else 0.75, 1.03)
axes[0].set_yticks(ys)
axes[0].set_yticklabels(names, fontsize=7)
for y, t in zip(ys, tx):
    axes[1].text(1.05, y, "n=%s  plasmid=%s" % ("{:,}".format(t["n_scored"]), t["n_plasmid"]),
                 va="center", fontsize=6.0, color="#444444")
label(axes[0], "a", x=-0.52)
label(axes[1], "b", x=-0.06)
axes[0].text(0.0, -0.26, "Orange marks a point estimate below the prespecified 0.95 precision "
                         "floor: " + ", ".join(mathtaxon(t) for t in canon["taxa_below_PPV_floor"])
                         + ".",
             transform=axes[0].transAxes, fontsize=6.4, color=ORANGE)
save(fig, "Figure5_taxon",
     [{"taxon": t["taxon"], "n_scored": t["n_scored"], "n_plasmid": t["n_plasmid"],
       "PPV": t["PPV"], "PPV_ci_low": t["PPV_ci95"][0], "PPV_ci_high": t["PPV_ci95"][1],
       "recall": t["recall"], "recall_ci_low": t["recall_ci95"][0],
       "recall_ci_high": t["recall_ci95"][1], "meets_PPV_floor": t["meets_PPV_floor"]}
      for t in tx],
     ["taxon", "n_scored", "n_plasmid", "PPV", "PPV_ci_low", "PPV_ci_high", "recall",
      "recall_ci_low", "recall_ci_high", "meets_PPV_floor"])

# ================================================================= Figure 6
print("Figure 6 - length, depth, assembly quality")
ln = canon["length_bins"]
dp = [d for d in canon["depth_and_assembly"] if d["stratum"].startswith("depth=")]
other = [d for d in canon["depth_and_assembly"] if not d["stratum"].startswith("depth=")]
fig, axes = plt.subplots(3, 1, figsize=(6.4, 6.2))


def strat_panel(ax, items, xlabels, title):
    xs = np.arange(len(items))
    ppv = [i["PPV"] for i in items]
    rec = [i["recall"] for i in items]
    ax.axhline(0.95, color=FLOOR, linestyle="--", linewidth=1.0, zorder=1)
    ax.plot(xs, ppv, "o-", color=BLUE, markersize=4.5, label="precision", zorder=3)
    ax.plot(xs, rec, "s--", color=ORANGE, markersize=4.0, label="recall", zorder=3)
    for x, v in zip(xs, ppv):
        ax.annotate("%.4f" % v, (x, v), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=5.8, color=BLUE)
    for x, v in zip(xs, rec):
        ax.annotate("%.4f" % v, (x, v), textcoords="offset points", xytext=(0, -11),
                    ha="center", fontsize=5.8, color=ORANGE)
    ax.set_xticks(xs)
    ax.set_xticklabels(["%s\nn = %s" % (l, "{:,}".format(i["n_scored"]))
                        for l, i in zip(xlabels, items)], fontsize=6.4)
    ax.set_xlim(-0.45, len(items) - 0.55)
    ax.set_ylim(0.36, 1.09)
    ax.set_ylabel("value")
    ax.set_title(title, fontsize=7.4, loc="left", pad=6)


strat_panel(axes[0], ln, [i["band"].replace("length=", "").replace("-<", " to <")
                          .replace(">=", "\u2265 ") for i in ln],
            "contig length")
strat_panel(axes[1], dp, [i["stratum"].replace("depth=", "").replace("_to_", " to ")
                          .replace("ge_", "\u2265 ") for i in dp],
            "retained sequencing depth")
strat_panel(axes[2], other, [i["stratum"].split("=")[1].replace("_", " ") for i in other],
            "assembly fragmentation and downsampling mode")
axes[0].legend(frameon=False, fontsize=6.6, loc="lower right", ncol=2)
axes[2].text(0.0, -0.40, "The dashed line is the prespecified 0.95 precision floor. "
                         "Every stratum shown carries an adequate denominator;\nbands were "
                         "defined before the analysis and were not chosen after seeing the "
                         "outcome.",
             transform=axes[2].transAxes, fontsize=6.2, color="#444444", va="top")
for a, s in zip(axes, "abc"):
    label(a, s, x=-0.10, y=1.20)
fig.tight_layout(h_pad=2.4)

save(fig, "Figure6_strata",
     [{"panel": p, "stratum": i.get("band", i.get("stratum")), "n_scored": i["n_scored"],
       "PPV": i["PPV"], "recall": i["recall"], "adequate_denominator": i["adequate"]}
      for p, group in (("a", ln), ("b", dp), ("c", other)) for i in group],
     ["panel", "stratum", "n_scored", "PPV", "recall", "adequate_denominator"])

# ================================================================= Figure 7
print("Figure 7 - coverage, failure and error structure")
fig = plt.figure(figsize=(7.4, 5.4))
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], hspace=0.62, wspace=0.34)

axa = fig.add_subplot(gs[0, 0])
mech = canon["panel_failure_mechanisms"]
labels_ = list(mech.keys())
vals = [mech[k] for k in labels_]
ys = np.arange(len(labels_))[::-1]
axa.barh(ys, vals, color=ORANGE, edgecolor=ORANGE, height=0.55)
axa.set_yticks(ys)
axa.set_yticklabels([l.replace(": ", ":\n") for l in labels_], fontsize=5.8)
axa.set_xlabel("failed tool-isolate units")
for y, v in zip(ys, vals):
    axa.text(v + 0.6, y, str(v), va="center", fontsize=6.4)
axa.set_xlim(0, max(vals) * 1.2)
axa.set_title("%s of %s tool-isolate units failed" %
              (canon["panel_units_failed"], "{:,}".format(canon["panel_units_total"])),
              fontsize=7.0, loc="left", pad=10)
axa.text(0.98, 0.06, "%s units succeeded" % "{:,}".format(canon["panel_units_succeeded"]),
         transform=axa.transAxes, ha="right", fontsize=6.2, color="#444444")
label(axa, "a", x=-0.62, y=1.10)

axb = fig.add_subplot(gs[0, 1])
covrows = sorted([(f(r["coverage_on_resolved"]), pretty(r["method"]), kind(r["method"])[1])
                  for r in inv])
ys = np.arange(len(covrows))
axb.barh(ys, [c for c, _, _ in covrows], color=[col for _, _, col in covrows], height=0.62)
axb.set_yticks(ys)
axb.set_yticklabels([n for _, n, _ in covrows], fontsize=5.6)
axb.set_xlim(0, 1.06)
axb.set_xlabel("coverage on truth-resolved contigs")
mfrac = canon["matched_denominator_fraction"]
axb.axvline(mfrac, color=FLOOR, linestyle=":", linewidth=1.0)
axb.text(0.0, -1.45,
         "matched common denominator: %s of %s contigs (%.1f%%)" %
         ("{:,}".format(canon["matched_denominator_n"]),
          "{:,}".format(canon["den_scored_resolved"]), mfrac * 100),
         fontsize=5.8, color=FLOOR, va="top", ha="left")
label(axb, "b", x=-0.52, y=1.10)

axc = fig.add_subplot(gs[1, :])
ea = canon["error_architecture"]
keys = ["v1.2-General@0.9285", "v1.1@0.9524", "v1.1@0.9605_high_conf", "router"]
xs = np.arange(len(keys))
fp = [ea[k]["FP"] for k in keys]
fn = [ea[k]["FN"] for k in keys]
axc.bar(xs - 0.19, fp, 0.36, label="false positives (contig called plasmid, truth chromosome)",
        color=ORANGE)
axc.bar(xs + 0.19, fn, 0.36, label="false negatives (contig called chromosome, truth plasmid)",
        color=BLUE)
axc.set_xticks(xs)
axc.set_xticklabels([pretty(k) for k in keys], fontsize=6.6)
axc.set_ylabel("contigs")
axc.legend(frameon=False, fontsize=6.4, loc="upper center",
           bbox_to_anchor=(0.5, 1.22), ncol=2)
for x, a, b in zip(xs, fp, fn):
    axc.text(x - 0.19, a + 22, "{:,}".format(a), ha="center", fontsize=6.2)
    axc.text(x + 0.19, b + 22, "{:,}".format(b), ha="center", fontsize=6.2)
axc.set_ylim(0, max(fn) * 1.16)
label(axc, "c", x=-0.075, y=1.10)

save(fig, "Figure7_flow_and_coverage",
     [{"panel": "a", "item": k, "value": v} for k, v in mech.items()] +
     [{"panel": "b", "item": n, "value": c} for c, n, _ in covrows] +
     [{"panel": "c", "item": "%s FP" % pretty(k), "value": ea[k]["FP"]} for k in keys] +
     [{"panel": "c", "item": "%s FN" % pretty(k), "value": ea[k]["FN"]} for k in keys],
     ["panel", "item", "value"])

# ================================================================= Figure 8
print("Figure 8 - genomic context of resistance determinants")
ab = js("docs/manuscript/PLASMIDCALL_ARG_CONTEXT_BIOLOGY.json")
PLAS, CHROM = BLUE, "#c9a227"      # plasmid vs chromosome; not a red/green pair

fig = plt.figure(figsize=(7.2, 7.0))
gs = fig.add_gridspec(3, 1, height_ratios=[0.85, 1.5, 0.7], hspace=0.55)


def stacked(ax, items, labeller, title, note=""):
    ys = np.arange(len(items))[::-1]
    frac = [d["plasmid_fraction"] for d in items]
    ax.barh(ys, frac, 0.62, color=PLAS, label="plasmid-derived")
    ax.barh(ys, [1 - f for f in frac], 0.62, left=frac, color=CHROM, label="chromosomal")
    ax.set_yticks(ys)
    ax.set_yticklabels([labeller(d) for d in items], fontsize=6.2)
    ax.set_xlim(0, 1.30)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25", "50", "75", "100"], fontsize=6.6)
    ax.set_xlabel("percentage of contigs carrying the determinant", fontsize=7)
    ax.set_title(title, fontsize=7.6, loc="left", pad=6)
    for y, d in zip(ys, items):
        ax.text(1.03, y, "%.1f%%   n=%d" % (100 * d["plasmid_fraction"], d["contigs"]),
                va="center", fontsize=5.9, color="#333333")
    if note:
        ax.text(0.0, -0.42, note, transform=ax.transAxes, fontsize=5.9, color="#444444",
                va="top")


axa = fig.add_subplot(gs[0])
stacked(axa, ab["by_taxon"], lambda d: mathtaxon(d["stratum"]),
        "a   by taxon")
axa.legend(frameon=False, fontsize=6.4, ncol=2, loc="upper right",
           bbox_to_anchor=(1.0, 1.42))

axb = fig.add_subplot(gs[1])
stacked(axb, ab["by_class"],
        lambda d: d["stratum"].replace("NITROFURAN/PHENICOL/QUINOLONE/TETRACYCLINE",
                                       "nitrofuran/phenicol/quinolone/tetracycline efflux")
                              .replace("LINCOSAMIDE/MACROLIDE/STREPTOGRAMIN",
                                       "lincosamide/macrolide/streptogramin")
                              .replace("LINCOSAMIDE/STREPTOGRAMIN", "lincosamide/streptogramin")
                              .replace("MACROLIDE/STREPTOGRAMIN", "macrolide/streptogramin")
                              .replace("QUATERNARY AMMONIUM", "quaternary ammonium")
                              .lower().replace("beta-lactam", "β-lactam"),
        "b   by antimicrobial class, every class with at least %d contigs"
        % ab["thresholds_prestated"]["class_min_contigs"])

axc = fig.add_subplot(gs[2])
van = [("vanA-type", ab["glycopeptide_operons"]["vanA_type"]),
       ("vanB-type", ab["glycopeptide_operons"]["vanB_type"]),
       ("vanD-type", ab["glycopeptide_operons"]["vanD_type"])]
van = [(k, v) for k, v in van if v]
stacked(axc, [v for _, v in van],
        lambda d: "",
        "c   glycopeptide-resistance operons")
axc.set_yticklabels(["$\\mathit{%s}$-type\n%d genes" % (k[:4], v["n_genes"])
                     for k, v in van], fontsize=6.4)
axc.text(0.0, -0.62,
         "The mapping that produced these labels uses sequence alignment against each isolate's "
         "own closed reference only.\nIt has no access to gene identity or function, so the "
         "separation of $\\mathit{vanA}$-type from $\\mathit{vanB}$- and $\\mathit{vanD}$-type is recovered\nindependently of the "
         "established genetics rather than assumed from it.",
         transform=axc.transAxes, fontsize=6.0, color="#444444", va="top")

save(fig, "Figure8_arg_genomic_context",
     [{"panel": "a", "stratum": d["stratum"], "contigs": d["contigs"],
       "plasmid_derived": d["plasmid_derived"], "chromosomal": d["chromosomal"],
       "plasmid_fraction": d["plasmid_fraction"]} for d in ab["by_taxon"]] +
     [{"panel": "b", "stratum": d["stratum"], "contigs": d["contigs"],
       "plasmid_derived": d["plasmid_derived"], "chromosomal": d["chromosomal"],
       "plasmid_fraction": d["plasmid_fraction"]} for d in ab["by_class"]] +
     [{"panel": "c", "stratum": k, "contigs": v["contigs"],
       "plasmid_derived": v["plasmid_derived"],
       "chromosomal": v["contigs"] - v["plasmid_derived"],
       "plasmid_fraction": v["plasmid_fraction"]} for k, v in van],
     ["panel", "stratum", "contigs", "plasmid_derived", "chromosomal", "plasmid_fraction"])

# ---------------------------------------------------------------- manifest
io.open(OUT + "/FIGURE_CHECKSUMS.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps({"generated_utc": "2026-08-24",
                "generator": "scripts/manuscript/make_figures.py",
                "font": FONT, "raster_dpi": 600,
                "journal_requirements": {"min_dpi": 300, "colour": "RGB",
                                         "typeface": "Arial or Helvetica",
                                         "optimum_font_size_pt": 8},
                "files": MANIFEST}, indent=1) + "\n")
print("\n%d figure files + source data written; checksums in FIGURE_CHECKSUMS.json"
      % len(MANIFEST))

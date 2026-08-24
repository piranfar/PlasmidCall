# P1.13 final evaluation report

**Dated** 2026-08-24 · **Freeze** `P1.13-PREDICTION-FREEZE-001` · **Join** `P1.13-TRUTH-JOIN-001`
**Verifier** `VERIFIER_PASS` — 176 values independently recomputed, **0 disagreements**

> **Correction notice.** Values in this document follow
> [`PLASMIDCALL_CORRECTION_ADDENDUM.md`](../../corrections/PLASMIDCALL_CORRECTION_ADDENDUM.md).
> Frozen artefacts are never edited; the addendum is the correction of record.

All values below are rederived from `P113_TRUTH_JOINED.tsv` by an independent verifier that does
not share code with the evaluation that produced the metric tables.

---

## 1. Denominators

| Quantity | Value |
|---|---|
| Isolates | 150 (cohort v3, 25 × 6 taxa) |
| Contigs joined | 19,320 |
| Eligible ≥ 1 kb | 9,784 |
| **Scored (RESOLVED truth)** | **9,371** |
| Unresolved, excluded from scoring | 413 (300 ambiguous, 113 unmapped) |
| Truth composition (scored) | 7,130 chromosome · 2,241 plasmid |

Truth join accounting was exact: 19,320 predictions ↔ 19,320 truth mappings, **0 records on
either side only, 0 duplicates, nothing silently dropped**. Unresolved contigs are recorded with
an explicit state and are never coerced to a label.

## 2. Primary endpoint — MET

**v1.2-General at the frozen threshold 0.9285, over all scored eligible contigs:**

| Metric | Value | 95 % CI (isolate-clustered, 4,000 replicates) |
|---|---|---|
| **PPV** | **0.9770** | **0.9642 – 0.9872** |
| **Recall** | **0.6631** | 0.6205 – 0.7052 |
| Specificity | 0.9953 | — |
| NPV | 0.9036 | — |
| F1 | 0.7900 | — |
| Balanced accuracy | 0.8292 | — |
| MCC | 0.7614 | — |
| Coverage | 1.0000 | zero abstentions |
| TP / FP / TN / FN | 1,486 / 35 / 7,095 / 755 | |

Predeclared requirement: **PPV ≥ 0.95 AND recall > 0.50**. Both are met, and critically the
**CI lower bound (0.9642) clears the 0.95 floor** — the exact point the frozen design warned was
narrow. P(PPV ≥ 0.95) = 0.9998 across bootstrap replicates.

## 3. The central comparative result

| Predictor | Coverage | PPV | Recall | F1 | MCC |
|---|---|---|---|---|---|
| **v1.2-General** | 1.000 | **0.9770** | 0.6631 | 0.7900 | 0.7614 |
| router | 1.000 | 0.9812 | 0.6042 | 0.7479 | 0.7229 |
| v1.1 @0.9524 | 1.000 | 0.9706 | 0.2798 | — | — |
| v1.1 @0.9605 | 1.000 | 0.9707 | 0.2512 | 0.3991 | 0.4405 |
| majority vote (baseline) | 1.000 | 0.8978 | 0.9054 | 0.9016 | 0.8704 |
| Plasmer | 1.000 | 0.8496 | 0.9603 | 0.9016 | 0.8710 |
| MOB-recon | 0.909 | 0.8860 | 0.8358 | 0.8602 | 0.8127 |
| Platon | 1.000 | 0.9363 | 0.7800 | 0.8510 | 0.8151 |
| gplas2 | 0.791 | 0.7571 | 0.9082 | 0.8258 | 0.7618 |
| PlasmidEC | 1.000 | 0.7279 | 0.9014 | 0.8054 | 0.7432 |
| PLASMe | 1.000 | 0.6496 | 0.9777 | 0.7805 | 0.7215 |
| plASgraph2 | 0.942 | 0.8754 | 0.6771 | 0.7636 | 0.7171 |
| HyAsP | 1.000 | 0.8446 | 0.6890 | 0.7589 | 0.6987 |
| RFPlasmid | 1.000 | 0.6660 | 0.8407 | 0.7432 | 0.6579 |
| PlaScope | 0.633 | 0.4986 | 0.9347 | 0.6503 | 0.5598 |
| geNomad | 1.000 | 0.6075 | 0.6243 | 0.6158 | 0.4928 |
| any-tool-plasmid (baseline) | 1.000 | 0.4186 | 0.9933 | 0.5890 | 0.4818 |
| PlasmidFinder | 0.976 | 0.9148 | 0.1324 | 0.2313 | 0.2997 |

**Two facts define the result, and both must be reported together:**

1. **Six comparators achieve a higher F1 than v1.2-General** (Plasmer, majority vote, MOB-recon,
   Platon, gplas2, PlasmidEC). PlasmidCall is **not** the best method by F1 and must not be
   presented as such.
2. **No comparator or baseline reaches PPV ≥ 0.95.** The highest comparator precision is Platon at
   0.9363; the best-F1 methods sit at 0.85–0.90. v1.2-General is the **only** evaluated strategy
   that satisfies the predeclared precision requirement, and it does so while retaining recall of
   0.66 at complete coverage.

This reproduces, in a second and larger independent cohort, the operating-point argument
established in P1.11.

## 4. Paired isolate-clustered contrasts

| Contrast | ΔPPV [95 % CI] | ΔRecall [95 % CI] |
|---|---|---|
| v1.2-General − v1.1 | +0.0064 [−0.0085, +0.0229] | **+0.3833 [+0.3190, +0.4455]** |
| v1.2-General − router | −0.0042 [−0.0090, −0.0004] | **+0.0589 [+0.0436, +0.0765]** |
| v1.1 − router | −0.0106 [−0.0265, +0.0029] | −0.3244 [−0.3794, −0.2676] |

v1.2-General gains large, significant recall over v1.1 at indistinguishable precision. Against the
router it trades a precision difference of 0.4 percentage points (statistically distinguishable but
small) for a significant recall gain.

## 5. ARG-bearing contigs — the operationally relevant subset

n = 635 scored ARG-bearing contigs.

| Model | PPV | Recall |
|---|---|---|
| **v1.2-General** | 0.9409 | **0.7782** |
| v1.1 | 0.9494 | 0.2820 |
| **router** | 0.9494 | **0.2820** |
| (non-ARG contigs, n = 8,736) | v1.2 0.9831 / router 0.9831 | 0.6476 / 0.6476 |

**Two findings here are material and must not be softened:**

* The **router recovers less than half** the plasmid-borne ARG contigs that v1.2-General does
  (recall 0.2820 vs 0.7782), because it routes exactly this subset to the high-precision v1.1
  pathway. This independently reproduces the P1.11 result and confirms that **the router should
  not be recommended for ARG-plasmid surveillance.**
* **On this subset neither strategy reaches PPV 0.95** (0.9409 and 0.9494). The primary endpoint
  is met over the whole eligible cohort, but the precision floor is *not* met on the ARG-bearing
  subset specifically. This is the most important qualification of the entire study and belongs in
  the abstract, not a supplementary note.

## 6. Per-taxon generalization (v1.2-General)

| Taxon | n | plasmid | PPV | Recall |
|---|---|---|---|---|
| *Klebsiella pneumoniae* | 1,904 | 676 | 0.9982 | 0.8136 |
| *Enterococcus faecium* | 3,077 | 851 | 0.9898 | 0.5711 |
| *Serratia* spp. | 992 | 44 | 0.9545 | 0.4773 |
| *Citrobacter* spp. | 1,540 | 379 | 0.9462 | 0.6966 |
| *Enterobacter* spp. | 1,021 | 150 | 0.9358 | 0.6800 |
| ***Enterococcus faecalis*** | 837 | 141 | **0.9130** | **0.4468** |

Precision holds ≥ 0.91 in every taxon, but **three taxa fall below the 0.95 floor**
(*Citrobacter* 0.9462, *Enterobacter* 0.9358, *E. faecalis* 0.9130) and recall varies more than
two-fold across taxa (0.4468 to 0.8136). **Cross-taxon universality is therefore not supported** and must not be
claimed. *E. faecalis* is the weakest domain on both axes, consistent with its predeclared
description as a hard Gram-positive validation domain.

## 7. Error architecture

| Model | FP | FN |
|---|---|---|
| v1.2-General | 35 | 755 |
| v1.1 | 19 | 1,614 |
| router | 26 | 887 |

Errors are overwhelmingly false negatives — the selective, precision-first design converts
uncertainty into missed plasmid calls rather than wrong ones, which is the intended behaviour for
surveillance triage. Full per-contig catalogue in `P113_ERROR_CATALOGUE.tsv` (3,336 rows) with
length, taxon, depth stratum, ARG status, panel agreement and truth confidence for each error.

## 8. Prespecified strata delivered

69 stratified rows across taxon, ARG-bearing status, contig length (1–5 kb, 5–20 kb, 20–100 kb,
≥ 100 kb), retained depth (4 strata), downsample mode, assembly fragmentation (tertiles),
tool-failure pattern and database representation — each for all three models, with denominators,
isolate counts and an explicit `adequate_denominator` flag. Strata with fewer than 20 plasmid
contigs or fewer than 100 contigs are flagged **SMALL DENOMINATOR — interval unstable, do not
over-read** and are not smoothed.

## 9. Continuous-score restriction honoured

PR-AUC is reported only for v1.1, v1.2-General and the router, whose continuous scores were frozen
before truth access. All twelve panel tools and all baselines emit fixed categorical calls; they
carry an explicit `curve_note` recording that no PR or calibration curve is produced for them.

## 10. Scenario assessment

**Scenario A — the primary endpoint is met — with one material qualification.**

The whole-cohort primary endpoint passes on both criteria with the CI lower bound clearing the
floor. The distinguishing claim is confirmed: PlasmidCall is the only evaluated strategy reaching
PPV ≥ 0.95, while six comparators beat it on F1. But the ARG-bearing subset, which is the actual
surveillance use case, does **not** reach the precision floor (0.9409), and three of six taxa fall
below it. The honest framing is a method with a demonstrated high-precision operating point whose
applicability boundary is now measured rather than assumed.

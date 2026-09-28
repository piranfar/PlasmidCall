# Frozen models

This directory holds the two frozen PlasmidCall models. Neither model was retuned or given a new
threshold after it was frozen. v1.1 was re-fitted deterministically once, in P1.11, from its
frozen specification, and the refit reproduced the frozen scores exactly (see below). To score a
table of tool calls with them, use
`scripts/score/plasmidcall_score.py` (see `scripts/score/README.md`).

Both models classify one contig from the calls of the same 12 plasmid classifiers, in this
order: HyAsP, MOB-recon, PLASMe, PlaScope, Plasmer, PlasmidEC, PlasmidFinder, Platon, RFPlasmid,
geNomad, gplas2, plASgraph2. Each call is one of seven states: `chromosome`, `plasmid`,
`unknown`, `unclassified`, `repeat`, `FAILED`, `MISSING`. A score below the threshold means
`not_selected`: no positive plasmid evidence. It is never a chromosome call.

The model cards are in `docs/model_cards/`. The router that combines the two models is
described in `docs/model_cards/MODEL_CARD_router_NOT_RECOMMENDED.md`.

## PlasmidCall v1.2-General

**What it is.** A standardised logistic regression over the 12 categorical calls. The encoding
has 102 features: a one-hot block of 7 columns per tool, one abstention indicator per tool, and
6 panel counts (`n_plasmid`, `n_chrom`, `n_valid`, `frac_plasmid`, `frac_chrom`, `agreement`).
When no tool votes chromosome or plasmid (`n_valid` = 0), the three fractions are 0.0. A tool in
a state that did not occur in training has its 8 columns set to the training means, so its
contribution to the logit is exactly 0.0. The panel counts still show the smaller panel.
The full encoding is in `P1.12_V1.2_ENCODING_SPEC.json`.

**Inputs.** The 12 calls only. No length or assembly feature.

**Threshold.** 0.9285: a probability at or above it is `plasmid_selected`.

**Training data.** 3,811 contigs from 39 *Escherichia coli* isolates (the P1.10 CP2 set), as
recorded in `P1.12_V1.2_TRAINING_RECEIPT.json`. The validated training claim is therefore
*E. coli*-specific.

**Runtime.** `P1.12_V1.2_MODEL_PORTABLE.json` holds every parameter as plain numbers: intercept,
coefficients, scaler means and scales, the states seen per tool in training, and the neutral
values. Scoring from it needs only numpy. The pickle holds the fitted scikit-learn pipeline
with the same parameters and needs scikit-learn 1.9.0.

| File | Bytes | sha256 (LF) |
|---|---|---|
| `plasmidcall_v1.2-general/P1.12_V1.2_MODEL_PORTABLE.json` | 12247 | `b2f00ee8a4668747e87d55e7abf2d6788656975c0fa40832cab621527bcc87a1` |
| `plasmidcall_v1.2-general/P1.12_V1.2_ENCODING_SPEC.json` | 3152 | `412eb43fac3573890187e3e4be75f99f4c8179dac957d5c69b3df370270ef12e` |
| `plasmidcall_v1.2-general/P1.12_V1.2_TRAINING_RECEIPT.json` | 1838 | `8d12111a8b23c5baf5bb305e85639f4391571b0cec7f5c33cf21d9f7cb4165a0` |
| `plasmidcall_v1.2-general/P1.12_V1.2_COEFFICIENTS.tsv` | 8530 | `b46b4416919f0509ff3de3c8acb7fd0e30a0645ac7b4e3f235eb57dd222bc6aa` |
| `plasmidcall_v1.2-general/P1.12_V1.2_FEATURE_DICTIONARY.tsv` | 15342 | `6686e410d74f219b4a4eebce2da968b50c13ea77353df989a909a877c28b0ef0` |
| `plasmidcall_v1.2-general/plasmidcall_v1_2_general.pkl` | 10073 | `f5d1cd1202b5077030a4512fb0c801abbdf39998b7c170acade03c268d68d74d` |

## PlasmidCall v1.1

**What it is.** A scikit-learn pipeline: a one-hot encoder for the 12 calls
(`handle_unknown="ignore"`, `min_frequency=5`), a median imputer and standard scaler for 22
numeric features, and a `HistGradientBoostingClassifier` (`max_depth=3`, `max_iter=200`,
`learning_rate=0.06`, `min_samples_leaf=25`, `l2_regularization=1.0`,
`random_state=20260816`). The design matrix has 51 columns.

**Inputs.** The 12 calls, the contig length, and the number of contigs of at least 1 kb in the
contig's sample. `FAILED` and `MISSING` are recoded to `unknown` before encoding. The exact
inputs, and why the input table must hold every contig of at least 1 kb of each sample, are in
`plasmidcall_v1.1/V1.1_INPUT_SPEC.md`.

**Thresholds.** 0.9524 (standard, `plasmid_selected`) and 0.9605 (`high_confidence_plasmid`).

**Training data.** The 1,460 resistance-gene-bearing contigs (280 plasmid, 1,180 not plasmid) of
the sealed development bundle from the 250-genome DEV_250 development set, which spans seven
genera. The estimator was refitted from that bundle by `scripts/evaluation/v11_scorer_p111.py`
and matched the historical P1.10 scores exactly on 10,332 rows
(`docs/evidence/P1.11_V11_RECONSTRUCTION_RECEIPT.json`). The development bundle is not in this
repository.

**Runtime.** v1.1 exists only as a pickle. There is no portable form.

| File | Bytes | sha256 |
|---|---|---|
| `plasmidcall_v1.1/plasmidcall_v1_1_m2.pkl` | 167815 | `6c179825a6c608d0468d36c37e08d2511485f18a5c38d4c7369c93b12498c50f` |

## Digests and line endings

The sha256 values above are taken over the bytes a git checkout gives. `.gitattributes` stores
text files with LF line endings. They equal the `sha256_canonical_lf` values in
`docs/evidence/P1.11_PRE_JOIN_HASH_RECEIPT_v2.json`.

`docs/evidence/P1.12_PRE_JOIN_HASH_RECEIPT.md` quotes different digests and sizes for three JSON
files. Those were taken from a working copy with CRLF line endings. The content is the same
apart from line endings.

| File | CRLF digest in the P1.12 receipt | LF digest (checkout) |
|---|---|---|
| `P1.12_V1.2_ENCODING_SPEC.json` | `13b5701c...` (3233 bytes) | `412eb43f...` (3152 bytes) |
| `P1.12_V1.2_MODEL_PORTABLE.json` | `0fbb44c9...` (13110 bytes) | `b2f00ee8...` (12247 bytes) |
| `P1.12_V1.2_TRAINING_RECEIPT.json` | `5371bbb7...` (1940 bytes) | `8d12111a...` (1838 bytes) |

`docs/closure/P113_CANONICAL_ARTEFACT_INVENTORY.tsv` quotes the same CRLF digest for
`P1.12_V1.2_MODEL_PORTABLE.json`. The frozen receipts are left as they were.

To check a checkout:

```bash
sha256sum models/plasmidcall_v1.1/*.pkl models/plasmidcall_v1.2-general/*
```

## scikit-learn version and pickle safety

Both pickles were written by scikit-learn 1.9.0 and record that version inside the file. They
also refer to `numpy._core`, which exists only from numpy 2. Load them only with
scikit-learn 1.9.0 and numpy 2 or later. The P1.13 frozen prediction table was produced with
Python 3.14.6, numpy 2.5.0, scikit-learn 1.9.0 and pandas 3.0.3. Another scikit-learn version may load a
pickle and still give different scores. The scorer refuses to load the v1.1 pickle in any other
environment.

Unpickling a file can run arbitrary code. Load a pickle only from this repository, and only
after its sha256 matches the table above. The scorer does both checks before it calls
`pickle.load`. For v1.2-General, prefer the portable JSON, which needs no pickle.

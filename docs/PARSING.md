# Parsing panel outputs into PlasmidCall calls

PlasmidCall does not read the 12 panel tools' native outputs directly. A frozen parser first
turns each tool's output into one call per contig, drawn from a seven-state vocabulary. The
models then score those calls. This page describes that parser, how each state arises, and how
to run it on your own outputs.

## Files

| Path | What it is |
|---|---|
| `scripts/parsers/frozen/parsers.py` | The frozen parser, version `p19c4-parsers/1.7`. One function per tool. Byte-identical to the copy that ran. Do not edit. |
| `scripts/parsers/frozen/parse_all.py` | The frozen driver that ran for the P1.13 evaluation. Byte-identical. Do not edit. |
| `scripts/parsers/parse_outputs.py` | A command-line driver for the frozen parser. Standard library only. |
| `scripts/parsers/tests/test_parse_outputs.py` | A self-test on synthetic inputs. It checks `parse_outputs.py` against the frozen driver. |
| `scripts/parsers/tests/check_parse_all_provenance.py` | A check that `parse_all.py` is the recorded P1.10 driver with five lines changed. Needs no data. |

`parse_all.py` cannot be pointed at your data without editing it. It hard-codes its paths
(`<root>/p113/assemblies/shortread` and `<root>/p113/inference`) and does its work at import
time. `parse_outputs.py` therefore imports the frozen `parsers.py` unchanged and repeats the
driver's loop, with paths taken from the command line. For the same inputs it writes the same
rows, in the same order, with the same bytes. The checks below show this.

## Provenance

| File | sha256 | Version |
|---|---|---|
| `parsers.py` | `68599a94af066f2dd1437de4ab307721ce8310399e0ba6fa91f2e559b65467b1` | `p19c4-parsers/1.7` |
| `parse_all.py` | `b3230949b062c48b82c84a63debe4b5ef14cb04d294aa36c032b2fc91cbc0077` | P1.13 driver |

- Both files were copied from member `env/` of `PlasmidCall_evidence_tier1_execution.tar.zst`
  (Part 1 of the data deposit, doi:10.5281/zenodo.22086357). That archive's sha256 is
  `4531ff03c25a020016d0d31f41bcea4c47c7b7fdb5adfef7ee94771b1f053c65`, as listed in the
  deposit's `MANIFEST.sha256`. The archive's own `P1.13_EVIDENCE_MANIFEST.sha256` lists both
  files with the digests above.
- `parsers.py` has the same digest in
  `docs/evidence/preflight_evidence/P1.10_ASEXECUTED_ENV_MANIFEST.json` and
  `docs/evidence/preflight_evidence/P1.11_DERIVED_RUNNER_RECEIPT.json`. Those receipts record
  that the same parser file ran in the P1.10, P1.11 and P1.13 phases.
- `parse_all.py` was derived from the P1.10 driver (sha256
  `1368faa316e10268a429952b40dbb9cefe2f9df5868849e02f6df9650d3a333a`, recorded in
  `P1.10_ASEXECUTED_ENV_MANIFEST.json`) by path substitution only. Five lines differ. Three
  (lines 7, 15 and 19) change the path token `p110` to `p113`, and two (lines 41 and 43) change
  the output file names from `P1.10_` to `P1.13_`. The parsing logic is the same.
- No record in this repository from before v1.1.0 holds the digest `b3230949...`. The byte
  identity with the deposit copy can be checked only against the deposit. The derivation above
  can be checked here, without the deposit:

  ```
  python -B scripts/parsers/tests/check_parse_all_provenance.py
  ```

  It reads the frozen `parse_all.py`, applies the reverse of the five-line change in memory, and
  requires the result to have the P1.10 digest `1368faa3...` from
  `P1.10_ASEXECUTED_ENV_MANIFEST.json`. It also requires that the P1.13 tokens appear on those
  five lines only, and that the recorded P1.11 derivation (`p110` to `p112` on the three path
  lines) turns the rebuilt driver into the P1.11 driver, `6370f437...`, recorded in
  `docs/evidence/preflight_evidence/P1.11_DERIVED_RUNNER_RECEIPT.json`. It writes nothing.
  Expected result: `8 checks, 8 passed, 0 failed`.
- `parse_outputs.py` checks both digests before it parses anything and stops if either
  differs. A line-ending conversion is the usual cause. The repository's `.gitattributes`
  keeps both files with LF line ends.

## Input layout

This is the layout the frozen runs used. `scripts/evaluation/p113_tool.sh` shows the exact
command that produced each tool's output and its receipt.

```
<assemblies>/<sample>/shortread.fasta          the contig universe and contig lengths
<native>/<tool>/<sample>/...                   each tool's native output directory
<receipts>/<tool>__<sample>.json               run receipt; its "status" field is "OK" or not
<receipts>/<tool>__<sample>.SHA256SUMS         optional; hashed into the native_sha256sums column
```

`<tool>` is the runner key. The table gives each runner key with its display name.

| Runner key | Display name | Long-table order | Wide-table tool column |
|---|---|---:|---:|
| `mobsuite` | MOB-recon | 1 | 2 |
| `platon` | Platon | 2 | 8 |
| `rfplasmid` | RFPlasmid | 3 | 9 |
| `plascope` | PlaScope | 4 | 4 |
| `plasmidec` | PlasmidEC | 5 | 6 |
| `plasmidfinder` | PlasmidFinder | 6 | 7 |
| `genomad` | geNomad | 7 | 10 |
| `plasme` | PLASMe | 8 | 3 |
| `plasmer` | Plasmer | 9 | 5 |
| `gplas2` | gplas2 | 10 | 11 |
| `plasgraph2` | plASgraph2 | 11 | 12 |
| `hyasp` | HyAsP | 12 | 1 |

There are two tool orders. The long table lists tools in the order of `parsers.PARSERS`. The
wide table uses the order frozen into both encoders (`TOOL_ORDER` in
`scripts/evaluation/freeze_v12.py`, `TOOLS` in `scripts/evaluation/v11_scorer_p111.py`):
HyAsP, MOB-recon, PLASMe, PlaScope, Plasmer, PlasmidEC, PlasmidFinder, Platon, RFPlasmid,
geNomad, gplas2, plASgraph2. Both encoders expect the tools in that order.

The contig universe is the assembly FASTA. A contig id is the first whitespace-separated token
of its header. Every contig in the FASTA gets one call from every tool. A contig that appears in
a tool's output but not in the FASTA is ignored.

## The seven states

| State | Meaning |
|---|---|
| `plasmid` | the tool called the contig plasmid |
| `chromosome` | the tool called the contig chromosome, or, for a two-valued tool, did not call it plasmid |
| `unknown` | the tool abstained, or did not report the contig |
| `unclassified` | PlaScope column only: mixed or no chromosome/plasmid evidence |
| `repeat` | gplas2 only: the contig was flagged as a repeat |
| `FAILED` | the tool's run did not succeed, or its mandatory output was absent or malformed |
| `MISSING` | no parsed call exists for this contig and tool |

`FAILED` and `MISSING` are explicit non-values. Neither is ever recoded as a negative call.

### How FAILED arises

The driver decides this per tool and sample, before and around the parser:

1. The receipt's `status` is not `"OK"`. Every contig of that sample is `FAILED` for that tool.
   The `native_call` column records `tool_status_<status>`. In the frozen runs, `status` was
   `"OK"` when the tool's exit code was 0 and `"FAILED"` otherwise.
2. There is no receipt. The status is taken as `NOT_RUN`, and case 1 applies:
   `native_call` is `tool_status_NOT_RUN`.
3. The status is `"OK"`, but the parser raises `ParseError`. Every contig of that sample is
   `FAILED` for that tool, with `native_call` `parse_error`. The error message goes to the
   summary. The parser raises `ParseError` when a mandatory output file is absent or empty, a
   required column is missing, a line is malformed, or the output holds a value outside the
   tool's known set.

Any other exception stops the frozen driver, and `parse_outputs.py` stops the same way. No
table is written for a run that stopped.

### How MISSING arises

The parser and the driver never emit `MISSING`. It is assigned only when the long table is
turned into the wide table, to a contig that has no row for a tool. The rule is the one in
`scripts/evaluation/build_p113_contig_table.py`: a call that is absent or empty becomes
`MISSING`. With `parse_outputs.py` this happens when a tool is left out with `--tools`, or when
`--from-long` reads a long table that lacks some rows. The frozen P1.13 prediction table holds
no `MISSING` cell.

A tool that was not run is therefore `FAILED` (`tool_status_NOT_RUN`) when it is parsed with
the other tools, and `MISSING` when it is left out of parsing. The two states are encoded
differently. The v1.2-General encoder sets a tool's block to exactly neutral when that tool is
in a state it never saw in training. `FAILED` was seen in training only for PlasmidFinder, and
`MISSING` was never seen. The same applies to any other unseen state; the model bundle's
`observed_states` lists, per tool, the states seen. See the docstring of
`scripts/evaluation/freeze_v12.py`.

### Per-tool rules

Each rule below is read from `frozen/parsers.py`. "Not listed" means the contig is in the
FASTA but absent from the tool's output.

| Tool | Mandatory output (absent or malformed: FAILED) | Rule |
|---|---|---|
| MOB-recon | `mob/contig_report.txt` with `contig_id` and `molecule_type`; not empty | `molecule_type` plasmid or chromosome is taken as is; any other value is a `ParseError`. Not listed: `unknown`. |
| Platon | `*.plasmid.fasta` and `*.chromosome.fasta` | In the plasmid file: `plasmid`. In the chromosome file: `chromosome` (the chromosome file is read second). Not listed: `unknown`. |
| RFPlasmid | `rf/**/prediction.csv` (or `**/prediction.csv`) with a `contigID` or `contig` column and `prediction` | `p` or plasmid: `plasmid`. `c` or chromosome: `chromosome`. Any other value is a `ParseError`. Not listed: `unknown`. |
| PlaScope (Centrifuge on the PlaScope index; see below) | `*_extendedresults.tsv` (Centrifuge) with `readID` and `taxID`; at least one row | plasmidEC's aggregation rule. Hits are counted per contig: taxID 2 chromosome (C), 3 plasmid (P), 0 unclassified (U). The plasmid fraction is P/(C+P+U), rounded to 2 decimals, and set to 0.5 when any U hit exists. At least 0.7: `plasmid`. Below 0.3: `chromosome`. Otherwise `unclassified`. A contig with hits but no C, P or U hit, or not listed: `unclassified`. |
| PlasmidEC | `pec/**/*plasmidEC_predictions*.tab` or `pec/gplas_format/*.tab` with `Contig_name` and `Prediction` | Plasmid: `plasmid`. Chromosome: `chromosome`. Any other value is a `ParseError`. Node names `S<id>_LN:i:<len>_dp:f:<depth>` map to contig `<id>`. Not listed (PlasmidEC drops contigs under 1,000 bp): `unknown`. |
| PlasmidFinder | `pf/results_tab.tsv` with `Contig` and `Plasmid` | At least one replicon hit: `plasmid`. Every other contig: `chromosome` (`native_call` `no_replicon_hit`). |
| geNomad | `genomad/*_summary/*_plasmid_summary.tsv` with `seq_name` | Listed: `plasmid`. Every other contig: `chromosome`. |
| PLASMe | `*.plasme.fna` and `temp/PLASMe_candidate.csv` with `query` and `PLASMe`; FASTA body must be sequence | A `c` prefix added to ids at run time is removed. Under 1,000 bp: `unknown`, whether listed or not. Otherwise, in the `.fna`: `plasmid`. Not in it: `chromosome` (`native_call` `gt350kb_rule` above 350,000 bp, `not_predicted_plasmid` below). |
| Plasmer | `**/*.plasmer.predClass.tsv`: two tab-separated columns, no header; not empty | plasmid: `plasmid`. chromosome: `chromosome`. unclassified: `unknown`. Any other class or line shape is a `ParseError`. Not listed: `unknown`. |
| gplas2 | `results/*_results.tab`, whitespace-separated, header with `Contig_name`, `Prediction`, `Bin` | Plasmid with a numeric bin: `plasmid`. Plasmid, Unbinned: `unknown`. Repeat: `repeat`. Chromosome: `chromosome`. Any other value is a `ParseError`. Rows of `results/*_chromosome_repeats.tab` whose first field is a number: `repeat`, unless already called. Not listed: under 1,000 bp `unknown`; initial PlasmidEC class chromosome `chromosome`; otherwise `unknown`. The initial class is read from `<native>/plasmidec/<sample>/pec/gplas_format/*.tab`. |
| plASgraph2 | `*.plasgraph2.csv` with `contig` and `label` | plasmid: `plasmid`. chromosome: `chromosome`. Any other label: `unknown`. Not listed: `unknown`. |
| HyAsP | `find/` and `find/putative_plasmid_contigs.fasta`; headers `<contig>\|...`, body must be sequence | In that file: `plasmid`. Every other contig: `chromosome`. Questionable plasmids are not counted. |

So `unclassified` comes only from the PlaScope column and `repeat` only from gplas2.
PlasmidFinder, geNomad and HyAsP never abstain: each contig is `plasmid`, `chromosome` or
`FAILED`.

### The PlaScope column

The recorded command in `scripts/evaluation/p113_tool.sh` does not run PlaScope's own script. It
runs Centrifuge directly on the PlaScope *E. coli* index (`chromosome_plasmid_db`), with
`-k 1000` and no size or coverage filter. The reason is recorded in
`docs/evidence/P1.9C4_model1_independent_validation_2026-08-19.md`: PlaScope's own extractor
could not handle Unicycler contig headers.

The call rule and its thresholds are taken from plasmidEC, not from PlaScope's own script. The
parser turns Centrifuge's hits into one call per contig with the aggregation rule of plasmidEC's
`transform_centrifuge_output.R`, as its docstring records: a plasmid fraction per contig, set to
0.5 when any hit is unclassified, with at least 0.7 for `plasmid` and below 0.3 for `chromosome`.
`parsers.py` implements that rule in Python; it does not include the R script. The rule is
plasmidEC's (Paganini et al. 2024, doi:10.1099/mgen.0.001193; MIT licence). The index is
PlaScope's (Royer et al. 2018, doi:10.1099/mgen.0.000211). The column keeps the name PlaScope
because the frozen tables and both encoders use that name.

## Running it

Run from the repository root. Set `PYTHONDONTWRITEBYTECODE=1`, or pass `-B`, if you want no
bytecode files. `parse_outputs.py` itself writes none next to the frozen files.

With receipts, as in the frozen runs:

```
python -B scripts/parsers/parse_outputs.py \
    --assemblies ASSEMBLIES --native NATIVE --receipts RECEIPTS \
    --long calls_long.tsv --wide calls_wide.tsv --summary parse_summary.json
```

Without receipts, when you ran the tools yourself:

```
python -B scripts/parsers/parse_outputs.py \
    --assemblies ASSEMBLIES --native NATIVE --status-from-outputs \
    --wide calls_wide.tsv
```

With `--status-from-outputs`, a tool counts as run when `<native>/<tool>/<sample>/` exists.
Otherwise it is `FAILED` with `tool_status_NOT_RUN`. This mode is not part of the frozen
driver. It cannot tell a crashed run from a finished one, so a crashed run is `FAILED` only if
its mandatory output is absent or malformed.

From long tables that already exist, for example the 1,800 per-sample files in Part 1 of the
data deposit (`inference/parsed/<tool>/<sample>.tsv`):

```
python -B scripts/parsers/parse_outputs.py \
    --from-long PART1/inference/parsed --long calls_long.tsv --wide calls_wide.tsv
```

Other options: `--samples S1,S2` parses a subset of samples. `--tools genomad,PlaScope` parses a
subset of tools, and the others are `MISSING` in the wide table. `--per-sample-dir DIR` writes
the frozen per-sample files `DIR/<tool>/<sample>.tsv`. `--fasta-name` changes the assembly file
name. `--quiet` drops the per tool and sample lines. The script refuses to write inside an
input directory.

### Outputs

- **Long table** (`--long`). The frozen layout, one row per contig and tool: `sample`,
  `contig_id`, `contig_length`, `tool`, `native_call`, `model1_code`, `evidence_score`,
  `native_sha256sums`, `parser_version`. The seven-state call is `model1_code`. `native_call`
  is the tool's own label or the rule that fired. The builder reads `model1_code`, never
  `native_call`. Rows run tool by tool in long-table order, then by sample in sorted order,
  then by contig in FASTA order. Tab-separated with CRLF line ends, as the frozen driver
  writes it.
- **Wide table** (`--wide`). One row per contig: `sample`, `contig_id`, `contig_length`, then
  the 12 tool columns in wide-table order. Rows run by sample in sorted order, then by contig
  in FASTA order. Tab-separated with LF line ends. `scripts/evaluation/v11_scorer_p111.py score
  --contig-table` reads this table as it is. It takes the 12 tool columns and `contig_length`,
  and derives each sample's count of contigs of at least 1 kb from the table itself, so keep
  every contig of a sample in it. For v1.2-General, pass the 12 tool columns in this order to
  `predict()` in `scripts/evaluation/freeze_v12.py`.
- **Summary** (`--summary`). Per tool and sample: the run status, any parse error, and the
  count of each state.

## Checks

**Self-test.** `python -B scripts/parsers/tests/test_parse_outputs.py` builds a synthetic
input tree in a temporary directory: two made-up samples, native outputs for all 12 tools and
receipts. No study data is used. It runs the frozen `parse_all.py` and `parse_outputs.py` on
the tree and makes 19 checks. The long table and all 24 per-sample files are byte-identical
between the two drivers. 96 contig and tool states match states derived by hand from the rules
above. They include each way `FAILED` arises: a failed run, no receipt, a malformed output and
an absent mandatory output. `MISSING` appears only where a call is absent. Expected result:
`19 checks, 19 passed, 0 failed`.

**Driver provenance.** `python -B scripts/parsers/tests/check_parse_all_provenance.py` ties the
frozen `parse_all.py` to the recorded P1.10 and P1.11 drivers, as described under Provenance.
Expected result: `8 checks, 8 passed, 0 failed`.

**Public data, P1.13.** From Part 1 of the data deposit:

- `--from-long` on the 1,800 per-sample files rebuilds the P1.13 long table: 231,840 rows,
  sha256 `e3e43a0269336f2e88a670ef1b226d5ed56e616557e72ece0e41d873ffb4f48f`. This is the digest
  recorded for the parsed call table in `docs/closure/P113_CANONICAL_ARTEFACT_INVENTORY.tsv`.
- The wide table from the same files matches the frozen prediction table
  `frozen/P1.13_FROZEN_PREDICTIONS.tsv` (sha256 `3bc733c0...`). All 19,320 rows agree in
  `sample`, `contig_id`, `contig_length` and the 12 tool columns, with 0 differing cells. Its
  cells are chromosome 145,426, plasmid 41,378, unknown 30,377, unclassified 8,777, FAILED 4,789
  and repeat 1,093. No cell is MISSING.
- Scoring that wide table reproduces the frozen scores. v1.2-General through
  `freeze_v12.predict()` differs from the frozen `v12_score` by at most 6.7e-16, with 0 call
  differences at 0.9285. v1.1 through `v11_scorer_p111.py score` matches `v11_score` exactly,
  with 0 differences in state or call.

**Native outputs, P1.13.** The native tool outputs are not in the deposit. The author holds
them. They were parsed for six isolates, one from each taxon: SAMN49850453 (*Citrobacter*),
SAMN35677795 (*Enterobacter*), SAMN37639060 (*E. faecalis*), SAMD00565567 (*E. faecium*),
SAMN13382572 (*K. pneumoniae*) and SAMEA121008655 (*Serratia*). The six include four failed
runs: MOB-recon and gplas2 on SAMN49850453, gplas2 on SAMEA121008655, and PlasmidFinder on
SAMN37639060. With the receipts from Part 1 and the assemblies as run, `parse_outputs.py` wrote
72 per-sample files (6 isolates by 12 tools). All 72 are byte-identical to the deposited files
in Part 1. Its 15,192 long-table rows are identical, in order, to the matching rows of the P1.13
long table. The frozen `parse_all.py`, run on the same inputs, wrote byte-identical output. The
wide table matched the frozen prediction table's tool columns on all 1,266 contigs.

These checks ran on Windows with Python 3.14.6.

## Limits

- Where a file pattern matches more than one file, the parser uses the first match, and the
  order of matches depends on the file system. In the six P1.13 isolates above, one pattern
  matched two files: Plasmer writes both
  `intermediate/<sample>.allFeatures.plasmer.predClass.tsv` and
  `results/<sample>.plasmer.predClass.tsv`. The two were byte-identical in all six runs, so the
  choice made no difference. Every other pattern matched at most one file. If your outputs hold
  extra copies that differ, remove them before parsing.
- The parser opens native files with the platform's default text encoding, mostly with
  `errors="replace"`. The frozen runs were on Linux, where the default is UTF-8. Every file the
  parser read for the six P1.13 isolates was ASCII, and the Windows checks above gave identical
  bytes.
- The rules were written for the tool versions pinned in `SOFTWARE_AND_DATABASE_VERSIONS.tsv`.
  Another version may change its output format. A changed format fails loudly (`FAILED`) only
  where the parser checks a file or column. A change in the meaning of a value would not be
  detected.
- `parse_outputs.py` departs from the frozen driver in five ways. None changes a call for the
  same inputs. It takes paths from the command line. It lists only directories under
  `--assemblies` as samples, where the frozen driver would stop on a stray file. It reports a
  malformed assembly FASTA with a message instead of a traceback. It reads the assembly FASTA
  as UTF-8. It adds `--status-from-outputs`, `--tools`, `--samples`, `--from-long` and the wide
  table.

Code in `scripts/parsers/` is under the MIT licence (`LICENSE`). This document is under CC BY
4.0 (`LICENSE-DATA`).

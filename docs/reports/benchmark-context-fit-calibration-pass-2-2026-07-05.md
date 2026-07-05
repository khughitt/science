# Benchmark Context-Fit Calibration pass-2 - 2026-07-05

## Commands

Raw JSON snapshots were written to `/tmp/benchmark-calibration-2026-07-05/`
and are intentionally not committed.

- `science benchmark gap-calibration --commons --format json`
- `science benchmark gaps --commons --calibration-summary --format json`
- `science benchmark gaps --commons --context-fit direct-fit --format json`
- `science benchmark tests --commons --exclude-fallback --state concrete --format json`
- `science benchmark test-triage --commons --format json`

All commands were run from the toolkit worktree with:

`PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science`

## Projects

- `multiple-myeloma`: `~/d/cancer/cancer-types/multiple-myeloma`
- `post-acute-infection`: `~/d/health/processes/post-acute-infection`
- `natural-systems`: `~/d/natural-systems`
- `cbioportal`: `~/d/cancer/data-sources/cbioportal`

## Aggregate Gap Calibration

- gap rows: `812`
- candidate rows: `2453`
- entity-specific candidate rows: `179`
- fallback candidate rows: `2274`
- fallback candidate ratio: `0.927`
- fallback concentration warning: `False`

Top fallback benchmarks:

- `dataset:mmrf-commpass`: 758 (0.333)
- `dataset:dream4-in-silico-network`: 394 (0.173)
- `dataset:ccle-proteomics-nusinow-2020`: 380 (0.167)
- `dataset:cptac-proteogenomics`: 378 (0.166)
- `dataset:cptac-gbm-2021-proteogenomics`: 364 (0.160)

Top suggested facets:

- `clinical-outcome`: 42
- `time-series`: 7
- `single-cell-rna-seq`: 5
- `perturbation`: 4
- `cross-context-generalization`: 1
- `spatial`: 1

## Concrete Non-Fallback Test Rows

This is the closest surface to "what can the project run or inspect next?"

| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context | runnable | stage-needed | metadata-only | blocked |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multiple-myeloma | 226 | 140 | 34 | 0 | 52 | 0 | 0 | 129 | 0 | 97 | 0 |
| post-acute-infection | 25 | 4 | 0 | 0 | 4 | 0 | 17 | 8 | 0 | 17 | 0 |
| natural-systems | 4 | 0 | 0 | 0 | 1 | 0 | 3 | 0 | 0 | 4 | 0 |
| cbioportal | 15 | 5 | 7 | 0 | 0 | 0 | 3 | 10 | 0 | 5 | 0 |

Notable changes relative to pass-1:

- `post-acute-infection` concrete rows increased from 9 to 25, but 17 are
  `out-of-context`.
- `cbioportal` direct-fit concrete rows dropped from 7 to 5 and adjacent-fit
  rows rose from 5 to 7.
- `multiple-myeloma` remains the only project with a large runnable concrete
  surface (`129` rows).

## Full Triage Rows

| Project | rows | run-now | stage-next | metadata-needed | blocked-or-reference | fallback-diagnostic | hidden generic fallback | shown fallback | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multiple-myeloma | 1126 | 129 | 0 | 0 | 97 | 900 | 900 | 0 | 140 | 34 | 0 | 52 | 900 | 0 |
| post-acute-infection | 211 | 8 | 0 | 0 | 17 | 186 | 185 | 1 | 5 | 0 | 0 | 4 | 185 | 17 |
| natural-systems | 322 | 0 | 0 | 0 | 4 | 318 | 318 | 0 | 0 | 0 | 0 | 1 | 318 | 3 |
| cbioportal | 127 | 10 | 0 | 0 | 5 | 112 | 90 | 22 | 5 | 29 | 0 | 0 | 90 | 3 |

The fallback presentation layer is doing its job: generic fallback remains
counted and diagnosable, but it no longer needs to occupy the default detailed
table. The remaining problem is no longer table volume alone; it is whether
the visible non-fallback rows are actionably labeled.

## Direct-Fit Gap Filter Check

| Project | direct-fit gap rows | example candidate pattern |
| --- | ---: | --- |
| multiple-myeloma | 48 | clinical-outcome gaps often map to `brca-metabric` and `brca-tcga-pancanatlas`; single-cell gaps map to atlas/perturbation benchmarks |
| post-acute-infection | 1 | wearable/EMA protocol maps to `dream4-in-silico-network` |
| natural-systems | 0 | no direct-fit gap rows |
| cbioportal | 1 | neuroactive drug exposure maps to `tahoe-100m` |

Pass-2 removes the pass-1 `cbioportal` direct-fit warning leak for
`cptac-gbm-2021-proteogenomics`. However, the `multiple-myeloma` direct-fit
surface still deserves review: breast-cancer clinical-outcome benchmarks may be
useful transfer baselines, but they should probably read as adjacent-fit unless
an explicit cross-cancer validation rule justifies direct-fit.

## Top Concrete Benchmarks

| Project | top concrete non-fallback benchmarks |
| --- | --- |
| multiple-myeloma | `mmrf-commpass` (52), `brca-metabric` (48), `brca-tcga-pancanatlas` (48), `sciplex3` (13), `tahoe-100m` (12) |
| post-acute-infection | `dream4-in-silico-network` (5), `mmrf-commpass` (4), `mouse-gastrulation-atlas` (3), `ctrpv2` (2), `sciplex3` (2), `l1000-cmap` (2), `tahoe-100m` (2), `dream-perturbation` (2) |
| natural-systems | `human-cell-atlas` (1), `mmrf-commpass` (1), `dream4-in-silico-network` (1), `mouse-gastrulation-atlas` (1) |
| cbioportal | `ccle-proteomics-nusinow-2020` (2), `brca-metabric` (2), `brca-tcga-pancanatlas` (2), `cptac-gbm-2021-proteogenomics` (2), `cptac-proteogenomics` (2) |

## Warning Review

Concrete rows with `context_fit_warnings`:

| Project | warned concrete rows | dominant warning pattern |
| --- | ---: | --- |
| multiple-myeloma | 9 | `cell-line-vs-primary` on CTRPv2/CCLE and `cross-disease:gbm-vs-myeloma` on CPTAC GBM |
| post-acute-infection | 17 | `domain-conflict`, all currently `out-of-context` |
| natural-systems | 3 | `domain-conflict`, all currently `out-of-context` |
| cbioportal | 5 | `cross-disease:gbm-vs-breast` adjacent rows plus perturbation `domain-conflict` out-of-context rows |

The main actionability defect is that `benchmark test-triage` can still put
`out-of-context` rows in `run-now` when they are concrete and runnable. Example
from `post-acute-infection`: CTRPv2, SciPlex3, L1000, and DREAM perturbation rows
are `run-now` because their access/task state is runnable, even though
`context_fit` says `out-of-context`.

## Blocked And Generic Fallback Concentration

MMRF remains the dominant blocked-support fallback source:

| Project | suppressed blocked-support fallback rows | top suppressed benchmark |
| --- | ---: | --- |
| multiple-myeloma | 450 | `dataset:mmrf-commpass` |
| post-acute-infection | 93 | `dataset:mmrf-commpass` |
| natural-systems | 159 | `dataset:mmrf-commpass` |
| cbioportal | 56 | `dataset:mmrf-commpass` |

Generic fallback remains broad but is now explicitly hidden from terminal detail:

| Project | hidden generic fallback rows | shown fallback rows | top generic fallback benchmarks |
| --- | ---: | ---: | --- |
| multiple-myeloma | 900 | 0 | `dream4-in-silico-network`, `ccle-proteomics-nusinow-2020`, `cptac-proteogenomics`, `cptac-gbm-2021-proteogenomics` |
| post-acute-infection | 185 | 1 | `dream4-in-silico-network`, `ccle-proteomics-nusinow-2020`, `cptac-proteogenomics`, `cptac-gbm-2021-proteogenomics` |
| natural-systems | 318 | 0 | `ccle-proteomics-nusinow-2020`, `cptac-gbm-2021-proteogenomics`, `dream4-in-silico-network`, `cptac-proteogenomics` |
| cbioportal | 90 | 22 | `dream4-in-silico-network`, `cptac-proteogenomics`, `ccle-proteomics-nusinow-2020` |

## Commons Notices

No commons notices were reported.

## Recommendation

Primary next slice before the belief-test design: **tighten actionability
semantics for visible non-fallback rows**.

Rationale:

- Generic fallback is still dominant in raw counts (`0.927` fallback candidate
  ratio), but it is now summarized rather than competing for detailed terminal
  attention.
- The stronger current defect is semantic: `run-now` can include
  `out-of-context` rows, and `direct-fit` can still include cross-cancer transfer
  rows that may be useful but should read as transfer/adjacent rather than direct.
- Metadata/staging is not the immediate bottleneck for the active cancer/data
  projects: multiple myeloma already has 129 runnable concrete rows, and
  cBioPortal has 10.

Recommended order:

1. Add a narrow triage rule: `out-of-context` rows must not land in `run-now`.
   They should be separated into a diagnostic bucket or require an explicit
   `--include-out-of-context` view.
2. Tighten source-study/direct-fit semantics for cancer transfer benchmarks:
   breast and GBM clinical/proteogenomic benchmarks can remain useful candidates,
   but should not be direct-fit for myeloma or cBioPortal unless a stronger
   project/source-study provenance signal is present.
3. Then step back and design the parsimonious Belief-Test Layer: a stable
   abstraction connecting benchmark task rows to project beliefs, with explicit
   signal strength, validation gates, and no hidden inference from text overlap
   alone.

## Raw Snapshot Policy

The raw JSON snapshots were used to compute this report and left in
`/tmp/benchmark-calibration-2026-07-05/`. They are not durable project artifacts.

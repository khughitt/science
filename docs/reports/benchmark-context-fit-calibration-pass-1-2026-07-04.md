# Benchmark Context-Fit Calibration pass-1 - 2026-07-04

## Commands

- `science benchmark gap-calibration --commons --format json`
- `science benchmark gaps --commons --format json`
- `science benchmark gaps --commons --context-fit direct-fit --format json`
- `science benchmark tests --commons --exclude-fallback --state concrete --format json`
- `science benchmark test-triage --commons --format json`

## Projects

- `multiple-myeloma`: `~/d/cancer/cancer-types/multiple-myeloma`
- `post-acute-infection`: `~/d/health/processes/post-acute-infection`
- `natural-systems`: `~/d/natural-systems`
- `cbioportal`: `~/d/cancer/data-sources/cbioportal`

## Aggregate Gap Calibration

- gap rows: `786`
- candidate rows: `2375`
- entity-specific candidate rows: `170`
- fallback candidate rows: `2205`
- fallback candidate ratio: `0.928`
- fallback concentration warning: `False`

Top fallback benchmarks:
- `dataset:mmrf-commpass`: 735 (0.333)
- `dataset:dream4-in-silico-network`: 380 (0.172)
- `dataset:ccle-proteomics-nusinow-2020`: 372 (0.169)
- `dataset:cptac-proteogenomics`: 363 (0.165)
- `dataset:cptac-gbm-2021-proteogenomics`: 355 (0.161)

## Concrete Non-Fallback Test Rows

| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multiple-myeloma | 226 | 140 | 34 | 0 | 52 | 0 | 0 |
| post-acute-infection | 9 | 2 | 0 | 0 | 1 | 0 | 6 |
| natural-systems | 4 | 0 | 0 | 0 | 1 | 0 | 3 |
| cbioportal | 15 | 7 | 5 | 0 | 0 | 0 | 3 |

## Full Triage Rows

| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multiple-myeloma | 1576 | 140 | 34 | 0 | 502 | 900 | 0 |
| post-acute-infection | 219 | 2 | 0 | 0 | 1 | 210 | 6 |
| natural-systems | 481 | 0 | 0 | 0 | 1 | 477 | 3 |
| cbioportal | 183 | 29 | 5 | 0 | 0 | 146 | 3 |

## Unfiltered Gap Candidates

| Project | rows | direct-fit | adjacent-fit | method-fit | blocked-fit | generic-fallback | out-of-context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multiple-myeloma | 1509 | 105 | 11 | 0 | 493 | 900 | 0 |
| post-acute-infection | 213 | 0 | 0 | 0 | 1 | 210 | 2 |
| natural-systems | 480 | 0 | 0 | 0 | 1 | 477 | 2 |
| cbioportal | 173 | 23 | 1 | 0 | 0 | 146 | 3 |

## Direct-Fit Gap Filter Check

| Project | gap rows | candidate rows | direct-fit candidates |
| --- | ---: | ---: | ---: |
| multiple-myeloma | 48 | 105 | 105 |
| post-acute-infection | 0 | 0 | 0 |
| natural-systems | 0 | 0 | 0 |
| cbioportal | 23 | 23 | 23 |

## Suspicious Direct Or Adjacent Rows

| Project | context_fit | benchmark | entity | warnings |
| --- | --- | --- | --- | --- |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `hypothesis:0002-cross-study-ranking-divergence-is-structured` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `hypothesis:0009-treatment-induced-signature-frequency-contamination` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `hypothesis:0010-joint-indel-sbs-improves-aetiology-discrimination` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `hypothesis:0011-sbs1-lrr-contamination-qc` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0004-mca-burden-in-esophageal-vs-other-study-tissues` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0005-gli1-normal-tissue-hotspot-inflation` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0007-cross-tissue-somatic-mutation-rate-variation-as-null-model` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0014-cfs-as-distinct-confounder-class` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0015-pan-cancer-aggregator-choice` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0018-can-mutational-signature-decomposition-be-added-downstream-of-the-cross` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0020-minimum-sample-size-and-caller-provenance-for` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0028-indel-call-availability-across-cbioportal-studies` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0029-assay-regime-divergence-attribution` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0031-residual-gene-length-signal-mechanism` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0033-neural-enrichment-cns-exclusion` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0035-label-free-neural-gene-definition` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0036-oncofetal-fetal-vs-adult-neural-expression` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0041-driver-complexity-vs-median-age-at-diagnosis` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0042-driver-normal-expression-tissue-cell-type-specificity` | cross-disease:gbm-vs-breast |
| cbioportal | direct-fit | `dataset:cptac-gbm-2021-proteogenomics` | `question:0043-driver-cancer-type-breadth-distribution` | cross-disease:gbm-vs-breast |

_Showing top 20 of 23 warned rows._

## Blocked-Fit Concentration

| Project | benchmark | blocked-fit candidates |
| --- | --- | ---: |
| multiple-myeloma | `dataset:mmrf-commpass` | 493 |
| post-acute-infection | `dataset:mmrf-commpass` | 1 |
| natural-systems | `dataset:mmrf-commpass` | 1 |

## Generic Fallback Concentration

| Project | benchmark | generic-fallback candidates |
| --- | --- | ---: |
| multiple-myeloma | `dataset:dream4-in-silico-network` | 235 |
| multiple-myeloma | `dataset:ccle-proteomics-nusinow-2020` | 225 |
| multiple-myeloma | `dataset:cptac-proteogenomics` | 225 |
| multiple-myeloma | `dataset:cptac-gbm-2021-proteogenomics` | 215 |
| natural-systems | `dataset:mmrf-commpass` | 159 |
| natural-systems | `dataset:ccle-proteomics-nusinow-2020` | 85 |
| natural-systems | `dataset:cptac-gbm-2021-proteogenomics` | 83 |
| natural-systems | `dataset:dream4-in-silico-network` | 76 |
| natural-systems | `dataset:cptac-proteogenomics` | 74 |
| post-acute-infection | `dataset:mmrf-commpass` | 70 |
| cbioportal | `dataset:mmrf-commpass` | 56 |
| post-acute-infection | `dataset:ccle-proteomics-nusinow-2020` | 39 |
| post-acute-infection | `dataset:cptac-gbm-2021-proteogenomics` | 35 |
| post-acute-infection | `dataset:dream4-in-silico-network` | 35 |
| cbioportal | `dataset:dream4-in-silico-network` | 34 |
| cbioportal | `dataset:cptac-proteogenomics` | 33 |
| post-acute-infection | `dataset:cptac-proteogenomics` | 31 |
| cbioportal | `dataset:ccle-proteomics-nusinow-2020` | 23 |

## Commons Notices

No commons notices were reported.

## Recommendation

Primary next slice: **classifier tuning**.

Reason: 23 direct/adjacent gap candidate(s) carry cross-context warnings.

Signals:
- natural-systems direct-fit concrete rows: 0
- direct/adjacent gap candidates with cross-context warnings: 23
- generic-fallback triage share: 1733/2459 (0.70)
- fallback candidate concentration: 0.22 of 1733
- method-fit concrete share: 0/254 (0.00)
- blocked-fit candidate concentration: 1.00 of 495

## Raw Snapshots

Raw JSON snapshots were written to the session scratch directory and are intentionally not committed.

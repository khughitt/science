# Benchmarking

Science benchmark support is descriptive and read-only today. It lets projects
catalog benchmark-capable datasets, inspect benchmark coverage, find candidate
benchmark opportunities, report coverage gaps, and project draft benchmark test
rows. It does not create graph benchmark edges, authored belief-test plans,
benchmark outcomes, or proposition evidence updates.

## Benchmark Metadata

Benchmark metadata lives on dataset entities under `benchmark:`:

```yaml
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response"]
  source_datasets: []
  related_beliefs: ["hypothesis:drug-response"]
  notes:
    - "Useful perturbation benchmark."
  limitations:
    - "Facets only until held-out tasks are defined."
  tasks:
    - id: "compound-response"
      task_type: "response-prediction"
      prediction_target: "post-treatment expression signature"
      held_out_unit: "compound"
      metric: "rank-correlation"
      baseline: "untreated expression profile"
      ground_truth:
        type: "measured-outcome"
        description: "measured post-perturbation expression state"
      interpretation_limits:
        - "Positive rank correlation is the intended signal."
      intervention: "compound and dose"
      contexts: ["cell line", "compound", "dose"]
```

`domains`, `modalities`, `signal_types`, and `benchmark_kinds` are free-text
facet lists. `source_datasets` and `related_beliefs` are also free text; they
are not graph edges. `notes` and `limitations` explain how to interpret sparse
or incomplete benchmark records.

Task IDs are local to the dataset. They must be lowercase kebab-case, 2-64
characters, and unique within the benchmark block. In prose and reports, render
tasks as `dataset:<slug>#<task-id>`.

`dataset_class` still controls operational meaning:

| Class | Benchmark use |
|---|---|
| `deposit` | The benchmark data can be obtained and staged. |
| `reference` | The record is a portal, registry, atlas, or leaderboard used for lookup. |
| `pointer` | The benchmark is worth tracking but is not yet usable as data or lookup. |

## Metadata Validation

`science validate` includes benchmark metadata checks:

| Rule | Severity | Meaning |
|---|---|---|
| `benchmark.pointer-block` | info | A pointer dataset carries benchmark metadata. |
| `benchmark.block-malformed` | warn | `benchmark` is not a mapping. |
| `benchmark.facets-lack-task-or-limitation` | warn | `benchmark_kinds` exists without tasks or limitations. |
| `benchmark.task-id-invalid` | error | A task ID is not lowercase kebab-case or is outside 2-64 characters. |
| `benchmark.task-id-duplicate` | error | A benchmark block repeats a task ID. |
| `benchmark.task-sparse` | warn | A task is missing `task_type` or `prediction_target`. |
| `benchmark.perturbation-context-missing` | warn | A perturbation benchmark task lacks `intervention` and `contexts`. |
| `benchmark.timepoints-missing` | warn | A time-series benchmark task lacks `timepoints`. |

## Benchmark Kinds

`benchmark_kinds` is free text in v1, but these tokens are the stable starting
vocabulary:

| Kind | Use |
|---|---|
| `static-association` | Cross-sectional associations, classifications, or signatures. |
| `perturbation-response` | Response to interventions such as CRISPR, drug, knockdown, stimulation, or environmental shift. |
| `time-series` | Temporal dynamics, ordering, trajectories, or delayed effects. |
| `longitudinal-cohort` | Patient or sample trajectories across repeated measurements. |
| `cross-context-generalization` | Transfer across cohort, tissue, species, assay, or project context. |
| `mechanism-discrimination` | Competing mechanisms that make different observable predictions. |
| `calibration` | Calibration of scores, probabilities, or uncertainty estimates. |

## Catalog And Coverage

Use:

```bash
science benchmark list [--domain <domain>] [--kind <kind>] [--belief-ref-text <token>] [--commons] [--coverage-summary] [--format table|json]
```

The command reads local benchmark datasets from `entities/datasets/*.md`. With
`--commons`, it also reads benchmark dataset records from the configured commons
registry. If commons cannot be read, Science emits a notice and still reports
local rows.

`--belief-ref-text` matches exact tokens in `benchmark.related_beliefs`; it does
not resolve entities. `--coverage-summary` returns counts by `domains`,
`modalities`, `signal_types`, `benchmark_kinds`, `dataset_class`, and task
completeness (`with_tasks` versus `facets_only`).

JSON output has:

- `rows`: benchmark dataset rows with ID, title, scope, class, facet lists, task
  count, and task IDs.
- `summary`: coverage counts.
- `commons_notice`: null or the commons read failure.

## Opportunities

Use:

```bash
science benchmark opportunities [--domain <domain>] [--entity <ref>] [--commons] [--calibration-report] [--format table|json]
```

Opportunities compare project questions, hypotheses, and propositions with
available benchmark datasets. They are candidate matches, not assertions that a
benchmark evaluates an entity. Row scores are heuristic and combine baseline
benchmark quality with entity-relative overlap. The report gives diversity
credit to the first matched benchmark per high-value facet for each entity, so
row order is part of the prioritization contract.

JSON output has:

- `matched_opportunities`: candidate rows with entity, benchmark, optional task,
  match reasons, facets, baseline score, relative score, score components, and
  notes.
- `coverage_gaps`: high-value facets missing from matched opportunities.
- `available_unmapped_benchmarks`: benchmark datasets not matched to project
  entities.
- `unmapped_project_entities`: project entities without candidate matches.
- `calibration`: optional token/scoring evidence when `--calibration-report` is
  set.
- `commons_notice`.

## Gaps

Use:

```bash
science benchmark gaps [--domain <domain>] [--entity <ref>] [--facet <facet>] [--commons] [--calibration-report] [--calibration-summary] [--evidence-report] [--format table|json]
```

Gap reports identify entities with no matched benchmark, weak coverage, or
missing high-value facets. Gap levels are:

| Level | Meaning |
|---|---|
| `uncovered` | No matched benchmark opportunities for the entity. |
| `weak` | Matches are taskless or below the weak relative-score threshold. |
| `missing-facet` | Matches exist but omit high-value modality or signal facets. |

Candidate benchmarks are selected from unmatched benchmark datasets. Candidates
with entity-specific facet evidence use `missing-facet:*` and `entity-hint:*`
reason notes. If no entity-specific candidate exists, Science falls back to
generally useful benchmarks and marks them with `fallback:*` notes. Fallback
rows are limited to three and use deterministic per-entity rotation among tied
quality tiers. Selection notes explain why a fallback row was selected, such as
`selected:task-ready`, `selected:generic-baseline`,
`selected:available-benchmark`, or `selected:diversity-rotation`.

JSON output has:

- `benchmark_gaps`: gap rows with entity, level, missing facets, current matches,
  candidate benchmarks, suggested search facets, and reason.
- `summary`: counts of total, uncovered, weakly covered, and missing-facet
  entities.
- `calibration`: optional gap token/candidate evidence.
- `evidence_report`: optional explanations for fallback-only or missing
  candidate cases.
- `commons_notice`.

`--calibration-summary` adds aggregate candidate metrics: candidate row counts,
entity-specific versus fallback rows, score min/median/max, top suggested
facets, top matched hint facets, top fallback benchmarks, top fallback reasons,
top fallback selection reasons, fallback benchmark shares, and
`fallback_concentration_warning`.

## Cross-Project Gap Calibration

Use:

```bash
science benchmark gap-calibration --project label=path [--project label=path ...] [--domain <domain>] [--facet <facet>] [--commons] [--format table|json]
```

Project labels must be unique. The report runs benchmark gap analysis for each
project and summarizes calibration quality across projects. JSON output has
`projects`, `aggregate`, and `commons_notices`.

The aggregate section reports project count, gap rows, candidate rows,
entity-specific candidate rows, fallback candidate rows, fallback ratio, top
suggested facets, top matched hint facets, top fallback benchmarks, top fallback
reasons, top fallback selection reasons, fallback benchmark shares, and whether
fallback recommendations are concentrated on one benchmark.

## Benchmark Test Projection

Use:

```bash
science benchmark tests [--domain <domain>] [--entity <ref>] [--facet <facet>] [--state concrete|draft-needed] [--source opportunity-relative|gap-candidate|gap-fallback] [--exclude-fallback] [--readiness runnable|stage-needed|metadata-only|blocked] [--runnable-only] [--benchmark <id-or-slug>] [--commons] [--format table|json]
```

This command projects read-only benchmark test rows from opportunities and gaps.
It does not create authored plans or outcomes.

Rows from concrete benchmark tasks have `test_plan_state: concrete`. Rows from
facets-only benchmarks have `test_plan_state: draft-needed` and include `needs`
entries for the missing task fields. `priority_source` records where the row
came from:

| Source | Meaning |
|---|---|
| `opportunity-relative` | A direct benchmark opportunity match. |
| `gap-candidate` | A gap candidate with entity-specific facet evidence. |
| `gap-fallback` | A broad fallback candidate. |

`readiness_label` summarizes runtime readiness:

| Readiness | Meaning |
|---|---|
| `runnable` | A concrete task is attached to a runnable deposit. |
| `stage-needed` | The benchmark needs staging, acquisition, derivation, or another preparation step before use. |
| `metadata-only` | The benchmark is reference or pointer metadata rather than runnable data. |
| `blocked` | Access, verification, withdrawal, embargo, or unknown operational state blocks use. |

Duplicate projected rows are merged by `(entity_id, benchmark_id, task_id)`.
Direct opportunity rows outrank gap candidates, and gap candidates outrank
fallbacks. Within the same source, the higher priority score wins. Merged rows
keep the union of matched facets and reason notes.

## Cataloging Workflow

The `/science:catalog-benchmarks` command and `science-catalog-benchmarks` skill
should keep v1 cataloging descriptive:

- discover benchmark-capable datasets;
- classify benchmark facets and `dataset_class`;
- add concrete `benchmark.tasks[]` only when the evaluation task is clear;
- record limitations for facets-only records;
- run `science benchmark list --coverage-summary --format json`;
- run `science validate --profile commit`.

Do not use cataloging to create graph benchmark edges, belief-test plans,
benchmark outcomes, or gap entities.

## Not Implemented Yet

The current benchmark system stops at descriptive metadata and read-only
projections. These features remain future work:

- authored `plan_kind: belief-test` schema and templates;
- graph-aware benchmark-to-belief or benchmark-to-proposition edges;
- structured benchmark result and outcome records;
- workflow support that turns benchmark outcomes into evidence/proposition
  updates;
- cross-project success analysis over actual benchmark outcomes.

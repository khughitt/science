---
description: Discover, classify, and summarize benchmark-capable datasets without adding belief edges or benchmark outcomes.
---

# Catalog Benchmarks

Catalog benchmark-capable datasets for `$ARGUMENTS`.
If no argument is provided, run the v1 descriptive benchmark loop over the project's active questions, hypotheses, and existing datasets.

## Scope

v1 is descriptive only:

- discover benchmark-capable datasets;
- classify `benchmark.domains`, `benchmark.modalities`, `benchmark.signal_types`, and `benchmark.benchmark_kinds`;
- add sparse `benchmark.tasks[]` only when the task is concrete;
- run `science benchmark list` and the facet coverage summary;
- record limitations when a dataset is facets-only.

Do not create belief-test plans, benchmark outcomes, graph edges, or benchmark gap entities in v1. Those are Phase 2/3.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` with role `research-assistant`.

Read:

1. `${CLAUDE_PLUGIN_ROOT}/skills/data/SKILL.md`
2. `~/d/science/docs/user-guide/benchmarking.md`
3. `entities/datasets/`, if present
4. `entities/questions/`, `entities/hypotheses/`, and `entities/propositions/`, if present

## Step 1: Inspect Current Benchmark Coverage

Run:

```bash
science benchmark list --format json
science benchmark list --coverage-summary --format json
science benchmark list --commons --coverage-summary --format json
```

Use the JSON `summary` object as the source of truth for facet counts by domain, modality, signal type, benchmark kind, dataset class, and task completeness.

## Step 2: Classify Candidate Benchmarks

For each candidate dataset, decide whether it is:

- `dataset_class: deposit` when the benchmark data can be obtained and staged;
- `dataset_class: reference` when it is a benchmark portal, registry, atlas, or leaderboard used for lookup;
- `dataset_class: pointer` when it is worth tracking but not yet usable as data or lookup.

Do not infer `dataset_class` from `source_class`. A reference genome or reference atlas can be a downloadable deposit; a portal can be reference-only.

Fill the `benchmark` block with sparse, concrete metadata:

```yaml
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response"]
  source_datasets: []
  related_beliefs: []
  limitations:
    - "Facets only; no held-out task definition yet."
```

Add `benchmark.tasks[]` only when the task is concrete. The preferred minimum
for a useful catalog entry is a `prediction_target` and a `held_out_unit` (what
is predicted and what is withheld), plus `metric` and `baseline`:

```yaml
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response"]
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
        - "Positive rank correlation against held-out perturbation response is the intended signal."
      intervention: "compound and dose"
      contexts: ["cell line", "compound", "dose"]
```

Task identity is local to the dataset. Render it as `dataset:<slug>#<task-id>` in prose and reports.

## Step 3: Search for Missing Facets

Prefer candidates that add new information relative to the existing summary:

- first proteomics benchmark before another RNA-seq benchmark;
- first perturbation or time-series signal before another static association dataset;
- first multimodal benchmark before another single-modality dataset;
- a reference registry when it makes future concrete deposits discoverable.

Useful biology/omics signal types include perturbation, time-series, longitudinal cohort, proteomics, spatial, single-cell, bulk RNA-seq, and multimodal proteogenomics.

## Step 4: Validate

Run:

```bash
science benchmark list --coverage-summary --format json
science validate --profile commit
```

Resolve benchmark metadata warnings before handing off. A facets-only record should have `limitations`; perturbation records should name `intervention` or `contexts` when they have tasks; time-series records should name `timepoints` when they have tasks.

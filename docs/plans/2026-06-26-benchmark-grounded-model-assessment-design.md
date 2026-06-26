---
id: "plan:2026-06-26-benchmark-grounded-model-assessment-design"
type: "plan"
title: "Benchmark-grounded model assessment for Science"
status: "proposed"
created: "2026-06-26"
updated: "2026-06-26"
related:
  - "plan:2026-06-26-dataset-catalog-triage-pack-design"
  - "plan:2026-06-26-feedback-telemetry-adaptation-design"
  - "plan:2026-06-21-catalog-datasets-design"
  - "plan:2026-05-31-belief-profile-design"
---

# Benchmark-grounded model assessment for Science

## Purpose

Science is strong at building computational workflows and aggregating evidence
from multiple sources. It is weaker at testing whether the resulting beliefs,
mechanistic models, and project-level representations actually predict or
explain held-out empirical structure.

This design adds benchmark-grounded model assessment: a way to catalog known
benchmark datasets, map them to project beliefs and mechanisms, identify gaps
where no suitable benchmark exists, and run explicit belief tests against
benchmarks. The goal is to make Science projects more empirically accountable:
not just "what does the literature suggest?" but "what should this model predict,
and where can we test that prediction?"

## Goals

- Catalog benchmark datasets relevant to a project, topic, or wider field.
- Represent what each benchmark can and cannot test.
- Link benchmarks to hypotheses, propositions, mechanisms, prediction tasks, and
  known failure modes.
- Make benchmark gaps visible as first-class research needs.
- Support small benchmark evaluation plans that test project beliefs or models.
- Use benchmark outcomes to study which Science project patterns correlate with
  successful prediction or explanation.
- Treat perturbation and time-series datasets as high-value benchmarks because
  they test causal and temporal structure more directly than static association
  datasets.

## Non-goals

- No claim that benchmark performance is the only measure of scientific value.
- No automatic truth assignment to hypotheses based on one benchmark.
- No benchmark leaderboard in v1.
- No requirement that every project have runnable benchmark evaluations before
  it can proceed.
- No broad benchmark data hosting. Science catalogs and routes benchmarks; it
  does not become a data warehouse.

## Core concept

A benchmark is a dataset plus an evaluation interpretation.

The same raw dataset may be a normal `dataset:*` in one context and a benchmark
in another. Benchmark status depends on what question it tests, what target is
held out, what label or endpoint is treated as ground truth, and what baseline
or competing model defines meaningful performance.

Therefore, do not create a separate top-level entity kind in v1. Instead, model
benchmark information as structured metadata attached to `dataset:*` records and
as evaluation-plan documents that reference those datasets.

## Benchmark metadata

Extend dataset catalog semantics with an optional `benchmark` block:

```yaml
benchmark:
  scope: "project"        # project | field | cross-project
  domain: "biology"
  modality:
    - "single-cell-rna-seq"
    - "perturbation"
  benchmark_kind:
    - "perturbation-response"
    - "time-series"
  endpoints:
    - "cell-state transition"
    - "gene-expression response"
  ground_truth:
    type: "measured-outcome"
    description: "post-perturbation expression state"
  suitable_for:
    - "mechanism-discrimination"
    - "model-calibration"
    - "prediction"
  limitations:
    - "single cell line"
    - "short time horizon"
  related_beliefs:
    - "hypothesis:0005-dynamic-homeostasis"
    - "proposition:stress-response-is-state-dependent"
```

Fields should be sparse and additive. A benchmark record with only domain,
modality, and benchmark kind is still useful.

## Benchmark classes

Initial benchmark classes:

| Class | Purpose |
|---|---|
| `static-association` | Test cross-sectional associations, classifications, or signatures. |
| `perturbation-response` | Test response to interventions such as CRISPR, drug, knockdown, stimulation, or environmental shift. |
| `time-series` | Test temporal dynamics, ordering, trajectories, or delayed effects. |
| `longitudinal-cohort` | Test patient/sample trajectories across repeated measurements. |
| `cross-context-generalization` | Test whether a model learned in one cohort, tissue, species, assay, or project transfers to another. |
| `mechanism-discrimination` | Distinguish competing mechanisms that make different observable predictions. |
| `calibration` | Assess whether scores, probabilities, or uncertainty estimates are calibrated. |

Perturbation and time-series classes should be highlighted in reports because
they provide stronger tests of causal or dynamic claims than static benchmarks.

## Benchmark catalog workflow

Add a command/skill workflow, tentatively `/science:catalog-benchmarks`, with
four phases:

1. **Topic scan.** Given a project, field, or hypothesis cluster, find benchmark
   datasets already in the project catalog and likely external benchmarks.
2. **Benchmark classification.** For each candidate, classify benchmark kind,
   modality, endpoints, access, and limitations.
3. **Belief mapping.** Link each benchmark to hypotheses, propositions,
   mechanisms, or prediction tasks it can test.
4. **Gap map.** Identify important beliefs or mechanisms with no suitable
   benchmark, and classify the missing benchmark shape.

This command should reuse dataset catalog infrastructure. Benchmarks are a
specialized view over datasets, not a parallel data catalog.

## Benchmark gap map

Benchmark gaps are first-class outputs:

```yaml
id: "benchmark-gap:dynamic-immune-recovery-perturbation"
type: "benchmark-gap"
target:
  - "hypothesis:0005-dynamic-homeostasis"
missing_benchmark_kind:
  - "perturbation-response"
  - "time-series"
required_modalities:
  - "proteomics"
  - "single-cell-rna-seq"
required_context:
  species: "human"
  condition: "post-acute infection"
why_needed: "Current evidence is mostly observational; no benchmark tests recovery after controlled perturbation."
candidate_paths:
  - "search public perturbation repositories"
  - "compile derived benchmark from existing longitudinal cohorts"
```

Whether benchmark gaps should become a formal entity kind can be deferred. In
v1 they can live as rows in reports or `docs/benchmark-gaps/*.md` documents.

## Belief tests

A belief test is a small evaluation plan that maps a project belief to a
benchmark prediction.

Example:

```yaml
id: "belief-test:stress-response-state-dependence"
type: "plan"
plan_kind: "belief-test"
beliefs:
  - "proposition:stress-response-is-state-dependent"
benchmarks:
  - "dataset:sciplex3"
prediction:
  statement: "Baseline cell state should predict perturbation response direction."
metric:
  name: "held-out response rank correlation"
  minimum_interpretable_effect: 0.2
baselines:
  - "cell-type-only model"
  - "random gene-set baseline"
outcomes:
  supports_if: "model exceeds cell-type-only baseline on held-out perturbations"
  disputes_if: "model fails to exceed baseline or reverses predicted direction"
```

Belief tests should route to existing workflow machinery:

- `catalog-benchmarks` finds and maps benchmark candidates.
- `plan-analysis` or `plan-pipeline` designs the runnable evaluation.
- `pre-register` locks prediction, metric, and interpretation thresholds when
  the test is confirmatory.
- `interpret-results` records outcome and updates propositions/evidence.

## Evaluation outputs

Benchmark evaluations should produce:

- A normal workflow output package when code runs.
- A `belief-test` or plan document tying the benchmark to the tested beliefs.
- Evidence lines or findings that support, dispute, or qualify propositions.
- A benchmark result summary:

```yaml
benchmark_result:
  benchmark: "dataset:sciplex3"
  belief_test: "belief-test:stress-response-state-dependence"
  outcome: "supports|disputes|mixed|inconclusive"
  metric_values:
    held_out_rank_correlation: 0.31
  baselines:
    cell_type_only: 0.12
  interpretation: "supports state-dependent perturbation response in this context"
```

This keeps benchmark results integrated with the existing proposition/evidence
model instead of creating a separate scoring universe.

## Cross-project success analysis

Once benchmark outcomes exist, Science can ask which project patterns correlate
with better benchmark performance.

Candidate explanatory features:

- Dataset access and stageability at planning time.
- Presence of perturbation/time-series benchmarks.
- Number of independent evidence lines per proposition.
- Whether hypotheses had explicit falsifiable predictions.
- Whether pre-registration existed before evaluation.
- Validation health at execution time.
- Feedback/telemetry friction around the workflow.
- Reuse of commons datasets or shared benchmark definitions.

Analysis must adjust for data availability and benchmark coverage. A project in
a field with no useful benchmarks should not be judged the same as a project
with abundant public perturbation datasets.

This is a later-phase analysis surface, not part of v1 implementation. The v1
requirement is to record enough structured benchmark metadata and outcomes that
such analysis becomes possible.

## Commands and surfaces

### `/science:catalog-benchmarks`

Agent workflow:

- discover field/project benchmarks;
- classify benchmark kinds and modalities;
- link to beliefs;
- create benchmark gap map;
- recommend next belief tests.

### `science benchmark list`

Read-only query over dataset benchmark metadata:

```bash
science benchmark list --domain biology
science benchmark list --kind perturbation-response
science benchmark list --related hypothesis:0005
science benchmark list --format json
```

### `science benchmark gaps`

Report benchmark gaps by project, domain, mechanism, or hypothesis:

```bash
science benchmark gaps --target hypothesis:0005
science benchmark gaps --kind time-series
```

### `science benchmark tests`

List belief-test plans and outcomes:

```bash
science benchmark tests --status planned|run|interpreted
science benchmark tests --benchmark dataset:sciplex3
```

These CLI surfaces are query/report tools. Authoring can initially happen via
normal dataset and plan creation until the model stabilizes.

## Integration with dataset catalog

The dataset catalog triage pack introduces dataset classes such as `deposit`,
`reference`, and `pointer`. Benchmarks compose with those classes:

- A runnable benchmark is usually a `deposit`.
- A benchmark registry or leaderboard can be a `reference`.
- A not-yet-materialized benchmark candidate can be a `pointer`.

Benchmark reports should include access and runtime stageability from the
dataset catalog. A benchmark that cannot be accessed or staged should not be
recommended for immediate belief testing without an acquisition step.

## Integration with feedback and telemetry

Telemetry should eventually answer:

- Which benchmark workflows fail most often?
- Which benchmark classes are often missing in a field?
- Which commands precede successful benchmark tests?
- Which validation failures predict failed or inconclusive benchmark outcomes?

Feedback should capture benchmark workflow friction:

```bash
science feedback add \
  --target "command:catalog-benchmarks" \
  --category gap \
  --summary "No natural place to record perturbation benchmark limitations"
```

## Implementation phases

### Phase 1: benchmark metadata and reports

- Add optional `benchmark` block support on dataset entities.
- Add query helpers for benchmark metadata.
- Add `science benchmark list`.
- Add `/science:catalog-benchmarks` command doc.
- Add benchmark gap report as docs or query output.

### Phase 2: belief-test plans

- Define `plan_kind: belief-test` conventions.
- Add templates/examples for belief tests.
- Link belief tests to datasets, hypotheses, propositions, metrics, and
  baselines.
- Route confirmatory tests through `pre-register`.

### Phase 3: benchmark outcomes and cross-project analysis

- Add structured benchmark result summaries.
- Integrate outcomes with evidence/proposition updates.
- Add reports comparing project patterns to benchmark outcomes while adjusting
  for benchmark availability.

## Validation and quality checks

- Benchmark dataset with `benchmark.benchmark_kind` but no endpoint should warn.
- Belief test without a benchmark should warn.
- Confirmatory belief test without pre-registration should warn.
- Benchmark result without baseline or metric should warn.
- Perturbation/time-series benchmark missing timepoint or intervention metadata
  should warn when that metadata is relevant.

## Success criteria

- A project can list known benchmarks relevant to its topic or field.
- A project can see which hypotheses/propositions have no suitable benchmark.
- Perturbation and time-series datasets are visible as high-value tests rather
  than just ordinary datasets.
- A project can write a belief-test plan that connects a proposition to a
  benchmark prediction, metric, baseline, and interpretation threshold.
- Benchmark outcomes can update the proposition/evidence graph instead of
  living only in workflow logs.
- Science can eventually study which project practices correlate with better
  benchmark-grounded performance, adjusted for data availability.

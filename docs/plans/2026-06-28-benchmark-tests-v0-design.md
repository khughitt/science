# Benchmark Tests v0 Design

## Goal

Add a read-only `science benchmark tests` report that turns benchmark
opportunities and gaps into candidate test-plan rows. The command should answer:

- what project entity could be tested;
- which benchmark dataset or task is relevant;
- whether the row is concrete or still needs task design;
- which target, held-out unit, metric, baseline, and ground truth are known;
- why the candidate was suggested; and
- what still needs to be specified before the test is runnable or interpretable.

This is the first narrow slice of Phase 2 benchmark testing. It deliberately
does not create belief-test plan files, benchmark outcomes, graph edges, or
pre-registration records.

## Context

The benchmark catalog v1 established benchmark metadata on dataset entities.
`science benchmark opportunities` reports entity-to-benchmark matches.
`science benchmark gaps` reports uncovered, weakly covered, and missing-facet
entities. The newer gap calibration and evidence-report work makes gap
candidates explainable and surfaces deterministic facet hints from project text.

The next useful step is not another broad matching surface. It is a planning
projection over the existing substrate: "given the current project entities and
benchmark metadata, what concrete validation could we run, and where is the
benchmark metadata only enough to draft a test?"

## Command

Add:

```bash
science benchmark tests
science benchmark tests --commons
science benchmark tests --entity hypothesis:0005
science benchmark tests --facet clinical-outcome
science benchmark tests --state concrete
science benchmark tests --state draft-needed
science benchmark tests --benchmark dataset:sciplex3
science benchmark tests --format json
```

The command is read-only. It mirrors the existing benchmark command conventions:

- `--entity` resolves through `resolve_entity_ref()`;
- `--domain` filters benchmark datasets by benchmark domain;
- `--facet` uses the same valid hint-facet vocabulary as `benchmark gaps`;
- `--commons` includes commons benchmark dataset entities;
- `--format table|json` follows the existing CLI pattern;
- commons degradation emits the same stderr notice and still returns local rows.

## Row Semantics

Emit one row per `(entity, benchmark, task)` when a benchmark has task metadata.
Emit one row per `(entity, benchmark)` when the benchmark is relevant but has no
task metadata.

Each row has a `test_plan_state`:

- `concrete`: the benchmark has an explicit task with enough evaluable metadata
  to identify the prediction target, held-out unit, metric, baseline, and ground
  truth surface.
- `draft-needed`: the benchmark is relevant by facets, gap candidates, or
  opportunity matching, but task metadata is absent or incomplete. The row is a
  useful benchmark need, not a runnable test plan.

Concrete rows may still carry `needs` if the task is partially specified. A row
is `concrete` only when a task exists; it is not a promise that local files are
already staged or that the benchmark has been run.

## JSON Contract

Top-level shape:

```json
{
  "benchmark_tests": [],
  "summary": {
    "entities_total": 12,
    "test_plan_rows": 20,
    "concrete_rows": 8,
    "draft_needed_rows": 12,
    "entities_with_test_plans": 6,
    "entities_without_test_plans": 6,
    "top_facets": []
  },
  "commons_notice": null
}
```

Concrete row example:

```json
{
  "entity_id": "hypothesis:0005-dynamic-homeostasis",
  "entity_title": "Dynamic homeostasis predicts recovery trajectories",
  "benchmark_id": "dataset:sciplex3",
  "benchmark_title": "Sci-Plex perturbation response atlas",
  "task_id": "dataset:sciplex3#drug-response",
  "test_plan_state": "concrete",
  "test_plan_kind": "perturbation-response",
  "readiness": "runnable",
  "priority_score": 78,
  "score_components": {
    "relevance": 42,
    "baseline_quality": 18,
    "task_completeness": 12,
    "readiness": 6
  },
  "matched_facets": ["perturbation", "single-cell-rna-seq"],
  "reason_notes": ["entity-hint:perturbation", "task-ready", "signal:perturbation"],
  "prediction_target": "drug-induced expression response",
  "held_out_unit": "compound",
  "metric": "rank correlation",
  "baseline": "nearest-neighbor expression profile",
  "ground_truth": {
    "type": "observed-response",
    "description": "measured post-perturbation expression"
  },
  "needs": []
}
```

Draft-needed row example:

```json
{
  "entity_id": "hypothesis:0005-dynamic-homeostasis",
  "entity_title": "Dynamic homeostasis predicts recovery trajectories",
  "benchmark_id": "dataset:hca-spatial",
  "benchmark_title": "Human Cell Atlas spatial reference",
  "task_id": null,
  "test_plan_state": "draft-needed",
  "test_plan_kind": "spatial-validation",
  "readiness": "metadata-only",
  "priority_score": 47,
  "score_components": {
    "relevance": 28,
    "baseline_quality": 14,
    "task_completeness": 0,
    "readiness": 5
  },
  "matched_facets": ["spatial"],
  "reason_notes": ["entity-hint:spatial", "draft-needed"],
  "prediction_target": "",
  "held_out_unit": "",
  "metric": "",
  "baseline": "",
  "ground_truth": {
    "type": "",
    "description": ""
  },
  "needs": ["prediction-target", "held-out-unit", "metric", "baseline", "ground-truth"]
}
```

All added fields are additive to a new command. No existing benchmark command
contract changes.

## Data Flow

`science benchmark tests` should be a projection over the same analysis used by
`benchmark opportunities` and `benchmark gaps`.

1. Run the existing opportunity/gap analysis for the project, honoring
   `--entity`, `--domain`, `--facet`, and `--commons`.
2. Collect candidate sources:
   - matched opportunities from `opportunity_report`;
   - weak current matches from `gaps_report`;
   - entity-specific gap candidates from `gaps_report`;
   - fallback gap candidates only when no entity-specific candidate exists, and
     label their reason notes explicitly.
3. For each relevant dataset:
   - emit task rows for each available `tasks[]` entry;
   - emit one `draft-needed` row if the dataset has no tasks;
   - for incomplete task rows, populate `needs` for missing target/unit/metric/
     baseline/ground-truth fields.
4. Sort rows by `priority_score desc`, then `test_plan_state` with `concrete`
   before `draft-needed`, then entity id, benchmark id, and task id.

This keeps the command aligned with calibrated matching and avoids a second
matching implementation.

## Scoring

`priority_score` is intentionally transparent. It is not a learned score and
does not imply scientific truth.

Use bounded additive components:

- `relevance`: gap candidate `candidate_score` when present, otherwise matched
  opportunity `relative_score`, capped at 55.
- `baseline_quality`: scaled from existing benchmark `baseline_score`, capped at
  20.
- `task_completeness`: points for known prediction target, held-out unit, metric,
  baseline, and ground truth, capped at 15.
- `readiness`: points from the existing readiness/baseline substrate, capped at
  10.

Clamp the sum to 100. Emit `score_components` so every score is reconstructable
from JSON. Prefer existing component values from benchmark opportunity contexts
instead of re-validating dataset frontmatter per row.

## Readiness Labels

The command should expose a compact readiness label for planning:

- `runnable`: dataset has task metadata and readiness is good enough for use-now
  style planning.
- `stage-needed`: dataset looks obtainable but local runtime materialization is
  not yet complete.
- `metadata-only`: benchmark metadata is useful for planning, but no runnable
  task should be assumed.
- `blocked`: access or licensing state blocks immediate use.

The label is a presentation projection over existing dataset readiness and
benchmark metadata. It must not create a new independent access vocabulary.

## Table Output

Default table columns:

```text
entity | state | benchmark | task | score | facets | needs
```

The table should be compact and sorted like JSON. If no rows remain after
filters, print:

```text
No benchmark test plans.
```

## Filters

- `--state concrete|draft-needed` filters by `test_plan_state`.
- `--benchmark <dataset-ref>` filters exact benchmark ids. Accept canonical ids
  such as `dataset:sciplex3` and bare dataset slugs when unambiguous.
- `--facet <facet>` filters by matched or suggested benchmark facets, using the
  same normalized valid set as `benchmark gaps`.
- `--entity`, `--domain`, and `--commons` behave like the existing benchmark
  commands.

## Error Handling

- Unknown `--entity` raises the same Click error as `benchmark gaps`.
- Unknown `--facet` raises the same validation error as `benchmark gaps`.
- Unknown `--state` is rejected by Click.
- Unknown `--benchmark` should produce an empty report rather than an error,
  because benchmark availability changes with `--commons` and project-local
  metadata. The filter is exact after normalization.
- Commons degradation emits `notice: commons benchmarks unavailable (...)` to
  stderr and continues with local benchmark metadata.

## Non-Goals

- No file creation or mutation.
- No `plan_kind: belief-test` schema yet.
- No benchmark result or outcome model.
- No belief graph updates.
- No pre-registration integration.
- No embeddings or semantic matching.
- No automatic benchmark-gap or belief-test entity creation.

## Testing

Add focused tests for:

- concrete row generation from a benchmark with `tasks[]`;
- draft-needed row generation from a relevant benchmark without tasks;
- incomplete task rows populate `needs`;
- `--state concrete` and `--state draft-needed` filtering;
- current matched opportunities are included, not only gap rows;
- entity-specific gap candidates are included with reason notes;
- fallback candidates are included only when no entity-specific candidate exists
  for that entity, with explicit fallback notes;
- unknown facet/entity errors match existing benchmark command semantics;
- JSON shape is stable;
- table output renders entity, state, benchmark, task, score, facets, and needs;
- commons notice behavior is preserved.

## Future Work

Once this report is useful on real projects, a follow-on design can introduce
authored belief-test plans:

- `plan_kind: belief-test` conventions;
- templates/examples for benchmark test plans;
- validation for missing benchmark, metric, baseline, or interpretation
  threshold;
- optional routing through `pre-register`;
- benchmark result summaries that can feed evidence and proposition updates.

## Self-Review

- No placeholders or TBDs remain.
- The command is read-only and does not overlap with authoring or outcome
  phases.
- The row model distinguishes concrete task rows from draft-needed benchmark
  needs.
- The design reuses existing opportunities/gaps/readiness contracts and avoids a
  second matching path.
- Paths and command examples avoid machine-specific absolute paths.

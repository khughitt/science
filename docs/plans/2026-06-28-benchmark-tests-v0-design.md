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
  opportunity matching, but task metadata is absent or incomplete. This includes
  benchmarks with no `tasks[]` and task rows that have a `task_id` but are
  missing one or more evaluable fields. The row is a useful benchmark need, not
  a runnable test plan.

A `concrete` row has no `needs`. It is not a promise that local files are
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
    "top_facets": [{"facet": "perturbation", "count": 5}]
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
  "task_type": "perturbation response",
  "benchmark_kinds": ["perturbation-response"],
  "readiness_label": "runnable",
  "priority_score": 78,
  "priority_source": "opportunity-relative",
  "score_components": {
    "source": {
      "related_belief_id": 40,
      "facet_overlap": 16,
      "kind_signal_fit": 10,
      "diversity_added": 15,
      "readiness_penalty": -3
    },
    "baseline": {
      "task_completeness": 30,
      "signal_value": 10,
      "modality_value": 4,
      "readiness": 15,
      "limitations": 10
    }
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
  "task_type": "",
  "benchmark_kinds": ["static-association"],
  "readiness_label": "metadata-only",
  "priority_score": 47,
  "priority_source": "gap-candidate",
  "score_components": {
    "source": {
      "missing_facet_overlap": 0,
      "hint_facet_overlap": 20,
      "task_readiness": 12,
      "baseline_quality": 15
    },
    "baseline": {
      "task_completeness": 0,
      "signal_value": 0,
      "modality_value": 6,
      "readiness": 15,
      "limitations": 10
    }
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
   - entity-specific gap candidates from `gaps_report`;
   - fallback gap candidates only when no entity-specific candidate exists, and
     label their reason notes explicitly.
   Gap `current_matches` are not a second row source because they are derived
   from the same opportunity rows; they can annotate weak coverage, but must not
   duplicate `(entity, benchmark, task)` rows.
3. For each relevant dataset:
   - emit task rows for each available `tasks[]` entry;
   - label a task row `concrete` only when prediction target, held-out unit,
     metric, baseline, and ground truth are present;
   - label incomplete task rows `draft-needed` and populate `needs`;
   - emit one `draft-needed` row if the dataset has no tasks;
   - for every draft-needed row, populate `needs` for missing target/unit/
     metric/baseline/ground-truth fields.
4. Deduplicate rows by `(entity_id, benchmark_id, task_id)`. If the same row is
   seen through multiple projections, keep one row and merge `reason_notes`;
   prefer the more specific source in this order: matched opportunity,
   entity-specific gap candidate, fallback gap candidate.
5. Sort rows by `test_plan_state` with `concrete` before `draft-needed`, then
   `priority_score desc`, then entity id, benchmark id, and task id. This
   favors immediately specifiable validation while still preserving the source
   score as the within-state ranking signal. Consumers that prefer pure score
   ranking can sort JSON rows themselves.

This keeps the command aligned with calibrated matching and avoids a second
matching implementation.

## Scoring

`priority_score` is intentionally transparent. It is not a learned score and
does not imply scientific truth.

Do not recombine existing score components into a new additive score. The
existing source scores are already calibrated 0-100 signals and already include
task/readiness terms where they belong:

- opportunity-derived rows use the opportunity `relative_score` as
  `priority_score` and set `priority_source: "opportunity-relative"`;
- gap-candidate rows use the candidate `candidate_score` as `priority_score` and
  set `priority_source: "gap-candidate"`;
- fallback rows use the fallback candidate `candidate_score` as
  `priority_score` and set `priority_source: "gap-fallback"`.

This means `priority_score` is a within-state sort key, not a single scientific
quantity with identical semantics across origins. Expose `priority_source` and
pass through the applicable existing component dict under
`score_components.source`. Include the existing benchmark baseline components
under `score_components.baseline` for explanation and tie-breaking context, but
do not add them to `priority_score` again.

## Facets

There is no existing `matched_facets` field. The command should compute it as a
presentation projection:

- for opportunity rows, use normalized benchmark `modalities` and
  `signal_types`;
- for gap-candidate rows, use `matched_missing_facets`,
  `matched_hint_facets`, and normalized benchmark `modalities` /
  `signal_types`;
- for rows with entity facet hints, include hint facets only when the benchmark
  declares the same normalized facet.

Filter `--facet` against this projected `matched_facets` set. The valid filter
vocabulary should stay the same as `benchmark gaps`
(`BENCHMARK_GAP_HINT_FACETS`), but rows may expose additional normalized dataset
facets for display. A facet outside the valid filter set is display-only until
the gap hint vocabulary intentionally grows.

## Readiness Labels

The command should expose a compact readiness label for planning. Compute it as
an ordered procedure over `readiness_for(frontmatter).state`,
`runtime_state_for(frontmatter)`, and task presence. Reference/pointer runtime
states are handled first because they are metadata-only by class. After that,
readiness is checked before deposit runtime defaults because it refines cases
that runtime stageability collapses. For example, a derived dataset can be
`runtime_state=blocked-access` but `readiness=derived-via-code`, and an
embargoed dataset can be `runtime_state=unstaged-deposit` but
`readiness=embargoed`.

1. If runtime state is `reference-only` or `pointer-only`, label
   `metadata-only`. These rows often have no external/derived `origin`, so their
   readiness can be `unknown` without implying an access block.
2. If runtime state is `runnable` and the row has a task, label `runnable`.
   A staged local artifact is actionable for test planning even when sparse
   access metadata makes `readiness_for(...).state` report `unknown`.
3. If readiness is `embargoed`, `withdrawn`, `unknown`, or ends with
   `, unverified`, label `blocked`.
4. If readiness is `derived-via-code`, `derived-via-member-of`,
   `derived-via-workflow-recipe`, `consumable-via-scope-reduced`,
   `consumable-via-substituted`, or `acquiring`, label `stage-needed`.
5. Otherwise, use runtime stageability:
   - `runtime_state == "unstaged-deposit"`: `stage-needed`;
   - `runtime_state == "blocked-access"`: `blocked`.
6. If no task metadata is present and no earlier rule matched, label
   `metadata-only`.

The label is a presentation projection over existing dataset readiness and
benchmark metadata. It must not create a new independent access vocabulary.
Use `readiness_label` for the row field so it does not collide with the numeric
`baseline.readiness` score component.

`readiness_label` and `test_plan_state` are separate axes. A draft-needed row
with an incomplete task can still be `runnable` if the dataset is staged; a
concrete row can be `stage-needed` or `blocked` if the task is specified but
access/runtime readiness is not.

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
- `--facet <facet>` filters by projected `matched_facets`, using the same
  normalized valid set as `benchmark gaps`.
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
- commons notice behavior is preserved;
- synthetic duplicate rows merge into one `(entity, benchmark, task)` row with
  deterministic source precedence and merged reason notes;
- `priority_source` matches the row origin and `priority_score` equals the
  applicable source score without recomputing additive components;
- `readiness_label` derivation covers runtime states plus readiness override
  cases including `derived-via-code -> stage-needed` and
  `embargoed -> blocked`.

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

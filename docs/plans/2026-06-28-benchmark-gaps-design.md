---
id: "plan:2026-06-28-benchmark-gaps-design"
type: "plan"
title: "Benchmark gap reports"
status: "proposed"
created: "2026-06-28"
updated: "2026-06-28"
related:
  - "plan:2026-06-26-benchmark-grounded-model-assessment-design"
  - "plan:2026-06-27-benchmark-opportunities-design"
  - "plan:2026-06-27-benchmark-opportunities-implementation-plan"
---

# Benchmark gap reports

## Purpose

`science benchmark opportunities` already exposes the raw material needed to
answer the first project-level benchmark coverage question:

> Which project entities appear uncovered or weakly covered by benchmark-capable
> datasets, and which benchmark facets should a curator inspect next?

This design adds a read-only `science benchmark gaps` command as Phase 2's first
slice. It is deliberately a projection over `opportunity_report()`, not a second
matching implementation. The command should make the opportunity report's gaps
easier to act on while preserving the same matching semantics, commons
degradation behavior, entity filtering, domain filtering, and cautious
"human-review" posture.

## Goals

- Report project entities with no benchmark matches.
- Report project entities whose benchmark matches are weak or only facets-level.
- Project existing high-value missing-facet rows from `coverage_gaps`.
- Show baseline-ranked unmapped benchmark candidates for each gap.
- Treat `suggested_search_facets` as the primary actionable v1 signal for what
  kind of benchmark coverage to look for next.
- Reuse the existing high-value facet vocabulary:
  - `GAP_MODALITIES = ("proteomics", "spatial", "multimodal")`
  - `GAP_SIGNAL_TYPES = ("perturbation", "time-series", "cross-context-generalization")`
- Keep output deterministic, read-only, and JSON-first.

## Non-goals

- No new benchmark matching path.
- No semantic embeddings, LLM ranking, or graph-aware belief mapping.
- No automatic gap entity creation.
- No benchmark evaluation plan generation.
- No new benchmark metadata fields.
- No new `RelationKind` values or materialize changes.

## Command surface

Add:

```bash
science benchmark gaps
science benchmark gaps --commons
science benchmark gaps --domain biology
science benchmark gaps --entity hypothesis:0005-dynamic-homeostasis
science benchmark gaps --facet time-series
science benchmark gaps --format json
```

`--entity` uses the same entity reference resolution as
`science benchmark opportunities`; user input is resolved with
`resolve_entity_ref()` and translated into a Click error if resolution fails.

`--facet` filters gap rows by a normalized high-value missing facet. It is not
called `--kind`, because values like `time-series` are benchmark signal facets,
not project entity kinds. Valid values are exactly the union of
`GAP_MODALITIES` and `GAP_SIGNAL_TYPES`. CLI validation is intentionally strict
and case-sensitive in v1, so users should pass the lowercase canonical spelling
such as `time-series`, not `Time-Series`.

## Architecture

Add `gaps_report()` to `science_tool.benchmark_opportunities`. It calls
`opportunity_report()` once and projects over the returned payload:

- `unmapped_project_entities` produces `uncovered` gaps.
- `coverage_gaps` produces missing modality and signal annotations.
- `matched_opportunities` provides current coverage and weak-match detection.
- `available_unmapped_benchmarks` provides the candidate benchmark pool.
- `commons_notice` passes through unchanged.

The CLI layer should only parse options, resolve `--entity`, call
`gaps_report()`, print the commons notice, and render table or JSON output.

This avoids the main risk: letting `benchmark gaps` and `benchmark
opportunities` disagree because they loaded entities, loaded commons rows,
normalized facets, or matched text differently.

## Gap levels

Each returned row has exactly one `gap_level`. `uncovered` is mutually exclusive
with the other levels because it requires zero matches. The meaningful overlap
to resolve is between `weak` and `missing-facet`; an entity can have weak
matches while also missing high-value facets. Use this precedence:

1. `uncovered`: the entity appears in `unmapped_project_entities`, meaning it
   has zero matched benchmark opportunities.
2. `weak`: the entity has matches, but every matched row is weak by the v1
   heuristic.
3. `missing-facet`: the entity has at least one existing `coverage_gaps` row and
   is not already `uncovered` or `weak`.

The first implementation uses a deliberately simple weak heuristic:

- all matched rows for the entity have `relative_score < 15`, or
- all matched rows for the entity are taskless (`task_id is null`).

The threshold is an implementation constant, not a CLI option in this tranche.
It can be tuned later after calibration reports show whether it is too strict or
too permissive.

An entity can have missing high-value facets and weak matches at the same time.
The row should still be classified as `weak`, while retaining the missing facet
lists so the reason remains inspectable.

## JSON contract

JSON is the stable surface:

```json
{
  "benchmark_gaps": [
    {
      "entity_id": "hypothesis:0005-dynamic-homeostasis",
      "entity_title": "Dynamic homeostasis predicts perturbation recovery",
      "gap_level": "weak",
      "missing_modalities": ["proteomics"],
      "missing_signal_types": ["time-series"],
      "current_matches": [
        {
          "benchmark_id": "dataset:hca-spatial",
          "task_id": null,
          "relative_score": 20,
          "baseline_score": 41
        }
      ],
      "candidate_benchmarks": [
        {
          "benchmark_id": "dataset:cptac-proteogenomics",
          "benchmark_title": "CPTAC proteogenomics",
          "baseline_score": 78,
          "matched_missing_facets": []
        }
      ],
      "suggested_search_facets": ["proteomics", "time-series"],
      "reason": "Matched benchmarks are taskless or below the weak relative-score threshold."
    }
  ],
  "summary": {
    "entities_total": 12,
    "entities_with_gaps": 4,
    "uncovered_entities": 2,
    "weakly_covered_entities": 1,
    "missing_facet_entities": 1
  },
  "commons_notice": null
}
```

Table output is a concise rendering of the same data:

- entity id
- gap level
- missing facets
- current match count
- candidate benchmark ids
- reason

If no rows remain after filters, print `No benchmark gaps.`.

## Candidate benchmark ordering

Candidate benchmarks are drawn from `available_unmapped_benchmarks`. In v1 they
are primarily baseline-ranked context: "benchmarks not already matched anywhere
in this opportunity report." For each gap row:

1. Normalize the row's missing modalities and signal types.
2. Normalize each candidate's `unmapped_facets`.
3. Compute `matched_missing_facets` as the intersection.
4. Sort by:
   - count of `matched_missing_facets` descending (forward-compatible; expected
     to be zero for GAP facets under the v1 exact matcher),
   - `baseline_score` descending,
   - `benchmark_id` ascending.

If a row has no missing facets, candidates still appear, sorted by baseline
score. This keeps uncovered entities useful even when their text does not
mention one of the high-value facets.

With the current exact controlled-facet matcher, `matched_missing_facets` is
expected to be empty for GAP facets in v1. A candidate appears in
`available_unmapped_benchmarks` only when no entity matched it. If a project
entity contains GAP facet `X` and a benchmark declares `X`, the exact facet
overlap makes that benchmark a matched opportunity, so it is no longer
available as an unmapped candidate. Keep `matched_missing_facets` in the JSON
contract for forward compatibility with future fuzzy or semantic matching, but
do not present it as the actionable v1 signal. The actionable v1 signal is
`suggested_search_facets`, combined with baseline-ranked candidate benchmarks.

## Summary semantics

`entities_total` is the number of unique entities visible to the projected
opportunity report after `--entity` filtering. It is computed from the union of
entity ids appearing in:

- `matched_opportunities`
- `coverage_gaps`
- `unmapped_project_entities`

`entities_with_gaps` is the number of rows in `benchmark_gaps` after filters.
The three level-specific counts are also after filters. This makes the summary
consistent with what the user is looking at.

`entities_total` is intentionally computed before `--facet` row filtering. For
example, `--facet time-series` can return `entities_total: 2` and
`entities_with_gaps: 1` when two project entities were inspected but only one
remaining gap row mentions `time-series`.

## Error handling

- Invalid `--entity` input follows the existing opportunities command behavior:
  translate `EntityCommandError` into `click.ClickException`.
- Commons failures are not fatal. `commons_notice` passes through from
  `opportunity_report()` and the CLI prints
  `notice: commons benchmarks unavailable (<notice>)` to stderr.
- Invalid `--facet` values fail at the Click boundary before `gaps_report()`
  runs.

## Testing strategy

- Unit-test `gaps_report()` as a projection over real `opportunity_report()`
  fixtures rather than mocking loaders.
- Assert the precedence rule with an entity that is both weak and missing a
  high-value facet.
- Assert candidate output is baseline-ranked in v1 and keeps
  `matched_missing_facets: []` under exact matching.
- Assert `suggested_search_facets` contains the missing high-value facets.
- Assert `--facet` filters by missing high-value facet and does not reuse
  entity-kind terminology.
- Assert CLI JSON shape, table empty state, invalid entity handling, and commons
  degradation behavior.

## Future work

- Calibrate the weak threshold using real projects and calibration output.
- Add graph-aware belief gap mapping once benchmark-to-belief relations become
  typed edges.
- Add a mutating scaffold command only after read-only gap reports are trusted.
- Consider first-class gap entities if repeated human triage shows stable,
  actionable research needs.

# Benchmark Actionability Tuning Design

## Status

Draft for review.

## Context

The 2026-06-30 actionability calibration found that benchmark metadata is now
good enough to expose many concrete test rows, but the default reports are still
too fallback-heavy to be useful as triage surfaces.

Across the four active calibration projects:

- `248` concrete non-fallback benchmark-test rows were available.
- `122` were runnable and `126` were metadata-only.
- `2327` benchmark-gap candidate rows were emitted.
- `2160 / 2327` gap candidate rows were fallback candidates.

The main problem is therefore not missing task metadata. It is report
actionability: fallback-only candidates dominate the visible surface, and the
unmapped-term evidence is noisy enough that it cannot reliably drive facet
lexicon tuning.

## Goals

- Make `science benchmark gaps` and `science benchmark tests` easier to use for
  action-oriented triage.
- Preserve existing deterministic, local-first behavior.
- Preserve existing JSON fields so current consumers do not break.
- Keep fallback candidates available as diagnostics and coarse inventory
  signals, while making entity-specific evidence the main default signal.
- Clean up unmapped-term evidence so lexicon tuning starts from plausible domain
  terms rather than project slugs and generic workflow vocabulary.

## Non-Goals

- No embeddings or semantic search.
- No graph-aware belief mapping.
- No commons metadata changes.
- No automatic facet-lexicon mutation.
- No removal of fallback candidates from JSON payloads.
- No change to opportunity matching or benchmark scoring formulas.

## Design Summary

Add an actionability layer over the existing reports. This layer changes default
ordering, summaries, and evidence categorization, but it does not create a new
matcher or a new benchmark model.

The existing `gaps_report()` and `benchmark_tests_report()` remain the source of
truth. The implementation should reuse the current candidate classification:

- entity-specific candidate: has `matched_missing_facets` or
  `matched_hint_facets`;
- fallback candidate: has a `fallback:*` reason note;
- concrete test row: task metadata is complete;
- runnable test row: readiness label is `runnable`.

## `science benchmark gaps`

### JSON Contract

Keep the existing top-level shape and existing `benchmark_gaps[].candidate_benchmarks`
field unchanged. Add one row-level field:

```json
{
  "candidate_mode": "fallback-only"
}
```

`candidate_mode` is additive and uses the same row-level semantics as the
evidence report:

- `entity-specific`: any candidate has matched missing or hint facets;
- `fallback-only`: candidates exist but all are fallback candidates;
- `none`: no candidates exist.

This gives JSON consumers the same signal the default table uses without
requiring them to recompute the mode from candidate internals.

Add actionability summary fields under the existing `summary` object. The
numbers below are illustrative and based on the 2026-06-30 calibration; they are
not expected to reproduce exactly in every project run:

```json
{
  "candidate_rows": 2327,
  "entity_specific_candidate_rows": 167,
  "fallback_candidate_rows": 2160,
  "fallback_candidate_ratio": 0.928,
  "gap_candidate_mode_counts": {
    "entity-specific": 48,
    "fallback-only": 720,
    "none": 0
  }
}
```

`gap_candidate_mode_counts` counts gap rows, not candidate rows. A gap row is:

- `entity-specific` when any candidate has matched missing or hint facets;
- `fallback-only` when candidates exist but all are fallback candidates;
- `none` when no candidates exist.

The evidence report should read this row-level `candidate_mode` instead of
recomputing the same value from `candidate_benchmarks`. This keeps the mode
classification behind one chokepoint.

These fields are additive. They do not replace `calibration`,
`calibration_summary`, or `evidence_report`.

The candidate counts must come from one shared helper used by both
`_gap_summary()` and `gap_calibration_summary()`. `candidate_rows`,
`entity_specific_candidate_rows`, and `fallback_candidate_rows` already exist in
`gap_calibration_summary()` today; the implementation should move that counting
logic behind a small single-source helper instead of creating a second
comprehension that can drift.

### Table Output

The default table should keep the current gap rows, but make fallback status
visible without flooding the main cells:

- Add a compact candidate-mode indicator per row:
  `entity-specific`, `fallback-only`, or `none`.
- For `fallback-only` rows, show a compact candidate cell such as the first
  fallback id plus `+N fallback`, where `N` is the number of additional fallback
  candidates already present in that row's capped `candidate_benchmarks` list.
- Do not imply that one row mixes entity-specific and fallback candidates.
  `_candidate_rows()` currently returns either the entity-specific list or the
  fallback list, never both.
- Keep detailed fallback diagnostics in `--calibration-summary` and
  `--evidence-report`.

No new flag is required for v1. JSON still contains complete fallback details.
The table simply stops presenting fallback candidates as equally actionable.

## `science benchmark tests`

### Sorting

Keep concrete rows ahead of draft-needed rows, then order by source:

1. `opportunity-relative`
2. `gap-candidate`
3. `gap-fallback`

This preserves the existing concrete-first guarantee. Within a
`test_plan_state` bucket, matched opportunities and entity-specific gap
candidates sort ahead of fallback rows. This means a concrete `gap-candidate`
row remains ahead of a draft-needed `opportunity-relative` row; the source order
only applies after the state bucket has been chosen.

Within each state/source bucket, sort readiness by this total order:

1. `runnable`
2. `stage-needed`
3. `metadata-only`
4. `blocked`

Then sort by higher `priority_score`, followed by stable identifiers.

This preserves fallback rows but prevents high-scoring generic fallback rows
from sorting above more actionable matched opportunity or entity-specific gap
rows.

### Summary

Add source-count fields to the existing `summary` object:

```json
{
  "source_counts": {
    "opportunity-relative": 122,
    "gap-candidate": 44,
    "gap-fallback": 2160
  },
  "fallback_rows": 2160,
  "fallback_row_ratio": 0.928
}
```

The existing `--exclude-fallback`, `--source`, `--readiness`, and
`--runnable-only` filters remain unchanged. Filtering continues to happen before
sorting, so `--exclude-fallback` still removes `gap-fallback` rows before the new
ordering is applied.

## Evidence Report Term Hygiene

The existing evidence report already exposes `unmapped_high_value_terms`, but
the calibration showed the top terms are mixed:

- project-local labels: `mm30`, `pais`, `cbioportal`;
- generic workflow/modeling terms: `models`, `catalog`, `project`;
- possible domain terms: `cytogenetic`, `expression`, `mutation`,
  `post-infectious`, `lesion`.

Add a deterministic term categorization step for evidence output. The shape
below is illustrative; example terms are not a list to hardcode:

```json
{
  "term_categories": {
    "domain_candidate_terms": [
      {"term": "cytogenetic", "count": 19, "example_entities": ["hypothesis:0002-cytogenetic-distinct-entities"]}
    ],
    "project_local_terms": [
      {"term": "cbioportal", "count": 17, "example_entities": ["hypothesis:0001-non-tumor-signal-contamination"]}
    ],
    "workflow_or_modeling_terms": [
      {"term": "catalog", "count": 25, "example_entities": ["hypothesis:0000-working-model"]}
    ],
    "other_terms": []
  }
}
```

Keep `lexicon_candidates` unchanged for compatibility: it remains the same
all-category top term list currently returned by the evidence report. Add
`summary.top_domain_candidate_terms` and `term_categories.domain_candidate_terms`
as the cleaner actionability surface for lexicon tuning. Consumers that want the
new behavior should read the new domain-specific fields.

### Categorization Rules

Use structural checks and shared token hygiene where possible. Avoid embedding
specific active project names in library code.

- `project_local_terms`: tokens structurally derived from the current project,
  including normalized project-root path segments, project root stem tokens, and
  entity-id stems. The implementation may also consume an existing project
  metadata field for aliases if one is already available, but v1 should not add
  a new config surface only for this report.
- `workflow_or_modeling_terms`: generic terms that are useful for project prose
  but poor benchmark facets. Before adding a new list, audit overlap with
  `_UNMAPPED_TERM_EXCLUSIONS`, `_STOP_TOKENS`, `_phrase_tokens()`, and
  `FACET_HINT_TERMS`; terms already excluded upstream should not be reclassified
  downstream. Any remaining v1 list should be small, shared, and named as
  workflow/modeling evidence hygiene rather than project-specific special
  cases.
- `domain_candidate_terms`: retained unmapped terms not in the excluded sets and
  not classified as project-local or workflow/modeling.
- `other_terms`: reserved for future categories; empty in v1 unless a term is
  intentionally retained but should not be lexicon-ranked. It is included as an
  intentionally inert forward-compatibility slot.

These rules are intentionally conservative. The purpose is to improve ranking
hygiene, not to decide that every domain candidate should become a facet hint.

## Error Handling

No new hard errors are introduced.

- Unknown facet filters keep using the existing normalization and `ValueError`
  behavior.
- Commons degradation behavior is unchanged.
- Evidence categorization is best-effort over already-retained tokens. It should
  never suppress existing gap rows, candidates, or benchmark test rows.

## Testing

Add focused tests for:

- `gaps_report()` summary includes candidate row counts, fallback ratio, and
  gap-row candidate-mode counts.
- `benchmark gaps` table output visibly distinguishes fallback-only rows from
  entity-specific rows.
- `benchmark_tests_report()` sorts `opportunity-relative` and `gap-candidate`
  rows ahead of `gap-fallback` rows even when fallback scores are higher.
- `benchmark_tests_report()` sorts `runnable` before `metadata-only` within the
  same `test_plan_state` and `priority_source` bucket.
- `benchmark_tests_report()` summary includes source counts and fallback ratio.
- `gaps_report(evidence_report=True)` categorizes calibration terms:
  `cytogenetic`, `mutation`, `post-infectious`, and `lesion` as domain
  candidates; structurally-derived project path/id terms as project-local; and
  retained workflow/modeling terms as workflow/modeling.
- `lexicon_candidates` remains compatible with the previous all-category top
  unmapped-term list, while `summary.top_domain_candidate_terms` and
  `term_categories.domain_candidate_terms` expose the cleaner lexicon-tuning
  surface.
- Existing `--exclude-fallback`, `--source`, `--readiness`, and
  `--runnable-only` behavior remains unchanged.

## Calibration Check

After implementation, rerun the four-project calibration from
`docs/audits/benchmark-actionability-calibration-2026-06-30.md`.

Expected qualitative outcome:

- Default table triage is no longer dominated by fallback-only candidates.
- JSON still contains fallback candidates for downstream analysis.
- `summary.top_domain_candidate_terms` and
  `term_categories.domain_candidate_terms` are no longer dominated by
  project-local or workflow terms.
- The fallback candidate ratio may remain high, but it is visible as a
  diagnostic rather than driving the primary action surface.

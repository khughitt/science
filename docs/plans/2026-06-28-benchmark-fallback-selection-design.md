# Benchmark Fallback Selection Design

## Goal

Make fallback candidates in benchmark gap reports more useful by reducing
repeated top-three fallback rows while preserving entity-specific candidate
behavior and existing candidate scores.

## Non-Goals

- Do not change `candidate_score` component math.
- Do not change entity-specific candidate ranking.
- Do not add semantic embeddings or belief-graph matching.
- Do not use project-global mutable selection state.

## Selection Policy

Fallback selection only applies when a gap row has no entity-specific candidates.
Entity-specific candidates are still returned before any fallback logic.

Fallback rows are sorted into quality tiers by:

1. `candidate_score` descending
2. `baseline_score` descending

Within a quality tier, candidates are rotated by a stable hash of the project
entity id, then selected lexically by benchmark id after rotation. This creates
diversity across entities only among equally-ranked fallback candidates. A
higher-quality tier is always exhausted before a lower-quality tier is used.

The fallback limit stays `min(3, limit)`.

## Diagnostics

Fallback rows keep the existing `fallback:*` reason notes and gain one
selection note:

- `selected:diversity-rotation` when the selected row came from a rotated tier
  with more candidates than remaining slots.
- `selected:generic-baseline` when selected from baseline-quality fallback
  rows without a diversity rotation.
- `selected:task-ready` when selected because task readiness was the only
  positive fallback signal.
- `selected:available-benchmark` when no positive score signal exists.

`top_fallback_reasons` continues to count only `fallback:*` notes. Add
`top_fallback_selection_reasons` to single-project and batch calibration
summaries, counting only `selected:*` notes.

## CLI Contract

`science benchmark gaps --calibration-summary --format json` and
`science benchmark gap-calibration --format json` expose
`top_fallback_selection_reasons`.

Table output adds `top_fallback_selection_reasons` beside the existing fallback
diagnostics.

## Expected Effect

On projects where many fallback candidates tie on quality, different gap rows
should see different fallback triples. When only three candidates exist or when
quality tiers differ, output remains effectively unchanged.

## Testing

Tests should verify:

- Equal-quality fallback candidates rotate across multiple generic entities.
- Higher-quality fallback tiers still outrank lower-quality tiers.
- Fallback reason summaries do not count `selected:*` notes as fallback reasons.
- Summary and batch aggregate reports include `top_fallback_selection_reasons`.
- CLI table output renders the new diagnostic row.


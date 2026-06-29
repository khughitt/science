# Benchmark Gap Evidence Extraction v1 Design

## Goal

Make benchmark gap outputs explain why project entities do or do not connect to
benchmark facets, and surface high-signal project terms that are not yet mapped
by the deterministic facet hint lexicon.

## Context

After the commons benchmark seed expansion, `science benchmark gap-calibration`
over the four active projects still reports a fallback-heavy candidate set:

- `entity_specific_candidate_rows`: 51
- `fallback_candidate_rows`: 2274
- `fallback_candidate_ratio`: 0.978

This means the candidate substrate is broader, but most project entities still
do not produce entity-specific benchmark evidence. Adding more seeds now would
only help at the margin unless we can see which project terms fail to become
facet hints or facet matches.

## Decision

Add an opt-in evidence report to `science benchmark gaps` and `gaps_report()`.
The report is a pure projection over the existing opportunity/gap analysis. It
does not change matching, ranking, fallback selection, or benchmark metadata.

The public CLI flag is:

```bash
science benchmark gaps --evidence-report
```

For JSON output, `--evidence-report` adds a top-level `evidence_report` object.
For table output, it renders a compact "Gap Evidence" table after the existing
gap table.

## JSON Contract

When disabled:

```json
"evidence_report": {"enabled": false}
```

When enabled:

```json
"evidence_report": {
  "enabled": true,
  "summary": {
    "entities_total": 3,
    "entities_with_no_facet_hints": 1,
    "entities_with_fallback_only_candidates": 1,
    "top_unmapped_project_terms": [
      {"term": "organoid", "count": 2, "example_entities": ["hypothesis:0001-organoid"]}
    ]
  },
  "entities": {
    "hypothesis:0001-organoid": {
      "candidate_mode": "fallback-only",
      "tokens": ["organoid", "therapy"],
      "facet_hints": [],
      "matched_facets": [],
      "suggested_search_facets": [],
      "unmapped_high_value_terms": ["organoid", "therapy"],
      "why_no_specific_candidate": ["no-facet-hints", "only-fallback-candidates"]
    }
  },
  "lexicon_candidates": [
    {
      "term": "organoid",
      "count": 2,
      "example_entities": ["hypothesis:0001-organoid"],
      "suggested_facets": []
    }
  ]
}
```

## Semantics

`candidate_mode` is one of:

- `entity-specific`: at least one candidate has `matched_missing_facets` or
  `matched_hint_facets`.
- `fallback-only`: candidates exist, but all are fallback candidates.
- `none`: no candidates are present.

`matched_facets` is the union of:

- current matched opportunity row modalities and signal types;
- candidate `matched_missing_facets`;
- candidate `matched_hint_facets`.

`unmapped_high_value_terms` are retained project entity tokens that are not:

- already mapped by `FACET_HINT_TERMS`;
- part of any `FACET_HINT_PHRASES`;
- present in `matched_facets`;
- in the current benchmark gap hint facet vocabulary;
- generic entity-id fragments, entity kind labels, or common workflow tokens.

`why_no_specific_candidate` is deterministic:

- `no-facet-hints`: entity produced no facet hints.
- `hints-have-no-candidate-facet-overlap`: entity has hints but no candidate
  matched those hints.
- `only-fallback-candidates`: candidates exist but none are entity-specific.
- `no-candidates`: no candidates were returned.
- `current-match-too-weak`: the gap row is weak rather than uncovered.

## Lexicon Candidates

The report aggregates `unmapped_high_value_terms` across entities. It does not
auto-map them to facets. Manual tuning remains required because terms such as
`therapy`, `clone`, or `organoid` can imply different benchmark needs depending
on context.

Terms are sorted by descending count, then lexically. Each term includes up to
three example entity ids.

## Non-Goals

- No embeddings or semantic search.
- No graph-aware belief mapping.
- No automatic lexicon mutation.
- No changes to candidate ranking or fallback selection.
- No changes to existing `calibration` or `calibration_summary` contracts.

## Testing

Add unit coverage for:

- fallback-only rows with unmapped terms;
- entity-specific rows that do not report fallback-only reasons;
- current matched facets contributing to `matched_facets`;
- JSON/table CLI exposure;
- a small lexicon tuning case that maps real project vocabulary without
  creating direct facet matches accidentally.

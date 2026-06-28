---
id: "plan:2026-06-28-benchmark-gap-calibration-v2-design"
type: "plan"
title: "Benchmark gap calibration v2"
status: "proposed"
created: "2026-06-28"
updated: "2026-06-28"
related:
  - "plan:2026-06-26-benchmark-grounded-model-assessment-design"
  - "plan:2026-06-27-benchmark-opportunities-design"
  - "plan:2026-06-28-benchmark-gaps-design"
---

# Benchmark gap calibration v2

## Purpose

The first `science benchmark gaps` implementation correctly exposes uncovered,
weak, and missing-facet rows as a projection over `science benchmark
opportunities`. A calibration pass over active biology / omics projects showed
that the report is technically consistent but not yet actionable enough:

- Most rows are `uncovered`.
- `missing-facet` rows are absent in sampled projects, so
  `suggested_search_facets` is usually empty.
- `candidate_benchmarks` are project-global because they come from
  `available_unmapped_benchmarks`; many gap rows receive the same candidates.
- Some opportunity matches are driven by broad tokens such as `cancer` or
  `varies`.

This design tightens the deterministic calibration layer while preserving the
read-only, human-review posture. It should make gap rows answer:

> For this specific project entity, what benchmark facets appear worth looking
> for next, and which benchmark-capable datasets are plausible near misses?

## Calibration Inputs

The observed behavior came from read-only runs against further-along projects:

- `~/d/health/processes/post-acute-infection`
- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/natural-systems`
- `~/d/cancer/data-sources/cbioportal`

The design does not encode project-specific rules from those runs. They are
used only to tune generic failure modes: noisy tokens, empty missing-facet
signals, and non-specific candidate lists.

## Goals

- Keep `gaps_report()` consistent with `opportunity_report()`; no divergent
  entity or benchmark loading path.
- Replace project-global candidate rows with per-entity near-miss candidates.
- Infer actionable facet hints from entity text even when there is no current
  benchmark match.
- Make calibration evidence visible for gap rows, not only matched
  opportunities.
- Reduce false-positive matches from broad domain tokens and boilerplate.
- Preserve deterministic, inspectable scoring; no embeddings or LLM judgments.

## Non-goals

- No graph-aware belief mapping.
- No automatic benchmark gap entity creation.
- No benchmark evaluation plan generation.
- No semantic or fuzzy matching in this tranche.
- No new benchmark metadata fields.
- No changes to commons seed records required for the feature to work.

## Architecture

Keep `opportunity_report()` as the source of truth for loaded project entities,
benchmark datasets, matched opportunities, coverage gaps, and commons notices.
Add one internal analysis layer in `science_tool.benchmark_opportunities` that
is computed from the same loaded entities and dataset contexts used by
`opportunity_report()`:

```text
load entities + datasets
  -> dataset contexts
  -> matched opportunities
  -> opportunity report
  -> per-entity gap diagnostics
  -> gaps report
```

The new diagnostic layer is not a second positive matcher. It may score
near-miss candidates for an entity, but it must not change
`matched_opportunities`, `coverage_gaps`, or `unmapped_project_entities`.
`gaps_report()` should still call the shared opportunity assembly path once and
project over its output plus the diagnostic payload.

If implementation needs to avoid recomputing contexts, extract a private
assembly helper such as `_opportunity_analysis()` that returns the public
`OpportunityReport` plus internal entity/context objects. Both
`opportunity_report()` and `gaps_report()` should use that helper rather than
copying loader logic.

## Facet Hint Lexicon

Add a small controlled hint lexicon for gap discovery. These hints infer
high-value benchmark facets from entity text; they are not positive benchmark
matches by themselves.

Initial mappings:

| Entity token or phrase | Facet hint |
| --- | --- |
| `intervention`, `drug`, `compound`, `knockout`, `perturb`, `perturbation` | `perturbation` |
| `time-series`, `timeseries`, `temporal`, `dynamic`, `longitudinal`, `trajectory` | `time-series` |
| `proteomic`, `proteomics`, `protein`, `phosphoproteomic`, `phosphoproteomics` | `proteomics` |
| `spatial`, `region`, `microenvironment`, `neighborhood` | `spatial` |
| `multimodal`, `multi-modal`, `multiomic`, `multi-omic`, `proteogenomic`, `proteogenomics` | `multimodal` |
| `single-cell`, `singlecell`, `scrna`, `scRNA-seq`, `single-cell-rna-seq` | `single-cell-rna-seq` |
| `transfer`, `generalization`, `cross-context`, `cross context`, `external validation` | `cross-context-generalization` |

Only the union of `GAP_MODALITIES`, `GAP_SIGNAL_TYPES`, and existing
high-value opportunity facets should be emitted as structured hints. Unknown
tokens may appear in calibration evidence but should not become
`suggested_search_facets`.

`suggested_search_facets` should be computed as:

1. Missing facets already supplied by `coverage_gaps`.
2. Facet hints inferred from the entity's title and content preview.
3. Facets represented in weak current matches only when the match is taskless or
   below the weak threshold.

The list is normalized, de-duplicated, and sorted with the high-value gap
facets first.

## Token Hygiene

The calibration pass showed that several tokens are too broad for positive
matching. Update token handling so these tokens can be retained for calibration
display but do not create `facet_overlap` points:

- broad domains: `biology`, `cancer`
- vague catalog values: `varies`
- entity/document boilerplate: `claim`, `statement`, `summary`, `question`,
  `hypothesis`, `proposition`
- generic workflow terms already treated as stop tokens: `analysis`, `cell`,
  `data`, `dataset`, `evidence`, `model`, `result`, `response`

This should be implemented as explicit scoring hygiene, not as silent
post-filtering of rows. Calibration output should show whether a token was
dropped as a stop token, broad token, short token, or retained entity token.

The stoplist is a calibration knob. Changes to it should be covered by tests
that show the intended false-positive suppression.

## Near-Miss Candidate Rows

Replace `candidate_benchmarks` in gap rows with per-entity near-miss candidates.
Candidates should be selected from benchmark contexts not already represented in
the entity's `current_matches`; they are not limited to
`available_unmapped_benchmarks`.

Each candidate row should include:

```json
{
  "benchmark_id": "dataset:cptac-proteogenomics",
  "benchmark_title": "CPTAC proteogenomics",
  "baseline_score": 78,
  "candidate_score": 32,
  "matched_missing_facets": ["proteomics"],
  "matched_hint_facets": ["proteomics", "multimodal"],
  "reason_notes": [
    "entity-hint:proteomics",
    "entity-hint:multimodal",
    "high-baseline"
  ]
}
```

`matched_missing_facets` remains for compatibility with the current JSON
contract, but it is no longer the only evidence column. In v2 the actionable
fields are `matched_hint_facets`, `candidate_score`, and `reason_notes`.

Initial candidate scoring:

- `missing_facet_overlap` (0-30): missing facets from `coverage_gaps` that the
  candidate declares.
- `hint_facet_overlap` (0-30): inferred entity facet hints that the candidate
  declares.
- `task_readiness` (0-20): derived from baseline task completeness and
  readiness components, not recomputed separately.
- `baseline_quality` (0-20): scaled from the existing `baseline_score`.

Clamp `candidate_score` to 100. Do not include candidates with
`candidate_score == 0` unless an entity has no scored candidates at all. In
that fallback case, include at most three high-baseline benchmark candidates
with `reason_notes: ["high-baseline-fallback"]` so the report stays useful but
does not pretend there was entity-specific evidence.

Default candidate ordering:

1. `candidate_score` descending
2. count of `matched_hint_facets` descending
3. `baseline_score` descending
4. `benchmark_id` ascending

Limit table output to the top three candidates per gap row. JSON may include up
to five candidates per row to preserve useful detail without flooding large
projects.

## Gap Calibration Report

Add `--calibration-report` to `science benchmark gaps`.

For JSON output, add a top-level `calibration` object:

```json
{
  "enabled": true,
  "gap_entity_evidence": {
    "hypothesis:0005-dynamic-homeostasis": {
      "entity_tokens": ["dynamic", "homeostasis", "perturbation"],
      "dropped_tokens": {
        "stop": ["response"],
        "broad": ["cancer"],
        "short": []
      },
      "facet_hints": ["perturbation", "time-series"],
      "gap_level_reason": "No matched benchmark opportunities for this entity."
    }
  },
  "candidate_evidence": [
    {
      "entity_id": "hypothesis:0005-dynamic-homeostasis",
      "benchmark_id": "dataset:sciplex3",
      "candidate_score": 52,
      "components": {
        "missing_facet_overlap": 0,
        "hint_facet_overlap": 30,
        "task_readiness": 12,
        "baseline_quality": 10
      },
      "reason_notes": ["entity-hint:perturbation", "high-baseline"]
    }
  ]
}
```

For table output, `--calibration-report` should append a compact calibration
table after the normal gap table, mirroring `science benchmark opportunities
--calibration-report`. The table can render JSON values in folded cells; it does
not need a custom interactive layout.

When `--format json` is used without `--calibration-report`, include
`"calibration": {"enabled": false}` for shape stability.

## Output Contract Changes

The public `science benchmark gaps --format json` payload becomes:

```json
{
  "benchmark_gaps": [],
  "summary": {
    "entities_total": 0,
    "entities_with_gaps": 0,
    "uncovered_entities": 0,
    "weakly_covered_entities": 0,
    "missing_facet_entities": 0
  },
  "calibration": {
    "enabled": false
  },
  "commons_notice": null
}
```

Existing row fields remain. `candidate_benchmarks[]` is extended additively with
`candidate_score`, `matched_hint_facets`, and `reason_notes`.

`--facet` filtering continues to filter by `missing_modalities`,
`missing_signal_types`, and `suggested_search_facets`. This means an uncovered
row with inferred `time-series` text can appear under
`science benchmark gaps --facet time-series` even if it has no
`coverage_gaps` row.

`entities_total` remains the number of entities visible to the opportunity
analysis after `--entity` filtering and before `--facet` filtering. The
level-specific summary counts remain after filters, matching the displayed rows.

## Error Handling

- Invalid `--facet` values still fail early with a Click error.
- Commons unavailability still returns local rows plus `commons_notice`.
- Empty projects return stable empty sections and `calibration.enabled`.
- Missing optional benchmark metadata should reduce candidate score rather than
  crash.
- Candidate scoring should use cached dataset contexts; do not call
  readiness/model validation per entity-candidate row.

## Testing

Add focused tests for:

- Entity facet hints populate `suggested_search_facets` for uncovered rows.
- `--facet` can select an uncovered row via inferred facet hints.
- Candidate rows are per-entity and can include benchmarks that are matched
  elsewhere in the project but not for that entity.
- Candidate ordering prefers hint overlap over a generic high-baseline fallback.
- Broad tokens such as `cancer` and `varies` do not create positive
  `facet_overlap` matches.
- Gap calibration JSON includes entity token evidence, dropped broad tokens,
  facet hints, candidate score components, and reason notes.
- Existing commons notice behavior and entity resolution remain unchanged.

## Success Criteria

- Running `science benchmark gaps --commons --domain biology --format json`
  against active biology projects produces entity-specific candidate variation
  instead of the same global candidate list for most uncovered rows.
- `suggested_search_facets` is populated for obvious entity language such as
  perturbation, longitudinal/time-series, proteomics, spatial, and multimodal.
- Noisy broad-token matches observed during calibration are suppressed by tests.
- The report remains deterministic, read-only, and explainable from JSON alone.

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

Keep `opportunity_report()` as the source of truth for the public opportunity
payload: loaded project entities, benchmark datasets, matched opportunities,
coverage gaps, and commons notices all come from one assembly path. Extract a
private `_opportunity_analysis()` helper in
`science_tool.benchmark_opportunities` that loads entities and datasets,
builds cached dataset contexts, computes matched rows, and returns the public
`OpportunityReport` plus the internal entity/context objects needed for
diagnostics:

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
Both public functions should project over `_opportunity_analysis()`:

- `opportunity_report()` returns only the public opportunity payload.
- `gaps_report()` uses the same public payload plus cached entities and dataset
  contexts for per-entity diagnostics.

This helper is required, not optional. Candidate scoring needs cached
`DatasetOpportunityContext` values such as baseline components,
`scoreable_facet_tokens`, and readiness-derived penalties. Recomputing those
inside entity-candidate loops would reintroduce repeated readiness/model
validation and risk drift from opportunity scoring.

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

Define one public emittable facet set, `BENCHMARK_GAP_HINT_FACETS`, as the
normalized union of `GAP_MODALITIES`, `GAP_SIGNAL_TYPES`, and existing
high-value opportunity facets that the command may suggest. The initial set is:

- `proteomics`
- `spatial`
- `multimodal`
- `perturbation`
- `time-series`
- `cross-context-generalization`
- `longitudinal`
- `multi-omic`
- `single-cell-rna-seq`

Unknown tokens may appear in calibration evidence but should not become
`suggested_search_facets`. The `--facet` valid set must be exactly
`BENCHMARK_GAP_HINT_FACETS` after normalization. This prevents drift where a
row can emit `suggested_search_facets: ["single-cell-rna-seq"]` but
`science benchmark gaps --facet single-cell-rna-seq` rejects the value.

`suggested_search_facets` should be computed as:

1. Missing facets already supplied by `coverage_gaps`.
2. Facet hints inferred from the entity's title and content preview.
3. Facets represented in weak current matches only when the match is taskless or
   below the weak threshold.

The list is normalized, de-duplicated, and sorted by
`BENCHMARK_GAP_HINT_FACETS` priority order, then lexical order for any future
facets added outside the constant. Candidate `matched_hint_facets`,
`matched_missing_facets`, and calibration `facet_hints` use the same ordering.

## Token Hygiene

The calibration pass showed that several tokens are too broad for positive
matching, but they live on different token surfaces. Split token hygiene by
surface instead of using one catch-all set.

Dataset controlled-facet exclusions extend `BROAD_NON_SCOREABLE_FACETS`. These
tokens can appear in dataset domains, modalities, signal types, or benchmark
kinds and therefore can create `facet_overlap` unless excluded:

- `biology`
- `cancer`
- `varies`

Entity-token suppressions extend the entity text token gate used before hint
inference and `facet_overlap`. These are project document/kind words or generic
workflow terms; they should be retained in calibration evidence but not in
`ProjectBenchmarkEntity.tokens`:

- `claim`
- `statement`
- `summary`
- `question`
- `hypothesis`
- `proposition`
- `analysis`
- `cell`
- `data`
- `dataset`
- `evidence`
- `model`
- `result`
- `response`

Suppressing `question`, `hypothesis`, and `proposition` as text tokens must not
affect kind-aware scoring. `_kind_signal_points()` reads the entity kind and
entity tokens separately; the entity kind remains available even when the word
`hypothesis` is removed from text tokens.

This should be implemented as explicit scoring hygiene, not as silent
post-filtering of rows. Calibration output should show whether a token was
dropped as a stop token, broad dataset-facet token, broad entity token, short
token, or retained entity token.

The live scoring path should use the cleaned token sets only. The fuller
dropped-token record is display evidence and must not leak back into
`facet_overlap`, hint inference, or candidate scoring.

The stoplist is a calibration knob. Changes to it should be covered by tests
that show the intended false-positive suppression.

## Near-Miss Candidate Rows

Replace `candidate_benchmarks` in gap rows with per-entity near-miss candidates.
Candidates should be selected from cached benchmark contexts not already
represented in the entity's `current_matches`; they are not limited to
`available_unmapped_benchmarks`. Score all entity-candidate pairs in one pass
over cached contexts. Do not recompute baseline score, readiness, or controlled
facet tokens inside the per-row loop.

Near-miss candidates depend on hint-only vocabulary. If an entity text contains
the same normalized token that a benchmark declares as a scoreable controlled
facet, the benchmark is a positive `matched_opportunity` and is excluded from
near-miss candidates for that entity. For example, `perturbation` can match a
benchmark that declares `signal_types: [perturbation]`, while `drug`,
`compound`, or `knockout` can infer a perturbation hint without creating that
positive exact-facet match.

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

Initial candidate scoring is additive and intentionally favors entity-specific
evidence:

- `missing_facet_overlap` (0-30): missing facets from `coverage_gaps` that the
  candidate declares, `10` points per facet, capped at `30`.
- `hint_facet_overlap` (0-35): inferred entity facet hints that the candidate
  declares, `10` points per facet, capped at `35`.
- `task_readiness` (0-20): scaled only from cached baseline
  `task_completeness` and `readiness` components:
  `round(((task_completeness / 30) * 12) + ((readiness / 15) * 8))`.
- `baseline_quality` (0-15): scaled from baseline components that are not
  already counted in `task_readiness`: `signal_value`, `modality_value`, and
  `limitations`, using
  `round(((signal_value + modality_value + limitations) / 55) * 15)`.

This avoids double-counting task completeness and readiness through both
`task_readiness` and `baseline_quality`. A benchmark with no entity-specific
facet evidence can earn at most `35` points from entity-agnostic quality
signals, which keeps candidate variation driven primarily by the entity's
missing facets and inferred hints.

Clamp `candidate_score` to 100. Do not include candidates with
`candidate_score == 0` unless an entity has no scored candidates at all. In
that fallback case, include at most three high-baseline benchmark candidates
with `reason_notes: ["high-baseline-fallback"]` so the report stays useful but
does not pretend there was entity-specific evidence. Fallback rows are used only
when there are zero scored candidates; they are never mixed with scored rows and
still count against the JSON/table row limits.

Because `task_readiness` contributes entity-agnostic points for benchmark
records with complete tasks and usable readiness, `candidate_score == 0` will be
uncommon in catalogs with task-rich benchmarks. In those cases the report may
still show candidates without entity-specific hint overlap, bounded by the
entity-agnostic ceiling described above. Calibration output should make that
distinction visible through zero `missing_facet_overlap` /
`hint_facet_overlap` components.

Emit `high-baseline` on scored candidate rows when `baseline_quality >= 8`.
Emit `task-ready` when `task_readiness >= 12`. These notes are deterministic
labels derived from the component values, not independent scoring rules.

Default candidate ordering:

1. `candidate_score` descending
2. count of `matched_hint_facets` descending
3. `baseline_score` descending
4. `benchmark_id` ascending

Limit table output to the top three candidates per gap row. JSON may include up
to five candidates per row to preserve useful detail without flooding large
projects.

`reason_notes` are sorted deterministically by note family priority
(`missing-facet`, `entity-hint`, `task-ready`, `high-baseline`,
`high-baseline-fallback`) and then lexical order within a family. Synonym-based
hints converge to one normalized facet before note generation, so
`intervention` and `perturbation` should not produce duplicate
`entity-hint:perturbation` notes.

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
        "broad_entity": ["summary"],
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
      "dropped_dataset_facets": ["cancer"],
      "components": {
        "missing_facet_overlap": 0,
        "hint_facet_overlap": 30,
        "task_readiness": 12,
        "baseline_quality": 10
      },
      "reason_notes": ["entity-hint:perturbation", "task-ready", "high-baseline"]
    }
  ]
}
```

`gap_entity_evidence[].dropped_tokens` reports entity-side token decisions.
`candidate_evidence[].dropped_dataset_facets` reports candidate dataset
controlled facets that were excluded from scoring because they are broad.

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
`missing_signal_types`, and `suggested_search_facets`. The valid normalized
values for `--facet` are exactly `BENCHMARK_GAP_HINT_FACETS`. This means an
uncovered row with inferred `time-series` text can appear under
`science benchmark gaps --facet time-series` even if it has no
`coverage_gaps` row, and a row with inferred `single-cell-rna-seq` text can be
selected with `--facet single-cell-rna-seq`.

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
- The `--facet` valid set equals the emittable hint facet set, including
  `single-cell-rna-seq`.
- Candidate-score component tests verify that task/readiness contributions are
  not counted again inside `baseline_quality`.
- Existing v1 `candidate_benchmarks` fields still serialize for consumers:
  `benchmark_id`, `benchmark_title`, `baseline_score`, and
  `matched_missing_facets`.
- Existing commons notice behavior and entity resolution remain unchanged.

## Success Criteria

- Running `science benchmark gaps --commons --domain biology --format json`
  against active biology projects produces entity-specific candidate variation
  instead of the same global candidate list for most uncovered rows.
- `suggested_search_facets` is populated for obvious entity language such as
  perturbation, longitudinal/time-series, proteomics, spatial, and multimodal.
- Noisy broad-token matches observed during calibration are suppressed by tests.
- The report remains deterministic, read-only, and explainable from JSON alone.

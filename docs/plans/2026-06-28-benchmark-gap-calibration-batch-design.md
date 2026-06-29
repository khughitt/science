# Benchmark Gap Calibration Batch Design

## Goal

Add a read-only batch calibration surface for benchmark gaps across real projects.
The command should answer: which projects have actionable benchmark candidates,
which facets remain suggested-but-unmatched, and which fallback benchmarks are
dominating the report.

## Non-Goals

- Do not change benchmark matching, candidate scoring, or fallback semantics.
- Do not introduce named project-set configuration in v1.
- Do not write to project directories or commons.
- Do not infer belief graph gaps. This remains a projection over benchmark gap
  reports.

## Command Surface

Add a sibling command to `science benchmark gaps`:

```bash
science benchmark gap-calibration \
  --project pai=~/d/health/processes/post-acute-infection \
  --project mm=~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --format table
```

`--project` is repeatable and accepts `label=path`. Labels must be non-empty and
unique after trimming. Paths are expanded with `Path.expanduser()` and resolved.
The command fails early on malformed entries, duplicate labels, or nonexistent
project roots.

`--commons`, `--domain`, and `--facet` mirror `benchmark gaps` and are applied to
every project. `--format` supports `table` and `json`.

## Architecture

The batch command is an orchestration layer over existing single-project APIs:

1. Parse and validate the project list.
2. For each project, call `gaps_report(..., include_commons=..., domain=..., facet=...)`.
3. Summarize each report with `gap_calibration_summary(report)`.
4. Build an aggregate projection from the per-project summaries and rows.

No low-level dataset contexts, entity loaders, or scoring helpers are called from
the batch layer. This keeps `gaps_report()` as the single source of truth for
gap semantics.

## JSON Contract

The JSON payload has three top-level fields:

```json
{
  "projects": [
    {
      "label": "mm",
      "project_root": "~/d/cancer/cancer-types/multiple-myeloma",
      "summary": {},
      "calibration_summary": {},
      "commons_notice": null
    }
  ],
  "aggregate": {
    "project_count": 1,
    "gap_rows": 503,
    "candidate_rows": 1491,
    "entity_specific_candidate_rows": 33,
    "fallback_candidate_rows": 1458,
    "fallback_candidate_ratio": 0.978,
    "top_suggested_facets": [],
    "top_matched_hint_facets": [],
    "top_fallback_benchmarks": []
  },
  "commons_notices": []
}
```

`project_root` is rendered with `~/d/` when it is under the user's `~/d`
directory; otherwise it is rendered as a resolved absolute path. This follows
the repository documentation convention while keeping JSON deterministic on the
current machine.

`commons_notices` contains `{label, notice}` rows for projects where commons
could not be loaded. The command does not fail the whole batch for commons
degradation, matching `benchmark gaps`.

## Table Contract

Table output renders two sections:

- `Benchmark Gap Calibration` with one row per project.
- `Aggregate Benchmark Gap Calibration` with totals and top-list rows.

The per-project table includes label, gap rows, entity-specific candidates,
fallback candidates, fallback ratio, top suggested facets, top matched hint
facets, and top fallback benchmarks.

## Aggregate Semantics

Aggregate scalar fields are sums across projects, except:

- `project_count`: number of project entries processed.
- `fallback_candidate_ratio`: fallback candidates divided by all candidates,
  rounded to three decimals; `null` when there are no candidates.
- Top lists: counters merged across project-level top evidence by walking the
  actual gap rows, not by re-summing truncated per-project top lists.

## Error Handling

- No `--project` entries: Click error.
- Malformed `--project`: Click error explaining `label=path`.
- Duplicate label: Click error naming the label.
- Missing project path: Click error naming the label and path.
- Invalid `--facet`: let `gaps_report()` raise the existing value error.
- Commons unavailable: keep per-project notices and continue.

## Testing

Use temp project fixtures with local benchmark records and hypothesis entities.
Tests should cover:

- Project spec parsing rejects malformed and duplicate labels.
- JSON batch output includes project rows and aggregate totals.
- Aggregate top counters are computed from actual rows.
- Table output renders both expected sections.
- Commons notices are preserved per project without failing the batch.


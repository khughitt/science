# Benchmark Gaps Context-Fit Design

## Context

`science benchmark tests` and `science benchmark test-triage` now expose
deterministic `context_fit` labels:

- `direct-fit`
- `adjacent-fit`
- `method-fit`
- `blocked-fit`
- `generic-fallback`
- `out-of-context`

The labels made benchmark-test triage substantially easier to read. In the
active-project smoke pass after that merge:

- multiple myeloma retained focused direct-fit concrete rows;
- cBioPortal retained a small focused direct-fit set;
- natural systems no longer produced a large direct-fit biology fallback set;
- multiple myeloma fallback-diagnostic rows were all `generic-fallback`.

The remaining mismatch is that `science benchmark gaps` still reports candidate
benchmarks without this context/actionability axis. It already distinguishes
candidate mode (`entity-specific`, `fallback-only`, `none`) and carries candidate
reason notes, but a table row like "fallback-only, candidates: BRCA METABRIC,
CPTAC, DREAM4" still forces a reader to infer whether those candidates are
directly relevant, adjacent, method-only, blocked, or generic fallback.

The implementation should not create a second context-fit classifier. The
existing benchmark-test projection already converts gap candidates into
benchmark-test rows via `_rows_for_gap_candidate(...)`; those rows have the
right internal evidence and already pass through the context-fit classifier.
`benchmark gaps` should reuse that path to summarize candidate fit.

## Goals

- Add context-fit/actionability labels to `science benchmark gaps` candidate
  rows.
- Keep `gaps_report()` raw matching, candidate scoring, gap levels, and
  candidate-mode logic unchanged.
- Make the default table more actionable by showing candidate fit next to each
  candidate.
- Add a `--context-fit` filter to `science benchmark gaps` using the same
  vocabulary and OR semantics as `benchmark tests` and `benchmark test-triage`.
- Preserve JSON compatibility through additive fields only.
- Reuse existing context-fit derivation from benchmark-test row building; do not
  fork the classifier.

## Non-Goals

- Do not change `candidate_score`, fallback rotation, near-miss scoring, gap
  levels, or facet-hint inference.
- Do not hide fallback candidates from raw JSON unless the user explicitly
  requests a `--context-fit` filter.
- Do not add embeddings, ontology lookup, network access, or model calls.
- Do not rewrite commons benchmark metadata as part of this slice.
- Do not project context-fit onto `benchmark list` or `benchmark opportunities`
  in this slice.

## Recommended Approach

Use `benchmark tests` as the context-fit source of truth for gap candidates.

For each `BenchmarkGapRow` candidate:

1. Resolve its `DatasetOpportunityContext` from the already-loaded
   `OpportunityAnalysis.contexts`.
2. Resolve the `ProjectBenchmarkEntity` from the same analysis.
3. Determine the candidate `PrioritySource`:
   - `gap-fallback` when `_is_fallback_candidate(candidate)` is true;
   - otherwise `gap-candidate`.
4. Reuse `_rows_for_gap_candidate(...)` with:
   - the candidate score;
   - the stored candidate score components;
   - candidate reason notes;
   - `_matched_facets_for_context(context, extra=matched candidate facets)`.
5. Summarize the produced `BenchmarkTestRow` list back onto the candidate:
   - choose the best `context_fit` by `CONTEXT_FIT_ORDER`;
   - merge `context_fit_reasons`;
   - merge `context_fit_warnings`;
   - expose optional task-level detail only in calibration/evidence views, not
     in the default candidate row.

This keeps gap candidate fit identical to the benchmark-test projection for the
same `(entity, benchmark)` pair. It also avoids reloading commons, reparsing
datasets, or inventing gap-specific context rules.

## Row Contract

Extend `GapCandidateBenchmarkRow` additively:

```json
{
  "benchmark_id": "dataset:cptac-gbm-2021-proteogenomics",
  "benchmark_title": "CPTAC GBM proteogenomics (cBioPortal, Cell 2021)",
  "baseline_score": 86,
  "candidate_score": 42,
  "matched_missing_facets": [],
  "matched_hint_facets": ["proteomics", "multi-omic"],
  "reason_notes": ["entity-hint:proteomics", "task-ready"],
  "context_fit": "direct-fit",
  "context_fit_reasons": [
    "specific-context:cbioportal",
    "task-signal:proteomics",
    "task-support:supported"
  ],
  "context_fit_warnings": ["cross-disease:gbm-vs-breast"]
}
```

Extend `BenchmarkGapSummary` additively:

```json
{
  "candidate_context_fit_counts": {
    "direct-fit": 12,
    "adjacent-fit": 4,
    "method-fit": 7,
    "blocked-fit": 2,
    "generic-fallback": 180,
    "out-of-context": 0
  }
}
```

Do not add a row-level `context_fit` to `BenchmarkGapRow` in v1. A gap row can
have multiple candidates with different fits; reducing that to a single label
would be lossy and would invite consumers to treat a mixed row as homogeneous.
Use the summary map and candidate-level fields instead.

## Filtering

Add repeatable `--context-fit` to `science benchmark gaps`.

Semantics:

- Valid values are exactly `CONTEXT_FITS`.
- Multiple flags are ORed.
- Filtering is applied after candidate rows have been annotated.
- For each gap row, candidate lists are filtered to candidates whose
  `context_fit` is in the requested set.
- Gap rows with no remaining candidates are omitted from the filtered output.
- `candidate_mode` is recomputed from the filtered candidate list.
- `summary` is computed from the filtered row set.
- `evidence_report` and `calibration` reflect the filtered row set.

This makes:

```bash
science benchmark gaps --context-fit direct-fit --commons
```

an action queue for gap rows with direct-fit candidate benchmarks, while:

```bash
science benchmark gaps --context-fit generic-fallback --commons
```

remains an explicit diagnostic view of fallback-only noise.

No new `--exclude-fallback` flag is needed in v1. `--context-fit
generic-fallback` and the existing `candidate_mode` summary are enough to audit
fallback behavior without adding another filter vocabulary.

## Table Output

The default table should keep its existing columns, but candidate rendering
should include fit labels. Example:

```text
dataset:cptac-gbm-2021-proteogenomics [direct-fit] (42)
dataset:brca-metabric [adjacent-fit] (35)
dataset:dream4-in-silico-network [method-fit] (28)
dataset:l1000-cmap [generic-fallback] (55)
```

If a row has mixed candidate fits, the table should show each candidate's label
rather than a row-level label. If candidates are truncated in the existing
formatter, the truncation notice should still be based on candidate count, not
fit count.

JSON consumers get the full candidate-level fields.

## Calibration and Evidence Reports

`calibration.candidate_evidence[]` should include:

- `context_fit`;
- `context_fit_reasons`;
- `context_fit_warnings`.

`evidence_report.entities[*]` should remain mostly unchanged. It already reports
`candidate_mode`, `matched_facets`, `suggested_search_facets`, and
`why_no_specific_candidate`. Candidate-level context fit belongs with candidates,
not entity evidence.

If future calibration shows repeated false-positive fit labels, tune the shared
context-fit classifier rather than adding gap-only suppressions.

## Data Flow

`gaps_report()` already calls `_opportunity_analysis(...)`, which returns:

- project entities;
- dataset contexts;
- matched opportunity rows.

The new flow is:

1. Build raw gap rows and candidate score index exactly as today.
2. Annotate each candidate with context fit using a helper such as
   `_annotate_gap_candidate_context_fit(...)`.
3. Apply optional `context_fit` filtering to candidate lists.
4. Recompute `candidate_mode` for rows after filtering.
5. Drop empty candidate rows only when a context-fit filter is active.
6. Sort rows by existing gap-level/entity ordering.
7. Build summary, calibration, and evidence payloads from the final rows.

The helper should not call `benchmark_tests_report()` because that would recurse
through `gaps_report()`. It should reuse the lower-level `_rows_for_gap_candidate`
path directly.

## Error Handling

- Unknown context-fit values raise `ValueError("unknown benchmark context-fit
  value: ...")`, reusing `_normalize_context_fit_filters(...)`.
- CLI wraps that `ValueError` in `click.ClickException`, matching
  `benchmark tests` and `benchmark test-triage`.
- If a candidate references an unknown benchmark context, fail early with a
  clear `ValueError`; do not silently omit the candidate.
- If a gap row references an unknown entity, fail early with a clear
  `ValueError`.
- Commons unavailability behavior remains unchanged and continues to surface as
  `commons_notice`.

## Alternatives Considered

### A. Reuse benchmark-test row projection directly

This is the recommended approach. It produces the same context-fit label for the
same gap candidate that `benchmark tests` would produce and keeps the classifier
single-sourced.

Tradeoff: a candidate with multiple tasks may summarize several task-level rows
into one candidate-level label. That is acceptable because `benchmark gaps`
currently operates at benchmark-candidate granularity, not task granularity.

### B. Add a gap-specific context-fit classifier

Rejected. It would be simpler to wire at first, but it would drift from
`benchmark tests`, especially around blocked support, broad-context tokens,
limitations, and numeric-token suppression.

### C. Only add table decoration, no JSON fields

Rejected. The table would become more readable, but JSON consumers and review
artifacts would still have to recompute or scrape the label. Additive JSON fields
are cheap and match the rest of the benchmark report surfaces.

## Testing

Add focused tests for:

- `gaps_report()` annotates entity-specific candidates with `context_fit`,
  reasons, and warnings.
- fallback-only candidates with no project/entity context classify as
  `generic-fallback`.
- blocked task-support candidates classify as `blocked-fit`, except blocked
  fallback-only rows with no context remain `generic-fallback` with the
  `blocked-support-fallback` warning.
- `--context-fit direct-fit` filters candidate lists and omits rows with no
  remaining candidates.
- multiple `--context-fit` flags OR together.
- unknown `--context-fit` values fail in API and CLI paths.
- table output includes candidate fit labels.
- `calibration.candidate_evidence[]` includes context-fit fields when
  `--calibration-report` is enabled.
- natural-systems active-project smoke does not produce a large direct-fit
  `benchmark gaps --context-fit direct-fit` result.

Regression tests should include the recent context-fit calibration cases:

- limitations-only overlap must not create `direct-fit`;
- numeric/year-only overlap must not create `specific-context`;
- coarse domains such as `health` must not create `specific-context`;
- readiness-blocked candidates must not appear as `direct-fit`.

## Success Criteria

- `science benchmark gaps` JSON is additive and includes candidate-level
  context-fit fields.
- `science benchmark gaps --context-fit direct-fit` works and returns only rows
  with at least one direct-fit candidate.
- Table output makes fallback/generic candidates visually distinguishable from
  direct or adjacent candidates.
- Existing unfiltered `benchmark gaps` row counts and candidate scoring remain
  stable except for additive fields and summary additions.
- Existing `benchmark tests` and `benchmark test-triage` behavior remains
  unchanged.
- Active-project smoke confirms the new gaps view reduces generic fallback noise
  without hiding it from explicit diagnostic filters.

## Implementation Notes

- Prefer a small internal `GapCandidateContextFit` helper type or `TypedDict`
  only if it avoids tuple unpacking. Do not create a new public vocabulary.
- Reuse `ContextFit`, `CONTEXT_FITS`, `CONTEXT_FIT_ORDER`, and
  `_normalize_context_fit_filters(...)`.
- Keep candidate context-fit annotation near gap candidate construction so the
  candidate score index and dataset contexts are already in scope.
- Use `~/d/...` paths in smoke-test documentation.
- Keep review artifacts and docs in `docs/plans/`; do not create new docs
  subdirectories for this slice.

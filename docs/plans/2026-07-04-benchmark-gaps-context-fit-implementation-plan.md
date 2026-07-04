# Benchmark Gaps Context-Fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add candidate-level `context_fit` labels, summaries, filtering, and table rendering to `science benchmark gaps` by reusing the existing benchmark-test context-fit projection.

**Architecture:** `gaps_report()` remains the source of benchmark gap rows and candidate scoring. After raw candidate construction, each gap candidate is projected through the same `_rows_for_gap_candidate(...)` path that `benchmark_tests_report()` already uses, summarized back to candidate-level fields, optionally filtered by `--context-fit`, and then passed to existing summary/calibration/evidence builders. The CLI only adds a repeatable filter option and renders the additive candidate fields.

**Tech Stack:** Python 3.12, Click, Rich, pytest, existing `science_tool.benchmark_opportunities` report builders.

---

## File Structure

- `science/src/science_tool/benchmark_opportunities.py`
  - Extend gap candidate/report TypedDicts with additive context-fit fields.
  - Add candidate annotation helpers that reuse `_rows_for_gap_candidate(...)`.
  - Add candidate-context-fit summary counts.
  - Add context-fit filtering to `gaps_report(...)`.
  - Add context-fit fields to gap calibration candidate evidence.
- `science/src/science_tool/cli.py`
  - Add repeatable `--context-fit` to `science benchmark gaps`.
  - Pass the filter through to `gaps_report(...)`.
  - Render `candidate_id [context-fit] (score)` in the gaps table.
- `science/tests/test_benchmark_opportunities.py`
  - Add report-level tests for annotation, cross-surface consistency, fallback behavior, filtering, summary counts, calibration evidence, and API errors.
- `science/tests/test_benchmark_cli.py`
  - Add CLI tests for `--context-fit`, invalid filter values, and table rendering.

## Execution Notes

- Work from this isolated worktree:

```bash
cd ~/d/science/.worktrees/benchmark-gaps-context-fit-design
```

- Confirm imports resolve to the worktree before running tests:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c "import science_tool; print(science_tool.__file__)"
```

Expected: the printed path starts with `~/d/science/.worktrees/benchmark-gaps-context-fit-design/science/src/science_tool/`.

- Use the same `PYTHONPATH=science/src:science/model/src` prefix for every pytest/ruff command in this plan so the worktree source cannot be shadowed by the editable install from the main checkout.

---

### Task 1: Annotate Gap Candidates With Context Fit

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing report tests for gap candidate context fit**

Add these tests in `science/tests/test_benchmark_opportunities.py` near the existing context-fit tests, after `test_context_fit_blocked_fallback_without_context_is_generic`.

```python
def test_gaps_report_projects_context_fit_fields_for_entity_specific_candidate(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0600-sciplex-gap",
        """
id: hypothesis:0600-sciplex-gap
type: hypothesis
title: Sci-Plex benchmark gap
""",
        body="Sci-plex drug compound knockout screen should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    payload = gaps_report(tmp_path)
    row = payload["benchmark_gaps"][0]
    candidate = row["candidate_benchmarks"][0]

    assert row["candidate_mode"] == "entity-specific"
    assert candidate["benchmark_id"] == "dataset:sciplex3"
    assert candidate["context_fit"] == "direct-fit"
    assert "specific-context:sci-plex" in candidate["context_fit_reasons"]
    assert "task-support:supported" in candidate["context_fit_reasons"]
    assert candidate["context_fit_warnings"] == []
    assert payload["summary"]["candidate_context_fit_counts"]["direct-fit"] == 1


def test_gaps_report_context_fit_matches_benchmark_tests_projection(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report, gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0601-sciplex-gap",
        """
id: hypothesis:0601-sciplex-gap
type: hypothesis
title: Sci-Plex consistency gap
""",
        body="Sci-plex drug compound screen should be tested.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    gap_payload = gaps_report(tmp_path)
    test_payload = benchmark_tests_report(tmp_path)
    gap_candidate = gap_payload["benchmark_gaps"][0]["candidate_benchmarks"][0]
    test_rows = [
        row
        for row in test_payload["benchmark_tests"]
        if row["entity_id"] == "hypothesis:0601-sciplex-gap"
        and row["benchmark_id"] == "dataset:sciplex3"
        and row["priority_source"] == "gap-candidate"
    ]

    assert test_rows
    assert gap_candidate["context_fit"] == test_rows[0]["context_fit"]
    assert set(gap_candidate["context_fit_reasons"]) <= {
        reason for row in test_rows for reason in row["context_fit_reasons"]
    }
    assert set(gap_candidate["context_fit_warnings"]) <= {
        warning for row in test_rows for warning in row["context_fit_warnings"]
    }


def test_gaps_report_blocked_fallback_without_context_is_generic(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0602-unmapped",
        """
id: hypothesis:0602-unmapped
type: hypothesis
title: Unmapped benchmark entity
""",
        body="No specific benchmark facet appears here.",
    )
    _write_dataset(
        tmp_path,
        "blocked-mmrf",
        """
id: dataset:blocked-mmrf
type: dataset
title: MMRF CoMMpass
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: outcome prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: measured-outcome
        description: progression
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
""",
    )

    payload = gaps_report(tmp_path)
    candidate = payload["benchmark_gaps"][0]["candidate_benchmarks"][0]

    assert candidate["context_fit"] == "generic-fallback"
    assert "blocked-support-fallback" in candidate["context_fit_warnings"]
    assert payload["summary"]["candidate_context_fit_counts"]["generic-fallback"] == 1
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_projects_context_fit_fields_for_entity_specific_candidate \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_context_fit_matches_benchmark_tests_projection \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_blocked_fallback_without_context_is_generic \
  -q
```

Expected: FAIL because `GapCandidateBenchmarkRow` candidates do not yet contain `context_fit`, `context_fit_reasons`, `context_fit_warnings`, or `candidate_context_fit_counts`.

- [ ] **Step 3: Extend gap candidate and calibration TypedDicts**

In `science/src/science_tool/benchmark_opportunities.py`, update `GapCandidateBenchmarkRow`, `GapCandidateEvidence`, and `BenchmarkGapSummary`.

```python
class GapCandidateBenchmarkRow(TypedDict):
    benchmark_id: str
    benchmark_title: str
    baseline_score: int
    candidate_score: int
    matched_missing_facets: list[str]
    matched_hint_facets: list[str]
    reason_notes: list[str]
    context_fit: NotRequired[ContextFit]
    context_fit_reasons: NotRequired[list[str]]
    context_fit_warnings: NotRequired[list[str]]
```

```python
class GapCandidateEvidence(TypedDict):
    entity_id: str
    benchmark_id: str
    candidate_score: int
    dropped_dataset_facets: list[str]
    components: dict[str, int]
    reason_notes: list[str]
    context_fit: NotRequired[ContextFit]
    context_fit_reasons: NotRequired[list[str]]
    context_fit_warnings: NotRequired[list[str]]
```

```python
class BenchmarkGapSummary(TypedDict):
    entities_total: int
    entities_with_gaps: int
    uncovered_entities: int
    weakly_covered_entities: int
    missing_facet_entities: int
    candidate_rows: int
    entity_specific_candidate_rows: int
    fallback_candidate_rows: int
    fallback_candidate_ratio: float
    gap_candidate_mode_counts: dict[CandidateMode, int]
    candidate_context_fit_counts: dict[ContextFit, int]
```

- [ ] **Step 4: Add candidate annotation helpers**

Add these helpers in `science/src/science_tool/benchmark_opportunities.py` near `_candidate_rows(...)`, after `_select_fallback_rows(...)` and before `_candidate_rows(...)`.

```python
def _summarize_gap_candidate_test_rows(rows: list[BenchmarkTestRow]) -> tuple[ContextFit, list[str], list[str]]:
    if not rows:
        raise ValueError("gap candidate produced no benchmark-test rows")
    context_fit = min((row["context_fit"] for row in rows), key=lambda value: CONTEXT_FIT_ORDER[value])
    reasons = sorted({reason for row in rows for reason in row["context_fit_reasons"]})
    warnings = sorted({warning for row in rows for warning in row["context_fit_warnings"]})
    return context_fit, reasons, warnings


def _annotate_gap_candidate_context_fit(
    candidate: GapCandidateBenchmarkRow,
    *,
    entity: ProjectBenchmarkEntity,
    project_context_tokens: frozenset[str],
    context: DatasetOpportunityContext,
    score: CandidateScore,
) -> GapCandidateBenchmarkRow:
    priority_source: PrioritySource = "gap-fallback" if _is_fallback_candidate(candidate) else "gap-candidate"
    extra_facets = set(candidate["matched_missing_facets"]) | set(candidate["matched_hint_facets"])
    rows = _rows_for_gap_candidate(
        entity=entity,
        project_context_tokens=project_context_tokens,
        context=context,
        priority_score=int(candidate["candidate_score"]),
        priority_source=priority_source,
        source_components=dict(score.components),
        reason_notes=list(candidate["reason_notes"]),
        matched_facets=_matched_facets_for_context(context, extra=extra_facets),
    )
    context_fit, reasons, warnings = _summarize_gap_candidate_test_rows(rows)
    return {
        **candidate,
        "context_fit": context_fit,
        "context_fit_reasons": reasons,
        "context_fit_warnings": warnings,
    }
```

Do not call `_gap_candidate_components(...)` from this helper. It re-runs `_candidate_score(...)` from an assembled payload and is intentionally avoided for `gaps_report()` annotation.

- [ ] **Step 5: Add summary counting for candidate context fit**

Add this helper near `_gap_candidate_counts(...)`.

```python
def _gap_candidate_context_fit_counts(rows: list[BenchmarkGapRow]) -> dict[ContextFit, int]:
    counts = _empty_context_fit_counts()
    for row in rows:
        for candidate in row["candidate_benchmarks"]:
            context_fit = candidate.get("context_fit")
            if context_fit is not None:
                counts[context_fit] += 1
    return counts
```

Then update `_gap_summary(...)` so it includes the new count map.

```python
def _gap_summary(rows: list[BenchmarkGapRow], entities_total: int) -> BenchmarkGapSummary:
    return {
        "entities_total": entities_total,
        "entities_with_gaps": len(rows),
        "uncovered_entities": sum(1 for row in rows if row["gap_level"] == "uncovered"),
        "weakly_covered_entities": sum(1 for row in rows if row["gap_level"] == "weak"),
        "missing_facet_entities": sum(1 for row in rows if row["gap_level"] == "missing-facet"),
        **_gap_candidate_counts(rows),
        "candidate_context_fit_counts": _gap_candidate_context_fit_counts(rows),
    }
```

- [ ] **Step 6: Wire annotation into `gaps_report()`**

In `gaps_report(...)`, after `entity_by_id` and `candidate_score_index` are prepared, add context maps once:

```python
    entity_by_id = {entity.id: entity for entity in analysis.entities}
    context_by_id = {context.dataset.id: context for context in analysis.contexts}
    project_context_tokens = _project_context_tokens(project_root, analysis.entities)
    candidate_score_index: CandidateScoreIndex = {}
```

Then replace the existing `candidates = _candidate_rows(...)` assignment with:

```python
        candidates = _candidate_rows(
            current_entity_id,
            analysis.contexts,
            current_matches,
            missing_facets,
            hint_facets,
            candidate_score_index,
        )
        entity_for_context = entity_by_id.get(current_entity_id)
        if entity_for_context is None:
            raise ValueError(f"gap row references unknown entity: {current_entity_id}")
        annotated_candidates: list[GapCandidateBenchmarkRow] = []
        for candidate in candidates:
            context = context_by_id.get(candidate["benchmark_id"])
            if context is None:
                raise ValueError(f"gap candidate references unknown benchmark context: {candidate['benchmark_id']}")
            score = candidate_score_index[(current_entity_id, candidate["benchmark_id"])]
            annotated_candidates.append(
                _annotate_gap_candidate_context_fit(
                    candidate,
                    entity=entity_for_context,
                    project_context_tokens=project_context_tokens,
                    context=context,
                    score=score,
                )
            )
        candidates = annotated_candidates
```

Keep the row construction otherwise unchanged.

- [ ] **Step 7: Run tests for Task 1**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_projects_context_fit_fields_for_entity_specific_candidate \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_context_fit_matches_benchmark_tests_projection \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_blocked_fallback_without_context_is_generic \
  -q
```

Expected: PASS.

- [ ] **Step 8: Run context-fit regression tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_projects_context_fit_fields \
  science/tests/test_benchmark_opportunities.py::test_context_fit_readiness_blocked_rows_are_blocked_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_limitations_do_not_promote_direct_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_numeric_tokens_do_not_promote_direct_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_broad_tokens_do_not_promote_direct_fit \
  science/tests/test_benchmark_opportunities.py::test_context_fit_blocked_fallback_without_context_is_generic \
  -q
```

Expected: PASS. These existing tests verify the shared classifier still behaves as calibrated.

- [ ] **Step 9: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat: annotate benchmark gap candidates with context fit"
```

---

### Task 2: Add Context-Fit Filtering and Calibration Evidence

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing API tests for filtering, invalid values, and calibration evidence**

Add these tests in `science/tests/test_benchmark_opportunities.py` after the Task 1 tests.

```python
def test_gaps_report_filters_context_fit_and_recomputes_candidate_mode(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0603-direct",
        """
id: hypothesis:0603-direct
type: hypothesis
title: Direct Sci-Plex gap
""",
        body="Sci-plex drug compound screen should be benchmarked.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0604-generic",
        """
id: hypothesis:0604-generic
type: hypothesis
title: Generic fallback gap
""",
        body="No specific benchmark facet appears here.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    payload = gaps_report(tmp_path, context_fit=("direct-fit",))

    assert [row["entity_id"] for row in payload["benchmark_gaps"]] == ["hypothesis:0603-direct"]
    row = payload["benchmark_gaps"][0]
    assert row["candidate_mode"] == "entity-specific"
    assert [candidate["context_fit"] for candidate in row["candidate_benchmarks"]] == ["direct-fit"]
    assert payload["summary"]["candidate_context_fit_counts"]["direct-fit"] == 1
    assert payload["summary"]["candidate_context_fit_counts"]["generic-fallback"] == 0


def test_gaps_report_context_fit_filter_accepts_or_values(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0605-direct",
        """
id: hypothesis:0605-direct
type: hypothesis
title: Direct Sci-Plex gap
""",
        body="Sci-plex drug compound screen should be benchmarked.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0606-generic",
        """
id: hypothesis:0606-generic
type: hypothesis
title: Generic fallback gap
""",
        body="No specific benchmark facet appears here.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    payload = gaps_report(tmp_path, context_fit=("direct-fit", "generic-fallback"))
    fits = {
        candidate["context_fit"]
        for row in payload["benchmark_gaps"]
        for candidate in row["candidate_benchmarks"]
    }

    assert fits == {"direct-fit", "generic-fallback"}
    assert payload["summary"]["candidate_context_fit_counts"]["direct-fit"] == 1
    assert payload["summary"]["candidate_context_fit_counts"]["generic-fallback"] >= 1


def test_gaps_report_rejects_unknown_context_fit_filter(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    with pytest.raises(ValueError, match="unknown benchmark context-fit value: near-fit"):
        gaps_report(tmp_path, context_fit=("near-fit",))


def test_gaps_report_calibration_candidate_evidence_includes_context_fit(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0607-sciplex-calibration",
        """
id: hypothesis:0607-sciplex-calibration
type: hypothesis
title: Sci-Plex calibration gap
""",
        body="Sci-plex drug compound screen should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    payload = gaps_report(tmp_path, calibration_report=True)
    evidence = payload["calibration"]["candidate_evidence"][0]

    assert evidence["context_fit"] == "direct-fit"
    assert "specific-context:sci-plex" in evidence["context_fit_reasons"]
    assert evidence["context_fit_warnings"] == []
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_filters_context_fit_and_recomputes_candidate_mode \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_context_fit_filter_accepts_or_values \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_rejects_unknown_context_fit_filter \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_calibration_candidate_evidence_includes_context_fit \
  -q
```

Expected: FAIL because `gaps_report(...)` does not accept `context_fit` yet and calibration evidence does not include context-fit fields.

- [ ] **Step 3: Add context-fit filtering helpers**

Add these helpers in `science/src/science_tool/benchmark_opportunities.py` near `_gap_candidate_context_fit_counts(...)`.

```python
def _filter_gap_rows_by_candidate_context_fit(
    rows: list[BenchmarkGapRow],
    context_fit: Sequence[ContextFit] | None,
) -> list[BenchmarkGapRow]:
    if context_fit is None:
        return rows

    allowed = set(context_fit)
    filtered_rows: list[BenchmarkGapRow] = []
    for row in rows:
        candidates = [
            candidate
            for candidate in row["candidate_benchmarks"]
            if candidate.get("context_fit") in allowed
        ]
        if not candidates:
            continue
        filtered_rows.append(
            {
                **row,
                "candidate_benchmarks": candidates,
                "candidate_mode": _candidate_mode(candidates),
            }
        )
    return filtered_rows
```

This helper only drops rows when a context-fit filter is explicitly active. Unfiltered output keeps every candidate and only gains additive fields.

- [ ] **Step 4: Add `context_fit` to `gaps_report(...)` and apply filtering before summary/calibration**

Change the `gaps_report(...)` signature:

```python
def gaps_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    facet: str | None = None,
    context_fit: Sequence[str] | None = None,
    calibration_report: bool = False,
    evidence_report: bool = False,
) -> BenchmarkGapReport:
```

At the top of the function, normalize the filter:

```python
    normalized_facet = _normalized_gap_facet(facet)
    normalized_context_fit = _normalize_context_fit_filters(context_fit)
```

After the row loop and before `rows.sort(...)` / `_gap_calibration_payload(...)`, apply the candidate filter:

```python
    rows = _filter_gap_rows_by_candidate_context_fit(rows, normalized_context_fit)
    rows.sort(key=lambda row: (_gap_level_sort_key(row["gap_level"]), row["entity_id"]))
```

Do not add a `filters` object to `BenchmarkGapReport` in this task. Existing gaps payloads do not expose filters; this slice only changes row/candidate fields additively plus the summary map.

- [ ] **Step 5: Add context-fit fields to calibration evidence**

In `_gap_calibration_payload(...)`, extend the `candidate_evidence.append(...)` mapping.

```python
            candidate_evidence.append(
                {
                    "entity_id": row["entity_id"],
                    "benchmark_id": candidate["benchmark_id"],
                    "candidate_score": score.total,
                    "dropped_dataset_facets": _dataset_broad_facets(context),
                    "components": dict(score.components),
                    "reason_notes": list(candidate["reason_notes"]),
                    "context_fit": candidate["context_fit"],
                    "context_fit_reasons": list(candidate["context_fit_reasons"]),
                    "context_fit_warnings": list(candidate["context_fit_warnings"]),
                }
            )
```

Indexing these fields directly is intentional. Calibration should fail loudly if a future refactor passes unannotated candidates into this path.

- [ ] **Step 6: Run Task 2 tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_filters_context_fit_and_recomputes_candidate_mode \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_context_fit_filter_accepts_or_values \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_rejects_unknown_context_fit_filter \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_calibration_candidate_evidence_includes_context_fit \
  -q
```

Expected: PASS.

- [ ] **Step 7: Run affected API regression tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_filters_payload_dedupes_context_fit \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_rejects_unknown_context_fit_filter \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_sorts_with_context_fit_inside_bucket \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_filters_context_fit \
  -q
```

Expected: PASS. These verify that adding candidate annotations to `gaps_report()` did not alter `benchmark_tests_report()` or `benchmark_test_triage_report()` context-fit filtering behavior.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat: filter benchmark gaps by context fit"
```

---

### Task 3: Add CLI Flag and Table Rendering

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Add these tests in `science/tests/test_benchmark_cli.py` after `test_benchmark_gaps_cli_table_shows_candidate_mode_and_compacts_fallbacks`.

```python
def test_benchmark_gaps_cli_filters_context_fit_json(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0600-direct",
        """
id: hypothesis:0600-direct
type: hypothesis
title: Direct Sci-Plex gap
""",
        body="Sci-plex drug compound screen should be benchmarked.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0601-generic",
        """
id: hypothesis:0601-generic
type: hypothesis
title: Generic fallback gap
""",
        body="No specific benchmark facet appears here.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    result = _invoke_gaps(tmp_path, "--context-fit", "direct-fit", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [row["entity_id"] for row in payload["benchmark_gaps"]] == ["hypothesis:0600-direct"]
    candidates = payload["benchmark_gaps"][0]["candidate_benchmarks"]
    assert [candidate["context_fit"] for candidate in candidates] == ["direct-fit"]


def test_benchmark_gaps_cli_rejects_unknown_context_fit(tmp_path: Path) -> None:
    result = _invoke_gaps(tmp_path, "--context-fit", "near-fit")

    assert result.exit_code != 0
    assert "Invalid value for '--context-fit'" in result.output


def test_benchmark_gaps_cli_table_shows_candidate_context_fit(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0602-context-table",
        """
id: hypothesis:0602-context-table
type: hypothesis
title: Context table gap
""",
        body="Sci-plex drug compound screen should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    result = _invoke_gaps(tmp_path)

    assert result.exit_code == 0
    assert "dataset:sciplex3 [direct-fit]" in result.output
```

- [ ] **Step 2: Run the new CLI tests and verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_filters_context_fit_json \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_rejects_unknown_context_fit \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_table_shows_candidate_context_fit \
  -q
```

Expected: FAIL because `science benchmark gaps` does not yet expose `--context-fit`, and the table formatter does not display fit labels.

- [ ] **Step 3: Add the `--context-fit` Click option**

In `science/src/science_tool/cli.py`, add this option to the `benchmark_gaps` decorator block after `--evidence-report` and before `--format`.

```python
@click.option(
    "--context-fit",
    "context_fit",
    multiple=True,
    type=click.Choice(
        ["direct-fit", "adjacent-fit", "method-fit", "blocked-fit", "generic-fallback", "out-of-context"]
    ),
    help="Filter by benchmark context-fit label. May be supplied more than once.",
)
```

Update the function signature to include `context_fit`.

```python
def benchmark_gaps(
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    include_commons: bool,
    calibration_report: bool,
    calibration_summary: bool,
    evidence_report: bool,
    context_fit: tuple[str, ...],
    output_format: str,
    project_root: Path | None,
) -> None:
```

Pass it into `gaps_report(...)`.

```python
        payload = gaps_report(
            root,
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            facet=facet,
            context_fit=context_fit,
            calibration_report=calibration_report,
            evidence_report=evidence_report,
        )
```

- [ ] **Step 4: Render candidate context fit in the gaps table**

Replace `_format_gap_candidates_for_table(...)` with:

```python
def _format_gap_candidate_for_table(candidate: Mapping[str, Any]) -> str:
    context_fit = candidate.get("context_fit")
    label = f" [{context_fit}]" if context_fit else ""
    return f"{candidate['benchmark_id']}{label} ({candidate['candidate_score']})"


def _format_gap_candidates_for_table(row: Mapping[str, Any]) -> str:
    candidates = row["candidate_benchmarks"]
    if not candidates:
        return "-"
    if row.get("candidate_mode") == "fallback-only":
        first = _format_gap_candidate_for_table(candidates[0])
        remainder = len(candidates) - 1
        return first if remainder <= 0 else f"{first} +{remainder} fallback"
    return ", ".join(_format_gap_candidate_for_table(candidate) for candidate in candidates[:3])
```

This preserves existing fallback compaction while making the shown candidate's fit and score visible.

- [ ] **Step 5: Run Task 3 tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_filters_context_fit_json \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_rejects_unknown_context_fit \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_table_shows_candidate_context_fit \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_table_shows_candidate_mode_and_compacts_fallbacks \
  -q
```

Expected: PASS. The existing fallback compaction test must still see `+2 fallback`.

- [ ] **Step 6: Run affected CLI regression tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_evidence_report_json \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_evidence_report_table \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_filters_context_fit_or_values \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_filters_context_fit \
  -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat: expose context-fit filter for benchmark gaps"
```

---

### Task 4: Full Verification and Active-Project Smoke

**Files:**
- No code changes expected.
- Verify: `science/tests/test_benchmark_opportunities.py`, `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Run focused benchmark test suite**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run ruff on touched files**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science ruff check \
  science/src/science_tool/benchmark_opportunities.py \
  science/src/science_tool/cli.py \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py
```

Expected: PASS.

- [ ] **Step 3: Smoke `benchmark gaps --context-fit direct-fit` on multiple myeloma**

Run:

```bash
SCIENCE_PROJECT_ROOT=~/d/cancer/cancer-types/multiple-myeloma \
SCIENCE_COMMONS_ROOT=~/d/science-commons \
PYTHONPATH=science/src:science/model/src \
rtk uv run --frozen --project science science benchmark gaps --commons --context-fit direct-fit --format json > /tmp/mm-benchmark-gaps-direct-fit.json
```

Expected: command exits 0. Inspect the row count and candidate fit counts:

```bash
python - <<'PY'
import json
payload = json.load(open("/tmp/mm-benchmark-gaps-direct-fit.json"))
print("rows", len(payload["benchmark_gaps"]))
print("candidate_context_fit_counts", payload["summary"]["candidate_context_fit_counts"])
PY
```

Expected: every visible candidate has `context_fit == "direct-fit"` and the direct-fit count is nonzero if the project still has direct-fit gap candidates.

- [ ] **Step 4: Smoke `benchmark gaps --context-fit direct-fit` on natural systems**

Run:

```bash
SCIENCE_PROJECT_ROOT=~/d/natural-systems \
SCIENCE_COMMONS_ROOT=~/d/science-commons \
PYTHONPATH=science/src:science/model/src \
rtk uv run --frozen --project science science benchmark gaps --commons --context-fit direct-fit --format json > /tmp/ns-benchmark-gaps-direct-fit.json
```

Expected: command exits 0. Inspect the row count and candidate fit counts:

```bash
python - <<'PY'
import json
payload = json.load(open("/tmp/ns-benchmark-gaps-direct-fit.json"))
print("rows", len(payload["benchmark_gaps"]))
print("candidate_context_fit_counts", payload["summary"]["candidate_context_fit_counts"])
PY
```

Expected: natural systems should not show a large direct-fit biology fallback set. If the count is unexpectedly large, do not change scoring in this branch; record the observation for the next calibration slice.

- [ ] **Step 5: Smoke explicit generic fallback diagnostic view**

Run:

```bash
SCIENCE_PROJECT_ROOT=~/d/cancer/cancer-types/multiple-myeloma \
SCIENCE_COMMONS_ROOT=~/d/science-commons \
PYTHONPATH=science/src:science/model/src \
rtk uv run --frozen --project science science benchmark gaps --commons --context-fit generic-fallback --format json > /tmp/mm-benchmark-gaps-generic-fallback.json
```

Expected: command exits 0. Inspect:

```bash
python - <<'PY'
import json
payload = json.load(open("/tmp/mm-benchmark-gaps-generic-fallback.json"))
print("rows", len(payload["benchmark_gaps"]))
print("candidate_context_fit_counts", payload["summary"]["candidate_context_fit_counts"])
print("mode_counts", payload["summary"]["gap_candidate_mode_counts"])
PY
```

Expected: this view keeps generic fallback candidates visible for diagnostics instead of hiding them globally.

- [ ] **Step 6: Check git status**

Run:

```bash
rtk git status --short
```

Expected: clean worktree. If smoke-output files were accidentally written under the repo, remove or move them before final review.

- [ ] **Step 7: Commit any verification-only doc updates if needed**

If Step 3-5 uncovered a small documentation correction in `docs/plans/2026-07-04-benchmark-gaps-context-fit-design.md`, commit only that correction:

```bash
rtk git add docs/plans/2026-07-04-benchmark-gaps-context-fit-design.md
rtk git commit -m "docs: note benchmark gaps context-fit smoke results"
```

If no doc changes were made, skip this step.

---

## Self-Review Checklist

- Spec coverage:
  - Candidate-level fields: Task 1.
  - Summary counts: Task 1.
  - Context-fit filtering with OR semantics: Task 2 and Task 3.
  - Calibration candidate evidence: Task 2.
  - Table labels: Task 3.
  - Cross-surface reuse instead of gap-specific classifier: Task 1 cross-surface test and helper reuse.
  - Active-project smoke: Task 4.
- Placeholder scan:
  - No `TBD`, unbounded "handle edge cases", or unspecified test steps remain.
  - The only conditional step is Task 4 Step 7, which has an explicit skip condition.
- Type consistency:
  - `ContextFit`, `CONTEXT_FIT_ORDER`, `CandidateScore`, `CandidateScoreIndex`, `PrioritySource`, `BenchmarkTestRow`, `GapCandidateBenchmarkRow`, and `BenchmarkGapSummary` match existing names in `benchmark_opportunities.py`.
  - CLI test helpers use existing `_invoke_gaps`, `_write_entity`, and `_write_dataset` signatures.
  - `context_fit` is a `Sequence[str] | None` API input and normalizes to `tuple[ContextFit, ...] | None` through existing `_normalize_context_fit_filters(...)`.

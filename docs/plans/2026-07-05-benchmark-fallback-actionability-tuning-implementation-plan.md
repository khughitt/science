# Benchmark Fallback Actionability Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fallback display diagnostics and default table compaction so generic benchmark fallback remains visible as evidence but no longer dominates actionability views.

**Architecture:** Keep raw matching/scoring unchanged. Add one fallback display-group projection in `benchmark_opportunities.py`, surface additive diagnostics on gap and triage reports, and update `cli.py` table rendering to collapse generic fallback detail while preserving JSON row payloads.

**Tech Stack:** Python 3.12, Click, Rich tables, pytest, typed dict report contracts in `science/src/science_tool/benchmark_opportunities.py`.

---

## Scope And File Map

**Design spec:** `docs/plans/2026-07-05-benchmark-fallback-actionability-tuning-design.md`

**Modify:**

- `science/src/science_tool/benchmark_opportunities.py`
  - Add `FallbackDisplayGroup` vocabulary and group helper functions.
  - Add `fallback_diagnostics` to `BenchmarkGapReport`.
  - Add display-group fields to triage fallback diagnostics and fallback rollups.
  - Keep raw `benchmark_gaps[].candidate_benchmarks`, `benchmark_tests_report()`, and `fallback_diagnostics.rollups` complete.

- `science/src/science_tool/cli.py`
  - Collapse all-generic fallback in `benchmark gaps` table.
  - Hide generic fallback rollups from the default `benchmark test-triage` fallback detail table.
  - Print compact generic fallback diagnostics in table mode.

- `science/tests/test_benchmark_opportunities.py`
  - Add unit tests for fallback group derivation.
  - Add report-level tests for gap and triage diagnostics reconciliation.
  - Update exact rollup assertions for additive `display_group`.

- `science/tests/test_benchmark_cli.py`
  - Update gap table expectations.
  - Add CLI tests that JSON stays raw while default tables collapse generic fallback.
  - Update fallback-rollup table tests for generic-hidden behavior.

**Do not modify:**

- `baseline_score`, `candidate_score`, `relative_score`, `_candidate_rows()` selection logic, or context-fit classification.
- Benchmark commons metadata or project entities.

## Task 0: Confirm Worktree And Source Resolution

**Files:**
- None

- [ ] **Step 1: Confirm branch/worktree**

Run:

```bash
rtk git branch --show-current
rtk git rev-parse --show-toplevel
```

Expected: output contains both of these lines:

```text
benchmark-fallback-actionability-tuning-design
.worktrees/benchmark-fallback-actionability-tuning-design
```

- [ ] **Step 2: Confirm Python imports resolve to this worktree**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c "import science_tool, pathlib; print(pathlib.Path(science_tool.__file__).resolve())"
```

Expected: printed path contains:

```text
.worktrees/benchmark-fallback-actionability-tuning-design/science/src/science_tool/
```

If it points at the main checkout, keep `PYTHONPATH=science/src:science/model/src` on every pytest/science command in later tasks.

## Task 1: Add Fallback Display Group Vocabulary

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Extend the triage row test helper**

First update `_benchmark_test_row_for_triage()` in `science/tests/test_benchmark_opportunities.py` so the new tests can build realistic fallback rows. Replace the helper signature and returned fields with this version:

```python
def _benchmark_test_row_for_triage(
    *,
    entity_id: str,
    benchmark_id: str,
    test_plan_state: str = "concrete",
    readiness_label: str = "runnable",
    priority_source: str = "opportunity-relative",
    priority_score: int = 10,
    task_id: str | None = "dataset:benchmark#task",
    matched_facets: list[str] | None = None,
    needs: list[str] | None = None,
    context_fit: str = "direct-fit",
    reason_notes: list[str] | None = None,
    task_support_state: str | None = None,
    task_support_reason: str = "",
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "entity_title": entity_id.removeprefix("hypothesis:"),
        "benchmark_id": benchmark_id,
        "benchmark_title": benchmark_id.removeprefix("dataset:"),
        "dataset_class": "deposit",
        "task_id": task_id,
        "test_plan_state": test_plan_state,
        "task_type": "validation",
        "benchmark_kinds": ["static-association"],
        "readiness_label": readiness_label,
        "priority_score": priority_score,
        "priority_source": priority_source,
        "score_components": {"source": {"component": priority_score}, "baseline": {}},
        "matched_facets": matched_facets or ["perturbation"],
        "reason_notes": reason_notes or ["fixture"],
        "context_fit": context_fit,
        "context_fit_reasons": [],
        "context_fit_warnings": [],
        "prediction_target": "target" if task_id else "",
        "held_out_unit": "unit" if task_id else "",
        "metric": "auroc" if task_id else "",
        "baseline": "majority-class" if task_id else "",
        "ground_truth": {
            "type": "measured-outcome" if task_id else "",
            "description": "label" if task_id else "",
        },
        "task_support_state": task_support_state,
        "task_support_reason": task_support_reason,
        "task_support_checked_at": "",
        "task_support_evidence": [],
        "task_support_notes": [],
        "needs": needs
        or ([] if task_id else ["prediction-target", "held-out-unit", "metric", "baseline", "ground-truth"]),
    }
```

- [ ] **Step 2: Add failing unit tests for display groups**

Add these tests near `test_benchmark_test_triage_bucket_assignment_is_ordered()` in `science/tests/test_benchmark_opportunities.py`:

```python
def test_fallback_display_group_for_gap_candidates() -> None:
    from science_tool.benchmark_opportunities import _fallback_display_group_for_gap_candidate

    base = {
        "benchmark_id": "dataset:fallback",
        "benchmark_title": "Fallback",
        "baseline_score": 80,
        "candidate_score": 20,
        "matched_missing_facets": [],
        "matched_hint_facets": [],
        "context_fit": "generic-fallback",
        "context_fit_reasons": [],
        "context_fit_warnings": [],
    }

    assert (
        _fallback_display_group_for_gap_candidate(
            {**base, "reason_notes": ["fallback:baseline-quality", "selected:generic-baseline"]}
        )
        == "generic-baseline-fallback"
    )
    assert (
        _fallback_display_group_for_gap_candidate(
            {**base, "reason_notes": ["fallback:task-ready", "selected:task-ready"]}
        )
        == "generic-task-ready-fallback"
    )
    assert (
        _fallback_display_group_for_gap_candidate({**base, "reason_notes": ["fallback:available-benchmark"]})
        == "generic-available-fallback"
    )
    assert (
        _fallback_display_group_for_gap_candidate(
            {
                **base,
                "context_fit": "adjacent-fit",
                "reason_notes": ["fallback:baseline-quality"],
            }
        )
        == "specific-fallback"
    )
    assert (
        _fallback_display_group_for_gap_candidate(
            {
                **base,
                "reason_notes": ["fallback:baseline-quality"],
                "context_fit_warnings": ["blocked-support-fallback"],
            }
        )
        == "blocked-support-fallback"
    )


def test_fallback_display_group_rejects_non_fallback_candidate() -> None:
    from science_tool.benchmark_opportunities import _fallback_display_group_for_gap_candidate

    with pytest.raises(ValueError, match="non-fallback gap candidate"):
        _fallback_display_group_for_gap_candidate(
            {
                "benchmark_id": "dataset:specific",
                "benchmark_title": "Specific",
                "baseline_score": 80,
                "candidate_score": 30,
                "matched_missing_facets": ["proteomics"],
                "matched_hint_facets": [],
                "reason_notes": ["missing-facet:proteomics"],
                "context_fit": "direct-fit",
                "context_fit_reasons": [],
                "context_fit_warnings": [],
            }
        )


def test_fallback_display_group_for_test_rows() -> None:
    from science_tool.benchmark_opportunities import _fallback_display_group_for_test_row

    assert (
        _fallback_display_group_for_test_row(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:generic-baseline",
                benchmark_id="dataset:generic-baseline",
                priority_source="gap-fallback",
                context_fit="generic-fallback",
                reason_notes=["fallback:baseline-quality", "selected:generic-baseline"],
            )
        )
        == "generic-baseline-fallback"
    )
    assert (
        _fallback_display_group_for_test_row(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:generic-task",
                benchmark_id="dataset:generic-task",
                priority_source="gap-fallback",
                context_fit="generic-fallback",
                reason_notes=["fallback:task-ready", "selected:task-ready"],
            )
        )
        == "generic-task-ready-fallback"
    )
    assert (
        _fallback_display_group_for_test_row(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:specific",
                benchmark_id="dataset:specific",
                priority_source="gap-fallback",
                context_fit="adjacent-fit",
                reason_notes=["fallback:baseline-quality"],
            )
        )
        == "specific-fallback"
    )
    assert (
        _fallback_display_group_for_test_row(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:blocked",
                benchmark_id="dataset:blocked",
                priority_source="gap-fallback",
                context_fit="generic-fallback",
                reason_notes=["fallback:baseline-quality"],
                task_support_state="blocked",
            )
        )
        == "blocked-support-fallback"
    )


def test_fallback_display_group_rejects_non_fallback_test_row() -> None:
    from science_tool.benchmark_opportunities import _fallback_display_group_for_test_row

    with pytest.raises(ValueError, match="non-fallback benchmark test row"):
        _fallback_display_group_for_test_row(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:run",
                benchmark_id="dataset:run",
                priority_source="opportunity-relative",
                context_fit="direct-fit",
            )
        )
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_fallback_display_group_for_gap_candidates \
  science/tests/test_benchmark_opportunities.py::test_fallback_display_group_rejects_non_fallback_candidate \
  science/tests/test_benchmark_opportunities.py::test_fallback_display_group_for_test_rows \
  science/tests/test_benchmark_opportunities.py::test_fallback_display_group_rejects_non_fallback_test_row -q
```

Expected: FAIL with import errors for `_fallback_display_group_for_gap_candidate` and `_fallback_display_group_for_test_row`.

- [ ] **Step 4: Add vocabulary and helpers**

In `science/src/science_tool/benchmark_opportunities.py`, add the display-group type near the existing `ContextFit` / `TaskSupportCountKey` aliases:

```python
FallbackDisplayGroup = Literal[
    "specific-fallback",
    "blocked-support-fallback",
    "generic-baseline-fallback",
    "generic-task-ready-fallback",
    "generic-available-fallback",
]
```

Add constants near `READINESS_LABELS` / `CONTEXT_FITS`:

```python
FALLBACK_DISPLAY_GROUPS: tuple[FallbackDisplayGroup, ...] = (
    "specific-fallback",
    "blocked-support-fallback",
    "generic-baseline-fallback",
    "generic-task-ready-fallback",
    "generic-available-fallback",
)
GENERIC_FALLBACK_DISPLAY_GROUPS: frozenset[FallbackDisplayGroup] = frozenset(
    {
        "generic-baseline-fallback",
        "generic-task-ready-fallback",
        "generic-available-fallback",
    }
)
```

Add helpers after `_is_fallback_candidate()`:

```python
def _fallback_group_from_notes(
    *,
    benchmark_id: str,
    reason_notes: Sequence[str],
    context_fit: ContextFit,
    blocked: bool,
) -> FallbackDisplayGroup:
    if blocked:
        return "blocked-support-fallback"
    if context_fit != "generic-fallback":
        return "specific-fallback"

    notes = set(reason_notes)
    if "fallback:baseline-quality" in notes or "selected:generic-baseline" in notes:
        return "generic-baseline-fallback"
    if "fallback:task-ready" in notes or "selected:task-ready" in notes:
        return "generic-task-ready-fallback"
    if any(note.startswith("fallback:") for note in notes):
        return "generic-available-fallback"
    raise ValueError(f"fallback row has no fallback reason notes: {benchmark_id}")


def _fallback_display_group_for_gap_candidate(candidate: GapCandidateBenchmarkRow) -> FallbackDisplayGroup:
    if not _is_fallback_candidate(candidate):
        raise ValueError(f"non-fallback gap candidate passed to fallback display grouping: {candidate['benchmark_id']}")
    return _fallback_group_from_notes(
        benchmark_id=candidate["benchmark_id"],
        reason_notes=candidate["reason_notes"],
        context_fit=candidate["context_fit"],
        blocked="blocked-support-fallback" in candidate["context_fit_warnings"],
    )


def _fallback_display_group_for_test_row(row: BenchmarkTestRow) -> FallbackDisplayGroup:
    if row["priority_source"] != "gap-fallback":
        raise ValueError(f"non-fallback benchmark test row passed to fallback display grouping: {row['benchmark_id']}")
    return _fallback_group_from_notes(
        benchmark_id=row["benchmark_id"],
        reason_notes=row["reason_notes"],
        context_fit=row["context_fit"],
        blocked=_is_blocked_support_fallback(row),
    )


def _is_generic_fallback_display_group(group: FallbackDisplayGroup) -> bool:
    return group in GENERIC_FALLBACK_DISPLAY_GROUPS
```

`_fallback_display_group_for_test_row()` references `_is_blocked_support_fallback()`, which is defined later in the file. That is valid because the helper is called only at runtime after module load.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_fallback_display_group_for_gap_candidates \
  science/tests/test_benchmark_opportunities.py::test_fallback_display_group_rejects_non_fallback_candidate \
  science/tests/test_benchmark_opportunities.py::test_fallback_display_group_for_test_rows \
  science/tests/test_benchmark_opportunities.py::test_fallback_display_group_rejects_non_fallback_test_row -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat: classify benchmark fallback display groups"
```

## Task 2: Add Gap Fallback Diagnostics

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing report test**

Add this test after `test_gaps_report_blocked_fallback_without_context_is_generic()` in `science/tests/test_benchmark_opportunities.py`:

```python
def test_gaps_report_includes_fallback_diagnostics(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import FALLBACK_DISPLAY_GROUPS, gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0607-generic",
        """
id: hypothesis:0607-generic
type: hypothesis
title: Generic benchmark entity
""",
        body="No specific benchmark facet appears here.",
    )
    _write_dataset(
        tmp_path,
        "generic-a",
        """
id: dataset:generic-a
type: dataset
title: Generic A
dataset_class: deposit
local_path: data/generic-a
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
    )
    _write_dataset(
        tmp_path,
        "generic-b",
        """
id: dataset:generic-b
type: dataset
title: Generic B
dataset_class: deposit
local_path: data/generic-b
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
    )

    payload = gaps_report(tmp_path)
    candidates = [candidate for row in payload["benchmark_gaps"] for candidate in row["candidate_benchmarks"]]
    diagnostics = payload["fallback_diagnostics"]

    assert diagnostics["candidate_rows"] == len(candidates)
    assert diagnostics["generic_fallback_candidate_rows"] == len(candidates)
    assert diagnostics["specific_fallback_candidate_rows"] == 0
    assert set(diagnostics["groups"]) == set(FALLBACK_DISPLAY_GROUPS)
    assert sum(diagnostics["groups"].values()) == len(candidates)
    assert diagnostics["groups"]["generic-baseline-fallback"] == len(candidates)
    assert diagnostics["top_generic_fallback_benchmarks"][0]["benchmark_id"].startswith("dataset:generic-")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_includes_fallback_diagnostics -q
```

Expected: FAIL with `KeyError: 'fallback_diagnostics'`.

- [ ] **Step 3: Add gap diagnostics types**

In `science/src/science_tool/benchmark_opportunities.py`, add this typed dict after `BenchmarkGapSummary`:

```python
class BenchmarkGapFallbackDiagnostics(TypedDict):
    candidate_rows: int
    generic_fallback_candidate_rows: int
    specific_fallback_candidate_rows: int
    groups: dict[FallbackDisplayGroup, int]
    top_generic_fallback_benchmarks: list[BenchmarkCountRow]
```

Update `BenchmarkGapReport`:

```python
class BenchmarkGapReport(TypedDict):
    benchmark_gaps: list[BenchmarkGapRow]
    summary: BenchmarkGapSummary
    fallback_diagnostics: BenchmarkGapFallbackDiagnostics
    calibration: GapCalibrationPayload
    evidence_report: EvidenceReport
    commons_notice: str | None
```

- [ ] **Step 4: Add gap diagnostics implementation**

Add these helpers near `_top_fallback_benchmarks()`:

```python
def _empty_fallback_display_group_counts() -> dict[FallbackDisplayGroup, int]:
    return {group: 0 for group in FALLBACK_DISPLAY_GROUPS}


def _gap_fallback_diagnostics(rows: list[BenchmarkGapRow], *, top: int = 10) -> BenchmarkGapFallbackDiagnostics:
    fallback_candidates: list[GapCandidateBenchmarkRow] = []
    group_counts = _empty_fallback_display_group_counts()
    generic_benchmarks: Counter[str] = Counter()

    for row in rows:
        for candidate in row["candidate_benchmarks"]:
            if not _is_fallback_candidate(candidate):
                continue
            fallback_candidates.append(candidate)
            group = _fallback_display_group_for_gap_candidate(candidate)
            group_counts[group] += 1
            if _is_generic_fallback_display_group(group):
                generic_benchmarks[candidate["benchmark_id"]] += 1

    generic_rows = sum(group_counts[group] for group in GENERIC_FALLBACK_DISPLAY_GROUPS)
    return {
        "candidate_rows": len(fallback_candidates),
        "generic_fallback_candidate_rows": generic_rows,
        "specific_fallback_candidate_rows": group_counts["specific-fallback"],
        "groups": group_counts,
        "top_generic_fallback_benchmarks": _top_benchmark_counts(generic_benchmarks, top=top),
    }
```

Update the `return` in `gaps_report()` to include the diagnostics. Find the existing return near the end of `gaps_report()` and make it:

```python
    return {
        "benchmark_gaps": rows,
        "summary": _gap_summary(rows, entities_total=len(analysis.entities)),
        "fallback_diagnostics": _gap_fallback_diagnostics(rows),
        "calibration": _gap_calibration_payload(
            analysis.entities,
            rows,
            score_index,
            analysis.contexts,
            enabled=calibration_report,
        ),
        "evidence_report": _gap_evidence_report(analysis.entities, rows, enabled=evidence_report),
        "commons_notice": analysis.report["commons_notice"],
    }
```

Keep the exact existing arguments for `_gap_calibration_payload()` and `_gap_evidence_report()` if they differ slightly in the current file; the only required addition is `"fallback_diagnostics": _gap_fallback_diagnostics(rows)`.

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_includes_fallback_diagnostics -q
```

Expected: PASS.

- [ ] **Step 6: Run nearby gap tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_blocked_fallback_without_context_is_generic \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_filters_context_fit_and_recomputes_candidate_mode \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_context_fit_filter_accepts_or_values -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat: add benchmark gap fallback diagnostics"
```

## Task 3: Add Triage Fallback Display Diagnostics

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing triage diagnostics assertions**

In `test_benchmark_test_triage_fallback_diagnostics_roll_up_visible_fallback_rows()`, update the expected rollup dictionary to include `display_group` near the existing `reason_notes` field:

```python
        "display_group": "generic-baseline-fallback",
```

Then add these assertions after the rollup equality:

```python
    assert payload["fallback_diagnostics"]["display_group_counts"] == {
        "specific-fallback": 0,
        "blocked-support-fallback": 0,
        "generic-baseline-fallback": 2,
        "generic-task-ready-fallback": 0,
        "generic-available-fallback": 0,
    }
    assert payload["fallback_diagnostics"]["hidden_generic_fallback_rows"] == 2
    assert payload["fallback_diagnostics"]["shown_fallback_rows"] == 0
    assert payload["fallback_diagnostics"]["terminal_visible_rollup_count"] == 0
    assert payload["fallback_diagnostics"]["terminal_hidden_rollup_count"] == 1
    assert payload["fallback_diagnostics"]["top_generic_fallback_benchmarks"] == [
        {"benchmark_id": "dataset:supported-fallback-rollup", "count": 2}
    ]
```

- [ ] **Step 2: Add failing blocked/suppression diagnostics assertions**

In `test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default()`, add:

```python
    assert payload["fallback_diagnostics"]["display_group_counts"] == {
        "specific-fallback": 0,
        "blocked-support-fallback": 0,
        "generic-baseline-fallback": 1,
        "generic-task-ready-fallback": 0,
        "generic-available-fallback": 0,
    }
    assert payload["fallback_diagnostics"]["hidden_generic_fallback_rows"] == 1
    assert payload["fallback_diagnostics"]["shown_fallback_rows"] == 0
```

In `test_benchmark_test_triage_report_include_blocked_fallback_restores_rows()`, add after the rollup assertions:

```python
    assert rollups[0]["display_group"] == "blocked-support-fallback"
    assert payload["fallback_diagnostics"]["display_group_counts"] == {
        "specific-fallback": 0,
        "blocked-support-fallback": 1,
        "generic-baseline-fallback": 0,
        "generic-task-ready-fallback": 0,
        "generic-available-fallback": 0,
    }
    assert payload["fallback_diagnostics"]["hidden_generic_fallback_rows"] == 0
    assert payload["fallback_diagnostics"]["shown_fallback_rows"] == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_diagnostics_roll_up_visible_fallback_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_include_blocked_fallback_restores_rows -q
```

Expected: FAIL with missing `display_group` / missing diagnostics keys.

- [ ] **Step 4: Extend fallback rollup and diagnostics types**

In `BenchmarkTestFallbackRollup`, add:

```python
    display_group: FallbackDisplayGroup
```

In `BenchmarkTestTriageFallbackDiagnostics`, add:

```python
    display_group_counts: dict[FallbackDisplayGroup, int]
    hidden_generic_fallback_rows: int
    shown_fallback_rows: int
    top_generic_fallback_benchmarks: list[BenchmarkCountRow]
    top_generic_fallback_reasons: list[ReasonCountRow]
    terminal_visible_rollup_count: int
    terminal_hidden_rollup_count: int
```

- [ ] **Step 5: Add triage diagnostics implementation**

In `_benchmark_test_fallback_rollups()`, compute the group for each rollup group and add it to the rollup dictionary.

Immediately before the existing line that starts `reason_notes = sorted(`, add:

```python
        display_groups = {_fallback_display_group_for_test_row(row) for row in group_rows}
        if len(display_groups) > 1:
            raise ValueError(f"fallback rollup has inconsistent display groups for {_rollup_task_label(benchmark_id, task_id)}")
```

Add this key to the rollup dict:

```python
                "display_group": next(iter(display_groups)),
```

Place it near `"reason_notes"` so exact test dictionaries are easy to read.

Add these helpers before `_benchmark_test_fallback_diagnostics()`:

```python
def _fallback_display_group_counts(rows: Sequence[BenchmarkTestRow]) -> dict[FallbackDisplayGroup, int]:
    counts = _empty_fallback_display_group_counts()
    for row in rows:
        counts[_fallback_display_group_for_test_row(row)] += 1
    return counts


def _generic_fallback_test_rows(rows: Sequence[BenchmarkTestRow]) -> list[BenchmarkTestRow]:
    return [
        row
        for row in rows
        if _is_generic_fallback_display_group(_fallback_display_group_for_test_row(row))
    ]


def _visible_fallback_rollups_for_terminal(
    rollups: Sequence[BenchmarkTestFallbackRollup],
) -> list[BenchmarkTestFallbackRollup]:
    return [
        rollup
        for rollup in rollups
        if not _is_generic_fallback_display_group(rollup["display_group"])
    ]
```

Update `_benchmark_test_fallback_diagnostics()` to compute rollups once and include the new fields:

```python
def _benchmark_test_fallback_diagnostics(
    rows: list[BenchmarkTestTriageRow],
) -> BenchmarkTestTriageFallbackDiagnostics:
    rollups = _benchmark_test_fallback_rollups(rows)
    visible_rollups = _visible_fallback_rollups_for_terminal(rollups)
    generic_rows = _generic_fallback_test_rows(rows)
    generic_benchmarks = Counter(row["benchmark_id"] for row in generic_rows)
    generic_reasons = Counter(
        reason
        for row in generic_rows
        for reason in row["reason_notes"]
        if reason.startswith("fallback:") or reason.startswith("selected:")
    )
    return {
        "top_benchmarks": _top_triage_benchmark_counts(rows),
        "top_facets": _top_triage_facet_counts(rows),
        "readiness_counts": _benchmark_test_readiness_counts(rows),
        "dataset_class_counts": _benchmark_test_dataset_class_counts(rows),
        "task_support_counts": _benchmark_test_task_support_counts(rows),
        "top_benchmarks_by_readiness": _top_triage_benchmark_counts_by_readiness(rows),
        "top_benchmarks_by_dataset_class": _top_triage_benchmark_counts_by_dataset_class(rows),
        "display_group_counts": _fallback_display_group_counts(rows),
        "hidden_generic_fallback_rows": len(generic_rows),
        "shown_fallback_rows": sum(rollup["count"] for rollup in visible_rollups),
        "top_generic_fallback_benchmarks": _top_benchmark_counts(generic_benchmarks),
        "top_generic_fallback_reasons": _top_reason_counts(generic_reasons),
        "terminal_visible_rollup_count": len(visible_rollups),
        "terminal_hidden_rollup_count": len(rollups) - len(visible_rollups),
        "rollups": rollups,
    }
```

- [ ] **Step 6: Update exact rollup assertions elsewhere**

Search for exact expected rollup dictionaries:

```bash
rg -n "\"reason_notes\": \\[|rollups\\[0\\] ==|rollups\\[1\\]" science/tests/test_benchmark_opportunities.py
```

For every exact expected `BenchmarkTestFallbackRollup`, add the expected `display_group`:

- supported generic fallback rollups: `"generic-baseline-fallback"`;
- blocked support fallback rollups restored via `include_blocked_fallback=True`: `"blocked-support-fallback"`;
- any non-generic fallback row with `context_fit != "generic-fallback"`: `"specific-fallback"`.

- [ ] **Step 7: Run tests to verify they pass**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_diagnostics_roll_up_visible_fallback_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_include_blocked_fallback_restores_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_exclude_fallback_prevents_suppression -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat: add triage fallback display diagnostics"
```

## Task 4: Collapse Generic Fallback In CLI Tables

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Update gap table test expectations**

Replace `test_benchmark_gaps_cli_table_shows_candidate_mode_and_compacts_fallbacks()` with:

```python
def test_benchmark_gaps_cli_table_collapses_generic_fallback_candidates(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-generic",
        """
id: hypothesis:0004-generic
type: hypothesis
title: Generic fallback benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    for slug in ("generic-a", "generic-b", "generic-c"):
        _write_dataset(
            tmp_path,
            slug,
            f"""
id: dataset:{slug}
type: dataset
title: {slug}
benchmark:
  domains: [biology]
  modalities: [assay]
  signal_types: [unrelated]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
        )

    result = _invoke_gaps(tmp_path)

    assert result.exit_code == 0
    assert "fallback-only" in result.output
    assert "generic fallback: 3 candidates" in result.output
    assert "Collapsed 3 generic fallback candidates" in result.output
    assert "dataset:generic-a [" not in result.output
    assert "+2 fallback" not in result.output
```

Add this JSON test after it:

```python
def test_benchmark_gaps_cli_json_keeps_raw_generic_fallback_candidates(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0005-generic-json",
        """
id: hypothesis:0005-generic-json
type: hypothesis
title: Generic fallback benchmark gap JSON
""",
        body="Homeostatic recovery remains under-tested.",
    )
    for slug in ("generic-json-a", "generic-json-b"):
        _write_dataset(
            tmp_path,
            slug,
            f"""
id: dataset:{slug}
type: dataset
title: {slug}
benchmark:
  domains: [biology]
  modalities: [assay]
  signal_types: [unrelated]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
        )

    result = _invoke_gaps(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    candidates = payload["benchmark_gaps"][0]["candidate_benchmarks"]
    assert len(candidates) == 2
    assert {candidate["benchmark_id"] for candidate in candidates} == {
        "dataset:generic-json-a",
        "dataset:generic-json-b",
    }
    assert payload["fallback_diagnostics"]["generic_fallback_candidate_rows"] == 2
```

- [ ] **Step 2: Add triage table tests**

In `test_benchmark_test_triage_cli_table_output_shows_fallback_rollups()`, change the assertions to expect generic fallback summary instead of detailed fallback table:

```python
    assert "Benchmark Test Triage: fallback-diagnostic" not in result.output
    assert "Benchmark Test Triage: generic fallback summary" in result.output
    assert "1 generic fallback rows hidden from detailed table" in result.output
    assert "dataset:visible-fallback:1" in result.output
    assert "ready (protein-lineage-association)" not in result.output
    assert "hypothesis:0306-generic" not in result.output
```

Remove the old assertions from that test that require the fallback detail table, task label, support, readiness, dataset class, facets, or example entity to appear.

Update the monkeypatched `rollups` in `test_benchmark_test_triage_cli_table_output_shows_hidden_fallback_rollup_count()` to include `"display_group": "specific-fallback"` in every rollup dict. This keeps that test focused on the existing visible-rollup cap behavior.

In `test_benchmark_test_triage_cli_errors_when_fallback_rollups_missing()`, update the fake `fallback_diagnostics` payload to include a nonzero terminal-visible count:

```python
            "fallback_diagnostics": {"rollups": [], "terminal_visible_rollup_count": 1},
```

This keeps the test focused on the error case where the report says there should be a visible fallback rollup but the rollup list is empty.

Add a new test after it:

```python
def test_benchmark_test_triage_cli_table_hides_generic_but_keeps_json_rollups(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0307-generic-json",
        """
id: hypothesis:0307-generic-json
type: hypothesis
title: Generic fallback JSON hypothesis
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "generic-json-rollup",
        """
id: dataset:generic-json-rollup
type: dataset
title: Generic JSON Rollup
dataset_class: deposit
local_path: data/generic-json-rollup
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      task_type: protein-lineage-association
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
      support:
        state: supported
        checked_at: '2026-07-03'
""",
    )

    table_result = _invoke_test_triage(tmp_path, "--source", "gap-fallback")
    json_result = _invoke_test_triage(tmp_path, "--source", "gap-fallback", "--format", "json")

    assert table_result.exit_code == 0
    assert "Benchmark Test Triage: fallback-diagnostic" not in table_result.output
    assert "Benchmark Test Triage: generic fallback summary" in table_result.output
    payload = json.loads(json_result.output)
    assert payload["fallback_diagnostics"]["rollups"][0]["benchmark_id"] == "dataset:generic-json-rollup"
    assert payload["fallback_diagnostics"]["rollups"][0]["display_group"] == "generic-baseline-fallback"
    assert payload["buckets"]["fallback-diagnostic"][0]["benchmark_id"] == "dataset:generic-json-rollup"
```

- [ ] **Step 3: Run CLI tests to verify they fail**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_table_collapses_generic_fallback_candidates \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_json_keeps_raw_generic_fallback_candidates \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_fallback_rollups \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_hides_generic_but_keeps_json_rollups -q
```

Expected: FAIL because CLI still renders generic fallback ids/rollups in detail.

- [ ] **Step 4: Implement gap table formatting**

Replace `_format_gap_candidates_for_table()` with:

```python
def _format_gap_candidates_for_table(row: Mapping[str, Any]) -> str:
    candidates = row["candidate_benchmarks"]
    if not candidates:
        return "-"
    if row.get("candidate_mode") != "fallback-only":
        return ", ".join(_format_gap_candidate_for_table(candidate) for candidate in candidates)

    from science_tool.benchmark_opportunities import (
        _fallback_display_group_for_gap_candidate,
        _is_generic_fallback_display_group,
    )

    groups = [_fallback_display_group_for_gap_candidate(candidate) for candidate in candidates]
    generic = [_is_generic_fallback_display_group(group) for group in groups]
    if any(generic) and not all(generic):
        benchmark_ids = ", ".join(candidate["benchmark_id"] for candidate in candidates)
        raise click.ClickException(f"mixed generic and specific fallback candidates in one gap row: {benchmark_ids}")
    if all(generic):
        top = candidates[0]["benchmark_id"]
        return f"generic fallback: {len(candidates)} candidates (top: {top})"
    return ", ".join(_format_gap_candidate_for_table(candidate) for candidate in candidates)
```

In `benchmark_gaps()`, after rendering the gap table and before the calibration summary block, add:

```python
    generic_fallback_rows = payload["fallback_diagnostics"]["generic_fallback_candidate_rows"]
    if generic_fallback_rows:
        click.echo(
            f"Collapsed {generic_fallback_rows} generic fallback candidates; "
            "use --calibration-summary or --format json for diagnostics."
        )
```

This line should run only in table mode because the JSON branch returns earlier.

- [ ] **Step 5: Implement triage table filtering**

In `benchmark_test_triage()` table rendering, replace the current fallback-detail block from:

```python
    fallback_count = payload["summary"]["bucket_counts"]["fallback-diagnostic"]
    if fallback_count:
        diagnostics = payload["fallback_diagnostics"]
        rollups = diagnostics["rollups"]
        visible_rollups = rollups[:10]
        if not visible_rollups:
            raise click.ClickException("fallback diagnostics rollups missing for fallback rows")
        table = Table(title="Benchmark Test Triage: fallback-diagnostic", show_header=True, header_style="bold")
        for col in ("rows", "benchmark", "task", "support", "readiness", "class", "facets", "examples"):
            table.add_column(col, overflow="fold", no_wrap=False)
        row_label = f"{fallback_count} fallback rows grouped into {len(rollups)} rollups"
        if len(visible_rollups) < len(rollups):
            hidden_rollups = len(rollups) - len(visible_rollups)
            row_label = f"{row_label} (showing {len(visible_rollups)}, {hidden_rollups} hidden)"
        for index, rollup in enumerate(visible_rollups):
            table.add_row(
                row_label if index == 0 else "",
                str(rollup.get("benchmark_id") or "-"),
                _format_test_triage_rollup_task(rollup),
                _format_test_triage_rollup_support(rollup),
                str(rollup.get("readiness_label") or "-"),
                str(rollup.get("dataset_class") or "-"),
                _format_test_triage_rollup_facets(rollup),
                _format_test_triage_rollup_examples(rollup),
            )
        Console(width=200).print(table)
        visible_rows += len(visible_rollups)
```

to:

```python
    fallback_count = payload["summary"]["bucket_counts"]["fallback-diagnostic"]
    if fallback_count:
        diagnostics = payload["fallback_diagnostics"]
        rollups = diagnostics["rollups"]
        visible_rollups = [
            rollup for rollup in rollups if not str(rollup.get("display_group", "")).startswith("generic-")
        ][:10]
        terminal_visible_total = diagnostics.get("terminal_visible_rollup_count", len(rollups))
        if terminal_visible_total > 0 and not visible_rollups:
            raise click.ClickException("fallback diagnostics rollups missing for fallback rows")
        if visible_rollups:
            table = Table(title="Benchmark Test Triage: fallback-diagnostic", show_header=True, header_style="bold")
            for col in ("rows", "benchmark", "task", "support", "readiness", "class", "facets", "examples"):
                table.add_column(col, overflow="fold", no_wrap=False)
            row_label = f"{fallback_count} fallback rows grouped into {len(rollups)} rollups"
            if terminal_visible_total > len(visible_rollups):
                hidden_rollups = terminal_visible_total - len(visible_rollups)
                row_label = f"{row_label} (showing {len(visible_rollups)}, {hidden_rollups} hidden)"
            for index, rollup in enumerate(visible_rollups):
                table.add_row(
                    row_label if index == 0 else "",
                    str(rollup.get("benchmark_id") or "-"),
                    _format_test_triage_rollup_task(rollup),
                    _format_test_triage_rollup_support(rollup),
                    str(rollup.get("readiness_label") or "-"),
                    str(rollup.get("dataset_class") or "-"),
                    _format_test_triage_rollup_facets(rollup),
                    _format_test_triage_rollup_examples(rollup),
                )
            Console(width=200).print(table)
            visible_rows += len(visible_rollups)
```

With this block, a nonzero `fallback_count` with zero terminal-visible rollups skips the detailed fallback table instead of raising; the generic summary table added below accounts for the hidden rows.

Add a generic summary table after the fallback detail block and before suppressed blocked fallback:

```python
    hidden_generic = payload["fallback_diagnostics"].get("hidden_generic_fallback_rows", 0)
    if hidden_generic:
        diagnostics = payload["fallback_diagnostics"]
        table = Table(
            title="Benchmark Test Triage: generic fallback summary",
            show_header=True,
            header_style="bold",
        )
        for col in ("rows", "top benchmarks", "top reasons"):
            table.add_column(col, overflow="fold", no_wrap=False)
        table.add_row(
            f"{hidden_generic} generic fallback rows hidden from detailed table",
            _format_count_rows(diagnostics.get("top_generic_fallback_benchmarks", []), key="benchmark_id"),
            _format_count_rows(diagnostics.get("top_generic_fallback_reasons", []), key="reason"),
        )
        Console(width=200).print(table)
        visible_rows += 1
```

- [ ] **Step 6: Run CLI tests to verify they pass**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_table_collapses_generic_fallback_candidates \
  science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_json_keeps_raw_generic_fallback_candidates \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_fallback_rollups \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_hidden_fallback_rollup_count \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_hides_generic_but_keeps_json_rollups \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_errors_when_fallback_rollups_missing -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat: collapse generic benchmark fallback tables"
```

## Task 5: Preserve Review Artifacts And Full JSON Diagnostics

**Files:**
- Modify: `science/tests/test_benchmark_cli.py`
- Modify if needed: `science/src/science_tool/cli.py`

- [ ] **Step 1: Update review-file test for complete rollups**

In `test_benchmark_test_triage_review_file_includes_visible_fallback_rollups()`, add assertions that the review file keeps generic fallback rollups:

```python
    assert rollups[0]["display_group"] == "generic-baseline-fallback"
    assert written["fallback_diagnostics"]["hidden_generic_fallback_rows"] == 1
    assert written["fallback_diagnostics"]["terminal_hidden_rollup_count"] == 1
```

If the fixture writes more than one generic row, use the actual expected counts from the test fixture.

- [ ] **Step 2: Update suppression review-file test**

In `test_benchmark_test_triage_review_file_includes_suppression_diagnostics()`, keep:

```python
    assert written["fallback_diagnostics"]["rollups"] == []
```

Add:

```python
    assert written["fallback_diagnostics"]["display_group_counts"] == {
        "specific-fallback": 0,
        "blocked-support-fallback": 0,
        "generic-baseline-fallback": 0,
        "generic-task-ready-fallback": 0,
        "generic-available-fallback": 0,
    }
    assert written["fallback_diagnostics"]["hidden_generic_fallback_rows"] == 0
```

- [ ] **Step 3: Run review-file tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_review_file_includes_visible_fallback_rollups \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_review_file_includes_suppression_diagnostics \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_writes_default_review_file -q
```

Expected: PASS. If this fails because the YAML writer drops the new diagnostics, update `_write_benchmark_test_triage_review_file()` so it writes `payload["fallback_diagnostics"]` unchanged. It should already do this.

- [ ] **Step 4: Commit**

Run:

```bash
rtk git add science/tests/test_benchmark_cli.py science/src/science_tool/cli.py
rtk git commit -m "test: preserve fallback diagnostics in triage review artifacts"
```

If `science/src/science_tool/cli.py` did not change in this task, omit it from `git add`.

## Task 6: Run Focused Suite And Real-Project Smoke

**Files:**
- No intended source changes.
- Possible doc note only if smoke output reveals a design mismatch.

- [ ] **Step 1: Run focused benchmark tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src \
  rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting check**

Run:

```bash
rtk git diff --check
```

Expected: no output, exit code `0`.

- [ ] **Step 3: Smoke `benchmark gaps` table on multiple myeloma**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science science benchmark gaps \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --context-fit generic-fallback \
  | sed -n '1,80p'
```

Expected:

- output includes `generic fallback:` compact candidate text;
- output includes `Collapsed 3 generic fallback candidates` or the project-specific generic fallback count;
- output does not print long lists of individual generic fallback candidate ids in each row.

- [ ] **Step 4: Smoke `benchmark test-triage` table on multiple myeloma**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science science benchmark test-triage \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --source gap-fallback \
  | sed -n '1,120p'
```

Expected:

- output includes `Benchmark Test Triage: generic fallback summary`;
- output includes `generic fallback rows hidden from detailed table`;
- detailed fallback rollup table is absent or limited to non-generic fallback rollups.

- [ ] **Step 5: Smoke JSON raw preservation**

Run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science science benchmark test-triage \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --source gap-fallback \
  --format json > /tmp/benchmark-fallback-actionability-triage.json
```

Then run:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("/tmp/benchmark-fallback-actionability-triage.json").read_text())
fallback_rows = payload["buckets"]["fallback-diagnostic"]
diagnostics = payload["fallback_diagnostics"]
assert "display_group_counts" in diagnostics
assert "hidden_generic_fallback_rows" in diagnostics
assert diagnostics["rollups"] or not fallback_rows
print(
    "fallback_rows=",
    len(fallback_rows),
    "hidden_generic=",
    diagnostics["hidden_generic_fallback_rows"],
    "rollups=",
    len(diagnostics["rollups"]),
)
PY
```

Expected: prints counts and exits `0`.

If shell heredoc execution is inconvenient in the execution environment, use this equivalent single-line check:

```bash
PYTHONPATH=science/src:science/model/src rtk uv run --frozen --project science python -c 'import json; from pathlib import Path; payload=json.loads(Path("/tmp/benchmark-fallback-actionability-triage.json").read_text()); fallback_rows=payload["buckets"]["fallback-diagnostic"]; diagnostics=payload["fallback_diagnostics"]; assert "display_group_counts" in diagnostics; assert "hidden_generic_fallback_rows" in diagnostics; assert diagnostics["rollups"] or not fallback_rows; print("fallback_rows=", len(fallback_rows), "hidden_generic=", diagnostics["hidden_generic_fallback_rows"], "rollups=", len(diagnostics["rollups"]))'
```

- [ ] **Step 6: Commit any final test-only or doc corrections**

If smoke reveals no source changes, do not commit.

If a source/test correction was needed, run the focused suite again, then:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
rtk git commit -m "fix: finalize benchmark fallback diagnostics"
```

## Final Verification Before Handoff

- [ ] Run:

```bash
rtk git status --short
```

Expected: clean worktree.

- [ ] Run:

```bash
rtk git log --oneline --max-count=6
```

Expected: shows the design commit, plan commit, and task commits on `benchmark-fallback-actionability-tuning-design`.

- [ ] Summarize:

- which tests passed;
- whether real-project smoke passed;
- any behavior intentionally left for a later slice, especially `--include-generic-fallback-detail`.

# Benchmark Test Triage Fallback Rollups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add grouped fallback rollups to `science benchmark test-triage` diagnostics and render those rollups in the default table output while preserving existing per-entity fallback rows.

**Architecture:** Keep `benchmark_tests_report()` and triage bucket assignment unchanged. Add a pure rollup projection inside `_benchmark_test_fallback_diagnostics()` over the already-filtered visible `fallback-diagnostic` bucket, then update the CLI to render that projection instead of the old one-row aggregate table. Existing JSON fields and review artifacts remain intact; `fallback_diagnostics.rollups` is additive and always present.

**Tech Stack:** Python 3.11+, Click/Rich CLI, pytest, TypedDict-based report contracts.

---

## Worktree And Test Command Notes

This plan was drafted in the isolated worktree:

```bash
/mnt/ssd/Dropbox/science/.worktrees/benchmark-test-triage-fallback-rollups-plan
```

When executing this plan in a worktree, run tests with an explicit source path so the editable install cannot resolve `science_tool` from the main checkout:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest ...
```

Before implementation, confirm import resolution from the worktree:

```bash
PYTHONPATH=science/src:science/model/src python -c "import science_tool, pathlib; print(pathlib.Path(science_tool.__file__).resolve())"
```

Expected: the printed path starts with the worktree path and ends in `science/src/science_tool/__init__.py`.

## Files

- Modify: `science/src/science_tool/benchmark_opportunities.py`
  - Add the `BenchmarkTestFallbackRollup` TypedDict.
  - Add required `rollups` to `BenchmarkTestTriageFallbackDiagnostics`.
  - Add fallback rollup grouping, invariant checks, sorting, and count partition helpers.
  - Include rollups in `_benchmark_test_fallback_diagnostics()`.
- Modify: `science/src/science_tool/cli.py`
  - Replace the fallback-diagnostic aggregate table with a rollup table.
  - Keep suppressed blocked fallback diagnostics rendering unchanged.
- Modify: `science/tests/test_benchmark_opportunities.py`
  - Add report-level rollup tests and update existing diagnostics assertions for the new required `rollups` key.
- Modify: `science/tests/test_benchmark_cli.py`
  - Update default table assertions.
  - Add review-file assertion for `fallback_diagnostics.rollups`.

---

### Task 1: Add Report-Level Fallback Rollups

**Files:**
- Modify: `science/tests/test_benchmark_opportunities.py`
- Modify: `science/src/science_tool/benchmark_opportunities.py`

- [ ] **Step 1: Add failing report tests for rollups**

In `science/tests/test_benchmark_opportunities.py`, insert these tests after `test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics`:

```python
def test_benchmark_test_triage_fallback_diagnostics_roll_up_visible_fallback_rows(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    for slug, title, body in (
        ("0106-generic-a", "Generic fallback A", "Homeostatic recovery remains under-tested."),
        ("0107-generic-b", "Generic fallback B", "Adaptive recovery remains under-tested."),
    ):
        _write_entity(
            tmp_path,
            "hypotheses",
            slug,
            f"""
id: hypothesis:{slug}
type: hypothesis
title: {title}
""",
            body=body,
        )
    _write_dataset(
        tmp_path,
        "supported-fallback-rollup",
        """
id: dataset:supported-fallback-rollup
type: dataset
title: Supported Fallback Rollup
dataset_class: deposit
local_path: data/supported-fallback-rollup
benchmark:
  domains: [biology]
  modalities: [proteomics, multimodal]
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

    payload = benchmark_test_triage_report(tmp_path, source="gap-fallback")

    fallback_rows = payload["buckets"]["fallback-diagnostic"]
    rollups = payload["fallback_diagnostics"]["rollups"]
    assert len(fallback_rows) == 2
    assert len(rollups) == 1
    assert sum(rollup["count"] for rollup in rollups) == payload["summary"]["bucket_counts"]["fallback-diagnostic"]
    assert rollups[0] == {
        "benchmark_id": "dataset:supported-fallback-rollup",
        "benchmark_title": "Supported Fallback Rollup",
        "task_id": "dataset:supported-fallback-rollup#ready",
        "task_type": "protein-lineage-association",
        "count": 2,
        "task_support_state": "supported",
        "task_support_reason": "",
        "readiness_label": "runnable",
        "dataset_class": "deposit",
        "test_plan_state": "concrete",
        "top_facets": [
            {"facet": "proteomics", "count": 2},
            {"facet": "multimodal", "count": 2},
            {"facet": "time-series", "count": 2},
        ],
        "example_entities": [
            "hypothesis:0106-generic-a",
            "hypothesis:0107-generic-b",
        ],
        "reason_notes": ["fallback:high-baseline"],
    }


def test_benchmark_test_triage_fallback_rollups_sort_and_cap_examples(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    for index in range(4):
        _write_entity(
            tmp_path,
            "hypotheses",
            f"0110-generic-{index}",
            f"""
id: hypothesis:0110-generic-{index}
type: hypothesis
title: Generic fallback {index}
""",
            body=f"Recovery pattern {index} remains under-tested.",
        )
    _write_dataset(
        tmp_path,
        "fallback-small",
        """
id: dataset:fallback-small
type: dataset
title: Fallback Small
dataset_class: reference
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
      support:
        state: candidate
        reason: requires-study-specific-staging
        checked_at: '2026-07-03'
""",
    )
    _write_dataset(
        tmp_path,
        "fallback-large",
        """
id: dataset:fallback-large
type: dataset
title: Fallback Large
dataset_class: deposit
local_path: data/fallback-large
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
      support:
        state: supported
        checked_at: '2026-07-03'
""",
    )

    payload = benchmark_test_triage_report(tmp_path, source="gap-fallback")

    rollups = payload["fallback_diagnostics"]["rollups"]
    assert [rollup["benchmark_id"] for rollup in rollups] == [
        "dataset:fallback-large",
        "dataset:fallback-small",
    ]
    assert rollups[0]["count"] == 4
    assert rollups[0]["example_entities"] == [
        "hypothesis:0110-generic-0",
        "hypothesis:0110-generic-1",
        "hypothesis:0110-generic-2",
    ]
    assert rollups[1]["task_support_state"] == "candidate"
    assert rollups[1]["task_support_reason"] == "requires-study-specific-staging"
    assert rollups[1]["readiness_label"] == "metadata-only"
    assert rollups[1]["dataset_class"] == "reference"


def test_benchmark_test_fallback_rollups_raise_on_inconsistent_support_reason() -> None:
    from science_tool.benchmark_opportunities import _benchmark_test_fallback_rollups

    base = {
        "benchmark_id": "dataset:drift",
        "benchmark_title": "Drift",
        "task_id": "dataset:drift#ready",
        "task_type": "protein-lineage-association",
        "task_support_state": "candidate",
        "readiness_label": "runnable",
        "dataset_class": "deposit",
        "test_plan_state": "concrete",
        "matched_facets": ["proteomics"],
        "reason_notes": ["fallback:high-baseline"],
    }
    rows = [
        {**base, "entity_id": "hypothesis:a", "task_support_reason": "reason-one"},
        {**base, "entity_id": "hypothesis:b", "task_support_reason": "reason-two"},
    ]

    with pytest.raises(ValueError, match="inconsistent task support reasons"):
        _benchmark_test_fallback_rollups(cast("list[Any]", rows))
```

This test exercises the design's fail-loud-against-metadata-drift contract directly.
Because the grouping key makes conflicting reasons unreachable through the public
report API, the private helper is called with hand-crafted rows that share a group
key but disagree on `task_support_reason`.

- [ ] **Step 2: Run report tests and verify they fail for the missing field**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_diagnostics_roll_up_visible_fallback_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_rollups_sort_and_cap_examples \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_fallback_rollups_raise_on_inconsistent_support_reason \
  -q
```

Expected: FAIL. The two report tests fail with `KeyError: 'rollups'`; the invariant
test fails with `ImportError`/`AttributeError` because `_benchmark_test_fallback_rollups`
does not exist yet.

- [ ] **Step 3: Add rollup report types**

In `science/src/science_tool/benchmark_opportunities.py`, add this TypedDict after `BenchmarkTestSuppressedBlockedSupportDiagnostics`:

```python
class BenchmarkTestFallbackRollup(TypedDict):
    benchmark_id: str
    benchmark_title: str
    task_id: str | None
    task_type: str
    count: int
    task_support_state: BenchmarkTaskSupportState | None
    task_support_reason: str
    readiness_label: ReadinessLabel
    dataset_class: DatasetClass
    test_plan_state: TestPlanState
    top_facets: list[FacetCountRow]
    example_entities: list[str]
    reason_notes: list[str]
```

Then add `rollups` as a required key in `BenchmarkTestTriageFallbackDiagnostics`:

```python
class BenchmarkTestTriageFallbackDiagnostics(TypedDict):
    top_benchmarks: list[BenchmarkCountRow]
    top_facets: list[FacetCountRow]
    readiness_counts: dict[ReadinessLabel, int]
    dataset_class_counts: dict[DatasetClass, int]
    task_support_counts: dict[TaskSupportCountKey, int]
    top_benchmarks_by_readiness: dict[ReadinessLabel, list[BenchmarkCountRow]]
    top_benchmarks_by_dataset_class: dict[DatasetClass, list[BenchmarkCountRow]]
    rollups: list[BenchmarkTestFallbackRollup]
    suppressed_blocked_support: NotRequired[BenchmarkTestSuppressedBlockedSupportDiagnostics]
```

- [ ] **Step 4: Add rollup helpers**

In `science/src/science_tool/benchmark_opportunities.py`, update the imports:

```python
from collections.abc import Callable, Mapping, Sequence
```

In `science/src/science_tool/benchmark_opportunities.py`, add these helpers after `_top_triage_benchmark_counts_by_dataset_class` and before `_benchmark_test_fallback_diagnostics`:

```python
_TASK_SUPPORT_ROLLUP_ORDER: dict[BenchmarkTaskSupportState | None, int] = {
    "supported": 0,
    "candidate": 1,
    "blocked": 2,
    None: 3,
}


def _benchmark_test_fallback_rollup_sort_key(
    rollup: BenchmarkTestFallbackRollup,
) -> tuple[int, str, str, int, int, int, int]:
    return (
        -rollup["count"],
        rollup["benchmark_id"],
        rollup["task_id"] or "",
        _TASK_SUPPORT_ROLLUP_ORDER[rollup["task_support_state"]],
        READINESS_LABELS.index(rollup["readiness_label"]),
        DATASET_CLASSES.index(rollup["dataset_class"]),
        ("concrete", "draft-needed").index(rollup["test_plan_state"]),
    )


def _distinct_row_strings(
    rows: Sequence[BenchmarkTestTriageRow],
    value: Callable[[BenchmarkTestTriageRow], str],
) -> set[str]:
    return {item for row in rows if (item := value(row))}


def _benchmark_test_fallback_rollups(
    rows: list[BenchmarkTestTriageRow],
    *,
    examples: int = 3,
) -> list[BenchmarkTestFallbackRollup]:
    grouped: dict[
        tuple[
            str,
            str | None,
            BenchmarkTaskSupportState | None,
            ReadinessLabel,
            DatasetClass,
            TestPlanState,
        ],
        list[BenchmarkTestTriageRow],
    ] = {}
    for row in rows:
        key = (
            row["benchmark_id"],
            row["task_id"],
            row["task_support_state"],
            row["readiness_label"],
            row["dataset_class"],
            row["test_plan_state"],
        )
        grouped.setdefault(key, []).append(row)

    rollups: list[BenchmarkTestFallbackRollup] = []
    for (
        benchmark_id,
        task_id,
        task_support_state,
        readiness_label,
        dataset_class,
        test_plan_state,
    ), group_rows in grouped.items():
        benchmark_titles = _distinct_row_strings(group_rows, lambda row: row["benchmark_title"])
        if len(benchmark_titles) != 1:
            raise ValueError(f"fallback rollup has inconsistent benchmark titles for {benchmark_id}")
        task_types = _distinct_row_strings(group_rows, lambda row: row["task_type"])
        if len(task_types) > 1:
            raise ValueError(f"fallback rollup has inconsistent task types for {benchmark_id}#{task_id or ''}")
        support_reasons = _distinct_row_strings(group_rows, lambda row: row["task_support_reason"])
        if len(support_reasons) > 1:
            raise ValueError(f"fallback rollup has inconsistent task support reasons for {benchmark_id}#{task_id or ''}")

        example_entities: list[str] = []
        for row in group_rows:
            if row["entity_id"] not in example_entities:
                example_entities.append(row["entity_id"])
            if len(example_entities) == examples:
                break

        reason_notes = sorted(
            {note for row in group_rows for note in row["reason_notes"]},
            key=_reason_note_sort_key,
        )
        rollups.append(
            {
                "benchmark_id": benchmark_id,
                "benchmark_title": next(iter(benchmark_titles)),
                "task_id": task_id,
                "task_type": next(iter(task_types)) if task_types else "",
                "count": len(group_rows),
                "task_support_state": task_support_state,
                "task_support_reason": next(iter(support_reasons)) if support_reasons else "",
                "readiness_label": readiness_label,
                "dataset_class": dataset_class,
                "test_plan_state": test_plan_state,
                "top_facets": _top_triage_facet_counts(group_rows),
                "example_entities": example_entities,
                "reason_notes": reason_notes,
            }
        )

    return sorted(rollups, key=_benchmark_test_fallback_rollup_sort_key)
```

- [ ] **Step 5: Include rollups in diagnostics**

Update `_benchmark_test_fallback_diagnostics()`:

```python
def _benchmark_test_fallback_diagnostics(
    rows: list[BenchmarkTestTriageRow],
) -> BenchmarkTestTriageFallbackDiagnostics:
    return {
        "top_benchmarks": _top_triage_benchmark_counts(rows),
        "top_facets": _top_triage_facet_counts(rows),
        "readiness_counts": _benchmark_test_readiness_counts(rows),
        "dataset_class_counts": _benchmark_test_dataset_class_counts(rows),
        "task_support_counts": _benchmark_test_task_support_counts(rows),
        "top_benchmarks_by_readiness": _top_triage_benchmark_counts_by_readiness(rows),
        "top_benchmarks_by_dataset_class": _top_triage_benchmark_counts_by_dataset_class(rows),
        "rollups": _benchmark_test_fallback_rollups(rows),
    }
```

- [ ] **Step 6: Update existing empty diagnostics assertions**

In `science/tests/test_benchmark_opportunities.py`, update the empty fallback diagnostics assertion in `test_benchmark_test_triage_report_exclude_fallback_prevents_suppression` by adding:

```python
    assert payload["fallback_diagnostics"]["rollups"] == []
```

In `science/tests/test_benchmark_cli.py`, update the exact `written["fallback_diagnostics"] == {...}` assertion in `test_benchmark_test_triage_cli_writes_default_review_file` to include:

```python
        "rollups": [],
```

- [ ] **Step 7: Run report tests and verify they pass**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_diagnostics_roll_up_visible_fallback_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_rollups_sort_and_cap_examples \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_fallback_rollups_raise_on_inconsistent_support_reason \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_exclude_fallback_prevents_suppression \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_writes_default_review_file \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
git commit -m "feat: add benchmark fallback rollups"
```

---

### Task 2: Preserve Suppression And Exclusion Semantics

**Files:**
- Modify: `science/tests/test_benchmark_opportunities.py`
- Modify: `science/src/science_tool/benchmark_opportunities.py`

- [ ] **Step 1: Add regression assertions for suppressed and included blocked fallback rows**

In `science/tests/test_benchmark_opportunities.py`, update `test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default` with these assertions after `payload["fallback_diagnostics"]["suppressed_blocked_support"] == {...}`:

```python
    assert payload["fallback_diagnostics"]["rollups"] == [
        {
            "benchmark_id": "dataset:mmrf-like",
            "benchmark_title": "MMRF Like",
            "task_id": "dataset:mmrf-like#overall-survival",
            "task_type": "",
            "count": 1,
            "task_support_state": None,
            "task_support_reason": "",
            "readiness_label": "runnable",
            "dataset_class": "deposit",
            "test_plan_state": "concrete",
            "top_facets": [
                {"facet": "clinical", "count": 1},
                {"facet": "time-to-event", "count": 1},
            ],
            "example_entities": ["hypothesis:0103-generic"],
            "reason_notes": ["fallback:high-baseline"],
        }
    ]
    assert all(
        rollup["task_support_state"] != "blocked"
        for rollup in payload["fallback_diagnostics"]["rollups"]
    )
```

Update `test_benchmark_test_triage_report_include_blocked_fallback_restores_rows` with these assertions:

```python
    assert payload["fallback_diagnostics"]["rollups"] == [
        {
            "benchmark_id": "dataset:blocked-fallback",
            "benchmark_title": "Blocked Fallback",
            "task_id": "dataset:blocked-fallback#progression-risk",
            "task_type": "",
            "count": 1,
            "task_support_state": "blocked",
            "task_support_reason": "open-metadata-missing-progression-endpoint",
            "readiness_label": "blocked",
            "dataset_class": "deposit",
            "test_plan_state": "concrete",
            "top_facets": [
                {"facet": "clinical", "count": 1},
                {"facet": "time-to-event", "count": 1},
            ],
            "example_entities": ["hypothesis:0104-generic"],
            "reason_notes": [
                "fallback:high-baseline",
                "task-support:blocked:open-metadata-missing-progression-endpoint",
            ],
        }
    ]
```

Update `test_benchmark_test_triage_report_exclude_fallback_prevents_suppression` with this assertion if it was not already added in Task 1:

```python
    assert payload["fallback_diagnostics"]["rollups"] == []
```

- [ ] **Step 2: Run suppression-focused tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_include_blocked_fallback_restores_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_exclude_fallback_prevents_suppression \
  -q
```

Expected: PASS. The implementation from Task 1 should already satisfy these assertions because rollups are built from the visible `fallback-diagnostic` bucket.

- [ ] **Step 3: Commit Task 2**

```bash
git add science/tests/test_benchmark_opportunities.py
git commit -m "test: cover fallback rollup filtering"
```

---

### Task 3: Render Fallback Rollups In The CLI

**Files:**
- Modify: `science/tests/test_benchmark_cli.py`
- Modify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Update the CLI table test to expect rollup output**

In `science/tests/test_benchmark_cli.py`, replace `test_benchmark_test_triage_cli_table_output_shows_fallback_breakdowns` with:

```python
def test_benchmark_test_triage_cli_table_output_shows_fallback_rollups(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0306-generic",
        """
id: hypothesis:0306-generic
type: hypothesis
title: Generic fallback hypothesis
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "visible-fallback",
        """
id: dataset:visible-fallback
type: dataset
title: Visible Fallback
dataset_class: deposit
local_path: data/visible-fallback
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
      support:
        state: supported
        checked_at: '2026-07-03'
""",
    )

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback")

    assert result.exit_code == 0
    assert "Benchmark Test Triage: fallback-diagnostic" in result.output
    assert "1 fallback rows grouped into 1 rollups" in result.output
    assert "visible-fallback" in result.output
    assert "ready" in result.output
    assert "supported" in result.output
    assert "runnable" in result.output
    assert "deposit" in result.output
    assert "proteomics:1" in result.output
    assert "hypothesis:0306-generic" in result.output
    assert "top benchmarks" not in result.output
    assert "runnable:1" not in result.output
    assert "deposit:1" not in result.output
    assert "none:1" not in result.output
```

- [ ] **Step 2: Add CLI helper formatters for rollups**

In `science/src/science_tool/cli.py`, add these helpers near `_format_test_triage_task`, `_format_test_triage_needs`, and `_format_test_triage_facets`:

```python
def _format_test_triage_rollup_task(rollup: Mapping[str, Any]) -> str:
    task_id = rollup.get("task_id")
    if not task_id:
        return "-"
    task = str(task_id).split("#", 1)[-1]
    task_type = str(rollup.get("task_type") or "")
    return f"{task} ({task_type})" if task_type else task


def _format_test_triage_rollup_support(rollup: Mapping[str, Any]) -> str:
    state = str(rollup.get("task_support_state") or "none")
    reason = str(rollup.get("task_support_reason") or "")
    return f"{state}: {reason}" if reason else state


def _format_test_triage_rollup_facets(rollup: Mapping[str, Any]) -> str:
    return _format_count_rows(rollup.get("top_facets", []), key="facet")


def _format_test_triage_rollup_examples(rollup: Mapping[str, Any]) -> str:
    examples = [str(entity_id) for entity_id in rollup.get("example_entities", [])]
    return ", ".join(examples) if examples else "-"
```

- [ ] **Step 3: Replace the fallback aggregate table block**

In `science/src/science_tool/cli.py`, replace the current `fallback_count` block:

```python
    fallback_count = payload["summary"]["bucket_counts"]["fallback-diagnostic"]
    if fallback_count:
        diagnostics = payload["fallback_diagnostics"]
        table = Table(title="Benchmark Test Triage: fallback-diagnostic", show_header=True, header_style="bold")
        for col in ("rows", "top benchmarks", "top facets", "readiness", "class", "support"):
            table.add_column(col, overflow="fold", no_wrap=False)
        table.add_row(
            f"{fallback_count} fallback rows",
            _format_count_rows(diagnostics["top_benchmarks"], key="benchmark_id"),
            _format_count_rows(diagnostics["top_facets"], key="facet"),
            _format_count_map(diagnostics["readiness_counts"]),
            _format_count_map(diagnostics["dataset_class_counts"]),
            _format_count_map(diagnostics["task_support_counts"]),
        )
        Console(width=200).print(table)
        visible_rows += 1
```

with:

```python
    fallback_count = payload["summary"]["bucket_counts"]["fallback-diagnostic"]
    if fallback_count:
        diagnostics = payload["fallback_diagnostics"]
        rollups = diagnostics["rollups"]
        visible_rollups = rollups[:10]
        rollup_label = f"{fallback_count} fallback rows grouped into {len(rollups)} rollups"
        if len(rollups) > len(visible_rollups):
            rollup_label = f"{rollup_label} (showing {len(visible_rollups)})"
        table = Table(title="Benchmark Test Triage: fallback-diagnostic", show_header=True, header_style="bold")
        for col in ("rows", "benchmark", "task", "support", "readiness", "class", "facets", "examples"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for index, rollup in enumerate(visible_rollups):
            table.add_row(
                rollup_label if index == 0 else "",
                rollup["benchmark_id"],
                _format_test_triage_rollup_task(rollup),
                _format_test_triage_rollup_support(rollup),
                rollup["readiness_label"],
                rollup["dataset_class"],
                _format_test_triage_rollup_facets(rollup),
                _format_test_triage_rollup_examples(rollup),
            )
        Console(width=200).print(table)
        visible_rows += len(visible_rollups)
```

This keeps the existing suppressed blocked fallback table unchanged.

- [ ] **Step 4: Run the CLI table test**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_fallback_rollups \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
git commit -m "feat: render benchmark fallback rollups"
```

---

### Task 4: Verify Review Artifact And Full Focused Suite

**Files:**
- Modify: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add a review-file assertion for rollups**

In `science/tests/test_benchmark_cli.py`, update `test_benchmark_test_triage_cli_writes_default_review_file` by asserting the empty rollups key is present as described in Task 1.

Then update `test_benchmark_test_triage_review_file_includes_suppression_diagnostics` by adding this assertion after the existing `written["fallback_diagnostics"]["suppressed_blocked_support"] == {...}` assertion:

```python
    assert written["fallback_diagnostics"]["rollups"] == []
```

This pins the default behavior: blocked-support fallback rows suppressed from visible fallback diagnostics do not appear in rollups.

- [ ] **Step 2: Run the focused benchmark triage test set**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_bucket_assignment_is_ordered \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_buckets_and_preserves_summary_fields \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_diagnostics_roll_up_visible_fallback_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_rollups_sort_and_cap_examples \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_diagnostics_count_supported_task_support \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_include_blocked_fallback_restores_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_exclude_fallback_prevents_suppression \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_json_output \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_suppression_diagnostic \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_fallback_rollups \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_buckets \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_writes_default_review_file \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_review_file_includes_suppression_diagnostics \
  -q
```

Expected: PASS.

- [ ] **Step 3: Run static checks for touched files**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen ruff check \
  science/src/science_tool/benchmark_opportunities.py \
  science/src/science_tool/cli.py \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py
```

Expected: PASS.

- [ ] **Step 4: Run real-project smoke checks**

Run:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --frozen science benchmark test-triage \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --source gap-fallback
```

Expected:
- Table contains `Benchmark Test Triage: fallback-diagnostic`.
- Table title or first row includes a phrase like `fallback rows grouped into 3 rollups`.
- The rollup table shows `ccle-proteomics-nusinow-2020`, `cptac-proteogenomics`, and `dream4-in-silico-network`.

Run:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --frozen science benchmark test-triage \
  --project-root ~/d/natural-systems \
  --commons \
  --source gap-fallback
```

Expected:
- Table contains `Benchmark Test Triage: fallback-diagnostic`.
- Table reports grouped fallback rollups rather than the old `top benchmarks` aggregate columns.

- [ ] **Step 5: Commit Task 4**

```bash
git add science/tests/test_benchmark_cli.py
git commit -m "test: verify benchmark fallback rollup artifacts"
```

---

### Task 5: Final Verification

**Files:**
- No new source files.

- [ ] **Step 1: Run the full benchmark opportunity and CLI test files**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting checks**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen ruff format --check \
  science/src/science_tool/benchmark_opportunities.py \
  science/src/science_tool/cli.py \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py
```

Expected: PASS. If it fails, run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen ruff format \
  science/src/science_tool/benchmark_opportunities.py \
  science/src/science_tool/cli.py \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py
```

Then rerun the format check and commit the formatting changes with the source/test changes that introduced them.

- [ ] **Step 3: Inspect diff**

Run:

```bash
git diff --stat HEAD~4..HEAD
git diff HEAD~4..HEAD -- science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

Expected:
- No changes outside the four intended files.
- `fallback_diagnostics.rollups` is required in report JSON.
- Per-entity `buckets["fallback-diagnostic"]` rows are preserved.
- CLI fallback output now uses rollup columns.

- [ ] **Step 4: Request review before merging**

Use `superpowers:requesting-code-review` to request a review of the implementation before merging back to `main`.

---

## Self-Review

- Spec coverage: The plan adds the required `rollups` field, keeps existing fallback rows, preserves aggregate JSON diagnostics, renders rollups in the default table, accounts for suppressed blocked fallback rows, and verifies review YAML serialization.
- Deliberate deviation from the design doc: the `entity_count` rollup field is intentionally omitted. It was speculative (justified only by a hypothetical future multi-task row shape that cannot occur within a single fallback bucket today), and dropping it follows `Explicit > Defensive`. The design doc has been updated to match.
- Fail-loud coverage: the group-invariant `ValueError` branches (inconsistent `benchmark_title` / `task_type` / `task_support_reason`) are unreachable through the public report API, so a dedicated unit test calls `_benchmark_test_fallback_rollups` directly with a conflicting group to pin the design's drift-detection contract.
- Placeholder scan: No `TBD`, `TODO`, or open-ended implementation steps remain. Each task has concrete code snippets and commands.
- Type consistency: `BenchmarkTestFallbackRollup` fields match the design and the CLI reads the same field names. The sort order uses existing `READINESS_LABELS`, `DATASET_CLASSES`, and task support states.
- Test strategy: The tests cover grouping, count partitioning, field propagation, sorting, example capping, suppressed/default behavior, `--include-blocked-fallback`, `--exclude-fallback`, CLI table rendering, and review-file serialization.

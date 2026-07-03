# Benchmark Fallback Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science benchmark test-triage` explain visible fallback rows by readiness, dataset class, and task-support state without changing benchmark matching, scoring, or suppression behavior.

**Architecture:** Add `dataset_class` to the existing `BenchmarkTestRow` contract from the already-normalized `DatasetOpportunityContext.dataset.dataset_class`. Then compute additive fallback diagnostics from `buckets["fallback-diagnostic"]`, keeping suppressed blocked-support rows in their existing separate diagnostic block. The CLI remains a projection over the report payload and only adds compact aggregate columns to the fallback diagnostic table.

**Tech Stack:** Python 3.12, Click/Rich CLI, TypedDict report contracts, pytest via `PYTHONPATH=science/src:science/model/src uv run --frozen pytest`, ruff via `PYTHONPATH=science/src:science/model/src uv run --frozen ruff check`.

---

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Reuse the canonical `DatasetClass` type for benchmark-test rows.
  - Add `dataset_class` to `BenchmarkTestRow`.
  - Add fallback diagnostic helper functions for counts and grouped top benchmark rows.
  - Extend `BenchmarkTestTriageFallbackDiagnostics`.
- Modify `science/src/science_tool/cli.py`
  - Add `readiness`, `class`, and `support` columns to the fallback diagnostic aggregate table.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add report-level regression tests for row metadata and diagnostics.
  - Update existing fallback-diagnostic assertions to include the new stable fields.
- Modify `science/tests/test_benchmark_cli.py`
  - Update JSON review-file expectations for the additive fields.
  - Add table-output assertions for the new columns.

No schema migration, commons metadata edit, or new command is part of this plan.

---

### Task 0: Create Isolated Worktree

**Files:**
- No code files changed.

- [ ] **Step 1: Verify current checkout status**

Run:

```bash
git status --short
```

Expected: existing unrelated bio-identity files may be dirty. Do not stage or edit them:

```text
 M docs/plans/2026-07-03-benchmark-fallback-diagnostics-design.md
 M docs/plans/2026-07-03-bio-identity-p4-assembly-registry-design.md
?? docs/plans/2026-07-03-benchmark-fallback-diagnostics-implementation-plan.md
?? docs/plans/2026-07-03-bio-identity-p4-assembly-registry-implementation-plan.md
```

Treat the current fallback diagnostics design file as planning context unless explicitly asked to commit it.

- [ ] **Step 2: Create a feature worktree**

Run:

```bash
git worktree add .worktrees/benchmark-fallback-diagnostics -b benchmark-fallback-diagnostics HEAD
```

Expected: worktree created on a new branch.

- [ ] **Step 3: Enter the worktree**

Run:

```bash
cd .worktrees/benchmark-fallback-diagnostics
git status --short
```

Expected: clean worktree. If it is not clean, stop and inspect before continuing.

- [ ] **Step 4: Confirm imports resolve from the worktree**

Run from inside `.worktrees/benchmark-fallback-diagnostics`:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen python -c "import pathlib, science_tool; print(pathlib.Path(science_tool.__file__).resolve())"
```

Expected: printed path starts with the worktree path and includes `.worktrees/benchmark-fallback-diagnostics/science/src/science_tool`. Keep the `PYTHONPATH=science/src:science/model/src` prefix on every test, lint, and CLI command in this plan so the editable install from the main checkout cannot shadow worktree edits.

---

### Task 1: Emit `dataset_class` On Benchmark Test Rows

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add a failing report-level row metadata assertion**

In `science/tests/test_benchmark_opportunities.py`, update `test_benchmark_test_triage_report_buckets_and_preserves_summary_fields` after the existing run-now/metadata-needed benchmark-id assertions:

```python
    assert payload["buckets"]["run-now"][0]["dataset_class"] == "deposit"
    assert payload["buckets"]["metadata-needed"][0]["dataset_class"] == "reference"
    assert payload["buckets"]["fallback-diagnostic"][0]["dataset_class"] == "deposit"
```

In `science/tests/test_benchmark_cli.py`, update `test_benchmark_test_triage_cli_json_output` after the benchmark-id assertion:

```python
    assert payload["buckets"]["run-now"][0]["dataset_class"] == "deposit"
```

- [ ] **Step 2: Run focused tests and verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_buckets_and_preserves_summary_fields science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_json_output -q
```

Expected: FAIL with `KeyError: 'dataset_class'`.

- [ ] **Step 3: Add the row field and type**

In `science/src/science_tool/benchmark_opportunities.py`, extend the existing semantics import:

```python
from science_tool.datasets.semantics import DatasetClass, dataset_class_for, runtime_state_for
```

Do not add a local `DatasetClass` alias; `science_tool.datasets.semantics.DatasetClass` is the vocabulary source of truth.

Add the field to `BenchmarkTestRow`:

```python
    dataset_class: DatasetClass
```

In `_benchmark_test_row(...)`, add the row value immediately after `benchmark_title`:

```python
        "dataset_class": cast("DatasetClass", context.dataset.dataset_class),
```

Do not call `dataset_class_for(...)` here. The context already holds the normalized class from the dataset loading path.

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_buckets_and_preserves_summary_fields science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_json_output -q
```

Expected: PASS.

- [ ] **Step 5: Run type/lint check for the modified module**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen ruff check science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
git commit -m "feat: expose benchmark test dataset class"
```

Expected: commit created with only the three scoped files.

---

### Task 2: Add Visible Fallback Diagnostic Counts

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing diagnostics assertions for visible fallback rows**

In `science/tests/test_benchmark_opportunities.py`, replace the tail of `test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics` after `assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == len(fallback_rows)` with:

```python
    assert payload["fallback_diagnostics"]["top_benchmarks"][0]["benchmark_id"].startswith("dataset:fallback-")
    assert payload["fallback_diagnostics"]["top_facets"][0] == {"facet": "proteomics", "count": 2}
    assert payload["fallback_diagnostics"]["readiness_counts"] == {
        "runnable": 2,
        "stage-needed": 0,
        "metadata-only": 0,
        "blocked": 0,
    }
    assert payload["fallback_diagnostics"]["dataset_class_counts"] == {
        "deposit": 2,
        "reference": 0,
        "pointer": 0,
    }
    assert payload["fallback_diagnostics"]["task_support_counts"] == {
        "supported": 0,
        "candidate": 0,
        "blocked": 0,
        "none": 2,
    }
    assert sum(payload["fallback_diagnostics"]["readiness_counts"].values()) == len(fallback_rows)
    assert sum(payload["fallback_diagnostics"]["dataset_class_counts"].values()) == len(fallback_rows)
    assert sum(payload["fallback_diagnostics"]["task_support_counts"].values()) == len(fallback_rows)
    assert payload["fallback_diagnostics"]["top_benchmarks_by_readiness"]["runnable"][0]["benchmark_id"].startswith(
        "dataset:fallback-"
    )
    assert payload["fallback_diagnostics"]["top_benchmarks_by_readiness"]["metadata-only"] == []
    assert payload["fallback_diagnostics"]["top_benchmarks_by_dataset_class"]["deposit"][0]["benchmark_id"].startswith(
        "dataset:fallback-"
    )
    assert payload["fallback_diagnostics"]["top_benchmarks_by_dataset_class"]["reference"] == []
    assert payload["filters"]["source"] == "gap-fallback"
```

- [ ] **Step 2: Add a failing supported-state fallback test**

Add this test after `test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics`:

```python
def test_benchmark_test_triage_fallback_diagnostics_count_supported_task_support(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0102-supported-generic",
        """
id: hypothesis:0102-supported-generic
type: hypothesis
title: Generic supported benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "supported-fallback",
        """
id: dataset:supported-fallback
type: dataset
title: Supported Fallback
dataset_class: deposit
local_path: data/supported-fallback
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

    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == 1
    assert payload["fallback_diagnostics"]["task_support_counts"] == {
        "supported": 1,
        "candidate": 0,
        "blocked": 0,
        "none": 0,
    }
```

- [ ] **Step 3: Add a failing zero-count assertion to the suppression test**

In `test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default`, after the existing `top_benchmarks` assertion and before `suppressed_blocked_support`, add:

```python
    assert payload["fallback_diagnostics"]["readiness_counts"] == {
        "runnable": 1,
        "stage-needed": 0,
        "metadata-only": 0,
        "blocked": 0,
    }
    assert payload["fallback_diagnostics"]["dataset_class_counts"] == {
        "deposit": 1,
        "reference": 0,
        "pointer": 0,
    }
    assert payload["fallback_diagnostics"]["task_support_counts"] == {
        "supported": 0,
        "candidate": 0,
        "blocked": 0,
        "none": 1,
    }
```

This pins the design rule that suppressed blocked-support rows are not counted in visible fallback diagnostics.

- [ ] **Step 4: Add a failing empty-visible-fallback assertion**

In `test_benchmark_test_triage_report_exclude_fallback_prevents_suppression`, after the existing assertion that `suppressed_blocked_support` is absent, add:

```python
    assert payload["fallback_diagnostics"]["readiness_counts"] == {
        "runnable": 0,
        "stage-needed": 0,
        "metadata-only": 0,
        "blocked": 0,
    }
    assert payload["fallback_diagnostics"]["dataset_class_counts"] == {
        "deposit": 0,
        "reference": 0,
        "pointer": 0,
    }
    assert payload["fallback_diagnostics"]["task_support_counts"] == {
        "supported": 0,
        "candidate": 0,
        "blocked": 0,
        "none": 0,
    }
    assert payload["fallback_diagnostics"]["top_benchmarks_by_readiness"] == {
        "runnable": [],
        "stage-needed": [],
        "metadata-only": [],
        "blocked": [],
    }
    assert payload["fallback_diagnostics"]["top_benchmarks_by_dataset_class"] == {
        "deposit": [],
        "reference": [],
        "pointer": [],
    }
```

- [ ] **Step 5: Run focused tests and verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_diagnostics_count_supported_task_support science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_exclude_fallback_prevents_suppression -q
```

Expected: FAIL with missing `readiness_counts`, `dataset_class_counts`, `task_support_counts`, or grouped top benchmark keys.

- [ ] **Step 6: Add diagnostic types and constants**

In `science/src/science_tool/benchmark_opportunities.py`, update the collections import and add constants near the benchmark-test type aliases.

Change:

```python
from collections.abc import Mapping
```

to:

```python
from collections.abc import Mapping, Sequence
```

Add:

```python
TaskSupportCountKey = Literal["supported", "candidate", "blocked", "none"]

READINESS_LABELS: tuple[ReadinessLabel, ...] = ("runnable", "stage-needed", "metadata-only", "blocked")
DATASET_CLASSES: tuple[DatasetClass, ...] = ("deposit", "reference", "pointer")
TASK_SUPPORT_COUNT_KEYS: tuple[TaskSupportCountKey, ...] = ("supported", "candidate", "blocked", "none")
```

Change `_benchmark_test_readiness_counts(...)` so it can accept `BenchmarkTestTriageRow` lists without a cast:

```python
def _benchmark_test_readiness_counts(rows: Sequence[BenchmarkTestRow]) -> dict[ReadinessLabel, int]:
```

Extend `BenchmarkTestTriageFallbackDiagnostics`:

```python
class BenchmarkTestTriageFallbackDiagnostics(TypedDict):
    top_benchmarks: list[BenchmarkCountRow]
    top_facets: list[FacetCountRow]
    readiness_counts: dict[ReadinessLabel, int]
    dataset_class_counts: dict[DatasetClass, int]
    task_support_counts: dict[TaskSupportCountKey, int]
    top_benchmarks_by_readiness: dict[ReadinessLabel, list[BenchmarkCountRow]]
    top_benchmarks_by_dataset_class: dict[DatasetClass, list[BenchmarkCountRow]]
    suppressed_blocked_support: NotRequired[BenchmarkTestSuppressedBlockedSupportDiagnostics]
```

- [ ] **Step 7: Add helper functions**

In `science/src/science_tool/benchmark_opportunities.py`, after `_top_triage_facet_counts(...)`, add:

```python
def _benchmark_test_dataset_class_counts(rows: list[BenchmarkTestTriageRow]) -> dict[DatasetClass, int]:
    counts: dict[DatasetClass, int] = {dataset_class: 0 for dataset_class in DATASET_CLASSES}
    for row in rows:
        counts[row["dataset_class"]] += 1
    return counts


def _task_support_count_key(row: BenchmarkTestTriageRow) -> TaskSupportCountKey:
    state = row["task_support_state"]
    return state if state is not None else "none"


def _benchmark_test_task_support_counts(rows: list[BenchmarkTestTriageRow]) -> dict[TaskSupportCountKey, int]:
    counts: dict[TaskSupportCountKey, int] = {key: 0 for key in TASK_SUPPORT_COUNT_KEYS}
    for row in rows:
        counts[_task_support_count_key(row)] += 1
    return counts


def _top_triage_benchmark_counts_by_readiness(
    rows: list[BenchmarkTestTriageRow],
    *,
    top: int = 10,
) -> dict[ReadinessLabel, list[BenchmarkCountRow]]:
    return {
        readiness: _top_triage_benchmark_counts(
            [row for row in rows if row["readiness_label"] == readiness],
            top=top,
        )
        for readiness in READINESS_LABELS
    }


def _top_triage_benchmark_counts_by_dataset_class(
    rows: list[BenchmarkTestTriageRow],
    *,
    top: int = 10,
) -> dict[DatasetClass, list[BenchmarkCountRow]]:
    return {
        dataset_class: _top_triage_benchmark_counts(
            [row for row in rows if row["dataset_class"] == dataset_class],
            top=top,
        )
        for dataset_class in DATASET_CLASSES
    }


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
    }
```

- [ ] **Step 8: Use the helper in triage report construction**

In `benchmark_test_triage_report(...)`, replace:

```python
    fallback_diagnostics: BenchmarkTestTriageFallbackDiagnostics = {
        "top_benchmarks": _top_triage_benchmark_counts(fallback_rows),
        "top_facets": _top_triage_facet_counts(fallback_rows),
    }
```

with:

```python
    fallback_diagnostics = _benchmark_test_fallback_diagnostics(fallback_rows)
```

Keep the existing `suppressed_blocked_support` block unchanged.

- [ ] **Step 9: Run focused tests and verify they pass**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_fallback_diagnostics_count_supported_task_support science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_exclude_fallback_prevents_suppression -q
```

Expected: PASS.

- [ ] **Step 10: Run all benchmark-opportunity tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_opportunities.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

Run:

```bash
git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
git commit -m "feat: add fallback diagnostic breakdowns"
```

Expected: commit created with only the scoped files.

---

### Task 3: Show Diagnostics In CLI Table And Review Artifacts

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Update JSON review-file expectation for stable diagnostics**

In `science/tests/test_benchmark_cli.py`, update `test_benchmark_test_triage_cli_writes_default_review_file`.

Replace:

```python
    assert written["fallback_diagnostics"] == {"top_benchmarks": [], "top_facets": []}
```

with:

```python
    assert written["fallback_diagnostics"] == {
        "top_benchmarks": [],
        "top_facets": [],
        "readiness_counts": {
            "runnable": 0,
            "stage-needed": 0,
            "metadata-only": 0,
            "blocked": 0,
        },
        "dataset_class_counts": {
            "deposit": 0,
            "reference": 0,
            "pointer": 0,
        },
        "task_support_counts": {
            "supported": 0,
            "candidate": 0,
            "blocked": 0,
            "none": 0,
        },
        "top_benchmarks_by_readiness": {
            "runnable": [],
            "stage-needed": [],
            "metadata-only": [],
            "blocked": [],
        },
        "top_benchmarks_by_dataset_class": {
            "deposit": [],
            "reference": [],
            "pointer": [],
        },
    }
```

- [ ] **Step 2: Add a failing fallback table-output test**

Add this test after `test_benchmark_test_triage_cli_table_output_shows_suppression_diagnostic`:

```python
def test_benchmark_test_triage_cli_table_output_shows_fallback_breakdowns(tmp_path: Path) -> None:
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
""",
    )

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback")

    assert result.exit_code == 0
    assert "Benchmark Test Triage: fallback-diagnostic" in result.output
    assert "readiness" in result.output
    assert "class" in result.output
    assert "support" in result.output
    assert "runnable:1" in result.output
    assert "deposit:1" in result.output
    assert "none:1" in result.output
```

- [ ] **Step 3: Run focused CLI tests and verify they fail**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_writes_default_review_file science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_fallback_breakdowns -q
```

Expected: FAIL before CLI table changes, either because the new test is not present yet or because the `readiness`/`class`/`support` columns are absent.

- [ ] **Step 4: Update fallback diagnostic table columns**

In `science/src/science_tool/cli.py`, inside the `if fallback_count:` block for `Benchmark Test Triage: fallback-diagnostic`, replace:

```python
        for col in ("rows", "top benchmarks", "top facets"):
            table.add_column(col, overflow="fold", no_wrap=False)
        table.add_row(
            f"{fallback_count} fallback rows",
            _format_count_rows(diagnostics["top_benchmarks"], key="benchmark_id"),
            _format_count_rows(diagnostics["top_facets"], key="facet"),
        )
```

with:

```python
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
```

Add this helper near `_format_count_rows(...)` if no equivalent exists:

```python
def _format_count_map(counts: Mapping[str, int]) -> str:
    rows = [
        {"key": key, "count": count}
        for key, count in counts.items()
        if count
    ]
    return _format_count_rows(rows, key="key") if rows else "-"
```

If `_format_count_rows(...)` is defined after this helper's intended location, place `_format_count_map(...)` immediately after `_format_count_rows(...)` instead.

- [ ] **Step 5: Run focused CLI tests and verify they pass**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_writes_default_review_file science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_fallback_breakdowns -q
```

Expected: PASS.

- [ ] **Step 6: Run all benchmark CLI tests**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
git commit -m "feat: show fallback diagnostic breakdowns"
```

Expected: commit created with only the scoped files.

---

### Task 4: Full Verification And Calibration Smoke

**Files:**
- No code files changed unless verification finds a bug.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run ruff**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

Expected: PASS.

- [ ] **Step 3: Run a real-project JSON smoke on multiple myeloma**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --format json > /tmp/benchmark-triage-mm-fallback-diagnostics.json
```

Expected: exit 0. A stale commons registry warning on stderr is acceptable.

Then inspect the diagnostics:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/benchmark-triage-mm-fallback-diagnostics.json").read_text())
diagnostics = payload["fallback_diagnostics"]
fallback_count = payload["summary"]["bucket_counts"]["fallback-diagnostic"]
print("fallback_count", fallback_count)
print("readiness_counts", diagnostics["readiness_counts"])
print("dataset_class_counts", diagnostics["dataset_class_counts"])
print("task_support_counts", diagnostics["task_support_counts"])
print("suppressed", payload["summary"]["suppressed_blocked_support_fallback_rows"])
assert sum(diagnostics["readiness_counts"].values()) == fallback_count
assert sum(diagnostics["dataset_class_counts"].values()) == fallback_count
assert sum(diagnostics["task_support_counts"].values()) == fallback_count
PY
```

Expected: printed diagnostics with all three assertions passing.

- [ ] **Step 4: Run a real-project table smoke on natural systems**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback
```

Expected: exit 0 and, when fallback rows are present, a `Benchmark Test Triage: fallback-diagnostic` table with `readiness`, `class`, and `support` columns.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git status --short
git diff --stat
git diff
```

Expected: only scoped benchmark code/test files are dirty, or no dirty files if all tasks were committed.

- [ ] **Step 6: Commit any verification-only fixes**

If Task 4 revealed a small fix, commit it:

```bash
git add science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
git commit -m "fix: stabilize fallback diagnostic output"
```

Expected: commit created only if a fix was necessary. If there were no changes, skip this step.

---

## Self-Review Checklist

- Spec coverage:
  - `dataset_class` row metadata: Task 1.
  - Additive fallback diagnostic counts and grouped top benchmarks: Task 2.
  - Suppressed blocked-support fallback rows excluded from visible diagnostics: Task 2.
  - Stable zero-count diagnostics: Task 2.
  - CLI table columns: Task 3.
  - Real-project calibration smoke: Task 4.
- Placeholder scan:
  - No placeholder markers or unspecified implementation steps.
  - Every test and implementation step includes exact code or exact commands.
- Type consistency:
  - `DatasetClass` is imported from `science_tool.datasets.semantics`; `TaskSupportCountKey`, `BenchmarkTestRow.dataset_class`, and `BenchmarkTestTriageFallbackDiagnostics` are introduced before use.
  - Helper functions read from row fields already present in `BenchmarkTestRow`.
  - CLI uses payload fields produced by the report layer.

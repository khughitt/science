# Benchmark Blocked-Fallback Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Suppress `gap-fallback` rows with `task_support_state: blocked` from the default `science benchmark test-triage` action queue while preserving raw `science benchmark tests` output and explicit suppression diagnostics.

**Architecture:** Keep `benchmark_tests_report()` unchanged as the raw source of truth. Add a triage-only partition step inside `benchmark_test_triage_report()` that separates visible rows from suppressed blocked-support fallback rows, then bucket only visible rows and report the hidden population through summary and fallback diagnostics. Add a CLI flag that restores the current full fallback view for debugging.

**Tech Stack:** Python 3.12, Click CLI, Rich table output, PyYAML review artifacts, pytest.

---

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add `include_blocked_fallback` to `benchmark_test_triage_report()`.
  - Add triage-only helpers for identifying and partitioning blocked-support fallback rows.
  - Extend `BenchmarkTestTriageFallbackDiagnostics` with optional `suppressed_blocked_support`.
  - Add `summary.suppressed_blocked_support_fallback_rows`.
  - Keep `readiness_counts`, `source_counts`, `fallback_rows`, and `fallback_row_ratio` computed over upstream post-filter rows.

- Modify `science/src/science_tool/cli.py`
  - Add `--include-blocked-fallback` to `science benchmark test-triage`.
  - Pass the flag into `benchmark_test_triage_report()`.
  - Include the flag in review artifact source-command text when true.
  - Render a compact suppression diagnostic table independently of the visible fallback bucket.

- Modify `science/tests/test_benchmark_opportunities.py`
  - Add report-level tests for suppression, restoration, upstream summary counts, multi-task selectivity, and `--exclude-fallback` interaction at the function layer.

- Modify `science/tests/test_benchmark_cli.py`
  - Add CLI JSON tests for sparse filter behavior.
  - Add table-output test for compact suppression diagnostics.
  - Add review-file test for persisted suppression diagnostics.

---

### Task 0: Isolated Worktree Setup

**Files:**
- Verify only: repository state
- Create worktree: `.worktrees/benchmark-blocked-fallback-triage`

- [ ] **Step 1: Verify the main checkout is clean before creating the worktree**

Run from the repository root:

```bash
git status --short
```

Expected: no output. If there is output, stop and ask the user which changes belong to this plan before creating the worktree. Do not stash or commit unrelated changes.

- [ ] **Step 2: Create the feature worktree**

Run from the repository root:

```bash
git worktree add -b benchmark-blocked-fallback-triage .worktrees/benchmark-blocked-fallback-triage HEAD
```

Expected: worktree is created on branch `benchmark-blocked-fallback-triage`.

- [ ] **Step 3: Move into the feature worktree**

Run:

```bash
cd .worktrees/benchmark-blocked-fallback-triage
git status --short
git branch --show-current
```

Expected:

```text
benchmark-blocked-fallback-triage
```

All remaining commands in this plan run from `.worktrees/benchmark-blocked-fallback-triage`.

---

### Task 1: Report-Layer Suppression Contract

**Files:**
- Modify: `science/tests/test_benchmark_opportunities.py`
- Modify: `science/src/science_tool/benchmark_opportunities.py`

- [ ] **Step 1: Write the failing report-level tests**

Add these tests after `test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics()` in `science/tests/test_benchmark_opportunities.py`:

```python
def test_benchmark_test_triage_report_suppresses_blocked_support_fallback_by_default(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0103-generic",
        """
id: hypothesis:0103-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "mmrf-like",
        """
id: dataset:mmrf-like
type: dataset
title: MMRF-like benchmark
dataset_class: deposit
local_path: data/mmrf-like
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
    - id: overall-survival
      task_type: survival prediction
      prediction_target: overall survival
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: overall survival endpoint
""",
    )

    payload = benchmark_test_triage_report(tmp_path, source="gap-fallback")

    assert payload["summary"]["test_plan_rows"] == 2
    assert payload["summary"]["source_counts"]["gap-fallback"] == 2
    assert payload["summary"]["fallback_rows"] == 2
    assert sum(payload["summary"]["readiness_counts"].values()) == 2
    assert payload["summary"]["suppressed_blocked_support_fallback_rows"] == 1
    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == 1
    assert [row["task_id"] for row in payload["buckets"]["fallback-diagnostic"]] == [
        "dataset:mmrf-like#overall-survival"
    ]
    assert payload["fallback_diagnostics"]["top_benchmarks"] == [
        {"benchmark_id": "dataset:mmrf-like", "count": 1}
    ]
    assert payload["fallback_diagnostics"]["suppressed_blocked_support"] == {
        "rows": 1,
        "top_benchmarks": [{"benchmark_id": "dataset:mmrf-like", "count": 1}],
    }
    assert "include_blocked_fallback" not in payload["filters"]


def test_benchmark_test_triage_report_include_blocked_fallback_restores_rows(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0104-generic",
        """
id: hypothesis:0104-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "blocked-fallback",
        """
id: dataset:blocked-fallback
type: dataset
title: Blocked Fallback
dataset_class: deposit
local_path: data/blocked-fallback
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
""",
    )

    payload = benchmark_test_triage_report(tmp_path, source="gap-fallback", include_blocked_fallback=True)

    assert payload["summary"]["test_plan_rows"] == 1
    assert payload["summary"]["source_counts"]["gap-fallback"] == 1
    assert payload["summary"]["fallback_rows"] == 1
    assert payload["summary"]["suppressed_blocked_support_fallback_rows"] == 0
    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == 1
    assert [row["task_id"] for row in payload["buckets"]["fallback-diagnostic"]] == [
        "dataset:blocked-fallback#progression-risk"
    ]
    assert "suppressed_blocked_support" not in payload["fallback_diagnostics"]
    assert payload["filters"]["include_blocked_fallback"] is True


def test_benchmark_test_triage_report_exclude_fallback_prevents_suppression(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0105-generic",
        """
id: hypothesis:0105-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "blocked-fallback",
        """
id: dataset:blocked-fallback
type: dataset
title: Blocked Fallback
dataset_class: deposit
local_path: data/blocked-fallback
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
""",
    )

    payload = benchmark_test_triage_report(
        tmp_path,
        source="gap-fallback",
        exclude_fallback=True,
        include_blocked_fallback=True,
    )

    assert payload["summary"]["test_plan_rows"] == 0
    assert payload["summary"]["source_counts"]["gap-fallback"] == 0
    assert payload["summary"]["fallback_rows"] == 0
    assert payload["summary"]["suppressed_blocked_support_fallback_rows"] == 0
    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == 0
    assert "suppressed_blocked_support" not in payload["fallback_diagnostics"]
    assert payload["filters"]["exclude_fallback"] is True
    assert payload["filters"]["include_blocked_fallback"] is True
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py \
  -k 'blocked_support_fallback or include_blocked_fallback_restores or exclude_fallback_prevents_suppression' -q
```

Expected: FAIL. At least one failure should mention `benchmark_test_triage_report() got an unexpected keyword argument 'include_blocked_fallback'`, and default suppression assertions should fail before implementation.

- [ ] **Step 3: Extend triage types and add suppression helpers**

In `science/src/science_tool/benchmark_opportunities.py`, replace the current `BenchmarkTestTriageFallbackDiagnostics` definition:

```python
class BenchmarkTestTriageFallbackDiagnostics(TypedDict):
    top_benchmarks: list[BenchmarkCountRow]
    top_facets: list[FacetCountRow]
```

with:

```python
class BenchmarkTestSuppressedBlockedSupportDiagnostics(TypedDict):
    rows: int
    top_benchmarks: list[BenchmarkCountRow]


class BenchmarkTestTriageFallbackDiagnostics(TypedDict):
    top_benchmarks: list[BenchmarkCountRow]
    top_facets: list[FacetCountRow]
    suppressed_blocked_support: NotRequired[BenchmarkTestSuppressedBlockedSupportDiagnostics]
```

After `_top_triage_facet_counts(...)`, add:

```python
def _is_blocked_support_fallback(row: BenchmarkTestRow) -> bool:
    return row["priority_source"] == "gap-fallback" and row.get("task_support_state") == "blocked"


def _partition_blocked_support_fallback_rows(
    rows: list[BenchmarkTestRow],
    *,
    include_blocked_fallback: bool,
) -> tuple[list[BenchmarkTestRow], list[BenchmarkTestRow]]:
    if include_blocked_fallback:
        return rows, []

    visible: list[BenchmarkTestRow] = []
    suppressed: list[BenchmarkTestRow] = []
    for row in rows:
        if _is_blocked_support_fallback(row):
            suppressed.append(row)
        else:
            visible.append(row)
    return visible, suppressed
```

- [ ] **Step 4: Add suppression count to triage summary**

Change `_benchmark_test_triage_summary(...)` from:

```python
def _benchmark_test_triage_summary(
    report_summary: BenchmarkTestSummary,
    *,
    rows: list[BenchmarkTestRow],
    buckets: dict[BenchmarkTestTriageBucket, list[BenchmarkTestTriageRow]],
) -> dict[str, Any]:
    summary: dict[str, Any] = dict(report_summary)
    summary["bucket_counts"] = _benchmark_test_triage_bucket_counts(buckets)
    summary["readiness_counts"] = _benchmark_test_readiness_counts(rows)
    return summary
```

to:

```python
def _benchmark_test_triage_summary(
    report_summary: BenchmarkTestSummary,
    *,
    rows: list[BenchmarkTestRow],
    buckets: dict[BenchmarkTestTriageBucket, list[BenchmarkTestTriageRow]],
    suppressed_blocked_support_fallback_rows: int,
) -> dict[str, Any]:
    summary: dict[str, Any] = dict(report_summary)
    summary["bucket_counts"] = _benchmark_test_triage_bucket_counts(buckets)
    summary["readiness_counts"] = _benchmark_test_readiness_counts(rows)
    summary["suppressed_blocked_support_fallback_rows"] = suppressed_blocked_support_fallback_rows
    return summary
```

- [ ] **Step 5: Add the sparse include flag to triage filters**

Change `_benchmark_test_triage_filters(...)` to accept `include_blocked_fallback: bool` after `exclude_fallback: bool`.

Inside the function, after the existing `exclude_fallback` block, add:

```python
    if include_blocked_fallback:
        filters["include_blocked_fallback"] = True
```

Update the function signature to:

```python
def _benchmark_test_triage_filters(
    *,
    include_commons: bool,
    entity_id: str | None,
    domain: str | None,
    facet: str | None,
    state: TestPlanState | None,
    source: PrioritySource | None,
    exclude_fallback: bool,
    include_blocked_fallback: bool,
    readiness: ReadinessLabel | None,
    benchmark_id: str | None,
) -> dict[str, Any]:
```

- [ ] **Step 6: Partition rows inside `benchmark_test_triage_report()`**

Change the `benchmark_test_triage_report(...)` signature to include:

```python
    include_blocked_fallback: bool = False,
```

after `exclude_fallback: bool = False`.

Replace the current bucket-building block:

```python
    rows = report["benchmark_tests"]
    buckets = _empty_benchmark_test_triage_buckets()
    for row in rows:
        bucket = _benchmark_test_triage_bucket(row)
        buckets[bucket].append(_benchmark_test_triage_row(row))

    fallback_rows = buckets["fallback-diagnostic"]
    return {
        "summary": _benchmark_test_triage_summary(report["summary"], rows=rows, buckets=buckets),
        "buckets": buckets,
        "fallback_diagnostics": {
            "top_benchmarks": _top_triage_benchmark_counts(fallback_rows),
            "top_facets": _top_triage_facet_counts(fallback_rows),
        },
```

with:

```python
    rows = report["benchmark_tests"]
    visible_rows, suppressed_blocked_support_rows = _partition_blocked_support_fallback_rows(
        rows,
        include_blocked_fallback=include_blocked_fallback,
    )
    buckets = _empty_benchmark_test_triage_buckets()
    for row in visible_rows:
        bucket = _benchmark_test_triage_bucket(row)
        buckets[bucket].append(_benchmark_test_triage_row(row))

    fallback_rows = buckets["fallback-diagnostic"]
    fallback_diagnostics: BenchmarkTestTriageFallbackDiagnostics = {
        "top_benchmarks": _top_triage_benchmark_counts(fallback_rows),
        "top_facets": _top_triage_facet_counts(fallback_rows),
    }
    if suppressed_blocked_support_rows:
        suppressed_triage_rows = [_benchmark_test_triage_row(row) for row in suppressed_blocked_support_rows]
        fallback_diagnostics["suppressed_blocked_support"] = {
            "rows": len(suppressed_blocked_support_rows),
            "top_benchmarks": _top_triage_benchmark_counts(suppressed_triage_rows),
        }
    return {
        "summary": _benchmark_test_triage_summary(
            report["summary"],
            rows=rows,
            buckets=buckets,
            suppressed_blocked_support_fallback_rows=len(suppressed_blocked_support_rows),
        ),
        "buckets": buckets,
        "fallback_diagnostics": fallback_diagnostics,
```

In the `_benchmark_test_triage_filters(...)` call in the same return value, pass:

```python
            include_blocked_fallback=include_blocked_fallback,
```

after `exclude_fallback=exclude_fallback`.

- [ ] **Step 7: Run the report-layer tests**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py \
  -k 'benchmark_test_triage_report or benchmark_test_triage_bucket' -q
```

Expected: PASS.

- [ ] **Step 8: Commit report-layer suppression**

Run:

```bash
git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
git commit -m "feat: suppress blocked fallback triage rows"
```

Expected: commit succeeds.

---

### Task 2: CLI Flag, JSON Filters, and Table Diagnostics

**Files:**
- Modify: `science/tests/test_benchmark_cli.py`
- Modify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Write the failing CLI JSON and table tests**

Add these tests after `test_benchmark_test_triage_candidate_support_does_not_enter_run_now()` in `science/tests/test_benchmark_cli.py`:

```python
def test_benchmark_test_triage_cli_suppresses_blocked_fallback_by_default(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0305-generic",
        """
id: hypothesis:0305-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "blocked-fallback",
        """
id: dataset:blocked-fallback
type: dataset
title: Blocked Fallback
dataset_class: deposit
local_path: data/blocked-fallback
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
""",
    )

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["fallback_rows"] == 1
    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == 0
    assert payload["summary"]["suppressed_blocked_support_fallback_rows"] == 1
    assert payload["fallback_diagnostics"]["suppressed_blocked_support"] == {
        "rows": 1,
        "top_benchmarks": [{"benchmark_id": "dataset:blocked-fallback", "count": 1}],
    }
    assert "include_blocked_fallback" not in payload["filters"]


def test_benchmark_test_triage_cli_include_blocked_fallback_restores_json_rows(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0306-generic",
        """
id: hypothesis:0306-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "blocked-fallback",
        """
id: dataset:blocked-fallback
type: dataset
title: Blocked Fallback
dataset_class: deposit
local_path: data/blocked-fallback
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
""",
    )

    result = _invoke_test_triage(
        tmp_path,
        "--source",
        "gap-fallback",
        "--include-blocked-fallback",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == 1
    assert payload["summary"]["suppressed_blocked_support_fallback_rows"] == 0
    assert "suppressed_blocked_support" not in payload["fallback_diagnostics"]
    assert payload["filters"]["include_blocked_fallback"] is True
    assert payload["buckets"]["fallback-diagnostic"][0]["task_support_state"] == "blocked"


def test_benchmark_test_triage_cli_table_output_shows_suppression_diagnostic(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0307-generic",
        """
id: hypothesis:0307-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "blocked-fallback",
        """
id: dataset:blocked-fallback
type: dataset
title: Blocked Fallback
dataset_class: deposit
local_path: data/blocked-fallback
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
""",
    )

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback")

    assert result.exit_code == 0
    assert "Suppressed 1 fallback rows for blocked task support" in result.output
    assert "dataset:blocked-fallback (1)" in result.output
    assert "Benchmark Test Triage: fallback-diagnostic" not in result.output
    assert "No benchmark test triage rows." not in result.output
```

- [ ] **Step 2: Run the new CLI tests to verify they fail**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_benchmark_cli.py \
  -k 'blocked_fallback_by_default or include_blocked_fallback_restores_json_rows or suppression_diagnostic' -q
```

Expected: FAIL. The first test may fail because `--include-blocked-fallback` is not registered yet, and table output will not include the suppression diagnostic until implemented.

- [ ] **Step 3: Add the CLI flag and pass it to the report**

In `science/src/science_tool/cli.py`, add this option to the `benchmark_test_triage` decorators near `--exclude-fallback`:

```python
@click.option(
    "--include-blocked-fallback",
    is_flag=True,
    help="Include gap-fallback rows for blocked task-support tasks in triage output.",
)
```

Add `include_blocked_fallback: bool` to the `benchmark_test_triage(...)` function parameters immediately after `exclude_fallback: bool`.

In the `benchmark_test_triage_report(...)` call, pass:

```python
            include_blocked_fallback=include_blocked_fallback,
```

after `exclude_fallback=exclude_fallback`.

- [ ] **Step 4: Thread the flag into review source-command text**

Change `_test_triage_source_command(...)` to accept `include_blocked_fallback: bool` after `exclude_fallback: bool`.

Inside `_test_triage_source_command(...)`, after:

```python
    if exclude_fallback:
        parts.append("--exclude-fallback")
```

add:

```python
    if include_blocked_fallback:
        parts.append("--include-blocked-fallback")
```

In the `_test_triage_source_command(...)` call inside `benchmark_test_triage(...)`, pass:

```python
                    include_blocked_fallback=include_blocked_fallback,
```

after `exclude_fallback=exclude_fallback`.

- [ ] **Step 5: Render the compact suppression diagnostic table**

In `benchmark_test_triage(...)`, after the existing visible fallback-diagnostic table block and before:

```python
    if not visible_rows:
        click.echo("No benchmark test triage rows.")
        return
```

add:

```python
    suppressed = payload["fallback_diagnostics"].get("suppressed_blocked_support")
    if suppressed:
        table = Table(
            title="Benchmark Test Triage: suppressed blocked fallback",
            show_header=True,
            header_style="bold",
        )
        for col in ("rows", "top benchmarks"):
            table.add_column(col, overflow="fold", no_wrap=False)
        table.add_row(
            f"Suppressed {suppressed['rows']} fallback rows for blocked task support",
            _format_count_rows(suppressed["top_benchmarks"], key="benchmark_id"),
        )
        Console(width=200).print(table)
        visible_rows += 1
```

- [ ] **Step 6: Run the focused CLI tests**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_benchmark_cli.py \
  -k 'blocked_fallback_by_default or include_blocked_fallback_restores_json_rows or suppression_diagnostic' -q
```

Expected: PASS.

- [ ] **Step 7: Run existing triage CLI tests**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -k 'benchmark_test_triage' -q
```

Expected: PASS.

- [ ] **Step 8: Commit CLI flag and table diagnostics**

Run:

```bash
git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
git commit -m "feat: expose blocked fallback triage control"
```

Expected: commit succeeds.

---

### Task 3: Review Artifact and Regression Verification

**Files:**
- Modify: `science/tests/test_benchmark_cli.py`
- Verify: `science/src/science_tool/benchmark_opportunities.py`
- Verify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Add a review-file regression test**

Add this test after `test_benchmark_test_triage_cli_writes_default_review_file(...)` in `science/tests/test_benchmark_cli.py`:

```python
def test_benchmark_test_triage_review_file_includes_suppression_diagnostics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 3))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0308-generic",
        """
id: hypothesis:0308-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "blocked-fallback",
        """
id: dataset:blocked-fallback
type: dataset
title: Blocked Fallback
dataset_class: deposit
local_path: data/blocked-fallback
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
""",
    )

    result = _invoke_test_triage(
        tmp_path,
        "--source",
        "gap-fallback",
        "--write-review-file",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    review_path = tmp_path / "doc" / "audits" / "benchmark-test-triage" / f"2026-07-03-{tmp_path.name}.yaml"
    written = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    assert written["summary"]["fallback_rows"] == 1
    assert written["summary"]["bucket_counts"]["fallback-diagnostic"] == 0
    assert written["summary"]["suppressed_blocked_support_fallback_rows"] == 1
    assert written["buckets"]["fallback-diagnostic"] == []
    assert written["fallback_diagnostics"]["suppressed_blocked_support"] == {
        "rows": 1,
        "top_benchmarks": [{"benchmark_id": "dataset:blocked-fallback", "count": 1}],
    }
```

- [ ] **Step 2: Run the review-file test**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_test_triage_review_file_includes_suppression_diagnostics -q
```

Expected: PASS. If it fails before Task 2 implementation, the failure should be due to missing suppression diagnostics in the written artifact.

- [ ] **Step 3: Run the full benchmark-opportunities and CLI benchmark tests**

Run:

```bash
uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 4: Run lint on touched Python files**

Run:

```bash
uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

Expected: PASS.

- [ ] **Step 5: Run real-project calibration checks**

Run:

```bash
uv run --frozen --project science science benchmark test-triage \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --benchmark mmrf-commpass \
  --format json
```

Expected qualitative output:

- `summary.suppressed_blocked_support_fallback_rows` is greater than `0`.
- `summary.bucket_counts["fallback-diagnostic"]` is lower than `summary.fallback_rows`.
- `fallback_diagnostics.suppressed_blocked_support.top_benchmarks` includes `dataset:mmrf-commpass`.
- Non-fallback rows for `dataset:mmrf-commpass#progression-risk` remain in `blocked-or-reference`.

Run the opt-in comparison:

```bash
uv run --frozen --project science science benchmark test-triage \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --benchmark mmrf-commpass \
  --include-blocked-fallback \
  --format json
```

Expected qualitative output:

- `summary.suppressed_blocked_support_fallback_rows` is `0`.
- `filters.include_blocked_fallback` is `true`.
- Blocked-support fallback rows are present in `buckets["fallback-diagnostic"]`.

- [ ] **Step 6: Commit review-file test and final verification fixes**

If Step 1 required test-only additions after Task 2, run:

```bash
git add science/tests/test_benchmark_cli.py
git commit -m "test: cover blocked fallback triage artifacts"
```

If no files changed after Task 2, skip this commit and note that the review artifact behavior was already covered by Task 2 changes.

---

## Self-Review

### Spec Coverage

- Default suppression of `priority_source == "gap-fallback"` plus `task_support_state == "blocked"`: Task 1.
- `--include-blocked-fallback` restores current behavior: Tasks 1 and 2.
- `--exclude-fallback` wins before suppression: Task 1.
- Raw `benchmark_tests_report()` unchanged: Task 1 implements partition only in `benchmark_test_triage_report()`.
- Non-fallback blocked rows remain visible: existing test `test_benchmark_test_triage_routes_blocked_task_support_to_blocked_bucket` remains in the Task 3 full run.
- Non-blocked fallback rows remain visible: Task 1 multi-task test keeps `overall-survival` in `fallback-diagnostic`.
- Multi-task blocked-only suppression: Task 1.
- Summary counts split upstream row set from displayed buckets: Task 1.
- `readiness_counts` include suppressed rows: Task 1.
- Sparse filters convention for `include_blocked_fallback`: Tasks 1 and 2.
- Table suppression diagnostic independent of visible fallback bucket: Task 2.
- Review YAML includes suppression diagnostics and does not expand suppressed rows: Task 3.
- Real-project calibration: Task 3.

### Placeholder Scan

Red-flag scan is clean. All new helper/function names are defined before use.

### Type Consistency

- `include_blocked_fallback` is added consistently to `benchmark_test_triage_report()`, `_benchmark_test_triage_filters()`, CLI parameters, and `_test_triage_source_command()`.
- `BenchmarkTestTriageFallbackDiagnostics.suppressed_blocked_support` is optional and omitted when zero rows are suppressed.
- `summary.suppressed_blocked_support_fallback_rows` is always present and numeric.
- Suppression diagnostics aggregate only by `benchmark_id`; no `top_reasons` field is introduced.

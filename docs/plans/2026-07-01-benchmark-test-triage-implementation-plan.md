# Benchmark Test Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science benchmark test-triage`, a read-only benchmark validation work-queue report with an explicit YAML review artifact option.

**Architecture:** Build a projection layer over the existing `benchmark_tests_report()` output. The benchmark matching, scoring, filtering, readiness labels, and row ordering remain in `benchmark_tests_report()`; triage only buckets rows, summarizes the buckets, renders a compact table, and optionally writes a durable project-local YAML review artifact.

**Tech Stack:** Python 3, Click, Rich tables, PyYAML, existing Science benchmark report helpers, pytest, ruff.

---

## Design References

- Approved spec: `docs/plans/2026-07-01-benchmark-test-triage-design.md`
- Existing report implementation: `science/src/science_tool/benchmark_opportunities.py`
- Existing CLI surface: `science/src/science_tool/cli.py`
- Existing report tests: `science/tests/test_benchmark_opportunities.py`
- Existing CLI artifact precedent: `science benchmark hint-candidates` in `science/src/science_tool/cli.py`

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add triage types.
  - Add bucket assignment and summary helpers.
  - Add `benchmark_test_triage_report()`.
  - Keep `benchmark_tests_report()` unchanged except for reused types/helpers if needed.
- Modify `science/src/science_tool/cli.py`
  - Add date/path/source-command/review-file helpers for benchmark test triage.
  - Add `science benchmark test-triage`.
  - Mirror `benchmark hint-candidates` path and no-overwrite behavior.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add report-level unit tests for bucket assignment, ordering, summary, fallback diagnostics, and filter forwarding.
- Modify `science/tests/test_benchmark_cli.py`
  - Add CLI tests for JSON, table, review file writing, output validation, no-overwrite, and commons notice.

Do not create first-class benchmark-test entities in this plan. Do not add apply behavior.

---

## Task 1: Triage Report Projection

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

### Goal

Add a pure report function:

```python
benchmark_test_triage_report(...)
```

It calls `benchmark_tests_report()` once, preserves existing filters and sort order, buckets the resulting rows, adds review placeholders, and returns summary/fallback diagnostics.

- [ ] **Step 1: Add failing report tests**

Append these tests near the existing `benchmark_tests_report` tests in `science/tests/test_benchmark_opportunities.py`.

```python
def _benchmark_test_row_for_triage(
    *,
    entity_id: str,
    benchmark_id: str,
    test_plan_state: str,
    readiness_label: str,
    priority_source: str,
    priority_score: int = 10,
    task_id: str | None = "dataset:benchmark#task",
    matched_facets: list[str] | None = None,
    needs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "entity_title": entity_id.removeprefix("hypothesis:"),
        "benchmark_id": benchmark_id,
        "benchmark_title": benchmark_id.removeprefix("dataset:"),
        "task_id": task_id,
        "test_plan_state": test_plan_state,
        "task_type": "validation",
        "benchmark_kinds": ["static-association"],
        "readiness_label": readiness_label,
        "priority_score": priority_score,
        "priority_source": priority_source,
        "score_components": {"source": {"component": priority_score}, "baseline": {}},
        "matched_facets": matched_facets or ["perturbation"],
        "reason_notes": ["fixture"],
        "prediction_target": "target" if task_id else "",
        "held_out_unit": "unit" if task_id else "",
        "metric": "auroc" if task_id else "",
        "baseline": "majority-class" if task_id else "",
        "ground_truth": {"type": "measured-outcome" if task_id else "", "description": "label" if task_id else ""},
        "needs": needs or ([] if task_id else ["prediction-target", "held-out-unit", "metric", "baseline", "ground-truth"]),
    }


def test_benchmark_test_triage_bucket_assignment_is_ordered() -> None:
    from science_tool.benchmark_opportunities import _benchmark_test_triage_bucket

    assert (
        _benchmark_test_triage_bucket(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:run",
                benchmark_id="dataset:run",
                test_plan_state="concrete",
                readiness_label="runnable",
                priority_source="opportunity-relative",
            )
        )
        == "run-now"
    )
    assert (
        _benchmark_test_triage_bucket(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:stage",
                benchmark_id="dataset:stage",
                test_plan_state="draft-needed",
                readiness_label="stage-needed",
                priority_source="gap-candidate",
                task_id=None,
            )
        )
        == "stage-next"
    )
    assert (
        _benchmark_test_triage_bucket(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:metadata",
                benchmark_id="dataset:metadata",
                test_plan_state="draft-needed",
                readiness_label="metadata-only",
                priority_source="gap-candidate",
                task_id=None,
            )
        )
        == "metadata-needed"
    )
    assert (
        _benchmark_test_triage_bucket(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:blocked",
                benchmark_id="dataset:blocked",
                test_plan_state="concrete",
                readiness_label="blocked",
                priority_source="opportunity-relative",
            )
        )
        == "blocked-or-reference"
    )
    assert (
        _benchmark_test_triage_bucket(
            _benchmark_test_row_for_triage(
                entity_id="hypothesis:fallback",
                benchmark_id="dataset:fallback",
                test_plan_state="concrete",
                readiness_label="runnable",
                priority_source="gap-fallback",
            )
        )
        == "fallback-diagnostic"
    )


def test_benchmark_test_triage_report_buckets_and_preserves_summary_fields(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0100-perturbation",
        """
id: hypothesis:0100-perturbation
type: hypothesis
title: Perturbation response hypothesis
""",
        body="Drug perturbation should shift response states.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0101-spatial",
        """
id: hypothesis:0101-spatial
type: hypothesis
title: Spatial validation hypothesis
""",
        body="Microenvironment region structure needs validation.",
    )
    _write_dataset(
        tmp_path,
        "runnable-perturbation",
        """
id: dataset:runnable-perturbation
type: dataset
title: Runnable Perturbation
dataset_class: deposit
local_path: data/runnable-perturbation
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )
    _write_dataset(
        tmp_path,
        "spatial-reference",
        """
id: dataset:spatial-reference
type: dataset
title: Spatial Reference
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    payload = benchmark_test_triage_report(tmp_path)

    assert payload["commons_notice"] is None
    assert payload["review_file"] is None
    assert payload["summary"]["test_plan_rows"] == 2
    assert payload["summary"]["source_counts"]["opportunity-relative"] == 2
    assert payload["summary"]["bucket_counts"] == {
        "run-now": 1,
        "stage-next": 0,
        "metadata-needed": 1,
        "blocked-or-reference": 0,
        "fallback-diagnostic": 0,
    }
    assert payload["summary"]["readiness_counts"]["runnable"] == 1
    assert payload["summary"]["readiness_counts"]["metadata-only"] == 1
    assert [row["benchmark_id"] for row in payload["buckets"]["run-now"]] == ["dataset:runnable-perturbation"]
    assert [row["benchmark_id"] for row in payload["buckets"]["metadata-needed"]] == ["dataset:spatial-reference"]
    assert payload["buckets"]["run-now"][0]["review"] == {
        "decision": "",
        "owner": "",
        "next_action": "",
        "notes": "",
    }
    assert payload["fallback_diagnostics"] == {"top_benchmarks": [], "top_facets": []}


def test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_test_triage_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0102-generic",
        """
id: hypothesis:0102-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "fallback-a",
        """
id: dataset:fallback-a
type: dataset
title: Fallback A
dataset_class: deposit
local_path: data/fallback-a
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
        "fallback-b",
        """
id: dataset:fallback-b
type: dataset
title: Fallback B
dataset_class: deposit
local_path: data/fallback-b
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [perturbation]
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

    payload = benchmark_test_triage_report(tmp_path, source="gap-fallback")

    fallback_rows = payload["buckets"]["fallback-diagnostic"]
    assert fallback_rows
    assert {row["priority_source"] for row in fallback_rows} == {"gap-fallback"}
    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == len(fallback_rows)
    assert payload["fallback_diagnostics"]["top_benchmarks"][0]["benchmark_id"].startswith("dataset:fallback-")
    assert payload["fallback_diagnostics"]["top_facets"][0] == {"facet": "proteomics", "count": 2}
    assert payload["filters"]["source"] == "gap-fallback"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_bucket_assignment_is_ordered \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_buckets_and_preserves_summary_fields \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics \
  -q
```

Expected: FAIL because `_benchmark_test_triage_bucket` and `benchmark_test_triage_report` are not defined.

- [ ] **Step 3: Add triage types**

In `science/src/science_tool/benchmark_opportunities.py`, add these definitions after `BenchmarkTestReport`.

```python
BenchmarkTestTriageBucket = Literal[
    "run-now",
    "stage-next",
    "metadata-needed",
    "blocked-or-reference",
    "fallback-diagnostic",
]

BENCHMARK_TEST_TRIAGE_BUCKETS: tuple[BenchmarkTestTriageBucket, ...] = (
    "run-now",
    "stage-next",
    "metadata-needed",
    "blocked-or-reference",
    "fallback-diagnostic",
)


class BenchmarkTestReviewFields(TypedDict):
    decision: str
    owner: str
    next_action: str
    notes: str


class BenchmarkTestTriageRow(BenchmarkTestRow):
    review: BenchmarkTestReviewFields


class BenchmarkTestTriageFallbackDiagnostics(TypedDict):
    top_benchmarks: list[BenchmarkCountRow]
    top_facets: list[FacetCountRow]


class BenchmarkTestTriageReport(TypedDict):
    summary: dict[str, Any]
    buckets: dict[BenchmarkTestTriageBucket, list[BenchmarkTestTriageRow]]
    fallback_diagnostics: BenchmarkTestTriageFallbackDiagnostics
    filters: dict[str, Any]
    review_file: str | None
    commons_notice: str | None
```

If `Any` is not already imported in this file, add it to the existing typing imports.

- [ ] **Step 4: Add report projection helpers**

In `science/src/science_tool/benchmark_opportunities.py`, add these helpers after `_benchmark_test_summary`.

```python
def _empty_benchmark_test_triage_buckets() -> dict[BenchmarkTestTriageBucket, list[BenchmarkTestTriageRow]]:
    return {bucket: [] for bucket in BENCHMARK_TEST_TRIAGE_BUCKETS}


def _benchmark_test_triage_bucket(row: BenchmarkTestRow) -> BenchmarkTestTriageBucket:
    if (
        row["test_plan_state"] == "concrete"
        and row["readiness_label"] == "runnable"
        and row["priority_source"] != "gap-fallback"
    ):
        return "run-now"
    if row["readiness_label"] == "stage-needed" and row["priority_source"] != "gap-fallback":
        return "stage-next"
    if (
        row["test_plan_state"] == "draft-needed"
        and row["priority_source"] != "gap-fallback"
        and row["readiness_label"] != "blocked"
    ):
        return "metadata-needed"
    if row["readiness_label"] in {"metadata-only", "blocked"} and row["priority_source"] != "gap-fallback":
        return "blocked-or-reference"
    if row["priority_source"] == "gap-fallback":
        return "fallback-diagnostic"
    raise ValueError(f"unable to classify benchmark test row: {row['entity_id']} {row['benchmark_id']}")


def _benchmark_test_review_fields() -> BenchmarkTestReviewFields:
    return {
        "decision": "",
        "owner": "",
        "next_action": "",
        "notes": "",
    }


def _benchmark_test_triage_row(row: BenchmarkTestRow) -> BenchmarkTestTriageRow:
    return cast("BenchmarkTestTriageRow", {**row, "review": _benchmark_test_review_fields()})


def _benchmark_test_triage_bucket_counts(
    buckets: dict[BenchmarkTestTriageBucket, list[BenchmarkTestTriageRow]],
) -> dict[BenchmarkTestTriageBucket, int]:
    return {bucket: len(buckets[bucket]) for bucket in BENCHMARK_TEST_TRIAGE_BUCKETS}


def _benchmark_test_readiness_counts(rows: list[BenchmarkTestRow]) -> dict[ReadinessLabel, int]:
    counts: dict[ReadinessLabel, int] = {
        "runnable": 0,
        "stage-needed": 0,
        "metadata-only": 0,
        "blocked": 0,
    }
    for row in rows:
        counts[row["readiness_label"]] += 1
    return counts


def _top_triage_benchmark_counts(rows: list[BenchmarkTestTriageRow], *, top: int = 10) -> list[BenchmarkCountRow]:
    counter = Counter(row["benchmark_id"] for row in rows)
    return [
        {"benchmark_id": benchmark_id, "count": count}
        for benchmark_id, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top]
    ]


def _top_triage_facet_counts(rows: list[BenchmarkTestTriageRow], *, top: int = 10) -> list[FacetCountRow]:
    counter = Counter(facet for row in rows for facet in row["matched_facets"])
    return [
        {"facet": facet, "count": count}
        for facet, count in sorted(counter.items(), key=lambda item: (-item[1], _facet_sort_key(item[0])))[:top]
    ]


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


def _benchmark_test_triage_filters(
    *,
    include_commons: bool,
    entity_id: str | None,
    domain: str | None,
    facet: str | None,
    state: TestPlanState | None,
    source: PrioritySource | None,
    exclude_fallback: bool,
    readiness: ReadinessLabel | None,
    benchmark_id: str | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    if include_commons:
        filters["include_commons"] = True
    if entity_id is not None:
        filters["entity_id"] = entity_id
    if domain is not None:
        filters["domain"] = domain
    if facet is not None:
        filters["facet"] = facet
    if state is not None:
        filters["state"] = state
    if source is not None:
        filters["source"] = source
    if exclude_fallback:
        filters["exclude_fallback"] = True
    if readiness is not None:
        filters["readiness"] = readiness
    if benchmark_id is not None:
        filters["benchmark_id"] = benchmark_id
    return filters
```

- [ ] **Step 5: Add `benchmark_test_triage_report()`**

In `science/src/science_tool/benchmark_opportunities.py`, add this function after `benchmark_tests_report()`.

```python
def benchmark_test_triage_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    facet: str | None = None,
    state: TestPlanState | None = None,
    source: PrioritySource | None = None,
    exclude_fallback: bool = False,
    readiness: ReadinessLabel | None = None,
    benchmark_id: str | None = None,
    review_file: str | None = None,
) -> BenchmarkTestTriageReport:
    report = benchmark_tests_report(
        project_root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        facet=facet,
        state=state,
        source=source,
        exclude_fallback=exclude_fallback,
        readiness=readiness,
        benchmark_id=benchmark_id,
    )
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
        "filters": _benchmark_test_triage_filters(
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            facet=facet,
            state=state,
            source=source,
            exclude_fallback=exclude_fallback,
            readiness=readiness,
            benchmark_id=benchmark_id,
        ),
        "review_file": review_file,
        "commons_notice": report["commons_notice"],
    }
```

- [ ] **Step 6: Run report tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_bucket_assignment_is_ordered \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_buckets_and_preserves_summary_fields \
  science/tests/test_benchmark_opportunities.py::test_benchmark_test_triage_report_preserves_filtered_row_order_and_fallback_diagnostics \
  -q
```

Expected: PASS.

- [ ] **Step 7: Run focused benchmark opportunity tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -k "benchmark_test_triage or benchmark_tests_report" -q
```

Expected: PASS.

- [ ] **Step 8: Commit report projection**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): add test triage report"
```

---

## Task 2: CLI Command and Review Artifact

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

### Goal

Add `science benchmark test-triage` with table/json output and explicit YAML review-file writing.

- [ ] **Step 1: Add CLI test helper**

In `science/tests/test_benchmark_cli.py`, add this helper near `_invoke_tests`.

```python
def _invoke_test_triage(tmp_path: Path, *args: str):
    result = CliRunner().invoke(
        science_cli,
        ["benchmark", "test-triage", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )
    if result.exit_code == 0 and "--format" in args and args[args.index("--format") + 1] == "json":
        result.output_bytes = result.stdout_bytes
    return result
```

- [ ] **Step 2: Add failing CLI JSON and table tests**

Append these tests near the existing `benchmark tests` CLI tests in `science/tests/test_benchmark_cli.py`.

```python
def test_benchmark_test_triage_cli_json_output(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0200-perturbation",
        """
id: hypothesis:0200-perturbation
type: hypothesis
title: Perturbation response hypothesis
""",
        body="Drug perturbation should shift response states.",
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
  tasks:
    - id: compound-response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )

    result = _invoke_test_triage(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["review_file"] is None
    assert payload["summary"]["bucket_counts"]["run-now"] == 1
    assert payload["buckets"]["run-now"][0]["benchmark_id"] == "dataset:sciplex3"
    assert payload["buckets"]["run-now"][0]["review"] == {
        "decision": "",
        "owner": "",
        "next_action": "",
        "notes": "",
    }
    assert payload["filters"] == {}


def test_benchmark_test_triage_cli_table_output_shows_buckets(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0201-spatial",
        """
id: hypothesis:0201-spatial
type: hypothesis
title: Spatial hypothesis
""",
        body="Microenvironment region needs spatial validation.",
    )
    _write_dataset(
        tmp_path,
        "hca-spatial",
        """
id: dataset:hca-spatial
type: dataset
title: HCA Spatial
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke_test_triage(tmp_path)

    assert result.exit_code == 0
    assert "Benchmark Test Triage" in result.output
    assert "metadata-needed" in result.output
    assert "hypothesis:0201-spatial" in result.output
    assert "dataset:hca-spatial" in result.output
    assert "prediction-target" in result.output
```

- [ ] **Step 3: Add failing review-file tests**

Append these tests near the tests from Step 2.

```python
def test_benchmark_test_triage_cli_output_requires_write_flag(tmp_path: Path) -> None:
    result = _invoke_test_triage(tmp_path, "--output", "doc/audits/benchmark-test-triage/custom.yaml")

    assert result.exit_code != 0
    assert "--output requires --write-review-file" in result.output


def test_benchmark_test_triage_cli_runnable_only_conflicts_with_other_readiness(tmp_path: Path) -> None:
    result = _invoke_test_triage(tmp_path, "--runnable-only", "--readiness", "stage-needed")

    assert result.exit_code != 0
    assert "--runnable-only conflicts with --readiness stage-needed" in result.output


def test_benchmark_test_triage_cli_writes_default_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 1))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0202-perturbation",
        """
id: hypothesis:0202-perturbation
type: hypothesis
title: Perturbation response hypothesis
""",
        body="Drug perturbation should shift response states.",
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
  tasks:
    - id: compound-response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )

    result = _invoke_test_triage(tmp_path, "--write-review-file", "--format", "json")

    assert result.exit_code == 0
    review_path = tmp_path / "doc" / "audits" / "benchmark-test-triage" / f"2026-07-01-{tmp_path.name}.yaml"
    assert review_path.is_file()
    assert f"wrote benchmark test triage review file: {review_path}" in result.stderr
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    written = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    assert written["project"] == tmp_path.name
    assert written["generated_at"] == "2026-07-01"
    assert written["review_file"] == str(review_path)
    assert written["source_command"].startswith("science benchmark test-triage")
    assert written["summary"]["bucket_counts"]["run-now"] == 1
    assert written["buckets"]["run-now"][0]["review"]["decision"] == ""
    assert written["fallback_diagnostics"] == {"top_benchmarks": [], "top_facets": []}


def test_benchmark_test_triage_cli_refuses_existing_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 1))
    output_path = tmp_path / "doc" / "audits" / "benchmark-test-triage" / "custom.yaml"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("existing: true\n", encoding="utf-8")

    result = _invoke_test_triage(
        tmp_path,
        "--write-review-file",
        "--output",
        "doc/audits/benchmark-test-triage/custom.yaml",
    )

    assert result.exit_code != 0
    assert "review file already exists" in result.output
    assert output_path.read_text(encoding="utf-8") == "existing: true\n"


def test_benchmark_test_triage_cli_rejects_output_outside_project_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 1))

    relative_result = _invoke_test_triage(tmp_path, "--write-review-file", "--output", "../outside.yaml")
    assert relative_result.exit_code != 0
    assert "--output must stay under project root" in relative_result.output
    assert not (tmp_path.parent / "outside.yaml").exists()

    outside_path = tmp_path.parent / "outside-absolute.yaml"
    absolute_result = _invoke_test_triage(tmp_path, "--write-review-file", "--output", str(outside_path))
    assert absolute_result.exit_code != 0
    assert "--output must stay under project root" in absolute_result.output
    assert not outside_path.exists()
```

- [ ] **Step 4: Run CLI tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_json_output \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_buckets \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_output_requires_write_flag \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_runnable_only_conflicts_with_other_readiness \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_writes_default_review_file \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_refuses_existing_review_file \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_rejects_output_outside_project_root \
  -q
```

Expected: FAIL with Click reporting no such command `test-triage`, or missing `_benchmark_test_triage_today`.

- [ ] **Step 5: Add CLI helper functions**

In `science/src/science_tool/cli.py`, add these helpers after `_write_hint_candidates_review_file()`.

```python
def _benchmark_test_triage_today() -> date:
    return date.today()


def _default_test_triage_review_path(project_root: Path, generated: date) -> Path:
    from science_tool.paths import resolve_paths

    doc_dir = resolve_paths(project_root).doc_dir
    return (
        doc_dir
        / "audits"
        / "benchmark-test-triage"
        / f"{generated.isoformat()}-{project_root.name}.yaml"
    )


def _resolve_test_triage_output_path(project_root: Path, output_path: Path | None, generated: date) -> Path:
    root = project_root.resolve()
    if output_path is None:
        return _default_test_triage_review_path(root, generated)

    path = output_path if output_path.is_absolute() else root / output_path
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise click.ClickException(f"--output must stay under project root: {output_path}") from exc
    return resolved


def _test_triage_source_command(
    *,
    include_commons: bool,
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    state: str | None,
    priority_source: str | None,
    exclude_fallback: bool,
    readiness_label: str | None,
    runnable_only: bool,
    benchmark_ref: str | None,
    output_format: str,
) -> str:
    # Best-effort context string for review artifacts, not an exact shell history record.
    parts = ["science", "benchmark", "test-triage"]
    if include_commons:
        parts.append("--commons")
    if domain is not None:
        parts.extend(["--domain", domain])
    if entity_ref is not None:
        parts.extend(["--entity", entity_ref])
    if facet is not None:
        parts.extend(["--facet", facet])
    if state is not None:
        parts.extend(["--state", state])
    if priority_source is not None:
        parts.extend(["--source", priority_source])
    if exclude_fallback:
        parts.append("--exclude-fallback")
    if readiness_label is not None:
        parts.extend(["--readiness", readiness_label])
    if runnable_only:
        parts.append("--runnable-only")
    if benchmark_ref is not None:
        parts.extend(["--benchmark", benchmark_ref])
    if output_format != "table":
        parts.extend(["--format", output_format])
    parts.append("--write-review-file")
    return " ".join(parts)


def _write_test_triage_review_file(
    *,
    payload: Mapping[str, Any],
    project_root: Path,
    output_path: Path | None,
    generated: date,
    source_command: str,
) -> Path:
    path = _resolve_test_triage_output_path(project_root, output_path, generated)
    if path.exists():
        raise click.ClickException(f"review file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "project": project_root.name,
        "project_root": _display_project_path(project_root),
        "generated_at": generated.isoformat(),
        "review_file": str(path),
        "source_command": source_command,
        "filters": payload["filters"],
        "summary": payload["summary"],
        "buckets": payload["buckets"],
        "fallback_diagnostics": payload["fallback_diagnostics"],
        "commons_notice": payload["commons_notice"],
    }
    path.write_text(yaml.safe_dump(artifact, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
```

- [ ] **Step 6: Add table formatting helpers**

In `science/src/science_tool/cli.py`, add these helpers near `_format_gap_candidates_for_table()`.

```python
def _format_test_triage_task(row: Mapping[str, Any]) -> str:
    task_id = row.get("task_id")
    return str(task_id) if task_id else "-"


def _format_test_triage_needs(row: Mapping[str, Any]) -> str:
    needs = row.get("needs") or []
    return ", ".join(str(need) for need in needs) if needs else "-"


def _format_test_triage_facets(row: Mapping[str, Any]) -> str:
    facets = row.get("matched_facets") or []
    return ", ".join(str(facet) for facet in facets) if facets else "-"
```

- [ ] **Step 7: Add `benchmark test-triage` command**

In `science/src/science_tool/cli.py`, add the command after `benchmark_tests()`.

```python
@benchmark_group.command("test-triage")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--facet", default=None, help="Limit plans to a benchmark facet.")
@click.option("--state", type=click.Choice(["concrete", "draft-needed"]), default=None, help="Filter by test plan state.")
@click.option(
    "--source",
    "priority_source",
    type=click.Choice(["opportunity-relative", "gap-candidate", "gap-fallback"]),
    default=None,
    help="Filter by benchmark test priority source.",
)
@click.option("--exclude-fallback", is_flag=True, help="Drop broad fallback benchmark rows.")
@click.option(
    "--readiness",
    "readiness_label",
    type=click.Choice(["runnable", "stage-needed", "metadata-only", "blocked"]),
    default=None,
    help="Filter by benchmark runtime/readiness label.",
)
@click.option("--runnable-only", is_flag=True, help="Shortcut for --readiness runnable.")
@click.option("--benchmark", "benchmark_ref", default=None, help="Filter by benchmark dataset id or slug.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option("--write-review-file", is_flag=True, help="Write a YAML review artifact under the project root.")
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(path_type=Path, file_okay=True, dir_okay=False),
    help="Review artifact path. Relative paths are resolved under the project root.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_test_triage(
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    state: str | None,
    priority_source: str | None,
    exclude_fallback: bool,
    readiness_label: str | None,
    runnable_only: bool,
    benchmark_ref: str | None,
    include_commons: bool,
    write_review_file: bool,
    output_path: Path | None,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report benchmark test plans grouped for action triage."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import TestPlanState, benchmark_test_triage_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    if output_path is not None and not write_review_file:
        raise click.ClickException("--output requires --write-review-file")

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc
    if runnable_only and readiness_label not in {None, "runnable"}:
        raise click.ClickException(f"--runnable-only conflicts with --readiness {readiness_label}")

    try:
        payload = benchmark_test_triage_report(
            root,
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            facet=facet,
            state=cast("TestPlanState | None", state),
            source=cast("Any", priority_source),
            exclude_fallback=exclude_fallback,
            readiness="runnable" if runnable_only else cast("Any", readiness_label),
            benchmark_id=benchmark_ref,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    if write_review_file:
        generated = _benchmark_test_triage_today()
        review_path = _write_test_triage_review_file(
            payload=payload,
            project_root=root,
            output_path=output_path,
            generated=generated,
            source_command=_test_triage_source_command(
                include_commons=include_commons,
                domain=domain,
                entity_ref=entity_ref,
                facet=facet,
                state=state,
                priority_source=priority_source,
                exclude_fallback=exclude_fallback,
                readiness_label=readiness_label,
                runnable_only=runnable_only,
                benchmark_ref=benchmark_ref,
                output_format=output_format,
            ),
        )
        payload["review_file"] = str(review_path)
        click.echo(f"wrote benchmark test triage review file: {review_path}", err=True)

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    visible_rows = 0
    for bucket in ("run-now", "stage-next", "metadata-needed", "blocked-or-reference"):
        bucket_rows = payload["buckets"][bucket][:10]
        if not bucket_rows:
            continue
        table = Table(title=f"Benchmark Test Triage: {bucket}", show_header=True, header_style="bold")
        for col in ("entity", "benchmark", "task", "readiness", "score", "facets", "needs"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for row in bucket_rows:
            visible_rows += 1
            table.add_row(
                row["entity_id"],
                row["benchmark_id"],
                _format_test_triage_task(row),
                row["readiness_label"],
                str(row["priority_score"]),
                _format_test_triage_facets(row),
                _format_test_triage_needs(row),
            )
        Console(width=200).print(table)
    fallback_count = payload["summary"]["bucket_counts"]["fallback-diagnostic"]
    if fallback_count:
        diagnostics = payload["fallback_diagnostics"]
        table = Table(title="Benchmark Test Triage: fallback-diagnostic", show_header=True, header_style="bold")
        for col in ("rows", "top benchmarks", "top facets"):
            table.add_column(col, overflow="fold", no_wrap=False)
        table.add_row(
            f"{fallback_count} fallback rows",
            _format_count_rows(diagnostics["top_benchmarks"], key="benchmark_id"),
            _format_count_rows(diagnostics["top_facets"], key="facet"),
        )
        Console(width=200).print(table)
        visible_rows += 1
    if not visible_rows:
        click.echo("No benchmark test triage rows.")
        return
```

- [ ] **Step 8: Run focused CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_json_output \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_table_output_shows_buckets \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_output_requires_write_flag \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_runnable_only_conflicts_with_other_readiness \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_writes_default_review_file \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_refuses_existing_review_file \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_rejects_output_outside_project_root \
  -q
```

Expected: PASS.

- [ ] **Step 9: Add commons notice CLI test**

Append this test near the other `test-triage` CLI tests.

```python
def test_benchmark_test_triage_cli_json_and_commons_notice(tmp_path: Path) -> None:
    result = _invoke_test_triage(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["commons_notice"] is not None
    assert "notice: commons benchmarks unavailable" in result.stderr
```

- [ ] **Step 10: Run commons notice test**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_test_triage_cli_json_and_commons_notice \
  -q
```

Expected: PASS.

- [ ] **Step 11: Run focused benchmark CLI suite**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -k "benchmark_test_triage or benchmark_tests_cli or benchmark_hint_candidates_cli" -q
```

Expected: PASS.

- [ ] **Step 12: Commit CLI command**

Run:

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(benchmark): add test triage command"
```

---

## Task 3: Full Verification and Real-Project Smoke

**Files:**
- No production files expected.
- Optional local output only under `/tmp`.

### Goal

Verify the command against the focused test suite and inspect active project output without creating project review artifacts.

- [ ] **Step 1: Run full benchmark test suite**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run ruff**

Run:

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/benchmark_opportunities.py \
  science/src/science_tool/cli.py \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py
```

Expected: PASS.

- [ ] **Step 3: Smoke active projects without writing review files**

Run these commands. They must not use `--write-review-file`.

```bash
rtk uv run --frozen --project science science benchmark test-triage \
  --project-root ~/d/health/processes/post-acute-infection \
  --commons \
  --exclude-fallback \
  --format json > /tmp/pais-benchmark-test-triage.json

rtk uv run --frozen --project science science benchmark test-triage \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --exclude-fallback \
  --format json > /tmp/mm-benchmark-test-triage.json

rtk uv run --frozen --project science science benchmark test-triage \
  --project-root ~/d/natural-systems \
  --commons \
  --exclude-fallback \
  --format json > /tmp/natural-benchmark-test-triage.json

rtk uv run --frozen --project science science benchmark test-triage \
  --project-root ~/d/cancer/data-sources/cbioportal \
  --commons \
  --exclude-fallback \
  --format json > /tmp/cbioportal-benchmark-test-triage.json
```

Expected: each command exits 0 and writes JSON under `/tmp`. If a project has no rows after `--exclude-fallback`, that is acceptable; record it in the final handoff.

- [ ] **Step 4: Inspect smoke output summaries**

Run:

```bash
rtk uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path

for label, path in [
    ("pais", Path("/tmp/pais-benchmark-test-triage.json")),
    ("mm", Path("/tmp/mm-benchmark-test-triage.json")),
    ("natural", Path("/tmp/natural-benchmark-test-triage.json")),
    ("cbioportal", Path("/tmp/cbioportal-benchmark-test-triage.json")),
]:
    payload = json.loads(path.read_text())
    summary = payload["summary"]
    print(label)
    print("  bucket_counts:", summary["bucket_counts"])
    print("  readiness_counts:", summary["readiness_counts"])
    print("  top_facets:", summary["top_facets"][:5])
    for bucket in ["run-now", "stage-next", "metadata-needed", "blocked-or-reference"]:
        rows = payload["buckets"][bucket][:3]
        if rows:
            print(f"  {bucket}:")
            for row in rows:
                print(f"    {row['entity_id']} -> {row['benchmark_id']} ({row['readiness_label']}, {row['priority_score']})")
PY
```

Expected: readable summaries. Use these to judge whether `run-now` and `stage-next` are useful.

- [ ] **Step 5: Confirm no review artifacts were written**

Run:

```bash
rtk git status --short
```

Expected: only intended code/test changes are present before the final commit. No generated project YAML files should appear.

- [ ] **Step 6: Commit verification adjustments if needed**

If Task 3 required small code/test fixes, commit them:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
rtk git commit -m "test(benchmark): verify test triage report"
```

If no fixes were needed, skip this commit.

---

## Self-Review

### Spec Coverage

- New command `science benchmark test-triage`: Task 2.
- Same filters as `benchmark tests`: Task 2 command options and Task 1 report signature.
- Explicit `--write-review-file` and `--output`: Task 2.
- Canonical `doc/` review path and project-root escape checks: Task 2 helpers and tests.
- No overwrite behavior: Task 2 tests and helper.
- Ordered, first-match bucket assignment: Task 1 helper and tests.
- `draft-needed` + `stage-needed` precedence to `stage-next`: Task 1 test.
- Summary preserves `benchmark_tests_report()` fields and adds bucket/readiness counts: Task 1.
- Nullable `task_id`: Task 1 row projection inherits the existing nullable field; Task 2 table renders `-`.
- Fallback diagnostics summarized instead of row-dominating table output: Task 1 diagnostics and Task 2 table.
- Commons notice behavior: Task 2.
- Real-project smoke without generating project artifacts: Task 3.

### Placeholder Scan

No unresolved implementation placeholders remain. Human review fields intentionally use empty strings in the review artifact contract.

### Type Consistency

- Bucket literals are consistently named `run-now`, `stage-next`, `metadata-needed`, `blocked-or-reference`, and `fallback-diagnostic`.
- Report function is `benchmark_test_triage_report`.
- CLI command is `benchmark test-triage`.
- Review file helper names use `test_triage`, distinct from existing `hint_candidates` helpers.

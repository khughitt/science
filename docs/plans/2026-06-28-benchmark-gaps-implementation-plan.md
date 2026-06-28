# Benchmark Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `science benchmark gaps` report that projects existing benchmark opportunity output into uncovered, weak, and missing-facet gap rows.

**Architecture:** Keep all report assembly in `science_tool.benchmark_opportunities` and make it call `opportunity_report()` exactly once. The new command should not load entities, load datasets, or match facets directly in the CLI. The CLI only parses options, resolves `--entity`, delegates to `gaps_report()`, and renders JSON/table output.

**Tech Stack:** Python 3.12/3.13, Click, Rich, existing Science benchmark opportunity helpers, pytest/CliRunner, ruff, pyright.

---

## Design References

- `docs/plans/2026-06-28-benchmark-gaps-design.md`
- `docs/plans/2026-06-27-benchmark-opportunities-design.md`
- `science/src/science_tool/benchmark_opportunities.py`
- `science/src/science_tool/cli.py`
- `science/tests/test_benchmark_opportunities.py`

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add gap report `TypedDict` contracts.
  - Add `WEAK_RELATIVE_SCORE_THRESHOLD = 15`.
  - Add `gaps_report()` as a projection over `opportunity_report()`.
  - Add small pure helpers for grouping matches, candidate ordering, weak detection, summary counts, and optional facet filtering.
- Modify `science/src/science_tool/cli.py`
  - Add `science benchmark gaps`.
  - Reuse `resolve_entity_ref()` and commons notice handling from `benchmark opportunities`.
  - Render JSON and table output.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add direct report tests and CLI tests next to the existing opportunity tests, reusing local fixture helpers.

## Public JSON Contract

The command returns:

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
  "commons_notice": null
}
```

Each gap row contains:

```json
{
  "entity_id": "hypothesis:0005-dynamic-homeostasis",
  "entity_title": "Dynamic homeostasis predicts perturbation recovery",
  "gap_level": "weak",
  "missing_modalities": ["proteomics"],
  "missing_signal_types": ["time-series"],
  "current_matches": [
    {
      "benchmark_id": "dataset:hca-spatial",
      "task_id": null,
      "relative_score": 20,
      "baseline_score": 41
    }
  ],
  "candidate_benchmarks": [
    {
      "benchmark_id": "dataset:cptac-proteogenomics",
      "benchmark_title": "CPTAC proteogenomics",
      "baseline_score": 78,
      "matched_missing_facets": []
    }
  ],
  "suggested_search_facets": ["proteomics", "time-series"],
  "reason": "Matched benchmarks are taskless or below the weak relative-score threshold."
}
```

Rows are sorted by `gap_level` precedence (`uncovered`, `weak`, `missing-facet`), then `entity_id`.

In v1, `matched_missing_facets` is expected to remain empty under the exact
facet matcher. Keep the field for forward compatibility, but treat
`suggested_search_facets` as the actionable missing-facet signal and candidate
benchmarks as baseline-ranked context.

---

### Task 1: Direct Gap Projection Report

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing tests for uncovered and missing-facet projection**

Append these tests to `science/tests/test_benchmark_opportunities.py`:

```python
def test_gaps_report_projects_uncovered_entities_and_candidate_benchmarks(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-unmapped",
        """
id: hypothesis:0001-unmapped
type: hypothesis
title: Homeostatic recovery has no benchmark yet
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "atlas",
        """
id: dataset:atlas
type: dataset
title: Atlas Benchmark
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  tasks:
    - id: transfer
      prediction_target: region label
      held_out_unit: tissue
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: curated region
""",
    )

    payload = gaps_report(tmp_path)

    assert payload["summary"] == {
        "entities_total": 1,
        "entities_with_gaps": 1,
        "uncovered_entities": 1,
        "weakly_covered_entities": 0,
        "missing_facet_entities": 0,
    }
    row = payload["benchmark_gaps"][0]
    assert row["entity_id"] == "hypothesis:0001-unmapped"
    assert row["gap_level"] == "uncovered"
    assert row["missing_modalities"] == []
    assert row["missing_signal_types"] == []
    assert row["current_matches"] == []
    assert row["candidate_benchmarks"][0]["benchmark_id"] == "dataset:atlas"
    assert row["candidate_benchmarks"][0]["matched_missing_facets"] == []


def test_gaps_report_projects_existing_coverage_gaps_as_missing_facet(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial-proteomics",
        """
id: hypothesis:0002-spatial-proteomics
type: hypothesis
title: Spatial proteomics transfer
""",
        body="Spatial proteomics transfer should generalize.",
    )
    _write_dataset(
        tmp_path,
        "spatial",
        """
id: dataset:spatial
type: dataset
title: Spatial Atlas
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  tasks:
    - id: transfer
      prediction_target: region label
      held_out_unit: tissue
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: curated region
""",
    )
    _write_dataset(
        tmp_path,
        "unrelated",
        """
id: dataset:unrelated
type: dataset
title: Unrelated Benchmark
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: response
      prediction_target: response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured response
""",
    )

    payload = gaps_report(tmp_path)

    row = payload["benchmark_gaps"][0]
    assert row["gap_level"] == "missing-facet"
    assert row["missing_modalities"] == ["proteomics"]
    assert row["missing_signal_types"] == []
    assert row["suggested_search_facets"] == ["proteomics"]
    assert row["candidate_benchmarks"][0]["benchmark_id"] == "dataset:unrelated"
    assert row["candidate_benchmarks"][0]["matched_missing_facets"] == []
```

- [ ] **Step 2: Run the red checks**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gaps_report_projects_uncovered_entities_and_candidate_benchmarks science/tests/test_benchmark_opportunities.py::test_gaps_report_projects_existing_coverage_gaps_as_missing_facet -q
```

Expected: FAIL with an import error because `gaps_report` does not exist.

- [ ] **Step 3: Add the gap report contracts and projection helpers**

In `science/src/science_tool/benchmark_opportunities.py`, add these contracts after `OpportunityReport`:

```python
WEAK_RELATIVE_SCORE_THRESHOLD = 15


class GapCurrentMatchRow(TypedDict):
    benchmark_id: str
    task_id: str | None
    relative_score: int
    baseline_score: int


class GapCandidateBenchmarkRow(TypedDict):
    benchmark_id: str
    benchmark_title: str
    baseline_score: int
    matched_missing_facets: list[str]


class BenchmarkGapRow(TypedDict):
    entity_id: str
    entity_title: str
    gap_level: str
    missing_modalities: list[str]
    missing_signal_types: list[str]
    current_matches: list[GapCurrentMatchRow]
    candidate_benchmarks: list[GapCandidateBenchmarkRow]
    suggested_search_facets: list[str]
    reason: str


class BenchmarkGapSummary(TypedDict):
    entities_total: int
    entities_with_gaps: int
    uncovered_entities: int
    weakly_covered_entities: int
    missing_facet_entities: int


class BenchmarkGapReport(TypedDict):
    benchmark_gaps: list[BenchmarkGapRow]
    summary: BenchmarkGapSummary
    commons_notice: str | None
```

Add these pure helpers near `_coverage_gaps()`:

```python
def _gap_level_sort_key(level: str) -> int:
    order = {"uncovered": 0, "weak": 1, "missing-facet": 2}
    return order[level]


def _matched_by_entity(rows: list[OpportunityRow]) -> dict[str, list[OpportunityRow]]:
    grouped: dict[str, list[OpportunityRow]] = {}
    for row in rows:
        grouped.setdefault(row["entity_id"], []).append(row)
    return grouped


def _coverage_gap_by_entity(rows: list[CoverageGapRow]) -> dict[str, CoverageGapRow]:
    return {row["entity_id"]: row for row in rows}


def _entity_title_map(report: OpportunityReport) -> dict[str, str]:
    titles: dict[str, str] = {}
    for row in report["matched_opportunities"]:
        titles.setdefault(row["entity_id"], row["entity_title"])
    for row in report["unmapped_project_entities"]:
        titles.setdefault(row["entity_id"], row["entity_title"])
    return titles


def _current_match_rows(rows: list[OpportunityRow]) -> list[GapCurrentMatchRow]:
    return [
        {
            "benchmark_id": row["benchmark_id"],
            "task_id": row["task_id"],
            "relative_score": row["relative_score"],
            "baseline_score": row["baseline_score"],
        }
        for row in rows
    ]


def _is_weak_gap(rows: list[OpportunityRow]) -> bool:
    if not rows:
        return False
    all_low_score = all(row["relative_score"] < WEAK_RELATIVE_SCORE_THRESHOLD for row in rows)
    all_taskless = all(row["task_id"] is None for row in rows)
    return all_low_score or all_taskless


def _candidate_rows(
    available: list[UnmappedBenchmarkRow],
    missing_facets: set[str],
) -> list[GapCandidateBenchmarkRow]:
    candidates: list[GapCandidateBenchmarkRow] = []
    for row in available:
        candidate_facets = {_normalize_token(value) for value in row["unmapped_facets"]}
        matched_facets = sorted(candidate_facets & missing_facets)
        candidates.append(
            {
                "benchmark_id": row["benchmark_id"],
                "benchmark_title": row["benchmark_title"],
                "baseline_score": row["baseline_score"],
                "matched_missing_facets": matched_facets,
            }
        )
    return sorted(
        candidates,
        key=lambda row: (-len(row["matched_missing_facets"]), -row["baseline_score"], row["benchmark_id"]),
    )


def _gap_summary(rows: list[BenchmarkGapRow], entities_total: int) -> BenchmarkGapSummary:
    return {
        "entities_total": entities_total,
        "entities_with_gaps": len(rows),
        "uncovered_entities": sum(1 for row in rows if row["gap_level"] == "uncovered"),
        "weakly_covered_entities": sum(1 for row in rows if row["gap_level"] == "weak"),
        "missing_facet_entities": sum(1 for row in rows if row["gap_level"] == "missing-facet"),
    }
```

- [ ] **Step 4: Implement `gaps_report()`**

Add this function after `opportunity_report()`:

```python
def gaps_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    facet: str | None = None,
) -> BenchmarkGapReport:
    opportunity = opportunity_report(
        project_root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
    )
    matched = _matched_by_entity(opportunity["matched_opportunities"])
    coverage = _coverage_gap_by_entity(opportunity["coverage_gaps"])
    titles = _entity_title_map(opportunity)
    unmapped_ids = {row["entity_id"] for row in opportunity["unmapped_project_entities"]}
    entity_ids = sorted(set(matched) | set(coverage) | unmapped_ids)

    rows: list[BenchmarkGapRow] = []
    normalized_facet = _normalize_token(facet) if facet is not None else None
    for current_entity_id in entity_ids:
        current_matches = matched.get(current_entity_id, [])
        gap = coverage.get(current_entity_id)
        missing_modalities = list(gap["missing_modalities"]) if gap is not None else []
        missing_signal_types = list(gap["missing_signal_types"]) if gap is not None else []
        missing_facets = {_normalize_token(value) for value in missing_modalities + missing_signal_types}

        if current_entity_id in unmapped_ids:
            gap_level = "uncovered"
            reason = "No matched benchmark opportunities for this entity."
        elif _is_weak_gap(current_matches):
            gap_level = "weak"
            reason = "Matched benchmarks are taskless or below the weak relative-score threshold."
        elif gap is not None:
            gap_level = "missing-facet"
            reason = gap["reason"]
        else:
            continue

        if normalized_facet is not None and normalized_facet not in missing_facets:
            continue

        rows.append(
            {
                "entity_id": current_entity_id,
                "entity_title": titles.get(current_entity_id, current_entity_id),
                "gap_level": gap_level,
                "missing_modalities": missing_modalities,
                "missing_signal_types": missing_signal_types,
                "current_matches": _current_match_rows(current_matches),
                "candidate_benchmarks": _candidate_rows(
                    opportunity["available_unmapped_benchmarks"],
                    missing_facets,
                ),
                "suggested_search_facets": sorted(missing_facets),
                "reason": reason,
            }
        )

    rows.sort(key=lambda row: (_gap_level_sort_key(row["gap_level"]), row["entity_id"]))
    return {
        "benchmark_gaps": rows,
        "summary": _gap_summary(rows, entities_total=len(entity_ids)),
        "commons_notice": opportunity["commons_notice"],
    }
```

- [ ] **Step 5: Run the projection tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gaps_report_projects_uncovered_entities_and_candidate_benchmarks science/tests/test_benchmark_opportunities.py::test_gaps_report_projects_existing_coverage_gaps_as_missing_facet -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): project opportunity gaps"
```

Expected: commit succeeds.

---

### Task 2: Weak Precedence and Facet Filtering Regression Locks

**Files:**
- Modify: `science/tests/test_benchmark_opportunities.py`
- Modify: `science/src/science_tool/benchmark_opportunities.py`

- [ ] **Step 1: Add regression tests for weak precedence and direct facet filtering**

Append:

```python
def test_gaps_report_prefers_weak_over_missing_facet(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0003-taskless-spatial-proteomics",
        """
id: hypothesis:0003-taskless-spatial-proteomics
type: hypothesis
title: Spatial proteomics taskless coverage
""",
        body="Spatial proteomics transfer remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "spatial-facets",
        """
id: dataset:spatial-facets
type: dataset
title: Spatial Facets
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  limitations:
    - Facets only.
""",
    )
    _write_dataset(
        tmp_path,
        "unrelated-task",
        """
id: dataset:unrelated-task
type: dataset
title: Unrelated Task
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: response
      prediction_target: response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured response
""",
    )

    payload = gaps_report(tmp_path)

    row = payload["benchmark_gaps"][0]
    assert row["gap_level"] == "weak"
    assert row["missing_modalities"] == ["proteomics"]
    assert row["suggested_search_facets"] == ["proteomics"]
    assert row["candidate_benchmarks"][0]["benchmark_id"] == "dataset:unrelated-task"


def test_gaps_report_filters_by_high_value_facet(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-temporal",
        """
id: hypothesis:0004-temporal
type: hypothesis
title: Time-series missing gap
""",
        body="Time-series dynamics remain untested.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0005-proteomics",
        """
id: hypothesis:0005-proteomics
type: hypothesis
title: Proteomics missing gap
""",
        body="Proteomics transfer remains untested.",
    )

    payload = gaps_report(tmp_path, facet="time-series")

    assert [row["entity_id"] for row in payload["benchmark_gaps"]] == ["hypothesis:0004-temporal"]
    assert payload["summary"]["entities_total"] == 2
    assert payload["summary"]["entities_with_gaps"] == 1
```

- [ ] **Step 2: Run the regression checks**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gaps_report_prefers_weak_over_missing_facet science/tests/test_benchmark_opportunities.py::test_gaps_report_filters_by_high_value_facet -q
```

Expected: PASS after Task 1. These are green-on-arrival regression locks for
the precedence and filtering behavior already implemented in Task 1.

- [ ] **Step 3: Fix any implementation mismatch**

If the tests fail after Task 1, adjust only the gap projection helpers. Keep these invariants:

```python
if current_entity_id in unmapped_ids:
    gap_level = "uncovered"
elif _is_weak_gap(current_matches):
    gap_level = "weak"
elif gap is not None:
    gap_level = "missing-facet"
else:
    continue
```

and:

```python
if normalized_facet is not None and normalized_facet not in missing_facets:
    continue
```

- [ ] **Step 4: Run all direct benchmark opportunity tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "test(benchmark): lock gap precedence"
```

Expected: commit succeeds. If no production code changed in this task, keep the test-only commit.

---

### Task 3: CLI Command

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add a gaps CLI helper and JSON test**

Add this helper near `_invoke()`:

```python
def _invoke_gaps(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "gaps", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )
```

Append:

```python
def test_benchmark_gaps_cli_json_output(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0006-proteomics",
        """
id: hypothesis:0006-proteomics
type: hypothesis
title: Proteomics gap
""",
        body="Proteomics coverage is missing.",
    )

    result = _invoke_gaps(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["benchmark_gaps"][0]["gap_level"] == "uncovered"
    assert payload["benchmark_gaps"][0]["missing_modalities"] == ["proteomics"]
    assert payload["summary"]["entities_with_gaps"] == 1
```

- [ ] **Step 2: Add CLI tests for table empty state, facet filtering, and invalid entity**

Append:

```python
def test_benchmark_gaps_cli_table_empty_state(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0007-covered",
        """
id: hypothesis:0007-covered
type: hypothesis
title: Spatial covered
""",
        body="Spatial transfer is covered.",
    )
    _write_dataset(
        tmp_path,
        "spatial-covered",
        """
id: dataset:spatial-covered
type: dataset
title: Spatial Covered
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  tasks:
    - id: transfer
      prediction_target: region label
      held_out_unit: tissue
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: curated region
""",
    )

    result = _invoke_gaps(tmp_path)

    assert result.exit_code == 0
    assert "No benchmark gaps." in result.output


def test_benchmark_gaps_cli_facet_filter(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0008-proteomics",
        """
id: hypothesis:0008-proteomics
type: hypothesis
title: Proteomics gap
""",
        body="Proteomics coverage is missing.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0009-temporal",
        """
id: hypothesis:0009-temporal
type: hypothesis
title: Time-series gap
""",
        body="Time-series coverage is missing.",
    )

    result = _invoke_gaps(tmp_path, "--facet", "time-series", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [row["entity_id"] for row in payload["benchmark_gaps"]] == ["hypothesis:0009-temporal"]


def test_benchmark_gaps_cli_invalid_entity_uses_click_error(tmp_path: Path) -> None:
    result = _invoke_gaps(tmp_path, "--entity", "hypothesis:nope")

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "hypothesis:nope" in result.output
```

- [ ] **Step 3: Run the CLI red checks**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_json_output science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_table_empty_state science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_facet_filter science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_invalid_entity_uses_click_error -q
```

Expected: FAIL because `benchmark gaps` is not registered.

- [ ] **Step 4: Implement the CLI command**

In `science/src/science_tool/cli.py`, add this command near `benchmark_opportunities`:

```python
@benchmark_group.command("gaps")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--facet", default=None, help="Limit gaps to a high-value missing benchmark facet.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
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
def benchmark_gaps(
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    include_commons: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report benchmark coverage gaps for project entities."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import GAP_MODALITIES, GAP_SIGNAL_TYPES, gaps_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    valid_facets = sorted(set(GAP_MODALITIES + GAP_SIGNAL_TYPES))
    if facet is not None and facet not in valid_facets:
        raise click.ClickException(f"Invalid facet {facet!r}. Choose one of: {', '.join(valid_facets)}")

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc

    payload = gaps_report(
        root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        facet=facet,
    )
    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    rows = payload["benchmark_gaps"]
    if not rows:
        click.echo("No benchmark gaps.")
        return

    table = Table(title="Benchmark Gaps", show_header=True, header_style="bold")
    for col in ("entity", "level", "missing facets", "matches", "candidates", "reason"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        missing = ", ".join(row["missing_modalities"] + row["missing_signal_types"]) or "-"
        candidates = ", ".join(candidate["benchmark_id"] for candidate in row["candidate_benchmarks"][:3]) or "-"
        table.add_row(
            row["entity_id"],
            row["gap_level"],
            missing,
            str(len(row["current_matches"])),
            candidates,
            row["reason"],
        )
    Console(width=200).print(table)
```

- [ ] **Step 5: Run the CLI checks**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_json_output science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_table_empty_state science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_facet_filter science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_invalid_entity_uses_click_error -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(cli): report benchmark gaps"
```

Expected: commit succeeds.

---

### Task 4: Commons Degradation, Validation, and Smoke

**Files:**
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add commons degradation test for gaps**

Append:

```python
def test_benchmark_gaps_cli_reports_commons_notice(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0010-proteomics",
        """
id: hypothesis:0010-proteomics
type: hypothesis
title: Proteomics commons gap
""",
        body="Proteomics coverage is missing.",
    )

    result = _invoke_gaps(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    assert "notice: commons benchmarks unavailable" in result.stderr
    payload = json.loads(result.output)
    assert payload["commons_notice"] is not None
```

- [ ] **Step 2: Run the commons test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_gaps_cli_reports_commons_notice -q
```

Expected: PASS.

- [ ] **Step 3: Run the benchmark opportunity suite**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 4: Run lint and type checks**

Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk uv run --frozen --project science pyright science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
```

Expected: both commands PASS.

- [ ] **Step 5: Run a real-project smoke test**

Run if the project exists locally:

```bash
rtk uv run --frozen --project science science benchmark gaps --project-root ~/d/health/comparisons/pan-disease --commons --domain biology --format json
```

Expected: command exits 0, prints JSON with `benchmark_gaps`, `summary`, and `commons_notice`.

- [ ] **Step 6: Commit Task 4 if tests or docs changed**

Run only if Task 4 required changes:

```bash
rtk git add science/tests/test_benchmark_opportunities.py
rtk git commit -m "test(benchmark): cover gap commons notice"
```

Expected: commit succeeds if there were staged changes.

---

## Final Verification

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk uv run --frozen --project science pyright science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk git diff --check
```

Expected: all commands pass.

## Self-Review Checklist

- `gaps_report()` calls `opportunity_report()` once and does not re-load entities or datasets.
- `GAP_MODALITIES` and `GAP_SIGNAL_TYPES` are reused as the only public high-value facet vocabulary.
- Gap-level precedence is `uncovered > weak > missing-facet`.
- `--facet` is used instead of `--kind`.
- JSON contains all fields in the public contract.
- Table output remains a concise projection of JSON.
- Commons notice behavior matches `science benchmark opportunities`.
- No mutating behavior is introduced.

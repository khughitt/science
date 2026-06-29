# Benchmark Gap Calibration Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `science benchmark gap-calibration` command that runs benchmark gap calibration summaries across multiple project roots.

**Architecture:** Keep `gaps_report()` and `gap_calibration_summary()` as the single-project source of truth. Add a small batch projection helper in `benchmark_opportunities.py`, then expose it through a sibling CLI command under `science benchmark`.

**Tech Stack:** Python 3.13, Click, Rich tables, pytest, ruff.

---

## Files

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add typed rows for batch project specs, per-project summaries, aggregate summaries, and the full batch payload.
  - Add `benchmark_gap_calibration_batch(projects, include_commons=False, domain=None, facet=None)`.
  - Add `_display_path()` for `~/d/`-style rendered roots.
- Modify `science/src/science_tool/cli.py`
  - Add `science benchmark gap-calibration`.
  - Parse repeatable `--project label=path` inputs.
  - Render JSON and table output.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add direct helper coverage for batch aggregation and commons notices.
- Modify `science/tests/test_benchmark_cli.py`
  - Add CLI parsing, JSON, and table coverage.
- Keep this plan and the design doc under `docs/plans/`.

## Task 1: Batch Helper Contract

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Write a failing helper test**

Add this test near the existing gap calibration summary tests:

```python
def test_gap_calibration_batch_summarizes_multiple_projects(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_gap_calibration_batch

    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    _write_entity(
        project_a,
        "hypotheses",
        "0001-drug",
        """
id: hypothesis:0001-drug
type: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )
    _write_dataset(
        project_a,
        "sciplex",
        """
id: dataset:sciplex
type: dataset
title: Sci-Plex
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )
    _write_entity(
        project_b,
        "hypotheses",
        "0002-temporal",
        """
id: hypothesis:0002-temporal
type: hypothesis
title: Temporal benchmark gap
""",
        body="Temporal dynamic measurements should be tested.",
    )

    payload = benchmark_gap_calibration_batch(
        [
            ("a", project_a),
            ("b", project_b),
        ]
    )

    assert [row["label"] for row in payload["projects"]] == ["a", "b"]
    assert payload["aggregate"]["project_count"] == 2
    assert payload["aggregate"]["gap_rows"] == 2
    assert payload["aggregate"]["entity_specific_candidate_rows"] == 1
    assert payload["aggregate"]["fallback_candidate_rows"] == 0
    assert payload["aggregate"]["fallback_candidate_ratio"] == 0.0
    assert payload["aggregate"]["top_suggested_facets"][0] == {"facet": "perturbation", "count": 1}
    assert payload["aggregate"]["top_matched_hint_facets"] == [{"facet": "perturbation", "count": 1}]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gap_calibration_batch_summarizes_multiple_projects -q
```

Expected: FAIL because `benchmark_gap_calibration_batch` is not defined.

- [ ] **Step 3: Implement typed payloads and the helper**

Add typed rows below `GapCalibrationSummary`:

```python
class GapCalibrationProjectRow(TypedDict):
    label: str
    project_root: str
    summary: BenchmarkGapSummary
    calibration_summary: GapCalibrationSummary
    commons_notice: str | None


class GapCalibrationAggregate(TypedDict):
    project_count: int
    gap_rows: int
    candidate_rows: int
    entity_specific_candidate_rows: int
    fallback_candidate_rows: int
    fallback_candidate_ratio: float | None
    top_suggested_facets: list[FacetCountRow]
    top_matched_hint_facets: list[FacetCountRow]
    top_fallback_benchmarks: list[BenchmarkCountRow]


class GapCalibrationCommonsNotice(TypedDict):
    label: str
    notice: str


class GapCalibrationBatchReport(TypedDict):
    projects: list[GapCalibrationProjectRow]
    aggregate: GapCalibrationAggregate
    commons_notices: list[GapCalibrationCommonsNotice]
```

Add helper functions:

```python
def _display_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    home_d = (Path.home() / "d").resolve()
    try:
        return f"~/d/{resolved.relative_to(home_d).as_posix()}"
    except ValueError:
        return str(resolved)


def _merge_top_facets(rows: list[BenchmarkGapRow], *, top: int) -> tuple[list[FacetCountRow], list[FacetCountRow]]:
    suggested = Counter(facet for row in rows for facet in row["suggested_search_facets"])
    matched = Counter(
        facet
        for row in rows
        for candidate in row["candidate_benchmarks"]
        for facet in candidate["matched_hint_facets"]
    )
    return _top_facet_counts(suggested, top=top), _top_facet_counts(matched, top=top)


def _fallback_benchmark_counts(rows: list[BenchmarkGapRow], *, top: int) -> list[BenchmarkCountRow]:
    fallback = Counter(
        candidate["benchmark_id"]
        for row in rows
        for candidate in row["candidate_benchmarks"]
        if candidate["reason_notes"] == ["high-baseline-fallback"]
    )
    return _top_benchmark_counts(fallback, top=top)
```

Add the public helper:

```python
def benchmark_gap_calibration_batch(
    projects: list[tuple[str, Path]],
    *,
    include_commons: bool = False,
    domain: str | None = None,
    facet: str | None = None,
    top: int = 10,
) -> GapCalibrationBatchReport:
    project_rows: list[GapCalibrationProjectRow] = []
    notices: list[GapCalibrationCommonsNotice] = []
    all_gap_rows: list[BenchmarkGapRow] = []
    for label, project_root in projects:
        report = gaps_report(
            project_root,
            include_commons=include_commons,
            domain=domain,
            facet=facet,
        )
        summary = gap_calibration_summary(report, top=top)
        notice = report["commons_notice"]
        if notice:
            notices.append({"label": label, "notice": notice})
        project_rows.append(
            {
                "label": label,
                "project_root": _display_path(project_root),
                "summary": report["summary"],
                "calibration_summary": summary,
                "commons_notice": notice,
            }
        )
        all_gap_rows.extend(report["benchmark_gaps"])

    gap_rows = sum(row["calibration_summary"]["gap_rows"] for row in project_rows)
    candidate_rows = sum(row["calibration_summary"]["candidate_rows"] for row in project_rows)
    entity_specific = sum(row["calibration_summary"]["entity_specific_candidate_rows"] for row in project_rows)
    fallback = sum(row["calibration_summary"]["fallback_candidate_rows"] for row in project_rows)
    top_suggested, top_matched = _merge_top_facets(all_gap_rows, top=top)
    return {
        "projects": project_rows,
        "aggregate": {
            "project_count": len(project_rows),
            "gap_rows": gap_rows,
            "candidate_rows": candidate_rows,
            "entity_specific_candidate_rows": entity_specific,
            "fallback_candidate_rows": fallback,
            "fallback_candidate_ratio": round(fallback / candidate_rows, 3) if candidate_rows else None,
            "top_suggested_facets": top_suggested,
            "top_matched_hint_facets": top_matched,
            "top_fallback_benchmarks": _fallback_benchmark_counts(all_gap_rows, top=top),
        },
        "commons_notices": notices,
    }
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gap_calibration_batch_summarizes_multiple_projects -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py docs/plans/2026-06-28-benchmark-gap-calibration-batch-design.md docs/plans/2026-06-28-benchmark-gap-calibration-batch-implementation-plan.md
rtk git commit -m "feat(benchmark): add gap calibration batch helper"
```

## Task 2: CLI JSON Contract

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add CLI fixture helpers and failing JSON test**

Add helper functions to `science/tests/test_benchmark_cli.py`:

```python
def _write_entity(root: Path, folder: str, slug: str, frontmatter: str, *, body: str) -> None:
    path = root / "entities" / folder / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}\n", encoding="utf-8")


def _invoke_gap_calibration(*args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "gap-calibration", *args],
        catch_exceptions=False,
        env={"SCIENCE_COMMONS_ROOT": "/tmp/science-no-commons"},
    )
```

Add the failing test:

```python
def test_benchmark_gap_calibration_json_summarizes_projects(tmp_path: Path) -> None:
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    _write_entity(
        project_a,
        "hypotheses",
        "0001-drug",
        """
id: hypothesis:0001-drug
type: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )
    _write_dataset(
        project_a,
        "sciplex",
        """
id: dataset:sciplex
type: dataset
title: Sci-Plex
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )
    _write_entity(
        project_b,
        "hypotheses",
        "0002-temporal",
        """
id: hypothesis:0002-temporal
type: hypothesis
title: Temporal benchmark gap
""",
        body="Temporal dynamic measurements should be tested.",
    )

    result = _invoke_gap_calibration(
        "--project",
        f"a={project_a}",
        "--project",
        f"b={project_b}",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [row["label"] for row in payload["projects"]] == ["a", "b"]
    assert payload["aggregate"]["project_count"] == 2
    assert payload["aggregate"]["entity_specific_candidate_rows"] == 1
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_gap_calibration_json_summarizes_projects -q
```

Expected: FAIL because the command does not exist.

- [ ] **Step 3: Implement CLI parsing and JSON output**

Add a parser helper near `benchmark_gaps`:

```python
def _parse_project_specs(project_specs: tuple[str, ...]) -> list[tuple[str, Path]]:
    if not project_specs:
        raise click.ClickException("at least one --project label=path is required")
    parsed: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for spec in project_specs:
        if "=" not in spec:
            raise click.ClickException("--project must use label=path")
        label, raw_path = spec.split("=", 1)
        label = label.strip()
        if not label:
            raise click.ClickException("--project label must be non-empty")
        if label in seen:
            raise click.ClickException(f"duplicate --project label: {label}")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            raise click.ClickException(f"--project {label} path does not exist: {path}")
        seen.add(label)
        parsed.append((label, path))
    return parsed
```

Add the command:

```python
@benchmark_group.command("gap-calibration")
@click.option("--project", "project_specs", multiple=True, help="Project as label=path. Repeat for each project.")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--facet", default=None, help="Limit gaps to a high-value missing benchmark facet.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def benchmark_gap_calibration(
    project_specs: tuple[str, ...],
    domain: str | None,
    facet: str | None,
    include_commons: bool,
    output_format: str,
) -> None:
    """Summarize benchmark gap calibration across projects."""
    from science_tool.benchmark_opportunities import benchmark_gap_calibration_batch

    projects = _parse_project_specs(project_specs)
    try:
        payload = benchmark_gap_calibration_batch(
            projects,
            include_commons=include_commons,
            domain=domain,
            facet=facet,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_gap_calibration_json_summarizes_projects -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(cli): add benchmark gap calibration json"
```

## Task 3: CLI Table and Validation

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing CLI validation and table tests**

Add:

```python
def test_benchmark_gap_calibration_rejects_duplicate_project_labels(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = _invoke_gap_calibration("--project", f"demo={project}", "--project", f"demo={project}")

    assert result.exit_code != 0
    assert "duplicate --project label: demo" in result.output


def test_benchmark_gap_calibration_table_renders_sections(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_entity(
        project,
        "hypotheses",
        "0001-drug",
        """
id: hypothesis:0001-drug
type: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )

    result = _invoke_gap_calibration("--project", f"demo={project}")

    assert result.exit_code == 0
    assert "Benchmark Gap Calibration" in result.output
    assert "Aggregate Benchmark Gap Calibration" in result.output
    assert "demo" in result.output
```

- [ ] **Step 2: Run the focused tests and verify table output fails**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_gap_calibration_rejects_duplicate_project_labels science/tests/test_benchmark_cli.py::test_benchmark_gap_calibration_table_renders_sections -q
```

Expected: duplicate-label test PASS, table test FAIL because table rendering is not implemented.

- [ ] **Step 3: Implement table output**

Extend `benchmark_gap_calibration` after the JSON branch:

```python
    from rich.console import Console
    from rich.table import Table

    table = Table(title="Benchmark Gap Calibration", show_header=True, header_style="bold")
    for col in (
        "project",
        "gap rows",
        "entity candidates",
        "fallback candidates",
        "fallback ratio",
        "suggested facets",
        "matched facets",
        "fallback benchmarks",
    ):
        table.add_column(col, overflow="fold", no_wrap=False)
    for project in payload["projects"]:
        summary = project["calibration_summary"]
        ratio = "-"
        if summary["candidate_rows"]:
            ratio = f"{summary['fallback_candidate_rows'] / summary['candidate_rows']:.3f}"
        table.add_row(
            project["label"],
            str(summary["gap_rows"]),
            str(summary["entity_specific_candidate_rows"]),
            str(summary["fallback_candidate_rows"]),
            ratio,
            _format_count_rows(summary["top_suggested_facets"], key="facet"),
            _format_count_rows(summary["top_matched_hint_facets"], key="facet"),
            _format_count_rows(summary["top_fallback_benchmarks"], key="benchmark_id"),
        )
    Console(width=200).print(table)

    aggregate_table = Table(title="Aggregate Benchmark Gap Calibration", show_header=True, header_style="bold")
    aggregate_table.add_column("field", overflow="fold", no_wrap=False)
    aggregate_table.add_column("value", overflow="fold", no_wrap=False)
    aggregate = payload["aggregate"]
    for field in (
        "project_count",
        "gap_rows",
        "candidate_rows",
        "entity_specific_candidate_rows",
        "fallback_candidate_rows",
        "fallback_candidate_ratio",
    ):
        aggregate_table.add_row(field, str(aggregate[field]))
    aggregate_table.add_row("top_suggested_facets", _format_count_rows(aggregate["top_suggested_facets"], key="facet"))
    aggregate_table.add_row("top_matched_hint_facets", _format_count_rows(aggregate["top_matched_hint_facets"], key="facet"))
    aggregate_table.add_row("top_fallback_benchmarks", _format_count_rows(aggregate["top_fallback_benchmarks"], key="benchmark_id"))
    Console(width=200).print(aggregate_table)
```

Add the formatter helper near `_parse_project_specs`:

```python
def _format_count_rows(rows: list[dict[str, object]], *, key: str) -> str:
    values = [f"{row[key]}:{row['count']}" for row in rows]
    return ", ".join(values) if values else "-"
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_gap_calibration_rejects_duplicate_project_labels science/tests/test_benchmark_cli.py::test_benchmark_gap_calibration_table_renders_sections -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(cli): render benchmark gap calibration table"
```

## Task 4: Commons Notice Coverage and Verification

**Files:**
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add a commons degradation test**

Add:

```python
def test_gap_calibration_batch_preserves_commons_notices(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.benchmark_opportunities import benchmark_gap_calibration_batch

    project = tmp_path / "project"
    project.mkdir()
    _write_entity(
        project,
        "hypotheses",
        "0001-drug",
        """
id: hypothesis:0001-drug
type: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))

    payload = benchmark_gap_calibration_batch([("demo", project)], include_commons=True)

    assert payload["projects"][0]["commons_notice"] is not None
    assert payload["commons_notices"] == [
        {"label": "demo", "notice": payload["projects"][0]["commons_notice"]}
    ]
```

- [ ] **Step 2: Run the focused test and verify it passes or fails for the expected reason**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gap_calibration_batch_preserves_commons_notices -q
```

Expected: PASS if Task 1 already preserved notices; otherwise FAIL because the notice is not included.

- [ ] **Step 3: Fix notice projection if needed**

If the test fails because notices are absent, update `benchmark_gap_calibration_batch()` so every non-empty `report["commons_notice"]` appends `{"label": label, "notice": notice}` to `commons_notices`.

- [ ] **Step 4: Run ruff and focused tests**

Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected:

- Ruff exits 0.
- Pytest reports 59+ passing tests.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "test(benchmark): cover gap calibration commons notices"
```

## Task 5: Real-Project Smoke

**Files:**
- No source changes expected.

- [ ] **Step 1: Run the command on the active project set**

Run:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark gap-calibration \
  --project pai=~/d/health/processes/post-acute-infection \
  --project mm=~/d/cancer/cancer-types/multiple-myeloma \
  --project natural=~/d/natural-systems \
  --project cbioportal=~/d/cancer/data-sources/cbioportal \
  --commons \
  --format json
```

Expected: exit 0, JSON includes four project rows and aggregate counts.

- [ ] **Step 2: Inspect the aggregate signal**

Confirm the payload exposes:

- `aggregate.fallback_candidate_ratio`
- `aggregate.top_suggested_facets`
- `aggregate.top_matched_hint_facets`
- `aggregate.top_fallback_benchmarks`

- [ ] **Step 3: Commit any doc correction only if the smoke reveals a contract mismatch**

If no docs change is needed, do not commit.


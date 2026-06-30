# Benchmark Hint Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science benchmark hint-candidates`, a read-only benchmark facet hint review report with an explicit YAML review artifact write path.

**Architecture:** `science_tool.benchmark_opportunities` owns the report contract and projects over `gaps_report(..., evidence_report=True)` without re-tokenizing text. `science_tool.cli` remains a thin command layer for option parsing, table/JSON rendering, commons notice handling, and explicit review-file writes. The default terminal view shows only actionable domain candidates; JSON and review artifacts include all evidence-derived categories, plus existing hints only when `--include-existing` is passed.

**Tech Stack:** Python 3.11, Click, Rich, PyYAML, pytest, existing `science_tool` benchmark report helpers.

---

## Pre-Execution Notes

- Create an isolated worktree before implementation, for example:

```bash
rtk git worktree add .worktrees/benchmark-hint-candidates -b benchmark-hint-candidates
```

- Work from `.worktrees/benchmark-hint-candidates`.
- Preserve the unrelated untracked file in the main worktree: `docs/audits/plans-cleanup/batches/june-003.md`.
- The design file currently has local edits that tighten `reason_notes` and `suggested_facets`; keep implementation aligned with those semantics.
- Use scoped `git add` commands in each task. Do not use `git add -A`.

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add typed report contract for hint candidates.
  - Add deterministic row projection helpers.
  - Add public `benchmark_hint_candidates_report(...)`.
- Modify `science/src/science_tool/cli.py`
  - Add `science benchmark hint-candidates`.
  - Add review-file path/date helpers.
  - Render table/JSON and write YAML only with `--write-review-file`.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add report-level tests for projection, counts, reason notes, existing hints, and `min_count`.
- Modify `science/tests/test_benchmark_cli.py`
  - Add command-level tests for JSON, table, commons notice, write artifact, output validation, and no-results behavior.
- No schema or commons data changes are part of this tranche.

---

### Task 1: Core Hint Candidate Report

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing report projection tests**

Append these tests near the existing evidence-report tests in `science/tests/test_benchmark_opportunities.py`:

```python
def test_hint_candidates_report_projects_evidence_categories_and_reason_notes(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import (
        HINT_CANDIDATE_TRUNCATION_NOTICE,
        TERM_BUCKET_CAP,
        benchmark_hint_candidates_report,
    )

    project_root = tmp_path / "cbioportal-project"
    project_root.mkdir()
    for index in range(3):
        _write_entity(
            project_root,
            "hypotheses",
            f"005{index}-alpha",
            f"""
id: hypothesis:005{index}-alpha
type: hypothesis
title: Cytogenetic lesion model {index}
""",
            body="Cytogenetic lesion mutation evidence should be benchmarked against project catalog models.",
        )
    _write_dataset(
        project_root,
        "generic",
        """
id: dataset:generic
type: dataset
title: Generic Benchmark
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

    payload = benchmark_hint_candidates_report(project_root)

    rows = payload["hint_candidates"]
    by_term = {row["term"]: row for row in rows}
    assert {"cytogenetic", "lesion", "mutation"} <= set(by_term)
    assert by_term["cytogenetic"]["count"] == 3
    assert by_term["cytogenetic"]["category"] == "domain-candidate"
    assert by_term["cytogenetic"]["current_hint"] is None
    assert by_term["cytogenetic"]["suggested_action"] == "review-for-hint"
    assert by_term["cytogenetic"]["suggested_facets"] == []
    assert by_term["cytogenetic"]["reason_notes"] == [
        "unmapped-domain-term",
        "frequent-term",
        "fallback-heavy-project",
    ]
    assert "cbioportal" in {row["term"] for row in rows if row["category"] == "project-local"}
    assert {"catalog", "models"} <= {row["term"] for row in rows if row["category"] == "workflow-or-modeling"}
    assert payload["summary"]["domain_candidate_terms"] >= 3
    assert payload["summary"]["project_local_terms"] >= 1
    assert payload["summary"]["workflow_or_modeling_terms"] >= 2
    assert payload["summary"]["existing_hint_terms"] == 0
    assert payload["summary"]["term_bucket_cap"] == TERM_BUCKET_CAP
    assert payload["summary"]["truncation_notice"] == HINT_CANDIDATE_TRUNCATION_NOTICE
    assert payload["summary"]["fallback_only_gap_rows"] == 3
    assert payload["summary"]["entity_specific_gap_rows"] == 0
    assert payload["review_file"] is None


def test_hint_candidates_report_filters_min_count_within_capped_evidence_rows(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_hint_candidates_report

    for index in range(2):
        _write_entity(
            tmp_path,
            "hypotheses",
            f"006{index}-alpha",
            f"""
id: hypothesis:006{index}-alpha
type: hypothesis
title: Cytogenetic signal {index}
""",
            body="Cytogenetic lesion evidence should be reviewed.",
        )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0069-beta",
        """
id: hypothesis:0069-beta
type: hypothesis
title: Rare signal
""",
        body="Epigenetic marker evidence should be reviewed.",
    )

    payload = benchmark_hint_candidates_report(tmp_path, min_count=2)

    terms = {row["term"] for row in payload["hint_candidates"]}
    assert "cytogenetic" in terms
    assert "lesion" in terms
    assert "epigenetic" not in terms
    assert "marker" not in terms


def test_hint_candidates_report_existing_hints_are_directly_enumerated_when_requested(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import FACET_HINT_TERMS, benchmark_hint_candidates_report

    payload = benchmark_hint_candidates_report(tmp_path, include_existing=True, min_count=99)

    rows = [row for row in payload["hint_candidates"] if row["category"] == "existing-hint"]
    by_term = {row["term"]: row for row in rows}
    assert set(by_term) == set(FACET_HINT_TERMS)
    assert by_term["drug"]["count"] is None
    assert by_term["drug"]["current_hint"] == "perturbation"
    assert by_term["drug"]["suggested_action"] == "already-mapped"
    assert by_term["drug"]["suggested_facets"] == []
    assert by_term["drug"]["example_entities"] == []
    assert by_term["drug"]["reason_notes"] == ["already-mapped-term"]
    assert payload["summary"]["existing_hint_terms"] == len(FACET_HINT_TERMS)


def test_hint_candidates_report_rejects_invalid_min_count(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_hint_candidates_report

    with pytest.raises(ValueError, match="min_count must be at least 1"):
        benchmark_hint_candidates_report(tmp_path, min_count=0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_projects_evidence_categories_and_reason_notes science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_filters_min_count_within_capped_evidence_rows science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_existing_hints_are_directly_enumerated_when_requested science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_rejects_invalid_min_count -q
```

Expected: FAIL because `benchmark_hint_candidates_report`, `TERM_BUCKET_CAP`, and `HINT_CANDIDATE_TRUNCATION_NOTICE` do not exist.

- [ ] **Step 3: Add report types, constants, and projection helpers**

In `science/src/science_tool/benchmark_opportunities.py`, add these constants near the existing benchmark facet constants:

```python
TERM_BUCKET_CAP = 10
FREQUENT_TERM_COUNT = 3
HINT_CANDIDATE_TRUNCATION_NOTICE = "evidence categories are capped at top 10 terms per bucket"
```

Add these type aliases and typed dicts after `BenchmarkGapReport`:

```python
HintCandidateCategory = Literal["domain-candidate", "project-local", "workflow-or-modeling", "existing-hint"]
HintCandidateAction = Literal["review-for-hint", "project-local-or-alias", "not-a-benchmark-facet", "already-mapped"]


class HintCandidateRow(TypedDict):
    term: str
    count: int | None
    category: HintCandidateCategory
    current_hint: str | None
    suggested_action: HintCandidateAction
    suggested_facets: list[str]
    example_entities: list[str]
    reason_notes: list[str]


class HintCandidateSummary(TypedDict):
    candidate_terms: int
    domain_candidate_terms: int
    project_local_terms: int
    workflow_or_modeling_terms: int
    existing_hint_terms: int
    term_bucket_cap: int
    truncation_notice: str
    fallback_only_gap_rows: int
    entity_specific_gap_rows: int


class HintCandidatesReport(TypedDict):
    project_root: str
    summary: HintCandidateSummary
    hint_candidates: list[HintCandidateRow]
    review_file: str | None
    commons_notice: str | None
```

Add these helpers near `_term_categories(...)`:

```python
def _hint_candidate_reason_notes(
    *,
    category: HintCandidateCategory,
    count: int | None,
    fallback_heavy: bool,
) -> list[str]:
    notes: list[str] = []
    if category == "domain-candidate":
        notes.append("unmapped-domain-term")
    elif category == "project-local":
        notes.append("project-local-term")
    elif category == "workflow-or-modeling":
        notes.append("workflow-or-modeling-term")
    elif category == "existing-hint":
        notes.append("already-mapped-term")
    if count is not None and count >= FREQUENT_TERM_COUNT:
        notes.append("frequent-term")
    if fallback_heavy:
        notes.append("fallback-heavy-project")
    return notes


def _hint_candidate_from_term_row(
    row: TermCountRow,
    *,
    category: HintCandidateCategory,
    fallback_heavy: bool,
) -> HintCandidateRow:
    if category == "domain-candidate":
        action: HintCandidateAction = "review-for-hint"
    elif category == "project-local":
        action = "project-local-or-alias"
    elif category == "workflow-or-modeling":
        action = "not-a-benchmark-facet"
    else:
        action = "already-mapped"
    count = row["count"]
    return {
        "term": row["term"],
        "count": count,
        "category": category,
        "current_hint": None,
        "suggested_action": action,
        "suggested_facets": [],
        "example_entities": list(row["example_entities"]),
        "reason_notes": _hint_candidate_reason_notes(category=category, count=count, fallback_heavy=fallback_heavy),
    }


def _existing_hint_candidate_rows(*, fallback_heavy: bool) -> list[HintCandidateRow]:
    return [
        {
            "term": term,
            "count": None,
            "category": "existing-hint",
            "current_hint": facet,
            "suggested_action": "already-mapped",
            "suggested_facets": [],
            "example_entities": [],
            "reason_notes": _hint_candidate_reason_notes(
                category="existing-hint",
                count=None,
                fallback_heavy=fallback_heavy,
            ),
        }
        for term, facet in sorted(FACET_HINT_TERMS.items())
    ]


def _hint_candidate_sort_key(row: HintCandidateRow) -> tuple[int, int, str]:
    category_order: dict[HintCandidateCategory, int] = {
        "domain-candidate": 0,
        "project-local": 1,
        "workflow-or-modeling": 2,
        "existing-hint": 3,
    }
    count = row["count"] if row["count"] is not None else -1
    return (category_order[row["category"]], -count, row["term"])


def _hint_candidate_rows_from_evidence(
    evidence: EvidenceReport,
    *,
    min_count: int,
    include_existing: bool,
    fallback_heavy: bool,
) -> list[HintCandidateRow]:
    if not evidence["enabled"]:
        raise ValueError("benchmark gap evidence report must be enabled")
    categories = evidence["term_categories"]
    rows: list[HintCandidateRow] = []
    category_sources: tuple[tuple[TermCategory, HintCandidateCategory], ...] = (
        ("domain_candidate_terms", "domain-candidate"),
        ("project_local_terms", "project-local"),
        ("workflow_or_modeling_terms", "workflow-or-modeling"),
    )
    for source_key, category in category_sources:
        for term_row in categories[source_key]:
            if term_row["count"] >= min_count:
                rows.append(
                    _hint_candidate_from_term_row(term_row, category=category, fallback_heavy=fallback_heavy)
                )
    if include_existing:
        rows.extend(_existing_hint_candidate_rows(fallback_heavy=fallback_heavy))
    rows.sort(key=_hint_candidate_sort_key)
    return rows


def _hint_candidate_summary(rows: list[HintCandidateRow], gap_summary: BenchmarkGapSummary) -> HintCandidateSummary:
    return {
        "candidate_terms": len(rows),
        "domain_candidate_terms": sum(1 for row in rows if row["category"] == "domain-candidate"),
        "project_local_terms": sum(1 for row in rows if row["category"] == "project-local"),
        "workflow_or_modeling_terms": sum(1 for row in rows if row["category"] == "workflow-or-modeling"),
        "existing_hint_terms": sum(1 for row in rows if row["category"] == "existing-hint"),
        "term_bucket_cap": TERM_BUCKET_CAP,
        "truncation_notice": HINT_CANDIDATE_TRUNCATION_NOTICE,
        "fallback_only_gap_rows": gap_summary["gap_candidate_mode_counts"]["fallback-only"],
        "entity_specific_gap_rows": gap_summary["gap_candidate_mode_counts"]["entity-specific"],
    }
```

- [ ] **Step 4: Add the public report function**

Add this function near `gaps_report(...)`:

```python
def benchmark_hint_candidates_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    domain: str | None = None,
    min_count: int = 1,
    include_existing: bool = False,
    review_file: str | None = None,
) -> HintCandidatesReport:
    if min_count < 1:
        raise ValueError("min_count must be at least 1")

    gap_payload = gaps_report(
        project_root,
        include_commons=include_commons,
        domain=domain,
        evidence_report=True,
    )
    gap_summary = gap_payload["summary"]
    fallback_heavy = (
        gap_summary["gap_candidate_mode_counts"]["fallback-only"]
        > gap_summary["gap_candidate_mode_counts"]["entity-specific"]
    )
    rows = _hint_candidate_rows_from_evidence(
        gap_payload["evidence_report"],
        min_count=min_count,
        include_existing=include_existing,
        fallback_heavy=fallback_heavy,
    )
    return {
        "project_root": str(project_root),
        "summary": _hint_candidate_summary(rows, gap_summary),
        "hint_candidates": rows,
        "review_file": review_file,
        "commons_notice": gap_payload["commons_notice"],
    }
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_projects_evidence_categories_and_reason_notes science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_filters_min_count_within_capped_evidence_rows science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_existing_hints_are_directly_enumerated_when_requested science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_rejects_invalid_min_count -q
```

Expected: PASS.

- [ ] **Step 6: Run adjacent benchmark opportunity tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gaps_report_evidence_report_explains_fallback_only_unmapped_terms science/tests/test_benchmark_opportunities.py::test_gaps_report_evidence_report_categorizes_unmapped_terms_without_redefining_lexicon_candidates science/tests/test_benchmark_opportunities.py::test_term_categories_are_disjoint_and_project_local_uses_leaf_not_ancestors -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): add hint candidates report"
```

---

### Task 2: CLI JSON and Table Command

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing CLI tests for JSON, table, and validation**

Add this helper near the other `_invoke_*` helpers in `science/tests/test_benchmark_cli.py`:

```python
def _invoke_hint_candidates(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "hint-candidates", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )
```

Append these tests near the benchmark gaps CLI tests:

```python
def test_benchmark_hint_candidates_cli_json_and_commons_notice(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0070-alpha",
        """
id: hypothesis:0070-alpha
type: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    assert "notice: commons benchmarks unavailable" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["commons_notice"] is not None
    assert payload["review_file"] is None
    assert payload["summary"]["term_bucket_cap"] == 10
    assert payload["summary"]["truncation_notice"] == "evidence categories are capped at top 10 terms per bucket"
    assert {row["term"] for row in payload["hint_candidates"]} >= {"cytogenetic", "lesion", "mutation"}
    assert all(row["suggested_facets"] == [] for row in payload["hint_candidates"])
    assert all(row["suggested_action"] != "needs-new-facet-vocab" for row in payload["hint_candidates"])


def test_benchmark_hint_candidates_cli_table_shows_only_domain_candidates(tmp_path: Path) -> None:
    project_root = tmp_path / "cbioportal-project"
    project_root.mkdir()
    _write_entity(
        project_root,
        "hypotheses",
        "0071-alpha",
        """
id: hypothesis:0071-alpha
type: hypothesis
title: Cytogenetic project model
""",
        body="Cytogenetic lesion evidence should be benchmarked against project catalog models.",
    )

    result = _invoke_hint_candidates(project_root)

    assert result.exit_code == 0
    assert "Benchmark Hint Candidates" in result.output
    assert "cytogenetic" in result.output
    assert "review-for-hint" in result.output
    assert "catalog" not in result.output
    assert "cbioportal" not in result.output


def test_benchmark_hint_candidates_cli_include_existing_json(tmp_path: Path) -> None:
    result = _invoke_hint_candidates(tmp_path, "--include-existing", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    existing = [row for row in payload["hint_candidates"] if row["category"] == "existing-hint"]
    assert existing
    by_term = {row["term"]: row for row in existing}
    assert by_term["drug"]["count"] is None
    assert by_term["drug"]["current_hint"] == "perturbation"
    assert by_term["drug"]["example_entities"] == []
    assert by_term["drug"]["reason_notes"] == ["already-mapped-term"]


def test_benchmark_hint_candidates_cli_output_requires_write_flag(tmp_path: Path) -> None:
    result = _invoke_hint_candidates(tmp_path, "--output", "docs/audits/benchmark-hint-candidates/custom.yaml")

    assert result.exit_code != 0
    assert "--output requires --write-review-file" in result.output


def test_benchmark_hint_candidates_cli_table_empty_state(tmp_path: Path) -> None:
    result = _invoke_hint_candidates(tmp_path)

    assert result.exit_code == 0
    assert "No benchmark hint candidates." in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_json_and_commons_notice science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_table_shows_only_domain_candidates science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_include_existing_json science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_output_requires_write_flag science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_table_empty_state -q
```

Expected: FAIL because `benchmark hint-candidates` is not registered.

- [ ] **Step 3: Add table formatter**

In `science/src/science_tool/cli.py`, add this helper near `_format_gap_candidates_for_table(...)`:

```python
def _format_hint_candidate_count(row: Mapping[str, Any]) -> str:
    count = row["count"]
    return "-" if count is None else str(count)


def _hint_candidate_table_rows(rows: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if row["category"] == "domain-candidate"]
```

- [ ] **Step 4: Add the command**

Add this command before `benchmark_gaps(...)` in `science/src/science_tool/cli.py`:

```python
@benchmark_group.command("hint-candidates")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option("--min-count", default=1, type=click.IntRange(min=1), show_default=True, help="Minimum visible term count.")
@click.option("--include-existing", is_flag=True, help="Include terms already mapped by the benchmark hint lexicon.")
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
def benchmark_hint_candidates(
    domain: str | None,
    include_commons: bool,
    min_count: int,
    include_existing: bool,
    write_review_file: bool,
    output_path: Path | None,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report candidate terms for benchmark facet hint review."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import benchmark_hint_candidates_report

    if output_path is not None and not write_review_file:
        raise click.ClickException("--output requires --write-review-file")

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        payload = benchmark_hint_candidates_report(
            root,
            include_commons=include_commons,
            domain=domain,
            min_count=min_count,
            include_existing=include_existing,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    rows = _hint_candidate_table_rows(payload["hint_candidates"])
    if not rows:
        click.echo("No benchmark hint candidates.")
        return

    table = Table(title="Benchmark Hint Candidates", show_header=True, header_style="bold")
    for col in ("term", "count", "action", "suggested facets", "examples"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        table.add_row(
            row["term"],
            _format_hint_candidate_count(row),
            row["suggested_action"],
            ", ".join(row["suggested_facets"]) or "-",
            ", ".join(row["example_entities"]) or "-",
        )
    Console(width=200).print(table)
```

- [ ] **Step 5: Run focused CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_json_and_commons_notice science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_table_shows_only_domain_candidates science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_include_existing_json science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_output_requires_write_flag science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_table_empty_state -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(benchmark): add hint candidates cli"
```

---

### Task 3: Review Artifact Write Path

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing review-file tests**

Add `from datetime import date` and `import yaml` to `science/tests/test_benchmark_cli.py` if they are not already present.

Append these tests near the hint-candidates CLI tests:

```python
def test_benchmark_hint_candidates_cli_writes_default_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0072-alpha",
        """
id: hypothesis:0072-alpha
type: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(tmp_path, "--write-review-file", "--format", "json")

    assert result.exit_code == 0
    review_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    assert review_path.is_file()
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    written = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    assert written["project"] == tmp_path.name
    assert written["generated_at"] == "2026-06-30"
    assert written["source_command"].startswith("science benchmark hint-candidates")
    assert written["summary"]["term_bucket_cap"] == 10
    assert written["candidates"][0]["decision"] == "pending"
    assert written["candidates"][0]["reviewer_notes"] == ""
    assert written["candidates"][0]["suggested_facets"] == []


def test_benchmark_hint_candidates_cli_writes_custom_project_relative_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0073-alpha",
        """
id: hypothesis:0073-alpha
type: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(
        tmp_path,
        "--write-review-file",
        "--output",
        "docs/audits/benchmark-hint-candidates/custom.yaml",
    )

    assert result.exit_code == 0
    review_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / "custom.yaml"
    assert review_path.is_file()
    assert f"wrote benchmark hint candidate review file: {review_path}" in result.stderr


def test_benchmark_hint_candidates_cli_refuses_existing_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    output_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / "custom.yaml"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("existing: true\n", encoding="utf-8")

    result = _invoke_hint_candidates(
        tmp_path,
        "--write-review-file",
        "--output",
        "docs/audits/benchmark-hint-candidates/custom.yaml",
    )

    assert result.exit_code != 0
    assert "review file already exists" in result.output
    assert output_path.read_text(encoding="utf-8") == "existing: true\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_writes_default_review_file science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_writes_custom_project_relative_review_file science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_refuses_existing_review_file -q
```

Expected: FAIL because `_benchmark_hint_candidates_today` and review-file writing do not exist.

- [ ] **Step 3: Add review artifact helpers**

In `science/src/science_tool/cli.py`, add these helpers near the hint-candidates table helpers:

```python
def _benchmark_hint_candidates_today() -> date:
    return date.today()


def _display_project_path(path: Path) -> str:
    resolved = path.resolve()
    home = Path.home().resolve()
    try:
        return "~/" + str(resolved.relative_to(home))
    except ValueError:
        return str(resolved)


def _default_hint_candidates_review_path(project_root: Path, generated: date) -> Path:
    return (
        project_root
        / "docs"
        / "audits"
        / "benchmark-hint-candidates"
        / f"{generated.isoformat()}-{project_root.name}.yaml"
    )


def _resolve_hint_candidates_output_path(project_root: Path, output_path: Path | None, generated: date) -> Path:
    if output_path is None:
        return _default_hint_candidates_review_path(project_root, generated)
    return output_path if output_path.is_absolute() else project_root / output_path


def _hint_candidates_source_command(
    *,
    include_commons: bool,
    domain: str | None,
    min_count: int,
    include_existing: bool,
    output_format: str,
) -> str:
    # Best-effort context string for review artifacts, not an exact shell history record.
    parts = ["science", "benchmark", "hint-candidates"]
    if include_commons:
        parts.append("--commons")
    if domain is not None:
        parts.extend(["--domain", domain])
    if min_count != 1:
        parts.extend(["--min-count", str(min_count)])
    if include_existing:
        parts.append("--include-existing")
    if output_format != "table":
        parts.extend(["--format", output_format])
    parts.append("--write-review-file")
    return " ".join(parts)


def _write_hint_candidates_review_file(
    *,
    payload: Mapping[str, Any],
    project_root: Path,
    output_path: Path | None,
    generated: date,
    source_command: str,
) -> Path:
    path = _resolve_hint_candidates_output_path(project_root, output_path, generated)
    if path.exists():
        raise click.ClickException(f"review file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "project": project_root.name,
        "project_root": _display_project_path(project_root),
        "generated_at": generated.isoformat(),
        "source_command": source_command,
        "summary": payload["summary"],
        "candidates": [
            {
                **row,
                "decision": "pending",
                "reviewer_notes": "",
            }
            for row in payload["hint_candidates"]
        ],
    }
    path.write_text(yaml.safe_dump(artifact, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
```

- [ ] **Step 4: Wire review writing into the command**

Replace the report call block in `benchmark_hint_candidates(...)` with this final flow:

```python
    generated = _benchmark_hint_candidates_today()
    review_file: str | None = None
    try:
        payload = benchmark_hint_candidates_report(
            root,
            include_commons=include_commons,
            domain=domain,
            min_count=min_count,
            include_existing=include_existing,
        )
        if write_review_file:
            review_path = _write_hint_candidates_review_file(
                payload=payload,
                project_root=root,
                output_path=output_path,
                generated=generated,
                source_command=_hint_candidates_source_command(
                    include_commons=include_commons,
                    domain=domain,
                    min_count=min_count,
                    include_existing=include_existing,
                    output_format=output_format,
                ),
            )
            review_file = str(review_path)
            payload = {**payload, "review_file": review_file}
            click.echo(f"wrote benchmark hint candidate review file: {review_path}", err=True)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
```

Keep the existing commons notice, JSON rendering, and table rendering after this block.

- [ ] **Step 5: Run review-file tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_writes_default_review_file science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_writes_custom_project_relative_review_file science/tests/test_benchmark_cli.py::test_benchmark_hint_candidates_cli_refuses_existing_review_file -q
```

Expected: PASS.

- [ ] **Step 6: Run all hint-candidates CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -q -k "hint_candidates"
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(benchmark): write hint candidate review files"
```

---

### Task 4: Full Verification and Real-Project Smoke Check

**Files:**
- Modify: none expected
- Test: benchmark test suites and real-project command output

- [ ] **Step 1: Run focused benchmark test suites**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint on touched files**

Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

Expected: PASS.

- [ ] **Step 3: Run command against an active project without writing**

Run:

```bash
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/cancer/cancer-types/multiple-myeloma
```

Expected: command exits 0, prints either a `Benchmark Hint Candidates` table or `No benchmark hint candidates.`, and does not create a new review YAML file under `~/d/cancer/cancer-types/multiple-myeloma/docs/audits/benchmark-hint-candidates/`.

- [ ] **Step 4: Run JSON smoke against the same project**

Run:

```bash
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/cancer/cancer-types/multiple-myeloma --format json
```

Expected: JSON contains `summary.term_bucket_cap`, `summary.truncation_notice`, `hint_candidates`, `review_file: null`, and `commons_notice`.

- [ ] **Step 5: Inspect changed files**

Run:

```bash
rtk git diff --stat
rtk git diff -- science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

Expected: diff only contains the hint-candidates report, CLI, and tests.

- [ ] **Step 6: Commit final verification notes if any test-only adjustments were needed**

If Task 4 required no code changes, skip this commit. If a small verification fix was needed, commit only touched benchmark files:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
rtk git commit -m "test(benchmark): verify hint candidates command"
```

---

## Self-Review

- **Spec coverage:** The plan covers the read-only default report, projection over `gaps_report(..., evidence_report=True)`, `--domain`, `--commons`, `--project-root`, `--min-count`, `--include-existing`, table/JSON output, explicit review-file writes, `--output` validation, existing-file failure, deterministic date seam, capped evidence buckets, reason notes, empty `suggested_facets`, and no automatic hint mutation.
- **Known interpretation:** JSON and review artifacts include domain, project-local, and workflow/modeling evidence rows. The default terminal table filters to `domain-candidate` rows so non-actionable categories do not dominate the normal view.
- **Placeholder scan:** The plan contains no undefined implementation placeholders. Every new public helper, type, option, and test assertion is specified.
- **Type consistency:** `HintCandidateRow.count` is `int | None` so existing-hint rows can use `null`; `current_hint` is non-null only for `existing-hint`; `suggested_action` excludes `needs-new-facet-vocab`; `suggested_facets` is always `[]` in v1.
- **Risk note:** The source evidence remains capped at top 10 per category. The command documents that cap in summary fields and does not request a wider evidence report API.

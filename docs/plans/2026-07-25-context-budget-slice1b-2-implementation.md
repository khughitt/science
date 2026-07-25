# Context Budget — Slice 1b-2 (wire the REPORT/DOCUMENT offenders) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the four remaining measured-over-budget commands under the context budget: `curate inventory` (a versioned DOCUMENT that must refuse past budget) and the three REPORT-shaped commands `prose lint`, `curate consolidation-candidates`, and `validate` (a summary plus one or more growable finding lists, projected per section like `health`).

**Architecture:** Slice 1a built the machinery and `health` (REPORT) + `entities inventory` (DOCUMENT) are the shipped reference patterns. A DOCUMENT command renders its whole payload into a `BoundedSink` and flushes: `flush()` refuses (raises `BudgetExceeded`, printing nothing) when stdout exceeds the ceiling, while `--output PATH` is always complete. A REPORT command builds its full report, computes `displayed = full if output_path else project_<cmd>(full)` with a bespoke per-command projection that caps each growable list and records what it dropped, renders through `sink.console`/`sink.echo` (never raw `click.echo`/`get_console`), appends a "showing N of M … complete_via" footer when it projected, then `emit(..., sink=sink)` + `sink.flush()`. Summary counts and exit codes always derive from the FULL result, never the projected one.

**Tech Stack:** Python 3.11, Click, Rich, pytest.

## Global Constraints

- **Python floor is 3.11** — no PEP 695 syntax (`class Foo[T]`, `def f[T]()`); use `TypeVar` + `Generic`.
- **`stdout is always budgeted; `--output PATH` is always complete.`** Projection never runs against a file sink (`BoundedSink.max_rows` returns `None` for a file sink; a REPORT command guards `displayed = full if output_path is not None else project_<cmd>(full)`).
- **A DOCUMENT is never partially emitted.** No projection; the whole payload is rendered and `flush()` refuses past budget. Dropping records from a versioned document would corrupt it.
- **Summary counts and exit codes use the FULL result.** Projection narrows only what is displayed. `validate` exits nonzero on the full result's errors/gated; `prose lint --strict` exits on the full hit list. Mirrors `health`'s `total_issues`, which is copied through untouched.
- **Conventional commits.** No AI-attribution trailer/footer on commits, PRs, or comments.
- **Use `~/d/` or relative paths** in docs and code, never absolute `/home/...` or `/mnt/...`.
- **Composition over inheritance; explicit over defensive; fail early, no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.**
- **Run tests from `science/`:** `cd science && uv run --frozen pytest`. Lint: `uv run ruff check`. Types: `uv run pyright`. Per the AGENTS.md note, run a scoped selection during iteration — the full suite (~10k tests) exceeds the 120s default command timeout; reserve the full run for the end and give it an explicit long timeout.
- **The registry partition is asserted.** `tests/test_budget_boundary.py::EXPECTED_CLASSIFICATION_COUNTS` starts at `{"budgeted": 10, "exempt": 67, "deferred": 201}`. Every task that moves a key from `DEFERRED` to `BUDGETS` MUST update this dict in the same commit. Final state after this slice: `{"budgeted": 14, "exempt": 67, "deferred": 197}`.
- **The measured-offenders test is fully discharged by this slice.** `tests/test_budget_registry.py::test_the_remaining_measured_offenders_are_deferred` asserts `measured <= set(DEFERRED)` over exactly these four commands. Each task removes its command from that `measured` set; the final task deletes the now-empty test (Task 5).

## Boundary guards every wired command must satisfy

Two AST/tree guards in `tests/test_budget_boundary.py` run over `BUDGETS` automatically:

1. `test_every_budgeted_command_constructs_its_own_sink` — the command's **own callback body** (not a nested function/lambda/comprehension) must contain a `BoundedSink(...)` call.
2. `test_every_budgeted_command_offers_the_output_escape` — the command must expose a `--output` option.

## Reference patterns (read before starting)

- **DOCUMENT:** `science/src/science_tool/entities_inventory_cli.py::entities_inventory_command` (lines ~50-79).
- **REPORT:** `science/src/science_tool/graph/health_cli.py::health_command` and its bespoke projector `science/src/science_tool/graph/health_projection.py::project_health_report` (note `SECTION_ROW_CAP = 40`, the `section_omitted`/`displayed_issues` recording, and that `--output` skips projection entirely).
- **The sink API:** `science/src/science_tool/budget/sink.py` — `sink.console` (Rich, at budget width), `sink.echo(str)`, `sink.write(str)`, `sink.complete_via`, `flush()` (refuses past `max_chars` for a stdout sink; writes the file for a file sink).
- **emit routing:** `science/src/science_tool/output.py::emit` — the JSON branch does `sink.echo(json.dumps(payload, ...))`, so **projection must record any omission INSIDE `payload`**; the text branch calls `render_text()`, which must write only through the sink.

---

## Task 1: Wire `curate inventory` (DOCUMENT) and create the regression module

**Files:**
- Modify: `science/src/science_tool/budget/registry.py` (move `curate inventory` DEFERRED→BUDGETS)
- Modify: `science/src/science_tool/curate/cli.py:16-46` (the `inventory_cmd` callback)
- Modify: `science/tests/test_budget_boundary.py` (bump partition to 11/67/200)
- Modify: `science/tests/test_budget_registry.py` (drop `"curate inventory"` from the measured set)
- Create: `science/tests/test_budget_regression_reports.py` (new module + shared helpers for this slice)

**Interfaces:**
- Consumes from slice 1a: `BoundedSink(budget, *, output_path, command_path, complete_via)`; `budget.registry.lookup`; `budget.invocation.build_complete_via(ctx, *, output_hint)`; `budget.control.bounded_control_notice`; `output.emit(*, output_format, payload, render_text, sort_keys=False, sink=None)`.
- Produces: `curate inventory` registered `CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT)`; the shared test helpers `_invoke`, `_seed_entities`, `_assert_document_refuses`, `_assert_document_file_complete`, and `_assert_report_projection` that Tasks 2-4 reuse.

- [ ] **Step 1: Create the regression module with DOCUMENT + REPORT helpers and the `curate inventory` case**

Create `science/tests/test_budget_regression_reports.py`:

```python
"""Sizes AND completeness for the slice 1b-2 REPORT/DOCUMENT commands.

Separate from test_budget_regression_rows.py (ROWS commands) because these commands
project per section (REPORT) or refuse whole (DOCUMENT) rather than dropping flat rows.

Proven per command:
  DOCUMENT (curate inventory): stdout over budget REFUSES (nonzero exit, names --output,
    emits no partial payload); --output writes the complete document.
  REPORT (prose lint, consolidation-candidates, validate): stdout stays under the ceiling
    AND projection ran (a "showing"/omitted footer in table, an omission marker with full
    totals in JSON); --output is complete and unprojected in both formats.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main


def _seed_entities(root: Path, kind: str, plural: str, count: int) -> None:
    folder = root / "entities" / plural
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (folder / f"{i:04d}.md").write_text(
            f"---\nid: {kind}:{kind[0]}{i:04d}-a-deliberately-long-descriptive-slug\n"
            f"kind: {kind}\ntitle: {kind.title()} {i} with a long title to exercise wrapping\n"
            f"status: open\n---\n\nBody paragraph for {kind} {i}.\n"
        )


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def _assert_document_refuses(command_path: str, base_args: list[str], *, sentinel: str) -> None:
    """A DOCUMENT over budget refuses on stdout: nonzero exit, names --output, leaks nothing."""
    result = _invoke(base_args)
    assert result.exit_code != 0, result.output
    assert "--output" in result.output
    assert visible_len(result.output) <= BUDGETS[command_path].max_chars
    assert sentinel not in result.output  # no partial payload leaked past the refusal


def _assert_document_file_complete(base_args, out_dir, *, expected_items, count_items):
    """--output writes the complete document; every seeded record is present."""
    target = out_dir / "complete.json"
    result = _invoke([*base_args, "--output", str(target)])
    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())  # the complete document parses whole
    assert count_items(payload) == expected_items
    return payload


def _assert_report_projection(command_path, base_args, out_dir, *, expected_exit, omitted_key, count_items, summary_of):
    """Prove the REPORT contract with the --output file as ground truth.

    - exact exit code in every format;
    - the file is complete and unprojected (no omission marker);
    - projected stdout math reconciles: shown + omitted == the full total;
    - the summary block is byte-identical projected vs complete (projection alters display only);
    - projected stdout stays under the ceiling and carries the "showing " footer;
    - the complete table file exceeds the ceiling (rejects an empty/projected file).
    """
    file_json = out_dir / "complete.json"
    fr = _invoke([*base_args, "--format", "json", "--output", str(file_json)])
    assert fr.exit_code == expected_exit, fr.output
    complete = json.loads(file_json.read_text())
    assert complete.get(omitted_key, 0) == 0, "file JSON must not be projected"
    total = count_items(complete)

    sr = _invoke([*base_args, "--format", "json"])
    assert sr.exit_code == expected_exit, sr.output
    proj = json.loads(sr.output)
    shown, omitted = count_items(proj), proj.get(omitted_key, 0)
    assert omitted > 0, f"expected projection but {omitted_key}={omitted}"
    assert shown + omitted == total, f"{shown} + {omitted} != {total}"
    assert summary_of(proj) == summary_of(complete), "projection must not alter the summary"

    tr = _invoke(base_args)
    assert tr.exit_code == expected_exit, tr.output
    assert visible_len(tr.output) <= BUDGETS[command_path].max_chars
    assert "showing " in tr.output

    file_txt = out_dir / "complete.txt"
    ttr = _invoke([*base_args, "--output", str(file_txt)])
    assert ttr.exit_code == expected_exit, ttr.output
    written = file_txt.read_text()
    assert "showing " not in written
    assert visible_len(written) > BUDGETS[command_path].max_chars


def test_curate_inventory_refuses_and_completes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    # One record per entity: 900 entities makes the inventory JSON ~340k chars, far over 20,000.
    _seed_entities(tmp_path, "question", "questions", 300)
    _seed_entities(tmp_path, "interpretation", "interpretations", 300)
    _seed_entities(tmp_path, "discussion", "discussions", 300)
    monkeypatch.chdir(tmp_path)
    # A seeded artifact id proves nothing partial leaks when the DOCUMENT refuses on stdout.
    _assert_document_refuses("curate inventory", ["curate", "inventory"], sentinel="discussion:d0000")
    payload = _assert_document_file_complete(
        ["curate", "inventory"], tmp_path,
        expected_items=900, count_items=lambda p: len(p["artifacts"]),
    )
    assert sum(payload["artifact_counts"].values()) == 900  # {question:300, interpretation:300, discussion:300}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_reports.py -v`
Expected: FAIL — `curate inventory` is not in `BUDGETS` (KeyError in the helper) and has no `--output` option; today it prints the whole ~700k inventory to stdout instead of refusing. If the seeded inventory is somehow under 20,000 chars, increase the counts until the unbudgeted run exceeds it before proceeding.

- [ ] **Step 3: Register the budget and drop the deferral**

In `science/src/science_tool/budget/registry.py`, add to `BUDGETS`:

```python
    "curate inventory": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
```

and delete from `DEFERRED`:

```python
    "curate inventory": DeferredCommand("one record per entity", "1b", 683_657),
```

- [ ] **Step 4: Bump the partition and drop the measured entry**

In `tests/test_budget_boundary.py`, set `EXPECTED_CLASSIFICATION_COUNTS` to `{"budgeted": 11, "exempt": 67, "deferred": 200}`.

In `tests/test_budget_registry.py::test_the_remaining_measured_offenders_are_deferred`, remove `"curate inventory"` from the `measured` set (leave the other three).

- [ ] **Step 5: Wire the `inventory_cmd` callback**

In `science/src/science_tool/curate/cli.py`, add the `--output` option and route through a DOCUMENT sink. Replace the body of `inventory_cmd` so it reads:

```python
@curate_group.command("inventory")
@click.option("--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json", show_default=True)
@click.option(
    "--recently-modified-days",
    type=int,
    default=7,
    show_default=True,
    help="Window (days) for the recently_modified signal.",
)
@click.option(
    "--recently-modified-top-k",
    type=int,
    default=20,
    show_default=True,
    help="Cap recently_modified to the K most-recent entries; pass 0 to disable.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted inventory to PATH instead of stdout.",
)
def inventory_cmd(
    project_root: Path,
    output_format: str,
    recently_modified_days: int,
    recently_modified_top_k: int,
    output_path: Path | None,
) -> None:
    """Print a deterministic project corpus inventory."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    inventory = collect_inventory(
        project_root,
        recent_days=recently_modified_days,
        recent_top_k=None if recently_modified_top_k <= 0 else recently_modified_top_k,
    )
    payload = inventory.model_dump(mode="json")
    sink = BoundedSink(
        lookup("curate inventory"),
        output_path=output_path,
        command_path="curate inventory",
        complete_via=build_complete_via(click.get_current_context(), output_hint="inventory.json"),
    )
    control_notice = (
        bounded_control_notice(f"wrote the curate inventory to {output_path}")
        if output_path is not None
        else None
    )
    emit(output_format=output_format, payload=payload, render_text=lambda: None, sort_keys=True, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
```

A DOCUMENT budget declares no `max_rows`, so nothing is projected: `emit(..., sink=sink)` serializes the full inventory into the sink and `flush()` refuses (raises `BudgetExceeded`) when stdout exceeds 20,000 chars. `--output` writes the complete document. `sort_keys=True` preserves the command's existing deterministic byte output.

- [ ] **Step 6: Run the regression, boundary guards, and lint/types**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_reports.py tests/test_budget_boundary.py tests/test_budget_registry.py -v && uv run ruff check && uv run pyright`
Expected: PASS/clean; partition 11/67/200.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/budget/registry.py science/src/science_tool/curate/cli.py science/tests/test_budget_boundary.py science/tests/test_budget_registry.py science/tests/test_budget_regression_reports.py
git commit -m "feat(budget): refuse over-budget curate inventory, offer --output"
```

---

## Task 2: Wire `prose lint` (REPORT)

**Files:**
- Create: `science/src/science_tool/prose_lint_projection.py` (bespoke projector)
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `science/src/science_tool/prose_lint_cli.py:29-143` (the `lint_cmd` callback and `_render_table`)
- Modify: `science/tests/test_budget_boundary.py` (partition 12/67/199)
- Modify: `science/tests/test_budget_registry.py` (drop `"prose lint"`)
- Modify: `science/tests/test_budget_regression_reports.py`

**Interfaces:**
- Consumes: the slice-1a helpers and the Task 1 test helpers.
- Produces: `prose lint` registered `CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT)`; `prose_lint_projection.project_prose_lint(payload: dict, cap: int = PROSE_LINT_ROW_CAP) -> dict`.

The `prose lint` payload is `{"counts": {...}, "hits": [ {file,line,col,check,severity,message}, ... ], "coverage": {...}}`. `counts` and `coverage` are the summary; `hits` is the one growable list.

- [ ] **Step 1: Add the regression case (RED)**

Append to `science/tests/test_budget_regression_reports.py`:

```python
def _seed_prose_hits(root: Path, count: int) -> None:
    """Seed markdown files each carrying a bare author-year, a reliable prose-lint hit."""
    docs = root / "doc"
    docs.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        # "(Smith 2020)" with no [@cite] anchor is a bare-author-year finding.
        (docs / f"note-{i:04d}.md").write_text(
            f"# Note {i}\n\nThe result was significant (Smith {2000 + (i % 25)}), a bare "
            f"author-year citation number {i} that the linter must flag.\n"
        )


def test_prose_lint_is_bounded_and_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    _seed_prose_hits(tmp_path, 400)
    monkeypatch.chdir(tmp_path)
    _assert_report_projection(
        "prose lint", ["prose", "lint"], tmp_path,
        expected_exit=0,  # no --strict -> prose lint never fails the run
        omitted_key="hits_omitted",
        count_items=lambda p: len(p["hits"]),
        summary_of=lambda p: p["counts"],
    )
    # The per-check `counts` are the summary; they must equal the full hit total.
    complete = json.loads((tmp_path / "complete.json").read_text())
    assert sum(complete["counts"].values()) == len(complete["hits"])
```

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_reports.py::test_prose_lint_is_bounded_and_complete -v`
Expected: FAIL — `prose lint` not in `BUDGETS`; the seed produces two hits per file (`bare-author-year` + `frontmatter-inline-gap`), so 400 files ≈ 800 hits print unbudgeted, far over 30,000 chars, and there is no `--output`. Confirmed against source: 20 files produce 40 hits with `sum(counts.values()) == len(hits)`. If a future default-check change drops the seed under 30,000 chars, inspect `science_tool.prose_lint.CHECKS` and grow the seed until the RED run exceeds the ceiling.

- [ ] **Step 2: Write the projector**

Create `science/src/science_tool/prose_lint_projection.py`:

```python
"""Projection for `science prose lint` display. Narrows the growable `hits` list without
changing the summary the report claims. Lives beside the command, not in budget/, so the
budgeting mechanism stays free of domain knowledge (mirrors graph/health_projection.py)."""

from __future__ import annotations

from typing import Any

PROSE_LINT_ROW_CAP = 40


def project_prose_lint(payload: dict[str, Any], cap: int = PROSE_LINT_ROW_CAP) -> dict[str, Any]:
    """Return a display copy with `hits` capped and `hits_omitted` recorded.

    `counts` and `coverage` are copied through untouched: they are the summary, and
    redefining them from the capped list would make the report understate its own findings.
    """
    if cap < 0:
        raise ValueError(f"prose lint cap must be non-negative, got {cap}")
    hits = payload["hits"]
    capped = hits[:cap]
    return {
        **payload,
        "hits": capped,
        "hits_omitted": len(hits) - len(capped),
    }
```

- [ ] **Step 3: Register the budget, drop the deferral, bump the partition, drop the measured entry**

In `registry.py`, add to `BUDGETS`:

```python
    "prose lint": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
```

and delete `"prose lint": DeferredCommand("one row per prose finding", "1b", 550_226),` from `DEFERRED`.

Set `EXPECTED_CLASSIFICATION_COUNTS` to `{"budgeted": 12, "exempt": 67, "deferred": 199}`, and remove `"prose lint"` from the measured set in `test_budget_registry.py`.

- [ ] **Step 4: Wire the callback and rewire `_render_table` through the sink**

In `science/src/science_tool/prose_lint_cli.py`, add `--output`, construct the sink, project for stdout, and route rendering through the sink. Replace the `--strict` decorator's following signature/body and `_render_table`:

```python
@click.option("--strict", is_flag=True, help="Promote info-severity issues to warn; exit non-zero on any issue.")
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout.",
)
def lint_cmd(root: Path, fmt: str, checks: tuple[str, ...], strict: bool, output_path: Path | None) -> None:
    """Run prose-quality lints across the project's doc/ and entities/ trees."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.prose_lint_projection import project_prose_lint

    # ... keep the entire existing body that builds `result` and `payload` unchanged ...

    sink = BoundedSink(
        lookup("prose lint"),
        output_path=output_path,
        command_path="prose lint",
        complete_via=build_complete_via(click.get_current_context(), output_hint="prose-lint.json"),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete prose-lint report to {output_path}")
        if output_path is not None
        else None
    )
    displayed = payload if output_path is not None else project_prose_lint(payload)
    emit(output_format=fmt, payload=displayed, render_text=lambda: _render_table(displayed, root, sink), sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

    # Mirrors `science markers scan`: only --strict + issues fails the run. Uses the FULL
    # result, never the projected display.
    if strict and result["hits"]:
        sys.exit(1)
```

Rewrite `_render_table` to take the (possibly projected) payload and the sink, writing through `sink.echo`, and to print the omission footer:

```python
def _render_table(payload: dict, root: Path, sink) -> None:
    hits = payload["hits"]
    numeric_coverage = (payload.get("coverage") or {}).get("numeric-verification")
    if numeric_coverage:
        sink.echo(
            "numeric-verification: "
            f"{numeric_coverage.get('verified', 0)} verified, "
            f"{numeric_coverage.get('unverifiable', 0)} unverifiable, "
            f"{numeric_coverage.get('mismatch', 0)} mismatch, "
            f"{numeric_coverage.get('error', 0)} error"
        )
    if not hits:
        if not numeric_coverage:
            sink.echo("prose lint: no issues found.")
        return
    by_file: dict[str, list] = {}
    for hit in hits:
        by_file.setdefault(hit["file"], []).append(hit)
    for path in sorted(by_file):
        sink.echo(f"\n{path}")
        for hit in sorted(by_file[path], key=lambda h: (h["line"], h["col"])):
            sink.echo(f"  {hit['line']}:{hit['col']} [{hit['check']}] ({hit['severity']}) {hit['message']}")
    sink.echo("\nSummary:")
    for check, count in sorted(payload["counts"].items()):
        sink.echo(f"  {check}: {count}")
    omitted = payload.get("hits_omitted", 0)
    if omitted:
        shown = len(hits)
        sink.echo(f"\nshowing {shown} of {shown + omitted} hits")
        sink.echo(f"  complete output:  {sink.complete_via}")
```

Note the render now reads dict `hits` (from `payload["hits"]`, already `asdict`-serialized with `file` made relative in the existing body) rather than `Hit` dataclasses — the payload's hits are dicts. Keep the existing `payload` construction (it already relativizes `file`). Add `from pathlib import Path` only if missing (it is already imported).

- [ ] **Step 5: Run tests, lint, types**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_reports.py tests/test_budget_boundary.py tests/test_budget_registry.py -v && uv run ruff check && uv run pyright`
Expected: PASS/clean; partition 12/67/199. If the projected table still exceeds 30,000 chars at cap 40, lower `PROSE_LINT_ROW_CAP` (never shrink the test seed).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/prose_lint_projection.py science/src/science_tool/prose_lint_cli.py science/src/science_tool/budget/registry.py science/tests/test_budget_boundary.py science/tests/test_budget_registry.py science/tests/test_budget_regression_reports.py
git commit -m "feat(budget): bound prose lint output through a sink"
```

---

## Task 3: Wire `curate consolidation-candidates` (REPORT)

**Files:**
- Create: `science/src/science_tool/consolidation_candidates_projection.py`
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `science/src/science_tool/curate/cli.py:49-74` (the `consolidation_candidates_cmd` callback)
- Modify: `science/src/science_tool/consolidation_candidates.py` (make `render_text` append an omission footer, or handle it in the callback — see Step 4)
- Modify: `science/tests/test_budget_boundary.py` (partition 13/67/198)
- Modify: `science/tests/test_budget_registry.py` (drop `"curate consolidation-candidates"`)
- Modify: `science/tests/test_budget_regression_reports.py`

**Interfaces:**
- Produces: `curate consolidation-candidates` registered `CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT)`; `consolidation_candidates_projection.project_consolidation_candidates(payload: dict, cap: int = CONSOLIDATION_ROW_CAP) -> dict`.

The payload is `ConsolidationCandidates.model_dump(mode="json")` with three growable lists — `superseded_lineage.linear`, `superseded_lineage.non_linear`, and `semantic_clusters` — plus a `counts` summary and `project_root`.

- [ ] **Step 1: Add the regression case (RED)**

Append to `science/tests/test_budget_regression_reports.py`:

```python
def test_consolidation_candidates_is_bounded_and_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import yaml

    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    folder = tmp_path / "entities" / "interpretations"
    folder.mkdir(parents=True)

    def _write(name: str, fm: dict) -> None:
        (folder / f"{name}.md").write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\nbody\n")

    # The supersession edge is a RELATION with predicate "sci:supersedes" on the successor
    # (top-level `supersedes:` is ignored -- verified against consolidation.py). Each pair is
    # one linear lineage chain. Distinct id stems (oldNNNN / newNNNN) avoid the alias
    # collision that a shared numeric stem (qNNNN-old / qNNNN-new) would raise.
    for i in range(300):
        _write(f"old{i:04d}", {"id": f"interpretation:old{i:04d}", "kind": "interpretation",
                               "title": f"Old {i}", "status": "superseded"})
        _write(f"new{i:04d}", {"id": f"interpretation:new{i:04d}", "kind": "interpretation",
                               "title": f"New {i}", "status": "open",
                               "relations": [{"predicate": "sci:supersedes", "target": f"interpretation:old{i:04d}"}]})
    monkeypatch.chdir(tmp_path)
    _assert_report_projection(
        "curate consolidation-candidates", ["curate", "consolidation-candidates"], tmp_path,
        expected_exit=0,  # read-only report
        omitted_key="candidates_omitted",
        count_items=lambda p: (
            len(p["superseded_lineage"]["linear"])
            + len(p["superseded_lineage"]["non_linear"])
            + len(p["semantic_clusters"])
        ),
        summary_of=lambda p: p["counts"],
    )
```

Run the case. Expected: FAIL — not budgeted, no `--output`, output over budget. Confirmed against source: 6 relation-pairs produce 6 linear chains (exit 0), so 300 pairs produce 300 chains, ~exceeding 30,000 chars. If a future detector change drops the count, add `related:` overlaps for semantic clusters until the unbudgeted run exceeds 30,000 chars.

- [ ] **Step 2: Write the projector**

Create `science/src/science_tool/consolidation_candidates_projection.py`:

```python
"""Projection for `science curate consolidation-candidates` display. Caps the three
growable lists and records how many rows were dropped, without touching `counts`."""

from __future__ import annotations

from typing import Any

CONSOLIDATION_ROW_CAP = 40


def project_consolidation_candidates(payload: dict[str, Any], cap: int = CONSOLIDATION_ROW_CAP) -> dict[str, Any]:
    if cap < 0:
        raise ValueError(f"consolidation cap must be non-negative, got {cap}")
    lineage = payload.get("superseded_lineage") or {}
    linear = lineage.get("linear") or []
    non_linear = lineage.get("non_linear") or []
    clusters = payload.get("semantic_clusters") or []

    capped_linear = linear[:cap]
    capped_non_linear = non_linear[:cap]
    capped_clusters = clusters[:cap]
    omitted = (
        (len(linear) - len(capped_linear))
        + (len(non_linear) - len(capped_non_linear))
        + (len(clusters) - len(capped_clusters))
    )
    return {
        **payload,
        "superseded_lineage": {**lineage, "linear": capped_linear, "non_linear": capped_non_linear},
        "semantic_clusters": capped_clusters,
        "candidates_omitted": omitted,
    }
```

- [ ] **Step 3: Register, drop deferral, bump partition, drop measured entry**

Add to `BUDGETS`: `"curate consolidation-candidates": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),`; delete its `DeferredCommand` line. Set `EXPECTED_CLASSIFICATION_COUNTS` to `{"budgeted": 13, "exempt": 67, "deferred": 198}`; remove `"curate consolidation-candidates"` from the measured set.

- [ ] **Step 4: Wire the callback**

`consolidation_candidates.render_text` takes a `ConsolidationCandidates` model and returns a string. Project on the dict payload, re-hydrate the model for `render_text`, echo through the sink, and add the omission footer. Replace `consolidation_candidates_cmd`'s body tail:

```python
def consolidation_candidates_cmd(
    project_root: Path,
    output_format: str,
    related_jaccard: float,
    min_cluster_size: int,
    max_cluster_size: int,
    output_path: Path | None,
) -> None:
    """Report consolidation candidates (read-only; superseded-lineage + semantic)."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.consolidation_candidates import (
        ConsolidationCandidates,
        detect_consolidation_candidates,
        render_text,
    )
    from science_tool.consolidation_candidates_projection import project_consolidation_candidates

    report = detect_consolidation_candidates(
        project_root,
        related_jaccard=related_jaccard,
        min_cluster_size=min_cluster_size,
        max_cluster_size=max_cluster_size,
    )
    full_payload = report.model_dump(mode="json")
    sink = BoundedSink(
        lookup("curate consolidation-candidates"),
        output_path=output_path,
        command_path="curate consolidation-candidates",
        complete_via=build_complete_via(click.get_current_context(), output_hint="consolidation-candidates.json"),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete consolidation report to {output_path}")
        if output_path is not None
        else None
    )
    displayed = full_payload if output_path is not None else project_consolidation_candidates(full_payload)

    def _render() -> None:
        sink.echo(render_text(ConsolidationCandidates.model_validate(displayed)))
        omitted = displayed.get("candidates_omitted", 0)
        if omitted:
            shown = (
                len(displayed["superseded_lineage"]["linear"])
                + len(displayed["superseded_lineage"]["non_linear"])
                + len(displayed["semantic_clusters"])
            )
            sink.echo(f"\nshowing {shown} of {shown + omitted} candidates")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=output_format, payload=displayed, render_text=_render, sink=sink, sort_keys=True)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
```

Add the `--output` option (identical shape to Task 2) and the `output_path: Path | None` parameter to the decorator/signature. The footer uses the `"showing "` convention that the shared `_assert_report_projection` helper checks, matching the other REPORT commands.

- [ ] **Step 5: Run tests, lint, types**

Run the reports + boundary + registry suites, ruff, pyright. Expected PASS/clean; partition 13/67/198. Lower `CONSOLIDATION_ROW_CAP` if the projected table exceeds 30,000 chars.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/consolidation_candidates_projection.py science/src/science_tool/curate/cli.py science/src/science_tool/budget/registry.py science/tests/test_budget_boundary.py science/tests/test_budget_registry.py science/tests/test_budget_regression_reports.py
git commit -m "feat(budget): bound curate consolidation-candidates through a sink"
```

---

## Task 4: Wire `validate` (REPORT)

**Files:**
- Create: `science/src/science_tool/validate/projection.py`
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `science/src/science_tool/validate/cli.py:25-107,166-184` (callback + `_emit_text`)
- Modify: `science/tests/test_budget_boundary.py` (partition 14/67/197)
- Modify: `science/tests/test_budget_registry.py` (drop `"validate"` — leaves the measured set empty)
- Modify: `science/tests/test_budget_regression_reports.py`

**Interfaces:**
- Produces: `validate` registered `CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT)`; `validate.projection.project_validate_results(results: list, cap: int = VALIDATE_ROW_CAP) -> tuple[list, int]` returning `(capped_results, omitted)`.

`validate`'s JSON payload is `{"summary": {errors,warnings,infos}, "results": [...]}` (built by `_json_payload`); its text render is `_emit_text(result, verbose=...)`, which uses a raw `get_console`. Exit code depends on `result.errors`/`result.gated` — the FULL result.

- [ ] **Step 1: Add the regression case (RED)**

Append to `science/tests/test_budget_regression_reports.py`:

```python
def test_validate_is_bounded_and_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    # Many unresolved references produce many validation findings. Seed entities whose
    # `related:` points at nonexistent targets. Confirmed against source: 20 such entities
    # produce 160 findings (37 errors, 123 warnings, 0 infos), so 400 far exceed the ceiling
    # and `validate` exits 1 (errors present).
    folder = tmp_path / "entities" / "questions"
    folder.mkdir(parents=True)
    for i in range(400):
        (folder / f"{i:04d}.md").write_text(
            f"---\nid: question:q{i:04d}-a-long-descriptive-slug\nkind: question\n"
            f"title: Question {i}\nstatus: open\n"
            f"related: [hypothesis:h{i:04d}-does-not-exist-anywhere-in-this-project]\n---\n\nbody\n"
        )
    monkeypatch.chdir(tmp_path)
    _assert_report_projection(
        "validate", ["validate"], tmp_path,
        expected_exit=1,  # errors present -> ctx.exit(1) on the full result
        omitted_key="results_omitted",
        count_items=lambda p: len(p["results"]),
        summary_of=lambda p: p["summary"],
    )
```

Run the case. Expected: FAIL — `validate` not budgeted, no `--output`, findings printed unbudgeted. If unresolved-ref seeding does not yield >30,000 chars of findings, inspect `validate/runner.py` for a cheaper high-volume finding and grow the seed until the RED run exceeds the ceiling.

- [ ] **Step 2: Write the projector**

Create `science/src/science_tool/validate/projection.py`:

```python
"""Projection for `science validate` display: cap the growable findings list, leaving the
summary counts and exit-determining totals to the full result."""

from __future__ import annotations

from typing import Any

VALIDATE_ROW_CAP = 40


def project_validate_results(results: list[Any], cap: int = VALIDATE_ROW_CAP) -> tuple[list[Any], int]:
    """Return (capped_results, omitted_count)."""
    if cap < 0:
        raise ValueError(f"validate cap must be non-negative, got {cap}")
    capped = results[:cap]
    return capped, len(results) - len(capped)
```

- [ ] **Step 3: Register, drop deferral, bump partition, drop measured entry**

Add `"validate": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),` to `BUDGETS`; delete its `DeferredCommand` line. Set `EXPECTED_CLASSIFICATION_COUNTS` to `{"budgeted": 14, "exempt": 67, "deferred": 197}`. Remove `"validate"` from the measured set — it is now empty (Task 5 deletes the test).

- [ ] **Step 4: Wire the callback and thread the sink through `_emit_text`**

In `validate/cli.py`, add `--output`/`output_path`, build the sink, project the displayed results for stdout, thread the sink console into the text renderer, and build the JSON payload from the displayed results while recording the omission. Keep `ctx.exit(1)` on the FULL result. The projected JSON payload must record the omission (add `results_omitted`).

Add the option to the decorator and `output_path: Path | None` to the signature. Replace the tail from `_record_validation_summary(...)` onward:

```python
    _record_validation_summary(result=result, profile=profile, strict=strict, fail_on=fail_on)

    sidecar_stdout = captured_stdout.getvalue()
    if sidecar_stdout:
        click.echo(sidecar_stdout, nl=False, err=True)

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.validate.projection import project_validate_results

    sink = BoundedSink(
        lookup("validate"),
        output_path=output_path,
        command_path="validate",
        complete_via=build_complete_via(click.get_current_context(), output_hint="validate.json"),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete validation report to {output_path}")
        if output_path is not None
        else None
    )

    # Visibility is FORMAT-SPECIFIC and MUST be applied before the cap: INFO rows must never
    # consume the cap, and each format's omission count must reflect what that format shows.
    # (JSON drops all INFO; text keeps only "visible info" per _display_filter.)
    json_visible = [item for item in result.results if item.severity is not Severity.INFO]
    text_visible = [item for item in result.results if _display_filter(item, verbose=verbose)]
    if output_path is not None:
        json_results, json_omitted = json_visible, 0
        text_results, text_omitted = text_visible, 0
    else:
        json_results, json_omitted = project_validate_results(json_visible)
        text_results, text_omitted = project_validate_results(text_visible)

    # Summary counts always come from the FULL result (via _json_payload); projection
    # narrows only the displayed `results`. results_omitted is added only when it projected.
    payload = {
        "summary": _json_payload(result)["summary"],
        "results": [item.to_dict() for item in json_results],
    }
    if json_omitted:
        payload["results_omitted"] = json_omitted

    emit(
        output_format=output_format,
        payload=payload,
        render_text=lambda: _emit_text(result, text_results, text_omitted, sink, verbose=verbose),
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

    # Exit reflects the FULL result, never the projected display.
    if result.errors or result.gated:
        ctx.exit(1)
```

Rewire `_emit_text` to render through the sink's console and print the footer, taking the already-visible-and-capped results:

```python
def _emit_text(
    result: RunResult,
    shown_results: list[Result],
    omitted: int,
    sink,
    *,
    verbose: bool = False,
) -> None:
    # shown_results is already filtered by _display_filter AND capped by the caller; render
    # it as-is. The header/coverage/notices/summary come from the FULL result.
    console = sink.console
    console.print(BANNER)
    console.print("Science Project Validation")
    console.print(BANNER)
    console.print(_format_check_coverage(result), soft_wrap=True)
    for item in _notice_results(result):
        console.print(_format_notice(item), soft_wrap=True)

    if verbose:
        for section in _section_names(result):
            console.print(section_banner(section))

    for item in shown_results:
        console.print(_format_result(item), soft_wrap=True)

    if omitted:
        sink.echo(f"showing {len(shown_results)} of {len(shown_results) + omitted} findings")
        sink.echo(f"  complete output:  {sink.complete_via}")

    console.print()
    console.print(BANNER)
    console.print(_format_summary(result), soft_wrap=True)
```

Add a small `_display_filter` helper equivalent to the old `_text_results` predicate (INFO handling), so the caller can filter `result.results` before capping:

```python
def _display_filter(item: Result, *, verbose: bool) -> bool:
    if verbose:
        return not _is_visible_info(item)
    return item.severity is not Severity.INFO
```

The summary (`_format_summary`) and coverage still read the FULL `result`, so counts and PASS/FAIL are unchanged. `ctx.exit(1)` fires on the full result. The stderr sidecar is untouched.

- [ ] **Step 5: Run tests, lint, types**

Run the reports + boundary + registry suites, ruff, pyright. Expected PASS/clean; partition 14/67/197. Lower `VALIDATE_ROW_CAP` if the projected report exceeds 30,000 chars at cap 40.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/projection.py science/src/science_tool/validate/cli.py science/src/science_tool/budget/registry.py science/tests/test_budget_boundary.py science/tests/test_budget_registry.py science/tests/test_budget_regression_reports.py
git commit -m "feat(budget): bound validate output through a sink"
```

---

## Task 5: Delete the discharged measured-offenders test, refresh the partition docstring, run the full suite

**Files:**
- Modify: `science/tests/test_budget_registry.py` (delete `test_the_remaining_measured_offenders_are_deferred`)
- Modify: `science/tests/test_budget_boundary.py` (docstring only)

**Interfaces:**
- Consumes: the final 14/67/197 partition.
- Produces: nothing.

- [ ] **Step 1: Delete the fully discharged test**

All ten measured offenders are now wired (six in 1b-1, four in 1b-2), so `test_the_remaining_measured_offenders_are_deferred` has an empty `measured` set and asserts nothing. Delete the entire function (and any now-unused imports it alone used, e.g. leave `DEFERRED` if other tests use it — verify with a grep). Its invariant — "measured offenders stay deferred until wired" — is fully retired; the partition-cardinality guard remains the standing check.

- [ ] **Step 2: Refresh the partition docstring**

In `test_budget_boundary.py::test_classification_partition_has_the_audited_cardinality`, append a sentence recording this slice:

```python
    ...  Slice 1b-2 then wired the four REPORT/DOCUMENT offenders (curate inventory,
    prose lint, curate consolidation-candidates, validate), moving them from deferred to
    budgeted. The live partition is therefore 14/67/197 = 278.
    """
```

(Adjust the exact wording to fold cleanly into the existing docstring; keep the final total truthful.)

- [ ] **Step 3: Run the whole budget suite and the full suite**

Run: `cd science && uv run --frozen pytest tests/ -k budget -v`
Then: `cd science && uv run --frozen pytest` (pass an explicit long timeout; ~2-3 min).
Expected: all pass. Note main currently carries pre-existing failures in `test_proposition_reconciliation_cli.py` and `test_tasks_cli.py` (JSON-output tests) unrelated to this slice — confirm your changes add none beyond that set.

- [ ] **Step 4: Lint and type-check**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_budget_registry.py science/tests/test_budget_boundary.py
git commit -m "test(budget): retire the discharged measured-offenders test; record slice 1b-2 partition"
```

---

## Self-Review

**Spec coverage.** All four remaining measured offenders are wired: `curate inventory` as DOCUMENT (Task 1), `prose lint` (Task 2), `curate consolidation-candidates` (Task 3), and `validate` (Task 4) as REPORT. Task 5 retires the discharged test and records the final partition. No other command is in scope; the ~190 long-tail generic-registered DEFERRED commands are 1b-3+.

**Type consistency.** REPORT commands register `CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT)` (matching `health`); `curate inventory` registers `CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT)` (matching `entities inventory`). Each bespoke projector is `project_<cmd>(payload/results, cap=...) -> narrowed`, recording an `*_omitted` count inside the payload so `emit`'s JSON branch carries the omission. `EXPECTED_CLASSIFICATION_COUNTS` advances 10→11→12→13→14 budgeted and 201→200→199→198→197 deferred across Tasks 1-4.

**Guard alignment.** Each wired callback constructs its `BoundedSink` in its own body and exposes `--output`, satisfying both AST guards. DOCUMENT refuse is `flush()` raising `BudgetExceeded`; REPORT projection is skipped when `output_path is not None`, so `--output` is always complete.

**Behavioural coverage.** DOCUMENT: `_assert_document_refuses` (nonzero exit + names `--output` + a seeded artifact-id sentinel is absent, proving no partial payload leaked) and `_assert_document_file_complete` (the `--output` file parses whole and holds exactly the seeded record count — 900 artifacts). REPORT: one helper, `_assert_report_projection`, uses the `--output` file as ground truth and asserts, per command: the **exact** exit code in both formats (prose 0, consolidation 0, validate 1); the file is complete and unprojected (`omitted_key == 0`); the projected stdout reconciles (`shown + omitted == full total`); the summary block is identical projected-vs-complete (projection alters display only, never counts); projected stdout is under the ceiling with the `"showing "` footer; and the complete table file exceeds the ceiling (rejecting an empty or projected file). These are command-specific via the `count_items`/`summary_of`/`expected_exit`/`omitted_key` parameters, so a wrong total, an altered summary, a wrong exit code, or an incomplete file all fail. The FULL-result invariant (summary + exit) is enforced in the wiring and verified by the summary-invariance and exact-exit-code assertions.

**Known limits.**
- `max_chars=30_000` / per-command cap 40 are carried from `health`/`SECTION_ROW_CAP`. If any projected REPORT exceeds 30,000 chars at cap 40 (wide rows), lower that command's cap constant until the regression is green — never shrink the test seed (the slice-1b-1 lesson).
- Each RED step instructs measuring the unbudgeted size and growing the seed if it is under the ceiling, because the exact corpus that pushes `prose lint`/`validate`/`consolidation-candidates` over budget depends on which checks fire; the plan's seeds are the starting point, not a guarantee.
- `validate`'s `_emit_text` rewire is the largest surface change; its stderr sidecar and `ctx.exit(1)`-on-full-result behaviour are preserved deliberately and must stay covered by the existing `test_validate` / validate-CLI tests (run them in Task 4 Step 5 alongside the budget suite).

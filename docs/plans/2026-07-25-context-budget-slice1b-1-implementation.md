# Context Budget — Slice 1b-1 (wire the ROWS offenders) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the six measured-over-budget, flat-row commands (`entity list`, `feedback list`, `questions list`, `interpretations list`, `discussions list`, `entity needs-review`) under the slice-1a context budget by routing each through a `BoundedSink`.

**Architecture:** Slice 1a already built the machinery — `BUDGETS`/`DEFERRED` registry, `project_rows` projection, `BoundedSink`, and the `emit`/`emit_query_rows` payload channel that projects rows and records truncation when a `sink` is supplied. This slice adds no architecture. Each command gains a `--output PATH` escape, constructs a `BoundedSink` from the registry in its own callback, passes that sink to `emit_query_rows`, and flushes. The three typed-entity lists share one helper (`list_typed_entities`), so the sink is threaded through it as an optional parameter — the other three callers of that helper stay unbudgeted.

**Tech Stack:** Python 3.11, Click, Rich, pytest, rdflib (needs-review reads the materialized graph).

## Global Constraints

- **Python floor is 3.11** — all three packages pin `requires-python = ">=3.11"` and `pyrightconfig.json` sets `pythonVersion: 3.11`. PEP 695 syntax (`class Foo[T]`, `def f[T]()`) is a **3.12** feature; use `TypeVar` + `Generic`.
- **`stdout is always budgeted; `--output PATH` is always complete.** Projection never runs against a file sink. This is the slice-1a contract and every task here inherits it.
- **Conventional commits.** No AI-attribution trailer/footer on commits, PRs, or comments.
- **Use `~/d/` or relative paths** in docs and code, never absolute `/home/...` or `/mnt/...` paths.
- **Composition over inheritance; explicit over defensive; fail early, no silent fallbacks; no "legacy"/"compatibility" layers; no `Unified` prefix.**
- **Run tests from `science/`:** `cd science && uv run --frozen pytest`. Lint: `uv run ruff check`. Types: `uv run pyright`.
- **The registry partition is asserted.** `tests/test_budget_boundary.py::EXPECTED_CLASSIFICATION_COUNTS` is currently `{"budgeted": 4, "exempt": 67, "deferred": 206}`. Every task that moves a key from `DEFERRED` to `BUDGETS` MUST update this dict in the same commit or the partition test fails. Final state after this slice: `{"budgeted": 10, "exempt": 67, "deferred": 200}`.

## Boundary guards every wired command must satisfy

Two AST/tree guards in `tests/test_budget_boundary.py` run over `BUDGETS` automatically — no per-command test authoring, but the wiring must be shaped to pass them:

1. `test_every_budgeted_command_constructs_its_own_sink` — the command's **own callback body** (not a nested function, lambda, or comprehension) must contain a `BoundedSink(...)` call. A command that delegates sink construction to a helper fails. This is why the typed-entity commands construct the sink in each callback and pass it *into* `list_typed_entities`, rather than letting the helper build it.
2. `test_every_budgeted_command_offers_the_output_escape` — the command must expose a `--output` option.

---

## Task 1: Record the slice-1b decomposition in the umbrella design

**Files:**
- Modify: `docs/plans/2026-07-24-agent-context-budget-program-design.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by later tasks; this is the design-of-record for why slice 1b is split by payload shape.

- [ ] **Step 1: Add a "Slice 1b decomposition" subsection under "Slice 1 — the context-budget contract"**

Insert after the existing slice-1 body (before "### Slice 2"):

```markdown
#### Slice 1b decomposition

Slice 1a wired the four hand-picked commands and mass-registered every other growable
leaf as `DeferredCommand(..., "1b")` to satisfy the completeness guard. That deferral
set is ~200 commands of three different payload shapes, so 1b is not one plan. It is
split by shape, because the projection mechanism differs by shape:

- **1b-1 — ROWS offenders (this slice).** The measured-over-budget commands whose payload
  is a flat row list: `entity list` (1.7M chars), `questions list`, `interpretations list`,
  `entity needs-review`, `feedback list`, `discussions list`. Uniform `emit_query_rows`
  wiring; `project_rows` already handles narrowing. Highest value (includes the single
  worst offender) at lowest risk.
- **1b-2 — REPORT/DOCUMENT offenders (next).** `prose lint`, `validate`, and
  `curate consolidation-candidates` are REPORT-shaped (a summary plus a growable list) and
  need the per-section projection `health` uses; `curate inventory` is a versioned
  structured document that must refuse past budget like `entities inventory`, because
  dropping records corrupts the model. Forcing these through row-projection would emit
  misleading output, so they are deliberately excluded from 1b-1.
- **1b-3+ — the long tail.** The remaining ~190 generic-registered commands. Each needs a
  per-command audit: genuinely growable ones get wired; fixed-shape ones (mutation and
  creation confirmations mis-labeled growable) move to `EXEMPTIONS`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/plans/2026-07-24-agent-context-budget-program-design.md
git commit -m "docs(budget): record the slice 1b shape-based decomposition"
```

---

## Task 2: Wire `entity list`

**Files:**
- Modify: `science/src/science_tool/budget/registry.py` (move `entity list` from `DEFERRED` to `BUDGETS`)
- Modify: `science/src/science_tool/entities_cli.py:193-242` (the `entity_list` callback)
- Modify: `science/tests/test_budget_boundary.py` (bump `EXPECTED_CLASSIFICATION_COUNTS`)
- Create: `science/tests/test_budget_regression_rows.py` (new size-regression module + shared fixture)

**Interfaces:**
- Consumes from slice 1a: `BoundedSink(budget, *, output_path, command_path, complete_via)`; `budget.registry.lookup(command_path) -> CommandBudget | None`; `budget.invocation.build_complete_via(ctx, *, output_hint) -> str`; `budget.control.bounded_control_notice(message) -> str`; `output.emit_query_rows(*, output_format, title, columns, rows, meta=None, renderers=None, sink=None)`.
- Produces: `entity list` registered as `CommandBudget(max_chars=20_000, shape=ROWS, max_rows=40)`; a new test module and `rows_corpus` fixture that Tasks 3-5 extend.

- [ ] **Step 1: Write the new regression module with the shared fixture and the `entity list` case**

Create `science/tests/test_budget_regression_rows.py`. The fixture is deliberately separate from `test_budget_regression.py::project`, whose exact entity counts are asserted by slice-1a tests; adding kinds there would break them.

```python
"""Emitted sizes for the slice 1b-1 ROWS commands on an over-budget corpus.

Separate from ``test_budget_regression.py`` because that module's ``project`` fixture
asserts exact entity counts; this one seeds extra kinds (interpretations, discussions),
feedback, and a needs-review graph without disturbing those assertions.
"""

from __future__ import annotations

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


@pytest.fixture
def rows_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    _seed_entities(tmp_path, "question", "questions", 300)
    _seed_entities(tmp_path, "interpretation", "interpretations", 300)
    _seed_entities(tmp_path, "discussion", "discussions", 300)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def test_entity_list_stays_within_its_ceiling(rows_corpus: Path) -> None:
    for args in (["entity", "list"], ["entity", "list", "--format", "json"]):
        result = _invoke(args)
        assert result.exit_code == 0, result.output
        ceiling = BUDGETS["entity list"].max_chars
        assert visible_len(result.output) <= ceiling, (
            f"{args} emitted {visible_len(result.output)} > {ceiling}"
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_rows.py -v`
Expected: FAIL — `entity list` is not in `BUDGETS` yet (`KeyError`), and its unbudgeted output over 900 entities is far above 20,000 chars.

- [ ] **Step 3: Move `entity list` from `DEFERRED` to `BUDGETS`**

In `science/src/science_tool/budget/registry.py`, add to the `BUDGETS` dict:

```python
    "entity list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
```

and delete this line from the `DEFERRED` dict:

```python
    "entity list": DeferredCommand("one row per entity", "1b", 1_706_994),
```

- [ ] **Step 4: Bump the asserted partition**

In `science/tests/test_budget_boundary.py`, change `EXPECTED_CLASSIFICATION_COUNTS`:

```python
EXPECTED_CLASSIFICATION_COUNTS = {
    "budgeted": 5,
    "exempt": 67,
    "deferred": 205,
}
```

(The explanatory docstring on `test_classification_partition_has_the_audited_cardinality` is refreshed once in Task 6, after all six moves.)

- [ ] **Step 5: Wire the `entity_list` callback**

In `science/src/science_tool/entities_cli.py`, add the `--output` option and `output_path` parameter, construct the sink, pass it to `emit_query_rows`, and flush. The command's top-level imports already include `emit_query_rows`; add the budget imports locally as `tasks list` does.

Replace the decorator/signature (currently ends at the `--format` option and `def entity_list(... output_format: str) -> None:`) so it reads:

```python
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def entity_list(
    kind_arg: str | None,
    kind: str | None,
    status: str | None,
    related: str | None,
    include_hidden: bool,
    include_archived: bool,
    output_format: str,
    output_path: Path | None,
) -> None:
    """List source-authored entities."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
```

Keep the existing body that resolves `kind` and builds `rows`. Replace the trailing `emit_query_rows(...)` call with:

```python
    complete_via = build_complete_via(click.get_current_context(), output_hint="entities.json")
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} entities to {output_path}")
        if output_path is not None
        else None
    )
    sink = BoundedSink(
        lookup("entity list"),
        output_path=output_path,
        command_path="entity list",
        complete_via=complete_via,
    )
    emit_query_rows(
        output_format=output_format,
        title="Entities",
        columns=[("id", "ID"), ("kind", "Kind"), ("status", "Status"), ("title", "Title"), ("path", "Path")],
        rows=rows,
        renderers=entity_table_renderers(),
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
```

- [ ] **Step 6: Run the regression, the boundary guards, and the full budget suite**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_rows.py tests/test_budget_boundary.py -v`
Expected: PASS — `entity list` stays under 20,000 chars, constructs its own sink, and offers `--output`; the partition is `5/67/205`.

- [ ] **Step 7: Lint and type-check**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/budget/registry.py science/src/science_tool/entities_cli.py science/tests/test_budget_boundary.py science/tests/test_budget_regression_rows.py
git commit -m "feat(budget): bound entity list output through a sink"
```

---

## Task 3: Wire `feedback list`

**Files:**
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `science/src/science_tool/feedback_cli.py:154-201` (the `feedback_list` callback)
- Modify: `science/tests/test_budget_boundary.py`
- Modify: `science/tests/test_budget_regression_rows.py`

**Interfaces:**
- Consumes: the slice-1a helpers listed in Task 2.
- Produces: `feedback list` registered as `CommandBudget(max_chars=20_000, shape=ROWS, max_rows=40)`.

- [ ] **Step 1: Add the `feedback list` regression case**

Feedback entries are read from `$SCIENCE_FEEDBACK_DIR` (see `feedback_cli._get_feedback_dir`), not the project tree, so the test points that env var at a seeded directory. Append to `science/tests/test_budget_regression_rows.py`:

```python
def test_feedback_list_stays_within_its_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.feedback import VALID_CATEGORIES

    category = next(iter(sorted(VALID_CATEGORIES)))
    fb_dir = tmp_path / "feedback"
    fb_dir.mkdir()
    for i in range(300):
        (fb_dir / f"fb-2026-01-01-{i:03d}.yaml").write_text(
            f"id: fb-2026-01-01-{i:03d}\n"
            "created: 2026-01-01\n"
            f"project: demo-project-{i:03d}\n"
            f"target: command:some-long-target-name-{i:03d}\n"
            "concern: methodology:design\n"  # a valid VALID_CONCERNS value
            f"category: {category}\n"
            f"summary: A deliberately long feedback summary line number {i} to exercise wrapping\n"
            "status: open\n"
            "recurrence: 1\n"
        )
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(fb_dir))

    for args in (["feedback", "list"], ["feedback", "list", "--format", "json"]):
        result = _invoke(args)
        assert result.exit_code == 0, result.output
        ceiling = BUDGETS["feedback list"].max_chars
        assert visible_len(result.output) <= ceiling, (
            f"{args} emitted {visible_len(result.output)} > {ceiling}"
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_rows.py::test_feedback_list_stays_within_its_ceiling -v`
Expected: FAIL — `feedback list` not in `BUDGETS`; 300 wide feedback rows exceed 20,000 chars.

The seed uses `category = next(iter(sorted(VALID_CATEGORIES)))` and `concern: methodology:design` (both verified valid against `science_tool.feedback`), so parsing should succeed; if a required `FeedbackEntry` field is nonetheless missing, the RED run surfaces it in stderr — add it to the seed before proceeding.

- [ ] **Step 3: Register the budget and drop the deferral**

In `registry.py`, add to `BUDGETS`:

```python
    "feedback list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
```

and delete from `DEFERRED`:

```python
    "feedback list": DeferredCommand("one row per feedback item", "1b", 44_307),
```

- [ ] **Step 4: Bump the partition**

`EXPECTED_CLASSIFICATION_COUNTS` → `{"budgeted": 6, "exempt": 67, "deferred": 204}`.

- [ ] **Step 5: Wire the `feedback_list` callback**

Add the `--output` option after the `--format` option, add `output_path: Path | None` to the signature, and — because `feedback_cli.py` does not import `Path` at module top in this function's scope — ensure `from pathlib import Path` is present at the top of the module (it is used elsewhere; verify). Then replace the trailing `emit_query_rows(...)` call:

```python
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    complete_via = build_complete_via(click.get_current_context(), output_hint="feedback.json")
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} feedback entries to {output_path}")
        if output_path is not None
        else None
    )
    sink = BoundedSink(
        lookup("feedback list"),
        output_path=output_path,
        command_path="feedback list",
        complete_via=complete_via,
    )
    emit_query_rows(output_format=output_format, title="Feedback", columns=columns, rows=rows, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
```

Place the four budget imports at the top of the callback body (after the existing `from science_tool.feedback import list_entries`).

- [ ] **Step 6: Run tests, lint, types**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_rows.py tests/test_budget_boundary.py -v && uv run ruff check && uv run pyright`
Expected: PASS/clean; partition `6/67/204`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/budget/registry.py science/src/science_tool/feedback_cli.py science/tests/test_budget_boundary.py science/tests/test_budget_regression_rows.py
git commit -m "feat(budget): bound feedback list output through a sink"
```

---

## Task 4: Wire the typed-entity lists (`questions list`, `interpretations list`, `discussions list`)

**Files:**
- Modify: `science/src/science_tool/budget/registry.py` (three moves)
- Modify: `science/src/science_tool/typed_entity_cli.py:101` (`list_typed_entities` gains an optional `sink`)
- Modify: `science/src/science_tool/questions_cli.py:80-86`, `interpretations_cli.py:61-67`, `discussions_cli.py:61-67` (three callbacks)
- Modify: `science/tests/test_budget_boundary.py`
- Modify: `science/tests/test_budget_regression_rows.py`

**Interfaces:**
- Consumes: slice-1a helpers; the `rows_corpus` fixture from Task 2 (already seeds 300 each of questions, interpretations, discussions).
- Produces: `list_typed_entities(kind, status, related, output_format, *, sink: BoundedSink | None = None)` — the added parameter is keyword-only and defaults to `None`, so the three unbudgeted callers (`hypotheses list`, `propositions list`, `evidence-lines list`) are unchanged. Each of the three wired commands is registered `CommandBudget(max_chars=20_000, shape=ROWS, max_rows=40)`.

- [ ] **Step 1: Add the regression cases**

Append to `science/tests/test_budget_regression_rows.py`:

```python
@pytest.mark.parametrize(
    ("command_path", "args"),
    [
        ("questions list", ["questions", "list"]),
        ("questions list", ["questions", "list", "--format", "json"]),
        ("interpretations list", ["interpretations", "list"]),
        ("interpretations list", ["interpretations", "list", "--format", "json"]),
        ("discussions list", ["discussions", "list"]),
        ("discussions list", ["discussions", "list", "--format", "json"]),
    ],
)
def test_typed_entity_list_stays_within_its_ceiling(
    rows_corpus: Path, command_path: str, args: list[str]
) -> None:
    result = _invoke(args)
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS[command_path].max_chars
    assert visible_len(result.output) <= ceiling, (
        f"{args} emitted {visible_len(result.output)} > {ceiling}"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_rows.py::test_typed_entity_list_stays_within_its_ceiling -v`
Expected: FAIL — none of the three is in `BUDGETS`; each returns 300 rows well over the ceiling.

- [ ] **Step 3: Register the three budgets and drop the three deferrals**

In `registry.py`, add to `BUDGETS`:

```python
    "questions list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "interpretations list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "discussions list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
```

and delete from `DEFERRED`:

```python
    "questions list": DeferredCommand("one row per question", "1b", 113_076),
    "interpretations list": DeferredCommand("one row per interpretation", "1b", 97_281),
    "discussions list": DeferredCommand("one row per discussion", "1b", 30_780),
```

- [ ] **Step 4: Bump the partition**

`EXPECTED_CLASSIFICATION_COUNTS` → `{"budgeted": 9, "exempt": 67, "deferred": 201}`.

- [ ] **Step 5: Thread an optional sink through `list_typed_entities`**

In `science/src/science_tool/typed_entity_cli.py`, change the helper signature and pass the sink to `emit_query_rows`, flushing when present:

```python
def list_typed_entities(
    kind: str,
    status: str | None,
    related: str | None,
    output_format: str,
    *,
    sink: BoundedSink | None = None,
) -> None:
    try:
        rows = list_entities(Path.cwd(), kind=kind, status=status, related=related)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    emit_query_rows(
        output_format=output_format,
        title=ENTITY_LIST_TITLES.get(kind, kind.replace("-", " ").title() + "s"),
        columns=[("id", "ID"), ("status", "Status"), ("title", "Title"), ("path", "Path")],
        rows=rows,
        renderers=entity_table_renderers(),
        sink=sink,
    )
    if sink is not None:
        sink.flush()
```

Add the import at the top of `typed_entity_cli.py`:

```python
from science_tool.budget.sink import BoundedSink
```

- [ ] **Step 6: Wire the three command callbacks**

Each callback constructs the sink in its own body (required by the AST guard) and passes it in. For `questions_cli.py`, replace the `question_list` command:

```python
@question_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def question_list(status: str | None, related: str | None, output_format: str, output_path: Path | None) -> None:
    """List source-authored questions."""
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    sink = BoundedSink(
        lookup("questions list"),
        output_path=output_path,
        command_path="questions list",
        complete_via=build_complete_via(click.get_current_context(), output_hint="questions.json"),
    )
    list_typed_entities("question", status, related, output_format, sink=sink)
```

Apply the identical transformation to `interpretation_list` in `interpretations_cli.py` (command path `"interpretations list"`, kind `"interpretation"`, hint `"interpretations.json"`) and `discussion_list` in `discussions_cli.py` (command path `"discussions list"`, kind `"discussion"`, hint `"discussions.json"`).

Import note (verified against source): `questions_cli.py` already imports `Path`, `click`, and `OUTPUT_FORMATS`. `interpretations_cli.py` and `discussions_cli.py` import `click` and `OUTPUT_FORMATS` but **not** `Path` — add `from pathlib import Path` to the top of each of those two modules (the new `output_path: Path | None` parameter type needs it).

The file-success control notice is omitted here: `list_typed_entities` owns the flush, and these three commands did not previously print a post-flush line. `--output` completeness is still covered because the sink writes the full payload to the file; the boundary guard only requires the option to exist and the sink to be constructed.

- [ ] **Step 7: Run tests, lint, types**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_rows.py tests/test_budget_boundary.py tests/test_typed_entity_cli.py -v && uv run ruff check && uv run pyright`
Expected: PASS/clean; partition `9/67/201`. If `test_typed_entity_cli.py` does not exist, drop it from the invocation; run the questions/interpretations/discussions CLI tests that do exist to confirm no regression in the unbudgeted callers.

- [ ] **Step 8: Verify the unbudgeted callers still work**

Run: `cd science && uv run --frozen pytest -k "hypotheses or propositions or evidence_lines" -v`
Expected: PASS — `hypotheses list`, `propositions list`, `evidence-lines list` call `list_typed_entities` without a sink and behave exactly as before.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/budget/registry.py science/src/science_tool/typed_entity_cli.py science/src/science_tool/questions_cli.py science/src/science_tool/interpretations_cli.py science/src/science_tool/discussions_cli.py science/tests/test_budget_boundary.py science/tests/test_budget_regression_rows.py
git commit -m "feat(budget): bound the typed-entity list commands through a sink"
```

---

## Task 5: Wire `entity needs-review`

**Files:**
- Modify: `science/src/science_tool/budget/registry.py`
- Modify: `science/src/science_tool/entities_cli.py:601-620` (the `entity_needs_review` callback)
- Modify: `science/tests/test_budget_boundary.py`
- Modify: `science/tests/test_budget_regression_rows.py`

**Interfaces:**
- Consumes: slice-1a helpers; `entity_review.list_needs_review(project_root)`, which reads `graph.trig` and returns rows for triples whose `sci:freshnessState` is `"needs-review"` or `"stale"`.
- Produces: `entity needs-review` registered as `CommandBudget(max_chars=20_000, shape=ROWS, max_rows=40)`. Final partition `10/67/200`.

- [ ] **Step 1: Add the regression case with a hand-built needs-review graph**

`list_needs_review` reads the materialized graph directly, so the fixture writes a `graph.trig` with 60 flagged entities using the same namespaces the reader uses — no full materialization pipeline. Append to `science/tests/test_budget_regression_rows.py`:

```python
def test_needs_review_stays_within_its_ceiling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rdflib import Dataset, Literal

    from science_tool.graph.store import DEFAULT_GRAPH_PATH, PROJECT_NS, SCI_NS

    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for i in range(60):
        uri = PROJECT_NS[f"question/q{i:04d}-a-deliberately-long-descriptive-slug"]
        knowledge.add((uri, SCI_NS.freshnessState, Literal("needs-review")))
    trig_path = tmp_path / DEFAULT_GRAPH_PATH
    trig_path.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(trig_path), format="trig")
    monkeypatch.chdir(tmp_path)

    for args in (["entity", "needs-review"], ["entity", "needs-review", "--format", "json"]):
        result = _invoke(args)
        assert result.exit_code == 0, result.output
        ceiling = BUDGETS["entity needs-review"].max_chars
        assert visible_len(result.output) <= ceiling, (
            f"{args} emitted {visible_len(result.output)} > {ceiling}"
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_rows.py::test_needs_review_stays_within_its_ceiling -v`
Expected: FAIL — `entity needs-review` not in `BUDGETS`. (60 short rows may or may not exceed 20k unbudgeted; the case still fails on the missing `BUDGETS` key. If 60 rows do not exceed the ceiling, raise the loop to 400 so the RED state also demonstrates flooding, matching the other cases.)

- [ ] **Step 3: Register the budget and drop the deferral**

In `registry.py`, add to `BUDGETS`:

```python
    "entity needs-review": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
```

and delete from `DEFERRED`:

```python
    "entity needs-review": DeferredCommand("one row per flagged entity", "1b", 59_697),
```

- [ ] **Step 4: Bump the partition**

`EXPECTED_CLASSIFICATION_COUNTS` → `{"budgeted": 10, "exempt": 67, "deferred": 200}`.

- [ ] **Step 5: Wire the `entity_needs_review` callback**

In `science/src/science_tool/entities_cli.py`, add the `--output` option, thread `output_path`, construct the sink, and pass it in:

```python
@entity_group.command("needs-review")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def entity_needs_review(output_format: str, output_path: Path | None) -> None:
    """List epistemic entities flagged needs-review or stale by the materialized graph."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.entity_review import list_needs_review
    from science_tool.output import emit_query_rows

    rows = list_needs_review(Path.cwd())
    complete_via = build_complete_via(click.get_current_context(), output_hint="needs-review.json")
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} flagged entities to {output_path}")
        if output_path is not None
        else None
    )
    sink = BoundedSink(
        lookup("entity needs-review"),
        output_path=output_path,
        command_path="entity needs-review",
        complete_via=complete_via,
    )
    emit_query_rows(
        output_format=output_format,
        title="Entities needing review",
        columns=[("state", "State"), ("kind", "Kind"), ("id", "ID")],
        rows=rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
```

- [ ] **Step 6: Run tests, lint, types**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression_rows.py tests/test_budget_boundary.py -v && uv run ruff check && uv run pyright`
Expected: PASS/clean; partition `10/67/200`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/budget/registry.py science/src/science_tool/entities_cli.py science/tests/test_budget_boundary.py science/tests/test_budget_regression_rows.py
git commit -m "feat(budget): bound entity needs-review output through a sink"
```

---

## Task 6: Refresh the partition docstring and run the full suite

**Files:**
- Modify: `science/tests/test_budget_boundary.py` (docstring only)

**Interfaces:**
- Consumes: the final `10/67/200` partition established by Tasks 2-5.
- Produces: nothing.

- [ ] **Step 1: Update the explanatory docstring on `test_classification_partition_has_the_audited_cardinality`**

Append a sentence recording this slice, so the number's provenance stays truthful:

```python
    """Lock the audited partition, not only its absence of unclassified leaves.

    Task 1 supplied 4 budgeted, 3 exempt, and 11 deferred paths. Task 13's RED
    surfaced 258 more, classified as 65 exempt and 193 deferred. Review then
    corrected tasks summary from exempt to deferred because its distinct type/group
    keys are unbounded. The post-merge belief-basis command adds one deferred leaf
    because compare mode emits one row per changed entity. Slice 1b-1 then wired six
    ROWS offenders (entity list, feedback list, questions/interpretations/discussions
    list, entity needs-review), moving them from deferred to budgeted. The live
    partition is therefore 10/67/200 = 277.
    """
```

- [ ] **Step 2: Run the entire budget suite plus the whole test run**

Run: `cd science && uv run --frozen pytest tests/ -k budget -v`
Then: `cd science && uv run --frozen pytest`
Expected: all pass. The registry-completeness guard, sink-construction guard, output-escape guard, and the six new size regressions are green; no slice-1a test regressed.

- [ ] **Step 3: Lint and type-check the whole package**

Run: `cd science && uv run ruff check && uv run pyright`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_budget_boundary.py
git commit -m "test(budget): record slice 1b-1 in the partition-cardinality docstring"
```

---

## Self-Review

**Spec coverage.** All six measured ROWS offenders are wired: `entity list` (Task 2), `feedback list` (Task 3), `questions`/`interpretations`/`discussions list` (Task 4), `entity needs-review` (Task 5). The four non-ROWS offenders (`prose lint`, `validate`, `curate consolidation-candidates`, `curate inventory`) are explicitly deferred to 1b-2 and recorded in the umbrella design (Task 1). No other slice-1b command is in scope.

**Type consistency.** Every command registers `CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40)` and constructs `BoundedSink(lookup(<path>), output_path=..., command_path=<path>, complete_via=...)` with the exact signature slice 1a ships. `list_typed_entities` gains a keyword-only `sink: BoundedSink | None = None`, leaving its three unbudgeted callers unchanged. The `EXPECTED_CLASSIFICATION_COUNTS` dict advances 4→5→6→9→10 budgeted and 206→205→204→201→200 deferred across Tasks 2-5, matching the six moves.

**Guard alignment.** Each wired callback constructs its sink in its own body (not a nested scope), satisfying `test_every_budgeted_command_constructs_its_own_sink`, and exposes `--output`, satisfying `test_every_budgeted_command_offers_the_output_escape`. The typed-entity commands deliberately build the sink in the callback rather than in `list_typed_entities` for exactly this reason.

**Known limits.**
- `max_rows=40` is carried from `tasks list`. The per-command size regressions assert `visible_len <= 20_000`; if a wide-row render (e.g. `feedback list`, 8 columns) ever exceeds the ceiling at 40 rows, lower that command's `max_rows` until the regression is green. The measured sizes make this unlikely at 40 rows.
- The `entity needs-review` regression builds `graph.trig` directly rather than materializing it. This exercises `list_needs_review`'s actual read path but not the freshness-computation that assigns `freshnessState` in production; that computation is covered by the graph-materialization tests, not this budget slice.
- `curate inventory` (683k) and `prose lint` (550k) — offenders #2 and #3 by size — remain unbounded until 1b-2, because row-projection would corrupt a structured document and misrepresent a summary-plus-findings report respectively.

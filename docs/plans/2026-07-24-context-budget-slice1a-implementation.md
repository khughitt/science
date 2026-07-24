# Context Budget — Slice 1a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the context-budget mechanism and wire it end-to-end, in **both** output formats,
through the four commands that bypass the shared emitters — `tasks list`, `health`,
`entities inventory`, `data audit`.

**Architecture:** `BoundedSink` **is the output channel**, not a wrapper around one branch of
`emit`. Every budgeted command constructs one sink, renders everything into it (via
`sink.console` for Rich renderables and `sink.echo` for lines), and flushes once. Flush measures
the whole invocation and either writes it to stdout, writes it complete to `--output PATH`, or
raises. Semantic narrowing happens earlier, in a **projection** chosen by the command's declared
payload shape; an unregistered shape refuses rather than degrading.

**Tech Stack:** Python 3.12+, Click, Rich, Pydantic, pytest. All work is in `science/`.

**Parent design:**
[`2026-07-24-agent-context-budget-program-design.md`](2026-07-24-agent-context-budget-program-design.md)
(rev 4). Read "Slice 1 — the context-budget contract" before starting.

**Supersedes** the slice-1 plan in commit `5364826c`, which had six contract breaks: it assumed
ten commands would inherit budgets automatically (they use `emit`, not `emit_query_rows`, so
they inherit nothing); left `health`'s 21 tables and `data audit`'s default text branch outside
the sink entirely; projected `tasks list` JSON but not its table; hardcoded an escape command
that dropped the user's own filters; computed `displayed_issues` with semantics incompatible
with `total_issues`; and guarded only modules that import an emitter.

## Scope

**In scope (1a):** the mechanism, plus `tasks list`, `health`, `entities inventory`,
`data audit` wired completely in table and JSON.

**Deferred to 1b:** the ten other measured offenders (`entity list`, `questions list`,
`interpretations list`, `discussions list`, `feedback list`, `entity needs-review`,
`curate consolidation-candidates`, `curate inventory`, `prose lint`, `validate`). They are
recorded in a `DEFERRED` registry table with each measured size — **not** in `EXEMPTIONS`, which
asserts a command cannot grow. The completeness guard requires every leaf command to sit in
exactly one of `BUDGETS`, `EXEMPTIONS`, or `DEFERRED`.

## Global Constraints

- Run everything from `science/` — `cd science && uv run --frozen pytest`. There is no root
  `pyproject.toml`; running `uv run` from the repo root is the most common orientation mistake.
- Lint and types from `science/`: `uv run ruff check`, `uv run pyright`.
- **stdout is always budgeted; `--output PATH` is always complete.** No flag makes stdout
  unbounded, and no projection ever runs against a file sink.
- **Semantic truncation never happens in the sink.** The sink routes, measures, raises.
- **`total_issues` never changes meaning.** It stays the unfiltered clean-report gate.
- **Every budgeted command owns exactly one sink** and emits nothing outside it.
- Composition over inheritance; explicit over defensive; fail early, no silent fallbacks.
- No "legacy"/"compatibility" layers. No `Unified` prefix.
- Conventional commits. No AI-attribution trailers.
- Use `~/d/` or relative paths in docs and code.

## File Structure

**New package `science/src/science_tool/budget/`** — domain-agnostic. No health/task/entity
imports.

| File | Responsibility |
|---|---|
| `budget/registry.py` | `CommandBudget`, `PayloadShape`, `BUDGETS`, `EXEMPTIONS`, `DEFERRED`, `lookup`, `shape_for`. |
| `budget/measure.py` | `visible_len`, `BUDGET_CONSOLE_WIDTH`. |
| `budget/sink.py` | `BoundedSink` (the output channel), `BudgetExceeded`. |
| `budget/projection.py` | `project_rows`, `ProjectedRows`. |
| `budget/invocation.py` | `build_complete_via` — derives the escape command from the live Click context. |

**Modified:** `output.py` (both branches through the sink), `styles.py` (`width`),
`tasks_cli.py`, `tasks_display.py`, `graph/health.py` (extract `count_issues`),
`graph/health_cli.py`, `entities_inventory_cli.py`, `data_cli.py`.

**New:** `graph/health_projection.py` — health-specific projection, beside health rather than in
`budget/`.

---

### Task 1: Registry with shapes and a deferred state

**Files:**
- Create: `science/src/science_tool/budget/__init__.py`, `science/src/science_tool/budget/registry.py`
- Test: `science/tests/test_budget_registry.py`

**Interfaces:**
- Produces: `PayloadShape` (`StrEnum`: `ROWS`, `REPORT`, `DOCUMENT`),
  `CommandBudget(max_chars: int, shape: PayloadShape, max_rows: int | None = None)`,
  `BUDGETS: dict[str, CommandBudget]`, `EXEMPTIONS: dict[str, str]`,
  `DEFERRED: dict[str, DeferredCommand]`, `DeferredCommand(measured_chars: int, target_slice: str)`,
  `lookup(command_path) -> CommandBudget | None`, `shape_for(command_path) -> PayloadShape | None`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_registry.py
from __future__ import annotations

import pytest

from science_tool.budget.registry import (
    BUDGETS,
    DEFERRED,
    EXEMPTIONS,
    CommandBudget,
    PayloadShape,
    lookup,
    shape_for,
)

WIRED = ["tasks list", "health", "entities inventory", "data audit"]


@pytest.mark.parametrize("path", WIRED)
def test_slice_1a_commands_are_budgeted(path: str) -> None:
    budget = lookup(path)
    assert isinstance(budget, CommandBudget)
    assert budget.max_chars > 0


@pytest.mark.parametrize("path", WIRED)
def test_every_budgeted_command_declares_a_shape(path: str) -> None:
    assert isinstance(shape_for(path), PayloadShape)


def test_rows_shape_declares_a_row_cap() -> None:
    for path, budget in BUDGETS.items():
        if budget.shape is PayloadShape.ROWS:
            assert budget.max_rows is not None, f"{path} is row-shaped but has no max_rows"


def test_document_shape_declares_no_row_cap() -> None:
    """A versioned document is refused whole, never partially emitted."""
    for path, budget in BUDGETS.items():
        if budget.shape is PayloadShape.DOCUMENT:
            assert budget.max_rows is None


def test_lookup_returns_none_for_unregistered_command() -> None:
    assert lookup("tasks add") is None


def test_deferred_entries_record_a_measurement_over_the_audit_floor() -> None:
    """DEFERRED is for measured offenders awaiting wiring, not a parking lot."""
    for path, entry in DEFERRED.items():
        assert entry.measured_chars > 20_000, f"{path} is not a measured offender"
        assert entry.target_slice.strip()


def test_the_ten_deferred_offenders_are_recorded() -> None:
    assert set(DEFERRED) == {
        "entity list",
        "questions list",
        "interpretations list",
        "discussions list",
        "feedback list",
        "entity needs-review",
        "curate consolidation-candidates",
        "curate inventory",
        "prose lint",
        "validate",
    }


def test_the_three_tables_are_mutually_disjoint() -> None:
    assert not (set(BUDGETS) & set(EXEMPTIONS))
    assert not (set(BUDGETS) & set(DEFERRED))
    assert not (set(EXEMPTIONS) & set(DEFERRED))


def test_every_exemption_states_a_reason() -> None:
    for path, reason in EXEMPTIONS.items():
        assert reason.strip(), f"{path} is exempt with no reason"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget'`

- [ ] **Step 3: Write the registry**

```python
# science/src/science_tool/budget/registry.py
"""Single source of truth for per-command output ceilings and payload shapes.

Ceilings are in *visible* characters (ANSI stripped) at ``BUDGET_CONSOLE_WIDTH``. Values
come from the 2026-07-24 audit of ``~/d/natural-systems``, the largest adopting project.

Three tables, deliberately distinct:

- ``BUDGETS``   -- wired: the command owns a sink and honours a ceiling.
- ``EXEMPTIONS``-- a claim that the command's output CANNOT grow with project size.
- ``DEFERRED``  -- measured over budget, not yet wired. NOT an exemption: recording a
  known-oversized command as exempt would assert something false.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PayloadShape(StrEnum):
    """How a command's payload may be narrowed.

    ``ROWS``     -- a flat row list; project by dropping rows.
    ``REPORT``   -- a heterogeneous multi-section report; project per section.
    ``DOCUMENT`` -- a versioned document; REFUSE past budget, never partially emit.
    """

    ROWS = "rows"
    REPORT = "report"
    DOCUMENT = "document"


@dataclass(frozen=True)
class CommandBudget:
    max_chars: int
    shape: PayloadShape
    max_rows: int | None = None


@dataclass(frozen=True)
class DeferredCommand:
    measured_chars: int
    target_slice: str


BUDGETS: dict[str, CommandBudget] = {
    "tasks list": CommandBudget(max_chars=20_000, shape=PayloadShape.ROWS, max_rows=40),
    "health": CommandBudget(max_chars=30_000, shape=PayloadShape.REPORT),
    "entities inventory": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
    "data audit": CommandBudget(max_chars=20_000, shape=PayloadShape.DOCUMENT),
}

EXEMPTIONS: dict[str, str] = {
    "tasks summary": "measured 1,692 chars on 2026-07-24; aggregate counts, cannot grow with backlog size",
    "graph stats": "measured 341 chars on 2026-07-24; fixed-shape summary",
    "telemetry status": "measured 366 chars on 2026-07-24; fixed-shape summary",
}

DEFERRED: dict[str, DeferredCommand] = {
    "entity list": DeferredCommand(measured_chars=1_706_994, target_slice="1b"),
    "curate inventory": DeferredCommand(measured_chars=683_657, target_slice="1b"),
    "prose lint": DeferredCommand(measured_chars=550_226, target_slice="1b"),
    "questions list": DeferredCommand(measured_chars=113_076, target_slice="1b"),
    "validate": DeferredCommand(measured_chars=109_466, target_slice="1b"),
    "interpretations list": DeferredCommand(measured_chars=97_281, target_slice="1b"),
    "curate consolidation-candidates": DeferredCommand(measured_chars=71_553, target_slice="1b"),
    "entity needs-review": DeferredCommand(measured_chars=59_697, target_slice="1b"),
    "feedback list": DeferredCommand(measured_chars=44_307, target_slice="1b"),
    "discussions list": DeferredCommand(measured_chars=30_780, target_slice="1b"),
}


def lookup(command_path: str) -> CommandBudget | None:
    return BUDGETS.get(command_path)


def shape_for(command_path: str) -> PayloadShape | None:
    budget = BUDGETS.get(command_path)
    return budget.shape if budget is not None else None
```

```python
# science/src/science_tool/budget/__init__.py
"""Command output budgeting: registry, measurement, projection, sink."""

from science_tool.budget.registry import (
    BUDGETS,
    DEFERRED,
    EXEMPTIONS,
    CommandBudget,
    DeferredCommand,
    PayloadShape,
    lookup,
    shape_for,
)

__all__ = [
    "BUDGETS",
    "DEFERRED",
    "EXEMPTIONS",
    "CommandBudget",
    "DeferredCommand",
    "PayloadShape",
    "lookup",
    "shape_for",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_budget_registry.py -v`
Expected: PASS (9 tests, 8 parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/budget/ science/tests/test_budget_registry.py
git commit -m "feat(budget): add ceiling registry with payload shapes and a deferred table"
```

---

### Task 2: Measurement and pinned width

**Files:**
- Create: `science/src/science_tool/budget/measure.py`
- Modify: `science/src/science_tool/styles.py:145` (`_new_console`), `:156` (`get_console`)
- Test: `science/tests/test_budget_measure.py`

**Interfaces:**
- Produces: `BUDGET_CONSOLE_WIDTH: int`, `visible_len(text: str) -> int`. `get_console` gains
  keyword-only `width: int | None = None`.

Budget counts **ANSI-stripped visible characters**. `resolve_color_policy` (`styles.py:126`)
returns `NEVER` unless `FORCE_COLOR`/`--color` is set, so on the agent path visible characters
equal emitted characters, and row selection stays identical across color modes.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_measure.py
from __future__ import annotations

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH, visible_len
from science_tool.styles import ColorPolicy, get_console


def test_visible_len_ignores_ansi_escapes() -> None:
    assert visible_len("hello") == 5
    assert visible_len("\x1b[1;31mhello\x1b[0m") == 5


def test_visible_len_counts_newlines() -> None:
    assert visible_len("ab\ncd") == 5


def test_get_console_honours_an_explicit_width() -> None:
    console = get_console(width=BUDGET_CONSOLE_WIDTH)
    assert console.width == BUDGET_CONSOLE_WIDTH


def test_explicit_width_beats_terminal_columns(monkeypatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    assert get_console(width=BUDGET_CONSOLE_WIDTH).width == BUDGET_CONSOLE_WIDTH


def test_width_console_is_not_cached_across_calls() -> None:
    """A width-specific console must never poison the context-cached default."""
    a = get_console(width=50)
    b = get_console(width=120)
    assert a is not b
    assert (a.width, b.width) == (50, 120)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_measure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget.measure'`

- [ ] **Step 3: Add `width` to the console factory**

In `science/src/science_tool/styles.py`:

```python
def _new_console(policy: ColorPolicy, file: TextIO | None = None, width: int | None = None) -> Console:
    match policy:
        case ColorPolicy.NEVER:
            return Console(file=file, force_terminal=False, color_system=None, no_color=True, width=width)
        case ColorPolicy.ALWAYS:
            return Console(file=file, force_terminal=True, color_system="standard", no_color=False, width=width)
        case ColorPolicy.AUTO:
            auto_env = {key: value for key, value in os.environ.items() if key not in _COLOR_ENV_KEYS}
            return Console(file=file, no_color=False, _environ=auto_env, width=width)


def get_console(
    *,
    context: click.Context | None = None,
    file: TextIO | None = None,
    width: int | None = None,
) -> Console:
    policy = get_color_policy(context)
    if file is not None or width is not None:
        # Never cached: the cache is keyed only by context, so a file- or width-specific
        # console would otherwise be handed back to unrelated callers.
        return _new_console(policy, file, width)

    current = context or click.get_current_context(silent=True)
    if current is None:
        return _new_console(policy)

    current.ensure_object(dict)
    cached = current.obj.get(_CONSOLE_KEY)
    if isinstance(cached, Console):
        return cached

    console = _new_console(policy)
    current.obj[_CONSOLE_KEY] = console
    return console
```

- [ ] **Step 4: Write the measurement module**

```python
# science/src/science_tool/budget/measure.py
"""Deterministic size measurement for budgeted output.

Width is pinned rather than inherited from Rich's non-TTY default, which varies with
``COLUMNS``. Color is excluded: we count ANSI-stripped *visible* characters, so row
selection is identical across color modes. Under ``--color always`` the emitted bytes
exceed the budget by the ANSI overhead -- a human at a terminal, not an agent, and
``resolve_color_policy`` defaults to ``NEVER`` on the agent path.
"""

from __future__ import annotations

import re

BUDGET_CONSOLE_WIDTH = 100

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def visible_len(text: str) -> int:
    """Length of ``text`` with ANSI escape sequences removed."""
    return len(_ANSI_RE.sub("", text))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_budget_measure.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Check for console regressions**

Run: `cd science && uv run --frozen pytest -k "console or color or styles" -v`
Expected: PASS — `width=None` must leave every existing call site unchanged.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/budget/measure.py science/src/science_tool/styles.py science/tests/test_budget_measure.py
git commit -m "feat(budget): add ANSI-stripped measurement and an explicit console width"
```

---

### Task 3: `BoundedSink` as the output channel

**Files:**
- Create: `science/src/science_tool/budget/sink.py`
- Test: `science/tests/test_budget_sink.py`

**Interfaces:**
- Consumes: `CommandBudget` (Task 1), `visible_len`, `BUDGET_CONSOLE_WIDTH` (Task 2).
- Produces: `BudgetExceeded(click.ClickException)`,
  `BoundedSink(budget, *, output_path=None, command_path="", complete_via="")` with
  `.console: Console`, `.echo(text: str = "") -> None`, `.write(text: str) -> None`,
  `.flush() -> None`, `.is_file_sink: bool`, `.max_rows: int | None`, `.complete_via: str`.

**The sink is the channel.** Commands render Rich renderables via `sink.console.print(...)` and
lines via `sink.echo(...)`. Everything accumulates in one buffer and is measured once at
`flush()`. This is what makes a 21-table command obey one command-total ceiling, and what makes
`--output` capture *all* of a command's output rather than only its JSON branch.

Buffer-then-flush also means an over-budget command prints **nothing** rather than a truncated
prefix.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_sink.py
from __future__ import annotations

from pathlib import Path

import pytest
from rich.table import Table

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH
from science_tool.budget.registry import CommandBudget, PayloadShape
from science_tool.budget.sink import BoundedSink, BudgetExceeded

ROWS_BUDGET = CommandBudget(max_chars=100, shape=PayloadShape.ROWS, max_rows=5)


def test_echo_reaches_stdout_only_after_flush(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list")
    sink.echo("hello")
    assert capsys.readouterr().out == ""
    sink.flush()
    assert capsys.readouterr().out == "hello\n"


def test_console_output_is_captured_by_the_sink(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list")
    table = Table(title="T")
    table.add_column("C")
    table.add_row("x")
    sink.console.print(table)
    sink.flush()
    assert "┏" in capsys.readouterr().out


def test_console_uses_the_pinned_width() -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list")
    assert sink.console.width == BUDGET_CONSOLE_WIDTH


def test_over_budget_flush_prints_nothing_and_raises(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=10, shape=PayloadShape.ROWS, max_rows=5), command_path="tasks list")
    sink.echo("x" * 50)
    with pytest.raises(BudgetExceeded) as excinfo:
        sink.flush()
    assert capsys.readouterr().out == ""
    assert "tasks list" in str(excinfo.value)
    assert "--output" in str(excinfo.value)


def test_many_sections_share_one_command_total_ceiling() -> None:
    sink = BoundedSink(CommandBudget(max_chars=100, shape=PayloadShape.REPORT), command_path="health")
    for _ in range(3):
        sink.echo("y" * 50)
    with pytest.raises(BudgetExceeded):
        sink.flush()


def test_file_sink_is_never_truncated(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    sink = BoundedSink(
        CommandBudget(max_chars=10, shape=PayloadShape.REPORT),
        output_path=target,
        command_path="health",
    )
    sink.echo("y" * 10_000)
    sink.flush()
    assert target.read_text() == "y" * 10_000 + "\n"


def test_file_sink_reports_no_row_cap(tmp_path: Path) -> None:
    """--output is complete, so projection must not run against a file sink."""
    sink = BoundedSink(ROWS_BUDGET, output_path=tmp_path / "o.json", command_path="tasks list")
    assert sink.max_rows is None
    assert sink.is_file_sink is True


def test_stdout_sink_reports_the_budget_row_cap() -> None:
    assert BoundedSink(ROWS_BUDGET, command_path="tasks list").max_rows == 5


def test_unbudgeted_command_is_unbounded(capsys) -> None:
    sink = BoundedSink(None, command_path="tasks add")
    sink.echo("z" * 100_000)
    sink.flush()
    assert len(capsys.readouterr().out) == 100_001


def test_ansi_does_not_count_against_the_ceiling(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=12, shape=PayloadShape.ROWS, max_rows=5), command_path="tasks list")
    sink.echo("\x1b[1;31m" + "x" * 9 + "\x1b[0m")
    sink.flush()
    assert "x" * 9 in capsys.readouterr().out


def test_flush_is_idempotent(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list")
    sink.echo("once")
    sink.flush()
    sink.flush()
    assert capsys.readouterr().out == "once\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_sink.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget.sink'`

- [ ] **Step 3: Write the sink**

```python
# science/src/science_tool/budget/sink.py
"""The output channel for budgeted commands.

A budgeted command constructs ONE sink, renders everything into it, and flushes once.
Rich renderables go through ``sink.console``; plain lines through ``sink.echo``. Nothing
reaches stdout until ``flush()``.

Why a channel rather than a wrapper around ``emit``'s JSON branch: a command like
``health`` renders 21 tables and a dozen messages directly. Wrapping only the final
serialization would leave all of that on stdout and write an empty ``--output`` file.
Owning the channel is what makes the ceiling command-total and ``--output`` complete.

The sink holds characters, not rows, so it never truncates: it cannot count omitted items
nor cut without severing a table box or an ANSI escape. Semantic narrowing belongs in
projection, which runs before anything is rendered. A projected payload that still
exceeds its ceiling is a budget misconfiguration, so ``flush()`` raises -- printing
nothing rather than a misleading prefix.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import click
from rich.console import Console

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH, visible_len
from science_tool.budget.registry import CommandBudget
from science_tool.styles import get_console


class BudgetExceeded(click.ClickException):
    """A projected payload still exceeded its ceiling."""


class BoundedSink:
    def __init__(
        self,
        budget: CommandBudget | None,
        *,
        output_path: Path | None = None,
        command_path: str = "",
        complete_via: str = "",
    ) -> None:
        self._budget = budget
        self._output_path = output_path
        self._command_path = command_path
        self._complete_via = complete_via
        self._buffer = StringIO()
        self._console: Console | None = None
        self._flushed = False

    @property
    def console(self) -> Console:
        """A Rich console writing into this sink at the pinned budget width."""
        if self._console is None:
            self._console = get_console(file=self._buffer, width=BUDGET_CONSOLE_WIDTH)
        return self._console

    @property
    def is_file_sink(self) -> bool:
        return self._output_path is not None

    @property
    def complete_via(self) -> str:
        return self._complete_via

    @property
    def max_rows(self) -> int | None:
        """Row cap for projection, or None when nothing may be dropped.

        A file sink always returns None: ``--output PATH`` is guaranteed complete, so
        projection must not run against one.
        """
        if self._output_path is not None:
            return None
        return self._budget.max_rows if self._budget is not None else None

    def echo(self, text: str = "") -> None:
        self._buffer.write(text + "\n")

    def write(self, text: str) -> None:
        """Append raw text with no trailing newline added."""
        self._buffer.write(text)

    def flush(self) -> None:
        if self._flushed:
            return
        self._flushed = True
        text = self._buffer.getvalue()

        if self._output_path is not None:
            self._output_path.write_text(text, encoding="utf-8")
            return

        if self._budget is not None:
            size = visible_len(text)
            if size > self._budget.max_chars:
                escape = self._complete_via or f"{self._command_path} --output PATH"
                raise BudgetExceeded(
                    f"{self._command_path or 'command'} produced {size} visible chars after "
                    f"projection, over its {self._budget.max_chars} ceiling. Nothing was "
                    f"printed. For the complete payload run:\n  {escape}"
                )

        click.echo(text, nl=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_budget_sink.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/budget/sink.py science/tests/test_budget_sink.py
git commit -m "feat(budget): make BoundedSink the output channel for budgeted commands"
```

---

### Task 4: Row projection

**Files:**
- Create: `science/src/science_tool/budget/projection.py`
- Test: `science/tests/test_budget_projection.py`

**Interfaces:**
- Produces: `ProjectedRows(rows, omitted, total)` with `.truncated: bool`;
  `project_rows(rows, max_rows) -> ProjectedRows`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_projection.py
from __future__ import annotations

from science_tool.budget.projection import project_rows

ROWS = [{"id": f"t{i:03d}"} for i in range(100)]


def test_projection_is_a_noop_under_the_cap() -> None:
    result = project_rows(ROWS[:5], max_rows=40)
    assert result.rows == ROWS[:5]
    assert (result.omitted, result.total, result.truncated) == (0, 5, False)


def test_projection_keeps_the_first_n_in_caller_order() -> None:
    result = project_rows(ROWS, max_rows=40)
    assert result.rows == ROWS[:40]
    assert (result.omitted, result.total, result.truncated) == (60, 100, True)


def test_none_cap_disables_row_projection() -> None:
    result = project_rows(ROWS, max_rows=None)
    assert result.rows == ROWS
    assert result.truncated is False


def test_empty_rows_project_cleanly() -> None:
    result = project_rows([], max_rows=40)
    assert (result.rows, result.total, result.truncated) == ([], 0, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_projection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget.projection'`

- [ ] **Step 3: Write the projection**

```python
# science/src/science_tool/budget/projection.py
"""Semantic narrowing of row-shaped payloads, before serialization.

Projection runs early precisely so the omitted count is known and can travel inside the
payload. After rendering there are only characters.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProjectedRows:
    rows: list[Mapping[str, Any]]
    omitted: int
    total: int

    @property
    def truncated(self) -> bool:
        return self.omitted > 0


def project_rows(rows: Sequence[Mapping[str, Any]], max_rows: int | None) -> ProjectedRows:
    """Keep the first ``max_rows`` in caller order, reporting how many were dropped.

    Caller order is preserved rather than re-sorted: the command already sorted for a
    reason, and re-sorting here would make the truncated view disagree with the complete
    one.
    """
    total = len(rows)
    if max_rows is None or total <= max_rows:
        return ProjectedRows(rows=list(rows), omitted=0, total=total)
    return ProjectedRows(rows=list(rows[:max_rows]), omitted=total - max_rows, total=total)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_budget_projection.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/budget/projection.py science/tests/test_budget_projection.py
git commit -m "feat(budget): add row projection with omitted-count reporting"
```

---

### Task 5: Derive the escape command from the live invocation

**Files:**
- Create: `science/src/science_tool/budget/invocation.py`
- Test: `science/tests/test_budget_invocation.py`

**Interfaces:**
- Produces: `build_complete_via(ctx: click.Context, *, output_hint: str) -> str`.

A hardcoded escape command is worse than none: pointing a user who ran `--status proposed` at a
bare `tasks list` sends them to the default working set, which is a different result set. The
escape must reproduce **their** selection plus `--output`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_invocation.py
from __future__ import annotations

import click
from click.testing import CliRunner

from science_tool.budget.invocation import build_complete_via

CAPTURED: list[str] = []


@click.group()
def demo() -> None:
    pass


@demo.command("list")
@click.option("--status", default=None)
@click.option("--all", "show_all", is_flag=True, default=False)
@click.option("--aspect", "aspects", multiple=True)
@click.option("--output", "output_path", default=None)
def demo_list(status: str | None, show_all: bool, aspects: tuple[str, ...], output_path: str | None) -> None:
    CAPTURED.append(build_complete_via(click.get_current_context(), output_hint="out.json"))


def _run(args: list[str]) -> str:
    CAPTURED.clear()
    result = CliRunner().invoke(demo, args, prog_name="science")
    assert result.exit_code == 0, result.output
    return CAPTURED[0]


def test_bare_invocation_appends_only_the_output_flag() -> None:
    assert _run(["list"]) == "science list --output out.json"


def test_user_selection_is_preserved() -> None:
    assert _run(["list", "--status", "proposed"]) == "science list --status proposed --output out.json"


def test_boolean_flags_render_without_a_value() -> None:
    assert _run(["list", "--all"]) == "science list --all --output out.json"


def test_repeatable_options_repeat() -> None:
    out = _run(["list", "--aspect", "a", "--aspect", "b"])
    assert out == "science list --aspect a --aspect b --output out.json"


def test_existing_output_option_is_replaced_not_duplicated() -> None:
    out = _run(["list", "--output", "old.json"])
    assert out.count("--output") == 1
    assert out.endswith("--output out.json")


def test_defaults_are_omitted() -> None:
    assert "--status" not in _run(["list"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_invocation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget.invocation'`

- [ ] **Step 3: Write the builder**

```python
# science/src/science_tool/budget/invocation.py
"""Reconstruct the caller's invocation, plus ``--output``, as the escape command.

A truncation footer that names a *different* selection than the user asked for is worse
than no footer: it silently substitutes one result set for another. This rebuilds the
command from the live Click context so the escape returns exactly what was truncated.
"""

from __future__ import annotations

import click

_OUTPUT_PARAMS = frozenset({"output_path", "output"})


def build_complete_via(ctx: click.Context, *, output_hint: str) -> str:
    """Return ``<command path> <non-default options> --output <hint>``."""
    parts: list[str] = [ctx.command_path]
    params_by_name = {param.name: param for param in ctx.command.params}

    for name, value in ctx.params.items():
        if name in _OUTPUT_PARAMS:
            continue
        param = params_by_name.get(name)
        if param is None or not isinstance(param, click.Option):
            continue
        if value is None or value == param.default:
            continue
        flag = max(param.opts, key=len)
        if value is True:
            parts.append(flag)
        elif isinstance(value, (list, tuple)):
            for item in value:
                parts.extend([flag, str(item)])
        else:
            parts.extend([flag, str(value)])

    parts.extend(["--output", output_hint])
    return " ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_budget_invocation.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/budget/invocation.py science/tests/test_budget_invocation.py
git commit -m "feat(budget): derive the escape command from the live invocation"
```

---

### Task 6: Route both emitter branches through the sink

**Files:**
- Modify: `science/src/science_tool/output.py:18` (`emit`), `:73` (`emit_query_rows`)
- Test: `science/tests/test_output_budgeting.py`

**Interfaces:**
- Consumes: `BoundedSink` (Task 3), `project_rows` (Task 4).
- Produces: `emit(..., sink: BoundedSink | None = None)` where the **text branch also uses the
  sink**, and `emit_query_rows(..., sink: BoundedSink | None = None)`.

`render_text` callbacks must render into `sink.console` / `sink.echo`. `emit` cannot do that for
them — it can only pass the sink down — so the contract is: **when a caller supplies a sink, its
`render_text` must write only into that sink.** Task 11's guard checks this per command.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_output_budgeting.py
from __future__ import annotations

import json
from pathlib import Path

from science_tool.budget.registry import CommandBudget, PayloadShape
from science_tool.budget.sink import BoundedSink
from science_tool.output import emit, emit_query_rows

COLUMNS = [("id", "ID"), ("title", "Title")]
ROWS = [{"id": f"t{i:03d}", "title": f"task {i}"} for i in range(100)]
BIG = CommandBudget(max_chars=500_000, shape=PayloadShape.ROWS, max_rows=40)


def _emit_rows(fmt: str, sink: BoundedSink) -> None:
    emit_query_rows(output_format=fmt, title="Tasks", columns=COLUMNS, rows=ROWS, sink=sink)


def test_json_truncation_metadata_lives_in_the_payload(capsys) -> None:
    sink = BoundedSink(BIG, command_path="tasks list", complete_via="science tasks list --output t.json")
    _emit_rows("json", sink)
    sink.flush()
    payload = json.loads(capsys.readouterr().out)
    assert payload["truncation"] == {
        "omitted": 60,
        "total": 100,
        "complete_via": "science tasks list --output t.json",
    }
    assert len(payload["rows"]) == 40


def test_truncated_json_is_a_single_parseable_document(capsys) -> None:
    sink = BoundedSink(BIG, command_path="tasks list")
    _emit_rows("json", sink)
    sink.flush()
    json.loads(capsys.readouterr().out)


def test_untruncated_json_has_no_truncation_key(capsys) -> None:
    budget = CommandBudget(max_chars=500_000, shape=PayloadShape.ROWS, max_rows=500)
    sink = BoundedSink(budget, command_path="tasks list")
    _emit_rows("json", sink)
    sink.flush()
    assert "truncation" not in json.loads(capsys.readouterr().out)


def test_table_branch_reaches_the_sink_not_stdout(capsys) -> None:
    """The text branch must be captured by the sink, not printed directly."""
    sink = BoundedSink(BIG, command_path="tasks list")
    _emit_rows("table", sink)
    assert capsys.readouterr().out == ""  # nothing before flush
    sink.flush()
    assert "┏" in capsys.readouterr().out


def test_table_footer_names_the_omitted_count_and_the_derived_escape(capsys) -> None:
    sink = BoundedSink(BIG, command_path="tasks list", complete_via="science tasks list --status proposed --output t.json")
    _emit_rows("table", sink)
    sink.flush()
    out = capsys.readouterr().out
    assert "40 of 100" in out
    assert "--status proposed --output t.json" in out


def test_table_output_is_never_cut_mid_box(capsys) -> None:
    budget = CommandBudget(max_chars=500_000, shape=PayloadShape.ROWS, max_rows=3)
    sink = BoundedSink(budget, command_path="tasks list")
    _emit_rows("table", sink)
    sink.flush()
    out = capsys.readouterr().out
    assert out.count("┏") == 1 and out.count("└") == 1


def test_emit_text_branch_routes_through_the_sink_to_a_file(tmp_path: Path) -> None:
    """A table-format command with --output must produce a NON-EMPTY file."""
    target = tmp_path / "report.txt"
    sink = BoundedSink(BIG, output_path=target, command_path="health")

    def _render() -> None:
        sink.echo("section one")
        sink.echo("section two")

    emit(output_format="table", payload={"ignored": True}, render_text=_render, sink=sink)
    sink.flush()
    assert target.read_text() == "section one\nsection two\n"


def test_file_sink_disables_row_projection(tmp_path: Path) -> None:
    target = tmp_path / "rows.json"
    sink = BoundedSink(BIG, output_path=target, command_path="tasks list")
    _emit_rows("json", sink)
    sink.flush()
    payload = json.loads(target.read_text())
    assert len(payload["rows"]) == 100
    assert "truncation" not in payload


def test_sink_none_preserves_historical_behaviour(capsys) -> None:
    emit_query_rows(output_format="json", title="T", columns=COLUMNS, rows=ROWS[:2])
    assert len(json.loads(capsys.readouterr().out)["rows"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_output_budgeting.py -v`
Expected: FAIL — `TypeError: emit() got an unexpected keyword argument 'sink'`

- [ ] **Step 3: Rewrite the emitters**

In `science/src/science_tool/output.py`, add imports:

```python
from science_tool.budget.projection import project_rows
from science_tool.budget.sink import BoundedSink
```

Replace `emit` and `emit_query_rows`:

```python
def emit(
    *,
    output_format: str,
    payload: Any,
    render_text: Callable[[], None],
    indent: int | None = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = True,
    default: Callable[[Any], Any] | None = None,
    sink: BoundedSink | None = None,
) -> None:
    """Emit ``payload`` as JSON when ``output_format == "json"``, else ``render_text()``.

    Serialization kwargs mirror ``json.dumps`` so existing call sites keep their exact
    byte output. Diagnostics must never reach stdout through this function: the JSON
    branch writes only ``json.dumps(payload, ...)``, so truncation is recorded INSIDE
    ``payload`` by projection, never echoed alongside it.

    CONTRACT: when ``sink`` is supplied, ``render_text`` must write only into that sink
    (``sink.console`` / ``sink.echo``). ``emit`` cannot enforce this for a caller-supplied
    callback -- ``tests/test_budget_boundary.py`` checks it per command.

    When ``sink`` is None the historical unbudgeted behaviour is preserved exactly.
    """
    if output_format == "json":
        rendered = json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii, default=default)
        if sink is None:
            click.echo(rendered)
        else:
            sink.echo(rendered)
        return
    render_text()


def emit_query_rows(
    *,
    output_format: str,
    title: str,
    columns: Sequence[tuple[str, str] | tuple[str, str, dict[str, Any]]],
    rows: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any] | None = None,
    renderers: Mapping[str, Callable[[Any, Mapping[str, Any]], Any]] | None = None,
    sink: BoundedSink | None = None,
) -> None:
    projected = project_rows(rows, sink.max_rows if sink is not None else None)
    rows_list = projected.rows

    payload: dict[str, Any] = {"format": "json", "rows": rows_list}
    if meta is not None:
        payload["meta"] = dict(meta)
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via if sink is not None else "",
        }

    def _render() -> None:
        table = Table(title=title)
        for col in columns:
            _, label, *rest = col
            col_kwargs: dict[str, Any] = rest[0] if rest else {}
            table.add_column(label, **col_kwargs)

        cell_renderers = renderers or {}
        for row in rows_list:
            cells: list[Any] = []
            for key, *_ in columns:
                value = row.get(key, "")
                renderer = cell_renderers.get(key)
                cells.append(renderer(value, row) if renderer is not None else str(value))
            table.add_row(*cells)

        if sink is None:
            get_console(file=click.get_text_stream("stdout")).print(table)
            return

        sink.console.print(table)
        if projected.truncated:
            sink.echo(f"showing {len(rows_list)} of {projected.total} rows")
            sink.echo(f"  complete output:  {sink.complete_via or '(pass --output PATH)'}")

    emit(output_format=output_format, payload=payload, render_text=_render, sink=sink)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_output_budgeting.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Verify every existing call site is unchanged**

Run: `cd science && uv run --frozen pytest -v`
Expected: PASS. `sink=None` must preserve byte-identical historical output.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/output.py science/tests/test_output_budgeting.py
git commit -m "feat(budget): route both emitter branches through the sink"
```

---

### Task 7: `tasks list` — both formats projected, working-set default, `--output`

**Files:**
- Modify: `science/src/science_tool/tasks_cli.py:487-605`
- Modify: `science/src/science_tool/tasks_display.py:70`
- Test: `science/tests/test_tasks_list_budget.py`

**Interfaces:**
- Consumes: `BoundedSink`, `lookup`, `build_complete_via`, `project_rows`.
- Produces: `render_tasks_table(tasks, resolver=None, sink=None, footer=None) -> None`;
  `tasks list --output PATH`.

**Both formats project.** The previous plan projected only JSON, so the table branch handed the
full list to the renderer and hit the char backstop. Here the command projects **once**, before
choosing a format, and both branches consume the same projected rows.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_tasks_list_budget.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.budget.registry import BUDGETS
from science_tool.budget.measure import visible_len
from science_tool.cli import main

TASKS = "\n".join(
    f"""## [t{i:03d}] Task {i} with a deliberately long title to exercise wrapping
- priority: P2
- status: {"active" if i < 3 else "proposed"}
- related: [question:q{i:04d}-a-long-question-slug, hypothesis:h{i:04d}-another-long-slug]
- created: 2026-01-01

Body for task {i}.
"""
    for i in range(200)
)


def _project(root: Path) -> None:
    (root / "science.yaml").write_text("id: demo\nname: demo\n")
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "active.md").write_text(TASKS)


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def test_default_list_shows_only_the_working_set() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = _invoke(["tasks", "list", "--format", "json"])
        assert result.exit_code == 0, result.output
        assert {row["status"] for row in json.loads(result.output)["rows"]} == {"active"}


def test_table_branch_is_projected_and_stays_within_budget() -> None:
    """The regression the previous plan missed: table output must project, not raise."""
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = _invoke(["tasks", "list", "--status", "proposed"])
        assert result.exit_code == 0, result.output
        assert visible_len(result.output) <= BUDGETS["tasks list"].max_chars
        assert "of 197 rows" in result.output


def test_table_footer_escape_preserves_the_user_selection() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = _invoke(["tasks", "list", "--status", "proposed"])
        assert "--status proposed" in result.output
        assert "--output" in result.output


def test_json_branch_stays_within_budget() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = _invoke(["tasks", "list", "--status", "proposed", "--format", "json"])
        assert result.exit_code == 0, result.output
        assert visible_len(result.output) <= BUDGETS["tasks list"].max_chars
        assert json.loads(result.output)["truncation"]["total"] == 197


def test_output_file_is_complete_in_json() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        root = Path(fs)
        _project(root)
        target = root / "tasks.json"
        result = _invoke(
            ["tasks", "list", "--status", "proposed", "--format", "json", "--output", str(target)]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(target.read_text())
        assert len(payload["rows"]) == 197
        assert "truncation" not in payload


def test_output_file_is_complete_in_table_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        root = Path(fs)
        _project(root)
        target = root / "tasks.txt"
        result = _invoke(["tasks", "list", "--status", "proposed", "--output", str(target)])
        assert result.exit_code == 0, result.output
        written = target.read_text()
        assert "t199" in written
        assert "of 197 rows" not in written  # complete, so no truncation footer
        assert str(target) in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_tasks_list_budget.py -v`
Expected: FAIL — `no such option: --output`

- [ ] **Step 3: Make `render_tasks_table` sink-owned**

In `science/src/science_tool/tasks_display.py`, add imports and replace the tail of
`render_tasks_table`:

```python
from science_tool.budget.sink import BoundedSink


def render_tasks_table(
    tasks: list[Task],
    resolver: ReadinessResolver | None = None,
    sink: BoundedSink | None = None,
    footer: list[str] | None = None,
) -> None:
    """Render a colored Rich table of tasks, through ``sink`` when one is supplied."""
    # ... table construction unchanged, through the add_row loop ...

    lines: list[str] = []
    if resolver is not None:
        for t in tasks:
            summary = render_blocker_summary(t, resolver)
            if summary is not None:
                lines.append(summary)
    lines.extend(footer or [])

    if sink is None:
        console = get_console()
        console.print(table)
        for line in lines:
            console.print(line)
        return

    sink.console.print(table)
    for line in lines:
        sink.echo(line)
```

Blocker summaries go through the same sink so they count against the command-total ceiling
instead of escaping it.

- [ ] **Step 4: Rewire the command**

In `science/src/science_tool/tasks_cli.py`, add the option:

```python
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
```

Add `output_path: Path | None` to the signature, then replace the body's tail:

```python
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    WORKING_SET = ("active", "blocked")

    matched = list_tasks(...)  # unchanged call
    if status is None and not show_all:
        matched = [t for t in matched if t.status in WORKING_SET]
    matched = sort_tasks(matched)

    complete_via = build_complete_via(click.get_current_context(), output_hint="tasks.json")
    sink = BoundedSink(
        lookup("tasks list"),
        output_path=output_path,
        command_path="tasks list",
        complete_via=complete_via,
    )
    try:
        if output_format == "json":
            # ... existing column/row construction, then:
            emit_query_rows(
                output_format=output_format,
                title="Tasks",
                columns=columns,
                rows=rows,
                meta=meta,
                sink=sink,
            )
        else:
            projected = project_rows(matched, sink.max_rows)
            footer = (
                [
                    f"showing {len(projected.rows)} of {projected.total} rows",
                    f"  complete output:  {complete_via}",
                ]
                if projected.truncated
                else []
            )
            render_tasks_table(list(projected.rows), resolver=resolver, sink=sink, footer=footer)
        sink.flush()
    finally:
        if output_path is not None:
            click.echo(f"wrote {len(matched)} tasks to {output_path}")
```

`project_rows` is generic over sequences, so it accepts the `Task` list directly for the table
branch and the dict rows for JSON.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_tasks_list_budget.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Run the task suite for regressions**

Run: `cd science && uv run --frozen pytest tests/test_tasks_cli.py tests/test_tasks.py tests/test_tasks_archive.py -v`
Expected: PASS. Tests asserting the old unfiltered default must pass an explicit `--status`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/tasks_cli.py science/src/science_tool/tasks_display.py science/tests/test_tasks_list_budget.py
git commit -m "feat(tasks): budget both list formats, default to the working set, add --output"
```

---

### Task 8: Extract `count_issues` so displayed and total are comparable

**Files:**
- Modify: `science/src/science_tool/graph/health.py:355-374`
- Test: `science/tests/test_health_count_issues.py`

**Interfaces:**
- Produces: `count_issues(report: Mapping[str, Any]) -> int` in `graph/health.py`.
  `build_health_report` computes `total_issues = count_issues(report_body)` instead of an inline
  sum.

**Why this task exists.** The previous plan computed `displayed_issues` as `len(kept)` summed
over sections. That is not the same quantity as `total_issues`, which counts `managed_artifacts`
only where `counts_as_issue`, folds `archive_lag` to `1 if lag_total`, and includes
`coverage_gaps` and `layered_claim_issue_count`. A footer comparing the two would compare
incompatible numbers. Extracting one counting function and running it over **both** the full and
the projected report makes them comparable by construction.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_health_count_issues.py
from __future__ import annotations

from science_tool.graph.health import count_issues


def _report(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "unresolved_refs": [],
        "unregistered_ref_kinds": [],
        "lingering_tags_lines": [],
        "agent_context": [],
        "identity_policy": [],
        "entity_identity": [],
        "dataset_anomalies": [],
        "schema_invalid": [],
        "tooling_scaffold": [],
        "validation": [],
        "managed_artifacts": [],
        "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
        "layered_claims": {"migration_issues": []},
        "cross_paper_evidence": {"findings": []},
        "prose_epistemics": {"findings": []},
    }
    base.update(overrides)
    return base


def test_empty_report_counts_zero() -> None:
    assert count_issues(_report()) == 0


def test_validation_rows_each_count() -> None:
    assert count_issues(_report(validation=[{"severity": "warning"}] * 7)) == 7


def test_managed_artifacts_count_only_when_flagged() -> None:
    artifacts = [{"counts_as_issue": True}, {"counts_as_issue": False}]
    assert count_issues(_report(managed_artifacts=artifacts)) == 1


def test_archive_lag_counts_as_one_regardless_of_magnitude() -> None:
    lag = {"done_in_active": 9, "retired_in_active": 4, "missing_completed": 2}
    assert count_issues(_report(archive_lag=lag)) == 1


def test_unresolved_refs_count() -> None:
    assert count_issues(_report(unresolved_refs=[{"ref": "a"}, {"ref": "b"}])) == 2


def test_nested_findings_count() -> None:
    report = _report(cross_paper_evidence={"findings": [{"severity": "error"}] * 3})
    assert count_issues(report) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_count_issues.py -v`
Expected: FAIL — `ImportError: cannot import name 'count_issues'`

- [ ] **Step 3: Extract the function**

In `science/src/science_tool/graph/health.py`, add above `build_health_report`:

```python
def count_issues(report: Mapping[str, Any]) -> int:
    """The single definition of "how many issues does this report contain".

    Used twice: once over the full report to produce ``total_issues`` (the clean-report
    gate), and once over the projected report to produce ``displayed_issues``. Running the
    SAME function over both is what makes "showing N of M" a comparison of like with like.

    Deliberately NOT a plain row count: ``managed_artifacts`` counts only where
    ``counts_as_issue``, and ``archive_lag`` is one issue however large the lag.
    """

    def _rows(key: str) -> list[Any]:
        value = report.get(key) or []
        return value if isinstance(value, list) else []

    def _findings(key: str) -> list[Any]:
        section = report.get(key) or {}
        findings = section.get("findings") if isinstance(section, dict) else None
        return findings if isinstance(findings, list) else []

    archive_lag = report.get("archive_lag") or {}
    lag_total = archive_lag_total(archive_lag) if isinstance(archive_lag, dict) else 0

    layered = report.get("layered_claims") or {}
    layered_issues = len(layered.get("migration_issues") or []) if isinstance(layered, dict) else 0

    return (
        len(_rows("unresolved_refs"))
        + len(_rows("unregistered_ref_kinds"))
        + len(_rows("lingering_tags_lines"))
        + len(_rows("agent_context"))
        + len(_rows("identity_policy"))
        + len(_rows("entity_identity"))
        + layered_issues
        + int(report.get("coverage_gaps") or 0)
        + len(_rows("dataset_anomalies"))
        + len(_rows("schema_invalid"))
        + (1 if lag_total else 0)
        + sum(1 for f in _rows("managed_artifacts") if isinstance(f, dict) and f.get("counts_as_issue"))
        + len(_rows("tooling_scaffold"))
        + len(_rows("validation"))
        + sum(1 for f in _findings("prose_epistemics") if not isinstance(f, dict) or f.get("counts_as_issue") is True)
        + len(_findings("cross_paper_evidence"))
    )
```

Then replace the inline `total_issues = (...)` sum at line 357 with:

```python
    total_issues = count_issues(
        {
            "unresolved_refs": unresolved_refs,
            "unregistered_ref_kinds": unregistered_ref_kinds,
            "lingering_tags_lines": lingering_tags_lines,
            "agent_context": agent_context,
            "identity_policy": identity_policy_findings,
            "entity_identity": entity_identity,
            "layered_claims": {"migration_issues": [None] * layered_claim_issue_count},
            "coverage_gaps": coverage_gaps,
            "dataset_anomalies": dataset_anomalies,
            "schema_invalid": schema_invalid,
            "archive_lag": archive_lag,
            "managed_artifacts": managed_artifacts,
            "tooling_scaffold": tooling_scaffold,
            "validation": validation,
            "prose_epistemics": {"findings": prose_epistemics_findings},
            "cross_paper_evidence": cross_paper_evidence,
        }
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_health_count_issues.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Verify `total_issues` is numerically unchanged**

Run: `cd science && uv run --frozen pytest -k health -v`
Expected: PASS. This refactor must not move any existing count.

Then against the real project:

```bash
cd ~/d/natural-systems && uv run --with-editable ~/d/science/science science health --format json | python3 -c "import json,sys; print(json.load(sys.stdin)['total_issues'])"
```

Expected: `366` — the value measured on 2026-07-24.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/health.py science/tests/test_health_count_issues.py
git commit -m "refactor(health): extract count_issues as the single issue-counting definition"
```

---

### Task 9: Health section classification and severity threshold

**Files:**
- Create: `science/src/science_tool/graph/health_projection.py`
- Test: `science/tests/test_health_projection.py`

**Interfaces:**
- Produces: `SEVERITY_SECTIONS`, `COUNTS_AS_ISSUE_SECTIONS`, `UNFILTERED_SECTIONS`,
  `NESTED_FINDING_SECTIONS`, `SCALAR_SECTIONS`, `SEVERITY_ORDER`,
  `meets_threshold(row, threshold) -> bool`, `UnknownSection(Exception)`.

**Classification, verified against the TypedDicts on 2026-07-24 — do not re-derive:**

| Signal | Sections |
|---|---|
| `severity` | `validation`, `schema_invalid` (`graph/health.py:43`), `dataset_anomalies`, `entity_identity` (`health_checks/entity_identity.py:13`), `cross_paper_evidence.findings` (`health_checks/cross_paper_evidence.py:15`), `prose_epistemics.findings` (`health_checks/prose_epistemics.py:41`, which also carries `counts_as_issue`) |
| `counts_as_issue` only | `managed_artifacts` (`project_artifacts/health_integration.py:20`) |
| neither | `agent_context`, `archive_lag`, `identity_policy`, `invalid_entity_aspects`, `layered_claims`, `legacy_task_type`, `lingering_tags_lines`, `unregistered_ref_kinds`, `unresolved_refs`, `tooling_scaffold`, `accepted_validation`, `unwired_checks` |

`counts_as_issue` is **issue-count membership**, never a display filter — the two are
orthogonal, and `prose_epistemics` emits `severity: "warning"` with `counts_as_issue: True`.

`--severity` is a **threshold**: `error` = errors only; `warn` = warnings and errors; `all` =
everything.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_health_projection.py
from __future__ import annotations

import pytest

from science_tool.graph.health_projection import (
    COUNTS_AS_ISSUE_SECTIONS,
    SEVERITY_SECTIONS,
    UNFILTERED_SECTIONS,
    meets_threshold,
)


def test_entity_identity_is_severity_bearing() -> None:
    assert "entity_identity" in SEVERITY_SECTIONS


def test_cross_paper_evidence_is_severity_bearing_not_counts_as_issue() -> None:
    assert "cross_paper_evidence" in SEVERITY_SECTIONS
    assert "cross_paper_evidence" not in COUNTS_AS_ISSUE_SECTIONS


def test_prose_epistemics_filters_on_severity() -> None:
    assert "prose_epistemics" in SEVERITY_SECTIONS


def test_managed_artifacts_is_counts_as_issue_only() -> None:
    assert "managed_artifacts" in COUNTS_AS_ISSUE_SECTIONS
    assert "managed_artifacts" not in SEVERITY_SECTIONS


def test_unwired_checks_is_never_filtered() -> None:
    assert "unwired_checks" in UNFILTERED_SECTIONS


def test_classifications_are_disjoint() -> None:
    assert not (SEVERITY_SECTIONS & COUNTS_AS_ISSUE_SECTIONS)
    assert not (SEVERITY_SECTIONS & UNFILTERED_SECTIONS)
    assert not (COUNTS_AS_ISSUE_SECTIONS & UNFILTERED_SECTIONS)


@pytest.mark.parametrize(
    ("severity", "threshold", "expected"),
    [
        ("warning", "warn", True),
        ("error", "warn", True),
        ("info", "warn", False),
        ("error", "error", True),
        ("warning", "error", False),
        ("info", "all", True),
        ("warning", "all", True),
    ],
)
def test_threshold_semantics(severity: str, threshold: str, expected: bool) -> None:
    assert meets_threshold({"severity": severity}, threshold) is expected


def test_counts_as_issue_never_filters_display() -> None:
    """A warning that counts as an issue is still hidden at --severity error."""
    assert meets_threshold({"severity": "warning", "counts_as_issue": True}, "error") is False


def test_row_without_severity_survives_every_threshold() -> None:
    assert meets_threshold({"code": "x"}, "error") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_projection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.health_projection'`

- [ ] **Step 3: Write the classification module**

```python
# science/src/science_tool/graph/health_projection.py
"""Health-report projection: section classification and severity thresholding.

Lives beside health rather than in ``budget/`` so the budgeting mechanism stays free of
domain knowledge.

The classification was verified against the TypedDicts on 2026-07-24 and getting it wrong
is not cosmetic: treating ``cross_paper_evidence`` as a ``counts_as_issue`` section hides
its errors entirely, because it has no such field.

``counts_as_issue`` is ISSUE-COUNT MEMBERSHIP, not severity. It decides whether a row
feeds ``count_issues`` and is never used to filter display -- the two are orthogonal, and
``prose_epistemics`` emits ``severity: "warning"`` together with ``counts_as_issue: True``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class UnknownSection(Exception):
    """A report section with no registered classification.

    Raised rather than guessed: silently capping an unrecognised section would be exactly
    the silent-degradation this program exists to remove.
    """


SEVERITY_SECTIONS = frozenset(
    {
        "validation",
        "schema_invalid",
        "dataset_anomalies",
        "entity_identity",
        "cross_paper_evidence",
        "prose_epistemics",
    }
)

COUNTS_AS_ISSUE_SECTIONS = frozenset({"managed_artifacts"})

UNFILTERED_SECTIONS = frozenset(
    {
        "agent_context",
        "archive_lag",
        "identity_policy",
        "invalid_entity_aspects",
        "layered_claims",
        "legacy_task_type",
        "lingering_tags_lines",
        "unregistered_ref_kinds",
        "unresolved_refs",
        "tooling_scaffold",
        "accepted_validation",
        # An unwired check DID NOT RUN. graph/health.py:60 keeps it out of total_issues so
        # a report containing one cannot claim the project is clean; hiding it behind a
        # severity default would defeat exactly that.
        "unwired_checks",
    }
)

# Sections whose rows live under a "findings" key rather than at the top level.
NESTED_FINDING_SECTIONS = frozenset({"cross_paper_evidence", "prose_epistemics"})

# Non-list sections that pass through untouched.
SCALAR_SECTIONS = frozenset({"total_issues", "coverage_gaps", "_meta"})

SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "warn": 1, "error": 2}

_THRESHOLD_FLOOR: dict[str, int] = {"all": 0, "warn": 1, "error": 2}


def meets_threshold(row: Mapping[str, Any], threshold: str) -> bool:
    """True when ``row`` is at or above ``threshold``.

    A row with no ``severity`` key survives every threshold: absence of the signal is not
    evidence of low severity, and dropping such rows would hide findings.
    """
    severity = row.get("severity")
    if severity is None:
        return True
    return SEVERITY_ORDER.get(str(severity), 2) >= _THRESHOLD_FLOOR[threshold]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_health_projection.py -v`
Expected: PASS (9 tests, 7 parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/health_projection.py science/tests/test_health_projection.py
git commit -m "feat(health): classify report sections and add severity thresholding"
```

---

### Task 10: Health per-section caps and comparable `displayed_issues`

**Files:**
- Modify: `science/src/science_tool/graph/health_projection.py`
- Test: `science/tests/test_health_projection_caps.py`

**Interfaces:**
- Consumes: `meets_threshold`, the section sets (Task 9), `count_issues` (Task 8).
- Produces: `SECTION_ROW_CAP: int`,
  `project_health_report(report, threshold, cap=None) -> dict[str, Any]`. Returns the same keys,
  adds `displayed_issues` (computed by `count_issues` over the projected report) and
  `section_omitted: dict[str, int]`, and leaves `total_issues` untouched.

**Severity does not solve the size problem.** All 361 of natural-systems' `validation` findings
are `severity: "warning"` against `total_issues` = 366, so an error-only default would show
nothing while announcing 366 issues. Row caps bound output; severity is a user lens. Default
threshold is `warn`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_health_projection_caps.py
from __future__ import annotations

import pytest

from science_tool.graph.health import count_issues
from science_tool.graph.health_projection import (
    SECTION_ROW_CAP,
    UnknownSection,
    project_health_report,
)


def _natural_systems_shaped_report() -> dict[str, object]:
    """All-warning validation against a non-zero total_issues -- the real 2026-07-24 shape."""
    return {
        "validation": [
            {"severity": "warning", "code": "document_structure", "message": f"m{i}"} for i in range(361)
        ],
        "managed_artifacts": [{"counts_as_issue": False, "name": "a"}],
        "unresolved_refs": [{"ref": "r1"}, {"ref": "r2"}],
        "archive_lag": {"done_in_active": 4, "retired_in_active": 0, "missing_completed": 1},
        "unwired_checks": [],
        "total_issues": 364,
    }


def test_default_warn_threshold_does_not_empty_an_all_warning_report() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert len(projected["validation"]) == SECTION_ROW_CAP


def test_section_omitted_records_what_was_dropped() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["section_omitted"]["validation"] == 361 - SECTION_ROW_CAP


def test_total_issues_is_never_rewritten() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["total_issues"] == 364


def test_displayed_issues_uses_the_same_counting_rules_as_total() -> None:
    """displayed_issues must be count_issues(projected), not a raw row count.

    The fixture's single managed_artifacts row has counts_as_issue=False, so it must NOT
    contribute; unresolved_refs and archive_lag must.
    """
    report = _natural_systems_shaped_report()
    projected = project_health_report(report, threshold="warn")
    assert projected["displayed_issues"] == count_issues(projected)
    # 40 validation + 2 unresolved_refs + 1 archive_lag; managed_artifacts excluded.
    assert projected["displayed_issues"] == SECTION_ROW_CAP + 3


def test_displayed_never_exceeds_total() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["displayed_issues"] <= projected["total_issues"]


def test_error_threshold_hides_warnings_but_reports_them_as_omitted() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="error")
    assert projected["validation"] == []
    assert projected["section_omitted"]["validation"] == 361
    assert projected["total_issues"] == 364


def test_unfiltered_sections_ignore_threshold_and_cap() -> None:
    report = _natural_systems_shaped_report()
    report["unwired_checks"] = [{"name": f"check{i}"} for i in range(100)]
    projected = project_health_report(report, threshold="error")
    assert len(projected["unwired_checks"]) == 100


def test_counts_as_issue_section_is_not_severity_filtered() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="error")
    assert len(projected["managed_artifacts"]) == 1


def test_nested_findings_are_projected_in_place() -> None:
    report = _natural_systems_shaped_report()
    report["cross_paper_evidence"] = {
        "status": "active",
        "findings": [{"severity": "error", "code": f"c{i}"} for i in range(100)],
    }
    projected = project_health_report(report, threshold="error")
    assert len(projected["cross_paper_evidence"]["findings"]) == SECTION_ROW_CAP
    assert projected["cross_paper_evidence"]["status"] == "active"


def test_unknown_list_section_refuses_rather_than_capping() -> None:
    report = _natural_systems_shaped_report()
    report["brand_new_check"] = [{"severity": "error"}] * 500
    with pytest.raises(UnknownSection, match="brand_new_check"):
        project_health_report(report, threshold="warn")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_projection_caps.py -v`
Expected: FAIL — `ImportError: cannot import name 'SECTION_ROW_CAP'`

- [ ] **Step 3: Add caps and the projector**

Append to `science/src/science_tool/graph/health_projection.py`:

```python
SECTION_ROW_CAP = 40


def _classified(section: str) -> str:
    if section in UNFILTERED_SECTIONS:
        return "unfiltered"
    if section in SEVERITY_SECTIONS:
        return "severity"
    if section in COUNTS_AS_ISSUE_SECTIONS:
        return "counts_as_issue"
    raise UnknownSection(
        f"health report section {section!r} has no classification. Add it to "
        f"SEVERITY_SECTIONS, COUNTS_AS_ISSUE_SECTIONS, or UNFILTERED_SECTIONS in "
        f"graph/health_projection.py. Refusing rather than guessing a cap."
    )


def _project_section(
    rows: list[Any],
    section: str,
    threshold: str,
    cap: int,
    omitted: dict[str, int],
) -> list[Any]:
    kind = _classified(section)
    if kind == "unfiltered":
        return rows

    if kind == "severity":
        kept = [row for row in rows if not isinstance(row, dict) or meets_threshold(row, threshold)]
    else:
        kept = list(rows)

    capped = kept[:cap]
    dropped = (len(rows) - len(kept)) + (len(kept) - len(capped))
    if dropped:
        omitted[section] = dropped
    return capped


def project_health_report(
    report: dict[str, Any],
    threshold: str,
    cap: int | None = None,
) -> dict[str, Any]:
    """Narrow a health report for display without changing what it claims.

    ``total_issues`` is copied through untouched: it is the clean-report gate
    (``graph/health_cli.py:158``) and redefining it as a displayed count would let a
    filtered report announce "Project is clean". ``displayed_issues`` is computed by
    ``count_issues`` over the PROJECTED report, so "showing N of M" compares like with
    like rather than a raw row count against an issue count.
    """
    from science_tool.graph.health import count_issues

    effective_cap = SECTION_ROW_CAP if cap is None else cap
    omitted: dict[str, int] = {}
    projected: dict[str, Any] = {}

    for key, value in report.items():
        if key in SCALAR_SECTIONS or not isinstance(value, (list, dict)):
            projected[key] = value
            continue

        if key in NESTED_FINDING_SECTIONS and isinstance(value, dict):
            findings = value.get("findings")
            if isinstance(findings, list):
                projected[key] = {
                    **value,
                    "findings": _project_section(findings, key, threshold, effective_cap, omitted),
                }
                continue

        if isinstance(value, list):
            projected[key] = _project_section(value, key, threshold, effective_cap, omitted)
            continue

        _classified(key)  # dict sections must still be classified
        projected[key] = value

    projected["displayed_issues"] = count_issues(projected)
    projected["section_omitted"] = omitted
    return projected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_health_projection_caps.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/health_projection.py science/tests/test_health_projection_caps.py
git commit -m "feat(health): add per-section caps and count_issues-based displayed_issues"
```

---

### Task 11: Wire every `health` output path through the sink

**Files:**
- Modify: `science/src/science_tool/graph/health_cli.py` — options, `--list-checks` branch
  (`:75-84`), `_render_report` (`:104-436`), the final `emit` (`:436`)
- Test: `science/tests/test_health_cli_budget.py`

**Interfaces:**
- Consumes: `project_health_report` (Task 10), `BoundedSink` (Task 3), `build_complete_via`
  (Task 5), `lookup` (Task 1).
- Produces: `science health --severity {error,warn,all}` (default `warn`), `health --output PATH`.

**This is the task the previous plan got most wrong.** `_render_report` writes 21 tables through
`get_console().print()` and many lines through `click.echo()`. Every one must become
`sink.console.print()` / `sink.echo()`, or table output escapes the sink and `--output` writes an
empty file. `--list-checks` needs the same treatment.

**`--output` is complete, so it receives the unprojected report** and, in table format, an
unprojected rendering.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_health_cli_budget.py
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main

REPORT = {
    "validation": [{"severity": "warning", "path": f"p{i}", "rule": "r", "message": "m" * 80} for i in range(361)],
    "managed_artifacts": [],
    "unresolved_refs": [],
    "unregistered_ref_kinds": [],
    "lingering_tags_lines": [],
    "agent_context": [],
    "identity_policy": [],
    "entity_identity": [],
    "dataset_anomalies": [],
    "schema_invalid": [],
    "tooling_scaffold": [],
    "accepted_validation": [],
    "unwired_checks": [],
    "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
    "layered_claims": {"migration_issues": []},
    "cross_paper_evidence": {"findings": []},
    "prose_epistemics": {"findings": []},
    "total_issues": 361,
}


@pytest.fixture
def stub_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_health_report is imported INSIDE health_command, so patch it at its source."""
    import science_tool.graph.health as health_module

    monkeypatch.setattr(health_module, "build_health_report", lambda *_a, **_k: dict(REPORT))


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def test_severity_and_output_options_exist() -> None:
    result = _invoke(["health", "--help"])
    assert result.exit_code == 0, result.output
    assert "--severity" in result.output
    assert "--output" in result.output


def test_table_output_stays_within_budget(stub_report: None) -> None:
    result = _invoke(["health"])
    assert result.exit_code == 0, result.output
    assert visible_len(result.output) <= BUDGETS["health"].max_chars


def test_json_output_stays_within_budget(stub_report: None) -> None:
    result = _invoke(["health", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert visible_len(result.output) <= BUDGETS["health"].max_chars


def test_filtered_report_never_claims_clean(stub_report: None) -> None:
    result = _invoke(["health", "--severity", "error"])
    assert result.exit_code == 0, result.output
    assert "Project is clean" not in result.output
    assert "361" in result.output


def test_table_output_file_is_non_empty_and_complete(stub_report: None, tmp_path: Path) -> None:
    """The defect the previous plan shipped: table + --output wrote nothing."""
    target = tmp_path / "health.txt"
    result = _invoke(["health", "--output", str(target)])
    assert result.exit_code == 0, result.output
    written = target.read_text()
    assert len(written) > BUDGETS["health"].max_chars
    assert "m" * 80 in written


def test_json_output_file_is_complete(stub_report: None, tmp_path: Path) -> None:
    target = tmp_path / "health.json"
    result = _invoke(["health", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())
    assert len(payload["validation"]) == 361
    assert "section_omitted" not in payload


def test_list_checks_also_routes_through_the_sink(tmp_path: Path) -> None:
    target = tmp_path / "checks.txt"
    result = _invoke(["health", "--list-checks", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert target.read_text().strip() != ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_cli_budget.py -v`
Expected: FAIL — `--severity` absent; the table `--output` test writes an empty file.

- [ ] **Step 3: Add the options and build the sink first**

In `health_command`, add:

```python
@click.option(
    "--severity",
    type=click.Choice(["error", "warn", "all"]),
    default="warn",
    show_default=True,
    help="Minimum severity to display. A THRESHOLD, not an equality filter: "
    "`warn` shows warnings AND errors.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout.",
)
```

Add `severity: str` and `output_path: Path | None` to the signature, and construct the sink at
the **top of the function**, before the `--list-checks` branch:

```python
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    sink = BoundedSink(
        lookup("health"),
        output_path=output_path,
        command_path="health",
        complete_via=build_complete_via(click.get_current_context(), output_hint="health.json"),
    )
```

- [ ] **Step 4: Route `--list-checks` through the sink**

```python
        def _render_checks() -> None:
            table = Table(title="Health checks")
            table.add_column("Check")
            table.add_column("Requires sources")
            table.add_column("Description")
            for row in available_checks:
                table.add_row(str(row["name"]), "yes" if row["requires_sources"] else "no", str(row["description"]))
            sink.console.print(table)

        emit(output_format=output_format, payload={"checks": available_checks}, render_text=_render_checks, sink=sink)
        sink.flush()
        return
```

- [ ] **Step 5: Route every `_render_report` output call through the sink**

Mechanical but must be exhaustive. In `_render_report`:

- Replace `console = get_console()` with nothing; use `sink.console` at each print site.
- Replace every `console.print(X)` with `sink.console.print(X)` — all 21 table sites plus the
  message prints.
- Replace every `click.echo(...)` that writes to **stdout** with `sink.echo(...)`. Leave the
  `err=True` timing echoes on stderr: stderr is not budgeted and not captured by `--output`.

Verify none were missed:

```bash
cd science && grep -n "console\.print\|click\.echo" src/science_tool/graph/health_cli.py | grep -v "sink\." | grep -v "err=True"
```

Expected: no output. Any line printed here is an output path that escapes the sink.

- [ ] **Step 6: Project for display, keep the file complete**

`_render_report` reads from a module-level-in-function `displayed` variable; the clean-report
gate keys off the untouched `report["total_issues"]`:

```python
    from science_tool.graph.health_projection import SECTION_ROW_CAP, project_health_report

    # --output is complete: no projection at all when writing to a file.
    displayed = report if output_path is not None else project_health_report(report, threshold=severity)

    def _render_report() -> None:
        ...
        total_issues = report["total_issues"]
        if total_issues == 0:
            # ... unchanged clean-report branch, via sink.echo ...
            return

        # ... section rendering, reading from `displayed` ...

        omitted = displayed.get("section_omitted") or {}
        if omitted:
            hidden = sum(omitted.values())
            sink.echo(
                f"showing {displayed['displayed_issues']} of {total_issues} issues "
                f"(severity: {severity}, cap: {SECTION_ROW_CAP}/section)"
            )
            sink.echo(f"  {hidden} finding(s) hidden — {sink.complete_via}")

    try:
        emit(output_format=output_format, payload=displayed, render_text=_render_report, sink=sink)
        sink.flush()
    finally:
        if output_path is not None:
            click.echo(f"wrote the complete health report to {output_path}")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_health_cli_budget.py -v`
Expected: PASS (7 tests)

- [ ] **Step 8: Run the health suite for regressions**

Run: `cd science && uv run --frozen pytest -k health -v`
Expected: PASS. Tests asserting the old unfiltered table must pass `--severity all`.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/graph/health_cli.py science/tests/test_health_cli_budget.py
git commit -m "feat(health): route all output through the sink, add --severity and --output"
```

---

### Task 12: Bulk dumps refuse stdout in both formats

**Files:**
- Modify: `science/src/science_tool/entities_inventory_cli.py:50-61`
- Modify: `science/src/science_tool/data_cli.py:49-90`
- Test: `science/tests/test_bulk_dump_refusal.py`

**Interfaces:**
- Consumes: `BoundedSink`, `lookup`, `build_complete_via`.
- Produces: `--output PATH` on both commands; both refuse when the stdout payload exceeds budget.

**`data audit`'s default format is text**, and the previous plan guarded only its JSON echoes.
Both branches route through the sink here. Note the two distinct `render_json` signatures:
`render_json(violations, outcomes, notes)` under `--fix`, `render_json(violations, notes=notes)`
otherwise.

`data audit` ends with `raise SystemExit(1)` when violations exist, so the flush must happen
**before** that exit.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_bulk_dump_refusal.py
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.budget.registry import BUDGETS
from science_tool.cli import main


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def _project(root: Path, entities: int) -> None:
    (root / "science.yaml").write_text("id: demo\nname: demo\n")
    questions = root / "entities" / "questions"
    questions.mkdir(parents=True)
    for i in range(entities):
        (questions / f"{i:04d}-q.md").write_text(
            f"---\nid: q{i:04d}\nkind: question\ntitle: Question {i}\n---\n\n" + ("body text " * 200)
        )


def test_small_inventory_prints_to_stdout(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=1)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["entities", "inventory"])
    assert result.exit_code == 0, result.output
    json.loads(result.output)


def test_oversized_inventory_is_refused_not_truncated(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=400)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["entities", "inventory"])
    assert result.exit_code != 0
    assert "--output" in result.output
    assert "schema_version" not in result.output  # no partial document leaked


def test_inventory_output_file_is_complete(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=400)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "inv.json"
    result = _invoke(["entities", "inventory", "--output", str(target)])
    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())
    assert payload["schema_version"] == "2"
    assert len(target.read_text()) > BUDGETS["entities inventory"].max_chars


def test_data_audit_text_branch_is_budgeted(tmp_path: Path, monkeypatch) -> None:
    """The default format is text; the previous plan guarded only JSON."""
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for i in range(3_000):
        (data_dir / f"stranded-record-with-a-long-name-{i:05d}.md").write_text("x")
    monkeypatch.chdir(tmp_path)
    result = _invoke(["data", "audit"])
    assert "--output" in result.output


def test_data_audit_output_file_is_complete_in_text_format(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for i in range(3_000):
        (data_dir / f"stranded-record-with-a-long-name-{i:05d}.md").write_text("x")
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.txt"
    result = _invoke(["data", "audit", "--output", str(target)])
    assert result.exit_code in (0, 1)
    assert len(target.read_text()) > BUDGETS["data audit"].max_chars
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_bulk_dump_refusal.py -v`
Expected: FAIL — `no such option: --output` on both commands.

- [ ] **Step 3: Wire `entities inventory`**

```python
@click.option("--output", type=click.Path(path_type=Path), default=None)
def entities_inventory_command(project_path: Path, output_format: str, output: Path | None) -> None:
    """Emit the versioned Science entity inventory for a project."""
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    inventory = build_inventory(project_path)
    rendered = inventory.model_dump_json(indent=2) + "\n"

    sink = BoundedSink(
        lookup("entities inventory"),
        output_path=output,
        command_path="entities inventory",
        complete_via=build_complete_via(click.get_current_context(), output_hint="inventory.json"),
    )
    sink.write(rendered)
    sink.flush()
    if output is not None:
        click.echo(f"wrote the entity inventory to {output}")
```

The sink raises `BudgetExceeded` before printing anything, so no partial `schema_version`
document can leak — which is why refusal, not truncation, is correct for this shape.

- [ ] **Step 4: Wire both `data audit` branches**

```python
@click.option("--output", "output_path", type=click.Path(path_type=Path), default=None)
def data_audit_command(
    project_path: Path | None,
    fix: bool,
    output_format: str,
    as_json: bool,
    output_path: Path | None,
) -> None:
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    # ... existing policy/violations/notes construction unchanged ...

    sink = BoundedSink(
        lookup("data audit"),
        output_path=output_path,
        command_path="data audit",
        complete_via=build_complete_via(click.get_current_context(), output_hint="audit.json"),
    )

    if fix:
        outcomes = apply_fixes(project_path, violations)
        if emit_json:
            sink.write(render_json(violations, outcomes, notes))
        else:
            performed = sum(1 for o in outcomes if o.performed)
            flagged = sum(1 for o in outcomes if not o.performed)
            for o in outcomes:
                mark = "moved" if o.performed else "FLAG"
                tgt = o.violation.proposed_target or "-"
                sink.echo(f"  [{mark}] {o.violation.path} → {tgt}" + (f"  ({o.reason})" if o.reason else ""))
            sink.echo(f"\n{performed} moved (staged, not committed), {flagged} flagged.")
        sink.flush()
        if output_path is not None:
            click.echo(f"wrote the data audit report to {output_path}")
        return

    if emit_json:
        sink.write(render_json(violations, notes=notes))
    else:
        for note in notes:
            sink.echo(f"  [{note.severity}:{note.code}] {note.message}")
        if not violations:
            sink.echo("clean: no data/results boundary violations.")
        for v in violations:
            tgt = v.proposed_target or "-"
            sink.echo(f"  [{v.quadrant.value}] {v.path} → {tgt}")

    sink.flush()
    if output_path is not None:
        click.echo(f"wrote the data audit report to {output_path}")
    if violations:
        raise SystemExit(1)
```

The flush precedes `raise SystemExit(1)` so the report is emitted before the non-zero exit.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_bulk_dump_refusal.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Run the affected suites**

Run: `cd science && uv run --frozen pytest -k "inventory or data_audit or data_cli" -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/entities_inventory_cli.py science/src/science_tool/data_cli.py science/tests/test_bulk_dump_refusal.py
git commit -m "feat(budget): route bulk dumps through the sink and refuse oversized stdout"
```

---

### Task 13: Guards and behavioural regression

**Files:**
- Create: `science/tests/test_budget_boundary.py`
- Create: `science/tests/test_budget_regression.py`

**Interfaces:**
- Consumes: `BUDGETS`, `EXEMPTIONS`, `DEFERRED` (Task 1); the Click tree at `science_tool.cli:main`.

Three guards, each stronger than the superseded plan's:

1. **Classification covers EVERY leaf command**, not only modules importing an emitter — so a
   command that prints via bare `click.echo` cannot escape.
2. **Sink routing is proven per command**, by locating the command's own callback function in
   the AST and requiring it to construct a `BoundedSink` — not by searching its module for a
   substring.
3. **Regression covers all four wired commands in both formats.**

- [ ] **Step 1: Write the guards**

```python
# science/tests/test_budget_boundary.py
"""Context-budget boundary guards (slice 1a).

Scope is DERIVED: guard 1 walks the live Click tree, so a new command fails until
classified; guard 2 locates each budgeted command's own callback in the AST rather than
grepping its module.

Known gap, stated rather than hidden: guard 2 proves the callback CONSTRUCTS a sink, not
that every branch inside it routes through one. ``tests/test_budget_regression.py`` is
what checks actual emitted sizes, and Task 11 Step 5 carries a grep for stray
``console.print`` / ``click.echo`` in the health renderer. This is a ratchet, not a
sandbox -- the same candid limit ``test_output_boundary.py`` documents.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import click

from science_tool.budget.registry import BUDGETS, DEFERRED, EXEMPTIONS
from science_tool.cli import main


def _leaf_commands(cmd: click.Command, path: list[str]) -> list[tuple[str, click.Command]]:
    if isinstance(cmd, click.Group):
        found: list[tuple[str, click.Command]] = []
        for name, sub in sorted(cmd.commands.items()):
            found.extend(_leaf_commands(sub, [*path, name]))
        return found
    return [(" ".join(path), cmd)]


def test_every_leaf_command_is_classified() -> None:
    """Every command is budgeted, exempt, or explicitly deferred -- no silent third state."""
    classified = set(BUDGETS) | set(EXEMPTIONS) | set(DEFERRED)
    unclassified = sorted(path for path, _ in _leaf_commands(main, []) if path not in classified)
    assert not unclassified, (
        f"{len(unclassified)} command(s) carry no budget, exemption, or deferral:\n  "
        + "\n  ".join(unclassified)
        + "\n\nAdd a CommandBudget (wired), an EXEMPTIONS reason (cannot grow), or a "
        "DeferredCommand (measured over budget, wiring scheduled)."
    )


def _callback_source(cmd: click.Command) -> str | None:
    callback = cmd.callback
    if callback is None:
        return None
    unwrapped = inspect.unwrap(callback)
    try:
        return inspect.getsource(unwrapped)
    except (OSError, TypeError):
        return None


def test_every_budgeted_command_constructs_its_own_sink() -> None:
    by_path = dict(_leaf_commands(main, []))
    missing: list[str] = []
    for command_path in sorted(BUDGETS):
        cmd = by_path.get(command_path)
        if cmd is None:
            missing.append(f"{command_path} (absent from the CLI tree)")
            continue
        source = _callback_source(cmd)
        if source is None:
            missing.append(f"{command_path} (callback source unavailable)")
            continue
        tree = ast.parse(inspect.cleandoc(source))
        constructs = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "BoundedSink"
            for node in ast.walk(tree)
        )
        if not constructs:
            missing.append(command_path)
    assert not missing, "Budgeted commands whose callback never constructs a BoundedSink:\n  " + "\n  ".join(missing)


def test_every_budgeted_command_offers_the_output_escape() -> None:
    by_path = dict(_leaf_commands(main, []))
    missing = [
        path
        for path in sorted(BUDGETS)
        if by_path.get(path) is None
        or not any("--output" in param.opts for param in by_path[path].params if isinstance(param, click.Option))
    ]
    assert not missing, "Budgeted commands with no --output escape:\n  " + "\n  ".join(missing)


def test_deferred_commands_are_real_cli_commands() -> None:
    known = {path for path, _ in _leaf_commands(main, [])}
    stale = sorted(set(DEFERRED) - known)
    assert not stale, "DEFERRED names commands that no longer exist:\n  " + "\n  ".join(stale)
```

- [ ] **Step 2: Run the guards to see what they surface**

Run: `cd science && uv run --frozen pytest tests/test_budget_boundary.py -v`
Expected: `test_every_leaf_command_is_classified` FAILS, listing every unclassified leaf command.
**This list is the work item, not a bug.**

- [ ] **Step 3: Classify everything the guard surfaced**

For each command in the failure output, add an `EXEMPTIONS` entry (if its output cannot grow
with project size) or a `DeferredCommand` (if it can). Measure before claiming an exemption:

```bash
cd ~/d/natural-systems && uv run --with-editable ~/d/science/science science <command> 2>/dev/null | wc -m
```

Use this reason format:

```python
    "graph stats": "measured 341 chars on 2026-07-24; fixed-shape summary",
```

Do not guess. An exemption is a claim, and the reason string is where the claim is recorded.
Mutating commands (`tasks add`, `graph build`, `entity create`, …) are exempt with the reason
`"mutating command; emits a fixed-size confirmation"` — but spot-check a few before writing it
across the board.

- [ ] **Step 4: Run the guards to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_budget_boundary.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write the behavioural regression suite**

```python
# science/tests/test_budget_regression.py
"""Actual emitted sizes for every wired command, in both formats.

The boundary guards prove classification and wiring; this proves size.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main

TASKS = "\n".join(
    f"""## [t{i:03d}] Task {i} with a deliberately long title to exercise wrapping behaviour
- priority: P2
- status: {"active" if i < 5 else "proposed"}
- related: [question:q{i:04d}-a-long-question-slug, hypothesis:h{i:04d}-another-long-slug]
- created: 2026-01-01

Body paragraph for task {i}, long enough to matter multiplied by the backlog size.
"""
    for i in range(400)
)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text(TASKS)
    entities = tmp_path / "entities" / "questions"
    entities.mkdir(parents=True)
    for i in range(300):
        (entities / f"{i:04d}-q.md").write_text(
            f"---\nid: q{i:04d}\nkind: question\ntitle: Question {i}\n---\n\n" + ("body " * 300)
        )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


@pytest.mark.parametrize(
    ("command_path", "args"),
    [
        ("tasks list", ["tasks", "list"]),
        ("tasks list", ["tasks", "list", "--status", "proposed"]),
        ("tasks list", ["tasks", "list", "--status", "proposed", "--format", "json"]),
        ("health", ["health"]),
        ("health", ["health", "--format", "json"]),
        ("health", ["health", "--severity", "all"]),
    ],
)
def test_command_stays_within_its_ceiling(project: Path, command_path: str, args: list[str]) -> None:
    result = _invoke(args)
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS[command_path].max_chars
    assert visible_len(result.output) <= ceiling, f"{args} emitted {visible_len(result.output)} > {ceiling}"


@pytest.mark.parametrize(
    ("args", "target_name"),
    [
        (["tasks", "list", "--status", "proposed", "--format", "json"], "tasks.json"),
        (["tasks", "list", "--status", "proposed"], "tasks.txt"),
        (["health", "--format", "json"], "health.json"),
        (["health"], "health.txt"),
        (["entities", "inventory"], "inventory.json"),
    ],
)
def test_output_file_is_written_and_non_empty(project: Path, args: list[str], target_name: str) -> None:
    target = project / target_name
    result = _invoke([*args, "--output", str(target)])
    assert result.exit_code in (0, 1), result.output
    assert target.is_file(), f"{args} --output wrote no file"
    assert target.stat().st_size > 0, f"{args} --output wrote an empty file"


def test_tasks_list_json_reports_the_full_total(project: Path) -> None:
    result = _invoke(["tasks", "list", "--status", "proposed", "--format", "json"])
    assert json.loads(result.output)["truncation"]["total"] == 395
```

- [ ] **Step 6: Run the regression suite**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression.py -v`
Expected: PASS (10 parametrized cases)

- [ ] **Step 7: Full suite, lint, types**

```bash
cd science
uv run --frozen pytest
uv run ruff check
uv run pyright
```

Expected: all green.

- [ ] **Step 8: Verify against the real project**

```bash
cd ~/d/natural-systems
uv run --with-editable ~/d/science/science science tasks list | wc -m
uv run --with-editable ~/d/science/science science health | wc -m
uv run --with-editable ~/d/science/science science health --output /tmp/h.txt && wc -m /tmp/h.txt
```

Expected: `tasks list` well under 20,000 (was 144,655); `health` well under 30,000 (was 426,926);
`/tmp/h.txt` far larger than 30,000, proving the file escape is complete.

- [ ] **Step 9: Commit**

```bash
git add science/tests/test_budget_boundary.py science/tests/test_budget_regression.py science/src/science_tool/budget/registry.py
git commit -m "test(budget): add classification, sink-construction, and size regression guards"
```

---

## Self-Review

**Spec coverage.** Core invariant (Tasks 3, 7, 11, 12); projection/sink split (3, 4, 10);
registry SSOT with shapes (1); command-total ceiling (3, tested explicitly); per-shape projection
with refusal for unregistered shapes (1, 10, 12); truncation visible in both formats (6, 11);
counting semantics (2); uniform `--output` (7, 11, 12, guarded in 13); working-set default (7);
health classification correction (9); severity as a threshold defaulting to `warn` (9, 10); row
caps as the real mechanism (10); `total_issues` invariance (8, 10, 11); comparable
`displayed_issues` (8, 10); `unwired_checks` never filtered (9, 10); all guards (13).

**Corrections to the superseded plan, each with a covering test.** Ten commands no longer
claimed to inherit budgets — they are in `DEFERRED` and guarded (Task 1, Task 13). `health`'s
text branch reaches the sink (Task 11 Steps 4–6, `test_table_output_file_is_non_empty_and_complete`).
`tasks list` projects both formats (Task 7, `test_table_branch_is_projected_and_stays_within_budget`).
`complete_via` derived from the invocation (Task 5, `test_user_selection_is_preserved`).
`displayed_issues` via `count_issues` (Task 8, `test_displayed_issues_uses_the_same_counting_rules_as_total`).
`data audit`'s text branch budgeted with the correct `render_json` signatures (Task 12).
Guards cover every leaf command and prove per-command sink construction (Task 13). The broken
monkeypatch is fixed: `stub_report` patches `science_tool.graph.health.build_health_report` at
its source, since `health_cli` imports it inside the function body.

**Type consistency.** `CommandBudget(max_chars, shape, max_rows)` used identically in Tasks 1, 3,
6, 13. `BoundedSink(budget, *, output_path, command_path, complete_via)` constructed identically
in Tasks 7, 11, 12. `ProjectedRows.rows/.omitted/.total/.truncated` consumed in Tasks 6, 7.
`meets_threshold(row, threshold)` (Task 9) called by `_project_section` (Task 10).
`count_issues(report)` (Task 8) called by `project_health_report` (Task 10) and its test.
`build_complete_via(ctx, *, output_hint)` (Task 5) used in Tasks 7, 11, 12. `visible_len` (Task 2)
used in Tasks 3, 7, 11, 13.

**Known limits, stated.** Guard 2 proves sink *construction*, not that every branch routes
through it — Task 11 Step 5's grep and the regression suite cover the rest. The `DEFERRED` table
is a bookkeeping ratchet: it prevents silence, not oversized output, and those ten commands stay
unbounded until 1b.

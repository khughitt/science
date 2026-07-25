# Context Budget — Slice 1a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the context-budget mechanism and wire it end-to-end, in **every supported**
output format, through the four commands that bypass the shared emitters — `tasks list`,
`health`, `entities inventory`, `data audit`.

**Architecture:** `BoundedSink` **is the payload channel**, not a wrapper around one branch of
`emit`. Every budgeted command constructs one sink, renders its complete payload into it (via
`sink.console` for Rich renderables and `sink.echo` for lines), and flushes once. Flush measures
the whole payload and either writes it to stdout, writes it complete to `--output PATH`, or
raises. Semantic narrowing happens earlier, in a **projection** chosen by the command's declared
payload shape; an unregistered shape refuses rather than degrading. After a successful
`--output` write, a command may emit one fixed-shape bounded control notice directly to
stdout; those notices are the sole sink-bypass exception.

**Tech Stack:** Python 3.11 (see Global Constraints), Click, Rich, Pydantic, pytest. All work is
in `science/`.

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
`data audit` wired completely in every supported format: table and JSON for `tasks list`,
`health`, and `data audit`; JSON only for `entities inventory`.

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
- **Python floor is 3.11** — `science/pyproject.toml:5` (`requires-python = ">=3.11"`, matched by
  `model/` and `qa/`) and `pyrightconfig.json:3` (`"pythonVersion": "3.11"`). PEP 695 syntax
  (`class Foo[T]`, `def f[T]()`) is a **3.12** feature and Pyright reports it as an error at this
  floor. Use `TypeVar` + `Generic`, as `instruments.py:27-31` and `output.py:15` already do.
- **stdout is always budgeted; `--output PATH` is always complete.** No flag makes stdout
  unbounded, and no projection ever runs against a file sink.
- **Semantic truncation never happens in the sink.** The sink routes, measures, raises.
- **`total_issues` never changes meaning.** It stays the unfiltered clean-report gate.
- **Every budgeted command owns exactly one sink** and emits no payload outside it. A single
  fixed-shape bounded control notice after a successful `--output` write is the sole exception.
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
| `budget/sink.py` | `BoundedSink` (the payload output channel), `BudgetExceeded`. |
| `budget/projection.py` | `project_rows`, `ProjectedRows`. |
| `budget/invocation.py` | `build_complete_via` — derives the escape command from the live Click context. |

**Modified:** `output.py` (both branches through the sink), `styles.py` (`width`),
`tasks_cli.py`, `tasks_display.py`, `graph/health_count.py` (extract `count_issues`),
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
  `DEFERRED: dict[str, DeferredCommand]`,
  `DeferredCommand(growth_reason: str, target_slice: str, measured_chars: int | None = None)`,
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


def test_every_deferred_entry_states_what_makes_it_grow() -> None:
    """DEFERRED is defined by growability, not by current size.

    The reason string is the mirror of an exemption's: it is the claim being recorded,
    and it is what stops the table becoming a parking lot.
    """
    for path, entry in DEFERRED.items():
        assert entry.growth_reason.strip(), f"{path} is deferred with no growth reason"
        assert entry.target_slice.strip(), f"{path} is deferred with no target slice"


def test_the_ten_measured_offenders_are_deferred() -> None:
    measured = {
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
    assert measured <= set(DEFERRED)
    for path in measured:
        assert (DEFERRED[path].measured_chars or 0) > 20_000


def test_a_growable_but_small_command_can_be_deferred() -> None:
    """tasks archive emits one row per archivable task but measures tiny.

    It is not exempt (its output grows) and has no over-threshold measurement, so the
    taxonomy must still have a truthful home for it.
    """
    entry = DEFERRED["tasks archive"]
    assert entry.measured_chars is None
    assert entry.growth_reason.strip()


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
- ``DEFERRED``  -- CAN grow with project size, not yet wired.

``DEFERRED`` is defined by growability, not by current size. An earlier draft required a
measurement above 20k, which left no truthful home for a command that grows but happens
to be small today -- ``tasks archive`` emits one row per archivable task
(``tasks_cli.py:333``) yet measures tiny on a freshly-archived project. Calling that
exempt would assert something false. Every non-budgeted command therefore carries a
justification string either way: ``EXEMPTIONS`` says why it cannot grow, ``DEFERRED``
says what makes it grow.
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
    """A command whose output grows with project size but is not yet wired.

    ``growth_reason`` states WHAT makes it grow -- the mirror of an exemption's reason.
    ``measured_chars`` records an observation, not a threshold for admission.
    """

    growth_reason: str
    target_slice: str
    measured_chars: int | None = None


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
    # Measured over budget on 2026-07-24; wiring scheduled for slice 1b.
    "entity list": DeferredCommand("one row per entity", "1b", 1_706_994),
    "curate inventory": DeferredCommand("one record per entity", "1b", 683_657),
    "prose lint": DeferredCommand("one row per prose finding", "1b", 550_226),
    "questions list": DeferredCommand("one row per question", "1b", 113_076),
    "validate": DeferredCommand("one row per validation finding", "1b", 109_466),
    "interpretations list": DeferredCommand("one row per interpretation", "1b", 97_281),
    "curate consolidation-candidates": DeferredCommand("one row per candidate cluster", "1b", 71_553),
    "entity needs-review": DeferredCommand("one row per flagged entity", "1b", 59_697),
    "feedback list": DeferredCommand("one row per feedback item", "1b", 44_307),
    "discussions list": DeferredCommand("one row per discussion", "1b", 30_780),
    # Growable but small on the audited project -- the case that has no truthful
    # exemption. Populated further by Task 13 Step 3.
    "tasks archive": DeferredCommand("one row per archivable task", "1b"),
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
from science_tool.styles import get_console


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

### Task 3: `BoundedSink` as the payload output channel

**Files:**
- Create: `science/src/science_tool/budget/sink.py`
- Test: `science/tests/test_budget_sink.py`

**Interfaces:**
- Consumes: `CommandBudget` (Task 1), `visible_len`, `BUDGET_CONSOLE_WIDTH` (Task 2).
- Produces: `BudgetExceeded(click.ClickException)`,
  `BoundedSink(budget, *, output_path=None, command_path="", complete_via="")` with
  `.console: Console`, `.echo(text: str = "") -> None`, `.write(text: str) -> None`,
  `.reserve_output() -> AbstractContextManager[None]`, `.flush() -> None`,
  `.is_file_sink: bool`, `.max_rows: int | None`, `.complete_via: str`.

`complete_via` is conditionally required: constructing a **budgeted stdout** sink without it
fails immediately. A file sink is already the complete-output route, and an unbudgeted sink has
no ceiling to escape, so neither needs one. There is no synthesized
`"<command> --output PATH"` fallback.

**The sink is the payload channel.** Commands render Rich renderables via
`sink.console.print(...)` and lines via `sink.echo(...)`. The entire payload accumulates in one
buffer and is measured once at `flush()`. This is what makes a 21-table command obey one
command-payload ceiling, and what makes `--output` capture the complete payload rather than only
its JSON branch. A fixed-shape bounded control notice emitted only after a successful file
write is control output, not payload, and is the sole permitted bypass.

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
TASKS_COMPLETE = "science tasks list --output tasks.json"
HEALTH_COMPLETE = "science health --output health.json"


def test_echo_reaches_stdout_only_after_flush(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    sink.echo("hello")
    assert capsys.readouterr().out == ""
    sink.flush()
    assert capsys.readouterr().out == "hello\n"


def test_console_output_is_captured_by_the_sink(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    table = Table(title="T")
    table.add_column("C")
    table.add_row("x")
    sink.console.print(table)
    sink.flush()
    assert "┏" in capsys.readouterr().out


def test_console_uses_the_pinned_width() -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    assert sink.console.width == BUDGET_CONSOLE_WIDTH


def test_over_budget_flush_prints_nothing_and_raises(capsys) -> None:
    sink = BoundedSink(
        CommandBudget(max_chars=10, shape=PayloadShape.ROWS, max_rows=5),
        command_path="tasks list",
        complete_via=TASKS_COMPLETE,
    )
    sink.echo("x" * 50)
    with pytest.raises(BudgetExceeded) as excinfo:
        sink.flush()
    assert capsys.readouterr().out == ""
    assert "tasks list" in str(excinfo.value)
    assert "--output" in str(excinfo.value)


def test_many_sections_share_one_command_total_ceiling() -> None:
    sink = BoundedSink(
        CommandBudget(max_chars=100, shape=PayloadShape.REPORT),
        command_path="health",
        complete_via=HEALTH_COMPLETE,
    )
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
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    assert sink.max_rows == 5


def test_budgeted_stdout_sink_requires_complete_via() -> None:
    with pytest.raises(ValueError, match="complete_via"):
        BoundedSink(ROWS_BUDGET, command_path="tasks list")


def test_unbudgeted_command_is_unbounded(capsys) -> None:
    sink = BoundedSink(None, command_path="tasks add")
    sink.echo("z" * 100_000)
    sink.flush()
    assert len(capsys.readouterr().out) == 100_001


def test_ansi_does_not_count_against_the_ceiling(capsys) -> None:
    sink = BoundedSink(
        CommandBudget(max_chars=12, shape=PayloadShape.ROWS, max_rows=5),
        command_path="tasks list",
        complete_via=TASKS_COMPLETE,
    )
    sink.echo("\x1b[1;31m" + "x" * 9 + "\x1b[0m")
    sink.flush()
    assert "x" * 9 in capsys.readouterr().out


def test_flush_is_idempotent(capsys) -> None:
    sink = BoundedSink(ROWS_BUDGET, command_path="tasks list", complete_via=TASKS_COMPLETE)
    sink.echo("once")
    sink.flush()
    sink.flush()
    assert capsys.readouterr().out == "once\n"


```

The sink has **no size-preflight method**. An earlier draft added `flush_check()` so that
`data audit --fix` could measure before mutating. That was unsound: the post-fix report is not
bounded by anything measurable pre-fix (see Task 12), so a passing size check promised nothing.
It does expose `reserve_output()` for mutation flows: entering that context creates a writable
same-directory temporary file without touching the final destination. This is a path/writability
reservation, not a speculative payload measurement.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_sink.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget.sink'`

- [ ] **Step 3: Write the sink**

```python
# science/src/science_tool/budget/sink.py
"""The payload output channel for budgeted commands.

A budgeted command constructs ONE sink, renders its complete payload into it, and flushes
once. Rich renderables go through ``sink.console``; plain lines through ``sink.echo``. No
payload reaches stdout until ``flush()``. After a successful file flush, a command may emit
one fixed-shape bounded control notice directly; that notice is the sole exception.

Why a channel rather than a wrapper around ``emit``'s JSON branch: a command like
``health`` renders 21 tables and a dozen messages directly. Wrapping only the final
serialization would leave all of that on stdout and write an empty ``--output`` file.
Owning the channel is what makes the ceiling payload-total and ``--output`` complete.

The sink holds characters, not rows, so it never truncates: it cannot count omitted items
nor cut without severing a table box or an ANSI escape. Semantic narrowing belongs in
projection, which runs before anything is rendered. A projected payload that still
exceeds its ceiling is a budget misconfiguration, so ``flush()`` raises -- printing
nothing rather than a misleading prefix.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
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
        if budget is not None and output_path is None and not complete_via:
            raise ValueError("complete_via is required for a budgeted stdout sink")
        self._budget = budget
        self._output_path = output_path
        self._command_path = command_path
        self._complete_via = complete_via
        self._buffer = StringIO()
        self._console: Console | None = None
        self._flushed = False
        self._reserved_path: Path | None = None

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

    @contextmanager
    def reserve_output(self) -> Iterator[None]:
        """Reserve a writable sibling temp before a mutation-before-report flow."""
        if self._output_path is None:
            raise ValueError("reserve_output requires a file sink")
        if self._reserved_path is not None:
            raise RuntimeError("output is already reserved")
        reserved = self._create_temp_path()
        self._reserved_path = reserved
        try:
            yield
        finally:
            reserved.unlink(missing_ok=True)
            self._reserved_path = None

    def flush(self) -> None:
        if self._flushed:
            return
        text = self._buffer.getvalue()

        if self._output_path is not None:
            self._flush_file(text)
            self._flushed = True
            return

        if self._budget is not None:
            size = visible_len(text)
            if size > self._budget.max_chars:
                raise self._exceeded(size)

        click.echo(text, nl=False)
        self._flushed = True

    def _create_temp_path(self) -> Path:
        assert self._output_path is not None
        if self._output_path.is_dir():
            raise IsADirectoryError(f"{self._output_path} is a directory")
        parent = self._output_path.parent
        if not parent.is_dir():
            raise FileNotFoundError(f"output parent does not exist: {parent}")
        fd, raw_path = tempfile.mkstemp(
            dir=parent,
            prefix=f".{self._output_path.name}.",
            suffix=".tmp",
        )
        os.close(fd)
        return Path(raw_path)

    def _flush_file(self, text: str) -> None:
        assert self._output_path is not None
        temp_path = self._reserved_path or self._create_temp_path()
        try:
            with temp_path.open("w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self._output_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _exceeded(self, size: int) -> BudgetExceeded:
        assert self._budget is not None
        return BudgetExceeded(
            f"{self._command_path or 'command'} produced {size} visible chars after "
            f"projection, over its {self._budget.max_chars} ceiling. "
            f"Nothing was printed. For the complete payload run:\n  {self._complete_via}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_budget_sink.py -v`
Expected: PASS (12 tests)


- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/budget/sink.py science/tests/test_budget_sink.py
git commit -m "feat(budget): make BoundedSink the payload channel for budgeted commands"
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


def test_projection_is_generic_over_non_mapping_rows() -> None:
    """tasks list projects Task models, which are Pydantic BaseModels, not Mappings."""
    from datetime import date

    from science_model.tasks import Task

    tasks = [Task(id=f"t{i:03d}", title=f"Task {i}", created=date(2026, 1, 1)) for i in range(10)]
    result = project_rows(tasks, max_rows=4)
    assert len(result.rows) == 4
    assert all(isinstance(row, Task) for row in result.rows)
    assert result.total == 10
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

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

RowT = TypeVar("RowT")


@dataclass(frozen=True)
class ProjectedRows(Generic[RowT]):
    """Generic over the row type.

    ``tasks list`` projects ``Task`` models for its table branch and dicts for its JSON
    branch; a ``Mapping``-only signature would be a type error at the first call site.

    ``TypeVar`` + ``Generic`` rather than PEP 695 ``class ProjectedRows[T]``: the packages
    declare ``requires-python = ">=3.11"`` and Pyright is pinned to 3.11, where the PEP 695
    form is a syntax-level error. ``output.py:15`` and ``instruments.py:31`` use the same
    construction.
    """

    rows: list[RowT]
    omitted: int
    total: int

    @property
    def truncated(self) -> bool:
        return self.omitted > 0


def project_rows(rows: Sequence[RowT], max_rows: int | None) -> ProjectedRows[RowT]:
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

import shlex

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


def test_values_with_spaces_are_quoted() -> None:
    out = _run(["list", "--status", "needs review"])
    assert "'needs review'" in out
    assert out == "science list --status 'needs review' --output out.json"


def test_shell_metacharacters_are_quoted() -> None:
    out = _run(["list", "--status", "a;rm -rf b"])
    assert shlex.split(out)[3] == "a;rm -rf b"
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

import shlex

import click

_OUTPUT_PARAMS = frozenset({"output_path", "output"})


def build_complete_via(ctx: click.Context, *, output_hint: str) -> str:
    """Return ``<command path> <non-default options> --output <hint>``, shell-safe.

    Values are quoted with ``shlex.join``: the caller's shell already protected a path or
    filter containing spaces, and reconstructing the command by naive joining would strip
    that protection and advertise a command that does something different.

    The command path itself is not quoted -- it is a sequence of literal words, and
    quoting it would produce ``'science tasks list'`` as one token.
    """
    tokens: list[str] = []
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
            tokens.append(flag)
        elif isinstance(value, (list, tuple)):
            for item in value:
                tokens.extend([flag, str(item)])
        else:
            tokens.extend([flag, str(value)])

    tokens.extend(["--output", output_hint])
    return f"{ctx.command_path} {shlex.join(tokens)}"
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
COMPLETE_VIA = "science tasks list --output tasks.json"


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
    sink = BoundedSink(BIG, command_path="tasks list", complete_via=COMPLETE_VIA)
    _emit_rows("json", sink)
    sink.flush()
    json.loads(capsys.readouterr().out)


def test_untruncated_json_has_no_truncation_key(capsys) -> None:
    budget = CommandBudget(max_chars=500_000, shape=PayloadShape.ROWS, max_rows=500)
    sink = BoundedSink(budget, command_path="tasks list", complete_via=COMPLETE_VIA)
    _emit_rows("json", sink)
    sink.flush()
    assert "truncation" not in json.loads(capsys.readouterr().out)


def test_returned_count_is_reconciled_with_the_projected_rows(capsys) -> None:
    """The caller computes it pre-projection; the emitter owns the final row count."""
    sink = BoundedSink(BIG, command_path="tasks list", complete_via=COMPLETE_VIA)
    emit_query_rows(
        output_format="json",
        title="Tasks",
        columns=COLUMNS,
        rows=ROWS,
        meta={"returned_count": len(ROWS), "active_total": 100},
        sink=sink,
    )
    sink.flush()
    payload = json.loads(capsys.readouterr().out)
    assert payload["meta"]["returned_count"] == 40 == len(payload["rows"])
    assert payload["meta"]["active_total"] == 100  # unrelated meta is untouched
    assert payload["truncation"]["total"] == 100  # the pre-projection count still travels


def test_meta_without_returned_count_is_passed_through(capsys) -> None:
    sink = BoundedSink(BIG, command_path="tasks list", complete_via=COMPLETE_VIA)
    emit_query_rows(
        output_format="json",
        title="Tasks",
        columns=COLUMNS,
        rows=ROWS,
        meta={"sort_order": "status_rank,id"},
        sink=sink,
    )
    sink.flush()
    assert json.loads(capsys.readouterr().out)["meta"] == {"sort_order": "status_rank,id"}


def test_table_branch_reaches_the_sink_not_stdout(capsys) -> None:
    """The text branch must be captured by the sink, not printed directly."""
    sink = BoundedSink(BIG, command_path="tasks list", complete_via=COMPLETE_VIA)
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
    sink = BoundedSink(budget, command_path="tasks list", complete_via=COMPLETE_VIA)
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
        meta_out = dict(meta)
        # This function owns the projection, so it owns the row count. `returned_count`
        # means "rows in THIS payload"; a caller computing it before projection would
        # report 366 next to 40 rows. Reconciling here is the only way the two cannot
        # disagree.
        if "returned_count" in meta_out:
            meta_out["returned_count"] = len(rows_list)
        payload["meta"] = meta_out
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
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=output_format, payload=payload, render_text=_render, sink=sink)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_output_budgeting.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Verify every existing call site is unchanged**

Run: `cd science && uv run --frozen pytest -v`
Expected: PASS. `sink=None` must preserve byte-identical historical output.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/output.py science/tests/test_output_budgeting.py
git commit -m "feat(budget): route both emitter branches through the sink"
```

---

### Task 7: `tasks list` — both supported formats projected, working-set default, `--output`

**Files:**
- Modify: `science/src/science_tool/tasks_cli.py:487-605`
- Modify: `science/src/science_tool/tasks_display.py:70`
- Test: `science/tests/test_tasks_list_budget.py`

**Interfaces:**
- Consumes: `BoundedSink`, `lookup`, `build_complete_via`, `project_rows`.
- Produces: `render_tasks_table(tasks, resolver=None, sink=None, footer=None) -> None`;
  `tasks list --output PATH`.

**Both supported formats project.** The previous plan projected only JSON, so the table branch
handed the full list to the renderer and hit the char backstop. Here the command projects
**once**, before choosing a format, and both branches consume the same projected rows.

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

Blocker summaries go through the same sink so they count against the command-payload ceiling
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
    if output_format == "json":
        # ... existing column/row construction, then:
        #
        # The default is no longer "everything except done/retired" -- it is the working
        # set -- so `applied_filters` must say what was actually applied. Replace the
        # `exclude_status` line at tasks_cli.py:595:
        #
        #     if not show_all and status is None:
        #         applied_filters["only_status"] = list(WORKING_SET)
        #
        # `exclude_status` is dropped rather than kept alongside: retaining a key that
        # names two of the four excluded statuses would be a more precise-looking lie
        # than omitting it. Its one consumer is test_tasks_cli.py:398, updated in Step 6.
        #
        # `returned_count` stays as the caller computes it; `emit_query_rows` reconciles
        # it against the projected rows (Task 6).
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
        render_tasks_table(projected.rows, resolver=resolver, sink=sink, footer=footer)

    sink.flush()
    # This fixed-shape bounded control notice is intentionally outside the payload sink.
    # allowed only AFTER a successful file flush, never in `finally`: a `finally` here would announce
    # "wrote ..." even when rendering raised or the write failed, reporting success for
    # a file that may not exist.
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
Expected: PASS. Two known updates, both consequences of the narrowed default:

- `test_tasks_cli.py:398` asserts `meta["applied_filters"]["exclude_status"] == ["done", "retired"]`.
  Change to `meta["applied_filters"]["only_status"] == ["active", "blocked"]`.
- `test_tasks_cli.py:394` asserts `meta["returned_count"] == 1`. That fixture is well under 40
  rows, so projection is a no-op and the assertion holds unchanged — but confirm it, because a
  silent change here would mean the reconciliation is firing when it should not.

Any other test asserting the old unfiltered default must pass an explicit `--status` or `--all`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/tasks_cli.py science/src/science_tool/tasks_display.py science/tests/test_tasks_list_budget.py
git commit -m "feat(tasks): budget both supported list formats, default to the working set, add --output"
```

---

### Task 8: Extract `count_issues` so displayed and total are comparable

**Files:**
- Create: `science/src/science_tool/graph/health_count.py` — strict counting and its
  validation helpers
- Modify: `science/src/science_tool/graph/health.py` — the typing import (`:12`), the
  `layered_claim_issue_count` / `coverage_gaps` locals and their loop (`:342-351`), the inline
  `total_issues` sum (`:353-374`), and the `layered_claims` entry of the report literal (`:365-370`)
- Test: `science/tests/test_health_count_issues.py`

**Interfaces:**
- Produces: `count_issues(report: Mapping[str, Any]) -> int` in `graph/health_count.py`.
  `graph/health.py` imports it privately as `_count_issues`; it does not re-export the helper.
  `build_health_report` assembles a real `HealthReport` with a placeholder total and then sets
  `report["total_issues"] = _count_issues(report)`, replacing the inline sum.

**Why this task exists.** The previous plan computed `displayed_issues` as `len(kept)` summed
over sections — not the same quantity as `total_issues`, which counts `managed_artifacts` only
where `counts_as_issue` and folds `archive_lag` to `1 if lag_total`.

**`count_issues` must consume the report's real shape, not a normalized one.** An earlier draft
of this task called it with a synthetic dict that flattened `layered_claim_issue_count` into
`layered_claims["migration_issues"]` and passed a top-level `coverage_gaps`. Neither exists in
the actual report: `layered_claims` is a `LayeredClaimHealthReport` (`graph/health.py:185`) with
four keys, `layered_claim_issue_count = len(migration_issues) + len(rival_model_gaps)`
(`health.py:342`), and `coverage_gaps` is a **local** derived from the two `CoverageMetric`
fields — it is never a report key. Calling `count_issues(projected)` on that synthetic contract
would have silently dropped rival-model gaps and every coverage gap, leaving the two counts
incomparable exactly as before.

So: `count_issues` reads `layered_claims` as the real TypedDict, and `build_health_report`
assembles the actual report body **first** and calls the same function on it. It accepts the
complete `HealthReport` shape and the same shape after projection (which only narrows registered
lists and adds metadata). Missing required sections, wrong section types, and malformed required
nested fields raise immediately; none are normalized to empty collections or zero. Every row
list must contain mappings, and the `counts_as_issue` fields used for managed-artifact and prose
counting must exist and be boolean.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_health_count_issues.py
from __future__ import annotations

import pytest

from science_tool.graph.health_count import count_issues


def _report(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "unresolved_refs": [],
        "unregistered_ref_kinds": [],
        "lingering_tags_lines": [],
        "agent_context": [],
        "identity_policy": [],
        "entity_identity": [],
        "legacy_task_type": [],
        "invalid_entity_aspects": [],
        "dataset_anomalies": [],
        "schema_invalid": [],
        "tooling_scaffold": [],
        "validation": [],
        "accepted_validation": [],
        "unwired_checks": [],
        "managed_artifacts": [],
        "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
        "layered_claims": _layered(),
        "cross_paper_evidence": {
            "status": "ok",
            "empty_state": "no_propositions",
            "summary": {},
            "findings": [],
            "propositions": [],
        },
        "prose_epistemics": {
            "applicable": False,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [],
        },
        "total_issues": 0,
    }
    base.update(overrides)
    return base


def _layered(**overrides: object) -> dict[str, object]:
    """The real LayeredClaimHealthReport shape (graph/health.py:185) -- all four keys."""
    base: dict[str, object] = {
        "proposition_claim_layer_coverage": {"numerator": 0, "denominator": 0, "fraction": 0.0},
        "causal_leaning_identification_coverage": {"numerator": 0, "denominator": 0, "fraction": 0.0},
        "rival_model_packets_missing_discriminating_predictions": [],
        "migration_issues": [],
    }
    base.update(overrides)
    return base


def test_empty_report_counts_zero() -> None:
    assert count_issues(_report()) == 0


def test_health_aggregator_does_not_reexport_count_issues() -> None:
    from science_tool.graph import health

    assert not hasattr(health, "count_issues")


def test_rival_model_gaps_count_alongside_migration_issues() -> None:
    """health.py:342 sums BOTH lists into layered_claim_issue_count."""
    layered = _layered(
        migration_issues=[{"proposition": "p"}],
        rival_model_packets_missing_discriminating_predictions=[{"proposition": "p", "packet_id": "k"}] * 2,
    )
    assert count_issues(_report(layered_claims=layered)) == 3


def test_each_incomplete_coverage_metric_counts_as_one_gap() -> None:
    """coverage_gaps is derived from the two CoverageMetrics, not a report key."""
    layered = _layered(
        proposition_claim_layer_coverage={"numerator": 3, "denominator": 10, "fraction": 0.3},
        causal_leaning_identification_coverage={"numerator": 5, "denominator": 5, "fraction": 1.0},
    )
    assert count_issues(_report(layered_claims=layered)) == 1


def test_complete_coverage_contributes_no_gap() -> None:
    layered = _layered(
        proposition_claim_layer_coverage={"numerator": 4, "denominator": 4, "fraction": 1.0},
        causal_leaning_identification_coverage={"numerator": 5, "denominator": 5, "fraction": 1.0},
    )
    assert count_issues(_report(layered_claims=layered)) == 0


def test_zero_denominator_coverage_contributes_no_gap() -> None:
    """An empty denominator means "nothing to cover", not "a gap"."""
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
    cross_paper = {
        "status": "fail",
        "empty_state": "active",
        "summary": {},
        "findings": [{"severity": "error"}] * 3,
        "propositions": [],
    }
    report = _report(cross_paper_evidence=cross_paper)
    assert count_issues(report) == 3


@pytest.mark.parametrize(
    "key",
    ["validation", "archive_lag", "layered_claims", "cross_paper_evidence", "prose_epistemics"],
)
def test_missing_required_section_is_rejected(key: str) -> None:
    report = _report()
    del report[key]
    with pytest.raises(ValueError, match=key):
        count_issues(report)


@pytest.mark.parametrize(
    ("key", "value"),
    [("validation", {}), ("archive_lag", []), ("layered_claims", [])],
)
def test_wrong_section_type_is_rejected(key: str, value: object) -> None:
    with pytest.raises(TypeError, match=key):
        count_issues(_report(**{key: value}))


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("cross_paper_evidence", {}),
        ("cross_paper_evidence", {"findings": {}}),
        ("prose_epistemics", {}),
        ("prose_epistemics", {"findings": None}),
    ],
)
def test_nested_findings_must_exist_and_be_a_list(section: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError), match="findings"):
        count_issues(_report(**{section: value}))


@pytest.mark.parametrize(
    "key",
    ["migration_issues", "rival_model_packets_missing_discriminating_predictions"],
)
def test_layered_issue_lists_are_required(key: str) -> None:
    layered = _layered()
    del layered[key]
    with pytest.raises(ValueError, match=key):
        count_issues(_report(layered_claims=layered))


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        ("proposition_claim_layer_coverage", {"numerator": 0, "fraction": 1.0}),
        ("causal_leaning_identification_coverage", {"numerator": "zero", "denominator": 0, "fraction": 1.0}),
    ],
)
def test_coverage_metrics_reject_missing_or_wrong_typed_fields(metric: str, value: object) -> None:
    layered = _layered(**{metric: value})
    with pytest.raises((TypeError, ValueError), match=metric):
        count_issues(_report(layered_claims=layered))


@pytest.mark.parametrize(
    "section",
    [
        "unresolved_refs",
        "unregistered_ref_kinds",
        "lingering_tags_lines",
        "agent_context",
        "identity_policy",
        "entity_identity",
        "legacy_task_type",
        "invalid_entity_aspects",
        "dataset_anomalies",
        "schema_invalid",
        "managed_artifacts",
        "tooling_scaffold",
        "validation",
        "accepted_validation",
        "unwired_checks",
    ],
)
def test_root_row_sections_reject_non_mapping_members(section: str) -> None:
    with pytest.raises(TypeError, match=rf"{section}\[0\]"):
        count_issues(_report(**{section: [None]}))


@pytest.mark.parametrize(
    "section",
    ["migration_issues", "rival_model_packets_missing_discriminating_predictions"],
)
def test_layered_issue_lists_reject_non_mapping_members(section: str) -> None:
    layered = _layered(**{section: [None]})
    with pytest.raises(TypeError, match=rf"{section}\[0\]"):
        count_issues(_report(layered_claims=layered))


@pytest.mark.parametrize("section", ["cross_paper_evidence", "prose_epistemics"])
def test_nested_findings_reject_non_mapping_members(section: str) -> None:
    report_section = dict(_report()[section])
    report_section["findings"] = [None]
    with pytest.raises(TypeError, match=rf"{section}\.findings\[0\]"):
        count_issues(_report(**{section: report_section}))


@pytest.mark.parametrize(
    ("section", "row"),
    [
        ("managed_artifacts", {}),
        ("managed_artifacts", {"counts_as_issue": "yes"}),
        ("prose_epistemics", {}),
        ("prose_epistemics", {"counts_as_issue": 1}),
    ],
)
def test_issue_membership_flag_is_required_and_boolean(
    section: str, row: dict[str, object]
) -> None:
    if section == "managed_artifacts":
        report = _report(managed_artifacts=[row])
    else:
        prose = dict(_report()["prose_epistemics"])
        prose["findings"] = [row]
        report = _report(prose_epistemics=prose)
    with pytest.raises((TypeError, ValueError), match="counts_as_issue"):
        count_issues(report)


def test_prose_findings_count_only_when_flagged() -> None:
    prose = dict(_report()["prose_epistemics"])
    prose["findings"] = [
        {"counts_as_issue": True},
        {"counts_as_issue": False},
    ]
    assert count_issues(_report(prose_epistemics=prose)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_count_issues.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.health_count'`

- [ ] **Step 3: Extract the function**

Create `science/src/science_tool/graph/health_count.py` with the collection and typing imports
needed by the strict counter:

```python
from collections.abc import Mapping
from typing import Any, cast
```

Then add the counter and its validation helpers to that module:

```python
def count_issues(report: Mapping[str, Any]) -> int:
    """The single definition of "how many issues does this report contain".

    Used twice: once over the full report to produce ``total_issues`` (the clean-report
    gate), and once over the projected report to produce ``displayed_issues``. Running the
    SAME function over both is what makes "showing N of M" a comparison of like with like.

    Deliberately NOT a plain row count: ``managed_artifacts`` counts only where
    ``counts_as_issue``, and ``archive_lag`` is one issue however large the lag.

    The input must be a real ``HealthReport`` or its projected counterpart. Projection
    retains every required section, so treating a missing or wrongly typed section as
    empty would hide producer/projector contract breaks.
    """

    def _required(container: Mapping[str, Any], key: str, path: str) -> Any:
        if key not in container:
            raise ValueError(f"{path} is missing required field {key!r}")
        return container[key]

    def _mapping(container: Mapping[str, Any], key: str, path: str) -> Mapping[str, Any]:
        value = _required(container, key, path)
        if not isinstance(value, Mapping):
            raise TypeError(f"{path}.{key} must be a mapping, got {type(value).__name__}")
        return value

    def _mapping_members(value: list[Any], path: str) -> list[Mapping[str, Any]]:
        for index, member in enumerate(value):
            if not isinstance(member, Mapping):
                raise TypeError(
                    f"{path}[{index}] must be a mapping, got {type(member).__name__}"
                )
        return cast("list[Mapping[str, Any]]", value)

    def _rows(key: str) -> list[Mapping[str, Any]]:
        value = _required(report, key, "health report")
        if not isinstance(value, list):
            raise TypeError(f"health report.{key} must be a list, got {type(value).__name__}")
        return _mapping_members(value, f"health report.{key}")

    # Validate the complete root shape, including registered sections that do not
    # contribute to the count. A projected report retains all of these keys.
    row_sections = (
        "unresolved_refs",
        "unregistered_ref_kinds",
        "lingering_tags_lines",
        "agent_context",
        "identity_policy",
        "entity_identity",
        "legacy_task_type",
        "invalid_entity_aspects",
        "dataset_anomalies",
        "schema_invalid",
        "managed_artifacts",
        "tooling_scaffold",
        "validation",
        "accepted_validation",
        "unwired_checks",
    )
    rows = {key: _rows(key) for key in row_sections}
    total_issues = _required(report, "total_issues", "health report")
    if type(total_issues) is not int:
        raise TypeError(
            f"health report.total_issues must be an int, got {type(total_issues).__name__}"
        )

    archive_lag = _mapping(report, "archive_lag", "health report")
    for key in ("done_in_active", "retired_in_active", "missing_completed"):
        value = _required(archive_lag, key, "health report.archive_lag")
        if type(value) is not int:
            raise TypeError(
                f"health report.archive_lag.{key} must be an int, got {type(value).__name__}"
            )
    lag_total = archive_lag_total(cast("TaskArchiveLag", archive_lag))

    # layered_claims is a LayeredClaimHealthReport (health.py:185): BOTH issue lists
    # count, and coverage gaps are derived from its two CoverageMetric fields -- there is
    # no top-level `coverage_gaps` key in a report body.
    layered = _mapping(report, "layered_claims", "health report")
    migration_issues = _required(layered, "migration_issues", "health report.layered_claims")
    rival_model_gaps = _required(
        layered,
        "rival_model_packets_missing_discriminating_predictions",
        "health report.layered_claims",
    )
    for key, value in (
        ("migration_issues", migration_issues),
        ("rival_model_packets_missing_discriminating_predictions", rival_model_gaps),
    ):
        if not isinstance(value, list):
            raise TypeError(
                f"health report.layered_claims.{key} must be a list, "
                f"got {type(value).__name__}"
            )
    migration_issues = _mapping_members(
        migration_issues,
        "health report.layered_claims.migration_issues",
    )
    rival_model_gaps = _mapping_members(
        rival_model_gaps,
        "health report.layered_claims.rival_model_packets_missing_discriminating_predictions",
    )
    layered_issues = len(migration_issues) + len(rival_model_gaps)
    coverage_gaps = 0
    for key in ("proposition_claim_layer_coverage", "causal_leaning_identification_coverage"):
        metric = _mapping(layered, key, "health report.layered_claims")
        for field in ("numerator", "denominator"):
            value = _required(metric, field, f"health report.layered_claims.{key}")
            if type(value) is not int:
                raise TypeError(
                    f"health report.layered_claims.{key}.{field} must be an int, "
                    f"got {type(value).__name__}"
                )
        fraction = _required(metric, "fraction", f"health report.layered_claims.{key}")
        if not isinstance(fraction, (int, float)) or isinstance(fraction, bool):
            raise TypeError(
                f"health report.layered_claims.{key}.fraction must be numeric, "
                f"got {type(fraction).__name__}"
            )
        if metric["denominator"] > 0 and metric["numerator"] < metric["denominator"]:
            coverage_gaps += 1

    def _findings(key: str) -> list[Mapping[str, Any]]:
        section = _mapping(report, key, "health report")
        findings = _required(section, "findings", f"health report.{key}")
        if not isinstance(findings, list):
            raise TypeError(
                f"health report.{key}.findings must be a list, "
                f"got {type(findings).__name__}"
            )
        return _mapping_members(findings, f"health report.{key}.findings")

    def _count_issue_flags(findings: list[Mapping[str, Any]], path: str) -> int:
        count = 0
        for index, finding in enumerate(findings):
            flag = _required(finding, "counts_as_issue", f"{path}[{index}]")
            if type(flag) is not bool:
                raise TypeError(
                    f"{path}[{index}].counts_as_issue must be a bool, "
                    f"got {type(flag).__name__}"
                )
            count += int(flag)
        return count

    prose_findings = _findings("prose_epistemics")
    cross_paper_findings = _findings("cross_paper_evidence")
    managed_artifact_issues = _count_issue_flags(
        rows["managed_artifacts"],
        "health report.managed_artifacts",
    )
    prose_issues = _count_issue_flags(
        prose_findings,
        "health report.prose_epistemics.findings",
    )

    return (
        len(rows["unresolved_refs"])
        + len(rows["unregistered_ref_kinds"])
        + len(rows["lingering_tags_lines"])
        + len(rows["agent_context"])
        + len(rows["identity_policy"])
        + len(rows["entity_identity"])
        + layered_issues
        + coverage_gaps
        + len(rows["dataset_anomalies"])
        + len(rows["schema_invalid"])
        + (1 if lag_total else 0)
        + managed_artifact_issues
        + len(rows["tooling_scaffold"])
        + len(rows["validation"])
        + prose_issues
        + len(cross_paper_findings)
    )
```

Then restructure the tail of `build_health_report`. Two constraints shape how:

1. There is **no `layered_claims` local** today — the dict is built inline inside the
   `report: HealthReport = {...}` literal at `health.py:365-370`. Referring to a
   `layered_claims` name would not resolve.
2. `HealthReport` is a `TypedDict`. Spreading a `dict[str, Any]` into it
   (`{**report_body, "total_issues": ...}`) is a Pyright assignment error, because a
   `dict[str, Any]` cannot prove it supplies the required keys.

So: hoist `layered_claims` into a typed local, build a **real** `HealthReport` with a placeholder
total, then overwrite that one field.

Once `count_issues` owns the arithmetic, five locals that fed only the inline sum become unused
and Ruff flags each as `F841`. Delete all of them:

- the inline `total_issues` sum (`health.py:353-374`);
- `layered_claim_issue_count` / `coverage_gaps` and the `for metric in (proposition_coverage,
  causal_coverage):` loop that computed them (`health.py:342-351`);
- `prose_epistemics_findings` and `prose_epistemics_issue_count` (`health.py:335-340`) —
  `count_issues` re-derives the prose count internally via its `_findings` helper;
- `lag_total` (`health.py:356`) — `count_issues` recomputes it with `archive_lag_total`.

Keep `prose_epistemics` (the dict at `health.py:334`, still spread into the report literal),
`proposition_coverage`, and `causal_coverage` — the last two feed the `layered_claims` local
below. `archive_lag_total` moves to `health_count.py`, where `count_issues` calls it.

Import the counter privately in `health.py`:

```python
from science_tool.graph.health_count import count_issues as _count_issues
```

```python
    layered_claims: LayeredClaimHealthReport = {
        "proposition_claim_layer_coverage": proposition_coverage,
        "causal_leaning_identification_coverage": causal_coverage,
        "rival_model_packets_missing_discriminating_predictions": rival_model_gaps,
        "migration_issues": migration_issues,
    }

    report: HealthReport = {
        "unresolved_refs": unresolved_refs,
        "unregistered_ref_kinds": unregistered_ref_kinds,
        "lingering_tags_lines": lingering_tags_lines,
        "agent_context": agent_context,
        "identity_policy": identity_policy_findings,
        "entity_identity": entity_identity,
        "layered_claims": layered_claims,
        "cross_paper_evidence": cross_paper_evidence,
        "legacy_task_type": legacy_task_type,
        "invalid_entity_aspects": invalid_entity_aspects,
        "dataset_anomalies": dataset_anomalies,
        "schema_invalid": schema_invalid,
        "archive_lag": cast("TaskArchiveLag", archive_lag),
        # ... every remaining key of the existing literal, unchanged and in place ...
        "total_issues": 0,  # placeholder: count_issues reads the assembled report below
    }
    report["total_issues"] = _count_issues(report)
```

Everything between `archive_lag` and `total_issues` in the existing literal stays exactly as it
is; only `layered_claims` changes (inline dict → the typed local) and `total_issues` changes
(inline sum → placeholder plus the assignment). `_meta` is `NotRequired` and is attached later by
the caller, unaffected.

The same `health_count.count_issues` implementation is now called on the same shape in both
places — privately over the assembled `HealthReport` here, and directly over the projected
report in Task 10 — so no normalization step can drift between them. Its parameter type is
`Mapping[str, Any]`, which both a `HealthReport` and the projected `dict[str, Any]` satisfy.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_health_count_issues.py -v`
Expected: PASS (50 collected)

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
git add science/src/science_tool/graph/health_count.py science/src/science_tool/graph/health.py science/tests/test_health_count_issues.py
git commit -m "refactor(health): extract count_issues as the single issue-counting definition"
```

---

### Task 9: Health section classification and severity threshold

**Files:**
- Create: `science/src/science_tool/graph/health_projection.py`
- Test: `science/tests/test_health_projection.py`

**Interfaces:**
- Produces: `SEVERITY_SECTIONS`, `COUNTS_AS_ISSUE_SECTIONS`, `UNFILTERED_SECTIONS`,
  `NESTED_FINDING_SECTIONS`, `MAPPING_SECTIONS`, `SCALAR_SECTIONS`, `SEVERITY_ORDER`,
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


def test_unknown_severity_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown health severity"):
        meets_threshold({"severity": "critical"}, "warn")


def test_explicit_none_severity_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown health severity"):
        meets_threshold({"severity": None}, "warn")
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

# Registered non-row mappings that pass through projection after a shape check.
MAPPING_SECTIONS = frozenset({"archive_lag", "layered_claims"})

# Non-list sections that pass through untouched. This is an ALLOW-LIST, not a type test:
# any other non-list key is refused. `coverage_gaps` is deliberately absent -- it is a local
# inside `build_health_report`, never a report key (`health.py:341-351`).
SCALAR_SECTIONS = frozenset({"total_issues", "_meta"})

SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "warn": 1, "error": 2}

_THRESHOLD_FLOOR: dict[str, int] = {"all": 0, "warn": 1, "error": 2}


def meets_threshold(row: Mapping[str, Any], threshold: str) -> bool:
    """True when ``row`` is at or above ``threshold``.

    A row with no ``severity`` key survives every valid threshold: absence of the signal
    is not evidence of low severity, and dropping such rows would hide findings. A present
    value, including explicit ``None``, must be a registered severity string.
    """
    if "severity" not in row:
        return True
    severity = row["severity"]
    if not isinstance(severity, str) or severity not in SEVERITY_ORDER:
        raise ValueError(f"unknown health severity {severity!r}")
    return SEVERITY_ORDER[severity] >= _THRESHOLD_FLOOR[threshold]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_health_projection.py -v`
Expected: PASS (17 collected)

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

from science_tool.graph.health_count import count_issues
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
        "unregistered_ref_kinds": [],
        "lingering_tags_lines": [],
        "agent_context": [],
        "identity_policy": [],
        "entity_identity": [],
        "legacy_task_type": [],
        "invalid_entity_aspects": [],
        "dataset_anomalies": [],
        "schema_invalid": [],
        "tooling_scaffold": [],
        "accepted_validation": [],
        "archive_lag": {"done_in_active": 4, "retired_in_active": 0, "missing_completed": 1},
        "unwired_checks": [],
        "layered_claims": {
            "proposition_claim_layer_coverage": {"numerator": 0, "denominator": 0, "fraction": 1.0},
            "causal_leaning_identification_coverage": {"numerator": 0, "denominator": 0, "fraction": 1.0},
            "rival_model_packets_missing_discriminating_predictions": [],
            "migration_issues": [],
        },
        "cross_paper_evidence": {
            "status": "ok",
            "empty_state": "no_propositions",
            "summary": {},
            "findings": [],
            "propositions": [],
        },
        "prose_epistemics": {
            "applicable": False,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [],
        },
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
        "empty_state": "active",
        "summary": {},
        "findings": [{"severity": "error", "code": f"c{i}"} for i in range(100)],
        "propositions": [],
    }
    projected = project_health_report(report, threshold="error")
    assert len(projected["cross_paper_evidence"]["findings"]) == SECTION_ROW_CAP
    assert projected["cross_paper_evidence"]["status"] == "active"


@pytest.mark.parametrize(
    ("section", "value"),
    [("validation", {}), ("managed_artifacts", "findings"), ("unresolved_refs", None)],
)
def test_registered_row_sections_reject_non_lists(section: str, value: object) -> None:
    report = _natural_systems_shaped_report()
    report[section] = value
    with pytest.raises(TypeError, match=section):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize(
    "section",
    ["validation", "managed_artifacts", "unresolved_refs"],
)
def test_registered_row_sections_reject_non_mapping_members(section: str) -> None:
    report = _natural_systems_shaped_report()
    report[section] = [None]
    with pytest.raises(TypeError, match=rf"{section}\[0\]"):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("cross_paper_evidence", {}),
        ("cross_paper_evidence", {"findings": {}}),
        (
            "cross_paper_evidence",
            {
                "status": "ok",
                "empty_state": "active",
                "summary": [],
                "findings": [],
                "propositions": [],
            },
        ),
        (
            "cross_paper_evidence",
            {
                "status": "ok",
                "empty_state": "active",
                "summary": {},
                "findings": [],
            },
        ),
        ("prose_epistemics", {}),
        ("prose_epistemics", {"findings": None}),
        (
            "prose_epistemics",
            {
                "applicable": "no",
                "summary": {},
                "coverage": {},
                "sources": [],
                "findings": [],
            },
        ),
        (
            "prose_epistemics",
            {
                "applicable": False,
                "summary": {},
                "coverage": {},
                "findings": [],
            },
        ),
    ],
)
def test_nested_sections_require_their_registered_shape(section: str, value: object) -> None:
    report = _natural_systems_shaped_report()
    report[section] = value
    with pytest.raises((TypeError, ValueError), match=section):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize("section", ["archive_lag", "layered_claims"])
def test_registered_mapping_sections_reject_non_mappings(section: str) -> None:
    report = _natural_systems_shaped_report()
    report[section] = []
    with pytest.raises(TypeError, match=section):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("archive_lag", {"done_in_active": 0, "retired_in_active": 0}),
        (
            "archive_lag",
            {"done_in_active": "zero", "retired_in_active": 0, "missing_completed": 0},
        ),
        (
            "layered_claims",
            {
                "proposition_claim_layer_coverage": {
                    "numerator": 0,
                    "denominator": 0,
                    "fraction": 1.0,
                },
                "causal_leaning_identification_coverage": {
                    "numerator": 0,
                    "denominator": 0,
                    "fraction": 1.0,
                },
                "migration_issues": [],
            },
        ),
        (
            "layered_claims",
            {
                "proposition_claim_layer_coverage": {
                    "numerator": 0,
                    "denominator": 0,
                    "fraction": 1.0,
                },
                "causal_leaning_identification_coverage": {
                    "numerator": 0,
                    "denominator": "zero",
                    "fraction": 1.0,
                },
                "rival_model_packets_missing_discriminating_predictions": [],
                "migration_issues": [],
            },
        ),
    ],
)
def test_mapping_sections_require_their_registered_shape(
    section: str, value: object
) -> None:
    report = _natural_systems_shaped_report()
    report[section] = value
    with pytest.raises((TypeError, ValueError), match=section):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize("section", ["cross_paper_evidence", "prose_epistemics"])
def test_nested_findings_reject_non_mapping_members(section: str) -> None:
    report = _natural_systems_shaped_report()
    nested = dict(report[section])
    nested["findings"] = [None]
    report[section] = nested
    with pytest.raises(TypeError, match=rf"{section}\.findings\[0\]"):
        project_health_report(report, threshold="warn")


def test_unknown_list_section_refuses_rather_than_capping() -> None:
    report = _natural_systems_shaped_report()
    report["brand_new_check"] = [{"severity": "error"}] * 500
    with pytest.raises(UnknownSection, match="brand_new_check"):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize("value", [True, 7, "clean", 1.5, None])
def test_unknown_scalar_section_refuses(value: object) -> None:
    """A new scalar section must be classified too.

    A type test (`not isinstance(value, (list, dict))`) would wave every one of these
    through unexamined -- a new `"degraded": True` or `"entity_count": 41000` would join
    the report with nobody having decided what it means for the budget.
    """
    report = _natural_systems_shaped_report()
    report["brand_new_scalar"] = value
    with pytest.raises(UnknownSection, match="brand_new_scalar"):
        project_health_report(report, threshold="warn")


def test_registered_scalars_still_pass_through() -> None:
    report = _natural_systems_shaped_report()
    report["_meta"] = {"timings": [], "total_duration_seconds": 0.5}
    projected = project_health_report(report, threshold="warn")
    assert projected["_meta"] == {"timings": [], "total_duration_seconds": 0.5}
    assert projected["total_issues"] == report["total_issues"]


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("total_issues", "364"),
        ("_meta", {"timings": []}),
        ("_meta", {"timings": {}, "total_duration_seconds": 0.5}),
    ],
)
def test_registered_scalars_require_their_registered_shape(
    section: str, value: object
) -> None:
    report = _natural_systems_shaped_report()
    report[section] = value
    with pytest.raises((TypeError, ValueError), match=section):
        project_health_report(report, threshold="warn")
```

`_meta` is a dict, and it is in `SCALAR_SECTIONS` rather than `UNFILTERED_SECTIONS` because it is
not a findings section at all — it carries timings, and reaching `_classified` would be wrong.
Registered does not mean unchecked: row sections require mapping members; `archive_lag`,
`layered_claims`, both nested finding reports, `total_issues`, and `_meta` validate their required
fields and field types before projection.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_projection_caps.py -v`
Expected: FAIL — `ImportError: cannot import name 'SECTION_ROW_CAP'`

- [ ] **Step 3: Add caps and the projector**

Append to `science/src/science_tool/graph/health_projection.py`:

```python
SECTION_ROW_CAP = 40


def _required_field(container: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in container:
        raise ValueError(f"{path} is missing required field {key!r}")
    return container[key]


def _required_mapping(
    container: Mapping[str, Any],
    key: str,
    path: str,
) -> Mapping[str, Any]:
    value = _required_field(container, key, path)
    if not isinstance(value, Mapping):
        raise TypeError(f"{path}.{key} must be a mapping, got {type(value).__name__}")
    return value


def _required_list(container: Mapping[str, Any], key: str, path: str) -> list[Any]:
    value = _required_field(container, key, path)
    if not isinstance(value, list):
        raise TypeError(f"{path}.{key} must be a list, got {type(value).__name__}")
    return value


def _validate_mapping_members(rows: list[Any], path: str) -> None:
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TypeError(f"{path}[{index}] must be a mapping, got {type(row).__name__}")


def _validate_integer_field(container: Mapping[str, Any], key: str, path: str) -> None:
    value = _required_field(container, key, path)
    if type(value) is not int:
        raise TypeError(f"{path}.{key} must be an int, got {type(value).__name__}")


def _validate_coverage_metric(
    layered: Mapping[str, Any],
    key: str,
    path: str,
) -> None:
    metric = _required_mapping(layered, key, path)
    metric_path = f"{path}.{key}"
    _validate_integer_field(metric, "numerator", metric_path)
    _validate_integer_field(metric, "denominator", metric_path)
    fraction = _required_field(metric, "fraction", metric_path)
    if not isinstance(fraction, (int, float)) or isinstance(fraction, bool):
        raise TypeError(
            f"{metric_path}.fraction must be numeric, got {type(fraction).__name__}"
        )


def _validate_mapping_section(section: str, value: Mapping[str, Any]) -> None:
    path = f"health report section {section!r}"
    if section == "archive_lag":
        for key in ("done_in_active", "retired_in_active", "missing_completed"):
            _validate_integer_field(value, key, path)
        return

    for key in (
        "proposition_claim_layer_coverage",
        "causal_leaning_identification_coverage",
    ):
        _validate_coverage_metric(value, key, path)
    for key in (
        "rival_model_packets_missing_discriminating_predictions",
        "migration_issues",
    ):
        rows = _required_list(value, key, path)
        _validate_mapping_members(rows, f"{path}.{key}")


def _validate_nested_section(
    section: str,
    value: Mapping[str, Any],
) -> list[Any]:
    path = f"health report section {section!r}"
    if section == "cross_paper_evidence":
        for key in ("status", "empty_state"):
            field = _required_field(value, key, path)
            if not isinstance(field, str):
                raise TypeError(f"{path}.{key} must be a str, got {type(field).__name__}")
        _required_mapping(value, "summary", path)
        propositions = _required_list(value, "propositions", path)
        _validate_mapping_members(propositions, f"{path}.propositions")
    else:
        applicable = _required_field(value, "applicable", path)
        if type(applicable) is not bool:
            raise TypeError(
                f"{path}.applicable must be a bool, got {type(applicable).__name__}"
            )
        _required_mapping(value, "summary", path)
        _required_mapping(value, "coverage", path)
        sources = _required_list(value, "sources", path)
        _validate_mapping_members(sources, f"{path}.sources")

    findings = _required_list(value, "findings", path)
    _validate_mapping_members(findings, f"{path}.findings")
    return findings


def _validate_scalar_section(section: str, value: Any) -> None:
    path = f"health report section {section!r}"
    if section == "total_issues":
        if type(value) is not int:
            raise TypeError(f"{path} must be an int, got {type(value).__name__}")
        return

    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be a mapping, got {type(value).__name__}")
    timings = _required_list(value, "timings", path)
    _validate_mapping_members(timings, f"{path}.timings")
    duration = _required_field(value, "total_duration_seconds", path)
    if not isinstance(duration, (int, float)) or isinstance(duration, bool):
        raise TypeError(
            f"{path}.total_duration_seconds must be numeric, "
            f"got {type(duration).__name__}"
        )


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
    _validate_mapping_members(rows, f"health report section {section!r}")
    kind = _classified(section)
    if kind == "unfiltered":
        return rows

    if kind == "severity":
        kept = [row for row in rows if meets_threshold(row, threshold)]
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
    from science_tool.graph.health_count import count_issues

    effective_cap = SECTION_ROW_CAP if cap is None else cap
    omitted: dict[str, int] = {}
    projected: dict[str, Any] = {}

    for key, value in report.items():
        # SCALAR_SECTIONS is the ONLY way a non-list section skips classification. Testing
        # `not isinstance(value, (list, dict))` here instead would let a newly added
        # boolean/int/string section pass through unexamined purely because of its Python
        # type -- the silent escape this projector exists to prevent.
        if key in SCALAR_SECTIONS:
            _validate_scalar_section(key, value)
            projected[key] = value
            continue

        if key in NESTED_FINDING_SECTIONS:
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"health report section {key!r} must be a mapping, "
                    f"got {type(value).__name__}"
                )
            findings = _validate_nested_section(key, value)
            projected[key] = {
                **value,
                "findings": _project_section(findings, key, threshold, effective_cap, omitted),
            }
            continue

        if key in MAPPING_SECTIONS:
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"health report section {key!r} must be a mapping, "
                    f"got {type(value).__name__}"
                )
            _validate_mapping_section(key, value)
            projected[key] = value
            continue

        # Classification happens before the list check so an unknown scalar still raises
        # UnknownSection rather than being mistaken for a malformed known section.
        _classified(key)
        if not isinstance(value, list):
            raise TypeError(
                f"health report section {key!r} must be a list, "
                f"got {type(value).__name__}"
            )
        projected[key] = _project_section(value, key, threshold, effective_cap, omitted)

    projected["displayed_issues"] = count_issues(projected)
    projected["section_omitted"] = omitted
    return projected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_health_projection_caps.py -v`
Expected: PASS (41 collected)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/health_projection.py science/tests/test_health_projection_caps.py
git commit -m "feat(health): add per-section caps and count_issues-based displayed_issues"
```

---

### Task 11: Wire every `health` payload path through the sink

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
    "legacy_task_type": [],
    "invalid_entity_aspects": [],
    "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
    # All four LayeredClaimHealthReport keys. The adoption table at health_cli.py:376
    # reads both coverage metrics UNCONDITIONALLY, and the rival-model table reads its
    # list — a fixture carrying only `migration_issues` raises KeyError before any
    # assertion runs.
    "layered_claims": {
        "proposition_claim_layer_coverage": {"numerator": 0, "denominator": 0, "fraction": 0.0},
        "causal_leaning_identification_coverage": {"numerator": 0, "denominator": 0, "fraction": 0.0},
        "rival_model_packets_missing_discriminating_predictions": [],
        "migration_issues": [],
    },
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

    emit(output_format=output_format, payload=displayed, render_text=_render_report, sink=sink)
    sink.flush()
    # This fixed-shape bounded control notice is the sole permitted sink bypass.
    # Emit it only AFTER a successful flush, never in `finally` — see Task 7.
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
git commit -m "feat(health): route all payload through the sink, add --severity and --output"
```

---

### Task 12: Bulk dumps refuse stdout in every supported format

**Files:**
- Modify: `science/src/science_tool/entities_inventory_cli.py:50-61`
- Modify: `science/src/science_tool/data_cli.py:28-90` (the `--fix` help and the `--output` gate)
- Test: `science/tests/test_bulk_dump_refusal.py`
- Modify (existing regression): `science/tests/test_data_audit_cli.py:66` — bare `--fix` no longer
  succeeds; move it to `--output` and add a refusal test

**Interfaces:**
- Consumes: `BoundedSink`, `lookup`, `build_complete_via`.
- Produces: `--output PATH` on both commands; both refuse when the stdout payload exceeds budget.

**Entity inventory remains JSON-only. `data audit` supports text and JSON**, and its default
format is text; the previous plan guarded only its JSON echoes. Both supported `data audit`
branches route through the sink here. Note the two distinct `render_json` signatures:
`render_json(violations, outcomes, notes)` under `--fix`, `render_json(violations, notes=notes)`
otherwise.

`data audit` ends with `raise SystemExit(1)` when violations exist, so the flush must happen
**before** that exit.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_bulk_dump_refusal.py
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.budget.registry import BUDGETS
from science_tool.cli import main

# Enough stranded records that both the text and JSON reports exceed the data-audit
# budget (20_000 chars); kept modest so the positive test's per-move `git add` stays fast.
STRANDED_RECORDS = 400


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


# Do not rely on chdir for this command. Its Click option currently uses
# `default=Path.cwd()`, which is evaluated when entities_inventory_cli is imported,
# before these tests change directory. Pass the fixture root explicitly in every
# inventory invocation so the test cannot inspect the developer's checkout by accident.
def test_small_inventory_prints_to_stdout(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=1)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["entities", "inventory", "--project-root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    json.loads(result.output)


def test_oversized_inventory_is_refused_not_truncated(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=400)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["entities", "inventory", "--project-root", str(tmp_path)])
    assert result.exit_code != 0
    assert "--output" in result.output
    assert "schema_version" not in result.output  # no partial document leaked


def test_inventory_output_file_is_complete(tmp_path: Path, monkeypatch) -> None:
    _project(tmp_path, entities=400)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "inv.json"
    result = _invoke(
        ["entities", "inventory", "--project-root", str(tmp_path), "--output", str(target)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())
    assert payload["schema_version"] == "2"
    assert len(target.read_text()) > BUDGETS["entities inventory"].max_chars


def test_data_audit_text_branch_is_budgeted(tmp_path: Path, monkeypatch) -> None:
    """The default format is text; the previous plan guarded only JSON."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["data", "audit"])
    assert "--output" in result.output


def test_data_audit_output_file_is_complete_in_text_format(tmp_path: Path, monkeypatch) -> None:
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.txt"
    result = _invoke(["data", "audit", "--output", str(target)])
    assert result.exit_code in (0, 1)
    assert len(target.read_text()) > BUDGETS["data audit"].max_chars


def test_data_audit_json_branch_is_budgeted(tmp_path: Path, monkeypatch) -> None:
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = _invoke(["data", "audit", "--format", "json"])
    assert "--output" in result.output


def test_data_audit_output_file_is_complete_in_json_format(tmp_path: Path, monkeypatch) -> None:
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.json"
    result = _invoke(["data", "audit", "--format", "json", "--output", str(target)])
    assert result.exit_code in (0, 1)
    json.loads(target.read_text())
    assert len(target.read_text()) > BUDGETS["data audit"].max_chars


def test_fix_without_output_refuses_before_moving_any_file(tmp_path: Path, monkeypatch) -> None:
    """apply_fixes mutates the tree, so --fix must not depend on a later budget check."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = _invoke(["data", "audit", "--fix"])

    assert result.exit_code != 0
    assert "--output" in result.output
    assert not (tmp_path / "results").exists(), "files were moved despite the command failing"


def test_fix_refuses_a_missing_parent_output_before_moving(tmp_path: Path, monkeypatch) -> None:
    """A missing output parent must fail while the tree is intact."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = _invoke(["data", "audit", "--fix", "--output", "does/not/exist/audit.json"])

    assert result.exit_code != 0
    assert not (tmp_path / "results").exists(), "files were moved despite an unwritable --output"


def test_fix_refuses_a_directory_output_before_moving(tmp_path: Path, monkeypatch) -> None:
    """Path.touch() accepts a directory; the command must reject it before moving."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "report-dir"
    target.mkdir()

    result = _invoke(["data", "audit", "--fix", "--output", str(target)])

    assert result.exit_code != 0
    assert not (tmp_path / "results").exists(), "files were moved despite a directory --output"


def test_fix_refuses_an_unreservable_output_before_moving(tmp_path: Path, monkeypatch) -> None:
    """Creating the sibling temp, not touching the target, proves output is reservable."""
    from science_tool.budget import sink as sink_module

    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.json"

    def deny_reservation(*args: object, **kwargs: object):
        raise PermissionError("read-only destination")

    monkeypatch.setattr(sink_module.tempfile, "mkstemp", deny_reservation)
    result = _invoke(["data", "audit", "--fix", "--output", str(target)])

    assert result.exit_code != 0
    assert not (tmp_path / "results").exists(), "files were moved despite a read-only --output"


def test_fix_rejects_output_ancestor_of_a_proposed_destination(
    tmp_path: Path, monkeypatch
) -> None:
    """The report path must not become a directory created by the planned move."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "results").mkdir()
    target = tmp_path / "results" / "exp00000"

    result = _invoke(["data", "audit", "--fix", "--output", str(target)])

    assert result.exit_code != 0
    assert "overlaps" in result.output
    assert (tmp_path / "data" / "processed" / "exp00000" / "RESULTS.md").exists()
    assert not target.exists()
    assert list((tmp_path / "results").glob(".exp00000.*.tmp")) == []


def test_fix_with_output_mutates_and_writes_the_complete_report(tmp_path: Path, monkeypatch) -> None:
    """A reserved file sink removes known size and destination failures."""
    _stranded_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "audit.json"

    result = _invoke(["data", "audit", "--fix", "--format", "json", "--output", str(target)])

    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())
    assert len(payload["violations"]) == STRANDED_RECORDS
    assert all(row["performed"] for row in payload["violations"])
    assert (tmp_path / "results" / "exp00000" / "RESULTS.md").exists()
    assert len(target.read_text()) > BUDGETS["data audit"].max_chars


def test_fix_on_a_clean_project_still_works_without_output(tmp_path: Path, monkeypatch) -> None:
    """The gate keys on there being violations, not on --fix alone."""
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)

    result = _invoke(["data", "audit", "--fix"])

    assert result.exit_code == 0, result.output
```

Add this shared helper near the top of the test module:

```python
def _stranded_project(root: Path) -> None:
    """A git repo whose data/ holds many *movable* stranded records.

    Uses the exact shape the existing CLI suite proves movable
    (data/processed/exp/RESULTS.md -> results/exp/RESULTS.md; see
    test_data_audit_cli.py::test_audit_json_contract), scaled until the report exceeds
    the data-audit budget.

    A real repository is required: for each untracked move `apply_fixes` runs
    `git add <target>` (data_audit_fix.py:171), which errors outside a repo. Without
    `git init` the positive --fix test would exit nonzero after partially mutating.
    """
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "science.yaml").write_text("id: demo\nname: demo\n")
    for i in range(STRANDED_RECORDS):
        record = root / "data" / "processed" / f"exp{i:05d}" / "RESULTS.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("# r\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_bulk_dump_refusal.py -v`
Expected: FAIL — `data audit` has no `--output`; entity inventory still floods stdout; and the
pre-mutation reservation/normalized-overlap checks are absent.

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
    # The fixed-shape bounded control notice is non-payload and may bypass the sink only
    # after the file write succeeds.
    if output is not None:
        click.echo(f"wrote the entity inventory to {output}")
```

The sink raises `BudgetExceeded` before printing anything, so no partial `schema_version`
document can leak — which is why refusal, not truncation, is correct for this shape.

- [ ] **Step 4: Wire both `data audit` branches**

First amend the existing `--fix` option's help so the new requirement is discoverable
(`data_cli.py:28`):

```python
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Relocate stranded records data/ → results/ (stages, never commits). "
    "Requires --output PATH when there are violations to act on.",
)
```

Then add the `--output` option and the gate:

```python
def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _fix_output_overlap(
    project_path: Path,
    output_path: Path,
    violations: list[Violation],
) -> tuple[str, str] | None:
    normalized_output = output_path.resolve(strict=False)
    project_root = project_path.resolve()
    for violation in violations:
        source = (project_root / violation.path).resolve(strict=False)
        if _paths_overlap(normalized_output, source):
            return "source", violation.path
        if violation.proposed_target is not None:
            destination = (project_root / violation.proposed_target).resolve(strict=False)
            if _paths_overlap(normalized_output, destination):
                return "proposed destination", violation.proposed_target
    return None


@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path, file_okay=True, dir_okay=False),
    default=None,
)
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

    if fix and violations:
        # apply_fixes MOVES FILES. Rule out the two deterministic report failures this
        # command controls BEFORE the moves, or the caller can be left with a changed
        # tree, no report, and a reason to retry:
        #
        # 1. SIZE. There is no honest preflight for it: the post-fix JSON adds `basepath`
        #    and an unbounded `rewritten_resources` array per datapackage row
        #    (data_audit.py:296-299), so nothing measurable before the moves bounds the
        #    final document, and the pre-fix text preview (~6.7k chars for 100 violations)
        #    is far smaller than its JSON (~20.4k), so it would pass in exactly the cases
        #    that then fail. The only sound rule is structural: send the report somewhere
        #    unbounded. A file sink has no ceiling, so its flush cannot fail on size.
        if output_path is None:
            raise click.UsageError(
                f"data audit --fix would act on {len(violations)} violation(s), and the size "
                f"of the resulting report cannot be bounded before the moves run. A budget "
                f"failure after mutating would leave the tree changed with no report. "
                f"Re-run with --output PATH."
            )
        # 2. OUTPUT TOPOLOGY. Normalize through absolute paths and symlinks, then
        #    reject equality or ancestor/descendant overlap with every violation source
        #    and proposed destination. Otherwise apply_fixes could create the requested
        #    report path as a directory (or move the source out from under it) before
        #    flush.
        overlap = _fix_output_overlap(project_path, output_path, violations)
        if overlap is not None:
            kind, audited_path = overlap
            raise click.UsageError(
                f"data audit --fix output {output_path} collides with or overlaps audited "
                f"{kind} {audited_path}. Refusing before any file is moved."
            )

    if fix:
        def apply_render_and_flush() -> None:
            outcomes = apply_fixes(project_path, violations)
            if emit_json:
                sink.write(render_json(violations, outcomes, notes))
            else:
                performed = sum(1 for o in outcomes if o.performed)
                flagged = sum(1 for o in outcomes if not o.performed)
                for o in outcomes:
                    mark = "moved" if o.performed else "FLAG"
                    tgt = o.violation.proposed_target or "-"
                    sink.echo(
                        f"  [{mark}] {o.violation.path} → {tgt}"
                        + (f"  ({o.reason})" if o.reason else "")
                    )
                sink.echo(
                    f"\n{performed} moved (staged, not committed), {flagged} flagged."
                )
            sink.flush()

        if violations:
            # Entering the context creates a writable sibling temp without touching the
            # final destination. It therefore fails for a missing parent, directory
            # target, or inability to reserve while the source tree is still intact.
            reserved = False
            try:
                with sink.reserve_output():
                    reserved = True
                    apply_render_and_flush()
            except OSError as exc:
                if not reserved:
                    raise click.UsageError(
                        f"data audit --fix cannot reserve its report destination "
                        f"{output_path}: {exc}. Refusing before any file is moved."
                    ) from exc
                raise
        else:
            apply_render_and_flush()
        # Sole sink-bypass exception: one fixed-shape bounded control notice after flush.
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
    # Sole sink-bypass exception: one fixed-shape bounded control notice after flush.
    if output_path is not None:
        click.echo(f"wrote the data audit report to {output_path}")
    if violations:
        raise SystemExit(1)
```

The flush precedes `raise SystemExit(1)` so the report is emitted before the non-zero exit.

**The gate is deliberately conservative, and this is a real behaviour change.** It fires on any
violation, including `leaked_payload` rows that the fixer only ever flags. A narrower gate could
consult `data_audit._planned_action` and demand `--output` only when something would actually
move — but that would make correctness depend on `_planned_action` staying in lockstep with
`apply_fixes`, a coupling nothing currently enforces. Erring toward asking for `--output` too
often costs a re-run; erring the other way costs a mutated tree with no report. The `--fix` help
text now states the requirement (Step 4); record the behaviour change in `docs/plans/` when slice
1a lands.

`--fix` on a clean project still works bare, which is the only case where its output is trivially
small anyway.

- [ ] **Step 5: Update the existing `--fix` regression**

`test_data_audit_cli.py::test_fix_moves_and_reports_performed` (`test_data_audit_cli.py:66`)
invokes bare `--fix --json` on a single violation and asserts `exit_code == 0`. The new gate makes
that invocation refuse, so the test must move to the supported `--output` form. It is selected by
Step 6's `-k "data_audit"` filter, so leaving it stale would fail the suite. Replace it with:

```python
def test_fix_moves_and_reports_performed(tmp_path: Path):
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    out = tmp_path / "audit.json"
    res = _run(tmp_path, "--fix", "--json", "--output", str(out))
    assert res.exit_code == 0
    payload = json.loads(out.read_text())
    assert payload["violations"][0]["performed"] is True
    assert (tmp_path / "results/exp1/RESULTS.md").exists()


def test_fix_without_output_refuses(tmp_path: Path):
    """The report size cannot be bounded before the moves, so --fix demands --output."""
    _init_repo(tmp_path)
    _write(tmp_path, "data/processed/exp1/RESULTS.md", b"# r\n")
    res = _run(tmp_path, "--fix", "--json")
    assert res.exit_code != 0
    assert "--output" in res.output
    assert not (tmp_path / "results/exp1/RESULTS.md").exists()
```

The new negative test lives beside the updated one; both use the file's existing `_init_repo` /
`_write` / `_run` helpers, so no new imports are needed.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_bulk_dump_refusal.py -v`
Expected: PASS (13 tests)

- [ ] **Step 7: Run the affected suites**

Run: `cd science && uv run --frozen pytest -k "inventory or data_audit or data_cli" -v`
Expected: PASS, including the updated `test_data_audit_cli.py`.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/entities_inventory_cli.py science/src/science_tool/data_cli.py science/tests/test_bulk_dump_refusal.py science/tests/test_data_audit_cli.py
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
3. **Regression covers all four wired commands in every supported format** — table and JSON
   where both exist, and JSON only for `entities inventory`.

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

For each command in the failure output, classify by **growability**, not by current size:

- `EXEMPTIONS` — the output shape is fixed and cannot grow with project size.
- `DEFERRED` — the output contains a per-item element, so it grows. Record what makes it grow.

Read the command's emission sites before deciding. The question is "does this emit one row per
*something*?", not "how big is it today".

```bash
cd ~/d/natural-systems && uv run --with-editable ~/d/science/science science <command> 2>/dev/null | wc -m
```

Reason formats:

```python
EXEMPTIONS["graph stats"] = "measured 341 chars on 2026-07-24; fixed-shape summary"
DEFERRED["tasks archive"] = DeferredCommand("one row per archivable task", "1b")
```

**Do not write a blanket exemption for mutating commands.** "Mutating command; emits a fixed-size
confirmation" is false for any command with an unbounded preview — `tasks archive` is exactly
that: its dry-run emits one row per archivable task (`tasks_cli.py:333`) yet measures small on a
freshly-archived project. Small today is not the same as bounded. Check each one.

An exemption is a claim about the code, and the reason string is where the claim is recorded.

- [ ] **Step 4: Run the guards to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_budget_boundary.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Write the behavioural regression suite**

```python
# science/tests/test_budget_regression.py
"""Actual emitted sizes for every wired command, in every supported format.

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
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for i in range(3_000):
        (data_dir / f"stranded-record-with-a-long-name-{i:05d}.md").write_text("x")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def _scope_project(args: list[str], project: Path) -> list[str]:
    """Make inventory tests independent of its import-time Path.cwd() default."""
    if args[:2] == ["entities", "inventory"]:
        return [*args, "--project-root", str(project)]
    return args


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
    ("command_path", "args"),
    [
        ("entities inventory", ["entities", "inventory"]),
        ("data audit", ["data", "audit"]),
        ("data audit", ["data", "audit", "--format", "json"]),
    ],
)
def test_bulk_dump_refuses_rather_than_flooding(project: Path, command_path: str, args: list[str]) -> None:
    """DOCUMENT-shaped commands refuse; they never emit a partial payload."""
    result = _invoke(_scope_project(args, project))
    assert result.exit_code != 0
    assert "--output" in result.output
    assert visible_len(result.output) <= BUDGETS[command_path].max_chars


@pytest.mark.parametrize(
    ("args", "target_name"),
    [
        (["tasks", "list", "--status", "proposed", "--format", "json"], "tasks.json"),
        (["tasks", "list", "--status", "proposed"], "tasks.txt"),
        (["health", "--format", "json"], "health.json"),
        (["health"], "health.txt"),
        (["entities", "inventory"], "inventory.json"),
        (["data", "audit"], "audit.txt"),
        (["data", "audit", "--format", "json"], "audit.json"),
    ],
)
def test_output_file_is_written_and_non_empty(project: Path, args: list[str], target_name: str) -> None:
    target = project / target_name
    result = _invoke([*_scope_project(args, project), "--output", str(target)])
    assert result.exit_code in (0, 1), result.output
    assert target.is_file(), f"{args} --output wrote no file"
    assert target.stat().st_size > 0, f"{args} --output wrote an empty file"


@pytest.mark.parametrize(
    ("args", "target_name"),
    [
        (["tasks", "list", "--status", "proposed", "--format", "json"], "tasks.json"),
        (["tasks", "list", "--status", "proposed"], "tasks.txt"),
        (["health", "--format", "json"], "health.json"),
        (["health"], "health.txt"),
        (["entities", "inventory"], "inventory.json"),
        (["data", "audit"], "audit.txt"),
        (["data", "audit", "--format", "json"], "audit.json"),
    ],
)
def test_no_success_message_when_the_command_fails(
    project: Path, args: list[str], target_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sole payload-sink bypass must follow a successful flush, not sit in `finally`."""
    from science_tool.budget import sink as sink_module

    def _boom(self: object) -> None:
        raise RuntimeError("render failed")

    monkeypatch.setattr(sink_module.BoundedSink, "flush", _boom)
    result = _invoke([*_scope_project(args, project), "--output", str(project / target_name)])
    assert result.exit_code != 0
    assert "wrote" not in result.output


def test_tasks_list_json_reports_the_full_total(project: Path) -> None:
    result = _invoke(["tasks", "list", "--status", "proposed", "--format", "json"])
    assert json.loads(result.output)["truncation"]["total"] == 395
```

- [ ] **Step 6: Run the regression suite**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression.py -v`
Expected: PASS (24 cases across all four wired commands in every supported format;
`entities inventory` is JSON-only)

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
registry SSOT with shapes (1); command-payload ceiling (3, tested explicitly); per-shape projection
with refusal for unregistered shapes (1, 10, 12); truncation visible in both supported formats
(6, 11);
counting semantics (2); uniform `--output` (7, 11, 12, guarded in 13); working-set default (7);
health classification correction (9); severity as a threshold defaulting to `warn` (9, 10); row
caps as the real mechanism (10); `total_issues` invariance (8, 10, 11); comparable
`displayed_issues` (8, 10); `unwired_checks` never filtered (9, 10); all guards (13).

**Corrections to the superseded plan, each with a covering test.** Ten commands no longer
claimed to inherit budgets — they are in `DEFERRED` and guarded (Task 1, Task 13). `health`'s
text branch reaches the sink (Task 11 Steps 4–6, `test_table_output_file_is_non_empty_and_complete`).
`tasks list` projects both supported formats (Task 7,
`test_table_branch_is_projected_and_stays_within_budget`).
`complete_via` derived from the invocation (Task 5, `test_user_selection_is_preserved`).
`displayed_issues` via `count_issues` (Task 8, `test_displayed_issues_uses_the_same_counting_rules_as_total`).
`data audit`'s text branch budgeted with the correct `render_json` signatures (Task 12).
Guards cover every leaf command and prove per-command sink construction (Task 13). The broken
monkeypatch is fixed: `stub_report` patches `science_tool.graph.health.build_health_report` at
its source, since `health_cli` imports it inside the function body.

**Type consistency.** `CommandBudget(max_chars, shape, max_rows)` used identically in Tasks 1, 3,
6, 13. `BoundedSink(budget, *, output_path, command_path, complete_via)` constructed identically
in Tasks 7, 11, 12; Task 3 enforces that `complete_via` is non-empty exactly for budgeted stdout
sinks. `ProjectedRows.rows/.omitted/.total/.truncated` consumed in Tasks 6, 7.
`meets_threshold(row, threshold)` (Task 9) called by `_project_section` (Task 10).
`count_issues(report)` (Task 8) called by `project_health_report` (Task 10) and its test.
`build_complete_via(ctx, *, output_hint)` (Task 5) used in Tasks 7, 11, 12. `visible_len` (Task 2)
used in Tasks 3, 7, 11, 13.

**Second-review corrections, each with a covering test.** `count_issues` consumes the real
`LayeredClaimHealthReport` — both issue lists plus coverage gaps derived from the two
`CoverageMetric` fields — and `build_health_report` assembles the actual body before calling it,
so no synthetic normalization can drift (Task 8,
`test_rival_model_gaps_count_alongside_migration_issues`,
`test_each_incomplete_coverage_metric_counts_as_one_gap`). `DEFERRED` is defined by growability
rather than a size floor, giving `tasks archive` a truthful home (Task 1,
`test_a_growable_but_small_command_can_be_deferred`). `data audit --fix` refuses to mutate at all
unless the report has an unbounded destination (Task 12,
`test_fix_without_output_refuses_before_moving_any_file`,
`test_fix_with_output_mutates_and_writes_the_complete_report`). Success messages follow a
successful `flush()` instead of sitting in `finally` (Tasks 7 and 11,
`test_no_success_message_when_the_command_fails`). `ProjectedRows`/`project_rows` are generic, so
`tasks list` can project `Task` models (Task 4,
`test_projection_is_generic_over_non_mapping_rows`). The health fixture carries all four
`layered_claims` keys the renderer reads unconditionally (Task 11). `data audit` appears in the
regression matrix in both supported formats (Task 13); entity inventory remains JSON-only.
`build_complete_via` renders through `shlex.join`
(Task 5, `test_values_with_spaces_are_quoted`).

**Third-review corrections.** The `--fix` preflight is gone: it measured a text preview (~6.7k
chars for 100 violations) against a JSON document it does not bound (~20.4k for the same 100), so
it passed in exactly the cases that then failed. The structural gate replaces it, and
`BoundedSink.flush_check()` — added for that preflight and now unused — is removed with it
(Tasks 3 and 12). `build_health_report` hoists `layered_claims` into a typed local and overwrites
a placeholder `total_issues` on a real `HealthReport`, because the previous draft named a local
that does not exist and spread a `dict[str, Any]` into a `TypedDict` (Task 8). Generics use
`TypeVar` + `Generic`: PEP 695 `class Foo[T]` is Python 3.12 syntax and both packages and Pyright
are pinned to 3.11 (Task 4, Global Constraints). `SCALAR_SECTIONS` is an allow-list rather than a
type test, so a new boolean or integer section is refused rather than waved through (Task 10,
`test_unknown_scalar_section_refuses`). `emit_query_rows` reconciles `meta["returned_count"]`
against the projected rows and `tasks list` reports `only_status` instead of the now-incomplete
`exclude_status` (Tasks 6 and 7, `test_returned_count_is_reconciled_with_the_projected_rows`).

**Fourth-review corrections.** `Path.touch()` is not a writability check: it succeeds for an
existing directory and can succeed for a read-only file. Before `apply_fixes`, `data audit`
now rejects directory-valued `--output` arguments and reserves a writable same-directory
temporary file without touching an existing report; missing-parent, directory, and reservation
failure regressions prove the tree remains intact (Task 12). Entity-inventory regressions pass
`--project-root` explicitly in both Task 12 and Task 13: its current Click default is
`Path.cwd()` evaluated when the command module is imported, so changing directory later does not
retarget the invocation.

**Pre-flight rulings.** The invariant covers payload output: every payload byte goes through the
sink, while one fixed-shape bounded control notice after a successful `--output` flush is the sole
bypass. The failure regression exercises that ordering in every supported file-output path
(Tasks 7, 11–13). A budgeted stdout sink rejects missing `complete_via` at construction; file and
unbudgeted sinks remain valid without it, and no synthesized escape remains (Task 3).
`count_issues` now accepts only the complete `HealthReport` / projected-report shape and rejects
missing or wrongly typed root and nested fields instead of converting them to empty/zero
(Task 8). Unknown severities raise rather than rank as errors (Task 9). The projector rejects
non-list row sections, malformed nested `findings`, and non-mapping registered object sections
while preserving registered scalars (Task 10). Format coverage says “every supported format”
throughout: `tasks list`, `health`, and `data audit` cover table and JSON; entity inventory stays
JSON-only (Tasks 7, 11–13).

**Important pre-flight review fixes.** Strict health counting now validates every list member and
the boolean issue-membership fields it reads, including managed artifacts and nested prose
findings (Task 8). `meets_threshold` distinguishes a missing `severity` key from a present
`None`: only the missing key survives, while any present unregistered/non-string value raises
(Task 9). Health projection validates mapping members and the full required shapes of its
registered mapping, nested-report, and scalar sections before filtering or capping (Task 10).

**Whole-branch review fixes.** File sinks write to a same-directory temporary file, flush and
`fsync` it, and atomically replace the destination; failures clean up the temporary file and
preserve any prior destination. Mutation flows explicitly reserve that temporary destination
before acting. `data audit --fix` also resolves the requested output, every violation source,
and every proposed destination through absolute paths and symlinks, refusing equality and
ancestor/descendant overlaps before mutation. The command path and selected options are
reconstructed as tokens and the entire
invocation passes through `shlex.join`. The sole sink bypass is a single-line control notice
with an explicit 8,192-visible-character ceiling, not a “fixed success” string. Strict health
counting and its validation helpers live cohesively in `graph/health_count.py`, leaving
`graph/health.py` focused on aggregation.

**Known limits, stated.** Guard 2 proves sink *construction*, not that every branch routes
through it — Task 11 Step 5's grep and the regression suite cover the rest. The `DEFERRED` table
is a bookkeeping ratchet: it prevents silence, not oversized output, and those commands stay
unbounded until 1b. The `--fix` gate is coarser than strictly necessary — it fires on any
violation, including `leaked_payload` rows the fixer only flags — because the precise version
would depend on `data_audit._planned_action` staying in lockstep with `apply_fixes`, which
nothing enforces. It is a deliberate behaviour change to an existing command. Reserving a
writable sibling before mutation removes known path/type/permission failures; it does not make
`apply_fixes` transactional or prevent a later flush failure caused by disk exhaustion or an
external filesystem change. A later mutation/render failure can still leave the project tree
changed because `apply_fixes` is not transactional, but the reserved report destination remains
byte-for-byte intact and no sibling temporary file leaks.

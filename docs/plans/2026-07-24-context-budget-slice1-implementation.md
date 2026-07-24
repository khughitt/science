# Context Budget — Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound the stdout size of agent-facing `science` commands so no invocation can flood an
agent's context, while keeping a guaranteed-complete file escape.

**Architecture:** Two phases that must not be collapsed. **Projection** runs before
serialization, is shape-aware, and produces a structurally valid payload plus counts of what it
dropped. **`BoundedSink`** runs after rendering, routes to stdout or a file, measures, and raises
if a projected payload still exceeds its ceiling. One sink per command invocation, threaded
through both existing emitters, so a command rendering 21 tables gets one command-total ceiling.

**Tech Stack:** Python 3.12+, Click, Rich, Pydantic, pytest. All work is in the `science/`
package (`science/pyproject.toml`).

**Parent design:**
[`2026-07-24-agent-context-budget-program-design.md`](2026-07-24-agent-context-budget-program-design.md)
(rev 4). Read its "Slice 1 — the context-budget contract" section before starting.

## Global Constraints

- Run everything from `science/` — `cd science && uv run --frozen pytest`. There is no root
  `pyproject.toml`; running `uv run` from the repo root is the most common orientation mistake.
- Lint and types from `science/`: `uv run ruff check` and `uv run pyright`. Pyright is configured
  once by `pyrightconfig.json` at the repo root; test directories are not type-checked.
- **The core invariant:** stdout is always budgeted; `--output PATH` is always complete. No flag
  makes stdout unbounded.
- **Semantic truncation never happens in the sink.** The sink only routes, measures, and raises.
- **`total_issues` never changes meaning.** It stays the unfiltered clean-report gate.
- Composition over inheritance; explicit over defensive; fail early instead of silent fallbacks.
- No "legacy"/"compatibility" layers. No `Unified` prefix on component names.
- Conventional commits. No AI-attribution trailers on commits or PRs.
- Use `~/d/` or relative paths in docs and code, never `/home/keith/` or `/mnt/ssd/Dropbox/`.

## File Structure

**New package `science/src/science_tool/budget/`** — domain-agnostic budgeting. Kept free of any
health/task/entity imports so nothing domain-specific leaks into the mechanism.

| File | Responsibility |
|---|---|
| `budget/__init__.py` | Re-exports the public surface. |
| `budget/registry.py` | `CommandBudget`, the `BUDGETS` table, `EXEMPTIONS`, `lookup()`. Single SSOT for every ceiling. |
| `budget/measure.py` | `visible_len()` (ANSI-stripped), `BUDGET_CONSOLE_WIDTH`, `render_to_text()`. |
| `budget/sink.py` | `BoundedSink`, `BudgetExceeded`. Routing + measurement + backstop only. |
| `budget/projection.py` | `project_rows()`, `ProjectedRows`. Row-shape projection only. |

**Modified:**

| File | Change |
|---|---|
| `output.py` | `emit` and `emit_query_rows` accept an optional `sink`; `emit_query_rows` applies row projection and emits truncation metadata. |
| `styles.py` | `get_console` / `_new_console` accept a `width`. |
| `tasks_cli.py` | Working-set default, `--output`, sink wiring. |
| `tasks_display.py` | `render_tasks_table` renders into the sink instead of printing. |
| `graph/health_projection.py` (new) | Health-specific projection: severity threshold, section classification, per-section caps. Lives with health, not in `budget/`. |
| `graph/health_cli.py` | `--severity`, `--output`, projection + sink wiring. |
| `entities_inventory_cli.py` | Refuse past budget. |
| `data_cli.py` | Refuse past budget. |

**Tests:** one file per task under `science/tests/`, plus three guards in
`tests/test_budget_boundary.py`.

---

### Task 1: Budget registry

**Files:**
- Create: `science/src/science_tool/budget/__init__.py`
- Create: `science/src/science_tool/budget/registry.py`
- Test: `science/tests/test_budget_registry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CommandBudget(max_rows: int | None, max_chars: int)`,
  `BUDGETS: dict[str, CommandBudget]`, `EXEMPTIONS: dict[str, str]`,
  `lookup(command_path: str) -> CommandBudget | None`. Command paths are space-joined Click
  paths without the root, e.g. `"tasks list"`, `"health"`, `"entities inventory"`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_registry.py
from __future__ import annotations

import pytest

from science_tool.budget.registry import BUDGETS, EXEMPTIONS, CommandBudget, lookup


def test_lookup_returns_budget_for_registered_command() -> None:
    budget = lookup("tasks list")
    assert isinstance(budget, CommandBudget)
    assert budget.max_chars > 0


def test_lookup_returns_none_for_unregistered_command() -> None:
    assert lookup("tasks add") is None


def test_every_budget_has_a_positive_char_ceiling() -> None:
    for path, budget in BUDGETS.items():
        assert budget.max_chars > 0, f"{path} has a non-positive ceiling"


def test_every_exemption_states_a_reason() -> None:
    for path, reason in EXEMPTIONS.items():
        assert reason.strip(), f"{path} is exempt with no reason"


def test_budgets_and_exemptions_are_disjoint() -> None:
    assert not (set(BUDGETS) & set(EXEMPTIONS))


@pytest.mark.parametrize(
    "path",
    [
        "entities inventory",
        "data audit",
        "entity list",
        "curate inventory",
        "prose lint",
        "health",
        "tasks list",
        "questions list",
        "validate",
        "interpretations list",
        "curate consolidation-candidates",
        "entity needs-review",
        "feedback list",
        "discussions list",
    ],
)
def test_every_measured_offender_is_budgeted(path: str) -> None:
    """The 14 commands measured over 20k chars on 2026-07-24 must all carry a ceiling."""
    assert lookup(path) is not None, f"{path} exceeded 20k chars in the audit but has no budget"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget'`

- [ ] **Step 3: Write the registry**

```python
# science/src/science_tool/budget/registry.py
"""Single source of truth for per-command output ceilings.

Ceilings are in *visible* characters (ANSI stripped), measured at
``BUDGET_CONSOLE_WIDTH``. They exist to bound what an agent's context absorbs from one
command, not to make output pretty. Values were chosen from the 2026-07-24 audit of
``~/d/natural-systems``, the largest adopting project, with headroom.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandBudget:
    """A ceiling for one command's stdout.

    ``max_rows`` bounds row-shaped payloads before serialization; ``None`` means the
    command's projection bounds itself some other way (``health`` uses per-section caps).
    ``max_chars`` is the backstop the sink enforces after rendering.
    """

    max_chars: int
    max_rows: int | None = None


BUDGETS: dict[str, CommandBudget] = {
    # Row-shaped query commands.
    "tasks list": CommandBudget(max_chars=20_000, max_rows=40),
    "entity list": CommandBudget(max_chars=30_000, max_rows=100),
    "entity needs-review": CommandBudget(max_chars=20_000, max_rows=60),
    "questions list": CommandBudget(max_chars=30_000, max_rows=80),
    "interpretations list": CommandBudget(max_chars=30_000, max_rows=80),
    "discussions list": CommandBudget(max_chars=20_000, max_rows=60),
    "feedback list": CommandBudget(max_chars=20_000, max_rows=60),
    "curate consolidation-candidates": CommandBudget(max_chars=20_000, max_rows=60),
    "prose lint": CommandBudget(max_chars=30_000, max_rows=100),
    "validate": CommandBudget(max_chars=30_000, max_rows=100),
    # Heterogeneous report: bounded by its own per-section projection.
    "health": CommandBudget(max_chars=30_000, max_rows=None),
    # Bulk dumps: any real project blows these, which is the point — they route to --output.
    "entities inventory": CommandBudget(max_chars=20_000, max_rows=None),
    "data audit": CommandBudget(max_chars=20_000, max_rows=None),
    "curate inventory": CommandBudget(max_chars=20_000, max_rows=None),
}

EXEMPTIONS: dict[str, str] = {
    "tasks summary": "measured 1,692 chars on 2026-07-24; aggregate counts cannot grow with project size",
    "graph stats": "measured 341 chars on 2026-07-24; fixed-shape summary",
    "telemetry status": "measured 366 chars on 2026-07-24; fixed-shape summary",
}


def lookup(command_path: str) -> CommandBudget | None:
    """Return the budget for a space-joined Click path, or None when unregistered."""
    return BUDGETS.get(command_path)
```

```python
# science/src/science_tool/budget/__init__.py
"""Command output budgeting: registry, measurement, projection, sink."""

from science_tool.budget.registry import BUDGETS, EXEMPTIONS, CommandBudget, lookup

__all__ = ["BUDGETS", "EXEMPTIONS", "CommandBudget", "lookup"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_budget_registry.py -v`
Expected: PASS (7 tests, including 14 parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/budget/ science/tests/test_budget_registry.py
git commit -m "feat(budget): add per-command output ceiling registry"
```

---

### Task 2: Visible-character measurement and pinned width

**Files:**
- Create: `science/src/science_tool/budget/measure.py`
- Modify: `science/src/science_tool/styles.py:145` (`_new_console`), `:156` (`get_console`)
- Test: `science/tests/test_budget_measure.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `BUDGET_CONSOLE_WIDTH: int`, `visible_len(text: str) -> int`,
  `render_to_text(renderable: object) -> str`. `get_console` gains a keyword-only
  `width: int | None = None`.

Budget counts **ANSI-stripped visible characters**. `resolve_color_policy` (`styles.py:126`)
returns `NEVER` unless `FORCE_COLOR`/`--color` is set, so on the agent path visible characters
equal emitted characters. Counting visible characters keeps row selection identical across color
modes, which counting raw output would not.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_measure.py
from __future__ import annotations

from rich.table import Table

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH, render_to_text, visible_len


def test_visible_len_ignores_ansi_escapes() -> None:
    plain = "hello"
    colored = "\x1b[1;31mhello\x1b[0m"
    assert visible_len(plain) == 5
    assert visible_len(colored) == 5


def test_visible_len_counts_newlines() -> None:
    assert visible_len("ab\ncd") == 5


def test_render_to_text_uses_the_pinned_width() -> None:
    table = Table(title="T")
    table.add_column("C")
    table.add_row("x" * 500)
    text = render_to_text(table)
    widest = max(len(line) for line in text.splitlines())
    assert widest <= BUDGET_CONSOLE_WIDTH


def test_render_to_text_is_independent_of_terminal_columns(monkeypatch) -> None:
    table = Table(title="T")
    table.add_column("C")
    for i in range(20):
        table.add_row(f"row-{i}")

    monkeypatch.setenv("COLUMNS", "80")
    narrow = render_to_text(table)
    monkeypatch.setenv("COLUMNS", "400")
    wide = render_to_text(table)
    assert narrow == wide
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_measure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget.measure'`

- [ ] **Step 3: Add the width parameter to the console factory**

In `science/src/science_tool/styles.py`, change `_new_console` and `get_console`:

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

Note the changed cache condition: a console built for a specific `file` **or** `width` is never
cached, because the cache is keyed only by context.

- [ ] **Step 4: Write the measurement module**

```python
# science/src/science_tool/budget/measure.py
"""Deterministic size measurement for budgeted output.

Two decisions are pinned here so the same data always costs the same budget:

- **Width** is fixed at ``BUDGET_CONSOLE_WIDTH`` rather than inherited from Rich's
  non-TTY default, which varies with ``COLUMNS``.
- **Color** is excluded: we count ANSI-stripped *visible* characters. Under
  ``--color always`` or ``FORCE_COLOR`` the emitted bytes exceed the budget by the ANSI
  overhead. That is a human at a terminal, not an agent, and it keeps row selection
  identical across color modes. ``resolve_color_policy`` defaults to ``NEVER``, so on the
  agent path visible characters and emitted characters are the same.
"""

from __future__ import annotations

import re
from io import StringIO

from science_tool.styles import get_console

BUDGET_CONSOLE_WIDTH = 100

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def visible_len(text: str) -> int:
    """Length of ``text`` with ANSI escape sequences removed."""
    return len(_ANSI_RE.sub("", text))


def render_to_text(renderable: object) -> str:
    """Render a Rich renderable to a string at the pinned budget width."""
    buffer = StringIO()
    console = get_console(file=buffer, width=BUDGET_CONSOLE_WIDTH)
    console.print(renderable)
    return buffer.getvalue()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_budget_measure.py tests/test_styles.py -v`
Expected: PASS. If `tests/test_styles.py` does not exist, run only the first file.

- [ ] **Step 6: Verify no console regressions elsewhere**

Run: `cd science && uv run --frozen pytest -k "console or color or styles" -v`
Expected: PASS — the `width=None` default must leave every existing call site unchanged.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/budget/measure.py science/src/science_tool/styles.py science/tests/test_budget_measure.py
git commit -m "feat(budget): add ANSI-stripped measurement at a pinned console width"
```

---

### Task 3: `BoundedSink`

**Files:**
- Create: `science/src/science_tool/budget/sink.py`
- Test: `science/tests/test_budget_sink.py`

**Interfaces:**
- Consumes: `CommandBudget` (Task 1), `visible_len` (Task 2).
- Produces: `BudgetExceeded(Exception)`,
  `BoundedSink(budget: CommandBudget | None, output_path: Path | None = None)` with
  `.write(text: str) -> None`, `.is_file_sink: bool`, `.close() -> None`, and
  `.command_path: str` set by the constructor caller for error messages.

The sink **never truncates**. If a projected payload still exceeds `max_chars`, that is a budget
misconfiguration and it raises.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_sink.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.budget.registry import CommandBudget
from science_tool.budget.sink import BoundedSink, BudgetExceeded


def test_stdout_sink_accepts_output_under_budget(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=100), command_path="tasks list")
    sink.write("x" * 50)
    sink.close()
    assert capsys.readouterr().out == "x" * 50


def test_stdout_sink_raises_when_projected_output_still_exceeds(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=10), command_path="tasks list")
    with pytest.raises(BudgetExceeded) as excinfo:
        sink.write("x" * 50)
    assert "tasks list" in str(excinfo.value)


def test_accumulated_writes_share_one_command_total_ceiling() -> None:
    """A command emitting many sections gets ONE ceiling, not one per section."""
    sink = BoundedSink(CommandBudget(max_chars=100), command_path="health")
    sink.write("x" * 60)
    with pytest.raises(BudgetExceeded):
        sink.write("x" * 60)


def test_file_sink_is_never_truncated(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    sink = BoundedSink(CommandBudget(max_chars=10), output_path=target, command_path="health")
    payload = "y" * 10_000
    sink.write(payload)
    sink.close()
    assert target.read_text() == payload


def test_file_sink_reports_itself_as_a_file_sink(tmp_path: Path) -> None:
    sink = BoundedSink(CommandBudget(max_chars=10), output_path=tmp_path / "o.txt", command_path="health")
    assert sink.is_file_sink is True
    sink.close()


def test_unbudgeted_command_is_unbounded_on_stdout(capsys) -> None:
    sink = BoundedSink(None, command_path="tasks add")
    sink.write("z" * 100_000)
    sink.close()
    assert len(capsys.readouterr().out) == 100_000


def test_ansi_does_not_count_against_the_ceiling(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=10), command_path="tasks list")
    sink.write("\x1b[1;31m" + "x" * 9 + "\x1b[0m")
    sink.close()
    assert "x" * 9 in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_sink.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget.sink'`

- [ ] **Step 3: Write the sink**

```python
# science/src/science_tool/budget/sink.py
"""Output routing, measurement, and the ceiling backstop.

The sink is deliberately dumb about content. It holds characters, not rows, so it
CANNOT count omitted items, cannot insert truncation metadata into an already-serialized
document, and cannot cut without risking a severed table box or a split ANSI escape.
Semantic truncation belongs in projection, which runs before serialization.

If a projected payload still exceeds ``max_chars``, that is a budget misconfiguration to
fix, not something to trim blindly -- so this raises.
"""

from __future__ import annotations

from pathlib import Path

import click

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import CommandBudget


class BudgetExceeded(click.ClickException):
    """A projected payload still exceeded its ceiling."""


class BoundedSink:
    """Routes a command's output to stdout (budgeted) or a file (always complete).

    One sink per command invocation. Threading the same sink through every emitter call
    is what gives a multi-section command one command-total ceiling instead of one
    ceiling per section.
    """

    def __init__(
        self,
        budget: CommandBudget | None,
        *,
        output_path: Path | None = None,
        command_path: str = "",
    ) -> None:
        self._budget = budget
        self._output_path = output_path
        self._command_path = command_path
        self._written = 0
        self._handle = output_path.open("w", encoding="utf-8") if output_path is not None else None

    @property
    def is_file_sink(self) -> bool:
        return self._handle is not None

    @property
    def command_path(self) -> str:
        return self._command_path

    def write(self, text: str) -> None:
        if self._handle is not None:
            self._handle.write(text)
            return

        if self._budget is not None:
            self._written += visible_len(text)
            if self._written > self._budget.max_chars:
                raise BudgetExceeded(
                    f"{self._command_path or 'command'} produced {self._written} visible chars "
                    f"after projection, over its {self._budget.max_chars} ceiling. "
                    f"This is a budget misconfiguration; rerun with --output PATH for the "
                    f"complete payload."
                )

        click.echo(text, nl=False)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_budget_sink.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Export from the package**

```python
# science/src/science_tool/budget/__init__.py
"""Command output budgeting: registry, measurement, projection, sink."""

from science_tool.budget.measure import BUDGET_CONSOLE_WIDTH, render_to_text, visible_len
from science_tool.budget.registry import BUDGETS, EXEMPTIONS, CommandBudget, lookup
from science_tool.budget.sink import BoundedSink, BudgetExceeded

__all__ = [
    "BUDGETS",
    "BUDGET_CONSOLE_WIDTH",
    "EXEMPTIONS",
    "BoundedSink",
    "BudgetExceeded",
    "CommandBudget",
    "lookup",
    "render_to_text",
    "visible_len",
]
```

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/budget/ science/tests/test_budget_sink.py
git commit -m "feat(budget): add BoundedSink with command-total ceiling and complete file sink"
```

---

### Task 4: Row projection

**Files:**
- Create: `science/src/science_tool/budget/projection.py`
- Test: `science/tests/test_budget_projection.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ProjectedRows(rows: list[Mapping[str, Any]], omitted: int, total: int)` with a
  `.truncated: bool` property, and
  `project_rows(rows: Sequence[Mapping[str, Any]], max_rows: int | None) -> ProjectedRows`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_budget_projection.py
from __future__ import annotations

from science_tool.budget.projection import project_rows

ROWS = [{"id": f"t{i:03d}"} for i in range(100)]


def test_projection_is_a_noop_under_the_cap() -> None:
    result = project_rows(ROWS[:5], max_rows=40)
    assert result.rows == ROWS[:5]
    assert result.omitted == 0
    assert result.total == 5
    assert result.truncated is False


def test_projection_keeps_the_first_n_in_caller_order() -> None:
    result = project_rows(ROWS, max_rows=40)
    assert result.rows == ROWS[:40]
    assert result.omitted == 60
    assert result.total == 100
    assert result.truncated is True


def test_none_cap_disables_row_projection() -> None:
    result = project_rows(ROWS, max_rows=None)
    assert result.rows == ROWS
    assert result.omitted == 0
    assert result.truncated is False


def test_empty_rows_project_cleanly() -> None:
    result = project_rows([], max_rows=40)
    assert result.rows == []
    assert result.total == 0
    assert result.truncated is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_budget_projection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.budget.projection'`

- [ ] **Step 3: Write the projection**

```python
# science/src/science_tool/budget/projection.py
"""Semantic narrowing of row-shaped payloads, before serialization.

Projection runs early precisely so the omitted count is known and can be carried in the
payload itself. Doing this after rendering would leave only characters.
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
    reason (``tasks list`` sorts by status rank then id), and re-sorting here would make
    the truncated view disagree with the complete one.
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

### Task 5: Wire the emitters to projection and the sink

**Files:**
- Modify: `science/src/science_tool/output.py:18` (`emit`), `:73` (`emit_query_rows`)
- Test: `science/tests/test_output_budgeting.py`

**Interfaces:**
- Consumes: `BoundedSink` (Task 3), `project_rows` (Task 4), `render_to_text` (Task 2),
  `CommandBudget` (Task 1).
- Produces: `emit(..., sink: BoundedSink | None = None)` and
  `emit_query_rows(..., sink: BoundedSink | None = None, complete_via: str | None = None)`.
  When projection drops rows, the JSON payload gains
  `truncation: {"omitted": int, "total": int, "complete_via": str}` and the text output gains a
  footer.

`complete_via` is the exact command string printed to the user and embedded in JSON, e.g.
`"science tasks list --format json --output tasks.json"`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_output_budgeting.py
from __future__ import annotations

import json

from science_tool.budget.registry import CommandBudget
from science_tool.budget.sink import BoundedSink
from science_tool.output import emit_query_rows

COLUMNS = [("id", "ID"), ("title", "Title")]
ROWS = [{"id": f"t{i:03d}", "title": f"task {i}"} for i in range(100)]


def _emit(fmt: str, sink: BoundedSink) -> None:
    emit_query_rows(
        output_format=fmt,
        title="Tasks",
        columns=COLUMNS,
        rows=ROWS,
        sink=sink,
        complete_via="science tasks list --format json --output tasks.json",
    )


def test_json_truncation_metadata_lives_in_the_payload(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=200_000, max_rows=40), command_path="tasks list")
    _emit("json", sink)
    sink.close()
    payload = json.loads(capsys.readouterr().out)
    assert payload["truncation"]["omitted"] == 60
    assert payload["truncation"]["total"] == 100
    assert payload["truncation"]["complete_via"].endswith("--output tasks.json")
    assert len(payload["rows"]) == 40


def test_truncated_json_still_parses_as_one_document(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=200_000, max_rows=5), command_path="tasks list")
    _emit("json", sink)
    sink.close()
    json.loads(capsys.readouterr().out)  # raises if diagnostics leaked into stdout


def test_untruncated_json_has_no_truncation_key(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=200_000, max_rows=500), command_path="tasks list")
    _emit("json", sink)
    sink.close()
    assert "truncation" not in json.loads(capsys.readouterr().out)


def test_table_footer_names_the_omitted_count_and_escape(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=200_000, max_rows=40), command_path="tasks list")
    _emit("table", sink)
    sink.close()
    out = capsys.readouterr().out
    assert "40 of 100" in out
    assert "--output tasks.json" in out


def test_table_output_is_never_cut_mid_box(capsys) -> None:
    sink = BoundedSink(CommandBudget(max_chars=200_000, max_rows=3), command_path="tasks list")
    _emit("table", sink)
    sink.close()
    out = capsys.readouterr().out
    box_lines = [line for line in out.splitlines() if line.startswith(("┏", "┡", "└"))]
    assert len(box_lines) >= 3  # top, header rule, bottom — all present
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_output_budgeting.py -v`
Expected: FAIL — `TypeError: emit_query_rows() got an unexpected keyword argument 'sink'`

- [ ] **Step 3: Rewrite the emitters**

Replace `emit` and `emit_query_rows` in `science/src/science_tool/output.py`:

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
    """Emit ``payload`` as JSON on stdout when ``output_format == "json"``, else
    invoke ``render_text`` for human output.

    Serialization kwargs mirror ``json.dumps`` so existing call sites keep their
    exact byte output. Diagnostics must never reach stdout through this function:
    the JSON branch writes only ``json.dumps(payload, ...)``. Truncation is therefore
    recorded *inside* ``payload`` by the caller's projection, never echoed alongside it.

    When ``sink`` is None the historical unbudgeted behaviour is preserved exactly.
    """
    if output_format == "json":
        rendered = json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii, default=default)
        if sink is None:
            click.echo(rendered)
        else:
            sink.write(rendered + "\n")
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
    complete_via: str | None = None,
) -> None:
    max_rows = sink.max_rows if sink is not None else None
    projected = project_rows(rows, max_rows)
    rows_list = projected.rows

    payload: dict[str, Any] = {"format": "json", "rows": rows_list}
    if meta is not None:
        payload["meta"] = dict(meta)
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": complete_via or "",
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
            console = get_console(file=click.get_text_stream("stdout"))
            console.print(table)
            return

        text = render_to_text(table)
        if projected.truncated:
            text += (
                f"showing {len(rows_list)} of {projected.total} rows\n"
                f"  complete output:  {complete_via or '(pass --output PATH)'}\n"
            )
        sink.write(text)

    emit(output_format=output_format, payload=payload, render_text=_render, sink=sink)
```

Add these imports at the top of `output.py`:

```python
from science_tool.budget.measure import render_to_text
from science_tool.budget.projection import project_rows
from science_tool.budget.sink import BoundedSink
```

- [ ] **Step 4: Expose `max_rows` on the sink — None for a file sink**

Add to `BoundedSink` in `science/src/science_tool/budget/sink.py`:

```python
    @property
    def max_rows(self) -> int | None:
        """Row cap for projection, or None when nothing should be dropped.

        A file sink always returns None: `--output PATH` is guaranteed complete, so
        projection must not run at all when writing to one. Returning the budget's cap
        here would silently truncate the file and break the core invariant.
        """
        if self._handle is not None:
            return None
        return self._budget.max_rows if self._budget is not None else None
```

Add the covering test to `science/tests/test_budget_sink.py`:

```python
def test_file_sink_reports_no_row_cap(tmp_path: Path) -> None:
    """--output is complete, so projection must not run against a file sink."""
    sink = BoundedSink(
        CommandBudget(max_chars=10, max_rows=5),
        output_path=tmp_path / "o.json",
        command_path="tasks list",
    )
    assert sink.max_rows is None
    sink.close()


def test_stdout_sink_reports_the_budget_row_cap() -> None:
    sink = BoundedSink(CommandBudget(max_chars=10, max_rows=5), command_path="tasks list")
    assert sink.max_rows == 5
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_output_budgeting.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Verify every existing emitter call site is unchanged**

Run: `cd science && uv run --frozen pytest -v`
Expected: PASS. `sink=None` must preserve byte-identical historical output; any failure here
means the default path changed and must be fixed before continuing.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/output.py science/src/science_tool/budget/sink.py science/tests/test_output_budgeting.py
git commit -m "feat(budget): route emitters through projection and BoundedSink"
```

---

### Task 6: `tasks list` — working-set default, `--output`, sink wiring

**Files:**
- Modify: `science/src/science_tool/tasks_cli.py:487-605` (`tasks_list`)
- Modify: `science/src/science_tool/tasks_display.py:70` (`render_tasks_table`)
- Test: `science/tests/test_tasks_list_budget.py`

**Interfaces:**
- Consumes: `BoundedSink`, `lookup`, `emit_query_rows` with `sink`/`complete_via`.
- Produces: `render_tasks_table(tasks, resolver=None, sink=None) -> None`. `tasks list` gains
  `--output PATH` and defaults to the working set.

**Behaviour change:** with no `--status` and no `--all`, `tasks list` returns only `active` and
`blocked` tasks. `--all` keeps its existing meaning — *include done and retired* — and does not
bypass the ceiling.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_tasks_list_budget.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main

TASKS = "\n".join(
    f"""## [t{i:03d}] Task {i}
- priority: P2
- status: {"active" if i < 3 else "proposed"}
- created: 2026-01-01

Body for task {i}.
"""
    for i in range(60)
)


def _project(root: Path) -> None:
    (root / "science.yaml").write_text("id: demo\nname: demo\n")
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "active.md").write_text(TASKS)


def test_default_list_shows_only_the_working_set() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = runner.invoke(main, ["tasks", "list", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert {row["status"] for row in payload["rows"]} == {"active"}


def test_explicit_status_still_reaches_proposed_tasks() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = runner.invoke(main, ["tasks", "list", "--status", "proposed", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert len(payload["rows"]) > 0


def test_output_file_is_complete_and_untruncated() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        root = Path(fs)
        _project(root)
        target = root / "tasks.json"
        result = runner.invoke(
            main,
            ["tasks", "list", "--status", "proposed", "--format", "json", "--output", str(target)],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(target.read_text())
        assert len(payload["rows"]) == 57
        assert "truncation" not in payload


def test_output_path_is_echoed_to_stdout() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        root = Path(fs)
        _project(root)
        target = root / "tasks.json"
        result = runner.invoke(main, ["tasks", "list", "--format", "json", "--output", str(target)])
        assert result.exit_code == 0, result.output
        assert str(target) in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_tasks_list_budget.py -v`
Expected: FAIL — `no such option: --output`, and the default-list test fails because proposed
tasks are still returned.

- [ ] **Step 3: Make `render_tasks_table` sink-aware**

In `science/src/science_tool/tasks_display.py`, replace the tail of `render_tasks_table`:

```python
def render_tasks_table(
    tasks: list[Task],
    resolver: ReadinessResolver | None = None,
    sink: BoundedSink | None = None,
) -> None:
    """Render a colored Rich table of tasks, through ``sink`` when one is supplied."""
    # ... table construction unchanged, up to and including the add_row loop ...

    lines: list[str] = []
    if resolver is not None:
        for t in tasks:
            summary = render_blocker_summary(t, resolver)
            if summary is not None:
                lines.append(summary)

    if sink is None:
        console = get_console()
        console.print(table)
        for line in lines:
            console.print(line)
        return

    text = render_to_text(table)
    if lines:
        text += "\n".join(lines) + "\n"
    sink.write(text)
```

Add imports at the top of `tasks_display.py`:

```python
from science_tool.budget.measure import render_to_text
from science_tool.budget.sink import BoundedSink
```

The blocker summaries go through the same sink so they count against the command-total ceiling
rather than escaping it.

- [ ] **Step 4: Change the default filter and add `--output`**

In `science/src/science_tool/tasks_cli.py`, add the option and rewire the body:

```python
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
```

Add `output_path: Path | None` to the `tasks_list` signature, then inside the function:

```python
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    WORKING_SET = ("active", "blocked")

    matched = list_tasks(
        DEFAULT_TASKS_DIR,
        project_root=Path.cwd(),
        priority=priority,
        status=status,
        related=related,
        group=group,
        aspects=list(aspects) or None,
        include_done=show_all,
    )
    if status is None and not show_all:
        matched = [t for t in matched if t.status in WORKING_SET]
    matched = sort_tasks(matched)

    sink = BoundedSink(lookup("tasks list"), output_path=output_path, command_path="tasks list")
    complete_via = "science tasks list --format json --output tasks.json"
```

Pass `sink=sink, complete_via=complete_via` to the `emit_query_rows` call, pass
`sink=sink` to `render_tasks_table`, and close the sink at the end:

```python
    finally:
        sink.close()
        if output_path is not None:
            click.echo(f"wrote {len(matched)} tasks to {output_path}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_tasks_list_budget.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the existing task suite for regressions**

Run: `cd science && uv run --frozen pytest tests/test_tasks_cli.py tests/test_tasks.py tests/test_tasks_archive.py -v`
Expected: PASS. Tests asserting the old unfiltered default must be updated to pass an explicit
`--status`, since the default is now the working set by design.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/tasks_cli.py science/src/science_tool/tasks_display.py science/tests/test_tasks_list_budget.py
git commit -m "feat(tasks): default list to the working set and add a complete --output sink"
```

---

### Task 7: Health severity threshold and section classification

**Files:**
- Create: `science/src/science_tool/graph/health_projection.py`
- Test: `science/tests/test_health_projection.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `SEVERITY_SECTIONS: frozenset[str]`, `COUNTS_AS_ISSUE_SECTIONS: frozenset[str]`,
  `UNFILTERED_SECTIONS: frozenset[str]`, `SEVERITY_ORDER: dict[str, int]`,
  `meets_threshold(row: Mapping[str, Any], threshold: str) -> bool`.

**Classification, verified against the TypedDicts — do not re-derive it:**

| Signal | Sections |
|---|---|
| `severity` | `validation`, `schema_invalid` (`graph/health.py:43`), `dataset_anomalies`, `entity_identity` (`graph/health_checks/entity_identity.py:13`), `cross_paper_evidence.findings` (`graph/health_checks/cross_paper_evidence.py:15`) |
| `severity` **and** `counts_as_issue` | `prose_epistemics.findings` (`graph/health_checks/prose_epistemics.py:41`) |
| `counts_as_issue` only | `managed_artifacts` (`project_artifacts/health_integration.py:20`) |
| neither | `agent_context`, `archive_lag`, `identity_policy`, `invalid_entity_aspects`, `layered_claims`, `legacy_task_type`, `lingering_tags_lines`, `unregistered_ref_kinds`, `unresolved_refs`, `tooling_scaffold` |

**`counts_as_issue` is issue-count membership, not severity.** It feeds `total_issues`
(`graph/health.py:370`) and is never a display filter. The two are orthogonal:
`prose_epistemics` emits `severity: "warning"` with `counts_as_issue: True`.

**`--severity` is a threshold, not equality.** `error` = errors only; `warn` = warnings and
errors; `all` = everything.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_health_projection.py
from __future__ import annotations

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


def test_prose_epistemics_is_severity_bearing() -> None:
    """It carries counts_as_issue too, but severity is what filters display."""
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


def test_warn_threshold_retains_errors_as_well_as_warnings() -> None:
    assert meets_threshold({"severity": "warning"}, "warn") is True
    assert meets_threshold({"severity": "error"}, "warn") is True
    assert meets_threshold({"severity": "info"}, "warn") is False


def test_error_threshold_retains_only_errors() -> None:
    assert meets_threshold({"severity": "error"}, "error") is True
    assert meets_threshold({"severity": "warning"}, "error") is False


def test_all_threshold_retains_everything() -> None:
    assert meets_threshold({"severity": "info"}, "all") is True
    assert meets_threshold({"severity": "warning"}, "all") is True


def test_counts_as_issue_never_filters_display() -> None:
    """A warning that counts as an issue is still hidden at --severity error."""
    row = {"severity": "warning", "counts_as_issue": True}
    assert meets_threshold(row, "error") is False


def test_row_without_severity_survives_every_threshold() -> None:
    assert meets_threshold({"code": "x"}, "error") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_projection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.health_projection'`

- [ ] **Step 3: Write the classification module**

```python
# science/src/science_tool/graph/health_projection.py
"""Health-report projection: severity thresholding and section classification.

Lives beside health rather than in ``budget/`` so the budgeting mechanism stays free of
domain knowledge.

The classification below was verified against the TypedDicts on 2026-07-24. Getting it
wrong is not cosmetic: treating ``cross_paper_evidence`` as a ``counts_as_issue`` section
hides its errors entirely, because it has no such field.

``counts_as_issue`` is ISSUE-COUNT MEMBERSHIP, not severity. It decides whether a row
feeds ``total_issues`` (``graph/health.py:370``) and is never used to filter display --
the two are orthogonal, and ``prose_epistemics`` emits ``severity: "warning"`` together
with ``counts_as_issue: True``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
        # An unwired check DID NOT RUN. health.py:60 keeps it out of total_issues so a
        # report containing one cannot claim the project is clean; hiding it behind a
        # severity default would defeat exactly that.
        "unwired_checks",
    }
)

SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "warn": 1, "error": 2}

_THRESHOLD_FLOOR: dict[str, int] = {"all": 0, "warn": 1, "error": 2}


def meets_threshold(row: Mapping[str, Any], threshold: str) -> bool:
    """True when ``row`` is at or above ``threshold``.

    A row with no ``severity`` key survives every threshold: absence of the signal is not
    evidence of low severity, and silently dropping such rows would hide findings.
    """
    severity = row.get("severity")
    if severity is None:
        return True
    floor = _THRESHOLD_FLOOR[threshold]
    return SEVERITY_ORDER.get(str(severity), 2) >= floor
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_health_projection.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/health_projection.py science/tests/test_health_projection.py
git commit -m "feat(health): classify report sections and add severity thresholding"
```

---

### Task 8: Health per-section row caps and `displayed_issues`

**Files:**
- Modify: `science/src/science_tool/graph/health_projection.py`
- Test: `science/tests/test_health_projection_caps.py`

**Interfaces:**
- Consumes: `meets_threshold`, the three section sets (Task 7).
- Produces: `SECTION_ROW_CAP: int`,
  `project_health_report(report: dict[str, Any], threshold: str, cap: int | None = None) -> dict[str, Any]`.
  The returned report has the same keys, adds `displayed_issues: int` and
  `section_omitted: dict[str, int]`, and leaves `total_issues` **untouched**.

**Severity does not solve the size problem.** All 361 of natural-systems' `validation` findings
are `severity: "warning"` against `total_issues` = 366, so an error-only default would display
nothing while announcing 366 issues. Row caps are the mechanism that bounds output; severity is
a user-facing lens. Default threshold is therefore `warn`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_health_projection_caps.py
from __future__ import annotations

from science_tool.graph.health_projection import SECTION_ROW_CAP, project_health_report


def _natural_systems_shaped_report() -> dict[str, object]:
    """All-warning validation with a non-zero total_issues — the real shape on 2026-07-24."""
    return {
        "validation": [
            {"severity": "warning", "code": "document_structure", "message": f"m{i}"} for i in range(361)
        ],
        "managed_artifacts": [{"counts_as_issue": False, "name": "a"}],
        "archive_lag": {"done_in_active": 4, "retired_in_active": 0, "missing_completed": 1},
        "unwired_checks": [],
        "total_issues": 366,
    }


def test_default_warn_threshold_does_not_empty_an_all_warning_report() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert len(projected["validation"]) > 0


def test_row_cap_bounds_a_large_section() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert len(projected["validation"]) == SECTION_ROW_CAP
    assert projected["section_omitted"]["validation"] == 361 - SECTION_ROW_CAP


def test_total_issues_is_never_rewritten() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["total_issues"] == 366


def test_displayed_issues_tracks_what_was_shown() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["displayed_issues"] < projected["total_issues"]
    assert projected["displayed_issues"] == SECTION_ROW_CAP


def test_error_threshold_hides_warnings_but_still_reports_them_as_omitted() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="error")
    assert projected["validation"] == []
    assert projected["section_omitted"]["validation"] == 361
    assert projected["total_issues"] == 366


def test_unfiltered_sections_are_untouched_by_threshold_and_cap() -> None:
    report = _natural_systems_shaped_report()
    report["unwired_checks"] = [{"name": f"check{i}"} for i in range(100)]
    projected = project_health_report(report, threshold="error")
    assert len(projected["unwired_checks"]) == 100


def test_counts_as_issue_section_is_not_severity_filtered() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="error")
    assert len(projected["managed_artifacts"]) == 1


def test_nested_findings_sections_are_projected_in_place() -> None:
    report = _natural_systems_shaped_report()
    report["cross_paper_evidence"] = {
        "status": "active",
        "findings": [{"severity": "error", "code": f"c{i}"} for i in range(100)],
    }
    projected = project_health_report(report, threshold="error")
    assert len(projected["cross_paper_evidence"]["findings"]) == SECTION_ROW_CAP
    assert projected["cross_paper_evidence"]["status"] == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_projection_caps.py -v`
Expected: FAIL — `ImportError: cannot import name 'project_health_report'`

- [ ] **Step 3: Add caps and the projector**

Append to `science/src/science_tool/graph/health_projection.py`:

```python
SECTION_ROW_CAP = 40

_NESTED_FINDING_SECTIONS = ("cross_paper_evidence", "prose_epistemics")


def _project_rows(
    rows: list[Any],
    section: str,
    threshold: str,
    cap: int,
    omitted: dict[str, int],
) -> list[Any]:
    if section in UNFILTERED_SECTIONS:
        return rows

    kept = [row for row in rows if not isinstance(row, dict) or meets_threshold(row, threshold)]
    dropped_by_threshold = len(rows) - len(kept)

    capped = kept[:cap]
    dropped_by_cap = len(kept) - len(capped)

    total_dropped = dropped_by_threshold + dropped_by_cap
    if total_dropped:
        omitted[section] = total_dropped
    return capped


def project_health_report(
    report: dict[str, Any],
    threshold: str,
    cap: int | None = None,
) -> dict[str, Any]:
    """Narrow a health report for display without changing what it claims.

    ``total_issues`` is copied through untouched: it is the clean-report gate
    (``graph/health_cli.py:158``) and redefining it as a displayed count would let a
    filtered report announce "Project is clean". ``displayed_issues`` and
    ``section_omitted`` are added alongside so the two can never silently diverge.
    """
    effective_cap = SECTION_ROW_CAP if cap is None else cap
    omitted: dict[str, int] = {}
    projected: dict[str, Any] = {}
    displayed = 0

    for key, value in report.items():
        if key in _NESTED_FINDING_SECTIONS and isinstance(value, dict):
            findings = value.get("findings")
            if isinstance(findings, list):
                kept = _project_rows(findings, key, threshold, effective_cap, omitted)
                projected[key] = {**value, "findings": kept}
                displayed += len(kept)
                continue

        if isinstance(value, list):
            kept = _project_rows(value, key, threshold, effective_cap, omitted)
            projected[key] = kept
            if key not in UNFILTERED_SECTIONS:
                displayed += len(kept)
            continue

        projected[key] = value

    projected["displayed_issues"] = displayed
    projected["section_omitted"] = omitted
    return projected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_health_projection_caps.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/health_projection.py science/tests/test_health_projection_caps.py
git commit -m "feat(health): add per-section row caps and displayed_issues"
```

---

### Task 9: Wire `health` to `--severity`, `--output`, and the sink

**Files:**
- Modify: `science/src/science_tool/graph/health_cli.py:14-56` (options and signature),
  `:155-165` (clean-report gate), `:436` (the `emit` call)
- Test: `science/tests/test_health_cli_budget.py`

**Interfaces:**
- Consumes: `project_health_report` (Task 8), `BoundedSink` (Task 3), `lookup` (Task 1).
- Produces: `science health --severity {error,warn,all}` (default `warn`) and
  `science health --output PATH`.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_health_cli_budget.py
from __future__ import annotations

from click.testing import CliRunner

from science_tool.cli import main


def test_severity_option_exists_and_defaults_to_warn() -> None:
    result = CliRunner().invoke(main, ["health", "--help"])
    assert result.exit_code == 0, result.output
    assert "--severity" in result.output
    assert "warn" in result.output


def test_output_option_exists() -> None:
    result = CliRunner().invoke(main, ["health", "--help"])
    assert result.exit_code == 0, result.output
    assert "--output" in result.output


def test_filtered_report_never_claims_clean(monkeypatch) -> None:
    """total_issues > 0 with everything filtered out must NOT print the clean message."""
    from science_tool.graph import health_cli

    report = {
        "validation": [{"severity": "warning", "message": f"m{i}"} for i in range(50)],
        "unwired_checks": [],
        "total_issues": 50,
        "layered_claims": {},
        "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
    }
    monkeypatch.setattr(health_cli, "build_health_report", lambda *_a, **_k: report)

    result = CliRunner().invoke(main, ["health", "--severity", "error"])
    assert "Project is clean" not in result.output
    assert "50" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_health_cli_budget.py -v`
Expected: FAIL — `--severity` is not in the help output.

- [ ] **Step 3: Add the options**

In `science/src/science_tool/graph/health_cli.py`, add to `health_command`:

```python
@click.option(
    "--severity",
    "severity",
    type=click.Choice(["error", "warn", "all"]),
    default="warn",
    show_default=True,
    help="Minimum severity to display. A threshold, not an equality filter: "
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

Add `severity: str` and `output_path: Path | None` to the signature.

- [ ] **Step 4: Project, then emit through the sink**

Replace line 436 and guard the clean-report gate. After `report` is built:

```python
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.graph.health_projection import project_health_report

    displayed = project_health_report(report, threshold=severity)
    sink = BoundedSink(lookup("health"), output_path=output_path, command_path="health")
    payload = report if output_path is not None else displayed
    try:
        emit(output_format=output_format, payload=payload, render_text=_render_report, sink=sink)
    finally:
        sink.close()
    if output_path is not None:
        click.echo(f"wrote the complete health report to {output_path}")
```

`_render_report` reads from `displayed`, not `report`, and its clean-report gate keys off the
untouched `report["total_issues"]`:

```python
        total_issues = report["total_issues"]
        if total_issues == 0:
            # ... unchanged clean-report branch ...
            return

        omitted = displayed.get("section_omitted") or {}
        if omitted:
            hidden = sum(omitted.values())
            click.echo(
                f"showing {displayed['displayed_issues']} of {total_issues} issues "
                f"(severity: {severity}, cap: {SECTION_ROW_CAP}/section)"
            )
            click.echo(f"  {hidden} hidden — science health --severity all --output health.json")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_health_cli_budget.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the health suite for regressions**

Run: `cd science && uv run --frozen pytest -k health -v`
Expected: PASS. Tests asserting the old unfiltered table must be updated to pass
`--severity all`.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/health_cli.py science/tests/test_health_cli_budget.py
git commit -m "feat(health): add --severity threshold and complete --output sink"
```

---

### Task 10: Bulk dumps refuse stdout past budget

**Files:**
- Modify: `science/src/science_tool/entities_inventory_cli.py:50-61`
- Modify: `science/src/science_tool/data_cli.py:49-90`
- Test: `science/tests/test_bulk_dump_refusal.py`

**Interfaces:**
- Consumes: `lookup` (Task 1), `visible_len` (Task 2).
- Produces: no new symbols. Both commands exit non-zero when the stdout payload would exceed
  budget and no `--output` was given.

**A versioned document is refused, never truncated.** `entities inventory` emits a pinned
`schema_version: "2"` contract; a partial document under that contract would be a lie about the
contract.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_bulk_dump_refusal.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from science_tool.budget.registry import lookup
from science_tool.entities_inventory_cli import guard_stdout_payload


def test_small_payload_passes_the_guard() -> None:
    guard_stdout_payload("{}", command_path="entities inventory", output_path=None)


def test_oversized_payload_is_refused_not_truncated() -> None:
    budget = lookup("entities inventory")
    assert budget is not None
    payload = "x" * (budget.max_chars + 1)
    with pytest.raises(Exception) as excinfo:
        guard_stdout_payload(payload, command_path="entities inventory", output_path=None)
    message = str(excinfo.value)
    assert "--output" in message
    assert "entities inventory" in message


def test_output_path_bypasses_the_guard_entirely(tmp_path: Path) -> None:
    budget = lookup("entities inventory")
    assert budget is not None
    payload = "x" * (budget.max_chars + 1)
    guard_stdout_payload(payload, command_path="entities inventory", output_path=tmp_path / "o.json")


def test_refusal_message_never_contains_partial_json() -> None:
    budget = lookup("entities inventory")
    assert budget is not None
    document = json.dumps({"schema_version": "2", "entities": ["e"] * 50_000})
    assert len(document) > budget.max_chars
    with pytest.raises(Exception) as excinfo:
        guard_stdout_payload(document, command_path="entities inventory", output_path=None)
    assert "schema_version" not in str(excinfo.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_bulk_dump_refusal.py -v`
Expected: FAIL — `ImportError: cannot import name 'guard_stdout_payload'`

- [ ] **Step 3: Write the guard and apply it**

Add to `science/src/science_tool/entities_inventory_cli.py`:

```python
def guard_stdout_payload(rendered: str, *, command_path: str, output_path: Path | None) -> None:
    """Refuse to print an oversized payload to stdout.

    Refusal rather than truncation: this payload is a versioned document, and emitting a
    partial one under its ``schema_version`` contract would misrepresent the contract.
    The message deliberately does not echo any of the payload.
    """
    if output_path is not None:
        return
    budget = lookup(command_path)
    if budget is None:
        return
    size = visible_len(rendered)
    if size > budget.max_chars:
        raise click.ClickException(
            f"{command_path} would write {size} chars to stdout, over its "
            f"{budget.max_chars} ceiling. Rerun with --output PATH to write the complete "
            f"payload to a file."
        )
```

Add imports:

```python
import click

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import lookup
```

Then in `entities_inventory_command`, insert the guard before echoing:

```python
    inventory = build_inventory(project_path)
    rendered = inventory.model_dump_json(indent=2) + "\n"
    guard_stdout_payload(rendered, command_path="entities inventory", output_path=output)
    if output is None:
        click.echo(rendered, nl=False)
    else:
        output.write_text(rendered, encoding="utf-8")
        click.echo(f"wrote the entity inventory to {output}")
```

- [ ] **Step 4: Apply the same guard to `data audit`**

`data audit` has no `--output` today. Add one, then guard. In
`science/src/science_tool/data_cli.py`:

```python
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete report to PATH instead of stdout.",
)
```

Add `output_path: Path | None` to `data_audit_command`, then wrap each JSON echo:

```python
    from science_tool.entities_inventory_cli import guard_stdout_payload

    if emit_json:
        rendered = render_json(violations, outcomes, notes)
        guard_stdout_payload(rendered, command_path="data audit", output_path=output_path)
        if output_path is None:
            click.echo(rendered, nl=False)
        else:
            output_path.write_text(rendered, encoding="utf-8")
            click.echo(f"wrote the data audit report to {output_path}")
        return
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_bulk_dump_refusal.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Run the affected suites**

Run: `cd science && uv run --frozen pytest -k "inventory or data_audit or data_cli" -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/entities_inventory_cli.py science/src/science_tool/data_cli.py science/tests/test_bulk_dump_refusal.py
git commit -m "feat(budget): refuse oversized bulk dumps on stdout, require --output"
```

---

### Task 11: Guards

**Files:**
- Create: `science/tests/test_budget_boundary.py`

**Interfaces:**
- Consumes: `BUDGETS`, `EXEMPTIONS` (Task 1); the Click tree at `science_tool.cli:main`.
- Produces: no runtime symbols — tests only.

Three guards. Scope is **derived**, not hand-listed: the classification guard walks the Click
tree and the emitter-import set comes from the AST, so a new command cannot silently escape.
The known limit is stated in the module docstring the way `test_output_boundary.py` and
`test_cli_is_registration_only.py` state theirs.

- [ ] **Step 1: Write the guard tests**

```python
# science/tests/test_budget_boundary.py
"""Context-budget boundary guards (slice 1).

Three ratchets:

1. **Classification.** Every leaf Click command whose module imports an emitter must be
   either budgeted or explicitly exempt with a reason. Scope is derived by walking the
   Click tree and reading imports from the AST, so a NEW emitting command fails until
   somebody classifies it.
2. **Sink routing.** Every budgeted command's module must reference ``BoundedSink``.
3. **Registry hygiene.** Budgets and exemptions stay disjoint and non-empty.

Known gap, stated rather than hidden: guard 1 keys on the *module* importing an emitter,
not on the individual command callback. A non-emitting command sharing a module with an
emitting one is therefore swept in and must be exempted explicitly. That is deliberate --
the failure direction is "asks for a decision you did not need" rather than "silently
lets an unbounded command through". Guard 2 likewise proves a reference, not that every
code path uses it; the budget regression test in
``tests/test_budget_regression.py`` is what checks actual sizes.
"""

from __future__ import annotations

import ast
from pathlib import Path

import click

from science_tool.budget.registry import BUDGETS, EXEMPTIONS
from science_tool.cli import main

_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_EMITTERS = {"emit", "emit_query_rows"}


def _leaf_commands(cmd: click.Command, path: list[str]) -> list[tuple[str, click.Command]]:
    if isinstance(cmd, click.Group):
        found: list[tuple[str, click.Command]] = []
        for name, sub in sorted(cmd.commands.items()):
            found.extend(_leaf_commands(sub, [*path, name]))
        return found
    return [(" ".join(path), cmd)]


def _module_path_for(cmd: click.Command) -> Path | None:
    callback = cmd.callback
    if callback is None:
        return None
    module = getattr(callback, "__module__", "")
    if not module.startswith("science_tool"):
        return None
    relative = Path(*module.split(".")[1:])
    for candidate in (_SRC / relative.with_suffix(".py"), _SRC / relative / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _imports_an_emitter(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(alias.name in _EMITTERS for alias in node.names):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _EMITTERS:
            return True
    return False


def test_every_emitting_command_is_budgeted_or_exempt() -> None:
    unclassified: list[str] = []
    for command_path, cmd in _leaf_commands(main, []):
        module = _module_path_for(cmd)
        if module is None or not _imports_an_emitter(module):
            continue
        if command_path in BUDGETS or command_path in EXEMPTIONS:
            continue
        unclassified.append(command_path)
    assert not unclassified, (
        "These commands emit output but carry neither a budget nor an exemption:\n  "
        + "\n  ".join(sorted(unclassified))
        + "\nAdd a CommandBudget to BUDGETS, or an EXEMPTIONS entry stating why it cannot grow."
    )


def test_every_budgeted_command_module_references_the_sink() -> None:
    missing: list[str] = []
    by_path = dict(_leaf_commands(main, []))
    for command_path in BUDGETS:
        cmd = by_path.get(command_path)
        if cmd is None:
            missing.append(f"{command_path} (not in the CLI tree)")
            continue
        module = _module_path_for(cmd)
        if module is None or "BoundedSink" not in module.read_text(encoding="utf-8"):
            missing.append(command_path)
    assert not missing, "Budgeted commands whose module never references BoundedSink:\n  " + "\n  ".join(missing)


def test_registry_entries_are_disjoint_and_reasoned() -> None:
    assert not (set(BUDGETS) & set(EXEMPTIONS))
    for path, reason in EXEMPTIONS.items():
        assert reason.strip(), f"{path} is exempt with no reason"
```

- [ ] **Step 2: Run the guards to see what they surface**

Run: `cd science && uv run --frozen pytest tests/test_budget_boundary.py -v`
Expected: `test_every_emitting_command_is_budgeted_or_exempt` FAILS, listing every emitting
command not yet classified. This list is the work item, not a bug.

- [ ] **Step 3: Classify everything the guard surfaced**

For each command in the failure output, add either a `CommandBudget` to `BUDGETS` or an
`EXEMPTIONS` entry. Use this exact reason format for commands measured in the audit:

```python
    "graph stats": "measured 341 chars on 2026-07-24; fixed-shape summary",
```

For commands not measured, measure before classifying:

```bash
cd ~/d/natural-systems && uv run --frozen science <command> 2>/dev/null | wc -m
```

Do not guess. An exemption asserting a command is small is a claim, and the reason string is
where that claim is recorded.

- [ ] **Step 4: Run the guards to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_budget_boundary.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write the budget regression test**

```python
# science/tests/test_budget_regression.py
"""Actual rendered sizes for budgeted commands, against a fixture project.

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
- related: [question:q{i:04d}-some-long-question-slug, hypothesis:h{i:04d}-another-long-slug]
- created: 2026-01-01

Body paragraph for task {i}, long enough to matter when multiplied by the backlog size.
"""
    for i in range(400)
)


@pytest.fixture
def fixture_project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text(TASKS)
    return tmp_path


def test_tasks_list_stays_within_budget(fixture_project: Path, monkeypatch) -> None:
    monkeypatch.chdir(fixture_project)
    budget = BUDGETS["tasks list"]
    for args in (["tasks", "list"], ["tasks", "list", "--status", "proposed"]):
        result = CliRunner().invoke(main, args)
        assert result.exit_code == 0, result.output
        assert visible_len(result.output) <= budget.max_chars, f"{args} exceeded its ceiling"


def test_tasks_list_json_stays_within_budget(fixture_project: Path, monkeypatch) -> None:
    monkeypatch.chdir(fixture_project)
    result = CliRunner().invoke(main, ["tasks", "list", "--status", "proposed", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert visible_len(result.output) <= BUDGETS["tasks list"].max_chars
    payload = json.loads(result.output)
    assert payload["truncation"]["total"] == 395


def test_output_file_escapes_the_budget_entirely(fixture_project: Path, monkeypatch) -> None:
    monkeypatch.chdir(fixture_project)
    target = fixture_project / "all.json"
    result = CliRunner().invoke(
        main,
        ["tasks", "list", "--status", "proposed", "--format", "json", "--output", str(target)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())
    assert len(payload["rows"]) == 395
    assert visible_len(target.read_text()) > BUDGETS["tasks list"].max_chars
```

- [ ] **Step 6: Run the regression test**

Run: `cd science && uv run --frozen pytest tests/test_budget_regression.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run the whole suite, lint, and types**

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
```

Expected: `tasks list` well under 20,000 (was 144,655); `health` well under 30,000
(was 426,926). The overlay flag runs the uncommitted toolkit without touching that project's
pinned dependency.

- [ ] **Step 9: Commit**

```bash
git add science/tests/test_budget_boundary.py science/tests/test_budget_regression.py science/src/science_tool/budget/registry.py
git commit -m "test(budget): add classification, sink-routing, and size regression guards"
```

---

## Self-Review

**Spec coverage.** Every slice-1 element in the parent design maps to a task: the core invariant
(Tasks 3, 6, 9, 10), projection/sink split (3, 4, 5, 8), the registry SSOT (1), command-total
ceiling (3, tested explicitly), per-shape projections (4 rows, 8 health, 10 refusal), truncation
visible in every format (5, 9), counting semantics (2), uniform `--output` (6, 9, 10),
working-set defaults (6), the health classification correction (7), severity as a threshold
defaulting to `warn` (7, 8), row caps as the real budget mechanism (8), `total_issues`
invariance (8, 9), `unwired_checks` never filtered (7, 8), and all three guards (11).

**Deliberately deferred to slice 1 follow-up:** the eight remaining budgeted commands
(`entity list`, `questions list`, `interpretations list`, `discussions list`, `feedback list`,
`entity needs-review`, `curate consolidation-candidates`, `prose lint`, `validate`,
`curate inventory`) get their ceilings enforced automatically once Task 5 lands, because they
already route through `emit_query_rows` — but none has `--output` yet, so an oversized run will
raise rather than offer the escape. Task 11 Step 3 surfaces them; adding `--output` to each is
mechanical and follows the Task 6 pattern exactly.

**Type consistency.** `CommandBudget(max_chars, max_rows)` is used with those names in Tasks 1,
3, 5, 11. `BoundedSink(budget, *, output_path, command_path)` is constructed identically in
Tasks 3, 6, 9. `project_rows` returns `ProjectedRows` with `.rows/.omitted/.total/.truncated`,
consumed in Task 5. `meets_threshold(row, threshold)` (Task 7) is called by `_project_rows`
(Task 8). `guard_stdout_payload(rendered, *, command_path, output_path)` is defined and reused
in Task 10. `visible_len` and `render_to_text` (Task 2) are used in Tasks 3, 5, 6, 10, 11.

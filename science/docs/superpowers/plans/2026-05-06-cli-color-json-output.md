# CLI Color and JSON Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global Science CLI color policy, centralize terminal styles, and align high-value JSON spellings without changing default agent-safe output.

**Architecture:** Add `science_tool.styles` as the single terminal styling boundary, wire the root Click command to store the effective color policy in context, then migrate current Rich call sites to the shared console and style helpers. Keep JSON behavior stable, add `--format json` aliases to DAG read/report commands, and update agent command docs to prefer canonical JSON spelling.

**Tech Stack:** Python 3.13, Click, Rich, pytest, uv.

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `science/src/science_tool/styles.py` | Create | Color policy resolution, Rich console construction, semantic style maps, typed-reference rendering |
| `science/src/science_tool/cli.py` | Modify | Root `--color` option, health command console migration |
| `science/src/science_tool/tasks_display.py` | Modify | Use shared styles for task table status, priority, type, dates, related refs, and console |
| `science/src/science_tool/output.py` | Modify | Use shared console helper for generic Rich tables |
| `science/src/science_tool/verdict/cli.py` | Modify | Use shared console helper for rollup table output |
| `science/src/science_tool/dag/cli.py` | Modify | Add canonical `--format json` spelling while preserving existing `--json` |
| `science/tests/test_cli_styles.py` | Create | Unit tests for policy resolution, console policy, and entity-reference style helpers |
| `science/tests/test_cli_color_policy.py` | Create | End-to-end root CLI color behavior tests |
| `science/tests/dag/test_cli.py` | Modify | DAG `--format json` alias coverage |
| `commands/dag-audit.md` | Modify | Prefer `--format json` in agent-facing DAG audit docs |
| `commands/curate.md` | Modify | Prefer `--format json` in agent-facing curate docs |
| `science/docs/superpowers/specs/2026-05-06-cli-color-json-output-design.md` | Read | Source design and acceptance criteria |

## Task 1: Style Policy Unit Tests

**Files:**
- Create: `science/tests/test_cli_styles.py`

- [ ] **Step 1: Write failing tests for policy resolution and reference rendering.**

Create `science/tests/test_cli_styles.py` with this content:

```python
from __future__ import annotations

import io

import click
import pytest
from rich.text import Text

from science_tool.styles import (
    ColorPolicy,
    get_console,
    render_entity_ref,
    resolve_color_policy,
    set_color_policy,
)


def test_resolve_color_policy_explicit_wins_over_environment() -> None:
    env = {"NO_COLOR": "1", "FORCE_COLOR": "1"}

    assert resolve_color_policy("auto", env=env) == ColorPolicy.AUTO
    assert resolve_color_policy("always", env=env) == ColorPolicy.ALWAYS
    assert resolve_color_policy("never", env=env) == ColorPolicy.NEVER


def test_resolve_color_policy_honors_no_color_before_force_color() -> None:
    env = {"NO_COLOR": "1", "FORCE_COLOR": "1"}

    assert resolve_color_policy(None, env=env) == ColorPolicy.NEVER


def test_resolve_color_policy_honors_force_color_without_no_color() -> None:
    assert resolve_color_policy(None, env={"FORCE_COLOR": "1"}) == ColorPolicy.ALWAYS
    assert resolve_color_policy(None, env={"FORCE_COLOR": "true"}) == ColorPolicy.ALWAYS
    assert resolve_color_policy(None, env={"FORCE_COLOR": "0"}) == ColorPolicy.NEVER


def test_resolve_color_policy_defaults_to_never() -> None:
    assert resolve_color_policy(None, env={}) == ColorPolicy.NEVER


def test_resolve_color_policy_rejects_invalid_explicit_value() -> None:
    with pytest.raises(ValueError, match="invalid color policy"):
        resolve_color_policy("sometimes", env={})


def test_get_console_caches_for_click_context() -> None:
    with click.Context(click.Command("demo")) as ctx:
        set_color_policy(ctx, ColorPolicy.NEVER)

        first = get_console(context=ctx)
        second = get_console(context=ctx)

    assert first is second


def test_get_console_non_cached_for_explicit_file() -> None:
    with click.Context(click.Command("demo")) as ctx:
        set_color_policy(ctx, ColorPolicy.NEVER)
        left = io.StringIO()
        right = io.StringIO()

        first = get_console(context=ctx, file=left)
        second = get_console(context=ctx, file=right)

    assert first is not second


def test_render_entity_ref_styles_known_kind() -> None:
    rendered = render_entity_ref("question:q104-rigor-conditional-claims")

    assert isinstance(rendered, Text)
    assert rendered.plain == "question:q104-rigor-conditional-claims"
    assert rendered.spans


def test_render_entity_ref_handles_unknown_kind() -> None:
    rendered = render_entity_ref("custom-kind:local-part")

    assert rendered.plain == "custom-kind:local-part"
    assert rendered.spans


def test_render_entity_ref_without_kind_is_plain_text() -> None:
    rendered = render_entity_ref("plain-token")

    assert rendered.plain == "plain-token"
```

- [ ] **Step 2: Run tests to verify they fail because `science_tool.styles` does not exist.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_styles.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'science_tool.styles'`.

## Task 2: Implement `science_tool.styles`

**Files:**
- Create: `science/src/science_tool/styles.py`
- Test: `science/tests/test_cli_styles.py`

- [ ] **Step 1: Create the style module.**

Create `science/src/science_tool/styles.py` with this content:

```python
from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

import click
from rich.console import Console
from rich.style import Style
from rich.text import Text

COLOR_POLICY_CHOICES: tuple[str, ...] = ("never", "auto", "always")
_POLICY_KEY = "science_color_policy"
_CONSOLE_KEY = "science_rich_console"


class ColorPolicy(StrEnum):
    NEVER = "never"
    AUTO = "auto"
    ALWAYS = "always"


TASK_STATUS_STYLES: dict[str, str] = {
    "active": "bold green",
    "blocked": "bold red",
    "proposed": "yellow",
    "deferred": "dim",
    "done": "blue",
    "retired": "dim strike",
}

TASK_TYPE_STYLES: dict[str, str] = {
    "dev": "cyan",
    "research": "magenta",
    "analysis": "blue",
    "writing": "green",
}

TASK_PRIORITY_STYLES: dict[str, str] = {
    "P0": "bold red",
    "P1": "red",
    "P2": "yellow",
    "P3": "dim",
}

ENTITY_KIND_STYLES: dict[str, tuple[str, str]] = {
    "task": ("bold cyan", "cyan"),
    "question": ("bold magenta", "magenta"),
    "hypothesis": ("bold green", "green"),
    "discussion": ("bold yellow", "yellow"),
    "interpretation": ("bold blue", "blue"),
    "plan": ("bold bright_blue", "bright_blue"),
    "concept": ("bold bright_magenta", "bright_magenta"),
    "report": ("bold bright_green", "bright_green"),
    "spec": ("bold bright_yellow", "bright_yellow"),
    "topic": ("bold white", "white"),
    "meta": ("bold dim", "dim"),
    "proposition": ("bold green", "green"),
    "observation": ("bold bright_green", "bright_green"),
    "finding": ("bold bright_green", "bright_green"),
    "story": ("bold bright_magenta", "bright_magenta"),
    "theme": ("bold bright_blue", "bright_blue"),
    "mechanism": ("bold bright_red", "bright_red"),
    "dataset": ("bold cyan", "cyan"),
    "paper": ("bold bright_cyan", "bright_cyan"),
    "workflow": ("bold bright_blue", "bright_blue"),
    "workflow-run": ("bold blue", "blue"),
}

MUTED_STYLE = "dim"
WARNING_STYLE = "yellow"
ERROR_STYLE = "bold red"
SUCCESS_STYLE = "green"


def resolve_color_policy(
    explicit: str | ColorPolicy | None,
    *,
    env: Mapping[str, str] | None = None,
) -> ColorPolicy:
    if isinstance(explicit, ColorPolicy):
        return explicit
    if explicit is not None:
        try:
            return ColorPolicy(explicit)
        except ValueError as exc:
            raise ValueError(f"invalid color policy: {explicit}") from exc

    values = os.environ if env is None else env
    if values.get("NO_COLOR"):
        return ColorPolicy.NEVER

    force_color = values.get("FORCE_COLOR")
    if force_color is not None and force_color != "" and force_color != "0":
        return ColorPolicy.ALWAYS

    return ColorPolicy.NEVER


def set_color_policy(context: click.Context, policy: ColorPolicy) -> None:
    context.ensure_object(dict)
    context.obj[_POLICY_KEY] = policy
    context.obj.pop(_CONSOLE_KEY, None)


def get_color_policy(context: click.Context | None = None) -> ColorPolicy:
    current = context or click.get_current_context(silent=True)
    while current is not None:
        if isinstance(current.obj, dict) and _POLICY_KEY in current.obj:
            return current.obj[_POLICY_KEY]
        current = current.parent
    return resolve_color_policy(None)


def get_console(
    *,
    context: click.Context | None = None,
    file: Any | None = None,
) -> Console:
    current = context or click.get_current_context(silent=True)
    policy = get_color_policy(current)
    if file is not None:
        return _build_console(policy=policy, file=file)

    cache_context = _nearest_context_with_policy(current) or current
    if cache_context is None:
        return _build_console(policy=policy, file=click.get_text_stream("stdout"))

    cache_context.ensure_object(dict)
    cached = cache_context.obj.get(_CONSOLE_KEY)
    if isinstance(cached, Console):
        return cached

    console = _build_console(policy=policy, file=click.get_text_stream("stdout"))
    cache_context.obj[_CONSOLE_KEY] = console
    return console


def _nearest_context_with_policy(context: click.Context | None) -> click.Context | None:
    current = context
    while current is not None:
        if isinstance(current.obj, dict) and _POLICY_KEY in current.obj:
            return current
        current = current.parent
    return None


def _build_console(*, policy: ColorPolicy, file: Any) -> Console:
    if policy == ColorPolicy.NEVER:
        return Console(file=file, force_terminal=False, color_system=None)
    if policy == ColorPolicy.ALWAYS:
        return Console(file=file, force_terminal=True, color_system="auto")
    return Console(file=file, force_terminal=None, color_system="auto")


def age_style(created: object) -> Style:
    from datetime import date

    if not isinstance(created, date):
        return Style.parse(MUTED_STYLE)

    days = (date.today() - created).days
    t = min(max(days, 0), 90) / 90.0
    if t < 0.5:
        s = t * 2
        r = int(60 + 140 * s)
        g = 180
        b = int(60 - 60 * s)
    else:
        s = (t - 0.5) * 2
        r = 200
        g = int(180 - 120 * s)
        b = 0
    return Style(color=f"#{r:02x}{g:02x}{b:02x}")


def entity_kind_styles(kind: str) -> tuple[str, str]:
    return ENTITY_KIND_STYLES.get(kind, ("bold dim", "dim"))


def render_entity_ref(ref: str) -> Text:
    if ":" not in ref:
        return Text(ref)

    kind, local_part = ref.split(":", 1)
    prefix_style, local_style = entity_kind_styles(kind)
    text = Text()
    text.append(kind, style=prefix_style)
    text.append(":", style=MUTED_STYLE)
    text.append(local_part, style=local_style)
    return text
```

- [ ] **Step 2: Run style tests to verify they pass.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_styles.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit style module and unit tests.**

Run from repository root:

```bash
git add science/src/science_tool/styles.py science/tests/test_cli_styles.py
git commit -m "feat: add CLI color style policy"
```

Expected: commit succeeds and includes only `styles.py` plus `test_cli_styles.py`.

## Task 3: Root Color Option and Task Table Behavior

**Files:**
- Create: `science/tests/test_cli_color_policy.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/src/science_tool/tasks_display.py`
- Test: `science/tests/test_cli_color_policy.py`

- [ ] **Step 1: Write failing CLI color policy tests.**

Create `science/tests/test_cli_color_policy.py` with this content:

```python
from __future__ import annotations

import json
import re
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _write_active_tasks() -> None:
    tasks_dir = Path("tasks")
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text(
        "## [t001] Color task\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- related: [question:q001-demo, custom-kind:alpha]\n"
        "- created: 2026-05-01\n\n"
        "Description.\n"
    )


def test_root_color_rejects_invalid_policy() -> None:
    result = CliRunner().invoke(main, ["--color", "sometimes", "tasks", "list"])

    assert result.exit_code != 0
    assert "Invalid value for '--color'" in result.output


def test_tasks_list_default_has_no_ansi() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["tasks", "list"])

    assert result.exit_code == 0, result.output
    assert "Color task" in result.output
    assert ANSI_RE.search(result.output) is None


def test_tasks_list_auto_has_no_ansi_under_clirunner() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["--color", "auto", "tasks", "list"])

    assert result.exit_code == 0, result.output
    assert "Color task" in result.output
    assert ANSI_RE.search(result.output) is None


def test_tasks_list_always_emits_ansi() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["--color", "always", "tasks", "list"])

    assert result.exit_code == 0, result.output
    assert "Color task" in result.output
    assert ANSI_RE.search(result.output) is not None


def test_tasks_list_json_has_no_ansi_even_when_color_forced() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["--color", "always", "tasks", "list", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is None
    payload = json.loads(result.output)
    assert payload["rows"][0]["title"] == "Color task"
```

- [ ] **Step 2: Run CLI color tests to verify they fail.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_color_policy.py -q
```

Expected: FAIL because the root command does not accept `--color`.

- [ ] **Step 3: Wire the root Click option.**

In `science/src/science_tool/cli.py`, add this import near the existing `science_tool.output` import:

```python
from science_tool.styles import COLOR_POLICY_CHOICES, resolve_color_policy, set_color_policy
```

Replace the root command definition:

```python
@click.group()
def main() -> None:
    """Science CLI tools."""
```

with:

```python
@click.group()
@click.option(
    "--color",
    "color_policy",
    type=click.Choice(COLOR_POLICY_CHOICES),
    default=None,
    help="Terminal color policy. Defaults to never unless FORCE_COLOR is set.",
)
@click.pass_context
def main(ctx: click.Context, color_policy: str | None) -> None:
    """Science CLI tools."""
    set_color_policy(ctx, resolve_color_policy(color_policy))
```

- [ ] **Step 4: Migrate `tasks_display.py` to shared styles.**

In `science/src/science_tool/tasks_display.py`, replace the imports and local style maps.

Remove:

```python
from datetime import date

from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text
```

Add:

```python
from rich.table import Table
from rich.text import Text
from science_tool.styles import (
    TASK_PRIORITY_STYLES,
    TASK_STATUS_STYLES,
    TASK_TYPE_STYLES,
    age_style,
    get_console,
    render_entity_ref,
)
```

Delete `_STATUS_STYLE`, `_TYPE_STYLE`, `_PRIORITY_STYLE`, and `_age_style`.

Add this helper above `render_tasks_table`:

```python
def _render_related_refs(refs: list[str]) -> Text:
    text = Text()
    for index, ref in enumerate(refs):
        if index:
            text.append(", ", style="dim")
        text.append_text(render_entity_ref(ref))
    return text
```

In `render_tasks_table`, replace the styled cells:

```python
type_text = Text(t.type, style=_TYPE_STYLE.get(t.type, ""))
pri_text = Text(t.priority, style=_PRIORITY_STYLE.get(t.priority, ""))
status_text = Text(t.status, style=_STATUS_STYLE.get(t.status, ""))
created_text = Text(t.created.isoformat(), style=_age_style(t.created))
```

with:

```python
type_text = Text(t.type, style=TASK_TYPE_STYLES.get(t.type, ""))
pri_text = Text(t.priority, style=TASK_PRIORITY_STYLES.get(t.priority, ""))
status_text = Text(t.status, style=TASK_STATUS_STYLES.get(t.status, ""))
created_text = Text(t.created.isoformat(), style=age_style(t.created))
```

Replace:

```python
row.append(Text(", ".join(t.related), style="dim"))
```

with:

```python
row.append(_render_related_refs(t.related))
```

Replace:

```python
console = Console()
```

with:

```python
console = get_console()
```

- [ ] **Step 5: Run targeted CLI color tests.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_color_policy.py tests/test_tasks_cli.py::TestTasksList::test_list_json_format -q
```

Expected: PASS.

- [ ] **Step 6: Commit root color option and task table migration.**

Run from repository root:

```bash
git add science/src/science_tool/cli.py science/src/science_tool/tasks_display.py science/tests/test_cli_color_policy.py
git commit -m "feat: add root CLI color policy"
```

Expected: commit succeeds and includes only the root CLI, task display, and CLI color tests.

## Task 4: Shared Console for Generic Table Renderers

**Files:**
- Modify: `science/src/science_tool/output.py`
- Modify: `science/src/science_tool/verdict/cli.py`
- Test: `science/tests/test_cli_color_policy.py`

- [ ] **Step 1: Add a direct generic table no-ANSI test.**

Append this test to `science/tests/test_cli_color_policy.py`:

```python
def test_emit_query_rows_default_has_no_ansi(capsys) -> None:
    from science_tool.output import emit_query_rows

    emit_query_rows(
        output_format="table",
        title="Rows",
        columns=[("id", "ID"), ("title", "Title")],
        rows=[{"id": "question:q001-demo", "title": "Demo"}],
    )

    captured = capsys.readouterr()
    assert "question:q001-demo" in captured.out
    assert ANSI_RE.search(captured.out) is None
```

- [ ] **Step 2: Run the new test.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_color_policy.py::test_emit_query_rows_default_has_no_ansi -q
```

Expected: PASS before implementation because the current helper already disables color. This test freezes the behavior before refactoring.

- [ ] **Step 3: Migrate `output.py` to shared console construction.**

In `science/src/science_tool/output.py`, add:

```python
from science_tool.styles import get_console
```

Replace:

```python
console = Console(file=click.get_text_stream("stdout"), force_terminal=False, color_system=None)
```

with:

```python
console = get_console(file=click.get_text_stream("stdout"))
```

Remove the now-unused `from rich.console import Console` import.

- [ ] **Step 4: Migrate verdict rollup table output.**

In `science/src/science_tool/verdict/cli.py`, add:

```python
from science_tool.styles import get_console
```

Remove:

```python
from rich.console import Console
```

Replace:

```python
console = Console(file=click.get_text_stream("stdout"), force_terminal=False, color_system=None)
```

with:

```python
console = get_console(file=click.get_text_stream("stdout"))
```

- [ ] **Step 5: Run generic output and verdict CLI tests.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_color_policy.py::test_emit_query_rows_default_has_no_ansi tests/test_verdict_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit generic table renderer migration.**

Run from repository root:

```bash
git add science/src/science_tool/output.py science/src/science_tool/verdict/cli.py science/tests/test_cli_color_policy.py
git commit -m "refactor: route rich tables through CLI style policy"
```

Expected: commit succeeds and includes only generic output, verdict CLI, and the added test.

## Task 5: Health Command Console Policy

**Files:**
- Modify: `science/tests/test_cli_color_policy.py`
- Modify: `science/src/science_tool/cli.py`

- [ ] **Step 1: Add health command color-policy tests.**

Append these helpers and tests to `science/tests/test_cli_color_policy.py`:

```python
def _health_report_with_archive_lag() -> dict:
    return {
        "archive_lag": {
            "done_in_active": 1,
            "retired_in_active": 0,
            "missing_completed": 0,
        },
        "managed_artifacts": [],
        "tooling_scaffold": [],
        "unregistered_ref_kinds": [],
        "unresolved_refs": [],
        "lingering_tags_lines": [],
        "identity_policy": [],
        "legacy_structured_literature_prefixes": [],
        "dataset_anomalies": [],
        "layered_claims": {
            "migration_issues": [],
            "rival_model_packets_missing_discriminating_predictions": [],
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
        },
    }


def test_health_never_strips_markup_and_ansi(monkeypatch) -> None:
    from science_tool.graph import health as health_module

    monkeypatch.setattr(health_module, "build_health_report", lambda _root: _health_report_with_archive_lag())

    result = CliRunner().invoke(main, ["--color", "never", "health"])

    assert result.exit_code == 0, result.output
    assert "Next:" in result.output
    assert "science tasks archive" in result.output
    assert "[cyan]" not in result.output
    assert ANSI_RE.search(result.output) is None


def test_health_always_emits_ansi(monkeypatch) -> None:
    from science_tool.graph import health as health_module

    monkeypatch.setattr(health_module, "build_health_report", lambda _root: _health_report_with_archive_lag())

    result = CliRunner().invoke(main, ["--color", "always", "health"])

    assert result.exit_code == 0, result.output
    assert "science tasks archive" in result.output
    assert ANSI_RE.search(result.output) is not None
```

- [ ] **Step 2: Run health tests to verify `--color=always` fails.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_color_policy.py::test_health_never_strips_markup_and_ansi tests/test_cli_color_policy.py::test_health_always_emits_ansi -q
```

Expected: `test_health_never_strips_markup_and_ansi` passes and `test_health_always_emits_ansi` fails because `health` still constructs `Console()` directly.

- [ ] **Step 3: Migrate health command console construction.**

In `science/src/science_tool/cli.py`, inside `health_command`, remove:

```python
from rich.console import Console
```

Add this import inside `health_command` near the Rich `Table` import:

```python
from science_tool.styles import get_console
```

Replace:

```python
console = Console()
```

with:

```python
console = get_console()
```

- [ ] **Step 4: Run health color-policy tests.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_color_policy.py::test_health_never_strips_markup_and_ansi tests/test_cli_color_policy.py::test_health_always_emits_ansi -q
```

Expected: PASS.

- [ ] **Step 5: Commit health console migration.**

Run from repository root:

```bash
git add science/src/science_tool/cli.py science/tests/test_cli_color_policy.py
git commit -m "refactor: apply color policy to health output"
```

Expected: commit succeeds and includes only `cli.py` plus the color-policy test file.

## Task 6: Environment Behavior End-to-End

**Files:**
- Modify: `science/tests/test_cli_color_policy.py`
- Test: `science/tests/test_cli_color_policy.py`

- [ ] **Step 1: Add end-to-end environment precedence tests.**

Append these tests to `science/tests/test_cli_color_policy.py`:

```python
def test_force_color_enables_color_when_flag_omitted(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["tasks", "list"])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is not None


def test_no_color_beats_force_color_when_flag_omitted(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["tasks", "list"])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is None


def test_explicit_color_beats_no_color(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("NO_COLOR", "1")
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["--color", "always", "tasks", "list"])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is not None
```

- [ ] **Step 2: Run the environment tests.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_color_policy.py::test_force_color_enables_color_when_flag_omitted tests/test_cli_color_policy.py::test_no_color_beats_force_color_when_flag_omitted tests/test_cli_color_policy.py::test_explicit_color_beats_no_color -q
```

Expected: PASS.

- [ ] **Step 3: Commit environment coverage.**

Run from repository root:

```bash
git add science/tests/test_cli_color_policy.py
git commit -m "test: cover CLI color environment precedence"
```

Expected: commit succeeds and includes only the color-policy test file.

## Task 7: DAG JSON Alias Convergence

**Files:**
- Modify: `science/tests/dag/test_cli.py`
- Modify: `science/src/science_tool/dag/cli.py`

- [ ] **Step 1: Add tests for canonical `--format json` on DAG read/report commands.**

Append these tests to `science/tests/dag/test_cli.py`:

```python
def test_dag_validate_accepts_format_json(cli_project: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["dag", "validate", "--project", str(cli_project), "--format", "json"])

    assert result.exit_code in {0, 1}
    payload = json.loads(result.output)
    assert "findings" in payload


def test_dag_staleness_accepts_format_json(cli_project: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["dag", "staleness", "--project", str(cli_project), "--format", "json"])

    assert result.exit_code in {0, 1}
    payload = json.loads(result.output)
    assert "drifted_edges" in payload


def test_dag_audit_accepts_format_json(cli_project: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["dag", "audit", "--project", str(cli_project), "--format", "json"])

    assert result.exit_code in {0, 1}
    payload = json.loads(result.output)
    assert "staleness" in payload
```

- [ ] **Step 2: Run the DAG alias tests to verify they fail.**

Run from `science/`:

```bash
uv run --frozen pytest tests/dag/test_cli.py::test_dag_validate_accepts_format_json tests/dag/test_cli.py::test_dag_staleness_accepts_format_json tests/dag/test_cli.py::test_dag_audit_accepts_format_json -q
```

Expected: FAIL with Click rejecting `--format`.

- [ ] **Step 3: Add a small output-format helper in `dag/cli.py`.**

In `science/src/science_tool/dag/cli.py`, add this helper after `dag_group`:

```python
def _wants_json(*, as_json: bool, output_format: str) -> bool:
    return as_json or output_format == "json"
```

- [ ] **Step 4: Add `--format` to `staleness`, `audit`, and `validate`.**

For `staleness_cmd`, add this Click option after the existing `--json` option:

```python
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
```

Change the function signature from:

```python
def staleness_cmd(ctx: click.Context, recent_days: int, as_json: bool, project_path: Path | None) -> None:
```

to:

```python
def staleness_cmd(
    ctx: click.Context,
    recent_days: int,
    as_json: bool,
    output_format: str,
    project_path: Path | None,
) -> None:
```

Replace:

```python
if as_json:
```

with:

```python
if _wants_json(as_json=as_json, output_format=output_format):
```

For `audit_cmd`, add the same `@click.option("--format", ...)` block after the existing `--json` option.

Change the signature from:

```python
def audit_cmd(
    ctx: click.Context,
    fix: bool,
    strict: bool,
    recent_days: int,
    as_json: bool,
    project_path: Path | None,
) -> None:
```

to:

```python
def audit_cmd(
    ctx: click.Context,
    fix: bool,
    strict: bool,
    recent_days: int,
    as_json: bool,
    output_format: str,
    project_path: Path | None,
) -> None:
```

Replace:

```python
if as_json:
```

with:

```python
if _wants_json(as_json=as_json, output_format=output_format):
```

For `validate_cmd`, add this option after the existing `--json` option:

```python
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
```

Change the signature from:

```python
def validate_cmd(strict: bool, slug: str | None, as_json: bool, project_path: Path | None) -> None:
```

to:

```python
def validate_cmd(
    strict: bool,
    slug: str | None,
    as_json: bool,
    output_format: str,
    project_path: Path | None,
) -> None:
```

Replace:

```python
if as_json:
```

with:

```python
if _wants_json(as_json=as_json, output_format=output_format):
```

- [ ] **Step 5: Run DAG alias tests.**

Run from `science/`:

```bash
uv run --frozen pytest tests/dag/test_cli.py::test_dag_validate_accepts_format_json tests/dag/test_cli.py::test_dag_staleness_accepts_format_json tests/dag/test_cli.py::test_dag_audit_accepts_format_json -q
```

Expected: PASS.

- [ ] **Step 6: Run existing DAG CLI tests.**

Run from `science/`:

```bash
uv run --frozen pytest tests/dag/test_cli.py tests/dag/test_validate_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit DAG JSON alias support.**

Run from repository root:

```bash
git add science/src/science_tool/dag/cli.py science/tests/dag/test_cli.py
git commit -m "feat: add DAG format json aliases"
```

Expected: commit succeeds and includes only DAG CLI and DAG CLI tests.

## Task 8: Agent-Facing Command Docs

**Files:**
- Modify: `commands/dag-audit.md`
- Modify: `commands/curate.md`

- [ ] **Step 1: Update DAG audit docs to use canonical JSON spelling.**

In `commands/dag-audit.md`, replace:

```bash
science dag audit --json
```

with:

```bash
science dag audit --format json
```

- [ ] **Step 2: Update curate docs to use canonical DAG JSON spelling.**

In `commands/curate.md`, replace:

```bash
uv run science dag audit --json
```

with:

```bash
uv run science dag audit --format json
```

- [ ] **Step 3: Verify no agent command doc still recommends `dag audit --json`.**

Run from repository root:

```bash
rg -n "dag audit --json" commands science/docs
```

Expected: no matches.

- [ ] **Step 4: Commit documentation updates.**

Run from repository root:

```bash
git add commands/dag-audit.md commands/curate.md
git commit -m "docs: prefer canonical DAG JSON output"
```

Expected: commit succeeds and includes only the two command docs.

## Task 9: Final Verification

**Files:**
- Read: all files changed by Tasks 1-8

- [ ] **Step 1: Run targeted CLI output tests.**

Run from `science/`:

```bash
uv run --frozen pytest tests/test_cli_styles.py tests/test_cli_color_policy.py tests/test_tasks_cli.py::TestTasksList tests/test_verdict_cli.py tests/dag/test_cli.py tests/dag/test_validate_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint on changed Python files.**

Run from `science/`:

```bash
uv run --frozen ruff check src/science_tool/styles.py src/science_tool/cli.py src/science_tool/tasks_display.py src/science_tool/output.py src/science_tool/verdict/cli.py src/science_tool/dag/cli.py tests/test_cli_styles.py tests/test_cli_color_policy.py tests/dag/test_cli.py
```

Expected: PASS.

- [ ] **Step 3: Run formatting check on changed Python files.**

Run from `science/`:

```bash
uv run --frozen ruff format --check src/science_tool/styles.py src/science_tool/cli.py src/science_tool/tasks_display.py src/science_tool/output.py src/science_tool/verdict/cli.py src/science_tool/dag/cli.py tests/test_cli_styles.py tests/test_cli_color_policy.py tests/dag/test_cli.py
```

Expected: PASS.

- [ ] **Step 4: Manually inspect git diff for unrelated changes.**

Run from repository root:

```bash
git status --short
git diff --stat HEAD
```

Expected:
- Only files named in this plan are modified, plus pre-existing unrelated untracked files if they were present before implementation.
- No `.venv`, generated DAG PNG, cache, or unrelated task files are staged.

- [ ] **Step 5: Commit final verification note if formatting changed files.**

If `ruff format --check` failed and `ruff format` changed files, run from repository root:

```bash
git add science/src/science_tool/styles.py science/src/science_tool/cli.py science/src/science_tool/tasks_display.py science/src/science_tool/output.py science/src/science_tool/verdict/cli.py science/src/science_tool/dag/cli.py science/tests/test_cli_styles.py science/tests/test_cli_color_policy.py science/tests/dag/test_cli.py
git commit -m "style: format CLI output policy changes"
```

Expected: commit succeeds only when formatter changes exist. If formatting was already clean, skip this commit.

## Acceptance Checklist

- [ ] `science tasks list` emits no ANSI by default under `CliRunner`.
- [ ] `science --color=auto tasks list` emits no ANSI under `CliRunner`.
- [ ] `science --color=always tasks list` emits ANSI under `CliRunner`.
- [ ] `NO_COLOR` beats `FORCE_COLOR` when `--color` is omitted.
- [ ] Explicit `--color=always` beats `NO_COLOR`.
- [ ] `tasks list --format json` remains parseable JSON even with `--color=always`.
- [ ] `health` uses the shared color policy.
- [ ] `output.emit_query_rows` and verdict rollup tables use the shared console helper.
- [ ] `dag staleness`, `dag audit`, and `dag validate` accept `--format json`.
- [ ] Existing `--json` DAG spelling still works.
- [ ] Agent-facing DAG audit docs use `--format json`.

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import date
from enum import StrEnum
from typing import Any, TextIO

import click
from rich.console import Console
from rich.style import Style
from rich.text import Text

COLOR_POLICY_CHOICES: tuple[str, ...] = ("never", "auto", "always")

_POLICY_KEY = "science_color_policy"
_CONSOLE_KEY = "science_rich_console"
_COLOR_ENV_KEYS = frozenset({"NO_COLOR", "FORCE_COLOR"})


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
    "evidence-line": ("bold bright_yellow", "bright_yellow"),
    "proposition": ("bold green", "green"),
    "observation": ("bold bright_green", "bright_green"),
    "finding": ("bold bright_green", "bright_green"),
    "story": ("bold bright_magenta", "bright_magenta"),
    "theme": ("bold bright_blue", "bright_blue"),
    "mechanism": ("bold bright_red", "bright_red"),
    "dataset": ("bold cyan", "cyan"),
    "derived-dataset": ("bold cyan", "cyan"),
    "data-package": ("bold bright_cyan", "bright_cyan"),
    "research-package": ("bold bright_cyan", "bright_cyan"),
    "paper": ("bold bright_cyan", "bright_cyan"),
    "workflow": ("bold bright_blue", "bright_blue"),
    "workflow-run": ("bold blue", "blue"),
}

ENTITY_STATUS_STYLES: dict[str, str] = {
    "active": "green",
    "open": "green",
    "proposed": "yellow",
    "draft": "yellow",
    "candidate": "yellow",
    "under-investigation": "bold yellow",
    "partially-answered": "cyan",
    "partially-supported": "cyan",
    "supported": "bold green",
    "answered": "bold green",
    "complete": "bold green",
    "contested": "bold red",
    "weakened": "red",
    "refuted": "bold red",
    "deferred": "dim",
    "superseded": "dim",
    "retired": "dim strike",
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
    if force_color and force_color != "0":
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
            policy = current.obj[_POLICY_KEY]
            return policy if isinstance(policy, ColorPolicy) else ColorPolicy(policy)
        current = current.parent
    return resolve_color_policy(None)


def _new_console(policy: ColorPolicy, file: TextIO | None = None) -> Console:
    match policy:
        case ColorPolicy.NEVER:
            return Console(file=file, force_terminal=False, color_system=None, no_color=True)
        case ColorPolicy.ALWAYS:
            return Console(file=file, force_terminal=True, color_system="standard", no_color=False)
        case ColorPolicy.AUTO:
            auto_env = {key: value for key, value in os.environ.items() if key not in _COLOR_ENV_KEYS}
            return Console(file=file, no_color=False, _environ=auto_env)


def get_console(*, context: click.Context | None = None, file: TextIO | None = None) -> Console:
    policy = get_color_policy(context)
    if file is not None:
        return _new_console(policy, file)

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


def age_style(created: date) -> Style:
    """Map task age to a green->yellow->red gradient."""
    days = (date.today() - created).days
    t = min(max(days, 0), 90) / 90.0
    if t < 0.5:
        s = t * 2
        r = int(60 + 140 * s)
        g = int(180)
        b = int(60 - 60 * s)
    else:
        s = (t - 0.5) * 2
        r = int(200)
        g = int(180 - 120 * s)
        b = int(0)
    return Style(color=f"#{r:02x}{g:02x}{b:02x}")


def entity_kind_styles(kind: str) -> tuple[str, str]:
    return ENTITY_KIND_STYLES.get(kind, (MUTED_STYLE, MUTED_STYLE))


def render_entity_ref(ref: str) -> Text:
    if ":" not in ref:
        return Text(ref)

    kind, local_part = ref.split(":", 1)
    prefix_style, local_style = entity_kind_styles(kind)
    text = Text()
    text.append(kind, style=prefix_style)
    text.append(":")
    text.append(local_part, style=local_style)
    return text


def render_entity_kind(kind: str) -> Text:
    prefix_style, _ = entity_kind_styles(kind)
    return Text(kind, style=prefix_style)


def render_entity_status(status: str) -> Text:
    if not status:
        return Text("")
    return Text(status, style=ENTITY_STATUS_STYLES.get(status, ""))


def render_muted(value: object) -> Text:
    return Text(str(value), style=MUTED_STYLE)


def entity_table_renderers() -> dict[str, Callable[[Any, Mapping[str, Any]], Any]]:
    return {
        "id": lambda value, _row: render_entity_ref(str(value)),
        "canonical_id": lambda value, _row: render_entity_ref(str(value)),
        "kind": lambda value, _row: render_entity_kind(str(value)),
        "type": lambda value, _row: render_entity_kind(str(value)),
        "status": lambda value, _row: render_entity_status(str(value)),
        "path": lambda value, _row: render_muted(value),
    }

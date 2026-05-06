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


def test_resolve_color_policy_ignores_empty_no_color() -> None:
    assert resolve_color_policy(None, env={"NO_COLOR": "", "FORCE_COLOR": "1"}) == ColorPolicy.ALWAYS


def test_resolve_color_policy_honors_force_color_without_no_color() -> None:
    assert resolve_color_policy(None, env={"FORCE_COLOR": "1"}) == ColorPolicy.ALWAYS
    assert resolve_color_policy(None, env={"FORCE_COLOR": "true"}) == ColorPolicy.ALWAYS
    assert resolve_color_policy(None, env={"FORCE_COLOR": "0"}) == ColorPolicy.NEVER


def test_resolve_color_policy_ignores_empty_force_color() -> None:
    assert resolve_color_policy(None, env={"FORCE_COLOR": ""}) == ColorPolicy.NEVER


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


def test_get_console_auto_policy_ignores_no_color_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    with click.Context(click.Command("demo")) as ctx:
        set_color_policy(ctx, ColorPolicy.AUTO)

        console = get_console(context=ctx, file=io.StringIO())

    assert console.no_color is False


def test_render_entity_ref_styles_known_kind() -> None:
    rendered = render_entity_ref("question:q104-rigor-conditional-claims")
    prefix_span = next(span for span in rendered.spans if span.start == 0 and span.end == len("question"))
    local_part_span = next(
        span
        for span in rendered.spans
        if span.start == len("question:") and span.end == len("question:q104-rigor-conditional-claims")
    )

    assert isinstance(rendered, Text)
    assert rendered.plain == "question:q104-rigor-conditional-claims"
    assert prefix_span.style != local_part_span.style


def test_render_entity_ref_handles_unknown_kind() -> None:
    rendered = render_entity_ref("custom-kind:local-part")

    assert rendered.plain == "custom-kind:local-part"
    assert rendered.spans


def test_render_entity_ref_without_kind_is_plain_text() -> None:
    rendered = render_entity_ref("plain-token")

    assert rendered.plain == "plain-token"
    assert rendered.spans == []

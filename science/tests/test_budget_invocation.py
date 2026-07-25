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
@click.option("--include-archived/--no-include-archived", default=True)
@click.option("--aspect", "aspects", multiple=True)
@click.option("--output", "output_path", default=None)
def demo_list(
    status: str | None,
    show_all: bool,
    include_archived: bool,
    aspects: tuple[str, ...],
    output_path: str | None,
) -> None:
    CAPTURED.append(build_complete_via(click.get_current_context(), output_hint="out.json"))


@click.command("list")
@click.option("--status", default=lambda: "proposed")
@click.option("--output", "output_path", default=None)
def callable_default_list(status: str, output_path: str | None) -> None:
    CAPTURED.append(build_complete_via(click.get_current_context(), output_hint="out.json"))


@click.command("list")
@click.option("--status", default="proposed")
@click.option("--output", "output_path", default=None)
def static_default_list(status: str, output_path: str | None) -> None:
    CAPTURED.append(build_complete_via(click.get_current_context(), output_hint="out.json"))


def _run(args: list[str]) -> str:
    CAPTURED.clear()
    result = CliRunner().invoke(demo, args, prog_name="science")
    assert result.exit_code == 0, result.output
    return CAPTURED[0]


def _run_callable_default(args: list[str]) -> str:
    CAPTURED.clear()
    result = CliRunner().invoke(callable_default_list, args, prog_name="science")
    assert result.exit_code == 0, result.output
    return CAPTURED[0]


def _run_static_default(args: list[str]) -> str:
    CAPTURED.clear()
    result = CliRunner().invoke(static_default_list, args, prog_name="science")
    assert result.exit_code == 0, result.output
    return CAPTURED[0]


def test_bare_invocation_appends_only_the_output_flag() -> None:
    assert _run(["list"]) == "science list --output out.json"


def test_user_selection_is_preserved() -> None:
    assert _run(["list", "--status", "proposed"]) == "science list --status proposed --output out.json"


def test_boolean_flags_render_without_a_value() -> None:
    assert _run(["list", "--all"]) == "science list --all --output out.json"


def test_paired_boolean_false_uses_negative_flag() -> None:
    assert _run(["list", "--no-include-archived"]) == "science list --no-include-archived --output out.json"


def test_repeatable_options_repeat() -> None:
    out = _run(["list", "--aspect", "a", "--aspect", "b"])
    assert out == "science list --aspect a --aspect b --output out.json"


def test_existing_output_option_is_replaced_not_duplicated() -> None:
    out = _run(["list", "--output", "old.json"])
    assert out.count("--output") == 1
    assert out.endswith("--output out.json")


def test_defaults_are_omitted() -> None:
    assert "--status" not in _run(["list"])


def test_callable_defaults_are_omitted() -> None:
    assert _run_callable_default([]) == "science --output out.json"


def test_explicit_value_equal_to_default_is_preserved() -> None:
    assert _run_static_default(["--status", "proposed"]) == "science --status proposed --output out.json"


def test_values_with_spaces_are_quoted() -> None:
    out = _run(["list", "--status", "needs review"])
    assert "'needs review'" in out
    assert out == "science list --status 'needs review' --output out.json"


def test_shell_metacharacters_are_quoted() -> None:
    out = _run(["list", "--status", "a;rm -rf b"])
    assert shlex.split(out)[3] == "a;rm -rf b"

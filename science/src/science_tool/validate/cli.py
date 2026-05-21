from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from rich.text import Text

from science_tool.styles import ERROR_STYLE, SUCCESS_STYLE, WARNING_STYLE, get_console
from science_tool.validate._helpers import section_banner
from science_tool.validate.checks import CANONICAL_CHECKS
from science_tool.validate.context import ValidateContextError
from science_tool.validate.result import Result, Severity
from science_tool.validate.runner import RunResult, run


BANNER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


@click.command(name="validate")
@click.option("--verbose", is_flag=True, default=False, help="Show verbose validation details.")
@click.option("--strict", is_flag=True, default=False, help="Enable strict validation checks.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path.cwd,
    metavar="PATH",
    show_default="current working directory",
    help="Science project root.",
)
@click.pass_context
def validate_cmd(
    ctx: click.Context,
    verbose: bool,
    strict: bool,
    output_format: str,
    project_root: Path,
) -> None:
    """Validate a Science project."""
    try:
        result = run(
            project_root,
            strict=strict,
            verbose=verbose,
        )
    except ValidateContextError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(json.dumps(_json_payload(result), indent=2))
    else:
        _emit_text(result)

    if result.errors:
        ctx.exit(1)


def _json_payload(result: RunResult) -> dict[str, Any]:
    return {
        "summary": {
            "errors": result.errors,
            "warnings": result.warnings,
            "infos": result.infos,
        },
        "results": [item.to_dict() for item in result.results],
    }


def _emit_text(result: RunResult) -> None:
    console = get_console(file=click.get_text_stream("stdout"))
    console.print(BANNER)
    console.print("Science Project Validation")
    console.print(BANNER)

    for section in _section_names():
        console.print()
        console.print(section_banner(section))

    for item in result.results:
        console.print(_format_result(item))

    console.print()
    console.print(BANNER)
    console.print(_format_summary(result))


def _section_names() -> list[str]:
    sections: list[str] = []
    for entry in CANONICAL_CHECKS:
        if entry.section not in sections:
            sections.append(entry.section)
    return sections or ["Science project"]


def _format_result(result: Result) -> Text:
    style = _severity_style(result.severity)
    text = Text(style=style)
    text.append(result.severity.name)

    location = _location(result)
    if location:
        text.append(f" {location}")
        if result.rule:
            text.append(f" [{result.rule}]")
        text.append(f" {result.message}")
    else:
        text.append(f" {result.message}")
        if result.rule:
            text.append(f" [{result.rule}]")
    if result.task:
        text.append(f" ({result.task})")
    return text


def _location(result: Result) -> str | None:
    if result.path is None:
        return None
    if result.line is None:
        return str(result.path)
    return f"{result.path}:{result.line}"


def _format_summary(result: RunResult) -> Text:
    status = "PASSED: all checks clean"
    style = SUCCESS_STYLE
    if result.errors:
        status = f"FAILED: {result.errors} error(s), {result.warnings} warning(s)"
        style = ERROR_STYLE
    elif result.warnings:
        status = f"PASSED with {result.warnings} warning(s)"
        style = WARNING_STYLE

    text = Text(style=style)
    text.append(status)
    return text


def _severity_style(severity: Severity) -> str:
    if severity is Severity.ERROR:
        return ERROR_STYLE
    if severity is Severity.WARN:
        return WARNING_STYLE
    return ""

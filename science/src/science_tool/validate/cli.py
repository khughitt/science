from __future__ import annotations

import json
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import Any, cast

import click
from rich.text import Text

from science_tool.styles import ERROR_STYLE, SUCCESS_STYLE, WARNING_STYLE, get_console
from science_tool.validate._helpers import section_banner
from science_tool.validate.acceptance import filter_accepted_warnings
from science_tool.validate.context import ValidateContextError
from science_tool.validate.gates import GATE_TIERS, gated_findings
from science_tool.validate.result import Result, Severity
from science_tool.validate.runner import VALIDATE_PROFILES, RunResult, ValidationProfile, run

BANNER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


@click.command(name="validate")
@click.option("--verbose", is_flag=True, default=False, help="Show verbose validation details.")
@click.option("--strict", is_flag=True, default=False, help="Enable strict validation checks.")
@click.option(
    "--fail-on",
    "fail_on",
    type=click.Choice(list(GATE_TIERS)),
    default=None,
    help="Exit nonzero when a finding gated at this tier (or below) is present. "
    "Overrides science.yaml code_gate. Default: report (never blocks).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--profile",
    "profile",
    type=click.Choice(list(VALIDATE_PROFILES)),
    default="full",
    show_default=True,
    help="Validation profile to run. Use commit for fast authoring-time checks.",
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
    fail_on: str | None,
    output_format: str,
    profile: str,
    project_root: Path,
) -> None:
    """Validate a Science project."""
    captured_stdout = StringIO()
    try:
        with redirect_stdout(captured_stdout):
            result = run(
                project_root,
                strict=strict,
                verbose=verbose,
                fail_on=fail_on,
                profile=cast(ValidationProfile, profile),
            )
            result = _with_accepted_warnings_filtered(project_root, result)
    except ValidateContextError as exc:
        raise click.ClickException(str(exc)) from exc

    _record_validation_summary(result=result, profile=profile, strict=strict, fail_on=fail_on)

    sidecar_stdout = captured_stdout.getvalue()
    if sidecar_stdout:
        click.echo(sidecar_stdout, nl=False, err=True)

    if output_format == "json":
        click.echo(json.dumps(_json_payload(result), indent=2))
    else:
        _emit_text(result)

    if result.errors or result.gated:
        ctx.exit(1)


def _record_validation_summary(
    *,
    result: RunResult,
    profile: str,
    strict: bool,
    fail_on: str | None,
) -> None:
    from science_tool.telemetry import (
        append_event,
        get_telemetry_dir,
        new_validation_summary_event,
        telemetry_enabled,
    )

    if not telemetry_enabled():
        return
    event = new_validation_summary_event(
        command="validate",
        profile=profile,
        strict=strict,
        fail_on=fail_on,
        errors=result.errors,
        warnings=result.warnings,
        infos=result.infos,
        gated=bool(result.gated),
        rule_ids=[item.rule for item in result.results],
    )
    append_event(get_telemetry_dir(), event)


def _json_payload(result: RunResult) -> dict[str, Any]:
    return {
        "summary": {
            "errors": result.errors,
            "warnings": result.warnings,
            "infos": result.infos,
        },
        "results": [item.to_dict() for item in result.results if item.severity is not Severity.INFO],
    }


def _with_accepted_warnings_filtered(project_root: Path, result: RunResult) -> RunResult:
    filtered_results = filter_accepted_warnings(project_root, result.results)
    if len(filtered_results) == len(result.results):
        return result
    return replace(
        result,
        results=filtered_results,
        errors=sum(1 for item in filtered_results if item.severity is Severity.ERROR),
        warnings=sum(1 for item in filtered_results if item.severity is Severity.WARN),
        infos=sum(1 for item in filtered_results if item.severity is Severity.INFO),
        gated=tuple(gated_findings(filtered_results, result.gate_tier)),
    )


def _emit_text(result: RunResult) -> None:
    console = get_console(file=click.get_text_stream("stdout"))
    console.print(BANNER)
    console.print("Science Project Validation")
    console.print(BANNER)

    for section in _section_names(result):
        console.print()
        console.print(section_banner(section))

    for item in result.results:
        console.print(_format_result(item))

    console.print()
    console.print(BANNER)
    console.print(_format_summary(result))


def _section_names(result: RunResult) -> list[str]:
    return list(result.sections) or ["Science project"]


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
    if result.errors:
        status = f"FAILED: {result.errors} error(s), {result.warnings} warning(s)"
        style = ERROR_STYLE
    elif result.gated:
        status = (
            f"FAILED: {len(result.gated)} finding(s) gated at tier "
            f"'{result.gate_tier}', {result.warnings} warning(s)"
        )
        style = ERROR_STYLE
    elif result.warnings:
        status = f"PASSED with {result.warnings} warning(s)"
        style = WARNING_STYLE
    else:
        status = "PASSED: all checks clean"
        style = SUCCESS_STYLE

    text = Text(style=style)
    text.append(status)
    return text


def _severity_style(severity: Severity) -> str:
    if severity is Severity.ERROR:
        return ERROR_STYLE
    if severity is Severity.WARN:
        return WARNING_STYLE
    return ""

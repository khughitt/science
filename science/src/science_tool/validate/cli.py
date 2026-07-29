from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import click
from rich.text import Text
from science_model.audit import AuditFinding, LocationEvidence, PathSubject

if TYPE_CHECKING:
    from science_tool.budget.sink import BoundedSink

from science_tool.output import emit
from science_tool.styles import ERROR_STYLE, SUCCESS_STYLE, WARNING_STYLE
from science_tool.validate._helpers import section_banner
from science_tool.validate.acceptance import filter_accepted_warnings
from science_tool.validate.context import ValidateContextError
from science_tool.validate.gates import GATE_TIERS, gated_findings
from science_tool.validate.observations import ValidationNotice
from science_tool.validate.runner import VALIDATE_PROFILES, RunResult, ValidationProfile, run

BANNER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


@click.command(name="validate")
@click.option("--verbose", is_flag=True, default=False, help="Show verbose validation details.")
@click.option("--strict", is_flag=True, default=False, help="Enable strict validation checks.")
@click.option(
    "--all",
    "include_all_checks",
    is_flag=True,
    default=False,
    help="Run checks disabled by project-level narrowing configuration.",
)
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
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted validation report to PATH instead of stdout.",
)
@click.pass_context
def validate_cmd(
    ctx: click.Context,
    verbose: bool,
    strict: bool,
    include_all_checks: bool,
    fail_on: str | None,
    output_format: str,
    profile: str,
    project_root: Path,
    output_path: Path | None,
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
                include_all_checks=include_all_checks,
            )
            result = _with_accepted_warnings_filtered(project_root, result)
    except ValidateContextError as exc:
        raise click.ClickException(str(exc)) from exc

    _record_validation_summary(result=result, profile=profile, strict=strict, fail_on=fail_on)

    sidecar_stdout = captured_stdout.getvalue()
    if sidecar_stdout:
        click.echo(sidecar_stdout, nl=False, err=True)

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.validate.projection import project_validate_results

    sink = BoundedSink(
        lookup("validate"),
        output_path=output_path,
        command_path="validate",
        complete_via=build_complete_via(click.get_current_context(), output_hint=hint_for("validate", output_format)),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete validation report to {output_path}")
        if output_path is not None
        else None
    )

    # Visibility is FORMAT-SPECIFIC and MUST be applied before the cap: INFO rows must never
    # consume the cap, and each format's omission count must reflect what that format shows.
    # (JSON drops all INFO; text keeps only "visible info" per _display_filter.)
    json_visible = [item for item in result.results if item.severity != "info"]
    text_visible = [item for item in result.results if _display_filter(item, result, verbose=verbose)]
    if output_path is not None:
        json_results, json_omitted = json_visible, 0
        text_results, text_omitted = text_visible, 0
    else:
        json_results, json_omitted = project_validate_results(json_visible)
        text_results, text_omitted = project_validate_results(text_visible)

    # Summary counts always come from the FULL result (via _json_payload); projection
    # narrows only the displayed `results`. results_omitted is added only when it projected.
    payload = {
        "summary": _json_payload(result)["summary"],
        "results": [_legacy_result_projection(item) for item in json_results],
    }
    if json_omitted:
        payload["results_omitted"] = json_omitted

    emit(
        output_format=output_format,
        payload=payload,
        render_text=lambda: _emit_text(result, text_results, text_omitted, sink, verbose=verbose),
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

    # Exit reflects the FULL result, never the projected display.
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
        rule_ids=[item.rule_id for item in result.results],
    )
    append_event(get_telemetry_dir(), event)


def _json_payload(result: RunResult) -> dict[str, Any]:
    emitted_results = [item for item in result.results if item.severity != "info"]
    return {
        "summary": {
            "errors": sum(1 for item in emitted_results if item.severity == "error"),
            "warnings": sum(1 for item in emitted_results if item.severity == "warn"),
            "infos": sum(1 for item in emitted_results if item.severity == "info"),
        },
        "results": [_legacy_result_projection(item) for item in emitted_results],
    }


def _with_accepted_warnings_filtered(project_root: Path, result: RunResult) -> RunResult:
    filtered_results = filter_accepted_warnings(
        project_root,
        result.results,
        registry=result.registry,
    )
    if len(filtered_results) == len(result.results):
        return result
    return replace(
        result,
        results=filtered_results,
        errors=sum(1 for item in filtered_results if item.severity == "error"),
        warnings=sum(1 for item in filtered_results if item.severity == "warn"),
        infos=sum(1 for item in filtered_results if item.severity == "info"),
        gated=tuple(gated_findings(filtered_results, result.gate_tier)),
    )


def _emit_text(
    result: RunResult,
    shown_results: list[AuditFinding],
    omitted: int,
    sink: BoundedSink,
    *,
    verbose: bool = False,
) -> None:
    # shown_results is already filtered by _display_filter AND capped by the caller; render
    # it as-is. The header/coverage/notices/summary come from the FULL result.
    console = sink.console
    console.print(BANNER)
    console.print("Science Project Validation")
    console.print(BANNER)
    console.print(_format_check_coverage(result), soft_wrap=True)
    for item in _notice_results(result):
        console.print(_format_notice(item), soft_wrap=True)

    if verbose:
        for section in _section_names(result):
            console.print(section_banner(section))

    for item in shown_results:
        console.print(_format_result(item), soft_wrap=True)

    if verbose:
        for notice in result.notices:
            console.print(_format_validation_notice(notice), soft_wrap=True)

    if omitted:
        sink.echo(f"showing {len(shown_results)} of {len(shown_results) + omitted} findings")
        sink.echo(f"  complete output:  {sink.complete_via}")

    console.print()
    console.print(BANNER)
    console.print(_format_summary(result), soft_wrap=True)


def _format_check_coverage(result: RunResult) -> str:
    included_count = len(result.sections)
    skipped_count = len(result.skipped_sections)
    if skipped_count:
        skipped = ", ".join(result.skipped_sections)
        return f"Checks: {included_count} included, {skipped_count} skipped (profile: {result.profile}; skipped: {skipped})"
    return f"Checks: {included_count} included, 0 skipped (profile: {result.profile})"


def _display_filter(
    item: AuditFinding,
    run_result: RunResult,
    *,
    verbose: bool,
) -> bool:
    if verbose:
        return not _is_visible_info(item, run_result)
    return item.severity != "info"


def _notice_results(result: RunResult) -> list[AuditFinding]:
    return [item for item in result.results if _is_visible_info(item, result)]


def _is_visible_info(finding: AuditFinding, run_result: RunResult | None = None) -> bool:
    if finding.severity != "info":
        return False
    if run_result is None:
        raise ValueError("RunResult registry is required to resolve INFO visibility")
    return run_result.registry.rule(finding.rule_id).default_visibility == "visible"


def _section_names(result: RunResult) -> list[str]:
    return list(result.sections)


def _format_notice(result: AuditFinding) -> Text:
    text = Text()
    text.append("NOTE")
    text.append(f" {result.message}")
    task = result.qualifiers.get("task")
    if isinstance(task, str):
        text.append(f" ({task})")
    return text


def _format_result(result: AuditFinding) -> Text:
    if _is_checking_info(result):
        return _format_checking_info_result(result)

    style = _severity_style(result.severity)
    text = Text(style=style)
    text.append(result.severity.upper())

    location = _location(result)
    if location:
        text.append(f" {location}")
        text.append(f" [{result.rule_id}]")
        text.append(f" {result.message}")
    else:
        text.append(f" {result.message}")
        text.append(f" [{result.rule_id}]")
    task = result.qualifiers.get("task")
    if isinstance(task, str):
        text.append(f" ({task})")
    return text


def _format_checking_info_result(result: AuditFinding) -> Text:
    text = Text(style=_severity_style(result.severity))
    text.append(result.severity.upper())
    text.append(f" [{result.rule_id}]")
    text.append(f" {result.message}")
    task = result.qualifiers.get("task")
    if isinstance(task, str):
        text.append(f" ({task})")
    return text


def _is_checking_info(result: AuditFinding) -> bool:
    return (
        result.severity == "info" and isinstance(result.subject, PathSubject) and result.message.startswith("Checking ")
    )


def _location(result: AuditFinding) -> str | None:
    if not isinstance(result.subject, PathSubject):
        return None
    line = next(
        (evidence.line for evidence in result.evidence if isinstance(evidence, LocationEvidence)),
        None,
    )
    if line is None:
        return result.subject.path
    return f"{result.subject.path}:{line}"


def _format_summary(result: RunResult) -> Text:
    if result.errors:
        status = f"FAILED: {result.errors} error(s), {result.warnings} warning(s)"
        style = ERROR_STYLE
    elif result.gated:
        status = (
            f"FAILED: {len(result.gated)} finding(s) gated at tier '{result.gate_tier}', {result.warnings} warning(s)"
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


def _severity_style(severity: str) -> str:
    if severity == "error":
        return ERROR_STYLE
    if severity == "warn":
        return WARNING_STYLE
    return ""


def _legacy_result_projection(finding: AuditFinding) -> dict[str, object]:
    path = finding.subject.path if isinstance(finding.subject, PathSubject) else None
    line = next(
        (evidence.line for evidence in finding.evidence if isinstance(evidence, LocationEvidence)),
        None,
    )
    task = finding.qualifiers.get("task")
    return {
        "severity": finding.severity,
        "path": path,
        "line": line,
        "message": finding.message,
        "rule": finding.rule_id,
        "task": task if isinstance(task, str) else None,
    }


def _format_validation_notice(notice: ValidationNotice) -> Text:
    text = Text()
    if notice.path is not None:
        location = str(notice.path)
        if notice.line is not None:
            location = f"{location}:{notice.line}"
        text.append(f"INFO {location} {notice.message}")
    else:
        text.append(f"INFO {notice.message}")
    return text

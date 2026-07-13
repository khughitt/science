from __future__ import annotations

import sys
from typing import Any

import click

from science_tool.annotation.cli import annotate_group
from science_tool.belief_cli import belief_group
from science_tool.benchmark_cli import benchmark_group
from science_tool.bib_cli import bib_group
from science_tool.big_picture.cli import big_picture_group
from science_tool.book_split_cli import book_split_command
from science_tool.commons import commons_group
from science_tool.curate.cli import curate_group
from science_tool.data_cli import data_group
from science_tool.dag.cli import dag_group
from science_tool.datasets.cli import dataset_group
from science_tool.datasets_discovery_cli import datasets_group
from science_tool.doi_cli import doi_group
from science_tool.discussions_cli import discussion_group
from science_tool.distill_cli import distill_group
from science_tool.entities_cli import entity_group
from science_tool.entities_inventory_cli import entities_group
from science_tool.evidence_lines_cli import evidence_line_group
from science_tool.explore_ideas_cli import explore_ideas_group
from science_tool.feedback_cli import feedback_group
from science_tool.graph.cli import graph_group
from science_tool.graph.health_cli import health_command
from science_tool.hypotheses_cli import hypothesis_group
from science_tool.inquiry_cli import inquiry_group
from science_tool.interpretations_cli import interpretation_group
from science_tool.labnote_cli import labnote_group
from science_tool.markers_cli import markers_group
from science_tool.paper_cli import paper_fetch_command, paper_group
from science_tool.patch.cli import patch_group
from science_tool.peers_cli import peers_group
from science_tool.project_cli import project_group
from science_tool.propositions_cli import proposition_group
from science_tool.prose_lint_cli import prose_group
from science_tool.qa_audit.cli import qa_audit_command
from science_tool.questions_cli import question_group
from science_tool.refs_cli import refs_group
from science_tool.research_package.cli import research_package_group
from science_tool.search_cli import search_command
from science_tool.skills_lint import skills_group
from science_tool.styles import (
    COLOR_POLICY_CHOICES,
    resolve_color_policy,
    set_color_policy,
)
from science_tool.sync_cli import sync_group
from science_tool.tasks_cli import tasks_group
from science_tool.telemetry_cli import telemetry_group
from science_tool.validate.cli import validate_cmd
from science_tool.verdict.cli import verdict_group
from science_tool.wander.cli import wander_command


_TELEMETRY_ARGV: list[str] = []


class TelemetryGroup(click.Group):
    """Root Click group that records local telemetry for command failures."""

    def main(self, *args: Any, **kwargs: Any) -> Any:
        standalone_mode = kwargs.pop("standalone_mode", True)
        raw_args = _raw_click_args(args=args, kwargs=kwargs)
        global _TELEMETRY_ARGV
        _TELEMETRY_ARGV = raw_args
        try:
            result = super().main(*args, standalone_mode=False, **kwargs)
            if isinstance(result, int) and result != 0 and standalone_mode:
                raise SystemExit(result)
            return result
        except click.ClickException as exc:
            _record_telemetry_error(raw_args, exc)
            if not standalone_mode:
                raise
            exc.show()
            raise SystemExit(exc.exit_code) from exc
        except click.Abort as exc:
            _record_telemetry_error(raw_args, exc)
            if not standalone_mode:
                raise
            click.echo("Aborted!", err=True)
            raise SystemExit(1) from exc


def _raw_click_args(*, args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[str]:
    raw = kwargs.get("args")
    if raw is None and args:
        raw = args[0]
    if raw is None:
        return sys.argv[1:]
    return [str(value) for value in raw]


def _command_from_argv(argv: list[str]) -> str:
    command_parts: list[str] = []
    skip_value = False
    for token in argv:
        if skip_value:
            skip_value = False
            continue
        if token.startswith("--"):
            if "=" not in token:
                skip_value = True
            continue
        if token.startswith("-") and token != "-":
            skip_value = True
            continue
        command_parts.append(token)
        if len(command_parts) >= 2:
            break
    return " ".join(command_parts) or "unknown"


def _command_from_context() -> str:
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return _command_from_argv(_TELEMETRY_ARGV)
    parts = ctx.command_path.split()
    if parts and parts[0] in {"main", "science"}:
        parts = parts[1:]
    return " ".join(parts) or _command_from_argv(_TELEMETRY_ARGV)


def _record_telemetry_finish() -> None:
    from science_tool.telemetry import append_event, get_telemetry_dir, new_event, telemetry_enabled

    if not telemetry_enabled():
        return
    event = new_event(
        event_type="command_finish",
        command=_command_from_context(),
        argv=_TELEMETRY_ARGV,
        exit_code=0,
    )
    append_event(get_telemetry_dir(), event)


def _record_telemetry_error(argv: list[str], exc: BaseException) -> None:
    from science_tool.telemetry import append_event, get_telemetry_dir, new_event, telemetry_enabled

    if not telemetry_enabled():
        return
    exit_code = exc.exit_code if isinstance(exc, click.ClickException) else 1
    event = new_event(
        event_type="command_error",
        command=_command_from_argv(argv),
        argv=argv,
        exit_code=exit_code,
        error_class=exc.__class__.__name__,
        error_message_template=_error_message_template(exc),
    )
    append_event(get_telemetry_dir(), event)


def _error_message_template(exc: BaseException) -> str:
    if isinstance(exc, click.NoSuchOption):
        return "No such option: {option}"
    if isinstance(exc, click.UsageError):
        return exc.__class__.__name__
    return exc.__class__.__name__


@click.group(cls=TelemetryGroup)
@click.version_option(
    package_name="science",
    prog_name="science",
    message="%(prog)s %(version)s",
)
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


@main.result_callback()
def _record_cli_success(_: object, **__: object) -> None:
    _record_telemetry_finish()


main.add_command(dag_group)
main.add_command(entity_group)
main.add_command(curate_group)
main.add_command(research_package_group)
main.add_command(verdict_group)
main.add_command(big_picture_group)
main.add_command(refs_group)
main.add_command(annotate_group)
main.add_command(markers_group)
main.add_command(prose_group)
main.add_command(skills_group)
main.add_command(peers_group)
main.add_command(wander_command)
main.add_command(qa_audit_command)
main.add_command(commons_group)
main.add_command(validate_cmd)
main.add_command(patch_group)
main.add_command(telemetry_group)
main.add_command(feedback_group)
main.add_command(labnote_group)
main.add_command(search_command)
main.add_command(data_group)
main.add_command(distill_group)
main.add_command(book_split_command)
main.add_command(doi_group)
main.add_command(benchmark_group)
main.add_command(graph_group)
main.add_command(health_command)
main.add_command(dataset_group)
main.add_command(tasks_group)
main.add_command(explore_ideas_group)
main.add_command(proposition_group)
main.add_command(evidence_line_group)
main.add_command(hypothesis_group)
main.add_command(discussion_group)
main.add_command(interpretation_group)
main.add_command(question_group)
main.add_command(entities_group)
main.add_command(belief_group)
main.add_command(inquiry_group)
main.add_command(datasets_group)
main.add_command(project_group)
main.add_command(bib_group)
main.add_command(sync_group)
main.add_command(paper_group)
main.add_command(paper_fetch_command)


if __name__ == "__main__":
    main()

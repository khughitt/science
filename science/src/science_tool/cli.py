from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, cast

import click

from science_tool.annotation.cli import annotate_group
from science_tool.benchmark_cli import benchmark_group
from science_tool.big_picture.cli import big_picture_group
from science_tool.book_split_cli import book_split_command
from science_tool.causal.export_chirho import export_chirho_script
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.commons import commons_group
from science_tool.curate.cli import curate_group
from science_tool.data_cli import data_group
from science_tool.data_root import (
    DataRootConfigError,
    discover_project_root,
    project_config_path,
    resolve_data_root,
)
from science_tool.dag.cli import dag_group
from science_tool.data_worktree import hydrate_worktree_data
from science_tool.datasets import available_adapters, get_adapter, search_all
from science_tool.datasets import infer_schema as _infer_schema
from science_tool.datasets.cli import dataset_group
from science_tool.datasets.validate import validate_path
from science_tool.doi_cli import doi_group
from science_tool.distill_cli import distill_group
from science_tool.entities import list_entities
from science_tool.entities_cli import entity_group
from science_tool.entities_inventory import build_inventory
from science_tool.entity_kinds import register_local_kind
from science_tool.entity_migrations import audit_identifiers
from science_tool.explore_ideas import (
    ApplyValidationError,
    ApplyWriteBackError,
    apply_report,
    backfill_lens_views,
    check_report,
    inspect_gaps_report,
    resolve_anchors_report,
)
from science_tool.feedback_cli import feedback_group
from science_tool.graph import belief_profile, belief_snapshot
from science_tool.graph.cli import graph_group
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    get_inquiry,
    list_inquiries,
    shorten_uri,
    validate_inquiry,
)
from science_tool.labnote_cli import labnote_group
from science_tool.markers_cli import markers_group
from science_tool.output import OUTPUT_FORMATS, emit, emit_query_rows
from science_tool.patch.cli import patch_group
from science_tool.peers_cli import peers_group
from science_tool.project_artifacts.cli import artifacts_group as _artifacts_group
from science_tool.prose_lint_cli import prose_group
from science_tool.qa_audit.cli import qa_audit_command
from science_tool.refs_cli import refs_group
from science_tool.research_package.cli import research_package_group
from science_tool.search_cli import search_command
from science_tool.skills_lint import skills_group
from science_tool.styles import (
    COLOR_POLICY_CHOICES,
    resolve_color_policy,
    set_color_policy,
)
from science_tool.telemetry_cli import telemetry_group
from science_tool.typed_entity_cli import (
    build_origin_frontmatter,
    create_typed_entity,
    emit_entity_warnings,
    list_typed_entities,
    show_typed_entity,
)
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
main.add_command(dataset_group)


@main.group("entities")
def entities_group() -> None:
    """Inspect and audit Science entity inventories."""


@entities_group.command("inventory")
@click.option(
    "--project-root",
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Project root to inventory (legacy alias; default: current working directory).",
)
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json")
@click.option("--output", type=click.Path(path_type=Path), default=None)
def entities_inventory_command(
    project_path: Path,
    output_format: str,
    output: Path | None,
) -> None:
    """Emit the versioned Science entity inventory for a project."""
    inventory = build_inventory(project_path)
    rendered = inventory.model_dump_json(indent=2) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        output.write_text(rendered, encoding="utf-8")


@entities_group.command("audit-identifiers")
@click.option(
    "--project-root",
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Project root to audit (legacy alias; default: current working directory).",
)
def entities_audit_identifiers_command(project_path: Path) -> None:
    emit(output_format="json", payload=audit_identifiers(project_path), render_text=lambda: None)


@entities_group.command("mark-superseded")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_mark_superseded_command(project_root: Path, apply_changes: bool) -> None:
    """Auto-derive `superseded` status from linear supersedes chains (report, then --apply)."""
    from science_tool.consolidation import mark_superseded

    report = mark_superseded(project_root, apply=apply_changes)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.command("archive")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--status", "statuses", multiple=True, help="Statuses to archive (default: superseded, archived).")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_archive_command(project_root: Path, statuses: tuple[str, ...], apply_changes: bool) -> None:
    """Relocate hidden-status entities into entities/_archive/ (report, then --apply)."""
    from datetime import datetime, timezone

    from science_tool.archive import DEFAULT_ARCHIVE_STATUSES, archive_entities

    status_set = frozenset(statuses) if statuses else DEFAULT_ARCHIVE_STATUSES
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = archive_entities(project_root, statuses=status_set, apply=apply_changes, now=now)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.command("unarchive")
@click.argument("ids", nargs=-1, required=True)
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_unarchive_command(ids: tuple[str, ...], project_root: Path, apply_changes: bool) -> None:
    """Restore archived entities to their original path (report, then --apply)."""
    from datetime import datetime, timezone

    from science_tool.archive import unarchive_entities

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = unarchive_entities(project_root, list(ids), apply=apply_changes, now=now)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.group("consolidate")
def entities_consolidate_group() -> None:
    """Collapse a cluster of entities into one cluster-digest (scaffold, then apply)."""


@entities_consolidate_group.command("scaffold")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option(
    "--into",
    "digest_id",
    required=True,
    help="Canonical synthesis id to mint for the cluster-digest (e.g. synthesis:0001-slug).",
)
@click.option("--members", required=True, help="Comma-separated member entity ids.")
@click.option("--title", default=None, help="Digest title (default: derived placeholder).")
def entities_consolidate_scaffold_command(project_root: Path, digest_id: str, members: str, title: str | None) -> None:
    """Mint a cluster-digest stub with consolidates relations (touches no members)."""
    from science_tool.consolidate import scaffold_digest

    member_ids = [m.strip() for m in members.split(",") if m.strip()]
    report = scaffold_digest(project_root, digest_id=digest_id, member_ids=member_ids, title=title or digest_id)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_consolidate_group.command("apply")
@click.argument("digest_id")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_consolidate_apply_command(digest_id: str, project_root: Path, apply_changes: bool) -> None:
    """Demote + relocate the digest's consolidated members (report, then --apply)."""
    from datetime import datetime, timezone

    from science_tool.consolidate import apply_consolidation

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = apply_consolidation(project_root, digest_id, apply=apply_changes, now=now)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.command("generate-decisions")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--write", "write_changes", is_flag=True, help="Write core/decisions.md (default: print).")
def entities_generate_decisions_command(project_root: Path, write_changes: bool) -> None:
    """Render core/decisions.md from entities/decision/*.md (generated view, §B5)."""
    import yaml as _yaml

    from science_tool.graph.decision_log import (
        DECISIONS_REL,
        read_decision_owners,
        render_decisions_view,
    )

    _manifest = _yaml.safe_load(project_config_path(project_root).read_text(encoding="utf-8")) or {}
    _v = _manifest.get("layout_version")
    version = _v if isinstance(_v, int) else None
    if version is None or version < 3:
        raise click.ClickException(
            f"generate-decisions needs an `entities/decision/` owner root, but this project is "
            f"layout_version {version}. This Science version supports layout_version 3 only; "
            f"the v2 layout is no longer supported."
        )

    owners = read_decision_owners(project_root / "entities" / "decision")
    rendered = render_decisions_view(owners)
    if write_changes:
        out = project_root / DECISIONS_REL
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
        click.echo(f"wrote {DECISIONS_REL} ({len(owners)} decisions)")
    else:
        click.echo(rendered)


@entities_group.command("register-kind")
@click.argument("kind")
@click.option("--class", "entity_class", required=True)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Project root whose local profile should be updated (legacy alias; default: current working directory).",
)
def entities_register_kind_command(kind: str, entity_class: str, project_path: Path) -> None:
    """Register a project-local entity kind in the local profile."""
    try:
        result = register_local_kind(project_path, kind, entity_class)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{kind}: {result}")


@main.group("propositions")
def proposition_group() -> None:
    """Proposition source commands."""


@proposition_group.command("create")
@click.argument("title")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def proposition_create(
    title: str,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored proposition."""

    create_typed_entity(
        kind="proposition",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=list(source_refs),
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
    )


@proposition_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def proposition_show(ref: str, output_format: str) -> None:
    """Show a source-authored proposition."""
    show_typed_entity("proposition", ref, output_format)


@proposition_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def proposition_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored propositions."""
    list_typed_entities("proposition", status, related, output_format)


@main.group("evidence-lines")
def evidence_line_group() -> None:
    """Evidence-line source commands."""


@evidence_line_group.command("create")
@click.argument("title")
@click.option("--target", required=True, help="Target proposition or claim reference")
@click.option("--stance", required=True, type=click.Choice(["supports", "disputes"]), help="Evidence stance")
@click.option("--source", default=None, help="Source reference")
@click.option("--strength", default=None, type=click.Choice(["strong", "moderate", "weak"]))
@click.option(
    "--evidence-type",
    default=None,
    type=click.Choice(
        [
            "literature",
            "literature_evidence",
            "empirical_data",
            "empirical_data_evidence",
            "simulation",
            "simulation_evidence",
            "benchmark",
            "benchmark_evidence",
            "expert_judgment",
            "negative_result",
        ]
    ),
)
@click.option("--independence", default=None, type=click.Choice(["independent", "shared-source", "circular"]))
@click.option("--independence-group", default=None, help="Independence group key for shared-source/circular evidence")
@click.option(
    "--belief-eligible/--no-belief-eligible",
    default=None,
    help="Whether the line can contribute to belief aggregation; use --no-belief-eligible for staged lines",
)
@click.option(
    "--dispute-scope",
    default=None,
    type=click.Choice(["whole_claim", "generalization", "mechanism", "boundary"]),
)
@click.option(
    "--evidence-role",
    default=None,
    type=click.Choice(["direct_test", "proxy_support", "background_constraint", "negative_control", "model_criticism"]),
)
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def evidence_line_create(
    title: str,
    target: str,
    stance: str,
    source: str | None,
    strength: str | None,
    evidence_type: str | None,
    independence: str | None,
    independence_group: str | None,
    belief_eligible: bool | None,
    dispute_scope: str | None,
    evidence_role: str | None,
    related_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored evidence line."""

    extra_frontmatter: dict[str, object] = {
        "target": target,
        "stance": stance,
    }
    if source:
        extra_frontmatter["source"] = source
        source_refs = [source]
    else:
        source_refs = []
    if strength:
        extra_frontmatter["strength"] = strength
    if evidence_type:
        extra_frontmatter["evidence_type"] = evidence_type
    if independence:
        extra_frontmatter["independence"] = independence
    if independence_group:
        extra_frontmatter["independence_group"] = independence_group
    if belief_eligible is not None:
        extra_frontmatter["belief_eligible"] = belief_eligible
    if dispute_scope:
        extra_frontmatter["dispute_scope"] = dispute_scope
    if evidence_role:
        extra_frontmatter["evidence_role"] = evidence_role

    create_typed_entity(
        kind="evidence-line",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=source_refs,
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
        extra_frontmatter=extra_frontmatter,
    )


@evidence_line_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def evidence_line_show(ref: str, output_format: str) -> None:
    """Show a source-authored evidence line."""
    show_typed_entity("evidence-line", ref, output_format)


@evidence_line_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def evidence_line_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored evidence lines."""
    list_typed_entities("evidence-line", status, related, output_format)


@main.group("hypotheses")
def hypothesis_group() -> None:
    """Hypothesis source commands."""


@hypothesis_group.command("create")
@click.argument("title")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option(
    "--phase",
    type=click.Choice(["active", "candidate"]),
    default="active",
    show_default=True,
    help="candidate trial framing (includes Promotion criteria) or committed active frame",
)
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
@click.option(
    "--origin",
    "origins",
    multiple=True,
    help="Origin as TYPE[:REF][@DATE], e.g. user, literature:Smith2019@2019-03-01. Repeatable.",
)
@click.option("--added-by", "added_by", default=None, help="Discovery stamp (who surfaced this entity).")
def hypothesis_create(
    title: str,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    phase: str,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
    origins: tuple[str, ...],
    added_by: str | None,
) -> None:
    """Create a source-authored hypothesis."""

    sections = list(with_sections)
    if phase == "candidate" and "promotion-criteria" not in sections:
        sections.append("promotion-criteria")

    extra = build_origin_frontmatter(origins, added_by)

    create_typed_entity(
        kind="hypothesis",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=list(source_refs),
        phase=phase,
        with_sections=sections,
        without_sections=list(without_sections),
        no_hints=no_hints,
        extra_frontmatter=extra,
    )


@hypothesis_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def hypothesis_show(ref: str, output_format: str) -> None:
    """Show a source-authored hypothesis."""
    show_typed_entity("hypothesis", ref, output_format)


@hypothesis_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def hypothesis_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored hypotheses."""
    list_typed_entities("hypothesis", status, related, output_format)


@main.group("discussions")
def discussion_group() -> None:
    """Discussion source commands."""


@discussion_group.command("create")
@click.argument("title")
@click.option("--focus", "focus_refs", multiple=True, help="Focus entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def discussion_create(
    title: str,
    focus_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored discussion."""

    create_typed_entity(
        kind="discussion",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(focus_refs),
        source_refs=list(source_refs),
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
    )


@discussion_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def discussion_show(ref: str, output_format: str) -> None:
    """Show a source-authored discussion."""
    show_typed_entity("discussion", ref, output_format)


@discussion_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def discussion_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored discussions."""
    list_typed_entities("discussion", status, related, output_format)


@main.group("interpretations")
def interpretation_group() -> None:
    """Interpretation source commands."""


@interpretation_group.command("create")
@click.argument("title")
@click.option("--input", "input_refs", multiple=True, help="Input source reference (repeatable)")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def interpretation_create(
    title: str,
    input_refs: tuple[str, ...],
    related_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored interpretation."""

    create_typed_entity(
        kind="interpretation",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=list(input_refs),
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
    )


@interpretation_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def interpretation_show(ref: str, output_format: str) -> None:
    """Show a source-authored interpretation."""
    show_typed_entity("interpretation", ref, output_format)


@interpretation_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def interpretation_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored interpretations."""
    list_typed_entities("interpretation", status, related, output_format)


@main.group("explore-ideas")
def explore_ideas_group() -> None:
    """Explore-ideas commands."""


@explore_ideas_group.command("apply")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option("--model-id", "model_id", required=True, help="Model id for the --added-by provenance stamp.")
@click.option("--check", "check_only", is_flag=True, help="Validate and summarize the apply plan without writing.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def explore_ideas_apply(from_value: str, model_id: str, check_only: bool, output_format: str) -> None:
    """Apply kept candidates from an exploration report to real entities."""
    try:
        if check_only:
            check_result = check_report(Path.cwd(), from_value, model_id)

            def _render_check() -> None:
                click.echo(
                    f"{len(check_result.to_create)} would create, "
                    f"{len(check_result.skipped_applied)} already applied, "
                    f"{len(check_result.skipped_other)} deferred/dropped, "
                    f"{len(check_result.manual)} to apply manually"
                )
                for plan in check_result.to_create:
                    click.echo(f"  would create {plan.candidate_id} ({plan.kind})")
                for candidate_id in check_result.skipped_applied:
                    click.echo(f"  already applied: {candidate_id}")
                for candidate_id in check_result.skipped_other:
                    click.echo(f"  skipped drop/defer: {candidate_id}")
                for candidate_id, kind in check_result.manual:
                    click.echo(f"  apply manually ({kind}): {candidate_id}")

            emit(output_format=output_format, payload=check_result.to_dict(), render_text=_render_check)
            return
        result = apply_report(Path.cwd(), from_value, model_id, date.today())
    except (ApplyValidationError, ApplyWriteBackError) as exc:
        raise click.ClickException(str(exc)) from exc

    def _render_result() -> None:
        click.echo(
            f"{len(result.created)} created, "
            f"{len(result.skipped_applied)} already applied, "
            f"{len(result.skipped_other)} deferred/dropped, "
            f"{len(result.manual)} to apply manually, "
            f"{len(result.failures)} failed"
        )
        for created in result.created:
            click.echo(f"  created {created.candidate_id} -> {created.entity_id} ({created.kind})")
        for candidate_id in result.skipped_applied:
            click.echo(f"  already applied: {candidate_id}")
        for candidate_id in result.skipped_other:
            click.echo(f"  skipped drop/defer: {candidate_id}")
        for candidate_id, kind in result.manual:
            click.echo(f"  apply manually ({kind}): {candidate_id}")
        for candidate_id, error in result.failures:
            click.echo(f"  FAILED {candidate_id}: {error}")
        for created in result.created:
            emit_entity_warnings(created.warnings)

    emit(output_format=output_format, payload=result.to_dict(), render_text=_render_result)

    if result.failures:
        raise SystemExit(1)


def _render_gap_result_text(result) -> None:
    counts = result.counts
    click.echo(
        f"{counts['entities']} applied entities inspected, "
        f"{counts['gaps']} gaps ({counts['errors']} errors, {counts['warnings']} warnings)"
    )
    for entity in result.entities:
        if not entity.gaps:
            continue
        label = entity.entity_id or "<missing applied_as>"
        kind = entity.kind or "unknown"
        click.echo("")
        click.echo(f"{entity.candidate_id} -> {label} ({kind})")
        for gap in entity.gaps:
            click.echo(f"  {gap.severity.upper()} {gap.code}: {gap.message}")
            click.echo(f"    next: {gap.suggested_action}")


@explore_ideas_group.command("gaps")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def explore_ideas_gaps(from_value: str, output_format: str) -> None:
    """Inspect applied exploration entities for deterministic follow-up gaps."""
    try:
        result = inspect_gaps_report(Path.cwd(), from_value)
    except ApplyValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    emit(output_format=output_format, payload=result.to_dict(), render_text=lambda: _render_gap_result_text(result))


@explore_ideas_group.command("resolve-anchors")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def explore_ideas_resolve_anchors(from_value: str, output_format: str) -> None:
    """Resolve report literature anchors against papers and references.bib."""
    try:
        result = resolve_anchors_report(Path.cwd(), from_value)
    except ApplyValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    def _render() -> None:
        counts = result.counts
        click.echo(
            f"{counts['resolved']} resolved, "
            f"{counts['already_resolved']} already resolved, "
            f"{counts['ambiguous']} ambiguous, "
            f"{counts['unresolved']} unresolved"
        )
        for row in result.anchors:
            label = f"{row.candidate_id}[{row.anchor_index}]"
            if row.status == "resolved":
                click.echo(f"  {label} -> {row.resolved} ({row.match_kind})")
            elif row.status == "already-resolved":
                click.echo(f"  {label} already resolved: {row.resolved}")
            elif row.status == "ambiguous":
                click.echo(f"  {label} ambiguous {row.match_kind}: {', '.join(row.candidates)}")
            else:
                click.echo(f"  {label} unresolved: {row.query}")

    emit(output_format=output_format, payload=result.to_dict(), render_text=_render)


@explore_ideas_group.command("backfill-lens-views")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
def explore_ideas_backfill_lens_views(from_value: str) -> None:
    """Backfill lens_views onto entities from a prior applied report."""
    try:
        touched = backfill_lens_views(Path.cwd(), from_value, date.today())
    except (ApplyValidationError, ApplyWriteBackError) as exc:
        raise click.ClickException(str(exc)) from exc
    for entity_id, n in touched:
        click.echo(f"  {entity_id}: +{n} lens_view(s)")
    click.echo(f"backfilled {sum(n for _, n in touched)} view(s) across {len(touched)} entit(ies)")


@main.group("belief")
def belief_group() -> None:
    """Derived belief scalar and append-only snapshots."""


@belief_group.command("snapshot")
@click.option(
    "--path",
    "graph_path",
    default=str(DEFAULT_GRAPH_PATH),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option("--as-of", "as_of", default=None, help="Snapshot date YYYY-MM-DD (default: today).")
def belief_snapshot_cmd(graph_path: Path, as_of: str | None) -> None:
    """Append per-claim belief snapshots to knowledge/belief-snapshots.jsonl."""
    from .graph.io import project_root_from_graph_path

    as_of_value = as_of or date.today().isoformat()
    records = belief_snapshot.make_snapshots(graph_path, as_of=as_of_value)
    out_path = project_root_from_graph_path(graph_path) / "knowledge" / "belief-snapshots.jsonl"
    added = belief_snapshot.append_snapshots(out_path, records)
    click.echo(f"belief snapshot {as_of_value}: {len(records)} claims, {added} new rows -> {out_path}")


def _belief_profile_table_row(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row["evidence"]
    caps = row["caps"]
    cap_labels = [name for name, active in caps.items() if active]
    return {
        "entity": row["entity"],
        "kind": row["kind"],
        "belief_state": row["belief_state"],
        "contested": "yes" if row["contested"] else "no",
        "labels": ", ".join(row["epistemic_labels"]) or "-",
        "support": evidence["support_count"],
        "dispute": evidence["dispute_count"],
        "diagnostic": "-" if evidence["diagnostic_count"] is None else evidence["diagnostic_count"],
        "sources": evidence["source_count"],
        "empirical": "yes" if evidence["has_empirical_data"] else "no",
        "caps": ", ".join(cap_labels) or "-",
        "freshness": row["freshness_state"] or "-",
        "label": row["label"],
    }


@belief_group.command("profile")
@click.option(
    "--path",
    "graph_path",
    default=str(DEFAULT_GRAPH_PATH),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
@click.option(
    "--kind",
    "kinds",
    multiple=True,
    type=click.Choice(belief_profile.SUPPORTED_KINDS),
    help="Entity kind filter; repeatable.",
)
@click.option(
    "--label",
    "labels",
    multiple=True,
    type=click.Choice(belief_profile.PROFILE_LABELS),
    help="Epistemic label filter; repeatable with AND semantics.",
)
@click.option("--all", "include_all", is_flag=True, help="Include every supported belief-bearing entity.")
def belief_profile_cmd(
    graph_path: Path,
    output_format: str,
    kinds: tuple[str, ...],
    labels: tuple[str, ...],
    include_all: bool,
) -> None:
    """List derived epistemic profiles for belief-bearing entities."""
    rows = belief_profile.make_profiles(
        graph_path,
        include_all=include_all,
        kinds=kinds,
        labels=labels,
    )
    emit_rows = rows if output_format == "json" else [_belief_profile_table_row(row) for row in rows]
    emit_query_rows(
        output_format=output_format,
        title="Belief Profile",
        columns=[
            ("entity", "Entity"),
            ("kind", "Kind"),
            ("belief_state", "Belief"),
            ("contested", "Contested"),
            ("labels", "Labels"),
            ("support", "Support"),
            ("dispute", "Dispute"),
            ("diagnostic", "Diagnostic"),
            ("sources", "Sources"),
            ("empirical", "Empirical"),
            ("caps", "Caps"),
            ("freshness", "Freshness"),
            ("label", "Label"),
        ],
        rows=emit_rows,
        meta={
            "count": len(rows),
            "include_all": include_all,
            "kinds": list(kinds),
            "labels": list(labels),
        },
    )


@main.group()
def inquiry() -> None:
    """Inquiry subgraph commands."""


def _retired_mutator(slug: str) -> click.ClickException:
    return click.ClickException(
        f"Inquiry graph mutation is retired. Edit entities/patches/{slug}.md and run `science graph build`."
    )


def _retired_writer(command: str, forward_path: str) -> click.ClickException:
    return click.ClickException(f"{command} is retired. {forward_path}, then run `science graph build`.")


def _ref_from_uri(value: str) -> str:
    """Best-effort reverse of entity_uri_for_ref for the import bridge."""
    from science_tool.graph.io import PROJECT_NS

    if not isinstance(value, str) or not value:
        return value or ""
    if value.startswith(str(PROJECT_NS)):
        local = value[len(str(PROJECT_NS)) :]
        if "/" in local:
            kind, slug = local.split("/", 1)
            return f"{kind}:{slug}"
    return value


def _local_predicate(value: str) -> str:
    """Map a flow-edge predicate URI back to the authored short name."""
    for short in ("feedsInto", "produces", "causes"):
        if value.endswith(short):
            return short
    return value.rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def _render_inquiry_source(
    slug: str,
    *,
    title: str,
    focal_ref: str,
    profile: str,
    status: str,
    project: str = "",
    boundary_roles: list[tuple[str, str]] | None = None,  # (ref, "BoundaryIn"|"BoundaryOut")
    flow_edges: list[tuple[str, str, str, list[str]]] | None = None,  # (subject_ref, predicate, object_ref, claim_refs)
    treatment_ref: str | None = None,
    outcome_ref: str | None = None,
) -> str:
    import yaml

    inquiry: dict = {"profile": profile, "status": status}
    boundary_roles = boundary_roles or []
    flow_edges = flow_edges or []
    inquiry["boundary_roles"] = [{"ref": r, "role": role} for r, role in boundary_roles]
    inquiry["flow_edges"] = [
        {"subject": s, "predicate": p, "object": o, "claim_refs": list(claims)} for s, p, o, claims in flow_edges
    ]
    inquiry["assumptions"] = []
    inquiry["transformations"] = []
    if profile == "causal":
        inquiry["treatment"] = treatment_ref or ""
        inquiry["outcome"] = outcome_ref or ""

    frontmatter = {
        "id": f"patch-definition:{slug}",
        "type": "patch-definition",
        "title": title,
        "status": "active",
        # The build loader normally injects these base-Entity fields; we author
        # them here so the scaffold is directly model-valid (the `import` bridge
        # validates it via `PatchDefinitionEntity(**fm)` without the loader).
        "project": project,
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": title,
        "file_path": f"entities/patches/{slug}.md",
        "focal": focal_ref,
        "scope_set": [{"scope": "local"}],
        "neighborhood_policy": {"name": "local-closure-v1", "version": "local-closure-v1", "max_depth": 2},
        "patch_type": "inquiry",
        "inquiry": inquiry,
    }
    body = f"# Inquiry: {title}\n\n<!-- Edit the `inquiry:` block above, then run `science graph build`. -->\n"
    return "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n" + body


@inquiry.command("init")
@click.argument("slug")
@click.option("--label", required=True)
@click.option("--target", required=True, help="Focal hypothesis or question (e.g. hypothesis:h01)")
@click.option("--profile", required=True, type=click.Choice(["investigation", "causal"]))
@click.option(
    "--status", default="sketch", type=click.Choice(["sketch", "specified", "planned", "in-progress", "complete"])
)
@click.option("--treatment", default=None, help="Treatment ref (required for --profile causal)")
@click.option("--outcome", default=None, help="Outcome ref (required for --profile causal)")
@click.option("--project-root", "project_root", default=".", type=click.Path(path_type=Path, file_okay=False))
def inquiry_init(slug, label, target, profile, status, treatment, outcome, project_root):
    """Scaffold an inquiry patch-definition source file (does not write the graph)."""
    if profile == "causal" and (not treatment or not outcome):
        raise click.ClickException("causal profile requires --treatment and --outcome")
    dest = Path(project_root) / "entities" / "patches" / f"{slug}.md"
    if dest.exists():
        raise click.ClickException(f"{dest} already exists")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        _render_inquiry_source(
            slug,
            title=label,
            focal_ref=target,
            profile=profile,
            status=status,
            project=(Path(project_root).resolve().name or "project"),
            treatment_ref=treatment,
            outcome_ref=outcome,
        ),
        encoding="utf-8",
    )
    click.echo(f"Scaffolded {dest}")


@inquiry.command("import")
@click.argument("slug")
@click.option("--project-root", "project_root", default=".", type=click.Path(path_type=Path, file_okay=False))
@click.option("--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), type=click.Path(path_type=Path))
@click.option("--force", is_flag=True, help="Overwrite an existing source file")
def inquiry_import(slug, project_root, graph_path, force):
    """Bridge: write a patch-definition source from an existing graph inquiry."""
    import yaml
    from science_model.patch_definition import PatchDefinitionEntity

    from science_tool.graph.store.inquiry import get_inquiry

    dest = Path(project_root) / "entities" / "patches" / f"{slug}.md"
    if dest.exists() and not force:
        raise click.ClickException(f"{dest} exists; pass --force to overwrite")

    info = get_inquiry(graph_path, slug)
    profile = "causal" if info.get("inquiry_type") == "causal" else "investigation"
    boundary = [(_ref_from_uri(u), "BoundaryIn") for u in info.get("boundary_in", [])]
    boundary += [(_ref_from_uri(u), "BoundaryOut") for u in info.get("boundary_out", [])]
    flows = [
        (
            _ref_from_uri(e["subject"]),
            _local_predicate(e["predicate"]),
            _ref_from_uri(e["object"]),
            [_ref_from_uri(c) for c in e.get("claims", [])],
        )
        for e in info.get("edges", [])
    ]
    treatment = info.get("treatment")
    outcome = info.get("outcome")
    text = _render_inquiry_source(
        slug,
        title=info.get("label") or slug,
        focal_ref=_ref_from_uri(info.get("target") or ""),
        profile=profile,
        status=info.get("status") or "sketch",
        project=(Path(project_root).resolve().name or "project"),
        boundary_roles=boundary,
        flow_edges=flows,
        treatment_ref=_ref_from_uri(treatment) if isinstance(treatment, str) and treatment else None,
        outcome_ref=_ref_from_uri(outcome) if isinstance(outcome, str) and outcome else None,
    )
    PatchDefinitionEntity(**yaml.safe_load(text.split("---")[1]))  # fail loudly on invalid bridge output
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    click.echo(f"Imported inquiry/{slug} -> {dest}")


@inquiry.command("add-node")
@click.argument("slug")
@click.argument("entity")
@click.option("--role", required=False, type=click.Choice(["BoundaryIn", "BoundaryOut"]), default=None)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_node(slug: str, entity: str, role: str | None, graph_path: Path) -> None:
    """Add a node to an inquiry, optionally with a boundary role."""
    raise _retired_mutator(slug)


@inquiry.command("add-edge")
@click.argument("slug")
@click.argument("subject")
@click.argument("predicate")
@click.argument("object", metavar="OBJECT")
@click.option("--claim", "claim_refs", multiple=True, help="Supporting proposition reference (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_edge(
    slug: str,
    subject: str,
    predicate: str,
    object: str,
    claim_refs: tuple[str, ...],
    graph_path: Path,
) -> None:
    """Add an edge within an inquiry subgraph."""
    raise _retired_mutator(slug)


@inquiry.command("add-assumption")
@click.argument("slug")
@click.argument("label")
@click.option("--source", required=True, help="Evidence source (e.g. paper:doi_...)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_assumption(slug: str, label: str, source: str, graph_path: Path) -> None:
    """Add an assumption to an inquiry with provenance."""
    raise _retired_mutator(slug)


@inquiry.command("add-transformation")
@click.argument("slug")
@click.argument("label")
@click.option("--tool", default="", help="Tool or library name")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_transformation(slug: str, label: str, tool: str, graph_path: Path) -> None:
    """Add a transformation step to an inquiry."""
    raise _retired_mutator(slug)


@inquiry.command("set-estimand")
@click.argument("slug")
@click.option("--treatment", required=True, help="Treatment variable (e.g. concept/drug)")
@click.option("--outcome", required=True, help="Outcome variable (e.g. concept/recovery)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_set_estimand(slug: str, treatment: str, outcome: str, graph_path: Path) -> None:
    """Set treatment and outcome variables for a causal inquiry."""
    raise _retired_mutator(slug)


@inquiry.command("list")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_list(output_format: str, graph_path: Path) -> None:
    """List all inquiries."""
    rows = list_inquiries(graph_path)
    if not rows:
        if output_format == "json":
            click.echo("[]")
        else:
            click.echo("No inquiries found.")
        return
    emit_query_rows(
        output_format=output_format,
        title="Inquiries",
        columns=[
            ("slug", "Slug"),
            ("label", "Label"),
            ("inquiry_type", "Type"),
            ("status", "Status"),
            ("target", "Target"),
            ("created", "Created"),
        ],
        rows=rows,
    )


@inquiry.command("show")
@click.argument("slug")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_show(slug: str, output_format: str, graph_path: Path) -> None:
    """Show details of an inquiry."""
    try:
        info = get_inquiry(graph_path, slug)
    except ValueError as e:
        raise click.ClickException(str(e))

    def _render() -> None:
        click.echo(f"Inquiry: {info['label']}")
        click.echo(f"  Slug: {info['slug']}")
        click.echo(f"  Type: {info['inquiry_type']}")
        click.echo(f"  Status: {info['status']}")
        click.echo(f"  Target: {info['target']}")
        click.echo(f"  Created: {info['created']}")
        if info.get("description"):
            click.echo(f"  Description: {info['description']}")
        related = info.get("related") or []
        if related:
            click.echo(f"  Related: {len(related)} entit{'y' if len(related) == 1 else 'ies'}")
            for n in related:
                click.echo(f"    - {shorten_uri(n)}")
        click.echo(f"  Boundary In: {len(info['boundary_in'])} node(s)")
        for n in info["boundary_in"]:
            click.echo(f"    - {shorten_uri(n)}")
        click.echo(f"  Boundary Out: {len(info['boundary_out'])} node(s)")
        for n in info["boundary_out"]:
            click.echo(f"    - {shorten_uri(n)}")
        click.echo(f"  Edges: {len(info['edges'])}")
        for edge in info["edges"]:
            line = f"    {shorten_uri(edge['subject'])} --[{shorten_uri(edge['predicate'])}]--> {shorten_uri(edge['object'])}"
            claims = edge.get("claims")
            if claims:
                claims = ", ".join(shorten_uri(claim) for claim in claims)
                line = f"{line} [{claims}]"
            click.echo(line)

    emit(output_format=output_format, payload=info, render_text=_render, default=str)


@inquiry.command("validate")
@click.argument("slug")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_validate(slug: str, output_format: str, graph_path: Path) -> None:
    """Validate an inquiry subgraph."""
    try:
        results = validate_inquiry(graph_path, slug)
    except ValueError as e:
        raise click.ClickException(str(e))

    def _render() -> None:
        for r in results:
            icon = "PASS" if r["status"] == "pass" else "FAIL" if r["status"] == "fail" else "WARN"
            click.echo(f"  [{icon}] {r['check']}: {r['message']}")

    emit(output_format=output_format, payload=results, render_text=_render)

    if any(r["status"] == "fail" for r in results):
        raise click.exceptions.Exit(1)


@inquiry.command("export-pgmpy")
@click.argument("slug")
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_export_pgmpy(slug: str, output_path: Path | None, graph_path: Path) -> None:
    """Export a causal inquiry as a pgmpy scaffold script."""
    try:
        script = export_pgmpy_script(graph_path, slug)
    except ValueError as e:
        raise click.ClickException(str(e))

    if output_path:
        output_path.write_text(script, encoding="utf-8")
        click.echo(f"Wrote pgmpy script to {output_path}")
    else:
        click.echo(script)


@inquiry.command("export-chirho")
@click.argument("slug")
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_export_chirho(slug: str, output_path: Path | None, graph_path: Path) -> None:
    """Export a causal inquiry as a ChiRho/Pyro scaffold script."""
    try:
        script = export_chirho_script(graph_path, slug)
    except ValueError as e:
        raise click.ClickException(str(e))

    if output_path:
        output_path.write_text(script, encoding="utf-8")
        click.echo(f"Wrote ChiRho script to {output_path}")
    else:
        click.echo(script)


@main.group()
def datasets() -> None:
    """Dataset discovery and download commands."""


@datasets.command("sources")
def datasets_sources() -> None:
    """List available dataset adapters."""
    adapters = available_adapters()
    if not adapters:
        click.echo("No dataset adapters available. Install with: uv add science[datasets]")
        return
    click.echo("Available dataset sources:")
    for name in adapters:
        click.echo(f"  - {name}")


@datasets.command("search")
@click.argument("query")
@click.option("--source", default=None, help="Comma-separated list of sources (e.g. zenodo,geo)")
@click.option("--max", "max_results", default=20, show_default=True, help="Max results per source")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_search(query: str, source: str | None, max_results: int, output_format: str) -> None:
    """Search for datasets across repositories."""
    sources = source.split(",") if source else None
    results = search_all(
        query,
        sources=sources,
        max_per_source=max_results,
        on_error=lambda name, exc: click.echo(f"Warning: source {name!r} unavailable: {exc}", err=True),
    )
    if not results:
        click.echo("No datasets found.")
        return

    rows = [
        {
            "source": r.source,
            "id": r.id,
            "title": r.title[:80],
            "year": r.year or "",
            "access": r.access or "",
            "modality": r.modality or "",
            "organism": r.organism or "",
            "sample_count": r.sample_count or "",
            "doi": r.doi or "",
        }
        for r in results
    ]

    emit_query_rows(
        output_format=output_format,
        title=f"Dataset Search: {query}",
        columns=[
            ("source", "Source"),
            ("id", "ID"),
            ("title", "Title", {"no_wrap": True}),
            ("year", "Year"),
            ("access", "Access"),
            ("modality", "Modality"),
            ("organism", "Organism"),
            ("doi", "DOI"),
        ],
        rows=rows,
    )


@datasets.command("metadata")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_metadata(source_id: str, output_format: str) -> None:
    """Show full metadata for a dataset. Use SOURCE:ID format (e.g. zenodo:12345)."""
    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345 or geo:GSE12345")
    adapter = get_adapter(source)
    result = adapter.metadata(dataset_id)

    rows = [
        {"field": "Source", "value": result.source},
        {"field": "ID", "value": result.id},
        {"field": "Title", "value": result.title},
        {"field": "Description", "value": result.description[:200] if result.description else ""},
        {"field": "DOI", "value": result.doi or ""},
        {"field": "URL", "value": result.url or ""},
        {"field": "Year", "value": str(result.year) if result.year else ""},
        {"field": "License", "value": result.license or ""},
        {"field": "Access", "value": result.access or ""},
        {"field": "Keywords", "value": ", ".join(result.keywords) if result.keywords else ""},
        {"field": "Organism", "value": result.organism or ""},
        {"field": "Modality", "value": result.modality or ""},
        {"field": "Samples", "value": str(result.sample_count) if result.sample_count else ""},
        {"field": "Files", "value": str(result.file_count) if result.file_count else ""},
    ]

    emit_query_rows(
        output_format=output_format,
        title=f"Dataset: {result.title}",
        columns=[("field", "Field"), ("value", "Value")],
        rows=rows,
    )


@datasets.command("files")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_files(source_id: str, output_format: str) -> None:
    """List downloadable files in a dataset. Use SOURCE:ID format."""
    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345")
    adapter = get_adapter(source)
    file_list = adapter.files(dataset_id)
    if not file_list:
        click.echo("No files found.")
        return

    rows = [
        {
            "filename": f.filename,
            "format": f.format or "",
            "size": _human_size(f.size_bytes) if f.size_bytes else "",
            "checksum": (f.checksum[:30] + "...") if f.checksum and len(f.checksum) > 30 else (f.checksum or ""),
        }
        for f in file_list
    ]

    emit_query_rows(
        output_format=output_format,
        title="Files",
        columns=[("filename", "Filename"), ("format", "Format"), ("size", "Size"), ("checksum", "Checksum")],
        rows=rows,
    )



def _resolve_cli_data_root(project_root: Path | None) -> Path:
    try:
        return resolve_data_root(discover_project_root(project_root))
    except DataRootConfigError as exc:
        raise click.ClickException(str(exc)) from exc


@datasets.command("download")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--file", "file_pattern", default=None, help="Download only files matching this pattern")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Project root for resolving the configured data root.",
)
@click.option("--dest", "dest_dir", default=None, show_default="resolved data root / raw", type=click.Path(path_type=Path))
def datasets_download(source_id: str, file_pattern: str | None, project_root: Path | None, dest_dir: Path | None) -> None:
    """Download dataset files. Use SOURCE:ID format."""
    import fnmatch

    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345")
    if dest_dir is None:
        dest_dir = _resolve_cli_data_root(project_root) / "raw"
    adapter = get_adapter(source)
    file_list = adapter.files(dataset_id)
    if not file_list:
        click.echo("No files found.")
        return

    if file_pattern:
        file_list = [f for f in file_list if fnmatch.fnmatch(f.filename, file_pattern)]
        if not file_list:
            click.echo(f"No files matching pattern: {file_pattern}")
            return

    for fi in file_list:
        click.echo(f"Downloading {fi.filename}...")
        path = adapter.download(fi, dest_dir)
        click.echo(f"  Saved to {path}")


@datasets.command("validate")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Project root for resolving the configured data root.",
)
@click.option("--path", "data_path", default=None, show_default="resolved data root", type=click.Path(path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_validate(project_root: Path | None, data_path: Path | None, output_format: str) -> None:
    """Validate Frictionless Data Packages in raw/ and processed/ directories."""
    if data_path is None:
        data_path = _resolve_cli_data_root(project_root)
    results = validate_path(data_path)
    emit_query_rows(
        output_format=output_format,
        title="Data Validation",
        columns=[("check", "Check"), ("status", "Status"), ("details", "Details")],
        rows=results,
    )
    if any(r["status"] == "fail" for r in results):
        raise click.exceptions.Exit(1)


@datasets.command("qa")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--resource", "resource", default=None, help="Restrict QA to one resource (default: all tabular).")
@click.option(
    "--report-dir",
    "report_dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Persist qa_report.{json,md} (+ per-resource subdirs). Default: print only.",
)
@click.option(
    "--config",
    "runknobs",
    default=None,
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="Optional operational run-knobs YAML overlaid on the schema-derived config.",
)
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True)
@click.option("--no-strict", is_flag=True, default=False, help="Suppress the build-fatal exit 1 (local inspection).")
def datasets_qa(
    path: Path,
    resource: str | None,
    report_dir: Path | None,
    runknobs: Path | None,
    output_format: str,
    no_strict: bool,
) -> None:
    """Run schema-driven QA over a datapackage's tabular resources (package-level).

    Exit codes: 0 ok · 1 structural flag fired (build-fatal; --no-strict forces 0) ·
    2 bad input (missing descriptor / unknown resource / unreadable data).
    """
    from science_qa.compile import CompileError
    from science_qa.runner import RunnerError, package_report_dict

    from science_tool.datasets import qa as _qa

    try:
        result, code = _qa.run_package_qa(
            path, resource=resource, report_dir=report_dir, runknobs=runknobs, no_strict=no_strict
        )
    except (CompileError, RunnerError, ValueError, FileNotFoundError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(2) from exc

    def _render() -> None:
        for outcome in result.outcomes:
            if outcome.status == "not-applicable":
                continue
            click.echo(_qa.render_resource_line(outcome))
        click.echo(_qa.render_package_summary(result))

    emit(output_format=output_format, payload=package_report_dict(result), render_text=_render, sort_keys=True)

    if code:
        raise click.exceptions.Exit(code)


@datasets.command("infer-schema")
@click.argument("datapackage", type=click.Path(path_type=Path))
@click.option("--resource", "resource", required=True, help="Resource name (or path) to infer.")
@click.option("--sample", default=10000, show_default=True, help="Max rows sampled for inference.")
@click.option("--write", "do_write", is_flag=True, help="Apply ONLY the safe names+types patch in place.")
@click.option(
    "--emit-suggestions",
    "suggestions_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Write the review report to this YAML file (never mutates the descriptor).",
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_infer_schema(
    datapackage: Path,
    resource: str,
    sample: int,
    do_write: bool,
    suggestions_path: Path | None,
    output_format: str,
) -> None:
    """Infer a resource's observed shape (field names + coarse types) from its table.

    Read-only by default (prints a diff vs the existing schema + a review report). With
    --write, applies ONLY the safe names+types patch; it never infers constraints, keys,
    foreignKeys, or qa: those are recommended in the report and authored by hand. Writes
    are canonical (the descriptor is re-rendered in its own format; formatting/comments are
    not preserved).
    """
    try:
        result = _infer_schema.infer_schema_result(datapackage, resource, sample)
    except _infer_schema.InferSchemaError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(_infer_schema.result_to_json(result), nl=False)
    else:
        emit_query_rows(
            output_format=output_format,
            title="Proposed schema (names + types only)",
            columns=[("glyph", ""), ("action", "Action"), ("field", "Field"), ("details", "Details")],
            rows=_infer_schema.render_diff_rows(result.diff),
        )
        emit_query_rows(
            output_format=output_format,
            title="Review recommendations (NOT applied — author by hand)",
            columns=[("kind", "Kind"), ("column", "Column"), ("note", "Note"), ("label", "Label")],
            rows=_infer_schema.render_report_rows(result.report),
        )

    if suggestions_path is not None:
        suggestions_path.write_text(_infer_schema.report_to_yaml(result.report), encoding="utf-8")
        click.echo(f"Wrote review report to {suggestions_path}")

    if do_write:
        try:
            _infer_schema.write_patch(result)
        except _infer_schema.InferSchemaError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Applied names+types patch to {result.descriptor_path}")


@datasets.command("hydrate-worktree")
@click.option("--project-root", default=".", show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--source-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Checkout that already has ignored local data directories. Defaults to auto-detecting another git worktree.",
)
@click.option("--dry-run", is_flag=True, help="Report actions without creating symlinks.")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_hydrate_worktree(
    project_root: Path,
    source_root: Path | None,
    dry_run: bool,
    output_format: str,
) -> None:
    """Symlink ignored data directories from another checkout into this worktree."""
    try:
        actions = hydrate_worktree_data(project_root=project_root, source_root=source_root, dry_run=dry_run)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    rows = [
        {
            "path": action.relative_path.as_posix(),
            "status": action.status,
            "source": str(action.source),
            "target": str(action.target),
            "details": action.details,
        }
        for action in actions
    ]
    emit_query_rows(
        output_format=output_format,
        title="Data Worktree Hydration",
        columns=[
            ("path", "Path"),
            ("status", "Status"),
            ("source", "Source"),
            ("target", "Target"),
            ("details", "Details"),
        ],
        rows=rows,
    )
    if all(action.status == "missing-source" for action in actions):
        raise click.exceptions.Exit(1)


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


DEFAULT_TASKS_DIR = Path("tasks")


@main.group()
def tasks() -> None:
    """Task management commands."""


@tasks.command("add")
@click.argument("title")
@click.option("--priority", required=True, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--aspects", "aspects", multiple=True)
@click.option("--related", multiple=True)
@click.option("--blocked-by", multiple=True)
@click.option("--group", default="")
@click.option("--description", default="")
@click.option("--force", is_flag=True, help="Record blockers even if entity not yet known")
def tasks_add(
    title: str,
    priority: str,
    aspects: tuple[str, ...],
    related: tuple[str, ...],
    blocked_by: tuple[str, ...],
    group: str,
    description: str,
    force: bool,
) -> None:
    """Add a new task."""
    from science_tool.tasks import TaskAspectValidationError, add_task, validate_task_aspects
    from science_tool.tasks_blockers import BlockerValidationError

    validated_aspects: list[str] = []
    if aspects:
        try:
            validated_aspects = validate_task_aspects(list(aspects))
        except TaskAspectValidationError as exc:
            raise click.ClickException(str(exc)) from exc

    try:
        task = add_task(
            project_root=Path.cwd(),
            tasks_dir=DEFAULT_TASKS_DIR,
            title=title,
            priority=priority,
            aspects=validated_aspects or None,
            related=list(related) or None,
            blocked_by=list(blocked_by) or None,
            group=group,
            description=description,
            force=force,
        )
    except BlockerValidationError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created [{task.id}] {task.title}")


def _warn_dangling_task_refs(tasks_dir: Path) -> None:
    """Post-write self-check: surface any blocked-by/parent task ref that no
    longer resolves, so a dropped sibling is caught here rather than at graph build."""
    from science_tool.tasks import find_dangling_task_refs

    dangling = find_dangling_task_refs(tasks_dir)
    if not dangling:
        return
    for task_id, refs in sorted(dangling.items()):
        click.echo(
            f"WARNING: task {task_id} references unresolved task(s): {', '.join(refs)}",
            err=True,
        )


@tasks.command("done")
@click.argument("task_id")
@click.option("--note", default=None)
def tasks_done(task_id: str, note: str | None) -> None:
    """Mark a task as done."""
    from science_tool.tasks import complete_task

    try:
        task = complete_task(DEFAULT_TASKS_DIR, task_id, note=note)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] marked done")
    _warn_dangling_task_refs(DEFAULT_TASKS_DIR)


@tasks.command("defer")
@click.argument("task_id")
@click.option("--reason", default=None)
def tasks_defer(task_id: str, reason: str | None) -> None:
    """Defer a task."""
    from science_tool.tasks import defer_task

    try:
        task = defer_task(DEFAULT_TASKS_DIR, task_id, reason=reason)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] deferred")


@tasks.command("retire")
@click.argument("task_id")
@click.option("--reason", default=None)
def tasks_retire(task_id: str, reason: str | None) -> None:
    """Retire a task (closed without completion — no longer a priority)."""
    from science_tool.tasks import retire_task

    try:
        task = retire_task(DEFAULT_TASKS_DIR, task_id, reason=reason)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] retired")
    _warn_dangling_task_refs(DEFAULT_TASKS_DIR)


@tasks.command("block")
@click.argument("task_id")
@click.option(
    "--by",
    "blocked_by",
    multiple=True,
    required=True,
    help="Typed blocker ref (repeatable): <kind>:<local-id> or <peer>:<kind>:<local-id>",
)
@click.option("--force", is_flag=True, help="Record blocker even if entity not yet known")
def tasks_block(task_id: str, blocked_by: tuple[str, ...], force: bool) -> None:
    """Block a task by one or more typed entity references."""
    from science_tool.tasks import block_task
    from science_tool.tasks_blockers import BlockerValidationError
    from science_tool.tasks_readiness import make_project_entity_lookup

    try:
        task = block_task(
            project_root=Path.cwd(),
            tasks_dir=DEFAULT_TASKS_DIR,
            task_id=task_id,
            blocked_by=list(blocked_by),
            force=force,
        )
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    except BlockerValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if force:
        try:
            lookup = cast(Callable[[str], object | None], make_project_entity_lookup(Path.cwd()))
        except ValueError:
            lookup = _missing_project_entity_lookup

        for ref in blocked_by:
            if lookup(ref) is None:
                click.echo(
                    f"WARNING: recorded unresolved blocker {ref}; graph audit will flag it",
                    err=True,
                )

    refs = ", ".join(task.blocked_by)
    click.echo(f"[{task.id}] blocked by {refs}")


def _missing_project_entity_lookup(_ref: str) -> object | None:
    return None


@tasks.command("blockers")
@click.argument("task_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def tasks_blockers(task_id: str, fmt: str) -> None:
    """Show per-blocker readiness for a task."""
    from science_tool.tasks import _find_task, _read_active
    from science_tool.tasks_readiness import make_project_resolver

    tasks = _read_active(DEFAULT_TASKS_DIR)
    try:
        task = _find_task(tasks, task_id)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        resolver = make_project_resolver()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    rows = []
    for ref in task.blocked_by:
        readiness = resolver.resolve_ref(ref)
        rows.append(
            {
                "ref": ref,
                "ready": readiness.ready,
                "state": readiness.state,
                "detail": readiness.detail,
                "unresolved": readiness.state == "unresolved",
            }
        )

    def _render() -> None:
        click.echo(f"Blockers for [{task.id}] {task.title}:")
        for row in rows:
            marker = "✓" if row["ready"] else "·"
            line = f"  {marker} {row['ref']:40s}  {row['state']}"
            if row["detail"]:
                line += f"  ({row['detail']})"
            click.echo(line)

    emit(output_format=fmt, payload={"task_id": task.id, "blockers": rows}, render_text=_render)


@tasks.command("fix-blockers")
@click.option("--dry-run", is_flag=True, help="List legacy untyped blockers without modifying any files")
def tasks_fix_blockers(dry_run: bool) -> None:
    """Interactive sweep to retype legacy untyped blockers."""
    from science_tool.tasks import (
        _write_active,
        parse_tasks_for_cli,
    )
    from science_tool.tasks_blockers import is_typed_ref

    tasks_path = DEFAULT_TASKS_DIR / "active.md"
    tasks_, warnings = parse_tasks_for_cli(tasks_path)
    if not warnings:
        click.echo("No legacy untyped blockers found.")
        return

    if dry_run:
        click.echo("Legacy untyped blockers (dry-run):")
        for w in warnings:
            click.echo(f"  {w}")
        return

    changed = False
    for task in tasks_:
        new_blockers: list[str] = []
        for ref in task.blocked_by:
            if is_typed_ref(ref):
                new_blockers.append(ref)
                continue
            click.echo(f"\nTask [{task.id}] {task.title}")
            click.echo(f"  legacy blocker: {ref!r}")
            replacement = click.prompt(
                "  replace with (typed ref, or empty to drop, or '!' to keep as-is)",
                default="",
                show_default=False,
            ).strip()
            if replacement == "!":
                new_blockers.append(ref)
            elif replacement == "":
                changed = True  # drop
            else:
                if not is_typed_ref(replacement):
                    click.echo(f"  ! {replacement!r} not a typed ref; keeping original")
                    new_blockers.append(ref)
                else:
                    new_blockers.append(replacement)
                    changed = True
        task.blocked_by = new_blockers

    if changed and click.confirm("\nWrite changes to tasks/active.md?", default=True):
        _write_active(DEFAULT_TASKS_DIR, tasks_)
        click.echo("Updated.")
    else:
        click.echo("No changes written.")


@tasks.command("unblock")
@click.argument("task_id")
def tasks_unblock(task_id: str) -> None:
    """Unblock a task."""
    from science_tool.tasks import unblock_task

    try:
        task = unblock_task(DEFAULT_TASKS_DIR, task_id)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] unblocked → active")


@tasks.command("archive")
@click.option("--apply", "do_apply", is_flag=True, help="Write changes to disk (default is dry-run).")
@click.option(
    "--check",
    is_flag=True,
    help="Print archivable counts and exit non-zero when lag is present (used by science health).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
@click.option(
    "--tasks-dir",
    default=DEFAULT_TASKS_DIR,
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def tasks_archive(do_apply: bool, check: bool, output_format: str, tasks_dir: Path) -> None:
    """Move done/retired tasks from active.md to done/YYYY-MM.md.

    Default is dry-run: prints the planned moves without touching disk.
    Pass --apply to perform the writes (idempotent on re-run).
    """
    from science_tool.tasks_archive import apply_archive, count_archivable, plan_archive

    if check:
        counts = count_archivable(tasks_dir)
        emit_query_rows(
            output_format=output_format,
            title="Tasks Archive Lag",
            columns=[("metric", "Metric"), ("count", "Count")],
            rows=[{"metric": k, "count": v} for k, v in counts.items()],
        )
        if any(counts.values()):
            ctx = click.get_current_context()
            ctx.exit(1)
        return

    plan = plan_archive(tasks_dir)

    rows: list[dict[str, Any]] = [
        {
            "id": entry.task.id,
            "status": entry.task.status,
            "destination": str(entry.destination),
            "missing_completed": entry.missing_completed,
        }
        for entry in plan.entries
    ]

    emit_query_rows(
        output_format=output_format,
        title="Tasks Archive Plan",
        columns=[
            ("id", "ID"),
            ("status", "Status"),
            ("destination", "Destination"),
            ("missing_completed", "Missing completed:"),
        ],
        rows=rows,
    )

    for entry in plan.entries:
        if entry.missing_completed:
            click.echo(
                f"WARNING: [{entry.task.id}] has no `completed:` date; "
                f"routed to current month {entry.destination.name}",
                err=True,
            )

    for parse_error in plan.parse_errors:
        click.echo(
            f"WARNING: parse error in {parse_error.heading!r}: {parse_error.message}",
            err=True,
        )

    if not do_apply:
        if output_format != "json":
            click.echo(f"Mode: dry-run — would move {len(plan.entries)} task(s)")
        return

    if plan.parse_errors:
        raise click.ClickException(f"Refusing to apply: {len(plan.parse_errors)} parse error(s) in active.md")

    result = apply_archive(plan)
    if output_format != "json":
        click.echo(
            f"Moved {len(result.moved)} task(s); "
            f"{len(result.skipped_duplicates)} duplicate(s) skipped; "
            f"wrote {len(result.destinations_written)} destination file(s)"
        )


@tasks.command("edit")
@click.argument("task_id")
@click.option("--title", default=None)
@click.option("--description", default=None)
@click.option("--priority", default=None, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--status", default=None)
@click.option("--aspects", "aspects", multiple=True)
@click.option("--related", multiple=True)
@click.option("--blocked-by", multiple=True)
@click.option(
    "--clear-blockers",
    is_flag=True,
    help="Drop all blocked-by refs (e.g. when remediating status drift). Cannot combine with --blocked-by.",
)
@click.option("--group", default=None)
@click.option("--force", is_flag=True, help="Record blockers even if entity not yet known")
def tasks_edit(
    task_id: str,
    title: str | None,
    description: str | None,
    priority: str | None,
    status: str | None,
    aspects: tuple[str, ...],
    related: tuple[str, ...],
    blocked_by: tuple[str, ...],
    clear_blockers: bool,
    group: str | None,
    force: bool,
) -> None:
    """Edit an existing task's fields."""
    from science_tool.tasks import TaskAspectValidationError, edit_task, validate_task_aspects
    from science_tool.tasks_blockers import BlockerValidationError

    if clear_blockers and blocked_by:
        raise click.ClickException("--clear-blockers cannot be combined with --blocked-by")

    validated_aspects: list[str] | None = None
    if aspects:
        try:
            validated_aspects = validate_task_aspects(list(aspects))
        except TaskAspectValidationError as exc:
            raise click.ClickException(str(exc)) from exc

    # None = leave blocked-by untouched; [] = clear it. --clear-blockers forces the
    # empty list so a stale blocker can be dropped without hand-editing active.md.
    blocked_by_arg: list[str] | None
    if clear_blockers:
        blocked_by_arg = []
    elif blocked_by:
        blocked_by_arg = list(blocked_by)
    else:
        blocked_by_arg = None

    try:
        task = edit_task(
            project_root=Path.cwd(),
            tasks_dir=DEFAULT_TASKS_DIR,
            task_id=task_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            aspects=validated_aspects,
            related=list(related) if related else None,
            blocked_by=blocked_by_arg,
            group=group,
            force=force,
        )
    except BlockerValidationError as e:
        raise click.ClickException(str(e)) from e
    except (KeyError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Edited [{task.id}] {task.title}")


@tasks.command("note")
@click.argument("task_id")
@click.argument("note")
@click.option("--date", "note_date_raw", default=None, help="Note date in YYYY-MM-DD format.")
def tasks_note(task_id: str, note: str, note_date_raw: str | None) -> None:
    """Append a dated note to a task."""
    from datetime import date

    from science_tool.tasks import append_task_note

    note_date = date.today()
    if note_date_raw is not None:
        try:
            note_date = date.fromisoformat(note_date_raw)
        except ValueError as exc:
            raise click.ClickException("Date must use YYYY-MM-DD") from exc

    try:
        task = append_task_note(DEFAULT_TASKS_DIR, task_id, note, note_date=note_date)
    except (KeyError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Added note to [{task.id}] ({note_date.isoformat()})")


@tasks.command("list")
@click.option("--priority", default=None, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option(
    "--status",
    default=None,
    type=click.Choice(["proposed", "active", "blocked", "deferred", "retired", "done"]),
)
@click.option("--related", default=None)
@click.option("--group", default=None, help="Filter by group (exact match)")
@click.option("--aspect", "aspects", multiple=True, help="Filter by aspect (repeatable)")
@click.option("--all", "show_all", is_flag=True, default=False, help="Include done and retired tasks")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def tasks_list(
    priority: str | None,
    status: str | None,
    related: str | None,
    group: str | None,
    aspects: tuple[str, ...],
    show_all: bool,
    output_format: str,
) -> None:
    """List tasks. Done/retired tasks are hidden by default; use --all or --status=done to include them."""
    from science_model.tasks import Task

    from science_tool.tasks import list_tasks, parse_tasks_for_cli
    from science_tool.tasks_display import render_tasks_table, sort_tasks
    from science_tool.tasks_readiness import make_project_resolver

    # Surface legacy-untyped-blocker warnings on stderr.
    _, warnings = parse_tasks_for_cli(DEFAULT_TASKS_DIR / "active.md")
    for w in warnings:
        click.echo(f"WARNING: {w}", err=True)

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
    matched = sort_tasks(matched)

    try:
        resolver = make_project_resolver()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        columns: list[tuple[str, str]] = [
            ("id", "ID"),
            ("title", "Title"),
            ("type", "Type"),
            ("priority", "Priority"),
            ("status", "Status"),
            ("group", "Group"),
            ("related", "Related"),
            ("created", "Created"),
        ]

        def _row_with_readiness(t: Task) -> dict:
            row: dict = {
                "id": t.id,
                "title": t.title,
                "type": t.type,
                "priority": t.priority,
                "status": t.status,
                "group": t.group,
                "related": ", ".join(t.related),
                "created": t.created.isoformat(),
            }
            if t.status == "blocked" and t.blocked_by:
                readiness_entries = []
                for ref in t.blocked_by:
                    r = resolver.resolve_ref(ref)
                    readiness_entries.append(
                        {
                            "ref": ref,
                            "ready": r.ready,
                            "state": r.state,
                            "detail": r.detail,
                            "unresolved": r.state == "unresolved",
                        }
                    )
                row["blocked_by_readiness"] = readiness_entries
            return row

        rows = [_row_with_readiness(t) for t in matched]
        # Total count of active-file tasks before any filtering, so callers can
        # tell whether they're looking at a curated view or the full list
        # (fb-2026-05-01-006).
        from science_tool.tasks import _read_active

        active_total = len(_read_active(DEFAULT_TASKS_DIR))
        applied_filters: dict[str, object] = {}
        if priority is not None:
            applied_filters["priority"] = priority
        if status is not None:
            applied_filters["status"] = status
        if related is not None:
            applied_filters["related"] = related
        if group is not None:
            applied_filters["group"] = group
        if aspects:
            applied_filters["aspects"] = list(aspects)
        if not show_all and status is None:
            applied_filters["exclude_status"] = ["done", "retired"]
        meta = {
            "active_total": active_total,
            "returned_count": len(rows),
            "sort_order": "status_rank,id",
            "applied_filters": applied_filters,
        }
        emit_query_rows(output_format=output_format, title="Tasks", columns=columns, rows=rows, meta=meta)
    else:
        render_tasks_table(matched, resolver=resolver)


@tasks.command("show")
@click.argument("task_id")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def tasks_show(task_id: str, output_format: str) -> None:
    """Show full details of a task."""
    from science_tool.tasks import find_task_location, render_task
    from science_tool.tasks_readiness import make_project_resolver

    try:
        location = find_task_location(DEFAULT_TASKS_DIR, task_id)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    task = location.task
    try:
        resolver = make_project_resolver() if task.blocked_by else None
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    readiness_rows = []
    if resolver is not None:
        for ref in task.blocked_by:
            readiness = resolver.resolve_ref(ref)
            readiness_rows.append(
                {
                    "ref": ref,
                    "state": readiness.state,
                    "ready": readiness.ready,
                    "detail": readiness.detail,
                }
            )

    payload = task.model_dump(mode="json")
    payload["blocked_by_readiness"] = readiness_rows

    def _render() -> None:
        click.echo(render_task(task))

        # Append a resolver-enriched readiness section. render_task() already
        # emitted the raw blocked-by line; suppression would require coupling
        # render_task to a resolver, but render_task is also the on-disk
        # serializer and must stay pure.
        if task.blocked_by:
            click.echo("\nBlocker readiness:")
            for readiness in readiness_rows:
                line = f"  - {readiness['ref']:40s}  {readiness['state']}"
                if readiness["detail"]:
                    line += f"  ({readiness['detail']})"
                click.echo(line)

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


@tasks.command("summary")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def tasks_summary(output_format: str) -> None:
    """Print summary counts by status, type, priority, and group."""
    from collections import Counter

    from science_tool.tasks import parse_tasks, warn_invalid_statuses

    active = parse_tasks(DEFAULT_TASKS_DIR / "active.md")
    if not active:
        emit(
            output_format=output_format,
            payload={"total": 0, "by_status": {}, "by_type": {}, "by_priority": {}, "by_group": {}},
            render_text=lambda: click.echo("No active tasks."),
        )
        return

    warn_invalid_statuses(active)

    by_status = Counter(t.status for t in active)
    by_type = Counter(t.type for t in active)
    by_priority = Counter(t.priority for t in active)
    by_group = Counter(t.group for t in active if t.group)

    def _render() -> None:
        click.echo(f"Total: {len(active)}")
        click.echo("By status:   " + ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items())))
        click.echo("By type:     " + ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items())))
        click.echo("By priority: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_priority.items())))
        if by_group:
            click.echo("By group:    " + ", ".join(f"{k}: {v}" for k, v in sorted(by_group.items())))

    emit(
        output_format=output_format,
        payload={
            "total": len(active),
            "by_status": dict(sorted(by_status.items())),
            "by_type": dict(sorted(by_type.items())),
            "by_priority": dict(sorted(by_priority.items())),
            "by_group": dict(sorted(by_group.items())),
        },
        render_text=_render,
        sort_keys=True,
    )


@main.group()
def project() -> None:
    """Project-level commands."""


project.add_command(_artifacts_group)


@project.command("topic-coverage")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root containing entities/topics/.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def project_topic_coverage(project_root: Path, output_format: str) -> None:
    """Report how much of entities/topics/ is curated (substantive vs. stub)."""
    from science_tool.topic_coverage import MalformedTopicError, compute_topic_coverage

    try:
        cov = compute_topic_coverage(project_root)
    except MalformedTopicError as exc:
        raise click.ClickException(str(exc)) from exc

    def _render() -> None:
        if cov.n_topics == 0:
            click.echo("topics: 0 (no topics)")
            return
        warn = "  ⚠ stub-dominated" if cov.stub_dominated else ""
        click.echo(
            f"topics: {cov.n_topics} (substantive {cov.n_substantive}, "
            f"stubs {cov.n_topics - cov.n_substantive}) — stub_ratio {cov.stub_ratio:.2f}{warn}"
        )
        if cov.stub_dominated:
            for r in cov.topics:
                if not r.substantive:
                    click.echo(f"  stub: {r.id}")

    emit(output_format=output_format, payload=cov.to_dict(), render_text=_render)


@project.command("resolve-refs")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root whose question/hypothesis index refs resolve against.",
)
@click.option(
    "--query",
    "queries",
    multiple=True,
    required=True,
    help="Ref to resolve (repeatable): an id, slug, or keyword/title fragment.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def project_resolve_refs(project_root: Path, queries: tuple[str, ...], output_format: str) -> None:
    """Resolve free-string refs to canonical entity ids (id-slug + title matching)."""
    from science_tool.resolve_refs import build_ref_index, load_index_rows

    index = build_ref_index(load_index_rows(project_root))
    results = [index.resolve(q) for q in queries]

    def _render() -> None:
        for r in results:
            if r.resolved is not None:
                click.echo(f"{r.query} -> {r.resolved} ({r.match_kind})")
            elif r.candidates:
                click.echo(f"{r.query} -> {r.match_kind}: {', '.join(r.candidates)}")
            else:
                click.echo(f"{r.query} -> unresolved")

    emit(output_format=output_format, payload=[r.to_dict() for r in results], render_text=_render)


@project.command("serialize")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root containing science.yaml.",
)
@click.option(
    "--out",
    "out_archive",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Output .tar.gz path (must be outside the project root).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Build despite data-audit boundary violations (audit only; "
    "never bypasses missing/untracked science.yaml or guard failures).",
)
def project_serialize(project_root: Path, out_archive: Path, force: bool) -> None:
    """Serialize the tracked project source into a deterministic, shareable bundle.

    Reproducibility, not a privacy scrubber: ships all git-tracked entities and
    results faithfully; restricted material must not be tracked.
    """
    from science_tool.project_package.serialize import SerializeError, serialize_project

    try:
        result = serialize_project(project_root, out_archive, force=force)
    except SerializeError as exc:
        raise click.ClickException(str(exc)) from exc
    suffix = " [forced]" if result.forced else ""
    click.echo(f"Serialized {result.file_count} file(s), {result.payload_count} payload(s){suffix} → {result.out_path}")


@project.command("verify")
@click.argument("bundle", type=click.Path(exists=False, dir_okay=False, path_type=Path))
@click.option(
    "--against",
    "against_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Compare the bundle to a live checkout (commit, source, payloads). Explicit only.",
)
@click.option(
    "--extract",
    "extract_to",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Materialize the bundle's source tree into this empty or new directory.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit a JSON verdict.")
@click.pass_context
def project_verify(
    ctx: click.Context,
    bundle: Path,
    against_root: Path | None,
    extract_to: Path | None,
    output_format: str,
    as_json: bool,
) -> None:
    """Verify a serialized project bundle."""
    from science_tool.project_package.verify import (
        BundleIntegrityError,
        VerifyError,
        verdict_json,
        verify_project,
    )

    emit_json = as_json or output_format == "json"

    try:
        result = verify_project(bundle, against=against_root, extract=extract_to)
    except BundleIntegrityError as exc:
        _emit_verify_error(emit_json, exit_code=2, status="integrity", message=str(exc))
        ctx.exit(2)
    except VerifyError as exc:
        _emit_verify_error(emit_json, exit_code=4, status="operational", message=str(exc))
        ctx.exit(4)

    def _render() -> None:
        _render_verify_human(result)
        for warning in result.warnings:
            click.echo(f"warning: {warning}", err=True)

    emit(
        output_format="json" if emit_json else output_format,
        payload=verdict_json(result),
        render_text=_render,
        sort_keys=True,
    )
    ctx.exit(result.exit_code)


def _emit_verify_error(as_json: bool, *, exit_code: int, status: str, message: str) -> None:
    emit(
        output_format="json" if as_json else "text",
        payload={"version": 1, "exit_code": exit_code, "status": status, "error": message},
        render_text=lambda: click.echo(f"error: {message}", err=True),
        sort_keys=True,
    )


def _render_verify_human(result: Any) -> None:
    click.echo(f"  OK schema {result.bundle_schema_version}")
    click.echo(f"  OK {result.file_count} file(s) match manifest hashes")
    click.echo(f"  OK data_version {result.data_version} recomputes")
    if result.extracted_to is not None:
        click.echo(f"  OK extracted -> {result.extracted_to}")

    against = result.against
    if against is not None:
        click.echo(f"\n  against: {against.root}")
        mark = "OK" if against.commit.match else "DIFFER"
        click.echo(f"    commit:   {against.commit.bundle[:8]} vs {against.commit.head[:8]}  {mark}")
        click.echo(
            f"    source:   {against.source.match}/{against.source.total} match"
            f"  (differ {len(against.source.differ)}, absent {len(against.source.absent)})"
        )
        click.echo(
            f"    payloads: {against.payloads.ok} ok, {len(against.payloads.differ)} differ, "
            f"{len(against.payloads.missing)} missing, {len(against.payloads.extra)} extra"
        )
        for path in against.payloads.missing:
            click.echo(f"              MISSING: {path}")
        for path in against.payloads.differ:
            click.echo(f"              DIFFER:  {path}")

    click.echo(f"\n  status: {result.status} (exit {result.exit_code})")


@project.command("index")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def project_index(output_format: str, project_root: Path) -> None:
    """Produce a compact index of questions and hypotheses for this project."""
    project_root = project_root.resolve()

    # Resolve entities through the canonical project-sources loader.
    rows: list[dict[str, str]] = []
    for kind in ("hypothesis", "question"):
        for entity in list_entities(project_root, kind=kind):
            rows.append(
                {
                    "kind": str(entity["kind"]),
                    "id": str(entity["id"]),
                    "file": str(entity["path"]),
                    "title": str(entity["title"]),
                    "status": str(entity["status"]),
                }
            )

    emit_query_rows(
        output_format=output_format,
        title="Project Index",
        columns=[
            ("kind", "Kind"),
            ("id", "ID"),
            ("file", "File"),
            ("title", "Title"),
            ("status", "Status"),
        ],
        rows=rows,
    )


@main.command("health")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "--format",
    "output_format",
    default="table",
    show_default=True,
    type=click.Choice(["table", "json"]),
)
@click.option(
    "--timings",
    is_flag=True,
    help="Include per-check timing diagnostics.",
)
@click.option(
    "--fast",
    is_flag=True,
    help="Run only health checks that do not require loading project sources.",
)
@click.option(
    "--check",
    "checks",
    multiple=True,
    help="Run only the named health check. May be passed multiple times.",
)
@click.option(
    "--skip",
    "skip_checks",
    multiple=True,
    help="Skip the named health check. May be passed multiple times.",
)
@click.option(
    "--list-checks",
    is_flag=True,
    help="List available health checks and exit.",
)
def health_command(
    project_root: Path,
    output_format: str,
    timings: bool,
    fast: bool,
    checks: tuple[str, ...],
    skip_checks: tuple[str, ...],
    list_checks: bool,
) -> None:
    """Aggregate diagnostics for the project: unresolved refs, lingering tags, etc."""
    from rich.table import Table

    from science_tool.graph.health import build_health_report, list_health_checks
    from science_tool.styles import get_console

    project_root = project_root.resolve()
    if list_checks:
        available_checks = list_health_checks()

        def _render_checks() -> None:
            table = Table(title="Health checks")
            table.add_column("Name", style="bold")
            table.add_column("Requires sources")
            table.add_column("Description")
            for row in available_checks:
                table.add_row(str(row["name"]), "yes" if row["requires_sources"] else "no", str(row["description"]))
            get_console().print(table)

        emit(output_format=output_format, payload={"checks": available_checks}, render_text=_render_checks)
        return

    try:
        if timings or fast or checks or skip_checks:
            report = build_health_report(
                project_root,
                collect_timings=timings,
                checks=frozenset(checks) or None,
                skip_checks=frozenset(skip_checks) or None,
                fast=fast,
            )
        else:
            report = build_health_report(project_root)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    def _render_report() -> None:
        if timings:
            meta = report.get("_meta") or {}
            timing_rows = meta.get("timings") or []
            total_duration = meta.get("total_duration_seconds")
            click.echo("Health timings:", err=True)
            for row in timing_rows:
                click.echo(f"  {row['name']}: {row['duration_seconds']:.3f}s", err=True)
            if isinstance(total_duration, int | float):
                click.echo(f"  total: {total_duration:.3f}s", err=True)

        layered_claims = report["layered_claims"]
        layered_claim_issue_count = len(layered_claims["migration_issues"]) + len(
            layered_claims["rival_model_packets_missing_discriminating_predictions"]
        )
        coverage_gaps = 0
        for metric in (
            layered_claims["proposition_claim_layer_coverage"],
            layered_claims["causal_leaning_identification_coverage"],
        ):
            if metric["denominator"] > 0 and metric["numerator"] < metric["denominator"]:
                coverage_gaps += 1

        archive_lag = report["archive_lag"]
        archive_lag_total = (
            archive_lag["done_in_active"] + archive_lag["retired_in_active"] + archive_lag["missing_completed"]
        )

        managed_artifacts = report.get("managed_artifacts") or []
        managed_artifacts_issue_count = sum(1 for f in managed_artifacts if f.get("counts_as_issue"))

        tooling_scaffold = report.get("tooling_scaffold") or []
        agent_context = report.get("agent_context") or []
        unregistered_ref_kinds = report.get("unregistered_ref_kinds") or []
        entity_identity = report.get("entity_identity") or []
        schema_invalid = report.get("schema_invalid") or []
        validation = report.get("validation") or []
        accepted_validation = report.get("accepted_validation") or []
        prose_epistemics = report.get("prose_epistemics") or {}
        raw_prose_epistemics_findings = prose_epistemics.get("findings") if isinstance(prose_epistemics, dict) else None
        prose_epistemics_findings: list[dict[str, object]] = (
            [cast("dict[str, object]", row) for row in raw_prose_epistemics_findings if isinstance(row, dict)]
            if isinstance(raw_prose_epistemics_findings, list)
            else []
        )
        cross_paper_evidence = report.get("cross_paper_evidence") or {}
        raw_cross_paper_findings = cross_paper_evidence.get("findings") if isinstance(cross_paper_evidence, dict) else None
        cross_paper_findings: list[dict[str, object]] = (
            [cast("dict[str, object]", row) for row in raw_cross_paper_findings if isinstance(row, dict)]
            if isinstance(raw_cross_paper_findings, list)
            else []
        )

        total_issues = (
            len(report["unresolved_refs"])
            + len(unregistered_ref_kinds)
            + len(report["lingering_tags_lines"])
            + len(report["identity_policy"])
            + len(entity_identity)
            + layered_claim_issue_count
            + coverage_gaps
            + len(report.get("dataset_anomalies") or [])
            + len(schema_invalid)
            + (1 if archive_lag_total else 0)
            + managed_artifacts_issue_count
            + len(tooling_scaffold)
            + len(agent_context)
            + len(validation)
            + sum(1 for f in prose_epistemics_findings if f.get("counts_as_issue") is True)
            + len(cross_paper_findings)
        )
        if total_issues == 0:
            click.echo("Project is clean — no issues found.")
            if accepted_validation:
                click.echo(f"Accepted validation warnings: {len(accepted_validation)}")
            return

        console = get_console()

        if archive_lag_total:
            lag_table = Table(title="Tasks Archive Lag")
            lag_table.add_column("Metric", style="bold")
            lag_table.add_column("Count", justify="right")
            for key in ("done_in_active", "retired_in_active", "missing_completed"):
                lag_table.add_row(key, str(archive_lag[key]))
            console.print(lag_table)
            console.print(
                "\n[bold]Next:[/bold] run [cyan]science tasks archive[/cyan] to preview, then [cyan]--apply[/cyan]."
            )

        flagged_managed_artifacts = [f for f in managed_artifacts if f.get("counts_as_issue")]
        if flagged_managed_artifacts:
            ma_table = Table(title=f"Managed artifacts ({len(flagged_managed_artifacts)})")
            ma_table.add_column("Name", style="bold")
            ma_table.add_column("Status")
            ma_table.add_column("Detail")
            for row in flagged_managed_artifacts:
                ma_table.add_row(row["name"], row["status"], row["detail"])
            console.print(ma_table)
            console.print(
                "\n[bold]Next:[/bold] run "
                "[cyan]science project artifacts check[/cyan] / "
                "[cyan]update[/cyan] / [cyan]install[/cyan] per status."
            )

        if tooling_scaffold:
            ts_table = Table(title=f"Tooling scaffold ({len(tooling_scaffold)})")
            ts_table.add_column("Code", style="bold")
            ts_table.add_column("Detail")
            ts_table.add_column("Fix")
            for row in tooling_scaffold:
                ts_table.add_row(row["code"], row["detail"], row["fix"])
            console.print(ts_table)
            console.print(
                "\n[bold]Next:[/bold] follow the suggested fix for each row — "
                "see [cyan]commands/create-project.md[/cyan] for the canonical scaffold."
            )

        if agent_context:
            ac_table = Table(title=f"Agent context ({len(agent_context)})")
            ac_table.add_column("Code", style="bold")
            ac_table.add_column("File")
            ac_table.add_column("Detail")
            ac_table.add_column("Fix")
            for row in agent_context:
                ac_table.add_row(row["code"], row["source_file"], row["detail"], row["fix"])
            console.print(ac_table)
            console.print(
                "\n[bold]Next:[/bold] keep [cyan]CLAUDE.md[/cyan] minimal, remove [cyan]@core/*[/cyan] "
                "includes, and keep [cyan]core/overview.md[/cyan] as concise boot context."
            )

        if schema_invalid:
            si_table = Table(title=f"Schema-invalid entities ({len(schema_invalid)})")
            si_table.add_column("Kind", style="bold")
            si_table.add_column("Path")
            si_table.add_column("Detail")
            for row in schema_invalid:
                si_table.add_row(row["kind"], row["path"], row["message"])
            console.print(si_table)
            console.print(
                "\n[bold]Next:[/bold] fix each entity's frontmatter to satisfy its schema "
                "(these are excluded from the graph until repaired); rerun "
                "[cyan]science validate[/cyan] for the authoritative error."
            )

        if prose_epistemics_findings:
            prose_epistemics_next = "science annotate build-prose-health --write"
            pe_table = Table(title=f"Prose Epistemics ({len(prose_epistemics_findings)})")
            pe_table.add_column("Code", style="bold")
            pe_table.add_column("Source")
            pe_table.add_column("Detail")
            for row in prose_epistemics_findings:
                pe_table.add_row(
                    str(row.get("code", "")),
                    str(row.get("source_ref") or ""),
                    f"{row.get('message', '')}\nNext action: {prose_epistemics_next}",
                )
            console.print(pe_table)
            console.print(f"\n[bold]Next:[/bold] run [cyan]{prose_epistemics_next}[/cyan].")

        if cross_paper_findings:
            cpe_table = Table(title=f"Cross-paper evidence ({len(cross_paper_findings)})")
            cpe_table.add_column("Reason", style="bold", no_wrap=True)
            cpe_table.add_column("Sidecar", overflow="fold")
            cpe_table.add_column("Annotation", no_wrap=True)
            cpe_table.add_column("Detail", overflow="fold")
            for row in cross_paper_findings:
                sidecar = str(row.get("sidecar", ""))
                if sidecar:
                    try:
                        sidecar = str(Path(sidecar).resolve().relative_to(project_root))
                    except ValueError:
                        pass
                reason = str(row.get("reason", ""))
                annotation = str(row.get("annotation", ""))
                detail = str(row.get("detail", ""))
                cpe_table.add_row(
                    reason,
                    sidecar,
                    annotation,
                    detail,
                )
            console.print(cpe_table)
            console.print("\n[bold]Next:[/bold] fix stale promoted_to refs or proposition source_refs, then rerun health.")

        if report["unresolved_refs"]:
            table = Table(title=f"Unresolved references ({len(report['unresolved_refs'])})")
            table.add_column("Target", style="bold")
            table.add_column("Mentions", justify="right")
            table.add_column("Suggested triage")
            table.add_column("Sources (first 3)")
            for row in report["unresolved_refs"]:
                srcs = ", ".join(row["sources"][:3])
                if len(row["sources"]) > 3:
                    srcs += f", … (+{len(row['sources']) - 3})"
                table.add_row(row["target"], str(row["mention_count"]), row["looks_like"], srcs)
            console.print(table)

        if unregistered_ref_kinds:
            table = Table(title=f"Unregistered reference kinds ({len(unregistered_ref_kinds)})")
            table.add_column("Kind", style="bold")
            table.add_column("Field")
            table.add_column("Mentions", justify="right")
            table.add_column("Refs (first 3)")
            table.add_column("Sources (first 3)")
            for row in unregistered_ref_kinds:
                refs = ", ".join(row["refs"][:3])
                if len(row["refs"]) > 3:
                    refs += f", … (+{len(row['refs']) - 3})"
                srcs = ", ".join(row["sources"][:3])
                if len(row["sources"]) > 3:
                    srcs += f", … (+{len(row['sources']) - 3})"
                table.add_row(row["kind"], row["field"], str(row["mention_count"]), refs, srcs)
            console.print(table)
            console.print(
                "\n[bold]Next:[/bold] register these entity kinds in a profile, migrate the refs to "
                "registered kinds, or move non-entity annotations to [cyan]meta:*[/cyan]."
            )

        if report["lingering_tags_lines"]:
            with_values = [r for r in report["lingering_tags_lines"] if r["values"]]
            empty_count = len(report["lingering_tags_lines"]) - len(with_values)

            if with_values:
                title = f"Legacy `tags:` fields to migrate ({len(with_values)})"
                table = Table(title=title)
                table.add_column("File", style="bold")
                table.add_column("Values")
                for row in with_values:
                    table.add_row(row["file"], ", ".join(row["values"]))
                console.print(table)

            if empty_count:
                console.print(f"[dim]...and {empty_count} additional file(s) with empty `tags: []` (cosmetic only).[/dim]")

        if report["identity_policy"]:
            table = Table(title=f"Identity Policy ({len(report['identity_policy'])})")
            table.add_column("Check", style="bold")
            table.add_column("Entity")
            table.add_column("File")
            table.add_column("Message")
            for row in report["identity_policy"]:
                table.add_row(row["check"], row["entity_id"], row["source_file"], row["message"])
            console.print(table)

        if entity_identity:
            table = Table(title=f"Entity Identity ({len(entity_identity)})")
            table.add_column("Code", style="bold", no_wrap=True, min_width=26)
            table.add_column("Severity")
            table.add_column("Path", overflow="fold")
            table.add_column("Canonical ID", overflow="fold")
            table.add_column("Message", overflow="fold")
            for row in entity_identity:
                table.add_row(
                    row["code"],
                    row["severity"],
                    row.get("path") or "",
                    row.get("canonical_id") or "",
                    row["message"],
                )
            console.print(table)

        if validation:
            table = Table(title=f"Validation ({len(validation)})")
            table.add_column("Severity", style="bold")
            table.add_column("Path", overflow="fold")
            table.add_column("Rule")
            table.add_column("Task")
            table.add_column("Message", overflow="fold")
            for row in validation:
                path = row.get("path") or ""
                line = row.get("line")
                if line is not None:
                    path = f"{path}:{line}" if path else str(line)
                table.add_row(
                    row.get("severity", ""),
                    path,
                    row.get("rule") or "",
                    row.get("task") or "",
                    row.get("message", ""),
                )
            console.print(table)

        adoption_table = Table(title="Layered-Claim Adoption")
        adoption_table.add_column("Check", style="bold")
        adoption_table.add_column("Coverage", justify="right")
        adoption_table.add_column("Fraction", justify="right")
        for label, metric in (
            ("Propositions with authored claim_layer", layered_claims["proposition_claim_layer_coverage"]),
            (
                "Causal-leaning propositions with authored identification_strength",
                layered_claims["causal_leaning_identification_coverage"],
            ),
        ):
            adoption_table.add_row(
                label,
                f"{metric['numerator']}/{metric['denominator']}",
                f"{metric['fraction']:.2f}",
            )
        console.print(adoption_table)

        if layered_claims["migration_issues"]:
            issue_table = Table(title=f"Layered-Claim Migration Issues ({len(layered_claims['migration_issues'])})")
            issue_table.add_column("Proposition", style="bold")
            issue_table.add_column("Warnings")
            issue_table.add_column("TODOs")
            for row in layered_claims["migration_issues"]:
                issue_table.add_row(
                    row["proposition"],
                    "; ".join(row["warnings"]) or "-",
                    "; ".join(row["todos"]) or "-",
                )
            console.print(issue_table)

        if layered_claims["rival_model_packets_missing_discriminating_predictions"]:
            rival_table = Table(
                title=(
                    "Rival-model packets missing discriminating predictions "
                    f"({len(layered_claims['rival_model_packets_missing_discriminating_predictions'])})"
                )
            )
            rival_table.add_column("Proposition", style="bold")
            rival_table.add_column("Packet")
            for row in layered_claims["rival_model_packets_missing_discriminating_predictions"]:
                rival_table.add_row(row["proposition"], row["packet_id"])
            console.print(rival_table)

        dataset_anomalies = report.get("dataset_anomalies") or []
        if dataset_anomalies:
            ds_table = Table(title=f"Dataset Anomalies ({len(dataset_anomalies)})")
            ds_table.add_column("Code", style="bold")
            ds_table.add_column("Severity")
            ds_table.add_column("Entity")
            ds_table.add_column("Message")
            for row in dataset_anomalies:
                ds_table.add_row(
                    row.get("code", ""),
                    row.get("severity", ""),
                    row.get("entity_id", ""),
                    row.get("message", ""),
                )
            console.print(ds_table)

    emit(output_format=output_format, payload=report, render_text=_render_report)


@main.command("paper-fetch")
@click.option("--doi", default=None, help="DOI (bare, doi: prefix, or doi.org URL)")
@click.option(
    "--url",
    default=None,
    help="Landing-page URL: doi.org, PubMed, PMC, arXiv, or bioRxiv/medRxiv",
)
@click.option("--pmid", default=None, help="PubMed ID (resolved to DOI via Europe PMC)")
@click.option("--pmcid", default=None, help="PMC ID, e.g. PMC12345 (resolved to DOI via Europe PMC)")
@click.option("--arxiv", default=None, help="arXiv ID, e.g. 2502.09135 (constructs the 10.48550/arXiv.<id> DOI)")
@click.option(
    "--email",
    default=None,
    help="Contact email for polite-pool APIs (falls back to $SCIENCE_CONTACT_EMAIL)",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Override cache directory (defaults to $SCIENCE_CACHE_DIR or ~/.cache/science)",
)
def paper_fetch_cmd(
    doi: str | None,
    url: str | None,
    pmid: str | None,
    pmcid: str | None,
    arxiv: str | None,
    email: str | None,
    cache_dir: Path | None,
) -> None:
    """Probe agent-friendly sources for a paper and emit a JSON decision record.

    Intended for the paper-researcher subagent: call this first, branch on the
    ``status`` field, and only fall back to open-ended search when it reports
    status=not_found. A status of paywalled or blocked_but_oa means the caller
    should ask the user for a PDF rather than scavenge the web. A status of
    error indicates conflicting identifiers — see ``metadata.reason``.
    """
    import os as _os

    from science_tool.paper_fetch import FetchConfig, fetch_paper

    resolved_email = email or _os.environ.get("SCIENCE_CONTACT_EMAIL")
    if not resolved_email:
        raise click.ClickException("Contact email is required. Pass --email or set $SCIENCE_CONTACT_EMAIL.")
    cfg_kwargs: dict[str, Any] = {"email": resolved_email}
    if cache_dir is not None:
        cfg_kwargs["cache_dir"] = cache_dir
    cfg = FetchConfig(**cfg_kwargs)
    result = fetch_paper(doi=doi, url=url, pmid=pmid, pmcid=pmcid, arxiv=arxiv, cfg=cfg)
    emit(output_format="json", payload=result.to_dict(), render_text=lambda: None)


@main.group("paper")
def paper() -> None:
    """Paper-entity source-text commands."""


@paper.command("persist-source")
@click.argument("identifier")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False),
    help="Project root (defaults to the current directory).",
)
@click.option(
    "--email",
    default=None,
    help="Contact email for polite-pool APIs (falls back to $SCIENCE_CONTACT_EMAIL)",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Override cache directory (defaults to $SCIENCE_CACHE_DIR or ~/.cache/science)",
)
def persist_source_cmd(
    identifier: str,
    project_root: Path | None,
    email: str | None,
    cache_dir: Path | None,
) -> None:
    """Persist <citekey>.source.md (abstract always; full text when OA-licensed).

    Resolves a DOI or PMID to an existing paper entity, fetches the article text
    (PubTator3 BioC preferred, Europe PMC abstract fallback), license-gates
    full-text persistence, and writes the anchor surface next to the entity.
    """
    import os as _os

    from science_tool.annotation.source_text import SourceTextError, persist_source
    from science_tool.paper_fetch import FetchConfig

    resolved_email = email or _os.environ.get("SCIENCE_CONTACT_EMAIL")
    if not resolved_email:
        raise click.ClickException("Contact email is required. Pass --email or set $SCIENCE_CONTACT_EMAIL.")
    cfg_kwargs: dict[str, Any] = {"email": resolved_email}
    if cache_dir is not None:
        cfg_kwargs["cache_dir"] = cache_dir
    cfg = FetchConfig(**cfg_kwargs)
    root = (project_root or Path.cwd()).resolve()
    try:
        out = persist_source(project_root=root, identifier=identifier, cfg=cfg)
    except SourceTextError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Wrote {out}")


@main.group("questions")
def question() -> None:
    """Question-file management commands."""


@question.command("create")
@click.argument("title")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
@click.option(
    "--origin",
    "origins",
    multiple=True,
    help="Origin as TYPE[:REF][@DATE], e.g. user, literature:Smith2019@2019-03-01. Repeatable.",
)
@click.option("--added-by", "added_by", default=None, help="Discovery stamp (who surfaced this entity).")
def question_create(
    title: str,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
    origins: tuple[str, ...],
    added_by: str | None,
) -> None:
    """Create a source-authored question."""

    extra = build_origin_frontmatter(origins, added_by)

    create_typed_entity(
        kind="question",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=list(source_refs),
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
        extra_frontmatter=extra,
    )


@question.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def question_show(ref: str, output_format: str) -> None:
    """Show a source-authored question."""
    show_typed_entity("question", ref, output_format)


@question.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def question_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored questions."""
    list_typed_entities("question", status, related, output_format)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@question.command("reserve")
@click.option("--slug", required=True, help="Kebab-case slug for the question (will be normalized)")
@click.option("--title", default=None, help="Question title (used in frontmatter and H1)")
@click.option("--related", default=None, help="Comma-separated related entity IDs")
@click.option("--ontology", default=None, help="Comma-separated ontology terms")
@click.option("--source-refs", default=None, help="Comma-separated source refs, e.g. cite:Smith2024 or paper:Smith2024")
@click.option("--datasets", default=None, help="Comma-separated dataset IDs")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Project root; questions are written under entities/questions/.",
)
@click.option(
    "--questions-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Deprecated override: write to this directory verbatim instead of <root>/entities/questions.",
)
@click.option(
    "--template",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Override body template (file content used verbatim, with {title} substituted)",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
def question_reserve_cmd(
    slug: str,
    title: str | None,
    related: str | None,
    ontology: str | None,
    source_refs: str | None,
    datasets: str | None,
    project_root: Path,
    questions_dir: Path | None,
    template: Path | None,
    as_json: bool,
    output_format: str,
) -> None:
    """Atomically reserve the next question number and write a stub file.

    Writes ``entities/questions/NNNN-slug.md`` under the project root.
    Designed for parallel subagents: reservation locks on the NUMBER (via a
    per-number sentinel), so concurrent reserves with different slugs never
    collide on a number. Returns the assigned path so the caller can write
    the body without re-querying the directory.
    """
    from science_tool.questions import reserve_question

    template_body = template.read_text(encoding="utf-8") if template else None
    reservation = reserve_question(
        project_root,
        slug,
        title=title,
        related=_split_csv(related),
        ontology_terms=_split_csv(ontology),
        source_refs=_split_csv(source_refs),
        datasets=_split_csv(datasets),
        template_body=template_body,
        questions_dir=questions_dir,
    )

    def _render() -> None:
        click.echo(f"Reserved {reservation.id}")
        click.echo(f"  path: {reservation.path}")

    effective_format = "json" if (as_json or output_format == "json") else output_format
    emit(
        output_format=effective_format,
        payload={
            "id": reservation.id,
            "number": reservation.number,
            "padded": reservation.padded,
            "slug": reservation.slug,
            "path": str(reservation.path),
        },
        render_text=_render,
    )


@main.group()
def bib() -> None:
    """Project bibliography (papers/references.bib) commands."""


@bib.command("add")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Project root containing papers/references.bib.",
)
@click.option("--entry", "entry", default=None, help="BibTeX entry text (inline).")
@click.option(
    "--entry-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Read the BibTeX entry from this file.",
)
@click.option("--replace", is_flag=True, help="Replace the existing entry if the key is already present.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def bib_add(
    project_root: Path,
    entry: str | None,
    entry_file: Path | None,
    replace: bool,
    output_format: str,
    as_json: bool,
) -> None:
    """Atomically append a BibTeX entry to papers/references.bib.

    Reads the entry from --entry, --entry-file, or stdin (in that order). A
    locked open-read-write cycle avoids the Read→Edit mtime race the Edit tool
    hits under Dropbox sync, and serializes concurrent appends from parallel
    subagents. Idempotent by key; pass --replace to overwrite an existing entry.

    Example (subagent heredoc):

        uv run science bib add --project-root . <<'EOF'
        @article{Smith2024, title={...}, author={...}, year={2024}}
        EOF
    """
    from science_tool.bibliography import add_bib_entry

    if entry is not None:
        text = entry
    elif entry_file is not None:
        text = entry_file.read_text(encoding="utf-8")
    else:
        text = click.get_text_stream("stdin").read()
    if not text.strip():
        raise click.ClickException("No BibTeX entry provided (pass --entry, --entry-file, or pipe via stdin).")

    try:
        result = add_bib_entry(project_root, text, replace=replace)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    effective_format = "json" if (as_json or output_format == "json") else output_format
    emit(
        output_format=effective_format,
        payload={"key": result.key, "action": result.action, "path": str(result.path)},
        render_text=lambda: click.echo(f"{result.action}: {result.key} ({result.path})"),
        indent=None,
    )


@main.group()
def sync() -> None:
    """Cross-project sync commands."""


@sync.command("run")
@click.option("--config", "config_path", type=click.Path(), default=None)
@click.option("--dry-run", is_flag=True, help="Preview without writing changes")
def sync_run(config_path: str | None, dry_run: bool) -> None:
    """Run cross-project sync."""
    from science_tool.registry.config import get_default_config_path, load_global_config
    from science_tool.registry.index import get_default_registry_dir
    from science_tool.registry.state import get_default_state_path
    from science_tool.registry.sync import run_sync as do_sync

    cfg_path = Path(config_path) if config_path else get_default_config_path()
    config = load_global_config(cfg_path)
    if not config.projects:
        click.echo("No registered projects. Run science commands in project directories first.")
        return

    registry_dir = get_default_registry_dir()
    state_path = get_default_state_path()
    report = do_sync(
        project_paths=[Path(p.path) for p in config.projects],
        registry_dir=registry_dir,
        state_path=state_path,
        dry_run=dry_run,
    )
    prefix = "[dry run] " if dry_run else ""
    click.echo(f"{prefix}Sync complete.")
    click.echo(f"  Entities: {report.entities_total} (+{report.entities_new} new)")
    click.echo(f"  Relations: {report.relations_total}")
    if report.drift_warnings:
        click.echo("  Drift warnings:")
        for warning in report.drift_warnings:
            click.echo(f"    {warning}")


@sync.command("status")
@click.option("--config", "config_path", type=click.Path(), default=None)
def sync_status(config_path: str | None) -> None:
    """Show sync status and staleness."""
    from datetime import datetime

    from science_tool.registry.config import get_default_config_path, load_global_config
    from science_tool.registry.state import load_sync_state

    cfg_path = Path(config_path) if config_path else get_default_config_path()
    config = load_global_config(cfg_path)
    state_path = cfg_path.parent / "sync_state.yaml"
    state = load_sync_state(state_path)

    if state.last_sync is None:
        click.echo("No sync has been performed yet.")
        if config.projects:
            click.echo(f"  {len(config.projects)} registered project(s). Run `science sync run`.")
        return

    days = (datetime.now() - state.last_sync).days
    click.echo(f"Last sync: {state.last_sync.isoformat()} ({days} days ago)")
    stale_threshold = config.sync.stale_after_days
    if days > stale_threshold:
        click.echo(f"  Sync is stale (threshold: {stale_threshold} days). Run `science sync run`.")
    for name, pstate in state.projects.items():
        click.echo(f"  {name}: {pstate.entity_count} entities (hash: {pstate.entity_hash[:8]})")


@sync.command("projects")
@click.option("--config", "config_path", type=click.Path(), default=None)
def sync_projects(config_path: str | None) -> None:
    """List registered projects."""
    from science_tool.registry.config import get_default_config_path, load_global_config

    cfg_path = Path(config_path) if config_path else get_default_config_path()
    config = load_global_config(cfg_path)
    if not config.projects:
        click.echo("No registered projects.")
        return
    for p in config.projects:
        click.echo(f"  {p.name}: {p.path} (registered {p.registered})")


@sync.command("rebuild")
@click.option("--config", "config_path", type=click.Path(), default=None)
def sync_rebuild(config_path: str | None) -> None:
    """Rebuild registry from scratch by scanning all projects."""
    import shutil

    from science_tool.registry.config import get_default_config_path, load_global_config, prune_missing_projects
    from science_tool.registry.index import get_default_registry_dir
    from science_tool.registry.state import get_default_state_path
    from science_tool.registry.sync import run_sync as do_sync

    cfg_path = Path(config_path) if config_path else get_default_config_path()
    registry_dir = get_default_registry_dir()
    state_path = get_default_state_path()

    pruned = prune_missing_projects(cfg_path)
    for path in pruned:
        click.echo(f"Pruned missing project: {path}")

    config = load_global_config(cfg_path)
    if not config.projects:
        click.echo("No registered projects.")
        return

    if registry_dir.is_dir():
        shutil.rmtree(registry_dir)
    click.echo("Registry cleared. Rebuilding...")

    report = do_sync(
        project_paths=[Path(p.path) for p in config.projects],
        registry_dir=registry_dir,
        state_path=state_path,
    )
    click.echo(f"Rebuild complete. {report.entities_total} entities, {report.relations_total} relations.")


if __name__ == "__main__":
    main()

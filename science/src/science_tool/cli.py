from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import click
from rich.text import Text
from science_model.reasoning import MembershipRole

from science_tool.annotation.cli import annotate_group
from science_tool.big_picture.cli import big_picture_group
from science_tool.causal.export_chirho import export_chirho_script
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.commons import commons_group
from science_tool.curate.cli import curate_group
from science_tool.dag.cli import dag_group
from science_tool.data_worktree import hydrate_worktree_data
from science_tool.datasets import available_adapters, get_adapter, search_all
from science_tool.datasets import infer_schema as _infer_schema
from science_tool.datasets.validate import validate_path
from science_tool.distill.openalex import distill_openalex
from science_tool.distill.pykeen_source import distill_pykeen
from science_tool.doi import lookup_doi_metadata
from science_tool.entities import (
    EntityCommandError,
    EntityRemovalPlan,
    append_entity_note,
    create_entity,
    edit_entity,
    find_entity,
    graph_is_stale,
    list_entities,
    plan_entity_removal,
    remove_entity,
)
from science_tool.entities_inventory import build_inventory
from science_tool.entity_kinds import register_local_kind
from science_tool.entity_migrations import audit_identifiers
from science_tool.graph import belief_profile, belief_snapshot
from science_tool.graph.cross_impact import query_cross_impact
from science_tool.graph.materialize import materialization_audit, materialize_graph
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    GRAPH_LAYERS,
    PropositionEvidenceLine,
    PropositionInteractionTerm,
    add_article,
    add_concept,
    add_discussion,
    add_edge,
    add_evidence_edge,
    add_falsification,
    add_finding,
    add_hypothesis,
    add_interpretation,
    add_mechanism,
    add_observation,
    add_paper_entity,
    add_proposition,
    add_question,
    add_story,
    build_graph_dot,
    diff_graph_inputs,
    export_graph_payload,
    get_inquiry,
    import_snapshot,
    init_graph_file,
    list_inquiries,
    query_claims,
    query_coverage,
    query_dashboard_summary,
    query_evidence,
    query_gaps,
    query_inquiry_summary,
    query_neighborhood,
    query_neighborhood_summary,
    query_predicates,
    query_project_summary,
    query_question_summary,
    query_uncertainty,
    read_graph_stats,
    shorten_uri,
    stamp_revision,
    validate_graph,
    validate_inquiry,
)
from science_tool.markers_cli import markers_group
from science_tool.output import OUTPUT_FORMATS, emit_query_rows
from science_tool.patch.cli import patch_group
from science_tool.peers_cli import peers_group
from science_tool.project_artifacts.cli import artifacts_group as _artifacts_group
from science_tool.prose import scan_prose
from science_tool.prose_lint_cli import prose_group
from science_tool.qa_audit.cli import qa_audit_command
from science_tool.refs_cli import refs_group
from science_tool.research_package.cli import research_package_group
from science_tool.skills_lint import skills_group
from science_tool.styles import (
    COLOR_POLICY_CHOICES,
    entity_table_renderers,
    get_console,
    render_entity_kind,
    render_entity_ref,
    render_entity_status,
    render_muted,
    resolve_color_policy,
    set_color_policy,
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


@main.command("search")
@click.argument("query")
@click.option(
    "--archived",
    is_flag=True,
    default=False,
    help="Search the archive index (required; live search not yet implemented).",
)
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json", show_default=True)
def search_command(query: str, archived: bool, project_root: Path, output_format: str) -> None:
    """Search entities. P3 supports --archived only (reads the archive index)."""
    if not archived:
        raise click.UsageError(
            "science search currently supports only --archived (live entity search is not implemented)."
        )
    from science_tool.archive import search_archive

    hits = search_archive(project_root, query)
    if output_format == "json":
        click.echo(json.dumps(hits, indent=2, sort_keys=True))
    else:
        for h in hits:
            click.echo(f"{h['id']}  [{h['kind']}]  {h['title'] or ''}")


def _parse_dataset_effects(entries: tuple[str, ...]) -> dict[str, float] | None:
    if not entries:
        return None

    dataset_effects: dict[str, float] = {}
    for entry in entries:
        if "=" not in entry:
            raise click.ClickException(f"Dataset effect must be DATASET=VALUE, got '{entry}'")
        dataset, value = entry.split("=", 1)
        dataset_name = dataset.strip()
        if not dataset_name:
            raise click.ClickException(f"Dataset effect must include a dataset name, got '{entry}'")
        try:
            dataset_effects[dataset_name] = float(value.strip())
        except ValueError as exc:
            raise click.ClickException(f"Dataset effect value must be numeric, got '{entry}'") from exc
    return dataset_effects


def _parse_evidence_lines(entries: tuple[str, ...]) -> list[dict[str, object]] | None:
    if not entries:
        return None

    evidence_lines: list[dict[str, object]] = []
    for entry in entries:
        try:
            parsed = json.loads(entry)
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"Evidence line must be valid JSON, got '{entry}'") from exc
        if not isinstance(parsed, dict):
            raise click.ClickException("Evidence line JSON must decode to an object")
        if not isinstance(parsed.get("source"), str) or not parsed["source"].strip():
            raise click.ClickException("Evidence line JSON must include a non-empty 'source' string")
        if not isinstance(parsed.get("kind"), str) or not parsed["kind"].strip():
            raise click.ClickException("Evidence line JSON must include a non-empty 'kind' string")
        datasets = parsed.get("datasets", [])
        if not isinstance(datasets, list) or any(not isinstance(item, str) for item in datasets):
            raise click.ClickException("Evidence line JSON 'datasets' must be a list of strings")
        evidence_lines.append(
            {
                "source": parsed["source"],
                "kind": parsed["kind"],
                "datasets": datasets,
            }
        )
    return evidence_lines


def _parse_interaction_terms(entries: tuple[str, ...]) -> list[PropositionInteractionTerm] | None:
    if not entries:
        return None

    interaction_terms: list[PropositionInteractionTerm] = []
    for entry in entries:
        try:
            parsed = json.loads(entry)
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"Interaction term must be valid JSON, got '{entry}'") from exc
        if not isinstance(parsed, dict):
            raise click.ClickException("Interaction term JSON must decode to an object")
        modifier = parsed.get("modifier")
        effect = parsed.get("effect")
        if not isinstance(modifier, str) or not modifier.strip():
            raise click.ClickException("Interaction term JSON must include a non-empty 'modifier' string")
        if not isinstance(effect, str) or not effect.strip():
            raise click.ClickException("Interaction term JSON must include a non-empty 'effect' string")
        interaction_term: PropositionInteractionTerm = {
            "modifier": modifier,
            "effect": effect,
        }
        note = parsed.get("note")
        if isinstance(note, str) and note.strip():
            interaction_term["note"] = note
        interaction_terms.append(interaction_term)
    return interaction_terms


main.add_command(dag_group)
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


@main.group("entities")
def entities_group() -> None:
    """Inspect and audit Science entity inventories."""


@entities_group.command("inventory")
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
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
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
def entities_audit_identifiers_command(project_path: Path) -> None:
    click.echo(json.dumps(audit_identifiers(project_path), indent=2))


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
    click.echo(json.dumps(report, indent=2))


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
    click.echo(json.dumps(report, indent=2))


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
    click.echo(json.dumps(report, indent=2))


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
    click.echo(json.dumps(report, indent=2))


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
    click.echo(json.dumps(report, indent=2))


@entities_group.command("migrate")
@click.option("--apply", "apply_changes", is_flag=True, help="Apply the migration (default: dry run).")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
def entities_migrate_command(apply_changes: bool, project_root: Path) -> None:
    """Migrate a project's doc/specs entity layout into entities/ (v2 → v3)."""
    from science_tool.entity_layout_migration import migrate_layout

    try:
        report = migrate_layout(project_root, apply=apply_changes)
    except ValueError as exc:  # collisions / unresolved refs block --apply
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(report, indent=2))


@entities_group.command("triage-aggregate")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
@click.option("--promote-coined", is_flag=True, help="Promote `coined` rows to owner files.")
@click.option("--delete-cruft", is_flag=True, help="Delete `cruft` (migration:*) rows.")
@click.option("--delete-shadow", is_flag=True, help="Delete `shadow` rows (id already has a real owner).")
@click.option("--promote-decisions", is_flag=True, help="Promote `decision` rows backed by core/decisions.md.")
@click.option(
    "--retire-external-refs",
    is_flag=True,
    help="Delete `external-ref` (paper/article) rows backed by papers/references.bib.",
)
@click.option(
    "--migrate-curie-refs",
    is_flag=True,
    help="Migrate `curie-external-ref` rows into knowledge/sources/<profile>/external_refs.yaml, then drop them.",
)
@click.option("--apply", "apply_changes", is_flag=True, help="Execute the plan (default: dry-run).")
def entities_triage_aggregate_command(
    project_root: Path,
    output_format: str,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
    promote_decisions: bool,
    retire_external_refs: bool,
    migrate_curie_refs: bool,
    apply_changes: bool,
) -> None:
    """Triage (and, with bucket flags, retire) aggregate rows — multi-type (entities.yaml/terms.yaml) and single-type (doc/<plural>/<plural>.{yaml,json}, e.g. observations.yaml) (§B5)."""
    from collections import Counter

    from science_tool.bibliography import load_bib_entries
    from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
    from science_tool.graph.aggregate_triage import classify_aggregate_rows, inbound_reference_counts
    from science_tool.graph.decision_log import DecisionLogIndex, parse_decision_log
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root, include_commons=False, strict_core_schema=False, strict_identity=False)
    # The reference surface must be commons-INCLUSIVE: a commons entity can reference
    # a project-owned id, and deleting that local owner would dangle the commons ref.
    # Ownership/bucketing stays on the commons-exclusive `sources` above so commons
    # ownership does not perturb shadow/coined classification (design §B5).
    ref_sources = load_project_sources(
        project_root, include_commons=True, strict_core_schema=False, strict_identity=False
    )
    rows = classify_aggregate_rows(sources, inbound_ref_counts=inbound_reference_counts(ref_sources))
    any_bucket = (
        promote_coined
        or delete_cruft
        or delete_shadow
        or promote_decisions
        or retire_external_refs
        or migrate_curie_refs
    )

    # No bucket flags → the unchanged 3a read-only report.
    if not any_bucket:
        if apply_changes:
            raise click.UsageError(
                "--apply requires at least one of --promote-coined/--delete-cruft/--delete-shadow/"
                "--promote-decisions/--retire-external-refs/--migrate-curie-refs."
            )
        if output_format == "json":
            click.echo(
                json.dumps(
                    [
                        {
                            "canonical_id": r.canonical_id,
                            "kind": r.kind,
                            "source_path": r.source_path,
                            "has_real_owner": r.has_real_owner,
                            "bucket": r.bucket.value,
                            "evidence": r.evidence,
                        }
                        for r in rows
                    ],
                    indent=2,
                )
            )
            return
        counts = Counter(r.bucket.value for r in rows)
        click.echo(f"{len(rows)} aggregate rows:")
        for bucket in sorted(counts):
            click.echo(f"  {bucket}: {counts[bucket]}")
        for r in rows:
            click.echo(
                f"  [{r.bucket.value}] {r.canonical_id} (kind={r.kind}, source_path={r.source_path}) -- {r.evidence}"
            )
        return

    # Retirement plan/apply path. --apply is v3-gated.
    if apply_changes:
        import yaml as _yaml

        _manifest = _yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
        _v = _manifest.get("layout_version")
        version = _v if isinstance(_v, int) else None
        if version is None or version < 3:
            raise click.ClickException(
                f"promotion needs an `entities/` owner root, but this project is layout_version {version}. "
                "This Science version supports layout_version 3 only; the v2 layout is no longer supported."
            )

    decisions_path = project_root / "core" / "decisions.md"
    decision_index = (
        parse_decision_log(decisions_path.read_text(encoding="utf-8"))
        if promote_decisions and decisions_path.is_file()
        else DecisionLogIndex({})
    )
    bib_keys = frozenset(load_bib_entries(project_root)) if retire_external_refs else frozenset()
    plan = plan_retirement(
        project_root,
        sources,
        rows,
        promote_coined=promote_coined,
        delete_cruft=delete_cruft,
        delete_shadow=delete_shadow,
        promote_decisions=promote_decisions,
        retire_external_refs=retire_external_refs,
        bib_keys=bib_keys,
        decision_index=decision_index,
        migrate_curie_refs=migrate_curie_refs,
    )
    report = apply_retirement(project_root, plan, dry_run=not apply_changes, decision_index=decision_index)
    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "dry_run": report.dry_run,
                    "promoted": list(report.promoted),
                    "migrated": list(report.migrated),
                    "deleted": list(report.deleted),
                    "rejected": [list(p) for p in report.rejected],
                    "skipped": [list(p) for p in report.skipped],
                    "files_rewritten": list(report.files_rewritten),
                },
                indent=2,
            )
        )
        return
    head = "PLAN (dry-run)" if report.dry_run else "APPLIED"
    click.echo(
        f"{head}: {len(report.promoted)} promoted, {len(report.migrated)} migrated, "
        f"{len(report.deleted)} deleted, {len(report.rejected)} rejected, {len(report.skipped)} skipped"
    )
    for cid in report.promoted:
        click.echo(f"  promote {cid}")
    for cid in report.migrated:
        click.echo(f"  migrate {cid}")
    for cid in report.deleted:
        click.echo(f"  delete  {cid}")
    for cid, reason in (*report.rejected, *report.skipped):
        click.echo(f"  skip    {cid} -- {reason}")


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

    _manifest = _yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
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
@click.option("--project", "project_path", type=click.Path(path_type=Path), default=Path.cwd())
def entities_register_kind_command(kind: str, entity_class: str, project_path: Path) -> None:
    """Register a project-local entity kind in the local profile."""
    try:
        result = register_local_kind(project_path, kind, entity_class)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{kind}: {result}")


@main.group("entity")
def entity_group() -> None:
    """Create, edit, note, list, and inspect source-authored entities."""


@entity_group.command("create")
@click.argument("kind")
@click.argument("title")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--path", "explicit_path", type=click.Path(path_type=Path))
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def entity_create(
    kind: str,
    title: str,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    explicit_path: Path | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored entity markdown file."""

    try:
        result = create_entity(
            project_root=Path.cwd(),
            kind=kind,
            title=title,
            entity_id=entity_id,
            slug=slug,
            explicit_path=explicit_path,
            status=status,
            related=list(related_refs),
            source_refs=list(source_refs),
            with_sections=list(with_sections),
            without_sections=list(without_sections),
            no_hints=no_hints,
        )
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created {result.entity_id} at {result.path.relative_to(Path.cwd())}")
    _emit_entity_warnings(result.warnings)


@entity_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_show(ref: str, output_format: str) -> None:
    """Show a source-authored entity."""

    try:
        location = find_entity(Path.cwd(), ref)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    _emit_entity_show(location, output_format)


@entity_group.command("edit")
@click.argument("ref")
@click.option("--title")
@click.option("--status")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--updated")
def entity_edit(
    ref: str,
    title: str | None,
    status: str | None,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    updated: str | None,
) -> None:
    """Edit source-authored entity metadata."""

    try:
        result = edit_entity(
            Path.cwd(),
            ref,
            title=title,
            status=status,
            related=list(related_refs),
            source_refs=list(source_refs),
            updated=_parse_entity_date(updated) if updated else None,
        )
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Updated {result.entity_id} at {result.path.relative_to(Path.cwd())}")
    _emit_entity_warnings(result.warnings)


@entity_group.command("note")
@click.argument("ref")
@click.argument("note")
@click.option("--date", "note_date")
def entity_note(ref: str, note: str, note_date: str | None) -> None:
    """Append a dated note to a source-authored entity."""

    from datetime import date as _date

    try:
        date_value = _parse_entity_date(note_date) if note_date else None
        result = append_entity_note(Path.cwd(), ref, note, note_date=date_value)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    display_date = (date_value or _date.today()).isoformat()
    click.echo(f"Added note to {result.entity_id} ({display_date})")
    _emit_entity_warnings(result.warnings)


@entity_group.command("remove")
@click.argument("target")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Delete the entity and safe references.")
def entity_remove(target: str, apply_changes: bool) -> None:
    """Preview or remove an entity file and safely removable references."""

    try:
        plan = remove_entity(Path.cwd(), target) if apply_changes else plan_entity_removal(Path.cwd(), target)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    _emit_entity_removal_plan(plan, applied=apply_changes)


@entity_group.command("list")
@click.argument("kind_arg", required=False)
@click.option("--kind")
@click.option("--status")
@click.option("--related")
@click.option(
    "--include-hidden", is_flag=True, default=False, help="Include superseded/archived entities (hidden by default)."
)
@click.option(
    "--include-archived",
    is_flag=True,
    default=False,
    help="Include archived (relocated) entities from the archive index.",
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_list(
    kind_arg: str | None,
    kind: str | None,
    status: str | None,
    related: str | None,
    include_hidden: bool,
    include_archived: bool,
    output_format: str,
) -> None:
    """List source-authored entities."""

    if kind_arg is not None:
        if kind is not None and kind != kind_arg:
            raise click.ClickException(f"positional kind {kind_arg!r} conflicts with --kind {kind!r}")
        kind = kind_arg
    try:
        rows = list_entities(
            Path.cwd(),
            kind=kind,
            status=status,
            related=related,
            include_hidden=include_hidden,
            include_archived=include_archived,
        )
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    emit_query_rows(
        output_format=output_format,
        title="Entities",
        columns=[("id", "ID"), ("kind", "Kind"), ("status", "Status"), ("title", "Title"), ("path", "Path")],
        rows=rows,
        renderers=entity_table_renderers(),
    )


@entity_group.command("sections")
@click.argument("kind")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_sections(kind: str, output_format: str) -> None:
    """List template sections for a source-authored entity kind."""

    from science_model.templates import MIGRATED_KINDS, EntityTemplateError, Renderer

    if kind not in MIGRATED_KINDS:
        supported = ", ".join(sorted(MIGRATED_KINDS))
        raise click.ClickException(
            f"Kind '{kind}' has no inspectable section template. "
            f"Kinds with declared sections: {supported}. "
            "Other kinds are created with a fixed Summary/Notes body — use `science entity create` directly."
        )

    try:
        sections = Renderer().sections(kind)
    except EntityTemplateError as exc:
        raise click.ClickException(str(exc)) from exc
    rows = [
        {
            "key": section.key,
            "required": "required" if section.required else "optional",
            "name": section.name,
            "hint": section.hint[:80],
        }
        for section in sections
    ]
    emit_query_rows(
        output_format=output_format,
        title=f"{kind} Template Sections",
        columns=[("key", "KEY"), ("required", "REQ?"), ("name", "NAME"), ("hint", "HINT")],
        rows=rows,
    )


@entity_group.command("neighbors")
@click.argument("ref")
@click.option("--hops", type=int, default=2, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_neighbors(ref: str, hops: int, output_format: str) -> None:
    """Show graph neighbors for a source-authored entity."""

    try:
        location = find_entity(Path.cwd(), ref)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    if graph_is_stale(Path.cwd(), DEFAULT_GRAPH_PATH):
        click.echo("WARNING: graph materialization may be stale; results below could miss recent edits.", err=True)
    rows = query_neighborhood(
        graph_path=DEFAULT_GRAPH_PATH,
        center=location.entity_id,
        hops=hops,
        graph_layer="graph/knowledge",
        limit=200,
    )
    emit_query_rows(
        output_format=output_format,
        title="Entity Neighbors",
        columns=[("subject", "Subject"), ("predicate", "Predicate"), ("object", "Object")],
        rows=rows,
    )


@entity_group.command("review")
@click.argument("ref")
@click.option(
    "--note",
    default=None,
    help="Required review artifact: the finding, prose diff, created task, or a "
    "reasoned 'no change'. A review without a recorded artifact is rejected.",
)
def entity_review(ref: str, note: str | None) -> None:
    """Mark an epistemic entity as reviewed-as-of today.

    A review must record an artifact via --note; a bare timestamp bump is
    rejected to prevent review-theater (see epistemic-drift-detection design M1).
    """
    from science_tool.entity_review import ReviewError, review_entity

    try:
        path, changed = review_entity(Path.cwd(), ref, note=note, require_artifact=True)
    except ReviewError as exc:
        raise click.ClickException(str(exc)) from exc
    rel = path.relative_to(Path.cwd())
    if changed:
        click.echo(f"Reviewed {ref} -> {rel}")
    else:
        click.echo(f"Reviewed {ref} -> {rel} (no changes)")


@entity_group.command("needs-review")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
def entity_needs_review(output_format: str) -> None:
    """List epistemic entities flagged needs-review or stale by the materialized graph."""
    from science_tool.entity_review import list_needs_review
    from science_tool.output import emit_query_rows

    rows = list_needs_review(Path.cwd())
    emit_query_rows(
        output_format=output_format,
        title="Entities needing review",
        columns=[("state", "State"), ("kind", "Kind"), ("id", "ID")],
        rows=rows,
    )


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

    _create_typed_entity(
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
    _show_typed_entity("proposition", ref, output_format)


@proposition_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def proposition_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored propositions."""
    _list_typed_entities("proposition", status, related, output_format)


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
@click.option(
    "--dispute-scope",
    default=None,
    type=click.Choice(["whole_claim", "generalization", "mechanism", "boundary"]),
)
@click.option(
    "--evidence-role",
    default=None,
    type=click.Choice(
        ["direct_test", "proxy_support", "background_constraint", "negative_control", "model_criticism"]
    ),
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
    if dispute_scope:
        extra_frontmatter["dispute_scope"] = dispute_scope
    if evidence_role:
        extra_frontmatter["evidence_role"] = evidence_role

    _create_typed_entity(
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
    _show_typed_entity("evidence-line", ref, output_format)


@evidence_line_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def evidence_line_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored evidence lines."""
    _list_typed_entities("evidence-line", status, related, output_format)


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
) -> None:
    """Create a source-authored hypothesis."""

    sections = list(with_sections)
    if phase == "candidate" and "promotion-criteria" not in sections:
        sections.append("promotion-criteria")

    _create_typed_entity(
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
    )


@hypothesis_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def hypothesis_show(ref: str, output_format: str) -> None:
    """Show a source-authored hypothesis."""
    _show_typed_entity("hypothesis", ref, output_format)


@hypothesis_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def hypothesis_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored hypotheses."""
    _list_typed_entities("hypothesis", status, related, output_format)


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

    _create_typed_entity(
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
    _show_typed_entity("discussion", ref, output_format)


@discussion_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def discussion_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored discussions."""
    _list_typed_entities("discussion", status, related, output_format)


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

    _create_typed_entity(
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
    _show_typed_entity("interpretation", ref, output_format)


@interpretation_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def interpretation_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored interpretations."""
    _list_typed_entities("interpretation", status, related, output_format)


def _create_typed_entity(
    *,
    kind: str,
    title: str,
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    related: list[str],
    source_refs: list[str],
    phase: str | None = None,
    with_sections: list[str] | None = None,
    without_sections: list[str] | None = None,
    no_hints: bool = False,
    extra_frontmatter: dict[str, object] | None = None,
) -> None:
    try:
        result = create_entity(
            project_root=Path.cwd(),
            kind=kind,
            title=title,
            entity_id=entity_id,
            slug=slug,
            status=status,
            related=related,
            source_refs=source_refs,
            phase=phase,
            with_sections=with_sections,
            without_sections=without_sections,
            no_hints=no_hints,
            extra_frontmatter=extra_frontmatter,
        )
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created {result.entity_id} at {result.path.relative_to(Path.cwd())}")
    _emit_entity_warnings(result.warnings)


def _show_typed_entity(kind: str, ref: str, output_format: str) -> None:
    try:
        location = find_entity(Path.cwd(), ref)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    if location.kind != kind:
        raise click.ClickException(f"Expected {kind} entity, got {location.entity_id}")
    _emit_entity_show(location, output_format)


def _list_typed_entities(kind: str, status: str | None, related: str | None, output_format: str) -> None:
    try:
        rows = list_entities(Path.cwd(), kind=kind, status=status, related=related)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    emit_query_rows(
        output_format=output_format,
        title=_ENTITY_LIST_TITLES.get(kind, kind.replace("-", " ").title() + "s"),
        columns=[("id", "ID"), ("status", "Status"), ("title", "Title"), ("path", "Path")],
        rows=rows,
        renderers=entity_table_renderers(),
    )


_ENTITY_LIST_TITLES = {
    "discussion": "Discussions",
    "evidence-line": "Evidence Lines",
    "hypothesis": "Hypotheses",
    "interpretation": "Interpretations",
    "proposition": "Propositions",
    "question": "Questions",
}


def _entity_show_payload(location: Any) -> dict[str, object]:
    return {
        "id": location.entity_id,
        "kind": location.kind,
        "title": location.title,
        "status": location.status,
        "path": location.rel_path,
        "related": _frontmatter_string_list(location.frontmatter.get("related")),
        "source_refs": _frontmatter_string_list(location.frontmatter.get("source_refs")),
        "body": location.body,
    }


def _emit_entity_show(location: Any, output_format: str) -> None:
    payload = _entity_show_payload(location)
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    console = get_console(file=click.get_text_stream("stdout"))
    _print_entity_field(console, "id", render_entity_ref(str(payload["id"])))
    _print_entity_field(console, "type", render_entity_kind(str(payload["kind"])))
    _print_entity_field(console, "title", Text(str(payload["title"])))
    _print_entity_field(console, "status", render_entity_status(str(payload["status"])))
    _print_entity_field(console, "path", render_muted(payload["path"]))
    _print_entity_refs_field(console, "related", payload["related"])
    _print_entity_refs_field(console, "source_refs", payload["source_refs"])
    if location.body:
        click.echo()
        console.print(Text(location.body.rstrip("\n")))


def _emit_entity_removal_plan(plan: EntityRemovalPlan, *, applied: bool) -> None:
    action = "Removed" if applied else "DRY RUN"
    click.echo(f"{action} {plan.entity_id}")
    click.echo(f"- delete {plan.rel_path}")
    if plan.safe_hits:
        click.echo("- safe structured reference cleanup:")
        for hit in sorted(plan.safe_hits, key=lambda item: (item.rel_path, item.line, item.detail)):
            click.echo(f"  - {hit.rel_path}:{hit.line}: {hit.detail}")
    else:
        click.echo("- safe structured reference cleanup: none")
    if plan.manual_hits:
        click.echo("- manual references:")
        for hit in sorted(plan.manual_hits, key=lambda item: (item.rel_path, item.line, item.detail)):
            click.echo(f"  - {hit.rel_path}:{hit.line}: {hit.detail}")
    else:
        click.echo("- manual references: none")
    if not applied:
        click.echo("Run with --apply to delete the entity and rewrite safe structured references.")


def _print_entity_field(console: Any, label: str, value: Text) -> None:
    line = Text(f"{label}: ")
    line.append_text(value)
    console.print(line)


def _print_entity_refs_field(console: Any, label: str, refs: object) -> None:
    line = Text(f"{label}: ")
    if isinstance(refs, list):
        for index, ref in enumerate(refs):
            if index:
                line.append(", ")
            line.append_text(render_entity_ref(str(ref)))
    console.print(line)


def _emit_entity_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        click.echo(f"WARNING: {warning}")


def _frontmatter_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _parse_entity_date(value: str) -> Any:
    from datetime import date

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise click.ClickException(f"Invalid date: {value}") from exc


def _normalize_legacy_graph_source(source: str) -> str:
    if source.startswith("manual:"):
        return "source/" + source.split(":", 1)[1]
    return source


@main.group()
def graph() -> None:
    """Knowledge graph commands."""


@graph.command("init")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_init(graph_path: Path) -> None:
    """Initialize a project graph.trig with named graph layers."""

    init_graph_file(graph_path)
    click.echo(f"Initialized graph at {graph_path}")
    viz_path = graph_path.parent.parent / "code" / "notebooks" / "viz.py"
    if viz_path.exists():
        click.echo(f"Copied visualization notebook to {viz_path}")
        notebooks_dir = viz_path.parent
        click.echo(f"  Run: cd {notebooks_dir} && uv run marimo edit {viz_path.name}")


@graph.command("build")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "--local-only",
    is_flag=True,
    help="Materialize only knowledge/graph.trig; leave knowledge/composite.trig untouched.",
)
def graph_build(project_root: Path, local_only: bool) -> None:
    """Materialize graph.trig and, unless skipped, composite.trig from structured project sources."""
    from science_tool.graph.composite import assemble_composite_graph
    from science_tool.peers import PeerNotFound, PeerUnresolved
    from science_tool.project_config import load_project_config
    from science_tool.registry.config import ensure_registered

    _project_root = Path.cwd() if str(project_root) == "." else project_root
    _science_yaml = _project_root / "science.yaml"
    _cfg = None
    if _science_yaml.is_file():
        _cfg = load_project_config(_project_root)
        ensure_registered(
            _project_root,
            _cfg.name,
            project_id=_cfg.id,
            role=str(_cfg.role),
            parent=None,
        )

    try:
        local_path = materialize_graph(_project_root)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Materialized local graph at {local_path}")

    stale_composite_path = _project_root / "knowledge" / "composite.trig"
    if local_only:
        click.echo("Skipped composite graph refresh (--local-only)")
    elif _cfg is not None and _cfg.peers:
        if stale_composite_path.exists():
            stale_composite_path.unlink()
        try:
            composite_path = assemble_composite_graph(_project_root)
        except (PeerNotFound, PeerUnresolved, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Materialized composite graph at {composite_path}")
    else:
        if stale_composite_path.exists():
            stale_composite_path.unlink()

    # Non-blocking ontology suggestions
    from science_tool.graph.sources import load_project_sources
    from science_tool.graph.suggest import suggest_ontologies

    try:
        sources = load_project_sources(project_root)
        suggestions = suggest_ontologies(
            entities=sources.entities,
            declared_ontologies=[c.ontology for c in sources.ontology_catalogs],
        )
        for s in suggestions:
            click.echo(
                f"  Ontology suggestion: {s.entity_count} entities match '{s.ontology_name}' "
                f"— consider adding `ontologies: [{s.ontology_name}]` to science.yaml"
            )
    except Exception:  # noqa: BLE001
        pass  # Suggestions are non-blocking


@graph.command("propagate-freshness")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
def graph_propagate_freshness(project_root: Path, output_format: str) -> None:
    """Read-only freshness sweep — recomputes in memory and reports flagged entities."""
    from science_tool.graph.freshness import propagate_freshness_in_memory

    _project_root = (Path.cwd() if str(project_root) == "." else project_root).resolve()
    rows = propagate_freshness_in_memory(_project_root)
    emit_query_rows(
        output_format=output_format,
        title="Entities needing review (in-memory)",
        columns=[("state", "State"), ("kind", "Kind"), ("id", "ID")],
        rows=rows,
    )


@graph.command("audit")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def graph_audit(output_format: str, project_root: Path) -> None:
    """Audit canonical source references before graph materialization."""

    rows, has_failures = materialization_audit(project_root)
    emit_query_rows(
        output_format=output_format,
        title="Graph Source Audit",
        columns=[
            ("check", "Check"),
            ("status", "Status"),
            ("source", "Source"),
            ("field", "Field"),
            ("target", "Target"),
            ("details", "Details"),
        ],
        rows=rows,
    )
    if has_failures:
        raise click.exceptions.Exit(1)


@graph.command("migrate-addresses")
@click.option("--apply", is_flag=True, default=False, help="Write changes to disk (default is dry-run).")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_migrate_addresses(apply: bool, graph_path: Path) -> None:
    """Flip anti-canonical sci:addresses edges to the canonical direction.

    The CORE_PROFILE declares `addresses` with source=question, target=proposition,
    so the canonical RDF triple is `?question sci:addresses ?proposition`. Earlier
    workflows produced the reversed direction (`?proposition sci:addresses ?question`),
    which made `question-summary` undercount. This command rewrites those triples
    in place. Triples already in the canonical direction are left untouched.

    Dry-run by default; pass --apply to write.
    """
    from science_tool.graph.store import migrate_addresses_direction

    stats = migrate_addresses_direction(graph_path, apply=apply)
    if stats["flipped"] == 0:
        click.echo(f"No anti-canonical sci:addresses triples found ({stats['already_canonical']} already canonical).")
        return
    verb = "Flipped" if apply else "Would flip"
    click.echo(f"{verb} {stats['flipped']} sci:addresses triple(s) ({stats['already_canonical']} already canonical).")
    if not apply:
        click.echo("Re-run with --apply to write changes.")


@graph.command("stats")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_stats(output_format: str, graph_path: Path) -> None:
    """Show triple counts for configured named graph layers."""

    counts = read_graph_stats(graph_path)
    rows: list[dict[str, str | int]] = []

    total = 0
    for layer in GRAPH_LAYERS:
        layer_count = counts.get(layer, 0)
        rows.append({"graph": layer, "triples": layer_count})
        total += layer_count
    rows.append({"graph": "total", "triples": total})

    emit_query_rows(
        output_format=output_format,
        title="Graph Stats",
        columns=[("graph", "Graph"), ("triples", "Triples")],
        rows=rows,
    )


@graph.command("validate")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_validate(output_format: str, graph_path: Path) -> None:
    """Run structural validation checks on graph.trig."""

    rows, has_failures = validate_graph(graph_path)
    emit_query_rows(
        output_format=output_format,
        title="Graph Validation",
        columns=[("check", "Check"), ("status", "Status"), ("details", "Details")],
        rows=rows,
    )
    if has_failures:
        raise click.exceptions.Exit(1)


@graph.command("diff")
@click.option("--mode", type=click.Choice(("hybrid", "mtime", "hash")), default="hybrid", show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_diff(mode: str, output_format: str, graph_path: Path) -> None:
    """Show files that are stale relative to graph revision metadata."""

    rows = diff_graph_inputs(graph_path=graph_path, mode=mode)
    emit_query_rows(
        output_format=output_format,
        title="Graph Diff",
        columns=[("path", "Path"), ("status", "Status"), ("reason", "Reason")],
        rows=rows,
    )


@graph.command("stamp-revision")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_stamp_revision(graph_path: Path) -> None:
    """Update graph revision metadata to reflect current project state."""

    revision_time = stamp_revision(graph_path)
    click.echo(f"Stamped graph revision: {revision_time}")


@graph.command("predicates")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def graph_predicates_cmd(output_format: str) -> None:
    """List all supported predicates with descriptions and typical graph layers."""

    rows = query_predicates()
    emit_query_rows(
        output_format=output_format,
        title="Supported Predicates",
        columns=[("predicate", "Predicate"), ("description", "Description"), ("layer", "Layer")],
        rows=rows,
    )


@graph.command("neighborhood")
@click.argument("center")
@click.option("--hops", type=int, default=2, show_default=True)
@click.option("--layer", "graph_layer", type=click.Choice(GRAPH_LAYERS), default="graph/knowledge", show_default=True)
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_neighborhood(
    center: str, hops: int, graph_layer: str, limit: int, output_format: str, graph_path: Path
) -> None:
    """Return neighborhood edges around a center entity."""

    rows = query_neighborhood(
        graph_path=graph_path,
        center=center,
        hops=hops,
        graph_layer=graph_layer,
        limit=limit,
    )
    emit_query_rows(
        output_format=output_format,
        title="Graph Neighborhood",
        columns=[("subject", "Subject"), ("predicate", "Predicate"), ("object", "Object")],
        rows=rows,
    )


@graph.command("claims")
@click.option("--about", required=True)
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_claims(about: str, limit: int, output_format: str, graph_path: Path) -> None:
    """Return claims mentioning a term/entity."""

    rows = query_claims(graph_path=graph_path, about=about, limit=limit)
    emit_query_rows(
        output_format=output_format,
        title="Graph Claims",
        columns=[("claim", "Claim"), ("text", "Text"), ("sources", "Sources")],
        rows=rows,
    )


@graph.command("evidence")
@click.argument("target_ref")
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_evidence(target_ref: str, limit: int, output_format: str, graph_path: Path) -> None:
    """Return support/dispute evidence for a claim, or aggregate claim-backed evidence for a hypothesis."""

    rows = query_evidence(graph_path=graph_path, target_ref=target_ref, limit=limit)
    emit_query_rows(
        output_format=output_format,
        title="Graph Evidence",
        columns=[("evidence", "Evidence"), ("relation", "Relation"), ("text", "Text"), ("sources", "Sources")],
        rows=rows,
    )


@graph.command("cross-impact")
@click.argument("target_ref")
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_cross_impact(target_ref: str, limit: int, output_format: str, graph_path: Path) -> None:
    """Show conservative cross-impact for a proposition or evidence line."""

    payload = query_cross_impact(graph_path=graph_path, target_ref=target_ref, limit=limit)
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    emit_query_rows(
        output_format=output_format,
        title=f"Cross Impact: {payload['target']} ({payload['scope']})",
        columns=[
            ("dependent_proposition", "Dependent Proposition"),
            ("dependent_text", "Text"),
            ("relation", "Relation"),
            ("hypotheses", "Hypotheses"),
            ("interpretations", "Interpretations"),
            ("discussions", "Discussions"),
            ("questions", "Questions"),
            ("scope", "Scope"),
            ("scope_reason", "Reason"),
        ],
        rows=payload["rows"],
    )


@graph.command("coverage")
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_coverage(limit: int, output_format: str, graph_path: Path) -> None:
    """Show variables with/without dataset links and observedness status."""

    rows = query_coverage(graph_path=graph_path, limit=limit)
    emit_query_rows(
        output_format=output_format,
        title="Graph Coverage",
        columns=[("entity", "Entity"), ("label", "Label"), ("measured", "Measured"), ("observed", "Observed")],
        rows=rows,
    )


@graph.command("gaps")
@click.argument("center")
@click.option("--hops", type=int, default=2, show_default=True)
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_gaps(center: str, hops: int, limit: int, output_format: str, graph_path: Path) -> None:
    """Show structural and evidential fragility in a neighborhood around a graph target."""

    rows = query_gaps(graph_path=graph_path, center=center, hops=hops, limit=limit)
    emit_query_rows(
        output_format=output_format,
        title="Graph Gaps",
        columns=[("entity", "Entity"), ("label", "Label"), ("issues", "Issues")],
        rows=rows,
    )


@graph.command("uncertainty")
@click.option("--top", type=int, default=10, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_uncertainty(top: int, output_format: str, graph_path: Path) -> None:
    """Show claims and hypotheses ranked by derived uncertainty signals from support/dispute structure."""

    rows = query_uncertainty(graph_path=graph_path, top=top)
    emit_query_rows(
        output_format=output_format,
        title="Graph Uncertainty",
        columns=[
            ("entity", "Entity"),
            ("text", "Text"),
            ("signals", "Signals"),
            ("status", "Status"),
            ("confidence", "Confidence"),
        ],
        rows=rows,
    )


@graph.command("dashboard-summary")
@click.option("--top", type=int, default=25, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_dashboard_summary(top: int, output_format: str, graph_path: Path) -> None:
    """Show claim-centric dashboard summaries for evidence mix, empirical support, and risk."""

    rows = query_dashboard_summary(graph_path=graph_path, top=top)
    emit_query_rows(
        output_format=output_format,
        title="Graph Dashboard Summary",
        columns=[
            ("claim", "Claim"),
            ("text", "Text"),
            ("belief_display", "Belief State"),
            ("signals", "Signals"),
            ("support_count", "Supports"),
            ("dispute_count", "Disputes"),
            ("source_count", "Sources"),
            ("evidence_types", "Evidence Types"),
            ("has_empirical_data", "Empirical"),
            ("statistical_support", "Stat Support"),
            ("mechanistic_support", "Mech Support"),
            ("replication_scope", "Replication"),
            ("claim_status", "Claim Status"),
            ("pre_registration_count", "Pre-reg Count"),
            ("pre_registrations", "Pre-registrations"),
            ("interaction_count", "Interaction Count"),
            ("interaction_modifiers", "Interaction Modifiers"),
            ("bridge_count", "Bridge Count"),
            ("bridge_hypotheses", "Bridge Hypotheses"),
        ],
        rows=rows,
    )


@graph.command("neighborhood-summary")
@click.option("--top", type=int, default=25, show_default=True)
@click.option("--hops", type=int, default=1, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_neighborhood_summary(top: int, hops: int, output_format: str, graph_path: Path) -> None:
    """Show claim-centered neighborhood risk summaries for local uncertainty prioritization."""

    rows = query_neighborhood_summary(graph_path=graph_path, top=top, hops=hops)
    emit_query_rows(
        output_format=output_format,
        title="Graph Neighborhood Summary",
        columns=[
            ("center_claim", "Center Claim"),
            ("text", "Text"),
            ("neighborhood_risk", "Neighborhood Risk"),
            ("avg_risk_score", "Avg Claim Risk"),
            ("contested_count", "Contested"),
            ("single_source_count", "Single Source"),
            ("no_empirical_count", "No Empirical"),
            ("neighbor_claim_count", "Neighbors"),
            ("structural_fragility", "Structure"),
        ],
        rows=rows,
    )


@graph.command("question-summary")
@click.option("--top", type=int)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_question_summary(top: int | None, output_format: str, graph_path: Path) -> None:
    """Show question-level rollups derived from claim and neighborhood summaries."""

    rows = query_question_summary(graph_path=graph_path, top=top)
    emit_query_rows(
        output_format=output_format,
        title="Graph Question Summary",
        columns=[
            ("question", "Question"),
            ("text", "Text"),
            ("priority_score", "Priority"),
            ("avg_risk_score", "Avg Risk"),
            ("claim_count", "Claims"),
            ("neighborhood_count", "Neighbors"),
            ("contested_claim_count", "Contested"),
            ("single_source_claim_count", "Single-Source"),
            ("no_empirical_claim_count", "No Empirical"),
        ],
        rows=rows,
    )


@graph.command("inquiry-summary")
@click.option("--top", type=int, default=25, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_inquiry_summary(top: int, output_format: str, graph_path: Path) -> None:
    """Show inquiry-level rollups derived from explicit claim backing and claim summaries."""

    rows = query_inquiry_summary(graph_path=graph_path, top=top)
    emit_query_rows(
        output_format=output_format,
        title="Graph Inquiry Summary",
        columns=[
            ("inquiry", "Inquiry"),
            ("label", "Label"),
            ("text", "Text"),
            ("priority_score", "Priority"),
            ("avg_risk_score", "Avg Risk"),
            ("claim_count", "Claims"),
            ("backed_claim_count", "Backed"),
            ("contested_claim_count", "Contested"),
            ("single_source_claim_count", "Single-Source"),
            ("no_empirical_claim_count", "No Empirical"),
            ("inquiry_type", "Type"),
            ("status", "Status"),
        ],
        rows=rows,
    )


@graph.command("attention-sample")
@click.option("--limit", type=int, default=5, show_default=True)
@click.option("--seed", type=int, default=None, help="Seed for reproducible weighted sampling.")
@click.option("--kind", "kinds", multiple=True, help="Restrict candidates to one or more entity kinds.")
@click.option("--epsilon", type=float, default=0.05, show_default=True, help="Positive weight floor.")
@click.option("--today", type=click.DateTime(formats=["%Y-%m-%d"]), default=None, help="Date for age weighting.")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--reason-aware",
    is_flag=True,
    help="Use opt-in reason-coded review routing before weighted random sampling.",
)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_attention_sample(
    limit: int,
    seed: int | None,
    kinds: tuple[str, ...],
    epsilon: float,
    today: datetime | None,
    output_format: str,
    reason_aware: bool,
    graph_path: Path,
) -> None:
    """Sample epistemic entities by graph-derived attention weight."""
    from science_tool.graph.attention import query_attention_sample

    if limit < 0:
        raise click.ClickException("--limit must be >= 0")
    sample_date: date | None = today.date() if today is not None else None
    try:
        rows = query_attention_sample(
            graph_path=graph_path,
            limit=limit,
            seed=seed,
            today=sample_date,
            kinds=set(kinds) if kinds else None,
            epsilon=epsilon,
            reason_aware=reason_aware,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    table_rows = rows
    if output_format == "table":
        table_rows = [
            {
                **row,
                "reasons": ", ".join(reason["code"] for reason in row.get("reasons", [])),
            }
            for row in rows
        ]
    emit_query_rows(
        output_format=output_format,
        title="Graph Attention Sample",
        columns=[
            ("id", "ID"),
            ("freshness_state", "Freshness"),
            ("attention_weight", "Weight"),
            ("incoming_bears_on", "Bears On"),
            ("days_since_last_review", "Days"),
            ("support_count", "Supports"),
            ("dispute_count", "Disputes"),
            ("evidence_source_count", "Evidence Sources"),
            ("reasons", "Reasons"),
            ("label", "Label"),
        ],
        rows=table_rows,
    )


@graph.command("attention-rank")
@click.option("--limit", type=int, default=None, help="Cap the number of ranked rows (default: all).")
@click.option("--kind", "kinds", multiple=True, help="Restrict candidates to one or more entity kinds.")
@click.option("--epsilon", type=float, default=0.05, show_default=True, help="Positive weight floor.")
@click.option("--today", type=click.DateTime(formats=["%Y-%m-%d"]), default=None, help="Date for age weighting.")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_attention_rank(
    limit: int | None,
    kinds: tuple[str, ...],
    epsilon: float,
    today: datetime | None,
    output_format: str,
    graph_path: Path,
) -> None:
    """Rank epistemic entities by graph-derived attention weight (deterministic)."""
    from science_tool.graph.attention import query_attention_ranked

    if limit is not None and limit < 0:
        raise click.ClickException("--limit must be >= 0")
    rank_date: date | None = today.date() if today is not None else None
    rows = query_attention_ranked(
        graph_path=graph_path,
        limit=limit,
        today=rank_date,
        kinds=set(kinds) if kinds else None,
        epsilon=epsilon,
    )
    emit_query_rows(
        output_format=output_format,
        title="Attention ranking",
        columns=[
            ("id", "ID"),
            ("kind", "Kind"),
            ("freshness_state", "Freshness"),
            ("attention_weight", "Weight"),
            ("open_question_debt", "Q-Debt"),
        ],
        rows=rows,
    )


@graph.command("project-summary")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_project_summary(output_format: str, graph_path: Path) -> None:
    """Show a research-project rollup derived from lower-level reasoning summaries."""

    try:
        rows = query_project_summary(graph_path=graph_path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    emit_query_rows(
        output_format=output_format,
        title="Graph Project Summary",
        columns=[
            ("project", "Project"),
            ("profile", "Profile"),
            ("priority_score", "Priority"),
            ("avg_risk_score", "Avg Risk"),
            ("question_count", "Questions"),
            ("inquiry_count", "Inquiries"),
            ("claim_count", "Claims"),
            ("high_risk_neighborhood_count", "High-Risk Neighborhoods"),
            ("contested_claim_count", "Contested"),
            ("single_source_claim_count", "Single-Source"),
            ("no_empirical_claim_count", "No Empirical"),
        ],
        rows=rows,
    )


@graph.command("viz")
@click.option("--layer", "graph_layer", type=click.Choice(GRAPH_LAYERS), default="graph/knowledge", show_default=True)
@click.option("--center", default=None)
@click.option("--hops", type=int, default=2, show_default=True)
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_viz(
    graph_layer: str,
    center: str | None,
    hops: int,
    limit: int,
    output_path: Path | None,
    graph_path: Path,
) -> None:
    """Generate Graphviz DOT for a graph layer or neighborhood."""

    dot = build_graph_dot(
        graph_path=graph_path,
        graph_layer=graph_layer,
        center=center,
        hops=hops,
        limit=limit,
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(dot, encoding="utf-8")
        click.echo(f"Wrote DOT to {output_path}")
        return
    click.echo(dot)


@graph.command("export-json")
@click.option("--overlay", "overlays", multiple=True, type=click.Choice(("causal", "evidence")))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_export_json(overlays: tuple[str, ...], graph_path: Path) -> None:
    """Export the graph payload as JSON."""

    payload = export_graph_payload(graph_path, overlays=list(overlays) if overlays else None)
    click.echo(json.dumps(payload.model_dump(mode="json"), indent=2, sort_keys=True))


@graph.command("import")
@click.argument("snapshot_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_import(snapshot_path: Path, graph_path: Path) -> None:
    """Import a Turtle snapshot into the knowledge graph."""

    count = import_snapshot(graph_path=graph_path, snapshot_path=snapshot_path)
    click.echo(f"Imported {count} triples from {snapshot_path.name}")


@graph.command("scan-prose")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def graph_scan_prose(directory: Path, output_format: str) -> None:
    """Scan markdown files for ontology annotations (frontmatter + inline CURIEs)."""

    file_results = scan_prose(directory)
    rows: list[dict[str, str]] = []
    for entry in file_results:
        rows.append(
            {
                "path": entry["path"],
                "frontmatter_terms": "; ".join(entry["frontmatter_terms"]),
                "inline_annotations": "; ".join(f"{a['term']} [{a['curie']}]" for a in entry["inline_annotations"]),
            }
        )

    emit_query_rows(
        output_format=output_format,
        title="Prose Annotations",
        columns=[
            ("path", "Path"),
            ("frontmatter_terms", "Frontmatter Terms"),
            ("inline_annotations", "Inline Annotations"),
        ],
        rows=rows,
    )


PROJECT_STATUSES = ("selected-primary", "deferred", "active", "candidate", "speculative")
EVIDENCE_TYPES = (
    "literature_evidence",
    "empirical_data_evidence",
    "simulation_evidence",
    "benchmark_evidence",
    "expert_judgment",
    "negative_result",
)


@graph.group("add")
def graph_add() -> None:
    """Add graph entities and edges."""


@graph_add.command("concept")
@click.argument("label")
@click.option("--type", "concept_type", default=None)
@click.option("--ontology-id", default=None)
@click.option("--note", default=None, help="skos:note annotation")
@click.option("--definition", default=None, help="skos:definition annotation")
@click.option("--property", "properties", type=(str, str), multiple=True, help="KEY VALUE property pair (repeatable)")
@click.option("--status", default=None, type=click.Choice(PROJECT_STATUSES), help="Project status")
@click.option("--source", default=None, help="Provenance source reference (paper:doi_... or file path)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_concept(
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None,
    definition: str | None,
    properties: tuple[tuple[str, str], ...],
    status: str | None,
    source: str | None,
    graph_path: Path,
) -> None:
    """Add a concept node to the knowledge graph."""

    concept_uri = add_concept(
        graph_path=graph_path,
        label=label,
        concept_type=concept_type,
        ontology_id=ontology_id,
        note=note,
        definition=definition,
        properties=list(properties) if properties else None,
        status=status,
        source=source,
    )
    click.echo(f"Added concept: {concept_uri}")


@graph_add.command("article")
@click.argument("doi")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_article_cmd(doi: str, graph_path: Path) -> None:
    """Add an external literature reference by DOI."""
    uri = add_article(graph_path, doi)
    click.echo(f"Added paper: {uri}")


@graph_add.command("proposition")
@click.argument("text")
@click.option("--source", required=True, help="Provenance reference")
@click.option("--confidence", type=float, default=None)
@click.option("--evidence-type", default=None, type=click.Choice(EVIDENCE_TYPES))
@click.option("--id", "proposition_id", default=None, help="Custom proposition ID slug")
@click.option("--subject", default=None, help="Structured S-P-O: subject entity")
@click.option("--predicate", default=None, help="Structured S-P-O: predicate")
@click.option("--object", "obj", default=None, help="Structured S-P-O: object entity")
@click.option(
    "--compositional-status",
    default=None,
    type=click.Choice(["not_run", "clr_tested", "clr_robust", "clr_attenuated"]),
)
@click.option("--compositional-method", default=None, help="Normalization or per-cell method used")
@click.option("--compositional-note", default=None, help="Brief note on compositional robustness outcome")
@click.option("--platform-pattern", default=None, help="Summary label for platform heterogeneity")
@click.option("--dataset-effect", "dataset_effect_entries", multiple=True, help="Per-dataset effect as DATASET=VALUE")
@click.option(
    "--evidence-line",
    "evidence_line_entries",
    multiple=True,
    help='Evidence-line JSON, e.g. {"source":"t133","kind":"internal_correlation","datasets":["MMRF"]}',
)
@click.option(
    "--statistical-support",
    default=None,
    type=click.Choice(["none", "single_dataset", "replicated", "heterogeneous"]),
)
@click.option(
    "--mechanistic-support",
    default=None,
    type=click.Choice(["none", "inferred", "direct"]),
)
@click.option(
    "--replication-scope",
    default=None,
    type=click.Choice(["none", "single_source", "multi_source", "cross_dataset"]),
)
@click.option(
    "--claim-status",
    default=None,
    type=click.Choice(["active", "null", "weakened", "retired", "falsified"]),
)
@click.option("--pre-registration", "pre_registration_refs", multiple=True, help="Linked pre-registration ref")
@click.option(
    "--interaction-term",
    "interaction_term_entries",
    multiple=True,
    help='Interaction-term JSON, e.g. {"modifier":"concept/kras","effect":"amplifies","note":"..."}',
)
@click.option("--bridge-between", "bridge_between_refs", multiple=True, help="Hypothesis ref bridged by this claim")
@click.option(
    "--bridge-role",
    "bridge_role",
    type=click.Choice(["core", "rival", "background"]),
    default="core",
    show_default=True,
    help="Membership role for --bridge-between frames",
)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_proposition_cmd(
    text: str,
    source: str,
    confidence: float | None,
    evidence_type: str | None,
    proposition_id: str | None,
    subject: str | None,
    predicate: str | None,
    obj: str | None,
    compositional_status: str | None,
    compositional_method: str | None,
    compositional_note: str | None,
    platform_pattern: str | None,
    dataset_effect_entries: tuple[str, ...],
    evidence_line_entries: tuple[str, ...],
    statistical_support: str | None,
    mechanistic_support: str | None,
    replication_scope: str | None,
    claim_status: str | None,
    pre_registration_refs: tuple[str, ...],
    interaction_term_entries: tuple[str, ...],
    bridge_between_refs: tuple[str, ...],
    bridge_role: str,
    graph_path: Path,
) -> None:
    """Add a proposition to the knowledge graph."""
    dataset_effects = _parse_dataset_effects(dataset_effect_entries)
    evidence_lines = _parse_evidence_lines(evidence_line_entries)
    interaction_terms = _parse_interaction_terms(interaction_term_entries)
    uri = add_proposition(
        graph_path,
        text,
        source,
        confidence,
        evidence_type,
        proposition_id,
        subject,
        predicate,
        obj,
        compositional_status=compositional_status,
        compositional_method=compositional_method,
        compositional_note=compositional_note,
        platform_pattern=platform_pattern,
        dataset_effects=dataset_effects,
        evidence_lines=cast(list[PropositionEvidenceLine] | None, evidence_lines),
        statistical_support=statistical_support,
        mechanistic_support=mechanistic_support,
        replication_scope=replication_scope,
        claim_status=claim_status,
        pre_registration_refs=list(pre_registration_refs) if pre_registration_refs else None,
        interaction_terms=interaction_terms,
        bridge_between_refs=list(bridge_between_refs) if bridge_between_refs else None,
        bridge_role=MembershipRole(bridge_role),
    )
    click.echo(f"Added proposition: {uri}")
    click.echo(
        "WARNING: this entry is written directly to graph.trig and will be wiped on the next "
        "`science graph build`, which rematerialises the graph from markdown sources."
    )
    click.echo("Tip: use `science propositions create <title>` for durable source-authored project work.")


@graph_add.command("observation")
@click.argument("description")
@click.option("--data-source", required=True, help="Reference to data-package or dataset")
@click.option("--metric", default=None)
@click.option("--value", default=None)
@click.option("--uncertainty", default=None)
@click.option("--conditions", default=None)
@click.option("--id", "observation_id", default=None)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_observation_cmd(
    description: str,
    data_source: str,
    metric: str | None,
    value: str | None,
    uncertainty: str | None,
    conditions: str | None,
    observation_id: str | None,
    graph_path: Path,
) -> None:
    """Add an observation — a concrete empirical fact anchored to data."""
    uri = add_observation(graph_path, description, data_source, metric, value, uncertainty, conditions, observation_id)
    click.echo(f"Added observation: {uri}")
    click.echo(
        "WARNING: this entry is written directly to graph.trig and will be wiped on the next "
        "`science graph build`, which rematerialises the graph from markdown sources. "
        "Anchor observations inside an interpretation, finding, or proposition source file to make them durable."
    )


@graph_add.command("evidence")
@click.argument("source_entity")
@click.argument("target_entity")
@click.option("--stance", required=True, type=click.Choice(["supports", "disputes"]))
@click.option("--strength", default=None, type=click.Choice(["strong", "moderate", "weak"]))
@click.option("--caveats", default=None)
@click.option("--method", "evidence_method", default=None)
@click.option(
    "--independence",
    default=None,
    type=click.Choice(["independent", "shared-source", "circular"]),
    help="Independence of evidence source from validation target",
)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_evidence_cmd(
    source_entity: str,
    target_entity: str,
    stance: str,
    strength: str | None,
    caveats: str | None,
    evidence_method: str | None,
    independence: str | None,
    graph_path: Path,
) -> None:
    """Add an evidence edge (supports/disputes) between entities."""
    add_evidence_edge(
        graph_path, source_entity, target_entity, stance, strength, caveats, evidence_method, independence
    )
    click.echo(f"Added {stance} edge: {source_entity} \u2192 {target_entity}")
    click.echo(
        "WARNING: this edge is written directly to graph.trig and will be wiped on the next "
        "`science graph build`, which rematerialises the graph from markdown sources. "
        "Author evidence relations inside the source file (proposition, finding, or interpretation) to make them durable."
    )


@graph_add.command("hypothesis")
@click.argument("hypothesis_id")
@click.option("--text", required=True)
@click.option("--source", required=True)
@click.option("--status", default=None, type=click.Choice(PROJECT_STATUSES), help="Project status")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_hypothesis(hypothesis_id: str, text: str, source: str, status: str | None, graph_path: Path) -> None:
    """Add a hypothesis with provenance."""

    hypothesis_uri = add_hypothesis(
        graph_path=graph_path,
        hypothesis_id=hypothesis_id,
        text=text,
        source=_normalize_legacy_graph_source(source),
        status=status,
    )
    click.echo(f"Added hypothesis: {hypothesis_uri}")
    click.echo("Tip: use `science entity create hypothesis <title>` for durable source-authored project work.")


@graph_add.command("question")
@click.argument("question_id")
@click.option("--text", required=True)
@click.option("--source", required=True)
@click.option(
    "--maturity", default="open", show_default=True, type=click.Choice(("open", "partially-resolved", "resolved"))
)
@click.option("--status", default=None, type=click.Choice(PROJECT_STATUSES), help="Project status")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_question(
    question_id: str,
    text: str,
    source: str,
    maturity: str,
    status: str | None,
    related_refs: tuple[str, ...],
    graph_path: Path,
) -> None:
    """Add an open question with provenance."""

    question_uri = add_question(
        graph_path=graph_path,
        question_id=question_id,
        text=text,
        source=_normalize_legacy_graph_source(source),
        maturity=maturity,
        status=status,
        related=list(related_refs) if related_refs else None,
    )
    click.echo(f"Added question: {question_uri}")
    click.echo("Tip: use `science entity create question <title>` for durable source-authored project work.")


@graph_add.command("edge")
@click.argument("subject")
@click.argument("predicate")
@click.argument("object")
@click.option("--graph", "graph_layer", type=click.Choice(GRAPH_LAYERS), default="graph/knowledge", show_default=True)
@click.option("--claim", "claim_refs", multiple=True, help="Supporting proposition reference (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_edge(
    subject: str,
    predicate: str,
    object: str,
    graph_layer: str,
    claim_refs: tuple[str, ...],
    graph_path: Path,
) -> None:
    """Add an arbitrary edge to a selected named graph layer."""

    s_uri, p_uri, o_uri = add_edge(
        graph_path=graph_path,
        subject=subject,
        predicate=predicate,
        obj=object,
        graph_layer=graph_layer,
        claim_refs=list(claim_refs) if claim_refs else None,
    )
    click.echo(
        f"Added edge in {graph_layer}: {shorten_uri(str(s_uri))} {shorten_uri(str(p_uri))} {shorten_uri(str(o_uri))}"
    )


@graph_add.command("finding")
@click.argument("summary")
@click.option("--confidence", required=True, type=click.Choice(["high", "moderate", "low", "speculative"]))
@click.option("--proposition", "propositions", multiple=True, required=True, help="Proposition ref(s)")
@click.option("--observation", "observations", multiple=True, required=True, help="Observation ref(s)")
@click.option("--source", required=True, help="data-package or workflow-run that produced the observations")
@click.option("--id", "finding_id", default=None, help="Custom finding ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_finding_cmd(
    summary: str,
    confidence: str,
    propositions: tuple[str, ...],
    observations: tuple[str, ...],
    source: str,
    finding_id: str | None,
    graph_path: Path,
) -> None:
    """Add a finding — propositions grounded by observations."""
    uri = add_finding(graph_path, summary, confidence, list(propositions), list(observations), source, finding_id)
    click.echo(f"Added finding: {uri}")
    click.echo(
        "WARNING: this entry is written directly to graph.trig and will be wiped on the next "
        "`science graph build`, which rematerialises the graph from markdown sources. "
        "Anchor findings inside an interpretation source file to make them durable."
    )


@graph_add.command("interpretation")
@click.argument("summary")
@click.option("--finding", "findings", multiple=True, required=True, help="Finding ref(s)")
@click.option("--context", "interp_context", default=None, help="What prompted this analysis")
@click.option("--prior", default=None, help="Previous interpretation ref (provenance chain)")
@click.option("--id", "interpretation_id", default=None, help="Custom interpretation ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_interpretation_cmd(
    summary: str,
    findings: tuple[str, ...],
    interp_context: str | None,
    prior: str | None,
    interpretation_id: str | None,
    graph_path: Path,
) -> None:
    """Add an interpretation — one analysis session's narrative and findings."""
    uri = add_interpretation(graph_path, summary, list(findings), interp_context, prior, interpretation_id)
    click.echo(f"Added interpretation: {uri}")
    click.echo("Tip: use `science entity create interpretation <title>` for durable source-authored project work.")


@graph_add.command("discussion")
@click.argument("summary")
@click.option("--proposition", "propositions", multiple=True, required=True, help="Proposition ref(s)")
@click.option("--context", "disc_context", default=None, help="What prompted this discussion")
@click.option("--prior", default=None, help="Previous discussion ref (provenance chain)")
@click.option("--id", "discussion_id", default=None, help="Custom discussion ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_discussion_cmd(
    summary: str,
    propositions: tuple[str, ...],
    disc_context: str | None,
    prior: str | None,
    discussion_id: str | None,
    graph_path: Path,
) -> None:
    """Add a discussion — theoretical reasoning producing propositions."""
    uri = add_discussion(graph_path, summary, list(propositions), disc_context, prior, discussion_id)
    click.echo(f"Added discussion: {uri}")
    click.echo("Tip: use `science entity create discussion <title>` for durable source-authored project work.")


@graph_add.command("falsification")
@click.option("--predicted", required=True, help="Prediction made before analysis")
@click.option("--source-of-prediction", required=True, help="Origin of the falsified prediction")
@click.option("--observed", required=True, help="Observed result that contradicted the prediction")
@click.option("--decision", required=True, help="Decision taken after the falsification")
@click.option("--proposition", "proposition_ref", required=True, help="Proposition ref that was falsified")
@click.option("--supersedes-claim", default=None, help="Optional superseded claim ref")
@click.option("--id", "falsification_id", default=None, help="Custom falsification ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_falsification_cmd(
    predicted: str,
    source_of_prediction: str,
    observed: str,
    decision: str,
    proposition_ref: str,
    supersedes_claim: str | None,
    falsification_id: str | None,
    graph_path: Path,
) -> None:
    """Add a falsification record linked to a proposition."""
    uri = add_falsification(
        graph_path=graph_path,
        predicted=predicted,
        source_of_prediction=source_of_prediction,
        observed=observed,
        decision=decision,
        proposition_ref=proposition_ref,
        falsification_id=falsification_id,
        supersedes_claim=supersedes_claim,
    )
    click.echo(f"Added falsification: {uri}")


@graph_add.command("story")
@click.argument("title")
@click.option("--summary", required=True, help="Brief summary of the narrative arc")
@click.option("--about", required=True, help="Question or hypothesis this story is about")
@click.option("--interpretation", "interpretations", multiple=True, required=True, help="Interpretation ref(s)")
@click.option("--status", default="draft", type=click.Choice(["draft", "developing", "mature"]))
@click.option("--id", "story_id", default=None, help="Custom story ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_story_cmd(
    title: str,
    summary: str,
    about: str,
    interpretations: tuple[str, ...],
    status: str,
    story_id: str | None,
    graph_path: Path,
) -> None:
    """Add a story — a narrative arc around a question or hypothesis."""
    uri = add_story(graph_path, title, summary, about, list(interpretations), status, story_id)
    click.echo(f"Added story: {uri}")


@graph_add.command("mechanism")
@click.argument("title")
@click.option("--summary", required=True, help="Brief explanatory summary")
@click.option("--participant", "participants", multiple=True, required=True, help="Participant ref(s)")
@click.option("--proposition", "propositions", multiple=True, required=True, help="Mechanism proposition ref(s)")
@click.option("--status", default="draft", help="Mechanism status")
@click.option("--id", "mechanism_id", default=None, help="Custom mechanism ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_mechanism_cmd(
    title: str,
    summary: str,
    participants: tuple[str, ...],
    propositions: tuple[str, ...],
    status: str,
    mechanism_id: str | None,
    graph_path: Path,
) -> None:
    """Add a mechanism over existing typed entities and proposition refs."""
    uri = add_mechanism(graph_path, title, summary, list(participants), list(propositions), status, mechanism_id)
    click.echo(f"Added mechanism: {uri}")


@graph_add.command("paper")
@click.argument("title")
@click.option("--story", "stories", multiple=True, required=True, help="Story ref(s)")
@click.option("--status", default="outline", type=click.Choice(["outline", "draft", "revision", "final"]))
@click.option("--abstract", default=None, help="Paper abstract")
@click.option("--id", "paper_id", default=None, help="Custom paper ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_paper_cmd(
    title: str,
    stories: tuple[str, ...],
    status: str,
    abstract: str | None,
    paper_id: str | None,
    graph_path: Path,
) -> None:
    """Add a paper — a composition of stories for communication."""
    uri = add_paper_entity(graph_path, title, list(stories), status, abstract, paper_id)
    click.echo(f"Added paper: {uri}")


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
    if output_format == "json":
        import json

        click.echo(json.dumps(info, indent=2, default=str))
    else:
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

    if output_format == "json":
        import json

        click.echo(json.dumps(results, indent=2))
    else:
        for r in results:
            icon = "PASS" if r["status"] == "pass" else "FAIL" if r["status"] == "fail" else "WARN"
            click.echo(f"  [{icon}] {r['check']}: {r['message']}")

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


@datasets.command("download")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--file", "file_pattern", default=None, help="Download only files matching this pattern")
@click.option("--dest", "dest_dir", default="data/raw", show_default=True, type=click.Path(path_type=Path))
def datasets_download(source_id: str, file_pattern: str | None, dest_dir: Path) -> None:
    """Download dataset files. Use SOURCE:ID format."""
    import fnmatch

    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345")
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
@click.option("--path", "data_path", default="data", show_default=True, type=click.Path(path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_validate(data_path: Path, output_format: str) -> None:
    """Validate Frictionless Data Packages in raw/ and processed/ directories."""
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

    if output_format == "json":
        click.echo(json.dumps(package_report_dict(result), indent=2, sort_keys=True))
    else:
        for outcome in result.outcomes:
            if outcome.status == "not-applicable":
                continue
            click.echo(_qa.render_resource_line(outcome))
        click.echo(_qa.render_package_summary(result))

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


@main.group()
def doi() -> None:
    """DOI metadata commands."""


@doi.command("lookup")
@click.argument("doi")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def doi_lookup(doi: str, output_format: str) -> None:
    """Lookup DOI metadata via Crossref."""

    metadata = lookup_doi_metadata(doi)
    rows = [{"field": key, "value": str(value)} for key, value in metadata.items()]
    emit_query_rows(
        output_format=output_format,
        title="DOI Lookup",
        columns=[("field", "Field"), ("value", "Value")],
        rows=rows,
    )


@main.group()
def distill() -> None:
    """Distill public knowledge graphs into Turtle snapshots."""


@distill.command("openalex")
@click.option("--level", type=click.Choice(("subfields", "topics")), default="subfields", show_default=True)
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
@click.option("--cache-path", default=None, type=click.Path(path_type=Path))
def distill_openalex_cmd(level: str, output_path: Path | None, cache_path: Path | None) -> None:
    """Fetch OpenAlex science hierarchy and write Turtle snapshot."""

    result = distill_openalex(level=level, output_path=output_path, cache_path=cache_path)
    click.echo(f"Wrote OpenAlex snapshot ({level}) to {result}")


@distill.command("pykeen")
@click.argument("dataset_name")
@click.option("--budget", type=int, default=None)
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
def distill_pykeen_cmd(dataset_name: str, budget: int | None, output_path: Path | None) -> None:
    """Distill a PyKEEN dataset into a Turtle snapshot."""

    result = distill_pykeen(dataset_name=dataset_name, budget=budget, output_path=output_path)
    click.echo(f"Wrote {dataset_name} snapshot to {result}")


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

    if fmt == "json":
        click.echo(json.dumps({"task_id": task.id, "blockers": rows}, indent=2))
        return

    click.echo(f"Blockers for [{task.id}] {task.title}:")
    for row in rows:
        marker = "✓" if row["ready"] else "·"
        line = f"  {marker} {row['ref']:40s}  {row['state']}"
        if row["detail"]:
            line += f"  ({row['detail']})"
        click.echo(line)


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

    if output_format == "json":
        payload = task.model_dump(mode="json")
        payload["blocked_by_readiness"] = readiness_rows
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

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


@tasks.command("summary")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def tasks_summary(output_format: str) -> None:
    """Print summary counts by status, type, priority, and group."""
    from collections import Counter

    from science_tool.tasks import parse_tasks, warn_invalid_statuses

    active = parse_tasks(DEFAULT_TASKS_DIR / "active.md")
    if not active:
        if output_format == "json":
            click.echo(
                json.dumps({"total": 0, "by_status": {}, "by_type": {}, "by_priority": {}, "by_group": {}}, indent=2)
            )
            return
        click.echo("No active tasks.")
        return

    warn_invalid_statuses(active)

    by_status = Counter(t.status for t in active)
    by_type = Counter(t.type for t in active)
    by_priority = Counter(t.priority for t in active)
    by_group = Counter(t.group for t in active if t.group)

    if output_format == "json":
        click.echo(
            json.dumps(
                {
                    "total": len(active),
                    "by_status": dict(sorted(by_status.items())),
                    "by_type": dict(sorted(by_type.items())),
                    "by_priority": dict(sorted(by_priority.items())),
                    "by_group": dict(sorted(by_group.items())),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    click.echo(f"Total: {len(active)}")
    click.echo("By status:   " + ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items())))
    click.echo("By type:     " + ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items())))
    click.echo("By priority: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_priority.items())))
    if by_group:
        click.echo("By group:    " + ", ".join(f"{k}: {v}" for k, v in sorted(by_group.items())))


@main.group()
def project() -> None:
    """Project-level commands."""


project.add_command(_artifacts_group)


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

    # Resolve entities through the canonical project-sources loader so the index
    # is layout-agnostic: it finds questions/hypotheses whether they live under
    # the v3 `entities/<kind>/` home or the legacy `doc/`-`specs/` dirs.
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
    import json as _json

    from rich.table import Table

    from science_tool.graph.health import build_health_report, list_health_checks
    from science_tool.styles import get_console

    project_root = project_root.resolve()
    if list_checks:
        available_checks = list_health_checks()
        if output_format == "json":
            click.echo(_json.dumps({"checks": available_checks}, indent=2))
            return
        table = Table(title="Health checks")
        table.add_column("Name", style="bold")
        table.add_column("Requires sources")
        table.add_column("Description")
        for row in available_checks:
            table.add_row(str(row["name"]), "yes" if row["requires_sources"] else "no", str(row["description"]))
        get_console().print(table)
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

    if output_format == "json":
        click.echo(_json.dumps(report, indent=2))
        return

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

    total_issues = (
        len(report["unresolved_refs"])
        + len(unregistered_ref_kinds)
        + len(report["lingering_tags_lines"])
        + len(report["identity_policy"])
        + len(entity_identity)
        + len(report["legacy_structured_literature_prefixes"])
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

    if report["legacy_structured_literature_prefixes"]:
        table = Table(
            title=(
                "Legacy `article:` prefixes in structured sources "
                f"({len(report['legacy_structured_literature_prefixes'])})"
            )
        )
        table.add_column("File", style="bold")
        table.add_column("Legacy Ref")
        for row in report["legacy_structured_literature_prefixes"]:
            table.add_row(row["source_file"], row["legacy_ref"])
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
    import json as _json
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
    click.echo(_json.dumps(result.to_dict(), indent=2))


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


@main.command("book-split")
@click.argument("pdf", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json", "as_json", is_flag=True, help="Emit the chapter manifest as JSON.")
def book_split_cmd(pdf: Path, as_json: bool) -> None:
    """Extract a chapter manifest from a book PDF's outline/bookmarks.

    Intended for the /review-books command: call this first; on a non-zero exit
    with 'no outline', fall back to reading the book's table-of-contents pages.
    """
    import json as _json

    from science_tool.book_split import BookSplitError, split_book

    try:
        chapters = split_book(pdf)
    except BookSplitError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = [c.to_dict() for c in chapters]
    if as_json:
        click.echo(_json.dumps(payload, indent=2))
    else:
        for c in chapters:
            part = f"  [{c.part}]" if c.part else ""
            click.echo(f"{c.n:>3}. {c.title}  (pp. {c.start_page}-{c.end_page}){part}")


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
) -> None:
    """Create a source-authored question."""

    _create_typed_entity(
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
    )


@question.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def question_show(ref: str, output_format: str) -> None:
    """Show a source-authored question."""
    _show_typed_entity("question", ref, output_format)


@question.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def question_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored questions."""
    _list_typed_entities("question", status, related, output_format)


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
    import json as _json

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
    if as_json or output_format == "json":
        click.echo(
            _json.dumps(
                {
                    "id": reservation.id,
                    "number": reservation.number,
                    "padded": reservation.padded,
                    "slug": reservation.slug,
                    "path": str(reservation.path),
                },
                indent=2,
            )
        )
    else:
        click.echo(f"Reserved {reservation.id}")
        click.echo(f"  path: {reservation.path}")


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
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def bib_add(
    project_root: Path,
    entry: str | None,
    entry_file: Path | None,
    replace: bool,
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
    import json as _json

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

    if as_json:
        click.echo(_json.dumps({"key": result.key, "action": result.action, "path": str(result.path)}))
    else:
        click.echo(f"{result.action}: {result.key} ({result.path})")


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


@main.group()
def telemetry() -> None:
    """Local telemetry reporting commands."""


@telemetry.command("status")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def telemetry_status_cmd(output_format: str) -> None:
    """Show local telemetry status."""
    from science_tool.telemetry import get_telemetry_dir, read_events, telemetry_enabled

    telemetry_dir = get_telemetry_dir()
    rows = [
        {
            "enabled": telemetry_enabled(),
            "telemetry_dir": str(telemetry_dir),
            "event_count": len(read_events(telemetry_dir)),
        }
    ]
    emit_query_rows(
        output_format=output_format,
        title="Telemetry Status",
        columns=[
            ("enabled", "Enabled"),
            ("telemetry_dir", "Directory"),
            ("event_count", "Events"),
        ],
        rows=rows,
    )


@telemetry.command("report")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
@click.option("--errors", "include_errors", is_flag=True, help="Include recent command failures.")
@click.option("--limit", default=5, type=click.IntRange(1, 100), show_default=True, help="Recent error rows to show.")
def telemetry_report_cmd(output_format: str, include_errors: bool, limit: int) -> None:
    """Summarize local telemetry events."""
    from science_tool.telemetry import get_telemetry_dir, read_events, recent_error_rows, summarize_events

    events = read_events(get_telemetry_dir())
    summary = summarize_events(events)
    if include_errors:
        summary["recent_errors"] = recent_error_rows(events, limit=limit)
    rows = [summary]
    emit_query_rows(
        output_format=output_format,
        title="Telemetry Report",
        columns=[
            ("total_events", "Events"),
            ("event_types", "Event types"),
            ("commands", "Commands"),
            ("error_classes", "Errors"),
            ("exit_codes", "Exit codes"),
        ],
        rows=rows,
    )
    if include_errors and output_format != "json":
        emit_query_rows(
            output_format=output_format,
            title="Recent Errors",
            columns=[
                ("timestamp", "Timestamp", {"no_wrap": True}),
                ("failure", "Failure"),
                ("argv", "Argv"),
            ],
            rows=_telemetry_error_table_rows(cast(list[dict[str, object]], summary["recent_errors"])),
        )


@telemetry.command("export")
@click.option("--format", "output_format", default="jsonl", type=click.Choice(["jsonl"]))
def telemetry_export_cmd(output_format: str) -> None:
    """Export local telemetry events."""
    from science_tool.telemetry import export_events_jsonl, get_telemetry_dir, read_events

    if output_format == "jsonl":
        click.echo(export_events_jsonl(read_events(get_telemetry_dir())), nl=False)


@telemetry.command("prune")
@click.option("--before", "before_date", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def telemetry_prune_cmd(before_date: datetime, output_format: str) -> None:
    """Remove local telemetry events before a date."""
    from science_tool.telemetry import get_telemetry_dir, prune_events

    telemetry_dir = get_telemetry_dir()
    cutoff = before_date.date()
    removed = prune_events(telemetry_dir, before=cutoff)
    rows = [{"before": cutoff.isoformat(), "removed": removed, "telemetry_dir": str(telemetry_dir)}]
    emit_query_rows(
        output_format=output_format,
        title="Telemetry Prune",
        columns=[
            ("before", "Before"),
            ("removed", "Removed"),
            ("telemetry_dir", "Directory"),
        ],
        rows=rows,
    )


_FB_CATEGORIES = ("friction", "gap", "guidance", "suggestion", "positive")
_FB_STATUSES = ("open", "addressed", "deferred", "wontfix")


@main.group()
def feedback() -> None:
    """Feedback management commands."""


def _get_feedback_dir() -> Path:
    import os

    from science_tool.registry.config import get_science_config_dir

    return Path(os.environ.get("SCIENCE_FEEDBACK_DIR", str(get_science_config_dir() / "feedback")))


@feedback.command("add", context_settings={"allow_extra_args": True})
@click.option("--from-recent", is_flag=True, help="Use the newest eligible local telemetry event as feedback context.")
@click.option("--target", default=None, help="What the feedback is about (e.g., command:interpret-results)")
@click.option("--summary", required=True, help="One-line description")
@click.option("--category", default=None, type=click.Choice(_FB_CATEGORIES))
@click.option("--detail", default=None, help="Optional prose detail")
@click.option("--project", default=None, help="Project name (auto-detected if omitted)")
@click.option("--related", multiple=True, help="Related feedback entry IDs")
@click.pass_context
def feedback_add(
    ctx: click.Context,
    from_recent: bool,
    target: str,
    summary: str,
    category: str | None,
    detail: str | None,
    project: str | None,
    related: tuple[str, ...],
) -> None:
    """Add a feedback entry."""
    from datetime import date as _date

    from science_tool.feedback import (
        FeedbackEntry,
        detect_project,
        find_duplicate,
        next_feedback_id,
        save_entry,
    )

    fb_dir = _get_feedback_dir()
    recent_index = _parse_from_recent_index(ctx.args, from_recent=from_recent)
    if recent_index is not None:
        from science_tool.telemetry import feedback_context_from_recent_event, get_telemetry_dir, read_events

        try:
            telemetry_context = feedback_context_from_recent_event(read_events(get_telemetry_dir()), index=recent_index)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        target = target or telemetry_context.target
        category = category or telemetry_context.category
        detail = f"{detail}\n\n{telemetry_context.detail}" if detail else telemetry_context.detail

    if target is None:
        raise click.UsageError("--target is required unless --from-recent is used")
    category = category or "suggestion"

    if project is None:
        project = detect_project(Path.cwd())

    # Check for duplicates
    dup = find_duplicate(fb_dir, target=target, summary=summary)
    if dup is not None:
        dup.recurrence += 1
        save_entry(fb_dir, dup)
        click.echo(f"Incremented recurrence on {dup.id} (now {dup.recurrence})")
        return

    today = _date.today().isoformat()
    entry_id = next_feedback_id(fb_dir, today)

    entry = FeedbackEntry(
        id=entry_id,
        created=today,
        project=project,
        target=target,
        category=category,
        summary=summary,
        detail=detail,
        related=list(related),
    )
    save_entry(fb_dir, entry)
    click.echo(f"Created {entry.id}: {entry.summary}")


def _parse_from_recent_index(extra_args: list[str], *, from_recent: bool) -> int | None:
    if not from_recent:
        if extra_args:
            raise click.UsageError(f"Unexpected argument: {extra_args[0]}")
        return None
    if not extra_args:
        return 1
    if len(extra_args) > 1:
        raise click.UsageError("--from-recent accepts at most one 1-based index")
    try:
        index = int(extra_args[0])
    except ValueError as exc:
        raise click.UsageError("--from-recent index must be an integer") from exc
    if index < 1:
        raise click.UsageError("--from-recent index must be 1 or greater")
    return index


@feedback.command("list")
@click.option("--status", default="open", help="Filter by status (omit for 'open'; use 'all' for all statuses)")
@click.option("--target", default=None, help="Filter by target (supports fnmatch globs)")
@click.option("--category", default=None, type=click.Choice(_FB_CATEGORIES))
@click.option("--project", default=None, help="Filter by project")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def feedback_list(
    status: str | None,
    target: str | None,
    category: str | None,
    project: str | None,
    output_format: str,
) -> None:
    """List feedback entries (default: open only)."""
    from science_tool.feedback import list_entries

    if status == "all":
        status = None

    fb_dir = _get_feedback_dir()
    entries = list_entries(fb_dir, status=status, target=target, category=category, project=project)

    columns = [
        ("id", "ID"),
        ("created", "Date"),
        ("project", "Project"),
        ("target", "Target"),
        ("category", "Category"),
        ("summary", "Summary"),
        ("recurrence", "Recur"),
    ]
    rows = [
        {
            "id": e.id,
            "created": e.created,
            "project": e.project,
            "target": e.target,
            "category": e.category,
            "summary": e.summary,
            "recurrence": e.recurrence,
        }
        for e in entries
    ]
    emit_query_rows(output_format=output_format, title="Feedback", columns=columns, rows=rows)


@feedback.command("update")
@click.argument("entry_id")
@click.option("--status", default=None, type=click.Choice(_FB_STATUSES))
@click.option("--resolution", default=None, help="Required when setting terminal status")
@click.option("--category", default=None, type=click.Choice(_FB_CATEGORIES))
@click.option("--summary", default=None)
@click.option("--detail", default=None)
@click.option("--related", multiple=True, help="Related feedback entry IDs")
def feedback_update(
    entry_id: str,
    status: str | None,
    resolution: str | None,
    category: str | None,
    summary: str | None,
    detail: str | None,
    related: tuple[str, ...],
) -> None:
    """Update a feedback entry."""
    from science_tool.feedback import update_entry as _update

    fb_dir = _get_feedback_dir()
    try:
        entry = _update(
            fb_dir,
            entry_id,
            status=status,
            resolution=resolution,
            category=category,
            summary=summary,
            detail=detail,
            related=list(related) if related else None,
        )
    except (FileNotFoundError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Updated {entry.id}")


@feedback.command("triage")
@click.option("--target", default=None, help="Filter by target (fnmatch glob)")
@click.option(
    "--cluster", "cluster_mode", is_flag=True, help="Cluster near-duplicate summaries within each target/category"
)
@click.option(
    "--since", "since_days", type=click.IntRange(min=0), default=None, help="Only include entries from the last N days"
)
@click.option("--with-telemetry", is_flag=True, help="Include recent local telemetry context.")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def feedback_triage(
    target: str | None,
    cluster_mode: bool,
    since_days: int | None,
    with_telemetry: bool,
    output_format: str,
) -> None:
    """Show open entries grouped or clustered for triage."""
    from science_tool.feedback import attach_telemetry_to_triage_rows, cluster_for_triage, group_for_triage

    fb_dir = _get_feedback_dir()
    if cluster_mode or output_format == "json":
        rows = cluster_for_triage(fb_dir, target=target, since_days=since_days)
        if with_telemetry:
            from science_tool.telemetry import format_feedback_telemetry, get_telemetry_dir, read_events

            rows = attach_telemetry_to_triage_rows(
                rows,
                events=read_events(get_telemetry_dir()),
                since_days=since_days,
            )
        if not rows:
            if output_format == "json":
                emit_query_rows(
                    output_format=output_format,
                    title="Feedback Triage",
                    columns=[],
                    rows=[],
                    meta={"cluster": True, "since_days": since_days, "with_telemetry": with_telemetry},
                )
            else:
                click.echo("No open feedback entries.")
            return
        columns = [
            ("target", "Target"),
            ("category", "Category"),
            ("count", "Count"),
            ("total_recurrence", "Recur"),
            ("suggested_status", "Suggested"),
            ("suggested_next_test_target", "Next test target"),
            ("representative_summary", "Summary"),
            ("entry_ids", "Entries"),
        ]
        if with_telemetry:
            columns.append(("telemetry_text", "Telemetry"))
        table_rows = rows if output_format == "json" else _feedback_triage_table_rows(rows, with_telemetry=with_telemetry)
        emit_query_rows(
            output_format=output_format,
            title="Feedback Triage",
            columns=columns,
            rows=table_rows,
            meta={"cluster": True, "since_days": since_days, "with_telemetry": with_telemetry},
        )
        return

    groups = group_for_triage(fb_dir, target=target)

    if not groups:
        click.echo("No open feedback entries.")
        return

    telemetry_events: list[dict[str, object]] = []
    if with_telemetry:
        from science_tool.telemetry import get_telemetry_dir, read_events

        telemetry_events = read_events(get_telemetry_dir())

    for target_key, group in groups.items():
        n_projects = len(group["projects"])
        n_entries = len(group["entries"])
        total_recur = group["total_recurrence"]
        projects_str = ", ".join(sorted(group["projects"])) if group["projects"] else "unknown"
        click.echo(
            f"\n## {target_key}  ({n_entries} entries, {total_recur} recurrences, {n_projects} projects: {projects_str})"
        )
        if with_telemetry:
            from science_tool.telemetry import format_feedback_telemetry, summarize_recent_for_feedback_target

            summary = summarize_recent_for_feedback_target(
                telemetry_events,
                target=target_key,
                since_days=since_days if since_days is not None else 14,
            )
            click.echo(f"Telemetry: {format_feedback_telemetry(summary)}")
        for entry in group["entries"]:
            click.echo(f"  - {entry.id} [{entry.category}] {entry.summary}")


def _feedback_triage_table_rows(rows: list[dict[str, object]], *, with_telemetry: bool) -> list[dict[str, object]]:
    from science_tool.telemetry import format_feedback_telemetry

    table_rows: list[dict[str, object]] = []
    for row in rows:
        entry_ids = row.get("entry_ids")
        telemetry = row.get("telemetry")
        copied = dict(row)
        copied["entry_ids"] = ", ".join(str(entry_id) for entry_id in entry_ids) if isinstance(entry_ids, list) else ""
        copied["telemetry_text"] = (
            format_feedback_telemetry(cast(dict[str, object], telemetry))
            if with_telemetry and isinstance(telemetry, dict)
            else ""
        )
        table_rows.append(copied)
    return table_rows


def _telemetry_error_table_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    table_rows: list[dict[str, object]] = []
    for row in rows:
        failure = str(row.get("command") or "")
        details = [
            f"exit={row['exit_code']}" if isinstance(row.get("exit_code"), int) else "",
            str(row.get("error_class") or ""),
        ]
        detail_text = " ".join(detail for detail in details if detail)
        if detail_text:
            failure = f"{failure} ({detail_text})" if failure else detail_text
        table_rows.append(
            {
                "timestamp": row.get("timestamp", ""),
                "failure": failure,
                "argv": row.get("argv", ""),
            }
        )
    return table_rows


@feedback.command("scaffold-test")
@click.argument("entry_id")
@click.option(
    "--out",
    "out_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path for the pytest scaffold; relative paths are resolved from the current directory.",
)
@click.option("--dry-run", is_flag=True, help="Print the planned output path without writing.")
@click.option("--force", is_flag=True, help="Overwrite an existing scaffold file.")
def feedback_scaffold_test(entry_id: str, out_path: Path | None, dry_run: bool, force: bool) -> None:
    """Create a failing pytest scaffold for one feedback entry."""
    from science_tool.feedback import scaffold_test_for_feedback

    fb_dir = _get_feedback_dir()
    try:
        result = scaffold_test_for_feedback(
            fb_dir,
            entry_id,
            project_root=Path.cwd(),
            out_path=out_path,
            force=force,
            dry_run=dry_run,
        )
    except (FileNotFoundError, FileExistsError) as exc:
        raise click.ClickException(str(exc)) from exc

    prefix = "[dry run] Would write" if dry_run else "Wrote"
    click.echo(f"{prefix} feedback regression scaffold: {result.path}")
    click.echo(f"Suggested existing test target: {result.suggested_test_target}")
    click.echo(f"Replace the scaffold with a real failing test before closing {entry_id}.")


@feedback.command("report")
@click.option("--status", default=None, help="Filter by status")
@click.option("--project", default=None, help="Filter by project")
def feedback_report(status: str | None, project: str | None) -> None:
    """Generate a markdown report of feedback entries."""
    from science_tool.feedback import render_report

    fb_dir = _get_feedback_dir()
    report = render_report(fb_dir, status=status, project=project)
    click.echo(report)


# ── dataset (entity lifecycle) ──────────────────────────────────────────────


def _project_root_from_env() -> Path:
    """Return project root from SCIENCE_PROJECT_ROOT env var or cwd."""
    import os

    env = os.environ.get("SCIENCE_PROJECT_ROOT")
    return Path(env).resolve() if env else Path.cwd()


@main.group("benchmark")
def benchmark_group() -> None:
    """Benchmark dataset reports."""


@benchmark_group.command("list")
@click.option("--domain", default=None, help="Filter by benchmark domain.")
@click.option("--kind", "benchmark_kind", default=None, help="Filter by benchmark kind.")
@click.option("--belief-ref-text", default=None, help="Filter by exact related-belief text token.")
@click.option("--commons", "include_commons", is_flag=True, help="Also list commons benchmark dataset entities.")
@click.option("--coverage-summary", "coverage_summary_flag", is_flag=True, help="Only report coverage summary counts.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_list(
    domain: str | None,
    benchmark_kind: str | None,
    belief_ref_text: str | None,
    include_commons: bool,
    coverage_summary_flag: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """List dataset entities with benchmark metadata."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_catalog import coverage_summary, list_benchmarks

    root = project_root.resolve() if project_root else _project_root_from_env()
    rows, notice = list_benchmarks(
        root,
        domain=domain,
        benchmark_kind=benchmark_kind,
        belief_ref_text=belief_ref_text,
        include_commons=include_commons,
    )
    summary = coverage_summary(rows)

    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    if output_format == "json":
        if coverage_summary_flag:
            payload = {"summary": summary, "commons_notice": notice}
        else:
            payload = {"rows": rows, "summary": summary, "commons_notice": notice}
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    if coverage_summary_flag:
        table = Table(show_header=True, header_style="bold")
        for col in ("facet", "value", "count"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for facet, counts in summary.items():
            for value, count in counts.items():
                table.add_row(facet, value, str(count))
        Console(width=200).print(table)
        return

    if not rows:
        click.echo("No matching benchmark dataset entities.")
        return

    table = Table(show_header=True, header_style="bold")
    for col in ("id", "title", "scope", "class", "domains", "modalities", "signal_types", "kinds", "tasks"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        table.add_row(
            row["id"],
            row["title"],
            row["scope"],
            row["dataset_class"],
            ", ".join(row["domains"]),
            ", ".join(row["modalities"]),
            ", ".join(row["signal_types"]),
            ", ".join(row["benchmark_kinds"]),
            ", ".join(row["task_ids"]),
        )
    Console(width=200).print(table)


@benchmark_group.command("opportunities")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option("--calibration-report", is_flag=True, help="Include token/scoring calibration details.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_opportunities(
    domain: str | None,
    entity_ref: str | None,
    include_commons: bool,
    calibration_report: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report candidate benchmark opportunities for project entities."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import opportunity_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc

    payload = opportunity_report(
        root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        calibration_report=calibration_report,
    )
    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    rows = payload["matched_opportunities"]
    if not rows:
        click.echo("No candidate benchmark opportunities.")
    else:
        table = Table(title="Candidate Opportunities", show_header=True, header_style="bold")
        for col in ("entity", "benchmark", "task", "relative", "baseline", "reasons"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for row in rows:
            table.add_row(
                row["entity_id"],
                row["benchmark_id"],
                row["task_id"] or "-",
                str(row["relative_score"]),
                str(row["baseline_score"]),
                ", ".join(row["match_reasons"]),
            )
        Console(width=200).print(table)

    if calibration_report:
        calibration_table = Table(title="Calibration", show_header=True, header_style="bold")
        calibration_table.add_column("field", overflow="fold", no_wrap=False)
        calibration_table.add_column("value", overflow="fold", no_wrap=False)
        for field, value in payload["calibration"].items():
            calibration_table.add_row(field, json.dumps(value, sort_keys=True))
        Console(width=200).print(calibration_table)


def _parse_project_specs(project_specs: tuple[str, ...]) -> list[tuple[str, Path]]:
    if not project_specs:
        raise click.ClickException("at least one --project label=path is required")
    parsed: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for spec in project_specs:
        if "=" not in spec:
            raise click.ClickException("--project must use label=path")
        label, raw_path = spec.split("=", 1)
        label = label.strip()
        if not label:
            raise click.ClickException("--project label must be non-empty")
        if label in seen:
            raise click.ClickException(f"duplicate --project label: {label}")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            raise click.ClickException(f"--project {label} path does not exist: {path}")
        seen.add(label)
        parsed.append((label, path))
    return parsed


def _format_count_rows(rows: list[dict[str, Any]], *, key: str) -> str:
    values = [f"{row[key]}:{row['count']}" for row in rows]
    return ", ".join(values) if values else "-"


def _format_share_rows(rows: list[dict[str, Any]], *, key: str) -> str:
    values = [f"{row[key]}:{row['count']} ({row['share']})" for row in rows]
    return ", ".join(values) if values else "-"


@benchmark_group.command("gap-calibration")
@click.option("--project", "project_specs", multiple=True, help="Project as label=path. Repeat for each project.")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--facet", default=None, help="Limit gaps to a high-value missing benchmark facet.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def benchmark_gap_calibration(
    project_specs: tuple[str, ...],
    domain: str | None,
    facet: str | None,
    include_commons: bool,
    output_format: str,
) -> None:
    """Summarize benchmark gap calibration across projects."""
    from science_tool.benchmark_opportunities import benchmark_gap_calibration_batch

    projects = _parse_project_specs(project_specs)
    try:
        payload = benchmark_gap_calibration_batch(
            projects,
            include_commons=include_commons,
            domain=domain,
            facet=facet,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title="Benchmark Gap Calibration", show_header=True, header_style="bold")
    for col in (
        "project",
        "gap rows",
        "entity candidates",
        "fallback candidates",
        "fallback ratio",
        "suggested facets",
        "matched facets",
        "fallback benchmarks",
    ):
        table.add_column(col, overflow="fold", no_wrap=False)
    for project in payload["projects"]:
        summary = project["calibration_summary"]
        ratio = "-"
        if summary["candidate_rows"]:
            ratio = f"{summary['fallback_candidate_rows'] / summary['candidate_rows']:.3f}"
        table.add_row(
            project["label"],
            str(summary["gap_rows"]),
            str(summary["entity_specific_candidate_rows"]),
            str(summary["fallback_candidate_rows"]),
            ratio,
            _format_count_rows(summary["top_suggested_facets"], key="facet"),
            _format_count_rows(summary["top_matched_hint_facets"], key="facet"),
            _format_count_rows(summary["top_fallback_benchmarks"], key="benchmark_id"),
        )
    Console(width=200).print(table)

    aggregate_table = Table(title="Aggregate Benchmark Gap Calibration", show_header=True, header_style="bold")
    aggregate_table.add_column("field", overflow="fold", no_wrap=False)
    aggregate_table.add_column("value", overflow="fold", no_wrap=False)
    aggregate = payload["aggregate"]
    for field in (
        "project_count",
        "gap_rows",
        "candidate_rows",
        "entity_specific_candidate_rows",
        "fallback_candidate_rows",
        "fallback_candidate_ratio",
    ):
        aggregate_table.add_row(field, str(aggregate[field]))
    aggregate_table.add_row(
        "top_suggested_facets",
        _format_count_rows(aggregate["top_suggested_facets"], key="facet"),
    )
    aggregate_table.add_row(
        "top_matched_hint_facets",
        _format_count_rows(aggregate["top_matched_hint_facets"], key="facet"),
    )
    aggregate_table.add_row(
        "top_fallback_benchmarks",
        _format_count_rows(aggregate["top_fallback_benchmarks"], key="benchmark_id"),
    )
    aggregate_table.add_row(
        "top_fallback_reasons",
        _format_count_rows(aggregate["top_fallback_reasons"], key="reason"),
    )
    aggregate_table.add_row(
        "top_fallback_selection_reasons",
        _format_count_rows(aggregate["top_fallback_selection_reasons"], key="reason"),
    )
    aggregate_table.add_row(
        "top_fallback_benchmark_shares",
        _format_share_rows(aggregate["top_fallback_benchmark_shares"], key="benchmark_id"),
    )
    aggregate_table.add_row("fallback_concentration_warning", str(aggregate["fallback_concentration_warning"]))
    Console(width=200).print(aggregate_table)


@benchmark_group.command("gaps")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--facet", default=None, help="Limit gaps to a high-value missing benchmark facet.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option("--calibration-report", is_flag=True, help="Include gap token/candidate calibration details.")
@click.option("--calibration-summary", is_flag=True, help="Summarize benchmark gap calibration metrics.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_gaps(
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    include_commons: bool,
    calibration_report: bool,
    calibration_summary: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report benchmark coverage gaps for project entities."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import gap_calibration_summary, gaps_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc

    try:
        payload = gaps_report(
            root,
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            facet=facet,
            calibration_report=calibration_report,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    summary_payload = gap_calibration_summary(payload) if calibration_summary else None
    if output_format == "json":
        output_payload: dict[str, object] = dict(payload)
        if summary_payload is not None:
            output_payload["calibration_summary"] = summary_payload
        click.echo(json.dumps(output_payload, indent=2, sort_keys=True))
        return

    rows = payload["benchmark_gaps"]
    if not rows:
        click.echo("No benchmark gaps.")
    else:
        table = Table(title="Benchmark Gaps", show_header=True, header_style="bold")
        for col in ("entity", "level", "missing facets", "matches", "candidates", "reason"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for row in rows:
            missing = ", ".join(row["missing_modalities"] + row["missing_signal_types"]) or "-"
            candidates = ", ".join(candidate["benchmark_id"] for candidate in row["candidate_benchmarks"][:3]) or "-"
            table.add_row(
                row["entity_id"],
                row["gap_level"],
                missing,
                str(len(row["current_matches"])),
                candidates,
                row["reason"],
            )
        Console(width=200).print(table)

    if summary_payload is not None:
        summary_table = Table(title="Gap Calibration Summary", show_header=True, header_style="bold")
        summary_table.add_column("field", overflow="fold", no_wrap=False)
        summary_table.add_column("value", overflow="fold", no_wrap=False)
        score_range = (
            "-"
            if summary_payload["score_min"] is None
            else f"{summary_payload['score_min']} / {summary_payload['score_median']} / {summary_payload['score_max']}"
        )
        scalar_rows = {
            "gap_rows": summary_payload["gap_rows"],
            "rows_with_suggested_facets": summary_payload["rows_with_suggested_facets"],
            "candidate_rows": summary_payload["candidate_rows"],
            "entity_specific_candidate_rows": summary_payload["entity_specific_candidate_rows"],
            "fallback_candidate_rows": summary_payload["fallback_candidate_rows"],
            "score_min_median_max": score_range,
            "top_suggested_facets": summary_payload["top_suggested_facets"],
            "top_matched_hint_facets": summary_payload["top_matched_hint_facets"],
            "top_fallback_benchmarks": summary_payload["top_fallback_benchmarks"],
            "top_fallback_reasons": summary_payload["top_fallback_reasons"],
            "top_fallback_selection_reasons": summary_payload["top_fallback_selection_reasons"],
            "top_fallback_benchmark_shares": summary_payload["top_fallback_benchmark_shares"],
            "fallback_concentration_warning": summary_payload["fallback_concentration_warning"],
        }
        for field, value in scalar_rows.items():
            if field == "top_fallback_benchmark_shares":
                rendered = _format_share_rows(value, key="benchmark_id")
            elif field in {"top_fallback_reasons", "top_fallback_selection_reasons"}:
                rendered = _format_count_rows(value, key="reason")
            else:
                rendered = json.dumps(value, sort_keys=True) if isinstance(value, list) else str(value)
            summary_table.add_row(field, rendered)
        Console(width=200).print(summary_table)

    if calibration_report:
        calibration_table = Table(title="Gap Calibration", show_header=True, header_style="bold")
        calibration_table.add_column("field", overflow="fold", no_wrap=False)
        calibration_table.add_column("value", overflow="fold", no_wrap=False)
        for field, value in payload["calibration"].items():
            calibration_table.add_row(field, json.dumps(value, sort_keys=True))
        Console(width=200).print(calibration_table)


@main.group("dataset")
def dataset_group() -> None:
    """Dataset entity lifecycle commands (list, register-run, reconcile)."""


@dataset_group.command("list")
@click.option("--origin", default=None, type=click.Choice(["external", "derived"]))
@click.option("--status", default=None, help="Filter by status (e.g. candidate, active)")
@click.option("--candidate", is_flag=True, help="Shorthand for --status candidate")
@click.option("--tier", default=None, type=click.Choice(["use-now", "evaluate-next", "track"]))
@click.option("--unverified", is_flag=True, help="Only external entities with access.verified false")
@click.option(
    "--level",
    default=None,
    type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]),
)
@click.option(
    "--include-gated",
    is_flag=True,
    help="Include gated datasets (registration/controlled/commercial); excluded by default",
)
@click.option("--commons", "include_commons", is_flag=True, help="Also list commons dataset entities")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_list(
    origin: str | None,
    status: str | None,
    candidate: bool,
    tier: str | None,
    unverified: bool,
    level: str | None,
    include_gated: bool,
    include_commons: bool,
    project_root: Path | None,
) -> None:
    """List dataset entities as a table, with filters."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.datasets_catalog import list_datasets

    root = project_root.resolve() if project_root else _project_root_from_env()
    if candidate:
        status = "candidate"

    rows, notice = list_datasets(
        root,
        origin=origin,
        status=status,
        tier=tier,
        unverified=unverified,
        level=level,
        include_gated=include_gated,
        include_commons=include_commons,
    )
    if notice:
        click.echo(f"notice: commons datasets unavailable ({notice})", err=True)

    if not rows:
        click.echo("No matching dataset entities.")
        return

    table = Table(show_header=True, header_style="bold")
    for col in ("id", "title", "status", "tier", "origin", "level", "verified", "scope"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for r in rows:
        table.add_row(
            r["id"],
            r["title"],
            r["status"],
            r["tier"],
            r["origin"],
            r["level"],
            "yes" if r["verified"] else "no",
            r["scope"],
        )
    Console(width=200).print(table)


@dataset_group.command("prioritize")
@click.option("--origin", default=None, type=click.Choice(["external", "derived"]))
@click.option("--status", default=None)
@click.option("--tier", default=None, type=click.Choice(["use-now", "evaluate-next", "track"]))
@click.option(
    "--level", default=None, type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"])
)
@click.option(
    "--include-gated",
    is_flag=True,
    help="Include gated datasets (registration/controlled/commercial); excluded by default",
)
@click.option("--include-reference", is_flag=True, help="Include reference-class datasets in the ranking")
@click.option("--include-pointer", is_flag=True, help="Include pointer-class records in the ranking")
@click.option(
    "--runtime-state",
    default=None,
    type=click.Choice(["runnable", "unstaged-deposit", "blocked-access", "reference-only", "pointer-only"]),
    help="Filter by derived runtime state",
)
@click.option("--coverage", is_flag=True, help="Invert reach into per-question/hypothesis coverage rows")
@click.option("--format", "output_format", default="table", type=click.Choice(["table", "json"]))
@click.option("--explain", is_flag=True, help="Show the per-row scoring reason")
@click.option("--project-root", default=None, type=click.Path(path_type=Path, file_okay=False, dir_okay=True))
def dataset_prioritize(
    origin: str | None,
    status: str | None,
    tier: str | None,
    level: str | None,
    include_gated: bool,
    include_reference: bool,
    include_pointer: bool,
    runtime_state: str | None,
    coverage: bool,
    output_format: str,
    explain: bool,
    project_root: Path | None,
) -> None:
    """Rank dataset entities by accessibility-weighted, graph-aware usefulness."""
    import json as _json

    from science_tool.dataset_prioritize import excluded_summary, prioritize, target_coverage
    from science_tool.datasets.semantics import RuntimeState
    from science_tool.entities import graph_is_stale
    from science_tool.graph.store import DEFAULT_GRAPH_PATH
    from science_tool.graph.store.dataset import _load_dataset
    from science_tool.graph.store.identity import _graph_uri

    root = project_root.resolve() if project_root else _project_root_from_env()
    runtime_state_filter = cast(RuntimeState | None, runtime_state)
    graph_path = root / DEFAULT_GRAPH_PATH
    knowledge = provenance = None
    if graph_path.exists():
        if graph_is_stale(root, graph_path):
            click.echo(
                "warning: graph may be stale; reach/leverage from last build — run `science graph build`",
                err=True,
            )
        ds = _load_dataset(graph_path)
        knowledge = ds.graph(_graph_uri("graph/knowledge"))
        provenance = ds.graph(_graph_uri("graph/provenance"))
    else:
        click.echo("warning: no materialized graph; reach from frontmatter only", err=True)

    rows = prioritize(
        root,
        knowledge=knowledge,
        provenance=provenance,
        origin=origin,
        status=status,
        tier=tier,
        level=level,
        include_gated=include_gated or coverage,
        include_reference=include_reference or coverage,
        include_pointer=include_pointer or coverage,
        runtime_state=runtime_state_filter,
    )
    summary = excluded_summary(
        root,
        origin=origin,
        status=status,
        tier=tier,
        level=level,
        include_gated=include_gated,
        include_reference=include_reference,
        include_pointer=include_pointer,
        runtime_state=runtime_state_filter,
    )

    if coverage:
        coverage_rows = target_coverage(rows, root)
        if output_format == "json":
            click.echo(_json.dumps({"rows": coverage_rows, "excluded_summary": summary}, indent=2))
            return
        if not coverage_rows:
            click.echo("No question or hypothesis entities found.")
            return
        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        for c in ["target", "coverage", "gap-reason", "datasets"]:
            table.add_column(c, overflow="fold", no_wrap=False)
        for r in coverage_rows:
            table.add_row(
                str(r["target"]),
                str(r["coverage_state"]),
                str(r["gap_reason"]),
                ", ".join(r["datasets"]) if r["datasets"] else "-",
            )
        Console(width=200).print(table)
        return

    if output_format == "json":
        click.echo(_json.dumps({"rows": rows, "excluded_summary": summary}, indent=2))
        return
    if not rows:
        click.echo("No matching dataset entities.")
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(show_header=True, header_style="bold")
    cols = ["rank", "id", "score", "readiness", "runtime", "reach", "gap-flags"]
    if explain:
        cols.append("reason")
    for c in cols:
        table.add_column(c, overflow="fold", no_wrap=False)
    for i, r in enumerate(rows, 1):
        cells = [
            str(i),
            r["id"],
            f"{r['score']:g}",
            r["readiness"],
            r["runtime_state"],
            str(r["reach"]),
            ", ".join(r["gap_flags"]) or "-",
        ]
        if explain:
            cells.append(r["top_reason"])
        table.add_row(*cells)
    Console(width=200).print(table)
    if any(summary.values()):
        click.echo(
            "Excluded by default: "
            f"{summary['gated']} gated deposits, {summary['reference']} reference datasets, "
            f"{summary['pointer']} pointer records. Use --include-gated, --include-reference, "
            "or --include-pointer to inspect them."
        )


@dataset_group.command("add")
@click.argument("slug")
@click.option("--title", required=True, help="Human-readable dataset title")
@click.option("--origin", type=click.Choice(["external", "derived"]), default="external")
@click.option("dataset_class", "--class", type=click.Choice(["deposit", "reference", "pointer"]), default="deposit")
@click.option("--tier", type=click.Choice(["use-now", "evaluate-next", "track"]), default="track")
@click.option(
    "--level",
    type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]),
    default="controlled",
)
@click.option("--source-url", default="", help="Landing page / accession URL")
@click.option("--ontology-term", "ontology_terms", multiple=True)
@click.option("--related", "related", multiple=True, help="Related entity ref (repeatable)")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_add(
    slug: str,
    title: str,
    origin: str,
    dataset_class: str,
    tier: str,
    level: str,
    source_url: str,
    ontology_terms: tuple[str, ...],
    related: tuple[str, ...],
    project_root: Path | None,
) -> None:
    """Author a candidate external dataset entity under entities/datasets/."""
    from science_tool.datasets_catalog import add_dataset
    from science_tool.entities import EntityCommandError

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        entity_id, dest, warnings = add_dataset(
            root,
            slug,
            title=title,
            origin=origin,
            dataset_class=dataset_class,
            tier=tier,
            level=level,
            source_url=source_url,
            ontology_terms=ontology_terms,
            related=related,
        )
    except EntityCommandError as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    for w in warnings:
        click.echo(f"warning: {w}", err=True)
    click.echo(f"created {entity_id} -> {dest.relative_to(root)}")


@dataset_group.command("verify-access")
@click.argument("ref")
@click.option("--level", type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]))
@click.option(
    "--method",
    type=click.Choice(["retrieved", "credential-confirmed", "landing-confirmed", "metadata-confirmed"]),
)
@click.option("--license", "license_", default=None, help="SPDX id or sentinel (unknown|proprietary|custom)")
@click.option("dataset_class", "--class", type=click.Choice(["deposit", "reference", "pointer"]), default=None)
@click.option("--by", "verified_by", default="agent (verify-access)")
@click.option("--source-url", "source_url", default=None)
@click.option("--tier", type=click.Choice(["use-now", "evaluate-next", "track"]), default=None)
@click.option("--note", default="", help="Free-text evidence for the verification log line")
@click.option(
    "--exception",
    type=click.Choice(["scope-reduced", "expanded-to-acquire", "substituted"]),
    default=None,
    help="Record a Branch-B access exception instead of flipping verified",
)
@click.option("--rationale", default="")
@click.option("--superseded-by", "superseded_by", default=None)
@click.option("--followup-task", "followup_task", default=None)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_verify_access(
    ref: str,
    level: str | None,
    method: str | None,
    license_: str | None,
    dataset_class: str | None,
    verified_by: str,
    source_url: str | None,
    tier: str | None,
    note: str,
    exception: str | None,
    rationale: str,
    superseded_by: str | None,
    followup_task: str | None,
    project_root: Path | None,
) -> None:
    """Verify (or exception-gate) a dataset's accessibility.

    Sets the coupled origin/license/access fields together in one atomic edit and
    records a verification-log line (also backfills legacy entities).
    """
    from science_tool.datasets_catalog import verify_access
    from science_tool.entities import EntityCommandError

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        entity_id, dest, state, weight, warnings = verify_access(
            root,
            ref,
            level=level,
            license_=license_,
            dataset_class=dataset_class,
            method=method,
            verified_by=verified_by,
            source_url=source_url,
            tier=tier,
            note=note,
            exception=exception,
            rationale=rationale,
            superseded_by=superseded_by,
            followup_task=followup_task,
        )
    except EntityCommandError as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    for w in warnings:
        click.echo(f"warning: {w}", err=True)
    from science_model.frontmatter import parse_frontmatter
    from science_tool.datasets.semantics import runtime_state_for

    parsed = parse_frontmatter(dest)
    runtime_state = runtime_state_for(parsed[0]) if parsed else "blocked-access"
    click.echo(f"{entity_id} -> access={state} (weight {weight:g}), runtime={runtime_state}")


def _resolve_dataset_or_exit(root: Path, ref: str):
    from science_tool.datasets_catalog import resolve_dataset

    resolved = resolve_dataset(root, ref)
    if resolved is None:
        click.echo(f"no such dataset {ref!r} (searched local entities/datasets/ and commons)", err=True)
        raise click.exceptions.Exit(2)
    return resolved


@dataset_group.command("show")
@click.argument("ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def dataset_show(ref: str, project_root: Path | None) -> None:
    """Show a dataset entity (accepts `slug` or `dataset:slug`)."""
    from science_tool.datasets_catalog import format_show

    root = project_root.resolve() if project_root else _project_root_from_env()
    scope, fm, body = _resolve_dataset_or_exit(root, ref)
    for line in format_show(scope, fm, body):
        click.echo(line)


@dataset_group.command("consumers")
@click.argument("ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def dataset_consumers(ref: str, project_root: Path | None) -> None:
    """List entities that consume this dataset (via consumed_by)."""
    from science_tool.datasets_catalog import consumers_of

    root = project_root.resolve() if project_root else _project_root_from_env()
    _scope, fm, _body = _resolve_dataset_or_exit(root, ref)
    consumers = consumers_of(fm)
    if not consumers:
        click.echo("no recorded consumers")
        return
    for c in consumers:
        click.echo(c)


@dataset_group.command("register-run")
@click.argument("workflow_run_id")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_register_run(workflow_run_id: str, project_root: Path | None) -> None:
    """Register derived datasets for a completed workflow run.

    Writes per-output datapackage.yaml files, creates derived dataset entities,
    and updates symmetric edges (produces/consumed_by).
    """
    from science_tool.datasets_register import (
        write_derived_dataset_entities,
        write_per_output_datapackages,
        write_symmetric_edges,
    )

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        dp_paths = write_per_output_datapackages(root, workflow_run_id)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    for p in dp_paths:
        click.echo(f"wrote {p}")

    try:
        entities = write_derived_dataset_entities(root, workflow_run_id)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    for path, ds_id in entities:
        click.echo(f"entity {ds_id} -> {path}")

    dataset_ids = [ds_id for _, ds_id in entities]
    write_symmetric_edges(root, workflow_run_id, dataset_ids)
    click.echo(f"register-run complete: {len(dp_paths)} outputs, {len(entities)} entities")


@dataset_group.command("reconcile")
@click.argument("slug")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_reconcile(slug: str, project_root: Path | None) -> None:
    """Check cached-field drift between dataset entity and its runtime datapackage.yaml."""
    import yaml as _yaml
    from science_model.frontmatter import parse_frontmatter

    root = project_root.resolve() if project_root else _project_root_from_env()
    md = root / "entities" / "datasets" / f"{slug}.md"
    if not md.exists():
        click.echo(f"no such dataset entity: {md}", err=True)
        raise click.exceptions.Exit(2)
    result = parse_frontmatter(md)
    fm = result[0] if result else {}
    dp_rel = fm.get("datapackage", "")
    if not dp_rel:
        click.echo("no datapackage: pointer; nothing to reconcile", err=True)
        raise click.exceptions.Exit(0)
    rt_path = root / dp_rel
    if not rt_path.exists():
        click.echo(f"runtime datapackage missing: {rt_path}", err=True)
        raise click.exceptions.Exit(1)
    rt = _yaml.safe_load(rt_path.read_text(encoding="utf-8"))
    drifts = []
    for field in ("license", "update_cadence"):
        e_v = fm.get(field, "")
        r_v = rt.get(field, "")
        if e_v and r_v and e_v != r_v:
            drifts.append(f"{field}: entity={e_v!r} runtime={r_v!r}")
    e_ot = sorted(fm.get("ontology_terms") or [])
    r_ot = sorted(rt.get("ontology_terms") or [])
    if e_ot and r_ot and e_ot != r_ot:
        drifts.append(f"ontology_terms: entity={e_ot} runtime={r_ot}")
    if drifts:
        for d in drifts:
            click.echo(d)
        raise click.exceptions.Exit(1)
    click.echo("in sync")


# ── data-package (legacy migration) ────────────────────────────────────────


@main.group(name="data-package")
def data_package_group() -> None:
    """Legacy data-package commands."""


@data_package_group.command(name="list")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
)
def data_package_list_cmd(project_root: Path | None) -> None:
    """List legacy data-package entities (highlighting unmigrated ones)."""
    from science_model.frontmatter import parse_frontmatter

    proj = project_root or _project_root_from_env()
    dp_dir = proj / "doc" / "data-packages"
    if not dp_dir.exists():
        click.echo("no doc/data-packages/ directory")
        return
    for md in sorted(dp_dir.rglob("*.md")):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("type") != "data-package":
            continue
        status = fm.get("status", "?")
        marker = " (UNMIGRATED)" if status != "superseded" else ""
        click.echo(f"{fm.get('id', md.stem)}\t{status}{marker}")


@data_package_group.command(name="promote-orphans")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Write owner files (default: dry-run).")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
)
def data_package_promote_orphans_cmd(apply_changes: bool, project_root: Path | None) -> None:
    """Promote orphan datapackages to real entities/datasets/<id>.md owners (§B4)."""
    from science_tool.datapackage_promote import promote_orphan_datapackages

    proj = project_root or _project_root_from_env()
    report = promote_orphan_datapackages(proj, apply=apply_changes)
    for canonical_id, dp_rel in report["rejected"]:
        click.echo(f"skipped {canonical_id}: unsafe slug, not path-safe (from {dp_rel})", err=True)
    if not report["promotions"]:
        if not report["rejected"]:
            click.echo("no orphan datapackages to promote")
        return
    prefix = "wrote" if apply_changes else "[dry-run] would write"
    for plan in report["promotions"]:
        click.echo(f"{prefix} {plan.owner_rel}  (from {plan.datapackage_rel})")


if __name__ == "__main__":
    main()

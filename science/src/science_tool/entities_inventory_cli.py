"""`science entities` command group — inventory and audit of entity trees."""
from __future__ import annotations

import json
from pathlib import Path

import click

from science_tool.entities_inventory import build_inventory
from science_tool.entity_kinds import register_local_kind
from science_tool.entity_migrations import audit_identifiers
from science_tool.output import emit
from science_tool.project_config import project_config_path


def _collect_ids(ids: tuple[str, ...], ids_from: Path | None) -> frozenset[str] | None:
    """Merge --id flags and an --ids-from manifest into an allowlist, or None.

    Returns None when neither is supplied, preserving the legacy status sweep.
    An empty manifest is an error rather than a silent full sweep: a caller who
    passed --ids-from asked for scoping, and degrading that to "archive
    everything with this status" is the exact accident the allowlist exists to
    prevent.
    """
    collected = set(ids)
    if ids_from is not None:
        lines = [line.strip() for line in ids_from.read_text(encoding="utf-8").splitlines()]
        collected.update(line for line in lines if line and not line.startswith("#"))
        if not collected:
            raise click.ClickException(f"--ids-from {ids_from} contained no ids")
    return frozenset(collected) if collected else None


@click.group("entities")
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
@click.option("--id", "ids", multiple=True, help="Restrict to this entity id (repeatable).")
@click.option(
    "--ids-from",
    "ids_from",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="File of entity ids, one per line; '#' comments and blanks ignored.",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
@click.option(
    "--save-plan",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the preview plan here, for a later --apply-plan. Refuses to overwrite.",
)
@click.option("--overwrite-plan", is_flag=True, default=False, help="Allow --save-plan to replace an existing file.")
@click.option(
    "--apply-plan",
    "apply_plan_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Apply a plan saved by an earlier preview.",
)
@click.option("--expected-plan-sha256", default=None, help="Required with --apply-plan: SHA-256 of the raw plan bytes.")
@click.option(
    "--staging-token",
    default=None,
    help="Batch token for staging paths. Omit for standalone use: a unique token is "
         "generated and reported so two concurrent applies never collide.",
)
def entities_mark_superseded_command(
    project_root: Path,
    ids: tuple[str, ...],
    ids_from: Path | None,
    apply_changes: bool,
    save_plan: Path | None,
    overwrite_plan: bool,
    apply_plan_path: Path | None,
    expected_plan_sha256: str | None,
    staging_token: str | None,
) -> None:
    """Auto-derive `superseded` status from linear supersedes chains (report / --save-plan / --apply-plan)."""
    import secrets
    from datetime import date

    from science_tool.consolidation import SupersessionError, mark_superseded
    from science_tool.plan_common import (
        AllSupersessionMembers, EnvelopeError, ExplicitSupersessionIds, plan_sha256,
        read_plan_bytes, verify_envelope,
    )
    from science_tool.supersede_plan import (
        SupersedeApplyError, SupersedePlan, apply_supersede_plan, plan_supersede,
    )

    if apply_plan_path is not None:
        for bad, name in [(ids, "--id"), (ids_from, "--ids-from"), (save_plan, "--save-plan"),
                          (overwrite_plan, "--overwrite-plan"), (apply_changes, "--apply")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --apply-plan")
        if not expected_plan_sha256:
            raise click.UsageError("--apply-plan requires --expected-plan-sha256")
        raw = read_plan_bytes(apply_plan_path)
        try:
            verify_envelope(raw, expected_plan_sha256)
        except EnvelopeError as exc:
            raise click.ClickException(str(exc)) from exc
        plan = SupersedePlan.model_validate_json(raw)
        token = staging_token or secrets.token_hex(8)  # unique per standalone apply
        try:
            report = apply_supersede_plan(project_root.resolve(), plan, staging_token=token)
        except SupersedeApplyError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(output_format="json", payload={**report, "staging_token": token},
             render_text=lambda: None)
        return

    allowlist = _collect_ids(ids, ids_from)
    if save_plan is not None:
        # --apply-plan-only flags are invalid while saving.
        for bad, name in [(apply_changes, "--apply"), (expected_plan_sha256, "--expected-plan-sha256"),
                          (staging_token, "--staging-token")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --save-plan")
        selection = (ExplicitSupersessionIds(kind="explicit_ids", ids=sorted(allowlist))
                     if allowlist else AllSupersessionMembers(kind="all"))
        plan = plan_supersede(project_root.resolve(), selection=selection,
                              preview_date=date.today().isoformat())
        payload = plan.model_dump_json(indent=2).encode("utf-8")
        mode = "wb" if overwrite_plan else "xb"
        try:
            with open(save_plan, mode) as fh:
                fh.write(payload)
        except FileExistsError:
            raise click.UsageError(f"--save-plan target {save_plan} exists; pass --overwrite-plan") from None
        emit(output_format="json",
             payload={"report": plan.preview_report.model_dump(), "plan_sha256": plan_sha256(payload)},
             render_text=lambda: None)
        return

    # Plain report mode — flags that only make sense with a plan are rejected here.
    for bad, name in [(overwrite_plan, "--overwrite-plan"), (expected_plan_sha256, "--expected-plan-sha256"),
                      (staging_token, "--staging-token")]:
        if bad:
            raise click.UsageError(f"{name} requires --save-plan or --apply-plan")
    try:
        report = mark_superseded(project_root, ids=allowlist, apply=apply_changes)
    except SupersessionError as exc:
        raise click.ClickException(str(exc)) from exc
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.command("archive")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--status", "statuses", multiple=True, help="Statuses to archive (default: superseded, archived).")
@click.option("--id", "ids", multiple=True, help="Restrict to this entity id (repeatable).")
@click.option(
    "--ids-from",
    "ids_from",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="File of entity ids, one per line; '#' comments and blanks ignored.",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
@click.option(
    "--save-plan",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the preview plan here, for a later --apply-plan. Refuses to overwrite.",
)
@click.option("--overwrite-plan", is_flag=True, default=False, help="Allow --save-plan to replace an existing file.")
@click.option(
    "--apply-plan",
    "apply_plan_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Apply a plan saved by an earlier preview.",
)
@click.option("--expected-plan-sha256", default=None, help="Required with --apply-plan: SHA-256 of the raw plan bytes.")
@click.option(
    "--staging-token",
    default=None,
    help="Batch token for staging paths. Omit for standalone use: a unique token is "
         "generated and reported so two concurrent applies never collide.",
)
def entities_archive_command(
    project_root: Path,
    statuses: tuple[str, ...],
    ids: tuple[str, ...],
    ids_from: Path | None,
    apply_changes: bool,
    save_plan: Path | None,
    overwrite_plan: bool,
    apply_plan_path: Path | None,
    expected_plan_sha256: str | None,
    staging_token: str | None,
) -> None:
    """Relocate hidden-status entities into entities/_archive/ (report / --save-plan / --apply-plan)."""
    import secrets
    from datetime import datetime, timezone

    from science_tool.archive import DEFAULT_ARCHIVE_STATUSES, ArchiveError, archive_entities
    from science_tool.archive_plan import (
        ArchiveApplyError, ArchivePlan, apply_archive_plan, plan_archive,
    )
    from science_tool.plan_common import (
        ArchiveStatusSweep, EnvelopeError, ExplicitArchiveIds, plan_sha256, read_plan_bytes, verify_envelope,
    )

    if apply_plan_path is not None:
        for bad, name in [(statuses, "--status"), (ids, "--id"), (ids_from, "--ids-from"),
                          (save_plan, "--save-plan"), (overwrite_plan, "--overwrite-plan"),
                          (apply_changes, "--apply")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --apply-plan")
        if not expected_plan_sha256:
            raise click.UsageError("--apply-plan requires --expected-plan-sha256")
        raw = read_plan_bytes(apply_plan_path)
        try:
            verify_envelope(raw, expected_plan_sha256)
        except EnvelopeError as exc:
            raise click.ClickException(str(exc)) from exc
        plan = ArchivePlan.model_validate_json(raw)
        token = staging_token or secrets.token_hex(8)  # unique per standalone apply
        try:
            report = apply_archive_plan(project_root.resolve(), plan, staging_token=token)
        except ArchiveApplyError as exc:
            raise click.ClickException(str(exc)) from exc
        emit(output_format="json", payload={**report, "staging_token": token},
             render_text=lambda: None)
        return

    status_set = frozenset(statuses) if statuses else DEFAULT_ARCHIVE_STATUSES
    allowlist = _collect_ids(ids, ids_from)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if save_plan is not None:
        for bad, name in [(apply_changes, "--apply"), (expected_plan_sha256, "--expected-plan-sha256"),
                          (staging_token, "--staging-token")]:
            if bad:
                raise click.UsageError(f"{name} may not be combined with --save-plan")
        selection = (ExplicitArchiveIds(kind="explicit_ids", ids=sorted(allowlist),
                                        allowed_statuses=sorted(status_set))
                     if allowlist else
                     ArchiveStatusSweep(kind="all_by_status", statuses=sorted(status_set)))
        try:
            plan = plan_archive(project_root.resolve(), selection=selection, now=now)
        except ArchiveError as exc:
            raise click.ClickException(str(exc)) from exc
        payload = plan.model_dump_json(indent=2).encode("utf-8")
        mode = "wb" if overwrite_plan else "xb"
        try:
            with open(save_plan, mode) as fh:
                fh.write(payload)
        except FileExistsError:
            raise click.UsageError(f"--save-plan target {save_plan} exists; pass --overwrite-plan") from None
        emit(output_format="json",
             payload={"report": plan.preview_report.model_dump(), "plan_sha256": plan_sha256(payload)},
             render_text=lambda: None)
        return

    # Plain report mode — plan-only flags are rejected here.
    for bad, name in [(overwrite_plan, "--overwrite-plan"), (expected_plan_sha256, "--expected-plan-sha256"),
                      (staging_token, "--staging-token")]:
        if bad:
            raise click.UsageError(f"{name} requires --save-plan or --apply-plan")
    try:
        report = archive_entities(
            project_root, statuses=status_set, ids=allowlist, apply=apply_changes, now=now
        )
    except ArchiveError as exc:
        raise click.ClickException(str(exc)) from exc
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


@entities_group.command("import")
@click.argument(
    "sources",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--kind", default=None, help="Entity kind to import as (e.g. plan). Required when previewing.")
@click.option("--title", default=None, help="Entity title (default: the source's first level-1 heading).")
@click.option("--status", default=None, help="Entity status (default: the kind's default status).")
@click.option("--slug", default=None, help="Explicit slug (default: derived from the title).")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option(
    "--save-plan",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the preview plan here, for a later --apply-plan. Refuses to overwrite.",
)
@click.option(
    "--overwrite-plan",
    is_flag=True,
    default=False,
    help="Allow --save-plan to replace an existing file (never the source).",
)
@click.option(
    "--apply-plan",
    "apply_plan_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Apply a plan saved by an earlier preview. Mutually exclusive with SOURCE.",
)
@click.option("--expected-plan-sha256", default=None, help="Required with --apply-plan: SHA-256 of the raw plan bytes.")
def entities_import_command(
    sources: tuple[Path, ...],
    kind: str | None,
    title: str | None,
    status: str | None,
    slug: str | None,
    project_root: Path,
    save_plan: Path | None,
    overwrite_plan: bool,
    apply_plan_path: Path | None,
    expected_plan_sha256: str | None,
) -> None:
    """Import a loose markdown document as a canonical entity.

    Preview:  science entities import SRC --kind plan --save-plan p.json
    Apply:    science entities import --apply-plan p.json --expected-plan-sha256 SHA

    There is deliberately no --apply flag on the preview form. Re-deriving the
    plan inside the applying invocation would mean the operator approves one
    report and the command executes a different one -- silently, when anything
    claimed the previewed number in between.
    """
    from science_tool.entities import EntityCommandError
    from science_tool.entity_import import (
        EntityImportError,
        apply_cohort_import,
        apply_import,
        parse_cohort_import_plan,
        parse_import_plan,
        plan_cohort_import,
        plan_import,
    )
    from science_tool.plan_common import EnvelopeError, plan_sha256, read_plan_bytes, verify_envelope
    from science_tool.reference_rewrite import ReferenceDriftError

    if apply_plan_path is not None:
        if sources or kind is not None:
            raise click.UsageError(
                "--apply-plan takes the saved plan only; do not repeat SOURCE or --kind."
            )
        for supplied, option in [
            (title is not None, "--title"),
            (status is not None, "--status"),
            (slug is not None, "--slug"),
            (save_plan is not None, "--save-plan"),
            (overwrite_plan, "--overwrite-plan"),
        ]:
            if supplied:
                raise click.UsageError(f"{option} may not be combined with --apply-plan")
        if not expected_plan_sha256:
            raise click.UsageError("--apply-plan requires --expected-plan-sha256")

        exclude = frozenset({apply_plan_path.resolve()})
        raw = read_plan_bytes(apply_plan_path)
        try:
            verify_envelope(raw, expected_plan_sha256)
        except EnvelopeError as exc:
            raise click.ClickException(str(exc)) from exc
        try:
            probe = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise click.ClickException(f"plan is not valid JSON: {exc}") from exc
        if not isinstance(probe, dict):
            raise click.ClickException("plan is not a JSON object")

        plan_type = probe.get("plan_type")
        schema_version = probe.get("schema_version")
        cohort_version = (
            isinstance(schema_version, int)
            and not isinstance(schema_version, bool)
            and schema_version == 1
        )
        try:
            if plan_type == "cohort-import" and cohort_version:
                cohort_plan = parse_cohort_import_plan(raw)
                applied = apply_cohort_import(
                    project_root, cohort_plan, exclude=exclude
                )
                payload = {**cohort_plan.model_dump(), "applied": applied}
            elif plan_type is None and schema_version is None:
                single_plan = parse_import_plan(raw)
                applied = apply_import(project_root, single_plan, exclude=exclude)
                payload = {**single_plan.model_dump(), "applied": applied}
            else:
                raise click.ClickException(
                    "unsupported plan "
                    f"(plan_type={plan_type!r}, schema_version={schema_version!r})"
                )
        except (EntityImportError, EntityCommandError, ReferenceDriftError) as exc:
            raise click.ClickException(str(exc)) from exc
        emit(output_format="json", payload=payload, render_text=lambda: None)
        return

    if not sources or kind is None:
        raise click.UsageError(
            "SOURCE and --kind are required unless --apply-plan is given."
        )
    if expected_plan_sha256:
        raise click.UsageError("--expected-plan-sha256 requires --apply-plan")
    if save_plan is not None:
        save_resolved = save_plan.resolve()
        if any(save_resolved == source.resolve() for source in sources):
            raise click.UsageError(
                "--save-plan would overwrite the source document; choose another path"
            )
    preview_exclude = (
        frozenset({save_plan.resolve()}) if save_plan is not None else frozenset()
    )
    is_cohort = len(sources) >= 2
    if is_cohort and (title is not None or slug is not None):
        raise click.UsageError(
            "--title/--slug are per-document and not allowed with multiple sources"
        )
    try:
        if is_cohort:
            plan = plan_cohort_import(
                project_root,
                list(sources),
                kind=kind,
                status=status,
                exclude=preview_exclude,
            )
        else:
            source = next(iter(sources))
            plan = plan_import(
                project_root,
                source,
                kind=kind,
                title=title,
                status=status,
                slug=slug,
                exclude=preview_exclude,
            )
    except (EntityImportError, EntityCommandError) as exc:
        raise click.ClickException(str(exc)) from exc
    if save_plan is not None:
        payload_bytes = plan.model_dump_json(indent=2).encode("utf-8")
        try:
            with open(save_plan, "xb") as fh:
                fh.write(payload_bytes)
        except FileExistsError:
            if not overwrite_plan:
                raise click.UsageError(
                    f"--save-plan target {save_plan} exists; "
                    "pass --overwrite-plan to replace it"
                ) from None
            save_plan.write_bytes(payload_bytes)
        except OSError as exc:
            raise click.UsageError(
                f"cannot write --save-plan to {save_plan}: {exc}"
            ) from exc
        emit(
            output_format="json",
            payload={**plan.model_dump(), "plan_sha256": plan_sha256(payload_bytes)},
            render_text=lambda: None,
        )
        return
    emit(output_format="json", payload=plan.model_dump(), render_text=lambda: None)

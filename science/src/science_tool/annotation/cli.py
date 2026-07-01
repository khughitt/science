"""Click CLI group for the `annotate` subcommands.

Phase 3.1 ships the `verify` subcommand. Later phases (P3.2+) will add
`audit`, `lift-tokens`, `list`, `ack`, `dismiss`, `fix`, `render`, and
`stats` to this group.
"""

from __future__ import annotations

import json
import re as _re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from science_tool.annotation import crud, query
from science_tool.annotation.audit import audit_file, merge_planned
from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
    sidecar_for_markdown,
)
from science_tool.annotation.model import Annotation, Body, IriBody, Sidecar, Status
from science_tool.annotation.prose_decomposition import (
    DecompositionError,
    ProseDecompositionStore,
    compute_source_hash,
    parse_submitted_decomposition,
)
from science_tool.annotation.prose_grounding import (
    DEFAULT_GROUNDING_FLOOR,
    ProseGroundingError,
    build_prose_grounding_report,
    write_prose_grounding_report,
)
from science_tool.annotation.prose_health import (
    ProseHealthError,
    build_prose_health_report,
    write_prose_health_report,
)
from science_tool.annotation.prose_promote import ProsePromotionError, promote_prose_unit
from science_tool.annotation.prose_promotion_batch import (
    apply_prose_promotion_plan,
    plan_from_json_text,
    plan_prose_promotions,
    plan_to_json_text,
)
from science_tool.annotation.prose_source_entity import resolve_or_create_prose_source
from science_tool.annotation.prose_validation import (
    validate_latest_decomposition,
    validate_submitted_decomposition_artifact,
)
from science_tool.annotation.sources import LINT_SOURCES, SOURCES
from science_tool.annotation.sources.marker_token import (
    TOKEN_TYPE_MAP,
    MarkerTokenSource,
)
from science_tool.annotation.text_segmentation import (
    build_quote_selector,
    sentence_range_containing_literal,
    split_sentences_with_offsets,
)
from science_tool.annotation.verify import (
    VerifyReport,
    apply_supersessions,
    verify_path,
)
from science_tool.entities import EntityCommandError
from science_tool.markers import scan_text as _scan_markers_text
from science_tool.output import OUTPUT_FORMATS

_GROUNDING_SUMMARY_KEYS = (
    "grounded_units",
    "below_floor_units",
    "unbacked_units",
    "unpromoted_units",
    "skipped_units",
    "stale_units",
)
_PROSE_HEALTH_SUMMARY_KEYS = (
    "declared_sources",
    "sources_with_decomposition",
    "sources_with_grounding",
    "current_candidate_units",
    "promoted_units",
    "grounded_units",
    "below_floor_units",
    "unbacked_units",
    "unpromoted_units",
    "skipped_units",
    "stale_units",
    "contested_units",
)
_PROSE_VALIDATION_SUMMARY_KEYS = (
    "units",
    "resolved",
    "unresolved",
    "ambiguous",
    "stale",
    "hard_failures",
)


@click.group("annotate")
def annotate_group() -> None:
    """Annotation-system tooling (W3C Web Annotation sidecars)."""


@annotate_group.command("ingest-prose-decomposition")
@click.argument("artifact_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--allow-changed", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def ingest_prose_decomposition_cmd(
    artifact_path: Path,
    root: Path | None,
    allow_changed: bool,
    fmt: str,
) -> None:
    """Ingest an offline internal-prose decomposition JSON artifact."""
    project_root = (root or Path.cwd()).resolve()
    try:
        artifact = parse_submitted_decomposition(
            artifact_path.read_text(encoding="utf-8"),
            project_root=project_root,
        )
        current_hash = compute_source_hash(artifact.source.path)
        if current_hash != artifact.source.content_hash and not allow_changed:
            raise click.ClickException(
                "content hash mismatch: "
                f"artifact has {artifact.source.content_hash}; current source is {current_hash}"
            )

        source_resolution = resolve_or_create_prose_source(
            project_root=project_root,
            slug=artifact.source.slug,
            title=artifact.source.title,
            source_path=artifact.source.path,
            content_hash=artifact.source.content_hash,
            artifact_id=artifact.artifact.artifact_id,
        )
        report = ProseDecompositionStore(project_root).persist(artifact)
    except (DecompositionError, EntityCommandError) as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(
            json.dumps(
                {
                    "source_ref": artifact.source_ref,
                    "artifact_id": artifact.artifact.artifact_id,
                    "stale": report.stale_fingerprints,
                    "source_entity_created": source_resolution.created,
                },
                indent=2,
            )
        )
        return

    click.echo(
        "ingested prose decomposition "
        f"{report.artifact_id} for {artifact.source_ref} "
        f"({len(artifact.units)} units; {len(report.stale_fingerprints)} stale; "
        f"source_entity_created={source_resolution.created})"
    )


@annotate_group.command("check-prose-decomposition")
@click.option("--source", "source_ref", required=True)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def check_prose_decomposition_cmd(source_ref: str, root: Path | None, fmt: str) -> None:
    """Check the latest internal-prose decomposition artifact."""
    if not source_ref.startswith("prose-source:"):
        raise click.ClickException("--source must use prose-source:<slug>")

    slug = source_ref.split(":", 1)[1]
    if not slug:
        raise click.ClickException("source slug must not be empty")
    project_root = (root or Path.cwd()).resolve()
    try:
        artifact, report = validate_latest_decomposition(project_root, slug)
    except DecompositionError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(
            json.dumps(
                {
                    "source_ref": source_ref,
                    "artifact_id": artifact.artifact.artifact_id,
                    "units": report.rows,
                },
                indent=2,
            )
        )
        return

    click.echo(f"checked prose decomposition {artifact.artifact.artifact_id} for {source_ref}")
    for row in report.rows:
        detail = []
        if row["stale"]:
            detail.append("stale")
        if row["promoted_to"]:
            detail.append(f"promoted_to={row['promoted_to']}")
        if row["message"]:
            detail.append(str(row["message"]))
        message = f" - {'; '.join(detail)}" if detail else ""
        click.echo(
            f"  {row['unit_id']}: {row['status']} "
            f"({row['locator_status']}; {row['fingerprint']}){message}"
        )


@annotate_group.command("validate-prose-decomposition-artifact")
@click.argument("artifact_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--allow-changed", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def validate_prose_decomposition_artifact_cmd(
    artifact_path: Path,
    root: Path | None,
    allow_changed: bool,
    fmt: str,
) -> None:
    """Validate an offline internal-prose decomposition JSON artifact without ingesting it."""
    project_root = (root or Path.cwd()).resolve()
    try:
        artifact, report = validate_submitted_decomposition_artifact(
            artifact_path,
            project_root=project_root,
            allow_changed=allow_changed,
        )
    except DecompositionError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = report.to_json()
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2))
        return

    summary = _required_prose_validation_summary(payload)
    click.echo(
        f"validated prose decomposition {artifact.artifact.artifact_id} for {artifact.source_ref}: "
        f"units={summary['units']} resolved={summary['resolved']} "
        f"unresolved={summary['unresolved']} ambiguous={summary['ambiguous']} "
        f"stale={summary['stale']} hard_failures={summary['hard_failures']}"
    )
    for row in report.rows:
        detail = []
        if row["stale"]:
            detail.append("stale")
        if row["promoted_to"]:
            detail.append(f"promoted_to={row['promoted_to']}")
        if row["message"]:
            detail.append(str(row["message"]))
        message = f" - {'; '.join(detail)}" if detail else ""
        click.echo(
            f"  {row['unit_id']}: {row['status']} "
            f"({row['locator_status']}; {row['fingerprint']}){message}"
        )


def _required_prose_validation_summary(payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise click.ClickException("prose validation report summary must be an object")
    for key in _PROSE_VALIDATION_SUMMARY_KEYS:
        if key not in summary:
            raise click.ClickException(f"missing prose validation summary key: {key}")
    return summary


@annotate_group.command("promote-prose-decomposition")
@click.option("--source", "source_ref", required=True)
@click.option("--unit", "unit_id", required=True)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--apply", "do_apply", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def promote_prose_decomposition_cmd(
    source_ref: str,
    unit_id: str,
    root: Path | None,
    do_apply: bool,
    fmt: str,
) -> None:
    """Promote one validated internal-prose decomposition candidate."""
    project_root = (root or Path.cwd()).resolve()
    try:
        report = promote_prose_unit(
            project_root=project_root,
            source_ref=source_ref,
            unit_id=unit_id,
            apply=do_apply,
        )
    except (ProsePromotionError, DecompositionError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "minted": report.minted,
        "linked": report.linked,
        "skipped": dict(report.skipped),
        "written": report.written_paths,
    }
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2))
        return

    skipped = ", ".join(f"{reason}={count}" for reason, count in sorted(report.skipped.items())) or "none"
    mode = "applied" if do_apply else "planned"
    click.echo(
        f"{mode} prose promotion for {source_ref}#{unit_id}: "
        f"minted={report.minted} linked={report.linked} skipped={skipped}"
    )


@annotate_group.command("plan-prose-promotions")
@click.option("--source", "source_slug", required=True)
@click.option("--unit", "unit_ids", multiple=True, required=True)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--output", "output_path", default="-", type=click.Path(dir_okay=False, path_type=Path))
def plan_prose_promotions_cmd(
    source_slug: str,
    unit_ids: tuple[str, ...],
    root: Path | None,
    output_path: Path,
) -> None:
    """Write an identity-only prose promotion plan for selected units."""
    project_root = (root or Path.cwd()).resolve()
    if source_slug.startswith("prose-source:"):
        source_slug = source_slug.split(":", 1)[1]
    try:
        plan = plan_prose_promotions(project_root, source_slug, unit_ids)
    except (ProsePromotionError, DecompositionError) as exc:
        raise click.ClickException(str(exc)) from exc

    text = plan_to_json_text(plan)
    if str(output_path) == "-":
        click.echo(text, nl=False)
        return
    output_path.write_text(text, encoding="utf-8")
    click.echo(f"planned {len(plan.rows)} prose promotion rows to {output_path}")


@annotate_group.command("apply-prose-promotion-plan")
@click.argument("plan_json", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def apply_prose_promotion_plan_cmd(plan_json: Path, root: Path | None, fmt: str) -> None:
    """Apply an identity-only prose promotion plan after state validation."""
    project_root = (root or Path.cwd()).resolve()
    try:
        plan = plan_from_json_text(plan_json.read_text(encoding="utf-8"))
        report = apply_prose_promotion_plan(project_root, plan)
    except (OSError, ProsePromotionError, DecompositionError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "minted": report.minted,
        "linked": report.linked,
        "skipped": dict(report.skipped),
        "written": report.written_paths,
    }
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2))
        return

    skipped = ", ".join(f"{reason}={count}" for reason, count in sorted(report.skipped.items())) or "none"
    click.echo(
        f"applied prose promotion plan {plan_json}: "
        f"minted={report.minted} linked={report.linked} skipped={skipped}"
    )
    click.echo("recovered link rows may report no minted/linked counter increments")


@annotate_group.command("ground-prose-decomposition")
@click.option("--source", "source_ref", required=True)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--graph",
    "graph_path",
    default=Path("knowledge/graph.trig"),
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--floor", "floor", default=DEFAULT_GROUNDING_FLOOR)
@click.option("--write", "do_write", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def ground_prose_decomposition_cmd(
    source_ref: str,
    root: Path | None,
    graph_path: Path,
    floor: str,
    do_write: bool,
    fmt: str,
) -> None:
    """Ground promoted internal-prose units against the project graph."""
    if not source_ref.startswith("prose-source:"):
        raise click.ClickException("--source must use prose-source:<slug>")

    project_root = (root or Path.cwd()).resolve()
    if not graph_path.is_absolute():
        graph_path = project_root / graph_path
    if not graph_path.exists():
        raise click.ClickException(f"graph file is missing: {graph_path}")

    try:
        report = build_prose_grounding_report(
            project_root,
            source_ref,
            graph_path,
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            floor=floor,
        )
        payload = report.to_json()
        written = write_prose_grounding_report(project_root, report) if do_write else False
    except ProseGroundingError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = _required_prose_grounding_summary(payload)
    click.echo(
        f"grounded prose decomposition for {source_ref}: "
        f"grounded={summary['grounded_units']} "
        f"below_floor={summary['below_floor_units']} "
        f"unbacked={summary['unbacked_units']} "
        f"unpromoted={summary['unpromoted_units']} "
        f"skipped={summary['skipped_units']} "
        f"stale={summary['stale_units']}"
    )
    if do_write:
        click.echo("wrote prose grounding artifact" if written else "unchanged prose grounding artifact")


@annotate_group.command("cross-paper-evidence")
@click.option(
    "--source",
    "source_ref",
    default=None,
    help="proposition:<slug> to inspect; omit for project-wide",
)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def cross_paper_evidence_cmd(source_ref: str | None, root: Path | None, fmt: str) -> None:
    """Diagnose derived cross-paper literature evidence."""
    from science_tool.annotation.cross_paper_evidence import build_cross_paper_evidence_report

    if source_ref is not None and not source_ref.startswith("proposition:"):
        raise click.ClickException("--source must use proposition:<slug>")

    project_root = (root or Path.cwd()).resolve()
    payload = build_cross_paper_evidence_report(project_root, proposition_ref=source_ref)

    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    if source_ref is not None:
        belief = payload["belief"]
        click.echo(
            f"cross-paper evidence for {source_ref}: {len(payload['units'])} unit(s); "
            f"belief={belief['belief_magnitude']} contested={belief['contested']} "
            f"contested_groups={len(belief['contested_groups'])}"
        )
        for unit in payload["units"]:
            click.echo(
                f"  {unit['edge']:8s} {unit['paper']} "
                f"({unit['stance']}; {unit['role']}/{unit['strength']})"
            )
    else:
        summary = payload["summary"]
        if summary["propositions"] == 0:
            click.echo("No proposition entities found.")
        elif summary["units"] == 0:
            click.echo("No derived cross-paper literature evidence found.")
        else:
            for proposition in payload["propositions"]:
                click.echo(
                    f"{proposition['proposition']}: "
                    f"+{proposition['supporting_papers']} / "
                    f"-{proposition['disputing_papers']} paper(s)"
                )

    if payload["faults"]:
        click.echo(f"FAULTS ({len(payload['faults'])}):")
        for fault in payload["faults"]:
            click.echo(
                f"  {fault['sidecar']} [{fault['annotation']}] "
                f"{fault['reason']}: {fault['detail']}"
            )


@annotate_group.command("reconcile-propositions")
@click.option("--all", "all_scope", is_flag=True, default=False)
@click.option("--proposition", "proposition_ref", default=None)
@click.option(
    "--source",
    "source_md",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(("table", "json", "scaffold")),
    default="table",
)
def reconcile_propositions_cmd(
    all_scope: bool,
    proposition_ref: str | None,
    source_md: Path | None,
    root: Path | None,
    fmt: str,
) -> None:
    """Generate deterministic proposition reconciliation candidates."""
    from science_tool.annotation.proposition_reconciliation import (
        build_reconciliation_report,
        report_to_json,
    )

    selected = sum(
        1 for item in (all_scope, proposition_ref is not None, source_md is not None) if item
    )
    if selected != 1:
        raise click.ClickException("choose exactly one scope: --all, --proposition, or --source")
    if proposition_ref is not None and not proposition_ref.startswith("proposition:"):
        raise click.ClickException("--proposition must use proposition:<slug>")

    project_root = (root or Path.cwd()).resolve()
    source_sidecar = None
    if source_md is not None:
        source_path = source_md if source_md.is_absolute() else project_root / source_md
        source_sidecar = str(sidecar_for_markdown(source_path))

    report = build_reconciliation_report(
        project_root,
        proposition_ref=proposition_ref,
        source_sidecar=source_sidecar,
    )
    payload = report_to_json(report)

    if fmt in {"json", "scaffold"}:
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = payload["summary"]
    click.echo(
        "proposition reconciliation: "
        f"same_claim={summary['same_claim_candidates']} "
        f"factorization={summary['factorization_disagreements']} "
        f"faults={summary['faults']}"
    )
    for item in payload["same_claim_candidates"]:
        click.echo(
            f"same_claim {item['priority']:6s} {','.join(item['propositions'])} "
            f"flags={','.join(item['flags']) or '-'}"
        )
    for item in payload["factorization_disagreements"]:
        click.echo(
            f"factorization {item['priority']:6s} {item['proposition']} "
            f"action={item['recommended_action']}"
        )
    if payload["faults"]:
        click.echo(f"FAULTS ({len(payload['faults'])}):")
        for fault in payload["faults"]:
            click.echo(f"  {fault['reason']}: {fault['detail']}")


@annotate_group.command("validate-proposition-reconciliation")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def validate_proposition_reconciliation_cmd(
    input_path: Path, root: Path | None, fmt: str
) -> None:
    """Validate an agent-reviewed proposition reconciliation artifact."""
    from science_tool.annotation.proposition_reconciliation import (
        ReconciliationValidationError,
        build_reconciliation_report,
        validate_review_doc,
    )

    project_root = (root or Path.cwd()).resolve()
    try:
        doc = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--input is not valid JSON: {exc}") from exc
    report = build_reconciliation_report(project_root)
    try:
        payload = validate_review_doc(doc, report)
    except ReconciliationValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    click.echo(
        f"proposition reconciliation review: {payload['status']} "
        f"judgments={payload['judgments']} incomplete={len(payload['review_incomplete'])}"
    )


@annotate_group.command("build-prose-health")
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--manifest",
    "manifest_path",
    default=Path("data/prose-health/manifest.json"),
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option("--write", "do_write", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def build_prose_health_cmd(
    root: Path | None,
    manifest_path: Path,
    do_write: bool,
    fmt: str,
) -> None:
    """Build the project-level prose epistemics health artifact."""
    project_root = (root or Path.cwd()).resolve()
    if not manifest_path.is_absolute():
        manifest_path = project_root / manifest_path
    try:
        report = build_prose_health_report(
            project_root,
            manifest_path=manifest_path,
            generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )
        payload = report.to_json()
        written = write_prose_health_report(project_root, report) if do_write else False
    except ProseHealthError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = _required_prose_health_summary(payload)
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    strict = coverage.get("strict_grounding") if isinstance(coverage, dict) else {}
    strict_ratio = strict.get("ratio") if isinstance(strict, dict) else None
    strict_text = "n/a" if strict_ratio is None else f"{strict_ratio:.1%}"
    click.echo(
        "built prose health: "
        f"sources={summary['declared_sources']} "
        f"candidates={summary['current_candidate_units']} "
        f"promoted={summary['promoted_units']} "
        f"grounded={summary['grounded_units']} "
        f"strict_grounding={strict_text} "
        f"findings={len(payload.get('findings') or [])}"
    )
    if do_write:
        click.echo("wrote prose health artifact" if written else "unchanged prose health artifact")


def _required_prose_grounding_summary(payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise click.ClickException("prose grounding report summary must be an object")
    for key in _GROUNDING_SUMMARY_KEYS:
        if key not in summary:
            raise click.ClickException(f"missing prose grounding summary key: {key}")
    return summary


def _required_prose_health_summary(payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise click.ClickException("prose health report summary must be an object")
    for key in _PROSE_HEALTH_SUMMARY_KEYS:
        if key not in summary:
            raise click.ClickException(f"missing prose health summary key: {key}")
    return summary


@annotate_group.command("verify")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root to walk for *.anno.trig files.",
)
@click.option(
    "--summary-only",
    is_flag=True,
    help="Print only aggregate counts, not per-issue lines.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Promote degraded/fuzzy warnings to failures (exit 1).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    help="Mutate broken annotations to status='superseded' and rewrite sidecars.",
)
@click.option(
    "--actor",
    type=str,
    default=None,
    help="Required with --apply. Identity recorded as dc:contributor on each mutation.",
)
@click.option(
    "--force-dirty",
    is_flag=True,
    help="Bypass the clean-tree guard when --apply is set.",
)
def verify(
    root_path: Path,
    summary_only: bool,
    strict: bool,
    output_format: str,
    apply_changes: bool,
    actor: str | None,
    force_dirty: bool,
) -> None:
    """Resolve every annotation's selector against its source; report drift.

    Default is dry-run. With --apply, broken annotations are mutated to
    status='superseded' and their sidecars rewritten. --apply requires
    --actor.
    """
    root = root_path.resolve()

    if apply_changes:
        if not actor:
            raise click.ClickException("--apply requires --actor <identity>")
        if not force_dirty:
            dirty = _dirty_anno_files(root)
            if dirty:
                raise click.ClickException(
                    "Refusing to --apply: the following annotation files have "
                    "uncommitted changes:\n  "
                    + "\n  ".join(sorted(d.as_posix() for d in dirty))
                    + "\nCommit or stash, or pass --force-dirty to override."
                )

    report = verify_path(root)

    rewritten_count = 0
    pre_apply_broken = 0
    if apply_changes:
        if actor is None:
            raise click.ClickException("--apply requires --actor <identity>")
        pre_apply_broken = report.broken
        rewritten = apply_supersessions(
            report,
            actor=actor,
            now=datetime.now(timezone.utc),
        )
        rewritten_count = len(rewritten)
        # Re-run after apply so the table/JSON reflects the post-mutation
        # state. Broken count drops to 0 (or near-zero if a rewrite raced
        # with a concurrent edit); degraded/fuzzy/parse-errors unchanged.
        report = verify_path(root)

    if output_format == "json":
        _emit_json(
            report,
            root=root,
            summary_only=summary_only,
            apply_meta=(
                {
                    "rewritten_sidecars": rewritten_count,
                    "superseded_annotations": pre_apply_broken,
                }
                if apply_changes
                else None
            ),
        )
    else:
        if apply_changes:
            click.echo(
                f"annotate verify --apply: rewrote {rewritten_count} sidecar(s); "
                f"superseded {pre_apply_broken} broken annotation(s)."
            )
        _emit_table(report, summary_only=summary_only)

    # Unified exit policy. Parse errors and post-apply broken rows are
    # always hard failures. Strict additionally promotes degraded/fuzzy/
    # source-missing.
    if report.broken > 0 or report.parse_errors > 0:
        raise click.exceptions.Exit(1)
    if strict and (report.degraded > 0 or report.fuzzy > 0 or report.source_missing > 0):
        raise click.exceptions.Exit(1)


def _emit_table(report: VerifyReport, *, summary_only: bool) -> None:
    if (
        report.broken == 0
        and report.degraded == 0
        and report.fuzzy == 0
        and report.source_missing == 0
        and report.parse_errors == 0
    ):
        click.echo(
            f"annotate verify: all clean "
            f"({report.annotations} annotations across {report.sidecars} sidecars; "
            f"0 broken, 0 degraded, 0 fuzzy)"
        )
        if report.superseded_skipped:
            click.echo(
                f"  ({report.superseded_skipped} already-superseded annotations skipped)"
            )
        return

    click.echo(
        f"annotate verify: {report.broken} broken, "
        f"{report.degraded} degraded, {report.fuzzy} fuzzy, "
        f"{report.source_missing} source-missing, "
        f"{report.parse_errors} parse-errors "
        f"({report.annotations} annotations across {report.sidecars} sidecars)"
    )
    if report.superseded_skipped:
        click.echo(
            f"  ({report.superseded_skipped} already-superseded annotations skipped)"
        )

    if summary_only:
        return

    for issue in report.issues:
        click.echo(
            f"  [{issue.kind}] {issue.sidecar.name} :: {issue.annotation_id}"
        )
        if issue.source:
            click.echo(f"      source: {issue.source}")
        if issue.exact_preview:
            click.echo(f"      exact:  {issue.exact_preview!r}")


def _emit_json(
    report: VerifyReport,
    *,
    root: Path,
    summary_only: bool,
    apply_meta: Optional[dict[str, int]] = None,
) -> None:
    summary = {
        "sidecars": report.sidecars,
        "annotations": report.annotations,
        "broken": report.broken,
        "degraded": report.degraded,
        "fuzzy": report.fuzzy,
        "source_missing": report.source_missing,
        "parse_errors": report.parse_errors,
        "superseded_skipped": report.superseded_skipped,
    }
    payload: dict[str, object] = {"summary": summary}
    if apply_meta is not None:
        payload["apply"] = apply_meta
    if not summary_only:
        payload["issues"] = [
            {
                "sidecar": _relpath(issue.sidecar, root),
                "annotation_id": issue.annotation_id,
                "source": issue.source,
                "kind": issue.kind,
                "exact_preview": issue.exact_preview,
            }
            for issue in report.issues
        ]
    click.echo(json.dumps(payload, indent=2))


def _relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _dirty_anno_files(root: Path) -> list[Path]:
    """Return *.anno.trig files with uncommitted changes under `root`.

    Returns an empty list when `root` is not a git repo (we don't refuse
    to apply in non-git contexts; the guard is a convenience for CI/dev
    workflows, not a hard correctness requirement).
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return []
    if result.returncode != 0:
        return []
    dirty: list[Path] = []
    for line in result.stdout.splitlines():
        # Porcelain format: "XY path" — first two chars are status, then space, then path.
        if len(line) < 4:
            continue
        rel = line[3:].strip()
        if rel.endswith(".anno.trig"):
            dirty.append(Path(rel))
    return dirty


@annotate_group.command("audit")
@click.option(
    "--root", "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--source", "sources_opt",
    multiple=True,
    help=(
        "Source short name (repeatable). Defaults to LINT_SOURCES. "
        "Valid: " + ", ".join(sorted(SOURCES))
    ),
)
@click.option(
    "--no-llm", is_flag=True, default=False,
    help="Skip LLM sources (forward-compat no-op in P3.2).",
)
@click.option("--dry-run", is_flag=True, default=False)
@click.option(
    "--format", "fmt",
    type=click.Choice(("table", "json")), default="table",
)
@click.option("--actor", default="science-annotate-cli")
def audit_cmd(
    root_path: Path,
    sources_opt: tuple[str, ...],
    no_llm: bool,
    dry_run: bool,
    fmt: str,
    actor: str,
) -> None:
    """Run mechanical-audit sources; write planned rows to sidecars."""
    del no_llm  # accepted; P3.2 has no LLM sources to skip
    selected_names = tuple(sources_opt) if sources_opt else LINT_SOURCES
    unknown = [s for s in selected_names if s not in SOURCES]
    if unknown:
        click.echo(f"unknown source(s): {unknown!r}", err=True)
        raise SystemExit(1)
    selected = [SOURCES[s] for s in selected_names]
    full_source_names = sorted({s.name for s in selected})

    root = root_path.resolve()
    md_files = _collect_audit_markdown_files(root)
    now = datetime.now(timezone.utc)

    file_reports: list[dict] = []
    summary = {
        "files_scanned": len(md_files),
        "rows_written": 0,
        "duplicates_skipped": 0,
        "files_with_writes": 0,
        "sources_run": full_source_names,
    }

    for md in md_files:
        sidecar = md.with_suffix(".anno.trig")
        if dry_run:
            planned_per_source = {}
            for src in selected:
                plans = list(src.scan(md))
                planned_per_source[src.short_name] = len(plans)
            file_reports.append({
                "path": str(md.relative_to(root)),
                "rows_planned": planned_per_source,
            })
            continue
        report = audit_file(
            md, sidecar, sources=selected, actor=actor, now=now,
        )
        if report.rows_written or report.duplicates_skipped:
            file_reports.append({
                "path": str(md.relative_to(root)),
                "rows_written": report.written_per_source,
                "duplicates_skipped": report.duplicates_skipped,
            })
        summary["rows_written"] += report.rows_written
        summary["duplicates_skipped"] += report.duplicates_skipped
        if report.rows_written:
            summary["files_with_writes"] += 1

    if fmt == "json":
        click.echo(json.dumps({"summary": summary, "files": file_reports}, indent=2))
    else:
        _emit_audit_table(summary, file_reports, dry_run=dry_run)


def _collect_audit_markdown_files(root: Path) -> list[Path]:
    """Mirror prose_lint._collect_markdown_files but importable here."""
    from science_tool.prose_lint import _collect_markdown_files  # noqa: PLC0415
    return _collect_markdown_files(root)


def _emit_audit_table(
    summary: dict, files: list[dict], *, dry_run: bool,
) -> None:
    if dry_run:
        click.echo(f"audit dry-run over {summary['files_scanned']} file(s):")
    else:
        click.echo(
            f"audit: {summary['rows_written']} row(s) written, "
            f"{summary['duplicates_skipped']} duplicate(s) skipped, "
            f"{summary['files_with_writes']} file(s) modified."
        )
    for entry in files:
        click.echo(f"  {entry['path']}: {entry}")


_TOKEN_LITERAL_PATTERN = _re.compile(
    r" *\[(?:" + "|".join(TOKEN_TYPE_MAP.keys()) + r")\] *",
)


@annotate_group.command("lift-tokens")
@click.option(
    "--root", "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--remove", "remove_mode", is_flag=True, default=False)
@click.option("--force-dirty", is_flag=True, default=False)
@click.option(
    "--format", "fmt",
    type=click.Choice(("table", "json")), default="table",
)
@click.option("--actor", default="science-annotate-cli")
def lift_tokens_cmd(
    root_path: Path,
    remove_mode: bool,
    force_dirty: bool,
    fmt: str,
    actor: str,
) -> None:
    """Lift inline phase-2 tokens to sidecar annotation rows."""
    root = root_path.resolve()
    md_files = _collect_lift_markdown_files(root)
    now = datetime.now(timezone.utc)
    source = MarkerTokenSource()

    summary: dict = {
        "files_scanned": len(md_files),
        "rows_written": 0,
        "tokens_removed": 0,
        "duplicates_skipped": 0,
        "files_with_writes": 0,
    }
    file_reports: list[dict] = []

    if remove_mode:
        affected = _files_with_hits(md_files)
        if not force_dirty and affected:
            dirty = _dirty_files_among(root, affected)
            if dirty:
                click.echo(
                    "lift-tokens --remove refuses on dirty tree:\n  "
                    + "\n  ".join(str(p.relative_to(root)) for p in dirty),
                    err=True,
                )
                raise SystemExit(1)

    for md in md_files:
        sidecar_path = md.with_suffix(".anno.trig")
        original_text = md.read_text(encoding="utf-8")
        original_hits = list(
            _scan_markers_text(md, original_text, strict=False)
        )
        non_doc_hits = [h for h in original_hits if not h.in_documentation]
        if not non_doc_hits:
            continue

        if remove_mode:
            cleaned_text = _strip_tokens_from_prose(original_text)
            plans = _replan_for_remove(
                source, md, original_text, cleaned_text, non_doc_hits,
            )
        else:
            plans = list(source.scan(md))

        sidecar = (
            read_sidecar(sidecar_path) if sidecar_path.exists() else Sidecar()
        )
        new_sidecar, written = merge_planned(
            sidecar, plans, actor=actor, now=now,
        )

        if remove_mode:
            # Sidecar first, then prose (per spec write-order rationale).
            if written or new_sidecar != sidecar:
                atomic_write_text(
                    sidecar_path,
                    serialize_sidecar(new_sidecar),
                )
            atomic_write_text(md, cleaned_text)
            summary["tokens_removed"] += len(non_doc_hits)
        else:
            if written:
                atomic_write_text(
                    sidecar_path, serialize_sidecar(new_sidecar),
                )

        skipped = len(plans) - len(written)
        summary["rows_written"] += len(written)
        summary["duplicates_skipped"] += skipped
        if written:
            summary["files_with_writes"] += 1

        file_reports.append({
            "path": str(md.relative_to(root)),
            "rows_written": len(written),
            "duplicates_skipped": skipped,
            **({"tokens_removed": len(non_doc_hits)} if remove_mode else {}),
        })

    if fmt == "json":
        click.echo(
            json.dumps(
                {"summary": summary, "files": file_reports}, indent=2,
            )
        )
    else:
        click.echo(
            f"lift-tokens: {summary['rows_written']} row(s) written, "
            f"{summary['tokens_removed']} token(s) removed, "
            f"{summary['duplicates_skipped']} duplicate(s) skipped, "
            f"{summary['files_with_writes']} file(s) modified."
        )


def _collect_lift_markdown_files(root: Path) -> list[Path]:
    from science_tool.markers import _collect_markdown_files  # noqa: PLC0415
    return _collect_markdown_files(root)


def _files_with_hits(md_files: list[Path]) -> list[Path]:
    out: list[Path] = []
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        hits = [
            h
            for h in _scan_markers_text(md, text, strict=False)
            if not h.in_documentation
        ]
        if hits:
            out.append(md)
    return out


def _dirty_files_among(root: Path, files: list[Path]) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root), capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []  # not a git repo / git unavailable -> no dirty check
    dirty_rel: set[str] = set()
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        dirty_rel.add(line[3:].strip())
    out: list[Path] = []
    for f in files:
        rel = str(f.relative_to(root))
        if rel in dirty_rel:
            out.append(f)
    return out


def _strip_tokens_from_prose(text: str) -> str:
    from science_tool.markdown_utils import is_fence_line  # noqa: PLC0415
    out_lines: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        no_nl = line.rstrip("\n")
        if is_fence_line(no_nl):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue
        out_lines.append(_strip_tokens_outside_backticks(line))
    return "".join(out_lines)


def _strip_tokens_outside_backticks(line: str) -> str:
    parts = _re.split(r"(`[^`]*`)", line)
    for i, part in enumerate(parts):
        if part.startswith("`") and part.endswith("`"):
            continue
        parts[i] = _TOKEN_LITERAL_PATTERN.sub(" ", part)
    joined = "".join(parts)
    # Collapse the double-space introduced by removing a token from the
    # middle of a sentence; preserve leading indentation.
    leading_match = _re.match(r"^[ \t]*", joined)
    leading = leading_match.group(0) if leading_match else ""
    body = joined[len(leading):]
    body = _re.sub(r"  +", " ", body)
    return leading + body


def _replan_for_remove(
    source: MarkerTokenSource,
    md: Path,
    original_text: str,
    cleaned_text: str,
    original_hits,
) -> list:
    """Build planned rows whose selectors anchor to cleaned_text but whose
    `match_text`/`lifted_from` retain the original bracketed token."""
    from science_tool.annotation.model import (  # noqa: PLC0415
        Motivation,
        SpecificResource,
        TextualBody,
    )
    from science_tool.annotation.sources.base import (  # noqa: PLC0415
        PlannedAnnotation,
    )
    plans: list = []
    cleaned_sentences = split_sentences_with_offsets(cleaned_text)
    original_sentences = split_sentences_with_offsets(original_text)
    for hit in original_hits:
        literal = f"[{hit.token}]"
        rng = sentence_range_containing_literal(
            original_text, hit.line, literal,
        )
        if rng is None:
            continue
        try:
            ordinal = next(
                i for i, (s, _e) in enumerate(original_sentences)
                if s == rng[0]
            )
        except StopIteration:
            continue
        if ordinal >= len(cleaned_sentences):
            continue
        sent_start, sent_end = cleaned_sentences[ordinal]
        atype, body_msg = TOKEN_TYPE_MAP[hit.token]
        sel = build_quote_selector(
            cleaned_text, sent_start, sent_end, context=60,
        )
        plans.append(PlannedAnnotation(
            target=SpecificResource(source=md.name, selector=sel),
            annotation_type=atype,
            motivation=Motivation.CLASSIFYING,
            body=TextualBody(value=f"{body_msg} (lifted from {literal})"),
            match_text=literal,
            source_name=source.name,
            lifted_from=literal,
        ))
    return plans


# ---------------------------------------------------------------------------
# annotate list
# ---------------------------------------------------------------------------

_VALID_STATUS_VALUES = (
    "open", "ack", "fixed", "dismissed", "superseded", "all",
)


def _parse_status_filter(values: tuple[str, ...]) -> frozenset[Status] | None:
    """Convert --status flag values into a query.filter_annotations argument.

    `("all",)` (or any tuple containing "all") → None (no filter).
    Empty tuple is treated by the CLI default; this helper only sees
    explicit values.
    """
    if "all" in values:
        return None
    return frozenset(Status(v) for v in values)


def _scope_to_sidecars(
    root: Path | None,
    path: Path | None,
) -> tuple[Path, list[tuple[Path, Sidecar]]]:
    """Resolve the (--root, PATH) pair into (root_path, sidecars list).

    Caller is responsible for the mutual-exclusion check.
    """
    if path is not None:
        if path.is_dir():
            return path.resolve(), list(query.iter_sidecars(path))
        if path.suffix == ".md":
            sidecar_path = sidecar_for_markdown(path)
            if not sidecar_path.exists():
                return path.parent.resolve(), []
            return (
                path.parent.resolve(),
                [(sidecar_path, query.read_sidecar_strict(sidecar_path))],
            )
        if path.name.endswith(".anno.trig"):
            return (
                path.parent.resolve(),
                [(path, query.read_sidecar_strict(path))],
            )
        raise click.ClickException(
            f"PATH {path} is not a directory, .md, or .anno.trig file"
        )
    effective_root = (root or Path.cwd()).resolve()
    return effective_root, list(query.iter_sidecars(effective_root))


@annotate_group.command("list")
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--status", "statuses_opt", multiple=True,
    type=click.Choice(_VALID_STATUS_VALUES),
)
@click.option("--source", "sources_opt", multiple=True)
@click.option("--since", "since_ref", default=None)
@click.option(
    "--format", "fmt", type=click.Choice(("table", "json")), default="table",
)
def list_cmd(
    path: Path | None,
    root_path: Path | None,
    statuses_opt: tuple[str, ...],
    sources_opt: tuple[str, ...],
    since_ref: str | None,
    fmt: str,
) -> None:
    """List annotations matching filters."""
    if path is not None and root_path is not None:
        raise click.ClickException("--root and PATH are mutually exclusive")

    try:
        effective_root, sidecars = _scope_to_sidecars(root_path, path)
    except query.SidecarParseError as exc:
        raise click.ClickException(str(exc)) from exc

    statuses = _parse_status_filter(
        statuses_opt or ("open",),
    )

    since_changed: frozenset[Path] | None = None
    if since_ref is not None:
        try:
            since_changed = query.git_changed_markdown(effective_root, since_ref)
        except RuntimeError as exc:
            raise click.ClickException(
                f"--since failed: {exc}"
            ) from exc

    rows = list(query.filter_annotations(
        sidecars,
        statuses=statuses,
        sources=sources_opt,
        since_changed=since_changed,
    ))
    rows.sort(key=lambda pa: (
        query.entity_relpath_for_sidecar(pa[0], effective_root),
        pa[1].id,
    ))

    if fmt == "json":
        _emit_list_json(rows, effective_root, len(sidecars))
    else:
        _emit_list_table(rows, effective_root, len(sidecars))


def _emit_list_table(
    rows: list[tuple[Path, Annotation]],
    root: Path,
    sidecar_count: int,
) -> None:
    if not rows:
        click.echo(
            f"annotate list: 0 annotation(s) across {sidecar_count} sidecar(s)"
        )
        return
    for sidecar_path, ann in rows:
        qualified = (
            f"{query.entity_relpath_for_sidecar(sidecar_path, root)}:{ann.id}"
        )
        preview = ann.target.selector.exact
        if len(preview) > 60:
            preview = preview[:60] + "…"
        click.echo(
            f"  {qualified}  {ann.status.value:<10}  "
            f"{ann.source}  {ann.annotation_type}  {preview!r}"
        )
    click.echo(
        f"\nannotate list: {len(rows)} annotation(s) across "
        f"{sidecar_count} sidecar(s)"
    )


def _emit_list_json(
    rows: list[tuple[Path, Annotation]],
    root: Path,
    sidecar_count: int,
) -> None:
    items = []
    for sidecar_path, ann in rows:
        sel = ann.target.selector
        items.append({
            "id": ann.id,
            "qualified_id":
                f"{query.entity_relpath_for_sidecar(sidecar_path, root)}:{ann.id}",
            "status": ann.status.value,
            "source": ann.source,
            "annotation_type": ann.annotation_type,
            "exact_preview": ann.target.selector.exact[:60],
            "selector": {
                "exact": sel.exact,
                "prefix": sel.prefix,
                "suffix": sel.suffix,
            },
            "bodies": [_body_json(b) for b in ann.bodies],
        })
    click.echo(json.dumps({
        "summary": {
            "total_annotations": len(rows),
            "total_sidecars": sidecar_count,
        },
        "annotations": items,
    }, indent=2))


def _body_json(body: Body) -> dict[str, str]:
    """JSON view of a body for grounding consumers (IRI value / textual value)."""
    if isinstance(body, IriBody):
        return {"type": "iri", "value": body.iri}
    return {"type": "textual", "format": body.format, "value": body.value}


# ---------------------------------------------------------------------------
# annotate ack / dismiss / fix  (shared _crud_invoke orchestrator)
# ---------------------------------------------------------------------------

def _crud_invoke(
    verb: str,
    new_status: Status,
    *,
    id_arg: str,
    root_path: Path | None,
    actor_opt: str | None,
    force_dirty: bool,
    reason: str | None = None,
) -> None:
    """Shared body for ack_cmd / dismiss_cmd / fix_cmd.

    `verb` is the user-facing command name ("ack", "dismiss", "fix")
    used as the output prefix. Necessary because Status.DISMISSED.value
    is "dismissed" and Status.FIXED.value is "fixed" — the resulting
    status is NOT the verb. The spec output examples are
    `dismiss: ...` and `fix: ...`, not `dismissed: ...` / `fixed: ...`.
    """
    root = (root_path or Path.cwd()).resolve()
    actor = crud._resolve_actor(actor_opt, root)
    now = datetime.now(timezone.utc)
    try:
        result = crud.apply_status_change(
            root, id_arg, new_status,
            actor=actor, now=now, reason=reason, force_dirty=force_dirty,
        )
    except query.AmbiguousAnnotationId as exc:
        click.echo(str(exc), err=True)
        for cand in exc.candidates:
            click.echo(f"  {cand}", err=True)
        raise click.exceptions.Exit(2) from exc
    except query.AnnotationNotFound as exc:
        raise click.ClickException(str(exc)) from exc
    except crud.CrudRefusedDirty as exc:
        raise click.ClickException(str(exc)) from exc
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    suffix = (
        f" (reason: {reason})" if reason else ""
    )
    click.echo(
        f"{verb}: {result.qualified_id} "
        f"{result.prior_status.value} → {result.new_status.value}{suffix}"
    )


@annotate_group.command("ack")
@click.argument("id_arg", metavar="ID")
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--actor", "actor_opt", default=None)
@click.option("--force-dirty", is_flag=True, default=False)
def ack_cmd(
    id_arg: str, root_path: Path | None,
    actor_opt: str | None, force_dirty: bool,
) -> None:
    """Acknowledge an annotation (status: open → ack)."""
    _crud_invoke(
        "ack", Status.ACK,
        id_arg=id_arg, root_path=root_path,
        actor_opt=actor_opt, force_dirty=force_dirty,
    )


@annotate_group.command("dismiss")
@click.argument("id_arg", metavar="ID")
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--actor", "actor_opt", default=None)
@click.option("--force-dirty", is_flag=True, default=False)
@click.option("--reason", "reason", required=True)
def dismiss_cmd(
    id_arg: str, root_path: Path | None,
    actor_opt: str | None, force_dirty: bool, reason: str,
) -> None:
    """Dismiss an annotation (status: open → dismissed)."""
    if not reason.strip():
        raise click.ClickException("--reason cannot be empty")
    _crud_invoke(
        "dismiss", Status.DISMISSED,
        id_arg=id_arg, root_path=root_path,
        actor_opt=actor_opt, force_dirty=force_dirty,
        reason=reason,
    )


@annotate_group.command("fix")
@click.argument("id_arg", metavar="ID")
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--actor", "actor_opt", default=None)
@click.option("--force-dirty", is_flag=True, default=False)
def fix_cmd(
    id_arg: str, root_path: Path | None,
    actor_opt: str | None, force_dirty: bool,
) -> None:
    """Mark an annotation as fixed (status: open → fixed)."""
    _crud_invoke(
        "fix", Status.FIXED,
        id_arg=id_arg, root_path=root_path,
        actor_opt=actor_opt, force_dirty=force_dirty,
    )


@annotate_group.command("stats")
@click.option(
    "--root", "root_path", default=None,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--format", "fmt", type=click.Choice(("table", "json")), default="table",
)
def stats_cmd(root_path: Path | None, fmt: str) -> None:
    """Project-wide annotation counts (status / source / type)."""
    root = (root_path or Path.cwd()).resolve()
    try:
        sidecars = list(query.iter_sidecars(root))
    except query.SidecarParseError as exc:
        raise click.ClickException(str(exc)) from exc
    report = query.compute_stats(sidecars)
    if fmt == "json":
        click.echo(json.dumps({
            "summary": {
                "total_annotations": report.total_annotations,
                "total_sidecars": report.total_sidecars,
            },
            "by_status": {k.value: v for k, v in report.by_status.items()},
            "by_source": dict(report.by_source),
            "by_type": dict(report.by_type),
        }, indent=2))
        return
    click.echo(
        f"annotate stats: {report.total_annotations} annotation(s) across "
        f"{report.total_sidecars} sidecar(s)\n"
    )
    if report.by_status:
        click.echo("By status:")
        for status, count in report.by_status.items():
            click.echo(f"  {status.value:<12} {count}")
        click.echo()
    if report.by_source:
        click.echo("By source:")
        for source, count in report.by_source.items():
            click.echo(f"  {source:<40} {count}")
        click.echo()
    if report.by_type:
        click.echo("By type:")
        for type_, count in report.by_type.items():
            click.echo(f"  {type_:<24} {count}")


@annotate_group.command("pubtator")
@click.argument("identifier")
@click.option(
    "--project-root",
    "project_root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False),
    help="Project root (defaults to the current directory).",
)
@click.option(
    "--email",
    default=None,
    help="Contact email for polite-pool APIs (falls back to $SCIENCE_CONTACT_EMAIL).",
)
@click.option(
    "--cache-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Override cache directory (defaults to $SCIENCE_CACHE_DIR or ~/.cache/science).",
)
@click.option(
    "--actor",
    default="science-annotate-cli",
    help="Identity recorded as the annotation creator.",
)
def pubtator_cmd(
    identifier: str,
    project_root: Path | None,
    email: str | None,
    cache_dir: Path | None,
    actor: str,
) -> None:
    """Seed PubTator3 entity-mention annotations into `<citekey>.source.anno.trig`.

    Requires an existing `<citekey>.source.md` (run `science paper persist-source`
    first). PubMed-only: papers with no PubTator3 record are a graceful no-op.
    """
    import os as _os

    from science_tool.annotation.pubtator_seed import seed_pubtator
    from science_tool.annotation.source_text import SourceTextError
    from science_tool.paper_fetch import FetchConfig

    resolved_email = email or _os.environ.get("SCIENCE_CONTACT_EMAIL")
    if not resolved_email:
        raise click.ClickException(
            "Contact email is required. Pass --email or set $SCIENCE_CONTACT_EMAIL."
        )
    cfg = (
        FetchConfig(email=resolved_email)
        if cache_dir is None
        else FetchConfig(email=resolved_email, cache_dir=cache_dir)
    )
    root = (project_root or Path.cwd()).resolve()
    try:
        report = seed_pubtator(
            project_root=root,
            identifier=identifier,
            cfg=cfg,
            actor=actor,
            now=datetime.now(timezone.utc),
        )
    except SourceTextError as exc:
        raise click.ClickException(str(exc)) from exc

    if report.note:
        click.echo(report.note)
    all_skips = {
        **{f"entity:{k}": v for k, v in report.entity_skipped.items()},
        **{f"relation:{k}": v for k, v in report.relation_skipped.items()},
    }
    skips = ", ".join(f"{k}={v}" for k, v in sorted(all_skips.items()))
    click.echo(
        f"Wrote {report.entity_written} entity + {report.relation_written} relation "
        f"annotation(s)" + (f"; skipped {skips}" if skips else "")
    )


@annotate_group.command("extract")
@click.option(
    "--source-md", "source_md", required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the paper's <citekey>.source.md.",
)
@click.option("--model", required=True, help="Exact extracting model id (source identity).")
@click.option(
    "--input", "input_path", default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="candidates.json produced by the paper-annotate agent.",
)
@click.option("--check", "check_only", is_flag=True, default=False,
              help="Read-only: print JSON {status: changed|unchanged} for the "
                   "source vs last extraction (ignores --format).")
@click.option("--actor", default="paper-annotate",
              help="Identity recorded as the annotation creator.")
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def extract_cmd(
    source_md: Path,
    model: str,
    input_path: Path | None,
    check_only: bool,
    actor: str,
    fmt: str,
) -> None:
    """Persist agent-extracted annotation candidates as anchored spans.

    Handles both statement (proposition/question/hypothesis) and figurative
    (metaphor/analogy) candidates in one mixed candidates.json. `--check` reports
    changed/unchanged without writing. Otherwise reads `--input candidates.json`,
    anchors each quote, and merges idempotently into `<citekey>.source.anno.trig`.
    """
    from science_tool.annotation.source_text import SourceTextError
    from science_tool.annotation.statement_extract import (
        CandidateError,
        check_source_changed,
        parse_candidates,
    )

    if check_only:
        if input_path is not None:
            raise click.ClickException("--check takes no --input")
        try:
            changed = check_source_changed(source_md=source_md, model=model)
        except SourceTextError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(json.dumps({"status": "changed" if changed else "unchanged"}))
        return

    if input_path is None:
        raise click.ClickException("--input <candidates.json> is required (or use --check)")
    try:
        candidates = parse_candidates(input_path.read_text(encoding="utf-8"))
    except CandidateError as exc:
        raise click.ClickException(str(exc)) from exc

    from science_tool.annotation.text_source_adapter import (
        TextSourceAdapterError,
        resolve_adapter,
    )

    try:
        adapter = resolve_adapter(source_md)
    except TextSourceAdapterError as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        report = adapter.extract(
            source_md=source_md, model=model, candidates=candidates,
            now=datetime.now(timezone.utc), actor=actor,
        )
    except SourceTextError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps({
            "written": report.written,
            "skipped": report.skipped,
            "grounding_dropped": report.grounding_dropped,
            "source_text_hash_recorded": report.source_text_hash_recorded,
            "note": report.note,
        }, indent=2))
    else:
        skips = ", ".join(f"{k}:{v}" for k, v in sorted(report.skipped.items())) or "none"
        click.echo(
            f"annotate extract: {report.written} annotation(s) written, "
            f"{report.grounding_dropped} grounding field(s) dropped, "
            f"skipped [{skips}], "
            f"hash recorded: {report.source_text_hash_recorded}"
        )
        if report.note:
            click.echo(report.note)


@annotate_group.command("promote")
@click.argument(
    "source_md",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--root", "root", default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: cwd). Used to scan the proposition corpus + write entities.",
)
@click.option("--paper-ref", "paper_ref", default=None,
              help="Resolvable paper entity ref (paper:<id>) recorded in source_refs. "
                   "Defaults to the source adapter's ref (paper:<citekey> for a "
                   "<citekey>.source.md); a source no adapter handles fails loud.")
@click.option("--apply", "do_apply", is_flag=True, default=False,
              help="Execute candidates (mint/link + backlink). Default is read-only.")
@click.option("--input", "input_path", default=None,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Edited candidates.json with curator overrides (use with --apply).")
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def promote_cmd(source_md: Path, root: Path | None, paper_ref: str | None,
                do_apply: bool, input_path: Path | None, fmt: str) -> None:
    """Promote statement annotations (proposition/question/hypothesis) into entities (mint-or-link)."""
    from science_tool.annotation.io import sidecar_for_markdown
    from science_tool.annotation.promote import (
        PromotionApplyError,
        PromotionOverrideError,
        PromotionReadError,
        apply_candidates,
        apply_overrides,
        build_targets,
        collect_promotable,
        decide_all,
        load_corpora,
    )
    from science_tool.annotation.query import read_sidecar_strict
    from science_tool.annotation.text_source_adapter import (
        TextSourceAdapterError,
        resolve_adapter,
    )

    if input_path is not None and not do_apply:
        raise click.ClickException("--input requires --apply (curator overrides only apply when writing)")

    project_root = (root or Path.cwd()).resolve()
    if paper_ref is None:
        try:
            paper_ref = resolve_adapter(source_md).source_ref(source_md)
        except TextSourceAdapterError as exc:
            raise click.ClickException(str(exc)) from exc

    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar_strict(sidecar_path)
    corpora, derived_refs = load_corpora(project_root)
    targets = build_targets()
    try:
        promotable, skipped = collect_promotable(sidecar, sidecar_path, project_root, derived_refs=derived_refs)
    except PromotionReadError as exc:
        raise click.ClickException(str(exc)) from exc
    candidates = decide_all(promotable, corpora, targets)

    if do_apply and input_path is not None:
        try:
            raw = json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"--input is not valid JSON: {exc}") from exc
        # Accept either the full read-only output object or a bare candidates list.
        edited_rows = raw.get("candidates") if isinstance(raw, dict) else raw
        if not isinstance(edited_rows, list):
            raise click.ClickException("--input must be the read-only output object or a candidates list")
        existing_refs = {
            f"{kind}:{slug}" for kind, corp in corpora.items() for slug in corp.existing_slugs
        }
        try:
            candidates = apply_overrides(candidates, edited_rows, existing_refs=existing_refs)
        except PromotionOverrideError as exc:
            raise click.ClickException(str(exc)) from exc

    rows = [{"annotation": c.ref, "kind": c.kind, "decision": c.decision, "slug": c.slug,
             "claim": c.claim[:80], "reason": c.reason} for c in candidates]

    if not do_apply:
        if fmt == "json":
            click.echo(json.dumps({"candidates": rows, "skipped": dict(skipped)}, indent=2))
        else:
            for r in rows:
                click.echo(f"{r['kind']:11} {r['decision']:9} {r['slug'] or '-':40} {r['annotation']}  {r['claim']}")
            click.echo(f"skipped: {dict(skipped) or 'none'}")
        return

    try:
        report = apply_candidates(candidates, sidecar_path=sidecar_path,
                                  project_root=project_root, paper_ref=paper_ref)
    except PromotionApplyError as exc:
        raise click.ClickException(str(exc)) from exc
    if fmt == "json":
        click.echo(json.dumps({"minted": report.minted, "linked": report.linked,
                               "skipped": dict(report.skipped) | dict(skipped),
                               "written": report.written_paths}, indent=2))
    else:
        click.echo(f"annotate promote: {report.minted} minted, {report.linked} linked, "
                   f"skipped {dict(report.skipped) | dict(skipped)}")


@annotate_group.command("synthesize")
@click.argument("source_md", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path),
              help="Project root (default: cwd). Used to read/write proposition entities.")
@click.option("--apply", "do_apply", is_flag=True, default=False,
              help="Apply the curator-reviewed --input candidates. Default is read-only scaffold.")
@click.option("--input", "input_path", default=None,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Edited candidates.json (required with --apply).")
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="json")
def synthesize_cmd(source_md: Path, root: Path | None, do_apply: bool,
                   input_path: Path | None, fmt: str) -> None:
    """Synthesize predicate/polarity/claim_layer on promoted propositions (curator-reviewed)."""
    from science_tool.annotation.io import sidecar_for_markdown
    from science_tool.annotation.promote import entity_dest
    from science_tool.annotation.query import entity_relpath_for_sidecar, read_sidecar_strict
    from science_tool.annotation.synthesize import (
        SynthesisApplyError,
        SynthesisReadError,
        apply_synthesis,
        build_scaffold,
        in_scope_propositions,
        parse_candidates_doc,
    )
    from science_tool.entities import _parse_markdown_file

    if do_apply and input_path is None:
        raise click.ClickException("--apply requires --input (the curator-reviewed candidates file)")
    if input_path is not None and not do_apply:
        raise click.ClickException("--input requires --apply")

    project_root = (root or Path.cwd()).resolve()
    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar_strict(sidecar_path)
    relpath = entity_relpath_for_sidecar(sidecar_path, project_root)

    def ref_for(frag: str) -> str:
        return f"annotation:{relpath}#{frag}"

    scope = in_scope_propositions(sidecar)
    # current frontmatter for each in-scope proposition (read once)
    current: dict[str, dict] = {}
    for prop_ref in scope:
        dest = entity_dest(prop_ref, project_root)
        if not dest.exists():
            raise click.ClickException(f"in-scope proposition {prop_ref} has no file at {dest}")
        current[prop_ref], _ = _parse_markdown_file(dest)

    if not do_apply:
        file_text = source_md.read_text(encoding="utf-8")
        scaffold, unresolved = build_scaffold(sidecar, file_text, current, ref_for=ref_for)
        if fmt == "json":
            click.echo(json.dumps(scaffold, indent=2))
        else:
            for e in scaffold["propositions"]:
                click.echo(f"{e['proposition']:50} statements={len(e['statements'])} "
                           f"hints={len(e['relation_hints'])}")
            click.echo(f"unresolved relation hints: {unresolved}")
        return

    assert input_path is not None
    try:
        doc = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--input is not valid JSON: {exc}") from exc
    scope_refs = {p: {ref_for(a.id) for a in anns} for p, anns in scope.items()}
    try:
        source, candidates = parse_candidates_doc(doc, scope_refs)
        report = apply_synthesis(candidates, current=current, project_root=project_root,
                                 source=source, in_scope=set(scope))
    except SynthesisReadError as exc:
        raise click.ClickException(str(exc)) from exc
    except SynthesisApplyError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps({"updated": report.updated, "skipped": dict(report.skipped),
                               "written": report.written_paths}, indent=2))
    else:
        click.echo(f"annotate synthesize: {report.updated} updated, "
                   f"skipped {dict(report.skipped) or 'none'}")

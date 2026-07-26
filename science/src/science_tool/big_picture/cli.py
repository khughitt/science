from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import click
from science_model.aspects import (
    SOFTWARE_ASPECT,
    load_project_aspects,
    matches_aspect_filter,
)

from science_tool.big_picture.digests import load_cluster_digests, member_to_digest
from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.knowledge_gaps import compute_topic_gaps
from science_tool.big_picture.layout import entity_dir
from science_tool.big_picture.resolver import resolve_questions
from science_tool.big_picture.synthesis_paths import resolve_synthesis_path
from science_tool.big_picture.validator import (
    validate_rollup_file,
    validate_synthesis_file,
)
from science_tool.output import emit


@click.group("big-picture")
def big_picture_group() -> None:
    """Tools supporting the /science:big-picture command."""


@big_picture_group.command("resolve-questions")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root (containing specs/, doc/, science.yaml).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="json",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout.",
)
def resolve_questions_cmd(project_root: Path, output_format: str, output_path: Path | None) -> None:
    """Emit question→hypothesis resolver output.

    Successful results are enveloped under ``questions`` (mirroring the empty-result
    shape below) so a ``truncation`` sibling key can never collide with a question id.
    """
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    sink = BoundedSink(
        lookup("big-picture resolve-questions"),
        output_path=output_path,
        command_path="big-picture resolve-questions",
        complete_via=build_complete_via(
            click.get_current_context(), output_hint=hint_for("resolve-questions", output_format)
        ),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete resolver report to {output_path}")
        if output_path is not None
        else None
    )

    results = resolve_questions(project_root)
    if not results:
        payload: dict[str, object] = {
            "status": "empty",
            "reason": "no question entities found",
            "questions": {},
        }

        def _render_empty() -> None:
            sink.echo("no question entities found")

        emit(output_format=output_format, payload=payload, render_text=_render_empty, sink=sink, sort_keys=True)
        sink.flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    rows = sorted(results.items())
    projected = project_rows(rows, sink.max_rows)
    displayed = projected.rows

    payload = {"questions": {qid: asdict(out) for qid, out in displayed}}
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via,
        }

    def _render_table() -> None:
        for qid, out in displayed:
            primary = out.primary_hypothesis or "-"
            hyps = ", ".join(h.id for h in out.hypotheses) or "-"
            sink.echo(f"{qid}: primary={primary} hypotheses=[{hyps}]")
        if projected.truncated:
            sink.echo(f"showing {len(displayed)} of {projected.total} questions")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=output_format, payload=payload, render_text=_render_table, sink=sink, sort_keys=True)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@big_picture_group.command("synthesis-path")
@click.argument("hypothesis_id")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root.",
)
def synthesis_path_cmd(hypothesis_id: str, project_root: Path) -> None:
    """Print the synthesis entity path for HYPOTHESIS_ID.

    An existing `report_kind: hypothesis-synthesis` entity whose `hypothesis:` frontmatter
    names this hypothesis wins, whatever its filename -- numbered-entity projects bind the
    two by frontmatter, not by name. Falls back to `<hyp-id>.md` only when none exists.

    The orchestrator passes this path to the sub-agent instead of composing one, which is
    what created duplicate synthesis entities in mm30 and natural-systems
    (fb-2026-07-11-013, -002).
    """
    click.echo(str(resolve_synthesis_path(project_root, hypothesis_id)))


@big_picture_group.command("validate")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root.",
)
@click.option(
    "--staged",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=None,
    help=(
        "Validate generated files in this staging directory instead of entities/synthesis/, "
        "BEFORE they are reconciled into canonical entities. References are still checked "
        "against --project-root."
    ),
)
def validate_cmd(project_root: Path, staged: Path | None) -> None:
    """Validate generated big-picture synthesis files in this project.

    With ``--staged``, validate files in a staging directory BEFORE they are reconciled
    into canonical entities. Validation was strictly post-hoc, so a truncated ID was only
    caught after the canonical entities had already been overwritten and every repair had
    to be done against published files (fb-2026-07-11-003).

    The known-ID corpus always comes from ``--project-root``: staged files are checked
    against the real project, which is the whole point.
    """
    # v3 canonical layout: synthesis artifacts are `synthesis` entities under
    # entities/synthesis/. The rollup is identified by its report_kind rather
    # than a fixed filename; per-hypothesis and emergent-threads files are
    # validated as synthesis files.
    synthesis_dir = staged if staged is not None else entity_dir(project_root, "synthesis")

    issues = []
    unchecked: list[tuple[Path, str]] = []
    if synthesis_dir.is_dir():
        for path in sorted(synthesis_dir.glob("*.md")):
            fm = read_frontmatter(path) or {}
            if fm.get("report_kind") == "synthesis-rollup":
                result = validate_rollup_file(path, project_root=project_root)
            else:
                result = validate_synthesis_file(path, project_root=project_root)
            if result.status == "unwired":
                unchecked.append((path, result.reason or result.code or "unknown"))
            else:
                issues.extend(result.rows)

    for issue in issues:
        click.echo(f"[{issue.kind}] {issue.path.name}: {issue.message}")
    for path, reason in unchecked:
        click.echo(f"[not-checked] {path.name}: {reason}", err=True)

    # A file that could NOT be checked exits non-zero. Silence here would mean this
    # command passing green over a rollup it never read.
    if issues or unchecked:
        raise click.exceptions.Exit(code=1)


@big_picture_group.command("knowledge-gaps")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root.",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="Cap the JSON list to the top N entries (default: no limit).",
)
def knowledge_gaps_cmd(project_root: Path, limit: int | None) -> None:
    """Emit legacy topic-coverage gaps as JSON.

    Applies the same research-only aspect filter used by big-picture synthesis
    (excluding pure software-only questions) before computing demand over
    existing authored topic docs.
    """
    resolved = resolve_questions(project_root)
    try:
        project_aspects = load_project_aspects(project_root)
    except FileNotFoundError:
        project_aspects = []
    research_filter = {a for a in project_aspects if a != SOFTWARE_ASPECT}
    if research_filter:
        included = {
            qid for qid, out in resolved.items() if matches_aspect_filter(out.resolved_aspects, research_filter)
        }
    else:
        # No non-software project aspects declared → include everything.
        included = set(resolved)
    result = compute_topic_gaps(project_root, resolved, included)
    if result.status == "unwired":
        # The instrument did not run. Emitting [] here would report FULL topic
        # coverage on a project whose topic refs all dangle -- the silent-instrument
        # bug. Fail loudly instead; an empty list on stdout must always mean "no gaps".
        raise click.ClickException(f"knowledge-gaps did not run ({result.code}): {result.reason}")
    if result.reason:
        # A caveat rides along on a SUCCESSFUL run: part of the input was silently
        # dropped. It goes to stderr so stdout stays a parseable list of gaps.
        click.echo(f"notice ({result.code}): {result.reason}", err=True)
    gaps = result.rows
    if limit is not None:
        gaps = gaps[:limit]
    emit(output_format="json", payload=[asdict(g) for g in gaps], render_text=lambda: None, sort_keys=True)


@big_picture_group.command("cluster-digests")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root.",
)
@click.option(
    "--deep",
    is_flag=True,
    default=False,
    help="Attach index-only member summaries (id/kind/title/digest_insight) per digest.",
)
def cluster_digests_cmd(project_root: Path, deep: bool) -> None:
    """Emit the cluster-digest registry + member->digest map as JSON.

    Recognition surface for /science:big-picture: substitute one digest for its N
    archived members (and label it); --deep descends into the members index-only.
    """
    digests = load_cluster_digests(project_root, deep=deep)
    payload = {
        "digests": {did: asdict(cd) for did, cd in sorted(digests.items())},
        "member_to_digest": member_to_digest(project_root),
    }
    emit(output_format="json", payload=payload, render_text=lambda: None, sort_keys=True)

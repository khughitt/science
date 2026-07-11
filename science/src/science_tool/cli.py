from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click

from science_tool.annotation.cli import annotate_group
from science_tool.belief_cli import belief_group
from science_tool.benchmark_cli import benchmark_group
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
from science_tool.entities import list_entities
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
from science_tool.output import OUTPUT_FORMATS, emit, emit_query_rows
from science_tool.patch.cli import patch_group
from science_tool.peers_cli import peers_group
from science_tool.project_artifacts.cli import artifacts_group as _artifacts_group
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

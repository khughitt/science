from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import click

from science_tool.causal.export_chirho import export_chirho_script
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.datasets import available_adapters, get_adapter, search_all
from science_tool.datasets.validate import validate_data_packages
from science_tool.distill.openalex import distill_openalex
from science_tool.distill.pykeen_source import distill_pykeen
from science_tool.doi import lookup_doi_metadata
from science_tool.graph.materialize import materialization_audit, materialize_graph
from science_tool.graph.migrate import (
    audit_project_graph,
    rewrite_project_ids_in_sources,
    write_migration_report,
    write_local_sources,
)
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    GRAPH_LAYERS,
    PropositionEvidenceLine,
    add_article,
    add_assumption,
    add_concept,
    add_discussion,
    add_edge,
    add_evidence_edge,
    add_falsification,
    add_finding,
    add_hypothesis,
    add_inquiry,
    add_inquiry_edge,
    add_inquiry_node,
    add_interpretation,
    add_observation,
    add_paper_entity,
    add_proposition,
    add_question,
    add_story,
    add_transformation,
    build_graph_dot,
    diff_graph_inputs,
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
    set_boundary_role,
    set_treatment_outcome,
    shorten_uri,
    stamp_revision,
    validate_graph,
    validate_inquiry,
)
from science_tool.output import OUTPUT_FORMATS, emit_query_rows
from science_tool.prose import scan_prose
from science_tool.refs import check_refs
from science_tool.research_package.cli import research_package_group


@click.group()
def main() -> None:
    """Science CLI tools."""


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


def _parse_interaction_terms(entries: tuple[str, ...]) -> list[dict[str, str]] | None:
    if not entries:
        return None

    interaction_terms: list[dict[str, str]] = []
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
        interaction_term: dict[str, str] = {
            "modifier": modifier,
            "effect": effect,
        }
        note = parsed.get("note")
        if isinstance(note, str) and note.strip():
            interaction_term["note"] = note
        interaction_terms.append(interaction_term)
    return interaction_terms


main.add_command(research_package_group)


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
def graph_build(project_root: Path) -> None:
    """Materialize graph.trig from structured upstream project sources."""
    import yaml as _yaml

    from science_tool.registry.config import ensure_registered

    _project_root = Path.cwd() if str(project_root) == "." else project_root
    _science_yaml = _project_root / "science.yaml"
    if _science_yaml.is_file():
        _project_name = (_yaml.safe_load(_science_yaml.read_text()) or {}).get("name", _project_root.name)
        ensure_registered(_project_root, str(_project_name))

    try:
        trig_path = materialize_graph(project_root)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Materialized graph at {trig_path}")

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


@graph.command("migrate")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def graph_migrate(output_format: str, project_root: Path) -> None:
    """Rewrite alias-based refs, scaffold local sources, and persist a migration audit report."""

    project_root = project_root.resolve()
    initial_report = audit_project_graph(project_root)
    rewritten_files = rewrite_project_ids_in_sources(project_root, initial_report["alias_map"])
    write_local_sources(project_root, dict(initial_report))

    final_report = audit_project_graph(project_root)
    final_report_payload: dict[str, Any] = dict(final_report)
    final_report_payload["rewritten_files"] = rewritten_files
    final_report_payload["rewritten_file_count"] = len(rewritten_files)
    report_path = write_migration_report(project_root, final_report_payload)
    final_report_payload["report_path"] = str(report_path)

    if output_format == "json":
        click.echo(json.dumps(final_report_payload, indent=2, sort_keys=True))
    else:
        emit_query_rows(
            output_format=output_format,
            title="Graph Migration Audit",
            columns=[
                ("check", "Check"),
                ("status", "Status"),
                ("source", "Source"),
                ("field", "Field"),
                ("target", "Target"),
                ("details", "Details"),
            ],
            rows=[dict(row) for row in final_report["rows"]],
        )
        click.echo(f"Report: {report_path}")
        click.echo(f"Rewritten files: {len(rewritten_files)}")

    if final_report["has_failures"]:
        raise click.exceptions.Exit(1)


@graph.command("migrate-model")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def graph_migrate_model(project_root: Path) -> None:
    """Migrate project sources from old entity model to Project Model."""
    from science_tool.graph.project_model_migration import migrate_entity_sources

    project_root = project_root.resolve()
    stats = migrate_entity_sources(project_root)
    click.echo(
        f"Migration complete: {stats['migrated']} migrated, {stats['skipped']} skipped, {stats['errors']} errors"
    )
    if stats["errors"] > 0:
        click.echo("Review errors manually — some files may need manual migration.")


@graph.command("migrate-tags")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option("--apply", is_flag=True, default=False, help="Write changes to disk (default is dry-run).")
def graph_migrate_tags(project_root: Path, apply: bool) -> None:
    """Rewrite legacy `tags:` frontmatter into `related:` topic refs in-place.

    Entity frontmatter: `tags: [genomics]` → adds `topic:genomics` to `related`, removes `tags:` line.
    Task markdown: same idea for `- tags: [foo]` in tasks/active.md and tasks/done/*.md.
    Dry-run by default; pass --apply to actually write.
    """
    from science_tool.graph.tags_migration import migrate_tags_to_related

    project_root = project_root.resolve()
    report = migrate_tags_to_related(project_root, apply=apply)

    if not report.entity_files and not report.task_files and not report.errors:
        click.echo("No legacy tags found — nothing to migrate.")
        return

    prefix = "Would migrate" if not apply else "Migrated"
    for fm in report.entity_files:
        rel = fm.path.relative_to(project_root) if fm.path.is_absolute() else fm.path
        added = ", ".join(fm.added_to_related) if fm.added_to_related else "(no new refs)"
        click.echo(f"{prefix}: {rel}  tags={fm.tag_values} → related+={added}")

    for task_file in report.task_files:
        rel = task_file.relative_to(project_root) if task_file.is_absolute() else task_file
        click.echo(f"{prefix}: {rel}  (task file re-rendered)")

    for path, err in report.errors:
        rel = path.relative_to(project_root) if path.is_absolute() else path
        click.echo(f"ERROR: {rel}: {err}", err=True)

    total = len(report.entity_files) + len(report.task_files)
    action = "Migrated" if apply else "Would migrate"
    click.echo(f"\n{action} {total} file(s).")
    if not apply:
        click.echo("Re-run with --apply to write changes.")
    if report.errors:
        raise click.exceptions.Exit(1)


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
            ("belief_state", "Belief State"),
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
    click.echo(f"Added article: {uri}")


@graph_add.command("proposition")
@click.argument("text")
@click.option("--source", required=True, help="Provenance reference")
@click.option("--confidence", type=float, default=None)
@click.option("--evidence-type", default=None)
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
        interaction_terms=cast(list[dict[str, str]] | None, interaction_terms),
        bridge_between_refs=list(bridge_between_refs) if bridge_between_refs else None,
    )
    click.echo(f"Added proposition: {uri}")


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
        source=source,
        status=status,
    )
    click.echo(f"Added hypothesis: {hypothesis_uri}")


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
        source=source,
        maturity=maturity,
        status=status,
        related=list(related_refs) if related_refs else None,
    )
    click.echo(f"Added question: {question_uri}")


@graph_add.command("edge")
@click.argument("subject")
@click.argument("predicate")
@click.argument("object")
@click.option("--graph", "graph_layer", type=click.Choice(GRAPH_LAYERS), default="graph/knowledge", show_default=True)
@click.option("--claim", "claim_refs", multiple=True, help="Supporting relation claim reference (repeatable)")
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


@main.group()
def inquiry() -> None:
    """Inquiry subgraph commands."""


@inquiry.command("init")
@click.argument("slug")
@click.option("--label", required=True)
@click.option("--target", required=True, help="Target hypothesis or question (e.g. hypothesis:h01)")
@click.option("--description", default="")
@click.option(
    "--status",
    default="sketch",
    type=click.Choice(["sketch", "specified", "planned", "in-progress", "complete"]),
)
@click.option("--type", "inquiry_type", default="general", type=click.Choice(["general", "causal"]), show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_init(
    slug: str, label: str, target: str, description: str, status: str, inquiry_type: str, graph_path: Path
) -> None:
    """Create a new inquiry subgraph."""
    try:
        uri = add_inquiry(graph_path, slug, label, target, description, status, inquiry_type=inquiry_type)
        click.echo(f"Created inquiry: {shorten_uri(str(uri))}")
    except ValueError as e:
        raise click.ClickException(str(e))


@inquiry.command("add-node")
@click.argument("slug")
@click.argument("entity")
@click.option("--role", required=False, type=click.Choice(["BoundaryIn", "BoundaryOut"]), default=None)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_node(slug: str, entity: str, role: str | None, graph_path: Path) -> None:
    """Add a node to an inquiry, optionally with a boundary role."""
    try:
        if role:
            set_boundary_role(graph_path, slug, entity, role)
            click.echo(f"Set {entity} as {role} in inquiry/{slug}")
        else:
            add_inquiry_node(graph_path, slug, entity)
            click.echo(f"Added {entity} as interior node in inquiry/{slug}")
    except ValueError as e:
        raise click.ClickException(str(e))


@inquiry.command("add-edge")
@click.argument("slug")
@click.argument("subject")
@click.argument("predicate")
@click.argument("object", metavar="OBJECT")
@click.option("--claim", "claim_refs", multiple=True, help="Supporting relation claim reference (repeatable)")
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
    try:
        s, p, o = add_inquiry_edge(
            graph_path, slug, subject, predicate, object, list(claim_refs) if claim_refs else None
        )
        click.echo(f"Added edge: {shorten_uri(str(s))} --[{shorten_uri(str(p))}]--> {shorten_uri(str(o))}")
    except ValueError as e:
        raise click.ClickException(str(e))


@inquiry.command("add-assumption")
@click.argument("slug")
@click.argument("label")
@click.option("--source", required=True, help="Evidence source (e.g. paper:doi_...)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_assumption(slug: str, label: str, source: str, graph_path: Path) -> None:
    """Add an assumption to an inquiry with provenance."""
    try:
        uri = add_assumption(graph_path, label=label, source=source, inquiry_slug=slug)
        click.echo(f"Added assumption: {shorten_uri(str(uri))} in inquiry/{slug}")
    except ValueError as e:
        raise click.ClickException(str(e))


@inquiry.command("add-transformation")
@click.argument("slug")
@click.argument("label")
@click.option("--tool", default="", help="Tool or library name")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_transformation(slug: str, label: str, tool: str, graph_path: Path) -> None:
    """Add a transformation step to an inquiry."""
    try:
        uri = add_transformation(graph_path, label=label, inquiry_slug=slug, tool=tool)
        click.echo(f"Added transformation: {shorten_uri(str(uri))} in inquiry/{slug}")
    except ValueError as e:
        raise click.ClickException(str(e))


@inquiry.command("set-estimand")
@click.argument("slug")
@click.option("--treatment", required=True, help="Treatment variable (e.g. concept/drug)")
@click.option("--outcome", required=True, help="Outcome variable (e.g. concept/recovery)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_set_estimand(slug: str, treatment: str, outcome: str, graph_path: Path) -> None:
    """Set treatment and outcome variables for a causal inquiry."""
    try:
        set_treatment_outcome(graph_path, slug, treatment=treatment, outcome=outcome)
        click.echo(f"Set estimand for inquiry/{slug}: treatment={treatment}, outcome={outcome}")
    except ValueError as e:
        raise click.ClickException(str(e))


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
def refs() -> None:
    """Cross-reference validation commands."""


@refs.command("check")
@click.option("--root", "root_path", default=".", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option("--strict", is_flag=True, help="Exit with error on any broken ref (not just markers)")
def refs_check(root_path: Path, output_format: str, strict: bool) -> None:
    """Scan project documents for broken cross-references."""

    issues = check_refs(root_path.resolve())

    broken = [i for i in issues if i.ref_type != "marker"]
    markers = [i for i in issues if i.ref_type == "marker"]

    if output_format == "json":
        import json

        click.echo(
            json.dumps(
                {
                    "broken": [
                        {
                            "file": i.file,
                            "line": i.line,
                            "type": i.ref_type,
                            "value": i.ref_value,
                            "message": i.message,
                            "suggestion": i.suggestion,
                        }
                        for i in broken
                    ],
                    "markers": [{"file": i.file, "line": i.line, "value": i.ref_value} for i in markers],
                },
                indent=2,
            )
        )
    else:
        if broken:
            click.echo(f"refs check: {len(broken)} broken, {len(markers)} unresolved markers\n")
            for issue in broken:
                click.echo(f"  {issue.file}:{issue.line}")
                click.echo(f"    {issue.message}")
                if issue.suggestion:
                    click.echo(f"    Suggestion: {issue.suggestion}")
                click.echo()
        elif markers:
            click.echo(f"refs check: 0 broken, {len(markers)} unresolved markers\n")
        else:
            click.echo("refs check: all references valid, no unresolved markers")
            return

        if markers:
            unverified = [m for m in markers if m.ref_value == "[UNVERIFIED]"]
            needs_cite = [m for m in markers if m.ref_value == "[NEEDS CITATION]"]
            click.echo("  Unresolved markers:")
            if unverified:
                locs = ", ".join(f"{m.file}:{m.line}" for m in unverified)
                click.echo(f"    {len(unverified)}x [UNVERIFIED] ({locs})")
            if needs_cite:
                locs = ", ".join(f"{m.file}:{m.line}" for m in needs_cite)
                click.echo(f"    {len(needs_cite)}x [NEEDS CITATION] ({locs})")

    if broken:
        raise click.exceptions.Exit(1)
    if strict and markers:
        raise click.exceptions.Exit(1)


@main.group()
def datasets() -> None:
    """Dataset discovery and download commands."""


@datasets.command("sources")
def datasets_sources() -> None:
    """List available dataset adapters."""
    adapters = available_adapters()
    if not adapters:
        click.echo("No dataset adapters available. Install with: uv add science-tool[datasets]")
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
    results = search_all(query, sources=sources, max_per_source=max_results)
    if not results:
        click.echo("No datasets found.")
        return

    rows = [
        {
            "source": r.source,
            "id": r.id,
            "title": r.title[:80],
            "year": r.year or "",
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
            ("title", "Title"),
            ("year", "Year"),
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
    results = validate_data_packages(data_path)
    emit_query_rows(
        output_format=output_format,
        title="Data Validation",
        columns=[("check", "Check"), ("status", "Status"), ("details", "Details")],
        rows=results,
    )
    if any(r["status"] == "fail" for r in results):
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
def distill_openalex_cmd(level: str, output_path: Path | None) -> None:
    """Fetch OpenAlex science hierarchy and write Turtle snapshot."""

    result = distill_openalex(level=level, output_path=output_path)
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
@click.option("--type", "task_type", required=True, type=click.Choice(["research", "dev"]))
@click.option("--priority", required=True, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--related", multiple=True)
@click.option("--blocked-by", multiple=True)
@click.option("--group", default="")
@click.option("--description", default="")
def tasks_add(
    title: str,
    task_type: str,
    priority: str,
    related: tuple[str, ...],
    blocked_by: tuple[str, ...],
    group: str,
    description: str,
) -> None:
    """Add a new task."""
    from science_tool.tasks import add_task

    task = add_task(
        tasks_dir=DEFAULT_TASKS_DIR,
        title=title,
        task_type=task_type,
        priority=priority,
        related=list(related) or None,
        blocked_by=list(blocked_by) or None,
        group=group,
        description=description,
    )
    click.echo(f"Created [{task.id}] {task.title}")


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


@tasks.command("block")
@click.argument("task_id")
@click.option("--by", "blocked_by", required=True)
def tasks_block(task_id: str, blocked_by: str) -> None:
    """Block a task."""
    from science_tool.tasks import block_task

    try:
        task = block_task(DEFAULT_TASKS_DIR, task_id, blocked_by=blocked_by)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] blocked by {blocked_by}")


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


@tasks.command("edit")
@click.argument("task_id")
@click.option("--priority", default=None, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--status", default=None, type=click.Choice(["proposed", "active", "blocked", "deferred", "retired"]))
@click.option("--type", "task_type", default=None, type=click.Choice(["research", "dev"]))
@click.option("--related", multiple=True)
@click.option("--group", default=None)
def tasks_edit(
    task_id: str,
    priority: str | None,
    status: str | None,
    task_type: str | None,
    related: tuple[str, ...],
    group: str | None,
) -> None:
    """Edit a task's fields."""
    from science_tool.tasks import edit_task

    try:
        task = edit_task(
            DEFAULT_TASKS_DIR,
            task_id,
            priority=priority,
            status=status,
            task_type=task_type,
            related=list(related) if related else None,
            group=group,
        )
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] updated")


@tasks.command("list")
@click.option("--type", "task_type", default=None, type=click.Choice(["research", "dev"]))
@click.option("--priority", default=None, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option(
    "--status",
    default=None,
    type=click.Choice(["proposed", "active", "blocked", "deferred", "retired", "done"]),
)
@click.option("--related", default=None)
@click.option("--group", default=None, help="Filter by group (exact match)")
@click.option("--all", "show_all", is_flag=True, default=False, help="Include done and retired tasks")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def tasks_list(
    task_type: str | None,
    priority: str | None,
    status: str | None,
    related: str | None,
    group: str | None,
    show_all: bool,
    output_format: str,
) -> None:
    """List tasks. Done/retired tasks are hidden by default; use --all or --status=done to include them."""
    from science_tool.tasks import list_tasks
    from science_tool.tasks_display import render_tasks_table, sort_tasks

    matched = list_tasks(
        DEFAULT_TASKS_DIR,
        task_type=task_type,
        priority=priority,
        status=status,
        related=related,
        group=group,
        include_done=show_all,
    )
    matched = sort_tasks(matched)

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
        rows = [
            {
                "id": t.id,
                "title": t.title,
                "type": t.type,
                "priority": t.priority,
                "status": t.status,
                "group": t.group,
                "related": ", ".join(t.related),
                "created": t.created.isoformat(),
            }
            for t in matched
        ]
        emit_query_rows(output_format=output_format, title="Tasks", columns=columns, rows=rows)
    else:
        render_tasks_table(matched)


@tasks.command("show")
@click.argument("task_id")
def tasks_show(task_id: str) -> None:
    """Show full details of a task."""
    from science_tool.tasks import parse_tasks, render_task

    active = parse_tasks(DEFAULT_TASKS_DIR / "active.md")
    matching = [t for t in active if t.id == task_id]
    if not matching:
        raise click.ClickException(f"Task {task_id} not found in active.md")
    click.echo(render_task(matching[0]))


@tasks.command("summary")
def tasks_summary() -> None:
    """Print summary counts by status, type, priority, and group."""
    from collections import Counter

    from science_tool.tasks import parse_tasks, warn_invalid_statuses

    active = parse_tasks(DEFAULT_TASKS_DIR / "active.md")
    if not active:
        click.echo("No active tasks.")
        return

    warn_invalid_statuses(active)

    by_status = Counter(t.status for t in active)
    by_type = Counter(t.type for t in active)
    by_priority = Counter(t.priority for t in active)
    by_group = Counter(t.group for t in active if t.group)

    click.echo(f"Total: {len(active)}")
    click.echo("By status:   " + ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items())))
    click.echo("By type:     " + ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items())))
    click.echo("By priority: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_priority.items())))
    if by_group:
        click.echo("By group:    " + ", ".join(f"{k}: {v}" for k, v in sorted(by_group.items())))


@main.group()
def project() -> None:
    """Project-level commands."""


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
    import yaml as _yaml

    from science_tool.paths import resolve_paths

    project_root = project_root.resolve()
    paths = resolve_paths(project_root)

    rows: list[dict[str, str]] = []

    # Scan hypotheses
    hyp_dir = paths.specs_dir / "hypotheses"
    if hyp_dir.is_dir():
        for md in sorted(hyp_dir.glob("*.md")):
            title, status = _extract_title_status(md, _yaml)
            rows.append(
                {
                    "kind": "hypothesis",
                    "file": md.relative_to(project_root).as_posix(),
                    "title": title,
                    "status": status,
                }
            )

    # Scan questions
    q_dir = paths.doc_dir / "questions"
    if q_dir.is_dir():
        for md in sorted(q_dir.glob("*.md")):
            title, status = _extract_title_status(md, _yaml)
            rows.append(
                {"kind": "question", "file": md.relative_to(project_root).as_posix(), "title": title, "status": status}
            )

    emit_query_rows(
        output_format=output_format,
        title="Project Index",
        columns=[
            ("kind", "Kind"),
            ("file", "File"),
            ("title", "Title"),
            ("status", "Status"),
        ],
        rows=rows,
    )


def _extract_title_status(path: Path, _yaml: Any) -> tuple[str, str]:
    """Extract title and status from markdown frontmatter or first heading."""
    text = path.read_text(encoding="utf-8")
    title = path.stem
    status = ""

    # Try frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                fm = _yaml.safe_load(text[3:end])
                if isinstance(fm, dict):
                    title = str(fm.get("title") or title)
                    status = str(fm.get("status") or "")
            except _yaml.YAMLError:
                pass

    # Fallback: first H1/H2 heading
    if title == path.stem:
        for line in text.splitlines():
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break

    return title, status


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
            click.echo(f"  {len(config.projects)} registered project(s). Run `science-tool sync run`.")
        return

    days = (datetime.now() - state.last_sync).days
    click.echo(f"Last sync: {state.last_sync.isoformat()} ({days} days ago)")
    stale_threshold = config.sync.stale_after_days
    if days > stale_threshold:
        click.echo(f"  Sync is stale (threshold: {stale_threshold} days). Run `science-tool sync run`.")
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


# ── feedback ────────────────────────────────────────────────────────────────

_FB_CATEGORIES = ("friction", "gap", "guidance", "suggestion", "positive")
_FB_STATUSES = ("open", "addressed", "deferred", "wontfix")


@main.group()
def feedback() -> None:
    """Feedback management commands."""


def _get_feedback_dir() -> Path:
    import os

    from science_tool.registry.config import get_science_config_dir

    return Path(os.environ.get("SCIENCE_FEEDBACK_DIR", str(get_science_config_dir() / "feedback")))


@feedback.command("add")
@click.option("--target", required=True, help="What the feedback is about (e.g., command:interpret-results)")
@click.option("--summary", required=True, help="One-line description")
@click.option("--category", default="suggestion", type=click.Choice(_FB_CATEGORIES))
@click.option("--detail", default=None, help="Optional prose detail")
@click.option("--project", default=None, help="Project name (auto-detected if omitted)")
@click.option("--related", multiple=True, help="Related feedback entry IDs")
def feedback_add(
    target: str,
    summary: str,
    category: str,
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
def feedback_triage(target: str | None) -> None:
    """Show open entries grouped by target for triage."""
    from science_tool.feedback import group_for_triage

    fb_dir = _get_feedback_dir()
    groups = group_for_triage(fb_dir, target=target)

    if not groups:
        click.echo("No open feedback entries.")
        return

    for target_key, group in groups.items():
        n_projects = len(group["projects"])
        n_entries = len(group["entries"])
        total_recur = group["total_recurrence"]
        projects_str = ", ".join(sorted(group["projects"])) if group["projects"] else "unknown"
        click.echo(
            f"\n## {target_key}  ({n_entries} entries, {total_recur} recurrences, {n_projects} projects: {projects_str})"
        )
        for entry in group["entries"]:
            click.echo(f"  - {entry.id} [{entry.category}] {entry.summary}")


@feedback.command("report")
@click.option("--status", default=None, help="Filter by status")
@click.option("--project", default=None, help="Filter by project")
def feedback_report(status: str | None, project: str | None) -> None:
    """Generate a markdown report of feedback entries."""
    from science_tool.feedback import render_report

    fb_dir = _get_feedback_dir()
    report = render_report(fb_dir, status=status, project=project)
    click.echo(report)


if __name__ == "__main__":
    main()

"""`science graph` command group — knowledge-graph build, query, and inspection."""

from __future__ import annotations

from pathlib import Path

import click

from science_tool.graph.build import build_project_graph
from science_tool.graph.cross_impact import query_cross_impact
from science_tool.graph.materialize import materialization_audit
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    GRAPH_LAYERS,
    build_graph_dot,
    diff_graph_inputs,
    export_graph_payload,
    init_graph_file,
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
    validate_graph,
)
from science_tool.output import OUTPUT_FORMATS, emit, emit_query_rows, unwrap_instrument, unwrap_verdict
from science_tool.prose import scan_prose


@click.group("graph")
def graph_group() -> None:
    """Knowledge graph commands."""


@graph_group.command("init")
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


@graph_group.command("build")
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
@click.option(
    "--no-commons",
    is_flag=True,
    help=(
        "Self-contained build: do not consult the commons store at all. The graph omits "
        "commons-owned entities and commons overlays. Orthogonal to --local-only (which is about "
        "the composite refresh). Without this flag, a project that references commons ids and has "
        "no reachable store fails rather than silently building a partial graph."
    ),
)
def graph_build(project_root: Path, local_only: bool, no_commons: bool) -> None:
    """Materialize graph.trig and, unless skipped, composite.trig from structured project sources."""
    from science_tool.graph.composite import assemble_composite_graph
    from science_tool.peers import PeerNotFound, PeerUnresolved

    _project_root = Path.cwd() if str(project_root) == "." else project_root
    try:
        result = build_project_graph(_project_root, include_commons=not no_commons)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _cfg = result.config
    click.echo(f"Materialized local graph at {result.local_path}")
    if no_commons:
        # Loud on stdout so a self-contained graph is never silently mistaken for full coverage:
        # commons-owned entities and overlays are absent by request, not because none applied.
        click.echo("Self-contained build (--no-commons): commons entities and overlays were NOT consulted")

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
        sources = load_project_sources(project_root, include_commons=not no_commons)
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


@graph_group.command("propagate-freshness")
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


@graph_group.command("audit")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_audit(output_format: str, project_root: Path, output_path: Path | None) -> None:
    """Audit canonical source references before graph materialization."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    rows, has_failures = unwrap_verdict(materialization_audit(project_root), what="graph audit")
    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("graph-audit", output_format))
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(lookup("graph audit"), output_path=output_path, command_path="graph audit", complete_via=complete_via)
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
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
    if has_failures:
        raise click.exceptions.Exit(1)


@graph_group.command("stats")
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


@graph_group.command("validate")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_validate(output_format: str, graph_path: Path) -> None:
    """Run structural validation checks on graph.trig."""

    rows, has_failures = unwrap_verdict(validate_graph(graph_path), what="graph validate")
    emit_query_rows(
        output_format=output_format,
        title="Graph Validation",
        columns=[("check", "Check"), ("status", "Status"), ("details", "Details")],
        rows=rows,
    )
    if has_failures:
        raise click.exceptions.Exit(1)


@graph_group.command("diff")
@click.option("--mode", type=click.Choice(("hybrid", "mtime", "hash")), default="hybrid", show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_diff(mode: str, output_format: str, graph_path: Path, output_path: Path | None) -> None:
    """Show files that are stale relative to graph revision metadata."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    rows = unwrap_instrument(diff_graph_inputs(graph_path=graph_path, mode=mode), what="graph diff")
    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("graph-diff", output_format))
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(lookup("graph diff"), output_path=output_path, command_path="graph diff", complete_via=complete_via)
    emit_query_rows(
        output_format=output_format,
        title="Graph Diff",
        columns=[("path", "Path"), ("status", "Status"), ("reason", "Reason")],
        rows=rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("predicates")
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


@graph_group.command("neighborhood")
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

    rows = unwrap_instrument(
        query_neighborhood(
            graph_path=graph_path,
            center=center,
            hops=hops,
            graph_layer=graph_layer,
            limit=limit,
        ),
        what="graph neighborhood",
    )
    emit_query_rows(
        output_format=output_format,
        title="Graph Neighborhood",
        columns=[("subject", "Subject"), ("predicate", "Predicate"), ("object", "Object")],
        rows=rows,
    )


@graph_group.command("claims")
@click.option("--about", required=True)
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_claims(about: str, limit: int, output_format: str, graph_path: Path) -> None:
    """Return claims mentioning a term/entity."""

    rows = unwrap_instrument(query_claims(graph_path=graph_path, about=about, limit=limit), what="graph claims")
    emit_query_rows(
        output_format=output_format,
        title="Graph Claims",
        columns=[("claim", "Claim"), ("text", "Text"), ("sources", "Sources")],
        rows=rows,
    )


@graph_group.command("evidence")
@click.argument("target_ref")
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_evidence(target_ref: str, limit: int, output_format: str, graph_path: Path) -> None:
    """Return support/dispute evidence for a claim, or aggregate claim-backed evidence for a hypothesis."""

    rows = unwrap_instrument(
        query_evidence(graph_path=graph_path, target_ref=target_ref, limit=limit), what="graph evidence"
    )
    emit_query_rows(
        output_format=output_format,
        title="Graph Evidence",
        columns=[("evidence", "Evidence"), ("relation", "Relation"), ("text", "Text"), ("sources", "Sources")],
        rows=rows,
    )


@graph_group.command("cross-impact")
@click.argument("target_ref")
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_cross_impact(target_ref: str, limit: int, output_format: str, graph_path: Path) -> None:
    """Show conservative cross-impact for a proposition or evidence line."""

    payload = query_cross_impact(graph_path=graph_path, target_ref=target_ref, limit=limit)

    def _render() -> None:
        emit_query_rows(
            output_format=output_format,
            title=f"Cross Impact: {payload['target']} ({payload['scope']})",
            columns=[
                ("dependent_proposition", "Dependent Proposition"),
                ("dependent_text", "Text"),
                ("relation", "Relation"),
                ("hypotheses", "Hypotheses"),
                ("questions", "Questions"),
                ("scope", "Scope"),
                ("scope_reason", "Reason"),
            ],
            rows=payload["rows"],
        )

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


@graph_group.command("coverage")
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_coverage(limit: int, output_format: str, graph_path: Path) -> None:
    """Show variables with/without dataset links and observedness status."""

    rows = unwrap_instrument(query_coverage(graph_path=graph_path, limit=limit), what="graph coverage")
    emit_query_rows(
        output_format=output_format,
        title="Graph Coverage",
        columns=[("entity", "Entity"), ("label", "Label"), ("measured", "Measured"), ("observed", "Observed")],
        rows=rows,
    )


@graph_group.command("gaps")
@click.argument("center")
@click.option("--hops", type=int, default=2, show_default=True)
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_gaps(center: str, hops: int, limit: int, output_format: str, graph_path: Path, output_path: Path | None) -> None:
    """Show structural and evidential fragility in a neighborhood around a graph target."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    rows = unwrap_instrument(
        query_gaps(graph_path=graph_path, center=center, hops=hops, limit=limit), what="graph gaps"
    )
    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("graph-gaps", output_format))
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(lookup("graph gaps"), output_path=output_path, command_path="graph gaps", complete_via=complete_via)
    emit_query_rows(
        output_format=output_format,
        title="Graph Gaps",
        columns=[("entity", "Entity"), ("label", "Label"), ("issues", "Issues")],
        rows=rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("uncertainty")
@click.option("--top", type=int, default=10, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_uncertainty(top: int, output_format: str, graph_path: Path, output_path: Path | None) -> None:
    """Show claims and hypotheses ranked by derived uncertainty signals from support/dispute structure."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    rows = unwrap_instrument(query_uncertainty(graph_path=graph_path, top=top), what="graph uncertainty")
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("graph-uncertainty", output_format)
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("graph uncertainty"), output_path=output_path, command_path="graph uncertainty", complete_via=complete_via
    )
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
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("dashboard-summary")
@click.option("--top", type=int, default=25, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_dashboard_summary(top: int, output_format: str, graph_path: Path, output_path: Path | None) -> None:
    """Show claim-centric dashboard summaries for evidence mix, empirical support, and risk."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    rows = unwrap_instrument(query_dashboard_summary(graph_path=graph_path, top=top), what="graph dashboard")
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("graph-dashboard-summary", output_format)
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("graph dashboard-summary"),
        output_path=output_path,
        command_path="graph dashboard-summary",
        complete_via=complete_via,
    )
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
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("neighborhood-summary")
@click.option("--top", type=int, default=25, show_default=True)
@click.option("--hops", type=int, default=1, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_neighborhood_summary(
    top: int, hops: int, output_format: str, graph_path: Path, output_path: Path | None
) -> None:
    """Show claim-centered neighborhood risk summaries for local uncertainty prioritization."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    rows = unwrap_instrument(
        query_neighborhood_summary(graph_path=graph_path, top=top, hops=hops), what="graph neighborhood-summary"
    )
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("graph-neighborhood-summary", output_format)
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("graph neighborhood-summary"),
        output_path=output_path,
        command_path="graph neighborhood-summary",
        complete_via=complete_via,
    )
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
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("question-summary")
@click.option("--top", type=int)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_question_summary(top: int | None, output_format: str, graph_path: Path, output_path: Path | None) -> None:
    """Show question-level rollups derived from claim and neighborhood summaries."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    rows = unwrap_instrument(query_question_summary(graph_path=graph_path, top=top), what="graph question-summary")
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("graph-question-summary", output_format)
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("graph question-summary"),
        output_path=output_path,
        command_path="graph question-summary",
        complete_via=complete_via,
    )
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
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("inquiry-summary")
@click.option("--top", type=int, default=25, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_inquiry_summary(top: int, output_format: str, graph_path: Path, output_path: Path | None) -> None:
    """Show inquiry-level rollups derived from explicit claim backing and claim summaries."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    rows = unwrap_instrument(query_inquiry_summary(graph_path=graph_path, top=top), what="graph inquiry-summary")
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("graph-inquiry-summary", output_format)
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("graph inquiry-summary"),
        output_path=output_path,
        command_path="graph inquiry-summary",
        complete_via=complete_via,
    )
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
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("rehoming-debt")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_rehoming_debt(output_format: str, graph_path: Path, output_path: Path | None) -> None:
    """Open questions still attached to a CLOSED hypothesis (a terminal `status`).

    Closing a hypothesis does not close its questions -- it UNHOUSES them. They are dropped
    from the attention ranking along with their dead hypothesis, so without this surface a
    VISIBLE debt would become an INVISIBLE one. Retirement creates work; this is where that
    work shows up (fb-2026-07-11-005).
    """
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.graph.attention import list_rehoming_debt

    result = list_rehoming_debt(graph_path)
    rows = unwrap_instrument(result, what="graph rehoming-debt")
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("graph-rehoming-debt", output_format)
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("graph rehoming-debt"),
        output_path=output_path,
        command_path="graph rehoming-debt",
        complete_via=complete_via,
    )
    emit_query_rows(
        output_format=output_format,
        title="Re-homing debt (open questions on terminal hypotheses)",
        columns=[
            ("question", "Question"),
            ("terminal_hypothesis", "Terminal Hypothesis"),
            ("question_status", "Status"),
        ],
        rows=rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("attention-sample")
@click.option("--limit", type=int, default=5, show_default=True)
@click.option("--seed", type=int, default=None, help="Seed for reproducible weighted sampling.")
@click.option("--kind", "kinds", multiple=True, help="Restrict candidates to one or more entity kinds.")
@click.option("--epsilon", type=float, default=0.05, show_default=True, help="Positive weight floor.")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--reason-aware",
    is_flag=True,
    help="Use opt-in reason-coded review routing before weighted random sampling.",
)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_attention_sample(
    limit: int,
    seed: int | None,
    kinds: tuple[str, ...],
    epsilon: float,
    output_format: str,
    reason_aware: bool,
    graph_path: Path,
    output_path: Path | None,
) -> None:
    """Sample epistemic entities by graph-derived attention weight."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.graph.attention import query_attention_sample

    if limit < 0:
        raise click.ClickException("--limit must be >= 0")
    try:
        result = query_attention_sample(
            graph_path=graph_path,
            limit=limit,
            seed=seed,
            kinds=set(kinds) if kinds else None,
            epsilon=epsilon,
            reason_aware=reason_aware,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    rows = unwrap_instrument(result, what="graph attention-sample")
    table_rows = rows
    if output_format == "table":
        table_rows = [
            {
                **row,
                "reasons": ", ".join(reason["code"] for reason in row.get("reasons", [])),
                "last_reviewed": row["last_reviewed"] or "never",
            }
            for row in rows
        ]
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("graph-attention-sample", output_format)
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("graph attention-sample"),
        output_path=output_path,
        command_path="graph attention-sample",
        complete_via=complete_via,
    )
    emit_query_rows(
        output_format=output_format,
        title="Graph Attention Sample",
        columns=[
            ("id", "ID"),
            ("freshness_state", "Freshness"),
            ("attention_weight", "Weight"),
            ("incoming_bears_on", "Bears On"),
            ("last_reviewed", "Last reviewed"),
            ("support_count", "Supports"),
            ("dispute_count", "Disputes"),
            ("evidence_source_count", "Evidence Sources"),
            ("reasons", "Reasons"),
            ("label", "Label"),
        ],
        rows=table_rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("attention-rank")
@click.option("--limit", type=int, default=None, help="Cap the number of ranked rows (default: all).")
@click.option("--kind", "kinds", multiple=True, help="Restrict candidates to one or more entity kinds.")
@click.option("--epsilon", type=float, default=0.05, show_default=True, help="Positive weight floor.")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
@click.option(
    "--output", "output_path", type=click.Path(path_type=Path), default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def graph_attention_rank(
    limit: int | None,
    kinds: tuple[str, ...],
    epsilon: float,
    output_format: str,
    graph_path: Path,
    output_path: Path | None,
) -> None:
    """Rank epistemic entities by graph-derived attention weight (deterministic)."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.graph.attention import query_attention_ranked

    if limit is not None and limit < 0:
        raise click.ClickException("--limit must be >= 0")
    try:
        rows = unwrap_instrument(
            query_attention_ranked(
                graph_path=graph_path,
                limit=limit,
                kinds=set(kinds) if kinds else None,
                epsilon=epsilon,
            ),
            what="graph attention-rank",
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    table_rows = rows
    if output_format == "table":
        table_rows = [{**row, "last_reviewed": row["last_reviewed"] or "never"} for row in rows]
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("graph-attention-rank", output_format)
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("graph attention-rank"),
        output_path=output_path,
        command_path="graph attention-rank",
        complete_via=complete_via,
    )
    emit_query_rows(
        output_format=output_format,
        title="Attention ranking",
        columns=[
            ("id", "ID"),
            ("kind", "Kind"),
            ("freshness_state", "Freshness"),
            ("attention_weight", "Weight"),
            ("last_reviewed", "Last reviewed"),
            ("open_question_debt", "Q-Debt"),
        ],
        rows=table_rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@graph_group.command("project-summary")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_project_summary(output_format: str, graph_path: Path) -> None:
    """Show a research-project rollup derived from lower-level reasoning summaries."""

    try:
        rows = unwrap_instrument(query_project_summary(graph_path=graph_path), what="graph project-summary")
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


@graph_group.command("viz")
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


@graph_group.command("export-json")
@click.option("--overlay", "overlays", multiple=True, type=click.Choice(("causal", "evidence")))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_export_json(overlays: tuple[str, ...], graph_path: Path) -> None:
    """Export the graph payload as JSON."""

    payload = export_graph_payload(graph_path, overlays=list(overlays) if overlays else None)
    emit(output_format="json", payload=payload.model_dump(mode="json"), render_text=lambda: None, sort_keys=True)


@graph_group.command("scan-prose")
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


@graph_group.command("belief-basis")
@click.option(
    "--graph-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_GRAPH_PATH,
    show_default=True,
    help="Materialized graph to read.",
)
@click.option(
    "--out", "out_path", type=click.Path(path_type=Path), default=None,
    help="Write a sealed capture to this path.",
)
@click.option(
    "--compare", "compare_path", type=click.Path(path_type=Path), default=None,
    help="Compare the current basis against a previous capture.",
)
def belief_basis_command(graph_path: Path, out_path: Path | None, compare_path: Path | None) -> None:
    """Capture or compare the per-entity belief basis.

    Exactly one of --out / --compare. Exit codes: 0 clean, 1 a pre-existing
    entity's basis moved, 2 unwired (not computable — explicitly NOT clean).
    """
    import json
    import sys
    from typing import NoReturn

    from science_tool.graph.belief_basis import (
        build_snapshot,
        capture_basis,
        compare_bases,
        load_snapshot,
    )
    from science_tool.graph.store.identity import graph_uri
    from science_tool.graph.trig import load_trig_dataset_preserving_literals

    def _unwired(message: str) -> NoReturn:
        """Exit 2. Typed NoReturn so the checker knows nothing after a call is reachable."""
        click.echo(f"unwired: {message}")
        sys.exit(2)

    # A caller passing the same path for both would overwrite the baseline with the
    # current capture and then compare it against itself — always clean.
    if (out_path is None) == (compare_path is None):
        _unwired("--out and --compare are mutually exclusive; pass exactly one")

    try:
        dataset = load_trig_dataset_preserving_literals(graph_path)
        result = capture_basis(
            dataset.graph(graph_uri("graph/knowledge")),
            dataset.graph(graph_uri("graph/provenance")),
        )
    except Exception as exc:
        # Two distinct uncomputable cases share this handler: an unreadable or
        # malformed graph, and a basis that cannot be serialized (a future
        # EvidenceUnit field with a non-JSON-native type raises TypeError in
        # unit_key by design). Neither is a belief movement.
        _unwired(f"could not compute basis from {graph_path}: {exc}")

    if result.status == "unwired":
        _unwired(f"({result.code}) {result.reason}")

    if out_path is not None:
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Explicit utf-8 both here and on the compare read: the snapshot is a durable
            # artifact handed between processes and machines, and model_dump_json emits
            # utf-8. Defaulting to the ambient locale would raise under C/POSIX or decode
            # a utf-8 baseline into mojibake that fails the digest check.
            out_path.write_text(build_snapshot(result.rows).model_dump_json(indent=2), encoding="utf-8")
        except Exception as exc:  # unwritable output is uncomputable, not clean
            _unwired(f"could not write capture to {out_path}: {exc}")
        click.echo(f"captured {len(result.rows)} entities -> {out_path}")
        sys.exit(0)

    assert compare_path is not None  # exactly-one check above
    try:
        previous = load_snapshot(json.loads(compare_path.read_text(encoding="utf-8")))
    except Exception as exc:
        # OSError, JSONDecodeError, ValidationError, SnapshotIntegrityError — a
        # baseline we cannot read or cannot trust is unwired, never clean.
        _unwired(f"could not trust baseline {compare_path}: {exc}")

    deltas = compare_bases(previous.rows, result.rows)
    if not deltas:
        click.echo("clean: no pre-existing entity's belief basis moved")
        sys.exit(0)
    for delta in deltas:
        click.echo(f"MOVED {delta.entity_id}: {','.join(delta.changed)} — {delta.detail}")
    sys.exit(1)

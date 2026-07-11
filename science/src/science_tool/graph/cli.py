"""`science graph` command group — knowledge-graph build, query, and inspection."""

from __future__ import annotations

from datetime import date, datetime
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
from science_tool.output import OUTPUT_FORMATS, emit, emit_query_rows
from science_tool.prose import scan_prose


def _retired_writer(command: str, forward_path: str) -> click.ClickException:
    return click.ClickException(f"{command} is retired. {forward_path}, then run `science graph build`.")


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
def graph_build(project_root: Path, local_only: bool) -> None:
    """Materialize graph.trig and, unless skipped, composite.trig from structured project sources."""
    from science_tool.graph.composite import assemble_composite_graph
    from science_tool.peers import PeerNotFound, PeerUnresolved

    _project_root = Path.cwd() if str(project_root) == "." else project_root
    try:
        result = build_project_graph(_project_root)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    _cfg = result.config
    click.echo(f"Materialized local graph at {result.local_path}")

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


@graph_group.command("migrate-addresses")
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
    raise _retired_writer("graph migrate-addresses", "Address direction is canonical at build")


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

    rows, has_failures = validate_graph(graph_path)
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
def graph_diff(mode: str, output_format: str, graph_path: Path) -> None:
    """Show files that are stale relative to graph revision metadata."""

    rows = diff_graph_inputs(graph_path=graph_path, mode=mode)
    emit_query_rows(
        output_format=output_format,
        title="Graph Diff",
        columns=[("path", "Path"), ("status", "Status"), ("reason", "Reason")],
        rows=rows,
    )


@graph_group.command("stamp-revision")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_stamp_revision(graph_path: Path) -> None:
    """Update graph revision metadata to reflect current project state."""

    raise _retired_writer("graph stamp-revision", "The compiler stamps revisions")


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


@graph_group.command("claims")
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


@graph_group.command("evidence")
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

    rows = query_coverage(graph_path=graph_path, limit=limit)
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
def graph_gaps(center: str, hops: int, limit: int, output_format: str, graph_path: Path) -> None:
    """Show structural and evidential fragility in a neighborhood around a graph target."""

    rows = query_gaps(graph_path=graph_path, center=center, hops=hops, limit=limit)
    emit_query_rows(
        output_format=output_format,
        title="Graph Gaps",
        columns=[("entity", "Entity"), ("label", "Label"), ("issues", "Issues")],
        rows=rows,
    )


@graph_group.command("uncertainty")
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


@graph_group.command("dashboard-summary")
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


@graph_group.command("neighborhood-summary")
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


@graph_group.command("question-summary")
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


@graph_group.command("inquiry-summary")
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


@graph_group.command("attention-sample")
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


@graph_group.command("attention-rank")
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


@graph_group.command("project-summary")
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


@graph_group.command("import")
@click.argument("snapshot_path", required=False, type=click.Path(path_type=Path))
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_import(snapshot_path: Path | None, graph_path: Path) -> None:
    """Import a Turtle snapshot into the knowledge graph."""

    raise _retired_writer("graph import", "Raw-triple import is retired; author the source records")


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

@graph_group.group("add")
def graph_add() -> None:
    """Add graph entities and edges."""


@graph_add.command("concept")
@click.argument("label", required=False)
@click.option("--type", "concept_type", default=None)
@click.option("--ontology-id", default=None)
@click.option("--note", default=None, help="skos:note annotation")
@click.option("--definition", default=None, help="skos:definition annotation")
@click.option("--property", "properties", type=(str, str), multiple=True, help="KEY VALUE property pair (repeatable)")
@click.option("--status", default=None, help="Project status")
@click.option("--source", default=None, help="Provenance source reference (paper:doi_... or file path)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_concept(
    label: str | None,
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

    raise _retired_writer(
        "graph add concept",
        "Run `science entity create concept <title>` (or edit entities/concepts/<slug>.md)",
    )


@graph_add.command("article")
@click.argument("doi")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_article_cmd(doi: str, graph_path: Path) -> None:
    """Add an external literature reference by DOI."""
    raise _retired_writer(
        "graph add article",
        "Run `science entity create paper <title> --id <citekey>` "
        "(or edit entities/papers/<citekey>.md with a doi: field)",
    )


@graph_add.command("proposition")
@click.argument("text", required=False)
@click.option("--source", help="Provenance reference")
@click.option("--confidence", type=float, default=None)
@click.option("--evidence-type", default=None)
@click.option("--id", "proposition_id", default=None, help="Custom proposition ID slug")
@click.option("--subject", default=None, help="Structured S-P-O: subject entity")
@click.option("--predicate", default=None, help="Structured S-P-O: predicate")
@click.option("--object", "obj", default=None, help="Structured S-P-O: object entity")
@click.option("--compositional-status", default=None)
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
@click.option("--statistical-support", default=None)
@click.option("--mechanistic-support", default=None)
@click.option("--replication-scope", default=None)
@click.option("--claim-status", default=None)
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
    default="core",
    show_default=True,
    help="Membership role for --bridge-between frames",
)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_proposition_cmd(
    text: str | None,
    source: str | None,
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
    raise _retired_writer("graph add proposition", "Run `science propositions create <title>`")


@graph_add.command("observation")
@click.argument("description", required=False)
@click.option("--data-source", help="Reference to data-package or dataset")
@click.option("--metric", default=None)
@click.option("--value", default=None)
@click.option("--uncertainty", default=None)
@click.option("--conditions", default=None)
@click.option("--id", "observation_id", default=None)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_observation_cmd(
    description: str | None,
    data_source: str | None,
    metric: str | None,
    value: str | None,
    uncertainty: str | None,
    conditions: str | None,
    observation_id: str | None,
    graph_path: Path,
) -> None:
    """Add an observation — a concrete empirical fact anchored to data."""
    raise _retired_writer("graph add observation", "Run `science entity create observation <title>`")


@graph_add.command("evidence")
@click.argument("source_entity", required=False)
@click.argument("target_entity", required=False)
@click.option("--stance")
@click.option("--strength", default=None)
@click.option("--caveats", default=None)
@click.option("--method", "evidence_method", default=None)
@click.option(
    "--independence",
    default=None,
    help="Independence of evidence source from validation target",
)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_evidence_cmd(
    source_entity: str | None,
    target_entity: str | None,
    stance: str | None,
    strength: str | None,
    caveats: str | None,
    evidence_method: str | None,
    independence: str | None,
    graph_path: Path,
) -> None:
    """Add an evidence edge (supports/disputes) between entities."""
    raise _retired_writer(
        "graph add evidence",
        "Run `science evidence-lines create --target <ref> --stance <supports|disputes>`",
    )


@graph_add.command("hypothesis")
@click.argument("hypothesis_id", required=False)
@click.option("--text")
@click.option("--source")
@click.option("--status", default=None, help="Project status")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_hypothesis(
    hypothesis_id: str | None, text: str | None, source: str | None, status: str | None, graph_path: Path
) -> None:
    """Add a hypothesis with provenance."""

    raise _retired_writer("graph add hypothesis", "Run `science hypotheses create <title>`")


@graph_add.command("question")
@click.argument("question_id", required=False)
@click.option("--text")
@click.option("--source")
@click.option("--maturity", default="open", show_default=True)
@click.option("--status", default=None, help="Project status")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_question(
    question_id: str | None,
    text: str | None,
    source: str | None,
    maturity: str,
    status: str | None,
    related_refs: tuple[str, ...],
    graph_path: Path,
) -> None:
    """Add an open question with provenance."""

    raise _retired_writer("graph add question", "Run `science questions create <title>`")


@graph_add.command("edge")
@click.argument("subject", required=False)
@click.argument("predicate", required=False)
@click.argument("object", required=False)
@click.option("--graph", "graph_layer", default="graph/knowledge", show_default=True)
@click.option("--claim", "claim_refs", multiple=True, help="Supporting proposition reference (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_edge(
    subject: str | None,
    predicate: str | None,
    object: str | None,
    graph_layer: str,
    claim_refs: tuple[str, ...],
    graph_path: Path,
) -> None:
    """Add an arbitrary edge to a selected named graph layer."""

    raise _retired_writer(
        "graph add edge",
        (
            "Author the relation in `relations.yaml` (or `relations:` frontmatter) with the target graph_layer; "
            "claim-cited edges use inquiry flow_edges"
        ),
    )


@graph_add.command("finding")
@click.argument("summary", required=False)
@click.option("--confidence")
@click.option("--proposition", "propositions", multiple=True, help="Proposition ref(s)")
@click.option("--observation", "observations", multiple=True, help="Observation ref(s)")
@click.option("--source", help="data-package or workflow-run that produced the observations")
@click.option("--id", "finding_id", default=None, help="Custom finding ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_finding_cmd(
    summary: str | None,
    confidence: str | None,
    propositions: tuple[str, ...],
    observations: tuple[str, ...],
    source: str,
    finding_id: str | None,
    graph_path: Path,
) -> None:
    """Add a finding — propositions grounded by observations."""
    raise _retired_writer("graph add finding", "Run `science entity create finding <title>`")


@graph_add.command("interpretation")
@click.argument("summary", required=False)
@click.option("--finding", "findings", multiple=True, help="Finding ref(s)")
@click.option("--context", "interp_context", default=None, help="What prompted this analysis")
@click.option("--prior", default=None, help="Previous interpretation ref (provenance chain)")
@click.option("--id", "interpretation_id", default=None, help="Custom interpretation ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_interpretation_cmd(
    summary: str | None,
    findings: tuple[str, ...],
    interp_context: str | None,
    prior: str | None,
    interpretation_id: str | None,
    graph_path: Path,
) -> None:
    """Add an interpretation — one analysis session's narrative and findings."""
    raise _retired_writer("graph add interpretation", "Run `science interpretations create <title>`")


@graph_add.command("discussion")
@click.argument("summary", required=False)
@click.option("--proposition", "propositions", multiple=True, help="Proposition ref(s)")
@click.option("--context", "disc_context", default=None, help="What prompted this discussion")
@click.option("--prior", default=None, help="Previous discussion ref (provenance chain)")
@click.option("--id", "discussion_id", default=None, help="Custom discussion ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_discussion_cmd(
    summary: str | None,
    propositions: tuple[str, ...],
    disc_context: str | None,
    prior: str | None,
    discussion_id: str | None,
    graph_path: Path,
) -> None:
    """Add a discussion — theoretical reasoning producing propositions."""
    raise _retired_writer("graph add discussion", "Run `science discussions create <title>`")


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
    raise _retired_writer(
        "graph add falsification",
        "Run `science entity create falsification <title>` (set falsifies: to the proposition ref)",
    )


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
    raise _retired_writer(
        "graph add story",
        "Run `science entity create story <title>` (author synthesizes/organizedBy edges in relations.yaml)",
    )


@graph_add.command("mechanism")
@click.argument("title", required=False)
@click.option("--summary", help="Brief explanatory summary")
@click.option("--participant", "participants", multiple=True, help="Participant ref(s)")
@click.option("--proposition", "propositions", multiple=True, help="Mechanism proposition ref(s)")
@click.option("--status", default="draft", help="Mechanism status")
@click.option("--id", "mechanism_id", default=None, help="Custom mechanism ID slug")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def add_mechanism_cmd(
    title: str | None,
    summary: str | None,
    participants: tuple[str, ...],
    propositions: tuple[str, ...],
    status: str,
    mechanism_id: str | None,
    graph_path: Path,
) -> None:
    """Add a mechanism over existing typed entities and proposition refs."""
    raise _retired_writer("graph add mechanism", "Run `science entity create mechanism <title>`")



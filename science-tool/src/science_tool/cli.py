from __future__ import annotations

from pathlib import Path

import click

from science_tool.causal.export_chirho import export_chirho_script
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.distill.openalex import distill_openalex
from science_tool.distill.pykeen_source import distill_pykeen
from science_tool.doi import lookup_doi_metadata
from science_tool.graph.store import (
    GRAPH_LAYERS,
    DEFAULT_GRAPH_PATH,
    add_claim,
    add_concept,
    add_edge,
    add_hypothesis,
    add_assumption,
    add_inquiry,
    add_inquiry_edge,
    add_inquiry_node,
    add_transformation,
    add_paper,
    add_question,
    build_graph_dot,
    diff_graph_inputs,
    get_inquiry,
    import_snapshot,
    init_graph_file,
    list_inquiries,
    set_boundary_role,
    set_treatment_outcome,
    shorten_uri,
    stamp_revision,
    query_claims,
    query_coverage,
    query_evidence,
    query_gaps,
    query_neighborhood,
    query_predicates,
    query_uncertainty,
    read_graph_stats,
    validate_graph,
    validate_inquiry,
)
from science_tool.output import OUTPUT_FORMATS, emit_query_rows
from science_tool.prose import scan_prose


@click.group()
def main() -> None:
    """Science CLI tools."""


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
        click.echo(f"  Run: uv run --with marimo marimo edit {viz_path}")


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
@click.argument("hypothesis_id")
@click.option("--limit", type=int, default=200, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_evidence(hypothesis_id: str, limit: int, output_format: str, graph_path: Path) -> None:
    """Return evidence for/against a hypothesis, grouped by supports/refutes."""

    rows = query_evidence(graph_path=graph_path, hypothesis_id=hypothesis_id, limit=limit)
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
    """Show low-coverage areas in a neighborhood (missing provenance, low confidence, low connectivity)."""

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
    """Show highest-uncertainty claims/entities ranked by epistemic status and confidence."""

    rows = query_uncertainty(graph_path=graph_path, top=top)
    emit_query_rows(
        output_format=output_format,
        title="Graph Uncertainty",
        columns=[("entity", "Entity"), ("text", "Text"), ("status", "Status"), ("confidence", "Confidence")],
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


@graph_add.command("paper")
@click.option("--doi", required=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_paper(doi: str, graph_path: Path) -> None:
    """Add a paper node to the knowledge graph."""

    paper_uri = add_paper(graph_path=graph_path, doi=doi)
    click.echo(f"Added paper: {paper_uri}")


@graph_add.command("claim")
@click.argument("text")
@click.option("--source", required=True)
@click.option("--confidence", type=float, default=None)
@click.option("--id", "claim_id", default=None)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_claim(
    text: str,
    source: str,
    confidence: float | None,
    claim_id: str | None,
    graph_path: Path,
) -> None:
    """Add a claim with provenance."""

    claim_uri = add_claim(
        graph_path=graph_path,
        text=text,
        source=source,
        confidence=confidence,
        claim_id=claim_id,
    )
    click.echo(f"Added claim: {claim_uri}")


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
@click.option("--related-hypothesis", "related_hypotheses", multiple=True, help="Hypothesis reference (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_question(
    question_id: str,
    text: str,
    source: str,
    maturity: str,
    status: str | None,
    related_hypotheses: tuple[str, ...],
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
        related_hypotheses=list(related_hypotheses) if related_hypotheses else None,
    )
    click.echo(f"Added question: {question_uri}")


@graph_add.command("edge")
@click.argument("subject")
@click.argument("predicate")
@click.argument("object")
@click.option("--graph", "graph_layer", type=click.Choice(GRAPH_LAYERS), default="graph/knowledge", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_edge(subject: str, predicate: str, object: str, graph_layer: str, graph_path: Path) -> None:
    """Add an arbitrary edge to a selected named graph layer."""

    s_uri, p_uri, o_uri = add_edge(
        graph_path=graph_path, subject=subject, predicate=predicate, obj=object, graph_layer=graph_layer
    )
    click.echo(
        f"Added edge in {graph_layer}: {shorten_uri(str(s_uri))} {shorten_uri(str(p_uri))} {shorten_uri(str(o_uri))}"
    )


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
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_edge(slug: str, subject: str, predicate: str, object: str, graph_path: Path) -> None:
    """Add an edge within an inquiry subgraph."""
    try:
        s, p, o = add_inquiry_edge(graph_path, slug, subject, predicate, object)
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
            click.echo(
                f"    {shorten_uri(edge['subject'])} --[{shorten_uri(edge['predicate'])}]--> {shorten_uri(edge['object'])}"
            )


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


if __name__ == "__main__":
    main()

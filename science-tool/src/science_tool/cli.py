from __future__ import annotations

from pathlib import Path

import click

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
    add_paper,
    build_graph_dot,
    diff_graph_inputs,
    import_snapshot,
    init_graph_file,
    stamp_revision,
    query_claims,
    query_coverage,
    query_evidence,
    query_gaps,
    query_neighborhood,
    query_uncertainty,
    read_graph_stats,
    validate_graph,
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
                "inline_annotations": "; ".join(
                    f"{a['term']} [{a['curie']}]" for a in entry["inline_annotations"]
                ),
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


@graph.group("add")
def graph_add() -> None:
    """Add graph entities and edges."""


@graph_add.command("concept")
@click.argument("label")
@click.option("--type", "concept_type", default=None)
@click.option("--ontology-id", default=None)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_concept(label: str, concept_type: str | None, ontology_id: str | None, graph_path: Path) -> None:
    """Add a concept node to the knowledge graph."""

    concept_uri = add_concept(graph_path=graph_path, label=label, concept_type=concept_type, ontology_id=ontology_id)
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
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_hypothesis(hypothesis_id: str, text: str, source: str, graph_path: Path) -> None:
    """Add a hypothesis with provenance."""

    hypothesis_uri = add_hypothesis(graph_path=graph_path, hypothesis_id=hypothesis_id, text=text, source=source)
    click.echo(f"Added hypothesis: {hypothesis_uri}")


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

    add_edge(graph_path=graph_path, subject=subject, predicate=predicate, obj=object, graph_layer=graph_layer)
    click.echo(f"Added edge in {graph_layer}: {subject} {predicate} {object}")


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

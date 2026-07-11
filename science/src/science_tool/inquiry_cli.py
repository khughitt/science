"""`science inquiry` command group — inquiry subgraph commands."""
from __future__ import annotations

from pathlib import Path

import click

from science_tool.causal.export_chirho import export_chirho_script
from science_tool.causal.export_pgmpy import export_pgmpy_script
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    get_inquiry,
    list_inquiries,
    shorten_uri,
    validate_inquiry,
)
from science_tool.output import OUTPUT_FORMATS, emit, emit_query_rows, unwrap_instrument


@click.group("inquiry")
def inquiry_group() -> None:
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


@inquiry_group.command("init")
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


@inquiry_group.command("import")
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


@inquiry_group.command("add-node")
@click.argument("slug")
@click.argument("entity")
@click.option("--role", required=False, type=click.Choice(["BoundaryIn", "BoundaryOut"]), default=None)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_node(slug: str, entity: str, role: str | None, graph_path: Path) -> None:
    """Add a node to an inquiry, optionally with a boundary role."""
    raise _retired_mutator(slug)


@inquiry_group.command("add-edge")
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


@inquiry_group.command("add-assumption")
@click.argument("slug")
@click.argument("label")
@click.option("--source", required=True, help="Evidence source (e.g. paper:doi_...)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_assumption(slug: str, label: str, source: str, graph_path: Path) -> None:
    """Add an assumption to an inquiry with provenance."""
    raise _retired_mutator(slug)


@inquiry_group.command("add-transformation")
@click.argument("slug")
@click.argument("label")
@click.option("--tool", default="", help="Tool or library name")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_add_transformation(slug: str, label: str, tool: str, graph_path: Path) -> None:
    """Add a transformation step to an inquiry."""
    raise _retired_mutator(slug)


@inquiry_group.command("set-estimand")
@click.argument("slug")
@click.option("--treatment", required=True, help="Treatment variable (e.g. concept/drug)")
@click.option("--outcome", required=True, help="Outcome variable (e.g. concept/recovery)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_set_estimand(slug: str, treatment: str, outcome: str, graph_path: Path) -> None:
    """Set treatment and outcome variables for a causal inquiry."""
    raise _retired_mutator(slug)


@inquiry_group.command("list")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_list(output_format: str, graph_path: Path) -> None:
    """List all inquiries."""
    rows = unwrap_instrument(list_inquiries(graph_path), what="inquiry list")
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


@inquiry_group.command("show")
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

    def _render() -> None:
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

    emit(output_format=output_format, payload=info, render_text=_render, default=str)


@inquiry_group.command("validate")
@click.argument("slug")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def inquiry_validate(slug: str, output_format: str, graph_path: Path) -> None:
    """Validate an inquiry subgraph."""
    results = unwrap_instrument(validate_inquiry(graph_path, slug), what="inquiry validate")

    def _render() -> None:
        for r in results:
            icon = "PASS" if r["status"] == "pass" else "FAIL" if r["status"] == "fail" else "WARN"
            click.echo(f"  [{icon}] {r['check']}: {r['message']}")

    emit(output_format=output_format, payload=results, render_text=_render)

    if any(r["status"] == "fail" for r in results):
        raise click.exceptions.Exit(1)


@inquiry_group.command("export-pgmpy")
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


@inquiry_group.command("export-chirho")
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

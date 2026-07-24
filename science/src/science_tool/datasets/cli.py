"""`science dataset` command group — dataset entity lifecycle commands."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import click

from science_tool.datasets_identity import identity_group as dataset_identity_group
from science_tool.output import emit, unwrap_instrument


def _project_root_from_env() -> Path:
    """Return project root from SCIENCE_PROJECT_ROOT env var or cwd."""
    import os

    env = os.environ.get("SCIENCE_PROJECT_ROOT")
    return Path(env).resolve() if env else Path.cwd()


@click.group("dataset")
def dataset_group() -> None:
    """Dataset entity lifecycle commands (list, register-run, reconcile)."""


dataset_group.add_command(dataset_identity_group)


@dataset_group.command("list")
@click.option("--origin", default=None, type=click.Choice(["external", "derived"]))
@click.option("--status", default=None, help="Filter by status (e.g. candidate, active)")
@click.option("--candidate", is_flag=True, help="Shorthand for --status candidate")
@click.option("--tier", default=None, type=click.Choice(["use-now", "evaluate-next", "track"]))
@click.option("--unverified", is_flag=True, help="Only external entities with access.verified false")
@click.option(
    "--level",
    default=None,
    type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]),
)
@click.option(
    "--include-gated",
    is_flag=True,
    help="Include gated datasets (registration/controlled/commercial); excluded by default",
)
@click.option("--commons", "include_commons", is_flag=True, help="Also list commons dataset entities")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_list(
    origin: str | None,
    status: str | None,
    candidate: bool,
    tier: str | None,
    unverified: bool,
    level: str | None,
    include_gated: bool,
    include_commons: bool,
    project_root: Path | None,
) -> None:
    """List dataset entities as a table, with filters."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.datasets_catalog import list_datasets

    root = project_root.resolve() if project_root else _project_root_from_env()
    if candidate:
        status = "candidate"

    rows = unwrap_instrument(
        list_datasets(
            root,
            origin=origin,
            status=status,
            tier=tier,
            unverified=unverified,
            level=level,
            include_gated=include_gated,
            include_commons=include_commons,
        ),
        what="dataset list",
    )

    if not rows:
        click.echo("No matching dataset entities.")
        return

    table = Table(show_header=True, header_style="bold")
    for col in ("id", "title", "status", "tier", "origin", "level", "verified", "scope"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for r in rows:
        table.add_row(
            r["id"],
            r["title"],
            r["status"],
            r["tier"],
            r["origin"],
            r["level"],
            "yes" if r["verified"] else "no",
            r["scope"],
        )
    Console(width=200).print(table)


@dataset_group.command("prioritize")
@click.option("--origin", default=None, type=click.Choice(["external", "derived"]))
@click.option("--status", default=None)
@click.option("--tier", default=None, type=click.Choice(["use-now", "evaluate-next", "track"]))
@click.option(
    "--level", default=None, type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"])
)
@click.option(
    "--include-gated",
    is_flag=True,
    help="Include gated datasets (registration/controlled/commercial); excluded by default",
)
@click.option("--include-reference", is_flag=True, help="Include reference-class datasets in the ranking")
@click.option("--include-pointer", is_flag=True, help="Include pointer-class records in the ranking")
@click.option(
    "--runtime-state",
    default=None,
    type=click.Choice(["runnable", "unstaged-deposit", "blocked-access", "reference-only", "pointer-only"]),
    help="Filter by derived runtime state",
)
@click.option("--coverage", is_flag=True, help="Invert reach into per-question/hypothesis coverage rows")
@click.option("--format", "output_format", default="table", type=click.Choice(["table", "json"]))
@click.option("--explain", is_flag=True, help="Show the per-row scoring reason")
@click.option("--project-root", default=None, type=click.Path(path_type=Path, file_okay=False, dir_okay=True))
def dataset_prioritize(
    origin: str | None,
    status: str | None,
    tier: str | None,
    level: str | None,
    include_gated: bool,
    include_reference: bool,
    include_pointer: bool,
    runtime_state: str | None,
    coverage: bool,
    output_format: str,
    explain: bool,
    project_root: Path | None,
) -> None:
    """Rank dataset entities by accessibility-weighted, graph-aware usefulness."""
    from science_tool.dataset_prioritize import excluded_summary, prioritize, target_coverage
    from science_tool.datasets.semantics import RuntimeState
    from science_tool.entities import graph_is_stale
    from science_tool.graph.store import DEFAULT_GRAPH_PATH
    from science_tool.graph.store.dataset import load_dataset
    from science_tool.graph.store.identity import graph_uri

    root = project_root.resolve() if project_root else _project_root_from_env()
    runtime_state_filter = cast(RuntimeState | None, runtime_state)
    graph_path = root / DEFAULT_GRAPH_PATH
    knowledge = provenance = None
    if graph_path.exists():
        if graph_is_stale(root, graph_path):
            click.echo(
                "warning: graph may be stale; reach/leverage from last build — run `science graph build`",
                err=True,
            )
        ds = load_dataset(graph_path)
        knowledge = ds.graph(graph_uri("graph/knowledge"))
        provenance = ds.graph(graph_uri("graph/provenance"))
    else:
        click.echo("warning: no materialized graph; reach from frontmatter only", err=True)

    rows = prioritize(
        root,
        knowledge=knowledge,
        provenance=provenance,
        origin=origin,
        status=status,
        tier=tier,
        level=level,
        include_gated=include_gated or coverage,
        include_reference=include_reference or coverage,
        include_pointer=include_pointer or coverage,
        runtime_state=runtime_state_filter,
    )
    summary = excluded_summary(
        root,
        origin=origin,
        status=status,
        tier=tier,
        level=level,
        include_gated=include_gated,
        include_reference=include_reference,
        include_pointer=include_pointer,
        runtime_state=runtime_state_filter,
    )

    if coverage:
        coverage_rows = target_coverage(rows, root)

        def _render_coverage() -> None:
            if not coverage_rows:
                click.echo("No question or hypothesis entities found.")
                return
            from rich.console import Console
            from rich.table import Table

            table = Table(show_header=True, header_style="bold")
            for c in ["target", "coverage", "gap-reason", "datasets"]:
                table.add_column(c, overflow="fold", no_wrap=False)
            for r in coverage_rows:
                table.add_row(
                    str(r["target"]),
                    str(r["coverage_state"]),
                    str(r["gap_reason"]),
                    ", ".join(r["datasets"]) if r["datasets"] else "-",
                )
            Console(width=200).print(table)

        emit(
            output_format=output_format,
            payload={"rows": coverage_rows, "excluded_summary": summary},
            render_text=_render_coverage,
        )
        return

    def _render_rows() -> None:
        if not rows:
            click.echo("No matching dataset entities.")
            return

        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        cols = ["rank", "id", "score", "readiness", "runtime", "reach", "gap-flags"]
        if explain:
            cols.append("reason")
        for c in cols:
            table.add_column(c, overflow="fold", no_wrap=False)
        for i, r in enumerate(rows, 1):
            cells = [
                str(i),
                r["id"],
                f"{r['score']:g}",
                r["readiness"],
                r["runtime_state"],
                str(r["reach"]),
                ", ".join(r["gap_flags"]) or "-",
            ]
            if explain:
                cells.append(r["top_reason"])
            table.add_row(*cells)
        Console(width=200).print(table)
        if any(summary.values()):
            click.echo(
                "Excluded by default: "
                f"{summary['gated']} gated deposits, {summary['reference']} reference datasets, "
                f"{summary['pointer']} pointer records. Use --include-gated, --include-reference, "
                "or --include-pointer to inspect them."
            )

    emit(output_format=output_format, payload={"rows": rows, "excluded_summary": summary}, render_text=_render_rows)


@dataset_group.command("capability-pairs")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Enumerate a project's entities under entities/",
)
@click.option(
    "--commons-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Enumerate commons dataset records (datasets/<slug>/entity.md)",
)
@click.option(
    "--file",
    "file_path",
    default=None,
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    help="Enumerate a single entity file",
)
def dataset_capability_pairs(project_root: Path | None, commons_root: Path | None, file_path: Path | None) -> None:
    """List distinct observed capability shapes (provided/required) across a corpus.

    Read-only. Seeds the value-to-term crosswalk. Exactly one of --project-root,
    --commons-root, or --file is required.
    """
    from dataclasses import asdict

    from science_model.frontmatter import split_frontmatter

    from science_tool.datasets.capability_pairs import enumerate_pairs

    inputs = [project_root, commons_root, file_path]
    if sum(1 for i in inputs if i is not None) != 1:
        raise click.ClickException("exactly one of --project-root, --commons-root, or --file is required")

    records: list[dict] = []
    if project_root is not None:
        from science_tool.dataset_prioritize import _iter_entity_frontmatter

        records = [fm for _, fm in _iter_entity_frontmatter(project_root.resolve())]
    elif commons_root is not None:
        for entity_path in sorted(commons_root.resolve().glob("datasets/*/entity.md")):
            fm, _ = split_frontmatter(entity_path.read_text(encoding="utf-8"))
            if fm:
                records.append(fm)
    else:
        assert file_path is not None
        fm, _ = split_frontmatter(file_path.resolve().read_text(encoding="utf-8"))
        if fm:
            records.append(fm)

    shapes = enumerate_pairs(records)
    emit(output_format="json", payload=[asdict(s) for s in shapes], render_text=lambda: None)


@dataset_group.command("add")
@click.argument("slug")
@click.option("--title", required=True, help="Human-readable dataset title")
@click.option("--origin", type=click.Choice(["external", "derived"]), default="external")
@click.option("dataset_class", "--class", type=click.Choice(["deposit", "reference", "pointer"]), default="deposit")
@click.option("--tier", type=click.Choice(["use-now", "evaluate-next", "track"]), default="track")
@click.option(
    "--level",
    type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]),
    default="controlled",
)
@click.option("--source-url", default="", help="Landing page / accession URL")
@click.option("--ontology-term", "ontology_terms", multiple=True)
@click.option("--related", "related", multiple=True, help="Related entity ref (repeatable)")
@click.option(
    "--schema-profile",
    default=None,
    help="Composed entity schema profile. Defaults to the base dataset profile.",
)
@click.option("--taxon", type=int, default=None, help="NCBI taxonomy id for identity-bearing dataset profiles.")
@click.option("--assembly", default=None, help="Assembly label/digest, or UNKNOWN when intentionally unresolved.")
@click.option("--gene-namespace", default=None, help="Gene identifier namespace to declare.")
@click.option("--protein-namespace", default=None, help="Protein identifier namespace to declare.")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_add(
    slug: str,
    title: str,
    origin: str,
    dataset_class: str,
    tier: str,
    level: str,
    source_url: str,
    ontology_terms: tuple[str, ...],
    related: tuple[str, ...],
    schema_profile: str | None,
    taxon: int | None,
    assembly: str | None,
    gene_namespace: str | None,
    protein_namespace: str | None,
    project_root: Path | None,
) -> None:
    """Author a candidate external dataset entity under entities/datasets/."""
    from science_tool.datasets_catalog import add_dataset
    from science_tool.entities import EntityCommandError
    from science_tool.identity_authoring import (
        IdentityAuthoringError,
        build_identity_context,
    )

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        identity_context = build_identity_context(
            taxon=taxon,
            assembly=assembly,
            gene_namespace=gene_namespace,
            protein_namespace=protein_namespace,
        )
        entity_id, dest, warnings = add_dataset(
            root,
            slug,
            title=title,
            origin=origin,
            dataset_class=dataset_class,
            tier=tier,
            level=level,
            source_url=source_url,
            ontology_terms=ontology_terms,
            related=related,
            schema_profile=schema_profile,
            identity_context=identity_context,
        )
    except (EntityCommandError, IdentityAuthoringError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    for w in warnings:
        click.echo(f"warning: {w}", err=True)
    click.echo(f"created {entity_id} -> {dest.relative_to(root)}")


@dataset_group.command("verify-access")
@click.argument("ref")
@click.option("--level", type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]))
@click.option(
    "--method",
    type=click.Choice(["retrieved", "credential-confirmed", "landing-confirmed", "metadata-confirmed"]),
)
@click.option("--license", "license_", default=None, help="SPDX id or sentinel (unknown|proprietary|custom)")
@click.option("dataset_class", "--class", type=click.Choice(["deposit", "reference", "pointer"]), default=None)
@click.option("--by", "verified_by", default="agent (verify-access)")
@click.option("--source-url", "source_url", default=None)
@click.option("--tier", type=click.Choice(["use-now", "evaluate-next", "track"]), default=None)
@click.option("--note", default="", help="Free-text evidence for the verification log line")
@click.option(
    "--exception",
    type=click.Choice(["scope-reduced", "expanded-to-acquire", "substituted"]),
    default=None,
    help="Record a Branch-B access exception instead of flipping verified",
)
@click.option("--rationale", default="")
@click.option("--superseded-by", "superseded_by", default=None)
@click.option("--followup-task", "followup_task", default=None)
@click.option(
    "--on-request-only",
    "on_request_only",
    is_flag=True,
    default=False,
    help="Record availability=on-request-only (analysis-ineligible: 'available on author "
    "request' has no followable access procedure). Mutually exclusive with --method/--exception.",
)
@click.option(
    "--show-preexisting",
    "show_preexisting",
    is_flag=True,
    default=False,
    help="List pre-existing project audit failures individually instead of summarizing them",
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_verify_access(
    ref: str,
    level: str | None,
    method: str | None,
    license_: str | None,
    dataset_class: str | None,
    verified_by: str,
    source_url: str | None,
    tier: str | None,
    note: str,
    exception: str | None,
    rationale: str,
    superseded_by: str | None,
    followup_task: str | None,
    on_request_only: bool,
    show_preexisting: bool,
    project_root: Path | None,
) -> None:
    """Verify (or exception-gate) a dataset's accessibility.

    Sets the coupled origin/license/access fields together in one atomic edit and
    records a verification-log line (also backfills legacy entities).
    """
    from science_tool.datasets_catalog import verify_access
    from science_tool.entities import EntityCommandError

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        entity_id, dest, state, weight, warnings = verify_access(
            root,
            ref,
            level=level,
            license_=license_,
            dataset_class=dataset_class,
            method=method,
            verified_by=verified_by,
            source_url=source_url,
            tier=tier,
            note=note,
            exception=exception,
            rationale=rationale,
            superseded_by=superseded_by,
            followup_task=followup_task,
            on_request_only=on_request_only,
        )
    except EntityCommandError as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    from science_model.frontmatter import parse_frontmatter
    from science_tool.datasets.semantics import runtime_state_for

    parsed = parse_frontmatter(dest)
    runtime_state = runtime_state_for(parsed[0]) if parsed else "blocked-access"
    # Print the actionable verify-access result FIRST so it is not buried under
    # pre-existing, unrelated project audit warnings (fb-2026-06-28-015).
    click.echo(f"{entity_id} -> access={state} (weight {weight:g}), runtime={runtime_state}")

    preexisting = [w for w in warnings if w.startswith("pre-existing audit failure:")]
    for w in warnings:
        if w in preexisting and not show_preexisting:
            continue
        click.echo(f"warning: {w}", err=True)
    if preexisting and not show_preexisting:
        click.echo(
            f"note: {len(preexisting)} pre-existing project audit warning(s) unrelated to this "
            "dataset (run `science validate`, or --show-preexisting to list here)",
            err=True,
        )


@dataset_group.command("link")
@click.argument("dataset_ref")
@click.argument("target_ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_link(dataset_ref: str, target_ref: str, project_root: Path | None) -> None:
    """Append a dataset id to a question/hypothesis datasets: list."""
    from science_tool.datasets_catalog import link_dataset_to_target
    from science_tool.entities import EntityCommandError

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        dataset_id, target_id, dest, changed = link_dataset_to_target(root, dataset_ref, target_ref)
    except EntityCommandError as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)

    rel = dest.relative_to(root)
    prefix = "linked" if changed else "already linked"
    click.echo(f"{prefix} {dataset_id} -> {target_id} ({rel})")


@dataset_group.command("reconcile-links")
@click.option("--fix", is_flag=True, help="Rewrite resolvable free-text datasets: entries to dataset:<slug> ids")
@click.option("--format", "output_format", default="table", type=click.Choice(["table", "json"]))
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_reconcile_links(fix: bool, output_format: str, project_root: Path | None) -> None:
    """Report or fix Q/H free-text datasets: entries that resolve to dataset ids."""
    from science_tool.datasets_catalog import reconcile_dataset_links

    root = project_root.resolve() if project_root else _project_root_from_env()
    rows = unwrap_instrument(reconcile_dataset_links(root, fix=fix), what="dataset reconcile-links")

    def _render() -> None:
        if rows:
            for row in rows:
                action = "fixed" if fix else "would fix"
                click.echo(
                    f"{action}: {row['file']} {row['entity_id']} datasets entry "
                    f"{row['entry']!r} -> {row['resolved_dataset']} ({row['reason']})"
                )
        else:
            click.echo("no resolvable free-text dataset links")

    emit(output_format=output_format, payload={"rows": rows}, render_text=_render)

    if rows and not fix:
        raise click.exceptions.Exit(1)


def _resolve_dataset_or_exit(root: Path, ref: str):
    from science_tool.datasets_catalog import resolve_dataset

    resolved = resolve_dataset(root, ref)
    if resolved is None:
        click.echo(f"no such dataset {ref!r} (searched local entities/datasets/ and commons)", err=True)
        raise click.exceptions.Exit(2)
    return resolved


@dataset_group.command("show")
@click.argument("ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def dataset_show(ref: str, project_root: Path | None) -> None:
    """Show a dataset entity (accepts `slug` or `dataset:slug`)."""
    from science_tool.datasets_catalog import format_show

    root = project_root.resolve() if project_root else _project_root_from_env()
    scope, fm, body = _resolve_dataset_or_exit(root, ref)
    for line in format_show(scope, fm, body):
        click.echo(line)


@dataset_group.command("consumers")
@click.argument("ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def dataset_consumers(ref: str, project_root: Path | None) -> None:
    """List entities that consume this dataset (via consumed_by)."""
    from science_tool.datasets_catalog import consumers_of

    root = project_root.resolve() if project_root else _project_root_from_env()
    _scope, fm, _body = _resolve_dataset_or_exit(root, ref)
    consumers = consumers_of(fm)
    if not consumers:
        click.echo("no recorded consumers")
        return
    for c in consumers:
        click.echo(c)


@dataset_group.command("register-run")
@click.argument("workflow_run_id")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_register_run(workflow_run_id: str, project_root: Path | None) -> None:
    """Register derived datasets for a completed workflow run.

    Writes per-output datapackage.yaml files, creates derived dataset entities,
    and updates symmetric edges (produces/consumed_by).
    """
    from science_tool.datasets_register import (
        FingerprintCaptureError,
        persist_run_fingerprint,
        preflight_register_run_identity,
        write_derived_dataset_entities,
        write_per_output_datapackages,
        write_symmetric_edges,
    )

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        preflight_register_run_identity(root, workflow_run_id)
        fingerprint = persist_run_fingerprint(root, workflow_run_id)
        click.echo(f"captured fingerprint {fingerprint.fingerprint_policy} for {workflow_run_id}")
        dp_paths = write_per_output_datapackages(root, workflow_run_id)
    except (FileNotFoundError, ValueError, FingerprintCaptureError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    for p in dp_paths:
        click.echo(f"wrote {p}")

    try:
        entities = write_derived_dataset_entities(root, workflow_run_id)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    for path, ds_id in entities:
        click.echo(f"entity {ds_id} -> {path}")

    dataset_ids = [ds_id for _, ds_id in entities]
    write_symmetric_edges(root, workflow_run_id, dataset_ids)
    click.echo(f"register-run complete: {len(dp_paths)} outputs, {len(entities)} entities")


@dataset_group.command("stochasticity")
@click.argument("ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
@click.option("--format", "output_format", type=click.Choice(["human", "json"]), default="human")
def dataset_stochasticity(ref: str, project_root: Path | None, output_format: str) -> None:
    """Report which steps in a derived dataset's provenance were stochastic.

    Names the fingerprinted run the dataset inherited its provenance from, the
    seeds that run realized, and which steps are nondeterministic and therefore
    not exactly reproducible.
    """
    from science_tool.datasets_stochasticity import (
        DatasetStochasticityError,
        report_dataset_stochasticity,
    )
    from science_tool.datasets_stochasticity_format import render_human, render_json

    root = project_root.resolve() if project_root else _project_root_from_env()
    try:
        report = report_dataset_stochasticity(root, ref)
    except DatasetStochasticityError as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)

    def _render() -> None:
        for line in render_human(report):
            click.echo(line)

    emit(output_format=output_format, payload=render_json(report), render_text=_render)


@dataset_group.command("migrate-capabilities")
@click.option(
    "--project-root",
    required=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root to migrate (gen-2 -> gen-3 dataset capabilities)",
)
@click.option(
    "--crosswalk",
    "crosswalk_path",
    required=True,
    type=click.Path(path_type=Path, exists=True, file_okay=True, dir_okay=False),
    help="Value-to-term capability crosswalk YAML (required; there is no packaged default)",
)
@click.option("--apply", is_flag=True, help="Write the migration (default is a dry-run report)")
@click.option("--resume", "resume_flag", is_flag=True, help="Finish an interrupted write pass from its journal")
def dataset_migrate_capabilities(
    project_root: Path, crosswalk_path: Path, apply: bool, resume_flag: bool
) -> None:
    """Transactionally rewrite dataset capability fields to the gen-3 shape and pin the project.

    Dry-run by default: prints the per-entity rewrite report (the review artifact). `--apply`
    journals, writes, sets the schema-3 pin LAST, confirms it, then clears the journal. `--resume`
    finishes an interrupted pass. Any refused or unmapped capability shape aborts with nothing written.
    """
    from science_tool.datasets.capability_migration import MigrationRefused, migrate, resume

    try:
        if resume_flag:
            paths = resume(project_root)
        else:
            paths = migrate(project_root, crosswalk_path=crosswalk_path, apply=apply)
    except MigrationRefused as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)

    if resume_flag:
        click.echo(f"resumed: wrote {len(paths)} file(s) and pinned to entity_schema_version 3")
    elif apply:
        click.echo(f"migrated {len(paths)} file(s) and pinned to entity_schema_version 3")
    else:
        click.echo(f"dry-run: {len(paths)} file(s) would be rewritten (use --apply to write)")


@dataset_group.command("reconcile")
@click.argument("slug")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def dataset_reconcile(slug: str, project_root: Path | None) -> None:
    """Check cached-field drift between dataset entity and its runtime datapackage.yaml."""
    import yaml as _yaml
    from science_model.frontmatter import parse_frontmatter

    root = project_root.resolve() if project_root else _project_root_from_env()
    md = root / "entities" / "datasets" / f"{slug}.md"
    if not md.exists():
        click.echo(f"no such dataset entity: {md}", err=True)
        raise click.exceptions.Exit(2)
    result = parse_frontmatter(md)
    fm = result[0] if result else {}
    dp_rel = fm.get("datapackage", "")
    if not dp_rel:
        click.echo("no datapackage: pointer; nothing to reconcile", err=True)
        raise click.exceptions.Exit(0)
    rt_path = root / dp_rel
    if not rt_path.exists():
        click.echo(f"runtime datapackage missing: {rt_path}", err=True)
        raise click.exceptions.Exit(1)
    rt = _yaml.safe_load(rt_path.read_text(encoding="utf-8"))
    drifts = []
    for field in ("license", "update_cadence"):
        e_v = fm.get(field, "")
        r_v = rt.get(field, "")
        if e_v and r_v and e_v != r_v:
            drifts.append(f"{field}: entity={e_v!r} runtime={r_v!r}")
    e_ot = sorted(fm.get("ontology_terms") or [])
    r_ot = sorted(rt.get("ontology_terms") or [])
    if e_ot and r_ot and e_ot != r_ot:
        drifts.append(f"ontology_terms: entity={e_ot} runtime={r_ot}")
    if drifts:
        for d in drifts:
            click.echo(d)
        raise click.exceptions.Exit(1)
    click.echo("in sync")

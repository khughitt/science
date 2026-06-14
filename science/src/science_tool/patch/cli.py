from __future__ import annotations

from pathlib import Path

import click
from rdflib import Dataset

from science_model.patch_definition import PatchDefinitionEntity
from science_tool.graph.materialize import PATCH_MEMBERSHIP_POLICY_VERSION, build_dataset_from_sources
from science_tool.graph.patch_membership import (
    derive_patch_memberships,
    patch_membership_pairs,
    validate_patch_membership_convenience,
)
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import DEFAULT_GRAPH_PATH, canonical_id_from_entity_uri


@click.group("patch")
def patch_group() -> None:
    """Patch definition diagnostics."""


@patch_group.command("explain")
@click.argument("patch_id")
@click.option("--project-root", default=".", show_default=True, type=click.Path(exists=True, path_type=Path, file_okay=False))
def patch_explain(patch_id: str, project_root: Path) -> None:
    """Explain derived patch membership without writing graph.trig."""
    root = project_root.resolve()
    dataset = _load_graph(root)
    definitions = _patch_definitions(root)
    selected = [definition for definition in definitions if definition.canonical_id == patch_id]
    if not selected:
        raise click.ClickException(f"patch definition not found: {patch_id}")
    result = derive_patch_memberships(dataset, selected, policy_version=PATCH_MEMBERSHIP_POLICY_VERSION)
    click.echo(patch_id)
    for warning in result.warnings:
        click.echo(f"warning: {warning}")
    for record in result.records:
        member = canonical_id_from_entity_uri(str(record.member)) or str(record.member)
        predicate = str(record.derivation_predicate) if record.derivation_predicate is not None else ""
        click.echo(
            f"{member}\trole={record.member_role}\tkind={record.member_kind}"
            f"\treason={record.derivation_reason}\tdepth={record.depth}\tpredicate={predicate}"
        )


@patch_group.command("check")
@click.option("--project-root", default=".", show_default=True, type=click.Path(exists=True, path_type=Path, file_okay=False))
def patch_check(project_root: Path) -> None:
    """Re-derive patch membership and diff it against graph.trig."""
    root = project_root.resolve()
    actual_dataset = _load_graph(root)
    expected_dataset = _expected_graph(root)
    errors = validate_patch_membership_convenience(actual_dataset)
    actual_pairs = patch_membership_pairs(actual_dataset)
    expected_pairs = patch_membership_pairs(expected_dataset)
    for pair in sorted(expected_pairs - actual_pairs):
        errors.append(f"stale patch membership: missing {_format_pair(pair)}")
    for pair in sorted(actual_pairs - expected_pairs):
        errors.append(f"stale patch membership: unexpected {_format_pair(pair)}")
    if errors:
        for error in errors:
            click.echo(error)
        raise click.exceptions.Exit(1)
    click.echo("patch check: OK")


def _load_graph(project_root: Path) -> Dataset:
    graph_path = project_root / DEFAULT_GRAPH_PATH
    if not graph_path.is_file():
        raise click.ClickException(f"Graph file not found at {graph_path}. Run `science graph build` first.")
    dataset = Dataset()
    dataset.parse(str(graph_path), format="trig")
    return dataset


def _expected_graph(project_root: Path) -> Dataset:
    sources = load_project_sources(project_root, strict_identity=False)
    return build_dataset_from_sources(sources)


def _patch_definitions(project_root: Path) -> list[PatchDefinitionEntity]:
    sources = load_project_sources(project_root, strict_identity=False)
    return [entity for entity in sources.entities if isinstance(entity, PatchDefinitionEntity)]


def _format_pair(pair: tuple[str, str]) -> str:
    patch_uri, member_uri = pair
    patch = canonical_id_from_entity_uri(patch_uri) or patch_uri
    member = canonical_id_from_entity_uri(member_uri) or member_uri
    return f"{patch} -> {member}"

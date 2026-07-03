"""CLI helpers for authoring dataset ``identity_context`` declarations."""

from __future__ import annotations

import fnmatch
import json
import os
import re
from pathlib import Path
from typing import Any

import click
import yaml

from science_tool.commons.assembly import ASSEMBLY_REGISTRY_ID
from science_tool.commons.gene_crosswalk import GENE_CROSSWALK_ID
from science_tool.commons.identity_resolve import IdentityResolutionMessage, resolve_identity
from science_tool.commons.identity_stamp import derive_stamp
from science_tool.commons.protein_crosswalk import PROTEIN_CROSSWALK_ID
from science_tool.identity_authoring import IdentityAuthoringError, validate_identity_context_declaration


_LOCAL_DATASET_SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_DATAPACKAGE_FORMAT_BY_SUFFIX = {".json": "json", ".yaml": "yaml", ".yml": "yaml"}


def _project_root_from_env() -> Path:
    return Path(os.environ.get("SCIENCE_PROJECT_ROOT") or ".").resolve()


def _render_entity(frontmatter: dict[str, Any], body_suffix: str) -> str:
    front = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{front}---{body_suffix}"


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _dataset_id_from_path(path: Path) -> str:
    return f"dataset:{path.stem}"


def _slug_pattern(ref: str) -> str:
    return ref.removeprefix("dataset:")


def _has_glob(ref: str) -> bool:
    return any(char in ref for char in "*?[")


def _dataset_paths(project_root: Path, ref: str) -> list[Path]:
    dataset_dir = project_root / "entities" / "datasets"
    if _has_glob(ref):
        pattern = _slug_pattern(ref)
        if not dataset_dir.is_dir():
            return []
        return [
            path
            for path in sorted(dataset_dir.glob("*.md"))
            if fnmatch.fnmatchcase(path.stem, pattern) or fnmatch.fnmatchcase(f"dataset:{path.stem}", ref)
        ]
    slug = _slug_pattern(ref)
    if not _LOCAL_DATASET_SLUG_RE.fullmatch(slug):
        return []
    path = dataset_dir / f"{slug}.md"
    return [path] if path.exists() else []


def _load_dataset(path: Path, ref: str) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise click.ClickException(f"no such dataset {ref!r}: {path} does not exist")
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise click.ClickException(f"no such dataset {ref!r}: {path} has no frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise click.ClickException(f"no such dataset {ref!r}: {path} has invalid frontmatter")
    frontmatter = yaml.safe_load(parts[1]) or {}
    if not isinstance(frontmatter, dict):
        raise click.ClickException(f"no such dataset {ref!r}: {path} frontmatter is not a mapping")
    if (frontmatter.get("kind") or frontmatter.get("type")) != "dataset":
        raise click.ClickException(f"no such dataset {ref!r}: {path} is not a dataset entity")
    return frontmatter, parts[2]


def _matching_dataset_paths_or_exit(project_root: Path, ref: str) -> list[Path]:
    paths = _dataset_paths(project_root, ref)
    if not paths:
        raise click.ClickException(f"no such dataset {ref!r} under entities/datasets/")
    return paths


def _set_if_requested(identity_context: dict[str, Any], key: str, value: Any | None) -> None:
    if value is not None:
        identity_context[key] = value


def _build_identity_declaration(
    current: Any,
    *,
    taxon: int | None,
    assembly: str | None,
    gene_namespace: str | None,
    protein_namespace: str | None,
) -> dict[str, Any]:
    identity_context = dict(current) if isinstance(current, dict) else {}
    _set_if_requested(identity_context, "taxon", taxon)
    if assembly is not None:
        identity_context["assembly"] = {
            "label": assembly,
            "registry": ASSEMBLY_REGISTRY_ID,
        }
    molecular_ids = identity_context.get("molecular_ids")
    if not isinstance(molecular_ids, dict):
        molecular_ids = {}
    if gene_namespace is not None:
        molecular_ids["gene"] = {
            "namespace": gene_namespace,
            "registry": GENE_CROSSWALK_ID,
        }
    if protein_namespace is not None:
        molecular_ids["protein"] = {
            "namespace": protein_namespace,
            "registry": PROTEIN_CROSSWALK_ID,
        }
    if molecular_ids:
        identity_context["molecular_ids"] = molecular_ids
    return identity_context


def _identity_status(identity_context: dict[str, Any]) -> str:
    statuses: list[str] = []
    assembly = identity_context.get("assembly")
    if isinstance(assembly, dict) and isinstance(assembly.get("resolution_status"), str):
        statuses.append(assembly["resolution_status"])
    molecular_ids = identity_context.get("molecular_ids")
    if isinstance(molecular_ids, dict):
        statuses.extend(
            decl.get("resolution_status")
            for decl in molecular_ids.values()
            if isinstance(decl, dict) and isinstance(decl.get("resolution_status"), str)
        )
    if "declared_unresolved" in statuses:
        return "declared_unresolved"
    if statuses and all(status == "resolved" for status in statuses):
        return "resolved"
    return "declared"


def _echo_messages(messages: tuple[IdentityResolutionMessage, ...]) -> None:
    for message in messages:
        click.echo(f"{message.level}: {message.path}: {message.message}", err=message.level != "info")


def _has_resolution_error(messages: tuple[IdentityResolutionMessage, ...]) -> bool:
    return any(message.level == "error" for message in messages)


def _project_relative_existing_path(project_root: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return None
    resolved = (project_root / candidate).resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return None
    return resolved if resolved.exists() and resolved.is_file() else None


def _stamp_datapackage(project_root: Path, frontmatter: dict[str, Any]) -> bool:
    datapackage = frontmatter.get("datapackage")
    identity_context = frontmatter.get("identity_context")
    if not isinstance(datapackage, str) or not datapackage.strip() or not isinstance(identity_context, dict):
        return False
    datapackage_path = _project_relative_existing_path(project_root, datapackage)
    if datapackage_path is None:
        click.echo(f"warning: datapackage not stamped; missing or unsafe path {datapackage!r}", err=True)
        return False
    descriptor_format = _DATAPACKAGE_FORMAT_BY_SUFFIX.get(datapackage_path.suffix)
    if descriptor_format is None:
        click.echo(f"warning: datapackage not stamped; unsupported extension {datapackage_path.suffix!r}", err=True)
        return False
    before = datapackage_path.read_text(encoding="utf-8")
    loaded = json.loads(before) if descriptor_format == "json" else yaml.safe_load(before)
    loaded = loaded or {}
    if not isinstance(loaded, dict):
        click.echo(f"warning: datapackage not stamped; top level is not a mapping: {datapackage}", err=True)
        return False
    science = loaded.get("science")
    if not isinstance(science, dict):
        science = {}
    science["identity_context"] = derive_stamp(identity_context)
    loaded["science"] = science
    text = (
        json.dumps(loaded, indent=2, ensure_ascii=False) + "\n"
        if descriptor_format == "json"
        else yaml.safe_dump(loaded, sort_keys=False, allow_unicode=True, default_flow_style=False)
    )
    if text != before:
        _atomic_write(datapackage_path, text)
    return True


@click.group(name="identity")
def identity_group() -> None:
    """Author and inspect dataset identity_context declarations."""


@identity_group.command("resolve")
@click.argument("ref")
@click.option("--taxon", type=int, default=None)
@click.option("--assembly", default=None)
@click.option("--gene-namespace", default=None)
@click.option("--protein-namespace", default=None)
@click.option("--stamp", is_flag=True, help="Also stamp science.identity_context into an existing datapackage.")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def resolve_cmd(
    ref: str,
    taxon: int | None,
    assembly: str | None,
    gene_namespace: str | None,
    protein_namespace: str | None,
    stamp: bool,
    project_root: Path | None,
) -> None:
    """Resolve or degrade a dataset identity_context declaration."""
    root = project_root.resolve() if project_root else _project_root_from_env()
    for path in _matching_dataset_paths_or_exit(root, ref):
        frontmatter, body_suffix = _load_dataset(path, ref)
        identity_context = _build_identity_declaration(
            frontmatter.get("identity_context"),
            taxon=taxon,
            assembly=assembly,
            gene_namespace=gene_namespace,
            protein_namespace=protein_namespace,
        )
        resolved = resolve_identity(identity_context)
        if _has_resolution_error(resolved.messages):
            dataset_id = (
                frontmatter.get("id") if isinstance(frontmatter.get("id"), str) else _dataset_id_from_path(path)
            )
            _echo_messages(resolved.messages)
            raise click.ClickException(f"identity resolution failed for {dataset_id}")
        try:
            identity_context = validate_identity_context_declaration(resolved.identity_context)
        except IdentityAuthoringError as exc:
            raise click.ClickException(str(exc)) from exc
        frontmatter["identity_context"] = identity_context
        next_text = _render_entity(frontmatter, body_suffix)
        before = path.read_text(encoding="utf-8")
        dataset_id = frontmatter.get("id") if isinstance(frontmatter.get("id"), str) else _dataset_id_from_path(path)
        changed = next_text != before
        if changed:
            _atomic_write(path, next_text)
        stamped = _stamp_datapackage(root, frontmatter) if stamp else False
        status = _identity_status(resolved.identity_context)
        verb = "updated" if changed else "unchanged"
        suffix = " stamped" if stamped else ""
        click.echo(f"{verb} {dataset_id} identity_context resolution={status}{suffix}")
        _echo_messages(resolved.messages)


@identity_group.command("show")
@click.argument("ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def show_cmd(ref: str, project_root: Path | None) -> None:
    """Print the current dataset identity_context block."""
    root = project_root.resolve() if project_root else _project_root_from_env()
    paths = _matching_dataset_paths_or_exit(root, ref)
    if len(paths) != 1:
        raise click.ClickException(f"show expects one dataset, got {len(paths)} matches for {ref!r}")
    frontmatter, _body = _load_dataset(paths[0], ref)
    identity_context = (
        frontmatter.get("identity_context") if isinstance(frontmatter.get("identity_context"), dict) else {}
    )
    click.echo(yaml.safe_dump(identity_context, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip())


@identity_group.command("suggest")
@click.argument("ref")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def suggest_cmd(ref: str, project_root: Path | None) -> None:
    """Print a conservative identity_context scaffold without editing files."""
    root = project_root.resolve() if project_root else _project_root_from_env()
    paths = _matching_dataset_paths_or_exit(root, ref)
    if len(paths) != 1:
        raise click.ClickException(f"suggest expects one dataset, got {len(paths)} matches for {ref!r}")
    frontmatter, _body = _load_dataset(paths[0], ref)
    dataset_id = frontmatter.get("id") if isinstance(frontmatter.get("id"), str) else _dataset_id_from_path(paths[0])
    scaffold = {
        "identity_context": {
            "taxon": None,
            "assembly": {
                "label": None,
                "registry": ASSEMBLY_REGISTRY_ID,
            },
            "molecular_ids": {
                "gene": {
                    "namespace": None,
                    "registry": GENE_CROSSWALK_ID,
                },
                "protein": {
                    "namespace": None,
                    "registry": PROTEIN_CROSSWALK_ID,
                },
            },
        }
    }
    click.echo(f"suggested identity_context scaffold for {dataset_id}:")
    click.echo(yaml.safe_dump(scaffold, sort_keys=False, allow_unicode=True, default_flow_style=False).rstrip())

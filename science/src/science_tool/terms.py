from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from science_tool.graph.entity_registry import EntityKindNotRegisteredError
from science_tool.graph.identity_table import IdentityDeclaration, ParticipationMode, build_identity_table
from science_tool.graph.sources import (
    _enrich_raw,
    _format_missing_fields,
    load_project_sources,
    local_profile_sources_dir,
    resolve_local_profile_name,
)


class TermsCommandError(ValueError):
    """Raised for user-correctable terms CLI errors."""


@dataclass(frozen=True)
class TermsAddResult:
    term_id: str
    path: Path


def add_term(
    term_id: str,
    *,
    title: str,
    project_root: Path,
    description: str | None = None,
    aliases: Sequence[str] = (),
    same_as: Sequence[str] = (),
    ontology_terms: Sequence[str] = (),
) -> TermsAddResult:
    project_root = project_root.resolve()
    kind, _local_id = _parse_term_id(term_id)
    profile_name = resolve_local_profile_name(project_root)
    path = local_profile_sources_dir(project_root, local_profile=profile_name) / "terms.yaml"

    document = _load_terms_document(path)
    terms = document["terms"]
    _reject_duplicate_target_row(terms, term_id=term_id, path=path)

    sources = load_project_sources(project_root, strict_identity=False)
    try:
        schema = sources.registry.resolve(kind)
    except EntityKindNotRegisteredError as exc:
        raise TermsCommandError(
            f"Unsupported term id prefix {kind!r}: science terms add requires a registered entity kind. "
            "Use --ontology-term for external ontology CURIEs."
        ) from exc

    _reject_identity_collisions(sources, term_id=term_id)

    row: dict[str, object] = {
        "id": term_id,
        "title": title,
    }
    if description:
        row["description"] = description
    if aliases:
        row["aliases"] = list(aliases)
    if same_as:
        row["same_as"] = list(same_as)
    if ontology_terms:
        row["ontology_terms"] = list(ontology_terms)

    canonical_id = _validate_lightweight_term_row(
        row,
        kind=kind,
        schema=schema,
        project_root=project_root,
        local_profile=profile_name,
        source_path=str(path.relative_to(project_root)),
        ontology_catalogs=sources.ontology_catalogs,
    )
    if canonical_id != term_id:
        raise TermsCommandError(f"{term_id} canonicalizes to {canonical_id}; use the canonical id as the term id")

    terms.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return TermsAddResult(term_id=term_id, path=path)


def _parse_term_id(term_id: str) -> tuple[str, str]:
    prefix, separator, local_id = term_id.partition(":")
    if not separator or not prefix or not local_id:
        raise TermsCommandError(f"term id must be a CURIE with a prefix and local id, got {term_id!r}")
    return prefix, local_id


def _load_terms_document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"terms": []}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TermsCommandError(f"{path}: terms.yaml is not valid YAML") from exc
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise TermsCommandError(f"{path}: expected a mapping with a list-valued 'terms' key")
    document = dict(loaded)
    terms = document.get("terms")
    if not isinstance(terms, list):
        raise TermsCommandError(f"{path}: expected a list-valued 'terms' key")
    return document


def _reject_duplicate_target_row(terms: list[object], *, term_id: str, path: Path) -> None:
    for index, row in enumerate(terms, start=1):
        if not isinstance(row, Mapping):
            raise TermsCommandError(f"{path}: terms row {index} must be a mapping")
        row_id = row.get("id")
        canonical_id = row.get("canonical_id")
        if row_id == term_id or canonical_id == term_id:
            raise TermsCommandError(f"{term_id} already exists in the target terms.yaml at {path}")


def _reject_identity_collisions(sources: object, *, term_id: str) -> None:
    table = build_identity_table(sources)
    target_owners = [
        row
        for row in table.rows
        if row.participation_mode is ParticipationMode.OWNER and row.canonical_id == term_id
    ]
    if target_owners:
        locations = ", ".join(_owner_location(owner) for owner in sorted(target_owners, key=_owner_location))
        raise TermsCommandError(f"{term_id} already resolves to an existing owner: {locations}")

    genuine_collisions = [collision for collision in table.collisions() if collision.is_genuine]
    if genuine_collisions:
        collision_ids = ", ".join(sorted({collision.canonical_id for collision in genuine_collisions}))
        raise TermsCommandError(
            "Project already contains identity collision(s) unrelated to this term: "
            f"{collision_ids}. Resolve them before adding terms."
        )


def _owner_location(owner: IdentityDeclaration) -> str:
    path = owner.source_ref.path if owner.source_ref is not None else "<unknown>"
    return f"{owner.adapter}:{path}"


def _validate_lightweight_term_row(
    row: dict[str, object],
    *,
    kind: str,
    schema: Any,
    project_root: Path,
    local_profile: str,
    source_path: str,
    ontology_catalogs: list[object],
) -> str:
    raw = dict(row)
    canonical_id = raw.get("canonical_id") or raw.get("id")
    if isinstance(canonical_id, str) and canonical_id:
        raw.setdefault("canonical_id", canonical_id)
        if "kind" not in raw and ":" in canonical_id:
            raw["kind"] = canonical_id.split(":", 1)[0]
    raw.pop("content", None)
    raw.pop("body", None)
    raw.setdefault("file_path", source_path)

    _enrich_raw(
        raw,
        kind=kind,
        project_slug=project_root.name,
        local_profile=local_profile,
        active_kinds=frozenset(),
        ontology_catalogs=ontology_catalogs,
    )
    try:
        entity = schema.model_validate(raw)
    except ValidationError as exc:
        term_id = str(row["id"])
        raise TermsCommandError(
            f"{term_id} cannot be represented as a lightweight term: {_format_missing_fields(exc)}"
        ) from exc
    return str(entity.canonical_id)

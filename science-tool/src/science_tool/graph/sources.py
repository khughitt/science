"""Structured upstream sources for deterministic graph materialization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, Field
from science_model.ontologies import load_catalogs_for_names
from science_model.ontologies.schema import OntologyCatalog
from science_model.profiles import CORE_PROFILE, load_shared_profile
from science_model.profiles.schema import ProfileManifest
from science_model.source_contracts import AuthoredTargetedRelation, BindingSource, ModelSource, ParameterSource

from science_tool.big_picture.literature_prefix import canonical_paper_id
from science_tool.graph.entity_providers.base import EntityDiscoveryContext
from science_tool.graph.entity_providers.resolver import EntityResolver, default_providers
from science_tool.graph.source_types import (
    EntityDatapackageInvalidError,  # noqa: F401
    EntityIdCollisionError,  # noqa: F401
    KnowledgeProfiles,
    SourceEntity,
    SourceRelation,
)
from science_tool.paths import resolve_paths
from science_tool.tasks import parse_tasks

_SHORT_ID_RE = re.compile(r"^(?P<token>[a-z]\d+)(?:[-_].*)?$", re.IGNORECASE)
_EXTERNAL_PREFIXES = frozenset({"go", "mesh", "doid", "hp", "so", "ncbitaxon", "ncbigene", "ensembl"})
_CORE_KINDS = frozenset(kind.name for kind in CORE_PROFILE.entity_kinds)
_SourceRecordT = TypeVar("_SourceRecordT", bound=BaseModel)


def known_kinds(
    extra_profiles: list[ProfileManifest] | None = None,
    ontology_catalogs: list[OntologyCatalog] | None = None,
) -> frozenset[str]:
    """Return entity kind names from core + extra profiles + ontology catalogs."""
    kinds = set(_CORE_KINDS)
    for profile in extra_profiles or []:
        kinds.update(kind.name for kind in profile.entity_kinds)
    for catalog in ontology_catalogs or []:
        kinds.update(et.name for et in catalog.entity_types)
    return frozenset(kinds)


def external_prefixes(ontology_catalogs: list[OntologyCatalog]) -> frozenset[str]:
    """Collect CURIE prefixes from declared ontology catalogs."""
    prefixes: set[str] = set()
    for catalog in ontology_catalogs:
        for et in catalog.entity_types:
            prefixes.update(p.lower() for p in et.curie_prefixes)
    return frozenset(prefixes)


class AliasCollisionError(ValueError):
    """Raised when two canonical entities claim the same alias."""

    def __init__(self, alias: str, first_canonical_id: str, second_canonical_id: str) -> None:
        self.alias = alias
        self.first_canonical_id = first_canonical_id
        self.second_canonical_id = second_canonical_id
        super().__init__(f"Alias '{alias}' maps to both {first_canonical_id} and {second_canonical_id}")


class ProjectSources(BaseModel):
    """Structured source bundle used to materialize a project graph."""

    project_name: str
    project_root: str
    profiles: KnowledgeProfiles
    entities: list[SourceEntity]
    relations: list[SourceRelation] = Field(default_factory=list)
    bindings: list[BindingSource] = Field(default_factory=list)
    manual_aliases: dict[str, str] = Field(default_factory=dict)
    ontology_catalogs: list[OntologyCatalog] = Field(default_factory=list)


SourceBinding = BindingSource


def load_project_sources(project_root: Path) -> ProjectSources:
    """Load typed project entities from markdown docs and task files."""
    project_root = project_root.resolve()
    config = _read_project_config(project_root)
    paths = resolve_paths(project_root)
    profiles = KnowledgeProfiles.model_validate(config["knowledge_profiles"])

    # Load declared ontology catalogs
    declared_ontologies: list[str] = list(config.get("ontologies") or [])  # type: ignore[union-attr]
    ontology_catalogs = load_catalogs_for_names(declared_ontologies) if declared_ontologies else []

    # Always try to load shared profile (no longer gated on curated list)
    extra_profiles: list[ProfileManifest] = []
    shared = load_shared_profile()
    if shared is not None:
        extra_profiles.append(shared)

    active_kinds = known_kinds(extra_profiles=extra_profiles, ontology_catalogs=ontology_catalogs)

    entities: list[SourceEntity] = []
    local_profile = profiles.local

    ctx = EntityDiscoveryContext(
        project_root=project_root,
        project_slug=project_root.name,
        local_profile=local_profile,
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )
    resolver = EntityResolver(default_providers())
    entities.extend(resolver.discover(ctx))

    entities.extend(
        _load_task_entities(
            project_root,
            paths.tasks_dir,
            local_profile=local_profile,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )
    )

    model_entities, model_relations = _load_model_sources(project_root, local_profile=local_profile)
    parameter_entities, parameter_relations = _load_parameter_sources(project_root, local_profile=local_profile)
    entities.extend(model_entities)
    entities.extend(parameter_entities)

    # Final global collision check across resolver + specialized parsers.
    seen: dict[str, list[tuple[str, str]]] = {}
    for e in entities:
        seen.setdefault(e.canonical_id, []).append((e.provider, e.source_path))
    collisions = {cid: srcs for cid, srcs in seen.items() if len(srcs) > 1}
    if collisions:
        cid, sources = next(iter(collisions.items()))
        raise EntityIdCollisionError(cid, sources)

    entities.sort(key=lambda entity: entity.canonical_id)
    relations = _load_structured_relations(project_root, local_profile=local_profile)
    relations.extend(model_relations)
    relations.extend(parameter_relations)
    relations.sort(key=lambda relation: (relation.graph_layer, relation.subject, relation.predicate, relation.object))
    bindings = _load_binding_sources(project_root, local_profile=local_profile)
    bindings.sort(key=lambda binding: (binding.model, binding.parameter, binding.source_path))

    return ProjectSources(
        project_name=str(config["name"]),
        project_root=str(project_root),
        profiles=profiles,
        entities=entities,
        relations=relations,
        bindings=bindings,
        manual_aliases=_load_manual_aliases(project_root, local_profile=local_profile),
        ontology_catalogs=ontology_catalogs,
    )


def build_alias_map(entities: list[SourceEntity], manual_aliases: dict[str, str] | None = None) -> dict[str, str]:
    """Build a best-effort alias map for canonical entity resolution."""
    alias_map: dict[str, str] = {}
    for entity in entities:
        _register_alias(alias_map, entity.canonical_id, entity.canonical_id)
        _register_alias(alias_map, entity.canonical_id.lower(), entity.canonical_id)
        for alias in entity.aliases:
            _register_alias(alias_map, alias, entity.canonical_id)
            _register_alias(alias_map, alias.lower(), entity.canonical_id)
    for alias, canonical_id in (manual_aliases or {}).items():
        _register_alias(alias_map, alias, canonical_id)
        _register_alias(alias_map, alias.lower(), canonical_id)
    return alias_map


def is_external_reference(raw: str, *, known_prefixes: frozenset[str] | None = None) -> bool:
    """Return True when a reference points outside the project graph."""
    if raw.startswith(("http://", "https://")):
        return True
    if ":" not in raw:
        return False
    prefix, _ = raw.split(":", 1)
    check_set = known_prefixes if known_prefixes is not None else _EXTERNAL_PREFIXES
    return prefix.lower() in check_set


def is_metadata_reference(raw: str) -> bool:
    """Return True for `meta:*` refs.

    Meta refs are intentional annotations preserved in source files but
    excluded from KG materialization (no entity required, no edge created).
    """
    return raw.startswith("meta:")


def _load_task_entities(
    project_root: Path,
    tasks_dir: Path,
    *,
    local_profile: str,
    active_kinds: frozenset[str] | None = None,
    ontology_catalogs: list[OntologyCatalog] | None = None,
) -> list[SourceEntity]:
    entities: list[SourceEntity] = []
    for path in _task_paths(tasks_dir):
        rel_path = path.relative_to(project_root).as_posix()
        for task in parse_tasks(path):
            canonical_id = f"task:{task.id.lower()}"
            entities.append(
                SourceEntity(
                    canonical_id=canonical_id,
                    kind="task",
                    title=task.title,
                    profile=_default_profile_for_kind(
                        "task",
                        local_profile=local_profile,
                        active_kinds=active_kinds,
                        ontology_catalogs=ontology_catalogs,
                    ),
                    source_path=rel_path,
                    provider="task",
                    status=task.status,
                    content_preview=task.description,
                    related=task.related,
                    blocked_by=task.blocked_by,
                    aliases=_derive_aliases(canonical_id, [task.id, task.id.upper()]),
                )
            )
    return entities


def _load_model_sources(project_root: Path, *, local_profile: str) -> tuple[list[SourceEntity], list[SourceRelation]]:
    records = _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name="models.yaml",
        root_key="models",
        model=ModelSource,
    )

    entities: list[SourceEntity] = []
    relations: list[SourceRelation] = []
    for record in records:
        entities.append(
            SourceEntity(
                canonical_id=record.canonical_id,
                kind="model",
                title=record.title,
                profile=record.profile,
                source_path=record.source_path,
                provider="model",
                domain=record.domain,
                related=record.related,
                source_refs=record.source_refs,
                aliases=_derive_aliases(record.canonical_id, record.aliases),
            )
        )
        relations.extend(_nested_relations(record.canonical_id, record.relations, source_path=record.source_path))

    return entities, relations


def _load_parameter_sources(
    project_root: Path, *, local_profile: str
) -> tuple[list[SourceEntity], list[SourceRelation]]:
    records = _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name="parameters.yaml",
        root_key="parameters",
        model=ParameterSource,
    )

    entities: list[SourceEntity] = []
    relations: list[SourceRelation] = []
    for record in records:
        entities.append(
            SourceEntity(
                canonical_id=record.canonical_id,
                kind="canonical_parameter",
                title=record.title,
                profile=record.profile,
                source_path=record.source_path,
                provider="parameter",
                domain=record.domain,
                content_preview=_parameter_preview(record),
                related=record.related,
                source_refs=record.source_refs,
                ontology_terms=record.ontology_terms,
                aliases=_derive_aliases(record.canonical_id, record.aliases),
            )
        )
        relations.extend(_nested_relations(record.canonical_id, record.relations, source_path=record.source_path))

    return entities, relations


def _load_binding_sources(project_root: Path, *, local_profile: str) -> list[BindingSource]:
    return _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name="bindings.yaml",
        root_key="bindings",
        model=BindingSource,
    )


def _task_paths(tasks_dir: Path) -> list[Path]:
    paths: list[Path] = []
    active_path = tasks_dir / "active.md"
    if active_path.is_file():
        paths.append(active_path)

    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        paths.extend(sorted(done_dir.glob("*.md")))
    return paths


def _load_structured_relations(project_root: Path, *, local_profile: str) -> list[SourceRelation]:
    relations_path = local_profile_sources_dir(project_root, local_profile=local_profile) / "relations.yaml"
    if not relations_path.is_file():
        return []

    data = yaml.safe_load(relations_path.read_text(encoding="utf-8")) or {}
    items = data.get("relations") or []
    if not isinstance(items, list):
        return []

    relations: list[SourceRelation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        subject = item.get("subject")
        predicate = item.get("predicate")
        obj = item.get("object")
        if not isinstance(subject, str) or not subject:
            continue
        if not isinstance(predicate, str) or not predicate:
            continue
        if not isinstance(obj, str) or not obj:
            continue

        subject = canonical_paper_id(subject)
        obj = canonical_paper_id(obj)

        relations.append(
            SourceRelation(
                subject=subject,
                predicate=predicate,
                object=obj,
                graph_layer=str(item.get("graph_layer") or "graph/knowledge"),
                source_path=str(item.get("source_path") or _default_local_source_path(local_profile, "relations.yaml")),
            )
        )

    return relations


def _load_typed_records(
    project_root: Path,
    *,
    local_profile: str,
    file_name: str,
    root_key: str,
    model: type[_SourceRecordT],
) -> list[_SourceRecordT]:
    path = local_profile_sources_dir(project_root, local_profile=local_profile) / file_name
    if not path.is_file():
        return []

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = data.get(root_key) or []
    if not isinstance(items, list):
        return []

    records: list[_SourceRecordT] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        records.append(model.model_validate(item))
    return records


def _read_project_config(project_root: Path) -> dict[str, object]:
    yaml_path = project_root / "science.yaml"
    data: dict[str, object] = {}
    if yaml_path.is_file():
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    knowledge_profiles = data.get("knowledge_profiles") or {}
    if not isinstance(knowledge_profiles, dict):
        knowledge_profiles = {}

    raw_ontologies = data.get("ontologies") or []
    if not isinstance(raw_ontologies, list):
        raw_ontologies = []

    return {
        "name": str(data.get("name") or project_root.name),
        "knowledge_profiles": {
            "local": str(knowledge_profiles.get("local") or "local"),
        },
        "ontologies": [str(o) for o in raw_ontologies],
    }


def _load_manual_aliases(project_root: Path, *, local_profile: str) -> dict[str, str]:
    mappings_path = local_profile_sources_dir(project_root, local_profile=local_profile) / "mappings.yaml"
    if not mappings_path.is_file():
        return {}

    data = yaml.safe_load(mappings_path.read_text(encoding="utf-8")) or {}
    aliases = data.get("aliases") or {}
    if not isinstance(aliases, dict):
        return {}

    result: dict[str, str] = {}
    for alias, canonical_id in aliases.items():
        if isinstance(alias, str) and isinstance(canonical_id, str):
            result[alias] = canonical_id
    return result


def _nested_relations(
    subject: str,
    relations: list[AuthoredTargetedRelation],
    *,
    source_path: str,
) -> list[SourceRelation]:
    flattened: list[SourceRelation] = []
    for relation in relations:
        flattened.append(
            SourceRelation(
                subject=subject,
                predicate=relation.predicate,
                object=relation.target,
                graph_layer=relation.graph_layer,
                source_path=source_path,
            )
        )
    return flattened


def _parameter_preview(record: ParameterSource) -> str:
    tokens = [record.symbol]
    if record.units:
        tokens.append(record.units)
    if record.quantity_group:
        tokens.append(record.quantity_group)
    return " | ".join(token for token in tokens if token)


def _derive_aliases(canonical_id: str, explicit_aliases: list[str]) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()

    def add(alias: str) -> None:
        cleaned = alias.strip()
        if not cleaned or cleaned == canonical_id or cleaned in seen:
            return
        seen.add(cleaned)
        aliases.append(cleaned)

    for alias in explicit_aliases:
        add(alias)

    kind, slug = canonical_id.split(":", 1)
    if kind not in {"hypothesis", "question", "task"}:
        return aliases

    match = _SHORT_ID_RE.match(slug)
    if match is None:
        head = slug.split("-", 1)[0]
        match = _SHORT_ID_RE.match(head)
    if match is not None:
        token = match.group("token")
        add(f"{kind}:{token.lower()}")
        add(f"{kind}:{token.upper()}")
        add(token.lower())
        add(token.upper())

    return aliases


def _register_alias(alias_map: dict[str, str], alias: str, canonical_id: str) -> None:
    existing = alias_map.get(alias)
    if existing is not None and existing != canonical_id:
        raise AliasCollisionError(alias=alias, first_canonical_id=existing, second_canonical_id=canonical_id)
    alias_map[alias] = canonical_id


def _default_profile_for_kind(
    kind: str,
    *,
    local_profile: str,
    active_kinds: frozenset[str] | None = None,
    ontology_catalogs: list[OntologyCatalog] | None = None,
) -> str:
    if kind in _CORE_KINDS:
        return "core"
    for catalog in ontology_catalogs or []:
        if any(et.name == kind for et in catalog.entity_types):
            return catalog.ontology
    return local_profile


def local_profile_sources_dir(project_root: Path, *, local_profile: str) -> Path:
    """Return the structured source directory for the configured local profile."""
    return project_root / "knowledge" / "sources" / local_profile


def _default_local_source_path(local_profile: str, file_name: str) -> str:
    return f"knowledge/sources/{local_profile}/{file_name}"

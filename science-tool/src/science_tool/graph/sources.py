"""Structured upstream sources for deterministic graph materialization."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, Field, ValidationError
from science_model.entities import Entity, EntityType, ProjectEntity, DomainEntity, core_entity_type_for_kind
from science_model.ontologies import load_catalogs_for_names
from science_model.ontologies.schema import OntologyCatalog
from science_model.profiles import CORE_PROFILE, LOCAL_PROFILE, load_profile_manifest, load_shared_profile
from science_model.profiles.schema import ProfileManifest
from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    ProxyDirectness,
    SupportScope,
)
from science_model.source_contracts import AuthoredTargetedRelation, BindingSource, ModelSource, ParameterSource
from science_model.source_ref import SourceRef

from science_tool.big_picture.literature_prefix import canonical_paper_id
from science_tool.graph.entity_registry import EntityKindNotRegisteredError, EntityRegistry
from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.storage_adapters.aggregate import AggregateAdapter
from science_tool.graph.storage_adapters.base import StorageAdapter
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter
from science_tool.graph.storage_adapters.task import TaskAdapter
from science_tool.paths import resolve_paths

logger = logging.getLogger(__name__)

_SHORT_ID_RE = re.compile(r"^(?P<token>[a-z]\d+)(?:[-_].*)?$", re.IGNORECASE)
_EXTERNAL_PREFIXES = frozenset({"go", "mesh", "doid", "hp", "so", "ncbitaxon", "ncbigene", "ensembl"})
_CORE_KINDS = frozenset(kind.name for kind in CORE_PROFILE.entity_kinds)
_SourceRecordT = TypeVar("_SourceRecordT", bound=BaseModel)

_ENUM_FIELDS: dict[str, type] = {
    "claim_layer": ClaimLayer,
    "identification_strength": IdentificationStrength,
    "proxy_directness": ProxyDirectness,
    "supports_scope": SupportScope,
    "evidence_role": EvidenceRole,
}


class KnowledgeProfiles(BaseModel):
    """Selected knowledge profiles for a project."""

    local: str = "local"


class SourceRelation(BaseModel):
    """An authored relation collected from structured source files."""

    subject: str
    predicate: str
    object: str
    graph_layer: str = "graph/knowledge"
    source_path: str


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

    model_config = {"arbitrary_types_allowed": True}

    project_name: str
    project_root: str
    profiles: KnowledgeProfiles
    entities: list[Entity]
    relations: list[SourceRelation] = Field(default_factory=list)
    bindings: list[BindingSource] = Field(default_factory=list)
    manual_aliases: dict[str, str] = Field(default_factory=dict)
    ontology_catalogs: list[OntologyCatalog] = Field(default_factory=list)


SourceBinding = BindingSource


def load_project_sources(project_root: Path) -> ProjectSources:
    """Load all project entities through the unified registry + adapters flow."""
    project_root = project_root.resolve()
    config = _read_project_config(project_root)
    profiles = KnowledgeProfiles.model_validate(config["knowledge_profiles"])
    local_profile = profiles.local

    declared_ontologies: list[str] = list(config.get("ontologies") or [])  # type: ignore[union-attr]
    ontology_catalogs = load_catalogs_for_names(declared_ontologies) if declared_ontologies else []
    local_profile_manifest = load_profile_manifest(
        local_profile_sources_dir(project_root, local_profile=local_profile) / "manifest.yaml"
    )

    profile_manifests: list[ProfileManifest] = [LOCAL_PROFILE]
    shared = load_shared_profile()
    if shared is not None:
        profile_manifests.append(shared)
    active_profiles = profile_manifests.copy()
    if local_profile_manifest is not None:
        active_profiles.append(local_profile_manifest)

    active_kinds = known_kinds(extra_profiles=active_profiles, ontology_catalogs=ontology_catalogs)

    registry = EntityRegistry.with_core_types()
    for profile in profile_manifests:
        for entity_kind in profile.entity_kinds:
            registry.register_profile_kind(entity_kind.name, ProjectEntity, owner=profile.name)
    for catalog in ontology_catalogs:
        for entity_type in catalog.entity_types:
            registry.register_catalog_kind(entity_type.name, DomainEntity, owner=catalog.ontology)
    if local_profile_manifest is not None:
        for entity_kind in local_profile_manifest.entity_kinds:
            registry.register_extension_kind(entity_kind.name, ProjectEntity)

    adapters: list[StorageAdapter] = [
        MarkdownAdapter(),
        AggregateAdapter(local_profile=local_profile),
        DatapackageAdapter(),
        TaskAdapter(),
    ]

    project_slug = project_root.name
    identity_table: dict[str, SourceRef] = {}
    entities: list[Entity] = []

    # cwd for relative-path resolution in adapters. The StorageAdapter.load_raw()
    # contract resolves ref.path against cwd; we chdir into project_root rather
    # than broaden the Protocol. Restored in the finally block.
    prev_cwd = os.getcwd()
    os.chdir(project_root)
    try:
        for adapter in adapters:
            for ref in adapter.discover(project_root):
                raw = adapter.load_raw(ref)
                raw_kind = raw.get("kind")
                if not isinstance(raw_kind, str) or not raw_kind:
                    # Adapter returned a record with no kind (e.g. frontmatter-less
                    # markdown). Skip rather than fail — mirrors the legacy behavior
                    # where parse_entity_file returned None.
                    continue
                kind = _normalize_kind(raw_kind)
                raw["kind"] = kind
                _enrich_raw(
                    raw,
                    kind=kind,
                    project_slug=project_slug,
                    local_profile=local_profile,
                    active_kinds=active_kinds,
                    ontology_catalogs=ontology_catalogs,
                )
                try:
                    schema = registry.resolve(kind)
                except EntityKindNotRegisteredError:
                    logger.warning(
                        "skipping %s: unknown entity kind %r (not registered in core or active profiles)",
                        ref.path,
                        kind,
                    )
                    continue
                try:
                    entity = schema.model_validate(raw)
                except ValidationError as exc:
                    missing = _format_missing_fields(exc)
                    logger.warning(
                        "skipping %s: schema validation failed for kind %r (%s)",
                        ref.path,
                        kind,
                        missing,
                    )
                    continue
                existing = identity_table.get(entity.canonical_id)
                if existing is not None:
                    raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
                identity_table[entity.canonical_id] = ref
                entities.append(entity)
    finally:
        os.chdir(prev_cwd)

    # Legacy model/parameter loaders from knowledge/sources/<local>/{models,parameters}.yaml.
    # Produce ProjectEntity records through the registry so they join the same pipeline.
    paths = resolve_paths(project_root)
    del paths  # unused; kept to document intent
    for entity, ref in _load_legacy_records(
        project_root,
        registry=registry,
        local_profile=local_profile,
        project_slug=project_slug,
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    ):
        existing = identity_table.get(entity.canonical_id)
        if existing is not None:
            raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
        identity_table[entity.canonical_id] = ref
        entities.append(entity)

    entities.sort(key=lambda e: e.canonical_id)

    relations = _load_structured_relations(project_root, local_profile=local_profile)
    # Legacy model/parameter relations come from the nested authored-relations block.
    relations.extend(
        _legacy_nested_relations(
            project_root,
            local_profile=local_profile,
            file_name="models.yaml",
            root_key="models",
            model=ModelSource,
        )
    )
    relations.extend(
        _legacy_nested_relations(
            project_root,
            local_profile=local_profile,
            file_name="parameters.yaml",
            root_key="parameters",
            model=ParameterSource,
        )
    )
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


def build_alias_map(entities: list[Entity], manual_aliases: dict[str, str] | None = None) -> dict[str, str]:
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
    """Return True when a reference points outside the project graph.

    Treated as external:
    - URLs (http(s)://...)
    - Filesystem paths (absolute `/...`, relative `./...` / `../...`, or any
      value containing `/` with no `:` prefix). Projects commonly cite
      data artifacts and result files from `source_refs:` — these should
      not be audited against the entity alias map.
    - Values with a declared external prefix (go:, mesh:, doi:, ...).
    """
    if raw.startswith(("http://", "https://")):
        return True
    if raw.startswith(("/", "./", "../")):
        return True
    if ":" not in raw:
        # No colon → either a filesystem path-ish token or a bare slug.
        # Treat anything containing a `/` as a path (external); bare
        # slugs still fail the audit so typos don't get silently hidden.
        return "/" in raw
    prefix, _ = raw.split(":", 1)
    check_set = known_prefixes if known_prefixes is not None else _EXTERNAL_PREFIXES
    return prefix.lower() in check_set


def is_metadata_reference(raw: str) -> bool:
    """Return True for `meta:*` refs.

    Meta refs are intentional annotations preserved in source files but
    excluded from KG materialization (no entity required, no edge created).
    """
    return raw.startswith("meta:")


def _enrich_raw(
    raw: dict[str, Any],
    *,
    kind: str,
    project_slug: str,
    local_profile: str,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> None:
    """Centralized normalization layer between adapter output and Entity validation.

    Mutates `raw` in place. Fills Entity defaults + legacy normalization:
    - `project`, `ontology_terms`, `related`, `source_refs`, `content_preview`
    - Paper-ID canonicalization (when kind == "paper" and on refs)
    - Profile defaulting (core/ontology/local)
    - Alias derivation for hypothesis/question/task
    - Normalize `kind` and optional core-only `type` projection
    - Description → content_preview fallback (legacy aggregate rows)
    - Drop invalid enum values for reasoning fields (soft warn via stderr)
    """
    raw.setdefault("project", project_slug)
    raw.setdefault("ontology_terms", [])
    raw.setdefault("related", [])
    raw.setdefault("source_refs", [])
    raw.setdefault("same_as", [])
    raw.setdefault("aliases", [])
    raw.setdefault("xrefs", [])
    raw.setdefault("scope", "project")
    raw.setdefault("provisional", False)
    raw.setdefault("deprecated_ids", [])
    raw.setdefault("file_path", "")
    raw.setdefault("content", "")
    raw["kind"] = _normalize_kind(kind)
    kind = raw["kind"]
    # content_preview fallback: prefer explicit, then description, then first 200 chars of content.
    if not raw.get("content_preview"):
        desc = raw.get("description")
        if isinstance(desc, str) and desc:
            raw["content_preview"] = desc
        else:
            content = raw.get("content") or ""
            raw["content_preview"] = content[:200] if isinstance(content, str) else ""

    raw["type"] = _project_type_value(kind, raw.get("type"))

    # Paper canonicalization on the entity's own id + reference lists.
    # Apply unconditionally: canonical_paper_id is a no-op for non-article/paper
    # prefixes, and the migration-window spec treats `article:<X>` as a legacy
    # alias of `paper:<X>` regardless of the source file's declared `kind`.
    # The previous `kind == "paper"` gate meant legacy files with `type: article`
    # were loaded as `article:<X>` while mentions in other files were canonicalized
    # to `paper:<X>`, producing spurious "unresolved reference" audit rows.
    canonical_id = raw.get("canonical_id") or raw.get("id")
    if isinstance(canonical_id, str) and canonical_id:
        canonical_id = canonical_paper_id(canonical_id)
        raw["canonical_id"] = canonical_id
        raw.setdefault("id", canonical_id)
    for ref_field in ("related", "source_refs", "same_as", "blocked_by"):
        vals = raw.get(ref_field)
        if isinstance(vals, list):
            raw[ref_field] = [canonical_paper_id(str(v)) for v in vals]

    # Profile defaulting.
    profile = raw.get("profile")
    if not isinstance(profile, str) or not profile:
        raw["profile"] = _default_profile_for_kind(
            kind,
            local_profile=local_profile,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )

    # Alias derivation (mix in file-stem-based tokens for hypothesis/question/task
    # files named `<token>-<rest>.md`; mirrors the legacy MarkdownProvider behavior).
    if isinstance(canonical_id, str):
        explicit = raw.get("aliases") or []
        if not isinstance(explicit, list):
            explicit = []
        explicit_list = [str(a) for a in explicit]
        fp = raw.get("file_path")
        path_aliases: list[str] = []
        if isinstance(fp, str) and fp and kind in {"hypothesis", "question", "task"}:
            stem = Path(fp).stem
            m = _SHORT_ID_RE.match(stem)
            if m is None:
                head = stem.split("-", 1)[0]
                m = _SHORT_ID_RE.match(head)
            if m is not None:
                token = m.group("token")
                path_aliases = [
                    f"{kind}:{token.lower()}",
                    f"{kind}:{token.upper()}",
                    token.lower(),
                    token.upper(),
                ]
        raw["aliases"] = _derive_aliases(canonical_id, kind, [*explicit_list, *path_aliases])

    # Drop invalid enum values silently (matches legacy load_reasoning_metadata behavior).
    for field, enum_type in _ENUM_FIELDS.items():
        value = raw.get(field)
        if isinstance(value, str):
            try:
                enum_type(value)
            except ValueError:
                raw.pop(field, None)


def _load_legacy_records(
    project_root: Path,
    *,
    registry: EntityRegistry,
    local_profile: str,
    project_slug: str,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> list[tuple[Entity, SourceRef]]:
    """Load model + parameter records from knowledge/sources/<local>/{models,parameters}.yaml."""
    out: list[tuple[Entity, SourceRef]] = []

    model_records = _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name="models.yaml",
        root_key="models",
        model=ModelSource,
    )
    for record in model_records:
        raw: dict[str, Any] = {
            "id": record.canonical_id,
            "canonical_id": record.canonical_id,
            "kind": "model",
            "type": "model",
            "title": record.title,
            "profile": record.profile,
            "file_path": record.source_path,
            "domain": record.domain,
            "related": list(record.related),
            "source_refs": list(record.source_refs),
            "aliases": list(record.aliases),
        }
        _enrich_raw(
            raw,
            kind="model",
            project_slug=project_slug,
            local_profile=local_profile,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )
        schema = registry.resolve("model")
        entity = schema.model_validate(raw)
        out.append((entity, SourceRef(adapter_name="legacy-model", path=record.source_path)))

    parameter_records = _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name="parameters.yaml",
        root_key="parameters",
        model=ParameterSource,
    )
    for record in parameter_records:
        raw = {
            "id": record.canonical_id,
            "canonical_id": record.canonical_id,
            "kind": "canonical_parameter",
            "type": "canonical_parameter",
            "title": record.title,
            "profile": record.profile,
            "file_path": record.source_path,
            "domain": record.domain,
            "content_preview": _parameter_preview(record),
            "related": list(record.related),
            "source_refs": list(record.source_refs),
            "ontology_terms": list(record.ontology_terms),
            "aliases": list(record.aliases),
        }
        # canonical_parameter is not a registered kind; register on-the-fly.
        # The spec routes unknown project kinds through ProjectEntity, but the
        # registry requires explicit registration.
        try:
            schema: type[Entity] = registry.resolve("canonical_parameter")
        except Exception:  # noqa: BLE001
            registry.register_extension_kind("canonical_parameter", ProjectEntity)
            schema = registry.resolve("canonical_parameter")

        _enrich_raw(
            raw,
            kind="canonical_parameter",
            project_slug=project_slug,
            local_profile=local_profile,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )
        entity = schema.model_validate(raw)
        out.append((entity, SourceRef(adapter_name="legacy-parameter", path=record.source_path)))

    return out


def _legacy_nested_relations(
    project_root: Path,
    *,
    local_profile: str,
    file_name: str,
    root_key: str,
    model: type[_SourceRecordT],
) -> list[SourceRelation]:
    records = _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name=file_name,
        root_key=root_key,
        model=model,
    )
    out: list[SourceRelation] = []
    for record in records:
        cid = getattr(record, "canonical_id", None)
        rels = getattr(record, "relations", None)
        src_path = getattr(record, "source_path", None)
        if not cid or not isinstance(rels, list) or not src_path:
            continue
        out.extend(_nested_relations(cid, rels, source_path=src_path))
    return out


def _load_binding_sources(project_root: Path, *, local_profile: str) -> list[BindingSource]:
    return _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name="bindings.yaml",
        root_key="bindings",
        model=BindingSource,
    )


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

    # Legacy science.yaml uses `profiles: {local: local}` instead of `knowledge_profiles`.
    # Prefer knowledge_profiles; fall back to profiles if present.
    if not knowledge_profiles:
        fallback = data.get("profiles") or {}
        if isinstance(fallback, dict):
            knowledge_profiles = fallback

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


def _normalize_kind(kind: str) -> str:
    cleaned = kind.strip()
    if cleaned in {"parameter", "canonical-parameter"}:
        return EntityType.CANONICAL_PARAMETER.value
    if cleaned == "parameter-binding":
        return "parameter_binding"
    return cleaned


def _project_type_value(kind: str, raw_type: object) -> str | None:
    normalized_kind = _normalize_kind(kind)
    if isinstance(raw_type, EntityType):
        return raw_type.value
    if isinstance(raw_type, str):
        normalized_type = _normalize_kind(raw_type)
        if normalized_type == EntityType.UNKNOWN.value:
            return EntityType.UNKNOWN.value
    projected = core_entity_type_for_kind(normalized_kind)
    return projected.value if projected is not None else None


def _derive_aliases(canonical_id: str, kind: str, explicit_aliases: list[str]) -> list[str]:
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

    if kind not in {"hypothesis", "question", "task"}:
        return aliases

    if ":" in canonical_id:
        slug = canonical_id.split(":", 1)[1]
    else:
        slug = canonical_id
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


def _format_missing_fields(exc: ValidationError) -> str:
    """Compact summary of pydantic validation errors for logging."""
    parts: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()))
        msg = err.get("msg", "invalid")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts) if parts else str(exc)

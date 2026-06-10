"""Structured upstream sources for deterministic graph materialization."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

import yaml
from pydantic import BaseModel, Field, ValidationError
from science_model.entities import (
    Entity,
    EntityClass,
    EntityType,
    ProjectEntity,
    DomainEntity,
    core_entity_type_for_kind,
)
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
from science_model.source_contracts import (
    AuthoredTargetedRelation,
    BindingSource,
    ModelSource,
    ParameterSource,
    StructuredEntitySource,
)
from science_model.source_ref import SourceRef

from science_tool.big_picture.literature_prefix import canonical_paper_id
from science_tool.bibliography import is_bibliography_reference as _is_bibliography_reference
from science_tool.commons.aliases import load_manual_aliases
from science_tool.graph.entity_registry import EntityKindNotRegisteredError, EntityRegistry
from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.identity_table import (
    IdentityDeclaration,
    ParticipationMode,
    classify_owner_scope,
)
from science_tool.graph.storage_adapters.aggregate import AggregateAdapter
from science_tool.graph.storage_adapters.base import StorageAdapter
from science_tool.graph.storage_adapters.bib import BibAdapter
from science_tool.graph.storage_adapters.curie_ref import CurieRefAdapter
from science_tool.graph.storage_adapters.code import CodeAdapter
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter
from science_tool.graph.storage_adapters.task import TaskAdapter
from science_tool.graph.storage_adapters.workflow_run import WorkflowRunAdapter
from science_tool.paths import resolve_paths

logger = logging.getLogger(__name__)

_SHORT_ID_RE = re.compile(r"^(?P<token>[a-z]\d+)(?:[-_].*)?$", re.IGNORECASE)
_EXTERNAL_PREFIXES = frozenset({"go", "mesh", "doid", "hp", "so", "ncbitaxon", "ncbigene", "ensembl"})
_CORE_KINDS = frozenset(kind.name for kind in CORE_PROFILE.entity_kinds)
_SourceRecordT = TypeVar("_SourceRecordT", bound=BaseModel)
_TypedRecordCache = dict[tuple[str, str, str, str, type[BaseModel]], object]

_ENUM_FIELDS: dict[str, type] = {
    "claim_layer": ClaimLayer,
    "identification_strength": IdentificationStrength,
    "proxy_directness": ProxyDirectness,
    "supports_scope": SupportScope,
    "evidence_role": EvidenceRole,
}

_SAFE_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


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


class MarkdownSourceDocument(BaseModel):
    path: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body: str = ""


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


class SkippedEntity(BaseModel):
    """An entity dropped during load.

    Surfaced by ``audit_project_sources`` as a warn row so that an entity being
    silently excluded from the graph (unknown kind, failed schema validation) is
    visible to ``science graph audit`` / validate rather than only logged.
    """

    path: str
    kind: str
    reason: str  # "unknown_entity_kind" | "entity_schema_validation_failed" | "core_schema_validation_failed"
    details: str


@dataclass(frozen=True, slots=True)
class AggregateRowMeta:
    """Row-level triage metadata for one aggregate (`entities.yaml`) entry.

    Captured at load time — before non-strict dedup can drop a shadowed entry's
    Entity (sources.py emit point) — so the §B5 triage classifier can bucket every
    aggregate row. Joined to its IdentityDeclaration by (path, line), which
    AggregateAdapter always populates.
    """

    path: str
    line: int
    canonical_id: str
    kind: str
    source_path: str | None
    # 4c: the row's external authority identifier, captured from the VALIDATED
    # entity. `entity.primary_external_id` is a typed ExternalId (or None); a
    # malformed value never reaches capture (it fails ExternalId validation and the
    # row is skipped). So this is the full {source, id, curie, provenance} dump or
    # None — never a half-filled mapping that could masquerade as a backed ref.
    primary_external_id: dict[str, str] | None = None


class ProjectSources(BaseModel):
    """Structured source bundle used to materialize a project graph."""

    model_config = {"arbitrary_types_allowed": True}

    project_name: str
    project_root: str
    profiles: KnowledgeProfiles
    entities: list[Entity]
    entity_source_adapters: dict[str, str] = Field(default_factory=dict)
    # §B4: id -> rel path of a datapackage.yaml that DEFERRED to an existing owner.
    # The owner won the owner column, but member-resource resolution still needs the
    # datapackage path (the geneset member CSV lives there, not in the owner file).
    dataset_datapackages: dict[str, str] = Field(default_factory=dict)
    relations: list[SourceRelation] = Field(default_factory=list)
    bindings: list[BindingSource] = Field(default_factory=list)
    manual_aliases: dict[str, str] = Field(default_factory=dict)
    ontology_catalogs: list[OntologyCatalog] = Field(default_factory=list)
    registry: EntityRegistry
    markdown_documents: list[MarkdownSourceDocument] = Field(default_factory=list)
    skipped_entities: list[SkippedEntity] = Field(default_factory=list)
    commons_overlay_paths: dict[str, str] = Field(default_factory=dict)
    identity_declarations: list[IdentityDeclaration] = Field(default_factory=list)
    # §B5: row-level metadata for every aggregate (entities.yaml) owner row, captured
    # before non-strict dedup so shadowed rows (whose Entity is dropped) stay triable.
    aggregate_rows: list[AggregateRowMeta] = Field(default_factory=list)
    freshness_enabled: bool = True


SourceBinding = BindingSource


def _resolve_entity_class(declared: str | None, default: EntityClass) -> EntityClass:
    """Parse entity_class from a manifest string, or return the default."""
    if declared is None:
        return default
    try:
        return EntityClass(declared)
    except ValueError:
        raise ValueError(
            f"Invalid entity_class {declared!r} in profile manifest; expected one of {[c.value for c in EntityClass]}"
        )


def load_project_sources(
    project_root: Path,
    markdown_overrides: dict[str, str] | None = None,
    *,
    include_commons: bool = True,
    strict_core_schema: bool = True,
    strict_identity: bool = True,
) -> ProjectSources:
    """Load all project entities through the unified registry + adapters flow.

    When ``strict_core_schema`` is True (the default, used by ``validate`` and
    graph build), a core-kind entity that fails schema validation raises a
    ``ValueError`` — those callers must fail hard on a malformed core entity.
    When False (used by the ``health`` diagnostic sweep), the failure is recorded
    as a ``SkippedEntity`` (reason ``entity_schema_validation_failed``) and the
    rest of the project still loads, so one bad entity cannot take the whole
    report offline (fb-2026-05-30-008).
    """
    project_root = project_root.resolve()
    config = _read_project_config(project_root)
    profiles = KnowledgeProfiles.model_validate(config["knowledge_profiles"])
    local_profile = profiles.local
    freshness_block = config.get("freshness") or {}
    if not isinstance(freshness_block, dict):
        freshness_block = {}
    freshness_enabled = bool(freshness_block.get("enabled", True))

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
            registry.register_profile_kind(
                entity_kind.name,
                ProjectEntity,
                owner=profile.name,
                entity_class=_resolve_entity_class(entity_kind.entity_class, EntityClass.OPERATIONAL),
            )
    for catalog in ontology_catalogs:
        for entity_type in catalog.entity_types:
            registry.register_catalog_kind(entity_type.name, DomainEntity, owner=catalog.ontology)
    if local_profile_manifest is not None:
        for entity_kind in local_profile_manifest.entity_kinds:
            registry.register_extension_kind(
                entity_kind.name,
                ProjectEntity,
                entity_class=_resolve_entity_class(entity_kind.entity_class, EntityClass.OPERATIONAL),
            )

    project_paths = resolve_paths(project_root)
    adapters: list[StorageAdapter] = [
        # The 21 entity-layout kinds live under entities/ (Plan 3 cutover). The
        # datapackage/workflow family (dataset, workflow, workflow-run) is NOT one
        # of those layout kinds and was not migrated, so we keep discovering it at
        # its existing doc/ roots (also hard-coded in validate/_helpers.py,
        # dataset_promotion_contract.py, commons/promote.py). The markdown.py
        # default stays entities/-only; these doc/ roots are listed explicitly.
        # NOTE: doc/ is a TRANSITIONAL home for this family, not a principled one —
        # whether dataset/workflow/workflow-run should become first-class entities/
        # kinds (and gain dataset<->claim epistemic edges) is deferred to a dedicated
        # follow-up. See docs/plans/2026-04-19-dataset-entity-lifecycle-design.md.
        MarkdownAdapter(
            scan_roots=["entities", "research/packages", "doc/datasets", "doc/workflows", "doc/workflow-runs"],
            virtual_files=markdown_overrides,
        ),
        AggregateAdapter(local_profile=local_profile, virtual_files=markdown_overrides),
        # NOTE: AggregateAdapter must precede the external-reference adapters
        # (BibAdapter, CurieRefAdapter) — their defer guard relies on aggregate
        # stubs (and markdown owners) being declared first this load.
        BibAdapter(),
        CurieRefAdapter(local_profile=local_profile),
        DatapackageAdapter(),
        WorkflowRunAdapter(),
        TaskAdapter(),
        CodeAdapter(
            code_roots=project_paths.code_roots,
            repo_root=project_root,
            excludes=project_paths.code_excludes,
        ),
    ]

    project_slug = project_root.name
    project_name = str(config["name"])
    identity_table: dict[str, SourceRef] = {}
    identity_declarations: list[IdentityDeclaration] = []
    aggregate_rows: list[AggregateRowMeta] = []
    entities: list[Entity] = []
    entity_source_adapters: dict[str, str] = {}
    dataset_datapackages: dict[str, str] = {}
    markdown_documents: list[MarkdownSourceDocument] = []
    skipped_entities: list[SkippedEntity] = []

    # cwd for relative-path resolution in adapters. The StorageAdapter.load_raw()
    # contract resolves ref.path against cwd; we chdir into project_root rather
    # than broaden the Protocol. Restored in the finally block.
    prev_cwd = os.getcwd()
    os.chdir(project_root)
    try:
        for adapter in adapters:
            for ref in adapter.discover(project_root):
                raw = adapter.load_raw(ref)
                if isinstance(adapter, MarkdownAdapter):
                    markdown_documents.append(
                        MarkdownSourceDocument(
                            path=ref.path,
                            frontmatter={key: value for key, value in raw.items() if key != "content"},
                            body=str(raw.get("content") or ""),
                        )
                    )
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
                    skipped_entities.append(
                        SkippedEntity(
                            path=str(ref.path),
                            kind=kind,
                            reason="unknown_entity_kind",
                            details="not registered in core or active profiles",
                        )
                    )
                    continue
                try:
                    entity = schema.model_validate(raw)
                except ValidationError as exc:
                    details = _format_missing_fields(exc)
                    if registry.is_core_kind(kind):
                        if isinstance(adapter, MarkdownAdapter) and _is_missing_identity_validation(exc):
                            logger.warning(
                                "skipping %s: core entity is missing identity fields (%s)",
                                ref.path,
                                details,
                            )
                            skipped_entities.append(
                                SkippedEntity(
                                    path=str(ref.path),
                                    kind=kind,
                                    reason="entity_schema_validation_failed",
                                    details=f"missing identity fields ({details})",
                                )
                            )
                            continue
                        if strict_core_schema:
                            raise ValueError(
                                f"schema validation failed for registered entity kind {kind!r} at {ref.path}: {details}"
                            ) from exc
                        logger.warning(
                            "skipping %s: schema validation failed for registered core kind %r (%s)",
                            ref.path,
                            kind,
                            details,
                        )
                        # Distinct reason from the missing-identity branch above
                        # (which the entity_identity health check already reports
                        # as missing-canonical-id): health surfaces ONLY these as
                        # schema_invalid findings, avoiding double-counting
                        # (fb-2026-05-30-008).
                        skipped_entities.append(
                            SkippedEntity(
                                path=str(ref.path),
                                kind=kind,
                                reason="core_schema_validation_failed",
                                details=details,
                            )
                        )
                        continue
                    logger.warning(
                        "skipping %s: schema validation failed for registered profile kind %r (%s)",
                        ref.path,
                        kind,
                        details,
                    )
                    skipped_entities.append(
                        SkippedEntity(
                            path=str(ref.path),
                            kind=kind,
                            reason="entity_schema_validation_failed",
                            details=details,
                        )
                    )
                    continue
                owner_scope, deprecated = classify_owner_scope(adapter.name, project_name=project_name)
                if isinstance(adapter, DatapackageAdapter) and entity.canonical_id in identity_table:
                    # §B4: a datapackage is attached resource metadata, not a second
                    # owner. Its id already has an owner recorded this load (a real
                    # markdown owner OR a transitional entities.yaml aggregate stub —
                    # both adapters precede DatapackageAdapter), so it DEFERS: emit no
                    # competing owner declaration and no duplicate entity (it never
                    # collides, under strict or non-strict). A datapackage shadowed by
                    # an aggregate stub rides that stub; §B5 retirement carries the
                    # debt. Only a TRUE orphan (id not yet owned) synthesizes the
                    # deprecated transitional owner below.
                    # Record its path so the geneset member gate can still locate the
                    # datapackage's resources after the owner (markdown) wins the column.
                    dataset_datapackages[entity.canonical_id] = ref.path
                    continue
                if (
                    adapter.participation_mode == ParticipationMode.EXTERNAL_REFERENCE
                    and entity.canonical_id in identity_table
                ):
                    # §B3/§C3 external-reference defer (generalized over bib + curie):
                    # an external-reference adapter contributes references, not
                    # owners. If a real owner OR a transitional aggregate stub already
                    # claimed this id this load (all owner-ish adapters precede the
                    # external-reference adapters), it defers — no second declaration,
                    # no duplicate entity, no collision under strict load. The
                    # owner->external-reference flip happens automatically on the next
                    # load once retirement drops the stub. The branch is deliberately
                    # adapter-agnostic; source-specific parsing stays in the adapter.
                    continue
                identity_declarations.append(
                    IdentityDeclaration(
                        canonical_id=entity.canonical_id,
                        participation_mode=adapter.participation_mode,
                        owner_scope=owner_scope,
                        adapter=adapter.name,
                        source_ref=ref,
                        deprecated=deprecated,
                    )
                )
                if adapter.name == "aggregate":
                    assert ref.line is not None  # AggregateAdapter always sets the entry index
                    sp_raw = raw.get("source_path")
                    # Capture from the VALIDATED entity, not raw: entity.primary_external_id
                    # is a typed ExternalId (already passed ExternalId validation) or None.
                    # exclude_none drops the optional `version`, leaving the four required keys.
                    pei = entity.primary_external_id
                    aggregate_rows.append(
                        AggregateRowMeta(
                            path=ref.path,
                            line=ref.line,
                            canonical_id=entity.canonical_id,
                            kind=kind,
                            # source_path is unschema'd extra metadata; normalize a
                            # malformed (non-string) value to None so the report can't crash.
                            source_path=sp_raw if isinstance(sp_raw, str) else None,
                            primary_external_id=pei.model_dump(exclude_none=True) if pei is not None else None,
                        )
                    )
                existing = identity_table.get(entity.canonical_id)
                if existing is not None:
                    if strict_identity:
                        raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
                    continue
                identity_table[entity.canonical_id] = ref
                entities.append(entity)
                entity_source_adapters[entity.canonical_id] = adapter.name
    finally:
        os.chdir(prev_cwd)

    # Legacy model/parameter loaders from knowledge/sources/<local>/{models,parameters}.yaml.
    # Produce ProjectEntity records through the registry so they join the same pipeline.
    typed_record_cache: _TypedRecordCache = {}
    for entity, ref in [
        *_load_legacy_records(
            project_root,
            registry=registry,
            local_profile=local_profile,
            project_slug=project_slug,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
            typed_record_cache=typed_record_cache,
        ),
        *_load_structured_source_records(
            project_root,
            registry=registry,
            local_profile=local_profile,
            local_profile_manifest=local_profile_manifest,
            project_slug=project_slug,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
            typed_record_cache=typed_record_cache,
        ),
    ]:
        owner_scope, deprecated = classify_owner_scope(ref.adapter_name, project_name=project_name)
        identity_declarations.append(
            IdentityDeclaration(
                canonical_id=entity.canonical_id,
                participation_mode=ParticipationMode.OWNER,
                owner_scope=owner_scope,
                adapter=ref.adapter_name,
                source_ref=ref,
                deprecated=deprecated,
            )
        )
        existing = identity_table.get(entity.canonical_id)
        if existing is not None:
            if strict_identity:
                raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
            continue
        identity_table[entity.canonical_id] = ref
        entities.append(entity)
        entity_source_adapters[entity.canonical_id] = ref.adapter_name

    entities.sort(key=lambda e: e.canonical_id)

    relations = _load_structured_relations(project_root, local_profile=local_profile)
    relations.extend(_entity_nested_relations(entities))
    # Legacy model/parameter relations come from the nested authored-relations block.
    relations.extend(
        _legacy_nested_relations(
            project_root,
            local_profile=local_profile,
            file_name="models.yaml",
            root_key="models",
            model=ModelSource,
            typed_record_cache=typed_record_cache,
        )
    )
    relations.extend(
        _legacy_nested_relations(
            project_root,
            local_profile=local_profile,
            file_name="parameters.yaml",
            root_key="parameters",
            model=ParameterSource,
            typed_record_cache=typed_record_cache,
        )
    )
    relations.sort(key=lambda relation: (relation.graph_layer, relation.subject, relation.predicate, relation.object))
    bindings = _load_binding_sources(project_root, local_profile=local_profile, typed_record_cache=typed_record_cache)
    bindings.sort(key=lambda binding: (binding.model, binding.parameter, binding.source_path))

    commons_overlay_paths: dict[str, str] = {}
    if include_commons:
        from science_tool.graph.commons_sources import _load_commons_referenced_entities

        commons_loaded, commons_overlay_paths, commons_owner_collisions = _load_commons_referenced_entities(
            project_root=project_root,
            project_slug=project_slug,
            project_entities=entities,
            project_relations=relations,
            project_bindings=bindings,
            identity_table=identity_table,
            registry=registry,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )
        for collision_id, collision_ref in commons_owner_collisions:
            owner_scope, deprecated = classify_owner_scope(collision_ref.adapter_name, project_name=project_name)
            identity_declarations.append(
                IdentityDeclaration(
                    canonical_id=collision_id,
                    participation_mode=ParticipationMode.OWNER,
                    owner_scope=owner_scope,
                    adapter=collision_ref.adapter_name,
                    source_ref=collision_ref,
                    deprecated=deprecated,
                )
            )
            # Deliberately do NOT add to `entities` / `identity_table`: the local owner
            # remains the single materialized entity; the second owner row exists only
            # so reference resolution (once scope-aware) flags the bare ref as
            # ambiguous (design §B3a). No strict raise — cross-scope is not a collision.
        for entity, ref in commons_loaded:
            owner_scope, deprecated = classify_owner_scope(ref.adapter_name, project_name=project_name)
            identity_declarations.append(
                IdentityDeclaration(
                    canonical_id=entity.canonical_id,
                    participation_mode=ParticipationMode.OWNER,
                    owner_scope=owner_scope,
                    adapter=ref.adapter_name,
                    source_ref=ref,
                    deprecated=deprecated,
                )
            )
            overlay_path = commons_overlay_paths.get(entity.canonical_id)
            if overlay_path:
                identity_declarations.append(
                    IdentityDeclaration(
                        canonical_id=entity.canonical_id,
                        participation_mode=ParticipationMode.BORROWER,
                        owner_scope=owner_scope,
                        adapter="overlay",
                        source_ref=SourceRef(adapter_name="overlay", path=overlay_path),
                        deprecated=False,
                    )
                )
            existing = identity_table.get(entity.canonical_id)
            if existing is not None:
                if strict_identity:
                    raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
                continue
            identity_table[entity.canonical_id] = ref
            entities.append(entity)
            entity_source_adapters[entity.canonical_id] = ref.adapter_name

        entities.sort(key=lambda e: e.canonical_id)

    return ProjectSources(
        project_name=str(config["name"]),
        project_root=str(project_root),
        profiles=profiles,
        entities=entities,
        entity_source_adapters=entity_source_adapters,
        dataset_datapackages=dataset_datapackages,
        relations=relations,
        bindings=bindings,
        manual_aliases=_load_manual_aliases(project_root, local_profile=local_profile),
        ontology_catalogs=ontology_catalogs,
        registry=registry,
        markdown_documents=markdown_documents,
        skipped_entities=skipped_entities,
        commons_overlay_paths=commons_overlay_paths,
        identity_declarations=identity_declarations,
        aggregate_rows=aggregate_rows,
        freshness_enabled=freshness_enabled,
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


# Annotation-only reference namespaces: pointers an author keeps in source files
# (e.g. `meta:<phase>` process tags, `spec:<design-doc>` pointers to design
# documents that are not first-class entities) that are intentionally NOT
# materialized as KG edges and require no resolvable entity.
_ANNOTATION_REF_PREFIXES = frozenset({"meta", "spec"})


def is_metadata_reference(raw: str) -> bool:
    """Return True for annotation-only refs (`meta:*`, `spec:*`).

    These are intentional annotations preserved in source files but excluded
    from KG materialization (no entity required, no edge created). `spec:` joins
    `meta:` because design-spec pointers reference plain design documents, not
    first-class entities.
    """
    return any(raw.startswith(f"{prefix}:") for prefix in _ANNOTATION_REF_PREFIXES)


def is_bibliography_reference(raw: str) -> bool:
    """Return True for project bibliography refs such as `cite:<bibkey>`."""
    return _is_bibliography_reference(raw)


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
    - Validate reasoning enum fields and fail early on legacy/invalid shapes
    """
    raw.setdefault("project", project_slug)
    raw.setdefault("ontology_terms", [])
    raw.setdefault("related", [])
    raw.setdefault("relations", [])
    raw.setdefault("source_refs", [])
    raw.setdefault("evidence_refs", [])
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
    for ref_field in ("related", "commits_to", "source_refs", "evidence_refs", "same_as", "blocked_by"):
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

    # Reasoning metadata is current-state metadata. Do not silently erase invalid
    # legacy shapes: fail early so migrations have a visible target.
    for field, enum_type in _ENUM_FIELDS.items():
        value = raw.get(field)
        if isinstance(value, str):
            try:
                enum_type(value)
            except ValueError as exc:
                allowed = ", ".join(sorted(str(member.value) for member in enum_type))
                source = raw.get("file_path") or raw.get("canonical_id") or raw.get("id") or "<unknown source>"
                raise ValueError(
                    f"invalid reasoning metadata {field}={value!r} at {source}; expected one of: {allowed}"
                ) from exc


def _load_legacy_records(
    project_root: Path,
    *,
    registry: EntityRegistry,
    local_profile: str,
    project_slug: str,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
    typed_record_cache: _TypedRecordCache | None = None,
) -> list[tuple[Entity, SourceRef]]:
    """Load model + parameter records from knowledge/sources/<local>/{models,parameters}.yaml."""
    out: list[tuple[Entity, SourceRef]] = []

    model_records = _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name="models.yaml",
        root_key="models",
        model=ModelSource,
        cache=typed_record_cache,
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
        cache=typed_record_cache,
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
        # canonical_parameter is registered as a profile kind by LOCAL_PROFILE,
        # which is always included in profile_manifests above.
        schema: type[Entity] = registry.resolve("canonical_parameter")

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


def _load_structured_source_records(
    project_root: Path,
    *,
    registry: EntityRegistry,
    local_profile: str,
    local_profile_manifest: ProfileManifest | None,
    project_slug: str,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
    typed_record_cache: _TypedRecordCache | None = None,
) -> list[tuple[Entity, SourceRef]]:
    """Load owner entities from profile-declared structured-source data files.

    Generalizes the hardcoded model/parameter loaders (_load_legacy_records) to any
    kind whose rows live in a single-type YAML data file under
    knowledge/sources/<profile>/. Two declaration sites feed this: project-LOCAL
    kinds with `structured_source` set, and CORE kinds the project augments via
    `core_structured_sources`. Each row becomes an owner entity of that kind, so
    generated kinds (e.g. local limit-relation/morphism-edge, or core `finding`
    rows from an audit) need not ride the multi-type entities.yaml/terms.yaml
    aggregate that v3 retirement forbids.
    """
    out: list[tuple[Entity, SourceRef]] = []
    if local_profile_manifest is None:
        return out
    # (kind_name, source_file, root_key) specs from two sources: project-LOCAL
    # kinds that declare their own structured_source, and CORE kinds the project
    # augments via core_structured_sources (no registration/shadowing needed --
    # the core kind is already in the registry).
    specs: list[tuple[str, str, str | None]] = [
        (kind_decl.name, kind_decl.structured_source, kind_decl.structured_source_root_key)
        for kind_decl in local_profile_manifest.entity_kinds
        if kind_decl.structured_source
    ]
    specs.extend(
        (css.kind, css.structured_source, css.structured_source_root_key)
        for css in local_profile_manifest.core_structured_sources
    )
    for kind_name, source_file, root_key_override in specs:
        root_key = root_key_override or kind_name
        default_path = f"knowledge/sources/{local_profile}/{source_file}"
        records = _load_typed_records(
            project_root,
            local_profile=local_profile,
            file_name=source_file,
            root_key=root_key,
            model=StructuredEntitySource,
            cache=typed_record_cache,
        )
        schema = registry.resolve(kind_name)
        for record in records:
            raw: dict[str, Any] = {
                "id": record.canonical_id,
                "canonical_id": record.canonical_id,
                "kind": kind_name,
                "type": kind_name,
                "title": record.title or record.canonical_id,
                "profile": record.profile or local_profile,
                "file_path": record.source_path or default_path,
                "related": list(record.related),
                "source_refs": list(record.source_refs),
                "evidence_refs": list(record.evidence_refs),
                "aliases": list(record.aliases),
                "ontology_terms": list(record.ontology_terms),
            }
            if record.domain is not None:
                raw["domain"] = record.domain
            if record.description is not None:
                raw["description"] = record.description
            if record.created is not None:
                raw["created"] = record.created
            if record.updated is not None:
                raw["updated"] = record.updated
            _enrich_raw(
                raw,
                kind=kind_name,
                project_slug=project_slug,
                local_profile=local_profile,
                active_kinds=active_kinds,
                ontology_catalogs=ontology_catalogs,
            )
            entity = schema.model_validate(raw)
            out.append(
                (entity, SourceRef(adapter_name="structured-source", path=record.source_path or default_path))
            )
    return out


def _legacy_nested_relations(
    project_root: Path,
    *,
    local_profile: str,
    file_name: str,
    root_key: str,
    model: type[_SourceRecordT],
    typed_record_cache: _TypedRecordCache | None = None,
) -> list[SourceRelation]:
    records = _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name=file_name,
        root_key=root_key,
        model=model,
        cache=typed_record_cache,
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


def _entity_nested_relations(entities: list[Entity]) -> list[SourceRelation]:
    flattened: list[SourceRelation] = []
    for entity in entities:
        if not entity.relations:
            continue
        for relation in entity.relations:
            flattened.append(
                SourceRelation(
                    subject=entity.canonical_id,
                    predicate=relation.predicate,
                    object=canonical_paper_id(relation.target),
                    graph_layer=relation.graph_layer,
                    source_path=entity.file_path,
                )
            )
    return flattened


def _load_binding_sources(
    project_root: Path,
    *,
    local_profile: str,
    typed_record_cache: _TypedRecordCache | None = None,
) -> list[BindingSource]:
    return _load_typed_records(
        project_root,
        local_profile=local_profile,
        file_name="bindings.yaml",
        root_key="bindings",
        model=BindingSource,
        cache=typed_record_cache,
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
    cache: _TypedRecordCache | None = None,
) -> list[_SourceRecordT]:
    cache_key = (str(project_root.resolve()), local_profile, file_name, root_key, model)
    if cache is not None and cache_key in cache:
        return cast("list[_SourceRecordT]", cache[cache_key])

    path = local_profile_sources_dir(project_root, local_profile=local_profile) / file_name
    if not path.is_file():
        if cache is not None:
            cache[cache_key] = []
        return []

    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_SAFE_YAML_LOADER) or {}
    items = data.get(root_key) or []
    if not isinstance(items, list):
        if cache is not None:
            cache[cache_key] = []
        return []

    records: list[_SourceRecordT] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        records.append(model.model_validate(item))
    if cache is not None:
        cache[cache_key] = records
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

    raw_freshness = data.get("freshness") or {}
    if not isinstance(raw_freshness, dict):
        raw_freshness = {}

    return {
        "name": str(data.get("name") or project_root.name),
        "knowledge_profiles": {
            "local": str(knowledge_profiles.get("local") or "local"),
        },
        "ontologies": [str(o) for o in raw_ontologies],
        "freshness": raw_freshness,
    }


def resolve_local_profile_name(project_root: Path) -> str:
    """Return the active local knowledge-profile name for the project at *project_root*.

    Prefers the value at ``knowledge_profiles.local`` in the project config;
    falls back to the legacy ``profiles.local`` key if the newer key is absent;
    defaults to ``"local"`` when neither key is present.
    """
    return str(_read_project_config(project_root)["knowledge_profiles"]["local"])


def _load_manual_aliases(project_root: Path, *, local_profile: str) -> dict[str, str]:
    return load_manual_aliases(project_root, local_profile=local_profile)


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


def _is_missing_identity_validation(exc: ValidationError) -> bool:
    errors = exc.errors()
    if not errors:
        return False
    identity_fields = {"id", "canonical_id"}
    for err in errors:
        loc = err.get("loc", ())
        field = str(loc[0]) if loc else ""
        if field not in identity_fields or err.get("type") != "missing":
            return False
    return True

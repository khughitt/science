"""Structured upstream sources for deterministic graph materialization."""

from __future__ import annotations

import inspect
import logging
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, TypeVar, cast

import yaml
from pydantic import BaseModel, Field, ValidationError
from science_model.entities import (
    DomainEntity,
    Entity,
    EntityType,
    ProjectEntity,
    core_entity_type_for_kind,
)
from science_model.identity import EntityClass
from science_model.ontologies import load_catalogs_for_names
from science_model.ontologies.schema import OntologyCatalog
from science_model.profiles import CORE_PROFILE, LOCAL_PROFILE, load_profile_manifest, load_shared_profile
from science_model.profiles.schema import ProfileManifest
from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    MembershipRole,
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
from science_model.autonomous_runs import AutonomousRunRecord

from science_model.entity_schema import PROJECT_MIXIN_NAMES
from science_model.entity_schema.merge import MergePolicy, read_merge_policy
from science_model.entity_schema.profile import ProfileParseError, default_profile_for_kind

from science_tool.bibliography import is_bibliography_reference as _is_bibliography_reference
from science_tool.commons.aliases import load_manual_aliases
from science_tool.entity_profiles import (
    ARMED_SCHEMA_GENERATIONS,
    ProjectSchema,
    load_project_schema,
)
from science_tool.project_config import (
    selected_local_profile_name,
    validated_entity_schema_version,
)
from science_tool.graph.autonomous_runs import load_run_records
from science_tool.graph.entity_registry import (
    EntityKindNotRegisteredError,
    EntityProjectionError,
    EntityRegistry,
)
from science_tool.graph.errors import ContributionConflictError, EntityIdentityCollisionError
from science_tool.graph.identity_arbitration import (
    ArbitrationCode,
    ArbitrationContext,
    ArbitrationError,
    EntityContribution,
    SourceContribution,
    arbitrate_contributions,
)
from science_tool.graph.identity_table import (
    IdentityDeclaration,
    ParticipationMode,
    classify_owner_scope,
)
from science_tool.graph.source_records import MarkdownSourceDocument
from science_tool.graph.source_normalization import normalize_structured_row
from science_tool.graph.skill_loads import SkillLoadRecord, collect_skill_loads, load_skill_aliases
from science_tool.graph.storage_adapters.base import StorageAdapter
from science_tool.graph.storage_adapters.bib import BibAdapter
from science_tool.graph.storage_adapters.code import CodeAdapter
from science_tool.graph.storage_adapters.curie_ref import CurieRefAdapter
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter
from science_tool.graph.storage_adapters.task import TaskAdapter
from science_tool.data_root import project_config_path
from science_tool.graph.storage_adapters.workflow_run import WorkflowRunAdapter
from science_tool.paths import resolve_paths

logger = logging.getLogger(__name__)

_SHORT_ID_RE = re.compile(r"^(?P<token>[a-z]\d+)(?:[-_].*)?$", re.IGNORECASE)
_NUMERIC_ID_PREFIX_RE = re.compile(r"^(?P<number>\d{1,4})(?:[-_].*)?$")
_KIND_SHORT_PREFIX: dict[str, str] = {
    "hypothesis": "h",
    "question": "q",
    "task": "t",
}
_EXTERNAL_PREFIXES = frozenset({"go", "mesh", "doid", "hp", "so", "ncbitaxon", "ncbigene", "ensembl"})
_CORE_KINDS = frozenset(kind.name for kind in CORE_PROFILE.entity_kinds)
_SourceRecordT = TypeVar("_SourceRecordT", bound=BaseModel)
_TypedRecordCache = dict[tuple[str, str, str, str, type[BaseModel]], object]

_ENUM_FIELDS: dict[str, type[StrEnum]] = {
    "claim_layer": ClaimLayer,
    "identification_strength": IdentificationStrength,
    "proxy_directness": ProxyDirectness,
    "supports_scope": SupportScope,
    "evidence_role": EvidenceRole,
}

_SAFE_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_PROJECT_CONFIG_CACHE: dict[tuple[str, int], dict[str, object]] = {}

# Keys these loaders ASSEMBLE rather than read from the author. Only the ones the composed schema
# refuses need listing -- `profile`, `aliases`, `ontology_terms`, `related` and `source_refs` are
# admitted (measured), so hiding them would only widen the blind spot. `id`, `kind` and `title`
# are NOT here on purpose: they are policy values for real schema fields, and the schema requires
# all three, so hiding them would refuse every record for a missing key the loader had supplied.
_STRUCTURED_INJECTED_KEYS: frozenset[str] = frozenset(
    {"canonical_id", "type", "file_path", "evidence_refs"}
)
_LEGACY_INJECTED_KEYS: frozenset[str] = _STRUCTURED_INJECTED_KEYS


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
    role: MembershipRole | None = None


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


class CanonicalMarkdownRejection(StrEnum):
    """Why a discovered Markdown record is not a canonical entity."""

    MISSING_KIND = "missing_kind"
    UNKNOWN_KIND = "unknown_kind"
    PROJECT_SCHEMA = "project_schema_validation_failed"
    ENTITY_SCHEMA = "entity_schema_validation_failed"


@dataclass(frozen=True)
class CanonicalMarkdownContext:
    """Filesystem-free inputs needed to judge one Markdown entity record."""

    project_slug: str
    local_profile: str
    active_kinds: frozenset[str]
    ontology_catalogs: list[OntologyCatalog]
    registry: EntityRegistry
    project_schema: ProjectSchema | None


@dataclass(frozen=True)
class CanonicalMarkdownValidation:
    """Accepted entity or an explicit canonical-rejection reason."""

    kind: str | None = None
    schema: type[Entity] | None = None
    entity: Entity | None = None
    authored_aliases: frozenset[str] = frozenset()
    rejection: CanonicalMarkdownRejection | None = None
    error: ValidationError | ValueError | None = None


@dataclass(frozen=True)
class ActiveProfiles:
    """Resolved project profiles and ontology catalogs used to build a registry."""

    profile_manifests: list[ProfileManifest]
    local_profile_manifest: ProfileManifest | None
    ontology_catalogs: list[OntologyCatalog]
    local_profile: str
    local_manifest_rel: str


class ProjectSources(BaseModel):
    """Structured source bundle used to materialize a project graph."""

    model_config = {"arbitrary_types_allowed": True}

    project_name: str
    project_root: str
    profiles: KnowledgeProfiles
    entities: list[Entity]
    entity_source_adapters: dict[str, str] = Field(default_factory=dict)
    # §B4: id -> rel path of a datapackage.yaml that ATTACHES to an id something else
    # represents. The representative won the owner column, but member-resource resolution still
    # needs the datapackage path (the geneset member CSV lives there, not in the owner file).
    dataset_datapackages: dict[str, str] = Field(default_factory=dict)
    relations: list[SourceRelation] = Field(default_factory=list)
    bindings: list[BindingSource] = Field(default_factory=list)
    manual_aliases: dict[str, str] = Field(default_factory=dict)
    # Subset of `manual_aliases` keys that came from the ARCHIVE index (not project-
    # authored `mappings.yaml`). build_alias_map needs this to keep an archived id from
    # silently shadowing a live entity's auto-derived token: an authored mapping may win
    # over a colliding derived alias, an archive token never does.
    archive_alias_tokens: frozenset[str] = Field(default_factory=frozenset)
    ontology_catalogs: list[OntologyCatalog] = Field(default_factory=list)
    registry: EntityRegistry
    markdown_documents: list[MarkdownSourceDocument] = Field(default_factory=list)
    skipped_entities: list[SkippedEntity] = Field(default_factory=list)
    commons_overlay_paths: dict[str, str] = Field(default_factory=dict)
    identity_declarations: list[IdentityDeclaration] = Field(default_factory=list)
    # Every conflict arbitration found, whether or not this load raised. Under
    # `strict_identity=True` the load raises and no consumer reads this; under
    # `strict_identity=False` it is the ONLY channel carrying field-policy conflicts --
    # declarations can reconstruct a duplicate owner, but nothing about a field two sources
    # disagreed on. Without it, a diagnostic load would report a clean project by saying
    # exactly what a project with no conflicts says.
    arbitration_errors: list[ArbitrationError] = Field(default_factory=list)
    freshness_enabled: bool = True
    # Registered cross-project scopes (this project's id + declared peer ids). The
    # graph audit accepts `<peer>:<kind>:<slug>` addresses to these scopes (design
    # §B3a; federation resolution deferred to t068) instead of flagging unresolved.
    peer_ids: frozenset[str] = Field(default_factory=frozenset)
    # §B6: child canonical_id -> parent_dataset ref for sci:subCohortOf materialization.
    # Built from the final entities list (after commons merge) immediately before return.
    dataset_parents: dict[str, str] = Field(default_factory=dict)
    # The kinds whose extra-preserving load was schema-checked (unevaluatedProperties:
    # false), i.e. PROJECT_MIXIN_NAMES when the project is pinned, else empty. The graph
    # audit's undeclared_key diagnostic fires only for kinds OUTSIDE this set: a key that
    # survives load on an in-set kind is schema-blessed; an out-of-set kind's extras were
    # never vouched. Default empty is conservative (diagnostic may fire).
    strict_schema_kinds: frozenset[str] = Field(default_factory=frozenset)
    # Reified skill-load records produced during load from gen-3 plans' `skills_loaded`
    # (see graph/skill_loads.py). Empty for gen-<=2 / unpinned projects. Emitted into
    # graph/provenance by materialize._add_skill_load_edges.
    skill_loads: list[SkillLoadRecord] = Field(default_factory=list)
    # Finalized autonomous run records loaded from `runs/` (see graph/autonomous_runs.py).
    # Empty for every project that has never run unattended. Emitted into graph/provenance
    # by materialize._add_run_record_edges, and NEVER into graph/knowledge.
    run_records: list[AutonomousRunRecord] = Field(default_factory=list)


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


def _resolve_active_profiles(project_root: Path) -> ActiveProfiles:
    project_root = project_root.resolve()
    config = _read_project_config(project_root)
    profiles = KnowledgeProfiles.model_validate(config["knowledge_profiles"])
    local_profile = profiles.local
    declared_ontologies: list[str] = list(config.get("ontologies") or [])  # type: ignore[union-attr]
    ontology_catalogs = load_catalogs_for_names(declared_ontologies) if declared_ontologies else []
    local_dir = local_profile_sources_dir(project_root, local_profile=local_profile)
    local_profile_manifest = load_profile_manifest(local_dir / "manifest.yaml")
    profile_manifests: list[ProfileManifest] = [LOCAL_PROFILE]
    shared = load_shared_profile()
    if shared is not None:
        profile_manifests.append(shared)
    local_manifest_rel = os.path.relpath(local_dir / "manifest.yaml", project_root)
    return ActiveProfiles(
        profile_manifests=profile_manifests,
        local_profile_manifest=local_profile_manifest,
        ontology_catalogs=ontology_catalogs,
        local_profile=local_profile,
        local_manifest_rel=local_manifest_rel,
    )


def build_entity_registry(resolved: ActiveProfiles) -> tuple[EntityRegistry, list[SkippedEntity]]:
    """Assemble the profile-aware registry and report stale graduated kinds."""
    registry = EntityRegistry.with_core_types()
    # A kind that a profile/local manifest declares can graduate to a core kind
    # in a later release (e.g. `synthesis`). The registry intentionally refuses
    # to let an extension/profile kind shadow a core one, but for a graduated kind
    # that refusal would crash the whole load (and every command built on it) for
    # any project whose manifest still carries the now-redundant declaration. Skip
    # those stale declarations — the core definition wins — and record each as a
    # SkippedEntity so `science health`/`graph audit` nudge the project to drop it.
    graduated_kind_skips: list[SkippedEntity] = []

    def _graduated_skip(kind: str, manifest_rel: str) -> None:
        graduated_kind_skips.append(
            SkippedEntity(
                path=manifest_rel,
                kind=kind,
                reason="kind_graduated_to_core",
                details=(
                    f"manifest declares entity kind {kind!r}, which is now a core kind; "
                    "the core definition supersedes it. Remove the declaration from the manifest."
                ),
            )
        )

    for profile in resolved.profile_manifests:
        for entity_kind in profile.entity_kinds:
            if registry.is_core_kind(entity_kind.name):
                _graduated_skip(entity_kind.name, f"profile:{profile.name}")
                continue
            registry.register_profile_kind(
                entity_kind.name,
                ProjectEntity,
                owner=profile.name,
                entity_class=_resolve_entity_class(entity_kind.entity_class, EntityClass.OPERATIONAL),
                curation_scope=entity_kind.curation_scope,
            )
    for catalog in resolved.ontology_catalogs:
        for entity_type in catalog.entity_types:
            registry.register_catalog_kind(entity_type.name, DomainEntity, owner=catalog.ontology)
    if resolved.local_profile_manifest is not None:
        for entity_kind in resolved.local_profile_manifest.entity_kinds:
            if registry.is_core_kind(entity_kind.name):
                _graduated_skip(entity_kind.name, resolved.local_manifest_rel)
                continue
            registry.register_extension_kind(
                entity_kind.name,
                ProjectEntity,
                entity_class=_resolve_entity_class(entity_kind.entity_class, EntityClass.OPERATIONAL),
                curation_scope=entity_kind.curation_scope,
            )
    return registry, graduated_kind_skips


def registry_for_project(project_root: Path) -> EntityRegistry:
    """Return the profile-aware entity registry for a project."""
    registry, _skips = build_entity_registry(_resolve_active_profiles(project_root))
    return registry


def validate_canonical_markdown_record(
    raw: dict[str, Any],
    *,
    path: str,
    context: CanonicalMarkdownContext,
) -> CanonicalMarkdownValidation:
    """Validate one already-read Markdown record as a canonical entity.

    This authority performs no I/O. Pathname and descriptor-anchored readers
    supply raw frontmatter plus the same resolved project context, then consume
    the same kind, project-schema, enrichment, and Pydantic-model decision.
    """
    candidate = dict(raw)
    raw_kind = candidate.get("kind")
    if not isinstance(raw_kind, str) or not raw_kind.strip():
        return CanonicalMarkdownValidation(
            rejection=CanonicalMarkdownRejection.MISSING_KIND
        )

    kind = _normalize_kind(raw_kind)
    candidate["kind"] = kind

    def _enrich(candidate_raw: dict[str, Any]) -> frozenset[str]:
        return _enrich_raw(
            candidate_raw,
            kind=kind,
            project_slug=context.project_slug,
            local_profile=context.local_profile,
            active_kinds=context.active_kinds,
            ontology_catalogs=context.ontology_catalogs,
        )

    try:
        entity = context.registry.build(
            kind,
            candidate,
            project_schema=context.project_schema,
            path=path,
            injected=MarkdownAdapter.INJECTED_KEYS,
            enrich=_enrich,
        )
    except EntityKindNotRegisteredError:
        return CanonicalMarkdownValidation(
            kind=kind, rejection=CanonicalMarkdownRejection.UNKNOWN_KIND
        )
    except EntityProjectionError as exc:
        # No authored_aliases: verified that this branch reads only `schema` and `error`.
        # There is no entity to carry them on.
        return CanonicalMarkdownValidation(
            kind=kind,
            schema=exc.schema,
            rejection=CanonicalMarkdownRejection.ENTITY_SCHEMA,
            error=exc.error,
        )
    except ValueError as exc:
        return CanonicalMarkdownValidation(
            kind=kind,
            rejection=CanonicalMarkdownRejection.PROJECT_SCHEMA,
            error=exc,
        )
    return CanonicalMarkdownValidation(
        kind=kind,
        schema=type(entity),
        entity=entity,
        authored_aliases=entity._authored_aliases,
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
    # The AUTHORED pin, and the only thing that arms schema-first validation. Absent (or 1) means the
    # project has not migrated, so its entities load exactly as they did before D5.
    #
    # The pin was VALIDATED in `_read_project_config` through `validated_entity_schema_version` -- the
    # one narrow authority the WRITE path (`load_project_schema_if_pinned`) also reads it through, so
    # the two never disagree about which generation a project speaks. That authority checks the value
    # without full `ProjectConfig` (which requires `name`): a graph build has never demanded a `name`,
    # and tightening that under a migration would put it inside Task 11's diff. So by here the value is
    # already 1, 2, 3, or None -- a `"2"` or `"3"` (stray-quote) was refused at read time, not silently
    # read as unpinned. An ARMED generation both switches validation on AND selects the mixin row it
    # composes against, so the declared value is forwarded straight to `load_project_schema`.
    declared = config.get("entity_schema_version")
    project_schema = (
        load_project_schema(project_root, generation=declared)
        if isinstance(declared, int) and declared in ARMED_SCHEMA_GENERATIONS
        else None
    )
    profiles = KnowledgeProfiles.model_validate(config["knowledge_profiles"])
    freshness_block = config.get("freshness") or {}
    if not isinstance(freshness_block, dict):
        freshness_block = {}
    freshness_enabled = bool(freshness_block.get("enabled", True))

    resolved = _resolve_active_profiles(project_root)
    local_profile = resolved.local_profile
    ontology_catalogs = resolved.ontology_catalogs
    local_profile_manifest = resolved.local_profile_manifest
    active_profiles = list(resolved.profile_manifests)
    if local_profile_manifest is not None:
        active_profiles.append(local_profile_manifest)
    active_kinds = known_kinds(extra_profiles=active_profiles, ontology_catalogs=ontology_catalogs)

    registry, graduated_kind_skips = build_entity_registry(resolved)
    canonical_context = CanonicalMarkdownContext(
        project_slug=project_root.name,
        local_profile=local_profile,
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
        registry=registry,
        project_schema=project_schema,
    )

    project_paths = resolve_paths(project_root)
    adapters: list[StorageAdapter] = [
        # The dataset/workflow/workflow-run/workflow-step family are now first-class
        # entities/ kinds (home=entities/<kind>, strategy=id-local). They are
        # discovered via the default entities/ root like every other owner kind;
        # the legacy doc/ scan roots have been removed (owners no longer live there).
        # See docs/user-guide/project-layout.md.
        MarkdownAdapter(
            virtual_files=markdown_overrides,
        ),
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
    # Collection is EXHAUSTIVE and SELECTION-FREE: every validated entity becomes a
    # contribution, and nothing here consults what another adapter claimed. Identity is decided
    # once, by `arbitrate_contributions`, over the complete set -- so the outcome cannot depend
    # on adapter iteration order, and a contribution that loses is recorded as having lost
    # rather than deleted.
    contributions: list[SourceContribution] = []
    field_policies: dict[tuple[str, str], dict[str, MergePolicy]] = {}
    markdown_documents: list[MarkdownSourceDocument] = []
    skipped_entities: list[SkippedEntity] = list(graduated_kind_skips)

    # cwd for relative-path resolution in adapters. The StorageAdapter.load_raw()
    # contract resolves ref.path against cwd; we chdir into project_root rather
    # than broaden the Protocol. Restored in the finally block.
    prev_cwd = os.getcwd()
    os.chdir(project_root)
    try:
        for adapter in adapters:
            for ref in adapter.discover(project_root):
                raw = adapter.load_raw(ref)
                doc = adapter.source_document(ref, raw)
                if doc is not None:
                    markdown_documents.append(doc)
                validation = validate_canonical_markdown_record(
                    raw,
                    path=str(ref.path),
                    context=canonical_context,
                )
                if (
                    validation.rejection
                    == CanonicalMarkdownRejection.MISSING_KIND
                ):
                    # Adapter returned a record with no kind (e.g. frontmatter-less
                    # markdown). Skip rather than fail — mirrors the legacy behavior
                    # where parse_entity_file returned None.
                    continue
                kind = validation.kind
                if kind is None:
                    raise AssertionError("canonical validation omitted normalized kind")
                if validation.rejection == CanonicalMarkdownRejection.UNKNOWN_KIND:
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
                if validation.rejection == CanonicalMarkdownRejection.PROJECT_SCHEMA:
                    if not isinstance(validation.error, ValueError):
                        raise AssertionError(
                            "project-schema rejection omitted its validation error"
                        )
                    raise validation.error
                if validation.rejection == CanonicalMarkdownRejection.ENTITY_SCHEMA:
                    schema = validation.schema
                    exc = validation.error
                    if schema is None or not isinstance(exc, ValidationError):
                        raise AssertionError(
                            "entity-schema rejection omitted schema or error"
                        )
                    details = _format_missing_fields(exc)
                    failure = _format_schema_validation_failure(kind=kind, schema=schema, exc=exc)
                    if registry.is_core_kind(kind):
                        if adapter.skip_core_on_missing_identity and _is_missing_identity_validation(exc):
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
                                f"schema validation failed for registered entity kind {kind!r} at {ref.path}: {failure}"
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
                                details=failure,
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
                            details=failure,
                        )
                    )
                    continue
                entity = validation.entity
                if entity is None:
                    raise AssertionError("accepted canonical record omitted its entity")
                owner_scope, deprecated = classify_owner_scope(adapter.name, project_name=project_name)
                _contribute(
                    entity=entity,
                    ref=ref,
                    adapter_name=adapter.name,
                    participation_mode=adapter.participation_mode,
                    owner_scope=owner_scope,
                    deprecated=deprecated,
                    contributions=contributions,
                    field_policies=field_policies,
                )
    finally:
        os.chdir(prev_cwd)

    # Legacy model/parameter loaders from knowledge/sources/<local>/{models,parameters}.yaml.
    # Produce ProjectEntity records through the registry so they join the same pipeline.
    typed_record_cache: _TypedRecordCache = {}
    for entity, ref in [
        *_load_legacy_records(
            project_root,
            registry=registry,
            project_schema=project_schema,
            local_profile=local_profile,
            project_slug=project_slug,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
            typed_record_cache=typed_record_cache,
        ),
        *_load_structured_source_records(
            project_root,
            registry=registry,
            project_schema=project_schema,
            local_profile=local_profile,
            local_profile_manifest=local_profile_manifest,
            project_slug=project_slug,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
            typed_record_cache=typed_record_cache,
        ),
    ]:
        owner_scope, deprecated = classify_owner_scope(ref.adapter_name, project_name=project_name)
        _contribute(
            entity=entity,
            ref=ref,
            adapter_name=ref.adapter_name,
            participation_mode=ParticipationMode.OWNER,
            owner_scope=owner_scope,
            deprecated=deprecated,
            contributions=contributions,
            field_policies=field_policies,
        )

    relations = _load_structured_relations(project_root, local_profile=local_profile)
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

    if include_commons:
        from science_tool.graph.commons_sources import collect_commons_contributions

        # Close over what commons says BEFORE anything is decided. Seeds are the local
        # CANDIDATES, not a selection: closure asks which commons ids this project reaches, and
        # an id reached by a candidate that later loses a contest was still reached.
        closure = collect_commons_contributions(
            project_root=project_root,
            project_slug=project_slug,
            seed_entities=[c.candidate for c in contributions if isinstance(c, EntityContribution)],
            project_relations=relations,
            project_bindings=bindings,
            registry=registry,
            project_schema=project_schema,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )
        contributions.extend(closure.contributions)
        field_policies.update(closure.field_policies)

    # ONE decision, over the COMPLETE set: every local adapter, every legacy loader, and all of
    # commons have now contributed. Arbitration sorts before it decides, so the outcome does not
    # depend on the order any of the loops above happened to run in.
    arbitration = arbitrate_contributions(
        contributions,
        context=ArbitrationContext(project_scope=project_name, field_policies=field_policies),
    )
    identity_declarations: list[IdentityDeclaration] = list(arbitration.identity_declarations)
    entities: list[Entity] = list(arbitration.entities)
    entity_source_adapters: dict[str, str] = dict(arbitration.entity_source_adapters)
    dataset_datapackages: dict[str, str] = dict(arbitration.dataset_datapackages)
    arbitration_errors: list[ArbitrationError] = list(arbitration.errors)
    # What actually COMPOSED, not what merely resolved. An overlay whose id a project owner
    # won did not compose, and reporting it here would claim project commentary reached a graph
    # node that never received it.
    commons_overlay_paths: dict[str, str] = dict(arbitration.overlay_paths)

    # Nested edges come from the REPRESENTATIVES, not from encounter-order candidates. A
    # candidate that lost a contest must not leak its edges into the graph: the entity the
    # reader sees would then have relations no file it can open actually declares.
    relations.extend(_entity_nested_relations(entities))
    relations.sort(key=lambda relation: (relation.graph_layer, relation.subject, relation.predicate, relation.object))

    # THE STRICT BOUNDARY. Arbitration always detects; strictness decides raise vs. report.
    # The ledger is the fact, and these exceptions are a projection of it -- so a diagnostic
    # load and a strict load disagree about what to DO, never about what is true.
    if strict_identity:
        _raise_first_arbitration_error(arbitration_errors)

    dataset_parents = {e.canonical_id: e.parent_dataset for e in entities if e.kind == "dataset" and e.parent_dataset}

    # Archived ids remain resolvable reference targets (index-only; archived
    # markdown is NOT loaded as a live entity). Folding them into manual_aliases
    # makes the audit + materialization resolvers treat refs to archived ids as
    # resolved instead of unresolved_reference. Fail loud on a real collision with a
    # project-authored manual alias (archive-vs-entity collisions surface separately
    # as AliasCollisionError when ReferenceResolver.from_entities runs).
    from science_tool.archive import load_archive_index

    manual_aliases = _load_manual_aliases(project_root, local_profile=local_profile)
    archive_alias_tokens: set[str] = set()
    for token, canonical in load_archive_index(project_root).resolvable_ids().items():
        existing = manual_aliases.get(token)
        if existing is not None and existing != canonical:
            raise ValueError(
                f"archive token {token!r} -> {canonical!r} collides with project manual "
                f"alias -> {existing!r}; unarchive or rename before archiving"
            )
        manual_aliases[token] = canonical
        archive_alias_tokens.add(token)

    generation = project_schema._generation if project_schema is not None else None
    skill_loads = collect_skill_loads(
        entities,
        generation=generation,
        aliases=load_skill_aliases() if generation == 3 else {},
    )
    run_records = load_run_records(project_root)

    return ProjectSources(
        project_name=str(config["name"]),
        project_root=str(project_root),
        profiles=profiles,
        entities=entities,
        entity_source_adapters=entity_source_adapters,
        dataset_datapackages=dataset_datapackages,
        relations=relations,
        bindings=bindings,
        manual_aliases=manual_aliases,
        archive_alias_tokens=frozenset(archive_alias_tokens),
        ontology_catalogs=ontology_catalogs,
        registry=registry,
        markdown_documents=markdown_documents,
        skipped_entities=skipped_entities,
        commons_overlay_paths=commons_overlay_paths,
        identity_declarations=identity_declarations,
        arbitration_errors=arbitration_errors,
        freshness_enabled=freshness_enabled,
        peer_ids=frozenset(config.get("peer_ids") or []),  # type: ignore[arg-type]
        dataset_parents=dataset_parents,
        strict_schema_kinds=PROJECT_MIXIN_NAMES if project_schema is not None else frozenset(),
        skill_loads=skill_loads,
        run_records=run_records,
    )


# Alias provenance, most-authoritative first. The ONLY collision resolved silently is
# (mappings, derived): a `mappings.yaml` mapping is an explicit, external human
# declaration and wins over an auto-derived convenience token. Every other cross-target
# collision raises AliasCollisionError. In particular a `frontmatter` alias does NOT beat
# a colliding derived short id -- an entity claiming another entity's short id is an
# ambiguity to report, not to silently resolve.
_PROV_CANONICAL = 0  # entity.canonical_id -- the identity itself
_PROV_MAPPINGS = 1  # a `mappings.yaml` mapping (external, project-authored)
_PROV_FRONTMATTER = 2  # an explicit `aliases:` entry on the entity itself
_PROV_ARCHIVE = 3  # a token folded in from the archive index
_PROV_DERIVED = 4  # path-stem / number-derived short token (`q04` from `0004`)


def build_alias_map(
    entities: list[Entity],
    manual_aliases: dict[str, str] | None = None,
    *,
    archive_alias_tokens: frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Build a best-effort alias map for canonical entity resolution.

    Provenance precedence (D5 / design rev 9). A `mappings.yaml` mapping silently overrides
    a colliding AUTO-DERIVED alias, because the number/path-derived short token (`q04` from
    `0004`) is a convenience, never an identity authority, and a project that renumbered
    its records declares the old numbers there deliberately. Every OTHER cross-target
    collision still raises `AliasCollisionError`: canonical-vs-canonical, mappings-vs-
    mappings, an entity's own frontmatter alias vs anything it disagrees with (including a
    derived short id -- that is a real ambiguity, not a convenience to drop), and an
    archive token vs anything. An archive token never wins silently, so an archived id can
    never shadow a live entity's derived token.
    """
    # token -> (canonical_id, provenance)
    claims: dict[str, tuple[str, int]] = {}

    def register(token: str, canonical_id: str, provenance: int) -> None:
        existing = claims.get(token)
        if existing is None:
            claims[token] = (canonical_id, provenance)
            return
        existing_id, existing_prov = existing
        if existing_id == canonical_id:
            # Same target: keep the strongest provenance so a later derived duplicate can
            # never weaken a mapping/frontmatter claim.
            if provenance < existing_prov:
                claims[token] = (canonical_id, provenance)
            return
        if {existing_prov, provenance} == {_PROV_MAPPINGS, _PROV_DERIVED}:
            if existing_prov == _PROV_DERIVED:
                claims[token] = (canonical_id, provenance)  # the mapping replaces derived
            return  # else the mapping already holds it; drop the derived token
        raise AliasCollisionError(
            alias=token, first_canonical_id=existing_id, second_canonical_id=canonical_id
        )

    for entity in entities:
        register(entity.canonical_id, entity.canonical_id, _PROV_CANONICAL)
        register(entity.canonical_id.lower(), entity.canonical_id, _PROV_CANONICAL)
        # Provenance is CARRIED from load (`_authored_aliases`), never reconstructed by
        # token equality: a frontmatter token that coincides with this entity's own
        # derived short id (`q01` authored on the entity `0001` also derives) stays
        # FRONTMATTER, so a colliding mappings entry still raises instead of silently
        # winning as it would against a purely-derived token.
        authored = entity._authored_aliases
        for alias in entity.aliases:
            provenance = _PROV_FRONTMATTER if alias in authored else _PROV_DERIVED
            register(alias, entity.canonical_id, provenance)
            register(alias.lower(), entity.canonical_id, provenance)
    for alias, canonical_id in (manual_aliases or {}).items():
        provenance = _PROV_ARCHIVE if alias in archive_alias_tokens else _PROV_MAPPINGS
        register(alias, canonical_id, provenance)
        register(alias.lower(), canonical_id, provenance)

    return {token: claim[0] for token, claim in claims.items()}


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


# Annotation-only reference namespaces: pointer FIELDS an author keeps in source
# files (e.g. `meta:<phase>` process tags) whose individual metadata-reference
# edges are intentionally NOT materialized and require no resolvable target. As of
# S3b `spec` is a fully resolved first-class entity kind: a spec FILE materializes
# as a node and every `spec:` reference (ordinary pointer fields included) resolves
# to it and materializes an edge, so `spec` is no longer suppressed here.
_ANNOTATION_REF_PREFIXES = frozenset({"meta"})


def is_metadata_reference(raw: str) -> bool:
    """Return True for annotation-only refs (`meta:*`).

    These are intentional annotations preserved in source files but excluded from
    KG materialization at the metadata-reference edge level (no target required,
    no edge created). `spec:` is NOT among them as of S3b: it resolves to a real
    spec entity and materializes an edge like any other kind reference.
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
) -> frozenset[str]:
    """Centralized normalization layer between adapter output and Entity validation.

    Mutates `raw` in place. Fills Entity defaults + legacy normalization:
    - `project`, `ontology_terms`, `related`, `source_refs`, `content_preview`
    - Profile defaulting (core/ontology/local)
    - Alias derivation for hypothesis/question/task
    - Normalize `kind` and optional core-only `type` projection
    - Description → content_preview fallback (legacy aggregate rows)
    - Validate reasoning enum fields and fail early on legacy/invalid shapes

    Returns the frozenset of EXPLICITLY-authored frontmatter alias tokens (empty for
    entities without a canonical id or an `aliases:` list). Callers set this on the
    constructed entity's `_authored_aliases` so alias resolution can carry provenance.
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

    canonical_id = raw.get("canonical_id") or raw.get("id")
    if isinstance(canonical_id, str) and canonical_id:
        raw["canonical_id"] = canonical_id
        raw.setdefault("id", canonical_id)

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
    # `authored` captures ONLY the explicit frontmatter tokens (cleaned exactly as
    # `_derive_aliases.add` stores them), so a coincident authored/derived token keeps
    # its authored provenance downstream instead of being reclassified as derived.
    authored: frozenset[str] = frozenset()
    if isinstance(canonical_id, str):
        explicit = raw.get("aliases") or []
        if not isinstance(explicit, list):
            explicit = []
        explicit_list = [str(a) for a in explicit]
        authored = frozenset(
            token for a in explicit_list if (token := a.strip()) and token != canonical_id
        )
        path_aliases = _path_alias_tokens(raw.get("file_path"), kind)
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

    return authored


def _load_legacy_records(
    project_root: Path,
    *,
    registry: EntityRegistry,
    project_schema: ProjectSchema | None,
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
        authored = frozenset(record.model_dump(exclude_unset=True))
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
        def _enrich(candidate_raw: dict[str, Any]) -> frozenset[str]:
            return _enrich_raw(
                candidate_raw,
                kind="model",
                project_slug=project_slug,
                local_profile=local_profile,
                active_kinds=active_kinds,
                ontology_catalogs=ontology_catalogs,
            )

        entity = registry.build(
            "model",
            raw,
            project_schema=project_schema,
            path=record.source_path,
            injected=_LEGACY_INJECTED_KEYS - authored,
            enrich=_enrich,
        )
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
        authored = frozenset(record.model_dump(exclude_unset=True))
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
        def _enrich(candidate_raw: dict[str, Any]) -> frozenset[str]:
            return _enrich_raw(
                candidate_raw,
                kind="canonical_parameter",
                project_slug=project_slug,
                local_profile=local_profile,
                active_kinds=active_kinds,
                ontology_catalogs=ontology_catalogs,
            )

        entity = registry.build(
            "canonical_parameter",
            raw,
            project_schema=project_schema,
            path=record.source_path,
            injected=_LEGACY_INJECTED_KEYS - authored,
            enrich=_enrich,
        )
        out.append((entity, SourceRef(adapter_name="legacy-parameter", path=record.source_path)))

    return out


def _load_structured_source_records(
    project_root: Path,
    *,
    registry: EntityRegistry,
    project_schema: ProjectSchema | None,
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
    rows from an audit) use a declared single-type source file rather than a
    retired aggregate manifest.
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
        for record in records:
            authored_row = record.model_dump(exclude_unset=True)
            raw = normalize_structured_row(authored_row)
            authored = frozenset(raw)
            # Loader BACKFILLS -- policy, not source content, and deliberately after normalization
            # so the schema sees them as the loader's contribution rather than the author's.
            raw["kind"] = kind_name
            raw["type"] = kind_name
            raw.setdefault("canonical_id", record.canonical_id)
            raw.setdefault("title", record.title or record.canonical_id)
            raw.setdefault("profile", record.profile or local_profile)
            raw.setdefault("file_path", default_path)
            raw.setdefault("related", list(record.related))
            raw.setdefault("source_refs", list(record.source_refs))
            raw.setdefault("evidence_refs", list(record.evidence_refs))
            raw.setdefault("aliases", list(record.aliases))
            raw.setdefault("ontology_terms", list(record.ontology_terms))
            if record.domain is not None:
                raw.setdefault("domain", record.domain)
            if record.description is not None:
                raw.setdefault("description", record.description)
            if record.created is not None:
                raw.setdefault("created", record.created)
            if record.updated is not None:
                raw.setdefault("updated", record.updated)
            def _enrich(
                candidate_raw: dict[str, Any], _kind: str = kind_name
            ) -> frozenset[str]:
                return _enrich_raw(
                    candidate_raw,
                    kind=_kind,
                    project_slug=project_slug,
                    local_profile=local_profile,
                    active_kinds=active_kinds,
                    ontology_catalogs=ontology_catalogs,
                )

            entity = registry.build(
                kind_name,
                raw,
                project_schema=project_schema,
                path=record.source_path or default_path,
                injected=_STRUCTURED_INJECTED_KEYS - authored,
                enrich=_enrich,
            )
            out.append((entity, SourceRef(adapter_name="structured-source", path=record.source_path or default_path)))
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
                    object=relation.target,
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

        raw_role = item.get("role")
        role: MembershipRole | None = None
        if raw_role is not None:
            if not isinstance(raw_role, str):
                raise ValueError(
                    f"relations.yaml: 'role' must be a string, got {type(raw_role).__name__!r} "
                    f"(value: {raw_role!r}); valid roles are "
                    f"{[r.value for r in MembershipRole]}"
                )
            role = MembershipRole(raw_role)

        relations.append(
            SourceRelation(
                subject=subject,
                predicate=predicate,
                object=obj,
                graph_layer=str(item.get("graph_layer") or "graph/knowledge"),
                source_path=str(item.get("source_path") or _default_local_source_path(local_profile, "relations.yaml")),
                role=role,
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
    yaml_path = project_config_path(project_root)
    cache_key: tuple[str, int] | None = None
    if yaml_path.is_file():
        cache_key = (str(yaml_path.resolve()), yaml_path.stat().st_mtime_ns)
        cached = _PROJECT_CONFIG_CACHE.get(cache_key)
        if cached is not None:
            return deepcopy(cached)

    data: dict[str, object] = {}
    if yaml_path.is_file():
        loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        if loaded is not None:
            if not isinstance(loaded, dict):
                raise ValueError(
                    f"{yaml_path}: project configuration must be a mapping"
                )
            data = loaded

    # The pin, VALIDATED here through the one narrow authority the write path also uses -- key AND
    # value, WITHOUT the rest of `ProjectConfig` (which requires `name`, a tightening not this arc's).
    # It has to run HERE: the pin decides whether this loader enforces the entity schema at all, so a
    # misspelled key OR an illegal value (`"2"`, `3`) would read as "unpinned", switch the schema check
    # off, and load an unvalidated corpus while its author believed it was protected. Fail-open,
    # reachable by one transposed letter or one stray quote.
    pinned_version = validated_entity_schema_version(data)

    local_profile = selected_local_profile_name(data)

    raw_ontologies = data.get("ontologies") or []
    if not isinstance(raw_ontologies, list):
        raw_ontologies = []

    raw_freshness = data.get("freshness") or {}
    if not isinstance(raw_freshness, dict):
        raw_freshness = {}

    # Registered scopes whose `<scope>:<kind>:<slug>` addresses are recognized as
    # cross-project references (this project's own id + declared peer ids). Used by
    # the graph audit to accept scoped peer refs as the forward-compatible structured
    # form (design §B3a) instead of flagging them unresolved; resolution is deferred
    # to federation (t068, §D4). Mirrors refs.py `_load_project_ids` for tool parity.
    peer_ids: list[str] = []
    self_id = data.get("id")
    if isinstance(self_id, str) and self_id:
        peer_ids.append(self_id)
    raw_peers = data.get("peers") or []
    if isinstance(raw_peers, list):
        for entry in raw_peers:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]:
                peer_ids.append(str(entry["id"]))

    config: dict[str, object] = {
        "name": str(data.get("name") or project_root.name),
        "knowledge_profiles": {
            "local": local_profile,
        },
        "ontologies": [str(o) for o in raw_ontologies],
        "freshness": raw_freshness,
        "peer_ids": peer_ids,
        # This dict is a CURATED projection of science.yaml -- an unlisted key does not reach the
        # loader at all, so the pin has to be listed. It is the VALIDATED value: `2` arms schema
        # validation, `1`/absent do not, and an illegal value already raised above rather than
        # reaching here as a silent "unpinned".
        "entity_schema_version": pinned_version,
    }
    if cache_key is not None:
        _PROJECT_CONFIG_CACHE[cache_key] = config
    return deepcopy(config)


def resolve_local_profile_name(project_root: Path) -> str:
    """Return the active local knowledge-profile name for the project at *project_root*.

    Uses ``knowledge_profiles.local`` in the project config and defaults to
    ``"local"`` when it is absent.
    """
    config = _read_project_config(project_root)
    return selected_local_profile_name(config)


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
    else:
        numeric_match = _NUMERIC_ID_PREFIX_RE.match(slug)
        if numeric_match is None:
            head = slug.split("-", 1)[0]
            numeric_match = _NUMERIC_ID_PREFIX_RE.match(head)
        prefix = _KIND_SHORT_PREFIX.get(kind)
        if numeric_match is not None and prefix is not None:
            number = numeric_match.group("number")
            token = f"{prefix}{number}"
            add(f"{kind}:{token.lower()}")
            add(f"{kind}:{token.upper()}")
            add(token.lower())
            add(token.upper())
            compact_number = number.lstrip("0").zfill(2)
            if compact_number != number:
                compact_token = f"{prefix}{compact_number}"
                add(f"{kind}:{compact_token.lower()}")
                add(f"{kind}:{compact_token.upper()}")
                add(compact_token.lower())
                add(compact_token.upper())

    return aliases


def _path_alias_tokens(file_path: object, kind: str) -> list[str]:
    """Short-id alias tokens derived from a `<token>-<rest>.md` file stem.

    Mirrors the legacy MarkdownProvider behavior: only hypothesis/question/task files whose
    stem starts with a `[a-z]<digits>` short id contribute path aliases.
    """
    if not (isinstance(file_path, str) and file_path and kind in {"hypothesis", "question", "task"}):
        return []
    stem = Path(file_path).stem
    match = _SHORT_ID_RE.match(stem)
    if match is None:
        match = _SHORT_ID_RE.match(stem.split("-", 1)[0])
    if match is None:
        return []
    token = match.group("token")
    return [f"{kind}:{token.lower()}", f"{kind}:{token.upper()}", token.lower(), token.upper()]


def _raise_first_arbitration_error(errors: list[ArbitrationError]) -> None:
    """Project the arbitration ledger onto the strict loader's exception contract.

    `errors` is already sorted, so a project with several problems reports the same one every
    run instead of whichever adapter happened to run first.
    """
    for error in errors:
        match error.code:
            case ArbitrationCode.DUPLICATE_OWNER:
                # This exception predates arbitration and names exactly two refs. Duplicate-owner
                # is detected over the whole set, so there may be more than two; the pair shown
                # is the first two in sorted order, and the rest surface once these are resolved.
                first, second = error.contributors[0], error.contributors[1]
                raise EntityIdentityCollisionError(error.canonical_id, first, second)
            case ArbitrationCode.CONTRIBUTION_CONFLICT:
                raise ContributionConflictError(
                    canonical_id=error.canonical_id,
                    field=error.field,
                    refs=error.contributors,
                )
            case ArbitrationCode.MISSING_OWNER | ArbitrationCode.AMBIGUOUS_REPRESENTATIVE:
                # Deliberately diagnostic. Both are states a load can legitimately reach
                # mid-migration, and both already suppress materialization of the affected id,
                # so the graph never shows a guessed answer. The audit reports them.
                continue
            case unhandled:  # pragma: no cover - totality guard
                # No fall-through. A new code must be given a disposition HERE, because the
                # fall-through's answer would have been "do not raise" -- silently downgrading
                # an unconsidered defect to a passing strict build.
                raise RuntimeError(f"arbitration code has no strict-boundary disposition: {unhandled!r}")


def _contribute(
    *,
    entity: Entity,
    ref: SourceRef,
    adapter_name: str,
    participation_mode: ParticipationMode,
    owner_scope: str,
    deprecated: bool,
    contributions: list[SourceContribution],
    field_policies: dict[tuple[str, str], dict[str, MergePolicy]],
) -> None:
    """Record one contribution. UNCONDITIONALLY -- it never asks what else claimed this id.

    That is the whole point: a contribution is a statement that a source made, and whether the
    statement wins is not a property of the statement. Deciding here is what let iteration order
    determine identity and erase the loser.
    """
    declaration = IdentityDeclaration(
        canonical_id=entity.canonical_id,
        participation_mode=participation_mode,
        owner_scope=owner_scope,
        adapter=adapter_name,
        source_ref=ref,
        deprecated=deprecated,
    )
    contributions.append(EntityContribution(declaration=declaration, candidate=entity))
    if participation_mode is not ParticipationMode.OWNER:
        return
    try:
        profile = default_profile_for_kind(entity.kind)
    except ProfileParseError:
        # NOT a fallback policy. It means no overlay/external composition contract exists for
        # this project-only kind, so there is nothing to register. Arbitration fails loudly if
        # an attachment later needs a policy that was never declared -- which is the honest
        # outcome, rather than composing under a guessed default.
        return
    field_policies[(owner_scope, entity.canonical_id)] = read_merge_policy(profile)


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


def _format_schema_validation_failure(*, kind: str, schema: type[Entity], exc: ValidationError) -> str:
    """Format an entity validation failure with authoring discovery hints."""
    details = _format_missing_fields(exc)
    source = inspect.getsourcefile(schema) or inspect.getfile(schema)
    return "\n".join(
        [
            details,
            f"inspect effective schema: science entity sections {kind} --format json",
            f'create a valid stub: science entity create {kind} "Title"',
            f"schema source: {Path(source).as_posix()}",
        ]
    )


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

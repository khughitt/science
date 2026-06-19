"""Deterministic graph materialization from structured project sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
import hashlib
import json
from pathlib import Path
from typing import Literal as _Literal
from urllib.parse import quote

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import PROV, RDF, RDFS, SKOS, XSD
from science_model.entities import Entity, EntityClass, EvidenceLineEntity
from science_model.identity import EntityScope
from science_model.ontologies.schema import OntologyCatalog
from science_model.patch_definition import PatchDefinitionEntity
from science_model.profiles import CORE_PROFILE
from science_model.profiles.schema import RelationKind
from science_model.reasoning import EvidenceStance, MeasurementModel, RivalModelPacket
from science_model.relations import relation_allows_kinds

from science_tool.addressing import is_address, parse_address
from science_tool.bibliography import is_bibliography_reference
from science_tool.code.lifecycle import ORPHAN_GATING_EXEMPT_STATUSES
from science_tool.commons.geneset import GenesetCollectionError, parse_geneset_rows
from science_tool.commons.datapackage import DatasetResource, read_dataset_resources
from science_tool.commons.geneset_resources import (
    dataset_datapackage_path,
    dataset_geneset_frontmatter,
    read_member_rows,
)
from science_tool.graph.dataset_usage import (
    add_usage_record_to_graph,
    project_entity_uri,
    usage_records_for_entity,
    usage_records_for_geneset_rows,
)
from science_tool.graph.dataset_independence import (
    derive_dataset_independence_records,
    emit_dataset_independence_records,
)
from science_tool.graph.dataset_qa import emit_dataset_qa_layer
from science_tool.graph.freshness import (
    EntityFreshnessInfo,
    close_bears_on,
    derive_bears_on_from_audits,
    derive_bears_on_from_chain_links,
    derive_bears_on_from_pre_registrations,
    derive_bears_on_from_produced_by_code,
    derive_bears_on_from_provenance,
    derive_bears_on_from_typed_edges,
    derive_freshness,
)
from science_tool.graph.identity_table import ParticipationMode, build_identity_table
from science_tool.graph.migrate import AuditRow, audit_project_sources
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import (
    ProjectSources,
    SourceBinding,
    SourceRelation,
    _EXTERNAL_PREFIXES,
    external_prefixes,
    is_external_reference,
    is_metadata_reference,
    load_project_sources,
)
from science_tool.graph.inquiry_compile import emit_inquiry_views
from science_tool.graph.io import CITO_NS, DCAT_NS, DCTERMS_NS, entity_uri_for_ref
from science_tool.graph.source_snapshots import (
    SourceSnapshotResult,
    compute_source_snapshots,
    emit_source_snapshots,
)
from science_tool.graph.patch_membership import (
    derive_patch_memberships,
    emit_patch_memberships,
)
from science_tool.graph.store import (
    CURIE_PREFIXES,
    DEFAULT_GRAPH_PATH,
    GRAPH_LAYERS,
    PROJECT_ENTITY_PREFIXES,
    PROJECT_NS,
    SCHEMA_NS,
    SCI_NS,
    canonical_id_from_entity_uri,
    save_graph_dataset,
)


def _iter_membership_refs(entity):
    """Yield (frame_ref, MembershipRole) for an entity's discusses entries.

    Propositions expose iter_memberships(); any other entity with a plain
    `discusses` list is treated as all-core (defensive, no behavior change).
    """
    iter_memberships = getattr(entity, "iter_memberships", None)
    if callable(iter_memberships):
        yield from sorted(iter_memberships(), key=lambda pair: pair[0])
        return
    from science_model.reasoning import MembershipRole

    for raw in sorted(getattr(entity, "discusses", []) or []):
        yield raw, MembershipRole.CORE


def _membership_uri(prop_canonical: str, frame_canonical: str):
    """Deterministic IRI for a (proposition, frame) membership node."""
    slug = f"{prop_canonical}__{frame_canonical}".replace(":", "_").replace("/", "_")
    return PROJECT_NS[f"membership/{slug}"]


@dataclass(frozen=True)
class _ArchivedEndpoint:
    """Duck-typed stand-in for an archived relation object: only ``.canonical_id``
    and ``.kind`` are read by ``_validate_authored_relation_endpoint``."""

    canonical_id: str
    kind: str


def _archived_uri_if_active(
    canonical_id: str | None,
    archive_active: dict,
    referenced_archived: set[str],
) -> URIRef | None:
    """``canonical_id`` is a RESOLVED id with no live entity. If it is an active
    archived id, record it for stub emission and return its URI; else None."""
    if canonical_id is not None and canonical_id in archive_active:
        referenced_archived.add(canonical_id)
        return _entity_uri(canonical_id)
    return None


def build_dataset_from_sources(sources: ProjectSources) -> Dataset:
    """Public wrapper for diagnostic re-derivation (e.g. `patch check`).

    Lets diagnostics rebuild the expected Dataset without importing the private
    `_build_dataset_from_sources` helper or writing `graph.trig`.
    """
    return _build_dataset_from_sources(sources)


@dataclass(frozen=True)
class CompilationResult:
    """Output of the compiler pipeline.

    `dataset`/`trig_path` are None for an audit-only run (`stop_after="audit"`).
    `sources` and `audit_rows` are the Load and Audit phase outputs, retained so
    callers (e.g. diagnostics) can inspect them without re-running those phases.
    For a full run, `dataset` reflects POST-write state: `save_graph_dataset` adds
    REVISION_URI provenance triples in place, so the field is not a pre-write
    snapshot (compare semantic content with REVISION_URI filtered out).
    """

    sources: ProjectSources
    audit_rows: list[AuditRow]
    has_failures: bool
    dataset: Dataset | None
    trig_path: Path | None


@dataclass(frozen=True)
class EmitResult:
    """Output of the Emit phase: the base authored graph plus the build context
    the Derive phase consumes (so Derive never recomputes `kind_class` or
    `pre_registration_targets`)."""

    dataset: Dataset
    kind_class: dict[str, EntityClass]
    pre_registration_targets: dict[URIRef, list[URIRef]]


def _emit_phase(sources: ProjectSources, *, archive_active: dict | None = None) -> EmitResult:
    """Emit the base authored graph and build the context Derive consumes.

    Owns dataset/named-graph setup, resolver/index construction, all base-graph
    emission through `_validate_no_amendment_cycles`, and the `kind_class` /
    `pre_registration_targets` build context.
    """
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    dataset.graph(PROJECT_NS["graph/causal"])
    datasets = dataset.graph(PROJECT_NS["graph/datasets"])

    archive_active = archive_active or {}
    referenced_archived: set[str] = set()

    resolver = ReferenceResolver.from_entities(
        sources.entities, manual_aliases=sources.manual_aliases, identity_table=build_identity_table(sources)
    )
    entity_index = {entity.canonical_id: entity for entity in sources.entities}
    ext_prefixes = _EXTERNAL_PREFIXES | external_prefixes(sources.ontology_catalogs)
    external_reference_ids = {
        d.canonical_id
        for d in sources.identity_declarations
        if d.participation_mode == ParticipationMode.EXTERNAL_REFERENCE
    }

    for entity in sources.entities:
        _add_entity(
            entity=entity,
            knowledge=knowledge,
            provenance=provenance,
            overlay_paths=sources.commons_overlay_paths,
            external_reference_ids=external_reference_ids,
        )

    for entity in sources.entities:
        _add_relations(
            entity,
            entity_index=entity_index,
            resolver=resolver,
            knowledge=knowledge,
            bridge=bridge,
            provenance=provenance,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
            archive_active=archive_active,
            referenced_archived=referenced_archived,
        )

    _add_produced_by_edges(sources, entity_index=entity_index, knowledge=knowledge)
    _add_dataset_usage_edges(sources, resolver=resolver, provenance=provenance)
    _add_sub_cohort_edges(sources, resolver=resolver, knowledge=knowledge)
    _add_dataset_resource_edges(sources, datasets=datasets)

    kind_class = _classify_entities(sources)
    pre_registration_targets = _pre_registration_commitment_targets(
        sources,
        entity_index=entity_index,
        resolver=resolver,
    )

    for relation in sources.relations:
        _add_authored_relation(
            relation,
            dataset=dataset,
            entity_index=entity_index,
            resolver=resolver,
            bridge=bridge,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
            kind_class=kind_class,
            archive_active=archive_active,
            referenced_archived=referenced_archived,
        )

    # Emit one tombstone stub node per referenced active archived id into the
    # knowledge graph. Runs AFTER both the per-entity relation loop and the
    # authored-relation loop have populated `referenced_archived`.
    for archived_id in sorted(referenced_archived):
        row = archive_active[archived_id]
        uri = _entity_uri(archived_id)
        knowledge.add((uri, RDF.type, SCI_NS.ArchivedEntity))
        if row.kind:
            knowledge.add((uri, SCI_NS.entityKind, Literal(row.kind)))
        if row.title:
            knowledge.add((uri, RDFS.label, Literal(row.title)))
        knowledge.add((uri, SCI_NS.archived, Literal(True)))
        # superseded_by emitted only when it resolves to a known id — a live entity OR
        # another active archived id. Unresolvable/dangling successor -> omitted.
        if row.superseded_by and (row.superseded_by in entity_index or row.superseded_by in archive_active):
            knowledge.add((uri, SCI_NS.supersededBy, _entity_uri(row.superseded_by)))

    for binding in sources.bindings:
        _add_binding(
            binding,
            knowledge=knowledge,
            provenance=provenance,
            entity_index=entity_index,
            resolver=resolver,
        )

    _validate_no_amendment_cycles(dataset)

    return EmitResult(
        dataset=dataset,
        kind_class=kind_class,
        pre_registration_targets=pre_registration_targets,
    )


def _derive_phase(
    emit: EmitResult,
    *,
    sources: ProjectSources,
    source_snapshots: SourceSnapshotResult | None,
) -> None:
    """Emit the snapshot layer and derive the epistemic layers onto `emit.dataset`.

    Preserves the load-bearing ordering: snapshot layer before `_derive_bears_on_layer`
    (so each SourceSnapshot's `bears_on` edge exists for closure); `source_changes`
    threaded into the freshness layer; the `freshness_enabled` gate intact.
    """
    dataset = emit.dataset
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    if source_snapshots is not None:
        emit_source_snapshots(dataset, source_snapshots)

    _derive_bears_on_layer(
        dataset,
        kind_class=emit.kind_class,
        pre_registration_targets=emit.pre_registration_targets,
        eligible_code_files=_eligible_code_files(sources),
    )
    _derive_patch_membership_layer(dataset, sources=sources)
    emit_dataset_independence_records(
        provenance,
        derive_dataset_independence_records(knowledge, provenance),
    )
    # Dataset-QA layer reuses dependence resolution, so it MUST run after the independence
    # records are emitted.
    emit_dataset_qa_layer(knowledge, provenance, sources)
    if sources.freshness_enabled:
        entity_meta = _build_entity_meta(sources, emit.kind_class)
        source_changes = source_snapshots.source_changes if source_snapshots is not None else {}
        _derive_freshness_layer(
            dataset, entities=entity_meta, today=_date.today(), source_changes=source_changes
        )


def _build_dataset_from_sources(
    sources: ProjectSources,
    *,
    source_snapshots: SourceSnapshotResult | None = None,
    archive_active: dict | None = None,
) -> Dataset:
    """Build the in-memory rdflib Dataset that `materialize_graph` would write.

    Composes the Emit phase (`_emit_phase`) and the Derive phase (`_derive_phase`).
    Pure: takes `ProjectSources`, returns a populated `Dataset`, never touches the
    filesystem. When `source_snapshots` is provided, the snapshot layer is emitted
    ahead of `_derive_bears_on_layer`; when None, no snapshot layer is emitted
    (pre-Slice-B behavior). `archive_active` (active archived-id index) is threaded
    into the Emit phase so archived-ref edges + tombstone stubs are materialized.
    Used by both `materialize_graph` (writes to disk) and the
    `propagate_freshness_in_memory` sweep (discards the dataset).
    """
    emit = _emit_phase(sources, archive_active=archive_active)
    _derive_phase(emit, sources=sources, source_snapshots=source_snapshots)
    return emit.dataset


def _preflight_migration(project_root: Path) -> None:
    """Project-root preflight, materialize-only: block on unmigrated data-packages.

    Scans `doc/data-packages/` for active (non-superseded) legacy data-package
    entities and raises RuntimeError if any remain. Not a phase and outside
    `stop_after`: the audit path never runs this.
    """
    from science_model.frontmatter import parse_frontmatter

    unmigrated: list[str] = []
    dp_dir = project_root / "doc" / "data-packages"
    if dp_dir.exists():
        for md in dp_dir.rglob("*.md"):
            result = parse_frontmatter(md)
            fm = result[0] if result else {}
            if fm.get("type") == "data-package" and fm.get("status") != "superseded":
                unmigrated.append(str(fm.get("id", md.stem)))
    if unmigrated:
        slugs = ", ".join(sorted(unmigrated))
        raise RuntimeError(
            f"unmigrated data-package entities: {slugs}. "
            f"Run `science data-package migrate <slug>` to split each into "
            f"derived dataset(s) + research-package."
        )


def _audit_phase(sources: ProjectSources) -> tuple[list[AuditRow], bool]:
    """Audit phase: the single `audit_project_sources` call site."""
    return audit_project_sources(sources)


def _write_phase(dataset: Dataset, trig_path: Path) -> Path:
    """Write phase: persist the dataset to `trig_path`."""
    trig_path.parent.mkdir(parents=True, exist_ok=True)
    save_graph_dataset(dataset, trig_path)
    return trig_path


def _compile(
    project_root: Path,
    *,
    stop_after: _Literal["audit"] | None = None,
    strict: bool = True,
) -> CompilationResult:
    """Run the source-compiler phases: Load -> Audit -> Emit -> Derive -> Write.

    `stop_after="audit"` returns after the audit phase without gating, emitting,
    or writing (the `materialization_audit` projection). A full run hard-gates on
    audit failures (the `materialize_graph` projection). The project-root preflight
    is materialize-only and lives outside `stop_after`; `strict` is threaded to it
    and `strict=False` suppresses it (matching the old `materialize_graph(strict=...)`).
    """
    project_root = project_root.resolve()

    # Project-root preflight, materialize-only: only when producing output.
    if stop_after is None and strict:
        _preflight_migration(project_root)

    sources = load_project_sources(project_root, strict_identity=False)
    audit_rows, has_failures = _audit_phase(sources)

    if stop_after == "audit":
        return CompilationResult(
            sources=sources,
            audit_rows=audit_rows,
            has_failures=has_failures,
            dataset=None,
            trig_path=None,
        )

    if has_failures:
        details = "; ".join(
            f"{row['source']} {row['field']} -> {row['target']}"
            for row in audit_rows
            if row["status"] == "fail"
        )
        raise ValueError(f"Cannot materialize graph with unresolved references: {details}")

    trig_path = project_root / DEFAULT_GRAPH_PATH
    # Snapshot OBSERVATION is compiler/provenance state and runs UNCONDITIONALLY — it is not
    # gated on freshness_enabled. Gating it would stop persisting SourceSnapshot provenance
    # when freshness is off and lose baseline continuity, so re-enabling freshness later would
    # miss every intervening content change. Only the freshness-STATE derivation (inside
    # `_derive_phase`, the `if sources.freshness_enabled` block) is gated.
    snapshots = compute_source_snapshots(sources, prior_graph_path=trig_path, today=_date.today())
    from science_tool.archive import load_archive_index

    archive_active = load_archive_index(project_root).active_by_id
    dataset = _build_dataset_from_sources(sources, source_snapshots=snapshots, archive_active=archive_active)
    trig_path = _write_phase(dataset, trig_path)

    return CompilationResult(
        sources=sources,
        audit_rows=audit_rows,
        has_failures=has_failures,
        dataset=dataset,
        trig_path=trig_path,
    )


def materialize_graph(project_root: Path, *, strict: bool = True) -> Path:
    """Build `knowledge/graph.trig` deterministically from project sources.

    When `strict=True` (the default), the project-root preflight raises
    RuntimeError if any legacy data-package entities have not yet been migrated
    via `science data-package migrate`.
    """
    result = _compile(project_root, strict=strict)
    assert result.trig_path is not None  # a full compile always writes
    return result.trig_path


def materialization_audit(project_root: Path) -> tuple[list[dict[str, str]], bool]:
    """Audit a project root for unresolved canonical references."""
    result = _compile(project_root, stop_after="audit")
    audit_rows = [
        {
            "check": row["check"],
            "status": row["status"],
            "source": row["source"],
            "field": row["field"],
            "target": row["target"],
            "details": row["details"],
        }
        for row in result.audit_rows
    ]
    return audit_rows, result.has_failures


def _add_entity(
    *,
    entity: Entity,
    knowledge,
    provenance,
    overlay_paths: dict[str, str] | None = None,
    external_reference_ids: set[str] | None = None,
) -> None:
    uri = _entity_uri(entity.canonical_id)
    knowledge.add((uri, RDF.type, SCI_NS[_kind_class_name(entity.kind)]))
    knowledge.add((uri, SCHEMA_NS.identifier, Literal(entity.canonical_id)))
    knowledge.add((uri, SKOS.prefLabel, Literal(entity.title)))
    summary = getattr(entity, "summary", "")
    if isinstance(summary, str) and summary.strip():
        knowledge.add((uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((uri, SCI_NS.profile, Literal(entity.profile)))
    scope_value = "cross-project" if entity.scope is EntityScope.SHARED else "project"
    knowledge.add((uri, SCI_NS.scope, Literal(scope_value)))
    if entity.domain:
        knowledge.add((uri, SCI_NS.domain, Literal(entity.domain)))
    if entity.status:
        knowledge.add((uri, SCI_NS.projectStatus, Literal(entity.status)))
    if entity.kind == "dataset" and entity.source_class:
        knowledge.add((uri, SCI_NS.sourceClass, Literal(entity.source_class)))
    if entity.kind == "dataset" and entity.license:
        knowledge.add((uri, SCI_NS.license, Literal(entity.license)))
    # Phase 4b/4c: external-reference nodes (bib papers, curie authority rows) are
    # provenance/reference nodes, not project owners. Mark prov:Entity off the
    # DECLARED participation mode, never off kind or curie presence — a future
    # commons-OWNED protein with a curie must keep full owner treatment.
    if external_reference_ids is not None and entity.canonical_id in external_reference_ids:
        knowledge.add((uri, RDF.type, PROV.Entity))
    if entity.kind in ("paper", "book"):
        # Thin bibliographic surface (year/doi/url), emitted only when present.
        year = getattr(entity, "year", None)
        if year is not None:
            knowledge.add((uri, DCTERMS_NS.date, Literal(str(year))))
        doi = getattr(entity, "doi", "")
        if doi:
            knowledge.add((uri, SCI_NS.doi, Literal(doi)))
        url = getattr(entity, "url", "")
        if url:
            knowledge.add((uri, DCAT_NS.downloadURL, URIRef(url)))

    source_uri = _source_uri(entity.file_path)
    provenance.add((uri, PROV.wasDerivedFrom, source_uri))
    if entity.confidence is not None:
        provenance.add((uri, SCI_NS.confidence, Literal(str(entity.confidence), datatype=XSD.decimal)))
    _add_reasoning_metadata(uri=uri, provenance=provenance, entity=entity)
    if isinstance(entity, EvidenceLineEntity):
        _add_evidence_line_metadata(uri=uri, provenance=provenance, entity=entity)
    provenance.add((source_uri, RDF.type, PROV.Entity))
    provenance.add((source_uri, SCHEMA_NS.identifier, Literal(entity.file_path)))
    if overlay_paths is not None and entity.canonical_id in overlay_paths:
        overlay_path = overlay_paths[entity.canonical_id]
        overlay_uri = _source_uri(overlay_path)
        provenance.add((uri, PROV.wasDerivedFrom, overlay_uri))
        provenance.add((overlay_uri, RDF.type, PROV.Entity))
        provenance.add((overlay_uri, SCHEMA_NS.identifier, Literal(overlay_path)))


def _add_relations(
    entity: Entity,
    *,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    knowledge,
    bridge,
    provenance,
    ontology_catalogs: list[OntologyCatalog],
    ext_prefixes: frozenset[str],
    archive_active: dict | None = None,
    referenced_archived: set[str] | None = None,
) -> None:
    archive_active = archive_active or {}
    if referenced_archived is None:
        referenced_archived = set()
    entity_uri = _entity_uri(entity.canonical_id)

    if entity.kind == "structural-chain":
        _add_chain_relations(
            chain_uri=entity_uri,
            entity=entity,
            entity_index=entity_index,
            resolver=resolver,
            knowledge=knowledge,
        )

    if entity.kind == "chain-audit":
        _add_chain_audit_relations(
            audit_uri=entity_uri,
            entity=entity,
            entity_index=entity_index,
            resolver=resolver,
            knowledge=knowledge,
        )

    if isinstance(entity, EvidenceLineEntity):
        _add_evidence_line_relations(
            line_uri=entity_uri,
            entity=entity,
            entity_index=entity_index,
            resolver=resolver,
            knowledge=knowledge,
            provenance=provenance,
            ext_prefixes=ext_prefixes,
        )

    for raw_target in sorted(getattr(entity, "participants", []) or []):
        if is_metadata_reference(raw_target):
            continue
        resolution = resolver.resolve(raw_target)
        if resolution.status != "resolved":
            continue
        assert resolution.canonical_id is not None
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            continue
        knowledge.add((entity_uri, SCI_NS.hasParticipant, _entity_uri(target.canonical_id)))

    for raw_target in sorted(getattr(entity, "propositions", []) or []):
        if is_metadata_reference(raw_target):
            continue
        resolution = resolver.resolve(raw_target)
        if resolution.status != "resolved":
            continue
        assert resolution.canonical_id is not None
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            continue
        knowledge.add((entity_uri, SCI_NS.hasProposition, _entity_uri(target.canonical_id)))

    for raw_target, role in _iter_membership_refs(entity):
        # `meta:`/`spec:` are the project-wide annotation-only escape hatch
        # (is_metadata_reference, sources.py): intentional pointers excluded from
        # KG materialization everywhere, NOT bundle memberships. They are skipped,
        # not rejected — membership semantics apply only to real entity refs.
        if is_metadata_reference(raw_target):
            continue
        # Loud-fail: a discusses frame MUST resolve (spec §5). A typo'd or dangling
        # frame is a hard error, never a silently dropped membership, because graph
        # audit does not currently cover PropositionEntity.discusses.
        resolution = resolver.resolve(raw_target, allow_cross_kind_fallback=True)
        if resolution.status != "resolved" or resolution.canonical_id is None:
            raise ValueError(
                f"{entity.canonical_id} discusses {raw_target!r}, which does not resolve to a "
                "known entity; a discusses frame must resolve to a bundle (spec §5)."
            )
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            raise ValueError(
                f"{entity.canonical_id} discusses {resolution.canonical_id!r}, which resolved but "
                "is missing from the entity index; cannot emit membership (spec §5)."
            )
        frame_uri = _entity_uri(target.canonical_id)
        # Loud-fail: a discusses frame must be a bundle (hypothesis/mechanism) (spec §5 rule 2).
        frame_kind = resolution.canonical_id.split(":", 1)[0]
        if frame_kind not in ("hypothesis", "mechanism"):
            raise ValueError(
                f"{entity.canonical_id} discusses {resolution.canonical_id!r}, which is a "
                f"{frame_kind!r}, not a bundle (hypothesis/mechanism); membership roles are "
                "only valid on bundle frames (spec §5)."
            )
        # 1) Plain triple, emitted verbatim — annotate, never replace (spec §5).
        knowledge.add((entity_uri, CITO_NS.discusses, frame_uri))
        # 3) BundleMembership plumbing node carrying the role.
        membership_uri = _membership_uri(entity.canonical_id, resolution.canonical_id)
        knowledge.add((membership_uri, RDF.type, SCI_NS.BundleMembership))
        knowledge.add((membership_uri, SCI_NS.membershipProposition, entity_uri))
        knowledge.add((membership_uri, SCI_NS.membershipFrame, frame_uri))
        knowledge.add((membership_uri, SCI_NS.membershipRole, Literal(role.value)))

    for raw_target in sorted(entity.related):
        if is_external_reference(raw_target, known_prefixes=ext_prefixes):
            _link_external_term(entity_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)
            continue
        if is_metadata_reference(raw_target):
            continue

        resolution = resolver.resolve(raw_target, allow_cross_kind_fallback=True, allow_tag=True)
        if resolution.status != "resolved":
            continue
        assert resolution.canonical_id is not None
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            archived_uri = _archived_uri_if_active(resolution.canonical_id, archive_active, referenced_archived)
            if archived_uri is not None:
                akind = archive_active[resolution.canonical_id].kind
                predicate = (
                    SCI_NS.tests
                    if entity.kind == "task" and akind in {"hypothesis", "question"}
                    else SKOS.related
                )
                knowledge.add((entity_uri, predicate, archived_uri))
            continue

        target_uri = _entity_uri(target.canonical_id)
        predicate = (
            SCI_NS.tests if entity.kind == "task" and target.kind in {"hypothesis", "question"} else SKOS.related
        )
        knowledge.add((entity_uri, predicate, target_uri))

    # Inquiry `target:` frontmatter → sci:target. The CLI mutation path is the
    # only other writer of this edge; doc-authored inquiries set it here so the
    # target_exists graph audit can resolve a target node.
    if entity.kind == "inquiry":
        raw_inquiry_target = getattr(entity, "target", None)
        if raw_inquiry_target and not is_metadata_reference(raw_inquiry_target):
            resolution = resolver.resolve(raw_inquiry_target, allow_cross_kind_fallback=True)
            if resolution.status == "resolved" and resolution.canonical_id is not None:
                target = entity_index.get(resolution.canonical_id)
                if target is not None:
                    knowledge.add((entity_uri, SCI_NS.target, _entity_uri(target.canonical_id)))

    # `blocked_by` lives on ProjectEntity; defensive getattr for bare Entity instances.
    for raw_target in sorted(getattr(entity, "blocked_by", []) or []):
        if is_metadata_reference(raw_target):
            continue
        resolution = resolver.resolve(raw_target)
        if resolution.status != "resolved":
            continue
        assert resolution.canonical_id is not None
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            continue
        knowledge.add((entity_uri, SCI_NS.blockedBy, _entity_uri(target.canonical_id)))

    for raw_target in sorted(entity.ontology_terms):
        _link_external_term(entity_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)

    for raw_target in sorted(entity.same_as):
        if is_metadata_reference(raw_target):
            continue
        if is_external_reference(raw_target, known_prefixes=ext_prefixes):
            _link_same_as_external(entity_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)
            continue
        # Internal alias: another project entity asserts equivalence with this one.
        resolution = resolver.resolve(raw_target)
        if resolution.status != "resolved":
            continue
        assert resolution.canonical_id is not None
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            continue
        knowledge.add((entity_uri, SKOS.exactMatch, _entity_uri(target.canonical_id)))

    for raw_target in sorted(entity.source_refs):
        if raw_target.startswith("annotation:"):
            provenance.add((entity_uri, PROV.wasDerivedFrom, _annotation_uri(raw_target)))
            continue
        if is_bibliography_reference(raw_target):
            continue
        if is_external_reference(raw_target, known_prefixes=ext_prefixes):
            _link_external_term(entity_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)
            continue
        if is_metadata_reference(raw_target):
            continue
        resolution = resolver.resolve(raw_target, allow_cross_kind_fallback=True)
        if resolution.status != "resolved":
            continue
        assert resolution.canonical_id is not None
        target = entity_index.get(resolution.canonical_id)
        if target is None:
            archived_uri = _archived_uri_if_active(resolution.canonical_id, archive_active, referenced_archived)
            if archived_uri is not None:
                provenance.add((entity_uri, PROV.wasDerivedFrom, archived_uri))
            continue
        provenance.add((entity_uri, PROV.wasDerivedFrom, _entity_uri(target.canonical_id)))

    for raw_target in sorted(getattr(entity, "evidence_refs", []) or []):
        if is_bibliography_reference(raw_target):
            continue
        if is_external_reference(raw_target, known_prefixes=ext_prefixes):
            _link_external_term(entity_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)
            continue
        if is_metadata_reference(raw_target):
            continue
        resolution = resolver.resolve(raw_target, allow_cross_kind_fallback=True)
        if resolution.status == "resolved":
            assert resolution.canonical_id is not None
            target = entity_index.get(resolution.canonical_id)
            if target is None:
                continue
            provenance.add((entity_uri, PROV.wasDerivedFrom, _entity_uri(target.canonical_id)))
            continue
        if _is_cross_project_address(raw_target):
            provenance.add((entity_uri, PROV.wasDerivedFrom, _address_uri(raw_target)))
            continue


def _add_chain_relations(
    *,
    chain_uri: URIRef,
    entity: Entity,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    knowledge,
) -> None:
    link_entities = [
        _canonical_entity(raw_ref, entity_index=entity_index, resolver=resolver)
        for raw_ref in (getattr(entity, "chain", None) or [])
    ]
    if not link_entities:
        return

    seen_canonical_links: dict[str, str] = {}
    for raw_ref, link_entity in zip(getattr(entity, "chain", None) or [], link_entities, strict=True):
        previous_raw_ref = seen_canonical_links.get(link_entity.canonical_id)
        if previous_raw_ref is not None:
            raise ValueError(
                "duplicate canonical chain link: "
                f"{previous_raw_ref!r} and {raw_ref!r} both resolve to {link_entity.canonical_id} "
                f"in {entity.file_path}"
            )
        seen_canonical_links[link_entity.canonical_id] = raw_ref

    relation_kind = _profile_relation_for_predicate(SCI_NS.hasLink)
    for raw_ref, link_entity in zip(getattr(entity, "chain", None) or [], link_entities, strict=True):
        relation = SourceRelation(
            subject=entity.canonical_id,
            predicate="sci:hasLink",
            object=raw_ref,
            source_path=entity.file_path,
        )
        _validate_authored_relation_endpoint(
            relation,
            relation_kind=relation_kind,
            subject_entity=entity,
            object_entity=link_entity,
        )

    link_uris = [_entity_uri(link_entity.canonical_id) for link_entity in link_entities]
    for link_uri in link_uris:
        knowledge.add((chain_uri, SCI_NS.hasLink, link_uri))

    sequence_nodes = [_chain_sequence_uri(entity.canonical_id, index) for index in range(len(link_uris))]
    head = sequence_nodes[0]
    knowledge.add((chain_uri, SCI_NS.linkSequence, head))
    for index, link_uri in enumerate(link_uris):
        node = sequence_nodes[index]
        rest = RDF.nil if index == len(link_uris) - 1 else sequence_nodes[index + 1]
        knowledge.add((node, RDF.first, link_uri))
        knowledge.add((node, RDF.rest, rest))


def _add_chain_audit_relations(
    *,
    audit_uri: URIRef,
    entity: Entity,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    knowledge,
) -> None:
    raw_chain = getattr(entity, "audits", None)
    if raw_chain is None:
        return
    chain_entity = _canonical_entity(raw_chain, entity_index=entity_index, resolver=resolver)
    relation = SourceRelation(
        subject=entity.canonical_id,
        predicate="sci:audits",
        object=raw_chain,
        source_path=entity.file_path,
    )
    _validate_authored_relation_endpoint(
        relation,
        relation_kind=_profile_relation_for_predicate(SCI_NS.audits),
        subject_entity=entity,
        object_entity=chain_entity,
    )
    chain_uri = _entity_uri(chain_entity.canonical_id)
    knowledge.add((audit_uri, SCI_NS.audits, chain_uri))


def _chain_sequence_uri(canonical_id: str, index: int) -> URIRef:
    kind, slug = canonical_id.split(":", 1)
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}/link-sequence/{index}"])


def _add_evidence_line_relations(
    *,
    line_uri: URIRef,
    entity: EvidenceLineEntity,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    knowledge,
    provenance,
    ext_prefixes: frozenset[str],
) -> None:
    """Emit cito:supports/disputes edge (→ knowledge) and prov:wasDerivedFrom source (→ provenance).

    Staged lines (belief_eligible=False) are silently skipped — they must not enter
    the belief/knowledge graph.
    """
    if not entity.belief_eligible:
        return
    resolution = resolver.resolve(entity.target, allow_cross_kind_fallback=True)
    if resolution.status == "resolved" and resolution.canonical_id is not None:
        target_entity = entity_index.get(resolution.canonical_id)
        if target_entity is not None:
            predicate = CITO_NS.supports if entity.stance == EvidenceStance.SUPPORTS else CITO_NS.disputes
            knowledge.add((line_uri, predicate, _entity_uri(target_entity.canonical_id)))

    raw_source = entity.source
    if raw_source is not None:
        if is_bibliography_reference(raw_source):
            pass  # bibliography refs are not resolved to entity URIs
        elif is_external_reference(raw_source, known_prefixes=ext_prefixes):
            pass  # external refs skipped for provenance (not project entities)
        elif is_metadata_reference(raw_source):
            pass  # meta: refs skipped
        else:
            resolution = resolver.resolve(raw_source, allow_cross_kind_fallback=True)
            if resolution.status == "resolved" and resolution.canonical_id is not None:
                source_entity = entity_index.get(resolution.canonical_id)
                if source_entity is not None:
                    provenance.add((line_uri, PROV.wasDerivedFrom, _entity_uri(source_entity.canonical_id)))


def _add_evidence_line_metadata(*, uri: URIRef, provenance, entity: EvidenceLineEntity) -> None:
    """Emit evidence-line-only provenance metadata.

    Does NOT re-emit evidence_role, independence_group, or measurement_model — those
    are already handled by _add_reasoning_metadata.

    Staged lines (belief_eligible=False) are silently skipped — quant scalar
    predicates must not feed belief aggregation for ungrounded staged lines.
    """
    if not entity.belief_eligible:
        return
    scalar_predicates: dict[str, object] = {
        "strength": SCI_NS.evidenceStrength,
        "independence": SCI_NS.evidenceIndependence,
        "dispute_scope": SCI_NS.disputeScope,
        "shared_dataset": SCI_NS.sharedDataset,
        "shared_lab": SCI_NS.sharedLab,
        "shared_platform": SCI_NS.sharedPlatform,
        "shared_cohort": SCI_NS.sharedCohort,
        "evidence_type": SCI_NS.evidenceType,
    }
    for field, predicate in scalar_predicates.items():
        value = getattr(entity, field, None)
        if value is not None:
            provenance.add((uri, predicate, Literal(str(value))))

    quant = getattr(entity, "quantitative_result", None)
    if quant is not None:
        # Typed posterior summary (Task 3a) — coerce each present sub-field to a
        # typed Literal so the belief layer can read sign(beta) and prob_sign.
        if quant.beta is not None:
            provenance.add((uri, SCI_NS.quantBeta, Literal(quant.beta)))
        if quant.prob_sign is not None:
            provenance.add((uri, SCI_NS.quantProbSign, Literal(quant.prob_sign)))
        if quant.hdi is not None and len(quant.hdi) == 2:
            provenance.add((uri, SCI_NS.quantHdiLow, Literal(quant.hdi[0])))
            provenance.add((uri, SCI_NS.quantHdiHigh, Literal(quant.hdi[1])))


def _pre_registration_commitment_targets(
    sources: ProjectSources,
    *,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
) -> dict[URIRef, list[URIRef]]:
    """Resolve pre-registration commitment targets for bears_on derivation.

    When `commits_to:` is present, it overrides `related:`. An explicit empty
    list means "derive no pre-reg bears_on edges".
    """
    targets_by_pre_registration: dict[URIRef, list[URIRef]] = {}
    ext_prefixes = external_prefixes(sources.ontology_catalogs)
    for entity in sources.entities:
        if entity.kind != "pre-registration":
            continue
        raw_targets = entity.commits_to if entity.commits_to is not None else entity.related
        resolved_targets: list[URIRef] = []
        for raw_target in sorted(raw_targets):
            if is_external_reference(raw_target, known_prefixes=ext_prefixes):
                continue
            if is_metadata_reference(raw_target):
                continue
            resolution = resolver.resolve(raw_target, allow_cross_kind_fallback=True, allow_tag=True)
            if resolution.status != "resolved":
                continue
            assert resolution.canonical_id is not None
            target = entity_index.get(resolution.canonical_id)
            if target is None:
                continue
            resolved_targets.append(_entity_uri(target.canonical_id))
        targets_by_pre_registration[_entity_uri(entity.canonical_id)] = resolved_targets
    return targets_by_pre_registration


def _add_produced_by_edges(
    sources: ProjectSources,
    *,
    entity_index: dict[str, Entity],
    knowledge,
) -> None:
    """Materialize `sci:producedBy` from datasets' code-only `produced_by` field.

    Lenient: a ref that does not resolve to a registered code-file entity is
    skipped (surfaced by the `code.produced-by-unresolved` validate check),
    never a hard-fail — preserving the fragility firewall. Not routed through
    `audit_project_sources`.
    """
    for entity in sources.entities:
        if entity.kind not in ("dataset", "data-package"):
            continue  # produced_by is a data-artifact field (relation source kinds)
        for ref in getattr(entity, "produced_by", []) or []:
            target = entity_index.get(ref)
            if target is None or target.kind != "code-file":
                continue
            knowledge.add((_entity_uri(entity.canonical_id), SCI_NS.producedBy, _entity_uri(target.canonical_id)))


def _add_sub_cohort_edges(sources: ProjectSources, *, resolver: ReferenceResolver, knowledge) -> None:
    """Materialize sci:subCohortOf edges from dataset.parent_dataset into the knowledge graph.

    URIs must match usage-fact dataset URIs (minted by `project_entity_uri`) so downstream
    B2 lineage grouping joins correctly.
    """
    for child_id, parent_ref in sources.dataset_parents.items():
        child = project_entity_uri(child_id)
        parent = project_entity_uri(_resolve_dataset_usage_ref(parent_ref, resolver))
        knowledge.add((child, SCI_NS.subCohortOf, parent))


def _add_dataset_usage_edges(sources: ProjectSources, *, resolver: ReferenceResolver, provenance) -> None:
    for entity in sources.entities:
        for record in usage_records_for_entity(
            entity,
            resolve_dataset_ref=lambda raw_ref: _resolve_dataset_usage_ref(raw_ref, resolver),
        ):
            add_usage_record_to_graph(record, provenance)
    for record in _geneset_usage_records(sources, resolver=resolver):
        add_usage_record_to_graph(record, provenance)


def _resource_uri(dataset_canonical_id: str, resource: DatasetResource) -> URIRef:
    """A deterministic distribution URI under the dataset entity (§B4 resource node)."""
    slug = resource.name or resource.path
    return URIRef(f"{_entity_uri(dataset_canonical_id)}/resource/{quote(slug, safe='')}")


def _add_dataset_resource_edges(sources: ProjectSources, *, datasets) -> None:
    """Materialize each dataset datapackage's `resources` as DCAT distributions about the
    dataset entity (design §B4): the datapackage compiles into resource/prov triples, never
    a second owner. Resource nodes are dual-typed dcat:Distribution + prov:Entity and live
    in the `datasets` named graph. The reader is lenient on absence (a dataset with no
    datapackage, or a datapackage with no/hash-less resources, contributes no distributions
    / a distribution without a hash) but strict on malformation: a declared-but-broken
    resource raises DatasetResourceError, which propagates to fail the build (fail early).
    """
    project_root = Path(sources.project_root)
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        rel = dataset_datapackage_path(
            entity_adapter=sources.entity_source_adapters.get(entity.canonical_id),
            entity_path=entity.file_path,
            datapackage_rel=sources.dataset_datapackages.get(entity.canonical_id),
        )
        if rel is None:
            continue
        dp_path = rel if rel.is_absolute() else project_root / rel
        if not dp_path.is_file():
            continue
        dataset_uri = _entity_uri(entity.canonical_id)
        for resource in read_dataset_resources(dp_path):
            r_uri = _resource_uri(entity.canonical_id, resource)
            datasets.add((dataset_uri, DCAT_NS.distribution, r_uri))
            datasets.add((r_uri, RDF.type, DCAT_NS.Distribution))
            datasets.add((r_uri, RDF.type, PROV.Entity))
            datasets.add((r_uri, DCTERMS_NS.identifier, Literal(resource.name or resource.path)))
            if resource.format:
                # NB: DCTERMS_NS.format would resolve to str.format (Namespace subclasses
                # str), so use item access to get the URIRef predicate.
                datasets.add((r_uri, DCTERMS_NS["format"], Literal(resource.format)))
            if resource.bytes is not None:
                datasets.add((r_uri, DCAT_NS.byteSize, Literal(resource.bytes, datatype=XSD.nonNegativeInteger)))
            if resource.hash:
                datasets.add((r_uri, SCI_NS.resourceHash, Literal(resource.hash)))
            if resource.source is not None:
                if resource.source.type == "url":
                    datasets.add((r_uri, DCAT_NS.downloadURL, URIRef(resource.source.ref)))
                else:
                    datasets.add((r_uri, DCTERMS_NS.source, Literal(f"{resource.source.type}:{resource.source.ref}")))


def _resolve_dataset_usage_ref(raw_ref: str, resolver: ReferenceResolver) -> str:
    resolution = resolver.resolve(raw_ref)
    if resolution.status != "resolved" or resolution.canonical_id is None:
        raise ValueError(f"unresolved dataset usage reference: {raw_ref}")
    if not resolution.canonical_id.startswith("dataset:"):
        raise ValueError(
            f"dataset usage reference resolved to non-dataset entity: {raw_ref} -> {resolution.canonical_id}"
        )
    return resolution.canonical_id


def _geneset_usage_records(sources: ProjectSources, *, resolver: ReferenceResolver):
    project_root = Path(sources.project_root)
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        fm = dataset_geneset_frontmatter(
            project_root,
            entity.file_path,
            entity_adapter=sources.entity_source_adapters.get(entity.canonical_id),
            datapackage_rel=sources.dataset_datapackages.get(entity.canonical_id),
        )
        if fm is None:
            continue
        raw_rows = read_member_rows(project_root, fm)
        if raw_rows is None:
            raise RuntimeError(f"{entity.canonical_id}: members_resource unavailable for graph materialization")
        if isinstance(raw_rows, Exception):
            raise RuntimeError(f"{entity.canonical_id}: members_resource malformed: {raw_rows}") from raw_rows
        try:
            rows = parse_geneset_rows(raw_rows)
        except GenesetCollectionError as exc:
            raise RuntimeError(f"{entity.canonical_id}: members_resource malformed: {exc}") from exc
        yield from usage_records_for_geneset_rows(
            collection_id=entity.canonical_id,
            # Cite the resource's real source (the datapackage), not whichever owner
            # won the column — fm["_path"] is the datapackage for a promoted owner and
            # is identical to entity.file_path for an orphan datapackage (no change).
            source_path=str(fm["_path"]),
            rows=rows,
            resolve_dataset_ref=lambda raw_ref: _resolve_dataset_usage_ref(raw_ref, resolver),
        )


def _eligible_code_files(sources: ProjectSources) -> set[URIRef]:
    """Code-file URIs whose edits propagate freshness: decision-bearing, fail-closed
    (un-annotated executable counts), exempting exploratory/retired."""
    eligible: set[URIRef] = set()
    for entity in sources.entities:
        if entity.kind != "code-file":
            continue
        if (entity.status or "") in ORPHAN_GATING_EXEMPT_STATUSES:
            continue
        declared = getattr(entity, "decision_bearing", None)
        # Fail-closed: an un-annotated *executable* propagates. This is intentionally
        # broader than classify_code_file()'s orphan rule (which keys off the narrower
        # "orphaned-executable" classification) — propagation should err toward
        # over-including, the orphan gate toward not over-flagging.
        effective = declared if declared is not None else getattr(entity, "executable", False)
        if effective:
            eligible.add(_entity_uri(entity.canonical_id))
    return eligible


def _link_external_term(
    source_uri: URIRef, raw_target: str, *, bridge, ontology_catalogs: list[OntologyCatalog]
) -> None:
    target_uri = _external_uri(raw_target)
    bridge.add((source_uri, SCI_NS.about, target_uri))
    _register_external_term(target_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)


def _link_same_as_external(
    source_uri: URIRef, raw_target: str, *, bridge, ontology_catalogs: list[OntologyCatalog]
) -> None:
    """Assert that a project entity is the same concept as an external CURIE.

    Emits ``skos:exactMatch`` (rather than ``sci:about``) to express identity
    rather than association — e.g. ``topic:PHF19`` ↔ ``UniProtKB:Q5T6S3``.
    """
    target_uri = _external_uri(raw_target)
    bridge.add((source_uri, SKOS.exactMatch, target_uri))
    _register_external_term(target_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)


def _register_external_term(
    target_uri: URIRef, raw_target: str, *, bridge, ontology_catalogs: list[OntologyCatalog]
) -> None:
    bridge.add((target_uri, RDF.type, SCI_NS.ExternalTerm))
    bridge.add((target_uri, SCHEMA_NS.identifier, Literal(raw_target)))
    bridge.add((target_uri, SCI_NS.profile, Literal(_external_profile(raw_target, ontology_catalogs))))


def _add_authored_relation(
    relation: SourceRelation,
    *,
    dataset: Dataset,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    bridge,
    ontology_catalogs: list[OntologyCatalog],
    ext_prefixes: frozenset[str],
    kind_class: dict[str, EntityClass] | None = None,
    archive_active: dict | None = None,
    referenced_archived: set[str] | None = None,
) -> None:
    del kind_class  # endpoint validation is now driven by the relation profile
    archive_active = archive_active or {}
    if referenced_archived is None:
        referenced_archived = set()
    graph = dataset.graph(_graph_uri(relation.graph_layer))
    subject_entity = _canonical_entity(relation.subject, entity_index=entity_index, resolver=resolver)
    subject_uri = _entity_uri(subject_entity.canonical_id)
    predicate_uri = _resolve_relation_term(relation.predicate)

    object_entity: Entity | _ArchivedEndpoint | None = None
    if is_external_reference(relation.object, known_prefixes=ext_prefixes):
        object_uri = _external_uri(relation.object)
        _register_external_term(object_uri, relation.object, bridge=bridge, ontology_catalogs=ontology_catalogs)
    else:
        obj_res = resolver.resolve(relation.object)
        obj_cid = obj_res.canonical_id if obj_res.status == "resolved" else None
        if obj_cid is not None and obj_cid not in entity_index and obj_cid in archive_active:
            # Resolved-but-not-live: an active archived id. Materialize the edge to its
            # canonical URI and validate the endpoint by the archived row's kind.
            arow = archive_active[obj_cid]
            object_uri = _entity_uri(obj_cid)
            object_entity = _ArchivedEndpoint(canonical_id=obj_cid, kind=arow.kind or "")
            referenced_archived.add(obj_cid)
        else:
            object_entity = _canonical_entity(relation.object, entity_index=entity_index, resolver=resolver)
            object_uri = _entity_uri(object_entity.canonical_id)

    relation_kind = _profile_relation_for_predicate(predicate_uri)
    _validate_authored_relation_endpoint(
        relation,
        relation_kind=relation_kind,
        subject_entity=subject_entity,
        object_entity=object_entity,  # type: ignore[arg-type]
    )

    graph.add((subject_uri, predicate_uri, object_uri))


_AMENDMENT_RELATION_PREDICATES = frozenset({SCI_NS.amends, SCI_NS.supersedes})


def _relation_name_for_error(relation_kind: RelationKind | None, predicate: str) -> str:
    if relation_kind is not None:
        return relation_kind.name
    return predicate


def _canonical_entity(
    raw_value: str,
    *,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
) -> Entity:
    resolution = resolver.resolve(raw_value)
    entity = entity_index.get(resolution.canonical_id or "")
    if entity is None:
        raise ValueError(f"Unknown canonical entity: {raw_value}")
    return entity


def _profile_relation_for_predicate(predicate_uri: URIRef) -> RelationKind | None:
    for relation_kind in CORE_PROFILE.relation_kinds:
        if _resolve_relation_term(relation_kind.predicate) == predicate_uri:
            return relation_kind
    return None


def _validate_authored_relation_endpoint(
    relation: SourceRelation,
    *,
    relation_kind: RelationKind | None,
    subject_entity: Entity,
    object_entity: Entity | None,
) -> None:
    if relation_kind is None:
        return
    if object_entity is None:
        if relation_kind.target_kinds or relation_kind.allowed_kind_pairs:
            raise ValueError(
                "invalid authored relation endpoint: "
                f"{relation.subject} {relation.predicate} ({_relation_name_for_error(relation_kind, relation.predicate)}) "
                f"{relation.object} in {relation.source_path} "
                "targets an external reference but the predicate requires a project entity"
            )
        return
    if object_entity is not None and subject_entity.canonical_id == object_entity.canonical_id:
        raise ValueError(
            "self-referential authored relation: "
            f"{relation.subject} {relation.predicate} ({_relation_name_for_error(relation_kind, relation.predicate)}) "
            f"{relation.object} in {relation.source_path}"
        )
    if relation_allows_kinds(relation_kind, subject_entity.kind, object_entity.kind):
        return
    raise ValueError(
        "invalid authored relation endpoint: "
        f"{relation.subject} {relation.predicate} ({_relation_name_for_error(relation_kind, relation.predicate)}) "
        f"{relation.object} in {relation.source_path} "
        f"(got {subject_entity.kind} -> {object_entity.kind})"
    )


def _display_entity_uri(uri: URIRef) -> str:
    canonical_id = canonical_id_from_entity_uri(str(uri))
    return canonical_id or str(uri)


def _validate_no_amendment_cycles(dataset: Dataset) -> None:
    adjacency: dict[URIRef, set[URIRef]] = {}
    for graph in dataset.graphs():
        for predicate in _AMENDMENT_RELATION_PREDICATES:
            for source, _, target in graph.triples((None, predicate, None)):
                if not isinstance(source, URIRef) or not isinstance(target, URIRef):
                    continue
                adjacency.setdefault(source, set()).add(target)

    visited: set[URIRef] = set()
    visiting: set[URIRef] = set()

    def visit(node: URIRef, path: list[URIRef]) -> None:
        if node in visiting:
            start = path.index(node)
            cycle = path[start:] + [node]
            cycle_text = " -> ".join(_display_entity_uri(item) for item in cycle)
            raise ValueError(f"cycle in amendment/supersession relations: {cycle_text}")
        if node in visited:
            return
        visiting.add(node)
        for target in sorted(adjacency.get(node, set()), key=str):
            visit(target, [*path, target])
        visiting.remove(node)
        visited.add(node)

    for node in sorted(adjacency, key=str):
        visit(node, [node])


def _add_binding(
    binding: SourceBinding,
    *,
    knowledge,
    provenance,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
) -> None:
    model_uri = _canonical_entity_uri(binding.model, entity_index=entity_index, resolver=resolver)
    parameter_uri = _canonical_entity_uri(binding.parameter, entity_index=entity_index, resolver=resolver)
    knowledge.add((model_uri, SCI_NS.hasParameter, parameter_uri))

    binding_uri = _binding_uri(binding)
    provenance.add((binding_uri, RDF.type, SCI_NS.ParameterBinding))
    provenance.add((binding_uri, SCI_NS.model, model_uri))
    provenance.add((binding_uri, SCI_NS.parameter, parameter_uri))
    provenance.add((binding_uri, PROV.wasDerivedFrom, _source_uri(binding.source_path)))
    provenance.add((binding_uri, SCHEMA_NS.identifier, Literal(f"{binding.model}|{binding.parameter}")))
    if binding.symbol:
        provenance.add((binding_uri, SCI_NS.symbol, Literal(binding.symbol)))
    if binding.role:
        provenance.add((binding_uri, SCI_NS.role, Literal(binding.role)))
    if binding.units_override:
        provenance.add((binding_uri, SCI_NS.unitsOverride, Literal(binding.units_override)))
    if binding.confidence is not None:
        provenance.add((binding_uri, SCI_NS.confidence, Literal(binding.confidence)))
    if binding.match_tier:
        provenance.add((binding_uri, SCI_NS.matchTier, Literal(binding.match_tier)))
    if binding.default_value is not None:
        provenance.add((binding_uri, SCI_NS.defaultValue, Literal(binding.default_value)))
    if binding.typical_range:
        for value in binding.typical_range:
            provenance.add((binding_uri, SCI_NS.typicalRangeValue, Literal(value)))
    if binding.notes:
        provenance.add((binding_uri, SCI_NS.note, Literal(binding.notes)))
    for target in binding.source_refs:
        if is_bibliography_reference(target):
            continue
        provenance.add(
            (
                binding_uri,
                PROV.wasDerivedFrom,
                _binding_reference_uri(target, entity_index=entity_index, resolver=resolver),
            )
        )


def _add_reasoning_metadata(*, uri: URIRef, provenance, entity: Entity) -> None:
    scalar_predicates = {
        "claim_layer": SCI_NS.claimLayer,
        "identification_strength": SCI_NS.identificationStrength,
        "proxy_directness": SCI_NS.proxyDirectness,
        "supports_scope": SCI_NS.supportsScope,
        "independence_group": SCI_NS.independenceGroup,
        "evidence_role": SCI_NS.evidenceRole,
        # Authored relational sign of a proposition (Task 3a). Present only on
        # PropositionEntity; getattr returns None for other kinds so they skip it.
        "polarity": SCI_NS.polarity,
    }
    for field, predicate in scalar_predicates.items():
        value = getattr(entity, field, None)
        if value is not None:
            provenance.add((uri, predicate, Literal(str(value))))

    measurement_model = getattr(entity, "measurement_model", None)
    if measurement_model is not None:
        provenance.add(
            (
                uri,
                SCI_NS.measurementModel,
                Literal(_model_to_json(measurement_model)),
            )
        )
    # `rival_model_packet` lives on ProjectEntity; defensive getattr for bare Entity instances.
    rival_packet = getattr(entity, "rival_model_packet", None)
    if rival_packet is not None:
        provenance.add(
            (
                uri,
                SCI_NS.rivalModelPacket,
                Literal(_model_to_json(rival_packet)),
            )
        )
    if getattr(entity, "composition_rule", None) is not None:
        provenance.add((uri, SCI_NS.compositionRule, Literal(entity.composition_rule.value)))
    if getattr(entity, "legacy_patch", None) is not None:
        provenance.add((uri, SCI_NS.legacyPatch, Literal(entity.legacy_patch)))
    if getattr(entity, "legacy_edge_id", None) is not None:
        provenance.add((uri, SCI_NS.legacyEdgeId, Literal(entity.legacy_edge_id)))


def _model_to_json(value: MeasurementModel | RivalModelPacket) -> str:
    return json.dumps(value.model_dump(mode="json"))


def _canonical_entity_uri(
    raw_value: str,
    *,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
) -> URIRef:
    resolution = resolver.resolve(raw_value)
    entity = entity_index.get(resolution.canonical_id or "")
    if entity is None:
        raise ValueError(f"Unknown canonical entity: {raw_value}")
    return _entity_uri(entity.canonical_id)


def _graph_uri(layer: str) -> URIRef:
    if layer not in GRAPH_LAYERS:
        raise ValueError(f"Unsupported graph layer: {layer}")
    return URIRef(PROJECT_NS[layer])


def _resolve_relation_term(value: str) -> URIRef:
    if value.startswith(("http://", "https://")):
        return URIRef(value)
    if ":" not in value:
        raise ValueError(f"Relation predicate must be a CURIE or absolute URI: {value}")

    prefix, suffix = value.split(":", 1)
    namespace = CURIE_PREFIXES.get(prefix)
    if namespace is not None:
        return URIRef(namespace[suffix])
    if prefix in PROJECT_ENTITY_PREFIXES:
        return URIRef(PROJECT_NS[f"{prefix}/{suffix}"])
    raise ValueError(f"Unknown relation predicate prefix: {prefix}")


def _entity_uri(canonical_id: str) -> URIRef:
    return entity_uri_for_ref(canonical_id)


def _annotation_uri(ref: str) -> URIRef:
    """Mint a stable project URI for an `annotation:<relpath>#<frag>` source ref.

    Bypasses entity resolution (an annotation is not an entity). Case/`/` of the relpath
    are preserved (unlike `entity_uri_for_ref`, which lowercases)."""
    body = ref.removeprefix("annotation:")
    return URIRef(PROJECT_NS[f"annotation/{body}"])


def _external_uri(raw_target: str) -> URIRef:
    if raw_target.startswith(("http://", "https://")):
        return URIRef(PROJECT_NS[f"external/url/{quote(raw_target, safe='')}"])
    if ":" not in raw_target:
        return URIRef(PROJECT_NS[f"external/term/{quote(raw_target.strip(), safe='')}"])

    prefix, suffix = raw_target.split(":", 1)
    safe_suffix = quote(suffix.strip(), safe="")
    return URIRef(PROJECT_NS[f"external/{prefix.lower()}/{safe_suffix}"])


def _address_uri(raw_target: str) -> URIRef:
    address = parse_address(raw_target)
    return URIRef(f"cancer://{address.project_id}/{address.artifact_id}")


def _is_cross_project_address(raw_target: str) -> bool:
    if not is_address(raw_target):
        return False
    prefix, _ = raw_target.split(":", 1)
    return prefix not in PROJECT_ENTITY_PREFIXES


def _binding_uri(binding: SourceBinding) -> URIRef:
    token = hashlib.sha1(
        "|".join(
            [binding.model, binding.parameter, binding.source_path, binding.symbol or "", binding.role or ""]
        ).encode("utf-8")
    ).hexdigest()[:12]
    return URIRef(PROJECT_NS[f"binding/{token}"])


def _source_uri(source_path: str) -> URIRef:
    safe_path = source_path.replace("/", "_").replace(" ", "_").lower()
    return URIRef(PROJECT_NS[f"source/{safe_path}"])


def _binding_reference_uri(
    raw_target: str,
    *,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
) -> URIRef:
    if is_external_reference(raw_target):
        return _external_uri(raw_target)
    return _canonical_entity_uri(raw_target, entity_index=entity_index, resolver=resolver)


def _kind_class_name(kind: str) -> str:
    return "".join(part.capitalize() for part in kind.replace("_", "-").split("-"))


def _external_profile(raw_target: str, ontology_catalogs: list[OntologyCatalog]) -> str:
    """Return the ontology name for a CURIE, or 'external' if no match."""
    if ":" not in raw_target:
        return "external"
    prefix, _ = raw_target.split(":", 1)
    prefix_lower = prefix.lower()
    for catalog in ontology_catalogs:
        for et in catalog.entity_types:
            if prefix_lower in {p.lower() for p in et.curie_prefixes}:
                return catalog.ontology
    return "external"


def _classify_entities(sources: ProjectSources) -> dict[str, EntityClass]:
    """Build a {URI string -> EntityClass} map from the project's entities.

    Uses the registry built by load_project_sources, which knows about profile,
    catalog, and extension kinds. Every entity in `sources.entities` was
    accepted by `registry.resolve(kind)` during loading, so kind_class lookup
    is guaranteed to succeed — let any unexpected miss raise loudly.
    """
    kind_class: dict[str, EntityClass] = {}
    for entity in sources.entities:
        uri_str = str(_entity_uri(entity.canonical_id))
        kind_class[uri_str] = sources.registry.kind_class(entity.kind)
    return kind_class


def _build_entity_meta(
    sources: ProjectSources,
    kind_class: dict[str, EntityClass],
) -> dict[str, EntityFreshnessInfo]:
    """Build the per-entity metadata dict consumed by derive_freshness."""
    entity_meta: dict[str, EntityFreshnessInfo] = {}
    for entity in sources.entities:
        uri_str = str(_entity_uri(entity.canonical_id))
        entity_meta[uri_str] = {
            "kind_class": kind_class[uri_str],
            "last_reviewed": entity.review_state.last_reviewed if entity.review_state else None,
            "created": entity.created,
            "updated": entity.updated,
            "review_horizon_days": (entity.review_state.review_horizon_days if entity.review_state else None),
        }
    return entity_meta


PATCH_MEMBERSHIP_POLICY_VERSION = "local-closure-v1"


def _derive_patch_membership_layer(dataset: Dataset, *, sources: ProjectSources) -> None:
    """Derive per-patch named graphs with reified PatchMembership nodes.

    Runs after `_derive_bears_on_layer` because patch closure reads the
    precomputed `sci:bearsOn` layer. No-ops when no PatchDefinitionEntity is
    present in sources.

    Inquiry views are emitted first so that any minted assumption/transformation
    nodes are typed in the graph before the deriver resolves memberKind.
    """
    patch_definitions = [
        entity for entity in sources.entities if isinstance(entity, PatchDefinitionEntity)
    ]
    if not patch_definitions:
        return
    emit_inquiry_views(dataset, patch_definitions)
    result = derive_patch_memberships(
        dataset,
        patch_definitions,
        policy_version=PATCH_MEMBERSHIP_POLICY_VERSION,
    )
    emit_patch_memberships(dataset, patch_definitions, result.records)


def _derive_bears_on_layer(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
    pre_registration_targets: dict[URIRef, list[URIRef]],
    eligible_code_files: set[URIRef],
) -> None:
    """Derive sci:bearsOn triples (typed-edge + provenance + produced_by + closure).

    Always runs regardless of freshness.enabled — bears_on edges are
    independently useful for dependency queries and are not part of freshness.
    """
    derive_bears_on_from_typed_edges(dataset, kind_class=kind_class)
    derive_bears_on_from_chain_links(dataset)
    derive_bears_on_from_audits(dataset)
    derive_bears_on_from_pre_registrations(
        dataset,
        pre_registration_targets=pre_registration_targets,
        kind_class=kind_class,
    )
    derive_bears_on_from_provenance(dataset, kind_class=kind_class)
    derive_bears_on_from_produced_by_code(dataset, eligible_code_files=eligible_code_files)
    close_bears_on(dataset, kind_class=kind_class)


def _derive_freshness_layer(
    dataset: Dataset,
    *,
    entities: dict[str, EntityFreshnessInfo],
    today: _date,
    source_changes: dict[str, _date],
) -> None:
    """Derive freshness state triples (sci:freshnessState / sci:upstreamChangeAt / sci:triggeredBy).

    Gated on sources.freshness_enabled — skipped entirely when opt-out is active.
    `source_changes` maps SourceSnapshot node URIs to their latest SourceChange observed_on
    (the values are `datetime.date`; `date` is imported as `_date` in this file).
    """
    derive_freshness(dataset, entities=entities, today=today, source_changes=source_changes)

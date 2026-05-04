"""Deterministic graph materialization from structured project sources."""

from __future__ import annotations

import hashlib
import json
from datetime import date as _date
from pathlib import Path
from urllib.parse import quote

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD
from science_model.entities import Entity, EntityClass
from science_model.ontologies.schema import OntologyCatalog
from science_model.reasoning import MeasurementModel, RivalModelPacket

from science_tool.addressing import is_address, parse_address
from science_tool.graph.freshness import (
    EntityFreshnessInfo,
    close_bears_on,
    derive_bears_on_from_provenance,
    derive_bears_on_from_typed_edges,
    derive_freshness,
)
from science_tool.graph.migrate import audit_project_sources
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
from science_tool.graph.store import (
    CURIE_PREFIXES,
    DEFAULT_GRAPH_PATH,
    GRAPH_LAYERS,
    PROJECT_ENTITY_PREFIXES,
    PROJECT_NS,
    SCHEMA_NS,
    SCI_NS,
    save_graph_dataset,
)


def _build_dataset_from_sources(sources: ProjectSources) -> Dataset:
    """Build the in-memory rdflib Dataset that `materialize_graph` would write.

    Composes the existing emission helpers (`_add_entity`, `_add_relations`,
    `_add_authored_relation`, `_add_binding`) and the epistemic derivation
    helpers (`_classify_entities`, `_derive_bears_on_layer`,
    `_derive_freshness_layer`). Pure: takes `ProjectSources`, returns a
    populated `Dataset`. Never touches the filesystem.

    Used by both `materialize_graph` (which writes to disk) and the
    `propagate_freshness_in_memory` sweep (which discards the dataset).
    """
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    dataset.graph(PROJECT_NS["graph/causal"])
    dataset.graph(PROJECT_NS["graph/datasets"])

    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    entity_index = {entity.canonical_id: entity for entity in sources.entities}
    ext_prefixes = _EXTERNAL_PREFIXES | external_prefixes(sources.ontology_catalogs)

    for entity in sources.entities:
        _add_entity(entity=entity, knowledge=knowledge, provenance=provenance)

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
        )

    kind_class = _classify_entities(sources)

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
        )

    for binding in sources.bindings:
        _add_binding(
            binding,
            knowledge=knowledge,
            provenance=provenance,
            entity_index=entity_index,
            resolver=resolver,
        )

    _derive_bears_on_layer(dataset, kind_class=kind_class)
    if sources.freshness_enabled:
        entity_meta = _build_entity_meta(sources, kind_class)
        _derive_freshness_layer(dataset, entities=entity_meta, today=_date.today())

    return dataset


def materialize_graph(project_root: Path, *, strict: bool = True) -> Path:
    """Build `knowledge/graph.trig` deterministically from project sources.

    When `strict=True` (the default), raises RuntimeError if any legacy
    data-package entities have not yet been migrated via
    `science-tool data-package migrate`.
    """
    project_root = project_root.resolve()

    if strict:
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
                f"Run `science-tool data-package migrate <slug>` to split each into "
                f"derived dataset(s) + research-package."
            )

    sources = load_project_sources(project_root)
    rows, has_failures = audit_project_sources(sources)
    if has_failures:
        details = "; ".join(f"{row['source']} -> {row['target']}" for row in rows if row["status"] == "fail")
        msg = f"Cannot materialize graph with unresolved references: {details}"
        raise ValueError(msg)

    dataset = _build_dataset_from_sources(sources)

    trig_path = project_root / DEFAULT_GRAPH_PATH
    trig_path.parent.mkdir(parents=True, exist_ok=True)
    save_graph_dataset(dataset, trig_path)
    return trig_path


def materialization_audit(project_root: Path) -> tuple[list[dict[str, str]], bool]:
    """Audit a project root for unresolved canonical references."""
    rows, has_failures = audit_project_sources(load_project_sources(project_root.resolve()))
    audit_rows = [
        {
            "check": row["check"],
            "status": row["status"],
            "source": row["source"],
            "field": row["field"],
            "target": row["target"],
            "details": row["details"],
        }
        for row in rows
    ]
    return audit_rows, has_failures


def _add_entity(*, entity: Entity, knowledge, provenance) -> None:
    uri = _entity_uri(entity.canonical_id)
    knowledge.add((uri, RDF.type, SCI_NS[_kind_class_name(entity.kind)]))
    knowledge.add((uri, SCHEMA_NS.identifier, Literal(entity.canonical_id)))
    knowledge.add((uri, SKOS.prefLabel, Literal(entity.title)))
    summary = getattr(entity, "summary", "")
    if isinstance(summary, str) and summary.strip():
        knowledge.add((uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((uri, SCI_NS.profile, Literal(entity.profile)))
    if entity.domain:
        knowledge.add((uri, SCI_NS.domain, Literal(entity.domain)))
    if entity.status:
        knowledge.add((uri, SCI_NS.projectStatus, Literal(entity.status)))

    source_uri = _source_uri(entity.file_path)
    provenance.add((uri, PROV.wasDerivedFrom, source_uri))
    if entity.confidence is not None:
        provenance.add((uri, SCI_NS.confidence, Literal(str(entity.confidence), datatype=XSD.decimal)))
    _add_reasoning_metadata(uri=uri, provenance=provenance, entity=entity)
    provenance.add((source_uri, RDF.type, PROV.Entity))
    provenance.add((source_uri, SCHEMA_NS.identifier, Literal(entity.file_path)))


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
) -> None:
    entity_uri = _entity_uri(entity.canonical_id)

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
            continue

        target_uri = _entity_uri(target.canonical_id)
        predicate = (
            SCI_NS.tests if entity.kind == "task" and target.kind in {"hypothesis", "question"} else SKOS.related
        )
        knowledge.add((entity_uri, predicate, target_uri))

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
            continue
        provenance.add((entity_uri, PROV.wasDerivedFrom, _entity_uri(target.canonical_id)))

    for raw_target in sorted(getattr(entity, "evidence_refs", []) or []):
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
) -> None:
    graph = dataset.graph(_graph_uri(relation.graph_layer))
    subject_uri = _canonical_entity_uri(relation.subject, entity_index=entity_index, resolver=resolver)
    predicate_uri = _resolve_relation_term(relation.predicate)

    if is_external_reference(relation.object, known_prefixes=ext_prefixes):
        object_uri = _external_uri(relation.object)
        _register_external_term(object_uri, relation.object, bridge=bridge, ontology_catalogs=ontology_catalogs)
    else:
        object_uri = _canonical_entity_uri(relation.object, entity_index=entity_index, resolver=resolver)

    # Phase 1 guard: hand-authored bears_on edges may only target epistemic kinds.
    # The auto-derivation engine respects this by construction; this catches
    # human-authored mistakes at the same place we accept their structured edges.
    if predicate_uri == SCI_NS.bearsOn and kind_class is not None:
        target_class = kind_class.get(str(object_uri))
        if target_class is not None and target_class != EntityClass.EPISTEMIC:
            raise ValueError(
                f"hand-authored bears_on must target an epistemic entity: "
                f"{relation.subject} -> {relation.object} in {relation.source_path} "
                f"(target classified {target_class.value})"
            )

    graph.add((subject_uri, predicate_uri, object_uri))


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
    kind, slug = canonical_id.split(":", 1)
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}"])


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
            "review_horizon_days": (
                entity.review_state.review_horizon_days if entity.review_state else None
            ),
        }
    return entity_meta


def _derive_bears_on_layer(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
) -> None:
    """Derive sci:bearsOn triples (typed-edge + provenance + closure).

    Always runs regardless of freshness.enabled — bears_on edges are
    independently useful for dependency queries and are not part of freshness.
    """
    derive_bears_on_from_typed_edges(dataset, kind_class=kind_class)
    derive_bears_on_from_provenance(dataset, kind_class=kind_class)
    close_bears_on(dataset, kind_class=kind_class)


def _derive_freshness_layer(
    dataset: Dataset,
    *,
    entities: dict[str, EntityFreshnessInfo],
    today: _date,
) -> None:
    """Derive freshness state triples (sci:freshnessState / sci:upstreamChangeAt / sci:triggeredBy).

    Gated on sources.freshness_enabled — skipped entirely when opt-out is active.
    """
    derive_freshness(dataset, entities=entities, today=today)

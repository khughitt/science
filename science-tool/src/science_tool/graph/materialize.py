"""Deterministic graph materialization from structured project sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD
from science_model import normalize_alias
from science_model.entities import Entity
from science_model.reasoning import MeasurementModel, RivalModelPacket
from science_model.ontologies.schema import OntologyCatalog

from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import (
    SourceBinding,
    SourceRelation,
    _EXTERNAL_PREFIXES,
    build_alias_map,
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

    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    dataset.graph(PROJECT_NS["graph/causal"])
    dataset.graph(PROJECT_NS["graph/datasets"])

    alias_map = build_alias_map(sources.entities, manual_aliases=sources.manual_aliases)
    entity_index = {entity.canonical_id: entity for entity in sources.entities}
    ext_prefixes = _EXTERNAL_PREFIXES | external_prefixes(sources.ontology_catalogs)

    for entity in sources.entities:
        _add_entity(entity=entity, knowledge=knowledge, provenance=provenance)

    for entity in sources.entities:
        _add_relations(
            entity,
            entity_index=entity_index,
            alias_map=alias_map,
            knowledge=knowledge,
            bridge=bridge,
            provenance=provenance,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
        )

    for relation in sources.relations:
        _add_authored_relation(
            relation,
            dataset=dataset,
            entity_index=entity_index,
            alias_map=alias_map,
            bridge=bridge,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
        )

    for binding in sources.bindings:
        _add_binding(
            binding,
            knowledge=knowledge,
            provenance=provenance,
            entity_index=entity_index,
            alias_map=alias_map,
        )

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
    knowledge.add((uri, RDF.type, SCI_NS[_kind_class_name(entity.type.value)]))
    knowledge.add((uri, SCHEMA_NS.identifier, Literal(entity.canonical_id)))
    knowledge.add((uri, SKOS.prefLabel, Literal(entity.title)))
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
    alias_map: dict[str, str],
    knowledge,
    bridge,
    provenance,
    ontology_catalogs: list[OntologyCatalog],
    ext_prefixes: frozenset[str],
) -> None:
    entity_uri = _entity_uri(entity.canonical_id)

    for raw_target in sorted(entity.related):
        if is_external_reference(raw_target, known_prefixes=ext_prefixes):
            _link_external_term(entity_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)
            continue
        if is_metadata_reference(raw_target):
            continue

        canonical_target = normalize_alias(raw_target, alias_map)
        target = entity_index.get(canonical_target)
        if target is None:
            continue

        target_uri = _entity_uri(target.canonical_id)
        predicate = (
            SCI_NS.tests
            if entity.type.value == "task" and target.type.value in {"hypothesis", "question"}
            else SKOS.related
        )
        knowledge.add((entity_uri, predicate, target_uri))

    # `blocked_by` lives on ProjectEntity; defensive getattr for bare Entity instances.
    for raw_target in sorted(getattr(entity, "blocked_by", []) or []):
        if is_metadata_reference(raw_target):
            continue
        canonical_target = normalize_alias(raw_target, alias_map)
        target = entity_index.get(canonical_target)
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
        canonical_target = normalize_alias(raw_target, alias_map)
        target = entity_index.get(canonical_target)
        if target is None:
            continue
        knowledge.add((entity_uri, SKOS.exactMatch, _entity_uri(target.canonical_id)))

    for raw_target in sorted(entity.source_refs):
        if is_external_reference(raw_target, known_prefixes=ext_prefixes):
            _link_external_term(entity_uri, raw_target, bridge=bridge, ontology_catalogs=ontology_catalogs)
            continue
        if is_metadata_reference(raw_target):
            continue
        canonical_target = normalize_alias(raw_target, alias_map)
        target = entity_index.get(canonical_target)
        if target is None:
            continue
        provenance.add((entity_uri, PROV.wasDerivedFrom, _entity_uri(target.canonical_id)))


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
    alias_map: dict[str, str],
    bridge,
    ontology_catalogs: list[OntologyCatalog],
    ext_prefixes: frozenset[str],
) -> None:
    graph = dataset.graph(_graph_uri(relation.graph_layer))
    subject_uri = _canonical_entity_uri(relation.subject, entity_index=entity_index, alias_map=alias_map)
    predicate_uri = _resolve_relation_term(relation.predicate)

    if is_external_reference(relation.object, known_prefixes=ext_prefixes):
        object_uri = _external_uri(relation.object)
        _register_external_term(object_uri, relation.object, bridge=bridge, ontology_catalogs=ontology_catalogs)
    else:
        object_uri = _canonical_entity_uri(relation.object, entity_index=entity_index, alias_map=alias_map)

    graph.add((subject_uri, predicate_uri, object_uri))


def _add_binding(
    binding: SourceBinding,
    *,
    knowledge,
    provenance,
    entity_index: dict[str, Entity],
    alias_map: dict[str, str],
) -> None:
    model_uri = _canonical_entity_uri(binding.model, entity_index=entity_index, alias_map=alias_map)
    parameter_uri = _canonical_entity_uri(binding.parameter, entity_index=entity_index, alias_map=alias_map)
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
                _binding_reference_uri(target, entity_index=entity_index, alias_map=alias_map),
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
        value = getattr(entity, field)
        if value is not None:
            provenance.add((uri, predicate, Literal(str(value))))

    if entity.measurement_model is not None:
        provenance.add(
            (
                uri,
                SCI_NS.measurementModel,
                Literal(_model_to_json(entity.measurement_model)),
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
    alias_map: dict[str, str],
) -> URIRef:
    canonical_id = normalize_alias(raw_value, alias_map)
    entity = entity_index.get(canonical_id)
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
    alias_map: dict[str, str],
) -> URIRef:
    if is_external_reference(raw_target):
        return _external_uri(raw_target)
    return _canonical_entity_uri(raw_target, entity_index=entity_index, alias_map=alias_map)


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

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import click
from rdflib import Literal, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD
from science_model.reasoning import MeasurementModel, RivalModelPacket
from science_model.relations import relation_allows_kinds

from science_tool.graph.sources import is_metadata_reference

from .constants import (
    CITO_NS,
    DCTERMS_NS,
    EVIDENCE_STANCE_PREDICATES,
    GRAPH_LAYERS,
    PROJECT_NS,
    SCHEMA_NS,
    SCI_NS,
    VALID_INQUIRY_TYPES,
    _RELATION_KIND_BY_PREDICATE,
)
from .identity import (
    _edge_statement_uri,
    _entity_kind_from_uri,
    _graph_uri,
    _resolve_term,
    _slug,
)
from .dataset import _load_dataset, _save_dataset
from .evidence_signals import _json_literal
from .types import PropositionEvidenceLine, PropositionInteractionTerm


def add_concept(
    graph_path: Path,
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None = None,
    definition: str | None = None,
    properties: list[tuple[str, str]] | None = None,
    status: str | None = None,
    source: str | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    concept_uri = URIRef(PROJECT_NS[f"concept/{_slug(label)}"])
    knowledge.add((concept_uri, RDF.type, SCI_NS.Concept))
    knowledge.add((concept_uri, SKOS.prefLabel, Literal(label)))

    if concept_type:
        knowledge.add((concept_uri, RDF.type, _resolve_term(concept_type)))
    if ontology_id:
        knowledge.add((concept_uri, SCHEMA_NS.identifier, Literal(ontology_id)))
    if note:
        knowledge.add((concept_uri, SKOS.note, Literal(note)))
    if definition:
        knowledge.add((concept_uri, SKOS.definition, Literal(definition)))
    if properties:
        for key, value in properties:
            pred = _resolve_term(key) if ":" in key else SCI_NS[key]
            knowledge.add((concept_uri, pred, Literal(value)))
    if status:
        knowledge.add((concept_uri, SCI_NS.projectStatus, Literal(status)))
    if source:
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        provenance.add((concept_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return concept_uri


def add_article(graph_path: Path, doi: str) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    doi_slug = _slug(doi)
    article_uri = URIRef(PROJECT_NS[f"article/doi_{doi_slug}"])
    knowledge.add((article_uri, RDF.type, SCI_NS.Article))
    knowledge.add((article_uri, SCHEMA_NS.identifier, Literal(doi)))

    _save_dataset(dataset, graph_path)
    return article_uri


def add_proposition(
    graph_path: Path,
    text: str,
    source: str,
    confidence: float | None = None,
    evidence_type: str | None = None,
    proposition_id: str | None = None,
    subject: str | None = None,
    predicate: str | None = None,
    obj: str | None = None,
    compositional_status: str | None = None,
    compositional_method: str | None = None,
    compositional_note: str | None = None,
    platform_pattern: str | None = None,
    dataset_effects: dict[str, float] | None = None,
    evidence_lines: list[PropositionEvidenceLine] | None = None,
    statistical_support: str | None = None,
    mechanistic_support: str | None = None,
    replication_scope: str | None = None,
    claim_status: str | None = None,
    pre_registration_refs: list[str] | None = None,
    interaction_terms: list[PropositionInteractionTerm] | None = None,
    bridge_between_refs: list[str] | None = None,
    claim_layer: str | None = None,
    identification_strength: str | None = None,
    proxy_directness: str | None = None,
    supports_scope: str | None = None,
    independence_group: str | None = None,
    evidence_role: str | None = None,
    measurement_model: MeasurementModel | dict[str, object] | None = None,
    rival_model_packet: RivalModelPacket | dict[str, object] | None = None,
) -> URIRef:
    """Add a proposition to the knowledge graph.

    When subject/predicate/obj are provided, the proposition has structured
    S-P-O form (replacing the former relation_claim).
    """
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    if proposition_id is not None:
        token = _slug(proposition_id)
        if not token:
            raise click.ClickException("Proposition ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{source}|{text}".encode("utf-8")).hexdigest()[:12]

    prop_uri = URIRef(PROJECT_NS[f"proposition/{token}"])
    knowledge.add((prop_uri, RDF.type, SCI_NS.Proposition))
    knowledge.add((prop_uri, SCHEMA_NS.text, Literal(text)))

    # Structured S-P-O form (optional)
    if subject and predicate and obj:
        subject_uri = _resolve_term(subject)
        predicate_uri = _resolve_term(predicate)
        object_uri = _resolve_term(obj)
        knowledge.add((prop_uri, SCI_NS.propSubject, subject_uri))
        knowledge.add((prop_uri, SCI_NS.propPredicate, predicate_uri))
        knowledge.add((prop_uri, SCI_NS.propObject, object_uri))

    provenance.add((prop_uri, PROV.wasDerivedFrom, _resolve_term(source)))
    if confidence is not None:
        provenance.add((prop_uri, SCI_NS.confidence, Literal(confidence, datatype=XSD.decimal)))
    if evidence_type is not None:
        provenance.add((prop_uri, SCI_NS.evidenceType, Literal(evidence_type)))
    if compositional_status is not None:
        provenance.add((prop_uri, SCI_NS.compositionalStatus, Literal(compositional_status)))
    if compositional_method is not None:
        provenance.add((prop_uri, SCI_NS.compositionalMethod, Literal(compositional_method)))
    if compositional_note is not None:
        provenance.add((prop_uri, SCI_NS.compositionalNote, Literal(compositional_note)))
    if platform_pattern is not None:
        provenance.add((prop_uri, SCI_NS.platformPattern, Literal(platform_pattern)))
    if dataset_effects is not None:
        normalized_dataset_effects = {str(name): float(value) for name, value in dataset_effects.items()}
        provenance.add((prop_uri, SCI_NS.datasetEffects, Literal(json.dumps(normalized_dataset_effects))))
    if evidence_lines is not None:
        for line in evidence_lines:
            normalized_line: PropositionEvidenceLine = {
                "source": str(line["source"]),
                "kind": str(line["kind"]),
                "datasets": [str(dataset) for dataset in line["datasets"]],
            }
            provenance.add((prop_uri, SCI_NS.evidenceLine, Literal(json.dumps(normalized_line))))
    if statistical_support is not None:
        provenance.add((prop_uri, SCI_NS.statisticalSupport, Literal(statistical_support)))
    if mechanistic_support is not None:
        provenance.add((prop_uri, SCI_NS.mechanisticSupport, Literal(mechanistic_support)))
    if replication_scope is not None:
        provenance.add((prop_uri, SCI_NS.replicationScope, Literal(replication_scope)))
    if claim_status is not None:
        provenance.add((prop_uri, SCI_NS.claimStatus, Literal(claim_status)))
    if claim_layer is not None:
        provenance.add((prop_uri, SCI_NS.claimLayer, Literal(str(claim_layer))))
    if identification_strength is not None:
        provenance.add((prop_uri, SCI_NS.identificationStrength, Literal(str(identification_strength))))
    if proxy_directness is not None:
        provenance.add((prop_uri, SCI_NS.proxyDirectness, Literal(str(proxy_directness))))
    if supports_scope is not None:
        provenance.add((prop_uri, SCI_NS.supportsScope, Literal(str(supports_scope))))
    if independence_group is not None:
        provenance.add((prop_uri, SCI_NS.independenceGroup, Literal(independence_group)))
    if evidence_role is not None:
        provenance.add((prop_uri, SCI_NS.evidenceRole, Literal(str(evidence_role))))
    if measurement_model is not None:
        provenance.add(
            (
                prop_uri,
                SCI_NS.measurementModel,
                Literal(_json_literal(measurement_model, MeasurementModel)),
            )
        )
    if rival_model_packet is not None:
        provenance.add(
            (
                prop_uri,
                SCI_NS.rivalModelPacket,
                Literal(_json_literal(rival_model_packet, RivalModelPacket)),
            )
        )
    if pre_registration_refs is not None:
        for pre_registration_ref in pre_registration_refs:
            provenance.add((prop_uri, SCI_NS.preRegisteredIn, _resolve_term(pre_registration_ref)))
    if interaction_terms is not None:
        for term in interaction_terms:
            normalized_term: PropositionInteractionTerm = {
                "modifier": str(_resolve_term(term["modifier"])),
                "effect": str(term["effect"]),
            }
            if "note" in term and term["note"]:
                normalized_term["note"] = str(term["note"])
            provenance.add((prop_uri, SCI_NS.interactionTerm, Literal(json.dumps(normalized_term))))
    if bridge_between_refs is not None:
        for bridge_ref in bridge_between_refs:
            bridge_uri = _resolve_term(bridge_ref)
            knowledge.add((prop_uri, CITO_NS.discusses, bridge_uri))
            provenance.add((prop_uri, SCI_NS.bridgeBetween, bridge_uri))

    _save_dataset(dataset, graph_path)
    return prop_uri


def add_observation(
    graph_path: Path,
    description: str,
    data_source: str,
    metric: str | None = None,
    value: str | None = None,
    uncertainty: str | None = None,
    conditions: str | None = None,
    observation_id: str | None = None,
) -> URIRef:
    """Add an observation — a concrete empirical fact anchored to data."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if observation_id is not None:
        token = _slug(observation_id)
        if not token:
            raise click.ClickException("Observation ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{data_source}|{description}".encode("utf-8")).hexdigest()[:12]

    obs_uri = URIRef(PROJECT_NS[f"observation/{token}"])
    knowledge.add((obs_uri, RDF.type, SCI_NS.Observation))
    knowledge.add((obs_uri, SCHEMA_NS.description, Literal(description)))
    knowledge.add((obs_uri, SCI_NS.dataSource, _resolve_term(data_source)))
    if metric:
        knowledge.add((obs_uri, SCI_NS.metric, Literal(metric)))
    if value:
        knowledge.add((obs_uri, SCI_NS.value, Literal(value)))
    if uncertainty:
        knowledge.add((obs_uri, SCI_NS.uncertainty, Literal(uncertainty)))
    if conditions:
        knowledge.add((obs_uri, SCI_NS.conditions, Literal(conditions)))

    _save_dataset(dataset, graph_path)
    return obs_uri


def add_evidence_edge(
    graph_path: Path,
    source_entity: str,
    target_entity: str,
    stance: str,
    strength: str | None = None,
    caveats: str | None = None,
    method: str | None = None,
    independence: str | None = None,
) -> None:
    """Add a supports/disputes evidence edge with annotations.

    Evidence is a relation (annotated edge), not a node.
    In RDF: reified statement in the provenance layer.
    """
    if stance not in ("supports", "disputes"):
        raise click.ClickException(f"Stance must be 'supports' or 'disputes', got '{stance}'")

    dataset = _load_dataset(graph_path)
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    source_uri = _resolve_term(source_entity)
    target_uri = _resolve_term(target_entity)
    predicate_uri = CITO_NS.supports if stance == "supports" else CITO_NS.disputes

    # Add the direct edge in knowledge layer
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    knowledge.add((source_uri, predicate_uri, target_uri))

    # Reify in provenance for annotations
    stmt_token = hashlib.sha1(f"{source_entity}|{stance}|{target_entity}".encode("utf-8")).hexdigest()[:12]
    stmt_uri = URIRef(PROJECT_NS[f"evidence/{stmt_token}"])
    provenance.add((stmt_uri, RDF.type, RDF.Statement))
    provenance.add((stmt_uri, RDF.subject, source_uri))
    provenance.add((stmt_uri, RDF.predicate, predicate_uri))
    provenance.add((stmt_uri, RDF.object, target_uri))

    if strength:
        provenance.add((stmt_uri, SCI_NS.evidenceStrength, Literal(strength)))
    if caveats:
        provenance.add((stmt_uri, SCI_NS.evidenceCaveats, Literal(caveats)))
    if method:
        provenance.add((stmt_uri, SCI_NS.evidenceMethod, Literal(method)))
    if independence:
        if independence not in ("independent", "shared-source", "circular"):
            raise click.ClickException(f"Independence must be independent/shared-source/circular, got '{independence}'")
        provenance.add((stmt_uri, SCI_NS.evidenceIndependence, Literal(independence)))

    _save_dataset(dataset, graph_path)


def add_finding(
    graph_path: Path,
    summary: str,
    confidence: str,
    propositions: list[str],
    observations: list[str],
    source: str,
    finding_id: str | None = None,
) -> URIRef:
    """Add a finding — propositions grounded by observations from an analysis."""
    if confidence not in ("high", "moderate", "low", "speculative"):
        raise click.ClickException(f"Confidence must be high/moderate/low/speculative, got '{confidence}'")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if finding_id is not None:
        token = _slug(finding_id)
        if not token:
            raise click.ClickException("Finding ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{source}|{summary}".encode("utf-8")).hexdigest()[:12]

    finding_uri = URIRef(PROJECT_NS[f"finding/{token}"])
    knowledge.add((finding_uri, RDF.type, SCI_NS.Finding))
    knowledge.add((finding_uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((finding_uri, SCI_NS.confidence, Literal(confidence)))

    for prop_ref in propositions:
        knowledge.add((finding_uri, SCI_NS.contains, _resolve_term(prop_ref)))

    for obs_ref in observations:
        knowledge.add((finding_uri, SCI_NS.contains, _resolve_term(obs_ref)))

    knowledge.add((finding_uri, SCI_NS.groundedBy, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return finding_uri


def add_interpretation(
    graph_path: Path,
    summary: str,
    findings: list[str],
    context: str | None = None,
    prior: str | None = None,
    interpretation_id: str | None = None,
) -> URIRef:
    """Add an interpretation — one analysis session's narrative and findings."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if interpretation_id is not None:
        token = _slug(interpretation_id)
        if not token:
            raise click.ClickException("Interpretation ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{summary}".encode("utf-8")).hexdigest()[:12]

    interp_uri = URIRef(PROJECT_NS[f"interpretation/{token}"])
    knowledge.add((interp_uri, RDF.type, SCI_NS.Interpretation))
    knowledge.add((interp_uri, SCHEMA_NS.description, Literal(summary)))

    if context:
        knowledge.add((interp_uri, SCI_NS.context, Literal(context)))

    for finding_ref in findings:
        knowledge.add((interp_uri, SCI_NS.contains, _resolve_term(finding_ref)))

    if prior:
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        provenance.add((interp_uri, PROV.wasDerivedFrom, _resolve_term(prior)))

    _save_dataset(dataset, graph_path)
    return interp_uri


def add_discussion(
    graph_path: Path,
    summary: str,
    propositions: list[str],
    context: str | None = None,
    prior: str | None = None,
    discussion_id: str | None = None,
) -> URIRef:
    """Add a discussion — theoretical reasoning producing propositions without empirical grounding."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if discussion_id is not None:
        token = _slug(discussion_id)
        if not token:
            raise click.ClickException("Discussion ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{summary}".encode("utf-8")).hexdigest()[:12]

    disc_uri = URIRef(PROJECT_NS[f"discussion/{token}"])
    knowledge.add((disc_uri, RDF.type, SCI_NS.Discussion))
    knowledge.add((disc_uri, SCHEMA_NS.description, Literal(summary)))

    if context:
        knowledge.add((disc_uri, SCI_NS.context, Literal(context)))

    for prop_ref in propositions:
        knowledge.add((disc_uri, SCI_NS.contains, _resolve_term(prop_ref)))

    if prior:
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        provenance.add((disc_uri, PROV.wasDerivedFrom, _resolve_term(prior)))

    _save_dataset(dataset, graph_path)
    return disc_uri


def add_falsification(
    graph_path: Path,
    predicted: str,
    source_of_prediction: str,
    observed: str,
    decision: str,
    proposition_ref: str,
    falsification_id: str | None = None,
    supersedes_claim: str | None = None,
) -> URIRef:
    """Add a falsification record linked to a proposition-backed claim."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if falsification_id is not None:
        token = _slug(falsification_id)
        if not token:
            raise click.ClickException("Falsification ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{predicted}|{observed}|{decision}".encode("utf-8")).hexdigest()[:12]

    proposition_uri = _resolve_term(proposition_ref)
    if (proposition_uri, RDF.type, SCI_NS.Proposition) not in knowledge:
        raise click.ClickException(f"Falsification target '{proposition_ref}' must resolve to a proposition entity")

    falsification_uri = URIRef(PROJECT_NS[f"falsification/{token}"])
    knowledge.add((falsification_uri, RDF.type, SCI_NS.Falsification))
    knowledge.add((falsification_uri, SCI_NS.predicted, Literal(predicted)))
    knowledge.add((falsification_uri, SCI_NS.observed, Literal(observed)))
    knowledge.add((falsification_uri, SCI_NS.decision, Literal(decision)))
    knowledge.add((falsification_uri, SCI_NS.sourceOfPrediction, Literal(source_of_prediction)))
    knowledge.add((falsification_uri, SCI_NS.falsifies, proposition_uri))
    if supersedes_claim:
        knowledge.add((falsification_uri, SCI_NS.supersedesClaim, _resolve_term(supersedes_claim)))

    _save_dataset(dataset, graph_path)
    return falsification_uri


def add_mechanism(
    graph_path: Path,
    title: str,
    summary: str,
    participants: list[str],
    propositions: list[str],
    status: str = "draft",
    mechanism_id: str | None = None,
) -> URIRef:
    """Add a mechanism as a strict explanatory structure over existing entities."""
    if len(participants) < 2:
        raise click.ClickException("Mechanism requires at least two participants")
    if not propositions:
        raise click.ClickException("Mechanism requires at least one proposition")
    if not summary.strip():
        raise click.ClickException("Mechanism requires a non-empty summary")
    if not status.strip():
        raise click.ClickException("Mechanism status must be non-empty")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    participant_uris: list[URIRef] = []
    for participant_ref in participants:
        participant_uri = _resolve_term(participant_ref)
        if not any(True for _ in knowledge.triples((participant_uri, RDF.type, None))):
            raise click.ClickException(f"Mechanism participant '{participant_ref}' must resolve to an existing entity")
        participant_kind = _entity_kind_from_uri(participant_uri)
        if participant_kind is not None and participant_kind != "concept":
            raise click.ClickException(
                f"Mechanism participants must be concept or domain entities, got '{participant_ref}'"
            )
        participant_uris.append(participant_uri)

    proposition_uris: list[URIRef] = []
    for proposition_ref in propositions:
        proposition_uri = _resolve_term(proposition_ref)
        if (proposition_uri, RDF.type, SCI_NS.Proposition) not in knowledge:
            raise click.ClickException(
                f"Mechanism proposition '{proposition_ref}' must resolve to a proposition entity"
            )
        proposition_uris.append(proposition_uri)

    if mechanism_id is not None:
        token = _slug(mechanism_id)
        if not token:
            raise click.ClickException("Mechanism ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{title}".encode("utf-8")).hexdigest()[:12]

    mechanism_uri = URIRef(PROJECT_NS[f"mechanism/{token}"])
    knowledge.add((mechanism_uri, RDF.type, SCI_NS.Mechanism))
    knowledge.add((mechanism_uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((mechanism_uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((mechanism_uri, SCI_NS.projectStatus, Literal(status)))

    for participant_uri in participant_uris:
        knowledge.add((mechanism_uri, SCI_NS.hasParticipant, participant_uri))
    for proposition_uri in proposition_uris:
        knowledge.add((mechanism_uri, SCI_NS.hasProposition, proposition_uri))

    _save_dataset(dataset, graph_path)
    return mechanism_uri


def add_story(
    graph_path: Path,
    title: str,
    summary: str,
    about: str,
    interpretations: list[str],
    status: str = "draft",
    story_id: str | None = None,
) -> URIRef:
    """Add a story — a narrative arc synthesizing interpretations around a question or hypothesis."""
    if status not in ("draft", "developing", "mature"):
        raise click.ClickException(f"Story status must be draft/developing/mature, got '{status}'")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if story_id is not None:
        token = _slug(story_id)
        if not token:
            raise click.ClickException("Story ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{title}".encode("utf-8")).hexdigest()[:12]

    story_uri = URIRef(PROJECT_NS[f"story/{token}"])
    knowledge.add((story_uri, RDF.type, SCI_NS.Story))
    knowledge.add((story_uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((story_uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((story_uri, SCI_NS.projectStatus, Literal(status)))
    knowledge.add((story_uri, SCI_NS.organizedBy, _resolve_term(about)))

    for interp_ref in interpretations:
        knowledge.add((story_uri, SCI_NS.synthesizes, _resolve_term(interp_ref)))

    _save_dataset(dataset, graph_path)
    return story_uri


def add_paper_entity(
    graph_path: Path,
    title: str,
    stories: list[str],
    status: str = "outline",
    abstract: str | None = None,
    paper_id: str | None = None,
) -> URIRef:
    """Add a paper — an ordered composition of stories for communication."""
    if status not in ("outline", "draft", "revision", "final"):
        raise click.ClickException(f"Paper status must be outline/draft/revision/final, got '{status}'")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if paper_id is not None:
        token = _slug(paper_id)
        if not token:
            raise click.ClickException("Paper ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{title}".encode("utf-8")).hexdigest()[:12]

    paper_uri = URIRef(PROJECT_NS[f"paper/{token}"])
    knowledge.add((paper_uri, RDF.type, SCI_NS.Paper))
    knowledge.add((paper_uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((paper_uri, SCI_NS.projectStatus, Literal(status)))

    if abstract:
        knowledge.add((paper_uri, SCHEMA_NS.description, Literal(abstract)))

    for story_ref in stories:
        knowledge.add((paper_uri, SCI_NS.comprises, _resolve_term(story_ref)))

    _save_dataset(dataset, graph_path)
    return paper_uri


def add_hypothesis(graph_path: Path, hypothesis_id: str, text: str, source: str, status: str | None = None) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    hypothesis_uri = URIRef(PROJECT_NS[f"hypothesis/{hypothesis_id.lower()}"])
    knowledge.add((hypothesis_uri, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((hypothesis_uri, SCHEMA_NS.identifier, Literal(hypothesis_id)))
    knowledge.add((hypothesis_uri, SCHEMA_NS.text, Literal(text)))

    if status:
        knowledge.add((hypothesis_uri, SCI_NS.projectStatus, Literal(status)))

    provenance.add((hypothesis_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return hypothesis_uri


def add_question(
    graph_path: Path,
    question_id: str,
    text: str,
    source: str,
    maturity: str = "open",
    status: str | None = None,
    related: list[str] | None = None,
) -> URIRef:
    """Add an open question with provenance to the graph."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    question_uri = URIRef(PROJECT_NS[f"question/{question_id.lower()}"])
    knowledge.add((question_uri, RDF.type, SCI_NS.Question))
    knowledge.add((question_uri, SCHEMA_NS.identifier, Literal(question_id)))
    knowledge.add((question_uri, SCHEMA_NS.text, Literal(text)))
    knowledge.add((question_uri, SCI_NS.maturity, Literal(maturity)))

    if status:
        knowledge.add((question_uri, SCI_NS.projectStatus, Literal(status)))

    provenance.add((question_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    if related:
        for ref in related:
            if is_metadata_reference(ref):
                continue
            knowledge.add((question_uri, SKOS.related, _resolve_term(ref)))

    _save_dataset(dataset, graph_path)
    return question_uri


def _warn_on_relation_direction_mismatch(
    predicate_uri: URIRef,
    subject_uri: URIRef,
    object_uri: URIRef,
    *,
    predicate: str,
) -> None:
    """Echo a warning when an edge violates the CORE_PROFILE source/target kinds.

    Profile is descriptive, not enforced — emit a stderr warning so users learn
    about direction mistakes (e.g. `prop sci:addresses question` when the
    canonical direction is `question sci:addresses prop`) without breaking
    existing workflows. Silent when subject/object URIs are not project
    entities, when the predicate has no profile entry, or when the kinds match.
    """
    constraint = _RELATION_KIND_BY_PREDICATE.get(predicate_uri)
    if constraint is None:
        return
    relation_kind = constraint
    subject_kind = _entity_kind_from_uri(subject_uri)
    object_kind = _entity_kind_from_uri(object_uri)
    if subject_kind is None or object_kind is None:
        return
    if relation_allows_kinds(relation_kind, subject_kind, object_kind):
        return
    if relation_allows_kinds(relation_kind, object_kind, subject_kind):
        click.echo(
            f"Warning: '{predicate}' direction looks reversed — "
            f"profile accepts {relation_kind.name} endpoints but got reversed "
            f"{subject_kind} -> {object_kind}.",
            err=True,
        )
        return
    click.echo(
        f"Warning: '{predicate}' edge has unexpected kinds — "
        f"got {subject_kind} -> {object_kind}.",
        err=True,
    )


def add_edge(
    graph_path: Path,
    subject: str,
    predicate: str,
    obj: str,
    graph_layer: str,
    claim_refs: list[str] | None = None,
) -> tuple[URIRef, URIRef, URIRef]:
    if graph_layer not in GRAPH_LAYERS:
        raise click.ClickException(f"Unsupported graph layer: {graph_layer}")
    if is_metadata_reference(subject) or is_metadata_reference(obj):
        raise click.ClickException(
            f"meta: refs are intentional metadata and cannot be subject or object of a graph edge "
            f"(got subject={subject!r}, object={obj!r})"
        )

    dataset = _load_dataset(graph_path)

    s_uri = _resolve_term(subject)
    p_uri = _resolve_term(predicate)
    o_uri = _resolve_term(obj)

    if graph_layer == "graph/knowledge" and p_uri in EVIDENCE_STANCE_PREDICATES:
        raise click.ClickException(
            f"Predicate '{predicate}' is an evidence stance predicate; use 'graph add evidence' instead."
        )

    _warn_on_relation_direction_mismatch(p_uri, s_uri, o_uri, predicate=predicate)

    # Warn if subject/object URIs don't exist in any graph yet
    for uri, label in [(s_uri, subject), (o_uri, obj)]:
        if not any((uri, None, None) in g for g in dataset.graphs()):
            click.echo(f"Warning: '{label}' resolves to {uri} which is not yet in the graph", err=True)

    layer = dataset.graph(_graph_uri(graph_layer))
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    layer.add((s_uri, p_uri, o_uri))
    if claim_refs:
        _attach_edge_claims(
            context_graph=layer,
            knowledge=knowledge,
            context_token=graph_layer,
            subject_uri=s_uri,
            predicate_uri=p_uri,
            object_uri=o_uri,
            claim_refs=claim_refs,
        )

    _save_dataset(dataset, graph_path)
    return s_uri, p_uri, o_uri


def migrate_addresses_direction(graph_path: Path, *, apply: bool) -> dict[str, int]:
    """Flip anti-canonical `?prop sci:addresses ?question` triples to the canonical
    `?question sci:addresses ?prop` direction declared by the CORE_PROFILE
    (source=question, target=proposition).

    Only triples where the subject is typed sci:Proposition AND the object is typed
    sci:Question are migrated; everything else is left alone (including triples
    that already match the canonical direction).

    With apply=False, returns counts without writing.
    """
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    flipped: list[tuple[URIRef, URIRef]] = []
    already_canonical = 0
    for s, _, o in knowledge.triples((None, SCI_NS.addresses, None)):
        if not (isinstance(s, URIRef) and isinstance(o, URIRef)):
            continue
        s_is_question = (s, RDF.type, SCI_NS.Question) in knowledge
        s_is_proposition = (s, RDF.type, SCI_NS.Proposition) in knowledge
        o_is_question = (o, RDF.type, SCI_NS.Question) in knowledge
        o_is_proposition = (o, RDF.type, SCI_NS.Proposition) in knowledge
        if s_is_question and o_is_proposition:
            already_canonical += 1
            continue
        if s_is_proposition and o_is_question:
            flipped.append((s, o))

    if apply and flipped:
        for prop_uri, question_uri in flipped:
            knowledge.remove((prop_uri, SCI_NS.addresses, question_uri))
            knowledge.add((question_uri, SCI_NS.addresses, prop_uri))
        _save_dataset(dataset, graph_path)

    return {
        "flipped": len(flipped),
        "already_canonical": already_canonical,
    }


def add_inquiry(
    graph_path: Path,
    slug: str,
    label: str,
    target: str,
    description: str = "",
    status: str = "sketch",
    inquiry_type: str = "general",
) -> URIRef:
    """Create a new inquiry named graph with metadata triples."""
    if inquiry_type not in VALID_INQUIRY_TYPES:
        raise ValueError(f"Invalid inquiry type '{inquiry_type}'. Must be one of: {', '.join(VALID_INQUIRY_TYPES)}")

    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    # Duplicate check
    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' already exists")

    inquiry_graph.add((inquiry_uri, RDF.type, SCI_NS.Inquiry))
    inquiry_graph.add((inquiry_uri, SKOS.prefLabel, Literal(label)))
    inquiry_graph.add((inquiry_uri, SCI_NS.inquiryStatus, Literal(status)))
    inquiry_graph.add((inquiry_uri, SCI_NS.inquiryType, Literal(inquiry_type)))
    inquiry_graph.add((inquiry_uri, SCI_NS.target, _resolve_term(target)))

    created = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    inquiry_graph.add((inquiry_uri, DCTERMS_NS.created, Literal(created)))

    if description:
        inquiry_graph.add((inquiry_uri, SKOS.note, Literal(description)))

    _save_dataset(dataset, graph_path)
    return inquiry_uri


def set_boundary_role(
    graph_path: Path,
    inquiry_slug: str,
    entity: str,
    role: str,
) -> None:
    """Assign a boundary role (BoundaryIn or BoundaryOut) to an entity within an inquiry."""
    valid_roles = {"BoundaryIn": SCI_NS.BoundaryIn, "BoundaryOut": SCI_NS.BoundaryOut}
    if role not in valid_roles:
        raise ValueError(f"Invalid boundary role '{role}'. Must be one of: {', '.join(sorted(valid_roles))}")

    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    entity_uri = _resolve_term(entity)
    inquiry_graph.add((entity_uri, SCI_NS.boundaryRole, valid_roles[role]))

    _save_dataset(dataset, graph_path)


def add_inquiry_node(
    graph_path: Path,
    inquiry_slug: str,
    entity: str,
) -> None:
    """Add an entity as an interior node to an inquiry (no boundary role)."""
    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    entity_uri = _resolve_term(entity)
    # Mark presence in inquiry by adding its type from knowledge graph
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    for t in knowledge.objects(entity_uri, RDF.type):
        inquiry_graph.add((entity_uri, RDF.type, t))
        break  # one type is sufficient to mark membership
    else:
        # If no type found in knowledge, add a generic membership triple
        inquiry_graph.add((entity_uri, RDF.type, SCI_NS.Concept))

    _save_dataset(dataset, graph_path)


def add_inquiry_edge(
    graph_path: Path,
    inquiry_slug: str,
    subject: str,
    predicate: str,
    obj: str,
    claim_refs: list[str] | None = None,
) -> tuple[URIRef, URIRef, URIRef]:
    """Add a triple to an inquiry's named graph."""
    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    if is_metadata_reference(subject) or is_metadata_reference(obj):
        raise click.ClickException(
            f"meta: refs are intentional metadata and cannot be subject or object of a graph edge "
            f"(got subject={subject!r}, object={obj!r})"
        )

    s_uri = _resolve_term(subject)
    p_uri = _resolve_term(predicate)
    o_uri = _resolve_term(obj)
    inquiry_graph.add((s_uri, p_uri, o_uri))
    if claim_refs:
        _attach_edge_claims(
            context_graph=inquiry_graph,
            knowledge=knowledge,
            context_token=str(inquiry_uri),
            subject_uri=s_uri,
            predicate_uri=p_uri,
            object_uri=o_uri,
            claim_refs=claim_refs,
        )

    _save_dataset(dataset, graph_path)
    return s_uri, p_uri, o_uri


def add_assumption(
    graph_path: Path,
    label: str,
    source: str,
    inquiry_slug: str | None = None,
) -> URIRef:
    """Create an assumption concept in the knowledge layer and optionally link it to an inquiry."""
    uri = add_concept(graph_path, label, concept_type="sci:Assumption", ontology_id=None, source=source)

    # Ensure sci:Assumption type is explicitly present in knowledge layer
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    knowledge.add((uri, RDF.type, SCI_NS.Assumption))

    if inquiry_slug is not None:
        safe_slug = _slug(inquiry_slug)
        inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])
        inquiry_graph = dataset.graph(inquiry_uri)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
            raise ValueError(f"Inquiry '{safe_slug}' does not exist")
        inquiry_graph.add((uri, RDF.type, SCI_NS.Assumption))

    _save_dataset(dataset, graph_path)
    return uri


def add_transformation(
    graph_path: Path,
    label: str,
    inquiry_slug: str,
    tool: str = "",
    params: dict[str, dict[str, str]] | None = None,
) -> URIRef:
    """Create a transformation concept and register it in an inquiry graph."""
    uri = add_concept(graph_path, label, concept_type="sci:Transformation", ontology_id=None)

    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    inquiry_graph.add((uri, RDF.type, SCI_NS.Transformation))

    if tool:
        inquiry_graph.add((uri, SCI_NS.tool, Literal(tool)))

    if params:
        for _param_name, meta in params.items():
            if "value" in meta:
                inquiry_graph.add((uri, SCI_NS.paramValue, Literal(meta["value"])))
            if "source" in meta:
                inquiry_graph.add((uri, SCI_NS.paramSource, Literal(meta["source"])))
            if "note" in meta:
                inquiry_graph.add((uri, SCI_NS.paramNote, Literal(meta["note"])))
            if "refs" in meta:
                for ref in meta["refs"] if isinstance(meta["refs"], list) else [meta["refs"]]:
                    inquiry_graph.add((uri, SCI_NS.paramRef, Literal(ref)))

    _save_dataset(dataset, graph_path)
    return uri


def add_data_package(
    graph_path: Path,
    package_id: str,
    title: str,
    *,
    produced_by: str | None = None,
) -> URIRef:
    """Add a data-package entity to the knowledge graph."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    uri = URIRef(PROJECT_NS[f"data-package/{_slug(package_id)}"])
    knowledge.add((uri, RDF.type, SCI_NS.DataPackage))
    knowledge.add((uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((uri, SCHEMA_NS.identifier, Literal(package_id)))

    if produced_by:
        knowledge.add((uri, SCI_NS.producedBy, _resolve_term(produced_by)))

    _save_dataset(dataset, graph_path)
    return uri


def set_param_metadata(
    graph_path: Path,
    entity: str,
    value: str,
    source: str,
    refs: list[str] | None = None,
    note: str = "",
) -> None:
    """Attach AnnotatedParam-style metadata (value, source, refs, note) to an entity in the knowledge graph."""
    entity_uri = _resolve_term(entity)

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    knowledge.add((entity_uri, SCI_NS.paramValue, Literal(value)))
    knowledge.add((entity_uri, SCI_NS.paramSource, Literal(source)))

    if note:
        knowledge.add((entity_uri, SCI_NS.paramNote, Literal(note)))

    if refs:
        for ref in refs:
            knowledge.add((entity_uri, SCI_NS.paramRef, Literal(ref)))

    _save_dataset(dataset, graph_path)


def _attach_edge_claims(
    context_graph,
    knowledge,
    context_token: str,
    subject_uri: URIRef,
    predicate_uri: URIRef,
    object_uri: URIRef,
    claim_refs: list[str],
) -> None:
    statement_uri = _edge_statement_uri(context_token, subject_uri, predicate_uri, object_uri)
    context_graph.add((statement_uri, RDF.type, RDF.Statement))
    context_graph.add((statement_uri, RDF.subject, subject_uri))
    context_graph.add((statement_uri, RDF.predicate, predicate_uri))
    context_graph.add((statement_uri, RDF.object, object_uri))

    seen: set[URIRef] = set()
    for claim_ref in claim_refs:
        claim_uri = _resolve_term(claim_ref)
        if claim_uri in seen:
            continue
        seen.add(claim_uri)
        if (claim_uri, RDF.type, SCI_NS.Proposition) not in knowledge:
            raise click.ClickException(f"Attached claim '{claim_ref}' must resolve to a proposition entity")

        claim_subject = next(knowledge.objects(claim_uri, SCI_NS.propSubject), None)
        claim_predicate = next(knowledge.objects(claim_uri, SCI_NS.propPredicate), None)
        claim_object = next(knowledge.objects(claim_uri, SCI_NS.propObject), None)
        if (claim_subject, claim_predicate, claim_object) != (subject_uri, predicate_uri, object_uri):
            raise click.ClickException(
                f"Attached claim '{claim_ref}' must assert the same subject, predicate, and object as the edge"
            )

        context_graph.add((statement_uri, SCI_NS.backedByClaim, claim_uri))

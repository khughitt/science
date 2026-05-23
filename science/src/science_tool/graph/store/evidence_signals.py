from __future__ import annotations

import json
from typing import cast

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF
from science_model.reasoning import MeasurementModel, RivalModelPacket

from .constants import CITO_NS, SCI_NS
from .identity import shorten_uri
from .types import (
    EvidenceClaimBundle,
    EvidenceSignalSummary,
    FalsificationRecord,
    PropositionEvidenceSemantics,
    PropositionInteractionTerm,
    PropositionPhase1Metadata,
)


def _linked_claims_for_hypothesis(knowledge, hypothesis_uri: URIRef) -> list[URIRef]:
    linked_claims: list[URIRef] = []
    seen: set[URIRef] = set()

    for subj, _, _ in knowledge.triples((None, CITO_NS.discusses, hypothesis_uri)):
        if isinstance(subj, URIRef) and (subj, RDF.type, SCI_NS.Proposition) in knowledge and subj not in seen:
            linked_claims.append(subj)
            seen.add(subj)

    return linked_claims


def _source_strings(provenance, primary_uri: URIRef, fallback_uri: URIRef | None = None) -> list[str]:
    sources = {str(src) for src in provenance.objects(primary_uri, PROV.wasDerivedFrom)}
    if fallback_uri is not None:
        sources.update(str(src) for src in provenance.objects(fallback_uri, PROV.wasDerivedFrom))
    return sorted(sources)


def _load_proposition_phase1_metadata(provenance, proposition_uri: URIRef) -> PropositionPhase1Metadata:
    metadata: PropositionPhase1Metadata = {}

    compositional_status_obj = next(provenance.objects(proposition_uri, SCI_NS.compositionalStatus), None)
    if compositional_status_obj is not None:
        metadata["compositional_status"] = str(compositional_status_obj)

    compositional_method_obj = next(provenance.objects(proposition_uri, SCI_NS.compositionalMethod), None)
    if compositional_method_obj is not None:
        metadata["compositional_method"] = str(compositional_method_obj)

    compositional_note_obj = next(provenance.objects(proposition_uri, SCI_NS.compositionalNote), None)
    if compositional_note_obj is not None:
        metadata["compositional_note"] = str(compositional_note_obj)

    platform_pattern_obj = next(provenance.objects(proposition_uri, SCI_NS.platformPattern), None)
    if platform_pattern_obj is not None:
        metadata["platform_pattern"] = str(platform_pattern_obj)

    dataset_effects_obj = next(provenance.objects(proposition_uri, SCI_NS.datasetEffects), None)
    if dataset_effects_obj is not None:
        parsed_dataset_effects = json.loads(str(dataset_effects_obj))
        metadata["dataset_effects"] = {str(name): float(value) for name, value in parsed_dataset_effects.items()}

    evidence_line_values = list(provenance.objects(proposition_uri, SCI_NS.evidenceLine))
    if evidence_line_values:
        metadata["evidence_lines"] = []
        for value in evidence_line_values:
            parsed_line = json.loads(str(value))
            metadata["evidence_lines"].append(
                {
                    "source": str(parsed_line["source"]),
                    "kind": str(parsed_line["kind"]),
                    "datasets": [str(dataset) for dataset in parsed_line.get("datasets", [])],
                }
            )

    claim_layer_obj = next(provenance.objects(proposition_uri, SCI_NS.claimLayer), None)
    if claim_layer_obj is not None:
        metadata["claim_layer"] = str(claim_layer_obj)

    supports_scope_obj = next(provenance.objects(proposition_uri, SCI_NS.supportsScope), None)
    if supports_scope_obj is not None:
        metadata["supports_scope"] = str(supports_scope_obj)

    measurement_model_obj = next(provenance.objects(proposition_uri, SCI_NS.measurementModel), None)
    if measurement_model_obj is not None:
        metadata["measurement_model"] = cast(dict[str, object], json.loads(str(measurement_model_obj)))

    rival_model_packet_obj = next(provenance.objects(proposition_uri, SCI_NS.rivalModelPacket), None)
    if rival_model_packet_obj is not None:
        metadata["rival_model_packet"] = cast(dict[str, object], json.loads(str(rival_model_packet_obj)))

    return metadata


def _load_proposition_evidence_semantics(provenance, proposition_uri: URIRef) -> PropositionEvidenceSemantics:
    semantics: PropositionEvidenceSemantics = {}

    statistical_support_obj = next(provenance.objects(proposition_uri, SCI_NS.statisticalSupport), None)
    if statistical_support_obj is not None:
        semantics["statistical_support"] = str(statistical_support_obj)

    mechanistic_support_obj = next(provenance.objects(proposition_uri, SCI_NS.mechanisticSupport), None)
    if mechanistic_support_obj is not None:
        semantics["mechanistic_support"] = str(mechanistic_support_obj)

    replication_scope_obj = next(provenance.objects(proposition_uri, SCI_NS.replicationScope), None)
    if replication_scope_obj is not None:
        semantics["replication_scope"] = str(replication_scope_obj)

    claim_status_obj = next(provenance.objects(proposition_uri, SCI_NS.claimStatus), None)
    if claim_status_obj is not None:
        semantics["claim_status"] = str(claim_status_obj)

    identification_strength_obj = next(provenance.objects(proposition_uri, SCI_NS.identificationStrength), None)
    if identification_strength_obj is not None:
        semantics["identification_strength"] = str(identification_strength_obj)

    proxy_directness_obj = next(provenance.objects(proposition_uri, SCI_NS.proxyDirectness), None)
    if proxy_directness_obj is not None:
        semantics["proxy_directness"] = str(proxy_directness_obj)

    independence_group_obj = next(provenance.objects(proposition_uri, SCI_NS.independenceGroup), None)
    if independence_group_obj is not None:
        semantics["independence_group"] = str(independence_group_obj)

    evidence_role_obj = next(provenance.objects(proposition_uri, SCI_NS.evidenceRole), None)
    if evidence_role_obj is not None:
        semantics["evidence_role"] = str(evidence_role_obj)

    return semantics


def _load_proposition_pre_registrations(provenance, proposition_uri: URIRef) -> list[str]:
    return sorted(shorten_uri(str(uri)) for uri in provenance.objects(proposition_uri, SCI_NS.preRegisteredIn))


def _load_proposition_interaction_terms(provenance, proposition_uri: URIRef) -> list[PropositionInteractionTerm]:
    interaction_terms: list[PropositionInteractionTerm] = []
    for value in provenance.objects(proposition_uri, SCI_NS.interactionTerm):
        parsed = json.loads(str(value))
        term: PropositionInteractionTerm = {
            "modifier": shorten_uri(str(parsed["modifier"])),
            "effect": str(parsed["effect"]),
        }
        note = parsed.get("note")
        if isinstance(note, str) and note:
            term["note"] = note
        interaction_terms.append(term)
    return interaction_terms


def _load_proposition_bridge_hypotheses(provenance, proposition_uri: URIRef) -> list[str]:
    return sorted(shorten_uri(str(uri)) for uri in provenance.objects(proposition_uri, SCI_NS.bridgeBetween))


def _load_proposition_falsifications(knowledge, proposition_uri: URIRef) -> list[FalsificationRecord]:
    falsifications: list[FalsificationRecord] = []
    for falsification_uri in sorted(knowledge.subjects(SCI_NS.falsifies, proposition_uri), key=str):
        if not isinstance(falsification_uri, URIRef):
            continue
        record: FalsificationRecord = {
            "uri": str(falsification_uri),
            "predicted": str(next(knowledge.objects(falsification_uri, SCI_NS.predicted), "")),
            "observed": str(next(knowledge.objects(falsification_uri, SCI_NS.observed), "")),
            "decision": str(next(knowledge.objects(falsification_uri, SCI_NS.decision), "")),
            "source_of_prediction": str(next(knowledge.objects(falsification_uri, SCI_NS.sourceOfPrediction), "")),
        }
        supersedes_claim_obj = next(knowledge.objects(falsification_uri, SCI_NS.supersedesClaim), None)
        if supersedes_claim_obj is not None:
            record["supersedes_claim"] = str(supersedes_claim_obj)
        falsifications.append(record)
    return falsifications


def _json_literal(
    value: MeasurementModel | RivalModelPacket | dict[str, object],
    model_type: type[MeasurementModel] | type[RivalModelPacket] | None = None,
) -> str:
    if isinstance(value, dict):
        if model_type is None:
            raise TypeError("Raw dict inputs require a model type for validation")
        payload = model_type.model_validate(value).model_dump(mode="json")
    elif hasattr(value, "model_dump"):
        payload = cast(MeasurementModel | RivalModelPacket, value).model_dump(mode="json")
    else:
        payload = value
    return json.dumps(payload)


def _evidence_targets_for_uri(knowledge, target_uri: URIRef) -> list[URIRef]:
    if (target_uri, RDF.type, SCI_NS.Hypothesis) not in knowledge:
        return [target_uri]
    return [target_uri, *_linked_claims_for_hypothesis(knowledge, target_uri)]


def _collect_evidence_signals(knowledge, provenance, target_uri: URIRef) -> EvidenceSignalSummary:
    support_sources: set[str] = set()
    dispute_sources: set[str] = set()
    support_items: set[str] = set()
    dispute_items: set[str] = set()

    def record(relation: str, evidence_uri: URIRef, fallback_uri: URIRef | None = None) -> None:
        source_strings = tuple(_source_strings(provenance, evidence_uri, fallback_uri))
        item = str(evidence_uri)
        if relation == "supports":
            support_items.add(item)
            support_sources.update(source_strings)
            return
        dispute_items.add(item)
        dispute_sources.update(source_strings)

    for aggregate_target in _evidence_targets_for_uri(knowledge, target_uri):
        for subj, _, _ in knowledge.triples((None, CITO_NS.supports, aggregate_target)):
            if isinstance(subj, URIRef):
                record("supports", subj)
        for subj, _, _ in knowledge.triples((None, CITO_NS.disputes, aggregate_target)):
            if isinstance(subj, URIRef):
                record("disputes", subj)

    total_evidence = len(support_items) + len(dispute_items)
    unique_source_count = len(support_sources | dispute_sources)
    if unique_source_count == 0 and total_evidence > 0:
        unique_source_count = total_evidence

    return {
        "support_count": len(support_items),
        "dispute_count": len(dispute_items),
        "support_sources": support_sources,
        "dispute_sources": dispute_sources,
        "source_count": unique_source_count,
    }


def _apply_phase1_metadata_to_bundle(
    bundle: EvidenceClaimBundle,
    metadata: PropositionPhase1Metadata,
) -> None:
    if "compositional_status" in metadata:
        bundle["compositional_status"] = metadata["compositional_status"]
    if "compositional_method" in metadata:
        bundle["compositional_method"] = metadata["compositional_method"]
    if "compositional_note" in metadata:
        bundle["compositional_note"] = metadata["compositional_note"]
    if "platform_pattern" in metadata:
        bundle["platform_pattern"] = metadata["platform_pattern"]
    if "dataset_effects" in metadata:
        bundle["dataset_effects"] = metadata["dataset_effects"]
    if "evidence_lines" in metadata:
        bundle["evidence_lines"] = metadata["evidence_lines"]
    if "claim_layer" in metadata:
        bundle["claim_layer"] = metadata["claim_layer"]
    if "supports_scope" in metadata:
        bundle["supports_scope"] = metadata["supports_scope"]
    if "measurement_model" in metadata:
        bundle["measurement_model"] = metadata["measurement_model"]
    if "rival_model_packet" in metadata:
        bundle["rival_model_packet"] = metadata["rival_model_packet"]


def _apply_evidence_semantics_to_bundle(
    bundle: EvidenceClaimBundle,
    semantics: PropositionEvidenceSemantics,
) -> None:
    if "statistical_support" in semantics:
        bundle["statistical_support"] = semantics["statistical_support"]
    if "mechanistic_support" in semantics:
        bundle["mechanistic_support"] = semantics["mechanistic_support"]
    if "replication_scope" in semantics:
        bundle["replication_scope"] = semantics["replication_scope"]
    if "claim_status" in semantics:
        bundle["claim_status"] = semantics["claim_status"]
    if "identification_strength" in semantics:
        bundle["identification_strength"] = semantics["identification_strength"]
    if "proxy_directness" in semantics:
        bundle["proxy_directness"] = semantics["proxy_directness"]
    if "independence_group" in semantics:
        bundle["independence_group"] = semantics["independence_group"]
    if "evidence_role" in semantics:
        bundle["evidence_role"] = semantics["evidence_role"]


def _evidence_type_strings(provenance, primary_uri: URIRef, fallback_uri: URIRef | None = None) -> set[str]:
    evidence_types = {str(value) for value in provenance.objects(primary_uri, SCI_NS.evidenceType)}
    if fallback_uri is not None:
        evidence_types.update(str(value) for value in provenance.objects(fallback_uri, SCI_NS.evidenceType))
    return {value for value in evidence_types if value}


def _collect_evidence_types(knowledge, provenance, target_uri: URIRef) -> set[str]:
    evidence_types: set[str] = set()

    def record(evidence_uri: URIRef, fallback_uri: URIRef | None = None) -> None:
        evidence_types.update(_evidence_type_strings(provenance, evidence_uri, fallback_uri))

    for aggregate_target in _evidence_targets_for_uri(knowledge, target_uri):
        for subj, _, _ in knowledge.triples((None, CITO_NS.supports, aggregate_target)):
            if isinstance(subj, URIRef):
                record(subj)
        for subj, _, _ in knowledge.triples((None, CITO_NS.disputes, aggregate_target)):
            if isinstance(subj, URIRef):
                record(subj)

    return evidence_types

from __future__ import annotations

from collections import deque
from itertools import combinations
from pathlib import Path
from typing import cast

from rdflib import URIRef
from rdflib.namespace import PROV, RDF, SKOS
from science_model.reasoning import EvidenceType

from science_tool.graph.belief import aggregate_belief, collect_evidence_units
from science_tool.graph.belief_weights import normalize_evidence_type
from science_tool.graph.io import project_root_from_graph_path as _project_root_from_graph_path

from .constants import CITO_NS, PROJECT_NS, SCHEMA_NS, SCI_NS, SCIC_NS
from .dataset import _load_dataset
from .evidence_signals import (
    _collect_evidence_signals,
    _collect_evidence_types,
    _evidence_targets_for_uri,
    _linked_claims_for_hypothesis,
    _load_proposition_bridge_hypotheses,
    _load_proposition_evidence_semantics,
    _load_proposition_falsifications,
    _load_proposition_interaction_terms,
    _load_proposition_pre_registrations,
)
from .identity import _graph_uri, _resolve_center_entity, _short_name
from .types import (
    ClaimSummaryData,
    InquirySummaryData,
    NeighborhoodSummaryData,
    ProjectSummaryData,
    QuestionSummaryData,
)


def _summary_targets(knowledge, *, include_hypotheses: bool) -> list[URIRef]:
    entity_types = [SCI_NS.Proposition]
    if include_hypotheses:
        entity_types.append(SCI_NS.Hypothesis)

    seen: set[URIRef] = set()
    targets: list[URIRef] = []
    for entity_type in entity_types:
        for uri, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not isinstance(uri, URIRef) or uri in seen:
                continue
            seen.add(uri)
            targets.append(uri)
    return targets


_EMPIRICAL_TYPES = frozenset({EvidenceType.EMPIRICAL_DATA, EvidenceType.BENCHMARK})


def _is_empirical_type(evidence_type: str) -> bool:
    """True iff the (possibly suffixed) evidence_type literal is empirical-grade data.

    Normalizes first so canonical ('empirical_data') and authored-suffixed
    ('empirical_data_evidence') literals both classify identically.
    """
    return normalize_evidence_type(evidence_type) in _EMPIRICAL_TYPES


def _claim_summary_data(knowledge, provenance, uri: URIRef) -> ClaimSummaryData | None:
    evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
    support_count = cast(int, evidence_summary["support_count"])
    dispute_count = cast(int, evidence_summary["dispute_count"])
    source_count = cast(int, evidence_summary["source_count"])
    evidence_types = sorted(_collect_evidence_types(knowledge, provenance, uri))
    has_empirical_data = any(_is_empirical_type(evidence_type) for evidence_type in evidence_types)
    belief = aggregate_belief(
        collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, uri))
    )
    belief_state = belief.magnitude.value
    contested = belief.contested
    belief_display = belief.display()
    evidence_semantics = _load_proposition_evidence_semantics(provenance, uri)
    statistical_support = evidence_semantics.get("statistical_support", "")
    mechanistic_support = evidence_semantics.get("mechanistic_support", "")
    replication_scope = evidence_semantics.get("replication_scope", "")
    claim_status = evidence_semantics.get("claim_status", "")
    pre_registrations = _load_proposition_pre_registrations(provenance, uri)
    pre_registration_count = len(pre_registrations)
    interaction_terms = _load_proposition_interaction_terms(provenance, uri)
    interaction_count = len(interaction_terms)
    interaction_modifiers = [f"{term['modifier']}({term['effect']})" for term in interaction_terms]
    bridge_hypotheses = _load_proposition_bridge_hypotheses(provenance, uri)
    bridge_count = len(bridge_hypotheses)
    has_explicit_semantics = any((statistical_support, mechanistic_support, replication_scope, claim_status))

    status_obj = next(provenance.objects(uri, SCI_NS.epistemicStatus), None)
    status = str(status_obj) if status_obj else ""
    conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
    confidence: float | None = None
    if conf_obj is not None:
        try:
            confidence = float(str(conf_obj))
        except ValueError:
            pass

    signals: list[str] = []
    risk_score = 0.0
    total_evidence = support_count + dispute_count
    if contested:
        signals.append("contested")
        risk_score += 3.0
    if support_count > 0 and source_count <= 1:
        signals.append("single_source")
        risk_score += 2.0
    if total_evidence > 0 and not has_empirical_data:
        signals.append("no_empirical_data")
        risk_score += 1.5
    if total_evidence == 0:
        signals.append("no_evidence")
        risk_score += 1.0
    if confidence is not None and confidence < 0.5:
        signals.append("low_confidence")
        risk_score += 1.0 + (0.5 - confidence)
    if _load_proposition_falsifications(knowledge, uri):
        signals.append("falsified")
        risk_score += 3.0
    if claim_status:
        signals.append(f"claim_status:{claim_status}")
        if claim_status in {"null", "weakened"}:
            risk_score += 1.0
        elif claim_status in {"retired", "falsified"}:
            risk_score += 2.0
    if pre_registration_count > 0:
        signals.append("pre_registered")
    if interaction_count > 0:
        signals.append("effect_modified")
    if bridge_count > 0:
        signals.append("cross_hypothesis_bridge")
    if status:
        signals.append(f"status:{status}")
        risk_score += 0.5

    if (
        total_evidence == 0
        and confidence is None
        and not status
        and not has_explicit_semantics
        and pre_registration_count == 0
        and interaction_count == 0
        and bridge_count == 0
    ):
        return None

    text_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
    text = str(text_obj) if text_obj else _short_name(str(uri))
    label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
    label = str(label_obj) if label_obj else text

    return {
        "uri": uri,
        "claim": str(uri),
        "label": label,
        "text": text,
        "belief_state": belief_state,
        "contested": contested,
        "belief_display": belief_display,
        "support_count": support_count,
        "dispute_count": dispute_count,
        "source_count": source_count,
        "evidence_types": evidence_types,
        "has_empirical_data": has_empirical_data,
        "statistical_support": statistical_support,
        "mechanistic_support": mechanistic_support,
        "replication_scope": replication_scope,
        "claim_status": claim_status,
        "pre_registration_count": pre_registration_count,
        "pre_registrations": pre_registrations,
        "interaction_count": interaction_count,
        "interaction_modifiers": interaction_modifiers,
        "bridge_count": bridge_count,
        "bridge_hypotheses": bridge_hypotheses,
        "signals": signals,
        "risk_score": risk_score,
    }


def _format_claim_summary_row(summary: ClaimSummaryData) -> dict[str, str]:
    evidence_types = summary["evidence_types"]
    signals = summary["signals"]
    return {
        "claim": str(summary["claim"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "belief_state": str(summary["belief_state"]),
        "contested": "yes" if bool(summary["contested"]) else "no",
        "belief_display": str(summary["belief_display"]),
        "support_count": str(summary["support_count"]),
        "dispute_count": str(summary["dispute_count"]),
        "source_count": str(summary["source_count"]),
        "evidence_types": "; ".join(evidence_types) if evidence_types else "-",
        "has_empirical_data": "yes" if bool(summary["has_empirical_data"]) else "no",
        "statistical_support": str(summary["statistical_support"]) or "-",
        "mechanistic_support": str(summary["mechanistic_support"]) or "-",
        "replication_scope": str(summary["replication_scope"]) or "-",
        "claim_status": str(summary["claim_status"]) or "-",
        "pre_registration_count": str(summary["pre_registration_count"]),
        "pre_registrations": "; ".join(summary["pre_registrations"]) if summary["pre_registrations"] else "-",
        "interaction_count": str(summary["interaction_count"]),
        "interaction_modifiers": "; ".join(summary["interaction_modifiers"])
        if summary["interaction_modifiers"]
        else "-",
        "bridge_count": str(summary["bridge_count"]),
        "bridge_hypotheses": "; ".join(summary["bridge_hypotheses"]) if summary["bridge_hypotheses"] else "-",
        "signals": "; ".join(signals) if signals else "-",
        "risk_score": f"{summary['risk_score']:.2f}",
    }


def _claim_summaries(knowledge, provenance, *, include_hypotheses: bool) -> list[ClaimSummaryData]:
    rows: list[ClaimSummaryData] = []
    for uri in _summary_targets(knowledge, include_hypotheses=include_hypotheses):
        summary = _claim_summary_data(knowledge, provenance, uri)
        if summary is not None:
            rows.append(summary)
    return rows


def query_dashboard_summary(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    rows = [
        _format_claim_summary_row(summary)
        for summary in _claim_summaries(knowledge, provenance, include_hypotheses=True)
    ]
    rows.sort(key=lambda row: (-float(row["risk_score"]), row["text"]))
    return rows[:top]


def _hypotheses_for_claim(knowledge, claim_uri: URIRef) -> set[URIRef]:
    hypotheses: set[URIRef] = set()

    for _, _, obj in knowledge.triples((claim_uri, CITO_NS.discusses, None)):
        if isinstance(obj, URIRef) and (obj, RDF.type, SCI_NS.Hypothesis) in knowledge:
            hypotheses.add(obj)

    return hypotheses


def _claim_summary_adjacency(knowledge, summary_uris: set[URIRef]) -> dict[URIRef, set[URIRef]]:
    adjacency: dict[URIRef, set[URIRef]] = {uri: set() for uri in summary_uris}
    link_predicates = {CITO_NS.supports, CITO_NS.disputes, CITO_NS.discusses}

    def connect(left: URIRef, right: URIRef) -> None:
        if left == right:
            return
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)

    for subj, predicate, obj in knowledge:
        if predicate not in link_predicates:
            continue
        if isinstance(subj, URIRef) and isinstance(obj, URIRef) and subj in summary_uris and obj in summary_uris:
            connect(subj, obj)

    claims_by_hypothesis: dict[URIRef, set[URIRef]] = {}
    for claim_uri in summary_uris:
        for hypothesis_uri in _hypotheses_for_claim(knowledge, claim_uri):
            claims_by_hypothesis.setdefault(hypothesis_uri, set()).add(claim_uri)

    for claim_group in claims_by_hypothesis.values():
        for left, right in combinations(sorted(claim_group, key=str), 2):
            connect(left, right)

    return adjacency


def _neighborhood_summary_data_rows(knowledge, provenance, *, hops: int) -> list[NeighborhoodSummaryData]:
    summary_rows = _claim_summaries(knowledge, provenance, include_hypotheses=False)
    by_uri: dict[URIRef, ClaimSummaryData] = {summary["uri"]: summary for summary in summary_rows}
    adjacency = _claim_summary_adjacency(knowledge, set(by_uri))

    rows: list[NeighborhoodSummaryData] = []
    for center_uri, center_summary in by_uri.items():
        visited: set[URIRef] = {center_uri}
        queue: deque[tuple[URIRef, int]] = deque([(center_uri, 0)])
        while queue:
            node, depth = queue.popleft()
            if depth >= hops:
                continue
            for neighbor in adjacency.get(node, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

        neighborhood = [by_uri[uri] for uri in sorted(visited, key=str)]
        neighbor_claim_count = max(len(neighborhood) - 1, 0)
        avg_risk_score = sum(float(item["risk_score"]) for item in neighborhood) / len(neighborhood)
        contested_count = sum("contested" in list(item["signals"]) for item in neighborhood)
        single_source_count = sum("single_source" in list(item["signals"]) for item in neighborhood)
        no_empirical_count = sum(not bool(item["has_empirical_data"]) for item in neighborhood)
        structural_fragility = "isolated" if neighbor_claim_count == 0 else "connected"
        neighborhood_risk = (
            avg_risk_score + (0.75 * contested_count) + (0.5 * single_source_count) + (0.5 * no_empirical_count)
        )

        rows.append(
            {
                "center_uri": center_uri,
                "label": str(center_summary["label"]),
                "text": str(center_summary["text"]),
                "neighbor_claim_count": neighbor_claim_count,
                "avg_risk_score": avg_risk_score,
                "contested_count": contested_count,
                "single_source_count": single_source_count,
                "no_empirical_count": no_empirical_count,
                "structural_fragility": structural_fragility,
                "neighborhood_risk": neighborhood_risk,
            }
        )

    return rows


def _format_neighborhood_summary_row(summary: NeighborhoodSummaryData) -> dict[str, str]:
    return {
        "center_claim": str(summary["center_uri"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "neighbor_claim_count": str(summary["neighbor_claim_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_count": str(summary["contested_count"]),
        "single_source_count": str(summary["single_source_count"]),
        "no_empirical_count": str(summary["no_empirical_count"]),
        "structural_fragility": str(summary["structural_fragility"]),
        "neighborhood_risk": f"{summary['neighborhood_risk']:.2f}",
    }


def query_neighborhood_summary(
    graph_path: Path,
    top: int,
    hops: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    rows = [
        _format_neighborhood_summary_row(summary)
        for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=hops)
    ]
    rows.sort(key=lambda row: (-float(row["neighborhood_risk"]), row["text"]))
    return rows[:top]


def _question_claims(knowledge, question_uri: URIRef) -> list[URIRef]:
    claims: set[URIRef] = set()
    for _, _, prop_uri in knowledge.triples((question_uri, SCI_NS.addresses, None)):
        if not isinstance(prop_uri, URIRef):
            continue
        if (prop_uri, RDF.type, SCI_NS.Proposition) in knowledge:
            claims.add(prop_uri)

    for related_uri in knowledge.objects(question_uri, SKOS.related):
        if not isinstance(related_uri, URIRef):
            continue
        if (related_uri, RDF.type, SCI_NS.Hypothesis) not in knowledge:
            continue
        claims.update(_linked_claims_for_hypothesis(knowledge, related_uri))

    return sorted(claims, key=str)


def _inquiry_claims(knowledge, inquiry_graph, inquiry_uri: URIRef) -> tuple[list[URIRef], list[URIRef]]:
    backed_claims: set[URIRef] = set()
    for statement_uri, _, _ in inquiry_graph.triples((None, RDF.type, RDF.Statement)):
        for claim_uri in inquiry_graph.objects(statement_uri, SCI_NS.backedByClaim):
            if isinstance(claim_uri, URIRef) and (claim_uri, RDF.type, SCI_NS.Proposition) in knowledge:
                backed_claims.add(claim_uri)

    targeted_claims: set[URIRef] = set()
    target_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.target), None)
    if isinstance(target_uri, URIRef):
        if (target_uri, RDF.type, SCI_NS.Proposition) in knowledge:
            targeted_claims.add(target_uri)
        elif (target_uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
            targeted_claims.update(_linked_claims_for_hypothesis(knowledge, target_uri))
        elif (target_uri, RDF.type, SCI_NS.Question) in knowledge:
            targeted_claims.update(_question_claims(knowledge, target_uri))

    claim_uris = sorted(backed_claims | targeted_claims, key=str)
    return claim_uris, sorted(backed_claims, key=str)


def _rollup_claim_group(
    claim_uris: list[URIRef],
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
    *,
    grounding_penalty: float = 0.0,
) -> dict[str, float | int]:
    claim_count = len(claim_uris)
    neighborhood_rows = [neighborhood_by_center[uri] for uri in claim_uris if uri in neighborhood_by_center]
    neighborhood_count = len(neighborhood_rows)

    risk_values: list[float] = []
    contested_claim_count = 0
    single_source_claim_count = 0
    no_empirical_claim_count = 0

    for claim_uri in claim_uris:
        summary = claim_by_uri.get(claim_uri)
        if summary is None:
            risk_values.append(1.0)
            no_empirical_claim_count += 1
            continue

        risk_values.append(float(summary["risk_score"]))
        if "contested" in list(summary["signals"]):
            contested_claim_count += 1
        if "single_source" in list(summary["signals"]):
            single_source_claim_count += 1
        if not bool(summary["has_empirical_data"]):
            no_empirical_claim_count += 1

    avg_risk_score = sum(risk_values) / claim_count if claim_count else 0.0
    avg_neighborhood_risk = (
        sum(float(summary["neighborhood_risk"]) for summary in neighborhood_rows) / neighborhood_count
        if neighborhood_count
        else 0.0
    )
    priority_score = (
        avg_risk_score
        + (0.5 * avg_neighborhood_risk)
        + (0.75 * contested_claim_count)
        + (0.5 * single_source_claim_count)
        + (0.5 * no_empirical_claim_count)
        + grounding_penalty
    )

    return {
        "claim_count": claim_count,
        "neighborhood_count": neighborhood_count,
        "avg_risk_score": avg_risk_score,
        "contested_claim_count": contested_claim_count,
        "single_source_claim_count": single_source_claim_count,
        "no_empirical_claim_count": no_empirical_claim_count,
        "priority_score": priority_score,
    }


def _question_summary_data(
    knowledge,
    question_uri: URIRef,
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
) -> QuestionSummaryData:
    question_text_obj = next(knowledge.objects(question_uri, SCHEMA_NS.text), None)
    question_text = str(question_text_obj) if question_text_obj else _short_name(str(question_uri))
    question_label_obj = next(knowledge.objects(question_uri, SKOS.prefLabel), None)
    question_identifier_obj = next(knowledge.objects(question_uri, SCHEMA_NS.identifier), None)
    question_label = (
        str(question_label_obj)
        if question_label_obj
        else str(question_identifier_obj)
        if question_identifier_obj
        else question_text
    )

    metrics = _rollup_claim_group(
        _question_claims(knowledge, question_uri),
        claim_by_uri,
        neighborhood_by_center,
    )
    return {
        "uri": question_uri,
        "question": str(question_uri),
        "label": question_label,
        "text": question_text,
        "claim_count": cast(int, metrics["claim_count"]),
        "neighborhood_count": cast(int, metrics["neighborhood_count"]),
        "avg_risk_score": cast(float, metrics["avg_risk_score"]),
        "contested_claim_count": cast(int, metrics["contested_claim_count"]),
        "single_source_claim_count": cast(int, metrics["single_source_claim_count"]),
        "no_empirical_claim_count": cast(int, metrics["no_empirical_claim_count"]),
        "priority_score": cast(float, metrics["priority_score"]),
    }


def _format_question_summary_row(summary: QuestionSummaryData) -> dict[str, str]:
    return {
        "question": str(summary["question"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "claim_count": str(summary["claim_count"]),
        "neighborhood_count": str(summary["neighborhood_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_claim_count": str(summary["contested_claim_count"]),
        "single_source_claim_count": str(summary["single_source_claim_count"]),
        "no_empirical_claim_count": str(summary["no_empirical_claim_count"]),
        "priority_score": f"{summary['priority_score']:.2f}",
    }


def query_question_summary(
    graph_path: Path,
    top: int | None,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    claim_by_uri = {
        summary["uri"]: summary for summary in _claim_summaries(knowledge, provenance, include_hypotheses=False)
    }
    neighborhood_by_center = {
        summary["center_uri"]: summary for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=1)
    }

    rows = [
        _format_question_summary_row(
            _question_summary_data(knowledge, question_uri, claim_by_uri, neighborhood_by_center)
        )
        for question_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Question))
        if isinstance(question_uri, URIRef)
    ]
    rows.sort(key=lambda row: (-float(row["priority_score"]), row["text"]))
    return rows if top is None else rows[:top]


def _inquiry_summary_data(
    knowledge,
    inquiry_graph,
    inquiry_uri: URIRef,
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
) -> InquirySummaryData:
    claim_uris, backed_claims = _inquiry_claims(knowledge, inquiry_graph, inquiry_uri)
    metrics = _rollup_claim_group(
        claim_uris,
        claim_by_uri,
        neighborhood_by_center,
        grounding_penalty=0.5 if not backed_claims else 0.0,
    )

    label_obj = next(inquiry_graph.objects(inquiry_uri, SKOS.prefLabel), None)
    label = str(label_obj) if label_obj else _short_name(str(inquiry_uri))
    text_obj = next(inquiry_graph.objects(inquiry_uri, SKOS.note), None)
    text = str(text_obj) if text_obj else label
    status_obj = next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryStatus), None)
    inquiry_type_obj = next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), None)

    return {
        "uri": inquiry_uri,
        "inquiry": str(inquiry_uri),
        "label": label,
        "text": text,
        "inquiry_type": str(inquiry_type_obj) if inquiry_type_obj else "general",
        "status": str(status_obj) if status_obj else "",
        "claim_count": cast(int, metrics["claim_count"]),
        "backed_claim_count": len(backed_claims),
        "avg_risk_score": cast(float, metrics["avg_risk_score"]),
        "contested_claim_count": cast(int, metrics["contested_claim_count"]),
        "single_source_claim_count": cast(int, metrics["single_source_claim_count"]),
        "no_empirical_claim_count": cast(int, metrics["no_empirical_claim_count"]),
        "priority_score": cast(float, metrics["priority_score"]),
    }


def _format_inquiry_summary_row(summary: InquirySummaryData) -> dict[str, str]:
    return {
        "inquiry": str(summary["inquiry"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "inquiry_type": str(summary["inquiry_type"]),
        "status": str(summary["status"]) or "-",
        "claim_count": str(summary["claim_count"]),
        "backed_claim_count": str(summary["backed_claim_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_claim_count": str(summary["contested_claim_count"]),
        "single_source_claim_count": str(summary["single_source_claim_count"]),
        "no_empirical_claim_count": str(summary["no_empirical_claim_count"]),
        "priority_score": f"{summary['priority_score']:.2f}",
    }


def query_inquiry_summary(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    claim_by_uri = {
        summary["uri"]: summary for summary in _claim_summaries(knowledge, provenance, include_hypotheses=False)
    }
    neighborhood_by_center = {
        summary["center_uri"]: summary for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=1)
    }

    inquiry_prefix = str(PROJECT_NS) + "inquiry/"
    rows: list[dict[str, str]] = []
    for inquiry_graph in dataset.graphs():
        graph_id = str(inquiry_graph.identifier)
        if not graph_id.startswith(inquiry_prefix):
            continue
        inquiry_uri = URIRef(graph_id)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
            continue

        rows.append(
            _format_inquiry_summary_row(
                _inquiry_summary_data(knowledge, inquiry_graph, inquiry_uri, claim_by_uri, neighborhood_by_center)
            )
        )

    rows.sort(key=lambda row: (-float(row["priority_score"]), row["label"]))
    return rows[:top]


def _project_summary_data(
    project_root: Path,
    profile: str,
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_rows: list[NeighborhoodSummaryData],
    question_rows: list[QuestionSummaryData],
    inquiry_rows: list[InquirySummaryData],
) -> ProjectSummaryData:
    high_risk_neighborhood_count = sum(float(row["neighborhood_risk"]) >= 3.0 for row in neighborhood_rows)
    metrics = _rollup_claim_group(
        sorted(claim_by_uri, key=str),
        claim_by_uri,
        {row["center_uri"]: row for row in neighborhood_rows},
    )

    return {
        "project": str(project_root),
        "profile": profile,
        "question_count": len(question_rows),
        "inquiry_count": len(inquiry_rows),
        "claim_count": cast(int, metrics["claim_count"]),
        "high_risk_neighborhood_count": high_risk_neighborhood_count,
        "avg_risk_score": cast(float, metrics["avg_risk_score"]),
        "contested_claim_count": cast(int, metrics["contested_claim_count"]),
        "single_source_claim_count": cast(int, metrics["single_source_claim_count"]),
        "no_empirical_claim_count": cast(int, metrics["no_empirical_claim_count"]),
        "priority_score": cast(float, metrics["priority_score"]) + (0.5 * high_risk_neighborhood_count),
    }


def _format_project_summary_row(summary: ProjectSummaryData) -> dict[str, str]:
    return {
        "project": summary["project"],
        "profile": summary["profile"],
        "question_count": str(summary["question_count"]),
        "inquiry_count": str(summary["inquiry_count"]),
        "claim_count": str(summary["claim_count"]),
        "high_risk_neighborhood_count": str(summary["high_risk_neighborhood_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_claim_count": str(summary["contested_claim_count"]),
        "single_source_claim_count": str(summary["single_source_claim_count"]),
        "no_empirical_claim_count": str(summary["no_empirical_claim_count"]),
        "priority_score": f"{summary['priority_score']:.2f}",
    }


def query_project_summary(graph_path: Path) -> list[dict[str, str]]:
    from science_tool.paths import resolve_paths

    project_root = _project_root_from_graph_path(graph_path).resolve()
    profile = resolve_paths(project_root).profile
    if profile != "research":
        raise ValueError("project-summary is currently defined only for research projects")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    claim_rows = _claim_summaries(knowledge, provenance, include_hypotheses=False)
    claim_by_uri = {summary["uri"]: summary for summary in claim_rows}
    neighborhood_rows = _neighborhood_summary_data_rows(knowledge, provenance, hops=1)
    neighborhood_by_center = {summary["center_uri"]: summary for summary in neighborhood_rows}
    question_rows = [
        _question_summary_data(knowledge, question_uri, claim_by_uri, neighborhood_by_center)
        for question_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Question))
        if isinstance(question_uri, URIRef)
    ]

    inquiry_prefix = str(PROJECT_NS) + "inquiry/"
    inquiry_rows: list[InquirySummaryData] = []
    for inquiry_graph in dataset.graphs():
        graph_id = str(inquiry_graph.identifier)
        if not graph_id.startswith(inquiry_prefix):
            continue
        inquiry_uri = URIRef(graph_id)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
            continue
        inquiry_rows.append(
            _inquiry_summary_data(knowledge, inquiry_graph, inquiry_uri, claim_by_uri, neighborhood_by_center)
        )

    return [
        _format_project_summary_row(
            _project_summary_data(project_root, profile, claim_by_uri, neighborhood_rows, question_rows, inquiry_rows)
        )
    ]


def query_coverage(
    graph_path: Path,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    causal = dataset.graph(_graph_uri("graph/causal"))
    datasets_graph = dataset.graph(_graph_uri("graph/datasets"))

    entity_uris: set[URIRef] = set()
    for uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Concept)):
        if isinstance(uri, URIRef):
            entity_uris.add(uri)
    for uri, _, _ in causal.triples((None, RDF.type, SCIC_NS.Variable)):
        if isinstance(uri, URIRef):
            entity_uris.add(uri)

    rows: list[dict[str, str]] = []
    for uri in sorted(entity_uris, key=str):
        label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
        label = str(label_obj) if label_obj else _short_name(str(uri))

        measured = any(datasets_graph.triples((uri, SCI_NS.measuredBy, None)))

        observed_lit = next(causal.objects(uri, SCIC_NS.isObserved), None)
        if observed_lit is not None:
            observed = str(observed_lit).lower() in ("true", "1")
            observed_str = "yes" if observed else "no"
        else:
            observed_str = "-"

        rows.append(
            {
                "entity": str(uri),
                "label": label,
                "measured": "yes" if measured else "no",
                "observed": observed_str,
            }
        )
    return rows[:limit]


def query_gaps(
    graph_path: Path,
    center: str,
    hops: int,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    center_uri = _resolve_center_entity(center)

    # BFS to find neighborhood entities
    adjacency: dict[URIRef, set[URIRef]] = {}
    for subj, _, obj in knowledge:
        if not isinstance(subj, URIRef) or not isinstance(obj, URIRef):
            continue
        adjacency.setdefault(subj, set()).add(obj)
        adjacency.setdefault(obj, set()).add(subj)

    visited: set[URIRef] = {center_uri}
    queue: deque[tuple[URIRef, int]] = deque([(center_uri, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbor in adjacency.get(node, set()):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, depth + 1))

    rows: list[dict[str, str]] = []
    for uri in sorted(visited, key=str):
        issues: list[str] = []

        # Low connectivity
        degree = len(adjacency.get(uri, set()))
        if degree <= 1:
            issues.append(f"structural_fragility(low_connectivity,degree={degree})")

        # Proposition and hypothesis evidence/provenance fragility
        if (uri, RDF.type, SCI_NS.Proposition) in knowledge or (uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
            if not any(provenance.triples((uri, PROV.wasDerivedFrom, None))):
                issues.append("missing_provenance")

            evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
            support_count = int(evidence_summary["support_count"])
            dispute_count = int(evidence_summary["dispute_count"])
            total_evidence = support_count + dispute_count
            source_count = int(evidence_summary["source_count"])
            belief = aggregate_belief(
                collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, uri))
            )
            if belief.contested:
                issues.append("evidential_fragility(contested)")
            if total_evidence > 0 and source_count <= 1:
                issues.append("evidential_fragility(single_source)")

        # Low confidence
        conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
        if conf_obj is not None:
            try:
                conf = float(str(conf_obj))
                if conf < 0.5:
                    issues.append(f"authored_low_confidence({conf:.2f})")
            except ValueError:
                pass

        if issues:
            label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
            if label_obj is None:
                label_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
            label = str(label_obj) if label_obj else _short_name(str(uri))

            rows.append(
                {
                    "entity": str(uri),
                    "label": label,
                    "issues": "; ".join(issues),
                }
            )
    return rows[:limit]


def query_uncertainty(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    uncertain_statuses = {"disputed", "hypothesized"}

    rows: list[dict[str, str]] = []
    # Collect all entities with epistemic metadata
    seen: set[URIRef] = set()
    for entity_type in (SCI_NS.Proposition, SCI_NS.Hypothesis):
        for uri, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not isinstance(uri, URIRef) or uri in seen:
                continue
            seen.add(uri)

            status_obj = next(provenance.objects(uri, SCI_NS.epistemicStatus), None)
            status = str(status_obj) if status_obj else ""

            conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
            confidence: float | None = None
            if conf_obj is not None:
                try:
                    confidence = float(str(conf_obj))
                except ValueError:
                    pass

            evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
            support_count = int(evidence_summary["support_count"])
            dispute_count = int(evidence_summary["dispute_count"])
            source_count = int(evidence_summary["source_count"])
            signals: list[str] = []
            risk_score = 0.0

            belief = aggregate_belief(
                collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, uri))
            )
            if belief.contested:
                signals.append("contested")
                risk_score += 3.0

            total_evidence = support_count + dispute_count
            if total_evidence > 0 and source_count <= 1:
                signals.append("single_source")
                risk_score += 2.0

            is_uncertain_status = status.lower() in uncertain_statuses
            if is_uncertain_status:
                signals.append(f"status:{status.lower()}")
                risk_score += 1.5

            is_low_confidence = confidence is not None and confidence < 0.5
            if is_low_confidence and confidence is not None:
                signals.append("low_confidence")
                risk_score += 1.0 + (0.5 - confidence)

            if not signals:
                continue

            text_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
            text = str(text_obj) if text_obj else _short_name(str(uri))

            rows.append(
                {
                    "entity": str(uri),
                    "text": text,
                    "status": status or "-",
                    "confidence": f"{confidence:.2f}" if confidence is not None else "-",
                    "signals": "; ".join(signals),
                    "support_count": str(support_count),
                    "dispute_count": str(dispute_count),
                    "_sort": str(risk_score),
                }
            )

    rows.sort(key=lambda r: float(r["_sort"]), reverse=True)
    for row in rows:
        del row["_sort"]
    return rows[:top]

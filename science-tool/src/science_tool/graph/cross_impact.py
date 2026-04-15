"""Conservative cross-impact queries for layered-claim graph updates."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TypedDict

import click
from rdflib import URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.graph.store import (
    CITO_NS,
    PROJECT_NS,
    SCI_NS,
    SCHEMA_NS,
    _load_dataset,
    _resolve_center_entity,
    shorten_uri,
)

_SCOPE_LABELS: tuple[str, ...] = ("local", "bundle-level", "cross-hypothesis", "project-wide")
_SCOPE_RANK: dict[str, int] = {label: index for index, label in enumerate(_SCOPE_LABELS)}
_SCOPE_HINT_RANK: dict[str, int] = {
    "local_proposition": _SCOPE_RANK["local"],
    "hypothesis_bundle": _SCOPE_RANK["bundle-level"],
    "cross_hypothesis": _SCOPE_RANK["cross-hypothesis"],
    "project_wide": _SCOPE_RANK["project-wide"],
}


class CrossImpactRow(TypedDict):
    dependent_proposition: str
    dependent_text: str
    relation: str
    hypotheses: str
    interpretations: str
    discussions: str
    questions: str
    scope: str
    scope_reason: str


class CrossImpactPayload(TypedDict):
    target: str
    target_text: str
    scope: str
    scope_reason: str
    rows: list[CrossImpactRow]


def query_cross_impact(graph_path: Path, target_ref: str, limit: int) -> CrossImpactPayload:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    target_uri, target_kind = _resolve_cross_impact_target(knowledge, provenance, target_ref)
    target_text = _entity_text(knowledge, target_uri)

    indexes = _build_cross_impact_indexes(knowledge, provenance)
    rows = _build_cross_impact_rows(knowledge=knowledge, provenance=provenance, target_uri=target_uri, indexes=indexes)

    if limit >= 0:
        rows = rows[:limit]

    scope = _scope_label_from_rank(
        max(
            [_scope_rank_for_row(row["scope"]) for row in rows] + [_scope_rank_for_hints(provenance, target_uri)],
            default=_SCOPE_RANK["local"],
        )
    )
    scope_reason = _payload_scope_reason(rows, provenance, target_uri)

    return {
        "target": shorten_uri(str(target_uri)),
        "target_text": target_text,
        "scope": scope,
        "scope_reason": scope_reason,
        "rows": rows,
    }


def _build_cross_impact_rows(
    *,
    knowledge,
    provenance,
    target_uri: URIRef,
    indexes: dict[str, dict[URIRef, set[URIRef]]],
) -> list[CrossImpactRow]:
    rows: list[CrossImpactRow] = []
    seen: set[tuple[str, str]] = set()

    for relation_uri, relation_label in ((CITO_NS.supports, "supports"), (CITO_NS.disputes, "disputes")):
        for dependent_uri, _, _ in knowledge.triples((None, relation_uri, target_uri)):
            if not isinstance(dependent_uri, URIRef):
                continue
            key = (str(dependent_uri), relation_label)
            if key in seen:
                continue
            seen.add(key)
            row = _build_cross_impact_row(
                knowledge=knowledge,
                provenance=provenance,
                dependent_uri=dependent_uri,
                relation_label=relation_label,
                indexes=indexes,
                target_uri=target_uri,
            )
            rows.append(row)

    rows.sort(key=lambda row: (row["dependent_proposition"], row["relation"]))
    return rows


def _build_cross_impact_row(
    *,
    knowledge,
    provenance,
    dependent_uri: URIRef,
    relation_label: str,
    indexes: dict[str, dict[URIRef, set[URIRef]]],
    target_uri: URIRef,
) -> CrossImpactRow:
    hypotheses = sorted(shorten_uri(str(uri)) for uri in indexes["proposition_hypotheses"].get(dependent_uri, set()))
    interpretations = sorted(
        shorten_uri(str(uri))
        for finding_uri in indexes["proposition_findings"].get(dependent_uri, set())
        for uri in indexes["finding_interpretations"].get(finding_uri, set())
    )
    discussions = sorted(shorten_uri(str(uri)) for uri in indexes["proposition_discussions"].get(dependent_uri, set()))
    questions = sorted(
        shorten_uri(str(uri))
        for uri in _questions_for_proposition(dependent_uri, hypotheses, indexes)
    )
    row_scope_rank, scope_reason = _classify_scope(
        provenance=provenance,
        proposition_uri=dependent_uri,
        hypotheses=hypotheses,
        target_uri=target_uri,
    )

    return {
        "dependent_proposition": shorten_uri(str(dependent_uri)),
        "dependent_text": _entity_text(knowledge, dependent_uri),
        "relation": relation_label,
        "hypotheses": "; ".join(hypotheses) if hypotheses else "-",
        "interpretations": "; ".join(interpretations) if interpretations else "-",
        "discussions": "; ".join(discussions) if discussions else "-",
        "questions": "; ".join(questions) if questions else "-",
        "scope": _scope_label_from_rank(row_scope_rank),
        "scope_reason": scope_reason,
    }


def _build_cross_impact_indexes(knowledge, provenance) -> dict[str, dict[URIRef, set[URIRef]]]:
    proposition_hypotheses: dict[URIRef, set[URIRef]] = defaultdict(set)
    proposition_findings: dict[URIRef, set[URIRef]] = defaultdict(set)
    finding_interpretations: dict[URIRef, set[URIRef]] = defaultdict(set)
    proposition_discussions: dict[URIRef, set[URIRef]] = defaultdict(set)
    proposition_questions: dict[URIRef, set[URIRef]] = defaultdict(set)
    hypothesis_questions: dict[URIRef, set[URIRef]] = defaultdict(set)

    for prop_uri, _, hyp_uri in knowledge.triples((None, CITO_NS.discusses, None)):
        if not isinstance(prop_uri, URIRef) or not isinstance(hyp_uri, URIRef):
            continue
        if (hyp_uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
            proposition_hypotheses[prop_uri].add(hyp_uri)

    for finder_uri, _, prop_uri in knowledge.triples((None, SCI_NS.contains, None)):
        if not isinstance(finder_uri, URIRef) or not isinstance(prop_uri, URIRef):
            continue
        if (finder_uri, RDF.type, SCI_NS.Finding) in knowledge and (prop_uri, RDF.type, SCI_NS.Proposition) in knowledge:
            proposition_findings[prop_uri].add(finder_uri)

    for interp_uri, _, finding_uri in knowledge.triples((None, SCI_NS.contains, None)):
        if not isinstance(interp_uri, URIRef) or not isinstance(finding_uri, URIRef):
            continue
        if (interp_uri, RDF.type, SCI_NS.Interpretation) in knowledge and (finding_uri, RDF.type, SCI_NS.Finding) in knowledge:
            finding_interpretations[finding_uri].add(interp_uri)

    for disc_uri, _, prop_uri in knowledge.triples((None, SCI_NS.contains, None)):
        if not isinstance(disc_uri, URIRef) or not isinstance(prop_uri, URIRef):
            continue
        if (disc_uri, RDF.type, SCI_NS.Discussion) in knowledge and (prop_uri, RDF.type, SCI_NS.Proposition) in knowledge:
            proposition_discussions[prop_uri].add(disc_uri)

    for question_uri, _, prop_uri in knowledge.triples((None, SCI_NS.addresses, None)):
        if not isinstance(question_uri, URIRef) or not isinstance(prop_uri, URIRef):
            continue
        if (question_uri, RDF.type, SCI_NS.Question) in knowledge and (prop_uri, RDF.type, SCI_NS.Proposition) in knowledge:
            proposition_questions[prop_uri].add(question_uri)

    for question_uri in knowledge.subjects(RDF.type, SCI_NS.Question):
        if not isinstance(question_uri, URIRef):
            continue
        for hypothesis_uri in knowledge.objects(question_uri, SKOS.related):
            if isinstance(hypothesis_uri, URIRef) and (hypothesis_uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
                hypothesis_questions[hypothesis_uri].add(question_uri)

    return {
        "proposition_hypotheses": proposition_hypotheses,
        "proposition_findings": proposition_findings,
        "finding_interpretations": finding_interpretations,
        "proposition_discussions": proposition_discussions,
        "proposition_questions": proposition_questions,
        "hypothesis_questions": hypothesis_questions,
    }


def _questions_for_proposition(
    proposition_uri: URIRef,
    hypotheses: list[str],
    indexes: dict[str, dict[URIRef, set[URIRef]]],
) -> set[URIRef]:
    questions = set(indexes["proposition_questions"].get(proposition_uri, set()))
    for hypothesis_text in hypotheses:
        hypothesis_uri = _resolve_cross_impact_ref(hypothesis_text)
        questions.update(indexes["hypothesis_questions"].get(hypothesis_uri, set()))
    return questions


def _resolve_cross_impact_ref(value: str) -> URIRef:
    if value.startswith("http://") or value.startswith("https://"):
        return URIRef(value)
    if ":" in value or "/" in value:
        from science_tool.graph.store import _resolve_term

        return _resolve_term(value)
    return URIRef(PROJECT_NS[f"concept/{value}"])


def _resolve_cross_impact_target(
    knowledge,
    provenance,
    target_ref: str,
) -> tuple[URIRef, str]:
    target_uri = _resolve_center_entity(target_ref)
    if (target_uri, RDF.type, SCI_NS.Proposition) in knowledge:
        return target_uri, "proposition"

    if (target_uri, RDF.type, RDF.Statement) in provenance:
        anchor_uri = next(provenance.objects(target_uri, RDF.object), None)
        if isinstance(anchor_uri, URIRef) and (anchor_uri, RDF.type, SCI_NS.Proposition) in knowledge:
            return anchor_uri, "evidence_line"
        raise click.ClickException(f"Cross-impact target evidence line has no proposition object: {target_ref}")

    raise click.ClickException(f"Cross-impact target not found: {target_ref}")


def _classify_scope(
    *,
    provenance,
    proposition_uri: URIRef,
    hypotheses: list[str],
    target_uri: URIRef,
) -> tuple[int, str]:
    base_rank = _SCOPE_RANK["local"]
    if len(hypotheses) == 1:
        base_rank = _SCOPE_RANK["bundle-level"]
    elif len(hypotheses) > 1:
        base_rank = _SCOPE_RANK["cross-hypothesis"]

    scope_hints = [
        _SCOPE_HINT_RANK[str(scope_obj)]
        for scope_obj in provenance.objects(target_uri, SCI_NS.supportsScope)
        if str(scope_obj) in _SCOPE_HINT_RANK
    ]
    max_rank = max([base_rank, *scope_hints], default=base_rank)
    reason_bits = ["direct_link"]
    if hypotheses:
        reason_bits.append("hypothesis_bundle")
    if scope_hints:
        scope_value = _scope_label_from_rank(max(scope_hints))
        reason_bits.append(f"supports_scope({scope_value.replace('-', '_')})")
    return max_rank, " + ".join(reason_bits)


def _scope_rank_for_row(scope_label: str) -> int:
    return _SCOPE_RANK.get(scope_label, _SCOPE_RANK["local"])


def _scope_rank_for_hints(provenance, target_uri: URIRef) -> int:
    ranks = [
        _SCOPE_HINT_RANK[str(scope_obj)]
        for scope_obj in provenance.objects(target_uri, SCI_NS.supportsScope)
        if str(scope_obj) in _SCOPE_HINT_RANK
    ]
    return max(ranks, default=_SCOPE_RANK["local"])


def _scope_label_from_rank(rank: int) -> str:
    return _SCOPE_LABELS[min(max(rank, 0), len(_SCOPE_LABELS) - 1)]


def _payload_scope_reason(rows: list[CrossImpactRow], provenance, target_uri: URIRef) -> str:
    if rows:
        widest_row = max(rows, key=lambda row: _scope_rank_for_row(row["scope"]))
        reasons = [widest_row["scope_reason"]]
    else:
        reasons = ["direct_link"]

    hint_values = [
        str(scope_obj)
        for scope_obj in provenance.objects(target_uri, SCI_NS.supportsScope)
        if str(scope_obj) in _SCOPE_HINT_RANK
    ]
    if hint_values:
        hint_reason = f"supports_scope({max(hint_values, key=lambda value: _SCOPE_HINT_RANK[value])})"
        if hint_reason not in reasons[-1]:
            reasons.append(hint_reason)

    return " + ".join(reasons)


def _entity_text(knowledge, uri: URIRef) -> str:
    for predicate in (SCHEMA_NS.text, SCHEMA_NS.description, SKOS.prefLabel):
        value = next(knowledge.objects(uri, predicate), None)
        if value is not None:
            return str(value)
    return shorten_uri(str(uri))


def _graph_uri(layer: str) -> URIRef:
    return URIRef(PROJECT_NS[layer])

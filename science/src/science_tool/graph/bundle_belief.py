"""Bundle belief roll-up (design doc 2026-06-11-bundle-belief-rollup-design.md).

A hypothesis/mechanism bundle's belief is derived from its member propositions
under an explicit composition rule. v1 implements weakest-link only.
"""
from __future__ import annotations

from rdflib import RDF, URIRef

from science_model.reasoning import CompositionRule
from .io import CITO_NS, SCI_NS

_BUNDLE_TYPES: dict[str, URIRef] = {
    "hypothesis": SCI_NS.Hypothesis,
    "mechanism": SCI_NS.Mechanism,
}
_KIND_DEFAULT_RULE: dict[str, CompositionRule] = {
    "hypothesis": CompositionRule.CONJUNCTIVE,
    "mechanism": CompositionRule.ALL_STEPS,
}


def bundle_kind(knowledge, uri: URIRef) -> str | None:
    """Return 'hypothesis'/'mechanism' if `uri` is a bundle type, else None."""
    for kind, type_uri in _BUNDLE_TYPES.items():
        if (uri, RDF.type, type_uri) in knowledge:
            return kind
    return None


def bundle_members(knowledge, uri: URIRef) -> list[URIRef]:
    """Direct member propositions: forward sci:hasProposition ∪ reverse cito:discusses.

    Restricted to Proposition-typed targets; non-transitive; deterministic order.
    """
    members: list[URIRef] = []
    seen: set[URIRef] = set()

    def _add(node) -> None:
        if (
            isinstance(node, URIRef)
            and node not in seen
            and (node, RDF.type, SCI_NS.Proposition) in knowledge
        ):
            seen.add(node)
            members.append(node)

    for _, _, obj in knowledge.triples((uri, SCI_NS.hasProposition, None)):
        _add(obj)
    for subj, _, _ in knowledge.triples((None, CITO_NS.discusses, uri)):
        _add(subj)

    members.sort(key=str)
    return members


def resolve_composition_rule(provenance, uri: URIRef, kind: str) -> CompositionRule:
    """Authored sci:compositionRule if present, else the per-kind default."""
    value = provenance.value(uri, SCI_NS.compositionRule)
    if value is not None:
        return CompositionRule(str(value))
    return _KIND_DEFAULT_RULE[kind]

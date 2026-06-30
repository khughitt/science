from __future__ import annotations

import hashlib
from dataclasses import dataclass

from rdflib import URIRef
from science_model.reasoning import EvidenceRole, EvidenceStance, EvidenceStrength, EvidenceType, IndependenceTag

from science_tool.graph.io import PROJECT_NS


@dataclass(frozen=True)
class LiteratureAssertion:
    proposition_ref: str
    paper_ref: str
    stance: str
    annotation_id: str
    sidecar: str


@dataclass(frozen=True)
class AssertionFault:
    sidecar: str
    annotation_id: str
    reason: str
    detail: str


class CrossPaperEvidenceError(Exception):
    def __init__(self, faults: tuple[AssertionFault, ...]) -> None:
        self.faults = faults
        super().__init__(str(self))

    def __str__(self) -> str:
        lines = ["cross-paper evidence faults:"]
        lines.extend(
            f"{idx}. {fault.sidecar}:{fault.annotation_id} {fault.reason}: {fault.detail}"
            for idx, fault in enumerate(self.faults, start=1)
        )
        return "\n".join(lines)


ACTIVE_STATUSES: frozenset[str] = frozenset({"open", "ack"})
DERIVED_STANCES: frozenset[str] = frozenset({"asserted", "negated", "hypothesized"})
KNOWN_STANCES: frozenset[str] = DERIVED_STANCES | {"open"}

LITERATURE_TYPE = EvidenceType.LITERATURE.value
INDEPENDENT = IndependenceTag.INDEPENDENT.value
STANCE_EMIT: dict[str, tuple[str, str, str]] = {
    "asserted": (
        EvidenceStance.SUPPORTS.value,
        EvidenceRole.PROXY_SUPPORT.value,
        EvidenceStrength.MODERATE.value,
    ),
    "negated": (
        EvidenceStance.DISPUTES.value,
        EvidenceRole.PROXY_SUPPORT.value,
        EvidenceStrength.MODERATE.value,
    ),
    "hypothesized": (
        EvidenceStance.SUPPORTS.value,
        EvidenceRole.BACKGROUND_CONSTRAINT.value,
        EvidenceStrength.WEAK.value,
    ),
}


def lit_assertion_uri(proposition_ref: str, paper_ref: str, stance: str) -> URIRef:
    key = f"{proposition_ref}\0{paper_ref}\0{stance}".encode()
    digest = hashlib.sha256(key).hexdigest()
    return URIRef(PROJECT_NS[f"evidence-line/lit-assertion/{digest}"])


def collapse_assertions(assertions: list[LiteratureAssertion]) -> list[LiteratureAssertion]:
    by_key: dict[tuple[str, str, str], LiteratureAssertion] = {}
    for assertion in assertions:
        key = (assertion.proposition_ref, assertion.paper_ref, assertion.stance)
        existing = by_key.get(key)
        if existing is None or assertion.annotation_id < existing.annotation_id:
            by_key[key] = assertion

    return [by_key[key] for key in sorted(by_key)]

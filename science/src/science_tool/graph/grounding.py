"""Read-only proposition grounding from materialized evidence-line belief."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rdflib import Graph, RDF, URIRef

from science_tool.graph.belief import BeliefMagnitude, aggregate_belief, collect_evidence_units
from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.graph.store import _graph_uri, _load_dataset
from science_tool.graph.store.evidence_signals import _evidence_targets_for_uri

DEFAULT_GROUNDING_FLOOR = BeliefMagnitude.SUPPORTED.value

_MAGNITUDE_ORDER = [
    BeliefMagnitude.SPECULATIVE.value,
    BeliefMagnitude.FRAGILE.value,
    BeliefMagnitude.SUPPORTED.value,
    BeliefMagnitude.WELL_SUPPORTED.value,
]


class GroundingError(ValueError):
    pass


class GroundingStatus(StrEnum):
    GROUNDED = "grounded"
    BELOW_FLOOR = "below_floor"
    UNBACKED = "unbacked"


@dataclass(frozen=True)
class GroundingResult:
    target_ref: str
    status: GroundingStatus
    belief_magnitude: str
    belief_display: str
    floor: str
    contested: bool
    support_units: int
    dispute_units: int
    diagnostic_units: int
    excluded_units: int
    flagged_ungrouped_units: int
    capped_by_refutation: bool
    authored_capped: bool
    qa_dataset_capped: bool
    policy_id: str
    policy_version: str

    def to_json(self) -> dict[str, str | bool | int]:
        return {
            "target_ref": self.target_ref,
            "status": self.status.value,
            "belief_magnitude": self.belief_magnitude,
            "belief_display": self.belief_display,
            "floor": self.floor,
            "contested": self.contested,
            "support_units": self.support_units,
            "dispute_units": self.dispute_units,
            "diagnostic_units": self.diagnostic_units,
            "excluded_units": self.excluded_units,
            "flagged_ungrouped_units": self.flagged_ungrouped_units,
            "capped_by_refutation": self.capped_by_refutation,
            "authored_capped": self.authored_capped,
            "qa_dataset_capped": self.qa_dataset_capped,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
        }


def load_grounding_graphs(graph_path: Path) -> tuple[Graph, Graph]:
    if not graph_path.exists():
        raise GroundingError(f"graph file not found: {graph_path}")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    if len(knowledge) == 0:
        raise GroundingError(f"knowledge graph is empty: {graph_path}")
    return knowledge, provenance


def ground_proposition(
    ref_or_uri: str | URIRef,
    knowledge: Graph,
    provenance: Graph,
    *,
    floor: str = DEFAULT_GROUNDING_FLOOR,
) -> GroundingResult:
    floor = _validate_floor(floor)
    target_uri = _target_uri(ref_or_uri)
    _require_proposition_target(knowledge, target_uri, ref_or_uri)

    units = collect_evidence_units(
        knowledge,
        provenance,
        _evidence_targets_for_uri(knowledge, target_uri),
    )
    belief = aggregate_belief(units)
    magnitude = belief.magnitude.value
    status = _status(len(belief.support_units), magnitude, floor)

    return GroundingResult(
        target_ref=_target_ref(target_uri),
        status=status,
        belief_magnitude=magnitude,
        belief_display=belief.display(),
        floor=floor,
        contested=belief.contested,
        support_units=len(belief.support_units),
        dispute_units=len(belief.dispute_units),
        diagnostic_units=len(belief.diagnostics),
        excluded_units=len(belief.excluded),
        flagged_ungrouped_units=len(belief.flagged_ungrouped),
        capped_by_refutation=belief.capped_by_refutation,
        authored_capped=belief.authored_capped,
        qa_dataset_capped=belief.qa_dataset_capped,
        policy_id=belief.policy_id,
        policy_version=belief.policy_version,
    )


def ground_propositions(
    refs_or_uris: list[str | URIRef],
    knowledge: Graph,
    provenance: Graph,
    *,
    floor: str = DEFAULT_GROUNDING_FLOOR,
) -> list[GroundingResult]:
    return [
        ground_proposition(ref_or_uri, knowledge, provenance, floor=floor)
        for ref_or_uri in refs_or_uris
    ]


def _validate_floor(floor: str) -> str:
    try:
        magnitude = BeliefMagnitude(floor)
    except ValueError as exc:
        raise GroundingError(f"unknown grounding floor: {floor}") from exc
    return magnitude.value


def _target_uri(ref_or_uri: str | URIRef) -> URIRef:
    if isinstance(ref_or_uri, URIRef):
        return ref_or_uri

    if ref_or_uri.startswith(("http://", "https://")):
        return URIRef(ref_or_uri)

    if not ref_or_uri.startswith("proposition:"):
        raise GroundingError(f"invalid proposition target ref: {ref_or_uri}")

    slug = ref_or_uri.removeprefix("proposition:").strip().lower()
    if not slug:
        raise GroundingError(f"invalid proposition target ref: {ref_or_uri}")
    return URIRef(PROJECT_NS[f"proposition/{slug}"])


def _target_ref(target_uri: URIRef) -> str:
    prefix = str(PROJECT_NS["proposition/"])
    target = str(target_uri)
    if target.startswith(prefix):
        return f"proposition:{target.removeprefix(prefix)}"
    return target


def _require_proposition_target(knowledge: Graph, target_uri: URIRef, original: str | URIRef) -> None:
    if (target_uri, RDF.type, SCI_NS.Proposition) not in knowledge:
        raise GroundingError(f"proposition target not found in knowledge graph: {original}")


def _status(support_count: int, magnitude: str, floor: str) -> GroundingStatus:
    if support_count == 0:
        return GroundingStatus.UNBACKED
    if _MAGNITUDE_ORDER.index(magnitude) >= _MAGNITUDE_ORDER.index(floor):
        return GroundingStatus.GROUNDED
    return GroundingStatus.BELOW_FLOOR

"""Independence-aware evidence aggregation -> ordinal belief (design §2/§3, Phase 1)."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rdflib import Graph, RDF, URIRef
from rdflib.namespace import PROV

from .io import CITO_NS, SCI_NS

EVIDENCE_LINE_CLASS = SCI_NS.EvidenceLine  # rdf:type minted by materialize.py _kind_class_name("evidence-line")


@dataclass(frozen=True)
class EvidenceUnit:
    line_uri: str
    stance: str                       # "supports" | "disputes"
    strength: str | None
    independence: str | None
    independence_group: str | None
    evidence_role: str | None
    evidence_type: str | None
    dispute_scope: str | None
    proxy_directness: str | None
    has_measurement_model: bool
    source: str | None
    observability_keys: tuple[str, ...]


_OBSERVABILITY = {
    "shared_dataset": SCI_NS.sharedDataset,
    "shared_lab": SCI_NS.sharedLab,
    "shared_platform": SCI_NS.sharedPlatform,
    "shared_cohort": SCI_NS.sharedCohort,
}


def _lit(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    for _, _, value in graph.triples((subject, predicate, None)):
        return str(value)
    return None


def _read_unit(provenance: Graph, line: URIRef, stance: str) -> EvidenceUnit:
    obs = tuple(name for name, pred in _OBSERVABILITY.items() if _lit(provenance, line, pred))
    return EvidenceUnit(
        line_uri=str(line),
        stance=stance,
        strength=_lit(provenance, line, SCI_NS.evidenceStrength),
        independence=_lit(provenance, line, SCI_NS.evidenceIndependence),
        independence_group=_lit(provenance, line, SCI_NS.independenceGroup),
        evidence_role=_lit(provenance, line, SCI_NS.evidenceRole),
        evidence_type=_lit(provenance, line, SCI_NS.evidenceType),
        dispute_scope=_lit(provenance, line, SCI_NS.disputeScope),
        proxy_directness=_lit(provenance, line, SCI_NS.proxyDirectness),
        has_measurement_model=_lit(provenance, line, SCI_NS.measurementModel) is not None,
        # Informational only; NOT consumed by Phase 1 aggregation. A line has multiple
        # prov:wasDerivedFrom objects (its source file AND source entity); first wins.
        source=_lit(provenance, line, PROV.wasDerivedFrom),
        observability_keys=obs,
    )


def collect_evidence_units(
    knowledge: Graph, provenance: Graph, targets: Iterable[URIRef]
) -> list[EvidenceUnit]:
    """Counted units are ONLY cito edges whose subject is an evidence-line (design §Prerequisite).

    Edge + rdf:type are read from `knowledge`; per-line metadata from `provenance`.
    `targets` is the expanded target set; callers pass `_evidence_targets_for_uri(...)` so a
    hypothesis sees its linked claims' evidence. Lines are de-duped by URI so a line bearing on
    multiple targets counts once.
    """
    units: list[EvidenceUnit] = []
    seen: set[str] = set()
    for target in targets:
        for predicate, stance in ((CITO_NS.supports, "supports"), (CITO_NS.disputes, "disputes")):
            for subject, _, _ in knowledge.triples((None, predicate, target)):
                if (subject, RDF.type, EVIDENCE_LINE_CLASS) not in knowledge:
                    continue
                if str(subject) in seen:
                    continue
                seen.add(str(subject))
                units.append(_read_unit(provenance, subject, stance))
    return units

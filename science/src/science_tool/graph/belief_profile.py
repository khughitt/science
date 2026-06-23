from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import RDF, URIRef
from rdflib.namespace import SKOS

from .belief import BeliefResult, EvidenceUnit, is_authored_assertion
from .belief_scalar import BeliefScalar, belief_scalar, belief_scalar_enabled
from .belief_weights import normalize_evidence_type
from .bundle_belief import BundleBeliefResult, belief_for_entity, bundle_kind
from .io import PROJECT_NS, SCI_NS, project_root_from_graph_path
from .store import _graph_uri, _load_dataset
from .store.summary import is_empirical_evidence_type

SUPPORTED_KINDS: tuple[str, ...] = ("proposition", "hypothesis", "mechanism")
PROFILE_LABELS: tuple[str, ...] = (
    "speculative",
    "fragile",
    "supported",
    "well_supported",
    "contested",
    "single_source",
    "no_empirical_data",
    "authored_only",
    "literature_only",
    "empirical_data_backed",
    "authored_capped",
    "qa_dataset_capped",
    "capped_by_refutation",
    "stale",
    "needs_review",
)
_KIND_TYPES = {
    "proposition": SCI_NS.Proposition,
    "hypothesis": SCI_NS.Hypothesis,
    "mechanism": SCI_NS.Mechanism,
}


@dataclass(frozen=True)
class _EvidenceSummary:
    support_count: int
    dispute_count: int
    diagnostic_count: int | None
    source_count: int
    evidence_types: list[str]
    has_empirical_data: bool
    support_units: tuple[EvidenceUnit, ...]
    all_units: tuple[EvidenceUnit, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "support_count": self.support_count,
            "dispute_count": self.dispute_count,
            "diagnostic_count": self.diagnostic_count,
            "source_count": self.source_count,
            "evidence_types": self.evidence_types,
            "has_empirical_data": self.has_empirical_data,
        }


def _belief_entity_uris(knowledge) -> list[URIRef]:
    seen: set[URIRef] = set()
    rows: list[URIRef] = []
    for kind in SUPPORTED_KINDS:
        for uri, _, _ in knowledge.triples((None, RDF.type, _KIND_TYPES[kind])):
            if isinstance(uri, URIRef) and uri not in seen:
                seen.add(uri)
                rows.append(uri)
    return sorted(rows, key=str)


def _entity_kind(knowledge, uri: URIRef) -> str | None:
    if (uri, RDF.type, SCI_NS.Proposition) in knowledge:
        return "proposition"
    return bundle_kind(knowledge, uri)


def _entity_ref(uri: URIRef) -> str:
    value = str(uri)
    prefix = str(PROJECT_NS)
    if value.startswith(prefix):
        suffix = value[len(prefix) :]
        if "/" in suffix:
            kind, slug = suffix.split("/", 1)
            if kind and slug:
                return f"{kind}:{slug}"
    return value


def _label_for_entity(knowledge, uri: URIRef) -> str:
    label = next(knowledge.objects(uri, SKOS.prefLabel), None)
    if label is not None:
        return str(label)
    text = next(knowledge.objects(uri, SCI_NS.text), None)
    if text is not None:
        return str(text)
    return _entity_ref(uri)


def _freshness_state(knowledge, uri: URIRef) -> str | None:
    value = next(knowledge.objects(uri, SCI_NS.freshnessState), None)
    return str(value) if value is not None else None


def _unique_sources(units: Iterable[EvidenceUnit]) -> int:
    return len({unit.source for unit in units if unit.source})


def _evidence_types(units: Iterable[EvidenceUnit]) -> list[str]:
    return sorted({normalize_evidence_type(unit.evidence_type) for unit in units if unit.evidence_type})


def _evidence_summary(result: BeliefResult | BundleBeliefResult) -> _EvidenceSummary:
    if isinstance(result, BundleBeliefResult):
        support_units = tuple(unit for member in result.member_results for unit in member.belief.support_units)
        dispute_units = tuple(unit for member in result.member_results for unit in member.belief.dispute_units)
        diagnostic_units = tuple(unit for member in result.member_results for unit in member.belief.diagnostics)
        all_units = (*support_units, *dispute_units, *diagnostic_units)
        diagnostic_count: int | None = None
    else:
        support_units = tuple(result.support_units)
        dispute_units = tuple(result.dispute_units)
        diagnostic_units = tuple(result.diagnostics)
        all_units = (*support_units, *dispute_units, *diagnostic_units)
        diagnostic_count = len(diagnostic_units)

    types = _evidence_types(all_units)
    return _EvidenceSummary(
        support_count=len(support_units),
        dispute_count=len(dispute_units),
        diagnostic_count=diagnostic_count,
        source_count=_unique_sources(all_units),
        evidence_types=types,
        has_empirical_data=any(is_empirical_evidence_type(value) for value in types),
        support_units=support_units,
        all_units=all_units,
    )


def _scalar_payload(scalar: BeliefScalar | None) -> dict[str, Any] | None:
    if scalar is None:
        return None
    return {
        "massed_support_score": scalar.massed_support_score,
        "massed_dispute_score": scalar.massed_dispute_score,
        "massed_support_band": list(scalar.massed_support_band),
        "massed_dispute_band": list(scalar.massed_dispute_band),
        "net_band": list(scalar.net_band),
        "net_robust": scalar.net_robust,
        "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
    }


def _belief_scalar_payload(
    result: BeliefResult | BundleBeliefResult, *, scalar_enabled: bool
) -> dict[str, Any] | None:
    if not scalar_enabled:
        return None
    if isinstance(result, BundleBeliefResult):
        return _scalar_payload(result.scalar)
    return _scalar_payload(belief_scalar(result))


def _caps_payload(result: BeliefResult | BundleBeliefResult) -> dict[str, bool]:
    return {
        "authored_capped": result.authored_capped,
        "qa_dataset_capped": result.qa_dataset_capped,
        "capped_by_refutation": result.capped_by_refutation,
    }


def _labels(
    result: BeliefResult | BundleBeliefResult,
    evidence: _EvidenceSummary,
    *,
    freshness_state: str | None,
) -> list[str]:
    labels: list[str] = [result.magnitude.value]
    if result.contested:
        labels.append("contested")
    if evidence.support_count + evidence.dispute_count > 0 and evidence.source_count == 1:
        labels.append("single_source")
    if evidence.support_count + evidence.dispute_count > 0 and not evidence.has_empirical_data:
        labels.append("no_empirical_data")
    if evidence.has_empirical_data:
        labels.append("empirical_data_backed")
    if evidence.support_units and all(is_authored_assertion(unit) for unit in evidence.support_units):
        labels.append("authored_only")

    normalized_types = {
        normalize_evidence_type(unit.evidence_type)
        for unit in evidence.all_units
        if unit.evidence_type
    }
    if normalized_types == {"literature"}:
        labels.append("literature_only")

    if result.authored_capped:
        labels.append("authored_capped")
    if result.qa_dataset_capped:
        labels.append("qa_dataset_capped")
    if result.capped_by_refutation:
        labels.append("capped_by_refutation")
    if freshness_state == "stale":
        labels.append("stale")
    if freshness_state == "needs-review":
        labels.append("needs_review")

    return list(dict.fromkeys(labels))


def _default_include(
    result: BeliefResult | BundleBeliefResult,
    evidence: _EvidenceSummary,
    *,
    freshness_state: str | None,
) -> bool:
    if isinstance(result, BundleBeliefResult) and result.member_results:
        # Deliberate design tradeoff: resolved bundles are informative by membership
        # even when all member propositions are still evidence-free.
        return True
    if not isinstance(result, BundleBeliefResult):
        diagnostic_count = evidence.diagnostic_count or 0
        if evidence.support_count + evidence.dispute_count + diagnostic_count > 0:
            return True
    if result.authored_capped or result.qa_dataset_capped or result.capped_by_refutation:
        return True
    return freshness_state in {"needs-review", "stale"}


def profile_records(
    knowledge,
    provenance,
    *,
    scalar_enabled: bool,
    include_all: bool = False,
    kinds: Sequence[str] = (),
    labels: Sequence[str] = (),
) -> list[dict[str, Any]]:
    requested_kinds = set(kinds)
    requested_labels = set(labels)
    unknown_labels = requested_labels - set(PROFILE_LABELS)
    if unknown_labels:
        raise ValueError(f"unknown belief profile label(s): {', '.join(sorted(unknown_labels))}")
    rows: list[dict[str, Any]] = []

    for uri in _belief_entity_uris(knowledge):
        kind = _entity_kind(knowledge, uri)
        if kind is None:
            continue
        if requested_kinds and kind not in requested_kinds:
            continue

        result = belief_for_entity(knowledge, provenance, uri, scalar_enabled=scalar_enabled)
        evidence = _evidence_summary(result)
        freshness = _freshness_state(knowledge, uri)
        row_labels = _labels(result, evidence, freshness_state=freshness)

        if not include_all and not _default_include(result, evidence, freshness_state=freshness):
            continue
        if requested_labels and not requested_labels.issubset(set(row_labels)):
            continue

        rows.append(
            {
                "entity": _entity_ref(uri),
                "kind": kind,
                "label": _label_for_entity(knowledge, uri),
                "belief_state": result.magnitude.value,
                "contested": result.contested,
                "epistemic_labels": row_labels,
                "evidence": evidence.payload(),
                "caps": _caps_payload(result),
                "freshness_state": freshness,
                "belief_scalar": _belief_scalar_payload(result, scalar_enabled=scalar_enabled),
            }
        )

    rows.sort(key=lambda row: row["entity"])
    return rows


def make_profiles(
    graph_path: Path,
    *,
    include_all: bool = False,
    kinds: Sequence[str] = (),
    labels: Sequence[str] = (),
) -> list[dict[str, Any]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    enabled = belief_scalar_enabled(project_root_from_graph_path(graph_path))
    return profile_records(
        knowledge,
        provenance,
        scalar_enabled=enabled,
        include_all=include_all,
        kinds=kinds,
        labels=labels,
    )

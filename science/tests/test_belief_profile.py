from __future__ import annotations

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import PROV, SKOS

from science_tool.graph.belief import EVIDENCE_LINE_CLASS
from science_tool.graph.belief_profile import profile_records
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store.summary import is_empirical_evidence_type


PROP_A = URIRef(PROJECT_NS["proposition/pa"])
PROP_B = URIRef(PROJECT_NS["proposition/pb"])
PROP_EMPTY = URIRef(PROJECT_NS["proposition/empty"])
HYP = URIRef(PROJECT_NS["hypothesis/h1"])


def _line(
    knowledge: Graph,
    provenance: Graph,
    target: URIRef,
    line_id: str,
    *,
    stance: str = "supports",
    evidence_type: str = "empirical_data",
    evidence_role: str = "direct_test",
    strength: str = "strong",
    independence: str = "independent",
    group: str | None = None,
    source: str | None = None,
    dispute_scope: str | None = None,
    confidence: float | None = None,
) -> URIRef:
    line = URIRef(PROJECT_NS[f"evidence-line/{line_id}"])
    knowledge.add((line, RDF.type, EVIDENCE_LINE_CLASS))
    predicate = CITO_NS.supports if stance == "supports" else CITO_NS.disputes
    knowledge.add((line, predicate, target))
    provenance.add((line, SCI_NS.evidenceType, Literal(evidence_type)))
    provenance.add((line, SCI_NS.evidenceRole, Literal(evidence_role)))
    provenance.add((line, SCI_NS.evidenceStrength, Literal(strength)))
    provenance.add((line, SCI_NS.evidenceIndependence, Literal(independence)))
    provenance.add((line, SCI_NS.independenceGroup, Literal(group or line_id)))
    if source is not None:
        provenance.add((line, PROV.wasDerivedFrom, URIRef(source)))
    if dispute_scope is not None:
        provenance.add((line, SCI_NS.disputeScope, Literal(dispute_scope)))
    if confidence is not None:
        provenance.add((line, SCI_NS.confidence, Literal(confidence)))
    return line


def _base_graphs() -> tuple[Graph, Graph]:
    knowledge = Graph()
    provenance = Graph()
    for uri in (PROP_A, PROP_B, PROP_EMPTY):
        knowledge.add((uri, RDF.type, SCI_NS.Proposition))
    knowledge.add((PROP_A, SKOS.prefLabel, Literal("Panel membership claim")))
    knowledge.add((HYP, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((HYP, SCI_NS.hasProposition, PROP_A))
    knowledge.add((HYP, SCI_NS.hasProposition, PROP_B))
    return knowledge, provenance


def test_profile_reuses_summary_empirical_type_semantics() -> None:
    assert is_empirical_evidence_type("empirical_data")
    assert is_empirical_evidence_type("empirical_data_evidence")
    assert is_empirical_evidence_type("benchmark")
    assert not is_empirical_evidence_type("literature")


def test_profile_emits_non_bundle_row_with_labels_and_null_scalar() -> None:
    knowledge, provenance = _base_graphs()
    _line(
        knowledge,
        provenance,
        PROP_A,
        "expert-a",
        evidence_type="expert_judgment",
        evidence_role="background_constraint",
        strength="moderate",
        source=str(PROJECT_NS["source/editorial-note"]),
        confidence=0.9,
    )

    rows = profile_records(knowledge, provenance, scalar_enabled=False)

    row = next(item for item in rows if item["entity"] == "proposition:pa")
    assert row == {
        "entity": "proposition:pa",
        "kind": "proposition",
        "label": "Panel membership claim",
        "belief_state": "fragile",
        "contested": False,
        "epistemic_labels": [
            "fragile",
            "single_source",
            "no_empirical_data",
            "authored_only",
        ],
        "evidence": {
            "support_count": 1,
            "dispute_count": 0,
            "diagnostic_count": 0,
            "source_count": 1,
            "evidence_types": ["expert_judgment"],
            "has_empirical_data": False,
        },
        "caps": {
            "authored_capped": False,
            "qa_dataset_capped": False,
            "capped_by_refutation": False,
        },
        "freshness_state": None,
        "belief_scalar": None,
    }


def test_profile_default_excludes_empty_rows_but_all_includes_them() -> None:
    knowledge, provenance = _base_graphs()

    default_entities = {
        row["entity"] for row in profile_records(knowledge, provenance, scalar_enabled=False)
    }
    all_entities = {
        row["entity"]
        for row in profile_records(knowledge, provenance, scalar_enabled=False, include_all=True)
    }

    assert "proposition:empty" not in default_entities
    assert "proposition:empty" in all_entities


def test_profile_bundle_summarizes_member_evidence_with_null_diagnostic_count() -> None:
    knowledge, provenance = _base_graphs()
    _line(knowledge, provenance, PROP_A, "emp-a", source=str(PROJECT_NS["source/a"]))
    _line(
        knowledge,
        provenance,
        PROP_B,
        "lit-b",
        evidence_type="literature",
        evidence_role="background_constraint",
        strength="moderate",
        source=str(PROJECT_NS["source/b"]),
    )

    row = next(
        item
        for item in profile_records(knowledge, provenance, scalar_enabled=False)
        if item["entity"] == "hypothesis:h1"
    )

    assert row["kind"] == "hypothesis"
    assert row["belief_state"] == "fragile"
    assert row["evidence"] == {
        "support_count": 2,
        "dispute_count": 0,
        "diagnostic_count": None,
        "source_count": 2,
        "evidence_types": ["empirical_data", "literature"],
        "has_empirical_data": True,
    }
    assert "empirical_data_backed" in row["epistemic_labels"]


def test_profile_filters_kind_and_repeated_labels_with_and_semantics() -> None:
    knowledge, provenance = _base_graphs()
    _line(
        knowledge,
        provenance,
        PROP_A,
        "expert-a",
        evidence_type="expert_judgment",
        evidence_role="background_constraint",
        strength="moderate",
        source=str(PROJECT_NS["source/editorial-note"]),
        confidence=0.9,
    )
    _line(knowledge, provenance, PROP_B, "emp-b", source=str(PROJECT_NS["source/b"]))

    rows = profile_records(
        knowledge,
        provenance,
        scalar_enabled=False,
        kinds=("proposition",),
        labels=("fragile", "no_empirical_data"),
    )

    assert [row["entity"] for row in rows] == ["proposition:pa"]


def test_profile_rejects_unknown_labels() -> None:
    knowledge, provenance = _base_graphs()

    import pytest

    with pytest.raises(ValueError, match="unknown belief profile label"):
        profile_records(knowledge, provenance, scalar_enabled=False, labels=("fragil",))


def test_profile_freshness_and_refutation_labels() -> None:
    knowledge, provenance = _base_graphs()
    _line(knowledge, provenance, PROP_A, "support-a", source=str(PROJECT_NS["source/a"]))
    _line(
        knowledge,
        provenance,
        PROP_A,
        "support-b",
        source=str(PROJECT_NS["source/b"]),
        group="support-b",
    )
    _line(
        knowledge,
        provenance,
        PROP_A,
        "refute-a",
        stance="disputes",
        source=str(PROJECT_NS["source/c"]),
        group="refute-a",
        dispute_scope="whole_claim",
    )
    knowledge.add((PROP_A, SCI_NS.freshnessState, Literal("needs-review")))

    row = next(
        item
        for item in profile_records(knowledge, provenance, scalar_enabled=False)
        if item["entity"] == "proposition:pa"
    )

    assert row["belief_state"] == "fragile"
    assert row["contested"] is True
    assert row["caps"]["capped_by_refutation"] is True
    assert row["freshness_state"] == "needs-review"
    assert "contested" in row["epistemic_labels"]
    assert "capped_by_refutation" in row["epistemic_labels"]
    assert "needs_review" in row["epistemic_labels"]


def _expected_scalar_payload(knowledge: Graph, provenance: Graph, target: URIRef) -> dict:
    from science_tool.graph.belief import aggregate_belief, collect_evidence_units
    from science_tool.graph.belief_scalar import belief_scalar

    scalar = belief_scalar(aggregate_belief(collect_evidence_units(knowledge, provenance, [target])))
    return {
        "massed_support_score": scalar.massed_support_score,
        "massed_dispute_score": scalar.massed_dispute_score,
        "massed_support_band": list(scalar.massed_support_band),
        "massed_dispute_band": list(scalar.massed_dispute_band),
        "net_band": list(scalar.net_band),
        "net_robust": scalar.net_robust,
        "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
    }


def test_profile_projects_existing_scalar_for_non_bundle_when_enabled() -> None:
    knowledge, provenance = _base_graphs()
    _line(knowledge, provenance, PROP_A, "emp-a", source=str(PROJECT_NS["source/a"]))

    row = next(
        item
        for item in profile_records(knowledge, provenance, scalar_enabled=True)
        if item["entity"] == "proposition:pa"
    )

    assert row["belief_scalar"] == _expected_scalar_payload(knowledge, provenance, PROP_A)


def test_profile_projects_existing_bundle_scalar_driver_when_enabled() -> None:
    knowledge, provenance = _base_graphs()
    _line(knowledge, provenance, PROP_A, "emp-a", source=str(PROJECT_NS["source/a"]))
    _line(
        knowledge,
        provenance,
        PROP_B,
        "lit-b",
        evidence_type="literature",
        evidence_role="background_constraint",
        strength="moderate",
        source=str(PROJECT_NS["source/b"]),
    )

    row = next(
        item
        for item in profile_records(knowledge, provenance, scalar_enabled=True)
        if item["entity"] == "hypothesis:h1"
    )

    assert row["belief_scalar"] == _expected_scalar_payload(knowledge, provenance, PROP_B)

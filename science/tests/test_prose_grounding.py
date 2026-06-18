import json
from pathlib import Path

import pytest
from rdflib import Dataset, Literal, RDF, URIRef

from science_tool.annotation.prose_decomposition import (
    ProseDecompositionStore,
    compute_source_hash,
    parse_submitted_decomposition,
)
from science_tool.annotation.prose_grounding import (
    ProseGroundingError,
    ProseGroundingReport,
    build_prose_grounding_report,
    write_prose_grounding_report,
)
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store import _graph_uri


TARGET = PROJECT_NS["proposition/basalt-cooling"]


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "# Section\n\n"
        "Basalt flows record the cooling history. "
        "This framing orients the example.\n",
        encoding="utf-8",
    )
    return source


def _artifact_payload(
    tmp_path: Path,
    artifact_id: str = "decomp-1",
    unit_id: str = "u001",
    quote: str = "Basalt flows record the cooling history.",
) -> dict:
    source = _source(tmp_path)
    return {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": compute_source_hash(source),
        },
        "artifact": {
            "id": artifact_id,
            "generated_at": "2026-06-18T12:00:00Z",
            "producer": "offline-agent",
        },
        "units": [
            {
                "unit_id": unit_id,
                "disposition": "candidate",
                "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
                "payload": {
                    "type": "proposition",
                    "exact": quote,
                    "prefix": "",
                    "suffix": "",
                    "stance": "asserted",
                },
            },
            {
                "unit_id": "s001",
                "disposition": "skip",
                "locator": {
                    "regime": "markdown-heading-path-with-quote",
                    "value": ["Section"],
                    "quote": {
                        "exact": "This framing orients the example.",
                        "prefix": "",
                        "suffix": "",
                    },
                },
                "reason": {"code": "not_a_claim", "detail": "Framing sentence."},
            },
        ],
    }


def _persist_artifact(tmp_path: Path, payload: dict):
    artifact = parse_submitted_decomposition(json.dumps(payload), project_root=tmp_path)
    store = ProseDecompositionStore(tmp_path)
    store.persist(artifact)
    return artifact, store


def _write_graph(tmp_path: Path, *, supports: int) -> Path:
    dataset = Dataset()
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    knowledge.add((TARGET, RDF.type, SCI_NS.Proposition))
    for index in range(supports):
        line = URIRef(PROJECT_NS[f"evidence-line/basalt-cooling-{index + 1}"])
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, TARGET))
        provenance.add((line, SCI_NS.evidenceStrength, Literal("strong")))
        provenance.add((line, SCI_NS.evidenceIndependence, Literal("independent")))
        provenance.add((line, SCI_NS.independenceGroup, Literal(f"g{index + 1}")))
        provenance.add((line, SCI_NS.evidenceRole, Literal("proxy")))
        provenance.add((line, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.serialize(destination=str(graph_path), format="trig")
    return graph_path


def test_build_prose_grounding_report_joins_promoted_unit_by_fingerprint(tmp_path: Path):
    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:basalt-cooling")
    graph_path = _write_graph(tmp_path, supports=2)

    report = build_prose_grounding_report(
        tmp_path,
        "prose-source:example",
        graph_path,
        generated_at="2026-06-18T13:00:00Z",
    ).to_json()

    assert report["source_ref"] == "prose-source:example"
    assert report["decomposition_artifact_id"] == "decomp-1"
    assert report["grounding_policy"] == {
        "floor": "supported",
        "belief_policy_id": DEFAULT_BELIEF_POLICY.policy_id,
        "belief_policy_version": DEFAULT_BELIEF_POLICY.version,
    }
    assert report["summary"]["grounded_units"] == 1
    assert report["summary"]["skipped_units"] == 1
    candidate = report["units"][0]
    assert candidate["unit_id"] == "u001"
    assert candidate["fingerprint"] == artifact.units[0].fingerprint
    assert candidate["proposition_ref"] == "proposition:basalt-cooling"
    assert candidate["status"] == "grounded"
    assert candidate["grounding"]["belief_magnitude"] == "supported"
    skip = report["units"][1]
    assert skip["status"] == "skipped"
    assert skip["proposition_ref"] is None
    assert skip["grounding"] is None
    assert skip["skip_reason"] == "not_a_claim"


def test_build_prose_grounding_report_keeps_promoted_link_across_unit_renumber(tmp_path: Path):
    first, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path, unit_id="u001"))
    store.record_promotion("example", first.units[0].fingerprint, "proposition:basalt-cooling")
    second, store = _persist_artifact(
        tmp_path,
        _artifact_payload(tmp_path, artifact_id="decomp-2", unit_id="u777"),
    )
    graph_path = _write_graph(tmp_path, supports=2)

    report = build_prose_grounding_report(
        tmp_path,
        "prose-source:example",
        graph_path,
        generated_at="2026-06-18T13:00:00Z",
    ).to_json()

    candidate = report["units"][0]
    assert candidate["unit_id"] == "u777"
    assert candidate["fingerprint"] == second.units[0].fingerprint == first.units[0].fingerprint
    assert candidate["status"] == "grounded"
    assert candidate["proposition_ref"] == "proposition:basalt-cooling"


def test_build_prose_grounding_report_classifies_below_floor(tmp_path: Path):
    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:basalt-cooling")
    graph_path = _write_graph(tmp_path, supports=1)

    report = build_prose_grounding_report(
        tmp_path,
        "prose-source:example",
        graph_path,
        generated_at="2026-06-18T13:00:00Z",
    ).to_json()

    assert report["summary"]["below_floor_units"] == 1
    candidate = report["units"][0]
    assert candidate["status"] == "below_floor"
    assert candidate["grounding"]["belief_magnitude"] == "fragile"


def test_build_prose_grounding_report_classifies_unpromoted_candidate(tmp_path: Path):
    _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    graph_path = _write_graph(tmp_path, supports=2)

    report = build_prose_grounding_report(
        tmp_path,
        "prose-source:example",
        graph_path,
        generated_at="2026-06-18T13:00:00Z",
    ).to_json()

    assert report["grounding_policy"] == {
        "floor": "supported",
        "belief_policy_id": DEFAULT_BELIEF_POLICY.policy_id,
        "belief_policy_version": DEFAULT_BELIEF_POLICY.version,
    }
    assert report["summary"]["unpromoted_units"] == 1
    candidate = report["units"][0]
    assert candidate["status"] == "unpromoted"
    assert candidate["proposition_ref"] is None


def test_build_prose_grounding_report_missing_promoted_proposition_fails(tmp_path: Path):
    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:missing")
    graph_path = _write_graph(tmp_path, supports=0)

    with pytest.raises(ProseGroundingError, match="not found in knowledge graph"):
        build_prose_grounding_report(
            tmp_path,
            "prose-source:example",
            graph_path,
            generated_at="2026-06-18T13:00:00Z",
        )


def test_write_prose_grounding_report_rejects_path_like_source_slug(tmp_path: Path):
    report = ProseGroundingReport(
        {
            "schema_version": 1,
            "source_ref": "prose-source:../escape",
            "decomposition_artifact_id": "decomp-1",
            "graph_path": "knowledge/graph.trig",
            "generated_at": "2026-06-18T13:00:00Z",
            "grounding_policy": {
                "floor": "supported",
                "belief_policy_id": DEFAULT_BELIEF_POLICY.policy_id,
                "belief_policy_version": DEFAULT_BELIEF_POLICY.version,
            },
            "summary": {},
            "units": [],
        }
    )

    with pytest.raises(ProseGroundingError, match="invalid prose source ref"):
        write_prose_grounding_report(tmp_path, report)

    assert not (tmp_path / "data" / "escape" / "grounding.json").exists()

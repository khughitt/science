import json
from pathlib import Path

import pytest
from rdflib import RDF, Dataset, Literal, URIRef

from science_tool.annotation.prose_decomposition import (
    ProseDecompositionStore,
    compute_source_hash,
    parse_submitted_decomposition,
)
from science_tool.annotation.prose_grounding import (
    ProseGroundingError,
    ProseGroundingReport,
    build_prose_grounding_report,
    prose_grounding_path,
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


def test_build_prose_grounding_report_rejects_invalid_floor_without_promotions(tmp_path: Path):
    _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    graph_path = _write_graph(tmp_path, supports=2)

    with pytest.raises(ProseGroundingError, match="unknown grounding floor"):
        build_prose_grounding_report(
            tmp_path,
            "prose-source:example",
            graph_path,
            generated_at="2026-06-18T13:00:00Z",
            floor="confident",
        )


def test_build_prose_grounding_report_rejects_missing_current_index_row(tmp_path: Path):
    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    index_path = store.index_path("example")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    del index["units"][artifact.units[0].fingerprint]
    index_path.write_text(json.dumps(index), encoding="utf-8")
    graph_path = _write_graph(tmp_path, supports=2)

    with pytest.raises(ProseGroundingError, match="missing current decomposition index row"):
        build_prose_grounding_report(
            tmp_path,
            "prose-source:example",
            graph_path,
            generated_at="2026-06-18T13:00:00Z",
        )


def test_build_prose_grounding_report_emits_stale_rows_without_counting_current_units(tmp_path: Path):
    first, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", first.units[0].fingerprint, "proposition:basalt-cooling")
    second, _store = _persist_artifact(
        tmp_path,
        _artifact_payload(
            tmp_path,
            artifact_id="decomp-2",
            quote="A different basalt claim is present.",
        ),
    )
    graph_path = _write_graph(tmp_path, supports=2)

    report = build_prose_grounding_report(
        tmp_path,
        "prose-source:example",
        graph_path,
        generated_at="2026-06-18T13:00:00Z",
    ).to_json()

    stale_rows = [row for row in report["units"] if row["status"] == "stale"]
    assert len(stale_rows) == 1
    assert stale_rows[0]["fingerprint"] == first.units[0].fingerprint
    assert stale_rows[0]["grounding"] is None
    assert report["summary"]["stale_units"] == 1
    assert report["summary"]["current_candidate_units"] == 1
    assert report["summary"]["grounded_units"] == 0
    assert report["units"][0]["fingerprint"] == second.units[0].fingerprint


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


def test_prose_grounding_path_rejects_path_like_slug(tmp_path: Path):
    with pytest.raises(ProseGroundingError, match="invalid prose source slug"):
        prose_grounding_path(tmp_path, "../escape")


def test_write_prose_grounding_report_writes_canonical_json(tmp_path: Path):
    report = ProseGroundingReport(
        {
            "schema_version": 1,
            "source_ref": "prose-source:example",
            "decomposition_artifact_id": "decomp-1",
            "graph_path": "knowledge/graph.trig",
            "generated_at": "2026-06-18T13:00:00Z",
            "grounding_policy": {
                "floor": "supported",
                "belief_policy_id": DEFAULT_BELIEF_POLICY.policy_id,
                "belief_policy_version": DEFAULT_BELIEF_POLICY.version,
            },
            "summary": {"grounded_units": 0},
            "units": [],
        }
    )

    assert write_prose_grounding_report(tmp_path, report) is True

    path = tmp_path / "data" / "prose-grounding" / "example" / "grounding.json"
    assert json.loads(path.read_text(encoding="utf-8")) == report.to_json()


def test_write_prose_grounding_report_skips_timestamp_only_rewrite(tmp_path: Path):
    artifact, store = _persist_artifact(tmp_path, _artifact_payload(tmp_path))
    store.record_promotion("example", artifact.units[0].fingerprint, "proposition:basalt-cooling")
    graph_path = _write_graph(tmp_path, supports=2)
    first = build_prose_grounding_report(
        tmp_path,
        "prose-source:example",
        graph_path,
        generated_at="2026-06-18T13:00:00Z",
    )
    second = build_prose_grounding_report(
        tmp_path,
        "prose-source:example",
        graph_path,
        generated_at="2026-06-18T14:00:00Z",
    )
    path = prose_grounding_path(tmp_path, "example")

    assert write_prose_grounding_report(tmp_path, first) is True
    first_text = path.read_text(encoding="utf-8")
    assert write_prose_grounding_report(tmp_path, second) is False

    assert path.read_text(encoding="utf-8") == first_text

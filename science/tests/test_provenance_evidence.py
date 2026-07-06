from pathlib import Path

import pytest
from conftest import build_entity_graph
from rdflib import Literal, URIRef

from science_tool.graph.store import PROJECT_NS, SCI_NS, _graph_uri, _load_dataset


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a minimal source-authored project root."""
    return tmp_path


def _entity(kind: str, entity_id: str, title: str, **frontmatter: object) -> dict:
    return {
        "kind": kind,
        "id": entity_id,
        "frontmatter": {"title": title, **frontmatter},
        "body": f"{title}\n",
    }


def _evidence_line(entity_id: str, title: str, **frontmatter: object) -> dict:
    return _entity("evidence-line", entity_id, title, **frontmatter)


def test_source_evidence_line_with_independence(project_root: Path):
    """Source-authored evidence-line independence annotation stores the value."""
    graph_path = build_entity_graph(
        project_root,
        [
            _entity("proposition", "prop-1", "Test proposition"),
            _evidence_line(
                "ev-1",
                "Test evidence",
                target="proposition:prop-1",
                stance="supports",
                strength="moderate",
                independence="circular",
            ),
        ],
    )

    provenance = _load_dataset(graph_path).graph(_graph_uri("graph/provenance"))
    line_uri = URIRef(PROJECT_NS["evidence-line/ev-1"])

    assert (line_uri, SCI_NS.evidenceIndependence, Literal("circular")) in provenance


def test_source_evidence_line_without_independence(project_root: Path):
    """Source-authored evidence-line without independence omits the predicate."""
    graph_path = build_entity_graph(
        project_root,
        [
            _entity("proposition", "prop-1", "Test proposition"),
            _evidence_line(
                "ev-1",
                "Test evidence",
                target="proposition:prop-1",
                stance="supports",
                strength="moderate",
            ),
        ],
    )

    provenance = _load_dataset(graph_path).graph(_graph_uri("graph/provenance"))
    line_uri = URIRef(PROJECT_NS["evidence-line/ev-1"])

    assert list(provenance.triples((line_uri, SCI_NS.evidenceIndependence, None))) == []


def test_source_evidence_line_invalid_independence(project_root: Path):
    """Invalid independence value is rejected by source materialization."""
    with pytest.raises(ValueError) as exc_info:
        build_entity_graph(
            project_root,
            [
                _entity("proposition", "prop-1", "Test proposition"),
                _evidence_line(
                    "ev-1",
                    "Test evidence",
                    target="proposition:prop-1",
                    stance="supports",
                    strength="moderate",
                    independence="invalid-value",
                ),
            ],
        )

    message = str(exc_info.value)
    assert "evidence-line" in message
    assert "independence" in message
    assert "independent" in message
    assert "shared-source" in message
    assert "circular" in message

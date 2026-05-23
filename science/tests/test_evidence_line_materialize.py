"""Tests for evidence-line triple emission during materialize."""

from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, URIRef
from rdflib.namespace import PROV

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS

# CITO_NS is defined in io.py; import directly.
from science_tool.graph.io import CITO_NS


def _write(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _load_dataset(project: Path) -> Dataset:
    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    return dataset


def _minimal_project(tmp_path: Path) -> Path:
    """Write a minimal project with a proposition, a paper, and an evidence-line."""
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")

    # Target proposition
    _write(
        tmp_path,
        "doc/propositions/p.md",
        """---
id: proposition:p
kind: proposition
title: "Proposition P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
    )

    # Source paper (resolves the `source:` ref on the evidence-line)
    _write(
        tmp_path,
        "doc/papers/x.md",
        """---
id: paper:x
kind: paper
title: "Paper X"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
    )

    # Evidence-line entity
    _write(
        tmp_path,
        "doc/evidence-lines/e.md",
        """---
id: evidence-line:e
kind: evidence-line
title: "E disputes P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
stance: disputes
target: proposition:p
source: paper:x
strength: strong
independence: independent
independence_group: g1
evidence_role: model_criticism
dispute_scope: generalization
shared_dataset: ds:alpha
---
""",
    )

    return tmp_path


def test_evidence_line_cito_edge_in_knowledge(tmp_path: Path) -> None:
    """stance: disputes + target: proposition:p → cito:disputes in knowledge graph."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    target_uri = URIRef(PROJECT_NS["proposition/p"])

    assert (line_uri, CITO_NS.disputes, target_uri) in knowledge, (
        "Expected cito:disputes edge from evidence-line:e to proposition:p in knowledge graph"
    )


def test_evidence_line_supports_not_emitted_for_disputes(tmp_path: Path) -> None:
    """cito:supports must NOT be present when stance is disputes."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    target_uri = URIRef(PROJECT_NS["proposition/p"])

    assert (line_uri, CITO_NS.supports, target_uri) not in knowledge, (
        "cito:supports must not be emitted when stance is disputes"
    )


def test_evidence_line_source_provenance_edge(tmp_path: Path) -> None:
    """source: paper:x → prov:wasDerivedFrom paper:x in provenance graph."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    paper_uri = URIRef(PROJECT_NS["paper/x"])

    assert (line_uri, PROV.wasDerivedFrom, paper_uri) in provenance, (
        "Expected prov:wasDerivedFrom edge from evidence-line:e to paper:x in provenance graph"
    )


def test_evidence_line_strength_in_provenance(tmp_path: Path) -> None:
    """strength: strong → sci:evidenceStrength Literal in provenance."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    values = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.evidenceStrength, None))}
    assert "strong" in values, f"Expected sci:evidenceStrength 'strong', got {values}"


def test_evidence_line_independence_in_provenance(tmp_path: Path) -> None:
    """independence: independent → sci:evidenceIndependence Literal in provenance."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    values = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.evidenceIndependence, None))}
    assert "independent" in values, f"Expected sci:evidenceIndependence 'independent', got {values}"


def test_evidence_line_dispute_scope_in_provenance(tmp_path: Path) -> None:
    """dispute_scope: generalization → sci:disputeScope Literal in provenance."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    values = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.disputeScope, None))}
    assert "generalization" in values, f"Expected sci:disputeScope 'generalization', got {values}"


def test_evidence_line_shared_dataset_in_provenance(tmp_path: Path) -> None:
    """shared_dataset: ds:alpha → sci:sharedDataset Literal in provenance."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    values = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.sharedDataset, None))}
    assert "ds:alpha" in values, f"Expected sci:sharedDataset 'ds:alpha', got {values}"


def test_evidence_line_evidence_role_in_provenance(tmp_path: Path) -> None:
    """evidence_role: model_criticism → sci:evidenceRole Literal in provenance (via reasoning metadata)."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    values = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.evidenceRole, None))}
    assert "model_criticism" in values, f"Expected sci:evidenceRole 'model_criticism', got {values}"


def test_evidence_line_independence_group_in_provenance(tmp_path: Path) -> None:
    """independence_group: g1 → sci:independenceGroup Literal in provenance (via reasoning metadata)."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e"])
    values = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.independenceGroup, None))}
    assert "g1" in values, f"Expected sci:independenceGroup 'g1', got {values}"


def test_evidence_line_supports_stance_emits_cito_supports(tmp_path: Path) -> None:
    """stance: supports → cito:supports in knowledge graph."""
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")
    _write(
        tmp_path,
        "doc/propositions/p.md",
        """---
id: proposition:p
kind: proposition
title: "Proposition P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/sup.md",
        """---
id: evidence-line:sup
kind: evidence-line
title: "Sup supports P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
stance: supports
target: proposition:p
---
""",
    )
    dataset = _load_dataset(tmp_path)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    line_uri = URIRef(PROJECT_NS["evidence-line/sup"])
    target_uri = URIRef(PROJECT_NS["proposition/p"])

    assert (line_uri, CITO_NS.supports, target_uri) in knowledge, (
        "Expected cito:supports edge for stance=supports"
    )
    assert (line_uri, CITO_NS.disputes, target_uri) not in knowledge, (
        "cito:disputes must not be emitted when stance is supports"
    )

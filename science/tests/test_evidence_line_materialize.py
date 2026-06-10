"""Tests for evidence-line triple emission during materialize."""

from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, Literal, URIRef
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
        "entities/propositions/p.md",
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
        "entities/papers/x.md",
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
        "entities/evidence-lines/e.md",
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
        "entities/propositions/p.md",
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
        "entities/evidence-lines/sup.md",
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


def test_dataset_source_class_emitted_and_line_derives_from_same_uri(tmp_path: Path) -> None:
    """A dataset with source_class=reference emits sci:sourceClass in knowledge.
    An evidence-line whose source is that dataset has the same dataset URI as
    one of its prov:wasDerivedFrom objects in provenance.
    """
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")

    # Target proposition
    _write(
        tmp_path,
        "entities/propositions/p.md",
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

    # Dataset entity with source_class=reference (origin=external requires an access block)
    dp = tmp_path / "data" / "refset" / "datapackage.yaml"
    dp.parent.mkdir(parents=True, exist_ok=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:refset\n"
        "type: dataset\n"
        "title: Reference Set\n"
        "status: active\n"
        "origin: external\n"
        "source_class: reference\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
        encoding="utf-8",
    )

    # Evidence-line entity whose source is the dataset
    _write(
        tmp_path,
        "entities/evidence-lines/el-ref.md",
        """---
id: evidence-line:el-ref
kind: evidence-line
title: "EL cites refset"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
stance: supports
target: proposition:p
source: dataset:refset
---
""",
    )

    rdf_dataset = _load_dataset(tmp_path)
    knowledge = rdf_dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = rdf_dataset.graph(PROJECT_NS["graph/provenance"])

    ds_uri = PROJECT_NS["dataset/refset"]
    line_uri = PROJECT_NS["evidence-line/el-ref"]

    # sci:sourceClass triple in knowledge
    assert (ds_uri, SCI_NS.sourceClass, Literal("reference")) in knowledge, (
        "Expected sci:sourceClass 'reference' on dataset:refset in knowledge graph"
    )

    # Evidence-line's prov:wasDerivedFrom includes the same dataset URI
    line_derived = {o for _, _, o in provenance.triples((line_uri, PROV.wasDerivedFrom, None))}
    assert ds_uri in line_derived, (
        f"Expected dataset URI {ds_uri} in evidence-line's prov:wasDerivedFrom; got {line_derived}"
    )


def test_evidence_line_evidence_type_in_provenance(tmp_path: Path) -> None:
    """evidence_type: empirical_data_evidence → sci:evidenceType Literal in provenance."""
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")
    _write(
        tmp_path,
        "entities/propositions/p.md",
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
        "entities/evidence-lines/et.md",
        """---
id: evidence-line:et
kind: evidence-line
title: "ET supports P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
stance: supports
target: proposition:p
evidence_type: empirical_data_evidence
---
""",
    )
    dataset = _load_dataset(tmp_path)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/et"])
    values = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.evidenceType, None))}
    assert "empirical_data_evidence" in values, (
        f"Expected sci:evidenceType 'empirical_data_evidence', got {values}"
    )


def test_evidence_line_task_source_lands_in_provenance_not_belief(tmp_path: Path) -> None:
    """Regression: source: task:t082 → prov:wasDerivedFrom in provenance; NEVER a cito edge.

    The evidence-line's `source` field records *where the finding came from* (provenance).
    Only the `target` field produces cito:supports/disputes (belief). A task-ref source
    must route exclusively into provenance, never into the knowledge graph as a cito edge.
    """
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")

    # Task entity that acts as the source of the evidence-line
    _write(
        tmp_path,
        "entities/tasks/t082.md",
        """---
id: task:t082
kind: task
title: "Task T082"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
    )

    # Target proposition that receives the cito:supports edge
    _write(
        tmp_path,
        "entities/propositions/q.md",
        """---
id: proposition:q
kind: proposition
title: "Proposition Q"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
---
""",
    )

    # Evidence-line: source is the task, target is the proposition
    _write(
        tmp_path,
        "entities/evidence-lines/el-task.md",
        """---
id: evidence-line:el-task
kind: evidence-line
title: "EL task source supports Q"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
stance: supports
target: proposition:q
source: task:t082
---
""",
    )

    rdf_dataset = _load_dataset(tmp_path)
    knowledge = rdf_dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = rdf_dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/el-task"])
    task_uri = URIRef(PROJECT_NS["task/t082"])
    target_uri = URIRef(PROJECT_NS["proposition/q"])

    # 1. prov:wasDerivedFrom must point at the task in the provenance graph
    assert (line_uri, PROV.wasDerivedFrom, task_uri) in provenance, (
        "Expected prov:wasDerivedFrom edge from evidence-line:el-task to task:t082 in provenance graph"
    )

    # 2. The task must NOT appear as the object of any cito edge (source never goes to belief)
    assert (line_uri, CITO_NS.supports, task_uri) not in knowledge, (
        "task:t082 must not appear as object of cito:supports — task sources belong in provenance only"
    )
    assert (line_uri, CITO_NS.disputes, task_uri) not in knowledge, (
        "task:t082 must not appear as object of cito:disputes — task sources belong in provenance only"
    )

    # 3. The cito:supports edge must point at the target proposition (split is correct)
    assert (line_uri, CITO_NS.supports, target_uri) in knowledge, (
        "Expected cito:supports edge from evidence-line:el-task to proposition:q in knowledge graph"
    )

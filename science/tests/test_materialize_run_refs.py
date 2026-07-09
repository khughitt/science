import pytest
from rdflib import Graph
from science_model.entities import EntityType, EvidenceLineEntity

from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import _add_run_ref_edges, _entity_uri
from science_tool.graph.reference_resolution import ReferenceResolver


def _line(run_refs: list[str]) -> EvidenceLineEntity:
    return EvidenceLineEntity(
        id="evidence-line:e1",
        canonical_id="evidence-line:e1",
        kind="evidence-line",
        type=EntityType.EVIDENCE_LINE,
        title="E1 supports H1",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/evidence-lines/e1.md",
        stance="supports",
        target="hypothesis:h1",
        belief_eligible=True,
        run_refs=run_refs,
    )


def test_unresolved_run_ref_raises():
    """Would catch: dropping/loosening the fail-closed raise when a run_refs
    entry does not resolve to any authored entity at all."""
    entity = _line(["workflow-run:missing"])
    resolver = ReferenceResolver(alias_map={}, slug_index={})
    with pytest.raises(ValueError, match="unresolved workflow-run reference"):
        _add_run_ref_edges(entity, _entity_uri(entity.canonical_id), resolver=resolver, knowledge=Graph())


def test_run_ref_resolving_to_non_workflow_run_raises():
    """Would catch: dropping/loosening the fail-closed raise when a run_refs
    entry resolves (e.g. via an authored alias/same_as) to an entity that is
    not a workflow-run — a silently mis-scoped resolution."""
    entity = _line(["workflow-run:foo"])
    resolver = ReferenceResolver(alias_map={"workflow-run:foo": "dataset:foo"}, slug_index={})
    with pytest.raises(ValueError, match="resolved to non-workflow-run"):
        _add_run_ref_edges(entity, _entity_uri(entity.canonical_id), resolver=resolver, knowledge=Graph())


def test_run_refs_emit_sci_run_ref_triples(materialized_knowledge_for_evidence_line):
    """run_refs must reach the graph, or the field is inert."""
    knowledge, line_uri = materialized_knowledge_for_evidence_line(
        run_refs=["workflow-run:r1", "workflow-run:r2"], belief_eligible=True
    )
    targets = {str(o) for o in knowledge.objects(line_uri, SCI_NS.runRef)}
    assert len(targets) == 2
    assert any(t.endswith("workflow-run/r1") or t.endswith("r1") for t in targets)


def test_staged_line_emits_no_run_refs(materialized_knowledge_for_evidence_line):
    knowledge, line_uri = materialized_knowledge_for_evidence_line(
        run_refs=["workflow-run:r1"], belief_eligible=False
    )
    assert list(knowledge.objects(line_uri, SCI_NS.runRef)) == []


def test_no_run_refs_emits_nothing(materialized_knowledge_for_evidence_line):
    knowledge, line_uri = materialized_knowledge_for_evidence_line(run_refs=[], belief_eligible=True)
    assert list(knowledge.objects(line_uri, SCI_NS.runRef)) == []


def test_run_ref_predicate_is_registered():
    from science_tool.graph.store.constants import PREDICATE_REGISTRY

    assert any(entry["predicate"] == "sci:runRef" for entry in PREDICATE_REGISTRY)

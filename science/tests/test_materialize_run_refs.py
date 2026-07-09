from science_tool.graph.io import SCI_NS


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

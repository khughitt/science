from rdflib import Literal

from science_tool.graph.io import SCI_NS


def test_fingerprinted_run_emits_policy_marker(materialized_knowledge_for_run):
    knowledge, run_uri = materialized_knowledge_for_run(with_fingerprint=True)
    assert list(knowledge.objects(run_uri, SCI_NS.fingerprintPolicy)) == [
        Literal("science-run-fingerprint/v1")
    ]


def test_unfingerprinted_run_emits_no_marker(materialized_knowledge_for_run):
    knowledge, run_uri = materialized_knowledge_for_run(with_fingerprint=False)
    assert list(knowledge.objects(run_uri, SCI_NS.fingerprintPolicy)) == []


def test_fingerprint_policy_predicate_is_registered():
    from science_tool.graph.store.constants import PREDICATE_REGISTRY

    assert any(entry["predicate"] == "sci:fingerprintPolicy" for entry in PREDICATE_REGISTRY)

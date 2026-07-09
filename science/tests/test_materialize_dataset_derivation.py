from rdflib import Literal

from science_tool.graph.io import SCI_NS


def test_workflow_run_derivation_emits_kind_and_run_edge(materialized_knowledge_for_dataset):
    knowledge, ds_uri, run_uri = materialized_knowledge_for_dataset(kind="workflow-run")
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == [Literal("workflow-run")]
    assert list(knowledge.objects(ds_uri, SCI_NS.workflowRun)) == [run_uri]


def test_recipe_derivation_emits_kind_but_no_run_edge(materialized_knowledge_for_dataset):
    knowledge, ds_uri, _ = materialized_knowledge_for_dataset(kind="workflow-recipe")
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == [Literal("workflow-recipe")]
    assert list(knowledge.objects(ds_uri, SCI_NS.workflowRun)) == []


def test_member_of_derivation_emits_parent_edge(materialized_knowledge_for_dataset):
    knowledge, ds_uri, parent_uri = materialized_knowledge_for_dataset(kind="member_of")
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == [Literal("member_of")]
    assert list(knowledge.objects(ds_uri, SCI_NS.memberOfParent)) == [parent_uri]
    assert list(knowledge.objects(ds_uri, SCI_NS.workflowRun)) == []


def test_dataset_without_derivation_emits_no_kind(materialized_knowledge_for_dataset):
    knowledge, ds_uri, _ = materialized_knowledge_for_dataset(kind=None)
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == []


def test_derivation_predicates_are_registered():
    from science_tool.graph.store.constants import PREDICATE_REGISTRY

    names = {entry["predicate"] for entry in PREDICATE_REGISTRY}
    assert {"sci:derivationKind", "sci:workflowRun", "sci:memberOfParent"} <= names

from types import SimpleNamespace

import pytest
from rdflib import Graph, Literal
from science_model.entities import DatasetEntity, EntityType
from science_model.packages.schema import DerivationBlock, MemberOfDerivationBlock

from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import _add_derivation_edges
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.run_resolution import (
    KIND_MEMBER_OF,
    KIND_WORKFLOW_RECIPE,
    KIND_WORKFLOW_RUN,
)


def _dataset(derivation) -> DatasetEntity:
    return DatasetEntity(
        id="dataset:ds1",
        canonical_id="dataset:ds1",
        kind="dataset",
        type=EntityType.DATASET,
        title="DS1",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/datasets/ds1.md",
        origin="derived",
        derivation=derivation,
    )


def test_unresolved_workflow_run_derivation_raises():
    """Would catch: dropping/loosening the fail-closed raise when a
    DerivationBlock names a workflow_run that resolves to nothing."""
    entity = _dataset(
        DerivationBlock(
            workflow="workflow:wf",
            workflow_run="workflow-run:missing",
            git_commit="abc",
            config_snapshot="config.yaml",
            produced_at="2026-04-19T00:00:00Z",
        )
    )
    resolver = ReferenceResolver(alias_map={}, slug_index={})
    sources = SimpleNamespace(entities=[entity])
    with pytest.raises(ValueError, match="unresolved workflow_run"):
        _add_derivation_edges(sources, resolver=resolver, knowledge=Graph())


def test_workflow_run_derivation_resolving_to_wrong_kind_raises():
    """Would catch: dropping/loosening the fail-closed raise when a
    DerivationBlock's workflow_run resolves (e.g. via an authored alias) to an
    entity that is not a workflow-run."""
    entity = _dataset(
        DerivationBlock(
            workflow="workflow:wf",
            workflow_run="workflow-run:foo",
            git_commit="abc",
            config_snapshot="config.yaml",
            produced_at="2026-04-19T00:00:00Z",
        )
    )
    resolver = ReferenceResolver(alias_map={"workflow-run:foo": "dataset:other"}, slug_index={})
    sources = SimpleNamespace(entities=[entity])
    with pytest.raises(ValueError, match="workflow_run resolved to non-workflow-run"):
        _add_derivation_edges(sources, resolver=resolver, knowledge=Graph())


def test_unresolved_member_of_parent_raises():
    """Would catch: dropping/loosening the fail-closed raise when a
    MemberOfDerivationBlock names a parent_dataset that resolves to nothing."""
    entity = _dataset(MemberOfDerivationBlock(kind="member_of", parent_dataset="dataset:missing", member_key="k1"))
    resolver = ReferenceResolver(alias_map={}, slug_index={})
    sources = SimpleNamespace(entities=[entity])
    with pytest.raises(ValueError, match="unresolved member_of parent"):
        _add_derivation_edges(sources, resolver=resolver, knowledge=Graph())


def test_member_of_parent_resolving_to_wrong_kind_raises():
    """Would catch: dropping/loosening the fail-closed raise when a
    MemberOfDerivationBlock's parent_dataset resolves to an entity that is not
    a dataset."""
    entity = _dataset(MemberOfDerivationBlock(kind="member_of", parent_dataset="dataset:foo", member_key="k1"))
    resolver = ReferenceResolver(alias_map={"dataset:foo": "workflow-run:other"}, slug_index={})
    sources = SimpleNamespace(entities=[entity])
    with pytest.raises(ValueError, match="member_of parent resolved to non-dataset"):
        _add_derivation_edges(sources, resolver=resolver, knowledge=Graph())


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


def test_emitted_derivation_kind_matches_run_resolution_constants(materialized_knowledge_for_dataset):
    """Pins each authored derivation arm to the token the resolver keys on.

    `materialize._add_derivation_edges` now emits the same `KIND_*` constants
    `run_resolution` consumes, so the two sites cannot drift. What is still
    unpinned is the mapping from an *authored* derivation shape to its token:
    swap the arms and every dataset of the changed arm silently resolves to
    `NO_PROVENANCE`. This materializes a real graph per arm and asserts the
    emitted `sci:derivationKind` is that arm's constant.
    """
    for kind, expected in (
        ("workflow-run", KIND_WORKFLOW_RUN),
        ("workflow-recipe", KIND_WORKFLOW_RECIPE),
        ("member_of", KIND_MEMBER_OF),
    ):
        knowledge, ds_uri, _ = materialized_knowledge_for_dataset(kind=kind)
        assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == [Literal(expected)]


def test_dataset_without_derivation_emits_no_kind(materialized_knowledge_for_dataset):
    knowledge, ds_uri, _ = materialized_knowledge_for_dataset(kind=None)
    assert list(knowledge.objects(ds_uri, SCI_NS.derivationKind)) == []


def test_derivation_predicates_are_registered():
    from science_tool.graph.store.constants import PREDICATE_REGISTRY

    names = {entry["predicate"] for entry in PREDICATE_REGISTRY}
    assert {"sci:derivationKind", "sci:workflowRun", "sci:memberOfParent"} <= names

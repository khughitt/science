"""Typed method / workflow-step entities (umbrella Spec 0, task:t087)."""

from science_model.entities import MethodEntity, ProjectEntity, WorkflowStepEntity


def _base(**overrides) -> dict:
    fields = {
        "id": "workflow-step:cluster",
        "kind": "workflow-step",
        "title": "Cluster",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "entities/workflow-steps/cluster.md",
    }
    fields.update(overrides)
    return fields


def test_workflow_step_retains_workflow_and_rule_name() -> None:
    step = WorkflowStepEntity.model_validate(
        _base(workflow="workflow:scrna-pipeline", rule_name="cluster")
    )
    assert step.workflow == "workflow:scrna-pipeline"
    assert step.rule_name == "cluster"


def test_workflow_step_fields_default_to_empty() -> None:
    step = WorkflowStepEntity.model_validate(_base())
    assert step.workflow == ""
    assert step.rule_name == ""


def test_method_entity_is_a_project_entity() -> None:
    method = MethodEntity.model_validate(
        _base(id="method:leiden", kind="method", title="Leiden")
    )
    assert isinstance(method, ProjectEntity)
    assert method.canonical_id == "method:leiden"


def test_bare_project_entity_does_not_DECLARE_step_fields_but_no_longer_EATS_them() -> None:
    """The motivation, restated -- because the old assertion pinned the defect as a feature.

    It read `assert not hasattr(entity, "rule_name")` under the docstring "the base class silently
    ignores these keys", which is `extra="ignore"` asserted as desirable. D3.3 abolishes exactly that:
    a projection must never silently drop what the schema admits.

    What the typed subclass really buys is DECLARATION -- a typed field, a default, a place in
    `model_fields`, and a materializer that knows the predicate. What it does not buy, and must not,
    is the destruction of the value on every other kind.
    """
    entity = ProjectEntity.model_validate(_base(workflow="workflow:x", rule_name="cluster"))

    assert "rule_name" not in ProjectEntity.model_fields  # not DECLARED...
    assert entity.model_extra == {"workflow": "workflow:x", "rule_name": "cluster"}  # ...not LOST

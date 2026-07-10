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


def test_bare_project_entity_still_drops_step_fields() -> None:
    """Guards the motivation: the base class silently ignores these keys."""
    entity = ProjectEntity.model_validate(_base(workflow="workflow:x", rule_name="cluster"))
    assert not hasattr(entity, "rule_name")

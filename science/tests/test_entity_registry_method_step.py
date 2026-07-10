"""method / workflow-step resolve to typed classes (umbrella Spec 0, task:t087)."""

from science_model.entities import MethodEntity, ProjectEntity, WorkflowStepEntity

from science_tool.graph.entity_registry import EntityRegistry


def test_method_resolves_to_method_entity() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("method") is MethodEntity


def test_workflow_step_resolves_to_workflow_step_entity() -> None:
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("workflow-step") is WorkflowStepEntity


def test_workflow_still_resolves_to_project_entity() -> None:
    """`workflow` has a WorkflowEntity in the model, but is deliberately NOT bound
    in CORE_KIND_MODELS; binding it is out of scope for Spec 0."""
    registry = EntityRegistry.with_core_types()
    assert registry.resolve("workflow") is ProjectEntity

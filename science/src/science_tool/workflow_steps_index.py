"""Reverse index from a workflow to its steps and their methods.

Source-layer query shared by `register-run` (seed_policy derivation) and the
`dataset stochasticity` report. A pure lookup: it resolves refs and pairs each
step with its method, and applies no fail-closed guards — callers that require
them (register-run's `_reject_*_steps`) keep applying their own.
"""

from __future__ import annotations

from science_model.entities import MethodEntity, WorkflowStepEntity

from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import ProjectSources


def steps_and_methods_for_workflow(
    sources: ProjectSources,
    resolver: ReferenceResolver,
    workflow_id: str,
) -> list[tuple[WorkflowStepEntity, MethodEntity | None]]:
    """Steps whose `workflow` resolves to `workflow_id`, each with its method.

    Sorted by `step.id`. The method is `None` when the step names none or the
    named method does not resolve to a `MethodEntity`.
    """
    by_id = {entity.id: entity for entity in sources.entities}
    steps = [
        entity
        for entity in sources.entities
        if isinstance(entity, WorkflowStepEntity)
        and entity.workflow
        and resolver.resolve(entity.workflow).canonical_id == workflow_id
    ]
    steps.sort(key=lambda s: s.id)

    pairs: list[tuple[WorkflowStepEntity, MethodEntity | None]] = []
    for step in steps:
        method: MethodEntity | None = None
        if step.method:
            resolution = resolver.resolve(step.method)
            target = by_id.get(resolution.canonical_id) if resolution.canonical_id else None
            if isinstance(target, MethodEntity):
                method = target
        pairs.append((step, method))
    return pairs

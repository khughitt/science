"""Seed-binding hygiene for workflow-step definitions (umbrella Spec 1, task:t079).

A step applying an unclassified method is an ERROR: the classification is
required at the point of use, which is the first moment it is both knowable and
checkable. Everything else is a warning -- `task:t079` ships visibility first.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_model.entities import Entity, MethodEntity, Stochasticity, WorkflowStepEntity

from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE_STOCHASTICITY_MISSING = "workflow-step.method-stochasticity-missing"
RULE_SEED_BINDING_MISSING = "workflow-step.seed-binding-missing"
RULE_RATIONALE_MISSING = "workflow-step.rationale-missing"
RULE_BINDING_ON_DETERMINISTIC = "workflow-step.seed-binding-on-deterministic-method"
RULE_BINDING_UNKNOWN_PARAM = "workflow-step.seed-binding-unknown-param"


def _warn(path: Path, message: str, rule: str) -> Result:
    return Result(severity=Severity.WARN, path=path, line=None, message=message, rule=rule, task=None)


def _step_results(step: WorkflowStepEntity, method: MethodEntity, path: Path) -> Iterator[Result]:
    if method.stochasticity is None:
        yield Result(
            severity=Severity.ERROR,
            path=path,
            line=None,
            message=(
                f"{step.canonical_id} applies {method.canonical_id}, which declares no "
                "stochasticity; classify the method as deterministic, seedable, or "
                "nondeterministic."
            ),
            rule=RULE_STOCHASTICITY_MISSING,
            task=None,
        )
        return

    if method.stochasticity is Stochasticity.DETERMINISTIC:
        if step.seed_bindings:
            yield _warn(
                path,
                f"{step.canonical_id} binds seeds for {method.canonical_id}, which is "
                "deterministic; no binding is meaningful.",
                RULE_BINDING_ON_DETERMINISTIC,
            )
        return

    if method.stochasticity is Stochasticity.NONDETERMINISTIC and not step.rationale:
        yield _warn(
            path,
            f"{step.canonical_id} applies {method.canonical_id}, which is nondeterministic, "
            "and supplies no rationale.",
            RULE_RATIONALE_MISSING,
        )

    if not method.seed_params:
        # `method.seed-params-missing` owns this gap; reporting an unknown
        # parameter here as well would report one defect twice.
        return

    for param in sorted(set(step.seed_bindings) - set(method.seed_params)):
        yield _warn(
            path,
            f"{step.canonical_id} binds {param!r}, which is not among "
            f"{method.canonical_id}'s seed_params.",
            RULE_BINDING_UNKNOWN_PARAM,
        )

    if method.stochasticity is Stochasticity.SEEDABLE:
        for param in method.seed_params:
            if param not in step.seed_bindings:
                yield _warn(
                    path,
                    f"{step.canonical_id} applies seedable {method.canonical_id} and leaves "
                    f"{param!r} unbound.",
                    RULE_SEED_BINDING_MISSING,
                )


@Check(section="workflow steps", order=54)
def check_workflow_step_seed_bindings(ctx: ValidateContext) -> Iterator[Result]:
    """A step's seed bindings must agree with the method it applies."""
    sources = ctx.project_sources()
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    entity_index: dict[str, Entity] = {entity.canonical_id: entity for entity in sources.entities}
    for step in sources.entities:
        if not isinstance(step, WorkflowStepEntity) or not step.method:
            continue
        resolution = resolver.resolve(step.method)
        if resolution.status != "resolved" or resolution.canonical_id is None:
            # An unresolved reference is the compiler's and `graph audit`'s defect.
            continue
        method = entity_index.get(resolution.canonical_id)
        if not isinstance(method, MethodEntity):
            # A ref that resolves to a non-method entity is the compiler's defect
            # (it raises on a step whose `method:` resolves to a non-method).
            continue
        yield from _step_results(step, method, ctx.project_root / step.file_path)

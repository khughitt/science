"""Seed-binding hygiene for workflow-step definitions (umbrella Spec 1, task:t079).

A step applying an unclassified method is an ERROR: the classification is
required at the point of use, which is the first moment it is both knowable and
checkable. Everything else is a warning -- `task:t079` ships visibility first.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_model.entities import Entity, MethodEntity, Stochasticity, WorkflowStepEntity

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE_STOCHASTICITY_MISSING = "workflow-step.method-stochasticity-missing"
RULE_SEED_BINDING_MISSING = "workflow-step.seed-binding-missing"
RULE_RATIONALE_MISSING = "workflow-step.rationale-missing"
RULE_BINDING_ON_DETERMINISTIC = "workflow-step.seed-binding-on-deterministic-method"
RULE_BINDING_UNKNOWN_PARAM = "workflow-step.seed-binding-unknown-param"


def _method_index(entities: list[Entity]) -> dict[str, MethodEntity]:
    index: dict[str, MethodEntity] = {}
    for entity in entities:
        if not isinstance(entity, MethodEntity):
            continue
        index[entity.canonical_id] = entity
        for alias in entity.aliases or []:
            index.setdefault(alias, entity)
    return index


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
    methods = _method_index(sources.entities)
    for step in sources.entities:
        if not isinstance(step, WorkflowStepEntity) or not step.method:
            continue
        method = methods.get(step.method)
        if method is None:
            # An unresolved reference is the compiler's and `graph audit`'s defect.
            continue
        yield from _step_results(step, method, ctx.project_root / step.file_path)

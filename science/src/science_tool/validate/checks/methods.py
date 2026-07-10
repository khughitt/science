"""Method-local seed hygiene (umbrella Spec 1, task:t079)."""

from __future__ import annotations

from collections.abc import Iterator

from science_model.entities import MethodEntity, Stochasticity

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE_SEED_PARAMS_MISSING = "method.seed-params-missing"


@Check(section="methods", order=55)
def check_method_seed_params(ctx: ValidateContext) -> Iterator[Result]:
    """A seedable method should name the parameters that control its randomness.

    A warning, not an error: a method may be known to be seedable before its
    parameter is identified, and every seedable method in the live corpus is in
    exactly that state.
    """
    for entity in ctx.project_sources().entities:
        if not isinstance(entity, MethodEntity):
            continue
        if entity.stochasticity is Stochasticity.SEEDABLE and not entity.seed_params:
            yield Result(
                severity=Severity.WARN,
                path=ctx.project_root / entity.file_path,
                line=None,
                message=(
                    f"{entity.canonical_id} is seedable but names no seed_params; "
                    "a step cannot bind a seed it cannot name."
                ),
                rule=RULE_SEED_PARAMS_MISSING,
                task=None,
            )

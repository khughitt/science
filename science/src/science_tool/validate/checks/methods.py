"""Method-local seed hygiene (umbrella Spec 1, task:t079)."""

from __future__ import annotations

from collections.abc import Iterator

from science_model.entities import MethodEntity, Stochasticity

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

RULE_SEED_PARAMS_MISSING = "method.seed-params-missing"


SECTION, RULES = declare_validation_rules(
    section_id="methods",
    section_title="methods",
    section_order=155,
    rule_ids=("method.seed-params-missing",),
    severities=frozenset({"error", "warn", "info"}),
)


@Check(section=SECTION, order=55, producer_id="validate.methods", rules=tuple(RULES.values()))
def check_method_seed_params(ctx: ValidateContext) -> Iterator[CheckObservation]:
    """A seedable method should name the parameters that control its randomness.

    A warning, not an error: a method may be known to be seedable before its
    parameter is identified, and every seedable method in the live corpus is in
    exactly that state.
    """
    for entity in ctx.project_sources().entities:
        if not isinstance(entity, MethodEntity):
            continue
        if entity.stochasticity is Stochasticity.SEEDABLE and not entity.seed_params:
            yield validation_observation(
                severity=Severity.WARN,
                path=ctx.project_root / entity.file_path,
                line=None,
                message=f"{entity.canonical_id} is seedable but names no seed_params; a step cannot bind a seed it cannot name.",
                rule=RULES["method.seed-params-missing"],
                task=None,
                qualifiers={"key": []},
            )

"""Port of validate.sh "Checking research scope..." block.

if [ "$PROFILE" = "research" ] && [ ! -f "$SPECS_DIR/research-question.md" ]; then
    error "$SPECS_DIR/research-question.md not found — every project needs a research question"
fi
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.paths import resolve_paths
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


SECTION, RULES = declare_validation_rules(
    section_id="research-scope",
    section_title="research scope",
    section_order=106,
    rule_ids=("research-scope.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(severity: Severity, path: str | None, message: str) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=Path(path) if path is not None else None,
        line=None,
        message=message,
        rule=RULES["research-scope.check"],
        task=None,
        qualifiers={"key": []},
    )


@Check(section=SECTION, order=3, producer_id="validate.research-scope", rules=tuple(RULES.values()))
def check_research_scope(ctx: ValidateContext) -> Iterator[CheckObservation]:
    if resolve_paths(ctx.project_root).profile != "research":
        return

    from science_tool.entities import singleton_path

    research_question = ctx.project_root / singleton_path("research-question")
    if not research_question.is_file():
        yield _result(
            Severity.ERROR,
            "entities/research-question.md",
            "research-question.md not found — every project needs a research question",
        )

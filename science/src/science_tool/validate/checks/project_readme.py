"""Project README convention checks."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_LEGACY_SECTIONS = ("## Current Priorities", "## Next Review Trigger")


SECTION, RULES = declare_validation_rules(
    section_id="project-readme",
    section_title="project readme",
    section_order=113,
    rule_ids=("project-readme.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(
    severity: Severity,
    path: str | None,
    message: str,
    *,
    key: list[str],
) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=Path(path) if path is not None else None,
        line=None,
        message=message,
        rule=RULES["project-readme.check"],
        task=None,
        qualifiers={"key": key},
    )


@Check(section=SECTION, order=10, producer_id="validate.project-readme", rules=tuple(RULES.values()))
def check_project_readme(ctx: ValidateContext) -> Iterator[CheckObservation]:
    readme_path = ctx.project_root / "README.md"
    if readme_path.is_file():
        yield _result(
            Severity.INFO,
            "README.md",
            "README.md exists",
            key=["exists"],
        )
        text = ctx.read_text_cached(readme_path)
        for section in _LEGACY_SECTIONS:
            if section in text:
                yield _result(
                    Severity.WARN,
                    "README.md",
                    f"README.md contains legacy task-queue section '{section}' — migrate tasks to tasks/active/ via /science:tasks",
                    key=["legacy-section", section],
                )
        return

    yield _result(
        Severity.INFO,
        "README.md",
        "README.md not found; use README.md for high-level project context and strategy",
        key=["exists"],
    )

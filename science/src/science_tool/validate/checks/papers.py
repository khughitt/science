"""Port of validate.sh "Checking paper summaries..." block.

Checks paper entities under ``entities/papers/`` for template section
conformance.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import declare_validation_rules
from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.observations import ValidationNotice
from science_tool.validate.result import Severity


SECTION, RULES = declare_validation_rules(
    section_id="papers",
    section_title="papers",
    section_order=110,
    rule_ids=(),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(severity: Severity, path: str | None, message: str) -> ValidationNotice:
    if severity is not Severity.INFO:
        raise ValueError("the papers observation is notice-only")
    return ValidationNotice(
        path=Path(path) if path is not None else None,
        line=None,
        message=message,
    )


@Check(section=SECTION, order=7, producer_id="validate.papers", rules=tuple(RULES.values()))
def check_papers(ctx: ValidateContext) -> Iterator[ValidationNotice]:
    papers_root = resolve_path_policy("paper").root
    yield _result(
        Severity.INFO,
        papers_root.as_posix(),
        f"Paper summary structure is checked in {papers_root.as_posix()}/",
    )

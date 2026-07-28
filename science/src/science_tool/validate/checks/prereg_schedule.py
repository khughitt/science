"""A frozen sampling schedule must declare the domain that calibrated it.

fb-2026-07-25-009: natural-systems `pre-registration:0034` imported `0026`'s
sampling schedule onto a 40× larger, far sparser substrate without establishing
that the old schedule still mixed adequately. The trigger is schedule CONTENT,
not the presence of any particular heading.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.prereg_frozen import frozen_because
from science_tool.validate.result import Severity

# Word-bounded on purpose. An earlier draft used bare `thin ` and a
# case-insensitive `ESS`; measured against the natural-systems corpus that
# matched 34 of 34 pre-registrations -- `thin ` inside "within", `ess` inside
# "unless"/"process"/"assess". An antecedent that selects the whole corpus is
# exactly as uninformative as one that selects none of it, and it looks like a
# success. This pattern selects 5 of 34, the documents that genuinely declare a
# schedule. It remains a PROSE HEURISTIC, which is why the rule is WARN and
# ungated.
_SCHEDULE_TOKENS = re.compile(r"\bburn[- ]in\b|\bthinning\b|\bR[_-]?hat\b|\bESS\b")
_COST_GATE_HEADING = re.compile(
    r"^## Cost Gate \(execution geometry\)[ \t]*$",
    re.MULTILINE,
)
_NEXT_SECTION = re.compile(r"^##[ \t]+", re.MULTILINE)
_PLACEHOLDER = re.compile(r"^<.*>$")
_REQUIRED_ROWS = ("Target geometry", "Calibration domain")
_RULE = "prereg.schedule-calibration-domain"


SECTION, RULES = declare_validation_rules(
    section_id="prereg-schedule",
    section_title="prereg schedule",
    section_order=117,
    rule_ids=("prereg.schedule-calibration-domain",),
    severities=frozenset({"error", "warn", "info"}),
)


def _warn(relative: str, message: str, *, key: list[str]) -> CheckObservation:
    return validation_observation(
        severity=Severity.WARN,
        path=Path(relative),
        line=None,
        message=message,
        rule=RULES["prereg.schedule-calibration-domain"],
        task=None,
        qualifiers={"key": key},
    )


def _section(body: str, heading_pattern: re.Pattern[str]) -> str | None:
    heading = heading_pattern.search(body)
    if heading is None:
        return None
    following = body[heading.end() :]
    next_section = _NEXT_SECTION.search(following)
    return following[: next_section.start()] if next_section is not None else following


def _cost_gate_section(body: str) -> str | None:
    return _section(body, _COST_GATE_HEADING)


def _table_rows(section: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] in _REQUIRED_ROWS:
            rows[cells[0]] = cells[1]
    return rows


def _unfilled_state(rows: dict[str, str], row: str) -> str | None:
    if row not in rows:
        return "absent"
    value = rows[row].strip()
    if not value:
        return "empty"
    if _PLACEHOLDER.fullmatch(value):
        return "placeholder"
    return None


@Check(section=SECTION, order=13, producer_id="validate.prereg-schedule", rules=tuple(RULES.values()))
def check_prereg_schedule(ctx: ValidateContext) -> Iterator[CheckObservation]:
    entities_root = ctx.project_root / resolve_path_policy("pre-registration").root
    if not entities_root.is_dir():
        return

    for path in sorted(entities_root.glob("*.md")):
        if not path.is_file():
            continue
        frontmatter = ctx.frontmatter(path)
        if str(frontmatter.get("kind", "")) != "pre-registration":
            continue
        if frozen_because(frontmatter) is None:
            continue
        body = ctx.body(path)
        if _SCHEDULE_TOKENS.search(body) is None:
            continue

        relative = path.relative_to(ctx.project_root).as_posix()
        section = _cost_gate_section(body)
        if section is not None:
            rows = _table_rows(section)
            for row in _REQUIRED_ROWS:
                state = _unfilled_state(rows, row)
                if state is not None:
                    yield _warn(
                        relative,
                        f"{relative} declares a sampling schedule but its Cost Gate row "
                        f"'{row}' is {state}; fill the row before freezing the schedule",
                        key=["cost-gate-row", row, state],
                    )
            continue
        yield _warn(
            relative,
            f"{relative} declares a sampling schedule but carries no Cost Gate; "
            "the schedule's calibration domain is undeclared",
            key=["cost-gate"],
        )

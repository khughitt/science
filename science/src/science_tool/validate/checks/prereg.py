"""Port of validate.sh pre-registration document block.

for f in "$DOC_DIR/meta/pre-registration-"*.md "$DOC_DIR/pre-registrations/"*.md; do
    # require sections, then require committed/spec when type is pre-registration
done
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_SECTIONS = ("Hypotheses Under Test", "Expected Outcomes", "Decision Criteria", "Null Result Plan")


SECTION, RULES = declare_validation_rules(
    section_id="prereg",
    section_title="prereg",
    section_order=115,
    rule_ids=("prereg.check",),
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
        rule=RULES["prereg.check"],
        task=None,
        qualifiers={"key": key},
    )


@Check(section=SECTION, order=12, producer_id="validate.prereg", rules=tuple(RULES.values()))
def check_prereg(ctx: ValidateContext) -> Iterator[CheckObservation]:
    entities_root = ctx.project_root / resolve_path_policy("pre-registration").root
    paths = sorted(entities_root.glob("*.md")) if entities_root.is_dir() else []
    for path in paths:
        if not path.is_file():
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        text = ctx.read_text_cached(path)
        for section in _SECTIONS:
            if f"## {section}" not in text:
                yield _result(
                    Severity.WARN,
                    relative,
                    f"Pre-registration {relative} missing section: {section}",
                    key=["required-section", section],
                )

        # Keyed on `kind`, which is what the template writes. This read `type:`
        # until 2026-07-20, so the two checks below had never fired: all 27
        # pre-registrations in the corpus declare `kind:` and none declare `type:`.
        frontmatter = ctx.frontmatter(path)
        if str(frontmatter.get("kind", "")) != "pre-registration":
            continue

        if "committed" not in frontmatter:
            yield _result(
                Severity.WARN,
                relative,
                f"{relative} kind 'pre-registration' should declare a 'committed:' date in frontmatter",
                key=["field", "committed"],
            )
        if "spec" not in frontmatter:
            yield _result(
                Severity.WARN,
                relative,
                f"{relative} kind 'pre-registration' should declare a 'spec:' field (empty string is OK if no paired design doc)",
                key=["field", "spec"],
            )

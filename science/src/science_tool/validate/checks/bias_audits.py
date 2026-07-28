"""Port of validate.sh bias audit document block.

for f in "$DOC_DIR/meta/bias-audit-"*.md; do
    # require bias audit sections
done
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_SECTIONS = ("Cognitive Biases", "Methodological Biases", "Summary")


SECTION, RULES = declare_validation_rules(
    section_id="bias-audits",
    section_title="bias audits",
    section_order=119,
    rule_ids=("bias-audits.check",),
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
        rule=RULES["bias-audits.check"],
        task=None,
        qualifiers={"key": key},
    )


@Check(section=SECTION, order=14, producer_id="validate.bias-audits", rules=tuple(RULES.values()))
def check_bias_audits(ctx: ValidateContext) -> Iterator[CheckObservation]:
    for path in sorted((ctx.doc_dir / "meta").glob("bias-audit-*.md")):
        if not path.is_file():
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        text = ctx.read_text_cached(path)
        for section in _SECTIONS:
            if f"## {section}" not in text:
                yield _result(
                    Severity.WARN,
                    relative,
                    f"Bias audit {relative} missing section: {section}",
                    key=["required-section", section],
                )

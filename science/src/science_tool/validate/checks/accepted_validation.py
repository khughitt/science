"""Fail-closed guard: an `accepted_validation` entry for an evidence-scoped rule
must carry a complete evidence-signature token (design §5.5). This is a canonical
CHECK, not a filter side effect, because `validate/cli.py` treats acceptance
filtering as removal-only (`len(filtered) == len(original)`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.acceptance import (
    EVIDENCE_SCOPED_RULES,
    accepted_validation_entries,
    entry_is_well_scoped,
)
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_RULE = "accepted-validation.evidence-scope-required"


@Check(section="accepted-validation hygiene", order=206)
def check_accepted_validation(ctx: ValidateContext) -> Iterator[Result]:
    for entry in accepted_validation_entries(ctx.project_root):
        rule = entry.get("rule")
        if rule in EVIDENCE_SCOPED_RULES and not entry_is_well_scoped(entry):
            yield Result(
                Severity.WARN,
                Path("science.yaml"),
                None,
                f"accepted_validation entry for {rule!r} (path={entry.get('path')!r}) must be "
                f"evidence-scoped: message_contains needs a complete 'evidence-signature: v1:<64-hex>' "
                f"token AND path must name one non-empty, project-relative plan, else it would blind "
                f"that rule even after the plan's deliverables change.",
                _RULE,
                None,
            )

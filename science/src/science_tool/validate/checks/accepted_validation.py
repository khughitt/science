"""Fail-closed guard: an `accepted_validation` entry for an evidence-scoped rule
must carry a complete evidence-signature token (design §5.5). This is a canonical
CHECK, not a filter side effect, because `validate/cli.py` treats acceptance
filtering as removal-only (`len(filtered) == len(original)`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_model.audit.fingerprint import canonical_json

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.data_root import PROJECT_CONFIG_FILENAME
from science_tool.validate.acceptance import (
    SIGNATURE_TOKEN_SPEC,
    EVIDENCE_SCOPED_RULES,
    accepted_validation_entries,
    canonical_acceptance_severity,
    entry_is_well_scoped,
)
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_RULE = "accepted-validation.evidence-scope-required"


SECTION, RULES = declare_validation_rules(
    section_id="accepted-validation",
    section_title="accepted validation",
    section_order=160,
    rule_ids=("accepted-validation.evidence-scope-required",),
    severities=frozenset({"error", "warn", "info"}),
)


@Check(section=SECTION, order=206, producer_id="validate.accepted-validation", rules=tuple(RULES.values()))
def check_accepted_validation(ctx: ValidateContext) -> Iterator[CheckObservation]:
    emitted: set[str] = set()
    for entry in accepted_validation_entries(ctx.project_root):
        if not isinstance(entry, dict):
            continue
        rule = entry.get("rule")
        if rule in EVIDENCE_SCOPED_RULES and not entry_is_well_scoped(entry):
            semantic_fields = {
                name: entry.get(name)
                for name in (
                    "rule",
                    "severity",
                    "path",
                    "task",
                    "message_contains",
                )
            }
            severity = canonical_acceptance_severity(semantic_fields["severity"])
            if severity is None:
                del semantic_fields["severity"]
            else:
                semantic_fields["severity"] = severity
            semantic_key = canonical_json(semantic_fields).decode("utf-8")
            if semantic_key in emitted:
                continue
            emitted.add(semantic_key)
            yield validation_observation(
                severity=Severity.WARN,
                path=Path(PROJECT_CONFIG_FILENAME),
                line=None,
                message=f"accepted_validation entry for {rule!r} (path={entry.get('path')!r}) must be evidence-scoped: message_contains needs a complete '{SIGNATURE_TOKEN_SPEC}' token AND path must name one non-empty, project-relative plan, else it would blind that rule even after the plan's deliverables change.",
                rule=RULES["accepted-validation.evidence-scope-required"],
                task=None,
                qualifiers={"key": ["acceptance-entry", semantic_key]},
            )

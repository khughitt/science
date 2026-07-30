from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection

from science_tool.findings.producers import FindingProducer


class CheckErrorQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: str


class RuntimeEmptyQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")


RUNTIME_SECTION = FindingSection(
    id="validate-runtime",
    title="Validation runtime",
    section_order=199,
)
RULE_CHECK_ERROR = FindingRule(
    id="validate.check-error",
    severities=frozenset({"error"}),
    subject_types=frozenset({"project"}),
    qualifier_schema=CheckErrorQualifiers,
    identity_qualifiers=("check",),
    title="Validation check could not run",
    section=RUNTIME_SECTION.id,
    display_order=19901,
    default_visibility="visible",
)
RULE_SIDECAR_REMOVED = FindingRule(
    id="validate.sidecar-removed",
    severities=frozenset({"error"}),
    subject_types=frozenset({"project"}),
    qualifier_schema=RuntimeEmptyQualifiers,
    title="Legacy validation sidecar removed",
    section=RUNTIME_SECTION.id,
    display_order=19902,
    default_visibility="visible",
)
RULE_PYTHON_SIDECAR_REMOVED = FindingRule(
    id="validate.python-sidecar-removed",
    severities=frozenset({"error"}),
    subject_types=frozenset({"project"}),
    qualifier_schema=RuntimeEmptyQualifiers,
    title="Python validation sidecar removed",
    section=RUNTIME_SECTION.id,
    display_order=19903,
    default_visibility="visible",
)
VALIDATION_RUNTIME_PRODUCER = FindingProducer(
    producer_id="validate.runtime",
    namespace="validate_checks",
    source_module="validate/runtime.py",
    rules=(RULE_CHECK_ERROR, RULE_SIDECAR_REMOVED, RULE_PYTHON_SIDECAR_REMOVED),
    sections=(RUNTIME_SECTION,),
)

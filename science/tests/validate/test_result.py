from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection, LocationEvidence

from science_tool.validate import Result, Severity


class _Qualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: list[str]
    task: str | None = None


_SECTION = FindingSection(id="result-test", title="Result test", section_order=1)
_RULE = FindingRule(
    id="result-test.problem",
    severities={"error", "warn", "info"},
    subject_types={"path", "project"},
    qualifier_schema=_Qualifiers,
    identity_qualifiers=("key",),
    title="Problem",
    section=_SECTION.id,
    display_order=1,
)


def _result(**changes: object) -> Result:
    values: dict[str, object] = {
        "severity": Severity.ERROR,
        "path": Path("doc/example.md"),
        "line": 3,
        "message": "broken",
        "rule": _RULE,
        "task": "task:1",
        "qualifiers": {"key": ["field"], "task": "task:1"},
    }
    values.update(changes)
    return Result(**values)  # type: ignore[arg-type]


def test_result_refuses_a_string_rule_at_runtime() -> None:
    invalid_rule: Any = "literal"
    with pytest.raises(TypeError, match="Result.rule must be FindingRule, got str"):
        _result(rule=invalid_rule)


def test_result_is_frozen() -> None:
    result = _result()
    with pytest.raises(FrozenInstanceError):
        result.message = "changed"  # type: ignore[misc]


def test_result_equality_uses_all_fields() -> None:
    first = _result()
    assert first == _result()
    assert first != replace(first, severity=Severity.WARN)


def test_result_projects_to_canonical_finding() -> None:
    finding = _result().to_finding(Path.cwd())
    assert finding.rule_id == _RULE.id
    assert finding.subject.path == "doc/example.md"
    assert finding.qualifiers == {"key": ("field",), "task": "task:1"}
    assert finding.evidence == (LocationEvidence(path="doc/example.md", line=3),)


def test_severity_from_str_accepts_names_and_values_case_insensitively() -> None:
    assert Severity.from_str("ERROR") is Severity.ERROR
    assert Severity.from_str("warn") is Severity.WARN
    assert Severity.from_str("Info") is Severity.INFO
    with pytest.raises(ValueError, match="unknown severity"):
        Severity.from_str("debug")

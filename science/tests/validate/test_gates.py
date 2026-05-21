from pathlib import Path

import pytest

from science_tool.validate.gates import (
    GATE_TIERS,
    cumulative_rules,
    gated_findings,
    resolve_gate_tier,
)
from science_tool.validate.result import Result, Severity


def _r(rule: str) -> Result:
    return Result(Severity.WARN, Path("code/x.py"), None, "msg", rule, None)


def test_tier_order_is_stable() -> None:
    assert GATE_TIERS == (
        "report",
        "ghost-files",
        "decision-bearing-orphans",
        "hygiene",
    )


def test_report_tier_gates_nothing() -> None:
    assert cumulative_rules("report") == frozenset()


def test_ghost_files_tier_gates_ghost_and_malformed() -> None:
    assert cumulative_rules("ghost-files") == frozenset(
        {"code.ghost", "code.malformed-block"}
    )


def test_hygiene_tier_is_cumulative() -> None:
    rules = cumulative_rules("hygiene")
    assert {"code.ghost", "code.malformed-block"} <= rules  # includes lower tiers
    assert {"code.metadata-gap", "code.unresolved-task", "code.uncommitted"} <= rules


def test_gated_findings_filters_by_cumulative_rules() -> None:
    findings = [_r("code.ghost"), _r("code.metadata-gap"), _r("manifest")]
    assert [f.rule for f in gated_findings(findings, "ghost-files")] == ["code.ghost"]
    assert {f.rule for f in gated_findings(findings, "hygiene")} == {
        "code.ghost",
        "code.metadata-gap",
    }
    assert gated_findings(findings, "report") == []


def test_resolve_prefers_flag_over_manifest() -> None:
    assert resolve_gate_tier("ghost-files", {"code_gate": "report"}) == "ghost-files"


def test_resolve_falls_back_to_manifest_then_default() -> None:
    assert resolve_gate_tier(None, {"code_gate": "hygiene"}) == "hygiene"
    assert resolve_gate_tier(None, {}) == "report"


def test_resolve_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="unknown code gate tier"):
        resolve_gate_tier(None, {"code_gate": "bogus"})

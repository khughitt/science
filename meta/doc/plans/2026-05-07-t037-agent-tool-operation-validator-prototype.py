#!/usr/bin/env python3
"""
Prototype validator for t037 v1.2 `agent-tool-operation` structural and
reason-code biconditional rules.

Standalone runner. NOT integrated into meta/validate.sh; this is a study.

Run with: python meta/doc/plans/2026-05-07-t037-agent-tool-operation-validator-prototype.py
Exits 0 if all tests match expectations; nonzero otherwise.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

EXT_KEY = "extension/agent-tool-operation"

AGENT_ROLES: set[str] = {
    "paper-reader",
    "field-extractor",
    "synthesis-author",
    "hypothesis-generator",
    "causal-prior-elicitor",
    "tool-planner",
    "tool-executor",
    "pipeline-runner",
    "graph-editor",
    "validator",
    "critic",
    "safety-reviewer",
    "task-editor",
}

ABSENCE_SENSITIVE_ROLES: set[str] = {
    "paper-reader",
    "field-extractor",
    "synthesis-author",
    "hypothesis-generator",
    "causal-prior-elicitor",
    "validator",
    "critic",
}

RETRIEVAL_METHODS: set[str] = {
    "rag-retrieval",
    "kg-filter",
    "web-search",
    "file-search",
}

PERMITTED_ROLES: set[str] = {
    "record-only",
    "quality-record-only",
    "prioritize-attention",
    "gate-update",
}

BLOCKING_CODES: set[str] = {
    "agent-source-unvalidated",
    "tool-chain-unvalidated",
    "safety-check-missing",
    "information-absence-undetected",
}


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    path: str
    rule: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.severity:5}] {self.rule:8} {self.path}: {self.msg}"


@dataclass(frozen=True)
class ResolvedOperationView:
    """Materialized registry state needed by t037 biconditional rules."""

    invokes_capability: bool = True
    # v1 prototype collapse: the real registry will expose per-protocol results.
    tool_chain_has_passed_validation: bool = False
    applicable_safety_policy: bool = False


def validate_agent_tool_operation(
    payload: dict,
    resolved_view: ResolvedOperationView,
) -> list[Issue]:
    issues: list[Issue] = []

    if EXT_KEY not in payload:
        return issues

    core = payload.get("core", {}) or {}
    ext = payload.get(EXT_KEY, {}) or {}
    reason_codes = set(core.get("reason_codes") or [])

    agent_role = ext.get("agent_role")
    if agent_role not in AGENT_ROLES:
        issues.append(
            Issue(
                "error",
                f"{EXT_KEY}.agent_role",
                "ato-2",
                f"agent_role is required and must be one of {sorted(AGENT_ROLES)}",
            )
        )

    validation_role = core.get("validation_role")
    if validation_role == "strengthen-belief":
        issues.append(
            Issue(
                "error",
                "core.validation_role",
                "ato-3",
                "agent-tool-operation cannot directly use validation_role strengthen-belief",
            )
        )

    tool_chain_ref = ext.get("tool_chain_ref")
    if resolved_view.invokes_capability and not _is_nonempty(tool_chain_ref):
        issues.append(
            Issue(
                "error",
                f"{EXT_KEY}.tool_chain_ref",
                "ato-4",
                "operations that invoke a capability must reference a one-step-or-more tool_chain_ref",
            )
        )

    safety_status = ext.get("safety_check_status")
    has_safety_code = "safety-check-missing" in reason_codes
    if not resolved_view.applicable_safety_policy:
        if safety_status != "not-applicable" or has_safety_code:
            issues.append(
                Issue(
                    "error",
                    f"{EXT_KEY}.safety_check_status",
                    "ato-5",
                    "without an applicable safety policy, safety_check_status must be not-applicable and safety-check-missing must not be declared",
                )
            )
    else:
        safety_missing = safety_status in {"skipped", "unknown"}
        if safety_status == "not-applicable" or safety_missing != has_safety_code:
            issues.append(
                Issue(
                    "error",
                    "core.reason_codes",
                    "ato-5",
                    "with an applicable safety policy, skipped/unknown safety status requires exactly safety-check-missing",
                )
            )

    agent_unvalidated = (
        _is_nonempty(ext.get("agent_model_version"))
        and ext.get("validation_status_detail") == "unvalidated"
    )
    has_agent_code = "agent-source-unvalidated" in reason_codes
    if agent_unvalidated != has_agent_code:
        issues.append(
            Issue(
                "error",
                "core.reason_codes",
                "ato-6",
                "agent-source-unvalidated iff agent_model_version is present and validation_status_detail is unvalidated",
            )
        )

    chain_unvalidated = (
        _is_nonempty(tool_chain_ref)
        and not resolved_view.tool_chain_has_passed_validation
    )
    has_chain_code = "tool-chain-unvalidated" in reason_codes
    if chain_unvalidated != has_chain_code:
        issues.append(
            Issue(
                "error",
                "core.reason_codes",
                "ato-7",
                "tool-chain-unvalidated iff tool_chain_ref is present and the resolved chain has no passed validation",
            )
        )

    context_uncertain = (
        ext.get("context_selection_method") in RETRIEVAL_METHODS
        and ext.get("context_completeness") != "complete-for-task"
    )
    has_context_code = "context-retrieval-uncertain" in reason_codes
    if context_uncertain != has_context_code:
        issues.append(
            Issue(
                "error",
                "core.reason_codes",
                "ato-8",
                "context-retrieval-uncertain iff retrieval/filter/search context is not complete-for-task",
            )
        )

    absence_undetected = (
        ext.get("abstention_supported") is False
        and agent_role in ABSENCE_SENSITIVE_ROLES
    )
    has_absence_code = "information-absence-undetected" in reason_codes
    if absence_undetected != has_absence_code:
        issues.append(
            Issue(
                "error",
                "core.reason_codes",
                "ato-9",
                "information-absence-undetected iff abstention is unsupported for an absence-sensitive role",
            )
        )

    if not _is_nonempty(ext.get("target_artifact_refs")) and not _is_nonempty(
        ext.get("abstention_reason")
    ):
        issues.append(
            Issue(
                "error",
                f"{EXT_KEY}.target_artifact_refs",
                "ato-10",
                "target_artifact_refs must be non-empty unless abstention_reason is present",
            )
        )

    return issues


def _is_nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, tuple, set, dict)):
        return len(value) > 0
    return True


def _base_payload() -> dict:
    return {
        "core": {
            "artifact_type": "agent-tool-operation",
            "extensions": ["agent-tool-operation"],
            "validation_role": "record-only",
            "reason_codes": [],
        },
        EXT_KEY: {
            "target_artifact_refs": ["artifact:target"],
            "agent_role": "tool-executor",
            "tool_chain_ref": "chain:validated",
            "context_selection_method": "explicit-user-provided",
            "context_completeness": "complete-for-task",
            "safety_check_status": "not-applicable",
            "validation_status_detail": "validated",
            "abstention_supported": True,
        },
    }


def _codes(payload: dict) -> list[str]:
    return payload["core"].setdefault("reason_codes", [])


def t01_minimal_valid() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    return (
        "01-minimal-valid",
        _base_payload(),
        ResolvedOperationView(tool_chain_has_passed_validation=True),
        set(),
    )


def t02_strengthen_forbidden() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload["core"]["validation_role"] = "strengthen-belief"
    return ("02-strengthen-forbidden", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-3"})


def t03_unknown_agent_role() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload[EXT_KEY]["agent_role"] = "unsupported-role"
    return ("03-unknown-agent-role", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-2"})


def t04_direct_capability_without_chain() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    del payload[EXT_KEY]["tool_chain_ref"]
    return ("04-direct-capability-without-chain", payload, ResolvedOperationView(), {"ato-4"})


def t05_no_safety_policy_not_applicable_clean() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    return ("05-no-safety-policy-not-applicable-clean", _base_payload(), ResolvedOperationView(tool_chain_has_passed_validation=True), set())


def t06_safety_code_overdeclared() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    _codes(payload).append("safety-check-missing")
    return ("06-safety-code-overdeclared", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-5"})


def t07_safety_policy_skipped_missing_code() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload[EXT_KEY]["safety_check_status"] = "skipped"
    return ("07-safety-policy-skipped-missing-code", payload, ResolvedOperationView(applicable_safety_policy=True, tool_chain_has_passed_validation=True), {"ato-5"})


def t08_agent_unvalidated_missing_code() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload[EXT_KEY]["agent_model_version"] = "model:v1"
    payload[EXT_KEY]["validation_status_detail"] = "unvalidated"
    return ("08-agent-unvalidated-missing-code", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-6"})


def t09_agent_unvalidated_overdeclared() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    _codes(payload).append("agent-source-unvalidated")
    return ("09-agent-unvalidated-overdeclared", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-6"})


def t10_tool_chain_unvalidated_missing_code() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    return ("10-tool-chain-unvalidated-missing-code", _base_payload(), ResolvedOperationView(), {"ato-7"})


def t11_tool_chain_unvalidated_overdeclared() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    _codes(payload).append("tool-chain-unvalidated")
    return ("11-tool-chain-unvalidated-overdeclared", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-7"})


def t12_context_retrieval_uncertain_missing_code() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload[EXT_KEY]["context_selection_method"] = "kg-filter"
    payload[EXT_KEY]["context_completeness"] = "partial"
    return ("12-context-retrieval-uncertain-missing-code", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-8"})


def t13_context_retrieval_uncertain_overdeclared() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    _codes(payload).append("context-retrieval-uncertain")
    return ("13-context-retrieval-uncertain-overdeclared", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-8"})


def t14_explicit_context_partial_no_code_clean() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload[EXT_KEY]["context_completeness"] = "partial"
    return ("14-explicit-context-partial-no-code-clean", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), set())


def t15_information_absence_missing_code() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload[EXT_KEY]["agent_role"] = "paper-reader"
    payload[EXT_KEY]["abstention_supported"] = False
    return ("15-information-absence-missing-code", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-9"})


def t16_information_absence_overdeclared_non_sensitive_role() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload[EXT_KEY]["abstention_supported"] = False
    _codes(payload).append("information-absence-undetected")
    return ("16-information-absence-overdeclared-non-sensitive-role", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-9"})


def t17_no_target_without_abstention() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload[EXT_KEY]["target_artifact_refs"] = []
    return ("17-no-target-without-abstention", payload, ResolvedOperationView(tool_chain_has_passed_validation=True), {"ato-10"})


def t18_no_extension_no_issues() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    return ("18-no-extension-no-issues", {"core": {"extensions": []}}, ResolvedOperationView(), set())


def t19_v12_pilot_adapted_ding() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload["core"]["reason_codes"] = [
        "agent-source-unvalidated",
        "tool-chain-unvalidated",
        "safety-check-missing",
        "information-absence-undetected",
    ]
    payload[EXT_KEY].update(
        {
            "target_artifact_refs": ["hypothesis:scitoolagent-generated-candidate"],
            "agent_role": "hypothesis-generator",
            "agent_model_version": "scitoolagent-summary-only",
            "tool_chain_ref": "chain:scitoolkg-retrieve-plan-execute-summarize",
            "context_selection_method": "kg-filter",
            "context_completeness": "complete-for-task",
            "safety_check_status": "unknown",
            "validation_status_detail": "unvalidated",
            "abstention_supported": False,
        }
    )
    return ("19-v12-pilot-adapted-ding", payload, ResolvedOperationView(applicable_safety_policy=True), set())


def t20_v12_pilot_adapted_paper_reader() -> tuple[str, dict, ResolvedOperationView, set[str]]:
    payload = _base_payload()
    payload["core"]["reason_codes"] = [
        "agent-source-unvalidated",
        "tool-chain-unvalidated",
        "information-absence-undetected",
    ]
    payload[EXT_KEY].update(
        {
            "target_artifact_refs": ["paper-summary:Yu2026"],
            "agent_role": "paper-reader",
            "agent_model_version": "claude-sonnet-4-5",
            "tool_chain_ref": "chain:pdf-read-summarize",
            "context_selection_method": "explicit-user-provided",
            "context_completeness": "unknown",
            "safety_check_status": "not-applicable",
            "validation_status_detail": "unvalidated",
            "abstention_supported": False,
        }
    )
    return ("20-v12-pilot-adapted-paper-reader", payload, ResolvedOperationView(), set())


def _rules(issues: list[Issue]) -> set[str]:
    return {i.rule for i in issues}


def run_tests() -> int:
    tests = [
        t01_minimal_valid,
        t02_strengthen_forbidden,
        t03_unknown_agent_role,
        t04_direct_capability_without_chain,
        t05_no_safety_policy_not_applicable_clean,
        t06_safety_code_overdeclared,
        t07_safety_policy_skipped_missing_code,
        t08_agent_unvalidated_missing_code,
        t09_agent_unvalidated_overdeclared,
        t10_tool_chain_unvalidated_missing_code,
        t11_tool_chain_unvalidated_overdeclared,
        t12_context_retrieval_uncertain_missing_code,
        t13_context_retrieval_uncertain_overdeclared,
        t14_explicit_context_partial_no_code_clean,
        t15_information_absence_missing_code,
        t16_information_absence_overdeclared_non_sensitive_role,
        t17_no_target_without_abstention,
        t18_no_extension_no_issues,
        t19_v12_pilot_adapted_ding,
        t20_v12_pilot_adapted_paper_reader,
    ]
    failures = 0
    for fn in tests:
        name, payload, resolved_view, expected = fn()
        issues = validate_agent_tool_operation(payload, resolved_view)
        got = _rules(issues)
        if got != expected:
            failures += 1
            print(f"FAIL {name}: expected {sorted(expected)}, got {sorted(got)}")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"PASS {name}: {sorted(got)}")
    print(f"{len(tests) - failures}/{len(tests)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run_tests())

from __future__ import annotations

from pathlib import Path

import pytest
from science_model.audit import AuditFinding, PathSubject

from science_tool.correspondence.signature import SIGNATURE_VERSION
from science_tool.validate.acceptance import (
    EVIDENCE_SCOPED_RULES,
    entry_is_evidence_scoped,
    entry_suppresses,
    filter_accepted_warnings,
)


def test_pre_migration_key_encodes_matcher_semantics_not_raw_yaml():
    from science_tool.validate.acceptance import pre_migration_acceptance_key

    absent = {"rule": "paper.status-vocabulary", "reason": "known"}
    malformed_wildcard = {
        "rule": "paper.status-vocabulary",
        "severity": 7,
        "reason": "another explanation",
    }
    assert pre_migration_acceptance_key(absent) == pre_migration_acceptance_key(malformed_wildcard)


def test_pre_migration_key_includes_every_match_discriminator():
    from science_tool.validate.acceptance import pre_migration_acceptance_key

    base = {
        "rule": "plan.correspondence-drift",
        "severity": "warning",
        "path": "entities/plans/1.md",
        "task": "t001",
        "message_contains": ["evidence-signature: v1:" + "a" * 64],
        "reason": "known",
    }
    keys = {
        pre_migration_acceptance_key(base),
        pre_migration_acceptance_key({**base, "path": "entities/plans/2.md"}),
        pre_migration_acceptance_key({**base, "task": "t002"}),
        pre_migration_acceptance_key({**base, "severity": "error"}),
        pre_migration_acceptance_key({**base, "message_contains": ["different"]}),
    }
    assert len(keys) == 5


@pytest.mark.parametrize("malformed", [7, ["valid", 7]])
def test_pre_migration_key_refuses_message_matchers_that_can_never_match(
    malformed,
):
    from science_tool.validate.acceptance import pre_migration_acceptance_key

    with pytest.raises(ValueError, match="malformed message_contains"):
        pre_migration_acceptance_key(
            {
                "rule": "paper.status-vocabulary",
                "message_contains": malformed,
                "reason": "dead entry",
            }
        )


_SIG = f"{SIGNATURE_VERSION}:" + "a" * 64  # the bare hash token (NOT scoped on its own)
_LABELED = f"evidence-signature: {_SIG}"  # the complete labeled token that IS scoped


def _finding(
    rule: str,
    path: str,
    message: str,
    *,
    severity: str = "warn",
) -> AuditFinding:
    return AuditFinding(
        rule_id=rule,
        subject=PathSubject(path=path),
        severity=severity,
        message=message,
    )


def _warn(rule: str, path: str, message: str) -> AuditFinding:
    return _finding(rule, path, message)


def test_evidence_scoped_rule_is_declared():
    assert "plan.correspondence-drift" in EVIDENCE_SCOPED_RULES


def test_path_only_entry_does_not_suppress_the_scoped_rule():
    entry = {"rule": "plan.correspondence-drift", "path": "entities/plans/0001-x.md", "reason": "checked"}
    assert not entry_suppresses(
        entry,
        rule="plan.correspondence-drift",
        severity="warn",
        path="entities/plans/0001-x.md",
        task=None,
        message=f"... {_LABELED}",
    )


def test_valid_signature_entry_suppresses():
    entry = {
        "rule": "plan.correspondence-drift",
        "path": "entities/plans/0001-x.md",
        "reason": "input file, not a deliverable",
        "message_contains": _LABELED,
    }
    assert entry_suppresses(
        entry,
        rule="plan.correspondence-drift",
        severity="warn",
        path="entities/plans/0001-x.md",
        task=None,
        message=f"... {_LABELED}",
    )


def test_bare_signature_without_label_does_not_suppress():
    # A hash without the `evidence-signature:` label is not a scoped signature.
    entry = {
        "rule": "plan.correspondence-drift",
        "path": "entities/plans/0001-x.md",
        "reason": "tried to accept with a bare hash",
        "message_contains": _SIG,
    }
    assert not entry_suppresses(
        entry,
        rule="plan.correspondence-drift",
        severity="warn",
        path="entities/plans/0001-x.md",
        task=None,
        message=f"... {_LABELED}",
    )


def test_scoped_entry_without_path_does_not_suppress():
    # Signature present, but no `path`: one signature would blind the rule tree-wide.
    entry = {"rule": "plan.correspondence-drift", "reason": "no path", "message_contains": _LABELED}
    assert not entry_suppresses(
        entry,
        rule="plan.correspondence-drift",
        severity="warn",
        path="entities/plans/0001-x.md",
        task=None,
        message=f"... {_LABELED}",
    )


def test_scoped_entry_with_absolute_path_does_not_suppress():
    entry = {
        "rule": "plan.correspondence-drift",
        "path": "/abs/entities/plans/0001-x.md",
        "reason": "absolute path",
        "message_contains": _LABELED,
    }
    assert not entry_suppresses(
        entry,
        rule="plan.correspondence-drift",
        severity="warn",
        path="/abs/entities/plans/0001-x.md",
        task=None,
        message=f"... {_LABELED}",
    )


def test_stale_signature_entry_does_not_suppress():
    entry = {
        "rule": "plan.correspondence-drift",
        "path": "entities/plans/0001-x.md",
        "reason": "was accepted",
        "message_contains": f"evidence-signature: {SIGNATURE_VERSION}:" + "b" * 64,
    }
    assert not entry_suppresses(
        entry,
        rule="plan.correspondence-drift",
        severity="warn",
        path="entities/plans/0001-x.md",
        task=None,
        message=f"live {_LABELED}",
    )


def test_entry_is_evidence_scoped_requires_the_exact_token_spelling():
    assert not entry_is_evidence_scoped({"message_contains": "evidence-signature:"})  # label, no hash
    assert not entry_is_evidence_scoped({"message_contains": f"{SIGNATURE_VERSION}:short"})  # malformed hash
    assert not entry_is_evidence_scoped({"message_contains": _SIG})  # hash, no label
    assert not entry_is_evidence_scoped({"message_contains": f"evidence-signature:{_SIG}"})  # no space
    assert not entry_is_evidence_scoped({"message_contains": f"evidence-signature:  {_SIG}"})  # two spaces
    assert not entry_is_evidence_scoped({"message_contains": f"evidence-signature:\n{_SIG}"})  # newline
    assert entry_is_evidence_scoped({"message_contains": f"x {_LABELED} y"})  # exact token


def test_other_rules_are_unaffected_by_evidence_scoping(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        "name: f\nprofile: research\nhealth:\n  accepted_validation:\n"
        '    - rule: "code.metadata-gap"\n      path: "x.py"\n      reason: "ok"\n',
        encoding="utf-8",
    )
    kept = filter_accepted_warnings(tmp_path, [_warn("code.metadata-gap", "x.py", "gap")])
    assert kept == []  # a non-scoped rule still suppresses with a path-only entry


def test_legacy_validate_acceptance_removes_only_the_warning(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        "name: f\nprofile: research\nhealth:\n  accepted_validation:\n"
        '    - rule: "code.metadata-gap"\n      path: "x.py"\n      reason: "ok"\n',
        encoding="utf-8",
    )
    warning = _warn("code.metadata-gap", "x.py", "gap")
    error = _finding("code.metadata-gap", "x.py", "gap", severity="error")

    assert filter_accepted_warnings(tmp_path, [warning, error]) == [error]


# filter_accepted_warnings is the `validate` surface (cli.py:152 _with_accepted_warnings_filtered
# delegates to it). These exercise the whole filter for the drift rule, not just the predicates.


def _drift_manifest(root: Path, entry_lines: str) -> None:
    (root / "science.yaml").write_text(
        "name: f\nprofile: research\nhealth:\n  accepted_validation:\n" + entry_lines,
        encoding="utf-8",
    )


def _drift_warn() -> AuditFinding:
    return _warn("plan.correspondence-drift", "entities/plans/0001-x.md", f"under-claims ... {_LABELED}")


def test_filter_keeps_drift_for_a_path_only_entry(tmp_path: Path):
    _drift_manifest(
        tmp_path,
        '    - rule: "plan.correspondence-drift"\n      path: "entities/plans/0001-x.md"\n      reason: "path only"\n',
    )
    assert filter_accepted_warnings(tmp_path, [_drift_warn()]) == [_drift_warn()]


def test_filter_suppresses_drift_for_a_valid_signature_entry(tmp_path: Path):
    _drift_manifest(
        tmp_path,
        '    - rule: "plan.correspondence-drift"\n      path: "entities/plans/0001-x.md"\n'
        f'      reason: "input, not a deliverable"\n      message_contains: "{_LABELED}"\n',
    )
    assert filter_accepted_warnings(tmp_path, [_drift_warn()]) == []


def test_filter_keeps_drift_for_a_stale_signature_entry(tmp_path: Path):
    _drift_manifest(
        tmp_path,
        '    - rule: "plan.correspondence-drift"\n      path: "entities/plans/0001-x.md"\n'
        '      reason: "stale"\n      message_contains: "evidence-signature: '
        + SIGNATURE_VERSION
        + ":"
        + "b" * 64
        + '"\n',
    )
    assert filter_accepted_warnings(tmp_path, [_drift_warn()]) == [_drift_warn()]


def test_a_previous_version_signature_is_not_evidence_scoped():
    """The version exists so a bump INVALIDATES old acceptances rather than silently
    honouring them. A guard that repeated the literal would keep matching v1 forever."""
    stale = "evidence-signature: v1:" + "c" * 64
    assert not entry_is_evidence_scoped({"message_contains": stale})
    assert SIGNATURE_VERSION != "v1", "update this test's stale token when the version bumps"


def _reported_validation_finding(*, severity: str, producer_id: str = "validate"):
    from science_model.audit import AuditFinding, ReportedFinding
    from science_model.audit.subjects import PathSubject

    return ReportedFinding(
        producer_id=producer_id,
        finding=AuditFinding(
            rule_id="paper.status-vocabulary",
            subject=PathSubject(path="entities/papers/0001.md"),
            severity=severity,
            qualifiers={"task": "t001"},
            message="arbitrary text",
            evidence=[],
        ),
    )


@pytest.mark.parametrize(
    ("entry_severity", "finding_severity", "accepted"),
    [
        ("warning", "warn", True),
        ("warning", "error", False),
        (None, "warn", True),
        (None, "error", True),
    ],
)
def test_partition_health_acceptances_uses_current_matcher_wildcards(
    tmp_path, entry_severity, finding_severity, accepted
):
    from science_tool.validate.acceptance import partition_health_acceptances

    severity = f"      severity: {entry_severity}\n" if entry_severity else ""
    (tmp_path / "science.yaml").write_text(
        "name: f\nprofile: research\nhealth:\n  accepted_validation:\n"
        "    - rule: paper.status-vocabulary\n"
        f"{severity}"
        "      reason: known\n",
        encoding="utf-8",
    )
    finding = _reported_validation_finding(severity=finding_severity)
    remaining, accepted_findings = partition_health_acceptances(tmp_path, [finding])
    assert (remaining, accepted_findings) == (([], accepted_findings) if accepted else ([finding], []))
    if accepted:
        assert accepted_findings[0].producer_id == "validate"
        assert accepted_findings[0].reason == "known"


def test_partition_never_offers_non_validation_findings_to_acceptances(tmp_path):
    from science_tool.validate.acceptance import partition_health_acceptances

    (tmp_path / "science.yaml").write_text(
        "name: f\nprofile: research\nhealth:\n  accepted_validation:\n"
        "    - rule: paper.status-vocabulary\n      reason: known\n",
        encoding="utf-8",
    )
    finding = _reported_validation_finding(severity="warn", producer_id="dataset-anomalies")
    assert partition_health_acceptances(tmp_path, [finding]) == ([finding], [])

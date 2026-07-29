from pathlib import Path

import yaml
from science_model.audit import PathSubject, ReportedFinding

from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import validate_finding
from science_tool.validate.acceptance import (
    AcceptedValidationEntry,
    accepted_validation_entries,
    partition_accepted_findings,
)
from science_tool.validate.checks.manifest import RULES


def _finding(*, severity: str = "warn"):
    return RULES["manifest.check"].build(
        subject=PathSubject(path="science.yaml"),
        severity=severity,
        qualifiers={"key": ["profile"]},
        message="missing profile",
    )


def _write_acceptance(
    root: Path,
    *,
    finding_id: str,
    severity_scope: list[str],
    reason: str = "  reviewed  ",
) -> None:
    (root / "science.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "test",
                "health": {
                    "accepted_validation": [
                        {
                            "finding_id": finding_id,
                            "fingerprint_version": 1,
                            "severity_scope": severity_scope,
                            "reason": reason,
                        }
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_health_acceptance_partitions_exact_fingerprint_without_overlap(
    tmp_path: Path,
) -> None:
    finding = _finding()
    registry = build_project_registry(tmp_path)
    finding_id = validate_finding(registry, "validate", finding)
    _write_acceptance(tmp_path, finding_id=finding_id, severity_scope=["warn"])
    matched = ReportedFinding(producer_id="validate", finding=finding)
    other = ReportedFinding(
        producer_id="validate",
        finding=RULES["manifest.check"].build(
            subject=PathSubject(path="science.yaml"),
            severity="warn",
            qualifiers={"key": ["created"]},
            message="missing created",
        ),
    )

    remaining, accepted = partition_accepted_findings(
        accepted_validation_entries(tmp_path),
        [matched, other],
        registry=registry,
    )

    expected_entry = AcceptedValidationEntry.model_validate(
        {
            "finding_id": finding_id,
            "fingerprint_version": 1,
            "severity_scope": ["warn"],
            "reason": "reviewed",
        }
    )
    assert remaining == [other]
    assert [item.finding for item in accepted] == [finding]
    assert accepted[0].acceptance_key == expected_entry.acceptance_key
    assert accepted[0].reason == "reviewed"


def test_warn_scope_does_not_accept_later_error_with_same_fingerprint(
    tmp_path: Path,
) -> None:
    warn = _finding(severity="warn")
    error = _finding(severity="error")
    registry = build_project_registry(tmp_path)
    finding_id = validate_finding(registry, "validate", warn)
    assert validate_finding(registry, "validate", error) == finding_id
    _write_acceptance(tmp_path, finding_id=finding_id, severity_scope=["warn"])
    reported = ReportedFinding(producer_id="validate", finding=error)

    remaining, accepted = partition_accepted_findings(
        accepted_validation_entries(tmp_path),
        [reported],
        registry=registry,
    )

    assert remaining == [reported]
    assert accepted == []


def test_wildcard_migrated_scope_accepts_warn_or_error(
    tmp_path: Path,
) -> None:
    warn = _finding(severity="warn")
    registry = build_project_registry(tmp_path)
    finding_id = validate_finding(registry, "validate", warn)
    _write_acceptance(
        tmp_path,
        finding_id=finding_id,
        severity_scope=["warn", "error"],
    )

    for severity in ("warn", "error"):
        reported = ReportedFinding(
            producer_id="validate",
            finding=_finding(severity=severity),
        )
        remaining, accepted = partition_accepted_findings(
            accepted_validation_entries(tmp_path),
            [reported],
            registry=registry,
        )
        assert remaining == []
        assert [item.finding.severity for item in accepted] == [severity]


def test_non_validation_findings_are_never_accepted(tmp_path: Path) -> None:
    finding = _finding()
    registry = build_project_registry(tmp_path)
    finding_id = validate_finding(registry, "validate", finding)
    _write_acceptance(tmp_path, finding_id=finding_id, severity_scope=["warn"])
    item = ReportedFinding(producer_id="other", finding=finding)

    remaining, accepted = partition_accepted_findings(
        accepted_validation_entries(tmp_path),
        [item],
        registry=registry,
    )

    assert remaining == [item]
    assert accepted == []


def test_partition_uses_the_provided_entry_snapshot(tmp_path: Path) -> None:
    finding = _finding()
    registry = build_project_registry(tmp_path)
    finding_id = validate_finding(registry, "validate", finding)
    entry = {
        "finding_id": finding_id,
        "fingerprint_version": 1,
        "severity_scope": ["warn"],
        "reason": "reviewed",
    }
    reported = ReportedFinding(producer_id="validate", finding=finding)

    remaining, accepted = partition_accepted_findings(
        [entry],
        [reported],
        registry=registry,
    )

    assert remaining == []
    assert [item.finding for item in accepted] == [finding]

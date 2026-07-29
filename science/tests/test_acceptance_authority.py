from __future__ import annotations

from pathlib import Path

import yaml
from science_model.audit import PathSubject

from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import validate_finding
from science_tool.validate.acceptance import filter_accepted_warnings
from science_tool.validate.checks.manifest import RULES


def _finding(*, severity: str = "warn", key: str = "profile"):
    return RULES["manifest.check"].build(
        subject=PathSubject(path="science.yaml"),
        severity=severity,
        qualifiers={"key": [key]},
        message=f"missing {key}",
    )


def _write_entries(root: Path, entries: list[object]) -> None:
    (root / "science.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "test",
                "health": {"accepted_validation": entries},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _current(
    finding_id: str,
    *,
    severity_scope: list[str],
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "fingerprint_version": 1,
        "severity_scope": severity_scope,
        "reason": "reviewed",
    }


def test_validate_filter_suppresses_exact_current_warn_only(
    tmp_path: Path,
) -> None:
    warning = _finding()
    error = _finding(severity="error")
    registry = build_project_registry(tmp_path)
    finding_id = validate_finding(registry, "validate", warning)
    assert validate_finding(registry, "validate", error) == finding_id
    _write_entries(
        tmp_path,
        [_current(finding_id, severity_scope=["warn", "error"])],
    )

    kept = filter_accepted_warnings(
        tmp_path,
        [warning, error],
        registry=registry,
    )

    assert kept == [error]


def test_validate_filter_keeps_different_fingerprint(
    tmp_path: Path,
) -> None:
    accepted = _finding(key="profile")
    other = _finding(key="summary")
    registry = build_project_registry(tmp_path)
    _write_entries(
        tmp_path,
        [
            _current(
                validate_finding(registry, "validate", accepted),
                severity_scope=["warn"],
            )
        ],
    )

    assert filter_accepted_warnings(
        tmp_path,
        [other],
        registry=registry,
    ) == [other]


def test_validate_filter_ignores_legacy_and_invalid_entries(
    tmp_path: Path,
) -> None:
    warning = _finding()
    registry = build_project_registry(tmp_path)
    _write_entries(
        tmp_path,
        [
            {"rule": "manifest.check", "reason": "reviewed"},
            {"finding_id": "invalid", "reason": "reviewed"},
        ],
    )

    assert filter_accepted_warnings(
        tmp_path,
        [warning],
        registry=registry,
    ) == [warning]

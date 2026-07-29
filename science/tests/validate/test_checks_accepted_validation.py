from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.validate.checks.accepted_validation import check_accepted_validation
from science_tool.validate.context import ValidateContext


def _write_entries(root: Path, entries: list[object]) -> None:
    (root / "science.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "f",
                "profile": "research",
                "health": {"accepted_validation": entries},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _run_check(root: Path):
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_accepted_validation(ctx))


def _current_entry() -> dict[str, object]:
    return {
        "finding_id": "a" * 64,
        "fingerprint_version": 1,
        "severity_scope": ["warn"],
        "reason": "reviewed",
    }


def test_legacy_entry_emits_migration_error(tmp_path: Path) -> None:
    _write_entries(
        tmp_path,
        [{"rule": "manifest.check", "severity": "warning", "reason": "reviewed"}],
    )

    findings = _run_check(tmp_path)

    assert [item.rule_id for item in findings] == ["accepted-validation.legacy-shape"]
    assert findings[0].severity == "error"
    assert findings[0].subject.type == "identifier"
    assert "migrate-acceptances" in findings[0].message


@pytest.mark.parametrize(
    "raw",
    [
        "scalar",
        {"reason": "missing identity"},
        {
            "finding_id": "a" * 64,
            "fingerprint_version": 2,
            "severity_scope": ["warn"],
            "reason": "reviewed",
        },
    ],
)
def test_invalid_entry_emits_invalid_not_legacy(tmp_path: Path, raw: object) -> None:
    _write_entries(tmp_path, [raw])

    findings = _run_check(tmp_path)

    assert [item.rule_id for item in findings] == ["accepted-validation.invalid-entry"]
    assert findings[0].subject.type == "identifier"


def test_valid_current_entry_emits_no_hygiene_finding(tmp_path: Path) -> None:
    _write_entries(tmp_path, [_current_entry()])

    assert _run_check(tmp_path) == []


def test_duplicate_identical_raw_entries_group_into_one_finding(
    tmp_path: Path,
) -> None:
    raw = {"reason": "missing identity"}
    _write_entries(tmp_path, [raw, raw])

    findings = _run_check(tmp_path)

    assert len(findings) == 1
    assert findings[0].rule_id == "accepted-validation.invalid-entry"

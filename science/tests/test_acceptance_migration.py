from datetime import date

import pytest
from science_model.audit import PathSubject

from science_tool.findings.acceptance_migration import (
    MigrationRow,
    classify_migration,
)
from science_tool.validate.acceptance import (
    InvalidAcceptance,
    classify_acceptance_entry,
    entry_matches,
    legacy_validation_fields,
)
from science_tool.validate.checks.manifest import RULES


def _finding(
    message: str, *, key: list[str] | None = None, severity: str = "warn"
):
    return RULES["manifest.check"].build(
        subject=PathSubject(path="science.yaml"),
        severity=severity,
        qualifiers={"key": key or ["profile"]},
        message=message,
    )


def _legacy(**overrides):
    return {
        "rule": "manifest.check",
        "severity": "warning",
        "path": "science.yaml",
        "message_contains": ["missing profile"],
        "reason": "reviewed",
        **overrides,
    }


def _current(finding_id: str = "c" * 64, **overrides):
    return {
        "finding_id": finding_id,
        "fingerprint_version": 1,
        "severity_scope": ["warn"],
        "reason": "already reviewed",
        "accepted_on": "2026-07-01",
        **overrides,
    }


def test_unique_match_migrates_and_preserves_warning_scope():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    result = classify_migration([_legacy()], [row], {"validate.manifest": "ok"})
    assert result.can_apply
    assert result.needs_write
    assert result.entries[0].verdict == "migrated"
    assert result.entries[0].replacement.severity_scope == ("warn",)


def test_wildcard_severity_preserves_warn_and_error_scope():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    entry = _legacy()
    del entry["severity"]
    result = classify_migration([entry], [row], {"validate.manifest": "ok"})
    assert result.entries[0].replacement.severity_scope == ("warn", "error")


def test_current_entry_is_idempotent_without_producer_evidence():
    result = classify_migration(
        [_current()],
        [],
        {"validate.references": "unwired"},
    )
    assert result.indeterminate_producers == ()
    assert result.can_apply
    assert not result.needs_write
    assert result.entries[0].verdict == "already-current"
    assert result.entries[0].replacement.accepted_on == date(2026, 7, 1)
    assert result.output_entries == (result.entries[0].replacement,)


@pytest.mark.parametrize(
    "raw",
    [
        _current(fingerprint_version=2),
        "scalar",
    ],
)
def test_invalid_entry_is_not_stale_and_preserves_classifier_error(raw):
    classified = classify_acceptance_entry(raw)
    assert isinstance(classified, InvalidAcceptance)

    result = classify_migration([raw], [], {})

    assert not result.can_apply
    assert result.entries[0].verdict == "invalid"
    assert result.entries[0].replacement is None
    assert result.entries[0].detail == classified.error


def test_mixed_current_and_legacy_entries_preserve_order():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    result = classify_migration(
        [_current(), _legacy()],
        [row],
        {"validate.manifest": "ok"},
    )
    assert [item.verdict for item in result.entries] == [
        "already-current",
        "migrated",
    ]
    assert [entry.finding_id for entry in result.output_entries] == [
        "c" * 64,
        "a" * 64,
    ]
    assert result.can_apply
    assert result.needs_write


def test_zero_and_multiple_matches_are_stale_and_ambiguous():
    rows = [
        MigrationRow(_finding("missing profile", key=["profile"]), "a" * 64),
        MigrationRow(_finding("missing profile", key=["name"]), "b" * 64),
    ]
    assert classify_migration(
        [_legacy(message_contains=["absent"])], rows, {"validate.manifest": "ok"}
    ).entries[0].verdict == "stale"
    assert classify_migration(
        [_legacy(message_contains=["missing"])], rows, {"validate.manifest": "ok"}
    ).entries[0].verdict == "ambiguous"


@pytest.mark.parametrize("message_contains", [7, ["valid", 7]])
def test_malformed_legacy_message_contains_is_stale(message_contains):
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    result = classify_migration(
        [_legacy(message_contains=message_contains)],
        [row],
        {"validate.manifest": "ok"},
    )
    assert result.entries[0].verdict == "stale"


def test_duplicate_finding_id_rejects_even_different_scopes():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    wildcard = _legacy()
    del wildcard["severity"]
    result = classify_migration(
        [_legacy(), wildcard], [row], {"validate.manifest": "ok"}
    )
    assert [item.verdict for item in result.entries] == ["duplicate", "duplicate"]
    assert not result.can_apply


def test_duplicate_detection_spans_current_and_migrated_entries():
    row = MigrationRow(_finding("missing profile"), "a" * 64)
    result = classify_migration(
        [_current("a" * 64), _legacy()],
        [row],
        {"validate.manifest": "ok"},
    )
    assert [item.verdict for item in result.entries] == ["duplicate", "duplicate"]
    assert not result.can_apply


def test_any_unwired_check_is_indeterminate_before_matching():
    result = classify_migration(
        [_legacy()],
        [],
        {"validate.manifest": "ok", "validate.references": "unwired"},
    )
    assert result.indeterminate_producers == ("validate.references",)
    assert result.entries[0].verdict == "indeterminate"
    assert "validate.references" in result.entries[0].detail


def test_migration_preserves_the_set_of_suppressed_findings():
    legacy = _legacy()
    del legacy["severity"]
    migrated = classify_migration(
        [legacy],
        [MigrationRow(_finding("missing profile"), "a" * 64)],
        {"validate.manifest": "ok"},
    ).output_entries[0]
    rows = [
        MigrationRow(_finding("missing profile", severity="warn"), "a" * 64),
        MigrationRow(_finding("missing profile", severity="error"), "a" * 64),
    ]

    old_suppressed = {
        (row.finding_id, row.finding.severity)
        for row in rows
        if entry_matches(legacy, **legacy_validation_fields(row.finding))
    }
    migrated_suppressed = {
        (row.finding_id, row.finding.severity)
        for row in rows
        if row.finding_id == migrated.finding_id
        and row.finding.severity in migrated.severity_scope
    }

    assert migrated_suppressed == old_suppressed

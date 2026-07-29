from datetime import date

import pytest
import yaml
from pydantic import ValidationError

from science_tool.validate.acceptance import (
    AcceptedValidationEntry,
    CurrentAcceptance,
    InvalidAcceptance,
    LegacyAcceptance,
    classify_acceptance_entry,
    raw_acceptance_digest,
)


BASE = {
    "finding_id": "a" * 64,
    "fingerprint_version": 1,
    "severity_scope": ["warn"],
    "reason": "reviewed",
}


@pytest.mark.parametrize(
    ("raw_scope", "expected"),
    [
        (["warn"], ("warn",)),
        (["error", "warn"], ("warn", "error")),
        (["warn", "warn"], ("warn",)),
        (["warn", "error"], ("warn", "error")),
    ],
)
def test_severity_scope_is_a_canonical_nonempty_set(raw_scope, expected):
    entry = AcceptedValidationEntry.model_validate({**BASE, "severity_scope": raw_scope})
    assert entry.severity_scope == expected
    assert entry.model_dump(mode="json")["severity_scope"] == list(expected)


@pytest.mark.parametrize("bad", [[], ["info"], "warn", [1], None])
def test_severity_scope_refuses_every_other_shape(bad):
    with pytest.raises(ValidationError):
        AcceptedValidationEntry.model_validate({**BASE, "severity_scope": bad})


def test_current_shape_is_selected_by_presence_of_finding_id():
    classified = classify_acceptance_entry(BASE)
    assert isinstance(classified, CurrentAcceptance)
    assert classified.entry.finding_id == "a" * 64


@pytest.mark.parametrize(
    "raw",
    [
        {**BASE, "fingerprint_version": 2},
        {**BASE, "severity_scope": ["info"]},
        {**BASE, "reason": " "},
        {**BASE, "typo": True},
    ],
)
def test_invalid_current_shape_never_falls_back_to_legacy(raw):
    classified = classify_acceptance_entry(raw)
    assert isinstance(classified, InvalidAcceptance)
    assert "legacy" not in classified.error.lower()


def test_old_shape_is_positive_legacy_classification():
    classified = classify_acceptance_entry(
        {"rule": "manifest.check", "severity": "warning", "reason": "reviewed"}
    )
    assert isinstance(classified, LegacyAcceptance)


@pytest.mark.parametrize("raw", ["scalar", 42, None, {"reason": "missing identity"}])
def test_every_other_yaml_entry_is_invalid_with_a_stable_subject_digest(raw):
    classified = classify_acceptance_entry(raw)
    assert isinstance(classified, InvalidAcceptance)
    assert classified.raw_digest == raw_acceptance_digest(raw)
    assert len(classified.raw_digest) == 32


def test_optional_accepted_on_is_an_iso_date():
    entry = AcceptedValidationEntry.model_validate(
        {**BASE, "accepted_on": "2026-07-29"}
    )
    assert entry.accepted_on == date(2026, 7, 29)


def test_current_entry_with_a_yaml_date_is_classified():
    classified = classify_acceptance_entry(
        {**BASE, "accepted_on": date(2026, 7, 29)}
    )
    assert isinstance(classified, CurrentAcceptance)
    assert classified.entry.accepted_on == date(2026, 7, 29)


@pytest.mark.parametrize(
    "raw",
    [
        yaml.safe_load("!!set {broken: null}"),
        yaml.safe_load("!!binary aGVsbG8="),
        yaml.safe_load("1: non-string-key"),
    ],
)
def test_every_yaml_value_has_a_digest_and_invalid_classification(raw):
    classified = classify_acceptance_entry(raw)
    assert isinstance(classified, InvalidAcceptance)
    assert classified.raw_digest == raw_acceptance_digest(raw)
    assert len(classified.raw_digest) == 32


@pytest.mark.parametrize("version", [True, 1.0])
def test_fingerprint_version_refuses_non_integer_one(version):
    with pytest.raises(ValidationError):
        AcceptedValidationEntry.model_validate({**BASE, "fingerprint_version": version})


def test_raw_acceptance_digest_has_a_literal_oracle():
    assert raw_acceptance_digest("scalar") == "1cf2462dbf783967e4408e886e4569a7"

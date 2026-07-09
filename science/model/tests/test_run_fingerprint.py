from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.run_fingerprint import ComponentProvenance, FingerprintComponent

WHEN = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


def test_captured_requires_non_empty_value():
    ok = FingerprintComponent(value="abc123", provenance=ComponentProvenance.CAPTURED)
    assert ok.value == "abc123"
    for bad in ("", "   ", None):
        with pytest.raises(ValidationError):
            FingerprintComponent(value=bad, provenance=ComponentProvenance.CAPTURED)


def test_unknown_forbids_value_and_attestation():
    ok = FingerprintComponent(provenance=ComponentProvenance.UNKNOWN)
    assert ok.value is None
    with pytest.raises(ValidationError):
        FingerprintComponent(value="x", provenance=ComponentProvenance.UNKNOWN)
    with pytest.raises(ValidationError):
        FingerprintComponent(provenance=ComponentProvenance.UNKNOWN, attested_by="bob")


def test_attested_requires_attested_by_and_at():
    ok = FingerprintComponent(
        value="sha256:1", provenance=ComponentProvenance.ATTESTED,
        attested_by="nextflow", attested_at=WHEN,
    )
    assert ok.attested_by == "nextflow"
    with pytest.raises(ValidationError):
        FingerprintComponent(value="sha256:1", provenance=ComponentProvenance.ATTESTED, attested_by="nextflow")
    with pytest.raises(ValidationError):
        FingerprintComponent(value="sha256:1", provenance=ComponentProvenance.ATTESTED, attested_at=WHEN)


def test_captured_forbids_attestation_fields():
    with pytest.raises(ValidationError):
        FingerprintComponent(
            value="abc", provenance=ComponentProvenance.CAPTURED,
            attested_by="bob", attested_at=WHEN,
        )


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        FingerprintComponent(value="a", provenance=ComponentProvenance.CAPTURED, bogus=1)

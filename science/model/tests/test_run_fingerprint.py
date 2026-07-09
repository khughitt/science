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


from science_model.run_fingerprint import (
    ArtifactLocality, CaptureOrigin, ExecutorKind, SeedPolicy,
)


def test_seed_policy_seeded_requires_seeds():
    ok = SeedPolicy(kind="seeded", seeds={"numpy": 7})
    assert ok.seeds == {"numpy": 7}
    with pytest.raises(ValidationError):
        SeedPolicy(kind="seeded")


def test_seed_policy_stochastic_unseeded_requires_rationale():
    ok = SeedPolicy(kind="stochastic-unseeded", rationale="vendor binary exposes no seed")
    assert ok.rationale
    with pytest.raises(ValidationError):
        SeedPolicy(kind="stochastic-unseeded")


def test_seed_policy_deterministic_takes_neither():
    ok = SeedPolicy(kind="deterministic")
    assert ok.seeds is None and ok.rationale is None
    with pytest.raises(ValidationError):
        SeedPolicy(kind="deterministic", seeds={"numpy": 1})


def test_capture_origin_requires_run_ref_prefix():
    ok = CaptureOrigin(
        origin_project="project:pan-disease", origin_run_ref="workflow-run:r1",
        captured_at=WHEN, captured_by="science", capture_policy="science-run-fingerprint/v1",
    )
    assert ok.origin_run_ref == "workflow-run:r1"
    with pytest.raises(ValidationError):
        CaptureOrigin(
            origin_project="project:pan-disease", origin_run_ref="r1",
            captured_at=WHEN, captured_by="science", capture_policy="science-run-fingerprint/v1",
        )


def test_enum_values():
    assert ExecutorKind.LOCAL == "local"
    assert ArtifactLocality.SCIENCE_MANAGED == "science-managed"

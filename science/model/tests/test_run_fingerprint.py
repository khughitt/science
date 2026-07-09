from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.run_fingerprint import (
    FINGERPRINT_POLICY_V1, ArtifactLocality, CaptureOrigin, ComponentProvenance,
    ExecutorKind, FingerprintComponent, RunFingerprint, SeedPolicy,
)

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


def _cap(v: str) -> FingerprintComponent:
    return FingerprintComponent(value=v, provenance=ComponentProvenance.CAPTURED)


def _fp(**over) -> RunFingerprint:
    base = dict(
        fingerprint_policy=FINGERPRINT_POLICY_V1,
        executor=ExecutorKind.LOCAL,
        input_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
        output_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
        code_sha=_cap("a" * 40),
        code_dirty=_cap("false"),
        environment_digest=_cap("sha256:env"),
        parameters_digest=_cap("sha256:params"),
        input_manifest_digest=_cap("sha256:in"),
        output_manifest_digest=_cap("sha256:out"),
        seed_policy=SeedPolicy(kind="seeded", seeds={"numpy": 7}),
    )
    base.update(over)
    return RunFingerprint(**base)


def test_code_dirty_must_be_true_or_false_token():
    assert _fp().code_dirty.value == "false"
    with pytest.raises(ValidationError):
        _fp(code_dirty=_cap("False"))
    with pytest.raises(ValidationError):
        _fp(code_dirty=_cap("yes"))


def test_code_dirty_may_be_unknown():
    fp = _fp(executor=ExecutorKind.EXTERNAL,
             code_dirty=FingerprintComponent(provenance=ComponentProvenance.UNKNOWN))
    assert fp.code_dirty.value is None


def test_commons_requires_capture_origin():
    with pytest.raises(ValidationError):
        _fp(executor=ExecutorKind.COMMONS)
    ok = _fp(
        executor=ExecutorKind.COMMONS,
        capture_origin=CaptureOrigin(
            origin_project="project:pan-disease", origin_run_ref="workflow-run:r1",
            captured_at=WHEN, captured_by="science", capture_policy=FINGERPRINT_POLICY_V1,
        ),
    )
    assert ok.capture_origin is not None


def test_non_commons_forbids_capture_origin():
    with pytest.raises(ValidationError):
        _fp(capture_origin=CaptureOrigin(
            origin_project="p", origin_run_ref="workflow-run:r1", captured_at=WHEN,
            captured_by="science", capture_policy=FINGERPRINT_POLICY_V1,
        ))


def _minimal_workflow_run(id_: str) -> dict:
    return dict(
        id=id_, kind="workflow-run", title=id_, project="demo",
        ontology_terms=[], related=[], source_refs=[],
        content_preview="", file_path=f"{id_}.md",
    )


def test_workflow_run_entity_carries_optional_fingerprint():
    from science_model.entities import WorkflowRunEntity

    e = WorkflowRunEntity(**_minimal_workflow_run("workflow-run:r1"))
    assert e.fingerprint is None
    e2 = WorkflowRunEntity(**_minimal_workflow_run("workflow-run:r2"), fingerprint=_fp())
    assert e2.fingerprint.code_sha.value == "a" * 40


def _minimal_evidence_line(id_: str = "evidence-line:e1", **overrides) -> dict:
    base = {
        "id": id_,
        "canonical_id": id_,
        "kind": "evidence-line",
        "title": "E1 supports H1",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": f"doc/evidence-lines/{id_}.md",
        "stance": "supports",
        "target": "hypothesis:h1",
    }
    base.update(overrides)
    return base


def test_evidence_line_run_refs_require_workflow_run_prefix():
    from science_model.entities import EvidenceLineEntity

    ok = EvidenceLineEntity(
        **_minimal_evidence_line("evidence-line:e1", run_refs=["workflow-run:r1"])
    )
    assert ok.run_refs == ["workflow-run:r1"]

    with pytest.raises(ValidationError):
        EvidenceLineEntity(
            **_minimal_evidence_line("evidence-line:e2", run_refs=["r1"])
        )


def test_evidence_line_run_refs_default_empty():
    from science_model.entities import EvidenceLineEntity

    e = EvidenceLineEntity(**_minimal_evidence_line("evidence-line:e3"))
    assert e.run_refs == []

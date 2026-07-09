from science_model.run_fingerprint import ArtifactLocality, ExecutorKind, RunFingerprint

from science_tool.run_fingerprint_policy import (
    COMPONENT_FIELDS, LOCALITY_OBLIGATION, OBLIGATIONS, Obligation, obligation_for,
)


def test_every_executor_declares_every_component():
    """The import-time reconciliation gate's property, asserted explicitly."""
    for executor in ExecutorKind:
        assert set(OBLIGATIONS[executor]) == set(COMPONENT_FIELDS), executor


def test_component_fields_match_the_model():
    expected = set()
    for name, field in RunFingerprint.model_fields.items():
        ann = str(field.annotation)
        if "FingerprintComponent" in ann:
            expected.add(name)
    assert set(COMPONENT_FIELDS) == expected


def test_local_must_capture_code_and_env_and_forbids_container():
    assert OBLIGATIONS[ExecutorKind.LOCAL]["code_sha"] is Obligation.MUST_CAPTURED
    assert OBLIGATIONS[ExecutorKind.LOCAL]["environment_digest"] is Obligation.MUST_CAPTURED
    assert OBLIGATIONS[ExecutorKind.LOCAL]["container_digest"] is Obligation.NOT_APPLICABLE


def test_external_may_attest_env_but_still_must_capture_code_sha():
    assert OBLIGATIONS[ExecutorKind.EXTERNAL]["code_sha"] is Obligation.MUST_CAPTURED
    assert OBLIGATIONS[ExecutorKind.EXTERNAL]["environment_digest"] is Obligation.MAY_ATTESTED
    assert OBLIGATIONS[ExecutorKind.EXTERNAL]["code_dirty"] is Obligation.MAY_UNKNOWN


def test_manifest_obligation_resolves_by_its_own_locality(local_fingerprint):
    fp = local_fingerprint(
        input_artifact_locality=ArtifactLocality.EXTERNAL,
        output_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
    )
    assert obligation_for(fp.executor, "input_manifest_digest", fp) is Obligation.MAY_ATTESTED
    assert obligation_for(fp.executor, "output_manifest_digest", fp) is Obligation.MUST_CAPTURED


def test_by_locality_never_leaks_to_callers(local_fingerprint):
    fp = local_fingerprint()
    for component in COMPONENT_FIELDS:
        assert obligation_for(fp.executor, component, fp) is not Obligation.BY_LOCALITY


def test_locality_obligation_table():
    assert LOCALITY_OBLIGATION[ArtifactLocality.SCIENCE_MANAGED] is Obligation.MUST_CAPTURED
    assert LOCALITY_OBLIGATION[ArtifactLocality.EXTERNAL] is Obligation.MAY_ATTESTED

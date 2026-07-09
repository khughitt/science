from datetime import UTC, datetime

from science_model.run_fingerprint import (
    ArtifactLocality,
    ComponentProvenance,
    ExecutorKind,
    FingerprintComponent,
    RunFingerprint,
)

from science_tool.run_fingerprint_policy import (
    COMPONENT_FIELDS, LOCALITY_OBLIGATION, OBLIGATIONS, Obligation, evaluate_fingerprint, obligation_for,
)

WHEN = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
UNKNOWN = FingerprintComponent(provenance=ComponentProvenance.UNKNOWN)


def _attested(v: str) -> FingerprintComponent:
    return FingerprintComponent(
        value=v, provenance=ComponentProvenance.ATTESTED,
        attested_by="nextflow", attested_at=WHEN,
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


def test_clean_local_fingerprint_has_no_findings(local_fingerprint):
    assert evaluate_fingerprint(local_fingerprint()) == []


def test_attested_where_capture_required_is_authored_capturable(local_fingerprint):
    fp = local_fingerprint(environment_digest=_attested("sha256:env"))
    rules = [f.rule for f in evaluate_fingerprint(fp)]
    assert rules == ["run.fingerprint-authored-capturable"]
    assert "environment_digest" in evaluate_fingerprint(fp)[0].message


def test_unknown_where_capture_required_is_incomplete(local_fingerprint):
    fp = local_fingerprint(parameters_digest=UNKNOWN)
    assert [f.rule for f in evaluate_fingerprint(fp)] == ["run.fingerprint-incomplete"]


def test_container_digest_present_on_local_is_incomplete(local_fingerprint):
    fp = local_fingerprint(container_digest=_attested("sha256:img"))
    findings = evaluate_fingerprint(fp)
    assert [f.rule for f in findings] == ["run.fingerprint-incomplete"]
    assert "not applicable" in findings[0].message


def test_external_may_attest_environment_digest(local_fingerprint):
    fp = local_fingerprint(
        executor=ExecutorKind.EXTERNAL,
        environment_digest=_attested("sha256:env"),
        container_digest=_attested("sha256:img"),
        parameters_digest=_attested("sha256:params"),
        code_dirty=UNKNOWN,
    )
    assert evaluate_fingerprint(fp) == []


def test_external_still_cannot_attest_code_sha(local_fingerprint):
    fp = local_fingerprint(
        executor=ExecutorKind.EXTERNAL, code_sha=_attested("b" * 40),
        environment_digest=_attested("sha256:env"),
        container_digest=_attested("sha256:img"),
        parameters_digest=_attested("sha256:params"), code_dirty=UNKNOWN,
    )
    assert [f.rule for f in evaluate_fingerprint(fp)] == ["run.fingerprint-authored-capturable"]


def test_external_input_locality_allows_attested_manifest(local_fingerprint):
    fp = local_fingerprint(
        executor=ExecutorKind.EXTERNAL,
        input_artifact_locality=ArtifactLocality.EXTERNAL,
        input_manifest_digest=_attested("sha256:in"),
        environment_digest=_attested("sha256:env"),
        container_digest=_attested("sha256:img"),
        parameters_digest=_attested("sha256:params"), code_dirty=UNKNOWN,
    )
    assert evaluate_fingerprint(fp) == []


def test_findings_are_deterministically_ordered(local_fingerprint):
    fp = local_fingerprint(environment_digest=UNKNOWN, parameters_digest=UNKNOWN)
    messages = [f.message for f in evaluate_fingerprint(fp)]
    assert messages == sorted(messages)


def test_container_digest_is_may_unknown_for_external_and_commons():
    assert OBLIGATIONS[ExecutorKind.EXTERNAL]["container_digest"] is Obligation.MAY_UNKNOWN
    assert OBLIGATIONS[ExecutorKind.COMMONS]["container_digest"] is Obligation.MAY_UNKNOWN
    assert OBLIGATIONS[ExecutorKind.LOCAL]["container_digest"] is Obligation.NOT_APPLICABLE


def test_external_container_digest_unknown_yields_no_findings(local_fingerprint):
    """A non-local run that legitimately used no container states it explicitly:
    a present component with `provenance: unknown`, not absence."""
    fp = local_fingerprint(
        executor=ExecutorKind.EXTERNAL,
        environment_digest=_attested("sha256:env"),
        container_digest=UNKNOWN,
        parameters_digest=_attested("sha256:params"),
        code_dirty=UNKNOWN,
    )
    assert evaluate_fingerprint(fp) == []


def test_external_container_digest_absent_is_still_incomplete(local_fingerprint):
    fp = local_fingerprint(
        executor=ExecutorKind.EXTERNAL,
        environment_digest=_attested("sha256:env"),
        container_digest=None,
        parameters_digest=_attested("sha256:params"),
        code_dirty=UNKNOWN,
    )
    findings = evaluate_fingerprint(fp)
    assert [f.rule for f in findings] == ["run.fingerprint-incomplete"]
    assert "container_digest" in findings[0].message

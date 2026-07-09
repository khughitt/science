import pytest

from science_model.run_fingerprint import ArtifactLocality, ComponentProvenance, ExecutorKind
from science_tool.datasets_register import FingerprintCaptureError, capture_fingerprint


def _kwargs(**over):
    base = dict(
        executor=ExecutorKind.LOCAL,
        input_locality=ArtifactLocality.SCIENCE_MANAGED,
        output_locality=ArtifactLocality.SCIENCE_MANAGED,
        code_sha="a" * 40,
        code_dirty=False,
        environment_digest="sha256:env",
        parameters_digest="sha256:params",
        input_manifest_digest="sha256:in",
        output_manifest_digest="sha256:out",
    )
    base.update(over)
    return base


def test_capture_marks_every_component_captured():
    run_fm = {"fingerprint": {"seed_policy": {"kind": "deterministic"}}}
    fp = capture_fingerprint(run_fm=run_fm, **_kwargs())
    for name in ("code_sha", "code_dirty", "environment_digest",
                 "parameters_digest", "input_manifest_digest", "output_manifest_digest"):
        assert getattr(fp, name).provenance is ComponentProvenance.CAPTURED
    assert fp.code_dirty.value == "false"
    assert fp.container_digest is None
    assert fp.fingerprint_policy == "science-run-fingerprint/v1"


def test_capture_encodes_dirty_as_lowercase_token():
    run_fm = {"fingerprint": {"seed_policy": {"kind": "deterministic"}}}
    fp = capture_fingerprint(run_fm=run_fm, **_kwargs(code_dirty=True))
    assert fp.code_dirty.value == "true"


def test_hand_authored_capturable_component_is_rejected():
    run_fm = {"fingerprint": {"code_sha": {"value": "dead" * 10, "provenance": "captured"}}}
    with pytest.raises(FingerprintCaptureError, match="code_sha"):
        capture_fingerprint(run_fm=run_fm, **_kwargs())


def test_hand_authored_seed_policy_is_preserved():
    run_fm = {"fingerprint": {"seed_policy": {"kind": "seeded", "seeds": {"numpy": 7}}}}
    fp = capture_fingerprint(run_fm=run_fm, **_kwargs())
    assert fp.seed_policy.kind == "seeded" and fp.seed_policy.seeds == {"numpy": 7}


def test_missing_seed_policy_defaults_to_stochastic_unseeded_is_rejected():
    """Seed policy is authored, never invented. Absent => fail loud."""
    with pytest.raises(FingerprintCaptureError, match="seed_policy"):
        capture_fingerprint(run_fm={"fingerprint": {}}, **_kwargs())


def test_captured_fingerprint_evaluates_clean():
    from science_tool.run_fingerprint_policy import evaluate_fingerprint

    run_fm = {"fingerprint": {"seed_policy": {"kind": "deterministic"}}}
    assert evaluate_fingerprint(capture_fingerprint(run_fm=run_fm, **_kwargs())) == []

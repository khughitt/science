import hashlib

from science_tool.validate.checks.workflow_runs import check_run_fingerprint_obligations
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(tmp_path) -> ValidateContext:
    (tmp_path / "science.yaml").write_text("name: t\nprofile: software\n", encoding="utf-8")
    (tmp_path / "entities" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    return ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)


def _write_run(tmp_path, name: str, fingerprint_yaml: str) -> None:
    (tmp_path / "entities" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "entities" / "workflow-runs" / f"{name}.md").write_text(
        f"---\nid: workflow-run:{name}\nkind: workflow-run\ntitle: {name}\n{fingerprint_yaml}---\n",
        encoding="utf-8",
    )


CLEAN = """fingerprint:
  fingerprint_policy: science-run-fingerprint/v1
  executor: local
  input_artifact_locality: science-managed
  output_artifact_locality: science-managed
  code_sha: {value: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, provenance: captured}
  code_dirty: {value: "false", provenance: captured}
  environment_digest: {value: "sha256:env", provenance: captured}
  parameters_digest: {value: "sha256:params", provenance: captured}
  input_manifest_digest: {value: "sha256:in", provenance: captured}
  output_manifest_digest: {value: "sha256:out", provenance: captured}
  seed_policy: {kind: deterministic}
"""


def test_run_without_fingerprint_emits_nothing(tmp_path):
    _write_run(tmp_path, "r1", "")
    assert list(check_run_fingerprint_obligations(_ctx(tmp_path))) == []


def test_clean_fingerprint_emits_nothing(tmp_path):
    _write_run(tmp_path, "r1", CLEAN)
    assert list(check_run_fingerprint_obligations(_ctx(tmp_path))) == []


def test_attested_capturable_component_is_error(tmp_path):
    bad = CLEAN.replace(
        '  environment_digest: {value: "sha256:env", provenance: captured}',
        '  environment_digest: {value: "sha256:env", provenance: attested, '
        'attested_by: bob, attested_at: "2026-07-09T12:00:00Z"}',
    )
    _write_run(tmp_path, "r1", bad)
    results = list(check_run_fingerprint_obligations(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["run.fingerprint-authored-capturable"]
    assert results[0].severity is Severity.ERROR


def test_unknown_capturable_component_is_warn(tmp_path):
    bad = CLEAN.replace(
        '  parameters_digest: {value: "sha256:params", provenance: captured}',
        "  parameters_digest: {provenance: unknown}",
    )
    _write_run(tmp_path, "r1", bad)
    results = list(check_run_fingerprint_obligations(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["run.fingerprint-incomplete"]
    assert results[0].severity is Severity.WARN


def test_malformed_fingerprint_is_error(tmp_path):
    bad = CLEAN.replace(
        '  code_dirty: {value: "false", provenance: captured}',
        '  code_dirty: {value: "", provenance: captured}',
    )
    assert bad != CLEAN, "replace() found no match against CLEAN; fixture text has drifted"
    _write_run(tmp_path, "r1", bad)
    results = list(check_run_fingerprint_obligations(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["run.fingerprint-malformed"]
    assert results[0].severity is Severity.ERROR


def test_commons_origin_digest_mismatch_is_error(tmp_path):
    src = tmp_path / "imported.md"
    src.write_text("real content", encoding="utf-8")
    commons = CLEAN.replace("  executor: local", "  executor: commons") + (
        "  container_digest: {provenance: unknown}\n"
        "  capture_origin:\n"
        "    origin_project: project:pan-disease\n"
        "    origin_run_ref: workflow-run:r0\n"
        "    captured_at: '2026-07-09T12:00:00Z'\n"
        "    captured_by: science\n"
        "    capture_policy: science-run-fingerprint/v1\n"
        "    source_ref: imported.md\n"
        "    source_digest: deadbeef\n"
    )
    _write_run(tmp_path, "r1", commons)
    results = list(check_run_fingerprint_obligations(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["run.fingerprint-origin-unverified"]
    assert results[0].severity is Severity.ERROR


def test_commons_origin_matching_digest_passes(tmp_path):
    src = tmp_path / "imported.md"
    src.write_text("real content", encoding="utf-8")
    digest = hashlib.sha256(b"real content").hexdigest()
    commons = CLEAN.replace("  executor: local", "  executor: commons") + (
        "  container_digest: {provenance: unknown}\n"
        "  capture_origin:\n"
        "    origin_project: project:pan-disease\n"
        "    origin_run_ref: workflow-run:r0\n"
        "    captured_at: '2026-07-09T12:00:00Z'\n"
        "    captured_by: science\n"
        "    capture_policy: science-run-fingerprint/v1\n"
        "    source_ref: imported.md\n"
        f"    source_digest: {digest}\n"
    )
    _write_run(tmp_path, "r1", commons)
    assert list(check_run_fingerprint_obligations(_ctx(tmp_path))) == []

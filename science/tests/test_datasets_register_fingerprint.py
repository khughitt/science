import subprocess
from pathlib import Path

import pytest
import yaml

from science_model.run_fingerprint import ArtifactLocality, ComponentProvenance, ExecutorKind
from science_tool.datasets_register import (
    FingerprintCaptureError,
    capture_fingerprint,
    persist_run_fingerprint,
)


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


def test_invalid_seed_policy_surfaces_as_capture_error():
    """An authored seed_policy that fails RunFingerprint/SeedPolicy validation must
    surface as FingerprintCaptureError, not a bare pydantic ValidationError — the CLI
    only catches the former."""
    run_fm = {"fingerprint": {"seed_policy": {"kind": "not-a-real-kind"}}}
    with pytest.raises(FingerprintCaptureError, match="seed_policy"):
        capture_fingerprint(run_fm=run_fm, **_kwargs())


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "uv.lock").write_text("lock", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("alpha: 1\n", encoding="utf-8")
    runs = tmp_path / "entities" / "workflow-runs"
    runs.mkdir(parents=True)
    (runs / "r1.md").write_text(
        "---\n"
        "id: workflow-run:r1\nkind: workflow-run\ntitle: R1\n"
        "config_snapshot: config.yaml\n"
        "fingerprint:\n"
        "  executor: local\n"
        "  input_artifact_locality: science-managed\n"
        "  output_artifact_locality: science-managed\n"
        "  seed_policy: {kind: deterministic}\n"
        "---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path, check=True,
    )
    return tmp_path


def test_persist_writes_captured_components_into_frontmatter(git_project):
    fp = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert fp.code_sha.provenance == "captured" and len(fp.code_sha.value) == 40
    assert fp.code_dirty.value == "false"

    written = yaml.safe_load(
        (git_project / "entities" / "workflow-runs" / "r1.md").read_text().split("---")[1]
    )
    assert written["fingerprint"]["code_sha"]["provenance"] == "captured"
    assert written["fingerprint"]["seed_policy"]["kind"] == "deterministic"


def test_dirty_worktree_is_captured_as_true(git_project):
    (git_project / "config.yaml").write_text("alpha: 2\n", encoding="utf-8")
    assert persist_run_fingerprint(git_project, "workflow-run:r1").code_dirty.value == "true"


def test_persisted_fingerprint_evaluates_clean(git_project):
    from science_tool.run_fingerprint_policy import evaluate_fingerprint

    assert evaluate_fingerprint(persist_run_fingerprint(git_project, "workflow-run:r1")) == []


def test_missing_lockfile_fails_loud(git_project):
    (git_project / "uv.lock").unlink()
    with pytest.raises(FingerprintCaptureError, match="uv.lock"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_missing_executor_declaration_fails_loud(git_project):
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(run.read_text().replace("  executor: local\n", ""), encoding="utf-8")
    with pytest.raises(FingerprintCaptureError, match="executor"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_missing_config_snapshot_file_fails_loud(git_project):
    (git_project / "config.yaml").unlink()
    with pytest.raises(FingerprintCaptureError, match="config.yaml"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_absent_git_repo_fails_loud(tmp_path: Path):
    """No `.git` at all (never initialized) — `git rev-parse HEAD` fails loud."""
    (tmp_path / "uv.lock").write_text("lock", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("alpha: 1\n", encoding="utf-8")
    runs = tmp_path / "entities" / "workflow-runs"
    runs.mkdir(parents=True)
    (runs / "r1.md").write_text(
        "---\n"
        "id: workflow-run:r1\nkind: workflow-run\ntitle: R1\n"
        "config_snapshot: config.yaml\n"
        "fingerprint:\n"
        "  executor: local\n"
        "  input_artifact_locality: science-managed\n"
        "  output_artifact_locality: science-managed\n"
        "  seed_policy: {kind: deterministic}\n"
        "---\n",
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="git"):
        persist_run_fingerprint(tmp_path, "workflow-run:r1")


def test_persist_is_not_idempotent_because_its_own_write_dirties_the_tree(git_project):
    """`code_dirty` is the worktree state AT CAPTURE TIME — including the previous
    run's uncommitted fingerprint write. This is the honest semantics; commit the
    run entity before re-registering.
    """
    first = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert first.code_dirty.value == "false"

    second = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert second.code_dirty.value == "true"  # the first call's write is uncommitted
    assert second.code_sha.value == first.code_sha.value


def test_code_sha_is_stable_across_repeated_capture(git_project):
    """Only `code_dirty` moves; the commit identity does not."""
    first = persist_run_fingerprint(git_project, "workflow-run:r1")
    second = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert first.code_sha.value == second.code_sha.value
    assert first.environment_digest.value == second.environment_digest.value

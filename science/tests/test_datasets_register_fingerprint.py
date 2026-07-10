import subprocess
from pathlib import Path

import pytest
import yaml

from science_model.frontmatter import parse_frontmatter
from science_model.run_fingerprint import (
    ArtifactLocality,
    ComponentProvenance,
    ExecutorKind,
    SeedPolicy,
)
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
        seed_policy=SeedPolicy(kind="deterministic"),
        step_seeds={},
    )
    base.update(over)
    return base


def test_capture_marks_every_component_captured():
    fp = capture_fingerprint(run_fm={}, **_kwargs())
    for name in ("code_sha", "code_dirty", "environment_digest",
                 "parameters_digest", "input_manifest_digest", "output_manifest_digest"):
        assert getattr(fp, name).provenance is ComponentProvenance.CAPTURED
    assert fp.code_dirty.value == "false"
    assert fp.container_digest is None
    assert fp.fingerprint_policy == "science-run-fingerprint/v1"
    assert fp.seed_policy.kind == "deterministic"
    assert fp.step_seeds == {}


def test_capture_encodes_dirty_as_lowercase_token():
    fp = capture_fingerprint(run_fm={}, **_kwargs(code_dirty=True))
    assert fp.code_dirty.value == "true"


def test_capture_carries_supplied_seed_policy_and_step_seeds():
    """`seed_policy`/`step_seeds` are arguments now (derived by the caller), not
    read from `run_fm`; `capture_fingerprint` places them on the fingerprint verbatim."""
    fp = capture_fingerprint(
        run_fm={},
        **_kwargs(
            seed_policy=SeedPolicy(kind="seeded"),
            step_seeds={"workflow-step:cluster": {"random_state": 42}},
        ),
    )
    assert fp.seed_policy.kind == "seeded"
    assert fp.step_seeds == {"workflow-step:cluster": {"random_state": 42}}


def test_hand_authored_capturable_component_is_rejected():
    run_fm = {"fingerprint": {"code_sha": {"value": "dead" * 10, "provenance": "captured"}}}
    with pytest.raises(FingerprintCaptureError, match="code_sha"):
        capture_fingerprint(run_fm=run_fm, **_kwargs())


def test_hand_authored_seed_policy_is_rejected_by_direct_caller():
    """A direct `capture_fingerprint` caller may not smuggle `seed_policy` in via
    `run_fm` — it is derived, and the widened guard rejects it."""
    run_fm = {"fingerprint": {"seed_policy": {"kind": "deterministic"}}}
    with pytest.raises(FingerprintCaptureError, match="derived by register-run"):
        capture_fingerprint(run_fm=run_fm, **_kwargs())


def test_captured_fingerprint_evaluates_clean():
    from science_tool.run_fingerprint_policy import evaluate_fingerprint

    assert evaluate_fingerprint(capture_fingerprint(run_fm={}, **_kwargs())) == []


@pytest.fixture
def git_project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "uv.lock").write_text("lock", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("alpha: 1\nseed: 42\n", encoding="utf-8")
    (tmp_path / "science.yaml").write_text(
        "name: fingerprint-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    for sub, name, body in [
        ("workflows", "w1", "id: workflow:w1\nkind: workflow\ntitle: W1\n"),
        ("methods", "leiden",
         "id: method:leiden\nkind: method\ntitle: Leiden\n"
         "stochasticity: seedable\nseed_params: [random_state]\n"),
        ("workflow-steps", "cluster",
         "id: workflow-step:cluster\nkind: workflow-step\ntitle: Cluster\n"
         "workflow: workflow:w1\nmethod: method:leiden\n"
         'seed_bindings:\n  random_state: "config.seed"\n'),
        ("workflow-runs", "r1",
         "id: workflow-run:r1\nkind: workflow-run\ntitle: R1\n"
         "workflow: workflow:w1\nconfig_snapshot: config.yaml\n"
         "fingerprint:\n"
         "  executor: local\n"
         "  input_artifact_locality: science-managed\n"
         "  output_artifact_locality: science-managed\n"),
    ]:
        d = tmp_path / "entities" / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(f"---\n{body}---\n", encoding="utf-8")
    # The run declares `workflow: workflow:w1`, so output_manifest_digest capture
    # reads the run-aggregate datapackage; an empty one yields the empty-manifest digest.
    results = tmp_path / "results" / "w1" / "r1"
    results.mkdir(parents=True)
    (results / "datapackage.yaml").write_text(yaml.safe_dump({"resources": []}), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path, check=True,
    )
    return tmp_path


def test_persisted_fingerprint_carries_derived_policy_and_step_seeds(git_project):
    fp = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert fp.seed_policy.kind == "seeded"
    assert fp.seed_policy.rationale is None
    assert fp.step_seeds == {"workflow-step:cluster": {"random_state": 42}}
    written = parse_frontmatter(git_project / "entities" / "workflow-runs" / "r1.md")[0]
    assert written["fingerprint"]["step_seeds"] == {"workflow-step:cluster": {"random_state": 42}}
    assert "seeds" not in written["fingerprint"]["seed_policy"]


def test_authored_seed_policy_is_rejected(git_project):
    # Spec 2 inverts t077: seed_policy was the ONE authored fingerprint field.
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(
        run.read_text(encoding="utf-8").replace(
            "  output_artifact_locality: science-managed\n",
            "  output_artifact_locality: science-managed\n  seed_policy: {kind: deterministic}\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="derived by register-run"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_run_without_a_workflow_ref_fails_closed(git_project):
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(run.read_text(encoding="utf-8").replace("workflow: workflow:w1\n", "", 1), encoding="utf-8")
    with pytest.raises(FingerprintCaptureError, match="declares no workflow"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_workflow_with_no_steps_fails_closed(git_project):
    (git_project / "entities" / "workflow-steps" / "cluster.md").unlink()
    with pytest.raises(FingerprintCaptureError, match="Declare at least one step"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_methodless_step_fails_closed(git_project):
    step = git_project / "entities" / "workflow-steps" / "cluster.md"
    step.write_text(step.read_text(encoding="utf-8").replace("method: method:leiden\n", "", 1), encoding="utf-8")
    with pytest.raises(FingerprintCaptureError, match="declares no method"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_unclassified_method_fails_closed(git_project):
    m = git_project / "entities" / "methods" / "leiden.md"
    m.write_text(m.read_text(encoding="utf-8").replace("stochasticity: seedable\n", "", 1), encoding="utf-8")
    with pytest.raises(FingerprintCaptureError, match="has no stochasticity"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_derivation_error_surfaces_as_capture_error(git_project):
    """A `SeedPolicyDerivationError` (here: a seed binding that names a config key
    the snapshot lacks) must reach the caller as `FingerprintCaptureError` — the
    CLI only catches the latter."""
    (git_project / "config.yaml").write_text("alpha: 1\n", encoding="utf-8")  # drop `seed`
    with pytest.raises(FingerprintCaptureError, match="no key 'seed'"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_persist_writes_captured_components_into_frontmatter(git_project):
    fp = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert fp.code_sha.provenance == "captured" and len(fp.code_sha.value) == 40
    assert fp.code_dirty.value == "false"

    written = yaml.safe_load(
        (git_project / "entities" / "workflow-runs" / "r1.md").read_text().split("---")[1]
    )
    assert written["fingerprint"]["code_sha"]["provenance"] == "captured"
    # git_project's one step applies a seedable method, so the derived policy is seeded.
    assert written["fingerprint"]["seed_policy"]["kind"] == "seeded"


def test_dirty_worktree_is_captured_as_true(git_project):
    # Change alpha (dirties the tree) but keep `seed` so the derivation still resolves.
    (git_project / "config.yaml").write_text("alpha: 2\nseed: 42\n", encoding="utf-8")
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
    """No `.git` at all (never initialized) — `git rev-parse HEAD` fails loud.

    The seed_policy derivation (loadable project, deterministic step) succeeds
    first; the git capture is what fails, so the error still names git.
    """
    (tmp_path / "uv.lock").write_text("lock", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("alpha: 1\n", encoding="utf-8")
    (tmp_path / "science.yaml").write_text(
        "name: fingerprint-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    for sub, name, body in [
        ("workflows", "w1", "id: workflow:w1\nkind: workflow\ntitle: W1\n"),
        ("methods", "const", "id: method:const\nkind: method\ntitle: Const\nstochasticity: deterministic\n"),
        ("workflow-steps", "s1",
         "id: workflow-step:s1\nkind: workflow-step\ntitle: S1\n"
         "workflow: workflow:w1\nmethod: method:const\n"),
        ("workflow-runs", "r1",
         "id: workflow-run:r1\nkind: workflow-run\ntitle: R1\n"
         "workflow: workflow:w1\nconfig_snapshot: config.yaml\n"
         "fingerprint:\n"
         "  executor: local\n"
         "  input_artifact_locality: science-managed\n"
         "  output_artifact_locality: science-managed\n"),
    ]:
        d = tmp_path / "entities" / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(f"---\n{body}---\n", encoding="utf-8")
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


def _project_with_output_resource(root: Path, *, resource: dict) -> Path:
    """A `git_project`-style fixture whose run declares a `workflow:` and whose
    results directory carries one run-aggregate resource, so
    `output_manifest_digest` capture reads it.
    """
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "uv.lock").write_text("lock", encoding="utf-8")
    (root / "config.yaml").write_text("alpha: 1\n", encoding="utf-8")
    (root / "science.yaml").write_text(
        "name: fingerprint-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    for sub, name, body in [
        ("workflows", "wf", "id: workflow:wf\nkind: workflow\ntitle: WF\n"),
        ("methods", "const", "id: method:const\nkind: method\ntitle: Const\nstochasticity: deterministic\n"),
        ("workflow-steps", "s1",
         "id: workflow-step:s1\nkind: workflow-step\ntitle: S1\n"
         "workflow: workflow:wf\nmethod: method:const\n"),
    ]:
        d = root / "entities" / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(f"---\n{body}---\n", encoding="utf-8")
    runs = root / "entities" / "workflow-runs"
    runs.mkdir(parents=True)
    (runs / "r1.md").write_text(
        "---\n"
        "id: workflow-run:r1\nkind: workflow-run\ntitle: R1\n"
        'workflow: "workflow:wf"\n'
        "config_snapshot: config.yaml\n"
        "fingerprint:\n"
        "  executor: local\n"
        "  input_artifact_locality: science-managed\n"
        "  output_artifact_locality: science-managed\n"
        "---\n",
        encoding="utf-8",
    )
    results = root / "results" / "wf" / "r1"
    results.mkdir(parents=True)
    (results / "datapackage.yaml").write_text(
        yaml.safe_dump({"resources": [resource]}), encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=root, check=True,
    )
    return root


def test_resource_without_content_hash_fails_loud(tmp_path: Path):
    """No `hash`/`sha256`/`digest` on a resource must not silently fall back to
    its declared `path` — that would leave `output_manifest_digest` blind to
    content changes. It must name the offending resource and the source."""
    project = _project_with_output_resource(tmp_path, resource={"name": "out", "path": "out.csv"})
    with pytest.raises(FingerprintCaptureError, match="out.csv"):
        persist_run_fingerprint(project, "workflow-run:r1")


def test_changing_resource_hash_changes_output_manifest_digest(tmp_path: Path):
    project_a = _project_with_output_resource(
        tmp_path / "a", resource={"name": "out", "path": "out.csv", "hash": "sha256:aaa"}
    )
    fp_a = persist_run_fingerprint(project_a, "workflow-run:r1")

    project_b = _project_with_output_resource(
        tmp_path / "b", resource={"name": "out", "path": "out.csv", "hash": "sha256:bbb"}
    )
    fp_b = persist_run_fingerprint(project_b, "workflow-run:r1")

    assert fp_a.output_manifest_digest.value != fp_b.output_manifest_digest.value


def test_skipped_workflow_step_file_fails_closed(git_project):
    # `persist_run_fingerprint` loads with strict_core_schema=False (the run it is
    # registering carries an incomplete fingerprint by construction). That makes the
    # loader SILENTLY SKIP any workflow-step whose frontmatter fails validation.
    # Deriving from the surviving subset would stamp this run with a seed_policy
    # computed from an incomplete step set -- here, `seeded` while a second step
    # vanished. A skipped method is already fail-closed (its ref stops resolving);
    # a skipped step is not, because nothing knows it should have been there.
    broken = git_project / "entities" / "workflow-steps" / "broken.md"
    broken.write_text(
        "---\nid: workflow-step:broken\nkind: workflow-step\ntitle: Broken\n"
        "workflow: workflow:w1\nmethod: method:leiden\n"
        'seed_bindings:\n  random_state: "env.SEED"\n---\n',
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="failed schema validation"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_skipped_workflow_step_in_a_subdirectory_fails_closed(git_project):
    # Entity discovery is recursive (`rglob`), so a step may live anywhere under
    # entities/. A guard that enumerates only `entities/workflow-steps/*.md` misses
    # a nested one, and the derivation proceeds on the surviving subset.
    bad = git_project / "entities" / "workflow-steps" / "nested" / "embed.md"
    bad.parent.mkdir(parents=True)
    bad.write_text(
        "---\nid: workflow-step:embed\nkind: workflow-step\ntitle: Embed\n"
        "workflow: workflow:w1\nmethod: method:leiden\n"
        'seed_bindings:\n  random_state: "env.SEED"\n---\n',
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="failed schema validation"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def _write_nondeterministic_step(root, workflow_ref: str) -> None:
    (root / "entities" / "methods" / "embed.md").write_text(
        "---\nid: method:embed\nkind: method\ntitle: Embed\nstochasticity: nondeterministic\n---\n",
        encoding="utf-8",
    )
    (root / "entities" / "workflow-steps" / "embed.md").write_text(
        f"---\nid: workflow-step:embed\nkind: workflow-step\ntitle: Embed\n"
        f"workflow: {workflow_ref}\nmethod: method:embed\n---\n",
        encoding="utf-8",
    )


def test_step_with_an_unresolvable_workflow_ref_fails_closed(git_project):
    # A bare slug is a REAL pattern in the corpus (post-acute-infection authors
    # `workflow: "t035-..."`). Matching step membership on canonical_id silently
    # excludes such a step, so this nondeterministic one would vanish and the run
    # would be stamped `seeded` -- a false reproducibility claim.
    _write_nondeterministic_step(git_project, '"w1"')
    with pytest.raises(FingerprintCaptureError, match="does not resolve"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_step_with_no_workflow_ref_fails_closed(git_project):
    _write_nondeterministic_step(git_project, '""')
    with pytest.raises(FingerprintCaptureError, match="declares no workflow"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_step_belonging_to_another_workflow_is_excluded_not_rejected(git_project):
    # The guards must not over-reject: a step that resolves cleanly to a DIFFERENT
    # workflow is simply not part of this run's step set.
    (git_project / "entities" / "workflows" / "w2.md").write_text(
        "---\nid: workflow:w2\nkind: workflow\ntitle: W2\n---\n", encoding="utf-8"
    )
    _write_nondeterministic_step(git_project, "workflow:w2")
    fp = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert fp.seed_policy.kind == "seeded"
    assert fp.step_seeds == {"workflow-step:cluster": {"random_state": 42}}

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from science_model.frontmatter import parse_frontmatter
from science_model.run_fingerprint import (
    ArtifactLocality,
    CaptureOrigin,
    ComponentProvenance,
    ExecutorKind,
    RunDeclaration,
    SeedPolicy,
)
from science_tool.datasets_register import (
    FingerprintCaptureError,
    capture_fingerprint,
    persist_run_fingerprint,
)


def _declaration(**over) -> RunDeclaration:
    base = dict(
        executor=ExecutorKind.LOCAL,
        input_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
        output_artifact_locality=ArtifactLocality.SCIENCE_MANAGED,
    )
    base.update(over)
    return RunDeclaration(**base)


def _kwargs(**over):
    base = dict(
        declaration=_declaration(),
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
    fp = capture_fingerprint(**_kwargs())
    for name in ("code_sha", "code_dirty", "environment_digest",
                 "parameters_digest", "input_manifest_digest", "output_manifest_digest"):
        assert getattr(fp, name).provenance is ComponentProvenance.CAPTURED
    assert fp.code_dirty.value == "false"
    assert fp.container_digest is None
    assert fp.fingerprint_policy == "science-run-fingerprint/v1"
    assert fp.seed_policy.kind == "deterministic"
    assert fp.step_seeds == {}


def test_capture_encodes_dirty_as_lowercase_token():
    fp = capture_fingerprint(**_kwargs(code_dirty=True))
    assert fp.code_dirty.value == "true"


def test_capture_carries_supplied_seed_policy_and_step_seeds():
    """`seed_policy`/`step_seeds` are arguments now (derived by the caller), not
    read from `run_fm`; `capture_fingerprint` places them on the fingerprint verbatim."""
    fp = capture_fingerprint(
        **_kwargs(
            seed_policy=SeedPolicy(kind="seeded"),
            step_seeds={"workflow-step:cluster": {"random_state": 42}},
        ),
    )
    assert fp.seed_policy.kind == "seeded"
    assert fp.step_seeds == {"workflow-step:cluster": {"random_state": 42}}


def test_capture_takes_no_frontmatter_so_nothing_can_be_hand_authored():
    """t093 made the old `run_fm` guard structurally unnecessary.

    `capture_fingerprint` used to accept the run's frontmatter and reject any
    observation found under `fingerprint:`. It now accepts only the typed
    declaration, so there is no channel to smuggle one through — asserted here so
    a future signature change cannot quietly reopen one.
    """
    import inspect

    params = set(inspect.signature(capture_fingerprint).parameters)
    assert "run_fm" not in params
    assert "declaration" in params


def test_capture_copies_declared_fields_onto_the_fingerprint():
    """The fingerprint stands alone as a science-run-fingerprint/v1 record."""
    fp = capture_fingerprint(**_kwargs(declaration=_declaration(
        input_artifact_locality=ArtifactLocality.EXTERNAL)))
    assert fp.executor is ExecutorKind.LOCAL
    assert fp.input_artifact_locality is ArtifactLocality.EXTERNAL
    assert fp.output_artifact_locality is ArtifactLocality.SCIENCE_MANAGED
    assert fp.capture_origin is None


def test_a_commons_run_can_be_captured_because_capture_origin_is_declared():
    """Before t093 `capture_origin` was unreachable, so a commons run could not
    be registered at all: the model demands it and nothing could supply it."""
    origin = CaptureOrigin(
        origin_project="upstream", origin_run_ref="workflow-run:up",
        captured_at=datetime(2026, 7, 10, tzinfo=UTC), captured_by="science",
        capture_policy="science-run-fingerprint/v1",
    )
    fp = capture_fingerprint(**_kwargs(declaration=_declaration(
        executor=ExecutorKind.COMMONS, capture_origin=origin)))
    assert fp.executor is ExecutorKind.COMMONS
    assert fp.capture_origin is not None
    assert fp.capture_origin.origin_run_ref == "workflow-run:up"


def test_captured_fingerprint_evaluates_clean():
    from science_tool.run_fingerprint_policy import evaluate_fingerprint

    assert evaluate_fingerprint(capture_fingerprint(**_kwargs())) == []


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
         "execution:\n"
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


def test_authored_seed_policy_in_the_declaration_is_rejected(git_project):
    """Spec 2 inverted t077: `seed_policy` was the ONE authored fingerprint field.

    It is derived, so it is not part of the declaration — `extra="forbid"` on
    `RunDeclaration` is what says so.
    """
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(
        run.read_text(encoding="utf-8").replace(
            "  output_artifact_locality: science-managed\n",
            "  output_artifact_locality: science-managed\n  seed_policy: {kind: deterministic}\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="seed_policy"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_a_pre_t093_authored_fingerprint_stub_is_rejected_and_names_the_migration(git_project):
    """The exact block the old template told authors to write is now refused."""
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(
        run.read_text(encoding="utf-8").replace("execution:\n", "fingerprint:\n", 1),
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="`execution:` must be declared"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_authored_fingerprint_alongside_a_declaration_is_rejected(git_project):
    """`fingerprint:` is captured, never authored. A partial one is hand-written
    by construction: every fingerprint register-run writes round-trips the model."""
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(
        run.read_text(encoding="utf-8").replace(
            "config_snapshot: config.yaml\n",
            "config_snapshot: config.yaml\nfingerprint:\n  code_sha: {value: abc, provenance: captured}\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="captured by register-run, never authored"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_reregistering_accepts_the_fingerprint_it_previously_wrote(git_project):
    """The guard above must not reject register-run's own output."""
    first = persist_run_fingerprint(git_project, "workflow-run:r1")
    second = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert first.code_sha.value == second.code_sha.value
    assert second.seed_policy.kind == "seeded"


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
         "execution:\n"
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
        "execution:\n"
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


def test_commons_run_persists_and_reregisters_with_capture_origin(git_project):
    """End-to-end for the path t093 unblocked.

    A commons run was previously impossible to register: `RunFingerprint` requires
    `capture_origin` when executor='commons', and nothing could supply it. Now the
    run declares it. The second call proves the serialized `capture_origin` survives
    the YAML round-trip and is re-accepted as register-run's own prior write.
    """
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(
        run.read_text(encoding="utf-8").replace(
            "  executor: local\n",
            "  executor: commons\n"
            "  capture_origin:\n"
            "    origin_project: upstream\n"
            "    origin_run_ref: workflow-run:up\n"
            "    captured_at: 2026-07-10T00:00:00Z\n"
            "    captured_by: science\n"
            "    capture_policy: science-run-fingerprint/v1\n",
        ),
        encoding="utf-8",
    )
    first = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert first.executor is ExecutorKind.COMMONS
    assert first.capture_origin is not None
    assert first.capture_origin.origin_project == "upstream"

    second = persist_run_fingerprint(git_project, "workflow-run:r1")
    assert second.capture_origin == first.capture_origin


def test_declaring_capture_origin_on_a_local_run_fails_loud(git_project):
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    run.write_text(
        run.read_text(encoding="utf-8").replace(
            "  output_artifact_locality: science-managed\n",
            "  output_artifact_locality: science-managed\n"
            "  capture_origin:\n"
            "    origin_project: upstream\n"
            "    origin_run_ref: workflow-run:up\n"
            "    captured_at: 2026-07-10T00:00:00Z\n"
            "    captured_by: science\n"
            "    capture_policy: science-run-fingerprint/v1\n",
        ),
        encoding="utf-8",
    )
    with pytest.raises(FingerprintCaptureError, match="capture_origin"):
        persist_run_fingerprint(git_project, "workflow-run:r1")


def test_author_then_validate_then_register_then_validate(git_project):
    """The catch-22 t093 names, asserted end to end.

    Before the fix, step 2 raised: the authored `fingerprint:` stub could not
    satisfy the full `RunFingerprint` schema, and `strict_core_schema=True` is the
    default that `science validate` and `science graph build` both load under.
    """
    from science_tool.graph.sources import load_project_sources
    from science_tool.validate.checks.workflow_runs import check_run_fingerprint_obligations
    from science_tool.validate.context import ValidateContext

    def fingerprint_findings() -> list:
        ctx = ValidateContext.from_project_root(git_project, strict=False, verbose=False)
        return list(check_run_fingerprint_obligations(ctx))

    # 1. The run is authored, declaring how it executed. Nothing is captured yet.
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    assert "execution:" in run.read_text(encoding="utf-8")
    assert "fingerprint:" not in run.read_text(encoding="utf-8")

    # 2. It strict-loads and validates clean BEFORE it has ever been registered.
    sources = load_project_sources(git_project, strict_core_schema=True)
    assert not sources.skipped_entities
    assert fingerprint_findings() == []

    # 3. Register it.
    persist_run_fingerprint(git_project, "workflow-run:r1")
    assert "fingerprint:" in run.read_text(encoding="utf-8")

    # 4. It still strict-loads and validates clean, now with a captured fingerprint.
    sources = load_project_sources(git_project, strict_core_schema=True)
    assert not sources.skipped_entities
    assert fingerprint_findings() == []


def test_editing_the_declaration_after_registering_is_caught_as_drift(git_project):
    """The fail-open the split introduces: two copies of `executor` can diverge."""
    from science_tool.validate.checks.workflow_runs import check_run_fingerprint_obligations
    from science_tool.validate.context import ValidateContext

    persist_run_fingerprint(git_project, "workflow-run:r1")
    run = git_project / "entities" / "workflow-runs" / "r1.md"
    text = run.read_text(encoding="utf-8")
    head, sep, tail = text.partition("fingerprint:")
    run.write_text(
        head.replace("  input_artifact_locality: science-managed\n",
                     "  input_artifact_locality: external\n") + sep + tail,
        encoding="utf-8",
    )
    ctx = ValidateContext.from_project_root(git_project, strict=False, verbose=False)
    rules = [r.rule for r in check_run_fingerprint_obligations(ctx)]
    assert rules == ["run.fingerprint-declaration-drift"]

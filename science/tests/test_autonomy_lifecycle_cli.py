from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main

AGENT = "curation-sweep"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture(autouse=True)
def pinned_toolkit(monkeypatch: pytest.MonkeyPatch) -> None:
    """As in Task 5: `assert_toolkit_matches` refuses a dirty judging toolkit, and the
    checkout these tests run in is dirty while this plan is being implemented."""
    from science_tool.autonomy import toolkit as toolkit_module

    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Reuses Task 5's seeded project; a basis of zero units makes every case vacuous.

    The graph is built and committed for the same reason as in Task 5: `start`
    materializes, so an unbuilt graph would leave the tree dirty behind the supervisor's
    own back."""
    from science_tool.graph.materialize import materialize_graph
    from test_autonomy_lifecycle import _seed_science_project

    root = tmp_path / "project"
    root.mkdir()
    _seed_science_project(root)
    materialize_graph(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


@pytest.fixture
def baseline_path(tmp_path: Path) -> Path:
    return tmp_path / "supervisor-state" / "run.json"


@pytest.fixture
def feedback_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`feedback_cli._get_feedback_dir` reads SCIENCE_FEEDBACK_DIR before falling back to
    the user's config dir. Redirect it so a test never writes to the real one."""
    target = tmp_path / "feedback"
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(target))
    return target


def _start(project: Path, baseline_path: Path, *extra: str):
    return CliRunner().invoke(
        main,
        [
            "autonomy", "start", "--project-root", str(project),
            "--agent", AGENT, "--model", "test-model",
            "--short-id", "a3f1", "--baseline-out", str(baseline_path), *extra,
        ],
    )


def _finish(project: Path, baseline_path: Path, *extra: str):
    return CliRunner().invoke(
        main,
        [
            "autonomy", "finish", "--project-root", str(project),
            "--baseline", str(baseline_path), "--head", _git(project, "rev-parse", "HEAD"),
            "--tokens", "100", "--wall-clock-seconds", "1800", *extra,
        ],
    )


def _edit_and_commit(project: Path, old: str, new: str, run_id: str, *, marked: bool = True) -> None:
    paper = project / "entities" / "papers" / "x.md"
    paper.write_text(paper.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    _git(project, "add", "-A")
    message = f"docs: edit\n\nScience-Run: {run_id}" if marked else "docs: edit"
    _git(project, "commit", "-q", "-m", message, "--author", f"{AGENT} <agent@science.local>")


def _run_id(baseline_path: Path) -> str:
    return json.loads(baseline_path.read_text(encoding="utf-8"))["run_id"]


def test_start_exits_zero_and_writes_a_baseline_but_no_record(project: Path, baseline_path: Path):
    result = _start(project, baseline_path)
    assert result.exit_code == 0, result.output
    assert baseline_path.exists()
    assert not (project / "runs").exists()


def test_start_json_names_the_run_and_the_baseline(project: Path, baseline_path: Path):
    result = _start(project, baseline_path, "--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["run_id"].startswith("run:")
    assert payload["baseline_path"] == str(baseline_path)
    assert payload["branch"] == f"auto/{payload['run_id'].removeprefix('run:')}"
    assert "snapshot" not in payload, "the payload is a summary, not the whole capture"


def test_start_refuses_a_baseline_inside_the_project(project: Path):
    result = _start(project, project / "runs" / "b.json")
    assert result.exit_code == 2
    assert "inside the project root" in result.output


def test_start_exits_two_when_the_project_root_is_not_a_repository(tmp_path: Path, baseline_path: Path):
    """`extract._git` raises `ExtractError` whenever git exits non-zero, including when
    `--project-root` is not a git repository at all. Without `ExtractError` on the
    boundary tuple this tracebacks instead of exiting 2."""
    not_a_repo = tmp_path / "loose"
    not_a_repo.mkdir()
    result = _start(not_a_repo, baseline_path)
    assert result.exit_code == 2
    assert result.exception is None or isinstance(result.exception, SystemExit), result.output
    assert "could not start" in result.output


def test_finish_exits_zero_on_a_clean_run(project: Path, baseline_path: Path, feedback_dir: Path):
    _start(project, baseline_path)
    _edit_and_commit(project, "venue: Nature", "venue: Science", _run_id(baseline_path))

    result = _finish(project, baseline_path)
    assert result.exit_code == 0, result.output
    assert "clean" in result.output
    assert not feedback_dir.exists(), "a clean run files no feedback"


def test_finish_exits_one_on_quarantine_and_names_the_cause(project: Path, baseline_path: Path, feedback_dir: Path):
    _start(project, baseline_path)
    _edit_and_commit(
        project, "venue: Nature", "venue: Nature\nmethods_summary: rewritten", _run_id(baseline_path)
    )

    result = _finish(project, baseline_path)
    assert result.exit_code == 1, result.output
    assert "quarantined" in result.output
    assert "methods_summary" in result.output


def test_a_quarantine_files_exactly_one_feedback_entry(project: Path, baseline_path: Path, feedback_dir: Path):
    import yaml

    _start(project, baseline_path)
    run_id = _run_id(baseline_path)
    _edit_and_commit(project, "venue: Nature", "venue: Nature\nmethods_summary: rewritten", run_id)

    assert _finish(project, baseline_path).exit_code == 1

    entries = sorted(feedback_dir.glob("fb-*.yaml"))
    assert len(entries) == 1
    entry = yaml.safe_load(entries[0].read_text(encoding="utf-8"))
    assert run_id in entry["summary"]
    assert entry["target"] == "command:autonomy-finish"
    assert entry["status"] == "open"
    assert "methods_summary" in entry["detail"]


def test_the_feedback_category_is_one_the_rest_of_the_system_recognizes(
    project: Path, baseline_path: Path, feedback_dir: Path
):
    """`category` has no field validator, so an invented value is accepted silently and
    then never appears in a category-filtered view. Pin it to the real vocabulary."""
    import yaml

    from science_tool.feedback import VALID_CATEGORIES

    _start(project, baseline_path)
    _edit_and_commit(
        project, "venue: Nature", "venue: Nature\nmethods_summary: rewritten", _run_id(baseline_path)
    )
    assert _finish(project, baseline_path).exit_code == 1

    entry = yaml.safe_load(sorted(feedback_dir.glob("fb-*.yaml"))[0].read_text(encoding="utf-8"))
    assert entry["category"] in VALID_CATEGORIES


def test_a_finish_with_no_budget_option_is_an_argument_error(project: Path, baseline_path: Path):
    """`RunBudget` requires at least one. Without this guard the omission surfaces as an
    `unwired` attestation -- a record saying 'we could not tell' filed because of a typo."""
    _start(project, baseline_path)
    result = CliRunner().invoke(
        main,
        [
            "autonomy", "finish", "--project-root", str(project),
            "--baseline", str(baseline_path), "--head", _git(project, "rev-parse", "HEAD"),
        ],
    )
    assert result.exit_code == 2
    assert "--tokens" in result.output
    assert not (project / "runs").exists(), "an argument error must attest nothing"


def test_start_refuses_an_agent_slug_the_record_could_never_carry(project: Path, baseline_path: Path):
    """Fail at `start`, not hours later when `finish` builds the record and discovers the
    identity is unusable -- by then the run's work exists and can never be attested."""
    result = CliRunner().invoke(
        main,
        [
            "autonomy", "start", "--project-root", str(project),
            "--agent", "Curation_Sweep", "--model", "test-model",
            "--short-id", "a3f1", "--baseline-out", str(baseline_path),
        ],
    )
    assert result.exit_code == 2
    assert "kebab-case" in result.output
    assert not baseline_path.exists()


def test_a_quarantine_still_exits_one_when_feedback_cannot_be_filed(
    project: Path, baseline_path: Path, monkeypatch: pytest.MonkeyPatch, feedback_dir: Path
):
    """The record is already written and can never be rewritten. If escalation crashes
    the command here, a retry hits the never-overwrite rule and the run can never be
    finished at all."""
    from science_tool.autonomy import lifecycle as lifecycle_module

    _start(project, baseline_path)
    _edit_and_commit(
        project, "venue: Nature", "venue: Nature\nmethods_summary: rewritten", _run_id(baseline_path)
    )

    def _boom(*a, **k):
        raise OSError("feedback directory is read-only")

    monkeypatch.setattr(lifecycle_module, "file_quarantine_feedback", _boom)

    result = _finish(project, baseline_path)
    assert result.exit_code == 1, result.output
    assert "feedback directory is read-only" in result.output
    assert (project / "runs").exists(), "the attestation is written regardless"


def test_finish_exits_two_on_a_missing_baseline(project: Path, tmp_path: Path, feedback_dir: Path):
    result = CliRunner().invoke(
        main,
        [
            "autonomy", "finish", "--project-root", str(project),
            "--baseline", str(tmp_path / "absent.json"),
            "--head", _git(project, "rev-parse", "HEAD"),
            "--tokens", "0", "--wall-clock-seconds", "1",
        ],
    )
    assert result.exit_code == 2
    assert "unwired" in result.output
    assert not feedback_dir.exists(), "unwired blocks; it does not file a quarantine item"


def test_finish_refuses_a_baseline_inside_the_project(project: Path):
    result = CliRunner().invoke(
        main,
        [
            "autonomy", "finish", "--project-root", str(project),
            "--baseline", str(project / "runs" / "b.json"),
            "--head", _git(project, "rev-parse", "HEAD"),
            "--tokens", "0", "--wall-clock-seconds", "1",
        ],
    )
    assert result.exit_code == 2
    assert "inside the project root" in result.output


def test_finish_json_carries_the_disposition_and_the_denials(project: Path, baseline_path: Path, feedback_dir: Path):
    _start(project, baseline_path)
    _edit_and_commit(
        project, "venue: Nature", "venue: Nature\nmethods_summary: rewritten", _run_id(baseline_path)
    )

    result = _finish(project, baseline_path, "--json")
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["disposition"] == "quarantined"
    assert any(d["field"] == "methods_summary" for d in payload["denials"])


def test_both_commands_are_registered_under_the_autonomy_group():
    group = main.commands["autonomy"]
    assert {"start", "finish", "path-gate"} <= set(group.commands)  # type: ignore[attr-defined]


def test_finish_exits_2_when_git_cannot_be_invoked_at_all(
    project: Path, baseline_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """`unwired` must never degrade into a stronger-looking verdict.

    Exit 1 is `quarantined` in the shipped docs. A `FileNotFoundError` escaping the
    lifecycle gets click's generic exit 1, so a machine with no git would report the run
    as a policy violation rather than as unjudgeable.
    """
    from science_tool.autonomy import git as git_module

    assert _start(project, baseline_path).exit_code == 0
    head = _git(project, "rev-parse", "HEAD")

    class _NoGit:
        @staticmethod
        def run(*args, **kwargs):
            raise OSError(2, "No such file or directory: 'git'")

    monkeypatch.setattr(git_module, "subprocess", _NoGit)

    result = CliRunner().invoke(
        main,
        [
            "autonomy", "finish", "--project-root", str(project),
            "--baseline", str(baseline_path), "--head", head,
            "--tokens", "100", "--wall-clock-seconds", "1800",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "unwired" in result.output

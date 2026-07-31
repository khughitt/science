from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from science_model.autonomous_runs import RunTier
from science_model.evidence_broker import (
    MAX_TARGET_CHARS,
    EvidenceSessionSpec,
    InstrumentIdentity,
    SurfacePolicy,
)

from science_tool.autonomy.control_plane import run_dir
from science_tool.autonomy.lifecycle import start_run
from science_tool.cli import main

HANDLE = "2026-07-25-curation-sweep-a3f1"
NOTICE = "withheld"
FILE_CONTENT = "visible bytes\n"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture(autouse=True)
def pinned_toolkit(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.autonomy import toolkit as toolkit_module

    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    from science_tool.graph.materialize import materialize_graph
    from test_autonomy_lifecycle import _seed_science_project

    root = tmp_path / "project"
    root.mkdir()
    _seed_science_project(root)
    (root / "a.md").write_text(FILE_CONTENT, encoding="utf-8")
    (root / "private").mkdir()
    (root / "private" / "secret.md").write_text("secret\n", encoding="utf-8")
    materialize_graph(root)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


@pytest.fixture
def brokered(project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SCIENCE_CONTROL_PLANE", str(tmp_path / "control"))
    baseline = start_run(
        project,
        agent="curation-sweep",
        model="test-model",
        tier=RunTier.BELIEF_NEUTRAL,
        short_id="a3f1",
        started=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        evidence=EvidenceSessionSpec(
            budget=3,
            surface_policy=SurfacePolicy(deny_prefixes=("private",), notice=NOTICE),
            instrument=InstrumentIdentity(
                ref="rubric.md", sha256="c" * 64, prompt_hash="d" * 64
            ),
        ),
    )
    return baseline


def _serve(project: Path, handle: str, target: str, *extra: str):
    return CliRunner().invoke(
        main,
        [
            "evidence",
            "serve",
            "--project-root",
            str(project),
            "--session",
            handle,
            "--op",
            "read",
            "--target",
            target,
            *extra,
        ],
    )


def test_a_traversing_handle_is_refused_before_any_path_join(project: Path) -> None:
    result = _serve(project, "../../elsewhere", "a.md")
    assert result.exit_code == 2
    assert "run id" in result.output


def test_an_overlong_target_is_reported_as_a_usage_error(project: Path, brokered) -> None:
    result = _serve(project, HANDLE, "a" * (MAX_TARGET_CHARS + 1))
    assert result.exit_code == 2
    assert "characters" in result.output


def test_a_handle_whose_baseline_names_another_run_is_refused_after_loading(
    project: Path, brokered
) -> None:
    other = "2026-07-25-curation-sweep-b4e2"
    directory = run_dir(project, other)
    directory.mkdir(parents=True)
    source = brokered.evidence.journal_path.parent / "baseline.json"
    (directory / "baseline.json").write_bytes(source.read_bytes())
    result = _serve(project, other, "a.md")
    assert result.exit_code == 2
    assert "does not name" in result.output


def test_an_unbrokered_run_cannot_be_served(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_CONTROL_PLANE", str(tmp_path / "control"))
    directory = run_dir(project, HANDLE)
    start_run(
        project,
        agent="curation-sweep",
        model="test-model",
        tier=RunTier.BELIEF_NEUTRAL,
        short_id="a3f1",
        started=datetime(2026, 7, 25, 9, 0, tzinfo=UTC),
        baseline_out=directory / "baseline.json",
    )
    result = _serve(project, HANDLE, "a.md")
    assert result.exit_code == 2
    assert "not opened with a broker spec" in result.output


def test_the_receipt_never_carries_the_bytes(project: Path, brokered) -> None:
    result = _serve(project, HANDLE, "a.md", "--format", "json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) == {"outcome", "sha256", "path", "notice"}
    assert payload["notice"] is None
    assert FILE_CONTENT not in result.output


def test_a_refusal_prints_the_notice_and_no_path(project: Path, brokered) -> None:
    result = _serve(project, HANDLE, "private/secret.md", "--format", "json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["outcome"] == "refused"
    assert payload["path"] is None
    assert payload["notice"] == NOTICE


def test_the_cli_cannot_override_the_budget_or_the_policy() -> None:
    from science_tool.evidence_broker.cli import serve_command

    names = {param.name for param in serve_command.params}
    assert names & {"budget", "deny_prefixes", "surface_policy", "journal_path", "commit"} == set()

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main

PAPER = "entities/papers/smith2020.md"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _paper_text(*, venue: str = "Nature", extra: str = "") -> str:
    return f"---\nid: paper:smith2020\nkind: paper\ntitle: T\nvenue: {venue}\n{extra}---\n\nAbstract.\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    _write(tmp_path, PAPER, _paper_text())
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def _run(repo: Path, base: str, head: str, *extra: str):
    return CliRunner().invoke(
        main,
        [
            "autonomy",
            "path-gate",
            "--project-root",
            str(repo),
            "--base",
            base,
            "--head",
            head,
            *extra,
        ],
    )


def test_an_allowed_edit_exits_zero(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "venue")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, head)
    assert result.exit_code == 0, result.output
    assert "allowed" in result.output


def test_a_denied_edit_exits_one_and_names_path_and_field(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(extra="confidence: 0.9\n"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "confidence")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, head)
    assert result.exit_code == 1
    assert PAPER in result.output
    assert "confidence" in result.output


def test_an_unresolvable_commit_exits_two_not_zero(repo: Path):
    """Exit 2 mirrors `graph belief-basis`: a gate that cannot see must not report
    allowed."""
    base = _git(repo, "rev-parse", "HEAD")
    result = _run(repo, base, "0" * 40)
    assert result.exit_code == 2
    assert "could not evaluate" in result.output


def test_malformed_frontmatter_exits_two_not_a_traceback(repo: Path):
    """An unparseable change set is uncomputable, not clean, and must land on the
    exit-2 branch rather than escaping as an unhandled YAMLError."""
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, "---\nid: paper:smith2020\nvenue: [unclosed\n---\n\nAbstract.\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "malformed")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, head)
    assert result.exit_code == 2, result.output
    assert "could not evaluate" in result.output


def test_report_only_denies_an_entity_edit(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(venue="Science"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "venue")
    head = _git(repo, "rev-parse", "HEAD")

    assert _run(repo, base, head, "--tier", "report-only").exit_code == 1


@pytest.mark.parametrize(
    "output_args",
    [
        pytest.param(("--json",), id="json-alias"),
        pytest.param(("--format", "json"), id="canonical-format"),
    ],
)
def test_json_output_carries_the_denials(repo: Path, output_args: tuple[str, ...]):
    base = _git(repo, "rev-parse", "HEAD")
    _write(repo, PAPER, _paper_text(extra="confidence: 0.9\n"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "confidence")
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, head, *output_args)
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["allowed"] is False
    assert payload["denials"][0]["field"] == "confidence"


def test_format_json_allowed_output_is_parseable_and_exits_zero(repo: Path):
    head = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, head, head, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["allowed"] is True
    assert payload["denials"] == []


def test_format_json_evaluation_error_is_parseable_and_exits_two(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")

    result = _run(repo, base, "0" * 40, "--format", "json")

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["allowed"] is False
    assert payload["denials"] == []
    assert payload["error"].startswith("could not evaluate:")


def test_the_command_is_registered_under_the_autonomy_group():
    assert "autonomy" in main.commands
    assert "path-gate" in main.commands["autonomy"].commands  # type: ignore[attr-defined]

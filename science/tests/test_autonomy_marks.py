from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy.marks import verify_marks

RUN_ID = "run:2026-07-25-curation-sweep-a3f1"
AGENT = "curation-sweep"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _commit(root: Path, message: str, *, author: str | None = None) -> str:
    (root / "f.txt").write_text(message, encoding="utf-8")
    _git(root, "add", "-A")
    args = ["commit", "-q", "-m", message]
    if author is not None:
        args += ["--author", author]
    _git(root, *args)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "base")
    return tmp_path


def _good_message(n: int) -> str:
    return f"docs: change {n}\n\nScience-Run: {RUN_ID}"


def test_a_well_marked_range_has_no_issues(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, _good_message(1), author=f"{AGENT} <agent@science.local>")
    assert verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT) == ()


def test_a_commit_with_no_trailer_is_flagged(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, "docs: untagged", author=f"{AGENT} <agent@science.local>")
    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert len(issues) == 1
    assert "trailer" in issues[0].reason


def test_a_commit_naming_another_run_is_flagged(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(
        repo, "docs: x\n\nScience-Run: run:2026-01-01-other-0000",
        author=f"{AGENT} <agent@science.local>",
    )
    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert "another run" in issues[0].reason


def test_a_foreign_author_is_flagged(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, _good_message(1), author="Someone Else <a@b.c>")
    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert "author" in issues[0].reason


def test_the_agents_name_over_a_foreign_email_is_flagged(repo: Path):
    """Design §3 spells the author as `<role> <agent@science.local>`. Checking the name
    alone accepts half of that spelling, which is not the spelling."""
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, _good_message(1), author=f"{AGENT} <someone@example.com>")
    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert len(issues) == 1
    assert "someone@example.com" in issues[0].reason


def test_every_commit_in_the_range_is_checked(repo: Path):
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _good_message(1), author=f"{AGENT} <agent@science.local>")
    _commit(repo, "docs: untagged", author=f"{AGENT} <agent@science.local>")
    head = _commit(repo, _good_message(3), author=f"{AGENT} <agent@science.local>")

    issues = verify_marks(repo, base, head, run_id=RUN_ID, agent=AGENT)
    assert len(issues) == 1


def test_an_empty_range_has_no_issues(repo: Path):
    head = _git(repo, "rev-parse", "HEAD")
    assert verify_marks(repo, head, head, run_id=RUN_ID, agent=AGENT) == ()

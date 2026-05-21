import os
import subprocess
from datetime import date
from pathlib import Path

from science_tool.code.git import last_content_change_date


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def test_returns_last_commit_date(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    (tmp_path / "f.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "f.py")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-03-15T12:00:00", "GIT_AUTHOR_DATE": "2026-03-15T12:00:00"}
    _git(tmp_path, "commit", "-m", "add f", env=env)
    assert last_content_change_date("f.py", repo_root=tmp_path) == date(2026, 3, 15)


def test_returns_none_for_untracked_file(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    (tmp_path / "f.py").write_text("x = 1\n", encoding="utf-8")
    assert last_content_change_date("f.py", repo_root=tmp_path) is None

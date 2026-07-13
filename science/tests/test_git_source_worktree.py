from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.git_source


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit(repo: Path) -> str:
    _run("git", "init", "-q", cwd=repo)
    _run("git", "config", "user.email", "science-test@example.invalid", cwd=repo)
    _run("git", "config", "user.name", "Science Test", cwd=repo)
    _run("git", "add", ".", cwd=repo)
    _run("git", "commit", "-q", "-m", "fixture", cwd=repo)
    return _run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()


def _toolkit_repo(root: Path) -> tuple[Path, str]:
    repo = root / "toolkit"
    repo.mkdir()
    _write(
        repo / "science" / "pyproject.toml",
        """[project]
name = "science"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["science-model"]

[project.scripts]
science = "science.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv.sources]
science-model = { path = "model", editable = true }
""",
    )
    _write(repo / "science" / "src" / "science" / "__init__.py", "")
    _write(
        repo / "science" / "src" / "science" / "cli.py",
        """from __future__ import annotations

import sys

from science_model import MODEL_SENTINEL


def main() -> None:
    if sys.argv[1:] == ["validate", "--verbose"]:
        print(f"validated:{MODEL_SENTINEL}")
        return
    print(f"science-fixture:{MODEL_SENTINEL}")
""",
    )
    _write(
        repo / "science" / "model" / "pyproject.toml",
        """[project]
name = "science-model"
version = "1.0.0"
requires-python = ">=3.11"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""",
    )
    _write(
        repo / "science" / "model" / "src" / "science_model" / "__init__.py",
        'MODEL_SENTINEL = "same-sha-model"\n',
    )
    return repo, _commit(repo)


def _consumer_repo(root: Path, toolkit: Path) -> Path:
    repo = root / "consumer"
    repo.mkdir()
    git_url = toolkit.resolve().as_uri()
    _write(
        repo / "pyproject.toml",
        f"""[project]
name = "consumer"
version = "0.1.0"
requires-python = ">=3.11"

[dependency-groups]
dev = ["science"]

[tool.uv.sources]
science = {{ git = "{git_url}", subdirectory = "science" }}
""",
    )
    _write(
        repo / "tests" / "test_install.py",
        """import unittest

from science_model import MODEL_SENTINEL


class InstallTest(unittest.TestCase):
    def test_nested_model_is_installed(self) -> None:
        self.assertEqual(MODEL_SENTINEL, "same-sha-model")
""",
    )
    _write(
        repo / "validate.sh",
        '#!/usr/bin/env bash\nset -euo pipefail\nexec uv run science validate "$@"\n',
    )
    (repo / "validate.sh").chmod(0o755)
    _write(repo / ".gitignore", ".venv/\n.worktrees/\n")
    _commit(repo)
    return repo


def test_git_source_with_nested_editable_source_runs_in_nested_worktree(tmp_path: Path) -> None:
    toolkit, toolkit_sha = _toolkit_repo(tmp_path)
    consumer = _consumer_repo(tmp_path, toolkit)

    _run("uv", "lock", cwd=consumer)
    lock = tomllib.loads((consumer / "uv.lock").read_text(encoding="utf-8"))
    packages = {package["name"]: package for package in lock["package"]}
    science_source = packages["science"]["source"]["git"]
    model_source = packages["science-model"]["source"]["git"]

    assert f"subdirectory=science#{toolkit_sha}" in science_source
    assert f"subdirectory=science%2Fmodel#{toolkit_sha}" in model_source

    _run("git", "add", "uv.lock", cwd=consumer)
    _run("git", "commit", "-q", "-m", "lock", cwd=consumer)
    worktree = consumer / ".worktrees" / "feature"
    worktree.parent.mkdir()
    _run("git", "worktree", "add", "-q", "-b", "feature", str(worktree), cwd=consumer)

    _run("uv", "sync", "--frozen", cwd=worktree)
    cli = _run("uv", "run", "--frozen", "science", cwd=worktree)
    tests = _run("uv", "run", "--frozen", "python", "-m", "unittest", "discover", "-s", "tests", cwd=worktree)
    validation = _run("bash", "validate.sh", "--verbose", cwd=worktree)

    assert cli.stdout.strip() == "science-fixture:same-sha-model"
    assert "OK" in tests.stderr
    assert validation.stdout.strip() == "validated:same-sha-model"

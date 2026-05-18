"""Tests for science_tool.commons.bootstrap."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.bootstrap import init_commons
from science_tool.commons.errors import CommonsRootMalformedError


def test_init_creates_layout_in_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "new-commons"
    init_commons(root)
    assert root.is_dir()
    assert (root / ".git").is_dir()
    assert (root / ".gitignore").is_file()
    assert (root / "README.md").is_file()
    for sub in ("datasets", "papers", "topics", "themes"):
        assert (root / sub).is_dir()
        assert (root / sub / ".gitkeep").is_file()


def test_gitignore_excludes_registry_but_tracks_migrations(tmp_path: Path) -> None:
    """`.migrations/` must NOT be gitignored — promote commits audit logs there."""
    root = tmp_path / "commons"
    init_commons(root)
    text = (root / ".gitignore").read_text(encoding="utf-8")
    assert "registry.sqlite" in text
    assert ".migrations/" not in text
    assert "__pycache__/" in text


def test_init_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "commons"
    init_commons(root)
    readme_before = (root / "README.md").read_text(encoding="utf-8")
    init_commons(root)  # second call should not modify
    readme_after = (root / "README.md").read_text(encoding="utf-8")
    assert readme_before == readme_after


def test_init_refuses_non_empty_non_commons_dir(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    (root / "some-other-file.txt").write_text("hello")
    with pytest.raises(CommonsRootMalformedError) as exc_info:
        init_commons(root)
    assert "datasets" in exc_info.value.missing or ".git" in exc_info.value.missing


def test_init_force_skips_malformed_check(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    (root / "stray.txt").write_text("hello")
    init_commons(root, force=True)
    # After force-init, stray file is preserved and layout exists:
    assert (root / "stray.txt").is_file()
    assert (root / "datasets").is_dir()
    assert (root / ".git").is_dir()

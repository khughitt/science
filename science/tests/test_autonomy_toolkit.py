from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.autonomy import toolkit as toolkit_module
from science_tool.autonomy.toolkit import (
    ToolkitError,
    assert_gate_is_external,
    assert_toolkit_matches,
    toolkit_is_clean,
    toolkit_revision,
    toolkit_source_root,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root), *args],
        capture_output=True, text=True, check=True,
    )


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "f.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def test_the_toolkit_source_root_holds_the_running_package():
    assert (toolkit_source_root() / "science_tool" / "__init__.py").exists()


def test_the_revision_is_a_full_sha():
    revision = toolkit_revision()
    assert len(revision) == 40
    assert all(c in "0123456789abcdef" for c in revision)


def test_a_clean_checkout_reads_clean(clean_repo: Path):
    assert toolkit_is_clean(clean_repo) is True


def test_a_modified_tracked_file_makes_the_checkout_dirty(clean_repo: Path):
    (clean_repo / "f.txt").write_text("b\n", encoding="utf-8")
    assert toolkit_is_clean(clean_repo) is False


def test_an_untracked_file_makes_the_checkout_dirty(clean_repo: Path):
    """An untracked module is still importable, so it still judges the run. HEAD would
    report the same sha either way."""
    (clean_repo / "new.py").write_text("x = 1\n", encoding="utf-8")
    assert toolkit_is_clean(clean_repo) is False


def test_a_dirty_toolkit_is_refused_even_when_the_revision_matches(
    monkeypatch: pytest.MonkeyPatch,
):
    """The whole point: HEAD is unchanged by uncommitted edits, so revision equality
    passes while the code that rendered the verdict is not the code the record names."""
    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: False)
    with pytest.raises(ToolkitError, match="uncommitted"):
        assert_toolkit_matches(toolkit_revision())


def test_a_project_that_does_not_contain_the_toolkit_passes(tmp_path: Path):
    assert_gate_is_external(tmp_path)  # does not raise


def test_a_project_containing_the_running_toolkit_is_refused():
    """Design §0 / test #7: a run that edits toolkit code must not be able to alter the
    code that judges it. If the executing science lives inside the run's tree, it can."""
    inside = toolkit_source_root().parent
    with pytest.raises(ToolkitError):
        assert_gate_is_external(inside)


def test_a_mismatched_revision_is_refused(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: True)
    with pytest.raises(ToolkitError, match="moved during the run"):
        assert_toolkit_matches("0" * 40)


def test_the_recorded_revision_matches_itself(monkeypatch: pytest.MonkeyPatch):
    """Cleanliness is forced here: the checkout this test runs in is dirty exactly while
    this plan is being implemented, and that is not what this test is about."""
    monkeypatch.setattr(toolkit_module, "toolkit_is_clean", lambda root=None: True)
    assert_toolkit_matches(toolkit_revision())  # does not raise

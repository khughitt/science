# science/tests/test_text_scan.py
"""The scannable-text surface: never hand a PNG to a UTF-8 read."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from science_tool.text_scan import (
    MAX_SCANNABLE_BYTES,
    TEXT_SUFFIXES,
    iter_scannable_files,
    read_text_or_skip,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\xfd"


def test_binary_file_is_not_scannable(tmp_path: Path) -> None:
    (tmp_path / "img.png").write_bytes(PNG_MAGIC)
    (tmp_path / "a.md").write_text("# hi\n", encoding="utf-8")

    names = {p.name for p in iter_scannable_files(tmp_path)}

    assert "a.md" in names
    assert "img.png" not in names


def test_code_files_are_scannable() -> None:
    """Code carries path references; it must be SEEN even though it is never rewritten."""
    for suffix in (".py", ".ts", ".tsx", ".js"):
        assert suffix in TEXT_SUFFIXES


def test_undecodable_bytes_report_a_skip(tmp_path: Path) -> None:
    path = tmp_path / "weird.md"
    path.write_bytes(b"\xff\xfe\x00\x00not utf8")

    text, skip = read_text_or_skip(path, "weird.md")

    assert text is None
    assert skip is not None
    assert skip.rel_path == "weird.md"
    assert "utf-8" in skip.reason.lower()


def test_unreadable_file_reports_a_skip_not_a_clean_read(tmp_path: Path) -> None:
    """An OSError must never be indistinguishable from a file with no references."""
    path = tmp_path / "locked.md"
    path.write_text("see doc/plans/old.md\n", encoding="utf-8")
    path.chmod(0o000)
    try:
        text, skip = read_text_or_skip(path, "locked.md")
    finally:
        path.chmod(0o644)

    assert text is None
    assert skip is not None
    assert skip.rel_path == "locked.md"


def test_read_text_or_skip_returns_text(tmp_path: Path) -> None:
    path = tmp_path / "a.md"
    path.write_text("# hi\n", encoding="utf-8")

    assert read_text_or_skip(path, "a.md") == ("# hi\n", None)


def test_skip_dirs_are_honoured(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "readme.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "keep.md").write_text("x\n", encoding="utf-8")

    names = {p.name for p in iter_scannable_files(tmp_path)}

    assert names == {"keep.md"}


def test_project_walk_prunes_skipped_directories_and_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.project_walk import iter_project_files

    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.md").write_text("hidden\n", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "worktrees").write_text("hidden\n", encoding="utf-8")
    keep = tmp_path / "keep.md"
    keep.write_text("keep\n", encoding="utf-8")

    real_scandir = os.scandir
    scanned_directories: list[Path] = []

    def recording_scandir(path: str | bytes | os.PathLike[str] | os.PathLike[bytes]):
        scanned_directories.append(Path(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", recording_scandir)

    assert iter_project_files(tmp_path) == [keep]
    assert tmp_path / ".git" not in scanned_directories


def test_project_walk_filters_suffix_before_file_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.project_walk import iter_project_files

    keep = tmp_path / "keep.md"
    keep.write_text("keep\n", encoding="utf-8")
    skipped = tmp_path / "skip.bin"
    skipped.write_bytes(b"binary")
    real_is_file = Path.is_file

    def guarded_is_file(path: Path) -> bool:
        if path == skipped:
            raise AssertionError("suffix filtering happened after stat")
        return real_is_file(path)

    monkeypatch.setattr(Path, "is_file", guarded_is_file)

    assert iter_project_files(tmp_path, suffixes=frozenset({".md"})) == [keep]


def test_project_walk_does_not_follow_directory_symlinks(tmp_path: Path) -> None:
    from science_tool.project_walk import iter_project_files

    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "target.md"
    target.write_text("target\n", encoding="utf-8")
    hidden = outside / "hidden.md"
    hidden.write_text("hidden\n", encoding="utf-8")
    link_to_file = project / "link.md"
    link_to_directory = project / "linked-directory"
    try:
        link_to_file.symlink_to(target)
        link_to_directory.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")

    files = iter_project_files(project)

    assert link_to_file in files
    assert all(path.name != "hidden.md" for path in files)


def test_tool_managed_dirs_are_skipped(tmp_path: Path) -> None:
    """A Snakemake working dir and the `.ai/` agent-scaffolding tree are tool-managed, not project
    reference surfaces. A `spec:`/link token vendored inside `.snakemake/conda/...` (a real cbioportal
    false positive) or a placeholder in `.ai/templates/` must never be scanned as a referrer."""
    (tmp_path / ".snakemake/conda/env/lib").mkdir(parents=True)
    (tmp_path / ".snakemake/conda/env/lib/test_common.py").write_text("open('spec://x')\n", encoding="utf-8")
    (tmp_path / ".ai/templates").mkdir(parents=True)
    (tmp_path / ".ai/templates/gene-note.md").write_text("---\nsymbol: '{{SYMBOL}}'\n---\n", encoding="utf-8")
    (tmp_path / "keep.md").write_text("x\n", encoding="utf-8")

    names = {p.name for p in iter_scannable_files(tmp_path)}

    assert names == {"keep.md"}


def test_oversize_file_is_not_scannable(tmp_path: Path, monkeypatch) -> None:
    """A hundreds-of-MB data file or generated artifact is not a prose reference
    site. Reading it to scan for links is what made a corpus-wide import balloon
    to tens of GB of RSS on a data-bearing repo. It is excluded here for the same
    reason the suffix allowlist exists -- categorically not a reference site --
    not decoded-then-skipped, because the read is the harm.
    """
    monkeypatch.setattr("science_tool.text_scan.MAX_SCANNABLE_BYTES", 16)
    (tmp_path / "data.json").write_bytes(b"x" * 64)  # over the (patched) cap
    (tmp_path / "keep.md").write_text("# hi\n", encoding="utf-8")  # under it

    names = {p.name for p in iter_scannable_files(tmp_path)}

    assert "keep.md" in names
    assert "data.json" not in names


def test_file_at_the_cap_is_still_scannable(tmp_path: Path, monkeypatch) -> None:
    """The cap is a ceiling well above any hand-authored reference file; a file
    exactly at it is still scanned, so the guard never clips a genuine source."""
    monkeypatch.setattr("science_tool.text_scan.MAX_SCANNABLE_BYTES", 16)
    (tmp_path / "edge.json").write_bytes(b"x" * 16)  # exactly at the cap

    names = {p.name for p in iter_scannable_files(tmp_path)}

    assert "edge.json" in names


def test_default_cap_clears_the_largest_plausible_source() -> None:
    """The real ceiling must sit above a canonical source (the largest here is a
    ~0.8 MB knowledge yaml), so the guard only ever excludes data and artifacts."""
    assert MAX_SCANNABLE_BYTES >= 1024 * 1024


def test_scans_the_real_repository_and_covers_its_python() -> None:
    """The regression synthetic fixtures cannot catch.

    "Does not raise" is too weak: a scan that returned [] would pass it. Assert
    positive coverage of a file class known to exist here.
    """
    repo = Path(__file__).resolve().parents[2]
    files = iter_scannable_files(repo)
    assert files, "scanned nothing"

    rels = {p.relative_to(repo).as_posix() for p in files}
    assert "science/src/science_tool/entities.py" in rels, "own source not scanned"

    skips = [skip for p in files if (skip := read_text_or_skip(p, p.name)[1]) is not None]
    assert skips == [], f"unexpected skips in a clean checkout: {skips}"

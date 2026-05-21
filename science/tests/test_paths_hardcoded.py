from pathlib import Path

import pytest

from science_tool.paths import resolve_paths


def test_hardcoded_path_patterns_parsed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nhardcoded_path_patterns:\n  - /data/proj/mm30/\n  - /scratch/\n",
        encoding="utf-8",
    )
    paths = resolve_paths(tmp_path)
    assert paths.hardcoded_path_patterns == ("/data/proj/mm30/", "/scratch/")


def test_hardcoded_path_patterns_default_empty(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    assert resolve_paths(tmp_path).hardcoded_path_patterns == ()


def test_hardcoded_path_patterns_must_be_list_of_strings(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nhardcoded_path_patterns: nope\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hardcoded_path_patterns"):
        resolve_paths(tmp_path)

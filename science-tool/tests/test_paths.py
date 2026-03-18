from pathlib import Path

import pytest

from science_tool.paths import resolve_paths


def test_defaults_to_research_profile_when_no_yaml(tmp_path: Path) -> None:
    paths = resolve_paths(tmp_path)
    assert paths.profile == "research"
    assert paths.doc_dir == tmp_path / "doc"
    assert paths.code_dir == tmp_path / "code"
    assert paths.templates_dir == tmp_path / ".ai/templates"
    assert paths.prompts_dir == tmp_path / ".ai/prompts"
    assert paths.knowledge_dir == tmp_path / "knowledge"
    assert paths.tasks_dir == tmp_path / "tasks"


def test_research_profile_uses_canonical_execution_roots(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\nstatus: active\nprofile: research\n", encoding="utf-8")
    paths = resolve_paths(tmp_path)
    assert paths.profile == "research"
    assert paths.code_dir == tmp_path / "code"
    assert paths.doc_dir == tmp_path / "doc"
    assert paths.papers_dir == tmp_path / "papers"


def test_software_profile_uses_src_for_code_dir(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\nstatus: active\nprofile: software\n", encoding="utf-8")
    paths = resolve_paths(tmp_path)
    assert paths.profile == "software"
    assert paths.code_dir == tmp_path / "src"
    assert paths.doc_dir == tmp_path / "doc"
    assert paths.tasks_dir == tmp_path / "tasks"


def test_invalid_profile_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\nstatus: active\nprofile: hybrid\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported project profile"):
        resolve_paths(tmp_path)

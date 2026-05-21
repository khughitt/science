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


def test_code_roots_default_to_profile_code_dir(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\nprofile: research\n", encoding="utf-8")
    paths = resolve_paths(tmp_path)
    assert paths.code_roots == (tmp_path / "code",)
    assert paths.app_roots == ()
    assert paths.code_excludes == ()
    assert paths.code_dir == tmp_path / "code"


def test_declared_code_app_roots_and_excludes(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\n"
        "code_roots:\n  - code\n  - scripts\n"
        "app_roots:\n  - app\n"
        "code_excludes:\n  - '**/vendor/**'\n",
        encoding="utf-8",
    )
    paths = resolve_paths(tmp_path)
    assert paths.code_roots == (tmp_path / "code", tmp_path / "scripts")
    assert paths.app_roots == (tmp_path / "app",)
    assert paths.code_excludes == ("**/vendor/**",)
    assert paths.code_dir == tmp_path / "code"  # first declared root is canonical


def test_code_roots_must_be_list_of_strings(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots: code\n", encoding="utf-8")
    with pytest.raises(ValueError, match="code_roots must be a list of strings"):
        resolve_paths(tmp_path)


def test_absolute_or_escaping_roots_rejected(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots:\n  - /etc\n", encoding="utf-8")
    with pytest.raises(ValueError, match="relative paths inside the project"):
        resolve_paths(tmp_path)


def test_parent_escaping_root_rejected(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots:\n  - ../sibling\n", encoding="utf-8")
    with pytest.raises(ValueError, match="relative paths inside the project"):
        resolve_paths(tmp_path)


def test_nested_roots_rejected(tmp_path: Path) -> None:
    # A root nested under another would discover the same file twice -> id collision.
    (tmp_path / "science.yaml").write_text(
        "name: t\ncode_roots:\n  - code\n  - code/stages\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="must not be nested"):
        resolve_paths(tmp_path)


def test_empty_root_rejected(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots:\n  - ''\n", encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty"):
        resolve_paths(tmp_path)


def test_duplicate_roots_deduplicated(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\ncode_roots:\n  - code\n  - code\n", encoding="utf-8")
    assert resolve_paths(tmp_path).code_roots == (tmp_path / "code",)

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from science_tool.validate import ValidateContext
from science_tool.validate.context import ValidateContextError


def _project(root: Path) -> Path:
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    return root


def test_context_loads_manifest_and_default_directories(tmp_path: Path) -> None:
    ctx = ValidateContext.from_project_root(_project(tmp_path), strict=True, verbose=False)

    assert ctx.project_root == tmp_path.resolve()
    assert ctx.doc_dir == tmp_path / "doc"
    assert ctx.specs_dir == tmp_path / "specs"
    assert ctx.papers_dir == tmp_path / "doc" / "papers"
    assert ctx.provenance_dir == tmp_path / "doc" / "provenance"
    assert ctx.themes_dir == tmp_path / "doc" / "themes"
    assert ctx.manifest == {"name": "demo"}
    assert ctx.strict is True
    assert ctx.verbose is False


def test_context_requires_science_yaml(tmp_path: Path) -> None:
    with pytest.raises(ValidateContextError, match="science.yaml not found"):
        ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)


def test_read_text_cached_reuses_value_for_same_absolute_path_and_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = ValidateContext.from_project_root(_project(tmp_path), strict=False, verbose=False)
    path = tmp_path / "doc.md"
    path.write_text("hello", encoding="utf-8")
    calls = 0

    def counted_read_text(self: Path, *args: object, **kwargs: object) -> str:
        nonlocal calls
        calls += 1
        return "hello"

    monkeypatch.setattr(Path, "read_text", counted_read_text)

    assert ctx.read_text_cached(path) == "hello"
    assert ctx.read_text_cached(path) == "hello"
    assert calls == 1


def test_read_yaml_reuses_parsed_value_for_same_absolute_path_and_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = ValidateContext.from_project_root(_project(tmp_path), strict=False, verbose=False)
    yaml_path = tmp_path / "data.yaml"
    yaml_path.write_text("answer: 42\n", encoding="utf-8")
    calls = 0
    original_safe_load = yaml.safe_load

    def counted_safe_load(stream: Any) -> Any:
        nonlocal calls
        calls += 1
        return original_safe_load(stream)

    monkeypatch.setattr("science_tool.validate.context.yaml.safe_load", counted_safe_load)

    assert ctx.read_yaml(yaml_path) == {"answer": 42}
    assert ctx.read_yaml(yaml_path) == {"answer": 42}
    assert calls == 1


def test_frontmatter_reuses_parsed_value_for_same_absolute_path_and_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = ValidateContext.from_project_root(_project(tmp_path), strict=False, verbose=False)
    md_path = tmp_path / "note.md"
    md_path.write_text("---\ntitle: Demo\n---\nBody\n", encoding="utf-8")
    calls = 0
    original_safe_load = yaml.safe_load

    def counted_safe_load(stream: Any) -> Any:
        nonlocal calls
        calls += 1
        return original_safe_load(stream)

    monkeypatch.setattr("science_tool.validate.context.yaml.safe_load", counted_safe_load)

    assert ctx.frontmatter(md_path) == {"title": "Demo"}
    assert ctx.frontmatter(md_path) == {"title": "Demo"}
    assert calls == 1

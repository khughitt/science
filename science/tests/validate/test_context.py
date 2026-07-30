from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml

from science_tool.validate import ValidateContext
from science_tool.validate.context import ValidateContextError
from science_tool.graph.sources import (
    ProjectSources,
    SkippedEntity,
    enforce_project_source_strictness,
)


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


def test_project_sources_loads_once_per_commons_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = ValidateContext.from_project_root(_project(tmp_path), strict=False, verbose=False)
    loaded = cast(
        ProjectSources,
        SimpleNamespace(skipped_entities=[], arbitration_errors=[]),
    )
    calls: list[bool] = []

    def counted_load_project_sources(project_root: Path, **kwargs: Any) -> ProjectSources:
        assert project_root == ctx.project_root
        calls.append(kwargs["include_commons"])
        assert kwargs["strict_core_schema"] is False
        assert kwargs["strict_identity"] is False
        return loaded

    monkeypatch.setattr("science_tool.graph.sources.load_project_sources", counted_load_project_sources)

    for strict_core_schema in (False, True):
        for strict_identity in (False, True):
            assert (
                ctx.project_sources(
                    include_commons=True,
                    strict_core_schema=strict_core_schema,
                    strict_identity=strict_identity,
                )
                is loaded
            )
    assert (
        ctx.project_sources(
            include_commons=False,
            strict_core_schema=False,
            strict_identity=False,
        )
        is loaded
    )
    assert calls == [True, False]


def test_project_source_strictness_projects_recorded_schema_failure() -> None:
    sources = cast(
        ProjectSources,
        SimpleNamespace(
            skipped_entities=[
                SkippedEntity(
                    path="entities/questions/bad.md",
                    kind="question",
                    reason="core_schema_validation_failed",
                    details="missing required field 'title'",
                )
            ],
            arbitration_errors=[],
        ),
    )

    assert (
        enforce_project_source_strictness(
            sources,
            strict_core_schema=False,
            strict_identity=False,
        )
        is sources
    )
    with pytest.raises(
        ValueError,
        match=(
            "schema validation failed for registered entity kind 'question' "
            "at entities/questions/bad.md: missing required field 'title'"
        ),
    ):
        enforce_project_source_strictness(
            sources,
            strict_core_schema=True,
            strict_identity=False,
        )


def test_graph_dataset_reuses_parsed_trig_for_same_path_and_mtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = ValidateContext.from_project_root(_project(tmp_path), strict=False, verbose=False)
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text("@prefix ex: <http://example.org/> .\n", encoding="utf-8")
    calls = 0

    from science_tool.graph.store import dataset as dataset_module

    original_load_dataset = dataset_module._load_dataset

    def counted_load_dataset(path: Path):
        nonlocal calls
        calls += 1
        return original_load_dataset(path)

    monkeypatch.setattr(dataset_module, "_load_dataset", counted_load_dataset)

    assert ctx.graph_dataset(graph_path) is ctx.graph_dataset(graph_path)
    assert calls == 1

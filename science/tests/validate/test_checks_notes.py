from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from science_tool.validate import Result, Severity, ValidateContext


def _write_manifest(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _messages(results: Iterable[Result]) -> list[str]:
    return [result.message for result in results]


def _valid_note(note_type: str, *, note_id: str | None = None, datasets: str | None = None) -> str:
    fields = [
        f"id: {note_id or f'{note_type}:demo'}",
        f"type: {note_type}",
        "title: Demo",
        "status: draft",
        "tags: []",
        "ontology_terms: []",
        "source_refs: []",
        "related: []",
        "created: 2026-01-01",
        "updated: 2026-01-02",
    ]
    if datasets is not None:
        fields.append(datasets)
    return "\n".join(
        [
            "---",
            *fields,
            "---",
            "## Summary",
            "## Thoughts",
            "## Connections to Project",
            "## Related",
        ]
    )


def _write_note(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_notes_absent_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    assert list(check_notes(_ctx(tmp_path))) == []


def test_notes_index_missing_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    (tmp_path / "notes").mkdir()

    assert _messages(check_notes(_ctx(tmp_path))) == ["notes/index.md missing — add a notes coverage index"]


def test_notes_scan_order_is_deterministic_and_emits_info(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(tmp_path, "notes/topics/b.md", _valid_note("topic"))
    _write_note(tmp_path, "notes/topics/a.md", _valid_note("topic"))
    _write_note(tmp_path, "notes/articles/a.md", _valid_note("article"))
    _write_note(tmp_path, "notes/questions/a.md", _valid_note("question"))
    _write_note(tmp_path, "notes/methods/a.md", _valid_note("method"))
    _write_note(tmp_path, "notes/datasets/a.md", _valid_note("dataset"))

    info_messages = [result.message for result in check_notes(_ctx(tmp_path)) if result.severity is Severity.INFO]

    assert info_messages == [
        "Checking notes/topics/a.md...",
        "Checking notes/topics/b.md...",
        "Checking notes/articles/a.md...",
        "Checking notes/questions/a.md...",
        "Checking notes/methods/a.md...",
        "Checking notes/datasets/a.md...",
    ]


def test_missing_frontmatter_start_warns_and_skips_file(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(tmp_path, "notes/topics/a.md", "id: topic:a\n")

    assert _messages(check_notes(_ctx(tmp_path))) == [
        "Checking notes/topics/a.md...",
        "notes/topics/a.md missing YAML frontmatter start marker (---)",
    ]


def test_missing_frontmatter_end_warns_and_skips_file(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(tmp_path, "notes/topics/a.md", "---\nid: topic:a\n")

    assert _messages(check_notes(_ctx(tmp_path))) == [
        "Checking notes/topics/a.md...",
        "notes/topics/a.md missing YAML frontmatter end marker (---)",
    ]


def test_missing_required_frontmatter_fields_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(
        tmp_path,
        "notes/topics/a.md",
        "\n".join(["---", "id: topic:a", "type: topic", "---", "## Summary"]),
    )

    messages = _messages(check_notes(_ctx(tmp_path)))

    for field in ("title", "status", "tags", "ontology_terms", "source_refs", "related", "created", "updated"):
        assert f"notes/topics/a.md frontmatter missing field: {field}" in messages


def test_datasets_accepts_bare_key_inline_array_and_block_list(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(tmp_path, "notes/topics/bare.md", _valid_note("topic", datasets="datasets:"))
    _write_note(tmp_path, "notes/topics/inline.md", _valid_note("topic", datasets="datasets: [a, b]"))
    _write_note(
        tmp_path,
        "notes/topics/block.md",
        _valid_note("topic", datasets="\n".join(["datasets:", "  - a"])),
    )

    messages = _messages(check_notes(_ctx(tmp_path)))

    assert not any(message.endswith("datasets field should be an array/list") for message in messages)


def test_scalar_datasets_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(tmp_path, "notes/topics/a.md", _valid_note("topic", datasets="datasets: scalar"))

    assert "notes/topics/a.md datasets field should be an array/list" in _messages(check_notes(_ctx(tmp_path)))


def test_type_mismatch_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(tmp_path, "notes/topics/a.md", _valid_note("article", note_id="topic:a"))

    assert "notes/topics/a.md type 'article' does not match expected 'topic'" in _messages(check_notes(_ctx(tmp_path)))


def test_quoted_type_mismatch_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(
        tmp_path,
        "notes/topics/a.md",
        _valid_note("article", note_id="topic:a").replace("type: article", 'type: "article"'),
    )

    assert "notes/topics/a.md type 'article' does not match expected 'topic'" in _messages(check_notes(_ctx(tmp_path)))


def test_id_prefix_mismatch_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(tmp_path, "notes/topics/a.md", _valid_note("topic", note_id="article:a"))

    assert "notes/topics/a.md id 'article:a' should start with 'topic:'" in _messages(check_notes(_ctx(tmp_path)))


def test_quoted_id_prefix_mismatch_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(
        tmp_path,
        "notes/topics/a.md",
        _valid_note("topic", note_id="article:a").replace("id: article:a", "id: 'article:a'"),
    )

    assert "notes/topics/a.md id 'article:a' should start with 'topic:'" in _messages(check_notes(_ctx(tmp_path)))


def test_missing_common_sections_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(
        tmp_path,
        "notes/topics/a.md",
        "\n".join(
            [
                "---",
                "id: topic:a",
                "type: topic",
                "title: Demo",
                "status: draft",
                "tags: []",
                "ontology_terms: []",
                "source_refs: []",
                "related: []",
                "created: 2026-01-01",
                "updated: 2026-01-02",
                "---",
            ]
        ),
    )

    messages = _messages(check_notes(_ctx(tmp_path)))

    for section in ("## Summary", "## Thoughts", "## Connections to Project", "## Related"):
        assert f"notes/topics/a.md missing section: {section}" in messages


def test_complete_valid_note_emits_only_info(tmp_path: Path) -> None:
    from science_tool.validate.checks.notes import check_notes

    _write_note(tmp_path, "notes/index.md", "# Notes\n")
    _write_note(tmp_path, "notes/topics/a.md", _valid_note("topic"))

    assert [(result.severity, result.message) for result in check_notes(_ctx(tmp_path))] == [
        (Severity.INFO, "Checking notes/topics/a.md...")
    ]


def test_canonical_loader_imports_notes_after_bias_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    import science_tool.validate.checks as checks

    loaded_modules: list[str] = []

    def record_import(module_name: str) -> None:
        loaded_modules.append(module_name)

    monkeypatch.setattr(checks.importlib, "import_module", record_import)

    checks._load_canonical_checks()

    assert "science_tool.validate.checks.bias_audits" in loaded_modules
    assert "science_tool.validate.checks.notes" in loaded_modules
    assert loaded_modules.index("science_tool.validate.checks.notes") == (
        loaded_modules.index("science_tool.validate.checks.bias_audits") + 1
    )

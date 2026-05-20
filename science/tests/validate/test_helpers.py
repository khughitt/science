from __future__ import annotations

from pathlib import Path

from science_tool.validate import ValidateContext
from science_tool.validate._helpers import parse_frontmatter_document, resolve_reference, section_banner


def _project(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_parse_frontmatter_document_returns_frontmatter_and_body(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    path = tmp_path / "doc" / "note.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nid: question:q01\ntags:\n  - demo\n---\n\nBody\n", encoding="utf-8")

    frontmatter, body = parse_frontmatter_document(ctx, path)

    assert frontmatter == {"id": "question:q01", "tags": ["demo"]}
    assert body == "\nBody\n"


def test_parse_frontmatter_document_returns_empty_frontmatter_without_delimiters(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    path = tmp_path / "doc" / "note.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Heading\n\nBody\n", encoding="utf-8")

    assert parse_frontmatter_document(ctx, path) == ({}, "# Heading\n\nBody\n")


def test_parse_frontmatter_document_returns_full_text_when_closing_delimiter_is_missing(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    path = tmp_path / "doc" / "note.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\ntitle: Demo\nBody\n", encoding="utf-8")

    assert parse_frontmatter_document(ctx, path) == ({}, "---\ntitle: Demo\nBody\n")


def test_parse_frontmatter_document_returns_empty_frontmatter_for_non_mapping_yaml(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    path = tmp_path / "doc" / "note.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\n- not\n- mapping\n---\nBody\n", encoding="utf-8")

    assert parse_frontmatter_document(ctx, path) == ({}, "Body\n")


def test_resolve_reference_finds_frontmatter_id_in_doc_or_specs(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    doc_path = tmp_path / "doc" / "questions" / "q01.md"
    specs_path = tmp_path / "specs" / "hypotheses" / "h01.md"
    doc_path.parent.mkdir(parents=True)
    specs_path.parent.mkdir(parents=True)
    doc_path.write_text("---\nid: question:q01\n---\nQuestion\n", encoding="utf-8")
    specs_path.write_text("---\nid: hypothesis:h01\n---\nHypothesis\n", encoding="utf-8")

    assert resolve_reference(ctx, "question:q01") == doc_path
    assert resolve_reference(ctx, "hypothesis:h01") == specs_path


def test_resolve_reference_falls_back_to_doc_paper_slug(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    paper_path = tmp_path / "doc" / "papers" / "Foo2024.md"
    paper_path.parent.mkdir(parents=True)
    paper_path.write_text("# Paper\n", encoding="utf-8")

    assert resolve_reference(ctx, "paper:Foo2024") == paper_path


def test_resolve_reference_rejects_unsafe_paper_fallback_slugs(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    escape_path = tmp_path / "doc" / "some-doc.md"
    nested_path = tmp_path / "doc" / "papers" / "subdir" / "name.md"
    escape_path.parent.mkdir(parents=True)
    nested_path.parent.mkdir(parents=True)
    escape_path.write_text("# Escape\n", encoding="utf-8")
    nested_path.write_text("# Nested\n", encoding="utf-8")

    assert resolve_reference(ctx, "paper:../some-doc") is None
    assert resolve_reference(ctx, "paper:subdir/name") is None


def test_resolve_reference_resolves_cite_key_to_bibliography(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    bib_path = tmp_path / "papers" / "references.bib"
    bib_path.parent.mkdir(parents=True)
    bib_path.write_text("@article{Bar2023,\n  title = {Demo}\n}\n", encoding="utf-8")

    assert resolve_reference(ctx, "cite:Bar2023") == bib_path
    assert resolve_reference(ctx, "cite:Missing2024") is None


def test_resolve_reference_resolves_task_id_and_bare_task_id(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    active_path = tmp_path / "tasks" / "active.md"
    done_path = tmp_path / "tasks" / "done" / "archive.md"
    active_path.parent.mkdir(parents=True)
    done_path.parent.mkdir(parents=True)
    active_path.write_text("# Active\n\n## [t012] Active task\n", encoding="utf-8")
    done_path.write_text("# Done\n\n## [t099] Done task\n", encoding="utf-8")

    assert resolve_reference(ctx, "task:t012") == active_path
    assert resolve_reference(ctx, "t099") == done_path
    assert resolve_reference(ctx, "task:t404") is None


def test_resolve_reference_resolves_long_task_ids_with_flexible_heading_whitespace(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    active_path = tmp_path / "tasks" / "active.md"
    active_path.parent.mkdir(parents=True)
    active_path.write_text("# Active\n\n##   [t1000] Long task\n", encoding="utf-8")

    assert resolve_reference(ctx, "task:t1000") == active_path
    assert resolve_reference(ctx, "t1000") == active_path


def test_resolve_reference_does_not_treat_three_part_refs_as_local_frontmatter_ids(tmp_path: Path) -> None:
    ctx = _project(tmp_path)
    path = tmp_path / "doc" / "questions" / "q01.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nid: peer:question:q01\n---\nQuestion\n", encoding="utf-8")

    assert resolve_reference(ctx, "peer:question:q01") is None


def test_section_banner_formats_checking_line() -> None:
    assert section_banner("demo...") == "Checking demo..."

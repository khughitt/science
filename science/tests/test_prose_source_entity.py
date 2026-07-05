from datetime import date

import yaml

from science_tool.annotation.prose_source_entity import resolve_or_create_prose_source


def test_resolver_creates_missing_prose_source(tmp_path):
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir()
    source.write_text("# Example\n", encoding="utf-8")

    result = resolve_or_create_prose_source(
        project_root=tmp_path,
        slug="example",
        title="Example",
        source_path=source,
        content_hash="sha256:" + "1" * 64,
        artifact_id="decomp-1",
        today=date(2026, 6, 18),
    )

    path = tmp_path / "entities" / "prose-sources" / "example.md"
    assert result.entity_id == "prose-source:example"
    assert result.path == path
    assert result.created is True
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["source_path"] == "docs/example.md"
    assert frontmatter["content_hash"] == "sha256:" + "1" * 64
    assert frontmatter["latest_decomposition_artifact"] == "decomp-1"
    assert frontmatter["updated"] == "2026-06-18"


def test_resolver_preserves_authored_notes(tmp_path):
    path = tmp_path / "entities" / "prose-sources"
    path.mkdir(parents=True)
    existing = path / "example.md"
    existing.write_text(
        "---\n"
        "id: prose-source:example\n"
            "kind: prose-source\n"
        "title: Example\n"
        "status: active\n"
        "source_path: old.md\n"
        "content_hash: sha256:old\n"
        "latest_decomposition_artifact: old\n"
        "source_refs: []\n"
        "related: []\n"
        "created: '2026-06-18'\n"
        "updated: '2026-06-18'\n"
        "---\n"
        "# Example\n\n## Source\n\n## Notes\n\nCurated note.\n",
        encoding="utf-8",
    )
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir()
    source.write_text("# Example\n", encoding="utf-8")

    result = resolve_or_create_prose_source(
        project_root=tmp_path,
        slug="example",
        title="Example Changed",
        source_path=source,
        content_hash="sha256:" + "2" * 64,
        artifact_id="decomp-2",
        today=date(2026, 6, 19),
    )

    text = existing.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert result.created is False
    assert "Curated note." in text
    assert frontmatter["title"] == "Example"
    assert frontmatter["status"] == "active"
    assert frontmatter["source_path"] == "docs/example.md"
    assert frontmatter["content_hash"] == "sha256:" + "2" * 64
    assert frontmatter["latest_decomposition_artifact"] == "decomp-2"
    assert frontmatter["source_refs"] == []
    assert frontmatter["related"] == []
    assert frontmatter["created"] == "2026-06-18"
    assert frontmatter["updated"] == "2026-06-19"


def test_resolver_displays_missing_project_paths_and_outside_paths(tmp_path):
    missing_source = tmp_path / "docs" / "missing.md"

    resolve_or_create_prose_source(
        project_root=tmp_path,
        slug="missing",
        title="Missing",
        source_path=missing_source,
        content_hash="sha256:" + "3" * 64,
        artifact_id="decomp-3",
        today=date(2026, 6, 18),
    )

    missing_entity = tmp_path / "entities" / "prose-sources" / "missing.md"
    text = missing_entity.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["source_path"] == "docs/missing.md"

    outside_path = tmp_path.parent / "outside.md"

    resolve_or_create_prose_source(
        project_root=tmp_path,
        slug="outside",
        title="Outside",
        source_path=outside_path,
        content_hash="sha256:" + "4" * 64,
        artifact_id="decomp-4",
        today=date(2026, 6, 18),
    )

    outside_entity = tmp_path / "entities" / "prose-sources" / "outside.md"
    text = outside_entity.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["source_path"] == str(outside_path)


def test_resolver_uses_project_relative_path_for_non_science_project_root(tmp_path):
    project_root = tmp_path / "natural-systems"
    source = project_root / "entities" / "discussions" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Example\n", encoding="utf-8")

    resolve_or_create_prose_source(
        project_root=project_root,
        slug="example",
        title="Example",
        source_path=source,
        content_hash="sha256:" + "5" * 64,
        artifact_id="decomp-5",
        today=date(2026, 6, 19),
    )

    entity = project_root / "entities" / "prose-sources" / "example.md"
    frontmatter = yaml.safe_load(entity.read_text(encoding="utf-8").split("---", 2)[1])
    assert frontmatter["source_path"] == "entities/discussions/example.md"

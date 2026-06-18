from pathlib import Path

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
    )

    path = tmp_path / "entities" / "prose-sources" / "example.md"
    assert result.entity_id == "prose-source:example"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["source_path"]
    assert frontmatter["content_hash"] == "sha256:" + "1" * 64
    assert frontmatter["latest_decomposition_artifact"] == "decomp-1"


def test_resolver_preserves_authored_notes(tmp_path):
    path = tmp_path / "entities" / "prose-sources"
    path.mkdir(parents=True)
    existing = path / "example.md"
    existing.write_text(
        "---\n"
        "id: prose-source:example\n"
        "type: prose-source\n"
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

    resolve_or_create_prose_source(
        project_root=tmp_path,
        slug="example",
        title="Example Changed",
        source_path=source,
        content_hash="sha256:" + "2" * 64,
        artifact_id="decomp-2",
    )

    text = existing.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert "Curated note." in text
    assert frontmatter["title"] == "Example"
    assert frontmatter["content_hash"] == "sha256:" + "2" * 64
    assert frontmatter["latest_decomposition_artifact"] == "decomp-2"

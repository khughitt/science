from pathlib import Path

from science_model.frontmatter import parse_entity_file, parse_frontmatter


def test_parse_frontmatter_basic(tmp_path: Path):
    md = tmp_path / "test.md"
    md.write_text("""---
id: "hypothesis:h01-test"
type: hypothesis
title: "Test hypothesis"
status: proposed
tags: [genomics, ml]
ontology_terms: ["GO:0006915"]
created: 2026-03-01
updated: 2026-03-10
related: ["question:q01"]
source_refs: []
---

This is the body content of the hypothesis.

## Rationale

Some rationale here.
""")
    result = parse_frontmatter(md)
    assert result is not None
    fm, body = result
    assert fm["id"] == "hypothesis:h01-test"
    assert fm["type"] == "hypothesis"
    assert fm["tags"] == ["genomics", "ml"]
    assert "This is the body content" in body


def test_parse_frontmatter_missing_file(tmp_path: Path):
    result = parse_frontmatter(tmp_path / "nonexistent.md")
    assert result is None


def test_parse_entity_file(tmp_path: Path):
    md = tmp_path / "test.md"
    md.write_text("""---
id: "question:q01-test"
type: question
title: "What is X?"
status: open
tags: []
created: 2026-03-01
---

Body text here.
""")
    entity = parse_entity_file(md, project_slug="my-project")
    assert entity is not None
    assert entity.id == "question:q01-test"
    assert entity.type.value == "question"
    assert entity.project == "my-project"
    assert entity.content_preview == "Body text here."


def test_parse_entity_file_infers_type_from_id_prefix(tmp_path: Path):
    """When type is missing but id has a recognized prefix, infer the type."""
    md = tmp_path / "h01.md"
    md.write_text("""---
id: "hypothesis:h01-test"
title: "Hypothesis without explicit type"
status: proposed
tags: []
created: 2026-03-01
---

Body text.
""")
    entity = parse_entity_file(md, project_slug="test-project")
    assert entity is not None
    assert entity.type.value == "hypothesis"
    assert entity.id == "hypothesis:h01-test"


def test_parse_entity_file_returns_none_without_type_or_id(tmp_path: Path):
    """Files with neither type nor a recognizable id prefix are skipped."""
    md = tmp_path / "plain.md"
    md.write_text("""---
title: "No type no id prefix"
status: draft
---

Body text.
""")
    entity = parse_entity_file(md, project_slug="test-project")
    assert entity is None


def test_parse_entity_file_with_sync_source(tmp_path: Path):
    config = tmp_path / "science.yaml"
    config.write_text("name: test-project\n", encoding="utf-8")
    doc = tmp_path / "doc" / "sync"
    doc.mkdir(parents=True)
    f = doc / "q-from-other.md"
    f.write_text(
        "---\n"
        'id: "question:q-from-other"\n'
        "type: question\n"
        'title: "Propagated question"\n'
        "sync_source:\n"
        '  project: "aging-clocks"\n'
        '  entity_id: "question:q4-tp53"\n'
        '  sync_date: "2026-03-23"\n'
        "---\n"
        "Body text.\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(f, project_slug="test-project")
    assert entity is not None
    assert entity.sync_source is not None
    assert entity.sync_source.project == "aging-clocks"
    assert entity.sync_source.entity_id == "question:q4-tp53"

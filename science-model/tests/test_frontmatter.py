from pathlib import Path

from science_model.frontmatter import parse_frontmatter, parse_entity_file


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
    fm, body = parse_frontmatter(md)
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
    assert entity.id == "question:q01-test"
    assert entity.type.value == "question"
    assert entity.project == "my-project"
    assert entity.content_preview == "Body text here."

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from science_model.templates import EntityTemplateError, Renderer


def _fields(kind: str = "discussion") -> dict[str, object]:
    return {
        "entity_id": f"{kind}:2026-05-03-example",
        "kind": kind,
        "title": "Example title",
        "status": "active",
        "related": ["question:q01-example"],
        "source_refs": ["paper:smith2026"],
        "created": "2026-05-03",
        "updated": "2026-05-03",
        "slug": "example",
        "local_part": "2026-05-03-example",
        "nn": "01",
    }


def _frontmatter(text: str) -> dict[str, object]:
    _, frontmatter_text, _ = text.split("---\n", 2)
    loaded = yaml.safe_load(frontmatter_text)
    assert isinstance(loaded, dict)
    return loaded


@pytest.mark.parametrize("kind", ["hypothesis", "question", "interpretation", "discussion", "theme"])
def test_packaged_template_renders_required_sections(kind: str) -> None:
    text = Renderer(today=date(2026, 5, 3)).render(kind, fields=_fields(kind))
    frontmatter = _frontmatter(text)
    assert frontmatter["id"] == f"{kind}:2026-05-03-example"
    assert frontmatter["title"] == "Example title"
    assert "_template" not in frontmatter
    assert "{{title}}" not in text
    assert "{{YYYY-MM-DD}}" not in text
    if kind == "theme":
        assert frontmatter["theme_kind"] == "methodological"
        assert frontmatter["theme_scope"] == "project"
        assert "## Definition" in text
        assert "## Guardrails" in text
    elif kind == "question":
        assert "## Summary" in text
    else:
        assert "# " in text


def test_optional_section_renders_only_when_requested() -> None:
    renderer = Renderer(today=date(2026, 5, 3))
    default_text = renderer.render("discussion", fields=_fields("discussion"))
    explicit_text = renderer.render("discussion", fields=_fields("discussion"), with_keys=["double-blind-addendum"])
    assert "## Double-Blind Addendum" not in default_text
    assert "## Double-Blind Addendum" in explicit_text


def test_without_removes_required_section() -> None:
    text = Renderer(today=date(2026, 5, 3)).render(
        "hypothesis",
        fields=_fields("hypothesis"),
        without_keys=["related-work"],
    )
    assert "## Related Work" not in text
    assert "## Organizing Conjecture" in text


def test_no_hints_strips_html_comments() -> None:
    text = Renderer(today=date(2026, 5, 3)).render("discussion", fields=_fields("discussion"), no_hints=True)
    assert "<!--" not in text
    assert "-->" not in text


def test_unknown_section_key_errors_with_valid_keys() -> None:
    expected = (
        "Unknown section key 'bogus'. Valid keys: focus, current-position, critical-analysis, "
        "evidence-needed, prioritized-follow-ups, synthesis, double-blind-addendum"
    )
    with pytest.raises(EntityTemplateError, match=re.escape(expected)):
        Renderer(today=date(2026, 5, 3)).render("discussion", fields=_fields("discussion"), with_keys=["bogus"])


def test_omitted_frontmatter_field_is_not_emitted() -> None:
    text = Renderer(today=date(2026, 5, 3)).render("discussion", fields=_fields("discussion"))
    frontmatter = _frontmatter(text)
    assert "focus_ref" not in frontmatter
    assert frontmatter["focus_type"] == "question"


def test_declared_section_must_exist(tmp_path: Path) -> None:
    template = tmp_path / "broken.md"
    template.write_text(
        """---
id: "broken:{{slug}}"
type: "broken"
title: "{{title}}"
_template:
  frontmatter:
    id: { from: entity_id }
  sections:
    - { key: missing, name: "Missing", required: true }
---

# {{title}}

## Present
""",
        encoding="utf-8",
    )
    with pytest.raises(EntityTemplateError, match="declares section 'Missing' but no matching heading exists"):
        Renderer(template_root=tmp_path, today=date(2026, 5, 3)).render("broken", fields=_fields("broken"))


def test_body_heading_order_controls_render_order(tmp_path: Path) -> None:
    template = tmp_path / "ordered.md"
    template.write_text(
        """---
id: "ordered:{{slug}}"
type: "ordered"
title: "{{title}}"
_template:
  frontmatter:
    id: { from: entity_id }
  sections:
    - { key: second, name: "Second", required: true }
    - { key: first, name: "First", required: true }
---

# {{title}}

## First
First body.

## Second
Second body.
""",
        encoding="utf-8",
    )
    text = Renderer(template_root=tmp_path, today=date(2026, 5, 3)).render("ordered", fields=_fields("ordered"))
    assert text.index("## First") < text.index("## Second")


def test_default_null_is_rejected(tmp_path: Path) -> None:
    template = tmp_path / "bad-null.md"
    template.write_text(
        """---
id: "bad-null:{{slug}}"
type: "bad-null"
title: "{{title}}"
_template:
  frontmatter:
    id: { from: entity_id }
    optional_field: { default: null }
  sections:
    - { key: summary, name: "Summary", required: true }
---

# {{title}}

## Summary
Body.
""",
        encoding="utf-8",
    )
    with pytest.raises(EntityTemplateError, match="default cannot be null"):
        Renderer(template_root=tmp_path, today=date(2026, 5, 3)).render("bad-null", fields=_fields("bad-null"))


@pytest.mark.parametrize("kind", ["hypothesis", "question", "interpretation", "discussion", "theme"])
def test_root_and_packaged_migrated_templates_match(kind: str) -> None:
    root_template = Path(__file__).parents[3] / "templates" / f"{kind}.md"
    packaged_template = Path(__file__).parents[1] / "src" / "science_model" / "templates" / f"{kind}.md"
    assert packaged_template.read_text(encoding="utf-8") == root_template.read_text(encoding="utf-8")

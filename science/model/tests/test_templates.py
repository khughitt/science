from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from science_model.entities import EvidenceLineEntity
from science_model.frontmatter import parse_entity_file
from science_model.reasoning import EvidenceStance
from science_model.templates import MIGRATED_KINDS, EntityTemplateError, Renderer


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


def test_hypothesis_phase_defaults_to_active_when_unset() -> None:
    text = Renderer(today=date(2026, 5, 3)).render("hypothesis", fields=_fields("hypothesis"))
    assert _frontmatter(text)["phase"] == "active"


def test_hypothesis_phase_takes_context_value() -> None:
    fields = _fields("hypothesis")
    fields["phase"] = "candidate"
    text = Renderer(today=date(2026, 5, 3)).render("hypothesis", fields=fields)
    assert _frontmatter(text)["phase"] == "candidate"


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


@pytest.mark.parametrize("kind", sorted(MIGRATED_KINDS))
def test_root_and_packaged_migrated_templates_match(kind: str) -> None:
    root_template = Path(__file__).parents[3] / "templates" / f"{kind}.md"
    packaged_template = Path(__file__).parents[1] / "src" / "science_model" / "templates" / f"{kind}.md"
    assert packaged_template.read_text(encoding="utf-8") == root_template.read_text(encoding="utf-8")


def test_packaged_templates_are_exactly_the_migrated_kinds() -> None:
    """The packaged templates dir must hold exactly one .md per migrated kind and
    nothing else. The Renderer only ever reads packaged templates for migrated
    kinds, so any other .md is an unread, unguarded shadow (task:t092/t090). This
    invariant keeps test_root_and_packaged_migrated_templates_match's coverage
    complete: every packaged file it does not check cannot exist."""
    packaged_dir = Path(__file__).parents[1] / "src" / "science_model" / "templates"
    packaged = {p.name for p in packaged_dir.glob("*.md")}
    expected = {f"{kind}.md" for kind in MIGRATED_KINDS}
    assert packaged == expected


# ---------------------------------------------------------------------------
# evidence-line template
# ---------------------------------------------------------------------------


def _evidence_line_fields() -> dict[str, object]:
    return _fields("evidence-line")


def test_evidence_line_template_renders() -> None:
    """evidence-line is in MIGRATED_KINDS and the packaged template renders without error."""
    from science_model.templates import MIGRATED_KINDS

    assert "evidence-line" in MIGRATED_KINDS
    text = Renderer(today=date(2026, 5, 3)).render("evidence-line", fields=_evidence_line_fields())
    frontmatter = _frontmatter(text)
    assert frontmatter["id"] == "evidence-line:2026-05-03-example"
    assert frontmatter["kind"] == "evidence-line"
    assert frontmatter["stance"] == "supports"
    assert frontmatter["target"] not in ("", None)
    assert "_template" not in frontmatter
    assert "{{title}}" not in text
    assert "## What this line shows" in text
    assert "## Why it is independent" in text
    assert "## Caveats / scope" in text


def test_evidence_line_template_measurement_model_optional() -> None:
    """Measurement Model section is optional (excluded by default)."""
    text = Renderer(today=date(2026, 5, 3)).render("evidence-line", fields=_evidence_line_fields())
    assert "## Measurement Model" not in text


def test_evidence_line_template_measurement_model_included_on_request() -> None:
    text = Renderer(today=date(2026, 5, 3)).render(
        "evidence-line",
        fields=_evidence_line_fields(),
        with_keys=["measurement-model"],
    )
    assert "## Measurement Model" in text


def test_evidence_line_template_sections_declared() -> None:
    """Renderer.sections() returns exactly the four declared sections."""
    sections = Renderer(today=date(2026, 5, 3)).sections("evidence-line")
    keys = [s.key for s in sections]
    required = {s.key for s in sections if s.required}
    optional = {s.key for s in sections if not s.required}
    assert "what-this-line-shows" in keys
    assert "why-it-is-independent" in keys
    assert "caveats-scope" in keys
    assert "measurement-model" in keys
    assert required == {"what-this-line-shows", "why-it-is-independent", "caveats-scope"}
    assert optional == {"measurement-model"}


def test_evidence_line_template_round_trip(tmp_path: Path) -> None:
    """Rendering the template and parsing the file yields a valid EvidenceLineEntity."""
    text = Renderer(today=date(2026, 5, 3)).render("evidence-line", fields=_evidence_line_fields())
    (tmp_path / "science.yaml").write_text("slug: test-project\n", encoding="utf-8")
    ev_dir = tmp_path / "doc" / "evidence-lines"
    ev_dir.mkdir(parents=True)
    ev_file = ev_dir / "2026-05-03-example.md"
    ev_file.write_text(text, encoding="utf-8")
    entity = parse_entity_file(ev_file, "test-project")
    assert isinstance(entity, EvidenceLineEntity)
    assert entity.stance == EvidenceStance.SUPPORTS
    assert entity.target == "proposition:CHANGEME"


# ---------------------------------------------------------------------------
# new-kind domain templates (finding, method, paper,
# pre-registration, synthesis)
# ---------------------------------------------------------------------------

# Matches a raw, unfilled placeholder like {{nn}}, {{slug}}, or {{title}}.
_RAW_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")


@pytest.mark.parametrize(
    "kind",
    ["finding", "method", "paper", "pre-registration", "synthesis"],
)
def test_new_kind_template_is_migrated(kind: str) -> None:
    from science_model.templates import MIGRATED_KINDS

    assert kind in MIGRATED_KINDS


def test_finding_template_renders_id_without_raw_placeholders() -> None:
    text = Renderer(today=date(2026, 5, 3)).render("finding", fields=_fields("finding"))
    frontmatter = _frontmatter(text)
    assert frontmatter["id"] == "finding:2026-05-03-example"
    assert frontmatter["kind"] == "finding"
    assert "_template" not in frontmatter
    # No raw / unfilled placeholders survive in the rendered output.
    assert not _RAW_PLACEHOLDER_RE.search(text), _RAW_PLACEHOLDER_RE.search(text).group(0)
    assert "h{{nn}}" not in text


def test_synthesis_template_renders_id_without_raw_placeholders() -> None:
    text = Renderer(today=date(2026, 5, 3)).render("synthesis", fields=_fields("synthesis"))
    frontmatter = _frontmatter(text)
    assert frontmatter["id"] == "synthesis:2026-05-03-example"
    assert frontmatter["kind"] == "synthesis"
    assert "_template" not in frontmatter
    assert not _RAW_PLACEHOLDER_RE.search(text), _RAW_PLACEHOLDER_RE.search(text).group(0)


def test_paper_template_renders_id_without_raw_placeholders() -> None:
    text = Renderer(today=date(2026, 5, 3)).render("paper", fields=_fields("paper"))
    frontmatter = _frontmatter(text)
    assert frontmatter["id"] == "paper:2026-05-03-example"
    assert frontmatter["kind"] == "paper"
    assert "_template" not in frontmatter
    assert not _RAW_PLACEHOLDER_RE.search(text), _RAW_PLACEHOLDER_RE.search(text).group(0)


def test_hypothesis_id_has_no_legacy_h_prefix_placeholder() -> None:
    text = Renderer(today=date(2026, 5, 3)).render("hypothesis", fields=_fields("hypothesis"))
    frontmatter = _frontmatter(text)
    assert frontmatter["id"] == "hypothesis:2026-05-03-example"
    assert "h{{nn}}" not in text
    assert not _RAW_PLACEHOLDER_RE.search(text), _RAW_PLACEHOLDER_RE.search(text).group(0)

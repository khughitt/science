# Template-Driven Entity Shells Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shipped Markdown templates the single source of truth for source-authored entity shells created by `science hypothesis create`, `science question create`, `science interpretation create`, and `science discussion create`.

**Architecture:** Keep repo-root `templates/` as the canonical source for commands, skills, and plugin packaging. Add a packaged copy under `science-model/src/science_model/templates/` for installed CLI use, with tests that compare the two copies for the migrated kinds. Keep `science` responsible for CLI argument collection, ID/path policy, project writes, and validation; it calls the renderer for migrated kinds and keeps the generic Summary/Notes shell for non-migrated kinds.

**Tech Stack:** Python 3.11, Click, Pydantic v2, PyYAML, `importlib.resources`, pytest, Hatchling package data.

---

## Context

`science/src/science_tool/entities.py::build_entity_markdown` currently creates generic shells for most kinds and a hard-coded discussion body for fb-2026-04-30-001. That fixed `/science:discuss` drift temporarily, but it created a second source of truth beside `templates/discussion.md`.

The durable fix is to render entity bodies from `templates/<kind>.md`. The four Phase 1 migrated kinds are:

- `hypothesis`
- `question`
- `interpretation`
- `discussion`

For those migrated kinds, a missing `_template:` metadata block is a hard configuration error. For all other kinds, the existing generic shell remains unchanged.

## File Structure

- Keep canonical templates in: `templates/`
- Create packaged copies in: `science-model/src/science_model/templates/`
- Create: `science-model/src/science_model/templates.py`
- Create: `science-model/tests/test_templates.py`
- Modify: `science/src/science_tool/entities.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_entities.py`
- Modify: `science/tests/test_entities_cli.py`
- Review only if package-data verification fails: `science-model/pyproject.toml`

## Data Contract

Each migrated template has a `_template:` block inside frontmatter:

```yaml
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "discussion" }
    title: { from: title }
    status: { from: status }
    related: { from: related }
    source_refs: { from: source_refs }
    created: { from: created }
    updated: { from: updated }
    focus_type: { default: "question" }
    focus_ref: { omit: true }
    mode: { default: "standard" }
  sections:
    - { key: focus, name: "Focus", required: true }
```

Field policy rules:

- `from: <field>` reads a renderer context field. Valid fields are `entity_id`, `kind`, `title`, `status`, `related`, `source_refs`, `created`, `updated`, `slug`, `local_part`, and `nn`.
- `default: <value>` emits a literal value after placeholder substitution. `default: null` is invalid; authors must use `omit: true` for omitted fields or a concrete default value for emitted fields.
- `omit: true` documents a human-facing example field that must not be emitted.
- A field policy must use exactly one of `from`, `default`, or `omit`.
- `_template` is removed from rendered frontmatter.

Section rules:

- `key` is the CLI-facing stable identifier.
- `name` must match a real `## ` heading in the body.
- `required: true` sections render by default and can be removed with `--without KEY`.
- `required: false` sections are omitted by default and can be added with `--with KEY`.
- Body order follows the order of `## ` headings in the template body. The renderer iterates parsed body sections and looks up each heading's metadata by `name`; `_template.sections` order is not used for rendering.
- H1 is template-owned; the renderer substitutes placeholders in it and emits it verbatim.
- `--no-hints` strips HTML comments from emitted body content.

Placeholder rules:

- Canonical placeholders are `{{title}}`, `{{slug}}`, `{{YYYY-MM-DD}}`, `{{YYYY-MM-DD-slug}}`, and `{{nn}}`.
- `{{nn}}` is an empty string when the entity local part has no leading question/hypothesis-style number. That is expected for date-prefixed IDs such as `discussion:2026-05-03-example`.
- Unknown `{{...}}` strings stay verbatim.
- Angle-bracket placeholders in migrated templates are removed during migration. User-fillable guidance belongs in HTML comments or plain empty cells, not `<placeholder>` prose.

## Task 1: Add Packaged Template Copies

**Files:**
- Read: `templates/`
- Create: `science-model/src/science_model/templates/`

- [ ] **Step 1: Enumerate existing template consumers**

Run:

```bash
rg -n "CLAUDE_PLUGIN_ROOT.*/templates|templates/.*\\.md|\\.ai/templates" \
  commands skills codex-skills references science/tests/test_command_docs.py
```

Expected: output includes command and skill consumers such as `commands/add-hypothesis.md`, `commands/discuss.md`, `commands/find-datasets.md`, `commands/pre-register.md`, `commands/research-papers.md`, `commands/search-literature.md`, `commands/research-topic.md`, `commands/big-picture.md`, `skills/pipelines/snakemake.md`, and generated `codex-skills/` references. This confirms root `templates/` must remain a real directory for plugin packaging.

- [ ] **Step 2: Copy templates into the package**

Run:

```bash
mkdir -p science-model/src/science_model/templates
cp -R templates/. science-model/src/science_model/templates/
```

Expected: `science-model/src/science_model/templates/discussion.md` exists and root `templates/` is still a normal directory, not a symlink.

- [ ] **Step 3: Verify both locations resolve**

Run:

```bash
test -d templates
test ! -L templates
test -f templates/discussion.md
test -f science-model/src/science_model/templates/discussion.md
```

Expected: all four commands exit 0.

- [ ] **Step 4: Verify package resource visibility from a checkout**

Run:

```bash
uv run --frozen python -c "import importlib.resources as r; p = r.files('science_model').joinpath('templates/discussion.md'); print(p.read_text(encoding='utf-8').splitlines()[0])"
```

Expected output:

```text
---
```

- [ ] **Step 5: Commit**

Run:

```bash
git add templates science-model/src/science_model/templates
git commit -m "chore: package science templates for installed CLI"
```

## Task 2: Normalize Migrated Templates

**Files:**
- Modify: `templates/hypothesis.md`
- Modify: `templates/question.md`
- Modify: `templates/interpretation.md`
- Modify: `templates/discussion.md`
- Modify: `science-model/src/science_model/templates/hypothesis.md`
- Modify: `science-model/src/science_model/templates/question.md`
- Modify: `science-model/src/science_model/templates/interpretation.md`
- Modify: `science-model/src/science_model/templates/discussion.md`

- [ ] **Step 1: Normalize placeholders**

Apply these replacements in the four migrated templates. The `<nn>` and `<slug>` replacements apply to `question.md`; `hypothesis.md` already uses `{{nn}}` and `{{slug}}`.

```text
{{Short Title}} -> {{title}}
{{discussion title}} -> {{title}}
<Question> -> {{title}}
<YYYY-MM-DD> -> {{YYYY-MM-DD}}
<nn> -> {{nn}}
<slug> -> {{slug}}
```

In `question.md`, replace prose angle placeholders such as `<decision this question affects>` with HTML hint comments so no `<...>` placeholder remains in that template body.

In `discussion.md`, replace the `Prioritized Follow-Ups` table's `<action>`, `<rationale>`, and `<deps>` placeholders with empty cells and put the guidance in an HTML comment immediately above the table. This makes `--no-hints` remove the guidance cleanly instead of leaving angle placeholders in the rendered shell.

Run:

```bash
rg -n "<nn>|<slug>|<Question>|<YYYY-MM-DD>|\\{\\{Short Title\\}\\}|\\{\\{discussion title\\}\\}" templates science-model/src/science_model/templates
rg -n '<[A-Za-z]' templates/question.md templates/discussion.md science-model/src/science_model/templates/question.md science-model/src/science_model/templates/discussion.md
```

Expected: no matches from either command.

- [ ] **Step 2: Promote discussion's optional addendum**

In both copies of `discussion.md`, move `## Double-Blind Addendum` out of the surrounding HTML comment. Keep this hint comment as the first content inside the section:

```markdown
<!-- Include this section only when mode = "double-blind". -->
```

Run:

```bash
rg -n "DOUBLE-BLIND ADDENDUM|Delete this entire block" templates/discussion.md science-model/src/science_model/templates/discussion.md
```

Expected: no matches.

- [ ] **Step 3: Add `_template` to hypothesis**

Insert this block in both copies of `hypothesis.md` frontmatter before the closing `---`:

```yaml
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "hypothesis" }
    title: { from: title }
    status: { from: status }
    phase: { default: "active" }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: organizing-conjecture, name: "Organizing Conjecture", required: true }
    - { key: proposition-bundle, name: "Proposition Bundle", required: true }
    - { key: current-uncertainty, name: "Current Uncertainty", required: true }
    - { key: predictions, name: "Predictions", required: true }
    - { key: falsifiability, name: "Falsifiability", required: true }
    - { key: promotion-criteria, name: "Promotion criteria", required: false }
    - { key: supporting-evidence, name: "Supporting Evidence", required: true }
    - { key: disputing-evidence, name: "Disputing Evidence", required: true }
    - { key: evidence-needed-to-shift-belief, name: "Evidence Needed To Shift Belief", required: true }
    - { key: related-work, name: "Related Work", required: true }
```

- [ ] **Step 4: Add `_template` to question**

Insert this block in both copies of `question.md` frontmatter before the closing `---`:

```yaml
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "question" }
    title: { from: title }
    status: { from: status }
    ontology_terms: { default: [] }
    datasets: { default: [] }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: summary, name: "Summary", required: true }
    - { key: why-it-matters, name: "Why It Matters", required: true }
    - { key: current-evidence, name: "Current Evidence", required: true }
    - { key: thoughts, name: "Thoughts", required: true }
    - { key: connections-to-project, name: "Connections to Project", required: true }
    - { key: related, name: "Related", required: true }
```

- [ ] **Step 5: Add `_template` to interpretation**

Insert this block in both copies of `interpretation.md` frontmatter before the closing `---`:

```yaml
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "interpretation" }
    title: { from: title }
    status: { from: status }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
    input: { from: source_refs }
    workflow_run: { omit: true }
    prior_interpretations: { default: [] }
  sections:
    - { key: verdict, name: "Verdict", required: true }
    - { key: findings-summary, name: "Findings Summary", required: true }
    - { key: evidence-quality, name: "Evidence Quality", required: true }
    - { key: data-quality-checks, name: "Data Quality Checks", required: true }
    - { key: proposition-level-updates, name: "Proposition-Level Updates", required: true }
    - { key: hypothesis-level-implications, name: "Hypothesis-Level Implications", required: true }
    - { key: evidence-vs-open-questions, name: "Evidence vs. Open Questions", required: true }
    - { key: new-questions-raised, name: "New Questions Raised", required: true }
    - { key: user-questions, name: "User Questions", required: false }
    - { key: limitations-residual-uncertainty, name: "Limitations & Residual Uncertainty", required: true }
    - { key: updated-priorities, name: "Updated Priorities", required: true }
```

- [ ] **Step 6: Add `_template` to discussion**

Insert this block in both copies of `discussion.md` frontmatter before the closing `---`:

```yaml
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "discussion" }
    title: { from: title }
    status: { from: status }
    source_refs: { from: source_refs }
    related: { from: related }
    created: { from: created }
    updated: { from: updated }
    focus_type: { default: "question" }
    focus_ref: { omit: true }
    mode: { default: "standard" }
  sections:
    - { key: focus, name: "Focus", required: true }
    - { key: current-position, name: "Current Position", required: true }
    - { key: critical-analysis, name: "Critical Analysis", required: true }
    - { key: evidence-needed, name: "Evidence Needed", required: true }
    - { key: prioritized-follow-ups, name: "Prioritized Follow-Ups", required: true }
    - { key: synthesis, name: "Synthesis", required: true }
    - { key: double-blind-addendum, name: "Double-Blind Addendum", required: false }
```

- [ ] **Step 7: Commit**

Run:

```bash
git add templates science-model/src/science_model/templates
git commit -m "feat: add template metadata for entity shells"
```

## Task 3: Add Renderer Tests First

**Files:**
- Create: `science-model/tests/test_templates.py`

- [ ] **Step 1: Write failing renderer tests**

Create `science-model/tests/test_templates.py` with:

```python
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


@pytest.mark.parametrize("kind", ["hypothesis", "question", "interpretation", "discussion"])
def test_packaged_template_renders_required_sections(kind: str) -> None:
    text = Renderer(today=date(2026, 5, 3)).render(kind, fields=_fields(kind))
    frontmatter = _frontmatter(text)
    assert frontmatter["id"] == f"{kind}:2026-05-03-example"
    assert frontmatter["title"] == "Example title"
    assert "_template" not in frontmatter
    assert "{{title}}" not in text
    assert "{{YYYY-MM-DD}}" not in text
    if kind == "question":
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


@pytest.mark.parametrize("kind", ["hypothesis", "question", "interpretation", "discussion"])
def test_root_and_packaged_migrated_templates_match(kind: str) -> None:
    root_template = Path(__file__).parents[2] / "templates" / f"{kind}.md"
    packaged_template = Path(__file__).parents[1] / "src" / "science_model" / "templates" / f"{kind}.md"
    assert packaged_template.read_text(encoding="utf-8") == root_template.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests and verify they fail on missing module**

Run:

```bash
uv run --frozen pytest science-model/tests/test_templates.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_model.templates'`.

- [ ] **Step 3: Commit failing tests**

Run:

```bash
git add science-model/tests/test_templates.py
git commit -m "test: specify template renderer behavior"
```

## Task 4: Implement `science_model.templates`

**Files:**
- Create: `science-model/src/science_model/templates.py`

- [ ] **Step 1: Create renderer module**

Create `science-model/src/science_model/templates.py` with these public objects and behavior:

```python
from __future__ import annotations

import importlib.resources
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


MIGRATED_KINDS: frozenset[str] = frozenset({"hypothesis", "question", "interpretation", "discussion"})
VALID_FIELD_NAMES: frozenset[str] = frozenset(
    {"entity_id", "kind", "title", "status", "related", "source_refs", "created", "updated", "slug", "local_part", "nn"}
)


class EntityTemplateError(ValueError):
    """Raised when an entity template cannot be rendered."""


class FrontmatterFieldPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    from_: str | None = Field(default=None, alias="from")
    default: Any = None
    omit: bool = False

    @model_validator(mode="after")
    def exactly_one_policy(self) -> "FrontmatterFieldPolicy":
        enabled = [self.from_ is not None, "default" in self.model_fields_set, self.omit]
        if sum(enabled) != 1:
            raise ValueError("frontmatter field policy must use exactly one of from, default, or omit")
        if "default" in self.model_fields_set and self.default is None:
            raise ValueError("default cannot be null; use omit: true or a concrete default")
        if self.from_ is not None and self.from_ not in VALID_FIELD_NAMES:
            raise ValueError(f"unknown renderer field: {self.from_}")
        return self


class TemplateSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    name: str
    required: bool


class TemplateMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frontmatter: dict[str, FrontmatterFieldPolicy]
    sections: list[TemplateSection]


@dataclass(frozen=True)
class SectionInfo:
    key: str
    name: str
    required: bool
    hint: str


class Renderer:
    def __init__(self, template_root: Path | None = None, today: date | None = None) -> None:
        self.template_root = template_root
        self.today = today or date.today()

    def render(
        self,
        kind: str,
        *,
        fields: dict[str, object],
        with_keys: list[str] | tuple[str, ...] = (),
        without_keys: list[str] | tuple[str, ...] = (),
        no_hints: bool = False,
    ) -> str:
        template_text = self._read_template(kind)
        frontmatter, body = _split_frontmatter(template_text, kind)
        metadata = _load_metadata(frontmatter, kind)
        h1, sections = _parse_body_sections(body, kind)
        _assert_declared_sections_exist(metadata, sections, kind)
        _assert_known_keys(metadata, with_keys, without_keys, kind)

        context = _context_with_computed_fields(fields, self.today)
        rendered_frontmatter = _render_frontmatter(metadata, context)
        rendered_body = _render_body(
            h1=h1,
            sections=sections,
            metadata=metadata,
            context=context,
            with_keys=set(with_keys),
            without_keys=set(without_keys),
            no_hints=no_hints,
        )
        return "---\n" + yaml.safe_dump(rendered_frontmatter, sort_keys=False) + "---\n" + rendered_body

    def sections(self, kind: str) -> list[SectionInfo]:
        template_text = self._read_template(kind)
        frontmatter, body = _split_frontmatter(template_text, kind)
        metadata = _load_metadata(frontmatter, kind)
        _, parsed_sections = _parse_body_sections(body, kind)
        _assert_declared_sections_exist(metadata, parsed_sections, kind)
        metadata_by_name = {section.name: section for section in metadata.sections}
        rows: list[SectionInfo] = []
        for parsed_section in parsed_sections:
            section = metadata_by_name[parsed_section.name]
            rows.append(
                SectionInfo(
                    key=section.key,
                    name=section.name,
                    required=section.required,
                    hint=_first_hint(parsed_section.content),
                )
            )
        return rows

    def _read_template(self, kind: str) -> str:
        filename = f"{kind}.md"
        if self.template_root is not None:
            path = self.template_root / filename
            if not path.exists():
                raise EntityTemplateError(f"Template not found: {path}")
            return path.read_text(encoding="utf-8")
        resource = importlib.resources.files("science_model").joinpath("templates", filename)
        if not resource.is_file():
            raise EntityTemplateError(f"Packaged template not found: science_model/templates/{filename}")
        return resource.read_text(encoding="utf-8")
```

Use private helpers in the same file for `_split_frontmatter`, `_load_metadata`, `_parse_body_sections`, `_assert_declared_sections_exist`, `_assert_known_keys`, `_context_with_computed_fields`, `_render_frontmatter`, `_render_body`, `_substitute`, `_strip_hints`, and `_first_hint`.

- [ ] **Step 2: Implement parsing details**

Implement helpers with these exact semantics:

- `_split_frontmatter` requires a leading `---\n` and a second `---\n`; otherwise raise `EntityTemplateError(f"Template {kind}.md is missing YAML frontmatter")`.
- `_load_metadata` parses YAML with `yaml.safe_load`, requires `_template`, validates it with `TemplateMetadata.model_validate`, and raises `EntityTemplateError` with the kind and validation message on failure.
- `_parse_body_sections` treats the first non-empty line before any `## ` heading as the H1, then captures top-level `## ` sections until the next `## ` heading.
- `_assert_known_keys` rejects unknown `--with` or `--without` keys with `Unknown section key '<key>'. Valid keys: <comma-separated keys>`. The valid keys are listed in parsed body order, not alphabetical order.
- `_render_frontmatter` emits fields in `_template.frontmatter` order, skips `omit: true`, and applies placeholder substitution to string values.
- `_render_frontmatter` must build a new output dict from `metadata.frontmatter`; do not mutate the parsed YAML frontmatter by deleting `_template`.
- `_render_body` iterates parsed body sections in body order. For each heading, look up its metadata by `name`, then emit it when it is required and not in `without_keys`, or when its key is present in `with_keys`.
- `_strip_hints` removes all `<!-- ... -->` blocks with `re.DOTALL`.
- `_first_hint` returns the first HTML comment body with all whitespace runs collapsed to a single space and leading/trailing whitespace stripped.

- [ ] **Step 3: Run renderer tests**

Run:

```bash
uv run --frozen pytest science-model/tests/test_templates.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
git add science-model/src/science_model/templates.py science-model/tests/test_templates.py
git commit -m "feat: render entity shells from templates"
```

## Task 5: Wire Renderer Into Entity Creation

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Modify: `science/tests/test_entities.py`

- [ ] **Step 1: Extend `build_entity_markdown` arguments**

Change `build_entity_markdown` to accept:

```python
    with_sections: list[str] | None = None,
    without_sections: list[str] | None = None,
    no_hints: bool = False,
```

For migrated kinds, build a renderer field dict and call:

```python
from science_model.templates import MIGRATED_KINDS, EntityTemplateError, Renderer

if kind in MIGRATED_KINDS:
    local_part = entity_id.split(":", 1)[1]
    fields: dict[str, object] = {
        "entity_id": validate_entity_id(kind, entity_id),
        "kind": kind,
        "title": title,
        "status": status,
        "related": related,
        "source_refs": source_refs,
        "created": today.isoformat(),
        "updated": today.isoformat(),
        "slug": local_part.removeprefix(f"{today.isoformat()}-"),
        "local_part": local_part,
        "nn": _leading_number(local_part),
    }
    try:
        return Renderer(today=today).render(
            kind,
            fields=fields,
            with_keys=list(with_sections or []),
            without_keys=list(without_sections or []),
            no_hints=no_hints,
        )
    except EntityTemplateError as exc:
        raise EntityCommandError(str(exc)) from exc
```

Add `_leading_number(local_part: str) -> str` that returns the leading digit sequence after an optional one-letter prefix, or `""` if none exists:

```python
def _leading_number(local_part: str) -> str:
    match = _ID_PREFIX_RE.match(local_part)
    return match.group("number") if match else ""
```

Remove `_DISCUSSION_BODY_SECTIONS` and the `kind == "discussion"` branch from `_entity_body_template`.

- [ ] **Step 2: Extend `create_entity` arguments**

Add the same three keyword-only arguments to `create_entity` and pass them through to `build_entity_markdown`.

This path must still call `_validate_prospective_write` after rendering template-driven frontmatter. Do not bypass the audit to make template-created entities pass.

- [ ] **Step 3: Update entity tests**

In `science/tests/test_entities.py`, update `test_build_entity_markdown_uses_canonical_frontmatter_and_body` so `kind="question"` expects template sections:

```python
assert "## Why It Matters" in text
assert "## Notes" not in text
```

Keep `test_build_entity_markdown_for_discussion_uses_canonical_sections`, and add:

```python
def test_build_entity_markdown_can_include_optional_template_section() -> None:
    text = build_entity_markdown(
        kind="discussion",
        entity_id="discussion:2026-05-03-test",
        title="Test discussion",
        status="active",
        related=[],
        source_refs=[],
        today=date(2026, 5, 3),
        with_sections=["double-blind-addendum"],
    )
    assert "## Double-Blind Addendum" in text


def test_build_entity_markdown_can_strip_template_hints() -> None:
    text = build_entity_markdown(
        kind="discussion",
        entity_id="discussion:2026-05-03-test",
        title="Test discussion",
        status="active",
        related=[],
        source_refs=[],
        today=date(2026, 5, 3),
        no_hints=True,
    )
    assert "<!--" not in text


def test_template_driven_create_entity_passes_prospective_audit_for_all_migrated_kinds(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-seed.md",
        {"id": "question:q01-seed", "type": "question", "title": "Seed", "status": "active"},
    )

    cases: list[tuple[str, str, str | None]] = [
        ("question", "What should we test next?", None),
        ("hypothesis", "Template shell hypothesis", "hypothesis:h01-template-shell"),
        ("discussion", "Template shell discussion", None),
        ("interpretation", "Template shell interpretation", None),
    ]
    for kind, title, entity_id in cases:
        result = create_entity(
            project_root=tmp_path,
            kind=kind,
            title=title,
            entity_id=entity_id,
            related=[],
            source_refs=[],
            today=date(2026, 5, 3),
        )
        assert result.warnings == []
        assert result.path.exists()
```

- [ ] **Step 4: Run entity tests**

Run:

```bash
uv run --frozen pytest science/tests/test_entities.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add science/src/science_tool/entities.py science/tests/test_entities.py
git commit -m "feat: use templates for source entity shells"
```

## Task 6: Add CLI Flags and Section Listing

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_entities_cli.py`

- [ ] **Step 1: Add shared create options**

Add these Click options to `entity create`, `hypothesis create`, `question create`, `interpretation create`, and `discussion create`:

```python
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
```

Thread `with_sections=list(with_sections)`, `without_sections=list(without_sections)`, and `no_hints=no_hints` through `_create_typed_entity` and `create_entity`.

- [ ] **Step 2: Add `entity sections` command**

Add this command under `entity_group`:

```python
@entity_group.command("sections")
@click.argument("kind")
def entity_sections(kind: str) -> None:
    """List template sections for a source-authored entity kind."""

    from science_model.templates import EntityTemplateError, Renderer

    try:
        sections = Renderer().sections(kind)
    except EntityTemplateError as exc:
        raise click.ClickException(str(exc)) from exc
    rows = [
        {
            "key": section.key,
            "required": "required" if section.required else "optional",
            "name": section.name,
            "hint": section.hint[:80],
        }
        for section in sections
    ]
    emit_query_rows(
        output_format="table",
        title=f"{kind} Template Sections",
        columns=[("key", "KEY"), ("required", "REQ?"), ("name", "NAME"), ("hint", "HINT")],
        rows=rows,
    )
```

`emit_query_rows` is already imported and used in `science/src/science_tool/cli.py`; no new output helper is required.

- [ ] **Step 3: Add CLI tests**

In `science/tests/test_entities_cli.py`, add tests that invoke:

```python
runner.invoke(main, ["discussion", "create", "Test discussion", "--with", "double-blind-addendum"])
runner.invoke(main, ["discussion", "create", "Test discussion", "--no-hints"])
runner.invoke(main, ["entity", "sections", "discussion"])
runner.invoke(main, ["discussion", "create", "Test discussion", "--with", "bogus"])
```

Assert:

- the optional addendum appears in the created discussion file
- no HTML comment remains when `--no-hints` is passed
- `entity sections discussion` output includes `double-blind-addendum` and `optional`
- unknown section key exits non-zero and names valid keys

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run --frozen pytest science/tests/test_entities_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add science/src/science_tool/cli.py science/tests/test_entities_cli.py
git commit -m "feat: expose template section controls in CLI"
```

## Task 7: Package and Regression Verification

**Files:**
- Review only if needed: `science-model/pyproject.toml`

- [ ] **Step 1: Verify package data in an installed wheel**

Run:

```bash
cd science-model
uv build
cd ..
wheel_path="$(ls science-model/dist/science_model-*.whl | tail -n 1)"
uv run --with "$wheel_path" python -c "import importlib.resources as r; print(r.files('science_model').joinpath('templates/question.md').is_file())"
```

Expected output:

```text
True
```

If the output is not `True`, add explicit Hatch force-include config to `science-model/pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/science_model/templates" = "science_model/templates"
```

Then rerun the package-data check.

- [ ] **Step 2: Verify root templates are a real plugin-packaged directory**

Run:

```bash
test -d templates
test ! -L templates
rg -n "CLAUDE_PLUGIN_ROOT.*/templates|templates/.*\\.md|\\.ai/templates" commands skills references science/tests/test_command_docs.py
```

Expected: `templates/` is a real directory, not a symlink, and the grep still shows command/skill consumers that resolve through that path.

- [ ] **Step 3: Run the prospective-audit regression directly**

Run:

```bash
uv run --frozen pytest science/tests/test_entities.py::test_template_driven_create_entity_passes_prospective_audit_for_all_migrated_kinds -q
```

Expected: PASS. This verifies the new template frontmatter fields do not introduce blocking `_validate_prospective_write` audit rows.

- [ ] **Step 4: Run focused test suites**

Run:

```bash
uv run --frozen pytest science-model/tests/test_templates.py science/tests/test_entities.py science/tests/test_entities_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Run static checks**

Run:

```bash
uv run --frozen ruff check science-model/src/science_model/templates.py science-model/tests/test_templates.py science/src/science_tool/entities.py science/src/science_tool/cli.py science/tests/test_entities.py science/tests/test_entities_cli.py
uv run --frozen pyright science-model/src/science_model science/src/science_tool
```

Expected: both commands PASS.

- [ ] **Step 6: Verify no stale hard-coded discussion shell remains**

Run:

```bash
rg -n "_DISCUSSION_BODY_SECTIONS|kind == \"discussion\"|Summary\\n\\n\\n## Notes" science/src/science_tool/entities.py
```

Expected: no matches.

- [ ] **Step 7: Commit package verification fixes if any**

Run only if `science-model/pyproject.toml` changed:

```bash
git add science-model/pyproject.toml
git commit -m "build: include packaged entity templates"
```

## Task 8: Final End-to-End Check

**Files:**
- No planned edits.

- [ ] **Step 1: Create one entity of each migrated kind in a temporary project**

Run:

```bash
tmpdir="$(mktemp -d)"
printf "%s\n" "$tmpdir" > /tmp/science-template-shells-tmpdir
cat > "$tmpdir/science.yaml" <<'EOF'
name: "template-shell-smoke"
aspects:
  - hypothesis-testing
EOF
mkdir -p "$tmpdir/doc/questions" "$tmpdir/specs/hypotheses" "$tmpdir/doc/discussions" "$tmpdir/doc/interpretations"
cat > "$tmpdir/doc/questions/q01-seed.md" <<'EOF'
---
id: "question:q01-seed"
type: "question"
title: "Seed"
status: "active"
---
# Seed
EOF
(
  cd "$tmpdir"
  uv run --project ~/d/science/science science question create "What should we test next?"
  uv run --project ~/d/science/science science hypothesis create "Template shell hypothesis" --id hypothesis:h01-template-shell
  uv run --project ~/d/science/science science discussion create "Template shell discussion" --with double-blind-addendum
  uv run --project ~/d/science/science science interpretation create "Template shell interpretation"
)
```

Expected: all four commands create Markdown files with kind-specific sections.

- [ ] **Step 2: Run graph load and audit smoke tests on the temporary project**

Run:

```bash
tmpdir="$(cat /tmp/science-template-shells-tmpdir)"
(
  cd "$tmpdir"
  uv run --project ~/d/science/science science entity list
  uv run --project ~/d/science/science science graph audit --project-root "$tmpdir"
)
```

Expected: `entity list` output includes the four created entities; `graph audit` exits 0 and reports no blocking failures.

- [ ] **Step 3: Run full focused verification**

Run:

```bash
uv run --frozen pytest science-model/tests/test_templates.py science/tests/test_entities.py science/tests/test_entities_cli.py -q
uv run --frozen ruff check science-model/src/science_model/templates.py science-model/tests/test_templates.py science/src/science_tool/entities.py science/src/science_tool/cli.py science/tests/test_entities.py science/tests/test_entities_cli.py
```

Expected: all commands PASS.

- [ ] **Step 4: Final commit**

Run:

```bash
git status --short
git add docs/plans/2026-05-03-template-driven-entity-shells-design.md science-model science templates
git commit -m "feat: template-driven source entity shells"
```

Expected: the staged diff contains template metadata in both template locations, packaged template copies, renderer, CLI wiring, tests, and this plan.

## Risks and Mitigations

- **Template metadata becomes load-bearing.** Mitigation: `science-model/tests/test_templates.py` renders all migrated templates and checks declared section names against real headings.
- **Root and packaged templates drift.** Mitigation: `test_root_and_packaged_migrated_templates_match` compares both copies for all migrated kinds.
- **Plugin template consumers break if `templates/` is not a real directory.** Mitigation: root `templates/` remains canonical; Task 1 enumerates `${CLAUDE_PLUGIN_ROOT}/templates/...` consumers, and Task 7 verifies `templates/` is not a symlink.
- **Downstream graph consumers see more frontmatter fields.** Mitigation: the prospective-audit regression creates all four migrated kinds through `create_entity` and expects no warnings; Task 8 also runs `science graph audit`.
- **Unknown placeholders appear in authored comments.** Mitigation: renderer substitutes only the closed canonical vocabulary and preserves unknown `{{...}}` text.
- **CLI options are added inconsistently across create paths.** Mitigation: Task 6 wires the same options through generic `entity create` and all four typed create commands.

## Self-Review

- Spec coverage: the plan covers canonical root templates plus packaged copies, `_template` metadata, renderer API, CLI `--with` / `--without` / `--no-hints`, `entity sections`, migrated-kind hard errors, optional discussion addendum handling, package-data verification, prospective audit verification, and end-to-end graph audit smoke checks.
- Placeholder scan: product placeholders are limited to documented template syntax; there are no unresolved implementation placeholders in task instructions.
- Type consistency: renderer field names in template metadata match the field dict assembled in `science/src/science_tool/entities.py`; CLI option names map to `with_sections`, `without_sections`, and `no_hints` through all create paths.

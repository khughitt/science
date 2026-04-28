# Source Entity CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build source-authored `science-tool entity` commands plus typed wrappers for questions, hypotheses, discussions, and interpretations.

**Architecture:** Add `science_tool/entities.py` as the domain module for source entity authoring. Keep source validation on the existing registry/adapters path by adding virtual markdown overrides to the markdown loader, then wire Click commands in `science_tool/cli.py`. The first increment writes markdown/frontmatter sources only; graph mutation remains under `graph add`.

**Tech Stack:** Python 3, Click, PyYAML, Pydantic entities from `science-model`, rdflib-backed graph queries, `uv run --frozen pytest`, `ruff`, and `pyright`.

---

## File Structure

- Create `science-tool/src/science_tool/entities.py`
  - Path policy, slug/id generation, frontmatter/body rendering, source lookup, create/edit/note/list/neighbors helpers, and validation.
- Modify `science-tool/src/science_tool/graph/storage_adapters/markdown.py`
  - Add optional virtual markdown file overrides and parse-from-text helper.
  - Ignore non-`.md` staging files by relying on the current `*.md` glob.
- Modify `science-tool/src/science_tool/graph/sources.py`
  - Add optional `markdown_overrides: dict[str, str] | None = None` parameter to `load_project_sources`.
  - Pass overrides into `MarkdownAdapter`.
- Modify `science-tool/src/science_tool/cli.py`
  - Import entity helpers.
  - Add `entity`, `question`, `hypothesis`, `discussion`, and `interpretation` groups.
  - Add soft-deprecation guidance to overlapping `graph add` commands.
- Create `science-tool/tests/test_entities.py`
  - Unit tests for core policy, slug/id generation, rendering, editing, note insertion, validation, and reference resolution.
- Create `science-tool/tests/test_entities_cli.py`
  - CLI tests for create/show/edit/note/list/neighbors and typed wrappers.
- Create `science-tool/tests/_fixtures/entity_helpers.py`
  - Shared project seeding and markdown entity helpers for entity tests.
- Modify `science-tool/tests/test_storage_adapters/test_markdown.py`
  - Tests for virtual overrides and `.md.tmp` non-discovery.
- Modify `science-tool/tests/test_graph_materialize.py`
  - Smoke coverage that source-authored and graph-only entities do not double-count after materialization.

## Shared Test Fixtures

Create `science-tool/tests/_fixtures/entity_helpers.py` and import these helpers from
both `science-tool/tests/test_entities.py` and
`science-tool/tests/test_entities_cli.py`.

```python
from pathlib import Path

import yaml


def seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: entity-cli-test\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )


def write_markdown_entity(root: Path, rel_path: str, frontmatter: dict[str, object], body: str = "") -> Path:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body,
        encoding="utf-8",
    )
    return path
```

### Task 1: Markdown Virtual Overrides

**Files:**
- Modify: `science-tool/src/science_tool/graph/storage_adapters/markdown.py`
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Test: `science-tool/tests/test_storage_adapters/test_markdown.py`

- [ ] **Step 1: Write failing markdown override tests**

Add these tests to `science-tool/tests/test_storage_adapters/test_markdown.py`.

```python
def test_virtual_markdown_override_is_discovered_and_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = MarkdownAdapter(virtual_files={
        "doc/questions/q01-example.md": '---\nid: "question:q01-example"\ntype: "question"\ntitle: "Q1"\n---\nBody.\n'
    })

    refs = adapter.discover(tmp_path)

    assert [ref.path for ref in refs] == ["doc/questions/q01-example.md"]
    monkeypatch.chdir(tmp_path)
    raw = adapter.load_raw(refs[0])
    assert raw["canonical_id"] == "question:q01-example"
    assert raw["kind"] == "question"
    assert raw["content"] == "Body.\n"


def test_virtual_markdown_override_replaces_disk_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "doc" / "questions").mkdir(parents=True)
    (tmp_path / "doc" / "questions" / "q01-example.md").write_text(
        '---\nid: "question:q01-example"\ntype: "question"\ntitle: "Old"\n---\nOld body.\n',
        encoding="utf-8",
    )
    adapter = MarkdownAdapter(virtual_files={
        "doc/questions/q01-example.md": '---\nid: "question:q01-example"\ntype: "question"\ntitle: "New"\n---\nNew body.\n'
    })

    refs = adapter.discover(tmp_path)

    assert [ref.path for ref in refs] == ["doc/questions/q01-example.md"]
    monkeypatch.chdir(tmp_path)
    raw = adapter.load_raw(refs[0])
    assert raw["title"] == "New"
    assert raw["content"] == "New body.\n"


def test_md_tmp_files_are_not_discovered(tmp_path: Path) -> None:
    (tmp_path / "doc" / "questions").mkdir(parents=True)
    (tmp_path / "doc" / "questions" / "q01-example.md.tmp").write_text(
        '---\nid: "question:q01-example"\ntype: "question"\ntitle: "Q1"\n---\n',
        encoding="utf-8",
    )

    assert MarkdownAdapter().discover(tmp_path) == []
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_storage_adapters/test_markdown.py -q
```

Expected: FAIL because `MarkdownAdapter.__init__` has no `virtual_files` parameter.

- [ ] **Step 3: Implement virtual overrides**

In `science-tool/src/science_tool/graph/storage_adapters/markdown.py`, update the adapter shape like this.

```python
class MarkdownAdapter(StorageAdapter):
    name = "markdown"

    def __init__(self, scan_roots: list[str] | None = None, virtual_files: dict[str, str] | None = None) -> None:
        self._scan_roots = scan_roots or ["doc", "specs", "research/packages"]
        self._virtual_files = dict(virtual_files or {})

    @property
    def scan_roots(self) -> tuple[str, ...]:
        return tuple(self._scan_roots)

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs_by_path: dict[str, SourceRef] = {}
        for rel in self._scan_roots:
            root = project_root / rel
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                try:
                    rel_path = str(path.relative_to(project_root))
                except ValueError:
                    rel_path = str(path)
                refs_by_path[rel_path] = SourceRef(adapter_name=self.name, path=rel_path)
        for rel_path in self._virtual_files:
            if rel_path.endswith(".md"):
                refs_by_path[rel_path] = SourceRef(adapter_name=self.name, path=rel_path)
        return [refs_by_path[path] for path in sorted(refs_by_path)]

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        if ref.path in self._virtual_files:
            fm, body = _parse_markdown_text(self._virtual_files[ref.path])
        else:
            path = Path(ref.path)
            if not path.is_absolute():
                path = Path.cwd() / path
            fm, body = _parse_markdown(path)
        raw: dict[str, Any] = dict(fm)
        raw["content"] = body
        raw["file_path"] = ref.path
        if "kind" not in raw and "type" in raw:
            raw["kind"] = raw["type"]
        if "canonical_id" not in raw and "id" in raw:
            raw["canonical_id"] = raw["id"]
        return raw
```

Add a text parser and use it from `_parse_markdown`.

```python
def _parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    return _parse_markdown_text(path.read_text(encoding="utf-8"))


def _parse_markdown_text(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return ({}, text)
    try:
        _, fm_raw, body = text.split("---\n", 2)
    except ValueError:
        return ({}, text)
    fm = yaml.safe_load(fm_raw) or {}
    if not isinstance(fm, dict):
        return ({}, body)
    return (fm, body.lstrip("\n"))
```

In `science-tool/src/science_tool/graph/sources.py`, change the function signature to:

```python
def load_project_sources(project_root: Path, markdown_overrides: dict[str, str] | None = None) -> ProjectSources:
```

Then change only the markdown adapter entry in the existing `adapters` list to
`MarkdownAdapter(virtual_files=markdown_overrides)`.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_storage_adapters/test_markdown.py science-tool/tests/test_load_project_sources_unified.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/storage_adapters/markdown.py science-tool/src/science_tool/graph/sources.py science-tool/tests/test_storage_adapters/test_markdown.py
git commit -m "feat(entities): support virtual markdown source validation"
```

### Task 2: Entity Core Policies, Slugs, IDs, And Rendering

**Files:**
- Create: `science-tool/src/science_tool/entities.py`
- Create: `science-tool/tests/_fixtures/entity_helpers.py`
- Create: `science-tool/tests/test_entities.py`

- [ ] **Step 1: Write failing core tests**

Create `science-tool/tests/_fixtures/entity_helpers.py` with the shared helper code from
the "Shared Test Fixtures" section.

Create `science-tool/tests/test_entities.py` with these tests.

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_tool.entities import (
    EntityCommandError,
    append_note_to_body,
    build_entity_markdown,
    derive_slug,
    generate_entity_id,
    path_for_entity,
    resolve_entity_ref,
    resolve_path_policy,
    validate_slug,
)


def test_builtin_path_policy_maps_core_kinds() -> None:
    assert resolve_path_policy("question").root == Path("doc/questions")
    assert resolve_path_policy("hypothesis").root == Path("specs/hypotheses")
    assert resolve_path_policy("discussion").filename == "date-local-part"
    assert resolve_path_policy("interpretation").filename == "date-local-part"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("What explains model family overlap?", "what-explains-model-family-overlap"),
        ("Model-family overlap: v2", "model-family-overlap-v2"),
        ("Café response -- Δ", "cafe-response"),
        ("the and what", "the-and-what"),
    ],
)
def test_derive_slug_is_deterministic(title: str, expected: str) -> None:
    assert derive_slug(title) == expected


def test_derive_slug_rejects_empty_or_too_short_values() -> None:
    with pytest.raises(EntityCommandError, match="requires --slug"):
        derive_slug("???")
    with pytest.raises(EntityCommandError, match="requires --slug"):
        derive_slug("Q?")


def test_derive_slug_truncates_to_72_characters_without_trailing_hyphen() -> None:
    slug = derive_slug(" ".join(["model"] * 30))
    assert len(slug) <= 72
    assert not slug.endswith("-")


def test_derive_slug_truncation_boundary_is_stable() -> None:
    assert derive_slug(("a" * 71) + " b") == "a" * 71


def test_validate_slug_rejects_bad_override() -> None:
    with pytest.raises(EntityCommandError, match="Invalid slug"):
        validate_slug("Bad_Slug")


def test_generate_entity_id_respects_existing_q_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    assert generate_entity_id(tmp_path, "question", "New Thing", None, None) == "question:q02-new-thing"


def test_generate_entity_id_respects_existing_numeric_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/01-existing.md",
        {"id": "question:01-existing", "type": "question", "title": "Existing"},
    )
    assert generate_entity_id(tmp_path, "question", "New Thing", None, None) == "question:02-new-thing"


def test_generate_entity_id_rejects_mixed_prefixes(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(tmp_path, "doc/questions/q01-a.md", {"id": "question:q01-a", "type": "question", "title": "A"})
    write_markdown_entity(tmp_path, "doc/questions/02-b.md", {"id": "question:02-b", "type": "question", "title": "B"})
    with pytest.raises(EntityCommandError, match="Mixed ID conventions"):
        generate_entity_id(tmp_path, "question", "New Thing", None, None)


def test_generate_entity_id_rejects_empty_siblings(tmp_path: Path) -> None:
    seed_project(tmp_path)
    with pytest.raises(EntityCommandError, match="No existing question siblings"):
        generate_entity_id(tmp_path, "question", "First Question", None, None)


def test_generate_entity_id_uses_slug_override(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    assert generate_entity_id(tmp_path, "question", "Ignored Title", None, "chosen-slug") == "question:q02-chosen-slug"


def test_path_for_entity_couples_filename_and_local_part() -> None:
    assert path_for_entity("question", "question:q02-new-thing", date(2026, 4, 28)) == Path("doc/questions/q02-new-thing.md")
    assert path_for_entity("discussion", "discussion:2026-04-28-topic", date(2026, 4, 28)) == Path("doc/discussions/2026-04-28-topic.md")


def test_path_for_entity_round_trips_dot_bearing_manual_id() -> None:
    assert path_for_entity("question", "question:q01.draft", date(2026, 4, 28)) == Path("doc/questions/q01.draft.md")


def test_resolve_entity_ref_distinguishes_dot_and_dash_local_parts(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01.draft.md",
        {"id": "question:q01.draft", "type": "question", "title": "Dot"},
    )
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-draft.md",
        {"id": "question:q01-draft", "type": "question", "title": "Dash"},
    )

    assert resolve_entity_ref(tmp_path, "q01.draft") == "question:q01.draft"
    assert resolve_entity_ref(tmp_path, "q01-draft") == "question:q01-draft"


def test_build_entity_markdown_uses_canonical_frontmatter_and_body() -> None:
    text = build_entity_markdown(
        kind="question",
        entity_id="question:q02-new-thing",
        title="New Thing",
        status="open",
        related=["hypothesis:h01"],
        source_refs=[],
        today=date(2026, 4, 28),
    )
    _, frontmatter_text, _ = text.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_text)
    assert frontmatter["id"] == "question:q02-new-thing"
    assert frontmatter["type"] == "question"
    assert frontmatter["status"] == "open"
    assert frontmatter["related"] == ["hypothesis:h01"]
    assert "# New Thing" in text
    assert "## Notes" in text


def test_append_note_to_body_creates_peer_notes_section() -> None:
    body = "# Title\n\n## Summary\n\nBody."
    updated = append_note_to_body(body, "- 2026-04-28: Clarified.")
    assert updated == "# Title\n\n## Summary\n\nBody.\n\n## Notes\n\n- 2026-04-28: Clarified."


def test_append_note_to_body_inserts_before_next_peer_heading() -> None:
    body = "# Title\n\n## Summary\n\nBody.\n\n## Notes\n\n- 2026-04-27: Earlier.\n\n## Evidence\n\nDetails."
    updated = append_note_to_body(body, "- 2026-04-28: Later.")
    assert "- 2026-04-28: Later.\n\n## Evidence" in updated
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py -q
```

Expected: FAIL because `science_tool.entities` does not exist.

- [ ] **Step 3: Implement core module**

Create `science-tool/src/science_tool/entities.py` with these public names and behavior.

```python
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml

EntityFilenamePolicy = Literal["local-part", "date-local-part"]


class EntityCommandError(ValueError):
    """Raised for user-correctable entity CLI errors."""


@dataclass(frozen=True)
class EntityPathPolicy:
    root: Path
    filename: EntityFilenamePolicy


_BUILTIN_MARKDOWN_POLICIES: dict[str, EntityPathPolicy] = {
    "question": EntityPathPolicy(root=Path("doc/questions"), filename="local-part"),
    "hypothesis": EntityPathPolicy(root=Path("specs/hypotheses"), filename="local-part"),
    "discussion": EntityPathPolicy(root=Path("doc/discussions"), filename="date-local-part"),
    "interpretation": EntityPathPolicy(root=Path("doc/interpretations"), filename="date-local-part"),
}
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_LOCAL_PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_ID_PREFIX_RE = re.compile(r"^(?P<prefix>[a-z]?)(?P<number>\d+)-", re.IGNORECASE)
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+.+$")
_NOTES_HEADING_RE = re.compile(r"^##\s+Notes\s*$")
```

Implement:

- `resolve_path_policy(kind: str) -> EntityPathPolicy`
- `derive_slug(title: str) -> str`
- `validate_slug(slug: str) -> str`
- `validate_entity_id(kind: str, entity_id: str) -> str`
- `generate_entity_id(project_root: Path, kind: str, title: str, entity_id: str | None, slug: str | None) -> str`
- `path_for_entity(kind: str, entity_id: str, today: date) -> Path`
- `build_entity_markdown(kind: str, entity_id: str, title: str, status: str, related: list[str], source_refs: list[str], today: date) -> str`
- `append_note_to_body(body: str, note_line: str) -> str`

Use this YAML renderer for the MVP so string quoting is deterministic in tests.

```python
def _dump_frontmatter(frontmatter: dict[str, object]) -> str:
    return yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False)
```

For `build_entity_markdown`, assert frontmatter by parsing the emitted YAML in tests instead of depending on PyYAML quote style. Do not hand-roll YAML serialization just to force quotes.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/entities.py science-tool/tests/_fixtures/entity_helpers.py science-tool/tests/test_entities.py
git commit -m "feat(entities): add source entity core policies"
```

### Task 3: Create With Prospective Validation

**Files:**
- Modify: `science-tool/src/science_tool/entities.py`
- Modify: `science-tool/tests/test_entities.py`

- [ ] **Step 1: Add failing create tests**

Append these tests to `science-tool/tests/test_entities.py`.

```python
from science_tool.entities import create_entity
from science_tool.graph.sources import load_project_sources


def test_create_entity_writes_question_source_and_loads_it(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing", "status": "open"},
    )

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="What explains model family overlap?",
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:q02-what-explains-model-family-overlap"
    assert result.path == tmp_path / "doc/questions/q02-what-explains-model-family-overlap.md"
    assert result.warnings == []
    sources = load_project_sources(tmp_path)
    assert "question:q02-what-explains-model-family-overlap" in {entity.canonical_id for entity in sources.entities}


def test_create_entity_rejects_existing_destination(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    with pytest.raises(EntityCommandError, match="already exists"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="Existing",
            entity_id="question:q01-existing",
            today=date(2026, 4, 28),
        )


def test_create_entity_with_unresolved_related_succeeds_with_warning(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="New Question",
        related=["hypothesis:h01"],
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:q02-new-question"
    assert any("unresolved_reference" in warning for warning in result.warnings)


def test_create_entity_rejects_concept_with_guidance(tmp_path: Path) -> None:
    seed_project(tmp_path)
    with pytest.raises(EntityCommandError, match="graph add concept"):
        create_entity(project_root=tmp_path, kind="concept", title="Local Concept", entity_id="concept:local")


def test_create_entity_prewrite_validation_removes_no_tmp_file(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    with pytest.raises(EntityCommandError, match="prefix"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="Bad",
            entity_id="hypothesis:h01-bad",
            today=date(2026, 4, 28),
        )
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_create_entity_prospective_audit_failure_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    calls = 0

    def fake_audit_project_sources(sources: object) -> tuple[list[dict[str, str]], bool]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return [], False
        return [
            {
                "check": "ambiguous_cross_kind_reference",
                "status": "fail",
                "source": "question:q02-new-question",
                "field": "related",
                "target": "q01",
                "details": "q01 resolves to multiple canonical identities",
            }
        ], True

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    with pytest.raises(EntityCommandError, match="ambiguous_cross_kind_reference"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="New Question",
            related=["q01"],
            today=date(2026, 4, 28),
        )

    assert not (tmp_path / "doc/questions/q02-new-question.md").exists()
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_create_entity_reports_preexisting_audit_failures_as_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    preexisting_row = {
        "check": "unresolved_reference",
        "status": "fail",
        "source": "question:q01-existing",
        "field": "related",
        "target": "hypothesis:h-missing",
        "details": "pre-existing missing hypothesis",
    }

    def fake_audit_project_sources(sources: object) -> tuple[list[dict[str, str]], bool]:
        return [preexisting_row], True

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="New Question",
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:q02-new-question"
    assert any("pre-existing audit failure" in warning for warning in result.warnings)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py -q
```

Expected: FAIL because `create_entity` is missing.

- [ ] **Step 3: Implement create and validation**

Add result dataclass and create helper.

```python
@dataclass(frozen=True)
class EntityWriteResult:
    entity_id: str
    path: Path
    warnings: list[str]
```

Implement `create_entity(project_root: Path, kind: str, title: str, *, entity_id: str | None = None, slug: str | None = None, explicit_path: Path | None = None, status: str | None = None, related: list[str] | None = None, source_refs: list[str] | None = None, today: date | None = None) -> EntityWriteResult`.

Implementation requirements:

- Resolve `project_root`.
- Reject `kind == "concept"` with message containing `graph add concept`.
- If `entity_id` is omitted, call `generate_entity_id`.
- If `slug` and `entity_id` are both supplied, raise `EntityCommandError`.
- Use `status or _DEFAULT_STATUS[kind]`, with defaults:
  - `question`: `open`
  - `hypothesis`: `candidate`
  - `discussion`: `active`
  - `interpretation`: `active`
- Validate built-in status values with `_STATUS_VALUES`.
- Derive `rel_path` from `explicit_path` or `path_for_entity`.
- Reject absolute `explicit_path`, paths with `..`, non-`.md` paths, or paths outside `doc`, `specs`, or `research/packages`.
- Reject existing destination path.
- Render markdown with canonical frontmatter and body.
- Write a staging file next to destination with suffix `.md.tmp`.
- Run baseline audit with `load_project_sources(project_root)` and prospective audit with `load_project_sources(project_root, markdown_overrides={rel_path: text})`.
- For create, do not call `load_project_sources` more than twice per write operation; the baseline and prospective loads are already the expensive path.
- Ignore the `has_failures` flag returned by `audit_project_sources`. Blocking is decided only by the row-set diff described below.
- Compare audit row tuples `(check, status, source, field, target, details)` between baseline and prospective.
- Print pre-existing baseline failure rows as warnings after a successful write with this prefix: `pre-existing audit failure: <check> on <source>: <details>`.
- Treat new `unresolved_reference` rows from the target entity in `related` or `source_refs` as warnings.
- Treat all other new failure rows as blocking and raise `EntityCommandError`.
- Use `os.replace(tmp_path, destination)` only after validation passes.
- Delete the tmp file in `except` and `finally` when it still exists.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py science-tool/tests/test_load_project_sources_unified.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/entities.py science-tool/tests/test_entities.py
git commit -m "feat(entities): create source-authored markdown entities"
```

### Task 4: Lookup, Edit, Note, And List Core

**Files:**
- Modify: `science-tool/src/science_tool/entities.py`
- Modify: `science-tool/tests/test_entities.py`

- [ ] **Step 1: Add failing operation tests**

Append these tests to `science-tool/tests/test_entities.py`.

```python
from science_tool.entities import (
    append_entity_note,
    edit_entity,
    find_entity,
    list_entities,
    resolve_entity_ref,
)


def test_resolve_entity_ref_accepts_canonical_and_unique_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(tmp_path, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha"})
    assert resolve_entity_ref(tmp_path, "question:q01-alpha") == "question:q01-alpha"
    assert resolve_entity_ref(tmp_path, "q01") == "question:q01-alpha"


def test_resolve_entity_ref_rejects_ambiguous_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(tmp_path, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha"})
    write_markdown_entity(tmp_path, "doc/questions/q01-beta.md", {"id": "question:q01-beta", "type": "question", "title": "Beta"})
    with pytest.raises(EntityCommandError, match="Ambiguous"):
        resolve_entity_ref(tmp_path, "q01")


def test_edit_entity_preserves_unknown_frontmatter_and_adds_related(tmp_path: Path) -> None:
    seed_project(tmp_path)
    path = write_markdown_entity(
        tmp_path,
        "doc/questions/q01-alpha.md",
        {
            "id": "question:q01-alpha",
            "type": "question",
            "title": "Alpha",
            "status": "open",
            "tags": ["biology"],
            "related": ["hypothesis:h01"],
            "source_refs": [],
            "created": "2026-04-27",
            "updated": "2026-04-27",
        },
        "# Alpha\n\n## Summary\n",
    )

    result = edit_entity(
        tmp_path,
        "question:q01-alpha",
        title="Alpha updated",
        related=["hypothesis:h02"],
        today=date(2026, 4, 28),
    )

    assert any("unresolved_reference" in warning for warning in result.warnings)
    text = path.read_text(encoding="utf-8")
    assert "Alpha updated" in text
    assert "tags:" in text
    assert "hypothesis:h01" in text
    assert "hypothesis:h02" in text
    assert "updated: '2026-04-28'" in text or 'updated: "2026-04-28"' in text or "updated: 2026-04-28" in text


def test_edit_entity_rejects_invalid_question_status(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(tmp_path, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"})
    with pytest.raises(EntityCommandError, match="Invalid status"):
        edit_entity(tmp_path, "question:q01-alpha", status="active")


def test_append_entity_note_creates_notes_section_and_updated_field(tmp_path: Path) -> None:
    seed_project(tmp_path)
    path = write_markdown_entity(
        tmp_path,
        "doc/questions/q01-alpha.md",
        {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
        "# Alpha\n\n## Summary\n\nBody.\n",
    )

    append_entity_note(tmp_path, "q01", "Clarified scope.", note_date=date(2026, 4, 28))

    text = path.read_text(encoding="utf-8")
    assert "## Notes\n\n- 2026-04-28: Clarified scope." in text
    assert "updated:" in text


def test_append_entity_note_rejects_blank(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(tmp_path, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha"})
    with pytest.raises(EntityCommandError, match="cannot be empty"):
        append_entity_note(tmp_path, "q01", "   ", note_date=date(2026, 4, 28))


def test_edit_entity_prospective_audit_failure_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    path = write_markdown_entity(
        tmp_path,
        "doc/questions/q01-alpha.md",
        {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
        "# Alpha\n",
    )
    original = path.read_text(encoding="utf-8")
    calls = 0

    def fake_audit_project_sources(sources: object) -> tuple[list[dict[str, str]], bool]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return [], False
        return [
            {
                "check": "ambiguous_cross_kind_reference",
                "status": "fail",
                "source": "question:q01-alpha",
                "field": "related",
                "target": "q01",
                "details": "q01 resolves to multiple canonical identities",
            }
        ], True

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    with pytest.raises(EntityCommandError, match="ambiguous_cross_kind_reference"):
        edit_entity(tmp_path, "q01", related=["q01"], today=date(2026, 4, 28))

    assert path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_append_entity_note_prospective_audit_failure_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    path = write_markdown_entity(
        tmp_path,
        "doc/questions/q01-alpha.md",
        {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
        "# Alpha\n",
    )
    original = path.read_text(encoding="utf-8")
    calls = 0

    def fake_audit_project_sources(sources: object) -> tuple[list[dict[str, str]], bool]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return [], False
        return [
            {
                "check": "invalid_registered_schema",
                "status": "fail",
                "source": "question:q01-alpha",
                "field": "type",
                "target": "question",
                "details": "forced failure",
            }
        ], True

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    with pytest.raises(EntityCommandError, match="invalid_registered_schema"):
        append_entity_note(tmp_path, "q01", "Clarified.", note_date=date(2026, 4, 28))

    assert path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_list_entities_filters_kind_and_exact_status(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(tmp_path, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"})
    write_markdown_entity(tmp_path, "doc/questions/q02-beta.md", {"id": "question:q02-beta", "type": "question", "title": "Beta", "status": "answered"})
    rows = list_entities(tmp_path, kind="question", status="answered")
    assert [row["id"] for row in rows] == ["question:q02-beta"]


def test_list_entities_orders_by_canonical_id(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(tmp_path, "doc/questions/q02-beta.md", {"id": "question:q02-beta", "type": "question", "title": "Beta", "status": "open"})
    write_markdown_entity(tmp_path, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"})
    rows = list_entities(tmp_path, kind="question")
    assert [row["id"] for row in rows] == ["question:q01-alpha", "question:q02-beta"]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py -q
```

Expected: FAIL because lookup/edit/note/list helpers are missing.

- [ ] **Step 3: Implement operations**

Add dataclass:

```python
@dataclass(frozen=True)
class EntityLocation:
    entity_id: str
    kind: str
    title: str
    status: str
    path: Path
    rel_path: str
    frontmatter: dict[str, object]
    body: str
```

Implement:

- `find_entity(project_root: Path, ref: str) -> EntityLocation`
- `resolve_entity_ref(project_root: Path, ref: str) -> str`
- `edit_entity(project_root: Path, ref: str, *, title: str | None = None, status: str | None = None, related: list[str] | None = None, source_refs: list[str] | None = None, updated: date | None = None, today: date | None = None) -> EntityWriteResult`
- `append_entity_note(project_root: Path, ref: str, note: str, note_date: date | None = None) -> EntityWriteResult`
- `list_entities(project_root: Path, kind: str | None = None, status: str | None = None) -> list[dict[str, str]]`

Parsing and writing rules:

- Use the existing markdown parse helper behavior: frontmatter between `---` fences, body after the second fence.
- `find_entity` raises `EntityCommandError` with a message listing the searched source roots when no entity matches.
- Preserve unknown frontmatter keys by starting from the parsed dict.
- On edit, update only requested scalar fields.
- Additive list updates append unique values in order.
- Always set or add `updated` to the supplied date or `date.today()`.
- Re-render through `yaml.safe_dump(sort_keys=False)`.
- Reuse the same prospective validation helper from `create_entity`.
- Use the same `.md.tmp` staging file plus `os.replace` pattern as `create_entity` for `edit_entity` and `append_entity_note`.
- `edit_entity` and `append_entity_note` may call `load_project_sources` three times in the MVP: once to locate the entity, once for baseline audit, and once for prospective audit.
- Sort `list_entities` rows alphabetically by canonical id.

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/entities.py science-tool/tests/test_entities.py
git commit -m "feat(entities): edit list and note source entities"
```

### Task 5: Generic Entity CLI

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Create: `science-tool/tests/test_entities_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `science-tool/tests/test_entities_cli.py` with these tests.

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_tool.cli import main


def test_entity_create_question_writes_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(root, "doc/questions/q01-existing.md", {"id": "question:q01-existing", "type": "question", "title": "Existing", "status": "open"})

        result = runner.invoke(main, ["entity", "create", "question", "New Question"])

        assert result.exit_code == 0, result.output
        assert "question:q02-new-question" in result.output
        assert Path("doc/questions/q02-new-question.md").is_file()


def test_entity_create_with_unresolved_related_prints_warning() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(root, "doc/questions/q01-existing.md", {"id": "question:q01-existing", "type": "question", "title": "Existing", "status": "open"})

        result = runner.invoke(main, ["entity", "create", "question", "New Question", "--related", "hypothesis:h01"])

        assert result.exit_code == 0, result.output
        assert "WARNING" in result.output


def test_entity_show_finds_source_entity_by_shorthand() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(root, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"})

        result = runner.invoke(main, ["entity", "show", "q01"])

        assert result.exit_code == 0, result.output
        assert "question:q01-alpha" in result.output
        assert "Alpha" in result.output


def test_entity_show_emits_body_content() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(
            root,
            "doc/questions/q01-alpha.md",
            {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"},
            "# Alpha\n\n## Summary\n\nBody content.\n",
        )

        result = runner.invoke(main, ["entity", "show", "q01"])

        assert result.exit_code == 0, result.output
        assert "## Summary" in result.output
        assert "Body content." in result.output


def test_entity_show_json_outputs_machine_readable_payload() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(root, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"})

        result = runner.invoke(main, ["entity", "show", "q01", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload == {
            "id": "question:q01-alpha",
            "kind": "question",
            "title": "Alpha",
            "status": "open",
            "path": "doc/questions/q01-alpha.md",
            "related": [],
            "source_refs": [],
            "body": "",
        }


def test_entity_edit_adds_related_without_replacing_existing() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        path = write_markdown_entity(root, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open", "related": ["hypothesis:h01"]})

        result = runner.invoke(main, ["entity", "edit", "q01", "--related", "hypothesis:h02"])

        assert result.exit_code == 0, result.output
        assert "WARNING" in result.output
        text = path.read_text(encoding="utf-8")
        assert "hypothesis:h01" in text
        assert "hypothesis:h02" in text


def test_entity_note_adds_dated_note() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        path = write_markdown_entity(root, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"}, "# Alpha\n")

        result = runner.invoke(main, ["entity", "note", "q01", "Clarified.", "--date", "2026-04-28"])

        assert result.exit_code == 0, result.output
        assert "Added note to question:q01-alpha (2026-04-28)" in result.output
        assert "- 2026-04-28: Clarified." in path.read_text(encoding="utf-8")


def test_entity_list_filters_exact_status() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(root, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"})
        write_markdown_entity(root, "doc/questions/q02-beta.md", {"id": "question:q02-beta", "type": "question", "title": "Beta", "status": "answered"})

        result = runner.invoke(main, ["entity", "list", "--kind", "question", "--status", "answered", "--format", "json"])

        assert result.exit_code == 0, result.output
        assert "question:q02-beta" in result.output
        assert "question:q01-alpha" not in result.output
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities_cli.py -q
```

Expected: FAIL because `entity` command group is missing.

- [ ] **Step 3: Implement CLI group**

In `science-tool/src/science_tool/cli.py`, import helpers.

```python
from science_tool.entities import (
    EntityCommandError,
    append_entity_note,
    create_entity,
    edit_entity,
    find_entity,
    list_entities,
)
```

Add a Click group near the existing `tasks` group.

```python
@main.group("entity")
def entity_group() -> None:
    """Create, edit, note, list, and inspect source-authored entities."""
```

Implement commands:

- `entity create <kind> <title>` with repeatable `--related` and `--source-ref`, plus `--id`, `--slug`, `--path`, `--status`.
- `entity show <ref>` prints id, type, title, status, path, related, source refs, then body.
- `entity show <ref> --format json` prints a JSON object containing `id`, `kind`, `title`, `status`, `path`, `related`, `source_refs`, and `body`.
- `entity edit <ref>` supports `--title`, `--status`, repeatable `--related`, repeatable `--source-ref`, `--updated`.
- `entity note <ref> <note>` supports `--date`.
- `entity list` uses `emit_query_rows` for table/json.

Catch `EntityCommandError` and re-raise `click.ClickException(str(exc))`. Print each `EntityWriteResult.warning` as `WARNING: <warning text>` after successful writes.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py science-tool/tests/test_entities_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_entities_cli.py
git commit -m "feat(entities): add generic entity CLI"
```

### Task 6: Typed Wrappers And Graph Add Guidance

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/tests/test_entities_cli.py`

- [ ] **Step 1: Add failing wrapper tests**

Append these tests to `science-tool/tests/test_entities_cli.py`.

```python
def test_question_create_wrapper_delegates_to_entity_create() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(root, "doc/questions/q01-existing.md", {"id": "question:q01-existing", "type": "question", "title": "Existing", "status": "open"})

        result = runner.invoke(main, ["question", "create", "Wrapper Question", "--slug", "wrapper"])

        assert result.exit_code == 0, result.output
        assert "question:q02-wrapper" in result.output
        assert Path("doc/questions/q02-wrapper.md").is_file()


def test_discussion_focus_maps_to_related() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            ["discussion", "create", "Planning", "--id", "discussion:2026-04-28-planning", "--focus", "question:q01-alpha"],
        )

        assert result.exit_code == 0, result.output
        assert "question:q01-alpha" in Path("doc/discussions/2026-04-28-planning.md").read_text(encoding="utf-8")


def test_interpretation_input_maps_to_source_refs() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            ["interpretation", "create", "Result", "--id", "interpretation:2026-04-28-result", "--input", "results/run-1"],
        )

        assert result.exit_code == 0, result.output
        assert "results/run-1" in Path("doc/interpretations/2026-04-28-result.md").read_text(encoding="utf-8")


def test_graph_add_question_mentions_entity_create() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        init = runner.invoke(main, ["graph", "init"])
        assert init.exit_code == 0, init.output

        result = runner.invoke(
            main,
            [
                "graph",
                "add",
                "question",
                "q01-legacy",
                "--text",
                "Legacy question",
                "--source",
                "manual:test",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "entity create question" in result.output
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities_cli.py -q
```

Expected: FAIL because typed wrapper groups and graph guidance are missing.

- [ ] **Step 3: Implement wrappers**

Add command groups:

```python
@main.group("question")
def question_group() -> None:
    """Question source commands."""
```

Repeat for `hypothesis`, `discussion`, and `interpretation`. Each `create` command calls `create_entity` with the fixed kind. Map:

- `discussion create --focus` to `related=[focus]`
- `interpretation create --input` to `source_refs=[input]`

Add output line `Created <id> at <path>`.

- [ ] **Step 4: Add graph add soft-deprecation output**

For `graph_add_question`, `graph_add_hypothesis`, `graph_add_discussion`, and `graph_add_interpretation`, append one extra `click.echo` line after the existing success output:

```python
click.echo("Tip: use `science-tool entity create question <title>` for durable source-authored project work.")
```

Use the matching kind name in each message.

- [ ] **Step 5: Run wrapper tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_entities_cli.py
git commit -m "feat(entities): add typed source entity wrappers"
```

### Task 7: Entity Neighbors And Staleness

**Files:**
- Modify: `science-tool/src/science_tool/entities.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/tests/test_entities.py`
- Modify: `science-tool/tests/test_entities_cli.py`

- [ ] **Step 1: Add failing staleness and neighbor tests**

Append to `science-tool/tests/test_entities.py`.

```python
import os

from science_tool.entities import graph_is_stale


def test_graph_is_stale_when_source_newer_than_graph(tmp_path: Path) -> None:
    seed_project(tmp_path)
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text("", encoding="utf-8")
    source = write_markdown_entity(tmp_path, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha"})
    os.utime(graph_path, (1, 1))
    os.utime(source, (2, 2))
    assert graph_is_stale(tmp_path, graph_path) is True
```

Append to `science-tool/tests/test_entities_cli.py`.

```python
def test_entity_neighbors_source_only_warns_and_returns_no_rows() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(root, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"})
        graph = Path("knowledge/graph.trig")
        graph.parent.mkdir(parents=True)
        graph.write_text("@prefix sci: <http://example.org/science/vocab/> .\n", encoding="utf-8")
        os.utime(graph, (1, 1))
        os.utime(Path("doc/questions/q01-alpha.md"), (2, 2))

        result = runner.invoke(main, ["entity", "neighbors", "question:q01-alpha", "--format", "json"])

        assert result.exit_code == 0, result.output
        assert "WARNING" in result.output
        assert "[]" in result.output


def test_entity_neighbors_missing_graph_fails_cleanly() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)
        write_markdown_entity(root, "doc/questions/q01-alpha.md", {"id": "question:q01-alpha", "type": "question", "title": "Alpha", "status": "open"})

        result = runner.invoke(main, ["entity", "neighbors", "question:q01-alpha"])

        assert result.exit_code != 0
        assert "Graph file not found: knowledge/graph.trig" in result.output
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py science-tool/tests/test_entities_cli.py -q
```

Expected: FAIL because `graph_is_stale` and `entity neighbors` are missing.

- [ ] **Step 3: Implement staleness helper**

In `science-tool/src/science_tool/entities.py`, add:

```python
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter


def graph_is_stale(project_root: Path, graph_path: Path) -> bool:
    if not graph_path.exists():
        return True
    markdown_paths = [
        path
        for root in MarkdownAdapter().scan_roots
        for path in project_root.glob(f"{root}/**/*.md")
    ]
    source_paths = [*markdown_paths, *project_root.glob("tasks/**/*.md")]
    if not source_paths:
        return False
    newest_source_mtime = max(path.stat().st_mtime for path in source_paths)
    return newest_source_mtime > graph_path.stat().st_mtime
```

- [ ] **Step 4: Implement CLI neighbors**

In `science-tool/src/science_tool/cli.py`, `entity neighbors` should:

- Resolve the entity with `find_entity` first.
- If `graph_is_stale(Path.cwd(), DEFAULT_GRAPH_PATH)`, emit `WARNING: graph materialization may be stale; results below could miss recent edits.`
- Call `query_neighborhood(DEFAULT_GRAPH_PATH, center=<canonical id>, hops=hops, graph_layer="graph/knowledge", limit=200)`.
- Let `query_neighborhood` propagate the existing `ClickException("Graph file not found: knowledge/graph.trig")` from `_load_dataset` when the graph file is absent.
- Expect `query_neighborhood` to return `[]` for entities with no edges in the graph; no special source-only branch is needed.
- Format rows with `emit_query_rows`.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py science-tool/tests/test_entities_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/entities.py science-tool/src/science_tool/cli.py science-tool/tests/test_entities.py science-tool/tests/test_entities_cli.py
git commit -m "feat(entities): show graph neighbors with staleness warnings"
```

### Task 8: Materialization Integration And Final Verification

**Files:**
- Modify: `science-tool/tests/test_graph_materialize.py`
- Review: `science-tool/src/science_tool/entities.py`
- Review: `science-tool/src/science_tool/cli.py`

- [ ] **Step 1: Add materialization integration test**

Add a focused test to `science-tool/tests/test_graph_materialize.py`.

Add imports if they are not already present in the file:

```python
from rdflib import Dataset
from rdflib.namespace import RDF

from science_tool.graph.store import PROJECT_NS, add_hypothesis
```

```python
def test_source_authored_hypothesis_and_graph_added_hypothesis_do_not_double_count(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: materialize-entities\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    (tmp_path / "specs" / "hypotheses").mkdir(parents=True)
    (tmp_path / "specs" / "hypotheses" / "h01-source.md").write_text(
        "---\n"
        'id: "hypothesis:h01-source"\n'
        'type: "hypothesis"\n'
        'title: "Source hypothesis"\n'
        'status: "active"\n'
        "---\n"
        "# Hypothesis: Source hypothesis\n",
        encoding="utf-8",
    )

    graph_path = materialize_graph(tmp_path)
    add_hypothesis(graph_path=graph_path, title="Graph hypothesis", hypothesis_id="h02-graph")
    graph_path = materialize_graph(tmp_path)

    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    source_uri = PROJECT_NS["hypothesis/h01-source"]
    source_type_triples = list(knowledge.triples((source_uri, RDF.type, None)))

    assert len(source_type_triples) == 1
```

- [ ] **Step 2: Run integration tests**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_graph_materialize.py science-tool/tests/test_entities.py science-tool/tests/test_entities_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Run formatting and lint**

Run:

```bash
uv run --frozen ruff format science-tool/src/science_tool/entities.py science-tool/src/science_tool/cli.py science-tool/src/science_tool/graph/storage_adapters/markdown.py science-tool/src/science_tool/graph/sources.py science-tool/tests/_entity_helpers.py science-tool/tests/test_entities.py science-tool/tests/test_entities_cli.py science-tool/tests/test_storage_adapters/test_markdown.py science-tool/tests/test_graph_materialize.py
uv run --frozen ruff check .
uv run --frozen pyright
```

Expected: all commands exit 0.

- [ ] **Step 4: Run full focused test suite**

Run:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py science-tool/tests/test_entities_cli.py science-tool/tests/test_storage_adapters/test_markdown.py science-tool/tests/test_load_project_sources_unified.py science-tool/tests/test_graph_materialize.py -q
```

Expected: PASS.

- [ ] **Step 5: Manual CLI smoke**

Run:

```bash
repo=/mnt/ssd/Dropbox/science
tmpdir=$(mktemp -d)
cd "$tmpdir"
printf 'name: smoke\nknowledge_profiles: {local: local}\n' > science.yaml
mkdir -p doc/questions
printf '%s\n' '---' 'id: "question:q01-existing"' 'type: "question"' 'title: "Existing"' 'status: "open"' '---' '# Existing' > doc/questions/q01-existing.md
uv run --project "$repo/science-tool" --frozen science-tool entity create question "What explains model family overlap?"
uv run --project "$repo/science-tool" --frozen science-tool entity note q02 "Clarified scope." --date 2026-04-28
uv run --project "$repo/science-tool" --frozen science-tool entity show q02
```

Expected output includes `question:q02-what-explains-model-family-overlap` and `- 2026-04-28: Clarified scope.`

- [ ] **Step 6: Commit**

```bash
git add science-tool/tests/test_graph_materialize.py
git commit -m "test(entities): cover source entity materialization"
```

## Final Verification

- [ ] Run focused tests:

```bash
uv run --frozen pytest science-tool/tests/test_entities.py science-tool/tests/test_entities_cli.py science-tool/tests/test_storage_adapters/test_markdown.py science-tool/tests/test_load_project_sources_unified.py science-tool/tests/test_graph_materialize.py -q
```

- [ ] Run project quality checks:

```bash
uv run --frozen ruff check .
uv run --frozen pyright
```

- [ ] Inspect git history:

```bash
git log --oneline -8
git status --short
```

Expected: recent commits correspond to the tasks above and `git status --short` is empty.

## Spec Coverage Checklist

- [ ] Generic `entity create/show/edit/note/list/neighbors` implemented.
- [ ] Typed wrappers implemented for question, hypothesis, discussion, interpretation.
- [ ] Path policy hardcoded in `science_tool/entities.py`.
- [ ] Slug derivation and `--slug` override implemented.
- [ ] ID convention inference handles `qNN` and `NN`, rejects mixed and empty sibling sets.
- [ ] Filename local part equals canonical id local part.
- [ ] Frontmatter schema uses `id`, `type`, `title`, `status`, `related`, `source_refs`, `created`, `updated`.
- [ ] Unknown frontmatter fields survive edit/note.
- [ ] Validation uses virtual prospective markdown plus `.md.tmp` staging and atomic replace.
- [ ] Create/edit/note rollback tests cover prospective audit failures after staging.
- [ ] New unresolved target refs warn; structural audit errors block.
- [ ] Pre-existing audit failures are reported as warnings and do not block.
- [ ] `audit_project_sources(...)[1]` / `has_failures` is ignored in favor of row-set diff semantics.
- [ ] `## Notes` grammar implemented.
- [ ] Additive edit semantics implemented for `related` and `source_refs`.
- [ ] `entity create concept` rejected with guidance.
- [ ] `entity list --status` exact-match filtering implemented.
- [ ] `entity list` orders rows by canonical id.
- [ ] `entity show --format json` implemented.
- [ ] `entity neighbors` warns on stale graph and has no source fallback.
- [ ] Overlapping `graph add` commands emit source-authoring guidance.

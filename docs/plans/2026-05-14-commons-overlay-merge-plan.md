# Phase D1: Commons Overlay Merge Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-time project-overlay merge to `science_tool.commons` — a project carries a thin overlay file for a commons entity, and `science commons show <id> --project <name>` returns the canonical entity with the overlay's project-specific fields and body sections merged in per the `science:merge` policy.

**Architecture:** A new single module `science_tool/commons/overlay.py` holds everything: `OverlayAdapter` (discover/parse/validate overlay files), policy-driven `merge_entity()`, the `resolve_entity()` entry point, and `validate_project_overlays()`. The merge is fully data-driven — it reads the field→policy map from Phase A's `science_model.entity_schema` (`read_merge_policy`, `read_overlay_merge_policy`) so new annotated schema fields need no code change here. Git `pin_version` resolution is deferred to Phase E; D1 parses the field and warns when it is set.

**Tech Stack:** Python 3.11+, Click 8.1, Pydantic 2, pyyaml, pytest, `uv run pytest`. No new third-party dependencies.

**Spec:** `docs/plans/2026-05-14-commons-overlay-merge-design.md`

**Deviations from spec:** none.

**Conventions:**
- All commands run from the repo's `science/` directory: `cd ~/d/science/science` first (the package and tests live there).
- Test invocation: `uv run pytest <path>::<name> -v`.
- One commit per task. TDD: failing test first, minimal implementation, green, commit.
- All new error classes subclass the existing `science_tool.commons.errors.CommonsError`.

---

## Task 1: Phase D1 error classes

**Files:**
- Modify: `science/src/science_tool/commons/errors.py`
- Test: `science/tests/test_commons_errors.py` (create if absent; otherwise append)

- [ ] **Step 1: Write the failing test**

Create or append to `science/tests/test_commons_errors.py`:

```python
"""Tests for science_tool.commons.errors — Phase D1 additions."""
from __future__ import annotations

from pathlib import Path

from science_tool.commons.errors import (
    CommonsError,
    OverlayMergeError,
    OverlayValidationError,
    ProjectDirectoryMissingError,
    ProjectNotRegisteredError,
)


def test_project_not_registered_error_carries_name() -> None:
    exc = ProjectNotRegisteredError("protein-landscape")
    assert isinstance(exc, CommonsError)
    assert exc.name == "protein-landscape"
    assert "protein-landscape" in str(exc)


def test_project_directory_missing_error_carries_project_and_path() -> None:
    exc = ProjectDirectoryMissingError("protein-landscape", Path("/gone/pl"))
    assert isinstance(exc, CommonsError)
    assert exc.project == "protein-landscape"
    assert exc.path == Path("/gone/pl")
    assert "/gone/pl" in str(exc)


def test_overlay_validation_error_carries_cause() -> None:
    cause = ValueError("schema boom")
    exc = OverlayValidationError(
        Path("/p/doc/papers/Adams2025.md"),
        canonical_id="paper:Adams2025",
        cause=cause,
    )
    assert isinstance(exc, CommonsError)
    assert exc.overlay_path == Path("/p/doc/papers/Adams2025.md")
    assert exc.canonical_id == "paper:Adams2025"
    assert exc.cause is cause
    assert "schema boom" in str(exc)
    assert "Adams2025.md" in str(exc)


def test_overlay_merge_error_carries_field_and_id() -> None:
    exc = OverlayMergeError(field="title", canonical_id="paper:Adams2025")
    assert isinstance(exc, CommonsError)
    assert exc.field == "title"
    assert exc.canonical_id == "paper:Adams2025"
    assert "title" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_errors.py -v`
Expected: FAIL with `ImportError: cannot import name 'OverlayMergeError'` (or similar).

- [ ] **Step 3: Write minimal implementation**

Append to `science/src/science_tool/commons/errors.py`:

```python
class ProjectNotRegisteredError(CommonsError):
    """A `--project <name>` value has no entry in config.yaml `projects[]`."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"project {name!r} is not registered; check `projects:` in "
            f"the global config"
        )
        self.name = name


class ProjectDirectoryMissingError(CommonsError):
    """A registered project's path is not a directory on disk."""

    def __init__(self, project: str, path: Path) -> None:
        super().__init__(
            f"registered project {project!r} directory not found at {path}"
        )
        self.project = project
        self.path = path


class OverlayValidationError(CommonsError):
    """A project overlay file failed parsing or schema validation, or its
    `overlay_of` does not resolve to a real canonical entity."""

    def __init__(
        self,
        overlay_path: Path,
        *,
        canonical_id: str | None,
        cause: Exception,
    ) -> None:
        super().__init__(f"overlay {overlay_path} failed: {cause}")
        self.overlay_path = overlay_path
        self.canonical_id = canonical_id
        self.cause = cause


class OverlayMergeError(CommonsError):
    """Defense-in-depth: a `replace`/`forbidden` field reached `merge_entity`
    despite overlay-schema validation. Indicates a corrupt overlay schema or a
    validation bypass, never a normal user path."""

    def __init__(self, *, field: str, canonical_id: str) -> None:
        super().__init__(
            f"overlay for {canonical_id} sets field {field!r} whose merge "
            f"policy forbids overlay contribution"
        )
        self.field = field
        self.canonical_id = canonical_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_errors.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/errors.py science/tests/test_commons_errors.py
git commit -m "feat(commons): Phase D1 error classes"
```

---

## Task 2: `resolve_project_root` in config.py

**Files:**
- Modify: `science/src/science_tool/commons/config.py`
- Test: `science/tests/test_commons_config.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_config.py`:

```python
def test_resolve_project_root_returns_registered_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from science_tool.commons.config import resolve_project_root

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump(
            {
                "projects": [
                    {
                        "path": "/home/me/d/protein-landscape",
                        "name": "protein-landscape",
                        "registered": "2026-05-14",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert resolve_project_root("protein-landscape") == Path(
        "/home/me/d/protein-landscape"
    )


def test_resolve_project_root_unknown_name_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from science_tool.commons.config import resolve_project_root
    from science_tool.commons.errors import ProjectNotRegisteredError

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump({"projects": []}), encoding="utf-8"
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(ProjectNotRegisteredError, match="nope"):
        resolve_project_root("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_config.py -k resolve_project_root -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_project_root'`.

- [ ] **Step 3: Write minimal implementation**

Append to `science/src/science_tool/commons/config.py` (the `from science_tool.commons.errors import CommonsError` import already exists at the top; extend it to also import `ProjectNotRegisteredError`):

Change the existing import line:
```python
from science_tool.commons.errors import CommonsError
```
to:
```python
from science_tool.commons.errors import CommonsError, ProjectNotRegisteredError
```

Then append this function:

```python
def resolve_project_root(name: str) -> Path:
    """Look up a registered project by name and return its root path.

    Reads `projects[]` from the global config. Raises ProjectNotRegisteredError
    if no entry matches `name`. Does not assert the path exists on disk — that
    is checked by callers (resolve_entity / validate_project_overlays), which
    raise ProjectDirectoryMissingError instead.
    """
    from science_tool.registry.config import load_global_config

    cfg = load_global_config()
    for project in cfg.projects:
        if project.name == name:
            return Path(project.path).expanduser()
    raise ProjectNotRegisteredError(name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_config.py -k resolve_project_root -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/config.py science/tests/test_commons_config.py
git commit -m "feat(commons): resolve_project_root — registered-name project lookup"
```

---

## Task 3: `overlay.py` module + `_read_markdown_body` helper + overlay fixtures

**Files:**
- Create: `science/src/science_tool/commons/overlay.py`
- Create: `science/tests/fixtures/overlays/proj-alpha/doc/papers/Adams2025.md`
- Create: `science/tests/fixtures/overlays/proj-alpha/doc/datasets/cath-domains.md`
- Create: `science/tests/fixtures/overlays/proj-broken/doc/papers/Adams2025.md`
- Create: `science/tests/fixtures/overlays/proj-broken/doc/topics/nonexistent-topic.md`
- Test: `science/tests/test_commons_overlay.py` (create)

- [ ] **Step 1: Create the overlay fixtures**

Create `science/tests/fixtures/overlays/proj-alpha/doc/papers/Adams2025.md`:

```markdown
---
id: "paper:Adams2025"
overlay_of: "paper:Adams2025"
relevance: "H2 — supports the homology-split argument"
hypothesis_links: ["H2", "H4"]
project_tags: ["high-priority"]
tags: ["overlay-added"]
---

## Project-Specific Notes

Adams2025 anchors the homology-split argument in this project.
```

Create `science/tests/fixtures/overlays/proj-alpha/doc/datasets/cath-domains.md`:

```markdown
---
id: "dataset:cath-domains"
overlay_of: "dataset:cath-domains"
relevance: "primary structural reference"
task_links: ["t012"]
---

## Project Usage

Used for the domain-classification baseline.
```

Create `science/tests/fixtures/overlays/proj-broken/doc/papers/Adams2025.md` (sets `title`, which the overlay schema's `additionalProperties: false` rejects):

```markdown
---
id: "paper:Adams2025"
overlay_of: "paper:Adams2025"
title: "illegal — overlays cannot set title"
---

## Notes
```

Create `science/tests/fixtures/overlays/proj-broken/doc/topics/nonexistent-topic.md` (schema-valid, but `overlay_of` resolves to no canonical entity):

```markdown
---
id: "topic:nonexistent-topic"
overlay_of: "topic:nonexistent-topic"
relevance: "this canonical entity does not exist in the commons store"
---

## Notes
```

- [ ] **Step 2: Write the failing test**

Create `science/tests/test_commons_overlay.py`:

```python
"""Tests for science_tool.commons.overlay."""
from __future__ import annotations

from pathlib import Path


def test_read_markdown_body_returns_text_after_frontmatter(tmp_path: Path) -> None:
    from science_tool.commons.overlay import _read_markdown_body

    md = tmp_path / "doc.md"
    md.write_text(
        "---\n"
        "id: \"paper:X\"\n"
        "---\n"
        "\n"
        "# Heading\n"
        "\n"
        "Body text.\n",
        encoding="utf-8",
    )
    body = _read_markdown_body(md)
    assert body == "\n# Heading\n\nBody text.\n"


def test_read_markdown_body_no_frontmatter_returns_whole_file(tmp_path: Path) -> None:
    from science_tool.commons.overlay import _read_markdown_body

    md = tmp_path / "plain.md"
    md.write_text("# Just a heading\n\ntext\n", encoding="utf-8")
    assert _read_markdown_body(md) == "# Just a heading\n\ntext\n"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.overlay'`.

- [ ] **Step 4: Write minimal implementation**

Create `science/src/science_tool/commons/overlay.py`:

```python
"""Project-overlay discovery and read-time merge for the commons store.

A project carries a thin overlay file (`<project>/doc/<type>/<slug>.md`) for a
commons entity. This module discovers, parses, and validates overlay files,
and merges them onto the canonical entity per the schema's `science:merge`
policy. Git `pin_version` resolution is deferred to Phase E — D1 parses the
field but the merge always uses the live canonical entity.

See docs/plans/2026-05-14-commons-overlay-merge-design.md.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.markdown_utils import parse_frontmatter


def _read_markdown_body(path: Path) -> str:
    """Return the markdown body of `path` — everything after the frontmatter."""
    _, body_start = parse_frontmatter(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[body_start - 1:])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/overlay.py science/tests/test_commons_overlay.py science/tests/fixtures/overlays
git commit -m "feat(commons): overlay.py module + _read_markdown_body + fixtures"
```

---

## Task 4: `OverlayRecord` + `OverlayAdapter.load`

**Files:**
- Modify: `science/src/science_tool/commons/overlay.py`
- Test: `science/tests/test_commons_overlay.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_overlay.py`:

```python
import pytest

_OVERLAYS = Path(__file__).parent / "fixtures" / "overlays"


def test_overlay_adapter_load_hit() -> None:
    from science_tool.commons.overlay import OverlayAdapter, OverlayRecord

    root = _OVERLAYS / "proj-alpha"
    rec = OverlayAdapter(root, "proj-alpha").load("paper:Adams2025")
    assert isinstance(rec, OverlayRecord)
    assert rec.canonical_id == "paper:Adams2025"
    assert rec.type == "paper"
    assert rec.slug == "Adams2025"
    assert rec.project == "proj-alpha"
    assert rec.project_root == root
    assert rec.overlay_path == root / "doc" / "papers" / "Adams2025.md"
    assert rec.frontmatter["relevance"].startswith("H2")
    assert "Project-Specific Notes" in rec.body
    assert rec.pin_version is None
    assert rec.pin_effective_version is None


def test_overlay_adapter_load_miss_returns_none() -> None:
    from science_tool.commons.overlay import OverlayAdapter

    root = _OVERLAYS / "proj-alpha"
    assert OverlayAdapter(root, "proj-alpha").load("paper:NoSuchPaper") is None


def test_overlay_adapter_load_schema_failure_raises_with_cause() -> None:
    from science_tool.commons.errors import OverlayValidationError
    from science_tool.commons.overlay import OverlayAdapter

    root = _OVERLAYS / "proj-broken"
    with pytest.raises(OverlayValidationError) as excinfo:
        OverlayAdapter(root, "proj-broken").load("paper:Adams2025")
    assert excinfo.value.canonical_id == "paper:Adams2025"
    assert excinfo.value.cause is not None


def test_overlay_adapter_load_malformed_id_raises() -> None:
    from science_tool.commons.errors import OverlayValidationError
    from science_tool.commons.overlay import OverlayAdapter

    root = _OVERLAYS / "proj-alpha"
    with pytest.raises(OverlayValidationError):
        OverlayAdapter(root, "proj-alpha").load("not-a-canonical-id")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k overlay_adapter_load -v`
Expected: FAIL with `ImportError: cannot import name 'OverlayAdapter'`.

- [ ] **Step 3: Write minimal implementation**

Add to `science/src/science_tool/commons/overlay.py` — extend the imports and add the dataclass + adapter:

Replace the import block at the top of the file with:

```python
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_model.entity_schema import EntityValidationError, EntityValidator

from science_tool.commons.errors import OverlayValidationError
from science_tool.markdown_utils import parse_frontmatter

_TYPE_TO_DIR = {
    "dataset": "datasets",
    "paper": "papers",
    "topic": "topics",
    "theme": "themes",
}
```

Then add below `_read_markdown_body`:

```python
@dataclass(frozen=True, slots=True)
class OverlayRecord:
    """One validated project overlay for a commons entity."""

    canonical_id: str
    type: str
    slug: str
    project: str
    project_root: Path
    overlay_path: Path
    frontmatter: dict[str, Any]
    body: str
    pin_version: str | None
    pin_effective_version: str | None


class OverlayAdapter:
    """Discover, parse, and validate overlay files in one registered project."""

    def __init__(
        self,
        project_root: Path,
        project: str,
        validator: EntityValidator | None = None,
    ) -> None:
        self._project_root = project_root
        self._project = project
        self._validator = validator or EntityValidator()

    def load(self, canonical_id: str) -> OverlayRecord | None:
        """Load the overlay for `canonical_id`, or None if no overlay file exists.

        Raises OverlayValidationError on a malformed id, unparseable frontmatter,
        a schema failure, or an `overlay_of` that does not match the path-derived
        canonical id.
        """
        type_dir, slug = self._split_id(canonical_id)
        overlay_path = self._project_root / "doc" / type_dir / f"{slug}.md"
        if not overlay_path.is_file():
            return None
        return self._build(canonical_id, overlay_path)

    def _split_id(self, canonical_id: str) -> tuple[str, str]:
        if ":" not in canonical_id:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=None,
                cause=ValueError(
                    f"canonical id {canonical_id!r} is not in '<type>:<slug>' form"
                ),
            )
        type_name, slug = canonical_id.split(":", 1)
        type_dir = _TYPE_TO_DIR.get(type_name)
        if type_dir is None:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(f"unknown entity type {type_name!r}"),
            )
        return type_dir, slug

    def _build(self, canonical_id: str, overlay_path: Path) -> OverlayRecord:
        type_name, slug = canonical_id.split(":", 1)
        try:
            frontmatter, _ = parse_frontmatter(overlay_path)
            if not frontmatter:
                raise EntityValidationError(
                    f"{overlay_path} has no parseable frontmatter"
                )
            self._validator.validate_overlay(frontmatter)
            declared = frontmatter.get("overlay_of")
            if declared != canonical_id:
                raise EntityValidationError(
                    f"overlay_of {declared!r} does not match path-derived "
                    f"canonical id {canonical_id!r}"
                )
        except EntityValidationError as exc:
            raise OverlayValidationError(
                overlay_path, canonical_id=canonical_id, cause=exc
            ) from exc

        return OverlayRecord(
            canonical_id=canonical_id,
            type=type_name,
            slug=slug,
            project=self._project,
            project_root=self._project_root,
            overlay_path=overlay_path,
            frontmatter=frontmatter,
            body=_read_markdown_body(overlay_path),
            pin_version=frontmatter.get("pin_version") or None,
            pin_effective_version=frontmatter.get("pin_effective_version") or None,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k overlay_adapter_load -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/overlay.py science/tests/test_commons_overlay.py
git commit -m "feat(commons): OverlayRecord + OverlayAdapter.load"
```

---

## Task 5: `OverlayAdapter.scan`

**Files:**
- Modify: `science/src/science_tool/commons/overlay.py`
- Test: `science/tests/test_commons_overlay.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_overlay.py`:

```python
def test_overlay_adapter_scan_yields_records() -> None:
    from science_tool.commons.overlay import OverlayAdapter, OverlayRecord

    root = _OVERLAYS / "proj-alpha"
    items = list(OverlayAdapter(root, "proj-alpha").scan())
    assert all(isinstance(i, OverlayRecord) for i in items)
    ids = sorted(i.canonical_id for i in items)
    assert ids == ["dataset:cath-domains", "paper:Adams2025"]


def test_overlay_adapter_scan_yields_errors_for_broken_files() -> None:
    from science_tool.commons.errors import OverlayValidationError
    from science_tool.commons.overlay import OverlayAdapter, OverlayRecord

    root = _OVERLAYS / "proj-broken"
    items = list(OverlayAdapter(root, "proj-broken").scan())
    # proj-broken/doc/papers/Adams2025.md fails the overlay schema;
    # proj-broken/doc/topics/nonexistent-topic.md is schema-valid here
    # (the dangling overlay_of check belongs to validate_project_overlays).
    errors = [i for i in items if isinstance(i, OverlayValidationError)]
    records = [i for i in items if isinstance(i, OverlayRecord)]
    assert len(errors) == 1
    assert errors[0].canonical_id == "paper:Adams2025"
    assert len(records) == 1
    assert records[0].canonical_id == "topic:nonexistent-topic"


def test_overlay_adapter_scan_missing_doc_dir_yields_nothing(tmp_path: Path) -> None:
    from science_tool.commons.overlay import OverlayAdapter

    # tmp_path exists but has no doc/ subtree.
    assert list(OverlayAdapter(tmp_path, "empty-proj").scan()) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k overlay_adapter_scan -v`
Expected: FAIL with `AttributeError: 'OverlayAdapter' object has no attribute 'scan'`.

- [ ] **Step 3: Write minimal implementation**

Add the `scan` method to `OverlayAdapter` in `science/src/science_tool/commons/overlay.py` (place it directly after `load`):

```python
    def scan(self) -> Iterator[OverlayRecord | OverlayValidationError]:
        """Walk the project's doc/{datasets,papers,topics,themes}/*.md overlays.

        Yields an OverlayRecord or an OverlayValidationError per file. A missing
        doc/ directory or a missing type subdirectory yields nothing — a project
        need not overlay every type.
        """
        for type_name, type_dir in _TYPE_TO_DIR.items():
            subdir = self._project_root / "doc" / type_dir
            if not subdir.is_dir():
                continue
            for child in sorted(subdir.iterdir()):
                if child.suffix != ".md" or not child.is_file():
                    continue
                canonical_id = f"{type_name}:{child.stem}"
                try:
                    yield self._build(canonical_id, child)
                except OverlayValidationError as exc:
                    yield exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k overlay_adapter_scan -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/overlay.py science/tests/test_commons_overlay.py
git commit -m "feat(commons): OverlayAdapter.scan"
```

---

## Task 6: `MergedEntity` + `merge_entity`

**Files:**
- Modify: `science/src/science_tool/commons/overlay.py`
- Test: `science/tests/test_commons_overlay.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_overlay.py`:

```python
def _canonical_record(tmp_path: Path, slug: str = "Adams2025"):
    """Copy the commons paper fixture into tmp_path and return its CommonsEntityRecord."""
    import shutil

    from science_tool.commons.adapter import CommonsEntityAdapter

    src = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(src, root)
    return CommonsEntityAdapter(root).load(f"paper:{slug}")


def _merge_policy_for(record):
    from science_model.entity_schema import parse_profile, read_merge_policy

    return read_merge_policy(parse_profile(record.schema_profile))


def test_merge_entity_no_overlay_is_canonical_only(tmp_path: Path) -> None:
    from science_tool.commons.overlay import MergedEntity, merge_entity

    record = _canonical_record(tmp_path)
    merged = merge_entity(record, None, _merge_policy_for(record))
    assert isinstance(merged, MergedEntity)
    assert merged.overlay is None
    assert merged.merged_frontmatter == record.frontmatter
    assert "representative paper" in merged.merged_body
    assert set(merged.field_sources.values()) == {"canonical"}


def test_merge_entity_append_field_dedups_and_orders(tmp_path: Path) -> None:
    from science_tool.commons.overlay import OverlayAdapter, merge_entity

    record = _canonical_record(tmp_path)  # tags == ["evaluation", "homology"]
    overlay = OverlayAdapter(
        _OVERLAYS / "proj-alpha", "proj-alpha"
    ).load("paper:Adams2025")  # tags == ["overlay-added"]
    merged = merge_entity(record, overlay, _merge_policy_for(record))
    assert merged.merged_frontmatter["tags"] == [
        "evaluation",
        "homology",
        "overlay-added",
    ]
    assert merged.field_sources["tags"] == "canonical+overlay"


def test_merge_entity_project_only_field_copied_from_overlay(tmp_path: Path) -> None:
    from science_tool.commons.overlay import OverlayAdapter, merge_entity

    record = _canonical_record(tmp_path)
    overlay = OverlayAdapter(
        _OVERLAYS / "proj-alpha", "proj-alpha"
    ).load("paper:Adams2025")
    merged = merge_entity(record, overlay, _merge_policy_for(record))
    assert merged.merged_frontmatter["hypothesis_links"] == ["H2", "H4"]
    assert merged.merged_frontmatter["relevance"].startswith("H2")
    assert merged.field_sources["hypothesis_links"] == "overlay"
    assert merged.field_sources["relevance"] == "overlay"


def test_merge_entity_body_appends_overlay_sections(tmp_path: Path) -> None:
    from science_tool.commons.overlay import OverlayAdapter, merge_entity

    record = _canonical_record(tmp_path)
    overlay = OverlayAdapter(
        _OVERLAYS / "proj-alpha", "proj-alpha"
    ).load("paper:Adams2025")
    merged = merge_entity(record, overlay, _merge_policy_for(record))
    assert "representative paper" in merged.merged_body
    assert "Project-Specific Notes" in merged.merged_body
    assert merged.merged_body.index("representative paper") < merged.merged_body.index(
        "Project-Specific Notes"
    )


def test_merge_entity_rejects_forbidden_overlay_field(tmp_path: Path) -> None:
    from science_model.entity_schema import MergePolicy

    from science_tool.commons.errors import OverlayMergeError
    from science_tool.commons.overlay import OverlayRecord, merge_entity

    record = _canonical_record(tmp_path)
    # Hand-craft an OverlayRecord that smuggles a `replace`-policy field past
    # validation — exercises the defense-in-depth guard.
    bad = OverlayRecord(
        canonical_id="paper:Adams2025",
        type="paper",
        slug="Adams2025",
        project="x",
        project_root=tmp_path,
        overlay_path=tmp_path / "x.md",
        frontmatter={"id": "paper:Adams2025", "overlay_of": "paper:Adams2025",
                     "title": "smuggled"},
        body="",
        pin_version=None,
        pin_effective_version=None,
    )
    policy = _merge_policy_for(record)
    assert policy["title"] == MergePolicy.REPLACE  # sanity
    with pytest.raises(OverlayMergeError, match="title"):
        merge_entity(record, bad, policy)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k merge_entity -v`
Expected: FAIL with `ImportError: cannot import name 'merge_entity'`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/commons/overlay.py`, extend the import block — add to the `science_model.entity_schema` import and the errors import, and add the `CommonsEntityRecord` import:

Change:
```python
from science_model.entity_schema import EntityValidationError, EntityValidator

from science_tool.commons.errors import OverlayValidationError
```
to:
```python
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    MergePolicy,
    read_overlay_merge_policy,
)

from science_tool.commons.adapter import CommonsEntityRecord
from science_tool.commons.errors import OverlayMergeError, OverlayValidationError
```

Then append to the file:

```python
_SKIP_OVERLAY_FIELDS = frozenset(
    {"id", "overlay_of", "pin_version", "pin_effective_version"}
)


@dataclass(frozen=True, slots=True)
class MergedEntity:
    """A canonical commons entity with an optional project overlay merged in."""

    canonical: CommonsEntityRecord
    overlay: OverlayRecord | None
    merged_frontmatter: dict[str, Any]
    merged_body: str
    field_sources: dict[str, str]  # field -> canonical | overlay | canonical+overlay


def _dedup(items: list[Any]) -> list[Any]:
    """Order-preserving de-duplication for arrays of primitives."""
    seen: set[Any] = set()
    out: list[Any] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def merge_entity(
    canonical: CommonsEntityRecord,
    overlay: OverlayRecord | None,
    merge_policy: dict[str, MergePolicy],
) -> MergedEntity:
    """Merge an overlay onto a canonical entity per the `science:merge` policy.

    `merge_policy` is read_merge_policy(parse_profile(canonical.schema_profile)).
    Overlay-only fields (relevance, hypothesis_links, ...) resolve via
    read_overlay_merge_policy(). pin_version is carried on the overlay but is
    NOT acted on in D1 — the CLI emits the "pinning inactive" warning.
    """
    canonical_body = _read_markdown_body(canonical.body_path)

    if overlay is None:
        merged = dict(canonical.frontmatter)
        return MergedEntity(
            canonical=canonical,
            overlay=None,
            merged_frontmatter=merged,
            merged_body=canonical_body,
            field_sources={key: "canonical" for key in merged},
        )

    overlay_policy = read_overlay_merge_policy()
    merged = dict(canonical.frontmatter)
    field_sources: dict[str, str] = {key: "canonical" for key in merged}

    for field, value in overlay.frontmatter.items():
        if field in _SKIP_OVERLAY_FIELDS:
            continue
        policy = merge_policy.get(field) or overlay_policy.get(
            field, MergePolicy.PROJECT_ONLY
        )
        if policy is MergePolicy.APPEND:
            base = canonical.frontmatter.get(field, [])
            merged[field] = _dedup(list(base) + list(value))
            field_sources[field] = "canonical+overlay"
        elif policy is MergePolicy.PROJECT_ONLY:
            merged[field] = value
            field_sources[field] = "overlay"
        else:  # REPLACE / FORBIDDEN — unreachable for a validated overlay
            raise OverlayMergeError(
                field=field, canonical_id=canonical.canonical_id
            )

    if overlay.body.strip():
        merged_body = canonical_body + "\n\n" + overlay.body
    else:
        merged_body = canonical_body

    return MergedEntity(
        canonical=canonical,
        overlay=overlay,
        merged_frontmatter=merged,
        merged_body=merged_body,
        field_sources=field_sources,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k merge_entity -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/overlay.py science/tests/test_commons_overlay.py
git commit -m "feat(commons): MergedEntity + policy-driven merge_entity"
```

---

## Task 7: `resolve_entity`

**Files:**
- Modify: `science/src/science_tool/commons/overlay.py`
- Test: `science/tests/test_commons_overlay.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_overlay.py`:

```python
def _seed_commons_and_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, projects: dict[str, Path]
) -> Path:
    """Copy the commons fixture, build its registry, and write a config.yaml
    registering `projects` (name -> root path). Returns the commons root."""
    import shutil

    import yaml

    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder

    src = Path(__file__).parent / "fixtures" / "commons" / "valid"
    commons_root = tmp_path / "commons"
    shutil.copytree(src, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump(
            {
                "projects": [
                    {"path": str(p), "name": n, "registered": "2026-05-14"}
                    for n, p in projects.items()
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    return commons_root


def test_resolve_entity_no_project_is_canonical_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.overlay import resolve_entity

    _seed_commons_and_config(tmp_path, monkeypatch, projects={})
    merged = resolve_entity("paper:Adams2025")
    assert merged.overlay is None
    assert merged.merged_frontmatter["title"].startswith("A representative")


def test_resolve_entity_with_overlay_merges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.overlay import resolve_entity

    _seed_commons_and_config(
        tmp_path, monkeypatch, projects={"proj-alpha": _OVERLAYS / "proj-alpha"}
    )
    merged = resolve_entity("paper:Adams2025", project="proj-alpha")
    assert merged.overlay is not None
    assert merged.merged_frontmatter["hypothesis_links"] == ["H2", "H4"]
    assert "overlay-added" in merged.merged_frontmatter["tags"]


def test_resolve_entity_project_without_overlay_for_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.overlay import resolve_entity

    _seed_commons_and_config(
        tmp_path, monkeypatch, projects={"proj-alpha": _OVERLAYS / "proj-alpha"}
    )
    # proj-alpha has no overlay for the theme — canonical-only, not an error.
    merged = resolve_entity("theme:research-hygiene", project="proj-alpha")
    assert merged.overlay is None


def test_resolve_entity_unknown_project_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.errors import ProjectNotRegisteredError
    from science_tool.commons.overlay import resolve_entity

    _seed_commons_and_config(tmp_path, monkeypatch, projects={})
    with pytest.raises(ProjectNotRegisteredError):
        resolve_entity("paper:Adams2025", project="ghost")


def test_resolve_entity_registered_project_missing_dir_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.errors import ProjectDirectoryMissingError
    from science_tool.commons.overlay import resolve_entity

    _seed_commons_and_config(
        tmp_path, monkeypatch, projects={"gone": tmp_path / "does-not-exist"}
    )
    with pytest.raises(ProjectDirectoryMissingError):
        resolve_entity("paper:Adams2025", project="gone")


def test_resolve_entity_unknown_id_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.errors import CommonsEntityError
    from science_tool.commons.overlay import resolve_entity

    _seed_commons_and_config(tmp_path, monkeypatch, projects={})
    with pytest.raises(CommonsEntityError):
        resolve_entity("paper:NoSuchPaper")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k resolve_entity -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_entity'`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/commons/overlay.py`, extend the import block. Change:
```python
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    MergePolicy,
    read_overlay_merge_policy,
)

from science_tool.commons.adapter import CommonsEntityRecord
from science_tool.commons.errors import OverlayMergeError, OverlayValidationError
```
to:
```python
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    MergePolicy,
    parse_profile,
    read_merge_policy,
    read_overlay_merge_policy,
)

from science_tool.commons.adapter import CommonsEntityRecord
from science_tool.commons.config import resolve_commons_root, resolve_project_root
from science_tool.commons.errors import (
    CommonsRootNotFoundError,
    OverlayMergeError,
    OverlayValidationError,
    ProjectDirectoryMissingError,
)
from science_tool.commons.query import CommonsQuery
```

Then append to the file:

```python
def resolve_entity(canonical_id: str, project: str | None = None) -> MergedEntity:
    """Resolve a commons entity, optionally merged with a project overlay.

    With `project=None`, returns a canonical-only MergedEntity. With a project
    name, reads the project's overlay (if any) and merges it. Raises
    CommonsRootNotFoundError, CommonsEntityError (unknown id),
    ProjectNotRegisteredError (unknown project name), or
    ProjectDirectoryMissingError (registered project whose directory is gone).
    """
    root = resolve_commons_root()
    if not root.is_dir():
        raise CommonsRootNotFoundError(root)

    record = CommonsQuery(root).show(canonical_id)
    policy = read_merge_policy(parse_profile(record.schema_profile))

    if project is None:
        return merge_entity(record, None, policy)

    project_root = resolve_project_root(project)
    if not project_root.is_dir():
        raise ProjectDirectoryMissingError(project, project_root)

    overlay = OverlayAdapter(project_root, project).load(canonical_id)
    return merge_entity(record, overlay, policy)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k resolve_entity -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/overlay.py science/tests/test_commons_overlay.py
git commit -m "feat(commons): resolve_entity — overlay-merge entry point"
```

---

## Task 8: `OverlayValidationReport` + `validate_project_overlays`

**Files:**
- Modify: `science/src/science_tool/commons/overlay.py`
- Test: `science/tests/test_commons_overlay.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_overlay.py`:

```python
def test_validate_project_overlays_clean_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.overlay import validate_project_overlays

    _seed_commons_and_config(
        tmp_path, monkeypatch, projects={"proj-alpha": _OVERLAYS / "proj-alpha"}
    )
    report = validate_project_overlays("proj-alpha")
    assert report.checked == 2
    assert report.errors == []


def test_validate_project_overlays_reports_schema_and_dangling_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.overlay import validate_project_overlays

    _seed_commons_and_config(
        tmp_path, monkeypatch, projects={"proj-broken": _OVERLAYS / "proj-broken"}
    )
    report = validate_project_overlays("proj-broken")
    # one schema failure (papers/Adams2025.md) + one dangling overlay_of
    # (topics/nonexistent-topic.md).
    assert report.checked == 2
    assert len(report.errors) == 2
    failed_ids = sorted(e.canonical_id for e in report.errors)
    assert failed_ids == ["paper:Adams2025", "topic:nonexistent-topic"]


def test_validate_project_overlays_missing_dir_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.errors import ProjectDirectoryMissingError
    from science_tool.commons.overlay import validate_project_overlays

    _seed_commons_and_config(
        tmp_path, monkeypatch, projects={"gone": tmp_path / "does-not-exist"}
    )
    with pytest.raises(ProjectDirectoryMissingError):
        validate_project_overlays("gone")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k validate_project_overlays -v`
Expected: FAIL with `ImportError: cannot import name 'validate_project_overlays'`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/commons/overlay.py`, extend the imports — change:
```python
from science_tool.commons.adapter import CommonsEntityRecord
```
to:
```python
from science_tool.commons.adapter import CommonsEntityAdapter, CommonsEntityRecord
```
and change:
```python
from science_tool.commons.errors import (
    CommonsRootNotFoundError,
    OverlayMergeError,
    OverlayValidationError,
    ProjectDirectoryMissingError,
)
```
to:
```python
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsRootNotFoundError,
    OverlayMergeError,
    OverlayValidationError,
    ProjectDirectoryMissingError,
)
```

Then append to the file:

```python
@dataclass(frozen=True)
class OverlayValidationReport:
    """Result of validating every overlay file in one project."""

    checked: int
    errors: list[OverlayValidationError]


def validate_project_overlays(project: str) -> OverlayValidationReport:
    """Validate every overlay file in a registered project.

    Each overlay is checked against the overlay schema (via OverlayAdapter.scan)
    and its `overlay_of` is confirmed to resolve to a real canonical entity in
    the commons store. Raises CommonsRootNotFoundError, ProjectNotRegisteredError,
    or ProjectDirectoryMissingError before scanning.
    """
    root = resolve_commons_root()
    if not root.is_dir():
        raise CommonsRootNotFoundError(root)

    project_root = resolve_project_root(project)
    if not project_root.is_dir():
        raise ProjectDirectoryMissingError(project, project_root)

    commons_adapter = CommonsEntityAdapter(root)
    checked = 0
    errors: list[OverlayValidationError] = []
    for item in OverlayAdapter(project_root, project).scan():
        checked += 1
        if isinstance(item, OverlayValidationError):
            errors.append(item)
            continue
        try:
            commons_adapter.load(item.canonical_id)
        except CommonsEntityError as exc:
            errors.append(
                OverlayValidationError(
                    item.overlay_path,
                    canonical_id=item.canonical_id,
                    cause=exc,
                )
            )
    return OverlayValidationReport(checked=checked, errors=errors)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -k validate_project_overlays -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the whole overlay test file**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_overlay.py -v`
Expected: PASS (all tests so far — 23).

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/overlay.py science/tests/test_commons_overlay.py
git commit -m "feat(commons): validate_project_overlays + OverlayValidationReport"
```

---

## Task 9: `science commons show --project`

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`
- Test: `science/tests/test_commons_cli.py` (append; also remove the obsolete `test_show_rejects_project_flag`)

- [ ] **Step 1: Write the failing test**

In `science/tests/test_commons_cli.py`, **delete** the existing `test_show_rejects_project_flag` test (lines defining that function — it asserts the Phase B rejection that this task removes).

Then append a shared helper and the new tests:

```python
def _seeded_store_with_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_name: str, fixture: str
) -> Path:
    """Seed the commons store + registry, register one overlay project, return root."""
    import shutil

    import yaml

    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder

    src = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(src, root)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()

    overlay_root = Path(__file__).parent / "fixtures" / "overlays" / fixture
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump(
            {
                "projects": [
                    {
                        "path": str(overlay_root),
                        "name": project_name,
                        "registered": "2026-05-14",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    return root


def test_show_project_human_merges_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["show", "paper:Adams2025", "--project", "proj-alpha"]
    )
    assert result.exit_code == 0, result.output
    assert "overlay:" in result.output
    assert "proj-alpha" in result.output
    assert "Project-Specific Notes" in result.output


def test_show_project_json_includes_overlay_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        ["show", "paper:Adams2025", "--project", "proj-alpha", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["canonical_id"] == "paper:Adams2025"
    assert payload["merged_frontmatter"]["hypothesis_links"] == ["H2", "H4"]
    assert payload["overlay"]["project"] == "proj-alpha"
    assert payload["overlay"]["overlay_path"] == "doc/papers/Adams2025.md"
    assert payload["field_sources"]["tags"] == "canonical+overlay"


def test_show_project_with_no_overlay_for_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        ["show", "theme:research-hygiene", "--project", "proj-alpha", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["overlay"] is None


def test_show_unknown_project_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["show", "paper:Adams2025", "--project", "ghost"]
    )
    assert result.exit_code == 1
    assert "ghost" in result.output


def test_show_project_warns_on_inactive_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Add a pin_version to the proj-alpha paper overlay copy.
    import shutil

    import yaml

    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder

    src = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(src, root)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()

    proj = tmp_path / "proj-pinned"
    (proj / "doc" / "papers").mkdir(parents=True)
    (proj / "doc" / "papers" / "Adams2025.md").write_text(
        '---\nid: "paper:Adams2025"\noverlay_of: "paper:Adams2025"\n'
        'pin_version: "1.2.0"\nrelevance: "pinned"\n---\n\n## Notes\n',
        encoding="utf-8",
    )
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump(
            {
                "projects": [
                    {"path": str(proj), "name": "proj-pinned",
                     "registered": "2026-05-14"}
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        commons_group, ["show", "paper:Adams2025", "--project", "proj-pinned"]
    )
    assert result.exit_code == 0, result.output
    assert "pin_version" in result.stderr
    assert "Phase E" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -k show_project -v`
Expected: FAIL — `--project` still hits the Phase B rejection (`exit_code == 1`, "Phase D" in output) or KeyError on the new JSON keys.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/commons/cli.py`:

(a) Extend the imports — change:
```python
from science_tool.commons.resolver import resolve
```
to:
```python
from science_tool.commons.overlay import MergedEntity, resolve_entity
from science_tool.commons.resolver import resolve
```

(b) Replace the entire `show_cmd` function with:

```python
@commons_group.command("show")
@click.argument("entity_id")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.option(
    "--project",
    default=None,
    help="Merge the named registered project's overlay into the entity.",
)
def show_cmd(entity_id: str, as_json: bool, project: str | None) -> None:
    """Print one entity by canonical id, optionally merged with a project overlay."""
    if project is None:
        root = _require_root()
        try:
            record = CommonsQuery(root).show(entity_id)
        except CommonsError as exc:
            raise click.ClickException(str(exc)) from exc
        if as_json:
            click.echo(json.dumps(_record_to_json(record, root), indent=2, sort_keys=True))
        else:
            _print_record_human(record)
        return

    try:
        merged = resolve_entity(entity_id, project=project)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    if merged.overlay is not None and merged.overlay.pin_version:
        click.echo(
            f"warning: pin_version {merged.overlay.pin_version} on overlay is "
            f"inactive until Phase E; merged from live entity",
            err=True,
        )
    if as_json:
        click.echo(json.dumps(_merged_to_json(merged), indent=2, sort_keys=True))
    else:
        _print_merged_human(merged)
```

(c) Add these two helpers next to `_record_to_json` / `_print_record_human`:

```python
def _merged_to_json(merged: MergedEntity) -> dict:
    overlay = merged.overlay
    overlay_json = None
    if overlay is not None:
        overlay_json = {
            "project": overlay.project,
            "overlay_path": str(
                overlay.overlay_path.relative_to(overlay.project_root)
            ),
            "pin_version": overlay.pin_version,
            "pin_effective_version": overlay.pin_effective_version,
        }
    return {
        "canonical_id": merged.canonical.canonical_id,
        "type": merged.canonical.type,
        "schema_profile": merged.canonical.schema_profile,
        "merged_frontmatter": merged.merged_frontmatter,
        "merged_body": merged.merged_body,
        "field_sources": merged.field_sources,
        "overlay": overlay_json,
    }


def _print_merged_human(merged: MergedEntity) -> None:
    record = merged.canonical
    click.echo(f"{record.canonical_id}")
    click.echo(f"  title:          {merged.merged_frontmatter.get('title', '')}")
    click.echo(f"  schema_profile: {record.schema_profile}")
    tags = merged.merged_frontmatter.get("tags") or []
    if tags:
        click.echo(f"  tags:           {', '.join(tags)}")
    if merged.overlay is not None:
        contributed = sorted(
            field
            for field, src in merged.field_sources.items()
            if src in ("overlay", "canonical+overlay")
        )
        click.echo(f"  overlay:        {merged.overlay.project}")
        click.echo(f"    contributed:  {', '.join(contributed)}")
    click.echo("")
    click.echo(merged.merged_body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -k show -v`
Expected: PASS (existing `test_show_human` / `test_show_json` still pass; 5 new `show_project` / `show_unknown_project` tests pass).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/cli.py science/tests/test_commons_cli.py
git commit -m "feat(commons): science commons show --project — overlay-merged view"
```

---

## Task 10: `science commons validate --project`

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`
- Test: `science/tests/test_commons_cli.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_cli.py`:

```python
def test_validate_project_clean_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--project", "proj-alpha"])
    assert result.exit_code == 0, result.output
    assert "checked 2" in result.output


def test_validate_project_broken_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-broken", "proj-broken")
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--project", "proj-broken"])
    assert result.exit_code == 1
    assert "error" in result.output


def test_validate_project_with_type_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seeded_store_with_project(tmp_path, monkeypatch, "proj-alpha", "proj-alpha")
    runner = CliRunner()
    result = runner.invoke(
        commons_group,
        ["validate", "--project", "proj-alpha", "--type", "paper"],
    )
    assert result.exit_code == 2
    assert "--project cannot be combined with --type" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -k validate_project -v`
Expected: FAIL with `No such option: --project`.

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/commons/cli.py`:

(a) Extend the imports — change:
```python
from science_tool.commons.overlay import MergedEntity, resolve_entity
```
to:
```python
from science_tool.commons.overlay import (
    MergedEntity,
    resolve_entity,
    validate_project_overlays,
)
```

(b) Replace the entire `validate_cmd` function with:

```python
@commons_group.command("validate")
@click.option("--type", "entity_type", default=None, help="Filter to one type.")
@click.option("--slug", default=None, help="Filter to one slug.")
@click.option(
    "--project",
    default=None,
    help="Validate every overlay file in the named registered project.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def validate_cmd(
    entity_type: str | None,
    slug: str | None,
    project: str | None,
    as_json: bool,
) -> None:
    """Validate commons entities, or a project's overlay files with --project."""
    if project is not None:
        if entity_type is not None or slug is not None:
            raise click.UsageError(
                "--project cannot be combined with --type/--slug"
            )
        try:
            overlay_report = validate_project_overlays(project)
        except CommonsError as exc:
            raise click.ClickException(str(exc)) from exc
        if as_json:
            click.echo(
                json.dumps(
                    {
                        "checked": overlay_report.checked,
                        "errors": [
                            {
                                "overlay_path": str(e.overlay_path),
                                "canonical_id": e.canonical_id,
                                "message": str(e.cause),
                            }
                            for e in overlay_report.errors
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            click.echo(f"checked {overlay_report.checked} overlays")
            for err in overlay_report.errors:
                click.echo(f"  error: {err}", err=True)
        if overlay_report.errors:
            raise click.exceptions.Exit(1)
        return

    root = _require_root()
    report = CommonsValidator(CommonsEntityAdapter(root)).validate(
        type=entity_type, slug=slug
    )
    if as_json:
        payload = {
            "checked": report.checked,
            "errors": [
                {
                    "path": str(e.path),
                    "canonical_id": e.canonical_id,
                    "message": str(e.cause),
                }
                for e in report.errors
            ],
        }
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        click.echo(f"checked {report.checked} entities")
        for err in report.errors:
            click.echo(f"  error: {err}", err=True)
    if report.errors:
        raise click.exceptions.Exit(1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -k validate -v`
Expected: PASS (existing canonical-validate tests still pass; 3 new `validate_project` tests pass).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/cli.py science/tests/test_commons_cli.py
git commit -m "feat(commons): science commons validate --project — overlay validation"
```

---

## Task 11: Public API surface

**Files:**
- Modify: `science/src/science_tool/commons/__init__.py`
- Test: `science/tests/test_commons_public_api.py` (modify — the expected set already lists the Phase C names; add the D1 names)

- [ ] **Step 1: Write the failing test**

In `science/tests/test_commons_public_api.py`, add the D1 names to the `expected` set inside `test_public_api_exports` (after the `# Phase C` block):

```python
        # Phase D1
        "OverlayAdapter",
        "OverlayRecord",
        "MergedEntity",
        "OverlayValidationReport",
        "merge_entity",
        "resolve_entity",
        "validate_project_overlays",
        "resolve_project_root",
        "ProjectNotRegisteredError",
        "ProjectDirectoryMissingError",
        "OverlayValidationError",
        "OverlayMergeError",
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_public_api.py -v`
Expected: FAIL — `missing public name: OverlayAdapter` (assertion error).

- [ ] **Step 3: Write minimal implementation**

In `science/src/science_tool/commons/__init__.py`:

(a) Add these imports (alongside the existing commons imports, keeping alphabetical-ish grouping):

```python
from science_tool.commons.config import (
    CommonsSettings,
    load_data_overrides,
    resolve_commons_data_root,
    resolve_commons_root,
    resolve_project_root,
)
from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
    DataIntegrityError,
    DataLogicalPathError,
    DataResourceNotFoundError,
    OverlayMergeError,
    OverlayValidationError,
    ProjectDirectoryMissingError,
    ProjectNotRegisteredError,
)
from science_tool.commons.overlay import (
    MergedEntity,
    OverlayAdapter,
    OverlayRecord,
    OverlayValidationReport,
    merge_entity,
    resolve_entity,
    validate_project_overlays,
)
```

(The `config` and `errors` import blocks already exist — extend them rather than duplicating; the `overlay` block is new.)

(b) Add the new names to `__all__` (keep it sorted, matching the existing style):

```python
    "MergedEntity",
    "OverlayAdapter",
    "OverlayMergeError",
    "OverlayRecord",
    "OverlayValidationError",
    "OverlayValidationReport",
    "ProjectDirectoryMissingError",
    "ProjectNotRegisteredError",
    "merge_entity",
    "resolve_entity",
    "resolve_project_root",
    "validate_project_overlays",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_public_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/commons/__init__.py science/tests/test_commons_public_api.py
git commit -m "feat(commons): export Phase D1 public surface"
```

---

## Task 12: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the commons test suite**

Run: `cd ~/d/science/science && uv run pytest tests/ -k commons -v`
Expected: PASS — every commons test (Phase B + C + D1).

- [ ] **Step 2: Run the full science_tool suite**

Run: `cd ~/d/science/science && uv run pytest tests/ -q`
Expected: PASS — no regressions.

- [ ] **Step 3: Run the model suite**

Run: `cd ~/d/science/science && uv run pytest ../model/tests/ -q`
Expected: PASS — D1 does not touch `science_model`, so this is a no-regression check on the Phase A `entity_schema` layer D1 depends on.

- [ ] **Step 4: Smoke-test the CLI end-to-end**

Run:
```bash
cd ~/d/science/science && uv run python - <<'EOF'
import shutil, tempfile, os
from pathlib import Path
tmp = Path(tempfile.mkdtemp())
src = Path("tests/fixtures/commons/valid")
root = tmp / "commons"
shutil.copytree(src, root)
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
cfg = tmp / "cfg"; cfg.mkdir()
overlay = Path("tests/fixtures/overlays/proj-alpha").resolve()
import yaml
(cfg / "config.yaml").write_text(yaml.dump({"projects": [
    {"path": str(overlay), "name": "proj-alpha", "registered": "2026-05-14"}]}))
os.environ["SCIENCE_COMMONS_ROOT"] = str(root)
os.environ["SCIENCE_CONFIG_DIR"] = str(cfg)
os.environ["SCIENCE_COMMONS_QUIET_STALE"] = "1"
from science_tool.commons import resolve_entity
m = resolve_entity("paper:Adams2025", project="proj-alpha")
assert m.overlay is not None
assert m.merged_frontmatter["hypothesis_links"] == ["H2", "H4"]
assert "overlay-added" in m.merged_frontmatter["tags"]
print("D1 smoke test OK")
EOF
```
Expected: prints `D1 smoke test OK`.

- [ ] **Step 5: Commit (only if Steps 1–4 surfaced fixable issues; otherwise skip)**

If any step required a fix, commit it:
```bash
cd ~/d/science && git add -A
git commit -m "fix(commons): Phase D1 full-suite verification fixes"
```
If all four steps passed clean, there is nothing to commit — D1 is complete.

---

## Self-Review

**Spec coverage** (against `2026-05-14-commons-overlay-merge-design.md`):
- §4.1a `_read_markdown_body` — Task 3.
- §4.3 `resolve_project_root` (registered-name lookup, no disk check) — Task 2.
- §5.2 `OverlayRecord` (incl. `project_root`) — Task 4.
- §5.3 `OverlayAdapter.load` / `.scan` — Tasks 4, 5.
- §5.4 `merge_entity` (policy-driven; `append` dedup; `project_only`; body; `OverlayMergeError` guard) — Task 6.
- §5.5 `MergedEntity` — Task 6.
- §5.6 `resolve_entity` (incl. `ProjectDirectoryMissingError` check) — Task 7.
- §5.7 `validate_project_overlays` + `OverlayValidationReport` — Task 8.
- §6.1 `show --project` (warning, human, `_merged_to_json(m)`) — Task 9.
- §6.2 `validate --project` (mutually exclusive with `--type`/`--slug` → `UsageError`) — Task 10.
- §7 error classes (all four) — Task 1.
- §8 fixtures + test files — fixtures in Task 3; tests across Tasks 1–11; suites in Task 12.
- §9 public API surface — Task 11.

**Placeholder scan:** no TBD/TODO; every code step shows complete code; every command has an expected result.

**Type consistency:** `OverlayRecord` field set is identical in Task 4's definition and Task 6's hand-crafted instance. `MergedEntity` field set matches between Task 6's definition and its consumers in Tasks 9. `merge_entity(canonical, overlay, merge_policy)` signature is consistent across Tasks 6, 7. `resolve_entity(canonical_id, project=None)` consistent across Tasks 7, 9. `validate_project_overlays(project)` / `OverlayValidationReport(checked, errors)` consistent across Tasks 8, 10. `_merged_to_json(m)` takes only `m` (no `root`) per the spec round-2 fix — consistent in Task 9.

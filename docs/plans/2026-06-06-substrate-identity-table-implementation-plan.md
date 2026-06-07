# Identity Table Foundation (Substrate Phase 1.1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture every entity's identity participation as **row-based declarations collected inside `load_project_sources` at emit time** (before the existing dedup/collapse), expose them as a compiled `IdentityTable` keyed by `(owner_scope, canonical_id)`, and let the graph **audit/diagnostic** entry points **report** identity collisions (including `entities.yaml` stub-shadows) instead of crashing. The audit/diagnostic paths (`materialization_audit`, `collect_unresolved_refs`) load **non-strict** and gain additive `identity_collision` rows; **the migrator, the materialization *build*, and conformance are not rerouted yet** (they keep strict loading — a real duplicate in a build must still fail hard).

**Architecture:** The loader already builds an internal `identity_table: dict[str, SourceRef]` that first-wins-or-raises at three sites (`graph/sources.py:377-382` adapter loop, `:398-403` legacy, `:450-455` commons). That dict is lossy (keyed by `canonical_id`, one adapter per id) and raises before `ProjectSources` is returned — so the collisions we want to report die there. This plan adds, alongside that dict, an **append-only `list[IdentityDeclaration]`** populated at each emit site *before* the dedup check; each declaration carries its own `(canonical_id, participation_mode, owner_scope, adapter, source_ref, deprecated)`, so two owners of one id are both recorded with their true provenance. A new `strict_identity: bool = True` parameter preserves today's raise-on-duplicate behavior by default; `strict_identity=False` records the duplicate declaration and keeps the first entity, so a colliding project still loads and the audit can report it. `IdentityTable` wraps the declarations and computes collisions on the `(owner_scope, canonical_id)` key. `audit_identity_table` emits the existing graph-audit row shape, folded additively into `audit_project_sources`.

**Tech Stack:** Python 3, Pydantic v2 (`science_model`), pytest. Library at `~/d/science/science/` (`src/science_tool/`, `tests/`). Run tests with `cd ~/d/science/science && uv run --frozen pytest`.

**Scope (this plan only):** the `IdentityDeclaration`/`IdentityTable` types, in-loader declaration collection, the `strict_identity` flag, `build_identity_table`, `audit_identity_table`, additive wiring into `audit_project_sources`, and routing the two graph-audit/diagnostic entry points (`materialization_audit`, `collect_unresolved_refs`) to non-strict loading. **Out of scope** (later Phase-1 sub-plans, see "Where this sits"): adapter-level enforcement (MarkdownAdapter owner-only / OverlayAdapter sole-borrower / `overlay_of`-in-owner-root error), scoped-ref resolution (§B3a), rerouting the migrator's collision detection + retiring the simulation/masking hack (§C4), migrating orphan datapackages to real entity-file owners (§B4 — Phase 1.1 only *flags* them by marking the datapackage row a deprecated transitional owner).

**Design source:** `~/d/science/docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md` — §B3 (two columns), §B3a (key), §C1–C3 (compiler seam, adapter modes).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/science_tool/graph/identity_table.py` | `ParticipationMode`, `IdentityDeclaration`, `IdentityCollision`, `IdentityTable`, `classify_owner_scope`, `build_identity_table` | **Create** |
| `tests/test_graph_identity_table.py` | Unit tests for the types, classifier, builder, collision rule | **Create** |
| `src/science_tool/graph/sources.py` | Add `identity_declarations` field to `ProjectSources`; add `strict_identity` param; append declarations at the 3 emit sites | **Modify** (`ProjectSources` 136-154; `load_project_sources` 172-474; emit sites 377-382, 398-403, 450-455) |
| `tests/test_identity_declarations_loader.py` | Real `tmp_path` loader tests: declarations populated; strict raises, non-strict records | **Create** |
| `src/science_tool/graph/migrate.py` | Add `audit_identity_table`; fold it additively into `audit_project_sources` | **Modify** (`audit_project_sources` 145-191) |
| `tests/test_graph_migrate_identity_audit.py` | `audit_identity_table` unit + real `tmp_path` integration via `audit_project_sources` | **Create** |
| `src/science_tool/graph/materialize.py` | Route `materialization_audit` to non-strict loading | **Modify** (`materialization_audit` 210-212) |
| `src/science_tool/graph/health.py` | Route `collect_unresolved_refs` to non-strict loading; drop `identity_collision` rows from the unresolved-ref grouping | **Modify** (`collect_unresolved_refs` 99-117) |
| `tests/test_identity_audit_entrypoints.py` | `tmp_path` tests that both entry points report (not crash) on a stub-shadow | **Create** |

### Reference facts (verified against `main`)

- `ProjectSources` (`graph/sources.py:136-154`): Pydantic `BaseModel`, `model_config = {"arbitrary_types_allowed": True}`. Fields include `project_name: str`, `entities: list[Entity]`, `entity_source_adapters: dict[str, str]`, `commons_overlay_paths: dict[str, str]`, `manual_aliases: dict[str, str]`. **New field added here:** `identity_declarations`.
- `load_project_sources(project_root, markdown_overrides=None, *, include_commons=True, strict_core_schema=True) -> ProjectSources` (`graph/sources.py:172`). Internals used here: `project_slug = project_root.name` (261), `identity_table: dict[str, SourceRef] = {}` (262), `config` dict with `config["name"]` (set ~189, used 460), `commons_overlay_paths` (434).
- Three emit sites, all the same shape `existing = identity_table.get(...); if existing is not None: raise EntityIdentityCollisionError(...); identity_table[...] = ref; entities.append(...); entity_source_adapters[...] = <name>`:
  - adapter loop 377-382 (`adapter.name`),
  - legacy 398-403 (`ref.adapter_name`),
  - commons 449-455 (`ref.adapter_name`).
- `EntityIdentityCollisionError(canonical_id, first_ref, second_ref)` in `science_tool.graph.errors` (subclass of `ValueError`).
- `SourceRef(adapter_name: str, path: str, line: int | None = None)` — `model/src/science_model/source_ref.py`.
- `audit_project_sources(sources) -> tuple[list[dict], bool]` (`graph/migrate.py:145-191`); an audit row is a dict with keys `check, status, source, field, target, details` (see its `AliasCollisionError` branch 152-162).
- Test idiom (from `tests/test_load_project_sources_unified.py:29-51`): `science.yaml` = `"name: <n>\nprofile: research\nprofiles: {local: local}\n"`; entity at `entities/<plural>/<x>.md` with frontmatter `id`, `type`, `title`; `load_project_sources(tmp_path)` returns sources. Aggregate stub idiom (from MM30): `knowledge/sources/local/entities.yaml` is a YAML list of `{canonical_id, kind, title, profile, source_path}`.

---

## Task 1: Identity value types + collision rule

**Files:**
- Create: `src/science_tool/graph/identity_table.py`
- Test: `tests/test_graph_identity_table.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_identity_table.py
from science_model.source_ref import SourceRef
from science_tool.graph.identity_table import (
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
)


def _decl(cid, mode=ParticipationMode.OWNER, scope="proj", adapter="markdown", path="p", deprecated=False):
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=mode,
        owner_scope=scope,
        adapter=adapter,
        source_ref=SourceRef(adapter_name=adapter, path=path),
        deprecated=deprecated,
    )


def test_modes_and_row_defaults():
    assert ParticipationMode.OWNER.value == "owner"
    assert ParticipationMode.BORROWER.value == "borrower"
    assert ParticipationMode.EXTERNAL_REFERENCE.value == "external-reference"
    row = _decl("hypothesis:h1")
    assert row.deprecated is False
    assert row.owner_scope == "proj"


def test_owners_keyed_by_scope_and_id_no_collision_when_clean():
    table = IdentityTable(rows=[_decl("hypothesis:h1"), _decl("task:t1", adapter="task")])
    assert set(table.owners()) == {("proj", "hypothesis:h1"), ("proj", "task:t1")}
    assert table.collisions() == []


def test_collision_when_two_owners_share_key_stub_shadow():
    table = IdentityTable(rows=[
        _decl("question:q1", adapter="markdown", path="entities/question/0007-q1.md"),
        _decl("question:q1", adapter="aggregate",
              path="knowledge/sources/local/entities.yaml", deprecated=True),
    ])
    cols = table.collisions()
    assert len(cols) == 1
    assert cols[0].owner_scope == "proj"
    assert cols[0].canonical_id == "question:q1"
    assert len(cols[0].rows) == 2
    assert any(r.deprecated for r in cols[0].rows)  # the stub is flagged


def test_no_collision_across_scopes_or_for_borrower():
    table = IdentityTable(rows=[
        _decl("topic:bayesian", scope="commons", adapter="commons-merged"),
        _decl("topic:bayesian", mode=ParticipationMode.BORROWER, scope="commons", adapter="overlay"),
        _decl("topic:bayesian", scope="proj"),  # different scope key
    ])
    # commons owner + commons borrower + proj owner => no key has >1 OWNER row
    assert table.collisions() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.identity_table'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/science_tool/graph/identity_table.py
"""Compiled identity table: every entity's participation mode and owner scope.

Built from row-based declarations collected inside ``load_project_sources`` at
emit time (the compiler output the substrate design, §C1, requires consumers to
read instead of re-walking disk). This module defines the value types and the
collision rule; the loader populates the declarations.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

from science_model.source_ref import SourceRef


class ParticipationMode(str, Enum):
    """What a single identity row contributes (design §B3)."""

    OWNER = "owner"
    BORROWER = "borrower"
    EXTERNAL_REFERENCE = "external-reference"


@dataclass(frozen=True)
class IdentityDeclaration:
    """One identity row: an entity's participation in one owner scope."""

    canonical_id: str
    participation_mode: ParticipationMode
    owner_scope: str
    adapter: str
    source_ref: SourceRef | None
    deprecated: bool = False  # transitional owner (e.g. aggregate), design §C3


@dataclass(frozen=True)
class IdentityCollision:
    """Two owner rows sharing one (owner_scope, canonical_id) — the identity error."""

    owner_scope: str
    canonical_id: str
    rows: tuple[IdentityDeclaration, ...]


@dataclass(frozen=True)
class IdentityTable:
    """All identity declarations compiled from a project's loaded sources."""

    rows: list[IdentityDeclaration] = field(default_factory=list)

    def owners(self) -> dict[tuple[str, str], list[IdentityDeclaration]]:
        """Owner rows grouped by the identity key (owner_scope, canonical_id)."""
        grouped: dict[tuple[str, str], list[IdentityDeclaration]] = defaultdict(list)
        for row in self.rows:
            if row.participation_mode is ParticipationMode.OWNER:
                grouped[(row.owner_scope, row.canonical_id)].append(row)
        return dict(grouped)

    def collisions(self) -> list[IdentityCollision]:
        """Every (owner_scope, canonical_id) claimed by more than one owner row."""
        return [
            IdentityCollision(owner_scope=scope, canonical_id=cid, rows=tuple(rows))
            for (scope, cid), rows in self.owners().items()
            if len(rows) > 1
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/identity_table.py science/tests/test_graph_identity_table.py
git commit -m "feat(substrate): identity declaration/table value types + collision rule"
```

---

## Task 2: `classify_owner_scope` — adapter → (owner_scope, deprecated)

A pure helper the loader calls at each emit site, so classification has one tested home and never silently defaults (review: no silent `"markdown"` fallback). Owner-vs-borrower is decided at the call site (overlays are emitted as borrowers explicitly); this helper covers the owner rows' scope + deprecation.

**Files:**
- Modify: `src/science_tool/graph/identity_table.py` (append)
- Test: `tests/test_graph_identity_table.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_graph_identity_table.py
from science_tool.graph.identity_table import classify_owner_scope

_COMMONS = "commons"


def test_classify_owner_scope():
    # aggregate AND datapackage are transitional deprecated owners (design §B4/§C3):
    # in the target state datapackages are attachments, not owners, so any datapackage
    # currently emitting an entity is an orphan/transitional owner to be migrated.
    assert classify_owner_scope("aggregate", project_name="proj") == ("proj", True)
    assert classify_owner_scope("datapackage", project_name="proj") == ("proj", True)
    # commons-merged is owned by the commons scope, not deprecated
    assert classify_owner_scope("commons-merged", project_name="proj") == (_COMMONS, False)
    # everything else (markdown/task/workflow-run/code-file/legacy-*) is a plain owner
    for adapter in ("markdown", "task", "workflow-run", "code-file",
                    "legacy-model", "legacy-parameter"):
        assert classify_owner_scope(adapter, project_name="proj") == ("proj", False)


def test_classify_owner_scope_rejects_empty_adapter():
    import pytest
    with pytest.raises(ValueError):
        classify_owner_scope("", project_name="proj")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py::test_classify_owner_scope -q`
Expected: FAIL — `ImportError: cannot import name 'classify_owner_scope'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/science_tool/graph/identity_table.py`:

```python
_COMMONS_SCOPE = "commons"


def classify_owner_scope(adapter: str, *, project_name: str) -> tuple[str, bool]:
    """Return (owner_scope, deprecated) for an owner declaration from `adapter`.

    Fails loud on an empty adapter (review: missing provenance must not silently
    become a project markdown owner).
    """
    if not adapter:
        raise ValueError("identity declaration requires a non-empty adapter name")
    if adapter == "commons-merged":
        return (_COMMONS_SCOPE, False)
    # aggregate (entities.yaml) and datapackage are transitional deprecated owners:
    # the target substrate retires entities.yaml (§B5) and treats datapackages as
    # attachments, not owners (§B4). Flag them so later phases can find them.
    if adapter in ("aggregate", "datapackage"):
        return (project_name, True)
    return (project_name, False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/identity_table.py science/tests/test_graph_identity_table.py
git commit -m "feat(substrate): classify_owner_scope for transitional owners and commons scope"
```

---

## Task 3: Collect declarations in the loader + `strict_identity` flag

This is the core change. Add the `identity_declarations` field, the `strict_identity` parameter, and emit a declaration at each of the three sites **before** the dedup check. In non-strict mode, a duplicate is recorded and skipped (first entity wins) instead of raising.

**Files:**
- Modify: `src/science_tool/graph/sources.py`
- Test: `tests/test_identity_declarations_loader.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_identity_declarations_loader.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.sources import load_project_sources


def _seed(root: Path, name: str = "proj") -> None:
    (root / "science.yaml").write_text(
        f"name: {name}\nprofile: research\nprofiles: {{local: local}}\n",
        encoding="utf-8",
    )


def _write_md(root: Path, rel: str, cid: str, kind: str, title: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{cid}"\ntype: "{kind}"\ntitle: "{title}"\n---\n', encoding="utf-8")


def _write_aggregate_stub(root: Path, cid: str, kind: str, title: str) -> None:
    # AggregateAdapter reads the `entities:` key of a MAPPING (aggregate.py:69),
    # not a top-level list.
    local = root / "knowledge" / "sources" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "entities.yaml").write_text(
        "\n".join(
            [
                "entities:",
                f"  - canonical_id: {cid}",
                f"    kind: {kind}",
                f"    title: {title}",
                "    profile: local",
                "    source_path: knowledge/sources/local/entities.yaml",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_normal_load_populates_owner_declarations(tmp_path: Path) -> None:
    _seed(tmp_path, name="proj")
    _write_md(tmp_path, "entities/hypotheses/h1.md", "hypothesis:h1", "hypothesis", "H1")
    sources = load_project_sources(tmp_path, include_commons=False)
    decls = {d.canonical_id: d for d in sources.identity_declarations}
    assert "hypothesis:h1" in decls
    assert decls["hypothesis:h1"].participation_mode is ParticipationMode.OWNER
    assert decls["hypothesis:h1"].owner_scope == "proj"
    assert decls["hypothesis:h1"].deprecated is False
    assert decls["hypothesis:h1"].adapter == "markdown"


def test_aggregate_entry_is_deprecated_owner_declaration(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write_aggregate_stub(tmp_path, "concept:1q-gain", "concept", "1q gain")
    sources = load_project_sources(tmp_path, include_commons=False)
    decls = {d.canonical_id: d for d in sources.identity_declarations}
    assert decls["concept:1q-gain"].deprecated is True
    assert decls["concept:1q-gain"].owner_scope == "proj"


def test_strict_identity_true_still_raises_on_duplicate(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write_md(tmp_path, "entities/questions/q1.md", "question:q1", "question", "Q1")
    _write_aggregate_stub(tmp_path, "question:q1", "question", "Q1")
    with pytest.raises(EntityIdentityCollisionError):
        load_project_sources(tmp_path, include_commons=False)  # strict_identity defaults True


def test_strict_identity_false_records_both_owner_declarations(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write_md(tmp_path, "entities/questions/q1.md", "question:q1", "question", "Q1")
    _write_aggregate_stub(tmp_path, "question:q1", "question", "Q1")
    sources = load_project_sources(tmp_path, include_commons=False, strict_identity=False)
    q1_owners = [
        d for d in sources.identity_declarations
        if d.canonical_id == "question:q1" and d.participation_mode is ParticipationMode.OWNER
    ]
    assert len(q1_owners) == 2
    adapters = {d.adapter for d in q1_owners}
    assert adapters == {"markdown", "aggregate"}
    # first entity still wins: exactly one question:q1 entity survives
    assert sum(1 for e in sources.entities if e.canonical_id == "question:q1") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_identity_declarations_loader.py -q`
Expected: FAIL — `AttributeError: 'ProjectSources' object has no attribute 'identity_declarations'` (and `TypeError` for the `strict_identity` kwarg).

- [ ] **Step 3a: Add the field + import to `ProjectSources`**

In `src/science_tool/graph/sources.py`, add the import near the other `graph` imports at the top:

```python
from science_tool.graph.identity_table import (
    IdentityDeclaration,
    ParticipationMode,
    classify_owner_scope,
)
```

In the `ProjectSources` class body (after `commons_overlay_paths`, ~line 153), add:

```python
    identity_declarations: list[IdentityDeclaration] = Field(default_factory=list)
```

- [ ] **Step 3b: Add the `strict_identity` parameter**

Change the signature (line 172) from:

```python
def load_project_sources(
    project_root: Path,
    markdown_overrides: dict[str, str] | None = None,
    *,
    include_commons: bool = True,
    strict_core_schema: bool = True,
) -> ProjectSources:
```

to add `strict_identity: bool = True,` as the last keyword-only param.

Add the accumulator next to `identity_table` (line 262):

```python
    identity_declarations: list[IdentityDeclaration] = []
```

- [ ] **Step 3c: Emit at the adapter loop (replace lines 377-382)**

```python
                owner_scope, deprecated = classify_owner_scope(adapter.name, project_name=project_name)
                identity_declarations.append(
                    IdentityDeclaration(
                        canonical_id=entity.canonical_id,
                        participation_mode=ParticipationMode.OWNER,
                        owner_scope=owner_scope,
                        adapter=adapter.name,
                        source_ref=ref,
                        deprecated=deprecated,
                    )
                )
                existing = identity_table.get(entity.canonical_id)
                if existing is not None:
                    if strict_identity:
                        raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
                    continue
                identity_table[entity.canonical_id] = ref
                entities.append(entity)
                entity_source_adapters[entity.canonical_id] = adapter.name
```

where `project_name = str(config["name"])` — add `project_name = str(config["name"])` once near line 261 (next to `project_slug`).

- [ ] **Step 3d: Emit at the legacy loop (replace lines 398-403)**

```python
        owner_scope, deprecated = classify_owner_scope(ref.adapter_name, project_name=project_name)
        identity_declarations.append(
            IdentityDeclaration(
                canonical_id=entity.canonical_id,
                participation_mode=ParticipationMode.OWNER,
                owner_scope=owner_scope,
                adapter=ref.adapter_name,
                source_ref=ref,
                deprecated=deprecated,
            )
        )
        existing = identity_table.get(entity.canonical_id)
        if existing is not None:
            if strict_identity:
                raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
            continue
        identity_table[entity.canonical_id] = ref
        entities.append(entity)
        entity_source_adapters[entity.canonical_id] = ref.adapter_name
```

- [ ] **Step 3e: Emit at the commons loop (replace lines 449-455) + overlay borrower**

```python
        for entity, ref in commons_loaded:
            owner_scope, deprecated = classify_owner_scope(ref.adapter_name, project_name=project_name)
            identity_declarations.append(
                IdentityDeclaration(
                    canonical_id=entity.canonical_id,
                    participation_mode=ParticipationMode.OWNER,
                    owner_scope=owner_scope,
                    adapter=ref.adapter_name,
                    source_ref=ref,
                    deprecated=deprecated,
                )
            )
            overlay_path = commons_overlay_paths.get(entity.canonical_id)
            if overlay_path:
                identity_declarations.append(
                    IdentityDeclaration(
                        canonical_id=entity.canonical_id,
                        participation_mode=ParticipationMode.BORROWER,
                        owner_scope=owner_scope,
                        adapter="overlay",
                        source_ref=SourceRef(adapter_name="overlay", path=overlay_path),
                        deprecated=False,
                    )
                )
            existing = identity_table.get(entity.canonical_id)
            if existing is not None:
                if strict_identity:
                    raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
                continue
            identity_table[entity.canonical_id] = ref
            entities.append(entity)
            entity_source_adapters[entity.canonical_id] = ref.adapter_name
```

Confirm `SourceRef` is imported in `sources.py` (it is — used at line 262's type). Add it to the `ProjectSources(...)` constructor at the end (line 459+):

```python
        identity_declarations=identity_declarations,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_identity_declarations_loader.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/sources.py science/tests/test_identity_declarations_loader.py
git commit -m "feat(substrate): collect identity declarations in loader + strict_identity flag"
```

---

## Task 4: `build_identity_table` from a loaded `ProjectSources`

Now that declarations live on `ProjectSources`, the builder is a thin wrapper that also works against a structural stub (so unit tests need no full loader).

**Files:**
- Modify: `src/science_tool/graph/identity_table.py` (append)
- Test: `tests/test_graph_identity_table.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_graph_identity_table.py
from dataclasses import dataclass as _dc, field as _f

from science_tool.graph.identity_table import build_identity_table


@_dc
class _Sources:
    identity_declarations: list = _f(default_factory=list)


def test_build_identity_table_wraps_declarations_and_finds_collisions():
    src = _Sources(identity_declarations=[
        _decl("question:q1", adapter="markdown", path="entities/question/0007-q1.md"),
        _decl("question:q1", adapter="aggregate",
              path="knowledge/sources/local/entities.yaml", deprecated=True),
        _decl("hypothesis:h1"),
    ])
    table = build_identity_table(src)
    assert len(table.rows) == 3
    cols = table.collisions()
    assert [c.canonical_id for c in cols] == ["question:q1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py::test_build_identity_table_wraps_declarations_and_finds_collisions -q`
Expected: FAIL — `ImportError: cannot import name 'build_identity_table'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/science_tool/graph/identity_table.py`:

```python
from typing import Protocol


class _DeclaredSources(Protocol):
    identity_declarations: list[IdentityDeclaration]


def build_identity_table(sources: _DeclaredSources) -> IdentityTable:
    """Compile the IdentityTable from a project's collected declarations (§C1)."""
    return IdentityTable(rows=list(sources.identity_declarations))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/identity_table.py science/tests/test_graph_identity_table.py
git commit -m "feat(substrate): build_identity_table wraps collected declarations"
```

---

## Task 5: `audit_identity_table` — collisions as audit rows

**Files:**
- Modify: `src/science_tool/graph/migrate.py` (add `audit_identity_table` + imports)
- Test: `tests/test_graph_migrate_identity_audit.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graph_migrate_identity_audit.py
from science_model.source_ref import SourceRef
from science_tool.graph.identity_table import (
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
)
from science_tool.graph.migrate import audit_identity_table


def _owner(cid, adapter, path, deprecated=False):
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=ParticipationMode.OWNER,
        owner_scope="proj",
        adapter=adapter,
        source_ref=SourceRef(adapter_name=adapter, path=path),
        deprecated=deprecated,
    )


def test_audit_identity_table_reports_collision_rows():
    table = IdentityTable(rows=[
        _owner("question:q1", "markdown", "entities/question/0007-q1.md"),
        _owner("question:q1", "aggregate", "knowledge/sources/local/entities.yaml", deprecated=True),
    ])
    rows = audit_identity_table(table)
    assert len(rows) == 1
    row = rows[0]
    assert row["check"] == "identity_collision"
    assert row["status"] == "fail"
    assert row["source"] == "question:q1"
    assert row["field"] == "owner_scope"
    assert row["target"] == "proj"
    assert "entities/question/0007-q1.md" in row["details"]
    assert "knowledge/sources/local/entities.yaml" in row["details"]


def test_audit_identity_table_clean_when_no_collisions():
    table = IdentityTable(rows=[_owner("hypothesis:h1", "markdown", "entities/hypothesis/0001-h1.md")])
    assert audit_identity_table(table) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate_identity_audit.py -q`
Expected: FAIL — `ImportError: cannot import name 'audit_identity_table'`.

- [ ] **Step 3: Write minimal implementation**

In `src/science_tool/graph/migrate.py`, add near the other `graph` imports:

```python
from science_tool.graph.identity_table import IdentityTable, build_identity_table
```

Add the function directly above `audit_project_sources` (~line 144):

```python
def audit_identity_table(table: IdentityTable) -> list[dict]:
    """Turn identity-table collisions into graph-audit rows (design §B3, §C2)."""
    rows: list[dict] = []
    for collision in table.collisions():
        paths = [(r.source_ref.path if r.source_ref else "<unknown>") for r in collision.rows]
        rows.append(
            {
                "check": "identity_collision",
                "status": "fail",
                "source": collision.canonical_id,
                "field": "owner_scope",
                "target": collision.owner_scope,
                "details": "owned by " + " and ".join(paths),
            }
        )
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate_identity_audit.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/migrate.py science/tests/test_graph_migrate_identity_audit.py
git commit -m "feat(substrate): audit_identity_table emits identity_collision rows"
```

---

## Task 6: Fold identity audit into `audit_project_sources` + real integration test

**Files:**
- Modify: `src/science_tool/graph/migrate.py` (`audit_project_sources`)
- Test: `tests/test_graph_migrate_identity_audit.py` (append — real `tmp_path` loader)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_graph_migrate_identity_audit.py
from pathlib import Path

import pytest

from science_tool.graph.errors import EntityIdentityCollisionError
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import load_project_sources


def _seed(root: Path, name: str = "proj") -> None:
    (root / "science.yaml").write_text(
        f"name: {name}\nprofile: research\nprofiles: {{local: local}}\n", encoding="utf-8"
    )


def _md(root: Path, rel: str, cid: str, kind: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{cid}"\ntype: "{kind}"\ntitle: "{cid}"\n---\n', encoding="utf-8")


def _agg(root: Path, cid: str, kind: str) -> None:
    # AggregateAdapter reads the `entities:` key of a mapping (aggregate.py:69).
    local = root / "knowledge" / "sources" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "entities.yaml").write_text(
        f"entities:\n  - canonical_id: {cid}\n    kind: {kind}\n    title: {cid}\n"
        f"    profile: local\n    source_path: knowledge/sources/local/entities.yaml\n",
        encoding="utf-8",
    )


def test_strict_load_still_raises_on_stub_shadow(tmp_path: Path) -> None:
    _seed(tmp_path)
    _md(tmp_path, "entities/questions/q1.md", "question:q1", "question")
    _agg(tmp_path, "question:q1", "question")
    with pytest.raises(EntityIdentityCollisionError):
        load_project_sources(tmp_path, include_commons=False)


def test_nonstrict_load_then_audit_reports_identity_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _md(tmp_path, "entities/questions/q1.md", "question:q1", "question")
    _agg(tmp_path, "question:q1", "question")
    sources = load_project_sources(tmp_path, include_commons=False, strict_identity=False)
    rows, failed = audit_project_sources(sources)
    assert failed is True
    collision_rows = [r for r in rows if r["check"] == "identity_collision"]
    assert len(collision_rows) == 1
    assert collision_rows[0]["source"] == "question:q1"


def test_clean_project_audit_has_no_identity_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _md(tmp_path, "entities/hypotheses/h1.md", "hypothesis:h1", "hypothesis")
    sources = load_project_sources(tmp_path, include_commons=False)
    rows, _ = audit_project_sources(sources)
    assert [r for r in rows if r["check"] == "identity_collision"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate_identity_audit.py::test_nonstrict_load_then_audit_reports_identity_collision -q`
Expected: FAIL — no `identity_collision` row yet (audit doesn't consult the identity table).

- [ ] **Step 3: Write minimal implementation**

Read `audit_project_sources` (`graph/migrate.py:145-191`) in full first. Preserve **every** existing check and the existing `AliasCollisionError` early branch; only append the identity block before the final return and OR its failure into the returned bool. Concretely, ensure both the alias-collision return path and the normal path include the identity rows. The safest edit keeps the existing body but, instead of `return (rows, failed)` / the early `return ([...], True)`, routes through a shared tail:

```python
    # Additive identity-table audit (design §C2): consume the compiled model.
    identity_rows = audit_identity_table(build_identity_table(sources))
    rows.extend(identity_rows)
    failed = failed or bool(identity_rows)
    return rows, failed
```

If the current function early-returns inside the `except AliasCollisionError` block, refactor so that branch sets `rows`/`failed` and falls through to this shared tail rather than returning directly (so an alias collision AND an identity collision both surface). Do not remove the alias row.

- [ ] **Step 4: Run test to verify it passes (and nothing regressed)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate_identity_audit.py -q`
Expected: PASS (5 passed).

Regression sweep:
Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate.py tests/test_load_project_sources_unified.py tests/test_entity_layout_migration.py tests/test_entity_errors.py -q`
Expected: all PASS. If a test asserted an exact audit-row list on a project that genuinely has overlapping owners, update it to allow the new `identity_collision` row (the row is correct; the old assertion was blind to the collision).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/migrate.py science/tests/test_graph_migrate_identity_audit.py
git commit -m "feat(substrate): fold identity-table collisions into audit_project_sources (additive)"
```

---

## Task 7: Route audit/diagnostic entry points to non-strict loading

The graph-audit/diagnostic entry points still load default-strict, so they'd
crash on a real duplicate instead of reporting it (review High-1). Route them to
`strict_identity=False`: `materialization_audit`, `collect_unresolved_refs`, and
the broader `build_health_report` diagnostic sweep. Keep the materialization
**build** strict. Also: `health`'s `collect_unresolved_refs` groups *every* fail
row by `target`, which would mislabel an `identity_collision` row (whose `target`
is the owner scope, e.g. `"proj"`) as an unresolved reference — exclude that
check from the grouping.

**Files:**
- Modify: `src/science_tool/graph/materialize.py` (`materialization_audit`, line 212)
- Modify: `src/science_tool/graph/health.py` (`collect_unresolved_refs`, lines 106, 111-117; `build_health_report`, line 571)
- Test: `tests/test_identity_audit_entrypoints.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_identity_audit_entrypoints.py
from __future__ import annotations

from pathlib import Path

from science_tool.graph.health import build_health_report, collect_unresolved_refs
from science_tool.graph.materialize import materialization_audit


def _seed(root: Path, name: str = "proj") -> None:
    (root / "science.yaml").write_text(
        f"name: {name}\nprofile: research\nprofiles: {{local: local}}\n", encoding="utf-8"
    )


def _md(root: Path, rel: str, cid: str, kind: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{cid}"\ntype: "{kind}"\ntitle: "{cid}"\n---\n', encoding="utf-8")


def _agg(root: Path, cid: str, kind: str) -> None:
    local = root / "knowledge" / "sources" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "entities.yaml").write_text(
        f"entities:\n  - canonical_id: {cid}\n    kind: {kind}\n    title: {cid}\n"
        f"    profile: local\n    source_path: knowledge/sources/local/entities.yaml\n",
        encoding="utf-8",
    )


def _stub_shadow(root: Path) -> None:
    _seed(root)
    _md(root, "entities/questions/q1.md", "question:q1", "question")
    _agg(root, "question:q1", "question")


def test_materialization_audit_reports_collision_without_crashing(tmp_path: Path) -> None:
    _stub_shadow(tmp_path)
    rows, has_failures = materialization_audit(tmp_path)  # must not raise
    assert has_failures is True
    assert any(r["check"] == "identity_collision" and r["source"] == "question:q1" for r in rows)


def test_collect_unresolved_refs_excludes_identity_collision(tmp_path: Path) -> None:
    _stub_shadow(tmp_path)
    refs = collect_unresolved_refs(tmp_path)  # must not raise
    # the collision is NOT mislabeled as an unresolved reference (e.g. to "proj")
    assert all(ref.target != "proj" for ref in refs)


def test_build_health_report_diagnostic_load_is_nonstrict(tmp_path: Path) -> None:
    _stub_shadow(tmp_path)
    report = build_health_report(tmp_path)  # must not raise
    assert report["project_root"] == str(tmp_path.resolve())
```

> `collect_unresolved_refs` returns a list of `UnresolvedRef`; each has a
> `target` attribute (see `health.py`). The assertion confirms the owner-scope
> target of an identity_collision row never leaks into the unresolved-ref list.
> `build_health_report` is the broader diagnostic sweep; the test only asserts
> report-not-crash because identity-collision findings are surfaced by graph
> audit in this phase, not by a dedicated health bucket yet.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_identity_audit_entrypoints.py -q`
Expected: FAIL — `materialization_audit` or `build_health_report` raises
`EntityIdentityCollisionError` (strict load), so the tests error before asserting.

- [ ] **Step 3a: Non-strict load in `materialization_audit`**

In `src/science_tool/graph/materialize.py`, change line 212 from:

```python
    rows, has_failures = audit_project_sources(load_project_sources(project_root.resolve()))
```

to:

```python
    rows, has_failures = audit_project_sources(
        load_project_sources(project_root.resolve(), strict_identity=False)
    )
```

Leave the `materialize`/build function above it (ending ~line 207) untouched — a build must still fail hard on a real duplicate.

- [ ] **Step 3b: Non-strict load + filter in `collect_unresolved_refs`**

In `src/science_tool/graph/health.py`, change line 106 from:

```python
        sources = load_project_sources(project_root.resolve())
```

to:

```python
        sources = load_project_sources(project_root.resolve(), strict_identity=False)
```

Then in the fail-row grouping loop (lines 111-117), skip identity-collision rows — they are reported separately and are not unresolved references:

```python
    for row in rows:
        if row["status"] != "fail":
            continue
        if row["check"] == "identity_collision":
            continue
        target = row["target"]
        source = row["source"]
        if source not in by_target[target]:
            by_target[target].append(source)
```

Finally, in `build_health_report` (around line 571), keep the existing
`strict_core_schema=False` diagnostic behavior and add `strict_identity=False`:

```python
        context.sources = context.run(
            "load_project_sources",
            lambda: load_project_sources(
                project_root,
                strict_core_schema=False,
                strict_identity=False,
            ),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_identity_audit_entrypoints.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/materialize.py science/src/science_tool/graph/health.py science/tests/test_identity_audit_entrypoints.py
git commit -m "feat(substrate): graph audit/diagnostic entry points load non-strict and report identity collisions"
```

---

## Task 8: Full-suite green + ruff

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: all PASS. The only intended behavior change is the new opt-in `strict_identity=False` path and the additive `identity_collision` audit row; default-path behavior is unchanged, so existing tests should stay green. Reconcile any test that asserted an exact audit-row set on an overlapping-owner project (see Task 6 Step 4).

- [ ] **Step 2: Lint/format**

Run: `cd ~/d/science/science && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: clean. If formatting differs, run `uv run --frozen ruff format .` and re-stage.

- [ ] **Step 3: Commit any lint fixes**

```bash
cd ~/d/science && git add -A science/
git commit -m "chore(substrate): ruff clean for identity-table foundation"
```

---

## Self-Review

**1. Spec coverage (this plan's scope only):**
- §B3 two columns (`participation_mode` × `owner_scope`) → Task 1 types; Tasks 2–3 set them at emit time. ✓
- §B3a identity key `(owner_scope, canonical_id)` → Task 1 `owners()`/`collisions()`. ✓
- §C3 adapter modes (commons owner@commons, overlay borrower@commons, aggregate deprecated owner) → Task 2 classifier + Task 3 emit sites. ✓
- §C2 consumers read the compiled model → Tasks 5–6 (audit consumes `build_identity_table`). ✓
- Review-1 High (loader raises/collapses before the table sees collisions) → Task 3 collects declarations *before* the dedup and adds `strict_identity=False`; Task 7 routes the audit/diagnostic entry points (`materialization_audit`, `collect_unresolved_refs`, `build_health_report`) to non-strict so they report instead of crash. ✓
- Review-1 High (dict loses provenance) → row-based `identity_declarations`, each carrying its own adapter + source_ref. ✓
- Review-1 Medium (invalid integration test) → Task 6 uses real `tmp_path` + `load_project_sources`, asserts strict raises and non-strict reports. ✓
- Review-1 Medium (silent `"markdown"` default) → `classify_owner_scope` raises on empty adapter; declarations always carry the true adapter. ✓
- Review-2 High (audit entry points still load strict) → Task 7. ✓
- Review-2 High (aggregate fixture shape) → all `entities.yaml` helpers now write the `entities:` mapping AggregateAdapter reads (`aggregate.py:69`). ✓
- Review-2 Medium (datapackage classification) → `classify_owner_scope` marks `datapackage` a deprecated transitional owner alongside `aggregate` (Task 2), so Phase 2 can find orphan datapackages. ✓
- Explicitly deferred (named in Scope): adapter-level enforcement, scoped-ref resolution, migrator rerouting, *migrating* orphan datapackages (1.1 only flags them). Later sub-plans. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every test step shows assertions. Task 6 Step 3 instructs reading the current function first because the exact early-return structure must be preserved — it states precisely what to add and the invariant to keep, not a vague "handle it". ✓

**3. Type consistency:** `ParticipationMode`, `IdentityDeclaration(canonical_id, participation_mode, owner_scope, adapter, source_ref, deprecated)`, `IdentityCollision(owner_scope, canonical_id, rows)`, `IdentityTable.rows/owners()/collisions()`, `classify_owner_scope(adapter, *, project_name) -> (str, bool)`, `build_identity_table(sources)`, `audit_identity_table(table)` are spelled identically across Tasks 1–6. `SourceRef(adapter_name=, path=)` matches the model. `load_project_sources(..., strict_identity=True)` and `ProjectSources.identity_declarations` are consistent across Tasks 3, 4, 6. Audit-row keys match `migrate.py`. ✓

---

## Where this sits (Phase 1 roadmap — NOT part of this plan)

This is **Phase 1.1**: the compiled `IdentityTable`, collected in-loader, reported by the audit in non-strict mode. It changes no default-path behavior; `strict_identity=False` is opt-in and the audit row is additive. Subsequent Phase-1 sub-plans (each its own full plan):

- **1.2 — Adapter enforcement:** MarkdownAdapter `owner`-only; `OverlayAdapter` the sole borrower reader; `overlay_of` in an owner root (`entities/`) a conformance error (design §B2, §C3). Depends on 1.1.
- **1.3 — Scoped-ref resolution (§B3a):** `ambiguous_reference` error + scoped form (`commons:topic:x`); bare-ref search chain that never shadows owner ambiguity. Depends on 1.1.
- **1.4 — Migrator on the compiled model (§C4):** replace the alias-collision proxy + the in-memory simulation/masking with `build_identity_table`-based detection (load with `strict_identity=False`, block apply on any `identity_collision`); renumber only non-transitional project owners. Retires the masking branch's held hack. Depends on 1.1–1.3.
- **1.5 — Migrate orphan datapackages (§B4):** 1.1 already *flags* datapackage rows as deprecated transitional owners; 1.5 migrates a datapackage with no entity-file owner to a real owner file (and the conformance check that forbids a second declaration). Depends on 1.1.

Phases 2–4 (dataset reconciliation, `entities.yaml` retirement, external-reference resolver) follow Phase 1 and are out of scope here.
```

# Source Compiler — Adapter Policy Keystone (Spec 3, Slice A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the adapter-identity branching in `load_project_sources` into declared policy/hooks on the `StorageAdapter` contract, strictly behavior-neutral, pinned by characterization tests.

**Architecture:** Move the two source-record types to a leaf module (breaks the import cycle), add a small policy surface (`skip_core_on_missing_identity`, `should_defer`, `source_document`, `on_owner_declared`, `deferred_dataset_datapackage`) to `StorageAdapter` with per-adapter overrides, then rewrite the load loop to read that surface — removing every `isinstance(adapter, …)` and `adapter.name == …` branch. `classify_owner_scope` stays as the consolidated owner-scope SSOT.

**Tech Stack:** Python 3.12/3.13, Pydantic v2, pytest, uv workspace. Tool code under `science/src/science_tool/`, tests under `science/tests/`.

**Design:** `~/d/science/docs/plans/2026-06-15-source-compiler-adapter-policy-keystone-design.md`

---

## Conventions for every task

- **Worktree:** Work happens in an isolated git worktree created via `superpowers:using-git-worktrees`. Every subagent MUST `cd` into the worktree path and run `rtk git branch --show-current` to confirm it is on the feature branch before editing or committing — commits must not leak to `main`.
- **Repo layout:** the repo root is `~/d/science`; the Python workspace member lives in `~/d/science/science/`. Run Python tooling from the workspace dir via the raw `rtk` proxy (`rtk` has no `uv`/`pytest` subcommand of its own, so pass them through `rtk proxy`): `cd <worktree>/science && rtk proxy uv run --frozen pytest …`. Do NOT use `rtk pytest` or `rtk uv` (they collect 0 tests / are unrecognized in this uv workspace).
- **Git:** use `rtk git …` for status/diff/commit/branch. **Do NOT** include any `Co-Authored-By` trailer.
- **Paths in code/docs:** write `~/d/…`, never `/home/keith/…` or `/mnt/ssd/Dropbox/…`.
- **Behavior-neutral:** this slice changes no behavior. The pytest summary line is sometimes swallowed by warning capture in this repo — confirm green via exit code 0 (`echo "EXIT=$?"`) or `--junit-xml`, not the printed summary.
- **`science_model` must never import `science_tool`** (not touched here, but keep it true).

---

## File structure

- **Create** `science/src/science_tool/graph/source_records.py` — leaf module holding `MarkdownSourceDocument` and `AggregateRowMeta` (depends only on stdlib + pydantic). Future home for Slice B's `SourceRecord`/`SourceSnapshot`.
- **Modify** `science/src/science_tool/graph/sources.py` — delete the two record-type definitions, re-import them from the leaf (preserves the public path `science_tool.graph.sources.{MarkdownSourceDocument,AggregateRowMeta}`), and rewrite the load loop body.
- **Modify** `science/src/science_tool/graph/storage_adapters/base.py` — add the policy surface with common-case defaults.
- **Modify** `storage_adapters/markdown.py` — override `skip_core_on_missing_identity`, `source_document`.
- **Modify** `storage_adapters/datapackage.py` — override `should_defer`, `deferred_dataset_datapackage`.
- **Modify** `storage_adapters/aggregate.py` — override `on_owner_declared`.
- **Create** `science/tests/graph/test_source_records_relocation.py` — public-path import guard (Task 1).
- **Create** `science/tests/graph/test_adapter_policy_surface.py` — per-adapter policy unit tests (Task 2).
- **Create** `science/tests/graph/test_source_load_equivalence.py` — characterization tests pinning every collapsed branch (Task 3).
- **Create** `science/tests/graph/test_load_loop_no_adapter_branching.py` — guard that the loop is branch-free (Task 4).

---

## Task 1: Relocate record types to a leaf module

Moves `MarkdownSourceDocument` and `AggregateRowMeta` out of `sources.py` (which imports the adapter modules) into a leaf so adapters can return them without an import cycle. Pure move + re-export; behavior-neutral.

**Files:**
- Create: `science/src/science_tool/graph/source_records.py`
- Modify: `science/src/science_tool/graph/sources.py` (remove the two class definitions near lines 98–101 and 150–170; add a re-import)
- Test: `science/tests/graph/test_source_records_relocation.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/graph/test_source_records_relocation.py`:

```python
from __future__ import annotations


def test_record_types_live_in_leaf_and_reexport_from_sources() -> None:
    # Canonical home is the leaf module.
    from science_tool.graph.source_records import AggregateRowMeta, MarkdownSourceDocument

    # Public path stays valid (aggregate_retire.py + existing tests import from here).
    from science_tool.graph.sources import (
        AggregateRowMeta as SourcesAggregateRowMeta,
        MarkdownSourceDocument as SourcesMarkdownSourceDocument,
    )

    # Re-export must be the SAME object, not a copy.
    assert SourcesAggregateRowMeta is AggregateRowMeta
    assert SourcesMarkdownSourceDocument is MarkdownSourceDocument


def test_leaf_module_does_not_import_sources_or_adapters() -> None:
    import science_tool.graph.source_records as mod

    src = mod.__file__
    assert src is not None
    text = open(src, encoding="utf-8").read()
    assert "from science_tool.graph.sources" not in text
    assert "storage_adapters" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd <worktree>/science && rtk proxy uv run --frozen pytest tests/graph/test_source_records_relocation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.source_records'`.

- [ ] **Step 3: Create the leaf module**

Create `science/src/science_tool/graph/source_records.py` with the two types moved verbatim from `sources.py` (keep the `AggregateRowMeta` docstring intact):

```python
"""Leaf source-record types emitted by storage adapters during load.

Lives below ``sources.py`` (which imports the adapter modules) so adapters can
return these types without an import cycle. Slice B's ``SourceRecord`` /
``SourceSnapshot`` will join this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class MarkdownSourceDocument(BaseModel):
    path: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body: str = ""


@dataclass(frozen=True, slots=True)
class AggregateRowMeta:
    """Row-level triage metadata for one aggregate (`entities.yaml`) entry.

    Captured at load time — before non-strict dedup can drop a shadowed entry's
    Entity (sources.py emit point) — so the §B5 triage classifier can bucket every
    aggregate row. Joined to its IdentityDeclaration by (path, line), which
    AggregateAdapter always populates.
    """

    path: str
    line: int
    canonical_id: str
    kind: str
    source_path: str | None
    # 4c: the row's external authority identifier, captured from the VALIDATED
    # entity. `entity.primary_external_id` is a typed ExternalId (or None); a
    # malformed value never reaches capture (it fails ExternalId validation and the
    # row is skipped). So this is the full {source, id, curie, provenance} dump or
    # None — never a half-filled mapping that could masquerade as a backed ref.
    primary_external_id: dict[str, str] | None = None
```

- [ ] **Step 4: Remove the definitions from `sources.py` and re-import**

In `science/src/science_tool/graph/sources.py`, delete the `class MarkdownSourceDocument(BaseModel): …` block (≈ lines 98–101) and the `@dataclass(frozen=True, slots=True)\nclass AggregateRowMeta: …` block (≈ lines 150–170). Then add this import alongside the other `science_tool.graph.*` imports (near line 47), so the public path keeps resolving:

```python
from science_tool.graph.source_records import AggregateRowMeta, MarkdownSourceDocument
```

Leave every other use of these names in `sources.py` (the `ProjectSources` fields, the loop) unchanged — they now resolve via the import.

- [ ] **Step 5: Run the relocation test + the existing callers' tests**

Run:
```
cd <worktree>/science && rtk proxy uv run --frozen pytest \
  tests/graph/test_source_records_relocation.py \
  tests/test_entity_identity_health.py \
  tests/graph/test_aggregate_retire_decisions.py \
  tests/graph/test_aggregate_row_metadata.py -v ; echo "EXIT=$?"
```
Expected: EXIT=0 (the existing tests import `AggregateRowMeta`/`MarkdownSourceDocument` from `science_tool.graph.sources` and must still pass).

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/graph/source_records.py \
            science/src/science_tool/graph/sources.py \
            science/tests/graph/test_source_records_relocation.py
rtk git commit -m "refactor(source-compiler): relocate source-record types to leaf module (Spec 3 Slice A)"
```

---

## Task 2: Add the policy surface to `StorageAdapter` and overrides

Adds the declared policy (defaults on the base, overrides on the three adapters that need them). Additive only — nothing wired into the loop yet, so the full suite stays green.

**Files:**
- Modify: `science/src/science_tool/graph/storage_adapters/base.py`
- Modify: `science/src/science_tool/graph/storage_adapters/markdown.py`
- Modify: `science/src/science_tool/graph/storage_adapters/datapackage.py`
- Modify: `science/src/science_tool/graph/storage_adapters/aggregate.py`
- Test: `science/tests/graph/test_adapter_policy_surface.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/graph/test_adapter_policy_surface.py`:

```python
from __future__ import annotations

from science_model.entities import EntityType, ProjectEntity
from science_model.source_ref import SourceRef

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.source_records import AggregateRowMeta, MarkdownSourceDocument
from science_tool.graph.storage_adapters.aggregate import AggregateAdapter
from science_tool.graph.storage_adapters.bib import BibAdapter
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter
from science_tool.graph.storage_adapters.task import TaskAdapter


def _mk_entity(cid: str, kind: str) -> ProjectEntity:
    """Minimal valid ProjectEntity (all required base fields supplied)."""
    return ProjectEntity(
        id=cid,
        canonical_id=cid,
        kind=kind,
        type=EntityType(kind),
        title="X",
        project="test",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="test",
    )


def test_base_defaults_are_inert() -> None:
    # TaskAdapter overrides none of the new policy → it exercises the base defaults.
    adapter = TaskAdapter()
    assert adapter.skip_core_on_missing_identity is False
    assert adapter.should_defer(already_owned=True) is False
    assert adapter.source_document(SourceRef(adapter_name="task", path="t.md"), {}) is None
    entity = _mk_entity("task:t1", "task")
    assert adapter.on_owner_declared(
        entity=entity, ref=SourceRef(adapter_name="task", path="t.md"), raw={}, kind="task"
    ) is None
    assert adapter.deferred_dataset_datapackage(
        entity=entity, ref=SourceRef(adapter_name="task", path="t.md")
    ) is None


def test_external_reference_defers_only_when_already_owned() -> None:
    adapter = BibAdapter()
    assert adapter.participation_mode is ParticipationMode.EXTERNAL_REFERENCE
    assert adapter.should_defer(already_owned=True) is True
    assert adapter.should_defer(already_owned=False) is False


def test_markdown_overrides() -> None:
    adapter = MarkdownAdapter()
    assert adapter.skip_core_on_missing_identity is True
    ref = SourceRef(adapter_name="markdown", path="entities/h1.md")
    raw = {"kind": "hypothesis", "title": "H1", "content": "body text"}
    doc = adapter.source_document(ref, raw)
    assert isinstance(doc, MarkdownSourceDocument)
    assert doc.path == "entities/h1.md"
    assert doc.body == "body text"
    assert "content" not in doc.frontmatter
    assert doc.frontmatter["kind"] == "hypothesis"


def test_datapackage_overrides() -> None:
    adapter = DatapackageAdapter()
    assert adapter.should_defer(already_owned=True) is True
    assert adapter.should_defer(already_owned=False) is False
    entity = _mk_entity("dataset:ds2", "dataset")
    ref = SourceRef(adapter_name="datapackage", path="data/ds2/datapackage.yaml")
    assert adapter.deferred_dataset_datapackage(entity=entity, ref=ref) == (
        "dataset:ds2",
        "data/ds2/datapackage.yaml",
    )


def test_aggregate_on_owner_declared_builds_row_meta() -> None:
    adapter = AggregateAdapter(local_profile="local")
    entity = _mk_entity("concept:coined", "concept")
    ref = SourceRef(adapter_name="aggregate", path="knowledge/sources/local/entities.yaml", line=0)
    meta = adapter.on_owner_declared(entity=entity, ref=ref, raw={"source_path": "x"}, kind="concept")
    assert isinstance(meta, AggregateRowMeta)
    assert meta.canonical_id == "concept:coined"
    assert meta.line == 0
    assert meta.kind == "concept"
    assert meta.source_path == "x"
    assert meta.primary_external_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <worktree>/science && rtk proxy uv run --frozen pytest tests/graph/test_adapter_policy_surface.py -v`
Expected: FAIL — `AttributeError: 'TaskAdapter' object has no attribute 'should_defer'` (and similar).

- [ ] **Step 3: Add the policy surface to the base**

In `science/src/science_tool/graph/storage_adapters/base.py`, add the imports and the policy members. The full updated file body (keeping the existing `discover`/`load_raw`/`dump`):

```python
"""StorageAdapter base — persistence-only contract.

Per spec §Storage Adapters: an adapter may discover files, parse
storage-specific syntax, and load records into the canonical entity
model family. It MAY NOT define entity semantics — validation belongs
to the registered entity schema.
"""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import Any

from science_model.entities import Entity
from science_model.source_ref import SourceRef

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.source_records import AggregateRowMeta, MarkdownSourceDocument


class StorageAdapter(ABC):
    """Abstract base class all storage adapters inherit from.

    Subclasses MUST override `discover()` and `load_raw()`. `dump()` is
    optional during migration; the default raises NotImplementedError.

    Load-time policy is declared here (Spec 3 Slice A) so the source-load loop
    reads it instead of branching on adapter type/name. The defaults below are
    the common case (an owner adapter that contributes no extra records and never
    defers); adapters override only what differs.
    """

    name: str  # human-readable adapter name; travels in SourceRef.adapter_name

    # Default participation: an adapter declares owner rows. Subclasses that
    # contribute borrower/external-reference rows override this (design §B3/§C3).
    participation_mode: ParticipationMode = ParticipationMode.OWNER

    # When True, a core entity that fails schema validation SOLELY because it is
    # missing identity fields is skipped-with-warning even under strict_core_schema,
    # instead of raising (fb-2026-05-30-008). Only MarkdownAdapter sets this.
    skip_core_on_missing_identity: bool = False

    def discover(self, project_root: Path) -> list[SourceRef]:
        """Walk `project_root` and return one SourceRef per discoverable record.

        For adapters where one file contains many records (multi-entity
        aggregates), return one SourceRef per entry — line number included
        where practical. For single-entity files, return one SourceRef per file.
        """
        raise NotImplementedError

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        """Return a registry-dispatchable raw record.

        The returned dict MUST contain a `kind` field (string) so the registry
        can resolve the target schema. All other fields become kwargs to
        `SchemaClass.model_validate(raw)`.
        """
        raise NotImplementedError

    def dump(self, entity: Entity) -> str | dict[str, Any]:
        """Serialize an entity back to this adapter's storage format.

        Optional during migration. Subclasses raise NotImplementedError if
        write support is not implemented.
        """
        raise NotImplementedError(f"adapter {self.name!r} does not support write")

    # --- load-time policy (Spec 3 Slice A) -------------------------------------

    def should_defer(self, *, already_owned: bool) -> bool:
        """Return True to contribute no owner declaration and no duplicate entity
        when this id is already owned this load.

        Default: an external-reference adapter (bib, curie-ref) defers to an
        existing owner (§B3/§C3). DatapackageAdapter overrides this — it is an
        OWNER adapter but still defers to an existing owner (§B4).
        """
        return self.participation_mode is ParticipationMode.EXTERNAL_REFERENCE and already_owned

    def source_document(self, ref: SourceRef, raw: dict[str, Any]) -> MarkdownSourceDocument | None:
        """Optional source document captured at load time. Base: none.

        MarkdownAdapter returns the markdown body + frontmatter for the
        annotation/anchor surface.
        """
        return None

    def on_owner_declared(
        self, *, entity: Entity, ref: SourceRef, raw: dict[str, Any], kind: str
    ) -> AggregateRowMeta | None:
        """Optional row-level triage metadata captured right after this entity's
        owner declaration is emitted. Base: none. AggregateAdapter returns one
        AggregateRowMeta per entities.yaml row (§B5).
        """
        return None

    def deferred_dataset_datapackage(
        self, *, entity: Entity, ref: SourceRef
    ) -> tuple[str, str] | None:
        """When this adapter defers (should_defer True), the (canonical_id, path)
        the loop should record in `dataset_datapackages`, or None to record
        nothing. Base: none. DatapackageAdapter returns its (id, path) so member
        resources stay locatable after the owner wins the column (§B4).
        """
        return None
```

- [ ] **Step 4: Add the markdown overrides**

In `science/src/science_tool/graph/storage_adapters/markdown.py`, add the import and the two overrides inside `class MarkdownAdapter`:

```python
from science_tool.graph.source_records import MarkdownSourceDocument
```

```python
class MarkdownAdapter(StorageAdapter):
    name = "markdown"
    skip_core_on_missing_identity = True

    # ... existing __init__, scan_roots, discover, load_raw unchanged ...

    def source_document(self, ref: SourceRef, raw: dict[str, Any]) -> MarkdownSourceDocument | None:
        return MarkdownSourceDocument(
            path=ref.path,
            frontmatter={key: value for key, value in raw.items() if key != "content"},
            body=str(raw.get("content") or ""),
        )
```

- [ ] **Step 5: Add the datapackage overrides**

In `science/src/science_tool/graph/storage_adapters/datapackage.py`, add the `Entity` import and the two overrides inside `class DatapackageAdapter`:

```python
from science_model.entities import Entity
```

```python
    def should_defer(self, *, already_owned: bool) -> bool:
        return already_owned

    def deferred_dataset_datapackage(
        self, *, entity: Entity, ref: SourceRef
    ) -> tuple[str, str] | None:
        # §B4: a datapackage is attached resource metadata, not a second owner.
        # When its id is already owned (markdown owner or transitional aggregate
        # stub — both precede DatapackageAdapter), defer and record the path so
        # member-resource resolution can still find the datapackage's resources.
        return (entity.canonical_id, ref.path)
```

- [ ] **Step 6: Add the aggregate override**

In `science/src/science_tool/graph/storage_adapters/aggregate.py`, add the imports and the override inside `class AggregateAdapter`:

```python
from science_model.entities import Entity

from science_tool.graph.source_records import AggregateRowMeta
```

```python
    def on_owner_declared(
        self, *, entity: Entity, ref: SourceRef, raw: dict[str, Any], kind: str
    ) -> AggregateRowMeta | None:
        assert ref.line is not None  # AggregateAdapter always sets the entry index
        sp_raw = raw.get("source_path")
        # Capture from the VALIDATED entity, not raw: entity.primary_external_id
        # is a typed ExternalId (already validated) or None. exclude_none drops the
        # optional `version`, leaving the four required keys.
        pei = entity.primary_external_id
        return AggregateRowMeta(
            path=ref.path,
            line=ref.line,
            canonical_id=entity.canonical_id,
            kind=kind,
            # source_path is unschema'd extra metadata; normalize a malformed
            # (non-string) value to None so the report can't crash.
            source_path=sp_raw if isinstance(sp_raw, str) else None,
            primary_external_id=pei.model_dump(exclude_none=True) if pei is not None else None,
        )
```

- [ ] **Step 7: Run the policy tests + full suite**

Run:
```
cd <worktree>/science && rtk proxy uv run --frozen pytest tests/graph/test_adapter_policy_surface.py -v ; echo "EXIT=$?"
cd <worktree>/science && rtk proxy uv run --frozen pytest -q ; echo "FULL_EXIT=$?"
```
Expected: EXIT=0 and FULL_EXIT=0 (additive change; nothing wired yet, so all existing tests still pass).

- [ ] **Step 8: Commit**

```bash
rtk git add science/src/science_tool/graph/storage_adapters/base.py \
            science/src/science_tool/graph/storage_adapters/markdown.py \
            science/src/science_tool/graph/storage_adapters/datapackage.py \
            science/src/science_tool/graph/storage_adapters/aggregate.py \
            science/tests/graph/test_adapter_policy_surface.py
rtk git commit -m "feat(source-compiler): declare adapter load-time policy on StorageAdapter (Spec 3 Slice A)"
```

---

## Task 3: Characterization test pinning the FULL load output

Builds two minimal projects that exercise all five branch points, then captures the **full normalized load output** — `entities`, `identity_declarations`, `skipped_entities`, `markdown_documents`, `aggregate_rows`, `dataset_datapackages`, `entity_source_adapters` — and asserts it equals a frozen expected value **field for field** (the design's equivalence guarantee). The frozen literals below were captured from the current (pre-flip) loop, so the test runs GREEN now; Task 4's flip must keep it green. Fixture shapes are lifted from existing passing tests; the strict/non-strict split is required because branch 2 (missing-identity skip) is only meaningful under `strict_core_schema=True` while the bib→aggregate-stub defer (branch 4) is exercised under `strict_core_schema=False` (mirroring `tests/graph/test_bib_external_reference_load.py`).

**Files:**
- Test: `science/tests/graph/test_source_load_equivalence.py`

- [ ] **Step 1: Write the full-snapshot characterization test (must pass on current code)**

Create `science/tests/graph/test_source_load_equivalence.py`:

```python
"""Behavior-neutral pinning test for the Spec 3 Slice A loop refactor.

Two fixtures exercise every branch that moves from the load loop onto adapter
policy: 1 markdown source_document, 2 missing-identity skip under strict, 3
datapackage defer onto a markdown owner, 4 external-ref (bib) defer onto an
aggregate stub, 5 aggregate row-meta capture. `_snapshot` captures the full
normalized load output; the test asserts it equals a frozen value captured from
the pre-refactor loop. The flip in Task 4 must keep this green field-for-field.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_tool.graph.sources import ProjectSources, load_project_sources

_MANIFEST = "name: slice-a\nprofile: research\nprofiles: {local: local}\n"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot(s: ProjectSources) -> dict[str, Any]:
    """Normalize the full load output into deterministic, comparable values."""
    return {
        "entities": [e.canonical_id for e in s.entities],  # load sorts by canonical_id
        "identity_declarations": sorted(
            (d.canonical_id, d.participation_mode.value, d.owner_scope, d.adapter, d.deprecated)
            for d in s.identity_declarations
        ),
        "skipped_entities": sorted((x.path, x.kind, x.reason) for x in s.skipped_entities),
        "markdown_documents": sorted(
            (d.path, tuple(sorted(d.frontmatter)), d.body) for d in s.markdown_documents
        ),
        "aggregate_rows": sorted(
            (
                m.path,
                m.line,
                m.canonical_id,
                m.kind,
                m.source_path,
                tuple(sorted(m.primary_external_id.items())) if m.primary_external_id else None,
            )
            for m in s.aggregate_rows
        ),
        "dataset_datapackages": dict(s.dataset_datapackages),
        "entity_source_adapters": dict(s.entity_source_adapters),
    }


def _build_strict_project(root: Path) -> None:
    _write(root, "science.yaml", _MANIFEST)
    # branch 1 + a normal markdown owner
    _write(
        root,
        "entities/hypotheses/h1.md",
        '---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\n---\nbody\n',
    )
    # branch 2: core hypothesis missing identity → skip-warn even under strict
    _write(root, "entities/hypotheses/bad.md", '---\ntype: "hypothesis"\ntitle: "Bad"\n---\n')
    # branch 3: markdown dataset owner that a datapackage will defer to
    _write(
        root,
        "entities/datasets/ds2.md",
        '---\nid: "dataset:ds2"\ntype: "dataset"\ntitle: "DS2"\n'
        'origin: "external"\naccess: {level: "public", verified: false}\n---\n',
    )
    # branch 3: the deferring datapackage (same id as the markdown owner) + an orphan
    for dsid in ("ds2", "ds1"):
        _write(
            root,
            f"data/{dsid}/datapackage.yaml",
            yaml.safe_dump(
                {
                    "profiles": ["science-pkg-entity-1.0"],
                    "name": dsid,
                    "id": f"dataset:{dsid}",
                    "type": "dataset",
                    "title": dsid.upper(),
                    "origin": "external",
                    "access": {"level": "public", "verified": False},
                }
            ),
        )


def _build_nonstrict_project(root: Path) -> None:
    _write(root, "science.yaml", _MANIFEST)
    # branch 5: aggregate rows captured; branch 4: paper stub the bib defers to
    _write(
        root,
        "knowledge/sources/local/entities.yaml",
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "concept:coined",
                        "kind": "concept",
                        "title": "Coined",
                        "source_path": "knowledge/sources/local/entities.yaml",
                    },
                    {"canonical_id": "paper:Smith2024", "kind": "paper", "title": "S"},
                ]
            }
        ),
    )
    # branch 4: bib has the same paper id → defers to the aggregate stub
    _write(root, "papers/references.bib", "@article{Smith2024,\n  title = {Cells},\n}\n")


# Frozen expected output, captured from the current (pre-flip) loop.
EXPECTED_STRICT: dict[str, Any] = {
    "entities": ["dataset:ds1", "dataset:ds2", "hypothesis:h1"],
    "identity_declarations": [
        ("dataset:ds1", "owner", "slice-a", "datapackage", True),
        ("dataset:ds2", "owner", "slice-a", "markdown", False),
        ("hypothesis:h1", "owner", "slice-a", "markdown", False),
    ],
    "skipped_entities": [
        ("entities/hypotheses/bad.md", "hypothesis", "entity_schema_validation_failed"),
    ],
    "markdown_documents": [
        (
            "entities/datasets/ds2.md",
            ("access", "canonical_id", "file_path", "id", "kind", "origin", "title", "type"),
            "",
        ),
        ("entities/hypotheses/bad.md", ("file_path", "kind", "title", "type"), ""),
        (
            "entities/hypotheses/h1.md",
            ("canonical_id", "file_path", "id", "kind", "title", "type"),
            "body\n",
        ),
    ],
    "aggregate_rows": [],
    "dataset_datapackages": {"dataset:ds2": "data/ds2/datapackage.yaml"},
    "entity_source_adapters": {
        "dataset:ds1": "datapackage",
        "dataset:ds2": "markdown",
        "hypothesis:h1": "markdown",
    },
}

EXPECTED_NONSTRICT: dict[str, Any] = {
    "entities": ["concept:coined", "paper:Smith2024"],
    "identity_declarations": [
        ("concept:coined", "owner", "slice-a", "aggregate", True),
        ("paper:Smith2024", "owner", "slice-a", "aggregate", True),
    ],
    "skipped_entities": [],
    "markdown_documents": [],
    "aggregate_rows": [
        (
            "knowledge/sources/local/entities.yaml",
            0,
            "concept:coined",
            "concept",
            "knowledge/sources/local/entities.yaml",
            None,
        ),
        ("knowledge/sources/local/entities.yaml", 1, "paper:Smith2024", "paper", None, None),
    ],
    "dataset_datapackages": {},
    "entity_source_adapters": {"concept:coined": "aggregate", "paper:Smith2024": "aggregate"},
}


def test_strict_load_full_output_is_unchanged(tmp_path: Path) -> None:
    _build_strict_project(tmp_path)
    sources = load_project_sources(tmp_path, include_commons=False)  # strict defaults
    assert _snapshot(sources) == EXPECTED_STRICT


def test_nonstrict_load_full_output_is_unchanged(tmp_path: Path) -> None:
    _build_nonstrict_project(tmp_path)
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=True
    )
    assert _snapshot(sources) == EXPECTED_NONSTRICT
```

- [ ] **Step 2: Run on the current (pre-flip) loop and confirm GREEN**

Run: `cd <worktree>/science && rtk proxy uv run --frozen pytest tests/graph/test_source_load_equivalence.py -v ; echo "EXIT=$?"`
Expected: EXIT=0. The frozen `EXPECTED_*` literals were captured from current behavior, so the test must pass *before* the loop changes. If a literal mismatches (e.g. the environment differs), re-capture by printing `_snapshot(...)` for each fixture and update the literal to match current behavior — do NOT change the fixture or weaken `_snapshot`; the captured output IS the behavior contract the flip must preserve.

- [ ] **Step 3: Commit**

```bash
rtk git add science/tests/graph/test_source_load_equivalence.py
rtk git commit -m "test(source-compiler): pin full source-load output before Slice A flip"
```

---

## Task 4: Rewrite the loop to read adapter policy; remove all adapter branching

Replaces the five branch points with policy calls. `classify_owner_scope` stays. Pinned by the guard test (drives the change) and Task 3's characterization tests + full suite (prove no behavior changed).

**Files:**
- Modify: `science/src/science_tool/graph/sources.py` (the `load_project_sources` loop body, ≈ lines 368–536)
- Test: `science/tests/graph/test_load_loop_no_adapter_branching.py`

- [ ] **Step 1: Write the failing guard test**

Create `science/tests/graph/test_load_loop_no_adapter_branching.py`:

```python
from __future__ import annotations

import science_tool.graph.sources as sources_mod


def test_load_loop_has_no_adapter_type_or_name_branching() -> None:
    src = sources_mod.__file__
    assert src is not None
    text = open(src, encoding="utf-8").read()
    # The loop must dispatch on declared policy, not adapter identity.
    assert "isinstance(adapter," not in text
    # `classify_owner_scope(adapter.name, ...)` is a value lookup and stays, but no
    # control-flow branch may compare adapter.name to a literal.
    assert "adapter.name ==" not in text
```

- [ ] **Step 2: Run guard to verify it fails**

Run: `cd <worktree>/science && rtk proxy uv run --frozen pytest tests/graph/test_load_loop_no_adapter_branching.py -v`
Expected: FAIL — both `isinstance(adapter,` and `adapter.name ==` are present in the current loop.

- [ ] **Step 3: Rewrite the loop body**

In `science/src/science_tool/graph/sources.py`, make these five edits inside the `for adapter in adapters:` loop. Preserve the surrounding code and the exact ordering.

**Edit A — branch 1 (markdown document capture).** Replace:

```python
                if isinstance(adapter, MarkdownAdapter):
                    markdown_documents.append(
                        MarkdownSourceDocument(
                            path=ref.path,
                            frontmatter={key: value for key, value in raw.items() if key != "content"},
                            body=str(raw.get("content") or ""),
                        )
                    )
```

with:

```python
                doc = adapter.source_document(ref, raw)
                if doc is not None:
                    markdown_documents.append(doc)
```

**Edit B — branch 2 (missing-identity skip under strict).** Replace:

```python
                        if isinstance(adapter, MarkdownAdapter) and _is_missing_identity_validation(exc):
```

with:

```python
                        if adapter.skip_core_on_missing_identity and _is_missing_identity_validation(exc):
```

**Edit C — branches 3 + 4 (datapackage defer + external-ref defer).** Replace the entire two-branch block:

```python
                if isinstance(adapter, DatapackageAdapter) and entity.canonical_id in identity_table:
                    # §B4: a datapackage is attached resource metadata, not a second
                    # owner. Its id already has an owner recorded this load (a real
                    # markdown owner OR a transitional entities.yaml aggregate stub —
                    # both adapters precede DatapackageAdapter), so it DEFERS: emit no
                    # competing owner declaration and no duplicate entity (it never
                    # collides, under strict or non-strict). A datapackage shadowed by
                    # an aggregate stub rides that stub; §B5 retirement carries the
                    # debt. Only a TRUE orphan (id not yet owned) synthesizes the
                    # deprecated transitional owner below.
                    # Record its path so the geneset member gate can still locate the
                    # datapackage's resources after the owner (markdown) wins the column.
                    dataset_datapackages[entity.canonical_id] = ref.path
                    continue
                if (
                    adapter.participation_mode == ParticipationMode.EXTERNAL_REFERENCE
                    and entity.canonical_id in identity_table
                ):
                    # §B3/§C3 external-reference defer (generalized over bib + curie):
                    # an external-reference adapter contributes references, not
                    # owners. If a real owner OR a transitional aggregate stub already
                    # claimed this id this load (all owner-ish adapters precede the
                    # external-reference adapters), it defers — no second declaration,
                    # no duplicate entity, no collision under strict load. The
                    # owner->external-reference flip happens automatically on the next
                    # load once retirement drops the stub. The branch is deliberately
                    # adapter-agnostic; source-specific parsing stays in the adapter.
                    continue
```

with the single policy-driven block:

```python
                # Defer is declared by the adapter (§B3/§B4/§C3): external-reference
                # adapters (bib, curie-ref) and datapackages yield to an existing
                # owner of this id rather than emit a competing owner. A deferring
                # datapackage still reports its (id, path) so the geneset member gate
                # can locate its resources after the owner wins the column.
                if adapter.should_defer(already_owned=entity.canonical_id in identity_table):
                    pair = adapter.deferred_dataset_datapackage(entity=entity, ref=ref)
                    if pair is not None:
                        deferred_id, deferred_path = pair
                        dataset_datapackages[deferred_id] = deferred_path
                    continue
```

**Edit D — branch 5 (aggregate row capture).** Replace:

```python
                if adapter.name == "aggregate":
                    assert ref.line is not None  # AggregateAdapter always sets the entry index
                    sp_raw = raw.get("source_path")
                    # Capture from the VALIDATED entity, not raw: entity.primary_external_id
                    # is a typed ExternalId (already passed ExternalId validation) or None.
                    # exclude_none drops the optional `version`, leaving the four required keys.
                    pei = entity.primary_external_id
                    aggregate_rows.append(
                        AggregateRowMeta(
                            path=ref.path,
                            line=ref.line,
                            canonical_id=entity.canonical_id,
                            kind=kind,
                            # source_path is unschema'd extra metadata; normalize a
                            # malformed (non-string) value to None so the report can't crash.
                            source_path=sp_raw if isinstance(sp_raw, str) else None,
                            primary_external_id=pei.model_dump(exclude_none=True) if pei is not None else None,
                        )
                    )
```

with:

```python
                meta = adapter.on_owner_declared(entity=entity, ref=ref, raw=raw, kind=kind)
                if meta is not None:
                    aggregate_rows.append(meta)
```

Leave `owner_scope, deprecated = classify_owner_scope(adapter.name, project_name=project_name)` (the line just above Edit C) unchanged, and leave the `identity_declarations.append(...)`, collision handling, and `entity_source_adapters[...] = adapter.name` lines unchanged.

- [ ] **Step 4: Run the guard, characterization tests, and full suite**

Run:
```
cd <worktree>/science && rtk proxy uv run --frozen pytest \
  tests/graph/test_load_loop_no_adapter_branching.py \
  tests/graph/test_source_load_equivalence.py \
  tests/graph/test_adapter_policy_surface.py \
  tests/graph/test_source_records_relocation.py -v ; echo "EXIT=$?"
cd <worktree>/science && rtk proxy uv run --frozen pytest -q ; echo "FULL_EXIT=$?"
```
Expected: EXIT=0 (guard now passes; characterization tests still green) and FULL_EXIT=0 (≈ 5500+ tests, behavior unchanged). If the full suite reports an empty summary line, re-run with `--junit-xml=/tmp/slice-a.xml` and confirm 0 failures/errors.

- [ ] **Step 5: Lint the touched files**

Run:
```
cd <worktree>/science && rtk proxy uv run --frozen ruff check \
  src/science_tool/graph/source_records.py \
  src/science_tool/graph/sources.py \
  src/science_tool/graph/storage_adapters/base.py \
  src/science_tool/graph/storage_adapters/markdown.py \
  src/science_tool/graph/storage_adapters/datapackage.py \
  src/science_tool/graph/storage_adapters/aggregate.py ; echo "EXIT=$?"
```
Expected: EXIT=0. If `ruff` flags `MarkdownAdapter`/`DatapackageAdapter` as now-unused imports in `sources.py`, confirm first they are still used to construct the adapter list (they should be) — only remove an import ruff proves is unused.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/graph/sources.py \
            science/tests/graph/test_load_loop_no_adapter_branching.py
rtk git commit -m "refactor(source-compiler): drive source-load loop from adapter policy, remove adapter branching (Spec 3 Slice A)"
```

---

## Self-review (completed by plan author)

**1. Spec coverage**

- Adapter policy on the contract (design §"Policy surface") → Task 2.
- Record-types-to-leaf import-cycle fix (design §"Record types move to a leaf module") → Task 1, with the public re-export preserved (callers `aggregate_retire.py`, `tests/test_entity_identity_health.py`, `tests/graph/test_aggregate_retire_decisions.py` import from `science_tool.graph.sources`).
- `classify_owner_scope` kept (design §"owner_scope policy stays consolidated") → Task 4 leaves it untouched; guard allows `classify_owner_scope(adapter.name, …)` while forbidding `adapter.name ==`.
- Rewritten uniform loop (design §"The rewritten loop") → Task 4.
- Error policy preserved exactly, only `skip_core_on_missing_identity` lifted (design §"Error policy") → Task 4 Edit B.
- Behavior-neutral guarantee with the full output captured incl. `entity_source_adapters` (design §"Behavior-neutral guarantee & testing") → Task 3 asserts the FULL normalized load output (all 7 fields: `entities`, `identity_declarations`, `skipped_entities`, `markdown_documents`, `aggregate_rows`, `dataset_datapackages`, `entity_source_adapters`) equals a frozen literal captured from current behavior, field-for-field.
- Success criterion "no `isinstance(adapter,…)` / `adapter.name ==`" → Task 4 guard test.
- Out-of-scope items (error rationalization, legacy-loaders-as-adapters, `SourceSnapshot`) → not in any task, by design.

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code. Task 2 uses a verified `_mk_entity` helper (full minimal `ProjectEntity` shape); Task 3's frozen `EXPECTED_*` literals were captured from the live pre-flip loop.

**3. Type/name consistency:** Method names and signatures match across base (Task 2), overrides (Task 2), and call sites (Task 4): `should_defer(*, already_owned)`, `source_document(ref, raw)`, `on_owner_declared(*, entity, ref, raw, kind)`, `deferred_dataset_datapackage(*, entity, ref) -> tuple[str, str] | None`, `skip_core_on_missing_identity`. Record types `MarkdownSourceDocument` / `AggregateRowMeta` are created in Task 1 and imported consistently thereafter.

# Epistemic Dependency Graph — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The design is at `docs/plans/2026-05-03-epistemic-dependency-graph-design.md` — read it first; this plan implements its **Phase 1** scope.

**Goal:** Land the structural surface needed to make the project knowledge graph live: (a) explicit operational/epistemic/reference taxonomy on every registered entity kind, (b) a `bears_on` relation that captures forward-in-time epistemic dependency, auto-derived from existing typed edges and from `prov:wasDerivedFrom` provenance, with transitive closure across operational hops, and (c) a per-entity `review_state` frontmatter field plus a derived `EpistemicFreshness` flag in the materialized graph. Phase 2 (weighted sampling) is tracked as `[t011]` and is **not** in scope here.

**Architecture:** Three additive layers. (1) `science-model` gains `EntityClass` + `EpistemicReviewState` and the `bears_on` `RelationKind`. (2) `science/graph/entity_registry.py` gains `entity_class` registration metadata; `science/graph/freshness.py` (new) implements `bears_on` derivation + closure + freshness computation, called by `materialize_graph()` after existing triple emission. (3) New `entity review`, `entity needs-review`, and `graph propagate-freshness` CLI commands; `validate.sh` checks for `bears_on` target-kind correctness and `review_state` shape. No data migration — all new fields default to backward-compatible values.

**Tech Stack:** Python 3.13 + Pydantic v2 (model layer), rdflib (graph), Click (CLI), pytest (tests), Bash (validate.sh).

---

## Scope

In scope (Phase 1):
- `EntityClass` enum + classification at registry layer.
- `bears_on` relation kind in `CORE_PROFILE` + auto-derivation engine + transitive closure.
- `EpistemicReviewState` field on `Entity`; frontmatter parsing.
- `EpistemicFreshness` triples emitted into the materialized graph by `graph build`.
- `entity review`, `entity needs-review`, `graph propagate-freshness` CLI commands.
- `validate.sh` checks (lockstep with `meta/validate.sh`).
- Skill prose updates for `science:status` and `science:next-steps`.

Out of scope (Phase 2 / `[t011]` and `[t012]`):
- Weighted sampling for attention.
- Pre-registration skill recast (separate task `[t012]`).
- Content-hash–based change detection (we use frontmatter `updated` dates in phase 1).
- `bears_on` edge-weight metadata.
- Cross-project freshness propagation.

---

## File Structure

| File | Role | Status |
|---|---|---|
| `science-model/src/science_model/entities.py` | Add `EntityClass` enum + `EpistemicReviewState` model + `review_state` field on `Entity` | Modify |
| `science-model/src/science_model/frontmatter.py` | Parse `review_state` block from frontmatter | Modify |
| `science-model/src/science_model/profiles/core.py` | Add `bears_on` `RelationKind` | Modify |
| `science-model/tests/test_review_state_model.py` | Unit tests for `EpistemicReviewState` and frontmatter round-trip | Create |
| `science/src/science_tool/graph/entity_registry.py` | Add `entity_class` parameter on register methods + `kind_class()` lookup | Modify |
| `science/src/science_tool/graph/freshness.py` | `bears_on` derivation + closure + freshness computation | Create |
| `science/src/science_tool/graph/store.py` | Add `bearsOn`, `freshnessState`, `triggeredBy`, `upstreamChangeAt` to the SCI predicates list | Modify |
| `science/src/science_tool/graph/materialize.py` | Call freshness derivation after existing emission | Modify |
| `science/src/science_tool/entity_review.py` | `entity review` and `entity needs-review` CLI implementations | Create |
| `science/src/science_tool/cli.py` | Register new commands; wire `graph propagate-freshness` | Modify |
| `science/tests/test_kind_class.py` | Tests for registry `entity_class` registration | Create |
| `science/tests/test_bears_on_derivation.py` | Tests for typed-edge + provenance derivation, closure, cycle protection | Create |
| `science/tests/test_freshness_derivation.py` | Tests for freshness computation against last_reviewed dates | Create |
| `science/tests/test_entity_review_cli.py` | CLI tests for `entity review` and `entity needs-review` | Create |
| `science/tests/test_graph_propagate_freshness_cli.py` | CLI tests for the read-only sweep | Create |
| `scripts/validate.sh` | `bears_on` target classification + `review_state` shape checks | Modify |
| `meta/validate.sh` | Lockstep mirror | Modify |
| `science/tests/test_validate_script.py` | New cases for the new checks | Modify |
| `commands/science/status.md` (or skill body) | Mention freshness in the orientation output | Modify |
| `commands/science/next-steps.md` (or skill body) | Surface `needs-review` entities in the next-steps suggestions | Modify |
| `docs/claim-and-evidence-model.md` | Add `bears_on` and freshness section | Modify |
| `docs/proposition-and-evidence-model.md` | Same | Modify |

---

## Task 1: `EntityClass` enum + `EpistemicReviewState` model

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Create: `science-model/tests/test_review_state_model.py`

- [ ] **Step 1: Write failing tests**

Create `science-model/tests/test_review_state_model.py`:

```python
"""Unit tests for EntityClass and EpistemicReviewState."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from science_model.entities import EntityClass, EpistemicReviewState


def test_entity_class_values():
    assert EntityClass.EPISTEMIC.value == "epistemic"
    assert EntityClass.OPERATIONAL.value == "operational"
    assert EntityClass.REFERENCE.value == "reference"


def test_review_state_defaults():
    rs = EpistemicReviewState()
    assert rs.last_reviewed is None
    assert rs.last_review_note == ""
    assert rs.review_horizon_days is None


def test_review_state_with_values():
    rs = EpistemicReviewState(
        last_reviewed=date(2026, 5, 1),
        last_review_note="Re-checked after Lee2026 dataset added",
        review_horizon_days=90,
    )
    assert rs.last_reviewed == date(2026, 5, 1)
    assert rs.last_review_note == "Re-checked after Lee2026 dataset added"
    assert rs.review_horizon_days == 90


def test_review_state_rejects_negative_horizon():
    with pytest.raises(ValidationError, match="review_horizon_days"):
        EpistemicReviewState(review_horizon_days=-1)


def test_review_state_rejects_zero_horizon():
    with pytest.raises(ValidationError, match="review_horizon_days"):
        EpistemicReviewState(review_horizon_days=0)
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science-model/tests/test_review_state_model.py -q
```

Expected: FAIL with `ImportError: cannot import name 'EntityClass'` (or similar).

- [ ] **Step 3: Implement**

In `science-model/src/science_model/entities.py`, after the existing `class EntityType(StrEnum):` block (around line 60), add:

```python
class EntityClass(StrEnum):
    """High-level taxonomic classification of an entity kind.

    Distinguishes which kinds carry continuous belief (epistemic), which
    represent operational artifacts produced by project work (operational),
    and which name external things that rarely change (reference).

    Used by the freshness engine to decide whether an entity participates
    in `bears_on` propagation: only EPISTEMIC entities are valid targets.
    """

    EPISTEMIC = "epistemic"
    OPERATIONAL = "operational"
    REFERENCE = "reference"
```

In the same file, after `EntityClass`, add the `EpistemicReviewState` model:

```python
class EpistemicReviewState(BaseModel):
    """Per-entity review-as-of state for epistemic entities.

    `last_reviewed` is the date the user (or agent) last considered this
    entity in light of all evidence. `last_review_note` is an optional
    human-readable note about that review. `review_horizon_days` is an
    optional per-entity threshold for the `stale` state — when set,
    entities whose `last_reviewed` is older than `now - horizon` flip
    to `stale` even without any upstream change.
    """

    last_reviewed: date | None = None
    last_review_note: str = ""
    review_horizon_days: int | None = None

    @model_validator(mode="after")
    def _validate_horizon(self) -> "EpistemicReviewState":
        if self.review_horizon_days is not None and self.review_horizon_days <= 0:
            raise ValueError("review_horizon_days must be positive when set")
        return self
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science-model/tests/test_review_state_model.py -q
```

Expected: PASS, 5/5.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/tests/test_review_state_model.py
git commit -m "feat(model): add EntityClass enum and EpistemicReviewState model"
```

---

## Task 2: `review_state` field on `Entity` + frontmatter parsing

**Files:**
- Modify: `science-model/src/science_model/entities.py` — add `review_state` field
- Modify: `science-model/src/science_model/frontmatter.py` — parse it
- Modify: `science-model/tests/test_review_state_model.py` — round-trip tests

- [ ] **Step 1: Add round-trip tests**

Append to `science-model/tests/test_review_state_model.py`:

```python
from pathlib import Path
from science_model.frontmatter import parse_entity_file


def test_entity_default_review_state_is_unset(tmp_path: Path):
    p = tmp_path / "h01.md"
    p.write_text(
        '---\n'
        'id: "hypothesis:h01"\n'
        'kind: "hypothesis"\n'
        'title: "Test hypothesis"\n'
        'created: "2026-04-01"\n'
        '---\n\nBody.\n'
    )
    entity = parse_entity_file(p, project_slug="demo")
    assert entity is not None
    assert entity.review_state is None


def test_entity_parses_review_state_block(tmp_path: Path):
    p = tmp_path / "h01.md"
    p.write_text(
        '---\n'
        'id: "hypothesis:h01"\n'
        'kind: "hypothesis"\n'
        'title: "Test hypothesis"\n'
        'created: "2026-04-01"\n'
        'review_state:\n'
        '  last_reviewed: "2026-05-01"\n'
        '  last_review_note: "Re-checked after Lee2026 added"\n'
        '  review_horizon_days: 90\n'
        '---\n\nBody.\n'
    )
    entity = parse_entity_file(p, project_slug="demo")
    assert entity is not None
    assert entity.review_state is not None
    assert entity.review_state.last_reviewed == date(2026, 5, 1)
    assert entity.review_state.last_review_note == "Re-checked after Lee2026 added"
    assert entity.review_state.review_horizon_days == 90


def test_entity_review_state_partial_block(tmp_path: Path):
    p = tmp_path / "h01.md"
    p.write_text(
        '---\n'
        'id: "hypothesis:h01"\n'
        'kind: "hypothesis"\n'
        'title: "Test hypothesis"\n'
        'created: "2026-04-01"\n'
        'review_state:\n'
        '  last_reviewed: "2026-05-01"\n'
        '---\n\nBody.\n'
    )
    entity = parse_entity_file(p, project_slug="demo")
    assert entity is not None
    assert entity.review_state is not None
    assert entity.review_state.last_reviewed == date(2026, 5, 1)
    assert entity.review_state.last_review_note == ""
    assert entity.review_state.review_horizon_days is None
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science-model/tests/test_review_state_model.py -q
```

Expected: FAIL on the round-trip cases — `Entity` has no `review_state` field yet.

- [ ] **Step 3: Add field to `Entity`**

In `science-model/src/science_model/entities.py`, inside `class Entity(BaseModel):` (immediately after the `review_after: date | None = None` line, around line 163), add:

```python
    review_state: EpistemicReviewState | None = None
```

- [ ] **Step 4: Add frontmatter parsing**

In `science-model/src/science_model/frontmatter.py`, add a helper near the other `_coerce_*` functions:

```python
def _coerce_review_state(fm: dict) -> "EpistemicReviewState | None":
    raw = fm.get("review_state")
    if not isinstance(raw, dict):
        return None
    from science_model.entities import EpistemicReviewState
    return EpistemicReviewState(
        last_reviewed=_coerce_date(raw.get("last_reviewed")),
        last_review_note=str(raw.get("last_review_note") or ""),
        review_horizon_days=raw.get("review_horizon_days"),
    )
```

In the same file, inside `parse_entity_file`'s `entity_kwargs = {...}` dict (around line 300), add:

```python
        "review_state": _coerce_review_state(fm),
```

(Place the line near the existing `"review_after": _coerce_date(fm.get("review_after")),` for grouping.)

- [ ] **Step 5: Run, verify pass**

```bash
uv run --frozen pytest science-model/tests/test_review_state_model.py -q
```

Expected: PASS, 8/8.

- [ ] **Step 6: Run the full science-model test suite to catch regressions**

```bash
uv run --frozen pytest science-model/tests/ -q
```

Expected: All previously passing tests still pass; new tests pass.

- [ ] **Step 7: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/src/science_model/frontmatter.py science-model/tests/test_review_state_model.py
git commit -m "feat(model): parse review_state block from entity frontmatter"
```

---

## Task 3: `bears_on` `RelationKind` in core profile

**Files:**
- Modify: `science-model/src/science_model/profiles/core.py`
- Create: `science-model/tests/test_bears_on_relation.py`

- [ ] **Step 1: Write failing tests**

Create `science-model/tests/test_bears_on_relation.py`:

```python
"""Tests that the core profile declares the bears_on relation kind."""

from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE


EPISTEMIC_KINDS = {
    "hypothesis",
    "question",
    "proposition",
    "observation",
    "finding",
    "interpretation",
    "discussion",
    "story",
    "mechanism",
}


def test_core_profile_declares_bears_on():
    names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "bears_on" in names


def test_bears_on_predicate():
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert rel.predicate == "sci:bearsOn"


def test_bears_on_targets_are_epistemic_only():
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    declared = set(rel.target_kinds)
    # Every declared target is in the epistemic set.
    assert declared.issubset(EPISTEMIC_KINDS), f"non-epistemic targets: {declared - EPISTEMIC_KINDS}"
    # Core epistemic kinds are all declared as valid targets.
    assert EPISTEMIC_KINDS.issubset(declared), f"missing epistemic targets: {EPISTEMIC_KINDS - declared}"


def test_bears_on_sources_are_unrestricted():
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    # Empty source_kinds list = unrestricted, matching the has_participant pattern.
    assert rel.source_kinds == []
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science-model/tests/test_bears_on_relation.py -q
```

Expected: FAIL — relation not declared.

- [ ] **Step 3: Implement**

In `science-model/src/science_model/profiles/core.py`, append a new `RelationKind` to the `relation_kinds=[...]` list (immediately after the existing `produced_by` entry around line 244):

```python
        RelationKind(
            name="bears_on",
            predicate="sci:bearsOn",
            source_kinds=[],
            target_kinds=[
                "hypothesis",
                "question",
                "proposition",
                "observation",
                "finding",
                "interpretation",
                "discussion",
                "story",
                "mechanism",
            ],
            layer="layer/core",
            description=(
                "Source entity's state contributes to the evidence base of the "
                "target epistemic entity. Direction is upstream→downstream "
                "(evidence → belief). Auto-derived from typed edges and "
                "prov:wasDerivedFrom triples by the freshness engine; may also "
                "be hand-authored for cases the auto-rules miss."
            ),
        ),
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science-model/tests/test_bears_on_relation.py -q
```

Expected: PASS, 4/4.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/profiles/core.py science-model/tests/test_bears_on_relation.py
git commit -m "feat(model): declare bears_on relation kind in core profile"
```

---

## Task 4: `EntityRegistry` accepts `entity_class` at registration

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py`
- Modify: `science/tests/test_entity_registry.py` — update existing tests
- Create: `science/tests/test_kind_class.py`

- [ ] **Step 1: Write failing tests for the new behavior**

Create `science/tests/test_kind_class.py`:

```python
"""Tests for EntityRegistry's entity_class classification."""

from __future__ import annotations

import pytest

from science_model.entities import EntityClass, ProjectEntity
from science_tool.graph.entity_registry import EntityRegistry


def test_with_core_types_classifies_every_kind():
    """Every kind registered by with_core_types() must have a classification."""
    r = EntityRegistry.with_core_types()
    classifications = r.all_kind_classes()
    # Spot-check a representative sample of each class.
    assert classifications["hypothesis"] == EntityClass.EPISTEMIC
    assert classifications["proposition"] == EntityClass.EPISTEMIC
    assert classifications["observation"] == EntityClass.EPISTEMIC
    assert classifications["finding"] == EntityClass.EPISTEMIC
    assert classifications["interpretation"] == EntityClass.EPISTEMIC
    assert classifications["discussion"] == EntityClass.EPISTEMIC
    assert classifications["story"] == EntityClass.EPISTEMIC
    assert classifications["mechanism"] == EntityClass.EPISTEMIC

    assert classifications["task"] == EntityClass.OPERATIONAL
    assert classifications["dataset"] == EntityClass.OPERATIONAL
    assert classifications["workflow"] == EntityClass.OPERATIONAL
    assert classifications["workflow-run"] == EntityClass.OPERATIONAL
    assert classifications["workflow-step"] == EntityClass.OPERATIONAL
    assert classifications["data-package"] == EntityClass.OPERATIONAL
    assert classifications["research-package"] == EntityClass.OPERATIONAL
    assert classifications["paper"] == EntityClass.OPERATIONAL
    assert classifications["plan"] == EntityClass.OPERATIONAL

    assert classifications["concept"] == EntityClass.REFERENCE
    assert classifications["topic"] == EntityClass.REFERENCE
    assert classifications["article"] == EntityClass.REFERENCE
    assert classifications["variable"] == EntityClass.REFERENCE
    assert classifications["inquiry"] == EntityClass.REFERENCE


def test_kind_class_lookup_returns_classification():
    r = EntityRegistry.with_core_types()
    assert r.kind_class("hypothesis") == EntityClass.EPISTEMIC
    assert r.kind_class("dataset") == EntityClass.OPERATIONAL
    assert r.kind_class("article") == EntityClass.REFERENCE


def test_kind_class_lookup_for_unknown_kind_raises():
    from science_tool.graph.entity_registry import EntityKindNotRegisteredError
    r = EntityRegistry.with_core_types()
    with pytest.raises(EntityKindNotRegisteredError):
        r.kind_class("frobnicator")


def test_register_extension_kind_defaults_to_operational():
    r = EntityRegistry.with_core_types()

    class MyExt(ProjectEntity):
        pass

    r.register_extension_kind("nat-sys:species", MyExt)
    assert r.kind_class("nat-sys:species") == EntityClass.OPERATIONAL


def test_register_extension_kind_accepts_explicit_class():
    r = EntityRegistry.with_core_types()

    class MyExt(ProjectEntity):
        pass

    r.register_extension_kind("nat-sys:eco-claim", MyExt, entity_class=EntityClass.EPISTEMIC)
    assert r.kind_class("nat-sys:eco-claim") == EntityClass.EPISTEMIC


def test_register_core_kind_requires_entity_class():
    r = EntityRegistry()

    class MyEntity(ProjectEntity):
        pass

    # Calling without entity_class should raise TypeError (missing required kwarg).
    with pytest.raises(TypeError):
        r.register_core_kind("foo", MyEntity)  # type: ignore[call-arg]
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_kind_class.py -q
```

Expected: FAIL — no `kind_class` / `all_kind_classes` / `entity_class` parameter yet.

- [ ] **Step 3: Modify the registry**

In `science/src/science_tool/graph/entity_registry.py`, replace the file content with:

```python
"""EntityRegistry — explicit kind → schema dispatch.

Per spec §Model Registry and Kind Resolution. Core kinds are registered by
Science; extension kinds are registered by the project. Duplicate
registrations are hard errors; extensions may not shadow core kinds.

Each registered kind also carries an `EntityClass` classification
(epistemic / operational / reference) used by the freshness engine to
decide which entities can be `bears_on` targets and which propagate
needs-review state.
"""

from __future__ import annotations

from science_model.entities import (
    DatasetEntity,
    Entity,
    EntityClass,
    MechanismEntity,
    ProjectEntity,
    ResearchPackageEntity,
    TaskEntity,
    WorkflowRunEntity,
)


class EntityKindAlreadyRegisteredError(ValueError):
    """Raised when a kind is registered twice."""


class EntityKindShadowError(ValueError):
    """Raised when an extension tries to register a core kind."""


class EntityKindNotRegisteredError(KeyError):
    """Raised when resolve() is called with an unregistered kind."""


# Classification for every kind in with_core_types(). Adding a new kind there
# requires adding an entry here — the registration call asserts coverage.
_CORE_KIND_CLASSES: dict[str, EntityClass] = {
    # Typed entities
    "task": EntityClass.OPERATIONAL,
    "dataset": EntityClass.OPERATIONAL,
    "workflow-run": EntityClass.OPERATIONAL,
    "research-package": EntityClass.OPERATIONAL,
    "mechanism": EntityClass.EPISTEMIC,
    # Generic project kinds (alphabetized)
    "article": EntityClass.REFERENCE,
    "assumption": EntityClass.EPISTEMIC,
    "concept": EntityClass.REFERENCE,
    "curation-sweep": EntityClass.OPERATIONAL,
    "data-package": EntityClass.OPERATIONAL,
    "discussion": EntityClass.EPISTEMIC,
    "experiment": EntityClass.OPERATIONAL,
    "finding": EntityClass.EPISTEMIC,
    "hypothesis": EntityClass.EPISTEMIC,
    "inquiry": EntityClass.REFERENCE,
    "interpretation": EntityClass.EPISTEMIC,
    "method": EntityClass.OPERATIONAL,
    "observation": EntityClass.EPISTEMIC,
    "paper": EntityClass.OPERATIONAL,
    "plan": EntityClass.OPERATIONAL,
    "proposition": EntityClass.EPISTEMIC,
    "question": EntityClass.EPISTEMIC,
    "report": EntityClass.EPISTEMIC,
    "search": EntityClass.OPERATIONAL,
    "spec": EntityClass.OPERATIONAL,
    "story": EntityClass.EPISTEMIC,
    "topic": EntityClass.REFERENCE,
    "transformation": EntityClass.OPERATIONAL,
    "unknown": EntityClass.REFERENCE,
    "validation-report": EntityClass.EPISTEMIC,
    "variable": EntityClass.REFERENCE,
    "workflow": EntityClass.OPERATIONAL,
    "workflow-step": EntityClass.OPERATIONAL,
}


class EntityRegistry:
    """Resolves kind strings to their Entity subclass at load time."""

    def __init__(self) -> None:
        self._core: dict[str, type[Entity]] = {}
        self._profile: dict[str, type[Entity]] = {}
        self._catalog: dict[str, type[Entity]] = {}
        self._extensions: dict[str, type[Entity]] = {}
        self._kind_class: dict[str, EntityClass] = {}

    @classmethod
    def with_core_types(cls) -> "EntityRegistry":
        """Return a registry pre-populated with Science core kinds."""
        r = cls()
        # Typed entities
        r.register_core_kind("task", TaskEntity, entity_class=_CORE_KIND_CLASSES["task"])
        r.register_core_kind("dataset", DatasetEntity, entity_class=_CORE_KIND_CLASSES["dataset"])
        r.register_core_kind("workflow-run", WorkflowRunEntity, entity_class=_CORE_KIND_CLASSES["workflow-run"])
        r.register_core_kind(
            "research-package", ResearchPackageEntity, entity_class=_CORE_KIND_CLASSES["research-package"]
        )
        r.register_core_kind("mechanism", MechanismEntity, entity_class=_CORE_KIND_CLASSES["mechanism"])
        # Generic project kinds → ProjectEntity.
        for kind in (
            "concept",
            "hypothesis",
            "question",
            "proposition",
            "observation",
            "inquiry",
            "topic",
            "interpretation",
            "discussion",
            "plan",
            "assumption",
            "transformation",
            "variable",
            "method",
            "experiment",
            "article",
            "workflow",
            "workflow-step",
            "data-package",
            "finding",
            "story",
            "paper",
            "search",
            "report",
            "validation-report",
            "unknown",
            "spec",
            "curation-sweep",
        ):
            r.register_core_kind(kind, ProjectEntity, entity_class=_CORE_KIND_CLASSES[kind])
        return r

    def register_core_kind(self, kind: str, cls: type[Entity], *, entity_class: EntityClass) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core or kind in self._profile or kind in self._catalog or kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"kind {kind!r} already registered")
        self._core[kind] = cls
        self._kind_class[kind] = entity_class

    def register_profile_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        owner: str,
        entity_class: EntityClass = EntityClass.OPERATIONAL,
    ) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core:
            raise EntityKindShadowError(f"profile kind {kind!r} shadows a core kind from {owner}")
        if kind in self._profile or kind in self._catalog or kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"profile kind {kind!r} already registered")
        self._profile[kind] = cls
        self._kind_class[kind] = entity_class

    def register_catalog_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        owner: str,
        entity_class: EntityClass = EntityClass.REFERENCE,
    ) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core:
            return
        if kind in self._profile:
            raise EntityKindShadowError(f"catalog kind {kind!r} shadows an existing kind from {owner}")
        if kind in self._catalog:
            if self._catalog[kind] is cls:
                return
            raise EntityKindAlreadyRegisteredError(f"catalog kind {kind!r} already registered")
        if kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"catalog kind {kind!r} already registered")
        self._catalog[kind] = cls
        self._kind_class[kind] = entity_class

    def register_extension_kind(
        self,
        kind: str,
        cls: type[Entity],
        *,
        entity_class: EntityClass = EntityClass.OPERATIONAL,
    ) -> None:
        self._require_entity_subclass(cls)
        if kind in self._core or kind in self._profile or kind in self._catalog:
            raise EntityKindShadowError(
                f"extension kind {kind!r} shadows a registered kind; use a project-specific prefix"
            )
        if kind in self._extensions:
            raise EntityKindAlreadyRegisteredError(f"extension kind {kind!r} already registered")
        self._extensions[kind] = cls
        self._kind_class[kind] = entity_class

    def resolve(self, kind: str) -> type[Entity]:
        if kind in self._core:
            return self._core[kind]
        if kind in self._profile:
            return self._profile[kind]
        if kind in self._catalog:
            return self._catalog[kind]
        if kind in self._extensions:
            return self._extensions[kind]
        raise EntityKindNotRegisteredError(f"no schema registered for kind {kind!r}")

    def kind_class(self, kind: str) -> EntityClass:
        if kind not in self._kind_class:
            raise EntityKindNotRegisteredError(f"no classification registered for kind {kind!r}")
        return self._kind_class[kind]

    def all_kind_classes(self) -> dict[str, EntityClass]:
        return dict(self._kind_class)

    @staticmethod
    def _require_entity_subclass(candidate: object) -> None:
        if not (isinstance(candidate, type) and issubclass(candidate, Entity)):
            raise TypeError(f"registered class must subclass Entity, got {candidate!r}")
```

- [ ] **Step 4: Run, verify the new tests pass**

```bash
uv run --frozen pytest science/tests/test_kind_class.py -q
```

Expected: PASS, 6/6.

- [ ] **Step 5: Update the existing registry tests that call `register_core_kind` directly**

`science/tests/test_entity_registry.py` has two tests that call `register_core_kind` *outside* of `with_core_types()` and will hit `TypeError: missing keyword-only argument 'entity_class'`:

- `test_duplicate_core_registration_is_hard_error()` (line ~57): `registry.register_core_kind("task", TaskEntity)` — change to `registry.register_core_kind("task", TaskEntity, entity_class=EntityClass.OPERATIONAL)`. Add `from science_model.entities import EntityClass` at the top of the file.
- `test_register_core_kind_rejects_non_entity_subclass` (line ~127): `registry.register_core_kind("x", NotAnEntity)` — change to `registry.register_core_kind("x", NotAnEntity, entity_class=EntityClass.OPERATIONAL)`.

These tests are checking duplicate-detection and subclass-checking behavior; the `entity_class` value is irrelevant to what they assert.

Other call sites in `test_entity_registry.py` use `register_profile_kind`, `register_catalog_kind`, or `register_extension_kind`, which now have sensible defaults (`OPERATIONAL` / `REFERENCE` / `OPERATIONAL`). Those tests do not need updating.

After applying the edits:

```bash
uv run --frozen pytest science/tests/test_entity_registry.py -q
```

Expected: PASS, all original tests still pass.

- [ ] **Step 6: Run the full science graph tests to catch downstream regressions**

```bash
uv run --frozen pytest science/tests/test_entity_registry.py science/tests/test_extension_registration.py science/tests/test_graph_materialize.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/entity_registry.py science/tests/test_kind_class.py
git commit -m "feat(graph): classify every registered kind as epistemic/operational/reference"
```

---

## Task 5: `freshness.py` — typed-edge `bears_on` derivation

**Files:**
- Create: `science/src/science_tool/graph/freshness.py`
- Create: `science/tests/test_bears_on_derivation.py`

The derivation engine reads triples from a materialized rdflib `Dataset` and emits `bears_on` triples into the same dataset's knowledge graph. This task implements only the typed-edge rules (rules 1–7 from the design doc); provenance and `has_participant` filtering are Task 6, closure is Task 7.

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_bears_on_derivation.py`:

```python
"""Tests for typed-edge -> bears_on derivation."""

from __future__ import annotations

from rdflib import Dataset, URIRef

from science_tool.graph.freshness import derive_bears_on_from_typed_edges
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _make_dataset_with(triples: list[tuple[URIRef, URIRef, URIRef]]) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, p, o in triples:
        knowledge.add((s, p, o))
    return ds


def _bears_on_pairs(ds: Dataset) -> set[tuple[str, str]]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {
        (str(s), str(o))
        for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))
    }


def test_tests_emits_bears_on():
    """workflow-run sci:tests hypothesis -> bears_on."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.tests, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("workflow-run/wfr1")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_supports_emits_bears_on():
    """observation cito:supports proposition -> bears_on (signed -> unsigned)."""
    from rdflib.namespace import Namespace
    cito = Namespace("http://purl.org/spar/cito/")
    ds = _make_dataset_with([(_u("observation/o1"), cito.supports, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("observation/o1")), str(_u("proposition/p1"))) in _bears_on_pairs(ds)


def test_disputes_emits_bears_on():
    from rdflib.namespace import Namespace
    cito = Namespace("http://purl.org/spar/cito/")
    ds = _make_dataset_with([(_u("proposition/p1"), cito.disputes, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("proposition/p1")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_grounds_emits_bears_on():
    """workflow-run sci:grounds observation -> bears_on."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.grounds, _u("observation/o1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("workflow-run/wfr1")), str(_u("observation/o1"))) in _bears_on_pairs(ds)


def test_grounded_by_inverse_emits_bears_on():
    """finding sci:groundedBy workflow-run -> workflow-run bears_on finding."""
    ds = _make_dataset_with([(_u("finding/f1"), SCI_NS.groundedBy, _u("workflow-run/wfr1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("workflow-run/wfr1")), str(_u("finding/f1"))) in _bears_on_pairs(ds)


def test_contains_inverse_emits_bears_on_when_container_is_epistemic():
    """interpretation sci:contains finding -> finding bears_on interpretation."""
    ds = _make_dataset_with([(_u("interpretation/i1"), SCI_NS.contains, _u("finding/f1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("finding/f1")), str(_u("interpretation/i1"))) in _bears_on_pairs(ds)


def test_synthesizes_inverse_emits_bears_on():
    """story sci:synthesizes interpretation -> interpretation bears_on story."""
    ds = _make_dataset_with([(_u("story/s1"), SCI_NS.synthesizes, _u("interpretation/i1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("interpretation/i1")), str(_u("story/s1"))) in _bears_on_pairs(ds)


def test_has_proposition_inverse_emits_bears_on():
    """mechanism sci:hasProposition proposition -> proposition bears_on mechanism."""
    ds = _make_dataset_with([(_u("mechanism/m1"), SCI_NS.hasProposition, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("proposition/p1")), str(_u("mechanism/m1"))) in _bears_on_pairs(ds)


def test_addresses_does_not_emit_bears_on():
    """question sci:addresses proposition does NOT trigger bears_on (operational direction)."""
    ds = _make_dataset_with([(_u("question/q1"), SCI_NS.addresses, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds)
    assert _bears_on_pairs(ds) == set()


def test_idempotent():
    """Running derivation twice produces the same triples."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.tests, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds)
    first = _bears_on_pairs(ds)
    derive_bears_on_from_typed_edges(ds)
    second = _bears_on_pairs(ds)
    assert first == second
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_bears_on_derivation.py -q
```

Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Implement**

First, ensure `bearsOn` is in the SCI namespace's predicates list. In `science/src/science_tool/graph/store.py`, find the `_PROJECT_PREDICATES` (or equivalent) registration list. (Locate via `grep -n "SCI_NS\." store.py | head -50`; the predicate becomes addressable via `SCI_NS.bearsOn` automatically because rdflib's `Namespace` is open by default — no list change strictly required, but keep an eye on whether store.py has an explicit allowlist for graph-validate.)

Create `science/src/science_tool/graph/freshness.py`:

```python
"""Freshness engine — bears_on derivation and EpistemicFreshness computation.

Implements Phase 1 of docs/plans/2026-05-03-epistemic-dependency-graph-design.md.
Operates over an rdflib Dataset that has already been populated with the
project's typed relations and provenance triples by `materialize_graph()`.

Public surface:
    derive_bears_on_from_typed_edges(dataset)
    derive_bears_on_from_provenance(dataset, *, kind_class)
    close_bears_on(dataset, *, kind_class)
    derive_freshness(dataset, *, entities, kind_class, today)
"""

from __future__ import annotations

from rdflib import Dataset, URIRef
from rdflib.namespace import Namespace

from science_tool.graph.store import PROJECT_NS, SCI_NS

CITO_NS = Namespace("http://purl.org/spar/cito/")


def derive_bears_on_from_typed_edges(dataset: Dataset) -> None:
    """Emit `bears_on` triples derived from the project's typed relations.

    Reads the knowledge layer; writes new `sci:bearsOn` triples back into the
    same layer. Idempotent: re-running on a dataset that already contains
    derived edges does not emit duplicates (rdflib graphs are sets).

    Rules:
      ?s sci:tests           ?t  -> ?s bears_on ?t
      ?s cito:supports       ?t  -> ?s bears_on ?t
      ?s cito:disputes       ?t  -> ?s bears_on ?t
      ?s sci:grounds         ?t  -> ?s bears_on ?t
      ?f sci:groundedBy      ?s  -> ?s bears_on ?f          (inverse)
      ?c sci:contains        ?m  -> ?m bears_on ?c          (inverse)
      ?s sci:synthesizes     ?t  -> ?t bears_on ?s          (inverse)
      ?m sci:hasProposition  ?p  -> ?p bears_on ?m          (inverse)
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    direct_predicates: list[URIRef] = [
        SCI_NS.tests,
        CITO_NS.supports,
        CITO_NS.disputes,
        SCI_NS.grounds,
    ]
    inverse_predicates: list[URIRef] = [
        SCI_NS.groundedBy,
        SCI_NS.contains,
        SCI_NS.synthesizes,
        SCI_NS.hasProposition,
    ]

    new_triples: list[tuple[URIRef, URIRef, URIRef]] = []
    for predicate in direct_predicates:
        for s, _, o in knowledge.triples((None, predicate, None)):
            new_triples.append((s, SCI_NS.bearsOn, o))
    for predicate in inverse_predicates:
        for s, _, o in knowledge.triples((None, predicate, None)):
            new_triples.append((o, SCI_NS.bearsOn, s))

    for triple in new_triples:
        knowledge.add(triple)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_bears_on_derivation.py -q
```

Expected: PASS, 10/10.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/freshness.py science/tests/test_bears_on_derivation.py
git commit -m "feat(graph): typed-edge bears_on derivation in freshness module"
```

---

## Task 6: `freshness.py` — provenance-derived `bears_on` and epistemic-only `has_participant`

**Files:**
- Modify: `science/src/science_tool/graph/freshness.py`
- Modify: `science/tests/test_bears_on_derivation.py` — add provenance + has_participant cases

- [ ] **Step 1: Add failing tests**

Append to `science/tests/test_bears_on_derivation.py`:

```python
from rdflib.namespace import PROV
from science_model.entities import EntityClass
from science_tool.graph.freshness import (
    derive_bears_on_from_provenance,
    derive_bears_on_from_typed_edges,
)


def test_provenance_emits_bears_on_for_epistemic_target():
    """hypothesis prov:wasDerivedFrom article -> article bears_on hypothesis."""
    ds = _make_dataset_with([])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    provenance.add((_u("hypothesis/h1"), PROV.wasDerivedFrom, _u("article/lee2026")))

    kind_class = {
        str(_u("hypothesis/h1")): EntityClass.EPISTEMIC,
        str(_u("article/lee2026")): EntityClass.REFERENCE,
    }
    derive_bears_on_from_provenance(ds, kind_class=kind_class)

    assert (str(_u("article/lee2026")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_provenance_skips_non_epistemic_target():
    """dataset prov:wasDerivedFrom article -> NO bears_on (dataset is operational)."""
    ds = _make_dataset_with([])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    provenance.add((_u("dataset/foo"), PROV.wasDerivedFrom, _u("article/lee2026")))

    kind_class = {
        str(_u("dataset/foo")): EntityClass.OPERATIONAL,
        str(_u("article/lee2026")): EntityClass.REFERENCE,
    }
    derive_bears_on_from_provenance(ds, kind_class=kind_class)

    assert _bears_on_pairs(ds) == set()


def test_has_participant_emits_bears_on_for_epistemic_participants_only():
    """mechanism sci:hasParticipant ?p -> ?p bears_on mechanism iff p is epistemic."""
    ds = _make_dataset_with([
        (_u("mechanism/m1"), SCI_NS.hasParticipant, _u("proposition/p1")),
        (_u("mechanism/m1"), SCI_NS.hasParticipant, _u("concept/c1")),
    ])
    kind_class = {
        str(_u("mechanism/m1")): EntityClass.EPISTEMIC,
        str(_u("proposition/p1")): EntityClass.EPISTEMIC,
        str(_u("concept/c1")): EntityClass.REFERENCE,
    }
    derive_bears_on_from_typed_edges(ds, kind_class=kind_class)

    pairs = _bears_on_pairs(ds)
    assert (str(_u("proposition/p1")), str(_u("mechanism/m1"))) in pairs
    assert (str(_u("concept/c1")), str(_u("mechanism/m1"))) not in pairs
```

Note: this test passes `kind_class` to `derive_bears_on_from_typed_edges` — we extend the existing function signature in step 3. Earlier tests in this file call it without `kind_class`; update those calls too:

```python
def _kc_empty() -> dict:
    return {}
```

Then change the existing test call sites from `derive_bears_on_from_typed_edges(ds)` to `derive_bears_on_from_typed_edges(ds, kind_class=_kc_empty())`. (`has_participant` rules require classification; missing entries are treated as REFERENCE so they're skipped — preserves behavior of the existing tests.)

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_bears_on_derivation.py -q
```

Expected: FAIL — `derive_bears_on_from_provenance` doesn't exist; `derive_bears_on_from_typed_edges` doesn't accept `kind_class`.

- [ ] **Step 3: Extend `freshness.py`**

In `science/src/science_tool/graph/freshness.py`, replace the existing `derive_bears_on_from_typed_edges` and add `derive_bears_on_from_provenance`:

```python
from rdflib.namespace import PROV
from science_model.entities import EntityClass


def derive_bears_on_from_typed_edges(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass] | None = None,
) -> None:
    """Emit `bears_on` triples derived from the project's typed relations.

    `kind_class` maps an entity URI (as str) to its EntityClass. It is required
    for the `mechanism sci:hasParticipant ?p` rule, which only emits `bears_on`
    when the participant is itself epistemic. Other rules ignore it.

    See module docstring for the full rule list.
    """
    kc = kind_class or {}
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    direct_predicates: list[URIRef] = [
        SCI_NS.tests,
        CITO_NS.supports,
        CITO_NS.disputes,
        SCI_NS.grounds,
    ]
    inverse_predicates: list[URIRef] = [
        SCI_NS.groundedBy,
        SCI_NS.contains,
        SCI_NS.synthesizes,
        SCI_NS.hasProposition,
    ]

    new_triples: list[tuple[URIRef, URIRef, URIRef]] = []
    for predicate in direct_predicates:
        for s, _, o in knowledge.triples((None, predicate, None)):
            new_triples.append((s, SCI_NS.bearsOn, o))
    for predicate in inverse_predicates:
        for s, _, o in knowledge.triples((None, predicate, None)):
            new_triples.append((o, SCI_NS.bearsOn, s))

    # has_participant: emit only when participant is itself epistemic.
    for s, _, o in knowledge.triples((None, SCI_NS.hasParticipant, None)):
        if kc.get(str(o)) == EntityClass.EPISTEMIC:
            new_triples.append((o, SCI_NS.bearsOn, s))

    for triple in new_triples:
        knowledge.add(triple)


def derive_bears_on_from_provenance(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
) -> None:
    """Emit `bears_on` triples from prov:wasDerivedFrom edges.

    Rule: `?d prov:wasDerivedFrom ?s` -> `?s bears_on ?d` iff `?d` is epistemic.
    This is how papers/articles enter the dependency graph, since the core
    profile has no direct paper -> hypothesis edge — paper-to-claim provenance
    flows through `source_refs`/`evidence_refs` and is materialized as
    PROV.wasDerivedFrom by `_add_relations` in `materialize.py`.
    """
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    new_triples: list[tuple[URIRef, URIRef, URIRef]] = []
    for s, _, o in provenance.triples((None, PROV.wasDerivedFrom, None)):
        # In materialize.py the *derived* side is the subject of wasDerivedFrom.
        # If the derived entity is epistemic, the source bears on it.
        if kind_class.get(str(s)) == EntityClass.EPISTEMIC:
            new_triples.append((o, SCI_NS.bearsOn, s))

    for triple in new_triples:
        knowledge.add(triple)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_bears_on_derivation.py -q
```

Expected: PASS, 13/13.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/freshness.py science/tests/test_bears_on_derivation.py
git commit -m "feat(graph): provenance + has_participant bears_on derivation"
```

---

## Task 7: `freshness.py` — transitive closure with cycle protection

**Files:**
- Modify: `science/src/science_tool/graph/freshness.py`
- Modify: `science/tests/test_bears_on_derivation.py`

The closure step walks `bears_on` chains: if `A bears_on B` and `B bears_on C` and `C` is epistemic, emit `A bears_on C`. We bound the closure with a `visited` set to handle cycles through operational hops.

- [ ] **Step 1: Add failing tests**

Append to `science/tests/test_bears_on_derivation.py`:

```python
from science_tool.graph.freshness import close_bears_on


def test_close_bears_on_walks_to_epistemic_target():
    """A bears_on B (operational) bears_on C (epistemic) -> A bears_on C."""
    ds = _make_dataset_with([])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("dataset/d1"), SCI_NS.bearsOn, _u("workflow-run/wfr1")))
    knowledge.add((_u("workflow-run/wfr1"), SCI_NS.bearsOn, _u("hypothesis/h1")))

    kind_class = {
        str(_u("dataset/d1")): EntityClass.OPERATIONAL,
        str(_u("workflow-run/wfr1")): EntityClass.OPERATIONAL,
        str(_u("hypothesis/h1")): EntityClass.EPISTEMIC,
    }
    close_bears_on(ds, kind_class=kind_class)

    assert (str(_u("dataset/d1")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_close_bears_on_terminates_on_cycle():
    """A bears_on B bears_on A (cycle) does not infinite loop and adds nothing extra."""
    ds = _make_dataset_with([])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("workflow-run/a"), SCI_NS.bearsOn, _u("workflow-run/b")))
    knowledge.add((_u("workflow-run/b"), SCI_NS.bearsOn, _u("workflow-run/a")))
    knowledge.add((_u("workflow-run/a"), SCI_NS.bearsOn, _u("hypothesis/h1")))

    kind_class = {
        str(_u("workflow-run/a")): EntityClass.OPERATIONAL,
        str(_u("workflow-run/b")): EntityClass.OPERATIONAL,
        str(_u("hypothesis/h1")): EntityClass.EPISTEMIC,
    }
    close_bears_on(ds, kind_class=kind_class)

    pairs = _bears_on_pairs(ds)
    # Closure should add: workflow-run/b bears_on hypothesis/h1 (via a)
    assert (str(_u("workflow-run/b")), str(_u("hypothesis/h1"))) in pairs
    # Should NOT loop forever or self-edge.
    self_edges = {(s, o) for s, o in pairs if s == o}
    assert self_edges == set()


def test_close_bears_on_does_not_create_edges_to_operational():
    """Closure only emits edges to epistemic targets."""
    ds = _make_dataset_with([])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("dataset/d1"), SCI_NS.bearsOn, _u("workflow-run/wfr1")))

    kind_class = {
        str(_u("dataset/d1")): EntityClass.OPERATIONAL,
        str(_u("workflow-run/wfr1")): EntityClass.OPERATIONAL,
    }
    close_bears_on(ds, kind_class=kind_class)

    # Existing edge preserved; no new closure edges since target is not epistemic.
    pairs = _bears_on_pairs(ds)
    assert pairs == {(str(_u("dataset/d1")), str(_u("workflow-run/wfr1")))}
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_bears_on_derivation.py -q -k close
```

Expected: FAIL — `close_bears_on` doesn't exist.

- [ ] **Step 3: Implement**

Append to `science/src/science_tool/graph/freshness.py`:

```python
def close_bears_on(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
) -> None:
    """Emit transitive `bears_on` edges via DFS with cycle protection.

    For each source S that has any outgoing `bears_on` edge, walk the chain
    forward; whenever a reachable node is epistemic, emit `S bears_on T`.
    Skip self-edges (cycles through operational hops produce them otherwise).

    `kind_class` is required: closure terminates at epistemic targets, so
    we must classify every reachable node.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    # Build adjacency map from existing bears_on edges.
    adjacency: dict[URIRef, set[URIRef]] = {}
    for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None)):
        adjacency.setdefault(s, set()).add(o)

    new_triples: set[tuple[URIRef, URIRef, URIRef]] = set()
    for source in list(adjacency):
        # DFS from source.
        stack: list[URIRef] = list(adjacency[source])
        visited: set[URIRef] = set()
        while stack:
            node = stack.pop()
            if node in visited or node == source:
                continue
            visited.add(node)
            if kind_class.get(str(node)) == EntityClass.EPISTEMIC:
                new_triples.add((source, SCI_NS.bearsOn, node))
            stack.extend(adjacency.get(node, set()))

    for triple in new_triples:
        knowledge.add(triple)
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_bears_on_derivation.py -q
```

Expected: PASS, all (16/16 with the 3 new closure tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/freshness.py science/tests/test_bears_on_derivation.py
git commit -m "feat(graph): bears_on transitive closure with cycle protection"
```

---

## Task 8: `freshness.py` — `EpistemicFreshness` derivation

**Files:**
- Modify: `science/src/science_tool/graph/freshness.py`
- Create: `science/tests/test_freshness_derivation.py`

For each epistemic entity, compare `last_reviewed` (frontmatter, falling back to `created`) against the most-recent `updated` date of any upstream `bears_on` source. Emit `sci:freshnessState`, `sci:upstreamChangeAt`, `sci:triggeredBy` triples.

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_freshness_derivation.py`:

```python
"""Tests for EpistemicFreshness derivation against last_reviewed timestamps."""

from __future__ import annotations

from datetime import date

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import XSD

from science_model.entities import EntityClass
from science_tool.graph.freshness import derive_freshness
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _ds_with_bears_on(pairs: list[tuple[URIRef, URIRef]]) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, o in pairs:
        knowledge.add((s, SCI_NS.bearsOn, o))
    return ds


def _state_for(ds: Dataset, target: URIRef) -> str | None:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for _, _, o in knowledge.triples((target, SCI_NS.freshnessState, None)):
        return str(o)
    return None


def _triggered_by(ds: Dataset, target: URIRef) -> set[str]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {str(o) for _, _, o in knowledge.triples((target, SCI_NS.triggeredBy, None))}


def test_freshness_fresh_when_no_upstream_change():
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 5, 1),
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    assert _state_for(ds, _u("hypothesis/h1")) == "fresh"
    assert _triggered_by(ds, _u("hypothesis/h1")) == set()


def test_freshness_needs_review_when_upstream_changed_after_last_review():
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 4, 1),
            "created": date(2026, 3, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 3, 1),
            "updated": date(2026, 5, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    assert _state_for(ds, _u("hypothesis/h1")) == "needs-review"
    assert _triggered_by(ds, _u("hypothesis/h1")) == {str(_u("dataset/d1"))}


def test_freshness_falls_back_to_created_when_last_reviewed_unset():
    ds = _ds_with_bears_on([(_u("dataset/d1"), _u("hypothesis/h1"))])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": None,
            "created": date(2026, 5, 2),
            "updated": date(2026, 5, 2),
            "review_horizon_days": None,
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    # created (2026-05-02) > upstream updated (2026-04-01) => fresh
    assert _state_for(ds, _u("hypothesis/h1")) == "fresh"


def test_freshness_stale_when_horizon_exceeded_without_upstream_change():
    ds = _ds_with_bears_on([])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2025, 1, 1),
            "created": date(2024, 12, 1),
            "updated": date(2025, 1, 1),
            "review_horizon_days": 90,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    assert _state_for(ds, _u("hypothesis/h1")) == "stale"


def test_freshness_skips_non_epistemic_entities():
    ds = _ds_with_bears_on([])
    entities = {
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    assert _state_for(ds, _u("dataset/d1")) is None  # No freshness emitted.


def test_freshness_emits_upstream_change_at():
    ds = _ds_with_bears_on([
        (_u("dataset/d1"), _u("hypothesis/h1")),
        (_u("dataset/d2"), _u("hypothesis/h1")),
    ])
    entities = {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 4, 1),
            "created": date(2026, 3, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
        str(_u("dataset/d1")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 3, 1),
            "updated": date(2026, 4, 15),
            "review_horizon_days": None,
        },
        str(_u("dataset/d2")): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": None,
            "created": date(2026, 3, 1),
            "updated": date(2026, 5, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3))
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    upstream_at_values = [
        str(o)
        for _, _, o in knowledge.triples((_u("hypothesis/h1"), SCI_NS.upstreamChangeAt, None))
    ]
    assert upstream_at_values == ["2026-05-01"]
    triggered = _triggered_by(ds, _u("hypothesis/h1"))
    assert triggered == {str(_u("dataset/d1")), str(_u("dataset/d2"))}
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_freshness_derivation.py -q
```

Expected: FAIL — `derive_freshness` doesn't exist.

- [ ] **Step 3: Implement**

Append to `science/src/science_tool/graph/freshness.py`:

```python
from datetime import date as _date


def derive_freshness(
    dataset: Dataset,
    *,
    entities: dict[str, dict],
    today: _date,
) -> None:
    """Compute EpistemicFreshness for every epistemic entity and emit triples.

    `entities` maps URI string -> dict with keys:
        kind_class: EntityClass
        last_reviewed: date | None
        created: date | None
        updated: date | None
        review_horizon_days: int | None

    Algorithm:
      1. For each epistemic entity E:
         a. baseline = E.last_reviewed or E.created
         b. Walk every (S, bears_on, E) triple. For each S, change_at = S.updated or S.created.
         c. If any change_at > baseline, state = "needs-review", upstream_change_at = max(change_at).
            triggered_by = list of all S with change_at > baseline.
         d. Else if review_horizon_days set and (today - baseline).days > horizon, state = "stale".
         e. Else state = "fresh".
      2. Emit:
         (E, sci:freshnessState, Literal(state))
         (E, sci:upstreamChangeAt, Literal(date, datatype=xsd:date))   if upstream_change_at
         (E, sci:triggeredBy, S)                                       for each S in triggered_by

    Skips non-epistemic entities silently (no triples emitted).
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    # Build inverse adjacency: target -> {sources that bear on it}.
    bears_on_in: dict[URIRef, set[URIRef]] = {}
    for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None)):
        bears_on_in.setdefault(o, set()).add(s)

    for entity_uri_str, info in entities.items():
        if info["kind_class"] != EntityClass.EPISTEMIC:
            continue
        entity_uri = URIRef(entity_uri_str)
        baseline = info.get("last_reviewed") or info.get("created")
        if baseline is None:
            # Defensive: an entity with neither last_reviewed nor created is
            # treated as fresh. Validation ensures `created` is normally set.
            knowledge.add((entity_uri, SCI_NS.freshnessState, Literal("fresh")))
            continue

        triggered: list[URIRef] = []
        upstream_change_at: _date | None = None
        for source_uri in bears_on_in.get(entity_uri, set()):
            source_info = entities.get(str(source_uri))
            if source_info is None:
                continue
            change_at = source_info.get("updated") or source_info.get("created")
            if change_at is None:
                continue
            if change_at > baseline:
                triggered.append(source_uri)
                if upstream_change_at is None or change_at > upstream_change_at:
                    upstream_change_at = change_at

        if triggered:
            state = "needs-review"
        else:
            horizon = info.get("review_horizon_days")
            if horizon is not None and (today - baseline).days > horizon:
                state = "stale"
            else:
                state = "fresh"

        knowledge.add((entity_uri, SCI_NS.freshnessState, Literal(state)))
        if upstream_change_at is not None:
            knowledge.add((
                entity_uri,
                SCI_NS.upstreamChangeAt,
                Literal(upstream_change_at.isoformat(), datatype=XSD.date),
            ))
        for source_uri in sorted(triggered):
            knowledge.add((entity_uri, SCI_NS.triggeredBy, source_uri))
```

Also add the `XSD` import at the top of `freshness.py`:

```python
from rdflib.namespace import PROV, XSD
```

(Combine with the existing `PROV` import added in Task 6.)

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_freshness_derivation.py -q
```

Expected: PASS, 6/6.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/freshness.py science/tests/test_freshness_derivation.py
git commit -m "feat(graph): EpistemicFreshness derivation in freshness module"
```

---

## Task 9: Wire freshness into `materialize_graph()`

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Create: `science/tests/test_graph_freshness_integration.py`

- [ ] **Step 1: Write failing integration test**

Create `science/tests/test_graph_freshness_integration.py`:

```python
"""End-to-end integration: materialize_graph emits bears_on + freshness triples."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from rdflib import Dataset, URIRef

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"))


def _build_min_project(tmp_path: Path) -> Path:
    """Minimal project with one hypothesis + one task that tests it.

    A task fixture is used (not workflow-run) because materialize.py converts
    `related: [hypothesis:foo]` to a `sci:tests` triple only when the source
    entity's kind is `task` (see `materialize.py:220`). Workflow-runs would
    need an explicit authored sci:tests relation, which is heavier to set up
    in a fixture; the bears_on derivation rule fires identically either way.
    """
    root = tmp_path / "demo"
    _write(root / "science.yaml", """
        name: demo
        knowledge_profiles:
          local: core
    """)
    _write(root / "knowledge" / "graph.trig", "")
    _write(root / "doc" / "hypotheses" / "h1.md", """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """)
    # Tasks live under `tasks/active.md` per the project layout, but the
    # frontmatter parser also accepts standalone task files when authored
    # under doc/. For the simplest fixture, write a task as a single .md file
    # under doc/tasks/.
    _write(root / "doc" / "tasks" / "t1.md", """
        ---
        id: "task:t1"
        kind: "task"
        title: "Demo task"
        status: "active"
        created: "2026-05-01"
        updated: "2026-05-01"
        related: ["hypothesis:h1"]
        ---
        Body.
    """)
    return root


def _load_dataset(path: Path) -> Dataset:
    ds = Dataset()
    ds.parse(path, format="trig")
    return ds


def test_materialize_emits_bears_on_when_task_tests_hypothesis(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    # task:t1 has related:[hypothesis:h1] — materialize emits sci:tests for
    # task->hypothesis (materialize.py:220), which the freshness engine then
    # derives into a sci:bearsOn triple.
    pairs = {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}
    task_uri = str(URIRef(PROJECT_NS["task/t1"]))
    h_uri = str(URIRef(PROJECT_NS["hypothesis/h1"]))
    assert (task_uri, h_uri) in pairs


def test_materialize_emits_freshness_state(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root)
    ds = _load_dataset(trig)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    h_uri = URIRef(PROJECT_NS["hypothesis/h1"])
    states = [str(o) for _, _, o in knowledge.triples((h_uri, SCI_NS.freshnessState, None))]
    # h1.created = 2026-04-01, last_reviewed unset, t1.updated = 2026-05-01 > created => needs-review.
    assert states == ["needs-review"]


def test_materialize_does_not_mutate_entity_files(tmp_path: Path):
    root = _build_min_project(tmp_path)
    h_path = root / "doc" / "hypotheses" / "h1.md"
    before = h_path.read_text()
    before_mtime = h_path.stat().st_mtime_ns

    materialize_graph(root)

    assert h_path.read_text() == before
    assert h_path.stat().st_mtime_ns == before_mtime
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_graph_freshness_integration.py -q
```

Expected: FAIL — `materialize_graph` does not call freshness derivation yet.

- [ ] **Step 3: Wire in materialize.py**

In `science/src/science_tool/graph/materialize.py`, modify `materialize_graph()` (the existing function around line 40) to call freshness after the existing emission loops, before `save_graph_dataset`.

Add the imports near the existing block at the top:

```python
from datetime import date as _date

from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.freshness import (
    close_bears_on,
    derive_bears_on_from_provenance,
    derive_bears_on_from_typed_edges,
    derive_freshness,
)
```

Inside `materialize_graph`, after the existing `for binding in sources.bindings: ...` loop and before `trig_path = ...`, add:

```python
    # Phase 1 epistemic dependency graph: derive bears_on + freshness.
    # Use EntityRegistry.with_core_types() for classification. Profile-,
    # catalog-, and extension-kind classification is not threaded here in
    # Phase 1: those kinds default to OPERATIONAL via the defensive fallback,
    # which is the documented Phase-1 behavior (see design doc § Decisions
    # #4). Later phases can plumb the full registry through ProjectSources.
    registry = EntityRegistry.with_core_types()

    kind_class: dict[str, EntityClass] = {}
    entity_meta: dict[str, dict] = {}
    for entity in sources.entities:
        uri_str = str(_entity_uri(entity.canonical_id))
        try:
            entity_class = registry.kind_class(entity.kind)
        except EntityKindNotRegisteredError:
            entity_class = EntityClass.OPERATIONAL  # Phase-1 default for non-core kinds.
        kind_class[uri_str] = entity_class
        entity_meta[uri_str] = {
            "kind_class": entity_class,
            "last_reviewed": entity.review_state.last_reviewed if entity.review_state else None,
            "created": entity.created,
            "updated": entity.updated,
            "review_horizon_days": (
                entity.review_state.review_horizon_days if entity.review_state else None
            ),
        }

    derive_bears_on_from_typed_edges(dataset, kind_class=kind_class)
    derive_bears_on_from_provenance(dataset, kind_class=kind_class)
    close_bears_on(dataset, kind_class=kind_class)
    derive_freshness(dataset, entities=entity_meta, today=_date.today())
```

Also add the `EntityClass` and registry-error imports at the top of `materialize.py`:

```python
from science_model.entities import Entity, EntityClass
from science_tool.graph.entity_registry import EntityKindNotRegisteredError
```

- [ ] **Step 4: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_graph_freshness_integration.py -q
```

Expected: PASS, 3/3.

- [ ] **Step 5: Run the full materialize test suite**

```bash
uv run --frozen pytest science/tests/test_graph_materialize.py science/tests/test_graph_freshness_integration.py -q
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit the wiring**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_graph_freshness_integration.py
git commit -m "feat(graph): wire bears_on + freshness derivation into materialize_graph"
```

- [ ] **Step 7: Add a failing test for hand-authored `bears_on` targeting a non-epistemic kind**

The auto-derivation engine only emits `bears_on` to epistemic targets by construction. The remaining hole is *hand-authored* `bears_on` edges (in a structured `relations.yaml` or equivalent), which flow through `_add_authored_relation` and currently bypass the relation-kind target-check entirely. Add a guard at materialize time.

Append to `science/tests/test_graph_freshness_integration.py`:

```python
import pytest


def test_materialize_rejects_hand_authored_bears_on_to_non_epistemic_target(tmp_path: Path):
    """A hand-authored sci:bearsOn pointing at a dataset (operational) is invalid."""
    root = _build_min_project(tmp_path)
    # Inject a structured relation that points bears_on at a dataset.
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "datasets" / "d1.md").write_text(
        dedent(
            """
            ---
            id: "dataset:d1"
            kind: "dataset"
            title: "Demo"
            origin: "external"
            access:
              level: "public"
              verified: true
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            """
        ).lstrip()
    )
    relations_yaml = root / "doc" / "relations" / "extra.yaml"
    relations_yaml.parent.mkdir(parents=True, exist_ok=True)
    relations_yaml.write_text(
        '- subject: "task:t1"\n'
        '  predicate: "sci:bearsOn"\n'
        '  object: "dataset:d1"\n'
        '  graph_layer: "graph/knowledge"\n'
    )

    with pytest.raises(ValueError, match="bears_on"):
        materialize_graph(root)
```

(The relations.yaml shape is per `SourceRelation`'s structure used by `load_project_sources`. If the project's existing fixture pattern uses a different file path or schema for authored relations, mirror it here — the test asserts the *guard*, not the on-disk format.)

Run, verify failure:

```bash
uv run --frozen pytest science/tests/test_graph_freshness_integration.py -q -k bears_on
```

Expected: FAIL — currently `_add_authored_relation` silently accepts the bad triple.

- [ ] **Step 8: Implement the guard in `_add_authored_relation`**

In `science/src/science_tool/graph/materialize.py`, modify `_add_authored_relation` (around line 320). Add a check after the predicate is resolved and before the triple is added:

```python
def _add_authored_relation(
    relation: SourceRelation,
    *,
    dataset: Dataset,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    bridge,
    ontology_catalogs: list[OntologyCatalog],
    ext_prefixes: frozenset[str],
    kind_class: dict[str, EntityClass] | None = None,
) -> None:
    graph = dataset.graph(_graph_uri(relation.graph_layer))
    subject_uri = _canonical_entity_uri(relation.subject, entity_index=entity_index, resolver=resolver)
    predicate_uri = _resolve_relation_term(relation.predicate)

    if is_external_reference(relation.object, known_prefixes=ext_prefixes):
        object_uri = _external_uri(relation.object)
        _register_external_term(object_uri, relation.object, bridge=bridge, ontology_catalogs=ontology_catalogs)
    else:
        object_uri = _canonical_entity_uri(relation.object, entity_index=entity_index, resolver=resolver)

    # Phase 1 guard: hand-authored bears_on edges may only target epistemic kinds.
    # The auto-derivation engine respects this by construction; this catches
    # human-authored mistakes at the same place we accept their structured edges.
    if predicate_uri == SCI_NS.bearsOn and kind_class is not None:
        target_class = kind_class.get(str(object_uri))
        if target_class is not None and target_class != EntityClass.EPISTEMIC:
            raise ValueError(
                f"hand-authored bears_on must target an epistemic entity, got "
                f"{relation.object!r} (classified {target_class.value})"
            )

    graph.add((subject_uri, predicate_uri, object_uri))
```

Update the single call site in `build_dataset_from_sources` (introduced in Task 12 Step 3a) to pass `kind_class=kind_class`. Note that `kind_class` is computed *after* the loop in the current Task 9 wiring — for the guard to fire, compute it earlier, before the `_add_authored_relation` loop:

```python
def build_dataset_from_sources(sources: ProjectSources) -> Dataset:
    # ... existing top of function ...

    # Build kind_class up front so authored-relation validation can see it.
    registry = EntityRegistry.with_core_types()
    kind_class: dict[str, EntityClass] = {}
    for entity in sources.entities:
        uri_str = str(_entity_uri(entity.canonical_id))
        try:
            kind_class[uri_str] = registry.kind_class(entity.kind)
        except EntityKindNotRegisteredError:
            kind_class[uri_str] = EntityClass.OPERATIONAL

    # ... existing _add_entity loop ...
    # ... existing _add_relations loop ...

    for relation in sources.relations:
        _add_authored_relation(
            relation,
            dataset=dataset,
            entity_index=entity_index,
            resolver=resolver,
            bridge=bridge,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
            kind_class=kind_class,
        )

    # ... existing _add_binding loop ...

    # Now build entity_meta (uses kind_class already computed).
    entity_meta: dict[str, dict] = {}
    for entity in sources.entities:
        uri_str = str(_entity_uri(entity.canonical_id))
        entity_meta[uri_str] = {
            "kind_class": kind_class[uri_str],
            "last_reviewed": entity.review_state.last_reviewed if entity.review_state else None,
            "created": entity.created,
            "updated": entity.updated,
            "review_horizon_days": (
                entity.review_state.review_horizon_days if entity.review_state else None
            ),
        }

    derive_bears_on_from_typed_edges(dataset, kind_class=kind_class)
    derive_bears_on_from_provenance(dataset, kind_class=kind_class)
    close_bears_on(dataset, kind_class=kind_class)
    derive_freshness(dataset, entities=entity_meta, today=_date.today())

    return dataset
```

Run, verify pass:

```bash
uv run --frozen pytest science/tests/test_graph_freshness_integration.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit the guard**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_graph_freshness_integration.py
git commit -m "feat(graph): reject hand-authored bears_on edges to non-epistemic targets"
```

---

## Task 10: `entity review` CLI command

**Files:**
- Create: `science/src/science_tool/entity_review.py`
- Modify: `science/src/science_tool/cli.py` — register command
- Create: `science/tests/test_entity_review_cli.py`

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_entity_review_cli.py`:

```python
"""CLI tests for `entity review`."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner

from science_tool.cli import main as cli_main


def _setup_project_with_hypothesis(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "doc" / "hypotheses").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n")
    (root / "doc" / "hypotheses" / "h1.md").write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            Body.
            """
        ).lstrip()
    )
    return root


def test_entity_review_sets_last_reviewed(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    assert result.exit_code == 0, result.output

    text = (root / "doc" / "hypotheses" / "h1.md").read_text()
    today = date.today().isoformat()
    assert "review_state:" in text
    assert f"last_reviewed: \"{today}\"" in text or f"last_reviewed: {today}" in text


def test_entity_review_records_note(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(
        cli_main, ["entity", "review", "hypothesis:h1", "--note", "Re-checked after Lee2026"]
    )
    assert result.exit_code == 0, result.output

    text = (root / "doc" / "hypotheses" / "h1.md").read_text()
    assert "last_review_note" in text
    assert "Re-checked after Lee2026" in text


def test_entity_review_idempotent(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    text_first = (root / "doc" / "hypotheses" / "h1.md").read_text()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    text_second = (root / "doc" / "hypotheses" / "h1.md").read_text()
    # Second call rewrites last_reviewed to today again — same date so file unchanged.
    assert text_first == text_second


def test_entity_review_unknown_id_errors(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:nonexistent"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "unknown" in result.output.lower()


def test_entity_review_preserves_existing_review_horizon_days(tmp_path: Path, monkeypatch):
    """Reviewing must not clobber other review_state fields."""
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "doc" / "hypotheses" / "h1.md"
    h_path.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            review_state:
              last_reviewed: "2026-04-15"
              review_horizon_days: 90
            ---
            Body.
            """
        ).lstrip()
    )
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    assert result.exit_code == 0, result.output

    text = h_path.read_text()
    assert "review_horizon_days: 90" in text
    today = date.today().isoformat()
    assert today in text


def test_entity_review_preserves_existing_note_when_no_note_passed(tmp_path: Path, monkeypatch):
    """Reviewing without --note keeps any pre-existing last_review_note."""
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "doc" / "hypotheses" / "h1.md"
    h_path.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            review_state:
              last_reviewed: "2026-04-15"
              last_review_note: "Original note"
            ---
            Body.
            """
        ).lstrip()
    )
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    text = h_path.read_text()
    assert "Original note" in text


def test_entity_review_replaces_existing_note_when_new_note_passed(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "doc" / "hypotheses" / "h1.md"
    h_path.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            review_state:
              last_reviewed: "2026-04-15"
              last_review_note: "Original note"
            ---
            Body.
            """
        ).lstrip()
    )
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "New note"])
    text = h_path.read_text()
    assert "Original note" not in text
    assert "New note" in text
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_entity_review_cli.py -q
```

Expected: FAIL — command doesn't exist.

- [ ] **Step 3: Implement command body**

Create `science/src/science_tool/entity_review.py`:

```python
"""Implementation of `entity review` and `entity needs-review` commands.

`entity review <id>` updates the review_state.last_reviewed (and optional
last_review_note) frontmatter on the named entity. It is the only command
in Phase 1 that mutates entity frontmatter from the freshness pipeline.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.entities import EntityCommandError, find_entity


class ReviewError(Exception):
    pass


def review_entity(
    project_root: Path,
    entity_ref: str,
    *,
    note: str | None = None,
    today: date | None = None,
) -> Path:
    """Set review_state.last_reviewed = today on the entity's frontmatter.

    Preserves any existing review_state fields (review_horizon_days,
    last_review_note when no new note is passed) by doing a YAML
    round-trip: parse → mutate the dict → re-dump.

    Returns the entity's file path. Raises ReviewError on lookup failure.
    """
    today = today or date.today()
    try:
        location = find_entity(project_root, entity_ref)
    except EntityCommandError as exc:
        raise ReviewError(str(exc)) from exc

    path = project_root / location.rel_path
    text = path.read_text()
    new_text = _upsert_review_state(text, last_reviewed=today, note=note)
    if new_text != text:
        path.write_text(new_text)
    return path


def _upsert_review_state(text: str, *, last_reviewed: date, note: str | None) -> str:
    """Update review_state in YAML frontmatter, preserving sibling fields.

    YAML round-trip: split frontmatter from body on the `---` delimiters,
    parse the frontmatter to a dict, mutate `review_state` in place
    (creating it if missing), re-dump with `yaml.safe_dump`. This preserves
    `review_horizon_days` and any pre-existing `last_review_note` when the
    caller did not pass a new note.

    Note semantics: passing `note=None` leaves any existing
    `last_review_note` untouched. Passing `note=""` clears it.
    """
    import yaml

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        raise ReviewError("entity file lacks YAML frontmatter")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ReviewError("entity file frontmatter is unterminated")

    fm_text = "".join(lines[1:end_idx])
    body_text = "".join(lines[end_idx + 1 :])

    fm = yaml.safe_load(fm_text) or {}
    if not isinstance(fm, dict):
        raise ReviewError("frontmatter is not a YAML mapping")

    rs = fm.get("review_state")
    if not isinstance(rs, dict):
        rs = {}
    rs["last_reviewed"] = last_reviewed.isoformat()
    if note is not None:
        if note == "":
            rs.pop("last_review_note", None)
        else:
            rs["last_review_note"] = note
    fm["review_state"] = rs

    new_fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=False)
    return f"---\n{new_fm_text}---\n{body_text}"
```

- [ ] **Step 4: Wire into the CLI**

In `science/src/science_tool/cli.py`, after the existing `entity_show` / `entity_edit` / `entity_note` commands (around line 380), add:

```python
@entity_group.command("review")
@click.argument("ref")
@click.option("--note", default=None, help="Optional note recorded with the review.")
def entity_review(ref: str, note: str | None) -> None:
    """Mark an epistemic entity as reviewed-as-of today."""
    from science_tool.entity_review import ReviewError, review_entity

    try:
        path = review_entity(Path.cwd(), ref, note=note)
    except ReviewError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Reviewed {ref} -> {path.relative_to(Path.cwd())}")
```

- [ ] **Step 5: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_entity_review_cli.py -q
```

Expected: PASS, 4/4.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/entity_review.py science/src/science_tool/cli.py science/tests/test_entity_review_cli.py
git commit -m "feat(cli): add entity review command (sets last_reviewed in frontmatter)"
```

---

## Task 11: `entity needs-review` CLI command

**Files:**
- Modify: `science/src/science_tool/entity_review.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_entity_review_cli.py`

`entity needs-review` reads the materialized graph, lists entities with `freshnessState = needs-review` or `stale`. Output format mirrors existing `entity list` patterns.

- [ ] **Step 1: Add failing tests**

Append to `science/tests/test_entity_review_cli.py`:

```python
def _setup_with_built_graph(tmp_path: Path) -> Path:
    """Project where graph build has run and h1 ends up needs-review."""
    from science_tool.graph.materialize import materialize_graph

    root = _setup_project_with_hypothesis(tmp_path)
    # Add a workflow-run that tests h1 with a more recent updated date.
    (root / "doc" / "workflow-runs").mkdir(parents=True)
    (root / "doc" / "workflow-runs" / "wfr1.md").write_text(
        dedent(
            """
            ---
            id: "workflow-run:wfr1"
            kind: "workflow-run"
            title: "Demo run"
            status: "complete"
            created: "2026-05-01"
            updated: "2026-05-01"
            related: ["hypothesis:h1"]
            ---
            Body.
            """
        ).lstrip()
    )
    materialize_graph(root)
    return root


def test_entity_needs_review_lists_flagged(tmp_path: Path, monkeypatch):
    root = _setup_with_built_graph(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "needs-review"])
    assert result.exit_code == 0, result.output
    assert "hypothesis:h1" in result.output
    assert "needs-review" in result.output


def test_entity_needs_review_json_format(tmp_path: Path, monkeypatch):
    root = _setup_with_built_graph(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "needs-review", "--format", "json"])
    assert result.exit_code == 0, result.output

    import json
    payload = json.loads(result.output)
    ids = {row["id"] for row in payload}
    assert "hypothesis:h1" in ids


def test_entity_needs_review_empty_when_all_fresh(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    # Mark h1 reviewed so nothing is flagged.
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    from science_tool.graph.materialize import materialize_graph
    materialize_graph(root)
    result = runner.invoke(cli_main, ["entity", "needs-review"])
    assert result.exit_code == 0, result.output
    assert "hypothesis:h1" not in result.output
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_entity_review_cli.py -q -k needs_review
```

Expected: FAIL — command doesn't exist.

- [ ] **Step 3: Implement reader function**

Append to `science/src/science_tool/entity_review.py`:

```python
from rdflib import Dataset, URIRef
from science_tool.graph.store import DEFAULT_GRAPH_PATH, PROJECT_NS, SCI_NS


def list_needs_review(project_root: Path) -> list[dict[str, str]]:
    """Read the materialized graph and return rows for needs-review/stale entities.

    Each row: {"id": "<entity-id>", "kind": "<kind>", "state": "<state>"}.
    """
    trig = project_root / DEFAULT_GRAPH_PATH
    if not trig.exists():
        return []
    ds = Dataset()
    ds.parse(trig, format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])

    rows: list[dict[str, str]] = []
    for s, _, o in knowledge.triples((None, SCI_NS.freshnessState, None)):
        state = str(o)
        if state not in {"needs-review", "stale"}:
            continue
        # Recover entity id from URI: PROJECT_NS["<kind>/<slug>"].
        uri = str(s)
        prefix = str(PROJECT_NS)
        if uri.startswith(prefix):
            tail = uri[len(prefix):]  # e.g. "hypothesis/h1"
            kind, _, slug = tail.partition("/")
            rows.append({"id": f"{kind}:{slug}", "kind": kind, "state": state})
    rows.sort(key=lambda r: (r["state"], r["kind"], r["id"]))
    return rows
```

- [ ] **Step 4: Wire CLI command**

In `science/src/science_tool/cli.py`, after the `entity_review` command, add:

```python
@entity_group.command("needs-review")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def entity_needs_review(output_format: str) -> None:
    """List epistemic entities flagged needs-review or stale by the materialized graph."""
    from science_tool.entity_review import list_needs_review

    rows = list_needs_review(Path.cwd())
    if output_format == "json":
        click.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        click.echo("No entities flagged.")
        return
    click.echo(f"{'state':<14}{'kind':<20}{'id':<40}")
    click.echo("-" * 74)
    for row in rows:
        click.echo(f"{row['state']:<14}{row['kind']:<20}{row['id']:<40}")
```

- [ ] **Step 5: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_entity_review_cli.py -q
```

Expected: PASS, 7/7.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/entity_review.py science/src/science_tool/cli.py science/tests/test_entity_review_cli.py
git commit -m "feat(cli): add entity needs-review command"
```

---

## Task 12: `graph propagate-freshness` read-only sweep

**Files:**
- Modify: `science/src/science_tool/graph/freshness.py` — add a project-level convenience function
- Modify: `science/src/science_tool/cli.py`
- Create: `science/tests/test_graph_propagate_freshness_cli.py`

This command does the freshness derivation in memory without writing the materialized graph. Useful in CI / pre-commit hooks that want a quick "what would change?" report.

- [ ] **Step 1: Write failing test**

Create `science/tests/test_graph_propagate_freshness_cli.py`:

```python
"""CLI tests for `graph propagate-freshness` — read-only sweep."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner

from science_tool.cli import main as cli_main


def _build_project_with_stale_hypothesis(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "doc" / "hypotheses").mkdir(parents=True)
    (root / "doc" / "workflow-runs").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n")
    (root / "doc" / "hypotheses" / "h1.md").write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            Body.
            """
        ).lstrip()
    )
    (root / "doc" / "workflow-runs" / "wfr1.md").write_text(
        dedent(
            """
            ---
            id: "workflow-run:wfr1"
            kind: "workflow-run"
            title: "Demo run"
            status: "complete"
            created: "2026-05-01"
            updated: "2026-05-01"
            related: ["hypothesis:h1"]
            ---
            Body.
            """
        ).lstrip()
    )
    return root


def test_propagate_freshness_reports_needs_review(tmp_path: Path, monkeypatch):
    root = _build_project_with_stale_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["graph", "propagate-freshness"])
    assert result.exit_code == 0, result.output
    assert "hypothesis:h1" in result.output
    assert "needs-review" in result.output


def test_propagate_freshness_does_not_write_graph(tmp_path: Path, monkeypatch):
    """Sweep must be read-only — the graph file is not created if absent."""
    root = _build_project_with_stale_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    trig = root / "knowledge" / "graph.trig"
    runner = CliRunner()
    runner.invoke(cli_main, ["graph", "propagate-freshness"])
    # The sweep doesn't materialize, so the trig isn't created.
    assert not trig.exists()


def test_propagate_freshness_does_not_mutate_entity_files(tmp_path: Path, monkeypatch):
    root = _build_project_with_stale_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    h_path = root / "doc" / "hypotheses" / "h1.md"
    before_mtime = h_path.stat().st_mtime_ns

    runner = CliRunner()
    runner.invoke(cli_main, ["graph", "propagate-freshness"])

    assert h_path.stat().st_mtime_ns == before_mtime
```

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_graph_propagate_freshness_cli.py -q
```

Expected: FAIL — command doesn't exist.

- [ ] **Step 3a: Factor a shared dataset-building helper out of `materialize_graph`**

The original draft of this step replayed only `_add_relations`, missing authored relations (`_add_authored_relation`) and bindings (`_add_binding`). For projects that declare their `sci:tests` / `sci:supports` edges in structured relations files (the common case), that subset would silently disagree with `graph build`. Instead, factor a shared helper so both code paths emit the same triples.

In `science/src/science_tool/graph/materialize.py`, extract everything *between* the `Dataset()` construction and the `save_graph_dataset(...)` call into a new function. The result of the refactor:

```python
def build_dataset_from_sources(sources: ProjectSources) -> Dataset:
    """Emit knowledge/bridge/provenance triples + bears_on + freshness into
    an in-memory Dataset. Shared by `materialize_graph` (which writes the
    result to disk) and freshness sweep tools (which discard it).

    Pure: takes ProjectSources, returns a populated Dataset, never touches
    the filesystem and never mutates entity files.
    """
    from datetime import date as _date

    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    dataset.graph(PROJECT_NS["graph/causal"])
    dataset.graph(PROJECT_NS["graph/datasets"])

    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
    entity_index = {entity.canonical_id: entity for entity in sources.entities}
    ext_prefixes = _EXTERNAL_PREFIXES | external_prefixes(sources.ontology_catalogs)

    for entity in sources.entities:
        _add_entity(entity=entity, knowledge=knowledge, provenance=provenance)

    for entity in sources.entities:
        _add_relations(
            entity,
            entity_index=entity_index,
            resolver=resolver,
            knowledge=knowledge,
            bridge=bridge,
            provenance=provenance,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
        )

    for relation in sources.relations:
        _add_authored_relation(
            relation,
            dataset=dataset,
            entity_index=entity_index,
            resolver=resolver,
            bridge=bridge,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
        )

    for binding in sources.bindings:
        _add_binding(
            binding,
            knowledge=knowledge,
            provenance=provenance,
            entity_index=entity_index,
            resolver=resolver,
        )

    # Phase 1 epistemic dependency graph derivation (same logic as in
    # materialize_graph; see Task 9).
    registry = EntityRegistry.with_core_types()
    kind_class: dict[str, EntityClass] = {}
    entity_meta: dict[str, dict] = {}
    for entity in sources.entities:
        uri_str = str(_entity_uri(entity.canonical_id))
        try:
            entity_class = registry.kind_class(entity.kind)
        except EntityKindNotRegisteredError:
            entity_class = EntityClass.OPERATIONAL
        kind_class[uri_str] = entity_class
        entity_meta[uri_str] = {
            "kind_class": entity_class,
            "last_reviewed": entity.review_state.last_reviewed if entity.review_state else None,
            "created": entity.created,
            "updated": entity.updated,
            "review_horizon_days": (
                entity.review_state.review_horizon_days if entity.review_state else None
            ),
        }

    derive_bears_on_from_typed_edges(dataset, kind_class=kind_class)
    derive_bears_on_from_provenance(dataset, kind_class=kind_class)
    close_bears_on(dataset, kind_class=kind_class)
    derive_freshness(dataset, entities=entity_meta, today=_date.today())

    return dataset
```

Then `materialize_graph` becomes:

```python
def materialize_graph(project_root: Path, *, strict: bool = True) -> Path:
    project_root = project_root.resolve()
    # ... (existing strict-mode pre-check, unchanged) ...

    sources = load_project_sources(project_root)
    rows, has_failures = audit_project_sources(sources)
    if has_failures:
        details = "; ".join(f"{row['source']} -> {row['target']}" for row in rows if row["status"] == "fail")
        msg = f"Cannot materialize graph with unresolved references: {details}"
        raise ValueError(msg)

    dataset = build_dataset_from_sources(sources)

    trig_path = project_root / DEFAULT_GRAPH_PATH
    trig_path.parent.mkdir(parents=True, exist_ok=True)
    save_graph_dataset(dataset, trig_path)
    return trig_path
```

The Task 9 wiring instructions are superseded by this refactor: `materialize_graph` no longer contains the freshness derivation inline — it lives in `build_dataset_from_sources`. **If Task 9 has already been implemented, move the freshness block from `materialize_graph` into `build_dataset_from_sources` as part of this step.** The integration tests from Task 9 still pass because the same triples land in the same dataset.

Run the Task 9 integration tests to confirm the refactor is behavior-preserving:

```bash
uv run --frozen pytest science/tests/test_graph_freshness_integration.py science/tests/test_graph_materialize.py -q
```

Expected: PASS.

- [ ] **Step 3b: Add the `propagate_freshness_in_memory` wrapper**

Append to `science/src/science_tool/graph/freshness.py`:

```python
def propagate_freshness_in_memory(project_root: Path) -> list[dict]:
    """Compute freshness without writing the materialized graph.

    Loads project sources, builds the same in-memory dataset
    `materialize_graph` would build (via `build_dataset_from_sources`),
    extracts the freshness rows, returns them. Filesystem-pure on the
    output side: never writes the trig and never mutates entity files.

    Same semantics as `graph build` for which entities surface as
    needs-review / stale, by construction (shared helper).
    """
    from science_tool.graph.materialize import build_dataset_from_sources
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root.resolve())
    dataset = build_dataset_from_sources(sources)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    rows: list[dict] = []
    for s, _, o in knowledge.triples((None, SCI_NS.freshnessState, None)):
        state = str(o)
        if state == "fresh":
            continue
        uri = str(s)
        prefix = str(PROJECT_NS)
        if uri.startswith(prefix):
            tail = uri[len(prefix):]
            kind, _, slug = tail.partition("/")
            rows.append({"id": f"{kind}:{slug}", "kind": kind, "state": state})
    rows.sort(key=lambda r: (r["state"], r["kind"], r["id"]))
    return rows
```

- [ ] **Step 4: Wire CLI command**

In `science/src/science_tool/cli.py`, after the existing `graph_build` command (around line 690), add:

```python
@graph.command("propagate-freshness")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def graph_propagate_freshness(project_root: Path, output_format: str) -> None:
    """Read-only freshness sweep — recomputes in memory and reports flagged entities."""
    from science_tool.graph.freshness import propagate_freshness_in_memory

    _project_root = Path.cwd() if str(project_root) == "." else project_root
    rows = propagate_freshness_in_memory(_project_root)
    if output_format == "json":
        click.echo(json.dumps(rows, indent=2))
        return
    if not rows:
        click.echo("All epistemic entities are fresh.")
        return
    click.echo(f"{'state':<14}{'kind':<20}{'id':<40}")
    click.echo("-" * 74)
    for row in rows:
        click.echo(f"{row['state']:<14}{row['kind']:<20}{row['id']:<40}")
```

- [ ] **Step 5: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_graph_propagate_freshness_cli.py -q
```

Expected: PASS, 3/3.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/freshness.py science/src/science_tool/cli.py science/tests/test_graph_propagate_freshness_cli.py
git commit -m "feat(cli): add graph propagate-freshness read-only sweep"
```

---

## Task 13: `validate.sh` check for `review_state` frontmatter shape

**Files:**
- Modify: `scripts/validate.sh`
- Modify: `meta/validate.sh` (lockstep)
- Modify: `science/tests/test_validate_script.py`

A warning when `review_state.review_horizon_days` is non-positive — catches malformed frontmatter blocks at validate time rather than waiting until the next graph build picks up the Pydantic error. Consistent with surrounding validator conventions (warn, not error).

**Note on hand-authored `bears_on` validation.** The original draft of this task also covered "any hand-authored `bears_on` triple must target an epistemic kind." That check moved to Task 9 (the graph-build pipeline) because hand-authored relations live in YAML relations files, not in entity frontmatter — so the right enforcement point is `_add_authored_relation` at materialize time, not the per-file `validate.sh` sweep. See Task 9 Step 7 below.

- [ ] **Step 1: Write failing tests**

In `science/tests/test_validate_script.py`, locate where existing validator tests are added (find `def test_validate_warns_on_` patterns) and append:

```python
def test_validate_warns_on_review_state_with_invalid_horizon(tmp_path: Path):
    project = _make_project(tmp_path)  # use the existing helper
    h = project / "doc" / "hypotheses" / "h-bad.md"
    h.parent.mkdir(parents=True, exist_ok=True)
    h.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h-bad"
            kind: "hypothesis"
            title: "Bad horizon"
            created: "2026-01-01"
            review_state:
              last_reviewed: "2026-01-01"
              review_horizon_days: -5
            ---
            """
        ).lstrip()
    )
    result = _run_validate(project)  # use the existing runner helper
    assert "review_horizon_days must be positive" in result.stdout or "review_horizon_days" in result.stdout
```

(If `_make_project` and `_run_validate` aren't the existing helper names, look for the equivalents in the file — typed-blockers added new validator tests via the same pattern.)

- [ ] **Step 2: Run, verify failure**

```bash
uv run --frozen pytest science/tests/test_validate_script.py -q -k review_state
```

Expected: FAIL — validator doesn't check this yet.

- [ ] **Step 3: Implement in `scripts/validate.sh`**

In `scripts/validate.sh`, find the section that validates entity frontmatter (a sweep over `doc/**/*.md` with `yq`/`grep` extraction). Add a block, ideally near the existing `available_after` check from typed-entity-blockers:

```bash
# Section: review_state shape validation
for f in $(find "$DOC_DIR" -name "*.md" -type f 2>/dev/null); do
    horizon=$(awk '/^review_state:/,/^[^ ]/{ if ($1=="review_horizon_days:") print $2 }' "$f" | head -1 | tr -d '"')
    if [ -n "$horizon" ] && [ "$horizon" -le 0 ] 2>/dev/null; then
        warn "$f: review_state.review_horizon_days must be positive (got $horizon)"
    fi
done
```

(Wire it through the project's existing `warn` helper / counter increment per surrounding convention.)

- [ ] **Step 4: Mirror to `meta/validate.sh`**

Apply the identical block in `meta/validate.sh`. The two scripts have different sha256 but are kept in lockstep until managed-artifact-versioning unifies them.

- [ ] **Step 5: Run, verify pass**

```bash
uv run --frozen pytest science/tests/test_validate_script.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/validate.sh meta/validate.sh science/tests/test_validate_script.py
git commit -m "feat(validate): warn on invalid review_state.review_horizon_days"
```

---

## Task 14: Skill prose + docs updates

**Files:**
- Modify: `commands/science/status.md`
- Modify: `commands/science/next-steps.md`
- Modify: `docs/claim-and-evidence-model.md`
- Modify: `docs/proposition-and-evidence-model.md`

Phase 1 finishes by surfacing the new state to humans/agents through the skills they actually use.

- [ ] **Step 1: Update `science:status` skill prose**

In `commands/science/status.md` (or wherever the skill body lives — find via `grep -rn "## science:status\|^name: status" ~/d/science/skills/`), add a section near "Recent activity" that explicitly mentions reading `entity needs-review` for the orientation:

> Run `science entity needs-review` to surface epistemic entities whose evidence base has changed since their last reviewed-as-of date. Include up to 5 of the highest-impact ones (most upstream sources flagged) in the orientation.

(Match the file's existing structure / tone — consult adjacent sections.)

- [ ] **Step 2: Update `science:next-steps` skill prose**

In `commands/science/next-steps.md`, add a paragraph explaining that needs-review entities should be considered as candidate next steps when the user is otherwise blocked:

> When the backlog is unclear, list `science entity needs-review` output and propose one as a candidate next step. Frame it as "you reviewed this on date X; since then upstream Y changed — worth a fresh look?" rather than as a verdict.

- [ ] **Step 3: Update `docs/claim-and-evidence-model.md`**

Add a section after the existing claim/evidence model description:

```markdown
## Epistemic dependency: `bears_on` and freshness

Beyond the static claim-evidence shape (supports/disputes), Science maintains a forward-in-time dependency view: when upstream evidence changes, which downstream beliefs need attention. This is captured by the `bears_on` relation, auto-derived from typed edges (tests/grounded_by/contains/etc.) and `prov:wasDerivedFrom` provenance. Each epistemic entity carries a `review_state.last_reviewed` date in its frontmatter; `graph build` compares that against upstream `updated` dates and emits an `EpistemicFreshness` flag (`fresh` / `needs-review` / `stale`) into the materialized graph.

Freshness is a flag, not a gate. A `needs-review` entity remains readable, citable, and usable in synthesis — the flag only affects what `science:status` and `science:next-steps` surface for human attention.

See `docs/plans/2026-05-03-epistemic-dependency-graph-design.md` for the full design.
```

- [ ] **Step 4: Update `docs/proposition-and-evidence-model.md`**

Apply the analogous section, framed in the proposition model's vocabulary.

- [ ] **Step 5: Verify all docs render and contain the new content**

```bash
grep -l "bears_on" docs/claim-and-evidence-model.md docs/proposition-and-evidence-model.md
grep -l "needs-review" commands/science/status.md commands/science/next-steps.md
```

Expected: each grep finds the file.

- [ ] **Step 6: Commit**

```bash
git add commands/science/status.md commands/science/next-steps.md docs/claim-and-evidence-model.md docs/proposition-and-evidence-model.md
git commit -m "docs: surface bears_on / freshness in skills + claim/evidence model docs"
```

---

## Final verification

After all 14 tasks:

- [ ] **Run the full science-model test suite**

```bash
uv run --frozen pytest science-model/tests/ -q
```

Expected: PASS.

- [ ] **Run the full science test suite**

```bash
uv run --frozen pytest science/tests/ -q
```

Expected: PASS. (Watch for incidental fallout from the entity_registry changes — anything that called `register_extension_kind` without `entity_class` should still work via the default; any test mocking the registry may need to update.)

- [ ] **Run validate.sh on the meta project**

```bash
cd meta && bash validate.sh
```

Expected: only the pre-existing duplicate-task error (`t001` vs `t001b`) — no regression.

- [ ] **Run a graph build end-to-end on a downstream project (optional sanity check)**

Pick `~/d/cancer/cancer-types/myeloma` or another downstream project that has a built graph today. Run `science graph build` and confirm:

- The new `sci:bearsOn`, `sci:freshnessState`, `sci:upstreamChangeAt`, `sci:triggeredBy` triples appear in `knowledge/graph.trig`.
- No entity files are mutated by the build (`git status` shows only `knowledge/graph.trig` changed).
- `science entity needs-review` lists a sensible set of entities (ones whose upstream evidence has changed since they were created/last-reviewed).

- [ ] **Update task status**

Mark `[t010]` as `done` in `meta/tasks/active.md`. `[t011]` (phase 2) and `[t012]` (pre-reg recast) remain `proposed`/`deferred`.

- [ ] **Commit the task status update**

```bash
git add meta/tasks/active.md
git commit -m "chore(meta): mark t010 (epistemic dep graph phase 1) done"
```

---

## Self-Review of the Plan

1. **Spec coverage.** Every section of the design doc maps to a task:
   - Part 1 entity taxonomy → Task 1 (enum) + Task 4 (registry).
   - Part 2 `bears_on` derivation → Task 3 (relation kind) + Tasks 5/6/7 (engine).
   - Part 3 freshness → Task 2 (frontmatter field) + Task 8 (derivation) + Task 9 (wiring).
   - Part 4 pre-reg recast → tracked as separate task `[t012]`, deliberately out of scope here.
   - Validation, CLI, and graph-build integration → Tasks 10/11/12/13.
   - Display surface → Task 14.
   - File touch list — every entry has a task that creates/modifies it.

2. **Placeholder scan.** No "TBD"/"implement later" — every step has either real code or an exact command. Task 13's validate.sh changes reference an existing helper (`warn`) found in surrounding code; Task 14 references skill body locations to be located via grep at execution time (acceptable since file paths vary by skill source layout).

3. **Type consistency.**
   - `EpistemicReviewState` field name and shape are consistent across Tasks 1, 2, 8, 9, 10, 12.
   - `EntityClass` enum is consistent across Tasks 1, 4, 5, 6, 7, 8, 9, 12.
   - `derive_bears_on_from_typed_edges(dataset, *, kind_class=...)` signature consistent in Tasks 5/6 and called identically in Tasks 9 and 12.
   - `kind_class` dict keying on URI string (not the URIRef object) consistent everywhere.
   - `entity_meta` dict shape consistent across Tasks 8, 9, 12.

4. **Risks flagged inline.**
   - Task 4 changes a public method signature on `EntityRegistry` (`register_core_kind` now requires `entity_class`). All call sites are within `with_core_types()` and downstream tests; mitigated by Step 5/6 running existing test suites. Profile/extension/catalog `register_*` methods get sensible defaults to avoid breaking external callers.
   - Task 9 modifies the materialize pipeline; integration tests in Task 9 + the final-verification end-to-end check guard against regressions in existing graph build behavior.
   - Task 13's bash awk is fragile; the test in Step 1 covers the negative-horizon case; richer YAML validation belongs to a managed-artifact-versioning follow-up.

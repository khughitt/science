# Curation Scope Certification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science entity review plan:NNNN` succeed by giving `EntityKind` its own declared `curation_scope` axis, resolved at exactly one profile-aware boundary, without touching `bears_on` propagation.

**Architecture:** `curation_scope` (`epistemic | correspondence | none`, default `none`) is authored per kind on `EntityKind` in `science-model` — derived from neither `EntityClass` nor the deleted closed list. `science-model` validates only the *shape* of `ReviewState`. **Scope** — may a kind carry `review_state` at all? — is decided in exactly one place: `EntityRegistry.curation_scope_for_kind`, consumed at the `science_tool` boundary (`review_entity`), which is the only layer that can see a project's local and shared descriptors. The hardcoded `Entity._validate_review_state_kind` closed list is deleted, its knowledge migrated into the per-kind declarations.

**Tech Stack:** Python 3.12+, Pydantic v2, Click, pytest. Two nested packages: `science-model` (`science/model/`) and `science` (`science/`).

## Global Constraints

- **No compatibility shim, alias, or `Unified` prefix.** `EpistemicReviewState` → `ReviewState` is a clean rename; there is no back-compat alias (project convention; design §5).
- **No AI-attribution trailers** on any commit (no `Co-Authored-By`, no "Generated with Claude Code").
- **`curation_scope` is authored per kind, derived from nothing.** Never compute it from `EntityClass` or from the closed list — that is the §4.1 regression this spec exists to prevent.
- **`bears_on` / freshness is not touched.** `sci:freshnessState` and `bears_on` targets stay gated on `EntityClass.EPISTEMIC` in `graph/freshness.py`. A `correspondence` kind may remain a `bears_on` **source** (design §5.1).
- **Tests run from the package directory.** Model: `cd science/model && uv run --frozen pytest`. Tool: `cd science && uv run --frozen pytest`. Lint per package: `uv run ruff check`. Types once from repo root config: `cd science && uv run pyright`.
- **Ratified `correspondence` roster (design §5 item 5, 2026-07-17), nine kinds:** `claim-registry`, `curation-sweep`, `method`, `plan`, `pre-registration`, `research-package`, `spec`, `transformation`, `workflow`. `talk` and `search` are `none` (unprobeable). Everything else non-epistemic is `none`.
- **Authoritative core-kind partition (from `CORE_PROFILE`, verified 2026-07-17):** 21 `EPISTEMIC`, 21 `OPERATIONAL`, 8 `REFERENCE` = 50 kinds. The full scope map is fixed in Task 4 Step 1.
- **Paths in docs/code use `~/d/`**, never `/home/keith/d/` or `/mnt/ssd/Dropbox/`.

---

## File Structure

**Created:**
- None. All changes modify existing files.

**Modified — `science-model`:**
- `science/model/src/science_model/identity.py` — add `CurationScope` StrEnum beside `EntityClass`.
- `science/model/src/science_model/profiles/schema.py` — add `curation_scope: CurationScope | None` field to `EntityKind`.
- `science/model/src/science_model/profiles/core.py` — declare `curation_scope` on the 21 epistemic + 9 correspondence core kinds.
- `science/model/src/science_model/entities.py` — rename `EpistemicReviewState` → `ReviewState`; **delete** `_validate_review_state_kind`; fix a stale `extra="ignore"` comment.
- `science/model/src/science_model/frontmatter.py` — rename references.
- `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json` — update the `$comment` class name.
- `science/model/tests/test_review_state_model.py` — rename references; rewrite the closed-list rejection tests to assert shape-only acceptance.

**Modified — `science` (tool):**
- `science/src/science_tool/graph/entity_registry.py` — store declared scope; add `curation_scope_for_kind`; thread the kwarg through `register_*` and `with_core_types`.
- `science/src/science_tool/graph/sources.py` — thread `curation_scope` through profile/local registration; extract `_resolve_active_profiles`, `build_entity_registry`, `registry_for_project`.
- `science/src/science_tool/entities.py` — `_load_markdown_entities` / `find_entity` discover local-extension kinds via `entity_policies(project_root)` (Task 6-A).
- `science/src/science_tool/entity_review.py` — replace the `EntityClass` gate with the `curation_scope_for_kind` boundary.
- `science/src/science_tool/entities_cli.py` — update the `entity review` help (no longer "epistemic entity" only).
- `science/tests/test_entity_registry.py` — scope-resolution unit tests + exhaustive roster.
- `science/tests/test_entity_review_cli.py` (and `test_entity_review*`) — boundary behaviour, theater guard.
- `science/tests/test_curation_scope_guard.py` (**create**) — the single-decider import-closure guard.
- `science/tests/test_freshness_derivation.py` — directional isolation assertion.
- `science/scripts/verify_downstream_scope.sh` (**create**) — Task 10 downstream check.

---

### Task 1: `CurationScope` enum and the `EntityKind.curation_scope` field (model, shape only)

**Files:**
- Modify: `science/model/src/science_model/identity.py:17` (after `class EntityClass`)
- Modify: `science/model/src/science_model/profiles/schema.py:30` (in `class EntityKind`)
- Test: `science/model/tests/test_curation_scope_field.py` (create)

**Interfaces:**
- Produces: `CurationScope(StrEnum)` with members `EPISTEMIC = "epistemic"`, `CORRESPONDENCE = "correspondence"`, `NONE = "none"`, importable from `science_model.identity`.
- Produces: `EntityKind.curation_scope: CurationScope | None = None`.

- [ ] **Step 1: Write the failing test**

Create `science/model/tests/test_curation_scope_field.py`:

```python
"""CurationScope enum and the EntityKind.curation_scope field (shape only)."""

import pytest

from science_model.identity import CurationScope
from science_model.profiles.schema import EntityKind


def test_curation_scope_members():
    assert CurationScope.EPISTEMIC.value == "epistemic"
    assert CurationScope.CORRESPONDENCE.value == "correspondence"
    assert CurationScope.NONE.value == "none"


def test_entity_kind_curation_scope_defaults_none_field():
    ek = EntityKind(name="x", canonical_prefix="x", layer="layer/local", description="")
    assert ek.curation_scope is None  # undeclared, NOT resolved — resolution is the registry's job


def test_entity_kind_accepts_declared_scope():
    ek = EntityKind(
        name="plan",
        canonical_prefix="plan",
        layer="layer/core",
        description="",
        curation_scope=CurationScope.CORRESPONDENCE,
    )
    assert ek.curation_scope is CurationScope.CORRESPONDENCE


def test_entity_kind_coerces_string_scope():
    ek = EntityKind(
        name="hypothesis", canonical_prefix="hypothesis", layer="layer/core",
        description="", curation_scope="epistemic",
    )
    assert ek.curation_scope is CurationScope.EPISTEMIC


def test_entity_kind_rejects_unknown_scope():
    with pytest.raises(ValueError):
        EntityKind(name="x", canonical_prefix="x", layer="layer/local", description="", curation_scope="sometimes")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_curation_scope_field.py -v`
Expected: FAIL with `ImportError: cannot import name 'CurationScope'`.

- [ ] **Step 3: Add the enum**

In `science/model/src/science_model/identity.py`, immediately after the `EntityClass` StrEnum, add:

```python
class CurationScope(StrEnum):
    """Whether — and how — a kind's records may carry review state (design §5).

    An axis of its own, authored per kind and derived from NEITHER `EntityClass`
    (calibrated for `bears_on` propagation) NOR the deleted closed list. `epistemic`
    asks "given new evidence, is this still my belief?"; `correspondence` asks "does
    this record still correspond to reality — did it ship?"; `none` means there is
    nothing to review.
    """

    EPISTEMIC = "epistemic"
    CORRESPONDENCE = "correspondence"
    NONE = "none"
```

(If `StrEnum` is not already imported in `identity.py`, it is — `EntityClass` uses it. Confirm the existing `from enum import StrEnum`.)

- [ ] **Step 4: Add the field**

In `science/model/src/science_model/profiles/schema.py`, add the import and field. At the top, extend the identity import:

```python
from science_model.identity import CurationScope, EntityClass
```

In `class EntityKind`, add after the `template_ready` line (schema.py:32):

```python
    curation_scope: CurationScope | None = None  # design §5: authored per kind; None = undeclared (registry applies the default)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_curation_scope_field.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
cd science/model && uv run ruff check src/science_model/identity.py src/science_model/profiles/schema.py
git add model/src/science_model/identity.py model/src/science_model/profiles/schema.py model/tests/test_curation_scope_field.py
git commit -m "feat(model): add CurationScope axis and EntityKind.curation_scope field"
```

---

### Task 2: Rename `EpistemicReviewState` → `ReviewState` (clean, no shim)

**Files:**
- Modify: `science/model/src/science_model/entities.py:138,154,377`
- Modify: `science/model/src/science_model/frontmatter.py:16,425,426,430`
- Modify: `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json:170`
- Modify: `science/model/tests/test_review_state_model.py` (all references)

**Interfaces:**
- Produces: `ReviewState` (was `EpistemicReviewState`), importable from `science_model.entities`. No alias.

- [ ] **Step 1: Confirm the rename surface**

Run: `cd science && grep -rn "EpistemicReviewState" model/src model/tests`
Expected: references in `entities.py` (3), `frontmatter.py` (3), `test_review_state_model.py` (several). The `mixin-hypothesis-1.0.json` `$comment` (1) mentions it in prose.

- [ ] **Step 2: Rename the class and its uses in `entities.py`**

In `science/model/src/science_model/entities.py`:
- Line 138: `class EpistemicReviewState(BaseModel):` → `class ReviewState(BaseModel):`
- Line 154: `def _validate_horizon(self) -> "EpistemicReviewState":` → `def _validate_horizon(self) -> "ReviewState":`
- Line 377: `review_state: EpistemicReviewState | None = None` → `review_state: ReviewState | None = None`

Update the class docstring's first line to drop "for epistemic entities" (the type now serves correspondence kinds too):

```python
class ReviewState(BaseModel):
    """Per-entity review-as-of state.

    `last_reviewed` is the date the user (or agent) last considered this entity.
    `last_review_note` is an optional human-readable note about that review.
    `review_horizon_days` is an optional per-entity threshold for the `stale`
    state — when set, entities whose `last_reviewed` is older than `now - horizon`
    flip to `stale` even without any upstream change.
    """
```

- [ ] **Step 3: Fix the stale `extra=` comment while in the file**

In `science/model/src/science_model/entities.py` around line 884, the comment reads `` `Entity` is `extra="ignore"` `` — this is stale (D3.3 made `Entity` `extra="allow"`; see entities.py:302-324 and 324 `model_config = ConfigDict(extra="allow")`). Correct it:

```python
    # The four TERMINAL fields. `Entity` is `extra="allow"`, so an undeclared field is PRESERVED
    # (D3.3) but never projected into a typed surface until DECLARED here -- and any consumer reading
```

(Keep the rest of the comment unchanged; only `extra="ignore"` → `extra="allow"` and the follow-on clause so the sentence stays true.)

- [ ] **Step 4: Rename references in `frontmatter.py` and the schema `$comment`**

In `science/model/src/science_model/frontmatter.py`: replace `EpistemicReviewState` with `ReviewState` at lines 16 (import), 425 (return annotation), 426 (docstring), 430 (constructor call).

In `science/model/src/science_model/schemas/mixin-hypothesis-1.0.json:170`, in the `$comment`, replace `EpistemicReviewState (entities.py:138)` with `ReviewState (entities.py:138)`.

- [ ] **Step 5: Rename references in the model test file**

In `science/model/tests/test_review_state_model.py`, replace every `EpistemicReviewState` with `ReviewState` (import at line 11, and constructor calls at 22, 29, 41, 46, 130, 142). Leave the closed-list rejection tests (128-144) otherwise unchanged for now — Task 7 rewrites their bodies.

- [ ] **Step 6: Verify no reference remains, then run the suites**

```bash
cd science && grep -rn "EpistemicReviewState" model/ src/ tests/ ; echo "exit=$?"
```
Expected: no matches (grep exit 1).

```bash
cd science/model && uv run --frozen pytest tests/test_review_state_model.py -q
cd science && uv run --frozen pytest tests/ -q -k "review or freshness or hypothesis" 
```
Expected: PASS (the rename is behaviour-neutral).

- [ ] **Step 7: Commit**

```bash
cd science/model && uv run ruff check src/science_model
git add model/src/science_model/entities.py model/src/science_model/frontmatter.py model/src/science_model/schemas/mixin-hypothesis-1.0.json model/tests/test_review_state_model.py
git commit -m "refactor(model): rename EpistemicReviewState -> ReviewState (no shim); fix stale extra= comment"
```

---

### Task 3: Declare `curation_scope` on the 30 non-`none` core kinds

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (30 `EntityKind` blocks)
- Test: `science/model/tests/test_curation_scope_field.py` (extend)

**Interfaces:**
- Consumes: `CurationScope` (Task 1).
- Produces: each of the 21 epistemic core kinds carries `curation_scope=CurationScope.EPISTEMIC`; each of the 9 correspondence core kinds carries `curation_scope=CurationScope.CORRESPONDENCE`. The 20 `none` kinds are left undeclared (default `none`, applied by the registry in Task 4).

- [ ] **Step 1: Write the failing assertion over `CORE_PROFILE`**

Add to `science/model/tests/test_curation_scope_field.py`:

```python
from science_model.profiles.core import CORE_PROFILE

_EPISTEMIC = {
    "assumption", "chain-audit", "discussion", "evidence-line", "falsification",
    "finding", "hypothesis", "inquiry", "interpretation", "mechanism", "observation",
    "patch-definition", "proposition", "question", "report", "research-question",
    "story", "structural-chain", "synthesis", "theme", "validation-report",
}
_CORRESPONDENCE = {
    "claim-registry", "curation-sweep", "method", "plan", "pre-registration",
    "research-package", "spec", "transformation", "workflow",
}


def test_core_profile_declares_epistemic_and_correspondence_only():
    declared = {ek.name: ek.curation_scope for ek in CORE_PROFILE.entity_kinds
                if ek.curation_scope is not None}
    from science_model.identity import CurationScope
    assert {k for k, v in declared.items() if v is CurationScope.EPISTEMIC} == _EPISTEMIC
    assert {k for k, v in declared.items() if v is CurationScope.CORRESPONDENCE} == _CORRESPONDENCE
    # `none` kinds are left undeclared on purpose; the registry applies the default.
    assert all(v is not CurationScope.NONE for v in declared.values())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_curation_scope_field.py::test_core_profile_declares_epistemic_and_correspondence_only -v`
Expected: FAIL — no kind declares `curation_scope` yet (both sets empty).

- [ ] **Step 3: Add `curation_scope=CurationScope.EPISTEMIC` to the 21 epistemic kinds**

In `science/model/src/science_model/profiles/core.py`, add the line `curation_scope=CurationScope.EPISTEMIC,` to the `EntityKind(...)` block of each of these kinds (add it next to `entity_class=EntityClass.EPISTEMIC,`):

`assumption`, `chain-audit`, `discussion`, `evidence-line`, `falsification`, `finding`, `hypothesis`, `inquiry`, `interpretation`, `mechanism`, `observation`, `patch-definition`, `proposition`, `question`, `report`, `research-question`, `story`, `structural-chain`, `synthesis`, `theme`, `validation-report`.

Worked example — the `hypothesis` block becomes (only the added line shown in context):

```python
        EntityKind(
            name="hypothesis",
            canonical_prefix="hypothesis",
            layer="layer/core",
            description="...",
            entity_class=EntityClass.EPISTEMIC,
            curation_scope=CurationScope.EPISTEMIC,
            category=KindCategory.AUTHORED_CORE,
            # ...unchanged...
        ),
```

Ensure `CurationScope` is imported at the top of `core.py`: extend the existing identity import to `from science_model.identity import CurationScope, EntityClass` (match whatever the current import line is).

- [ ] **Step 4: Add `curation_scope=CurationScope.CORRESPONDENCE` to the 9 correspondence kinds**

In the same file, add `curation_scope=CurationScope.CORRESPONDENCE,` to each of: `claim-registry`, `curation-sweep`, `method`, `plan`, `pre-registration`, `research-package`, `spec`, `transformation`, `workflow`.

Worked example — the `plan` block (core.py:429):

```python
        EntityKind(
            name="plan",
            canonical_prefix="plan",
            layer="layer/core",
            description="An authored implementation or analysis plan.",
            entity_class=EntityClass.OPERATIONAL,
            curation_scope=CurationScope.CORRESPONDENCE,
            category=KindCategory.AUTHORED_CORE,
            home="entities/plans",
            # ...unchanged...
        ),
```

Do **not** add `curation_scope` to any other kind — the remaining 20 (`article`, `book`, `code-file`, `concept`, `construct`, `data-package`, `dataset`, `decision`, `experiment`, `outcome`, `paper`, `prose-source`, `search`, `talk`, `task`, `topic`, `unknown`, `variable`, `workflow-run`, `workflow-step`) stay undeclared.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_curation_scope_field.py -v`
Expected: PASS. Also run the full model suite to confirm nothing else parsed `CORE_PROFILE` strictly:
`cd science/model && uv run --frozen pytest -q`

- [ ] **Step 6: Commit**

```bash
cd science/model && uv run ruff check src/science_model/profiles/core.py
git add model/src/science_model/profiles/core.py model/tests/test_curation_scope_field.py
git commit -m "feat(model): declare curation_scope on epistemic + correspondence core kinds"
```

---

### Task 4: Registry resolves scope — `curation_scope_for_kind` (the single decider)

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py:86-172,191` (storage + register_* + with_core_types + new method)
- Test: `science/tests/test_entity_registry.py`

**Interfaces:**
- Consumes: `CurationScope` (`science_model.identity`), `CORE_PROFILE`.
- Produces: `EntityRegistry.curation_scope_for_kind(self, kind: str) -> CurationScope` — the ONLY code that applies the default. All `register_*` methods gain `curation_scope: CurationScope | None = None`. `with_core_types` passes `ek.curation_scope`.

- [ ] **Step 1: Write the failing tests (resolution rules + exhaustive roster)**

Add to `science/tests/test_entity_registry.py`:

```python
from science_model.identity import CurationScope, EntityClass
from science_model.entities import ProjectEntity
from science_tool.graph.entity_registry import EntityRegistry

_EPISTEMIC = {
    "assumption", "chain-audit", "discussion", "evidence-line", "falsification",
    "finding", "hypothesis", "inquiry", "interpretation", "mechanism", "observation",
    "patch-definition", "proposition", "question", "report", "research-question",
    "story", "structural-chain", "synthesis", "theme", "validation-report",
}
_CORRESPONDENCE = {
    "claim-registry", "curation-sweep", "method", "plan", "pre-registration",
    "research-package", "spec", "transformation", "workflow",
}
# Every core kind not in the two sets above resolves to `none`.
_NONE = {
    "article", "book", "code-file", "concept", "construct", "data-package", "dataset",
    "decision", "experiment", "outcome", "paper", "prose-source", "search", "talk",
    "task", "topic", "unknown", "variable", "workflow-run", "workflow-step",
}


def test_core_roster_resolves_exhaustively():
    """Design acceptance test 8: every core kind maps to the ratified §5 scope."""
    r = EntityRegistry.with_core_types()
    expected = (
        {k: CurationScope.EPISTEMIC for k in _EPISTEMIC}
        | {k: CurationScope.CORRESPONDENCE for k in _CORRESPONDENCE}
        | {k: CurationScope.NONE for k in _NONE}
    )
    assert set(expected) == r.core_kinds(), "roster and registered core kinds disagree"
    for kind, scope in expected.items():
        assert r.curation_scope_for_kind(kind) is scope, kind


def test_closed_list_kinds_all_resolve_none():
    """Design acceptance test 2: the deleted closed list's knowledge is preserved."""
    r = EntityRegistry.with_core_types()
    for kind in ("task", "dataset", "workflow-run", "data-package", "paper",
                 "prose-source", "book", "experiment", "code-file"):
        assert r.curation_scope_for_kind(kind) is CurationScope.NONE, kind


def test_core_kind_undeclared_defaults_none():
    """Design acceptance test 3: a core kind with no declaration → none (refused later)."""
    r = EntityRegistry()
    r.register_core_kind("gadget", ProjectEntity, entity_class=EntityClass.OPERATIONAL)
    assert r.curation_scope_for_kind("gadget") is CurationScope.NONE


def test_extension_kind_undeclared_defaults_correspondence():
    """Design acceptance test 9: an undeclared EXTENSION kind → correspondence."""
    r = EntityRegistry()
    r.register_extension_kind("design", ProjectEntity, entity_class=EntityClass.OPERATIONAL)
    assert r.curation_scope_for_kind("design") is CurationScope.CORRESPONDENCE


def test_extension_kind_declared_scope_wins():
    r = EntityRegistry()
    r.register_extension_kind(
        "design", ProjectEntity, entity_class=EntityClass.OPERATIONAL,
        curation_scope=CurationScope.NONE,
    )
    assert r.curation_scope_for_kind("design") is CurationScope.NONE


def test_unregistered_kind_defaults_correspondence():
    """Unknown kinds behave like extension kinds — reviewable by default (§6.2)."""
    r = EntityRegistry.with_core_types()
    assert r.curation_scope_for_kind("totally-unknown-kind") is CurationScope.CORRESPONDENCE
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_entity_registry.py -k curation -v`
Expected: FAIL — `EntityRegistry` has no `curation_scope_for_kind`.

- [ ] **Step 3: Add storage + thread the kwarg + the resolver**

In `science/src/science_tool/graph/entity_registry.py`:

Extend the import at the top to include `CurationScope`:
```python
from science_model.identity import CurationScope, EntityClass
```

In `__init__` (line 86-91) add the declared-scope map:
```python
        self._curation_scope_declared: dict[str, CurationScope | None] = {}
```

Add `curation_scope: CurationScope | None = None` to each of `register_core_kind`, `register_profile_kind`, `register_catalog_kind`, `register_extension_kind`, and store it in each after the existing `self._kind_class[kind] = ...` line:
```python
        self._curation_scope_declared[kind] = curation_scope
```
For `register_catalog_kind`, place the store on both the early-`return` core-shadow path? No — keep it beside the existing `self._kind_class[kind]` assignment only (the shadow paths `return` before registering, so they store nothing, which is correct).

In `with_core_types` (line 104), pass the declared scope:
```python
            r.register_core_kind(
                ek.name,
                CORE_KIND_MODELS.get(ek.name, ProjectEntity),
                entity_class=ek.entity_class,
                curation_scope=ek.curation_scope,
            )
```

Add the resolver near `kind_class` (after line 197):
```python
    def curation_scope_for_kind(self, kind: str) -> CurationScope:
        """Resolve a kind's curation scope — the SINGLE decider (design §6.1).

        Declared value wins. Otherwise the default is polarity-split by registration
        bucket (design §6.2): core/profile/catalog kinds default to `none` (a newly
        registered core kind is out of scope until declared); extension kinds and
        wholly-unregistered kinds default to `correspondence`, preserving today's
        reviewable-by-default behaviour for exactly the population that has it
        (project-local extension kinds such as multiple-myeloma's `design`).
        """
        declared = self._curation_scope_declared.get(kind)
        if declared is not None:
            return declared
        if kind in self._core or kind in self._profile or kind in self._catalog:
            return CurationScope.NONE
        return CurationScope.CORRESPONDENCE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_entity_registry.py -k curation -v`
Expected: PASS (6 tests, including the exhaustive roster).

- [ ] **Step 5: Run the registry + kind-reconciliation suites (guard against knock-on)**

Run: `cd science && uv run --frozen pytest tests/test_entity_registry.py tests/test_kind_reconciliation_registry.py tests/test_kind_map_equivalence.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd science && uv run ruff check src/science_tool/graph/entity_registry.py
git add src/science_tool/graph/entity_registry.py tests/test_entity_registry.py
git commit -m "feat(registry): curation_scope_for_kind — the single scope decider"
```

---

### Task 5: Profile-aware registry builders (`build_entity_registry`, `registry_for_project`)

**Files:**
- Modify: `science/src/science_tool/graph/sources.py:256-329` (extract + thread `curation_scope`)
- Test: `science/tests/test_sources_registry.py` (create)

**Interfaces:**
- Consumes: the profile loaders already used in `sources.py` (`load_shared_profile`, `load_profile_manifest`, `local_profile_sources_dir`, `LOCAL_PROFILE`, `load_catalogs_for_names`, `_read_project_config`, `KnowledgeProfiles`), and `EntityRegistry` (Task 4).
- Produces:
  - `_resolve_active_profiles(project_root: Path) -> ActiveProfiles` — a frozen dataclass holding `profile_manifests: list[ProfileManifest]`, `local_profile_manifest: ProfileManifest | None`, `ontology_catalogs: list`, `local_profile: str`, `local_manifest_rel: str`.
  - `build_entity_registry(resolved: ActiveProfiles) -> tuple[EntityRegistry, list[SkippedEntity]]` — assembles the registry, threading `curation_scope` from every manifest kind, returns it plus `graduated_kind_skips`.
  - `registry_for_project(project_root: Path) -> EntityRegistry` — `_resolve_active_profiles` then `build_entity_registry`, returning just the registry. This is what `review_entity` calls.

- [ ] **Step 1: Write the failing parity + threading tests**

Create `science/tests/test_sources_registry.py`:

```python
"""registry_for_project parity with load_project_sources, and local-manifest scope threading."""

from science_model.identity import CurationScope
from science_tool.graph.sources import registry_for_project, load_project_sources


def test_registry_for_project_matches_load_project_sources(tmp_project):
    """The lightweight builder yields the same kind→scope map as the full loader."""
    full = load_project_sources(tmp_project).registry
    light = registry_for_project(tmp_project)
    kinds = sorted(full.all_kind_classes())
    assert kinds == sorted(light.all_kind_classes())
    for k in kinds:
        assert full.curation_scope_for_kind(k) is light.curation_scope_for_kind(k), k


def test_local_extension_kind_defaults_correspondence(tmp_project_with_design_kind):
    """A project-local extension kind with no declared scope resolves to correspondence (§6.2)."""
    r = registry_for_project(tmp_project_with_design_kind)
    assert r.curation_scope_for_kind("design") is CurationScope.CORRESPONDENCE


def test_local_manifest_declared_scope_wins(tmp_project_with_scoped_kind):
    """A local manifest that declares curation_scope: none on its kind is authoritative (§6.2 item 1)."""
    r = registry_for_project(tmp_project_with_scoped_kind)
    assert r.curation_scope_for_kind("logbook") is CurationScope.NONE
```

Add fixtures to `science/tests/conftest.py` (or the nearest fixtures module). `tmp_project` is a minimal project with a valid `science.yaml` and `knowledge/sources/<local>/manifest.yaml` declaring no extra kinds. `tmp_project_with_design_kind` adds an extension kind `design` (no `curation_scope`). `tmp_project_with_scoped_kind` adds `logbook` with `curation_scope: none`. Mirror an existing project fixture in the tests directory (search `tests/` for a helper that already writes `science.yaml` + a local `manifest.yaml`, e.g. in `test_sources*.py` or `conftest.py`, and reuse it rather than hand-rolling the config):

```python
# in conftest.py — reuse the existing minimal-project helper if one exists.
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_sources_registry.py -v`
Expected: FAIL — `registry_for_project` does not exist.

- [ ] **Step 3: Extract `_resolve_active_profiles` and `build_entity_registry`**

In `science/src/science_tool/graph/sources.py`, add a frozen dataclass and two functions above `load_project_sources`:

```python
@dataclass(frozen=True)
class ActiveProfiles:
    profile_manifests: list[ProfileManifest]
    local_profile_manifest: ProfileManifest | None
    ontology_catalogs: list  # OntologyCatalog
    local_profile: str
    local_manifest_rel: str


def _resolve_active_profiles(project_root: Path) -> ActiveProfiles:
    project_root = project_root.resolve()
    config = _read_project_config(project_root)
    profiles = KnowledgeProfiles.model_validate(config["knowledge_profiles"])
    local_profile = profiles.local
    declared_ontologies = list(config.get("ontologies") or [])
    ontology_catalogs = load_catalogs_for_names(declared_ontologies) if declared_ontologies else []
    local_dir = local_profile_sources_dir(project_root, local_profile=local_profile)
    local_profile_manifest = load_profile_manifest(local_dir / "manifest.yaml")
    profile_manifests: list[ProfileManifest] = [LOCAL_PROFILE]
    shared = load_shared_profile()
    if shared is not None:
        profile_manifests.append(shared)
    local_manifest_rel = os.path.relpath(local_dir / "manifest.yaml", project_root)
    return ActiveProfiles(
        profile_manifests=profile_manifests,
        local_profile_manifest=local_profile_manifest,
        ontology_catalogs=ontology_catalogs,
        local_profile=local_profile,
        local_manifest_rel=local_manifest_rel,
    )


def build_entity_registry(resolved: ActiveProfiles) -> tuple[EntityRegistry, list[SkippedEntity]]:
    """Assemble the profile-aware registry, threading curation_scope from every manifest kind."""
    registry = EntityRegistry.with_core_types()
    graduated_kind_skips: list[SkippedEntity] = []

    def _graduated_skip(kind: str, manifest_rel: str) -> None:
        graduated_kind_skips.append(
            SkippedEntity(
                path=manifest_rel,
                kind=kind,
                reason="kind_graduated_to_core",
                details=(
                    f"manifest declares entity kind {kind!r}, which is now a core kind; "
                    "the core definition supersedes it. Remove the declaration from the manifest."
                ),
            )
        )

    for profile in resolved.profile_manifests:
        for entity_kind in profile.entity_kinds:
            if registry.is_core_kind(entity_kind.name):
                _graduated_skip(entity_kind.name, f"profile:{profile.name}")
                continue
            registry.register_profile_kind(
                entity_kind.name,
                ProjectEntity,
                owner=profile.name,
                entity_class=_resolve_entity_class(entity_kind.entity_class, EntityClass.OPERATIONAL),
                curation_scope=entity_kind.curation_scope,
            )
    for catalog in resolved.ontology_catalogs:
        for entity_type in catalog.entity_types:
            registry.register_catalog_kind(entity_type.name, DomainEntity, owner=catalog.ontology)
    if resolved.local_profile_manifest is not None:
        for entity_kind in resolved.local_profile_manifest.entity_kinds:
            if registry.is_core_kind(entity_kind.name):
                _graduated_skip(entity_kind.name, resolved.local_manifest_rel)
                continue
            registry.register_extension_kind(
                entity_kind.name,
                ProjectEntity,
                entity_class=_resolve_entity_class(entity_kind.entity_class, EntityClass.OPERATIONAL),
                curation_scope=entity_kind.curation_scope,
            )
    return registry, graduated_kind_skips


def registry_for_project(project_root: Path) -> EntityRegistry:
    """Profile-aware registry for a project — the boundary `review_entity` consults."""
    registry, _skips = build_entity_registry(_resolve_active_profiles(project_root))
    return registry
```

Add `from dataclasses import dataclass` and `import os` to the imports if not already present (both are likely present — confirm).

- [ ] **Step 4: Refactor `load_project_sources` to call the new helpers**

Replace `load_project_sources` lines 256-329 (the profile resolution + registry build) with a call to the extracted helpers, keeping the intermediate values it still needs. Specifically:

```python
    resolved = _resolve_active_profiles(project_root)
    local_profile = resolved.local_profile
    ontology_catalogs = resolved.ontology_catalogs
    local_profile_manifest = resolved.local_profile_manifest
    active_profiles = list(resolved.profile_manifests)
    if local_profile_manifest is not None:
        active_profiles.append(local_profile_manifest)
    active_kinds = known_kinds(extra_profiles=active_profiles, ontology_catalogs=ontology_catalogs)

    registry, graduated_kind_skips = build_entity_registry(resolved)
```

Remove the now-duplicated inline `registry = EntityRegistry.with_core_types()` … registration loop and the inline `_graduated_skip`/`graduated_kind_skips` definitions (they moved into `build_entity_registry`). Keep everything downstream (`project_paths`, adapters, …) unchanged — it already consumes `registry`, `graduated_kind_skips`, `local_profile`, `ontology_catalogs`, `active_kinds`, `local_profile_manifest`, which are all still bound. `config`/`project_schema`/`freshness_enabled` are read before line 256 and are untouched.

- [ ] **Step 5: Run parity tests + the full sources/graph suite**

```bash
cd science && uv run --frozen pytest tests/test_sources_registry.py -v
cd science && uv run --frozen pytest tests/ -q -k "sources or graph_build or load_project or validate"
```
Expected: PASS. The parity test proves the extraction is behaviour-preserving; the broader run guards the load path.

- [ ] **Step 6: Commit**

```bash
cd science && uv run ruff check src/science_tool/graph/sources.py && uv run pyright
git add src/science_tool/graph/sources.py tests/test_sources_registry.py tests/conftest.py
git commit -m "refactor(sources): extract build_entity_registry/registry_for_project; thread curation_scope"
```

---

### Task 6: Discover local-extension entities, then enforce scope at the boundary

**Two deliverables, two commits.** First, `find_entity` must be able to *find* a local-extension entity (`design:0001`) — today it cannot, so a `design` review would fail with "Entity not found" **before** the scope check runs. Then move scope enforcement to the boundary and fix the now-contradictory CLI help.

**Files:**
- Modify: `science/src/science_tool/entities.py` — `_load_markdown_entities` (~1849) and the `find_entity` not-found roots message (~724)
- Modify: `science/src/science_tool/entity_review.py:39-84`
- Modify: `science/src/science_tool/entities_cli.py:544-548` (review command help)
- Test: `science/tests/test_entities.py` (discovery regression), `science/tests/test_entity_review_cli.py`

**Interfaces:**
- Consumes: `entity_policies` (existing, `entities.py:180`), `registry_for_project` (Task 5), `curation_scope_for_kind` (Task 4), `CurationScope`.
- Produces: `find_entity(project_root, ref)` discovers entities in project-local extension homes (e.g. `entities/design/`), not just the builtin core homes. `review_entity(...)` refuses a kind whose resolved `curation_scope` is `none`; admits `epistemic` and `correspondence` kinds. Signature and return type unchanged.

#### Deliverable A — local-extension discovery

- [ ] **Step 1: Write the failing discovery regression test**

`find_entity` → `_load_markdown_entities(project_root)` iterates only `_BUILTIN_MARKDOWN_POLICIES` (`entities.py:1849`), so a project-local extension kind whose home is `entities/design/` is invisible. Add to `science/tests/test_entities.py` (reuse the module's project-writing helper; if none writes a local `design` manifest + entity, mirror the `tmp_project_with_design_kind` fixture from Task 5):

```python
from science_tool.entities import find_entity


def test_find_entity_discovers_local_extension_kind(tmp_project_with_design_kind):
    """A local-extension entity under entities/design/ must be findable (else its
    review fails at lookup, before the scope check — plan Task 6 P1)."""
    loc = find_entity(tmp_project_with_design_kind, "design:0001")
    assert loc.kind == "design"
    assert loc.rel_path == "entities/design/0001.md"  # match the fixture's layout
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_entities.py -k discovers_local_extension -v`
Expected: FAIL — `EntityCommandError: Entity not found: design:0001`.

- [ ] **Step 3: Make `_load_markdown_entities` policy-source project-aware**

In `science/src/science_tool/entities.py`, in `_load_markdown_entities` (line ~1849), replace the builtin-only iteration with the project-aware policy table (builtins ∪ local kinds), which `entity_policies(project_root)` already assembles:

```python
def _load_markdown_entities(project_root: Path, kind: str | None = None) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for policy_kind, policy in entity_policies(project_root).items():
        if kind is not None and policy_kind != kind:
            continue
        root = project_root / policy.root
        if not root.is_dir():
            continue
        for path in iter_entity_markdown(root):
            frontmatter, _ = _parse_markdown_file(path)
            entity_id = frontmatter.get("id")
            entity_kind = frontmatter.get("kind")
            if isinstance(entity_id, str) and isinstance(entity_kind, str):
                entities.append({"id": entity_id, "kind": entity_kind, "path": path, "frontmatter": frontmatter})
    return entities
```

And in `find_entity` (line ~724), make the not-found message list the same project-aware roots so the error is accurate:

```python
    roots = ", ".join(str(policy.root) for policy in entity_policies(project_root).values())
    raise EntityCommandError(f"Entity not found: {ref}. Searched source roots: {roots}")
```

**Blast-radius note:** `_load_markdown_entities` also backs the public `load_markdown_entities`. Widening discovery to local kinds is the correct behaviour (a project's own entities should be findable), but run the entities suite in Step 4 to confirm no caller relied on the builtin-only scan.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_entities.py -q && uv run --frozen pytest tests/ -q -k "entity or find_entity or markdown"`
Expected: PASS.

- [ ] **Step 5: Commit deliverable A**

```bash
cd science && uv run ruff check src/science_tool/entities.py
git add src/science_tool/entities.py tests/test_entities.py
git commit -m "fix(entities): find_entity discovers local-extension kinds via entity_policies"
```

#### Deliverable B — the scope boundary + CLI help

- [ ] **Step 6: Write the failing boundary tests**

Add to `science/tests/test_entity_review_cli.py` (reuse the module's existing project fixture that writes `science.yaml` + entities; `review_project_with_design` is the Task 5 `tmp_project_with_design_kind` shape plus a `design:0001` entity):

```python
from science_tool.entity_review import ReviewError, review_entity


def test_review_admits_plan(review_project):
    """Design acceptance test 4: a correspondence kind (plan) is reviewable."""
    path, changed = review_entity(review_project, "plan:0001", note="shipped: ships in commit abc", require_artifact=True)
    assert changed
    assert "last_reviewed" in path.read_text()


def test_review_refuses_dataset(review_project):
    """Design acceptance test 5: a none-scoped kind is refused at the boundary."""
    with pytest.raises(ReviewError, match="curation_scope 'none'"):
        review_entity(review_project, "dataset:example", note="x", require_artifact=True)


def test_review_theater_guard_on_plan(review_project):
    """Design acceptance test 7: a bare timestamp bump on a plan is refused without an artifact."""
    with pytest.raises(ReviewError, match="recorded artifact"):
        review_entity(review_project, "plan:0001", note=None, require_artifact=True)


def test_review_admits_local_extension_kind(review_project_with_design):
    """§6.2: an undeclared project-local extension kind (design) stays reviewable."""
    path, changed = review_entity(
        review_project_with_design, "design:0001", note="matches the shipped module layout", require_artifact=True
    )
    assert changed
```

The `review_project` fixture needs a `plan:0001` entity and a `dataset:example` entity (both with valid frontmatter) plus a `science.yaml`. Reuse the existing entity-writing helpers in the test module.

- [ ] **Step 7: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_entity_review_cli.py -k "plan or dataset or theater or extension" -v`
Expected: FAIL — `dataset` is currently refused with the OLD `EntityClass` message ("only meaningful on epistemic entities"), and `plan` is currently REFUSED (it is `OPERATIONAL`) — the opposite of the new behaviour.

- [ ] **Step 8: Replace the `EntityClass` gate with the `curation_scope` boundary**

In `science/src/science_tool/entity_review.py`, replace the imports and the gate. Remove:
```python
from science_model.identity import EntityClass
from science_tool.graph.entity_registry import EntityKindNotRegisteredError, EntityRegistry
```
and the block at lines 68-77 (`registry = EntityRegistry.with_core_types()` … the `EntityClass.EPISTEMIC` raise).

Add:
```python
from science_model.identity import CurationScope
```
and, inside `review_entity` where the old gate was:
```python
    from science_tool.graph.sources import registry_for_project

    registry = registry_for_project(project_root)
    scope = registry.curation_scope_for_kind(location.kind)
    if scope is CurationScope.NONE:
        raise ReviewError(
            f"entity {entity_ref!r} has kind {location.kind!r} with curation_scope 'none'; "
            f"there is nothing to review. Declare curation_scope on the kind to admit it."
        )
```

Update the docstring: replace "non-epistemic target" / "the epistemic-kind gate" wording with "a `none`-scoped kind" and note scope is decided by `curation_scope_for_kind`. The `require_artifact` check stays exactly as-is, still running after the scope gate so lookup and scope errors take precedence.

- [ ] **Step 9: Fix the contradictory CLI help (design deliverable 5, plan P2)**

In `science/src/science_tool/entities_cli.py`, the `entity_review` command docstring (line ~545) still says "Mark an **epistemic** entity as reviewed", which is now false — correspondence kinds are admitted. Update it:

```python
def entity_review(ref: str, note: str | None) -> None:
    """Mark an entity as reviewed-as-of today.

    Works on any kind whose curation_scope admits review — epistemic kinds and the
    ratified correspondence kinds (plan, spec, method, ...). A review must record an
    artifact via --note; a bare timestamp bump is rejected to prevent review-theater.
    """
```

- [ ] **Step 10: Run tests + pyright to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_entity_review_cli.py -v && uv run pyright src/science_tool/entity_review.py && uv run --frozen pytest tests/ -q -k "entity_review or needs_review"`
Expected: PASS. `plan` reviewable, `dataset` refused with the new message, theater guard intact, local `design` reviewable. (The removed `EntityKindNotRegisteredError` import must have no remaining use — pyright flags a dangling import.)

- [ ] **Step 11: Commit deliverable B**

```bash
cd science && uv run ruff check src/science_tool/entity_review.py src/science_tool/entities_cli.py
git add src/science_tool/entity_review.py src/science_tool/entities_cli.py tests/test_entity_review_cli.py
git commit -m "feat(review): decide scope via curation_scope_for_kind at the boundary; fix CLI help"
```

---

### Task 7: Delete `_validate_review_state_kind` (model does shape only)

**Files:**
- Modify: `science/model/src/science_model/entities.py:390-408` (delete the validator)
- Test: `science/model/tests/test_review_state_model.py:128-144` (rewrite)

**Interfaces:**
- Produces: `Entity.model_validate(raw)` performs NO scope check (design §6.1, test 5b). `Entity` no longer has a `_validate_review_state_kind` method. `ReviewState` shape validation (`_validate_horizon`) is unchanged.

- [ ] **Step 1: Rewrite the model tests to assert shape-only acceptance**

In `science/model/tests/test_review_state_model.py`, replace `test_review_state_rejected_on_non_epistemic_kinds` (128-132) with its inverse — the model now ACCEPTS a shape-valid `review_state` on any kind (scope moved to the tool boundary):

```python
@pytest.mark.parametrize("kind", NON_EPISTEMIC_KINDS)
def test_model_accepts_review_state_shape_on_any_kind(kind: str) -> None:
    """Design test 5b: the model validates SHAPE only — scope is refused at the tool
    boundary (curation_scope_for_kind), not here. A bare model_validate never was a
    safe scope gate (it consulted a list that could not see a project's own kinds)."""
    rs = ReviewState(last_reviewed=None)
    entity = Entity(**_baseline_kwargs(kind), review_state=rs)
    assert entity.review_state is not None


@pytest.mark.parametrize("kind", NON_EPISTEMIC_KINDS)
def test_no_review_state_still_valid_on_non_epistemic_kinds(kind: str) -> None:
    Entity(**_baseline_kwargs(kind))


def test_model_still_rejects_malformed_review_state_shape() -> None:
    """Shape errors still fail at the model — only the kind-SCOPE check moved out."""
    with pytest.raises(ValidationError, match="review_horizon_days"):
        Entity(**_baseline_kwargs("dataset"), review_state=ReviewState(review_horizon_days=0))
```

Keep `test_review_state_allowed_on_open_kinds` but update its comment (there is no closed list anymore; all shapes are accepted at the model).

- [ ] **Step 2: Run to verify the OLD test now fails**

Run: `cd science/model && uv run --frozen pytest tests/test_review_state_model.py -k "review_state" -v`
Expected: the new `test_model_accepts_review_state_shape_on_any_kind` FAILS (the validator still rejects), confirming the test bites.

- [ ] **Step 3: Delete the validator**

In `science/model/src/science_model/entities.py`, delete the entire `_validate_review_state_kind` method (lines 390-408 — the `@model_validator(mode="after")` decorator through `return self`). Leave `_validate_lens_views` and every other validator untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run --frozen pytest tests/test_review_state_model.py -q && uv run --frozen pytest -q`
Expected: PASS (whole model suite).

- [ ] **Step 5: Confirm no other model code references the deleted symbol**

Run: `cd science && grep -rn "_validate_review_state_kind\|non_epistemic" model/src`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
cd science/model && uv run ruff check src/science_model/entities.py
git add model/src/science_model/entities.py model/tests/test_review_state_model.py
git commit -m "refactor(model): delete _validate_review_state_kind — scope moved to the tool boundary"
```

---

### Task 8: Single-decider guard (import-closure)

**Files:**
- Test: `science/tests/test_curation_scope_guard.py` (create)

**Interfaces:**
- Consumes: nothing new. Asserts the invariant of design acceptance test 1.

- [ ] **Step 1: Write the guard test**

Design test 1 warns: *a guard that lists its scope has a hole by construction.* So scan the source tree rather than enumerate allowed modules. Create `science/tests/test_curation_scope_guard.py`:

```python
"""Design acceptance test 1: exactly one decider resolves curation scope."""

import ast
from pathlib import Path

from science_model.entities import Entity

# Both real source roots. The test lives at science/tests/, so science/ is parents[1];
# the model package is science/model/, NOT repository-root model/.
_TOOL_SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"
_MODEL_SRC = Path(__file__).resolve().parents[1] / "model" / "src" / "science_model"
assert _TOOL_SRC.is_dir() and _MODEL_SRC.is_dir(), (_TOOL_SRC, _MODEL_SRC)  # fail loud on a path typo

# The single legitimate home of scope DECISION: the enum lives in identity.py; the
# default is applied in entity_registry.py. Everything else may only CALL the decider
# and compare its RESULT.
_DECIDER = _TOOL_SRC / "graph" / "entity_registry.py"
_ENUM_HOME = _MODEL_SRC / "identity.py"

# The deleted closed list (design §4). Its reappearance anywhere is the two-taxonomy
# split re-emerging.
_CLOSED_LIST = {"task", "dataset", "workflow-run", "data-package", "paper",
                "prose-source", "book", "experiment", "code-file"}


def _py_files(root: Path):
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


def _all_src():
    return _py_files(_TOOL_SRC) + _py_files(_MODEL_SRC)


def test_validator_is_gone():
    assert not hasattr(Entity, "_validate_review_state_kind"), (
        "the model-layer scope validator must be deleted (design §6.1)"
    )


def test_closed_list_literal_appears_nowhere():
    """No module reconstructs the closed set as a review gate (both source roots)."""
    offenders = []
    for path in _all_src():
        text = path.read_text()
        # a set/frozenset literal containing the whole closed list
        if all(f'"{k}"' in text or f"'{k}'" in text for k in _CLOSED_LIST):
            offenders.append(str(path))
    assert offenders == [], f"closed-list knowledge resurfaced in: {offenders}"


def test_only_one_module_applies_the_scope_default():
    """The DEFAULT-application polarity (undeclared → correspondence/none) is what
    'deciding scope' means. A second decider under ANY function name would have to
    name a CurationScope default value to return it. The only production module
    permitted to reference `CurationScope.CORRESPONDENCE` / `CurationScope.NONE` as a
    RETURNED default is the decider; the enum's own definition lives in identity.py.
    Consumers may compare against the decider's result but must not re-derive it.

    This catches a renamed second decider that `def curation_scope_for_kind`-name
    matching would miss, and does not enumerate an allow-list of trusted modules —
    it names only the one legitimate home."""
    offenders = []
    for path in _all_src():
        if path in (_DECIDER, _ENUM_HOME):
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            # a `return <...CurationScope.CORRESPONDENCE/NONE...>` is default application
            if isinstance(node, ast.Return) and node.value is not None:
                src = ast.dump(node.value)
                if "CORRESPONDENCE" in src or ("attr='NONE'" in src and "CurationScope" in src):
                    offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], f"a second scope decider applies the default in: {offenders}"


def test_decider_exists_where_expected():
    """The one decider is a method on EntityRegistry named curation_scope_for_kind."""
    tree = ast.parse(_DECIDER.read_text())
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "curation_scope_for_kind" in names


def test_entity_review_does_not_branch_on_entity_class_for_scope():
    """The old EntityClass gate is gone from the review path."""
    text = (_TOOL_SRC / "entity_review.py").read_text()
    assert "EntityClass" not in text, "review scope must not consult EntityClass (design §6.1)"
    assert "curation_scope_for_kind" in text
```

- [ ] **Step 2: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_curation_scope_guard.py -v`
Expected: PASS (Tasks 4–7 already satisfy every assertion). The `assert _TOOL_SRC.is_dir() and _MODEL_SRC.is_dir()` at import time fails loudly if either path is wrong. `test_entity_review.py` compares `scope is CurationScope.NONE` (a comparison, not a `return` of a default) so it is not flagged; if a legitimate consumer ever needs to `return CurationScope.NONE`, route it through the decider instead — do NOT add the module to an allow-list.

- [ ] **Step 3: Commit**

```bash
cd science && uv run ruff check tests/test_curation_scope_guard.py
git add tests/test_curation_scope_guard.py
git commit -m "test(scope): import-closure guard — exactly one curation-scope decider"
```

---

### Task 9: Directional freshness isolation (correspondence stays out of `bears_on` sinks)

**Files:**
- Test: `science/tests/test_freshness_derivation.py` (extend) and confirm `tests/test_bears_on_derivation.py`

**Interfaces:**
- Consumes: nothing new — this proves the Global Constraint that `bears_on`/freshness is untouched (design test 6, §5.1). No production code changes; if a test fails, the fix is in the test's expectations, never by loosening freshness.

- [ ] **Step 1: Write the directional isolation test**

Add to `science/tests/test_freshness_derivation.py`, following the module's existing
pattern exactly — `derive_freshness(ds, entities=..., today=..., source_changes={})` over
an `EntityFreshnessInfo` dict, with the module helpers `_u`, `_ds_with_bears_on`,
`_state_for` (there is no `build_graph`/`entity_uri`/`freshness_project` — those do not
exist in this file):

```python
def test_correspondence_entity_never_receives_freshness_state():
    """Design test 6: a correspondence-scoped OPERATIONAL kind (plan) with a set
    last_reviewed never becomes a bears_on TARGET and never receives sci:freshnessState.
    derive_freshness gates sinks on EntityClass.EPISTEMIC (freshness.py:337), which
    `plan` (OPERATIONAL) is not — curation_scope did not change this."""
    plan = _u("plan/0001")
    src = _u("hypothesis/h1")
    ds = _ds_with_bears_on([(src, plan)])  # even with an inbound bears_on edge
    entities: dict[str, EntityFreshnessInfo] = {
        str(plan): {
            "kind_class": EntityClass.OPERATIONAL,
            "last_reviewed": date(2026, 4, 1),
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
        str(src): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 4, 1),
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        },
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 3), source_changes={})
    assert _state_for(ds, plan) is None  # OPERATIONAL → never a freshness sink
```

(`EntityFreshnessInfo`, `derive_freshness`, `date`, and `EntityClass` are already imported at the top of the file; `_u`, `_ds_with_bears_on`, `_state_for` are module-level helpers.)

- [ ] **Step 2: Confirm the pre-registration source suite still passes (the over-tightening guard)**

Run: `cd science && uv run --frozen pytest -k pre_registration -v`
Expected: **5 passed** — including `test_pre_registration_related_epistemic_targets_derive_bears_on_by_default`. `pre-registration` is `correspondence`-scoped AND a `bears_on` SOURCE; this suite is the guard that the change did not break it (design §5.1, risk table).

- [ ] **Step 3: Run the new test + the broader freshness/bears_on suites**

Run: `cd science && uv run --frozen pytest tests/test_freshness_derivation.py tests/test_bears_on_derivation.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
cd science && uv run ruff check tests/test_freshness_derivation.py
git add tests/test_freshness_derivation.py
git commit -m "test(freshness): assert correspondence entities stay out of bears_on sinks (directional)"
```

---

### Task 10: Downstream verification against real checkouts (not CI)

**Files:**
- Create: `science/scripts/verify_downstream_scope.sh`

**Interfaces:**
- Consumes: real project checkouts at `~/d/cancer/cancer-types/multiple-myeloma` and `~/d/natural-systems`. Design test 10 / §6.2 insist this runs against real `entities/`, because this repo has none and green CI here proves nothing.

- [ ] **Step 1: Write the verification script**

The comparison is *which toolkit revision* runs — `main` vs the branch — against the
**same** downstream projects. The script points `validate --project-root` at each
downstream project and runs the toolkit selected by `SCIENCE_PKG` (default: the package
containing the script). That lets one script — living only on the branch — drive both
the `main` toolkit (via a throwaway `main` worktree) and the branch toolkit, with no
stashing and no `git checkout` of the working tree.

Create `science/scripts/verify_downstream_scope.sh`:

```bash
#!/usr/bin/env bash
# Design acceptance test 10 / §6.2: `science validate` exit code + result count must be
# UNCHANGED by the curation_scope change on real downstream projects. Run once with the
# `main` toolkit (SCIENCE_PKG=<main-worktree>/science) and once with the branch toolkit.
set -euo pipefail

# Toolkit package to run; defaults to the science/ dir that contains this script.
SCIENCE_PKG="${SCIENCE_PKG:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

MM=~/d/cancer/cancer-types/multiple-myeloma
NS=~/d/natural-systems
OUT="${1:?usage: verify_downstream_scope.sh <baseline|branch>}"
STAMP="/tmp/curation-scope-verify-$OUT.txt"
: > "$STAMP"

for proj in "$MM" "$NS"; do
  name="$(basename "$proj")"
  json="/tmp/$name-$OUT.json"
  set +e   # a nonzero validate exit is data, not a failure of this script
  ( cd "$SCIENCE_PKG" && uv run --frozen science validate --format json --project-root "$proj" ) > "$json" 2>/dev/null
  code=$?
  set -e
  # validate --format json emits {"errors","warnings","infos","results":[...]} (validate/cli.py)
  n=$(jq '.results | length' "$json" 2>/dev/null || echo PARSE_ERR)
  e=$(jq '.errors'          "$json" 2>/dev/null || echo PARSE_ERR)
  w=$(jq '.warnings'        "$json" 2>/dev/null || echo PARSE_ERR)
  echo "$name exit=$code results=$n errors=$e warnings=$w" | tee -a "$STAMP"
done
echo "wrote $STAMP (toolkit: $SCIENCE_PKG)"
```

Confirm the JSON keys against the real CLI once before trusting counts:
`cd science && uv run science validate --format json --project-root ~/d/natural-systems | jq 'keys'`.

- [ ] **Step 2: Capture the baseline with the `main` toolkit (no stashing)**

```bash
cd science && chmod +x scripts/verify_downstream_scope.sh
git worktree add /tmp/science-main main                       # clean main checkout of the TOOLKIT
SCIENCE_PKG=/tmp/science-main/science ./scripts/verify_downstream_scope.sh baseline
```

The branch's script runs the `main` toolkit against the real mm + ns checkouts. Nothing in the working tree is stashed or checked out. (If `uv run --frozen` in the worktree needs a sync, run `cd /tmp/science-main/science && uv sync --frozen` first.)

- [ ] **Step 3: Run with the branch toolkit and diff**

```bash
cd science && ./scripts/verify_downstream_scope.sh branch      # default SCIENCE_PKG = this (branch) science/
git worktree remove /tmp/science-main
diff /tmp/curation-scope-verify-baseline.txt /tmp/curation-scope-verify-branch.txt && echo "UNCHANGED — test 10 passes"
```
Expected: `UNCHANGED`. multiple-myeloma's local `design`/`review`/`critique`/`audit` extension kinds must resolve to `correspondence` (reviewable, as today), so `validate` output does not move. A DIFF here is a real regression — investigate before proceeding; do not adjust the baseline to match.

- [ ] **Step 4: Commit the script + record the result**

```bash
cd science && git add scripts/verify_downstream_scope.sh
git commit -m "test(scope): downstream verify_downstream_scope.sh — validate parity on mm + ns"
```

Record the captured `exit=/results=/errors=/warnings=` lines for mm and ns in the PR description / task notes as the test-10 evidence.

---

## Final validation

- [ ] **Full suites, both packages, lint, types:**

```bash
cd science/model && uv run --frozen pytest -q && uv run ruff check
cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright
```
Expected: all green.

- [ ] **End-to-end smoke — the blocker this spec exists to clear:**

`science entity review` has **no `--project-root`** — it operates on `Path.cwd()`. Run it
with the downstream project as the working directory, selecting the branch toolkit with
`uv run --project`:

```bash
cd ~/d/natural-systems && uv run --project ~/d/science/science science entity review plan:0001 --note "shipped in <commit>"
```
Expected: `Reviewed plan:0001 -> ...` (was refused before this spec — `plan` is `OPERATIONAL`). Then confirm from the same cwd that `entity review dataset:<id>` is refused with the `curation_scope 'none'` message, and that `entity review plan:0001` with no `--note` is refused by the theater guard.

## Self-review notes (for the executor)

- **Every design acceptance test maps to a task:** test 1 single-decider (Task 8); test 2 closed-list→none (Task 4); test 3 default-none-core (Task 4); test 4 positive plan review (Task 6-B); test 5 negative dataset refusal (Task 6-B); test 5b model shape-only (Task 7); test 6 freshness directional (Task 9); test 7 theater guard (Task 6-B); test 8 exhaustive roster (Task 4 Step 1); test 9 extension→correspondence (Task 4 unit + Task 6-B e2e); test 10 downstream (Task 10).
- **Local-extension review has a discovery precondition (Task 6-A):** `find_entity` must scan `entity_policies(project_root)`, not just `_BUILTIN_MARKDOWN_POLICIES`, or a `design:0001` review dies at lookup before the scope check. This is why Task 6 has two commits.
- **The CLI help must stop saying "epistemic entity"** (Task 6-B Step 9) — correspondence kinds are now admitted, and stale help is a user-facing contradiction.
- **Do not** derive `curation_scope` from `EntityClass` anywhere. **Do not** re-point `_validate_review_state_kind` — delete it. **Do not** add an `EpistemicReviewState` alias.
- If `registry_for_project` is too heavy for a command that runs outside a project (no `science.yaml`), that is acceptable — `entity review` is inherently project-scoped and already resolves entities under a project root.

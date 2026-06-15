# Kind Descriptor & Model Registry — Implementation Plan (Patchwork Kernel Spec 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `EntityKind`/`CORE_PROFILE` the single source of truth for per-kind facts (path policy, status vocab, shortform, template, `entity_class`), derive every tool/registry surface from it, reconcile `EntityType` + the registry under a strict drift gate, and delete the transitional `CORE_KINDS` manifest.

**Architecture:** Extend `EntityKind` to the full per-kind record, populate `CORE_PROFILE` (authored-core + reserved) and tag `LOCAL_PROFILE` (source-only) from today's verified literals, land a strict 3-way reconciliation gate (descriptor ≡ registry ≡ `EntityType` core projection), then flip each derived surface to compute from the descriptor behind its existing accessor — each flip pinned by a value-for-value equivalence test captured *before* the refactor. Finally remove `_CORE_KIND_CLASSES` and `science_model/kinds.py`.

**Tech Stack:** Python 3.13, Pydantic v2, `uv` workspace (`science_model` is a workspace member at `science/model/`), pytest, ruff. Design: `~/d/science/docs/plans/2026-06-14-kind-descriptor-model-registry-design.md`.

---

## Conventions (read before any task)

- **Worktree:** all work happens in `~/d/science/.worktrees/kind-descriptor-model-registry` on branch `feat/kind-descriptor-model-registry`. Every step `cd`s into it; verify `rtk git branch --show-current` prints `feat/kind-descriptor-model-registry` before committing (commits must not leak to `main`).
- **Tests run from the package dir under the worktree:** `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest <path>`. Model tests live in `science/model/tests/`; tool/root tests in `science/tests/`. Running pytest from the repo root fails with `ModuleNotFoundError: No module named 'science_model'`. (`rtk pytest` collects 0 tests under this uv workspace — keep `uv run --frozen pytest`.) Use `rtk git` / `rtk grep` for git/grep.
- **Dependency direction:** `science_model` must never import `science_tool`. Model-package tests may not import the registry or tool maps; that assertion lives in the tool/root suite.
- **No `Co-Authored-By` trailers** in commits. Use `~/d/` (not absolute Dropbox paths) in any doc/code text.
- **No compatibility/shim layers, no "Unified"/"legacy" naming.** Composition over inheritance; fail-loud over silent fallback.
- **Behavior-neutral except one documented additive change:** growing `CORE_PROFILE` grows `sources.py::_CORE_KINDS` (design §3/§8). That is guarded by the core-kind recognition contract test (Task 2) + the full suite; every other surface is value-for-value identical.

---

## Authoritative data sources (the SSOT for Task 2's values)

Every value populated in Task 2 is **transcribed from an existing literal**, with **exactly two explicit new audit rulings** (called out below): the `entity_class` of `decision` and `claim-registry`, which were map-only and had no prior registry/enum entry, so no literal to copy. Everything else is a transcription. The four `FROZEN_*` maps are the ones currently pasted in `science/tests/test_kind_descriptor_derivation.py` (the keystone guard — itself derived green from today's literals). Quoting them here so tasks are self-contained:

- **Path policy** (`home` + `strategy`) and the per-kind `default_status` / `statuses` come from `FROZEN_MARKDOWN_POLICIES`, `FROZEN_DEFAULT_STATUS`, `FROZEN_STATUS_VALUES` (reproduced verbatim in Task 4/5 fixtures below). `home` is the `EntityPathPolicy.root` rendered as a string, e.g. `"entities/hypotheses"`; singletons point at a file, e.g. `"entities/research-question.md"`, `"entities/claim-registry.yaml"`.
- **`shortform`** comes from `FROZEN_SHORTFORM = {"d":"discussion","h":"hypothesis","i":"interpretation","p":"proposition","q":"question","t":"theme"}`.
- **`entity_class`** comes from `_CORE_KIND_CLASSES` in `science/src/science_tool/graph/entity_registry.py` (reproduced in the Task 2 table below) — **except** the two new audit rulings: `decision` → `EntityClass.REFERENCE`, `claim-registry` → `EntityClass.OPERATIONAL` (these had no prior class). The three `source-only` kinds (`model`, `canonical_parameter`, `parameter_binding`) carry `EntityClass.OPERATIONAL` — their current effective value (the `register_profile_kind` default).
- **`template_ready`** is `True` for exactly the current `MIGRATED_KINDS` (`science/model/src/science_model/templates.py`): `{hypothesis, question, interpretation, discussion, theme, proposition, evidence-line, finding, method, paper, book, pre-registration, synthesis}` (13).
- **`category`**: `unknown` → `reserved`; `model`/`canonical_parameter`/`parameter_binding` → `source-only`; every other core kind → `authored-core`.

The gate (Task 3) and the per-flip equivalence tests (Tasks 4–6) are the *authority* that the transcription is exact — if a value is wrong, those tests go red.

---

## File Structure

**Created:**
- `science/model/tests/test_entity_kind_schema.py` — unit tests for the extended `EntityKind` / `KindCategory` / `EntityClass` placement (Task 1).
- `science/model/tests/test_kind_reconciliation.py` — model-package drift gate, assertions 1–3 (Task 3).
- `science/tests/test_kind_reconciliation_registry.py` — tool/root drift gate, assertion 4 + core-kind recognition contract (Task 3 / Task 2).
- `science/tests/test_kind_map_equivalence.py` — per-flip equivalence tests for the tool maps (Tasks 4–6); holds the `FROZEN_*` fixtures.

**Modified:**
- `science/model/src/science_model/identity.py` — add `EntityClass` (Task 1).
- `science/model/src/science_model/entities.py` — remove local `EntityClass`, re-export from `identity` (Task 1); add 9 `EntityType` members (Task 2).
- `science/model/src/science_model/profiles/schema.py` — `EntityFilenameStrategy`, `KindCategory`, extended `EntityKind` (Task 1).
- `science/model/src/science_model/kinds.py` — re-export `EntityFilenameStrategy` from `schema` (Task 1); **deleted** (Task 7).
- `science/model/src/science_model/profiles/core.py` — fully populate `CORE_PROFILE` (Task 2).
- `science/model/src/science_model/profiles/local.py` — tag `category=source-only` (Task 2).
- `science/model/src/science_model/templates.py` — `MIGRATED_KINDS` derives from `CORE_PROFILE` (Task 6).
- `science/src/science_tool/graph/entity_registry.py` — `CORE_KIND_MODELS` + `core_kinds()` (Task 1); `with_core_types` iterates descriptors, `_CORE_KIND_CLASSES` removed (Task 6).
- `science/src/science_tool/entities.py` — the four maps derive from `CORE_PROFILE` (Tasks 4–5); import `EntityFilenameStrategy` from `profiles.schema` (Task 7).

**Deleted (Task 7):**
- `science/model/src/science_model/kinds.py`, `science/model/tests/test_kinds.py`, `science/tests/test_kind_descriptor_derivation.py`.

---

## Task 1: Extend the descriptor schema (behavior-neutral)

**Files:**
- Modify: `science/model/src/science_model/identity.py`
- Modify: `science/model/src/science_model/entities.py`
- Modify: `science/model/src/science_model/profiles/schema.py`
- Modify: `science/model/src/science_model/kinds.py`
- Modify: `science/src/science_tool/graph/entity_registry.py`
- Test: `science/model/tests/test_entity_kind_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_entity_kind_schema.py
from __future__ import annotations

from science_model.entities import EntityClass as EntityClassFromEntities
from science_model.identity import EntityClass
from science_model.profiles.schema import EntityFilenameStrategy, EntityKind, KindCategory


def test_entity_class_defined_in_identity_and_reexported() -> None:
    # stable public path preserved
    assert EntityClassFromEntities is EntityClass
    assert {e.value for e in EntityClass} == {"epistemic", "operational", "reference"}


def test_kind_category_values() -> None:
    assert {c.value for c in KindCategory} == {"authored-core", "reserved", "source-only"}


def test_entity_kind_new_fields_default_to_neutral() -> None:
    ek = EntityKind(name="x", canonical_prefix="x", layer="layer/core", description="d")
    assert ek.entity_class is None
    assert ek.category is None
    assert ek.template_ready is False
    assert ek.shortform is None
    assert ek.strategy is None


def test_entity_kind_typed_fields_coerce() -> None:
    ek = EntityKind(
        name="hypothesis", canonical_prefix="hypothesis", layer="layer/core", description="d",
        entity_class="epistemic", category="authored-core", template_ready=True,
        shortform="h", home="entities/hypotheses", strategy="numeric",
    )
    assert ek.entity_class is EntityClass.EPISTEMIC
    assert ek.category is KindCategory.AUTHORED_CORE
    assert ek.strategy == "numeric"


def test_entity_filename_strategy_is_the_relocated_literal() -> None:
    # kinds.py must re-export the same object during the transition
    from science_model.kinds import EntityFilenameStrategy as FromKinds
    assert FromKinds is EntityFilenameStrategy
```

- [ ] **Step 2: Run it; expect failure** (`ImportError`/attribute errors)

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest model/tests/test_entity_kind_schema.py -q`
Expected: FAIL (cannot import `EntityClass` from `identity`, `KindCategory` missing, etc.).

- [ ] **Step 3: Move `EntityClass` to `identity.py`**

In `science/model/src/science_model/identity.py`, append (keep the existing docstring text from `entities.py`):

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

- [ ] **Step 4: Re-export `EntityClass` from `entities.py`**

In `science/model/src/science_model/entities.py`: delete the local `class EntityClass(StrEnum): ...` block (currently at ~line 117) and add a top-level import near the other `science_model.identity` usage (verify whether `entities.py` already imports from `identity`; if so, extend that import, else add `from science_model.identity import EntityClass`). The name must be importable as `science_model.entities.EntityClass`. Do **not** add a module-level `__all__`.

- [ ] **Step 5: Extend `schema.py`**

In `science/model/src/science_model/profiles/schema.py`, add imports and definitions above `EntityKind`:

```python
from enum import StrEnum
from typing import Literal

from science_model.identity import EntityClass

EntityFilenameStrategy = Literal["numeric", "citekey", "singleton", "slug", "verbatim"]


class KindCategory(StrEnum):
    """Named-contract taxonomy for kinds (design §2.3)."""

    AUTHORED_CORE = "authored-core"
    RESERVED = "reserved"
    SOURCE_ONLY = "source-only"
```

Then extend `EntityKind` (preserve existing field order/comments; add the new fields and type `strategy`):

```python
class EntityKind(BaseModel):
    """An entity kind declared by a knowledge profile."""

    name: str
    canonical_prefix: str
    layer: str
    description: str
    entity_class: EntityClass | None = None
    category: KindCategory | None = None  # None for project-local kinds (only built-in profiles set it)
    template_ready: bool = False  # renders through the migrated Renderer path (== today's MIGRATED_KINDS)
    shortform: str | None = None  # single-letter CLI alias, e.g. "h" -> hypothesis
    home: str | None = None
    strategy: EntityFilenameStrategy | None = None
    default_status: str | None = None
    statuses: list[str] | None = None
    structured_source: str | None = None
    structured_source_root_key: str | None = None
```

(Remove the now-redundant inline comment that described `strategy` as `"numeric" | "citekey"` only.)

- [ ] **Step 6: Relocate the Literal source in `kinds.py`**

In `science/model/src/science_model/kinds.py`, replace its local `EntityFilenameStrategy = Literal[...]` definition with a re-export so the tool's existing `from science_model.kinds import ... EntityFilenameStrategy` keeps working until Task 7:

```python
from science_model.profiles.schema import EntityFilenameStrategy  # noqa: F401  (re-export; relocated here in Spec 2)
```

Keep `KindDescriptor`, `CORE_KINDS`, `CORE_KINDS_BY_NAME` unchanged. Verify no import cycle (`profiles.schema` imports only `identity` + pydantic; `kinds.py` → `profiles.schema` is acyclic).

- [ ] **Step 7: Scaffold the registry code map + accessor**

In `science/src/science_tool/graph/entity_registry.py`, add the typed-model map and a read-only accessor (do **not** yet change `with_core_types`/`_CORE_KIND_CLASSES` — that is Task 6):

```python
# The only per-kind fact that cannot be data: the bound Pydantic class. Kinds
# absent here default to ProjectEntity at registration (design §2.4). Consumed by
# with_core_types() once the registry flip lands (Task 6).
CORE_KIND_MODELS: dict[str, type[Entity]] = {
    "task": TaskEntity,
    "dataset": DatasetEntity,
    "workflow-run": WorkflowRunEntity,
    "research-package": ResearchPackageEntity,
    "mechanism": MechanismEntity,
    "theme": ThemeEntity,
    "book": BookEntity,
    "paper": PaperEntity,
    "talk": TalkEntity,
    "structural-chain": StructuralChainEntity,
    "chain-audit": ChainAuditEntity,
    "code-file": CodeFileEntity,
    "evidence-line": EvidenceLineEntity,
    "inquiry": InquiryEntity,
    "proposition": PropositionEntity,
    "patch-definition": PatchDefinitionEntity,
}
```

And add to `EntityRegistry`:

```python
    def core_kinds(self) -> frozenset[str]:
        """Names of the registered core kinds (for reconciliation tests)."""
        return frozenset(self._core)
```

- [ ] **Step 8: Run tests + ruff**

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest model/tests/test_entity_kind_schema.py -q && uv run --frozen ruff check model/src/science_model src/science_tool/graph/entity_registry.py`
Expected: PASS, clean.

- [ ] **Step 9: Quick regression of nearby suites** (schema is widely imported)

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest model/tests -q`
Expected: PASS (the new fields are defaulted, so existing manifests/loaders are unaffected).

- [ ] **Step 10: Commit**

```bash
cd ~/d/science/.worktrees/kind-descriptor-model-registry
rtk git add science/model/src/science_model/identity.py science/model/src/science_model/entities.py \
  science/model/src/science_model/profiles/schema.py science/model/src/science_model/kinds.py \
  science/src/science_tool/graph/entity_registry.py science/model/tests/test_entity_kind_schema.py
rtk git commit -m "feat(kinds): extend EntityKind descriptor; relocate EntityClass + EntityFilenameStrategy; scaffold registry model map"
```

---

## Task 2: Populate descriptors, reconcile EntityType, tag locals (the audit)

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py`
- Modify: `science/model/src/science_model/profiles/local.py`
- Modify: `science/model/src/science_model/entities.py` (`EntityType` enum)
- Test: `science/tests/test_kind_reconciliation_registry.py` (core-kind recognition contract — written here, used as the guard)

> This task is **data transcription from existing literals** (see "Authoritative data sources"). The reconciliation gate (Task 3) and the equivalence tests (Tasks 4–6) prove the transcription is exact; **write Task 3's gate alongside this task and drive the population to green** rather than eyeballing 45 descriptors.

- [ ] **Step 1: Write the core-kind recognition contract test (captures the intended additive delta)**

```python
# science/tests/test_kind_reconciliation_registry.py  (recognition-contract portion)
from __future__ import annotations

from science_tool.graph.sources import known_kinds

# Captured BEFORE expanding CORE_PROFILE (the 23-kind core recognition set). Paste
# the exact pre-expansion result of known_kinds() here so the delta is reviewed.
PRE_EXPANSION_CORE_KINDS = frozenset({
    "hypothesis", "question", "task", "proposition", "observation", "finding",
    "interpretation", "story", "mechanism", "theme", "paper", "book", "talk",
    "experiment", "method", "workflow", "workflow-run", "workflow-step",
    "data-package", "structural-chain", "chain-audit", "code-file", "evidence-line",
})

# The authored-core/reserved kinds being ADDED to CORE_PROFILE this slice.
INTENDED_ADDITIONS = frozenset({
    "dataset", "variable", "assumption", "transformation", "article", "spec",
    "research-package", "validation-report", "curation-sweep", "concept",
    "construct", "outcome", "pre-registration", "research-question", "topic",
    "discussion", "inquiry", "plan", "report", "synthesis", "search",
    "patch-definition", "decision", "claim-registry", "unknown",
})


def test_core_kind_recognition_delta_is_exactly_the_intended_additions() -> None:
    now = known_kinds()
    assert PRE_EXPANSION_CORE_KINDS <= now, "lost a previously-core kind"
    assert now - PRE_EXPANSION_CORE_KINDS == INTENDED_ADDITIONS, "unexpected core-kind delta"
```

> Before editing `core.py`, run `known_kinds()` once and confirm `PRE_EXPANSION_CORE_KINDS` matches today's value exactly (adjust the frozen set if the live value differs — it must equal the *current* `CORE_PROFILE.entity_kinds` names). This test goes red until population is complete, then locks the delta.

- [ ] **Step 2: Add the 9 missing `EntityType` members**

In `science/model/src/science_model/entities.py`, add to `EntityType` (additive; place near related members, keep `StrEnum` hand-written):

```python
    CONSTRUCT = "construct"
    CURATION_SWEEP = "curation-sweep"
    OUTCOME = "outcome"
    PRE_REGISTRATION = "pre-registration"
    RESEARCH_QUESTION = "research-question"
    STRUCTURAL_CHAIN = "structural-chain"
    CHAIN_AUDIT = "chain-audit"
    DECISION = "decision"
    CLAIM_REGISTRY = "claim-registry"
```

- [ ] **Step 3: Populate `CORE_PROFILE` (authored-core + reserved) — the audit table**

For every kind below, ensure a `CORE_PROFILE.entity_kinds` `EntityKind` exists (add new ones; extend the 23 already present). Set `category`, `entity_class` (verbatim from `_CORE_KIND_CLASSES`), `template_ready` (True iff in `MIGRATED_KINDS`), `shortform` (from `FROZEN_SHORTFORM`), and — **only for kinds present in `FROZEN_MARKDOWN_POLICIES`** — `home`/`strategy`/`default_status`/`statuses` copied verbatim from the Task 4/5 fixtures. Kinds **not** in the path-policy set leave those four blank. For newly-added kinds also author `canonical_prefix` (= `name` unless an existing convention differs), `layer="layer/core"`, and a one-line `description`.

Reference table (`entity_class` column = `_CORE_KIND_CLASSES` verbatim; `tmpl` = `template_ready`; `sf` = shortform; `path?` = has a `FROZEN_MARKDOWN_POLICIES` entry):

| kind | category | entity_class | tmpl | sf | path? |
|---|---|---|---|---|---|
| task | authored-core | OPERATIONAL | – | – | – |
| dataset | authored-core | OPERATIONAL | – | – | – |
| workflow-run | authored-core | OPERATIONAL | – | – | – |
| research-package | authored-core | OPERATIONAL | – | – | – |
| mechanism | authored-core | EPISTEMIC | – | – | ✓ |
| theme | authored-core | EPISTEMIC | ✓ | t | ✓ |
| structural-chain | authored-core | EPISTEMIC | – | – | – |
| chain-audit | authored-core | EPISTEMIC | – | – | – |
| evidence-line | authored-core | EPISTEMIC | ✓ | – | ✓ |
| article | authored-core | REFERENCE | – | – | – |
| assumption | authored-core | EPISTEMIC | – | – | – |
| code-file | authored-core | OPERATIONAL | – | – | – |
| concept | authored-core | REFERENCE | – | – | ✓ |
| construct | authored-core | REFERENCE | – | – | ✓ |
| curation-sweep | authored-core | OPERATIONAL | – | – | – |
| data-package | authored-core | OPERATIONAL | – | – | – |
| discussion | authored-core | EPISTEMIC | ✓ | d | ✓ |
| experiment | authored-core | OPERATIONAL | – | – | – |
| finding | authored-core | EPISTEMIC | ✓ | – | ✓ |
| hypothesis | authored-core | EPISTEMIC | ✓ | h | ✓ |
| inquiry | authored-core | EPISTEMIC | – | – | ✓ |
| interpretation | authored-core | EPISTEMIC | ✓ | i | ✓ |
| method | authored-core | OPERATIONAL | ✓ | – | ✓ |
| observation | authored-core | EPISTEMIC | – | – | ✓ |
| outcome | authored-core | REFERENCE | – | – | ✓ |
| book | authored-core | OPERATIONAL | ✓ | – | ✓ |
| paper | authored-core | OPERATIONAL | ✓ | – | ✓ |
| talk | authored-core | OPERATIONAL | – | – | ✓ |
| plan | authored-core | OPERATIONAL | – | – | ✓ |
| pre-registration | authored-core | OPERATIONAL | ✓ | – | ✓ |
| patch-definition | authored-core | EPISTEMIC | – | – | ✓ |
| proposition | authored-core | EPISTEMIC | ✓ | p | ✓ |
| question | authored-core | EPISTEMIC | ✓ | q | ✓ |
| research-question | authored-core | EPISTEMIC | – | – | ✓ |
| report | authored-core | EPISTEMIC | – | – | ✓ |
| search | authored-core | OPERATIONAL | – | – | ✓ |
| spec | authored-core | OPERATIONAL | – | – | – |
| story | authored-core | EPISTEMIC | – | – | – |
| synthesis | authored-core | EPISTEMIC | ✓ | – | ✓ |
| topic | authored-core | REFERENCE | – | – | ✓ |
| transformation | authored-core | OPERATIONAL | – | – | – |
| validation-report | authored-core | EPISTEMIC | – | – | – |
| variable | authored-core | REFERENCE | – | – | – |
| workflow | authored-core | OPERATIONAL | – | – | – |
| workflow-step | authored-core | OPERATIONAL | – | – | – |
| **unknown** | **reserved** | REFERENCE | – | – | – |
| **decision** | authored-core | *audit: assign* | – | – | ✓ |
| **claim-registry** | authored-core | *audit: assign* | – | – | ✓ |

> `decision` and `claim-registry` were map-only (no prior registry/enum entry); the audit assigns each an `entity_class` (seed: `decision` → `REFERENCE`, `claim-registry` → `OPERATIONAL`) and registers them with `ProjectEntity` (Task 6 maps them by default). They carry their `FROZEN_MARKDOWN_POLICIES` path policy (`decision` → `entities/decision`,`verbatim`; `claim-registry` → `entities/claim-registry.yaml`,`singleton`); singleton/`verbatim` kinds have no status vocab so leave `default_status`/`statuses` blank for `claim-registry` and `research-question`, and copy `decision`'s status values from `FROZEN_*`.

Worked examples — copy these patterns:

```python
# (a) existing CORE_PROFILE kind gaining full fields (path-policy + template + shortform)
EntityKind(
    name="hypothesis", canonical_prefix="hypothesis", layer="layer/core",
    description="Testable project hypothesis.",
    entity_class=EntityClass.EPISTEMIC, category=KindCategory.AUTHORED_CORE,
    template_ready=True, shortform="h",
    home="entities/hypotheses", strategy="numeric", default_status="proposed",
    statuses=["proposed", "under-investigation", "partially-supported", "supported", "weakened", "refuted"],
),
# (b) authored-core kind with NO path policy (operational/reference)
EntityKind(
    name="dataset", canonical_prefix="dataset", layer="layer/core",
    description="Tabular or file dataset tracked as a research artifact.",
    entity_class=EntityClass.OPERATIONAL, category=KindCategory.AUTHORED_CORE,
),
# (c) reserved sentinel
EntityKind(
    name="unknown", canonical_prefix="unknown", layer="layer/core",
    description="Built-in sentinel kind for unrecognized entities.",
    entity_class=EntityClass.REFERENCE, category=KindCategory.RESERVED,
),
# (d) singleton authored-core kind (file home, no status vocab)
EntityKind(
    name="research-question", canonical_prefix="research-question", layer="layer/core",
    description="The project's single guiding research question.",
    entity_class=EntityClass.EPISTEMIC, category=KindCategory.AUTHORED_CORE,
    home="entities/research-question.md", strategy="singleton",
),
```

Add `from science_model.identity import EntityClass` and `from science_model.profiles.schema import ... KindCategory` to `core.py` imports.

- [ ] **Step 4: Tag `LOCAL_PROFILE` source-only kinds**

In `science/model/src/science_model/profiles/local.py`, add **both** `category=KindCategory.SOURCE_ONLY` **and** `entity_class=EntityClass.OPERATIONAL` to all three `EntityKind`s (`model`, `canonical_parameter`, `parameter_binding`); add the `KindCategory` + `EntityClass` imports. `OPERATIONAL` is their current effective class — the `register_profile_kind(..., entity_class=EntityClass.OPERATIONAL)` default they register under today — so recording it on the descriptor is behavior-neutral and makes the descriptor the complete SSOT (design §4 "reserved/source-only carry one too"). No kinds moved.

Add a named-contract test to `science/model/tests/test_kind_reconciliation.py` (Task 3 file; or alongside, if writing Task 2 first):

```python
def test_source_only_descriptors_carry_operational_class() -> None:
    from science_model.identity import EntityClass
    for ek in LOCAL_PROFILE.entity_kinds:
        if ek.category == KindCategory.SOURCE_ONLY:
            assert ek.entity_class == EntityClass.OPERATIONAL, ek.name
```

> Scope note: this slice's *registry* `entity_class` flip (Task 6) rewires only `with_core_types` (CORE kinds). Source-only kinds register via the local-profile loader (`register_profile_kind`), which already defaults to `OPERATIONAL` — equal to the descriptor value pinned above — so no loader rewiring is needed and behavior is unchanged. The descriptor is now the recorded SSOT for their class; wiring the loader to *read* it is a trivial future follow-on, not required here.

- [ ] **Step 5: Register the two promoted map-only kinds (temporary, until Task 6)**

`decision` and `claim-registry` are authored-core descriptors but not yet registry kinds, so the gate's assertion 4 (registry ≡ manifest) would fail at Task 3 until they register. Add them via the **existing** mechanism in `science/src/science_tool/graph/entity_registry.py` so the gate is green after Task 2: add entries to `_CORE_KIND_CLASSES` (`"decision": EntityClass.REFERENCE`, `"claim-registry": EntityClass.OPERATIONAL` — matching the descriptor `entity_class` seeds) and add `"decision"`, `"claim-registry"` to the generic `for kind in (...)` loop in `with_core_types` (both register as `ProjectEntity`). Task 6 deletes `_CORE_KIND_CLASSES` and this loop wholesale, picking these two up from `CORE_PROFILE` instead — so this is transitional wiring, not duplicated SSOT.

- [ ] **Step 6: Run the recognition contract + nearby suites**

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest tests/test_kind_reconciliation_registry.py model/tests -q`
Expected: the recognition-delta test PASSES (delta == `INTENDED_ADDITIONS`); model suite green. If the delta differs, fix the `CORE_PROFILE` additions (not the test).

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/.worktrees/kind-descriptor-model-registry
rtk git add science/model/src/science_model/profiles/core.py science/model/src/science_model/profiles/local.py \
  science/model/src/science_model/entities.py science/src/science_tool/graph/entity_registry.py \
  science/tests/test_kind_reconciliation_registry.py
rtk git commit -m "feat(kinds): populate CORE_PROFILE descriptors, tag LOCAL_PROFILE, reconcile EntityType (+9), register promoted kinds"
```

---

## Task 3: Reconciliation drift gate (strict, split by layer)

**Files:**
- Create: `science/model/tests/test_kind_reconciliation.py` (assertions 1–3, model-package)
- Modify: `science/tests/test_kind_reconciliation_registry.py` (assertion 4, tool/root)

- [ ] **Step 1: Write the model-package gate (assertions 1–3)**

```python
# science/model/tests/test_kind_reconciliation.py
from __future__ import annotations

from science_model.entities import EntityType
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import KindCategory

RESERVED = frozenset({"unknown"})
SOURCE_ONLY = frozenset({"model", "canonical_parameter", "parameter_binding"})

_ALL = [*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds]
_CATEGORY = {ek.name: ek.category for ek in _ALL}


def _authored_core() -> set[str]:
    return {ek.name for ek in _ALL if ek.category == KindCategory.AUTHORED_CORE}


def test_assertion1_authored_core_equals_enum_core_projection() -> None:
    enum_core_projection = {v.value for v in EntityType} - RESERVED - SOURCE_ONLY
    # strict 3-way equality (enum side): every authored-core descriptor is an enum
    # member, and every non-reserved/non-source-only enum member is authored-core.
    assert _authored_core() == enum_core_projection


def test_assertion2_every_enum_member_is_classified() -> None:
    unclassified = {v.value for v in EntityType if _CATEGORY.get(v.value) is None}
    assert unclassified == set(), f"unclassified EntityType members: {sorted(unclassified)}"


def test_assertion3_reserved_named_contract() -> None:
    assert _CATEGORY["unknown"] == KindCategory.RESERVED
    assert "unknown" not in _authored_core()


def test_assertion3_source_only_named_contracts() -> None:
    for name in SOURCE_ONLY:
        assert _CATEGORY[name] == KindCategory.SOURCE_ONLY, name
        assert name not in _authored_core()
```

> If `test_assertion1` fails because a `EntityType` member has no descriptor, that member is unclassified — add its descriptor in Task 2 (do not weaken the gate). The strict 3-way equality is the point.

- [ ] **Step 2: Add assertion 4 (manifest ≡ registry) to the tool/root test**

Append to `science/tests/test_kind_reconciliation_registry.py`:

```python
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import KindCategory
from science_tool.graph.entity_registry import EntityRegistry

RESERVED = frozenset({"unknown"})


def test_assertion4_authored_core_equals_registry_core() -> None:
    registry = EntityRegistry.with_core_types()
    registered_core = registry.core_kinds()
    authored_core = {ek.name for ek in CORE_PROFILE.entity_kinds if ek.category == KindCategory.AUTHORED_CORE}
    # registry registers authored-core + the reserved sentinel(s)
    assert registered_core - RESERVED == authored_core
```

- [ ] **Step 3: Run the gate**

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest model/tests/test_kind_reconciliation.py tests/test_kind_reconciliation_registry.py -q`
Expected: PASS. Any failure means Task 2's data is incomplete — fix the descriptors.

- [ ] **Step 4: Commit**

```bash
cd ~/d/science/.worktrees/kind-descriptor-model-registry
rtk git add science/model/tests/test_kind_reconciliation.py science/tests/test_kind_reconciliation_registry.py
rtk git commit -m "test(kinds): strict reconciliation gate (descriptor ≡ registry ≡ EntityType core projection)"
```

---

## Task 4: Derive path policies + shortform map

**Files:**
- Create: `science/tests/test_kind_map_equivalence.py` (FROZEN fixtures + path/shortform equivalence)
- Modify: `science/src/science_tool/entities.py`

- [ ] **Step 1: Write the equivalence test (fixtures captured before the flip)**

Create `science/tests/test_kind_map_equivalence.py` with the FROZEN fixtures copied verbatim from `science/tests/test_kind_descriptor_derivation.py` (`FROZEN_MARKDOWN_POLICIES`, `FROZEN_SHORTFORM`, and — for Task 5 — `FROZEN_DEFAULT_STATUS`, `FROZEN_STATUS_VALUES`). Then:

```python
from science_tool.entities import (
    EntityPathPolicy,
    _BUILTIN_MARKDOWN_POLICIES,
    _SHORTFORM_ENTITY_KINDS,
)
# ... FROZEN_MARKDOWN_POLICIES, FROZEN_SHORTFORM pasted above ...


def test_markdown_policies_equal_prior_literal() -> None:
    assert _BUILTIN_MARKDOWN_POLICIES == FROZEN_MARKDOWN_POLICIES


def test_shortforms_equal_prior_literal() -> None:
    assert _SHORTFORM_ENTITY_KINDS == FROZEN_SHORTFORM
```

- [ ] **Step 2: Run it; expect PASS** (still derived from `CORE_KINDS` at this point — confirms the fixtures match the live maps before the flip)

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest tests/test_kind_map_equivalence.py -q`
Expected: PASS.

- [ ] **Step 3: Flip the derivations to `CORE_PROFILE`**

In `science/src/science_tool/entities.py`, add an import of the manifests and a combined descriptor list, then rewrite the two maps to derive by **field presence** (design §4). Replace the `_BUILTIN_MARKDOWN_POLICIES` and `_SHORTFORM_ENTITY_KINDS` definitions:

```python
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE

_KIND_DESCRIPTORS = (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)

_BUILTIN_MARKDOWN_POLICIES: dict[str, EntityPathPolicy] = {
    ek.name: EntityPathPolicy(Path(ek.home), ek.strategy)
    for ek in _KIND_DESCRIPTORS
    if ek.home is not None and ek.strategy is not None
}
# ... (existing caches / _CORE_HOME_DIR_NAMES unchanged) ...
_SHORTFORM_ENTITY_KINDS: dict[str, str] = {
    ek.shortform: ek.name for ek in _KIND_DESCRIPTORS if ek.shortform
}
```

Leave `_DEFAULT_STATUS`/`_STATUS_VALUES` still deriving from `CORE_KINDS` for now (Task 5). Keep the `from science_model.kinds import CORE_KINDS, EntityFilenameStrategy` import until Task 7.

- [ ] **Step 4: Run equivalence + path/status/migration suites**

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest tests/test_kind_map_equivalence.py tests/test_entities.py -q`
Expected: PASS (derived maps byte-identical to the frozen literals).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/kind-descriptor-model-registry
rtk git add science/src/science_tool/entities.py science/tests/test_kind_map_equivalence.py
rtk git commit -m "refactor(kinds): derive path policies + shortform map from CORE_PROFILE (field-presence)"
```

---

## Task 5: Derive status map + status vocab

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Modify: `science/tests/test_kind_map_equivalence.py` (add status equivalence)

- [ ] **Step 1: Add status equivalence tests** (FROZEN fixtures already pasted in Task 4):

```python
from science_tool.entities import _DEFAULT_STATUS, _STATUS_VALUES


def test_default_status_equals_prior_literal() -> None:
    assert _DEFAULT_STATUS == FROZEN_DEFAULT_STATUS


def test_status_values_equal_prior_literal() -> None:
    assert _STATUS_VALUES == FROZEN_STATUS_VALUES
```

- [ ] **Step 2: Run; expect PASS** (still `CORE_KINDS`-derived).

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest tests/test_kind_map_equivalence.py -q`

- [ ] **Step 3: Flip the status maps**

In `science/src/science_tool/entities.py` replace the `_DEFAULT_STATUS` / `_STATUS_VALUES` definitions:

```python
_DEFAULT_STATUS: dict[str, str] = {
    ek.name: ek.default_status for ek in _KIND_DESCRIPTORS if ek.default_status
}
_STATUS_VALUES: dict[str, frozenset[str]] = {
    ek.name: frozenset(ek.statuses) for ek in _KIND_DESCRIPTORS if ek.statuses
}
```

- [ ] **Step 4: Run equivalence + status-validation suites**

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest tests/test_kind_map_equivalence.py tests/test_entities.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/kind-descriptor-model-registry
rtk git add science/src/science_tool/entities.py science/tests/test_kind_map_equivalence.py
rtk git commit -m "refactor(kinds): derive default-status + status-vocab maps from CORE_PROFILE"
```

---

## Task 6: Derive MIGRATED_KINDS + registry entity_class

**Files:**
- Modify: `science/model/src/science_model/templates.py`
- Modify: `science/src/science_tool/graph/entity_registry.py`
- Modify: `science/tests/test_kind_map_equivalence.py` (MIGRATED_KINDS + registry entity_class equivalence)

- [ ] **Step 1: Add equivalence tests for MIGRATED_KINDS and registry classes**

```python
# in science/tests/test_kind_map_equivalence.py
from science_model.templates import MIGRATED_KINDS
from science_tool.graph.entity_registry import EntityRegistry

FROZEN_MIGRATED_KINDS = frozenset({
    "hypothesis", "question", "interpretation", "discussion", "theme", "proposition",
    "evidence-line", "finding", "method", "paper", "book", "pre-registration", "synthesis",
})
# The FULL post-Task-2 _CORE_KIND_CLASSES (all 48 core kinds, values as EntityClass
# .value strings). By Task 6, "current" _CORE_KIND_CLASSES already includes the two
# promoted kinds, so they MUST be in this fixture. Copy the dict verbatim, e.g.:
FROZEN_KIND_CLASSES = {
    "task": "operational", "dataset": "operational", "workflow-run": "operational",
    # ... all 46 original entries verbatim ...
    "decision": "reference", "claim-registry": "operational",  # the two promoted (Task 2)
}


def test_migrated_kinds_equal_prior_literal() -> None:
    assert set(MIGRATED_KINDS) == FROZEN_MIGRATED_KINDS


def test_registry_entity_class_equals_prior_literal() -> None:
    registry = EntityRegistry.with_core_types()
    live = {k: v.value for k, v in registry.all_kind_classes().items()}
    # with_core_types registers exactly the core kinds, so assert FULL equality
    # (not just pre-existing entries) against the post-Task-2 class map.
    assert live == FROZEN_KIND_CLASSES
```

> Capture `FROZEN_KIND_CLASSES` by copying the `_CORE_KIND_CLASSES` dict **as it exists after Task 2** (48 entries, including `decision`/`claim-registry`), values as `EntityClass.value` strings. Full equality is the authority that the descriptor-derived registry classes reproduce the hand map exactly.

- [ ] **Step 2: Run; expect PASS** (still hand-written).

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest tests/test_kind_map_equivalence.py -q`

- [ ] **Step 3: Derive `MIGRATED_KINDS` from the manifest**

In `science/model/src/science_model/templates.py`, replace the hand-written `MIGRATED_KINDS` literal with a derivation (no cycle — `profiles` does not import `templates`):

```python
from science_model.profiles.core import CORE_PROFILE

MIGRATED_KINDS: frozenset[str] = frozenset(
    ek.name for ek in CORE_PROFILE.entity_kinds if ek.template_ready
)
```

- [ ] **Step 4: Flip `with_core_types` to iterate descriptors; remove `_CORE_KIND_CLASSES`**

In `science/src/science_tool/graph/entity_registry.py`, replace the ~30 hand-written `register_core_kind(...)` calls and the `_CORE_KIND_CLASSES` dict with:

```python
    @classmethod
    def with_core_types(cls) -> "EntityRegistry":
        """Return a registry pre-populated with Science core kinds, read from the
        descriptor SSOT (CORE_PROFILE). Model class comes from CORE_KIND_MODELS;
        kinds without a typed subclass default to ProjectEntity."""
        r = cls()
        for ek in CORE_PROFILE.entity_kinds:
            if ek.category not in (KindCategory.AUTHORED_CORE, KindCategory.RESERVED):
                continue
            if ek.entity_class is None:
                raise ValueError(f"core kind {ek.name!r} has no entity_class in CORE_PROFILE")
            r.register_core_kind(ek.name, CORE_KIND_MODELS.get(ek.name, ProjectEntity), entity_class=ek.entity_class)
        return r
```

Add imports: `from science_model.profiles.core import CORE_PROFILE`, `from science_model.profiles.schema import KindCategory`. Delete the `_CORE_KIND_CLASSES` dict. (`register_core_kind`'s signature is unchanged — it still takes `entity_class`.)

> Registration order changes (manifest order vs the old hand order). Verify nothing depends on registration order (the registry is a dict keyed by name; `resolve`/`kind_class` are order-independent). The full suite is the guard.

- [ ] **Step 5: Run equivalence + registry + full model suites**

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest tests/test_kind_map_equivalence.py model/tests -q && uv run --frozen pytest tests -k "registry or entities or kind" -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/.worktrees/kind-descriptor-model-registry
rtk git add science/model/src/science_model/templates.py science/src/science_tool/graph/entity_registry.py science/tests/test_kind_map_equivalence.py
rtk git commit -m "refactor(kinds): derive MIGRATED_KINDS + registry entity_class from CORE_PROFILE; drop _CORE_KIND_CLASSES"
```

---

## Task 7: Delete `CORE_KINDS`, repoint imports, replace keystone tests

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Delete: `science/model/src/science_model/kinds.py`
- Delete: `science/model/tests/test_kinds.py`
- Delete: `science/tests/test_kind_descriptor_derivation.py`

- [ ] **Step 1: Repoint the tool import**

In `science/src/science_tool/entities.py`, change `from science_model.kinds import CORE_KINDS, EntityFilenameStrategy` to `from science_model.profiles.schema import EntityFilenameStrategy` (and remove the now-unused `CORE_KINDS` import — confirm with `rtk grep -n "CORE_KINDS" science/src/science_tool/entities.py` that it is no longer referenced).

- [ ] **Step 2: Confirm `CORE_KINDS` has no remaining references**

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry && rtk grep -n "CORE_KINDS\b\|science_model.kinds\|KindDescriptor" science/src science/model/src`
Expected: only matches inside `science/model/src/science_model/kinds.py` itself (about to be deleted). If anything else references it, fix that first.

- [ ] **Step 3: Delete the module + the superseded keystone tests**

```bash
cd ~/d/science/.worktrees/kind-descriptor-model-registry
rtk git rm science/model/src/science_model/kinds.py science/model/tests/test_kinds.py science/tests/test_kind_descriptor_derivation.py
```

> Coverage is not lost: the path/status/shortform maps are now pinned by `test_kind_map_equivalence.py`; descriptor self-consistency is pinned by the reconciliation gate (`test_kind_reconciliation*.py`).

- [ ] **Step 4: Full suite + ruff (the final gate)**

Run: `cd ~/d/science/.worktrees/kind-descriptor-model-registry/science && uv run --frozen pytest -q && uv run --frozen ruff check model/src/science_model src/science_tool`
Expected: full suite PASS (the existing ~5400-test suite covers the broad `EntityType`/registry consumers), ruff clean.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/kind-descriptor-model-registry
rtk git add -A
rtk git commit -m "refactor(kinds): delete transitional CORE_KINDS; EntityKind is the sole kind SSOT"
```

---

## Verification (whole-slice)

- [ ] `uv run --frozen pytest -q` (from `science/`) — full suite green.
- [ ] `uv run --frozen ruff check model/src/science_model src/science_tool` — clean.
- [ ] Reconciliation gate green: `model/tests/test_kind_reconciliation.py` + `tests/test_kind_reconciliation_registry.py`.
- [ ] Equivalence green: `tests/test_kind_map_equivalence.py` (5 maps + registry classes).
- [ ] `rtk grep -rn "CORE_KINDS\|science_model.kinds\|_CORE_KIND_CLASSES" science/` returns nothing (manifest is the sole SSOT).
- [ ] `EntityType` has the 9 new members; `from science_model.entities import EntityClass` still resolves.

## Self-review notes (author)

- **Spec coverage:** Task 1 ↔ design §2.1/§2.2/§2.4; Task 2 ↔ §3/§3.1 + §5 (EntityType +9) + §3 additive-`_CORE_KINDS` note; Task 3 ↔ §3 assertions 1–4; Tasks 4–6 ↔ §4 derivations + per-flip equivalence; Task 7 ↔ §0.1 (delete `CORE_KINDS`, repoint Literal, replace keystone tests). The core-kind recognition contract (§7) is in Task 2.
- **Field-presence vs category:** every derived map filters on populated fields (`home`+`strategy`, `default_status`, `statuses`, `shortform`, `template_ready`), never on `category`; `category` is used only by the gate. This is what keeps the flips value-for-value identical (design §0.1/§4).
- **TDD shape for a transcription slice:** Tasks 4–6 write the frozen-fixture equivalence test first (PASS while still `CORE_KINDS`-derived), then flip the source and re-assert — so any transcription error in Task 2 surfaces as a red equivalence/gate test, not a silent behavior change.
- **One non-byte-identical change** (`sources.py::_CORE_KINDS` growth) is isolated to Task 2 and pinned by an explicit delta test + full suite.

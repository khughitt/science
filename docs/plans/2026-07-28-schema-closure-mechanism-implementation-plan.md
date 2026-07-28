# Schema Closure Mechanism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "is kind K schema-checked?" a single declaration on `EntityKind`, derive every consumer from it, and close the load paths that can reach a schema-closed kind without validating first.

**Architecture:** `EntityKind` gains `schema_closed: bool`, declared explicitly on all 53 shipped kinds. `PROJECT_MIXIN_NAMES` becomes derived from it, so arming a kind is one edit. Four gates compare that declaration against independently hand-authored artifacts. The structured-source path stops discarding unknown keys before validation, and entity construction is funnelled through one `registry.build` operation whose exclusivity is enforced by an AST guard over the *import surface*.

**Tech Stack:** Python 3.13, Pydantic v2, jsonschema, pytest, uv.

Design: [`meta/doc/plans/2026-07-26-schema-first-closure-design.md`](../../meta/doc/plans/2026-07-26-schema-first-closure-design.md) — §3 (declaration and gates), §4.3 (`promoted_from` ruling), §6 (testing). Read §3 before Task 1.

**This plan is the MECHANISM only.** It closes **no kind**. `hypothesis` remains the only `schema_closed=True` kind when this branch merges, and `PROJECT_MIXIN_NAMES` must still evaluate to exactly `{"hypothesis"}` — see Task 1 Step 6. The five kind slices (`concept`, `method`, `search`, `finding`, `observation`) follow as **five separate branches**, per the procedure Task 8 writes.

### Why the slices are not in this plan

Design §7 describes plan 2 as "mechanism … then five atomic kind slices." Design §4.0 rules that **"atomicity is defined at merge scope: one kind's slice is one branch, merged as a unit and never released in parts,"** and prohibits partial release. Both cannot hold in a single branch. §4.0 governs, because it is the specific ruling and it is the one carrying the stated failure mode ("a branch that merges steps 1–6 without step 7 leaves templates and writers emitting a declared field set that nothing enforces"). This plan therefore delivers the mechanism plus the repeatable slice procedure; each slice is its own branch.

## Global Constraints

- **Working directories.** CLI/tool work runs from `science/`; model work runs from `science/model/`. There is **no root `pyproject.toml`** — running `uv run` from the repo root is the most common orientation mistake here.
- **Test commands.** `cd science && uv run --frozen pytest` and `cd science/model && uv run --frozen pytest`. Never run two suites concurrently in the same worktree — they race on shared test-output paths.
- **The full `science/` suite takes ~2-3 min**, longer than the default 120s command timeout. Run scoped selections; reserve the full run for the top-level agent.
- **Lint/types.** `uv run ruff check` from the package you changed; `uv run pyright` from `science/` (one root config governs all three source trees).
- **Conventional commits. No AI-attribution trailer or footer** on commits, PRs, or comments.
- **Composition over inheritance; explicit over defensive; fail early instead of silent fallbacks. No "legacy"/"compatibility" layers. No `Unified` prefix.**
- **Use `~/d/` or relative paths in docs and code**, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **This branch closes no kind.** Any step that would set `schema_closed=True` on a kind other than `hypothesis` is out of scope and must be refused.
- **A gate must compare against an independently hand-authored artifact.** `PROJECT_MIXIN_NAMES == {k for k in kinds if k.schema_closed}` is the identity function once one derives from the other, and asserting it proves nothing. Every gate here compares the declaration against a *separately authored* surface — a generation row, a file on disk, a descriptor field.
- **Explicit `false` is reserved** (design §4.2) for base-admitted fields a kind narrows away and for tested tombstones. The 231-key shadow schema does **not** become a deny list.

## Verified starting state

Measured on `main` at `bbff18fd` before writing this plan. An implementer who finds any of these false should stop and report rather than adapt:

| fact | value |
|---|---|
| shipped kinds | **53** — 50 in `CORE_PROFILE`, 3 in `LOCAL_PROFILE` |
| `PROJECT_MIXIN_NAMES` today | `frozenset({"hypothesis"})`, hand-authored at `entity_schema/profile.py:24` |
| `set(row) - COMMONS_MIXIN_NAMES` | `{"hypothesis"}` for **both** generations 2 and 3 |
| tranche descriptors | all five of `concept`/`method`/`search`/`finding`/`observation` already declare `entity_class` **and** `home`, so gate 4 is pre-satisfied for them |
| import cycle risk | **none** — `profiles/` does not import `entity_schema`, and `entity_schema/profile.py` imports nothing from the package |
| dormant mixin files | `dataset-1.0`, `paper-1.0`, `theme-1.0`, `topic-1.0` exist on disk armed by no row — gate 2 must be forward-only |

**Design citations that have drifted** — use these corrected locations:

| design says | actual |
|---|---|
| `entity_kinds.py:125` (manifest validation) | `science/src/science_tool/entity_kinds.py:126` |
| `EntityKind` in `entity_kinds.py` | `science/model/src/science_model/profiles/schema.py:23` |
| `sources.py:457` (`_validate_against_schema` call) | `science/src/science_tool/graph/sources.py:412` (definition at `:1401`) |
| `sources.py:1306` (load gate) | `sources.py:1428`, inside `_validate_against_schema` |
| `source_contracts.py:71` | `science/model/src/science_model/source_contracts.py:71` — correct (`model_config = ConfigDict(extra="ignore")`) |
| `entity_registry.py:189` (`resolve`) | correct |
| `decision_log.py:157` (`promoted_from` write) | correct |
| entity-producing sites `:489`, `:998`, `:1038`, `:1126` | now `sources.py:404`, `:1119`, `:1150`, `:1216`, plus `commons_sources.py:395` |
| `migrate_hypothesis.py:77` under a `migrations/` dir | `science/src/science_tool/migrate_hypothesis.py:77` — directly under `science_tool/`; line correct |

**`EntityKind.entity_class` is a classification, not a class reference.** It holds an `EntityClass` enum member (`reference` / `operational` / `epistemic`). Only 21 kinds have a concrete `*Entity` Python class, and `concept` is not one of them — gate 4 asks for the descriptor field, never for a dedicated model class.

## File Structure

| File | Responsibility in this change |
|---|---|
| `science/model/src/science_model/profiles/schema.py` | `EntityKind.schema_closed`; `ProfileManifest` rejects the field from external manifests |
| `science/model/src/science_model/profiles/core.py`, `local.py` | explicit `schema_closed=` on all 53 shipped kinds |
| `science/model/src/science_model/entity_schema/profile.py` | `PROJECT_MIXIN_NAMES` becomes derived |
| `science/model/tests/test_schema_closed_gate.py` | **new** — explicit declaration, gates 1, 2, 4, commons standing assertion, manifest rejection |
| `science/model/src/science_model/source_contracts.py` | `StructuredEntitySource` becomes `extra="allow"` |
| `science/src/science_tool/graph/source_normalization.py` | **new** — the declared key mapping and declared drop set |
| `science/src/science_tool/graph/entity_registry.py` | `build(kind, raw, *, project_schema, path)` replaces handing out the class |
| `science/src/science_tool/graph/sources.py`, `commons_sources.py` | all five producing sites route through `registry.build` |
| `science/tests/test_entity_construction_boundary.py` | **new** — gate 3: behavioural checks plus the import-surface AST guard |
| `science/tests/test_schema_closure_mutations.py` | **new** — mutation matrix rows 1–8 |
| `docs/conventions/schema-closure-slice-procedure.md` | **new** — the repeatable per-kind slice procedure |

---

### Task 1: Declare `schema_closed`, derive `PROJECT_MIXIN_NAMES`

**Files:**
- Modify: `science/model/src/science_model/profiles/schema.py:23-53`
- Modify: `science/model/src/science_model/profiles/core.py`, `science/model/src/science_model/profiles/local.py`
- Modify: `science/model/src/science_model/entity_schema/profile.py:20-26`
- Test: `science/model/tests/test_schema_closed_gate.py` (new)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `EntityKind.schema_closed: bool`; `PROJECT_MIXIN_NAMES` derived over `CORE_PROFILE` + `LOCAL_PROFILE`; the module-level `SHIPPED_KINDS` tuple in the new test file, which Tasks 2 and 3 import.

- [ ] **Step 1: Add the field to `EntityKind`**

In `profiles/schema.py`, directly below the `supersedable` declaration (which is the precedent this follows):

```python
    # Schema-first closure: does this kind validate through a COMPOSED entity profile with
    # `unevaluatedProperties: false`? DECLARED per kind. `PROJECT_MIXIN_NAMES` derives from this,
    # so flipping it to True arms strictness, Markdown load validation, write-boundary validation
    # and `strict_schema_kinds` in ONE edit -- there is deliberately no separate strictness switch.
    # Defaults False because project-authored manifest kinds validate through this same model and
    # must not be forced to declare; a test asserts every SHIPPED kind sets it explicitly, so a
    # shipped kind that merely FORGOT is distinguishable from one ruled open. A project manifest
    # that authors it is REJECTED (see ProfileManifest) -- a project cannot install a packaged
    # type mixin, so honouring the field there would be a claim the toolkit cannot make true.
    schema_closed: bool = False
```

- [ ] **Step 2: Declare it explicitly on all 53 shipped kinds**

Add `schema_closed=False` to every `EntityKind(...)` in `core.py` and `local.py`, **except** `hypothesis`, which gets `schema_closed=True`. Place it adjacent to `supersedable=` on each entry so the two capability declarations read together.

This is 53 mechanical edits. Do not use a default to avoid them — the explicitness is the point, and Step 5's gate enforces it.

- [ ] **Step 3: Run the declaration count**

```bash
cd science/model && uv run --frozen python -c "
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
s=[*CORE_PROFILE.entity_kinds,*LOCAL_PROFILE.entity_kinds]
missing=[k.name for k in s if 'schema_closed' not in k.model_fields_set]
print('shipped:',len(s),'undeclared:',missing)
print('closed:',sorted(k.name for k in s if k.schema_closed))
"
```
Expected: `shipped: 53 undeclared: []` and `closed: ['hypothesis']`.

- [ ] **Step 4: Derive `PROJECT_MIXIN_NAMES`**

In `entity_schema/profile.py`, replace the hand-authored frozenset at line 24. Keep `COMMONS_MIXIN_NAMES` and `TYPE_MIXIN_NAMES` exactly as they are.

```python
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE

# Project-authored kinds converging onto the same schema system (base 2.0). DERIVED from the
# per-kind `schema_closed` declaration, over the BUILT-IN profiles only -- a project cannot arm
# strictness for itself. This set still gates BOTH schema strictness (`unevaluatedProperties:
# false`) and load enforcement, deliberately: `sources.py` explains that splitting them is how a
# green check over an unchecked record becomes possible.
PROJECT_MIXIN_NAMES: frozenset[str] = frozenset(
    kind.name
    for kind in (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)
    if kind.schema_closed
)
```

Verified before writing this plan: `profiles/` does not import `entity_schema`, so this introduces no cycle.

- [ ] **Step 5: Write the explicit-declaration gate**

Create `science/model/tests/test_schema_closed_gate.py`:

```python
"""Schema closure: ONE declaration, and the surfaces that must agree with it.

`EntityKind.schema_closed` answers "does this kind validate through a composed profile with
`unevaluatedProperties: false`?" `PROJECT_MIXIN_NAMES` DERIVES from it, so asserting the two agree
would be the identity function. Every gate here therefore compares the declaration against an
INDEPENDENTLY HAND-AUTHORED artifact -- a generation row, a file on disk, a descriptor field --
each of which can genuinely disagree.
"""

from __future__ import annotations

import pytest

from science_model.entity_schema.profile import (
    BASE_NAME,
    COMMONS_MIXIN_NAMES,
    PROJECT_MIXIN_NAMES,
    _BASE_VERSION_FOR_MIXIN,
    _MIXIN_VERSION_BY_GENERATION,
)
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import EntityKind

SHIPPED_KINDS: tuple[EntityKind, ...] = (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)


def test_every_shipped_kind_declares_schema_closed() -> None:
    # `model_fields_set` -- NOT the value. The False default is what keeps project-authored
    # manifest kinds inert, which means a shipped kind that merely forgot to declare would
    # otherwise be indistinguishable from one deliberately ruled open. Presence is the only
    # thing separating them.
    undeclared = sorted(k.name for k in SHIPPED_KINDS if "schema_closed" not in k.model_fields_set)
    assert not undeclared, f"shipped kinds not declaring schema_closed: {undeclared}"


def test_the_shipped_population_is_53() -> None:
    # Pins the population the other gates range over. A kind added without a ruling fails here
    # first, with a clearer message than a downstream equality.
    assert len(SHIPPED_KINDS) == 53
```

- [ ] **Step 6: Assert the mechanism closed nothing**

Append to the same file:

```python
def test_this_mechanism_closes_NO_new_kind() -> None:
    # The mechanism branch must be behaviourally inert: it changes HOW the answer is derived, not
    # WHAT it is. If this fails, a kind was closed without its atomic slice (design 4.0), which is
    # the partial release the design prohibits.
    assert PROJECT_MIXIN_NAMES == frozenset({"hypothesis"})
```

- [ ] **Step 7: Run the model suite scoped**

```bash
cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py tests/test_value_reconciliation.py tests/test_hypothesis_entity.py -q
```
Expected: PASS. Then run the whole model suite (it is fast): `uv run --frozen pytest -q`.

- [ ] **Step 8: Check the tool side still sees the same set**

```bash
cd science && uv run --frozen pytest tests/test_kind_reconciliation.py tests/test_kind_reconciliation_registry.py tests/test_hypothesis_schema_reconciliation.py -q
```
Expected: PASS, unchanged. These read `PROJECT_MIXIN_NAMES` and are the blast radius of Step 4.

- [ ] **Step 9: Lint, types, commit**

```bash
cd science/model && uv run ruff check
cd .. && uv run pyright
git add science/model/src/science_model/profiles/schema.py science/model/src/science_model/profiles/core.py science/model/src/science_model/profiles/local.py science/model/src/science_model/entity_schema/profile.py science/model/tests/test_schema_closed_gate.py
git commit -m "feat(entity-schema): declare schema_closed per kind and derive PROJECT_MIXIN_NAMES"
```

---

### Task 2: Reject `schema_closed` from external manifests

**Files:**
- Modify: `science/model/src/science_model/profiles/schema.py` (`ProfileManifest`)
- Test: `science/model/tests/test_schema_closed_gate.py` (extend)

**Interfaces:**
- Consumes: `EntityKind.schema_closed` from Task 1.
- Produces: a `ProfileManifest` before-validator that raises on the reserved field; nothing later depends on its name.

**Why one site suffices.** There are two external manifest entry points — `profiles/__init__.py:load_profile_manifest` (model) and `entity_kinds.py:126` `_validate_manifest_shape` (tool). **Both** end in `ProfileManifest.model_validate(<dict parsed from YAML>)`. The packaged profiles are *constructed* in Python (`ProfileManifest(...)` with `EntityKind` instances). A `mode="before"` validator can therefore distinguish them, which was **verified empirically** before this plan was written: on the packaged path the validator sees `EntityKind` instances in `entity_kinds`; on the external path it sees `dict`s. One rule at one site covers both loaders and cannot fire on packaged profiles.

- [ ] **Step 1: Write the failing test**

Append to `science/model/tests/test_schema_closed_gate.py`:

```python
from pydantic import ValidationError

from science_model.profiles.schema import ProfileManifest

_MINIMAL_EXTERNAL = {
    "name": "project-local",
    "imports": [],
    "relation_kinds": [],
    "strictness": "typed-extension",
}


def _external(kind: dict) -> dict:
    return {**_MINIMAL_EXTERNAL, "entity_kinds": [kind]}


_BASE_KIND = {
    "name": "widget",
    "canonical_prefix": "widget",
    "layer": "local",
    "description": "a project-local kind",
}


def test_an_external_manifest_may_NOT_author_schema_closed() -> None:
    # REJECTED, not ignored. A project cannot install a packaged type mixin, so honouring this
    # would be a claim the toolkit cannot make true -- and silently ignoring it is exactly the
    # fail-silent this programme abolishes.
    with pytest.raises(ValidationError, match="schema_closed"):
        ProfileManifest.model_validate(_external({**_BASE_KIND, "schema_closed": True}))


def test_an_external_manifest_may_not_author_schema_closed_FALSE_either() -> None:
    # Even the inert value is refused: accepting `false` would teach authors the key is theirs to
    # set, and the next edit flips it.
    with pytest.raises(ValidationError, match="schema_closed"):
        ProfileManifest.model_validate(_external({**_BASE_KIND, "schema_closed": False}))


def test_an_external_manifest_without_the_field_still_loads() -> None:
    manifest = ProfileManifest.model_validate(_external(dict(_BASE_KIND)))
    assert manifest.entity_kinds[0].schema_closed is False
    assert "schema_closed" not in manifest.entity_kinds[0].model_fields_set


def test_the_packaged_profiles_are_UNAFFECTED_by_the_rejection() -> None:
    # The packaged profiles construct EntityKind instances directly rather than validating raw
    # mappings, which is what makes one before-validator able to serve both external loaders
    # without touching them. If this ever fails, the rejection has become over-broad and the
    # 53 explicit declarations are what it will reject.
    assert any(k.schema_closed for k in SHIPPED_KINDS)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q -k "external or packaged"
```
Expected: the three `external` tests FAIL (no rejection exists yet — the first two because no error is raised, the third passes already); `packaged` passes.

- [ ] **Step 3: Implement the rejection**

In `profiles/schema.py`, add to `ProfileManifest`:

```python
from collections.abc import Mapping
from typing import Any

from pydantic import model_validator

# Fields the toolkit rules, which an externally loaded manifest may not author. A project cannot
# install a packaged type mixin, so it cannot arm schema closure for itself.
_TOOLKIT_RESERVED_KIND_FIELDS = frozenset({"schema_closed"})


class ProfileManifest(BaseModel):
    ...

    @model_validator(mode="before")
    @classmethod
    def _refuse_toolkit_reserved_fields(cls, data: Any) -> Any:
        """Refuse toolkit-ruled kind fields authored by an EXTERNAL manifest.

        Both external entry points (`load_profile_manifest` and the tool's
        `_validate_manifest_shape`) reach us through `model_validate` on a mapping parsed from
        YAML, so their entity_kinds entries arrive as `Mapping`. The packaged profiles construct
        `EntityKind` instances directly, so theirs do not -- which is exactly what lets one rule
        here serve both loaders without touching the 53 shipped declarations.
        """
        if not isinstance(data, Mapping):
            return data
        for entry in data.get("entity_kinds") or ():
            if not isinstance(entry, Mapping):
                continue  # a constructed EntityKind: packaged, not external
            reserved = _TOOLKIT_RESERVED_KIND_FIELDS & set(entry)
            if reserved:
                name = entry.get("name", "<unnamed>")
                msg = (
                    f"entity_kinds[{name!r}] may not author {sorted(reserved)}: these are ruled by "
                    "the toolkit. A project cannot install a packaged type mixin, so it cannot arm "
                    "schema closure for its own kinds."
                )
                raise ValueError(msg)
        return data
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q
```
Expected: PASS.

- [ ] **Step 5: Verify both real loaders reject, not just the model**

The tests above call `model_validate` directly. Prove the rejection reaches the two real entry points:

```bash
cd science && uv run --frozen python -c "
import tempfile, pathlib, yaml
from science_model.profiles import load_profile_manifest
d = pathlib.Path(tempfile.mkdtemp())
p = d / 'profile.yaml'
p.write_text(yaml.safe_dump({'name':'x','imports':[],'relation_kinds':[],'strictness':'typed-extension',
  'entity_kinds':[{'name':'widget','canonical_prefix':'widget','layer':'local','description':'d','schema_closed':True}]}))
try:
    load_profile_manifest(p); print('MODEL LOADER: NOT REJECTED -- defect')
except Exception as e: print('MODEL LOADER rejected:', str(e)[:80])
"
```
Expected: `MODEL LOADER rejected: ...`. Record the tool-side path (`entity_kinds.py:126`) as covered by the same `model_validate` call; if the implementer finds it does **not** go through `ProfileManifest.model_validate`, stop and report — the single-site premise is then false.

- [ ] **Step 6: Lint, types, commit**

```bash
cd science/model && uv run ruff check
cd .. && uv run pyright
git add science/model/src/science_model/profiles/schema.py science/model/tests/test_schema_closed_gate.py
git commit -m "feat(profiles): refuse toolkit-reserved kind fields in external manifests"
```

---

### Task 3: Gates 1, 2 and 4

**Files:**
- Test: `science/model/tests/test_schema_closed_gate.py` (extend)

**Interfaces:**
- Consumes: `SHIPPED_KINDS`, `PROJECT_MIXIN_NAMES`, `_MIXIN_VERSION_BY_GENERATION`, `_BASE_VERSION_FOR_MIXIN` from Task 1.
- Produces: gates the Task 7 mutation matrix targets by name.

**These are the gates that can genuinely disagree.** Each compares the declaration against a hand-authored artifact: a generation row (authored in `profile.py`), a file on disk, a descriptor field.

- [ ] **Step 1: Write gate 1 — generation-row equality, per generation, commons excluded**

```python
def test_GATE_1_every_generation_row_matches_the_closed_declaration() -> None:
    # Commons mixins (dataset/paper/theme/topic) appear in every row but stay OPEN and pin base
    # 1.0, so they must not force schema_closed=True. Exact equality gives both directions: a
    # closed kind missing from a row fails, and a project mixin in a row with no closed
    # declaration fails. A kind closed in gen 2 but absent from gen 3 would raise
    # ProfileParseError at load for every gen-3 project -- a real failure this catches.
    declared = {k.name for k in SHIPPED_KINDS if k.schema_closed}
    for generation, row in _MIXIN_VERSION_BY_GENERATION.items():
        project_entries = set(row) - COMMONS_MIXIN_NAMES
        assert project_entries == declared, (
            f"generation {generation}: in the row but not declared closed: "
            f"{sorted(project_entries - declared)}; declared closed but missing from the row: "
            f"{sorted(declared - project_entries)}"
        )


def test_GATE_1_commons_kinds_are_represented_in_every_generation_row() -> None:
    # The standing assertion that keeps gate 1's commons EXCLUSION from quietly becoming a hole:
    # if a commons kind vanished from a row, the exclusion above would silently stop covering it.
    for generation, row in _MIXIN_VERSION_BY_GENERATION.items():
        missing = COMMONS_MIXIN_NAMES - set(row)
        assert not missing, f"generation {generation} omits commons kinds: {sorted(missing)}"
```

- [ ] **Step 2: Write gate 2 — armed components resolve, forward only**

```python
from importlib.resources import files


def _packaged_schema_names() -> set[str]:
    return {p.name for p in files("science_model.schemas").iterdir() if p.name.endswith(".json")}


def test_GATE_2_every_ARMED_component_resolves_to_a_packaged_file() -> None:
    # Deliberately NOT biconditional. Schema files are versioned artifacts and a dormant
    # historical or staged version may legitimately sit on disk -- four do today
    # (dataset-1.0, paper-1.0, theme-1.0, topic-1.0), armed by no row. A raw mixin-*.json scan
    # used as the reverse authority would have failed on day one.
    available = _packaged_schema_names()
    for generation, row in _MIXIN_VERSION_BY_GENERATION.items():
        for kind, version in row.items():
            expected = f"mixin-{kind}-{version}.json"
            assert expected in available, (
                f"generation {generation} arms {kind}/{version} but {expected} is not packaged"
            )


def test_GATE_2_every_closed_kind_pins_base_2_0() -> None:
    # `_BASE_VERSION_FOR_MIXIN` is a third hand-maintained surface. Base 1.0 enum-locks `kind` to
    # the four commons kinds and an allOf can only narrow, so a closed project kind pinned to
    # base 1.0 is structurally unvalidatable rather than merely wrong.
    for name in PROJECT_MIXIN_NAMES:
        assert _BASE_VERSION_FOR_MIXIN[name] == "2.0", f"{name} is closed but does not pin base 2.0"
```

- [ ] **Step 3: Write gate 4 — descriptor prerequisites (one-way implication)**

```python
def test_GATE_4_a_closed_kind_declares_entity_class_and_home() -> None:
    # An IMPLICATION, not an equality: many deliberately open kinds already declare both. A kind
    # with no `home` cannot be located in order to be validated.
    for kind in SHIPPED_KINDS:
        if not kind.schema_closed:
            continue
        assert kind.entity_class is not None, f"{kind.name} is closed but declares no entity_class"
        assert kind.home is not None, f"{kind.name} is closed but declares no home"
```

- [ ] **Step 4: Run the gates**

```bash
cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q
```
Expected: PASS. If gate 2's base-2.0 assertion fails, stop — `_BASE_VERSION_FOR_MIXIN` disagreeing with the declaration is a real finding, not a test to adjust.

- [ ] **Step 5: Lint, types, commit**

```bash
cd science/model && uv run ruff check
cd .. && uv run pyright
git add science/model/tests/test_schema_closed_gate.py
git commit -m "test(entity-schema): add gates 1, 2 and 4 over the schema_closed declaration"
```

---

### Task 4: Stop discarding unknown keys before validation

**Files:**
- Modify: `science/model/src/science_model/source_contracts.py:71`
- Create: `science/src/science_tool/graph/source_normalization.py`
- Modify: `science/src/science_tool/graph/sources.py:1167-1260` (`_load_structured_source_records`)
- Test: `science/tests/test_entity_construction_boundary.py` (new)

**Interfaces:**
- Consumes: nothing from Tasks 1–3.
- Produces: `normalize_structured_row(row: Mapping[str, Any]) -> dict[str, Any]`, `STRUCTURED_KEY_MAPPING`, `STRUCTURED_DROP_KEYS` — all imported by Task 5.

**The defect being closed.** `StructuredEntitySource` is `extra="ignore"`, so on the structured path unknown keys are gone at `_load_typed_records` — *before* the mapping the entity is built from is even assembled. Validating at the construction site would inspect a mapping the toolkit itself just assembled: a check that can only ever pass. The required order is: **lossless source-contract validation → normalization → composed entity-schema validation → Pydantic projection.**

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_entity_construction_boundary.py`:

```python
"""Gate 3: every load path that can emit a schema-closed kind validates BEFORE projection.

The Markdown adapter is not the only path. The structured-source loader builds entities from a
mapping it assembles itself, so a check placed there inspects the toolkit's own output. These
tests pin the ORDER -- lossless parse, declared normalization, composed validation, projection --
because a check downstream of a lossy step validates the loss, not the input.
"""

from __future__ import annotations

import pytest

from science_model.source_contracts import StructuredEntitySource


def test_an_unknown_key_SURVIVES_the_source_contract() -> None:
    # extra="allow", not "ignore". This is what lets a shadow key reach schema validation at all.
    # extra="forbid" is rejected as the alternative: every existing row carries `kind`, which the
    # loader legitimately ignores, so forbidding would reject the whole corpus for a key the
    # design agrees is fine.
    record = StructuredEntitySource.model_validate(
        {"canonical_id": "finding:0001-x", "shadow_key": "value"}
    )
    assert record.model_extra == {"shadow_key": "value"}


def test_only_AUTHORED_keys_are_normalized() -> None:
    # The declared fields still DEFAULT (title="", profile="", source_path="", five empty lists).
    # Normalizing from the parsed record would promote those defaults into the mapping that gets
    # schema-validated -- an absent title would arrive as "" and fail minLength: 1, and an absent
    # evidence_refs would arrive as [] and read as an authored empty list.
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row({"canonical_id": "finding:0001-x"})
    assert normalized == {"id": "finding:0001-x"}
    assert "title" not in normalized
    assert "evidence_refs" not in normalized


def test_the_declared_key_mapping_is_applied() -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row(
        {"canonical_id": "finding:0001-x", "source_path": "knowledge/sources/x.yaml"}
    )
    assert normalized["id"] == "finding:0001-x"
    assert normalized["file_path"] == "knowledge/sources/x.yaml"
    assert "canonical_id" not in normalized
    assert "source_path" not in normalized


def test_kind_is_the_only_declared_DROP() -> None:
    # `kind` is authoritative from the manifest and deliberately ignored on the row, so it is a
    # legitimately dropped key rather than a shadow field. A drop that is not DECLARED is
    # indistinguishable from a bug, which is the whole reason this set is written down.
    from science_tool.graph.source_normalization import STRUCTURED_DROP_KEYS

    assert STRUCTURED_DROP_KEYS == frozenset({"kind"})


def test_a_shadow_key_reaches_the_normalized_mapping() -> None:
    from science_tool.graph.source_normalization import normalize_structured_row

    normalized = normalize_structured_row({"canonical_id": "finding:0001-x", "shadow_key": "v"})
    assert normalized["shadow_key"] == "v", "a shadow key must survive to be REFUSED downstream"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q
```
Expected: FAIL — `model_extra` is `{}` (extra="ignore"), and `science_tool.graph.source_normalization` does not exist.

- [ ] **Step 3: Make the source contract lossless**

In `science/model/src/science_model/source_contracts.py`, change line 71 and amend the docstring's "other unrecognized fields are ignored" sentence, which becomes false:

```python
    # extra="ALLOW", deliberately. Unknown keys must survive the source-contract parse so the
    # composed entity schema can refuse them; dropping here would put the loss UPSTREAM of the
    # check, making the check one that can only ever pass. `forbid` is wrong for the opposite
    # reason: every existing row carries `kind`, which the loader legitimately ignores, so it
    # would reject the whole corpus for a key that is fine.
    model_config = ConfigDict(extra="allow")
```

- [ ] **Step 4: Write the normalization module**

Create `science/src/science_tool/graph/source_normalization.py`:

```python
"""The declared normalization between a structured source row and an entity mapping.

Named and declared rather than inline, because a drop that is not declared is indistinguishable
from a bug. This ran as anonymous dict-building inside the structured loader; the schema check
that now follows it is only meaningful if what it lost is written down.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Authored key -> entity-schema key. The row authors `canonical_id`/`source_path`; the entity
# schema expects normalized `id`/`file_path`.
STRUCTURED_KEY_MAPPING: dict[str, str] = {
    "canonical_id": "id",
    "source_path": "file_path",
}

# Keys deliberately dropped. `kind` is authoritative from the manifest declaration and ignored on
# the row. Nothing else may join this set without a written ruling in the design.
STRUCTURED_DROP_KEYS: frozenset[str] = frozenset({"kind"})


def normalize_structured_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Map a raw structured-source row onto entity-schema keys, preserving AUTHORED keys only.

    Ranges over what the author actually wrote -- never over a parsed record's defaults. The
    declared fields of `StructuredEntitySource` all default (`title=""`, five empty lists), so
    normalizing from the parsed object would promote those defaults into the mapping that gets
    schema-validated: an absent `title` would arrive as `""` and fail `minLength: 1`, and an
    absent `evidence_refs` would arrive as `[]` and read as an authored empty list. The loader's
    own backfills stay explicit and separately testable downstream of this.
    """
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if key in STRUCTURED_DROP_KEYS:
            continue
        normalized[STRUCTURED_KEY_MAPPING.get(key, key)] = value
    return normalized
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q
```
Expected: PASS.

- [ ] **Step 6: Route the structured loader through it**

In `sources.py`, `_load_structured_source_records` (around `:1216-1250`) currently builds the entity mapping inline and calls `schema.model_validate(raw)`. Replace the inline dict-building with `normalize_structured_row` applied to the **original row mapping**, not to the parsed `StructuredEntitySource`. Retain the loader's explicit backfills (e.g. `title or canonical_id`) as separate, clearly named steps *after* normalization — they are loader policy, not source content.

Leave the `schema.model_validate(...)` call in place for now; Task 5 replaces it with `registry.build`.

- [ ] **Step 7: Run the structured-source suite**

```bash
cd science && uv run --frozen pytest -q -k "structured_source or structured or sources" 2>&1 | tail -5
```
Expected: PASS. If a test asserts an unknown key is silently dropped, that expectation is now **wrong by design** — repair it to assert the key survives, and record it in your report. Do not relax it.

- [ ] **Step 8: Lint, types, commit**

```bash
cd science/model && uv run ruff check
cd .. && uv run ruff check && uv run pyright
git add science/model/src/science_model/source_contracts.py science/src/science_tool/graph/source_normalization.py science/src/science_tool/graph/sources.py science/tests/test_entity_construction_boundary.py
git commit -m "feat(sources): make the structured source contract lossless and declare its normalization"
```

---

### Task 5: One construction choke point

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py:189`
- Modify: `science/src/science_tool/graph/sources.py:404`, `:1119`, `:1150`, `:1216`
- Modify: `science/src/science_tool/graph/commons_sources.py:395`
- Test: `science/tests/test_entity_construction_boundary.py` (extend)

**Interfaces:**
- Consumes: `normalize_structured_row` from Task 4.
- Produces: `EntityRegistry.build(kind: str, raw: Mapping[str, Any], *, project_schema: ProjectSchema | None, path: Path | None = None) -> Entity`. Task 6's AST guard depends on `resolve` no longer being the way callers obtain a class.

**Why `resolve` is the hole.** `EntityRegistry.resolve(kind)` returns `type[Entity]`. Handing out the class means any adapter — present or future — can construct an entity without validating. An AST rule over `.model_validate(...)` is defeated by a constructor call, a `TypeAdapter`, or any other spelling. Merging resolution and construction into one operation is what makes the guard enforceable, because a new adapter cannot construct an entity it cannot get the class for.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_construction_boundary.py`:

```python
def test_build_validates_a_closed_kind_before_projecting(tmp_path) -> None:
    # The load-bearing order. `hypothesis` is the one closed kind on this branch, so it is what
    # can demonstrate refusal at all.
    from science_model.entity_schema import EntityValidationError

    registry, project_schema = _armed_registry(tmp_path)  # helper defined below, same file
    with pytest.raises(EntityValidationError):
        registry.build(
            "hypothesis",
            {**_valid_hypothesis_mapping(), "shadow_key": "v"},
            project_schema=project_schema,
        )


def test_build_admits_a_valid_closed_kind(tmp_path) -> None:
    registry, project_schema = _armed_registry(tmp_path)
    entity = registry.build(
        "hypothesis", _valid_hypothesis_mapping(), project_schema=project_schema
    )
    assert entity.kind == "hypothesis"


def test_build_does_not_validate_an_OPEN_kind(tmp_path) -> None:
    # Open kinds keep loading exactly as before -- this branch closes nothing. A shadow key on an
    # open kind is preserved, not refused; that is the `extra="allow"` projection doing its job.
    registry, project_schema = _armed_registry(tmp_path)
    entity = registry.build(
        "concept", {**_valid_concept_mapping(), "shadow_key": "v"}, project_schema=project_schema
    )
    assert entity.kind == "concept"
```

Write `_armed_registry`, `_valid_hypothesis_mapping` and `_valid_concept_mapping` as module-level helpers in the same file. Build the registry through the existing `build_entity_registry(resolved)` path (`sources.py:322`) against a temporary project pinned to `entity_schema_version: 2`; read `tests/test_kind_reconciliation_registry.py` for the established way to construct one in this suite rather than inventing a second.

- [ ] **Step 2: Run it to verify it fails**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q -k build
```
Expected: FAIL with `AttributeError: 'EntityRegistry' object has no attribute 'build'`.

- [ ] **Step 3: Implement `build`**

In `entity_registry.py`, add alongside `resolve`:

```python
    def build(
        self,
        kind: str,
        raw: Mapping[str, Any],
        *,
        project_schema: ProjectSchema | None,
        path: Path | None = None,
    ) -> Entity:
        """Validate a raw mapping against its composed profile, THEN project it onto the model.

        Resolution and construction are ONE operation on purpose. Handing out `type[Entity]` is
        the hole: an adapter that can get the class can construct an entity without validating,
        and no AST rule over a call spelling can prevent that -- a constructor, a TypeAdapter or
        any other form defeats it. Merging them means a new adapter cannot skip the check,
        because it cannot obtain the class. `resolve` remains for callers that genuinely need the
        TYPE (registration, isinstance checks) and is guarded by the import-surface rule.
        """
        _validate_against_schema(kind, raw, project_schema=project_schema, path=path)
        return self.resolve(kind).model_validate(raw)
```

`_validate_against_schema` already carries the `kind not in PROJECT_MIXIN_NAMES` gate (`sources.py:1428`), so an open kind passes through untouched. If importing it from `sources.py` into `entity_registry.py` creates a cycle, move `_validate_against_schema` into its own module and import it from both — do **not** duplicate it.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q
```
Expected: PASS.

- [ ] **Step 5: Route all five producing sites through `build`**

Replace `registry.resolve(kind)` + `model_validate(raw)` pairs at:

- `sources.py:404` / `:412` — the Markdown path (already validates; `build` makes it the same call)
- `sources.py:1119-1120` — `model`
- `sources.py:1150-1160` — `canonical_parameter`
- `sources.py:1216` / `:1248` — structured source
- `commons_sources.py:395` / `:423` — commons

Each becomes one `registry.build(kind, raw, project_schema=..., path=...)` call. Where a site currently has no `project_schema` in scope, thread it — do not pass `None` to make the call compile, because `None` disables validation entirely.

- [ ] **Step 6: Run the graph and sources suites**

```bash
cd science && uv run --frozen pytest tests/test_kind_reconciliation_registry.py tests/test_entity_construction_boundary.py -q
cd science && uv run --frozen pytest -q -k "sources or commons or graph_build or registry" 2>&1 | tail -5
```
Expected: PASS.

- [ ] **Step 7: Lint, types, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/src/science_tool/graph/entity_registry.py science/src/science_tool/graph/sources.py science/src/science_tool/graph/commons_sources.py science/tests/test_entity_construction_boundary.py
git commit -m "feat(graph): merge entity resolution and construction into one validating operation"
```

---

### Task 6: The import-surface guard

**Files:**
- Test: `science/tests/test_entity_construction_boundary.py` (extend)

**Interfaces:**
- Consumes: `EntityRegistry.build` from Task 5.
- Produces: the AST guard the Task 7 mutation 5c targets.

**The rule is not "no module imports an entity class."** `entity_registry.py` imports the concrete classes *on purpose*, in order to register them — a block from `science_model.entities` (`:15`), plus `PatchDefinitionEntity` (`:38`) and `PropositionEntity` (`:41`). Writing the guard as a blanket ban would make registration itself the first violation. The rule is: **the registry module is the only importer, and every other module obtains entities through `registry.build`.**

**And a guard that LISTS its scope has a hole by construction.** There are exactly five entity-producing sites today, which is small enough to enumerate — and that is precisely why enumeration is rejected. It opens the day someone adds the sixth. Derive the scope from the package tree.

- [ ] **Step 1: Write the failing guard**

Append to `science/tests/test_entity_construction_boundary.py`:

```python
import ast
from pathlib import Path

_ENTITY_CLASS_SUFFIX = "Entity"
_REGISTRY_MODULE = "entity_registry.py"


def _entity_loading_package() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "science_tool" / "graph"


def _imported_entity_classes(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("science_model"):
            found |= {a.name for a in node.names if a.name.endswith(_ENTITY_CLASS_SUFFIX)}
    return found


def test_the_registry_is_the_ONLY_module_importing_entity_classes() -> None:
    # Scope is DERIVED from the package tree, never listed: there are five entity-producing sites
    # today, which is exactly why enumerating them is refused -- the list develops a hole the day
    # someone adds the sixth.
    offenders: dict[str, set[str]] = {}
    for module in sorted(_entity_loading_package().rglob("*.py")):
        if module.name == _REGISTRY_MODULE:
            continue
        imported = _imported_entity_classes(module)
        if imported:
            offenders[module.name] = imported
    assert not offenders, (
        "modules obtaining entity classes outside the registry: "
        f"{ {k: sorted(v) for k, v in offenders.items()} }. "
        "Construct entities through `registry.build(kind, raw, ...)`, which validates first."
    )


def test_every_imported_entity_class_is_actually_REGISTERED() -> None:
    # The registry's own imports are legitimate, but only for registration. A class imported and
    # never registered -- or registered from a class obtained some other way -- is the same hole
    # wearing the exemption.
    registry_module = _entity_loading_package() / _REGISTRY_MODULE
    imported = _imported_entity_classes(registry_module)
    source = registry_module.read_text(encoding="utf-8")
    unregistered = {name for name in imported if source.count(name) < 2}
    assert not unregistered, f"imported into the registry but never registered: {sorted(unregistered)}"
```

- [ ] **Step 2: Run it and read the real failures**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q -k "ONLY_module or REGISTERED"
```

**Do not predict this result — read it.** If modules other than the registry still import entity classes after Task 5, each is a real remaining hole: route it through `registry.build` and re-run. If a module legitimately needs the *type* (an `isinstance` check, a type annotation), that is a genuine finding about the guard's shape — report it rather than adding an exemption list, which would reintroduce the enumerated-scope hole.

- [ ] **Step 3: Close the offenders**

For each module the guard names, replace class-obtaining imports with `registry.build` calls. Where a type annotation is the only need, import from `science_model` under `if TYPE_CHECKING:` — a type-checking-only import cannot construct anything at runtime, and the guard should be refined to skip `TYPE_CHECKING` blocks if this case arises.

- [ ] **Step 4: Run the guard to verify it passes**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q
```
Expected: PASS.

- [ ] **Step 5: Lint, types, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/tests/test_entity_construction_boundary.py science/src/science_tool/graph/
git commit -m "test(graph): guard the entity-class import surface, deriving scope from the tree"
```

---

### Task 7: The mutation matrix

**Files:**
- Create: `science/tests/test_schema_closure_mutations.py` (documentation of results only — the mutations themselves are applied by hand and reverted)

**Interfaces:**
- Consumes: every gate from Tasks 1–6.
- Produces: nothing later depends on it.

This is a **verification** task. Each mutation breaks the implementation deliberately, proves a *named* gate catches it, and is then reverted. Rows 9–14 of design §6.2 belong to the kind slices and to the already-merged writer-containment plan; they are **not** in scope here.

**Method for every mutation:** confirm `git status --short` is clean → apply the mutation exactly → run the named selection → record the actual failures → revert (`git checkout -- <file>`) → confirm clean again. **Never commit a mutation.**

**The expected failures are part of the assertion.** If a mutation produces different tests or a different count than stated, that is a **finding — report it; do not edit this plan to match what you observed.** A mismatch means either the prediction is wrong or the implementation differs from what the plan assumed, and both need to be known.

- [ ] **Step 1: Mutation 1 — remove a generation-row entry for a closed kind**

Delete `"hypothesis": "1.0"` from generation 2 in `_MIXIN_VERSION_BY_GENERATION`.
Run: `cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q`
Expected: `test_GATE_1_every_generation_row_matches_the_closed_declaration` FAILS, naming `hypothesis` as declared-closed-but-missing-from-the-row. **Revert.**

- [ ] **Step 2: Mutation 2 — a closed declaration with no generation rows**

Set `schema_closed=True` on `concept` in `core.py`.
Expected: gate 1 FAILS for **both** generations. Gate 4 passes (concept declares `entity_class` and `home`), and `test_this_mechanism_closes_NO_new_kind` also FAILS — two named gates, which is correct, not redundant. **Revert.**

- [ ] **Step 3: Mutation 3 — a project mixin in a row with no closed declaration**

Add `"concept": "1.0"` to generation 2's row without touching any declaration.
Expected: gate 1 FAILS naming `concept` as in-the-row-but-not-declared. **Revert.**

- [ ] **Step 4: Mutation 4 — remove a packaged mixin file armed by a row**

`git mv science/model/src/science_model/schemas/mixin-hypothesis-1.0.json /tmp/`
Expected: `test_GATE_2_every_ARMED_component_resolves_to_a_packaged_file` FAILS naming `hypothesis/1.0`. **Revert** (`git mv` back, or `git checkout --`).

- [ ] **Step 5: Mutation 5a — restore `extra="ignore"` on `StructuredEntitySource`**

Expected: `test_an_unknown_key_SURVIVES_the_source_contract` FAILS (`model_extra` is `{}`), and `test_a_shadow_key_reaches_the_normalized_mapping` FAILS. This proves the **loss** is prevented. **Revert.**

- [ ] **Step 6: Mutation 5b — drop the schema check from `registry.build`**

Remove the `_validate_against_schema(...)` line, leaving only the projection.
Expected: `test_build_validates_a_closed_kind_before_projecting` FAILS (no exception raised). This proves the **check runs**.

5a and 5b are both required and are not redundant: 5a proves the loss is prevented, 5b proves the check runs. An earlier design draft had only the second, which would have passed against a pipeline faithfully validating a mapping the toolkit had already stripped — a check that cannot fail. **Revert.**

- [ ] **Step 7: Mutation 5c — construct an entity outside `registry.build`**

Add `from science_model.entities import MethodEntity` to `science/src/science_tool/graph/sources.py`.
Expected: `test_the_registry_is_the_ONLY_module_importing_entity_classes` FAILS, naming `sources.py` and `MethodEntity`. **Revert.**

(`MethodEntity` is used because it is real — verified. There is **no** `ConceptEntity`: only 21 kinds have a concrete `*Entity` class, and `concept` is not among them. A slice author closing `concept` should expect it to project onto the base `Entity`, which is also why gate 4 asks for `entity_class` on the *descriptor*, not for a dedicated class.)

- [ ] **Step 8: Mutation 5d — add an undeclared key to the drop set**

Change `STRUCTURED_DROP_KEYS` to `frozenset({"kind", "title"})`.
Expected: `test_kind_is_the_only_declared_DROP` FAILS. **Revert.**

- [ ] **Step 9: Mutation 6 — closed descriptor with `home=None`**

Set `home=None` on `hypothesis` in `core.py`.
Expected: `test_GATE_4_a_closed_kind_declares_entity_class_and_home` FAILS on `home`. **Revert.**

- [ ] **Step 10: Mutation 7 — closed descriptor with `entity_class=None`**

Set `entity_class=None` on `hypothesis`.
Expected: gate 4 FAILS on `entity_class`. **Revert.**

- [ ] **Step 11: Mutation 8 — external manifest authors `schema_closed`**

Already covered by `test_an_external_manifest_may_NOT_author_schema_closed`, which asserts the raise directly rather than requiring a source mutation. Confirm it fails when the `_refuse_toolkit_reserved_fields` validator body is replaced with `return data`.
Expected: both external-manifest rejection tests FAIL. **Revert.**

- [ ] **Step 12: Record the results and commit**

Write `science/tests/test_schema_closure_mutations.py` containing **no test functions** — a module docstring recording the matrix as executed: one row per mutation with the mutation, the named gate, and the observed failures. A results table nobody can run is still the record of what was proven, and it is where the next slice's author learns which gate covers what.

```bash
cd science && uv run ruff check
git add science/tests/test_schema_closure_mutations.py
git commit -m "docs(tests): record the schema-closure mutation matrix results"
```

---

### Task 8: The per-kind slice procedure, and the `promoted_from` ruling

**Files:**
- Create: `docs/conventions/schema-closure-slice-procedure.md`
- Modify: `science/src/science_tool/migrate_hypothesis.py:77` — **note the path**: this file is directly under `science_tool/`, not under a `migrations/` subdirectory as the design implies. The line number is correct.

**Interfaces:**
- Consumes: everything above.
- Produces: the procedure each of the five slice branches follows.

- [ ] **Step 1: Correct the superseded ruling comment**

The comment block at `science/src/science_tool/migrate_hypothesis.py:77-80` currently reads:

```python
# NOT migrated, and that is the ruling (2026-07-14): `promoted_from` is a PROJECT EXTENSION
# (protein-landscape). Its `origins` rename was refuted by the model -- `OriginRecord.type` is a
# required enum naming WHO had the idea, and the authored values are source paths naming WHERE the
# entity came from. Any type the migration picked would be fabricated provenance.
```

Design §4.3 refutes the **ownership** half (the first sentence) — `graph/decision_log.py:157` writes `fm["promoted_from"] = promoted_from` onto a **core** kind, and a project extension cannot own a field the toolkit writes into core-kind files. Under `unevaluatedProperties: false` every project would need to author protein-landscape's extension to survive a `decision` write it did not make.

Edit the comment to record the narrowed ruling. **Preserve the load-bearing half verbatim:** `promoted_from` is **not** migratable into `origins`, because `OriginRecord.type` is a required enum naming *who* had the idea while these values name *where* the entity came from — any type the migration picked would be fabricated provenance. Only the *ownership* half is superseded.

- [ ] **Step 2: Write the slice procedure**

Create `docs/conventions/schema-closure-slice-procedure.md`. It must state, in full:

The seven steps (design §4): freeze the field-surface inventory and dispositions; author the dormant mixin plus projection/value/mutation probes; update sources, templates, writers, readers and adapter-specific records; certify the candidate composed profile over all projects and all source paths; reconcile schema fields against the projection and the reader/omit decisions; diff graph, validation, dashboard and other derived outputs against an intended-change allowlist; then **atomically** add both generation entries and set `schema_closed=True`.

Plus these rulings, each stated so a slice author cannot re-litigate them:

- **Atomicity is merge scope.** One kind's slice is one branch, merged as a unit. Steps 1–6 land as separate reviewable commits; **step 7 is the only edit that arms enforcement**. **No partial release** — merging 1–6 without 7 leaves templates and writers emitting a declared field set that nothing enforces, which is this design's own defect in miniature.
- **The candidate universe is a union, not the observed corpus** (§4.1): fields observed across *all* source formats, template and writer output, keyed consumer reads, Pydantic projection fields and defaults, existing base/schema fields applicable to the kind, and known retired/tombstoned fields. A zero-occurrence field can still be prescribed by a template, and corpus success cannot prove rejection behaviour.
- **Explicit `false` is reserved** (§4.2) for base-admitted fields the kind narrows away and for tested tombstones. The 231-key shadow schema does not become a 231-entry deny list; omission is the default refusal.
- **`promoted_from` is a per-kind core field** (§4.3), declared inline in each mixin that admits it, matching this frozen literal oracle taken from `~/d/protein-landscape/schemas/extension-protein-landscape-promotion-1.0.json`:

  ```json
  {"type": "string", "minLength": 1,
   "description": "Path of the source file this entity was promoted from, e.g. knowledge/sources/local/entities.yaml"}
  ```

  The gate asserts each mixin equals **that literal**, not that the mixins agree with each other — pairwise equality permits every mixin to drift identically, which is the §3.4 tautology one level down. Semantics: it names *the authored artifact this entity was promoted out of* — a source location, not an idea origin. Four of the five tranche kinds carry it: `concept` (132), `finding` (26), `observation` (25), `method` (20).
- **`finding` carries a source migration and gate 3 is its hard prerequisite.** 149 generated rows in one file (`~/d/natural-systems/knowledge/sources/project_specific/finding.yaml`) are missing `updated`. **THE MIGRATION RULE: `updated = created`** — all 149 carry `created: 2026-04-30` and none carries `updated`. Migration date, file mtime and current date are each rejected **by name**: all four produce a schema-valid `format: date` string, so no schema check can distinguish them and only an assertion on provenance semantics can. The backfill is a one-time edit to the source file, **not a loader default** — the loader must keep failing on a row that genuinely lacks the field, or gate 3's behavioural test becomes unfalsifiable. Mutation-test all three alternatives.
- **Corpus certification runs per adapter, not per format** (§6.3), under the `real_projects` marker, composing each project's candidate profile **with that project's own declared extensions** — mm30's `mm30.assessment`, evolution's `evolution.provenance`, protein-landscape's `protein-landscape.promotion` are why `unevaluatedProperties: false` does not reject projects that did nothing wrong. The 20 expected project identities are frozen: when `-m real_projects` is explicitly selected a **missing project fails rather than skips**, or "all 20 passed" silently becomes "the 17 available passed."
- **Suggested slice order:** `concept` (329 docs, 4 non-base fields, reference class) first — largest corpus, simplest tail, and it proves the mechanism against the reference class. Then `method`, `search`, `observation`, and `finding` **last**, because it is the only one carrying a source migration.

- [ ] **Step 3: Verify the procedure names every out-of-scope debt**

The document must also record what a slice does **not** close, so a slice author does not assume otherwise: `hypothesis`'s re-alignment to the `promoted_from` ruling needs a versioned mixin bump and is **open debt**; the 6 unclosed core kinds carrying `promoted_from` outside the tranche (`topic` 64, `decision` 18, `paper` 17, `proposition` 9, `dataset` 4, `workflow` 3) get their declarations when those kinds close; and the structured rows of non-tranche kinds (`morphism-edge` 70, `limit-relation` 131, `workflow` 6) stay untouched — gate 3 makes their load path validating but no profile applies to them, so it must not be mistaken for having repaired them.

- [ ] **Step 4: Commit**

```bash
git add docs/conventions/schema-closure-slice-procedure.md science/src/science_tool/migrations/migrate_hypothesis.py
git commit -m "docs(conventions): the per-kind schema-closure slice procedure"
```

---

## Verification

Run once, at the end, by the top-level agent:

```bash
cd science && uv run --frozen pytest -q                    # ~2-3 min
cd science/model && uv run --frozen pytest -q
cd science && uv run ruff check && uv run pyright
cd science/model && uv run ruff check
cd science && uv run --frozen pytest -m real_projects -q   # opt-in
cd science && uv run --frozen pytest -m snapshot -q        # opt-in
```

**Four failures are pre-existing on `main`** and were reproduced at merge-base `ca937131` during the writer-containment branch: one `-m snapshot` formatter-snapshot mismatch (`Checks: 68` vs 69) and three `-m real_projects` failures (skills-coverage commons datasets, correspondence drift on multiple-myeloma, canonical-body parity). Reproduce any failure at the merge-base before attributing it to this branch.

**The behavioural invariant for this whole branch:** `PROJECT_MIXIN_NAMES == frozenset({"hypothesis"})` before and after. This plan changes *how* the answer is derived and *which paths must ask*, never *what the answer is*.

## Out of scope

- **Closing any kind.** Five separate branches, per Task 8's procedure.
- **The 769 `proposition` / `evidence-line` documents.** Piece 3.
- **Widening `REFERENCE_FIELD_NAMES` or the `undeclared_key` diagnostic.** A warning surface is not the mechanism this design builds; a wrong answer should become unreachable, not discouraged.
- **The remaining 44 unclosed core kinds** and the 16 authored non-core kinds.
- **`render_update`'s stale-owned-key hole**, recorded in the writer-containment plan's follow-up section. Independent of this work.

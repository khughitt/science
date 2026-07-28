# Schema Closure Mechanism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make "is kind K schema-checked?" a single declaration on `EntityKind`, derive every consumer from it, and close the load paths that can reach a schema-closed kind without validating first.

**Architecture:** `EntityKind` gains `schema_closed: bool`, declared explicitly on all 53 shipped kinds. `PROJECT_MIXIN_NAMES` becomes derived from it, so arming a kind is one edit. Four gates compare that declaration against independently hand-authored artifacts. The structured-source path stops discarding unknown keys before validation, and entity construction is funnelled through one `registry.build` operation whose exclusivity is enforced by an AST guard asserting that no module in the loading package resolves an entity class to build from.

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
| import cycle risk, Task 1 | **none** — `profiles/` does not import `entity_schema`, and `entity_schema/profile.py` imports nothing from the package |
| import cycle risk, Task 5 | **certain** — `sources.py:64` imports `EntityRegistry`, so `entity_registry.py` cannot import from `sources.py`. Task 5 Step 3 extracts the validators first; this is not a contingency |
| dormant mixin files | `dataset-1.0`, `paper-1.0`, `theme-1.0`, `topic-1.0` exist on disk armed by no row — gate 2 must be forward-only |
| `_validate_against_schema` signature | `(raw: dict[str, Any], *, kind: str, path: str, project_schema: ProjectSchema \| None)` — `raw` positional, `path` is `str` not `Path` |
| `registry.resolve` calls in `graph/` | **5**, the same five producing sites. Zero after Task 5 — which is what makes Task 6's guard assertable |
| `registry.resolve` calls elsewhere in `src/` | `verdict/parser.py:64`, `verdict/rollup.py:108` — a **different** registry (`… is None`; `EntityRegistry.resolve` raises) |
| modules in `graph/` importing an entity class | **12**, nearly all for `isinstance` and annotations (`materialize.py:1798` is `isinstance(object_entity, Entity)`). This is why Task 6 guards calls, not imports |
| `model_dump(exclude_unset=True)` under `extra="allow"` | returns authored keys **plus extras**, and no defaulted fields — verified against Pydantic; it is how Task 4 gets the authored row |
| `_load_typed_records` return/cache type | `list[_SourceRecordT]` — parsed models only. The authored mapping is **not** in scope at the construction site |
| tests asserting the opposite of Task 4 | `tests/test_undeclared_key_diagnostic.py:58` — inverted deliberately, with a ruling, in Task 4 Step 8 |

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
| `science/src/science_tool/graph/entity_registry.py` | `build(kind, raw, *, project_schema, path, enrich)` replaces handing out the class; `EntityProjectionError` keeps the Markdown reader's three rejection codes distinct |
| `science/src/science_tool/graph/sources.py`, `commons_sources.py` | all five producing sites route through `registry.build` |
| `science/tests/test_entity_construction_boundary.py` | **new** — gate 3: unit + end-to-end load-path checks, plus the construction-surface AST guard |
| `science/src/science_tool/graph/entity_schema_validation.py` | **new** — `validate_against_schema` / `validate_dataset_gen3`, moved out of `sources.py` to break a certain import cycle (Task 5) |
| `science/tests/test_local_kind_registration_reserved_fields.py` | **new** — pins the tool-side manifest loader's rejection (Task 2) |
| `science/tests/test_undeclared_key_diagnostic.py` | one test inverted: structured rows now preserve unknown reference keys (Task 4, Step 8) |
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
Expected: `MODEL LOADER rejected: ...`.

This command exercises **one** of the two entry points. The tool-side path (`entity_kinds.py:116-129`, `_validate_manifest_shape`) reaches the same `ProfileManifest.model_validate` call, but "shares the call today" is a fact about today's code, not a guarantee — and an ad-hoc shell command certifies nothing after this branch merges. Step 6 makes it durable.

- [ ] **Step 6: Pin the tool-side loader with a durable test**

Create `science/tests/test_local_kind_registration_reserved_fields.py`:

```python
"""The SECOND external manifest entry point, pinned so the two cannot silently diverge.

`science_model`'s `load_profile_manifest` and the tool's `_validate_manifest_shape` both reach
`ProfileManifest.model_validate` today. That is why one before-validator covers both -- and
exactly why it needs a test on THIS side: a future refactor that hand-rolls the tool-side parse
would leave the rejection covered by a model test that keeps passing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.entity_kinds import _validate_manifest_shape


def _manifest(**kind_extra: object) -> dict:
    return {
        "name": "local",
        "imports": [],
        "relation_kinds": [],
        "strictness": "typed-extension",
        "entity_kinds": [
            {
                "name": "widget",
                "canonical_prefix": "widget",
                "layer": "layer/local",
                "description": "d",
                **kind_extra,
            }
        ],
    }


def test_the_TOOL_side_loader_refuses_an_authored_schema_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="schema_closed"):
        _validate_manifest_shape(tmp_path / "manifest.yaml", _manifest(schema_closed=True))


def test_the_tool_side_loader_admits_an_ordinary_local_kind(tmp_path: Path) -> None:
    # The rejection must be about the RESERVED field, not about local kinds in general -- a check
    # that refuses everything would pass the test above while breaking `science kinds register`.
    _validate_manifest_shape(tmp_path / "manifest.yaml", _manifest(entity_class="reference"))


def test_registering_a_local_kind_still_works_end_to_end(tmp_path: Path) -> None:
    from science_tool.entity_kinds import register_local_kind

    (tmp_path / "science.yaml").write_text(yaml.safe_dump({"name": "demo"}), encoding="utf-8")
    assert register_local_kind(tmp_path, "widget", "reference") == "registered"
```

Run: `cd science && uv run --frozen pytest tests/test_local_kind_registration_reserved_fields.py -q`
Expected: PASS. If `_validate_manifest_shape` does **not** reach `ProfileManifest.model_validate`, the first test fails — stop and report, because the single-site premise is then false.

- [ ] **Step 7: Lint, types, commit**

```bash
cd science/model && uv run ruff check
cd .. && uv run ruff check && uv run pyright
git add science/model/src/science_model/profiles/schema.py science/model/tests/test_schema_closed_gate.py science/tests/test_local_kind_registration_reserved_fields.py
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
- Modify: `science/src/science_tool/graph/sources.py:1208-1249` (`_load_structured_source_records`)
- Test: `science/tests/test_entity_construction_boundary.py` (new)
- Test: `science/tests/test_undeclared_key_diagnostic.py:58` (invert one test — see Step 8; it asserts the opposite of this task by name)

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

from pathlib import Path

import pytest
import yaml

from science_model.source_contracts import StructuredEntitySource
from science_tool.graph.sources import load_project_sources


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

In `sources.py`, `_load_structured_source_records` (`:1208-1249`) currently builds the entity mapping inline from the parsed record's **attributes** and calls `schema.model_validate(raw)`.

**The authored row is not in scope at that point, and must not be re-plumbed to get it.** `_load_typed_records` (`:1365`) parses each YAML item and returns — and *caches* — only `list[_SourceRecordT]`. Changing it to return raw-plus-parsed pairs would change the cache value type and all four of its callers (`:1119`, `:1150`, `:1208`, `_load_binding_sources`, `_legacy_nested_relations`), for no gain: with `extra="allow"` from Step 3, the parsed record already carries the authored keys and only those.

Use `record.model_dump(exclude_unset=True)`. **Verified against Pydantic before this plan was written:** for `extra="allow"`, extras land in `model_fields_set`, so `model_dump(exclude_unset=True)` on a row authoring only `canonical_id` and `shadow_key` returns exactly `{"canonical_id": ..., "shadow_key": ...}` — authored keys plus extras, and none of the eleven defaulting fields. That is precisely the mapping `normalize_structured_row` must range over, and it is why Step 4's "never over a parsed record's defaults" rule is satisfiable without touching the loader's plumbing.

So the shape is:

```python
        for record in records:
            raw = normalize_structured_row(record.model_dump(exclude_unset=True))
            # Loader BACKFILLS -- policy, not source content, and deliberately after normalization
            # so the schema sees them as the loader's contribution rather than the author's.
            raw["kind"] = kind_name
            raw["type"] = kind_name
            raw.setdefault("canonical_id", record.canonical_id)
            raw.setdefault("title", record.title or record.canonical_id)
            raw.setdefault("profile", record.profile or local_profile)
            raw.setdefault("file_path", default_path)
```

Keep every other backfill the current code performs, each named and after normalization. Leave the `schema.model_validate(...)` call in place for now; Task 5 replaces it with `registry.build`.

- [ ] **Step 7: Prove the pipeline end to end, not just its three pieces**

The tests written in Step 1 each exercise **one** component with a hand-built dict. None of them proves an authored row travels `_load_typed_records` → `normalize_structured_row` → construction intact — and a mutation to `extra="ignore"` cannot fail a test that passes a dict straight to `normalize_structured_row`. Append the tests that can only pass if the real path is wired:

```python
def _write_structured_project(root: Path, rows: list[dict]) -> None:
    """A project whose local profile declares one structured-source kind."""
    (root / "science.yaml").write_text(
        yaml.safe_dump({"name": "demo", "local_profile": "project_specific"}), encoding="utf-8"
    )
    sources = root / "knowledge" / "sources" / "project_specific"
    sources.mkdir(parents=True)
    (sources / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "project_specific",
                "imports": [],
                "relation_kinds": [],
                "strictness": "typed-extension",
                "entity_kinds": [
                    {
                        "name": "widget",
                        "canonical_prefix": "widget",
                        "layer": "layer/local",
                        "description": "d",
                        "entity_class": "reference",
                        "structured_source": "widget.yaml",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (sources / "widget.yaml").write_text(yaml.safe_dump({"widget": rows}), encoding="utf-8")


def test_an_authored_shadow_key_SURVIVES_the_whole_load_path(tmp_path: Path) -> None:
    # THE end-to-end assertion. Every other test in this file builds its own input; this one
    # authors a file and reads what the loader produced. It is the only test in the gate that a
    # regression to `extra="ignore"` can fail.
    _write_structured_project(
        tmp_path, [{"canonical_id": "widget:0001-x", "title": "W", "shadow_key": "v"}]
    )
    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "widget:0001-x")
    assert (entity.model_extra or {}).get("shadow_key") == "v"


def test_a_row_omitting_an_optional_field_does_not_gain_an_empty_one(tmp_path: Path) -> None:
    # The defaults-promotion failure, asserted on the real path. If normalization ranged over the
    # parsed record rather than `model_dump(exclude_unset=True)`, an unauthored `evidence_refs`
    # would arrive as an authored `[]` -- schema-valid, and wrong.
    _write_structured_project(tmp_path, [{"canonical_id": "widget:0002-y", "title": "W2"}])
    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "widget:0002-y")
    assert entity.evidence_refs == []  # the MODEL default, not an authored value
```

Run: `cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q`
Expected: PASS. If `load_project_sources` needs more scaffolding than the helper above provides, read `tests/test_undeclared_key_diagnostic.py`'s `_write_project` for the established shape in this suite rather than inventing a second.

- [ ] **Step 8: Rule on the diagnostic surface this widens — do not leave it implicit**

`tests/test_undeclared_key_diagnostic.py:58`, `test_structured_source_drops_unknown_reference_key`, asserts the opposite of Step 3 **by name**. It is not collateral damage to repair quietly: it pins a real invariant — that the `undeclared_key` audit warning cannot misfire on structured rows, because their extras were destroyed upstream.

**The ruling: the warning is correct, and its absence was the same defect one layer up.** `_audit_undeclared_reference_keys` (`graph/migrate.py:141`) warns for a reference-named extra on a kind outside `strict_schema_kinds`. A structured row carrying `method: phantom` on a kind that does not declare `method` *is* an unvouched reference key. It could not be reported before only because the loss happened before the auditor could see it — which is the exact shape of defect gate 3 exists to close. Suppressing the warning now would re-hide it.

Replace the test in place, keeping the file's framing:

```python
def test_structured_source_PRESERVES_an_unknown_reference_key() -> None:
    # Inverted deliberately (schema-closure mechanism, Task 4). The contract is `extra="allow"`
    # so unknown keys survive to be REFUSED by the composed schema on a closed kind -- and, on an
    # open kind, to be REPORTED by the undeclared_key audit. The previous assertion pinned the
    # silence, not the correctness: a `method:` key on a kind that does not declare it is exactly
    # what the diagnostic is for, and it was unreportable only because the row was stripped first.
    record = StructuredEntitySource.model_validate(
        {"canonical_id": "workflow:w", "title": "W", "kind": "workflow", "method": "phantom"}
    )
    assert record.model_extra == {"method": "phantom"}  # `kind` is dropped by normalization, not here
```

- [ ] **Step 9: Measure the new warnings before accepting them**

The ruling above widens a **warning** surface across every project with structured sources. Warnings are not failures, but an unmeasured jump in them is how a diagnostic gets ignored. Count them:

```bash
cd science && uv run --frozen python -c "
import pathlib, yaml
from science_tool.graph.reference_fields import REFERENCE_FIELD_NAMES
tot = {}
for root in pathlib.Path.home().joinpath('d').glob('*/knowledge/sources/*/*.yaml'):
    try: data = yaml.safe_load(root.read_text()) or {}
    except Exception: continue
    for rows in data.values():
        if not isinstance(rows, list): continue
        for row in rows:
            if not isinstance(row, dict): continue
            for k in row:
                if k in REFERENCE_FIELD_NAMES: tot[k] = tot.get(k, 0) + 1
print(sorted(tot.items(), key=lambda kv: -kv[1]))
"
```

Import `REFERENCE_FIELD_NAMES` from wherever `graph/migrate.py` gets it — grep for it rather than assuming the module path above. Record the counts in your report. **If the total exceeds ~50, stop and report before committing**: that is no longer a diagnostic widening but a corpus finding, and it needs a ruling this plan does not contain.

- [ ] **Step 10: Run the structured-source and diagnostic suites**

```bash
cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py tests/test_entity_construction_boundary.py -q
cd science && uv run --frozen pytest -q -k "structured_source or structured or sources" 2>&1 | tail -5
```
Expected: PASS. Any **other** test asserting an unknown key is silently dropped is now wrong by design — repair it to assert the key survives, and record each one in your report. Do not relax an assertion to make it pass.

- [ ] **Step 11: Lint, types, commit**

```bash
cd science/model && uv run ruff check
cd .. && uv run ruff check && uv run pyright
git add science/model/src/science_model/source_contracts.py science/src/science_tool/graph/source_normalization.py science/src/science_tool/graph/sources.py science/tests/test_entity_construction_boundary.py science/tests/test_undeclared_key_diagnostic.py
git commit -m "feat(sources): make the structured source contract lossless and declare its normalization"
```

---

### Task 5: One construction choke point

**Files:**
- Create: `science/src/science_tool/graph/entity_schema_validation.py` (moved from `sources.py` — see Step 3)
- Modify: `science/src/science_tool/graph/entity_registry.py:189`
- Modify: `science/src/science_tool/graph/sources.py:382-456`, `:1119`, `:1150`, `:1216`, `:1401-1461`
- Modify: `science/src/science_tool/graph/commons_sources.py:395`
- Test: `science/tests/test_entity_construction_boundary.py` (extend)

**Interfaces:**
- Consumes: `normalize_structured_row` from Task 4.
- Produces:
  - `EntityRegistry.build(kind: str, raw: dict[str, Any], *, project_schema: ProjectSchema | None, path: str, enrich: Callable[[dict[str, Any]], frozenset[str]] | None = None) -> Entity`
  - `EntityRegistry.EntityProjectionError(kind, schema, error)` — a `ValueError` subclass carrying the resolved class
  - `graph/entity_schema_validation.py` exposing `validate_against_schema` / `validate_dataset_gen3`

  Task 6's guard depends on **no `registry.resolve` call surviving in `graph/`**.

**Why `resolve` is the hole.** `EntityRegistry.resolve(kind)` returns `type[Entity]`. Handing out the class means any adapter — present or future — can construct an entity without validating. Merging resolution and construction into one operation is what makes the boundary enforceable: obtaining the class stops being how an entity gets built, and the five sites that do it today become zero, which is a property a guard can assert.

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

- [ ] **Step 3: Extract the validators into their own module FIRST**

**The import cycle is certain, not contingent.** `sources.py:64` already does `from science_tool.graph.entity_registry import ... EntityRegistry`, so `entity_registry.py` importing anything from `sources.py` closes the loop. Do not attempt the import and see; extract first.

Create `science/src/science_tool/graph/entity_schema_validation.py` and **move** (not copy) `_validate_against_schema` (`sources.py:1401-1437`) and `_validate_dataset_gen3` (`sources.py:1440-1461`) into it verbatim, docstrings included, renamed to `validate_against_schema` / `validate_dataset_gen3`. Their five dependencies are all cycle-free — verified against the tree:

| Dependency | From | Imports `entity_registry`? |
|---|---|---|
| `PROJECT_MIXIN_NAMES`, `EntityValidationError` | `science_model.entity_schema` | no (different package) |
| `ProjectSchema` | `science_tool.entity_profiles` | no |
| `gen3_shape_issue` | `science_tool.datasets.capability_shape` | no |
| `MarkdownAdapter.INJECTED_KEYS` | `science_tool.graph.storage_adapters.markdown` | no |

In `sources.py`, delete both definitions and add `from science_tool.graph.entity_schema_validation import validate_against_schema, validate_dataset_gen3`, updating its two call sites (`:411`, `:417`). Run `cd science && uv run --frozen pytest -q -k "sources or schema" 2>&1 | tail -3` before continuing — a move that changed behaviour must surface here, not three steps later.

- [ ] **Step 4: Implement `build`**

**Match the moved signature exactly.** It is `(raw: dict[str, Any], *, kind: str, path: str, project_schema: ProjectSchema | None)` — `raw` is positional, `kind` and `path` are keyword-only, and `path` is `str`, not `Path`. In `entity_registry.py`, add alongside `resolve`:

```python
    def build(
        self,
        kind: str,
        raw: dict[str, Any],
        *,
        project_schema: "ProjectSchema | None",
        path: str,
    ) -> Entity:
        """Validate a raw mapping against its composed profile, THEN project it onto the model.

        Resolution and construction are ONE operation on purpose. Handing out `type[Entity]` is
        the hole: an adapter that can get the class can construct an entity without validating.
        Merging them means a new adapter cannot skip the check, because obtaining the class is no
        longer how you build an entity. `resolve` stays public for callers that genuinely need
        the TYPE, and Task 6 guards the call surface rather than the import surface -- because
        twelve modules in this package legitimately reference `Entity` for annotations and
        isinstance checks, and only the five that RESOLVE-then-construct are the hole.

        Raises EntityKindNotRegisteredError (unknown kind), ValueError (composed-schema refusal),
        or pydantic ValidationError (projection refusal) -- three distinct failures, kept distinct
        so the Markdown adapter can keep classifying them into its three rejection codes.
        """
        schema = self.resolve(kind)
        validate_against_schema(raw, kind=kind, path=path, project_schema=project_schema)
        validate_dataset_gen3(raw, kind=kind, path=path, project_schema=project_schema)
        return schema.model_validate(raw)
```

Import `ProjectSchema` under `if TYPE_CHECKING:` — `entity_profiles` is a heavier import than the registry needs at runtime, and the annotation is a string. `validate_against_schema` already carries the `kind not in PROJECT_MIXIN_NAMES` gate (moved from `sources.py:1428`), so an open kind passes through untouched.

`resolve` is called **before** validation so an unknown kind raises `EntityKindNotRegisteredError` rather than being schema-validated first; that ordering is what the Markdown path's `UNKNOWN_KIND` classification depends on.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q
```
Expected: PASS.

- [ ] **Step 5: Give `build` the two things the Markdown path would otherwise lose**

The Markdown path is not a resolve-then-validate pair that collapses into one call. `validate_canonical_markdown_record` (`sources.py:382-456`) does four things a flat `build` would destroy, and **both** must be handled before Step 6 touches any call site:

**(a) Enrichment sits BETWEEN validation and projection.** The real order is validate authored mapping → `_enrich_raw` (which mutates the mapping and returns `authored_aliases`) → `model_validate`. Validating after enrichment would show the composed schema keys the toolkit injected, and under `unevaluatedProperties: false` those become refusals of records that did nothing wrong. So `build` takes the enrichment as a parameter and owns the order — which is the point, since the order stops being each adapter's private property:

```python
        enrich: "Callable[[dict[str, Any]], frozenset[str]] | None" = None,
```

applied after the two validators and before `schema.model_validate(raw)`, with `build` performing the `entity._authored_aliases = authored_aliases` assignment both call sites do today.

**(b) Three failures must stay three failures.** The path classifies `UNKNOWN_KIND`, `PROJECT_SCHEMA`, and `ENTITY_SCHEMA` separately, and the `ENTITY_SCHEMA` branch (`sources.py:604-613`) needs the resolved **class** to format its message via `_format_schema_validation_failure`. `resolve` raising and `validate_against_schema` raising `ValueError` already separate the first two. For the third, add to `entity_registry.py`:

```python
class EntityProjectionError(ValueError):
    """A mapping that resolved and passed its composed schema, then failed the model projection.

    Carries the resolved class because the Markdown reader formats its rejection from it. Without
    this, the only way for a caller to obtain the class would be `resolve` -- reopening the exact
    hole `build` exists to close, in the one branch nobody reads.
    """

    def __init__(self, kind: str, schema: type[Entity], error: "ValidationError") -> None:
        super().__init__(f"{kind}: entity projection failed")
        self.kind = kind
        self.schema = schema
        self.error = error
```

and wrap the projection in `build`:

```python
        try:
            entity = schema.model_validate(raw)
        except ValidationError as exc:
            raise EntityProjectionError(kind, schema, exc) from exc
```

`validate_canonical_markdown_record` then keeps its exact current shape and rejection codes, with the three `try` blocks becoming one:

```python
    try:
        entity = context.registry.build(
            kind, candidate, project_schema=context.project_schema, path=path, enrich=_enrich,
        )
    except EntityKindNotRegisteredError:
        return CanonicalMarkdownValidation(kind=kind, rejection=CanonicalMarkdownRejection.UNKNOWN_KIND)
    except EntityProjectionError as exc:
        return CanonicalMarkdownValidation(
            kind=kind, schema=exc.schema, authored_aliases=..., 
            rejection=CanonicalMarkdownRejection.ENTITY_SCHEMA, error=exc.error,
        )
    except ValueError as exc:
        return CanonicalMarkdownValidation(
            kind=kind, rejection=CanonicalMarkdownRejection.PROJECT_SCHEMA, error=exc,
        )
```

**Order matters in that `except` chain:** `EntityProjectionError` subclasses `ValueError`, so it must be caught first. Note the `PROJECT_SCHEMA` branch no longer carries `schema=schema` — check whether the consumer at `sources.py:598-603` reads it (it reads only `.error`); if it does read `.schema`, report rather than dropping the field.

`authored_aliases` on the projection-failure branch: `build` has them but the exception does not carry them, and today's code does. Either add them to `EntityProjectionError` or confirm from `sources.py:604-660` that the `ENTITY_SCHEMA` branch never reads `validation.authored_aliases` — **check, do not assume.**

- [ ] **Step 6: Route the other four producing sites through `build`**

- `sources.py:1119-1120` — `model`
- `sources.py:1150-1160` — `canonical_parameter`
- `sources.py:1216` / `:1248` — structured source (its `_enrich_raw` call passes through the new `enrich` parameter, same as Markdown)
- `commons_sources.py:395` / `:423` — commons

Each becomes one `registry.build(kind, raw, project_schema=..., path=...)` call, and **no `registry.resolve` call may remain in `src/science_tool/graph/`** — Task 6's guard asserts exactly that, and the five sites listed across Steps 5 and 6 are the complete set (verified: `grep -rn 'registry\.resolve' src/` finds these five in `graph/`, plus two in `verdict/` that are a different registry object entirely — `registry.resolve(claim_id) is None` cannot be `EntityRegistry.resolve`, which raises).

Where a site currently has no `project_schema` in scope, thread it — do not pass `None` to make the call compile, because `None` disables validation entirely.

- [ ] **Step 7: Run the graph and sources suites**

```bash
cd science && uv run --frozen pytest tests/test_kind_reconciliation_registry.py tests/test_entity_construction_boundary.py -q
cd science && uv run --frozen pytest -q -k "sources or commons or graph_build or registry or markdown" 2>&1 | tail -5
```
Expected: PASS. The Markdown rejection-classification tests are the ones at risk here — if any of the three rejection codes stops being produced, this is where it shows.

- [ ] **Step 8: Lint, types, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/src/science_tool/graph/entity_registry.py science/src/science_tool/graph/entity_schema_validation.py science/src/science_tool/graph/sources.py science/src/science_tool/graph/commons_sources.py science/tests/test_entity_construction_boundary.py
git commit -m "feat(graph): merge entity resolution and construction into one validating operation"
```

---

### Task 6: The construction-surface guard

**Files:**
- Test: `science/tests/test_entity_construction_boundary.py` (extend)

**Interfaces:**
- Consumes: `EntityRegistry.build` from Task 5.
- Produces: the AST guard the Task 7 mutation 5c targets.

**This guard scans for `resolve` CALLS, not for entity-class imports.** An earlier draft of this plan proposed the import version. It was run against the tree before this revision and **fails today with twelve offenders in `graph/` alone** — `materialize.py`, `identity_arbitration.py`, `reference_resolution.py`, `storage_adapters/base.py` and eight others — nearly all of which import `Entity` for `isinstance` checks and type annotations, not to construct anything. `materialize.py:1798` is the clearest case: `isinstance(object_entity, Entity)` inside `_is_membership`. A guard whose green state requires rewriting twelve unrelated modules is not a guard; and the only ways to make it pass are an exemption list (the enumerated-scope hole, refused) or a scope narrowed until it asserts nothing.

The import surface was also the wrong surface. Importing `Entity` for an annotation constructs nothing. **Obtaining a class in order to build from it** is the hole, and that has exactly one spelling in this codebase: `registry.resolve(kind)` followed by `.model_validate(...)`. Measured before this revision:

| `registry.resolve` call sites in `src/science_tool/graph/` | 5 — `sources.py:404`, `:1119`, `:1150`, `:1216`; `commons_sources.py:395` |
| After Task 5 routes all five through `build` | **0** |
| Elsewhere in `src/` | `verdict/parser.py:64`, `verdict/rollup.py:108` — a **different** registry object (`registry.resolve(claim_id) is None`; `EntityRegistry.resolve` raises, never returns None) |

So the guard fails today, passes after Task 5, and fails again under mutation 5c. Scope stays derived from the package tree — `graph/` is the entity-loading package and every producing site lives in it — not from a list of modules.

- [ ] **Step 1: Write the failing guard**

Append to `science/tests/test_entity_construction_boundary.py`:

```python
import ast

_REGISTRY_MODULE = "entity_registry.py"


def _entity_loading_package() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "science_tool" / "graph"


def _receiver_name(func: ast.Attribute) -> str:
    value = func.value
    if isinstance(value, ast.Name):
        return value.id          # registry.resolve(kind)
    if isinstance(value, ast.Attribute):
        return value.attr        # context.registry.resolve(kind), self._registry.resolve(kind)
    return ""


def _registry_resolve_lines(module: Path) -> list[int]:
    """Lines calling `<...>registry.resolve(<arg>)`.

    Both filters are load-bearing and were measured, not guessed. Matching every `.resolve(` in
    this package reports 29 lines, of which 24 are `resolver.resolve(...)` in `materialize.py` --
    reference resolution, nothing to do with entity classes. Requiring an argument excludes
    `path.resolve()`; requiring a registry receiver excludes the resolver. Together they report
    exactly the five producing sites and nothing else.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    return sorted(  # sorted: ast.walk is breadth-first, so raw order is not source order
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "resolve"
        and node.args
        and _receiver_name(node.func).lower().endswith("registry")
    )


def test_NOTHING_in_the_loading_package_resolves_a_class_to_build_from() -> None:
    # The guard is over CALLS, not imports. Twelve modules in this package import `Entity` for
    # isinstance checks and annotations and construct nothing -- banning the import would make
    # those the violation and force either a rewrite of unrelated code or an exemption list, and
    # an exemption list is the enumerated-scope hole this project has been bitten by before.
    #
    # Obtaining a class in order to build from it has one spelling: `registry.resolve(kind)` then
    # `.model_validate(...)`. There were five such sites; `build` makes it zero. Scope is DERIVED
    # from the package tree, so a sixth adapter added tomorrow is inside it automatically.
    offenders: dict[str, list[int]] = {}
    for module in sorted(_entity_loading_package().rglob("*.py")):
        if module.name == _REGISTRY_MODULE:
            continue  # `build` calls `resolve` -- that is the one legitimate call, by construction
        lines = _registry_resolve_lines(module)
        if lines:
            offenders[module.name] = lines
    assert not offenders, (
        f"modules resolving an entity class outside the registry: {offenders}. "
        "Construct through `registry.build(kind, raw, ...)`, which validates first."
    )


def test_the_guard_can_actually_SEE_a_violation(tmp_path: Path) -> None:
    # An AST guard that silently matches nothing passes forever, and this one carries two filters
    # tuned to make it quiet. Pin the detector against known inputs so a refactor that breaks the
    # matching fails HERE, rather than turning the gate above into a green no-op.
    probe = tmp_path / "probe.py"
    probe.write_text(
        "def f(registry, context, resolver, path, kind):\n"
        "    registry.resolve(kind)\n"
        "    context.registry.resolve(kind)\n"
        "    resolver.resolve(kind)\n"   # a DIFFERENT resolver -- must not match
        "    path.resolve()\n",          # pathlib -- must not match
        encoding="utf-8",
    )
    assert _registry_resolve_lines(probe) == [2, 3]
```

- [ ] **Step 2: Run it and read the real result**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q -k "resolves_a_class or actually_SEE"
```

**Do not predict this result — read it.** Expected after Task 5: PASS. If any module still appears, it is a producing site Task 5 missed — route it through `build` rather than exempting it. If a module calls `.resolve(x)` on something that is *not* an `EntityRegistry` (the `verdict/` pattern, were it ever to move into `graph/`), that is a genuine finding about the guard's precision: report it, and prefer narrowing the match (e.g. requiring the receiver to be named `registry`) over adding a module exemption.

- [ ] **Step 3: Run the guard alongside the full boundary file**

```bash
cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q
```
Expected: PASS.

- [ ] **Step 4: Lint, types, commit**

```bash
cd science && uv run ruff check && uv run pyright
git add science/tests/test_entity_construction_boundary.py
git commit -m "test(graph): guard the entity construction surface, deriving scope from the tree"
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

Expected: `test_an_unknown_key_SURVIVES_the_source_contract` FAILS (`model_extra` is `{}`) and `test_an_authored_shadow_key_SURVIVES_the_whole_load_path` FAILS. This proves the **loss** is prevented, at the contract and on the real path.

`test_a_shadow_key_reaches_the_normalized_mapping` is **expected to keep passing** and that is not a defect: it hands a dict straight to `normalize_structured_row`, so the source contract is not in its path. It pins normalization, not losslessness. This is exactly why Task 4 Step 7's end-to-end test exists — without it, this mutation would be caught only by a single unit assertion on a model config, and the pipeline could regress with the gate still green. **Revert.**

- [ ] **Step 6: Mutation 5b — drop the schema check from `registry.build`**

Remove the `_validate_against_schema(...)` line, leaving only the projection.
Expected: `test_build_validates_a_closed_kind_before_projecting` FAILS (no exception raised). This proves the **check runs**.

5a and 5b are both required and are not redundant: 5a proves the loss is prevented, 5b proves the check runs. An earlier design draft had only the second, which would have passed against a pipeline faithfully validating a mapping the toolkit had already stripped — a check that cannot fail. **Revert.**

- [ ] **Step 7: Mutation 5c — obtain an entity class outside `registry.build`**

Restore one resolve-then-construct pair: in `_load_structured_source_records` (`sources.py`), replace the `registry.build(...)` call with `registry.resolve(kind_name).model_validate(raw)`.
Expected: `test_NOTHING_in_the_loading_package_resolves_a_class_to_build_from` FAILS, naming `sources.py` and the line. **Revert.**

An *import* of an entity class is deliberately **not** the mutation here: twelve modules in `graph/` already import `Entity` legitimately, so an import cannot distinguish a violation from an annotation. The resolve call is the thing that precedes construction, and it is what the guard watches.

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
git add docs/conventions/schema-closure-slice-procedure.md science/src/science_tool/migrate_hypothesis.py
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

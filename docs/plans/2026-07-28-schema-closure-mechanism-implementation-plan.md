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
- **Every command in this plan starts at the repository root and leaves you there.** Package-scoped commands are therefore written as subshells — `(cd science && …)` — never as a bare `cd`. A bare `cd` persists across tool calls in some harnesses and not others, so the same block resolves differently depending on what ran before it: a second `cd science/model` lands in `science/science/model`, and the `git add` lines, which are all root-relative, silently stage nothing. If you see a bare `cd` anywhere below, it is a defect in this plan — fix it rather than working around it.
- **Test commands.** `(cd science && uv run --frozen pytest)` and `(cd science/model && uv run --frozen pytest)`. Never run two suites concurrently in the same worktree — they race on shared test-output paths.
- **The full `science/` suite takes ~2-3 min**, longer than the default 120s command timeout. Run scoped selections; reserve the full run for the top-level agent.
- **Lint/types.** `uv run ruff check` from the package you changed; `uv run pyright` from `science/` (one root config governs all three source trees).
- **Imports belong to the step that adds the code.** Every task ends with a `ruff check` gate over a file the previous tasks also wrote, and ruff's default rule set includes **F401** (imported but unused) and **F821** (undefined name). So import exactly what the snippet you are appending uses, at the step that appends it — an import staged early "because a later task needs it" fails the earlier task's own gate. `from __future__ import annotations` postpones *annotations* only: a name used in a runtime expression (`except ValidationError`, `pytest.raises`, a default value) must be imported for real. Where a snippet below needs a name the file does not yet have, the step says so explicitly; if you find one that does not, add the import — that is a defect in this plan, not a licence to omit it.
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
| `mixin-hypothesis-1.0.json` required | exactly `id`, `kind`, `status` — the fixture helpers are built from this, not guessed |
| a proven-valid pinned hypothesis record | `tests/test_undeclared_key_diagnostic.py:29-40` — copy it. `test_kind_reconciliation_registry.py` is 82 lines and has no project fixture at all |
| armed-schema loader | `load_project_schema_if_pinned(root)` returns None when unpinned — assert non-None in fixtures or every refusal test passes vacuously |
| `EntityRegistry.resolve` callers | **7+ test files**, not 4. Derive the set with a sweep; do not work from a list |
| `EntityRegistry.resolve` name collisions | `ReferenceResolver.resolve`, `Path.resolve` — which is why Task 5 renames it to `resolve_class` (**0** occurrences anywhere in the tree) |
| `_enrich_raw` injects | 18 keys via `setdefault`, incl. `evidence_refs=[]` (`sources.py:1005`) — so any assertion that a loaded entity has `evidence_refs == []` is INERT |
| ENTITY_SCHEMA rejection branch reads | `validation.schema` and `validation.error` only (`sources.py:604-613`) — never `authored_aliases` |
| local-profile selection key | `knowledge_profiles.local` (`project_config.py:26`); a top-level `local_profile` is silently ignored and defaults to `"local"` |
| composed hypothesis profile, gen 2 | **REFUSES** `type`, `canonical_id`, `file_path`, `evidence_refs`, `content`; **admits** `profile`, `aliases`, `ontology_terms`, `related`, `source_refs`. Measured against the real validator, not read off the JSON |
| `MarkdownAdapter.INJECTED_KEYS` | `{canonical_id, content, file_path}` — one adapter's contract, which `_validate_against_schema:1430` applied to every adapter. `type` is absent from it, so the closed structured path refused every record until Task 5 made `injected` a parameter |
| projects with `knowledge/sources/*/` | **5** — `natural-systems` (35 source files), `protein-landscape` (3), `seq-feats` (3), `3d-attention-bias` (2), and this repo's `meta/` |
| undeclared-key audit entry point | `audit_project_sources` (`graph/migrate.py:287`); `REFERENCE_FIELD_NAMES` at `:112`. There is no `graph/reference_fields` module |
| sites calling `_enrich_raw` before projecting | **5** — `sources.py:432` (markdown), `:1111`, `:1152`, `:1240`, `commons_sources.py:415`. Every one needs `build`'s `enrich` callback; none may keep enriching outside it |
| commons needs the CLASS pre-construction | `commons_sources.py:405` reads `"summary" in schema.model_fields` to decide the `description` → `summary` mapping, and `test_graph_commons_sources.py:294` (`test_translate_topic_description_flows_to_content_preview`) pins it with `assert not hasattr(entity, "summary")`. Answered by `declares_field`, not by handing the class back |
| `project_schema` reachability | computed at `sources.py:491` inside `load_project_sources`, which also calls all four remaining producing loaders — so it threads with one keyword each. Only the Markdown path receives it today (`CanonicalMarkdownContext.project_schema`, `:199`/`:518`) |
| `ProjectSchema` location | `science_tool.entity_profiles:58` — a **tool-side** class; there is no `science_model` `ProjectSchema` |
| `registry_for_project` | `graph/sources.py:376` — the fixture's registry constructor |
| ruff config, both packages | default rule set (only `line-length` is set), so **F401** and **F821** are live. F821 fires on annotations even under `from __future__ import annotations` |
| guard colour before Task 5 | **green, vacuously** — `resolve_class` does not exist yet and `graph/` constructs no entity class directly. Task 6 has no red first run; mutation 5c is its only one |

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
(cd science/model && uv run --frozen python -c "
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
s=[*CORE_PROFILE.entity_kinds,*LOCAL_PROFILE.entity_kinds]
missing=[k.name for k in s if 'schema_closed' not in k.model_fields_set]
print('shipped:',len(s),'undeclared:',missing)
print('closed:',sorted(k.name for k in s if k.schema_closed))
")
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

from science_model.entity_schema.profile import PROJECT_MIXIN_NAMES
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
(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py tests/test_value_reconciliation.py tests/test_hypothesis_entity.py -q)
```
Expected: PASS. Then run the whole model suite (it is fast): `(cd science/model && uv run --frozen pytest -q)`.

- [ ] **Step 8: Check the tool side still sees the same set**

```bash
(cd science && uv run --frozen pytest tests/test_kind_reconciliation.py tests/test_kind_reconciliation_registry.py tests/test_hypothesis_schema_reconciliation.py -q)
```
Expected: PASS, unchanged. These read `PROJECT_MIXIN_NAMES` and are the blast radius of Step 4.

- [ ] **Step 9: Lint, types, commit**

```bash
(cd science/model && uv run ruff check)
(cd science && uv run pyright)
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

Add these imports at the top of the file — `pytest` is used here for the first time, and Task 1 deliberately did not stage it:

```python
import pytest
from pydantic import ValidationError

from science_model.profiles.schema import ProfileManifest
```

Then append:

```python
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
(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q -k "external or packaged")
```
Expected: **two fail, two pass.** The selection matches four tests. The two that assert a rejection fail, because no rejection exists yet and `pytest.raises` sees nothing raised: `test_an_external_manifest_may_NOT_author_schema_closed` and `..._FALSE_either`. The other two already pass and are not supposed to change — `test_an_external_manifest_without_the_field_still_loads` (the field defaults to `False` and stays out of `model_fields_set` with or without this task) and `test_the_packaged_profiles_are_UNAFFECTED_by_the_rejection`. They are here as the controls that catch an over-broad rejection in Step 3, not as red tests.

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
(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)
```
Expected: PASS.

- [ ] **Step 5: Verify both real loaders reject, not just the model**

The tests above call `model_validate` directly. Prove the rejection reaches the two real entry points:

```bash
(cd science && uv run --frozen python -c "
import tempfile, pathlib, yaml
from science_model.profiles import load_profile_manifest
d = pathlib.Path(tempfile.mkdtemp())
p = d / 'profile.yaml'
p.write_text(yaml.safe_dump({'name':'x','imports':[],'relation_kinds':[],'strictness':'typed-extension',
  'entity_kinds':[{'name':'widget','canonical_prefix':'widget','layer':'local','description':'d','schema_closed':True}]}))
try:
    load_profile_manifest(p); print('MODEL LOADER: NOT REJECTED -- defect')
except Exception as e: print('MODEL LOADER rejected:', str(e)[:80])
")
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

Run: `(cd science && uv run --frozen pytest tests/test_local_kind_registration_reserved_fields.py -q)`
Expected: PASS. If `_validate_manifest_shape` does **not** reach `ProfileManifest.model_validate`, the first test fails — stop and report, because the single-site premise is then false.

- [ ] **Step 7: Lint, types, commit**

```bash
(cd science/model && uv run ruff check)
(cd science && uv run ruff check && uv run pyright)
git add science/model/src/science_model/profiles/schema.py science/model/tests/test_schema_closed_gate.py science/tests/test_local_kind_registration_reserved_fields.py
git commit -m "feat(profiles): refuse toolkit-reserved kind fields in external manifests"
```

---

### Task 3: Gates 1, 2 and 4

**Files:**
- Test: `science/model/tests/test_schema_closed_gate.py` (extend)

**Interfaces:**
- Consumes: `SHIPPED_KINDS`, `PROJECT_MIXIN_NAMES`, `_MIXIN_VERSION_BY_GENERATION` from Task 1; the packaged `mixin-*.json` files on disk.
- Produces: gates the Task 7 mutation matrix targets by name.

**These are the gates that can genuinely disagree.** Each compares the declaration against a hand-authored artifact: a generation row (authored in `profile.py`), a file on disk, a descriptor field.

- [ ] **Step 1: Write gate 1 — generation-row equality, per generation, commons excluded**

Extend the file's imports — Task 1 imported only `PROJECT_MIXIN_NAMES`, and everything below is used for the first time in this task. All of it goes in the **top-of-file import block**; an import placed above the function that uses it is ruff **E402**:

```python
import json
from importlib.resources import files

from science_model.entity_schema.profile import (
    COMMONS_MIXIN_NAMES,
    PROJECT_MIXIN_NAMES,
    _MIXIN_VERSION_BY_GENERATION,
)
```

`_BASE_VERSION_FOR_MIXIN` is deliberately **not** imported — see Step 2 for why the assertion that would have used it was removed as tautological. Importing it unused is F401.

Then append:

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

Both `json` and `files` were staged by Step 1's import block. Append:

```python
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


def test_GATE_2_every_armed_project_mixin_pins_its_own_kind() -> None:
    # The packaged mixin's `const` is the hand-authored artifact here. base-2.0 constrains `kind`
    # to a SHAPE only ("^[a-z][a-z0-9-]*$", with a $comment saying the mixin's const pins the
    # exact kind), so the const is the sole thing tying a composed schema to the kind it claims
    # to be. Copying mixin-hypothesis-1.0.json to mixin-<newkind>-1.0.json and forgetting to
    # change the const yields a schema that silently validates every record as a hypothesis --
    # the exact slice-author error, and one nothing else catches.
    #
    # Only files that EXIST are checked; a missing packaged file is the previous gate's finding,
    # and duplicating it here would report one defect as two.
    available = _packaged_schema_names()
    for generation, row in _MIXIN_VERSION_BY_GENERATION.items():
        for kind in set(row) - COMMONS_MIXIN_NAMES:
            name = f"mixin-{kind}-{row[kind]}.json"
            if name not in available:
                continue
            schema = json.loads(files("science_model.schemas").joinpath(name).read_text())
            assert schema.get("properties", {}).get("kind") == {"const": kind}, (
                f"generation {generation}: {name} does not pin kind to {kind!r}"
            )
```

**Why this replaced the base-version assertion.** A draft of this step asserted `_BASE_VERSION_FOR_MIXIN[name] == "2.0"` for every closed kind, describing that dict as "a third hand-maintained surface." It is not. `profile.py:101` builds it as `{**{n: "1.0" for n in COMMONS_MIXIN_NAMES}, **{n: "2.0" for n in PROJECT_MIXIN_NAMES}}` — so once Task 1 derives `PROJECT_MIXIN_NAMES` from `schema_closed`, the assertion reads a value the comprehension just wrote from the same set it is ranging over. It is the identity function, and it is the exact defect this file's docstring says every gate here must avoid. The reasoning behind it was sound — base 1.0 does enum-lock `kind` to `["dataset", "paper", "topic", "theme"]` (verified in `science-entity-base-1.0.json`), so a closed project kind under base 1.0 really would be structurally unvalidatable — but the derivation makes that unreachable, and an unreachable hazard needs no gate. The mixin `const` is the surface that can actually disagree.

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
(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)
```
Expected: PASS — verified before this plan was written, by running the mixin-const gate's logic against the packaged files: both armed project mixins (`mixin-hypothesis-1.0.json`, `mixin-hypothesis-2.0.json`) pin `{"const": "hypothesis"}`. If it fails, stop: a packaged mixin disagreeing with the kind it is armed for is a real finding, not a test to adjust.

- [ ] **Step 5: Lint, types, commit**

```bash
(cd science/model && uv run ruff check)
(cd science && uv run pyright)
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
from typing import Any

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
(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q)
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
(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q)
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
    # `knowledge_profiles.local`, NOT a top-level `local_profile`. `selected_local_profile_name`
    # (project_config.py:26) reads only the former and silently defaults to "local" -- so the
    # wrong key sends the loader to knowledge/sources/local, it never reads this manifest, and
    # the test dies on StopIteration with nothing to indicate the fixture was the problem.
    (root / "science.yaml").write_text(
        yaml.safe_dump({"name": "demo", "knowledge_profiles": {"local": "project_specific"}}),
        encoding="utf-8",
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


def _write_closed_kind_project(root: Path, rows: list[dict]) -> None:
    """A PINNED project whose local profile attaches a structured source to the core `hypothesis`.

    `core_structured_sources` (profiles/schema.py:56) is what attaches a data file to a core kind
    without registering or shadowing it -- the only way to get a CLOSED kind onto the structured
    path, which is what makes refusal demonstrable here at all.
    """
    _write_structured_project(root, [])
    # entity_schema_version: 2 is REQUIRED. Without the pin, `load_project_schema` returns None,
    # `validate_against_schema` returns on its first line, and the test passes for the wrong
    # reason -- no refusal, because no validation was ever armed.
    (root / "science.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "demo",
                "knowledge_profiles": {"local": "project_specific"},
                "entity_schema_version": 2,
            }
        ),
        encoding="utf-8",
    )
    sources_dir = root / "knowledge" / "sources" / "project_specific"
    manifest = yaml.safe_load((sources_dir / "manifest.yaml").read_text())
    manifest["core_structured_sources"] = [
        {"kind": "hypothesis", "structured_source": "hypothesis.yaml"}
    ]
    (sources_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (sources_dir / "hypothesis.yaml").write_text(
        yaml.safe_dump({"hypothesis": rows}), encoding="utf-8"
    )


def test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path(
    tmp_path: Path,
) -> None:
    # THE keystone of gate 3, and the only test that fails under BOTH mutation 5a and 5b.
    #
    # Every other end-to-end test here uses `widget`, an OPEN local kind -- so it can only show
    # that an extra survives, never that anything refuses it. Refusal needs a closed kind, and
    # `hypothesis` is the one this branch has.
    _write_closed_kind_project(tmp_path, [{**_valid_hypothesis_row(), "shadow_key": "v"}])
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        load_project_sources(tmp_path)


def test_the_same_closed_row_WITHOUT_the_shadow_key_loads(tmp_path: Path) -> None:
    # The other half, and not optional. Without it the test above passes on ANY fixture defect --
    # a wrong path, a missing required field, a kind that never registered -- while appearing to
    # prove something about shadow keys. This is what makes the pair a controlled comparison:
    # one key differs between the two fixtures, and only one of them raises.
    _write_closed_kind_project(tmp_path, [_valid_hypothesis_row()])
    sources = load_project_sources(tmp_path)
    assert any(e.canonical_id == _valid_hypothesis_row()["canonical_id"] for e in sources.entities)
```

And the row helper:

```python
def _valid_hypothesis_row() -> dict[str, Any]:
    """The same valid hypothesis, in STRUCTURED-ROW spelling.

    Two deliberate differences from the markdown mapping: `canonical_id` rather than `id` (the
    row authors the former; `normalize_structured_row` maps it), and no `kind` (authoritative
    from the manifest declaration, and in STRUCTURED_DROP_KEYS). `status` is not a declared field
    of `StructuredEntitySource` -- with extra="allow" from Step 3 it rides through as an extra,
    which is exactly the mechanism under test: it must ARRIVE at the composed schema, where the
    mixin requires it, rather than being stripped upstream.
    """
    return {
        "canonical_id": "hypothesis:h1",
        "title": "H1",
        "status": "active",
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }
```

`mixin-hypothesis-1.0.json` requires exactly `id`, `kind`, `status` — verified against the packaged file. `id` and `kind` are supplied by normalization and the loader backfills respectively, so `status` is the only one the row must carry.

If this row cannot be made to satisfy both `StructuredEntitySource` and the hypothesis mixin, **stop and report** — that would mean no closed kind is reachable on the structured path at all, which is a finding about the design, not something to work around by loosening the fixture.

Run: `(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q)`
Expected: PASS.

**Exactly ONE test gets the xfail marker**, and getting this wrong fails the suite:

- `test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path` → mark `@pytest.mark.xfail(strict=True, reason="composed validation on the structured path arrives in Task 5")`. Nothing validates on this path yet, so no refusal happens and it genuinely fails here.
- `test_the_same_closed_row_WITHOUT_the_shadow_key_loads` → **no marker.** After Step 6 this row already loads through `schema.model_validate`. Marking it `strict=True` produces XPASS, which `strict` turns into a suite failure — the negative control would break Task 4 at the moment it started working correctly.

Task 5 Step 9 removes the one marker. Because it is `strict=True`, forgetting fails the suite rather than leaving a silently-skipped test.

If `load_project_sources` needs more scaffolding than the helper above provides, read `tests/test_undeclared_key_diagnostic.py`'s `_write_project` for the established shape in this suite rather than inventing a second.

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
    # BOTH survive. `kind` is not a declared field of StructuredEntitySource (the declared set is
    # canonical_id/title/profile/source_path/description/domain/created/updated and the five list
    # fields -- verified), so under extra="allow" it is an extra like any other. It is dropped
    # LATER, by `normalize_structured_row`'s STRUCTURED_DROP_KEYS, and this assertion is upstream
    # of that. Asserting `{"method": "phantom"}` here would fail, and "fixing" it by dropping
    # `kind` at the contract would reintroduce the very loss Task 4 exists to remove.
    assert record.model_extra == {"kind": "workflow", "method": "phantom"}
```

- [ ] **Step 9: Measure the new warnings before accepting them**

The ruling above widens a **warning** surface across every project with structured sources. Warnings are not failures, but an unmeasured jump in them is how a diagnostic gets ignored.

**Measure the audit rows, not the YAML keys.** Counting reference-shaped keys across source files answers the wrong question twice over: it counts *declared* fields that were never extras, and it counts files no structured adapter loads. The only thing that matters is how many `undeclared_key` rows the audit actually emits — so run the audit, before and after.

**The five projects, enumerated.** These are every Dropbox-resident project with a `knowledge/sources/*/` tree, found with `ls -d ~/d/*/knowledge/sources` plus this repo's own `meta/`. Non-manifest source files in each, for scale:

| project | source files |
|---|---|
| `~/d/natural-systems` | 35 |
| `~/d/protein-landscape` | 3 |
| `~/d/seq-feats` | 3 |
| `~/d/3d-attention-bias` | 2 |
| `meta/` (in this repo) | present |

Re-run the discovery command before measuring — a project added since this plan was written belongs in the sweep, and a list is only a starting point.

**Running both revisions.** The comparison needs the audit executed by two different toolkit revisions against the same project files. Do it with a second worktree rather than by stashing, so the branch implementation stays intact:

```bash
BASE=$(git merge-base HEAD main)
git worktree add /tmp/schema-closure-base "$BASE"
```

Write the probe once, outside both trees, so each revision runs identical code:

```bash
cat > /tmp/undeclared-count.py <<'EOF'
import sys, pathlib
from science_tool.graph.sources import load_project_sources
from science_tool.graph.migrate import audit_project_sources
for arg in sys.argv[1:]:
    root = pathlib.Path(arg).expanduser()
    verdict = audit_project_sources(load_project_sources(root))
    rows = [r for r in verdict.rows if r["check"] == "undeclared_key"]
    print(f"{root.name}\t{len(rows)}\t{sorted({r['field'] for r in rows})}")
EOF
```

Then run it under each revision, from that revision's `science/` package:

```bash
PROJECTS="$HOME/d/natural-systems $HOME/d/protein-landscape $HOME/d/seq-feats $HOME/d/3d-attention-bias $PWD/meta"
(cd /tmp/schema-closure-base/science && uv run --frozen python /tmp/undeclared-count.py $PROJECTS) > /tmp/undeclared-before.tsv
(cd science && uv run --frozen python /tmp/undeclared-count.py $PROJECTS) > /tmp/undeclared-after.tsv
diff -u /tmp/undeclared-before.tsv /tmp/undeclared-after.tsv || true
```

Clean up with `git worktree remove /tmp/schema-closure-base` once the numbers are recorded.

`verdict.rows` and `r["check"]` are written from the shape `audit_project_sources` returns — a `ValidationVerdict[AuditRow]` (`graph/migrate.py:287`). **Read that type before running**, and adjust the two accessors if they differ; a probe that raises `AttributeError` measures nothing, and one that silently yields `[]` measures nothing while looking like good news. `REFERENCE_FIELD_NAMES` lives at `graph/migrate.py:112`, **not** in a `graph/reference_fields` module, which does not exist. Call the real path; a hand-rolled reimplementation of the `undeclared_key` predicate would measure your reimplementation, not the diagnostic.

**The threshold is 20 rows, per project.** If any single project gains **21 or more** `undeclared_key` rows, stop and report before committing — that is no longer a diagnostic widening but a corpus finding, and it needs a ruling this plan does not contain. Record the exact per-project delta either way; "no change" is a result worth writing down, and on four of these five projects it is the likely one.

- [ ] **Step 10: Run the structured-source and diagnostic suites**

```bash
(cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py tests/test_entity_construction_boundary.py -q)
(cd science && uv run --frozen pytest -q -k "structured_source or structured or sources" 2>&1 | tail -5)
```
Expected: PASS. Any **other** test asserting an unknown key is silently dropped is now wrong by design — repair it to assert the key survives, and record each one in your report. Do not relax an assertion to make it pass.

- [ ] **Step 11: Lint, types, commit**

```bash
(cd science/model && uv run ruff check)
(cd science && uv run ruff check && uv run pyright)
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
  - `EntityRegistry.resolve_class(kind: str) -> type[Entity]` — `resolve` renamed in Step 4
  - `EntityRegistry.declares_field(kind: str, field: str) -> bool` — the one field question commons needs, answered without handing out the class
  - `entity_registry.EntityProjectionError(kind, schema, error)` — a **module-level** `ValueError` subclass carrying the resolved class, beside the three exceptions already in that module. Not an attribute of `EntityRegistry`; import it by name.
  - `graph/entity_schema_validation.py` exposing `validate_against_schema` / `validate_dataset_gen3`

  Task 6's guard depends on **no `resolve_class` call surviving in `graph/`** outside the registry.

**Why `resolve` is the hole.** `EntityRegistry.resolve(kind)` returns `type[Entity]`. Handing out the class means any adapter — present or future — can construct an entity without validating. Merging resolution and construction into one operation is what makes the boundary enforceable: obtaining the class stops being how an entity gets built, and the five sites that do it today become zero, which is a property a guard can assert.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_entity_construction_boundary.py`:

```python
def test_build_validates_a_closed_kind_before_projecting(tmp_path) -> None:
    # The load-bearing order. `hypothesis` is the one closed kind on this branch, so it is what
    # can demonstrate refusal at all.
    #
    # `ValueError`, not EntityValidationError: `validate_against_schema` CATCHES the model-layer
    # EntityValidationError and re-raises a ValueError carrying the path and the pinned
    # generation (sources.py:1431, moved in Step 3). Asserting the inner type would fail.
    registry, project_schema = _armed_registry(tmp_path)
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        registry.build(
            "hypothesis",
            {**_valid_hypothesis_mapping(), "shadow_key": "v"},
            project_schema=project_schema,
            path="entities/hypotheses/0001-x.md",
            injected=frozenset(),
        )


def test_build_admits_a_valid_closed_kind(tmp_path) -> None:
    registry, project_schema = _armed_registry(tmp_path)
    entity = registry.build(
        "hypothesis",
        _valid_hypothesis_mapping(),
        project_schema=project_schema,
        path="entities/hypotheses/0001-x.md",
        injected=frozenset(),      # the mapping is entirely authored -- nothing to hide
    )
    assert entity.kind == "hypothesis"


def test_build_does_not_validate_an_OPEN_kind(tmp_path) -> None:
    # Open kinds keep loading exactly as before -- this branch closes nothing. A shadow key on an
    # open kind is preserved, not refused; that is the `extra="allow"` projection doing its job.
    registry, project_schema = _armed_registry(tmp_path)
    entity = registry.build(
        "concept",
        {**_valid_concept_mapping(), "shadow_key": "v"},
        project_schema=project_schema,
        path="entities/concepts/0001-x.md",
        injected=frozenset(),
    )
    assert entity.kind == "concept"
```

`path` is **required and positional-free on every call** — it is what puts the file name in the refusal message, and a default would let a caller silently produce `": hypothesis frontmatter does not satisfy its schema"`. Three calls, three paths.

These three helpers decide whether every closed-kind test above is a real check or a vacuous one, so they are written out rather than described. First extend the file's imports — `EntityRegistry` and `ProjectSchema` appear in `_armed_registry`'s return annotation, and ruff reports **F821 on annotations even under `from __future__ import annotations`** (verified). `Any` was staged by Task 4 Step 1:

```python
from science_tool.entity_profiles import ProjectSchema, load_project_schema_if_pinned
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import registry_for_project
```

(`ProjectSchema` is `science_tool.entity_profiles:58` — a tool-side class, **not** a `science_model` one. Verified.)

Then add them as module-level helpers in the same file:

```python
def _armed_registry(tmp_path: Path) -> tuple[EntityRegistry, ProjectSchema]:
    """A registry plus a project schema that is actually ARMED.

    The assert is the point. `load_project_schema_if_pinned` returns None for an unpinned
    project, `validate_against_schema` returns on its first line when handed None, and every
    refusal test in this file would then pass by never validating anything. A fixture that fails
    silently open is worse than no fixture.
    """
    root = tmp_path / "armed"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\nentity_schema_version: 2\n", encoding="utf-8")
    project_schema = load_project_schema_if_pinned(root)
    assert project_schema is not None, "fixture is not pinned; the refusal tests would be vacuous"
    return registry_for_project(root), project_schema


def _valid_hypothesis_mapping() -> dict[str, Any]:
    """A hypothesis mapping that passes `unevaluatedProperties: false` under base 2.0 + mixin 1.0.

    Not invented: this is the record `tests/test_undeclared_key_diagnostic.py:33-40` writes and
    loads through `load_project_sources` on a project pinned to `entity_schema_version: 2`, in a
    test asserting `hypothesis` is in `strict_schema_kinds` -- i.e. a record already proven to
    survive the closed path. `mixin-hypothesis-1.0.json` requires exactly `id`, `kind`, `status`;
    the rest are base-2.0-admitted and present because the proven fixture carries them.
    """
    return {
        "id": "hypothesis:h1",
        "kind": "hypothesis",
        "title": "H1",
        "status": "active",
        "related": [],
        "source_refs": [],
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }


def _valid_concept_mapping() -> dict[str, Any]:
    """The same, for the OPEN kind. `concept` has no mixin, so only base 2.0 applies."""
    return {
        "id": "concept:c1",
        "kind": "concept",
        "title": "C1",
        "status": "active",
        "related": [],
        "source_refs": [],
        "created": "2026-03-12",
        "updated": "2026-03-12",
    }
```

If `_valid_hypothesis_mapping()` does **not** pass `build` on an armed registry, stop and report: the closed path would then be refusing a record the existing suite proves it accepts, which is a finding about Task 1's derivation, not a fixture to adjust until it passes.

(`tests/test_kind_reconciliation_registry.py` is **not** a useful reference here — it is 82 lines and contains no temporary-project or schema setup at all. `tests/test_undeclared_key_diagnostic.py:29-40` is the pattern to follow.)

- [ ] **Step 2: Run it to verify it fails**

```bash
(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q -k build)
```
Expected: FAIL with `AttributeError: 'EntityRegistry' object has no attribute 'build'`.

- [ ] **Step 3: Extract the validators into their own module FIRST**

**The import cycle is certain, not contingent.** `sources.py:64` already does `from science_tool.graph.entity_registry import ... EntityRegistry`, so `entity_registry.py` importing anything from `sources.py` closes the loop. Do not attempt the import and see; extract first.

Create `science/src/science_tool/graph/entity_schema_validation.py` and **move** (not copy) `_validate_against_schema` (`sources.py:1401-1437`) and `_validate_dataset_gen3` (`sources.py:1440-1461`) into it, docstrings included, renamed to `validate_against_schema` / `validate_dataset_gen3`.

**One change during the move, and it is not cosmetic.** `_validate_against_schema:1430` reads:

```python
    authored = {key: value for key, value in raw.items() if key not in MarkdownAdapter.INJECTED_KEYS}
```

That is the Markdown adapter's contract applied to every adapter, and it is wrong in both directions — measured against the composed hypothesis profile, not reasoned about:

| mapping | composed schema says |
|---|---|
| the bare valid hypothesis | ACCEPTED |
| `+ type` (structured loader backfills it unconditionally) | **REFUSED** |
| `+ canonical_id` | REFUSED (in `INJECTED_KEYS`, so hidden today) |
| `+ file_path` | REFUSED (in `INJECTED_KEYS`, so hidden today) |
| `+ evidence_refs` (structured loader backfills `[]`) | **REFUSED** |
| `+ content` | REFUSED (in `INJECTED_KEYS`, so hidden today — **even when authored**) |
| `+ profile`, `+ aliases`, `+ ontology_terms` | ACCEPTED |

So the closed structured path is unreachable as the plan previously had it — `type` alone refuses every record, and Task 4's keystone negative control could not have passed. And in the other direction, an authored `content` on a structured hypothesis was stripped by this line and the record accepted: a silent drop inside the check whose entire purpose is to stop silent drops.

Take the set as a parameter instead:

```python
def validate_against_schema(
    raw: dict[str, Any],
    *,
    kind: str,
    path: str,
    project_schema: ProjectSchema | None,
    injected: frozenset[str],
) -> None:
```

and the body line becomes:

```python
    authored = {key: value for key, value in raw.items() if key not in injected}
```

Everything else moves verbatim, `validate_dataset_gen3` included and unchanged. `MarkdownAdapter` is then **not** a dependency of the new module — drop it from the import list below, and from `sources.py` only if nothing else there uses it (`:528` does, so it stays).

Their remaining dependencies are all cycle-free — verified against the tree:

| Dependency | From | Imports `entity_registry`? |
|---|---|---|
| `PROJECT_MIXIN_NAMES`, `EntityValidationError` | `science_model.entity_schema` | no (different package) |
| `ProjectSchema` | `science_tool.entity_profiles` | no |
| `gen3_shape_issue` | `science_tool.datasets.capability_shape` | no |

**The new module's header, in full.** A "move the bodies" instruction with no import block is not executable — the two functions between them need six names:

```python
"""The composed-schema checks, extracted from `sources.py` so the registry can call them.

They live here rather than in `sources.py` because `entity_registry.py` must call them and
`sources.py:64` already imports `EntityRegistry` -- importing back would close a cycle. This
module imports nothing from `sources.py` and nothing from `entity_registry.py`, which is what
keeps that true.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from science_model.entity_schema import PROJECT_MIXIN_NAMES, EntityValidationError

from science_tool.datasets.capability_shape import gen3_shape_issue

if TYPE_CHECKING:
    from science_tool.entity_profiles import ProjectSchema
```

`ProjectSchema` is annotation-only in both signatures, so it stays under `TYPE_CHECKING`; the other four are used at runtime. Copy the import *lines* from `sources.py` — `:47`, `:53` — rather than retyping the module paths. `MarkdownAdapter` (`:86`) is deliberately absent: the `injected` parameter replaced it, and importing a storage adapter into the validation module would be the coupling this change removes.

**What `sources.py` is left holding.** Checked per name against the post-move file, because F401 at Step 10 will find these anyway and the answer differs per name:

| name | after the move | action |
|---|---|---|
| `EntityValidationError` | used **only** by the moved function (`:1433`) | drop it from the `:47` import, keep `PROJECT_MIXIN_NAMES` |
| `gen3_shape_issue` | used **only** by the moved function (`:1457`) | delete the `:53` import line entirely |
| `PROJECT_MIXIN_NAMES` | still used at `:846` | keep |
| `MarkdownAdapter` | still used at `:528` | keep |
| `ProjectSchema` | still used at `:199` and in loader signatures | keep |

Then delete both definitions and add `from science_tool.graph.entity_schema_validation import validate_against_schema, validate_dataset_gen3`, updating its two call sites (`:411`, `:417`). Run `(cd science && uv run --frozen pytest -q -k "sources or schema" 2>&1 | tail -3)` and `(cd science && uv run ruff check)` before continuing — a move that changed behaviour or orphaned an import must surface here, not three steps later.

- [ ] **Step 4: Rename `resolve` to `resolve_class` — this is what makes Task 6 enforceable**

`EntityRegistry.resolve` shares its name with `ReferenceResolver.resolve` and `Path.resolve`, and a guard over the bare name `resolve` must then discriminate by *receiver variable name* — which enforces a naming convention, not a boundary. `reg.resolve(kind)` would slip straight through.

`resolve_class` is **unique in the tree** (verified: zero occurrences across `src/`, `tests/`, and `model/src/`). Renaming turns the guard's match from a heuristic into an exact one: any receiver spelling is caught, and `resolver.resolve(...)` / `path.resolve()` cannot false-positive.

Rename the method at `entity_registry.py:189`, then **derive** the caller set rather than working from a list. A first draft of this step named four test files; there are at least seven, and the two it missed (`test_extension_registration.py:26`, `test_kind_class.py:109`) would have surfaced as a full-suite failure three tasks later. Sweep:

```bash
(cd science && grep -rn '\.resolve(' src/ tests/ | grep -v '\.resolve()' | grep -v 'resolver\.')
```

Read every hit and classify it. Three populations, and only the first gets renamed:

1. **`EntityRegistry.resolve`** — the five producing sites (Steps 7–8 replace these with `build` anyway) plus the test files. Rename.
2. **`ReferenceResolver.resolve`** — `materialize.py` alone has 24. Leave alone.
3. **The claim registry** in `verdict/parser.py:64` and `verdict/rollup.py:108` — matches a `registry.resolve` grep but is a different object (`… is None`; `EntityRegistry.resolve` raises, never returns None). Leave alone; if renaming appears to break it, **stop**, because the premise that they are separate is then false.

```bash
(cd science && uv run --frozen pytest -q -k "registry or kind_class or extension_registration or book_kind or talk_kind or undeclared_key" 2>&1 | tail -5)
```
Expected: PASS. Then confirm nothing was missed inside the loading package:

```bash
(cd science && grep -rn '\.resolve_class(\|\.resolve(' src/science_tool/graph/ | grep -v 'resolver\.\|\.resolve()')
```

Every hit must be a `resolve_class` one. The pattern has to name `resolve_class` explicitly — a bare `\.resolve(` no longer matches the renamed method, so the earlier spelling of this check would have reported "clean" by finding nothing at all. The `src/` path is relative to `science/`, which is why the whole thing is a subshell.

- [ ] **Step 5: Implement `build`**

**Match the moved signature exactly.** `validate_against_schema` is `(raw: dict[str, Any], *, kind: str, path: str, project_schema: ProjectSchema | None)` — `raw` is positional, `kind` and `path` are keyword-only, and `path` is `str`, not `Path`.

This is the **only** place in the plan that defines `build`, deliberately: an earlier draft showed it twice and the two copies drifted apart within one revision. Step 7 explains the `enrich` parameter and shows the Markdown call site, but does not restate the method.

Two things to place correctly. First, a **module-level** exception in `entity_registry.py`, beside the three that are already there (`EntityKindAlreadyRegisteredError` and friends at `:42-53`):

```python
class EntityProjectionError(ValueError):
    """A mapping that resolved and passed its composed schema, then failed the model projection.

    Carries the resolved class because the Markdown reader formats its rejection from it. Without
    this, the only way for a caller to obtain the class would be `resolve_class` -- reopening the
    exact hole `build` exists to close, in the one branch nobody reads.
    """

    def __init__(self, kind: str, schema: type[Entity], error: ValidationError) -> None:
        super().__init__(f"{kind}: entity projection failed")
        self.kind = kind
        self.schema = schema
        self.error = error
```

Second, a method **inside `class EntityRegistry`**, at the same indentation as `resolve_class` — not nested under the exception above:

```python
    def build(
        self,
        kind: str,
        raw: dict[str, Any],
        *,
        project_schema: "ProjectSchema | None",
        path: str,
        injected: frozenset[str],
        enrich: "Callable[[dict[str, Any]], frozenset[str]] | None" = None,
    ) -> Entity:
        """Validate a raw mapping against its composed profile, THEN project it onto the model.

        Resolution and construction are ONE operation on purpose. Handing out `type[Entity]` is
        the hole: an adapter that can get the class can construct an entity without validating.
        Merging them means a new adapter cannot skip the check, because obtaining the class is no
        longer how you build an entity. `resolve_class` stays public for callers that genuinely
        need the TYPE, and Task 6 guards the construction surface rather than the import surface
        -- because twelve modules in this package legitimately reference `Entity` for annotations
        and isinstance checks, and only the five that RESOLVE-then-construct are the hole.

        The ORDER is this method's contract, and why `enrich` is a parameter rather than the
        caller's business: enrichment injects eighteen keys the author never wrote, and a
        composed schema shown those keys under `unevaluatedProperties: false` would refuse
        records that did nothing wrong. Validate authored -> enrich -> project. Every adapter
        gets that order by construction instead of re-deriving it.

        `injected` is the same argument one layer down, and it is REQUIRED because there is no
        safe default. Enrichment is not the only bookkeeping: every adapter also assembles keys
        of its own before `build` is reached, and each assembles a DIFFERENT set. The moved
        validator used to subtract `MarkdownAdapter.INJECTED_KEYS` universally, which is one
        adapter's contract applied to all of them -- wrong in both directions, measured against
        the composed hypothesis schema:
          - the structured loader backfills `type`, and `type` is REFUSED. Every closed
            structured record would fail for a key no author wrote. So would `canonical_id`,
            `file_path`, and an unconditionally-backfilled `evidence_refs`.
          - `content` is stripped for everyone, so an AUTHORED `content` on a structured record
            was silently removed and the record accepted -- the fail-silent this programme exists
            to abolish, sitting inside the check meant to abolish it.

        A caller passes the keys IT contributed and the author did not. The subtraction happens
        at the call site because that is the only place both are known; hiding a key the author
        actually wrote is the failure mode, and it is why this is not a per-adapter constant.

        Raises EntityKindNotRegisteredError (unknown kind), ValueError (composed-schema refusal),
        or EntityProjectionError (projection refusal) -- three distinct failures, kept distinct so
        the Markdown adapter can keep classifying them into its three rejection codes.
        """
        schema = self.resolve_class(kind)
        validate_against_schema(
            raw, kind=kind, path=path, project_schema=project_schema, injected=injected
        )
        validate_dataset_gen3(raw, kind=kind, path=path, project_schema=project_schema)
        authored_aliases = enrich(raw) if enrich is not None else frozenset()
        try:
            entity = schema.model_validate(raw)
        except ValidationError as exc:
            raise EntityProjectionError(kind, schema, exc) from exc
        entity._authored_aliases = authored_aliases
        return entity
```

`resolve_class` — **the renamed method from Step 4**, not `resolve`, which no longer exists. It is called **before** validation so an unknown kind raises `EntityKindNotRegisteredError` rather than being schema-validated first; that ordering is what the Markdown path's `UNKNOWN_KIND` classification depends on.

**The imports this needs, in full.** `entity_registry.py` today imports `Entity` and the `*Entity` classes and nothing else this snippet uses — four of the five names below are new. Getting the runtime/`TYPE_CHECKING` split wrong is not cosmetic: `except ValidationError` is evaluated when the exception fires, so a `TYPE_CHECKING`-only import turns every projection failure into `NameError`.

```python
from typing import TYPE_CHECKING, Any                      # runtime: Any is used in annotations

from pydantic import ValidationError                       # runtime: caught in an `except` clause

from science_tool.graph.entity_schema_validation import (  # runtime: called
    validate_against_schema,
    validate_dataset_gen3,
)

if TYPE_CHECKING:                                          # annotations only, both quoted
    from collections.abc import Callable

    from science_tool.entity_profiles import ProjectSchema
```

**Third, one narrow query — `declares_field`.** Add it beside `resolve_class`, same indentation:

```python
    def declares_field(self, kind: str, field: str) -> bool:
        """Does this kind's model DECLARE `field`? A field question, not a class handout.

        Commons normalization needs exactly this and nothing more: `commons_sources.py:405` maps
        `description` -> `summary` only for kinds that actually declare `summary`, because on a
        `topic` (which does not) the key used to be silently eaten at `model_validate`, and with
        the projection now preserving what it admits, an eaten key becomes a kept one --
        `materialize._add_entity` reads `getattr(entity, "summary", "")` into
        `schema:description`, so every commons topic would start emitting a triple it has never
        had. That drop is load-bearing, and it has to happen BEFORE construction.

        Answering the question directly is what keeps `build` the only way to obtain a class. The
        alternative -- handing the class back so the caller can read `model_fields` -- is
        `resolve_class` by another name, and Task 6's guard would be green over a reopened hole.
        """
        return field in self.resolve_class(kind).model_fields
```

`resolve_class` is called here, inside the registry module, which is the one module Task 6's guard excludes — by construction, not by exemption.

`ProjectSchema` and `Callable` stay under `TYPE_CHECKING` — `entity_profiles` is a heavier import than the registry needs at runtime, and both annotations are already written as strings in the signature above. `Any` is imported for real because ruff reports **F821 on annotations even under `from __future__ import annotations`**.

`validate_against_schema` already carries the `kind not in PROJECT_MIXIN_NAMES` gate (moved from `sources.py:1428`), so an open kind passes through untouched.

(Step 3 already ruled on the imports the move orphans in `sources.py` — `EntityValidationError` and `gen3_shape_issue`. Nothing further is owed here.)

- [ ] **Step 6: Run the tests to verify they pass**

```bash
(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q)
```
Expected: PASS.

- [ ] **Step 7: Give `build` the two things the Markdown path would otherwise lose**

The Markdown path is not a resolve-then-validate pair that collapses into one call. `validate_canonical_markdown_record` (`sources.py:382-456`) does four things a flat `build` would destroy, and **both** must be handled before Step 6 touches any call site:

**(a) Enrichment sits BETWEEN validation and projection.** The real order is validate authored mapping → `_enrich_raw` (which mutates the mapping and returns `authored_aliases`) → `model_validate`. Validating after enrichment would show the composed schema the eighteen keys `_enrich_raw` injects (`sources.py:1000-1015`: `evidence_refs`, `related`, `same_as`, `xrefs`, `scope`, `provisional`, …), and under `unevaluatedProperties: false` those become refusals of records that did nothing wrong. So `build` takes the enrichment as a parameter and owns the order — the point being that the order stops being each adapter's private property.

**(b) Three failures must stay three failures.** The path classifies `UNKNOWN_KIND`, `PROJECT_SCHEMA`, and `ENTITY_SCHEMA` separately, and the `ENTITY_SCHEMA` branch (`sources.py:604-613`) needs the resolved **class** to format its message via `_format_schema_validation_failure`. `resolve_class` raising and `validate_against_schema` raising `ValueError` separate the first two; a typed exception carries the class for the third.

**The alias question is ruled here, not left to the implementer.** `authored_aliases` are **not** carried on the projection-failure branch. Verified at `sources.py:604-613`: the `ENTITY_SCHEMA` branch reads `validation.schema` and `validation.error` and nothing else — there is no entity to attach aliases to, and every consumer of that branch formats an error or skips. `build` therefore assigns `_authored_aliases` only on the success path.

`build` and `EntityProjectionError` were both written in full in Step 5 — including the `enrich` parameter this section explains. Do not restate them here.

This is the complete Markdown call site, replacing `sources.py:403-451`. The closure is what adapts `_enrich_raw`'s six-argument signature to the one-argument callback, so `build` needs to know nothing about markdown context:

```python
    def _enrich(candidate_raw: dict[str, Any]) -> frozenset[str]:
        return _enrich_raw(
            candidate_raw,
            kind=kind,
            project_slug=context.project_slug,
            local_profile=context.local_profile,
            active_kinds=context.active_kinds,
            ontology_catalogs=context.ontology_catalogs,
        )

    try:
        entity = context.registry.build(
            kind,
            candidate,
            project_schema=context.project_schema,
            path=path,
            injected=MarkdownAdapter.INJECTED_KEYS,
            enrich=_enrich,
        )
    except EntityKindNotRegisteredError:
        return CanonicalMarkdownValidation(kind=kind, rejection=CanonicalMarkdownRejection.UNKNOWN_KIND)
    except EntityProjectionError as exc:
        # No authored_aliases: verified that this branch (sources.py:604-613) reads only `schema`
        # and `error`. There is no entity to carry them on.
        return CanonicalMarkdownValidation(
            kind=kind,
            schema=exc.schema,
            rejection=CanonicalMarkdownRejection.ENTITY_SCHEMA,
            error=exc.error,
        )
    except ValueError as exc:
        return CanonicalMarkdownValidation(
            kind=kind, rejection=CanonicalMarkdownRejection.PROJECT_SCHEMA, error=exc,
        )
    return CanonicalMarkdownValidation(
        kind=kind,
        schema=type(entity),
        entity=entity,
        authored_aliases=entity._authored_aliases,
    )
```

**Markdown passes `MarkdownAdapter.INJECTED_KEYS` with no subtraction, deliberately.** That is exactly what the moved validator did for this path, so the Markdown behaviour is unchanged and this branch stays behaviourally inert there — which is the whole premise of the mechanism tranche. It does leave one residual: an author who writes `content:` in Markdown frontmatter still has it hidden from validation. That is a real hole, it is **pre-existing**, it is now confined to one adapter instead of applying to all of them, and closing it changes what the Markdown path accepts — so it belongs to a slice, not here. Record it in the plan's follow-up section rather than fixing it in passing.

`sources.py` needs `EntityProjectionError` added to its existing `from science_tool.graph.entity_registry import …` at `:64` — `EntityKindNotRegisteredError` is already there. `commons_sources.py:32` imports from the same module and needs it too if its `build` call catches projection failures.

**Order matters in that `except` chain:** `EntityProjectionError` subclasses `ValueError`, so it must be caught first. The `PROJECT_SCHEMA` branch drops `schema=` — verified against its consumer at `sources.py:598-603`, which reads only `.error` and re-raises it.

- [ ] **Step 8: Route the other four producing sites through `build`**

**Every one of these four enriches before projecting today** — `sources.py:1111`, `:1152`, `:1240`, and `commons_sources.py:415`, verified by grep. So every one gets an `enrich` closure; leaving `_enrich_raw` outside the call would put enrichment *before* validation and break the order Step 7(a) exists to enforce, and dropping it would lose both the eighteen defaults and `authored_aliases`. Each closure is written out below rather than described as "same as Markdown", because the arguments differ per site.

**Each also declares its own bookkeeping keys.** Step 5 made `injected` a required parameter; here is where the three non-Markdown values come from. Add these two module-level constants to `sources.py`, beside the other loader constants:

```python
# Keys these loaders ASSEMBLE rather than read from the author. Only the ones the composed schema
# refuses need listing -- `profile`, `aliases`, `ontology_terms`, `related` and `source_refs` are
# admitted (measured), so hiding them would only widen the blind spot. `id`, `kind` and `title`
# are NOT here on purpose: they are policy values for real schema fields, and the schema requires
# all three, so hiding them would refuse every record for a missing key the loader had supplied.
_STRUCTURED_INJECTED_KEYS: frozenset[str] = frozenset(
    {"canonical_id", "type", "file_path", "evidence_refs"}
)
_LEGACY_INJECTED_KEYS: frozenset[str] = _STRUCTURED_INJECTED_KEYS
```

and in `commons_sources.py`:

```python
# Commons assembles `scope`/`profile` and rewrites `file_path`; `summary` is DERIVED from the
# record's `description` at :405 and is likewise not the author's key.
_COMMONS_INJECTED_KEYS: frozenset[str] = frozenset(
    {"canonical_id", "type", "file_path", "evidence_refs", "scope", "summary"}
)
```

**`authored` is computed, never assumed, and the subtraction is the whole safety property.** At each site it is the set of keys the *record* carried before the loader touched anything:

```python
        authored = frozenset(record.model_dump(exclude_unset=True))
```

Compute it immediately after loading `record`, before assembling `raw`. Commons uses `frozenset(fm)` — the record's own frontmatter — which is already in scope at `_materialize_commons_candidate:385`.

Without the subtraction, an author who writes `evidence_refs: [paper:x]` on a closed structured record has it hidden from validation and silently accepted, which is the exact defect this change removes from the Markdown side. **Verified**, against the real composed hypothesis profile: with the subtraction, the valid control is ACCEPTED and each of `shadow_key`, an authored `content`, and an authored `evidence_refs` is REFUSED.

**(a) `model` — `sources.py:1111-1122`.** Replace the `_enrich_raw` / `resolve` / `model_validate` / `_authored_aliases` block with:

```python
        def _enrich(candidate_raw: dict[str, Any]) -> frozenset[str]:
            return _enrich_raw(
                candidate_raw,
                kind="model",
                project_slug=project_slug,
                local_profile=local_profile,
                active_kinds=active_kinds,
                ontology_catalogs=ontology_catalogs,
            )

        entity = registry.build(
            "model",
            raw,
            project_schema=project_schema,
            path=record.source_path,
            injected=_LEGACY_INJECTED_KEYS - authored,
            enrich=_enrich,
        )
```

**(b) `canonical_parameter` — `sources.py:1150-1161`.** This site currently resolves at `:1150` **before** enriching at `:1152`; `build` collapses both, so the `schema: type[Entity] = registry.resolve(...)` line is deleted rather than left as an unused local.

```python
        def _enrich(candidate_raw: dict[str, Any]) -> frozenset[str]:
            return _enrich_raw(
                candidate_raw,
                kind="canonical_parameter",
                project_slug=project_slug,
                local_profile=local_profile,
                active_kinds=active_kinds,
                ontology_catalogs=ontology_catalogs,
            )

        entity = registry.build(
            "canonical_parameter",
            raw,
            project_schema=project_schema,
            path=record.source_path,
            injected=_LEGACY_INJECTED_KEYS - authored,
            enrich=_enrich,
        )
```

**(c) structured source — `sources.py:1240-1249`.** `kind` is a loop variable here, so the closure closes over `kind_name`. `path` is the same expression the `SourceRef` on the following line already uses.

```python
            def _enrich(candidate_raw: dict[str, Any], _kind: str = kind_name) -> frozenset[str]:
                return _enrich_raw(
                    candidate_raw,
                    kind=_kind,
                    project_slug=project_slug,
                    local_profile=local_profile,
                    active_kinds=active_kinds,
                    ontology_catalogs=ontology_catalogs,
                )

            entity = registry.build(
                kind_name,
                raw,
                project_schema=project_schema,
                path=record.source_path or default_path,
                injected=_STRUCTURED_INJECTED_KEYS - authored,
                enrich=_enrich,
            )
```

The `_kind: str = kind_name` default is deliberate, not stylistic: this closure is defined **inside a loop**, and a bare `kind_name` reference would be looked up when the closure runs, not when it is created. `build` calls `enrich` immediately, so late binding happens to be harmless today — but it is harmless by accident, and binding at definition costs one parameter.

**(d) commons — `commons_sources.py:395-423`.** Two edits here, not one. First, `:395` `schema = registry.resolve(kind)` is deleted, and `:405`'s condition becomes a field question:

```python
    if "description" in fm and "summary" not in fm and registry.declares_field(kind, "summary"):
        raw["summary"] = fm["description"]
```

This is the only site that needed the class for something other than construction, and it is why `declares_field` exists (Step 5). Then `:415-423`:

```python
    def _enrich(candidate_raw: dict[str, object]) -> frozenset[str]:
        return _enrich_raw(
            candidate_raw,
            kind=kind,
            project_slug=project_slug,
            local_profile="shared",
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )

    return registry.build(
        kind,
        raw,
        project_schema=project_schema,
        path=str(record.body_path),
        injected=_COMMONS_INJECTED_KEYS - frozenset(fm),
        enrich=_enrich,
    )
```

**Two direct test callers break here, and they are not in this task's file list yet — add them.** `tests/test_graph_commons_sources.py` calls both threaded functions itself: `_closure` (`:82`) calls `collect_commons_contributions`, and `_translate` (`:262`) calls `_materialize_commons_candidate`. A new required keyword-only parameter makes both a `TypeError` at collection time. Give each helper `project_schema=None` — these fixtures load unpinned commons records, where `None` is the honest value rather than a validation opt-out, and every existing assertion in that file is about translation, not schema refusal. Add `science/tests/test_graph_commons_sources.py` to Step 10's `git add`. The `-k commons` selection in Step 9 runs this file, so getting it wrong surfaces there — but fix it here, where the signature changes.

Note the ordering constraint this site carries: the `description` → `summary` mapping, the `journal` → `venue` mapping, the `scope`/`profile`/`file_path` assignments, and the `_OVERLAY_ONLY_FIELDS` pops all happen at `:396-414`, **before** `build` is called — they shape the authored mapping into the one that gets validated. They are not enrichment and must not move into the closure; an overlay-only key left in place would be refused by a closed kind for a reason the author cannot act on.

Each site therefore becomes one `registry.build(kind, raw, project_schema=..., path=..., enrich=...)` call, and **no `resolve_class` call may remain in `src/science_tool/graph/`** — Task 6's guard asserts exactly that, and the five sites listed across Steps 5 and 6 are the complete set (verified: `grep -rn 'registry\.resolve' src/` finds these five in `graph/`, plus two in `verdict/` that are a different registry object entirely — `registry.resolve(claim_id) is None` cannot be `EntityRegistry.resolve`, which raises).

**None of the four has `project_schema` in scope today — thread it, and do not pass `None` to make the call compile.** `validate_against_schema` returns on its first line when handed `None` (`sources.py:1428`), so a `None` here would leave every one of these paths validating nothing while the guard went green. Only the Markdown path receives it, via `CanonicalMarkdownContext.project_schema` (`sources.py:199`, set at `:518`). The source is `load_project_sources`, which computes `project_schema` at `sources.py:491` and calls all four loaders inside its own body — so the value is one keyword away at every call site. Three threads:

1. `_load_legacy_records` (`sources.py:1076`) — add `project_schema: ProjectSchema | None` to its keyword-only parameters; the caller at `sources.py:689` passes `project_schema=project_schema`.
2. `_load_structured_source_records` (`sources.py:1167`) — same, caller at `sources.py:698`.
3. Commons is three hops, because the candidate is materialized from a collector object: `collect_commons_contributions` (`commons_sources.py:82`, called from `sources.py:748`) gains the parameter, passes it to `_CommonsClosureCollector.__init__` (`:116`) which stores `self._project_schema`, and `collect` passes it to `_materialize_commons_candidate` (`:184`) which gains it too.

If any of the three turns out **not** to have `project_schema` reachable without restructuring, stop and report — a producing path that cannot see the project's pinned generation is a finding about the loader's shape, not something to paper over with `None`.

- [ ] **Step 9: Remove the Task 4 xfail marker, add the validation-spy test, run the suites**

Task 4 left **one** test marked `@pytest.mark.xfail(strict=True)` because it needs composed validation on the structured path, which now exists: `test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path`. Delete that marker. (Its negative control was deliberately left unmarked — see Task 4 Step 7.) Because the xfail is `strict=True`, forgetting fails the suite rather than leaving a silently-skipped test, but delete it deliberately rather than waiting to be told.

Then add the validation-spy test that Task 4 could not host, because it needs both `graph/entity_schema_validation.py` (created in Step 3) and the structured path routed through `build` (Step 8):

```python
def test_an_unauthored_optional_field_is_absent_from_what_VALIDATION_SEES(
    tmp_path: Path, monkeypatch
) -> None:
    # The defaults-promotion failure. Asserting `entity.evidence_refs == []` on the loaded entity
    # would be INERT: `_enrich_raw` (sources.py:1005) does `raw.setdefault("evidence_refs", [])`
    # on every record, so that assertion holds whether the value was authored, promoted from the
    # source-model default, or injected by enrichment. It cannot fail, and a probe that cannot
    # fail proves nothing. The claim is about the mapping VALIDATION is shown, upstream of
    # enrichment -- so spy on that.
    #
    # Patch the CONSUMER binding, not the defining module. `entity_registry` does
    # `from ...entity_schema_validation import validate_against_schema` at import time, so it
    # holds its own reference; patching `entity_schema_validation.validate_against_schema` would
    # leave the name `build` actually calls untouched and the spy would record nothing --
    # collecting zero mappings and then failing on `next()`, which reads like a fixture bug.
    import science_tool.graph.entity_registry as reg_mod

    # Record the AUTHORED VIEW -- `raw` minus `injected` -- because that is the mapping the
    # validator ranges over. Spying on `raw` alone would assert the wrong thing now that
    # bookkeeping is subtracted inside the validator rather than absent from `raw`: the structured
    # loader backfills `evidence_refs` unconditionally, so it IS in `raw` and is supposed to be.
    seen: list[dict] = []
    real = reg_mod.validate_against_schema

    def _spy(raw, **kw):
        seen.append({k: v for k, v in raw.items() if k not in kw["injected"]})
        return real(raw, **kw)

    monkeypatch.setattr(reg_mod, "validate_against_schema", _spy)
    _write_structured_project(tmp_path, [{"canonical_id": "widget:0002-y", "title": "W2"}])
    load_project_sources(tmp_path)

    row = next(m for m in seen if m.get("id") == "widget:0002-y")
    assert "evidence_refs" not in row, "an unauthored field reached validation as an authored one"
    assert row["title"] == "W2"  # the authored ones DO arrive -- not a vacuously empty mapping
```

Then the two boundary controls, which also belong here rather than in Task 4: both need `_STRUCTURED_INJECTED_KEYS`, which Step 8 creates, and one needs composed validation on the structured path, which Step 8 wires.

```python
def test_the_loaders_OWN_bookkeeping_keys_do_not_refuse_the_row(tmp_path: Path) -> None:
    # The control above passes only if `type`, `canonical_id`, `file_path` and the backfilled
    # `evidence_refs` are hidden from the composed schema -- MEASURED: each is refused by the
    # hypothesis profile, and the structured loader adds all four to every row. This test asserts
    # the same thing from the other side, so the reason the control passes is pinned rather than
    # incidental. If `_STRUCTURED_INJECTED_KEYS` loses an entry, this is what says which one.
    from science_tool.graph.sources import _STRUCTURED_INJECTED_KEYS

    assert {"type", "canonical_id", "file_path", "evidence_refs"} <= _STRUCTURED_INJECTED_KEYS
    assert not {"id", "kind", "title"} & _STRUCTURED_INJECTED_KEYS, (
        "id/kind/title are REQUIRED by the composed schema; hiding them refuses every record"
    )


def test_an_AUTHORED_bookkeeping_key_is_still_refused(tmp_path: Path) -> None:
    # The opposing control, and the one that makes `injected` a subtraction rather than a constant.
    # `content` is bookkeeping for the Markdown adapter, which injects the body under that name.
    # It is NOT bookkeeping here: a structured row authoring `content` authored it, `hypothesis`
    # does not declare it, and the composed schema refuses it (measured). Before this branch, the
    # validator stripped `content` for every adapter unconditionally, so this row was silently
    # accepted -- a fail-silent living inside the check that exists to end fail-silence.
    _write_closed_kind_project(tmp_path, [{**_valid_hypothesis_row(), "content": "prose"}])
    with pytest.raises(ValueError, match="does not satisfy its schema"):
        load_project_sources(tmp_path)
```

Together with the keystone pair from Task 4, these make the authored/bookkeeping boundary checkable in **both** directions: bookkeeping the loader added must not refuse a clean record, and a key the author actually wrote must never be hidden because some *other* adapter treats that name as bookkeeping.

If `build` ends up calling `validate_against_schema` through a module reference rather than a direct import, patch whatever binding it actually uses — the rule is *patch the name the caller resolves*, and the failure mode of getting it wrong (an empty `seen`) looks like a broken fixture rather than a broken patch.

```bash
(cd science && uv run --frozen pytest tests/test_kind_reconciliation_registry.py tests/test_entity_construction_boundary.py -q)
(cd science && uv run --frozen pytest -q -k "sources or commons or graph_build or registry or markdown" 2>&1 | tail -5)
```
Expected: PASS. The Markdown rejection-classification tests are the ones at risk here — if any of the three rejection codes stops being produced, this is where it shows.

- [ ] **Step 10: Lint, types, commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/graph/entity_registry.py science/src/science_tool/graph/entity_schema_validation.py science/src/science_tool/graph/sources.py science/src/science_tool/graph/commons_sources.py science/tests/test_entity_construction_boundary.py science/tests/test_graph_commons_sources.py
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

The import surface was also the wrong surface. Importing `Entity` for an annotation constructs nothing. **Obtaining a class in order to build from it** is the hole, and it has more spellings than any list will hold: `registry.resolve_class(kind)`, `MethodEntity(**raw)`, `MethodEntity.model_validate(raw)`, `entities.MethodEntity(**raw)`, and `ME(**raw)` after `import … as ME`. Three drafts of this guard matched AST *shape* and missed one of these each time — which is the same enumerated-scope hole in a new costume. The guard therefore reduces every call target to its dotted segments and asks one question of all of them.

**Why the rename in Task 5 Step 4 is what makes this work.** A first attempt matched the bare name `resolve` and, to avoid the 24 `resolver.resolve(...)` calls in `materialize.py`, discriminated by whether the receiver variable was named `registry`. That enforces a naming convention: `reg.resolve(kind)` passes. `resolve_class` occurs nowhere else in the tree, so the match becomes exact and receiver-independent, and `test_the_guarded_METHOD_still_exists` stops a rename from silently disarming it.

**What this guard does and does not claim.** It makes the two known bypasses fail and derives its scope from the package tree, so a sixth adapter is inside it automatically. It is not a proof of impossibility — `getattr(registry, "resolve_" + "class")` would evade any AST rule. The durable barrier is that `build` is the only operation that returns a *validated* entity; the guard raises the cost of routing around it from "write different code" to "write deliberately obfuscated code."

Measured before this revision:

| `registry.resolve` call sites in `src/science_tool/graph/` | 5 — `sources.py:404`, `:1119`, `:1150`, `:1216`; `commons_sources.py:395` |
| After Task 5 routes all five through `build` | **0** |
| Elsewhere in `src/` | `verdict/parser.py:64`, `verdict/rollup.py:108` — a **different** registry object (`registry.resolve(claim_id) is None`; `EntityRegistry.resolve` raises, never returns None) |

**This guard does not go red-then-green, and pretending otherwise would be the more dangerous story.** Measured against the tree: it reports **zero offenders today**, because the five producing sites call `registry.resolve`, and the name it matches — `resolve_class` — does not exist until Task 5 Step 4 renames it. After Task 5 it also reports zero, this time because the sites are gone. Two green runs for opposite reasons, which is exactly the shape of a gate that asserts nothing.

What supplies the missing evidence is therefore not this test's own history but the two beside it: `test_the_guarded_METHOD_still_exists` (the name is load-bearing — a rename back to `resolve` would silence every match) and `test_the_guard_can_actually_SEE_every_violation_spelling` (the detector matches what it claims to). Mutation 5c is the red run, and it is the only one. Do not write this task expecting a failing first run.

Scope stays derived from the package tree — `graph/` is the entity-loading package and every producing site lives in it — not from a list of modules.

- [ ] **Step 1: Write the guard, its probe, and its rename tripwire together**

Add `import ast` **to the file's import block at the top** — Task 4 Step 1 created that block, and an import placed here, after four tasks' worth of functions, is ruff **E402**. Then append:

```python
_REGISTRY_MODULE = "entity_registry.py"


def _entity_loading_package() -> Path:
    return Path(__file__).resolve().parents[1] / "src" / "science_tool" / "graph"


def _entity_class_names() -> frozenset[str]:
    """Every concrete entity model name, DERIVED -- 24 of them, not a literal list.

    `endswith("Entity")` was tried and is wrong: it matches `SkippedEntity`, a plain dataclass
    constructed five times in `sources.py`, and the guard would have failed on it forever with no
    way out but an exemption. Ask the model package which classes are actually entities.
    """
    import science_model.entities as entities_module
    from science_model.patch_definition import PatchDefinitionEntity
    from science_model.propositions import PropositionEntity

    names = {
        name
        for name, obj in vars(entities_module).items()
        if isinstance(obj, type) and issubclass(obj, entities_module.Entity)
    }
    # These two live outside `entities.py` but are registered entity models like any other.
    return frozenset(names | {PatchDefinitionEntity.__name__, PropositionEntity.__name__})


def _dotted(func: ast.expr) -> list[str] | None:
    """Flatten a call target into its dotted segments, or None if it is not a plain name path.

    `entities.MethodEntity.model_validate` -> ["entities", "MethodEntity", "model_validate"].
    Matching on SEGMENTS rather than on AST shape is what makes the guard blind to import style:
    a bare name, a module-qualified name, and a `self._registry` chain all reduce to the same
    question -- does any segment name an entity class, or the resolver.
    """
    parts: list[str] = []
    node: ast.expr = func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None  # a subscript or call result -- not a name path we can rule on
    parts.append(node.id)
    return list(reversed(parts))


def _local_entity_names(tree: ast.Module, entity_names: frozenset[str]) -> frozenset[str]:
    """Entity class names PLUS every local name this module binds to one.

    Three binding forms, all ordinary code rather than evasion:
      `from science_model.entities import MethodEntity as ME`  -> ME       (ImportFrom)
      `EntityType = MethodEntity`                              -> EntityType  (Assign)
      `Annotated: type[Entity] = MethodEntity`                 -> Annotated   (AnnAssign)

    The annotated form is a separate AST node, not a flavour of `Assign`, and a draft that handled
    only `Assign` missed it -- adding a type annotation is the single most likely edit to make to
    a line like this, so missing it is missing the common case.

    There is nothing in the names `ME` or `EntityType` to recognize, so the binding has to be
    derived from the module's own statements. The pass runs to a fixed point because rebinding
    chains (`A = MethodEntity; B = A`) are one edit away from being written.
    """
    local = set(entity_names)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in entity_names and alias.asname:
                    local.add(alias.asname)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                target, value = node.target, node.value  # `X: type[Entity] = MethodEntity`
            else:
                continue
            if not isinstance(target, ast.Name) or target.id in local:
                continue
            segments = _dotted(value) if isinstance(value, ast.Name | ast.Attribute) else None
            if segments and any(s in local for s in segments):
                local.add(target.id)
                changed = True
    return frozenset(local)


def _class_obtaining_lines(module: Path) -> list[int]:
    """Lines that obtain an entity class in order to build from it.

    Two things count: the resolver (`…resolve_class(kind)`, any receiver) and any call whose
    target path passes through an entity class (`MethodEntity(**raw)`,
    `MethodEntity.model_validate(raw)`, `entities.MethodEntity(**raw)`, `ME(**raw)` after an
    aliased import). Earlier drafts matched AST SHAPE and kept missing spellings one at a time:
    an Attribute-only walk never sees the ordinary constructor (`ast.Name` func), and a
    Name-or-one-Attribute walk never sees `entities.MethodEntity(...)`, which is not obfuscation
    but an ordinary import style. Reducing the target to segments removes the whole category.

    No receiver-name heuristic either: an earlier draft matched the bare name `resolve` and had to
    discriminate on whether the receiver variable was called `registry`, which enforces a naming
    convention -- `reg.resolve(kind)` slipped straight through. Task 5 Step 4 renamed the method
    to `resolve_class`, which occurs nowhere else in the tree, so ANY receiver spelling is caught.

    Deliberately over-broad in one direction: `MethodEntity.model_fields` inside a call target
    also matches. That is a class being obtained to read from, which is what
    `EntityRegistry.declares_field` now exists to answer without handing the class out. The tree
    has zero such calls today, so the strictness costs nothing and closes the near-miss.
    """
    entity_names = _entity_class_names()
    tree = ast.parse(module.read_text(encoding="utf-8"))
    local = _local_entity_names(tree, entity_names)
    hits: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        segments = _dotted(node.func)
        if segments and any(s == "resolve_class" or s in local for s in segments):
            hits.add(node.lineno)
    return sorted(hits)  # ast.walk is breadth-first, so raw order is not source order


def test_NOTHING_in_the_loading_package_resolves_a_class_to_build_from() -> None:
    # The guard is over CALLS, not imports. Twelve modules in this package import `Entity` for
    # isinstance checks and annotations and construct nothing -- banning the import would make
    # those the violation and force either a rewrite of unrelated code or an exemption list, and
    # an exemption list is the enumerated-scope hole this project has been bitten by before.
    #
    # Obtaining a class in order to build from it reduces to one question: does the call target's
    # dotted path pass through `resolve_class` or an entity class (under any import spelling)?
    # There were five such sites; `build` makes it zero. Scope is DERIVED from the package tree,
    # so a sixth adapter is inside it automatically.
    offenders: dict[str, list[int]] = {}
    for module in sorted(_entity_loading_package().rglob("*.py")):
        if module.name == _REGISTRY_MODULE:
            continue  # `build` calls it -- the one legitimate call, by construction
        lines = _class_obtaining_lines(module)
        if lines:
            offenders[module.name] = lines
    assert not offenders, (
        f"modules obtaining an entity class outside the registry: {offenders}. "
        "Construct through `registry.build(kind, raw, ...)`, which validates first."
    )


def test_the_guarded_METHOD_still_exists() -> None:
    # Without this, the gate above is disarmed by a rename rather than by a fix: if
    # `resolve_class` is ever renamed back to `resolve`, every call site stops matching and the
    # guard goes permanently, silently green. The name is load-bearing, so assert it.
    from science_tool.graph.entity_registry import EntityRegistry

    assert hasattr(EntityRegistry, "resolve_class")
    assert not hasattr(EntityRegistry, "resolve"), (
        "`resolve` is back; the guard matches `resolve_class` and no longer sees the call sites"
    )


def test_the_guard_can_actually_SEE_every_violation_spelling(tmp_path: Path) -> None:
    # An AST guard that silently matches nothing passes forever. Pin the detector against all
    # TWELVE bypass spellings -- including the ones that defeated five earlier drafts -- so a
    # refactor that breaks the matching fails HERE rather than turning the gate into a no-op.
    #
    # The probe carries real imports and real assignments because `_local_entity_names` reads
    # both: `ME` is invisible without the `as` clause that bound it, and `EntityType` without the
    # assignment that did.
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from science_model import entities\n"
        "from science_model.entities import Entity, MethodEntity\n"
        "from science_model.entities import MethodEntity as ME\n"
        "from science_tool.graph.sources import SkippedEntity\n"
        "\n"
        "EntityType = MethodEntity\n"                    # local rebinding
        "Indirect = EntityType\n"                        # and a chain, to pin the fixed point
        "Annotated: type[Entity] = MethodEntity\n"       # ANNOTATED rebinding -- ast.AnnAssign
        "\n"
        "def f(registry, context, reg, resolver, path, kind, raw):\n"
        "    registry.resolve_class(kind)\n"
        "    context.registry.resolve_class(kind)\n"
        "    reg.resolve_class(kind)\n"                  # arbitrary receiver -- must match
        "    MethodEntity.model_validate(raw)\n"         # classmethod construction -- must match
        "    MethodEntity(**raw)\n"                      # ORDINARY constructor -- must match
        "    entities.MethodEntity(**raw)\n"             # module-qualified -- must match
        "    entities.MethodEntity.model_validate(raw)\n"# module-qualified classmethod -- match
        "    ME(**raw)\n"                                # ALIASED import -- must match
        "    ME.model_validate(raw)\n"                   # aliased classmethod -- must match
        "    EntityType(**raw)\n"                        # LOCAL REBINDING -- must match
        "    Indirect.model_validate(raw)\n"             # rebinding chain -- must match
        "    Annotated(**raw)\n"                         # annotated rebinding -- must match
        "    resolver.resolve(kind)\n"                   # a DIFFERENT resolver -- must not match
        "    path.resolve()\n"                           # pathlib -- must not match
        "    SkippedEntity(path='x')\n"                  # a dataclass, not an entity -- no match
        "    isinstance(raw, Entity)\n",                 # a type USE, not construction -- no match
        encoding="utf-8",
    )
    assert _class_obtaining_lines(probe) == [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
```

**This probe was executed against the real detector before this plan was written** — twelve hits at lines 11–22, and all four negatives correctly ignored, with zero offenders on the real `graph/` tree. The negatives are the ones that broke earlier drafts: `SkippedEntity(path='x')` (which an `endswith("Entity")` match flags, and which `sources.py` constructs five times) and `isinstance(raw, Entity)` (which the import-surface draft flagged in twelve modules). The seven *positives* added across the last three revisions — module-qualified, aliased, rebound, chained, and annotated — are all ordinary Python, not evasion, and five successive drafts missed them one or two at a time. Every one of those misses was found by someone writing the bypass down and running it. None was found by reasoning about the detector, which is the argument for keeping this probe exhaustive rather than representative.

**What remains uncovered, named rather than implied.** The detector is a static, single-module analysis. It does not see `getattr(registry, "resolve_" + "class")`, a class arriving as a function *parameter* (`def f(model: type[Entity]): model(**raw)`), or one pulled out of a dict at runtime (`CORE_KIND_MODELS[kind](**raw)` — which is why `entity_registry.py` is the excluded module rather than a special case). Each needs a data-flow analysis this test is not, and each is deliberate code rather than an ordinary idiom someone reaches for by accident. The durable barrier is that `build` is the only operation returning a *validated* entity; the guard's job is to keep the accidental bypasses out, and the list above is what it does not claim.

- [ ] **Step 2: Run it and read the real result**

```bash
(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q -k "resolves_a_class or actually_SEE")
```

**Do not predict this result — read it.** Expected after Task 5: PASS. If any module still appears, it is a producing site Task 5 missed — route it through `build` rather than exempting it. If a module calls `.resolve(x)` on something that is *not* an `EntityRegistry` (the `verdict/` pattern, were it ever to move into `graph/`), that cannot reach this guard at all — it matches `resolve_class`, which is unique in the tree, and that uniqueness is the entire reason Step 4 renamed the method. **Do not "narrow" the match by requiring the receiver to be named `registry`.** An earlier draft suggested exactly that as a fallback; it restores the naming-convention hole the rename was performed to close, and `reg.resolve_class(kind)` would walk straight through it. If the guard ever seems imprecise, report it — the fix is not a receiver heuristic.

- [ ] **Step 3: Run the guard alongside the full boundary file**

```bash
(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py -q)
```
Expected: PASS.

- [ ] **Step 4: Lint, types, commit**

```bash
(cd science && uv run ruff check && uv run pyright)
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

**Every mutation below carries its exact command.** A mutation without one is not reproducible: the observed failure set is a function of the selection, and two people running "the gates" get different answers. Mutation 3, for instance, fails gate 1 *and* the armed-component gate (`mixin-concept-1.0.json` is not packaged) — which reads as an unpredicted cascade only if the selection was never pinned.

**The semantics are REQUIRED-SUBSET, not set equality**, and the asymmetry is the point:

- **Each mutation names the gate it targets. That gate MUST fail — if it does not, stop.** A gate that does not catch its own mutation is the one thing this task exists to detect, and it is the only hard stop here.
- **The plan also predicts the other tests that fail under the same command.** These are a *prediction to check*, not a pass condition. Record the full observed set; where it differs from the prediction, report the difference with the cause you traced. A cascade you can trace to the mutation is expected — gates overlap by design, and the 5a/5b/5c rows below say exactly how. A failure you cannot trace to the mutation is a finding worth stopping for.

That split is deliberate. The targeted-gate direction is a property of the implementation and is worth failing the task over. The full-set direction is a property of *this plan's foresight*, and four review rounds have shown the plan wrong about it twice — so it is written as something to measure, not something to satisfy.

Do not edit this plan to match what you observed. A prediction and an implementation disagreeing means one of them is wrong, and which one is the finding.

- [ ] **Step 1: Mutation 1 — remove a generation-row entry for a closed kind**

Delete `"hypothesis": "1.0"` from generation 2 in `_MIXIN_VERSION_BY_GENERATION`.
Run: `(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)`
**Targets** `test_GATE_1_every_generation_row_matches_the_closed_declaration` — must FAIL, naming `hypothesis` as declared-closed-but-missing-from-the-row.
Predicted alongside it: nothing. The armed-component gate ranges over row entries, so removing one gives it less to check, not more; `PROJECT_MIXIN_NAMES` derives from `schema_closed` and is untouched. **Revert.**

- [ ] **Step 2: Mutation 2 — a closed declaration with no generation rows**

Set `schema_closed=True` on `concept` in `core.py`.
Run: `(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)`
**Targets** `test_GATE_1_every_generation_row_matches_the_closed_declaration` — must FAIL, for **both** generations, naming `concept` as declared-closed-but-missing-from-the-row.
Predicted alongside it: `test_this_mechanism_closes_NO_new_kind` also fails, because `PROJECT_MIXIN_NAMES` now derives `{"hypothesis", "concept"}`. Two gates for one mutation is correct, not redundant — one says the surfaces disagree, the other says this branch closed a kind it was not supposed to. Gate 4 passes (`concept` declares both `entity_class` and `home`), and the mixin-const gate passes (it ranges over row entries, and no row mentions `concept`). **Revert.**

- [ ] **Step 3: Mutation 3 — a project mixin in a row with no closed declaration**

Add `"concept": "1.0"` to generation 2's row without touching any declaration.
Run: `(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)`
**Targets** `test_GATE_1_every_generation_row_matches_the_closed_declaration` — must FAIL, naming `concept` as in-the-row-but-not-declared.
Predicted alongside it: `test_GATE_2_every_ARMED_component_resolves_to_a_packaged_file` also fails, because `mixin-concept-1.0.json` is not packaged. That is the same defect seen from the other end — arming a component the toolkit cannot resolve — and it is why the mixin-const gate skips names that are not on disk rather than reporting a third time. **Revert.**

- [ ] **Step 4: Mutation 4 — remove a packaged mixin file armed by a row**

Rename the file **inside the worktree** — `git mv` to a path outside the repository exits 128 with "outside repository", so `/tmp/` does not work:

```bash
git mv science/model/src/science_model/schemas/mixin-hypothesis-1.0.json \
       science/model/src/science_model/schemas/mixin-hypothesis-1.0.json.disabled
```

The `.json.disabled` suffix matters: `_packaged_schema_names()` filters on `.endswith(".json")`, so a file renamed to something still ending in `.json` would still be found and the mutation would do nothing.
Run: `(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)`
**Targets** `test_GATE_2_every_ARMED_component_resolves_to_a_packaged_file` — must FAIL, naming `hypothesis/1.0`.
Predicted alongside it: nothing. `test_GATE_2_every_armed_project_mixin_pins_its_own_kind` skips the missing file by design, so one missing artifact reports as one failure. **Revert:** `git mv science/model/src/science_model/schemas/mixin-hypothesis-1.0.json.disabled science/model/src/science_model/schemas/mixin-hypothesis-1.0.json`, then confirm `git status --short` is clean.

- [ ] **Step 5: Mutation 5a — restore `extra="ignore"` on `StructuredEntitySource`**

Run: `(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py tests/test_undeclared_key_diagnostic.py -q)`
**Targets** `test_an_unknown_key_SURVIVES_the_source_contract` — must FAIL, `model_extra` is `{}`.
Predicted alongside it, **four** more, all traceable to the same strip:
1. `test_an_authored_shadow_key_SURVIVES_the_whole_load_path` — the key is gone by the time the entity exists.
2. `test_structured_source_PRESERVES_an_unknown_reference_key` (in `test_undeclared_key_diagnostic.py`, inverted by Task 4 Step 8) — `model_extra` is empty, so the assertion that both extras survive fails. This is why that file is in the selection.
3. `test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path` — with the key stripped at the contract, the mapping reaching the composed schema is clean, nothing refuses it, and the `pytest.raises` fails. Precisely the point of 5a: the check is intact and still catches nothing, because it sits downstream of the loss.
4. `test_the_same_closed_row_WITHOUT_the_shadow_key_loads` — **the negative control fails too, and tracing why matters.** `status` is not a declared field of `StructuredEntitySource`; it rides through as an extra and is exactly what the hypothesis mixin *requires*. Restore `extra="ignore"` and `status` is destroyed with everything else, so the valid row now gets refused for a missing required field. If you see this one and cannot explain it, that is the trace.

Together these prove the **loss** is prevented, at the contract, on the real path, on the diagnostic surface, and where it would otherwise silently disarm the refusal.

`test_a_shadow_key_reaches_the_normalized_mapping` is **expected to keep passing** and that is not a defect: it hands a dict straight to `normalize_structured_row`, so the source contract is not in its path. It pins normalization, not losslessness. This is exactly why Task 4 Step 7's end-to-end test exists — without it, this mutation would be caught only by a single unit assertion on a model config, and the pipeline could regress with the gate still green. **Revert.**

- [ ] **Step 6: Mutation 5b — drop the schema check from `registry.build`**

Remove the `validate_against_schema(...)` line from `build`, leaving only the projection.
Run: `(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py tests/test_undeclared_key_diagnostic.py -q)`
**Targets** `test_build_validates_a_closed_kind_before_projecting` (unit) — must FAIL: no refusal at the choke point.
Predicted alongside it:

1. `test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path` (end-to-end) — no refusal on the real path.
2. `test_an_unauthored_optional_field_is_absent_from_what_VALIDATION_SEES` — **the cascade, and it is correct.** The spy patches the name `build` calls; deleting the call leaves `seen` empty and its `next()` raises `StopIteration`. A spy on a function nobody calls has nothing to say, which is the honest result.

Together these prove the **check runs**, at the choke point and on the real load path.

The end-to-end one is the load-bearing failure: it is the single test that fails under **both** 5a and 5b, which is what certifies that lossless parse and composed validation are wired to each other rather than merely both present.

5a and 5b are both required and are not redundant: 5a proves the loss is prevented, 5b proves the check runs. An earlier design draft had only the second, which would have passed against a pipeline faithfully validating a mapping the toolkit had already stripped — a check that cannot fail. **Revert.**

- [ ] **Step 7: Mutation 5c — obtain an entity class outside `registry.build`**

Restore one resolve-then-construct pair: in `_load_structured_source_records` (`sources.py`), replace the `registry.build(...)` call with `registry.resolve_class(kind_name).model_validate(raw)`.
Run: `(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py tests/test_undeclared_key_diagnostic.py -q)`
**Targets** `test_NOTHING_in_the_loading_package_resolves_a_class_to_build_from` — must FAIL, naming `sources.py` and the line.
Predicted alongside it:

1. `test_a_CLOSED_kind_refuses_a_shadow_key_through_the_whole_structured_path` — the bypassed path no longer validates, so nothing refuses.
2. `test_an_unauthored_optional_field_is_absent_from_what_VALIDATION_SEES` — same cause: the spied call is gone from this path, `seen` is empty.

That 5c reproduces 5b's two cascades is the point rather than noise: routing around `build` and gutting `build` are the same defect reached from opposite directions. **Revert.**

An *import* of an entity class is deliberately **not** the mutation here: twelve modules in `graph/` already import `Entity` legitimately, so an import cannot distinguish a violation from an annotation. The resolve call is the thing that precedes construction, and it is what the guard watches.

(`MethodEntity` is used because it is real — verified. There is **no** `ConceptEntity`: only 21 kinds have a concrete `*Entity` class, and `concept` is not among them. A slice author closing `concept` should expect it to project onto the base `Entity`, which is also why gate 4 asks for `entity_class` on the *descriptor*, not for a dedicated class.)

- [ ] **Step 8: Mutation 5d — add an undeclared key to the drop set**

Change `STRUCTURED_DROP_KEYS` to `frozenset({"kind", "title"})`.
Run: `(cd science && uv run --frozen pytest tests/test_entity_construction_boundary.py tests/test_undeclared_key_diagnostic.py -q)`
**Targets** `test_kind_is_the_only_declared_DROP` — must FAIL.
Predicted alongside it: **nothing.** An earlier draft predicted `test_a_shadow_key_reaches_the_normalized_mapping` would fail — it does not: its input carries no `title` at all, so adding `title` to the drop set changes nothing about it. And on the real loader paths, `title` is restored by the loader's own backfill *after* normalization, so a dropped `title` never reaches the schema. The drop-set gate is the only thing that sees this mutation, which is exactly what makes it worth having: nothing downstream would have noticed. **Revert.**

- [ ] **Step 9: Mutation 6 — closed descriptor with `home=None`**

Set `home=None` on `hypothesis` in `core.py`.
Run: `(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)`
**Targets** `test_GATE_4_a_closed_kind_declares_entity_class_and_home` — must FAIL on `home`.
Predicted alongside it: nothing in this file. **Revert.**

- [ ] **Step 10: Mutation 7 — closed descriptor with `entity_class=None`**

Set `entity_class=None` on `hypothesis`.
Run: `(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)`
**Targets** `test_GATE_4_a_closed_kind_declares_entity_class_and_home` — must FAIL on `entity_class`.
Predicted alongside it: nothing in this file. **Revert.**

- [ ] **Step 11: Mutation 8 — external manifest authors `schema_closed`**

Already covered by `test_an_external_manifest_may_NOT_author_schema_closed`, which asserts the raise directly rather than requiring a source mutation. Confirm it fails when the `_refuse_toolkit_reserved_fields` validator body is replaced with `return data`.
Run: `(cd science/model && uv run --frozen pytest tests/test_schema_closed_gate.py -q)` and `(cd science && uv run --frozen pytest tests/test_local_kind_registration_reserved_fields.py -q)`
**Targets** both external-manifest rejection tests (`..._may_NOT_author_schema_closed` and `..._FALSE_either`) plus the tool-side loader test — all three must FAIL.
Predicted alongside them: nothing; the two control tests in that file must keep passing, which is what shows the rejection was the only thing removed. **Revert.**

- [ ] **Step 12: Record the results and commit**

Write `science/tests/test_schema_closure_mutations.py` containing **no test functions** — a module docstring recording the matrix as executed: one row per mutation with the mutation, the named gate, and the observed failures. A results table nobody can run is still the record of what was proven, and it is where the next slice's author learns which gate covers what.

```bash
(cd science && uv run ruff check)
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
(cd science && uv run --frozen pytest -q)                    # ~2-3 min
(cd science/model && uv run --frozen pytest -q)
(cd science && uv run ruff check && uv run pyright)
(cd science/model && uv run ruff check)
(cd science && uv run --frozen pytest -m real_projects -q)   # opt-in
(cd science && uv run --frozen pytest -m snapshot -q)        # opt-in
```

**Four failures are pre-existing on `main`** and were reproduced at merge-base `ca937131` during the writer-containment branch: one `-m snapshot` formatter-snapshot mismatch (`Checks: 68` vs 69) and three `-m real_projects` failures (skills-coverage commons datasets, correspondence drift on multiple-myeloma, canonical-body parity). Reproduce any failure at the merge-base before attributing it to this branch.

**The behavioural invariant for this whole branch:** `PROJECT_MIXIN_NAMES == frozenset({"hypothesis"})` before and after. This plan changes *how* the answer is derived and *which paths must ask*, never *what the answer is*.

## Out of scope

- **Closing any kind.** Five separate branches, per Task 8's procedure.
- **The 769 `proposition` / `evidence-line` documents.** Piece 3.
- **Widening `REFERENCE_FIELD_NAMES` or the `undeclared_key` diagnostic.** A warning surface is not the mechanism this design builds; a wrong answer should become unreachable, not discouraged.
- **The remaining 44 unclosed core kinds** and the 16 authored non-core kinds.
- **`render_update`'s stale-owned-key hole**, recorded in the writer-containment plan's follow-up section. Independent of this work.
- **The Markdown adapter's authored-`content` blind spot.** `build` now takes `injected` per adapter, and Markdown passes `MarkdownAdapter.INJECTED_KEYS` verbatim so its behaviour is unchanged — which means an author who writes `content:` in Markdown frontmatter still has it hidden from the composed schema. Pre-existing, and now confined to one adapter rather than applied to all of them, but not closed. Closing it changes what the Markdown path accepts, so it belongs to a kind slice.

  > **Correction (2026-07-29, from the `method` slice).** This entry originally proposed the fix as `MarkdownAdapter.INJECTED_KEYS - frozenset(authored_frontmatter)` — "the same subtraction every other adapter already does." **That is not available here.** `validate_canonical_markdown_record` receives one already-merged `raw` dict from `adapter.load_raw(ref)`; the authored keys and the injected keys are indistinguishable inside it, so there is no `authored_frontmatter` to subtract. Closing this requires the adapter to report what it injected *per record* — a `StorageAdapter` protocol change, not a one-line subtraction. It is correspondingly larger than this entry implied, and it weakens every slice's step-4 certification until it lands. Sized as its own branch, not slice work.

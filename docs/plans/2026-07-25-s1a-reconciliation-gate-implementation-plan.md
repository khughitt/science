# S1a Reconciliation Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **2026-07-26 correction note:** the final whole-branch review found four factual defects in this
> plan, all discovered during execution and repaired here so the document matches what actually
> happened rather than reading as authored-correct: Task 2 Steps 8–9 named a `composition_rule`
> enum value (`"conjunctive_extra"`) that appears in no probe battery and a fallback field
> (`status`) that cannot work because it is unrestricted, corrected to `"evidence_union"` with the
> `status` note replaced by the reason it fails; Task 3 Step 4's expected outcome claimed both
> `test_value_reconciliation.py` tests fail from an unearned `VALUE_RECONCILED_KINDS` claim, but
> only one reads that name; Task 4 Step 3 told the implementer to comment out `PaperEntity.doi`,
> which raises `PydanticUserError` at import time because `doi` is named in a `field_validator`
> decorator, corrected to `year`; and Task 4's manifest carried two UNHELD notes since found false
> and repaired in commit `e023b6df` (the `version` `Reader`'s mapping, and the `sources`
> `PendingRuling`'s false universal), now brought in line with the shipped file.

**Goal:** Generalize the schema↔model reconciliation that today covers one kind into a gate that covers every kind with a schema, and fix the one composition derivation all of it depends on.

**Architecture:** One shared derivation (`admitted_field_names`) moves into `science_model`, replacing a copy that lives in a test and fixing a sibling reader that ignores `false` subschemas. On top of it, two guards: a **field-declaration gate** in the tool suite (every schema-admitted field is declared on the projection, modulo a frozen generation-keyed manifest of 31 known gaps), and **value-reconciliation coverage** in the model suite (the existing probe battery is parametrized over every profile of its kind, so coverage is established by running, never by claiming two schemas equivalent).

**Tech Stack:** Python ≥3.11, pytest, pydantic v2, JSON Schema. Two independently managed packages — `science/` (the tool) and `science/model/` (`science-model`). This plan does not change either package's dependency floors.

**Design doc:** [`meta/doc/plans/2026-07-25-s1a-reconciliation-gate-design.md`](../../meta/doc/plans/2026-07-25-s1a-reconciliation-gate-design.md)

## Global Constraints

- **No runtime behaviour change.** S1a is "a test gate plus one derivation fix." Nothing may start rejecting an entity that loads today. The single user-visible change is that `science entity fields <kind>` stops advertising fields the kind forbids.
- **`science_model` may not import `science_tool`.** The model package may not import its own consumer. This is why the field-declaration gate lives in the tool suite: the kind→model binding is `science_tool/graph/entity_registry.py` (`CORE_KIND_MODELS`).
- **Run commands from the package directory.** There is no root `pyproject.toml`. Tool work runs from `science/`; model work runs from `science/model/`.
- **Never run two suites concurrently in one worktree** — they race on shared test-output paths.
- **Conventional commits. No AI-attribution trailers or footers** on commits, PRs, or comments.
- **Composition over inheritance; explicit over defensive; fail early rather than silently falling back.** No compatibility or legacy layers.
- Work happens in the worktree `.worktrees/reconciliation-gate` on branch `reconciliation-gate`. **Verify the branch before every commit** — this repository lives in a Dropbox-synced tree and HEAD can move.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/model/src/science_model/entity_schema/introspection.py` | **Modify.** Gains `admitted_field_names(profile, loader=None) -> frozenset[str]`, the single composition derivation. Its existing `read_effective_frontmatter_fields` is fixed to honour `false` subschemas. |
| `science/model/tests/test_entity_schema_merge.py` | **Modify.** Gains the tests for both of the above. It already owns `read_merge_policy`'s `false`-handling test, so the sibling reader's fix belongs beside it. |
| `science/model/tests/test_hypothesis_entity.py` | **Modify.** Drops its local copy of the derivation, corrects three stale sentences, and parametrizes its battery over both hypothesis profiles. |
| `science/model/tests/test_value_reconciliation.py` | **Create.** The value-coverage ratchet: which profiles have a probe battery, asserted to partition the derived profile set exactly. Model-side because it needs no kind→model binding. |
| `science/tests/test_kind_reconciliation.py` | **Create.** The field-declaration gate, the 31-entry manifest, and the AST reader check. Tool-side because it needs `CORE_KIND_MODELS`. |

---

## Task 1: The shared composition derivation

**Files:**
- Modify: `science/model/src/science_model/entity_schema/introspection.py:21-62`
- Modify: `science/model/src/science_model/entity_schema/__init__.py` (export)
- Test: `science/model/tests/test_entity_schema_merge.py`

**Interfaces:**
- Consumes: `SchemaLoader`, `ProfileString`, `_iter_components` — all already in `introspection.py`.
- Produces: `admitted_field_names(profile: ProfileString, loader: SchemaLoader | None = None) -> frozenset[str]`, exported from `science_model.entity_schema`. Tasks 2, 3, and 4 all consume it.

**Background the implementer needs.** A JSON Schema property whose value is the literal `false` is a **forbidden** field — the property may not appear at all. `mixin-hypothesis-1.0.json` uses this for 17 fields. The sibling reader `read_merge_policy` already handles it correctly (returns `MergePolicy.FORBIDDEN`); `read_effective_frontmatter_fields` does not, because its loop skips anything that is not a `dict`. The consequence is measurable: `science entity fields hypothesis` currently advertises `contributors`, `licenses`, `schema_profile`, `sources`, `tags`, and `version`, all of which the kind rejects.

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_entity_schema_merge.py`. The existing imports at the top of that file already include `parse_profile` and `read_effective_frontmatter_fields`; add `admitted_field_names` to the same `from science_model.entity_schema import (...)` block.

```python
def test_admitted_field_names_excludes_what_a_later_component_forbids() -> None:
    # Composition is ORDERED: base 2.0 declares `tags`, the hypothesis mixin sets it to
    # `false`, and the composed profile therefore does not admit it. Deriving this from the
    # mixin ALONE is how `description` hid for four drafts -- it is declared by the BASE,
    # forbidden by nothing, and was on no model.
    admitted = admitted_field_names(parse_profile("science-entity-base/2.0+hypothesis/1.0"))

    assert "tags" not in admitted  # base declares it; the mixin forbids it
    assert "phase" not in admitted  # mixin-only, forbidden
    assert "description" in admitted  # base declares it; nothing forbids it
    assert "verdict" in admitted  # the mixin declares it


def test_effective_frontmatter_fields_omit_a_base_field_the_mixin_forbids() -> None:
    # `read_merge_policy` reads a `false` subschema as FORBIDDEN. This reader skipped it as
    # "not a dict", so a base field the mixin removed stayed in the output and
    # `science entity fields hypothesis` advertised six commons fields the kind rejects.
    keys = {
        field.key
        for field in read_effective_frontmatter_fields(
            parse_profile("science-entity-base/2.0+hypothesis/1.0")
        )
    }

    assert keys.isdisjoint({"contributors", "licenses", "schema_profile", "sources", "tags", "version"})
    assert "phase" not in keys
    assert "description" in keys  # the fix must not over-remove
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science/model && uv run --frozen pytest tests/test_entity_schema_merge.py -k "admitted_field_names or omit_a_base_field" -v
```

Expected: the first fails with `ImportError`/`NameError` on `admitted_field_names`; the second fails on the `isdisjoint` assertion, reporting the six leaked fields.

- [ ] **Step 3: Add `admitted_field_names`**

Insert into `science/model/src/science_model/entity_schema/introspection.py`, directly after `read_effective_frontmatter_fields`:

```python
def admitted_field_names(
    profile: ProfileString, loader: SchemaLoader | None = None
) -> frozenset[str]:
    """Every field name the COMPOSED profile admits.

    Composition is ORDERED: a later component's `false` subschema REMOVES a field an earlier
    one declared, so this cannot be computed from the mixin alone. `description` is declared by
    entity-base 2.0, forbidden by nothing, and hid for four drafts behind exactly that mistake.

    A `false` value means the property is forbidden outright, which is why it is discarded here
    rather than recorded -- the same reading `read_merge_policy` gives it.
    """
    loader = loader or SchemaLoader()
    names: set[str] = set()
    for component in _iter_components(profile):
        for key, spec in (loader.load(component).get("properties") or {}).items():
            if spec is False:
                names.discard(key)
            else:
                names.add(key)
    return frozenset(names)
```

- [ ] **Step 4: Fix `read_effective_frontmatter_fields`**

In the same file, replace the loop body at `introspection.py:44-52`:

```python
    for schema in schemas:
        properties = schema.get("properties") or {}
        for key, spec in properties.items():
            if spec is False:
                # A `false` subschema FORBIDS the property. The old guard skipped it as "not a
                # dict", leaving a base field the mixin removed in the output -- so
                # `science entity fields hypothesis` advertised six commons fields the kind
                # rejects. `read_merge_policy` already reads `false` as FORBIDDEN; this is the
                # same fact, finally read the same way by the other reader.
                specs_by_field.pop(key, None)
                if key in field_order:
                    field_order.remove(key)
                continue
            if not isinstance(spec, dict):
                continue
            if key not in specs_by_field:
                field_order.append(key)
                specs_by_field[key] = []
            specs_by_field[key].append(spec)
```

- [ ] **Step 5: Export it**

In `science/model/src/science_model/entity_schema/__init__.py`, add `admitted_field_names` to the `from science_model.entity_schema.introspection import (...)` block and to `__all__`, keeping both lists alphabetically ordered as they already are.

- [ ] **Step 6: Run the new tests**

```bash
cd science/model && uv run --frozen pytest tests/test_entity_schema_merge.py -v
```

Expected: PASS, including the pre-existing
`test_read_effective_frontmatter_fields_intersects_composed_schema_constraints` — it profiles
`science-entity-base/1.0+theme/2.0`, whose mixin forbids nothing, so the fix must not change it.

- [ ] **Step 7: Prove the fix is load-bearing**

Temporarily revert Step 4 (restore the bare `if not isinstance(spec, dict): continue`) and re-run.

```bash
cd science/model && uv run --frozen pytest tests/test_entity_schema_merge.py -k omit_a_base_field -v
```

Expected: FAIL, naming the six fields. Restore the fix and confirm PASS. **Record both outcomes in
the commit message** — a guard whose failure was never observed is not known to be a guard.

- [ ] **Step 8: Check the CLI consumer still works**

`science/src/science_tool/entities_cli.py:534` is the only production caller.

```bash
cd science && uv run --frozen pytest tests/test_entities_cli.py -q
```

Expected: PASS. Measured: **no test in either suite asserts on
`read_effective_frontmatter_fields` or `_entity_frontmatter_section_rows` output**, so nothing
should break. If something does, it was asserting the bug — update it to assert absence and say so
in the commit message.

- [ ] **Step 9: Commit**

```bash
cd ~/d/science/.worktrees/reconciliation-gate && git branch --show-current  # must print reconciliation-gate
git add science/model/src/science_model/entity_schema/introspection.py \
        science/model/src/science_model/entity_schema/__init__.py \
        science/model/tests/test_entity_schema_merge.py
git commit -m "fix(schema): read a false subschema as forbidden in both readers

read_merge_policy already returned FORBIDDEN for a `false` property;
read_effective_frontmatter_fields skipped it as 'not a dict', so a base
field a mixin removed stayed in the output and `science entity fields
hypothesis` advertised six commons fields the kind rejects.

Adds admitted_field_names as the single composition derivation, replacing
a copy that lives in a test module."
```

---

## Task 2: Repoint and parametrize the hypothesis battery

**Files:**
- Modify: `science/model/tests/test_hypothesis_entity.py:1-23` (docstring), `:42-57` (derivation), `:215-220` (`_schema_accepts`), `:282-342` (the three property tests), `:370-381` (battery ratchet)

**Interfaces:**
- Consumes: `admitted_field_names` from Task 1.
- Produces: `_PROFILE_BY_GENERATION: dict[int, ProfileString]` and `_SHARED_BY_GENERATION: dict[int, frozenset[str]]` — Task 3 relies on the *fact* that the battery runs against both generations, not on these names.

**Background the implementer needs.** This file is the one working reconciliation in the codebase. It asserts three properties of the hypothesis schema against `HypothesisEntity`, using `_BATTERY` — 27 fields of hand-authored probe values. Two things are being changed and one is deliberately not:

1. Three sentences assert `Entity` is `extra="ignore"`. It is `extra="allow"` (D3.3, `ae83241b`). Correct the sentences.
2. The battery currently runs only against generation 2's profile. Parametrize it over both.
3. **The comment saying the two capability fields' readers "re-parse RAW frontmatter and never go through the model at all" is CORRECT. Do not touch it.** Its readers are `dataset_prioritize.target_coverage`, which takes frontmatter from `_iter_entity_frontmatter`.

- [ ] **Step 1: Replace the local derivation**

Replace `science/model/tests/test_hypothesis_entity.py:42-57` — the `MIXIN`, `BASE_2`, `_PROFILE`, and `_ADMITTED` block — with:

```python
MIXIN = json.loads(
    (files("science_model.schemas") / "mixin-hypothesis-1.0.json").read_text(encoding="utf-8")
)
_GENERATIONS = (2, 3)
_PROFILE_BY_GENERATION = {
    generation: default_profile_for_kind("hypothesis", generation=generation)
    for generation in _GENERATIONS
}
_PROFILE = _PROFILE_BY_GENERATION[2]
_V = EntityValidator()

# The composed profile's admitted surface, from the ONE derivation in `science_model`. It was a
# local six-line copy here; two readers of the same fact is the defect this sub-project exists to
# remove, and the copy could not be reused by the tool-side gate.
_ADMITTED_BY_GENERATION = {
    generation: admitted_field_names(profile)
    for generation, profile in _PROFILE_BY_GENERATION.items()
}
_ADMITTED = _ADMITTED_BY_GENERATION[2]
```

`BASE_2` is now unused — delete its assignment. `MIXIN` is still used by the three
`*_is_not_a_SECOND_authority` tests, so it stays.

Update the import block at `:35-39` to add `admitted_field_names`:

```python
from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    admitted_field_names,
    default_profile_for_kind,
)
```

- [ ] **Step 2: Derive the shared surface per generation**

Replace the `_SHARED_FIELDS` assignment at `:69`:

```python
# The fields BOTH authorities describe, per generation. `false` properties are excluded by
# `_ADMITTED_BY_GENERATION`: the schema rejects them outright, so "at least as strict" holds
# trivially and there is nothing to compare.
_SHARED_BY_GENERATION = {
    generation: admitted & set(HypothesisEntity.model_fields)
    for generation, admitted in _ADMITTED_BY_GENERATION.items()
}
_SHARED_FIELDS = _SHARED_BY_GENERATION[2]
```

- [ ] **Step 3: Make `_schema_accepts` profile-aware**

Replace `science/model/tests/test_hypothesis_entity.py:215-220`:

```python
def _schema_accepts(field: str, value: Any, profile: ProfileString = _PROFILE) -> bool:
    try:
        _V.validate_as(_payload(**{field: value}), profile)
        return True
    except EntityValidationError:
        return False
```

Add `ProfileString` to the `science_model.entity_schema` import block from Step 1.

- [ ] **Step 4: Parametrize the three property tests over both generations**

Replace the decorators and opening lines of the three tests. `test_every_field_the_schema_ADMITS_is_REPRESENTABLE_in_the_projection` at `:282`:

```python
@pytest.mark.parametrize("generation", _GENERATIONS)
def test_every_field_the_schema_ADMITS_is_REPRESENTABLE_in_the_projection(generation: int) -> None:
    # A field the schema admits but the projection cannot hold is a field that validates on disk
    # and reaches the model as an UNTYPED extra (`Entity` is `extra="allow"` -- D3.3). It is
    # preserved, but it is unwired: no declared type, no graph predicate, and no general
    # diagnostic covers it. `phase` is that history and `description` was the third instance,
    # surviving every earlier draft because no test looked at the fields the BASE contributes.
    missing = _ADMITTED_BY_GENERATION[generation] - set(HypothesisEntity.model_fields) - _NOT_ON_THE_MODEL
    assert not missing, f"schema admits {sorted(missing)}; the projection has no declared field for them"
```

`test_the_schema_is_at_least_as_strict_as_the_projection` at `:291` — replace the decorator and the
first line of the body, keeping its long docstring unchanged:

```python
@pytest.mark.parametrize("generation", _GENERATIONS)
@pytest.mark.parametrize("field", sorted(_SHARED_FIELDS))
def test_the_schema_is_at_least_as_strict_as_the_projection(field: str, generation: int) -> None:
    """<<< keep the existing docstring verbatim >>>"""
    profile = _PROFILE_BY_GENERATION[generation]
    for value in _BATTERY[field]:
        schema_ok = _schema_accepts(field, value, profile)
        model_ok = _model_accepts(field, value)
        assert not (schema_ok and not model_ok), (
            f"gen {generation} {field}={value!r}: the SCHEMA admits it and the MODEL rejects it. "
            f"The schema is not authoritative for this field."
        )

    assert any(not _schema_accepts(field, v, profile) for v in _BATTERY[field]), (
        f"gen {generation} {field}: the schema rejected NOTHING in the battery -- its contract "
        f"admits anything"
    )
```

`test_every_value_the_schema_ADMITS_SURVIVES_the_projection` at `:323` — same treatment:

```python
@pytest.mark.parametrize("generation", _GENERATIONS)
@pytest.mark.parametrize("field", sorted(_SHARED_FIELDS))
def test_every_value_the_schema_ADMITS_SURVIVES_the_projection(field: str, generation: int) -> None:
    """<<< keep the existing docstring verbatim >>>"""
    profile = _PROFILE_BY_GENERATION[generation]
    for value in _BATTERY[field]:
        if not _schema_accepts(field, value, profile):
            continue  # the schema already refused it; nothing is owed
        assert _model_preserves(field, value), (
            f"gen {generation} {field}={value!r}: the SCHEMA admits it, the MODEL accepts it, and "
            f"`model_dump()` DROPS it. The value validates and then evaporates."
        )
```

- [ ] **Step 5: Make the battery ratchet cover every generation**

Replace `test_the_BATTERY_is_EXACTLY_the_shared_surface` at `:370`:

```python
@pytest.mark.parametrize("generation", _GENERATIONS)
def test_the_BATTERY_is_EXACTLY_the_shared_surface(generation: int) -> None:
    # EQUALITY, not coverage, and now per GENERATION -- a generation that adds a shared field
    # must gain a battery entry, and one that drops a field must lose it. `_SHARED_BY_GENERATION`
    # is derived; the battery is hand-written, so the battery is the half that falls behind, and
    # it falls behind in BOTH directions:
    #
    #   missing  -> a field is declared by both authorities and reconciled by neither, while every
    #               test still passes. (`description` and the whole base surface lived here.)
    #   spurious -> a battery entry for a field nobody declares. It never runs, and it reads like
    #               coverage that does not exist -- which is worse than no entry at all.
    shared = _SHARED_BY_GENERATION[generation]
    assert set(_BATTERY) == shared, (
        f"gen {generation} unreconciled: {sorted(shared - set(_BATTERY))}; "
        f"stale: {sorted(set(_BATTERY) - shared)}"
    )
```

- [ ] **Step 6: Correct the three stale sentences**

Three places assert the old `extra="ignore"` failure mode in the present tense. Change only these:

- **Line 8**, in the module docstring — replace
  `(else: validates on disk, silently dropped on load -- `Entity` is `extra="ignore"`).`
  with
  `` (else: it validates on disk and reaches the model as an UNTYPED extra -- `Entity` is `extra="allow"` since D3.3, so it is preserved but unwired: no declared type, no graph predicate). ``
- **Line 327**, in `test_every_value_the_schema_ADMITS_SURVIVES_the_projection`'s docstring — replace
  `` and `extra="ignore"` is exactly the gap between them: the model accepts the object, and `model_dump()` loses the keys it did not declare. ``
  with
  `` and a NESTED `extra="forbid"` submodel is exactly the gap between them: the outer field is declared, the model accepts the object, and `model_dump()` loses the inner keys the submodel did not declare. ``
- **Line 284**'s comment is replaced wholesale by Step 4.

**Line 20 stays as written** — `` `Entity` was `extra="ignore"` while every test in this file passed `` is past tense and historically accurate. **Lines 59-63 (`_NOT_ON_THE_MODEL`) stay as written** — its raw-frontmatter claim is correct.

- [ ] **Step 7: Run the file**

```bash
cd science/model && uv run --frozen pytest tests/test_hypothesis_entity.py -v
```

Expected: PASS, with roughly double the parametrized cases (27 fields × 2 generations for each of
the two battery tests). Confirm from the output that generation-3 cases actually ran.

- [ ] **Step 8: Prove the gen-3 parametrization can fail**

Edit `science/model/src/science_model/schemas/mixin-hypothesis-2.0.json` only — append `"evidence_union"` to `composition_rule`'s `enum` array. (`evidence_union` is already a `_BATTERY["composition_rule"]` probe value, and `Entity._validate_composition_rule` rejects it via `RESERVED_COMPOSITION_RULES` — so widening the schema's enum to admit it makes the schema admit a value the model rejects, which is exactly what `test_the_schema_is_at_least_as_strict_as_the_projection` exists to catch.)

```bash
cd science/model && uv run --frozen pytest tests/test_hypothesis_entity.py -k "at_least_as_strict and composition_rule" -v
```

Expected: the `generation=3` case FAILS and the `generation=2` case PASSES. Revert the schema edit
and confirm both pass.

- [ ] **Step 9: Prove there is no privileged reference generation**

Now make the same edit to `mixin-hypothesis-1.0.json` instead, and re-run the same command.

Expected: the `generation=2` case FAILS and `generation=3` PASSES — the mirror image of Step 8.
**This is the proof that no generation is a frozen reference contract the others are compared
against.** The battery's probe values are the fixed artifact; every generation is something they
run against. Revert and confirm both pass.

- [ ] **Step 10: Commit**

```bash
cd ~/d/science/.worktrees/reconciliation-gate && git branch --show-current  # must print reconciliation-gate
git add science/model/tests/test_hypothesis_entity.py
git commit -m "test(schema): run the hypothesis battery against every generation

The battery asserted three properties against generation 2 only, so
generation 3's composed profile was unreconciled despite being live.
Parametrizing it establishes coverage by execution rather than by
claiming the two schemas equivalent.

Also repoints the local composition derivation at admitted_field_names
and corrects three sentences that still described extra=\"ignore\"."
```

---

## Task 3: Value-reconciliation coverage ratchet

**Files:**
- Create: `science/model/tests/test_value_reconciliation.py`

**Interfaces:**
- Consumes: `_MIXIN_VERSION_BY_GENERATION` from `science_model.entity_schema.profile`.
- Produces: nothing other tasks import.

**Background the implementer needs.** Task 2 proved *hypothesis* is value-reconciled at both
generations by running its battery there. Nothing yet states which profiles have a battery at all,
so a sixth mixin could arrive with no probe values and no test would notice. This file is that
statement, and it is deliberately **model-side**: it needs no kind→model binding.

The declaration is a **kind set**, not a profile set. Membership in the profile set is derived, so
the hand-written part records only the non-derivable judgment ("this kind has an authored
battery") and its domain is checked exactly against the derived set.

- [ ] **Step 1: Write the failing test**

```python
"""Which profiles have a probe battery, and which are debt.

Task 2 established that hypothesis is value-reconciled at BOTH generations by running its battery
against each. This file states which kinds have a battery at all, so a newly declared mixin cannot
arrive with no probe values and no failing test.

☠️ The declaration is `VALUE_RECONCILED_KINDS` -- a set of KINDS. The pending PROFILE set is
derived from it. Declaring profiles directly would restate membership the profile table already
determines, and a hand-written declaration is only appropriate where it records a judgment that
cannot be derived.
"""

from __future__ import annotations

from science_model.entity_schema.profile import _MIXIN_VERSION_BY_GENERATION

# Kinds with an authored probe battery. `hypothesis` is `test_hypothesis_entity.py`, whose
# `_BATTERY` covers all 27 of its shared fields and runs against every hypothesis profile.
# S1b adds the other four; each addition is ~20-27 fields of hand-authored probe values, and a
# name may only be added here once that file exists and passes.
VALUE_RECONCILED_KINDS = frozenset({"hypothesis"})

# The exact remainder, frozen. This is a RATCHET, not a target: it must SHRINK deliberately as
# S1b authors batteries, and any growth means a mixin was declared without anyone classifying it.
PENDING_PROFILES = frozenset(
    {
        (2, "dataset"), (3, "dataset"),
        (2, "paper"), (3, "paper"),
        (2, "theme"), (3, "theme"),
        (2, "topic"), (3, "topic"),
    }
)


def _profiles() -> frozenset[tuple[int, str]]:
    return frozenset(
        (generation, kind)
        for generation, kinds in _MIXIN_VERSION_BY_GENERATION.items()
        for kind in kinds
    )


def test_the_declared_kinds_are_all_real_mixin_kinds() -> None:
    # A battery for a kind with no mixin reconciles nothing against nothing.
    unknown = VALUE_RECONCILED_KINDS - {kind for _, kind in _profiles()}
    assert not unknown, f"declared value-reconciled, but no mixin declares them: {sorted(unknown)}"


def test_pending_profiles_is_exactly_the_underived_remainder() -> None:
    # Both directions. A newly declared mixin or generation lands in `derived` and fails here
    # until someone either authors a battery or records the debt -- it cannot arrive silently.
    derived = frozenset(p for p in _profiles() if p[1] not in VALUE_RECONCILED_KINDS)
    assert PENDING_PROFILES == derived, (
        f"unclassified: {sorted(derived - PENDING_PROFILES)}; "
        f"stale: {sorted(PENDING_PROFILES - derived)}"
    )


def test_the_reconciled_profiles_are_the_complement() -> None:
    reconciled = _profiles() - PENDING_PROFILES
    assert reconciled == frozenset({(2, "hypothesis"), (3, "hypothesis")}), (
        f"value-reconciled profiles are {sorted(reconciled)}; "
        f"expected both hypothesis generations and nothing else"
    )
```

- [ ] **Step 2: Run it**

```bash
cd science/model && uv run --frozen pytest tests/test_value_reconciliation.py -v
```

Expected: PASS, 3 tests. (This file is a pure declaration-versus-derivation check, so it is green
on arrival — its value is in Steps 3 and 4, which show it can fail.)

- [ ] **Step 3: Prove a new mixin cannot arrive unclassified**

In `science/model/src/science_model/entity_schema/profile.py`, temporarily add `"question": "1.0"`
to the generation-2 entry of `_MIXIN_VERSION_BY_GENERATION`.

```bash
cd science/model && uv run --frozen pytest tests/test_value_reconciliation.py -v
```

Expected: `test_pending_profiles_is_exactly_the_underived_remainder` FAILS with
`unclassified: [(2, 'question')]`. Revert and confirm PASS.

- [ ] **Step 4: Prove an unearned claim cannot pass**

Temporarily change `VALUE_RECONCILED_KINDS` to `frozenset({"hypothesis", "dataset"})`.

Expected: `test_pending_profiles_is_exactly_the_underived_remainder` FAILS with
`stale: [(2, 'dataset'), (3, 'dataset')]`. `test_the_reconciled_profiles_are_the_complement`
does NOT fail from this mutation — it reads only `PENDING_PROFILES` (a hand-frozen literal) and
`_profiles()`, never `VALUE_RECONCILED_KINDS` or anything derived from it, so it cannot see this
change. Revert and confirm the first test PASSES. **Record both outcomes in the commit message.**

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/.worktrees/reconciliation-gate && git branch --show-current  # must print reconciliation-gate
git add science/model/tests/test_value_reconciliation.py
git commit -m "test(schema): ratchet which profiles have a probe battery

Nothing stated which kinds have probe values, so a newly declared mixin
could arrive with none and no test would notice. The declaration is a
kind set; the pending profile set is derived from it and frozen in both
directions."
```

---

## Task 4: The field-declaration gate

**Files:**
- Create: `science/tests/test_kind_reconciliation.py`

**Interfaces:**
- Consumes: `admitted_field_names` (Task 1); `CORE_KIND_MODELS` from `science_tool.graph.entity_registry`; `_MIXIN_VERSION_BY_GENERATION` from `science_model.entity_schema.profile`.
- Produces: nothing other tasks import.

**Background the implementer needs.** 31 `(kind, field)` pairs are admitted by a schema and not
declared on the projection. Under `extra="allow"` they are preserved as untyped extras rather than
dropped — but they are unwired, and no general diagnostic covers them (the graph audit's
`undeclared_key` fires only for 6 reference-shaped field names, and is suppressed for
strict-schema kinds; the intersection with these 31 is empty).

Each gap is exempted for one of two reasons. A `Reader` names a symbol that performs a keyed read
of the field. **The AST check proves the symbol exists and reads a mapping key of that name — it
does NOT prove the mapping is this kind's frontmatter.** That last step is human judgment, and the
check is demonstrably not sufficient on its own: `datasets_register._proxy_source_datasets` calls
`proxy.get("sources")` and passes the check while reading a nested key of `identity_contract`,
nothing to do with an entity's `sources` field. Every `Reader` entry therefore names the mapping in
its note. A `PendingRuling` is explicit debt: someone looked and found no reader.

- [ ] **Step 1: Write the gate**

```python
"""Every field a kind's schema admits is declared on that kind's projection.

D3 rules that JSON Schema is authoritative for entity fields and Pydantic is a PROJECTION of it.
`test_hypothesis_entity.py` proves that field-by-field for one kind. This file proves the
DECLARATION half for every kind that has a schema, at every live generation.

☠️ Lives in the TOOL suite, not `model/tests/`, because the kind -> model binding is
`CORE_KIND_MODELS` here in `science_tool`, and `science_model` may not import its consumer.
Entity subclasses do not self-declare their kind, so that dict is the only map. That the binding
sits in neither authority's package is a real finding; relocating it is S2's call, not S1a's.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import textwrap
from dataclasses import dataclass

import pytest

from science_model.entities import ProjectEntity
from science_model.entity_schema import admitted_field_names, default_profile_for_kind
from science_model.entity_schema.profile import _MIXIN_VERSION_BY_GENERATION
from science_tool.graph.entity_registry import CORE_KIND_MODELS

PROFILES = sorted(
    (generation, kind)
    for generation, kinds in _MIXIN_VERSION_BY_GENERATION.items()
    for kind in kinds
)


@dataclass(frozen=True, slots=True)
class Reader:
    """A named symbol that performs a keyed read of the field.

    `mapping` is prose naming WHAT is read, and it is load-bearing: the AST check below proves a
    keyed read of the name, not that the mapping is this kind's frontmatter. Necessary, not
    sufficient -- see `test_the_reader_check_is_not_sufficient_on_its_own`.
    """

    module: str
    symbol: str
    mapping: str


@dataclass(frozen=True, slots=True)
class PendingRuling:
    """Explicit debt: someone looked for a reader and found none.

    NOT evidence the gap is benign. S1b/S2 resolves each by declaring the field on the model,
    forbidding it in the mixin, or producing a reader.
    """

    note: str


_BOTH = frozenset({2, 3})
_COMMONS_FOUR = ("dataset", "paper", "theme", "topic")

_DATASET_PRIORITIZE = ("science_tool.dataset_prioritize", "target_coverage")

# (kind, field) -> (generations, reason). Expanded to (generation, kind, field) triples before
# comparison, so a generation 4 inherits NOTHING implicitly: its gaps must be declared or the gate
# fails. Today every entry applies to both generations; that is measured, not assumed.
UNHELD: dict[tuple[str, str], tuple[frozenset[int], Reader | PendingRuling]] = {
    ("hypothesis", "required_capabilities"): (
        _BOTH,
        Reader(*_DATASET_PRIORITIZE, "raw entity frontmatter via _iter_entity_frontmatter, gated on _is_qh"),
    ),
    ("hypothesis", "capability_scope"): (
        _BOTH,
        Reader(*_DATASET_PRIORITIZE, "raw entity frontmatter via _iter_entity_frontmatter, gated on _is_qh"),
    ),
    ("dataset", "provided_capabilities"): (
        _BOTH,
        Reader("science_tool.skills_coverage.evidence", "project_evidence",
               "entity.model_extra, inside `if entity.kind != 'dataset': continue`"),
    ),
    ("dataset", "sources"): (
        _BOTH,
        Reader("science_tool.commons.promote_dataset", "_dataset_recipe_source_hint",
               "the merged dataset entity fields, passed from commons.promote"),
    ),
    ("dataset", "runtime_state"): (
        _BOTH,
        PendingRuling(
            "datasets.semantics.runtime_state_for(fm) DERIVES this from dataset_class_for / "
            "has_runtime_artifact / _access; the row['runtime_state'] reads consume that derived "
            "output and commons.promote writes it. No reader of an AUTHORED value."
        ),
    ),
    ("paper", "paper_kind"): (
        _BOTH,
        Reader("science_tool.validate.checks.document_structure", "_check_documents",
               "ctx.frontmatter(path)"),
    ),
    ("paper", "arxiv"): (
        _BOTH,
        PendingRuling("skills_lint.sources._build_record reads `arxiv` from the SKILLS source registry, not entity frontmatter"),
    ),
    ("paper", "pmcid"): (
        _BOTH,
        PendingRuling("paper_fetch reads `pmcid` from a fetched API record, not entity frontmatter"),
    ),
}

for _kind in _COMMONS_FOUR:
    UNHELD[(_kind, "tags")] = (
        _BOTH,
        Reader("science_tool.commons.registry", "RegistryBuilder._insert_records", "record.frontmatter"),
    )
    UNHELD[(_kind, "schema_profile")] = (
        _BOTH,
        Reader("science_model.entity_schema.validator", "EntityValidator.validate",
               "the entity dict built from frontmatter (the commons path)"),
    )
    UNHELD[(_kind, "version")] = (
        _BOTH,
        Reader(
            "science_tool.validate.checks.commons_owner_collision",
            "check_commons_owner_collision",
            "record.frontmatter.get('version'), where record is the commons canonical "
            "(any of dataset/paper/theme/topic) resolved by CommonsQuery.show for the id "
            "of whatever project entity is being checked -- kind-agnostic by construction",
        ),
    )
    UNHELD[(_kind, "contributors")] = (
        _BOTH,
        PendingRuling("no keyed read of `contributors` exists anywhere in science_tool or science_model"),
    )
    UNHELD[(_kind, "licenses")] = (
        _BOTH,
        PendingRuling("no keyed read of `licenses` exists anywhere in science_tool or science_model"),
    )

for _kind in ("paper", "theme", "topic"):
    UNHELD[(_kind, "sources")] = (
        _BOTH,
        PendingRuling(
            "keyed `sources` reads exist (commons.catalog's catalog file, annotation.prose_health's "
            "manifest, skills_lint's skill frontmatter, tooling_dependency's uv config, "
            "identity_context's nested identity_contract.assembly.proxy key, and "
            "graph.store.queries/causal.export_*'s provenance-derived row dicts), but none reads a "
            "paper/theme/topic entity frontmatter `sources` -- no reader of that value exists"
        ),
    )


def _expanded() -> dict[tuple[int, str, str], Reader | PendingRuling]:
    return {
        (generation, kind, field): reason
        for (kind, field), (generations, reason) in UNHELD.items()
        for generation in generations
    }


def _model_for(kind: str) -> type:
    return CORE_KIND_MODELS.get(kind, ProjectEntity)


def _resolve(module: str, symbol: str) -> object:
    obj: object = importlib.import_module(module)
    for part in symbol.split("."):
        obj = getattr(obj, part)
    return obj


def _reads_key(symbol: object, field: str) -> bool:
    """True if `symbol`'s source performs a keyed read of the literal `field`."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(symbol)))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == field
        ):
            return True
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == field
        ):
            return True
    return False


@pytest.mark.parametrize("generation,kind", PROFILES)
def test_every_admitted_field_is_declared_on_the_projection(generation: int, kind: str) -> None:
    """EXACT equality against the frozen manifest, not a subset.

    A stale exemption fails as loudly as a new gap. The hand-written half is the half that falls
    behind, and it falls behind in both directions -- an exemption for a field that is now declared
    reads like known debt that no longer exists.
    """
    admitted = admitted_field_names(default_profile_for_kind(kind, generation=generation))
    gaps = admitted - set(_model_for(kind).model_fields)
    exempt = {f for (g, k, f) in _expanded() if (g, k) == (generation, kind)}

    assert gaps == exempt, (
        f"gen {generation} {kind}: undeclared gap {sorted(gaps - exempt)}; "
        f"stale exemption {sorted(exempt - gaps)}"
    )


@pytest.mark.parametrize(
    "kind,field",
    sorted(k for k, (_, reason) in UNHELD.items() if isinstance(reason, Reader)),
)
def test_every_declared_reader_exists_and_reads_its_field(kind: str, field: str) -> None:
    reader = UNHELD[(kind, field)][1]
    assert isinstance(reader, Reader)
    symbol = _resolve(reader.module, reader.symbol)
    assert _reads_key(symbol, field), (
        f"{reader.module}.{reader.symbol} is cited as the reader of {kind}.{field}, "
        f"but its source performs no keyed read of {field!r}"
    )


def test_the_reader_check_is_not_sufficient_on_its_own() -> None:
    """The check proves a keyed read of the NAME, never that the mapping is the right one.

    This is not a caveat in prose -- it is demonstrable. `_proxy_source_datasets` reads
    `identity_contract['assembly']['proxy']['sources']`, nothing to do with an entity's `sources`
    field, and it satisfies the check. That is why every `Reader` carries a `mapping` note and why
    `paper`/`theme`/`topic` `sources` is `PendingRuling` despite this function existing.
    """
    from science_tool.datasets_register import _proxy_source_datasets

    assert _reads_key(_proxy_source_datasets, "sources")
    assert isinstance(UNHELD[("paper", "sources")][1], PendingRuling)


def test_every_exemption_names_a_live_profile() -> None:
    # A manifest entry for a (generation, kind) that no longer exists never runs, and reads like
    # debt that is being tracked when it is not.
    orphans = {(g, k) for (g, k, _) in _expanded()} - set(PROFILES)
    assert not orphans, f"exemptions for profiles that do not exist: {sorted(orphans)}"
```

- [ ] **Step 2: Run the gate**

```bash
cd science && uv run --frozen pytest tests/test_kind_reconciliation.py -v
```

Expected: PASS — 10 profile cases, 17 reader cases, and 2 standalone tests.

- [ ] **Step 3: Prove it catches a new gap**

In `science/model/src/science_model/entities.py`, temporarily comment out a declared field on
`PaperEntity` (pick one the paper mixin declares, e.g. `year` — NOT `doi`: `doi` is named in a
`field_validator` decorator on the same class, so removing its field assignment raises
`PydanticUserError` at import time instead of exercising the gate; `year` is referenced by no
validator).

```bash
cd science && uv run --frozen pytest tests/test_kind_reconciliation.py -k "declared_on_the_projection" -v
```

Expected: both `paper` cases FAIL with `undeclared gap ['year']`. Restore and confirm PASS.

- [ ] **Step 4: Prove it catches a stale exemption**

Temporarily delete the `("paper", "pmcid")` entry from `UNHELD`, run the same command, and expect
both `paper` cases to FAIL with `undeclared gap ['pmcid']`. Then restore it and instead add
`("paper", "doi"): (_BOTH, PendingRuling("spurious"))`; expect both `paper` cases to FAIL with
`stale exemption ['doi']`. Restore.

- [ ] **Step 5: Prove the manifest is generation-keyed**

In `science/model/src/science_model/entity_schema/profile.py:96-104`, temporarily add a
generation-4 entry to `_MIXIN_VERSION_BY_GENERATION` copying generation 3's dict verbatim.
`_BASE_VERSION_FOR_MIXIN` needs **no** change — it is keyed by kind, not by generation.

```bash
cd science && uv run --frozen pytest tests/test_kind_reconciliation.py -k "declared_on_the_projection" -v
```

Expected: five new `generation=4` cases FAIL, each reporting its full gap set as an undeclared gap
— because `_BOTH` is `frozenset({2, 3})` and nothing was declared for 4. **This is the proof that a
pair-keyed manifest would have silently exempted them.** Revert.

- [ ] **Step 6: Prove the reader check can fail**

Temporarily repoint `("paper", "paper_kind")`'s reader at a symbol that does not read it, e.g.
`Reader("science_tool.commons.registry", "RegistryBuilder._insert_records", "wrong")`.

```bash
cd science && uv run --frozen pytest tests/test_kind_reconciliation.py -k "reader_exists" -v
```

Expected: the `paper-paper_kind` case FAILS. Revert and confirm PASS.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/.worktrees/reconciliation-gate && git branch --show-current  # must print reconciliation-gate
git add science/tests/test_kind_reconciliation.py
git commit -m "test(schema): gate that every admitted field is declared on its projection

Generalizes the field-declaration half of the hypothesis reconciliation
to every kind with a schema, at every live generation. The 31 known gaps
are frozen in a generation-keyed manifest with a reason each: 17 name a
reader whose keyed read is checked by AST, 14 are explicit debt.

The reader check is necessary, not sufficient, and the file proves it
rather than saying it -- _proxy_source_datasets satisfies the check while
reading an unrelated nested key."
```

---

## Final gate — top-level agent only

**Do not run this inside a task subagent.** The full suite is ~10k tests and takes 2-3 minutes,
which exceeds the default 120s command timeout; a foreground run auto-backgrounds and a subagent
that yields waiting on it will not reliably resume. Run the two suites **sequentially** — never
concurrently in one worktree, they race on shared test-output paths.

- [ ] **Step 1: Model suite**

```bash
cd science/model && uv run --frozen pytest
```

- [ ] **Step 2: Tool suite**

```bash
cd science && uv run --frozen pytest
```

- [ ] **Step 3: Lint and types**

```bash
cd science && uv run ruff check && uv run pyright
cd science/model && uv run ruff check
```

Ruff is configured per package; pyright is configured once by the repo-root `pyrightconfig.json`
and covers all three source trees regardless of which package you run it from. Test directories are
not type-checked, so only Task 1's changes are in pyright's scope.

- [ ] **Step 4: Confirm the working tree is clean**

Every mutation proof in Tasks 1-4 edits a source or schema file and reverts it. Confirm nothing
survived:

```bash
cd ~/d/science/.worktrees/reconciliation-gate && git status --porcelain
```

Expected: empty. A stray uncommitted schema edit from a mutation proof would be a silently
loosened contract.

---

## Self-Review

**Spec coverage.** Design §2 → Task 1. §3.1, §3.2, §3.3 → Task 4. §3.4 → see the deviation below.
§3.5, §3.6 → Tasks 2 and 3. §5's mutation table → distributed as proof steps inside the task that
owns each guard, rather than collected into a task of its own: a mutation proof is the "watch it
fail" half of the test cycle, and separating it from the guard it exercises is how it gets skipped.

**Two deliberate deviations from the design:**

1. **§3.4's composition self-check is not a separate assertion.** The design specifies a test
   asserting that the hypothesis mixin's 17 `false` properties are excluded from
   `admitted_field_names`. Task 1 Step 1 asserts exclusion for two representative members
   (`tags`, a base-declared forbidden field, and `phase`, a mixin-only one) plus non-exclusion for
   `description`, and Task 1 Step 7 proves the assertion fails when the fix is reverted. Enumerating
   all 17 by name would restate the mixin's contents in a test — the same
   declaration-in-two-places defect this sub-project exists to remove — and the 17 are already
   covered structurally: any one of them flipping from `false` to `{}` makes it admitted, which
   fails Task 4's exact-equality gate for hypothesis. **If the reviewer prefers the design's literal
   17-name assertion, it belongs in Task 1 Step 1 and is a two-line addition.**
2. **§3.4/§3.5's guards are split across packages.** The design places them in one file. The
   composition check has no kind→model dependency and belongs beside the derivation it guards
   (model suite); the field-declaration gate needs `CORE_KIND_MODELS` and cannot live there. The
   split follows the import constraint, not preference.

**Placeholder scan.** No TBD/TODO. Every code step carries the actual code; every mutation proof
names the exact file, the exact edit, and the exact expected failure text.

**Type consistency.** `admitted_field_names(profile, loader=None) -> frozenset[str]` is defined in
Task 1 and consumed with that signature in Tasks 2 and 4. `_PROFILE_BY_GENERATION` /
`_SHARED_BY_GENERATION` are introduced and used only within Task 2. `Reader` /`PendingRuling` /
`UNHELD` / `_expanded()` are introduced and used only within Task 4. `VALUE_RECONCILED_KINDS` and
`PENDING_PROFILES` are introduced and used only within Task 3. No task references a name another
task does not define.

**Validated before writing, not asserted.** Every quantity in this plan was run against the
worktree at `d9e79f91`:

- The generalized ordered-composition derivation in Task 1 returns results **identical** to the
  existing hand-rolled `_ADMITTED` on all 10 profiles.
- The Task 1 fix drops `read_effective_frontmatter_fields`'s hypothesis output from 35 keys to 29,
  removing exactly the 6 forbidden base fields and nothing else.
- Task 4's manifest was replicated and compared to the real derived gaps: **31 entries, 17 `Reader`,
  14 `PendingRuling`, and 0 of 10 profiles mismatching** — the gate ships green.
- All 17 `Reader` symbols resolve and pass the AST check; `_proxy_source_datasets` passes it too,
  which is why Task 4 asserts that as a test rather than noting it as a caveat.
- `PaperEntity` declares `doi` and the paper profile admits it, so Task 4 Step 3's mutation
  produces a real gap.
- Task 2's premise — that the existing battery's 27 fields and 108 probe values return identical
  verdicts against generation 3, with no field going vacuous — was run before the design claimed it.

**The one thing not pre-validated** is Task 2 Steps 8 and 9, the paired gen-2/gen-3 mutation
proofs. They require editing a shipped schema file, which was out of scope for a read-only
investigation. `composition_rule` does discriminate the way those steps expect, using
`"evidence_union"` — already a `_BATTERY` value, and reserved (rejected by the model via
`RESERVED_COMPOSITION_RULES`), so widening either mixin's enum to admit it produces exactly the
"schema admits it, model rejects it" case the mutation proof needs. `status` is NOT a usable
fallback: `HypothesisEntity.status` is an unrestricted `str | None`, so no schema-side enum
widening on it can ever make the model the stricter side — the model already accepts anything.

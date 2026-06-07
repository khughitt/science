# Scope-Aware Loading & Resolver Activation (Substrate Phase 1.4a) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a two-scope `IdentityTable` **producible from disk** (a `canonical_id` owned by both this project **and** commons records *both* owner rows), then **wire the Phase-1.3 scope-aware resolver into both consumers** — `audit_project_sources` and the graph builder — so the dormant §B3a mechanism goes **live**: a bare ref owned in >1 loaded scope becomes an `ambiguous_reference` audit failure, a scoped form (`commons:topic:x`) resolves, and a strict `materialize_graph` refuses to build an ambiguous project.

**Architecture:** Phase 1.3 shipped the scope-aware `ReferenceResolver` + the dormant `_audit_reference` branch but wired **neither** consumer, because no disk loader could produce a two-scope table (the commons loader *suppresses* loading a commons owner whose id is already locally owned). 1.4a removes exactly that gap. (1) The commons loader stops blanket-suppressing locally-owned ids from its query, so it can discover that commons *also* owns a referenced locally-owned id, and records a `owner_scope = "commons"` **declaration** for it — **without** materializing a duplicate `Entity` and **without** the cross-scope strict-raise (a local owner + a commons owner are two *different* identity keys `(this-project, id)` vs `(commons, id)`, never a §B3 collision). (2) `audit_project_sources` and (3) the graph builder `_build_dataset_from_sources` each construct their `ReferenceResolver` with `identity_table=build_identity_table(sources)`, activating scoped-form resolution and `scope_ambiguous` on real disk. The "hard-fail under strict" decision needs **no new `raise`**: `materialize_graph` already gates on `audit_project_sources` (`materialize.py:193-200`) and raises `ValueError` when any row is a `fail` — once audit is scope-aware, an `ambiguous_reference` row makes it refuse before the builder runs. Wiring the builder's resolver too (Task 3) closes the symmetric fail-open 1.3 flagged: a *scoped* ref must **resolve and materialize**, not be silently dropped.

**Tech Stack:** Python 3, pytest. Library at `~/d/science/science/` (`src/science_tool/`, `tests/`). Run tests with `cd ~/d/science/science && uv run --frozen pytest`. ruff 120-char.

**Activation / blast radius (read carefully — unlike 1.3 this is NOT zero-blast-radius):** 1.4a is the *activation* phase. After it, a project that locally owns a `canonical_id` that commons **also** owns — and references it — will surface a real `ambiguous_reference` audit failure and a strict `materialize_graph` refusal. That is the intended §B3a behavior (the design wants these flagged, not silently shadowed by the local owner as today). It means real projects can newly fail audit/build where they passed before. The change is **incremental and safe between tasks**: Task 1 alone only *records* the second owner row (a two-scope table is **not** a §B3 collision and produces **no** new failure while the resolvers stay scope-naive); the first behavior change lands at Task 2 (audit wiring) and is mirrored at Task 3 (build wiring). The library test-suite has no fixture that both locally-owns and commons-owns the same id, so the existing suite stays green; the new disk-level tests in this plan construct that situation explicitly.

**Scope (this plan only):** scope-aware commons-**owner** declaration recording in the loader (two-scope table producible from disk); wiring `build_identity_table`-driven scope-awareness into `audit_project_sources` (`migrate.py:168`) and `_build_dataset_from_sources` (`materialize.py:91`). **Out of scope** (later sub-plans / phases): the §C4 migrator rework — retire the `entity_layout_migration.py` simulation/masking hack + the alias-collision proxy, drive collision detection + apply-gating from `build_identity_table`, renumber only real this-project owners (**Phase 1.4b**, its own plan); orphan-datapackage synthesized owners + dataset dual-SSOT (1.5/§B4); `entities.yaml` retirement (Phase 3); the federated cross-project reference syntax against a *remote* scope's owners (`t068`, §D4). This plan does **not** change overlay/borrower suppression semantics, does **not** re-key the local dedup `dict`, and does **not** materialize a second `Entity` per id (so the `build_alias_map`/`entity_index` last-wins consumers are untouched).

**Design source:** `~/d/science/docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md` — §B1 (substrate invariant: one owner per `(id, owner_scope)`; borrowers never renumbered), §B3 (identity key `(owner_scope, canonical_id)`; collision = two *owner* rows same key; a commons owner + a project borrower of the same id are two different rows), §B3a (executable bare-ref resolution; multi-scope owner → `ambiguous_reference`; scoped form required), §C2 (every consumer reads the compiled model).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/science_tool/graph/commons_sources.py` | (a) Teach `_maybe_add` to collect the inner commons id from a `commons:<kind>:<slug>` **scoped** ref so scoped refs pull/record their commons owner; (b) stop blanket-suppressing locally-owned ids from the commons query; return the set of referenced ids that commons **also owns** (collide with a local owner) as a separate channel, so their commons-scope owner declaration can be recorded without materializing a duplicate `Entity` | **Modify** |
| `src/science_tool/graph/sources.py` | Record an `owner_scope = "commons"` OWNER declaration for each cross-scope commons owner returned by the loader, **without** appending a second `Entity` and **without** the strict cross-scope raise | **Modify** |
| `src/science_tool/graph/migrate.py` | `audit_project_sources`: build the identity table **once** and pass it to the resolver at line 168 (and reuse it for the existing `audit_identity_table` call at ~line 210) | **Modify** |
| `src/science_tool/graph/materialize.py` | `_build_dataset_from_sources`: construct the resolver with `identity_table=build_identity_table(sources)` (line 91) so scoped refs resolve at build | **Modify** |
| `tests/test_graph_commons_sources.py` | Loader test: commons owner of a referenced locally-owned id is returned on the new channel; existing-behavior tests stay green | **Modify** (append) |
| `tests/test_substrate_two_scope_e2e.py` | End-to-end: a project that locally owns + references a commons-owned id ⇒ `load_project_sources` yields a 2-scope `owner_scopes_by_id`; `audit_project_sources` emits `ambiguous_reference`; `materialize_graph` raises; a scoped form resolves and materializes | **Create** |

### Reference facts (verified against `main` @ `02e3527b`)

- **Loader dedup** (`sources.py:270`): `identity_table: dict[str, SourceRef] = {}` keyed by **bare** `canonical_id`. The main adapter loop (`sources.py:386-404`) and legacy loop (`sources.py:420-438`) append an OWNER `IdentityDeclaration` (via `classify_owner_scope(adapter.name, project_name=project_name)`) **before** the dedup check, then dedup: `existing = identity_table.get(cid)`; if present, `strict` → `raise EntityIdentityCollisionError`, else `continue`. **These two loops are NOT modified by this plan** (their strict-raise guards genuine *same-scope* collisions).
- **Commons declaration append** (`sources.py:484-515`): for each `(entity, ref)` in `commons_loaded`, append an OWNER declaration with `classify_owner_scope(ref.adapter_name=…"commons-merged"…)` → `owner_scope="commons"` (lines 485-495), a BORROWER declaration if an overlay exists (496-507), then the **same** dedup block (508-512) that raises under strict on an already-present id. **This dedup block is where the cross-scope raise must be removed** (see Task 1): a commons owner of a locally-owned id is cross-scope, not a collision.
- **Commons loader suppression** (`commons_sources.py`): `referenced_ids.difference_update(identity_table)` (line 87) removes locally-owned ids **before** querying commons; `pending_ids = referenced_ids | (set(overlays) - set(identity_table))` (line 89); `resolved_ids: set[str] = set(identity_table)` (line 101) seeds the transitive guard with locally-owned ids. The function signature takes `identity_table: dict[str, SourceRef]` and returns `tuple[list[tuple[Entity, SourceRef]], dict[str, str]]` (loaded entities + overlay paths). `query.show(canonical_id)` raises `CommonsEntityError` when commons has no such id (caught at 111-118 → `continue`).
- **`_maybe_add`** (`commons_sources.py:251-267`) is the predicate that decides whether a raw ref string is a commons reference: it rejects external/metadata refs and anything whose `prefix = raw.split(":",1)[0]` is not in `_COMMONS_TYPES = {"dataset","paper","topic","theme"}` (`commons_sources.py:38`). It does **not** understand the Phase-1.3 **scoped form** `commons:<kind>:<slug>` (prefix `"commons"` ∉ `_COMMONS_TYPES` ⇒ silently dropped). It is called throughout `collect_referenced_commons_ids` (`commons_sources.py:149-184`).
- **`audit_project_sources`** (`migrate.py:164-214`): builds the resolver at **line 168** via `ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)` (no identity table); separately calls `audit_identity_table(build_identity_table(sources))` additively at **~line 210**. `build_identity_table` is already imported (`migrate.py:30`). `migrate.py:261` builds another resolver inside `audit_project_graph` and `migrate.py:~261` reads only `.alias_map` — leave both unless noted.
- **`_build_dataset_from_sources`** (`materialize.py:80-162`): builds the resolver at **line 91** via `ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)`; `entity_index = {e.canonical_id: e for e in sources.entities}` (line 92, last-wins — safe because this plan keeps one `Entity` per id); uniformly skips non-`resolved` statuses downstream (`_add_relations`, `_add_authored_relation`, etc.). `materialize_graph` (line 165) is strict-by-default; **lines 193-200** load sources, run `audit_project_sources`, and `raise ValueError` if `has_failures` — this is the existing gate that delivers "hard-fail under strict" for `scope_ambiguous` once audit is wired.
- **`ReferenceResolver.from_entities(entities, *, manual_aliases=None, identity_table=None)`** (Phase 1.3): with an identity table it builds `owner_scopes`/`scope_names`/`owner_scopes_by_root`; `resolve` returns `scope_ambiguous` (candidates = sorted owning scopes) for a bare id owned in >1 scope, and resolves a `<scope>:<kind>:<slug>` form against that scope's owners. With no identity table it is byte-for-byte legacy. `IdentityTable.owner_scopes_by_id() -> dict[str, frozenset[str]]`.
- **`_audit_reference`** (Phase 1.3, `migrate.py`): maps `scope_ambiguous` → one `{"check":"ambiguous_reference","status":"fail",…}` row. Dormant on `main` because line 168 is scope-naive.
- **Commons test harness** (`tests/test_graph_commons_sources.py`): `_build_commons(tmp_path)` copies `tests/fixtures/commons/valid/` → `tmp_path/commons` and runs `RegistryBuilder(...).rebuild()`; tests `monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))` + `SCIENCE_COMMONS_QUIET_STALE=1`. The fixture owns `topic:single-cell-foundation-models` and `paper:Adams2025`. `test_orchestrator_skips_overlay_when_project_identity_already_exists` (line 520) shows the **current** suppression: with `identity_table={"topic:single-cell-foundation-models": …}` the loader returns `([], {})`. `test_load_project_sources_pulls_commons_referenced_topic` (line 590) shows the full-loader idiom (writes `science.yaml`, `knowledge/sources/local/manifest.yaml`, `entities/hypotheses/h1.md` with `related: ["topic:single-cell-foundation-models"]`).
- **All new names are free** (`grep` confirms): `commons_owner_collisions` (proposed return-channel name), `tests/test_substrate_two_scope_e2e.py`. No `tests/test_substrate_two_scope*` exists.

---

## Task 1: Loader records the cross-scope commons owner (two-scope table producible)

Make `_load_commons_referenced_entities` discover that commons **owns** a referenced locally-owned id and surface it on a **separate** return channel; have `load_project_sources` record that as a `owner_scope="commons"` OWNER declaration **without** appending a duplicate `Entity` and **without** the cross-scope strict-raise. After this task a two-scope `IdentityTable` is producible from disk; no new failure fires yet (resolvers still scope-naive).

**Files:**
- Modify: `src/science_tool/graph/commons_sources.py`
- Modify: `src/science_tool/graph/sources.py`
- Test: `tests/test_graph_commons_sources.py`

- [ ] **Step 1: Write the failing loader-unit test**

Append to `tests/test_graph_commons_sources.py`. This pins the new return channel at the `_load_commons_referenced_entities` boundary. The fixture owns `topic:single-cell-foundation-models`; we pass it in `identity_table` (simulating a local owner) AND reference it, and assert the loader now reports it as a **collision** (commons also owns it) rather than silently returning nothing.

```python
def test_commons_owner_of_locally_owned_referenced_id_is_reported_as_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = tmp_path / "project"
    project_root.mkdir()

    # The project locally owns topic:single-cell-foundation-models (seeded in
    # identity_table) AND references it; commons also owns it.
    cid = "topic:single-cell-foundation-models"
    loaded, overlay_paths, commons_owner_collisions = _load_commons_referenced_entities(
        project_root=project_root,
        project_slug="demo",
        project_entities=[_entity("topic:local", related=[cid])],
        project_relations=[],
        project_bindings=[],
        identity_table={cid: SourceRef(adapter_name="markdown", path="entities/topics/x.md")},
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset({"dataset", "paper", "theme", "topic"}),
        ontology_catalogs=[],
    )

    # NOT materialized as a project entity (no duplicate Entity), but reported as a
    # cross-scope commons owner so the caller can record the second owner row.
    assert loaded == []
    assert overlay_paths == {}
    assert [ref.adapter_name for _cid, ref in commons_owner_collisions] == ["commons-merged"]
    assert [c for c, _ref in commons_owner_collisions] == [cid]
```

> The existing `_load_commons` helper passes only `loaded, overlay_paths`; this test calls `_load_commons_referenced_entities` directly because the return arity changes. You will update the `_load_commons` helper in Step 3 to unpack three values so the other tests keep working.

Also append a focused unit test for scoped-form reference collection (so a `commons:<kind>:<slug>` scoped ref pulls/records its commons owner — the disambiguated form a user writes to fix a flagged ambiguity):

```python
def test_collect_referenced_commons_ids_collects_inner_id_from_scoped_ref() -> None:
    # The Phase-1.3 scoped form commons:<kind>:<slug> must collect the underlying
    # commons id, else a scoped ref could never pull/record its commons owner.
    assert _collect(entities=[_entity("topic:local", related=["commons:topic:phf19"])]) == {"topic:phf19"}
    # A non-commons inner kind is still ignored.
    assert _collect(entities=[_entity("topic:local", related=["commons:hypothesis:h1"])]) == set()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_commons_sources.py -q -k "scoped_ref or reported_as_collision"`
Expected: FAIL — `test_commons_owner_of_locally_owned_referenced_id_is_reported_as_collision` fails with `ValueError: not enough values to unpack (expected 3, got 2)` (function still returns a 2-tuple); `test_collect_referenced_commons_ids_collects_inner_id_from_scoped_ref` fails its first assertion (`set()` != `{"topic:phf19"}` — `_maybe_add` drops the scoped form).

- [ ] **Step 3: Implement the loader change**

First, teach `_maybe_add` (`commons_sources.py:251-267`) to also collect the inner commons id from a `commons:<kind>:<slug>` scoped ref. Replace the tail of the function (from the `prefix, value = raw.split(":", 1)` line onward):

```python
    prefix, value = raw.split(":", 1)
    if prefix in _COMMONS_TYPES:
        if value:
            found.add(raw)
        return
    # Scoped reference form commons:<kind>:<slug> (design §B3a): strip the leading
    # "commons" scope and collect the underlying commons id, so a scoped ref pulls
    # and records its commons owner. (Only the "commons" scope is recognized here;
    # project-name and federated scopes are out of scope until t068.)
    if prefix == "commons" and ":" in value:
        inner_prefix, inner_value = value.split(":", 1)
        if inner_prefix in _COMMONS_TYPES and inner_value:
            found.add(value)
    return
```

(The existing early-return filters above this point — `is_external_reference`, `is_metadata_reference`, the `":" not in raw` guard — stay unchanged.)

Then, change `_load_commons_referenced_entities` to (a) compute the locally-owned ids that are **referenced** and **owned by commons**, surfacing them on a new third return value, while (b) NOT loading them as project entities. Concretely:

Replace the suppression + return shape. After `referenced_ids = collect_referenced_commons_ids(...)` (line 81-86), DO NOT discard locally-owned ids wholesale. Instead split them out:

```python
    # Locally-owned ids that are referenced AND owned by commons are a cross-scope
    # situation (design §B3): record commons' owner row, but do NOT load a duplicate
    # entity. Everything else loads as before.
    locally_owned = set(identity_table)
    referenced_local = referenced_ids & locally_owned
    referenced_ids.difference_update(identity_table)

    pending_ids = referenced_ids | (set(overlays) - set(identity_table))

    commons_owner_collisions: list[tuple[str, SourceRef]] = []
    if referenced_local:
        # Resolve commons root lazily only when there is something to check.
        _root = resolve_commons_root()
        if _root.is_dir():
            _q = CommonsQuery(_root, warn_stale=False)
            for cid in sorted(referenced_local):
                try:
                    record = _q.show(cid)
                except CommonsEntityError:
                    continue  # commons does not own it -> not a cross-scope owner
                commons_owner_collisions.append(
                    (cid, SourceRef(adapter_name="commons-merged", path=_commons_source_ref_path(record.type, record.slug)))
                )

    if not pending_ids:
        return [], {}, commons_owner_collisions
```

Keep `resolved_ids: set[str] = set(identity_table)` (line 101) unchanged — the transitive loop still must not re-load locally-owned ids as entities; the collision channel above is the only path that records them. Update the final `return loaded, overlay_paths` (line 146) to `return loaded, overlay_paths, commons_owner_collisions`. Update the early `return [], {}` (line 91) as shown above to the 3-tuple. The function's return annotation becomes:

```python
) -> tuple[list[tuple[Entity, SourceRef]], dict[str, str], list[tuple[str, SourceRef]]]:
```

In `tests/test_graph_commons_sources.py`, update the `_load_commons` helper to unpack and drop the third value so the existing tests are unaffected:

```python
def _load_commons(
    project_root: Path,
    *,
    project_entities: list[Entity] | None = None,
    identity_table: dict[str, SourceRef] | None = None,
) -> tuple[list[tuple[Entity, SourceRef]], dict[str, str]]:
    loaded, overlay_paths, _collisions = _load_commons_referenced_entities(
        project_root=project_root,
        project_slug="demo",
        project_entities=project_entities or [],
        project_relations=[],
        project_bindings=[],
        identity_table=identity_table or {},
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset({"dataset", "paper", "theme", "topic"}),
        ontology_catalogs=[],
    )
    return loaded, overlay_paths
```

In `sources.py`, update the call site (line 473) to unpack three values and record the cross-scope commons owner declarations **without** appending entities:

```python
        commons_loaded, commons_overlay_paths, commons_owner_collisions = _load_commons_referenced_entities(
            project_root=project_root,
            project_slug=project_slug,
            project_entities=entities,
            project_relations=relations,
            project_bindings=bindings,
            identity_table=identity_table,
            registry=registry,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )
        for collision_id, collision_ref in commons_owner_collisions:
            owner_scope, deprecated = classify_owner_scope(collision_ref.adapter_name, project_name=project_name)
            identity_declarations.append(
                IdentityDeclaration(
                    canonical_id=collision_id,
                    participation_mode=ParticipationMode.OWNER,
                    owner_scope=owner_scope,
                    adapter=collision_ref.adapter_name,
                    source_ref=collision_ref,
                    deprecated=deprecated,
                )
            )
            # Deliberately do NOT add to `entities` / `identity_table`: the local owner
            # remains the single materialized entity; the second owner row exists only
            # so reference resolution (once scope-aware) flags the bare ref as
            # ambiguous (design §B3a). No strict raise — cross-scope is not a collision.
```

Place this block immediately after the `_load_commons_referenced_entities` call and **before** the existing `for entity, ref in commons_loaded:` loop. Leave that existing loop (and its strict-raise at 508-512) unchanged: it only ever sees genuinely-new commons entities (never locally-owned ids, which now route through `commons_owner_collisions`).

- [ ] **Step 4: Run the new test + the full commons-sources suite**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_commons_sources.py -q`
Expected: PASS — the new test plus all pre-existing tests in the file (the `_load_commons` helper now unpacks three values; `test_orchestrator_skips_overlay_when_project_identity_already_exists` still returns `([], {})` because that id is an **overlay**, not a reference, so it never enters `referenced_local`).

- [ ] **Step 5: ruff + Commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/commons_sources.py src/science_tool/graph/sources.py tests/test_graph_commons_sources.py && uv run --frozen ruff format --check src/science_tool/graph/commons_sources.py src/science_tool/graph/sources.py tests/test_graph_commons_sources.py` (fix with `ruff format` on those files if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/graph/commons_sources.py science/src/science_tool/graph/sources.py science/tests/test_graph_commons_sources.py
git commit -m "feat(substrate): record cross-scope commons owner row (two-scope table from disk)"
```
Do NOT add any "Co-Authored-By" trailer.

---

## Task 2: Wire `audit_project_sources` to the compiled identity table

Activate scope-aware resolution on the audit path: build the identity table once and pass it to the resolver at `migrate.py:168`. Now a bare ref owned in >1 loaded scope yields `ambiguous_reference` and a scoped form resolves.

**Files:**
- Modify: `src/science_tool/graph/migrate.py`
- Test: `tests/test_substrate_two_scope_e2e.py` (create)

- [ ] **Step 1: Write the failing end-to-end test**

Create `tests/test_substrate_two_scope_e2e.py`. This is the first test that exercises the whole disk→compile→audit path for a two-scope project. Model the on-disk project on `test_load_project_sources_pulls_commons_referenced_topic` (`tests/test_graph_commons_sources.py:590`); copy the `_build_commons` helper idiom.

```python
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import load_project_sources

_COMMONS_FIXTURE = Path(__file__).parent / "fixtures" / "commons" / "valid"
_SHARED_ID = "topic:single-cell-foundation-models"


def _build_commons(tmp_path: Path) -> Path:
    commons_root = tmp_path / "commons"
    shutil.copytree(_COMMONS_FIXTURE, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    return commons_root


def _project_owning_and_referencing_shared_id(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest = project_root / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("", encoding="utf-8")
    # A LOCAL owner file for the same id commons owns.
    topic = project_root / "entities" / "topics" / "single-cell-foundation-models.md"
    topic.parent.mkdir(parents=True)
    topic.write_text(
        f'---\nid: "{_SHARED_ID}"\ntype: "topic"\ntitle: "SCFM (local)"\n---\n', encoding="utf-8"
    )
    # A hypothesis that references the shared id with a BARE ref.
    hyp = project_root / "entities" / "hypotheses" / "h1.md"
    hyp.parent.mkdir(parents=True)
    hyp.write_text(
        f'---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\nrelated: ["{_SHARED_ID}"]\n---\n',
        encoding="utf-8",
    )
    return project_root


def test_load_produces_two_scope_identity_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_owning_and_referencing_shared_id(tmp_path)

    sources = load_project_sources(project_root)
    scopes = build_identity_table(sources).owner_scopes_by_id()[_SHARED_ID]
    assert "commons" in scopes
    assert len(scopes) == 2  # this-project owner + commons owner


def test_audit_emits_ambiguous_reference_for_two_scope_bare_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_owning_and_referencing_shared_id(tmp_path)

    sources = load_project_sources(project_root)
    rows, has_failures = audit_project_sources(sources)
    ambiguous = [r for r in rows if r["check"] == "ambiguous_reference"]
    assert has_failures is True
    assert len(ambiguous) == 1
    assert ambiguous[0]["target"] == _SHARED_ID
    assert ambiguous[0]["source"] == "hypothesis:h1"
```

- [ ] **Step 2: Run to verify the relevant assertion fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_substrate_two_scope_e2e.py -q`
Expected: `test_load_produces_two_scope_identity_table` PASSES (Task 1 already makes the table two-scope). `test_audit_emits_ambiguous_reference_for_two_scope_bare_ref` FAILS — `audit_project_sources`' resolver is still scope-naive (line 168 has no identity table), so the bare ref resolves to the local owner and no `ambiguous_reference` row is emitted (`len(ambiguous) == 0`, `has_failures` is False).

- [ ] **Step 3: Wire the resolver**

In `migrate.py`, inside `audit_project_sources`, build the identity table once and pass it to the resolver. Replace the resolver construction at line 168:

```python
        resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
```

with (build the table before the `try`, reuse it for the existing additive audit at ~line 210):

```python
        identity_table = build_identity_table(sources)
        resolver = ReferenceResolver.from_entities(
            sources.entities, manual_aliases=sources.manual_aliases, identity_table=identity_table
        )
```

Then change the existing `audit_identity_table(build_identity_table(sources))` call (~line 210) to reuse the local: `audit_identity_table(identity_table)`. Make NO other change (leave `migrate.py:261` and the `audit_project_graph` resolver alone — `audit_project_graph` calls `load_project_sources` then `audit_project_sources`, so it inherits the wiring transitively). Confirm `build_identity_table` is imported (`migrate.py:30`); it is.

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_substrate_two_scope_e2e.py -q`
Expected: PASS (both tests).

- [ ] **Step 5: Backward-compat regression**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_migrate.py tests/test_graph_migrate_identity_audit.py tests/test_identity_audit_entrypoints.py tests/test_entity_identity_health.py tests/test_commons_reference_graph.py -q`
Expected: all PASS, unchanged. The audit resolver is now scope-aware, but no existing fixture owns an id in two scopes, so single-scope ids resolve exactly as before and scoped-form parsing only triggers when a loaded scope-name prefixes a kind-qualified ref (none in fixtures). If a fixture newly fails, investigate before proceeding — it would mean a real fixture has a latent two-scope ownership.

- [ ] **Step 6: ruff + Commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/migrate.py tests/test_substrate_two_scope_e2e.py && uv run --frozen ruff format --check src/science_tool/graph/migrate.py tests/test_substrate_two_scope_e2e.py` (fix with `ruff format` if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/graph/migrate.py science/tests/test_substrate_two_scope_e2e.py
git commit -m "feat(substrate): wire audit_project_sources resolver to identity table (activate scope_ambiguous)"
```
No "Co-Authored-By" trailer.

---

## Task 3: Wire the graph builder + prove strict `materialize_graph` refuses an ambiguous project

Wire `_build_dataset_from_sources`' resolver (`materialize.py:91`) to the identity table so a **scoped** ref resolves and materializes (closing the symmetric fail-open 1.3 flagged), and prove that strict `materialize_graph` **refuses** an ambiguous project via the existing audit gate — no new `raise` needed.

**Files:**
- Modify: `src/science_tool/graph/materialize.py`
- Test: `tests/test_substrate_two_scope_e2e.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_substrate_two_scope_e2e.py`. Add the import:

```python
from science_tool.graph.materialize import materialize_graph
```

Then append a helper that writes a project using a **scoped** ref (the disambiguating form), plus two tests:

```python
def _project_with_scoped_ref(tmp_path: Path) -> Path:
    project_root = _project_owning_and_referencing_shared_id(tmp_path)
    # Re-author the hypothesis to use the scoped form -> unambiguous, must materialize.
    hyp = project_root / "entities" / "hypotheses" / "h1.md"
    hyp.write_text(
        f'---\nid: "hypothesis:h1"\ntype: "hypothesis"\ntitle: "H1"\nrelated: ["commons:{_SHARED_ID}"]\n---\n',
        encoding="utf-8",
    )
    return project_root


def test_materialize_graph_refuses_two_scope_bare_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_owning_and_referencing_shared_id(tmp_path)

    with pytest.raises(ValueError) as excinfo:
        materialize_graph(project_root)
    assert "unresolved references" in str(excinfo.value)
    assert _SHARED_ID in str(excinfo.value)


def test_scoped_ref_resolves_and_materializes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons_root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    project_root = _project_with_scoped_ref(tmp_path)

    # Audit clean (scoped form disambiguates) ...
    sources = load_project_sources(project_root)
    rows, has_failures = audit_project_sources(sources)
    assert [r for r in rows if r["check"] == "ambiguous_reference"] == []
    # ... and the build path resolves the scoped ref into a real edge between
    # hypothesis:h1 and topic:single-cell-foundation-models (NOT merely the topic
    # node, which is always present as the local owner).
    trig_path = materialize_graph(project_root)
    assert trig_path.exists()
    assert _has_hypothesis_topic_edge(trig_path)
```

> **Edge assertion — do NOT assert a bare substring.** The local topic owner is always materialized as a node, so `"single-cell-foundation-models" in graph_text` is satisfied even when the scoped edge is dropped — it would not fail at Step 2. Implement `_has_hypothesis_topic_edge(trig_path)` by loading the TriG and checking that an edge exists from `hypothesis:h1` to `topic:single-cell-foundation-models`. **Read an existing materialize test** (`tests/test_produced_by_materialize.py` or `tests/test_dataset_usage_materialize.py`) to copy the exact graph-loading idiom (rdflib `Dataset`/`ConjunctiveGraph.parse(format="trig")`, the `PROJECT_NS`/predicate URIs, and how a `related`/bridge edge between two entities is serialized) — do **not** invent a predicate URI. Assert the subject/object pair is connected; if the precise predicate is awkward to pin, assert that the set of objects reachable from the `hypothesis:h1` subject node includes the topic's URI. The point is a positive edge check that is absent when the scoped ref is dropped.
> If `materialize_graph`'s error message wording differs from `"Cannot materialize graph with unresolved references: …"` (`materialize.py:199`), keep the `test_materialize_graph_refuses_two_scope_bare_ref` assertions tolerant — match on `_SHARED_ID` presence, which is stable.

- [ ] **Step 2: Run to verify the relevant assertion fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_substrate_two_scope_e2e.py -q`
Expected: `test_materialize_graph_refuses_two_scope_bare_ref` PASSES already (Task 2 wired audit, and `materialize_graph` gates on it at `materialize.py:194-200`). `test_scoped_ref_resolves_and_materializes` FAILS at `_has_hypothesis_topic_edge(trig_path)` — the builder resolver (line 91) is still scope-naive, so the **scoped** ref `commons:topic:…` is treated as bare, resolves to nothing, and the `hypothesis:h1 → topic:…` edge is dropped (the topic *node* is still present as the local owner, which is why the edge check — not a node substring — is the discriminating assertion). The audit-clean assertion already passes via Task 2.

> If `test_materialize_graph_refuses_two_scope_bare_ref` does NOT pass at this step, the audit gate is not catching the ambiguous row — stop and re-check Task 2's wiring before continuing.

- [ ] **Step 3: Wire the builder resolver**

In `materialize.py`, ensure `build_identity_table` is imported (add `from science_tool.graph.identity_table import build_identity_table` to the existing imports if absent). Replace the resolver construction at line 91:

```python
    resolver = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)
```

with:

```python
    resolver = ReferenceResolver.from_entities(
        sources.entities, manual_aliases=sources.manual_aliases, identity_table=build_identity_table(sources)
    )
```

Make no other change. The builder still uniformly skips non-`resolved` statuses; a `scope_ambiguous` bare ref would skip here too, but `materialize_graph` never reaches the builder for an ambiguous project (its audit gate raises first). Non-gated callers of `_build_dataset_from_sources` (e.g. the in-memory freshness sweep) skip a `scope_ambiguous` edge harmlessly — acceptable for an in-memory non-authoritative pass.

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_substrate_two_scope_e2e.py -q`
Expected: PASS (all four tests).

- [ ] **Step 5: Backward-compat regression (build path)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_produced_by_materialize.py tests/test_dataset_usage_materialize.py tests/test_produced_by_freshness_e2e.py -q`
Expected: all PASS, unchanged. The builder resolver is now scope-aware, but with no two-scope fixtures the resolution outputs are identical for single-scope ids. If a fixture fails, restore behavior — do not edit the fixture.

- [ ] **Step 6: ruff + Commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/materialize.py tests/test_substrate_two_scope_e2e.py && uv run --frozen ruff format --check src/science_tool/graph/materialize.py tests/test_substrate_two_scope_e2e.py` (fix with `ruff format` if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/graph/materialize.py science/tests/test_substrate_two_scope_e2e.py
git commit -m "feat(substrate): wire graph builder resolver to identity table (scoped refs resolve; strict build refuses ambiguous)"
```
No "Co-Authored-By" trailer.

---

## Task 4: Full-suite green + ruff

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: all PASS (baseline before this plan: 4652 passed, 6 skipped, 4 deselected; this plan adds tests + additive/activated behavior). New activated behavior fires only when an id is owned in **two** loaded scopes, which no existing fixture does — so no real fixture exercises it. If a fixture now fails: a two-scope ownership is genuinely present in that fixture (investigate — it may be a real latent collision the activation correctly surfaced) OR a backward-compat regression slipped into the loader/resolver wiring (restore behavior; do NOT weaken the new tests).

- [ ] **Step 2: Lint/format (changed files)**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/commons_sources.py src/science_tool/graph/sources.py src/science_tool/graph/migrate.py src/science_tool/graph/materialize.py tests/test_graph_commons_sources.py tests/test_substrate_two_scope_e2e.py && uv run --frozen ruff format --check src/science_tool/graph/commons_sources.py src/science_tool/graph/sources.py src/science_tool/graph/migrate.py src/science_tool/graph/materialize.py tests/test_graph_commons_sources.py tests/test_substrate_two_scope_e2e.py`
Expected: clean. (Do NOT repo-wide reformat; the repo carries pre-existing ruff debt elsewhere.)

- [ ] **Step 3: Commit any lint fixes**

Only if Step 2 required changes:
```bash
cd ~/d/science && git add science/src/science_tool/graph/ science/tests/
git commit -m "chore(substrate): ruff clean for scope-aware loading"
```

---

## Self-Review

**1. Spec coverage (§B1/§B3/§B3a/§C2, this plan's scope):**
- "Two-scope table producible from disk" → Task 1 records the cross-scope commons owner declaration; `test_load_produces_two_scope_identity_table` asserts `owner_scopes_by_id` has 2 scopes. ✓
- "A commons owner + a project owner of the same id are two *different* rows, never a §B3 collision; no hard load error" → Task 1 records the second owner row without the strict cross-scope raise (the raise stays only in the same-scope loops). ✓
- "Multi-scope owner → `ambiguous_reference`" → Task 2 wires the audit resolver; `test_audit_emits_ambiguous_reference_for_two_scope_bare_ref`. ✓
- "Scoped form resolves; strict build refuses ambiguous" → Task 1 teaches `_maybe_add` the `commons:<kind>:<slug>` scoped form (so a scoped ref pulls/records its commons owner, putting `commons` in `scope_names`); Task 3 wires the builder resolver (scoped ref materializes into a real edge) and proves `materialize_graph` raises on the bare-ambiguous project via the existing audit gate. ✓ (decision: hard-fail under strict, delivered without a new `raise`)
- "A scoped ref with no accompanying bare ref still resolves" → without the `_maybe_add` scoped-form change the commons owner would never be recorded for a wholly-scoped project and the scoped ref would go unresolved at build; the change closes that. ✓
- §C2 "every consumer reads the compiled model" → both `audit_project_sources` and `_build_dataset_from_sources` now construct their resolver from `build_identity_table(sources)`. ✓
- Backward compatibility: no fixture owns an id in two scopes ⇒ `owner_scopes` has ≤1 scope for every existing id ⇒ `scope_ambiguous` never fires and scoped-form parsing never triggers ⇒ legacy behavior. Asserted by the Task 2/Task 3 regression suites + Task 4 full suite. ✓

**2. Placeholder scan:** No TBD/TODO. Every code step shows complete code; every test step shows assertions + exact commands. The one helper the implementer must complete — `_has_hypothesis_topic_edge(trig_path)` (Task 3) — is flagged inline with explicit instructions to copy the graph-loading idiom + predicate URIs from an existing materialize test (`do not invent a predicate URI`) and a positive edge check (not a node substring). `materialize_graph`'s exact error wording has a stable-substring fallback (`_SHARED_ID`). ✓

**3. Type/name consistency:** `commons_owner_collisions: list[tuple[str, SourceRef]]` is produced in `_load_commons_referenced_entities` (Task 1), unpacked at `sources.py` (Task 1), and never referenced elsewhere. The 3-tuple return shape is updated at all `return` sites and the `_load_commons` test helper. `identity_table` (the compiled `IdentityTable`) is built once in `audit_project_sources` (Task 2) and reused for both the resolver and `audit_identity_table`; distinct from the loader-local `identity_table: dict[str, SourceRef]` (Task 1) — same name, different scope/file, no collision. `build_identity_table` import confirmed present in `migrate.py` and added if absent in `materialize.py`. ✓

**4. Blast radius:** Non-zero by design (this is the activation phase). Production effect: a project that locally owns **and** references a commons-owned id now fails audit (`ambiguous_reference`) and strict `materialize_graph`. No second `Entity` per id is created, so the `build_alias_map`/`_register_alias`/`entity_index` last-wins consumers are untouched (no `AliasCollisionError` risk). The loader change is gated behind `referenced_local` (referenced **and** locally-owned **and** commons-owned) — empty for virtually all current projects, so the existing suite is unaffected. The one real-world activation target is MM30's known `report:lead-validation` content debt; surfacing it is the intended §B3a outcome and is handled by the §C4 migrator/triage in later phases, not here. ✓

---

## Where this sits (Phase 1 roadmap — NOT part of this plan)

Phase 1.1 (`e2b3a757`) compiled `IdentityTable`; 1.2 (`8a87e5b7`) added the owner-root overlay guard; 1.3 (`02e3527b`) built the scope-aware resolver + dormant `ambiguous_reference` branch. **This is Phase 1.4a**: scope-aware loading (two-scope tables from disk) + wiring the resolver into both consumers — the *activation* of §B3a. Remaining Phase-1 sub-plans (each its own full plan):

- **1.4b — Migrator on the compiled model (§C4):** retire the `entity_layout_migration.py` in-memory simulation/masking hack (`_simulated_postmove_audit_failures`) and the `graph/migrate.py` alias-collision proxy; drive collision detection + apply-gating from `build_identity_table` (block apply on any `identity_collision`); renumber only **real this-project** owners (`participation_mode=owner`, `owner_scope=this-project`, **not** transitional), carrying/promoting transitional owners by phase, never touching borrowed/external ids. Depends on 1.4a's scope-aware loader.
- **1.5 — Orphan datapackages + dataset dual-SSOT (§B4):** synthesize deprecated transitional owners for datapackage-only datasets; dataset `doc/datasets/` handling. Depends on 1.1.

Phases 2–4 (dataset reconciliation, `entities.yaml` retirement, external-reference resolver / `t068` federated scoped refs) follow Phase 1 and are out of scope here.

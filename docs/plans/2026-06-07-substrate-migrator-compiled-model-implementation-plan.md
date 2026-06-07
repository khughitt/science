# Migrator on the Compiled Model (Substrate Phase 1.4b) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive the entity-layout migrator's pre-mutation validation off the **compiled identity model** (design §C4): make duplicate ownership a first-class, legible `identity_collision` apply-blocker; retire the "simulation-mask" date hack and the alias-collision proxy; and make the post-move audit respect `participation_mode`/`owner_scope` so a commons **borrower** of an id is never misread as a collision with a project owner.

**Architecture:** The migrator's pre-mutation gate (`_simulated_postmove_audit_failures`, `entity_layout_migration.py:760`) already calls `audit_project_sources` over a post-move source set — and `audit_project_sources` already consumes the compiled model (it builds the `IdentityTable` and runs `audit_identity_table` → `identity_collision` rows additively, `migrate.py:167,213`). The ONLY reason duplicate ownership surfaces today as an opaque `schema_load_failure` (or raises) instead of a clean `identity_collision` is that the post-move model is re-loaded **strict** (`strict_identity=True`), so `EntityIdentityCollisionError` raises *before* `IdentityTable.collisions()` is reached; and the `9999-99-99` undated sentinel would crash the **strict core-schema** load, which is why the date-mask exists. 1.4b changes the post-move compile to **non-strict** (`strict_core_schema=False, strict_identity=False`): `collisions()` then fires naturally (first-class, owner-scoped, borrower-aware), the sentinel stops crashing the load (the date-mask becomes dead and is removed), and a small explicit triage re-surfaces *non-undated* malformed-core entities (`core_schema_validation_failed`) as blockers (preserving parity with the strict post-mutation backstop; undated entities keep their own dedicated guard). The alias-collision proxy is retired because duplicate ownership now has its own `identity_collision` row — `ambiguous_alias` reverts to signalling only genuine alias clashes. **The collision gate is deprecation-aware** (design §C4): because `collisions()` groups *all* owner rows including transitional `deprecated=True` ones, the migrator would otherwise hard-block on the common pre-v3 case of a real markdown owner shadowed by an `entities.yaml` aggregate stub of the same id. So the gate computes its blockers from `build_identity_table(sources).collisions()`, blocking **only** when ≥2 non-deprecated owners share a key, and carrying transitional-involved collisions as non-blocking warnings (surfaced in the report for §B5 retirement, never silently dropped) — and it therefore excludes `audit_project_sources`' own (deprecation-blind) `identity_collision` fail rows from the blocker passthrough.

**Tech Stack:** Python 3, pytest. Library at `~/d/science/science/` (`src/science_tool/`, `tests/`). Run tests with `cd ~/d/science/science && uv run --frozen pytest`. ruff 120-char.

## Interpretation of "Full §C4" — read before implementing (decision: hard, but honest about one constraint)

The user chose **Full §C4** ("post-move validation as a pure function of the compiled model + id-map, retiring the simulate-move-and-reload path") over the surgical alternative. Investigation surfaced one **unavoidable constraint**: the entities the migrator moves live under legacy `doc/`+`specs/` roots that the pre-move loader does **not** scan (`MarkdownAdapter` scans only `entities/`, `research/packages`, `doc/datasets`, `doc/workflows`, `doc/workflow-runs` — `sources.py:253-256`). So the moved entities are **not present in the pre-move compiled model**, and the post-move model cannot be obtained by remapping the pre-move model alone — it must be **compiled** with the moved entities present.

This plan therefore keeps a single post-move **compile** via the *canonical loader* (`load_project_sources(project_root, overrides, …)`, moved entities injected as virtual files at their new paths) and makes the audit a pure read of that compiled model. What is **retired** is the actual "simulation-mask hack": (1) the `_SIM_PLACEHOLDER_DATE` date-mask; (2) the strict-load-then-catch-exceptions-as-blockers dance; (3) the alias-collision proxy (relying on `ambiguous_alias`/`AliasCollisionError` to signal duplicate ownership). The retained compile uses **zero bespoke disk-format awareness** — it is the same compiler every consumer uses (§C2-compliant); only the canonical model is read for validation.

A *truly* reload-free transform (hand-parse the synthesized override texts into `Entity` objects in-memory and splice them into the pre-move model) is **deliberately deferred**: re-implementing the loader's frontmatter/reference parsing by hand on a load-bearing migrator (MM30's v3 migration still depends on it) risks divergence from the canonical parse — a silent audit blind spot — which violates "fail early / avoid silent fallbacks". Reusing the canonical compiler is the safer, more correct realization of §C4's "every consumer reads the compiled model" law. **If the reviewer/user wants the reload-free transform, it is a follow-up (1.4c), not folded in here.**

**Blast radius (non-zero, intended):** a project with two markdown owners of the same `canonical_id` previously blocked `--apply` via an opaque `schema_load_failure`/load crash; it now blocks via a clean `identity_collision` row. A project that *borrows* a commons id (overlay) while a project entity owns the same id is **no longer** misread as a collision (the §B3 "41 phantom collisions" fix reaches the migrator). Undated entities still block (own guard). Non-undated schema-invalid core entities still block (re-surfaced). No production path other than the migrator's **dry-run pre-mutation gate** changes; the strict post-mutation backstop (`entity_layout_migration.py:1013`) is left strict and untouched.

**Design source:** `~/d/science/docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md` — §B3 (identity key `(owner_scope, canonical_id)`; collision = two *owner* rows same key; a commons owner + a project borrower are different rows), §C2 ("every consumer reads the compiled model"), §C4 ("migration as a pure function of the compiled model: renumber real this-scope owners, never transitional/borrowed; collision = two owner rows same key → blocks apply; the simulation-mask hack and overlay/aggregate special-casing are no longer needed").

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/science_tool/entity_layout_migration.py` | (T1) Compile the post-move model **non-strict** (`strict_core_schema=False, strict_identity=False`); remove the `_SIM_PLACEHOLDER_DATE` date-mask; add `_schema_invalid_blockers` (triage on `core_schema_validation_failed`, exclude undated) to re-surface malformed-core entities; compute **deprecation-aware** identity-collision blockers from `build_identity_table(sources).collisions()` (block iff ≥2 non-deprecated owners; transitional-involved collisions become non-blocking warnings) and EXCLUDE `audit_project_sources`' own `identity_collision` fail rows from the blocker passthrough; surface transitional shadows in the report. (T2) Rename `_simulated_postmove_audit_failures` → `_postmove_audit_failures`; refresh now-stale "simulation"/proxy docstrings; keep `_dangling_alias_targets`' mappings-target check (decoupled from its collision-proxy framing) | **Modify** |
| `tests/test_entity_layout_migration.py` | (T1) New: two real owners of one id → clean `identity_collision` blocker (not `schema_load_failure`); markdown owner + transitional aggregate stub of same id → NOT blocked, surfaced as a transitional warning; a `BORROWER` row never collides (direct compiled-model test); non-undated malformed-core (`core_schema_validation_failed`) still blocks; purely-undated no spurious failure still holds. (T2) silent-same-scope-duplicate (no alias clash) now caught; `ambiguous_alias` still fires for a genuine alias clash; mappings dangling-target still blocks; `_SIM_PLACEHOLDER_DATE` gone | **Modify** (append/adjust) |

### Reference facts (verified against `main` @ `1cfd9ca1`)

- **Orchestrator** `migrate_layout(project_root, *, apply)` (`entity_layout_migration.py:874-1030`). Builds `rewritten`/`singleton_text`/`inplace_text`, computes `undated_entities` (`:896-903`), calls the pre-mutation gate `_simulated_postmove_audit_failures(...)` → `structural_failures` (`:955-962`), assembles `report` (`:964-975`), `if not apply: return report` (`:977`). Apply guards (raise, no mutation): `plan.collisions` (`:981`), `structural_failures` (`:983`), `undated_entities` (`:988`). Post-mutation strict backstop `audit_project_sources(load_project_sources(project_root))` (`:1013`) — **leave strict, untouched**.
- **Pre-mutation gate** `_simulated_postmove_audit_failures(project_root, plan, rewritten, singleton_text, inplace_text, undated_new_paths)` (`:760-819`). Builds `overrides` (`.md` only) with the date-mask substitution `text.replace(_UNDATED_SENTINEL, _SIM_PLACEHOLDER_DATE)` for `rel in undated_new_paths` (`:794-796`); `load_project_sources(project_root, overrides)` **strict by default** (`:798`); catches any exception → single `schema_load_failure` blocker (`:799-811`); captures `mappings_aliases = dict(sources.manual_aliases)` BEFORE injecting `plan.id_map` (`:815`); `sources = sources.model_copy(update={"manual_aliases": {**sources.manual_aliases, **plan.id_map}})` (`:816`); `rows, failed = audit_project_sources(sources)` (`:817`); returns `audit_fails + _dangling_alias_targets(sources, mappings_aliases)` (`:818-819`).
- **`_SIM_PLACEHOLDER_DATE = "2000-01-01"`** (`:757`) — used ONLY at `:795`. **`_UNDATED_SENTINEL = "9999-99-99"`** (`:45`) — keep (the undated guard + the new schema-triage exclusion both use it).
- **`_dangling_alias_targets(sources, mappings_aliases)`** (`:822-862`): builds a `ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases)`; on `AliasCollisionError` returns `[]` (lets the audit's `ambiguous_alias` row be the blocker); else validates each `mappings_aliases` target resolves (exempting `is_external_reference`/`is_metadata_reference`), emitting `dangling_alias_target` fails. **Its mappings-target role is legitimate and kept**; only its framing as a collision proxy is retired (the `AliasCollisionError`→`[]` branch stays — `ambiguous_alias` is still emitted by `audit_project_sources`).
- **`load_project_sources(project_root, markdown_overrides=None, *, include_commons=True, strict_core_schema=True, strict_identity=True)`** (`sources.py:178-185`). With `strict_core_schema=False`, a core-kind entity that fails schema validation is recorded as a `SkippedEntity` (reason `entity_schema_validation_failed`) instead of raising (`sources.py:188-194` docstring). With `strict_identity=False`, a duplicate `(owner_scope, canonical_id)` does **not** raise `EntityIdentityCollisionError` — both owner rows are recorded so `IdentityTable.collisions()` can report them (Phase 1.1 design; the additive audit path).
- **`ProjectSources.skipped_entities: list[SkippedEntity]`** (`sources.py:157`). `SkippedEntity` carries `path`, `kind`, `reason`, `details` (per `audit_project_sources`' warn-row emission, `migrate.py:200-210`). **There are THREE distinct `reason` strings (verified in `sources.py`)** and the migrator must triage on exactly the right one:
  - `"unknown_entity_kind"` (`sources.py:322`) — kind not registered. Not a schema failure; do NOT block here (already a warn).
  - `"entity_schema_validation_failed"` (`sources.py:342`, `:381`) — used for (a) a MarkdownAdapter **core entity missing identity fields** (this is skipped *even under strict*, `:332-346`, so it is NOT a malformed-core failure and must NOT newly block), and (b) a **profile-kind** schema failure (`:377-384`). Do NOT triage on this reason.
  - `"core_schema_validation_failed"` (`sources.py:366`) — a **core-kind entity whose schema validation fails under `strict_core_schema=False`** (the branch that would `raise` under strict, `:347-350`). **THIS is the reason `_schema_invalid_blockers` must block on** — it is the malformed-core case (incl. the `9999-99-99` undated sentinel, which fails the date schema; undated paths are excluded so they route to the dedicated undated guard, leaving genuinely-malformed non-undated core entities as blockers — parity with the strict post-mutation backstop).
- **`IdentityTable.collisions()` does NOT exclude `deprecated=True` owners** (`identity_table.py:54-80`: `owners()` filters `participation_mode is OWNER` only). So a real markdown owner (`deprecated=False`) plus a transitional `aggregate`/`datapackage` owner (`deprecated=True`) of the **same** `(project_name, canonical_id)` collide under `collisions()`. Per design §C4 ("migrate/promote transitional owners by their phase, **never blindly renumber/collide them**; carry as-is until §B5 retirement"), the migrator gate must NOT hard-block such a collision — it blocks only when **≥2 non-deprecated** owner rows share the key, and surfaces a transitional-involved collision as a non-blocking warning. This deprecation-aware filter lives in the **migrator gate**, computed from `table.collisions()` + each `collision.rows[*].deprecated`; `audit_identity_table`/`collisions()` themselves are unchanged (other consumers — validate/health — may legitimately surface transitional shadows as findings).
- **A `BORROWER` row never participates in `collisions()`** (`owners()` filters to `OWNER`). A borrower's `owner_scope` is the *borrowed* scope (e.g. `commons`), not `project_name`, so "owner + borrower with the same `(owner_scope, canonical_id)`" is not even disk-producible; the property is tested directly on a constructed `IdentityTable`/declaration set (see Task 1), not via a disk fixture.
- **`audit_project_sources(sources)`** (`migrate.py:164-217`): builds `identity_table = build_identity_table(sources)` (`:167`); on `AliasCollisionError` emits one `ambiguous_alias` fail (`:172-185`) and **falls through**; else audits entities/relations/bindings refs (`:189-195`) and emits `warn` rows for `skipped_entities` (`:200-210`); **always** `rows.extend(audit_identity_table(identity_table))` (`:213`) → an `identity_collision` fail row per `(owner_scope, canonical_id)` owned by >1 owner row. Returns `(rows, has_failures)`. So once the post-move model loads non-strict, `identity_collision` rows appear here with **no change to `audit_project_sources`**.
- **`audit_identity_table` row shape** (`migrate.py:146-161`): `{"check":"identity_collision","status":"fail","source":<canonical_id>,"field":"owner_scope","target":<owner_scope>,"details":"owned by <pathA> and <pathB>"}`.
- **`classify_owner_scope(adapter, *, project_name)`** (`identity_table.py:83-101`): `markdown` → `(project_name, False)`; `aggregate`/`datapackage` → `(project_name, True)` (transitional); `commons-merged` → `("commons", False)`. **THIS-PROJECT `owner_scope` is the project's configured `name`** (defaults to dir name) — NOT a fixed literal; tests must read it from the project, not assume `"project"`. A commons **overlay** of an id is a `borrower` row (`participation_mode=BORROWER`, `sources.py:518`), which `IdentityTable.owners()`/`collisions()` **exclude** — so a borrower never collides with an owner.
- **`IdentityTable.collisions()`** (`identity_table.py:74-80`): owner-rows-only, keyed on `(owner_scope, canonical_id)`, fires when >1 owner row shares the pair. Cross-scope owners (same id, different scope) are NOT collisions.
- **Existing tests that pin current behavior** (`tests/test_entity_layout_migration.py`): `test_schema_invalid_nonundated_core_entity_blocks_pre_mutation` (`:479`), `test_purely_undated_entity_has_no_spurious_structural_failure` (`:499`), `test_dangling_structural_related_ref_blocks_pre_mutation` (`:1064`), `test_colliding_entity_aliases_block_without_aborting_dry_run` (`:1306`), `test_mappings_yaml_dangling_alias_target_blocks` (`:1217`), `test_migrate_collision_blocks_apply` (`:391`), `test_migrate_dry_run_makes_no_changes` (`:316`). **Read each before changing behavior**; T1 must keep them green (adapting only the *mechanism* a test asserts when the plan explicitly changes it — e.g. duplicate-ownership now surfaces as `identity_collision`).
- **Helper idioms** in the test file: project scaffolds write `science.yaml`, legacy entities under `doc/`/`specs/`, and call `migrate_layout(project_root, apply=False/True)` reading `report["unresolved_references"]` / `report["collisions"]` / raised `ValueError`. The commons-overlay fixtures live in `tests/test_graph_commons_sources.py` / `tests/test_substrate_two_scope_e2e.py` (`_build_commons`, `SCIENCE_COMMONS_ROOT`) — reuse that idiom for the borrower-not-a-collision test.
- **New names are free** (grep): `_postmove_audit_failures`, `_schema_invalid_blockers`, `_identity_collision_rows`, and the report key `transitional_owner_collisions`. No existing references except the single gate call site at `:955` and the definition at `:760`.

---

## Task 1: Non-strict post-move compile + deprecation-aware `identity_collision` gate; retire the date-mask

Make the pre-mutation gate compile the post-move model **non-strict** so `collisions()` fires and the undated sentinel no longer crashes the load; remove the date-mask; re-surface non-undated **malformed-core** entities (`core_schema_validation_failed`) as blockers via a small explicit triage; and compute **deprecation-aware** identity-collision blockers (block iff ≥2 non-deprecated owners share a key; carry a transitional-involved collision as a non-blocking, report-surfaced warning, per §C4).

**Files:**
- Modify: `src/science_tool/entity_layout_migration.py`
- Test: `tests/test_entity_layout_migration.py`

- [ ] **Step 1: Write the failing tests**

First **read**: (1) `class SkippedEntity` (grep under `src/science_tool/`) to confirm `.path`/`.reason`/`.details` field names; (2) `class IdentityDeclaration` + `class IdentityTable` + `class IdentityCollision` (`graph/identity_table.py:19-80`) and `class SourceRef` so you can construct rows directly; (3) `test_schema_invalid_nonundated_core_entity_blocks_pre_mutation` (`:479`) and `test_purely_undated_entity_has_no_spurious_structural_failure` (`:499`) for the project-scaffold idiom; (4) the `AggregateAdapter` / an existing aggregate fixture for the `entities.yaml` shape (needed for the transitional-shadow test).

The collision **semantics** (two real owners block; transitional/​borrower don't) are *properties of the compiled model*, so they are tested directly on a constructed `IdentityTable` via the new `_identity_collision_rows` helper — these are deterministic and don't fight the planner (which deliberately avoids minting duplicate ids). Append:

```python
def _decl(cid, mode, scope="demo", *, adapter="markdown", deprecated=False):
    from science_model.source_ref import SourceRef
    from science_tool.graph.identity_table import IdentityDeclaration, ParticipationMode
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=mode,
        owner_scope=scope,
        adapter=adapter,
        source_ref=SourceRef(adapter_name=adapter, path=f"{adapter}/{cid}.md"),
        deprecated=deprecated,
    )


def test_identity_collision_rows_blocks_two_real_owners() -> None:
    from science_tool.entity_layout_migration import _identity_collision_rows
    from science_tool.graph.identity_table import IdentityTable, ParticipationMode

    table = IdentityTable(rows=[
        _decl("hypothesis:0001", ParticipationMode.OWNER, adapter="markdown"),
        _decl("hypothesis:0001", ParticipationMode.OWNER, adapter="markdown"),
    ])
    blockers, warnings = _identity_collision_rows(table)
    assert [r["check"] for r in blockers] == ["identity_collision"]
    assert blockers[0]["status"] == "fail" and blockers[0]["source"] == "hypothesis:0001"
    assert warnings == []


def test_identity_collision_rows_carries_transitional_shadow_as_warning() -> None:
    # A real markdown owner shadowed by an entities.yaml aggregate STUB of the same id
    # (deprecated=True) is the common pre-v3 debt: §C4 carries it as-is until §B5
    # retirement, so it must NOT block — it is surfaced as a non-blocking warning.
    from science_tool.entity_layout_migration import _identity_collision_rows
    from science_tool.graph.identity_table import IdentityTable, ParticipationMode

    table = IdentityTable(rows=[
        _decl("hypothesis:0001", ParticipationMode.OWNER, adapter="markdown"),
        _decl("hypothesis:0001", ParticipationMode.OWNER, adapter="aggregate", deprecated=True),
    ])
    blockers, warnings = _identity_collision_rows(table)
    assert blockers == []
    assert [r["check"] for r in warnings] == ["identity_collision"]
    assert warnings[0]["status"] == "warn"


def test_identity_collision_rows_ignores_borrower() -> None:
    # A BORROWER row never participates in collisions() (owners() filters to OWNER),
    # so an owner + a borrower of the same id is not a collision — the §B3 "41 phantom
    # collisions" fix. (Disk cannot even produce owner+borrower at the SAME owner_scope:
    # a borrower's scope is the borrowed scope; this constructs the property directly.)
    from science_tool.entity_layout_migration import _identity_collision_rows
    from science_tool.graph.identity_table import IdentityTable, ParticipationMode

    table = IdentityTable(rows=[
        _decl("topic:scfm", ParticipationMode.OWNER, scope="demo", adapter="markdown"),
        _decl("topic:scfm", ParticipationMode.BORROWER, scope="commons", adapter="overlay"),
    ])
    blockers, warnings = _identity_collision_rows(table)
    assert blockers == [] and warnings == []
```

> Confirm the exact `ParticipationMode` import path and member names (`OWNER`/`BORROWER`) and `SourceRef`'s constructor kwargs by reading the modules; adapt `_decl` if a field name differs. The `scope="demo"` default should match the test project's configured `name` only where it matters (the two-real-owners and transitional tests need the SAME scope on both rows so they share a key — `"demo"` on both is sufficient since `collisions()` keys on `(owner_scope, canonical_id)` regardless of the literal).

Also add ONE integration test that the deprecation-aware gate behavior reaches `migrate_layout` end-to-end (transitional shadow does not block apply and is surfaced in the report):

```python
def test_aggregate_stub_shadowing_markdown_owner_does_not_block_apply(tmp_path: Path) -> None:
    # End-to-end: a project with a real owner AND an entities.yaml aggregate stub of
    # the same id migrates without the gate hard-blocking; the shadow is reported under
    # transitional_owner_collisions (surfaced, not silently dropped).
    project_root = _make_project(tmp_path)            # use the file's scaffold helper
    _seed_markdown_owner_and_aggregate_stub(project_root, "hypothesis:0001")  # SEE NOTE
    report = migrate_layout(project_root, apply=False)
    assert any("hypothesis:0001" in str(c) for c in report["transitional_owner_collisions"])
    # The shadow alone must not block --apply (other guards may still apply; assert the
    # collision is not the blocker by checking it is absent from unresolved_references).
    assert all(
        "hypothesis:0001" not in t
        for targets in report["unresolved_references"].values()
        for t in targets
    )
```

> `_seed_markdown_owner_and_aggregate_stub` is the one fixture you must build from the real `AggregateAdapter` `entities.yaml` shape (read it first). It needs: a real markdown owner of `hypothesis:0001` that the post-move compile sees (either a pre-existing `entities/hypotheses/0001-*.md`, or a legacy `doc/`/`specs/` file the planner migrates and KEEPS at `hypothesis:0001`), PLUS an `entities.yaml` aggregate entry under `knowledge/sources/<profile>/` declaring the SAME id (→ a `deprecated=True` aggregate owner row).
>
> **Keep this integration test if at all practical — it is load-bearing.** The three `_identity_collision_rows` unit tests pin the helper's SEMANTICS in isolation, but ONLY this end-to-end test proves the tuple return is unpacked correctly at the `:955` gate call site AND that `report["transitional_owner_collisions"]` is actually wired into `migrate_layout`'s report dict (a unit test on the helper cannot catch a gate that forgets to thread the second tuple element into the report). Budget real effort on the `entities.yaml` fixture before considering any fallback. ONLY if the aggregate `entities.yaml` shape proves genuinely impractical to fixture after a real attempt may this test be dropped IN FAVOUR OF the unit tests — and if so you MUST add a substitute that still exercises the wiring: assert `migrate_layout` returns a report containing the `transitional_owner_collisions` key (even when empty) so the report-dict plumbing is still covered. Note any such substitution explicitly; do NOT weaken it to a tautology or silently omit the wiring assertion.

- [ ] **Step 2: Run to verify the new tests fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py -q -k "identity_collision_rows or aggregate_stub_shadowing"`
Expected: the three `_identity_collision_rows` tests FAIL to import (`ImportError`/`AttributeError`: `_identity_collision_rows` does not exist yet); the `aggregate_stub_shadowing` integration test fails on `report["transitional_owner_collisions"]` (`KeyError` — the report key does not exist yet). That is the red signal driving Step 3.

- [ ] **Step 3: Implement the non-strict compile + date-mask removal + deprecation-aware collision gate + schema triage**

In `entity_layout_migration.py`:

(a) Delete the module constant `_SIM_PLACEHOLDER_DATE` (`:757`).

(b) Add the deprecation-aware collision helper (it mirrors `migrate.audit_identity_table` but splits on `deprecated`, which the flat audit row does not carry — this is the migrator-local §C4 rule). Place it above the gate function. Use a `TYPE_CHECKING` import for `IdentityTable` (the file already has `from __future__ import annotations`, so the annotation need not be importable at runtime — but add it to the existing `if TYPE_CHECKING:` block alongside `ProjectSources` for clarity):

```python
def _identity_collision_rows(table: "IdentityTable") -> tuple[list[dict], list[dict]]:
    """Split identity-table collisions into hard blockers vs transitional carries (§B3/§C4).

    A collision is a HARD blocker only when >= 2 NON-deprecated owner rows share the
    (owner_scope, canonical_id) key — a genuine duplicate of a real owner. A collision
    that involves a transitional owner (deprecated=True, e.g. an entities.yaml aggregate
    STUB shadowing a real markdown owner) is NOT blocked: §C4 carries transitional owners
    as-is until §B5 retirement. Such a collision is returned as a non-blocking warning so
    the shadow debt is surfaced (never silently dropped), not as an apply blocker.

    Note: IdentityTable.collisions()/owners() already excludes BORROWER + external rows,
    so a borrower of an id never appears here (the §B3 "41 phantom collisions" fix).
    """
    blockers: list[dict] = []
    warnings: list[dict] = []
    for collision in table.collisions():
        paths = [(r.source_ref.path if r.source_ref else "<unknown>") for r in collision.rows]
        real_owners = sum(1 for r in collision.rows if not r.deprecated)
        row = {
            "check": "identity_collision",
            "status": "fail" if real_owners >= 2 else "warn",
            "source": collision.canonical_id,
            "field": "owner_scope",
            "target": collision.owner_scope,
            "details": "owned by " + " and ".join(paths),
        }
        (blockers if real_owners >= 2 else warnings).append(row)
    return blockers, warnings
```

(c) Replace the body of `_simulated_postmove_audit_failures` (`:786-819`) so it (1) drops the date-mask, (2) loads non-strict, (3) computes deprecation-aware collision blockers from the compiled `IdentityTable` while EXCLUDING `audit_project_sources`' own (deprecation-blind) `identity_collision` fails, (4) adds the schema triage, and (5) returns a `(blockers, transitional_warnings)` tuple. Change the return annotation to `-> tuple[list[dict], list[dict]]` and keep the early-exception `schema_load_failure` catch-all (returning `([...], [])`):

```python
    from science_tool.graph.identity_table import build_identity_table
    from science_tool.graph.migrate import audit_project_sources
    from science_tool.graph.sources import load_project_sources

    merged = {**rewritten, **singleton_text, **inplace_text}
    overrides = {rel: text for rel, text in merged.items() if rel.endswith(".md")}
    try:
        # Compile the post-move model through the canonical loader (moved entities as
        # virtual files at their new paths). Non-strict so a duplicate (owner_scope,
        # canonical_id) records BOTH owner rows for IdentityTable.collisions() to
        # report (deprecation-aware, below) instead of raising
        # EntityIdentityCollisionError, and so the 9999-99-99 undated sentinel no
        # longer crashes the load (no date-mask needed — undated entities are blocked
        # by their own guard; malformed-core failures are re-surfaced below).
        sources = load_project_sources(
            project_root, overrides, strict_core_schema=False, strict_identity=False
        )
    except Exception as exc:
        return (
            [
                {
                    "check": "schema_load_failure",
                    "status": "fail",
                    "source": "(project sources)",
                    "field": "frontmatter",
                    "target": str(exc),
                    "details": str(exc),
                }
            ],
            [],
        )
    mappings_aliases = dict(sources.manual_aliases)
    sources = sources.model_copy(update={"manual_aliases": {**sources.manual_aliases, **plan.id_map}})
    rows, failed = audit_project_sources(sources)
    # Drop the audit's deprecation-blind identity_collision fails; we recompute them
    # deprecation-aware below (a transitional shadow must not hard-block, design §C4).
    audit_fails = (
        [r for r in rows if r.get("status") == "fail" and r.get("check") != "identity_collision"]
        if failed
        else []
    )
    collision_blockers, transitional_warnings = _identity_collision_rows(build_identity_table(sources))
    blockers = (
        audit_fails
        + collision_blockers
        + _schema_invalid_blockers(sources, undated_new_paths)
        + _dangling_alias_targets(sources, mappings_aliases)
    )
    return blockers, transitional_warnings
```

(d) Add `_schema_invalid_blockers` immediately above the gate (verify `SkippedEntity` field/reason names first — adapt if they differ). **Triage on `core_schema_validation_failed`** (the malformed-core reason under non-strict load), NOT `entity_schema_validation_failed` (which is the missing-identity / profile-kind reason — already strict-skipped, not a malformed-core block):

```python
def _schema_invalid_blockers(sources: "ProjectSources", undated_new_paths: set[str]) -> list[dict]:
    """Re-surface malformed-core entities as pre-mutation blockers (strict-parity).

    Under the non-strict post-move compile, a core-kind entity whose schema validation
    fails is recorded as a SkippedEntity(reason="core_schema_validation_failed") instead
    of crashing the load — so we must re-flag it to keep parity with the strict
    post-mutation backstop. EXCEPT undated entities: they carry the 9999-99-99 sentinel
    (which also fails the date schema) but are blocked by the dedicated undated guard, so
    re-flagging them here would be a spurious double-block. (The missing-identity reason
    "entity_schema_validation_failed" is deliberately NOT triaged here — it is skipped
    even under strict load and is not a malformed-core failure.)
    """
    fails: list[dict] = []
    for skipped in sources.skipped_entities:
        if skipped.reason != "core_schema_validation_failed":
            continue
        if skipped.path in undated_new_paths:
            continue
        fails.append(
            {
                "check": "schema_load_failure",
                "status": "fail",
                "source": skipped.path,
                "field": "frontmatter",
                "target": skipped.reason,
                "details": skipped.details,
            }
        )
    return fails
```

> `undated_new_paths` is a set of **new** rel-paths (`{d["new_rel_path"] for d in undated_entities}`, passed at `:961`). Confirm `SkippedEntity.path` is the same rel-path form the override keys use; if it differs (absolute vs rel, or new vs old path), normalize before the membership test so the undated exclusion actually matches. If `SkippedEntity` lacks a `details` attribute, use the available equivalent (read the class).

(e) Update the gate's call site in `migrate_layout` (`:955`) to unpack the tuple and surface the transitional warnings in the report. Replace:

```python
    structural_failures = _simulated_postmove_audit_failures(
        project_root,
        plan,
        rewritten,
        singleton_text,
        inplace_text,
        {d["new_rel_path"] for d in undated_entities},
    )
```

with:

```python
    structural_failures, transitional_owner_collisions = _simulated_postmove_audit_failures(
        project_root,
        plan,
        rewritten,
        singleton_text,
        inplace_text,
        {d["new_rel_path"] for d in undated_entities},
    )
```

and add `"transitional_owner_collisions": transitional_owner_collisions,` to the `report` dict (`:964-975`). Leave the apply guards unchanged: `if structural_failures: raise ...` (`:983`) still fires on hard blockers only — transitional collisions are in the separate, non-blocking report channel.

- [ ] **Step 4: Run the new tests + the pinned behavior tests**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py -q -k "identity_collision_rows or aggregate_stub_shadowing or schema_invalid_nonundated or purely_undated"`
Expected: PASS — two real owners → blocker (fail); transitional shadow → warning (not blocker), surfaced under `report["transitional_owner_collisions"]`, apply not blocked by it; borrower → neither; non-undated malformed-core still blocks (now via `_schema_invalid_blockers` on `core_schema_validation_failed`); purely-undated still has no spurious structural failure (the sentinel no longer crashes the non-strict load; the undated entity is skipped, excluded from blockers, and a purely-undated entity has no inbound refs to fail).

- [ ] **Step 5: Run the full migrator suite (catch behavior drift)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py tests/test_migrate_local_kinds_integration.py -q`
Expected: all PASS. If `test_colliding_entity_aliases_block_without_aborting_dry_run` (`:1306`) or `test_mappings_yaml_dangling_alias_target_blocks` (`:1217`) fail, the alias path regressed — `_dangling_alias_targets` and the `ambiguous_alias` branch of `audit_project_sources` must still fire; investigate before proceeding (do NOT weaken the tests). If a previously-`schema_load_failure` assertion now sees `identity_collision`, update that ONE assertion to the new (cleaner) mechanism — that is the intended change — and note it.

- [ ] **Step 6: ruff + commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/entity_layout_migration.py tests/test_entity_layout_migration.py && uv run --frozen ruff format --check src/science_tool/entity_layout_migration.py tests/test_entity_layout_migration.py` (fix with `ruff format` on those files if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "feat(substrate): migrator gate reads compiled model (deprecation-aware identity_collision; retire date-mask)"
```
Do NOT add any "Co-Authored-By" trailer.

---

## Task 2: Retire the simulation/proxy framing — rename + docstrings + alias-check still works

The behavior is now compiled-model-driven; this task removes the residual "simulation"/proxy *framing* (rename + docstrings) and proves that retiring the proxy did NOT retire the legitimate `ambiguous_alias` check (a genuine alias clash still blocks). The proxy's old false-negative (a same-scope duplicate with no alias clash) is already covered by Task 1's `test_identity_collision_rows_blocks_two_real_owners`; no separate gate-level duplicate test is needed (the planner deliberately won't mint duplicate ids, so a duplicate is only cleanly constructible at the compiled-model layer, which Task 1 does).

**Files:**
- Modify: `src/science_tool/entity_layout_migration.py`
- Test: `tests/test_entity_layout_migration.py`

- [ ] **Step 1: Write the decisive test**

```python
def test_genuine_alias_clash_still_reports_ambiguous_alias(tmp_path: Path) -> None:
    # Retiring the duplicate-ownership PROXY must not retire the legitimate
    # ambiguous_alias check: two DIFFERENT ids sharing one alias still blocks via
    # ambiguous_alias (emitted by audit_project_sources, surfaced as a gate blocker).
    project_root = _make_project(tmp_path)
    _seed_conflicting_aliases(project_root)  # two entities, same alias -> different ids
    blockers, _transitional = _postmove_audit_failures_for(project_root)
    assert any(r["check"] == "ambiguous_alias" for r in blockers)
```

> Add a thin private test helper `_postmove_audit_failures_for(project_root) -> tuple[list[dict], list[dict]]` in the test module that mirrors the orchestrator's pre-gate setup (build `plan = plan_migration(project_root)` and the `rewritten`/`singleton_text`/`inplace_text` dicts as `migrate_layout` does at `:884-951`, then call the renamed `_postmove_audit_failures(...)` and return its `(blockers, transitional)` tuple). `_seed_conflicting_aliases` writes two real entities (e.g. via the file's existing scaffold helpers) that register the SAME alias string for DIFFERENT canonical ids — read `mappings.yaml`/`aliases:` handling (`build_alias_map`, `sources.py:554`) for the loadable shape. The test references the new name `_postmove_audit_failures`, so it cannot import until the Step-3 rename lands (that is its red signal). Do NOT weaken to a tautology.

- [ ] **Step 2: Run to verify (red)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py -q -k "genuine_alias_clash"`
Expected: FAILS to import/collect — `_postmove_audit_failures` does not exist yet (it is still `_simulated_postmove_audit_failures` until Step 3). That `ImportError` is the red signal driving the rename.

- [ ] **Step 3: Rename + refresh docstrings (no behavior change)**

In `entity_layout_migration.py`:
- Rename `_simulated_postmove_audit_failures` → `_postmove_audit_failures` (definition `:760` and the call site in `migrate_layout` `:955`). The Task-1 tuple return + report wiring stay as-is.
- Replace the function docstring with one that describes the compiled-model read (no "simulated"/"mask" language): e.g. *"Graph-audit-equivalent validation over the COMPILED post-move model (design §C4). Compiles the post-move ProjectSources via the canonical loader (moved entities as virtual files) and returns (blockers, transitional_owner_collisions): blockers are pre-mutation fail rows — deprecation-aware identity_collision (two real owners), reference, ambiguous_alias, malformed-core schema, and dangling-alias-target; transitional_owner_collisions are non-blocking warnings for transitional-owner shadows carried per §C4 until §B5 retirement. No simulate-and-mask."*
- In `_dangling_alias_targets` (`:822-862`), update the docstring/comment that frames the `AliasCollisionError`→`[]` branch as the collision signal: clarify that duplicate **ownership** is now reported as a deprecation-aware `identity_collision` by `_identity_collision_rows`, and this helper only validates that real `mappings.yaml` alias **targets** resolve (its legitimate, retained role). Do NOT change its logic.
- Confirm (grep) no `_SIM_PLACEHOLDER_DATE` / `_simulated_postmove_audit_failures` references remain anywhere under `src/` or `tests/`.

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_entity_layout_migration.py tests/test_migrate_local_kinds_integration.py -q`
Expected: all PASS, including the new alias-clash test.

- [ ] **Step 5: ruff + commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/entity_layout_migration.py tests/test_entity_layout_migration.py && uv run --frozen ruff format --check src/science_tool/entity_layout_migration.py tests/test_entity_layout_migration.py` (fix if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "refactor(substrate): retire simulation-mask/proxy framing in migrator gate (compiled-model read)"
```
No "Co-Authored-By" trailer.

---

## Task 3: Full-suite green + ruff

**Files:** none (verification only).

- [ ] **Step 1: Full test suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: all PASS (baseline before this plan: 4659 passed, 6 skipped, 4 deselected; this plan adds tests and changes only the migrator dry-run gate). If a non-migrator test fails, the non-strict post-move compile or the rename leaked beyond the gate — investigate; the only intended production change is `entity_layout_migration.py`'s pre-mutation gate. Do NOT weaken tests to pass.

- [ ] **Step 2: Lint/format (changed files)**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/entity_layout_migration.py tests/test_entity_layout_migration.py && uv run --frozen ruff format --check src/science_tool/entity_layout_migration.py tests/test_entity_layout_migration.py`
Expected: clean. (Do NOT repo-wide reformat; the repo carries pre-existing ruff debt elsewhere.)

- [ ] **Step 3: Commit any lint fixes** (only if Step 2 required changes)

```bash
cd ~/d/science && git add science/src/science_tool/entity_layout_migration.py science/tests/test_entity_layout_migration.py
git commit -m "chore(substrate): ruff clean for migrator compiled-model gate"
```

---

## Self-Review

**1. Spec coverage (§B3/§C2/§C4, this plan's scope):**
- "collision = two owner rows same `(owner_scope, canonical_id)` → blocks apply" → Task 1 loads the post-move model non-strict and computes deprecation-aware blockers via `_identity_collision_rows` (block iff ≥2 non-deprecated owners); `test_identity_collision_rows_blocks_two_real_owners`. ✓
- "a commons owner + a project borrower of the same id are different rows, never a collision" → `collisions()`/`owners()` exclude borrowers; `test_identity_collision_rows_ignores_borrower` (constructed directly — owner+borrower at the SAME `(owner_scope, canonical_id)` is not disk-producible since a borrower's scope is the borrowed scope). ✓ (the "41 phantom collisions" fix reaching the migrator)
- "renumber/operate only on **real** this-project owners; migrate/promote transitional owners by phase, NEVER blindly collide/renumber them; carry as-is until §B5 retirement" → `_identity_collision_rows` blocks ONLY on ≥2 non-deprecated owners; a real-owner + transitional-aggregate-stub collision is carried as a non-blocking warning surfaced in `report["transitional_owner_collisions"]`; `test_identity_collision_rows_carries_transitional_shadow_as_warning` + `test_aggregate_stub_shadowing_markdown_owner_does_not_block_apply`. This is the corrected behavior: `IdentityTable.collisions()` itself does NOT exclude `deprecated=True`, so the deprecation filter lives in the migrator gate. ✓
- "the simulation-mask hack is no longer needed" → Task 1 removes `_SIM_PLACEHOLDER_DATE` + the date substitution; the non-strict load + `_schema_invalid_blockers` (on `core_schema_validation_failed`) preserve "undated blocks via own guard" and "non-undated malformed-core blocks". Task 2 removes the residual naming/docstring framing. ✓
- "the alias-collision proxy is no longer needed" → duplicate ownership is signalled by the deprecation-aware `identity_collision`, not `ambiguous_alias`; the gate excludes `audit_project_sources`' own deprecation-blind `identity_collision` fails from the passthrough; `ambiguous_alias` reverts to genuine alias clashes only (`test_genuine_alias_clash_still_reports_ambiguous_alias`). ✓
- §C2 "every consumer reads the compiled model" → the gate's validation is a pure read of the compiled `ProjectSources` (`audit_project_sources` references + `build_identity_table().collisions()` for ownership); no bespoke disk-format awareness in the validation. ✓ (the one retained compile uses the canonical loader, per the Interpretation section)
- "pure function of the compiled model + id-map" — honest scope: a single canonical post-move **compile** remains because moved entities aren't in the pre-move model (Interpretation section); the reload-free in-memory transform is deferred to 1.4c with a stated correctness-risk rationale. ✓ (flagged for reviewer/user sanction at handoff)

**2. Placeholder scan:** No TBD/TODO. Code steps show complete code for `_identity_collision_rows`, the gate rewrite, and `_schema_invalid_blockers`. The collision **semantics** are pinned by three deterministic unit tests on constructed `IdentityTable`s (no planner fight). Test steps that depend on file-specific scaffold helpers (`_make_project`, the aggregate-stub fixture, `_seed_conflicting_aliases`, `_decl`) are flagged inline with explicit "read the real shape / adapt" instructions; the one integration test (`aggregate_stub_shadowing…`) is explicitly droppable in favour of the unit tests if the `entities.yaml` aggregate fixture proves impractical — never weakened to a tautology. ✓

**3. Type/name consistency:** `_postmove_audit_failures` (renamed in T2) returns `tuple[list[dict], list[dict]]` (blockers, transitional warnings); its single call site at `migrate_layout:955` unpacks both and surfaces the second under `report["transitional_owner_collisions"]` (T1 wires this; T2 only renames, so T2's test `ImportError` on the new name is the intended red). `_identity_collision_rows(table) -> tuple[list[dict], list[dict]]` and `_schema_invalid_blockers(sources, undated_new_paths) -> list[dict]` — each defined once, called once in the gate. `_SIM_PLACEHOLDER_DATE` removed; `_UNDATED_SENTINEL` kept. Triage reason is `core_schema_validation_failed` (the malformed-core reason under non-strict), NOT `entity_schema_validation_failed` (missing-identity / profile-kind) — verified against `sources.py:342/366/381`. `SkippedEntity` field names (`path`/`reason`/`details`), `ParticipationMode` members, and `SourceRef` kwargs are flagged to verify-before-use. ✓

**4. Blast radius:** Non-zero, confined to the migrator's dry-run pre-mutation gate. A genuine duplicate (two real owners) now blocks via a clean `identity_collision` (was opaque `schema_load_failure`/crash); commons-borrower phantom collisions disappear; **a transitional aggregate-stub shadow no longer hard-blocks** (it is carried + surfaced) — important so the migrator does not refuse the common pre-v3 `entities.yaml`-stub case it is meant to migrate past; undated + non-undated malformed-core still block. The strict post-mutation backstop (`:1013`) and every non-migrator consumer are untouched (`audit_identity_table`/`collisions()` unchanged; the deprecation filter is migrator-local). MM30's `report:lead-validation` debt (Task #30) will now surface, if it is a true two-real-owner duplicate, as a clean `identity_collision`; if it is a transitional shadow, as a non-blocking `transitional_owner_collisions` warning — the intended legible §C4 outcomes. ✓

---

## Where this sits (Phase 1 roadmap — NOT part of this plan)

Phase 1.1 (`e2b3a757`) compiled `IdentityTable`; 1.2 (`8a87e5b7`) the owner-root overlay guard; 1.3 (`02e3527b`) the scope-aware resolver + dormant `ambiguous_reference`; 1.4a (`1cfd9ca1`) scope-aware loading + resolver activation. **This is Phase 1.4b**: the migrator's pre-mutation gate on the compiled model — first-class `identity_collision`, retired mask + proxy. Remaining:

- **1.4c (optional purity refinement):** replace the single canonical post-move **compile** with a reload-free in-memory transform (parse synthesized override texts → `Entity` objects, splice into the pre-move model, remap references) — deferred here for correctness-risk reasons on a load-bearing migrator (Interpretation section). Only worth doing if a measured need (perf, or a true "no second compile" requirement) appears.
- **1.5 — Orphan datapackages + dataset `doc/datasets/` dual-SSOT (§B4):** synthesize deprecated transitional owners for datapackage-only datasets.
- **Phases 2–4:** dataset reconciliation, `entities.yaml` retirement (§B5; promotes the transitional `aggregate` owners that 1.4b's gate now carries as `transitional_owner_collisions` warnings — once retired, those shadows disappear), external-reference resolver / `t068` federated scoped refs.

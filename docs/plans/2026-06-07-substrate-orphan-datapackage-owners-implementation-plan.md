# Orphan Datapackage Owners (Substrate Phase 1.5) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the compiler implement the design §B4 dataset dual-SSOT invariant: a `datapackage.yaml` is **attached resource metadata, not a second owner** — it synthesizes a *deprecated, transitional* owner row **only when its id has no existing same-scope owner at all** (a **true orphan**); when *any* owner of the same id was already recorded — a real markdown owner **or** a transitional `entities.yaml` aggregate stub — the datapackage **defers** to it (no competing owner row, no collision). Add a conformance check that flags every synthesized/orphan datapackage owner (WARN during the v2→v3 transition, ERROR at `layout_version >= 3`) so orphans are surfaced for the §B4 Phase-2 migration.

**Architecture:** Today the unified adapter loop in `load_project_sources` (`graph/sources.py:283-404`) emits an `IdentityDeclaration` for **every** entity any adapter discovers, *before* its `canonical_id`-keyed dedup gate (`:397-402`). `classify_owner_scope("datapackage", …)` already tags datapackage owners `deprecated=True` (`identity_table.py:99-100`), but the loop never asks whether the datapackage's id *already has an owner* — so a markdown `dataset:x` owner (or an `entities.yaml` aggregate `dataset:x` stub) **plus** a `datapackage.yaml` of the same id appends two owner declarations and the second trips `EntityIdentityCollisionError` under strict (the dual-SSOT collision §B4 resolves). Phase 1.5 inserts a small **deferral** at the datapackage owner: when the loop's `identity_table` already holds the datapackage's `canonical_id` (i.e. an earlier adapter recorded an owner entity for it — markdown and aggregate both precede `DatapackageAdapter` in the adapter list), the datapackage emits **no** declaration and **no** duplicate entity — the existing owner wins cleanly and nothing collides. The deferral targets *any* existing same-scope owner, real **or** transitional: a datapackage shadowed by an aggregate stub defers to that stub and the §B5 aggregate-retirement path (Phase 3) carries the debt — so no strict-load path crashes. Only a **truly orphan** datapackage (no prior owner of its id) keeps synthesizing the deprecated transitional owner, so datapackage-only datasets keep loading. A new conformance check reads the **compiled model** (`load_project_sources` → `identity_declarations`, §C2) and flags each remaining datapackage owner declaration as a synthesized/orphan owner. (Reusing the loop's existing `identity_table` membership needs **no** new accumulator — it already records every recorded same-scope owner.)

**Tech Stack:** Python 3, pytest. Library at `~/d/science/science/` (`src/science_tool/`, `tests/`). Run tests with `cd ~/d/science/science && uv run --frozen pytest`. ruff 120-char.

## Interpretation of "Orphan-aware synthesis + flag" (the chosen scope)

The user chose **Orphan-aware synthesis + conformance flag** over the visibility-only alternative. So this plan **changes load-bearing loader dedup behavior** (a non-orphan datapackage now defers instead of colliding) — that is intended and is the §B4 dual-SSOT resolution. **Explicitly OUT of scope (design Phase 2, later sub-plans):**

- **Promotion** of orphan datapackages to real `entities/datasets/<id>.md` owner files (the actual migration).
- **Flip-to-error**: the orphan flag stays at WARN (ERROR only auto-promotes at `layout_version >= 3` via the standard gate); the deliberate "synthesize + warn → error" cutover is Phase 2.
- **Resource-metadata → PROV/resource triples**: a deferred datapackage's `resources` are not attached to the markdown owner's graph node here (the loader already strips non-entity datapackage fields today — `datapackage.py:96` — so there is no regression). Attaching resource metadata is Phase 2.
- **The "forbid a second declaration" conformance check** (Phase 2): with deferral in place there is no second *owner* declaration to forbid; the authoring-time guard that a datapackage must not *also* carry full entity metadata when a markdown owner exists is Phase 2.
- **Aggregate (`entities.yaml`) transitional owners** keep their own behavior unchanged: deferral is gated to `DatapackageAdapter` only (an aggregate stub still emits its deprecated owner row). What changes is that a datapackage **defers to** an existing aggregate stub of the same id (rather than colliding with it under strict), so an `entities.yaml` dataset stub + same-id `datapackage.yaml` no longer crashes the strict build/materialize path. The aggregate stub remains the (transitional) owner and is retired by §B5 (Phase 3), which then makes the datapackage a true orphan. (Note: 1.4b's `transitional_owner_collisions` warning channel only fires in the migrator's **non-strict** compiled-model gate — it does NOT protect normal strict build/materialize loads, which is exactly why this deferral, not that channel, is the correct fix here.)
- **Cross-scope (commons) datapackages**: deferral is scoped to **this-project** real owners recorded in the main loop (commons owners are a different `owner_scope` and a different key — never a collision). A datapackage whose id is owned only by commons is treated as orphan here (it has no this-project owner); the commons-borrow refinement is later.

**Design source:** `~/d/science/docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md` — §B4 ("the entity file is the identity declaration; the datapackage is attached resource metadata, not a second declaration … a datapackage with no owner is an error in target state; during rollout the compiler synthesizes a deprecated, transitional owner row for an orphan datapackage … Conformance flags every synthesized/deprecated owner; Phase 2 flips synthesize+warn to error"), §C2 ("every consumer reads the compiled model"), §C3 (`DatapackageAdapter` = attachment, never a declaration; zero-owner handling per §B4).

**Blast radius (non-zero, intended):** a project that has BOTH a markdown `dataset:x` owner and a `data/x/datapackage.yaml` of the same id previously **raised** `EntityIdentityCollisionError` on every strict load (build, materialize, conformance); it now loads cleanly with the markdown owner winning and the datapackage deferred. An orphan datapackage (no markdown owner) loads exactly as before (a deprecated `DatasetEntity` owner) but is now **surfaced** by a WARN conformance finding. Genuine duplicate **real** owners (two markdown owners of one id) still raise under strict (coverage preserved). No other adapter's behavior changes.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/science_tool/graph/sources.py` | (T1) Insert a §B4 **deferral** at the owner-declaration point in the unified adapter loop — a `DatapackageAdapter` entity whose `canonical_id` is already present in the loop's `identity_table` (any earlier recorded same-scope owner, real markdown **or** transitional aggregate) emits no declaration and no duplicate entity (`continue`). Only a true orphan (id absent from `identity_table`) synthesizes the deprecated owner. No new accumulator. | **Modify** |
| `tests/test_load_project_sources_unified.py` | (T1) New: orphan datapackage → one deprecated `datapackage` owner declaration + a loaded `DatasetEntity`; markdown owner + datapackage same id → markdown wins, datapackage deferred, no raise, `collisions() == []`; **aggregate `entities.yaml` dataset stub + same-id datapackage → aggregate owns, datapackage deferred, no strict crash, `collisions() == []`**. Repoint the existing cross-adapter-collision test to two **markdown** owners (preserve strict-collision coverage). | **Modify** |
| `src/science_tool/validate/checks/orphan_datapackage_owner.py` | (T2) New conformance check `check_orphan_datapackage_owner`: read the compiled model (`load_project_sources`, non-strict, `include_commons=False`); for each `IdentityDeclaration` with `adapter == "datapackage"` (these are orphans post-T1), yield WARN (ERROR at `layout_version >= 3`) citing the datapackage path. | **Create** |
| `src/science_tool/validate/checks/__init__.py` | (T2) Register `orphan_datapackage_owner` in `CANONICAL_CHECK_MODULES`. | **Modify** |
| `tests/validate/test_checks_orphan_datapackage_owner.py` | (T2) New: orphan datapackage → one WARN; non-orphan (deferred) datapackage → no finding; `layout_version: 3` → ERROR. | **Create** |

### Reference facts (verified against `main` @ `4db8042a`)

- **Unified adapter loop** `load_project_sources` (`graph/sources.py:283-404`). Adapter order (`:242-266`): `MarkdownAdapter` (scans `["entities","research/packages","doc/datasets","doc/workflows","doc/workflow-runs"]`), then `AggregateAdapter`, then **`DatapackageAdapter`**, then workflow/task/code. **Both markdown and aggregate precede datapackage**, so any markdown or aggregate owner of an id is recorded before the same-id datapackage is processed. Accumulators declared at `:270-275` (`identity_table: dict[str, SourceRef]`, `identity_declarations: list[IdentityDeclaration]`, `entities`, `entity_source_adapters`, `skipped_entities`). The local `identity_table` dict (`:270`, populated at `:402`) holds the `canonical_id`→`SourceRef` of every owner entity that passed the dedup gate this load — i.e. exactly "which same-scope owners have already been recorded." The deferral reuses it directly; no separate `real_owner_ids` set is needed.
- **The aggregate `entities.yaml` stub shape** (`AggregateAdapter` discovers `knowledge/sources/<local_profile>/entities.yaml`): a list under `entities:` of mappings carrying `canonical_id` + `kind` (+ kind-specific required fields). For a **dataset** entry to actually become a recorded owner (not a skipped schema-invalid entity), it must validate as a `DatasetEntity` — include the dataset-required fields (`title`, `origin`, `access: {level, verified}`). If the entry is schema-invalid it is recorded as a `SkippedEntity` and is NOT in `identity_table`, so the datapackage would not defer to it (it would instead synthesize as a true orphan — also non-crashing, but a different path). The aggregate-defer test MUST use a VALID dataset aggregate entry so it exercises the defer-to-recorded-aggregate-owner path (the one that previously strict-crashed).
- **Per-ref body** (`:285-404`): after `entity = schema.model_validate(raw)` (`:328`), computes `owner_scope, deprecated = classify_owner_scope(adapter.name, project_name=project_name)` (`:386`), then **always** appends an `IdentityDeclaration(participation_mode=OWNER, owner_scope, adapter=adapter.name, source_ref=ref, deprecated=deprecated)` (`:387-396`), then the dedup gate: `existing = identity_table.get(entity.canonical_id)` (`:397`); if `existing is not None`: `raise EntityIdentityCollisionError(...)` under `strict_identity` else `continue` (`:398-401`); else records `identity_table[id]=ref`, appends the entity, sets `entity_source_adapters[id]=adapter.name` (`:402-404`). **The declaration is appended BEFORE the dedup check** — that is why a markdown+datapackage pair yields two owner rows / a strict raise today.
- **`classify_owner_scope(adapter, *, project_name)`** (`identity_table.py:86-101`): `commons-merged`→`("commons", False)`; `("aggregate","datapackage")`→`(project_name, True)` (transitional/deprecated); else `(project_name, False)`. **Unchanged by this plan** — datapackage owners stay `deprecated=True`; this plan only decides *whether to emit* the datapackage owner at all.
- **`DatapackageAdapter`** (`graph/storage_adapters/datapackage.py`): `name = "datapackage"`; `discover` scans `data/` + `results/` for `datapackage.yaml` carrying profile `science-pkg-entity-1.0`, fail-fast on missing `id`/`type`/`title` (`EntityDatapackageInvalidError`); `load_raw` extracts only `_ENTITY_FIELDS` (strips `resources` — `:96`). Already imported and instantiated in `sources.py:258`, so `isinstance(adapter, DatapackageAdapter)` needs no new import (confirm the import line exists near the top of `sources.py`; it must, since `:258` constructs it).
- **`EntityIdentityCollisionError`** is raised at `sources.py:400` under `strict_identity=True`. The migrator's 1.4b non-strict gate (`strict_identity=False`) does not raise here; it carries duplicate owner rows for `IdentityTable.collisions()`. After this plan, a deferred (non-orphan) datapackage produces **no** second owner row, so it does not even reach `collisions()` — clean under both strict and non-strict.
- **`build_identity_table(sources)`** (`identity_table.py`) builds the compiled `IdentityTable` from `sources.identity_declarations`; `.collisions()` reports `(owner_scope, canonical_id)` keys with >1 OWNER row. Used in tests to assert "no collision".
- **Existing test to repoint**: `test_global_identity_collision_across_adapters` (`tests/test_load_project_sources_unified.py:190-215`) writes `entities/datasets/x.md` (markdown owner `dataset:x`) + `data/x/datapackage.yaml` (`dataset:x`) and asserts `pytest.raises(EntityIdentityCollisionError, match="dataset:x")`. **This scenario now DEFERS (no raise)** — repoint per Task 1. `test_load_produces_dataset_entity_for_datapackage` (`:167-188`) is the orphan case (datapackage only) and must stay green. The `_seed(tmp_path)` helper writes the project scaffold (`science.yaml` etc.) — reuse it.
- **Conformance check infra**: `@Check(section=…, order=N)` decorator (`validate/checks/__init__.py`); modules listed in `CANONICAL_CHECK_MODULES` (`validate/checks/__init__.py:25+`) are imported to register their checks. A check is `def check_x(ctx: ValidateContext) -> Iterator[Result]` yielding `Result(severity, path|None, line|None, message, code, extra|None)`. **Precedent for reading the compiled model in a check**: `validate/checks/code_files.py:183` does `sources = load_project_sources(ctx.project_root, include_commons=False)`. **Severity gate** (`entity_conformance.py:135-137`): `Severity.ERROR if isinstance(ctx.manifest.get("layout_version"), int) and version >= 3 else Severity.WARN` — replicate this tiny gate locally (it is module-private).
- **Check-test idiom** (`tests/validate/test_checks_dataset_promotion_contract.py:13-30`): write a `science.yaml` manifest string carrying `name`, `layout_version`, `knowledge_profiles: {local: knowledge/local}`; build `ValidateContext.from_project_root(root, strict=False, verbose=False)`; call the check fn and collect `list(check_x(ctx))`; assert on `Result.severity` / `.message`. Reuse this idiom.
- **New names are free** (grep): `check_orphan_datapackage_owner`, module `orphan_datapackage_owner`, Result code `"orphan-datapackage-owner"`. (No new accumulator in `sources.py` — the deferral reuses the existing `identity_table`.)

---

## Task 1: Loader — orphan-aware datapackage owner synthesis (defer to a real owner)

Insert the §B4 deferral so a datapackage owner is emitted **only** for an orphan id; a datapackage whose id already has a real (non-deprecated) owner defers (no declaration, no duplicate entity, no collision).

**Files:**
- Modify: `src/science_tool/graph/sources.py`
- Test: `tests/test_load_project_sources_unified.py`

- [ ] **Step 1: Write the failing tests**

First **read**: `tests/test_load_project_sources_unified.py` `_seed` helper + `test_load_produces_dataset_entity_for_datapackage` (`:167`) and `test_global_identity_collision_across_adapters` (`:190`) for the fixture idiom; and `graph/identity_table.py` `build_identity_table` / `IdentityTable.collisions()` for the no-collision assertion. Confirm `DatasetEntity`, `load_project_sources`, `build_identity_table` import paths used in the file.

Append/modify in `tests/test_load_project_sources_unified.py`:

```python
def test_orphan_datapackage_synthesizes_deprecated_owner(tmp_path: Path) -> None:
    # An orphan datapackage (no markdown owner of the same id) keeps loading as a
    # deprecated, transitional owner (design §B4 rollout) so datapackage-only
    # datasets are not dropped before migration.
    _seed(tmp_path)
    (tmp_path / "data" / "ds1").mkdir(parents=True)
    (tmp_path / "data" / "ds1" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "ds1",
                "id": "dataset:ds1",
                "type": "dataset",
                "title": "DS1",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)
    ds = next(e for e in sources.entities if e.canonical_id == "dataset:ds1")
    assert isinstance(ds, DatasetEntity)
    owners = [d for d in sources.identity_declarations if d.canonical_id == "dataset:ds1"]
    assert len(owners) == 1
    assert owners[0].adapter == "datapackage"
    assert owners[0].deprecated is True


def test_datapackage_defers_to_markdown_owner(tmp_path: Path) -> None:
    # §B4: a datapackage is attached resource metadata, NOT a second owner. With a
    # real markdown owner of the same id, the datapackage DEFERS — markdown wins,
    # no competing owner row, no collision (this scenario used to raise).
    _seed(tmp_path)
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    (tmp_path / "data" / "x").mkdir(parents=True)
    (tmp_path / "data" / "x" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "x",
                "id": "dataset:x",
                "type": "dataset",
                "title": "X dp",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)  # must NOT raise
    ds = next(e for e in sources.entities if e.canonical_id == "dataset:x")
    assert ds.title == "X md"  # the markdown owner won
    owners = [d for d in sources.identity_declarations if d.canonical_id == "dataset:x"]
    assert len(owners) == 1
    assert owners[0].adapter == "markdown" and owners[0].deprecated is False
    assert build_identity_table(sources).collisions() == []


def test_datapackage_defers_to_aggregate_stub_owner(tmp_path: Path) -> None:
    # §B4: a datapackage defers to ANY existing same-scope owner, including a
    # transitional entities.yaml aggregate stub. This previously strict-crashed
    # (EntityIdentityCollisionError); now the aggregate stub remains the (deprecated)
    # owner, the datapackage defers, nothing collides, and §B5 retires the stub later.
    _seed(tmp_path)
    # A VALID dataset aggregate entry (must validate as DatasetEntity so it is
    # RECORDED as an owner — origin + access are dataset-required; add any other
    # required fields if model_validate rejects this).
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True, exist_ok=True)
    (tmp_path / "knowledge" / "sources" / "local" / "entities.yaml").write_text(
        "entities:\n"
        '  - canonical_id: "dataset:x"\n'
        '    kind: "dataset"\n'
        '    title: "X agg"\n'
        '    origin: "external"\n'
        "    access:\n"
        '      level: "public"\n'
        "      verified: false\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "x").mkdir(parents=True)
    (tmp_path / "data" / "x" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "x",
                "id": "dataset:x",
                "type": "dataset",
                "title": "X dp",
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )
    sources = load_project_sources(tmp_path)  # must NOT raise (was a strict crash)
    owners = [d for d in sources.identity_declarations if d.canonical_id == "dataset:x"]
    assert len(owners) == 1
    assert owners[0].adapter == "aggregate" and owners[0].deprecated is True  # stub owns; dp deferred
    assert build_identity_table(sources).collisions() == []
```

> The aggregate entry MUST validate as a `DatasetEntity` (so it is recorded in `identity_table` and the datapackage actually defers to it — the path that previously crashed). If `model_validate` rejects the minimal entry, read `DatasetEntity` and add the missing required field(s); confirm by asserting `owners[0].adapter == "aggregate"` (a skipped-invalid stub would instead leave the datapackage as a synthesized owner, `adapter == "datapackage"`, which is the WRONG path for this test). Confirm `local_profile` resolves to `local` for the `_seed` scaffold (the entities.yaml lives under `knowledge/sources/<local_profile>/`); if `_seed` uses a different profile dir, write the stub there.

And **repoint** the existing `test_global_identity_collision_across_adapters` so it still covers the strict-collision path using two **markdown** owners (a genuine duplicate of two real owners), since the markdown+datapackage scenario no longer collides. Replace its body so it writes two `entities/datasets/*.md` files with the same `id: "dataset:x"` (different filenames, e.g. `x.md` and `x2.md`) and asserts `pytest.raises(EntityIdentityCollisionError, match="dataset:x")`. Rename it to `test_global_identity_collision_two_markdown_owners` for accuracy (update any reference; grep shows it is only defined here).

> Confirm `build_identity_table` is importable in this test module (add the import if missing: `from science_tool.graph.identity_table import build_identity_table`). Confirm `DatasetEntity` carries a `.title` attribute (it does — the datapackage fixture sets `title`); if the attribute name differs, assert on whichever field distinguishes the markdown record ("X md") from the datapackage record ("X dp").

- [ ] **Step 2: Run to verify the new tests fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_load_project_sources_unified.py -q -k "orphan_datapackage or defers_to_markdown or defers_to_aggregate or two_markdown_owners"`
Expected: `test_datapackage_defers_to_markdown_owner` and `test_datapackage_defers_to_aggregate_stub_owner` FAIL (both currently raise `EntityIdentityCollisionError` instead of deferring); `test_orphan_datapackage_synthesizes_deprecated_owner` PASSES already (orphan path is unchanged) — that is fine, it pins the orphan behavior the change must preserve; `test_global_identity_collision_two_markdown_owners` PASSES (two real owners still raise). The decisive reds are the two defer tests.

- [ ] **Step 3: Implement the deferral in the loader**

In `src/science_tool/graph/sources.py`, insert the §B4 deferral immediately after `owner_scope, deprecated = classify_owner_scope(...)` (`:386`) and **before** the `identity_declarations.append(...)` (`:387`):

```python
                owner_scope, deprecated = classify_owner_scope(adapter.name, project_name=project_name)
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
                    continue
                identity_declarations.append(
                    IdentityDeclaration(
                        canonical_id=entity.canonical_id,
                        participation_mode=ParticipationMode.OWNER,
                        owner_scope=owner_scope,
                        adapter=adapter.name,
                        source_ref=ref,
                        deprecated=deprecated,
                    )
                )
```

The deferral reuses the loop's existing `identity_table` dict (populated at `:402` for every owner entity that passed dedup), so it targets **any** already-recorded same-scope owner — real markdown or transitional aggregate. `MarkdownAdapter` and `AggregateAdapter` both precede `DatapackageAdapter` in the adapter list, so the owner is in `identity_table` before its datapackage is processed. No new accumulator is added.

> Verify `DatapackageAdapter` is already imported at the top of `sources.py` (it is constructed at `:258`). Do not add a duplicate import. Leave the dedup gate (`:397-402`) and `EntityIdentityCollisionError` raise unchanged — genuine duplicate **real** owners (two markdown declarations of one id) must still raise under strict; only `DatapackageAdapter` defers. (A second datapackage of an already-owned id also defers — acceptable: a datapackage is an attachment, not an identity declaration, so this is not a silent drop of a declaration; the surviving owner is still flagged for migration by Task 2.)

- [ ] **Step 4: Run the new + orphan tests**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_load_project_sources_unified.py -q`
Expected: all PASS — both defer tests now defer (no raise, the existing owner wins, `collisions() == []`): markdown-defer keeps the markdown owner, aggregate-defer keeps the aggregate stub owner; orphan test still loads the deprecated datapackage owner; two-markdown-owners test still raises; `test_load_produces_dataset_entity_for_datapackage` (orphan) still green.

- [ ] **Step 5: Run loader/identity/migrator suites (catch drift)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_load_project_sources_unified.py tests/test_graph_identity_table.py tests/test_entity_layout_migration.py tests/test_datasets.py tests/test_storage_adapters/test_datapackage.py -q`
Expected: all PASS. If a test asserted a markdown+datapackage collision elsewhere, repoint it to the defer behavior (intended change) and note it; do NOT weaken any test. `DatapackageAdapter` unit tests are unaffected (discovery/validation logic is untouched).

- [ ] **Step 6: ruff + commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/sources.py tests/test_load_project_sources_unified.py && uv run --frozen ruff format --check src/science_tool/graph/sources.py tests/test_load_project_sources_unified.py` (fix with `ruff format` on those files if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/graph/sources.py science/tests/test_load_project_sources_unified.py
git commit -m "feat(substrate): datapackage owners defer to real owners (§B4 orphan-aware synthesis)"
```
Do NOT add any "Co-Authored-By" trailer.

---

## Task 2: Conformance check — flag synthesized/orphan datapackage owners

Surface every remaining datapackage owner declaration (an orphan, post-Task-1) as a conformance finding so it is migrated to a real owner file. WARN during the v2→v3 transition; ERROR at `layout_version >= 3` via the standard gate. Reads the compiled model (§C2), not raw disk.

**Files:**
- Create: `src/science_tool/validate/checks/orphan_datapackage_owner.py`
- Modify: `src/science_tool/validate/checks/__init__.py`
- Test: `tests/validate/test_checks_orphan_datapackage_owner.py`

- [ ] **Step 1: Write the failing tests**

First **read**: `tests/validate/test_checks_dataset_promotion_contract.py:13-30` (the `_MANIFEST` string + `_ctx` helper) and `validate/checks/code_files.py:180-190` (the `load_project_sources` in-check idiom + how it yields `Result`s). Create `tests/validate/test_checks_orphan_datapackage_owner.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate.checks.orphan_datapackage_owner import check_orphan_datapackage_owner
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = (
    "name: demo-project\n"
    "created: 2026-01-01\n"
    "last_modified: 2026-01-02\n"
    "status: active\n"
    "summary: Demo project\n"
    "profile: research\n"
    "layout_version: {version}\n"
    "knowledge_profiles:\n"
    "  local: knowledge/local\n"
)


def _ctx(root: Path, *, version: int = 1) -> ValidateContext:
    (root / "science.yaml").write_text(_MANIFEST.format(version=version), encoding="utf-8")
    (root / "knowledge" / "local").mkdir(parents=True, exist_ok=True)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_datapackage(root: Path, slug: str, ident: str) -> None:
    pkg = root / "data" / slug
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": slug,
                "id": ident,
                "type": "dataset",
                "title": ident,
                "origin": "external",
                "access": {"level": "public", "verified": False},
            }
        ),
        encoding="utf-8",
    )


def test_orphan_datapackage_owner_flagged_warn(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_datapackage(tmp_path, "ds1", "dataset:ds1")
    results = list(check_orphan_datapackage_owner(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert "dataset:ds1" in results[0].message


def test_non_orphan_datapackage_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    # A real markdown owner of the same id -> the datapackage DEFERS (Task 1), so no
    # datapackage owner declaration remains -> nothing to flag.
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X md"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    _write_datapackage(tmp_path, "x", "dataset:x")
    assert list(check_orphan_datapackage_owner(ctx)) == []


def test_orphan_datapackage_owner_errors_at_v3(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, version=3)
    _write_datapackage(tmp_path, "ds1", "dataset:ds1")
    results = list(check_orphan_datapackage_owner(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.ERROR
```

> Confirm `ValidateContext.from_project_root` accepts the manifest as written (it requires `science.yaml` with a `name`; `knowledge_profiles.local` is needed so `load_project_sources` resolves the local profile — mirror exactly what `test_checks_dataset_promotion_contract._ctx` and an existing `load_project_sources` test scaffold provide; if `from_project_root` or `load_project_sources` needs additional manifest keys, copy them from a passing fixture rather than guessing). Confirm `Result.severity` is the attribute name (per `validate/result.py`).

- [ ] **Step 2: Run to verify the new tests fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_orphan_datapackage_owner.py -q`
Expected: collection/import FAILS — `check_orphan_datapackage_owner` does not exist yet (`ModuleNotFoundError`). That is the red signal.

- [ ] **Step 3: Implement the check**

Create `src/science_tool/validate/checks/orphan_datapackage_owner.py`:

```python
"""Conformance check: synthesized/orphan datapackage owners (design §B4).

A datapackage is attached resource metadata, not an identity declaration. After
the loader's orphan-aware synthesis (§B4), a datapackage that has a real owner of
the same id DEFERS to it and emits no owner declaration — so any datapackage
owner declaration that remains in the compiled model is an ORPHAN (a
datapackage-only dataset with no entity-file owner). Surface each one for
migration to a real entities/datasets/<id>.md owner. WARN during the v2->v3
transition; ERROR at layout_version >= 3 (the deliberate synthesize+warn -> error
cutover is Phase 2).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _severity(ctx: ValidateContext) -> Severity:
    # Mirrors validate/checks/entity_conformance._severity (module-private there).
    version = ctx.manifest.get("layout_version")
    return Severity.ERROR if isinstance(version, int) and version >= 3 else Severity.WARN


@Check(section="orphan datapackage owner (no entity-file owner)...", order=49)
def check_orphan_datapackage_owner(ctx: ValidateContext) -> Iterator[Result]:
    # Non-strict + no commons: a diagnostic must not abort on unrelated strictness
    # failures, and commons owners are a different scope (never this-project orphans).
    sources = load_project_sources(
        ctx.project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    for decl in sources.identity_declarations:
        if decl.adapter != "datapackage":
            continue
        path = Path(decl.source_ref.path) if decl.source_ref else None
        yield Result(
            _severity(ctx),
            path,
            None,
            f"{decl.canonical_id}: datapackage has no entity-file owner "
            "(orphan datapackage; synthesized transitional owner — migrate to "
            "entities/datasets/<id>.md per design §B4)",
            "orphan-datapackage-owner",
            None,
        )
```

> Verify: (1) `IdentityDeclaration` exposes `.adapter`, `.canonical_id`, `.source_ref` (it does — see `identity_table.py`); (2) the `@Check` decorator signature (`section`, `order`) — match `entity_conformance.py`'s usage exactly; (3) pick an `order` not already used — grep `order=` across `validate/checks/` and choose a free integer near the other dataset checks (the example uses `49`; change it if taken). (4) Confirm the `Result(...)` positional shape against `_result` in `entity_conformance.py:31-32` (`Result(severity, path, None, message, code, None)`).

Then register the module in `src/science_tool/validate/checks/__init__.py` — add `"orphan_datapackage_owner",` to the `CANONICAL_CHECK_MODULES` tuple (place it adjacent to the other `dataset_*` entries, e.g. right after `"dataset_promotion_contract",`).

- [ ] **Step 4: Run the new tests + check registration**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_orphan_datapackage_owner.py -q`
Expected: all PASS — orphan → one WARN citing `dataset:ds1`; non-orphan (deferred) → no finding; `layout_version: 3` → ERROR.

Also confirm the check is registered (imported via `CANONICAL_CHECK_MODULES`): `cd ~/d/science/science && uv run --frozen python -c "from science_tool.validate.checks import CANONICAL_CHECKS, CANONICAL_CHECK_MODULES; import science_tool.validate.checks as c; assert 'orphan_datapackage_owner' in CANONICAL_CHECK_MODULES"` (and that importing the package does not raise). If the registry is populated by importing each module, run whatever the existing test for `CANONICAL_CHECKS` does (grep `CANONICAL_CHECKS` in `tests/`) to confirm the new check loads.

- [ ] **Step 5: ruff + commit**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/validate/checks/orphan_datapackage_owner.py src/science_tool/validate/checks/__init__.py tests/validate/test_checks_orphan_datapackage_owner.py && uv run --frozen ruff format --check src/science_tool/validate/checks/orphan_datapackage_owner.py tests/validate/test_checks_orphan_datapackage_owner.py` (fix if needed). Then:

```bash
cd ~/d/science && git add science/src/science_tool/validate/checks/orphan_datapackage_owner.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_orphan_datapackage_owner.py
git commit -m "feat(substrate): conformance check flags orphan datapackage owners (§B4, WARN->ERROR at v3)"
```
No "Co-Authored-By" trailer.

---

## Task 3: Full-suite green + ruff

**Files:** none (verification only).

- [ ] **Step 1: Full test suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: all PASS (baseline before this plan: 4664 passed, 6 skipped, 4 deselected; this plan adds tests and changes the datapackage owner-emission path + adds one conformance check). If a non-loader/non-validate test fails, the deferral leaked beyond the intended path — investigate; the only intended production changes are `graph/sources.py` (datapackage deferral) and the new check + its registration. Do NOT weaken tests to pass.

- [ ] **Step 2: Lint/format (changed files)**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/sources.py src/science_tool/validate/checks/orphan_datapackage_owner.py src/science_tool/validate/checks/__init__.py tests/test_load_project_sources_unified.py tests/validate/test_checks_orphan_datapackage_owner.py && uv run --frozen ruff format --check src/science_tool/graph/sources.py src/science_tool/validate/checks/orphan_datapackage_owner.py tests/test_load_project_sources_unified.py tests/validate/test_checks_orphan_datapackage_owner.py`
Expected: clean. (Do NOT repo-wide reformat.)

- [ ] **Step 3: Commit any lint fixes** (only if Step 2 required changes)

```bash
cd ~/d/science && git add science/src/science_tool/graph/sources.py science/src/science_tool/validate/checks/ science/tests/test_load_project_sources_unified.py science/tests/validate/test_checks_orphan_datapackage_owner.py
git commit -m "chore(substrate): ruff clean for orphan-datapackage owners"
```

---

## Self-Review

**1. Spec coverage (§B4, this plan's scope):**
- "the entity file is the identity declaration; the datapackage is attached resource metadata, not a second declaration" → Task 1 makes a datapackage with an existing same-scope owner of the same id DEFER (no owner declaration, no duplicate entity) — whether that owner is a real markdown owner (`test_datapackage_defers_to_markdown_owner`) or a transitional aggregate stub (`test_datapackage_defers_to_aggregate_stub_owner`); both assert `collisions() == []` and no raise. ✓
- "during rollout, the compiler synthesizes a deprecated, transitional owner row for an orphan datapackage so datapackage-only datasets keep loading" → Task 1 keeps the deprecated owner only for TRUE orphans (id absent from `identity_table`); `test_orphan_datapackage_synthesizes_deprecated_owner` + the preserved `test_load_produces_dataset_entity_for_datapackage`. ✓
- "Conformance flags every synthesized/deprecated owner" → Task 2 `check_orphan_datapackage_owner` yields a finding per remaining datapackage owner declaration; `test_orphan_datapackage_owner_flagged_warn`; deferral means only true orphans carry a datapackage declaration, so only they are flagged (`test_non_orphan_datapackage_not_flagged`). An aggregate-shadowed datapackage is not flagged by THIS check (the aggregate stub is the debt, flagged/retired by §B5) — correct, no double-flagging. ✓
- "WARN during transition, Phase 2 flips synthesize+warn → error" → the check stays WARN, auto-promoting to ERROR only at `layout_version >= 3` via the standard gate; `test_orphan_datapackage_owner_errors_at_v3`. The deliberate flip-to-error + promotion-to-real-owner are explicitly deferred to Phase 2 (Interpretation section). ✓
- §C2 "every consumer reads the compiled model" → the check reads `load_project_sources(...).identity_declarations`, not raw disk (precedent `code_files.py:183`). ✓
- §C3 "DatapackageAdapter never a declaration; aggregate unchanged" → deferral is gated to `DatapackageAdapter`; `AggregateAdapter`'s own emission is untouched (it still produces its deprecated owner row). The datapackage now defers to that stub instead of strict-colliding with it, and §B5 retires the stub. Critically, this fixes a real strict-load crash that the 1.4b non-strict warning channel did NOT cover. ✓

**2. Placeholder scan:** No TBD/TODO. Complete code for the loader deferral, the new check, and all five tests. Fixture shapes are copied from the existing passing datapackage tests; manifest/`ValidateContext` keys are flagged "copy from a passing fixture rather than guess". ✓

**3. Type/name consistency:** The deferral checks `isinstance(adapter, DatapackageAdapter) and entity.canonical_id in identity_table` before the declaration append; no new accumulator; `classify_owner_scope`/`IdentityDeclaration`/dedup gate unchanged. The check `check_orphan_datapackage_owner` reads `decl.adapter == "datapackage"`, `decl.canonical_id`, `decl.source_ref.path`; `_severity` mirrors the `layout_version >= 3` gate; `Result(severity, path, None, message, "orphan-datapackage-owner", None)` matches `entity_conformance._result`'s positional shape. Module registered in `CANONICAL_CHECK_MODULES`. The repointed collision test now uses two markdown owners (preserving strict-collision coverage). ✓

**4. Blast radius:** Non-zero, intended and confined. Markdown+datapackage same id: was a strict `EntityIdentityCollisionError` on every load → now defers (markdown wins). **Aggregate `entities.yaml` dataset stub + same-id datapackage: was ALSO a strict crash (the gap the reviewer flagged) → now defers to the aggregate stub, no crash; §B5 carries the debt.** Orphan datapackage: unchanged load behavior, now WARN-surfaced. Genuine duplicate **real** (markdown) owners still raise. `AggregateAdapter`'s own emission, commons, and all non-dataset adapters unchanged. MM30 and any project carrying both a dataset owner (markdown or aggregate stub) and a same-id datapackage stop erroring on load and instead see a clean single owner; datapackage-only datasets get a WARN pointing at the §B4 migration. ✓

---

## Where this sits (Phase 1 roadmap — NOT part of this plan)

Phase 1.1 (`e2b3a757`) `IdentityTable`; 1.2 (`8a87e5b7`) owner-root overlay guard; 1.3 (`02e3527b`) scope-aware resolver; 1.4a (`1cfd9ca1`) scope-aware loading + activation; 1.4b (`4db8042a`) migrator on the compiled model. **This is Phase 1.5**: orphan-aware datapackage owner synthesis + the conformance flag (§B4 rollout half). With 1.5, design-Phase-1 ("compiler seam, supporting both transitional owner states — aggregate stubs and synthesized orphan datapackages — from day one") is complete. Remaining:

- **1.4c (optional purity):** reload-free in-memory migrator transform (deferred from 1.4b).
- **Phase 2 — Dataset reconciliation (§B4):** migrate orphan datapackages to real `entities/datasets/<id>.md` owners; flip the orphan flag from WARN to a hard error; attach datapackage resource metadata as PROV/resource triples; add the "forbid a second declaration" authoring guard.
- **Phase 3 — `entities.yaml` retirement (§B5):** concept/decision/latent triage; generate `core/decisions.md`; remove the `AggregateAdapter` deprecated-owner mode.
- **Phase 4:** external-reference resolver / `t068` federated scoped refs.

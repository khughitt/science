# Substrate Phase 2b — dataset reconciliation: identity hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the §B4 dataset-reconciliation identity hardening: flip the orphan-datapackage conformance check from "synthesize + warn" to an unconditional **error** (now that Phase 2a shipped `science data-package promote-orphans`), and add a standing, **deprecation-aware** conformance check that **forbids a second owner declaration** (the §B1 identity collision) — making it the single validate-surface for that diagnostic so it no longer surfaces inconsistently through the graph-audit path.

**Architecture:** Two additive, diagnostic conformance checks that read the **compiled model** (design §C2), never raw disk, plus a one-line routing change in the existing `check_graph`. Both checks load `load_project_sources(..., include_commons=False, strict_core_schema=False, strict_identity=False)` — non-strict so a diagnostic never aborts on the very condition it reports. Task 1 edits `orphan_datapackage_owner.py` (drop the layout-version severity gate). Task 2 adds `identity_collision.py`, built on the existing `build_identity_table()` / `IdentityTable.collisions()`, with a graded policy: **≥2 non-deprecated owners → ERROR** (the genuine §B1 duplicate), **otherwise → WARN** (a deprecated transitional owner — e.g. an `entities.yaml` aggregate stub, §C3 — shadowing a real owner: visible debt carried until §B5 retirement, not a hard error). Task 3 routes `identity_collision` rows out of `check_graph`'s display so the new check is the sole, deprecation-aware authority for that diagnostic in `science validate`.

**Tech Stack:** Python 3.13, `science_tool.validate` check framework (`@Check(section, order)` registry; `_load_canonical_checks` / `clear_checks_for_tests` for wiring tests), `science_tool.graph.identity_table` (`IdentityTable`, `IdentityCollision`, `IdentityDeclaration`, `ParticipationMode`, `build_identity_table`). Tests: `cd ~/d/science/science && uv run --frozen pytest`. Lint: `uv run --frozen ruff check . && uv run --frozen ruff format --check .` (120-char).

---

## Scope guard (what is OUT of Phase 2b)

Phase 2b is the **identity-hardening** slice of §B4 only. Explicitly deferred to a later **Phase 2c** plan:

- **Resource→PROV materialization.** Emitting the datapackage's general `resources` array / resource metadata as PROV/resource triples *about* the dataset entity (`materialize.py`). Today only geneset *members* materialize (the Phase 2a gate at `materialize.py:666`); the broader §B4 "the datapackage compiles into the graph as resource/`prov` triples about the dataset entity" statement is half-realized and stays so until 2c.

**Deliberately untouched (out of scope — do NOT change in 2b):**

- The loader's orphan **synthesis** behavior (`sources.py:392-405`). The loader MUST keep synthesizing the transitional owner so the project still loads and `promote-orphans` can read the orphan. Phase 2b flips only the **conformance severity**, never the loader.
- **`audit_identity_table` and `has_failures` semantics** (`migrate.py:146-161,216`). The graph audit reports every collision (including deprecated transitional shadows) as `status: "fail"`, which drives `materialization_audit`'s `has_failures` and therefore the **strict graph-build gate** (1.4a) and the migrator gate's recompute (1.4b). Three existing tests pin that `fail`/`has_failures` behavior (`test_graph_migrate_identity_audit.py`, `test_identity_audit_entrypoints.py`). Phase 2b does NOT re-grade that shared audit — it only stops `check_graph` from *displaying* the row (Task 3). Consequence, stated plainly: a transitional aggregate-stub shadow still contributes to `has_failures`, so a strict `science graph build` still treats it as a blocker — this is pre-existing 1.4b behavior, NOT a regression introduced here, and aligning the build gate with the carry-transitional intent (§C3/§C4) is a separate follow-up.
- The `AggregateAdapter` deprecated-owner mode / any `entities.yaml` retirement (§B5, Phase 3), and the federation / cross-scope resolver (§B3a/`t068`, Phase 4).

---

## File structure

| File | Responsibility | Task |
|---|---|---|
| `src/science_tool/validate/checks/orphan_datapackage_owner.py` (modify) | Orphan-datapackage check — flip to unconditional ERROR; message points at the promoter | 1 |
| `tests/validate/test_checks_orphan_datapackage_owner.py` (modify) | Lock unconditional-ERROR pre-v3 and at v3; assert promoter hint | 1 |
| `src/science_tool/validate/checks/identity_collision.py` (create) | New check: graded `(owner_scope, canonical_id)` collision — genuine→ERROR, transitional shadow→WARN (§B1/§B4/§C3); pure `graded_collisions()` helper | 2 |
| `src/science_tool/validate/checks/__init__.py` (modify) | Register `identity_collision` in `CANONICAL_CHECK_MODULES` | 2 |
| `tests/validate/test_checks_identity_collision.py` (create) | Unit-test the graded policy; disk-integration the happy/defer/clean paths; real canonical-loader wiring test | 2 |
| `src/science_tool/validate/checks/graph.py` (modify) | Route `identity_collision` rows out of `check_graph`'s display (new check owns the diagnostic) | 3 |
| `tests/validate/test_checks_graph.py` (modify) | Assert `check_graph` no longer emits an `identity_collision` row for a stub-shadow project | 3 |

---

## Task 1: Flip orphan-datapackage check to unconditional ERROR

**Context:** `orphan_datapackage_owner.py` (added in Phase 1.5) currently grades severity by layout version: `_severity()` returns `WARN` pre-v3 and `ERROR` at `layout_version >= 3`. The design's Phase-2 cutover ("flips the rule from 'synthesize + warn' to 'error'", §B4) is now safe because Phase 2a shipped `science data-package promote-orphans --apply`: an orphan is always actionable, so it is always an error. The loader still synthesizes the transitional owner (so the project loads and the promoter can read the orphan) — only this conformance severity flips.

**Files:**
- Modify: `src/science_tool/validate/checks/orphan_datapackage_owner.py`
- Test: `tests/validate/test_checks_orphan_datapackage_owner.py`

- [ ] **Step 1: Update the test to expect ERROR pre-v3 and assert the promoter hint**

In `tests/validate/test_checks_orphan_datapackage_owner.py`, replace:

```python
def test_orphan_datapackage_owner_flagged_warn(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_datapackage(tmp_path, "ds1", "dataset:ds1")
    results = list(check_orphan_datapackage_owner(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert "dataset:ds1" in results[0].message
```

with:

```python
def test_orphan_datapackage_owner_errors_pre_v3(tmp_path: Path) -> None:
    # Phase 2b cutover: an orphan is ALWAYS an error now that promotion tooling
    # exists (no longer WARN pre-v3). The loader still synthesizes a transitional
    # owner so the project loads; only this conformance severity flipped.
    ctx = _ctx(tmp_path)
    _write_datapackage(tmp_path, "ds1", "dataset:ds1")
    results = list(check_orphan_datapackage_owner(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.ERROR
    assert "dataset:ds1" in results[0].message
    assert "promote-orphans" in results[0].message
```

Leave `test_non_orphan_datapackage_not_flagged` and `test_orphan_datapackage_owner_errors_at_v3` as-is (both still pass).

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_orphan_datapackage_owner.py::test_orphan_datapackage_owner_errors_pre_v3 -v`
Expected: FAIL — current code returns `Severity.WARN` at version=1; `assert ... is Severity.ERROR` fails (and `promote-orphans` not yet in message).

- [ ] **Step 3: Flip the check to unconditional ERROR and repoint the message**

Rewrite `src/science_tool/validate/checks/orphan_datapackage_owner.py` in full:

```python
"""Conformance check: orphan datapackage owners (design §B4).

A datapackage is attached resource metadata, not an identity declaration. After
the loader's orphan-aware synthesis (§B4), a datapackage that has a real owner of
the same id DEFERS to it and emits no owner declaration — so any datapackage
owner declaration that remains in the compiled model is an ORPHAN (a
datapackage-only dataset with no entity-file owner).

Phase 2b cutover: promotion tooling now exists (`science data-package
promote-orphans --apply`, design §B4), so an orphan is always actionable and is
an ERROR regardless of layout_version. The loader still SYNTHESIZES a transitional
owner so the project keeps loading and the promoter can read the orphan; only this
conformance severity flips warn -> error.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


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
            Severity.ERROR,
            path,
            None,
            f"{decl.canonical_id}: datapackage has no entity-file owner "
            "(orphan datapackage); run `science data-package promote-orphans "
            "--apply` to create an entities/datasets/<id>.md owner (design §B4)",
            "orphan-datapackage-owner",
            None,
        )
```

This deletes the `_severity(ctx)` helper (no longer layout-gated). `ctx` is still used (`ctx.project_root`); `Severity` is still imported and used.

- [ ] **Step 4: Run the orphan check tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_orphan_datapackage_owner.py -v`
Expected: PASS — all three tests green.

- [ ] **Step 5: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/validate/checks/orphan_datapackage_owner.py tests/validate/test_checks_orphan_datapackage_owner.py && uv run --frozen ruff format --check src/science_tool/validate/checks/orphan_datapackage_owner.py tests/validate/test_checks_orphan_datapackage_owner.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/orphan_datapackage_owner.py science/tests/validate/test_checks_orphan_datapackage_owner.py
git commit -m "feat(substrate-2b): flip orphan-datapackage conformance to unconditional error

An orphan datapackage is always actionable now that Phase 2a shipped
\`science data-package promote-orphans\`, so the conformance check errors
regardless of layout_version (was WARN pre-v3). The loader still
synthesizes the transitional owner; only the conformance severity flips.
Design §B4 Phase-2 synthesize+warn -> error cutover."
```

---

## Task 2: Forbid-second-declaration conformance check (graded §B1 collision)

**Context:** The §B1 invariant names exactly one identity error: a **collision** — two owner declarations for the same canonical id in one address space, keyed `(owner_scope, canonical_id)`. Today this only surfaces in `science validate` buried in the graph-audit rows (via `materialization_audit` → `audit_identity_table`), with a deprecation-blind `fail`; there is no dedicated, first-class check. This task adds one and makes it the single validate-surface for the diagnostic (Task 3 routes the graph-audit copy away).

It reuses the existing compiled-model machinery: `build_identity_table(sources)` and `IdentityTable.collisions()` already group owner rows by key and return every key with >1 owner row. Two facts make this correct:

1. **Rows are collected pre-dedup.** `load_project_sources` appends each `IdentityDeclaration` *before* its `canonical_id` dedup gate (`sources.py:406` append, `:416` dedup), so under a **non-strict** load BOTH colliding owner rows survive in `sources.identity_declarations` even though the second `Entity` is skipped. The check must load non-strict (it also must, or it would crash on the very collision it reports).
2. **`collisions()` does not consider `deprecated`.** This check applies the policy: **≥2 non-deprecated owners → ERROR** (the genuine duplicate §B1 forbids); **otherwise → WARN** — a real markdown owner shadowed by a deprecated transitional owner (an `entities.yaml` aggregate stub, §C3) is rollout debt carried until §B5 retirement, surfaced (visible) but non-blocking. (A markdown owner + a sibling *datapackage* is NOT a collision at all: the datapackage DEFERS in Phase 1.5 and emits no owner row. An orphan datapackage synthesizes a single deprecated owner — one row, not a collision — handled by Task 1's orphan check.)

**Files:**
- Create: `src/science_tool/validate/checks/identity_collision.py`
- Modify: `src/science_tool/validate/checks/__init__.py`
- Test: `tests/validate/test_checks_identity_collision.py`

- [ ] **Step 1: Write the failing unit test for the graded policy**

Create `tests/validate/test_checks_identity_collision.py` with the pure-helper unit tests first:

```python
from __future__ import annotations

from pathlib import Path

import yaml

from science_model.source_ref import SourceRef
from science_tool.graph.identity_table import (
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
)
from science_tool.validate.checks.identity_collision import (
    check_forbidden_second_declaration,
    graded_collisions,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _owner(cid: str, *, path: str, deprecated: bool = False) -> IdentityDeclaration:
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=ParticipationMode.OWNER,
        owner_scope="demo-project",
        adapter="markdown",
        source_ref=SourceRef(adapter_name="markdown", path=path),
        deprecated=deprecated,
    )


def test_graded_two_real_owners_is_error() -> None:
    table = IdentityTable(
        rows=[
            _owner("dataset:x", path="entities/datasets/x.md"),
            _owner("dataset:x", path="entities/datasets/x-dup.md"),
        ]
    )
    graded = graded_collisions(table)
    assert len(graded) == 1
    severity, collision = graded[0]
    assert severity is Severity.ERROR
    assert collision.canonical_id == "dataset:x"
    assert {r.source_ref.path for r in collision.rows} == {
        "entities/datasets/x.md",
        "entities/datasets/x-dup.md",
    }


def test_graded_transitional_shadow_is_warn() -> None:
    # A real markdown owner shadowed by a deprecated aggregate/datapackage stub is a
    # rollout state carried until §B5/§B4 — visible (WARN) but NOT a hard error.
    table = IdentityTable(
        rows=[
            _owner("dataset:x", path="entities/datasets/x.md"),
            _owner("dataset:x", path="knowledge/sources/local/entities.yaml", deprecated=True),
        ]
    )
    graded = graded_collisions(table)
    assert len(graded) == 1
    assert graded[0][0] is Severity.WARN


def test_graded_single_owner_is_not_a_collision() -> None:
    table = IdentityTable(rows=[_owner("dataset:x", path="entities/datasets/x.md")])
    assert graded_collisions(table) == []


def test_graded_two_deprecated_owners_is_warn() -> None:
    table = IdentityTable(
        rows=[
            _owner("dataset:x", path="a", deprecated=True),
            _owner("dataset:x", path="b", deprecated=True),
        ]
    )
    graded = graded_collisions(table)
    assert len(graded) == 1
    assert graded[0][0] is Severity.WARN
```

- [ ] **Step 2: Run the unit tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_collision.py -v`
Expected: FAIL at import — `ModuleNotFoundError: science_tool.validate.checks.identity_collision`.

- [ ] **Step 3: Create the check module**

Create `src/science_tool/validate/checks/identity_collision.py`:

```python
"""Conformance check: forbidden second owner declaration (design §B1/§B4/§C3).

The one identity error the compiler must reject is a COLLISION: two owner
declarations for the same canonical id in one address space — the key
(owner_scope, canonical_id). A strict load raises EntityIdentityCollisionError
before this point; this diagnostic loads NON-STRICT so the collision surfaces as
a standing `science validate` result instead of an opaque load crash. Rows are
collected pre-dedup in load_project_sources, so both colliding owner rows survive
a non-strict load even though the second Entity is skipped.

This check is the SINGLE validate-surface for the collision diagnostic: the
graph-audit path (check_graph) routes its identity_collision rows here so the two
do not report the same condition with different policies.

Graded policy:
- >=2 NON-deprecated owners -> ERROR: the genuine duplicate §B1 forbids.
- otherwise -> WARN: a deprecated transitional owner (an entities.yaml aggregate
  stub, §C3) shadows a real owner — rollout debt carried until §B5 retirement.
  Visible so the debt is not lost, but non-blocking (the migration must not be
  bricked before its content migrates, §C4).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.graph.identity_table import (
    IdentityCollision,
    IdentityTable,
    build_identity_table,
)
from science_tool.graph.sources import load_project_sources
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def graded_collisions(table: IdentityTable) -> list[tuple[Severity, IdentityCollision]]:
    """Each (owner_scope, canonical_id) collision paired with its severity.

    ERROR when >=2 owner rows are non-deprecated (the genuine §B1 duplicate); WARN
    otherwise (a deprecated transitional owner shadows a real owner — §C3 rollout
    debt carried until §B5, visible but non-blocking).
    """
    graded: list[tuple[Severity, IdentityCollision]] = []
    for collision in table.collisions():
        non_deprecated = sum(1 for row in collision.rows if not row.deprecated)
        severity = Severity.ERROR if non_deprecated >= 2 else Severity.WARN
        graded.append((severity, collision))
    return graded


@Check(section="forbidden second owner declaration (identity collision)...", order=50)
def check_forbidden_second_declaration(ctx: ValidateContext) -> Iterator[Result]:
    # Non-strict + no commons, matching the orphan check: a diagnostic must not abort
    # on the collision it reports, and a commons owner + a local owner of the same id
    # are two DIFFERENT keys (different owner_scope), never a same-scope collision.
    sources = load_project_sources(
        ctx.project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    table = build_identity_table(sources)
    for severity, collision in graded_collisions(table):
        paths = sorted(row.source_ref.path for row in collision.rows if row.source_ref)
        first = Path(paths[0]) if paths else None
        joined = ", ".join(paths) if paths else "?"
        if severity is Severity.ERROR:
            detail = (
                "exactly one canonical owner per (owner_scope, canonical_id) is "
                "required (design §B1) — keep one owner declaration and remove the other."
            )
        else:
            detail = (
                "a deprecated transitional declaration shadows the owner (design "
                "§C3) — rollout debt carried until §B5 retirement; remove the stub "
                "to clear it."
            )
        yield Result(
            severity,
            first,
            None,
            f"{collision.canonical_id}: two owner declarations in scope "
            f"'{collision.owner_scope}' ({joined}); {detail}",
            "forbidden-second-declaration",
            None,
        )
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_collision.py -v`
Expected: PASS — the four `graded_collisions` unit tests are green.

- [ ] **Step 5: Register the check module**

In `src/science_tool/validate/checks/__init__.py`, add `"identity_collision"` to `CANONICAL_CHECK_MODULES` immediately after `"orphan_datapackage_owner"`:

```python
    "dataset_promotion_contract",
    "orphan_datapackage_owner",
    "identity_collision",
    "variant_identity",
```

- [ ] **Step 6: Add the disk-integration tests and a real canonical-loader wiring test**

Append to `tests/validate/test_checks_identity_collision.py`:

```python
_MANIFEST = (
    "name: demo-project\n"
    "created: 2026-01-01\n"
    "last_modified: 2026-01-02\n"
    "status: active\n"
    "summary: Demo project\n"
    "profile: research\n"
    "layout_version: 1\n"
    "knowledge_profiles:\n"
    "  local: knowledge/local\n"
)


def _ctx(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "knowledge" / "local").mkdir(parents=True, exist_ok=True)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_dataset_md(root: Path, filename: str, ident: str) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(
        f'---\nid: "{ident}"\ntype: "dataset"\ntitle: "{ident} {filename}"\n'
        'origin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )


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


def test_two_markdown_owners_flagged_error(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "x.md", "dataset:x")
    _write_dataset_md(tmp_path, "x-dup.md", "dataset:x")
    results = list(check_forbidden_second_declaration(ctx))
    assert len(results) == 1
    assert results[0].severity is Severity.ERROR
    assert "dataset:x" in results[0].message
    assert results[0].rule == "forbidden-second-declaration"


def test_markdown_owner_with_sibling_datapackage_not_flagged(tmp_path: Path) -> None:
    # The datapackage DEFERS to the markdown owner (Phase 1.5) -> one owner row ->
    # no collision.
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "x.md", "dataset:x")
    _write_datapackage(tmp_path, "x", "dataset:x")
    assert list(check_forbidden_second_declaration(ctx)) == []


def test_single_owner_not_flagged(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    _write_dataset_md(tmp_path, "x.md", "dataset:x")
    assert list(check_forbidden_second_declaration(ctx)) == []


def test_check_registered_via_canonical_loader() -> None:
    # A real wiring test (mirrors test_overlay_of_check_registered_via_canonical_loader):
    # clear the registry, drop the cached module so _load_canonical_checks() must
    # re-import it from CANONICAL_CHECK_MODULES, and assert the @Check ran. Importing
    # the check at module top would register it even if the module string were missing
    # from the tuple — this proves the tuple entry, not the import.
    import sys

    from science_tool.validate.checks import (
        CANONICAL_CHECKS,
        _load_canonical_checks,
        clear_checks_for_tests,
    )

    original_entries = list(CANONICAL_CHECKS)
    module_name = "science_tool.validate.checks.identity_collision"
    original_module = sys.modules.get(module_name)
    try:
        clear_checks_for_tests()
        sys.modules.pop(module_name, None)
        _load_canonical_checks()
        entries = [e for e in CANONICAL_CHECKS if e.fn.__name__ == "check_forbidden_second_declaration"]
        assert len(entries) == 1
        assert entries[0].order == 50
    finally:
        CANONICAL_CHECKS[:] = original_entries
        if original_module is None:
            sys.modules.pop(module_name, None)
```

Confirm `import yaml` is present at the top of the file (added in Step 1). `clear_checks_for_tests` / `_load_canonical_checks` / `CANONICAL_CHECKS` are exported from `science_tool.validate.checks` (used by `test_overlay_of_check_registered_via_canonical_loader`).

- [ ] **Step 7: Run the full identity-collision test file + register-aware lint**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_identity_collision.py -v && uv run --frozen ruff check src/science_tool/validate/checks/identity_collision.py src/science_tool/validate/checks/__init__.py tests/validate/test_checks_identity_collision.py && uv run --frozen ruff format --check src/science_tool/validate/checks/identity_collision.py tests/validate/test_checks_identity_collision.py`
Expected: PASS — unit + disk + wiring tests green; lint clean.

- [ ] **Step 8: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/identity_collision.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_identity_collision.py
git commit -m "feat(substrate-2b): add forbidden-second-declaration conformance check

Adds a standing, deprecation-aware \`science validate\` check for the §B1
identity collision (two owner declarations sharing one (owner_scope,
canonical_id)). Reads the compiled identity table (§C2), loads non-strict
so it does not abort on the collision it reports. Graded: >=2 non-deprecated
owners -> ERROR (genuine duplicate); a deprecated transitional shadow (§C3
aggregate stub) -> WARN, carried until §B5. Task 3 routes the graph-audit
copy here so this is the single validate-surface for the diagnostic."
```

---

## Task 3: Route the identity-collision diagnostic out of `check_graph`

**Context:** `check_graph` (`graph.py:174-188`) calls `materialization_audit()` and maps every audit row to a validate Result — `status == "fail"` → `Severity.ERROR`. `materialization_audit` → `audit_project_sources` → `audit_identity_table` (`migrate.py:213,146-161`) reports **every** `IdentityTable.collisions()` row as `status: "fail"`, deprecation-blind. So today a deprecated aggregate-stub shadow hard-fails `science validate` via this path — contradicting Task 2's graded policy (which WARNs it). Now that Task 2's dedicated check owns this diagnostic, `check_graph` must stop emitting `identity_collision` rows so the two paths do not report the same condition with different severities.

This is display-only: `materialization_audit` still **computes** the identity_collision rows, so `has_failures` (and therefore the strict graph-build gate, 1.4a) and the migrator's recompute (1.4b) are unchanged — see the Scope guard. We change only what `check_graph` *yields*.

**Files:**
- Modify: `src/science_tool/validate/checks/graph.py`
- Test: `tests/validate/test_checks_graph.py`

- [ ] **Step 1: Write the failing test**

In `tests/validate/test_checks_graph.py`, add a stub-shadow fixture helper and a test asserting `check_graph` yields no `identity_collision` row. Reuse the file's existing `_ctx` and `_messages` helpers:

```python
def _write_stub_shadow(root: Path) -> None:
    # A real markdown owner shadowed by a deprecated entities.yaml aggregate stub:
    # this is a collision in the compiled identity table. Pre-2b, check_graph emitted
    # it as a `graph audit: identity_collision ...` ERROR; 2b routes it to the
    # dedicated forbidden-second-declaration check instead.
    md = root / "entities" / "questions" / "q1.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text('---\nid: "question:q1"\ntype: "question"\ntitle: "q1"\n---\n', encoding="utf-8")
    local = root / "knowledge" / "sources" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "entities.yaml").write_text(
        "entities:\n  - canonical_id: question:q1\n    kind: question\n    title: q1\n"
        "    profile: local\n    source_path: knowledge/sources/local/entities.yaml\n",
        encoding="utf-8",
    )


def test_check_graph_does_not_emit_identity_collision(tmp_path: Path) -> None:
    from science_tool.validate.checks.graph import check_graph

    ctx = _ctx(tmp_path)
    _write_stub_shadow(tmp_path)
    messages = _messages(list(check_graph(ctx)))
    assert not any("identity_collision" in m for m in messages)
```

> Note for the implementer: confirm the import path for `check_graph` and `_ctx`/`_messages` matches what the rest of `test_checks_graph.py` already uses (it imports from `science_tool.validate`). If `check_graph` is imported at the top of the file already, drop the local import. The audit portion of `check_graph` runs without a `knowledge/graph.trig` (it returns early *after* the audit at `graph.py:190-192`), so no graph fixture is needed.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_graph.py::test_check_graph_does_not_emit_identity_collision -v`
Expected: FAIL — current `check_graph` emits `graph audit: identity_collision — question:q1 ...` as an ERROR row, so the assertion finds an `identity_collision` message.

- [ ] **Step 3: Route the row out of the display loop**

In `src/science_tool/validate/checks/graph.py`, inside `check_graph`'s audit-row loop (around line 182), add a `continue` for `identity_collision` rows. The loop becomes:

```python
        for row in audit_rows:
            if row["check"] == "identity_collision":
                # Owned by the dedicated forbidden-second-declaration conformance
                # check (deprecation-aware, design §B1/§B4). materialization_audit
                # still computes the row for has_failures (the build gate); we just
                # do not double-report it here with a contradictory severity.
                continue
            status = _status(row, context="graph audit", accepted={"fail", "warn"})
            severity = Severity.ERROR if status == "fail" else Severity.WARN
            yield _result(
                severity,
                f"graph audit: {row['check']} — {row['source']} {row['field']} -> {row['target']} ({row['details']})",
            )
```

Leave the `if not audit_rows:` INFO branch (line 179) unchanged — it keys off the unfiltered `audit_rows`, so a project whose only audit row is a routed `identity_collision` simply emits no graph-audit line (the dedicated check reports the collision). This is the minimal, lowest-risk diff.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/validate/test_checks_graph.py -v`
Expected: PASS — the new test is green and the existing `test_checks_graph.py` tests still pass (none assert an `identity_collision` emission; confirmed by grep).

- [ ] **Step 5: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/validate/checks/graph.py tests/validate/test_checks_graph.py && uv run --frozen ruff format --check src/science_tool/validate/checks/graph.py tests/validate/test_checks_graph.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/validate/checks/graph.py science/tests/validate/test_checks_graph.py
git commit -m "refactor(substrate-2b): route identity_collision out of check_graph display

The dedicated forbidden-second-declaration check now owns the identity
collision diagnostic with a deprecation-aware graded policy, so check_graph
stops emitting its deprecation-blind identity_collision ERROR rows (which
contradicted the new check on transitional stub shadows). Display-only:
materialization_audit still computes the rows for has_failures, so the
strict build gate and the migrator recompute are unchanged."
```

---

## Final verification (after all tasks)

- [ ] **Run the full suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: green (baseline ~4686 from Phase 2a, +~9 new tests). In particular the three pinning tests in `tests/test_graph_migrate_identity_audit.py` and `tests/test_identity_audit_entrypoints.py` (which assert `audit_identity_table`/`materialization_audit` still report `identity_collision` with `has_failures=True`) must remain green — Task 3 is display-only and does not change them.

- [ ] **Lint the whole tree**

Run: `cd ~/d/science/science && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: clean.

---

## Self-Review

**Spec coverage** — Phase 2b's two settled deliverables both have tasks, and the review finding is resolved:
- "flip zero-owner from synthesize + warn to error" → Task 1 (conformance severity unconditional ERROR; loader synthesis untouched, per Scope guard).
- "add the conformance check that forbids a second declaration" → Task 2 (graded §B1 collision check) + Task 3 (route the graph-audit copy away so the new check is the single validate-surface — resolves the High finding that `check_graph` would otherwise hard-fail transitional shadows the new check WARNs).
- Resource→PROV deferred to 2c (Scope guard) — not a gap.

**Placeholder scan** — no TBD/TODO; every code step shows full file or exact diff; every run step has an expected outcome. The Task 3 import/scaffolding note carries an explicit "confirm against existing file" instruction rather than a guess.

**Type consistency** — `IdentityCollision(owner_scope, canonical_id, rows: tuple[...])` matches `identity_table.py:39-45`. `IdentityDeclaration(canonical_id, participation_mode, owner_scope, adapter, source_ref, deprecated)` matches `:27-36`. `SourceRef(adapter_name, path, line=None)` matches `source_ref.py:14-19`. `Result(severity, path, line, message, rule, ...)` matches the orphan check's existing call shape. `build_identity_table` / `IdentityTable.collisions()` reused verbatim. `_load_canonical_checks`/`clear_checks_for_tests`/`CANONICAL_CHECKS` exports confirmed against `test_overlay_of_check_registered_via_canonical_loader`. `@Check` order 50 confirmed free.

**Consistency of the collision policy across surfaces** — after 2b: `science validate` reports a genuine duplicate as ERROR and a transitional stub shadow as WARN, from one check (Task 2); `check_graph` no longer double-reports either (Task 3). The strict graph-**build** gate (`has_failures`) is deliberately unchanged and still treats a transitional shadow as a blocker (pre-existing 1.4b behavior) — called out in the Scope guard as a separate follow-up, not silently diverged.

**Risk note** — Task 1's unconditional ERROR means any pre-v3 project with an orphan datapackage (possibly MM30) starts failing `science validate` until `promote-orphans --apply` is run — the intended Phase-2 forcing function. Surface it in the final report; do not weaken the check.

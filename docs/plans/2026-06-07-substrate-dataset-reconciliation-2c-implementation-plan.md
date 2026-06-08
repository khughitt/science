# Substrate Phase 2c — resource→PROV materialization + build-gate alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the two documented §B4 follow-ups: (1) materialize a dataset's datapackage `resources` array as **DCAT distribution / PROV-Entity triples about the dataset entity** (the half-realized "the datapackage compiles into the graph as resource/`prov` triples about the dataset entity" — today only geneset *members* materialize), and (2) **align the strict build gate with the carry-transitional WARN policy** by making `audit_identity_table` deprecation-aware (a transitional stub-shadow is carried, not a hard `fail`), converging the three places that grade an identity collision onto a single `IdentityCollision.is_genuine` predicate.

**Architecture:** Three tasks, smallest-blast-radius first. **Task 1** is a pure DRY + behavior fix in the graph layer: add an `is_genuine` property to `IdentityCollision` (`>=2 non-deprecated owner rows`) and repoint the three existing graders to it — `audit_identity_table` (was deprecation-blind `fail`, the misaligned build-gate path), the migrator's `_identity_collision_rows` (already graded, repointed for DRY), and validate's `graded_collisions` (already graded, repointed for DRY). The `has_failures` consumers that read `audit_identity_table`'s rows directly (strict `materialize_graph` build gate, `materialization_audit`/`graph audit` CLI, the freshness gate) all derive their gate from those rows, so the single grading change carries to all of them, and a genuine duplicate still sets `fail`. (The migrator-apply path already filters `identity_collision` rows out of the audit and recomputes them deprecation-aware via `_identity_collision_rows`, so it was **never** affected by the deprecation-blind audit; Task 1 repoints that recompute onto the shared predicate for DRY and refreshes its now-stale "deprecation-blind" comment.) **Task 2** adds the DCAT namespace, a §B4-aware datapackage path resolver, and a **lenient** resource reader (project datapackages are looser than commons ones — a resource may lack a hash, or the datapackage may declare no `resources` at all). **Task 3** wires a new `_add_dataset_resource_edges` emitter into `_build_dataset_from_sources`, populating the currently-empty `graph/datasets` named graph.

**Tech Stack:** Python 3.13, `rdflib` (PROV, DCAT, DCTERMS, SCI namespaces), `science_tool.graph` (`identity_table`, `migrate`, `materialize`), `science_tool.commons.datapackage` (the new materialization path — `read_dataset_resources` / `DatasetResource` / `DatasetResourceError` — reusing the strict `ResourceSource` / `validate_source` / `parse_resource_hash` / `validate_logical_path` primitives; the strict `read_datapackage` / `DataResource` is left untouched), `science_tool.commons.geneset_resources`. Tests: `cd ~/d/science/science && uv run --frozen pytest`. Lint: `uv run --frozen ruff check . && uv run --frozen ruff format --check .` (120-char).

---

## Scope guard (what is OUT of Phase 2c)

- **`entities.yaml` retirement / `AggregateAdapter` removal** (§B5) is Phase 3, not 2c. Task 1 makes a transitional aggregate-stub shadow a *carried WARN* across the build gate; it does **not** delete stubs or remove the deprecated-owner mode.
- **External-reference resolver / federation `t068`** (§B3a, §D4) is Phase 4.
- **Commons-scope (borrowed) dataset resources.** Task 3 materializes resources only for datasets this project owns with a **local** datapackage (orphan datapackage, or a real owner with a deferred local datapackage). A `commons-merged` dataset's resources belong to the commons scope's own materialization (§B4 `owner_scope`), so `dataset_datapackage_path` returns `None` for it — deliberately, not an oversight.
- **No new conformance check.** 2b's `forbidden-second-declaration` check already owns the validate surface; 2c only changes the *severity grading* it (and the audit, and the migrator) share, plus adds materialization. No new `@Check`.

---

## File structure

| File | Responsibility | Task |
|---|---|---|
| `src/science_tool/graph/identity_table.py` (modify) | Add `IdentityCollision.is_genuine` — the single `>=2 non-deprecated owners` predicate (§B1 genuine duplicate vs §C3/§B4 transitional shadow) | 1 |
| `src/science_tool/graph/migrate.py` (modify) | `audit_identity_table` grades `fail`/`warn` via `is_genuine` (was deprecation-blind `fail`) — aligns the build gate with carry-transitional (§C4) | 1 |
| `src/science_tool/entity_layout_migration.py` (modify) | `_identity_collision_rows` consumes `is_genuine` (DRY; behavior unchanged); refresh the now-stale `_postmove_audit_failures` "deprecation-blind" comment | 1 |
| `src/science_tool/validate/checks/identity_collision.py` (modify) | `graded_collisions` consumes `is_genuine` (DRY; behavior unchanged) | 1 |
| `src/science_tool/graph/materialize.py` (modify) | `materialize_graph` build-gate load → `strict_identity=False` so the deprecation-aware audit is the real gate (else a shadow raises at load) | 1 |
| `src/science_tool/graph/freshness.py` (modify) | Freshness-gate load → `strict_identity=False` (same gate family as the build) | 1 |
| `tests/test_graph_identity_table.py` (modify) | Unit-test `is_genuine` (genuine / transitional-shadow / two-deprecated / single) | 1 |
| `tests/test_graph_migrate_identity_audit.py` (modify) | Repoint the audit pinning tests: transitional shadow → `warn`/`failed False`; add genuine-duplicate → `fail` | 1 |
| `tests/test_identity_audit_entrypoints.py` (modify) | `materialization_audit` on a stub shadow → `has_failures False`, row still present | 1 |
| `tests/test_graph_build_strict.py` (modify) | Build carries a transitional stub-shadow; still blocks a genuine duplicate (now `ValueError`) | 1 |
| `src/science_tool/graph/io.py` (modify) | Declare `DCAT_NS` + register the `dcat` serializer prefix | 2 |
| `src/science_tool/commons/geneset_resources.py` (modify) | Factor `resolve_dataset_datapackage_source`; add `dataset_datapackage_path` (§B4-aware, local-only) | 2 |
| `src/science_tool/commons/datapackage.py` (modify) | Add `read_dataset_resources` + `DatasetResource` + `DatasetResourceError` (materialization view: lenient on absence — optional hash/bytes, no `resources` → `()`; strict on malformation — declared-but-broken path/hash/source raises) | 2 |
| `tests/test_commons_geneset_resources_datapackage_path.py` (create) | Unit-test the §B4 path resolution (orphan / deferred / commons-merged / none / entity.md sibling) | 2 |
| `tests/test_commons_read_dataset_resources.py` (create) | Unit-test the reader (no resources → (); missing hash → kept, hash None; full resource; url source; descriptive wrong-type ignored; malformed path/hash/source/entry → `DatasetResourceError`) | 2 |
| `src/science_tool/graph/materialize.py` (modify) | Capture the `datasets` graph; add `_add_dataset_resource_edges` + `_resource_uri`; wire into `_build_dataset_from_sources` | 3 |
| `src/science_tool/graph/store/constants.py` (modify) | Register `dcat:downloadURL` in `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (metadata, not a graph edge) | 3 |
| `tests/test_dataset_resource_materialize.py` (create) | Disk-integration: orphan + deferred datapackage → DCAT distribution / prov:Entity triples in `graph/datasets` | 3 |
| `tests/test_graph_export.py` (modify) | Export pins `dcat:distribution` as an edge, `dcat:downloadURL` as metadata (no spurious edge) | 3 |

---

## Task 1: Align the build gate — one `is_genuine` predicate, three consumers

**Context:** The §B1 collision is graded the same way in three places, but inconsistently:

1. `validate/checks/identity_collision.py::graded_collisions` — `non_deprecated >= 2 → ERROR else WARN` (added in 2b).
2. `entity_layout_migration.py::_identity_collision_rows` — `real_owners >= 2 → fail-blocker else warn` (migrator-apply path; already graded).
3. `graph/migrate.py::audit_identity_table` — **deprecation-blind: always `fail`.** This is the one the 2b plan flagged: it drives `has_failures`, so a transitional aggregate-stub shadow still hard-fails the strict `materialize_graph` build gate and the migrator recompute, contradicting the §C4 carry-transitional intent and the 2b graded validate policy.

Fix: hoist the `>=2 non-deprecated owners` test onto `IdentityCollision.is_genuine` (the design's single source of truth for "genuine §B1 duplicate vs transitional shadow"), and repoint all three. `audit_identity_table` becomes deprecation-aware (the behavior change); the other two are pure DRY repoints (behavior identical). `IdentityTable.collisions()/owners()` already excludes BORROWER/external rows, so this only ever grades owner-vs-owner.

**`has_failures` blast radius (verified) — and a load-strictness gotcha:** three gates read `audit_identity_table`'s rows via `audit_project_sources`: the `materialize_graph` build gate (`materialize.py:196-204`), `materialization_audit` → `graph audit` CLI (`materialize.py:215`, `cli.py:1062`), and the freshness gate (`freshness.py:411-414`). **But the audit-grade change alone is not enough for the build gate.** `materialization_audit` already loads with `strict_identity=False` (`materialize.py:215`), so the regrade reaches the `graph audit` CLI directly. `materialize_graph` and the freshness gate, however, call `load_project_sources(project_root)` with the **default `strict_identity=True`**, which **raises `EntityIdentityCollisionError` at load time** (`sources.py:416`) for *any* collision — transitional shadow included — *before* the audit ever runs. So Task 1 must **also switch those two loads to `strict_identity=False`**, letting the now-deprecation-aware `audit_project_sources`/`has_failures` be the real gate: a transitional shadow loads + carries (warn), a genuine duplicate is blocked by the audit (`fail` → the existing `ValueError`). Without this, the §C4 "a half-rolled project is never bricked" goal is not actually delivered for the build. (The strict *load* path itself — `load_project_sources(...)` with the default — still raises, and `test_strict_load_still_raises_on_stub_shadow` keeps pinning that; only the two gate call-sites relax.)

**The migrator-apply path is NOT a direct consumer (corrected):** `_postmove_audit_failures` (`entity_layout_migration.py:872`) already *filters* `identity_collision` rows out of `audit_project_sources`'s output and *recomputes* them via `_identity_collision_rows` (which is already deprecation-aware). So the migrator was never bound by the deprecation-blind audit — its blocker/warning split was already correct. Task 1 repoints `_identity_collision_rows` onto `is_genuine` (DRY, no behavior change) and refreshes the now-false "deprecation-blind" comment at the filter site. (`store/validation.py` / `validate_graph` `has_failures` is a *different*, post-build graph-store check, unaffected.)

**Files:**
- Modify: `src/science_tool/graph/identity_table.py`, `src/science_tool/graph/migrate.py`, `src/science_tool/entity_layout_migration.py`, `src/science_tool/validate/checks/identity_collision.py`, `src/science_tool/graph/materialize.py` (build-gate load → non-strict), `src/science_tool/graph/freshness.py` (freshness-gate load → non-strict)
- Test: `tests/test_graph_identity_table.py`, `tests/test_graph_migrate_identity_audit.py`, `tests/test_identity_audit_entrypoints.py`, `tests/test_graph_build_strict.py`

- [ ] **Step 1: Write the failing unit test for the predicate**

In `tests/test_graph_identity_table.py`, add (reuse the file's existing `IdentityDeclaration`/`ParticipationMode`/`IdentityTable` imports; add `IdentityCollision` to them if not already imported, and `SourceRef` from `science_model.source_ref`):

```python
def _collision(*deprecations: bool) -> IdentityCollision:
    rows = tuple(
        IdentityDeclaration(
            canonical_id="dataset:x",
            participation_mode=ParticipationMode.OWNER,
            owner_scope="proj",
            adapter="markdown",
            source_ref=SourceRef(adapter_name="markdown", path=f"p{i}.md"),
            deprecated=dep,
        )
        for i, dep in enumerate(deprecations)
    )
    return IdentityCollision(owner_scope="proj", canonical_id="dataset:x", rows=rows)


def test_is_genuine_two_real_owners() -> None:
    assert _collision(False, False).is_genuine is True


def test_is_genuine_transitional_shadow_is_not_genuine() -> None:
    # one real markdown owner + one deprecated aggregate/datapackage stub -> carried, not a hard error
    assert _collision(False, True).is_genuine is False


def test_is_genuine_two_deprecated_owners_is_not_genuine() -> None:
    assert _collision(True, True).is_genuine is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py::test_is_genuine_two_real_owners -v`
Expected: FAIL — `AttributeError: 'IdentityCollision' object has no attribute 'is_genuine'`.

- [ ] **Step 3: Add the `is_genuine` property**

In `src/science_tool/graph/identity_table.py`, add the property to the `IdentityCollision` dataclass (currently lines ~39-45):

```python
@dataclass(frozen=True)
class IdentityCollision:
    """Two owner rows sharing one (owner_scope, canonical_id) — the identity error."""

    owner_scope: str
    canonical_id: str
    rows: tuple[IdentityDeclaration, ...]

    @property
    def is_genuine(self) -> bool:
        """True when >=2 owner rows are non-deprecated — the genuine §B1 duplicate the
        compiler must reject. A collision involving a transitional deprecated owner (an
        entities.yaml aggregate stub §C3, or a synthesized orphan-datapackage owner §B4)
        shadowing a real owner is carried as rollout debt (§C4), surfaced as a non-blocking
        WARN, not a hard error. The single source of truth for this grade across the
        validate check, the graph audit, and the migrator.
        """
        return sum(1 for row in self.rows if not row.deprecated) >= 2
```

- [ ] **Step 4: Run the predicate unit tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py -k is_genuine -v`
Expected: PASS — all three green.

- [ ] **Step 5: Repoint `audit_identity_table` (the behavior change)**

In `src/science_tool/graph/migrate.py`, change `audit_identity_table` (currently lines ~146-161) so the status grades via `is_genuine`:

```python
def audit_identity_table(table: IdentityTable) -> list[dict]:
    """Turn identity-table collisions into graph-audit rows (design §B3, §C2).

    A genuine duplicate (>=2 non-deprecated owners) is `fail` (blocks the strict build
    gate via has_failures); a transitional stub-shadow is `warn` — carried until §B5
    retirement, not a build blocker (§C4). Grade via the shared IdentityCollision
    predicate so this path, the migrator, and the validate check never diverge.
    """
    rows: list[dict] = []
    for collision in table.collisions():
        paths = [(r.source_ref.path if r.source_ref else "<unknown>") for r in collision.rows]
        rows.append(
            {
                "check": "identity_collision",
                "status": "fail" if collision.is_genuine else "warn",
                "source": collision.canonical_id,
                "field": "owner_scope",
                "target": collision.owner_scope,
                "details": "owned by " + " and ".join(paths),
            }
        )
    return rows
```

- [ ] **Step 6: Repoint the migrator grader (DRY, no behavior change)**

In `src/science_tool/entity_layout_migration.py::_identity_collision_rows` (currently lines ~758-786), replace the local `real_owners = sum(...)` computation with `collision.is_genuine`:

```python
    blockers: list[dict] = []
    warnings: list[dict] = []
    for collision in table.collisions():
        paths = [(r.source_ref.path if r.source_ref else "<unknown>") for r in collision.rows]
        row = {
            "check": "identity_collision",
            "status": "fail" if collision.is_genuine else "warn",
            "source": collision.canonical_id,
            "field": "owner_scope",
            "target": collision.owner_scope,
            "details": "owned by " + " and ".join(paths),
        }
        (blockers if collision.is_genuine else warnings).append(row)
    return blockers, warnings
```

Leave the docstring's §B3/§C4 explanation intact (it already documents exactly this grade).

Then refresh the now-stale comment in `_postmove_audit_failures` (same file, ~line 872). It currently reads:

```python
    # Drop the audit's deprecation-blind identity_collision fails; we recompute them
    # deprecation-aware below (a transitional shadow must not hard-block, design §C4).
```

After Task 1 the audit is no longer deprecation-blind. Replace with:

```python
    # Separate identity_collision rows from the flat audit list; we recompute them split
    # into blockers vs transitional warnings via _identity_collision_rows below. The audit
    # now grades them deprecation-aware too (Task 1), but returns one flat row list — the
    # migrator needs the blocker/warning split for its own output (a transitional shadow
    # must not hard-block, design §C4).
```

The filter expression itself (`r.get("check") != "identity_collision"`) is unchanged — it still correctly routes collision rows to the recompute.

- [ ] **Step 7: Repoint the validate grader (DRY, no behavior change)**

In `src/science_tool/validate/checks/identity_collision.py::graded_collisions` (currently lines ~40-52), replace the local `non_deprecated` computation with `is_genuine`:

```python
def graded_collisions(table: IdentityTable) -> list[tuple[Severity, IdentityCollision]]:
    """Each (owner_scope, canonical_id) collision paired with its severity.

    ERROR for a genuine §B1 duplicate (>=2 non-deprecated owners); WARN otherwise (a
    deprecated transitional owner shadows a real owner — §C3 rollout debt carried until
    §B5, visible but non-blocking). Grade via IdentityCollision.is_genuine so this check,
    the graph audit, and the migrator share one source of truth.
    """
    return [
        (Severity.ERROR if collision.is_genuine else Severity.WARN, collision)
        for collision in table.collisions()
    ]
```

- [ ] **Step 8: Update the audit pinning tests for the new grade**

In `tests/test_graph_migrate_identity_audit.py`, the existing `test_audit_identity_table_reports_collision_rows` builds a markdown owner + a `deprecated=True` aggregate row — a transitional shadow, now `warn`. Change its status assertion and add a genuine-duplicate companion:

```python
def test_audit_identity_table_transitional_shadow_is_warn():
    # markdown owner + deprecated aggregate STUB shadow -> carried (warn), not a build blocker (§C4)
    table = IdentityTable(
        rows=[
            _owner("question:q1", "markdown", "entities/question/0007-q1.md"),
            _owner("question:q1", "aggregate", "knowledge/sources/local/entities.yaml", deprecated=True),
        ]
    )
    rows = audit_identity_table(table)
    assert len(rows) == 1
    row = rows[0]
    assert row["check"] == "identity_collision"
    assert row["status"] == "warn"
    assert row["source"] == "question:q1"
    assert row["field"] == "owner_scope"
    assert row["target"] == "proj"
    assert "entities/question/0007-q1.md" in row["details"]
    assert "knowledge/sources/local/entities.yaml" in row["details"]


def test_audit_identity_table_genuine_duplicate_is_fail():
    # two NON-deprecated owners of one (owner_scope, canonical_id) -> genuine §B1 duplicate, fail
    table = IdentityTable(
        rows=[
            _owner("question:q1", "markdown", "entities/question/a.md"),
            _owner("question:q1", "markdown", "entities/question/b.md"),
        ]
    )
    rows = audit_identity_table(table)
    assert len(rows) == 1
    assert rows[0]["status"] == "fail"
    assert rows[0]["source"] == "question:q1"
```

> Replace the old `test_audit_identity_table_reports_collision_rows` with `test_audit_identity_table_transitional_shadow_is_warn` (same fixture, flipped expectation) and add `test_audit_identity_table_genuine_duplicate_is_fail`. The `_owner(...)` helper already defaults `deprecated=False`.

Then update `test_nonstrict_load_then_audit_reports_identity_collision` in the same file: the disk fixture (`_md` markdown + `_agg` deprecated aggregate stub) is a transitional shadow, so `has_failures` is now `False` while the collision row is still present as a `warn`:

```python
def test_nonstrict_load_then_audit_reports_identity_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _md(tmp_path, "entities/questions/q1.md", "question:q1", "question")
    _agg(tmp_path, "question:q1", "question")
    sources = load_project_sources(tmp_path, include_commons=False, strict_identity=False)
    rows, failed = audit_project_sources(sources)
    # transitional stub-shadow is carried (§C4): surfaced as a warn row, does NOT fail the build
    assert failed is False
    collision_rows = [r for r in rows if r["check"] == "identity_collision"]
    assert len(collision_rows) == 1
    assert collision_rows[0]["source"] == "question:q1"
    assert collision_rows[0]["status"] == "warn"
```

Leave `test_strict_load_still_raises_on_stub_shadow` unchanged — the strict *load* still raises `EntityIdentityCollisionError` (that is the loader's strict gate, independent of the non-strict audit grading). Leave `test_clean_project_audit_has_no_identity_collision` and the `_audit_reference` ambiguous-reference tests unchanged.

- [ ] **Step 9: Update the entrypoints pinning test**

In `tests/test_identity_audit_entrypoints.py`, `test_materialization_audit_reports_collision_without_crashing` uses the same stub-shadow fixture; flip `has_failures` and assert the row is now a carried `warn`:

```python
def test_materialization_audit_reports_collision_without_crashing(tmp_path: Path) -> None:
    _stub_shadow(tmp_path)
    rows, has_failures = materialization_audit(tmp_path)  # must not raise
    # transitional stub-shadow is carried (§C4): a warn row, not a build failure
    assert has_failures is False
    collision = [r for r in rows if r["check"] == "identity_collision" and r["source"] == "question:q1"]
    assert len(collision) == 1
    assert collision[0]["status"] == "warn"
```

Leave `test_collect_unresolved_refs_excludes_identity_collision` and `test_build_health_report_diagnostic_load_is_nonstrict` unchanged.

- [ ] **Step 10: Switch the build + freshness gate loads to non-strict and pin the build behavior**

The audit regrade only governs the build once these two gates stop raising at load time. Change both call-sites.

In `src/science_tool/graph/materialize.py` (`materialize_graph`, ~line 196):

```python
    sources = load_project_sources(project_root, strict_identity=False)
```

In `src/science_tool/graph/freshness.py` (the audit-gated freshness entry, ~line 411):

```python
    sources = load_project_sources(project_root.resolve(), strict_identity=False)
```

Both then rely on `audit_project_sources` / `has_failures` (now deprecation-aware) as the real gate: a genuine duplicate still raises the existing `ValueError`, a transitional shadow loads and carries.

Add build-gate tests to `tests/test_graph_build_strict.py`:

```python
def _seed(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: proj\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8"
    )


def _question_md(root: Path, filename: str, cid: str) -> None:
    p = root / "entities" / "questions" / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{cid}"\ntype: "question"\ntitle: "{cid}"\n---\n', encoding="utf-8")


def _aggregate_stub(root: Path, cid: str) -> None:
    local = root / "knowledge" / "sources" / "local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "entities.yaml").write_text(
        f"entities:\n  - canonical_id: {cid}\n    kind: question\n    title: {cid}\n"
        "    profile: local\n    source_path: knowledge/sources/local/entities.yaml\n",
        encoding="utf-8",
    )


def test_strict_build_carries_transitional_stub_shadow(tmp_path: Path) -> None:
    # a real markdown owner shadowed by a DEPRECATED aggregate stub must NOT brick the
    # build (§C4 carry-transitional): the load no longer raises and the audit only warns.
    from science_tool.graph.materialize import materialize_graph

    _seed(tmp_path)
    _question_md(tmp_path, "q1.md", "question:q1")
    _aggregate_stub(tmp_path, "question:q1")
    trig = materialize_graph(tmp_path, strict=True)  # must not raise
    assert trig.is_file()


def test_strict_build_blocks_genuine_duplicate(tmp_path: Path) -> None:
    # two NON-deprecated owners of one id is a genuine §B1 collision — still blocked, now
    # at the audit stage (ValueError) rather than at load (EntityIdentityCollisionError).
    from science_tool.graph.materialize import materialize_graph

    _seed(tmp_path)
    _question_md(tmp_path, "q1.md", "question:q1")
    _question_md(tmp_path, "q1-dup.md", "question:q1")
    with pytest.raises(ValueError):
        materialize_graph(tmp_path, strict=True)
```

> Note for the implementer: `tests/test_graph_build_strict.py` does not define `_seed`/`_question_md`/`_aggregate_stub` today; if a name clashes after a rebase, rename the local helpers. The carry test builds a full graph, so the seed + one question must be the only content (no stray unresolved refs).

- [ ] **Step 11: Run the affected test files**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_identity_table.py tests/test_graph_migrate_identity_audit.py tests/test_identity_audit_entrypoints.py tests/test_entity_layout_migration.py tests/test_graph_build_strict.py tests/validate/test_checks_identity_collision.py -v`
Expected: PASS. In particular `test_entity_layout_migration.py::test_identity_collision_rows_blocks_two_real_owners` and `::test_identity_collision_rows_carries_transitional_shadow_as_warning` stay green (the migrator grade is unchanged; only its implementation now delegates to `is_genuine`), the 2b `test_checks_identity_collision.py` graded tests stay green, and the two new `test_graph_build_strict.py` cases pass.

- [ ] **Step 12: Run the full suite to catch any other stub-shadow assumption**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: green. If any test outside the files above fails because it assumed a *transitional* shadow blocks the build/migrator/freshness (it should now carry as a warn), or assumed `materialize_graph`/freshness raises `EntityIdentityCollisionError` on a duplicate (genuine duplicates now raise `ValueError` from the audit gate instead), that is the intended Task-1 behavior change — update the assertion accordingly and note it in the task report. A genuine duplicate (two non-deprecated owners) must still block everywhere.

- [ ] **Step 13: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/graph/identity_table.py src/science_tool/graph/migrate.py src/science_tool/entity_layout_migration.py src/science_tool/validate/checks/identity_collision.py src/science_tool/graph/materialize.py src/science_tool/graph/freshness.py tests/test_graph_identity_table.py tests/test_graph_migrate_identity_audit.py tests/test_identity_audit_entrypoints.py tests/test_graph_build_strict.py && uv run --frozen ruff format --check src/science_tool/graph/identity_table.py src/science_tool/graph/migrate.py src/science_tool/entity_layout_migration.py src/science_tool/validate/checks/identity_collision.py src/science_tool/graph/materialize.py src/science_tool/graph/freshness.py tests/test_graph_identity_table.py tests/test_graph_migrate_identity_audit.py tests/test_identity_audit_entrypoints.py tests/test_graph_build_strict.py`
Expected: clean.

- [ ] **Step 14: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/identity_table.py science/src/science_tool/graph/migrate.py science/src/science_tool/entity_layout_migration.py science/src/science_tool/validate/checks/identity_collision.py science/src/science_tool/graph/materialize.py science/src/science_tool/graph/freshness.py science/tests/test_graph_identity_table.py science/tests/test_graph_migrate_identity_audit.py science/tests/test_identity_audit_entrypoints.py science/tests/test_graph_build_strict.py
git commit -m "fix(substrate-2c): align build gate with carry-transitional collision policy

Two parts. (1) audit_identity_table was deprecation-blind (always fail);
hoist the >=2 non-deprecated-owners test onto IdentityCollision.is_genuine and
converge all three graders (audit, migrator _identity_collision_rows, validate
graded_collisions) on it: a genuine duplicate fails; a transitional shadow is a
warn. (2) The build + freshness gates loaded with strict_identity=True, raising
EntityIdentityCollisionError at LOAD before the audit ran, so the regrade alone
would not unbrick them; switch both to strict_identity=False so the now
deprecation-aware audit is the real gate (genuine duplicate -> ValueError,
transitional shadow carries). The migrator was already deprecation-aware (it
filters + recomputes collision rows), so it is unchanged here beyond the DRY
repoint. Resolves the documented 2b build-gate follow-up (design §C4)."
```

---

## Task 2: DCAT namespace + §B4-aware datapackage-resource reader

**Context:** Materialization needs to read a dataset's datapackage `resources` array independent of which adapter won the owner column — the exact §B4 ownership branch already encoded inline in `dataset_geneset_frontmatter` (`commons/geneset_resources.py:56-61`). Factor that branch into a reusable resolver and add a `dataset_datapackage_path` that returns the **local** datapackage path for a dataset (orphan datapackage, or a real owner's deferred local datapackage), or `None` (commons-merged / no datapackage). Task 3 feeds that path to the **lenient** `read_dataset_resources` (added below — *not* the strict commons-promotion `read_datapackage`). Also declare the DCAT namespace the emitter needs.

`DataResource` (from `science_tool.commons.datapackage`) exposes `path, hash, name, bytes, format, mediatype, source`, where `source` is a `ResourceSource(type, ref)` with `type ∈ {local, zenodo, github, url, daemon}`.

**Why a separate reader (not `read_datapackage`) — lenient on ABSENCE, strict on MALFORMATION:** `read_datapackage` strictly *raises* on a missing/empty `resources` list (`datapackage.py:435`) and on a resource with a missing/malformed `hash` (`datapackage.py:488`) — it is the commons-promotion validator, and treats *absent* optional data as a hard error. **Project** datapackages are looser about *absence*: existing materialization fixtures include entity-profile datapackages with **no `resources` key** (`tests/test_dataset_usage_materialize.py:296`) and geneset resources **without hashes** (`tests/test_dataset_usage_materialize.py:799`). So the materialization reader must tolerate *absent* optional data: no `resources` → `()`, no `hash` → `hash=None`.

But "optional" means "may be **absent**", not "may be silently **invalid**" (project rule: *fail early / avoid silent fallbacks*). A *declared* resource that is malformed — a non-mapping entry, a missing/invalid logical `path`, a present-but-malformed `hash`, or a malformed `source` — is a concrete data bug, distinct from the transitional *identity* debt Task 1 deliberately carries. The reader therefore **raises `DatasetResourceError`** (naming the datapackage and offending field) on those four integrity-bearing malformations, so materialization fails loudly rather than dropping a broken resource on the floor. Descriptive-only fields (`bytes`/`format`/`mediatype`) stay lenient — present-but-wrong-typed → ignored — because they carry no identity/integrity weight. This task adds that reader (`read_dataset_resources` → `DatasetResource`, raising `DatasetResourceError`) alongside the strict one, reusing the same parsing primitives (`validate_logical_path`, `parse_resource_hash`, `validate_source`) so the malformation contract matches `read_datapackage`'s.

**Files:**
- Modify: `src/science_tool/graph/io.py`, `src/science_tool/commons/geneset_resources.py`, `src/science_tool/commons/datapackage.py`
- Test: `tests/test_commons_geneset_resources_datapackage_path.py` (create), `tests/test_commons_read_dataset_resources.py` (create)

- [ ] **Step 1: Declare the DCAT namespace**

In `src/science_tool/graph/io.py`, after the `DCTERMS_NS` line (~18), add:

```python
DCAT_NS = Namespace("http://www.w3.org/ns/dcat#")
```

and register its serializer prefix in `_SERIALIZER_PREFIXES` (add after the `("dcterms", str(DCTERMS_NS))` tuple entry):

```python
    ("dcat", str(DCAT_NS)),
```

- [ ] **Step 2: Write the failing unit test for the path resolver**

Create `tests/test_commons_geneset_resources_datapackage_path.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.commons.geneset_resources import dataset_datapackage_path


def test_orphan_datapackage_returns_entity_path() -> None:
    # adapter == "datapackage": the entity IS the datapackage; its own path is read.
    p = dataset_datapackage_path(
        entity_adapter="datapackage", entity_path="data/ds1/datapackage.yaml", datapackage_rel=None
    )
    assert p == Path("data/ds1/datapackage.yaml")


def test_deferred_owner_returns_recorded_datapackage_rel() -> None:
    # a real markdown owner with a deferred local datapackage attachment.
    p = dataset_datapackage_path(
        entity_adapter="markdown", entity_path="entities/datasets/ds1.md", datapackage_rel="data/ds1/datapackage.yaml"
    )
    assert p == Path("data/ds1/datapackage.yaml")


def test_entity_md_source_maps_to_sibling_datapackage() -> None:
    # an orphan whose entity source is an entity.md sits beside its datapackage.yaml.
    p = dataset_datapackage_path(
        entity_adapter="datapackage", entity_path="data/ds1/entity.md", datapackage_rel=None
    )
    assert p == Path("data/ds1/datapackage.yaml")


def test_commons_merged_is_not_a_local_datapackage() -> None:
    # commons-scope resources are owned/materialized by commons (§B4 owner_scope) -> None here.
    assert (
        dataset_datapackage_path(entity_adapter="commons-merged", entity_path="x/entity.md", datapackage_rel=None)
        is None
    )


def test_no_datapackage_returns_none() -> None:
    assert (
        dataset_datapackage_path(entity_adapter="markdown", entity_path="entities/datasets/ds1.md", datapackage_rel=None)
        is None
    )
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_geneset_resources_datapackage_path.py -v`
Expected: FAIL at import — `ImportError: cannot import name 'dataset_datapackage_path'`.

- [ ] **Step 4: Factor the resolver and add `dataset_datapackage_path`**

In `src/science_tool/commons/geneset_resources.py`, add a shared resolver and the new local-datapackage path function, and repoint `dataset_geneset_frontmatter` to the resolver (behavior-preserving). Insert before `dataset_geneset_frontmatter` (line ~36):

```python
def resolve_dataset_datapackage_source(
    *, entity_adapter: str | None, entity_path: str | Path, datapackage_rel: str | None
) -> str | Path | None:
    """The datapackage source for a dataset entity, independent of which adapter won the
    owner column (design §B4):

    - the entity IS the datapackage (orphan) or a commons-merged dataset → the entity's
      own source path;
    - a real owner with a deferred datapackage attachment → the recorded ``datapackage_rel``;
    - no datapackage attachment → ``None``.
    """
    if entity_adapter in {"datapackage", "commons-merged"}:
        return entity_path
    if datapackage_rel is not None:
        return datapackage_rel
    return None


def dataset_datapackage_path(
    *, entity_adapter: str | None, entity_path: str | Path, datapackage_rel: str | None
) -> Path | None:
    """The LOCAL datapackage file for a dataset entity (design §B4), or ``None``.

    Like ``resolve_dataset_datapackage_source`` but excludes ``commons-merged`` (those
    resources are owned/materialized by the commons scope, not this project) and
    normalizes an ``entity.md`` source to its sibling ``datapackage.yaml``. Used to
    materialize a dataset's resources as DCAT distributions (§B4) regardless of whether
    the datapackage is an orphan owner or a deferred attachment on a real owner.
    """
    if entity_adapter == "datapackage":
        source: str | Path = entity_path
    elif datapackage_rel is not None:
        source = datapackage_rel
    else:
        return None
    path = Path(source)
    if path.name == "entity.md":
        return path.parent / "datapackage.yaml"
    return path
```

Then change `dataset_geneset_frontmatter`'s inline branch (lines ~56-61) to call the resolver:

```python
    source = resolve_dataset_datapackage_source(
        entity_adapter=entity_adapter, entity_path=entity_path, datapackage_rel=datapackage_rel
    )
    if source is None:
        return None
    return geneset_resource_frontmatter(project_root, source)
```

> Note for the implementer: this is a behavior-preserving extraction of the existing branch. Confirm `tests/` for `dataset_geneset_frontmatter` (e.g. `test_dataset_usage_materialize.py`, geneset tests) stay green in Step 6.

- [ ] **Step 5: Run the path-resolver tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_geneset_resources_datapackage_path.py -v`
Expected: PASS — all five green.

- [ ] **Step 6: Write the failing unit test for the lenient resource reader**

Create `tests/test_commons_read_dataset_resources.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.commons.datapackage import (
    DatasetResource,
    DatasetResourceError,
    ResourceSource,
    read_dataset_resources,
)

_GOOD_HASH = "sha256:" + "a" * 64


def _write(path: Path, doc: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def test_no_resources_key_returns_empty(tmp_path: Path) -> None:
    # an entity-profile datapackage with no resources (e.g. gtex/derived fixtures) -> ()
    dp = _write(tmp_path / "datapackage.yaml", {"profiles": ["science-pkg-entity-1.0"], "id": "dataset:x"})
    assert read_dataset_resources(dp) == ()


def test_resource_without_hash_is_kept_with_none_hash(tmp_path: Path) -> None:
    # geneset member resources legitimately lack a hash -> resource still materializes
    dp = _write(tmp_path / "datapackage.yaml", {"resources": [{"name": "sets", "path": "sets.csv"}]})
    resources = read_dataset_resources(dp)
    assert resources == (DatasetResource(path="sets.csv", name="sets"),)
    assert resources[0].hash is None


def test_full_resource_fields_are_parsed(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        {
            "resources": [
                {
                    "name": "counts",
                    "path": "counts.parquet",
                    "hash": _GOOD_HASH,
                    "bytes": 12345678,
                    "format": "parquet",
                    "source": {"type": "url", "ref": "https://example.org/counts.parquet"},
                }
            ]
        },
    )
    assert read_dataset_resources(dp) == (
        DatasetResource(
            path="counts.parquet",
            name="counts",
            hash=_GOOD_HASH,
            bytes=12345678,
            format="parquet",
            source=ResourceSource(type="url", ref="https://example.org/counts.parquet"),
        ),
    )


def test_descriptive_fields_wrong_typed_are_ignored_not_raised(tmp_path: Path) -> None:
    # bytes/format/mediatype carry no integrity weight -> present-but-wrong-typed is ignored
    dp = _write(
        tmp_path / "datapackage.yaml",
        {"resources": [{"path": "ok.csv", "bytes": "big", "format": 7, "mediatype": []}]},
    )
    assert read_dataset_resources(dp) == (DatasetResource(path="ok.csv"),)


def test_malformed_hash_raises(tmp_path: Path) -> None:
    # a DECLARED but malformed hash is a data bug -> loud, not silently dropped to None
    dp = _write(tmp_path / "datapackage.yaml", {"resources": [{"path": "ok.csv", "hash": "not-a-hash"}]})
    with pytest.raises(DatasetResourceError, match="hash"):
        read_dataset_resources(dp)


def test_pathless_entry_raises(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", {"resources": [{"name": "no-path"}]})
    with pytest.raises(DatasetResourceError, match="path"):
        read_dataset_resources(dp)


def test_non_mapping_entry_raises(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", {"resources": ["scalar-entry"]})
    with pytest.raises(DatasetResourceError, match="mapping"):
        read_dataset_resources(dp)


def test_malformed_source_raises(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        {"resources": [{"path": "ok.csv", "source": {"type": "bogus", "ref": "x"}}]},
    )
    with pytest.raises(DatasetResourceError, match="source"):
        read_dataset_resources(dp)


def test_absent_or_non_list_resources_returns_empty(tmp_path: Path) -> None:
    # top-level ABSENCE/ambiguity (file gone, or `resources` not a list) is "no
    # distributions", not a malformation -> (); only DECLARED entries are graded.
    missing = tmp_path / "nope.yaml"
    assert read_dataset_resources(missing) == ()
    scalar = _write(tmp_path / "scalar.yaml", {"resources": "not-a-list"})
    assert read_dataset_resources(scalar) == ()
```

- [ ] **Step 7: Run it to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_read_dataset_resources.py -v`
Expected: FAIL at import — `ImportError: cannot import name 'DatasetResource'` / `read_dataset_resources`.

- [ ] **Step 8: Add the lenient reader to `commons/datapackage.py`**

In `src/science_tool/commons/datapackage.py`, add (after the `DataResource` / `ResourceSource` dataclasses, ~line 380; `yaml`, `validate_logical_path`, `parse_resource_hash`, `validate_source`, `DataLogicalPathError` are all already in-module):

```python
class DatasetResourceError(ValueError):
    """A datapackage DECLARES a resource that is present but malformed (design §B4).

    Distinct from a legitimately *absent* optional field (no `resources` list, no `hash`),
    which `read_dataset_resources` tolerates. A declared resource with a non-mapping entry,
    a missing/invalid logical `path`, a malformed `hash`, or a malformed `source` is a
    concrete data bug — fail loudly (project rule: fail early / avoid silent fallbacks)
    rather than silently dropping a broken resource. The message names the datapackage path
    and the offending field. (This is *not* transitional identity debt — Task 1 carries
    that; a broken resource hash is unrelated to rollout state and must be fixed.)
    """


@dataclass(frozen=True, slots=True)
class DatasetResource:
    """A materialization view of one datapackage resource (design §B4).

    Unlike `DataResource` (the strict commons-promotion view), the optional fields may be
    *absent*: project datapackages are looser than commons ones (a resource may lack a
    hash or bytes, a datapackage may declare no resources at all). Absence is tolerated;
    a *present-but-malformed* integrity field (path/hash/source) is not — see
    `read_dataset_resources`, which raises `DatasetResourceError` rather than dropping it.
    """

    path: str
    name: str | None = None
    hash: str | None = None
    bytes: int | None = None
    format: str | None = None
    mediatype: str | None = None
    source: ResourceSource | None = None


def read_dataset_resources(path: Path) -> tuple[DatasetResource, ...]:
    """Resource read for graph materialization (design §B4): lenient on absence, strict on malformation.

    One `DatasetResource` per declared entry. Optional fields are included only when
    present and well-formed; *absent* optionals are fine (no `hash` → `hash=None`).
    Top-level absence/ambiguity — an unreadable datapackage, a non-mapping top level, or no
    `resources` list — yields `()` ("no distributions"). But a DECLARED resource that is
    malformed in an integrity-bearing field raises `DatasetResourceError` (fail early, no
    silent fallback): a non-mapping entry, a missing/invalid `path`, a present-but-malformed
    `hash`, or a malformed `source`. Descriptive-only fields (`bytes`/`format`/`mediatype`)
    stay lenient — present-but-wrong-typed is ignored, since they carry no integrity weight.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return ()
    if not isinstance(raw, dict):
        return ()
    entries = raw.get("resources")
    if not isinstance(entries, list):
        return ()

    out: list[DatasetResource] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DatasetResourceError(f"{path}: resource #{index} is not a mapping: {entry!r}")
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise DatasetResourceError(f"{path}: resource #{index} has no usable 'path'")
        try:
            logical_path = validate_logical_path(raw_path)
        except DataLogicalPathError as exc:
            raise DatasetResourceError(f"{path}: resource '{raw_path}' has an invalid path: {exc}") from exc

        raw_name = entry.get("name")
        name = raw_name if isinstance(raw_name, str) and raw_name.strip() else None

        raw_hash = entry.get("hash")
        if raw_hash is None:
            hash_ = None
        elif isinstance(raw_hash, str):
            try:
                parse_resource_hash(raw_hash)
            except ValueError as exc:
                raise DatasetResourceError(f"{path}: resource '{logical_path}' has a malformed hash {raw_hash!r}: {exc}") from exc
            hash_ = raw_hash
        else:
            raise DatasetResourceError(
                f"{path}: resource '{logical_path}' hash must be a string, got {type(raw_hash).__name__}"
            )

        raw_bytes = entry.get("bytes")
        size = raw_bytes if isinstance(raw_bytes, int) and not isinstance(raw_bytes, bool) and raw_bytes >= 0 else None

        raw_format = entry.get("format")
        fmt = raw_format if isinstance(raw_format, str) and raw_format.strip() else None

        raw_mediatype = entry.get("mediatype")
        mediatype = raw_mediatype if isinstance(raw_mediatype, str) and raw_mediatype.strip() else None

        raw_source = entry.get("source")
        if raw_source is None:
            source = None
        else:
            try:
                source = validate_source(raw_source)
            except ValueError as exc:
                raise DatasetResourceError(f"{path}: resource '{logical_path}' has a malformed source: {exc}") from exc

        out.append(
            DatasetResource(
                path=logical_path, name=name, hash=hash_, bytes=size, format=fmt, mediatype=mediatype, source=source
            )
        )
    return tuple(out)
```

- [ ] **Step 9: Run the lenient-reader tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_read_dataset_resources.py -v`
Expected: PASS — all nine green (3 well-formed, descriptive-fields-ignored, 4 malformation raises, absent/non-list → ()).

- [ ] **Step 10: Run the geneset/datapackage regression tests + lint**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_usage_materialize.py tests/test_commons_datapackage.py -q && uv run --frozen ruff check src/science_tool/graph/io.py src/science_tool/commons/geneset_resources.py src/science_tool/commons/datapackage.py tests/test_commons_geneset_resources_datapackage_path.py tests/test_commons_read_dataset_resources.py && uv run --frozen ruff format --check src/science_tool/graph/io.py src/science_tool/commons/geneset_resources.py src/science_tool/commons/datapackage.py tests/test_commons_geneset_resources_datapackage_path.py tests/test_commons_read_dataset_resources.py`
Expected: PASS / clean — the `dataset_geneset_frontmatter` refactor is behavior-preserving and the lenient reader is purely additive (strict `read_datapackage` is untouched).

- [ ] **Step 11: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/io.py science/src/science_tool/commons/geneset_resources.py science/src/science_tool/commons/datapackage.py science/tests/test_commons_geneset_resources_datapackage_path.py science/tests/test_commons_read_dataset_resources.py
git commit -m "feat(substrate-2c): DCAT namespace + B4-aware datapackage-resource readers

Declares the dcat: namespace (W3C-native, design D-006), factors the §B4
ownership branch out of dataset_geneset_frontmatter into a shared resolver
(dataset_datapackage_path: orphan owner or a real owner's deferred local
attachment; commons-merged excluded), and adds read_dataset_resources for
materialization: lenient on ABSENCE, strict on MALFORMATION. The commons-promotion
read_datapackage raises on absent resources / missing hash; project datapackages
are looser, so the new reader returns () for no-resources and keeps hash-less
resources with hash=None. But a DECLARED-but-malformed integrity field (non-mapping
entry, missing/invalid path, malformed hash, malformed source) raises
DatasetResourceError rather than being silently dropped (fail early / no silent
fallback); descriptive bytes/format/mediatype stay lenient. Prep for resource->PROV
materialization."
```

---

## Task 3: Materialize datapackage resources as DCAT distributions

**Context:** §B4 says "the datapackage compiles into the graph as resource/`prov` triples *about* the dataset entity." Today only geneset *members* materialize (`_add_dataset_usage_edges`). Add `_add_dataset_resource_edges`: for each dataset entity with a local datapackage (Task 2's `dataset_datapackage_path`), read its `resources` and emit, into the **`graph/datasets`** named graph (created at `materialize.py:90` but currently empty), one DCAT distribution per resource — dual-typed `dcat:Distribution` + `prov:Entity`, linked from the dataset via `dcat:distribution`, with `dcterms:identifier`, `dcterms:format`, `dcat:byteSize`, `sci:resourceHash`, and a `dcat:downloadURL` (for `source.type == "url"`) or `dcterms:source` (other source types). This is the user-approved vocabulary.

**Graph-export note (verified):** `graph export` treats any triple whose object is a `URIRef` and whose predicate is **not** in `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (`store/constants.py:39`) as a node-to-node **edge** (`store/export.py:142`). Of the resource triples, `dcat:distribution` (dataset → resource) is a genuine edge and should stay one; `dcat:downloadURL` has a `URIRef` object (the URL) but is **metadata about the distribution**, not a semantic edge — so it must be registered in `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (Step 7) or `graph export` would mint a spurious edge to the URL. The Literal-valued predicates (`dcterms:identifier`/`format`, `dcat:byteSize`, `sci:resourceHash`, `dcterms:source`) are never treated as edges (the gate checks `isinstance(object_, URIRef)`), and `rdf:type` is already in the metadata set.

**Files:**
- Modify: `src/science_tool/graph/materialize.py`, `src/science_tool/graph/store/constants.py` (register `dcat:downloadURL` as export metadata)
- Test: `tests/test_dataset_resource_materialize.py` (create), `tests/test_graph_export.py` (add a resource-export case)

- [ ] **Step 1: Write the failing disk-integration test**

Create `tests/test_dataset_resource_materialize.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml
from rdflib import Literal, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.graph.io import DCAT_NS, DCTERMS_NS
from science_tool.graph.materialize import _build_dataset_from_sources, _entity_uri
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS

_GOOD_HASH = "sha256:" + "a" * 64


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: proj\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8"
    )


def _datapackage(root: Path, slug: str, ident: str, *, with_url: bool) -> None:
    # MUST carry profiles: [science-pkg-entity-1.0] + id/type/title or DatapackageAdapter
    # never discovers it (storage_adapters/datapackage.py:74).
    pkg = root / "data" / slug
    pkg.mkdir(parents=True, exist_ok=True)
    resource: dict = {
        "name": "counts",
        "path": "counts.parquet",
        "hash": _GOOD_HASH,
        "bytes": 12345678,
        "format": "parquet",
    }
    if with_url:
        resource["source"] = {"type": "url", "ref": "https://example.org/counts.parquet"}
    doc = {
        "profiles": ["science-pkg-entity-1.0"],
        "name": slug,
        "id": ident,
        "type": "dataset",
        "title": ident,
        "origin": "external",
        "access": {"level": "public", "verified": False},
        "resources": [resource],
    }
    (pkg / "datapackage.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _datasets_graph(root: Path):
    sources = load_project_sources(root, include_commons=False)
    ds = _build_dataset_from_sources(sources)
    return ds.graph(PROJECT_NS["graph/datasets"])


def test_orphan_datapackage_resources_materialize_as_dcat(tmp_path: Path) -> None:
    _seed(tmp_path)
    _datapackage(tmp_path, "ds1", "dataset:ds1", with_url=True)
    g = _datasets_graph(tmp_path)

    dataset_uri = _entity_uri("dataset:ds1")
    distributions = list(g.objects(dataset_uri, DCAT_NS.distribution))
    assert len(distributions) == 1
    r = distributions[0]
    assert (r, RDF.type, DCAT_NS.Distribution) in g
    assert (r, RDF.type, PROV.Entity) in g
    assert (r, DCTERMS_NS.identifier, Literal("counts")) in g
    assert (r, DCTERMS_NS.format, Literal("parquet")) in g
    assert (r, SCI_NS.resourceHash, Literal(_GOOD_HASH)) in g
    assert (r, DCAT_NS.downloadURL, URIRef("https://example.org/counts.parquet")) in g
    # dcat:byteSize present as an integer literal
    assert any(int(o) == 12345678 for o in g.objects(r, DCAT_NS.byteSize))


def test_deferred_owner_datapackage_resources_materialize(tmp_path: Path) -> None:
    # a real markdown owner + a sibling datapackage that DEFERS to it (Phase 1.5):
    # resources still materialize about the dataset entity.
    _seed(tmp_path)
    md = tmp_path / "entities" / "datasets" / "ds1.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(
        '---\nid: "dataset:ds1"\ntype: "dataset"\ntitle: "DS1"\norigin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    _datapackage(tmp_path, "ds1", "dataset:ds1", with_url=False)
    g = _datasets_graph(tmp_path)

    dataset_uri = _entity_uri("dataset:ds1")
    distributions = list(g.objects(dataset_uri, DCAT_NS.distribution))
    assert len(distributions) == 1
    assert (distributions[0], DCTERMS_NS.identifier, Literal("counts")) in g


def test_dataset_without_datapackage_has_no_distribution(tmp_path: Path) -> None:
    _seed(tmp_path)
    md = tmp_path / "entities" / "datasets" / "ds2.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(
        '---\nid: "dataset:ds2"\ntype: "dataset"\ntitle: "DS2"\norigin: "external"\n'
        'access:\n  level: "public"\n  verified: false\n---\n',
        encoding="utf-8",
    )
    g = _datasets_graph(tmp_path)
    assert list(g.objects(_entity_uri("dataset:ds2"), DCAT_NS.distribution)) == []
```

> Note for the implementer: these tests pin the real shape of an orphan datapackage's `entity_adapter`/`file_path` in the compiled model. If `test_orphan_datapackage_resources_materialize_as_dcat` shows the orphan's source path is not what `dataset_datapackage_path` expects (e.g. the DatapackageAdapter records `file_path` as the `datapackage.yaml` vs an `entity.md`), adjust `dataset_datapackage_path` (Task 2) so both the orphan and deferred cases resolve — the two tests together lock both branches. Do not weaken the test to pass; fix the resolver.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_resource_materialize.py -v`
Expected: FAIL — `_build_dataset_from_sources` does not yet emit any `dcat:distribution` (the `graph/datasets` graph is empty), so `distributions` is `[]`.

- [ ] **Step 3: Add imports to materialize.py**

In `src/science_tool/graph/materialize.py`, extend the imports:

- Add to the existing `from science_tool.commons.geneset_resources import ...` line: `dataset_datapackage_path`.
- Add `from science_tool.commons.datapackage import DatasetResource, read_dataset_resources`.
- Change `from science_tool.graph.io import CITO_NS` to `from science_tool.graph.io import CITO_NS, DCAT_NS, DCTERMS_NS`.
- Confirm `PROV`, `RDF`, `XSD` are already imported (they are, from `rdflib.namespace`), and `Literal`, `URIRef`, `quote` (they are). Do **not** import `DatasetResourceError` here: a malformed declared resource SHOULD propagate out of materialization (fail early) — the emitter does not catch it. (The reader is lenient on *absence*, so the common no-resources / hash-less cases never raise; only a genuinely broken resource does, and that is meant to fail the build loudly.)

- [ ] **Step 4: Add the resource URI helper + emitter**

In `src/science_tool/graph/materialize.py`, add near `_add_dataset_usage_edges` (after it):

```python
def _resource_uri(dataset_canonical_id: str, resource: DatasetResource) -> URIRef:
    """A deterministic distribution URI under the dataset entity (§B4 resource node)."""
    slug = resource.name or resource.path
    return URIRef(f"{_entity_uri(dataset_canonical_id)}/resource/{quote(slug, safe='')}")


def _add_dataset_resource_edges(sources: ProjectSources, *, datasets) -> None:
    """Materialize each dataset datapackage's `resources` as DCAT distributions about the
    dataset entity (design §B4): the datapackage compiles into resource/prov triples, never
    a second owner. Resource nodes are dual-typed dcat:Distribution + prov:Entity and live
    in the `datasets` named graph. The reader is lenient on absence (a dataset with no
    datapackage, or a datapackage with no/hash-less resources, contributes no distributions
    / a distribution without a hash) but strict on malformation: a declared-but-broken
    resource raises DatasetResourceError, which propagates to fail the build (fail early).
    """
    project_root = Path(sources.project_root)
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        rel = dataset_datapackage_path(
            entity_adapter=sources.entity_source_adapters.get(entity.canonical_id),
            entity_path=entity.file_path,
            datapackage_rel=sources.dataset_datapackages.get(entity.canonical_id),
        )
        if rel is None:
            continue
        dp_path = rel if rel.is_absolute() else project_root / rel
        if not dp_path.is_file():
            continue
        dataset_uri = _entity_uri(entity.canonical_id)
        for resource in read_dataset_resources(dp_path):
            r_uri = _resource_uri(entity.canonical_id, resource)
            datasets.add((dataset_uri, DCAT_NS.distribution, r_uri))
            datasets.add((r_uri, RDF.type, DCAT_NS.Distribution))
            datasets.add((r_uri, RDF.type, PROV.Entity))
            datasets.add((r_uri, DCTERMS_NS.identifier, Literal(resource.name or resource.path)))
            if resource.format:
                datasets.add((r_uri, DCTERMS_NS.format, Literal(resource.format)))
            if resource.bytes is not None:
                datasets.add((r_uri, DCAT_NS.byteSize, Literal(resource.bytes, datatype=XSD.nonNegativeInteger)))
            if resource.hash:
                datasets.add((r_uri, SCI_NS.resourceHash, Literal(resource.hash)))
            if resource.source is not None:
                if resource.source.type == "url":
                    datasets.add((r_uri, DCAT_NS.downloadURL, URIRef(resource.source.ref)))
                else:
                    datasets.add((r_uri, DCTERMS_NS.source, Literal(f"{resource.source.type}:{resource.source.ref}")))
```

- [ ] **Step 5: Wire it into `_build_dataset_from_sources`**

In `_build_dataset_from_sources` (line ~90), capture the `datasets` named graph and call the emitter after `_add_dataset_usage_edges`. Change:

```python
    dataset.graph(PROJECT_NS["graph/datasets"])
```

to:

```python
    datasets = dataset.graph(PROJECT_NS["graph/datasets"])
```

and after the existing `_add_dataset_usage_edges(sources, resolver=resolver, provenance=provenance)` (line ~119) add:

```python
    _add_dataset_resource_edges(sources, datasets=datasets)
```

- [ ] **Step 6: Run the materialization test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_resource_materialize.py -v`
Expected: PASS — all three green (orphan, deferred, no-datapackage).

- [ ] **Step 7: Register `dcat:downloadURL` as export metadata and pin the export shape**

In `src/science_tool/graph/store/constants.py`, add `DCAT_NS` to the existing `from science_tool.graph.io import (...)` block and add `DCAT_NS.downloadURL` to the `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` frozenset:

```python
from science_tool.graph.io import (
    BIOLINK_NS,
    CITO_NS,
    DCAT_NS,
    DCTERMS_NS,
    PROJECT_NS as PROJECT_NS,
    REVISION_URI as REVISION_URI,
    SCHEMA_NS,
    SCI_NS,
    SCIC_NS,
)
```

```python
        # dcat:downloadURL has a URIRef object (the URL) but is distribution METADATA,
        # not a node-to-node edge; dcat:distribution stays the real dataset->resource edge.
        DCAT_NS.downloadURL,
```

Add an export test to `tests/test_graph_export.py` asserting `dcat:distribution` is exported as an edge while `dcat:downloadURL` is NOT. `export_graph_payload(graph_path) -> GraphExportPayload` (already imported in this file) loads a dataset from a `.trig` on disk; `payload.edges` is a list of `GraphExportEdge` whose `.predicate` is the full predicate-URI **string**. The `graph/datasets` named graph IS an exported layer (`_canonical_export_layer_id` maps it through), so the resource edges surface. Add these imports at the top of the file if absent — `from science_tool.graph.io import DCAT_NS`, `from science_tool.graph.materialize import _build_dataset_from_sources`, `from science_tool.graph.sources import load_project_sources`, `from science_tool.graph.store import _save_dataset` (the file already imports `export_graph_payload`), and `import yaml` — then:

```python
def test_dcat_downloadurl_is_metadata_not_an_edge(tmp_path: Path) -> None:
    # dcat:distribution is a real dataset->resource edge; dcat:downloadURL is metadata
    # about the distribution and must NOT become a spurious exported edge to the URL.
    (tmp_path / "science.yaml").write_text(
        "name: proj\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8"
    )
    pkg = tmp_path / "data" / "ds1"
    pkg.mkdir(parents=True)
    (pkg / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "ds1",
                "id": "dataset:ds1",
                "type": "dataset",
                "title": "DS1",
                "origin": "external",
                "access": {"level": "public", "verified": False},
                "resources": [
                    {
                        "name": "counts",
                        "path": "counts.parquet",
                        "source": {"type": "url", "ref": "https://example.org/counts.parquet"},
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    dataset = _build_dataset_from_sources(load_project_sources(tmp_path, include_commons=False))
    graph_path = tmp_path / "graph.trig"
    _save_dataset(dataset, graph_path)

    edge_predicates = {edge.predicate for edge in export_graph_payload(graph_path).edges}
    assert str(DCAT_NS.distribution) in edge_predicates
    assert str(DCAT_NS.downloadURL) not in edge_predicates
```

> Note for the implementer: if `tests/test_graph_export.py` already builds graphs a different way (e.g. via `INITIAL_GRAPH_TEMPLATE` + `add_*` helpers), keep this test's project-seed → `_build_dataset_from_sources` → `_save_dataset` → `export_graph_payload` flow — it is the only way to exercise the *materializer's* resource emission end-to-end. The single property to pin: `dcat:downloadURL` is absent from the exported edge predicates, `dcat:distribution` is present.

- [ ] **Step 8: Run graph materialization + export regressions + lint**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_graph_materialize.py tests/test_dataset_usage_materialize.py tests/test_graph_commons_mm30_canary.py tests/test_graph_export.py -q && uv run --frozen ruff check src/science_tool/graph/materialize.py src/science_tool/graph/store/constants.py tests/test_dataset_resource_materialize.py tests/test_graph_export.py && uv run --frozen ruff format --check src/science_tool/graph/materialize.py src/science_tool/graph/store/constants.py tests/test_dataset_resource_materialize.py tests/test_graph_export.py`
Expected: PASS / clean — resource emission is additive into a previously-empty named graph, and the **lenient** reader is why the existing fixtures stay green: the no-`resources` gtex/derived datapackages (`test_dataset_usage_materialize.py:296`) contribute no distributions, and the hash-less geneset resource (`:799`) materializes a distribution with no `sci:resourceHash` rather than raising. No existing materialization or export assertion regresses.

- [ ] **Step 9: Commit**

```bash
cd ~/d/science
git add science/src/science_tool/graph/materialize.py science/src/science_tool/graph/store/constants.py science/tests/test_dataset_resource_materialize.py science/tests/test_graph_export.py
git commit -m "feat(substrate-2c): materialize datapackage resources as DCAT distributions

Emits each dataset datapackage's resources array into the graph/datasets named
graph as dcat:Distribution + prov:Entity nodes linked dataset --dcat:distribution-->
resource, with dcterms:identifier/format, dcat:byteSize, sci:resourceHash, and
dcat:downloadURL or dcterms:source. Completes §B4 'the datapackage compiles into
resource/prov triples about the dataset entity' (was half-realized: only geneset
members materialized). Registers dcat:downloadURL as export metadata so it stays
distribution metadata, not a spurious graph edge (dcat:distribution remains the
dataset-resource edge). Works for orphan datapackages and real owners with a
deferred local datapackage; commons-merged resources belong to the commons scope."
```

---

## Final verification (after all tasks)

- [ ] **Run the full suite**

Run: `cd ~/d/science/science && uv run --frozen pytest -q`
Expected: green (baseline ~4695 from Phase 2b, plus the new Task-1/2/3 tests; three Phase-2b/earlier pinning tests updated in Task 1). No genuine-duplicate test regresses to a warn; no materialization assertion regresses.

- [ ] **Lint the whole tree**

Run: `cd ~/d/science/science && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: clean.

---

## Self-Review

**Spec coverage** — Phase 2c's two named deliverables both have tasks:
- "resource→PROV materialization" → Task 2 (DCAT namespace + §B4-aware path resolver + `read_dataset_resources`) + Task 3 (`_add_dataset_resource_edges` emitting DCAT distributions / prov:Entity into `graph/datasets`), with the user-approved vocabulary. The reader is **lenient on absence, strict on malformation**: absent resources and hash-less resources are normal (the explicit fix for "project datapackages are looser than commons ones"), but a *declared-but-malformed* integrity field (non-mapping entry, missing/invalid path, malformed hash, malformed source) raises `DatasetResourceError` and propagates to fail the build — honoring *fail early / avoid silent fallbacks* rather than silently dropping a broken resource. Descriptive `bytes`/`format`/`mediatype` stay lenient (no integrity weight).
- "align the strict build gate with the carry-transitional WARN policy" → Task 1: hoist `IdentityCollision.is_genuine`, converge all three graders, **and** switch the `materialize_graph` + freshness gate loads to `strict_identity=False` — the regrade alone is inert at those two call-sites because their default-strict load raises `EntityIdentityCollisionError` before the audit runs. After both, a transitional shadow carries (build succeeds, audit warns) while a genuine duplicate still blocks (audit `fail` → the existing `ValueError`). The `graph audit` CLI already loaded non-strict, so the regrade reaches it directly; the migrator was already deprecation-aware (filters + recomputes) and is only DRY-repointed.

**Placeholder scan** — no TBD/TODO; every code step (including the graph-export test, now a complete seed → `_build_dataset_from_sources` → `_save_dataset` → `export_graph_payload` body) shows the full function or an exact diff; every run step states an expected outcome. The three "Note for the implementer" callouts (geneset-refactor regression; orphan `file_path` shape; export-flow rationale) carry explicit "confirm/fix, do not weaken" instructions and are pinned by concrete TDD tests, not deferred work.

**Type consistency** — `IdentityCollision(owner_scope, canonical_id, rows: tuple[...])` + new `is_genuine` property matches `identity_table.py`. The new `DatasetResource(path, name, hash, bytes, format, mediatype, source)` mirrors `DataResource` but with every field beyond `path` optional, and reuses `ResourceSource(type, ref)` verbatim; `read_dataset_resources` reuses the in-module `validate_logical_path` / `parse_resource_hash` / `validate_source` / `DataLogicalPathError` primitives and raises the new `DatasetResourceError(ValueError)` (defined alongside `DatasetResource`) on a declared-but-malformed path/hash/source/entry (no new imports). The strict `read_datapackage` / `DataResource` is left untouched. The materializer's `_add_dataset_resource_edges` does **not** catch `DatasetResourceError` — a broken declared resource fails the build by design. `dataset_datapackage_path(*, entity_adapter, entity_path, datapackage_rel) -> Path | None` is called with the same three fields the geneset path already reads from `sources.entity_source_adapters` / `entity.file_path` / `sources.dataset_datapackages`. `DCAT_NS`/`DCTERMS_NS` imported from `science_tool.graph.io`; `SCI_NS`/`PROJECT_NS` from `science_tool.graph.store`; `PROV`/`RDF`/`XSD` from `rdflib.namespace` (all already in materialize.py). `_entity_uri` / `quote` reused. The Task 3 fixture uses `profiles: [science-pkg-entity-1.0]` + `id`/`type`/`title` so `DatapackageAdapter.discover` actually finds it.

**Consistency of the collision grade across surfaces** — after 2c, exactly one predicate (`IdentityCollision.is_genuine`) decides genuine-vs-transitional for the validate check, the graph audit (and thus every `has_failures` gate), and the migrator. The three can no longer diverge; the 2b "build gate still blocks a transitional shadow" caveat is resolved, not merely documented.

**Risk note** — Task 1 *relaxes* a gate: a transitional shadow stops blocking the strict build / freshness, and at those two call-sites a *genuine* duplicate now surfaces as a `ValueError` from the audit rather than an `EntityIdentityCollisionError` from the load (the strict-load API itself is unchanged and still raises — pinned by `test_strict_load_still_raises_on_stub_shadow`). This is the intended §C4 carry-transitional behavior and cannot let a genuine duplicate through (still blocked). Surface in the final report that any project previously bricked solely by a transitional aggregate-stub shadow will now build with a visible WARN — the desired mid-rollout ergonomics — and run the full suite (Step 12) to catch any test that assumed the old load-time raise. Task 3 is additive (new triples in a previously-empty named graph) plus one export-metadata registration so `dcat:downloadURL` does not become a spurious edge; lowest risk. The one new *failure* path it introduces is intended: a declared-but-malformed datapackage resource now raises `DatasetResourceError` out of materialization instead of being silently dropped. No existing fixture triggers it — the no-`resources` and hash-less fixtures are *absence* (still lenient), and real project datapackages (e.g. the mm30 canary) already passed the stricter commons-promotion `read_datapackage`, so their resources are well-formed. Step 12's full-suite run confirms nothing regresses; if a real datapackage ever does trip it, that surfaces a genuine data bug to fix, which is the point.

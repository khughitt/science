# Kernel Closure Phase 1 Plan: Tier 1 Retirement + Writer-Boundary Guard

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Design: [`2026-07-05-kernel-closure-writer-boundary-design.md`](2026-07-05-kernel-closure-writer-boundary-design.md)

**Goal:** Land the durable-writer boundary guard (the keystone of kernel closure), then retire the Tier 1 repo-dead / CLI-orphaned direct graph writers so the guard passes. After this phase, the only outstanding direct writers are the intentionally-deferred Tier 2 (`graph add *`) and Tier 3 (`import_snapshot`, `stamp_revision`, `migrate_addresses_direction`) sites, each explicitly enumerated in the guard's deferred-survivors ledger.

**Architecture:** A static AST-based guard test walks production modules, finds every call to `save_graph_dataset` / `_save_dataset`, resolves the enclosing function, and asserts the non-allowlisted call sites equal a frozen `EXPECTED_DEFERRED_WRITERS` ledger. The guard is authored RED (the 9 Tier 1 sites are present but not in the ledger); Tier 1 deletion turns it GREEN. Tests that previously constructed graph state through the orphaned inquiry mutators are migrated onto a single shared fixture that authors a `PatchDefinitionEntity` inquiry source and runs `graph build`, asserting against the honestly-compiled graph.

**Tech Stack:** Python 3.12, `ast`, pytest, existing `science_tool.graph.materialize` / `science_tool.dag`-style source fixtures.

---

## File Structure

- Create: `science/tests/graph/test_durable_write_boundary.py`
  - The guard test + the `EXPECTED_DEFERRED_WRITERS` ledger with per-site retirement-phase reasons.
- Create: `science/tests/graph/_inquiry_source_fixture.py` (or a fixture in `conftest.py` — implementer's choice, but centralized)
  - Shared helper: author a `PatchDefinitionEntity` inquiry source under `entities/patches/<slug>.md`, run `materialize_graph`, return the materialized dataset for assertions.
- Modify: `science/src/science_tool/graph/store/mutations.py`
  - Delete the 8 Tier 1 functions and their `_save_dataset` sites.
- Modify: `science/src/science_tool/graph/store/inquiry.py`
  - Delete `set_treatment_outcome` (line 177) and its `_save_dataset` site (line 207).
- Modify: `science/src/science_tool/graph/store/__init__.py` and `science/src/science_tool/graph/__init__.py`
  - Prune the deleted names from imports and `__all__`.
- Modify: `science/tests/test_inquiry.py`, `science/tests/test_causal.py`, `science/tests/test_graph_export.py`, `science/tests/test_meta_reference.py`
  - Migrate off the deleted mutators onto the shared source fixture.
- No design-doc edits are required during implementation unless review discovers a spec mismatch.

## Design Decisions Locked By This Plan

- **Guard granularity is `module:function`, not line number.** Line numbers shift when Tier 1 functions are deleted; the enclosing-function key is stable and reads as documentation.
- **The guard asserts the deferred set, not the empty set.** Tier 2/3 writers are legitimately still present after Phase 1, so `EXPECTED_DEFERRED_WRITERS` lists them (with a `phase:` reason each). The guard is the ratchet: a new unlisted writer OR a listed writer that disappears without a ledger edit both fail it.
- **The guard is authored RED and stays red until Task 5 (deletion) within this phase.** This is an intended within-phase red window on the feature branch; the branch does not merge until the guard is green. Tasks 1–4 leave it red by design.
- **Allowlist is exactly `{graph/materialize.py, graph/store/dataset.py}`** for this guard's scope (the two modules that legitimately call `save_graph_dataset` / `_save_dataset`). `composite.py`, `init_graph_file`, notebook scaffolding, and the belief-snapshot cache do not call these primitives and so do not appear; they are documented in the design's broader allowlist but are out of scope for this specific guard.
- **Tests migrate to source-built graphs, not mutation-built graphs.** Because the `sci:Inquiry` compat view is still emitted (Tier 4 is deferred), a materialized inquiry patch source still produces the `sci:Inquiry` triples the old tests asserted on — so the fixture path is viable now.
- **"Behavior-neutral" is scoped to source-built output.** The compiled `graph.trig` from `science graph build` over real/fixture sources is unchanged. Legacy tests that built graphs by direct mutation are intentionally replaced, not preserved byte-for-byte.

---

### Task 1: Author the Writer-Boundary Guard (RED)

**Files:**
- Create: `science/tests/graph/test_durable_write_boundary.py`

- [ ] **Step 1: Write the guard test and the deferred-writers ledger**

Create `science/tests/graph/test_durable_write_boundary.py`. The guard:

1. Enumerates production `.py` files under `src/science_tool/` (exclude anything under a `tests/` path).
2. Parses each with `ast`, finds every `ast.Call` whose function is a `Name`/`Attribute` named `save_graph_dataset` or `_save_dataset`, and resolves the enclosing `FunctionDef` (track parents during the walk).
3. Builds `actual = { f"{repo_rel_module}:{func_name}" }` for every such call NOT in the allowlist modules.
4. Asserts `actual == EXPECTED_DEFERRED_WRITERS`.

```python
from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "science_tool"
_WRITE_FUNCS = {"save_graph_dataset", "_save_dataset"}

# Modules that legitimately own durable graph writes.
_ALLOWLIST_MODULES = {
    "graph/materialize.py",       # compiler write phase — sole graph.trig owner
    "graph/store/dataset.py",     # defines/wraps the save primitive
}

# Direct writers that are KNOWN and intentionally deferred to a later kernel-closure
# phase. Every entry must carry a retirement phase. The guard fails if a site appears
# that is not listed here (regression) or a listed site disappears without editing
# this ledger (stale ledger). Tier 1 sites are deliberately ABSENT — their presence
# in code is what makes this guard RED until Task 5 deletes them.
EXPECTED_DEFERRED_WRITERS = {
    # Tier 2 — live `graph add *` mutators, retire in Phase 3 via _retired_mutator.
    "graph/store/mutations.py:add_concept",
    "graph/store/mutations.py:add_article",
    "graph/store/mutations.py:add_proposition",
    "graph/store/mutations.py:add_observation",
    "graph/store/mutations.py:add_evidence_edge",
    "graph/store/mutations.py:add_finding",
    "graph/store/mutations.py:add_interpretation",
    "graph/store/mutations.py:add_discussion",
    "graph/store/mutations.py:add_falsification",
    "graph/store/mutations.py:add_mechanism",
    "graph/store/mutations.py:add_story",
    "graph/store/mutations.py:add_paper_entity",
    "graph/store/mutations.py:add_hypothesis",
    "graph/store/mutations.py:add_question",
    "graph/store/mutations.py:add_edge",
    # Tier 3 — classify/retire in Phase 3.
    "graph/store/snapshot.py:import_snapshot",
    "graph/store/snapshot.py:stamp_revision",
}


def _enclosing_writer_sites() -> set[str]:
    sites: set[str] = set()
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_SRC).as_posix()
        if rel in _ALLOWLIST_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node  # type: ignore[attr-defined]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else None
            if name not in _WRITE_FUNCS:
                continue
            enclosing = node
            while enclosing is not None and not isinstance(enclosing, ast.FunctionDef):
                enclosing = getattr(enclosing, "parent", None)
            func_name = enclosing.name if isinstance(enclosing, ast.FunctionDef) else "<module>"
            sites.add(f"{rel}:{func_name}")
    return sites


def test_no_durable_graph_writer_outside_allowlist() -> None:
    actual = _enclosing_writer_sites()
    unexpected = actual - EXPECTED_DEFERRED_WRITERS
    stale = EXPECTED_DEFERRED_WRITERS - actual
    assert not unexpected, f"new direct graph writer(s) outside allowlist/ledger: {sorted(unexpected)}"
    assert not stale, f"ledger lists writer(s) that no longer exist — prune EXPECTED_DEFERRED_WRITERS: {sorted(stale)}"
```

- [ ] **Step 2: Run the guard and confirm it fails on the Tier 1 sites**

```bash
cd science
rtk uv run --frozen pytest tests/graph/test_durable_write_boundary.py -q
```

Expected: FAIL. The `unexpected` assertion fires listing exactly the 9 Tier 1 sites still in code:
`graph/store/mutations.py:add_inquiry`, `:set_boundary_role`, `:add_inquiry_node`, `:add_inquiry_edge`, `:add_assumption`, `:add_transformation`, `:add_data_package`, `:set_param_metadata`, and `graph/store/inquiry.py:set_treatment_outcome`. Record this failure list — it is the phase's proof that the guard catches the current boundary violation.

- [ ] **Step 3: Commit the guard (RED)**

```bash
rtk git add tests/graph/test_durable_write_boundary.py
rtk git commit -m "test(graph): add durable-writer boundary guard (red until Tier 1 retired)"
```

Note: the guard is intentionally red until Task 5. The branch must not merge until it is green.

---

### Task 2: External-Importer Preflight

**Files:**
- No code changes. This is a decision gate recorded in the commit message / phase notes.

- [ ] **Step 1: Grep for external importers of the Tier 1 names**

The Tier 1 names are re-exported through `graph/store/__init__.py` (and `add_data_package` etc. are `graph.store`-only, not in top-level `graph.__all__`). Confirm no code OUTSIDE this package imports them before deleting.

```bash
# Within the toolkit repo (excluding the graph package internals + tests that we will migrate):
cd /mnt/ssd/Dropbox/science/science
rtk grep -rn "add_inquiry\|add_inquiry_node\|add_inquiry_edge\|set_boundary_role\|add_assumption\|add_transformation\|set_param_metadata\|add_data_package\|set_treatment_outcome" src/ | grep -v "src/science_tool/graph/store/"
# Sibling repos that might import science_tool as a library rather than shell out to the CLI:
rtk grep -rn "add_inquiry\|add_data_package\|set_treatment_outcome\|set_param_metadata" ~/d/science-commons ~/d/science/meta 2>/dev/null
```

Expected: hits only in `graph/store/__init__.py` (the re-export) and the four test files named in Task 4. If any external importer exists, STOP and escalate: this becomes a documented breaking change and the deletion needs a deprecation note. If not, deletion is clean.

- [ ] **Step 2: Record the outcome**

Note the preflight result in the phase notes (clean vs. escalated). No commit unless escalation adds a deprecation note somewhere.

---

### Task 3: Centralized Inquiry-Source Test Fixture

**Files:**
- Create: `science/tests/graph/_inquiry_source_fixture.py` (or `conftest.py` fixture)

- [ ] **Step 1: Write a helper that builds inquiry state from source**

Create one shared helper that: writes a minimal project manifest, authors an `entities/patches/<slug>.md` `PatchDefinitionEntity` with `patch_type: inquiry` (nodes, edges, assumptions, treatment/outcome expressed as the authored inquiry profile), runs `materialize_graph`, and returns the materialized dataset. Model the manifest/authoring on the existing patch/inquiry source tests (grep `patch_type: inquiry` and existing `materialize_graph` test callers for the current authored schema).

```python
from __future__ import annotations

from pathlib import Path

from science_tool.graph.materialize import materialize_graph


def build_inquiry_project(tmp_path: Path, *, slug: str, patch_markdown: str) -> "Dataset":
    project = tmp_path / "project"
    (project / "entities/patches").mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    (project / "entities/patches" / f"{slug}.md").write_text(patch_markdown, encoding="utf-8")
    return materialize_graph(project)  # returns the compiled Dataset with sci:Inquiry views
```

The exact `patch_markdown` schema must be copied from a current passing inquiry-source test, not invented. If no such test exists, derive it from `graph/inquiry_compile.py` (`emit_inquiry_views`) and the `PatchDefinitionEntity` inquiry profile fields.

- [ ] **Step 2: Prove the fixture emits the sci:Inquiry view**

Add one test asserting the materialized dataset contains the `sci:Inquiry` type triple and the inquiry's nodes/edges, so downstream migrations have a trusted baseline.

```bash
cd science
rtk uv run --frozen pytest tests/graph/ -q -k inquiry_source
```

Expected: PASS (the compat view still exists; Tier 4 is deferred).

- [ ] **Step 3: Commit the fixture**

```bash
rtk git add tests/graph/_inquiry_source_fixture.py tests/graph/
rtk git commit -m "test(graph): add source-built inquiry fixture for boundary migration"
```

---

### Task 4: Migrate the Four Test Files onto the Fixture

**Files:**
- Modify: `science/tests/test_inquiry.py`, `science/tests/test_causal.py`, `science/tests/test_graph_export.py`, `science/tests/test_meta_reference.py`

- [ ] **Step 1: Replace mutator-built setup with the source fixture**

For each file, replace `add_inquiry* / set_boundary_role / add_assumption / add_transformation / set_param_metadata / set_treatment_outcome` construction with `build_inquiry_project(...)`, and repoint assertions at the materialized dataset. `test_causal.py` has the heaviest setup — expect the bulk of this task there; convert it to a small number of authored inquiry sources rather than many per-triple mutations.

- [ ] **Step 2: Run the migrated tests (guard still red — that is expected)**

```bash
cd science
rtk uv run --frozen pytest tests/test_inquiry.py tests/test_causal.py tests/test_graph_export.py tests/test_meta_reference.py -q
```

Expected: PASS. The migrated tests no longer import the Tier 1 mutators. The boundary guard is still RED at this point (the mutators still exist in `mutations.py` / `inquiry.py`); that flips in Task 5.

- [ ] **Step 3: Commit the migration**

```bash
rtk git add tests/test_inquiry.py tests/test_causal.py tests/test_graph_export.py tests/test_meta_reference.py
rtk git commit -m "test(graph): build inquiry test state from source, not direct mutators"
```

---

### Task 5: Delete Tier 1 Writers + Prune `__all__` (Guard → GREEN)

**Files:**
- Modify: `science/src/science_tool/graph/store/mutations.py`
- Modify: `science/src/science_tool/graph/store/inquiry.py`
- Modify: `science/src/science_tool/graph/store/__init__.py`
- Modify: `science/src/science_tool/graph/__init__.py`

- [ ] **Step 1: Delete the 9 Tier 1 functions**

From `mutations.py`: `add_inquiry`, `set_boundary_role`, `add_inquiry_node`, `add_inquiry_edge`, `add_assumption`, `add_transformation`, `add_data_package`, `set_param_metadata`. From `store/inquiry.py`: `set_treatment_outcome`. Also delete any now-orphaned private helper reachable ONLY from these (check `_attach_edge_claims` — it is still used by `add_edge` and must stay; confirm before removing anything).

- [ ] **Step 2: Prune the exports**

Remove all 9 names from `graph/store/__init__.py` (imports + any `__all__`) and from `graph/__init__.py` (imports + `__all__`) if present. Run a grep to confirm no dangling reference:

```bash
cd science
rtk grep -rn "add_inquiry\|add_inquiry_node\|add_inquiry_edge\|set_boundary_role\|add_assumption\|add_transformation\|set_param_metadata\|add_data_package\|set_treatment_outcome" src/
```

Expected: no matches in `src/` (all definitions and re-exports gone). If the retired inquiry CLI stubs referenced these symbols, confirm they only reference `_retired_mutator`, not the deleted functions.

- [ ] **Step 3: Run the guard — now GREEN**

```bash
cd science
rtk uv run --frozen pytest tests/graph/test_durable_write_boundary.py -q
```

Expected: PASS. `actual` now equals `EXPECTED_DEFERRED_WRITERS` exactly (18 deferred Tier 2/3 sites, zero Tier 1). This is the phase's crisp proof: the guard caught the old violation, and deletion made it pass.

- [ ] **Step 4: Commit the deletion**

```bash
rtk git add src/science_tool/graph/store/mutations.py src/science_tool/graph/store/inquiry.py src/science_tool/graph/store/__init__.py src/science_tool/graph/__init__.py
rtk git commit -m "refactor(graph): retire orphaned Tier 1 direct graph writers"
```

---

### Task 6: Full Verification

**Files:**
- No planned changes unless verification uncovers issues.

- [ ] **Step 1: Full focused + suite verification**

```bash
cd science
rtk uv run --frozen pytest tests/graph/test_durable_write_boundary.py tests/test_inquiry.py tests/test_causal.py tests/test_graph_export.py tests/test_meta_reference.py -q
rtk uv run --frozen pytest -q      # full suite: nothing else depended on the deleted writers
```

Expected: PASS. If any non-migrated test imported a deleted writer, migrate it onto the fixture (do not resurrect the writer).

- [ ] **Step 2: Lint + types on touched files**

```bash
cd science
rtk uv run --frozen ruff check src/science_tool/graph/store/mutations.py src/science_tool/graph/store/inquiry.py src/science_tool/graph/store/__init__.py src/science_tool/graph/__init__.py tests/graph/test_durable_write_boundary.py
rtk uv run --frozen pyright src/science_tool/graph/store/mutations.py src/science_tool/graph/store/inquiry.py
```

Expected: PASS.

- [ ] **Step 3: Request code review**

Use `superpowers:requesting-code-review`. Focus reviewers on: guard correctness (does the AST walk miss any call form, e.g. an aliased import of `_save_dataset`?), the ledger's honesty (are all 18 deferred sites real and phase-tagged?), and the test migration (do the source-built tests assert the same properties the mutation-built ones did?).

- [ ] **Step 4: Prepare merge**

Use `superpowers:finishing-a-development-branch`. The guard must be green before merge.

## Acceptance Checklist

- [ ] The boundary guard fails when any production module outside `{materialize.py, store/dataset.py}` calls `save_graph_dataset`/`_save_dataset` and the site is not in `EXPECTED_DEFERRED_WRITERS`.
- [ ] The guard was demonstrably RED against the 9 Tier 1 sites before deletion and GREEN after (recorded in Task 1 Step 2 and Task 5 Step 3).
- [ ] `EXPECTED_DEFERRED_WRITERS` lists exactly the 18 Tier 2/3 sites, each with a retirement-phase reason; no Tier 1 site remains.
- [ ] `add_data_package` and the 8 orphaned inquiry writers are deleted from source and pruned from every `__all__`.
- [ ] The four migrated test files build inquiry state via the shared source fixture and `materialize_graph`, not via direct mutators.
- [ ] The external-importer preflight was run and recorded (clean, or escalated to a documented breaking change).
- [ ] Full pytest suite, ruff, and pyright pass.
- [ ] No change to `graph.trig` compiled from real/fixture sources via `science graph build` (behavior-neutral for source-built output).

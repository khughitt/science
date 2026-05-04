# Phase 1 Polish (t013) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the 9 follow-up items from the final code review of `feature/epistemic-dependency-graph` (`meta/tasks/active.md` `[t013]`) so Phase 2 (weighted sampling) can build on a tightened Phase 1 surface.

**Architecture:** All work is additive to existing modules — no new top-level subsystems. Touches:
- `science-model`: `Entity.review_state` validator, `bears_on` `target_kinds` expansion.
- `science-tool`: registry threading through `ProjectSources`, audit gate parity, two new derivation triples (`sci:lastReviewed`, `sci:bearsOnDepth`), `freshness.enabled` opt-out, `entity review` epistemic gate.
- Tests: integration coverage gaps, boundary tests for `derive_freshness`.

**Tech Stack:** Pydantic v2, rdflib, click, pytest. TDD via `uv run --frozen --directory <pkg> pytest <args>`.

---

## File Structure

| Module | File | Responsibility |
| --- | --- | --- |
| science-model | `src/science_model/entities.py` | Entity-level validator on `review_state` |
| science-model | `src/science_model/profiles/core.py` | Expanded `bears_on.target_kinds` |
| science-model | `tests/test_review_state_model.py` | Validator boundary tests |
| science-model | `tests/test_bears_on_relation.py` | Reconciliation assertion |
| science-tool | `src/science_tool/graph/sources.py` | Build + expose registry on `ProjectSources` |
| science-tool | `src/science_tool/graph/materialize.py` | Consume `sources.registry` in `_classify_entities`; emit prep triples |
| science-tool | `src/science_tool/graph/freshness.py` | `sci:lastReviewed`, `sci:bearsOnDepth` emission; closure depth tracking; opt-out gate |
| science-tool | `src/science_tool/entity_review.py` | Reject non-epistemic targets at CLI |
| science-tool | `src/science_tool/cli.py` | Pass `kind_class` to `review_entity`; route `ReviewError` |
| science-tool | tests | New + boundary tests |

---

## Closed list of clearly-not-epistemic core kinds

The Task 1 validator must reject `review_state` on these kinds. List was supplied by the reviewer; double-checked against `_CORE_KIND_CLASSES` in `entity_registry.py`:

```
{"task", "dataset", "workflow-run", "data-package", "paper", "experiment"}
```

All six map to `EntityClass.OPERATIONAL`. Other operational kinds (`workflow`, `workflow-step`, `method`, `transformation`, `plan`, `search`, `spec`, `curation-sweep`) are *not* in the closed list — leaving headroom for projects that want to mark a `plan` or `method` for review without registry coupling. This stays at the science-model layer; the registry-aware version is the CLI gate (Task 3).

---

## Reconciliation list for `bears_on.target_kinds`

Today the relation declares 9 targets; the runtime classifies 4 more as `EntityClass.EPISTEMIC`. The implementer must:

1. Read `_CORE_KIND_CLASSES` in `science-tool/src/science_tool/graph/entity_registry.py`.
2. For each kind classified `EPISTEMIC`, ensure it appears in `bears_on.target_kinds`.
3. Expected additions: `assumption`, `report`, `validation-report`. (`model` is **not** in `_CORE_KIND_CLASSES` — the reviewer's note included it incorrectly. Do not add it.)

The test asserts equality between `set(bears_on.target_kinds)` and the EPISTEMIC subset of `_CORE_KIND_CLASSES`. This makes future drift a hard test failure rather than silent.

---

## Task 1: `review_state` validator on Entity

**Files:**
- Modify: `science-model/src/science_model/entities.py` (around line 202 — `review_state` field on `Entity`)
- Modify: `science-model/tests/test_review_state_model.py` (extend with new test class)

- [ ] **Step 1: Write the failing tests**

In `science-model/tests/test_review_state_model.py`, append:

```python
import pytest
from pydantic import ValidationError

from science_model.entities import Entity, EpistemicReviewState

NON_EPISTEMIC_KINDS = ["task", "dataset", "workflow-run", "data-package", "paper", "experiment"]


def _baseline_kwargs(kind: str) -> dict:
    return {
        "id": f"{kind}:t",
        "kind": kind,
        "title": "T",
        "project": "p",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "x.md",
    }


@pytest.mark.parametrize("kind", NON_EPISTEMIC_KINDS)
def test_review_state_rejected_on_non_epistemic_kinds(kind: str) -> None:
    rs = EpistemicReviewState(last_reviewed=None)
    with pytest.raises(ValidationError, match="review_state"):
        Entity(**_baseline_kwargs(kind), review_state=rs)


@pytest.mark.parametrize("kind", NON_EPISTEMIC_KINDS)
def test_no_review_state_still_valid_on_non_epistemic_kinds(kind: str) -> None:
    Entity(**_baseline_kwargs(kind))


def test_review_state_allowed_on_open_kinds() -> None:
    # Kinds outside the closed list (incl. extension kinds) keep accepting review_state.
    rs = EpistemicReviewState(last_reviewed=None)
    Entity(**_baseline_kwargs("hypothesis"), review_state=rs)
    Entity(**_baseline_kwargs("custom-extension-kind"), review_state=rs)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --frozen --directory science-model pytest tests/test_review_state_model.py -v
```

Expected: 13 failures on the new tests (12 reject cases + nothing for the allowed cases — actually the reject cases fail because no validator exists yet; the "no review_state" and "allowed" cases pass without changes).

- [ ] **Step 3: Implement the validator**

In `science-model/src/science_model/entities.py`, just below the `review_state: EpistemicReviewState | None = None` field (still inside `class Entity`), add:

```python
    @model_validator(mode="after")
    def _validate_review_state_kind(self) -> "Entity":
        # Closed list of clearly-non-epistemic core kinds. Avoids registry
        # coupling at the science-model layer while still rejecting the
        # high-confidence cases.
        non_epistemic = {
            "task",
            "dataset",
            "workflow-run",
            "data-package",
            "paper",
            "experiment",
        }
        if self.review_state is not None and self.kind in non_epistemic:
            raise ValueError(
                f"review_state is not allowed on kind {self.kind!r} "
                f"(non-epistemic by design)"
            )
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run --frozen --directory science-model pytest tests/test_review_state_model.py -v
```

Expected: all pass.

- [ ] **Step 5: Run the full suite to confirm nothing regressed**

```bash
uv run --frozen --directory science-model pytest -q
```

Expected: 283 + 13 (the new ones) = 296 passing.

- [ ] **Step 6: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/tests/test_review_state_model.py
git commit -m "feat(model): reject review_state on closed list of non-epistemic kinds"
```

---

## Task 2: Reconcile `bears_on.target_kinds` with EPISTEMIC classification

**Files:**
- Modify: `science-model/src/science_model/profiles/core.py` (around line 252-275)
- Modify: `science-model/tests/test_bears_on_relation.py` (replace the test that asserts a hardcoded list with one that asserts equality with the registry's EPISTEMIC subset)

- [ ] **Step 1: Read both files to find anchors**

```bash
uv run --frozen --directory science-model pytest tests/test_bears_on_relation.py -v
```

Note the existing test name(s).

- [ ] **Step 2: Update `bears_on.target_kinds`**

In `science-model/src/science_model/profiles/core.py`, change the `target_kinds` block of the `bears_on` `RelationKind` to (alphabetized, four new entries):

```python
            target_kinds=[
                "assumption",
                "discussion",
                "finding",
                "hypothesis",
                "interpretation",
                "mechanism",
                "observation",
                "proposition",
                "question",
                "report",
                "story",
                "validation-report",
            ],
```

- [ ] **Step 3: Add a coupling test in `science-model/tests/test_bears_on_relation.py`**

Append (or replace the existing list-equality test, whichever exists):

```python
def test_bears_on_targets_match_target_kinds_exactly() -> None:
    # Phase 1 polish (t013 #5): the relation must enumerate every kind that
    # the freshness engine will treat as EPISTEMIC. Drift here is a silent
    # bug — assert exact equality with the closed list.
    from science_model.profiles.core import CORE_PROFILE
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    expected = {
        "assumption",
        "discussion",
        "finding",
        "hypothesis",
        "interpretation",
        "mechanism",
        "observation",
        "proposition",
        "question",
        "report",
        "story",
        "validation-report",
    }
    assert set(bears_on.target_kinds) == expected
```

- [ ] **Step 4: Run model + tool test suites**

```bash
uv run --frozen --directory science-model pytest -q
uv run --frozen --directory science-tool pytest -q
```

Expected: all pass. The science-tool side already classifies these as EPISTEMIC, so derivation already accepts them — we're only making the relation declaration honest.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/profiles/core.py science-model/tests/test_bears_on_relation.py
git commit -m "fix(model): expand bears_on.target_kinds to match EPISTEMIC classification"
```

---

## Task 3: `entity review` rejects non-epistemic targets at CLI

**Files:**
- Modify: `science-tool/src/science_tool/entity_review.py`
- Modify: `science-tool/src/science_tool/cli.py` (the `entity review` click command)
- Modify: `science-tool/tests/test_entity_review_cli.py`

- [ ] **Step 1: Write the failing test**

The existing test file uses `_setup_project_with_hypothesis(tmp_path)` (line 16). Append a sibling helper and a test:

```python
def _setup_project_with_dataset(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "knowledge" / "datasets").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n")
    (root / "knowledge" / "datasets" / "d1.md").write_text(
        dedent(
            """
            ---
            id: "dataset:d1"
            kind: "dataset"
            title: "Demo dataset"
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            Body.
            """
        ).lstrip()
    )
    return root


def test_entity_review_rejects_non_epistemic_target(tmp_path: Path, monkeypatch):
    root = _setup_project_with_dataset(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "dataset:d1"])
    assert result.exit_code != 0, result.output
    assert "non-epistemic" in result.output.lower() or "operational" in result.output.lower()
```

(If the canonical `dataset` location is not `knowledge/datasets/` per the project's policies, mirror whatever path `materialize.py` accepts for dataset entities; the existing test fixtures use whichever path is canonical.)

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run --frozen --directory science-tool pytest tests/test_entity_review_cli.py::test_entity_review_rejects_non_epistemic_target -v
```

Expected: FAIL — `entity review dataset:demo` succeeds today.

- [ ] **Step 3: Add the gate in `entity_review.py`**

Modify `review_entity()` to consult the registry. Add this import near the existing imports:

```python
from science_model.entities import EntityClass
from science_tool.graph.entity_registry import EntityRegistry
```

Then, immediately after the `find_entity()` call (around line 55), insert:

```python
    registry = EntityRegistry.with_core_types()
    try:
        kind_class = registry.kind_class(location.entity.kind)
    except Exception:
        kind_class = None  # extension kinds default to allowed
    if kind_class is not None and kind_class != EntityClass.EPISTEMIC:
        raise ReviewError(
            f"entity {entity_ref!r} has kind {location.entity.kind!r} "
            f"({kind_class.value}); review_state is only meaningful on epistemic entities"
        )
```

(Use the existing `EntityCommandError`/`ReviewError` plumbing — no new exception class.)

If `location.entity` doesn't expose `.kind` directly, derive from `location.frontmatter["kind"]` instead. Confirm by reading `find_entity`'s return type before writing.

- [ ] **Step 4: Run the failing test again**

```bash
uv run --frozen --directory science-tool pytest tests/test_entity_review_cli.py -v
```

Expected: PASS for the new test; the existing happy-path tests still pass (they use epistemic kinds).

- [ ] **Step 5: Run the full suite**

```bash
uv run --frozen --directory science-tool pytest -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/entity_review.py science-tool/tests/test_entity_review_cli.py
git commit -m "feat(cli): entity review rejects non-epistemic targets"
```

---

## Task 4: Thread the project's full registry through `ProjectSources`

**Why:** Today `_classify_entities` builds a fresh `EntityRegistry.with_core_types()` per call, so profile/catalog/extension kinds always default to `OPERATIONAL`. Threading the registry built in `load_project_sources` (which knows about profile, catalog, and extension kinds) makes per-project classification correct.

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py` (add field on `ProjectSources`; populate at end of `load_project_sources`)
- Modify: `science-tool/src/science_tool/graph/materialize.py` (`_classify_entities` consumes `sources.registry`)
- Modify: `science-tool/tests/test_kind_class.py` or a new test file

- [ ] **Step 1: Write the failing integration test**

Create `science-tool/tests/test_extension_kind_classification.py`:

```python
"""Verify that extension kinds with declared epistemic class flow through
materialize_graph end-to-end (regression for t013 #3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_model.entities import EntityClass
from science_tool.graph.entity_registry import EntityRegistry


def test_project_sources_registry_classifies_extension_kinds(tmp_path: Path) -> None:
    # Use the load_project_sources path with an extension kind manifest.
    # Implementer: model on the existing extension-kind tests in tests/ —
    # whichever fixture writes a profile manifest with an extra entity_kind.
    # If no such fixture exists yet, create one inline that:
    #   - writes a science.yaml with knowledge_profiles.local = "ext"
    #   - writes knowledge/sources/ext/manifest.yaml declaring an entity_kind
    #     named "custom-belief" with entity_class: epistemic
    #   - writes one knowledge/sources/ext/<...>/foo.md with kind=custom-belief
    project_root = _build_extension_project(tmp_path)  # implementer: see below
    from science_tool.graph.sources import load_project_sources
    sources = load_project_sources(project_root)
    assert sources.registry.kind_class("custom-belief") == EntityClass.EPISTEMIC
```

The fixture builder `_build_extension_project` should reuse existing helpers if any (`grep -rn "register_extension_kind\|entity_class:" science-tool/tests/`); otherwise implement it directly with `Path.write_text`. Keep it minimal — one entity, one extension kind.

- [ ] **Step 2: Run to verify it fails**

```bash
uv run --frozen --directory science-tool pytest tests/test_extension_kind_classification.py -v
```

Expected: FAIL — `ProjectSources` has no `registry` field today.

- [ ] **Step 3: Add `registry` field to `ProjectSources`**

In `science-tool/src/science_tool/graph/sources.py`:

1. Add the import (it's already imported as `EntityRegistry` — confirm).
2. Add to the `ProjectSources` class body:

```python
    registry: EntityRegistry
```

3. Update the final `return ProjectSources(...)` block in `load_project_sources` to pass `registry=registry`.

4. Update the `model_config` if needed — `EntityRegistry` isn't a Pydantic model, but `arbitrary_types_allowed` is already set, so no change needed.

5. The manifest declares `entity_class` for extension kinds — confirm by reading `science-model/src/science_model/profiles/manifest.py` (or equivalent) and updating the `register_extension_kind` call site if needed:

```python
    if local_profile_manifest is not None:
        for entity_kind in local_profile_manifest.entity_kinds:
            registry.register_extension_kind(
                entity_kind.name,
                ProjectEntity,
                entity_class=_resolve_extension_class(entity_kind),  # implementer: read manifest
            )
```

If the manifest currently has no `entity_class` field, add it as optional `EntityClass | None = None` defaulting to `EntityClass.OPERATIONAL` (with a model-side test for the new field — keep it small).

- [ ] **Step 4: Update `_classify_entities` to consume `sources.registry`**

In `science-tool/src/science_tool/graph/materialize.py`:

```python
def _classify_entities(sources: ProjectSources) -> dict[str, EntityClass]:
    """Build a {URI string -> EntityClass} map from the project's entities.

    Uses the registry built by load_project_sources, which knows about profile,
    catalog, and extension kinds. Unregistered kinds default to OPERATIONAL.
    """
    kind_class: dict[str, EntityClass] = {}
    for entity in sources.entities:
        uri_str = str(_entity_uri(entity.canonical_id))
        try:
            kind_class[uri_str] = sources.registry.kind_class(entity.kind)
        except EntityKindNotRegisteredError:
            kind_class[uri_str] = EntityClass.OPERATIONAL
    return kind_class
```

Remove the now-unused `EntityRegistry.with_core_types()` import line if it was only used for this function.

- [ ] **Step 5: Run the failing test + suite**

```bash
uv run --frozen --directory science-tool pytest tests/test_extension_kind_classification.py -v
uv run --frozen --directory science-tool pytest -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/sources.py science-tool/src/science_tool/graph/materialize.py science-tool/tests/test_extension_kind_classification.py
git commit -m "feat(graph): thread project registry through ProjectSources for kind classification"
```

(Include the manifest change in the commit if Step 3 required one.)

---

## Task 5: Audit-gate parity for `propagate_freshness_in_memory`

**Why:** `materialize_graph` raises on unresolved refs (so a project with broken refs can't silently materialize). `propagate_freshness_in_memory` skips that gate, so the sweep silently produces a partial picture.

**Decision:** Share the gate. `propagate-freshness` is read-only on the filesystem but should be honest about completeness — running it on a project with broken refs should raise the same `ValueError` so the user fixes the refs first.

**Files:**
- Modify: `science-tool/src/science_tool/graph/freshness.py` (`propagate_freshness_in_memory`)
- Modify: `science-tool/tests/test_graph_propagate_freshness_cli.py`

- [ ] **Step 1: Write the failing test**

In `science-tool/tests/test_graph_propagate_freshness_cli.py`, append:

```python
def test_propagate_freshness_raises_on_unresolved_refs(tmp_path: Path) -> None:
    # Build a project with a hypothesis whose source_refs points at a missing entity.
    # Reuse whichever helper builds the smallest valid project in this test file.
    project_root = _build_project_with_unresolved_ref(tmp_path)  # implementer: see below
    from science_tool.graph.freshness import propagate_freshness_in_memory
    with pytest.raises(ValueError, match="unresolved references"):
        propagate_freshness_in_memory(project_root)
```

`_build_project_with_unresolved_ref` should add an entity whose `source_refs` cite `hypothesis:does-not-exist`. Reuse existing fixture helpers if any.

- [ ] **Step 2: Run to verify it fails**

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_propagate_freshness_cli.py::test_propagate_freshness_raises_on_unresolved_refs -v
```

Expected: FAIL — currently produces an empty rows list silently.

- [ ] **Step 3: Add the gate**

In `science-tool/src/science_tool/graph/freshness.py`, modify `propagate_freshness_in_memory`:

```python
def propagate_freshness_in_memory(project_root: Path) -> list[dict]:
    """Compute freshness without writing the materialized graph.

    Same audit gate as `materialize_graph`: raises ValueError if any
    source_refs / evidence_refs / typed-relation reference is unresolved.
    Without this, a project with broken refs would silently produce an
    incomplete freshness picture.
    """
    # Lazy imports to avoid cycle.
    from science_tool.graph.materialize import _build_dataset_from_sources
    from science_tool.graph.migrate import audit_project_sources

    sources = load_project_sources(project_root.resolve())
    rows, has_failures = audit_project_sources(sources)
    if has_failures:
        details = "; ".join(f"{row['source']} -> {row['target']}" for row in rows if row["status"] == "fail")
        raise ValueError(f"Cannot compute freshness with unresolved references: {details}")

    dataset = _build_dataset_from_sources(sources)
    # ... rest unchanged ...
```

- [ ] **Step 4: Run tests**

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_propagate_freshness_cli.py -v
uv run --frozen --directory science-tool pytest -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/freshness.py science-tool/tests/test_graph_propagate_freshness_cli.py
git commit -m "fix(graph): propagate-freshness reuses materialize_graph's audit gate"
```

---

## Task 6: Emit `sci:lastReviewed` per epistemic entity

**Why:** Phase 2 sampling will weight by review age. Today that requires re-parsing markdown frontmatter; emitting the triple in Phase 1 is ~3 lines and zero-cost.

**Files:**
- Modify: `science-tool/src/science_tool/graph/freshness.py` (`derive_freshness`)
- Modify: `science-tool/tests/test_freshness_derivation.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_freshness_derivation.py`:

```python
def test_derive_freshness_emits_last_reviewed_triple() -> None:
    # Build minimal dataset with one epistemic entity that has last_reviewed.
    from datetime import date
    from rdflib import Dataset, Literal, URIRef
    from rdflib.namespace import XSD
    from science_model.entities import EntityClass
    from science_tool.graph.freshness import derive_freshness
    from science_tool.graph.store import PROJECT_NS, SCI_NS

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    entities = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 1, 15),
            "created": date(2025, 1, 1),
            "updated": None,
            "review_horizon_days": None,
        }
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 4))

    triples = list(knowledge.triples((h, SCI_NS.lastReviewed, None)))
    assert triples == [(h, SCI_NS.lastReviewed, Literal("2026-01-15", datatype=XSD.date))]


def test_derive_freshness_no_last_reviewed_triple_when_unset() -> None:
    from datetime import date
    from rdflib import Dataset, URIRef
    from science_model.entities import EntityClass
    from science_tool.graph.freshness import derive_freshness
    from science_tool.graph.store import PROJECT_NS, SCI_NS

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    entities = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": None,
            "created": date(2025, 1, 1),
            "updated": None,
            "review_horizon_days": None,
        }
    }
    derive_freshness(ds, entities=entities, today=date(2026, 5, 4))
    assert list(knowledge.triples((h, SCI_NS.lastReviewed, None))) == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
uv run --frozen --directory science-tool pytest tests/test_freshness_derivation.py -k last_reviewed -v
```

Expected: 2 FAIL.

- [ ] **Step 3: Emit the triple**

In `science-tool/src/science_tool/graph/freshness.py`, inside the `derive_freshness` per-entity loop, after the existing `freshnessState` triple emission:

```python
        # Phase 2 prep: emit last_reviewed when set so sampling can read it
        # from the graph instead of re-parsing markdown frontmatter.
        last_reviewed = info.get("last_reviewed")
        if last_reviewed is not None:
            knowledge.add((
                entity_uri,
                SCI_NS.lastReviewed,
                Literal(last_reviewed.isoformat(), datatype=XSD.date),
            ))
```

Place it after the `freshnessState` emission and before the `triggeredBy` loop.

- [ ] **Step 4: Run tests**

```bash
uv run --frozen --directory science-tool pytest tests/test_freshness_derivation.py -v
uv run --frozen --directory science-tool pytest -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/freshness.py science-tool/tests/test_freshness_derivation.py
git commit -m "feat(graph): emit sci:lastReviewed for Phase 2 sampling"
```

---

## Task 7: Track `bears_on` depth in transitive closure

**Why:** Phase 2 attention can weight directness if depth is in the graph. Today closure emits flat `bears_on` triples.

**Decision:** Emit `sci:bearsOnDepth` as a separate triple keyed on `(source, target)` carrying the **minimum** depth across all paths. Direct edges (typed/provenance) are depth 1; closure edges are depth 2+.

**Files:**
- Modify: `science-tool/src/science_tool/graph/freshness.py` (`close_bears_on`; also annotate the direct edges in `derive_bears_on_from_typed_edges` and `derive_bears_on_from_provenance` with depth 1)
- Modify: `science-tool/tests/test_bears_on_derivation.py`

- [ ] **Step 1: Write the failing tests**

The existing test file already provides `_u(local)`, `_make_dataset_with(triples)`, and `_bears_on_pairs(ds)`. Add a helper for depth lookup and three depth tests:

```python
def _bears_on_depth(ds: Dataset, source: URIRef, target: URIRef) -> int | None:
    """Return the minimum sci:bearsOnDepth for (source, target), or None if no edge."""
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    depths: list[int] = []
    for bn, _, _ in knowledge.triples((None, RDF.type, SCI_NS.BearsOnEdge)):
        if (bn, SCI_NS.bearsOnSource, source) in knowledge and (bn, SCI_NS.bearsOnTarget, target) in knowledge:
            for _, _, d in knowledge.triples((bn, SCI_NS.bearsOnDepth, None)):
                depths.append(int(d))
    return min(depths) if depths else None


def test_direct_typed_edge_has_depth_one():
    h = _u("hypothesis/h1"); t = _u("task/t1")
    ds = _make_dataset_with([(t, SCI_NS.tests, h)])
    derive_bears_on_from_typed_edges(ds, kind_class={str(t): EntityClass.OPERATIONAL, str(h): EntityClass.EPISTEMIC})
    assert _bears_on_depth(ds, t, h) == 1


def test_closure_emits_minimum_depth_through_chain():
    # workflow-run grounds observation; observation supports hypothesis.
    # Closure: workflow-run bears_on hypothesis at depth 2.
    wr = _u("workflow-run/w1"); o = _u("observation/o1"); h = _u("hypothesis/h1")
    ds = _make_dataset_with([(wr, SCI_NS.grounds, o), (o, CITO_NS.supports, h)])
    kc = {str(wr): EntityClass.OPERATIONAL, str(o): EntityClass.EPISTEMIC, str(h): EntityClass.EPISTEMIC}
    derive_bears_on_from_typed_edges(ds, kind_class=kc)
    close_bears_on(ds, kind_class=kc)
    assert _bears_on_depth(ds, wr, o) == 1
    assert _bears_on_depth(ds, wr, h) == 2


def test_closure_diamond_takes_minimum_depth():
    # A -> B -> D (depth 2); A -> C -> X -> D (depth 3 via three hops). Min should be 2.
    a = _u("workflow-run/a"); b = _u("observation/b"); c = _u("observation/c")
    x = _u("observation/x"); d = _u("hypothesis/d")
    ds = _make_dataset_with([
        (a, SCI_NS.grounds, b), (b, CITO_NS.supports, d),
        (a, SCI_NS.grounds, c), (c, CITO_NS.supports, x), (x, CITO_NS.supports, d),
    ])
    kc = {
        str(a): EntityClass.OPERATIONAL,
        str(b): EntityClass.EPISTEMIC, str(c): EntityClass.EPISTEMIC,
        str(x): EntityClass.EPISTEMIC, str(d): EntityClass.EPISTEMIC,
    }
    derive_bears_on_from_typed_edges(ds, kind_class=kc)
    close_bears_on(ds, kind_class=kc)
    assert _bears_on_depth(ds, a, d) == 2
```

Add the imports (`from rdflib.namespace import RDF`, `EntityClass`, etc.) at the top of the file as needed.

- [ ] **Step 2: Decide on the triple shape**

We have two options:
- **(a)** A simple data property: `(source, sci:bearsOnDepth_<target>, depth)` — won't work because predicates can't be parameterized.
- **(b)** RDF reification — heavyweight.
- **(c)** A keyed pair: emit a fresh blank node `bn` such that `bn rdf:type sci:BearsOnEdge; sci:bearsOnSource source; sci:bearsOnTarget target; sci:bearsOnDepth depth`. Phase 2 can SELECT-WHERE on it.

Use **(c)**. It's slightly more verbose but is the only shape that lets Phase 2 query depth without RDF-reification gymnastics.

- [ ] **Step 3: Implement direct-edge depth (= 1)**

In `derive_bears_on_from_typed_edges` and `derive_bears_on_from_provenance`, every time you call `knowledge.add((s, SCI_NS.bearsOn, o))`, also call a new helper:

```python
def _emit_bears_on_edge(knowledge, source: URIRef, target: URIRef, depth: int) -> None:
    bn = BNode()
    knowledge.add((bn, RDF.type, SCI_NS.BearsOnEdge))
    knowledge.add((bn, SCI_NS.bearsOnSource, source))
    knowledge.add((bn, SCI_NS.bearsOnTarget, target))
    knowledge.add((bn, SCI_NS.bearsOnDepth, Literal(depth, datatype=XSD.integer)))
```

Call it with `depth=1` for typed/provenance edges.

- [ ] **Step 4: Implement closure depth (≥ 2)**

In `close_bears_on`, the existing DFS already tracks the path implicitly (stack length). Restructure the DFS so each stack entry is `(node, depth)`. When emitting a closure target, also call `_emit_bears_on_edge(... depth=current_depth)`. Track minimum depth per `(source, target)` to handle diamonds — use a dict keyed on `(source, target)` instead of the current `set` for `new_triples`, then emit edges from that dict.

(Direct edges already in the graph at depth 1 take precedence — the closure only emits when its derived depth is strictly less than any direct depth, but since direct is 1 and closure is ≥ 2, direct always wins. Implementer should still make this explicit by checking `if not _direct_edge_exists(source, target)` before emitting closure depth, OR just emit closure depth always and let Phase 2 take `MIN(?d)` in SPARQL. Pick the simpler choice and document it.)

- [ ] **Step 5: Run tests**

```bash
uv run --frozen --directory science-tool pytest tests/test_bears_on_derivation.py -v
uv run --frozen --directory science-tool pytest -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/freshness.py science-tool/tests/test_bears_on_derivation.py
git commit -m "feat(graph): track bears_on edge depth (Phase 2 sampling prep)"
```

---

## Task 8: `freshness.enabled: false` opt-out

**Why:** The design promised this but Phase 1 didn't ship it. First `graph build` on existing downstream projects will flag many entities as `needs-review` because `last_reviewed=None` everywhere. Projects need a way to disable freshness during migration.

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py` (read `freshness.enabled` from `science.yaml` config; expose on `ProjectSources`)
- Modify: `science-tool/src/science_tool/graph/materialize.py` (`_derive_epistemic_layer` skipped when disabled)
- Modify: `science-tool/src/science_tool/graph/freshness.py` (`propagate_freshness_in_memory` returns empty list when disabled)
- Modify: tests

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_freshness_opt_out.py`:

```python
"""freshness.enabled: false opt-out for downstream projects mid-migration."""
from __future__ import annotations

from pathlib import Path
import pytest

from science_tool.graph.freshness import propagate_freshness_in_memory
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS


def test_freshness_disabled_skips_state_emission(tmp_path: Path) -> None:
    project_root = _build_project_with_freshness_disabled(tmp_path)  # writes science.yaml with freshness.enabled: false
    trig_path = materialize_graph(project_root)
    # Parse trig and assert no sci:freshnessState triples.
    from rdflib import Dataset
    ds = Dataset(); ds.parse(trig_path, format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    assert list(knowledge.triples((None, SCI_NS.freshnessState, None))) == []


def test_propagate_freshness_returns_empty_when_disabled(tmp_path: Path) -> None:
    project_root = _build_project_with_freshness_disabled(tmp_path)
    assert propagate_freshness_in_memory(project_root) == []


def test_freshness_enabled_default_emits_state(tmp_path: Path) -> None:
    # Same project but no freshness block → default-on.
    project_root = _build_project_default_freshness(tmp_path)
    trig_path = materialize_graph(project_root)
    from rdflib import Dataset
    ds = Dataset(); ds.parse(trig_path, format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    assert len(list(knowledge.triples((None, SCI_NS.freshnessState, None)))) > 0
```

Implementer: stand up minimal `_build_project_with_freshness_disabled` and `_build_project_default_freshness` helpers — at least one epistemic entity each.

- [ ] **Step 2: Run to verify they fail**

```bash
uv run --frozen --directory science-tool pytest tests/test_freshness_opt_out.py -v
```

Expected: FAIL — config field doesn't exist; freshness always runs.

- [ ] **Step 3: Add the config field on `ProjectSources`**

In `science-tool/src/science_tool/graph/sources.py`:

1. Add field `freshness_enabled: bool = True` to `ProjectSources`.
2. In `load_project_sources`, read from `config`:

```python
    freshness_block = config.get("freshness") or {}
    freshness_enabled = bool(freshness_block.get("enabled", True))
```

3. Pass to `ProjectSources(...)`.

- [ ] **Step 4: Skip the layer when disabled**

In `science-tool/src/science_tool/graph/materialize.py`, in `_build_dataset_from_sources` (or whichever helper calls `_derive_epistemic_layer`):

```python
    if sources.freshness_enabled:
        _derive_epistemic_layer(dataset, kind_class=kind_class, entity_meta=entity_meta)
```

In `propagate_freshness_in_memory`:

```python
    if not sources.freshness_enabled:
        return []
```

(Insert this *after* the audit gate from Task 5.)

- [ ] **Step 5: Run tests**

```bash
uv run --frozen --directory science-tool pytest tests/test_freshness_opt_out.py -v
uv run --frozen --directory science-tool pytest -q
```

Expected: all pass.

- [ ] **Step 6: Update the design doc Migration section**

In `docs/plans/2026-05-03-epistemic-dependency-graph-design.md` § Migration, replace the bullet about always-on with text describing the new opt-out:

```markdown
**Data.** No automatic rewrite. The first `graph build` after this lands will populate `bears_on` triples and an initial freshness baseline (everything starts `fresh` if `last_reviewed`/`created` provides a baseline; `needs-review` otherwise). Projects mid-migration can set `freshness.enabled: false` in `science.yaml` to skip freshness emission while still benefiting from `bears_on`.
```

- [ ] **Step 7: Commit**

```bash
git add science-tool/src/science_tool/graph/sources.py science-tool/src/science_tool/graph/materialize.py science-tool/src/science_tool/graph/freshness.py science-tool/tests/test_freshness_opt_out.py docs/plans/2026-05-03-epistemic-dependency-graph-design.md
git commit -m "feat(graph): freshness.enabled: false opt-out for downstream migration"
```

---

## Task 9: `derive_freshness` boundary tests

**Files:**
- Modify: `science-tool/tests/test_freshness_derivation.py`

- [ ] **Step 1: Write the boundary tests**

Append:

```python
def test_horizon_boundary_inclusive_at_threshold() -> None:
    """today - baseline == horizon → still fresh (uses strict `>`)."""
    from datetime import date, timedelta
    from rdflib import Dataset, URIRef
    from science_model.entities import EntityClass
    from science_tool.graph.freshness import derive_freshness
    from science_tool.graph.store import PROJECT_NS, SCI_NS
    from rdflib import Literal

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    baseline = date(2026, 1, 1)
    horizon = 30
    entities = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": baseline,
            "created": baseline,
            "updated": None,
            "review_horizon_days": horizon,
        }
    }
    today_eq = baseline + timedelta(days=horizon)
    derive_freshness(ds, entities=entities, today=today_eq)
    assert (h, SCI_NS.freshnessState, Literal("fresh")) in knowledge


def test_horizon_one_day_past_threshold_is_stale() -> None:
    from datetime import date, timedelta
    from rdflib import Dataset, URIRef
    from science_model.entities import EntityClass
    from science_tool.graph.freshness import derive_freshness
    from science_tool.graph.store import PROJECT_NS, SCI_NS
    from rdflib import Literal

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    baseline = date(2026, 1, 1)
    horizon = 30
    entities = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": baseline,
            "created": baseline,
            "updated": None,
            "review_horizon_days": horizon,
        }
    }
    today_past = baseline + timedelta(days=horizon + 1)
    derive_freshness(ds, entities=entities, today=today_past)
    assert (h, SCI_NS.freshnessState, Literal("stale")) in knowledge


def test_horizon_one_day_minimum() -> None:
    from datetime import date, timedelta
    from rdflib import Dataset, URIRef, Literal
    from science_model.entities import EntityClass
    from science_tool.graph.freshness import derive_freshness
    from science_tool.graph.store import PROJECT_NS, SCI_NS

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h = URIRef("http://example.org/hypothesis/h")
    baseline = date(2026, 1, 1)
    entities = {
        str(h): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": baseline,
            "created": baseline,
            "updated": None,
            "review_horizon_days": 1,
        }
    }
    # day after baseline → still fresh (today - baseline == 1, not > 1)
    derive_freshness(ds, entities=entities, today=baseline + timedelta(days=1))
    assert (h, SCI_NS.freshnessState, Literal("fresh")) in knowledge

    # two days after → stale
    ds2 = Dataset()
    k2 = ds2.graph(PROJECT_NS["graph/knowledge"])
    derive_freshness(ds2, entities=entities, today=baseline + timedelta(days=2))
    assert (h, SCI_NS.freshnessState, Literal("stale")) in k2
```

- [ ] **Step 2: Run tests**

```bash
uv run --frozen --directory science-tool pytest tests/test_freshness_derivation.py -v
```

Expected: all pass (current logic is `>`, so the boundary cases match).

- [ ] **Step 3: Commit**

```bash
git add science-tool/tests/test_freshness_derivation.py
git commit -m "test(graph): lock derive_freshness horizon boundary semantics"
```

---

## Task 10: Integration test gaps

**Files:**
- Modify or create: `science-tool/tests/test_graph_freshness_integration.py`

Each sub-task is independent.

- [ ] **Step 1: Provenance + closure end-to-end**

Add a test that builds a dataset with `paper:p` cited as `source_refs:` of `hypothesis:h`, where `hypothesis:h supports interpretation:i`. Assert that after full `materialize_graph`, both `paper:p bears_on hypothesis:h` and `paper:p bears_on interpretation:i` (closure) are in the knowledge graph.

```python
def test_provenance_plus_closure_end_to_end(tmp_path: Path) -> None:
    project_root = _build_project_with_paper_chain(tmp_path)  # implementer: see existing helpers
    trig = materialize_graph(project_root)
    from rdflib import Dataset, URIRef
    from science_tool.graph.store import PROJECT_NS, SCI_NS, _entity_uri
    ds = Dataset(); ds.parse(trig, format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    paper = _entity_uri("paper:p")
    h = _entity_uri("hypothesis:h")
    i = _entity_uri("interpretation:i")
    assert (paper, SCI_NS.bearsOn, h) in knowledge
    assert (paper, SCI_NS.bearsOn, i) in knowledge
```

- [ ] **Step 2: `propagate_freshness_in_memory` and `materialize_graph` agree**

Add a test that:
1. Builds a project with several epistemic entities, varied `last_reviewed`/`created`/upstream-update combinations.
2. Calls `propagate_freshness_in_memory(root)` to get rows.
3. Calls `materialize_graph(root)`, parses the trig, and extracts the same rows from `sci:freshnessState` triples.
4. Asserts the two sets are equal.

```python
def test_propagate_and_materialize_agree(tmp_path: Path) -> None:
    project_root = _build_project_with_mixed_freshness(tmp_path)
    in_memory = propagate_freshness_in_memory(project_root)
    trig = materialize_graph(project_root)
    from_trig = _extract_non_fresh_rows_from_trig(trig)  # mirrors propagate_freshness_in_memory's filter
    assert sorted(in_memory, key=lambda r: r["id"]) == sorted(from_trig, key=lambda r: r["id"])
```

- [ ] **Step 3: Run all integration tests**

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_freshness_integration.py -v
uv run --frozen --directory science-tool pytest -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add science-tool/tests/test_graph_freshness_integration.py
git commit -m "test(graph): cover provenance+closure and propagate/materialize parity"
```

---

## Task 11: Mark `[t013]` done

**Files:**
- Modify: `meta/tasks/active.md`

- [ ] **Step 1: Update task status**

In `meta/tasks/active.md` `[t013]`:

```markdown
## [t013] Phase 1 follow-ups: tighten freshness and registry surface
- priority: P3
- status: done
- aspects: [software-development]
- related: []
- created: 2026-05-03
- completed: 2026-05-04
```

- [ ] **Step 2: Commit (meta-scoped)**

```bash
git add meta/tasks/active.md
git commit -m "chore(meta): mark t013 done"
```

(Per D-001, this commit is meta-only — separate from the tool-level commits above.)

---

## Final Validation

After all tasks complete:

- [ ] **Run full test suites**

```bash
uv run --frozen --directory science-model pytest -q
uv run --frozen --directory science-tool pytest -q
```

Expected: science-model 283 + 13 (T1) + 0 (T2 replaces) ≈ 296 passing; science-tool 1724 + new tests ≈ 1750+ passing.

- [ ] **Run `validate.sh`**

```bash
cd meta && bash validate.sh --verbose
```

Expected: warnings only on `review_horizon_days`/etc. as before — no new failures.

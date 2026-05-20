# Graph build × commons overlay integration — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire commons-promoted entities and their per-project overlays into `science graph build` so authored references to `<dataset|paper|topic|theme>:<slug>` IDs resolve and produce triples in the project graph.

**Architecture:** A new module `science_tool/graph/commons_sources.py` collects commons-typed references from `entities + relations + bindings`, loads their canonical body from the commons store via `CommonsQuery`, optionally merges a project overlay via `merge_entity`, translates the merged frontmatter into a typed `Entity` (pass-through + normalize), and appends it to `ProjectSources.entities` with `scope = EntityScope.SHARED`. A single new tail-call from `load_project_sources` invokes the module after relations + bindings are in scope. Downstream `audit_project_sources` and `materialize_graph` work unchanged except for two surgical extensions: `_add_entity` gains an optional `overlay_paths` kwarg for dual-source provenance, and emits a `sci:scope` triple for every entity.

**Tech Stack:** Python 3.11, pydantic 2, rdflib 7, pytest. Run with `uv run pytest tests/<test>.py -v` from `~/d/science/science/`. Lint with `uv run ruff format` and `uv run ruff check` from `~/d/science/science/`. Conventional commits, lowercase subjects (e.g., `feat(graph):`, `test(graph):`).

**Design spec:** `~/d/science/docs/plans/2026-05-19-graph-build-commons-overlay-integration-design.md`

---

## File Structure

Working directory: `~/d/science/science/` (the inner package directory). Paths below are relative to that.

| File | Action | Responsibility |
|---|---|---|
| `model/src/science_model/entities.py` | modify (Task 1) | Extend `ThemeEntity.theme_kind` and `ThemeEntity.theme_scope` Literals to admit commons vocabulary. |
| `src/science_tool/graph/store.py` | modify (Task 2) | Register `SCI_NS.scope` in the known-predicates list. |
| `src/science_tool/graph/materialize.py` | modify (Tasks 3, 4, 10, 11) | Emit `sci:scope` triple; accept optional `overlay_paths`; thread through `materialize_graph`; enrich unresolved-ref message. |
| `src/science_tool/graph/sources.py` | modify (Tasks 5, 9) | Add `commons_overlay_paths` to `ProjectSources`; insert tail-call into `load_project_sources`. |
| `src/science_tool/graph/commons_sources.py` | **NEW** (Tasks 6, 7, 8) | All commons-loading logic: collector + translator + orchestrator. |
| `tests/test_graph_commons_sources.py` | **NEW** (Tasks 6, 7, 8) | Unit tests for collector, translator, and orchestrator. |
| `tests/test_graph_materialize.py` | modify (Tasks 3, 4, 10) | E2E assertions for scope triple and dual provenance. |
| `tests/test_graph_migrate.py` | modify (Task 11) | Audit regression: commons-referenced topic resolves. |
| `tests/test_graph_commons_mm30_canary.py` | **NEW** (Task 12) | mm30-shaped canary fixture + tests. |
| `tests/fixtures/commons_mm30_canary/` | **NEW** (Task 12) | Synthetic project + commons stub reproducing the four mm30 patterns. |

Convention reminders for every task:
- Run tests from `~/d/science/science/`: `uv run pytest tests/<file>.py::<test> -v`.
- Format + lint after each step that edits Python: `uv run ruff format` then `uv run ruff check`.
- Commit messages use conventional format with lowercase subject (e.g., `feat(graph): add commons-source loading helper`).
- Never `git commit --amend`, never `--no-verify`. Fix root causes if a hook fails.

---

### Task 1: Extend `ThemeEntity` vocabulary Literals

**Files:**
- Modify: `model/src/science_model/entities.py:455-465`
- Test: `model/tests/test_entities_theme.py` (NEW) or extend an existing theme test — search first

Background: `ThemeEntity` currently accepts `theme_kind ∈ {methodological, biological, translational, evidence-quality, organizational}` and `theme_scope ∈ {project, federation, child}`. Commons-promoted themes from `schemas/mixin-theme-2.0.json` use `theme_kind ∈ {methodological, conceptual, empirical, domain}` and `theme_scope ∈ {project, cross-project}`. The plan loads commons themes into the project graph, so `ThemeEntity` must accept the union of both vocabularies. Per design §2 this is the **only** schema change in scope; vocabulary harmonization is a separate task.

- [ ] **Step 1: Confirm test file location**

Run: `ls ~/d/science/science/model/tests/ 2>/dev/null && grep -rln "ThemeEntity" ~/d/science/science/model/tests/ 2>/dev/null`
- If `model/tests/test_entities_theme.py` exists: extend it.
- If not, search `science/tests/` for an existing theme test. If still nothing, create `model/tests/test_entities_theme.py` (or `science/tests/test_entities_theme.py` if `model/tests/` is absent).

- [ ] **Step 2: Write the failing tests**

In the chosen test file (importing whatever path `ThemeEntity` lives at):

```python
from __future__ import annotations

import pytest
from science_model.entities import ThemeEntity


def _base() -> dict:
    return {
        "id": "theme:demo",
        "kind": "theme",
        "type": "theme",
        "title": "Demo theme",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "",
    }


# Note: every direct Entity.model_validate / ThemeEntity.model_validate call in
# this plan MUST include "type": <kind>. The Entity model runs a
# `_validate_kind_type_consistency` validator (entities.py:287) that compares
# `self.type` to `core_entity_type_for_kind(self.kind)` and raises
# "kind/type mismatch" if they disagree. The full load pipeline auto-fills
# `type` via `_enrich_raw`, but direct unit-test construction bypasses that.


@pytest.mark.parametrize("kind", ["conceptual", "empirical", "domain"])
def test_theme_entity_accepts_mixin_kinds(kind: str) -> None:
    entity = ThemeEntity.model_validate({**_base(), "theme_kind": kind})
    assert entity.theme_kind == kind


def test_theme_entity_accepts_cross_project_scope() -> None:
    entity = ThemeEntity.model_validate({**_base(), "theme_scope": "cross-project"})
    assert entity.theme_scope == "cross-project"


def test_theme_entity_rejects_unknown_kind() -> None:
    with pytest.raises(Exception):
        ThemeEntity.model_validate({**_base(), "theme_kind": "not-a-kind"})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest <test-path> -v`
Expected: the parametrized `conceptual` / `empirical` / `domain` and the `cross-project` test FAIL with pydantic ValidationError. The "rejects unknown kind" test PASSES (it's a control).

- [ ] **Step 4: Apply the Literal extensions**

Edit `model/src/science_model/entities.py` lines 458-465 (the `ThemeEntity` body). Replace:

```python
    theme_kind: Literal[
        "methodological",
        "biological",
        "translational",
        "evidence-quality",
        "organizational",
    ] = "methodological"
    theme_scope: Literal["project", "federation", "child"] = "project"
```

with:

```python
    theme_kind: Literal[
        "methodological",
        "biological",
        "translational",
        "evidence-quality",
        "organizational",
        "conceptual",
        "empirical",
        "domain",
    ] = "methodological"
    theme_scope: Literal[
        "project",
        "federation",
        "child",
        "cross-project",
    ] = "project"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest <test-path> -v`
Expected: all four tests PASS.

- [ ] **Step 6: Run the full model + tool test suites to confirm no regression**

Run: `cd ~/d/science/science && uv run pytest -q`
Expected: every test that previously passed still passes.

- [ ] **Step 7: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`
Expected: no diffs, no errors.

- [ ] **Step 8: Commit**

Run:
```bash
cd ~/d/science && git add science/model/src/science_model/entities.py <test-path>
git commit -m "feat(model): extend ThemeEntity literals to union mixin-theme-2.0 vocabulary"
```

---

### Task 2: Register `sci:scope` predicate in `GRAPH_EXPORT_EDGE_METADATA_PREDICATES`

**Files:**
- Modify: `src/science_tool/graph/store.py:264-318` (the `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` frozenset)
- Test: `tests/test_graph_store.py` (extend if exists, otherwise create)

Background: `store.py` exposes two distinct registries: (a) `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (frozenset starting at line 264) is the set of predicates whose triples are treated as **entity-level metadata** during graph export rather than as edges in the relation graph (`store.py:1582` and `1792` consume it). Entity-emitted predicates like `SCI_NS.projectStatus`, `SCI_NS.confidence`, `SCHEMA_NS.description` belong here. (b) `PREDICATE_REGISTRY` (list of dicts at line 2758) is a documentation registry of inter-entity edge predicates (`skos:related`, `cito:supports`, …); existing entity-metadata predicates `SCI_NS.profile` and `SCI_NS.domain` are not in `PREDICATE_REGISTRY` and that's correct.

`sci:scope` is an entity-metadata predicate (literal object, never a URIRef), so it must be added to `GRAPH_EXPORT_EDGE_METADATA_PREDICATES`. Do NOT add it to `PREDICATE_REGISTRY`.

- [ ] **Step 1: Locate the frozenset and confirm its line range**

Run: `grep -n "GRAPH_EXPORT_EDGE_METADATA_PREDICATES" ~/d/science/science/src/science_tool/graph/store.py | head`
Expected: definition at line 264, consumed at lines ~1582 and ~1792. Confirm before editing.

- [ ] **Step 2: Write the failing test**

In `tests/test_graph_store.py` (create if missing):

```python
from __future__ import annotations

from science_tool.graph.store import GRAPH_EXPORT_EDGE_METADATA_PREDICATES, SCI_NS


def test_sci_scope_is_registered_as_entity_metadata_predicate() -> None:
    """`sci:scope` is emitted by `_add_entity` as entity-level metadata
    (literal object), not an inter-entity edge. It must appear in the
    metadata-predicate allowlist so `store.py` does not misclassify it as
    a knowledge-graph edge."""
    assert SCI_NS.scope in GRAPH_EXPORT_EDGE_METADATA_PREDICATES
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_store.py::test_sci_scope_is_registered_as_entity_metadata_predicate -v`
Expected: FAIL with `assert URIRef('http://.../scope') in frozenset({...})` returning False.

- [ ] **Step 4: Add `SCI_NS.scope` to the frozenset**

In `src/science_tool/graph/store.py`, locate the listing in `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (line 264). Insert `SCI_NS.scope,` adjacent to `SCI_NS.projectStatus` (the other entity-metadata predicate emitted by `_add_entity`). Verify with:

```bash
grep -n "SCI_NS.scope" ~/d/science/science/src/science_tool/graph/store.py
```

- [ ] **Step 5: Run the failing test again**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_store.py::test_sci_scope_is_registered_as_entity_metadata_predicate -v`
Expected: PASS.

- [ ] **Step 6: Run the existing graph test suite for regression**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_store.py tests/test_graph_materialize.py -q`
Expected: PASS (the allowlist addition is purely additive).

- [ ] **Step 7: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 8: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/store.py science/tests/test_graph_store.py
git commit -m "feat(graph): register sci:scope in entity-metadata predicate allowlist"
```

---

### Task 3: Emit `sci:scope` triple in `_add_entity` for every entity

**Files:**
- Modify: `src/science_tool/graph/materialize.py:199-220` (the `_add_entity` function)
- Test: `tests/test_graph_materialize.py` (extend)

Background: `_add_entity` writes entity-level triples (identifier, prefLabel, profile, etc.). Every entity gets a new `sci:scope` triple whose object is `"cross-project"` for `EntityScope.SHARED` and `"project"` for `EntityScope.PROJECT`. This symmetry — project-local entities also emit `scope = "project"` — is intentional per design §5.2 so consumers don't infer scope from absence.

- [ ] **Step 1: Write the failing test**

In `tests/test_graph_materialize.py`, add (model the helpers on existing tests — most use a `tmp_path` project tree + `materialize_graph(project)`):

```python
def test_materialize_emits_scope_triple_for_project_entity(tmp_path: Path) -> None:
    # Build a minimal project with one project-local hypothesis entity.
    project = _build_minimal_project(tmp_path)  # reuse helper from existing tests
    trig_path = materialize_graph(project)
    text = trig_path.read_text(encoding="utf-8")
    assert 'sci:scope "project"' in text
```

If `_build_minimal_project` does not exist, copy the inline setup from `test_materialize_graph_includes_task_nodes_and_canonical_links` (around line 188).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_materialize.py::test_materialize_emits_scope_triple_for_project_entity -v`
Expected: FAIL with `'sci:scope "project"' in text` — the predicate isn't emitted yet.

- [ ] **Step 3: Add the import and the triple emission**

In `src/science_tool/graph/materialize.py`:

a. Confirm `EntityScope` is importable from `science_model.entities` (it's re-exported there) or import from `science_model.identity` directly. Search for an existing import:

```bash
grep -n "EntityScope" ~/d/science/science/src/science_tool/graph/materialize.py
```

If absent, add:

```python
from science_model.identity import EntityScope
```

b. In `_add_entity` (line 199), after the existing `SCI_NS.profile` emission (line 207) and before the `if entity.domain:` block (line 208), insert:

```python
    scope_value = "cross-project" if entity.scope is EntityScope.SHARED else "project"
    knowledge.add((uri, SCI_NS.scope, Literal(scope_value)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_materialize.py::test_materialize_emits_scope_triple_for_project_entity -v`
Expected: PASS.

- [ ] **Step 5: Run the full graph test suite**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_materialize.py -q`
Expected: every existing test still passes. The new triple is additive.

- [ ] **Step 6: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 7: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/materialize.py science/tests/test_graph_materialize.py
git commit -m "feat(graph): emit sci:scope triple for every entity"
```

---

### Task 4: Add optional `overlay_paths` kwarg to `_add_entity` for dual-source provenance

**Files:**
- Modify: `src/science_tool/graph/materialize.py:199-220`
- Test: `tests/test_graph_materialize.py` (extend)

Background: Per design §5.5, a commons-derived entity with a project overlay needs TWO `prov:wasDerivedFrom` triples — one for the commons body, one for the overlay. The Entity model has no field for the overlay path, so `_add_entity` accepts an optional `overlay_paths: dict[str, str] | None = None` keyed by `canonical_id`. Default `None` means existing callers don't change behavior.

- [ ] **Step 1: Write the failing test**

In `tests/test_graph_materialize.py`, add a focused test that directly exercises `_add_entity` with a synthetic Entity. Use rdflib `Graph` directly to avoid spinning a full project:

```python
def test_add_entity_emits_two_provenance_triples_when_overlay_path_present() -> None:
    from rdflib import Graph
    from rdflib.namespace import PROV
    from science_model.entities import Entity
    from science_tool.graph.materialize import _add_entity, _entity_uri

    entity = Entity.model_validate({
        "id": "topic:demo",
        "kind": "topic",
        "type": "topic",
        "title": "Demo",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "/abs/path/canonical.md",
    })
    knowledge = Graph()
    provenance = Graph()
    overlay_paths = {"topic:demo": "/abs/path/overlay.md"}
    _add_entity(
        entity=entity,
        knowledge=knowledge,
        provenance=provenance,
        overlay_paths=overlay_paths,
    )
    # `_entity_uri("topic:demo")` returns `PROJECT_NS["topic/demo"]` — no
    # `entity/` segment (materialize.py:774).
    entity_uri = _entity_uri("topic:demo")
    derived_from_entity = list(provenance.objects(entity_uri, PROV.wasDerivedFrom))
    assert len(derived_from_entity) == 2


def test_add_entity_emits_one_provenance_triple_without_overlay() -> None:
    from rdflib import Graph
    from rdflib.namespace import PROV
    from science_model.entities import Entity
    from science_tool.graph.materialize import _add_entity, _entity_uri

    entity = Entity.model_validate({
        "id": "topic:demo",
        "kind": "topic",
        "type": "topic",
        "title": "Demo",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "/abs/path/canonical.md",
    })
    knowledge = Graph()
    provenance = Graph()
    _add_entity(entity=entity, knowledge=knowledge, provenance=provenance)
    entity_uri = _entity_uri("topic:demo")
    derived_from_entity = list(provenance.objects(entity_uri, PROV.wasDerivedFrom))
    assert len(derived_from_entity) == 1
```

- [ ] **Step 2: Run tests to verify the two-provenance test fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_materialize.py::test_add_entity_emits_two_provenance_triples_when_overlay_path_present tests/test_graph_materialize.py::test_add_entity_emits_one_provenance_triple_without_overlay -v`
Expected: the "two-provenance" test FAILS (TypeError: unexpected keyword `overlay_paths`); the "one-provenance" test PASSES.

- [ ] **Step 3: Add the `overlay_paths` parameter and second-triple emission**

In `src/science_tool/graph/materialize.py`, change the signature and body of `_add_entity` (line 199):

```python
def _add_entity(
    *,
    entity: Entity,
    knowledge,
    provenance,
    overlay_paths: dict[str, str] | None = None,
) -> None:
    uri = _entity_uri(entity.canonical_id)
    knowledge.add((uri, RDF.type, SCI_NS[_kind_class_name(entity.kind)]))
    knowledge.add((uri, SCHEMA_NS.identifier, Literal(entity.canonical_id)))
    knowledge.add((uri, SKOS.prefLabel, Literal(entity.title)))
    summary = getattr(entity, "summary", "")
    if isinstance(summary, str) and summary.strip():
        knowledge.add((uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((uri, SCI_NS.profile, Literal(entity.profile)))
    scope_value = "cross-project" if entity.scope is EntityScope.SHARED else "project"
    knowledge.add((uri, SCI_NS.scope, Literal(scope_value)))
    if entity.domain:
        knowledge.add((uri, SCI_NS.domain, Literal(entity.domain)))
    if entity.status:
        knowledge.add((uri, SCI_NS.projectStatus, Literal(entity.status)))

    source_uri = _source_uri(entity.file_path)
    provenance.add((uri, PROV.wasDerivedFrom, source_uri))
    if entity.confidence is not None:
        provenance.add((uri, SCI_NS.confidence, Literal(str(entity.confidence), datatype=XSD.decimal)))
    _add_reasoning_metadata(uri=uri, provenance=provenance, entity=entity)
    provenance.add((source_uri, RDF.type, PROV.Entity))
    provenance.add((source_uri, SCHEMA_NS.identifier, Literal(entity.file_path)))

    if overlay_paths is not None:
        overlay_path = overlay_paths.get(entity.canonical_id)
        if overlay_path:
            overlay_uri = _source_uri(overlay_path)
            provenance.add((uri, PROV.wasDerivedFrom, overlay_uri))
            provenance.add((overlay_uri, RDF.type, PROV.Entity))
            provenance.add((overlay_uri, SCHEMA_NS.identifier, Literal(overlay_path)))
```

(This consolidates Task 3's `scope_value` block with the new `overlay_paths` block. If Task 3's edit is already in place, only the signature and the trailing `if overlay_paths` block are new.)

- [ ] **Step 4: Run tests to verify both pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_materialize.py -v`
Expected: PASS.

- [ ] **Step 5: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/materialize.py science/tests/test_graph_materialize.py
git commit -m "feat(graph): add optional overlay_paths kwarg to _add_entity for dual provenance"
```

---

### Task 5: Add `commons_overlay_paths` field to `ProjectSources`

**Files:**
- Modify: `src/science_tool/graph/sources.py:120-136` (the `ProjectSources` model)
- Test: `tests/test_graph_sources.py` (extend if exists, otherwise add a small new test file)

Background: Per design §4.5, the overlay file path is needed at materialize time but the Entity model can't carry it. `ProjectSources` gains a `dict[str, str]` side-table mapping `canonical_id -> overlay_path`. Default empty dict means projects with no overlays see zero behavior change.

- [ ] **Step 1: Write the failing test**

In a new or existing test file, add:

```python
def test_project_sources_defaults_commons_overlay_paths_empty() -> None:
    from science_tool.graph.entity_registry import EntityRegistry
    from science_tool.graph.sources import KnowledgeProfiles, ProjectSources

    sources = ProjectSources(
        project_name="demo",
        project_root="/tmp/demo",
        profiles=KnowledgeProfiles(),
        entities=[],
        registry=EntityRegistry.with_core_types(),
    )
    assert sources.commons_overlay_paths == {}


def test_project_sources_accepts_commons_overlay_paths() -> None:
    from science_tool.graph.entity_registry import EntityRegistry
    from science_tool.graph.sources import KnowledgeProfiles, ProjectSources

    sources = ProjectSources(
        project_name="demo",
        project_root="/tmp/demo",
        profiles=KnowledgeProfiles(),
        entities=[],
        registry=EntityRegistry.with_core_types(),
        commons_overlay_paths={"topic:x": "/abs/overlay.md"},
    )
    assert sources.commons_overlay_paths == {"topic:x": "/abs/overlay.md"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest <test-path> -v`
Expected: FAIL — `ProjectSources` has no field `commons_overlay_paths`.

- [ ] **Step 3: Add the field**

In `src/science_tool/graph/sources.py:120-136`, in the `ProjectSources` class body, add after the `markdown_documents` line (line 135):

```python
    commons_overlay_paths: dict[str, str] = Field(default_factory=dict)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest <test-path> -v`
Expected: PASS.

- [ ] **Step 5: Run the full test suite**

Run: `cd ~/d/science/science && uv run pytest -q`
Expected: no regression. `ProjectSources(...)` construction sites that omit the new field still work because of the default.

- [ ] **Step 6: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 7: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/sources.py <test-path>
git commit -m "feat(graph): add commons_overlay_paths side-table to ProjectSources"
```

---

### Task 6: Create `graph/commons_sources.py` with the reference collector

**Files:**
- Create: `src/science_tool/graph/commons_sources.py`
- Create: `tests/test_graph_commons_sources.py`

Background: The collector mirrors **every reference field that `audit_project_sources` walks** so that no commons ID can slip through unresolved. The three audit paths in `graph/migrate.py` are:

(a) **Entity fields** — see `_audit_entity` at `graph/migrate.py:300-396`. It walks: `related` (line 307), `commits_to` (line 319), `blocked_by` (line 332), `source_refs` (line 334), `evidence_refs` (line 345), `chain` (line 357), `audits` (singular string ref — `getattr(entity, "audits", None)`, line 369), `proposition_refs` (line 382), `same_as` (line 394). The collector must cover all nine.

(b) **Authored relations** — `SourceRelation.subject` and `.object`. See `graph/migrate.py:_audit_relation_endpoint` (line 558).

(c) **Parameter bindings** — `SourceBinding.model`, `.parameter`, AND every entry in `.source_refs`. See `graph/migrate.py:_audit_binding` (lines 505-525); `source_refs` is audited at line 514. Any commons ID that lives only in `binding.source_refs` will fail unresolved if collection misses it.

Additionally, `_add_relations` in `graph/materialize.py:222-365` walks two fields the audit does NOT cover: `participants` and `propositions`. Those are materialized as graph edges but not audit-gated. Including them in the collector is forward-looking: a commons ref appearing only via `participants:` would still produce a missing edge target at materialize time. The collector picks them up to keep that surface consistent.

Filter to `<type> ∈ {dataset, paper, topic, theme}` after collection. Return a `set[str]` of canonical_ids. Pure function — no I/O, no commons access.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_graph_commons_sources.py`:

```python
"""Tests for science_tool.graph.commons_sources."""
from __future__ import annotations

import pytest
from science_model.entities import Entity
from science_model.source_contracts import BindingSource

from science_tool.graph.commons_sources import collect_referenced_commons_ids
from science_tool.graph.sources import SourceRelation


def _entity(canonical_id: str, *, related: list[str] | None = None, source_refs: list[str] | None = None) -> Entity:
    kind = canonical_id.split(":", 1)[0]
    return Entity.model_validate({
        "id": canonical_id,
        "kind": kind,
        "type": kind,  # required: see _validate_kind_type_consistency (entities.py:287)
        "title": canonical_id,
        "project": "demo",
        "ontology_terms": [],
        "related": related or [],
        "source_refs": source_refs or [],
        "content_preview": "",
        "file_path": "",
    })


def test_collector_returns_empty_for_no_references() -> None:
    result = collect_referenced_commons_ids(
        project_entities=[_entity("hypothesis:h1")],
        project_relations=[],
        project_bindings=[],
    )
    assert result == set()


def test_collector_picks_up_entity_related_field() -> None:
    entities = [_entity("hypothesis:h1", related=["topic:phf19", "topic:prc2"])]
    result = collect_referenced_commons_ids(
        project_entities=entities,
        project_relations=[],
        project_bindings=[],
    )
    assert result == {"topic:phf19", "topic:prc2"}


def test_collector_picks_up_entity_source_refs() -> None:
    entities = [_entity("hypothesis:h1", source_refs=["paper:Adams2025"])]
    result = collect_referenced_commons_ids(
        project_entities=entities,
        project_relations=[],
        project_bindings=[],
    )
    assert result == {"paper:Adams2025"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_refs", ["paper:Adams2025"]),
        ("commits_to", ["topic:phf19"]),
        ("blocked_by", ["topic:phf19"]),
        ("chain", ["topic:phf19"]),
        ("proposition_refs", ["topic:phf19"]),
        ("same_as", ["paper:Adams2025"]),
        ("participants", ["topic:phf19"]),
        ("propositions", ["topic:phf19"]),
    ],
)
def test_collector_picks_up_other_audited_and_materialized_fields(
    field: str, value: list[str]
) -> None:
    """Every list field that `_audit_entity` walks AND the two materialize-only
    fields (`participants`, `propositions`) must be covered. Locks parity
    against graph/migrate.py:_audit_entity (lines 300-396).

    Uses SimpleNamespace as a duck-typed Entity stand-in: the collector only
    calls `getattr(entity, field, None)`, never any pydantic validator, so a
    plain attribute carrier suffices. Building real Entity instances for every
    field combo (especially `participants` / `propositions`, which live on
    MechanismEntity with its own invariants, and `audits`, which lives on
    ChainAuditEntity with a required verdict block) would dwarf what's actually
    under test."""
    from types import SimpleNamespace

    entity = SimpleNamespace(**{f: [] for f in (
        "related", "commits_to", "blocked_by", "source_refs", "evidence_refs",
        "chain", "proposition_refs", "same_as", "participants", "propositions",
    )})
    setattr(entity, field, value)
    setattr(entity, "audits", None)
    result = collect_referenced_commons_ids(
        project_entities=[entity],  # type: ignore[list-item]
        project_relations=[],
        project_bindings=[],
    )
    assert set(value) <= result, f"field {field!r} value {value!r} not picked up"


def test_collector_picks_up_audits_single_ref() -> None:
    """`audits` is a SINGLE optional string ref, not a list. graph/migrate.py:369
    audits the value via `getattr(entity, "audits", None)`. Locks coverage of
    that special-case path."""
    from types import SimpleNamespace

    entity = SimpleNamespace(
        related=[], commits_to=[], blocked_by=[], source_refs=[],
        evidence_refs=[], chain=[], proposition_refs=[], same_as=[],
        participants=[], propositions=[], audits="topic:phf19",
    )
    result = collect_referenced_commons_ids(
        project_entities=[entity],  # type: ignore[list-item]
        project_relations=[],
        project_bindings=[],
    )
    assert "topic:phf19" in result


def test_collector_picks_up_relation_endpoints() -> None:
    relations = [
        SourceRelation(
            subject="hypothesis:h1",
            predicate="related",
            object="topic:phf19",
            source_path="knowledge/sources/local/relations.yaml",
        )
    ]
    result = collect_referenced_commons_ids(
        project_entities=[],
        project_relations=relations,
        project_bindings=[],
    )
    assert result == {"topic:phf19"}


def test_collector_picks_up_binding_model_parameter() -> None:
    binding = BindingSource(
        model="dataset:foo",
        parameter="topic:phf19",
        source_path="knowledge/sources/local/parameter_bindings.yaml",
    )
    result = collect_referenced_commons_ids(
        project_entities=[],
        project_relations=[],
        project_bindings=[binding],
    )
    assert result == {"dataset:foo", "topic:phf19"}


def test_collector_picks_up_binding_source_refs() -> None:
    binding = BindingSource(
        model="model:m1",
        parameter="parameter:p1",
        source_path="knowledge/sources/local/parameter_bindings.yaml",
        source_refs=["topic:phf19", "paper:Adams2025"],
    )
    result = collect_referenced_commons_ids(
        project_entities=[],
        project_relations=[],
        project_bindings=[binding],
    )
    assert {"topic:phf19", "paper:Adams2025"} <= result


def test_collector_filters_to_commons_types_only() -> None:
    entities = [_entity("hypothesis:h1", related=[
        "topic:phf19",
        "hypothesis:h2",       # not a commons type
        "question:q1",         # not a commons type
        "paper:Adams2025",
        "dataset:foo",
        "theme:bar",
    ])]
    result = collect_referenced_commons_ids(
        project_entities=entities,
        project_relations=[],
        project_bindings=[],
    )
    assert result == {"topic:phf19", "paper:Adams2025", "dataset:foo", "theme:bar"}


def test_collector_ignores_external_and_meta_refs() -> None:
    entities = [_entity("hypothesis:h1", related=[
        "http://example.org/x",
        "go:0006281",
        "meta:annotation",
        "topic:phf19",
    ])]
    result = collect_referenced_commons_ids(
        project_entities=entities,
        project_relations=[],
        project_bindings=[],
    )
    assert result == {"topic:phf19"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v`
Expected: FAIL with `ImportError: cannot import name 'collect_referenced_commons_ids' from 'science_tool.graph.commons_sources'`.

- [ ] **Step 3: Create the module skeleton + collector**

Create `src/science_tool/graph/commons_sources.py`:

```python
"""Commons-source loading for the graph builder.

See `docs/plans/2026-05-19-graph-build-commons-overlay-integration-design.md`.

This module collects references to commons-promoted entities (datasets, papers,
topics, themes) from a project's entities, structured relations, and parameter
bindings, then loads the canonical body from the commons store (optionally
merging a project overlay) and translates the merged frontmatter into a typed
`Entity` with `scope = EntityScope.SHARED`. Strict failure semantics: an orphan
overlay aborts the build; a referenced-only ID with no commons canonical is
left to the existing audit path.

One-way dependency: graph → commons. Never the reverse.
"""

from __future__ import annotations

from science_model.entities import Entity
from science_model.source_contracts import BindingSource

from science_tool.graph.sources import (
    SourceRelation,
    is_external_reference,
    is_metadata_reference,
)

_COMMONS_TYPES = frozenset({"dataset", "paper", "topic", "theme"})


# Entity fields walked by `audit_project_sources._audit_entity` (graph/migrate.py:300-396).
# Every list-valued field that audit walks MUST appear here, or a commons ID used
# only via that field will be visible to the audit but not to the commons loader,
# yielding a hard `unresolved_reference` failure.
_AUDITED_LIST_FIELDS = (
    "related",
    "commits_to",
    "blocked_by",
    "source_refs",
    "evidence_refs",
    "chain",
    "proposition_refs",
    "same_as",
)
# Materialized but not audit-gated (`_add_relations` in graph/materialize.py:222).
# Carrying these so that a commons ref appearing only via `participants:` or
# `propositions:` still resolves at materialize time.
_MATERIALIZED_LIST_FIELDS = (
    "participants",
    "propositions",
)


def collect_referenced_commons_ids(
    *,
    project_entities: list[Entity],
    project_relations: list[SourceRelation],
    project_bindings: list[BindingSource],
) -> set[str]:
    """Collect every `<type>:<slug>` reference where `<type>` is a commons type.

    Mirrors the three audit paths in graph/migrate.py:
      (a) entity fields: every list field walked by `_audit_entity`, plus
          `audits` (singular string ref), plus the materialize-only
          `participants` / `propositions` to avoid producing dangling edges.
      (b) authored relations: SourceRelation.subject and .object
      (c) parameter bindings: BindingSource.model, .parameter, AND .source_refs
    """
    found: set[str] = set()

    for entity in project_entities:
        for field in _AUDITED_LIST_FIELDS:
            for ref in getattr(entity, field, None) or []:
                _maybe_add(found, ref)
        for field in _MATERIALIZED_LIST_FIELDS:
            for ref in getattr(entity, field, None) or []:
                _maybe_add(found, ref)
        # `audits` is a single optional string ref (graph/migrate.py:369), not
        # a list. Treat it specially.
        audits_target = getattr(entity, "audits", None)
        if audits_target:
            _maybe_add(found, audits_target)

    for relation in project_relations:
        _maybe_add(found, relation.subject)
        _maybe_add(found, relation.object)

    for binding in project_bindings:
        _maybe_add(found, binding.model)
        _maybe_add(found, binding.parameter)
        for ref in binding.source_refs or []:
            _maybe_add(found, ref)

    return found


def _maybe_add(found: set[str], raw: object) -> None:
    if not isinstance(raw, str) or not raw:
        return
    if is_external_reference(raw) or is_metadata_reference(raw):
        return
    if ":" not in raw:
        return
    type_part, _ = raw.split(":", 1)
    if type_part in _COMMONS_TYPES:
        found.add(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v`
Expected: PASS.

- [ ] **Step 5: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 6: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/commons_sources.py science/tests/test_graph_commons_sources.py
git commit -m "feat(graph): add commons-reference collector"
```

---

### Task 7: Add the entity-translation helper `_materialize_commons_entity`

**Files:**
- Modify: `src/science_tool/graph/commons_sources.py`
- Modify: `tests/test_graph_commons_sources.py`

Background: Per design §4.3, the translation strategy is **pass-through + normalize**. Copy the `MergedEntity.merged_frontmatter` dict verbatim into the raw Entity dict, then apply only the targeted normalizations: rename `id` → `canonical_id`, rename `description` → `summary` (when `summary` not already set), set `scope = "shared"`, `profile = "shared"`, `file_path = str(canonical.body_path)`, drop the overlay-only project fields and `schema_profile`. Run the existing `_enrich_raw` to fill defaults, then `registry.resolve(kind).model_validate(raw)`. This preserves dataset-mixin (`origin`, `access`, `derivation`, ...), theme-mixin (`theme_kind`, `theme_scope`), and paper-mixin fields automatically.

A handwritten subset would silently drop the dataset-mixin fields and break `DatasetEntity` invariants #7/#8. Pass-through is the load-bearing choice.

**Note on `summary`:** `summary` is defined only on `ThemeEntity` (entities.py:466) and `MechanismEntity` (entities.py:440); plain `ProjectEntity` (entities.py:324) — which `topic` and `paper` resolve to — has no such field. The translator still writes `summary` into the raw dict; pydantic's `extra="ignore"` drops it for kinds without the field. Critically, the original `description:` is NOT lost: `_enrich_raw` (sources.py:444-451) falls back to copying `description` into `content_preview` when `content_preview` is empty. The downstream consequence is that `_add_entity` emits `schema:description` only for themes/mechanisms (where `summary` survives); topics and papers carry the body text in `content_preview` instead. The tests in this task pin both behaviors.

- [ ] **Step 1: Write the failing tests**

In `tests/test_graph_commons_sources.py`, **merge** these new imports into the existing top-of-file import block created in Task 6 (do NOT append a fresh import block below existing tests — ruff `E402` rejects module-level imports after non-import code). `pytest` is already imported from Task 6; add only the new ones:

```python
from pathlib import Path
from dataclasses import dataclass
```

Then append the helpers and tests at the bottom of the file:

```python
@dataclass(frozen=True)
class _StubCanonical:
    """Minimal CommonsEntityRecord stand-in for translator unit tests."""
    canonical_id: str
    type: str
    slug: str
    schema_profile: str
    frontmatter: dict
    body_path: Path
    datapackage_path: Path | None = None
    mtime_ns: int = 0


def _merged(canonical_id: str, kind: str, frontmatter: dict, body_path: str = "/abs/canonical.md"):
    """Build a MergedEntity-shape that _materialize_commons_entity consumes."""
    from science_tool.commons.overlay import MergedEntity
    canonical = _StubCanonical(
        canonical_id=canonical_id,
        type=kind,
        slug=canonical_id.split(":", 1)[1],
        schema_profile=frontmatter.get("schema_profile", "science-entity-base/1.0+topic/2.0"),
        frontmatter=dict(frontmatter),
        body_path=Path(body_path),
    )
    return MergedEntity(
        canonical=canonical,
        overlay=None,
        merged_frontmatter=dict(frontmatter),
        merged_body="",
        field_sources={key: "canonical" for key in frontmatter},
    )


def test_translate_topic_sets_scope_shared() -> None:
    from science_tool.graph.commons_sources import _materialize_commons_entity
    from science_tool.graph.entity_registry import EntityRegistry
    from science_model.identity import EntityScope

    merged = _merged(
        canonical_id="topic:demo",
        kind="topic",
        frontmatter={
            "id": "topic:demo",
            "type": "topic",
            "title": "Demo",
            "schema_profile": "science-entity-base/1.0+topic/2.0",
            "tags": ["x"],
            "related": [],
            "source_refs": [],
        },
    )
    entity = _materialize_commons_entity(
        merged,
        registry=EntityRegistry.with_core_types(),
        project_slug="demo",
        active_kinds=frozenset({"topic"}),
        ontology_catalogs=[],
    )
    assert entity.scope is EntityScope.SHARED
    assert entity.canonical_id == "topic:demo"
    assert entity.kind == "topic"
    assert entity.title == "Demo"
    assert entity.file_path == "/abs/canonical.md"


def test_translate_topic_description_flows_to_content_preview() -> None:
    """Topics resolve to ProjectEntity, which has no `summary` field.
    `description` should still NOT be lost: it flows through `_enrich_raw`'s
    content_preview fallback (sources.py:444-451). `_add_entity` only emits a
    `schema:description` triple when `summary` is non-empty, so topics will
    NOT carry a description triple in the graph — that's a known consequence
    of the model layout (see ProjectEntity at entities.py:324; summary lives
    on ThemeEntity at line 466 and MechanismEntity at line 440)."""
    from science_tool.graph.commons_sources import _materialize_commons_entity
    from science_tool.graph.entity_registry import EntityRegistry

    merged = _merged(
        canonical_id="topic:demo",
        kind="topic",
        frontmatter={
            "id": "topic:demo",
            "type": "topic",
            "title": "Demo",
            "schema_profile": "science-entity-base/1.0+topic/2.0",
            "description": "A demo topic.",
        },
    )
    entity = _materialize_commons_entity(
        merged,
        registry=EntityRegistry.with_core_types(),
        project_slug="demo",
        active_kinds=frozenset({"topic"}),
        ontology_catalogs=[],
    )
    # Topic = ProjectEntity. No summary field → pydantic extra=ignore drops it.
    assert getattr(entity, "summary", None) in (None, "")
    # `_enrich_raw`'s content_preview fallback (sources.py:444-451) catches
    # the description so the body text isn't silently lost.
    assert entity.content_preview == "A demo topic."


def test_translate_theme_description_flows_to_summary() -> None:
    """Themes resolve to ThemeEntity, which DOES define `summary` (entities.py:466).
    For themes the description → summary rename is meaningful and survives validation."""
    from science_model.entities import ThemeEntity
    from science_tool.graph.commons_sources import _materialize_commons_entity
    from science_tool.graph.entity_registry import EntityRegistry

    merged = _merged(
        canonical_id="theme:demo",
        kind="theme",
        frontmatter={
            "id": "theme:demo",
            "type": "theme",
            "title": "Demo",
            "schema_profile": "science-entity-base/1.0+theme/2.0",
            "description": "A demo theme.",
        },
    )
    entity = _materialize_commons_entity(
        merged,
        registry=EntityRegistry.with_core_types(),
        project_slug="demo",
        active_kinds=frozenset({"theme"}),
        ontology_catalogs=[],
    )
    assert isinstance(entity, ThemeEntity)
    assert entity.summary == "A demo theme."


def test_translate_dataset_carries_mixin_fields() -> None:
    from science_model.entities import DatasetEntity
    from science_tool.graph.commons_sources import _materialize_commons_entity
    from science_tool.graph.entity_registry import EntityRegistry

    merged = _merged(
        canonical_id="dataset:foo",
        kind="dataset",
        frontmatter={
            "id": "dataset:foo",
            "type": "dataset",
            "title": "Foo",
            "schema_profile": "science-entity-base/1.0+dataset/1.0",
            "origin": "external",
            "access": {"level": "public", "verified": True, "source_url": "https://example.org"},
            "accessions": ["GSE12345"],
            "datapackage": "datapackage.yaml",
        },
        body_path="/abs/commons/datasets/foo/entity.md",
    )
    entity = _materialize_commons_entity(
        merged,
        registry=EntityRegistry.with_core_types(),
        project_slug="demo",
        active_kinds=frozenset({"dataset"}),
        ontology_catalogs=[],
    )
    assert isinstance(entity, DatasetEntity)
    assert entity.origin == "external"
    assert entity.access is not None
    assert entity.accessions == ["GSE12345"]


def test_translate_theme_with_cross_project_scope() -> None:
    from science_model.entities import ThemeEntity
    from science_tool.graph.commons_sources import _materialize_commons_entity
    from science_tool.graph.entity_registry import EntityRegistry

    merged = _merged(
        canonical_id="theme:demo",
        kind="theme",
        frontmatter={
            "id": "theme:demo",
            "type": "theme",
            "title": "Demo",
            "schema_profile": "science-entity-base/1.0+theme/2.0",
            "theme_kind": "conceptual",
            "theme_scope": "cross-project",
        },
    )
    entity = _materialize_commons_entity(
        merged,
        registry=EntityRegistry.with_core_types(),
        project_slug="demo",
        active_kinds=frozenset({"theme"}),
        ontology_catalogs=[],
    )
    assert isinstance(entity, ThemeEntity)
    assert entity.theme_kind == "conceptual"
    assert entity.theme_scope == "cross-project"


def test_translate_drops_overlay_only_fields() -> None:
    """Every overlay-1.1 project-only field listed in `_OVERLAY_ONLY_FIELDS`
    must be dropped pre-validate. Pins parity with overlay-1.1.json: relevance,
    hypothesis_links, task_links, question_links, project_tags, project_notes,
    source. Without explicit drops, pydantic's extra="ignore" would mask
    the contract, but the test asserts the contract directly."""
    from science_tool.graph.commons_sources import _materialize_commons_entity, _OVERLAY_ONLY_FIELDS
    from science_tool.graph.entity_registry import EntityRegistry

    expected_dropped = {
        "relevance", "hypothesis_links", "task_links", "question_links",
        "project_tags", "project_notes", "source",
    }
    assert set(_OVERLAY_ONLY_FIELDS) == expected_dropped, (
        f"_OVERLAY_ONLY_FIELDS must match overlay-1.1.json project-only fields; "
        f"diff: {set(_OVERLAY_ONLY_FIELDS) ^ expected_dropped}"
    )

    merged = _merged(
        canonical_id="topic:demo",
        kind="topic",
        frontmatter={
            "id": "topic:demo",
            "type": "topic",
            "title": "Demo",
            "schema_profile": "science-entity-base/1.0+topic/2.0",
            "relevance": "H1 anchor",
            "hypothesis_links": ["H1"],
            "task_links": ["t1"],
            "question_links": ["q1"],
            "project_tags": ["high-priority"],
            "project_notes": "see also …",
            "source": "internal-curation",
        },
    )
    entity = _materialize_commons_entity(
        merged,
        registry=EntityRegistry.with_core_types(),
        project_slug="demo",
        active_kinds=frozenset({"topic"}),
        ontology_catalogs=[],
    )
    # Every overlay-only field is either absent from the Entity model entirely
    # or carries its default (None / empty list). Iterate the whole drop list
    # so adding/removing entries in _OVERLAY_ONLY_FIELDS triggers a test update.
    for field in _OVERLAY_ONLY_FIELDS:
        value = getattr(entity, field, None)
        assert value in (None, "", [], {}), (
            f"overlay-only field {field!r} leaked onto Entity with value {value!r}"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v -k translate`
Expected: FAIL — `_materialize_commons_entity` is not defined.

- [ ] **Step 3: Add the translator**

In `src/science_tool/graph/commons_sources.py`, **merge** these imports into the existing top-of-file import block (DO NOT append a new import block below the function — ruff `E402` flags module-level imports not at the top of the file):

```python
from science_model.ontologies.schema import OntologyCatalog

from science_tool.commons.overlay import MergedEntity
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import _enrich_raw, _normalize_kind
```

After the existing imports, add the constant and translator function:

```python
_OVERLAY_ONLY_FIELDS = (
    # Per overlay-1.1.json: every project-only key that has no Entity field.
    # Pydantic's extra="ignore" would silently drop them anyway, but explicit
    # drops are part of the §5.4 contract and keep this list auditable when
    # overlay-1.x grows.
    "relevance",
    "hypothesis_links",
    "task_links",
    "question_links",
    "project_tags",
    "project_notes",
    "source",
)


def _materialize_commons_entity(
    merged: MergedEntity,
    *,
    registry: EntityRegistry,
    project_slug: str,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> Entity:
    """Translate a MergedEntity into a typed Entity (pass-through + normalize).

    The merged frontmatter flows into the raw Entity dict verbatim. Only the
    fields whose names or shapes differ between commons and the Entity model
    are normalized; everything else is carried through and either populates
    matching Entity fields or is silently dropped by pydantic's `extra=ignore`.

    Per design §4.3.
    """
    fm = dict(merged.merged_frontmatter)
    kind = _normalize_kind(fm["type"])
    schema = registry.resolve(kind)  # raises EntityKindNotRegisteredError if not registered

    raw: dict[str, object] = dict(fm)
    raw["kind"] = kind
    raw["canonical_id"] = fm["id"]
    if "description" in fm and "summary" not in fm:
        raw["summary"] = fm["description"]
    raw["scope"] = "shared"
    raw["profile"] = "shared"
    raw["file_path"] = str(merged.canonical.body_path)

    for overlay_only in _OVERLAY_ONLY_FIELDS:
        raw.pop(overlay_only, None)
    raw.pop("schema_profile", None)
    # commons frontmatter "id" is replaced by canonical_id above; Entity carries both,
    # but keeping the literal "id" key flows it back through _enrich_raw harmlessly.

    _enrich_raw(
        raw,
        kind=kind,
        project_slug=project_slug,
        local_profile="shared",
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )
    return schema.model_validate(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v -k translate`
Expected: PASS.

- [ ] **Step 5: Run the full commons-sources test file**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v`
Expected: every test passes — both the collector (Task 6) and the translator.

- [ ] **Step 6: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 7: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/commons_sources.py science/tests/test_graph_commons_sources.py
git commit -m "feat(graph): add pass-through commons entity translator"
```

---

### Task 8: Add `_load_commons_referenced_entities` orchestrator

**Files:**
- Modify: `src/science_tool/graph/commons_sources.py`
- Modify: `tests/test_graph_commons_sources.py`

Background: Per design §4.2 + §4.4, the orchestrator collects refs (Task 6) and overlay records (`OverlayAdapter.scan`), unions them, then for each canonical_id either loads from commons + merges + translates, or — when the canonical is missing — handles two cases:

- **Referenced-only missing** → SKIP (returns nothing for this id; existing audit path will emit `unresolved_reference`).
- **Overlay-anchored missing** (orphan overlay) → raise `OverlayValidationError` with the overlay path.

Returns `tuple[list[tuple[Entity, SourceRef]], dict[str, str]]` where the second element is the `canonical_id → overlay_path` map.

The function does NOT mutate `identity_table` or `entities` itself — that wiring lives in `load_project_sources` (Task 9). Keeping the orchestrator pure(-ish) makes it easier to unit-test.

- [ ] **Step 1: Write the failing tests using the existing commons fixture**

The `tests/fixtures/commons/valid/` tree already contains a working commons store with `topic:single-cell-foundation-models`, `paper:Adams2025`, `theme:research-hygiene`, `dataset:cath-domains`, `dataset:rnaseq-example`. Reuse it via the pattern in `tests/test_commons_inventory.py`.

In `tests/test_graph_commons_sources.py`, **merge** this import into the existing top-of-file import block (do NOT add it inline below existing helpers — ruff `E402` rejects mid-file module imports):

```python
import shutil
```

`pytest` and `Path` are already imported (Tasks 6 and 7). Then append the helper + tests at the bottom of the file:

```python
_COMMONS_FIXTURE = Path(__file__).parent / "fixtures" / "commons" / "valid"


def _build_commons(tmp_path: Path) -> Path:
    root = tmp_path / "commons"
    shutil.copytree(_COMMONS_FIXTURE, root)
    # CommonsQuery requires a built registry.
    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    return root


def test_orchestrator_loads_referenced_topic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_model.identity import EntityScope
    from science_tool.graph.commons_sources import _load_commons_referenced_entities
    from science_tool.graph.entity_registry import EntityRegistry

    root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    project = tmp_path / "project"
    project.mkdir()

    entities = [_entity("hypothesis:h1", related=["topic:single-cell-foundation-models"])]
    loaded, overlay_paths = _load_commons_referenced_entities(
        project_root=project,
        project_slug="demo",
        project_entities=entities,
        project_relations=[],
        project_bindings=[],
        identity_table={},
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset({"topic"}),
        ontology_catalogs=[],
    )
    assert len(loaded) == 1
    entity, ref = loaded[0]
    assert entity.canonical_id == "topic:single-cell-foundation-models"
    assert entity.scope is EntityScope.SHARED
    assert ref.adapter_name == "commons-merged"
    assert overlay_paths == {}


def test_orchestrator_skips_referenced_missing_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.graph.commons_sources import _load_commons_referenced_entities
    from science_tool.graph.entity_registry import EntityRegistry

    root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    project = tmp_path / "project"
    project.mkdir()
    entities = [_entity("hypothesis:h1", related=["topic:does-not-exist"])]
    loaded, _ = _load_commons_referenced_entities(
        project_root=project,
        project_slug="demo",
        project_entities=entities,
        project_relations=[],
        project_bindings=[],
        identity_table={},
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset({"topic"}),
        ontology_catalogs=[],
    )
    # Referenced-only missing canonical: skipped (audit path handles it later).
    assert loaded == []


def test_orchestrator_raises_on_orphan_overlay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.errors import OverlayValidationError
    from science_tool.graph.commons_sources import _load_commons_referenced_entities
    from science_tool.graph.entity_registry import EntityRegistry

    root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    project = tmp_path / "project"
    overlay_dir = project / "doc" / "topics"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "orphan.md").write_text(
        "---\n"
        'id: "topic:orphan"\n'
        'overlay_of: "topic:orphan"\n'
        "tags: [\"x\"]\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    with pytest.raises(OverlayValidationError) as excinfo:
        _load_commons_referenced_entities(
            project_root=project,
            project_slug="demo",
            project_entities=[],
            project_relations=[],
            project_bindings=[],
            identity_table={},
            registry=EntityRegistry.with_core_types(),
            active_kinds=frozenset({"topic"}),
            ontology_catalogs=[],
        )
    assert excinfo.value.canonical_id == "topic:orphan"


def test_orchestrator_loads_overlay_without_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.graph.commons_sources import _load_commons_referenced_entities
    from science_tool.graph.entity_registry import EntityRegistry

    root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    project = tmp_path / "project"
    overlay_dir = project / "doc" / "topics"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "single-cell-foundation-models.md").write_text(
        "---\n"
        'id: "topic:single-cell-foundation-models"\n'
        'overlay_of: "topic:single-cell-foundation-models"\n'
        "tags: [\"overlay-added\"]\n"
        "---\nproject notes\n",
        encoding="utf-8",
    )
    loaded, overlay_paths = _load_commons_referenced_entities(
        project_root=project,
        project_slug="demo",
        project_entities=[],
        project_relations=[],
        project_bindings=[],
        identity_table={},
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset({"topic"}),
        ontology_catalogs=[],
    )
    assert len(loaded) == 1
    entity, _ = loaded[0]
    assert entity.canonical_id == "topic:single-cell-foundation-models"
    assert overlay_paths == {
        "topic:single-cell-foundation-models": str(overlay_dir / "single-cell-foundation-models.md"),
    }


def test_orchestrator_no_overlays_no_refs_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.graph.commons_sources import _load_commons_referenced_entities
    from science_tool.graph.entity_registry import EntityRegistry

    # Point commons root at a non-existent path; helper must NOT touch it.
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    project = tmp_path / "project"
    project.mkdir()
    loaded, overlay_paths = _load_commons_referenced_entities(
        project_root=project,
        project_slug="demo",
        project_entities=[],
        project_relations=[],
        project_bindings=[],
        identity_table={},
        registry=EntityRegistry.with_core_types(),
        active_kinds=frozenset(),
        ontology_catalogs=[],
    )
    assert loaded == []
    assert overlay_paths == {}


def test_orchestrator_raises_when_commons_missing_but_overlays_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.errors import CommonsRootNotFoundError
    from science_tool.graph.commons_sources import _load_commons_referenced_entities
    from science_tool.graph.entity_registry import EntityRegistry

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    project = tmp_path / "project"
    overlay_dir = project / "doc" / "topics"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "single-cell-foundation-models.md").write_text(
        "---\n"
        'id: "topic:single-cell-foundation-models"\n'
        'overlay_of: "topic:single-cell-foundation-models"\n'
        "tags: [\"x\"]\n"
        "---\nbody\n",
        encoding="utf-8",
    )

    with pytest.raises(CommonsRootNotFoundError):
        _load_commons_referenced_entities(
            project_root=project,
            project_slug="demo",
            project_entities=[],
            project_relations=[],
            project_bindings=[],
            identity_table={},
            registry=EntityRegistry.with_core_types(),
            active_kinds=frozenset({"topic"}),
            ontology_catalogs=[],
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v -k orchestrator`
Expected: FAIL — `_load_commons_referenced_entities` is not defined.

- [ ] **Step 3: Implement the orchestrator**

In `src/science_tool/graph/commons_sources.py`, **merge** these imports into the existing top-of-file import block (DO NOT add a fresh import block below the existing function — ruff `E402` would reject it):

```python
import logging
from pathlib import Path

from science_model.entity_schema import parse_profile, read_merge_policy
from science_model.source_ref import SourceRef

from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsRootNotFoundError,
    OverlayValidationError,
)
from science_tool.commons.overlay import OverlayAdapter, merge_entity
from science_tool.commons.query import CommonsQuery
```

After the existing imports (but still at module top level), add the module-level constant + logger:

```python
logger = logging.getLogger(__name__)

_TYPE_TO_DIR = {"dataset": "datasets", "paper": "papers", "topic": "topics", "theme": "themes"}
```

Then append the function body at the end of the module:

```python
def _load_commons_referenced_entities(
    *,
    project_root: Path,
    project_slug: str,
    project_entities: list[Entity],
    project_relations: list[SourceRelation],
    project_bindings: list[BindingSource],
    identity_table: dict[str, SourceRef],
    registry: EntityRegistry,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> tuple[list[tuple[Entity, SourceRef]], dict[str, str]]:
    """Load commons-referenced and overlay-anchored entities for the project.

    Returns a list of (Entity, SourceRef) tuples ready to be appended to
    `ProjectSources.entities` plus a `canonical_id -> overlay_path` map for
    dual-source provenance emission. The caller wires both into ProjectSources
    and identity_table.

    Strict semantics:
      - Orphan overlay (overlay file exists, commons has no canonical) →
        OverlayValidationError.
      - Referenced-only missing canonical → skipped (audit path handles it).
      - Commons root absent AND project has either overlays or refs →
        CommonsRootNotFoundError.
      - Commons root absent AND project has neither → silent no-op (DEBUG log).
    """
    # Discover overlays first; their presence is one of the gate conditions.
    overlays_by_id: dict[str, "OverlayRecord"] = {}
    overlay_dir = project_root / "doc"
    if overlay_dir.is_dir():
        for record_or_error in OverlayAdapter(project_root, project_slug).scan():
            if isinstance(record_or_error, OverlayValidationError):
                raise record_or_error
            overlays_by_id[record_or_error.canonical_id] = record_or_error

    referenced = collect_referenced_commons_ids(
        project_entities=project_entities,
        project_relations=project_relations,
        project_bindings=project_bindings,
    )
    # Strip already-locally-registered ids: they're loaded by the regular adapter loop.
    referenced = {rid for rid in referenced if rid not in identity_table}

    needed: set[str] = referenced | overlays_by_id.keys()
    if not needed:
        return [], {}

    commons_root = resolve_commons_root()
    if not commons_root.is_dir():
        raise CommonsRootNotFoundError(commons_root)

    commons_query = CommonsQuery(commons_root)

    loaded: list[tuple[Entity, SourceRef]] = []
    overlay_paths: dict[str, str] = {}

    for canonical_id in sorted(needed):
        overlay = overlays_by_id.get(canonical_id)
        try:
            record = commons_query.show(canonical_id)
        except CommonsEntityError as exc:
            if overlay is not None:
                raise OverlayValidationError(
                    overlay.overlay_path, canonical_id=canonical_id, cause=exc
                ) from exc
            # Referenced-only and missing canonical → skip; audit will report it.
            continue

        if overlay is not None and (overlay.pin_version or overlay.pin_effective_version):
            logger.warning(
                "overlay %s sets pin_version=%r / pin_effective_version=%r; "
                "pinning is not enforced (warn-only per design §6.2)",
                overlay.overlay_path,
                overlay.pin_version,
                overlay.pin_effective_version,
            )

        policy = read_merge_policy(parse_profile(record.schema_profile))
        merged = merge_entity(record, overlay, policy)
        entity = _materialize_commons_entity(
            merged,
            registry=registry,
            project_slug=project_slug,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )
        type_dir = _TYPE_TO_DIR.get(entity.kind, entity.kind)
        slug = canonical_id.split(":", 1)[1]
        # Datasets in commons live at datasets/<slug>/entity.md (see
        # commons/adapter.py:_scan_type's `entity.md` lookup); other types
        # live at <type_dir>/<slug>.md.
        if entity.kind == "dataset":
            commons_path = f"commons://datasets/{slug}/entity.md"
        else:
            commons_path = f"commons://{type_dir}/{slug}.md"
        ref = SourceRef(
            adapter_name="commons-merged",
            path=commons_path,
        )
        loaded.append((entity, ref))
        if overlay is not None:
            overlay_paths[canonical_id] = str(overlay.overlay_path)

    return loaded, overlay_paths
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v -k orchestrator`
Expected: PASS.

- [ ] **Step 5: Run the entire commons-sources test file**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v`
Expected: every test passes (collector + translator + orchestrator).

- [ ] **Step 6: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 7: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/commons_sources.py science/tests/test_graph_commons_sources.py
git commit -m "feat(graph): add commons-source orchestrator with strict failure model"
```

---

### Task 9: Wire `_load_commons_referenced_entities` into `load_project_sources`

**Files:**
- Modify: `src/science_tool/graph/sources.py:154-351` (the `load_project_sources` function)
- Test: `tests/test_graph_commons_sources.py` (extend with integration tests)

Background: Per design §3.1, the new pass runs as a tail-call **after** relations + bindings load, so the collector sees refs from all three sources. After collecting, the loop appends each commons entity to `identity_table` and `entities`, then re-sorts `entities`. `ProjectSources.commons_overlay_paths` is populated from the helper's second return value. `EntityIdentityCollisionError` guard stays — defense in depth.

- [ ] **Step 1: Write the failing integration test**

In `tests/test_graph_commons_sources.py`, append:

```python
def test_load_project_sources_pulls_commons_referenced_topic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end through load_project_sources: a hypothesis referencing a
    commons topic causes the topic to enter ProjectSources.entities."""
    from science_tool.graph.sources import load_project_sources

    root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    project = tmp_path / "project"
    project.mkdir()
    # Minimal science.yaml.
    (project / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )
    # Empty local profile manifest.
    sources_dir = project / "knowledge" / "sources" / "local"
    sources_dir.mkdir(parents=True)
    (sources_dir / "manifest.yaml").write_text("name: local\nentity_kinds: []\n", encoding="utf-8")
    # A hypothesis that references the commons topic.
    specs_dir = project / "specs" / "hypotheses"
    specs_dir.mkdir(parents=True)
    (specs_dir / "h1.md").write_text(
        "---\n"
        'id: "hypothesis:h1"\n'
        'type: "hypothesis"\n'
        'title: "Hypothesis 1"\n'
        'related: ["topic:single-cell-foundation-models"]\n'
        "---\nbody\n",
        encoding="utf-8",
    )

    sources = load_project_sources(project)
    ids = {entity.canonical_id for entity in sources.entities}
    assert "hypothesis:h1" in ids
    assert "topic:single-cell-foundation-models" in ids
    # Entities list is fully sorted.
    canonical_ids = [entity.canonical_id for entity in sources.entities]
    assert canonical_ids == sorted(canonical_ids)
    # No overlay → empty overlay_paths.
    assert sources.commons_overlay_paths == {}


def test_load_project_sources_populates_overlay_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When an overlay exists, ProjectSources.commons_overlay_paths records it."""
    from science_tool.graph.sources import load_project_sources

    root = _build_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8",
    )
    sources_dir = project / "knowledge" / "sources" / "local"
    sources_dir.mkdir(parents=True)
    (sources_dir / "manifest.yaml").write_text("name: local\nentity_kinds: []\n", encoding="utf-8")
    overlay_dir = project / "doc" / "topics"
    overlay_dir.mkdir(parents=True)
    overlay_path = overlay_dir / "single-cell-foundation-models.md"
    overlay_path.write_text(
        "---\n"
        'id: "topic:single-cell-foundation-models"\n'
        'overlay_of: "topic:single-cell-foundation-models"\n'
        "tags: [\"overlay-added\"]\n"
        "---\nproject notes\n",
        encoding="utf-8",
    )

    sources = load_project_sources(project)
    assert sources.commons_overlay_paths == {
        "topic:single-cell-foundation-models": str(overlay_path),
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v -k load_project_sources`
Expected: FAIL — `load_project_sources` doesn't yet invoke the commons-loading pass.

- [ ] **Step 3: Add the call site in `load_project_sources` (lazy import to avoid the cycle)**

`commons_sources.py` imports `SourceRelation`, `is_external_reference`, `is_metadata_reference`, and `_enrich_raw` from `sources.py` at module top level (Tasks 6, 7). A reciprocal top-level import in `sources.py` would create a circular import that fails on cold load (Python evaluates `sources.py` top-to-bottom; commons_sources triggers a re-entrant import of `sources` before `SourceRelation` is bound). Resolve this by importing inside the function — `commons_sources.py` is only loaded when `load_project_sources` is actually called, which is well after `sources.py` has finished initializing.

In `src/science_tool/graph/sources.py`, **do NOT add a module-level import**. Instead, in `load_project_sources` (line 154), locate the block after `bindings.sort(...)` (line 336) and **before** the `return ProjectSources(...)` (line 338). Insert:

```python
    from science_tool.graph.commons_sources import _load_commons_referenced_entities

    commons_loaded, commons_overlay_paths = _load_commons_referenced_entities(
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
    for entity, ref in commons_loaded:
        existing = identity_table.get(entity.canonical_id)
        if existing is not None:
            raise EntityIdentityCollisionError(entity.canonical_id, existing, ref)
        identity_table[entity.canonical_id] = ref
        entities.append(entity)
        entity_source_adapters[entity.canonical_id] = ref.adapter_name

    entities.sort(key=lambda e: e.canonical_id)
```

And in the `return ProjectSources(...)` call, add the field:

```python
        commons_overlay_paths=commons_overlay_paths,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_sources.py -v -k load_project_sources`
Expected: PASS.

- [ ] **Step 5: Run the full graph + commons test suites for regression**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_*.py tests/test_commons_*.py -q`
Expected: every test still passes.

- [ ] **Step 6: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 7: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/sources.py science/tests/test_graph_commons_sources.py
git commit -m "feat(graph): wire commons-source loading into load_project_sources"
```

---

### Task 10: Thread `commons_overlay_paths` through `materialize_graph` → `_add_entity`

**Files:**
- Modify: `src/science_tool/graph/materialize.py` (find `_add_entity` call sites in `_build_dataset_from_sources` or `materialize_graph`)
- Test: `tests/test_graph_materialize.py` (extend with E2E test)

Background: `_add_entity` now accepts an `overlay_paths` kwarg (Task 4). The materialize call chain must pass `sources.commons_overlay_paths` down to every `_add_entity` invocation. The actual call site lives in the loop that walks `sources.entities` (probably inside `_build_dataset_from_sources` near line 57). Grep first; the design doesn't pin the exact line.

- [ ] **Step 1: Locate the `_add_entity` call site**

Run: `grep -n "_add_entity(" ~/d/science/science/src/science_tool/graph/materialize.py`
You should see one call site that iterates over `sources.entities`. Confirm before editing.

- [ ] **Step 2: Write the failing E2E test**

In `tests/test_graph_materialize.py`, add (modeling on the existing fixture pattern + reusing the `_build_commons` helper if it lives in this file, else inline it):

```python
def test_materialize_with_commons_topic_emits_scope_and_dual_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E2E: materialize a project that references a commons topic AND overlays it.
    Expect the resulting trig to contain (a) sci:scope "cross-project" for the
    commons entity, (b) two prov:wasDerivedFrom triples (commons body + overlay)."""
    import shutil
    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder
    from science_tool.graph.materialize import materialize_graph

    commons_root = tmp_path / "commons"
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "commons" / "valid",
        commons_root,
    )
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))

    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8",
    )
    sources_dir = project / "knowledge" / "sources" / "local"
    sources_dir.mkdir(parents=True)
    (sources_dir / "manifest.yaml").write_text("name: local\nentity_kinds: []\n", encoding="utf-8")
    specs_dir = project / "specs" / "hypotheses"
    specs_dir.mkdir(parents=True)
    (specs_dir / "h1.md").write_text(
        "---\n"
        'id: "hypothesis:h1"\n'
        'type: "hypothesis"\n'
        'title: "Hypothesis 1"\n'
        'related: ["topic:single-cell-foundation-models"]\n'
        "---\nbody\n",
        encoding="utf-8",
    )
    overlay_dir = project / "doc" / "topics"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / "single-cell-foundation-models.md").write_text(
        "---\n"
        'id: "topic:single-cell-foundation-models"\n'
        'overlay_of: "topic:single-cell-foundation-models"\n'
        "tags: [\"overlay-added\"]\n"
        "---\nproject notes\n",
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    # Parse the TriG instead of grepping the text: rdflib may group multiple
    # objects under a single predicate (`a prov:wasDerivedFrom <X>, <Y>`),
    # which would make a string-count assertion serializer-fragile.
    from rdflib import Dataset
    from rdflib.namespace import PROV
    from science_tool.graph.materialize import _entity_uri
    from science_tool.graph.store import SCI_NS

    ds = Dataset()
    ds.parse(trig_path, format="trig")

    commons_uri = _entity_uri("topic:single-cell-foundation-models")
    # The commons entity carries scope = "cross-project" in any named graph.
    scope_values = {
        str(obj) for _, _, obj, _ in ds.quads((commons_uri, SCI_NS.scope, None, None))
    }
    assert "cross-project" in scope_values

    # Two distinct prov:wasDerivedFrom objects from the commons entity:
    # one for the commons body, one for the project overlay.
    derived = {
        str(obj)
        for _, _, obj, _ in ds.quads((commons_uri, PROV.wasDerivedFrom, None, None))
    }
    assert len(derived) >= 2
    # The slugified overlay path is one of them.
    assert any("single-cell-foundation-models.md" in uri for uri in derived)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_materialize.py::test_materialize_with_commons_topic_emits_scope_and_dual_provenance -v`
Expected: FAIL — at minimum the overlay provenance triple is missing because `_add_entity` is not being called with `overlay_paths`.

- [ ] **Step 4: Thread `overlay_paths` through the call chain**

In `src/science_tool/graph/materialize.py`, locate the `_add_entity(...)` call site (found in Step 1; typically inside `_build_dataset_from_sources`) and update the invocation:

```python
        _add_entity(
            entity=entity,
            knowledge=knowledge,
            provenance=provenance,
            overlay_paths=sources.commons_overlay_paths,
        )
```

(If the call site has positional args, convert to keyword. Confirm `sources` is in scope at the call site — it should be: `_build_dataset_from_sources` receives `sources: ProjectSources`.)

- [ ] **Step 5: Run the failing test again**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_materialize.py::test_materialize_with_commons_topic_emits_scope_and_dual_provenance -v`
Expected: PASS.

- [ ] **Step 6: Run the full graph test suite**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_*.py -q`
Expected: every test still passes.

- [ ] **Step 7: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 8: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/materialize.py science/tests/test_graph_materialize.py
git commit -m "feat(graph): emit overlay provenance during materialize"
```

---

### Task 11: Enrich audit message for commons-typed unresolved refs

**Files:**
- Modify: `src/science_tool/graph/migrate.py` (the `_audit_reference`, `_audit_relation_endpoint`, `_audit_binding_endpoint` templates)
- Test: `tests/test_graph_migrate.py` (extend)

Background: Per design §6.3, when an unresolved ref is `<type>:<slug>` with `<type> ∈ {dataset, paper, topic, theme}`, the audit row's `details` field gains a hint pointing at the commons path that *would* have resolved it. The audit row's `check` value stays `"unresolved_reference"` (no new check type). Purely informational.

- [ ] **Step 1: Write the failing test**

This test must point `SCIENCE_COMMONS_ROOT` at a real, built commons fixture — otherwise Task 9's loader will raise `CommonsRootNotFoundError` before the audit ever runs (the project has a commons-typed ref, so the "silent no-op when no commons activity" branch doesn't apply). Use the existing `tests/fixtures/commons/valid` fixture: it has `topic:single-cell-foundation-models` but NOT `topic:does-not-exist`, so the loader skips the missing canonical and lets the audit emit the row.

In `tests/test_graph_migrate.py`, **merge** the `import shutil` line into the existing top-of-file import block (do NOT introduce it inline above the new test — ruff `E402` rejects mid-file module imports), then append the test function at the end of the file:

```python
def test_audit_unresolved_topic_includes_commons_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unresolved <commons-type>:<slug> ref enriches the audit detail
    with a pointer to ~/d/science-commons/<type-dir>/<slug>.md."""
    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder
    from science_tool.graph.migrate import audit_project_sources
    from science_tool.graph.sources import load_project_sources

    # Stand up a real built commons that simply does not contain the
    # `topic:does-not-exist` canonical. Without this, Task 9's loader would
    # raise CommonsRootNotFoundError on a project that references any commons
    # type with no commons root present.
    commons_root = tmp_path / "commons"
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "commons" / "valid",
        commons_root,
    )
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))

    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8",
    )
    sources_dir = project / "knowledge" / "sources" / "local"
    sources_dir.mkdir(parents=True)
    (sources_dir / "manifest.yaml").write_text("name: local\nentity_kinds: []\n", encoding="utf-8")
    specs_dir = project / "specs" / "hypotheses"
    specs_dir.mkdir(parents=True)
    (specs_dir / "h1.md").write_text(
        "---\n"
        'id: "hypothesis:h1"\n'
        'type: "hypothesis"\n'
        'title: "Hypothesis 1"\n'
        'related: ["topic:does-not-exist"]\n'
        "---\nbody\n",
        encoding="utf-8",
    )
    sources = load_project_sources(project)
    rows, has_failures = audit_project_sources(sources)
    assert has_failures
    bad = next(r for r in rows if r["target"] == "topic:does-not-exist")
    assert bad["check"] == "unresolved_reference"
    assert "topics/does-not-exist.md" in bad["details"]
    assert "science commons promote" in bad["details"] or "commons" in bad["details"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_migrate.py::test_audit_unresolved_topic_includes_commons_hint -v`
Expected: FAIL — the existing `details` strings don't include a commons hint.

- [ ] **Step 3: Add a small helper in `graph/migrate.py`**

Near the top of `src/science_tool/graph/migrate.py` (after the existing module-level helpers), add:

```python
_COMMONS_TYPE_TO_DIR = {"dataset": "datasets", "paper": "papers", "topic": "topics", "theme": "themes"}


def _commons_hint_for(target: str) -> str:
    """Return a commons-promotion hint suffix for a commons-typed canonical id,
    or an empty string for non-commons types. Purely informational; no I/O.

    Datasets live at datasets/<slug>/entity.md in commons (see
    `commons/adapter.py`); other commons types live at <type_dir>/<slug>.md.
    """
    if ":" not in target:
        return ""
    type_part, slug = target.split(":", 1)
    type_dir = _COMMONS_TYPE_TO_DIR.get(type_part)
    if type_dir is None:
        return ""
    if type_part == "dataset":
        canonical_path = f"~/d/science-commons/datasets/{slug}/entity.md"
    else:
        canonical_path = f"~/d/science-commons/{type_dir}/{slug}.md"
    return (
        f" (no local entity, no commons canonical at {canonical_path} — "
        f"run `science commons promote {type_part} --from <project>` if {target} "
        f"should be promoted, or check the ref's spelling)"
    )
```

Then update the three audit-row constructors that emit `"check": "unresolved_reference"`:

a. In `_audit_binding_endpoint` (line ~543-553): append `+ _commons_hint_for(raw_target)` to the `details` string.
b. In `_audit_relation_endpoint` (line ~580-593): same.
c. In `_audit_reference` (line ~596+ — find the unresolved-reference branch and apply the same suffix).

Apply each call site by changing:

```python
"details": f"{...} references an unknown canonical entity",
```

to:

```python
"details": f"{...} references an unknown canonical entity"
            + _commons_hint_for(raw_target),
```

- [ ] **Step 4: Run the failing test**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_migrate.py::test_audit_unresolved_topic_includes_commons_hint -v`
Expected: PASS.

- [ ] **Step 5: Run the full migrate test suite**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_migrate.py -q`
Expected: every test still passes (the audit-row tests pin specific `details` substrings — verify by grep that none rely on `details` being literally equal rather than substring-matched; if any do, update them to also accept the hint suffix).

- [ ] **Step 6: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 7: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/graph/migrate.py science/tests/test_graph_migrate.py
git commit -m "feat(graph): enrich unresolved-ref audit message with commons hint"
```

---

### Task 12: mm30 canary fixture + test

**Files:**
- Create: `tests/fixtures/commons_mm30_canary/commons/topics/cancer-as-singular-evolutionary-disease.md`
- Create: `tests/fixtures/commons_mm30_canary/commons/topics/formal-causal-mediation.md`
- Create: `tests/fixtures/commons_mm30_canary/commons/topics/causal-inference-biology-foundations.md`
- Create: `tests/fixtures/commons_mm30_canary/commons/topics/epigenetic-chromatin-mm-progression.md`
- Create: `tests/fixtures/commons_mm30_canary/project/science.yaml`
- Create: `tests/fixtures/commons_mm30_canary/project/knowledge/sources/local/manifest.yaml`
- Create: `tests/fixtures/commons_mm30_canary/project/specs/hypotheses/h4-attractor-convergence.md`
- Create: `tests/fixtures/commons_mm30_canary/project/doc/interpretations/2026-04-23-t650-demo.md`
- Create: `tests/fixtures/commons_mm30_canary/project/tasks/active.md`
- Create: `tests/fixtures/commons_mm30_canary/project/doc/topics/epigenetic-chromatin-mm-progression.md` (overlay)
- Create: `tests/test_graph_commons_mm30_canary.py`

Background: Per design §7.4, four mm30-shaped patterns. Build a minimal commons stub and project tree that reproduces each, then assert that `materialize_graph` succeeds and that the expected commons entities entered the graph. The 4 mm30 example topic IDs come from the design table:

| Pattern | Topic ID |
|---|---|
| Hypothesis spec → commons topic | `topic:cancer-as-singular-evolutionary-disease` |
| Interpretation → commons topic | `topic:formal-causal-mediation` |
| Task → commons topic | `topic:causal-inference-biology-foundations` |
| Overlay + outbound ref to same topic | `topic:epigenetic-chromatin-mm-progression` |

- [ ] **Step 1: Create the commons stub topics**

For each of the four topic ids above, create a minimal commons topic file. Example for the first:

`tests/fixtures/commons_mm30_canary/commons/topics/cancer-as-singular-evolutionary-disease.md`:

```markdown
---
schema_profile: science-entity-base/1.0+topic/2.0
id: topic:cancer-as-singular-evolutionary-disease
type: topic
title: Cancer as a singular evolutionary disease
version: "1.0.0"
created: "2026-05-01"
updated: "2026-05-01"
tags: []
related: []
---
Canary stub.
```

Repeat for the other three slugs (just change `id`, `title`, and `slug` in the filename).

- [ ] **Step 2: Create the project science.yaml and manifest**

`tests/fixtures/commons_mm30_canary/project/science.yaml`:

```yaml
name: mm30-canary
knowledge_profiles:
  local: local
```

`tests/fixtures/commons_mm30_canary/project/knowledge/sources/local/manifest.yaml`:

```yaml
name: local
entity_kinds: []
```

- [ ] **Step 3: Create the hypothesis spec that references a commons topic**

`tests/fixtures/commons_mm30_canary/project/specs/hypotheses/h4-attractor-convergence.md`:

```markdown
---
id: "hypothesis:h4-attractor-convergence"
type: "hypothesis"
title: "H4 attractor convergence"
related:
  - "topic:cancer-as-singular-evolutionary-disease"
  - "topic:epigenetic-chromatin-mm-progression"
---
Hypothesis body.
```

- [ ] **Step 4: Create the interpretation doc**

`tests/fixtures/commons_mm30_canary/project/doc/interpretations/2026-04-23-t650-demo.md`:

```markdown
---
id: "interpretation:2026-04-23-t650-demo"
type: "interpretation"
title: "T650 demo interpretation"
related:
  - "topic:formal-causal-mediation"
---
Interpretation body.
```

- [ ] **Step 5: Create the task DSL file**

`TaskAdapter` parses the task DSL — `tasks/*.md` files that contain `## [tNNN] title` headers, not typed markdown frontmatter. See `src/science_tool/tasks.py:32` (the `_TASK_ID_PATTERN = r"t[0-9]{3,}"` constraint and the `## [<id>] <title>` header regex) and `src/science_tool/graph/storage_adapters/task.py:33` (`parse_tasks(path)`).

`tests/fixtures/commons_mm30_canary/project/tasks/active.md`:

```markdown
## [t286] Demo task referencing a commons topic
- type: research
- priority: P1
- status: active
- created: 2026-04-20
- related: [topic:causal-inference-biology-foundations]

Task body.
```

The required fields are `type`, `priority`, `status`, `created` (per `tasks.py:_required_field` checks). `related:` is a bracketed comma-separated list per `tasks.py:_parse_list_value`. A reference template is at `tests/fixtures/spec_y_kitchen_sink/tasks/active.md`.

- [ ] **Step 6: Create the overlay file**

`tests/fixtures/commons_mm30_canary/project/doc/topics/epigenetic-chromatin-mm-progression.md`:

```markdown
---
id: "topic:epigenetic-chromatin-mm-progression"
overlay_of: "topic:epigenetic-chromatin-mm-progression"
tags: ["mm30-overlay"]
---
Project-specific notes for this topic.
```

- [ ] **Step 7: Write the canary tests**

Create `tests/test_graph_commons_mm30_canary.py`:

```python
"""mm30-shaped canary tests for graph build × commons-overlay integration.

Reproduces the four patterns observed in mm30 (commit d4701ff): hypothesis,
interpretation, and task files referencing commons topics, plus a project
overlay carrying the same topic id as an inbound reference.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder

_FIXTURE = Path(__file__).parent / "fixtures" / "commons_mm30_canary"


def _stage_fixture(tmp_path: Path) -> tuple[Path, Path]:
    commons = tmp_path / "commons"
    project = tmp_path / "project"
    shutil.copytree(_FIXTURE / "commons", commons)
    shutil.copytree(_FIXTURE / "project", project)
    RegistryBuilder(commons, CommonsEntityAdapter(commons)).rebuild()
    return project, commons


def test_canary_hypothesis_ref_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.graph.sources import load_project_sources

    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    sources = load_project_sources(project)
    ids = {entity.canonical_id for entity in sources.entities}
    assert "topic:cancer-as-singular-evolutionary-disease" in ids


def test_canary_interpretation_ref_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.graph.sources import load_project_sources

    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    sources = load_project_sources(project)
    ids = {entity.canonical_id for entity in sources.entities}
    assert "topic:formal-causal-mediation" in ids


def test_canary_task_ref_resolves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.graph.sources import load_project_sources

    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    sources = load_project_sources(project)
    ids = {entity.canonical_id for entity in sources.entities}
    assert "topic:causal-inference-biology-foundations" in ids


def test_canary_overlay_and_inbound_ref_share_single_entity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Overlay + outbound ref to the same id → ONE entity in the project graph,
    not two; provenance carries both commons body and overlay paths."""
    from science_tool.graph.sources import load_project_sources

    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    sources = load_project_sources(project)
    matching = [e for e in sources.entities if e.canonical_id == "topic:epigenetic-chromatin-mm-progression"]
    assert len(matching) == 1
    assert "topic:epigenetic-chromatin-mm-progression" in sources.commons_overlay_paths


def test_canary_materialize_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The end-to-end build that previously failed with unresolved refs now
    succeeds. This is the integration acceptance test."""
    from science_tool.graph.materialize import materialize_graph

    project, commons = _stage_fixture(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    trig_path = materialize_graph(project)
    assert trig_path.exists()
    # Parse the TriG rather than text-grep, for serializer robustness.
    from rdflib import Dataset
    from science_tool.graph.materialize import _entity_uri
    from science_tool.graph.store import SCI_NS

    ds = Dataset()
    ds.parse(trig_path, format="trig")
    cancer_uri = _entity_uri("topic:cancer-as-singular-evolutionary-disease")
    scope_values = {
        str(obj) for _, _, obj, _ in ds.quads((cancer_uri, SCI_NS.scope, None, None))
    }
    assert "cross-project" in scope_values
```

- [ ] **Step 8: Run the canary tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_graph_commons_mm30_canary.py -v`
Expected: PASS.

- [ ] **Step 9: Run the full test suite as a regression check**

Run: `cd ~/d/science/science && uv run pytest -q`
Expected: every test passes.

- [ ] **Step 10: Format + lint**

Run: `cd ~/d/science/science && uv run ruff format && uv run ruff check`

- [ ] **Step 11: Commit**

```bash
cd ~/d/science && git add science/tests/fixtures/commons_mm30_canary science/tests/test_graph_commons_mm30_canary.py
git commit -m "test(graph): add mm30 commons-overlay canary fixture and tests"
```

---

### Task 13: Run the mm30 acceptance test (manual, not CI)

**Files:** none modified.

Background: Per design §7.5, once the test suite passes, run `science graph build` against the live mm30 repo. mm30 currently fails with 65 unresolved `topic:*` references after Phase F commit `d4701ff`. Expected post-feature outcome: build succeeds, the 65 unresolved refs (16 unique topic ids + 1 dataset id) resolve cleanly, and `validate.sh` warning count drops.

This task is a manual integration check that produces no artifacts in `~/d/science`. It validates the implementation against the real-world canary.

- [ ] **Step 1: Confirm `SCIENCE_COMMONS_ROOT` is set or defaults correctly**

Run: `echo "${SCIENCE_COMMONS_ROOT:-${HOME}/d/science-commons}" && ls -d "${SCIENCE_COMMONS_ROOT:-${HOME}/d/science-commons}/topics" | head -3`
Expected: `~/d/science-commons/topics` exists and contains the Phase F promoted topics.

- [ ] **Step 2: Ensure commons registry is fresh**

Run: `cd ~/d/science/science && uv run science commons index rebuild`
Expected: rebuild completes; the registry sqlite is updated.

- [ ] **Step 3: Run the mm30 graph build**

Run:
```bash
cd ~/d/cancer/cancer-types/multiple-myeloma
uv run science graph build --project-root .
```
Expected: build succeeds. No "unresolved reference" failures.

- [ ] **Step 4: Verify the resolved-refs count via the audit**

Run: `cd ~/d/cancer/cancer-types/multiple-myeloma && uv run science graph audit --project-root . --format json | grep unresolved_reference_count`
Expected: `"unresolved_reference_count": 0` (or substantially lower than the 65 pre-feature; any residual must be non-commons-typed and explainable).

- [ ] **Step 5: Run mm30's validate script for the broader regression check**

Run: `cd ~/d/cancer/cancer-types/multiple-myeloma && bash validate.sh --verbose 2>&1 | tail -30`
Expected: warning count drops by the resolved-ref delta. No new errors. (Other warnings unrelated to this feature may remain — they're out of scope.)

- [ ] **Step 6: Document the acceptance result**

Add a one-line note to your PR description (or a follow-up comment) recording the pre/post unresolved-reference counts from Step 4. No file commit required in `~/d/science`.

---

## Self-Review

(Performed by the plan author after writing the plan — see skill checklist.)

**1. Spec coverage:**

| Spec section | Implementing task(s) |
|---|---|
| §2 ThemeEntity Literal extensions (theme_kind + theme_scope) | Task 1 |
| §3.1 Integration point (tail-call into load_project_sources after relations+bindings) | Tasks 8, 9 |
| §3.2 Module layout (commons_sources.py) | Tasks 6, 7, 8 |
| §3.3 Dependency direction (graph → commons only) | Tasks 6, 7, 8 (imports verified) |
| §3.4 No-op for non-Phase-F projects | Task 8 step `test_orchestrator_no_overlays_no_refs_is_noop` |
| §3.5 Commons-root resolution + missing-root semantics | Task 8 step `test_orchestrator_raises_when_commons_missing_but_overlays_present` |
| §3.6 Per-build caching | Task 8 (no cross-build cache by construction) |
| §4.1 Three-source collection (entities + relations + binding.{model, parameter, source_refs}) | Task 6 + Task 8 union with overlays |
| §4.2 Missing canonical (overlay → hard error; ref-only → skip) | Task 8 |
| §4.3 Pass-through + normalize translation | Task 7 |
| §4.4 Synthetic SourceRef + identity-table guard | Tasks 8, 9 |
| §4.5 commons_overlay_paths side-table | Tasks 5, 8 |
| §4.6 Downstream invariance | Verified by Task 9 integration + Task 12 canary |
| §5.1 Kind mapping (no registry changes) | Task 7 (uses existing registry) |
| §5.2 `sci:scope` predicate emitted for every entity | Tasks 2, 3 |
| §5.3 Field-mapping table (pass-through + explicit drops) | Task 7 |
| §5.4 Overlay-only fields dropped from graph | Task 7 (`_OVERLAY_ONLY_FIELDS`) |
| §5.5 Provenance: PROJECT_NS["source/<slugified>"] URIs, dual triples | Tasks 4, 10 |
| §6.1 Hard-error matrix | Tasks 7 (kind not registered), 8 (orphan overlay, commons root missing, collision via Task 9) |
| §6.2 Warnings (pin_version) | Task 8 |
| §6.3 Audit-row enrichment for commons-typed unresolved refs | Task 11 |
| §7.1 Unit tests (16 scenarios) | Tasks 6, 7, 8 distribute the unit tests |
| §7.2 E2E materialize tests | Task 10 |
| §7.3 Audit regression | Task 11 |
| §7.4 mm30 canary | Task 12 |
| §7.5 Acceptance test (manual) | Task 13 |

No gaps. Spec §8 open questions are all "documented decisions" — implementations baked into the relevant tasks.

**2. Placeholder scan:** No "TBD", "TODO", "fill in", or "appropriate error handling" anywhere. Each step gives concrete code or concrete commands.

**3. Type consistency:**

- `collect_referenced_commons_ids(...) -> set[str]` — used in Tasks 6 and 8 consistently.
- `_materialize_commons_entity(merged, *, registry, project_slug, active_kinds, ontology_catalogs) -> Entity` — Tasks 7 and 8 use the same kwargs.
- `_load_commons_referenced_entities(...) -> tuple[list[tuple[Entity, SourceRef]], dict[str, str]]` — Task 8 defines it; Task 9 consumes both elements.
- `ProjectSources.commons_overlay_paths: dict[str, str]` — Tasks 5 (define), 9 (populate), 10 (consume), 12 (assert).
- `_add_entity(*, entity, knowledge, provenance, overlay_paths=None)` — Tasks 4 (define), 10 (call with kwargs).
- `EntityScope` import — Tasks 3, 4, 7, 8 all import from `science_model.identity`.

All consistent.

---

## Execution Handoff

Plan complete and saved to `~/d/science/docs/plans/2026-05-19-graph-build-commons-overlay-integration-plan.md`.

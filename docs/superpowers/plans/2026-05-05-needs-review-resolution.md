# Needs-Review Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement first-class conclusion amendment and supersession semantics for `needs-review` resolution without changing freshness or `entity review` outcome semantics.

**Architecture:** Add explicit relation endpoint pairs at the shared profile-schema layer, then use those declarations from graph materialization to validate authored relations before triples are emitted. Source-authored markdown entities and structured `relations.yaml` both feed the same `SourceRelation` pipeline, while command/template prose teaches authors how to resolve `needs-review` outcomes.

**Tech Stack:** Python 3.11, Pydantic v2, rdflib, Click, pytest, Ruff, Pyright, markdown command/template docs.

---

## Scope Check

The spec covers schema/profile declarations, relation loading/materialization, freshness invariants, and command/template prose. These are tightly coupled around one workflow: a reviewed epistemic entity may lead to a new conclusion that `amends` or `supersedes` an older conclusion. This is a single implementation plan with independent commits per layer.

## File Structure

- `science-model/src/science_model/profiles/schema.py`
  - Add `RelationEndpointPair`.
  - Add `RelationKind.allowed_kind_pairs`.
- `science-model/src/science_model/relations.py`
  - Add a reusable `relation_allows_kinds()` helper used by validators and warning surfaces.
- `science-model/src/science_model/profiles/core.py`
  - Add `sci:amends`.
  - Broaden `sci:supersedes` with explicit allowed pairs.
- `science-model/src/science_model/entities.py`
  - Preserve source-authored `relations:` frontmatter on `Entity`. A repo scan
    before this plan found no current entity frontmatter using `relations:`, so
    the new typed field does not conflict with existing data. After this lands,
    malformed `relations:` blocks should fail entity parsing instead of being
    silently ignored.
- `science-tool/src/science_tool/graph/sources.py`
  - Convert markdown entity `relations:` blocks into `SourceRelation` records.
- `science-tool/src/science_tool/graph/materialize.py`
  - Validate declared authored relation endpoints with profile constraints.
  - Reject self-reference and cycles in `sci:amends` / `sci:supersedes`.
  - Emit valid `sci:amends` / conclusion `sci:supersedes` triples.
- `science-tool/src/science_tool/graph/store.py`
  - Keep graph-add warning logic consistent with `allowed_kind_pairs`.
- `science-tool/tests/test_graph_materialize.py`
  - Add end-to-end materialization tests for source-authored relations, valid endpoints, invalid endpoints, and cycles.
- `science-model/tests/test_profile_manifests.py`
  - Add schema/profile tests.
- `science-tool/tests/test_freshness_derivation.py`
  - Add a freshness invariant test proving `amends` / `supersedes` do not drive `needs-review`.
- `science-tool/tests/test_command_docs.py`
  - Add command/template prose coverage.
- `commands/interpret-results.md`
  - Add the needs-review resolution decision tree.
- `commands/next-steps.md`
  - Frame `needs-review` as a review prompt, not a conclusion.
- `commands/status.md`
  - Frame sampled `needs-review` / `stale` entities as review workflow candidates.
- `commands/big-picture.md`
  - Move arc/provenance guidance from `prior_interpretations` to graph chains.
- `templates/interpretation.md`
- `templates/interpretation-dev.md`
- `science-model/src/science_model/templates/interpretation.md`
- `science-model/src/science_model/templates/interpretation-dev.md`
  - Add relation guidance near `prior_interpretations`.
- `meta/tasks/active.md`
  - Mark `t017` complete after verification.

---

### Task 1: Relation Schema And Core Profile

**Files:**
- Modify: `science-model/src/science_model/profiles/schema.py`
- Modify: `science-model/src/science_model/relations.py`
- Modify: `science-model/src/science_model/profiles/core.py`
- Test: `science-model/tests/test_profile_manifests.py`

- [ ] **Step 1: Write failing schema/profile tests**

Add these imports to the top of `science-model/tests/test_profile_manifests.py`:

```python
from science_model.profiles.schema import RelationEndpointPair, RelationKind
from science_model.relations import relation_allows_kinds
```

Add these tests after `test_bears_on_targets_theme()`:

```python
def test_relation_kind_allowed_pairs_override_cartesian_kind_sets() -> None:
    relation = RelationKind(
        name="supersedes",
        predicate="sci:supersedes",
        source_kinds=["workflow-run", "interpretation"],
        target_kinds=["workflow-run", "interpretation"],
        allowed_kind_pairs=[
            RelationEndpointPair(source_kind="workflow-run", target_kind="workflow-run"),
            RelationEndpointPair(source_kind="interpretation", target_kind="interpretation"),
        ],
        layer="layer/core",
    )

    assert relation_allows_kinds(relation, "workflow-run", "workflow-run")
    assert relation_allows_kinds(relation, "interpretation", "interpretation")
    assert not relation_allows_kinds(relation, "interpretation", "workflow-run")
    assert not relation_allows_kinds(relation, "workflow-run", "interpretation")


def test_relation_kind_without_allowed_pairs_keeps_cartesian_behavior() -> None:
    relation = RelationKind(
        name="tests",
        predicate="sci:tests",
        source_kinds=["task", "workflow-run"],
        target_kinds=["hypothesis", "question"],
        layer="layer/core",
    )

    assert relation_allows_kinds(relation, "task", "hypothesis")
    assert relation_allows_kinds(relation, "workflow-run", "question")
    assert not relation_allows_kinds(relation, "hypothesis", "task")
```

Add this test after `test_core_profile_workflow_relations()`:

```python
def test_core_profile_declares_amends_and_non_cartesian_supersedes() -> None:
    relations = {relation.name: relation for relation in CORE_PROFILE.relation_kinds}
    conclusion_kinds = {
        "interpretation",
        "finding",
        "discussion",
        "report",
        "validation-report",
        "story",
    }

    amends = relations["amends"]
    supersedes = relations["supersedes"]

    assert amends.predicate == "sci:amends"
    assert supersedes.predicate == "sci:supersedes"
    assert relation_allows_kinds(amends, "interpretation", "finding")
    assert relation_allows_kinds(amends, "report", "interpretation")
    assert not relation_allows_kinds(amends, "workflow-run", "workflow-run")

    assert relation_allows_kinds(supersedes, "workflow-run", "workflow-run")
    assert relation_allows_kinds(supersedes, "interpretation", "finding")
    assert relation_allows_kinds(supersedes, "story", "validation-report")
    assert not relation_allows_kinds(supersedes, "interpretation", "workflow-run")
    assert not relation_allows_kinds(supersedes, "workflow-run", "interpretation")

    amends_pairs = {(pair.source_kind, pair.target_kind) for pair in amends.allowed_kind_pairs}
    supersedes_pairs = {(pair.source_kind, pair.target_kind) for pair in supersedes.allowed_kind_pairs}
    for source_kind in conclusion_kinds:
        for target_kind in conclusion_kinds:
            assert (source_kind, target_kind) in amends_pairs
            assert (source_kind, target_kind) in supersedes_pairs
    assert ("workflow-run", "workflow-run") in supersedes_pairs
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen --directory science-model pytest tests/test_profile_manifests.py -k "allowed_pairs or amends" -v
```

Expected: FAIL because `RelationEndpointPair`, `RelationKind.allowed_kind_pairs`, and `relation_allows_kinds` do not exist yet.

- [ ] **Step 3: Add explicit endpoint pairs to the schema**

Modify `science-model/src/science_model/profiles/schema.py`.

Change the pydantic import:

```python
from pydantic import BaseModel, Field
```

Add this class above `RelationKind`:

```python
class RelationEndpointPair(BaseModel):
    """One allowed source-kind / target-kind pair for a relation kind."""

    source_kind: str
    target_kind: str
```

Change `RelationKind` to:

```python
class RelationKind(BaseModel):
    """A relation kind declared by a knowledge profile."""

    name: str
    predicate: str
    source_kinds: list[str]
    target_kinds: list[str]
    allowed_kind_pairs: list[RelationEndpointPair] = Field(default_factory=list)
    layer: str
    description: str = ""
```

- [ ] **Step 4: Add relation endpoint helper**

Modify `science-model/src/science_model/relations.py` to this content:

```python
"""Helpers for working with declared relation kinds."""

from __future__ import annotations

from science_model.profiles.schema import RelationKind


def build_relation_registry(relations: list[RelationKind]) -> dict[str, RelationKind]:
    """Index relation kinds by name for fast lookup."""
    registry: dict[str, RelationKind] = {}
    for relation in relations:
        if relation.name in registry:
            msg = f"Duplicate relation kind: {relation.name}"
            raise ValueError(msg)
        registry[relation.name] = relation
    return registry


def relation_allows_kinds(relation: RelationKind, source_kind: str, target_kind: str) -> bool:
    """Return whether a relation kind permits a source-kind / target-kind pair.

    `allowed_kind_pairs`, when present, is the authoritative non-Cartesian
    allow-list. Otherwise, empty source/target kind lists retain their existing
    unrestricted meaning.
    """
    if relation.allowed_kind_pairs:
        return any(
            pair.source_kind == source_kind and pair.target_kind == target_kind
            for pair in relation.allowed_kind_pairs
        )
    source_allowed = not relation.source_kinds or source_kind in relation.source_kinds
    target_allowed = not relation.target_kinds or target_kind in relation.target_kinds
    return source_allowed and target_allowed
```

- [ ] **Step 5: Declare conclusion relation pairs in the core profile**

Modify the import in `science-model/src/science_model/profiles/core.py`:

```python
from science_model.profiles.schema import EntityKind, ProfileManifest, RelationEndpointPair, RelationKind
```

Add these constants above `CORE_PROFILE`:

```python
_CONCLUSION_KINDS = [
    "interpretation",
    "finding",
    "discussion",
    "report",
    "validation-report",
    "story",
]

_CONCLUSION_KIND_PAIRS = [
    RelationEndpointPair(source_kind=source_kind, target_kind=target_kind)
    for source_kind in _CONCLUSION_KINDS
    for target_kind in _CONCLUSION_KINDS
]
```

Replace the existing `supersedes` relation block with:

```python
        RelationKind(
            name="supersedes",
            predicate="sci:supersedes",
            source_kinds=["workflow-run", *_CONCLUSION_KINDS],
            target_kinds=["workflow-run", *_CONCLUSION_KINDS],
            allowed_kind_pairs=[
                RelationEndpointPair(source_kind="workflow-run", target_kind="workflow-run"),
                *_CONCLUSION_KIND_PAIRS,
            ],
            layer="layer/core",
            description=(
                "A newer entity replaces an older entity as canonical. Valid "
                "for workflow-run replacement and conclusion-level replacement."
            ),
        ),
```

Add this relation block immediately after `supersedes`:

```python
        RelationKind(
            name="amends",
            predicate="sci:amends",
            source_kinds=_CONCLUSION_KINDS,
            target_kinds=_CONCLUSION_KINDS,
            allowed_kind_pairs=_CONCLUSION_KIND_PAIRS,
            layer="layer/core",
            description=(
                "A newer conclusion revises, narrows, qualifies, or extends an "
                "older conclusion without replacing it."
            ),
        ),
```

- [ ] **Step 6: Run schema/profile tests**

Run:

```bash
uv run --frozen --directory science-model pytest tests/test_profile_manifests.py -v
```

Expected: PASS.

- [ ] **Step 7: Run science-model lint**

Run:

```bash
uv run --frozen --directory science-model ruff check src tests
```

Expected: PASS.

- [ ] **Step 8: Commit schema/profile changes**

Run:

```bash
git add science-model/src/science_model/profiles/schema.py science-model/src/science_model/relations.py science-model/src/science_model/profiles/core.py science-model/tests/test_profile_manifests.py
git commit -m "feat(model): add explicit relation endpoint pairs"
```

---

### Task 2: Source-Authored Entity Relations

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Test: `science-tool/tests/test_graph_materialize.py`

- [ ] **Step 1: Write failing materialization test for markdown entity relations**

Add this test near `test_materialize_graph_applies_structured_relations_with_internal_targets()` in `science-tool/tests/test_graph_materialize.py`:

```python
def test_materialize_graph_applies_source_entity_relations(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    interpretations = project / "doc" / "interpretations"
    interpretations.mkdir(parents=True)
    (interpretations / "old.md").write_text(
        "\n".join(
            [
                "---",
                'id: "interpretation:old"',
                'kind: "interpretation"',
                'title: "Old interpretation"',
                'status: "active"',
                'created: "2026-05-01"',
                'updated: "2026-05-01"',
                "related: []",
                "source_refs: []",
                "---",
                "",
                "Old body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (interpretations / "new.md").write_text(
        "\n".join(
            [
                "---",
                'id: "interpretation:new"',
                'kind: "interpretation"',
                'title: "New interpretation"',
                'status: "active"',
                'created: "2026-05-02"',
                'updated: "2026-05-02"',
                "related: []",
                "source_refs: []",
                "relations:",
                '  - predicate: "sci:amends"',
                '    target: "interpretation:old"',
                "---",
                "",
                "New body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    assert (PROJECT_NS["interpretation/new"], SCI.amends, PROJECT_NS["interpretation/old"]) in knowledge
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_materialize.py::test_materialize_graph_applies_source_entity_relations -v
```

Expected: FAIL because `Entity` currently ignores source-authored `relations:` blocks.

- [ ] **Step 3: Preserve `relations:` on parsed entities**

Modify `science-model/src/science_model/entities.py`.

Add this import:

```python
from science_model.source_contracts import AuthoredTargetedRelation
```

Add this field to `class Entity` immediately after `related: list[str]`:

```python
    relations: list[AuthoredTargetedRelation] = Field(default_factory=list)
```

- [ ] **Step 4: Normalize missing `relations` during source loading**

Modify `_enrich_raw()` in `science-tool/src/science_tool/graph/sources.py`.

Add this line immediately after `raw.setdefault("related", [])`:

```python
    raw.setdefault("relations", [])
```

- [ ] **Step 5: Convert entity relation blocks into `SourceRelation` records**

Add this helper below `_legacy_nested_relations()` in `science-tool/src/science_tool/graph/sources.py`:

```python
def _entity_nested_relations(entities: list[Entity]) -> list[SourceRelation]:
    flattened: list[SourceRelation] = []
    for entity in entities:
        if not entity.relations:
            continue
        for relation in entity.relations:
            flattened.append(
                SourceRelation(
                    subject=entity.canonical_id,
                    predicate=relation.predicate,
                    object=canonical_paper_id(relation.target),
                    graph_layer=relation.graph_layer,
                    source_path=entity.file_path,
                )
            )
    return flattened
```

In `load_project_sources()`, immediately after:

```python
    relations = _load_structured_relations(project_root, local_profile=local_profile)
```

add:

```python
    relations.extend(_entity_nested_relations(entities))
```

- [ ] **Step 6: Run source relation test**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_materialize.py::test_materialize_graph_applies_source_entity_relations -v
```

Expected: PASS.

- [ ] **Step 7: Run focused source/materialization tests**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_materialize.py -k "structured_relations or source_entity_relations" -v
```

Expected: PASS.

- [ ] **Step 8: Commit source relation loading**

Run:

```bash
git add science-model/src/science_model/entities.py science-tool/src/science_tool/graph/sources.py science-tool/tests/test_graph_materialize.py
git commit -m "feat(graph): load source-authored entity relations"
```

---

### Task 3: Authored Relation Endpoint Validation And Cycles

**Files:**
- Modify: `science-tool/src/science_tool/graph/materialize.py`
- Test: `science-tool/tests/test_graph_materialize.py`

- [ ] **Step 1: Write failing tests for valid and invalid endpoints**

Add these helper functions near the existing test helpers in `science-tool/tests/test_graph_materialize.py`:

```python
def _write_minimal_entity(path: Path, canonical_id: str, kind: str, title: str, extra_frontmatter: list[str] | None = None) -> None:
    lines = [
        "---",
        f'id: "{canonical_id}"',
        f'kind: "{kind}"',
        f'title: "{title}"',
        'status: "active"',
        'created: "2026-05-01"',
        'updated: "2026-05-01"',
        "related: []",
        "source_refs: []",
    ]
    if extra_frontmatter:
        lines.extend(extra_frontmatter)
    lines.extend(["---", "", f"{title} body.", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
```

Add these tests near the structured relation tests:

```python
def test_materialize_graph_accepts_conclusion_amends_and_supersedes(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(project / "doc" / "interpretations" / "old.md", "interpretation:old", "interpretation", "Old interpretation")
    _write_minimal_entity(
        project / "doc" / "interpretations" / "new.md",
        "interpretation:new",
        "interpretation",
        "New interpretation",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "interpretation:old"',
            '  - predicate: "sci:supersedes"',
            '    target: "interpretation:old"',
        ],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    assert (PROJECT_NS["interpretation/new"], SCI.amends, PROJECT_NS["interpretation/old"]) in knowledge
    assert (PROJECT_NS["interpretation/new"], SCI.supersedes, PROJECT_NS["interpretation/old"]) in knowledge


def test_materialize_graph_preserves_workflow_run_supersedes(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(project / "doc" / "runs" / "old.md", "workflow-run:old-run", "workflow-run", "Old run")
    _write_minimal_entity(
        project / "doc" / "runs" / "new.md",
        "workflow-run:new-run",
        "workflow-run",
        "New run",
        [
            "relations:",
            '  - predicate: "sci:supersedes"',
            '    target: "workflow-run:old-run"',
        ],
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    assert (PROJECT_NS["workflow-run/new-run"], SCI.supersedes, PROJECT_NS["workflow-run/old-run"]) in knowledge


def test_materialize_graph_rejects_invalid_supersedes_pair(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(project / "doc" / "interpretations" / "new.md", "interpretation:new", "interpretation", "New interpretation")
    _write_minimal_entity(project / "doc" / "runs" / "old.md", "workflow-run:old-run", "workflow-run", "Old run")
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "relations.yaml").write_text(
        "\n".join(
            [
                "relations:",
                '  - subject: "interpretation:new"',
                '    predicate: "sci:supersedes"',
                '    object: "workflow-run:old-run"',
                '    source_path: "knowledge/sources/local/relations.yaml"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"invalid authored relation endpoint.*interpretation:new.*sci:supersedes.*workflow-run:old-run.*relations.yaml"):
        materialize_graph(project)


def test_materialize_graph_rejects_invalid_amends_pair(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(project / "doc" / "runs" / "old.md", "workflow-run:old-run", "workflow-run", "Old run")
    _write_minimal_entity(
        project / "doc" / "runs" / "new.md",
        "workflow-run:new-run",
        "workflow-run",
        "New run",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "workflow-run:old-run"',
        ],
    )

    with pytest.raises(ValueError, match=r"invalid authored relation endpoint.*workflow-run:new-run.*sci:amends.*workflow-run:old-run.*new.md"):
        materialize_graph(project)
```

- [ ] **Step 2: Write failing tests for self-reference and cycles**

Add these tests after the invalid endpoint tests:

```python
def test_materialize_graph_rejects_self_supersedes(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "doc" / "interpretations" / "same.md",
        "interpretation:same",
        "interpretation",
        "Self replacement",
        [
            "relations:",
            '  - predicate: "sci:supersedes"',
            '    target: "interpretation:same"',
        ],
    )

    with pytest.raises(ValueError, match=r"self-referential authored relation.*interpretation:same.*sci:supersedes"):
        materialize_graph(project)


def test_materialize_graph_rejects_amendment_cycle(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "doc" / "interpretations" / "a.md",
        "interpretation:a",
        "interpretation",
        "A",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "interpretation:b"',
        ],
    )
    _write_minimal_entity(
        project / "doc" / "interpretations" / "b.md",
        "interpretation:b",
        "interpretation",
        "B",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "interpretation:a"',
        ],
    )

    with pytest.raises(ValueError, match=r"cycle in amendment/supersession relations: interpretation:a -> interpretation:b -> interpretation:a"):
        materialize_graph(project)


def test_materialize_graph_rejects_mixed_amends_supersedes_cycle(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "doc" / "interpretations" / "a.md",
        "interpretation:a",
        "interpretation",
        "A",
        [
            "relations:",
            '  - predicate: "sci:amends"',
            '    target: "interpretation:b"',
        ],
    )
    _write_minimal_entity(
        project / "doc" / "interpretations" / "b.md",
        "interpretation:b",
        "interpretation",
        "B",
        [
            "relations:",
            '  - predicate: "sci:supersedes"',
            '    target: "interpretation:a"',
        ],
    )

    with pytest.raises(ValueError, match=r"cycle in amendment/supersession relations: interpretation:a -> interpretation:b -> interpretation:a"):
        materialize_graph(project)
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_materialize.py -k "amends or supersedes or amendment_cycle" -v
```

Expected: FAIL because materialization does not validate endpoints or cycles yet.

- [ ] **Step 4: Import profile helpers in materialize**

Modify imports in `science-tool/src/science_tool/graph/materialize.py`.

Add:

```python
from science_model.profiles import CORE_PROFILE
from science_model.profiles.schema import RelationKind
from science_model.relations import relation_allows_kinds
```

Add `canonical_id_from_entity_uri` to the existing store import:

```python
from science_tool.graph.store import (
    CITO_NS,
    CURIE_PREFIXES,
    GRAPH_LAYERS,
    PROJECT_ENTITY_PREFIXES,
    PROJECT_NS,
    SCHEMA_NS,
    SCI_NS,
    canonical_id_from_entity_uri,
)
```

- [ ] **Step 5: Add relation validation helpers**

Add these helpers below `_add_authored_relation()` in `science-tool/src/science_tool/graph/materialize.py`:

```python
_AMENDMENT_RELATION_PREDICATES = frozenset({SCI_NS.amends, SCI_NS.supersedes})


def _relation_name_for_error(relation_kind: RelationKind | None, predicate: str) -> str:
    if relation_kind is not None:
        return relation_kind.name
    return predicate


def _canonical_entity(
    raw_value: str,
    *,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
) -> Entity:
    resolution = resolver.resolve(raw_value)
    entity = entity_index.get(resolution.canonical_id or "")
    if entity is None:
        raise ValueError(f"Unknown canonical entity: {raw_value}")
    return entity


def _profile_relation_for_predicate(predicate_uri: URIRef) -> RelationKind | None:
    for relation_kind in CORE_PROFILE.relation_kinds:
        if _resolve_relation_term(relation_kind.predicate) == predicate_uri:
            return relation_kind
    return None


def _validate_authored_relation_endpoint(
    relation: SourceRelation,
    *,
    relation_kind: RelationKind | None,
    subject_entity: Entity,
    object_entity: Entity | None,
) -> None:
    if relation_kind is None:
        return
    if object_entity is None:
        if relation_kind.target_kinds or relation_kind.allowed_kind_pairs:
            raise ValueError(
                "invalid authored relation endpoint: "
                f"{relation.subject} {relation.predicate} ({_relation_name_for_error(relation_kind, relation.predicate)}) "
                f"{relation.object} in {relation.source_path} "
                "targets an external reference but the predicate requires a project entity"
            )
        return
    if object_entity is not None and subject_entity.canonical_id == object_entity.canonical_id:
        raise ValueError(
            "self-referential authored relation: "
            f"{relation.subject} {relation.predicate} ({_relation_name_for_error(relation_kind, relation.predicate)}) "
            f"{relation.object} in {relation.source_path}"
        )
    if relation_allows_kinds(relation_kind, subject_entity.kind, object_entity.kind):
        return
    raise ValueError(
        "invalid authored relation endpoint: "
        f"{relation.subject} {relation.predicate} ({_relation_name_for_error(relation_kind, relation.predicate)}) "
        f"{relation.object} in {relation.source_path} "
        f"(got {subject_entity.kind} -> {object_entity.kind})"
    )


def _display_entity_uri(uri: URIRef) -> str:
    canonical_id = canonical_id_from_entity_uri(str(uri))
    return canonical_id or str(uri)


def _validate_no_amendment_cycles(dataset: Dataset) -> None:
    adjacency: dict[URIRef, set[URIRef]] = {}
    for graph in dataset.graphs():
        for predicate in _AMENDMENT_RELATION_PREDICATES:
            for source, _, target in graph.triples((None, predicate, None)):
                if not isinstance(source, URIRef) or not isinstance(target, URIRef):
                    continue
                adjacency.setdefault(source, set()).add(target)

    visited: set[URIRef] = set()
    visiting: set[URIRef] = set()

    def visit(node: URIRef, path: list[URIRef]) -> None:
        if node in visiting:
            start = path.index(node)
            cycle = path[start:] + [node]
            cycle_text = " -> ".join(_display_entity_uri(item) for item in cycle)
            raise ValueError(f"cycle in amendment/supersession relations: {cycle_text}")
        if node in visited:
            return
        visiting.add(node)
        for target in sorted(adjacency.get(node, set()), key=str):
            visit(target, [*path, target])
        visiting.remove(node)
        visited.add(node)

    for node in sorted(adjacency, key=str):
        visit(node, [node])
```

- [ ] **Step 6: Replace `_add_authored_relation` with validated version**

Replace `_add_authored_relation()` in `science-tool/src/science_tool/graph/materialize.py` with:

```python
def _add_authored_relation(
    relation: SourceRelation,
    *,
    dataset: Dataset,
    entity_index: dict[str, Entity],
    resolver: ReferenceResolver,
    bridge,
    ontology_catalogs: list[OntologyCatalog],
    ext_prefixes: frozenset[str],
    kind_class: dict[str, EntityClass] | None = None,
) -> None:
    del kind_class  # endpoint validation is now driven by the relation profile
    graph = dataset.graph(_graph_uri(relation.graph_layer))
    subject_entity = _canonical_entity(relation.subject, entity_index=entity_index, resolver=resolver)
    subject_uri = _entity_uri(subject_entity.canonical_id)
    predicate_uri = _resolve_relation_term(relation.predicate)

    object_entity: Entity | None = None
    if is_external_reference(relation.object, known_prefixes=ext_prefixes):
        object_uri = _external_uri(relation.object)
        _register_external_term(object_uri, relation.object, bridge=bridge, ontology_catalogs=ontology_catalogs)
    else:
        object_entity = _canonical_entity(relation.object, entity_index=entity_index, resolver=resolver)
        object_uri = _entity_uri(object_entity.canonical_id)

    relation_kind = _profile_relation_for_predicate(predicate_uri)
    _validate_authored_relation_endpoint(
        relation,
        relation_kind=relation_kind,
        subject_entity=subject_entity,
        object_entity=object_entity,
    )

    graph.add((subject_uri, predicate_uri, object_uri))
```

- [ ] **Step 7: Validate cycles after authored relations are added**

In `_build_dataset_from_sources()`, after the `for binding in sources.bindings:` loop and before `_derive_bears_on_layer(...)`, add:

```python
    _validate_no_amendment_cycles(dataset)
```

This intentionally treats `sci:amends` and `sci:supersedes` as one combined
conclusion-chain DAG, and it scans all named graphs so a relation authored on a
non-knowledge layer cannot escape cycle validation.

- [ ] **Step 8: Run endpoint validation tests**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_materialize.py -k "amends or supersedes or amendment_cycle" -v
```

Expected: PASS.

- [ ] **Step 9: Run freshness integration regression for `bears_on` validation**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_freshness_integration.py::test_materialize_rejects_hand_authored_bears_on_to_non_epistemic_target -v
```

Expected: PASS.

- [ ] **Step 10: Commit materialization validation**

Run:

```bash
git add science-tool/src/science_tool/graph/materialize.py science-tool/tests/test_graph_materialize.py
git commit -m "feat(graph): validate authored relation endpoints"
```

---

### Task 4: Graph-Add Warning Consistency

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_cli.py`

- [ ] **Step 1: Write failing warning test for non-Cartesian `supersedes`**

Add this test after `test_graph_add_edge_warns_on_reversed_addresses_direction()` in `science-tool/tests/test_graph_cli.py`:

```python
def test_graph_add_edge_warns_on_invalid_supersedes_kind_pair() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0

        result = runner.invoke(
            main,
            ["graph", "add", "edge", "interpretation/new_interpretation", "sci:supersedes", "workflow-run/old-run"],
        )
        assert result.exit_code == 0
        assert "unexpected kinds" in result.output
        assert "interpretation -> workflow-run" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_cli.py::test_graph_add_edge_warns_on_invalid_supersedes_kind_pair -v
```

Expected: FAIL because `_RELATION_KIND_BY_PREDICATE` only stores Cartesian source/target sets.

- [ ] **Step 3: Update store warning constraints to use `RelationKind`**

Modify `science-tool/src/science_tool/graph/store.py`.

Add this import:

```python
from science_model.profiles.schema import RelationKind
from science_model.relations import relation_allows_kinds
```

Replace `_RELATION_KIND_BY_PREDICATE` with:

```python
_RELATION_KIND_BY_PREDICATE: dict[URIRef, RelationKind] = {
    URIRef(SCI_NS[rk.predicate.split(":", 1)[1]] if rk.predicate.startswith("sci:") else rk.predicate): rk
    for rk in CORE_PROFILE.relation_kinds
    if rk.predicate.startswith("sci:")
}
```

In `_warn_on_relation_direction_mismatch()`, replace:

```python
    allowed_subject_kinds, allowed_object_kinds = constraint
```

with:

```python
    relation_kind = constraint
```

Replace the two kind checks and warning messages with:

```python
    if relation_allows_kinds(relation_kind, subject_kind, object_kind):
        return
    if relation_allows_kinds(relation_kind, object_kind, subject_kind):
        click.echo(
            f"Warning: '{predicate}' direction looks reversed — "
            f"profile accepts {relation_kind.name} endpoints but got reversed "
            f"{subject_kind} -> {object_kind}.",
            err=True,
        )
        return
    click.echo(
        f"Warning: '{predicate}' edge has unexpected kinds — "
        f"got {subject_kind} -> {object_kind}.",
        err=True,
    )
```

- [ ] **Step 4: Run graph CLI warning tests**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_graph_cli.py -k "warns_on_reversed_addresses_direction or warns_on_invalid_supersedes_kind_pair" -v
```

Expected: PASS.

- [ ] **Step 5: Commit warning consistency**

Run:

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/tests/test_graph_cli.py
git commit -m "fix(graph): respect explicit relation pairs in warnings"
```

---

### Task 5: Freshness Invariant And Workflow Prose

**Files:**
- Modify: `science-tool/tests/test_freshness_derivation.py`
- Modify: `science-tool/tests/test_command_docs.py`
- Modify: `commands/interpret-results.md`
- Modify: `commands/next-steps.md`
- Modify: `commands/status.md`
- Modify: `commands/big-picture.md`
- Modify: `templates/interpretation.md`
- Modify: `templates/interpretation-dev.md`
- Modify: `science-model/src/science_model/templates/interpretation.md`
- Modify: `science-model/src/science_model/templates/interpretation-dev.md`

- [ ] **Step 1: Write failing freshness invariant test**

Add this helper to `science-tool/tests/test_freshness_derivation.py` below `_ds_with_bears_on()`:

```python
def _ds_with_relation(source: URIRef, predicate: URIRef, target: URIRef) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((source, predicate, target))
    return ds
```

Add this test after `test_freshness_needs_review_when_upstream_changed_after_last_review()`:

```python
def test_freshness_ignores_amends_and_supersedes_edges() -> None:
    h = _u("hypothesis/h1")
    old = _u("interpretation/old")
    new = _u("interpretation/new")
    for predicate in (SCI_NS.amends, SCI_NS.supersedes):
        ds = _ds_with_relation(new, predicate, old)
        entities: dict[str, EntityFreshnessInfo] = {
            str(h): {
                "kind_class": EntityClass.EPISTEMIC,
                "last_reviewed": date(2026, 4, 1),
                "created": date(2026, 3, 1),
                "updated": date(2026, 4, 1),
                "review_horizon_days": None,
            },
            str(old): {
                "kind_class": EntityClass.EPISTEMIC,
                "last_reviewed": date(2026, 4, 1),
                "created": date(2026, 3, 1),
                "updated": date(2026, 4, 1),
                "review_horizon_days": None,
            },
            str(new): {
                "kind_class": EntityClass.EPISTEMIC,
                "last_reviewed": None,
                "created": date(2026, 5, 1),
                "updated": date(2026, 5, 1),
                "review_horizon_days": None,
            },
        }

        derive_freshness(ds, entities=entities, today=date(2026, 5, 3))

        assert _state_for(ds, h) == "fresh"
        assert _triggered_by(ds, h) == set()
```

- [ ] **Step 2: Write failing command/template prose tests**

Add this test to `science-tool/tests/test_command_docs.py` after `test_plan_analysis_is_integrated_with_neighbor_commands()`:

```python
def test_needs_review_resolution_docs_cover_amendment_workflow() -> None:
    expected_by_path = {
        "commands/interpret-results.md": (
            "needs-review resolution",
            "sci:amends",
            "sci:supersedes",
            "sci:supersedesClaim",
            "entity review <target-ref>",
            "flagged entity",
            "status: superseded",
        ),
        "commands/next-steps.md": (
            "needs-review",
            "review prompt",
            "sci:amends",
            "sci:supersedes",
        ),
        "commands/status.md": (
            "needs-review",
            "review workflow",
            "sci:amends",
            "sci:supersedes",
        ),
        "commands/big-picture.md": (
            "sci:amends",
            "sci:supersedes",
            "prior_interpretations",
            "not the machine-readable chain",
        ),
        "templates/interpretation.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "templates/interpretation-dev.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "science-model/src/science_model/templates/interpretation.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
        "science-model/src/science_model/templates/interpretation-dev.md": (
            "relations:",
            "sci:amends",
            "sci:supersedes",
        ),
    }
    for path, expected_strings in expected_by_path.items():
        text = _read(path)
        for expected in expected_strings:
            assert expected in text
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_freshness_derivation.py::test_freshness_ignores_amends_and_supersedes_edges tests/test_command_docs.py::test_needs_review_resolution_docs_cover_amendment_workflow -v
```

Expected: command docs test FAIL because prose/templates do not contain the new workflow. The freshness test should PASS unless freshness has drifted; keep it as an invariant.

- [ ] **Step 4: Update interpretation templates**

In all four template files:

- `templates/interpretation.md`
- `templates/interpretation-dev.md`
- `science-model/src/science_model/templates/interpretation.md`
- `science-model/src/science_model/templates/interpretation-dev.md`

Add this frontmatter block immediately after `prior_interpretations: []`:

```yaml
relations: []  # optional graph relations; use sci:amends or sci:supersedes for conclusion chains
```

In `templates/interpretation.md` and `science-model/src/science_model/templates/interpretation.md`, add this to the `_template.frontmatter` mapping:

```yaml
    relations: { default: [] }
```

Add this comment block below the frontmatter in all four files, directly after
the closing `---` and before the first `#` heading. Only
`templates/interpretation.md` and
`science-model/src/science_model/templates/interpretation.md` have a
`_template.frontmatter` mapping; do not add that mapping to the dev templates.

```markdown
<!--
Conclusion chains:
- Use `relations:` with `predicate: "sci:amends"` when this interpretation revises,
  narrows, qualifies, or extends an older conclusion.
- Use `relations:` with `predicate: "sci:supersedes"` when this interpretation
  replaces an older conclusion as the current canonical reading.
- Keep `prior_interpretations` only as a narrative breadcrumb. The graph relation
  is the machine-readable source of truth.
-->
```

- [ ] **Step 5: Update `commands/interpret-results.md`**

In `commands/interpret-results.md`, replace this existing block:

```markdown
### Cross-Referencing Prior Interpretations

When interpreting multiple tasks jointly or building on a prior interpretation, list which earlier interpretation documents this one extends or supersedes using the `prior_interpretations` frontmatter field.

- **Combined interpretations:** When interpreting 2+ tasks as a single arc, list any prior single-task interpretations that this combined document supersedes. The prior documents remain for provenance; the combined one is canonical for downstream reference.
- **Update mode:** When updating an existing interpretation with new evidence, reference the prior version's ID.

This creates a provenance chain across interpretation documents.
```

with:

````markdown
### Cross-Referencing Prior Interpretations

When interpreting multiple tasks jointly or building on a prior interpretation,
list earlier interpretation documents in `prior_interpretations` as a narrative
breadcrumb. This field is not the machine-readable conclusion chain.

For needs-review resolution, use first-class graph relations:

- `sci:amends` when the new conclusion revises, narrows, qualifies, or extends
  an older conclusion without replacing it.
- `sci:supersedes` when the new conclusion replaces the older conclusion as the
  current canonical reading. In this case, also mark the old conclusion
  `status: superseded`.

Do not use `sci:supersedesClaim` for conclusion replacement. That predicate is
reserved for falsification records.

Example frontmatter on the new interpretation:

```yaml
relations:
  - predicate: "sci:amends"
    target: "interpretation:old"
```

or:

```yaml
relations:
  - predicate: "sci:supersedes"
    target: "interpretation:old"
```

### Needs-Review Resolution

When a result is being interpreted because an epistemic entity was flagged
`needs-review`, keep the review timestamp separate from the conclusion change:

1. Inspect the flagged entity, its `sci:triggeredBy` upstream sources, and nearby
   prior conclusions.
2. If standing is unchanged, run
   `science-tool entity review <target-ref> --note "Reviewed against <source>; no standing change."`
3. If standing changes, author the new interpretation or finding, add
   `sci:amends` or `sci:supersedes`, and only then run
   `science-tool entity review <target-ref> --note "Reconsidered; see interpretation:<new>."`

`<target-ref>` is the flagged entity, not the newly authored conclusion.
Freshness remains a review prompt; it does not mutate standing.
````

- [ ] **Step 6: Update `commands/next-steps.md`**

In the weighted attention sample section of `commands/next-steps.md`, replace the two sentences:

```markdown
Treat the sample as a revisiting queue, not a ranked verdict.
Frame `needs-review` or `stale` rows as "this deserves a fresh look" rather than
as a claim that the prior conclusion is wrong. Propose one as a candidate next
step and add a corresponding task if accepted.
```

with:

```markdown
Treat the sample as a revisiting queue, not a ranked verdict. Frame
`needs-review` or `stale` rows as a review prompt rather than as evidence that a
prior conclusion is wrong.

When recommending work on a `needs-review` entity, name the resolution path:
unchanged review (`science-tool entity review <target-ref>`), amendment
(`sci:amends` from a new conclusion to the old conclusion), or replacement
(`sci:supersedes` plus `status: superseded` on the old conclusion). Propose one
as a candidate next step and add a corresponding task if accepted.
```

- [ ] **Step 7: Update `commands/status.md`**

Under "Staleness Warnings" in `commands/status.md`, add this paragraph after the attention-sample bullet:

```markdown
When a sampled entity is `needs-review`, frame it as a review workflow candidate:
the next action is to inspect `sci:triggeredBy` evidence, then either record an
unchanged review with `science-tool entity review <target-ref>` or author a new
conclusion linked by `sci:amends` / `sci:supersedes`. Do not describe the
freshness state as a conclusion that the old standing is wrong.
```

- [ ] **Step 8: Update `commands/big-picture.md`**

In `commands/big-picture.md`, replace this existing block:

```markdown
Compute `provenance_coverage` per hypothesis:
- `high` if ≥1 `.edges.yaml` is present OR ≥1 graph claim surfaces AND ≥60% of related interpretations have `prior_interpretations` chains.
- `partial` if neither of those but ≥30% of related interpretations have `prior_interpretations`.
- `thin` otherwise.
```

with:

```markdown
Compute `provenance_coverage` per hypothesis:
- `high` if ≥1 `.edges.yaml` is present OR ≥1 graph claim surfaces AND ≥60% of
  related interpretations participate in materialized `sci:amends` /
  `sci:supersedes` conclusion chains.
- `partial` if neither of those but ≥30% of related interpretations participate
  in materialized `sci:amends` / `sci:supersedes` chains.
- `thin` otherwise.

`prior_interpretations` is a narrative breadcrumb, not the machine-readable
chain. Use materialized `sci:amends` and `sci:supersedes` edges for arc
reconstruction. When a replacement chain exists, prefer non-superseded current
conclusions in the synthesis and keep superseded conclusions as provenance.
```

- [ ] **Step 9: Run freshness and command doc tests**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_freshness_derivation.py::test_freshness_ignores_amends_and_supersedes_edges tests/test_command_docs.py::test_needs_review_resolution_docs_cover_amendment_workflow -v
```

Expected: PASS.

- [ ] **Step 10: Commit freshness/docs updates**

Run:

```bash
git add science-tool/tests/test_freshness_derivation.py science-tool/tests/test_command_docs.py commands/interpret-results.md commands/next-steps.md commands/status.md commands/big-picture.md templates/interpretation.md templates/interpretation-dev.md science-model/src/science_model/templates/interpretation.md science-model/src/science_model/templates/interpretation-dev.md
git commit -m "docs: document needs-review resolution workflow"
```

---

### Task 6: Final Verification And Task Closure

**Files:**
- Modify: `meta/tasks/active.md`

- [ ] **Step 1: Run full focused verification**

Run:

```bash
uv run --frozen --directory science-model pytest tests/test_profile_manifests.py -v
uv run --frozen --directory science-tool pytest tests/test_graph_materialize.py tests/test_graph_freshness_integration.py tests/test_freshness_derivation.py tests/test_command_docs.py -v
uv run --frozen --directory science-tool pytest tests/test_graph_cli.py -k "warns_on_reversed_addresses_direction or warns_on_invalid_supersedes_kind_pair" -v
uv run --frozen --directory science-model ruff check src tests
uv run --frozen --directory science-tool ruff check src tests
uv run --frozen --directory science-tool pyright
```

Expected: all commands PASS.

- [ ] **Step 2: Run meta validation**

Run:

```bash
meta/validate.sh
```

Expected: PASS. If it prints the existing non-blocking warning `meta/pyproject.toml does not reference science-tool`, leave that warning unchanged.

- [ ] **Step 3: Mark `t017` complete**

In `meta/tasks/active.md`, replace the `t017` status line:

```markdown
- status: proposed
```

with:

```markdown
- status: done
- completed: 2026-05-05
```

Append this sentence after the existing `t017` body:

```markdown
**COMPLETED 2026-05-05.** Added first-class `sci:amends` and conclusion-level `sci:supersedes` semantics, explicit endpoint-pair validation, source-authored relation loading, needs-review resolution prose, and tests preserving freshness/review separation.
```

- [ ] **Step 4: Run task parser and meta validation**

Run:

```bash
uv run --frozen --directory science-tool pytest tests/test_tasks.py -v
meta/validate.sh
```

Expected: PASS, with only the existing non-blocking warning if it appears.

- [ ] **Step 5: Commit task closure**

Run:

```bash
git add meta/tasks/active.md
git commit -m "chore(meta): close t017 needs-review workflow"
```

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short
```

Expected: no output.

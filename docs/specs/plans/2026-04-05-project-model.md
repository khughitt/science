# Project Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Project Model redesign — replacing claim/relation_claim/evidence entities with proposition/observation/evidence-as-relation, retiring artifact into data_package, and renaming paper→article for literature references.

**Architecture:** The changes flow through three packages: `science-model` (entity types, profiles), `science-tool` (graph store, materialization, CLI), and project-level files (skills, templates, docs). Each task targets a specific layer, with tests validating each change before moving to the next.

**Tech Stack:** Python 3.11+, Pydantic v2, rdflib, Click, pytest

**Spec:** `docs/specs/2026-04-05-project-model-design.md`

---

### Task 1: Update EntityType Enum

**Files:**
- Modify: `science-model/src/science_model/entities.py:13-44`
- Test: `science-model/tests/test_entities.py`

- [ ] **Step 1: Write failing tests for new entity types**

```python
# Append to science-model/tests/test_entities.py

def test_proposition_entity_type():
    assert EntityType.PROPOSITION == "proposition"
    assert EntityType("proposition") == EntityType.PROPOSITION


def test_observation_entity_type():
    assert EntityType.OBSERVATION == "observation"
    assert EntityType("observation") == EntityType.OBSERVATION


def test_claim_entity_type_removed():
    assert not hasattr(EntityType, "CLAIM")


def test_relation_claim_entity_type_removed():
    assert not hasattr(EntityType, "RELATION_CLAIM")


def test_evidence_entity_type_removed():
    assert not hasattr(EntityType, "EVIDENCE")


def test_artifact_entity_type_removed():
    assert not hasattr(EntityType, "ARTIFACT")


def test_paper_renamed_to_article():
    """PAPER is removed from enum; ARTICLE represents external literature."""
    assert not hasattr(EntityType, "PAPER")
    assert EntityType.ARTICLE == "article"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-model && uv run --frozen pytest tests/test_entities.py -v -k "proposition or observation or claim_entity_type_removed or relation_claim_entity_type_removed or evidence_entity_type_removed or artifact_entity_type_removed or paper_renamed"`
Expected: FAIL — PROPOSITION and OBSERVATION don't exist, CLAIM/RELATION_CLAIM/EVIDENCE/ARTIFACT/PAPER still exist.

- [ ] **Step 3: Update EntityType enum**

Replace the enum in `science-model/src/science_model/entities.py:13-44`:

```python
class EntityType(StrEnum):
    """Known entity types across Science projects."""

    CONCEPT = "concept"
    HYPOTHESIS = "hypothesis"
    QUESTION = "question"
    PROPOSITION = "proposition"
    OBSERVATION = "observation"
    INQUIRY = "inquiry"
    TOPIC = "topic"
    INTERPRETATION = "interpretation"
    DISCUSSION = "discussion"
    MODEL = "model"
    PRE_REGISTRATION = "pre-registration"
    PLAN = "plan"
    ASSUMPTION = "assumption"
    TRANSFORMATION = "transformation"
    VARIABLE = "variable"
    DATASET = "dataset"
    METHOD = "method"
    COMPARISON = "comparison"
    EXPERIMENT = "experiment"
    ARTICLE = "article"
    WORKFLOW = "workflow"
    WORKFLOW_RUN = "workflow-run"
    WORKFLOW_STEP = "workflow-step"
    DATA_PACKAGE = "data-package"
    BIAS_AUDIT = "bias-audit"
    FINDING = "finding"
    STORY = "story"
    PAPER = "paper"
    UNKNOWN = "unknown"
```

Note: `PAPER` is now the compositional entity (your own paper), `ARTICLE` is external literature. `FINDING` and `STORY` are added here even though their full integration is in the Paper Model plan — they need to exist in the enum for the profile to reference them.

- [ ] **Step 4: Update existing tests that reference removed types**

In `science-model/tests/test_entities.py`, update:

- Remove `test_relation_claim_entity_type` (it tests `EntityType.RELATION_CLAIM`).
- Update any test that creates entities with `EntityType.CLAIM` to use `EntityType.PROPOSITION`.

- [ ] **Step 5: Run all entity tests**

Run: `cd science-model && uv run --frozen pytest tests/test_entities.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd science-model && git add src/science_model/entities.py tests/test_entities.py
git commit -m "refactor: replace claim/evidence/artifact entity types with proposition/observation

Part of Project Model redesign (docs/specs/2026-04-05-project-model-design.md).
- Add PROPOSITION, OBSERVATION, FINDING, STORY entity types
- Remove CLAIM, RELATION_CLAIM, EVIDENCE, ARTIFACT
- PAPER now means compositional paper; ARTICLE for external literature"
```

---

### Task 2: Update Core Profile Entity Kinds

**Files:**
- Modify: `science-model/src/science_model/profiles/core.py`
- Test: `science-model/tests/test_profile_manifests.py`

- [ ] **Step 1: Write failing tests for new profile entity kinds**

```python
# Append to science-model/tests/test_profile_manifests.py

def test_core_profile_has_proposition_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "proposition" in kind_names


def test_core_profile_has_observation_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "observation" in kind_names


def test_core_profile_has_finding_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "finding" in kind_names


def test_core_profile_has_story_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "story" in kind_names


def test_core_profile_has_paper_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "paper" in kind_names


def test_core_profile_no_claim_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "claim" not in kind_names


def test_core_profile_no_relation_claim_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "relation_claim" not in kind_names


def test_core_profile_no_evidence_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "evidence" not in kind_names


def test_core_profile_no_artifact_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "artifact" not in kind_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-model && uv run --frozen pytest tests/test_profile_manifests.py -v -k "proposition or observation or finding or story or paper_kind or no_claim or no_relation or no_evidence or no_artifact"`
Expected: FAIL

- [ ] **Step 3: Update entity kinds in core profile**

Replace entity_kinds list in `science-model/src/science_model/profiles/core.py`:

```python
CORE_PROFILE = ProfileManifest(
    name="core",
    imports=[],
    strictness="core",
    entity_kinds=[
        EntityKind(
            name="proposition",
            canonical_prefix="proposition",
            layer="layer/core",
            description="Truth-apt statement — the fundamental epistemic unit.",
        ),
        EntityKind(
            name="question",
            canonical_prefix="question",
            layer="layer/core",
            description="Open or resolved research question.",
        ),
        EntityKind(
            name="observation",
            canonical_prefix="observation",
            layer="layer/core",
            description="Concrete empirical fact anchored to specific data.",
        ),
        EntityKind(
            name="hypothesis",
            canonical_prefix="hypothesis",
            layer="layer/core",
            description="Named bundle of related propositions under investigation.",
        ),
        EntityKind(
            name="task",
            canonical_prefix="task",
            layer="layer/core",
            description="Operational project task tracked in the graph.",
        ),
        EntityKind(
            name="experiment",
            canonical_prefix="experiment",
            layer="layer/core",
            description="Bounded investigation that tests questions or hypotheses.",
        ),
        EntityKind(
            name="method",
            canonical_prefix="method",
            layer="layer/core",
            description="Analytical method or computational approach.",
        ),
        EntityKind(
            name="workflow",
            canonical_prefix="workflow",
            layer="layer/core",
            description="Reusable pipeline definition (Snakefile + config + rules).",
        ),
        EntityKind(
            name="workflow-run",
            canonical_prefix="workflow-run",
            layer="layer/core",
            description="Concrete execution of a workflow producing durable outputs.",
        ),
        EntityKind(
            name="workflow-step",
            canonical_prefix="workflow-step",
            layer="layer/core",
            description="Individual step within a workflow definition or run.",
        ),
        EntityKind(
            name="data-package",
            canonical_prefix="data-package",
            layer="layer/core",
            description="Frictionless research package containing analysis results and provenance.",
        ),
        EntityKind(
            name="finding",
            canonical_prefix="finding",
            layer="layer/core",
            description="Unit of learned knowledge: propositions grounded by observations from an analysis.",
        ),
        EntityKind(
            name="interpretation",
            canonical_prefix="interpretation",
            layer="layer/core",
            description="One analysis session's narrative and its findings.",
        ),
        EntityKind(
            name="story",
            canonical_prefix="story",
            layer="layer/core",
            description="Coherent narrative arc synthesizing interpretations around a question or hypothesis.",
        ),
        EntityKind(
            name="paper",
            canonical_prefix="paper",
            layer="layer/core",
            description="Ordered composition of stories structured for communication.",
        ),
    ],
```

- [ ] **Step 4: Update existing tests that reference removed kinds**

In `test_profile_manifests.py`:
- Update `test_core_profile_contains_task_and_hypothesis`: replace `"claim"` and `"evidence"` with `"proposition"` and `"observation"`.
- Remove `test_core_profile_has_artifact_kind`.
- Remove `test_derived_from_connects_artifact_to_data_package`.

- [ ] **Step 5: Run all profile tests**

Run: `cd science-model && uv run --frozen pytest tests/test_profile_manifests.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd science-model && git add src/science_model/profiles/core.py tests/test_profile_manifests.py
git commit -m "refactor: update core profile entity kinds for Project Model

Replace claim/relation_claim/evidence/artifact with proposition/observation.
Add finding/interpretation/story/paper compositional kinds."
```

---

### Task 3: Update Core Profile Relation Kinds

**Files:**
- Modify: `science-model/src/science_model/profiles/core.py`
- Test: `science-model/tests/test_profile_manifests.py`

- [ ] **Step 1: Write failing tests for new relation kinds**

```python
# Append to science-model/tests/test_profile_manifests.py

def test_supports_sources_proposition_and_observation() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "supports")
    assert "proposition" in rel.source_kinds
    assert "observation" in rel.source_kinds
    assert "claim" not in rel.source_kinds
    assert "evidence" not in rel.source_kinds


def test_supports_targets_proposition() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "supports")
    assert "proposition" in rel.target_kinds
    assert "hypothesis" in rel.target_kinds
    assert "claim" not in rel.target_kinds
    assert "relation_claim" not in rel.target_kinds


def test_disputes_sources_proposition_and_observation() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "disputes")
    assert "proposition" in rel.source_kinds
    assert "observation" in rel.source_kinds


def test_core_profile_has_grounded_by_relation() -> None:
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "grounded_by" in rel_names


def test_grounded_by_connects_finding_to_data_package() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "grounded_by")
    assert "finding" in rel.source_kinds
    assert "data-package" in rel.target_kinds
    assert "workflow-run" in rel.target_kinds


def test_core_profile_has_addresses_relation() -> None:
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "addresses" in rel_names


def test_addresses_connects_question_to_proposition() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "addresses")
    assert "question" in rel.source_kinds
    assert "proposition" in rel.target_kinds


def test_core_profile_has_synthesizes_relation() -> None:
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "synthesizes" in rel_names


def test_core_profile_has_organized_by_relation() -> None:
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "organized_by" in rel_names


def test_core_profile_has_comprises_relation() -> None:
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "comprises" in rel_names


def test_core_profile_no_derived_from_relation() -> None:
    """derived_from was artifact→data-package; artifact is retired."""
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "derived_from" not in rel_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-model && uv run --frozen pytest tests/test_profile_manifests.py -v -k "supports_sources or supports_targets or disputes_sources or grounded_by or addresses or synthesizes or organized_by or comprises or no_derived_from"`
Expected: FAIL

- [ ] **Step 3: Update relation kinds in core profile**

Replace the `relation_kinds` list in `science-model/src/science_model/profiles/core.py`:

```python
    relation_kinds=[
        RelationKind(
            name="tests",
            predicate="sci:tests",
            source_kinds=["task", "experiment", "workflow-run"],
            target_kinds=["hypothesis", "question"],
            layer="layer/core",
            description="Operational work tests a hypothesis or resolves a question.",
        ),
        RelationKind(
            name="blocked_by",
            predicate="sci:blockedBy",
            source_kinds=["task"],
            target_kinds=["task"],
            layer="layer/core",
            description="A task cannot proceed until another task is complete.",
        ),
        RelationKind(
            name="supports",
            predicate="cito:supports",
            source_kinds=["observation", "proposition"],
            target_kinds=["proposition", "hypothesis"],
            layer="layer/core",
            description="An observation or proposition provides evidence for a proposition or hypothesis.",
        ),
        RelationKind(
            name="disputes",
            predicate="cito:disputes",
            source_kinds=["observation", "proposition"],
            target_kinds=["proposition", "hypothesis"],
            layer="layer/core",
            description="An observation or proposition provides evidence against a proposition or hypothesis.",
        ),
        RelationKind(
            name="addresses",
            predicate="sci:addresses",
            source_kinds=["question"],
            target_kinds=["proposition"],
            layer="layer/core",
            description="A question frames or is addressed by a proposition.",
        ),
        RelationKind(
            name="contains",
            predicate="sci:contains",
            source_kinds=["workflow", "finding", "interpretation"],
            target_kinds=["workflow-step", "proposition", "observation", "finding"],
            layer="layer/core",
            description="A container entity includes its components.",
        ),
        RelationKind(
            name="grounded_by",
            predicate="sci:groundedBy",
            source_kinds=["finding"],
            target_kinds=["data-package", "workflow-run"],
            layer="layer/core",
            description="A finding is traceable to the data/code that produced its observations.",
        ),
        RelationKind(
            name="synthesizes",
            predicate="sci:synthesizes",
            source_kinds=["story"],
            target_kinds=["interpretation"],
            layer="layer/core",
            description="A story draws from and synthesizes interpretations.",
        ),
        RelationKind(
            name="organized_by",
            predicate="sci:organizedBy",
            source_kinds=["story"],
            target_kinds=["question", "hypothesis"],
            layer="layer/core",
            description="A story is organized around a question or hypothesis.",
        ),
        RelationKind(
            name="comprises",
            predicate="sci:comprises",
            source_kinds=["paper"],
            target_kinds=["story"],
            layer="layer/core",
            description="A paper is composed of stories.",
        ),
        RelationKind(
            name="realizes",
            predicate="sci:realizes",
            source_kinds=["workflow"],
            target_kinds=["method"],
            layer="layer/core",
            description="A workflow is the executable realization of a method.",
        ),
        RelationKind(
            name="executes",
            predicate="sci:executes",
            source_kinds=["workflow-run"],
            target_kinds=["workflow"],
            layer="layer/core",
            description="A workflow run executes a specific workflow.",
        ),
        RelationKind(
            name="supersedes",
            predicate="sci:supersedes",
            source_kinds=["workflow-run"],
            target_kinds=["workflow-run"],
            layer="layer/core",
            description="A workflow run replaces a prior run.",
        ),
        RelationKind(
            name="feeds_into",
            predicate="sci:feedsInto",
            source_kinds=["workflow-step"],
            target_kinds=["workflow-step"],
            layer="layer/core",
            description="A workflow step feeds data into another step.",
        ),
        RelationKind(
            name="produced_by",
            predicate="sci:producedBy",
            source_kinds=["data-package"],
            target_kinds=["workflow-run"],
            layer="layer/core",
            description="A data package was produced by a specific workflow run.",
        ),
        RelationKind(
            name="grounds",
            predicate="sci:grounds",
            source_kinds=["workflow-run"],
            target_kinds=["observation"],
            layer="layer/core",
            description="A workflow run produced data cited by an observation.",
        ),
    ],
)
```

- [ ] **Step 4: Update remaining old tests referencing removed relations**

In `test_profile_manifests.py`:
- Remove `test_core_profile_has_derived_from_relation`.
- Remove `test_derived_from_connects_artifact_to_data_package` (if not already removed in Task 2).
- Update `test_core_profile_workflow_relations` if it references removed relation names.

- [ ] **Step 5: Run all profile tests**

Run: `cd science-model && uv run --frozen pytest tests/test_profile_manifests.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd science-model && git add src/science_model/profiles/core.py tests/test_profile_manifests.py
git commit -m "refactor: update core profile relation kinds for Project Model

- supports/disputes now use proposition+observation as sources, proposition+hypothesis as targets
- Add addresses, grounded_by, synthesizes, organized_by, comprises, grounds
- Remove derived_from (artifact retired)
- Broaden contains to include finding→prop/obs and interpretation→finding"
```

---

### Task 4: Run Full science-model Test Suite

**Files:**
- All files in `science-model/tests/`

- [ ] **Step 1: Run full test suite**

Run: `cd science-model && uv run --frozen pytest -v`
Expected: Some tests may fail due to references to old entity types in other test files.

- [ ] **Step 2: Fix any remaining test failures**

Grep for remaining references to old entity types and update:

```bash
cd science-model && grep -rn "EntityType\.CLAIM\|EntityType\.RELATION_CLAIM\|EntityType\.EVIDENCE\|EntityType\.ARTIFACT\|EntityType\.PAPER" tests/
```

Replace:
- `EntityType.CLAIM` → `EntityType.PROPOSITION`
- `EntityType.RELATION_CLAIM` → `EntityType.PROPOSITION`
- `EntityType.EVIDENCE` → `EntityType.OBSERVATION`
- `EntityType.ARTIFACT` → `EntityType.DATA_PACKAGE`
- `EntityType.PAPER` → `EntityType.ARTICLE` (for literature references) or `EntityType.PAPER` (for compositional papers, context-dependent)

Also check string literals: `"claim"`, `"relation_claim"`, `"evidence"`, `"artifact"`.

- [ ] **Step 3: Run full test suite again**

Run: `cd science-model && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 4: Run linting**

Run: `cd science-model && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
cd science-model && git add -A
git commit -m "fix: update remaining tests for Project Model entity types"
```

---

### Task 5: Update Graph Store — Proposition Operations

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_cli.py`

- [ ] **Step 1: Write failing test for add_proposition**

```python
# Add to science-tool/tests/test_graph_cli.py or a new test_graph_store.py

def test_add_proposition(tmp_graph):
    """add_proposition creates a Proposition node with text and provenance."""
    from science_tool.graph.store import add_proposition, _load_dataset, _graph_uri, SCI_NS, SCHEMA_NS, PROJECT_NS
    from rdflib.namespace import RDF

    uri = add_proposition(
        tmp_graph,
        text="BRCA1 regulates DNA repair",
        source="article:smith-2024",
        confidence=0.8,
        proposition_id="brca1-regulates-dna-repair",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (uri, RDF.type, SCI_NS.Proposition) in knowledge
    assert (uri, SCHEMA_NS.text, None) in knowledge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_add_proposition -v`
Expected: FAIL — `add_proposition` does not exist.

- [ ] **Step 3: Implement add_proposition**

Add to `science-tool/src/science_tool/graph/store.py` (after the existing `add_claim` function, which will be removed later):

```python
def add_proposition(
    graph_path: Path,
    text: str,
    source: str,
    confidence: float | None = None,
    evidence_type: str | None = None,
    proposition_id: str | None = None,
    subject: str | None = None,
    predicate: str | None = None,
    obj: str | None = None,
) -> URIRef:
    """Add a proposition to the knowledge graph.

    When subject/predicate/obj are provided, the proposition has structured
    S-P-O form (replacing the former relation_claim).
    """
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    if proposition_id is not None:
        token = _slug(proposition_id)
        if not token:
            raise click.ClickException("Proposition ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{source}|{text}".encode("utf-8")).hexdigest()[:12]

    prop_uri = URIRef(PROJECT_NS[f"proposition/{token}"])
    knowledge.add((prop_uri, RDF.type, SCI_NS.Proposition))
    knowledge.add((prop_uri, SCHEMA_NS.text, Literal(text)))

    # Structured S-P-O form (optional)
    if subject and predicate and obj:
        subject_uri = _resolve_term(subject)
        predicate_uri = _resolve_term(predicate)
        object_uri = _resolve_term(obj)
        knowledge.add((prop_uri, SCI_NS.propSubject, subject_uri))
        knowledge.add((prop_uri, SCI_NS.propPredicate, predicate_uri))
        knowledge.add((prop_uri, SCI_NS.propObject, object_uri))

    provenance.add((prop_uri, PROV.wasDerivedFrom, _resolve_term(source)))
    if confidence is not None:
        provenance.add((prop_uri, SCI_NS.confidence, Literal(confidence, datatype=XSD.decimal)))
    if evidence_type is not None:
        provenance.add((prop_uri, SCI_NS.evidenceType, Literal(evidence_type)))

    _save_dataset(dataset, graph_path)
    return prop_uri
```

Note: `SCI_NS.propSubject`/`propPredicate`/`propObject` replace the former `claimSubject`/`claimPredicate`/`claimObject`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py::test_add_proposition -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py tests/
git commit -m "feat: add add_proposition to graph store

Replaces add_claim and add_relation_claim. Supports optional S-P-O
structured form via subject/predicate/obj parameters."
```

---

### Task 6: Update Graph Store — Observation + Evidence Edges

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Test: `science-tool/tests/test_graph_cli.py`

- [ ] **Step 1: Write failing tests**

```python
def test_add_observation(tmp_graph):
    from science_tool.graph.store import add_observation, _load_dataset, _graph_uri, SCI_NS
    from rdflib.namespace import RDF

    uri = add_observation(
        tmp_graph,
        description="Correlation r=0.73, p<0.001",
        data_source="data-package:expr-results",
        metric="pearson_r",
        value="0.73",
        observation_id="expr-corr-01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (uri, RDF.type, SCI_NS.Observation) in knowledge


def test_add_evidence_edge(tmp_graph):
    """Evidence is a relation (edge), not a node."""
    from science_tool.graph.store import (
        add_proposition, add_observation, add_evidence_edge,
        _load_dataset, _graph_uri, SCI_NS
    )
    from rdflib.namespace import RDF
    from rdflib import Literal

    obs_uri = add_observation(tmp_graph, description="r=0.73", data_source="data-package:x", observation_id="obs1")
    prop_uri = add_proposition(tmp_graph, text="X correlates with Y", source="article:a", proposition_id="prop1")
    add_evidence_edge(
        tmp_graph,
        source_entity=str(obs_uri),
        target_entity=str(prop_uri),
        stance="supports",
        strength="moderate",
        caveats="Small sample size",
    )
    dataset = _load_dataset(tmp_graph)
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    from rdflib import PROV
    from rdflib.namespace import CITO
    # The reified edge should exist — check for annotation
    found = False
    for s, p, o in provenance:
        if p == SCI_NS.evidenceStrength:
            found = True
    assert found
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py -v -k "add_observation or add_evidence_edge"`
Expected: FAIL

- [ ] **Step 3: Implement add_observation**

```python
def add_observation(
    graph_path: Path,
    description: str,
    data_source: str,
    metric: str | None = None,
    value: str | None = None,
    uncertainty: str | None = None,
    conditions: str | None = None,
    observation_id: str | None = None,
) -> URIRef:
    """Add an observation — a concrete empirical fact anchored to data."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if observation_id is not None:
        token = _slug(observation_id)
        if not token:
            raise click.ClickException("Observation ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{data_source}|{description}".encode("utf-8")).hexdigest()[:12]

    obs_uri = URIRef(PROJECT_NS[f"observation/{token}"])
    knowledge.add((obs_uri, RDF.type, SCI_NS.Observation))
    knowledge.add((obs_uri, SCHEMA_NS.description, Literal(description)))
    knowledge.add((obs_uri, SCI_NS.dataSource, _resolve_term(data_source)))
    if metric:
        knowledge.add((obs_uri, SCI_NS.metric, Literal(metric)))
    if value:
        knowledge.add((obs_uri, SCI_NS.value, Literal(value)))
    if uncertainty:
        knowledge.add((obs_uri, SCI_NS.uncertainty, Literal(uncertainty)))
    if conditions:
        knowledge.add((obs_uri, SCI_NS.conditions, Literal(conditions)))

    _save_dataset(dataset, graph_path)
    return obs_uri
```

- [ ] **Step 4: Implement add_evidence_edge**

```python
def add_evidence_edge(
    graph_path: Path,
    source_entity: str,
    target_entity: str,
    stance: str,
    strength: str | None = None,
    caveats: str | None = None,
    method: str | None = None,
) -> None:
    """Add a supports/disputes evidence edge with annotations.

    Evidence is a relation (annotated edge), not a node.
    In RDF: reified statement in the provenance layer.
    """
    if stance not in ("supports", "disputes"):
        raise click.ClickException(f"Stance must be 'supports' or 'disputes', got '{stance}'")

    dataset = _load_dataset(graph_path)
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    source_uri = _resolve_term(source_entity)
    target_uri = _resolve_term(target_entity)
    predicate_uri = CITO_NS.supports if stance == "supports" else CITO_NS.disputes

    # Add the direct edge in knowledge layer
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    knowledge.add((source_uri, predicate_uri, target_uri))

    # Reify in provenance for annotations
    stmt_token = hashlib.sha1(f"{source_entity}|{stance}|{target_entity}".encode("utf-8")).hexdigest()[:12]
    stmt_uri = URIRef(PROJECT_NS[f"evidence/{stmt_token}"])
    provenance.add((stmt_uri, RDF.type, RDF.Statement))
    provenance.add((stmt_uri, RDF.subject, source_uri))
    provenance.add((stmt_uri, RDF.predicate, predicate_uri))
    provenance.add((stmt_uri, RDF.object, target_uri))

    if strength:
        provenance.add((stmt_uri, SCI_NS.evidenceStrength, Literal(strength)))
    if caveats:
        provenance.add((stmt_uri, SCI_NS.evidenceCaveats, Literal(caveats)))
    if method:
        provenance.add((stmt_uri, SCI_NS.evidenceMethod, Literal(method)))

    _save_dataset(dataset, graph_path)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science-tool && uv run --frozen pytest tests/test_graph_cli.py -v -k "add_observation or add_evidence_edge"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py tests/
git commit -m "feat: add observation and evidence-as-relation to graph store

add_observation creates concrete empirical facts anchored to data.
add_evidence_edge creates supports/disputes edges with reified
annotations (strength, caveats, method) in the provenance layer."
```

---

### Task 7: Update Graph Store — Rename and Remove Old Operations

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`

- [ ] **Step 1: Rename add_paper to add_article**

In `store.py`, rename the `add_paper` function to `add_article`:

```python
def add_article(graph_path: Path, doi: str) -> URIRef:
    """Add an external literature reference to the knowledge graph."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    doi_slug = _slug(doi)
    article_uri = URIRef(PROJECT_NS[f"article/doi_{doi_slug}"])
    knowledge.add((article_uri, RDF.type, SCI_NS.Article))
    knowledge.add((article_uri, SCHEMA_NS.identifier, Literal(doi)))

    _save_dataset(dataset, graph_path)
    return article_uri
```

- [ ] **Step 2: Remove add_claim, add_relation_claim, add_artifact**

Delete the `add_claim`, `add_relation_claim`, and `add_artifact` functions from `store.py`. Their functionality is replaced by `add_proposition` and the data-package `type` field.

- [ ] **Step 3: Update PROJECT_ENTITY_PREFIXES**

```python
PROJECT_ENTITY_PREFIXES: set[str] = {
    "proposition",
    "observation",
    "concept",
    "hypothesis",
    "dataset",
    "question",
    "inquiry",
    "task",
    "data-package",
    "finding",
    "interpretation",
    "story",
    "paper",
    "article",
}
```

- [ ] **Step 4: Update RELATION_CLAIM_PREDICATE_URIS**

Rename to `STRUCTURED_PROPOSITION_PREDICATES` or remove if no longer needed. If relation claims were used to infer predicate types, this set may still be useful:

```python
STRUCTURED_PROPOSITION_PREDICATES: frozenset[URIRef] = frozenset(
    {
        SCI_NS.relatedTo,
        SCIC_NS.causes,
        SCIC_NS.confounds,
        CITO_NS.supports,
        CITO_NS.disputes,
        CITO_NS.discusses,
    }
)
```

- [ ] **Step 5: Run existing tests to check for breakage**

Run: `cd science-tool && uv run --frozen pytest tests/ -v --tb=short 2>&1 | head -100`
Expected: Some failures from tests referencing `add_claim`, `add_paper`, etc. — these will be fixed in Task 10.

- [ ] **Step 6: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py
git commit -m "refactor: rename add_paper→add_article, remove add_claim/add_relation_claim/add_artifact

Old operations replaced by add_proposition (Task 5) and add_evidence_edge (Task 6).
Update PROJECT_ENTITY_PREFIXES to match new entity types."
```

---

### Task 8: Update CLI Commands

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`

- [ ] **Step 1: Replace `graph add claim` with `graph add proposition`**

Find the CLI command registration for `claim` under the `graph add` group and replace it:

```python
@graph_add.command("proposition")
@click.argument("text")
@click.option("--source", required=True, help="Provenance reference (e.g., article:smith-2024)")
@click.option("--confidence", type=float, default=None, help="Confidence level (0.0-1.0)")
@click.option("--evidence-type", default=None, help="Evidence type classification")
@click.option("--id", "proposition_id", default=None, help="Custom proposition ID slug")
@click.option("--subject", default=None, help="Structured S-P-O: subject entity")
@click.option("--predicate", default=None, help="Structured S-P-O: predicate")
@click.option("--object", "obj", default=None, help="Structured S-P-O: object entity")
@click.pass_context
def add_proposition_cmd(ctx, text, source, confidence, evidence_type, proposition_id, subject, predicate, obj):
    """Add a proposition to the knowledge graph."""
    graph_path = _graph_path(ctx)
    uri = add_proposition(graph_path, text, source, confidence, evidence_type, proposition_id, subject, predicate, obj)
    click.echo(f"Added proposition: {uri}")
```

- [ ] **Step 2: Replace `graph add relation-claim` with nothing** (functionality merged into `graph add proposition --subject --predicate --object`)

Remove the `relation-claim` CLI command.

- [ ] **Step 3: Add `graph add observation` command**

```python
@graph_add.command("observation")
@click.argument("description")
@click.option("--data-source", required=True, help="Reference to data-package or dataset")
@click.option("--metric", default=None, help="What was measured")
@click.option("--value", default=None, help="Measured value")
@click.option("--uncertainty", default=None, help="Measurement uncertainty")
@click.option("--conditions", default=None, help="Experimental conditions")
@click.option("--id", "observation_id", default=None, help="Custom observation ID slug")
@click.pass_context
def add_observation_cmd(ctx, description, data_source, metric, value, uncertainty, conditions, observation_id):
    """Add an observation — a concrete empirical fact anchored to data."""
    graph_path = _graph_path(ctx)
    uri = add_observation(graph_path, description, data_source, metric, value, uncertainty, conditions, observation_id)
    click.echo(f"Added observation: {uri}")
```

- [ ] **Step 4: Add `graph add evidence` command for evidence edges**

```python
@graph_add.command("evidence")
@click.argument("source_entity")
@click.argument("target_entity")
@click.option("--stance", required=True, type=click.Choice(["supports", "disputes"]))
@click.option("--strength", default=None, type=click.Choice(["strong", "moderate", "weak"]))
@click.option("--caveats", default=None, help="Limitations or qualifications")
@click.option("--method", default=None, help="How support/dispute was established")
@click.pass_context
def add_evidence_cmd(ctx, source_entity, target_entity, stance, strength, caveats, method):
    """Add an evidence edge (supports/disputes) between entities."""
    graph_path = _graph_path(ctx)
    add_evidence_edge(graph_path, source_entity, target_entity, stance, strength, caveats, method)
    click.echo(f"Added {stance} edge: {source_entity} → {target_entity}")
```

- [ ] **Step 5: Rename `graph add paper` to `graph add article`**

```python
@graph_add.command("article")
@click.argument("doi")
@click.pass_context
def add_article_cmd(ctx, doi):
    """Add an external literature reference by DOI."""
    graph_path = _graph_path(ctx)
    uri = add_article(graph_path, doi)
    click.echo(f"Added article: {uri}")
```

Remove the old `paper` add command.

- [ ] **Step 6: Update imports at top of cli.py**

Add new imports and remove old ones:

```python
from science_tool.graph.store import (
    add_proposition,
    add_observation,
    add_evidence_edge,
    add_article,
    add_hypothesis,
    add_question,
    # ... keep other existing imports
)
```

Remove imports of: `add_claim`, `add_relation_claim`, `add_paper`, `add_artifact`.

- [ ] **Step 7: Search for remaining references to old functions in cli.py**

```bash
cd science-tool && grep -n "add_claim\|add_relation_claim\|add_paper\|add_artifact\|EVIDENCE_TYPES" src/science_tool/cli.py
```

Update or remove any remaining references.

- [ ] **Step 8: Commit**

```bash
cd science-tool && git add src/science_tool/cli.py
git commit -m "refactor: update CLI commands for Project Model

- graph add proposition (replaces claim + relation-claim)
- graph add observation (new)
- graph add evidence (new, creates annotated edge)
- graph add article (replaces paper)"
```

---

### Task 9: Update Task Model — Artifact and Finding Links

**Files:**
- Modify: `science-model/src/science_model/tasks.py`
- Test: `science-model/tests/test_tasks.py`

- [ ] **Step 1: Write failing test**

```python
# Append to science-model/tests/test_tasks.py

def test_task_has_artifacts_field():
    from science_model.tasks import Task
    t = Task(id="1", title="Run analysis", artifacts=["data-package:results-01"])
    assert t.artifacts == ["data-package:results-01"]


def test_task_has_findings_field():
    from science_model.tasks import Task
    t = Task(id="1", title="Run analysis", findings=["finding:f01"])
    assert t.findings == ["finding:f01"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-model && uv run --frozen pytest tests/test_tasks.py -v -k "artifacts or findings"`
Expected: FAIL

- [ ] **Step 3: Add fields to Task model**

In `science-model/src/science_model/tasks.py`, add to the `Task` class:

```python
    artifacts: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science-model && uv run --frozen pytest tests/test_tasks.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd science-model && git add src/science_model/tasks.py tests/test_tasks.py
git commit -m "feat: add artifacts and findings fields to Task model

Closes the traceability loop: task → artifacts → observations → findings → propositions."
```

---

### Task 10: Update Source Loading

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py`

- [ ] **Step 1: Update _CORE_KINDS cache**

The `_CORE_KINDS` frozenset is computed at import time from `CORE_PROFILE.entity_kinds`. Since we updated the core profile in Task 2, this automatically picks up the new kinds. Verify:

```bash
cd science-tool && uv run python -c "from science_tool.graph.sources import _CORE_KINDS; print(sorted(_CORE_KINDS))"
```

Expected: Should include `proposition`, `observation`, `finding`, `story`, `paper` and NOT include `claim`, `relation_claim`, `evidence`, `artifact`.

- [ ] **Step 2: Check entity type mapping in source loading**

The source loading code uses `entity.kind` (a string) from frontmatter, not the `EntityType` enum directly. Existing project source files that use `type: claim` will need to be handled during migration. For now, source loading should accept both old and new types.

No code changes needed in sources.py for this — the `kind` field is a string, not validated against the enum. The `known_kinds()` function will reject unknown kinds during audit, which is the correct behavior (migration converts old types first).

- [ ] **Step 3: Commit**

```bash
cd science-tool && git add src/science_tool/graph/sources.py
git commit -m "verify: source loading compatible with new entity types"
```

---

### Task 11: Update Materialization

**Files:**
- Modify: `science-tool/src/science_tool/graph/materialize.py`

- [ ] **Step 1: Verify _kind_class_name handles new types**

The `_kind_class_name` function converts kind strings to PascalCase for RDF types. Verify it handles the new kinds:

```bash
cd science-tool && uv run python -c "
from science_tool.graph.materialize import _kind_class_name
for kind in ['proposition', 'observation', 'finding', 'story', 'paper', 'interpretation']:
    print(f'{kind} -> {_kind_class_name(kind)}')"
```

Expected:
```
proposition -> Proposition
observation -> Observation
finding -> Finding
story -> Story
paper -> Paper
interpretation -> Interpretation
```

- [ ] **Step 2: Update _add_relations for evidence-as-relation**

Currently `_add_relations` maps `entity.kind == "task"` to `SCI_NS.tests`. We may want to add similar special-case handling for evidence edges (e.g., when a proposition's `related` field contains another proposition with a `supports:` prefix). However, this depends on the source file format for evidence edges.

For now, evidence edges will be added via `sources.relations` (authored relations) rather than `entity.related`. No change needed to `_add_relations`.

- [ ] **Step 3: Commit** (if changes were made, otherwise skip)

---

### Task 12: Update science-tool Tests

**Files:**
- Modify: `science-tool/tests/test_graph_cli.py`
- Modify: `science-tool/tests/test_graph_materialize.py`
- Modify: Any other test files referencing old entity types

- [ ] **Step 1: Find all references to old entity types in tests**

```bash
cd science-tool && grep -rn "add_claim\|add_relation_claim\|add_paper\|add_artifact\|\"claim\"\|\"relation_claim\"\|\"evidence\"\|\"artifact\"" tests/
```

- [ ] **Step 2: Update test references**

For each occurrence:
- `add_claim(...)` → `add_proposition(...)`
- `add_relation_claim(...)` → `add_proposition(..., subject=..., predicate=..., obj=...)`
- `add_paper(...)` → `add_article(...)`
- `add_artifact(...)` → remove or convert to data-package test
- String literals `"claim"` → `"proposition"`, `"evidence"` → `"observation"`, etc.

- [ ] **Step 3: Run full test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 4: Run linting**

Run: `cd science-tool && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
cd science-tool && git add tests/
git commit -m "fix: update science-tool tests for Project Model entity types"
```

---

### Task 13: Update Predicate Registry

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py` (PREDICATE_REGISTRY section)

- [ ] **Step 1: Update PREDICATE_REGISTRY entries**

Find the `PREDICATE_REGISTRY` list (around line 1585) and update:

- Change `"layer": "relation-claim"` entries to `"layer": "graph/knowledge"` (relation claims are gone)
- Add new predicates:
  ```python
  {"predicate": "sci:addresses", "layer": "graph/knowledge", "description": "Question addresses proposition"},
  {"predicate": "sci:groundedBy", "layer": "graph/knowledge", "description": "Finding grounded by data-package or workflow-run"},
  {"predicate": "sci:synthesizes", "layer": "graph/knowledge", "description": "Story synthesizes interpretation"},
  {"predicate": "sci:organizedBy", "layer": "graph/knowledge", "description": "Story organized by question or hypothesis"},
  {"predicate": "sci:comprises", "layer": "graph/knowledge", "description": "Paper comprises stories"},
  {"predicate": "sci:grounds", "layer": "graph/provenance", "description": "Workflow-run grounds observation"},
  {"predicate": "sci:dataSource", "layer": "graph/knowledge", "description": "Observation data source"},
  {"predicate": "sci:evidenceStrength", "layer": "graph/provenance", "description": "Evidence edge strength annotation"},
  {"predicate": "sci:evidenceCaveats", "layer": "graph/provenance", "description": "Evidence edge caveats annotation"},
  {"predicate": "sci:evidenceMethod", "layer": "graph/provenance", "description": "Evidence edge method annotation"},
  ```
- Remove predicates that reference `claimSubject`/`claimPredicate`/`claimObject` (replaced by `propSubject`/`propPredicate`/`propObject`)

- [ ] **Step 2: Commit**

```bash
cd science-tool && git add src/science_tool/graph/store.py
git commit -m "refactor: update predicate registry for Project Model relations"
```

---

### Task 14: Update Skills and Templates — Terminology

**Files:**
- Modify: `skills/research/SKILL.md`
- Modify: `skills/writing/SKILL.md`
- Modify: `skills/research/provenance.md`
- Modify: `skills/research/lab-notebook.md`
- Modify: `templates/paper-summary.md`
- Modify: `templates/hypothesis.md`
- Modify: `templates/experiment.md`
- Modify: `templates/interpretation.md`
- Modify: `templates/comparison.md`

- [ ] **Step 1: Update research skill**

In `skills/research/SKILL.md`:
- Replace "claim-centric model" → "proposition-centric model"
- Replace "claims and relation-claims" → "propositions"
- Replace "evidence supports or disputes claims" → "observations and propositions support or dispute propositions via evidence edges"

- [ ] **Step 2: Update writing skill**

In `skills/writing/SKILL.md`:
- Replace `relation_claim` → `proposition`

- [ ] **Step 3: Update provenance skill**

In `skills/research/provenance.md`:
- Replace `artifact` references → `data-package` with `type: result`
- Update `derived_from` relation description → finding's `grounded_by` relation

- [ ] **Step 4: Update lab-notebook skill**

In `skills/research/lab-notebook.md`:
- Replace `artifact` registration pattern → data-package pattern

- [ ] **Step 5: Update templates**

In `templates/paper-summary.md`:
- Change `id: "paper:{{bibtex_key}}"` → `id: "article:{{bibtex_key}}"`
- Change `type: "paper"` → `type: "article"`

In `templates/hypothesis.md`:
- Replace "claims" and "relation-claims" → "propositions"

In `templates/experiment.md`:
- Replace "claims or relation-claims" → "propositions"

In `templates/interpretation.md`:
- Replace "claim or relation-claim" → "proposition"

In `templates/comparison.md`:
- Replace "claims" → "propositions"

- [ ] **Step 6: Run grep to verify no remaining old terminology**

```bash
grep -rn "relation.claim\|relation_claim" skills/ templates/
grep -rn '"claim"' templates/  # Check for type: "claim" in frontmatter
```

- [ ] **Step 7: Commit**

```bash
git add skills/ templates/
git commit -m "docs: update skills and templates for Project Model terminology

Replace claim/relation_claim → proposition, evidence → observation/evidence edge,
artifact → data-package, paper → article (for literature references)."
```

---

### Task 15: Update Documentation — Claim and Evidence Model

**Files:**
- Modify: `docs/claim-and-evidence-model.md`

- [ ] **Step 1: Rename and rewrite**

Rename file to `docs/proposition-and-evidence-model.md` (keep old file with a redirect note).

Rewrite the document to reflect the new model:
- "Claim" → "Proposition" throughout
- "Relation claim" → "Proposition with S-P-O structure"
- "Evidence item" (entity) → "Evidence edge" (annotated relation)
- Update entity type tables
- Update worked examples
- Add new entity types: observation, finding

The document should reference the Project Model spec as the canonical design source.

- [ ] **Step 2: Update cross-references**

Search for other docs that reference `claim-and-evidence-model.md` and update the links:

```bash
grep -rn "claim-and-evidence-model" docs/ skills/
```

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "docs: rewrite claim-and-evidence model as proposition-and-evidence model

Comprehensive update to reflect Project Model redesign: propositions replace
claims, evidence is now a relation, observations anchor empirical facts."
```

---

### Task 16: Migration Script

**Files:**
- Create: `science-tool/src/science_tool/graph/project_model_migration.py`
- Test: `science-tool/tests/test_project_model_migration.py`

- [ ] **Step 1: Write failing test for entity type migration**

```python
# science-tool/tests/test_project_model_migration.py

import yaml
from pathlib import Path
from science_tool.graph.project_model_migration import migrate_entity_sources


def test_migrate_claim_to_proposition(tmp_path: Path) -> None:
    """claim entities in source files become propositions."""
    source = tmp_path / "doc" / "claims" / "c01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: claim:c01\ntype: claim\ntitle: Test claim\nrelated: []\nsource_refs: []\n---\nBody text\n"
    )
    results = migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: proposition" in content
    assert "id: proposition:c01" in content
    assert results["migrated"] >= 1


def test_migrate_relation_claim_to_proposition(tmp_path: Path) -> None:
    """relation_claim entities become propositions."""
    source = tmp_path / "doc" / "claims" / "rc01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: relation_claim:rc01\ntype: relation_claim\ntitle: X causes Y\nrelated: []\nsource_refs: []\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: proposition" in content
    assert "id: proposition:rc01" in content


def test_migrate_evidence_to_observation(tmp_path: Path) -> None:
    """evidence entities become observations (empirical content preserved)."""
    source = tmp_path / "doc" / "evidence" / "e01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: evidence:e01\ntype: evidence\ntitle: Correlation data\nrelated: []\nsource_refs: []\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "type: observation" in content
    assert "id: observation:e01" in content


def test_migrate_paper_to_article(tmp_path: Path) -> None:
    """paper (literature) entities become articles."""
    source = tmp_path / "doc" / "background" / "papers" / "smith-2024.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: paper:smith-2024\ntype: paper\ntitle: Smith 2024\nrelated: []\nsource_refs: []\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert 'type: "article"' in content or "type: article" in content
    assert "id: article:smith-2024" in content


def test_migrate_updates_cross_references(tmp_path: Path) -> None:
    """related and source_refs fields update old prefixes."""
    source = tmp_path / "doc" / "hypotheses" / "h01.md"
    source.parent.mkdir(parents=True)
    source.write_text(
        "---\nid: hypothesis:h01\ntype: hypothesis\ntitle: H1\nrelated:\n  - claim:c01\n  - evidence:e01\nsource_refs:\n  - paper:smith-2024\n---\n"
    )
    migrate_entity_sources(tmp_path)
    content = source.read_text()
    assert "proposition:c01" in content
    assert "observation:e01" in content
    assert "article:smith-2024" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science-tool && uv run --frozen pytest tests/test_project_model_migration.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement migration script**

```python
# science-tool/src/science_tool/graph/project_model_migration.py
"""Migration script: convert project sources from old entity model to Project Model."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

# Entity type renames
_TYPE_RENAMES = {
    "claim": "proposition",
    "relation_claim": "proposition",
    "evidence": "observation",
    "artifact": "data-package",
}

# Paper → article for literature references (in doc/background/papers/)
_PAPER_TO_ARTICLE = True

# ID prefix renames (same as type renames, plus paper→article)
_PREFIX_RENAMES = {
    "claim": "proposition",
    "relation_claim": "proposition",
    "evidence": "observation",
    "artifact": "data-package",
    "paper": "article",
}


def migrate_entity_sources(project_root: Path) -> dict[str, int]:
    """Migrate all entity source files in a project to the new model.

    Returns counts of migrated entities.
    """
    stats = {"migrated": 0, "skipped": 0, "errors": 0}

    # Scan all markdown files in doc/ and specs/
    for md_dir in ["doc", "specs"]:
        scan_dir = project_root / md_dir
        if not scan_dir.exists():
            continue
        for md_file in sorted(scan_dir.rglob("*.md")):
            try:
                if _migrate_file(md_file):
                    stats["migrated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception:
                stats["errors"] += 1

    # Scan structured sources in knowledge/sources/
    sources_dir = project_root / "knowledge" / "sources"
    if sources_dir.exists():
        for yaml_file in sorted(sources_dir.rglob("*.yaml")):
            try:
                if _migrate_yaml_source(yaml_file):
                    stats["migrated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception:
                stats["errors"] += 1

    return stats


def _migrate_file(path: Path) -> bool:
    """Migrate a single markdown file. Returns True if changes were made."""
    text = path.read_text(encoding="utf-8")

    # Split frontmatter
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not match:
        return False

    fm_text = match.group(1)
    body = match.group(2)

    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return False

    if not isinstance(fm, dict):
        return False

    changed = False
    entity_type = fm.get("type", "")

    # Rename entity type
    if entity_type in _TYPE_RENAMES:
        fm["type"] = _TYPE_RENAMES[entity_type]
        changed = True
    elif entity_type == "paper":
        fm["type"] = "article"
        changed = True

    # Rename ID prefix
    entity_id = fm.get("id", "")
    if ":" in entity_id:
        prefix, slug = entity_id.split(":", 1)
        if prefix in _PREFIX_RENAMES:
            fm["id"] = f"{_PREFIX_RENAMES[prefix]}:{slug}"
            changed = True

    # Update cross-references in related, source_refs, blocked_by
    for field in ("related", "source_refs", "blocked_by"):
        refs = fm.get(field, [])
        if isinstance(refs, list):
            new_refs = [_rename_ref(r) for r in refs]
            if new_refs != refs:
                fm[field] = new_refs
                changed = True

    if not changed:
        return False

    new_fm_text = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True).rstrip()
    path.write_text(f"---\n{new_fm_text}\n---\n{body}", encoding="utf-8")
    return True


def _migrate_yaml_source(path: Path) -> bool:
    """Migrate a structured YAML source file."""
    text = path.read_text(encoding="utf-8")
    new_text = text

    for old, new in _PREFIX_RENAMES.items():
        new_text = new_text.replace(f"{old}:", f"{new}:")

    for old, new in _TYPE_RENAMES.items():
        new_text = re.sub(rf"type:\s*{old}\b", f"type: {new}", new_text)

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def _rename_ref(ref: str) -> str:
    """Rename a cross-reference prefix if it matches an old entity type."""
    if ":" not in ref:
        return ref
    prefix, slug = ref.split(":", 1)
    if prefix in _PREFIX_RENAMES:
        return f"{_PREFIX_RENAMES[prefix]}:{slug}"
    return ref
```

- [ ] **Step 4: Run migration tests**

Run: `cd science-tool && uv run --frozen pytest tests/test_project_model_migration.py -v`
Expected: All PASS

- [ ] **Step 5: Add CLI command for migration**

In `cli.py`, add a migration command:

```python
@graph.command("migrate-model")
@click.pass_context
def migrate_model_cmd(ctx):
    """Migrate project sources from old entity model to Project Model."""
    from science_tool.graph.project_model_migration import migrate_entity_sources

    project_root = ctx.obj["project_root"]
    stats = migrate_entity_sources(project_root)
    click.echo(f"Migration complete: {stats['migrated']} migrated, {stats['skipped']} skipped, {stats['errors']} errors")
    if stats["errors"] > 0:
        click.echo("Review errors manually — some files may need manual migration.")
```

- [ ] **Step 6: Commit**

```bash
cd science-tool && git add src/science_tool/graph/project_model_migration.py tests/test_project_model_migration.py src/science_tool/cli.py
git commit -m "feat: add Project Model migration script

Automated migration of entity source files:
- claim/relation_claim → proposition
- evidence → observation
- paper (literature) → article
- artifact → data-package
- Updates cross-references in related/source_refs fields
CLI: science-tool graph migrate-model"
```

---

### Task 17: Integration Test — Full Round Trip

**Files:**
- Test: `science-tool/tests/test_project_model_integration.py`

- [ ] **Step 1: Write integration test**

```python
# science-tool/tests/test_project_model_integration.py
"""Integration test: create project sources with new entity types, materialize, and verify graph."""

from pathlib import Path

import yaml

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import _load_dataset, PROJECT_NS, SCI_NS
from rdflib.namespace import RDF


def _write_science_yaml(project_root: Path) -> None:
    config = {
        "name": "test-project",
        "profile": "research",
        "knowledge_profiles": {"local": "local"},
    }
    (project_root / "science.yaml").write_text(yaml.dump(config), encoding="utf-8")


def _write_source_entity(project_root: Path, entity_id: str, entity_type: str, title: str) -> None:
    prefix, slug = entity_id.split(":", 1)
    path = project_root / "doc" / prefix / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = {"id": entity_id, "type": entity_type, "title": title, "related": [], "source_refs": []}
    path.write_text(f"---\n{yaml.dump(fm)}---\n{title}\n", encoding="utf-8")


def test_materialize_with_proposition_and_observation(tmp_path: Path) -> None:
    project_root = tmp_path
    _write_science_yaml(project_root)
    _write_source_entity(project_root, "proposition:p01", "proposition", "X correlates with Y")
    _write_source_entity(project_root, "observation:obs01", "observation", "r=0.73 in dataset D")
    _write_source_entity(project_root, "question:q01", "question", "Does X cause Y?")

    trig_path = materialize_graph(project_root)
    dataset = _load_dataset(trig_path)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    # Verify proposition
    prop_uri = PROJECT_NS["proposition/p01"]
    assert (prop_uri, RDF.type, SCI_NS.Proposition) in knowledge

    # Verify observation
    obs_uri = PROJECT_NS["observation/obs01"]
    assert (obs_uri, RDF.type, SCI_NS.Observation) in knowledge

    # Verify question
    q_uri = PROJECT_NS["question/q01"]
    assert (q_uri, RDF.type, SCI_NS.Question) in knowledge
```

- [ ] **Step 2: Run integration test**

Run: `cd science-tool && uv run --frozen pytest tests/test_project_model_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd science-tool && git add tests/test_project_model_integration.py
git commit -m "test: add integration test for Project Model round trip"
```

---

### Task 18: Final Verification

- [ ] **Step 1: Run full science-model test suite**

Run: `cd science-model && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 2: Run full science-tool test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 3: Run linting on both packages**

```bash
cd science-model && uv run --frozen ruff check . && uv run --frozen ruff format --check .
cd science-tool && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: Clean

- [ ] **Step 4: Run type checking**

```bash
cd science-model && uv run --frozen pyright
cd science-tool && uv run --frozen pyright
```
Expected: No new errors

- [ ] **Step 5: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: final Project Model cleanup — linting, type checks"
```

# Mechanism Entity and Topic Deprecation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a strict `mechanism` entity to the Science model and tooling, replace topic-stub guidance with semantic triage, and isolate legacy `topic` support to migration-only surfaces.

**Architecture:** Land this in two layers. First, define a typed `mechanism` contract in `science-model` and thread it through unified loading/materialization so projects can represent named explanatory structures without using `topic`. Second, update authoring and audit surfaces in `science-tool` so unresolved refs are triaged into semantic homes instead of producing more `topic` debt. Keep legacy `topic` loading only where existing projects still need migration visibility.

**Tech Stack:** Python 3.12, Pydantic models, rdflib graph materialization, Click CLI, pytest, ruff, pyright

**Non-Goals:** Do not expand the biology catalog opportunistically. Do not rebrand `topic` as a softer synonym for `mechanism`. Do not add wildcard compatibility aliases for new authoring. Do not migrate MM30 entities/refs in this branch.

---

### Task 1: Align The Canonical Specs

**Files:**
- Modify: `docs/specs/2026-04-05-project-model-design.md`
- Modify: `docs/specs/2026-04-21-unified-entity-references-design.md`
- Reference: `docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md`

**Step 1: Write the failing doc assertions as a checklist**

Add a short checklist at the top of the working branch notes or commit message target:

```text
- topic is not the recommended semantic fallback
- mechanism is defined as a strict explanatory entity
- story remains narrative, not semantic fallback
- topic guidance is explicitly marked legacy / migration-only
```

**Step 2: Update the project-model spec**

Add a new subsection near `story` / `hypothesis`:

```markdown
### Mechanism

A mechanism is a named explanatory structure involving multiple typed entities
and one or more explicit propositions. It is not a theme tag or prose title.
```

**Step 3: Rewrite the unified-reference spec's topic section**

Replace the "narrow topic" recommendation with:

```markdown
- use domain kinds, method, concept, hypothesis, interpretation, story, or mechanism
- do not create new topic entities for semantic authoring
- treat existing topic refs as migration debt
```

Also add two explicit scope lines:

```markdown
- direct support/dispute/grounding edges to `mechanism` are out of v1 scope
- MM30 migration is a follow-on branch, not part of this implementation
```

**Step 4: Verify the wording is internally consistent**

Run: `rg -n "narrow the \`topic\`|genuine cross-theme|legitimate \`topic\`|topic stubs" docs/specs/2026-04-05-project-model-design.md docs/specs/2026-04-21-unified-entity-references-design.md`

Expected: no remaining text that still recommends `topic` for new semantic modeling work.

**Step 5: Commit**

```bash
git add docs/specs/2026-04-05-project-model-design.md docs/specs/2026-04-21-unified-entity-references-design.md
git commit -m "docs: define mechanism and deprecate topic fallback"
```

### Task 2: Freeze The `mechanism` Contract In Tests

**Files:**
- Modify: `science-model/tests/test_entities.py`
- Modify: `science-model/tests/test_frontmatter.py`
- Modify: `science-tool/tests/test_entity_registry.py`
- Modify: `science-tool/tests/test_graph_materialize.py`

**Step 1: Write the failing entity-model tests**

Add tests for a valid mechanism and two invalid ones:

```python
def test_mechanism_entity_requires_participants_and_propositions() -> None:
    raw = {
        "id": "mechanism:phf19-prc2-ifn-immunotherapy",
        "canonical_id": "mechanism:phf19-prc2-ifn-immunotherapy",
        "kind": "mechanism",
        "type": EntityType.MECHANISM,
        "title": "PHF19 / PRC2 / IFN / immunotherapy",
        "project": "mm30",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "Mechanistic summary.",
        "file_path": "doc/mechanisms/phf19-prc2-ifn-immunotherapy.md",
        "participants": ["protein:PHF19", "concept:prc2-complex"],
        "propositions": ["proposition:ifn-silencing"],
        "summary": "PHF19-PRC2 dampens IFN signaling relevant to immunotherapy.",
    }
    entity = MechanismEntity.model_validate(raw)
    assert entity.kind == "mechanism"
```

Also add explicit invariant failures:

```python
def test_mechanism_entity_rejects_single_participant() -> None:
    with pytest.raises(ValidationError, match="at least two participants"):
        MechanismEntity.model_validate({**VALID_RAW, "participants": ["concept:only-one"]})

def test_mechanism_entity_rejects_missing_propositions() -> None:
    with pytest.raises(ValidationError, match="at least one proposition"):
        MechanismEntity.model_validate({**VALID_RAW, "propositions": []})

def test_mechanism_entity_rejects_empty_summary() -> None:
    with pytest.raises(ValidationError, match="non-empty summary"):
        MechanismEntity.model_validate({**VALID_RAW, "summary": "  "})
```

**Step 2: Write the failing frontmatter test**

Add a markdown fixture under `doc/mechanisms/` and assert:

```python
assert entity.kind == "mechanism"
assert entity.id == "mechanism:test-mechanism"
assert entity.file_path == "doc/mechanisms/test-mechanism.md"
```

Use participant refs from allowed v1 kinds only:

```python
assert entity.participants == ["protein:PHF19", "concept:prc2-complex"]
```

**Step 3: Write the failing registry/materialization tests**

Add assertions like:

```python
assert registry.resolve("mechanism") is MechanismEntity
assert (mechanism_uri, SCI_NS.hasParticipant, participant_uri) in knowledge
assert (mechanism_uri, SCI_NS.hasProposition, proposition_uri) in knowledge
```

**Step 4: Run the targeted tests to verify they fail**

Run: `uv run --frozen pytest science-model/tests/test_entities.py science-model/tests/test_frontmatter.py science-tool/tests/test_entity_registry.py science-tool/tests/test_graph_materialize.py -q`

Expected: failures mentioning missing `MECHANISM` type, missing registry entry, or absent materialization predicates.

**Step 5: Commit**

```bash
git add science-model/tests/test_entities.py science-model/tests/test_frontmatter.py science-tool/tests/test_entity_registry.py science-tool/tests/test_graph_materialize.py
git commit -m "test: lock mechanism entity behavior"
```

### Task 3: Implement `MechanismEntity` In `science-model`

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Modify: `science-model/src/science_model/frontmatter.py`
- Modify: `science-model/src/science_model/profiles/core.py`
- Modify: `science-model/src/science_model/__init__.py`

**Step 1: Add the new entity type and typed subclass**

Add `MECHANISM = "mechanism"` and a typed subclass:

```python
class MechanismEntity(ProjectEntity):
    participants: list[str] = Field(default_factory=list)
    propositions: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="after")
    def _validate_mechanism_shape(self) -> "MechanismEntity":
        if len(self.participants) < 2:
            raise ValueError("mechanism requires at least two participants")
        if any(ref.split(":", 1)[0] not in ALLOWED_MECHANISM_PARTICIPANT_KINDS for ref in self.participants):
            raise ValueError("mechanism participants must be domain/catalog entities or concept entities")
        if not self.propositions:
            raise ValueError("mechanism requires at least one proposition")
        if not self.summary.strip():
            raise ValueError("mechanism requires a non-empty summary")
        return self
```

**Step 2: Teach frontmatter parsing about `doc/mechanisms/`**

Extend `_DIR_TO_KIND` and preserve mechanism-specific fields:

```python
_DIR_TO_KIND["mechanisms"] = "mechanism"
```

If `parse_entity_file()` still returns a plain `Entity`, upgrade it to instantiate
the right typed class for `mechanism` only. Do **not** broaden this branch into
generic typed dispatch for `story`, `hypothesis`, or other compositional kinds.

Also add a small note near the implementation that `proposition` is already a
first-class kind and not a new prerequisite for this branch.

**Step 3: Register `mechanism` in the core profile**

Add:

```python
EntityKind(
    name="mechanism",
    canonical_prefix="mechanism",
    layer="layer/core",
    description="Named explanatory structure linking multiple typed entities and propositions.",
)
```

Also add v1 relation kinds for authored structure:

```python
RelationKind(
    name="has_participant",
    predicate="sci:hasParticipant",
    source_kinds=["mechanism"],
    target_kinds=[],
    layer="layer/core",
    description="Mechanism participant link.",
)
RelationKind(
    name="has_proposition",
    predicate="sci:hasProposition",
    source_kinds=["mechanism"],
    target_kinds=["proposition"],
    layer="layer/core",
    description="Mechanism-defining proposition link.",
)
```

If empty `target_kinds` causes validation trouble elsewhere, stop and add a
small wildcard-support change rather than lying about the allowed targets.

**Step 4: Run the model tests**

Run: `uv run --frozen pytest science-model/tests/test_entities.py science-model/tests/test_frontmatter.py -q`

Expected: PASS.

**Step 5: Avoid partial mechanism fixtures**

Do not land project fixtures or authored `mechanism:` refs outside the tests
that are updated together with registry/materialization support in Task 4.

**Step 6: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/src/science_model/frontmatter.py science-model/src/science_model/profiles/core.py science-model/src/science_model/__init__.py
git commit -m "feat: add mechanism entity to science model"
```

### Task 4: Wire `mechanism` Through Unified Loading And Materialization

**Files:**
- Modify: `science-tool/src/science_tool/graph/entity_registry.py`
- Modify: `science-tool/src/science_tool/graph/materialize.py`
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/tests/test_load_project_sources_unified.py`
- Modify: `science-tool/tests/test_entity_registry.py`
- Modify: `science-tool/tests/test_graph_materialize.py`

**Step 1: Register the typed class**

Route the new kind through the registry:

```python
r.register_core_kind("mechanism", MechanismEntity)
```

Do not register `mechanism` as a generic `ProjectEntity`.

**Step 2: Materialize mechanism structure explicitly**

Extend `_add_entity()` / `_add_relations()` so mechanisms emit:

```python
knowledge.add((mechanism_uri, SCI_NS.hasParticipant, participant_uri))
knowledge.add((mechanism_uri, SCI_NS.hasProposition, proposition_uri))
knowledge.add((mechanism_uri, SCHEMA_NS.description, Literal(entity.summary)))
```

Use normal resolver paths so participants can point at catalog-backed or local
entities, and propositions resolve strictly.

**Step 3: Add mechanism to project-entity URI handling**

Update `PROJECT_ENTITY_PREFIXES` so store-level relation helpers recognize
`mechanism:` URIs as project entities.

Before changing it, confirm why `topic` is currently absent from that constant
and document whether the effect is limited to warning/validation paths or
something broader. Do not copy the existing omission blindly.

**Step 4: Write or update the unified-load regression**

Add a raw aggregate or markdown fixture with:

```yaml
id: mechanism:anti-coupling-axis
kind: mechanism
participants:
  - concept:translation
  - concept:cell-state
propositions:
  - proposition:anti-coupling
summary: Translation and cell-state programs move in opposite directions.
```

Assert that `load_project_sources()` yields `MechanismEntity`.

**Step 5: Run the targeted tool tests**

Run: `uv run --frozen pytest science-tool/tests/test_load_project_sources_unified.py science-tool/tests/test_entity_registry.py science-tool/tests/test_graph_materialize.py -q`

Expected: PASS.

**Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/entity_registry.py science-tool/src/science_tool/graph/materialize.py science-tool/src/science_tool/graph/store.py science-tool/tests/test_load_project_sources_unified.py science-tool/tests/test_entity_registry.py science-tool/tests/test_graph_materialize.py
git commit -m "feat: materialize mechanism entities"
```

### Task 5: Replace Topic-Stub Guidance With Semantic Triage

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`
- Modify: `codex-skills/science-health/SKILL.md`
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/src/science_tool/graph/tags_migration.py`

**Step 1: Write the failing health tests**

Add expectations that unresolved `topic:` refs are reported as migration hints,
not default stub work:

```python
assert by_target["topic:t143"] == "task"
assert by_target["topic:h99-bar"] == "hypothesis"
assert by_target["topic:genomics"] == "semantic-triage"
```

**Step 2: Update health classification names and copy**

Change the output contract from "real topics" to semantic homes:

```text
domain entity / method / concept / mechanism candidate / metadata / bad prefix
```

**Step 3: Remove topic-first migration guidance**

Adjust CLI help and skill text:

```text
Do not create topic stubs by default.
Use --as-topic only for legacy migrations you have already audited.
```

**Step 4: Run the health and migration tests**

Run: `uv run --frozen pytest science-tool/tests/test_health.py science-tool/tests/test_graph_migrate.py -q`

Expected: PASS, with no tests still asserting "need entity stubs" for semantic labels.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/health.py science-tool/tests/test_health.py codex-skills/science-health/SKILL.md science-tool/src/science_tool/cli.py science-tool/src/science_tool/graph/tags_migration.py
git commit -m "feat: replace topic stub guidance with semantic triage"
```

### Task 6: Fence Off Other Legacy Topic Surfaces

**Files:**
- Modify: `science-tool/src/science_tool/curate/inventory.py`
- Modify: `science-tool/src/science_tool/graph/storage_adapters/aggregate.py`
- Modify: `codex-skills/science-review-tasks/SKILL.md`
- Modify: other semantic-guidance skills under `codex-skills/` found by `rg -n "topic:" codex-skills`

**Step 1: Audit the remaining topic-aware surfaces**

Run: `rg -n "topic|doc/topics|topic:" science-tool/src/science_tool/curate/inventory.py science-tool/src/science_tool/graph/storage_adapters/aggregate.py codex-skills`

Expected: a concrete list of legacy-only topic surfaces outside health/big-picture.

**Step 2: Reframe them explicitly as legacy or prose-oriented**

- `inventory.py`: keep counting topic artifacts, but do not imply they are the
  recommended semantic destination for unresolved refs.
- `aggregate.py`: keep legacy aggregate loading for `topics`, but mark it as a
  compatibility/migration surface.
- skill docs: remove semantic guidance that recommends `topic:` where `concept`,
  `method`, domain kinds, or `mechanism` are the better fit.

**Step 3: Run the targeted tests**

Run: `uv run --frozen pytest science-tool/tests/test_curate_inventory.py science-tool/tests/test_storage_adapters/test_aggregate.py -q`

Expected: PASS.

**Step 4: Commit**

```bash
git add science-tool/src/science_tool/curate/inventory.py science-tool/src/science_tool/graph/storage_adapters/aggregate.py codex-skills
git commit -m "docs: mark legacy topic surfaces as migration-only"
```

### Task 7: Fence Off Legacy Topic-Coupled Big-Picture Logic

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/knowledge_gaps.py`
- Modify: `science-tool/tests/test_knowledge_gaps_cli.py`
- Modify: `science-tool/tests/test_big_picture_validator.py`
- Modify: `science-tool/tests/fixtures/big_picture/minimal_project/...` as needed

**Step 1: Write the failing behavior test**

Choose the immediate behavior and codify it first. For this branch, the
behavior is:

```python
assert "legacy topic coverage" in result.output
```

**Step 2: Stop presenting topic coverage as semantic completeness**

Rename internal language from generic "topic gaps" to legacy topic coverage,
and keep the feature explicitly tied to authored topic docs. Do not let this
surface imply that missing semantic refs should become `topic` files.

**Step 3: Keep the validator permissive during migration**

Existing legacy `topic:` refs in fixtures can still be recognized, but warnings
and docs must frame them as migration input rather than recommended modeling.

**Step 4: Run the big-picture tests**

Run: `uv run --frozen pytest science-tool/tests/test_knowledge_gaps_cli.py science-tool/tests/test_big_picture_validator.py science-tool/tests/test_big_picture_resolver.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/knowledge_gaps.py science-tool/tests/test_knowledge_gaps_cli.py science-tool/tests/test_big_picture_validator.py science-tool/tests/test_big_picture_resolver.py
git commit -m "refactor: isolate legacy topic coverage in big picture"
```

### Task 8: Add Minimal Authoring Ergonomics For `mechanism`

**Files:**
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/tests/test_graph_export.py`
- Add or Modify: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing CLI/store test**

Add a test that creates a mechanism directly:

```python
result = runner.invoke(
    main,
    [
        "graph",
        "add",
        "mechanism",
        "PHF19 / PRC2 / IFN",
        "--summary",
        "PHF19-PRC2 dampens IFN signaling.",
        "--participant",
        "protein:PHF19",
        "--participant",
        "concept:prc2-complex",
        "--proposition",
        "proposition:ifn-silencing",
        "--graph-path",
        str(graph_path),
    ],
)
assert result.exit_code == 0
```

**Step 2: Implement the minimal store helper**

Mirror `add_story()` with strict validation:

```python
def add_mechanism(..., participants: list[str], propositions: list[str], summary: str, mechanism_id: str | None = None, ...):
    if len(participants) < 2:
        raise click.ClickException("Mechanism requires at least two participants")
```

Match the existing CLI/store pattern for custom IDs:

```python
@click.option("--id", "mechanism_id", default=None, help="Custom mechanism ID slug")
```

**Step 3: Run the CLI tests**

Run: `uv run --frozen pytest science-tool/tests/test_graph_cli.py science-tool/tests/test_graph_export.py -q`

Expected: PASS.

**Step 4: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py science-tool/tests/test_graph_export.py
git commit -m "feat: add graph CLI support for mechanisms"
```

### Task 9: Capture Domain-Model Follow-Ups And Run The Full Verification Sweep

**Files:**
- Modify: `docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md`
- Modify: `docs/plans/2026-04-22-mechanism-entity-and-topic-deprecation-implementation.md`
- Optionally modify later: `science-model/src/science_model/ontologies/biology/catalog.yaml`

**Step 1: Record the topic-deprecation closure criterion**

Add a short section or checkbox confirming that `topic` should remain registered
until all of the following are true:

```markdown
- active first-party projects no longer author new semantic `topic:*` refs
- health/curation no longer recommends topic stubs
- legacy topic-aware features are labeled legacy/migration-only
```

**Step 2: Record the two catalog questions surfaced by MM30**

Add a follow-up note:

```markdown
- evaluate `cytogenetic_event` as a local or shared domain kind
- evaluate a cleaner biology home for molecular complexes such as PRC2
```

**Step 3: Run the repo checks**

Run: `uv run --frozen ruff check .`

Expected: PASS.

Run: `uv run --frozen pyright`

Expected: PASS.

Run: `uv run --frozen pytest`

Expected: PASS.

**Step 4: Commit**

```bash
git add docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md docs/plans/2026-04-22-mechanism-entity-and-topic-deprecation-implementation.md
git commit -m "docs: capture mechanism rollout and domain follow-ups"
```

## Notes For The Implementer

- `topic` is already absent from `science-model`'s `CORE_PROFILE`, so the first code change is not "remove topic from the profile." The live coupling is in `EntityType`, `frontmatter`, `entity_registry`, big-picture tooling, fixtures, and health guidance.
- Do not fake `mechanism` by routing it through generic `ProjectEntity`; the point of this branch is to give it typed structure.
- V1 `mechanism` participants should be restricted to domain/catalog entities and `concept`, not to compositional project entities like `story`, `interpretation`, `hypothesis`, or `task`.
- V1 does **not** add direct support/dispute/grounding edges targeting `mechanism`. Keep those semantics on propositions/hypotheses unless a later branch expands them deliberately.
- `proposition` is already live infrastructure in this repo; do not treat it as a new prerequisite task.
- MM30 migration is intentionally out of scope for this branch. This branch should make MM30 migration possible, not perform it.
- If relation-kind validation cannot express `mechanism -> many target kinds`, make that limitation explicit and fix it directly. Do not encode false narrow target lists just to get tests green.
- Do not mutate the biology catalog in the same commit as the mechanism core landing unless a failing test proves it is required.

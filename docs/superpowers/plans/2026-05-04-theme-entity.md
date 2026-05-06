# Theme Entity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `theme` as a first-class Science project entity for durable cross-cutting organizing frames that link questions, hypotheses, tasks, reports, concepts, child projects, and guardrails without reviving `topic` as a catch-all.

**Architecture:** `theme` lands as a Science core epistemic entity kind with a lightweight typed model, source-authored markdown support, a template-driven shell, graph materialization through the existing generic entity path, and guidance that distinguishes it from `topic`, `concept`, `question`, `hypothesis`, `task`, `discussion`, `interpretation`, and `story`. V1 intentionally uses existing `related`, `source_refs`, and `evidence_refs` relation plumbing rather than adding theme-specific predicates.

**Tech Stack:** Python 3.13, Pydantic models in `science-model`, Click CLI helpers in `science`, rdflib materialization, pytest, template renderer in `science_model.templates`.

---

## File Structure

- Modify `science-model/src/science_model/entities.py`: add `EntityType.THEME` and `ThemeEntity`.
- Modify `science-model/src/science_model/profiles/core.py`: register `theme` in `CORE_PROFILE.entity_kinds`.
- Modify `science/src/science_tool/graph/entity_registry.py`: register `theme` as an epistemic core kind backed by `ThemeEntity`.
- Modify `science/src/science_tool/entities.py`: add source-authored path, default status, and allowed statuses for `theme`.
- Modify `science-model/src/science_model/templates.py`: add `theme` to `MIGRATED_KINDS`.
- Create `templates/theme.md`: root copy of the theme template.
- Create `science-model/src/science_model/templates/theme.md`: packaged copy of the theme template.
- Modify `science-model/tests/test_profile_manifests.py`: profile coverage for `theme`.
- Modify `science-model/tests/test_templates.py`: packaged/root template coverage for `theme`.
- Modify `science/tests/test_kind_class.py`: registry classification coverage for `theme`.
- Modify `science/tests/test_load_project_sources_unified.py`: loader produces a `ThemeEntity`.
- Modify `science/tests/test_entities.py`: CLI source-authoring path/template coverage for `theme`.
- Modify `science/tests/test_graph_materialize.py`: graph build emits `SCI.Theme` and normal related edges for theme entities.
- Modify `docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md`: add `theme` to the reclassification guidance.
- Modify `commands/create-graph.md`, `commands/update-graph.md`, and matching skill docs under `codex-skills/science-create-graph/SKILL.md` and `codex-skills/science-update-graph/SKILL.md`: teach authoring guidance to use `theme` for cross-cutting organizing frames.
- Modify `commands/tasks.md` and `codex-skills/science-tasks/SKILL.md`: update examples away from `topic:*` when the link target is a cross-cutting frame.
- Modify `commands/review-tasks.md` and `codex-skills/science-review-tasks/SKILL.md`: update review guidance away from `topic:*` for cross-cutting frames.

## Semantics

Use `theme` when the project needs to cite, review, connect, or organize a durable cross-cutting frame as a unit.

Use `concept` for atomic vocabulary terms.
Use `question` for answerable research questions.
Use `hypothesis` for testable conjectures.
Use `task` for operational work.
Use `discussion` for a bounded comparison or decision record.
Use `interpretation` for evidence interpretation from a reading or result.
Use `story` for communication-layer synthesis.
Use `mechanism` for a structured explanatory object with participants and propositions.
Do not use `topic` for new semantic authoring.

Biological themes organize multiple biological concepts, mechanisms, evidence layers, or child-project claims; never use `theme_kind: biological` for a single gene, pathway, cell type, disease, or mechanism that has a more specific entity kind.

V1 frontmatter fields:

```yaml
id: "theme:<slug>"
type: "theme"
title: "<Title>"
status: "active"
theme_kind: "methodological"
theme_scope: "project"
related: []
source_refs: []
evidence_refs: []
created: "YYYY-MM-DD"
updated: "YYYY-MM-DD"
```

Allowed `theme_kind` values in the model:

- `methodological`
- `biological`
- `translational`
- `evidence-quality`
- `organizational`

Allowed `theme_scope` values in the model:

- `project`
- `federation`
- `child`

Use `theme_scope: child` only inside a child project when the theme is local to that child but should be visible to a federation parent through normal graph/ref links.

Allowed authoring statuses:

- `draft`
- `active`
- `superseded`
- `retired`

---

### Task 1: Core Model And Profile Kind

**Files:**
- Modify: `science-model/src/science_model/entities.py`
- Modify: `science-model/src/science_model/profiles/core.py`
- Test: `science-model/tests/test_profile_manifests.py`

- [ ] **Step 1: Write failing profile tests**

Append these tests to `science-model/tests/test_profile_manifests.py`:

```python
def test_core_profile_contains_theme_kind() -> None:
    kind_names = {kind.name for kind in CORE_PROFILE.entity_kinds}
    assert "theme" in kind_names


def test_theme_kind_profile_metadata() -> None:
    kind = next(kind for kind in CORE_PROFILE.entity_kinds if kind.name == "theme")
    assert kind.canonical_prefix == "theme"
    assert kind.layer == "layer/core"
    assert "cross-cutting" in kind.description


def test_bears_on_targets_theme() -> None:
    rel = next(relation for relation in CORE_PROFILE.relation_kinds if relation.name == "bears_on")
    assert "theme" in rel.target_kinds
```

- [ ] **Step 2: Run the profile tests and verify they fail**

Run:

```bash
cd science-model && uv run --frozen pytest tests/test_profile_manifests.py -q -k "theme"
```

Expected: failure because `theme` is not in `CORE_PROFILE.entity_kinds`.

- [ ] **Step 3: Add `theme` to `EntityType` and define `ThemeEntity`**

In `science-model/src/science_model/entities.py`, replace the existing typing import:

```python
from typing import Protocol
```

with:

```python
from typing import Literal, Protocol
```

Add this enum member to `EntityType` after `STORY = "story"`:

```python
    THEME = "theme"
```

Add this class immediately after `MechanismEntity`:

```python
class ThemeEntity(ProjectEntity):
    """Durable cross-cutting organizing frame for project knowledge."""

    theme_kind: Literal[
        "methodological",
        "biological",
        "translational",
        "evidence-quality",
        "organizational",
    ] = "methodological"
    theme_scope: Literal["project", "federation", "child"] = "project"
    summary: str = ""
```

- [ ] **Step 4: Add `theme` to the core profile and `bears_on` targets**

In `science-model/src/science_model/profiles/core.py`, add this `EntityKind` after `mechanism`:

```python
        EntityKind(
            name="theme",
            canonical_prefix="theme",
            layer="layer/core",
            description="Durable cross-cutting organizing frame linking project questions, hypotheses, tasks, reports, concepts, and guardrails.",
        ),
```

In the `bears_on` relation's `target_kinds` list in the same file, add `"theme"` after `"story"`:

```python
                "story",
                "theme",
                "validation-report",
```

- [ ] **Step 5: Run the profile tests and verify they pass**

Run:

```bash
cd science-model && uv run --frozen pytest tests/test_profile_manifests.py -q -k "theme"
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/src/science_model/profiles/core.py science-model/tests/test_profile_manifests.py
git commit -m "feat(model): add theme entity kind"
```

---

### Task 2: Registry Classification And Source Loading

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py`
- Modify: `science/tests/test_kind_class.py`
- Modify: `science/tests/test_load_project_sources_unified.py`

- [ ] **Step 1: Write failing registry classification test**

In `science/tests/test_kind_class.py`, add this assertion to `test_kind_class_lookup_returns_classification`:

```python
    assert r.kind_class("theme") == EntityClass.EPISTEMIC
```

Run:

```bash
cd science && uv run --frozen pytest tests/test_kind_class.py -q -k "kind_class_lookup_returns_classification"
```

Expected: failure because `theme` is not registered.

- [ ] **Step 2: Write failing source-loader test**

In `science/tests/test_load_project_sources_unified.py`, update the import block from `science_model.entities` to include `ThemeEntity`:

```python
    ThemeEntity,
```

Append this test after `test_load_project_sources_returns_typed_mechanism_entity`:

```python
def test_load_project_sources_returns_typed_theme_entity(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "doc" / "themes").mkdir(parents=True)
    (tmp_path / "doc" / "themes" / "transportability.md").write_text(
        "\n".join(
            [
                "---",
                'id: "theme:transportability"',
                'type: "theme"',
                'title: "Transportability"',
                'status: "active"',
                'theme_kind: "methodological"',
                'theme_scope: "federation"',
                'related: ["question:q001-recurring"]',
                "source_refs: []",
                "evidence_refs: []",
                "---",
                "",
                "# Theme: Transportability",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "doc" / "questions").mkdir(parents=True)
    (tmp_path / "doc" / "questions" / "q001-recurring.md").write_text(
        "\n".join(
            [
                "---",
                'id: "question:q001-recurring"',
                'type: "question"',
                'title: "What recurs?"',
                "related: []",
                "source_refs: []",
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}
    theme = by_id["theme:transportability"]

    assert isinstance(theme, ThemeEntity)
    assert theme.kind == "theme"
    assert theme.type == EntityType.THEME
    assert theme.theme_kind == "methodological"
    assert theme.theme_scope == "federation"
```

Run:

```bash
cd science && uv run --frozen pytest tests/test_load_project_sources_unified.py -q -k "typed_theme_entity"
```

Expected: failure because the registry cannot resolve `theme`.

- [ ] **Step 3: Register `theme` in the entity registry**

In `science/src/science_tool/graph/entity_registry.py`, add `ThemeEntity` to the import list:

```python
    ThemeEntity,
```

Add this entry to `_CORE_KIND_CLASSES` under typed entities:

```python
    "theme": EntityClass.EPISTEMIC,
```

Add this registration after the mechanism registration in `with_core_types()`:

```python
        r.register_core_kind("theme", ThemeEntity, entity_class=_CORE_KIND_CLASSES["theme"])
```

- [ ] **Step 4: Run registry and loader tests**

Run:

```bash
cd science && uv run --frozen pytest tests/test_kind_class.py tests/test_load_project_sources_unified.py -q -k "theme or kind_class_lookup_returns_classification or classifies_every_kind"
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/entity_registry.py science/tests/test_kind_class.py science/tests/test_load_project_sources_unified.py
git commit -m "feat(tool): register theme entities"
```

---

### Task 3: Template-Driven Markdown Authoring

**Files:**
- Modify: `science-model/src/science_model/templates.py`
- Create: `templates/theme.md`
- Create: `science-model/src/science_model/templates/theme.md`
- Modify: `science-model/tests/test_templates.py`
- Modify: `science/src/science_tool/entities.py`
- Modify: `science/tests/test_entities.py`

- [ ] **Step 1: Write failing template tests**

In `science-model/tests/test_templates.py`, change each parametrized kind list from:

```python
["hypothesis", "question", "interpretation", "discussion"]
```

to:

```python
["hypothesis", "question", "interpretation", "discussion", "theme"]
```

In `test_packaged_template_renders_required_sections`, add this branch before the existing `if kind == "question":` branch:

```python
    if kind == "theme":
        assert frontmatter["theme_kind"] == "methodological"
        assert frontmatter["theme_scope"] == "project"
        assert "## Definition" in text
        assert "## Guardrails" in text
    elif kind == "question":
        assert "## Summary" in text
    else:
        assert "# " in text
```

Run:

```bash
cd science-model && uv run --frozen pytest tests/test_templates.py -q -k "theme or migrated_templates_match or packaged_template"
```

Expected: failure because `science_model/templates/theme.md` does not exist and `theme` is not migrated.

- [ ] **Step 2: Add `theme` to migrated template kinds**

In `science-model/src/science_model/templates.py`, change:

```python
MIGRATED_KINDS: frozenset[str] = frozenset({"hypothesis", "question", "interpretation", "discussion"})
```

to:

```python
MIGRATED_KINDS: frozenset[str] = frozenset({"hypothesis", "question", "interpretation", "discussion", "theme"})
```

- [ ] **Step 3: Create the root theme template**

Create `templates/theme.md` with exactly this content:

```markdown
---
id: "theme:{{slug}}"
type: "theme"
title: "{{title}}"
status: "{{status}}"
theme_kind: "methodological"
theme_scope: "project"
related: []
source_refs: []
evidence_refs: []
created: "{{created}}"
updated: "{{updated}}"
_template:
  frontmatter:
    id: { from: entity_id }
    type: { default: "theme" }
    title: { from: title }
    status: { from: status }
    theme_kind: { default: "methodological" }
    theme_scope: { default: "project" }
    related: { from: related }
    source_refs: { from: source_refs }
    evidence_refs: { default: [] }
    created: { from: created }
    updated: { from: updated }
  sections:
    - { key: definition, name: "Definition", required: true }
    - { key: why-it-matters, name: "Why It Matters", required: true }
    - { key: boundaries, name: "Boundaries", required: true }
    - { key: current-project-links, name: "Current Project Links", required: true }
    - { key: guardrails, name: "Guardrails", required: true }
    - { key: downstream-work, name: "Downstream Work", required: true }
    - { key: open-questions, name: "Open Questions", required: true }
    - { key: update-triggers, name: "Update Triggers", required: true }
---

# Theme: {{title}}

## Definition

<!-- Define the cross-cutting organizing frame in 2-4 sentences. -->

## Why It Matters

<!-- Explain what project-level decisions or syntheses become clearer when this theme is explicit. -->

## Boundaries

<!-- State what belongs inside this theme and what should remain a concept, question, hypothesis, task, mechanism, discussion, interpretation, or story. -->

## Current Project Links

<!-- Link the questions, hypotheses, reports, child projects, concepts, methods, and tasks currently organized by this theme. -->

## Guardrails

<!-- Record constraints that should prevent over-generalization, layer mixing, causal overclaiming, or source-method confusion. -->

## Downstream Work

<!-- List task groups, analyses, child-project follow-ups, or synthesis passes motivated by this theme. -->

## Open Questions

<!-- Name unresolved questions that would change how this theme is used. -->

## Update Triggers

<!-- State what kind of new evidence, project restructuring, or completed work should cause this theme to be reviewed. -->
```

- [ ] **Step 4: Copy the root template into the packaged templates directory**

Run:

```bash
cp templates/theme.md science-model/src/science_model/templates/theme.md
```

Expected: no output.

- [ ] **Step 5: Add source-authoring policy and statuses**

In `science/src/science_tool/entities.py`, add this entry to `_BUILTIN_MARKDOWN_POLICIES`:

```python
    "theme": EntityPathPolicy(root=Path("doc/themes"), filename="local-part"),
```

Add this entry to `_DEFAULT_STATUS`:

```python
    "theme": "active",
```

Add this entry to `_STATUS_VALUES`:

```python
    "theme": frozenset({"draft", "active", "superseded", "retired"}),
```

- [ ] **Step 6: Write failing entity authoring tests**

In `science/tests/test_entities.py`, update `test_builtin_path_policy_maps_core_kinds` with:

```python
    assert resolve_path_policy("theme").root == Path("doc/themes")
```

In `test_template_driven_create_entity_passes_prospective_audit_for_all_migrated_kinds`, append this case:

```python
        ("theme", "Template shell theme", "theme:template-shell-theme"),
```

Append this test after `test_create_entity_writes_question_source_and_loads_it`:

```python
def test_create_entity_writes_theme_source_and_loads_it(tmp_path: Path) -> None:
    seed_project(tmp_path)

    result = create_entity(
        project_root=tmp_path,
        kind="theme",
        title="Transportability Across Cancer Types",
        entity_id="theme:transportability-across-cancer-types",
        related=[],
        source_refs=[],
        today=date(2026, 5, 4),
    )

    assert result.entity_id == "theme:transportability-across-cancer-types"
    assert result.path == tmp_path / "doc/themes/transportability-across-cancer-types.md"
    assert result.warnings == []
    text = result.path.read_text(encoding="utf-8")
    assert 'type: theme' in text or 'type: "theme"' in text or "type: 'theme'" in text
    assert "theme_kind: methodological" in text or 'theme_kind: "methodological"' in text
    assert "## Definition" in text
    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}
    assert "theme:transportability-across-cancer-types" in by_id
```

- [ ] **Step 7: Run template and authoring tests**

Run:

```bash
cd science-model && uv run --frozen pytest tests/test_templates.py -q
cd ../science && uv run --frozen pytest tests/test_entities.py -q -k "theme or builtin_path_policy or template_driven_create_entity"
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add science-model/src/science_model/templates.py science-model/src/science_model/templates/theme.md templates/theme.md science-model/tests/test_templates.py science/src/science_tool/entities.py science/tests/test_entities.py
git commit -m "feat(entity): add theme authoring template"
```

---

### Task 4: Graph Materialization And Reference Resolution

**Files:**
- Modify: `science/tests/test_graph_materialize.py`

- [ ] **Step 1: Write failing graph materialization test**

Append this test after `test_materialize_graph_emits_mechanism_participants_and_propositions`:

```python
def test_materialize_graph_emits_theme_node_and_related_edges(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    (project / "doc" / "themes").mkdir(parents=True)
    (project / "doc" / "themes" / "transportability.md").write_text(
        "\n".join(
            [
                "---",
                'id: "theme:transportability"',
                'type: "theme"',
                'title: "Transportability"',
                'status: "active"',
                'theme_kind: "methodological"',
                'theme_scope: "federation"',
                'related: ["question:q01-demo"]',
                "source_refs: []",
                "evidence_refs: []",
                "---",
                "",
                "# Theme: Transportability",
                "",
            ]
        ),
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)

    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    theme_uri = PROJECT_NS["theme/transportability"]
    question_uri = PROJECT_NS["question/q01-demo"]

    assert (theme_uri, RDF.type, SCI.Theme) in knowledge
    assert (theme_uri, SKOS.prefLabel, Literal("Transportability")) in knowledge
    assert (theme_uri, SCI.profile, Literal("core")) in knowledge
    assert (theme_uri, SKOS.related, question_uri) in knowledge
```

Run:

```bash
cd science && uv run --frozen pytest tests/test_graph_materialize.py -q -k "theme_node"
```

Expected: pass without materialization code changes, because Tasks 1-3 registered `theme` and the generic entity materializer already emits RDF type, label, profile, provenance, and `related` edges.

- [ ] **Step 2: Run reference and materialization regression subset**

Run:

```bash
cd science && uv run --frozen pytest tests/test_graph_materialize.py tests/test_load_project_sources_unified.py tests/test_health.py -q -k "theme or unresolved or materialize_graph"
```

Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_graph_materialize.py
git commit -m "test(graph): cover theme materialization"
```

---

### Task 5: Guidance And Command Documentation

**Files:**
- Modify: `docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md`
- Modify: `commands/create-graph.md`
- Modify: `commands/update-graph.md`
- Modify: `commands/tasks.md`
- Modify: `commands/review-tasks.md`
- Modify: `codex-skills/science-create-graph/SKILL.md`
- Modify: `codex-skills/science-update-graph/SKILL.md`
- Modify: `codex-skills/science-tasks/SKILL.md`
- Modify: `codex-skills/science-review-tasks/SKILL.md`

- [ ] **Step 1: Update topic-deprecation guidance**

In `docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md`, update the reclassification list by inserting this item after the `concept` item:

```markdown
4. **Is this a durable cross-cutting organizing frame?**
   Use `theme`. A theme links multiple questions, hypotheses, tasks,
   reports, methods, concepts, child projects, or guardrails as a named
   project lens. It is not a generic background topic and should carry
   boundaries, current links, guardrails, downstream work, and update triggers.
```

Renumber the following items by one.

- [ ] **Step 2: Add create/update graph guidance**

In `commands/create-graph.md` and `codex-skills/science-create-graph/SKILL.md`, replace the sentence:

```markdown
- add missing local-profile entities for legitimate project-local concepts
```

with:

```markdown
- add missing local-profile entities for legitimate project-local concepts
- add `theme` markdown entities under `doc/themes/` when the missing node is a durable cross-cutting organizing frame that links multiple questions, hypotheses, tasks, reports, methods, concepts, child projects, or guardrails.
```

In `commands/update-graph.md` and `codex-skills/science-update-graph/SKILL.md`, add this bullet under the entity-authoring guidance:

```markdown
- Use `theme:<slug>` for durable cross-cutting organizing frames. Do not use `topic:<slug>` for new semantic authoring; use `concept` for atomic vocabulary and `theme` for the project-level lens that organizes other entities.
```

- [ ] **Step 3: Locate topic examples in task and review-task guidance**

Run:

```bash
rg -n "topic:protein-folding|topic:umap|especially topic references" commands/tasks.md commands/review-tasks.md codex-skills/science-tasks/SKILL.md codex-skills/science-review-tasks/SKILL.md
```

Expected: matches in `commands/tasks.md`, `commands/review-tasks.md`, `codex-skills/science-tasks/SKILL.md`, and `codex-skills/science-review-tasks/SKILL.md`.

- [ ] **Step 4: Update task-linking examples away from topic**

In `commands/tasks.md`, `commands/review-tasks.md`, `codex-skills/science-tasks/SKILL.md`, and `codex-skills/science-review-tasks/SKILL.md`, replace examples like:

```markdown
topic:protein-folding
topic:umap
```

with:

```markdown
theme:protein-folding-generalization
method:umap
```

Also replace:

```markdown
Tasks sharing the same `related` entities (especially topic references)
```

with:

```markdown
Tasks sharing the same `related` entities, especially `theme:` references for cross-cutting work and `method:` references for analytical procedures
```

- [ ] **Step 5: Run documentation checks**

Run:

```bash
rg -n "topic:protein-folding|topic:umap|especially topic references" commands codex-skills
```

Expected: no matches.

Run:

```bash
rg -n "theme:<slug>|doc/themes|durable cross-cutting" commands codex-skills docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md
```

Expected: matches in the edited guidance files.

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md commands/create-graph.md commands/update-graph.md commands/tasks.md commands/review-tasks.md codex-skills/science-create-graph/SKILL.md codex-skills/science-update-graph/SKILL.md codex-skills/science-tasks/SKILL.md codex-skills/science-review-tasks/SKILL.md
git commit -m "docs: document theme entity usage"
```

---

### Task 6: End-To-End CLI Smoke Test

**Files:**
- Modify: `science/tests/test_entities_cli.py`

- [ ] **Step 1: Add a CLI smoke test**

Append this test to `science/tests/test_entities_cli.py`:

```python
def test_entity_create_theme_cli_round_trips() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "entity",
                "create",
                "theme",
                "Transportability Across Cancer Types",
                "--id",
                "theme:transportability-across-cancer-types",
            ],
        )

        assert result.exit_code == 0, result.output
        path = Path("doc/themes/transportability-across-cancer-types.md")
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "theme:transportability-across-cancer-types" in text
        assert "## Definition" in text
```

- [ ] **Step 2: Run the CLI smoke test**

Run:

```bash
cd science && uv run --frozen pytest tests/test_entities_cli.py -q -k "theme_cli_round_trips"
```

Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_entities_cli.py
git commit -m "test(cli): cover theme entity creation"
```

---

### Task 7: Full Verification

**Files:**
- No source edits.

- [ ] **Step 1: Run formatting**

Run:

```bash
uv run --frozen ruff format science-model science
```

Expected: command exits 0. When files are reformatted, include those changes in the final commit.

- [ ] **Step 2: Run lint**

Run:

```bash
uv run --frozen ruff check science-model science
```

Expected: command exits 0.

- [ ] **Step 3: Run focused tests**

Run:

```bash
cd science-model && uv run --frozen pytest tests/test_profile_manifests.py tests/test_templates.py -q
cd ../science && uv run --frozen pytest tests/test_kind_class.py tests/test_load_project_sources_unified.py tests/test_entities.py tests/test_entities_cli.py tests/test_graph_materialize.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run full package tests**

Run:

```bash
cd science-model && uv run --frozen pytest -q
cd ../science && uv run --frozen pytest -q
```

Expected: both commands exit 0.

- [ ] **Step 5: Run an end-to-end temporary project check**

Run:

```bash
tmpdir="$(mktemp -d)"
cd "$tmpdir"
printf 'name: theme-smoke\nprofile: research\nknowledge_profiles:\n  local: local\n' > science.yaml
uv run --project /home/keith/d/science/science --frozen science entity create theme "Transportability Across Cancer Types" --id theme:transportability-across-cancer-types --no-hints
uv run --project /home/keith/d/science/science --frozen science refs check
uv run --project /home/keith/d/science/science --frozen science graph build
test -f knowledge/graph.trig
```

Expected: entity creation succeeds, refs check reports valid references, graph build writes `knowledge/graph.trig`.

- [ ] **Step 6: Final commit for verification-only changes**

When Task 7 produces formatting-only changes, run:

```bash
git add science-model science
git commit -m "style: format theme entity changes"
```

When Task 7 produces no file changes, skip this commit.

---

## Self-Review

- Spec coverage: The plan adds the core kind, model class, registry classification, `bears_on` freshness targeting, markdown authoring path, template, graph materialization coverage, CLI smoke coverage, and authoring guidance. It keeps v1 authored relations to existing `related`, `source_refs`, and `evidence_refs`, matching the agreed scope.
- Placeholder scan: No implementation step depends on unresolved design choices.
- Type consistency: The plan uses `theme_kind`, `theme_scope`, `ThemeEntity`, `EntityType.THEME`, `doc/themes`, and `theme:<slug>` consistently across model, registry, template, tests, and guidance.
- Scope check: The plan deliberately avoids adding theme-specific predicates, migration tooling, or a bespoke `science theme` command. Generic `science entity create theme ...` is the v1 CLI surface.

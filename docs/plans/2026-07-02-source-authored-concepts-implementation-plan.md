# Source-Authored Concepts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable `science entity create concept ...` as the durable Markdown owner path for project-local concepts while preserving lightweight `terms.yaml` rows and non-durable `graph add concept` guidance.

**Architecture:** This is a narrow policy correction in the existing generic entity writer: remove the explicit `concept` block and prove the existing slug path, status vocabulary, source loader, graph build, and collision diagnostics already carry the behavior. Documentation then shifts from "concept authoring is a CLI/model mismatch" to a three-tier contract: most specific registered kind first, `terms.yaml` for lightweight local terms, and `entities/concepts/*.md` for full project concepts.

**Tech Stack:** Python 3.13, Click `CliRunner`, `pytest`, existing Science source loaders/materializer, Markdown user guide and command docs, generated Codex skill mirrors via `scripts/generate_codex_skills.py`.

---

## File Structure

- Modify `science/src/science_tool/entities.py`
  - Remove the `kind == "concept"` guard in `create_entity()`.
  - Do not add a new concept-specific path; concept should use the existing generic entity path policy.
- Modify `science/tests/test_entities_cli.py`
  - Add CLI coverage for creating concept entities, status validation, construct sibling behavior, source loading, and graph build.
- Modify `science/tests/test_load_project_sources_unified.py`
  - Add confirmation coverage for `terms.yaml`/aggregate rows colliding with `entities/concepts/*.md`.
- Modify `science/tests/test_user_guide_docs.py`
  - Replace mismatch guard tests with source-authored concept contract guard tests.
- Modify `science/tests/test_command_docs.py`
  - Replace command-doc assertions that forbid `science entity create concept ...` with assertions that permit the durable concept path while continuing to reject `science graph add concept` as durable authoring.
- Modify `science/tests/test_codex_skills.py`
  - Mirror the command-doc guard changes for committed and freshly generated Codex skills.
- Modify `docs/user-guide/entities.md`
  - Replace "Current Concept Ownership Mismatch" with a supported source-authored concept section.
- Modify `docs/user-guide/epistemic-model.md`
  - Replace "future supported concept entity" / "CLI does not support" wording with current supported concept entity wording.
- Modify `commands/sketch-model.md`
  - Allow concept entity creation for full reusable project-local concepts.
- Modify `commands/specify-model.md`
  - Point specified-model refs at source records, lightweight term rows, or source-authored concept entities.
- Modify `commands/create-graph.md`
  - Align concept triage language with source-authored concepts and lightweight terms.
- Modify `commands/health.md`
  - Align semantic triage language with source-authored concepts and lightweight terms.
- Regenerate:
  - `codex-skills/science-sketch-model/SKILL.md`
  - `codex-skills/science-specify-model/SKILL.md`
  - `codex-skills/science-create-graph/SKILL.md`
  - `codex-skills/science-health/SKILL.md`
  - any other generated skill mirror changed by `scripts/generate_codex_skills.py`

## Preconditions

- Work in the isolated worktree `.worktrees/source-authored-concepts-design`.
- Preserve any existing user edits in `docs/audits/framework-surface/source-authored-concepts-design.md`; do not revert them.
- Use this test command shape from the repository root:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest science/tests/test_entities_cli.py -q
```

---

### Task 1: Add Red CLI Tests For Source-Authored Concepts

**Files:**
- Modify: `science/tests/test_entities_cli.py`

- [ ] **Step 1: Add imports**

At the top of `science/tests/test_entities_cli.py`, add `materialize_graph` beside the existing `load_project_sources` import:

```python
from science_tool.graph.materialize import materialize_graph
```

The import block should contain both:

```python
from science_tool.graph.sources import load_project_sources
from science_tool.graph.materialize import materialize_graph
```

- [ ] **Step 2: Add failing concept CLI tests**

Add these tests after `test_entity_create_accepts_local_numeric_id_part()`:

```python
def test_entity_create_concept_writes_source() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["entity", "create", "concept", "Treatment Response"])

        assert result.exit_code == 0, result.output
        assert "concept:treatment-response" in result.output
        path = Path("entities/concepts/treatment-response.md")
        assert path.is_file()
        frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["id"] == "concept:treatment-response"
        assert frontmatter["type"] == "concept"
        assert frontmatter["title"] == "Treatment Response"
        assert frontmatter["status"] == "active"


def test_entity_create_concept_accepts_deprecated_status_and_rejects_invalid_status() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        deprecated = runner.invoke(
            main,
            ["entity", "create", "concept", "Legacy Concept", "--status", "deprecated"],
        )
        invalid = runner.invoke(
            main,
            ["entity", "create", "concept", "Bad Concept", "--status", "retired"],
        )

        assert deprecated.exit_code == 0, deprecated.output
        path = Path("entities/concepts/legacy-concept.md")
        frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["status"] == "deprecated"
        assert invalid.exit_code != 0
        assert "Invalid status for concept: retired" in invalid.output


def test_entity_create_construct_still_uses_generic_slug_path() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["entity", "create", "construct", "Treatment Response Construct"])

        assert result.exit_code == 0, result.output
        assert "construct:treatment-response-construct" in result.output
        path = Path("entities/constructs/treatment-response-construct.md")
        assert path.is_file()
        frontmatter = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert frontmatter["id"] == "construct:treatment-response-construct"
        assert frontmatter["type"] == "construct"
```

- [ ] **Step 3: Add source-load and graph-build coverage**

Add this test after the concept status test:

```python
def test_entity_create_concept_loads_and_resolves_in_graph_build() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["entity", "create", "concept", "Treatment Response"])
        assert result.exit_code == 0, result.output
        write_markdown_entity(
            root,
            "entities/hypotheses/h1.md",
            {
                "id": "hypothesis:h1",
                "type": "hypothesis",
                "title": "H1",
                "status": "proposed",
                "related": ["concept:treatment-response"],
            },
        )

        sources = load_project_sources(root)
        by_id = {entity.canonical_id: entity for entity in sources.entities}
        assert "concept:treatment-response" in by_id
        assert sources.entity_source_adapters["concept:treatment-response"] == "markdown"

        trig_path = materialize_graph(root, strict=False)
        assert trig_path.is_file()
```

- [ ] **Step 4: Run the new tests and verify they fail for the right reason**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_entities_cli.py::test_entity_create_concept_writes_source \
  science/tests/test_entities_cli.py::test_entity_create_concept_accepts_deprecated_status_and_rejects_invalid_status \
  science/tests/test_entities_cli.py::test_entity_create_concept_loads_and_resolves_in_graph_build \
  science/tests/test_entities_cli.py::test_entity_create_construct_still_uses_generic_slug_path \
  -q
```

Expected:

- The three concept tests fail with output containing `Source-authored concepts are not supported`.
- The construct sibling test passes.

Do not change implementation until the failure confirms the existing block is the cause.

---

### Task 2: Enable The Generic Concept Entity Write Path

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Test: `science/tests/test_entities_cli.py`

- [ ] **Step 1: Remove the concept-specific block**

In `science/src/science_tool/entities.py:create_entity()`, remove exactly this block:

```python
    if kind == "concept":
        raise EntityCommandError("Source-authored concepts are not supported; use graph add concept instead")
```

The function should now proceed from `today_value = today or date.today()` directly to `resolve_path_policy(kind)`.

- [ ] **Step 2: Run the red tests again**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_entities_cli.py::test_entity_create_concept_writes_source \
  science/tests/test_entities_cli.py::test_entity_create_concept_accepts_deprecated_status_and_rejects_invalid_status \
  science/tests/test_entities_cli.py::test_entity_create_concept_loads_and_resolves_in_graph_build \
  science/tests/test_entities_cli.py::test_entity_create_construct_still_uses_generic_slug_path \
  -q
```

Expected: all four tests pass.

- [ ] **Step 3: Run focused entity policy coverage**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_entities_cli.py \
  science/tests/test_slug_strategy.py \
  science/tests/test_status_visibility.py \
  -q
```

Expected: all selected tests pass. `test_status_visibility.py` should not require changes because `deprecated` is already classified in `_LIVE_STATUSES`.

- [ ] **Step 4: Commit the behavior slice**

Run:

```bash
git add science/src/science_tool/entities.py science/tests/test_entities_cli.py
git commit -m "feat: enable source-authored concepts"
```

---

### Task 3: Confirm Concept Identity Collision Handling

**Files:**
- Modify: `science/tests/test_load_project_sources_unified.py`

- [ ] **Step 1: Add an audit import**

At the top of `science/tests/test_load_project_sources_unified.py`, add:

```python
from science_tool.graph.migrate import audit_project_sources
```

Keep the existing imports for `EntityIdentityCollisionError`, `build_identity_table`, and `load_project_sources`.

- [ ] **Step 2: Add strict and non-strict collision tests**

Add these tests after `test_global_identity_collision_two_markdown_owners()`:

```python
def test_concept_markdown_owner_collides_with_terms_yaml_under_strict_identity(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "entities" / "concepts").mkdir(parents=True)
    (tmp_path / "entities" / "concepts" / "treatment-response.md").write_text(
        '---\nid: "concept:treatment-response"\ntype: "concept"\n'
        'title: "Treatment Response"\nstatus: "active"\n---\n',
        encoding="utf-8",
    )
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "terms.yaml").write_text(
        "\n".join(
            [
                "terms:",
                "  - id: concept:treatment-response",
                "    title: Treatment response term",
                "",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(EntityIdentityCollisionError, match="concept:treatment-response"):
        load_project_sources(tmp_path)


def test_concept_markdown_owner_wins_over_terms_yaml_in_nonstrict_load(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "entities" / "concepts").mkdir(parents=True)
    (tmp_path / "entities" / "concepts" / "treatment-response.md").write_text(
        '---\nid: "concept:treatment-response"\ntype: "concept"\n'
        'title: "Treatment Response"\nstatus: "active"\n---\n',
        encoding="utf-8",
    )
    local_sources = tmp_path / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "terms.yaml").write_text(
        "\n".join(
            [
                "terms:",
                "  - id: concept:treatment-response",
                "    title: Treatment response term",
                "",
            ]
        ),
        encoding="utf-8",
    )

    sources = load_project_sources(tmp_path, strict_identity=False)
    concepts = [entity for entity in sources.entities if entity.canonical_id == "concept:treatment-response"]
    owners = [
        declaration
        for declaration in sources.identity_declarations
        if declaration.canonical_id == "concept:treatment-response"
    ]

    assert len(concepts) == 1
    assert concepts[0].title == "Treatment Response"
    assert sources.entity_source_adapters["concept:treatment-response"] == "markdown"
    assert {owner.adapter for owner in owners} == {"markdown", "aggregate"}
    collisions = build_identity_table(sources).collisions()
    assert len(collisions) == 1
    assert collisions[0].canonical_id == "concept:treatment-response"

    rows, failed = audit_project_sources(sources)
    collision_rows = [row for row in rows if row["check"] == "identity_collision"]
    assert failed is False
    assert len(collision_rows) == 1
    assert collision_rows[0]["source"] == "concept:treatment-response"
    assert collision_rows[0]["status"] == "warn"
```

- [ ] **Step 3: Run collision tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_load_project_sources_unified.py::test_concept_markdown_owner_collides_with_terms_yaml_under_strict_identity \
  science/tests/test_load_project_sources_unified.py::test_concept_markdown_owner_wins_over_terms_yaml_in_nonstrict_load \
  -q
```

Expected: both tests pass. These are confirmation tests for existing loader behavior; if either fails, stop and inspect `load_project_sources()` ordering before changing production code.

- [ ] **Step 4: Run related identity tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_load_project_sources_unified.py \
  science/tests/test_identity_declarations_loader.py \
  science/tests/test_graph_migrate_identity_audit.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit the collision tests**

Run:

```bash
git add science/tests/test_load_project_sources_unified.py
git commit -m "test: pin concept identity collision behavior"
```

---

### Task 4: Update Docs Guard Tests For The New Contract

**Files:**
- Modify: `science/tests/test_user_guide_docs.py`
- Modify: `science/tests/test_command_docs.py`
- Modify: `science/tests/test_codex_skills.py`

- [ ] **Step 1: Replace the user-guide mismatch test**

In `science/tests/test_user_guide_docs.py`, replace `test_entities_chapter_documents_current_concept_ownership_mismatch()` with:

```python
def test_entities_chapter_documents_source_authored_concepts() -> None:
    text = _read(GUIDE_ROOT / "entities.md")
    section = _slice_between(
        text,
        "### Source-Authored Concepts",
        "### Legacy Topic Triage",
    )
    normalized = _norm(section)

    assert "`terms.yaml` is the lightweight concept tier" in normalized
    assert "`science entity create concept" in normalized
    assert "`entities/concepts/<slug>.md`" in normalized
    assert "Use the most specific registered kind before creating a local concept" in normalized
    assert "`science graph add concept` writes derived graph state" in normalized
    assert "Do not use graph-added concepts as durable owners" in normalized
```

- [ ] **Step 2: Update the epistemic-model guard**

In `test_epistemic_model_documents_inquiry_ref_ownership_contract()`, replace:

```python
    assert "`science graph add concept` is not durable inquiry authoring" in normalized
```

with:

```python
    assert "`science entity create concept" in normalized
    assert "`science graph add concept` is not durable inquiry authoring" in normalized
```

- [ ] **Step 3: Update command-doc guards**

In `science/tests/test_command_docs.py`, update `test_sketch_model_uses_source_first_inquiry_authoring()` by replacing these assertions:

```python
    assert "Do not use `science entity create concept` in this workflow" in normalized
    assert "Use a registered source kind, a lightweight `terms.yaml` row, or prose deferral" in normalized
```

with:

```python
    assert "Use the most specific registered source kind available before creating a local concept." in normalized
    assert "Use `science entity create concept" in normalized
    assert "when the model genuinely needs a reusable project-local concept" in normalized
    assert "Use a lightweight `terms.yaml` row when the term only needs a resolvable identity" in normalized
```

In the same test, delete these two negative assertions:

```python
    assert "```bash\nscience entity create concept" not in text
    assert "science entity create concept " not in text
```

Keep this negative assertion:

```python
    assert "```bash\nscience graph add concept" not in text
```

In `test_specify_model_marks_direct_graph_concepts_as_non_durable()`, replace:

```python
    assert "Make sure those refs resolve through source records or lightweight term rows" in normalized
```

with:

```python
    assert "Make sure those refs resolve through source records, lightweight term rows, or concept entity owners" in normalized
```

- [ ] **Step 4: Update Codex skill guards**

In both `test_concept_ownership_committed_skills_reflect_command_boundaries()` and `test_generated_concept_ownership_skills_reflect_command_boundaries()`, replace:

```python
    assert "Do not use `science entity create concept` in this workflow" in sketch_model
    assert "Use a registered source kind, a lightweight `terms.yaml` row, or prose deferral" in sketch_model
```

with:

```python
    assert "Use the most specific registered source kind available before creating a local concept." in sketch_model
    assert "Use `science entity create concept" in sketch_model
    assert "when the model genuinely needs a reusable project-local concept" in sketch_model
    assert "Use a lightweight `terms.yaml` row when the term only needs a resolvable identity" in sketch_model
```

In both tests, delete:

```python
    assert "```bash\nscience entity create concept" not in sketch_model_raw
    assert "science entity create concept " not in sketch_model_raw
```

Keep:

```python
    assert "```bash\nscience graph add concept" not in sketch_model_raw
```

In both tests, replace:

```python
    assert "Make sure those refs resolve through source records or lightweight term rows" in specify_model
```

with:

```python
    assert "Make sure those refs resolve through source records, lightweight term rows, or concept entity owners" in specify_model
```

- [ ] **Step 5: Run docs guard tests and verify they fail before doc edits**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_user_guide_docs.py::test_entities_chapter_documents_source_authored_concepts \
  science/tests/test_user_guide_docs.py::test_epistemic_model_documents_inquiry_ref_ownership_contract \
  science/tests/test_command_docs.py::test_sketch_model_uses_source_first_inquiry_authoring \
  science/tests/test_command_docs.py::test_specify_model_marks_direct_graph_concepts_as_non_durable \
  science/tests/test_codex_skills.py::test_concept_ownership_committed_skills_reflect_command_boundaries \
  science/tests/test_codex_skills.py::test_generated_concept_ownership_skills_reflect_command_boundaries \
  -q
```

Expected: failures point to missing new source-authored concept wording and stale mismatch wording. Do not update docs before seeing the expected failures.

---

### Task 5: Update User Guide And Command Docs

**Files:**
- Modify: `docs/user-guide/entities.md`
- Modify: `docs/user-guide/epistemic-model.md`
- Modify: `commands/sketch-model.md`
- Modify: `commands/specify-model.md`
- Modify: `commands/create-graph.md`
- Modify: `commands/health.md`

- [ ] **Step 1: Update `docs/user-guide/entities.md` table row**

Replace the `Stable project-local concept` row in `docs/user-guide/entities.md` with:

```markdown
| Stable project-local concept | Prefer the most specific registered source kind. When a local `concept:*` ref only needs a lightweight identity, use a row in `knowledge/sources/<profile>/terms.yaml`; when it needs prose, lifecycle status, source refs, aliases, same-as links, or relationships, create a Markdown owner with `science entity create concept ...`. |
```

- [ ] **Step 2: Replace the concept mismatch section**

In `docs/user-guide/entities.md`, replace the section from:

```markdown
### Current Concept Ownership Mismatch
```

through the paragraph ending immediately before:

```markdown
### Legacy Topic Triage
```

with:

````markdown
### Source-Authored Concepts

Use the most specific registered kind before creating a local concept. Domain
and core reference kinds such as `gene`, `protein`, `disease`, `pathway`,
`dataset`, `method`, `construct`, or `outcome` carry more meaning than a generic
`concept:*` owner.

`terms.yaml` is the lightweight concept tier. Use it when a term needs a stable
resolvable `concept:*` identity but does not need body prose, lifecycle work, or
structured relationships.

Use `science entity create concept "<title>"` when a project-local concept needs
a full Markdown owner:

```bash
science entity create concept "Treatment Response"
```

That command writes `entities/concepts/<slug>.md` and uses the normal entity
lifecycle: slug identity, `active` / `deprecated` status validation, source
refs, related refs, aliases, same-as links, notes, and graph materialization.

`science graph add concept` writes derived graph state in `knowledge/graph.trig`,
and `science graph build` regenerates that file from source records. Do not use
graph-added concepts as durable owners for variables, treatment/outcome refs,
unknowns, or boundary refs.

````

Do not include the trailing `### Legacy Topic Triage` marker in the replacement; it must remain as the next section heading.

- [ ] **Step 3: Update `docs/user-guide/epistemic-model.md` concept paragraph**

Replace the paragraph beginning `Use concept:* only when that ref already resolves` with:

```markdown
Use `concept:*` only when that ref already resolves through a source owner. Use
a local-profile `terms.yaml` row for lightweight terms, or
`science entity create concept "<title>"` when the project-local concept needs a
full Markdown owner under `entities/concepts/`. `science graph add concept` is
not durable inquiry authoring. Direct graph mutation writes generated graph
state that `science graph build` overwrites from source files.
```

- [ ] **Step 4: Update `commands/sketch-model.md` source entity guidance**

Replace the block beginning:

```markdown
Treatment and outcome refs may be `concept:*` only when the concept already
resolves through `terms.yaml` or another supported source owner.
```

through the paragraph ending:

```markdown
source owner is available. Unknown markers may be used in sketch as temporary
uncertainty markers; resolve or justify them before moving out of sketch.
```

with:

````markdown
Treatment and outcome refs may be `concept:*` only when the concept already
resolves through a source owner such as `terms.yaml` or `entities/concepts/*.md`.

2. **Create or update durable source entities**

Create or update source records before referencing them from the inquiry. Use
the most specific registered source kind available before creating a local
concept. Good targets include `question`, `hypothesis`, `dataset`,
`proposition`, `method`, `construct`, `outcome`, or a declared domain kind. Use
CLI helpers where available, then rebuild the graph.

For durable source records, use the generic entity lifecycle only for source
kinds the project actually supports or has registered:

```bash
science entity create <kind> "<title>" --id "<kind>:<slug>"
```

Use `science entity create concept "<title>"` when the model genuinely needs a
reusable project-local concept with a full Markdown owner. Use a lightweight
`terms.yaml` row when the term only needs a resolvable identity. Keep weak ideas
in prose when they do not need graph refs yet.

Do not invent unsupported `variable` or `unknown` entity files just to satisfy a
sketch. If no durable source owner exists yet, describe the term in the inquiry
patch prose and defer boundary roles or flow edges until a source owner is
available. Unknown markers may be used in sketch as temporary uncertainty
markers; resolve or justify them before moving out of sketch.
````

- [ ] **Step 5: Update the later `commands/sketch-model.md` refs paragraph**

Replace:

```markdown
Refs may be `concept:*` only when the concept already resolves through
`terms.yaml` or another supported source owner.
```

with:

```markdown
Refs may be `concept:*` only when the concept already resolves through
`terms.yaml`, `entities/concepts/*.md`, or another supported source owner.
```

- [ ] **Step 6: Update `commands/specify-model.md` source wording**

Replace:

```markdown
`entities/patches/<slug>.md`. Make sure those refs resolve through source
records or lightweight term rows before rebuilding the graph from source. Use a
more specific registered source kind when one exists; do not assume `concept`
entity authoring is available today.
```

with:

```markdown
`entities/patches/<slug>.md`. Make sure those refs resolve through source
records, lightweight term rows, or concept entity owners before rebuilding the
graph from source. Use a more specific registered source kind when one exists;
use `science entity create concept "<title>"` only for reusable project-local
concepts that need a full Markdown owner.
```

- [ ] **Step 7: Update `commands/create-graph.md` concept sentence**

Replace:

```markdown
prefer a local `concept:*` entity for project-scoped concepts rather than
inventing a shared canonical ID.
```

with:

```markdown
prefer the most specific registered kind. Use a lightweight `terms.yaml` row for
simple project-scoped concepts, or `science entity create concept "<title>"` when
the concept needs a full Markdown owner.
```

- [ ] **Step 8: Update `commands/health.md` semantic triage bullets**

Replace:

```markdown
- Project concept (`concept`, usually in `knowledge/sources/<profile>/terms.yaml`)
```

with:

```markdown
- Project concept (`concept`, as a lightweight `terms.yaml` row or a full `entities/concepts/*.md` owner)
```

Replace:

```markdown
- Semantic triage: create or reuse the typed entity chosen by the cookbook, add a lightweight `terms.yaml` row for stable concepts, rewrite as `meta:*`, or retire the ref.
```

with:

```markdown
- Semantic triage: create or reuse the typed entity chosen by the cookbook, add a lightweight `terms.yaml` row for stable concepts, create a full concept owner with `science entity create concept "<title>"`, rewrite as `meta:*`, or retire the ref.
```

- [ ] **Step 9: Run docs guard tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_user_guide_docs.py::test_entities_chapter_documents_source_authored_concepts \
  science/tests/test_user_guide_docs.py::test_epistemic_model_documents_inquiry_ref_ownership_contract \
  science/tests/test_command_docs.py::test_sketch_model_uses_source_first_inquiry_authoring \
  science/tests/test_command_docs.py::test_specify_model_marks_direct_graph_concepts_as_non_durable \
  -q
```

Expected: the user-guide and command-doc tests pass. Codex skill tests may still fail until generated mirrors are updated in Task 6.

---

### Task 6: Regenerate Codex Skills And Verify Mirrors

**Files:**
- Modify: generated files under `codex-skills/` changed by the generator
- Test: `science/tests/test_codex_skills.py`

- [ ] **Step 1: Regenerate Codex skills**

Run:

```bash
uv run --project science python scripts/generate_codex_skills.py
```

Expected output includes:

```text
Generated Codex skills in
```

- [ ] **Step 2: Inspect generated diff**

Run:

```bash
git diff -- codex-skills
```

Expected:

- Skill mirrors for changed source command docs are updated.
- No generated skill introduces a durable `science graph add concept` authoring example.
- Generated text matches source docs; do not hand-edit files under `codex-skills/`.

- [ ] **Step 3: Run Codex skill tests**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_codex_skills.py::test_concept_ownership_committed_skills_reflect_command_boundaries \
  science/tests/test_codex_skills.py::test_generated_concept_ownership_skills_reflect_command_boundaries \
  -q
```

Expected: both tests pass.

- [ ] **Step 4: Run focused docs and skill suite**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_user_guide_docs.py \
  science/tests/test_command_docs.py \
  science/tests/test_codex_skills.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit docs, guards, and generated skills**

Run:

```bash
git add \
  docs/user-guide/entities.md \
  docs/user-guide/epistemic-model.md \
  commands/sketch-model.md \
  commands/specify-model.md \
  commands/create-graph.md \
  commands/health.md \
  science/tests/test_user_guide_docs.py \
  science/tests/test_command_docs.py \
  science/tests/test_codex_skills.py \
  codex-skills
git commit -m "docs: document source-authored concepts"
```

---

### Task 7: Final Verification

**Files:**
- All modified files

- [ ] **Step 1: Run the full targeted verification set**

Run:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest \
  science/tests/test_entities_cli.py \
  science/tests/test_slug_strategy.py \
  science/tests/test_status_visibility.py \
  science/tests/test_load_project_sources_unified.py \
  science/tests/test_identity_declarations_loader.py \
  science/tests/test_graph_migrate_identity_audit.py \
  science/tests/test_user_guide_docs.py \
  science/tests/test_command_docs.py \
  science/tests/test_codex_skills.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 3: Review final diff**

Run:

```bash
git diff --stat
git status --short --branch
```

Expected:

- Worktree is on `source-authored-concepts-design`.
- Only intentional files are modified.
- No unrelated user edits are reverted.

- [ ] **Step 4: Confirm no uncommitted implementation changes remain**

Run:

```bash
git status --short
```

Expected: no output. If output remains, inspect each path and either add it to the appropriate earlier task commit or leave it unstaged with a note in the final handoff; do not create a catch-all commit.

---

## Self-Review Checklist

- Spec coverage:
  - `science entity create concept ...` behavior: Task 1 and Task 2.
  - Status visibility and deprecated status: Task 1 and Task 2.
  - Source loading and graph build: Task 1 and Task 2.
  - `terms.yaml`/markdown same-id collision: Task 3.
  - User-guide, command docs, and generated skills: Task 4 through Task 6.
  - `graph add concept` remains non-durable: Task 4 through Task 6.
  - Follow-ups stay out of scope: Task 5 does not add term-authoring helpers, command deprecations, or schema changes.
- Placeholder scan:
  - No unresolved implementation sections are left for the executor.
  - Every code-changing step includes the exact code or exact deletion to apply.
- Type consistency:
  - Test code uses existing names: `CliRunner`, `main`, `seed_project`, `write_markdown_entity`, `load_project_sources`, `materialize_graph`, `EntityIdentityCollisionError`, `audit_project_sources`, and `build_identity_table`.
  - Commands use the repository's verified invocation shape: `PYTEST_DEBUG_TEMPROOT=/tmp uv run --project science pytest ...`.

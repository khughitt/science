# Concept Source Ownership Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin and document the current concept/source ownership contract so inquiry and model guidance stops treating unresolved `concept:*` placeholders or direct graph mutation as durable authoring.

**Architecture:** This is a docs-and-tests-only implementation of the first slice from `docs/audits/framework-surface/concept-source-ownership-design.md`. Guard tests anchor on stable user-guide sections and command-doc sentences, source docs are updated, and generated Codex skill mirrors are regenerated from command docs.

**Tech Stack:** Markdown user guide and command docs, generated Codex skill mirrors, Python `pytest` doc guard tests, existing `scripts/generate_codex_skills.py`.

---

## Source Design

Implement the "Recommended First Slice" from `docs/audits/framework-surface/concept-source-ownership-design.md`.

Key decisions for this implementation:

- `concept` is currently a known CLI/model mismatch: the core model declares `entities/concepts`, but `science entity create concept ...` is blocked.
- `construct` is the near sibling that proves the mismatch is concept-specific, not a general policy against authored-core reference kinds.
- `science graph add concept ...` remains exploratory only. It writes generated graph state in `knowledge/graph.trig`, which `science graph build` regenerates from source.
- Inquiry `boundary_roles`, `flow_edges`, causal `treatment`/`outcome`, and `claim_refs` must reference existing source-owned refs; the compiler hard-errors unresolved ones at graph build (`PatchMembershipError`).
- Inquiry `unknowns` are different: `sci:Unknown` is an additive marker that may reference a not-yet-owned node, so an unresolved unknown does not fail the build (`inquiry validate` allows it in sketch status). Docs must not describe unknowns as must-resolve refs.
- Inquiry `assumptions` and `transformations` are local patch records whose graph nodes are minted by the compiler.
- `terms.yaml` is the currently supported lightweight concept-like path, but it is not yet routine in live project practice; docs should say this clearly.

## File Structure

- Modify `science/tests/test_user_guide_docs.py`: add helpers for anchored section slicing and normalized prose assertions, then add user-guide guard tests for inquiry ownership and the current concept mismatch.
- Modify `docs/user-guide/epistemic-model.md`: add an anchored ownership contract section for inquiry refs and inquiry-local nodes.
- Modify `docs/user-guide/entities.md`: tighten Reference Semantics around concept-like refs, `terms.yaml`, the blocked `concept` entity writer, and the `construct` asymmetry.
- Modify `science/tests/test_command_docs.py`: extend active command-doc guards for `sketch-model`, `specify-model`, and `plan-pipeline`.
- Modify `science/tests/test_codex_skills.py`: add generated and committed skill guards so Codex mirrors cannot drift from source command docs.
- Modify `commands/sketch-model.md`: route concept-like refs to existing source refs, registered source kinds, `terms.yaml`, or prose deferral; explicitly rule out `science entity create concept ...` as a current workflow.
- Modify `commands/specify-model.md`: clarify that durable variables must resolve through source refs or term rows, and direct graph concept writes are inspection-only.
- Modify `commands/plan-pipeline.md`: replace the `validated_by: "concept:<check>"` placeholder with an existing validation-ref placeholder and prose that says not to invent validation concepts.
- Modify `codex-skills/science-sketch-model/SKILL.md`, `codex-skills/science-specify-model/SKILL.md`, and `codex-skills/science-plan-pipeline/SKILL.md`: regenerate these through `scripts/generate_codex_skills.py`.

## Task 1: Add User-Guide Guard Tests

**Files:**
- Modify: `science/tests/test_user_guide_docs.py`

- [ ] **Step 1: Add section and normalization helpers**

In `science/tests/test_user_guide_docs.py`, add these helpers immediately after `_read`:

```python
def _slice_between(text: str, start: str, end: str) -> str:
    if start not in text:
        raise AssertionError(f"missing start marker: {start}")
    if end not in text:
        raise AssertionError(f"missing end marker: {end}")
    return text.split(start, 1)[1].split(end, 1)[0]


def _norm(text: str) -> str:
    return " ".join(text.split())
```

Keep `_read` raw. Existing tests rely on the actual file text.

- [ ] **Step 2: Add the failing ownership tests**

Append these tests near the existing entity and epistemic user-guide tests, after `test_entities_chapter_documents_reference_semantics_and_topic_deprecation`:

```python
def test_epistemic_model_documents_inquiry_ref_ownership_contract() -> None:
    text = _read(GUIDE_ROOT / "epistemic-model.md")
    section = _slice_between(
        text,
        "### Inquiry Ref Ownership Contract",
        "### Causal Inquiry Profiles",
    )
    normalized = _norm(section)

    assert "Inquiry fields use two ownership modes" in normalized
    assert "| Boundary refs | Existing source refs selected by the inquiry" in section
    assert "| Flow-edge endpoints | Existing source refs connected by the inquiry" in section
    assert "| Unknowns | A `sci:Unknown` marker on a referenced node" in section
    assert "| Assumptions | Inquiry-local records in `inquiry.assumptions`" in section
    assert "| Transformations | Inquiry-local records in `inquiry.transformations`" in section
    assert "unresolved endpoint refs are graph-build errors" in normalized
    assert "an unresolved unknown does not fail the build" in normalized
    assert "`science graph add concept` is not durable inquiry authoring" in normalized


def test_entities_chapter_documents_current_concept_ownership_mismatch() -> None:
    text = _read(GUIDE_ROOT / "entities.md")
    section = _slice_between(
        text,
        "### Current Concept Ownership Mismatch",
        "### Legacy Topic Triage",
    )
    normalized = _norm(section)

    assert "The core model declares `concept` as an authored reference kind" in normalized
    assert "`science entity create concept` is not a supported routine today" in normalized
    assert "`science graph add concept` writes derived graph state" in normalized
    assert "`construct` is source-authored through the normal entity lifecycle" in normalized
    assert "`terms.yaml` is the supported lightweight concept-like source path" in normalized
```

- [ ] **Step 3: Run the tests and verify they fail**

Run:

```bash
uv run pytest \
  science/tests/test_user_guide_docs.py::test_epistemic_model_documents_inquiry_ref_ownership_contract \
  science/tests/test_user_guide_docs.py::test_entities_chapter_documents_current_concept_ownership_mismatch \
  -q
```

Expected: FAIL. One failure should report `missing start marker: ### Inquiry Ref Ownership Contract`; the other should report `missing start marker: ### Current Concept Ownership Mismatch`.

- [ ] **Step 4: Commit the failing tests**

```bash
git add science/tests/test_user_guide_docs.py
git commit -m "test: pin concept ownership user guide contract"
```

## Task 2: Document the User-Guide Ownership Contract

**Files:**
- Modify: `docs/user-guide/epistemic-model.md`
- Modify: `docs/user-guide/entities.md`
- Test: `science/tests/test_user_guide_docs.py`

- [ ] **Step 1: Add the inquiry ownership section**

In `docs/user-guide/epistemic-model.md`, insert this section immediately after the paragraph ending with `assumption and transformation nodes are minted by the compiler.` and before `### Causal Inquiry Profiles`:

```markdown
### Inquiry Ref Ownership Contract

Inquiry fields use two ownership modes: existing source refs for reusable things
and compiler-minted local nodes for inquiry-local structure.

| Item | Durable owner |
|---|---|
| Boundary refs | Existing source refs selected by the inquiry and marked as `BoundaryIn` or `BoundaryOut`. |
| Flow-edge endpoints | Existing source refs connected by the inquiry. Edges do not create endpoint owners. |
| Flow-edge claims | Existing `proposition:*` refs when an edge has an explicit truth-apt assertion. |
| Causal treatment/outcome | Existing source refs, usually domain kinds, project concepts that already resolve, or lightweight local terms. |
| Unknowns | A `sci:Unknown` marker on a referenced node. The node may be an existing source ref or one not yet owned; the marker flags an open gap and is not a standalone owner. |
| Assumptions | Inquiry-local records in `inquiry.assumptions`; graph build mints local assumption nodes. |
| Transformations | Inquiry-local records in `inquiry.transformations`; graph build mints local transformation nodes. |

Boundary refs, flow-edge endpoints, causal treatment/outcome refs, and
flow-edge claim refs must already resolve through source records or lightweight
term rows before the inquiry can be materialized; unresolved endpoint refs are
graph-build errors.

Unknown refs are different. `sci:Unknown` is an additive marker that may
reference a not-yet-owned node, so an unresolved unknown does not fail the
build; `science inquiry validate` allows unresolved unknown nodes in sketch
status. Use the marker to flag something you do not yet have a source owner for,
not as a reason to invent one.

Use `concept:*` only when that ref already resolves through a source such as a
local-profile `terms.yaml` row or a future supported concept entity. The
current CLI does not support routine `science entity create concept ...`
authoring, and `science graph add concept` is not durable inquiry authoring.
Direct graph mutation writes generated graph state that `science graph build`
overwrites from source files.
```

- [ ] **Step 2: Tighten the Reference Semantics concept row**

In `docs/user-guide/entities.md`, replace this table row:

```markdown
| Stable project-local concept | `concept`, often as a lightweight row in `knowledge/sources/<profile>/terms.yaml`. |
```

with:

```markdown
| Stable project-local concept | Prefer the most specific registered source kind. When a local `concept:*` ref is needed, use a lightweight row in `knowledge/sources/<profile>/terms.yaml`; full `entities/concepts` authoring is model-declared but not routine CLI-supported yet. |
```

- [ ] **Step 3: Add headings around lightweight terms and legacy topic triage**

In `docs/user-guide/entities.md`, insert this heading immediately before the paragraph starting with `` `terms.yaml` is for lightweight semantic rows``:

```markdown
### Lightweight Semantic Terms

```

Then insert this heading immediately before the paragraph starting with `` `topic` remains registered for legacy projects``:

```markdown
### Legacy Topic Triage

```

- [ ] **Step 4: Add the concept mismatch section**

In `docs/user-guide/entities.md`, insert this section after the paragraph ending with `lifecycle work.` and before `### Legacy Topic Triage`:

```markdown
### Current Concept Ownership Mismatch

The core model declares `concept` as an authored reference kind with the home
`entities/concepts`, but `science entity create concept` is not a supported
routine today. The entity writer currently blocks that command and points to
graph mutation instead.

That graph-mutating path is not a durable replacement. `science graph add
concept` writes derived graph state in `knowledge/graph.trig`, and `science
graph build` regenerates that file from source records.

The mismatch is concept-specific. `construct` is source-authored through the
normal entity lifecycle even though it is also an authored-core reference kind.
Until `concept` follows the same supported source path, `terms.yaml` is the
supported lightweight concept-like source path. Use a more specific registered
kind when one exists, keep weak ideas in prose when they do not need graph refs,
and avoid creating unresolved `concept:*` placeholders to silence validation.
```

- [ ] **Step 5: Run the user-guide tests and verify they pass**

Run:

```bash
uv run pytest \
  science/tests/test_user_guide_docs.py::test_epistemic_model_documents_inquiry_ref_ownership_contract \
  science/tests/test_user_guide_docs.py::test_entities_chapter_documents_current_concept_ownership_mismatch \
  science/tests/test_user_guide_docs.py::test_entities_chapter_documents_reference_semantics_and_topic_deprecation \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit the user-guide docs**

```bash
git add docs/user-guide/epistemic-model.md docs/user-guide/entities.md
git commit -m "docs: document concept source ownership contract"
```

## Task 3: Add Command and Skill Guard Tests

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Modify: `science/tests/test_codex_skills.py`

- [ ] **Step 1: Extend the sketch-model source-doc guard**

In `science/tests/test_command_docs.py`, update `test_sketch_model_uses_source_first_inquiry_authoring` so the body is:

```python
def test_sketch_model_uses_source_first_inquiry_authoring() -> None:
    text = _read("commands/sketch-model.md")
    normalized = _norm(text)

    assert "Do not use `science graph add concept` as the durable authoring path." in normalized
    assert "Direct graph mutation writes to `knowledge/graph.trig`" in normalized
    assert "regenerated by `science graph build` from source files" in normalized
    assert "Do not use `science entity create concept` in this workflow" in normalized
    assert "Use a registered source kind, a lightweight `terms.yaml` row, or prose deferral" in normalized
    assert (
        "If no supported durable source kind exists yet, describe the term in the inquiry patch prose"
        in normalized
    )
    assert "boundary roles, flow edges, or unknown markers until a source owner is available" in normalized
    assert "Use the patch source for inquiry-local assumptions and transformations" in normalized
    assert "the inquiry compiler mints those local nodes from the authored patch" in normalized
    assert "```bash\nscience graph add concept" not in text
```

- [ ] **Step 2: Extend the specify-model source-doc guard**

In `science/tests/test_command_docs.py`, update `test_specify_model_marks_direct_graph_concepts_as_non_durable` so the body is:

```python
def test_specify_model_marks_direct_graph_concepts_as_non_durable() -> None:
    text = _read("commands/specify-model.md")
    normalized = _norm(text)

    assert (
        "For inquiry-patch projects, record durable variable refs in `entities/patches/<slug>.md`."
        in normalized
    )
    assert "Make sure those refs resolve through source records or lightweight term rows" in normalized
    assert "Direct `science graph add concept` writes are exploratory and non-durable." in normalized
    assert "They write to `knowledge/graph.trig`, which is regenerated from source files." in normalized
    assert "Do not treat graph-added concepts as owners for variables, treatment/outcome refs, or unknowns." in normalized
```

- [ ] **Step 3: Add the plan-pipeline validation-ref guard**

In `science/tests/test_command_docs.py`, append this test immediately after `test_plan_pipeline_documents_mixed_access_public_slice_gate`:

```python
def test_plan_pipeline_does_not_invent_validation_concepts() -> None:
    text = _read("commands/plan-pipeline.md")
    normalized = _norm(text)

    assert "Transformation `validated_by` refs should point to existing validation artifacts" in normalized
    assert "Leave `validated_by` blank or omit it when no validation artifact exists yet." in normalized
    assert "Do not use `concept:<check>` as a placeholder for a validation record that does not exist." in normalized
    assert 'validated_by: "<existing-validation-ref>"' in text
    assert 'validated_by: "concept:<check>"' not in text
```

- [ ] **Step 4: Add committed Codex skill guards**

In `science/tests/test_codex_skills.py`, append this test immediately after `test_task_inquiry_committed_skills_reflect_command_boundaries`:

```python
def test_concept_ownership_committed_skills_reflect_command_boundaries() -> None:
    sketch_model_raw = _read_skill("science-sketch-model")
    sketch_model = _norm(sketch_model_raw)
    specify_model = _norm(_read_skill("science-specify-model"))
    plan_pipeline = _norm(_read_skill("science-plan-pipeline"))

    assert "Do not use `science entity create concept` in this workflow" in sketch_model
    assert "Use a registered source kind, a lightweight `terms.yaml` row, or prose deferral" in sketch_model
    assert "```bash\nscience graph add concept" not in sketch_model_raw
    assert "Make sure those refs resolve through source records or lightweight term rows" in specify_model
    assert "Do not treat graph-added concepts as owners for variables, treatment/outcome refs, or unknowns." in specify_model
    assert "Transformation `validated_by` refs should point to existing validation artifacts" in plan_pipeline
    assert "Do not use `concept:<check>` as a placeholder for a validation record that does not exist." in plan_pipeline
```

- [ ] **Step 5: Add generated Codex skill guards**

In `science/tests/test_codex_skills.py`, append this test immediately after `test_concept_ownership_committed_skills_reflect_command_boundaries`:

```python
def test_generated_concept_ownership_skills_reflect_command_boundaries(
    tmp_path: Path,
) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    sketch_model_raw = generated["science-sketch-model"].read_text(encoding="utf-8")
    sketch_model = _norm(sketch_model_raw)
    specify_model = _norm(generated["science-specify-model"].read_text(encoding="utf-8"))
    plan_pipeline = _norm(generated["science-plan-pipeline"].read_text(encoding="utf-8"))

    assert "Do not use `science entity create concept` in this workflow" in sketch_model
    assert "Use a registered source kind, a lightweight `terms.yaml` row, or prose deferral" in sketch_model
    assert "```bash\nscience graph add concept" not in sketch_model_raw
    assert "Make sure those refs resolve through source records or lightweight term rows" in specify_model
    assert "Do not treat graph-added concepts as owners for variables, treatment/outcome refs, or unknowns." in specify_model
    assert "Transformation `validated_by` refs should point to existing validation artifacts" in plan_pipeline
    assert "Do not use `concept:<check>` as a placeholder for a validation record that does not exist." in plan_pipeline
```

- [ ] **Step 6: Run the tests and verify they fail**

Run:

```bash
uv run pytest \
  science/tests/test_command_docs.py::test_sketch_model_uses_source_first_inquiry_authoring \
  science/tests/test_command_docs.py::test_specify_model_marks_direct_graph_concepts_as_non_durable \
  science/tests/test_command_docs.py::test_plan_pipeline_does_not_invent_validation_concepts \
  science/tests/test_codex_skills.py::test_concept_ownership_committed_skills_reflect_command_boundaries \
  science/tests/test_codex_skills.py::test_generated_concept_ownership_skills_reflect_command_boundaries \
  -q
```

Expected: FAIL. The failures should be missing the new command-doc phrases and still finding `validated_by: "concept:<check>"`.

- [ ] **Step 7: Commit the failing tests**

```bash
git add science/tests/test_command_docs.py science/tests/test_codex_skills.py
git commit -m "test: pin concept ownership command guidance"
```

## Task 4: Update Source Command Docs

**Files:**
- Modify: `commands/sketch-model.md`
- Modify: `commands/specify-model.md`
- Modify: `commands/plan-pipeline.md`
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Tighten sketch-model source authoring guidance**

In `commands/sketch-model.md`, replace the Step 2 prose from:

````markdown
Create or update source records before referencing them from the inquiry. Prefer
normal entity files under `entities/` when the variable, question, hypothesis,
dataset, or proposition is a durable project concept. Use CLI helpers where
available, then rebuild the graph.

For standalone durable concept-like records, use the generic entity lifecycle
only for source kinds the project actually supports or has registered:

```bash
science entity create <kind> "<title>" --id "<kind>:<slug>"
```

Do not invent unsupported `concept`, `variable`, or `unknown` entity files just
to satisfy a sketch. If no supported durable source kind exists yet, describe
the term in the inquiry patch prose and defer boundary roles, flow edges, or
unknown markers until a source owner is available.
````

to:

````markdown
Create or update source records before referencing them from the inquiry. Use
the most specific registered source kind available, such as `question`,
`hypothesis`, `dataset`, `proposition`, `method`, `construct`, or a declared
domain kind. Use CLI helpers where available, then rebuild the graph.

For durable source records, use the generic entity lifecycle only for source
kinds the project actually supports or has registered:

```bash
science entity create <kind> "<title>" --id "<kind>:<slug>"
```

`concept` is currently a known CLI/model mismatch: the model declares
`entities/concepts`, but the entity writer does not support routine
`science entity create concept` authoring. Do not use `science entity create
concept` in this workflow. Use a registered source kind, a lightweight
`terms.yaml` row, or prose deferral instead.

Do not invent unsupported `concept`, `variable`, or `unknown` entity files just
to satisfy a sketch. If no supported durable source kind exists yet, describe
the term in the inquiry patch prose and defer boundary roles, flow edges, or
unknown markers until a source owner is available.
````

- [ ] **Step 2: Tighten specify-model durable variable guidance**

In `commands/specify-model.md`, replace this paragraph:

```markdown
For inquiry-patch projects, record durable variable refs in
`entities/patches/<slug>.md`. Add or update source entity files under
`entities/` for variables that are durable project concepts, then rebuild the
graph from source.
```

with:

```markdown
For inquiry-patch projects, record durable variable refs in
`entities/patches/<slug>.md`. Make sure those refs resolve through source
records or lightweight term rows before rebuilding the graph from source. Use a
more specific registered source kind when one exists; do not assume `concept`
entity authoring is available today.
```

- [ ] **Step 3: Tighten specify-model direct graph mutation warning**

In `commands/specify-model.md`, replace this paragraph:

```markdown
Direct `science graph add concept` writes are exploratory and non-durable. They
write to `knowledge/graph.trig`, which is regenerated from source files. Use
them only for temporary graph inspection, and repeat the durable definition in a
source file before treating the model as specified:
```

with:

```markdown
Direct `science graph add concept` writes are exploratory and non-durable. They
write to `knowledge/graph.trig`, which is regenerated from source files. Use
them only for temporary graph inspection. Do not treat graph-added concepts as
owners for variables, treatment/outcome refs, or unknowns.
```

Keep the existing `science graph add concept "<name>" --type <CURIE> --definition "<definition>"` code block below this paragraph. It remains explicitly inspection-only.

- [ ] **Step 4: Tighten plan-pipeline transformation validation refs**

In `commands/plan-pipeline.md`, replace this paragraph:

```markdown
For each identified step, edit the source file at `entities/patches/<slug>.md`.
Add transformation records under `inquiry.transformations` and connect them with
`flow_edges`. Then run `science graph build` and re-run `science inquiry
validate`.
```

with:

```markdown
For each identified step, edit the source file at `entities/patches/<slug>.md`.
Add transformation records under `inquiry.transformations` and connect them with
`flow_edges`. Transformation `validated_by` refs should point to existing
validation artifacts, such as a proposition, dataset, workflow-run, method, or
documented check. Leave `validated_by` blank or omit it when no validation
artifact exists yet. Do not use `concept:<check>` as a placeholder for a
validation record that does not exist. Then run `science graph build` and re-run
`science inquiry validate`.
```

Then, in the YAML example in the same section, replace:

```yaml
      validated_by: "concept:<check>"
```

with:

```yaml
      validated_by: "<existing-validation-ref>"
```

- [ ] **Step 5: Run source command-doc tests and verify they pass**

Run:

```bash
uv run pytest \
  science/tests/test_command_docs.py::test_sketch_model_uses_source_first_inquiry_authoring \
  science/tests/test_command_docs.py::test_specify_model_marks_direct_graph_concepts_as_non_durable \
  science/tests/test_command_docs.py::test_plan_pipeline_does_not_invent_validation_concepts \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit the source command docs**

```bash
git add commands/sketch-model.md commands/specify-model.md commands/plan-pipeline.md
git commit -m "docs: tighten concept ownership command guidance"
```

## Task 5: Regenerate Codex Skills and Verify

**Files:**
- Modify: `codex-skills/science-sketch-model/SKILL.md`
- Modify: `codex-skills/science-specify-model/SKILL.md`
- Modify: `codex-skills/science-plan-pipeline/SKILL.md`
- Test: `science/tests/test_codex_skills.py`

- [ ] **Step 1: Regenerate Codex skills**

Run:

```bash
uv run python scripts/generate_codex_skills.py
```

Expected output includes:

```text
Generated Codex skills in
```

- [ ] **Step 2: Inspect the generated diff**

Run:

```bash
git diff -- codex-skills/science-sketch-model/SKILL.md codex-skills/science-specify-model/SKILL.md codex-skills/science-plan-pipeline/SKILL.md
```

Expected: the diff reflects only the command-doc wording changes from Task 4 after the generator's standard command-to-skill transformation.

- [ ] **Step 3: Run focused Codex skill tests**

Run:

```bash
uv run pytest \
  science/tests/test_codex_skills.py::test_concept_ownership_committed_skills_reflect_command_boundaries \
  science/tests/test_codex_skills.py::test_generated_concept_ownership_skills_reflect_command_boundaries \
  science/tests/test_codex_skills.py::test_task_inquiry_committed_skills_reflect_command_boundaries \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run the full focused doc suite**

Run:

```bash
uv run pytest \
  science/tests/test_user_guide_docs.py \
  science/tests/test_command_docs.py \
  science/tests/test_codex_skills.py \
  -q
```

Expected: PASS.

- [ ] **Step 5: Check formatting and workspace status**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` exits 0. `git status --short` shows only the intended modified files until the commit is made.

- [ ] **Step 6: Commit the regenerated skills and test updates**

```bash
git add codex-skills/science-sketch-model/SKILL.md codex-skills/science-specify-model/SKILL.md codex-skills/science-plan-pipeline/SKILL.md science/tests/test_codex_skills.py
git commit -m "docs: regenerate concept ownership skills"
```

## Task 6: Final Review

**Files:**
- Review: all files changed by Tasks 1-5

- [ ] **Step 1: Review the cumulative diff**

Run:

```bash
git diff --stat HEAD~5..HEAD
git diff HEAD~5..HEAD -- docs/user-guide/epistemic-model.md docs/user-guide/entities.md commands/sketch-model.md commands/specify-model.md commands/plan-pipeline.md
```

Expected: the cumulative diff is docs-and-tests-only. It should not change Python runtime behavior or generated graph behavior.

- [ ] **Step 2: Verify the plan's non-goals**

Check the diff for these strings:

```bash
git diff HEAD~5..HEAD -- science/src/science_tool/entities.py science/model/src/science_model/profiles/core.py science/src/science_tool/graph
```

Expected: no output. This first slice must not enable `science entity create concept ...`, change the core profile, or change graph compilation.

- [ ] **Step 3: Run final focused verification**

Run:

```bash
uv run pytest \
  science/tests/test_user_guide_docs.py \
  science/tests/test_command_docs.py \
  science/tests/test_codex_skills.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Record final status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch, or only intentionally uncommitted files explicitly called out in the handoff.

## Self-Review Notes

- Spec coverage: Task 2 covers user-guide ownership and current mismatch; Task 4 covers active command docs; Task 5 covers generated Codex mirrors; Task 6 enforces the docs-only non-goal.
- Guard style: User-guide tests slice by stable headings before asserting prose, matching the existing anchored-doc-test style and avoiding broad file scans.
- Behavior scope: No runtime code changes are planned. Enabling source-authored concepts, adding a `terms.yaml` helper, and relabeling `graph add concept` remain separate later slices.

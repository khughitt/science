# Dataset Surface Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align Science dataset/data command guidance so agents use singular `science dataset` for durable dataset entities, plural `science datasets` for discovery/runtime datapackage tooling, and `science dataset verify-access` for the current access gate.

**Architecture:** This is a docs-and-tests slice, not a CLI behavior change. Add guard tests around the stale guidance first, update source command/skill docs, regenerate the generated command-skill mirrors in `codex-skills/`, then run focused documentation and generated-skill tests.

**Tech Stack:** Markdown command docs and skills, generated Codex skill mirrors, Python `pytest`, `scripts/generate_codex_skills.py`, existing `science_tool.codex_skills` generator.

---

## Files

- Modify: `science/tests/test_command_docs.py`
  - Add source-doc guard tests for `commands/find-datasets.md`, `commands/plan-pipeline.md`, and `commands/review-pipeline.md`.
- Modify: `science/tests/test_codex_skills.py`
  - Add generated-skill guard tests for `science-find-datasets`, `science-plan-pipeline`, and companion data skills as generator output.
- Modify: `commands/find-datasets.md`
  - Recast as discovery support that routes durable records through `science dataset add`, `science dataset verify-access`, `science dataset link`, and `science dataset prioritize`.
- Modify: `commands/plan-pipeline.md`
  - Replace stale `science dataset verify` wording with the current `science dataset verify-access` gate.
- Modify: `commands/review-pipeline.md`
  - Name the same `science dataset verify-access` gate during data-availability review.
- Modify: `skills/data/SKILL.md`
  - Route routine new data-source records through the singular dataset entity lifecycle.
- Modify: `skills/data/frictionless.md`
  - Clarify that Frictionless Data Packages are runtime/package descriptors, not the local dataset entity lifecycle.
- Modify as needed: `docs/user-guide/cli-and-workflows.md`, `docs/user-guide/entities.md`, `docs/user-guide/cross-project-work.md`
  - Only tighten wording if the tests or source docs expose a concrete ambiguity.
- Regenerate: `codex-skills/science-find-datasets/SKILL.md`
- Regenerate: `codex-skills/science-plan-pipeline/SKILL.md`
- Regenerate: any other generated skill mirror changed by `scripts/generate_codex_skills.py`

Do not change CLI command behavior in this slice. Do not hand-edit generated `codex-skills/` files except by running the generator. The current generator emits command skills plus the `research-methodology` and `scientific-writing` companion skills; it does not emit `skills/data/SKILL.md` as a standalone Codex skill.

---

### Task 1: Source Command-Doc Guard Tests

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Add failing tests for the source command docs**

Append these tests near the existing command-doc tests for `catalog-datasets`, `plan-pipeline`, and `review-pipeline` in `science/tests/test_command_docs.py`:

```python
def test_find_datasets_setup_is_layout_v3_aware() -> None:
    text = _read("commands/find-datasets.md")

    assert "entities/questions/" in text
    assert "entities/hypotheses/" in text
    assert "entities/datasets/" in text
    assert "legacy specs/research-question.md only if it exists" in text
    assert "legacy specs/scope-boundaries.md only if it exists" in text
    assert "- `specs/research-question.md`" not in text
    assert "- `specs/scope-boundaries.md`" not in text


def test_find_datasets_routes_durable_records_through_dataset_lifecycle() -> None:
    text = _read("commands/find-datasets.md")

    assert "science datasets search" in text
    assert "science datasets metadata <source>:<id> --format json" in text
    assert "science datasets files <source>:<id> --format json" in text
    assert "science dataset add <slug>" in text
    assert "--level <public|registration|controlled|commercial|mixed>" in text
    add_example = text.split("science dataset add <slug>", 1)[1].split(
        "science dataset verify-access <slug>",
        1,
    )[0]
    assert "--license" not in add_example
    assert "science dataset verify-access <slug>" in text
    assert "--method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed>" in text
    assert "--source-url \"<landing-page-or-download-url>\"" in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "science dataset prioritize" in text
    assert "Direct template authoring is a fallback" in text
    assert "For each `Use now` or `Evaluate next` dataset, create a dataset note" not in text
    assert "Update `science.yaml` data_sources section with new entries" not in text
    assert "--level <public|controlled|mixed>" not in text
    assert "--method <landing-confirmed|downloaded|manual-review>" not in text
    assert "--source \"<landing-page-or-download-url>\"" not in text
    assert "--date <YYYY-MM-DD>" not in text


def test_plan_pipeline_uses_current_dataset_verify_access_gate() -> None:
    text = _read("commands/plan-pipeline.md")

    assert "science dataset verify-access <slug>" in text
    assert "current `science dataset verify-access`" in text
    assert "future `science dataset verify`" not in text
    assert "(manual or future `science dataset verify`)" not in text


def test_review_pipeline_uses_current_dataset_verify_access_gate() -> None:
    text = _read("commands/review-pipeline.md")

    assert "science dataset verify-access <slug>" in text
    assert "Access verification should be current" in text
    assert "science dataset verify`" not in text
```

- [ ] **Step 2: Run the new tests and confirm they fail**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_command_docs.py::test_find_datasets_setup_is_layout_v3_aware \
  science/tests/test_command_docs.py::test_find_datasets_routes_durable_records_through_dataset_lifecycle \
  science/tests/test_command_docs.py::test_plan_pipeline_uses_current_dataset_verify_access_gate \
  science/tests/test_command_docs.py::test_review_pipeline_uses_current_dataset_verify_access_gate \
  -q
```

Expected: FAIL. The current `find-datasets` doc still lists legacy `specs/` paths directly, still presents manual `entities/datasets/<slug>.md` authoring as routine, and `plan-pipeline` still mentions a future `science dataset verify`.

- [ ] **Step 3: Commit the failing tests**

```bash
rtk git add science/tests/test_command_docs.py
rtk git commit -m "test: guard dataset command guidance"
```

Expected: commit succeeds with only the source command-doc tests staged.

---

### Task 2: Source Command Guidance

**Files:**
- Modify: `commands/find-datasets.md`
- Modify: `commands/plan-pipeline.md`
- Modify: `commands/review-pipeline.md`
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Update `commands/find-datasets.md` setup**

In `commands/find-datasets.md`, replace the opening paragraph and `## Setup` list with this text:

````markdown
# Find Datasets

Find candidate external datasets for `$ARGUMENTS`.
If no argument is provided, derive candidate search terms from active questions,
hypotheses, inquiry variables, and legacy specs only when those files exist;
then ask the user to confirm the focus.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `${CLAUDE_PLUGIN_ROOT}/skills/data/SKILL.md` for data management conventions.
2. If present, read `${CLAUDE_PLUGIN_ROOT}/skills/data/frictionless.md` for runtime Data Package guidance.
3. Read project context:
   - `entities/questions/`
   - `entities/hypotheses/`
   - `entities/datasets/` to avoid duplicating known dataset records
   - legacy specs/research-question.md only if it exists
   - legacy specs/scope-boundaries.md only if it exists
4. If an inquiry exists, check inquiry variables to understand what data the project needs:
   ```bash
   science inquiry list --format json
   ```
````

Do not keep `.ai/templates/dataset.md` in the required setup list. Template authoring is no longer the routine path for durable dataset records.

- [ ] **Step 2: Replace `find-datasets` Step 5 with lifecycle routing**

In `commands/find-datasets.md`, replace the entire `### Step 5: Document selected datasets` section with:

````markdown
### Step 5: Record selected datasets

For each `Use now` or `Evaluate next` dataset, create or update the durable
project record through the singular dataset entity lifecycle. Discovery uses
plural `science datasets ...`; durable project records use singular
`science dataset ...`.

Use the CLI path when the record can be expressed by current fields:

```bash
science dataset add <slug> \
  --title "<dataset title>" \
  --source-url "<landing-page-or-accession-url>" \
  --level <public|registration|controlled|commercial|mixed> \
  --tier <use-now|evaluate-next|track>
```

Then verify access evidence before handing the dataset to pipeline planning:

```bash
science dataset verify-access <slug> \
  --license <spdx-or-unknown> \
  --method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed> \
  --source-url "<landing-page-or-download-url>"
```

When the dataset supports a question or hypothesis, add typed links with the
helper instead of editing backlinks by hand:

```bash
science dataset link <dataset-ref> <question-or-hypothesis-ref>
```

If multiple dataset records need ranking after discovery, run:

```bash
science dataset prioritize --format json
```

Direct template authoring is a fallback for unsupported fields,
project-specific review templates, or deliberate backfills. When using that
fallback, read `.ai/templates/dataset.md` first; if it is not present, read
`${CLAUDE_PLUGIN_ROOT}/templates/dataset.md`. Fill unknown fields as
`[UNVERIFIED]`, then immediately run `science dataset verify-access <slug>` or
record why verification is blocked.

When mapping an adapter result's `access` tier to the entity `access.level`,
apply: `public -> public`, `restricted -> controlled`, and
`controlled -> controlled`. Use `mixed` only when sibling artefacts differ in
access level.
````

- [ ] **Step 3: Replace `find-datasets` Step 7 with durable-output wording**

In `commands/find-datasets.md`, replace the whole `### Step 7: Update project files` section with:

````markdown
### Step 7: Write durable outputs

1. Write machine-readable search results to `entities/searches/YYYY-MM-DD-datasets-<slug>.json`.
2. Ensure selected durable records were created or updated through
   `science dataset add <slug>` and `science dataset verify-access <slug>`.
3. If appropriate, suggest runtime acquisition commands:
   ```bash
   science datasets download <source>:<id> --dest data/raw/
   ```
4. Offer to create follow-up tasks via `science tasks add`:
   - Download and inspect `Use now` datasets
   - Create or update `datapackage.json` for downloaded runtime files
   - Map variables for pipeline planning
````

- [ ] **Step 4: Replace the `find-datasets` emission rules intro**

In `commands/find-datasets.md`, replace the first line under `### Emission rules (rev 2.1)` and keep the existing detailed bullets after it:

```markdown
When emitting or backfilling `entities/datasets/<slug>.md` through the CLI or the
explicit template fallback:
```

Then delete the stale bullet that says:

```markdown
- Always set `origin: "external"`.
```

Replace it with:

```markdown
- External discovery records should resolve to `origin: "external"`.
```

- [ ] **Step 5: Update `commands/plan-pipeline.md` access gate**

In `commands/plan-pipeline.md`, inside `### Step 2b: Data-access gate (both modes)`, replace:

```markdown
- **Branch A** — verifiable under current credentials → run verification
  (manual or future `science dataset verify`), then re-run this step.
```

with:

```markdown
- **Branch A** — verifiable under current credentials → run the current
  `science dataset verify-access <slug>` command with enum-safe evidence,
  then re-run this step.
```

- [ ] **Step 6: Update `commands/review-pipeline.md` data-availability review**

In `commands/review-pipeline.md`, inside `#### Dimension 3: Data Availability`, add this paragraph after the `derived` gate bullets and before `Runtime stageability`:

```markdown
- Access verification should be current: if a public, registration-only, or
  credentialed external dataset is obtainable but has stale or missing evidence,
  require `science dataset verify-access <slug>` before downstream stages consume
  it.
```

- [ ] **Step 7: Run the focused command-doc tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_command_docs.py::test_find_datasets_setup_is_layout_v3_aware \
  science/tests/test_command_docs.py::test_find_datasets_routes_durable_records_through_dataset_lifecycle \
  science/tests/test_command_docs.py::test_plan_pipeline_uses_current_dataset_verify_access_gate \
  science/tests/test_command_docs.py::test_review_pipeline_uses_current_dataset_verify_access_gate \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit source command guidance**

```bash
rtk git add commands/find-datasets.md commands/plan-pipeline.md commands/review-pipeline.md science/tests/test_command_docs.py
rtk git commit -m "docs: align dataset command guidance"
```

Expected: commit succeeds and keeps CLI code untouched.

---

### Task 3: Data Skill Guard Tests

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Add failing tests for source data skills**

Append these tests to `science/tests/test_command_docs.py` near other docs/skill guidance tests:

```python
def test_data_skill_routes_new_sources_through_dataset_entity_lifecycle() -> None:
    text = _read("skills/data/SKILL.md")

    assert "science dataset add <slug>" in text
    assert "--level <public|registration|controlled|commercial|mixed>" in text
    add_example = text.split("science dataset add <slug>", 1)[1].split(
        "science dataset verify-access <slug>",
        1,
    )[0]
    assert "--license" not in add_example
    assert "science dataset verify-access <slug>" in text
    assert "--method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed>" in text
    assert "--source-url \"<landing-page-or-download-url>\"" in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "Manual template authoring is a fallback" in text
    assert "runtime datapackage descriptors" in text
    assert "--level <public|controlled|mixed>" not in text
    assert "--method <landing-confirmed|downloaded|manual-review>" not in text
    assert "--source \"<landing-page-or-download-url>\"" not in text
    assert "--date <YYYY-MM-DD>" not in text


def test_frictionless_skill_distinguishes_datapackages_from_dataset_entities() -> None:
    text = _read("skills/data/frictionless.md")

    assert "runtime/package descriptor" in text
    assert "not the local dataset entity lifecycle" in text
    assert "Use `science dataset add <slug>`" in text
    assert "Use `science datasets validate --path data/raw/`" in text
```

- [ ] **Step 2: Run the new data-skill tests and confirm they fail**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_command_docs.py::test_data_skill_routes_new_sources_through_dataset_entity_lifecycle \
  science/tests/test_command_docs.py::test_frictionless_skill_distinguishes_datapackages_from_dataset_entities \
  -q
```

Expected: FAIL because the current data skill still says to document new sources with the template as the routine first step, and the Frictionless skill does not clearly state the lifecycle boundary.

- [ ] **Step 3: Commit the failing skill tests**

```bash
rtk git add science/tests/test_command_docs.py
rtk git commit -m "test: guard data skill dataset boundaries"
```

Expected: commit succeeds with only the skill guard tests staged.

---

### Task 4: Data Skill Guidance

**Files:**
- Modify: `skills/data/SKILL.md`
- Modify: `skills/data/frictionless.md`
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Replace `skills/data/SKILL.md` new-source workflow**

In `skills/data/SKILL.md`, replace the `## When Adding a New Data Source` section with:

````markdown
## When Adding a New Data Source

1. Create or update the durable dataset entity through the singular lifecycle:
   ```bash
   science dataset add <slug> \
     --title "<dataset title>" \
     --source-url "<landing-page-or-accession-url>" \
     --level <public|registration|controlled|commercial|mixed> \
     --tier <use-now|evaluate-next|track>
   ```
2. Verify access evidence before pipeline planning consumes the dataset:
   ```bash
   science dataset verify-access <slug> \
     --license <spdx-or-unknown> \
     --method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed> \
     --source-url "<landing-page-or-download-url>"
   ```
3. Link the dataset to the question or hypothesis it supports:
   ```bash
   science dataset link <dataset-ref> <question-or-hypothesis-ref>
   ```
4. Add acquisition scripts to `code/scripts/` or workflow rules under `code/workflows/`.
5. Create or update runtime datapackage descriptors in the appropriate data directory.

Manual template authoring is a fallback for unsupported fields, deliberate
legacy backfills, or project-specific review templates. When using that path,
write to `entities/datasets/<source-name>.md`, keep unknown evidence visibly
marked, and then run `science dataset verify-access <slug>` or record the
blocked verification reason.
````

- [ ] **Step 2: Replace the maturing-tooling fallback in `skills/data/SKILL.md`**

In `skills/data/SKILL.md`, replace the bullet list under `## While Tooling Is Still Maturing` with:

```markdown
- Use `science dataset add <slug>` and `science dataset verify-access <slug>`
  whenever current CLI fields can express the dataset record.
- Manually document data sources with the dataset template only when the CLI
  cannot represent the needed field or a project-specific review path requires
  the template.
- Download data by hand and place it in `data/raw/` only when automated download
  support is unavailable.
- Write preprocessing scripts in `code/scripts/` or workflow rules under
  `code/workflows/` with clear provenance.
- Keep runtime datapackage descriptors current for raw and processed data
  directories.
```

- [ ] **Step 3: Clarify the Frictionless lifecycle boundary**

In `skills/data/frictionless.md`, after the `Core Concepts` section, add:

```markdown
## Boundary With Dataset Entities

A Frictionless `datapackage.json` is a runtime/package descriptor for files that
exist in `data/raw/`, `data/processed/`, or result package directories. It is
not the local dataset entity lifecycle.

Use `science dataset add <slug>` and `science dataset verify-access <slug>` for
the durable `dataset:<slug>` entity. Use `science datasets validate --path
data/raw/`, `science datasets infer-schema`, and `science datasets qa` for
runtime datapackage descriptors and file-level QA.
```

- [ ] **Step 4: Update the Frictionless validation command wording**

In `skills/data/frictionless.md`, replace:

```bash
science datasets validate --path data/raw/
```

with the same command if it already exists, but make the preceding sentence say:

```markdown
# Validate a runtime data package (built-in lightweight checks)
```

The command itself should remain:

```bash
science datasets validate --path data/raw/
```

- [ ] **Step 5: Run the focused data-skill tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_command_docs.py::test_data_skill_routes_new_sources_through_dataset_entity_lifecycle \
  science/tests/test_command_docs.py::test_frictionless_skill_distinguishes_datapackages_from_dataset_entities \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit data skill guidance**

```bash
rtk git add skills/data/SKILL.md skills/data/frictionless.md science/tests/test_command_docs.py
rtk git commit -m "docs: clarify dataset entity and datapackage boundary"
```

Expected: commit succeeds.

---

### Task 5: Generated Command-Skill Guard Tests

**Files:**
- Modify: `science/tests/test_codex_skills.py`
- Test: `science/tests/test_codex_skills.py`

- [ ] **Step 1: Add failing committed generated-skill tests**

Append these tests near the existing generated `catalog-datasets` and `plan-pipeline` tests in `science/tests/test_codex_skills.py`:

```python
def test_committed_find_datasets_skill_routes_durable_records_through_dataset_lifecycle() -> None:
    text = _read_skill("science-find-datasets")

    assert "entities/questions/" in text
    assert "entities/hypotheses/" in text
    assert "legacy specs/research-question.md only if it exists" in text
    assert "science datasets search" in text
    assert "science dataset add <slug>" in text
    assert "--level <public|registration|controlled|commercial|mixed>" in text
    add_example = text.split("science dataset add <slug>", 1)[1].split(
        "science dataset verify-access <slug>",
        1,
    )[0]
    assert "--license" not in add_example
    assert "science dataset verify-access <slug>" in text
    assert "--method <retrieved|credential-confirmed|landing-confirmed|metadata-confirmed>" in text
    assert "--source-url \"<landing-page-or-download-url>\"" in text
    assert "science dataset link <dataset-ref> <question-or-hypothesis-ref>" in text
    assert "Direct template authoring is a fallback" in text
    assert "For each `Use now` or `Evaluate next` dataset, create a dataset note" not in text
    assert "--level <public|controlled|mixed>" not in text
    assert "--method <landing-confirmed|downloaded|manual-review>" not in text
    assert "--source \"<landing-page-or-download-url>\"" not in text
    assert "--date <YYYY-MM-DD>" not in text


def test_committed_plan_pipeline_skill_uses_current_dataset_verify_access_gate() -> None:
    text = _read_skill("science-plan-pipeline")

    assert "science dataset verify-access <slug>" in text
    assert "current `science dataset verify-access`" in text
    assert "future `science dataset verify`" not in text
```

- [ ] **Step 2: Run the generated-skill tests and confirm they fail before regeneration**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_codex_skills.py::test_committed_find_datasets_skill_routes_durable_records_through_dataset_lifecycle \
  science/tests/test_codex_skills.py::test_committed_plan_pipeline_skill_uses_current_dataset_verify_access_gate \
  -q
```

Expected: FAIL until committed generated mirrors are regenerated from the updated source docs.

- [ ] **Step 3: Commit generated-skill guard tests**

```bash
rtk git add science/tests/test_codex_skills.py
rtk git commit -m "test: guard generated dataset guidance"
```

Expected: commit succeeds.

---

### Task 6: Regenerate Codex Skills

**Files:**
- Regenerate: `codex-skills/`
- Test: `science/tests/test_codex_skills.py`

- [ ] **Step 1: Regenerate generated Codex skills from source docs**

Run from the repository root:

```bash
rtk uv run --frozen --project science python scripts/generate_codex_skills.py
```

Expected: command exits 0 and rewrites generated files under `codex-skills/`.

- [ ] **Step 2: Inspect generated diff**

```bash
rtk git diff -- codex-skills
```

Expected: generated mirrors reflect the updated command and skill source guidance. The diff should not introduce `/science:` references, `${CLAUDE_PLUGIN_ROOT}`, retired user-guide paths, or `@core/*.md` injection guidance.

- [ ] **Step 3: Run generated-skill tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_codex_skills.py::test_committed_find_datasets_skill_routes_durable_records_through_dataset_lifecycle \
  science/tests/test_codex_skills.py::test_committed_plan_pipeline_skill_uses_current_dataset_verify_access_gate \
  science/tests/test_codex_skills.py::test_no_generated_skill_has_at_core_injection_guidance \
  science/tests/test_codex_skills.py::test_no_generated_skill_references_retired_user_docs \
  -q
```

Expected: PASS.

- [ ] **Step 4: Commit regenerated skills**

```bash
rtk git add codex-skills science/tests/test_codex_skills.py
rtk git commit -m "docs: regenerate dataset guidance skills"
```

Expected: commit succeeds. If `science/tests/test_codex_skills.py` was already committed in Task 5 and has no new changes, `rtk git add` is harmless and the commit should include only generated files.

---

### Task 7: Optional User-Guide Tightening

**Files:**
- Modify only if needed: `docs/user-guide/cli-and-workflows.md`
- Modify only if needed: `docs/user-guide/entities.md`
- Modify only if needed: `docs/user-guide/cross-project-work.md`
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Search for remaining ambiguous dataset command guidance**

```bash
rtk rg -n "science datasets|science dataset|data-package|verify-access|dataset verify|entities/datasets/<slug>|data_sources" \
  docs/user-guide commands skills
```

Expected: output shows no remaining stale `science dataset verify` references outside audit/design/plan history, no routine direct authoring path for new dataset entities, and no user-guide wording that makes `science data-package` look like the current default for new work.

- [ ] **Step 2: Add a user-guide guard only if the search exposes a real gap**

If `docs/user-guide/cli-and-workflows.md` lacks a local command-boundary assertion near its dataset command taxonomy, add this test to `science/tests/test_command_docs.py`:

```python
def test_cli_user_guide_states_dataset_command_boundaries() -> None:
    text = _read("docs/user-guide/cli-and-workflows.md")

    assert "singular `dataset`" in text
    assert "plural `datasets`" in text
    assert "local dataset entity" in text
    assert "external discovery" in text
    assert "runtime" in text
    assert "legacy migration" in text
```

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_command_docs.py::test_cli_user_guide_states_dataset_command_boundaries \
  -q
```

Expected if added before doc edits: FAIL.

- [ ] **Step 3: Tighten only the missing user-guide wording**

If Step 2 was needed, add this paragraph near the dataset command taxonomy in `docs/user-guide/cli-and-workflows.md`:

```markdown
Use singular `science dataset ...` for the local dataset entity lifecycle:
creating records, verifying access, linking datasets to questions or
hypotheses, prioritizing candidates, and registering derived outputs. Use
plural `science datasets ...` for external discovery and runtime datapackage
work such as search, metadata inspection, downloads, schema inference,
validation, QA, and worktree hydration.
```

Do not edit `docs/user-guide/entities.md` or `docs/user-guide/cross-project-work.md` unless the search output shows a concrete stale or ambiguous sentence.

- [ ] **Step 4: Run the user-guide guard if it was added**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_command_docs.py::test_cli_user_guide_states_dataset_command_boundaries \
  -q
```

Expected: PASS if the test was added. If Step 2 was not needed, skip this command and record that the existing user-guide wording was already sufficient.

- [ ] **Step 5: Commit optional user-guide tightening if files changed**

```bash
rtk git add docs/user-guide/cli-and-workflows.md docs/user-guide/entities.md docs/user-guide/cross-project-work.md science/tests/test_command_docs.py
rtk git commit -m "docs: tighten dataset command taxonomy"
```

Expected: commit succeeds only if Step 2 or Step 3 made changes. If no user-guide changes were needed, do not create an empty commit.

---

### Task 8: Final Verification And Cleanup

**Files:**
- Verify: all modified source docs, tests, and generated skill mirrors

- [ ] **Step 1: Run focused documentation and generated-skill tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_command_docs.py \
  science/tests/test_codex_skills.py \
  science/tests/test_user_guide_docs.py \
  science/tests/test_no_doc_owner_path_literals.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run formatting/lint checks for touched Python tests**

```bash
rtk uv run --frozen --project science ruff check \
  science/tests/test_command_docs.py \
  science/tests/test_codex_skills.py
```

Expected: PASS with `All checks passed!`.

- [ ] **Step 3: Inspect final diff**

```bash
rtk git diff --stat
rtk git diff -- commands/find-datasets.md commands/plan-pipeline.md commands/review-pipeline.md skills/data/SKILL.md skills/data/frictionless.md science/tests/test_command_docs.py science/tests/test_codex_skills.py
```

Expected: diff shows only the intended guidance/test/generated-skill changes. It should not include CLI implementation changes.

- [ ] **Step 4: Check worktree status**

```bash
rtk git status --short --branch
```

Expected: clean, or only intentionally uncommitted plan/audit changes if the implementation branch is still in a planning phase.

---

## Self-Review

- Spec coverage:
  - `commands/find-datasets.md` direct-file authoring and legacy `specs/` assumptions are covered by Tasks 1 and 2.
  - `commands/plan-pipeline.md` stale `science dataset verify` wording is covered by Tasks 1 and 2.
  - `commands/review-pipeline.md` current access-gate wording is covered by Tasks 1 and 2.
  - `skills/data/SKILL.md` and `skills/data/frictionless.md` lifecycle boundaries are covered by Tasks 3 and 4.
  - Generated command-skill `codex-skills/` alignment is covered by Tasks 5 and 6.
  - Optional user-guide tightening is limited to concrete ambiguity and covered by Task 7.
  - Final verification is covered by Task 8.
- Placeholder scan:
  - No task uses undefined placeholders as instructions. Angle-bracket command arguments such as `<slug>` and `<source>:<id>` are literal command-doc conventions already used in this repository.
- Type/signature consistency:
  - Tests use existing `_read(path: str) -> str`, `ROOT`, and `generate_codex_skills(ROOT, tmp_path)` patterns.
  - Generated-skill names follow existing `command_to_skill_name` output such as `science-find-datasets` and `science-plan-pipeline`.

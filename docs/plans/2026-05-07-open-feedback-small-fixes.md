# Open Feedback Small Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address five open downstream feedback items while leaving bibliography source references as a design-only follow-up.

**Architecture:** The runtime fix is a core kind registration for `research-question`. The remaining fixes are command/template contract updates guarded by command-doc tests. Feedback status files are updated only after verification.

**Tech Stack:** Python 3.11, pytest, Click, Markdown command docs, YAML feedback records.

---

### Task 1: Register `research-question`

**Files:**
- Modify: `science/tests/test_entity_registry.py`
- Modify: `science/tests/test_load_project_sources_unified.py`
- Modify: `science/src/science_tool/graph/entity_registry.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert `research-question` resolves to `ProjectEntity`, is epistemic, and that `specs/research-question.md` with `id: rq:test` and `type: research-question` loads through `load_project_sources`.

- [ ] **Step 2: Verify RED**

Run `uv run --frozen pytest tests/test_entity_registry.py::test_research_question_kind_registered tests/test_load_project_sources_unified.py::test_load_project_sources_includes_research_question_with_rq_prefix -q` from `science/`. Expected failure: `research-question` is not registered.

- [ ] **Step 3: Implement**

Add `"research-question": EntityClass.EPISTEMIC` to `_CORE_KIND_CLASSES` and include `"research-question"` in the generic ProjectEntity kind loop.

- [ ] **Step 4: Verify GREEN**

Re-run the targeted tests.

### Task 2: Reclassify bias-audit template output

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Modify: `templates/bias-audit.md`
- Modify: `science/model/src/science_model/templates/bias-audit.md`

- [ ] **Step 1: Write failing doc-contract test**

Assert both bias-audit templates use `id: "report:bias-audit-{{slug}}"` and `type: "report"`, and no longer use `task:{{slug}}` or `type: "task"`.

- [ ] **Step 2: Verify RED**

Run `uv run --frozen pytest tests/test_command_docs.py::test_bias_audit_templates_emit_report_not_task -q` from `science/`. Expected failure: templates still emit task frontmatter.

- [ ] **Step 3: Implement**

Update both templates to emit a report entity.

- [ ] **Step 4: Verify GREEN**

Re-run the targeted test.

### Task 3: Make bias-audit commits conditional

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Modify: `commands/bias-audit.md`

- [ ] **Step 1: Write failing doc-contract test**

Assert the command says to commit only when the user/session explicitly requested commit approval, and that the unconditional `Commit: git add -A && git commit ...` instruction is absent.

- [ ] **Step 2: Verify RED**

Run `uv run --frozen pytest tests/test_command_docs.py::test_bias_audit_commit_step_is_conditional -q` from `science/`.

- [ ] **Step 3: Implement**

Replace the unconditional commit step with conditional guidance to report changed files unless commit approval exists.

- [ ] **Step 4: Verify GREEN**

Re-run the targeted test.

### Task 4: Document existing-inquiry sketch upgrade workflow

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Modify: `commands/sketch-model.md`

- [ ] **Step 1: Write failing doc-contract test**

Assert `sketch-model` documents upgrading/registering an existing `doc/inquiries/<slug>.md` before graph edits and preserving the existing slug/frontmatter.

- [ ] **Step 2: Verify RED**

Run `uv run --frozen pytest tests/test_command_docs.py::test_sketch_model_documents_existing_inquiry_upgrade -q` from `science/`.

- [ ] **Step 3: Implement**

Add an "Existing Inquiry Upgrade" workflow branch before the create-new-inquiry commands.

- [ ] **Step 4: Verify GREEN**

Re-run the targeted test.

### Task 5: Document pre-DAG critique mode

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Modify: `commands/critique-approach.md`

- [ ] **Step 1: Write failing doc-contract test**

Assert `critique-approach` documents a pre-DAG degraded mode for Markdown/sketch-stage inquiries, records validation unavailable, and forbids claiming formal adjustment-set review.

- [ ] **Step 2: Verify RED**

Run `uv run --frozen pytest tests/test_command_docs.py::test_critique_approach_documents_pre_dag_mode -q` from `science/`.

- [ ] **Step 3: Implement**

Add the degraded-mode branch before graph-theoretic analysis.

- [ ] **Step 4: Verify GREEN**

Re-run the targeted test.

### Task 6: Update feedback statuses

**Files:**
- Modify: `~/.config/science/feedback/fb-2026-05-05-001.yaml`
- Modify: `~/.config/science/feedback/fb-2026-05-05-002.yaml`
- Modify: `~/.config/science/feedback/fb-2026-05-05-003.yaml`
- Modify: `~/.config/science/feedback/fb-2026-05-07-001.yaml`
- Modify: `~/.config/science/feedback/fb-2026-05-07-002.yaml`
- Modify: `~/.config/science/feedback/fb-2026-05-07-003.yaml`

- [ ] **Step 1: Verify all targeted tests**

Run `uv run --frozen pytest tests/test_entity_registry.py tests/test_load_project_sources_unified.py tests/test_command_docs.py -q` from `science/`.

- [ ] **Step 2: Mark five implemented feedback records addressed**

Use `science feedback update <id> --status addressed --resolution "<specific resolution>"` for the five implemented items.

- [ ] **Step 3: Mark bibliography item designed**

Use `science feedback update fb-2026-05-05-002 --status addressed --resolution "Design captured in docs/superpowers/specs/2026-05-07-bibliography-source-refs-design.md; implementation intentionally deferred."`

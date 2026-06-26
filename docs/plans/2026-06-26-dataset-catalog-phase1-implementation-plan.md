# Dataset Catalog Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Phase 1 dataset catalog model and validation foundation: expanded access verification vocabulary, explicit dataset class helpers, deterministic runtime states, metadata validation, and health warning exemptions.

**Architecture:** Keep `dataset:*` as the entity kind. Add one small semantics module for class/runtime derivation so validation, health, and later CLI phases share the same source of truth. Update authoritative model/schema/template surfaces in one change so `verification_method` values cannot drift.

**Tech Stack:** Python 3, Pydantic v2, JSON Schema, Click, pytest, ruff.

---

### Task 1: Schema Vocabulary

**Files:**
- Modify: `science/model/src/science_model/packages/schema.py`
- Modify: `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
- Modify: `science/model/src/science_model/schemas/science-pkg-entity-1.0.json`
- Modify: `science/model/src/science_model/templates/dataset.md`
- Modify: `templates/dataset.md`
- Test: `science/model/tests/test_dataset_models.py`
- Test: `science/model/tests/test_entity_schema_mixin_dataset.py`
- Test: `science/tests/validate/test_checks_dataset_metadata.py`

- [ ] **Step 1: Write failing tests**

Add tests that instantiate `AccessBlock(..., verification_method="landing-confirmed")` and `"metadata-confirmed"`, and assert both JSON schema enum surfaces include `{"", "retrieved", "credential-confirmed", "landing-confirmed", "metadata-confirmed"}`.

- [ ] **Step 2: Verify red**

Run: `cd science && uv run --frozen pytest model/tests/test_dataset_models.py model/tests/test_entity_schema_mixin_dataset.py tests/validate/test_checks_dataset_metadata.py -q`

Expected: FAIL because the new verification methods are not accepted by the Pydantic literal or schema enums.

- [ ] **Step 3: Implement vocabulary**

Extend the `AccessBlock.verification_method` `Literal`, both JSON schema enums, and both dataset template comments.

- [ ] **Step 4: Verify green**

Run the same pytest command. Expected: all selected tests pass.

### Task 2: Dataset Semantics Helpers

**Files:**
- Create: `science/src/science_tool/datasets/semantics.py`
- Test: `science/tests/test_dataset_semantics.py`

- [ ] **Step 1: Write failing tests**

Cover:
- missing `dataset_class` returns `deposit`;
- `source_class: reference` with `datapackage` remains a `deposit` and runtime `runnable`;
- explicit `dataset_class: reference` returns `reference-only`;
- explicit `dataset_class: pointer` returns `pointer-only`;
- verified deposit without runtime artifact returns `unstaged-deposit`;
- unverified/gated/exception deposit returns `blocked-access`.

- [ ] **Step 2: Verify red**

Run: `cd science && uv run --frozen pytest tests/test_dataset_semantics.py -q`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement helpers**

Add:

```python
DatasetClass = Literal["deposit", "reference", "pointer"]
RuntimeState = Literal["runnable", "unstaged-deposit", "blocked-access", "reference-only", "pointer-only"]
def dataset_class_for(fm: Mapping[str, object]) -> DatasetClass: ...
def runtime_state_for(fm: Mapping[str, object]) -> RuntimeState: ...
def has_runtime_artifact(fm: Mapping[str, object]) -> bool: ...
```

Use the precedence from `docs/plans/2026-06-26-dataset-catalog-triage-pack-design.md`.

- [ ] **Step 4: Verify green**

Run: `cd science && uv run --frozen pytest tests/test_dataset_semantics.py -q`

Expected: all new tests pass.

### Task 3: Validation Checks

**Files:**
- Modify: `science/src/science_tool/validate/checks/dataset_metadata.py`
- Test: `science/tests/validate/test_checks_dataset_metadata.py`

- [ ] **Step 1: Write failing tests**

Add tests for:
- `dataset.legacy-missing-class` info when `dataset_class` is absent;
- no class inference from `source_class: reference`;
- `dataset.method-class-mismatch` for `reference` + `retrieved`;
- `dataset.method-class-mismatch` for `deposit` + `landing-confirmed`;
- `dataset.reference-missing-source-url` checks only `access.source_url`;
- `dataset.reference-runtime-artifact` and `dataset.pointer-runtime-artifact`.

- [ ] **Step 2: Verify red**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_dataset_metadata.py -q`

Expected: FAIL because the rules are not emitted.

- [ ] **Step 3: Implement validation**

Use `dataset_class_for()` and `has_runtime_artifact()` from the semantics module. Emit WARN for mismatches/runtime artifacts/source URL gaps and INFO for missing class.

- [ ] **Step 4: Verify green**

Run: `cd science && uv run --frozen pytest tests/validate/test_checks_dataset_metadata.py -q`

Expected: all metadata tests pass.

### Task 4: Health Warning Exemption

**Files:**
- Modify: `science/src/science_tool/graph/health.py`
- Test: `science/tests/test_health.py`

- [ ] **Step 1: Write failing tests**

Add tests showing `dataset_class: reference` and `dataset_class: pointer` do not emit `dataset_verified_but_unstageable`, while a verified `deposit` without runtime artifact still emits it with stageability wording.

- [ ] **Step 2: Verify red**

Run: `cd science && uv run --frozen pytest tests/test_health.py -k "dataset_verified_but_unstageable or reference_class or pointer_class" -q`

Expected: FAIL because health does not consult `dataset_class`.

- [ ] **Step 3: Implement exemption**

Import `dataset_class_for()` and `runtime_state_for()`. Exempt non-deposit classes entirely and change the verified unstaged deposit message to say access is verified but runtime files are not staged.

- [ ] **Step 4: Verify green**

Run the same pytest command. Expected: selected health tests pass.

### Task 5: Focused Verification

**Files:**
- All modified files from Tasks 1-4.

- [ ] **Step 1: Run focused tests**

Run:

```bash
cd science
uv run --frozen pytest model/tests/test_dataset_models.py model/tests/test_entity_schema_mixin_dataset.py tests/test_dataset_semantics.py tests/validate/test_checks_dataset_metadata.py tests/test_health.py tests/test_dataset_prioritize.py tests/test_dataset_verify_access.py tests/test_dataset_add_cli.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run lint**

Run:

```bash
cd science
uv run --frozen ruff check model/src/science_model/packages/schema.py src/science_tool/datasets/semantics.py src/science_tool/validate/checks/dataset_metadata.py src/science_tool/graph/health.py tests/test_dataset_semantics.py tests/validate/test_checks_dataset_metadata.py tests/test_health.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/plans/2026-06-26-dataset-catalog-triage-pack-design.md docs/plans/2026-06-26-dataset-catalog-phase1-implementation-plan.md science/model/src/science_model/packages/schema.py science/model/src/science_model/schemas/mixin-dataset-1.0.json science/model/src/science_model/schemas/science-pkg-entity-1.0.json science/model/src/science_model/templates/dataset.md templates/dataset.md science/src/science_tool/datasets/semantics.py science/src/science_tool/validate/checks/dataset_metadata.py science/src/science_tool/graph/health.py science/model/tests/test_dataset_models.py science/model/tests/test_entity_schema_mixin_dataset.py science/tests/test_dataset_semantics.py science/tests/validate/test_checks_dataset_metadata.py science/tests/test_health.py
git commit -m "feat(cli): add dataset catalog class semantics"
```

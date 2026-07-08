# Review-Pipeline Data Availability Tightening Implementation Plan

> **Status:** IMPLEMENTED on `main`.
>
> The locked-model input reconciliation rule, reference-class input deferral
> carve-out, command-doc tests, and generated Codex skill tests are present.
> This plan remains as the implementation record; unchecked task boxes below
> are stale.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the `review-pipeline` data-availability rubric so reviewers catch undeclared locked-model inputs and have a narrow, explicit reference-class input deferral rule.

**Architecture:** This is a source-guidance change. The command markdown and generated Codex skill are the behavior surface; doc tests guard the required wording and keep both surfaces aligned.

**Tech Stack:** Markdown command docs, Codex skill markdown, Pytest source-doc tests.

---

### Task 1: Lock the new rubric requirements with failing tests

**Files:**
- Modify: `science/tests/test_command_docs.py`
- Modify: `science/tests/test_codex_skills.py`

- [ ] **Step 1: Add the command-doc tests**

Add these tests near the existing `review-pipeline` tests in `science/tests/test_command_docs.py`:

```python
def test_review_pipeline_checks_locked_model_inputs_against_plan_inputs() -> None:
    text = _read("commands/review-pipeline.md")
    normalized = " ".join(text.split())

    assert "locked pre-registration model" in text
    assert "plan-declared input" in text
    assert "covariates, adjustment variables, strata" in text
    assert "endpoint/timing variables" in text
    assert "score inputs" in text
    assert "signature features" in text
    assert "undeclared locked-model requirement" in normalized
    assert "pre-registration model requires a covariate" in text
    assert "plan never declares as an input" in text


def test_review_pipeline_documents_reference_class_input_carveout() -> None:
    text = _read("commands/review-pipeline.md")
    normalized = " ".join(text.split())

    assert "Reference-class input deferral" in text
    assert "LD panels" in text
    assert "genome builds" in text
    assert "annotation releases" in text
    assert "benchmark/reference resources" in text
    assert "follow-on design or staging work package" in text
    assert "version pinning" in text
    assert "checksums or equivalent identity evidence" in text
    assert "compatibility checks" in text
    assert "does not apply to primary analytic datasets" in normalized
    assert "ordinary covariates, or locked-model variables" in text
```

- [ ] **Step 2: Add the Codex skill tests**

Add this test near the existing `science-review-pipeline` generated skill test in
`science/tests/test_codex_skills.py`:

```python
def test_review_pipeline_skill_documents_data_availability_tightening(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    text = generated["science-review-pipeline"].read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "locked pre-registration model" in text
    assert "covariates, adjustment variables, strata" in text
    assert "undeclared locked-model requirement" in normalized
    assert "Reference-class input deferral" in text
    assert "LD panels" in text
    assert "follow-on design or staging work package" in text
    assert "checksums or equivalent identity evidence" in text
    assert "does not apply to primary analytic datasets" in normalized
```

- [ ] **Step 3: Run the focused tests and confirm they fail**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_command_docs.py::test_review_pipeline_checks_locked_model_inputs_against_plan_inputs \
  tests/test_command_docs.py::test_review_pipeline_documents_reference_class_input_carveout \
  tests/test_codex_skills.py::test_review_pipeline_skill_documents_data_availability_tightening \
  -q
```

Expected: tests fail because the new rubric text is not present.

### Task 2: Update the review-pipeline command rubric

**Files:**
- Modify: `commands/review-pipeline.md`

- [ ] **Step 1: Add locked-model input reconciliation**

In `commands/review-pipeline.md`, inside `#### Dimension 3: Data Availability`, add a bullet after the plan input-source opening line:

```markdown
- Cross-check declared plan inputs against the locked pre-registration model
  before scoring. Required covariates, adjustment variables, strata/subgroup
  labels, endpoint/timing variables, score inputs, and signature features from
  the locked model must appear as a plan-declared input or derived input with
  traceable upstream sources. Treat any undeclared locked-model requirement as
  a data-availability **FAIL**, because the plan is not stageable for the model
  it claims to run.
```

- [ ] **Step 2: Add reference-class input deferral**

In the Runtime stageability bullet list, add this after the existing WP1 retrieval
probe exception:

```markdown
  - Reference-class input deferral: resources such as LD panels, genome builds,
    annotation releases, and benchmark/reference resources may defer runtime
    staging only when the plan explicitly labels them as reference-class inputs
    and names a follow-on design or staging work package that will own
    acquisition, version pinning, checksums or equivalent identity evidence, and
    compatibility checks before downstream analysis runs. This carve-out does
    not apply to primary analytic datasets, ordinary covariates, or
    locked-model variables.
```

- [ ] **Step 3: Update PASS/FAIL scoring**

Update the PASS bullet to include locked-model reconciliation and explicit
reference-class deferral:

```markdown
- **PASS** — all sources resolve; declared plan inputs cover locked-model
  requirements; verification gate satisfied per origin; runtime stageability
  satisfied, or runtime stageability is explicitly deferred to WP1 under the
  retrieval-probe exception above or to an owned reference-class input deferral;
  backlink present; freshness OK; invariants hold.
```

Add these FAIL bullets:

```markdown
  - A locked pre-registration model requires a covariate, adjustment variable,
    stratum/subgroup label, endpoint/timing variable, score input, or signature
    feature that the plan never declares as an input or derived input.
  - A reference-class input is deferred without an explicit follow-on design or
    staging work package that owns version pinning, checksums or equivalent
    identity evidence, and compatibility checks.
```

- [ ] **Step 4: Run command-doc tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_command_docs.py::test_review_pipeline_checks_locked_model_inputs_against_plan_inputs \
  tests/test_command_docs.py::test_review_pipeline_documents_reference_class_input_carveout \
  -q
```

Expected: command-doc tests pass.

### Task 3: Mirror the command rubric into the Codex skill

**Files:**
- Modify: `codex-skills/science-review-pipeline/SKILL.md`

- [ ] **Step 1: Apply the same Dimension 3 wording**

Make the same three edits from Task 2 in
`codex-skills/science-review-pipeline/SKILL.md`.

- [ ] **Step 2: Run the Codex skill test**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest \
  tests/test_codex_skills.py::test_review_pipeline_skill_documents_data_availability_tightening \
  -q
```

Expected: generated skill test passes.

### Task 4: Verify and commit

**Files:**
- Modified files from Tasks 1-3
- Added docs:
  - `docs/plans/2026-07-07-review-pipeline-data-availability-design.md`
  - `docs/plans/2026-07-07-review-pipeline-data-availability-plan.md`

- [ ] **Step 1: Run focused regression tests**

Run from `science/`:

```bash
PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest tests/test_command_docs.py tests/test_codex_skills.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run lint**

Run from `science/`:

```bash
uv run --frozen ruff check
```

Expected: no lint errors.

- [ ] **Step 3: Inspect the diff**

Run from the worktree root:

```bash
git diff -- commands/review-pipeline.md codex-skills/science-review-pipeline/SKILL.md science/tests/test_command_docs.py science/tests/test_codex_skills.py docs/plans/2026-07-07-review-pipeline-data-availability-design.md docs/plans/2026-07-07-review-pipeline-data-availability-plan.md
```

Expected: diff is limited to the approved rubric wording, tests, and docs.

- [ ] **Step 4: Commit**

Run from the worktree root:

```bash
git add commands/review-pipeline.md codex-skills/science-review-pipeline/SKILL.md science/tests/test_command_docs.py science/tests/test_codex_skills.py docs/plans/2026-07-07-review-pipeline-data-availability-design.md docs/plans/2026-07-07-review-pipeline-data-availability-plan.md
git commit -m "docs(review-pipeline): tighten data availability rubric"
```

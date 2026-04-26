# Science Plan Analysis Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/science:plan-analysis` as the methodology-readiness command that uses `skills/INDEX.md`, selects relevant leaves, and writes analysis plans before pre-registration or pipeline work.

**Architecture:** This is a command-documentation feature, not a runtime CLI. The primary artifact is `commands/plan-analysis.md`; generated `codex-skills/science-plan-analysis/SKILL.md` is produced by the existing generator. Existing commands get short routing hooks toward `plan-analysis` when analysis assumptions are underspecified.

**Tech Stack:** Markdown command docs, generated Codex skills, Python pytest docs tests, `uv`, existing `scripts/generate_codex_skills.py`.

---

## File Structure

### Created

- `commands/plan-analysis.md` - new Science command source.
- `codex-skills/science-plan-analysis/SKILL.md` - generated from command source.

### Modified

- `commands/plan-pipeline.md` - add methodology-readiness gate before orchestration.
- `commands/pre-register.md` - read linked analysis plans and recommend plan-analysis when assumptions are missing.
- `commands/status.md` - surface plan-analysis as a next step when analysis-facing work lacks an analysis plan.
- `commands/next-steps.md` - detect analysis-plan tracking gaps.
- `science-tool/tests/test_command_docs.py` - command behavior coverage.
- `science-tool/tests/test_codex_skills.py` - generated skill coverage.

### Out of Scope

- `science-tool plan-analysis` CLI.
- `science-tool skills search`.
- `skills/catalog.yaml`.
- Automatic modality detection from data files.

## Task 1: Add Command-Doc Tests For `plan-analysis`

**Files:**
- Modify: `science-tool/tests/test_command_docs.py`

- [ ] **Step 1: Add a failing test for the new command source**

Append this test after `test_command_docs_use_explicit_framework_resolution`:

```python
def test_plan_analysis_command_defines_methodology_readiness_workflow() -> None:
    text = _read("commands/plan-analysis.md")

    expected_strings = (
        "${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md",
        "${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md",
        "doc/plans/YYYY-MM-DD-<slug>-analysis-plan.md",
        "type: analysis-plan",
        "skills_loaded:",
        "Readiness Decision",
        "ready-with-caveats",
        "science-tool feedback add",
        "--target \"command:plan-analysis\"",
    )
    for expected in expected_strings:
        assert expected in text
```

- [ ] **Step 2: Add a failing test for the validation scenarios**

Append this test in the same file:

```python
def test_plan_analysis_command_covers_pressure_scenarios() -> None:
    text = _read("commands/plan-analysis.md")

    expected_strings = (
        "MM30 scRNA pseudobulk / entropy analysis",
        "cBioPortal targeted-panel mutation frequency or dN/dS analysis",
        "Natural-systems annotation/curation agreement analysis",
        "Protein-landscape heldout benchmark or embedding-manifold analysis",
        "data-expression-scrna-qa",
        "data-genomics-somatic-mutation-qa",
        "research-annotation-curation-qa",
        "data-protein-sequence-structure-qa",
    )
    for expected in expected_strings:
        assert expected in text
```

- [ ] **Step 3: Run the focused test and verify failure**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_command_docs.py::test_plan_analysis_command_defines_methodology_readiness_workflow tests/test_command_docs.py::test_plan_analysis_command_covers_pressure_scenarios -v
```

Expected: FAIL because `commands/plan-analysis.md` does not exist.

## Task 2: Create `commands/plan-analysis.md`

**Files:**
- Create: `commands/plan-analysis.md`

- [ ] **Step 1: Write the command document**

Create `commands/plan-analysis.md` with these sections:

```markdown
---
description: Plan whether an individual data analysis is methodologically ready before pre-registration, pipeline planning, or implementation. Use when the user asks to plan a statistical/data analysis, inspect dataset fitness, choose preprocessing/model assumptions, or prepare an analysis for pre-registration.
---

# Plan Analysis Readiness

> **Prerequisites:**
> - Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).
> - Read `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md`.
> - Load only the skill leaves justified by the modality, estimand, and data-signal classification.

## Purpose

Decide whether one analysis is methodologically ready to run. This command owns
data modality classification, input QA, independent-unit checks, estimand and
metric clarity, power/resolution limits, bias-vs-variance risks, sensitivity
arbitration, and required output artifacts.

Use `/science:plan-pipeline` after this command when execution orchestration is
non-trivial. Use `/science:pre-register` after this command when the plan is
`ready` or `ready-with-caveats` and confirmatory criteria should be locked.

## Setup

1. Read `science.yaml`.
2. Read `specs/research-question.md` if present.
3. Read relevant hypotheses, inquiries, tasks, prior pre-registrations, and existing plans named by the user.
4. If an inquiry slug is provided, read the inquiry/model state and reuse captured estimand, variables, independent unit, and model/test fields.
5. If the task is literature synthesis or theory without a data-analysis component, route to `/science:research-topic` or `/science:research-papers` unless the user explicitly wants an analysis plan.

## Leaf Selection Rubric

Pick the minimum leaves justified by the task. Multi-modal analyses accumulate
rows and de-duplicate. Record every loaded skill in `skills_loaded` with a
reason.

| Trigger phrase / data signal | Required leaves |
|---|---|
| RNA-seq DE, count matrix, TPM/FPKM, GEO expression cohort | `data-expression`, matching expression sub-leaf (`data-expression-bulk-rnaseq-qa`, `data-expression-microarray-qa`, or `data-expression-scrna-qa`), `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| Single-cell RNA-seq, h5ad, pseudobulk, per-cell model | `data-expression`, `data-expression-scrna-qa`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| Cell-type proportions, deconvolution, mixture fractions | `data-expression-scrna-qa` when scRNA-derived, `statistics-compositional-data`, `statistics-power-floor-acknowledgement` |
| Microarray, probe IDs, Affymetrix/Agilent/Illumina | `data-expression`, `data-expression-microarray-qa`, `statistics-bias-vs-variance-decomposition` |
| Targeted-panel mutation frequency, cBioPortal, GENIE, MAF | `data-genomics-somatic-mutation-qa`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition` |
| SBS signatures, TMB, dN/dS, dNdScv, driver ranking | `data-genomics-somatic-mutation-qa`, `data-genomics-mutational-signatures-and-selection`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| CRISPR/RNAi, DepMap, LINCS/L1000, drug response | `data-functional-genomics-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Survival, Cox, Weibull, censored outcomes across cohorts | `statistics-survival-and-hierarchical-models`, `statistics-power-floor-acknowledgement`, `statistics-sensitivity-arbitration` |
| Fractions/proportions constrained to sum to one | `statistics-compositional-data`, `statistics-bias-vs-variance-decomposition` |
| Embedding clustering, UMAP, HDBSCAN, Mapper, CKA, Moran's I | `data-embeddings-manifold-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration` |
| Protein PLM, UniProt/Pfam/CATH/Foldseek/MMseqs labels | `data-protein-sequence-structure-qa`; add `data-embeddings-manifold-qa` when embeddings/manifolds are analyzed |
| Manual/LLM annotation, claim extraction, taxonomy labels | `research-annotation-curation-qa`, `research-methodology` |

## Workflow

1. Classify the analysis: modalities, independent unit, estimand, intended model/test, confirmatory vs exploratory status.
2. Load the minimum relevant leaves from `skills/INDEX.md`.
3. Identify required input inspection and preprocessing/normalization checks.
4. State model/test assumptions, power floor or resolution limit, bias-vs-variance risks, and sensitivity-arbitration rules.
5. Decide exactly one readiness state: `ready`, `ready-with-caveats`, or `not-ready`.
6. Save the analysis plan by default.
7. If graph tooling is available, link the saved plan to referenced hypothesis, inquiry, and task entities.
8. If `not-ready`, create one task per blocking check when task tooling is available; otherwise list exact task text in the plan.

## Output

Save to `doc/plans/YYYY-MM-DD-<slug>-analysis-plan.md` unless the user explicitly requests terminal-only output.

Use this frontmatter:

```yaml
---
type: analysis-plan
id: analysis-plan:<slug>
date: YYYY-MM-DD
related:
  - hypothesis:<id>
  - inquiry:<slug>
  - task:<id>
status: ready | ready-with-caveats | not-ready
skills_loaded:
  - id: data-expression-scrna-qa
    reason: single-cell/pseudobulk expression analysis
---
```

The body must include:

- Analysis Question
- Related Hypotheses / Inquiries / Tasks
- Data Inputs and Provenance
- Required Input Inspection
- Preprocessing / Normalization Checks
- Independent Unit and Denominator
- Estimand and Primary Metric
- Model / Test Assumptions
- Power Floor or Resolution Limit
- Bias vs Variance Risks
- Sensitivity Arbitration
- Required Output Artifacts
- Aspect-contributed Sections
- Readiness Decision
- Feedback Reflection

For `ready-with-caveats`, include `Known Limitations To Carry Forward`.
For `not-ready`, include `Blocking Checks Before Pre-Registration`.

## Validation Pressure Scenarios

Use these as spot checks when applying the command:

1. **MM30 scRNA pseudobulk / entropy analysis** - include `data-expression`, `data-expression-scrna-qa`, `statistics-replicate-count-justification`, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition`, `statistics-sensitivity-arbitration`, and `statistics-compositional-data` if cell fractions enter the analysis.
2. **cBioPortal targeted-panel mutation frequency or dN/dS analysis** - include `data-genomics-somatic-mutation-qa`, `data-genomics-mutational-signatures-and-selection` for dN/dS/TMB/driver ranking, `statistics-power-floor-acknowledgement`, `statistics-bias-vs-variance-decomposition`, and `statistics-sensitivity-arbitration`.
3. **Natural-systems annotation/curation agreement analysis** - include `research-annotation-curation-qa`, `research-methodology`, `scientific-writing`, plus `statistics-bias-vs-variance-decomposition` and `statistics-power-floor-acknowledgement` when agreement statistics are verdict-bearing.
4. **Protein-landscape heldout benchmark or embedding-manifold analysis** - include `data-protein-sequence-structure-qa`, `data-embeddings-manifold-qa`, `statistics-bias-vs-variance-decomposition`, `statistics-power-floor-acknowledgement`, and `statistics-sensitivity-arbitration`.

## Process Reflection

Reflect on the **template**, **skill index**, and **workflow** used above.

If you have feedback, report each item via:

```bash
science-tool feedback add \
  --target "command:plan-analysis" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Skip if everything worked smoothly.
```

- [ ] **Step 2: Run the command-doc tests**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_command_docs.py::test_plan_analysis_command_defines_methodology_readiness_workflow tests/test_command_docs.py::test_plan_analysis_command_covers_pressure_scenarios -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add commands/plan-analysis.md science-tool/tests/test_command_docs.py
git commit -m "feat(commands): add science plan-analysis command"
```

## Task 3: Integrate Neighbor Commands

**Files:**
- Modify: `commands/plan-pipeline.md`
- Modify: `commands/pre-register.md`
- Modify: `commands/status.md`
- Modify: `commands/next-steps.md`
- Modify: `science-tool/tests/test_command_docs.py`

- [ ] **Step 1: Add failing integration test**

Append this test to `science-tool/tests/test_command_docs.py`:

```python
def test_plan_analysis_is_integrated_with_neighbor_commands() -> None:
    expected_by_path = {
        "commands/plan-pipeline.md": (
            "/science:plan-analysis",
            "methodological readiness",
            "analysis-plan:<slug>",
        ),
        "commands/pre-register.md": (
            "analysis-plan:<slug>",
            "doc/plans/*-analysis-plan.md",
            "/science:plan-analysis",
        ),
        "commands/status.md": (
            "analysis-plan:<slug>",
            "/science:plan-analysis",
        ),
        "commands/next-steps.md": (
            "analysis-plan:<slug>",
            "doc/plans/*-analysis-plan.md",
            "/science:plan-analysis",
        ),
    }
    for path, expected_strings in expected_by_path.items():
        text = _read(path)
        for expected in expected_strings:
            assert expected in text
```

- [ ] **Step 2: Run the integration test and verify failure**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_command_docs.py::test_plan_analysis_is_integrated_with_neighbor_commands -v
```

Expected: FAIL on at least one missing integration string.

- [ ] **Step 3: Update `commands/plan-pipeline.md`**

Under `## Rules`, add:

```markdown
- **MUST** check whether methodological readiness is already documented by an `analysis-plan:<slug>` artifact. If not, and the user is asking for orchestration before data QA, independent unit, estimand, power/resolution, and sensitivity rules are clear, recommend `/science:plan-analysis` before finalizing the pipeline plan.
```

Under `## Input Modes`, add:

```markdown
When an existing analysis plan is in scope, read `doc/plans/*-analysis-plan.md`
and reuse its methodological readiness checks. Do not re-decide those checks in
the pipeline plan; focus on execution.
```

- [ ] **Step 4: Update `commands/pre-register.md`**

In `## Setup`, add:

```markdown
6. Read linked analysis plans in `doc/plans/*-analysis-plan.md` when the user or context references `analysis-plan:<slug>`.
```

After `### 1. Identify the Analysis`, add:

```markdown
If this is a data-analysis pre-registration and no linked `analysis-plan:<slug>`
exists, recommend `/science:plan-analysis` when any of these are underspecified:
input QA, preprocessing/normalization checks, independent unit, estimand,
power/resolution limit, or sensitivity-arbitration rule. The recommendation is
advisory, not a hard dependency.
```

- [ ] **Step 5: Update `commands/status.md`**

Under `### 8. Next Steps`, add:

```markdown
- If active hypothesis, inquiry, or task work implies a data analysis but no
  linked `analysis-plan:<slug>` or `doc/plans/*-analysis-plan.md` exists,
  suggest `/science:plan-analysis` before pre-registration or pipeline planning.
```

- [ ] **Step 6: Update `commands/next-steps.md`**

Under `### 3c. Task Tracking Gaps`, add:

```markdown
Scan active analysis-facing tasks and inquiries for linked `analysis-plan:<slug>`
artifacts. If none exists and the task is about running, validating, or
pre-registering a data analysis, add a recommended next action to run
`/science:plan-analysis`. Check `doc/plans/*-analysis-plan.md` before
recommending a new one.
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_command_docs.py::test_plan_analysis_is_integrated_with_neighbor_commands -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add commands/plan-pipeline.md commands/pre-register.md commands/status.md commands/next-steps.md science-tool/tests/test_command_docs.py
git commit -m "docs(commands): route analysis readiness gaps to plan-analysis"
```

## Task 4: Generate Codex Skill And Validate Output

**Files:**
- Create: `codex-skills/science-plan-analysis/SKILL.md`
- Modify: `science-tool/tests/test_codex_skills.py`

- [ ] **Step 1: Add failing generated-skill test**

Append this test to `science-tool/tests/test_codex_skills.py`:

```python
def test_plan_analysis_generated_skill_mentions_index_and_readiness() -> None:
    text = _read_skill("science-plan-analysis")

    expected_strings = (
        "name: science-plan-analysis",
        "skills/INDEX.md",
        "doc/plans/YYYY-MM-DD-<slug>-analysis-plan.md",
        "Readiness Decision",
        "science-tool feedback add",
    )
    for expected in expected_strings:
        assert expected in text
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_codex_skills.py::test_plan_analysis_generated_skill_mentions_index_and_readiness -v
```

Expected: FAIL because `codex-skills/science-plan-analysis/SKILL.md` does not exist.

- [ ] **Step 3: Regenerate Codex skills**

Run:

```bash
uv run python scripts/generate_codex_skills.py
```

Expected: creates `codex-skills/science-plan-analysis/SKILL.md`.

- [ ] **Step 4: Run the generated-skill test**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_codex_skills.py::test_plan_analysis_generated_skill_mentions_index_and_readiness -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add codex-skills/science-plan-analysis/SKILL.md science-tool/tests/test_codex_skills.py
git commit -m "chore(codex-skills): generate plan-analysis skill"
```

## Task 5: Final Verification

**Files:**
- No planned edits.

- [ ] **Step 1: Run focused command and generated-skill tests**

Run:

```bash
cd science-tool && uv run --frozen pytest tests/test_command_docs.py tests/test_codex_skills.py -v
```

Expected: existing baseline failures in `tests/test_codex_skills.py` and `tests/test_command_docs.py` may remain; the new plan-analysis tests must pass. If a new plan-analysis test fails, fix it before continuing.

- [ ] **Step 2: Run skills lint**

Run:

```bash
cd science-tool && uv run --frozen science-tool skills lint --root ../skills --format text
```

Expected: exit 0.

- [ ] **Step 3: Run final status check**

Run:

```bash
git status --short
```

Expected: clean worktree.

# Aspect-Based Research Framework

## Problem

The science tool's commands and templates assume a one-size-fits-all project structure. Feedback from two projects (seq-feats, natural-systems-guide) across ~25 invocations reveals systematic friction:

- **Forced sections:** "Causal Model Implications" was marked "not applicable" 11 consecutive times in a non-causal project. "Hypothesis Evaluation" table had "no formal hypotheses" entries repeatedly.
- **Missing sections:** No natural place for sub-group analysis, tooling/implementation resources, metric invalidation findings, approach comparisons, or user-contributed insights.
- **Overlapping sections:** "Alternative Explanations / Confounders" collapsed into "Critical Analysis" in 4+ discuss invocations when the topic was methodological rather than empirical.
- **Incomplete signal classification:** The 4 categories (strong/suggestive/null/ambiguous) don't cover "the measurement tool is broken" or "structure observed but not statistically testable."

## Design

### Core concept: Aspects as composable mixins

Instead of a single project type, projects declare a list of **aspects** — composable mixins that contribute sections, signal categories, and guidance to the framework's commands and templates.

```yaml
# science.yaml
aspects:
  - causal-modeling
  - hypothesis-testing
  - computational-analysis
```

Aspects compose by contributing whole sections. No aspect is required. Projects add/remove aspects as they evolve.

### Aspect file structure

Lives in the plugin alongside commands/skills/templates:

```
aspects/
  causal-modeling/
    causal-modeling.md
  hypothesis-testing/
    hypothesis-testing.md
  computational-analysis/
    computational-analysis.md
  software-development/
    software-development.md
```

Nested directories prepare for future decomposition (e.g., `computational-analysis/benchmarks.md`) without adding complexity now.

### Aspect file format

Each aspect file declares what it contributes, organized by command:

```markdown
---
name: <aspect-name>
description: <one-line description>
---

# <Aspect Name>

<Brief description of when this aspect applies.>

## interpret-results

### Additional section: <Section Title>

(insert after: <existing section name>)

<Section content and guidance.>

### Additional workflow

<Extra workflow steps for this command.>

## discuss

### Additional guidance

<Extra guidance for discussions in this aspect.>

## Signal categories

- **Category** -- definition

## Available commands

- `command-name` -- when to use it
```

### Naming convention

Aspects follow `<descriptor>-<noun>` pattern using recognizable scientific/engineering terms:

- `causal-modeling`
- `hypothesis-testing`
- `computational-analysis`
- `software-development`

### Composition rules

- Aspects contribute **whole sections**, not fragments within sections.
- Sections are appended in the order aspects appear in `science.yaml`.
- No conflict resolution needed at this level; if aspects overlap, their sections simply coexist.
- Future evolution may introduce finer-grained injection points if needed.

### Future: Hierarchical aspects

Aspects can decompose over time:

```
computational-analysis/
  computational-analysis.md    # top-level
  benchmarks.md                # sub-aspect
  notebooks.md                 # sub-aspect
  pipelines.md                 # sub-aspect
```

Domain-specific aspects (physics, biology, bioinformatics) could form a parallel hierarchy. The current flat list in `science.yaml` supports this without schema changes.

## Changes

### 1. Command preamble update

`references/command-preamble.md` gains two steps:

**Aspect loading:** Read `aspects` from `science.yaml`, load each `aspects/<name>/<name>.md`, incorporate their sections and guidance.

**Aspect detection:** After loading, scan for structural signals suggesting aspects the project could benefit from but hasn't declared:

| Signal | Suggests |
|---|---|
| Files in `specs/hypotheses/` | `hypothesis-testing` |
| Files in `models/` (DAG files) | `causal-modeling` |
| Pipelines, notebooks, benchmark scripts in code dir | `computational-analysis` |
| Package manifests (pyproject.toml, package.json, Cargo.toml) | `software-development` |

If a signal is detected and the corresponding aspect isn't loaded, prompt the user before proceeding. Only check once per invocation; don't re-prompt for previously declined aspects.

### 2. Core template changes

**`templates/interpretation.md`** -- core becomes:

| Section | Status |
|---|---|
| Findings Summary (with signal classification) | Keep (always) |
| Evidence vs. Open Questions | New (replaces formal Hypothesis Evaluation -- lighter, works with or without formal hypotheses) |
| New Questions Raised | Keep (always) |
| Limitations & Caveats | Keep (always) |
| Additional Observations | New (catch-all for sub-group analysis, metric concerns, etc.) |
| Updated Priorities | Keep (always) |

Removed from core:
- Hypothesis Evaluation table (with IDs, status transitions) -> `hypothesis-testing` aspect
- Causal Model Implications -> `causal-modeling` aspect

**`templates/discussion.md`** -- merge "Critical Analysis" and "Alternative Explanations / Confounders" into a single **"Critical Analysis"** section:

> Strengths, weaknesses, assumptions, and likely failure modes. Include alternative explanations and confounding factors. If the alternatives are central to the analysis (e.g., revising an existing claim, evaluating a methodological decision), integrate them directly rather than splitting artificially.

**`templates/background-topic.md`** -- make `datasets` field optional with comment.

### 3. Signal classification expansion

Core categories (always available):

- **Strong** -- clear, replicated, large effect
- **Suggestive** -- directional but uncertain
- **Null** -- no effect detected
- **Ambiguous** -- multiple interpretations possible
- **Methodological** -- finding about the evaluation framework itself, not the phenomenon

Aspect-contributed:

- `computational-analysis` adds **Descriptive** -- structure observed but not statistically testable
- `causal-modeling` adds **Confounded** -- effect present but likely due to unmeasured variable

### 4. Initial aspect definitions

| Aspect | Sections it adds | Signal categories | Commands it enables |
|---|---|---|---|
| `causal-modeling` | Causal Model Implications (interpret), causal discussion guidance (discuss) | Confounded | build-dag, sketch-model, specify-model, critique-approach |
| `hypothesis-testing` | Formal Hypothesis Evaluation table (interpret), hypothesis status transitions | -- | add-hypothesis |
| `computational-analysis` | Sub-group Analysis (interpret, optional), computational methodology notes | Descriptive | -- |
| `software-development` | Tooling & Implementation (research-topic), architecture decisions | -- | -- |

### 5. Meta-feedback improvements

- Add `interpret-results` to the official feedback-collecting commands (it already collects feedback but wasn't in the original plan).
- Add 5th optional category: **"Suggested improvement"** -- concrete proposal for fixing friction. Agents often have clear ideas that currently get buried in friction descriptions.
- Encourage noting recurrence (e.g., "7th not applicable") to surface patterns needing systematic fixes.
- Add **aspect fit check** to the process reflection step: after writing feedback, consider whether the current aspects are the right fit — suggest additions if sections were missing, removals if aspect-contributed sections were consistently skipped or boilerplate.

## Implementation order

1. Create `aspects/` directory and the 4 initial aspect files
2. Update `references/command-preamble.md` with aspect loading step
3. Update `templates/interpretation.md` (core slimming)
4. Update `templates/discussion.md` (merge overlapping sections)
5. Update `templates/background-topic.md` (optional datasets)
6. Update `commands/interpret-results.md` (reference aspects, expanded signal categories)
7. Update `commands/discuss.md` (reference aspects, merged section guidance)
8. Update `commands/research-topic.md` (reference aspects)
9. Update feedback sections in all commands (add "Suggested improvement" category, recurrence note)
10. Update `docs/plans/2026-03-07-meta-feedback-design.md` to reference this design
11. Update `references/project-structure.md` to document aspects

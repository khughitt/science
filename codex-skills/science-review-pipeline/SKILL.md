---
name: science-review-pipeline
description: "Critically review a pipeline plan against an evidence rubric. Checks evidence coverage, assumption validity, data availability, identifiability, reproducibility, validation criteria, and scope. Use when the user wants to review, audit, or check a pipeline before implementation. Also use when the user says \"review pipeline\", \"check my plan\", \"audit assumptions\", or \"is this ready\". Also use when the user explicitly asks for `science-review-pipeline` or references `/science:review-pipeline`."
---

# Review Pipeline

Converted from Claude command `/science:review-pipeline`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each aspect, read `aspects/<name>/<name>.md`.
   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

> **Prerequisites:**
> - Load the `knowledge-graph` skill
> - Load the `research-methodology` skill
> - Read the `discussant` role prompt from `prompts/roles/discussant.md` (if available)

## Overview

This command performs a systematic review of an inquiry and its pipeline plan. It operates as a critical discussant — looking for weaknesses, missing evidence, and unjustified assumptions.

The review is NOT a rubber stamp. It should surface problems the user hasn't considered.

## Tool invocation

All `science-tool` commands below use this pattern:

```bash
uv run science-tool <command>
```

## Rules

- **MUST** run structural validation first (`inquiry validate`)
- **MUST** evaluate all 9 rubric dimensions
- **MUST** be critical — surface weaknesses, don't just confirm the plan is good
- **MUST** provide specific, actionable recommendations for each issue
- **MUST** save review report to `doc/inquiries/<slug>-review.md`
- **SHOULD** cross-reference claims against existing literature (LLM knowledge + web search)
- **MUST NOT** change the inquiry or plan — only report findings

## Workflow

### Step 1: Load inquiry and plan

```bash
science-tool inquiry show "<slug>" --format table
science-tool inquiry validate "<slug>" --format json
```

Also read:
- `doc/inquiries/<slug>.md` — inquiry document
- `doc/plans/*<slug>*` — implementation plan (if exists)
- `specs/scope-boundaries.md` — project scope

**Sub-plan handling:** If the plan being reviewed is a sub-plan of a larger inquiry (e.g., Tasks 2-3 of a broader inquiry), the inquiry-level validation may pass trivially. In this case:
- Apply the rubric dimensions to the plan's internal consistency, not just the parent inquiry's structure.
- Dimensions 1 (Evidence Coverage) and 7 (Scope Check) may be marked **N/A — inherited from parent plan** if the parent plan has already passed review on these dimensions. Reference the parent plan's review document.
- Focus review effort on dimensions specific to the sub-plan: validation criteria (Dim 6), assumption audit (Dim 2), integration boundaries (Dim 8).

### Step 2: Evaluate each rubric dimension

#### Dimension 1: Evidence Coverage

- Does every non-trivial parameter have `sci:paramSource` and `sci:paramRef`?
- Are there `[UNVERIFIED]` markers in the inquiry doc?
- Do any `sci:Unknown` nodes remain?

**Scoring:** PASS (all params sourced), WARN (some missing refs), FAIL (unsourced causal claims)

#### Dimension 2: Assumption Audit

For each `sci:Assumption` and `scic:causes` edge:
- Is the assumption justified with evidence?
- Could confounders explain the relationship?
- Is the causal direction justified?

**Scoring:** PASS (all justified), WARN (minor gaps), FAIL (unjustified causal claims)

#### Dimension 3: Data Availability

For each `BoundaryIn` node:
- Is the data source specified?
- Is the data actually accessible?
- Is the format specified?

**Scoring:** PASS (all accessible), WARN (some unspecified), FAIL (inaccessible sources)

#### Dimension 4: Identifiability

- Is every `BoundaryOut` reachable from `BoundaryIn` via directed edges?
- Are there disconnected components?
- Can the target hypothesis actually be tested?

**Scoring:** PASS (fully connected), FAIL (disconnected or unreachable)

#### Dimension 5: Reproducibility

- Are random seeds specified?
- Are software versions pinned?
- Are environments reproducible?

**Scoring:** PASS (fully specified), WARN (partial), FAIL (no reproducibility measures)

#### Dimension 6: Validation Criteria

- Does every `sci:Transformation` have a `sci:validatedBy` check?
- Is the check specific enough to catch failures?

**Scoring:** PASS (all steps validated), WARN (gaps), FAIL (no validation)

#### Dimension 7: Scope Check

- Does the inquiry stay within `specs/scope-boundaries.md`?
- Are there scope-creep risks?

**Scoring:** PASS (in scope), WARN (borderline), FAIL (out of scope)

#### Dimension 8: Integration Boundary Check

- Does the plan's output format match the consuming module's input format?
- Check tensor dimensions, data schemas, and API contracts across module boundaries
- Verify that intermediate representations are compatible between pipeline stages
- Read the actual code at integration points (model input shapes, data loader expectations, etc.)

**Scoring:** PASS (all boundaries verified), WARN (some unchecked), FAIL (mismatches found)

#### Dimension 9: Manifest Completeness

- Does the workflow produce a `datapackage.json` manifest in its output directory?
- Are all output resources listed?
- Are entity cross-references specified?
- Is provenance DAG included?

**Scoring:** PASS (complete manifest with resources + entities + provenance) /
WARN (manifest present but incomplete) / FAIL (no manifest generation)

### Step 3: Write review report

Save to `doc/inquiries/<slug>-review.md`:

```markdown
# Pipeline Review: {{label}}

- **Inquiry:** {{slug}}
- **Date:** {{date}}
- **Overall:** {{PASS|WARN|FAIL}}

## Summary

{{2-3 sentence assessment}}

## Rubric Results

| Dimension | Score | Issues |
|---|---|---|
| Evidence coverage | {{score}} | {{brief}} |
| Assumption audit | {{score}} | {{brief}} |
| Data availability | {{score}} | {{brief}} |
| Identifiability | {{score}} | {{brief}} |
| Reproducibility | {{score}} | {{brief}} |
| Validation criteria | {{score}} | {{brief}} |
| Scope check | {{score}} | {{brief}} |
| Integration boundaries | {{score}} | {{brief}} |
| Manifest completeness | {{score}} | {{brief}} |

## Detailed Findings

### {{Dimension with issues}}

{{Specific findings with actionable recommendations}}

## Recommendations

1. {{Highest priority action}}
2. {{Next priority}}

## Strengths

{{What's done well}}
```

Update the inquiry status to `reviewed`.

### Step 4: Present to user

Show the summary table and top recommendations. Ask if they want to:
1. Address the findings (modify inquiry/plan)
2. Accept the risks and proceed
3. Discuss specific findings in more depth

## Important Notes

- **Be genuinely critical.** The value is in finding problems before implementation.
- **Cross-check claims.** Use LLM knowledge and web search to verify factual claims.
- **Look for circular reasoning.** If A justifies B and B justifies A, flag it.
- **Consider failure modes.** For each transformation: what happens if it fails?

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:review-pipeline" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead

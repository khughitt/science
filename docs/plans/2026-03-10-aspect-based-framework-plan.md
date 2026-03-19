# Aspect-Based Research Framework Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add composable aspect mixins to the Science framework so commands and templates adapt to project characteristics instead of forcing one-size-fits-all sections.

**Architecture:** Projects declare `aspects: [causal-modeling, ...]` in `science.yaml`. Each aspect is defined in `aspects/<name>/<name>.md` and contributes whole sections, signal categories, and guidance to commands. The command preamble loads relevant aspects; individual commands don't need aspect-specific logic.

**Tech Stack:** Markdown (prompts, templates, aspect definitions), YAML (science.yaml schema)

---

## Chunk 1: Foundation — Aspect Files and Schema

### Task 1: Create aspect directory structure

**Files:**
- Create: `aspects/causal-modeling/causal-modeling.md`
- Create: `aspects/hypothesis-testing/hypothesis-testing.md`
- Create: `aspects/computational-analysis/computational-analysis.md`
- Create: `aspects/software-development/software-development.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p aspects/causal-modeling aspects/hypothesis-testing aspects/computational-analysis aspects/software-development
```

- [ ] **Step 2: Write `aspects/causal-modeling/causal-modeling.md`**

```markdown
---
name: causal-modeling
description: Causal inference and DAG-based reasoning
---

# Causal Modeling

Projects studying cause-effect relationships through directed acyclic graphs and structural causal models.

## interpret-results

### Additional section: Causal Model Implications

(insert after: Evidence vs. Open Questions)

If a causal inquiry exists:
- Do results suggest missing variables or edges?
- Should any edges be removed or reversed?
- Do effect sizes inform parameter estimates?
- Propose specific graph updates but do not execute them — list the `science-tool` commands that would make the changes.

If no causal model exists yet, note whether results suggest building one.

### Additional workflow

After evaluating findings against open questions, assess the causal model using the guidance above. Present proposed graph changes to the user before executing any `science-tool` commands.

## discuss

### Additional guidance

When discussing causal claims, explicitly consider:
- Reverse causation — could the effect cause the putative cause?
- Unmeasured confounders — what common causes might be missing?
- Selection bias — does the study design condition on a collider?
- Mediation vs direct effects — is the causal path fully specified?

## research-topic

### Additional guidance

When researching topics relevant to causal modeling, note:
- Known causal mechanisms and their evidence strength
- Common confounders in the domain
- Natural experiments or instrumental variables that could aid identification

## Signal categories

- **Confounded** — effect present but likely due to unmeasured variable

## Available commands

These commands become relevant with this aspect:
- `build-dag` — construct a causal DAG from variables and relationships
- `sketch-model` — sketch an informal causal model
- `specify-model` — formalize a causal model with parameters
- `critique-approach` — critically review a causal DAG inquiry
```

- [ ] **Step 3: Write `aspects/hypothesis-testing/hypothesis-testing.md`**

```markdown
---
name: hypothesis-testing
description: Formal hypothesis development, tracking, and evaluation
---

# Hypothesis Testing

Projects with formal, falsifiable hypotheses tracked through status transitions.

## interpret-results

### Additional section: Hypothesis Evaluation

(insert after: Evidence vs. Open Questions)

For each active hypothesis in `specs/hypotheses/`:
- Is it relevant to these results?
- If relevant: does the evidence support, refute, or leave it unchanged?
- Propose a status update if warranted: `proposed` → `supported` / `refuted` / `revised` / `under-investigation`
- If revising, draft the revised statement

Present the evaluation table to the user. **Do not update hypothesis files until the user confirms each proposed change.**

| Hypothesis | Prior Status | Evidence Summary | Proposed Status | Confidence |
|---|---|---|---|---|
| H01 — short title | proposed | brief evidence | supported / refuted / revised / unchanged | high / moderate / low |

### Additional workflow

After writing the interpretation document:
- Update hypothesis files in `specs/hypotheses/` with confirmed status changes and new evidence in the "Current Evidence" section.

## discuss

### Additional guidance

When discussing hypotheses:
- Reference the specific hypothesis ID and current status
- Distinguish between evidence that updates the hypothesis vs evidence that refines it
- Consider whether the hypothesis needs to be split into sub-hypotheses

## Signal categories

(none — uses core categories)

## Available commands

- `add-hypothesis` — develop and refine a new research hypothesis interactively
```

- [ ] **Step 4: Write `aspects/computational-analysis/computational-analysis.md`**

```markdown
---
name: computational-analysis
description: Computational and exploratory data analysis
---

# Computational Analysis

Projects involving computational experiments, exploratory analysis, benchmarks, or pipeline-driven results.

## interpret-results

### Additional section: Sub-group Analysis (optional)

(insert after: Additional Observations)

If results reveal sub-groups, clusters, or decompositions within the data:
- Characterize each sub-group with quantitative descriptors
- Compare sub-groups systematically (table format preferred)
- Note whether sub-groups are stable across methods or parameters
- Flag sub-groups that may be artifacts of the analysis method

Only include this section when decomposition results are present.

### Additional guidance

For computational/exploratory results:
- Distinguish between confirmatory analysis (testing a pre-specified hypothesis) and exploratory analysis (pattern discovery)
- When results are exploratory, note what would be needed to confirm the patterns
- For benchmark results, include baseline comparisons and report relative as well as absolute performance

## discuss

### Additional guidance

When discussing computational results:
- Consider whether findings are method-dependent (would a different algorithm produce the same pattern?)
- Distinguish between statistical artifacts and genuine structure
- For pipeline results, consider sensitivity to parameter choices

## research-topic

### Additional guidance

When researching computational methods or tools:
- Note implementation maturity and community adoption
- Compare alternative approaches systematically
- Include practical resources (libraries, frameworks, example code)

## Signal categories

- **Descriptive** — structure observed but not statistically testable (e.g., UMAP clusters, NMF factors, visualization patterns)
```

- [ ] **Step 5: Write `aspects/software-development/software-development.md`**

```markdown
---
name: software-development
description: Software engineering — applications, tools, and libraries
---

# Software Development

Projects that include building software artifacts (web apps, CLI tools, libraries, APIs).

## research-topic

### Additional section: Tooling & Implementation

(insert after: Relevance to This Project)

Practical resources for implementing or applying this topic:
- Libraries, frameworks, and tools
- Implementation patterns and best practices
- Example code or reference implementations
- Maturity level and community support

## interpret-results

### Additional guidance

When interpreting results related to software:
- Distinguish between correctness (does it work?) and quality (does it work well?)
- Note performance characteristics alongside functional results
- Consider whether results generalize across environments or configurations

## discuss

### Additional guidance

When discussing software design decisions:
- Consider maintainability and long-term evolution alongside correctness
- Evaluate trade-offs between simplicity and flexibility
- Note technical debt implications of each alternative

## Signal categories

(none — uses core categories)
```

- [ ] **Step 6: Commit aspect files**

```bash
git add aspects/
git commit -m "feat: add initial aspect definitions (causal-modeling, hypothesis-testing, computational-analysis, software-development)"
```

### Task 2: Update science.yaml schema

**Files:**
- Modify: `references/science-yaml-schema.md`

- [ ] **Step 1: Add `aspects` field to schema**

Add after the `paths:` section in the schema:

```yaml
# Optional — project aspects (composable mixins)
# Each aspect contributes additional sections, signal categories, and guidance to commands.
# See aspects/ directory for available aspects and what they provide.
aspects:                        # Default: [] (no aspects)
  - "string"                    # One of: causal-modeling, hypothesis-testing, computational-analysis, software-development
```

- [ ] **Step 2: Add aspects to the example sections**

Add `aspects:` to the basic example:

```yaml
aspects:
  - causal-modeling
  - hypothesis-testing
```

Add `aspects:` to the imported project example:

```yaml
aspects:
  - computational-analysis
  - software-development
```

- [ ] **Step 3: Commit**

```bash
git add references/science-yaml-schema.md
git commit -m "feat: add aspects field to science.yaml schema"
```

---

## Chunk 2: Core Mechanism — Preamble and Template Updates

### Task 3: Update command preamble to load aspects and detect aspect needs

**Files:**
- Modify: `references/command-preamble.md`

- [ ] **Step 1: Add aspect loading step**

Add as step 5 (after reading research-question.md):

```markdown
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each aspect, read `${CLAUDE_PLUGIN_ROOT}/aspects/<name>/<name>.md`.
   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
```

- [ ] **Step 2: Add aspect detection step**

Add as step 6 (after loading aspects):

```markdown
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `<specs_dir>/hypotheses/` | `hypothesis-testing` |
   | Files in `<models_dir>/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Pipeline files, notebooks, or benchmark scripts in `<code_dir>/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
```

- [ ] **Step 3: Commit**

```bash
git add references/command-preamble.md
git commit -m "feat: add aspect loading and detection to command preamble"
```

### Task 4: Update interpretation template

**Files:**
- Modify: `templates/interpretation.md`

- [ ] **Step 1: Replace current template with aspect-aware core**

Replace the full contents with:

```markdown
# Interpretation: {{Short Title}}

- **Date:** {{YYYY-MM-DD}}
- **Inquiry:** {{slug or "N/A"}}
- **Input:** {{path to results, notebook, or "prose description"}}

## Findings Summary

<!--
  Summarize key results. For each finding, classify signal strength.

  Core categories (always available):
  - Strong: clear, replicated, large effect
  - Suggestive: directional but uncertain
  - Null: no effect detected (important — record, don't discard)
  - Ambiguous: multiple interpretations possible
  - Methodological: finding about the evaluation framework itself, not the phenomenon

  Aspect-contributed categories (include if the project has the relevant aspect):
  - Descriptive (computational-analysis): structure observed but not statistically testable
  - Confounded (causal-modeling): effect present but likely due to unmeasured variable

  Include effect sizes and confidence intervals where available.
-->

## Evidence vs. Open Questions

<!--
  For each open question in doc/questions/:
  - Is it relevant to these results?
  - If relevant: does the evidence address, partially address, or leave it unchanged?
  - Note new constraints, refined scope, or resolved sub-questions

  This section works with or without formal hypotheses.
  If the project has the hypothesis-testing aspect, a formal Hypothesis Evaluation
  section will follow (contributed by that aspect).
-->

<!-- ASPECT SECTIONS INSERTED HERE -->
<!--
  Loaded aspects may contribute additional sections at this point.
  Follow the placement guidance in each aspect file.
-->

## New Questions Raised

<!--
  Questions that did not exist before these results.
  For each, note:
  - Priority (high / medium / low)
  - Type (empirical / methodological / theoretical)
  - Suggested approach to investigate
-->

## Limitations & Caveats

<!--
  What these results do NOT tell us.
  - Threats to internal validity (confounds, selection bias, measurement error)
  - Threats to external validity (generalizability, population differences)
  - Statistical limitations (power, multiple comparisons, model assumptions)
  - Data quality concerns
-->

## Additional Observations

<!--
  Catch-all for findings that don't fit neatly into other sections:
  - Sub-group or decomposition results
  - Control quality concerns
  - Metric or measurement validity issues
  - Unexpected patterns worth noting

  Skip this section if there's nothing to add.
-->

## Updated Priorities

<!--
  Given these findings, what changes in the research plan?
  - Tasks to add, reprioritize, or drop
  - Open questions to pursue further or set aside
  - Next commands to run (discuss, research-gaps, add-hypothesis, etc.)
-->
```

- [ ] **Step 2: Commit**

```bash
git add templates/interpretation.md
git commit -m "refactor: slim interpretation template to aspect-aware core"
```

### Task 5: Update discussion template

**Files:**
- Modify: `templates/discussion.md`

- [ ] **Step 1: Merge "Critical Analysis" and "Alternative Explanations / Confounders"**

Replace the current sections 3 and 4:

```markdown
## Critical Analysis

<Strengths, weaknesses, assumptions, and likely failure modes.
Include alternative explanations and confounding factors.
If the alternatives are central to the analysis (e.g., revising an existing claim
or evaluating a methodological decision), integrate them directly rather than
splitting into a separate section.>
```

Remove the separate `## Alternative Explanations / Confounders` section entirely.

- [ ] **Step 2: Commit**

```bash
git add templates/discussion.md
git commit -m "refactor: merge overlapping discussion sections into Critical Analysis"
```

### Task 6: Update background-topic template

**Files:**
- Modify: `templates/background-topic.md`

- [ ] **Step 1: Make datasets field optional**

Change the frontmatter `datasets: []` line to include a comment:

```yaml
datasets: []                    # omit if not applicable to this topic
```

- [ ] **Step 2: Commit**

```bash
git add templates/background-topic.md
git commit -m "fix: make datasets field optional in background-topic template"
```

---

## Chunk 3: Command Updates

### Task 7: Update interpret-results command

**Files:**
- Modify: `commands/interpret-results.md`

- [ ] **Step 1: Update the signal classification in Workflow section 1**

Replace the current signal classification list with the expanded version:

```markdown
- **Strong** — clear, replicated, large effect
- **Suggestive** — directional but uncertain
- **Null** — no effect detected (record this — it's informative)
- **Ambiguous** — multiple interpretations possible
- **Methodological** — finding about the evaluation framework itself, not the phenomenon (e.g., a metric is invalid, a baseline is inadequate)

Loaded aspects may contribute additional signal categories (e.g., **Descriptive** from `computational-analysis`, **Confounded** from `causal-modeling`). Check loaded aspect files for definitions.
```

- [ ] **Step 2: Replace Workflow section 2 (Evaluate hypotheses)**

Replace the current "Evaluate hypotheses" section with a lighter core:

```markdown
### 2. Evaluate against open questions

For each open question in `doc/questions/`:
- Is it relevant to these results?
- If relevant: does the evidence address, partially address, or leave it unchanged?
- Note new constraints, refined scope, or resolved sub-questions

If the project has the `hypothesis-testing` aspect, also perform the formal Hypothesis Evaluation contributed by that aspect.
```

- [ ] **Step 3: Replace Workflow section 3 (Assess causal model)**

Replace the current "Assess causal model" section with:

```markdown
### 3. Aspect-contributed analysis

Include any additional analysis sections contributed by loaded aspects (e.g., Causal Model Implications from `causal-modeling`, Hypothesis Evaluation table from `hypothesis-testing`, Sub-group Analysis from `computational-analysis`).

Follow the guidance in each aspect file for section content and placement.
```

- [ ] **Step 4: Update "After Writing" section**

Replace the current step 1 ("Update hypothesis files...") with:

```markdown
1. If the project has the `hypothesis-testing` aspect: update hypothesis files in `specs/hypotheses/` with confirmed status changes and new evidence.
```

- [ ] **Step 5: Commit**

```bash
git add commands/interpret-results.md
git commit -m "refactor: make interpret-results aspect-aware with expanded signal categories"
```

### Task 8: Update discuss command

**Files:**
- Modify: `commands/discuss.md`

- [ ] **Step 1: Update Writing Output sections**

Replace the current section list with:

```markdown
1. `## Focus`
2. `## Current Position`
3. `## Critical Analysis` (includes alternative explanations and confounders — see template)
4. `## Evidence Needed`
5. `## Prioritized Follow-Ups`
6. `## Synthesis` (include side-by-side summary in double-blind mode)
```

Remove the separate `## Alternative Explanations / Confounders` entry.

- [ ] **Step 2: Add aspect note to Standard mode**

Add after the standard mode steps:

```markdown
If loaded aspects contribute additional discussion guidance (e.g., causal reasoning checks from `causal-modeling`), incorporate that guidance into the critical analysis.
```

- [ ] **Step 3: Commit**

```bash
git add commands/discuss.md
git commit -m "refactor: make discuss command aspect-aware, merge overlapping sections"
```

### Task 9: Update research-topic command

**Files:**
- Modify: `commands/research-topic.md`

- [ ] **Step 1: Add aspect note to Writing section**

Add after "The output should include:":

```markdown
If loaded aspects contribute additional sections (e.g., Tooling & Implementation from `software-development`), include them after the core sections.
```

- [ ] **Step 2: Commit**

```bash
git add commands/research-topic.md
git commit -m "refactor: make research-topic command aspect-aware"
```

---

## Chunk 4: Feedback and Documentation

### Task 10: Update feedback sections across all commands

**Files:**
- Modify: `commands/interpret-results.md`
- Modify: `commands/discuss.md`
- Modify: `commands/research-topic.md`
- Modify: `commands/research-paper.md`
- Modify: `commands/add-hypothesis.md`
- Modify: `commands/research-gaps.md`
- Modify: `commands/critique-approach.md`

- [ ] **Step 1: Update the feedback entry format in all 7 commands**

In each command's "Process Reflection" section, replace the entry format block with:

~~~markdown
```markdown
## YYYY-MM-DD — <command-name>

**Template/structure friction:**
- Any section you left empty, filled with boilerplate, or that felt forced

**Missing capture:**
- Information you wanted to record but had no natural place for

**Guidance issues:**
- Command instructions that were confusing, contradictory, or didn't help

**Suggested improvement:**
- Concrete proposal for fixing any friction above (optional but encouraged)

**What worked well:**
- A section or instruction that genuinely improved the output
```
~~~

- [ ] **Step 2: Update the guidelines in all 7 commands**

Replace the guidelines block with:

```markdown
Guidelines:
- Be concrete and specific, not generic
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback
```

Keep the command-specific example in the first guideline bullet (each command has its own example). Only update the generic guidelines.

- [ ] **Step 3: Add aspect fit check to the reflection prompt in all 7 commands**

After the guidelines block in each command's "Process Reflection" section, add:

```markdown
Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [ ] **Step 4: Commit**

```bash
git add commands/interpret-results.md commands/discuss.md commands/research-topic.md commands/research-paper.md commands/add-hypothesis.md commands/research-gaps.md commands/critique-approach.md
git commit -m "feat: add 'suggested improvement' feedback category, recurrence guidance, and aspect fit check"
```

### Task 11: Update project-structure reference

**Files:**
- Modify: `references/project-structure.md`

- [ ] **Step 1: Add aspects directory to the directory listing**

Add after the `templates/` section:

```markdown
### `aspects/` — Project Aspects (Plugin-Level)

Composable mixins that adapt commands and templates to project characteristics.
Defined in the Science plugin, not in individual projects.

- `causal-modeling/causal-modeling.md` — causal inference, DAGs, structural models
- `hypothesis-testing/hypothesis-testing.md` — formal hypothesis tracking and evaluation
- `computational-analysis/computational-analysis.md` — exploratory analysis, benchmarks, pipelines
- `software-development/software-development.md` — applications, tools, libraries

Projects declare which aspects apply in `science.yaml`:

```yaml
aspects:
  - causal-modeling
  - computational-analysis
```

See `references/science-yaml-schema.md` for the schema and each aspect file for what it contributes.
```

- [ ] **Step 2: Commit**

```bash
git add references/project-structure.md
git commit -m "docs: document aspects directory in project-structure reference"
```

### Task 12: Update meta-feedback design doc

**Files:**
- Modify: `docs/plans/2026-03-07-meta-feedback-design.md`

- [ ] **Step 1: Add interpret-results to the command table**

Add `interpret-results` to the Tier 1 table:

```markdown
| `interpret-results` | interpretation template sections, signal classification, aspect-contributed sections |
```

- [ ] **Step 2: Add note about the aspect-based framework**

Add a section at the end:

```markdown
## Evolution: Aspect-Based Framework (2026-03-10)

The feedback system surfaced a systematic pattern: certain template sections are forced for projects
that don't need them. This led to the aspect-based framework design
(see `docs/plans/2026-03-10-aspect-based-framework.md`), which makes sections composable
based on project characteristics declared in `science.yaml`.

The feedback entry format was also updated:
- Added 5th category: **"Suggested improvement"** for concrete fix proposals
- Added recurrence guidance to surface patterns that need systematic fixes
```

- [ ] **Step 3: Update the entry format in the design doc**

Update the entry format block to include the new category:

```markdown
**Suggested improvement:**
- Concrete proposal for fixing any friction above (optional but encouraged)
```

- [ ] **Step 4: Commit**

```bash
git add docs/plans/2026-03-07-meta-feedback-design.md
git commit -m "docs: update meta-feedback design with interpret-results and aspect-based evolution"
```

### Task 13: Update CLAUDE.md template with aspects guidance

**Files:**
- Modify: `references/claude-md-template.md`

- [ ] **Step 1: Read the current template**

Read `references/claude-md-template.md` to understand its current structure.

- [ ] **Step 2: Add aspects guidance**

Add a section about aspects, noting that the project's `science.yaml` declares which aspects apply and that commands will automatically incorporate aspect-specific sections and guidance.

- [ ] **Step 3: Commit**

```bash
git add references/claude-md-template.md
git commit -m "docs: add aspects guidance to CLAUDE.md template"
```

### Task 14: Final validation

- [ ] **Step 1: Verify all aspect files exist and are well-formed**

```bash
ls -la aspects/*/
```

Verify 4 directories, each with one `.md` file.

- [ ] **Step 2: Verify cross-references**

Check that:
- `references/command-preamble.md` references `aspects/<name>/<name>.md`
- `references/science-yaml-schema.md` lists all 4 aspect names
- `references/project-structure.md` documents the aspects directory
- `templates/interpretation.md` references aspect insertion point
- All 7 command files have the updated feedback format

- [ ] **Step 3: Final commit (if any fixes needed)**

```bash
git add -A && git commit -m "fix: address validation issues in aspect framework"
```

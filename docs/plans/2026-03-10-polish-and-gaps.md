# Polish, Gaps & Future Directions Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix numbering bug in sketch-model, add Process Reflection to 6 research commands, add pre-registration prompt to plan-pipeline, and document future directions.

**Architecture:** All changes are markdown command files. Process Reflection sections follow the established pattern from `commands/pre-register.md`. No code changes.

**Tech Stack:** Markdown, YAML frontmatter, bash (validate.sh)

**Spec:** Review findings from the Reasoning & Coherence implementation (2026-03-10).

**Status: COMPLETE** — All 8 tasks executed and committed. Phase 2 (Frontmatter Standardization) also completed — see `2026-03-10-frontmatter-standardization.md`.

---

## Chunk 1: Quick Fixes and Process Reflection

### Task 1: Fix sketch-model Step 2 numbering overlap

**Files:**
- Modify: `commands/sketch-model.md`

The causal-mode questions (numbered 4-7) collide with the standard questions that follow (also numbered 4-5). Fix by making the standard questions unconditional continuations after the causal block.

- [x] **Step 1: Renumber the standard questions**

In `commands/sketch-model.md`, replace lines 101-107:

```markdown
4. **Data:** "What data do you have or could get?"
   - Existing datasets, databases, measurements
   - What's available vs. what would need to be generated?

5. **Unknowns:** "What are you unsure about?"
   - Create `sci:Unknown` nodes for gaps
   - "Is there something that might affect the outcome but you're not sure what?"
```

With:

```markdown
**For all modes, continue with:**

8. **Data:** "What data do you have or could get?"
   - Existing datasets, databases, measurements
   - What's available vs. what would need to be generated?

9. **Unknowns:** "What are you unsure about?"
   - Create `sci:Unknown` nodes for gaps
   - "Is there something that might affect the outcome but you're not sure what?"
```

This makes the numbering unambiguous: questions 1-3 are universal, 4-7 are causal-only (skipped in non-causal mode), 8-9 are universal again. The gap in numbering for non-causal mode is acceptable — it signals that questions 4-7 exist but were skipped.

- [x] **Step 2: Commit**

```bash
git add commands/sketch-model.md
git commit -m "fix: resolve question numbering overlap in sketch-model causal mode"
```

---

### Task 2: Add pre-registration suggestion to plan-pipeline

**Files:**
- Modify: `commands/plan-pipeline.md`

- [x] **Step 1: Add pre-registration check to Step 6 suggestions**

In `commands/plan-pipeline.md`, replace the Step 6 content:

```markdown
### Step 6: Suggest next steps

1. `/science:review-pipeline <slug>` — get critical review before implementation
2. Execute the plan using `superpowers:executing-plans`
3. `/science:discuss` — discuss specific aspects of the plan
```

With:

```markdown
### Step 6: Suggest next steps

1. If no pre-registration exists for the target hypothesis, suggest: `/science:pre-register` — to formalize expectations before running the analysis
2. `/science:review-pipeline <slug>` — get critical review before implementation
3. Execute the plan using `superpowers:executing-plans`
4. `/science:discuss` — discuss specific aspects of the plan
```

- [x] **Step 2: Commit**

```bash
git add commands/plan-pipeline.md
git commit -m "feat: suggest pre-registration in plan-pipeline next steps"
```

---

### Task 3: Add Process Reflection to sketch-model

**Files:**
- Modify: `commands/sketch-model.md`

- [x] **Step 1: Add Process Reflection section**

In `commands/sketch-model.md`, append after the `## Important Notes` section (after the last bullet):

```markdown

## Process Reflection

Reflect on the **sketch workflow** and the **interactive conversation** process.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — sketch-model

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

Guidelines:
- Be concrete and specific, not generic ("causal mode detection was ambiguous when the user said X" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [x] **Step 2: Commit**

```bash
git add commands/sketch-model.md
git commit -m "feat: add process reflection to sketch-model"
```

---

### Task 4: Add Process Reflection to specify-model

**Files:**
- Modify: `commands/specify-model.md`

- [x] **Step 1: Add Process Reflection section**

In `commands/specify-model.md`, append after the `## Important Notes` section (after the last bullet):

```markdown

## Process Reflection

Reflect on the **specification workflow** and the **evidence provenance** discipline.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — specify-model

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

Guidelines:
- Be concrete and specific, not generic ("provenance was hard to add for edges based on domain knowledge rather than papers" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [x] **Step 2: Commit**

```bash
git add commands/specify-model.md
git commit -m "feat: add process reflection to specify-model"
```

---

### Task 5: Add Process Reflection to plan-pipeline

**Files:**
- Modify: `commands/plan-pipeline.md`

- [x] **Step 1: Add Process Reflection section**

In `commands/plan-pipeline.md`, append after the `## Important Notes` section (after the last bullet):

```markdown

## Process Reflection

Reflect on the **pipeline planning workflow** and the **task decomposition** process.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — plan-pipeline

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

Guidelines:
- Be concrete and specific, not generic ("QA checkpoints were hard to define without knowing the data schema" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [x] **Step 2: Commit**

```bash
git add commands/plan-pipeline.md
git commit -m "feat: add process reflection to plan-pipeline"
```

---

### Task 6: Add Process Reflection to review-pipeline

**Files:**
- Modify: `commands/review-pipeline.md`

- [x] **Step 1: Add Process Reflection section**

In `commands/review-pipeline.md`, append after the `## Important Notes` section (after the last bullet):

```markdown

## Process Reflection

Reflect on the **review rubric** and the **audit workflow**.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — review-pipeline

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

Guidelines:
- Be concrete and specific, not generic ("QA coverage rubric was hard to score without seeing actual assertion code" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [x] **Step 2: Commit**

```bash
git add commands/review-pipeline.md
git commit -m "feat: add process reflection to review-pipeline"
```

---

### Task 7: Add Process Reflection to search-literature

**Files:**
- Modify: `commands/search-literature.md`

- [x] **Step 1: Add Process Reflection section**

In `commands/search-literature.md`, append after the last line of the `## After Search` section (after the commit step):

```markdown

## Process Reflection

Reflect on the **search strategy** and the **relevance ranking** workflow.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — search-literature

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

Guidelines:
- Be concrete and specific, not generic ("OpenAlex results were hard to rank without abstracts" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [x] **Step 2: Commit**

```bash
git add commands/search-literature.md
git commit -m "feat: add process reflection to search-literature"
```

---

### Task 8: Add Process Reflection to find-datasets

**Files:**
- Modify: `commands/find-datasets.md`

- [x] **Step 1: Add Process Reflection section**

In `commands/find-datasets.md`, append after the `## Output Summary` section (after the last line about data gaps):

```markdown

## Process Reflection

Reflect on the **dataset discovery** workflow and the **relevance ranking** process.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — find-datasets

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

Guidelines:
- Be concrete and specific, not generic ("dataset size estimates were unavailable from the API" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [x] **Step 2: Commit**

```bash
git add commands/find-datasets.md
git commit -m "feat: add process reflection to find-datasets"
```

---

## Deferred Work

### ~~Phase 2: Frontmatter Standardization (spec 3.3)~~ — DONE

Completed in separate plan: `2026-03-10-frontmatter-standardization.md`. Migrated 3 templates (hypothesis, discussion, interpretation), removed 2 obsolete templates (open-question, data-source), added cross-reference validation to validate.sh. `inquiry.md` deferred (requires Python code change to `store.py`).

### Phase 3: Generalize critique-approach to non-causal models

Currently `critique-approach` is causal-DAG-specific. The sensitivity analysis added in the Reasoning & Coherence implementation uses causal terminology (confounders, causal edges). But the spec envisions sensitivity analysis for conceptual models too ("assumption-focused analysis" vs "confounder-focused analysis").

**Why defer:** No project has needed non-causal critique yet. The Process Reflection feedback loop will surface this need when it arises.

**When to do it:**
- When a project without `causal-modeling` aspect tries to use `critique-approach`
- When Process Reflection feedback from `specify-model` or `sketch-model` suggests the critique step is missing

**Scope:**
- Generalize `critique-approach` description to trigger on non-causal models
- Add conditional sections: causal mode gets confounder/identifiability analysis; conceptual mode gets assumption/boundary analysis
- Sensitivity analysis language adapts: "causal edges" → "relationships"; "confounders" → "hidden mediators or moderators"
- May require splitting the command or using aspect-conditional sections

### Phase 4: Aspect Contributions for New Commands

The new reasoning commands (`pre-register`, `compare-hypotheses`, `bias-audit`) don't have aspect-specific sections yet. Potential additions:

- **`computational-analysis` + `pre-register`:** Data splitting strategy, test set contamination checks, computational reproducibility plan
- **`computational-analysis` + `bias-audit`:** Algorithmic bias, data leakage detection, overfitting checks
- **`causal-modeling` + `compare-hypotheses`:** Compare causal mechanisms (not just predictions), compare implied DAG structures, check whether hypotheses imply different adjustment sets

**Why defer:** Let usage feedback (Process Reflection) surface which aspects are actually needed. Speculative aspect contributions add complexity without proven value.

## Future Directions

These are larger conceptual additions that go beyond polish. They should be brainstormed and spec'd separately if pursued.

### Evidence Strength Registry

`compare-hypotheses` rates evidence as Strong/Suggestive/Weak, but this rating lives only in the comparison document. A lightweight evidence catalog — claims + sources + strength ratings — would make comparisons, audits, and interpretations more rigorous.

**Possible shape:** A `doc/evidence/` directory or entries in the knowledge graph with `confidence` attributes. Each claim links to its source (paper, dataset, prior result) and carries a strength rating. Commands like `compare-hypotheses` and `bias-audit` would read from this catalog instead of re-assessing evidence each time.

**Trigger:** When a project runs multiple comparisons or audits and the evidence assessments drift or contradict each other.

### Longitudinal Bias Tracking

`bias-audit` produces point-in-time snapshots. Over a long project, tracking how bias ratings change (did confirmation bias go from "not detected" to "possible" to "likely"?) would surface trends and catch slow drift.

**Possible shape:** `bias-audit` reads prior audits and includes a "Trend" column in the summary. Or a dedicated `/science:bias-trends` command that synthesizes across multiple audits.

**Trigger:** When a project has 3+ bias audits and the user asks "are we getting worse?"

### Power Analysis / Sample Size Reasoning

`pre-register` asks "Is the analysis sufficiently powered?" but there's no structured way to work through this. For computational/statistical projects, a power analysis tool would help formalize sample size decisions.

**Possible shape:** A section in `pre-register` (gated by `computational-analysis` aspect) that walks through effect size, significance level, power target, and required sample size. Or a separate command for projects where power analysis is central.

**Trigger:** When Process Reflection from `pre-register` repeatedly flags the power question as hard to answer.

### Replication Tracking

When results are reproduced or fail to reproduce, tracking this systematically. Currently `interpret-results` can note replication, but there's no structured mechanism.

**Possible shape:** A `replicated_by` / `failed_replication` field in interpretation frontmatter. `status` command surfaces replication status. `bias-audit` flags unreplicated key findings.

**Trigger:** When a project has multiple analysis rounds that revisit the same question.

### Meta-analysis Support

When multiple studies/analyses address the same question, synthesizing across them. Goes beyond `compare-hypotheses` (which compares explanations) to compare quantitative findings.

**Possible shape:** A `/science:synthesize` command that reads multiple interpretation documents for the same hypothesis and produces a summary of effect sizes, consistency, and overall conclusion. Likely gated by `computational-analysis` aspect.

**Trigger:** When a project has 5+ interpretations addressing overlapping hypotheses.

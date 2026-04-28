# Skill Feedback Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address ~28 unresolved skill feedback items across 11 files in the science repo (commands, templates).

**Architecture:** Pure markdown edits to command and template files. No code, no tests — these are prompt/guidance documents. Each task modifies one or two related files.

**Spec:** `docs/superpowers/specs/2026-03-25-skill-feedback-triage-design.md`

**Note:** Item 7a (bias-audit confound severity matrix) is already implemented at `commands/bias-audit.md:89-95`. Removed from plan.

---

### Task 1: interpret-results command — signal classification and evidence quality

**Files:**
- Modify: `commands/interpret-results.md:54-106`

- [ ] **Step 1: Add "descriptive" to signal classification list (line 62)**

Find the classification list at line 57-62 and add `descriptive`:

```markdown
### 1. Summarize The Findings

Extract the main findings and classify each as:
- `strong`
- `suggestive`
- `null`
- `ambiguous`
- `methodological`
- `descriptive` — structural or qualitative findings from exploratory/visualization analyses where statistical testing is not applicable (e.g., UMAP cluster structure, k-mer landscape patterns). Distinct from `suggestive`: the finding is qualitative by nature, not merely weak.
```

- [ ] **Step 2: Expand Step 4 evidence quality checklist (lines 96-106)**

Replace the existing terse bullets at lines 98-104 with more specific checks:

```markdown
### 4. Check Evidence Quality

Before updating beliefs, check:
- **Control uniqueness:** are controls distinct from test samples? No duplicate sequences, no shared samples across conditions
- **Dimensionality:** do embedding sizes, feature counts, and output shapes match expectations?
- **Sample counts:** do they match the experimental design? Spot-check against the data source
- **Data quality issues:** flag any anomalies discovered during interpretation as findings with signal strength `methodological`
- whether the result is confirmatory or exploratory
- whether the result is independent of prior supporting evidence or largely redundant
- whether it adds empirical support to a claim that previously had only literature or simulation support

If the finding is fragile, say so explicitly.

**Suspiciously good results:** When results substantially exceed pre-registered upper bounds (observed >> expected), do not accept them uncritically. Before proceeding:
- Enumerate plausible inflators: confounds, data leakage, overfitting, control inadequacy
- Reference the pre-registration document (in `doc/meta/pre-registration-*.md`) and compare observed vs. expected range explicitly
- State whether the result survives scrutiny or needs additional verification
```

- [ ] **Step 3: Verify the edit reads correctly**

Read `commands/interpret-results.md` lines 54-120 and confirm the new content integrates cleanly with surrounding steps.

- [ ] **Step 4: Commit**

```bash
git add commands/interpret-results.md
git commit -m "interpret-results: add descriptive signal category, expand evidence quality checks"
```

---

### Task 2: interpret-results command — adaptive terminology, prior findings, modes

**Files:**
- Modify: `commands/interpret-results.md:44-50` (Modes section)
- Modify: `commands/interpret-results.md:162-174` (Writing section)

- [ ] **Step 1: Add cross-referencing subsection after Modes list (after line 50)**

After the existing Dev mode bullet (line 50), add:

```markdown
### Cross-Referencing Prior Interpretations

When interpreting multiple tasks jointly or building on a prior interpretation, list which earlier interpretation documents this one extends or supersedes using the `prior_interpretations` frontmatter field.

- **Combined interpretations:** When interpreting 2+ tasks as a single arc, list any prior single-task interpretations that this combined document supersedes. The prior documents remain for provenance; the combined one is canonical for downstream reference.
- **Update mode:** When updating an existing interpretation with new evidence, reference the prior version's ID.

This creates a provenance chain across interpretation documents.
```

- [ ] **Step 2: Add adaptive terminology note in Writing section (after line 164)**

After "Follow `templates/interpretation.md`." add:

```markdown
If the project uses open questions rather than formal hypotheses, adapt section headers in the output document accordingly — e.g., "Question-Level Implications" instead of "Hypothesis-Level Implications". Evaluate against questions in `doc/questions/` rather than hypothesis files in `specs/hypotheses/`.
```

- [ ] **Step 3: Verify both edits**

Read `commands/interpret-results.md` lines 44-55 and 162-170 to confirm clean integration.

- [ ] **Step 4: Commit**

```bash
git add commands/interpret-results.md
git commit -m "interpret-results: add prior-findings cross-ref, adaptive hypothesis/question terminology"
```

---

### Task 3: interpretation template

**Files:**
- Modify: `templates/interpretation.md`

- [ ] **Step 1: Add `prior_interpretations` to frontmatter (after line 12)**

After the `workflow_run` field, add:

```yaml
prior_interpretations: []  # optional: interpretation IDs this document extends or supersedes
```

- [ ] **Step 2: Add "Data Quality Checks" section (after line 33, between Evidence Quality and Claim-Level Updates)**

After the Evidence Quality closing comment `-->`, add:

```markdown
## Data Quality Checks

<!-- Any data quality concerns discovered during interpretation?
- Control uniqueness: are controls distinct from test samples?
- Sample counts: do they match the experimental design?
- Dimensionality: do embedding sizes / feature counts match expectations?
- Unexpected duplicates or anomalies?

If no issues found, note "No data quality concerns identified."
Flag any issues as findings with signal strength "methodological". -->
```

- [ ] **Step 3: Add adaptive terminology hint to Hypothesis-Level Implications (line 45)**

Update the existing comment at lines 45-50:

```markdown
## Hypothesis-Level Implications

<!-- How do the claim-level updates affect the broader hypothesis?
Avoid direct "proved/refuted" language unless the case is genuinely overwhelming.

If the project uses open questions rather than formal hypotheses,
rename this section to "Question-Level Implications" and evaluate
against questions in doc/questions/ instead. -->
```

- [ ] **Step 4: Add "User Questions" section (after line 65, after New Questions Raised)**

After the New Questions Raised closing comment `-->`, add:

```markdown
## User Questions

<!-- Questions the user raised during interpretation, with answers.
These are often the most insightful prompts — record them as part of the
interpretation rather than losing them to conversation history.
Omit if no user questions were raised. -->
```

- [ ] **Step 5: Verify the full template**

Read the entire `templates/interpretation.md` and confirm section order is logical: Findings Summary → Evidence Quality → Data Quality Checks → Claim-Level Updates → Hypothesis-Level Implications → Evidence vs. Open Questions → New Questions Raised → User Questions → Limitations & Residual Uncertainty → Updated Priorities.

- [ ] **Step 6: Commit**

```bash
git add templates/interpretation.md
git commit -m "interpretation template: add data quality checks, user questions, prior_interpretations field"
```

---

### Task 4: plan-pipeline command

**Files:**
- Modify: `commands/plan-pipeline.md:37` (Rules)
- Modify: `commands/plan-pipeline.md:65-80` (Step 2)
- Modify: `commands/plan-pipeline.md:116-137` (Step 4)
- Modify: `commands/plan-pipeline.md:159-164` (Important Notes)

- [ ] **Step 1: Soften the tool-specific rule (line 37)**

Replace:
```markdown
- **MUST NOT** embed tool-specific logic (Snakemake rules, etc.) — reference skills instead
```
With:
```markdown
- **SHOULD** keep plans tool-agnostic by default — reference tool-specific skills. However, when the user explicitly requests a specific orchestration tool (Snakemake, Nextflow, Make, etc.), include a tool-specific section with the workflow definition while keeping the rest of the plan tool-agnostic.
```

- [ ] **Step 2: Update the matching Important Notes bullet (line 161)**

Replace:
```markdown
- **Plans are tool-agnostic by default.** Reference tool-specific skills rather than embedding their conventions.
```
With:
```markdown
- **Plans are tool-agnostic by default.** Reference tool-specific skills rather than embedding their conventions. Exception: when the user explicitly requests a specific tool, include a dedicated tool-specific section.
```

- [ ] **Step 3: Replace "Tech Stack" with "New Dependencies" in Step 4 template (line 129)**

Replace:
```markdown
**Tech Stack:** <tools identified in steps 2-3>
```
With:
```markdown
**New Dependencies:** <libraries, tools, or data sources not already in the project>
```

- [ ] **Step 4: Add new plan sections guidance in Step 4 (after line 137)**

After the plan template closing ``` and before "Each task should reference", add:

```markdown
#### Conditional Plan Sections

Include these sections when applicable:

- **Changes to Existing Code** (Task mode / extend-existing-workflow plans): Which existing files are modified and why? What's the diff from the current working pipeline? Omit when building from scratch.
- **Decision Criteria** (exploratory/research plans): What would change our mind about pursuing this? What result at what stage would make us stop or pivot? This is a top-level go/no-go, distinct from per-task validation criteria. Omit for straightforward implementation plans.
- **Reusable Infrastructure:** If any task produces infrastructure (tools, indices, data pipelines) with value beyond this specific analysis, flag it with `reusable: true` and briefly describe the broader applicability.
```

- [ ] **Step 5: Verify edits**

Read `commands/plan-pipeline.md` lines 27-45, 116-145, and 155-165 to confirm clean integration.

- [ ] **Step 6: Commit**

```bash
git add commands/plan-pipeline.md
git commit -m "plan-pipeline: new dependencies rename, tool-specific opt-in, conditional plan sections"
```

---

### Task 5: research-paper command

**Files:**
- Modify: `commands/research-paper.md:40-49` (Source Strategy, "If given a URL")
- Modify: `commands/research-paper.md:60-66` (After Writing)

- [ ] **Step 1: Add paywall fallback (after line 43)**

After "3. Cross-check key facts." in the "If given a URL" section, add:

```markdown
4. **If the URL returns a paywall, 403, or redirect loop:** fall back to DOI resolution → PubMed/preprint search (bioRxiv, arXiv, SSRN) → press coverage → GitHub README/repo. Do not abandon the paper — most paywalled papers have accessible metadata through alternative channels. Note the fallback source in the `Source:` frontmatter field.
```

- [ ] **Step 2: Add cross-paper synthesis section (after line 66, after "After Writing")**

After the existing "After Writing" numbered list, add:

```markdown
## Batch Processing

When processing multiple papers in a single session (2+ papers with a shared thematic connection), after all individual summaries are written:

1. Produce a brief cross-paper synthesis document at `doc/papers/synthesis-YYYY-MM-DD-<theme>.md`.
2. Contents: shared themes, tensions between papers, and combined implications for the project.
3. Cross-reference the individual paper summaries by their `id` fields.

This only applies when papers share a thematic connection. Unrelated papers processed in the same session do not need synthesis.
```

- [ ] **Step 3: Verify edits**

Read `commands/research-paper.md` lines 38-75 to confirm clean integration.

- [ ] **Step 4: Commit**

```bash
git add commands/research-paper.md
git commit -m "research-paper: paywall fallback, cross-paper synthesis for batch processing"
```

---

### Task 6: paper-summary template

**Files:**
- Modify: `templates/paper-summary.md`

- [ ] **Step 1: Add "Project Framework Mapping" section after Relevance (after line 39)**

After `## Relevance` and its comment, add:

```markdown
## Project Framework Mapping

<!-- If the project has an existing ontology, schema, or classification framework,
map the paper's concepts to the project's vocabulary:

| Paper Concept | Project Concept | Notes |
|---|---|---|
| <their term> | <our term> | <correspondence notes> |

Omit if no structured framework exists to map against. -->
```

- [ ] **Step 2: Add "Model / Tool Availability" section after Limitations (after line 43)**

After `## Limitations` and its comment, add:

```markdown
## Model / Tool Availability

<!-- If the paper describes a model, tool, or dataset intended for reuse:
- Available checkpoints / versions
- Hardware requirements
- License
- Quantization options (if applicable)
- Access restrictions

Omit for papers that don't release artifacts. -->
```

- [ ] **Step 3: Verify section order**

Read the full template and confirm order: Key Contribution → Methods → Key Findings → Relevance → Project Framework Mapping → Limitations → Model / Tool Availability → Follow-up.

- [ ] **Step 4: Commit**

```bash
git add templates/paper-summary.md
git commit -m "paper-summary template: add project framework mapping and model/tool availability sections"
```

---

### Task 7: next-steps command

**Files:**
- Modify: `commands/next-steps.md:85-91` (section 3b)
- Modify: `commands/next-steps.md:107-119` (section 4)
- Modify: `commands/next-steps.md:143` (writing template example)

- [ ] **Step 1: Rename and expand section 3b (lines 85-91)**

Replace the existing section 3b:

```markdown
### 3b. Newly Unblocked

If a prior next-steps analysis exists (`doc/meta/next-steps-*.md`), compare against it:
- Which tasks were previously blocked but are now unblocked?
- What changed to unblock them?

This longitudinal view makes progress visible and highlights newly actionable work.
```

With:

```markdown
### 3b. Status Transitions

If a prior next-steps analysis exists (`doc/meta/next-steps-*.md`), compare against it and surface all three directions:

- **Newly unblocked:** tasks that were blocked but are now actionable. What changed to unblock them?
- **Newly blocked:** tasks that lost a dependency or had assumptions invalidated since the last analysis.
- **Newly irrelevant:** tasks superseded by results or no longer decision-relevant. These are pruning opportunities — removing stale work from the queue is as valuable as adding new work.

This longitudinal view makes progress visible and highlights both forward momentum and pruning opportunities.
```

- [ ] **Step 2: Add design constraints guidance in section 4 (after line 119)**

After the existing "For each suggestion, include:" list, add:

```markdown
**Design constraints:** If the user has provided actionable design feedback during the session that doesn't fit the task/question/hypothesis taxonomy (e.g., page density preferences, API constraints, performance requirements), capture it as a row in the Recommended Next Actions table with a note to record it in project memory or a design doc.
```

- [ ] **Step 3: Update the writing template example (line 143)**

Replace:
```markdown
## Newly Unblocked (if prior analysis exists)
<tasks that became actionable since last analysis>
```
With:
```markdown
## Status Transitions (if prior analysis exists)
<newly unblocked, newly blocked, newly irrelevant tasks since last analysis>
```

- [ ] **Step 4: Verify edits**

Read `commands/next-steps.md` lines 83-155 to confirm clean integration.

- [ ] **Step 5: Commit**

```bash
git add commands/next-steps.md
git commit -m "next-steps: status transitions (blocked/irrelevant), design constraints guidance"
```

---

### Task 8: pre-register command

**Files:**
- Modify: `commands/pre-register.md:43-48` (section 4)
- Modify: `commands/pre-register.md:65-69` (section 5)

- [ ] **Step 1: Add pilot-specific prompt in section 4 (after line 48)**

After "What would you do next if results are ambiguous?", add:

```markdown
**Pilot experiments:** If this is a pilot (1-2 seeds, small N, exploratory scope), explicitly state what it CAN and CANNOT establish. A pilot can suggest directions and calibrate effect sizes but cannot confirm or refute a hypothesis. Frame decision criteria accordingly — a pilot's null result means "insufficient signal to justify scaling up", not "hypothesis is wrong."
```

- [ ] **Step 2: Add sampling strategy rationale in section 5 (after line 69)**

After "Are there analyses you plan to run 'just to see what happens'? Label them.", add:

```markdown
### 5b. Sampling Strategy Rationale (if applicable)

If the experimental design involves non-obvious sampling decisions (stratified sampling, subsampling from a larger population, context selection), document the rationale and trade-offs:
- What sampling strategy was chosen?
- What was the alternative?
- Why was this approach preferred?

Omit when sampling is straightforward (e.g., "use all available data").
```

- [ ] **Step 3: Verify edits**

Read `commands/pre-register.md` lines 40-75 to confirm clean integration.

- [ ] **Step 4: Commit**

```bash
git add commands/pre-register.md
git commit -m "pre-register: pilot-specific prompt, sampling strategy rationale"
```

---

### Task 9: discuss command + template

**Files:**
- Modify: `commands/discuss.md:68-76` (After Discussion section)
- Modify: `templates/discussion.md:37-41` (Follow-Ups table)

- [ ] **Step 1: Add actionable recommendations guidance (after line 76, in After Discussion)**

After item 5 ("Commit: ..."), but before the Process Reflection section, add:

```markdown
6. **Actionable recommendations:** If the discussion produced a concrete, low-cost design change or implementation recommendation (something testable in under an hour), it should be flagged with `[actionable now]` in the Prioritized Follow-Ups table. Offer to implement it immediately rather than creating a task for later. This prevents useful small changes from being buried in discussion documents.
```

- [ ] **Step 2: Update template Follow-Ups table example (lines 37-41)**

Replace:
```markdown
## Prioritized Follow-Ups

| Priority | Action | Why now | Dependencies |
|---|---|---|---|
| P1 | <action> | <rationale> | <deps> |
```

With:
```markdown
## Prioritized Follow-Ups

| Priority | Action | Why now | Dependencies |
|---|---|---|---|
| P1 | <action> | <rationale> | <deps> |
| P1 [actionable now] | <low-cost change> | <can verify immediately> | none |
```

- [ ] **Step 3: Verify edits**

Read `commands/discuss.md` lines 68-82 and `templates/discussion.md` lines 35-45 to confirm.

- [ ] **Step 4: Commit**

```bash
git add commands/discuss.md templates/discussion.md
git commit -m "discuss: actionable-now tag for low-cost recommendations"
```

---

### Task 10: review-pipeline command

**Files:**
- Modify: `commands/review-pipeline.md:50-60` (sub-plan handling + Dimension 1)

- [ ] **Step 1: Add conditional dimension guidance (expand line 50)**

Replace the existing sub-plan handling note:

```markdown
**Sub-plan handling:** If the plan being reviewed is a sub-plan of a larger inquiry (e.g., Tasks 2-3 of a broader inquiry), the inquiry-level validation may pass trivially. In this case, apply the rubric dimensions to the plan's internal consistency, not just the parent inquiry's structure.
```

With:

```markdown
**Sub-plan handling:** If the plan being reviewed is a sub-plan of a larger inquiry (e.g., Tasks 2-3 of a broader inquiry), the inquiry-level validation may pass trivially. In this case:
- Apply the rubric dimensions to the plan's internal consistency, not just the parent inquiry's structure.
- Dimensions 1 (Evidence Coverage) and 7 (Scope Check) may be marked **N/A — inherited from parent plan** if the parent plan has already passed review on these dimensions. Reference the parent plan's review document.
- Focus review effort on dimensions specific to the sub-plan: validation criteria (Dim 6), assumption audit (Dim 2), integration boundaries (Dim 8).
```

- [ ] **Step 2: Verify edit**

Read `commands/review-pipeline.md` lines 48-62 to confirm.

- [ ] **Step 3: Commit**

```bash
git add commands/review-pipeline.md
git commit -m "review-pipeline: conditional N/A for inherited rubric dimensions in sub-plans"
```

---

### Task 11: Update feedback file triage dates

**Files:**
- Modify: `/home/keith/d/3d-attention-bias/doc/meta/skill-feedback.md:3`
- Modify: `/home/keith/d/seq-feats/doc/meta/skill-feedback.md:3`
- Modify: `/home/keith/d/natural-systems/doc/meta/skill-feedback.md:3`

- [ ] **Step 1: Update 3d-attention-bias triage date**

Replace:
```markdown
> **Last reviewed:** 2026-03-15. All items through this date have been triaged — addressed items are reflected in the current commands/templates in the `science` repo. New feedback should be appended below the existing entries.
```
With:
```markdown
> **Last reviewed:** 2026-03-25. All items through this date have been triaged — addressed items are reflected in the current commands/templates in the `science` repo. New feedback should be appended below the existing entries.
```

- [ ] **Step 2: Update seq-feats triage date**

Same replacement: `2026-03-15` → `2026-03-25` on line 3. Also update the deferred note to reflect what's still deferred:

Replace:
```markdown
> **Last reviewed:** 2026-03-15. All items through this date have been triaged — addressed items are reflected in the current commands/templates in the `science` repo. Remaining items deferred: "Signal Decomposition" section (aspect-contributed, lower priority). New feedback should be appended below the existing entries.
```
With:
```markdown
> **Last reviewed:** 2026-03-25. All items through this date have been triaged — addressed items are reflected in the current commands/templates in the `science` repo. Remaining items deferred: "Signal Decomposition" section (aspect-contributed, lower priority). New feedback should be appended below the existing entries.
```

- [ ] **Step 3: Update natural-systems triage date**

Replace:
```markdown
> **Last reviewed:** 2026-03-15. All items through this date have been triaged — addressed items are reflected in the current commands/templates in the `science` repo. Remaining items deferred: "Comparison of Approaches" section for research-topic (aspect-contributed, lower priority). New feedback should be appended below the existing entries.
```
With:
```markdown
> **Last reviewed:** 2026-03-25. All items through this date have been triaged — addressed items are reflected in the current commands/templates in the `science` repo. Remaining items deferred: "Comparison of Approaches" section for research-topic (aspect-contributed, lower priority). New feedback should be appended below the existing entries.
```

- [ ] **Step 4: Commit all three**

```bash
cd /home/keith/d/3d-attention-bias && git add doc/meta/skill-feedback.md && git commit -m "doc: update skill feedback triage date to 2026-03-25"
cd /home/keith/d/seq-feats && git add doc/meta/skill-feedback.md && git commit -m "doc: update skill feedback triage date to 2026-03-25"
cd /home/keith/d/natural-systems && git add doc/meta/skill-feedback.md && git commit -m "doc: update skill feedback triage date to 2026-03-25"
```

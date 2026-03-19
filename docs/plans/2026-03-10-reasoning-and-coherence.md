# Reasoning, Critical Thinking & Coherence Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured adversarial reasoning commands, extend existing commands with sensitivity/QA/pre-registration checks, and simplify the command set by merging overlapping commands.

**Architecture:** All changes are to markdown command/template/aspect files — no code changes. New commands follow the existing pattern: YAML frontmatter → heading → setup → workflow → writing → after writing → process reflection. Extensions to existing commands are added as new sections or aspect contributions.

**Tech Stack:** Markdown, YAML frontmatter, bash (validate.sh)

**Spec:** `docs/superpowers/specs/2026-03-10-reasoning-and-coherence-design.md`

---

## Chunk 1: Templates and New Commands

### Task 1: Create pre-registration template

**Files:**
- Create: `templates/pre-registration.md`

- [ ] **Step 1: Create the template file**

```markdown
---
id: "pre-registration:{{slug}}"
type: "pre-registration"
title: "{{Short Title}}"
status: "active"
tags: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---

# Pre-registration: {{Short Title}}

## Hypotheses Under Test

<!-- Which hypotheses does this analysis address? List by ID (e.g., H01).
     These must match entries in the `related` frontmatter field
     so that interpret-results can find this pre-registration. -->

## Expected Outcomes

<!-- What do you expect to find, and why? Be specific about direction, magnitude, and pattern. -->

## Decision Criteria

<!-- For each hypothesis:
- What evidence would SUPPORT it?
- What evidence would WEAKEN it?
- What evidence would REFUTE it?
Be concrete — name the metric, the threshold, the pattern. -->

## Null Result Plan

<!-- What does it mean if results are ambiguous or null?
- Is the analysis underpowered?
- Does null mean the hypothesis is wrong, or that the test was inadequate?
- What would you do next? -->

## Known Limitations

<!-- What can this analysis NOT tell you, even if it works perfectly? -->

## Exploratory vs. Confirmatory

<!-- Which analyses are pre-registered (confirmatory) and which are explicitly exploratory?
Mark each planned analysis as one or the other. Exploratory analyses are fine — but they need different evidential weight. -->
```

- [ ] **Step 2: Verify template follows existing patterns**

Run: `head -14 templates/background-topic.md templates/pre-registration.md`
Expected: Both start with YAML frontmatter (quoted values, colon-delimited ID, full field set), then `# Heading`, then sections with HTML comments.

- [ ] **Step 3: Commit**

```bash
git add templates/pre-registration.md
git commit -m "feat: add pre-registration document template"
```

---

### Task 2: Create comparison template

**Files:**
- Create: `templates/comparison.md`

- [ ] **Step 1: Create the template file**

```markdown
---
id: "comparison:{{slug}}"
type: "comparison"
title: "{{Short Title}}"
status: "active"
tags: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---

# Hypothesis Comparison: {{Short Title}}

## Hypotheses Compared

<!-- Summary of each hypothesis with key claims. -->

### {{H01 — Title}}

<!-- Core claim, mechanism, and key predictions. -->

### {{H02 — Title}}

<!-- Core claim, mechanism, and key predictions. -->

## Evidence Inventory

<!-- For each hypothesis: what supports it, what weakens it, what is silent.
Use a table or structured list. -->

| Evidence | Supports H01 | Supports H02 | Neutral |
|---|---|---|---|
| {{finding or paper}} | {{how}} | {{how}} | {{why neutral}} |

## Discriminating Predictions

<!-- Where do these hypotheses make DIFFERENT predictions?
These are the high-value observations — the places where data could settle the question. -->

## Crucial Experiments

<!-- What single observation or analysis would most decisively distinguish between them?
Be specific about what you'd measure, what you'd expect under each hypothesis, and what data you'd need. -->

## Current Verdict

<!-- Which hypothesis is better supported? How confident are you?
What specific evidence would change the verdict? -->

## Synthesis

<!-- Are these truly competing, or could they be complementary?
Could they operate at different scales, in different conditions, or via different mechanisms? -->
```

- [ ] **Step 2: Commit**

```bash
git add templates/comparison.md
git commit -m "feat: add hypothesis comparison template"
```

---

### Task 3: Create bias-audit template

**Files:**
- Create: `templates/bias-audit.md`

- [ ] **Step 1: Create the template file**

```markdown
---
id: "bias-audit:{{slug}}"
type: "bias-audit"
title: "{{Short Title}}"
status: "active"
tags: []
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---

# Bias Audit: {{Short Title}}

## Scope

<!-- What area of the project is this audit focused on?
A specific hypothesis, inquiry, pipeline, or the most recently active area. -->

## Cognitive Biases

### Confirmation Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are you seeking/citing evidence that supports your preferred hypothesis disproportionately? Are disconfirming papers absent from your searches? -->

### Anchoring

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are early conclusions or first-read papers over-weighted? Has the framing shifted since the project started? -->

### Availability Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are you over-relying on familiar methods, datasets, or frameworks? -->

### Sunk Cost

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are you pursuing a hypothesis or approach because of effort invested rather than evidence? -->

## Methodological Biases

### Selection Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- In literature selection, data inclusion/exclusion, or method choice. -->

### Survivorship Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are you only seeing studies/datasets/methods that "worked"? -->

### HARKing

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Do current hypotheses match pre-registration? If no pre-registration exists, flag this. -->

### Multiple Comparisons / p-hacking Risk

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- How many analyses are planned? Is there correction? -->

### Confounding

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Cross-reference causal DAG if available; otherwise check for uncontrolled variables. -->

### Publication Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Is the literature search biased toward positive results? -->

## Summary

- **Overall threat level:** low / moderate / elevated / high
- **Top mitigations:**
  1. <!-- Highest priority mitigation -->
  2. <!-- Second priority -->
  3. <!-- Third priority -->
- **Recommended next actions:** <!-- What to do about the identified threats -->
```

- [ ] **Step 2: Commit**

```bash
git add templates/bias-audit.md
git commit -m "feat: add bias audit template"
```

---

### Task 4: Create `pre-register` command

**Files:**
- Create: `commands/pre-register.md`

- [ ] **Step 1: Create the command file**

```markdown
---
description: Formalize expectations before analysis to prevent post-hoc rationalization. Use after add-hypothesis or plan-pipeline, before running analysis. Also use when the user says "what do I expect", "pre-register", "before I run this", "formalize expectations", or "what would change my mind".
---

# Pre-register Expectations

Formalize the user's expectations, decision criteria, and null-result plans before analysis begins.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `templates/pre-registration.md`.
2. Read active hypotheses in `specs/hypotheses/`.
3. Read existing inquiries: run `science-tool inquiry list` (if available).
4. Read existing pipeline plans in `doc/plans/` (if any).
5. Read existing pre-registrations in `doc/meta/pre-registration-*.md` to avoid duplication.

## Interactive Refinement

Have a natural conversation with the user to formalize their expectations. The questions below are guidelines — use your judgment about which are needed based on how much context the user has already provided.

### 1. Identify the Analysis

- What analysis are you about to run?
- Which hypotheses does it test? (Reference by ID if they exist in `specs/hypotheses/`)
- Is there a pipeline plan? (Reference by slug if one exists in `doc/plans/`)

### 2. State Expected Outcomes

- What do you expect to find?
- Why do you expect this? (Link to existing evidence — papers, topics, prior results)
- How specific can you be? (Direction? Magnitude? Pattern?)

### 3. Define Decision Criteria

For each hypothesis under test:
- What evidence would **support** it? Be concrete — name the metric, the threshold, the pattern.
- What evidence would **weaken** it? What would make you less confident but not abandon it?
- What evidence would **refute** it? What would make you abandon this hypothesis?

### 4. Plan for Null Results

- What does a null result mean? Hypothesis is wrong, or test is inadequate?
- Is the analysis sufficiently powered to detect the expected effect?
- What would you do next if results are ambiguous?

### 5. Separate Confirmatory from Exploratory

- Which analyses are pre-registered (confirmatory)?
- Which are explicitly exploratory?
- Are there analyses you plan to run "just to see what happens"? Label them.

## Writing

After the conversation, write the pre-registration document following `templates/pre-registration.md`.

### Naming

Use the hypothesis ID or inquiry slug as the basis:
- **Filename:** `doc/meta/pre-registration-<slug>.md`
- The `related` frontmatter field must list the hypothesis IDs and/or inquiry slugs being tested.

## After Writing

1. Save to `doc/meta/pre-registration-<slug>.md`.
2. If relevant hypotheses exist, note in the output that pre-registration is now on record.
3. Suggest next steps:
   - `/science:plan-pipeline` — if no pipeline plan exists yet
   - `/science:bias-audit` — to check for blind spots before running the analysis
   - `/science:discuss` — to stress-test the expectations themselves
4. Commit: `git add -A && git commit -m "doc: pre-register expectations for <slug>"`

## Process Reflection

Reflect on the **pre-registration template** sections and the **decision criteria** workflow.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — pre-register

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
- Be concrete and specific, not generic ("the Null Result Plan section was hard to fill without knowing the sample size" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [ ] **Step 2: Verify command follows existing patterns**

Run: `head -5 commands/add-hypothesis.md commands/pre-register.md`
Expected: Both have YAML frontmatter with `description:` field.

- [ ] **Step 3: Commit**

```bash
git add commands/pre-register.md
git commit -m "feat: add pre-register command"
```

---

### Task 5: Create `compare-hypotheses` command

**Files:**
- Create: `commands/compare-hypotheses.md`

- [ ] **Step 1: Create the command file**

```markdown
---
description: Head-to-head evaluation of competing explanations. Use when 2+ hypotheses exist for the same phenomenon and need systematic comparison. Also use when the user says "compare", "which explanation is better", "competing hypotheses", "alternative explanations", or "which hypothesis".
---

# Compare Hypotheses

Perform a structured, head-to-head comparison of competing hypotheses from `$ARGUMENTS`. The goal is adversarial: force the researcher to consider that their preferred hypothesis might be wrong, and to identify what evidence would prove it.

If no arguments are provided, scan `specs/hypotheses/` and propose candidate pairs that share `related` entities, reference the same papers/topics, or make predictions about the same observable.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `templates/comparison.md`.
2. Read all hypotheses in `specs/hypotheses/`.
3. Read existing evidence:
   - `doc/topics/` — background knowledge
   - `doc/papers/` — paper summaries
   - `doc/interpretations/` — prior result interpretations
   - `doc/discussions/` — prior discussions
4. Read existing comparisons in `doc/discussions/comparison-*.md` to avoid repeating prior work.

## Hypothesis Selection

### If hypotheses are specified in `$ARGUMENTS`

Verify they exist in `specs/hypotheses/`. If an argument doesn't match a known hypothesis, search for the closest match and confirm with the user.

### If no hypotheses are specified

Propose candidate pairs by scanning `specs/hypotheses/` for hypotheses that:
- Reference the same papers or topics in their "Related Work" or "Current Evidence" sections
- Make predictions about the same observable or variable
- Address the same open question in `doc/questions/`
- Have overlapping keywords in their "Statement" sections

Recommend the highest-value pair (most evidence overlap, most divergent predictions) and present it to the user for confirmation.

### Comparison mode

Always pairwise. When 3+ hypotheses are relevant, compare the highest-value pair first and note remaining pairs for follow-up comparisons.

## Workflow

### 1. Summarize Each Hypothesis

For each hypothesis in the comparison:
- State the core claim
- Identify the proposed mechanism
- List key predictions

### 2. Build the Evidence Inventory

For each piece of relevant evidence (papers, topic summaries, prior interpretations):
- Does it support hypothesis A, hypothesis B, both, or neither?
- How strong is the support? (Strong / Suggestive / Weak)
- Are there caveats or alternative interpretations?

Present as a structured table.

### 3. Identify Discriminating Predictions

This is the most important section. Find places where the two hypotheses make **different** predictions:
- "If H01 is correct, we should observe X. If H02 is correct, we should observe Y instead."
- Focus on predictions that are testable with available or obtainable data.
- Rank by discriminatory power (how decisively would the observation distinguish them?).

### 4. Propose Crucial Experiments

Identify the single most decisive observation or analysis:
- What would you measure?
- What would you expect under each hypothesis?
- What data do you need?
- Is this feasible with current resources?

### 5. Assess Current Verdict

- Which hypothesis is better supported by current evidence?
- How confident? (High / Moderate / Low)
- What specific new evidence would change the verdict?

### 6. Consider Synthesis

- Are these truly competing, or could they be complementary?
- Could they operate at different scales, conditions, or via different mechanisms?
- Is there a synthesis that explains more than either alone?

## Writing

Follow `templates/comparison.md` and fill all sections.
Save to `doc/discussions/comparison-<slug>.md`.

The `<slug>` should capture both hypotheses, e.g., `comparison-h01-vs-h02.md`.

## After Writing

1. Save to `doc/discussions/comparison-<slug>.md`.
2. If crucial experiments suggest new analyses, offer to create tasks via `science-tool tasks add`.
3. If the comparison reveals the need for new hypotheses (e.g., a synthesis), suggest `/science:add-hypothesis`.
4. Suggest next steps:
   - `/science:pre-register` — if the crucial experiment is ready to run
   - `/science:discuss` — to debate specific points of disagreement
   - `/science:bias-audit` — to check if the comparison itself is biased
5. Commit: `git add -A && git commit -m "doc: compare hypotheses <slug>"`

## Process Reflection

Reflect on the **comparison template** sections and the **evidence inventory** workflow.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — compare-hypotheses

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
- Be concrete and specific, not generic ("the Discriminating Predictions section was hard when both hypotheses are vague" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence
- If everything worked smoothly, a single "No friction encountered" is fine

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [ ] **Step 2: Commit**

```bash
git add commands/compare-hypotheses.md
git commit -m "feat: add compare-hypotheses command"
```

---

### Task 6: Create `bias-audit` command

**Files:**
- Create: `commands/bias-audit.md`

- [ ] **Step 1: Create the command file**

```markdown
---
description: Systematic check of cognitive and methodological biases against current project state. Use at any point, especially before interpret-results or when a project feels too settled. Also use when the user says "check my biases", "what am I missing", "audit", "threats to validity", "blind spots", or "am I being fair".
---

# Bias Audit

Perform a systematic bias and threat-to-validity check against the current project state.

Use `$ARGUMENTS` to scope the audit to a specific hypothesis, inquiry, or pipeline. If no scope is provided, audit the most recently active area (most recently modified documents).

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `templates/bias-audit.md`.
2. Determine audit scope:
   - If `$ARGUMENTS` names a hypothesis: read that hypothesis and its related documents
   - If `$ARGUMENTS` names an inquiry: load the inquiry and its related documents
   - If `$ARGUMENTS` names a pipeline: read the pipeline plan and its source inquiry
   - If no scope: identify the most recently modified research documents (use `git log --oneline -10 --name-only -- doc/ specs/ models/`)
3. Read scoped documents:
   - Relevant hypotheses from `specs/hypotheses/`
   - Relevant topics from `doc/topics/`
   - Relevant papers from `doc/papers/`
   - Relevant discussions from `doc/discussions/`
   - Relevant interpretations from `doc/interpretations/`
   - Relevant searches from `doc/searches/`
   - Pipeline plans from `doc/plans/` (if applicable)
4. Read pre-registration documents from `doc/meta/pre-registration-*.md` (if any exist).
5. If `causal-modeling` aspect is active, load causal DAGs from the knowledge graph.

## Workflow

### 1. Establish Scope

State clearly what is being audited and why. If the user didn't specify a scope, explain how you chose the focus area.

### 2. Cognitive Bias Assessment

For each cognitive bias, assess based on the evidence you've read:

**Confirmation bias:**
- Examine literature searches: are there search terms that would find disconfirming evidence that weren't used?
- Compare citations: are papers that support the hypothesis cited more than papers that challenge it?
- Check discussions: do discussion artifacts explore alternative explanations seriously?

**Anchoring:**
- Compare the earliest project documents (first topics, first hypotheses) with recent ones: has the framing shifted, or is the project anchored to initial assumptions?
- Are first-cited papers given more weight than later ones?

**Availability bias:**
- Are methods, datasets, or frameworks chosen because they're familiar rather than optimal?
- Is there a pattern of using the same tools/approaches across different parts of the project?

**Sunk cost:**
- Are there hypotheses or approaches that have received significant effort but little supporting evidence?
- Has the project direction changed in response to evidence, or stayed fixed despite it?

### 3. Methodological Bias Assessment

**Selection bias:**
- In literature: are inclusion/exclusion criteria for papers explicit and justified?
- In data: are data inclusion/exclusion criteria documented?
- In methods: why was this method chosen over alternatives?

**Survivorship bias:**
- Are negative results or failed approaches documented?
- Does the literature review include studies that found null results?

**HARKing (Hypothesizing After Results are Known):**
- If pre-registration documents exist, compare current hypotheses against them. Flag any drift.
- If no pre-registration exists, flag this as a risk and suggest `/science:pre-register`.

**Multiple comparisons / p-hacking risk:**
- How many analyses are planned or have been run?
- Is there correction for multiple comparisons?
- Are analyses pre-specified or chosen after seeing data?

**Confounding:**
- If a causal DAG exists, review it for uncontrolled confounders.
- If no causal DAG exists, identify key relationships and ask: "what else could explain this?"

**Publication bias:**
- Are literature searches biased toward positive results?
- Are null-result papers included in the review?

### 4. Synthesize

- Rate each bias: not detected / possible / likely
- Identify the top 3 threats by severity
- For each threat, propose a specific mitigation
- Assign overall threat level: low / moderate / elevated / high

## Writing

Follow `templates/bias-audit.md` and fill all sections.
Save to `doc/meta/bias-audit-<slug>.md`.

## After Writing

1. Save to `doc/meta/bias-audit-<slug>.md`.
2. If HARKing risk is detected and no pre-registration exists, suggest `/science:pre-register`.
3. If confirmation bias is detected, suggest `/science:compare-hypotheses` to force consideration of alternatives.
4. If confounding is detected and no causal DAG exists, suggest `/science:sketch-model`.
5. Offer to create tasks for the recommended mitigations via `science-tool tasks add`.
6. Commit: `git add -A && git commit -m "doc: bias audit <slug>"`

## Process Reflection

Reflect on the **bias audit template** and the **assessment workflow**.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — bias-audit

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
- Be concrete and specific, not generic ("the Sunk Cost check was hard to assess without knowing time invested" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence
- If everything worked smoothly, a single "No friction encountered" is fine

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [ ] **Step 2: Commit**

```bash
git add commands/bias-audit.md
git commit -m "feat: add bias-audit command"
```

---

## Chunk 2: Extensions to Existing Commands

### Task 7: Add sensitivity analysis to `critique-approach`

**Files:**
- Modify: `commands/critique-approach.md`

The sensitivity analysis section is added between Step 6 (Assess overall validity) and Step 7 (Write review report).

Note: `critique-approach` is currently causal-DAG-specific. The sensitivity analysis added here uses causal terminology (confounders, causal edges). Generalizing `critique-approach` to support non-causal models is deferred — when that happens, the sensitivity section's language should be adapted per the spec (conceptual models get assumption-focused analysis instead).

- [ ] **Step 1: Add the sensitivity analysis step**

In `commands/critique-approach.md`, insert a new `### Step 6b: Sensitivity analysis` section after `### Step 6: Assess overall validity` and before `### Step 7: Write review report`.

Add this content:

```markdown
### Step 6b: Sensitivity analysis

For each key assumption or causal edge identified in steps 3-5, assess sensitivity:

1. **What if this assumption is violated?**
   - State the assumption explicitly
   - Describe how conclusions change if it's wrong
   - Rate impact: high (conclusions reverse) / moderate (conclusions weaken) / low (conclusions robust)

2. **What if this relationship doesn't hold or is reversed?**
   - For causal edges: what if A doesn't cause B, or B causes A?
   - For conceptual models: what if this link is spurious or mediated?

3. **Unmeasured variables**
   - For causal DAGs: for each critical path, what unmeasured confounder could explain the relationship?
   - For conceptual models: what hidden mediator or moderator could alter the relationship?

4. **Robustness**
   - What's the minimum effect size that would survive the identified threats?
   - How sensitive are conclusions to parameter choices?

5. **Boundary conditions**
   - Under what conditions does the model break down entirely?
   - Are there population, temporal, or contextual limits to applicability?

Include a sensitivity summary table in the review report:

| Assumption | If Violated | Impact | Robustness |
|---|---|---|---|
| <assumption> | <consequence> | high/moderate/low | <assessment> |
```

- [ ] **Step 2: Update the review report template in Step 7**

In the review report markdown template inside Step 7, add a `## Sensitivity Analysis` section after `## Structural Issues` and before `## Overall Assessment`:

```markdown
## Sensitivity Analysis
<sensitivity summary table and key findings>
```

- [ ] **Step 3: Update the overall assessment table**

In Step 6's assessment table, add a `Sensitivity` row after the last existing row (`| Temporal coherence | ... |`):

```markdown
| Sensitivity | How robust are conclusions to assumption violations? |
```

- [ ] **Step 4: Commit**

```bash
git add commands/critique-approach.md
git commit -m "feat: add sensitivity analysis to critique-approach"
```

---

### Task 8: Add QA checkpoints to `plan-pipeline` via `computational-analysis` aspect

**Files:**
- Modify: `aspects/computational-analysis/computational-analysis.md`

QA checkpoints are gated by the `computational-analysis` aspect. Adding them as an aspect contribution (rather than modifying `plan-pipeline` directly) follows the established pattern for aspect-conditional sections.

- [ ] **Step 1: Add plan-pipeline section to computational-analysis aspect**

In `aspects/computational-analysis/computational-analysis.md`, add a new top-level section before `## Signal categories`:

```markdown
## plan-pipeline

### Additional section: QA Checkpoints

(insert after: the last Task in the pipeline plan)

For each pipeline stage (each `sci:Transformation` node), define:

**Input assertions:**
- Expected row counts or data dimensions
- Value ranges and type constraints
- Missingness rates and schema conformance
- Distribution checks (if known expectations exist)

**Inter-stage invariants:**
- No silent row drops: row count before/after each transformation with allowed tolerance
- Referential integrity: foreign keys and join conditions verified
- Value conservation: aggregation totals match, no data loss in reshaping
- Cardinality checks: one-to-many, many-to-many relationships as expected

**Sanity checks:**
- Known-answer tests: run on synthetic or known data where the correct answer is predetermined
- Spot checks: sample N records and verify by hand
- Summary statistics: mean, median, range before/after each stage

**Failure mode:**
- Default: hard stop (assertion failure halts the pipeline)
- Document any stages where a logged warning is acceptable instead, with justification

Add QA checkpoints as first-class steps in the pipeline plan, not as afterthoughts. Each transformation task should include its assertions alongside the implementation steps.

### Additional guidance

When planning computational pipelines:
- Suggest a "dry run on small data" step before full execution
- For each transformation, ask: "How would I know if this step silently produced wrong results?"
- Include a final end-to-end sanity check that validates the complete output against known properties
```

- [ ] **Step 2: Commit**

```bash
git add aspects/computational-analysis/computational-analysis.md
git commit -m "feat: add QA checkpoint guidance to computational-analysis aspect for plan-pipeline"
```

---

### Task 9: Add QA coverage audit to `review-pipeline` via `computational-analysis` aspect

**Files:**
- Modify: `aspects/computational-analysis/computational-analysis.md`

- [ ] **Step 1: Add review-pipeline section to computational-analysis aspect**

In `aspects/computational-analysis/computational-analysis.md`, add after the `## plan-pipeline` section added in Task 8:

```markdown
## review-pipeline

### Additional rubric dimension: QA Coverage

(insert after: Dimension 7: Scope Check)

Evaluate QA discipline across the pipeline:

- **Assertion coverage:** Does every `sci:Transformation` have input/output assertions? Score: PASS (all covered) / WARN (gaps) / FAIL (no assertions)
- **Intermediate checkpoints:** Are there checks between stages, or is it black-box end-to-end? Score: PASS (intermediate checks) / WARN (only final check) / FAIL (no checks)
- **Failure handling:** What happens when an assertion fails? Is it hard stop or silent? Score: PASS (hard stop default) / WARN (mixed) / FAIL (all silent)
- **Dry run step:** Is there a "run on small/synthetic data" step before full execution? Score: PASS (present) / WARN (suggested but not planned) / FAIL (absent)
- **Edge case coverage:** Are edge cases documented (empty inputs, missing values, extreme values)? Score: PASS (documented) / WARN (partial) / FAIL (not considered)

Include QA Coverage as an additional row in the rubric results table.
```

- [ ] **Step 2: Commit**

```bash
git add aspects/computational-analysis/computational-analysis.md
git commit -m "feat: add QA coverage audit to computational-analysis aspect for review-pipeline"
```

---

### Task 10: Add pre-registration cross-check to `interpret-results`

**Files:**
- Modify: `commands/interpret-results.md`
- Modify: `templates/interpretation.md`

- [ ] **Step 1: Update interpret-results setup to load pre-registrations**

In `commands/interpret-results.md`, in the `## Setup` section, add after item 5 (the `inquiry show` code block):

```markdown
6. Check for pre-registration documents: scan `doc/meta/pre-registration-*.md`. If any exist, read them and identify which are relevant to the current interpretation (matching hypothesis IDs in the `related` frontmatter field).
```

- [ ] **Step 2: Add pre-registration cross-check step to workflow**

In `commands/interpret-results.md`, add a new step between `### 3. Aspect-contributed analysis` and `### 4. Surface new questions`. Insert:

```markdown
### 3b. Pre-registration cross-check

If a pre-registration document exists for any hypothesis or inquiry being interpreted (matched via `related` frontmatter field):

1. **Match check:** Does the result match pre-registered expectations?
   - Compare actual findings against the "Expected Outcomes" section of the pre-registration
   - Characterize any divergence: in direction, magnitude, or kind?

2. **QA verification:** Before updating beliefs, confirm that pipeline QA checks passed (if applicable).
   - Link to QA output if available
   - If QA checks haven't been run, flag this

3. **Confirmatory vs. exploratory:** Explicitly label each conclusion:
   - **Confirmatory:** pre-registered analysis with pre-specified decision criteria
   - **Exploratory:** post-hoc discovery (valid but needs different evidential weight)

4. **Goalpost check:** Has the interpretation drifted from pre-registered decision criteria?
   - Compare actual decision criteria used against the "Decision Criteria" section
   - Flag if the pre-registration was modified after analysis began (compare `created` date in pre-registration against today)

If no pre-registration exists, skip this step but note in the output: "No pre-registration on file. Consider `/science:pre-register` for future analyses."
```

- [ ] **Step 3: Update the interpretation template**

In `templates/interpretation.md`, add after `<!-- ASPECT SECTIONS INSERTED HERE -->`:

```markdown
## Pre-registration Cross-check (if applicable)

<!--
  If a pre-registration document exists for the hypotheses or inquiry being interpreted:
  - Does the result match expectations? If not, characterize the divergence.
  - Have QA checks passed?
  - Label each conclusion as confirmatory (pre-registered) or exploratory (post-hoc).
  - Has the interpretation drifted from pre-registered decision criteria?

  If no pre-registration exists, note: "No pre-registration on file."
-->
```

- [ ] **Step 4: Update the "After Writing" section**

In `commands/interpret-results.md`, in the `## After Writing` section, update item 5 (Suggest next steps). Change the `/science:research-gaps` reference to `/science:next-steps`:

Replace:
```markdown
   - `/science:research-gaps` — to reassess coverage given new knowledge
```
With:
```markdown
   - `/science:next-steps` — to reassess coverage and priorities given new knowledge
```

Also add:
```markdown
   - `/science:compare-hypotheses` — if results are ambiguous between competing explanations
   - `/science:bias-audit` — to check for post-hoc rationalization
```

- [ ] **Step 5: Commit**

```bash
git add commands/interpret-results.md templates/interpretation.md
git commit -m "feat: add pre-registration cross-check to interpret-results"
```

---

## Chunk 3: Coherence Cleanup

### Task 11: Merge `research-gaps` into `next-steps`

**Files:**
- Modify: `commands/next-steps.md` (rewrite to include gap analysis + save output)
- Modify: `commands/research-gaps.md` (convert to deprecated alias)

- [ ] **Step 1: Rewrite `next-steps` to include gap analysis and save output**

Replace the full content of `commands/next-steps.md` with:

```markdown
---
description: Synthesize recent progress, analyze coverage gaps, and suggest next actions. Use at session start, when the user says "what should I work on", "next steps", "priorities", "what's next", "gaps", or "what am I missing". Replaces the former research-gaps command.
---

# Next Steps

Synthesize the current state of the project, analyze coverage gaps, and suggest prioritized next actions.
Use `$ARGUMENTS` as optional filters, for example: `dev only`, `this week`, `related to h01`, `research tasks`, `gaps only`.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally, read (skip any that don't exist):
1. `tasks/active.md`
2. Recent completed tasks: scan `tasks/done/` for the most recent file
3. `specs/hypotheses/` — status of each hypothesis
4. `specs/scope-boundaries.md` — project scope
5. `doc/questions/` — open, high-priority questions
6. `doc/topics/` — current topic coverage
7. `doc/papers/` — paper coverage
8. `doc/meta/next-steps-*.md` — prior next-steps analyses (most recent)

Also run: `git log --oneline -15 --format="%h %s (%cr)"`

## Workflow

### 1. Recent Progress

Summarize what's been accomplished recently by combining:
- Recently completed tasks from `tasks/done/`
- Recent git commits

Group by theme (research, development, documentation) rather than listing chronologically.
Keep to 5-8 bullet points maximum.

### 2. Current State

From `tasks/active.md`, show:
- **P0 tasks** (critical path) — full detail
- **P1 tasks** (active work) — title and status
- **Blocked tasks** — what's blocking them
- **Hypothesis status** — one-line summary per hypothesis from `specs/hypotheses/`

### 3. Coverage Gap Analysis

Analyze project coverage across five dimensions:

1. **Concepts/topics:** What core topics are missing or too shallow?
2. **Evidence quality:** What claims rely on weak, old, or uncorroborated support?
3. **Contradictions:** Where do findings conflict without explicit resolution?
4. **Testability:** Which hypotheses lack falsifiability criteria or clear next tests?
5. **Data feasibility:** Where are key variables/questions blocked by missing datasets?

Focus on decision impact, not document volume.

Present as a coverage map: **Strong / Partial / Missing** for each major area.

### 4. Suggested Next Steps

Recommend 3-5 actions based on:
- High-impact gaps from the coverage analysis
- Unblocked tasks that were previously blocked
- Highest-priority active tasks without recent commits
- Stale tasks (active but no related activity in >7 days)
- Open high-priority questions that could become tasks

For each suggestion, include:
- The task ID (if it exists) or "new task" if suggesting something not yet tracked
- A brief rationale (1 sentence)
- The suggested command to run (e.g., `/science:research-topic`, `/science:tasks add ...`)

## Writing

Save output to `doc/meta/next-steps-<YYYY-MM-DD>.md` with these sections:

```markdown
# Next Steps — YYYY-MM-DD

## Recent Progress
<grouped bullet points>

## Current State
<task summary, hypothesis status>

## Coverage Gaps
### Coverage Map
| Area | Coverage | Key Gap |
|---|---|---|
| <area> | Strong/Partial/Missing | <gap> |

### High-Impact Gaps
<prioritized gap descriptions with evidence links>

## Recommended Next Actions
| Priority | Action | Rationale | Command |
|---|---|---|---|
| P1 | <action> | <why now> | <command> |
```

## Format

Display the output in the terminal using rich formatting:
- Section headers as `##`
- Tables for task lists and coverage maps
- Bullet lists for progress and suggestions
- Bold for emphasis on critical items

> **Note:** This command saves output to disk (unlike the previous read-only version). This is intentional — ephemeral analysis that disappears after the session is less useful than a versioned record.

## After Writing

1. Save to `doc/meta/next-steps-<YYYY-MM-DD>.md`.
2. Offer to create tasks from recommended items: "Create tasks from these suggestions?"
   - If accepted, run `science-tool tasks add` for each recommended task with appropriate priority, type, and related entities
3. Cross-link relevant items in `doc/questions/`.
4. Commit: `git add -A && git commit -m "doc: next steps and gap analysis <date>"`

## Process Reflection

Reflect on the **gap analysis framework** and the **prioritization workflow**.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — next-steps

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
- Be concrete and specific, not generic
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence
- If everything worked smoothly, a single "No friction encountered" is fine

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"
```

- [ ] **Step 2: Convert `research-gaps` to deprecated alias**

Replace the full content of `commands/research-gaps.md` with:

```markdown
---
description: "[Deprecated] Use /science:next-steps instead."
---

# Research Gaps

> **Deprecated:** This command is an alias. Run `/science:next-steps` for the full workflow (includes gap analysis).

Execute `/science:next-steps $ARGUMENTS`.
```

- [ ] **Step 3: Verify deprecated alias follows existing pattern**

Run: `diff <(head -9 commands/summarize-topic.md) <(head -9 commands/research-gaps.md)`
Expected: Same structure — YAML frontmatter with `[Deprecated]`, heading, blockquote, execute redirect.

- [ ] **Step 4: Commit**

```bash
git add commands/next-steps.md commands/research-gaps.md
git commit -m "feat: merge research-gaps into next-steps, deprecate research-gaps alias"
```

---

### Task 12: Merge `build-dag` into `sketch-model`

**Files:**
- Modify: `commands/sketch-model.md` (add causal mode detection)
- Modify: `commands/build-dag.md` (convert to deprecated alias)

- [ ] **Step 1: Add causal mode detection to `sketch-model`**

In `commands/sketch-model.md`, make the following changes:

**Update the description** in the YAML frontmatter to include causal triggers:

Replace the existing `description:` with:
```yaml
description: Sketch a research model interactively. Captures variables, relationships, data sources, and unknowns as an inquiry subgraph. Auto-detects causal mode when the causal-modeling aspect is active or user language signals causal intent. Use when the user wants to explore what variables matter, how things connect, or how to approach a question computationally. Also use when the user says "sketch", "what variables", "how would I model", "what affects what", "causal", "DAG", "confounders", or "treatment effect".
```

**Update the prerequisite** to conditionally load the causal-dag skill:

Replace:
```markdown
> **Prerequisite:** Load the `knowledge-graph` skill for ontology reference before starting.
```
With:
```markdown
> **Prerequisites:**
> - Load the `knowledge-graph` skill for ontology reference before starting.
> - If causal mode is active (see below): also load the `causal-dag` skill.
```

**Add a causal mode detection section** after `## Overview` and before `## Tool invocation`:

```markdown
## Causal Mode Detection

This command auto-detects causal intent and switches to causal DAG mode when appropriate. Causal mode activates when **any** of the following are true:

1. The `causal-modeling` aspect is active in `science.yaml`
2. User language in `$ARGUMENTS` signals causal intent: "causal", "DAG", "confounders", "treatment effect", "what causes", "intervention"
3. Existing causal inquiries exist in the project (check `science-tool inquiry list` for type=causal)

When causal mode is active:
- Load the `causal-dag` skill for pitfall patterns and ontology
- Create the inquiry with `--type causal` instead of default
- Use `scic:causes` and `scic:confounds` edges instead of `sci:feedsInto`
- Set the estimand (treatment → outcome) using `inquiry set-estimand`
- Require justification for every causal edge (claim with provenance and confidence)
- Ask about confounders for every proposed causal edge
- Suggest `/science:critique-approach` as the next step

When causal mode is NOT active:
- Follow the standard sketch workflow (variables, relationships, unknowns)
- Use `sci:feedsInto` for data flow edges, `skos:related` for uncertain associations
- Missing provenance and `sci:Unknown` nodes are fine
- Suggest `/science:specify-model` as the next step
```

**Update Step 2 (Interactive conversation)** to include causal-mode questions:

After question 3 ("What do you think affects what?"), add:

```markdown
**If causal mode is active, also ask:**

4. **Treatment:** "What is the treatment or intervention? (What do you want to manipulate or study the effect of?)"
5. **Outcome:** "What is the outcome? (What do you want to measure the effect on?)"
6. **Confounders:** "What variables affect both the treatment and outcome? (These are potential confounders.)"
7. **Evidence for causation:** For each proposed causal relationship: "Why do you believe A causes B? What evidence supports this?"
```

**Update Step 3 (Build the inquiry subgraph)** to handle causal mode:

After item 1 (Create the inquiry), add:

```markdown
**If causal mode:** create with `--type causal`:
```bash
science-tool inquiry init "<slug>" \
  --label "<descriptive label>" \
  --target "<hypothesis:hNN or question:qNN>" \
  --type causal
```

After item 4 (Add edges), add:

```markdown
**If causal mode:** use causal predicates:
```bash
science-tool inquiry add-edge "<slug>" "concept:<from>" "scic:causes" "concept:<to>"
science-tool graph add claim "<justification>" --source "<ref>" --confidence <0-1>
```

And set the estimand:
```bash
science-tool inquiry set-estimand "<slug>" --treatment "concept/<treatment>" --outcome "concept/<outcome>"
```

**Update Step 5 (Finalize)** next step suggestions:

Replace the current suggestions with:
```markdown
Suggest next steps:
1. If causal mode: `/science:critique-approach <slug>` to review the DAG for missing confounders
2. If non-causal and sketch looks good: `/science:specify-model <slug>` to add rigor
3. If more background needed: `/science:research-topic` or `/science:search-literature`
4. If hypotheses need work: `/science:add-hypothesis`
```

- [ ] **Step 2: Convert `build-dag` to deprecated alias**

Replace the full content of `commands/build-dag.md` with:

```markdown
---
description: "[Deprecated] Use /science:sketch-model instead — it auto-detects causal mode."
---

# Build a Causal DAG

> **Deprecated:** This command is an alias. Run `/science:sketch-model` for the full workflow (auto-detects causal mode when the `causal-modeling` aspect is active or user language signals causal intent).

Execute `/science:sketch-model $ARGUMENTS`.
```

- [ ] **Step 3: Commit**

```bash
git add commands/sketch-model.md commands/build-dag.md
git commit -m "feat: merge build-dag into sketch-model with causal mode detection, deprecate build-dag alias"
```

---

### Task 13: Update inquiry status lifecycle in relevant commands

**Files:**
- Modify: `commands/sketch-model.md` (set `sketch` status — already implied, make explicit)
- Modify: `commands/critique-approach.md` (set `critiqued` status)
- Modify: `commands/plan-pipeline.md` (update to reference `critiqued` status)
- Modify: `commands/review-pipeline.md` (set `reviewed` status)

- [ ] **Step 0: Verify `specify-model` already sets `specified` status**

Read `commands/specify-model.md` and confirm it sets the inquiry status to `specified`. If it doesn't, add an explicit status-setting instruction after the inquiry is finalized.

- [ ] **Step 1: Make status setting explicit in `sketch-model`**

In `commands/sketch-model.md`, in Step 4 (Visualize and summarize), add after `Save the inquiry document`:

```markdown
The inquiry status is `sketch` at this stage.
```

- [ ] **Step 2: Add `critiqued` status to `critique-approach`**

In `commands/critique-approach.md`, after the closing ``` of the review report template in Step 7 and before `### Step 8: Present findings`, add:

```markdown
Update the inquiry status to `critiqued`.

Note: this status indicates the inquiry has been through critical review, NOT that it passed. The review report documents what was found.
```

- [ ] **Step 3: Update `plan-pipeline` to reference `critiqued` status**

In `commands/plan-pipeline.md`, in Step 1, update the status check. After the existing warning about `sketch` status, add:

```markdown
If status is `specified` but not `critiqued`, warn: "This inquiry hasn't been through critique yet. Consider running `/science:critique-approach <slug>` first. Proceeding anyway."
```

Also update Step 5 to explicitly set the `planned` status (already sets it — just verify).

- [ ] **Step 4: Add `reviewed` status to `review-pipeline`**

In `commands/review-pipeline.md`, after the closing ``` of the review report template in Step 3 and before `### Step 4: Present to user`, add:

```markdown
Update the inquiry status to `reviewed`.
```

- [ ] **Step 5: Commit**

```bash
git add commands/sketch-model.md commands/critique-approach.md commands/plan-pipeline.md commands/review-pipeline.md
git commit -m "feat: formalize inquiry status lifecycle (sketch → specified → critiqued → planned → reviewed)"
```

---

### Task 14: Update cross-references across all commands

**Files:**
- Modify: `commands/interpret-results.md` (already done in Task 10 — verify)
- Modify: `commands/research-gaps.md` (already done in Task 11)
- Modify: `commands/discuss.md` (update suggested next steps if it references research-gaps)
- Modify: `commands/add-hypothesis.md` (add pre-register as suggested next step)

- [ ] **Step 1: Check `discuss.md` for stale references**

Read `commands/discuss.md` and search for references to `research-gaps` or deprecated commands. Update any found to use `next-steps` instead.

- [ ] **Step 2: Add pre-register suggestion to `add-hypothesis`**

In `commands/add-hypothesis.md`, in the `## After Writing` section, add after item 4 (Suggest papers):

```markdown
5. If the hypothesis is testable with planned analysis, suggest: `/science:pre-register` — to formalize expectations before running the analysis.
```

Update the numbering of the subsequent commit step.

- [ ] **Step 3: Update all stale cross-references across the project**

Search the entire project for references to deprecated commands:

Run: `grep -r "research-gaps\|build-dag\|summarize-topic\|summarize-paper" commands/ templates/ aspects/ references/ README.md --include="*.md" -l`

Known files requiring updates (verify and fix each):
- `commands/create-project.md` — references `/science:build-dag` → `/science:sketch-model` and `/science:research-gaps` → `/science:next-steps`
- `commands/search-literature.md` — references `/science:research-gaps` → `/science:next-steps`
- `templates/interpretation.md` — references `research-gaps` in a comment → `next-steps`
- `aspects/causal-modeling/causal-modeling.md` — references `build-dag` → `sketch-model`
- `references/project-structure.md` — references `10-research-gaps.md` → add note about `doc/meta/next-steps-*.md`

Do NOT modify the deprecated alias files themselves (`commands/research-gaps.md`, `commands/build-dag.md`, `commands/summarize-topic.md`, `commands/summarize-paper.md`).

Do NOT modify `README.md` here — Task 15 handles it separately.

- [ ] **Step 4: Commit**

```bash
git add commands/
git commit -m "fix: update cross-references to use non-deprecated command names"
```

---

### Task 15: Update README with final command table

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the command table**

Update the `## Commands` table in `README.md` to reflect the final state:
- Add: `pre-register`, `compare-hypotheses`, `bias-audit`
- Remove: `build-dag` (now a deprecated alias)
- Update: `next-steps` description to include gap analysis
- Update: `critique-approach` description to include sensitivity analysis

Replace the command table with:

```markdown
| Command | Description |
|---|---|
| `/science:status` | Curated project orientation — hypotheses, questions, activity, next steps |
| `/science:create-project` | Scaffold a new research project with full directory structure |
| `/science:import-project` | Add Science framework to an existing project without restructuring |
| `/science:research-paper` | Research and synthesize a paper (LLM knowledge → web search → PDF) |
| `/science:research-topic` | Research and synthesize a topic with project context |
| `/science:next-steps` | Gap analysis + progress synthesis + prioritized recommendations |
| `/science:discuss` | Structured critical discussion for ideas, hypotheses, or approaches |
| `/science:tasks` | Manage research and development tasks — add, complete, defer, list, filter |
| `/science:search-literature` | Search OpenAlex/PubMed, rank results, and create a prioritized reading queue |
| `/science:find-datasets` | Discover and document candidate datasets from public repositories |
| `/science:add-hypothesis` | Develop and refine a hypothesis interactively |
| `/science:pre-register` | Formalize expectations and decision criteria before analysis |
| `/science:compare-hypotheses` | Head-to-head evaluation of competing explanations |
| `/science:bias-audit` | Systematic bias and threat-to-validity check |
| `/science:interpret-results` | Interpret results with pre-registration cross-check |
| `/science:sketch-model` | Sketch a research model (auto-detects causal mode) |
| `/science:specify-model` | Formalize a model with full evidence provenance |
| `/science:critique-approach` | Review model for problems, sensitivity analysis |
| `/science:plan-pipeline` | Generate implementation plan with QA checkpoints |
| `/science:review-pipeline` | Audit plan against evidence rubric with QA coverage |
| `/science:create-graph` | Build a knowledge graph from project documents |
| `/science:update-graph` | Incrementally update the graph after document changes |
```

- [ ] **Step 2: Update the "What It Does" section**

Add three new bullets for the reasoning capabilities:

```markdown
- **Pre-register expectations** — formalize predictions and decision criteria before analysis
- **Compare competing hypotheses** — head-to-head evidence evaluation with discriminating predictions
- **Audit for biases** — systematic cognitive and methodological bias checklist
```

- [ ] **Step 3: Update the Typical Workflow section**

Add new phases for pre-registration, comparison, and bias audit. Update the workflow to show:

```markdown
### 2. State your hypotheses

...

After adding hypotheses, formalize your expectations:

```
/science:pre-register
```

### 4b. Compare competing explanations

```
/science:compare-hypotheses
```

When 2+ hypotheses exist for the same phenomenon, this command performs a structured head-to-head comparison — identifying discriminating predictions and crucial experiments.

### 7b. Audit for biases

```
/science:bias-audit
```

Systematic check of cognitive and methodological biases against current project state. Especially valuable before interpreting results or when a project feels "too settled".
```

- [ ] **Step 4: Update the iteration example**

```markdown
research-topic → add-hypothesis → pre-register → search-literature → research-paper ×3
→ compare-hypotheses → next-steps → discuss → bias-audit → update-graph
→ sketch-model → specify-model → critique-approach
→ find-datasets → plan-pipeline → review-pipeline
→ [run analysis] → interpret-results → next-steps
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README with reasoning commands, merged commands, and updated workflow"
```

---

### Task 16: Update `validate.sh` for new document types

**Files:**
- Modify: `scripts/validate.sh`

- [ ] **Step 1: Read the current validate.sh**

Read `scripts/validate.sh` in full to understand the existing validation structure.

- [ ] **Step 2: Add validation for pre-registration documents**

Add a new validation section (following the existing pattern of numbered sections) that checks:

```bash
# --- Pre-registration documents ---
for f in doc/meta/pre-registration-*.md; do
    [ -f "$f" ] || continue
    # Check for required sections
    for section in "Hypotheses Under Test" "Expected Outcomes" "Decision Criteria" "Null Result Plan"; do
        if ! grep -q "## $section" "$f"; then
            warn "Pre-registration $f missing section: $section"
        fi
    done
done
```

- [ ] **Step 3: Add validation for comparison documents**

```bash
# --- Hypothesis comparison documents ---
for f in doc/discussions/comparison-*.md; do
    [ -f "$f" ] || continue
    for section in "Hypotheses Compared" "Evidence Inventory" "Discriminating Predictions" "Current Verdict"; do
        if ! grep -q "## $section" "$f"; then
            warn "Comparison $f missing section: $section"
        fi
    done
done
```

- [ ] **Step 4: Add validation for bias audit documents**

```bash
# --- Bias audit documents ---
for f in doc/meta/bias-audit-*.md; do
    [ -f "$f" ] || continue
    for section in "Cognitive Biases" "Methodological Biases" "Summary"; do
        if ! grep -q "## $section" "$f"; then
            warn "Bias audit $f missing section: $section"
        fi
    done
done
```

- [ ] **Step 5: Update the research-gaps validation**

The existing validation checks `doc/10-research-gaps.md`. Update to also accept `doc/meta/next-steps-*.md` as the new location. Add section validation for the new format:

Find the section that validates `doc/10-research-gaps.md` and update:

```bash
# Legacy path — also check new path
if [ ! -f doc/10-research-gaps.md ]; then
    # Check for new-style next-steps files
    if ! ls doc/meta/next-steps-*.md 1>/dev/null 2>&1; then
        info "No gap analysis found (doc/10-research-gaps.md or doc/meta/next-steps-*.md)"
    fi
fi

# --- Next-steps documents (new format) ---
for f in doc/meta/next-steps-*.md; do
    [ -f "$f" ] || continue
    for section in "Recent Progress" "Current State" "Coverage Gaps" "Recommended Next Actions"; do
        if ! grep -q "## $section" "$f"; then
            warn "Next-steps $f missing section: $section"
        fi
    done
done
```

- [ ] **Step 6: Commit**

```bash
git add scripts/validate.sh
git commit -m "feat: add validation for pre-registration, comparison, and bias-audit documents"
```

---

## Deferred Work

The following items from the spec are intentionally deferred to a follow-up plan:

- **Spec 3.3: Standardize document frontmatter across existing documents.** New templates created in this plan use the standard frontmatter format. Migrating existing templates (`hypothesis.md`, `discussion.md`, `interpretation.md`) and adding `validate.sh` checks for frontmatter integrity is a separate effort. The new templates serve as the reference format.
- **Generalizing `critique-approach` to non-causal models.** The sensitivity analysis added here uses causal terminology. Adapting it for conceptual models requires rethinking the command's scope beyond this plan.
- **Adding Process Reflection to `sketch-model`.** The existing command lacks it; adding it while modifying for causal mode detection is a natural follow-up.

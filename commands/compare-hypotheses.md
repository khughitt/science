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

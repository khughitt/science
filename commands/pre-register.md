---
description: Formalize expectations before analysis to prevent post-hoc rationalization. Use after add-hypothesis or plan-pipeline and before running analysis — to state expectations or what would change the user's mind.
---

# Pre-register Expectations

Formalize the user's expectations, decision criteria, and null-result plans before analysis begins.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `.ai/templates/pre-registration.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/pre-registration.md`.
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

**Pilot experiments:** If this is a pilot (1-2 seeds, small N, exploratory scope), explicitly state what it CAN and CANNOT establish. A pilot can suggest directions and calibrate effect sizes but cannot confirm or refute a hypothesis. Frame decision criteria accordingly — a pilot's null result means "insufficient signal to justify scaling up", not "hypothesis is wrong."

### 4b. Plan for Suspicious/Unexpected Results

- What would "too good to be true" look like? (e.g., AUC > 0.95, perfect accuracy)
- What inflators could produce misleading results? (data leakage, confounds, overfitting)
- What checks would you run before accepting an unexpectedly strong result?

Skip this if the analysis type doesn't have a meaningful "too good" threshold.

### 4c. Metric Selection Rationale (if applicable)

If the primary metric has changed from prior analyses, or if the metric choice is non-obvious:
- What metric are you using and why?
- What motivated the change from the prior metric (if applicable)?
- What are the known limitations of this metric?

### 5. Separate Confirmatory from Exploratory

- Which analyses are pre-registered (confirmatory)?
- Which are explicitly exploratory?
- Are there analyses you plan to run "just to see what happens"? Label them.

### 5b. Sampling Strategy Rationale (if applicable)

If the experimental design involves non-obvious sampling decisions (stratified sampling, subsampling from a larger population, context selection), document the rationale and trade-offs:
- What sampling strategy was chosen?
- What was the alternative?
- Why was this approach preferred?

Omit when sampling is straightforward (e.g., "use all available data").

## Writing

After the conversation, write the pre-registration document using `.ai/templates/pre-registration.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/pre-registration.md`.

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

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:pre-register" \
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

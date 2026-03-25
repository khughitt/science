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

**Process bias:**
- Pace of iteration: how many commits/analyses in the recent period? Rapid single-analyst iteration creates momentum bias.
- Perspective diversity: has anyone else reviewed the findings or methodology?
- Cooling-off period: how much time elapsed between running analyses and interpreting results?
- Use `git log --oneline -20 --format="%h %an %s (%cr)"` to assess iteration pace and contributor diversity.

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
- For each identified confound, rate severity and fixability in a matrix:

| Confound | Severity | Fixability | Mitigation |
|---|---|---|---|
| _confound_ | HIGH/MED/LOW | EASY/HARD/INFEASIBLE | _action_ |

This makes mitigation recommendations actionable — HIGH severity + EASY to fix should be addressed before running experiments; MED severity + INFEASIBLE should be acknowledged as limitations.

**Publication bias:**
- Are literature searches biased toward positive results?
- Are null-result papers included in the review?
- For in-progress experimental projects (not systematic literature review), focus on whether background literature searches for context/methods may be biased. Mark "not applicable" if no systematic literature review was conducted.

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

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:bias-audit" \
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

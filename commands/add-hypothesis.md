---
description: Develop and refine a research hypothesis interactively. Use when the user wants to add a new hypothesis, formalize a conjecture, or develop a testable claim for their research project. Also use when the user says "I think", "what if", "could it be that", or proposes a potential mechanism or relationship.
---

# Add a Hypothesis

Develop a structured, falsifiable hypothesis from the user's input in `$ARGUMENTS`.

## Before Starting

1. Read the `research-methodology` skill for hypothesis development guidelines.
2. Read `templates/hypothesis.md` for the required document structure.
3. Read `specs/research-question.md` to understand the project scope.
4. Read existing hypotheses in `specs/hypotheses/` to understand what's already proposed and avoid duplication.
5. Check `doc/08-open-questions.md` — the new hypothesis may address an existing open question.

## Interactive Refinement

Have a natural conversation with the user to develop the hypothesis. The questions below are guidelines — use your judgment about which are needed based on how much context the user has already provided. If the user's initial input is already specific and falsifiable, you can skip ahead to writing. If it's vague, work through the relevant questions.

### 1. Clarify the Claim
- What specifically are you claiming? 
- Can you state it as a single, clear sentence?
- Is this about a **causal relationship**, a **correlation**, a **mechanism**, or a **prediction**?

### 2. Test for Falsifiability
- What evidence would **disprove** this hypothesis?
- Is there a specific observation, measurement, or experimental result that would make you abandon it?
- If you can't name one, the hypothesis needs to be more specific.

### 3. Identify Predictions
- If this hypothesis is correct, what else should we observe?
- Are there downstream consequences we can check?
- Can we make quantitative predictions, or only qualitative ones?

### 4. Assess Required Evidence
- What data do we need to test this?
- Is that data available, or does it need to be generated?
- What analysis methods would be appropriate?

### 5. Check for Connections
- Does this relate to existing hypotheses? How?
- Does this imply changes to the causal model?
- Does this address any open questions?

## Writing

After the conversation, write the hypothesis document following `templates/hypothesis.md`.

### Assigning an ID

Check existing files in `specs/hypotheses/` and assign the next sequential number.

- **Filename:** lowercase `h` prefix: `h01-short-title.md`, `h02-short-title.md`, etc.
- **In-document ID:** uppercase `H` prefix: `H01`, `H02`, etc. (used for cross-referencing in prose)

### Setting Initial Status

New hypotheses start as `proposed` unless the user presents existing evidence, in which case `under-investigation` may be appropriate.

## After Writing

1. Save to `specs/hypotheses/hNN-short-title.md`
2. Update `doc/07-hypotheses.md` with a one-line summary of the new hypothesis.
3. If the hypothesis addresses an open question, update `doc/08-open-questions.md`.
4. If the hypothesis implies causal relationships, note that `models/causal-dag.*` may need updating and mention this to the user.
5. Suggest 2-3 papers that may be relevant to testing this hypothesis (from LLM knowledge; cross-check titles and authors via web search before presenting).
6. Commit: `git add -A && git commit -m "hypothesis: add H<NN> - <short title>"`

## Process Reflection

Reflect on the **hypothesis template** sections and the **falsifiability/predictions** prompts.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — add-hypothesis

**Template/structure friction:**
- Any section you left empty, filled with boilerplate, or that felt forced

**Missing capture:**
- Information you wanted to record but had no natural place for

**Guidance issues:**
- Command instructions that were confusing, contradictory, or didn't help

**What worked well:**
- A section or instruction that genuinely improved the output
```

Guidelines:
- Be concrete and specific, not generic ("the Causal Model section was empty because no DAG exists yet" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

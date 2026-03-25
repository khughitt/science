---
description: Develop and refine a research hypothesis interactively. Use when the user wants to add a new hypothesis, formalize a conjecture, or organize a set of uncertain claims around one research direction. Also use when the user says "I think", "what if", "could it be that", or proposes a potential mechanism or relationship.
---

# Add a Hypothesis

Develop a structured hypothesis from the user's input in `$ARGUMENTS`.

In this project, a hypothesis is an organizing conjecture, not a settled fact. Treat it as a bundle of uncertain claims that may later gain or lose support.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `docs/claim-and-evidence-model.md`.
2. Read `templates/hypothesis.md`.
3. Read existing hypotheses in `specs/hypotheses/` to avoid duplication.
4. Check `doc/questions/` — the new hypothesis may address an existing open question.

## Interactive Refinement

Have a natural conversation with the user to develop the hypothesis. The questions below are guidelines — use judgment based on how much context the user has already provided.

### 1. Clarify the Conjecture
- What is the overall research idea?
- What are the main claims inside it?
- Which claims are causal, mechanistic, predictive, or descriptive?

Try to separate:
- the high-level hypothesis
- the concrete `claim` or `relation_claim` units that would actually be tested

### 2. Define the Claim Bundle

For each important subclaim, identify:
- subject, predicate, and object when it is naturally relational
- what would count as supporting evidence
- what would count as disputing evidence
- whether the claim is currently speculative, fragile, or already somewhat supported

### 3. Test for Falsifiability
- What evidence would materially lower confidence in this hypothesis?
- What observation or result would force revision of one of its key claims?
- If the user cannot name a disconfirming result, the hypothesis needs to be sharper.

### 4. Identify Predictions And Evidence Needs
- If the hypothesis is useful, what downstream predictions follow?
- What empirical-data evidence, simulation evidence, or literature evidence would shift belief?
- What would be the most discriminating test?

### 5. Check Connections
- Does this relate to existing hypotheses, questions, or inquiries?
- Does it imply candidate `relation_claim`s for the graph?
- Does it suggest a future inquiry or experiment?

## Writing

After the conversation, write the hypothesis document following `templates/hypothesis.md`.

Write the hypothesis as:
- one organizing conjecture
- a small set of explicit subclaims or relation-claims
- a skeptical assessment of current uncertainty

Do not frame a single paper or result as proving the hypothesis.

### Assigning an ID

Check existing files in `specs/hypotheses/` and assign the next sequential number.

- **Filename:** lowercase `h` prefix: `h01-short-title.md`, `h02-short-title.md`, etc.
- **Frontmatter `id`:** uses the filename stem: `"hypothesis:h01-short-title"`, `"hypothesis:h02-short-title"`, etc.
- **Prose references:** uppercase `H` prefix: `H01`, `H02`, etc.

### Populating Frontmatter

- `status`: `"proposed"` unless the user already has active investigation underway, then `"under-investigation"`
- `related`: list related hypotheses, questions, or topics
- `source_refs`: papers or prior project artifacts cited in the document
- `created` and `updated`: today's date

Avoid status labels like `supported` or `refuted` as the default outcome of authoring a new hypothesis.

## After Writing

1. Save to `specs/hypotheses/hNN-short-title.md`.
2. If the hypothesis addresses an open question, update the relevant file in `doc/questions/`.
3. If the hypothesis naturally decomposes into graph-native claims, note the likely `relation_claim`s the user may want to formalize later.
4. Suggest 2-3 papers that may be relevant to testing this hypothesis.
Source-check titles and authors via web search before presenting them.
5. If the hypothesis is ready to be formalized in the graph, suggest `/science:specify-model`.
6. If the user wants to design a test before running it, suggest `/science:pre-register`.
7. Commit: `git add -A && git commit -m "hypothesis: add H<NN> - <short title>"`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
  --target "command:add-hypothesis" \
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

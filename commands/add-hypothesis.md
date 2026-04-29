---
description: Develop and refine a research hypothesis interactively. Use when the user wants to add a hypothesis, formalize a conjecture, or organize uncertain propositions around one research direction.
---

# Add a Hypothesis

Develop a structured hypothesis from the user's input in `$ARGUMENTS`.

In this project, a hypothesis is an organizing conjecture, not a settled fact. Treat it as a bundle of uncertain propositions that may later gain or lose support.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `${CLAUDE_PLUGIN_ROOT}/docs/proposition-and-evidence-model.md`.
2. Read `.ai/templates/hypothesis.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/hypothesis.md`.
3. Read existing hypotheses in `specs/hypotheses/` to avoid duplication.
4. Check `doc/questions/` — the new hypothesis may address an existing open question.

## Interactive Refinement

Have a natural conversation with the user to develop the hypothesis. The questions below are guidelines — use judgment based on how much context the user has already provided.

### 1. Clarify the Conjecture
- What is the overall research idea?
- What are the main propositions inside it?
- Which propositions are causal, mechanistic, predictive, or descriptive?

Try to separate:
- the high-level hypothesis
- the concrete proposition units that would actually be tested

### 2. Define the Proposition Bundle

For each important proposition, identify:
- subject, predicate, and object when it is naturally relational
- whether it is best treated as `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`
- what would count as supporting evidence
- what would count as disputing evidence
- whether the proposition is currently speculative, fragile, or already somewhat supported

If a proposition relies on an indirect proxy, note that early and record the likely `measurement_model` rather than treating the proxy as direct evidence.

### 3. Test for Falsifiability
- What evidence would materially lower confidence in this hypothesis?
- What observation or result would force revision of one of its key propositions?
- If the user cannot name a disconfirming result, the hypothesis needs to be sharper.

### 4. Identify Predictions And Evidence Needs
- If the hypothesis is useful, what downstream predictions follow?
- What empirical-data evidence, simulation evidence, or literature evidence would shift belief?
- What would be the most discriminating test?

If the hypothesis has genuinely competing structural readings, note the likely rival-model packet:
- shared observables
- discriminating predictions
- an optional `current_working_model` only if one already exists

### 5. Check Connections
- Does this relate to existing hypotheses, questions, or inquiries?
- Does it imply candidate propositions for the graph?
- Does it suggest a future inquiry or experiment?

## Writing

After the conversation, create the hypothesis with `science-tool hypothesis create`. The tool assigns the next sequential `hNN` ID, places the file under `specs/hypotheses/`, and writes canonical frontmatter (`id`, `type`, `title`, `status`, `related`, `source_refs`, `created`, `updated`). It also runs prospective validation against the project's audit rules — unresolved references emit warnings, structural problems block.

```bash
uv run science-tool hypothesis create "<short title>" \
  --related <question:qNN-...> \
  --related <hypothesis:hMM-...> \
  --source-ref <paper-or-package-ref>
```

The command prints the chosen ID (e.g. `hypothesis:h03-short-title`) and the file path. Do NOT pre-write the file or hand-pick the ID — let the tool sequence and validate. If the user wants a specific slug, pass `--slug <slug>`; if they need a literal ID, pass `--id hypothesis:<local-part>`.

After the file is created, open it and fill in the body using `.ai/templates/hypothesis.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/hypothesis.md` as the writing reference. Preserve the frontmatter `science-tool` produced; only edit the body. Use `science-tool hypothesis edit <ref>` (or `science-tool entity edit <ref>`) for later metadata changes — both run prospective validation and update `updated` automatically.

Write the hypothesis as:
- one organizing conjecture
- a small set of explicit propositions
- a skeptical assessment of current uncertainty

Do not frame a single paper or result as proving the hypothesis.

### Naming Conventions

- **Filename:** lowercase `h` prefix: `h01-short-title.md`, `h02-short-title.md`, etc. (assigned by `science-tool hypothesis create`).
- **Frontmatter `id`:** matches the filename stem: `"hypothesis:h01-short-title"`.
- **Prose references:** uppercase `H` prefix: `H01`, `H02`, etc.

### Body And Optional Frontmatter

`science-tool hypothesis create` defaults `status` to `proposed`. The supported life-cycle values are `proposed`, `under-investigation`, `partially-supported`, `supported`, `weakened`, and `refuted`. Use `--status under-investigation` only if active testing is already underway. Avoid `supported`, `weakened`, or `refuted` as the default outcome of authoring a new hypothesis — those are evidence-based exit states.

Use optional layered-claim fields only when they reduce ambiguity, by editing the file body and frontmatter after creation:
- `claim_layer`
- `identification_strength`
- `measurement_model`
- `supports_scope` as a review hint, not as a graph override
- `rival_model_packet`

## After Writing

1. If the hypothesis addresses an open question, link it via `science-tool entity edit <question-ref> --related hypothesis:h<NN>-<short-title>`. (Or update the question body in place if it needs prose changes.)
2. If the hypothesis naturally decomposes into graph-native propositions, note the likely propositions the user may want to formalize later.
3. Suggest 2-3 papers that may be relevant to testing this hypothesis.
Source-check titles and authors via web search before presenting them.
4. If the hypothesis is ready to be formalized in the graph, suggest `/science:specify-model`.
5. If the user wants to design a test before running it, suggest `/science:pre-register`.
6. Commit: `git add -A && git commit -m "hypothesis: add H<NN> - <short title>"`

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

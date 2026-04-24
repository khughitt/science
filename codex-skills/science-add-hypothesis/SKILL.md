---
name: science-add-hypothesis
description: "Develop and refine a research hypothesis interactively. Use when the user wants to add a hypothesis, formalize a conjecture, or organize uncertain propositions around one research direction."
---

# Add a Hypothesis

Converted from Claude command `/science:add-hypothesis`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

Develop a structured hypothesis from the user's input in the user input.

In this project, a hypothesis is an organizing conjecture, not a settled fact. Treat it as a bundle of uncertain propositions that may later gain or lose support.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `docs/proposition-and-evidence-model.md`.
2. Read `.ai/templates/hypothesis.md` first; if not found, read `templates/hypothesis.md`.
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

After the conversation, write the hypothesis document using `.ai/templates/hypothesis.md` first, then `templates/hypothesis.md`.

Write the hypothesis as:
- one organizing conjecture
- a small set of explicit propositions
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

Use optional layered-claim fields only when they reduce ambiguity:
- `claim_layer`
- `identification_strength`
- `measurement_model`
- `supports_scope` as a review hint, not as a graph override
- `rival_model_packet`

Avoid status labels like `supported` or `refuted` as the default outcome of authoring a new hypothesis.

## After Writing

1. Save to `specs/hypotheses/hNN-short-title.md`.
2. If the hypothesis addresses an open question, update the relevant file in `doc/questions/`.
3. If the hypothesis naturally decomposes into graph-native propositions, note the likely propositions the user may want to formalize later.
4. Suggest 2-3 papers that may be relevant to testing this hypothesis.
Source-check titles and authors via web search before presenting them.
5. If the hypothesis is ready to be formalized in the graph, suggest `science-specify-model`.
6. If the user wants to design a test before running it, suggest `science-pre-register`.
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

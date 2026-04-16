---
name: science-bias-audit
description: "Systematic check of cognitive and methodological biases against current project state. Use at any point, especially before interpret-results or when a project feels too settled. Also use when the user says \"check my biases\", \"what am I missing\", \"audit\", \"threats to validity\", \"blind spots\", or \"am I being fair\". Also use when the user explicitly asks for `science-bias-audit` or references `/science:bias-audit`."
---

# Bias Audit

Converted from Claude command `/science:bias-audit`.

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
   For each aspect, read `aspects/<name>/<name>.md`.
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

Perform a systematic bias and threat-to-validity check against the current project state.

Use the user input to scope the audit to a specific hypothesis, inquiry, or pipeline. If no scope is provided, audit the most recently active area (most recently modified documents).

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `.ai/templates/bias-audit.md` first; if not found, read `templates/bias-audit.md`.
2. Determine audit scope:
   - If the user input names a hypothesis: read that hypothesis and its related documents
   - If the user input names an inquiry: load the inquiry and its related documents
   - If the user input names a pipeline: read the pipeline plan and its source inquiry
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
- If no pre-registration exists, flag this as a risk and suggest `science-pre-register`.

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

Follow `.ai/templates/bias-audit.md` first, then `templates/bias-audit.md`, and fill all sections.
Save to `doc/meta/bias-audit-<slug>.md`.

## After Writing

1. Save to `doc/meta/bias-audit-<slug>.md`.
2. If HARKing risk is detected and no pre-registration exists, suggest `science-pre-register`.
3. If confirmation bias is detected, suggest `science-compare-hypotheses` to force consideration of alternatives.
4. If confounding is detected and no causal DAG exists, suggest `science-sketch-model`.
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

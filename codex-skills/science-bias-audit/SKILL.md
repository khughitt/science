---
name: science-bias-audit
description: "Systematic check of cognitive and methodological biases against current project state — threats to validity and blind spots. Use any time, especially before interpret-results or when a project feels too settled."
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
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from layout-v3 entity roots first:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
   - Read legacy specs/research-question.md only if it exists.
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
   | Files in `entities/hypotheses/` | `hypothesis-testing` |
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
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

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
   - Relevant hypotheses from `entities/hypotheses/`
   - Relevant topics from `entities/topics/`
   - Relevant papers from `entities/papers/`
   - Relevant discussions from `entities/discussions/`
   - Relevant interpretations from `entities/interpretations/`
   - Relevant searches from `entities/searches/`
   - Pipeline plans from `entities/plans/` (if applicable)
4. Read pre-registration documents from `entities/pre-registrations/*.md` (if any exist).
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

**Corpus independence (closure check):**

When the audit covers multiple artifacts at once — e.g. a hypothesis, an analysis, and an evaluation set — verify that the *audit corpus* is not a subset of the *audited corpus*. If the evidence under review derives its standard from one of the artifacts being audited, the audit can only ratify, never falsify.

For each artifact under audit, answer:
- What corpus (papers, datasets, prior runs, gold answers) does it depend on?
- Does any other artifact in the same audit derive its evidence from that same corpus?
- Is there at least one source — a held-out dataset, an external benchmark, an independent literature search — outside the artifacts' shared corpus?

If the answer to the third question is **no**, mark this as a HIGH-severity finding regardless of the other bias categories: the audit cannot generate disconfirming evidence by construction. Recommended mitigations: (a) introduce an out-of-corpus benchmark; (b) split the multi-artifact audit into single-artifact passes with independent evidence; (c) explicitly downgrade the audit's verdict from "validated" to "internally consistent."

**Author independence (self-audit check):**

Independence has an author-side analogue to the corpus check above. If the agent running this audit also authored or substantively edited the artifact under audit — e.g. drafting a pre-registration and then auditing it in the same session — the audit's independence is compromised by construction: the same reasoning that produced the artifact is unlikely to falsify it. The corpus check catches the *data*-side version of this; this catches the *author*-side version.

Check explicitly: did this agent author or substantively edit any artifact under audit? If yes, register the verdict as **"self-audit (internally consistent)"** rather than **"audited"**, and recommend an independent pass — a different agent, a cooling-off period, or an out-of-corpus reviewer — before the artifact's verdict is treated as externally validated. Like the corpus closure check, this downgrades the claim rather than ratifying it; it is a registered surface, not just a process-bias note.

### 4. Synthesize

- Rate each bias: not detected / possible / likely
- Identify the top 3 threats by severity
- For each threat, propose a specific mitigation
- Assign overall threat level: low / moderate / elevated / high

## Writing

Follow `.ai/templates/bias-audit.md` first, then `templates/bias-audit.md`, and fill all sections.

The template emits a `type: report` entity saved to
`entities/reports/<NNNN>-bias-audit-<slug>.md`, with frontmatter
`id: report:<NNNN>-bias-audit-<slug>`. Pick `<NNNN>` as the next free numeric
report prefix, and keep the filename stem exactly equal to the `report:` local
part. The validator rejects `type: report` entities outside `entities/reports/`
and rejects stem/id mismatches. If the project keeps critical reviews of
pre-registrations under a `review` entity type (`entities/review/`) and has a
precedent for it, prefer that home and set the frontmatter `type`/`id` to match.

## After Writing

1. Save to `entities/reports/<NNNN>-bias-audit-<slug>.md` (or `entities/review/` per the note above).
2. If HARKing risk is detected and no pre-registration exists, suggest `science-pre-register`.
3. If confirmation bias is detected, suggest `science-compare-hypotheses` to force consideration of alternatives.
4. If confounding is detected and no causal DAG exists, suggest `science-sketch-model`.
5. Offer to create tasks for the recommended mitigations via `science tasks add`.
6. Only commit if the user explicitly requested a commit or the session has commit approval.
   Otherwise, report the changed files and leave the workspace uncommitted.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
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

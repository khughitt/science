---
description: Interpret analysis results and feed findings back into the research framework. Use when the user has pipeline output, notebook results, statistical summaries, or preliminary findings to evaluate against hypotheses and update project priorities. Also use when the user says "I got results", "here are the findings", "what does this mean for our hypotheses", or "update the project based on these results".
---

# Interpret Results

Interpret the results specified by `$ARGUMENTS` and systematically update the research framework.

If no argument is provided, ask the user to describe their findings or point to a results file.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `templates/interpretation.md`.
2. Read active hypotheses in `specs/hypotheses/`.
3. Read `doc/questions/` for open questions.
4. Read `tasks/active.md` if it exists.
5. If the user specifies an inquiry slug, load the inquiry context:
   ```bash
   uv run --with ${CLAUDE_PLUGIN_ROOT}/science-tool science-tool inquiry show "<slug>" --format json
   ```

## Input

`$ARGUMENTS` may be:
- A path to a results file, notebook, or output directory
- A prose description of findings
- An inquiry slug (to find associated outputs)

If given a file path, read it. If given a directory, scan for result files (`.csv`, `.json`, `.md`, `.ipynb`, `.html`) and summarize what's available.

## Workflow

### 1. Summarize findings

Extract the key results. For each finding, classify signal strength:

- **Strong** — clear, replicated, large effect
- **Suggestive** — directional but uncertain
- **Null** — no effect detected (record this — it's informative)
- **Ambiguous** — multiple interpretations possible
- **Methodological** — finding about the evaluation framework itself, not the phenomenon (e.g., a metric is invalid, a baseline is inadequate)

Loaded aspects may contribute additional signal categories (e.g., **Descriptive** from `computational-analysis`, **Confounded** from `causal-modeling`). Check loaded aspect files for definitions.

Include effect sizes and confidence intervals where available.
Ask the user to clarify anything ambiguous before proceeding.

### 2. Evaluate against open questions

For each open question in `doc/questions/`:
- Is it relevant to these results?
- If relevant: does the evidence address, partially address, or leave it unchanged?
- Note new constraints, refined scope, or resolved sub-questions

If the project has the `hypothesis-testing` aspect, also perform the formal Hypothesis Evaluation contributed by that aspect.

### 3. Aspect-contributed analysis

Include any additional analysis sections contributed by loaded aspects (e.g., Causal Model Implications from `causal-modeling`, Hypothesis Evaluation table from `hypothesis-testing`, Sub-group Analysis from `computational-analysis`).

Follow the guidance in each aspect file for section content and placement.

### 4. Surface new questions

Identify questions raised by these results that didn't exist before.
For each, note:
- Priority (high / medium / low)
- Type (empirical / methodological / theoretical)
- Suggested approach to investigate

### 5. Update priorities

Given the findings, propose changes to the task queue:
- Tasks to add via `science-tool tasks add`
- Existing tasks to reprioritize or complete
- Hypotheses to pursue further or set aside
- Next commands to run

## Writing

Follow `templates/interpretation.md` and fill all sections.
Save to `doc/interpretations/YYYY-MM-DD-<slug>.md`.

## After Writing

1. If the project has the `hypothesis-testing` aspect: update hypothesis files in `specs/hypotheses/` with confirmed status changes and new evidence.
2. Add new questions to `doc/questions/` using `templates/question.md`.
3. Update task queue: add new tasks, complete or reprioritize existing ones via `science-tool tasks`.
4. If graph updates were proposed, remind the user of the commands to run.
5. Suggest next steps:
   - `/science:discuss` — to debate interpretation of ambiguous findings
   - `/science:research-gaps` — to reassess coverage given new knowledge
   - `/science:add-hypothesis` — if new conjectures emerged
   - `/science:research-topic` or `/science:research-paper` — to fill gaps revealed by results
6. Commit: `git add -A && git commit -m "doc: interpret results <slug>"`

## Process Reflection

Reflect on the **interpretation template** sections and the **hypothesis evaluation** workflow.

After completing the task above, append a brief entry to `doc/meta/skill-feedback.md` (create the file and directory if they don't exist).

Use this format:

```markdown
## YYYY-MM-DD — interpret-results

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
- Be concrete and specific, not generic ("the signal classification felt artificial for exploratory results" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If the same issue has occurred before, note the recurrence (e.g., "3rd time this section was not applicable") — recurring patterns are the strongest signal for needed changes
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

Aspect fit check:
- Are the current project aspects the right fit for this work?
- If sections were missing that an unloaded aspect would have provided, suggest adding it
- If aspect-contributed sections were consistently skipped or filled with boilerplate, suggest removing the aspect
- Note any aspect suggestions in the feedback entry under "Suggested improvement"

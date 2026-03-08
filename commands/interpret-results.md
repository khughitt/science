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
4. Read `RESEARCH_PLAN.md`.
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

Include effect sizes and confidence intervals where available.
Ask the user to clarify anything ambiguous before proceeding.

### 2. Evaluate hypotheses

For each active hypothesis in `specs/hypotheses/`:
- Is it relevant to these results?
- If relevant: does the evidence support, refute, or leave it unchanged?
- Propose a status update if warranted: `proposed` → `supported` / `refuted` / `revised` / `under-investigation`
- If revising, draft the revised statement

Present the evaluation table to the user. **Do not update hypothesis files until the user confirms each proposed change.**

### 3. Assess causal model

If a causal inquiry exists:
- Do results suggest missing variables or edges?
- Should any edges be removed or reversed?
- Do effect sizes inform parameter estimates?
- Propose specific graph updates but do not execute them — list the `science-tool` commands that would make the changes

If no causal model exists, note whether results suggest building one.

### 4. Surface new questions

Identify questions raised by these results that didn't exist before.
For each, note:
- Priority (high / medium / low)
- Type (empirical / methodological / theoretical)
- Suggested approach to investigate

### 5. Update priorities

Given the findings, propose changes to `RESEARCH_PLAN.md`:
- Tasks to add, reprioritize, or drop
- Hypotheses to pursue further or set aside
- Next commands to run

## Writing

Follow `templates/interpretation.md` and fill all sections.
Save to `doc/interpretations/YYYY-MM-DD-<slug>.md`.

## After Writing

1. Update hypothesis files in `specs/hypotheses/` with confirmed status changes and new evidence in the "Current Evidence" section.
2. Add new questions to `doc/questions/` using `templates/question.md`.
3. Update `RESEARCH_PLAN.md` with revised priorities.
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

**What worked well:**
- A section or instruction that genuinely improved the output
```

Guidelines:
- Be concrete and specific, not generic ("the signal classification felt artificial for exploratory results" > "some sections could be improved")
- 2-5 bullets total. Skip categories that have nothing to report.
- If everything worked smoothly, a single "No friction encountered" is fine — don't manufacture feedback

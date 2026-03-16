---
description: Interpret analysis results and feed findings back into the research framework. Use when the user has pipeline output, notebook results, statistical summaries, or preliminary findings to evaluate against hypotheses and update project priorities. Also use when the user says "I got results", "here are the findings", "what does this mean for our hypotheses", or "update the project based on these results".
---

# Interpret Results

Interpret the results specified by `$ARGUMENTS` and systematically update the research framework.

If no argument is provided, ask the user to describe their findings or point to a results file.

## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `templates/interpretation.md` (resolve via command-preamble step 7).
2. Read active hypotheses in `specs/hypotheses/`.
3. Read open questions: check `doc/questions/` first; if it doesn't exist, scan for `*questions*.md` or `*open-questions*.md` in the doc directory.
4. Read `tasks/active.md` if it exists.
5. If the user specifies an inquiry slug, load the inquiry context:
   ```bash
   uv run science-tool inquiry show "<slug>" --format json
   ```
6. Check for pre-registration documents: scan `doc/meta/pre-registration-*.md`. If any exist, read them and identify which are relevant to the current interpretation (matching hypothesis IDs in the `related` frontmatter field).

## Input

`$ARGUMENTS` may be:
- A path to a results file, notebook, or output directory
- A prose description of findings
- An inquiry slug (to find associated outputs)

If given a file path, read it. If given a directory, scan for result files (`.csv`, `.json`, `.md`, `.ipynb`, `.html`) and summarize what's available.

## Mode Detection

Check whether interpretation documents already exist for these results (scan `doc/interpretations/` for files matching the inquiry slug or results description). Also assess the nature of the results.

- **Write mode** (default): No existing interpretation — write a full interpretation document following the workflow below.
- **Update mode**: Interpretation documents already exist for these results. Operate as a framework-update task: read existing interpretations, then run only the framework update steps (hypothesis evaluation, question cross-referencing, priority updates, decision gate assessment) without rewriting the interpretation narrative. Note "Update mode — existing interpretation: `<id>`" at the top of the output.
- **Dev mode**: The results are from an infrastructure or development task (pipeline formalization, tooling, refactoring) rather than an experimental analysis. Use a lighter-weight interpretation that focuses on: (a) what's now unblocked, (b) validation gaps in the new tooling, (c) new tasks or questions. Skip: signal strength classification (step 1), pre-registration cross-check (step 3b), and data quality checks (step 3c). Keep: evidence vs. open questions (step 2), user questions (step 3d), surface new questions (step 4), and update priorities (step 5). Note "Dev mode" at the top of the output.

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

### 3b. Pre-registration cross-check

If a pre-registration document exists for any hypothesis or inquiry being interpreted (matched via `related` frontmatter field):

1. **Match check:** Does the result match pre-registered expectations?
   - Compare actual findings against the "Expected Outcomes" section of the pre-registration
   - Characterize any divergence: in direction, magnitude, or kind?

2. **QA verification:** Before updating beliefs, confirm that pipeline QA checks passed (if applicable).
   - Link to QA output if available
   - If QA checks haven't been run, flag this

3. **Confirmatory vs. exploratory:** Explicitly label each conclusion:
   - **Confirmatory:** pre-registered analysis with pre-specified decision criteria
   - **Exploratory:** post-hoc discovery (valid but needs different evidential weight)

4. **Goalpost check:** Has the interpretation drifted from pre-registered decision criteria?
   - Compare actual decision criteria used against the "Decision Criteria" section
   - Flag if the pre-registration was modified after analysis began (compare `created` date in pre-registration against today)

If no pre-registration exists, skip this step but note in the output: "No pre-registration on file. Consider `/science:pre-register` for future analyses."

### 3c. Data Quality Checks

Before proceeding to new questions, verify basic data quality. This step has caught bugs twice at interpretation time — it's the natural moment for these checks:

- **Control uniqueness:** Are control sequences/samples distinct from each other and from test samples?
- **Dimensionality:** Do embedding dimensions match expectations (model output size, expected feature count)?
- **Sample counts:** Do sample counts match the experimental design? Any unexpected drops?
- **Value ranges:** Are metric values in plausible ranges? Any suspiciously perfect (1.0) or impossible values?

Flag any issues as a "Data Quality Issue" finding. These are distinct from methodological findings — they indicate the data generation may be broken, not just the analysis.

Skip this section in Dev mode.

### 3d. User Questions

If the user raises questions during interpretation (e.g., "does X also apply to Y?", "what about Z?"), record and answer them here. User-prompted follow-up questions are often the most insightful prompts and should be a first-class part of the interpretation, not an afterthought.

### 4. Surface new questions

Identify questions raised by these results that didn't exist before.
For each, note:
- Priority (high / medium / low)
- Type (empirical / methodological / theoretical)
- Suggested approach to investigate

**Numbering:** Before assigning new question IDs, check existing questions and use the next available number. Do not invent IDs that could conflict with the master list.

### 5. Update priorities

Given the findings, propose changes to the task queue:
- Tasks to add via `science-tool tasks add`
- Existing tasks to reprioritize or complete
- Hypotheses to pursue further or set aside
- Next commands to run

## Writing

Follow `templates/interpretation.md` and fill all sections.
Save to `doc/interpretations/YYYY-MM-DD-<slug>.md`.

Populate frontmatter fields:
- `id`: `"interpretation:YYYY-MM-DD-<slug>"`
- `related`: include the inquiry slug (e.g., `"inquiry:<slug>"`) and any hypothesis IDs being evaluated
- `source_refs`: IDs of papers or prior interpretations cited
- `input`: path to the results file, notebook, or prose description of what was analyzed
- `created` and `updated`: today's date

## After Writing

1. If the project has the `hypothesis-testing` aspect: update hypothesis files in `specs/hypotheses/` with confirmed status changes and new evidence.
2. Add new questions to `doc/questions/` using `templates/question.md`.
3. Update task queue: add new tasks, complete or reprioritize existing ones via `science-tool tasks`.
4. If graph updates were proposed, remind the user of the commands to run.
5. Suggest next steps:
   - `/science:discuss` — to debate interpretation of ambiguous findings
   - `/science:next-steps` — to reassess coverage and priorities given new knowledge
   - `/science:compare-hypotheses` — if results are ambiguous between competing explanations
   - `/science:bias-audit` — to check for post-hoc rationalization
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

---
description: Post-hoc reflection after an analysis failed or behaved unexpectedly. Investigate the root cause, identify what would have surfaced it sooner, and file the generalized methodology lesson as feedback. Use after a surprising result, a failed run, or a violated assumption.
---

# Post-Mortem

Run a structured post-hoc reflection on an analysis that failed or behaved unexpectedly, described by `$ARGUMENTS`, and capture any **generalized** methodology lesson as feedback.

If no argument is provided, ask the user which analysis, run, or result to reflect on.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

## When to use

Use this after the fact, when something did not go as planned: a QA issue surfaced late, an analysis design did not fit the data's constraints, a statistical method was applied in violation of its assumptions, or a result contradicted a pre-registered expectation. The goal is not to fix the one analysis — it is to improve the guidance so the next analysis surfaces the issue sooner.

Also use it when **a gate fired and nothing was lost** — a pre-registered check stopped the analysis before any observed data was read. Nothing surfaced late, and no result exists: that is the system working. **A post-mortem on a gate that fired is the cheapest kind, and its lessons are the most transferable, because nothing is entangled with a finding anyone wants to defend.** In this mode, read step 1's "gap between expectation and outcome" as *the gap between what the plan assumed about its own instruments and what was true*.

## Reflection

Work through these steps with the user. Keep the project-specific incident in the project (as an interpretation, note, or task); only a cross-project lesson goes to the global feedback store.

1. **Scope.** What was attempted, what was expected, and what actually happened? Be concrete about the gap between expectation and outcome.

2. **Root cause.** Why did it happen — the actual technical or methodological reason, not the symptom? Distinguish a one-off data/code mistake from a reasoning or process flaw.

3. **Earlier signal.** What would have surfaced this sooner? A QA check, an assumption test, a design review, a different pre-registration question? This is the core of the reflection.

4. **Generalize gate.** Is the lesson cross-project, or specific to this project? If it is purely project-local, **stop**: record it in the project and file nothing globally. Only continue for lessons that should change shared guidance.

   Then separate **the failing thing** (usually local — a specific model, a specific optimiser) from **the reason it was not caught sooner** (usually global — a check that could not fail, a threshold with no stated domain, a probe confounded with its own target). **File on the latter.** The mechanism generalises to nothing; the blind spot generalises to everyone.

5. **Target the surface.** Which guidance artifact should change so the earlier signal becomes routine? `--target` is **free text**; the resolvable namespaces are `skill:`, `command:`, `aspect:`, `template:`, and `cli:` — e.g. `skill:statistics`, `command:plan-analysis`, `aspect:computational-analysis`, `template:pre-registration`, `cli:validate`. Name the surface that should have caught it, not the nearest one on a list. Pick the `concern`:
   - `methodology:statistics` — assumptions, inference validity, model/finite-sample choices
   - `methodology:qa` — data/quality checks that should have caught it
   - `methodology:design` — analysis/study design vs. the question or data constraints
   - `methodology:data-fitness` — dataset suitability, preprocessing, provenance
   - `methodology:reasoning` — interpretation / causal / epistemic errors

6. **File the lesson.** For each distinct generalized lesson, run:

   ```bash
   science feedback add \
     --target "skill:statistics" \
     --concern methodology:statistics \
     --category <gap|guidance|suggestion|positive> \
     --summary "<the generalized lesson, one line>" \
     --detail "<what happened in this project as evidence; link the project entity>"
   ```

   - The `summary` is the improvement to shared guidance, not the incident.
   - The `detail` carries the incident as evidence and a pointer (path or id) to the project entity where the failure lives.
   - One entry per distinct lesson, not one big dump. The tool detects recurrence automatically: a re-filed lesson is **recorded as another occurrence** (its project/detail are kept, never discarded), and target spellings that name one surface — `command:`/`cli:`/`science:` — are matched as equivalent.
   - `--target` is free text, so **reuse an existing spelling** rather than minting a new variant: run `science feedback targets` to see the targets already on file. Near-duplicates that are not an exact match are surfaced as an advisory after your entry is filed — nothing is ever merged automatically.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:post-mortem" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- Skip if everything worked smoothly — no feedback is valid feedback

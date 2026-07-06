---
name: science-pre-register
description: "Formalize expectations before analysis to prevent post-hoc rationalization. Use after add-hypothesis or plan-pipeline and before running analysis — to state expectations or what would change the user's mind."
---

# Pre-register Expectations

Converted from Claude command `/science:pre-register`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `science-research-methodology` and `science-scientific-writing` Codex skills. If native skill loading is unavailable, use `codex-skills/INDEX.md` to map canonical Science skill names to generated skill files and source paths.
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
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
   If you are operating from a git worktree and `uv run --frozen science ...`
   fails because a relative editable `tool.uv.sources` path resolves to a
   nonexistent checkout, use the main checkout's synced environment while
   keeping the worktree as the current directory:
   `$MAIN/.venv/bin/science <command>`. For wrappers or rules that shell out to
   nested `uv run --frozen ...`, export `UV_PROJECT=$MAIN` so dependencies
   resolve from the main checkout while cwd-relative project files still come
   from the worktree.
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

Formalize the user's expectations, decision criteria, and null-result plans before analysis begins.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `.ai/templates/pre-registration.md` first; if not found, read `templates/pre-registration.md`.
2. Read active hypotheses in `entities/hypotheses/`.
3. Read existing inquiries: run `science inquiry list` (if available).
4. Read existing pipeline plans in `entities/plans/` (if any).
5. Read existing pre-registrations in `entities/pre-registrations/` to avoid duplication.
6. Read linked analysis plans in `entities/plans/*-analysis-plan.md` when the user or context references a `plan:<stem>` whose frontmatter has `plan_kind: analysis-plan`.

## Interactive Refinement

Have a natural conversation with the user to formalize their expectations. The questions below are guidelines — use your judgment about which are needed based on how much context the user has already provided.

### 0. Target Class — Operational or Epistemic?

Before anything else, identify which class the pre-reg primarily commits to. The two classes are evaluated differently at interpretation time and produce different graph effects.

- **Operational target** — a procedure, pipeline run, dataset processing step, or experimental protocol. The commitment is "we will execute X before observing Y." Deviation requires an `amendments:` record. Operational pre-regs remain gating.
- **Epistemic target** — a hypothesis, question, proposition, inquiry, or interpretation rule. The commitment is "we will *interpret* observed Y in this way to update belief about X." A null result against an epistemic pre-reg is **evidence**, weighted by the pre-reg's commitment — not a verdict that kills the hypothesis.

Mixed targets are common (e.g., "we will run analysis A, and treat H as supported if effect > 0.3"). Treat the procedure portion and the interpretation portion separately:

- **Operational portion:** stays as an amendment-gate check. `science:interpret-results` confirms the analysis ran as committed (or that any deviation has a corresponding `amendments:` record). No `bears_on` edge — operational targets are not `bears_on` sinks; the materializer rejects authored `bears_on` edges to non-epistemic targets.
- **Epistemic portion:** materializes as a `bears_on` edge from the pre-reg into the epistemic target via the auto-derivation rule registered in `science_tool/graph/materialize.py`. This is the load-bearing graph effect.

#### Sub-prompt: which `related:` entries are commitment targets vs. navigation context?

After the user lists `related:` entries, ask which subset the pre-reg actually constrains. This is the load-bearing question for whether `bears_on` edges accurately reflect the author's commitment — every pre-reg-using project mixes commitment targets with navigation-context refs in `related:`, and treating all epistemic refs as commitment targets over-derives edges.

> "Of the epistemic entries in `related:`, which are commitment targets — i.e., entities this pre-reg actually constrains the interpretation of? Anything *not* called out here will still appear in `related:` for discoverability but won't produce a `bears_on` edge."

Record the commitment-target subset as `commits_to:` in the pre-reg frontmatter (optional). The field means **"derive pre-reg `bears_on` edges to these targets"**; it does **not** mean "lock these targets forever." Any epistemic entity named in `commits_to:` remains responsive to all other upstream freshness dependencies — datasets, workflow-runs, observations, propositions, interpretations, and reports can still flag it `needs-review`.

If `commits_to:` is absent, the deriver falls back to "all epistemic `related:` entries are commitment targets," which over-derives for many existing mixed pre-regs. When in doubt, populate `commits_to:` explicitly.

#### Sub-axis: execution timing — runnable-now or data-gated?

Target class (operational/epistemic) is orthogonal to *when the analysis can run*. Most pre-regs are
**runnable-now**: the qualifying data/vehicle exists and § 4 (null/power) and the Null-Result Plan
presuppose execution. But a pre-reg may commit a **rule before any qualifying vehicle exists** — the
binding constraint is data availability (e.g. no adequately-powered cohort yet). Author these in
**data-gated mode** rather than improvising:

- **Execution-readiness gate for runnable-now mode.** When the vehicle exists but the verdict is only
  interpretable if specific checks pass, add an Execution-Readiness Gate rather than using the
  data-gated Vehicle-Admissibility Gate. This gate should name the power floor, input QA, preprocessing checks, and required sensitivity checks.
  Those checks must pass before the result can carry confirmatory weight. These checks gate verdict interpretability rather than data availability.
  A failed gate yields an inconclusive/protocol-failed interpretation, not a deferred standing verdict.
- **Commit the rule now, defer execution.** Write the decision criteria and expected outcomes as
  usual, but mark the analysis as not-yet-runnable.
- **Vehicle-admissibility gate.** State the explicit preconditions a future vehicle must satisfy to
  *activate* the rule — e.g. a locked power floor (minimum n), required differential design, and any
  lineage/comparator requirement. Spent vehicles that fail the floor do **not** qualify.
- **Standing verdict = no update until a vehicle clears.** Until an admissible vehicle exists, the
  pre-reg's standing interpretation is *inconclusive-for-coverage*: it produces **no `bears_on` belief
  update**. This is distinct from a null result (which is evidence) — there is simply no qualifying
  evidence yet. Map it to the canonical inconclusive verdict (`[?]`), not a new token.
- **Track with a `status: blocked` task** whose blocker is the admissibility gate, so the deferred
  analysis stays visible in the queue and activates when a qualifying vehicle arrives.

This differs from **Pilot Calibration** (§ below), which defers a single *threshold* to a pilot while
the analysis itself runs now. Data-gated mode defers the *entire analysis* pending a qualifying
vehicle. Note it explicitly at the top of the pre-reg (e.g. `mode: data-gated`) so interpret-results
treats the standing verdict as no-update rather than as a runnable null.

#### Sub-axis: in-run calibration without peeking

If the analysis runs now but one threshold must be derived from the run's own substrate, add a
**Calibration Gate**. This covers an in-run, no-peeking, marginal-derived threshold and is not a data-gated pre-registration: the vehicle exists, execution proceeds, and only the threshold value is filled in by a pre-committed rule.

The gate must name exactly which fields may be inspected to set the threshold: marginal distributions or eligibility counts only. It must also forbid outcome labels, effect estimates, group-contrast results, downstream performance metrics, or any target-linked signal before the threshold is locked. Record the lock point, formula, allowed inputs, forbidden inputs, and the audit artifact that proves the calibration happened before confirmatory scoring.

Use this instead of pretending a separate pilot or baseline artifact exists when the defensible
calibration source is the current run's marginal structure.

#### Sub-axis: multi-analysis coverage

When one pre-registration covers multiple analyses, add an **Analysis Registry** before the
per-analysis criteria. This is required when the analyses have mixed runnable/data-gated statuses
or different confirmatory/exploratory roles.

Record each analysis's `mode` (`runnable-now` or `data-gated`), status, commitment target, and
verdict policy in the registry. Then link each row to its readiness gate or vehicle-admissibility gate:
use an Execution-Readiness Gate for runnable-now analyses whose interpretability depends on checks
passing, and a Vehicle-Admissibility Gate for data-gated analyses that are not yet executable.

Do not collapse the whole pre-reg to a single top-level mode when rows differ. The pre-reg can be
committed as one document, but interpretability and standing verdicts are per analysis row.

### 1. Identify the Analysis

- What analysis are you about to run?
- Which hypotheses does it test? (Reference by ID if they exist in `entities/hypotheses/`)
- Is there a pipeline plan? (Reference by slug if one exists in `entities/plans/`)

If this is a data-analysis pre-registration and no linked `plan:<stem>` analysis
plan exists, recommend `science-plan-analysis` when any of these are underspecified:
input QA, preprocessing/normalization checks, independent unit, estimand,
power/resolution limit, or sensitivity-arbitration rule. The recommendation is
advisory, not a hard dependency.

### 1b. Feasibility Against Real Input Artifacts

Before locking any threshold in § 3, **load the actual input artifacts** — not your memory of them —
and check the analysis is feasible as framed. § 4 asks you to *reason* about power; this step makes
you *look*. For each arm of the planned comparison:

- **Support-set size.** What is the real *n* feeding each arm? Open the table/dataset and count.
- **Universe alignment.** How many of those rows survive into the *covering universe* the test
  actually runs against (after joins, filters, eligibility)? The effective *n* is usually smaller
  than the raw *n*.
- **Base rates.** What is the background/overlap rate the effect must beat? A high base rate can make
  a nominally-significant arm uninformative.
- **Count ledger.** Re-derive every numeric count referenced anywhere in the pre-registration from
  the loaded artifacts, not just the headline arm. This includes denominators, subgroup counts, exclusion counts, missingness counts, arm sizes, post-filter counts, and supporting counts in prose, tables, or caveats. Do not only verify the headline arm; if a count will appear in the
  locked criteria or rationale, record where it was re-derived from the loaded artifact.

If the numbers reveal an arm is underpowered or that the wrong arm was slated as confirmatory, **fix
the design here** — re-scope, swap which arm is confirmatory/exploratory, or add a feasibility
precondition — rather than discovering it post-data. This is exactly what pre-registration exists to
surface.

*Worked case (natural-systems H09).* Inspecting the inputs caught that the headline arm was
underpowered (cycle-support n=22, only 10 in the covering universe, 73% overlap base rate) and that
the confirmatory/exploratory assignment should be inverted — caught pre-data because the artifacts
were loaded before the criteria were locked.

### 2. State Expected Outcomes

- What do you expect to find?
- Why do you expect this? (Link to existing evidence — papers, topics, prior results)
- How specific can you be? (Direction? Magnitude? Pattern?)

### 3. Define Decision Criteria

Frame decision criteria according to the target class identified in § 0.

**For epistemic targets:**
- What evidence would **support** it? Be concrete — name the metric, the threshold, the pattern.
- What evidence would **weaken** it? What would make you less confident?
- What evidence would **shift belief away from** it? Don't frame as "would I abandon" — that's a kill-switch framing. Instead: how strongly would each result class move belief, and in which direction?

**For operational targets,** "refute" / "abandon" remains accurate (the procedure either ran as committed or it didn't):
- What evidence would **support** that the procedure ran as committed?
- What evidence would **refute** that — i.e., trigger an `amendments:` record?

### 4. Plan for Null Results

- What does a null result mean? Hypothesis is wrong, or test is inadequate?
- Is the analysis sufficiently powered to detect the expected effect?
- What would you do next if results are ambiguous?

**For epistemic targets:** A null result is evidence, weighted by the pre-reg's commitment. It is not a verdict on the hypothesis. Frame the null-result plan as "what update should this trigger?" rather than "would this kill the hypothesis?" The result feeds the target's evidence base via a `bears_on` edge derived at graph-build time; downstream `science:status` and `science:next-steps` then surface the target for review under the recast freshness/attention semantics.

**Pilot experiments:** If this is a pilot (1-2 seeds, small N, exploratory scope), explicitly state what it CAN and CANNOT establish. A pilot can suggest directions and calibrate effect sizes but cannot confirm or refute a hypothesis. Frame decision criteria accordingly — a pilot's null result means "insufficient signal to justify scaling up", not "hypothesis is wrong."

### 4b. Plan for Suspicious/Unexpected Results

- What would "too good to be true" look like? (e.g., AUC > 0.95, perfect accuracy)
- What inflators could produce misleading results? (data leakage, confounds, overfitting)
- What checks would you run before accepting an unexpectedly strong result?

Skip this if the analysis type doesn't have a meaningful "too good" threshold.

### 4c. Metric Selection Rationale (if applicable)

If the primary metric has changed from prior analyses, or if the metric choice is non-obvious:
- What metric are you using and why?
- What motivated the change from the prior metric (if applicable)?
- What are the known limitations of this metric?

### 5. Separate Confirmatory from Exploratory

- Which analyses are pre-registered (confirmatory)?
- Which are explicitly exploratory?
- Are there analyses you plan to run "just to see what happens"? Label them.

### 5b. Sampling Strategy Rationale (if applicable)

If the experimental design involves non-obvious sampling decisions (stratified sampling, subsampling from a larger population, context selection), document the rationale and trade-offs:
- What sampling strategy was chosen?
- What was the alternative?
- Why was this approach preferred?

Omit when sampling is straightforward (e.g., "use all available data").

## Writing

After the conversation, write the pre-registration document using `.ai/templates/pre-registration.md` first, then `templates/pre-registration.md`.

### Naming and Frontmatter

Use the hypothesis ID, inquiry slug, or task ID as the basis:
- **Filename:** `entities/pre-registrations/<slug>.md`.
- **Frontmatter** must use the canonical pre-registration shape:
  - `id: "pre-registration:<slug>"`
  - `kind: "pre-registration"`
  - `status: "committed"` once the user has signed off on the criteria
  - `committed: "<YYYY-MM-DD>"` — the date the criteria are locked
  - `spec: "<path-to-design-doc>"` — optional; empty string if no paired design doc exists
  - `related: [...]` — hypothesis IDs, inquiry slugs, and/or task IDs this pre-reg covers (mix of commitment targets and navigation context is fine here)
  - `commits_to: [...]` — optional; the subset of epistemic `related:` entries this pre-reg actually constrains. When present, `bears_on` edges are derived only to these targets. When absent, the deriver falls back to "all epistemic `related:` entries are commitment targets," which over-derives for mixed pre-regs.
- The `related` field is what `interpret-results` searches on, so it must be populated.
- Dataset refs are allowed in `related:` when a pre-registration is tied to a specific vehicle/dataset; they are navigation and provenance context, not commitment targets. Put epistemic targets in `commits_to:` so dataset context does not get treated as a locked claim.
- `commits_to:` is an edge-scoping field, not a lock. Populating it does not exempt the target from freshness propagation from other upstream entities.

## After Writing

1. Save to `entities/pre-registrations/<slug>.md`. The frontmatter must declare `kind: "pre-registration"` and `id: "pre-registration:<slug>"` per the template.
2. If relevant hypotheses exist, note in the output that pre-registration is now on record.
3. Suggest next steps:
   - `science-plan-pipeline` — if no pipeline plan exists yet
   - `science-bias-audit` — to check for blind spots before running the analysis
   - `science-discuss` — to stress-test the expectations themselves
4. Commit: `git add -A && git commit -m "doc: pre-register expectations for <slug>"`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:pre-register" \
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

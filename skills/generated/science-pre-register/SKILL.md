---
name: science-pre-register
description: "Formalize expectations before analysis to prevent post-hoc rationalization. Use after add-hypothesis or plan-pipeline and before running analysis — to state expectations or what would change the user's mind."
user-invocable: true
---

# Pre-register Expectations

## Science Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load the `science-command-preamble` skill. Use its
   `references/role-prompts/research-assistant.md` role prompt and its aspect definitions.
3. Load the `science-scientific-writing` skill. For research methodology, read the `science-command-preamble` skill's `references/methodology-index.md` and load the relevant generated methodology router skills (e.g. `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).
4. Read project context from current entity roots:
   - `entities/questions/` for active research questions.
   - `entities/hypotheses/` for hypotheses.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. the `science-command-preamble` skill's `references/aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under the `science-command-preamble` skill's `references/aspects/`.

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
   `references/templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Verify the project-local Science CLI:** Execute the top-level CLI
   Compatibility Gate below before the command's first Science invocation. It
   uses the consumer's frozen lock; do not route through a toolkit checkout or
   another environment.

## CLI Compatibility Gate

```bash
SCIENCE_REQUIRED_VERSION=0.3.0
if output=$(uv run --frozen science --version 2>&1); then
  SCIENCE_INSTALLED_VERSION=${output##* }
elif uv run --frozen science --help >/dev/null 2>&1; then
  # The CLI runs but has no --version option, so it predates the baseline.
  # Decided by behavior, never by matching Click's version-dependent wording.
  SCIENCE_INSTALLED_VERSION=
else
  # The CLI cannot run at all: missing/stale lock, Git fetch failure, import
  # error. Report the real diagnosis; never advise moving the Science pin.
  printf '%s\n' "$output" >&2
  exit 1
fi

if ! SCIENCE_INSTALLED_VERSION="$SCIENCE_INSTALLED_VERSION" \
     SCIENCE_REQUIRED_VERSION="$SCIENCE_REQUIRED_VERSION" \
     uv run --no-project python - <<'PY'
import os
import re
import sys

def release(name: str) -> tuple[int, int, int] | None:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", name)
    return tuple(map(int, match.groups())) if match else None

installed = release(os.environ["SCIENCE_INSTALLED_VERSION"])
required = release(os.environ["SCIENCE_REQUIRED_VERSION"])
sys.exit(0 if installed is not None and required is not None and installed >= required else 1)
PY
then
  display=${SCIENCE_INSTALLED_VERSION:-unknown-or-pre-0.3.0}
  echo "This Science agent command requires science >=$SCIENCE_REQUIRED_VERSION; found $display." >&2
  echo "upgrade with: uv lock --upgrade-package science && uv sync --frozen" >&2
  exit 1
fi
```

After the gate succeeds, run the command through the consumer's project-local
environment as `uv run science <command>`. Missing dependency, missing or stale
lock, and Git fetch failures are surfaced directly and must be fixed in the
consumer project.

A CLI that answers `--help` but rejects `--version` predates the baseline;
malformed successful output and a version below the floor are likewise
compatibility failures, and all three stop with the upgrade command. A CLI that
cannot run at all is an environment failure: its output is printed verbatim and
must be fixed as reported.

The `--help` probe is what separates those two classes. Do not substitute a match
against Click's error text — its wording changed in Click 8.4, and `science`
allows any `click>=8.1`, so a freshly locked consumer can emit either form. The
root `--version` probe is the permanent bootstrap surface; do not replace it with
a preflight subcommand, which an older CLI could not recognize either.

Formalize the user's expectations, decision criteria, and null-result plans before analysis begins.

## Setup


Additionally:
1. Read `.ai/templates/pre-registration.md` first; if not found, read `references/templates/pre-registration.md`.
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

#### Sub-axis: can the instrument resolve the threshold?

If the analysis estimates parameters numerically — an optimiser, a profile likelihood, an ODE or any
other discretisation in the inferential path — then a pre-registered threshold is a claim about an
**instrument** as much as about the world. A threshold finer than its instrument's resolution is not
conservative: it is noise-driven, and the noise has a sign.

Add an **Estimator Certification Gate**. It must commit, before any gate is evaluated:

- **Well-posedness** (free, design-only): is the parameter estimable at all? Skipping this makes the
  reproducibility criterion adversarial — it will "fix" a flat ridge by selecting a biased optimiser,
  because any operation that smooths the objective buys low variance with bias.
- **Forward-map accuracy** against a reference with a **different error-generating mechanism**. A
  finer step of the same scheme shares its truncation term and its stability boundary; that is a
  convergence check, not a reference.
- **Reproducibility** under perturbation of every inferentially irrelevant choice — start point,
  ordering, threads, seeds. If the estimator is deterministic, jitter must be **injected**: a check
  that cannot fail is not a check. Two replicates falsify an estimator; they cannot certify one.
- **Threshold calibration**: the null distribution of the statistic, simulated — not assumed. Either
  **EXECUTED** or explicitly **CONDITIONAL**, and a CONDITIONAL must state cost, trigger,
  invalidation clause, and **the decisions that may not depend on it until it completes**. Deferring
  it does not add a caveat; it removes decisions from the table.
- The **outer optimiser**, and why it is valid for the profile's smoothness/discontinuity structure.
  Gradient- and finite-difference-based outer methods are **prohibited unless smoothness is
  demonstrated**.
- The **error budget** `E = |b| + k*s <= rho * sigma_null(T)`. `rho` is the dimensionless
  **instrument-error fraction** (default `0.1`, never unstated), measured against the null's sampling
  SD — **not** as a percentage of the critical value, which drifts with the degrees of freedom. Do
  not call it `alpha`; `alpha` is the test size.
- The **INDETERMINATE** band: units whose statistic sits within `E` of the critical value are
  unresolvable by this instrument and must not be silently decided.

**Order: establish well-posedness, certify the estimator, price the design, then commit the budget.**
A budget priced on an uncertified estimator is a consequence of an untested assumption, not a
constraint — it can be wrong by orders of magnitude. If the budget must be committed first, mark it
**CONDITIONAL** and name what invalidates it.

See `the `science-study-design` skill` guidance from the `science-study-design` skill.

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
  Freeze the ledger at **full resolution**, not just the headline totals: for a matrix
  substrate that means the shape, the total nonzero count, the row-sum distribution, and
  the **complete column-sum vector** — not "244 models" but `244 × 24, 481 ones, row-sums
  {1:80,2:106,3:45,4:11,5:2}, column-sums (98,75,50,38,...,1,1)`. This is not only a design
  aid. The frozen ledger is a **runtime integrity check on the substrate**: if the vehicle
  is later silently regenerated from a drifted input, a mismatch (e.g. `248 nodes` where 244
  were registered) is immediately legible as a tripwire rather than a curiosity, and it is
  the only thing that makes a reconstruction **provably faithful** — a coarser
  totals-only check cannot certify the column-sum vector. (natural-systems
  pre-registration:0026, fb-2026-07-11-027.)
- **Derivation-cohort circularity.** If the proposed validation vehicle is also a training or
  validation cohort for the same scored signature, model, or threshold, that makes the in-cohort
  predictive-vs-prognostic test circular. It can still be useful for calibration or debugging, but do
  not register it as independent confirmatory validation; treat it as exploratory or require an
  independent validation vehicle before assigning confirmatory weight.

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
- The mirror image, for any **validation probe**: an unexpectedly *interesting* result from a probe
  is a probe-defect signature, not a finding. A broken probe does not announce itself by returning
  nothing — it returns something worth writing up. Before interpreting it, check the probe is not
  confounded with the thing it validates (e.g. a probe that grids the very parameter whose true
  values vary across its own cells).

Skip this if the analysis type doesn't have a meaningful "too good" threshold.

### 4c. Metric Selection Rationale (if applicable)

If the primary metric has changed from prior analyses, or if the metric choice is non-obvious:
- What metric are you using and why?
- What motivated the change from the prior metric (if applicable)?
- What are the known limitations of this metric?

### 4d. Blind Erosion — when observed values leak early

An accidental or exploratory run can expose confirmatory-relevant values (an observed
effect, a group contrast, a metric under the very config sweep the design leaves open)
**before** the null has been drawn. Blindness is then eroded even though no comparison was
possible. Distinguish two states and never conflate them:

- **Not conditioned on the null** (weaker) — the value was seen, but no null distribution
  or comparison exists yet.
- **Blind** (stronger) — no confirmatory-relevant value has been seen at all.

When values leak early:

1. **Escalate the next design choice to the human.** The agent who saw the values must not
   silently take the decision they now bear on (e.g. "run the registered cohort or amend to
   the current one", or fixing an under-specified statistic — a Louvain resolution — whose
   candidate values were just made visible by the leaked sweep).
2. **Record the exposure as a protocol deviation in the pre-registration** (`amendments:`),
   writing down the seen values explicitly and assigning them **no confirmatory weight**.

Treat this as the same failure class as a silently-regenerated frozen vehicle: a leak that is
not recorded quietly launders exploratory knowledge into a confirmatory decision.
(natural-systems pre-registration:0026, fb-2026-07-11-028.)

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

After the conversation, write the pre-registration document using `.ai/templates/pre-registration.md` first, then `references/templates/pre-registration.md`.

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

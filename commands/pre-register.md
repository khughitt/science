---
description: Formalize expectations before analysis to prevent post-hoc rationalization. Use after add-hypothesis or plan-pipeline and before running analysis — to state expectations or what would change the user's mind.
---

# Pre-register Expectations

Formalize the user's expectations, decision criteria, and null-result plans before analysis begins.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `.ai/templates/pre-registration.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/pre-registration.md`.
2. Read active hypotheses in `specs/hypotheses/`.
3. Read existing inquiries: run `science inquiry list` (if available).
4. Read existing pipeline plans in `doc/plans/` (if any).
5. Read existing pre-registrations in `doc/meta/pre-registration-*.md` to avoid duplication.
6. Read linked analysis plans in `doc/plans/*-analysis-plan.md` when the user or context references `analysis-plan:<slug>`.

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

### 1. Identify the Analysis

- What analysis are you about to run?
- Which hypotheses does it test? (Reference by ID if they exist in `specs/hypotheses/`)
- Is there a pipeline plan? (Reference by slug if one exists in `doc/plans/`)

If this is a data-analysis pre-registration and no linked `analysis-plan:<slug>`
exists, recommend `/science:plan-analysis` when any of these are underspecified:
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

After the conversation, write the pre-registration document using `.ai/templates/pre-registration.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/pre-registration.md`.

### Naming and Frontmatter

Use the hypothesis ID, inquiry slug, or task ID as the basis:
- **Filename:** `doc/meta/pre-registration-<slug>.md` (default), or `doc/pre-registrations/<slug>.md` if the project has adopted that placement.
- **Frontmatter** must use the canonical pre-registration shape:
  - `id: "pre-registration:<slug>"`
  - `type: "pre-registration"`
  - `status: "committed"` once the user has signed off on the criteria
  - `committed: "<YYYY-MM-DD>"` — the date the criteria are locked
  - `spec: "<path-to-design-doc>"` — optional; empty string if no paired design doc exists
  - `related: [...]` — hypothesis IDs, inquiry slugs, and/or task IDs this pre-reg covers (mix of commitment targets and navigation context is fine here)
  - `commits_to: [...]` — optional; the subset of epistemic `related:` entries this pre-reg actually constrains. When present, `bears_on` edges are derived only to these targets. When absent, the deriver falls back to "all epistemic `related:` entries are commitment targets," which over-derives for mixed pre-regs.
- The `related` field is what `interpret-results` searches on, so it must be populated.
- `commits_to:` is an edge-scoping field, not a lock. Populating it does not exempt the target from freshness propagation from other upstream entities.

## After Writing

1. Save to `doc/meta/pre-registration-<slug>.md` (or `doc/pre-registrations/<slug>.md` if the project uses that placement). The frontmatter must declare `type: "pre-registration"` and `id: "pre-registration:<slug>"` per the template.
2. If relevant hypotheses exist, note in the output that pre-registration is now on record.
3. Suggest next steps:
   - `/science:plan-pipeline` — if no pipeline plan exists yet
   - `/science:bias-audit` — to check for blind spots before running the analysis
   - `/science:discuss` — to stress-test the expectations themselves
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

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
8. **Resolve science CLI invocation:** When a command says to run `science`,
   prefer the project-local install path: `uv run science <command>`.
   This assumes the root `pyproject.toml` includes `science` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`
   (the distribution is `science`; the entry point it installs is `science`).
   If that fails (no root `pyproject.toml` or science not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science science <command>`

Formalize the user's expectations, decision criteria, and null-result plans before analysis begins.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `.ai/templates/pre-registration.md` first; if not found, read `templates/pre-registration.md`.
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
exists, recommend `science-plan-analysis` when any of these are underspecified:
input QA, preprocessing/normalization checks, independent unit, estimand,
power/resolution limit, or sensitivity-arbitration rule. The recommendation is
advisory, not a hard dependency.

### 2. State Expected Outcomes

- What do you expect to find?
- Why do you expect this? (Link to existing evidence — papers, topics, prior results)
- How specific can you be? (Direction? Magnitude? Pattern?)

For *narrative* direction/pattern expectations, prose in `## Expected Outcomes`
is fine. For any *interpretive numerical* expectation — a number that will
anchor a Decision Criteria threshold reading observed effects, CIs, or
posterior quantities as supporting / weakening / refuting the hypothesis —
drive an `## Expectations` block per parameter through § 2a.

Operational and QA thresholds are out of scope for § 2a: minimum sample
size, MCMC convergence checks (R-hat, ESS), leakage / suspicious-result
bounds, QC floors, runtime limits. These live in `## Known Limitations`,
`## Suspicious/Unexpected Result Plan`, or the paired analysis-plan doc
(`spec:` in frontmatter) with their own rationale. They are not
interpretive claims about expected biology and do not need Expectations
blocks.

Also surface *known-relevant parameters with no estimate* — parameters
the analysis depends on but for which no prior data supports a numerical
commitment. These are authored as `acknowledged`-tier blocks in § 2a step
4; they record a known unknown for transparency rather than letting it
silently affect interpretation.

### 2a. Classify Each Numerical Expectation by Evidence Tier

This is the load-bearing step that prevents pre-data numerical commitments
from masquerading as rigor. For each numerical expectation, walk the user
through:

1. **Name the parameter.** What quantity, with what units, on what data?
2. **State the central guess, range, and direction.** If the user can name
   the parameter as analysis-relevant but cannot honestly state a central
   value or range, this is an `acknowledged` block — skip to step 5 with
   `expected.central` and `expected.range` set to null. `direction:` can
   still carry meaning (e.g., `unsigned` or `unknown`); `provenance:` is
   an empty list.
3. **Enumerate the evidence the guess rests on.** For each source:
   - cohort/dataset/paper-key
   - reported estimate (value or range)
   - reference (task ID, doc path, paper key)
   - one-line note on what the source establishes and what it doesn't
4. **Classify the tier from the enumeration:**

   | Tier | Trigger |
   |---|---|
   | `acknowledged` | Parameter is analysis-relevant but no estimate is authored. `provenance:` is empty, `expected:` is null. Records a known unknown. |
   | `hint` | Literature-only support, OR one own-analysis on a single dataset, OR two own-analyses on disparate datasets. |
   | `calibrated` | 3+ own-analyses on disparate datasets, all enumerated in `provenance:`. The disparate-datasets requirement is the threshold for "real distribution, not technical artifact / batch effect / single-cohort idiosyncrasy." |

5. **Surface unknowns explicitly.** Ask the user to name at least one thing they
   *don't* know about this quantity that could move the estimate (or, for
   `acknowledged` blocks, why no estimate is possible). Empty `unknowns:` is
   the over-confidence smell — push back if the user wants to leave it
   empty at `hint` tier or below.
6. **Bind the expectation to gate use.** State how this expectation binds
   to Decision Criteria (§ 3):
   - `acknowledged`: "no gate; recorded as a known unknown for
     interpretation."
   - `hint`: gate uses a *wider acceptance range* authored before data
     arrives. Does not anchor a narrow threshold.
   - `calibrated`: may anchor a narrow threshold; cite the 3+ provenance
     entries.

Authoring guidance:

- If the user proposes a number with no enumerable provenance, do not
  write it into the pre-reg. Either obtain provenance (promoting to
  `hint`) or, if the parameter is genuinely relevant but unestimable,
  author it as `acknowledged` with `expected.central` and `expected.range`
  null and `provenance: []`. There is no "invalid" tier — pre-reg
  material requires either provenance or an honest declaration of
  ignorance.
- If only one or two own-analyses or literature claims support the guess,
  this is `hint`. Hint-tier numbers are fine to *register* (better than
  implicit expectations) — but any decision criterion that cites them
  must be authored with a wider acceptance range up front.
- Resist the temptation to upgrade `hint` to `calibrated` by adding
  literature references. The 3+ requirement is for *own analyses on
  disparate datasets*; literature support is necessary but not sufficient.
- When the user has only one or two prior own-analyses, the current
  pre-reg's analysis is plausibly the third — frame it that way ("if
  this pre-reg's fit replicates the direction, the *next* pre-reg can
  author `calibrated` expectations").
- Encourage authoring `acknowledged` blocks for parameters the user
  *knows* matter but cannot estimate. These make the project's
  uncertainty surface machine-readable (forward-compatible with later
  tooling that extracts uncertainty nodes; no parser reads them today)
  and prevent unknown parameters from silently affecting interpretation.
  Early-stage projects should have more `acknowledged` blocks than
  `calibrated` ones; that's healthy.

### 2b. Classify Each Provenance Entry by Calibration Source

For every entry in an Expectations block's `provenance:` list, ask the
user: *where did this number come from?* Five classes:

| `calibration_source` | When to use |
|---|---|
| `literature` | Paper, review, or external benchmark. Cite paper-key in `ref:`. |
| `prior_own_analysis` | A prior task or interpretation in this project that estimated this quantity on a different cohort or design. Cite `task:tNNN` or `interpretation:<slug>`. |
| `pilot_fit` | A committed pilot artifact that estimates this quantity for the *current* cohort/design. Pilot must run before main analysis if the gate depends on it. See § 2c. |
| `related_cohort_baseline` | A baseline analysis on a different but mechanistically-comparable cohort (e.g., healthy-tissue scRNA when the analysis is on disease scRNA). |
| `analyst_judgment` | Number picked from intuition without enumerable provenance. **Over-confidence flag.** |

The `analyst_judgment` class is intentionally uncomfortable to declare,
and that discomfort is the point. When the user proposes a number whose
honest classification would be `analyst_judgment`, present four options
in this order:

1. **Demote to `acknowledged`.** If the parameter is genuinely
   relevant but the user can't justify a number, set `expected.central`
   and `expected.range` to null. Most defensible default.
2. **Defer to pilot calibration (§ 2c).** Register a pilot or
   related-cohort baseline whose output will supply the cut before the
   main analysis runs. This is the *constructive* path — it turns "I
   picked a number" into "we will derive a number, by this rule, from
   this artifact."
3. **Widen the gate range substantially.** If the analyst's intuition
   is right about *direction and order of magnitude* but not the precise
   cut, author a wide range so the cuts are clearly boundary conditions
   rather than load-bearing thresholds. Soft-gate semantics apply.
4. **Accept the `analyst_judgment` flag as a permanent caveat.** Only
   for cases where the analyst's judgment is itself the relevant
   evidence (e.g., a domain expert's prior on direction), and the user
   accepts that the verdict will carry the caveat throughout downstream
   citation.

If the user picks option (4) without first considering (1)-(3), push
back. The `analyst_judgment` flag exists to *surface* anchoring, not to
launder it.

Authoring guidance:
- A block can have mixed `calibration_source` values across its
  `provenance:` entries. The tier classification (hint vs calibrated)
  reads off the *strongest* enumerable evidence — 3+ disparate-dataset
  `prior_own_analysis` entries clear `calibrated`; 1-2 `prior_own_analysis`
  or any number of `literature` clears `hint`; pure `analyst_judgment`
  with no other support should be `acknowledged` per option (1) above.
- `pilot_fit` entries are *promises before the pilot runs* and *evidence
  after the pilot completes*. The pilot's completion is the only event
  that promotes a `pilot_fit` entry from forward-reference to actual
  provenance. Updating the entry's `estimate:` and `ref:` after the
  pilot completes is the one post-authoring `provenance:` update
  permitted without an amendment, provided the pilot ran under the
  registered `derivation_rule`.

### 2c. Defer to Pilot Calibration

When § 2a/2b surface that a numerical cut would be `analyst_judgment` —
and the user picks option (2) from § 2b's pushback — register the
deferral in the pre-reg's `## Pilot Calibration` section. The deferral
itself is pre-registered: source, rule, and no-peeking discipline.

Walk the user through:

1. **Identify the target.** Which Expectations block's cuts are being
   deferred? Which § Decision Criteria threshold do they feed?
2. **Identify the calibration artifact.** What pilot fit or related-
   cohort baseline will produce the cut? Where will its output live
   (path, format)? When must it complete?
3. **Author the derivation rule.** Plain-language, specific enough that
   two independent readers would derive the same cut from the same
   pilot output. Avoid "we will choose a reasonable threshold" —
   reasonable-as-judged-after-data is exactly what the deferral is
   trying to prevent.
4. **State the no-peeking discipline.** Pilot must run on data that
   doesn't leak the main analysis's outcome. Common patterns: pilot
   runs on permutation-shuffled labels; pilot runs on a held-out
   cohort; pilot runs on a synthetic-data simulation that matches the
   real data's structural properties but not its true effect.
5. **Author the fallback.** What counts as pilot failure (degenerate
   null, missing data, etc.)? What happens to the gate if the pilot
   fails — usually a demotion of the parent Expectations block to
   `acknowledged`, or conversion of the gate to direction-only.

The pilot's output, once recorded, becomes a `pilot_fit`-typed
`provenance:` entry on the parent Expectations block. The cut moves
from `analyst_judgment` (or null, in the acknowledged case) to
pilot-derived. This is the only permitted pre-data refinement of a
provenance entry; everything else requires an amendment.

Pilot-calibration is the *cultural* complement to the schema. The
schema (tiers, soft gates, acknowledged) makes the absence of evidence
visible. Pilot calibration is the constructive answer: when evidence
is absent, build it before authoring the cut.

### 3. Define Decision Criteria

Frame decision criteria according to the target class identified in § 0.

**Expectations-to-criteria binding (required when § 2a produced any
Expectations blocks):** every *interpretive* numerical threshold authored
here — a threshold reading observed effects, CIs, or posterior quantities
as supporting / weakening / refuting the hypothesis — must trace back to
an Expectations block via that block's `gate_use:` field. Three rules:

- **Operational / QA thresholds are out of scope.** Minimum sample size,
  MCMC convergence checks (R-hat, ESS), leakage / suspicious-result
  bounds, QC floors, and runtime limits do not need Expectations blocks;
  they live in `## Known Limitations`, `## Suspicious/Unexpected Result
  Plan`, or the paired analysis-plan doc (`spec:` in frontmatter) with
  their own rationale.
- **`hint`-backed criteria must have a wider acceptance range authored up
  front.** "Soft" gates lower the evidential weight of both pass and fail
  (a hint-backed pass is less probative; a hint-backed fail is less
  catastrophic) but do *not* grant permission to revise the threshold
  after data arrives. If a soft gate fails, the analysis either accepts
  the failure under the registered terms or invokes the amendment
  procedure — and a recalibrated gate cannot support a confirmatory
  claim for the same analysis. That analysis becomes path-B /
  exploratory for the recalibrated threshold; the original gate remains
  reported in the verdict.
- **Criteria with no upstream Expectations block must contain no
  interpretive numerical specificity.** Either author the block (driving
  the user through § 2a) or rewrite the criterion as direction-only /
  pattern-only.

Narrow gates (small CI windows, high PPC pass-rates, tight effect-size
thresholds) require `calibrated`-tier backing — i.e., the Expectations
block this criterion cites must have 3+ disparate-dataset own-analyses
in `provenance:`. If the user wants a narrow gate but only has `hint`-
tier support, the right move is to author a wider gate now and queue a
follow-up analysis that would upgrade the tier for the *next* pre-reg —
not to author a narrow gate and plan to "relax it if needed."

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
   - `science-plan-pipeline` — if no pipeline plan exists yet
   - `science-bias-audit` — to check for blind spots before running the analysis
   - `science-discuss` — to stress-test the expectations themselves
4. Commit: `git add -A && git commit -m "doc: pre-register expectations for <slug>"`

## Anti-patterns and Smells

Watch for these during § 2-4 authoring. Each one is a sign that
numerical specificity is outrunning evidence.

| Smell | What it looks like | Right move |
|---|---|---|
| **Tight gates with no enumerable provenance.** | Author proposes "97% PPC pass rate" or "R² < 50%" without pointing to a cohort, pilot, paper, or baseline that established the number. | Drive § 2b classification. If the honest answer is `analyst_judgment`, present § 2b's four options. |
| **`hint`-tier blocks with narrow gates.** | The provenance has one own-analysis or two literature references, but the registered gate range is small (e.g., ±10% of central). | Widen the range to match the evidence basis. Narrow gates need `calibrated` backing. |
| **Empty `unknowns:` at `hint` tier or below.** | Author asserts there's nothing they don't know about the quantity. | Push back. At `hint` tier and below, at least one genuine unknown is almost always available — confounding generator, batch effect, scoring-method dependence, generalization to other cohorts. |
| **"Reasonable threshold" deferrals without a derivation rule.** | `## Pilot Calibration` says "we will pick a sensible cut after the pilot" without specifying how. | Author the derivation rule explicitly. Two readers should derive the same cut from the same pilot output. |
| **Soft bands borrowed from convention.** | The inconclusive band is "40-60%" or "0.05 < p < 0.1" because those are conventional, not because the evidence basis supports those particular widths. | Either anchor the band to the evidence basis (literature spread, prior own-analysis CIs) or defer the cuts to a pilot. |
| **Gate cuts where the same number appears in the task description.** | The pre-reg's central cut is the exact number the task author sketched in the task description, with no independent provenance. | Anchoring smell. Acknowledge the source, classify as `analyst_judgment`, and present § 2b's options. |
| **Verdict labels with no scope qualifier.** | Pre-reg says "supports H_X" without specifying "in cohort/design Y". | For single-dataset analyses, force scope into the verdict label (e.g., "Walker-only consistent with X"). The architectural-change interpretation should require independent replication regardless of within-cohort outcome. |
| **Reaching for `calibrated` by adding literature references.** | Author adds 3 paper references to a provenance list and labels the block `calibrated`. | The 3+ requirement is for *own analyses on disparate datasets*. Literature alone keeps the block at `hint` regardless of count. |
| **Operational thresholds dressed up as Expectations.** | Sample size minimums, R-hat ceilings, ESS floors, or QC bounds authored as Expectations blocks. | These belong in `## Known Limitations` or the paired analysis-plan doc. Expectations blocks are for interpretive biology, not pipeline machinery. |

When two or more smells coincide on the same Expectations block, the
block is almost certainly over-specified. Demote to `acknowledged`,
defer to pilot, or widen the gate.

## Worked Example: The t648 PPC Gate Failure

A real failure mode that motivated this skill's cultural reform.

**Setup.** A pre-reg for a hierarchical NB fit on ~318k cells / 49
patients registered a §5 precondition gate: *"97% of patients must
have observed sample SD inside the 90% predictive interval of the
NB-with-shared-φ model."* The gate was authored *before* the production
fit ran.

**What happened.** The fit converged cleanly (R̂ < 1.001, ESS_bulk > 4800,
zero divergences) but failed the gate: 33% of patients passed the SD
check, 65% passed the mean check. The misfit was real (per-patient
dispersion was heterogeneous in a way the shared-φ model couldn't
absorb), but the gate's threshold was *uninformative* — at n ≈ 6800
cells per patient, the predictive interval of sample SD is narrow
enough that no partially-pooled hierarchical model can reliably hit 97%
containment.

**The anti-patterns.** Three smells from the table above were present:

- Tight gate with no enumerable provenance: the 97% number came from
  analyst judgment ("seems strict but achievable") with no pilot, no
  literature, no related-cohort baseline.
- Empty unknowns: the gate's interaction with per-patient n was a
  known unknown that wasn't surfaced.
- Soft band borrowed from convention: 97%/90% is a conventional
  pair (90% CI, near-total containment) but the evidence basis didn't
  support that specific pair at this n.

**The corrected pattern.** Under the schema + cultural reform:

- The gate's §2a Expectations block would record `expected.central:
  null`, `evidence_tier: acknowledged` — no prior cohort had measured
  per-patient SD containment at n ≈ 6800.
- `## Pilot Calibration` would defer the cut: *"Run a 4-patient, 1000-
  cell-per-patient pilot fit. Derive the 97% threshold from the pilot's
  observed containment rate inflated by ×1.3 to account for the n
  difference."*
- Or, more honestly: the gate would be reframed as direction-only —
  "containment rate is reported; the verdict reads as 'severe misfit'
  if containment < 50% and 'tolerable misfit' otherwise, with the
  specific containment fraction always reported."

Either correction would have surfaced the n-dependence of the gate
*before* the fit ran, prevented the path-B amendment churn, and
preserved the verdict's evidential weight. The schema makes the
absence of evidence visible (`acknowledged`); pilot calibration is the
constructive response (`pilot_fit`); the smells list is the watchlist
for catching this pattern at authoring time.

Full history: this project's `task:t672` and its source pre-registration's
amendment chain.

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

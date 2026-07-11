# Estimator Doctrine — implementation plan

> **For agentic workers:** implement task-by-task. Steps use checkbox (`- [ ]`) syntax.
> Every anchor below was verified against the working tree; do not trust a line number blindly —
> re-grep the quoted text if a file has moved under you.

**Goal:** Ship the estimator doctrine from
[`2026-07-11-estimator-doctrine-design.md`](2026-07-11-estimator-doctrine-design.md) — a new
statistics leaf, a correction to an existing one, a pre-registration gate, and hooks in
`plan-analysis`, `pre-register`, `post-mortem`, and the `computational-analysis` aspect.

**Architecture:** Prose only. No CLI check, no validator rule, no lint. The doctrine's force is
that an author *encounters* it (the gate is in the scaffold), not that a validator rejects them.
That limit is real and is stated in the artifacts themselves rather than papered over.

**Tech stack:** Markdown under `skills/`, `commands/`, `templates/`, `aspects/`; two Python-adjacent
constraints — a packaged template shadow with a byte-identity test, and `science skills lint`.

## Global constraints

- **Two pre-registration templates.** `templates/pre-registration.md` and
  `science/model/src/science_model/templates/pre-registration.md` must stay **byte-identical**
  (`science/model/tests/test_templates.py` asserts it). The **packaged** copy is what `Renderer`
  reads by default, so editing only the root changes nothing an author sees.
- **`science skills lint` is machine-enforced.** Every `skills/**/*.md` needs YAML frontmatter with
  `name` + `description`, a `## Companion Skills` section, and an entry in `skills/INDEX.md`.
- **A template body heading with no `_template.sections` row is a KeyError crash**, not a silent
  no-op. The registry `name:` must match the `## ` heading **exactly**. Body order = render order.
- **`codex-skills/` is generated.** Never hand-edit. Regenerate with
  `cd science && uv run --frozen python ../scripts/generate_codex_skills.py`.
  Only `commands/*.md` are mirrored — `skills/statistics/*` leaves are **not**.
- Repo conventions: no AI-attribution trailers; no "legacy"/"compatibility" layers; explicit over
  defensive; `~/d/` in docs, not absolute paths.
- Validation, from the worktree root:
  ```bash
  cd science && uv run --frozen pytest
  cd science/model && uv run --frozen pytest
  cd science && uv run --frozen science skills lint --root ../skills
  ```

---

## Task 0: Clear the pre-existing codex-skills drift (do this FIRST, alone)

**Why:** `codex-skills/science-big-picture/SKILL.md` is already stale against
`commands/big-picture.md` (the InstrumentResult work edited the command; the mirror was last
regenerated in `656368c5`). No test catches it. If you regenerate the mirror as part of a later
task, an unrelated ~20-line `InstrumentResult` diff lands in *this* design's commit.

**Files:** `codex-skills/**` (generated)

- [ ] **Step 1: Regenerate the mirror before touching anything else**

```bash
cd science && uv run --frozen python ../scripts/generate_codex_skills.py
cd .. && git status --short codex-skills/
```
Expected: `codex-skills/science-big-picture/SKILL.md` modified (and possibly others), with a diff
about `InstrumentResult` / `list_research_orphans` — nothing to do with estimators.

- [ ] **Step 2: Commit it on its own**

```bash
git add codex-skills/
git commit -m "chore(codex-skills): regenerate the mirror; absorb pre-existing big-picture drift"
```

If `git status` shows nothing, the mirror was already current — skip both steps and move on.

---

## Task 1: The new leaf — `skills/statistics/estimator-certification.md`

**Files:**
- Create: `skills/statistics/estimator-certification.md`
- Modify: `skills/INDEX.md` (append under `## Statistics`, after `statistics-population-genetics-likelihood`)
- Modify: `skills/statistics/SKILL.md` (`## Leaves` table; `## Principles` — currently ends at 11)
- Modify: `commands/plan-analysis.md` (`## Leaf Selection Rubric` table)

**Interfaces:**
- Produces: registry id `statistics-estimator-certification`, consumed by Task 2's companion link
  and by the rubric row here.

- [ ] **Step 1: Write the leaf**

It must open with frontmatter and must contain `## Companion Skills` — `science skills lint` exits 1
otherwise. Content follows design §2, §3, §4.

````markdown
---
name: statistics-estimator-certification
description: Use when an analysis fits parameters numerically — any optimiser, profile likelihood, nuisance parameters, ODE or other discretisation in the inferential path — and especially before a pre-registered threshold, compute budget, or gate is allowed to depend on the fit.
---

# Estimator Certification

An estimator's self-report is not evidence about the estimator. "Converged" is a claim the
optimiser makes about itself, and a converged, multi-start optimum can be reproducibly,
repeatedly wrong. Certification is the discipline of establishing — *before* a threshold, a
budget, or a gate depends on it — that the number you are about to read is a function of the
data rather than of the run.

The failure this prevents is not a noisy answer. It is a **confident** one.

## The Four Axes, In Cost Order

Each is meaningless if the one above it is unsettled. They are cheapest-first, which is also
correctness-first — this is not a coincidence.

| Axis | Question | Cost |
|---|---|---|
| **0. Well-posedness** | Is the *problem* resolvable at all? | free (design-only, no data) |
| **1. Forward-map accuracy** | Does the code compute the model? | cheap |
| **2. Reproducibility** | Is the answer a function of the data, or of the run? | moderate |
| **3. Threshold calibration** | Does the decision rule have the null it claims? | expensive |

**Ordering rule: establish well-posedness → certify the estimator → price the design → commit
the budget.** A budget committed before certification is not a constraint on the analysis; it
is a consequence of an untested assumption. If you must commit early, mark the budget
**CONDITIONAL** and name what invalidates it.

## Axis 0: Is the Problem Resolvable?

Reproducibility and accuracy are properties of *an estimator applied to a problem*.
Well-posedness is a property of the **problem** — model × design × noise — and it dominates both.

If the likelihood has a flat ridge:

- the "true minimum" an accuracy check compares against **does not exist as a point** — two
  optimisers landing at different nuisance values with equal objective are *both right*;
- spread in the argmin is a **faithful report of genuine flatness**, not a defect;
- and the most dangerous available "fix" is an optimiser whose bias manufactures a unique
  apparent minimum.

**So skipping Axis 0 gives Axis 2 a perverse gradient: it will "fix" non-identifiability by
selecting a biased estimator.** This is why conditioning comes first.

Check, before any data touches the model: structural identifiability (rank of the sensitivity
matrix); practical identifiability (**are the profile-likelihood CIs closed?**); the Hessian/FIM
condition number and eigenspectrum at the optimum; sloppy-direction analysis.

### The discriminant: argmin spread vs objective spread

Write the failure taxonomy **before** the failure, and make it operable:

> Across replicates (Axis 2), compare the spread of the **argmin** against the spread of the
> **objective value**.
>
> - Argmin moves, objective stable → **flat ridge; practical non-identifiability.** The estimator
>   is fine; the parameter is not estimable. Say so.
> - Objective itself moves → **optimiser failure.**
>
> A doctrine that only ever discusses the spread of the *statistic* cannot tell these apart.

A taxonomy written *after* the failure will always find the category that closes the ticket.

## Axis 1: Does the Code Compute the Model?

An inaccurate forward map makes the objective **rough**, and a rough objective is what breaks
finite-difference gradients and inflates seed spread. Certifying an optimiser on top of an
uncertified forward map is meaningless — so this is upstream of Axis 2, not parallel to it.

### An independent reference means a different ERROR-GENERATING MECHANISM

This is the rule most often got wrong, including by an earlier draft of this skill.

Refining the step or tolerance of the **same scheme** is **not** an independent reference:

- **Same leading truncation term.** Error is `C(t,y)·h^p` with the same `C`. `u_h` and `u_{h/10}`
  have *correlated* error. Their agreement bounds nothing on its own.
- **Same stability boundary.** A stability failure (`|λh|` outside the stability region) is a
  *threshold*, not a smooth function of `h`. Richardson-type reasoning is valid only *inside* the
  asymptotic regime — and **you cannot establish that you are inside it by comparing two step
  sizes.**
- **Same bugs.** A wrong right-hand side, or a step heuristic that omits a term, is invisible to
  refinement. Refinement is blind to every error that is not a pure function of `h`.

> **Accuracy requires a reference with a different error-generating mechanism**: a different
> scheme *family* (implicit vs explicit, multistep vs Runge–Kutta), or an adaptive solver with
> error control at a tolerance 2–3 orders below the target.
>
> Step/tolerance refinement of the same scheme is a **convergence check, not a reference**, and it
> is informative only in its verified form — the **observed order of accuracy**
> `p̂ = log₂( ‖u_h − u_{h/2}‖ / ‖u_{h/2} − u_{h/4}‖ )`, checked against the theoretical `p`. If
> `p̂ ≠ p` you are not in the asymptotic regime, or you have a bug. Agreement between `u_h` and
> `u_{h/10}` **without an order check is not evidence.**

**Two implementations of the same scheme is an invariance check, not an accuracy check.** They are
equivariant at any step size and will agree to machine precision while both are wrong.

### The assertion that needs no reference at all

> **Stability-region assertion.** Evaluate the Jacobian spectrum along the trajectory; assert
> `|λ_max · h|` stays inside the scheme's stability region **at every step**.

## Axis 2: Is the Answer a Function of the Data, or of the Run?

### Two seeds falsify. They do not certify.

Two replicates give one pairwise difference. For `X₁,X₂ ~ N(μ,σ²)`, `|X₁−X₂|` is half-normal:
mean ≈ `1.13σ`, SD ≈ `0.85σ` — a **coefficient of variation of 0.76**. Meanwhile the
decision-relevant quantity is a **tail**, not a median.

> A large observed spread is **proof** of an unreliable estimator — and a two-minute check that can
> save weeks. A small spread from two draws is **not** proof of a reliable one.
>
> **Certification requires R ≥ 5 replicates, and R ≈ 20+ if the gate sits near its margin. Report
> the MAX over replicates and over analysis units — never the median.**

### Perturb every inferentially irrelevant degree of freedom

Not "the seed" — **every choice the science does not name**: the **start point** (jittered over
the plausible box), unit/block ordering, tie-breaking, BLAS thread count and reduction order, and
any RNG seed present.

> **If the estimator has no stochastic element, INJECT one.** A deterministic optimiser from a
> fixed start reproduces itself bit-for-bit: spread zero, gate passes, **check cannot fail**. That
> is not a certification, it is ceremony — see *Designing a Check That Can Fail*. A randomised
> multistart jitter is the minimum.
>
> An estimator that cannot be perturbed cannot be certified for reproducibility. It can only be
> certified for accuracy.

### The smoothing gradient — why reproducibility ALONE is adversarial

**Any operation that smooths the objective reduces spread while increasing bias.** A large
finite-difference step; a loose inner tolerance; coarse integration; heavy regularisation; early
stopping. Selecting an optimiser on low variance alone therefore selects *for* bias — actively,
not incidentally.

Accuracy alone, by contrast, is merely **insufficient** (there is no perverse gradient in "be
closer to the truth"). The two failures are not symmetric, and the asymmetry is the point.

**Also: per-unit convergence does not imply pooled convergence** when the likelihood sums many
independently-optimised blocks. One-sided per-unit errors **add rather than cancel**.

## Axis 3: Does the Decision Rule Have the Null It Claims?

Certifying the estimator certifies that you computed `T` correctly. It says **nothing** about
whether `Pr(T > c | H₀) = α`.

Where the nuisance dimension **grows with the sample** — per-unit nuisance parameters, i.e.
Neyman–Scott incidental-parameter territory — the profile MLE is **inconsistent**, the profile
score is **biased**, and the profile LR does **not** have a `χ²₁` null. A perfect optimiser on a
perfect integrator can still produce a badly miscalibrated test.

> **Verify the null distribution by simulation** (parametric bootstrap under the restricted model).
> Do not assume Wilks. Where nuisance dimension grows with `n`, prefer a modified/adjusted profile
> likelihood (Cox–Reid conditional profile; Barndorff-Nielsen `p*`; Severini), or a
> hierarchical/random-effects treatment — and check the empirical LR distribution against `χ²₁`
> **before** any threshold is pre-registered.

Note the trap: the error budget below is scaled by `σ_null(T)`. **If Axis 3 was skipped, that scale
is itself unverified** — you are calibrating your instrument against a ruler you have not checked.

### When simulating the null is unaffordable

It often is. This axis is **not** unconditionally required — but it may not be silently skipped
either. It must be **either EXECUTED or explicitly CONDITIONAL**, and a `CONDITIONAL` carries four
obligations:

> 1. **Cost.** What executing it would take.
> 2. **Trigger.** What would cause it to be executed.
> 3. **Invalidation clause.** What voids the deferral.
> 4. **The decisions that MAY NOT depend on it until it completes.**
>
> (4) is the one with teeth. Deferring Axis 3 does not add a caveat — it **removes decisions from
> the table.** Any verdict resting on `Pr(T > c | H₀) = α` is unavailable while the null is
> unverified, and you must name those verdicts **before the analysis runs**.

**An uncalibrated threshold is not a slightly-weaker threshold.** It is a threshold whose error rate
is unknown, and a decision rule with an unknown error rate is not a decision rule.

## Profiling

`nll_prof(ψ) = min over nuisance η`. **Warm-starting the inner fit from the previous grid point
makes the computed value depend on the path taken through the grid — so the "objective" is not a
function of ψ at all.** A tell-tale: an outer optimiser terminating *above* a value it already
evaluated. That is impossible for a genuine function.

But **functionhood is necessary, not sufficient, and it is not the property that matters.** The
profile enters inference only through **differences**, `Δnll = nll_prof(ψ) − nll_prof(ψ̂)`.

> The requirement is that inner-solve error be **(a) deterministic in ψ**, **(b) bounded well below
> the Δnll the inference resolves**, and **(c) approximately UNIFORM in ψ** — because a
> ψ-independent bias **cancels in the difference** and a ψ-dependent one **does not**.

| Protocol | (a) deterministic | (b) boundable | (c) uniform in ψ | Cost |
|---|---|---|---|---|
| Warm-starting | ✗ | ✗ | ✗ | cheap |
| Fixed continuation path | ✓ | partly | **✗ by construction** | **expensive** |
| **Fixed multistart pool** | ✓ | ✓ (raise `k`) | plausibly | moderate |

**Prefer a fixed multistart pool.** A fixed continuation path *does* restore functionhood — the
path does not depend on evaluation history — but it re-runs the entire path at every outer
evaluation (`O(m)` inner solves per call), and it carries the solution along whatever basin the
path lands in, so at a basin boundary it sits on the wrong branch. **Fixing the path converts a
path-dependence bug into a reproducible bias** — which, per the smoothing gradient above, is the
most dangerous state an estimator can be in.

### The outer optimiser must be justified against the profile's smoothness

A fixed-multistart profile is a **discontinuous** function of ψ — the winning start switches basins.
Functionhood is restored; **smoothness is not.** Running a gradient- or FD-based *outer* optimiser
over a piecewise surface is a second-order version of the bug the multistart pool was adopted to fix.

There is no universally correct outer optimiser, so this skill does not name one. It requires a
declaration:

> **Declare why the outer optimiser is valid for this profile's smoothness / discontinuity
> structure.**
>
> **Gradient-based and finite-difference-based outer methods are PROHIBITED unless smoothness is
> demonstrated** — demonstrated, not assumed and not asserted. A fixed-multistart profile is
> discontinuous *by construction*, so for one the default position is: **prohibited**.
>
> Absent a smoothness demonstration: use a derivative-free outer method, or a dense grid with local
> refinement.

A gradient step on a surface with basin-switch cliffs will happily report convergence at a cliff
edge. That is the same failure as warm-starting, one level up.

### The inner tolerance is derivable

Inner-solve error in `nll` is **one-sided** (a returned minimum is always ≥ the true minimum), and
with `n` independently-optimised blocks the per-block errors **sum**. To resolve a pooled `Δnll`
of `δ`, per-block inner accuracy must be `≲ δ/n`:

- `δ = 1.92`, 17 blocks → **≤ 0.11 nll/block**
- `δ = 1.92`, 136 blocks → **≤ 0.014 nll/block**

### Certify the DIFFERENCE, not the pieces

In a likelihood ratio `LR = 2(nll_restricted − nll_unrestricted)`, **both** terms carry one-sided
upward optimiser error. Those errors cancel **only if both models are optimised to equal
accuracy** — and the larger model is systematically the harder one, hence systematically the
*less* well optimised.

> **Optimiser error in an LR is not mean-zero and not conservative. Its sign is set by which model
> is harder to fit.** Match the inner tolerance **between the compared models**, and run
> certification on the **difference statistic**. Certifying `nll` to a tolerance says nothing
> about `Δnll`.

## One Error Budget, Three Outcomes

Two independent gates with two independent tolerances can **both pass while the decision flips**:
bias `0.4c` and spread `0.4c` each clear a 50%-of-`c` gate, but together they move the statistic by
`0.8c`. So combine them:

> **E := |b̂| + k·s**, with `k ≈ 2–3` (so the reproducibility term is an upper-tail bound, not a
> median), where `b̂` is measured bias against the independent reference and `s` the replicate
> spread.
>
> **Certification passes iff `E ≤ ρ · σ_null(T)`, with `ρ = 0.1` by default.**

### ρ, the instrument-error fraction — and why it is not called α

`ρ` is **dimensionless** and is measured against `σ_null(T)`, the sampling SD of the decision
statistic under its **declared null**.

> **Never call this `α`.** In likelihood testing `α` is the **test size** — the thing in
> `Pr(T > c | H₀) = α`. A constant named `α` sitting beside a likelihood-ratio threshold will be
> read as a significance level. It is not one. It is the fraction of the statistic's own null
> variability that the *instrument* is permitted to contribute.

**Do not state the bound as a percentage of the critical value.** That percentage is a property of
one particular null, not a rule — it drifts with the degrees of freedom and degenerates entirely
for non-`χ²` nulls and for `c → 0`. At a 5% test size:

| Null | `σ_null = √(2·df)` | `c` | `ρ·σ_null` at ρ=0.1 | …as % of `c` |
|---|---|---|---|---|
| χ²₁ | 1.414 | 3.841 | 0.141 | **3.7%** |
| χ²₂ | 2.000 | 5.991 | 0.200 | **3.3%** |
| χ²₃ | 2.449 | 7.815 | 0.245 | **3.1%** |
| χ²₅ | 3.162 | 11.070 | 0.316 | **2.9%** |

If you want a threshold-relative number, **derive it for your declared null.** Do not carry one
over.

> **Default `ρ = 0.1`** — the instrument then inflates `Var(T)` by ~1%, which is immaterial under
> any usual convention. Override it if you can justify it, but **`ρ` is never allowed to go
> unstated.**

### The third outcome

A global green light does **not** license every individual verdict. Even a certified estimator has
residual error `E > 0`, and any unit whose statistic sits within `E` of `c` is **unresolvable by
that instrument**.

> **Three outcomes, not two.** Per reported unit: **reject** if `T̂ − c > E`; **do-not-reject** if
> `c − T̂ > E`; otherwise **INDETERMINATE — the instrument cannot resolve this unit.**
>
> An honest estimator with known error yields three outcomes. Reporting two is how a
> flipped-by-noise cohort gets published as a clean decision.

## Designing a Check That Can Fail

Before a check may discharge an obligation, answer: **what result would have made this check
fail?** If no achievable result would, the check is not merely ceremony — it is *evidence-shaped*
ceremony, which is how it discharged the obligation in the first place.

Apply this to your own gates. A reproducibility check on a deterministic optimiser cannot fail. An
invariance check between two implementations of one scheme cannot detect inaccuracy.

Three specific traps:

- **A threshold on a surface must pre-specify the domain of its max**, up front, alongside the
  value. Narrowing the domain *after* seeing the number is the renegotiation pre-registration
  exists to prevent.

  But the naive fix is **circular**: the region "the analysis actually consults" is *estimated* —
  defined by where the optimiser believes the minimum is — so a fidelity check evaluated only
  there **cannot detect a true minimum lying elsewhere**. Pre-specify the domain as a **rule**, not
  a region, **and** verify the region is **closed under descent**: no point outside it has a lower
  objective than the minimum inside it.

- **A probe must not discretise a parameter whose true values vary across its own cells.** Put the
  simulated truths **on** the nodes, or remove the grid. Before interpreting any probe outcome,
  **check for correlation between the outcome and distance-to-node.**

- **An unexpectedly *interesting* result from a validation probe is a probe-defect signature, not a
  finding.** A broken probe does not announce itself by returning nothing — it returns something
  worth writing up.

### Checks that can actually fail

Rejecting bad checks is half the job. Reach for these:

| Check | Cost | Fires when |
|---|---|---|
| Nesting monotonicity: `nll_unrestricted ≤ nll_restricted` | free | optimiser failure, always |
| Outer optimum ≤ best evaluated point | free | broken/moving objective |
| `nll_prof(ψ̂) == nll_global`; `nll_prof(ψ) ≥ nll_global` | free | broken profile |
| Argmin-spread vs objective-spread | free (reuse replicates) | separates non-identifiability from optimiser failure |
| Autodiff/adjoint gradient vs production FD gradient | cheap | an FD step that smooths basins away |
| Jacobian spectrum vs the scheme's stability region | cheap | integrator instability |
| Observed order of convergence `p̂` vs theoretical `p` | moderate | pre-asymptotic regime; RHS bugs |
| Simulated null distribution of `T` vs `χ²` | expensive | miscalibrated threshold |

## "No Independent Reference Exists" Is Almost Always False

A reference essentially always exists for the two things certification is about. What may not exist
is a reference for whether the **model** is right — but that is validation of the model, not
certification of the estimator, and conflating them is how "we can't check it" gets said out loud.

**Forward map:**

- **Method of Manufactured Solutions.** Choose an analytic `u*(t)`, substitute into the ODE to
  derive the source `s(t) = du*/dt − f(u*)`, integrate the *modified* system, compare to `u*`
  exactly. Works for arbitrary nonlinear right-hand sides. This is **the** canonical answer to "no
  analytic solution exists."
- Order-of-accuracy verification under systematic refinement.
- **Analytic limits**: zero-density, single-clone, no-treatment, linearised, equilibrium — any
  parameterisation collapsing the model to closed form.
- **Invariants**: conservation, positivity, monotonicity, known bounds. A violation is *proof*.
- Stability-region assertion (no reference needed at all).
- An independent implementation **from the spec** (not a port), ideally different language/library.

**Estimator:**

- **Synthetic data with known truth.** You can always simulate from your own model, so the truth is
  known **by construction**. Parameter recovery, CI coverage, SBC ranks.
- **A gold-standard optimiser as reference for the argmin**: a global method (CMA-ES, differential
  evolution, basin-hopping) run to a large budget on a *certification subsample*. **The reference
  for an optimiser is a more expensive optimiser.** This always exists; it is only ever expensive.
- **Exact gradients (autodiff/adjoint) vs production FD gradients** — cheap, always available, and
  a direct detector of a bias-inducing FD step.
- Free self-consistency assertions (the table above).

> **An estimator is essentially never uncertifiable. It may be unaffordably certifiable — which is
> a budget statement, not an epistemic one.**

## Common Failure Modes

- **Converged, multi-start, and reproducibly wrong.** The optimiser's self-report is not evidence.
- **The reproducible config is the biased one.** Low seed spread bought by smoothing the objective.
- **The interesting artifact.** A confounded probe produces a substantive-looking finding that
  vanishes when the probe is fixed.
- **The budget priced on an assumed estimator.** A protocol rejected by its own fidelity test can
  be off by orders of magnitude — the certifiable protocol is the one to price.
- **Per-unit convergence read as pooled convergence.** One-sided errors add.
- **A gate that cannot fail**, discharging an obligation it never tested.

## Halt-On Conditions

- The objective is not a function of its own arguments (warm-started inner fits). **Stop.** Nothing
  downstream is interpretable.
- The error budget exceeds its bound (`E > ρ·σ_null`). The threshold is finer than the
  instrument's resolution. **Do not report reject/do-not-reject** — report INDETERMINATE, and
  either certify a better estimator or widen the threshold.
- Structural non-identifiability. No estimator fixes this; change the design.

## Reporting

State: the four axes and how each was established; the independent reference and **why its error
mechanism differs**; `R`, and the **max** (not median) spread over replicates and units; `b̂`, `s`,
`k`, `ρ`, and the resulting `E`; the outer optimiser and **why it is valid for the profile's
smoothness structure**; whether Axis 3 was EXECUTED or CONDITIONAL (and if CONDITIONAL, the decisions
it removes from the table); the number of units falling in the **INDETERMINATE** band; and the
**invalidation clause** — re-certify whenever the estimator, forward model, tolerances, hardware, or
library stack changes. Where certification ran at reduced scale, state the **scaling law** carrying
it to full scale (per-unit does not carry to pooled).

## Companion Skills

- [`likelihood-model-comparison.md`](./likelihood-model-comparison.md) — AIC/BIC/LRT once the
  estimator is certified; its numerical-precision audit assumes what this leaf establishes.
- [`population-genetics-likelihood.md`](./population-genetics-likelihood.md) — nuisance parameters
  must be estimated jointly, profiled, or pre-registered as such.
- [`sensitivity-arbitration.md`](./sensitivity-arbitration.md) — pre-commit which comparison is
  verdict-bearing before the arms disagree.
- [`bias-vs-variance-decomposition.md`](./bias-vs-variance-decomposition.md) — the trade this leaf's
  smoothing gradient exploits.
- [`prereg-defensive-instrumentation.md`](./prereg-defensive-instrumentation.md) — gates that
  consume design geometry and synthetic data only, before any observed value is read.
````

- [ ] **Step 2: Register in `skills/INDEX.md`**

Append under `## Statistics`, after the `statistics-population-genetics-likelihood` line:

```markdown
- `statistics-estimator-certification`: `skills/statistics/estimator-certification.md`
```

- [ ] **Step 3: Register in `skills/statistics/SKILL.md`**

Add a row at the end of the `## Leaves` table:

```markdown
| [`estimator-certification`](./estimator-certification.md) | An analysis fits parameters numerically — an optimiser, a profile likelihood, an ODE — and a threshold, budget, or gate is about to depend on the fit. |
```

Add Principle 12 (the list currently ends at 11):

```markdown
12. **An estimator's self-report is not evidence about the estimator.** "Converged" is a claim the
    optimiser makes about itself; a converged, multi-start optimum can be reproducibly wrong.
    Certify well-posedness, forward-map accuracy, reproducibility, and threshold calibration —
    in that order, cheapest first — *before* a threshold, budget, or gate depends on the fit.
    See [`estimator-certification`](./estimator-certification.md).
```

Do **not** add a `## When to invoke` bullet: that list is inconsistently maintained (7 of 11 leaves
have one; the two most recent additions do not). Matching precedent beats half-populating it.

- [ ] **Step 4: Add the rubric row in `commands/plan-analysis.md`**

Append to the `## Leaf Selection Rubric` table:

```markdown
| Profile likelihood, nuisance parameters, optimiser choice, ODE / numerical integration, parameter recovery, synthetic-recovery gate | `statistics-estimator-certification` |
```

- [ ] **Step 5: Verify the linter passes**

```bash
cd science && uv run --frozen science skills lint --root ../skills
```
Expected: exit 0. If it fails on `## Companion Skills`, frontmatter, or INDEX coverage, fix the leaf
— those three are hard-enforced.

- [ ] **Step 6: Commit**

```bash
git add skills/ commands/plan-analysis.md
git commit -m "feat(skills): add statistics-estimator-certification

An estimator's self-report is not evidence about the estimator. Four axes in cost
order -- well-posedness, forward-map accuracy, reproducibility, threshold calibration
-- each meaningless if the one above is unsettled. Ships the argmin-vs-objective
discriminant that separates non-identifiability from optimiser failure, the error
budget E = |b| + k*s with an INDETERMINATE third outcome, and the rule that an
independent reference means a different ERROR-GENERATING MECHANISM, not a finer step
of the same scheme."
```

---

## Task 2: Correct `likelihood-model-comparison.md`

**Why this is a correction, not an expansion:** the leaf currently tells an author to *"Confirm
optimizer convergence… Re-fit from multiple starts"* and names *"Unconverged or single-start
optimization"* as the failure mode. The source incident **converged** and **used multiple starts**,
and produced a reproducibly wrong answer. The leaf does not merely miss the failure — it certifies
the thing that failed.

**Files:** `skills/statistics/likelihood-model-comparison.md`

- [ ] **Step 1: Replace the optimiser bullet in `## Numerical-Precision Audit`**

Find:
```markdown
- Confirm optimizer convergence (gradient norm / relative tolerance), not just a
  returned value. Re-fit from multiple starts for multimodal likelihoods.
```
Replace with:
```markdown
- **Convergence is the optimiser's self-report, and is not evidence about the optimiser.** A
  converged, multi-start optimum can be reproducibly wrong. Before the comparison is read,
  certify the estimator — reproducibility under perturbation of every inferentially irrelevant
  choice, *and* accuracy against a reference with a different error-generating mechanism. See
  [`estimator-certification`](./estimator-certification.md).
- In a likelihood *ratio*, optimiser error does **not** cancel: both terms carry one-sided upward
  error, and the larger model is systematically the harder one to fit. Match the inner tolerance
  between the compared models.
```

- [ ] **Step 2: Add the missing failure mode**

In `## Common Failure Modes`, immediately after the "Unconverged or single-start optimization"
entry:
```markdown
- **Converged, multi-start, and reproducibly wrong.** The twin of the above, and the one that
  bites. Any operation that smooths the objective — a large finite-difference step, a loose inner
  tolerance, coarse integration — reduces seed spread *while increasing bias*. Selecting an
  optimiser on reproducibility alone therefore selects **for** bias.
```

- [ ] **Step 3: Companion-link the new leaf**

Add to `## Companion Skills`:
```markdown
- [`estimator-certification.md`](./estimator-certification.md) — certify the estimator before the
  comparison is read; this leaf's numerical-precision audit assumes what that one establishes.
```

- [ ] **Step 4: Verify and commit**

```bash
cd science && uv run --frozen science skills lint --root ../skills   # exit 0
cd .. && git add skills/statistics/likelihood-model-comparison.md
git commit -m "fix(skills): convergence is the optimiser's self-report, not evidence

The bullet this replaces is the advice that failed: the source incident confirmed
convergence and re-fit from multiple starts, and got a reproducibly wrong answer.
Adds the missing failure mode -- converged, multi-start, reproducibly wrong -- and
the smoothing gradient that produces it."
```

---

## Task 3: The pre-registration gate — BOTH template copies

**Files:**
- Modify: `templates/pre-registration.md`
- Modify: `science/model/src/science_model/templates/pre-registration.md` (**byte-identical**)
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Write the failing test first**

Follow the precedent of the existing paired gate tests in `science/tests/test_command_docs.py` —
they assert over **both** template paths.

```python
def test_pre_registration_templates_include_estimator_certification_gate() -> None:
    """Both copies carry the gate, and the packaged copy is the one Renderer reads."""
    for path in (
        REPO_ROOT / "templates" / "pre-registration.md",
        REPO_ROOT / "science" / "model" / "src" / "science_model" / "templates" / "pre-registration.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "## Estimator Certification Gate" in text
        assert "{ key: estimator-certification-gate," in text
        assert "required: true }" in text
        # The gate must not imply an enforcement that does not exist.
        assert "Nothing validates this section" in text
```

- [ ] **Step 2: Run it, confirm it fails**

```bash
cd science && uv run --frozen pytest tests/test_command_docs.py -k estimator_certification -v
```
Expected: FAIL — `assert "## Estimator Certification Gate" in text`.

- [ ] **Step 3: Add the registry row to BOTH copies**

In the `_template.sections` list, after the `total-comparison-count` row:

```yaml
    - { key: estimator-certification-gate, name: "Estimator Certification Gate", required: true }
```

The `name:` must match the `## ` heading **exactly** — a mismatch raises, and a body heading with
no row is a **KeyError on every render**.

- [ ] **Step 4: Add the body section to BOTH copies**

Immediately after `## Total Comparison Count` (body order = render order; the three existing gates
are `required: false` and vanish from a default scaffold, so appending at EOF would leave this gate
trailing a run of omitted ones):

````markdown
## Estimator Certification Gate

<!-- Applies when the analysis estimates parameters numerically -- any optimiser, profile, or
     ODE/discretisation in the inferential path. If it does not, DELETE this section.

     Nothing validates this section. Its force is that a threshold finer than its instrument's
     resolution is not conservative -- it is noise-driven, and the noise has a SIGN: optimiser
     error in a likelihood ratio is a difference of two one-sided biases, and the larger model is
     systematically the harder one to fit.

     Order: well-posedness -> certify -> price -> commit. A budget committed before certification
     is a consequence of an untested assumption, not a constraint on the analysis.

     See skills/statistics/estimator-certification.md. -->

| Axis | Commitment | Reference / domain |
|---|---|---|
| 0. Well-posedness | <structural + practical identifiability; are the profile CIs closed?> | <design-only; no data> |
| 1. Forward-map accuracy | <tolerance, on the DECISION STATISTIC, propagated> | <INDEPENDENT mechanism: a different scheme family, or an adaptive solver 2-3 orders tighter. NOT a finer step of the same scheme.> |
| 2. Reproducibility | <MAX over R >= 5 replicates -- not the median> | <perturb every inferentially irrelevant DOF: start point, ordering, threads, seeds. If the estimator is deterministic, INJECT jitter.> |
| 3. Threshold calibration | <null distribution of the statistic> | <simulated under the restricted model -- not assumed from Wilks> |
| 3. Threshold calibration | <EXECUTED, or CONDITIONAL> | <if CONDITIONAL: cost, trigger, invalidation clause, AND the decisions that may not depend on it until it completes> |
| Outer optimiser | <method; why it is valid for this profile's smoothness/discontinuity structure> | <gradient/FD-based methods PROHIBITED unless smoothness is DEMONSTRATED> |
| Error budget | E = \|b\| + k*s <= rho * sigma_null(T), k in [2,3] | <rho = 0.1 default, and NEVER unstated. Dimensionless, against the null's sampling SD -- NOT a % of the critical value, which drifts with df. Do not call it alpha; alpha is the test size.> |
| Indeterminate band | units with \|T - c\| <= E are INDETERMINATE, not silently decided | <report the count> |
| Compute budget | <cost> | <certified \| CONDITIONAL on ...> |
| Invalidation | <what re-opens this certificate> | <estimator, forward model, tolerances, hardware, libraries> |
````

- [ ] **Step 5: Confirm the two copies are byte-identical, then run both suites**

```bash
diff templates/pre-registration.md science/model/src/science_model/templates/pre-registration.md && echo "IDENTICAL"
cd science && uv run --frozen pytest tests/test_command_docs.py -k estimator_certification -v   # PASS
cd model && uv run --frozen pytest tests/test_templates.py -v                                   # PASS (byte-identity)
```

- [ ] **Step 6: Verify the scaffold actually renders it**

This is the check that catches the packaged-shadow trap:
```bash
cd science && uv run --frozen science entity sections pre-registration --format json | grep -i estimator
```
Expected: the `estimator-certification-gate` key, `required: true`. If absent, the packaged copy
was not edited.

- [ ] **Step 7: Commit**

```bash
git add templates/pre-registration.md science/model/src/science_model/templates/ science/tests/test_command_docs.py
git commit -m "feat(templates): add the Estimator Certification Gate to pre-registration

required: true, deliberately breaking the pattern of the three existing (optional)
gates. An optional gate is invisible to the author who does not already know the
doctrine exists -- precisely the author about to repeat the failure. The section
says out loud that nothing validates it: its force is that it is in front of you.

Edits BOTH template copies; the packaged one is what Renderer reads by default."
```

---

## Task 4: `commands/pre-register.md`

**Files:** `commands/pre-register.md`

- [ ] **Step 1: Add a NEW sub-axis for estimator certification**

Not under `#### Sub-axis: execution timing` — only two of the three gates live there. The
Calibration Gate already has its own sub-axis, and certification is likewise orthogonal to *when*
the analysis runs: it asks whether the instrument can **resolve** the threshold. Add, after the
existing calibration sub-axis:

```markdown
#### Sub-axis: can the instrument resolve the threshold?

If the analysis estimates parameters numerically — an optimiser, a profile likelihood, an ODE or
any other discretisation in the inferential path — a pre-registered threshold is a claim about an
**instrument** as much as about the world. A threshold finer than its instrument's resolution is
not conservative: it is noise-driven, and the noise has a sign.

Add an **Estimator Certification Gate**. It must commit, before any gate is evaluated:

- **Well-posedness** (free, design-only): is the parameter estimable at all? Skipping this makes
  the reproducibility criterion adversarial — it will "fix" a flat ridge by selecting a biased
  optimiser.
- **Forward-map accuracy** against a reference with a **different error-generating mechanism**. A
  finer step of the same scheme is a convergence check, not a reference.
- **Reproducibility** under perturbation of every inferentially irrelevant choice — start point,
  ordering, threads, seeds. If the estimator is deterministic, jitter must be **injected**; a check
  that cannot fail is not a check.
- **Threshold calibration**: the null distribution of the statistic, simulated — not assumed.
- The **error budget** `E = |b| + k·s ≤ ρ·σ_null(T)` — `ρ` is the dimensionless
  **instrument-error fraction** (default `0.1`, never unstated), measured against the null's
  sampling SD, **not** as a percentage of the critical value, which drifts with the degrees of
  freedom. Do not call it `α`; `α` is the test size.
- The **outer optimiser**, and why it is valid for the profile's smoothness structure —
  gradient/FD-based methods are **prohibited unless smoothness is demonstrated**.
- The **INDETERMINATE** band of units the instrument cannot resolve.

**Order: certify the estimator, then price the design, then commit the budget.** A budget priced
on an uncertified estimator is a consequence of an untested assumption, not a constraint — it can
be wrong by orders of magnitude. If the budget must be committed first, mark it **CONDITIONAL** and
name what invalidates it.

See [`skills/statistics/estimator-certification.md`](../skills/statistics/estimator-certification.md).
```

- [ ] **Step 2: Extend `### 4b. Plan for Suspicious/Unexpected Results`**

The step currently asks only what *too good to be true* looks like. Add its mirror:

```markdown
- An unexpectedly **interesting** result from a *validation probe* is a probe-defect signature, not
  a finding. A broken probe does not announce itself by returning nothing — it returns something
  worth writing up. Before interpreting it, check the probe is not confounded with the thing it
  validates (e.g. a probe that grids the very parameter whose true values vary across its cells).
```

- [ ] **Step 3: Commit**

```bash
git add commands/pre-register.md
git commit -m "feat(pre-register): certification sub-axis -- can the instrument resolve the threshold?

Certification is not an execution-timing question, so it gets its own sub-axis
(as the Calibration Gate already does) rather than joining the two gates that
answer 'when does this run'. Adds the certify -> price -> commit ordering, and the
mirror of 'too good to be true': an interesting result from a validation PROBE is
a probe-defect signature."
```

---

## Task 5: `commands/plan-analysis.md`

**Files:** `commands/plan-analysis.md` (the rubric row already landed in Task 1)

- [ ] **Step 1: Add a required body section**

To the required-body-section list, after `Model / Test Assumptions`:

```markdown
- Estimator and Probe Design
```

- [ ] **Step 2: Describe it in the Output section**

```markdown
**Estimator and Probe Design.** If the analysis estimates parameters numerically: name the
estimator, and state how each of the four certification axes will be established — well-posedness,
forward-map accuracy against an independent error-generating mechanism, reproducibility under
perturbation of every inferentially irrelevant choice, and calibration of the decision rule's null.
For **every validation probe** you plan, write the answer to: *what result would make this probe
fail?* A probe with no such answer is evidence-shaped ceremony. See
[`statistics-estimator-certification`](../skills/statistics/estimator-certification.md).
```

- [ ] **Step 3: Extend Workflow step 5**

Currently: *"State model/test assumptions, power floor or resolution limit, bias-vs-variance risks,
and sensitivity-arbitration rules."* Append:

```markdown
   If the analysis fits parameters numerically, also state the estimator certification plan (the
   four axes) and, for each validation probe, what result would make it fail.
```

- [ ] **Step 4: Commit**

```bash
git add commands/plan-analysis.md
git commit -m "feat(plan-analysis): require an Estimator and Probe Design section

Names the estimator, how each certification axis is established, and -- for every
validation probe -- what result would make that probe fail. A probe with no such
answer is evidence-shaped ceremony."
```

---

## Task 6: The `computational-analysis` aspect hook

**Files:** `aspects/computational-analysis/computational-analysis.md`

Nothing parses or tests aspect files — which cuts both ways: this edit trips no guard, and no guard
will catch a malformed anchor. Match the convention exactly.

- [ ] **Step 1: Insert a `## plan-analysis` section**

Between `## research-topic` and `## plan-pipeline`. The `(insert after: …)` anchor goes on **its own
line, blank-separated** — not inline:

```markdown
## plan-analysis

### Additional section: Numerical Accuracy

(insert after: Model / Test Assumptions)

When the workflow integrates an ODE, or otherwise discretises:

- **An independent reference means a different error-generating mechanism.** Comparing two
  implementations of the *same* scheme is an invariance check, not an accuracy check — they are
  equivariant at any step size and will agree to machine precision while both are wrong. Name a
  different scheme family, or an adaptive solver 2–3 orders tighter than the target.
- **Refinement alone is not evidence.** A finer step of the same scheme shares the leading
  truncation term and the stability boundary. If you refine, report the **observed order of
  accuracy** against the theoretical order — if they disagree, you are outside the asymptotic
  regime, or you have a bug.
- **Assert stability.** Evaluate the Jacobian spectrum along the trajectory and assert the step
  stays inside the scheme's stability region. This needs no reference at all.
- **State the tolerance on the decision statistic**, propagated — not on a trajectory, and not on
  an absolute likelihood.

See [`statistics-estimator-certification`](../../skills/statistics/estimator-certification.md).
```

- [ ] **Step 2: Commit**

```bash
git add aspects/computational-analysis/computational-analysis.md
git commit -m "feat(aspects): computational-analysis contributes Numerical Accuracy to plan-analysis

The aspect contributed nothing to plan-analysis, though plan-analysis reserves an
Aspect-contributed Sections slot. Asks for an independent error-generating mechanism,
an order-of-accuracy check, and a stability-region assertion whenever a workflow
discretises."
```

---

## Task 7: `commands/post-mortem.md` — three edits

**Files:** `commands/post-mortem.md`

- [ ] **Step 1: Add the success mode to `## When to use`**

The command frames the incident exclusively as failure. Append:

```markdown
Also use it when **a gate fired and nothing was lost** — a pre-registered check stopped the
analysis before any observed data was read. Nothing surfaced late, and no result exists: that is
the system working. **A post-mortem on a gate that fired is the cheapest kind, and its lessons are
the most transferable, because nothing is entangled with a finding anyone wants to defend.** In
this mode, read step 1's "gap between expectation and outcome" as *the gap between what the plan
assumed about its own instruments and what was true*.
```

- [ ] **Step 2: Sharpen step 4, the generalize gate**

Append to the step:

```markdown
   Separate **the failing thing** (usually local — a specific model, a specific optimiser) from
   **the reason it was not caught sooner** (usually global — a check that could not fail, a
   threshold with no domain, a probe confounded with its own target). **File on the latter.** The
   mechanism generalises to nothing; the blind spot generalises to everyone.
```

- [ ] **Step 3: Open the target list in step 5**

The list reads as a closed enumeration but `--target` is free text, and it omits `aspect:`
entirely. Replace the enumeration with:

```markdown
   `--target` is free text. The resolvable namespaces are `skill:`, `command:`, `aspect:`,
   `template:`, and `cli:` — e.g. `skill:statistics`, `command:plan-analysis`,
   `aspect:computational-analysis`, `template:pre-registration`. Name the surface that should have
   caught it, not the nearest one on a list.
```

- [ ] **Step 4: Commit**

```bash
git add commands/post-mortem.md
git commit -m "feat(post-mortem): a gate that fired is a post-mortem too

Adds the success mode (nothing surfaced late, no result exists -- the system
working), sharpens the generalize gate to separate the failing thing (local) from
the reason it stayed hidden (global), and opens the target list, which read as a
closed enumeration and omitted aspect: entirely."
```

---

## Task 8: Regenerate the mirror, validate, close the loop

- [ ] **Step 1: Regenerate `codex-skills/`**

Three commands changed (`pre-register`, `plan-analysis`, `post-mortem`); the statistics leaf is not
mirrored.

```bash
cd science && uv run --frozen python ../scripts/generate_codex_skills.py
cd .. && git status --short codex-skills/
```
Expected: exactly the three `science-{pre-register,plan-analysis,post-mortem}/SKILL.md` files
change. If `science-big-picture` also appears, Task 0 was skipped — go back and do it.

- [ ] **Step 2: Full validation**

```bash
cd science && uv run --frozen pytest
cd science/model && uv run --frozen pytest
cd science && uv run --frozen science skills lint --root ../skills
cd science && uv run ruff check && uv run pyright
```
All must be green. `ruff`/`pyright` should be untouched by a prose-only change — run them anyway,
because Task 3 edits a file under `science/model/src/`.

- [ ] **Step 3: Close the eleven feedback items**

The terminal status is **`addressed`** — verified against `science feedback update --help`, whose
`--status` choices are `open|addressed|deferred|wontfix`. There is **no `resolved`**.
`--resolution` is required when setting a terminal status.

```bash
cd science
for id in 006 007 008 009 010 011 012 013 014 015 016; do
  uv run --frozen science feedback update "fb-2026-07-10-$id" \
    --status addressed \
    --resolution "Estimator doctrine: skills/statistics/estimator-certification.md + the Estimator Certification Gate in templates/pre-registration.md + hooks in plan-analysis, pre-register, post-mortem, and the computational-analysis aspect. Design: docs/plans/2026-07-11-estimator-doctrine-design.md"
done
uv run --frozen science feedback list --concern 'methodology:*'
```

Expected: none of `fb-2026-07-10-006…016` remain open.

Two entries **stay open on purpose** — do not sweep them:
- `fb-2026-07-11-005` (retired-hypothesis phase in `big-picture`) is `methodology:design` but
  belongs to the attention-ranking cluster; it is recorded as follow-on in the InstrumentResult
  design.
- `fb-2026-07-11-008`, `-020`, `fb-2026-07-08-001`, `fb-2026-07-07-003` are methodology-concern but
  unrelated to estimators.

Note the feedback store lives at `~/.config/science/feedback/` — it is **outside this repo**, so
these updates are not part of any commit here. Say so in the PR/summary; a reader will otherwise
look for them in the diff.

- [ ] **Step 4: Commit**

```bash
git add codex-skills/
git commit -m "chore(codex-skills): regenerate for the estimator-doctrine command edits"
```

---

## Self-review

**Spec coverage** — every design section maps to a task:

| Design | Task |
|---|---|
| §6.1 new leaf (+4-place registration, skills lint) | 1 |
| §6.2 correct `likelihood-model-comparison` | 2 |
| §6.3 gate section, **both** template copies, `ρ` default | 3 |
| §6.4 `pre-register` new sub-axis + 4b mirror | 4 |
| §6.5 `plan-analysis` rubric + body section + workflow | 1 (rubric), 5 |
| §6.6 aspect hook | 6 |
| §6.7 `post-mortem` ×3 | 7 |
| §12 codex-skills drift hazard | 0, 8 |
| §7.1 enforcement gap (follow-on, no code) | — deliberately not implemented |

**The user's five attention points:**

1. *Reproducibility vs reference accuracy* — Task 1, Axes 1 and 2, kept explicitly distinct: one
   perturbs inferentially irrelevant choices, the other compares against a **different
   error-generating mechanism**. The doctrine's headline is that either alone is worse than
   useless, and the asymmetry (reproducibility-alone is *adversarial*; accuracy-alone is merely
   *insufficient*) is stated, not blurred.
2. *How certification failure blocks pricing and commitment* — Task 3 (the gate's `Compute budget`
   row: `certified | CONDITIONAL on ...`) and Task 4 (the **certify → price → commit** ordering,
   with the CONDITIONAL escape and its invalidation clause).
3. *Template language that does not imply validator enforcement* — Task 3, Step 1's test asserts
   the literal string `"Nothing validates this section"` is present. The claim is pinned by a test,
   not by good intentions.
4. *"No independent reference exists"* — Task 1 answers it rather than deferring: MMS,
   order-of-accuracy verification, analytic limits, invariants, a gold-standard optimiser,
   autodiff-vs-FD, and free self-consistency assertions. **Uncertifiable ≠ unaffordable.**
5. *"within X%" project-defined unless evidence supports a default* — evidence supports the
   **dimensionless** criterion, and only that: **`E ≤ ρ·σ_null(T)`, default `ρ = 0.1`, never
   unstated.** The constant is deliberately **not** called `α` (that is the test size) and is
   deliberately **not** expressed as a percentage of the critical value — that percentage drifts
   with the degrees of freedom (3.7% → 2.9% across χ²₁…χ²₅ at 5%) and degenerates for non-`χ²`
   nulls, so shipping it as *the* default would bake a χ²₁-at-5% special case into a general
   doctrine. Any threshold-relative number is **derived for the declared null**.

**Both former open questions are now disposed** — not by prescribing a universal answer (there
isn't one) but by requiring a **declaration**, which is what a pre-registration is for:

- **Outer optimiser** (Task 1, *The outer optimiser must be justified against the profile's
  smoothness*; Task 3 template row): the author declares why it is valid for the profile's
  smoothness/discontinuity structure. **Gradient- and FD-based outer methods are prohibited unless
  smoothness is demonstrated** — and a fixed-multistart profile is discontinuous *by construction*,
  so for one the default position is prohibited.
- **Axis 3** (Task 1, *When simulating the null is unaffordable*; Task 3 template row): **EXECUTED
  or explicitly CONDITIONAL.** A `CONDITIONAL` must state cost, trigger, invalidation clause, and —
  the clause with teeth — **the decisions that may not depend on it until it completes.** Deferring
  Axis 3 does not add a caveat; it removes decisions from the table.

**Known gaps, stated rather than hidden:**

- Nothing here is validator-enforced. That is the design's §7.1, and it is deliberate.
- The `k` in `E = |b̂| + k·s` is given as a range (2–3) rather than a value. Unlike `ρ`, no
  derivation pins it; it is a tail-coverage choice. The author states it, as with `ρ`.

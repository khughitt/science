---
name: statistics-estimator-certification
description: Use when an analysis fits parameters numerically — an optimiser, a profile likelihood, nuisance parameters, an ODE or any other discretisation in the inferential path — and especially before a pre-registered threshold, compute budget, or gate is allowed to depend on the fit.
provenance: internal
---

# Estimator Certification

An estimator's self-report is not evidence about the estimator. "Converged" is a claim the
optimiser makes about itself, and a converged, multi-start optimum can be reproducibly,
repeatedly wrong. Certification is the discipline of establishing — *before* a threshold, a budget,
or a gate depends on it — that the number you are about to read is a function of the data rather
than of the run.

The failure this prevents is not a noisy answer. It is a **confident** one.

## The Four Axes, In Cost Order

Each is meaningless if the one above it is unsettled. Cheapest first, which is also
correctness-first — not a coincidence.

| Axis | Question | Cost |
|---|---|---|
| **0. Well-posedness** | Is the *problem* resolvable at all? | free (design-only, no data) |
| **1. Forward-map accuracy** | Does the code compute the model? | cheap |
| **2. Reproducibility** | Is the answer a function of the data, or of the run? | moderate |
| **3. Threshold calibration** | Does the decision rule have the null it claims? | expensive |

**Ordering rule: establish well-posedness → certify the estimator → price the design → commit the
budget.** A budget committed before certification is not a constraint on the analysis; it is a
consequence of an untested assumption, and it can be wrong by orders of magnitude. If you must
commit early, mark the budget **CONDITIONAL** and name what invalidates it.

## Axis 0: Is the Problem Resolvable?

Reproducibility and accuracy are properties of *an estimator applied to a problem*. Well-posedness
is a property of the **problem** — model × design × noise — and it dominates both.

If the likelihood has a flat ridge:

- the "true minimum" an accuracy check compares against **does not exist as a point** — two
  optimisers landing at different nuisance values with equal objective are *both right*;
- spread in the argmin is a **faithful report of genuine flatness**, not a defect;
- and the most dangerous available "fix" is an optimiser whose bias manufactures a unique apparent
  minimum.

**So skipping Axis 0 gives Axis 2 a perverse gradient: it will "fix" non-identifiability by
selecting a biased estimator.** That is why conditioning comes first.

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
> A doctrine that only ever discusses the spread of the *statistic* cannot tell these apart — and
> will "fix" the first by selecting a biased optimiser.

A taxonomy written *after* the failure will always find the category that closes the ticket.

## Axis 1: Does the Code Compute the Model?

An inaccurate forward map makes the objective **rough**, and a rough objective is what breaks
finite-difference gradients and inflates seed spread. **Certifying an optimiser on top of an
uncertified forward map is meaningless** — so this is upstream of Axis 2, not parallel to it.

### An independent reference means a different ERROR-GENERATING MECHANISM

Refining the step or tolerance of the **same scheme** is **not** an independent reference:

- **Same leading truncation term.** Error is `C(t,y)·h^p` with the same `C`. `u_h` and `u_{h/10}`
  have *correlated* error. Their agreement bounds nothing on its own.
- **Same stability boundary.** A stability failure (`|λh|` outside the stability region) is a
  *threshold*, not a smooth function of `h`. Richardson-type reasoning is valid only *inside* the
  asymptotic regime — and **you cannot establish that you are inside it by comparing two step
  sizes.**
- **Same bugs.** A wrong right-hand side, or a step heuristic that omits a term, is invisible to
  refinement. Refinement is blind to every error that is not a pure function of `h`.

> **Accuracy requires a reference with a different error-generating mechanism**: a different scheme
> *family* (implicit vs explicit, multistep vs Runge–Kutta), or an adaptive solver with error
> control at a tolerance 2–3 orders below the target.
>
> Step/tolerance refinement of the same scheme is a **convergence check, not a reference**, and it
> is informative only in its verified form — the **observed order of accuracy**
> `p̂ = log₂( ‖u_h − u_{h/2}‖ / ‖u_{h/2} − u_{h/4}‖ )`, checked against the theoretical `p`. If
> `p̂ ≠ p`, you are not in the asymptotic regime, or you have a bug. Agreement between `u_h` and
> `u_{h/10}` **without an order check is not evidence.**

**Two implementations of the same scheme is an invariance check, not an accuracy check.** They are
equivariant at any step size and will agree to machine precision while both are wrong.

### The assertion that needs no reference at all

> **Stability-region assertion.** Evaluate the Jacobian spectrum along the trajectory; assert
> `|λ_max · h|` stays inside the scheme's stability region **at every step**.

## Axis 2: Is the Answer a Function of the Data, or of the Run?

### Two replicates falsify. They do not certify.

Two replicates give one pairwise difference. For `X₁,X₂ ~ N(μ,σ²)`, `|X₁−X₂|` is half-normal: mean
≈ `1.13σ`, SD ≈ `0.85σ` — a **coefficient of variation of 0.76**. Meanwhile the decision-relevant
quantity is a **tail**, not a median.

> A large observed spread is **proof** of an unreliable estimator — a cheap check that can save
> weeks. A small spread from two draws is **not** proof of a reliable one.
>
> **Certification requires R ≥ 5 replicates, and R ≈ 20+ if the gate sits near its margin. Report
> the MAX over replicates and over analysis units — never the median.**

### Perturb every inferentially irrelevant degree of freedom

Not "the seed" — **every choice the science does not name**: the **start point** (jittered over the
plausible box), unit/block ordering, tie-breaking, BLAS thread count and reduction order, and any
RNG seed present.

> **If the estimator has no stochastic element, INJECT one.** A deterministic optimiser from a
> fixed start reproduces itself bit-for-bit: spread zero, gate passes, **check cannot fail**. That
> is not a certification — it is ceremony. See *Designing a Check That Can Fail*. A randomised
> multistart jitter is the minimum.
>
> An estimator that cannot be perturbed cannot be certified for reproducibility. It can only be
> certified for accuracy.

### The smoothing gradient — why reproducibility ALONE is adversarial

**Any operation that smooths the objective reduces spread while increasing bias.** A large
finite-difference step; a loose inner tolerance; coarse integration; heavy regularisation; early
stopping. Selecting an optimiser on low variance alone therefore selects **for** bias — actively,
not incidentally. The reproducible configuration can be reproducibly wrong, and pooled across units
it can be *worse* than the noisy one that actually finds the minima.

Accuracy alone, by contrast, is merely **insufficient** — there is no perverse gradient in "be
closer to the truth". It tells you the estimator *can* find the right answer, not that it *will* on
the run whose number you publish. **The two failures are not symmetric, and the asymmetry is the
point.**

**Also: per-unit convergence does not imply pooled convergence** when the likelihood sums many
independently-optimised blocks. One-sided per-unit errors **add rather than cancel**.

## Axis 3: Does the Decision Rule Have the Null It Claims?

Certifying the estimator certifies that you computed `T` correctly. It says **nothing** about
whether `Pr(T > c | H₀) = α`.

Where the nuisance dimension **grows with the sample** — per-unit nuisance parameters, i.e.
Neyman–Scott incidental-parameter territory — the profile MLE is **inconsistent**, the profile score
is **biased**, and the profile LR does **not** have a `χ²₁` null. A perfect optimiser on a perfect
integrator can still produce a badly miscalibrated test.

> **Verify the null distribution by simulation** (parametric bootstrap under the restricted model).
> Do not assume Wilks. Where nuisance dimension grows with `n`, prefer a modified/adjusted profile
> likelihood (Cox–Reid conditional profile; Barndorff-Nielsen `p*`; Severini), or a
> hierarchical/random-effects treatment — and check the empirical LR distribution against `χ²₁`
> **before** any threshold is pre-registered.

Note the trap: the error budget below is scaled by `σ_null(T)`. **If Axis 3 was skipped, that scale
is itself unverified** — you are calibrating your instrument against a ruler you have not checked.

### When simulating the null is unaffordable

It often is. This axis is **not** unconditionally required — but it may not be *silently* skipped.
It must be **either EXECUTED or explicitly CONDITIONAL**, and a `CONDITIONAL` carries four
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

`nll_prof(ψ) = min over nuisance η`. **Warm-starting the inner fit from the previous grid point's
solution makes the computed value depend on the path taken through the grid — so the "objective" is
not a function of ψ at all.** A tell-tale: an outer optimiser terminating *above* a value it has
already evaluated. That is impossible for a genuine function.

But **functionhood is necessary, not sufficient — and it is not the property that matters.** The
profile enters inference only through **differences**, `Δnll = nll_prof(ψ) − nll_prof(ψ̂)`.

> The requirement is that inner-solve error be **(a) deterministic in ψ**, **(b) bounded well below
> the Δnll the inference resolves**, and **(c) approximately UNIFORM in ψ** — because a
> ψ-independent bias **cancels in the difference** and a ψ-dependent one **does not**.

| Protocol | (a) deterministic | (b) boundable | (c) uniform in ψ | Cost |
|---|---|---|---|---|
| Warm-starting | ✗ | ✗ | ✗ | cheap |
| Fixed continuation path | ✓ | partly | **✗ by construction** | **expensive** |
| **Fixed multistart pool** | ✓ | ✓ (raise `k`) | plausibly | moderate |

**Prefer a fixed multistart pool.** A fixed continuation path *does* restore functionhood — the path
does not depend on evaluation history — but it re-runs the entire path at every outer evaluation
(`O(m)` inner solves per call), and it carries the solution along whatever basin the path lands in,
so at a basin boundary it sits on the wrong branch. **Fixing the path converts a path-dependence bug
into a reproducible bias** — which, per the smoothing gradient above, is the most dangerous state an
estimator can be in.

### The outer optimiser must be justified against the profile's smoothness

A fixed-multistart profile is a **discontinuous** function of ψ — the winning start switches basins.
Functionhood is restored; **smoothness is not.** A gradient step on a surface with basin-switch
cliffs will happily report convergence at a cliff edge. That is the same failure as warm-starting,
one level up.

There is no universally correct outer optimiser, so this skill does not name one. It requires a
declaration:

> **Declare why the outer optimiser is valid for this profile's smoothness / discontinuity
> structure.**
>
> **Gradient-based and finite-difference-based outer methods are PROHIBITED unless smoothness is
> demonstrated** — demonstrated, not assumed and not asserted. A fixed-multistart profile is
> discontinuous *by construction*, so for one the default position is **prohibited**.
>
> Absent a smoothness demonstration: use a derivative-free outer method, or a dense grid with local
> refinement.

### The inner tolerance is derivable

Inner-solve error in `nll` is **one-sided** (a returned minimum is always ≥ the true minimum), and
with `n` independently-optimised blocks the per-block errors **sum**. To resolve a pooled `Δnll` of
`δ`, per-block inner accuracy must be `≲ δ/n`:

- `δ = 1.92`, 17 blocks → **≤ 0.11 nll/block**
- `δ = 1.92`, 136 blocks → **≤ 0.014 nll/block**

### Certify the DIFFERENCE, not the pieces

In a likelihood ratio `LR = 2(nll_restricted − nll_unrestricted)`, **both** terms carry one-sided
upward optimiser error. Those errors cancel **only if both models are optimised to equal accuracy** —
and the larger model is systematically the harder one, hence systematically the *less* well
optimised.

> **Optimiser error in an LR is not mean-zero and not conservative. Its sign is set by which model is
> harder to fit.** Match the inner tolerance **between the compared models**, and run certification
> on the **difference statistic**. Certifying `nll` to a tolerance says nothing about `Δnll`.

## One Error Budget, Three Outcomes

Two independent gates with two independent tolerances can **both pass while the decision flips**: a
bias and a spread that each clear a generous gate can, together, carry the statistic across its
threshold. So combine them into one budget:

> **E := |b̂| + k·s**, with `k ≈ 2–3` (so the reproducibility term is an upper-tail bound, not a
> median), where `b̂` is measured bias against the independent reference and `s` the replicate spread.
>
> **Certification passes iff `E ≤ ρ · σ_null(T)`, with `ρ = 0.1` by default.**

### ρ, the instrument-error fraction — and why it is not called α

`ρ` is **dimensionless** and is measured against `σ_null(T)`, the sampling SD of the decision
statistic under its **declared null**.

> **Never call this `α`.** In likelihood testing `α` is the **test size** — the thing in
> `Pr(T > c | H₀) = α`. A constant named `α` sitting beside a likelihood-ratio threshold will be read
> as a significance level. It is not one. It is the fraction of the statistic's own null variability
> that the *instrument* is permitted to contribute.

**Do not state the bound as a percentage of the critical value.** That percentage is a property of
one particular null, not a rule — it drifts with the degrees of freedom, and it degenerates entirely
for non-`χ²` nulls and as `c → 0`. At a 5% test size:

| Null | `σ_null = √(2·df)` | `c` | `ρ·σ_null` at ρ=0.1 | …as % of `c` |
|---|---|---|---|---|
| χ²₁ | 1.414 | 3.841 | 0.141 | **3.7%** |
| χ²₂ | 2.000 | 5.991 | 0.200 | **3.3%** |
| χ²₃ | 2.449 | 7.815 | 0.245 | **3.1%** |
| χ²₅ | 3.162 | 11.070 | 0.316 | **2.9%** |

If you want a threshold-relative number, **derive it for your declared null.** Do not carry one over.

> **Default `ρ = 0.1`** — the instrument then inflates `Var(T)` by ~1%, immaterial under any usual
> convention. Override it if you can justify it, but **`ρ` is never allowed to go unstated.**

### The third outcome

A global green light does **not** license every individual verdict. Even a certified estimator has
residual error `E > 0`, and any unit whose statistic sits within `E` of `c` is **unresolvable by that
instrument**.

> **Three outcomes, not two.** Per reported unit: **reject** if `T̂ − c > E`; **do-not-reject** if
> `c − T̂ > E`; otherwise **INDETERMINATE — the instrument cannot resolve this unit.**
>
> An honest estimator with known error yields three outcomes. Reporting two is how a
> flipped-by-noise unit gets published as a clean decision.

## Designing a Check That Can Fail

Before a check may discharge an obligation, answer: **what result would have made this check fail?**
If no achievable result would, the check is not merely ceremony — it is *evidence-shaped* ceremony,
which is how it discharged the obligation in the first place.

Apply this to your own gates. A reproducibility check on a deterministic optimiser cannot fail. An
invariance check between two implementations of one scheme cannot detect inaccuracy.

Three specific traps:

- **A threshold on a surface must pre-specify the domain of its max**, up front, alongside the value.
  Narrowing the domain *after* seeing the number is the renegotiation pre-registration exists to
  prevent.

  But the naive fix is **circular**: the region "the analysis actually consults" is *estimated* —
  defined by where the optimiser believes the minimum is — so a fidelity check evaluated only there
  **cannot detect a true minimum lying elsewhere**. Pre-specify the domain as a **rule**, not a
  region, **and** verify the region is **closed under descent**: no point outside it has a lower
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

- **Method of Manufactured Solutions.** Choose an analytic `u*(t)`, substitute into the ODE to derive
  the source `s(t) = du*/dt − f(u*)`, integrate the *modified* system, compare to `u*` exactly. Works
  for arbitrary nonlinear right-hand sides. This is **the** canonical answer to "no analytic solution
  exists."
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
  evolution, basin-hopping) run to a large budget on a *certification subsample*. **The reference for
  an optimiser is a more expensive optimiser.** This always exists; it is only ever expensive.
- **Exact gradients (autodiff/adjoint) vs production FD gradients** — cheap, always available, and a
  direct detector of a bias-inducing FD step.
- Free self-consistency assertions (the table above).

> **An estimator is essentially never uncertifiable. It may be unaffordably certifiable — which is a
> budget statement, not an epistemic one.**

## Common Failure Modes

- **Converged, multi-start, and reproducibly wrong.** The optimiser's self-report is not evidence.
- **The reproducible config is the biased one.** Low spread bought by smoothing the objective.
- **The interesting artifact.** A confounded probe produces a substantive-looking finding that
  vanishes when the probe is fixed.
- **The budget priced on an assumed estimator.** A protocol rejected by its own fidelity test can be
  off by orders of magnitude. Price the protocol that *survives* certification.
- **Per-unit convergence read as pooled convergence.** One-sided errors add.
- **A gradient outer optimiser on a discontinuous profile.** Warm-starting's failure, one level up.
- **A gate that cannot fail**, discharging an obligation it never tested.

## Halt-On Conditions

- The objective is not a function of its own arguments (warm-started inner fits). **Stop.** Nothing
  downstream is interpretable.
- The error budget exceeds its bound (`E > ρ·σ_null`). The threshold is finer than the instrument's
  resolution. **Do not report reject/do-not-reject** — report INDETERMINATE, and either certify a
  better estimator or widen the threshold.
- Structural non-identifiability. No estimator fixes this; change the design.

## Reporting

State: the four axes and how each was established; the independent reference and **why its error
mechanism differs** from the production one; `R`, and the **max** (not median) spread over replicates
and units; `b̂`, `s`, `k`, `ρ`, and the resulting `E`; the outer optimiser and **why it is valid for
the profile's smoothness structure**; whether Axis 3 was **EXECUTED or CONDITIONAL** (and if
CONDITIONAL, the decisions it removes from the table); the number of units falling in the
**INDETERMINATE** band; and the **invalidation clause** — re-certify whenever the estimator, forward
model, tolerances, hardware, or library stack changes. Where certification ran at reduced scale,
state the **scaling law** carrying it to full scale (per-unit does not carry to pooled).

## Companion Skills

- [`likelihood-model-comparison.md`](./likelihood-model-comparison.md) — AIC/BIC/LRT once the
  estimator is certified; its numerical-precision audit assumes what this leaf establishes.
- [`population-genetics-likelihood.md`](./population-genetics-likelihood.md) — nuisance parameters
  must be estimated jointly, profiled, or pre-registered as such.
- [`sensitivity-arbitration.md`](./sensitivity-arbitration.md) — pre-commit which comparison is
  verdict-bearing before the arms disagree.
- [`bias-vs-variance-decomposition.md`](./bias-vs-variance-decomposition.md) — the trade this leaf's
  smoothing gradient exploits.
- [`prereg-defensive-instrumentation.md`](./prereg-defensive-instrumentation.md) — gates that consume
  design geometry and synthetic data only, before any observed value is read.

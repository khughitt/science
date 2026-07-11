# Estimator Doctrine — design

**Status:** Proposed. Not implemented. **Revised** after adversarial statistical review (§9).
**Scope:** 11 open feedback items, `fb-2026-07-10-006` … `fb-2026-07-10-016`.
**Source project:** `evolution` (all 11), all tracing to one artifact:
pre-registration `0004-pre-registration-t078-kill-vs-psa-downregulation.md`, task t078.

> **Provenance note, stated up front.** The `evolution` project is not checked out on this
> machine. Every number, threshold, and failure attributed to t078 below is quoted from the
> feedback entries themselves (`~/.config/science/feedback/fb-2026-07-10-0**.yaml`), not
> re-derived from the project. Claims *about t078* are therefore only as good as that record.
> Claims about **what the doctrine should say** are argued on their own merits and are the
> reader's to check.

---

## 1. The finding

Eleven feedback items were filed from one episode. They are not eleven complaints. They are
one failure, observed eleven times, and the reporter of `fb-2026-07-10-016` had already worked
out why they looked like eleven:

> The most transferable lessons from this incident were not about the failing component but
> about **why it stayed invisible**: an invariance check that could not detect inaccuracy, a
> fidelity threshold with an unspecified domain, an optimiser-selection criterion that
> rewarded bias, and a probe confounded with the parameter it validated. The mechanism (a
> 136-nuisance-parameter profile) was entirely project-local and would have generalised to
> nothing.

That is the organising principle of this document:

> **The failing thing is usually local. The reason it stayed hidden is usually global.
> File on the latter.**

The local thing was a 136-nuisance-parameter profile likelihood over a cohort of PSA
trajectories. Nobody else will ever have that. What everybody has is the *shape* of how it hid.

### 1.1 The root cause

**The estimator was assumed rather than certified, and every artifact downstream inherited the
assumption.**

t078 pre-registered a decision rule — ΔNLL thresholds of 1.92 and 3.00 — and named an
optimiser. It never asked whether that optimiser could **resolve** those thresholds. It could
not: refitting *identical synthetic data* under two independent Sobol scramble seeds moved the
load-bearing statistic `LR_out` by a median of 2.40 and a max of 6.58 — **1.71× its own 3.84
critical value** — flipping the reject/do-not-reject decision in **3 of 15 cohorts**
(`fb-2026-07-10-007`).

Say precisely what went wrong here, because the obvious phrasing is wrong and the wrong
phrasing produces a wrong doctrine:

- **Not** "the threshold was too tight." A threshold is a claim about the world.
- **Not** "the threshold was unfalsifiable." Falsifiability is a property of a *hypothesis*;
  1.92 is perfectly falsifiable.
- **It is that the measurement error exceeded the effect being measured.** The threshold was
  finer than the instrument's **resolution**. The reported statistic was substantially a
  function of the seed rather than of the data.

And the error is not symmetric noise that averages out. Optimiser error in a likelihood *ratio*
is a difference of two **one-sided** biases (§2.4), so an unresolved decision is not merely
blurred — it is **tilted**, in a direction set by which model is harder to fit.

> **A threshold finer than its instrument's resolution is not conservative. It is noise-driven,
> and the noise has a sign.**

### 1.2 What this document does NOT claim about t078

It does not claim the 1.92 / 3.00 thresholds were *correctly calibrated*. **Nobody checked** —
and with 136 nuisance parameters over ~17 patients, that is a live question, not a formality
(§2.3). t078 has (at least) two independent defects: an instrument that could not resolve its
threshold, and a threshold whose null distribution was never verified. This document is
mostly about the first, but it must force the second to be **asked**, because certifying an
estimator certifies that you computed `T` correctly — it says **nothing** about whether
`Pr(T > 3.84 | H₀) = 0.05`.

### 1.3 The shape of how it hid

Four items describe checks that **ran, passed, and could not have failed for the reason they
were invoked**:

| Item | The check | Why it could not fail |
|---|---|---|
| `fb-...-008` | Integrator validated by comparing two implementations | Both implement the **same** fixed-step RK4 scheme, which are equivariant at any step size. They agreed to `6e-15` **while both were wrong** — against LSODA at `rtol 1e-11`, median error `1.2e-9` but **p99 0.70, max 72.0 log units**, exceeding RK4's `|λh| < 2.78` stability limit because the step heuristic omitted the density-dependent rates. |
| `fb-...-010` | "max surface deviation ≤ 0.1 nll" | The **domain of the max was never named**. Over the whole `(d, φ)` box the max landed in cells 400+ nll above the minimum that no inference reads. Restricted to the region the analysis consults, the same runs gave 0.11–0.75. |
| `fb-...-011` | Null-calibration probe | The probe **gridded `log10 d` — the parameter whose true values varied across its own cells** — while the unrestricted model had a free `φ` axis to absorb the discretisation error. `LR_out` partly measured each `d_true`'s distance to the nearest grid node. |
| `fb-...-009` | Optimiser chosen by seed-to-seed reproducibility | Reproducibility **alone** selects for bias. The winner had seed spread 0.0008 — 3 orders better than default — and was *reproducibly wrong*, missing the true minimum by 0.21 SSR/patient because a large finite-difference step smooths narrow basins away. |

Every one is the same defect: **a measurement that did not happen, reported as a clean result.**

That sentence is verbatim the ruling this toolkit shipped for *code* instruments — the
`InstrumentResult` convergence
([`2026-07-11-instrument-result-convergence-design.md`](2026-07-11-instrument-result-convergence-design.md)) —
where a query that could not run returned `[]` and the CLI printed "no findings." This document
is the same ruling for *methodological* instruments. There a helper that never looked returned
`[]`; here a check that could not fail returned PASS.

---

## 2. The doctrine

The eleven items resolve into **four axes and one rule**. The axes are ordered **by cost, cheapest
first** — which is also, not by coincidence, the order in which they must be established, because
each one is meaningless if the one above it has not been settled.

> **Axis 0 — Well-posedness.** Is the *problem* resolvable at all?
> **Axis 1 — Forward-map accuracy.** Does the code compute the model?
> **Axis 2 — Estimator reproducibility.** Is the answer a function of the data, or of the run?
> **Axis 3 — Threshold calibration.** Does the decision rule have the null it claims?
>
> **The rule — a check must be able to fail for the reason you invoked it.**

Axes 0–3 are *what to certify*. The rule is *how to know a certification is real*. The rule
applies to the axes themselves: §2.2 exists because an earlier draft of this document proposed
a reproducibility check that **could not fail** for a deterministic optimiser.

### 2.0 Axis 0 — Well-posedness (design-only; free)

Reproducibility and accuracy are properties of *an estimator applied to a problem*.
Well-posedness is a property of the **problem** — model × design × noise — and it dominates both.
It is also the cheapest thing to check, because it needs **no data at all**.

If the likelihood has a flat ridge, then: the "true minimum" the accuracy check compares against
**does not exist as a point** (two optimisers landing at different `η` with equal `nll` are
*both right*); seed spread in `η̂` is a **faithful report of genuine flatness**, not a defect;
and the most dangerous available "fix" is an optimiser whose bias manufactures a unique apparent
minimum — **which is exactly what `fb-...-009`'s large FD step does.** Smoothing narrow basins
away is a way of making a badly-conditioned problem *look* reproducible.

**So a doctrine that certifies estimators without first certifying conditioning has a live
incentive to select the bias.** Axis 0 is not optional preamble; it is what stops Axis 2 from
being adversarial.

Check, before any data: structural identifiability (rank of the sensitivity matrix); practical
identifiability (are the profile-likelihood CIs **closed**?); the Hessian/FIM condition number
and eigenspectrum at the optimum; sloppy-direction analysis.

**And ship the discriminant** — `fb-...-013` pre-committed a decision tree separating "optimiser
failure" from "practical non-identifiability", §4.8 calls that the load-bearing half, and an
earlier draft of this document then failed to say **how to tell them apart**:

> **Compare the spread of the ARGMIN against the spread of the OBJECTIVE.**
> `η̂` varies across replicates but `nll_prof(ψ)` is stable → **flat ridge; non-identifiability.**
> The estimator is fine and the parameter is not estimable.
> `nll` itself varies across replicates → **optimiser failure.**
>
> A doctrine that only ever discusses the spread of the *statistic* cannot tell these apart —
> and will "fix" the first by selecting a biased optimiser.

### 2.1 Axis 1 — Forward-map accuracy (cheap; and it is UPSTREAM of everything)

An inaccurate forward map makes the objective **rough**, and a rough objective is what breaks
finite-difference gradients and inflates seed spread. This is almost certainly the causal chain
from `fb-...-008` to `fb-...-009`: a max error of **72 log units** puts cliffs in the likelihood,
which is precisely why a large FD step "improved" reproducibility — by smoothing the cliffs away.

**Certifying an optimiser on top of an uncertified forward map is meaningless.**

#### An independent reference means a different ERROR-GENERATING MECHANISM

This is the doctrine's sharpest rule and the easiest to get wrong. *(An earlier draft of this
document got it wrong — see §9.)*

Refining the step or tolerance of the **same scheme** is **not** an independent reference:

- **Same leading truncation term.** Error is `C(t,y)·hᵖ` with the same `C`. `u_h` and `u_{h/10}`
  have *correlated*, not independent, error. Their agreement bounds nothing on its own.
- **Same stability boundary.** `fb-...-008`'s failure was a **stability** failure (`|λh| > 2.78`)
  — a *threshold*, not a smooth function of `h`. In the unstable regime an `h` vs `h/10`
  difference is not an error estimate at all. Richardson-type reasoning is valid only *inside*
  the asymptotic regime, and **you cannot establish that you are inside it by comparing two step
  sizes.**
- **Same bugs.** `fb-...-008`'s actual root cause was *"the step heuristic omitted the
  density-dependent rates."* Refinement is blind to every error that is not a pure function of `h`.

Note that `fb-...-008`'s real reference was **LSODA at `rtol 1e-11`** — a different scheme **and**
a tighter tolerance. A doctrine that turns that "and" into an "or" licenses a check that shares
the discretisation with the thing it validates, in a document whose thesis is *don't do that*.

> **Accuracy requires a reference with a different error-generating mechanism**: a different
> scheme *family* (implicit vs explicit, multistep vs Runge–Kutta), or an adaptive solver with
> error control at a tolerance 2–3 orders below the target.
>
> Step/tolerance refinement of the same scheme is a **convergence check, not a reference**, and
> it is informative only in its verified form — the **observed order of accuracy**
> `p̂ = log₂( ‖u_h − u_{h/2}‖ / ‖u_{h/2} − u_{h/4}‖ )`, checked against the theoretical `p`. If
> `p̂ ≠ p`, you are not in the asymptotic regime, or you have a bug. Agreement between `u_h` and
> `u_{h/10}` **without an order check is not evidence.**

Plus one assertion that needs **no reference at all** and would have caught `fb-...-008` outright:

> **Stability-region assertion.** Evaluate the Jacobian spectrum along the trajectory; assert
> `|λ_max · h|` stays inside the scheme's stability region **at every step**.

### 2.2 Axis 2 — Estimator reproducibility (and why "two seeds" is not it)

`fb-...-007` proposes: *every reported statistic must be reproduced by two independent optimiser
seeds on the same data.* As a **screen** this is exactly right, and the item claims no more for
itself — *"a two-minute check that would have preceded, and obviated, weeks of downstream
certification work."* As a **certification criterion** it fails three ways:

**(a) Two seeds can FAIL an estimator; two seeds cannot PASS one.** Two seeds give one pairwise
difference. For `X₁,X₂ ~ N(μ,σ²)`, `|X₁−X₂|` is half-normal with scale `σ√2`: mean ≈ `1.13σ`,
SD ≈ `0.85σ` — a **coefficient of variation of 0.76**. Meanwhile the decision-relevant quantity
is a **tail**: `fb-...-007`'s own numbers are *median 2.40, max 6.58*, a 2.7× median-to-max ratio.
A criterion built on `n=2` estimates something median-ish and is used to bound something max-ish.

> A large observed spread is **proof** of an unreliable estimator. A small one, from two draws, is
> **not** proof of a reliable one. Passing requires **R ≥ 5** replicates, and **R ≈ 20+** if the
> gate sits near its margin. Report the **max over replicates and over analysis units** — never
> the median.

**(b) It is PASS-by-construction for a deterministic optimiser.** A deterministic L-BFGS-B from a
fixed `x₀` reproduces itself bit-for-bit. Spread = 0. Gate passes. **By this document's own rule
(§2.4), that check cannot fail — so it is not a check.** This is the modal case in practice
(`scipy.optimize.minimize`, fixed start) and would have been the modal way this gate got
discharged fraudulently.

> **Perturb every inferentially irrelevant degree of freedom** — every choice the science does not
> name: **start point** (jittered over the plausible box), unit/block ordering, tie-breaking, BLAS
> thread count and reduction order, and any RNG seed present.
>
> **If the estimator has no stochastic element, inject one.** A randomised multistart jitter is
> the minimum. An estimator that *cannot be perturbed* cannot be certified for reproducibility —
> only for accuracy.

Note what `fb-...-007` actually varied: **Sobol scramble seeds** — the *start-set sampling* seed.
It varied the **initialisation**, which is the right thing to vary. "Optimiser seed" is a lossy
paraphrase that invites authors to vary something less informative.

**(c) Certify the DIFFERENCE, not the pieces.** See §2.4.

### 2.3 Axis 3 — Threshold calibration (expensive; often skipped; sometimes decisive)

Certifying the estimator certifies that you computed `T` correctly. It says **nothing** about
whether `Pr(T > c | H₀) = α`.

Where the nuisance dimension **grows with the sample** — 136 nuisance parameters over ~17 patients
is per-unit nuisance parameters, i.e. textbook Neyman–Scott incidental-parameter territory — the
profile MLE is **inconsistent**, the profile score is **biased**, and the profile LR does **not**
have a `χ²₁` null. A *perfect* optimiser on a *perfect* integrator can still produce a badly
miscalibrated test.

> **Verify the null distribution by simulation** (parametric bootstrap under the restricted model);
> do not assume Wilks. Where nuisance dimension grows with `n`, prefer a modified/adjusted profile
> likelihood (Cox–Reid conditional profile; Barndorff-Nielsen `p*`; Severini) or a
> hierarchical/random-effects treatment — and check the empirical LR distribution against `χ²₁`
> **before** any threshold is pre-registered.

The irony deserves a line, because it is instructive: **§2.2's reproducibility criterion uses the
critical value as its denominator, and that denominator is itself unverified.**

`fb-...-011`'s probe **was** a null-calibration exercise. An earlier draft of this document
extracted only its negative lesson (the probe was confounded) and never lifted the *positive*
practice — **calibrate the null by simulation** — into the doctrine. Both belong.

### 2.4 The rule — a check must be able to fail for the reason you invoked it

Before a check may discharge an obligation, its author must answer: **what result would have made
this check fail?** If no achievable result would, the check is not merely ceremony — it is
*evidence-shaped* ceremony, which is how it discharged the obligation.

Three rules earned by items, each now stated in its corrected form:

- **Invariance ≠ accuracy** (`fb-...-008`). Reproducing a result two ways that share the
  discretisation validates the *implementation*, not the *method*. See §2.1 for what a real
  reference is.
- **A threshold on a surface must pre-specify the domain of its max** (`fb-...-010`) — up front,
  alongside the value. Narrowing the domain *after* seeing the number is the renegotiation
  pre-registration exists to prevent.

  **But the naive fix is circular, and this document nearly shipped it.** The region "the analysis
  actually consults" (the MLE, the `Δnll ≤ 3` contour, the restricted-model minima) is
  **data-dependent and estimated** — defined by where the optimiser *believes* the minimum is. A
  fidelity check evaluated only where you already think the answer is **cannot detect a true
  minimum lying elsewhere.** So:

  > Pre-specify the domain as a **rule**, not a region (e.g. "the `Δnll ≤ Δ_max` contour under the
  > reference protocol, plus a stated margin"). **And** verify the region is **closed under
  > descent**: no point outside it has a lower `nll` than the minimum inside it. Without that
  > second clause, narrowing the domain is not the cure for `fb-...-010` — it is another way to
  > get the same unfalsifiable pass.

- **A probe must not discretise a parameter whose true values vary across its own cells**
  (`fb-...-011`). Put the simulated truths **on** the nodes, or remove the grid. And before
  interpreting any probe outcome, **check for correlation between the outcome and
  distance-to-node.**

  The cautionary detail: the confounded probe produced `φ̂ = 0.56` under a `φ_true = 1` null,
  which *reads as a substantive identifiability finding*. Re-run with continuous `d`, `d̂` tracked
  `d_true` (0.0121/0.0313/0.1035 vs 0.01/0.03/0.10) and **the effect vanished entirely.**
  **A broken probe does not announce itself by returning nothing. It returns something worth
  writing up.**

### 2.5 The joint criterion — and the asymmetry in it

**Reproducibility and accuracy must be certified jointly.** But the two halves fail differently,
and collapsing them loses the point:

- **Reproducibility alone is *adversarial*.** It has a perverse selection gradient. The general
  class — and it must be stated as a class, or it will be read as "watch your FD step" — is:
  **any operation that smooths the objective reduces seed spread while increasing bias.** A large
  FD step (`fb-...-009`), a loose inner tolerance, coarse integration, heavy regularisation, early
  stopping. `fb-...-009`'s winner had 3-orders-better spread and was reproducibly wrong; **pooled
  over 17 patients it was 2.6× WORSE** (nll seed spread 1.61 vs 0.63), because one-sided per-unit
  errors **add rather than cancel**.
- **Accuracy alone is merely *insufficient*.** There is no perverse gradient in "be closer to the
  truth". It tells you the estimator *can* find the right answer, not that it *will* on the run
  whose number you publish.

#### One error budget, and a third decision outcome

Two independent gates with two independent tolerances can **both pass while the decision still
flips**: a bias and a spread that each clear a generous gate can, together, move the statistic
across its threshold. Certification must therefore combine them into **one** budget:

> **E := |b̂| + k·s** (k ≈ 2–3, so the reproducibility term is an upper-tail bound, not a median),
> where `b̂` is measured bias against the independent reference and `s` the replicate spread.
>
> **Certification passes iff `E ≤ ρ · σ_null(T)`, with `ρ = 0.1` by default.**

**`ρ` — the instrument-error fraction — is dimensionless, and it is measured against the sampling
SD of the decision statistic under its declared null.** Not against the critical value. Two
reasons, and the naming one is not cosmetic:

- **Never call this `α`.** In likelihood testing `α` is the **test size**, and this document itself
  uses it that way in §2.3 (`Pr(T > c | H₀) = α`). A constant named `α` sitting next to a
  likelihood-ratio threshold *will* be read as a significance level. It is not one.
- **A percentage of the critical value does not generalise.** It is a property of the *declared
  null*, not a universal constant. For a 5%-size LR test:

  | Null | `σ_null = √(2·df)` | `c` (5%) | `ρ·σ_null` at ρ=0.1 | …as % of `c` |
  |---|---|---|---|---|
  | χ²₁ | 1.414 | 3.841 | 0.141 | **3.7%** |
  | χ²₂ | 2.000 | 5.991 | 0.200 | **3.3%** |
  | χ²₃ | 2.449 | 7.815 | 0.245 | **3.1%** |
  | χ²₅ | 3.162 | 11.070 | 0.316 | **2.9%** |

  The percentage **drifts with the degrees of freedom**, and it degenerates entirely for statistics
  whose null is not `χ²`, or where `c → 0`. So the rule is stated in `σ_null`, and any
  threshold-relative percentage is **derived for the declared null** — never carried over from
  someone else's.

The `ρ = 0.1` default is what makes the instrument an immaterial contributor to the variance of the
quantity being decided.

And a global green light does **not** license every individual verdict. Even a certified estimator
has residual error `E > 0`; any unit whose statistic sits within `E` of `c` is **unresolvable by
that instrument** — which is precisely t078's 3-of-15 flipping cohorts. So:

> **Three outcomes, not two.** For each reported unit: **reject** if `T̂ − c > E`;
> **do-not-reject** if `c − T̂ > E`; otherwise **INDETERMINATE — the instrument cannot resolve
> this unit.**
>
> An honest estimator with known error yields three outcomes. This is the operational payload of
> the entire doctrine.

### 2.6 Profiling: warm-starting, and what the real requirement is

Profiling defines `nll_prof(ψ) = min over nuisance η`. Warm-starting the inner fit from the
previous grid point's solution makes the computed value depend on **the path taken through the
grid** — so the "objective" is **not a function of ψ at all** (`fb-...-006`). Observed: Nelder–Mead
optimising a moving target for 451 evaluations and 236 s, **terminating ABOVE the coarse-grid
minimum it started from** — impossible for a genuine function, and therefore a *diagnostic*.

But **functionhood is necessary, not sufficient — and it is not the property that matters.** The
profile enters inference only through **differences**: `Δnll = nll_prof(ψ) − nll_prof(ψ̂)`.
Therefore:

> The requirement is not that inner-solve error be zero, nor merely that the objective be a
> function of ψ. It is that the inner-solve error be **(a) deterministic in ψ**, **(b) bounded
> well below the Δnll the inference resolves**, and **(c) approximately UNIFORM in ψ** — because a
> ψ-independent bias **cancels in the difference** and a ψ-dependent one **does not**.

Against that bar:

| Protocol | (a) deterministic | (b) boundable | (c) uniform in ψ | Cost |
|---|---|---|---|---|
| **Warm-starting** | ✗ | ✗ | ✗ | cheap |
| **Fixed continuation path** | ✓ | partly | **✗ by construction** | **expensive** |
| **Fixed multistart pool** | ✓ | ✓ (raise `k`) | plausibly | moderate |

A **fixed continuation path recomputed identically at every evaluation** *does* restore
functionhood — the path does not depend on evaluation history, so `nll_prof` is a well-defined
deterministic function of ψ. But it is **not the cheap fix an earlier draft called it**:

1. **It is the most expensive of the three.** "Recomputed identically at every evaluation" means
   every outer evaluation re-runs the *entire* path — `O(m)` inner solves per outer call instead
   of 1. In a document whose §2.7 is about a 700× budget miss, proposing the budget-blowing
   protocol as the cheap remedy is its own joke.
2. **It produces a reproducible bias.** Continuation carries the solution along whatever basin
   the path lands in; at a basin boundary the continued profile sits on the wrong branch,
   discontinuously. Fixing the path makes that bias **deterministic and reproducible** — by
   `fb-...-009`'s own lesson, the most dangerous state an estimator can be in. **Continuation
   converts a path-dependence bug into a reproducible bias.**
3. Its error is systematically smaller near the path's origin and grows as you leave it — it
   **fails (c) by construction.**

> **Prefer a fixed multistart pool.** It restores functionhood, its error is boundable by raising
> `k`, and it is the only option that plausibly attacks uniformity.

One caveat the multistart recommendation must carry: a fixed-pool profile is a **discontinuous**
function of ψ (the winning start switches basins). Functionhood is restored; **smoothness is not**.
Running a gradient/FD-based *outer* optimiser over a piecewise surface is a second-order version
of the same bug — so the leaf must say which outer methods are admissible.

#### The inner tolerance is derivable — so derive it

Inner-solve error in `nll` is **one-sided** (a returned minimum is always ≥ the true minimum), and
with `n` independently-optimised blocks the per-block errors **sum**. To resolve `Δnll = 1.92`
pooled, per-block inner accuracy must be `≲ 1.92/n`:

- 17 blocks → **≤ 0.11 nll/block**
- 136 blocks → **≤ 0.014 nll/block**

A concrete, principled number, derivable entirely from what the doctrine already asserts.

**And the dangerous version.** In a likelihood *ratio*, `LR = 2(nll_restricted − nll_unrestricted)`,
**both** terms carry one-sided upward optimiser error. Those errors cancel **only if both models
are optimised to equal accuracy** — and the larger model is systematically the harder one, hence
systematically the *less* well optimised.

> **Optimiser error in an LR is not mean-zero and not conservative. Its sign is set by which model
> is harder to fit.** The inner tolerance must be **matched between the compared models**, and
> certification must be run on the **difference statistic**, not on each `nll` separately.
> Certifying `nll` to a tolerance says nothing about `Δnll`.

### 2.7 Certify → price → commit

t078 budgeted **200 CPU-hours** for its primary profile — a price quoted for a warm-started
protocol later **rejected by the pre-registration's own fidelity test**. With the cheapest protocol
that survives certification, the same design costs **~4,900 CPU-hours** for the recovery gates and
**~140,000** for the nested bootstrap (`fb-...-012`) — a factor of ~700.

The budget was never a constraint on the analysis. It was a **consequence of an untested assumption
about the optimiser.**

> **Ordering: establish well-posedness → certify the estimator → price the design → commit the
> budget.** If a budget must be committed before certification, state it as **CONDITIONAL** and
> name what invalidates it.

**Certification itself needs an invalidation clause**, which an earlier draft gave the budget and
not the certificate: re-certify whenever the estimator, forward model, tolerances, hardware, or
library stack changes. And where certification is run at reduced scale on a subsample — as it must
be, for a 140,000-CPU-hour design — **the scaling law carrying it to full scale must be stated**,
non-trivially, because per-unit does not carry to pooled (§2.6).

---

## 3. "No independent reference exists" is almost always false

An earlier draft left this an open question and speculated that such an analysis "may be
uncertifiable." **That is wrong, and defeatist.** A reference essentially always exists for the two
things certification is about. What may not exist is a reference for whether the *model is right* —
but that is **validation of the model**, not **certification of the estimator**, and conflating
them is how "we can't check it" gets said out loud.

**Forward map (verification):**

- **Method of Manufactured Solutions.** Choose an analytic `u*(t)`, substitute into the ODE to
  derive the source `s(t) = du*/dt − f(u*)`, integrate the *modified* system, compare to `u*`
  exactly. Works for arbitrary nonlinear RHS. This is **the** canonical answer to "no analytic
  solution exists."
- **Order-of-accuracy verification** under systematic refinement (§2.1).
- **Analytic limits**: zero-density, single-clone, no-treatment, linearised, equilibrium — any
  parameterisation collapsing the model to closed form.
- **Invariants**: conservation, positivity, monotonicity, known bounds. A violation is *proof*.
- **Stability-region assertion** (§2.1) — needs no reference at all.
- **Independent implementation from the spec** (not a port), ideally different language/library.

**Estimator (validation):**

- **Synthetic data with known truth.** You can always simulate from your own model, so the truth is
  known **by construction**. Parameter recovery, CI coverage, SBC ranks. (t078 *had* this — its G2
  gate — and the doctrine must generalise it.)
- **A gold-standard optimiser as reference for the argmin**: a global method (CMA-ES, differential
  evolution, basin-hopping) at a large budget on a *certification subsample*. **The reference for
  an optimiser is a more expensive optimiser.** This always exists; it is only ever expensive.
- **Exact gradients (autodiff/adjoint) vs the production FD gradients.** Cheap, always available,
  and a **direct detector of `fb-...-009`'s exact defect**: an FD step that smooths basins away
  will disagree with the autodiff gradient.
- **Free self-consistency assertions**, requiring nothing external:
  - `nll_prof(ψ̂) == nll_global`, and `nll_prof(ψ) ≥ nll_global` for all ψ;
  - **nesting monotonicity**: the unrestricted fit's `nll` must be ≤ the restricted fit's, always;
  - **the returned outer optimum must be ≤ every evaluated point.** t078's *"terminating ABOVE the
    coarse-grid minimum it started from"* is one instance. An earlier draft called that "a
    diagnostic, if anyone is watching for it." It should be a **mandatory assertion** — free,
    unfakeable, and a *proof* of a broken objective when it fires.

> **The estimator is essentially never uncertifiable. It may be unaffordably certifiable — which
> is a budget statement (§2.7), not an epistemic one.**

---

## 4. Checks that can actually fail

The rule (§2.4) is a filter for rejecting bad checks. A doctrine that only teaches rejection, and
hands an author nothing to reach for, will be discharged by the same ceremony in a better costume.
This table is the constructive half, and it belongs in the leaf:

| Check | Cost | Fires when |
|---|---|---|
| Nesting monotonicity: `nll_unrestricted ≤ nll_restricted` | free | optimiser failure, always |
| Outer optimum ≤ best evaluated point | free | broken/moving objective (t078's 451-eval anecdote) |
| `nll_prof(ψ̂) == nll_global`; `nll_prof(ψ) ≥ nll_global` | free | broken profile |
| Argmin-spread vs objective-spread | free (reuse replicates) | separates non-identifiability from optimiser failure (`fb-...-013`) |
| Autodiff/adjoint gradient vs production FD gradient | cheap | `fb-...-009`'s FD-step bias, **directly** |
| Jacobian spectrum vs the scheme's stability region | cheap | `fb-...-008`, **directly** |
| Observed order of convergence `p̂` vs theoretical `p` | moderate | pre-asymptotic regime; RHS bugs |
| Simulated null distribution of `T` vs `χ²` | expensive | miscalibrated threshold (§2.3) |

---

## 5. What already exists, and what it gets wrong

`skills/statistics/likelihood-model-comparison.md` **already claims this ground**, in a four-bullet
`## Numerical-Precision Audit`. Its optimiser bullet:

> - Confirm optimizer convergence (gradient norm / relative tolerance), not just a returned value.
>   Re-fit from multiple starts for multimodal likelihoods.

**This is not merely thin. It is the advice that failed.** t078 confirmed convergence and re-fit
from multiple starts. The optimiser converged — reproducibly, repeatedly, and to the wrong place.
"Confirm convergence" asks for the optimiser's **self-report**, and the whole lesson of this
episode is that an estimator's self-report is not evidence about the estimator.

Its `## Common Failure Modes` entry — "**Unconverged or single-start optimization.** A local
optimum reported as the MLE" — names only half the failure space. Its twin, *a converged,
multi-start optimum that is reproducibly wrong*, is the one that bites, and it is absent.

| Surface | State |
|---|---|
| `skills/statistics/` (11 leaves) | Optimiser **selection**: absent. Profiling: one sentence (`population-genetics-likelihood.md`). Frequentist/MLE convergence: one bullet. Numerical accuracy: log-space/underflow only. Estimator validation as a named concept: **absent**. Well-posedness/conditioning: **absent**. (MCMC convergence, by contrast, is well covered.) |
| `commands/pre-register.md` (253 ln) | A developed **gate vocabulary** exists — Execution-Readiness, Calibration, Vehicle-Admissibility. **No compute-budget concept at all.** |
| `templates/pre-registration.md` (168 ln) | 13 sections in a machine-readable `_template.sections` registry. |
| `commands/plan-analysis.md` (203 ln) | **No synthetic-data or validation-probe concept.** Already names "numerical-precision audits" as an implementation gate. Has an `Aspect-contributed Sections` slot. |
| `commands/post-mortem.md` (70 ln) | Frames the incident exclusively as *failure*. |
| `aspects/computational-analysis/` (159 ln) | Contributes to `plan-pipeline` / `review-pipeline` / etc — **not** to `plan-analysis` / `pre-register` / `post-mortem`. Its QA vocabulary is *data/pipeline* QA, not *estimator* QA. |
| `docs/conventions/` | **Wrong home** — its bar is "a pattern observed in two or more downstream projects", and all 11 items are from `evolution`. Revisit if a second project reports the shape. |

---

## 6. The design

### 6.1 New leaf: `skills/statistics/estimator-certification.md`

Registry id `statistics-estimator-certification`.

```
# Estimator Certification

  <framing: an estimator's self-report is not evidence about the estimator.
   "Converged" is a claim the optimiser makes about itself.>

## The Four Axes, In Cost Order        (0 well-posedness / 1 forward map / 2 reproducibility
                                        / 3 threshold calibration -- each meaningless if the
                                        one above is unsettled)
## Axis 0: Is the Problem Resolvable?  (identifiability; the argmin-spread vs objective-spread
                                        discriminant; why skipping this makes Axis 2 adversarial)
## Axis 1: Does the Code Compute the Model?
        (independent reference = different ERROR-GENERATING MECHANISM;
         order-of-accuracy verification; stability-region assertion; MMS)
## Axis 2: Is the Answer a Function of the Data, or of the Run?
        (perturb every inferentially irrelevant DOF, not "the seed";
         2 seeds falsify, they do not certify; R>=5, report the MAX;
         a deterministic optimiser must have jitter INJECTED)
## Axis 3: Does the Decision Rule Have the Null It Claims?
        (simulate the null; incidental parameters; Cox-Reid / p* / Severini)
## Profiling                            (warm-starting; deterministic + bounded + UNIFORM in psi;
                                         the fixed-multistart-vs-continuation table;
                                         the derivable inner tolerance ~ delta/n;
                                         certify the DIFFERENCE statistic, not each nll)
## One Error Budget, Three Outcomes     (E = |b| + k*s; reject / do-not-reject / INDETERMINATE)
## Designing a Check That Can Fail      (the rule + the constructive table from §4)
## Common Failure Modes                 (converged-and-reproducibly-wrong; the interesting
                                         artifact; the 700x budget; the smoothing gradient)
## Halt-On Conditions
## Reporting                            (incl. the certification's invalidation clause)
## Companion Skills
```

**The leaf skeleton above is not a whole file.** `science skills lint` **machine-enforces** three
things a prose skeleton silently omits, and it exits 1 without them:

- YAML frontmatter with **`name`** (`statistics-estimator-certification`) and **`description`**;
- a **`## Companion Skills`** section (mandatory for *all* skills, not a convention);
- an entry in **`skills/INDEX.md`**.

Registration is therefore **four-place**, not three (`skills/INDEX.md`; the `## Leaves` table
*and* `## Principles` list in `skills/statistics/SKILL.md`; `commands/plan-analysis.md`'s Leaf
Selection Rubric), and one of those places is enforced by a linter rather than by convention.
`skills/statistics/*` leaves are **not** mirrored into `codex-skills/` — only the three *command*
edits propagate there. Exact anchors are in the implementation plan.

### 6.2 Correct `likelihood-model-comparison.md`

Not an expansion — a **correction** (§5).

- Rewrite the optimiser bullet: convergence is the optimiser's *self-report* and is not evidence.
- Add the missing failure mode: **a converged, multi-start optimum that is reproducibly wrong.**
- Add the smoothing-gradient class (§2.5): any operation that smooths the objective trades spread
  for bias.
- Companion-link the new leaf.

### 6.3 `templates/pre-registration.md` — a new gate section, `required: true`

**What `required:` actually does, because the obvious design is built on a false premise.** It is a
**scaffolding** flag, not a validation one: `required: true` → emitted into every new scaffold
(author drops it with `--without`); `required: false` → emitted only on `--with`.
**`science validate` does not check pre-registration sections at all** — its `document_structure`
check covers topics/papers/books against *hard-coded* lists and never reads `_template.sections`.
So there is **no "conditionally required" state**, and **no prose-only option gives this gate
validator teeth.**

Given that: **`required: true`**, deliberately breaking the pattern of the three existing
(`required: false`) gates. `required: false` is invisible to an author who does not already know
the doctrine exists — precisely the author about to repeat t078 — so the doctrine would reach only
those who least need it. The failure it prevents cost weeks of work, a ~700× budget error, and
flipped decisions in 3 of 15 cohorts; the ceremony it imposes is deleting one section from a survey
pre-registration. And the deletion is not pure cost: *"does this analysis estimate parameters
numerically? If not, remove this section"* is itself a forcing question.

Its force is that **it is in front of you**, not that a validator rejects you — and the section says
so, rather than implying an enforcement that does not exist.

```markdown
## Estimator Certification Gate

<!-- Applies when the analysis estimates parameters numerically -- any optimiser, profile, or
     ODE/discretisation in the inferential path. If it does not, DELETE this section.

     Nothing validates this section. Its force is that a threshold finer than its instrument's
     resolution is not conservative -- it is noise-driven, and optimiser error in a likelihood
     ratio has a SIGN (it is a difference of two one-sided biases).

     Order: well-posedness -> certify -> price -> commit. -->

| Axis | Commitment | Reference / domain |
|---|---|---|
| 0. Well-posedness | <structural + practical identifiability; are the profile CIs closed?> | <design-only; no data> |
| 1. Forward-map accuracy | <tolerance on the DECISION STATISTIC, propagated> | <INDEPENDENT mechanism: different scheme family, or adaptive solver 2-3 orders tighter. NOT a refinement of the same scheme.> |
| 2. Reproducibility | <max over R >= 5 replicates, not the median> | <perturb every inferentially irrelevant DOF: start point, ordering, threads, seeds. If deterministic, INJECT jitter.> |
| 3. Threshold calibration | <EXECUTED, or CONDITIONAL> | <if CONDITIONAL: cost, trigger, invalidation clause, AND the decisions that may not depend on it until it completes> |
| Outer optimiser | <method, and why it is valid for this profile's smoothness/discontinuity structure> | <gradient/FD-based methods PROHIBITED unless smoothness is demonstrated> |
| Error budget | E = \|b\| + k*s <= rho * sigma_null(T), k in [2,3] | <rho = 0.1 default; state it. NOT a % of the critical value -- that drifts with df. Never call it alpha.> |
| Indeterminate band | units with \|T - c\| <= E are INDETERMINATE | <report the count; not silently decided> |
| Compute budget | <cost> | <certified \| CONDITIONAL on ...> |
| Invalidation | <what re-opens this certificate> | <estimator, forward model, tolerances, hardware, libraries> |
```

#### Two templates, not one — and the registry row is mandatory in a harder sense than stated

There are **two** pre-registration templates, currently byte-identical, and a test
(`science/model/tests/test_templates.py`) asserts they stay that way:

- `templates/pre-registration.md` — what `commands/pre-register.md` tells the agent to read;
- `science/model/src/science_model/templates/pre-registration.md` — the **packaged** copy, which is
  what `Renderer` actually reads by default.

Editing only the root copy turns that test **red** *and* leaves `science entity create
pre-registration` scaffolding the **old** section list — the edit would "succeed" while changing
nothing an author sees. **Both files change, identically.**

And an earlier draft of this document claimed a body section without a registry row is "invisible
to the tooling." **False.** `_render_body` does an unguarded `metadata_by_name[parsed.name]`, so a
body heading with no registry row is a **KeyError crash on every render of that kind**. The
registry `name:` must match the `## ` heading text **exactly**. Registry *order* is free — body
heading order controls render order.

Registry row:

```yaml
- { key: estimator-certification-gate, name: "Estimator Certification Gate", required: true }
```

**Body placement**, which the design must specify because body order *is* render order: the three
existing gates sit at EOF but are all `required: false`, so they vanish from a default scaffold and
the rendered doc ends at `## Total Comparison Count`. Append the new `required: true` gate
**immediately after `## Total Comparison Count`**, so a default scaffold reads contiguously rather
than trailing a lone gate after a run of omitted ones.

### 6.4 `commands/pre-register.md`

- Add the **well-posedness → certify → price → commit** ordering and the Estimator Certification
  Gate to the gate vocabulary.

  **Not** under `#### Sub-axis: execution timing`, as an earlier draft said — only two of the three
  gates live there (Execution-Readiness, Vehicle-Admissibility); the Calibration Gate already has
  its **own** sub-axis. Estimator certification is not an execution-timing question at all: it asks
  whether the instrument can resolve the threshold, which is orthogonal to *when* the analysis runs.
  It gets a **new `#### Sub-axis:`** of its own, matching how Calibration is handled.
- Extend `### 4b. Suspicious/Unexpected Results` — currently "what would *too good to be true* look
  like?" — with its mirror, which is `fb-...-011`'s lesson:

  > An unexpectedly **interesting** result from a *validation probe* is a probe-defect signature,
  > not a finding. Before interpreting it, check the probe is not confounded with the thing it
  > validates.

### 6.5 `commands/plan-analysis.md`

- Leaf Selection Rubric row → `statistics-estimator-certification`, keyed on: profile likelihood,
  nuisance parameters, ODE / numerical integration, optimiser choice, parameter recovery,
  synthetic-recovery gate.
- New required body section **`Estimator and Probe Design`**: what is the estimator, how will it be
  certified on each of the four axes, and — for every validation probe — *what result would make
  this probe fail?*
- Extend Workflow step 5 with the certification plan.

### 6.6 `aspects/computational-analysis/` — a `## plan-analysis` hook

The aspect contributes nothing to `plan-analysis`, though `plan-analysis` reserves an
`Aspect-contributed Sections` slot. Add `### Additional section: Numerical Accuracy`, asking for an
independent reference **and** an order-of-accuracy check **and** a stability-region assertion
whenever the workflow integrates an ODE or otherwise discretises — `fb-...-008`'s explicit request.

Format matters: the convention puts the anchor on **its own line, blank-separated**, not inline —

```
### Additional section: Numerical Accuracy

(insert after: Model / Test Assumptions)

<body>
```

Aspect files are **agent-prose only**: no code parses them, and nothing validates or tests their
content (only aspect *names* are checked, against `KNOWN_ASPECTS`). This edit trips nothing — and
correspondingly, nothing will catch it if the format is wrong, which is why the format is stated
here.

### 6.7 `commands/post-mortem.md` — three edits

**(a) A success mode** (`fb-...-014`). The command frames the incident exclusively as failure. Here
**nothing surfaced late and no result existed**: pre-registered gates stopped the analysis before
observed data was read. That is *the system working*.

> A post-mortem on a **gate that fired** is the cheapest kind, and its lessons are the most
> transferable — because nothing is entangled with a finding anyone wants to defend.

Not a copy edit: a claim about where the good lessons are, and this episode is the evidence. The
gates caught, in order, an unstable integrator inherited from an earlier task, a profile protocol
that failed its own fidelity threshold, and an inner optimiser whose seed noise made the
load-bearing statistic a function of the seed rather than the data — **at zero inferential cost,
because no observed PSA value was ever read** (`fb-...-013`).

Step 1's "gap between expectation and outcome" needs its companion reading for this mode: *the gap
between what the plan assumed about its own estimator and what was true.*

**(b) Step 4's generalize gate** (`fb-...-016`):

> Separate **the failing thing** (usually local) from **the reason it was not caught sooner**
> (usually global). File on the latter.

**(c) Step 5/6's target list** (`fb-...-015`) reads as a closed enumeration, but `--target` is free
text. Name the resolvable namespaces (`skill:`, `aspect:`, `command:`, `template:`, `cli:`). Two of
this episode's lessons belonged to `aspect:computational-analysis`, which the list omits.

### 6.8 The preserved positive

`fb-...-013` is a `positive` and must not be digested into prose. It certifies a **structure**:

- gates consuming **design geometry and synthetic data only** (G1 structural identifiability, G2
  synthetic parameter recovery), run **before any model touches observed data**; and
- an **explicit failure taxonomy written before the failure** — a pre-committed tree separating
  *optimiser failure* from *practical non-identifiability*.

The second is the load-bearing half, and §2.0 now ships the **discriminant** that makes it
operable. Without it, predecessor task t075 hit the same optimiser, recorded it as "fits failed
unconverged", **discarded the diagnostic** — and t078 paid for the same defect twice. *A failure
taxonomy written after the failure will always find the category that closes the ticket.*

---

## 7. Non-goals

- **No code.** Nothing here adds a CLI check, a validator rule, or a lint. This is a real
  limitation, not a boast — §7.1.
- **No `docs/conventions/` entry** until a second project reports this shape (§5).
- **No new `concern` value.** The existing taxonomy routed all 11 items correctly.
- **Not a numerical-methods tutorial.** Scope: what must be true of an estimator *before a
  pre-registered threshold, budget, or gate is allowed to depend on it*.

### 7.1 The enforcement gap, stated rather than hidden

Every artifact here is **advisory**. A pre-registration that deletes the Estimator Certification
Gate while still fitting a model numerically passes `science validate` today and will keep passing.

That is a property of the surface (§6.3), not a choice — but it *is* a discovered toolkit defect,
bigger than this cluster:

> **`science validate` hard-codes section lists for three entity kinds (topic, paper, book) and
> ignores the `_template.sections` registry it already has.** Every other kind's `required: true`
> sections — pre-registration, hypothesis, question, the rest — are declared and never checked.

Closing that would give this gate real teeth *and* every other kind's required sections real teeth,
from a registry that already exists. **Out of scope here** (this cluster is prose), filed below.

---

## 8. Acceptance

Stated as what an author *encounters*, not what a validator *rejects* — because per §7.1 no
validator rejects any of it, and an acceptance criterion that quietly assumed enforcement would be
this document's own version of the bug it is about.

1. A pre-registration author whose analysis fits parameters numerically **cannot avoid meeting the
   question**: the gate is in the scaffold in front of them, and removing it is a deliberate act.
2. `likelihood-model-comparison.md` no longer tells an author that confirming convergence and
   re-fitting from multiple starts is sufficient. (Today it does; t078 did exactly that, and got a
   reproducibly wrong answer.)
3. An author with a **deterministic** optimiser is told to **inject** perturbation — the
   reproducibility check cannot be discharged by an estimator that trivially reproduces itself.
4. An author refining `h → h/10` of the same scheme is told that is a **convergence check, not a
   reference**, and is given the order-of-accuracy form that makes it informative.
5. `plan-analysis` routes an ODE / profile-likelihood / parameter-recovery task to
   `statistics-estimator-certification`.
6. `post-mortem` has a frame for an incident in which nothing broke and no result was lost.
7. For every validation probe an author plans, there is a written answer to *what result would make
   this probe fail?*
8. A certified analysis reports **three** outcomes per unit, not two: the INDETERMINATE band is
   representable.

### 8b. Follow-on work (out of scope, recorded so it is not lost)

- **Teach `science validate` to check entity sections against `_template.sections`** (§7.1).
  Affects every entity kind. Requires code, so not this cluster.

---

## 9. Review history

This design was revised after an adversarial statistical review. The review found that **two of the
original doctrine's most quotable rules were the two that were wrong** — which is itself the
doctrine's thesis operating on the doctrine:

| Original claim | Defect | Now |
|---|---|---|
| Accuracy needs "a different scheme, **or** a tighter tolerance" | The **"or" is unsound.** A refinement of the same scheme shares the leading truncation term, the stability boundary, and every non-`h` bug. `fb-...-008`'s real reference was LSODA at `rtol 1e-11` — a different scheme **AND** a tighter tolerance. The original licensed a check sharing the discretisation with the thing it validates — **in a document whose thesis is don't do that.** | §2.1 |
| "Two independent optimiser seeds" certifies reproducibility | **Fails the document's own rule.** A deterministic optimiser from a fixed start reproduces bit-for-bit: spread 0, gate passes, **cannot fail**. Also `n=2` estimates a median-ish quantity (CV 0.76) and is used to bound a max-ish one. | §2.2 |
| Two axes (reproducibility, accuracy) | Missing **well-posedness** (Axis 0) — without which Axis 2 has a *perverse gradient* toward selecting bias — and **threshold calibration** (Axis 3). | §2.0, §2.3 |
| "Continuation along a fixed path" is a *correct and cheap* fix | Correct (it restores functionhood) but **the most expensive of the three**, and it converts a path-dependence bug into a **reproducible bias** — the most dangerous state by the doc's own fb-009 lesson. | §2.6 |
| Certification is a global binary gate | No **error budget** combining bias and spread; no **INDETERMINATE** outcome — so t078's 3-of-15 flipping cohorts get reported as clean decisions once the global gate goes green. | §2.5 |
| "May be uncertifiable" if no independent reference | **Wrong and defeatist.** MMS, order verification, invariants, gold-standard optimiser, autodiff-vs-FD, and free self-consistency assertions always exist. Uncertifiable ≠ unaffordable. | §3 |
| "The threshold was not wrong" | **Unearned.** Nobody checked its calibration, and 136 nuisance parameters over ~17 patients is incidental-parameter territory where the profile LR is not `χ²₁`. | §1.2, §2.3 |
| "Unfalsifiable" | Wrong word. Falsifiability is a property of a hypothesis; **resolution** is a property of an instrument. | §1.1 |

## 10. Resolved: the instrument-error fraction `ρ`

An earlier draft left this open, declined a default, and — worse — called the constant **`α`**,
which in likelihood testing means the **test size**. A constant named `α` sitting beside a
likelihood-ratio threshold *will* be misread as a significance level. **The name is retired.**

> The constant is **`ρ`, the instrument-error fraction**: `E ≤ ρ · σ_null(T)`, **default `ρ = 0.1`**.
> Dimensionless. Measured against the **sampling SD of the decision statistic under its declared
> null** — never against the critical value.

Why not a percentage of the critical value: **it does not generalise.** It depends on the degrees of
freedom and on the test size, so it is a property of one particular null and not a rule (see the
drift table in §2.5: 3.7% → 2.9% across χ²₁…χ²₅ at 5%). Any threshold-relative percentage must be
**derived for the declared null**, and stating one as *the* default would bake a χ²₁-at-5% special
case into a general doctrine.

The author may override `ρ`, but must **state it and justify it**. It is never allowed to go
unstated: nothing validates this section (§7.1), so a blank `ρ` is unrecoverable — a template that
lets it go unfilled has changed nothing.

For scale: `ρ = 0.1` inflates `Var(T)` by ~1%. **t078's instrument error was 171% of its critical
value.**

## 11. Disposed: the two remaining questions

Neither is answered by *prescribing* a universal answer — there isn't one. Both are answered by
requiring the author to **declare**, which is what a pre-registration is for.

### 11.1 The outer optimiser over a discontinuous profile

A fixed-multistart profile restores functionhood but is **discontinuous** in ψ (the winning start
switches basins). Running a gradient- or FD-based outer optimiser over a piecewise surface is a
second-order version of the very bug the multistart pool was adopted to fix.

The doctrine does not name one admissible optimiser. It requires:

> **Declare why the outer optimiser is valid for the profile's smoothness / discontinuity
> structure.**
>
> **Gradient-based and finite-difference-based outer methods are PROHIBITED unless smoothness is
> demonstrated** — not assumed, not asserted. A fixed-multistart profile is discontinuous *by
> construction*, so the default position for one is: prohibited.
>
> Absent a smoothness demonstration, use a derivative-free outer method, or a dense grid with local
> refinement.

### 11.2 Axis 3 when simulating the null is unaffordable

Simulating a null distribution is genuinely expensive and will not always be affordable. The
doctrine does not require it unconditionally. It requires that Axis 3 be **either executed or
explicitly CONDITIONAL** — and a `CONDITIONAL` is not a shrug; it carries four obligations:

> A `CONDITIONAL` Axis 3 must state:
>
> 1. **Cost** — what executing it would take.
> 2. **Trigger** — what would cause it to be executed.
> 3. **Invalidation clause** — what would void the deferral.
> 4. **The decisions that MAY NOT depend on it until it completes.**
>
> (4) is the one with teeth. Deferring Axis 3 does not merely add a caveat — it **removes decisions
> from the table.** Any verdict resting on `Pr(T > c | H₀) = α` is unavailable while the null is
> unverified, and the pre-registration must say which verdicts those are, by name, before the
> analysis runs.

An uncalibrated threshold is not a slightly-weaker threshold. It is a threshold whose error rate is
unknown, and a decision rule with an unknown error rate is not a decision rule.

## 12. Landing hazard (mechanical, not conceptual)

`codex-skills/` is a generated mirror and is **already drifted on this branch**:
`codex-skills/science-big-picture/SKILL.md` is stale against `commands/big-picture.md`, which the
InstrumentResult work edited. **No test catches this** — every codex test asserts substring
presence only, and there is no committed-vs-generated drift test.

So whoever regenerates the mirror for this design will sweep an unrelated `InstrumentResult` diff
into their commit. **Regenerate and commit that drift separately, first**, so this design's diff
contains only this design.

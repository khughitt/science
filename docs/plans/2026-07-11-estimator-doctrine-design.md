# Estimator Doctrine — design

**Status:** Proposed. Not implemented.
**Scope:** 11 open feedback items, `fb-2026-07-10-006` … `fb-2026-07-10-016`.
**Source project:** `evolution` (all 11), all tracing to one artifact:
pre-registration `0004-pre-registration-t078-kill-vs-psa-downregulation.md`, task t078.

> **Provenance note, stated up front.** The `evolution` project is not checked out on this
> machine. Every number, threshold, and failure described below is quoted from the feedback
> entries themselves (`~/.config/science/feedback/fb-2026-07-10-0**.yaml`), not re-derived
> from the project. Anyone revisiting this doc should treat the feedback record as the
> primary source and the pre-registration as the thing to check it against.

---

## 1. The finding

Eleven feedback items were filed from one episode. They are not eleven complaints. They are
one failure, observed eleven times, and the reporter of `fb-2026-07-10-016` had already
worked out why they looked like eleven:

> The most transferable lessons from this incident were not about the failing component but
> about **why it stayed invisible**: an invariance check that could not detect inaccuracy, a
> fidelity threshold with an unspecified domain, an optimiser-selection criterion that
> rewarded bias, and a probe confounded with the parameter it validated. The mechanism (a
> 136-nuisance-parameter profile) was entirely project-local and would have generalised to
> nothing.

That is the organising principle of this document, and it is worth stating in its own right,
because it is the rule for reading every item below:

> **The failing thing is usually local. The reason it stayed hidden is usually global.
> File on the latter.**

The local thing was a 136-nuisance-parameter profile likelihood over a cohort of PSA
trajectories. Nobody else will ever have that. What everybody has is the *shape* of how it
hid.

### 1.1 The root cause, in one sentence

**The estimator was assumed rather than certified, and every artifact downstream inherited the
assumption.**

t078 pre-registered a decision rule — delta-nll thresholds of 1.92 and 3.00 — and named an
optimiser. It never asked whether that optimiser could resolve those thresholds. It could not.
Refitting *identical synthetic data* under two independent Sobol scramble seeds moved the
load-bearing statistic `LR_out` by a median of 2.40 and a max of 6.58 — **1.71× its own 3.84
critical value** — flipping the reject/do-not-reject decision in **3 of 15 cohorts**
(`fb-2026-07-10-007`).

The threshold was not wrong. The threshold was *unfalsifiable*: the instrument could not
resolve the distinction the threshold was drawn to make. Everything else — the compute budget,
the fidelity probe, the validation gates, and finally the post-mortem — was then built on top
of an estimator nobody had certified.

### 1.2 The shape of how it hid

Four of the eleven items describe checks that **ran, passed, and could not have failed for the
reason they were invoked**:

| Item | The check | Why it could not fail |
|---|---|---|
| `fb-...-008` | Integrator validated by comparing two implementations | Both implement the **same** fixed-step RK4 scheme. Two implementations of one scheme are equivariant at any step size. They agreed to `6e-15` **while both were wrong** — measured later against LSODA at `rtol 1e-11`, median error `1.2e-9` but **p99 0.70 and max 72.0 log units**. |
| `fb-...-010` | "max surface deviation ≤ 0.1 nll" | The **domain of the max was never specified**. Taken over the whole `(d, φ)` box it landed in cells 400+ nll units above the minimum that no inference ever reads. Restricted to the region the analysis actually consults, the same runs gave 0.11–0.75. |
| `fb-...-011` | Null-calibration probe | The probe **gridded `log10 d`, the very parameter whose true values varied across its own cells**, while the unrestricted model had a free `φ` axis to absorb the same discretisation error. `LR_out` then partly measured each `d_true`'s distance to the nearest grid node. |
| `fb-...-009` | Optimiser selected by seed-to-seed reproducibility | Reproducibility **alone** selects for bias. The winning config had seed spread 0.0008 — three orders of magnitude better than default — and was *reproducibly wrong*, missing the true minimum by 0.21 SSR per patient because a large finite-difference step smooths narrow basins away. |

Every one of these is the same defect: **a measurement that did not happen, reported as a
clean result.**

That sentence is not a coincidence. It is verbatim the ruling this toolkit just shipped for
*code* instruments — the `InstrumentResult` convergence
([`2026-07-11-instrument-result-convergence-design.md`](2026-07-11-instrument-result-convergence-design.md)),
where a query that could not run returned an empty list and the CLI printed "no findings."
The present document is the same ruling for *methodological* instruments. There a helper that
never looked returned `[]`; here a check that could not fail returned PASS. The remedy rhymes
too: make the "could not run" state **representable and loud**, rather than letting it wear
the costume of a clean result.

The resonance is worth naming explicitly in the guidance, because an author who has internalised
one will recognise the other.

---

## 2. The two principles

The eleven items resolve into two principles. They are not a partition of the items — several
items are evidence for both — they are two *lenses*, and every item is visible through at
least one.

### Principle 1 — Certify the estimator before anything depends on it

An estimator is **certified** when it has passed *both* of:

1. **Reproducibility.** Every reported statistic is reproduced by **two independent optimiser
   seeds on the same data**, to within a stated fraction of *its own critical value*.
   (`fb-...-007`. Note the denominator: "within X% of the statistic's own critical value" is
   the falsifiable form. "Within X%" alone is not — a statistic can be reproducible to 1% and
   still cross its threshold.)

2. **Accuracy against an INDEPENDENT reference.** A different scheme, or a tighter tolerance —
   not a second implementation of the same scheme. (`fb-...-008`.)

**Both, jointly. Either alone is actively adversarial.**

- Reproducibility alone selects for bias (`fb-...-009`): the low-variance config was
  reproducibly wrong, and pooled over 17 patients it was **2.6× worse** than the noisy config
  that actually found the minima (nll seed spread 1.61 vs 0.63), because one-sided per-unit
  optimiser errors **add rather than cancel**.
- Accuracy alone, unaccompanied by reproducibility, tells you the estimator *can* find the
  right answer, not that it *will* on the run whose number you are about to publish.

A corollary that deserves its own line, because it caught people twice:

> **Per-unit convergence does not imply pooled convergence** when the likelihood sums many
> independently-optimised blocks. (`fb-...-009`.)

#### 1a. Warm-starting silently destroys the objective

Profiling defines `nll_prof(ψ) = min over nuisance η`. Warm-starting the inner fit from the
previous grid point's solution makes the computed value depend on **the path taken through the
grid**. The "objective" is then **not a function of ψ at all** (`fb-...-006`).

This is not an optimisation detail; it is a silent violation of the definition. Observed
consequence: Nelder–Mead optimising a moving target for 451 evaluations and 236 s, and
**terminating ABOVE the coarse-grid minimum it started from** — a result that is impossible
for a genuine function and is therefore a *diagnostic*, if anyone is watching for it.

Correct and cheap alternatives, both of which restore functionhood: a **fixed multistart pool**,
or **continuation along a FIXED path recomputed identically at every evaluation**.

The rule: *inner fits under a profile must be a pure function of (fixed start set, ψ).*

#### 1b. Certify, then price, then commit

t078 budgeted **200 CPU-hours** for its primary profile. That price was quoted for a
warm-started protocol which was later **rejected by the pre-registration's own fidelity test**.
With the cheapest protocol that actually survives certification, the same design costs
**~4,900 CPU-hours** for the recovery gates and **~140,000** for the nested bootstrap
(`fb-...-012`).

The budget was therefore never a constraint on the analysis. It was a **consequence of an
untested assumption about the optimiser** — off by a factor of ~700.

> **Ordering rule: certify the estimator → price the design → commit the budget.**
> If a budget must be committed before certification, it must be stated as *conditional*, and
> the pre-registration must name what invalidates it.

### Principle 2 — A check must be able to fail for the reason you invoked it

Before a check is allowed to discharge an obligation, its author must answer: **what result
would have made this check fail?** If no achievable result would, the check is ceremony, and —
worse than ceremony — it is *evidence-shaped* ceremony, which is how it discharged the
obligation in the first place.

Three concrete rules, each earned by an item:

- **Invariance ≠ accuracy.** Reproducing a result two ways that share the discretisation
  validates the *implementation*, not the *method*. Numerical accuracy requires an
  independent reference. (`fb-...-008`.)
- **A threshold on a surface must pre-specify the domain over which its max is taken.**
  Narrowing the domain *after* seeing the number is exactly the renegotiation
  pre-registration exists to prevent — which is why the domain must be named **up front,
  alongside the threshold value**, not derived when the threshold fails. (`fb-...-010`.)
- **A probe must not discretise a parameter whose true values vary across its own cells.**
  Put the simulated truths **on** the nodes, or remove the grid. And before interpreting any
  probe outcome, **check for correlation between the outcome and distance-to-node.**
  (`fb-...-011`.)

The `fb-...-011` case is the cautionary one, because the artifact was *interesting*: the
confounded probe produced `φ̂ = 0.56` under a `φ_true = 1` null, which reads as a substantive
identifiability finding. Re-run with continuous `d`, `d̂` tracked `d_true` (0.0121 / 0.0313 /
0.1035 vs 0.01 / 0.03 / 0.10) **and the effect vanished entirely**. A broken probe does not
announce itself by returning nothing. It returns something worth writing up.

---

## 3. What already exists, and what it gets wrong

`skills/statistics/likelihood-model-comparison.md` **already claims this ground**, in a
four-bullet section, `## Numerical-Precision Audit`. Its optimiser bullet reads:

> - Confirm optimizer convergence (gradient norm / relative tolerance), not just a returned
>   value. Re-fit from multiple starts for multimodal likelihoods.

**This is not merely thin. As written, it is the advice that failed.** t078 confirmed
convergence and re-fit from multiple starts. The optimiser converged — reproducibly,
repeatedly, and to the wrong place. "Confirm convergence" is a claim about the optimiser's
*self-report*; the whole lesson of this episode is that an estimator's self-report is not
evidence about the estimator.

So the change to that leaf is a **correction**, not an expansion. Its `## Common Failure Modes`
entry "**Unconverged or single-start optimization.** A local optimum reported as the MLE"
names only half the failure space; its twin — *a converged, multi-start optimum that is
reproducibly wrong* — is the one that actually bites, and it is absent.

The rest of the surface:

| Surface | State |
|---|---|
| `skills/statistics/` (11 leaves) | Optimiser **selection**: absent. Likelihood **profiling**: one sentence, in `population-genetics-likelihood.md`. Frequentist/MLE convergence: one bullet. Numerical accuracy: the log-space/underflow bullets only. Estimator validation as a named concept: **absent**. (MCMC convergence, by contrast, is well covered — R-hat/ESS/divergences across three leaves.) |
| `commands/pre-register.md` (253 ln) | A well-developed **gate vocabulary** already exists — Execution-Readiness, Calibration, Vehicle-Admissibility, all optional and mode-triggered. **No compute-budget concept at all.** Clean insertion point. |
| `templates/pre-registration.md` (168 ln) | 13 sections in a machine-readable `_template.sections` registry; the three gates are all `required: false`. Adding a conditionally-required gate section is an exactly-supported extension. |
| `commands/plan-analysis.md` (203 ln) | **No synthetic-data or validation-probe concept.** (`## Validation Pressure Scenarios` is a misleading name — it self-tests the command's own leaf selection, not an analysis.) Already names "numerical-precision audits" as an implementation gate a pre-reg won't have enumerated. Has an `Aspect-contributed Sections` slot. |
| `commands/post-mortem.md` (70 ln) | Frames the incident exclusively as *failure*: "an analysis that failed", "a QA issue surfaced late", "a result contradicted a pre-registered expectation." |
| `aspects/computational-analysis/` (159 ln) | Contributes to `plan-pipeline`, `review-pipeline`, `interpret-results`, `discuss`, `research-topic` — **not** to `plan-analysis` / `pre-register` / `post-mortem`. Its QA vocabulary is *data/pipeline* QA, not *estimator* QA. The one sentence in the entire repo gesturing at estimator validation is "Known-answer tests: run on synthetic or known data where the correct answer is predetermined" — and it is scoped to pipeline transformations, not fitting code. |
| `docs/conventions/` | **Wrong home.** Its stated bar is "a pattern observed in two or more downstream projects." All 11 items are from `evolution`. Revisit if a second project reports the same shape. |

---

## 4. The design

### 4.1 New leaf: `skills/statistics/estimator-certification.md`

Registry id `statistics-estimator-certification`. Carries both principles, because they share
one root cause and because each half is thin alone.

Proposed section structure, using the established leaf vocabulary (`## Pre-Flight Checklist`,
`## Common Failure Modes`, `## Halt-On Conditions`, `## Reporting`, `## Companion Skills`):

```
# Estimator Certification

  <framing: an estimator's self-report is not evidence about the estimator.
   "Converged" is a claim the optimiser makes about itself.>

## Pre-Flight Checklist          (before any threshold, budget, or gate depends on a fit)
    1. Is the objective a function?      -> warm-starting check (1a)
    2. Two independent seeds, same data  -> within X% of the statistic's OWN critical value
    3. Accuracy vs an INDEPENDENT reference (different scheme / tighter tolerance)
    4. Pooled, not just per-unit
    5. Only now: price the design and commit the budget

## Certifying the Objective     (warm-starting; fixed multistart pool; fixed-path continuation)
## Reproducibility and Accuracy Are Not Substitutes
        (the 2.6x-worse-by-spread result; one-sided errors add, they do not cancel)
## Designing a Check That Can Fail
        (invariance != accuracy; the domain of a max; probe/target confounding)
## Common Failure Modes
        (converged-and-reproducibly-wrong; the interesting artifact; the 700x budget)
## Halt-On Conditions
## Reporting
## Companion Skills
```

**Three-place registration** (per the skills convention):
1. `skills/INDEX.md` — under `## Statistics`.
2. `skills/statistics/SKILL.md` — a row in the `## Leaves` table + a numbered `## Principles` entry.
3. `commands/plan-analysis.md` — a row in the `## Leaf Selection Rubric`, keyed on triggers like
   *profile likelihood, nuisance parameters, ODE/numerical integration, optimiser choice,
   parameter recovery, synthetic-recovery gate*.

Then regenerate `codex-skills/` (it is a generated mirror — never hand-edited).

### 4.2 Correct `likelihood-model-comparison.md`

Not an expansion — a correction, per §3.

- Rewrite the optimiser bullet in `## Numerical-Precision Audit`: convergence is the
  optimiser's *self-report*, and is not evidence. Point to the new leaf.
- Add the missing failure mode: **a converged, multi-start optimum that is reproducibly
  wrong**, sitting alongside the existing "unconverged or single-start" entry.
- Add the new leaf to its `## Companion Skills`.

### 4.3 `templates/pre-registration.md` — a new gate section, `required: true`

**First, what `required:` actually does — because the obvious design is built on a false
premise.** `required:` is a **scaffolding** flag, not a validation one:

- `required: true` → the section is emitted into every new scaffold; the author drops it with
  `--without <key>`.
- `required: false` → the section is emitted **only** if the author asks, with `--with <key>`.

`science validate` **does not check pre-registration sections at all.** Its
`document_structure` check covers topics, papers, and books, against *hard-coded* section
lists — it never reads the `_template.sections` registry. So there is **no "conditionally
required" state**, and **no prose-only option gives this gate validator teeth.** Any design
that claims otherwise is claiming a completion it did not earn.

Given that, the section is **`required: true`** — emitted into every new pre-registration.

The three existing gates are all `required: false`, so this deliberately breaks their pattern.
The reason is an asymmetry of costs. `required: false` is invisible to an author who does not
already know this doctrine exists — which is exactly the author who is about to repeat t078;
the doctrine would reach only the people who least need it. The failure it prevents cost weeks
of work, a ~700× budget error, and flipped decisions in 3 of 15 cohorts. The ceremony it
imposes is deleting one section from a survey pre-registration. And the deletion is not pure
cost: *"does this analysis estimate parameters numerically? If not, remove this section"* is
itself a forcing question that makes an author classify their own analysis.

Its force is that **it is in front of you**, not that a validator rejects you. State that
plainly in the section's own comment rather than implying an enforcement that does not exist.

```markdown
## Estimator Certification Gate

<!-- Applies when the analysis estimates parameters numerically -- any optimiser, profile,
     or ODE/discretisation in the inferential path.
     If it does not, DELETE this section.

  Nothing validates this section. Its force is that a threshold which depends on an
  uncertified estimator is not conservative -- it is UNFALSIFIABLE, because the instrument
  cannot resolve the distinction the threshold is drawn to make.

  - Reproducibility: every reported statistic must be reproduced by two independent
    optimiser seeds on the same data, to within <X>% of THAT STATISTIC'S OWN critical value.
    (Not "within X%" -- the critical value is the denominator that makes it falsifiable.)
  - Accuracy: state the INDEPENDENT reference -- a different scheme or a tighter tolerance.
    A second implementation of the same scheme is an invariance check, not an accuracy check.
  - Domain: for every tolerance threshold on a surface, name the region over which its max
    is taken, UP FRONT, alongside the value.
  - Budget: certify -> price -> commit. If the budget is committed before certification,
    mark it CONDITIONAL and name what invalidates it.

  A failed gate is a protocol failure, not a substantive null -- classify per the Null
  Result Plan. -->

| Criterion | Threshold | Reference / domain |
|---|---|---|
| Seed reproducibility | within <X>% of the statistic's own critical value | <2 independent seeds> |
| Numerical accuracy | <tolerance> | <INDEPENDENT scheme / tighter tolerance> |
| Surface-deviation domain | <value> | <the named region inference actually reads> |
| Compute budget | <cost> | <certified | CONDITIONAL on ...> |
```

Add the corresponding row to the `_template.sections` registry with `required: true` (a body
section without a registry row is invisible to the tooling).

### 4.4 `commands/pre-register.md` — the ordering rule

Add the **certify → price → commit** ordering, and the estimator-certification gate, to the
gate vocabulary in `### 0. Target Class` / the execution-timing sub-axis where the other three
gates live. This is where an author already decides which gates apply.

Also extend `### 4b. Suspicious/Unexpected Results` — currently "what would *too good to be
true* look like?" — with its mirror image, which is the `fb-...-011` lesson:

> An unexpectedly **interesting** result from a *validation probe* is a probe-defect signature,
> not a finding. Before interpreting it, check the probe is not confounded with the thing it
> validates.

### 4.5 `commands/plan-analysis.md` — a probe-design section

- Rubric row → `statistics-estimator-certification` (§4.1).
- A new required body section, **`Estimator and Probe Design`**, joining the existing list
  (which already runs Model/Test Assumptions → Power Floor → Bias vs Variance → Sensitivity
  Arbitration). It asks: what is the estimator, how will it be certified, and — for every
  validation probe — *what result would make this probe fail?*
- Workflow step 5 currently says "State model/test assumptions, power floor or resolution
  limit, bias-vs-variance risks, and sensitivity-arbitration rules." Extend with the estimator
  certification plan.

### 4.6 `aspects/computational-analysis/` — a `## plan-analysis` hook

The aspect currently contributes nothing to `plan-analysis`, though `plan-analysis` reserves an
`Aspect-contributed Sections` slot for exactly this. Add:

```
## plan-analysis
### Additional section: Numerical Accuracy  (insert after: Model / Test Assumptions)
```

...asking for an independent reference whenever the workflow integrates an ODE or otherwise
discretises — which is `fb-...-008`'s explicit request ("the aspect should ask for one
whenever a workflow integrates an ODE or otherwise discretises").

### 4.7 `commands/post-mortem.md` — three edits

**(a) A success mode** (`fb-...-014`). The command frames the incident exclusively as failure.
Here **nothing surfaced late and no result existed**: pre-registered gates stopped the analysis
before observed data was ever read. That is *the system working*. Add an explicit mode:

> A post-mortem on a **gate that fired** is the cheapest kind, and its lessons are the most
> transferable — because nothing is entangled with a finding anyone wants to defend.

This is not a copy edit. It is a claim about where the good lessons are, and this episode is
the evidence: the gates caught, in order, an unstable integrator inherited from an earlier
task, a profile protocol that failed its own fidelity threshold, and an inner optimiser whose
seed noise made the load-bearing statistic a function of the seed rather than the data — **at
zero inferential cost, because no observed PSA value was ever read** (`fb-...-013`).

Step 1's "the gap between expectation and outcome" needs a companion reading for this mode:
*the gap between what the plan assumed about its own estimator and what was true.*

**(b) Step 4's generalize gate** (`fb-...-016`) should prompt explicitly:

> Separate **the failing thing** (usually local) from **the reason it was not caught sooner**
> (usually global). File on the latter.

**(c) Step 5/6's target list** (`fb-...-015`) reads as a closed enumeration but `--target` is
free text. Name the resolvable namespaces (`skill:`, `aspect:`, `command:`, `template:`,
`cli:`) rather than an example subset. Two of this episode's lessons belonged to
`aspect:computational-analysis`, which the list does not mention.

### 4.8 The preserved positive

`fb-...-013` is a `positive`, and the design must not quietly digest it into prose. What it
certifies is a **structure** worth keeping and naming:

- gates that consume **design geometry and synthetic data only** (G1 structural
  identifiability, G2 synthetic parameter recovery), run **before any model touches observed
  data**; and
- an **explicit failure taxonomy written before the failure** — a pre-committed decision tree
  that classified *optimiser failure* separately from *practical non-identifiability*.

That second one is the load-bearing half. Without it, the predecessor task t075 hit the same
optimiser and recorded it as "fits failed unconverged" — **discarding the diagnostic**. t078
then paid for the same defect twice. A failure taxonomy written *after* the failure will
always find the category that closes the ticket.

---

## 5. Non-goals

- **No code.** Nothing here adds a CLI check, a validator rule, or a lint. This is a real
  limitation, not a boast — see §5.1. The doctrine is prose that changes what authors are
  *asked*; the toolkit has no way to verify that an independent reference is genuinely
  independent, and pretending otherwise would ship a guard that certifies a completion it did
  not earn.
- **No `docs/conventions/` entry** until a second project reports this shape (§3).
- **No new `concern` value.** The existing taxonomy (`methodology:statistics` / `:qa` /
  `:design`) already routed all 11 items correctly.
- **Not a general numerical-methods tutorial.** Scope is: what must be true of an estimator
  *before a pre-registered threshold, budget, or gate is allowed to depend on it*.

### 5.1 The enforcement gap, stated rather than hidden

Every artifact this design touches is **advisory**. A pre-registration that ignores the
Estimator Certification Gate — or deletes it while still fitting a model numerically — passes
`science validate` today and will keep passing it.

That is not a choice this design made; it is a property of the surface it lands on
(§4.3). But it *is* a discovered defect in the toolkit, and it is bigger than this cluster:

> **`science validate` hard-codes section lists for three entity kinds (topic, paper, book)
> and ignores the `_template.sections` registry it already has.** Every other kind's
> `required: true` sections — pre-registration, hypothesis, question, and the rest — are
> declared and then never checked.

Closing that would give this gate real teeth *and* every other kind's required sections real
teeth, from a registry that already exists. It is deliberately **out of scope here** (this
cluster was scoped as prose), and is filed as follow-on work below. It should not be smuggled
in as a footnote to a methodology spec.

---

## 6. Acceptance

Stated as what an author *encounters*, not what a validator *rejects* — because per §5.1 no
validator rejects any of it, and an acceptance criterion that quietly assumed enforcement
would be this document's own version of the bug it is about.

1. A pre-registration author whose analysis fits parameters numerically **cannot avoid meeting
   the question**: the Estimator Certification Gate is in the scaffold in front of them, and
   removing it is a deliberate act. (It is *not* validator-enforced — see §5.1. Force here
   means visibility, and the design says so out loud rather than implying more.)
2. `likelihood-model-comparison.md` no longer tells an author that confirming convergence and
   re-fitting from multiple starts is sufficient. (Today it does, and t078 did exactly that,
   and it produced a reproducibly wrong answer.)
3. `plan-analysis` routes an ODE / profile-likelihood / parameter-recovery task to
   `statistics-estimator-certification`.
4. `post-mortem` has a frame for an incident in which nothing broke and no result was lost.
5. For every validation probe an author plans, there is a written answer to *what result would
   make this probe fail?*

## 6b. Follow-on work (out of scope, recorded so it is not lost)

- **Teach `science validate` to check entity sections against `_template.sections`** (§5.1).
  Affects every entity kind, not just pre-registration. Requires code, so it does not belong
  to this cluster.

## 7. Open questions

- **`fb-...-007`'s "within X%" needs a default.** The item does not propose a value, and this
  design does not invent one. Options: leave `X` author-chosen but *mandatory to state* (the
  minimum viable rule, and what §4.3 currently encodes), or ship a default. Leaning: author-chosen,
  because the right value depends on how close the statistic sits to its critical value — but
  a template that lets `X` go unstated has changed nothing.
- **How does an author certify accuracy when no independent reference is available?** For an
  ODE there is always LSODA. For a bespoke likelihood there may be nothing to compare against.
  The honest answer may be that the analysis is then uncertifiable and must say so — but that
  is a strong claim and it is not yet earned by any of the 11 items.
- **`fb-2026-07-11-005`** (retired-hypothesis phase in `big-picture`) is `methodology:design`
  but belongs to the attention-ranking cluster, not this one. It is already recorded as
  follow-on work in the InstrumentResult design. Noted here only so its omission is deliberate.

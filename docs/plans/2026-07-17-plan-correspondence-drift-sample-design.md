# Plan correspondence-drift sample — design (pre-registration)

**Status:** DESIGN — 2026-07-17. **Pre-registration. Nothing below may change
after the first plan is adjudicated.**

This spec unblocks
[`2026-07-17-curation-scope-certification-design.md`](2026-07-17-curation-scope-certification-design.md)
(S1), whose §5 ruling is conditional on evidence that does not yet exist. S1's v1
justified admitting `plan` to curation scope with a status distribution — *"2 of
126 plans marked `complete`"* — and that inference was **retracted**: a status
distribution cannot distinguish a stale record from a plan legitimately in flight.

**Sequencing (ruled).** This sample runs **before** the S1 `correspondence` roster
is ratified. Ratifying the roster first would be circular — taxonomy judgment
would precede the evidence meant to justify it. Scope here is **`plan` only**;
every other kind is ratified afterwards, individually, informed by this result.

## 1. The question

> Do `plan` entities drift from reality often enough that a correspondence review
> would catch something a human would want caught?

**Not** "are plans mostly incomplete" (S1 §2.2's retracted error). The measured
quantity is the **mismatch rate**: how often a plan's recorded `status` disagrees
with what the evidence says its status is.

## 2. What this gates

Three pre-registered outcomes. **All three are reachable**; a gate whose "no"
branch is unreachable is not a certification.

| Outcome | Consequence |
|---|---|
| **Drift demonstrated** | Retain S1 §5. Admit `plan` to `curation_scope: correspondence`. **Then** ratify the remaining kinds individually. |
| **Drift ruled out** | **Withdraw S1 §5.** Certify epistemic-only as correct; `plan` stays out of scope. S1 closes having answered its question "no". The rest of the program (S2 rotation, S3 import) loses its S1 dependency and must re-justify itself independently. |
| **Inconclusive** | Expand per the §7 ladder. **Uncertainty is never read as absence** — an inconclusive result may not be reported as "no drift", and the §6 indeterminate rate can force this outcome on its own. |

## 3. Population (pinned)

**`plan` entities only** — `entities/plans/*.md`. Loose `doc/plans/*.md` are
**excluded**: they are not entities, cannot carry `review_state`, and S1's
question is about a *kind*. Including them would measure a different population
(that is S3's concern).

Measured 2026-07-17:

| Project | N | HEAD | tree | claimed-status distribution |
|---|---|---|---|---|
| multiple-myeloma | 126 | `0496fbc5` | **DIRTY** | draft 78, active 46, complete 2 |
| natural-systems | 109 | `85829c216` | clean | draft 49, active 22, complete 16, proposed 12, implemented 2, ready-with-caveats 2, current 1, completed 1, in-progress 1, agreed 1, design 1, superseded 1 |
| protein-landscape | 19 | `66051a2` | clean | active 11, draft 4, approved 3, proposed 1 |
| post-acute-infection | 10 | `007cbdf` | clean | active 6, ready-with-caveats 2, not-ready 1, archived 1 |

**N = 264.**

**Blocking preconditions.**

1. **multiple-myeloma's tree is dirty** and it is the largest stratum (48% of N).
   Its working copy is Dropbox-synced and its branch/HEAD can move mid-session.
   Commit or stash, re-pin, and **re-verify the sha immediately before the draw**.
   Adjudicating against an unpinned tree measures nothing reproducible.
2. **Re-pin all four HEADs at draw time** and record them. The figures above are a
   sizing sketch (S1 §2's lesson); the draw's own pins are authoritative.
3. **Every probe resolves against the pinned commit**, never against a later
   working tree.

## 4. Pre-registration — fixed before adjudication begins

Recorded, committed, and hashed **before the first plan is read**:

- the four pinned commit shas and clean-tree assertions (§3);
- the RNG **seed** and the realised allocation per stratum (§5);
- the **adjudication rubric** (§6) and its version;
- the **materiality threshold** θ (§7);
- the **ladder** and per-look α (§7);
- the **stopping rule** (§7).

Anything discovered later that would change these **invalidates the draw** and
requires a fresh pre-registration. This is the point of the exercise: thresholds
fixed *after* seeing a result are not thresholds.

## 5. Selection and stratification

- **Stratify by `(project, claimed_status)`.** Both matter: mm is 48% of N with a
  visibly different status convention (zero `proposed`, 2 `complete`), and
  `claimed_status` is one side of the comparison.
- **Proportional allocation, largest-remainder (Hamilton), no forced minimums.**
  A stratum rounding to zero is **reported as unsampled**, not topped up —
  silence is honest when prevalence is negligible. Its `N_h` is excluded from the
  population the estimate generalises to, and that exclusion is stated with the
  result.
- **Any stratum allocated `n_h = 1` is censused or collapsed** before inference,
  declared **before** the draw. A singleton is degenerate under resampling.
- **Collapse rule, predeclared:** the eleven natural-systems statuses outside the
  legal six (`proposed`, `implemented`, `current`, …) collapse into a single
  `illegal-vocabulary` stratum. They are S4's subject, not S1's, and splitting
  them creates singletons by construction.
- **Realised inclusion probabilities `π_h = n_h/N_h` are computed after the draw
  is fixed but before any outcome is scored**, and recorded with it. Largest-
  remainder rounding routinely breaks self-weighting, so **assume design-weighted
  inference** and prove otherwise, never the reverse.

## 6. Adjudication rubric

### 6.1 Blinded

**The adjudicator never sees `claimed_status`.** It derives a status from
evidence alone; the comparison against `claimed_status` happens **mechanically,
afterwards**. Showing the claim first would anchor the verdict toward it and
depress the very mismatch rate being measured — the result would be
indistinguishable from "no drift" regardless of the truth. Blinding is cheap and
is idiomatic here (`/science:discuss` already ships a double-blind mode).

Frontmatter is stripped from the adjudicator's view; the body, its declared
deliverables, and its task references are supplied.

### 6.2 Adjudicated status, from evidence only

Probes run against the pinned commit. Each declared deliverable is
**tri-state** — `present` / `absent` / `unknown` — and `deliverables[].probe`
records exactly what was tested (path, symbol, command) so every verdict is
re-runnable. Task ids resolve against `tasks/done/` and `tasks/active.md`.

| Evidence | Adjudicated |
|---|---|
| every deliverable `present` **and** every task `done` | `complete` |
| some deliverables `present`, or tasks mixed/active | `active` |
| no deliverable `present` **and** no task started | `draft` |
| another plan declares `supersedes` it | `superseded` |
| **any probe `unknown`**, or no probeable deliverable declared | **`indeterminate`** (§6.3) |

**Mismatch = `adjudicated ≠ claimed`**, reported as a **confusion matrix**, never
as a bare rate. The matrix is what distinguishes the two error directions:

- *over-claim* — claims `complete`, deliverables absent;
- *stale under-claim* — claims `draft`/`active`, everything shipped. **This is the
  S1 §2.2 hypothesis**, and the cell that decides the ruling.

A plan claiming `draft` whose work genuinely has not started is a **match**. This
is precisely what the retracted §2.2 count could not see.

### 6.3 `indeterminate` is not a match

An `indeterminate` plan is **neither match nor mismatch**. It is **never silently
dropped** — dropping it would bias the estimate toward whichever direction the
probes happen to fail in.

**Primary analysis: Manski worst-case bounds.** Compute the mismatch rate twice —
once counting every `indeterminate` as a match (lower bound), once as a mismatch
(upper bound). If **both** bounds fall on the same side of θ, the gate resolves
and the indeterminates did not matter. If they straddle θ, the result is
**inconclusive by construction** — no amount of point-estimating rescues it.

This is what "do not interpret uncertainty as absence" means operationally: the
uncertainty is carried into the bound rather than assumed away.

**Secondary, reported but never gating:** the complete-case rate (indeterminates
excluded) and the **indeterminate rate itself**. An indeterminate rate **> 20%**
forces `inconclusive` **regardless of the bounds** — at that level the instrument,
not the corpus, is what was measured, and the response is better probes, not more
sampling.

### 6.4 Reliability: double-review everything

At n = 40 (§7) a 20% overlap yields a κ too imprecise to act on. **Every sampled
plan is independently double-adjudicated**; disagreements are resolved by a third
adjudication, recorded. Report Cohen's κ and the full confusion matrix
descriptively — they characterise the instrument; they do **not** gate.

This is cheaper than the reliability sub-study it replaces, and it removes the
question rather than estimating it.

## 7. The three-way gate

**Materiality θ = 0.10.** A **predeclared convention, not a derived optimum**: at
roughly 1 plan in 10 misrecorded, a rotation plausibly repays its cost; at 1 in
50 it does not. Fixed here so it cannot be tuned to the result.

**Ladder — three looks, Bonferroni α = 0.05/3 ≈ 0.0167 one-sided each**, joint
≥95%. Clopper–Pearson (exact, boundary-valid: it retains uncertainty after zero
observed errors, which a bootstrap cannot — every resample of all-matches returns
1.0). Thresholds **derived, not chosen**:

| Look | n | rule out (drift < θ) | demonstrate (drift > θ) |
|---|---|---|---|
| 1 | **40** | k = 0 | k ≥ 9 |
| 2 | **80** | k ≤ 2 | k ≥ 15 |
| 3 | **264** | census — compare observed rate to θ directly |

`k` = mismatches. Anything between the two columns → next rung.

**Why the ladder starts at 40, not 30.** At α = 0.0167, the smallest n whose
zero-error upper bound clears θ is **39** (upper = 0.0997). **At n = 29, ruling
out is impossible at any k** — an unreachable branch, the same trap as
natural-systems' n = 20–21 band where even total agreement failed. Verified by
computation, not assumed.

**Stopping rule.** Exactly the three looks above, predeclared. *Expand-until-
conclusive* is optional stopping and inflates error; the Bonferroni adjustment is
what buys the three looks. **Rung 3 is a census**, so the ladder terminates: at
n = N the rate is observed exactly, the interval is degenerate, and no fourth look
exists. If the census itself lands within noise of θ, the honest report is
*"drift is approximately θ"* — which S1 must then rule on as a judgment, not as a
measurement.

**Finite-population correction.** N = 264 is closed and enumerable, so
hypergeometric bounds are admissible and materially tighten rung 2. **Predeclare
the choice before drawing**, never after seeing the draw.

## 8. Deliverables

1. The **pre-registration record** (§4), committed and hashed before adjudication.
2. The **probe harness** — reusable, since S2/S3 need the same probes. Reuse the
   natural-systems design's §5.1/§5.2 probe and rollup semantics rather than
   re-deriving them.
3. The **adjudication set**: per plan, `{doc_id, pinned_commit, source_sha256,
   deliverables[], task_refs[], adjudicated, claimed, verdict}`.
4. The **result**: confusion matrix, Manski bounds, indeterminate rate, κ, the
   realised `π_h`, and any unsampled strata.
5. A **ruling applied to S1** — retain, withdraw, or expand.

## 9. Risks

| Risk | Mitigation |
|---|---|
| **Adjudicator anchors on the claimed status** | §6.1 — blinded; frontmatter stripped; comparison is mechanical and after the fact |
| **Uncertainty read as absence** | §6.3 — Manski bounds carry indeterminates into the estimate; >20% indeterminate forces `inconclusive` regardless of bounds |
| **Indeterminates silently dropped** | §6.3 — complete-case rate is secondary and never gates |
| **Ruling out is unreachable at the chosen n** | §7 — thresholds derived; n = 29 proven impossible at α = 0.0167; ladder starts at 40 |
| **Optional stopping inflates error** | §7 — exactly three predeclared looks, Bonferroni-adjusted; census terminates the ladder |
| **Thresholds tuned to the result** | §4 — θ, α, ladder, rubric all fixed and hashed before the first read |
| **mm's dirty Dropbox tree moves mid-draw** | §3 — commit/stash, re-pin, re-verify sha immediately before the draw; probes resolve against the pin |
| **Circularity: roster ratified before its evidence** | Sequencing ruled in the header — `plan` only; other kinds ratified afterwards |
| **"No drift" branch quietly unreachable** | §2 — withdrawing S1 §5 is a first-class outcome with stated consequences for S2/S3 |
| Rare strata forced to n_h = 1 | §5 — no forced minimums; unsampled strata reported; singletons censused or collapsed by a rule declared before the draw |
| S4 vocabulary drift contaminates strata | §5 — the eleven illegal statuses collapse into one `illegal-vocabulary` stratum; S4 is a separate spec |
| Loose `doc/plans` smuggled into the population | §3 — `plan` entities only; loose docs are S3's population, not this one |

## 10. Non-goals

- **Ratifying the `correspondence` roster.** Explicitly after, not before (header).
- **Curating, fixing, or restatusing any plan.** This measures; it does not act.
  No plan's `status` is edited as a result of adjudication.
- **Measuring loose `doc/plans`.** §3.
- **Resolving the status vocabulary** (S4) — §5 collapses it into one stratum.
- **Extending to other kinds.** `plan` only.

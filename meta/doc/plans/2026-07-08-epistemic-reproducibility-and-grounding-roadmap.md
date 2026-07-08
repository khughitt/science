# Epistemic Reproducibility & Grounding Roadmap

> **Status:** Active design note / roadmap (Science/meta). Durable spine for a
> multi-phase program that closes the gaps between what the Science framing
> *aspires to* ("reproducible, data-driven, calibrated") and what it currently
> *structurally enforces*. Motivated by a 2026-07-08 review of the overall
> framing (`docs/user-guide/big-picture.md`, `hypothesis:0007-working-model`)
> plus two K.H. framing ideas (reproducibility validation; benchmarks as
> grounding).
>
> This note is the narrative + phasing spine. Concrete work is tracked as the
> `reproducibility-validation` and `benchmark-grounding` task groups (Phase 1)
> and the Phase-2 follow-ups below. New unknowns are `question:0016`,
> `question:0017`, `question:0018`; `question:0008` is extended in place.

## Why this program

The framing is coherent and its strongest commitments are real, not slogans:
authored files are the sole source of truth with everything derived; the belief
policy is explicit, versioned, and structural (ordinal aggregation, independence
reduction, refutation caps, authored-only and dataset-QA ceilings); the working
model is a federated patchwork rather than one monolithic graph. Those are the
right bets and this program does not restructure them.

The program targets five gaps where enforcement or evidence lags the framing:

1. **"Reproducible" outruns enforcement.** Knowledge-*graph* rebuild is rigorously
   reproducible (source content-hashing, deterministic TriG, bundle integrity).
   But an empirical evidence line's *claim* is never forced to resolve to a
   reproducible analysis run: `EvidencePayloadCore.source_commit` is optional and
   not wired into `validate`; dataset `DerivationBlock.git_commit` is a bare
   string that accepts `""`, is caller-supplied not captured, and there is no
   environment digest or seed anywhere. The creed says "believe nothing until we
   re-analyze the data ourselves," but the substrate does not yet make an
   empirical belief carry the fingerprint that lets someone else re-run it.
2. **Annotator calibration is not in the belief math.** The ordinal magnitude is
   driven by authored `strength` / `independence` / `independence_group`, which
   are increasingly assigned by LLM agents. `expert_judgment` has a confidence
   gate and ceiling, but empirical lines' strength/independence are taken at face
   value regardless of whether a calibrated human or an agent assigned them. The
   agent-fallibility problem is already well analyzed (`question:0008`,
   `task:t033`, the `evidence_payload` hooks); the residual gap is *wiring a
   calibration discount into the belief-update surface*.
3. **The central calibration claim (H02) is unmeasured.** "Rich evidence payloads
   improve calibration" is the empirical proposition that justifies the apparatus
   over a flat scalar baseline. `hypothesis:0002` itself says support is
   literature/architectural, not benchmark-based; the rich-vs-flat harness has
   not been built or run. The reusable pieces exist (a Brier/ground-truth scoring
   loop in `h01_simulator`, schema validators in `t034_validator` /
   `evidence_payload.py`) but have never been combined into a calibration
   comparison.
4. **Ontology expressiveness may outrun authoring discipline.** The vocabulary is
   large and the docs repeatedly warn "do not fill these performatively" — an
   admission of the failure mode. Every optional field an agent can fill is a
   place for plausible-but-hollow signal. Needs a standing "is this field
   consumed?" audit and continued core/extension discipline.
5. **Ordinal vs. continuous boundary is implicit.** The toolkit treats log-odds as
   an optional projection over ordinal belief (`epistemic-model.md`); meta D-003
   asserts operational beliefs are continuous probabilities bounded away from
   0/1. Both are reasonable; the boundary should be made load-bearing rather than
   left to drift.

## The unifying insight

Gaps 1–3 are not three unrelated builds. They are **three applications of one
pattern the framework already has working: a QA verdict that becomes a belief
input.** The dataset-QA ceiling already caps belief on a structural verdict over
a *resource*.

- **Reproducibility validation** (idea #1) applies that pattern to *runs*: a
  reproduction verdict (`unverified` / `self-consistent` / `independently-reproduced`
  / `failed`) acts as a ceiling.
- **Benchmark grounding** (idea #2) applies it to the *whole representation*: an
  external scoring surface that says whether belief tracks reality over time.

So none of this needs a new architectural primitive — it reuses a validated one.

Second connection: **benchmarks are the measurement substrate that unblocks two
gaps at once.** The H02 bakeoff (gap 3) needs external ground truth — benchmarks
are it. Annotator calibration (gap 2) cannot be *estimated* without ground truth
either — once predictions can be scored, an annotator's `strong` assignments can
be shown to verify at some rate, and that rate becomes the discount. Hence the
sequencing: reproducibility contract + benchmark substrate are the enabling
layer; calibration-discounting and the H02 bakeoff are what they unlock.

## Idea #1 — validate reproducibility, not just represent it

Distinct from `question:0013` / `task:t040`, which represent reproducibility
*claims* as typed evaluation artifacts. This idea is about *actively verifying*
reproducibility and feeding the verdict into belief.

- **Static tier (cheap, first):** a reproducibility lint over pipeline plans —
  flag stochastic steps with no declared seed, unpinned environments, uncaptured
  code SHA. Nearly free; catches the most common silent irreproducibility. The
  current pipeline guidance covers QA checks but does not stress-test
  reproducibility this way.
- **Dynamic tier:** a reproduction run — rerun a workflow twice and compare
  outputs. For computationally expensive workflows, a **seeded subsample** gives a
  smaller job that still indicates reproducibility (a reproduction smoke test).
- **Verdict as ceiling:** the reproduction verdict is tracked at the entity level
  (run / dataset / evidence) and caps belief, mirroring the dataset-QA ceiling.
- **Contract:** a first-class analysis-run reproducibility record (code SHA,
  environment digest, input-data content hashes, parameters, seed policy, output
  hashes) that belief-eligible empirical evidence must transitively resolve to.
  Phase it warn-only → eligibility gate so existing projects do not break on day
  one.

## Idea #2 — benchmarks as grounding

Intuition: if we are building useful representations of the world, we should be
able to *predict* things against them with increasing accuracy. A portfolio of
numerous, diverse, relevant benchmarks (or dataset collections used as
benchmarks) provides the **metrics** to evaluate representations and to watch how
knowledge changes over time.

- Furnishes the external ground truth H02 needs; generalizes to a
  calibration-over-time metric for the whole representation.
- Also lets the continuous belief projection (D-003) be genuinely *calibrated*
  against benchmark outcomes rather than being a bare monotone transform of the
  ordinal — connecting to gap 5.

**Caution the skepticism creed demands — leakage and Goodhart:**

- **Leakage / contamination:** if a paper's claim is simultaneously our evidence
  *and* our benchmark ground truth, the measurement is contaminated. Benchmarks
  used to tune the belief policy must be **disjoint** from those used to evaluate
  it. Treat "benchmark used for grounding" as a first-class provenance fact so
  leakage is *detectable*, not merely discouraged.
- **Goodhart:** the moment a benchmark becomes a target it stops measuring. Use a
  rotating / held-out grounding set; separate tune-benchmarks from
  eval-benchmarks.

## Phasing

**Phase 1 (leads) — enabling layer.** Chosen focus: reproducibility validation
+ benchmark grounding, because they unlock gaps 2 and 3.

- `reproducibility-validation` group: run-reproducibility contract; static repro
  lint; dynamic reproduction check (incl. seeded subsample); reproduction verdict
  as belief ceiling.
- `benchmark-grounding` group: benchmark portfolio as first-class grounding with
  leakage provenance; calibration-over-time metric; **run the H02 rich-vs-flat
  bakeoff** (the milestone that converts H02 from a bet into a measurement).

**Phase 2 (sequenced after) — consume the enabling layer.**

- Wire annotator calibration into the belief-update surface as a discount, with
  profiles estimated from benchmark ground truth (extends `task:t033` /
  `question:0008`).
- Standing inert-field audit + norm-to-check conversion (extends `task:t030`;
  start conversions as visibility warnings unless they affect belief
  eligibility).
- Make the ordinal↔continuous boundary load-bearing (ordinal as durable evidence
  state; continuous as calibrated decision/attention projection; ties to D-003
  and `question:0009`).

## What this builds on (do not duplicate)

- `question:0013` / `task:t040` — reproducibility *representation* schema (this
  program adds *validation* + ceiling on top).
- `question:0004` — source/pipeline provenance (the run contract extends it).
- `question:0008` / `task:t033` — LLM agents as fallible sources (extended in
  place for the belief-math wiring).
- `hypothesis:0002` / `question:0002` — rich-payload calibration (the bakeoff
  operationalizes it).
- `task:t068` — cross-project reference syntax (the federation-enforcement gap;
  tracked separately, not in scope here).
- `task:t030` — authoring-cost audit (the schema-hygiene follow-up extends it).

## Open questions minted with this roadmap

- `question:0016` — actively validate reproducibility; when a reproduction
  verdict should cap belief.
- `question:0017` — benchmark/dataset portfolios as external grounding, with
  leakage and Goodhart controls, and calibration-over-time.
- `question:0018` — the load-bearing boundary between ordinal evidence state and
  continuous calibrated belief.

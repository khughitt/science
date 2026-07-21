# Statistics Router Reconciliation — Design

**Date:** 2026-07-21
**Status:** Accepted
**Phase:** 4, slice 1 (of the phase-4 hub-conformance umbrella)
**Worktree/branch:** `.worktrees/skills-phase4` / `skills-phase4`

## Problem

`skills/statistics/SKILL.md` is the last remaining *route-and-teach hub* whose
teaching bulk is a 14-item **Principles** section. Two things are wrong with it
after the phase-3 reorg:

1. **It violates the router doctrine the corpus already adopted.**
   `skills/meta/skill-authoring.md` states the target invariant (lines 42–44,
   58): *"A document that routes and teaches is a hub; its teaching content is
   extracted into typed leaves before it is a true router. Routers contain
   navigation only; substantive methodology lives in typed leaves."* The
   sibling `skills/study-design/SKILL.md`, built in phase 3, already embodies
   this: a routing table with **no** principle prose.

2. **8 of its 14 principles teach leaves it no longer owns.** Phase 3 split the
   overloaded `statistics/` into `statistics/` (6 modeling `method-guide`
   leaves) and `study-design/` (8 `analysis-discipline` leaves). The Principles
   section was not updated: principles 1–6, 12, 14 still teach the eight
   `study-design/` leaves, which `study-design/SKILL.md` now routes to. So the
   statistics hub teaches methodology for another hub's leaves.

The current `statistics/SKILL.md` (153 lines) also carries a `When to invoke`
prose block (lines 123–143) that mixes statistics-modeling triggers with
study-design triggers (pre-registration, reviewing a pre-reg, resolving
sensitivity passes, deciding a bias correction), compounding the same overlap.

## Principle → leaf mapping (the reconciliation table)

| # | Principle (statistics/SKILL.md) | Target leaf | Owning hub | Disposition |
|---|---|---|---|---|
| 1 | Lock parameters by measurement | `study-design/replicate-count-justification.md` | study-design | **delete** (fold routing into study-design, already present) |
| 2 | Bias vs variance | `study-design/bias-vs-variance-decomposition.md` | study-design | **delete** |
| 3 | Pre-commit sensitivity arbitration | `study-design/sensitivity-arbitration.md` | study-design | **delete** |
| 4 | Power floor | `study-design/power-floor-acknowledgement.md` | study-design | **delete** |
| 5 | Pre-reg amendment vs fresh | `study-design/prereg-amendment-vs-fresh.md` | study-design | **delete** |
| 6 | Defensive instrumentation | `study-design/prereg-defensive-instrumentation.md` | study-design | **delete** |
| 7 | Model the independent unit | `statistics/survival-and-hierarchical-models.md` | statistics | **fold** into Leaves table |
| 8 | Compositional constraints | `statistics/compositional-data.md` | statistics | **fold** |
| 9 | Well-posed likelihood comparison | `statistics/likelihood-model-comparison.md` | statistics | **fold** |
| 10 | Drift before selection | `statistics/population-genetics-likelihood.md` | statistics | **fold** |
| 11 | Repeated time rows dependent | `statistics/time-series-and-longitudinal-models.md` | statistics | **fold** |
| 12 | Estimator self-report ≠ evidence | `study-design/estimator-certification.md` | study-design | **delete** |
| 13 | Bayesian gated sequence | `statistics/bayesian-workflow.md` | statistics | **fold** |
| 14 | Identification is a DAG question | `study-design/causal-identification.md` | study-design | **delete** |

Result: **6 fold** (own leaves) + **8 delete** (foreign leaves already routed
by study-design).

## Chosen approach: delete-to-conformance (Approach A)

Rewrite `statistics/SKILL.md` as a **pure router in the same section skeleton as
`study-design/SKILL.md`**. The two become sibling routers with one shared form.

Approaches considered and rejected:

- **B — move the 8 principles into `study-design/SKILL.md` as a Principles
  section.** Rejected: re-introduces methodology-in-router, the exact
  anti-pattern `study-design/SKILL.md` was built to avoid. The thesis of each
  moved principle already lives in its leaf.
- **C — trim in place to a 14-line one-liner digest.** Rejected: still
  routes-and-teaches and still teaches foreign leaves; only half-fixes the
  incoherence and leaves `statistics` off-doctrine.

### Target `statistics/SKILL.md` skeleton

Mirror `study-design/SKILL.md`:

1. **Frontmatter** — `name: statistics`, `provenance: internal`, and a
   `description` trimmed to the six modeling leaves (see *Description
   reconciliation* below).
2. Title + a one-sentence router doctrine line
   (*"A router carries no methodology; teaching content belongs in a typed
   leaf."*), consistent with `study-design/SKILL.md:9`.
3. **Routing trigger** — load when a finite-sample model is being *fit,
   compared, or reviewed* (as distinct from a rigor commitment / verdict
   certification, which routes to `study-design`).
4. **Scope boundary** — covers model fitting/comparison across the six modeling
   families; **excludes** pre-registration, replicate/power justification,
   estimator certification, sensitivity arbitration, causal identification, and
   bias/variance reasoning (see `../study-design/SKILL.md`). This is the exact
   mirror of `study-design/SKILL.md:16–20`.
5. **Leaves** — a table with `Leaf | Load when | Do not load when` for the six
   modeling leaves, matching `study-design/SKILL.md`'s three-column form. The
   six folded principles supply the `Load when` / `Do not load when` content.
6. **Decision / compose order** — leaves are independent; several may apply.
7. **Parent & neighbors** — parent `../INDEX.md`; neighboring router
   `../study-design/SKILL.md` (currently statistics does **not** list
   study-design as a neighbor — this closes the asymmetry, since
   `study-design/SKILL.md:43` already lists statistics).
8. **Success test** — a modeling task routes to the correct leaf with no
   methodology read from the router.
9. **Companion Skills** — retain the genuinely cross-hub companions
   (`literature`, `epistemics`, `writing`, `data-management`); these are
   navigation, not methodology.

The `When to invoke` prose block is removed; its statistics-modeling content is
absorbed by the Routing trigger + Leaves table, and its study-design content is
already covered by `study-design/SKILL.md`.

### Description reconciliation

The current `statistics` `description` is a keyword list dominated by
study-design terms (bootstrap, permutation, Monte Carlo, downsampling, MCMC,
power, bias-vs-variance, sensitivity arbitration, defensive instrumentation,
pre-registered). For a router those keywords misroute discovery **to**
statistics.

- Trim `statistics` `description` to the six modeling leaves (survival /
  hierarchical / mixed-effects, compositional, time-series/longitudinal,
  likelihood-model comparison, population-genetics likelihood, Bayesian
  workflow).
- **Migrate** the pre-registration / power / sensitivity / bias-variance /
  estimator-certification / causal-identification keywords into
  `study-design/SKILL.md`'s `description`, so routing coverage for those terms
  moves to the hub that owns them rather than being dropped. This is a
  one-line edit to a single frontmatter field; the study-design router body is
  untouched.

## Safety / honesty checks (built into the plan)

- **No anchor deep-links.** A repo grep confirms nothing links to
  `statistics/SKILL.md#principles` or `#when-to-invoke`; all inbound refs are
  file-level. Deleting the Principles / When-to-invoke sections breaks no link.
- **Thesis-survives check (certify mapping vs data).** For each of the 8
  deleted foreign principles, confirm the target `study-design/` leaf carries
  the principle's thesis *before* deleting the digest. All 8 leaves exist
  (91–425 lines). This is the classification-honesty discipline: reorganize,
  do not silently drop content.
- **Inbound file refs unchanged.** The eleven file-level inbound references to
  `statistics/SKILL.md` (from `INDEX.md`, `bio/`, `ml/`, `writing/`,
  `pipelines/`, `data-management/`, `study-design/`) all point at the file, not
  a section, and remain valid.

## Required companion edits

1. **`skills/meta/skill-authoring.md:44`** — the router invariant names the four
   remaining hubs and states "4 of 14". After this slice, statistics is a true
   router: update the count to **3 of 14** and drop `statistics/SKILL.md` from
   the hub list (leaving `data-management/SKILL.md`, `bio/transcriptomics/SKILL.md`,
   `pipelines/SKILL.md`). Note: `pipelines/SKILL.md` remains listed there and is
   a separate phase-4 slice — this design does not touch it.
2. **Regenerate the codex mirror.** Any `skills/` edit (including `skills/meta/`)
   requires regenerating `codex-skills/` or
   `test_committed_codex_skills_match_fresh_generation` fails.

## Out of scope

- The other phase-4 slices (data-management extraction, transcriptomics
  extraction, mutational-signatures split, and the pipelines question) — each
  is its own spec → plan → execution cycle.
- No new leaf files are created or renamed in this slice; the six statistics
  modeling leaves and eight study-design leaves are untouched on disk.

## Validation

From `science/`:

- `uv run --frozen science skills lint --root ../skills` — PASS.
- `uv run --frozen pytest -k codex` (committed-mirror test) — PASS after regen.
- `uv run --frozen pytest` — full suite green.
- Manual: `statistics/SKILL.md` and `study-design/SKILL.md` render as two
  routers of identical section skeleton; no numbered Principles list remains in
  `statistics/SKILL.md`.

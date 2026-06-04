# Epistemic drift detection: claim-vs-operationalization — design

**Date:** 2026-06-04
**Status:** Proposed
**Scope:** `science` tool (model, validation, graph attention) + a new entity-type-agnostic `review` skill + a downstream authoring convention (`operationalized_by:`)
**Anchor question:** `science-meta:question:15-claim-operationalization-drift`

> Paths are relative to the repo root (`~/d/science`, canonically
> `/mnt/ssd/Dropbox/science`). The tool lives under `science/src/science_tool/`
> and the model under `science/model/src/science_model/`.

## Problem

A real failure in the `multiple-myeloma` project surfaced a class of drift the framework
does not catch. Hypothesis H2 ("cytogenetic subtypes are distinct disease entities") was
`supported` / high-confidence and used as a top organizing model, yet:

1. Its prose claimed "cytogenetic subtypes" broadly, while the pipeline operationalized only
   **7** events (`constants.py::EVENTS`) and was analytically load-bearing on **2**
   (gain(1q), hyperdiploidy). The statement out-ran the implementation and then sat still.
2. A paper note (`doc/papers/Lu2025.md`) and a project decision (`core/decisions.md` D5)
   asserted the pipeline "covers" del(1p) and t(14;20) — a coverage claim the authoritative
   code manifest flatly contradicted. The D5 panel count was "9/11" when the true figure was
   "7/11"; it double-counted the two missing events.
3. Questions that flagged the missing high-risk subtypes (`q01`, `q06`, `q35`, `q38`) existed
   but were only weakly bound to the theme and never reshaped H2's claims.

None of these were caught by existing machinery, and each is a distinct failure mode.

### The three failure modes

- **A — Scope/operationalization drift.** Stated scope exceeds what is actually
  measured/operationalized. The entity stays "fresh" because nothing upstream changed; it was
  over-scoped at birth.
- **B — Prose-vs-implementation drift.** Prose asserts a fact about what the code/pipeline does
  that an authoritative manifest contradicts.
- **C — Weakly-bound / under-attended questions.** Questions that bear on an entity accumulate
  open/parked without ever being folded into its claims — *semantic* under-attention, not
  structural disconnection.

### Why the current engine misses them

- **Freshness is event- and horizon-driven.** It fires when an upstream `bears_on` source
  changed, or when `review_horizon_days` elapses. An entity that was over-scoped from the start
  and never touched is `fresh`. High confidence actively signals the opposite of "look here."
- **Orphan detection is structural.** `no_outbound_links`, unresolved refs, and `graph validate`
  orphaned nodes catch *disconnection*. The H2 gap-flagging questions were *connected*; the miss
  was that connection ≠ scope pressure.
- **No check inspects prose-vs-code.** `graph diff` checks prose↔graph sync. Nothing checks a
  prose coverage claim against a code manifest.

## What already exists (build on, don't rebuild)

- `review_state.last_reviewed`, `review_state.last_review_note`, `review_state.review_horizon_days`
  — parsed and validated (`science/model/src/science_model/entities.py:127`,
  `frontmatter.py:256`). **The review-state field you might think to add already exists.**
- A freshness engine emitting `fresh`/`stale`/`needs-review` with `bears_on` upstream
  propagation and `triggeredBy`/`upstreamChangeAt` provenance
  (`science/src/science_tool/graph/freshness.py:289`).
- Attention weighting that boosts `needs-review` (3×) and `stale` (2×), with a
  never-reviewed-in-365-days floor (`science/src/science_tool/graph/attention.py:19`), already
  consumed by `curate`, `next-steps`, `wander`.
- `EntityClass` separating EPISTEMIC / OPERATIONAL / REFERENCE
  (`entities.py:111`) — so review machinery can be entity-type-agnostic.
- A validate check registry with a decorator/section pattern
  (`science/src/science_tool/validate/checks/__init__.py:63`) — adding a check is cheap.

So the missing pieces are narrow: (i) **nobody populates `review_state`**, (ii) **no skill
performs the review**, and (iii) **no checks exist for failure modes A and B**.

## Goals / Non-goals

**Goals**
- Detect failure modes A, B, C — mechanically where possible, agentically for the residue.
- Be entity-type-agnostic from the start (hypotheses, propositions, interpretations, decisions,
  reports), with type-specific rubrics.
- Reuse the existing review-state + freshness + attention substrate.
- Avoid review-theater (timestamp bumps with no scrutiny) and horizon busywork.

**Non-goals**
- Not replacing `bias-audit`, `discuss`, or `dag-audit` — this composes with them.
- Not mandating `operationalized_by:` on every entity — it is opt-in for entities making scoped
  empirical claims.
- Not a live graph query service — batch/materialized is sufficient.

## Proposed mechanisms

### 1. Operationalization-coverage check (static; targets A + B) — highest leverage

Let scoped empirical entities optionally declare what operationalizes them:

```yaml
operationalized_by:
  - manifest: cytogenetics:EVENTS      # an enumerable source of truth in code/config
    claims_scope: ["gain_1q", "hyperdiploid", "del_17p", "t_4_14",
                   "t_11_14", "t_14_16", "myc_r"]
```

A new `validate` check (`checks/operationalization.py`) then:

- Resolves the named manifest from code/config (a small adapter per manifest kind — e.g. parse
  a Python `Final[list[str]]`, a YAML key, a datapackage resource list).
- **Fails** when prose coverage assertions (`covers X`, `operationalizes X`, "n/m panel")
  reference items absent from the manifest (mode B), using a lightweight claim-extraction pass
  over the entity body + linked decision/paper notes.
- **Warns** when the declared `claims_scope` is narrower than the entity's prose scope language,
  prompting a scope qualification (mode A).

This is deterministic and would have failed the build on both the D5 "9/11" miscount and the
Lu2025 "covers del(1p)" claim. Start with an explicit allowlist of manifest adapters; expand as
needed.

### 2. Open-question-debt attention term (graph; targets C) — would have caught H2

Add a term to `compute_attention_candidates` (`graph/attention.py`): for each epistemic entity,
compute **open-question debt** = a function of (count of `bears_on` questions with
`status ∈ {open, active, proposed, parked}`, their age, and whether any have been incorporated —
heuristic: question post-dates the entity's last `updated`). Surface it in `next-steps`/`status`
as "entities carrying the most unincorporated questions." H2 would have ranked at the top.

No new storage — it is a query over existing `bears_on` edges + question `status`.

### 3. Generalized `review` skill + review-state population (agentic; targets A residue)

One entity-type-agnostic skill (`codex-skills/science-review/`) that:

- Selects targets from the attention ranking (top-k overdue/indebted), runnable in parallel per
  entity (mirrors `big-picture`'s per-hypothesis fan-out).
- Applies a **type-specific rubric**:
  - *hypothesis*: scope vs operationalization; leaky/overstated language; falsifiability still
    crisp; confidence justified by current evidence.
  - *proposition*: claim layer + identification still accurate; evidence stance current.
  - *interpretation*: do conclusions still match the cited evidence and effect sizes?
  - *decision*: still in force? contradicted by code or a later decision?
  - *report*: do headline claims still match the entities they summarize?
- **Writes guarded `review_state`**: a review must emit a concrete artifact — a finding, a
  prose diff, a created task, or an explicit reasoned "no change" — before `last_reviewed` is
  set. A bare timestamp bump is disallowed by the skill's own checklist (the `dag-audit`/`curate`
  ledger discipline).

## Prioritization model

Do not lean on time horizons alone. Rank review priority by the conjunction that names the blind
spot:

```
priority ≈ w1·needs_review + w2·stale + w3·open_question_debt
         + w4·(status == supported && confidence high && last_reviewed old)
```

The last term is the "settled-looking but heavily caveated and overdue" signal — the same
instinct `bias-audit` encodes as "too settled," made quantitative.

## Tradeoffs and risks

- **Authoring cost** (`operationalized_by:`, agentic review) — see
  `question:04-authoring-cost-audit`. Mitigate by opt-in scope and attention-driven targeting.
- **Review-theater** — mitigate with the artifact-required guard.
- **Manifest-adapter brittleness** — start with a tiny allowlist (Python list constant, YAML key,
  datapackage resources); fail closed (warn, don't hard-error) on unparseable manifests.
- **Claim-extraction false positives** in the coverage check — keep mode-A as a *warning* and
  mode-B (manifest contradiction) as the only hard failure, since B is unambiguous.

## Staged rollout

1. **M1 (smallest thing that would have prevented this):** open-question-debt attention term
   (mechanism 2) + a minimal `review` skill (mechanism 3) writing guarded `review_state`. Use
   `multiple-myeloma` H2 as a regression fixture.
2. **M2:** operationalization-coverage check (mechanism 1), mode-B (manifest contradiction)
   first, with a Python-constant and YAML-key adapter.
3. **M3:** mode-A scope-language warning + per-kind rubrics fleshed out + horizon backstop for
   `supported`/high-confidence entities.

## Open questions

- Tracked in `science-meta:question:15-claim-operationalization-drift`.
- How much of the real drift landscape is mechanically detectable vs needs agentic review?
  (Parallels `question:05-source-dependence-detection`.)
- Should `operationalized_by:` be a first-class model field or an annotation? (Model field if it
  is to gate validation.)
- Relationship to `question:14-adaptive-project-topology`: that question asks how topology should
  *adapt* to evidence/uncertainty/decay; this design is the *detection* half — the signals that
  should drive such adaptation.

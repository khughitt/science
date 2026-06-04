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

- **Freshness fires only on `bears_on`, and `bears_on` comes only from *typed* edges.**
  `derive_bears_on_from_typed_edges` (`graph/freshness.py:70`) derives `bears_on` from
  `sci:tests`, `cito:supports`, `cito:disputes`, `sci:grounds`, `sci:synthesizes`,
  `sci:hasProposition`, `sci:hasParticipant`, plus chain/pre-reg/provenance/code derivers. A
  plain `related:` edge produces **no** `bears_on`. The needs-review test then only inspects
  `bears_on` sources whose `updated`/`created` post-dates the target baseline
  (`freshness.py:352`).
- **The H2 fixture had no `bears_on`-producing edge at all.** The gap-flagging questions
  (`q01`/`q06`/`q35`/`q38`) were not even in H2's `related:` list — a task (t2431) merely
  *proposed* to "bulk-bind" them. So there was nothing upstream to change, and freshness
  correctly stayed silent. Even had they been `related:`, that edge type is invisible to
  `bears_on`. **Freshness is working as designed; the scope debt simply lives below the
  `bears_on` layer.** This is the load-bearing fact the rest of the plan must respect: a debt
  metric that queries `bears_on` would inherit the exact blind spot it is meant to fix.
- **Even properly-typed scoping questions only fire once, on creation.** A question that
  *did* type a `tests`/scoping edge to H2 would trigger `needs-review` when created (its
  `created` post-dates H2's baseline), then go quiet after the next review bumps H2's
  `last_reviewed` — without anything forcing the *claims* to actually narrow. Freshness flags
  "look here once"; it does not track "this question is still unincorporated."
- **Orphan detection is structural.** `no_outbound_links`, unresolved refs, and `graph validate`
  orphaned nodes catch *disconnection*. The miss here was *semantic under-attention* of
  related-or-weaker links, not disconnection.
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

- A working `science entity review <ref> [--note]` command that already mutates
  `review_state.last_reviewed` (and optional `last_review_note`), preserving other review-state
  fields (`science/src/science_tool/entity_review.py:39`, `cli.py:494`).

So the missing pieces are narrow and **not** "population from scratch": (i) the existing
`entity review` command **permits a bare timestamp bump** (the note is optional and no artifact
is required), so M1 is to *harden/wrap* it into artifact-guarded review rather than build a new
populator; (ii) **no skill performs the actual scrutiny** that should precede the bump; and
(iii) **no checks exist for failure modes A and B**.

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

A new `validate` check (`checks/operationalization.py`) then splits cleanly by claim
structuredness, because only structured claims are deterministic enough to hard-fail a build:

- Resolves the named manifest from code/config (a small adapter per manifest kind — e.g. parse
  a Python `Final[list[str]]`, a YAML key, a datapackage resource list). Fail *closed* (warn,
  skip) when a manifest is unparseable rather than hard-erroring.
- **HARD-FAIL only on structured claims.** The structured `claims_scope:` list (and any future
  structured `coverage_claims:` syntax) is compared set-wise against the resolved manifest; a
  declared item absent from the manifest is an unambiguous contradiction (mode B) → build
  failure. This is genuinely deterministic — no NLP.
- **WARN on free prose.** A lightweight pass over the entity body and linked paper/decision notes
  for assertions like `covers X` / `operationalizes X` / "n/m panel" is heuristic and *cannot*
  be deterministic without a constrained claim grammar, so it only ever emits warnings (mode B
  prose + mode A scope-language-exceeds-`claims_scope`). It nudges authors to either qualify the
  prose or promote the claim into structured `claims_scope`.

Honest scope on the H2 fixture: a hard-fail would have fired **only if** D5/H2 had declared a
structured `claims_scope` (e.g. listing del(1p)/t(14;20) as covered) contradicting
`cytogenetics:EVENTS`. The actual Lu2025/D5 errors were free prose, so they would have surfaced
as *warnings*, not build failures — still caught, but the determinism claim must not be
oversold. The structured path is what gates the build; the prose path is an advisory net. Start
with an explicit allowlist of manifest adapters; expand as needed.

### 2. Open-question-debt attention term (graph; targets C) — would have caught H2

**Crucial design constraint (from finding 1): this term must NOT query `bears_on`.** The whole
failure is that scoping questions sit on `related:` edges or weaker (or are unlinked), which
never become `bears_on`. A debt metric over `bears_on` would reproduce the freshness blind spot.

Add a term to `compute_attention_candidates` (`graph/attention.py`) that operates over the
**broader connectivity layer**: for each epistemic entity, compute **open-question debt** from

- questions linked via `related:` (either direction), **plus**
- questions sharing a `theme`/`tag`/`group` with the entity (theme co-membership), to catch the
  H2 case where the questions were not even on H2's `related:` list;

weighted by question age and an "unincorporated" heuristic (question `created`/`updated`
post-dates the entity's last `last_reviewed`). Count only **debt statuses** — using the
canonical question vocabulary (`entities.py:97`): `active`, `partially-answered`, and
`deferred`. Exclude `answered` and `retired` (resolved) — they are not debt.

Surface in `next-steps`/`status` as "entities carrying the most unincorporated questions." H2
would have ranked at the top via theme co-membership even with zero `related:` edges.

No new storage — it is a query over existing `related:` edges, theme/tag membership, and
question `status`.

**Complementary authoring fix.** Encourage a *typed* question→entity relation (e.g. a
`scopes`/`refines`/`tests` predicate) for scoping questions, so that properly-typed ones also
enter the `bears_on` freshness engine and fire `needs-review` on creation. The debt term is the
backstop for the under-typed/unlinked majority; typing is the upgrade path for the ones that
earn it. (Whether to add a new scoping predicate to the `bears_on` deriver is itself an open
design question — see Open questions.)

### 3. Generalized `review` skill + review-state population (agentic; targets A residue)

One entity-type-agnostic skill (`codex-skills/science-review/`) that:

- Selects targets from the attention ranking (top-k overdue/indebted), runnable in parallel per
  entity (mirrors `big-picture`'s per-hypothesis fan-out).
- Applies a **type-specific rubric**:
  - *hypothesis*: scope vs operationalization; leaky/overstated language; falsifiability still
    crisp; confidence justified by current evidence.
  - *proposition*: claim layer + identification still accurate; evidence stance current.
  - *interpretation*: do conclusions still match the cited evidence and effect sizes?
  - *report*: do headline claims still match the entities they summarize?
  - *decision*: still in force? contradicted by code or a later decision? **Caveat:**
    `decision` is **not** a registered entity kind (`_CORE_KIND_CLASSES`,
    `graph/entity_registry.py:50`) — decisions live as parsed `##` sections in
    `core/decisions.md`, not as frontmatter entities with their own `review_state`. So
    decisions are *out of scope for entity-level review in M1*. Bringing them in requires a
    deliberate choice (Open questions): either (a) register a `decision` entity kind and migrate
    `core/decisions.md` to per-decision frontmatter, or (b) build a separate section-level review
    ledger keyed by decision heading. Do not assume entity-review machinery applies to them.
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
- **Claim-extraction false positives** in the coverage check — hard-fail is reserved for
  *structured* `claims_scope` contradictions (unambiguous, set-wise); all free-prose extraction
  (mode A scope-language and mode B prose assertions) is warning-only. See mechanism 1.

## Staged rollout

1. **M1 (smallest thing that would have prevented this):** open-question-debt attention term
   (mechanism 2, over `related:`/theme membership — explicitly **not** `bears_on`) + **harden the
   existing `science entity review` command** (mechanism 3) so it refuses a bare timestamp bump
   without a recorded artifact, and add the per-kind rubric to the backing skill. This is a
   wrap/hardening of `entity_review.py` + `cli.py`'s `entity review`, not a new populator. Use
   `multiple-myeloma` H2 (related-only/unlinked scoping questions; over-scoped supported
   hypothesis) as the regression fixture.
2. **M2:** operationalization-coverage check (mechanism 1) — structured `claims_scope` hard-fail
   first, with a Python-constant and YAML-key manifest adapter; free-prose warnings second.
3. **M3:** per-kind rubrics fleshed out + horizon backstop for "settled" entities (e.g.
   hypothesis `supported`/`partially-supported`) + decision-review path (register a `decision`
   kind *or* a section-level ledger; see Open questions) + optional typed scoping predicate.

## Open questions

- Tracked in `science-meta:question:15-claim-operationalization-drift`.
- How much of the real drift landscape is mechanically detectable vs needs agentic review?
  (Parallels `question:05-source-dependence-detection`.)
- Should `operationalized_by:` / `claims_scope:` be first-class model fields or annotations?
  (Model fields if they are to gate validation.)
- **Should a typed scoping predicate (`scopes`/`refines`) be added to the `bears_on` deriver?**
  Doing so would route properly-typed scoping questions into the freshness engine — but widening
  `bears_on` has propagation/attention side effects that need their own review.
- **How should decisions enter review?** Register a `decision` entity kind + migrate
  `core/decisions.md` to per-decision frontmatter, or build a section-level review ledger? The
  former unifies machinery; the latter avoids a migration. (Finding 4.)
- Relationship to `question:14-adaptive-project-topology`: that question asks how topology should
  *adapt* to evidence/uncertainty/decay; this design is the *detection* half — the signals that
  should drive such adaptation.

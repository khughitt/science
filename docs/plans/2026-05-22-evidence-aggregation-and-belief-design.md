# Independence-Aware Evidence Aggregation, Derived Belief, and Evidence QA

**Date**: 2026-05-22
**Status**: Draft
**Revision**: 2026-05-22c — representation fork settled: a first-class `evidence-line`
entity is the **single canonical shape** for all counted evidence; the alternative
"lightweight annotated relation" path is rejected (a dual shape breeds silent mismatch).
2026-05-22b incorporated a code-verified review — five corrections: the durable-authoring
prerequisite (was missing), the edge-vs-entity metadata split (was overstated), refutation
scope (Simeonov-style criticism must not hard-cap), the `shared-source` grouping key, and
the real `belief_state` enum.
**Origin**: Surfaced from a `cancer-evolution` review session (h006/h012). Wiring a
genuine dispute (Yang2022 supports vs. Simeonov2021 disputes the h012 plasticity-burst
cycle) exposed that the project carried evidence polarity only in prose, and that even
where signed edges exist, the framework aggregates them by counting — independence and
strength are stored but never used. This generalizes well beyond that one project.

## Problem

Science already has a strong, partly-implemented evidence layer:

- **Signed edges exist** — `cito:supports` / `cito:disputes` (SPAR CiTO), authored via
  `science graph add evidence <src> <tgt> --stance {supports,disputes}
  --strength {strong,moderate,weak} --independence {independent,shared-source,circular}
  --method ... --caveats ...`.
- **Some metadata is captured** — but split across two levels (see below).

Two structural gaps make aggregation impossible today:

1. **The annotated edge is ephemeral.** `graph add evidence` writes the reified edge
   *directly into `graph.trig`* and warns it "will be wiped on the next `science graph
   build`" (cli.py:1886). The recommended durable path — authoring the relation in a
   source file — currently materializes only a **bare triple**
   (`graph.add((subject, predicate, object))`, materialize.py:622) with **no edge
   annotations**. So you can have *durable but unannotated* edges, or *annotated but
   ephemeral* ones, never both. **There is no durable, annotated evidence-edge
   representation.** This is the prerequisite the rest of the design depends on.

2. **Metadata is split edge vs. entity, and aggregation ignores both.**
   - *Edge/statement-level* (only on the ephemeral CLI path, reified as an `RDF.Statement`,
     store.py:809): `sci:evidenceStrength`, `sci:evidenceCaveats`, `sci:evidenceMethod`,
     `sci:evidenceIndependence` (`{independent, shared-source, circular}`).
   - *Entity/proposition-level* (durable, materialize.py:771 `_add_reasoning_metadata`):
     `sci:claimLayer`, `sci:identificationStrength`, `sci:proxyDirectness`,
     `sci:supportsScope`, `sci:independenceGroup`, `sci:evidenceRole`, and
     `measurement_model`.
   - The rollup is just `support_count` / `dispute_count` (store.py:3613 `_belief_state`).
     `strength`, `independence`, `independence_group`, `evidence_type`, `evidence_role` are
     stored and surfaced in the bundle but **never combined**. Ten reviews citing one
     primary dataset count as ten.

3. **`belief_weight` / `influence_weight` are placeholders** — hardcoded `None` in
   `format_attention_candidate` (attention.py:250–251) for *every* project.

The intuition to honor: *aggregating multiple independent sources should reduce the chance
that one poor dataset or analysis skews the conclusion.* Belief should be a **robust,
independence-aware** function of evidence, never a popularity count, and never a source of
false precision.

## What already exists (so we extend, not reinvent)

Present and correct; this design does **not** touch them:

- Signed `cito:supports` / `cito:disputes`.
- The proposition metadata listed above, plus `rival_model_packet`
  (`current_working_model` / `alternative_models` / `shared_observables` /
  `discriminating_predictions` / `adjudication_rule`).
- `bears_on` derivation + transitive closure (unsigned dependency layer, distinct from
  support/dispute) and freshness (`sci:freshnessState`, `sci:triggeredBy`).
- The **proposed-but-deferred** graph-resident `sci:Posterior` (beta/HDI/probSign/fitTask)
  and `sci:edgeStatus` (`supported`/`tentative`/`structural`/`unknown`/`eliminated`),
  authoritative today only in the DAG/YAML layer (`dag/schema.py:PosteriorBlock`).
- Reproducibility primitives: `content_hash` audit cache, `DETECTOR_VERSIONS`, commons
  resource hashes (`sha256:` + `bytes`, `DataIntegrityError` on mismatch), deterministic
  materialization.

Existing **non-goals** we respect: no fully calibrated Bayesian engine; `sci:Posterior` is
Bayesian-shaped, not frequentist-CI; no merged cross-project graph.

## Goals

- **Prerequisite first**: a durable, annotated evidence representation (§Prerequisite),
  without which aggregation has nothing reproducible to read.
- Replace count-based rollup with **independence-aware aggregation** consuming `stance`,
  `strength`, `independence` + `independence_group`, `evidence_type`, `evidence_role`,
  and a new `dispute_scope`.
- Produce a **transparent evidence ledger** as the primary artifact and an **ordinal
  belief state** as the headline; any scalar is a derived, sensitivity-tested convenience.
- Make **decisive refutation non-averageable** — but scope it correctly (§rule 3), so an
  *interpretive* or *generalization-scoped* criticism does not masquerade as a data-level
  refutation.
- Encode multi-source robustness: belief rises with **independent** concordant lines
  (diminishing returns); a single line caps below the top of the ladder.
- Ship **QA / sanity checks** that fail loud on each failure mode.
- Keep everything **derived and reproducible** from pinned inputs.

## Non-goals

- No calibrated probabilities or invented priors. The quantitative scalar is **opt-in per
  project via `core/decisions.md`** (mirrors the precedent that a `disputed` edge-status is
  left to projects); the **ordinal ledger and belief_state are framework-wide**.
- No federated/cross-project belief. Belief is per-project; the same shared paper
  legitimately carries different stances in different projects.
- No automated truth/contradiction *resolution*; we surface contestation, we do not settle it.

## Prerequisite: a first-class `evidence-line` entity (the one canonical shape)

Aggregation needs every counted evidence line to be **durable** (survives `graph build`)
and **annotated at the line level**. The canonical representation is a **first-class
`evidence-line` entity** — and deliberately the *only* aggregated shape. A second,
"lightweight" annotated path (e.g. inline reified authored relations) is **rejected**: a
dual representation forces every validator, ledger query, migration, and reproducibility
check to reason over two equivalent shapes, which is the next inevitable source of silent
mismatch. One graph model; authoring UX may have shortcuts.

**The model:**

- Add an `evidence-line` **entity kind**.
- An `evidence-line` is the **subject** of `cito:supports` / `cito:disputes`; its object is
  the proposition (or finding/interpretation) it bears on. This resolves the edge-vs-entity
  split cleanly — all the per-line metadata lives on the line entity, not split across edge
  vs. proposition.
- It stores: `stance`, `strength`, `independence`, `independence_group`, `evidence_role`,
  `dispute_scope`, the observability fields (`shared_dataset` / `shared_lab` /
  `shared_platform` / `shared_cohort`), an optional `measurement_model`, and a reference to
  its source (`paper:` / `dataset:` / `data-package:`).
- Because it is an entity, each line gets a content hash, review state, and provenance —
  exactly what the ledger, reproducibility, append-only history, and calibration backtest
  need.

**Background material that is not ready to count** stays as `source_refs` / `related` /
`bears_on`, or is marked `unassessed` — it is **not** demoted into a weaker second evidence
path. Counting requires an `evidence-line`.

**Authoring UX (shortcuts, not a second model).** `evidence-line` need not mean one
markdown file per line forever. Authoring can start as a compact YAML source or a nested
evidence block on the proposition that **materializes into first-class `evidence-line`
entities**. The graph shape is singular; the ergonomics are layered on top.

**Until this lands, the pilot cannot be authored durably** — `graph add evidence` is
ephemeral and cannot even express `evidence_role`/`dispute_scope`. This is why Phase 0 is a
hard prerequisite.

## Design

### 1. The evidence ledger (primary artifact, framework-wide)

For a proposition `P`, collect its incoming `cito:supports` / `cito:disputes` evidence
lines and group by **independence unit** (the `independence_group`):

```
P: <claim text>
  FOR  (independent units: 3)
    [unit g1] empirical_data · direct_test · strong    (Yang2022)
    [unit g2] simulation     · proxy_support · moderate (ModelX)
    [unit g3] literature      · background_constraint · weak (ReviewY)
  AGAINST (independent units: 1)
    [unit g4] empirical_data · model_criticism · strong · scope=generalization (Simeonov2021)
  EXCLUDED / FLAGGED
    circular: 1 (ReviewZ cites Yang2022; group g1)     ← not counted
    shared-source: collapsed 2→1 within g1
```

The ledger is what humans read; everything below derives from it.

### 2. Independence-aware aggregation rules

1. **Collapse non-independent lines.** Lines sharing an `independence_group`, or tagged
   `shared-source`, collapse to one effective unit (keep the strongest; prefer
   `empirical_data_evidence`). `circular` lines are **excluded** and flagged.
   **`shared-source` and `circular` both require an `independence_group`** — without a
   group key, "collapse to what?" is undefined (QA #2b enforces this).
2. **Weight ordinally by quality.** Per-unit weight from (`evidence_type` × `evidence_role`
   × `strength`), with the *ordering* fixed and the *numbers* in config (conservative
   defaults): `empirical_data` > `benchmark`/`simulation` > `literature` > `expert_judgment`;
   `direct_test` > `proxy_support` > `background_constraint`. `negative_control` (supports
   *validity*, not the claim) and `model_criticism` (meta) are **separate ledger rows**, not
   summed into the FOR/AGAINST mass.
3. **Scoped refutation precedence (corrected).** Only an **independent, `strong`,
   `direct_test` dispute with `dispute_scope = whole_claim`** caps `belief_state` at
   `contested` and makes the claim eligible for `sci:edgeStatus = eliminated`. Disputes that
   are `model_criticism`, or scoped to `generalization` / `mechanism` / `boundary`, **down-weight
   and narrow** the claim (and may force a scope qualifier on the proposition) but **do not
   eliminate** it. *This is the Simeonov2021 case: its own proposition says the single
   endpoint "cannot observe the plasticity-burst phase" and is "interpretive tension, not a
   data-level refutation," so it is an independent strong `model_criticism` / generalization-
   scoped dispute — not a direct-test refutation. Encoding it as the latter would wrongly
   hard-cap h012.*
4. **Multi-source robustness.** Belief is a saturating function of the count of
   *independent* concordant units (diminishing returns; the 5th corroboration adds little,
   no single unit dominates). One unit, however strong, caps below the top of the ladder.
   Report **dispersion** across units; high dispersion downgrades confidence even with a
   positive central tendency (robust/trimmed combination). This is the direct encoding of
   "one poor dataset shouldn't skew the result."
5. **Proxy gate.** Units with `proxy_directness ∈ {indirect, derived}` and no
   `measurement_model` cannot contribute at full weight (promotes the existing migration
   warning to a belief-blocking condition for the quantitative scalar).

### 3. Belief-state ladder (enum migration — corrected)

The code already emits five values (store.py:3613): `speculative`, `fragile`, `supported`,
`well_supported`, `contested`. We **keep these, not invent `established`**, and define the
canonical ordinal ladder + an orthogonal contestation flag:

```
ordinal magnitude:  speculative < fragile < supported < well_supported
orthogonal flag:    contested   (coexisting unresolved supports + disputes)
```

- `speculative` — no supporting units.
- `fragile` — supported by a single independence unit (the single-source ceiling).
- `supported` — ≥2 independent units, none `direct_test`, or mixed quality.
- `well_supported` — ≥2 independent units including ≥1 `direct_test`, no unresolved
  whole-claim refutation.
- `contested` — set whenever an unresolved dispute mass is non-trivial; **displayed
  alongside** the magnitude (a claim can be `well_supported` *and* `contested`), so
  contestation is never hidden by the magnitude. Migration: re-derive all five from the new
  rules; the count-based `_belief_state` is replaced, not extended.

### 4. Derived scalars (opt-in display)

- **`belief_weight`** fills the placeholder as a **pair** `(support_mass, dispute_mass)`
  plus a derived net in `[-1, 1]`. **Never a bare net** — a bare net collapses
  high-support/high-dispute (genuinely contested) and low-evidence/neutral (genuinely
  unknown) to the same value, which is actively misleading. Display is opt-in per project.
- **`influence_weight`** stays distinct from belief — structural reach (downstream
  dependents via `bears_on` closure + `cross_impact` scope), not evidential support.

### 5. Edge status & posteriors

Land the already-designed `sci:edgeStatus` from YAML into the graph; aggregation sets it
(`eliminated` via rule 3, else `supported`/`tentative`). Where a project authored a
quantitative `sci:Posterior`, the ledger shows it as that unit's effect estimate; belief
never *requires* a posterior.

## QA / sanity checks

Each is a `science health` / `validate` rule, hygiene-tiered, fail-loud:

1. **`evidence.unstanced`** — a source linked to a claim with no `cito:` stance; require an
   explicit stance or `unassessed` (never infer support).
2. **`independence.suspect-circular`** — two units tagged `independent` that share a
   citation ancestor, dataset, lab, platform, or cohort; plus any `circular` line a summary
   counts. The single highest-value check.
2b. **`independence.ungrouped-collapse`** — a `shared-source` or `circular` line missing an
   `independence_group` (collapse target undefined).
3. **`belief.refutation-masked`** — magnitude ≥ `supported` while an independent strong
   `direct_test` whole-claim dispute is unresolved (violates rule 3). Note: a
   `model_criticism`/scoped dispute does **not** trip this — it sets `contested` instead.
4. **`belief.inflated`** — prose/summary confidence exceeding the independent-unit ceiling
   (e.g. `well_supported` from one unit).
5. **`belief.single-source-ceiling`** — magnitude above `fragile` from a single
   `independence_group`.
6. **`evidence.proxy-ungated`** — `indirect`/`derived` proxy contributing at full weight
   without a `measurement_model`.
7. **`belief.fragile-single-line`** (leave-one-out) — recompute dropping each independent
   unit; if removing any one flips `belief_state`, flag it. The direct encoding of the "one
   poor dataset skews things" risk.
8. **`belief.nonreproducible`** (golden test) — belief recomputes byte-identically from the
   same pinned input hashes.
9. **`evidence.strength-implausible`** — `strength = strong` on `expert_judgment` or
   `background_constraint`.
10. **`belief.calibration-backtest`** (long-horizon) — when a claim is later
    `superseded`/resolved, log whether the prior belief was directionally right; emit a
    deliberately-humble periodic summary (directional, not a calibration curve).

## Risks & limitations

- **Garbage-in.** Belief is only as good as authored `stance` / `strength` / `independence`
  / `dispute_scope`. *Mitigation*: QA #1/#2, LLM-proposes / human-ratifies, conservative
  defaults, `unassessed` as a loud first-class value.
- **Authoring cost & the prerequisite.** The `evidence-line` entity kind is real new
  schema + materializer work and adds per-line authoring burden. *Mitigation*: compact
  nested-block / YAML authoring that materializes into entities; assisted authoring;
  background material stays as `bears_on` / `unassessed` rather than being forced into lines.
- **False precision.** *Mitigation*: ledger-first; ordinal headline framework-wide; scalar
  opt-in, a pair not a net, shown only with sensitivity; no invented priors.
- **Over-capping by mis-scoped disputes.** The original draft would have let Simeonov-style
  criticism eliminate h012. *Mitigation*: rule 3 restricts the hard cap to `direct_test`
  whole-claim disputes; `dispute_scope` carries the rest.
- **Averaging hides decisive refutation.** *Mitigation*: rule 3 + QA #3.
- **Consensus entrenchment.** Many concordant non-independent lines manufacture false
  confidence. *Mitigation*: independence collapse, dispersion reporting, rival packets.
- **Independence is coarse and partly subjective.** `{independent, shared-source, circular}`
  ignores partial correlation (same lab/platform/cohort). *Mitigation (steer)*: add
  **observability fields before math** — see Decisions.
- **Gaming / HARKing.** *Mitigation*: pre-registration linkage, append-only belief history.
- **Weak low-N calibration.** The backtest is directional only; stated, not implied as
  calibrated.

## Reproducibility

- Belief is a **derived view** materialized from durable annotated edges; never hand-set,
  always recomputable.
- Each belief snapshot records its **input-hash set** (contributing line/source
  `content_hash`es + config version), so staleness is detectable like the audit ledger and
  a rebuild on identical inputs is byte-identical (QA #8).
- Snapshots are **append-only** with an as-of date (mirroring `sci:Posterior` refit
  history): the *belief trajectory* is auditable.

## Federation note

No federated belief (existing non-goal). Cross-project sharing stays content propagation
(`doc/sync/`, `sync_source:`). A shared paper with `supports` in one project and `disputes`
in another is **legitimate divergence, not drift** — surfaced, not reconciled.

## Decisions (from review steer)

- **Quantitative scalar — opt-in per project** via `core/decisions.md`. Ordinal ledger and
  `belief_state` are framework-wide; the `(support_mass, dispute_mass)` pair + net display
  is opt-in.
- **Graded independence — defer correlation math.** First add **observability**: require
  `independence_group`, and add optional `shared_dataset`, `shared_lab`, `shared_platform`,
  `shared_cohort` on the evidence line/group. Observability before math; correlation
  factors only once we can see the overlaps.
- **`belief_weight` — pair + derived net** (confirmed). A bare net is misleading because
  high/high and low/neutral collapse to the same value.

## Roadmap

- **Phase 0 — `evidence-line` entity kind (PREREQUISITE).** Add the entity kind + the
  `cito:supports`/`cito:disputes` relation with `evidence-line` as subject; line-level
  `stance`/`strength`/`independence`/`independence_group`/`evidence_role`/`dispute_scope` +
  observability fields + optional `measurement_model` + source ref; materializer emits the
  line node, its cito edge, and its metadata durably; compact nested-block authoring
  shortcut. Ship structural QA #1, #2, #2b, #9 (no aggregation yet).
- **Phase 1 — pilot + independence-aware aggregation → `belief_state`.** Re-author the
  cancer-evolution h012↔Simeonov2021 line durably as an independent strong `model_criticism`
  / generalization-scoped dispute; implement §2/§3; add QA #3, #4, #5, #6.
- **Phase 2 — derived scalar + sensitivity.** `belief_weight` (pair + net), leave-one-out
  (#7), golden reproducibility (#8), append-only snapshots.
- **Phase 3 — graph-resident `sci:edgeStatus` / `sci:Posterior`** (land the deferred
  YAML→graph migration) and connect to belief.
- **Phase 4 — calibration backtest (#10)** and optional pgmpy CPDs from posteriors.

## Open questions

- Authoring shortcut shape — nested evidence block on the proposition vs. a compact
  `evidence-lines.yaml` source; both must materialize into identical `evidence-line`
  entities (the graph shape is fixed; only the ergonomics are open).
- Exact ordinal weights for `evidence_type` × `evidence_role` × `strength` — config-driven;
  needs a pilot across a biology and a non-biology project.
- Diminishing-returns curve shape and the single-unit cap threshold.
- Exact `dispute_scope` vocabulary (`whole_claim` / `generalization` / `mechanism` /
  `boundary` proposed) and how a scoped dispute rewrites the proposition's scope qualifier.
- Whether `negative_control` / `model_criticism` rows ever feed the magnitude or stay
  purely diagnostic.

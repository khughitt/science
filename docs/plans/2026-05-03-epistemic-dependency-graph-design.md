# Epistemic Dependency Graph & Continuous Belief Flow — Design Sketch

**Status.** Design sketch. Companion to `2026-05-03-typed-entity-blockers-design.md`. The two specs cover orthogonal halves of the project's dependency model:

| Spec | Direction | Question it answers |
|---|---|---|
| Typed entity blockers | Forward (operational) | "Why can't this task proceed?" |
| **This spec** | Backward (epistemic) | "When upstream X changes, what beliefs/workflows downstream should be revisited?" |

Phase 1 is the structural piece (taxonomy + inverse edges + freshness state). Phase 2 is the behavioral piece (weighted sampling for attention) and is intentionally deferred behind tracked tasks so it isn't lost.

### Anchoring in existing decisions

This sketch is *not* introducing a new philosophical commitment to continuous belief. The meta-project already established that commitment in:

- **`meta/core/decisions.md` D-003** — "Operational beliefs are continuous in (0, 1), never 0 or 100%." Decisions that need a binary choice are computed *from* the continuous belief at the decision point, not by collapsing the representation. D-003 is already load-bearing for H01.
- **`meta/specs/hypotheses/h01-stochastic-revisiting.md`** — the project has a hypothesis (and a completed simulator validating it via `[t001]`/`[t001b]`/`[t002]`) that down-weighted-but-still-revisited propositions outperform hard-gating under noisy evidence. The simulator confirmed the effect; phase-2 weighted sampling here is the operationalization of that finding at the entity-graph layer.

What this sketch adds is the *structural surface* the existing commitments need: an entity taxonomy that distinguishes which entities can carry continuous belief, and an inverse-dependency edge type that lets evidence movement propagate. Without those, D-003 lives only in tool-internal decision code and never reaches the knowledge graph, and H01's validated mechanism has nowhere to attach.

---

## Motivation

The project today is good at building "research plumbing" — hypotheses connected to questions connected to datasets connected to workflow-runs connected to interpretations. It has weak points in two related places:

1. **Hard gating creates brittleness.** Pre-registrations and verdict-style interpretations function as binary valves. A false-negative result on one experiment can shut a research pathway indefinitely, with no structural mechanism to surface it again when later evidence shifts. This contradicts the project's own multi-line-of-evidence philosophy (`docs/claim-and-evidence-model.md`): no single experiment should accept or reject a claim, but the tooling has no way to express "mostly closed but reopen-able."

2. **Upstream changes don't propagate.** The current edge vocabulary (`supports`, `disputes`, `addresses`, `tests`, `feeds_into`, `grounded_by`, `produced_by` — see `science_model/profiles/core.py`) describes static relationships. None of them carry forward-in-time semantics: "if I change this dataset, what hypotheses should I re-examine?" When a new paper lands or a derived dataset is recomputed, downstream entities silently drift out of sync with their evidence base. The knowledge graph is stable when it should be living.

The two problems share a root: the project lacks an explicit notion of **epistemic dependency** — which entities' belief-state depends on which other entities' state — separate from the operational dependency model that typed-entity-blockers formalizes.

### Motivating cases

- **Cancer/myeloma.** A pre-registered analysis returned null. The hypothesis effectively went dormant. Six months later, a new dataset lands that would have moved the needle on the same proposition — but nothing in the project surfaces the connection, and the dormant hypothesis stays dormant.
- **Natural-systems.** A foundational paper is added to the bibliography. It bears on three hypotheses indirectly. There is no inverse edge from "this paper's claims" to "hypotheses whose evidence base this paper informs," so the connection is made (or missed) by whichever sweep happens to read both files.
- **Derived dataset re-run.** A workflow-run is re-executed with corrected parameters. Several interpretations were grounded in the prior run's output. Today there is no "needs review" signal on those interpretations.

---

## Architecture

### Part 1 — Entity taxonomy: epistemic vs operational

The current `EntityType` enum (`science_model/entities.py:24-60`) lists 30+ types as a flat namespace. They split along an axis the model doesn't currently make explicit:

**Epistemic entities** — entities whose meaning is a *belief* with associated uncertainty. State changes when new evidence lands.

- `hypothesis`, `question`, `proposition`, `observation`, `finding`, `interpretation`, `discussion`, `story`, `mechanism`, `model`, `assumption`, `report`, `validation-report`

**Operational entities** — entities whose meaning is a *thing in the world* or *thing produced by the project*. State changes when an action completes.

- `task`, `dataset`, `workflow`, `workflow-run`, `workflow-step`, `data-package`, `research-package`, `experiment`, `method`, `transformation`, `paper` (as artifact), `search`, `spec`, `plan`, `curation-sweep`

**Reference entities** — entities that name external things and rarely change.

- `concept`, `topic`, `variable`, `article`, `inquiry`, `canonical_parameter`, `unknown`, plus all `DomainEntity` subclasses

**Edge-case rulings (decided here, not deferred).**

- `observation` is **epistemic** despite being "anchored to data." An observation is a *claim* ("the data says X"); when the underlying data is recomputed or replaced, the observation's standing can change. Treating it as epistemic lets `bears_on` flow through to it.
- `paper` is **operational** in the artifact sense (a paper-as-output the project produces). `article` is **reference** (a bibliographic record of someone else's paper). The naming overlap is unfortunate but not load-bearing here.
- `mechanism` is **epistemic** — it's a structured proposition bundle, not a reference object — even though its `participants` field points at domain/reference entities.
- `assumption` and `model` are **epistemic**. A model whose load-bearing assumptions get disputed should surface as needs-review.

Refinements remain cheap because the classification is data on each registered kind, not hardcoded into branching logic.

**Why the distinction is load-bearing.**

- **Continuous-belief framing applies only to epistemic entities.** A dataset's `availability` is binary (it's released or it isn't). A hypothesis's standing is not. Trying to put both in the same continuous frame creates exactly the false precision the proposal is meant to avoid.
- **Pre-registration semantics shift.** A pre-reg over an *operational* claim ("we will run pipeline P with params X before looking at results") stays binary and gating — that's its whole point. A pre-reg over an *epistemic* claim ("if we observe Y we will treat hypothesis H as supported") becomes evidence input to H's standing, not a verdict on H. This rescues the rigor benefit of pre-registration without committing to the brittle gating behavior.
- **Inverse dependency edges only need to terminate at epistemic entities.** Operational entities are updated by running their producing process; reference entities by external curation. Only epistemic entities have a meaningful "needs review" state.

**Implementation surface — taxonomy lives at the registry layer, not the profile manifest.**

Originally I proposed adding `entity_class` to `EntityKind` in `science_model/profiles/schema.py`. That's wrong: `CORE_PROFILE.entity_kinds` (`science_model/profiles/core.py:9-106`) only declares 16 kinds, while `EntityRegistry.with_core_types()` (`science-tool/src/science_tool/graph/entity_registry.py:42-88`) registers 30+ — covering `dataset`, `article`, `report`, `validation-report`, `plan`, `spec`, `assumption`, `transformation`, `variable`, `search`, `curation-sweep`, etc. Putting the classification on the manifest would silently leave half the kinds unclassified, and any freshness check gated on classification would fall through to "unknown."

Place classification at the **registry layer**, where every core kind is enumerated:

```python
# science_model/entities.py — new enum
class EntityClass(StrEnum):
    EPISTEMIC = "epistemic"
    OPERATIONAL = "operational"
    REFERENCE = "reference"


# science-tool/src/science_tool/graph/entity_registry.py
class EntityRegistry:
    def __init__(self) -> None:
        # … existing fields …
        self._kind_class: dict[str, EntityClass] = {}

    def register_core_kind(
        self, kind: str, cls: type[Entity], *, entity_class: EntityClass
    ) -> None:
        # … existing checks …
        self._core[kind] = cls
        self._kind_class[kind] = entity_class

    def kind_class(self, kind: str) -> EntityClass:
        ...
```

Update `with_core_types()` so every `register_core_kind` call carries an `entity_class=...` argument. The classification list is the canonical taxonomy — adding a new kind without a classification is a registration-time error.

Profile/extension/catalog kinds also pass `entity_class`. The default for unknown extension kinds is `OPERATIONAL` (conservative: extensions don't get freshness propagation by default).

`EntityKind` in the manifest stays as-is for now; if the manifest layer eventually needs the classification, it reads it from the registry. (We keep one source of truth.)

### Part 2 — Inverse dependency edges: `bears_on`

A new relation kind expressing **forward-in-time epistemic dependency**:

```python
RelationKind(
    name="bears_on",
    predicate="sci:bearsOn",
    source_kinds=[],   # any kind — empty list = unrestricted, matching `has_participant`'s pattern
    target_kinds=["hypothesis", "question", "proposition", "observation",
                  "finding", "interpretation", "discussion", "story",
                  "mechanism", "model", "assumption", "report", "validation-report"],
    layer="layer/core",
    description=(
        "Source entity's state contributes to the evidence base of the target "
        "epistemic entity. Changes to the source should mark the target as "
        "needs-review. Direction is upstream→downstream (evidence → belief)."
    ),
),
```

Targets are exactly the epistemic kinds from Part 1's taxonomy; sources can be any kind. The validator (Part 4) enforces target-kind classification.

**Auto-derivation — actual edge mapping.**

The earlier draft of this section guessed at edges that don't exist in the core profile (`workflow-run tests proposition`, `paper supports hypothesis`, `dataset feeds_into workflow-run`, `workflow-run produces dataset`). Verifying against `science_model/profiles/core.py:108-252`, the real core relation vocabulary is:

| Existing edge | Source kinds | Target kinds |
|---|---|---|
| `tests` | task, experiment, workflow-run | hypothesis, question |
| `supports` / `disputes` | observation, proposition | proposition, hypothesis |
| `addresses` | question | proposition |
| `grounds` | workflow-run | observation |
| `grounded_by` | finding | data-package, workflow-run |
| `produced_by` | data-package | workflow-run |
| `executes` | workflow-run | workflow |
| `realizes` | workflow | method |
| `feeds_into` | workflow-step | workflow-step |
| `contains` | workflow, finding, interpretation, discussion | workflow-step, proposition, observation, finding |
| `synthesizes` | story | interpretation, discussion |
| `comprises` | paper | story |
| `organized_by` | story | question, hypothesis |
| `has_participant` / `has_proposition` | mechanism | (any) / proposition |
| `supersedes` | workflow-run | workflow-run |

Auto-derivation rules, expressed in those actual edges:

| Direct rule | Derived `bears_on` |
|---|---|
| `task|experiment|workflow-run` `tests` `H` | source `bears_on` H (epistemic target: hypothesis or question) |
| `observation|proposition` `supports|disputes` `T` | source `bears_on` T (signed → unsigned superset) |
| `workflow-run` `grounds` `observation` | workflow-run `bears_on` observation |
| `finding` `grounded_by` `workflow-run|data-package` | inverse: workflow-run / data-package `bears_on` finding |
| `data-package` `produced_by` `workflow-run` | (operational chain; provides transitive substrate, not direct `bears_on`) |
| `interpretation|discussion` `contains` `finding|observation|proposition` | inverse: finding/observation/proposition `bears_on` interpretation/discussion |
| `story` `synthesizes` `interpretation|discussion` | inverse: interpretation/discussion `bears_on` story |
| `mechanism` `has_proposition` `proposition` | inverse: proposition `bears_on` mechanism |
| `question` `addresses` `proposition` | (operational direction; `addresses` is question→proposition. No automatic `bears_on` — addresses signals "this question lives or dies on this proposition," not evidence flow.) |

Plus a separate **provenance-derived** rule:

| Provenance source | Derived `bears_on` |
|---|---|
| `entity.source_refs` / `entity.evidence_refs` (already materialized as `prov:wasDerivedFrom` triples in `science-tool/src/science_tool/graph/materialize.py:159,257-287`) | source-ref-target `bears_on` entity (only when entity's kind is epistemic) |

This is important: it's how a paper enters the dependency graph. The core profile has no `paper supports hypothesis` edge — paper-to-claim provenance flows through `source_refs`/`evidence_refs` and is materialized as PROV.wasDerivedFrom. The `bears_on` derivation reads those triples and emits explicit `bears_on` edges into epistemic entities.

**Transitive closure.** After direct + provenance derivation, walk the graph and propagate `bears_on` along chains:

```
workflow-run grounds observation
observation bears_on hypothesis     [direct from supports]
⇒ workflow-run bears_on hypothesis  [transitive]
```

Closure terminates at epistemic targets. The materialized graph stores the closure so freshness propagation is a single-hop lookup at runtime.

**Hand-authored `bears_on`.** Permitted for cases the auto-rules miss (e.g., a paper that contextualizes a hypothesis without a `supports`/`disputes` claim — a survey that reframes the question, an article in `source_refs` of a topic that itself bears on the hypothesis). Validator (Part 4) requires target to be an epistemic kind.

**Relationship to existing edges (clarified).**

- `supports` / `disputes`: signed; `bears_on` is the unsigned superset. Both kept — synthesis prose still wants the polarity.
- `grounded_by`: source-of-truth for finding-to-substrate provenance. The reverse direction *is* the `bears_on` derivation rule above; we don't add a new `grounded_by` over interpretations or stories. Propagation to interpretation/story flows via `contains` and `synthesizes`.
- `addresses`: deliberately not auto-derived. Question and proposition are conceptually linked but not in an evidence-flow sense.

**Cycle handling.** Even the actual edge graph has cycles through operational hops (workflow-run A's outputs feed a finding F, F is contained in interpretation I, I synthesized into story S, story tied back to a hypothesis whose later workflow-run is A's successor). Freshness propagation (Part 3) needs cycle protection identical to the typed-entity-blockers `ReadinessResolver`.

### Part 3 — Freshness state on epistemic entities

Two distinct things often get conflated under "freshness." Pulling them apart:

- **Reviewed-as-of timestamp** — durable, user-asserted fact. "I have looked at this entity in light of all evidence as of date X." Lives in entity frontmatter.
- **Currently-needs-review flag** — derived signal. Computed at graph-build time by comparing the reviewed-as-of timestamp against the most recent change timestamp of any upstream `bears_on` source.

The first is the source of truth that the user controls; the second is always re-derivable and lives in the materialized graph. Splitting them resolves the source-of-truth conflict and clarifies what each command does.

**Frontmatter (durable, per-entity).**

```python
class EpistemicReviewState(BaseModel):
    last_reviewed: date | None = None
    last_review_note: str = ""
    review_horizon_days: int | None = None   # optional per-entity stale threshold
```

Added to `ProjectEntity` and validated to be present only when the kind is epistemic. Defaults to `last_reviewed=None` (interpreted as "never explicitly reviewed since creation," which for the initial freshness baseline is treated as "fresh-as-of-`created`").

**Materialized (derived, recomputed at graph build).**

```python
class EpistemicFreshness(BaseModel):
    state: Literal["fresh", "needs-review", "stale"]
    triggered_by: list[str] = []  # entity refs whose change post-dates last_reviewed
    upstream_change_at: date | None = None
    reason: str = ""              # short, e.g. "dataset:foo modified 2026-05-01"
```

Stored only in the materialized graph — never in entity frontmatter. Re-derived from scratch on every `graph build`.

**Derivation rule.**

For each epistemic entity E:
1. Resolve `last_reviewed` from frontmatter (fall back to `created` if absent).
2. For each upstream `bears_on` source S (via the closed graph from Part 2), determine `most_recent_change(S)` — using the source entity's `updated` frontmatter date as the canonical change marker; content-hash comparison is a phase-2 refinement, not phase-1.
3. If any `most_recent_change(S) > last_reviewed`, E is `needs-review` and `triggered_by` lists those sources (capped at the top-N most recent).
4. Else if `now - last_reviewed > review_horizon_days` (when set), E is `stale`.
5. Else `fresh`.

**Commands and write boundaries.**

| Command | Reads | Writes |
|---|---|---|
| `graph build` (a.k.a. materialize) | entity frontmatter + previous graph | materialized graph only — no frontmatter mutation |
| `entity review <id>` | entity frontmatter | entity frontmatter (`last_reviewed`, `last_review_note`) |
| `entity needs-review` | materialized graph | (read-only) |
| `graph propagate-freshness` | entity frontmatter (computes derivation in memory) | (read-only by default) |
| `graph propagate-freshness --apply` | (deprecated — see below) | |

The `--apply` flag from the earlier draft is removed: there is nothing to apply, since the derived flag lives only in the materialized graph and is rewritten by `graph build`. `propagate-freshness` becomes a convenience read-only sweep that lists what `graph build` would compute, useful in CI / pre-commit hooks without doing a full materialize.

**Why three states, not two.** "Stale" captures attention rot independent of upstream change — a hypothesis nobody has looked at in a year is suspicious even if no edges fired. Defaulting `review_horizon_days` to unset (no stale state) avoids noise; projects that want it set it per-kind via `science.yaml` or per-entity in frontmatter.

**No automatic invalidation of conclusions.** Freshness is a *flag*, not a control-flow gate. An interpretation that's `needs-review` is still readable, citable, and usable in synthesis. The flag only affects (a) what `science:next-steps` and curation sweeps surface, and (b) how phase-2 weighted sampling weights attention.

### Part 4 — Pre-registration recast

Pre-registration today is implemented as `type: pre-registration` entities with `committed:` and `spec:` fields (see `2026-04-25-pre-registration-canonical-type.md`). The spec doesn't change; what changes is how the tool *interprets* the relationship between a pre-reg and the entity it pre-commits.

- A pre-reg over an **operational** target (e.g., "we will run analysis A with params P before unblinding") stays gating. The pre-reg's `committed:` date is the lock; deviations require a recorded amendment. No change.
- A pre-reg over an **epistemic** target (e.g., "if effect size > 0.3, treat hypothesis H as supported") becomes a `bears_on` source. When the analysis it commits to completes, the result feeds into H's evidence base via `bears_on`. The pre-reg's role is to *constrain interpretation in advance*, not to gate H's status. H's standing remains a function of accumulated evidence — pre-registered interpretations weigh more than post-hoc ones, but neither is a verdict.

This dissolves the "gate slammed shut on a viable pathway" problem without weakening pre-registration's anti-bias function. A null result against a pre-registered prediction is *evidence*, weighted by the pre-reg's commitment, but it's not a kill switch.

Practically, this is a documentation + skill change (`science:pre-register`, `science:interpret-results`) plus a pass over downstream projects' conventions. No schema change to pre-reg entities.

---

## Phase 2: Weighted sampling for attention

**Deferred and tracked.** Phase 2 turns the freshness flag into a behavior: when `science:next-steps`, `science:curate`, `science:big-picture`, or task-prioritization sweeps choose what to surface, they do **weighted random sampling** over candidates rather than deterministic top-N selection.

This phase operationalizes H01's simulator finding (`hypothesis:h01-stochastic-revisiting`, validated by `[t002]`) at the entity-graph layer: the simulator showed that exploration-based policies — including continued revisiting of down-weighted candidates — strictly beat hard-gating under noisy early evidence, with the gap widening as noise increases. The interpretation (`meta/doc/interpretations/h01-simulator-2026-04-24.md`) refined the load-bearing mechanism to "uncertainty-guided exploration" (UCB-style) rather than pure stochastic revisiting. Phase-2 weight design should respect that refinement: weights should be proxies for uncertainty / contestedness, not just for noise.

Sketch of the weight function (final form to be designed in phase 2):

```
weight(entity) ∝
    (1 + |bears_on incoming edges|)           # connectedness
  × (1 + days_since_last_review / 30)         # neglect / recency
  × needs_review_multiplier (1.0 | 3.0)       # explicit flag
  × evidence_imbalance (|supports| - |disputes| skew)  # contested entities surface more
  + ε                                          # noise floor — nothing goes to zero
```

**Crucial constraint.** Weights are derived from observable graph properties — edge counts, timestamps, status transitions — not from LLM-estimated probabilities. The proposal's continuous-belief framing is achieved through *attention behavior*, not by storing fake-precise posteriors on entities. An entity's standing remains qualitative ("supported", "contested", "dormant") in the data model; the *probability of being looked at on any given sweep* is what's continuous.

**ε floor is load-bearing.** It's the structural guarantee that "disproven" hypotheses can resurface. Without it, the system collapses back to deterministic gating. Default ε = 0.05 (every entity has a 5% baseline of being sampled regardless of weight); project-configurable.

Phase-2 design is **out of scope for this doc** but is tracked as a task so it isn't lost. See trajectory section.

---

## Validation, CLI, and graph-build integration

### `graph build` (a.k.a. materialize) extensions

`graph build` is wired in `science-tool/src/science_tool/cli.py:618` and drives `science-tool/src/science_tool/graph/materialize.py`. New steps land there:

- Derive `bears_on` triples from existing edges per the auto-derivation table.
- Walk `prov:wasDerivedFrom` triples (already emitted from `source_refs`/`evidence_refs` at `materialize.py:159,257-287`) and emit `bears_on` for any provenance edge whose target is an epistemic kind.
- Compute the transitive closure of `bears_on` across operational hops.
- For each epistemic entity, compute `EpistemicFreshness` per the derivation rule in Part 3 and write it into the materialized graph (only).

`graph build` does **not** mutate entity frontmatter. The split is enforced by code review, not just convention — `freshness.py` takes a graph object and a read-only entity store, and never the project root.

### `validate.sh` checks

- For every `bears_on` edge (hand-authored or derived), target kind must be classified `EPISTEMIC`. Reject otherwise.
- Freshness frontmatter shape (`last_reviewed`, `last_review_note`, `review_horizon_days`) validated when present, on epistemic-kind entities only.
- The earlier draft had a "validate `grounded_by` inverse `bears_on` is derivable" check — dropped, because the derivation is mechanical and the validator would just be re-running the deriver. Instead, validate that every `grounded_by` edge resolves at materialize time.

### New CLI commands

- `science-tool entity review <id>` — sets `last_reviewed = today`, optionally records `--note`. Idempotent.
- `science-tool entity needs-review` — lists all epistemic entities whose materialized state is `needs-review` or `stale`. Filterable by kind, age, project.
- `science-tool graph propagate-freshness` — read-only sweep that recomputes freshness in memory and prints a report, without writing the materialized graph. Useful in CI / pre-commit hooks. (No `--apply` flag — there is no separate write step; full materialization is `graph build`.)

### Display surface

- `science:status` and `science:next-steps` add a "Needs review" section sourced from the materialized freshness state.
- `science:big-picture` per-hypothesis files include freshness state in the header.
- No change to `tasks list` / `tasks show` — freshness is an entity property, not a task property.

---

## Migration

**Schema.** All new fields default to backward-compatible values (`entity_class` derived from kind via the manifest; `freshness.state="fresh"` if absent). Existing entities continue to validate without edits.

**Data.** No automatic rewrite. The first `graph build` after this lands will populate `bears_on` triples and an initial freshness baseline (everything starts `fresh` if `last_reviewed`/`created` provides a baseline; `needs-review` otherwise). Projects mid-migration can set `freshness.enabled: false` in `science.yaml` to skip freshness emission while still benefiting from `bears_on`.

**Skills.** `science:pre-register`, `science:interpret-results`, `science:next-steps`, `science:curate`, `science:big-picture`, and `science:status` need updates to consume the new field. Tracked as a follow-up sweep.

---

## Testing strategy

Three layers, mirroring typed-entity-blockers' structure.

### 1. `science-model` unit tests
- `EntityClass` enum values and serialization.
- `EpistemicReviewState` model validates date parsing; rejects negative `review_horizon_days`.
- `bears_on` `RelationKind` declared with epistemic-only `target_kinds`.

### 2. `science-tool` registry + graph + freshness tests
- `register_core_kind` requires `entity_class`; missing arg is a registration error.
- `with_core_types()` populates classification for every registered kind (test asserts complete coverage of the registry's hard-coded kind list).
- `kind_class("hypothesis") == EPISTEMIC`; `kind_class("dataset") == OPERATIONAL`; `kind_class("article") == REFERENCE`.
- Auto-derivation typed-edge rules:
  - `workflow-run tests hypothesis` → `workflow-run bears_on hypothesis`.
  - `observation supports proposition` → `observation bears_on proposition`.
  - `finding grounded_by workflow-run` → inverse `workflow-run bears_on finding`.
  - `interpretation contains finding` → inverse `finding bears_on interpretation`.
  - `story synthesizes interpretation` → inverse `interpretation bears_on story`.
- Auto-derivation provenance rule: an `article` in `source_refs` of a hypothesis emits `bears_on` (via the existing PROV.wasDerivedFrom triple).
- Auto-derivation does not emit `bears_on` for operational targets (`workflow-run bears_on dataset` would be a bug).
- Transitive closure: `workflow-run grounds observation` + `observation supports hypothesis` → derived `workflow-run bears_on hypothesis`.
- Cycle protection: pathological cycle through operational hops terminates without infinite loop.
- Freshness derivation:
  - Entity with `last_reviewed` post-dating all upstream `updated` dates → `fresh`.
  - Upstream `updated` post-dating `last_reviewed` → `needs-review` with that source in `triggered_by`.
  - `last_reviewed` absent → falls back to `created` for the comparison.
  - `review_horizon_days` set and exceeded with no upstream change → `stale`.
- `graph build` does not mutate any entity frontmatter (assert by file-mtime equality before/after).
- `entity review` updates `last_reviewed` and `last_review_note` on the target frontmatter only.

### 3. CLI / display tests
- `entity needs-review` lists flagged entities with kind/age columns.
- `graph propagate-freshness` is read-only and emits a report.
- `science:status` integration test surfaces a `needs-review` entity.

### End-to-end smoke
In a tmp project with one hypothesis backed by one observation, one finding (grounded_by a workflow-run), and one workflow-run: bump the workflow-run's `updated` date → `graph build` → confirm hypothesis is `needs-review` with `triggered_by` listing the workflow-run (via the closed transitive chain) → `entity review hypothesis:h01` → re-build → confirm the hypothesis is `fresh` again.

---

## File touch list (Phase 1)

| File | Change |
|---|---|
| `science-model/src/science_model/entities.py` | Add `EntityClass` enum; add `EpistemicReviewState` model; add `review_state` field on `ProjectEntity` (validated when kind is epistemic) |
| `science-model/src/science_model/profiles/core.py` | Add `bears_on` `RelationKind` (target_kinds = epistemic kinds) |
| `science-model/tests/test_review_state_model.py` | New |
| `science-tool/src/science_tool/graph/entity_registry.py` | Add `entity_class` parameter to `register_core_kind` / `register_profile_kind` / `register_extension_kind`; populate on all `with_core_types()` registrations; add `kind_class()` lookup |
| `science-tool/src/science_tool/graph/freshness.py` | New: `bears_on` auto-derivation engine (typed-edge rules + provenance walk + closure); freshness derivation per Part 3 |
| `science-tool/src/science_tool/graph/materialize.py` | Wire freshness step into the materialize pipeline (after existing triple emission); cycle-protected closure; write `EpistemicFreshness` triples into materialized graph only |
| `science-tool/src/science_tool/entity_review.py` | New: `entity review` / `entity needs-review` commands |
| `science-tool/src/science_tool/cli.py` | Register new commands; `graph propagate-freshness` subcommand alongside existing graph commands at line 618 |
| `science-tool/tests/test_kind_class.py` | New |
| `science-tool/tests/test_bears_on_derivation.py` | New (typed-edge derivation, provenance derivation, closure, cycle protection) |
| `science-tool/tests/test_freshness_derivation.py` | New |
| `science-tool/tests/test_entity_review_cli.py` | New |
| `scripts/validate.sh` | Add `bears_on` target-kind check (target classified epistemic); review-state frontmatter shape check |
| `meta/validate.sh` | Mirror lockstep |
| `docs/claim-and-evidence-model.md` | Add a section on `bears_on` and freshness; clarify pre-registration recast |
| `docs/proposition-and-evidence-model.md` | Same |

---

## Trajectory (out of scope for phase 1, tracked)

1. **Phase 2: weighted sampling.** Design the weight function, integrate into `science:next-steps` / `science:curate` / `science:big-picture` / task prioritization. Tracked as `[t010]`.
2. **Phase 3: cross-project freshness.** A paper added to the global bibliography should be able to mark downstream hypotheses across multiple projects as `needs-review`. Depends on cross-project entity resolution (federation workstream — see `docs/federation.md`).
3. **Phase 4: claim-layer continuous standing.** Replace the current implicit binary verdict-state on hypotheses with an explicit qualitative ladder ("dormant" / "contested" / "supported" / "well-supported") derived from edge counts and pre-registered interpretation outcomes. This is what would make the continuous-belief framing visible in the data, not just in attention. Deliberately deferred until phase 2 surfaces whether qualitative-ladder is actually needed or whether sampling-driven attention is sufficient.
4. **Conclusion-amendment workflow.** When a `needs-review` entity's reviewer concludes the new evidence changes the standing, what's the protocol? Probably an `amends` edge to a prior interpretation/finding, a new interpretation entity, and a `supersedes` link. Out of scope here; flagged for follow-up.
5. **Edge cases in the taxonomy.** `paper`, `mechanism`, `assumption`, `model` straddle categories. Final classification to be settled in phase 1 implementation; this sketch assumes the manifest-level field makes refinements cheap.

---

## Decisions (resolved 2026-05-03)

These were open questions during drafting; resolved here so the implementer doesn't re-litigate.

1. **Edge name: `bears_on`.** Kept. Reads in the right direction ("X bears on Y") and doesn't collide with existing predicates. `informs` is too soft (it sounds advisory rather than evidence-flow); `affects` is too generic; `feeds_belief` overcommits on the Bayesian framing.

2. **Freshness propagation: always on for epistemic entities, project-level opt-out.** Default behavior of `graph build` recomputes freshness for every epistemic entity. Downstream projects can disable via a `science.yaml` setting (`freshness.enabled: false`) during migration. Always-on is the right default because the materialized graph rebuilds anyway and freshness is purely additive in the materialized output.

3. **Pre-registration recast: documented here, implemented separately.** Data-model change is zero (no pre-reg schema change). The behavioral shift is in `science:pre-register`, `science:interpret-results`, and the project-level docs (`docs/claim-and-evidence-model.md`, `docs/proposition-and-evidence-model.md`). Tracked as a separate task `[t012]` so it can land independently of `[t010]`'s code work.

4. **`entity_class` is core, not profile-overridable.** The operational/epistemic split is foundational, not domain-specific. Profile/extension kinds must declare a classification at registration time; the default for unclassified extension kinds is `OPERATIONAL` (conservative — extensions don't get freshness propagation by default and must opt in by declaring `EPISTEMIC`).

5. **Upstream change marker: frontmatter `updated` date in phase 1; content hash in phase 2.** Deferred per the trajectory section. Date-based is correct under normal authoring workflow (frontmatter `updated` is bumped by every editor that respects the convention) and makes the feature shippable.

6. **`bears_on` edges are unweighted.** Phase-2 sampling computes weights from observable graph structure (incoming edge count, freshness state, days-since-review, evidence imbalance) + an `ε` floor. Adds zero schema burden in phase 1 and lets phase 2 iterate the weight function without touching stored edges.

7. **Mechanism `has_participant` propagation: epistemic participants only.** Derive `participant bears_on mechanism` only when the participant's kind is itself epistemic (proposition, observation, finding). Reference-kind participants (concepts, domain terms) do not trigger — a mechanism doesn't go stale because someone added a synonym to a concept it references. Implementation-time confirmation: walk `has_participant` triples, filter by participant `kind_class == EPISTEMIC`, emit `bears_on` for the survivors.

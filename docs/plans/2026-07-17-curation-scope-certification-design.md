# Curation scope certification — design

**Status:** DESIGN — **v2**, revised 2026-07-17 after review. **Not ready for an
implementation plan.**

**Blocking precondition.** The §5 ruling is **conditional** on the
correspondence-drift sample of §2.2, which **has not been run**. v1 justified the
ruling with a status distribution (*"2 of 126 plans marked complete"*); that
inference is **retracted** — it cannot distinguish a stale record from an
in-flight plan. Until the sample exists, this spec has no measured evidence, and
its gate can still withdraw §5 entirely and close the question as
*"epistemic-only certified as correct."*

**Ratify before implementing.** The §5 `correspondence` roster is a proposal, not
a finding (§5 item 5).

This is **spec 1 of a decomposed program** (§7). It is deliberately the smallest
piece, and everything else in the program depends on its ruling: until a review
of a `plan` can be *recorded*, no plan-curation command can exist.

## 1. Problem

`science entity review <id>` refuses any entity whose kind is not
`EntityClass.EPISTEMIC`:

> `review_state is only meaningful on epistemic entities`

`plan` is `EntityClass.OPERATIONAL`. So `science entity review plan:0042` is
rejected today, by design — nothing in the curation surface can record that
anyone looked at a plan.

Whether operational entities *drift enough to matter* is **not yet established**
(§2.2 — an earlier claim to that effect is retracted). That measurement is a
precondition, and the ruling in §5 is conditional on it.

This design does **not** ask "how do we curate plans". It asks the prior
question: **which kinds may carry review state, and is `review_state` even the
right instrument for the ones that aren't epistemic?** A defensible answer
includes *"the existing restriction is correct"* — §2.2's gate keeps that outcome
reachable.

## 2. Measured baseline

Measured 2026-07-17 across five Science projects. **Re-measure before acting.**

### 2.1 `review_state` is essentially unadopted

Frontmatter `review_state:` (not body-text mentions — see §2.4):

| Project | entities with `review_state` | kinds |
|---|---|---|
| post-acute-infection | 5 | proposition (4), hypothesis (1) |
| natural-systems | 3 | hypothesis (3) |
| multiple-myeloma | 1 | interpretation (1) |
| protein-landscape | 0 | — |
| labnote | 0 | — |

**9 entities across five projects, every one an epistemic kind.**

The corpus therefore does **not refute** the epistemic-only ruling — it is
consistent with it. But it cannot *certify* it either: at this adoption level
there is no usage signal in any direction. **The ruling is untested, not wrong.**
Certification therefore cannot rest on usage — it requires the
correspondence-drift sample of §2.2, which has **not yet been run**.

This is the opposite of the `status`-vocabulary case, where a large corpus
actively contradicted the descriptor. Here the instrument has barely been fired.

### 2.2 Operational drift is NOT yet measured — and this spec depends on it

**Retracted (2026-07-17, review).** An earlier draft of this section presented:

| Project | `entities/plans` | marked `complete` |
|---|---|---|
| multiple-myeloma | 126 | **2** |
| natural-systems | 109 | 16 |

and concluded "plans are not being closed out … this is correspondence drift."
**That inference does not follow.** A status distribution cannot distinguish a
*stale record* from a *genuinely draft or active plan*. 124 non-complete plans is
equally consistent with 124 healthy in-flight plans. The figures measure the
status field; they say nothing about correspondence with reality.

This is not a cosmetic overclaim. §2.1 establishes that the epistemic-only ruling
**cannot be certified from usage** (adoption ≈ 0), and this section was named as
the evidence certification rests on instead. With this retraction, **the spec
currently rests on no measured evidence at all.**

**Required before implementation — the correspondence-drift sample.** Specified as
its own pre-registration:
[`2026-07-17-plan-correspondence-drift-sample-design.md`](2026-07-17-plan-correspondence-drift-sample-design.md).

In outline: `plan` entities only (N = 264 across four pinned projects), stratified
by `(project, claimed_status)`, **blind** adjudication of status from evidence
alone with tri-state deliverable probes, and a **three-way gate** at materiality
θ = 0.10 over a predeclared 40 → 80 → 264 ladder:

| Outcome | Consequence for this spec |
|---|---|
| drift **demonstrated** | retain §5; admit `plan`; ratify the remaining roster afterwards |
| drift **ruled out** | **withdraw §5**; certify epistemic-only as correct; this spec closes having answered "no" |
| **inconclusive** | expand per the ladder; uncertainty is **never** reported as absence |

**Sequencing.** The sample runs **before** §5's roster is ratified. Ratifying
first would be circular — taxonomy judgment would precede the evidence meant to
justify it.

### 2.3 Status drift is convergent across independent projects

| Illegal value | natural-systems | multiple-myeloma | post-acute | protein-landscape |
|---|---|---|---|---|
| `draft-for-review` | — | **24** | 1 | — |
| `approved` | 14 | — | — | 4 |
| `proposed` | 15 | — | — | 1 |
| `ready-with-caveats` | 2 | — | 2 | — |
| `design` | 11 | — | — | — |

Four projects that share no backlog independently minted words for the same
missing idea: *design reviewed and approved, implementation not started*. This is
**tracked as a separate spec** (§7 S4) — it is evidence *about* the vocabulary,
not about curation scope, and it must not be resolved as a side effect here.

### 2.4 A contaminated signal (do not reuse naively)

`grep -rl review_state entities/` **over-reports**. Plan and design bodies
discuss `review_state` in prose; an unqualified grep counted 7 multiple-myeloma
"hits" of which **1** was real frontmatter. Any scope measurement must parse the
frontmatter block, not the file. The §2.1 figures do this.

Corollary already known upstream: `grep -l '^---'` counts horizontal rules, not
frontmatter. Frontmatter presence requires a **first-line** check.

## 3. Prior art (use, do not rebuild)

Substantially more of this exists than a fresh reading suggests:

- **`science entity review <id>`** (`entity_review.py`) — writes
  `review_state.last_reviewed` / `last_review_note`. Atomic, reuses the canonical
  frontmatter helpers.
- **`science entity needs-review`** — reads `sci:freshnessState` from the
  materialized graph, returns `needs-review` / `stale` rows.
- **`EpistemicReviewState`** — `{last_reviewed, last_review_note,
  review_horizon_days}` on `Entity`, plus a sibling `review_after` field.
- **`--require-artifact`** — the review-theater guard: *"A bare timestamp bump is
  not a review."*
- **`EntityClass`** — `EPISTEMIC` / `OPERATIONAL` / `REFERENCE`, already
  load-bearing in the freshness engine (only `EPISTEMIC` entities are valid
  `bears_on` **targets** — sources are unrestricted; see §5.1).
- **`spec` and `curation-sweep`** — already-declared kinds.
- **`/science:curate`** — an existing agent-led curation sweep command.

**Nothing in this program should re-implement any of the above.** The
`review_horizon_days` field in particular already supplies the per-entity
staleness threshold a rotation needs.

### 3.1 `spec` is a stub

`EntityKind(name="spec")` declares no `home`, no `strategy`, and no
`default_status` — unlike `plan`, which declares all three. It is not creatable
as it stands. Fleshing it out belongs to §7 S3, not here.

### 3.2 multiple-myeloma already did this by hand

multiple-myeloma carries a project-extension `design` kind with a populated
`entities/design/` directory (e.g. `design:0036-edges-yaml-retirement-design`),
alongside `review`, `critique`, `audit`, `bias-audit`, and `paper-review` kinds.

A project independently reinvented design-specs-as-entities. That is the
strongest available evidence for the §7 S3 direction — and evidence that the
gap is real rather than theoretical.

## 4. The defect: the CLI answers with the wrong taxonomy

Scope is enforced **twice, by two different taxonomies**:

| Layer | Mechanism | Verdict on `plan` |
|---|---|---|
| `science-model` | hardcoded closed list in `Entity._validate_review_state_kind` — `{task, dataset, workflow-run, data-package, paper, prose-source, book, experiment, code-file}` | **permitted** (not in list) |
| `science` CLI | `EntityRegistry.kind_class(...) != EntityClass.EPISTEMIC` | **refused** |

So a `plan` with `review_state` **validates on disk but cannot be written by the
command**. `spec` behaves the same way.

### 4.1 The closed list is not a redundant copy of `EntityClass`

The tempting fix — delete the closed list, derive scope from `EntityClass` — is
**wrong, and would be a regression.** The registered kinds partition as:

| `EntityClass` | n | members |
|---|---|---|
| `EPISTEMIC` | 21 | assumption, chain-audit, discussion, evidence-line, falsification, finding, hypothesis, inquiry, interpretation, mechanism, observation, patch-definition, proposition, question, report, research-question, story, structural-chain, synthesis, theme, validation-report |
| `OPERATIONAL` | 21 | book, claim-registry, code-file, curation-sweep, data-package, dataset, experiment, method, paper, plan, pre-registration, prose-source, research-package, search, spec, talk, task, transformation, workflow, workflow-run, workflow-step |
| `REFERENCE` | 8 | article, concept, construct, decision, outcome, topic, unknown, variable |

**Every one of the closed list's nine kinds is `OPERATIONAL`.** So the closed list
is not approximating `EntityClass` — it is drawing a distinction *inside*
`OPERATIONAL` that `EntityClass` cannot express:

- **authored artifacts that drift from reality** — plan, spec, method,
  pre-registration, workflow, transformation, search, claim-registry,
  research-package, curation-sweep, talk → a correspondence review is meaningful;
- **immutable external records** — paper, book, prose-source → the artifact does
  not change; there is nothing to re-review;
- **execution / derived records** — workflow-run, experiment, code-file,
  data-package, dataset, workflow-step → logs and outputs, not claims;
- **task** — carries its own lifecycle machinery.

Deriving scope from `EntityClass` would collapse these four groups into one and
admit `paper`, `dataset`, and `workflow-run` to curation. The closed list is the
layer that is *right*. **The CLI is the buggy layer**: it answers a curation
question with a taxonomy calibrated for `bears_on` propagation.

### 4.2 A deny list makes every new kind reviewable by default

The closed list is a **deny** list, so any kind added later is silently in scope
until someone remembers to forbid it. That is the wrong default for a schema-level
capability (§5.1). Its *knowledge* is correct; its *polarity* is not.

### 4.3 Out-of-scope observation: `EntityClass` looks miscalibrated

`paper` and `book` are `OPERATIONAL` — "operational artifacts produced by project
work" — but a paper is not produced by project work; it is an external thing that
rarely changes, which is `REFERENCE`'s own stated definition. Meanwhile
`REFERENCE` holds `concept`, `topic`, and `variable`.

This is **recorded, not fixed here.** `EntityClass` is load-bearing for
`bears_on`, and re-classifying kinds would move propagation behaviour — a change
that needs its own evidence and its own spec. It is noted because it is *why*
`EntityClass` cannot be borrowed for curation scope.

## 5. Ruling: curation scope is its own declared axis

Both "epistemic-only" and "extend `review_state` to plans" are wrong, because
`review_state` conflates two operations that merely share a schedule. And
**neither existing taxonomy answers the question** — `EntityClass` is calibrated
for propagation (§4.1), and the closed list has the right knowledge with the
wrong polarity (§4.2).

So curation scope is **declared explicitly on `EntityKind`**, deriving from
nothing, with two admitted verdict modes:

| `curation_scope` | The review asks | Driven by | Kinds |
|---|---|---|---|
| `epistemic` | *Given new evidence, is this still my belief?* | `bears_on` propagation | the 21 `EPISTEMIC` kinds |
| `correspondence` | *Does this record still correspond to reality — did it ship?* | code / task / deliverable probes | plan, spec, method, pre-registration, workflow, transformation, search, claim-registry, research-package, curation-sweep, talk |
| `none` (default) | — nothing to review | — | paper, book, prose-source, article (immutable); workflow-run, experiment, code-file, data-package, dataset, workflow-step (execution records); task (own lifecycle); all `REFERENCE` kinds |

A plan has no belief to reconsider, so `bears_on` freshness is meaningless for
it. But it drifts from reality (§2.2), and that drift is invisible to every
existing instrument.

Therefore:

1. **The scheduling substrate is universal** across in-scope kinds.
   `last_reviewed`, `review_horizon_days`, the rotation ordering key, and the
   review-theater guard apply to anything that can drift. Nothing about *when to
   look* is epistemic.
2. **The verdict is dispatched on `curation_scope`**, not on `EntityClass`.
3. **`bears_on` freshness stays epistemic-only *as a sink*.** The existing
   freshness-engine restriction is correct and is **not** touched. Correspondence
   staleness derives from `review_horizon_days` and probes, never from belief
   propagation. See §5.1 — the restriction is on **targets**, not sources, and
   conflating the two would break working behaviour.
4. **`none` is the default** for *core* kinds. A newly registered core kind is out
   of scope until someone declares otherwise — inverting the deny-list polarity of
   §4.2. **Extension kinds are a separate case with a live regression risk — see
   §6.2.**
5. **The `correspondence` roster above is a proposal, not a finding**, and §6.3
   test 8 is what turns it into one. It is derived from the closed list's four
   implicit groups (§4.1) and **must be ratified kind-by-kind and transcribed into
   the spec before implementation begins** — an approved design must not leave its
   central mapping open. `talk` and `search` are flagged uncertain: it is not
   obvious either drifts in a way a probe can check. `pre-registration` is
   confirmed `correspondence` (§5.1).

**The name is the tell.** `EpistemicReviewState` bakes the conflation into the
class name. Under this ruling it is renamed `ReviewState` — a **clean rename, no
compatibility shim, no alias** (per project convention).

### 5.1 A correspondence kind may be a `bears_on` SOURCE

**Verified 2026-07-17.** `derive_bears_on_from_pre_registrations`
(`graph/freshness.py:159`) emits `pre_registration_uri sci:bearsOn target_uri` —
the **pre-registration is the subject**, and only the *target* is gated on
`EntityClass.EPISTEMIC`. A `pre-registration` is a deliberate, tested `bears_on`
source: `pytest -k pre_registration` → **5 passed**, including
`test_pre_registration_related_epistemic_targets_derive_bears_on_by_default`.

`pre-registration` is `correspondence`-scoped in §5's roster. So "correspondence
entities are outside `bears_on`" is **false**, and an earlier draft of acceptance
test 6 asserted it — a criterion that would have failed a passing regression test
and pressured an implementer to break intended behaviour.

The correct invariant is directional:

> A `correspondence`-scoped entity is never a `bears_on` **target** and never
> receives `sci:freshnessState`. It **may** remain a `bears_on` **source** to
> epistemic targets.

This is why `EntityClass` and `curation_scope` must stay separate axes rather than
one merged notion of "epistemic-ness": `pre-registration` is *operational* by
class, *correspondence* by curation scope, and a *legitimate upstream* of belief.
No single axis expresses all three.

### 5.2 Why not just delete the restriction?

Because the restriction is *load-bearing for epistemic kinds* and merely
*mis-scoped*. Deleting it would let a `dataset` acquire `review_state` with no
defined verdict and no probe — review theater at the schema level, which is
exactly what `--require-artifact` exists to prevent at the command level. Scope
must be positively declared per kind, not left as whatever is not forbidden.

## 6. Deliverables

1. **A declared `curation_scope` field on `EntityKind`** — `epistemic` |
   `correspondence` | `none`, defaulting to `none` (§5 item 4). Authored per
   kind; derived from neither `EntityClass` nor the closed list.
2. **One SSOT predicate** (`curation_scope_for_kind`) reading that field, at the
   **single enforcement boundary of §6.1**. The hardcoded closed list is
   **deleted once its knowledge has been migrated** into the declarations —
   migrated, not merely dropped (§4.1), and not synchronized.
3. **The CLI stops consulting `EntityClass`** for scope. `EntityClass` keeps its
   propagation role untouched.
4. **Rename** `EpistemicReviewState` → `ReviewState`. No shim.
5. **`science entity review plan:NNNN` succeeds**, recording a correspondence
   review with a required artifact.
6. **`bears_on` freshness unchanged** — proven by test, not assertion.

### 6.1 Where scope is enforced — the profile-resolution boundary

An earlier draft said the predicate is "consulted by both the model validator and
the CLI." **That is unimplementable**, and the reason is architectural, not
incidental:

- `Entity._validate_review_state_kind` (`entities.py:390`) receives only
  `self.kind` — a bare string. Its own comment states the closed list exists to
  *"avoid registry coupling at the science-model layer."*
- `science-model` declares exactly three dependencies — `pydantic`, `pyyaml`,
  `jsonschema`. It **cannot import `science_tool`.**
- Core descriptors live in `science_model/profiles/core.py`, so the model *can*
  see those. **Project-local and shared descriptors cannot** — `science_tool`
  resolves them (`graph/sources.py:265`, `load_shared_profile`,
  `local_profile_manifest`).
- `entity_review.py:68` constructs only `EntityRegistry.with_core_types()`, so
  the CLI does not see them either on this path.

So the closed list is **not merely wrong-polarity (§4.2) — it is a deliberate
layering artifact.** §4.1 was right that it holds knowledge `EntityClass` lacks,
but incomplete about *why* it is shaped as a hardcoded list.

**Ruling: one profile-aware enforcement boundary; the model validates shape only.**

| Concern | Layer |
|---|---|
| `ReviewState` **shape** (field types, internal consistency) | `science-model`, no registry |
| **Scope** (may this kind carry `review_state` at all?) | profile-aware boundary in `science_tool`, where local + shared descriptors are resolved |

`Entity._validate_review_state_kind` is **deleted, not re-pointed.** Scope is a
profile question; a layer that cannot see profiles cannot answer it, and a partial
answer over core kinds only is exactly the two-taxonomy split this spec exists to
end. Enforcement joins the existing load+write boundary — the same shape as the
`validated_entity_schema_version` pin, which is the sole authority over its fields
via one path shared by load and write.

**Consequence — acceptance test 1 is reframed.** "Model and CLI agree per kind"
presumes two deciders. With one boundary the property becomes: **exactly one code
path decides scope**, asserted by a guard test proving no other module reads
`curation_scope` or reimplements the closed list.

**Standalone parsing behaviour (explicit).** `Entity.model_validate(raw)` with no
profile context performs **no scope check** and does not fail. It is a shape
parse. Scope is refused only at the boundary. This is a deliberate narrowing: a
bare `model_validate` never was a safe scope gate — it consulted a hardcoded list
that could not see a project's own kinds.

**Pydantic-context alternative — rejected.** Passing the registry via
`model_validate(..., context=...)` keeps validation in the model but makes the
check *silently optional*: every caller that forgets the context gets a pass. That
is fail-open on the exact axis this spec is tightening, and it re-creates the
"validated on disk but refused by the command" divergence in a new form.

### 6.2 Extension kinds: default-`none` is a live regression

`entity_review.py:70` today does this:

```python
except EntityKindNotRegisteredError:
    kind_class = None  # extension kinds default to allowed
```

**Extension kinds currently default to REVIEWABLE.** Applying default-`none`
(§5 item 4) to them would flip that to *refused* — and multiple-myeloma carries
project-extension kinds `design`, `review`, `critique`, `audit`, `bias-audit`, and
`paper-review` (§3.2), with populated `entities/design/`. **The project furthest
along the direction this program advocates is the one that breaks.**

This is the status-vocabulary regression's exact shape: a check that can only fire
on downstream data, shipped green because this repo has **no `entities/` of its
own**. Green CI here proves nothing.

Therefore:

1. **A local profile may declare `curation_scope`** on its kinds; that declaration
   is authoritative for that project.
2. **An undeclared *extension* kind resolves to `correspondence`, not `none`** —
   preserving today's reviewable-by-default behaviour for exactly the population
   that has it. Default-`none` governs **core** kinds, where the roster is
   ratified (§6.3 test 8) and silence means "not yet considered." For an
   extension kind, silence means "this project never had a field to fill in."
   The asymmetry is deliberate: **the tightening applies where the roster was
   certified, not where it was never asked.**
3. **This is re-examined once local profiles can declare scope** and adopters have
   migrated. Tightening extension kinds later is a separate, announced change.
4. **Verification runs against real downstream projects** — at minimum
   multiple-myeloma and natural-systems — asserting `science validate` exit codes
   and finding counts are unchanged. Not a unit test in this repo.

### 6.3 Acceptance tests

**These are framed around the single decider of §6.1.** v2 inherited "model and
CLI agree" phrasing from v1, which contradicted §6.1's own ruling — there is no
second decider left to agree with.

1. **Exactly one decider.** A guard test asserts that exactly one module resolves
   `curation_scope`: no other module reads the field or reimplements the closed
   list, and `Entity._validate_review_state_kind` **no longer exists**. This
   replaces v1's "no kind gets a different answer from the model and the CLI",
   which presumed the two-decider split this spec removes. Derive the guard from
   the import closure — a guard that *lists* its scope has a hole by construction.
2. **No knowledge lost in the migration.** Every kind on the deleted closed list
   resolves to `curation_scope: none` **at the boundary**. This catches a
   migration that dropped the list instead of transcribing it (§4.1).
3. **Default is `none` for core kinds.** A core kind declaring no
   `curation_scope` is refused at the boundary — the §4.2 polarity inversion,
   asserted rather than assumed. (Extension kinds differ deliberately: test 9.)
4. **Positive:** `entity review plan:NNNN --note "..."` writes
   `review_state.last_reviewed` and the file validates.
5. **Negative:** `entity review dataset:X` is refused at the boundary
   (`curation_scope: none`).
5b. **The model validates shape only (§6.1).** `Entity.model_validate(raw)` on a
   `none`-scoped kind carrying a well-formed `review_state` **succeeds** — no
   scope check, no context. Asserted explicitly, because it is a deliberate
   narrowing that reads like a hole: scope is refused at the boundary, and a bare
   `model_validate` never was a safe gate (it consulted a list that could not see
   a project's own kinds). Shape errors still fail here.
6. **Freshness isolation is directional (§5.1).** A `correspondence`-scoped entity
   carrying `review_state` never becomes a `bears_on` **target** and never
   receives `sci:freshnessState`. It **may** be a `bears_on` **source**.
   The existing `pre_registration` suite (5 tests) must stay green — it is the
   guard against over-tightening this, and an earlier draft of this criterion
   would have failed it.
7. **Theater guard holds** on the newly admitted kinds: a bare timestamp bump on
   a `plan` is refused without an artifact.
8. **The full core roster is asserted exhaustively.** Every core kind is checked
   against the ratified §5 mapping by an explicit table — `epistemic` for the 21
   `EPISTEMIC` kinds, `correspondence` for the ratified roster, `none` for the
   rest. Tests 1–3 are all satisfied by an implementation that returns `none` for
   everything; **this is the test that fails it**, and the one that catches
   `method`, `workflow`, or an epistemic kind silently defaulting.
9. **Extension kinds stay reviewable (§6.2).** An undeclared extension kind
   resolves to `correspondence`, not `none` — asserted directly, since this is a
   deliberate asymmetry that reads like a bug.
10. **Downstream projects are unchanged.** `science validate` exit code and
    finding count are identical before and after, run against real
    multiple-myeloma and natural-systems checkouts. Green CI in this repo does not
    substitute (§6.2).

## 7. Decomposition (this spec is S1)

| # | Spec | Depends on | Status |
|---|---|---|---|
| **S1** | **Curation scope certification** — this doc | — | design approved |
| S2 | Adaptive curation rotation — `n(N) = min(N, ⌈b·ln N − a⌉)`, least-recently-reviewed selection, sweep-provenance trailers | S1 | not started |
| S3 | Specs/plans as entities from creation — flesh out `spec` kind; intercept `superpowers:brainstorming` / `writing-plans` via the AGENTS.md template; `science entity import` for the loose corpus | S1, S2 | not started |
| S4 | Plan status vocabulary certification — the convergent `approved` / `draft-for-review` drift (§2.3) | — (parallel) | not started |
| S5 | State tier — durable vs derived vs transient; XDG state dir; sqlite activity cache | — (parallel) | not started |

**S2 rationale (recorded here so it is not re-litigated).** Coverage over
repeated sweeps requires **rotation, not random sampling**. Simulated over the
measured corpora, random draws reach full coverage in ~42 sweeps (p95 = 57, max
90) for natural-systems at n=57/N=389, versus a hard **7** for
least-recently-reviewed rotation. Random selection also leaves a tail of
never-read documents, which is presumption re-entering by the side door.

**S5 rationale.** The dividing line is **"can it be regenerated from
version-controlled sources?"** — not "can it be wiped". By that test, activity /
flux scores are derived (state dir), and `last_reviewed` / review counts are
**events derivable from nothing** and stay versioned in the repo. The existing
implementation already places `review_state` in frontmatter, consistent with
this. A stored flux score would be a cache that decays with wall-clock time while
nothing rewrites the file — wrong the moment it is written, and most wrong for
exactly the unreviewed entities the sweep exists to find.

## 8. Non-goals

- **Curating plans.** This spec makes a plan review *recordable*; S2/S3 make it
  happen.
- **Admitting the immutable-record and execution-record kinds** (`paper`, `book`,
  `dataset`, `workflow-run`, …). They stay `none`. Deferred until drift is
  measured for them (§2.1's lesson).
- **Re-classifying `EntityClass`** despite §4.3's finding. It moves propagation
  behaviour and needs its own spec.
- **Touching `bears_on` propagation.** Explicitly preserved.
- **Resolving the status vocabulary.** That is S4; §2.3 is evidence, not a
  mandate.
- **The state tier.** That is S5.
- **Rewriting plan content for quality.**

## 9. Risks

| Risk | Mitigation |
|---|---|
| Scope change corrupts `bears_on` propagation | Freshness sinks stay epistemic-only (§5 item 3); acceptance test 6 asserts a `correspondence` entity is never a propagation **target** |
| **Over-tightening breaks `pre-registration`** | §5.1 — `pre-registration` is `correspondence`-scoped **and** a deliberate `bears_on` **source** (`freshness.py:159`, 5 passing tests). The invariant is directional; an earlier draft of test 6 would have failed a passing regression test |
| **Scope enforced where profiles are invisible** | §6.1 — `science-model` cannot import `science_tool` and never sees local/shared descriptors. Scope moves to **one** profile-aware boundary; the model validates shape only; `_validate_review_state_kind` is deleted, not re-pointed |
| Pydantic-context enforcement fails open | §6.1 — rejected: a caller omitting the context silently passes, on the exact axis being tightened |
| **Default-`none` silently breaks adopters** | §6.2 — extension kinds default to **reviewable today**; multiple-myeloma's `design`/`review`/`critique`/`audit` kinds would flip to refused. Undeclared extension kinds resolve to `correspondence`; acceptance tests 9 + 10 |
| Shipped green on a repo with no `entities/` | §6.2 — the status-vocabulary regression's exact shape. Acceptance test 10 runs against real downstream checkouts, not CI fixtures |
| **Ruling built on retracted evidence** | §2.2 — the "2 of 126" drift claim is **retracted**; a status distribution cannot distinguish stale from in-flight. The correspondence-drift sample is a precondition, and its gate can withdraw §5 entirely |
| **Scope derived from `EntityClass`, destroying the closed list's knowledge** | §4.1 — every closed-list kind is `OPERATIONAL`, so deriving would admit `paper`/`dataset`/`workflow-run`. Scope is its **own declared axis**; acceptance test 2 asserts every closed-list kind still resolves to `none` |
| Closed list dropped rather than migrated | Acceptance test 2 is exactly this test; §6 deliverable 2 says *migrated, not merely dropped* |
| A future kind is reviewable by default | Default `none` + positive declaration (§5 item 4); acceptance test 3 |
| A second decider reappears | There is exactly **one** — §6.1 deletes `_validate_review_state_kind` rather than re-pointing it. Acceptance test 1 is an import-closure guard asserting no other module resolves scope; a guard that *lists* its scope has a hole by construction |
| Review theater on newly admitted kinds | `--require-artifact` extended to correspondence reviews; acceptance test 7 |
| `correspondence` roster admits kinds that cannot be probed | §5 item 5 — the roster is a proposal ratified kind-by-kind; `talk` and `search` flagged as uncertain |
| Ruling certified from an unadopted feature | §2.1 states plainly that adoption is ~0, so usage certifies nothing; §2.2 makes the drift sample a precondition rather than a claim |
| Scope creep into the other four specs | §7 fixes the boundaries; §8 names the exclusions |
| Measurement repeats the grep error | §2.4 records the contaminated signal; scope counts parse frontmatter, never `grep -l` |
| `entities.py:884` comment claims `extra="ignore"` | Stale comment — `Entity` is `extra="allow"` (D3.3). Correct it while in the file; it misleads exactly this kind of work |

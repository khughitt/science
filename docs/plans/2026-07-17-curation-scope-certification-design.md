# Curation scope certification — design

**Status:** DESIGN — approved 2026-07-17; implementation plan pending.

This is **spec 1 of a decomposed program** (§7). It is deliberately the smallest
piece, and everything else in the program depends on its ruling: until a review
of a `plan` can be *recorded*, no plan-curation command can exist.

## 1. Problem

`science entity review <id>` refuses any entity whose kind is not
`EntityClass.EPISTEMIC`:

> `review_state is only meaningful on epistemic entities`

`plan` is `EntityClass.OPERATIONAL`. So `science entity review plan:0042` is
rejected today, by design. Yet operational entities demonstrably drift — see
§2 — and nothing in the curation surface can currently record that anyone looked.

This design does **not** ask "how do we curate plans". It asks the prior
question: **which kinds may carry review state, and is `review_state` even the
right instrument for the ones that aren't epistemic?**

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
Certification must come from the drift evidence (§2.2), not from usage.

This is the opposite of the `status`-vocabulary case, where a large corpus
actively contradicted the descriptor. Here the instrument has barely been fired.

### 2.2 Operational drift is real and measured

| Project | `entities/plans` | marked `complete` |
|---|---|---|
| multiple-myeloma | 126 | **2** |
| natural-systems | 109 | 16 |

Plans are not being closed out. This is correspondence drift in an operational
kind, and an epistemic-only curation layer cannot see it by construction.

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
  `bears_on` targets).
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
3. **`bears_on` freshness stays epistemic-only.** The existing freshness-engine
   restriction is correct and is **not** touched. Correspondence staleness derives
   from `review_horizon_days` and probes, never from belief propagation.
4. **`none` is the default.** A newly registered kind is out of scope until
   someone declares otherwise — inverting the deny-list polarity of §4.2.
5. **The `correspondence` roster above is a proposal, not a finding.** It is
   derived from the closed list's four implicit groups (§4.1) and must be
   ratified kind-by-kind during implementation. `talk` and `search` in particular
   are uncertain: it is not obvious either drifts in a way a probe can check.

**The name is the tell.** `EpistemicReviewState` bakes the conflation into the
class name. Under this ruling it is renamed `ReviewState` — a **clean rename, no
compatibility shim, no alias** (per project convention).

### 5.1 Why not just delete the restriction?

Because the restriction is *load-bearing for epistemic kinds* and merely
*mis-scoped*. Deleting it would let a `dataset` acquire `review_state` with no
defined verdict and no probe — review theater at the schema level, which is
exactly what `--require-artifact` exists to prevent at the command level. Scope
must be positively declared per kind, not left as whatever is not forbidden.

## 6. Deliverables

1. **A declared `curation_scope` field on `EntityKind`** — `epistemic` |
   `correspondence` | `none`, defaulting to `none` (§5 item 4). Authored per
   kind; derived from neither `EntityClass` nor the closed list.
2. **One SSOT predicate** (`curation_scope_for_kind`) reading that field,
   consulted by **both** the model validator and the CLI. The hardcoded closed
   list is **deleted once its knowledge has been migrated** into the declarations
   — migrated, not merely dropped (§4.1), and not synchronized.
3. **The CLI stops consulting `EntityClass`** for scope. `EntityClass` keeps its
   propagation role untouched.
4. **Rename** `EpistemicReviewState` → `ReviewState`. No shim.
5. **`science entity review plan:NNNN` succeeds**, recording a correspondence
   review with a required artifact.
6. **`bears_on` freshness unchanged** — proven by test, not assertion.

### 6.1 Acceptance tests

1. **Scope SSOT.** No kind receives a different answer from the model and the
   CLI. Asserted by enumerating *every* registered kind through both paths and
   diffing — not by spot-checking `plan`.
2. **No knowledge lost in the migration.** Every kind on the deleted closed list
   resolves to `curation_scope: none`. This is the test that catches a migration
   that dropped the list instead of transcribing it (§4.1).
3. **Default is `none`.** A kind registered with no `curation_scope` declaration
   is refused by both layers — the §4.2 polarity inversion, asserted rather than
   assumed.
4. **Positive:** `entity review plan:NNNN --note "..."` writes
   `review_state.last_reviewed` and the file validates.
5. **Negative:** `entity review dataset:X` is refused (`curation_scope: none`),
   with the same verdict from the model.
6. **Freshness isolation:** a `correspondence`-scoped entity carrying
   `review_state` never becomes a `bears_on` target and never appears as an
   epistemic freshness source. This is the regression that would silently corrupt
   belief propagation.
7. **Theater guard holds** on the newly admitted kinds: a bare timestamp bump on
   a `plan` is refused without an artifact.

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
| Scope change corrupts `bears_on` propagation | Freshness stays epistemic-only (§5 item 3); acceptance test 6 asserts a `correspondence` entity is never a propagation target |
| **Scope derived from `EntityClass`, destroying the closed list's knowledge** | §4.1 — every closed-list kind is `OPERATIONAL`, so deriving would admit `paper`/`dataset`/`workflow-run`. Scope is its **own declared axis**; acceptance test 2 asserts every closed-list kind still resolves to `none` |
| Closed list dropped rather than migrated | Acceptance test 2 is exactly this test; §6 deliverable 2 says *migrated, not merely dropped* |
| A future kind is reviewable by default | Default `none` + positive declaration (§5 item 4); acceptance test 3 |
| Model and CLI diverge again | One predicate over one declared field; acceptance test 1 diffs **every** registered kind through both paths |
| Review theater on newly admitted kinds | `--require-artifact` extended to correspondence reviews; acceptance test 7 |
| `correspondence` roster admits kinds that cannot be probed | §5 item 5 — the roster is a proposal ratified kind-by-kind; `talk` and `search` flagged as uncertain |
| Ruling certified from an unadopted feature | §2.1 states plainly that adoption is ~0 and that certification rests on §2.2 drift, not usage |
| Scope creep into the other four specs | §7 fixes the boundaries; §8 names the exclusions |
| Measurement repeats the grep error | §2.4 records the contaminated signal; scope counts parse frontmatter, never `grep -l` |
| `entities.py:884` comment claims `extra="ignore"` | Stale comment — `Entity` is `extra="allow"` (D3.3). Correct it while in the file; it misleads exactly this kind of work |

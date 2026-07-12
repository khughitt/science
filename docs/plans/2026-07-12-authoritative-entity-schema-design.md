# The authoritative entity schema

**Date:** 2026-07-12 (rev 5 — D4 re-ruled post-audit; see §10)
**Status:** **Architecture accepted; final amendment applied.** D1–D5 ruled (§9), D4 contract
re-ruled against the audit. **Ready to write the D5 implementation plan.**
**Contract input:** [`2026-07-12-d4-status-vocabulary-audit.md`](2026-07-12-d4-status-vocabulary-audit.md)
**Subsumes:** the field-vocabulary (`extra="ignore"`) and status-vocabulary tracks — two
symptoms of one root.

## 1. The root cause

Three surfaces must agree about any piece of entity frontmatter: the **template** that tells
an author to write it, the **declaration** that models it, and the **graph** that consumes
it. **Nothing binds them.**

| axis | symptom | mechanism |
|---|---|---|
| **fields** — which keys exist | 194 undeclared keys; ~40% of files would fail strict validation | `Entity` is `extra="ignore"` → undeclared keys dropped at `model_validate` |
| **values** — what a key may hold | 472 status findings; `validate` broke in 2 projects | `EntityKind.statuses` never reconciled against templates/commands/usage |

**Proof they are one defect:** `templates/pre-registration.md` fails on *both* at once —
`status: "committed"` is an illegal **value**, and `committed:`/`spec:` are undeclared
**keys**, silently dropped. `meta/entities/hypotheses/0007-working-model.md` — the document
defining Science's model of knowledge — carries `role:` and `phase:`, both undeclared, both
dropped.

## 2. The correction: an authoritative schema system already exists

The previous revision of this design claimed Science has *no* authoritative entity schema and
proposed inventing one (`EntityKind.fields`). **That was wrong, and it would have built a
third parallel system.** Science has **two** entity systems with **opposite** policies:

| | project-authored entities | shared / commons entities |
|---|---|---|
| model | `Entity` / `ProjectEntity` | `SharedEntity` (`entity_schema/wrapper.py`) |
| unknown keys | **`extra="ignore"`** — silently dropped | **`extra="allow"`** — preserved in `extra` |
| schema | `EntityKind` descriptor: identity, placement, **status values — no fields** | **composed JSON Schema**, declared source of truth |
| composition | none | `schema_profile` = `<base>/<ver>+<mixin>/<ver>+<ext>/<ver>`, merged via `allOf` |
| conditional invariants | 20 hand-written `@model_validator`s | native JSON Schema |
| merge / conflict policy | none | `science:merge` → `REPLACE \| APPEND \| FORBIDDEN \| PROJECT_ONLY` |
| versioning | none | real (`mixin-paper-1.0` **and** `2.0` ship side by side) |
| adoption | all project entities | **369 commons records**, 8+ toolkit modules |

The shared system is **versioned, composable, annotation-driven, and already authoritative**.
The project-authored system never adopted it. `dataset` and `paper` consequently have **two
definitions today.**

So this is the *same* half-applied-pattern story once more: the schema layer was built,
applied to commons, and never applied to project entities. **The work is to converge them,
not to invent a third.**

## 3. Four separable concerns (the central correction)

The previous design compressed four independent things into one `FIELDS` row. They are
orthogonal and must be modelled separately:

| concern | question it answers | where it lives |
|---|---|---|
| **A. Shape & invariants** | type, required, cross-field rules | **JSON Schema** (`allOf`/`if`-`then`) — already does this |
| **B. Semantic role** | is this field lifecycle, verdict, relation, provenance? | new `science:axis` annotation |
| **C. Ownership & composition** | who may declare/override it; how do overlays merge? | `schema_profile` + existing `science:merge` |
| **D. Graph encoding** | how (or whether) it becomes triples | new `science:graph` annotation |

**Ownership is not an axis.** `project-local` is a *scope* — a project-local field can also be
a relation, a lifecycle field, or provenance. B and C are independent dimensions.

`EntityKind` keeps identity + placement and **points at a schema**. It does not re-declare
fields.

## 4. Concern A — shape & invariants

Invariants are **not** expressible as `{type, required, vocabulary}` rows. Real examples:

- `disposition_basis` is required **iff** `disposition == "closed"`.
- `derived_kind` is required **iff** `source_class == "derived"`, and **forbidden otherwise**
  (`entities.py:400`).

There are **20 `@model_validator`s** in `entities.py`. Generating models from flat field rows
would silently weaken every one.

**Resolution:** JSON Schema is authoritative for shape *and* invariants — it expresses these
natively, and the shared layer already composes constraints with `allOf`. The Pydantic class
becomes a **projection** for ergonomic in-code access (as `SharedEntity` already is), not a
second authority. Any invariant that JSON Schema genuinely cannot express is declared an
explicit, enumerated escape hatch — not an open-ended second surface.

## 5. Concern D — graph encoding (a predicate is not enough)

`origins` mints an **indexed node** emitting 6+ triples into the **provenance** graph, with
conditional branches (agent vs literature) and a `cite:` codec (`materialize.py:928`).
Capabilities are lists of mappings. One `predicate` string cannot express any of it.

```yaml
science:graph:
  policy:      omit | literal | reference | reference-list | node | codec
  graph:       knowledge | provenance          # target named graph
  predicate:   sci:disposition                 # for literal/reference/reference-list
  cardinality: one | many
  datatype:    xsd:date | xsd:boolean | ...    # literal only
  resolver:    entity-ref | citekey | none     # reference* only
  codec:       origins | capabilities | ...    # node/codec only — named, registered encoder
```

**`omit` is a first-class, legitimate choice.** The graph is a *derived view*, not a complete
replica of frontmatter. The rule is not "every field must be materialized" — it is **"every
field must make an explicit, declared decision about materialization."** Silence is what
produced `phase`.

## 6. Concern C — ownership & composition

Today a project **cannot** add a field to a core kind. `sources.py:269` (`_graduated_skip`)
*actively refuses* a profile kind that shadows a core kind and instructs the author to delete
the declaration. So `discussion.focus_type` is not merely undefined — it is **structurally
impossible**, which is exactly why it lives as an undeclared key read by `fm.get()`.

Project-local vocabulary is a **real need** (`commands/discuss.md` documents it as a feature;
mm30's `mm30_treatment_axis`; cancer-evolution's literature-import fields). The fix is to make
it **explicit**, not to forbid it:

- A project declares an **extension component** in its `schema_profile` that is **additive
  only**: it may *add* fields to a core kind; it may **not** redefine or retype a core field.
- Conflicts resolve through the **existing** `science:merge` policy: `PROJECT_ONLY` is already
  precisely "this field belongs to the project, not to commons."
- `_graduated_skip`'s blanket refusal is narrowed: reject **redefinition** of a core field
  (the stale-shadow case it was written for), permit **additive augmentation**.
- Predicate ownership: project-local fields materialize into a project-scoped namespace, never
  into `sci:`.

## 7. Concern B — the status split, with an explicit field contract

### 7.1 The measured collapse

Decomposing every vocabulary against the lifecycle words
`{draft, active, complete, superseded, retired, archived}`: **22 kinds are pure lifecycle**
(each hand-rolling a different arbitrary subset — `finding`/`observation`/`mechanism`/
`synthesis` are *identical*), and **10 fuse a semantic axis into the same string**. The
collapse is quantifiable — *the more semantic values a kind has, the fewer lifecycle words
survive, because they compete for one field*:

| kind | semantic values | lifecycle words left |
|---|---|---|
| `hypothesis` | 6 | **1** — only `archived` |
| `story` | 2 | **1** — only `draft` |
| `workflow-run` | 2 | **1** — only `complete` |
| pure-lifecycle kinds | 0 | 4–6 |

**`proposition`** — the primary belief-bearing entity — fuses belief (`supported`,
`contested`, `weakened`) with lifecycle (`superseded`, `archived`), so it **cannot be both
superseded and formerly supported**; one value silently overwrites the other.

### 7.2 The naming decision: `status` **is** the lifecycle

`phase` in the wild is `candidate` (14) / `active` (10), on hypotheses and synthesis — a
**lifecycle-shaped vocabulary**. It was invented precisely *because* `hypothesis.status` had
no lifecycle words left. It is a hand-rolled lifecycle axis, which is why it was never
declared and never wired.

**Therefore: `status` means the entity lifecycle, uniformly, on every kind.** Domain-specific
state moves to explicitly named fields per kind.

**They are not all one category.** Calling every named field a "semantic verdict" was a
flattening error. The domain axes are of *different kinds*, and conflating them is how the
collapse happened in the first place:

| category | asks | kinds |
|---|---|---|
| **verdict** (epistemic) | what does the evidence conclude? | `hypothesis.verdict`, `proposition.belief` |
| **answeredness** | is the question resolved? | `question.answer_state` |
| **execution outcome** | how did the run terminate? | `workflow-run.outcome` |
| **maturity** | how developed is the artifact? | `story.maturity` |
| **commitment** | is the plan frozen? | `pre-registration.commitment` |

This is the low-churn *and* the truthful choice: 22 of 33 kinds already use `status` this way,
and it means **natural-systems writing `status: active` on a hypothesis was correct all
along** — they had nowhere to put the verdict. It does, however, **invert part of the
fb-2026-07-11-005 ruling** (which made `status` the epistemic verdict on hypothesis). That
inversion is deliberate and is called out in §9 as decision D1.

### 7.3 The field contract (all 10 mixed kinds)

> **⚠️ CORRECTED BY THE D4 AUDIT** —
> [`2026-07-12-d4-status-vocabulary-audit.md`](2026-07-12-d4-status-vocabulary-audit.md) §5.
> The table below was written before the audit and **four rows are wrong**:
>
> | kind | this table said | audit found |
> |---|---|---|
> | `dataset` | no domain axis; `candidate` → `draft` | **`candidate` is an ACQUISITION-STATE axis** (not-yet-acquired vs acquired). **357 entities.** Do NOT map it to `draft`. |
> | `paper` | *(absent)* | **MISSING ROW** — a real reading/access axis (`unread → abstract-read → read → summarized`, + `paywalled`/`preprint`), 41 files; its only declared non-`active` value has **0** uses |
> | `synthesis` | no domain axis | its real axis is **`report_kind`** — undeclared, dropped by `extra="ignore"`, yet **branched on for control flow** from raw frontmatter |
> | `plan` | no domain axis | a **readiness axis** (`ready`/`ready-with-caveats`/`not-ready`) is being invented in `commands/plan-analysis.md` |
> | `workflow-run` | `outcome`: complete \| failed | **`running` and `failed` are DEAD** — indistinguishable to every consumer. Only `complete` is real. |
>
> Also: **the capability model is amended.** Capabilities are real (they are gated by code),
> but their *current assignment to kinds carries no recoverable intent* — the guard test D4
> leaned on turns out to pin one commit's ad-hoc enumeration. Capabilities must be **assigned
> by design**, not excavated. And **four of the six (`draftable`, `completable`, `retirable`,
> `deferrable`) have no implementing gate at all** — they must be built or dropped.

`status` (lifecycle) is **always present**, default `active`. Domain fields are **absent = not
yet assessed**, which is *distinct* from every explicit value.

**That absence rule is load-bearing, and it disqualifies values that merely restate
"unassessed."** A `verdict` of `proposed` or `under-investigation` says nothing about what the
evidence concludes — it says the evidence has not spoken. Admitting them would make
`verdict: proposed`, `verdict: under-investigation`, and *absent* three spellings of the same
state, re-collapsing the axis this design exists to split. **They are lifecycle, not verdict.**
The same pass is applied to every other domain axis: `deferred` is workflow, not answeredness;
`running` is execution state, not an outcome.

**THE AUDITED CONTRACT.** (Rows below are post-D4. The pre-audit draft got `dataset`,
`paper`, `synthesis`, `plan` and `workflow-run` wrong; those rows are **replaced**, not
annotated — a warning above contradictory contract text is unsafe input to a plan.)

| kind | → `status` (lifecycle) | → domain field (category) | default | audit note |
|---|---|---|---|---|
| `hypothesis` | **draft**(←proposed) / **active**(←under-investigation) / **complete** / superseded / retired / archived | **`verdict`** *(epistemic)*: partially-supported \| supported \| weakened \| refuted | **absent** | only `refuted` has a reader (`dataset_capabilities.py:46`) |
| `proposition` | draft / active / complete / superseded / retired / archived | **`belief`** *(epistemic)*: supported \| contested \| weakened | **absent** | belief axis has **0 authored, 0 readers** — belief is already computed from evidence-lines; `graph/belief.py` reads **no** status |
| `question` | active / **deferred** / complete / retired / archived | **`answer_state`** *(answeredness)*: answered \| partially-answered | **absent** | the **only** kind whose values drive behaviour; both selectors are two-axis (§2 of the audit) |
| `pre-registration` | draft / active / complete / superseded / retired | **`commitment`**: committed \| amended | **absent** | `committed` is **INERT** — the freeze is enforced nowhere (fb-2026-07-12-009) |
| **`dataset`** | draft / active / retired(←deprecated) | **`acquisition`**: candidate \| acquired | **`candidate`** | **CORRECTED.** `candidate` = *not yet acquired*, **357 entities**. NOT a draft synonym. |
| **`paper`** | active / retired | **`reading_state`**: unread \| abstract-read \| read \| summarized *(+ access: paywalled \| preprint \| stub)* | **absent** | **NEW ROW.** 41 authored files on an undeclared axis; declared `retired` has **0** uses |
| **`synthesis`** | active / complete / superseded / retired / archived | **`report_kind`**: hypothesis-synthesis \| synthesis-rollup \| emergent-threads \| cluster-digest | **required** | **NEW ROW.** Undeclared today, dropped by `extra="ignore"`, yet **branched on for control flow** in 5 places |
| **`plan`** | draft / active / complete / superseded / retired / archived | **`readiness`**: ready \| ready-with-caveats \| not-ready | **absent** | **CORRECTED.** The axis is being invented in `commands/plan-analysis.md:118`; a `not-ready` plan is `active` *and* not-ready |
| **`workflow-run`** | active *(in flight)* / superseded / archived | **`outcome`** *(execution)*: complete \| failed | **absent = in flight** | **CORRECTED.** `running`/`failed` are **dead** — indistinguishable to every consumer. Only `complete` is read (gates readiness). |
| `story` | draft / active / complete / superseded / archived | **`maturity`**: developing \| mature | absent | 0 entities, 0 readers; its CLI writer raises `_retired_writer`. **Nothing to preserve** — choose from scratch. |
| `concept` / `decision` / `workflow` | active / retired(←deprecated, ←abandoned, ←planned) / superseded / archived | *none* | — | **CONFIRMED** lifecycle synonyms: 0 readers, 0 authored uses |

Consequences worth stating plainly:

- **Only three of the ten pre-audit "mixed" kinds were what I thought.** The audit added
  `paper` and `synthesis` (genuine axes I had missed entirely), reclassified `dataset` and
  `plan` (axes I had wrongly called synonyms), and gutted `workflow-run`'s.
- **`complete` is mandatory on every kind that can conclude.** Without it, a successfully
  concluded hypothesis is forced into `retired`, which elsewhere means abandoned or
  indefinitely blocked — and `disposition` cannot be declared redundant until that hole is
  closed. Rev 2 omitted `complete` from hypothesis; that was a defect.
- **`deferred` needs a home on the lifecycle axis**, not on answeredness. It is a *paused* state
  and none of `{draft, active, complete, superseded, retired, archived}` means paused. This is a
  genuine gap in the lifecycle vocabulary and is exactly the sort of thing the D4 excavation must
  settle — provisionally, `deferred` is proposed as a lifecycle capability, not forced into an
  existing word.

**Allowed combinations.** The axes are orthogonal, and the load-bearing cells are:

| lifecycle + domain | means |
|---|---|
| `active` + `verdict: refuted` | refuted, but still being worked (writing it up) |
| `complete` + `verdict: supported` | supported and concluded |
| `retired` + `verdict` **absent** | pragmatically stopped while epistemically undecided |
| `superseded` + `verdict: supported` | *formerly* supported, now replaced — **the cell `proposition` literally could not express** |

That last row is the whole argument: under the old collapsed field, `superseded` overwrote
`supported` and the belief was silently lost.

**Orthogonal does NOT mean every combination is legal.** An earlier draft of this section said
"no combination is forbidden," which was wrong, and it contradicted §7.4. Axis independence is
a statement about *representation* — the two facts can be recorded separately — not a licence
to record a terminal state with no reason for it. Cross-field invariants are precisely what the
JSON Schema authority (§4) exists to express, and the terminal-transition invariant in §7.4 is
one of them.

### 7.4 `phase` is deleted; `disposition` is deleted; the *basis* survives

- **`phase`** (candidate|active) is the hand-rolled lifecycle. It **folds into `status`**:
  `phase: candidate` → `status: draft`; `phase: active` → `status: active`. The `phase:` key is
  then **deleted from the templates** (P0's "declare or delete" rule), not migrated forward.
  ⚠️ This changes `/science:big-picture`'s "Candidate frames" selector, which reads
  `phase == "candidate"`; it becomes `status == "draft"`.

- **`disposition` is DELETED** (shipped in `d2fc4d13`; two days old is not an argument for
  keeping it). Openness is **derived** from the lifecycle, not stored:

  | lifecycle | open? |
  |---|---|
  | `draft`, `active` | **open** |
  | `complete`, `superseded`, `retired`, `archived` | **closed** |

  Every fb-005 cell survives without a third state field — see the combination table in §7.3.
  A stored boolean that is a pure function of `status` is a denormalization waiting to
  disagree with its source.

- **`disposition_basis` SURVIVES, renamed `closure_basis`.** This is the asymmetry that
  matters: **the state is derivable; the authored reason is not.**

  ### The invariant

  > **A terminal entity requires either a PRESENT, VALID structural basis for that transition,
  > or `closure_basis`.**

  The condition is the **presence of the structure**, never the status word. An earlier draft
  keyed the requirement off the terminal value alone — assuming `superseded` *has* lineage,
  `archived` *has* an archive record, `complete` *has* a verdict. **None of those is
  guaranteed**, and one is explicitly guaranteed false: the live-lineage contract
  (`2026-07-02-phase4e-live-lineage-visibility-design.md`) states that *"live `status:
  superseded` without lineage emits no lineage edge and **does not fail**."* So a lineage-less
  `superseded` would have slipped through with no reason recorded anywhere — the exact hole
  `closure_basis` exists to close. Likewise `status: archived` is a *status*, not a physical
  archive location; the two can diverge.

  | terminal | structural basis that discharges the requirement | if that basis is ABSENT |
  |---|---|---|
  | `superseded` | valid lineage (`supersedes:` / `superseded_by` / `resynthesized_into`) resolving to a live successor | **`closure_basis` required** |
  | `archived` | an archive / consolidation record | **`closure_basis` required** |
  | `complete` | a verdict **plus** qualifying evidence | **`closure_basis` required** |
  | `retired` | *(none exists)* | **`closure_basis` ALWAYS required** |

  `retired` is the only terminal with no structural basis available to it, so it always
  requires an authored one. The others require one **exactly when their structure is missing**.

  ### Where the invariant is ENFORCED — two layers, not one

  An earlier draft said this invariant "lives in JSON Schema." **That is only half true, and the
  half that is false is the load-bearing half.** JSON Schema validates **one record in
  isolation**; it cannot resolve a successor ID, cannot confirm an archive record exists, and
  cannot check that a verdict's evidence is real. Those are **cross-record** facts.

  | layer | enforces | example |
  |---|---|---|
  | **JSON Schema** (§4) — local shape & presence | *"if `status` is terminal and the basis KEY is absent, `closure_basis` is required"* | `status: superseded` with no `superseded_by:`/`resynthesized_into:` key ⇒ `closure_basis` required |
  | **Enumerated D3 escape-hatch validator** — structural resolution | *"the basis key is present, but does it RESOLVE?"* | `superseded_by: hypothesis:9999` (dangling); an `archived` entity with no archive-index row; `complete` + a `verdict` whose evidence does not exist |

  This is exactly the D3 escape hatch, used as designed: an invariant JSON Schema genuinely
  cannot express, declared explicitly and backed by a contract test — **not** an open-ended
  second authority. Presence is schema; **resolution is a validator**. Getting this wrong would
  re-open the hole in a subtler form: a *present but dangling* `superseded_by:` would satisfy
  the schema and close the entity with no real reason behind it.

  **Open sub-decision:** `complete` + `verdict` **absent** may instead be *prohibited outright*
  for kinds carrying a verdict axis, rather than admitted with a `closure_basis`. Prohibition is
  cleaner ("you cannot conclude without concluding something"); admission is more permissive for
  work concluded on non-epistemic grounds. **Settle in the D4 audit, per kind.**

  This preserves and strengthens the fb-005 guarantee: closure cannot silently bury research
  debt, *and* it can no longer be discharged by a terminal word that merely looks structured.

## 8. Phasing

### The rule that fixes the earlier contradiction

An earlier draft put `phase` folding, `disposition` deletion, and the `status` reinterpretation
in **P0** while P0 promised *zero downstream source migration*. **Those cannot coexist.**
Existing files carry a *semantic* `status` and a *lifecycle* `phase`. Changing the templates and
consumers without rewriting the sources leaves **two incompatible meanings of `status` live at
once**, and the only way to serve both is the heuristic compatibility layer **D5 explicitly
forbids**.

> **P0 does not change meaning. It only inventories and certifies the field surfaces as they
> are.** Every change of meaning belongs to a versioned migration slice that moves schema,
> sources, templates and consumers **together, atomically, per kind.**

- **P0 — Inventory & certify (no reinterpretation).**
  Enumerate every field a template or toolkit writes; classify each as *declared+wired*,
  *declared+`omit`*, or *undeclared*. Adjudicate the undeclared ones — `role`, `input`,
  `report_kind`, `committed`, `spec`, `promoted_from` — as declare-or-delete. **`phase`,
  `disposition` and the `status` reinterpretation are explicitly NOT in P0**; they move to P2m.
  P0 is *zero downstream source migration* and *not* zero downstream churn — wiring a
  previously-dropped field still changes rebuilt graphs, dashboards, attention ranking and
  validation output. **P0 therefore requires downstream graph/output compatibility checks,
  including commons wherever a shared field is touched.**
- **P1 — Absorb the real subsystems.** `provided_capabilities`/`required_capabilities` is a
  designed capability-matching subsystem with its own validator and seven design docs, reading
  raw frontmatter, bypassing the model, invisible to the graph. Make it first-class.
- **P2 — Converge the two schema systems.** Project-authored kinds adopt `schema_profile`;
  `dataset`/`paper` stop having two definitions; commons compatibility is a gate, not an
  afterthought.
- **P2m — The versioned migration slices (one per kind, ATOMIC).** This is where meaning
  changes. Each slice, for exactly one kind, does all of the following **or none of it**:
  1. introduce the **target schema version**;
  2. **rewrite the sources** (deterministic mappings applied; ambiguous ones **refused** and
     sent for authored adjudication — D5);
  3. update the **templates**;
  4. update the **consumers/selectors** (e.g. big-picture's Candidate-frames selector
     `phase == "candidate"` → `status == "draft"`; attention ranking; `DEBT_QUESTION_STATUSES`);
  5. **graph/output diff** the result, including commons where shared fields are touched.

  `hypothesis` is the first slice: it carries `phase` **and** `disposition` **and** the `status`
  reinterpretation, so it is the one place all three land together — which is precisely why they
  must not be scattered across P0.
- **P3 — Then strictness**, WARN first, ratcheting to ERROR **per kind**, only after that kind's
  sources *and* consumers are certified. Severity is a property of the **kind**, never of
  `layout_version` (the axis that already failed).

## 9. Decisions — RULED (2026-07-12)

### D1 — `status` is the lifecycle. **Adopted.**

With the correction that disqualifies non-verdict values from `verdict` (§7.3): `proposed` and
`under-investigation` are lifecycle, not epistemic conclusions, and admitting them would make
three spellings of "unassessed". Same pass applied to `deferred` (workflow, not answeredness)
and `running` (execution state, not an outcome). Domain axes are **categorised**, not lumped
(§7.2).

### D2 — Delete `disposition`; keep the reason. **Adopted.**

Openness is derived from lifecycle. `disposition_basis` → **`closure_basis`**, required on
terminal transitions with **no structural basis** — in practice, `retired` (§7.4). `complete`
is added to every kind that can conclude; without it the deletion would be unsound, because a
concluded hypothesis would be forced into `retired` (= abandoned). fb-005 is **retained as
history with its superseded portion explicitly marked**, not rewritten away.

### D3 — Projection + reconciliation. **Adopted**, with a five-point contract:

1. Raw frontmatter is validated against its **composed JSON Schema first**.
2. The Pydantic projection is constructed **only after** schema validation passes.
3. **Projections MUST preserve schema-valid extension fields.** Never return to
   `extra="ignore"` — that is the original defect, and re-introducing it at the projection
   layer would silently undo the whole design.
4. A **CI reconciliation check** verifies every projected field against the effective composed
   schema.
5. Any invariant JSON Schema cannot express is an **enumerated escape hatch with a contract
   test** — not an open-ended second authority.

Generation is rejected: it adds build machinery without removing the need for methods,
ergonomic nested types, and runtime checks.

### D4 — RULED (post-audit): **two operational capabilities; lifecycle states are not capabilities.**

> **A capability denotes an OPERATION with distinct behaviour — not permission to use an enum
> value.**

The audit ([`2026-07-12-d4-status-vocabulary-audit.md`](2026-07-12-d4-status-vocabulary-audit.md))
ran and **refuted the premise D4 was commissioned on.** The earlier text here claimed
`test_reference_kind_does_not_gain_archived` proved `paper`/`book`/`talk` were *deliberately*
non-consolidatable. **It proves no such thing** — the guard pins one commit's ad-hoc
enumeration, its own rationale misnames `paper`/`book`/`talk` as "reference kinds" when they are
OPERATIONAL (the actual REFERENCE kinds, `topic`/`decision`, **were** given `archived`),
`sci:consolidates` declares `target_kinds=[]`, and `consolidate.py:77-80` tells the operator to
*go add `archived` to the kind*. The code treats the exclusion as **removable configuration**.

**So: capabilities are real, but their current assignment to kinds carries no recoverable
intent. Assign them BY DESIGN, kind by kind. Do not excavate.**

**Keep exactly two capabilities** — the two that gate an operation with distinct behaviour:

| capability | gates | admits |
|---|---|---|
| **`supersedable`** | the supersession operation, lineage edges, visibility change (`consolidation.py:74`, `materialize.py:177`) | `status: superseded` |
| **`consolidatable`** | the consolidation/archive machinery (`consolidate.py:49`, `archive.py:22`) | `status: archived` |

**Drop `draftable`, `completable`, `retirable`, `deferrable` as capabilities.** They have **no
implementing gate**, and inventing four specialized verbs to justify them is unwarranted product
scope. **Their lifecycle STATES are retained** — `draft`, `active`, `complete`, `retired`,
`deferred` are declared per kind by the schema, exactly like any other enum value.

**One generic lifecycle boundary, not four verbs.** `science entity edit --status` is *already*
the transition surface. D5 strengthens it rather than multiplying it:

1. validate the target status against the **composed schema**;
2. accept **`--closure-basis` atomically** with a terminal transition;
3. **enforce the terminal-basis invariant** (§7.4 — schema for presence, validator for
   resolution);
4. update the **two-axis consumers** (question debt, demand-closure) in the same transaction;
5. **fail before writing** when a requirement is unmet.

*(Alternatives rejected: four dedicated capabilities + commands — unjustified scope. A generic
transition-capability DSL — elegant, but another abstraction with no demonstrated transition
graphs behind it.)*

**Bidirectional consistency gates** (these would have caught the live half-wiring):

```
supersedable   ⇔ schema admits `superseded`
               ⇔ the lineage RelationKind admits the kind as an endpoint
               ⇔ the supersession operation handles the kind

consolidatable ⇔ schema admits `archived`
               ⇔ the archive/consolidation machinery handles the kind
```

The first gate fails **today**: `topic`/`decision`/`theme` declare `superseded` and are
auto-stamped by `consolidation.mark_superseded`, but `sci:supersedes` (`core.py:687-701`)
**forbids them as endpoints**, so authoring the canonical edge raises `ValueError` in
`materialize`. The vocabulary and the relation model disagree, and nothing notices.

**`entity_class` must NOT imply capabilities** — confirmed by the audit, which found it does
not track them today (REFERENCE `topic`/`decision` are consolidatable; OPERATIONAL
`paper`/`book`/`talk` are not; OPERATIONAL `method`/`plan`/`search` are).

### D5 — Versioned, report-before-apply, fail-early migration. **Adopted.**

Not additive-only. **No heuristic compatibility layer.**

1. Inventory raw values per kind and per project.
2. Separate **deterministic** mappings from **ambiguous** ones.
3. Introduce target schema **versions**; update templates and consumers.
4. Migrate **one kind at a time**, with graph/output diffs.
5. **Refuse ambiguous rewrites** and request authored adjudication — do not guess.
6. Ratchet **WARN → ERROR per kind**, only after that kind's sources *and* consumers are
   certified.

Two named information-loss traps, to be reported rather than papered over:

- **Do not** mechanically map `disposition: closed` → `status: retired`. The author must
  distinguish `complete` (concluded), `retired` (abandoned) and `superseded` (replaced). Those
  are three different facts and the boolean does not carry which.
- An existing `status: archived` **has already destroyed its prior verdict.** Leave `verdict`
  **absent** and **report the information loss**. Inventing a verdict to fill the column would
  be fabricating an epistemic conclusion — the precise failure the InstrumentResult ruling
  exists to prevent.

## 10. Revision history

### rev 3 (2026-07-12) — D1–D5 ruled

All five decisions ruled (§9). Three substantive corrections came out of the ruling, each
fixing a defect in rev 2:

- **`verdict` must not contain `proposed`/`under-investigation`.** They say the evidence has
  not spoken, not what it concluded — so they would have made `verdict: proposed`,
  `verdict: under-investigation` and *absent* three spellings of one state, re-collapsing the
  axis the design exists to split. Same pass applied to `deferred` and `running`. Domain axes
  are now **categorised** (verdict / answeredness / execution / maturity / commitment), not
  flattened into one "semantic" bucket.
- **rev 2 omitted `complete` from the hypothesis lifecycle.** That was a real defect: without
  it, a successfully concluded hypothesis is forced into `retired` (= abandoned), and
  `disposition` could not be soundly deleted. `complete` is now mandatory on every kind that
  can conclude.
- **`disposition_basis` survives as `closure_basis`.** The state is derivable; **the authored
  reason is not.** Required on terminal transitions carrying no structural basis — i.e.
  `retired`, which is exactly the transition that records its reason nowhere else.

fb-005 is retained as history with its superseded portion explicitly marked in
`2026-07-11-big-picture-identity-design.md` §5.2.

### rev 2 (2026-07-12) — what changed after the six-issue review


Rev 1 was reviewed and six issues were raised; all six were verified against the code and all
six were correct.

1. **Field rows cannot express invariants** → §4. Confirmed: 20 `@model_validator`s, including
   conditional `derived_kind`/`source_class`. JSON Schema is now the authority for shape *and*
   invariants; `EntityKind.fields` is withdrawn.
2. **A predicate cannot derive materialization** → §5. Confirmed: `origins` emits an indexed
   node, 6+ triples, into the *provenance* graph, with a `cite:` codec. Explicit graph policy
   added, with `omit` first-class.
3. **Project-local is undefined and impossible** → §6. Confirmed: `_graduated_skip`
   (`sources.py:269`) actively refuses it. And ownership is a **scope, not an axis** — B and C
   are now independent dimensions.
4. **The existing shared-entity schema system was omitted** → §2. **The most important
   correction.** `entity_schema/` is versioned, composable, annotation-driven, declares JSON
   Schema the source of truth, and governs 369 commons records. Rev 1 would have built a third
   parallel system. The goal is now *convergence*, and `science:axis`/`science:graph` follow the
   existing `science:merge` annotation precedent rather than inventing a new mechanism.
5. **No field contract for the split** → §7.3, the full table for all 10 mixed kinds, with
   defaults and absence semantics. Producing it surfaced that **four of the ten have no semantic
   axis at all** (only lifecycle synonyms), and that **`phase` is a hand-rolled lifecycle** —
   which flipped the naming decision (D1) and put `disposition` itself in question (D2).
6. **P0 is not "zero downstream churn"** → §8. Rephrased to zero downstream *source* migration,
   with mandatory graph/output compatibility checks including commons.

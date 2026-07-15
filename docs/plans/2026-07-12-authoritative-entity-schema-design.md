# The authoritative entity schema

**Date:** 2026-07-12 (rev 9 — `verdict` basis scoped + compatibility ruled as a MATRIX, not a ladder; see §10)
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

> **Its resolution is DELETION, not a split (rev 6).** Every other collapsed kind gets its
> semantic values *moved* to a named field. `proposition` does not: those three values have **0
> authored instances and 0 readers**, and the meaning they gesture at is **already owned by
> derived belief**. So there is nothing to move and nothing to preserve — the values are dropped,
> `status` becomes pure lifecycle, and belief stays computed. **The collapse here was never
> load-bearing; it was vestigial.** See §7.3.

### 7.2 The naming decision: `status` **is** the lifecycle

`phase` in the wild is `candidate` / `active`, on hypotheses and synthesis — a
**lifecycle-shaped vocabulary**. It is a hand-rolled lifecycle axis, which is why it was never
declared and never wired.

> **Corrected in rev 7.** This section used to add: *"it was invented because `hypothesis.status`
> had no lifecycle words left."* The cross-tab refutes the second clause. `status` had no
> lifecycle words **because it never held any** — `proposed` and `under-investigation` only *look*
> like lifecycle; they are the collapsed field's way of saying *"the evidence has not spoken,"*
> which D1 already ruled is `verdict`-absent, not a state. So the authors who reached for `phase`
> were **not** working around a vocabulary gap. **They were separating the two axes by hand,
> correctly, before this design existed.** `phase` is the lifecycle; `status` was only ever the
> verdict. See §10 rev 7 for the data and the corrected mapping.

**Therefore: `status` means the entity lifecycle, uniformly, on every kind.** Domain-specific
state moves to explicitly named fields per kind.

**They are not all one category.** Calling every named field a "semantic verdict" was a
flattening error. The domain axes are of *different kinds*, and conflating them is how the
collapse happened in the first place:

| category | asks | kinds |
|---|---|---|
| **verdict** (epistemic) | what does the evidence conclude? | `hypothesis.verdict` — **and nothing else** |
| **answeredness** | is the question resolved? | `question.answer_state` |
| **execution outcome** | how did the run terminate? | `workflow-run.outcome` |
| **maturity** | how developed is the artifact? | `story.maturity` |
| **commitment** | is the plan frozen? | `pre-registration.commitment` |
| **acquisition** | do we have the bytes yet? | `dataset.acquisition` *(D4)* |
| **reading state** | how far have we read it? | `paper.reading_state` *(D4)* |
| **record kind** | which flavour of report is this? | `synthesis.report_kind` *(D4)* |
| **readiness** | is the plan fit to execute? | `plan.readiness` *(D4)* |

> **The verdict row has exactly one member, and that is deliberate (rev 6).** Rev 5 listed
> `proposition.belief` here. It does not belong: **belief is derived from evidence lines, not
> authored** — see the `belief` bullet in §7.3. An authored `belief` field would be a second,
> hand-editable source of truth for a computed quantity, and the one place a human could write a
> conclusion the evidence does not support. `proposition` therefore gets **no domain axis at
> all**.

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
> | `paper` | *(absent)* | **MISSING ROW** — a real reading axis (`unread → abstract-read → read → summarized`), 41 files; its only declared non-`active` value has **0** uses. (The audit lumped `paywalled`/`preprint`/`stub` in here; **rev 6 unbundles them** — they are access, publication-version, and record-completeness, not reading progress. → D5 adjudication.) |
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
| `hypothesis` | **draft** / **active** / **complete** / superseded / retired / archived — **sourced from `phase`, NOT from `status`** (see rev 7) | **`verdict`** *(epistemic)*: partially-supported \| supported \| weakened \| refuted | **absent** | only `refuted` has a reader (`dataset_capabilities.py:46`) |
| `proposition` | draft / active / complete / superseded / retired / archived | ***none*** | — | **CORRECTED (rev 6).** `supported`/`contested`/`weakened` are **dropped, not migrated** — 0 authored instances, 0 readers. Belief is **derived**, and stays derived. |
| `question` | active / **deferred** / complete / retired / archived | **`answer_state`** *(answeredness)*: answered \| partially-answered | **absent** | the **only** kind whose values drive behaviour; both selectors are two-axis (§2 of the audit) |
| `pre-registration` | draft / active / complete / superseded / retired | **`commitment`**: committed \| amended | **absent** | `committed` is **INERT** — the freeze is enforced nowhere (fb-2026-07-12-009) |
| **`dataset`** | draft / active / retired(←deprecated) | **`acquisition`**: candidate \| acquired | **`candidate`** | **CORRECTED.** `candidate` = *not yet acquired*, **357 entities**. NOT a draft synonym. |
| **`paper`** | active / retired | **`reading_state`**: unread \| abstract-read \| read \| summarized | **absent** | **NEW ROW, CORRECTED (rev 6).** 41 authored files on an undeclared axis; declared `retired` has **0** uses. `paywalled`/`preprint`/`stub` are **NOT** reading states → D5 adjudication inventory (see below). |
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
- **`deferred` is an ordinary lifecycle state** admitted by the `question` schema — *not* a
  capability. It is a *paused* state, and none of `{draft, active, complete, superseded, retired,
  archived}` means paused, so the word is genuinely needed on the lifecycle axis (it is **not**
  answeredness). But under the ruled capability contract (§9, D4) a capability denotes an
  **operation with distinct behaviour**, and pausing has none: there is no `defer` operation, no
  gate, no consumer that branches on deferral beyond reading the enum. An earlier draft called it
  "provisionally a lifecycle capability"; that contradicted the adopted ruling and is **struck**.
  It is a value in an enum, and that is all it needs to be.

- **`belief` is NOT authored, and this design does not make it authored.** The pre-audit draft
  proposed lifting `supported`/`contested`/`weakened` off `proposition.status` onto an authored
  `belief` field. That was wrong on its own evidence — the audit found **0 authored instances and
  0 readers**, and belief is *already* computed from evidence lines (`graph/belief.py` reads no
  status at all; the user guide defines belief as derived in
  [`big-picture.md`](../user-guide/big-picture.md) and [`entities.md`](../user-guide/entities.md)).
  Minting an authored field would have created a **second, hand-editable source of truth for a
  derived quantity** — a denormalization of exactly the kind §7.4 deletes `disposition` to avoid,
  and worse, one an author could set to contradict the evidence. **The three values are dropped
  with no migration target** (there is nothing to migrate). Derived belief and its snapshots keep
  sole ownership of that meaning.

**Allowed combinations.** The axes are orthogonal, and the load-bearing cells are:

| lifecycle + domain | means |
|---|---|
| `active` + `verdict: refuted` | refuted, but still being worked (writing it up) |
| `complete` + `verdict: supported` | supported and concluded |
| `retired` + `verdict` **absent** | pragmatically stopped while epistemically undecided |
| `superseded` + `verdict: supported` | *formerly* supported, now replaced — **the cell the collapsed field literally could not express** |

That last row is the whole argument: under one collapsed `status`, writing `superseded`
**overwrote** `supported`, and the epistemic conclusion was silently destroyed by a
bookkeeping transition. (Rev 5 illustrated this with `proposition`; rev 6 drops that kind's
domain axis entirely, so the example is now `hypothesis` — the loss is identical and the
argument is unchanged.)

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
  `archived` *has a referenceable archive record*, `complete` *has* a verdict. **None of those is
  guaranteed** — the middle one is not even expressible (see the correction below) — and one is
  explicitly guaranteed false: the live-lineage contract
  (`2026-07-02-phase4e-live-lineage-visibility-design.md`) states that *"live `status:
  superseded` without lineage emits no lineage edge and **does not fail**."* So a lineage-less
  `superseded` would have slipped through with no reason recorded anywhere — the exact hole
  `closure_basis` exists to close. Likewise `status: archived` is a *status*, not a physical
  archive location; the two can diverge.

  | terminal | structural basis that discharges the requirement | if that basis is ABSENT |
  |---|---|---|
  | `superseded` | valid **local** lineage (`superseded_by` / `resynthesized_into`) resolving to a live successor — **not** top-level `supersedes:`, which is silently dropped (fb-2026-07-11-017); the *canonical* `relations:` edge lives on the **other** record, where a single-record schema cannot see it (rev 10) | **`closure_basis` required** |
  | `archived` | ***(none exists)*** — **CORRECTED 2026-07-13** | **`closure_basis` ALWAYS required** |
  | `complete` | a verdict **plus** qualifying evidence | **PROHIBITED** — not basis-discharged. See the rev-6 ruling below. |
  | `retired` | *(none exists)* | **`closure_basis` ALWAYS required** |

  > **`archived` has no structural basis, because the reference it would need cannot be written.**
  > This row said "an archive / consolidation record", and D5 Task 6 tried to give it a field
  > (`archive_ref`) — then found the referent does not exist. `archive.py` keys its index by the
  > archived entity's **own id** (`ArchiveIndex.active_by_id`) and **mints no record identifier**,
  > so there is nothing for a ref to point AT: an archived entity's record is already reachable
  > from `id` alone, and authoring a pointer to it would be a second, unversioned spelling of a
  > derivable fact. **`archived` therefore behaves exactly like `retired`** — an authored
  > `closure_basis`, always. **`superseded` is the ONLY terminal with resolvable structure**, and
  > it is the only one the cross-record validator below has anything to resolve.

  `retired` **and `archived`** have no structural basis available to them, so they **always**
  require an authored one. `superseded` is the **only** terminal with resolvable structure, and
  it requires an authored basis **exactly when that structure is missing**. `complete` is the
  exception in the other direction: for a verdict-bearing kind its structure is **mandatory** and
  no authored reason substitutes (ruled below).

  > **Superseded rev 10 — where the lineage actually LIVES.** `superseded` has structure, but
  > that structure is authored on the **successor**, not on the entity it closes: the canonical
  > edge is a `relations:` entry with `predicate: sci:supersedes` (`consolidation.py:7-12`),
  > pointing newer → older. A JSON Schema sees **one record in isolation**, so it can never read
  > it. `superseded_by` on the closed record is therefore the **derived inverse** — materialized
  > *by the tool* (`mark_superseded`) from the canonical edge, so that the closed record carries
  > its own reason and is valid on its own terms. It is **not** a second authored spelling of
  > supersession, and it is **not** the deleted top-level `supersedes:` (fb-2026-07-11-017); it
  > is the projection that makes single-record validation possible at all. **Author the edge;
  > the inverse is written for you.**

  ### Where the invariant is ENFORCED — two layers, not one

  An earlier draft said this invariant "lives in JSON Schema." **That is only half true, and the
  half that is false is the load-bearing half.** JSON Schema validates **one record in
  isolation**; it cannot resolve a successor ID and cannot check that a verdict's evidence is
  real. Those are **cross-record** facts.

  | layer | when | enforces | example |
  |---|---|---|---|
  | **JSON Schema** (§4) | load | local shape & **presence** | `status: superseded` with no `superseded_by:`/`resynthesized_into:` key ⇒ `closure_basis` required |
  | **Enumerated D3 escape-hatch validator** | load | structural **resolution** *(cross-record)* | `superseded_by: hypothesis:9999` (dangling). **Lineage is the ONLY thing it resolves** — `archived` has no resolvable structure (see above), so there is no archive-existence check and never was one to write. |
  | **Graph check** | **materialize** | evidential **sufficiency** | `complete` + a `verdict` whose qualifying evidence does not exist |

  > **Three layers, not two — corrected while writing D5.** An earlier draft put
  > *"`complete` + a verdict whose evidence does not exist"* in the load-time validator. **It
  > cannot live there.** Qualifying evidence is carried by *evidence-line edges*, which exist only
  > **after materialization** — a load-time validator reading one file at a time cannot see them.
  > Leaving it in that row would have had the design promising an invariant the implementation
  > structurally could not deliver, which is how §7.4's *first* draft went wrong (asserting
  > structure it never checked). It is a **graph** check, and it is named here rather than
  > quietly dropped.

  This is exactly the D3 escape hatch, used as designed: an invariant JSON Schema genuinely
  cannot express, declared explicitly and backed by a contract test — **not** an open-ended
  second authority. Presence is schema; **resolution is a validator**. Getting this wrong would
  re-open the hole in a subtler form: a *present but dangling* `superseded_by:` would satisfy
  the schema and close the entity with no real reason behind it.

  ### RULED (rev 6): `complete` requires a `verdict`. There is no `closure_basis` escape.

  > **`hypothesis.status: complete` with `verdict` ABSENT is PROHIBITED.** Not admitted-with-a-
  > basis: **prohibited**. The schema rejects it.

  The rev-5 draft left this open, offering `complete` + absent-verdict + `closure_basis` as a
  more permissive alternative for work "concluded on non-epistemic grounds." **That alternative
  destroys the distinction that justified adding `complete` in the first place.** Stopping for
  non-epistemic reasons already has an exact, and *better*, spelling:

  | situation | the correct encoding |
  |---|---|
  | concluded — the evidence spoke | `status: complete` + `verdict: <the conclusion>` |
  | stopped — the evidence never spoke | `status: retired` + `closure_basis: <why you stopped>` |

  Admitting `complete` + absent + `closure_basis` would give the *second* row a **second
  spelling** — and one that reads, to every consumer and every human, as if the hypothesis had
  been *resolved*. That is the same failure mode as the collapsed `status` axis, re-introduced
  one level down: a bookkeeping state masquerading as an epistemic one. `complete` must mean
  *"you concluded something"*, and therefore it must carry **what** you concluded.

  So the `complete` row of the table above is not merely "basis required when the structure is
  missing" — for a verdict-bearing kind the structure is **mandatory**, and `closure_basis`
  cannot substitute for it. `retired` remains the only terminal that closes on an authored
  reason alone. **This is the first P2m schema's central invariant** (hypothesis is slice 1).

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

The first gate fails **today** — and **this doc understated it by a factor of four.** It named
three kinds. The gate, executed against `CORE_PROFILE`, names **twelve**: `decision`, `inquiry`,
`mechanism`, `method`, `observation`, `plan`, `pre-registration`, `proposition`, `synthesis`,
`theme`, `topic`, `workflow-step`. All twelve declare `superseded` and are auto-stamped by
`consolidation.mark_superseded`, but `sci:supersedes` (`core.py:687-701`) admits only
`interpretation`/`finding`/`discussion`/`report` (plus three status-less kinds), so **authoring
the canonical edge raises `ValueError` in `materialize`**. The vocabulary and the relation model
disagree, and nothing notices — *because the number was never computed.* **A gate stated in prose
is not a gate;** this one is now derived from `CORE_PROFILE` and executed (D5 Task 7a).

**`hypothesis` fails it in a fourth, worse way.** It does not appear in the twelve because it
**does not declare `superseded` at all**: its `EntityKind.statuses` are
`[proposed, under-investigation, partially-supported, supported, weakened, refuted, archived]` —
the **verdict** vocabulary, which is the conflation this entire arc exists to end. So across the
certified roster (**18 roots, 147 hypotheses** — `field_inventory`, D5 Task 11 Step 0): **0
superseded, 0 archived, 0 authoring `relations:`, and 0 authoring `superseded_by`,
`resynthesized_into`, `supersedes`, `closure_basis`, or `archive_ref`.** The hypothesis
supersession triangle has **never been exercised**, in any project, which is precisely why all
three of its legs could be broken at once and stay silent. That makes D5's fix greenfield — there
is nothing to migrate, and no reason to get it wrong.

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

Three named information-loss traps, to be reported rather than papered over:

- **Do not** mechanically map `disposition: closed` → `status: retired`. The author must
  distinguish `complete` (concluded), `retired` (abandoned) and `superseded` (replaced). Those
  are three different facts and the boolean does not carry which.
- An existing `status: archived` **has already destroyed its prior verdict.** Leave `verdict`
  **absent** and **report the information loss**. Inventing a verdict to fill the column would
  be fabricating an epistemic conclusion — the precise failure the InstrumentResult ruling
  exists to prevent.
- **`paper`'s `paywalled` / `preprint` / `stub` go to adjudication, NOT to `reading_state`**
  (rev 6). They are three *different* axes wearing one field: **access** (can we get the PDF?),
  **publication version** (is this the preprint or the version of record?), and **record
  completeness** (is this a real summary or a placeholder?). Forcing them into a reading
  progression would re-commit, inside the very field meant to fix it, the exact collapse this
  design exists to undo — and would assert reading progress that no author ever claimed. D5
  **inventories them and stops**; the author names the axes.

**The migration must not invent a value it was not given.** Every one of these traps has the
same shape: a rewrite that *looks* deterministic because the target column has an obvious-seeming
slot, but which manufactures a fact — a conclusion, a closure reason, a reading state — that the
source never recorded.

## 10. Revision history

### rev 8 (2026-07-12) — `verdict` ownership ruled; the belief cluster partitioned

**`hypothesis.verdict` is AUTHORED, and its semantic owner is the adjudicating author.** Not
"authored for now" — authored *by contract*. This is **not** a second instance of the `belief`
defect (rev 6), and the distinction is the whole point:

| | asks | owner |
|---|---|---|
| **derived belief** | what does the versioned evidence-aggregation **policy** currently compute? | the policy |
| **authored `verdict`** | what conclusion did the **researcher adjudicate** from the evidence, the criteria, the context, and the hypothesis's composition? | the author |

Hypothesis-level derived belief **already exists** — `graph/belief.py`'s `_claims()` iterates
`(SCI_NS.Proposition, SCI_NS.Hypothesis)`, and `aggregate_belief()` processes hypothesis evidence
lines. So the earlier phrasing *"no hypothesis-scoped derivation"* was **wrong**. What does not
exist is a **total, versioned mapping** from that belief (or from interpretation-polarity
rollups) onto `partially-supported | supported | weakened | refuted`. The correct statement is
**"there is no derived hypothesis *verdict*"** — and adjudication is not a rounding of a scalar.

**The `verdict` contract:**

1. **Absent** = no adjudication has been recorded. (Not "no evidence" — *no adjudication*.)
2. **Every authored verdict must have a qualifying, resolvable basis at graph time** — **not only
   when `status: complete`**. A verdict with nothing behind it is the fabrication this design exists
   to prevent, whatever the lifecycle says.

   > **⚠️ AMENDED (rev 9). This clause originally said "evidence **or interpretation** basis" — and
   > the interpretation half is UNIMPLEMENTABLE.** `interpretation` **is not an entity kind in the
   > graph**: the registry holds `evidence-line`, `falsification`, `hypothesis`, `mechanism`,
   > `proposition`, … and no `interpretation`, with no typed edge from one to a hypothesis. The
   > contract named a basis the graph cannot represent, so any check claiming to enforce it would be
   > lying in its own docstring.
   >
   > **A qualifying basis is therefore, today, one of exactly two things** — and note the two have
   > DIFFERENT reaches, which an earlier draft flattened into one:
   >
   > 1. an **admissible, polarity-agreeing evidence-line unit**, on the hypothesis **or one of its
   >    CORE members**. An evidence line may bear on a hypothesis directly — the `supports` and
   >    `disputes` `RelationKind`s admit it, declaring `source_kinds` that include `evidence-line`
   >    and `target_kinds=["proposition", "hypothesis"]` (`profiles/core.py:648-660`). So both
   >    reaches are real.
   > 2. a **`falsification` record** (the *"explicitly linked negative adjudication"*) on a **CORE
   >    PROPOSITION member — and ONLY there.** A falsification *on the hypothesis* **cannot exist**:
   >    `FalsificationEntity.falsifies` is REQUIRED, and materialization HARD-RAISES unless its
   >    target resolves to `kind == "proposition"` (`materialize.py:1274`, "falsification targets
   >    must be propositions"). Permitting it here would name a basis the graph refuses to store —
   >    the same defect as the interpretation clause, one paragraph up.
   >
   > Evidence on a rival/background member adjudicates nothing about this hypothesis.
   >
   > Restoring the interpretation half requires its own slice — interpretation must become a graph
   > kind with a typed edge to the hypothesis. **Until then the clause is scoped, not quietly
   > claimed.** *(Found while designing Task 7; the existing `verdict/` subsystem parses
   > interpretation **bodies** for polarity tokens and never touches hypotheses — a different
   > concept that happens to share the word.)*

2b. **Verdict compatibility is a MATRIX, not an ordinal comparison.**
   `supported | partially-supported | weakened | refuted` is **not a ladder**, and must never be
   mapped onto the belief magnitudes `speculative → fragile → supported → well_supported`:
   - a decisive refutation of **one constituent proposition** is *compatible with*
     `partially-supported` — on a ladder it reads as a contradiction;
   - **`weakened` is temporal** — it asserts a *change*, and cannot be inferred from a single current
     belief snapshot;
   - **one decisive independent test can legitimately establish `refuted`** — so a "single-source
     ceiling" would flag the strongest possible refutation. The ceiling does not merely fail to
     transfer; **it inverts.**

   The **one hard invariant** is `verdict.refutation-masked`: **`supported`** (not
   `partially-supported`) while an unresolved **decisive whole-hypothesis or core-conjunction**
   refutation stands. Everything else the computed layer says is an **explanatory disagreement
   report** — per point 4, never a ceiling and never a rewrite.

   And it must be computed from **composed** hypothesis belief (`bundle_belief.belief_for_entity`,
   weakest-link over core members), **never a flattened evidence pool** — flattening lets strong
   evidence for one proposition mask a speculative core member. Direct whole-hypothesis refutations
   must be checked **separately**, because bundle dispatch never reads evidence attached to the
   hypothesis IRI itself once core members exist.
3. **`complete` additionally requires a verdict to be present** (rev 6).
4. **Computed systems may report a recommendation or a disagreement, but must NEVER populate or
   overwrite the authored verdict.** The moment they can, it stops being an adjudication.
5. **Any future deterministic rollup gets a distinct derived name** — it does not silently take
   over `verdict`'s ownership.

That makes `verdict` an **evidence-constrained adjudication**, not another hand-editable belief
scalar. The difference from `belief` is that `belief` had a policy that *already computed it*, and
an authored field would have been a second source of truth for the same quantity. Nothing computes
an adjudication.

**The six "belief cluster" fields are three unrelated ownership patterns, not one cluster.**
They must **not** all enter the core hypothesis mixin (that would violate §6's ownership contract
by making every observed key a *core* key):

| field | ruling |
|---|---|
| `belief_state` | **DELETE.** The second-source-of-truth defect, exactly. Hypothesis belief is already computed. |
| `evidence_stance` | **Not belief.** `literature-supported` describes **provenance/coverage**, not epistemic magnitude. Preserve only via a named project extension (e.g. `evidence_scope`), else derive/delete. Remove from `_authored_magnitude`. |
| `author_stated_evidence` | **Source provenance, not current belief.** Move to structured origin metadata or a project-local `source_stated_evidence`. **Must not influence computed belief.** |
| `confidence` | **Too ambiguous for the core schema** — unscoped subjective assessments. Migrate to a project-local prior or an `expert_judgment` evidence line, else delete. |
| `confidence_label`, `confidence_mechanistic_label` | **Real MM-specific interface fields, not core Science fields.** The MM exporter reads them and emits them separately from derived `bundle_belief` → keep as an explicit **project-local** assessment extension. |

**And a live bug this exposed.** `_authored_magnitude` (`validate/checks/evidence_lines.py:395-411`)
walks `("belief_state", "evidence_stance", "author_stated_evidence")` and **returns on the first
recognized token**. The corpus has **13 files with `belief_state: speculative` and the same 13 with
`evidence_stance: literature-supported`**. Because `belief_state` is checked first, the
`evidence_stance` value has **never** reached that check. Remove `belief_state` naively and
`_AUTHORED_MAGNITUDE["literature-supported"] == "supported"` (line 379) fires — silently promoting
13 hypotheses from the **lowest** rung (`speculative`) to `supported`, **purely by field order**.
**The fallback chain is to be DELETED, not adapted.**

### rev 7 (2026-07-12) — the corpus refuted the hypothesis mapping

Writing D5 required cross-tabulating `status` × `phase` across all **147 authored hypotheses**.
That cross-tab **refutes a mapping every revision since rev 2 has asserted**, and it would have
mis-migrated 88 files.

Rev 6 asserted two mappings that are **jointly unsatisfiable on 41% of the corpus**:

> `status: proposed` → `draft`  ·  `phase: active` → `active`

**60 hypotheses carry `status: proposed` AND `phase: active`.** One rule says `draft`, the other
says `active`. Both were called deterministic. Both cannot be.

| status × phase | n | rev-6 verdict |
|---|---|---|
| `proposed` + `active` | **60** | **CONTRADICTION** — the two rules disagree |
| `proposed` + `candidate` | 36 | agree → `draft` |
| `proposed` + *(absent)* | 28 | `draft` — **also wrong**; absent `phase` **defaults to `active`** |

**The resolution — and it follows from D1, which we already ruled.** `proposed` and
`under-investigation` are not lifecycle states *and never were*. They are the old collapsed
field's way of saying **"the evidence has not spoken"** — which is precisely the property D1
disqualified from `verdict`, because **absence already means it**. They therefore map to
**`verdict: absent`**, and they contribute **nothing** to the lifecycle.

> **`phase` IS the hypothesis lifecycle. `status` was only ever the verdict.**

That is the reverse of what rev 2 said (*"`phase` is a hand-rolled lifecycle invented because
`status` had no lifecycle words left"*). The first half was right; the second half was
backwards. `status` had no lifecycle words left **because it never held any** — `proposed` and
`under-investigation` only look like lifecycle. The authors who wrote `phase` were not working
around a gap; **they were correctly separating the two axes by hand**, years before this design
named them. The data is unambiguous: `phase` varies meaningfully (36 `candidate` / 60+ `active`),
while `status: proposed` is the untouched template default on **77 of 147** files.

**Corrected migration mapping (this is what D5 implements):**

| source | → target |
|---|---|
| `phase: candidate` | `status: draft` |
| `phase: active` **or absent** | `status: active` *(absent defaults to `active` — template, `hypotheses_cli.py:28`, `commands/big-picture.md:62`)* |
| `status: proposed` \| `under-investigation` | **`verdict` absent.** Contributes nothing to lifecycle. |
| `status: supported` \| `weakened` \| `partially-supported` \| `refuted` | `verdict: <same>` — lifecycle still from `phase` |

**Result: 145 of 147 deterministic; 2 refused for authored adjudication.** And the two are
exactly right: a test fixture with no `status` at all, and
**`natural-systems/hypotheses/0009`** — `status: retired` + `phase: candidate`, the *very file
whose corruption opened this arc* (fb-2026-07-11-005). Its lifecycle, its closure reason, and
its verdict were all destroyed by the collapsed field, and **no rule can recover them**. The
migration must stop and ask. That it stops on 0009, and on essentially nothing else, is the
strongest available evidence that the axis model is right.

**Why no revision caught this:** every one reasoned about the *vocabularies* and never
cross-tabulated the *corpus*. The D4 audit counted values per field, one field at a time — so a
contradiction that only exists in the **joint** distribution was invisible to it. Certify the
mapping against the data, not just the vocabulary against the readers.

### rev 6 (2026-07-12) — the design is closed on its own terms

Four corrections, two of them substantive enough to have changed the first P2m schema:

- **[P1] `belief` must not become authored frontmatter.** Rev 5 proposed lifting
  `supported`/`contested`/`weakened` off `proposition.status` onto an authored `belief` field —
  **while stating on the same line that the axis had 0 authored uses and 0 readers, and that
  belief is computed from evidence.** The design contradicted itself and I did not see it. An
  authored `belief` would be a **second, hand-editable source of truth for a derived quantity**,
  and the one place a human could record a conclusion the evidence does not support. That is the
  same denormalization §7.4 deletes `disposition` to avoid — and strictly worse, because
  `disposition` was at least a *function* of its source. **The field is removed; the three values
  are dropped with no migration target; `proposition` gets no domain axis at all.** Derived
  belief and its snapshots keep sole ownership of that meaning.
- **[P1] The hypothesis terminal invariant is RULED, not open.** `status: complete` with
  `verdict` **absent** is **prohibited**, not admitted-with-a-`closure_basis`. Rev 5 left this as
  an open sub-decision and floated the permissive branch — which would have **erased the
  distinction that justified adding `complete` in the first place**. Stopping for non-epistemic
  reasons already has an exact spelling (`retired` + `closure_basis`); admitting `complete` +
  absent-verdict would give it a *second* spelling, one that reads to every consumer as though
  the hypothesis had been resolved. A bookkeeping state masquerading as an epistemic one is the
  collapsed-`status` failure re-introduced one level down. **This is now the central invariant of
  the first P2m slice.**
- **[P2] The `paper` row re-collapsed three axes.** `paywalled` (access), `preprint`
  (publication version) and `stub` (record completeness) are **not** reading progress.
  `reading_state` keeps only `unread|abstract-read|read|summarized`; the other three go to D5's
  **adjudication inventory**. Assigning them would have re-committed the exact collapse this
  design exists to undo, *inside the field built to fix it*, and asserted reading progress no
  author ever claimed.
- **[P2] `deferred` is an ordinary lifecycle state, not a "provisional capability."** That
  sentence survived from before the capability contract and contradicted the adopted D4 ruling.
  Pausing has no operation, no gate, no branching consumer — it is a value in an enum.

The through-line of all four: **rev 5 was still, in four places, minting structure that no
evidence asked for** — an authored field for a computed quantity, an escape hatch for an
invariant that should simply hold, a bucket for values that belong on other axes, and a
capability for a verb that does not exist.

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

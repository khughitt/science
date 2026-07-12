# The authoritative entity schema

**Date:** 2026-07-12 (rev 3 — D1–D5 RULED; see §10 for the revision history)
**Status:** Architecture accepted. D1–D5 ruled (§9). Ready for an implementation plan.
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

`status` (lifecycle) is **always present**, default `active`. Domain fields are **absent = not
yet assessed**, which is *distinct* from every explicit value.

**That absence rule is load-bearing, and it disqualifies values that merely restate
"unassessed."** A `verdict` of `proposed` or `under-investigation` says nothing about what the
evidence concludes — it says the evidence has not spoken. Admitting them would make
`verdict: proposed`, `verdict: under-investigation`, and *absent* three spellings of the same
state, re-collapsing the axis this design exists to split. **They are lifecycle, not verdict.**
The same pass is applied to every other domain axis: `deferred` is workflow, not answeredness;
`running` is execution state, not an outcome.

| kind | today's status values | → `status` (lifecycle) | → domain field (category) | default |
|---|---|---|---|---|
| `hypothesis` | proposed, under-investigation, partially-supported, supported, weakened, refuted, archived | **draft**(←proposed) / **active**(←under-investigation) / **complete** / superseded / retired / archived | **`verdict`** *(epistemic)*: partially-supported \| supported \| weakened \| refuted | **absent** |
| `proposition` | draft, active, supported, contested, weakened, retired, superseded, archived | draft / active / complete / superseded / retired / archived | **`belief`** *(epistemic)*: supported \| contested \| weakened | **absent** |
| `question` | active, partially-answered, answered, deferred, retired, archived | active / **deferred** / complete / retired / archived | **`answer_state`** *(answeredness)*: answered \| partially-answered | **absent** |
| `workflow-run` | complete, running, failed | active *(while running)* / superseded / archived | **`outcome`** *(execution)*: complete \| failed | **absent = still running** |
| `story` | draft, developing, mature | draft / active / complete / superseded / archived | **`maturity`**: developing \| mature | absent |
| `pre-registration` | active, committed, amended, superseded, retired | draft / active / complete / superseded / retired | **`commitment`**: committed \| amended | absent |
| `dataset` | active, retired, candidate, deprecated, proposed | draft(←candidate, proposed) / active / retired(←deprecated) | *none* — lifecycle synonyms | — |
| `concept` | active, deprecated | active / retired(←deprecated) | *none* | — |
| `decision` | active, archived, superseded, abandoned | active / archived / superseded / retired(←abandoned) | *none* | — |
| `workflow` | active, retired, deprecated, planned | draft(←planned) / active / retired(←deprecated) | *none* | — |

Three consequences worth stating plainly:

- **Four of the ten have no domain axis at all.** `dataset`, `concept`, `decision`, `workflow`
  were only ever using lifecycle *synonyms* (`deprecated`, `abandoned`, `planned`, `candidate`).
  They collapse to pure-lifecycle kinds. Only **six** kinds carry a genuine second axis.
- **`complete` is mandatory on every kind that can conclude.** Without it, a successfully
  concluded hypothesis is forced into `retired`, which elsewhere means abandoned or
  indefinitely blocked — and `disposition` cannot be declared redundant until that hole is
  closed. Rev 2 omitted `complete` from hypothesis; that was a defect.
- **`deferred` needs a home on the lifecycle axis**, not on answeredness. It is a *paused* state
  and none of `{draft, active, complete, superseded, retired, archived}` means paused. This is a
  genuine gap in the lifecycle vocabulary and is exactly the sort of thing the D4 excavation must
  settle — provisionally, `deferred` is proposed as a lifecycle capability, not forced into an
  existing word.

**Allowed combinations.** The axes are orthogonal by construction; no combination is forbidden.
The load-bearing cells:

| lifecycle + domain | means |
|---|---|
| `active` + `verdict: refuted` | refuted, but still being worked (writing it up) |
| `complete` + `verdict: supported` | supported and concluded |
| `retired` + `verdict` **absent** | pragmatically stopped while epistemically undecided |
| `superseded` + `verdict: supported` | *formerly* supported, now replaced — **the cell `proposition` literally could not express** |

That last row is the whole argument: under the old collapsed field, `superseded` overwrote
`supported` and the belief was silently lost.

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
  matters: **the state is derivable; the authored reason is not.** `closure_basis` is required
  on a terminal transition that has **no structural basis** — where "structural basis" means
  the record already carries the reason in machine-readable form:

  | terminal transition | structural basis | `closure_basis` required? |
  |---|---|---|
  | → `superseded` | `supersedes:` / supersession lineage | **no** — lineage *is* the reason |
  | → `archived` | archive/consolidation record | **no** |
  | → `complete` | the verdict + its evidence | **no** |
  | → `retired` | *nothing* | **YES** — otherwise closure hides research debt |

  `retired` is precisely the transition that records no reason anywhere else, which is why it
  is the one that must carry an authored one. This preserves the fb-005 guarantee that
  retirement cannot silently bury a live question.

## 8. Phasing

- **P0 — Certify (zero downstream *source* migration).** Every field a shipped template or
  toolkit code writes is **declared and wired, or deleted from the template. No third option.**
  Adjudicate `phase`, `role`, `input`, `report_kind`, `committed`, `spec`, `promoted_from` one
  at a time.
  **P0 is *not* "zero downstream churn."** Projects may need no source edits, but wiring a
  previously-dropped field **changes their rebuilt graphs, dashboards, attention ranking, and
  validation output** — materializing `phase` is what re-ranks hypotheses. P0 therefore
  **requires downstream graph/output compatibility checks**, including **commons** wherever a
  shared field is touched.
- **P1 — Absorb the real subsystems.** `provided_capabilities`/`required_capabilities` is a
  designed capability-matching subsystem with its own validator and seven design docs, reading
  raw frontmatter, bypassing the model, invisible to the graph. Make it first-class.
- **P2 — Converge the two schema systems.** Project-authored kinds adopt `schema_profile`;
  `dataset`/`paper` stop having two definitions; commons compatibility is a gate, not an
  afterthought.
- **P3 — Then strictness**, WARN first, ratcheting to ERROR **per kind** as each kind's schema
  is certified and its projects migrated. Severity is a property of the **kind**, never of
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

### D4 — Excavate, then factor into **lifecycle capabilities**. **Adopted.**

Do **not** replace 22 arbitrary lists with one arbitrary universal list. Audit each kind, then
encode the recovered intent as composable named capabilities rather than 33 copied
vocabularies:

```
draftable · completable · supersedable · retirable · archivable(consolidatable) · deferrable?
```

A kind's lifecycle vocabulary is then *derived* from the capabilities it declares.

**`entity_class` must NOT automatically imply capabilities.** The existing
`test_reference_kind_does_not_gain_archived` guard is the proof: `paper`/`book`/`talk` are
deliberately non-consolidatable, and that intent is *more specific* than their broad
classification. Exact capability names follow the excavation, not the other way round.

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

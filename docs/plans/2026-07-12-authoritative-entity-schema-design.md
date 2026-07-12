# The authoritative entity schema

**Date:** 2026-07-12 (rev 2 — rewritten after review; see §10 for what changed and why)
**Status:** Design, for review.
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

**Therefore: `status` means the document lifecycle, uniformly, on every kind.** The semantic
axis moves to an explicitly named field per kind.

This is the low-churn *and* the truthful choice: 22 of 33 kinds already use `status` this way,
and it means **natural-systems writing `status: active` on a hypothesis was correct all
along** — they had nowhere to put the verdict. It does, however, **invert part of the
fb-2026-07-11-005 ruling** (which made `status` the epistemic verdict on hypothesis). That
inversion is deliberate and is called out in §9 as decision D1.

### 7.3 The field contract (all 10 mixed kinds)

`status` (lifecycle) is **always present**, default `active`. Semantic fields are **absent =
not yet assessed**, which is *distinct* from any explicit value.

| kind | today's status values | → `status` (lifecycle) | → semantic field | default |
|---|---|---|---|---|
| `hypothesis` | proposed, under-investigation, partially-supported, supported, weakened, refuted, archived | draft/active/superseded/retired/archived | **`verdict`**: proposed \| under-investigation \| partially-supported \| supported \| weakened \| refuted | absent |
| `proposition` | draft, active, supported, contested, weakened, retired, superseded, archived | draft/active/superseded/retired/archived | **`belief`**: supported \| contested \| weakened | absent |
| `question` | active, partially-answered, answered, deferred, retired, archived | active/retired/archived | **`answer_state`**: answered \| partially-answered \| deferred | absent |
| `workflow-run` | complete, running, failed | active/superseded/archived | **`outcome`**: running \| complete \| failed | required |
| `story` | draft, developing, mature | draft/active/superseded/archived | **`maturity`**: developing \| mature | absent |
| `dataset` | active, retired, candidate, deprecated, proposed | draft(←candidate,proposed)/active/retired(←deprecated) | *none* — these are lifecycle synonyms | — |
| `pre-registration` | active, committed, amended, superseded, retired | draft/active/superseded/retired | **`commitment`**: committed \| amended | absent |
| `concept` | active, deprecated | active/retired(←deprecated) | *none* | — |
| `decision` | active, archived, superseded, abandoned | active/archived/superseded/retired(←abandoned) | *none* | — |
| `workflow` | active, retired, deprecated, planned | draft(←planned)/active/retired(←deprecated) | *none* | — |

**Four of the ten have no real semantic axis at all** — `dataset`, `concept`, `decision`,
`workflow` were only ever using lifecycle *synonyms*. They collapse to pure-lifecycle kinds,
and their odd values migrate. Only **six** kinds carry a genuine second axis.

**Allowed combinations.** The axes are orthogonal by construction: `verdict: under-investigation`
+ `status: retired` is the load-bearing cell (epistemically undecided, pragmatically closed) —
the exact state `status: retired` could not express without lying. No combination is forbidden;
that is the point of separating them.

### 7.4 What this does to `phase` and `disposition`

- **`phase`** (candidate|active) is the hand-rolled lifecycle. It **folds into `status`**:
  `phase: candidate` → `status: draft`; `phase: active` → `status: active`. The `phase:` key is
  then **deleted from the templates** (P0's "declare or delete" rule), not migrated forward.
  ⚠️ This changes `/science:big-picture`'s "Candidate frames" selector, which reads
  `phase == "candidate"`.
- **`disposition`** (open|closed, shipped in `d2fc4d13`) is **likely subsumed** by
  `status: retired` + `verdict`. If `status` carries the lifecycle and `verdict` the epistemics,
  "closed for pragmatic reasons while epistemically undecided" is exactly
  `status: retired` + `verdict: under-investigation`. Retaining `disposition` would then be a
  *third* axis restating the first two. **Decision D2 in §9.** I shipped `disposition` two days
  ago; that is not a reason to keep it.

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

## 9. Decisions required before implementation

- **D1.** Adopt `status` = universal lifecycle, semantic axis → named field (§7.2)? This
  inverts part of the fb-005 ruling. *Recommend: yes* — 22/33 kinds already work this way, and
  it makes the authors right.
- **D2.** Does `disposition` survive, or is it subsumed by `status: retired` + `verdict` (§7.4)?
  *Recommend: subsumed*, unless a case exists that the two-axis form cannot express.
- **D3.** Is the Pydantic model **generated** from JSON Schema, or **reconciled** against it by
  a gate? *Recommend: projection + reconciliation gate* — matches `SharedEntity` and the
  existing 3-way gate, and avoids a codegen step in the build.
- **D4.** How uniform is the lifecycle, really? `test_reference_kind_does_not_gain_archived`
  pins `paper`/`book`/`talk` as deliberately non-consolidatable — so **some** per-kind variation
  is real intent. A first draft of this design proposed steamrolling all 22 pure-lifecycle
  kinds into one uniform set; that guard test would have caught it. **The variation must be
  excavated kind by kind, not assumed to be noise** — "certify before depending", applied to
  this design itself.
- **D5.** Migration cost. Splitting `status` is **not additive-only**: it rewrites authored
  values across every project and needs a real migration command plus a per-kind ratchet.

## 10. What changed in rev 2, and why

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

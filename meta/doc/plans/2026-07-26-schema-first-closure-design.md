# Schema-first closure: declare it per kind, and close the clean kinds

**Date:** 2026-07-26
**Status:** Design approved in section review; not yet implemented.
**Program:** system cohesion. Sub-project of the schema-first gap named — and deliberately
left open — by [`2026-07-25-s1a-reconciliation-gate-design.md`](2026-07-25-s1a-reconciliation-gate-design.md) §4.
**Branch:** `schema-first-gap`, forked from `main` at `e5ac13a0`.

Every quantity below was produced by running code against the shipped profiles and the live
corpus of the 20 armed projects. Where a claim is argued rather than measured it is marked
**(judgment)**.

---

## 1. The defect

`Entity` is `extra="allow"`. That is safe *only* because the composed JSON Schema is checked
first — `unevaluatedProperties: false` refuses what it does not know, and the projection then
preserves what the schema admitted. `entities.py:310-321` states the contract and its own
failure mode:

> The two are one contract: the SCHEMA refuses what it does not know, the PROJECTION preserves
> what it admitted. Separated, each is a defect.

They are separated for **49 of 50 core kinds**. `PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})`
(`entity_schema/profile.py:24`) gates both the load-path check (`graph/sources.py:1306`) and
validator strictness (`entity_schema/validator.py:108`). One kind is closed. The rest are
`extra="allow"` with nothing in front.

### 1.1 The gap, measured

Scanned: `entities/**/*.md` across the 20 projects declaring `entity_schema_version: 2` or `3`
(excluding `_archive/` and toolkit test fixtures). **7,993 documents, 46 authored kinds.**

**This is the Markdown adapter only**, and that limit is load-bearing — §1.3 measures the
structured-source population separately, and it changes a tranche premise.

| | keys | occurrences |
|---|---|---|
| Extra keys the `undeclared_key` diagnostic *can* warn on | 3 | 802 |
| **Extra keys nothing looks at at all** | **231** | **14,389** |

The existing diagnostic is narrower than its name suggests. `_audit_undeclared_reference_keys`
(`graph/migrate.py:141`) skips any key not in `REFERENCE_FIELD_NAMES` — which has **6** members —
and emits `warn`, not `error`. So the shadow schema is 231 keys wide and effectively unobserved.

**"Invisible" is not "illegitimate."** The highest-volume invisible keys are `source` (803),
`target` (642), `stance` (625), `evidence_type` (625), `evidence_role` (556), `strength` (556),
`belief_eligible` (481). Those are the load-bearing fields of `evidence-line` and `proposition`.
They are real tool-written fields with no schema, not junk. Any design that treats the 231 as a
deny list is solving the wrong problem.

**183 of the 231 keys belong to exactly one kind; ~20 are cross-kind.** `promoted_from` appears
on **14 kinds** (469 occurrences), `date` on 11, `mode` on 7. Those are a shared concern: ruling
them per kind *independently* would re-create the multi-surface defect this program exists to
close. §4.3 rules `promoted_from` and states the mechanism that keeps per-kind declarations from
drifting — one frozen literal shape, gated against that oracle rather than against each other.

### 1.2 What "not schema-checked" precisely means

Two populations, and they are not the same size:

- **45 core kinds have no mixin at all.** `default_profile_for_kind` **raises**
  `ProfileParseError` for them (`profile.py:124-125`), so no profile is ever resolved and base
  2.0 is not a contract they *fail* — it is a target they have not *adopted*.
- **49 core kinds lack project-kind closure.** The four commons kinds — `dataset`, `paper`,
  `topic`, `theme` — appear in every generation row and **do** resolve profiles, against base
  **1.0**, and `dataset` additionally has its own gen-3 shape check
  (`_validate_dataset_gen3`, `sources.py:1318`). They are deliberately open
  (`validator.py:104-106`: `SharedEntity` is `extra="allow"` and 369 records rely on it).

Documents that would not satisfy the target contract are **migration debt**, not live validation
failures. This distinction is load-bearing and the wording is used consistently below.

### 1.3 The structured-source population — measured, and it breaks a premise

Entities also enter through `_load_structured_source_records` (`graph/sources.py:1045`), fed by
project-local `structured_source` declarations and by `core_structured_sources`. Scanning every
declared structured source across the 20 projects:

| project | kind | rows | missing base-required |
|---|---|---|---|
| natural-systems | **`finding`** (core) | **149** | **`updated` in all 149** |
| natural-systems | `morphism-edge` (local) | 70 | `created` + `updated` in all 70 |
| natural-systems | `limit-relation` (local) | 131 | — |
| seq-feats | `workflow` (core) | 6 | — |

`finding` is in the tranche. Its Markdown population is 52 documents; its true population is
**201**, and **149 of them (74%) lack a base-required field**. Titles are sound — the loader
backfills `"title": record.title or record.canonical_id` (`sources.py:1101`) — so the failure is
dates, not titles.

**An earlier draft of this design asserted "zero corpus repair" for the whole tranche on the
Markdown scan alone.** That was measuring one adapter and generalising, which is the same error
as §2.1 in a different coordinate. §2.2 states the corrected premise.

---

## 2. The three pieces

This design covers pieces 1 and 2. Piece 3 is named so it is not mistaken for something this
design closes.

| # | piece | in this design |
|---|---|---|
| 1 | **Writer containment** — stop the producer emitting malformed records | yes |
| 2 | **Clean closure tranche** — close `concept`, `method`, `search`, `finding`, `observation` | yes |
| 3 | **`proposition` / `evidence-line` remediation** — repair 769 documents, then close both | **no** |

### 2.1 Why `evidence-line` is not in the tranche

An earlier draft of this design put `evidence-line` in the tranche, on the measurement that 9 of
its 13 non-model fields appear on ≥50% of its documents with **zero** singletons. That
consistency is real. It is the consistency of a machine-emitted skeleton.

`title` in base 2.0 is `{"type": "string", "minLength": 1}` and is **required**
(`science-entity-base-2.0.json:30`):

| kind | docs | empty title | skeleton dumps (≥8 empty values) |
|---|---|---|---|
| `evidence-line` | 614 | **432** | 391 |
| `proposition` | 460 | **337** | 340 |
| `concept` | 329 | 0 | 0 |
| `method` | 51 | 0 | 0 |
| `search` | 36 | 0 | 0 |
| `finding` | 52 | 0 | 0 |
| `observation` | 32 | 0 | 0 |

**769 documents in live research projects are incompatible with the target base-2.0 contract**,
stratified by kind, project and producer. They are not failures of an actively applied schema —
see §1.2 — but they are the reason the two paired kinds need their own migration program. Their
repair is neither bounded nor mechanical: 432 hand-authored titles cannot be reconstructed by any
rule, which is exactly the line §2.2's corrected premise draws.

Ranking `evidence-line` "cheap" was an error of method, recorded here because it is instructive:
**field-tail uniformity measures the producer, not the corpus.** A generated corpus is uniform
by construction, including when it is uniformly wrong.

### 2.2 The tranche

Five kinds spanning all three entity classes, so the mechanism is proved against each:

| kind | class | Markdown docs | structured rows | projects | observed non-base fields | rare (<5%) | source migration |
|---|---|---|---|---|---|---|---|
| `concept` | reference | 329 | 0 | 3 | 4 | 0 | none |
| `method` | operational | 51 | 0 | 5 | 6 | 0 | none |
| `search` | operational | 36 | 0 | 7 | 4 | 0 | none |
| `finding` | epistemic | 52 | **149** | 3 | 10 | 0 | **149 rows, 1 field** |
| `observation` | epistemic | 32 | 0 | 2 | 11 | 0 | none |

**"Observed non-base fields"** is every frontmatter key seen in the corpus that is not among base
2.0's 16 properties — model fields included, since base declares only 16 of the model's 67. It is
deliberately narrower than the **complete candidate universe** the adjudication actually ranges
over (§4.1); it is a corpus measurement, not the input to a ruling.

**The tranche's premise, corrected.** It is *not* "zero corpus repair." It is:

> Every kind in the tranche is either free of source migration, or carries a **bounded,
> mechanical, deterministically repairable** one.

`finding` is the second case: 149 generated rows, in one file
(`~/d/natural-systems/knowledge/sources/project_specific/finding.yaml`), missing one field. That
is categorically different from `evidence-line`'s 432 hand-authored titles, which no rule can
reconstruct. The `finding` slice therefore carries an explicit source-migration step, and gate 3
(§3.4) is a hard prerequisite for it.

**THE MIGRATION RULE: `updated = created`.** Measured — all 149 rows carry
`created: 2026-04-30` and none carries `updated`. The alternatives all produce schema-valid dates
and are all rejected, because a valid date is not the same as a true one:

| candidate | rejected because |
|---|---|
| **`updated = created`** | **SELECTED** — the rows have not been edited since generation; `updated == created` is the true statement about them |
| migration date | asserts the records changed on the day we added a field to them; they did not |
| file mtime | a property of the filesystem, not the record — Dropbox sync alone rewrites it |
| current date | same defect as migration date, and non-deterministic across reruns |

This rule is **mutation-tested**: substituting any alternative must fail a named test. All four
produce a valid `format: date` string, so a schema check cannot distinguish them — only an
assertion on provenance semantics can. Backfilling is a one-time edit to the source file, not a
loader default; the loader must keep failing on a row that genuinely lacks the field, or the
gate-3 behavioural test in §6.2 becomes unfalsifiable.

**No corpus repair does not waive tail adjudication.** Every field in the candidate universe still
needs a declare / omit / delete ruling. It means only that for four of the five kinds those
rulings land without editing live documents. Certification runs against **every source adapter**,
not only Markdown (§6.3).

---

## 3. Architecture: one declaration, four derived surfaces

### 3.1 The five surfaces today

"Is kind K schema-checked?" is currently answered by five **synchronized** surfaces — not
independent ones. `_BASE_VERSION_FOR_MIXIN` is already built from `COMMONS_MIXIN_NAMES` and
`PROJECT_MIXIN_NAMES` (`profile.py:101-104`), and the load gate reads the same set. The defect is
that synchronization is by hand at some joints and by derivation at others, with nothing
asserting which:

| surface | location |
|---|---|
| `PROJECT_MIXIN_NAMES` membership | `entity_schema/profile.py:24` |
| a row entry per generation in `_MIXIN_VERSION_BY_GENERATION` | `profile.py:92-95` |
| `_BASE_VERSION_FOR_MIXIN` | `profile.py:101-104` |
| a `mixin-<kind>-<ver>.json` on disk | `science_model/schemas/` |
| the load gate `kind not in PROJECT_MIXIN_NAMES` | `graph/sources.py:1306` |

`PROJECT_MIXIN_NAMES` already deliberately serves double duty, and `sources.py:1301-1304`
explains why: gating enforcement and strictness on one list prevents "a green check over an
unchecked record." That instinct is correct. This design extends it rather than replacing it.

### 3.2 The declaration

`EntityKind` — the per-kind SSOT — gains:

```python
schema_closed: bool = False
```

`PROJECT_MIXIN_NAMES` becomes derived from it, over the **built-in profiles only**
(`CORE_PROFILE` and `LOCAL_PROFILE`). Every existing consumer — the load gate, validator
strictness, `strict_schema_kinds` — keeps reading `PROJECT_MIXIN_NAMES` unchanged.

**Declared explicitly on all 53 shipped kinds**, asserted through `model_fields_set` rather
than the value. The `False` default is what keeps project-authored manifest kinds inert, which
means a shipped kind that merely *forgot* to declare would otherwise be indistinguishable from
one ruled open. Presence is the only thing separating them. (Same reasoning as `supersedable`
in S2.)

**Manifest scope is explicit.** `EntityKind` also parses project-authored manifests
(`entity_kinds.py:125` validates through `ProfileManifest`). A project cannot install a packaged
type mixin or alter `PROJECT_MIXIN_NAMES`, so `schema_closed: true` in an externally loaded
manifest is **rejected**, not silently ignored — a silent ignore is exactly the fail-silent this
program abolishes. The explicit-declaration gate runs over the 53 shipped kinds only.

### 3.3 Arming is one edit

Because `PROJECT_MIXIN_NAMES` derives from `schema_closed`, setting it to `True` immediately
arms `unevaluatedProperties: false`, Markdown load validation, write-boundary validation,
`strict_schema_kinds`, and every other membership consumer. **There is no separate strictness
switch, and that is desirable.** Consequences for the slice sequence:

- The mixin file lands **dormant** — present on disk, armed by no generation row.
- Corpus certification composes the candidate profile **explicitly**, not through membership.
- The final edit sets `schema_closed=True` and adds **both** generation-row entries together,
  atomically. Gate 1 requires exactly that atomicity.

### 3.4 The four gates

A test asserting `PROJECT_MIXIN_NAMES == {k for k in kinds if k.schema_closed}` is the identity
function once one derives from the other. Each gate below compares the declaration against an
**independently hand-authored artifact**, so each can genuinely disagree.

**Gate 1 — generation-row equality, per generation, commons excluded.**

```python
set(row) - COMMONS_MIXIN_NAMES == declared_schema_closed_names
```

Every generation row contains `dataset`, `paper`, `theme` and `topic`, but those are commons
mixins: they stay open and pin base 1.0, so they must not force `schema_closed=True`. Verified
today — `set(row) - COMMONS_MIXIN_NAMES` is `{"hypothesis"}` for both generations, equal to
`PROJECT_MIXIN_NAMES`. Exact equality gives both directions: a closed declaration missing from
any generation row fails, and a project mixin present in a row without a closed declaration
fails. A kind closed in gen 2 but absent from gen 3 would raise `ProfileParseError` at load for
every gen-3 project, so this is a real failure the gate must catch.

A **separate** standing assertion holds that every commons kind is represented in every
generation row as the generation policy requires, so the exclusion above cannot quietly become
a hole.

**Gate 2 — armed components resolve, forward only.**

Every `(kind, version)` armed by any generation row resolves to a packaged
`mixin-<kind>-<version>.json`. This is deliberately **not** biconditional: schema files are
versioned artifacts and a dormant historical or staged version may legitimately sit on disk.
Measured — four such files exist today:

| armed by some row | dormant on disk |
|---|---|
| `dataset-2.0`, `dataset-3.0`, `hypothesis-1.0`, `hypothesis-2.0`, `paper-2.0`, `theme-2.0`, `topic-2.0` | **`dataset-1.0`, `paper-1.0`, `theme-1.0`, `topic-1.0`** |

A raw `mixin-*.json` scan used as the reverse authority would have failed on day one. Gates 1
and 2 together still mutation-prove a missing file, a missing row, an extra row, and a stale
declaration, without implying every dormant schema file must be active.

**Gate 3 — every load path that can emit a closed kind validates before projection.**

The Markdown adapter is not the only path. `_validate_against_schema` is called at exactly one
site, `graph/sources.py:457`. The structured-source loader
(`_load_structured_source_records`, `sources.py:1045-1128`) calls `schema.model_validate(raw)`
directly — the Pydantic model, not the composed JSON Schema — and its record model
`StructuredEntitySource` is `extra="ignore"` (`source_contracts.py:71`), dropping unknown keys
*before* the entity is constructed. Its own docstring names the reachable case:

> …or `finding` rows from an audit.

`finding` is in this tranche, so `schema_closed=True` would otherwise overstate reality:
Markdown findings checked, structured findings not. The rule:

> Every authored load path capable of producing a schema-closed kind validates the unprojected
> source against its composed profile before dropping or enriching fields.

**A choke point at the construction site is not sufficient, because the loss happens earlier.**
An earlier draft proposed wrapping `schema.model_validate(raw)`. That cannot work. On the
structured path the sequence is:

| step | site | effect |
|---|---|---|
| 1 | `_load_typed_records` → `model.model_validate(item)` (`sources.py:1273`) | parses each row into `StructuredEntitySource`, which is **`extra="ignore"`** (`source_contracts.py:71`) — **unknown keys are gone here** |
| 2 | `sources.py:1096-1125` | a *new* mapping is built from the surviving typed fields |
| 3 | `sources.py:1126` | the entity is constructed |

By step 3 the shadow fields the design exists to expose no longer exist. Validating there
inspects a mapping the toolkit itself just assembled — a check that can only ever pass. The
legacy model and parameter paths (`:998`, `:1038`) have the same ordering.

There is a second reason the raw row cannot simply be handed to the entity profile: it authors
`canonical_id` and `source_path`, while the entity schema expects normalized `id` and
`file_path`. Measured on natural-systems' rows, the authored keys are
`canonical_id, created, description, evidence_refs, kind, profile, source_path, title` — and
`kind` is authoritative from the manifest and deliberately ignored on the row, so it is a
legitimately dropped key, not a shadow field.

**The required pipeline, stated as the ruling:**

```
raw source
  → lossless source-contract validation     (nothing is dropped)
  → normalization                           (declared key mapping; declared drop set)
  → composed entity-schema validation       (unevaluatedProperties: false bites HERE)
  → Pydantic entity projection
```

Consequences, each of which is a change this design owns:

1. **`StructuredEntitySource` stops being `extra="ignore"`.** It becomes `extra="allow"` so
   unknown keys survive step 1 and reach step 3. `extra="forbid"` is rejected: every existing
   row carries `kind`, which the loader legitimately ignores, so forbidding would reject the
   whole corpus for a key the design agrees is fine.
2. **Normalization becomes an explicit named step** with a declared mapping
   (`canonical_id → id`, `source_path → file_path`) and a **declared drop set** (`kind`, and
   nothing else without a written ruling). Today this is inline dict-building at `:1096-1125`;
   a drop that is not declared is indistinguishable from a bug.

   **Implementation note — carry authored fields only.** Once `StructuredEntitySource` is
   `extra="allow"`, its *declared* fields still default (`title=""`, `profile=""`,
   `source_path=""`, and five empty lists). Normalizing from the parsed record would promote
   those defaults into the mapping that gets schema-validated, so an absent `title` would arrive
   as `""` and fail `minLength: 1` while an absent `evidence_refs` would arrive as `[]` and read
   as an authored empty list. Normalization must therefore range over **authored** keys only —
   retain the original row mapping, or use `model_dump(exclude_unset=True)` — so the schema sees
   what the author wrote and the loader's own backfills (`title or canonical_id`) stay explicit
   and separately testable.
3. **The guard covers the boundary, not a call syntax.** An AST rule over
   `.model_validate(...)` is defeated by a constructor call, a `TypeAdapter`, or any other
   spelling. `EntityRegistry.resolve(kind)` returns `type[Entity]` (`entity_registry.py:189`),
   so **handing out the class is the hole**. Resolution and construction are merged into one
   operation — `registry.build(kind, raw, *, project_schema, path)` — and the enforceable guard
   is over the **import surface**: the entity model classes are obtainable only through that
   operation, checked by AST across the entity-loading package. A new adapter cannot construct
   an entity without going through it, because it cannot get the class.

   **Implementation note — registration is a legitimate importer.** `entity_registry.py` imports
   the concrete classes on purpose, in order to register them: a block from
   `science_model.entities` (`:15`), plus `PatchDefinitionEntity` (`:38`) and `PropositionEntity`
   (`:41`). The guard is therefore *not* "no module imports an entity class"; it is **"the
   registry module is the only importer, and every other module obtains classes through
   `registry.build`."** The registry's own import list must additionally be reconciled against
   the registered-kind population, so a class imported but never registered — or registered from
   a class obtained some other way — fails. Writing the guard as a blanket import ban would make
   registration itself the first violation.

This is the S1a lesson applied: the population is *derived* from what code can reach, not listed.
There are exactly five entity-producing sites today — `sources.py:489`, `:998`, `:1038`,
`:1126`, and `commons_sources.py:423` — which is small enough to enumerate, and that is precisely
why enumeration is rejected: **a guard that lists its scope has a hole by construction**, opening
the day someone adds the sixth.

This is a **mechanism** change and lands before the five slices, because `finding` is reachable
through the structured path.

**Gate 4 — descriptor prerequisites (one-way implication).**

`schema_closed ⟹ entity_class and home are declared`. A kind with no `home` cannot be located to
validate. This is an implication, not an equality: many deliberately open kinds already declare
both.

---

## 4. The per-kind atomic slice

[`2026-07-12-authoritative-entity-schema-design.md:447`](../../../docs/plans/2026-07-12-authoritative-entity-schema-design.md)
rules that every change of meaning moves "schema, sources, templates and consumers together,
**atomically, per kind**." The tranche is therefore **five independently atomic slices**, not one
change. Each runs the same seven steps:

1. **Freeze the complete field-surface inventory and dispositions.**
2. **Author the dormant mixin, plus projection / value / mutation probes.**
3. **Update sources, templates, writers, readers, and adapter-specific records.**
4. **Certify the candidate composed profile over all projects and all source paths.**
5. **Reconcile schema fields against the projection and the reader/omit decisions.**
6. **Diff graph, validation, dashboard and other derived outputs** against an intended-change
   allowlist. Wiring a previously-dropped field changes rebuilt graphs, dashboards, attention
   ranking and validation output — P0's own warning.
7. **Atomically add both generation entries and set `schema_closed=True`;** then run the four
   architectural gates and full verification.

### 4.0 Where atomicity binds

An earlier draft claimed "step 7 is the only edit that changes behaviour." That is false: step 3
changes source, template, writer and reader behaviour the moment it lands. The correction, stated
so the plan cannot re-introduce it:

> **Atomicity is defined at merge scope.** One kind's slice is one branch, merged as a unit and
> never released in parts. Within the branch, steps 1–6 land as separate reviewable commits;
> **step 7 is the only edit that arms schema enforcement.**

That distinction is what `2026-07-12-authoritative-entity-schema-design.md:447` requires — schema,
sources, templates and consumers moving *together* — and it is satisfied by the merge, not by
cramming seven steps into one commit. It also follows from §3.3: because `PROJECT_MIXIN_NAMES`
derives from `schema_closed`, step 7 is a single edit by construction, and steps 3–6 are
deliberately inert with respect to enforcement so they can be reviewed on their own.

The prohibition that carries the weight: **no partial release.** A branch that merges steps 1–6
without step 7 leaves templates and writers emitting a declared field set that nothing enforces —
the same separated-contract defect this design exists to close, in miniature.

### 4.1 Field adjudication needs the complete candidate universe

"Every observed field" is insufficient: a zero-occurrence field can still be prescribed by a
template or emitted by a writer, and corpus success cannot prove rejection behaviour. The
inventory is the **union** of:

- fields observed across **all** source formats (Markdown, structured-source, any other adapter)
- template and writer output
- keyed consumer reads
- Pydantic projection fields and defaults
- existing schema/base fields applicable to the kind
- known retired / tombstoned fields

Every admitted field then gets a value/shape probe battery across **both generations**, including
invalid mutations — the input shape the existing value-reconciliation ratchet
(`science/model/tests/test_value_reconciliation.py`, S1a) already expects.

### 4.2 Explicit `false` is reserved

`unevaluatedProperties: false` already rejects unadmitted names by construction. Omission is the
default refusal; the hypothesis mixin demonstrates this — it does **not** tombstone
`promoted_from`, it simply omits it, and `protein-landscape`'s own extension re-admits it.

Explicit `false` is used only for:

- base-admitted fields the kind deliberately narrows away
- named retired fields whose tombstone is intentional and tested

**Non-goal, stated so it cannot drift in:** the 231-key shadow schema does not become a 231-entry
deny list.

### 4.3 `promoted_from` — an ownership ruling, decided before, landed inside

`promoted_from` appears on **14 kinds / 469 occurrences**, including four of the five tranche
kinds. It is already named in P0's declare-or-delete list
(`2026-07-12-authoritative-entity-schema-design.md:454`).

**There is a prior ruling, and this design revisits it explicitly.** The hypothesis adjudication
routed `promoted_from` to a **project extension**: `~/d/protein-landscape/schemas/
extension-protein-landscape-promotion-1.0.json` declares it, wired via
`entity_extensions: hypothesis: [protein-landscape.promotion/1.0]`. That ruling was made on
evidence from the kind where the field is **rarest** — `hypothesis` carries it on 3 documents.
Distribution across all kinds:

```
meta 137 · concept 132 · topic 64 · finding 26 · observation 25 · method 20 · decision 18
paper 17 · proposition 9 · citation 7 · latent 4 · dataset 4 · hypothesis 3 · workflow 3
```

**The status-quo ruling is refuted by the toolkit's own code.** `graph/decision_log.py:157`
writes `fm["promoted_from"] = promoted_from` when promoting a decision section out of the
decision log into an owner file. That is toolkit code, emitting the field onto a **core** kind.
A project extension cannot own a field the toolkit writes into core-kind files: under
`unevaluatedProperties: false` every project would need to author protein-landscape's extension
to survive a `decision` write it did not make.

**THE RULING: `promoted_from` is a per-kind core field.** Of the four candidates:

| outcome | verdict |
|---|---|
| **per-kind core field** | **SELECTED** — declared in the mixin of each kind that legitimately carries it, ruled inside that kind's atomic slice |
| universal base field | rejected — needs a versioned base change and admits the field to *every* composed project kind, including the ones where it is meaningless; a wrong answer becomes reachable |
| delete | rejected — it is real provenance, and the toolkit writes it |
| project extension (status quo) | **refuted** by `decision_log.py:157`, above |

**Semantics, fixed here so each slice rules against one meaning:** `promoted_from` names *the
authored artifact this entity was promoted out of* — a source location, not an idea origin.
`decision_log.py` sets it to `DECISIONS_REL`; the 2026-07-14 note records that the authored
values are "source paths naming WHERE the entity came from."

**The 2026-07-14 ruling is narrowed, not overturned.** Its load-bearing half stands and must be
preserved verbatim in the migration code: `promoted_from` is **not** migratable into `origins`,
because `OriginRecord.type` is a required enum naming *who* had the idea while these values name
*where* the entity came from — "any type the migration picked would be fabricated provenance."
Only the ownership half ("a PROJECT EXTENSION") is superseded, and `migrate_hypothesis.py:77`
must be edited to say so rather than left asserting a ruling this design replaced.

**Shape stated once, admissibility stated per kind.** No shipped schema uses cross-file `$ref` —
every `$ref` is local (`#/$defs/...`) and shapes like `origin_record` and `authored_relation` are
already duplicated per mixin. `promoted_from` follows that convention: declared inline in each
mixin that admits it.

**The frozen shape**, taken from the one existing declaration
(`~/d/protein-landscape/schemas/extension-protein-landscape-promotion-1.0.json`):

```json
{"type": "string", "minLength": 1,
 "description": "Path of the source file this entity was promoted from, e.g. knowledge/sources/local/entities.yaml"}
```

The gate asserts each mixin's declaration equals **that literal oracle**, not merely that the
mixins agree with each other. Pairwise equality alone permits every mixin to drift identically —
the same tautology trap as §3.4, one level down.

**Scope, and the debt it leaves.** The ruling applies to kinds closed from now on. `hypothesis`
is already closed and its mixin omits the field; re-aligning it means a versioned mixin change,
which is **out of scope here** — protein-landscape's extension stays, and hypothesis's
re-alignment is recorded as open debt. Of the 14 kinds carrying the field, 4 are in this tranche
(`concept` 132, `finding` 26, `observation` 25, `method` 20); `meta`, `latent` and `citation` are
not core kinds at all; 6 unclosed core kinds stay open debt, and `hypothesis` is a separate item because it is already closed — both listed in §8.

---

## 5. Writer containment

Lands **first** and independently. It stops the debt growing; it does **not** backfill the 769
documents and is not a prerequisite for the tranche.

### 5.1 The boundary rule

> Empty fields may be acceptable while constructing an in-memory entity. They are not acceptable
> once persisted as authored source.

`dag/workbench.py:288-290` violates it, and cites test practice as the precedent for a
production write:

```python
# Base-required fields that have no value at lift time — safe empties
# (mirrors the minimal-construction pattern in the entity model tests).
title="",
```

`science_model/propositions.py:33-38` builds the same empties into the model defaults, so both
kinds inherit one lift path.

### 5.2 Deterministic title generation, not a required field

`WorkbenchRow` and `EvidenceStub` are both `extra="forbid"` and neither carries `title`
(`workbench.py:89-112`, `:114-169`). Requiring one would expand both authored-input contracts.
Deterministic generation is the narrower ruling:

**Proposition** — `subject`, `predicate` and `object` are all required `str` on `WorkbenchRow`,
so the result is non-empty by construction:

```python
title = f"{row.subject} {row.predicate} {row.object}"
```

**Evidence line** — `target` is the proposition id and is always present; `stance`, `source` and
`evidence_type` are all `str | None` on `EvidenceStub`:

```python
head = f"{stub.stance or 'supports'} {target_id}"
tail = stub.source or (stub.evidence_type.value if stub.evidence_type else None)
title = f"{head} — {tail}" if tail else head
```

**AMENDED 2026-07-27: the fallback is `'supports'`, not `'evidence'`.** The first draft used
`'evidence'`, which would have made the title contradict the record it titles: `_evidence_line_for_stub`
already defaults the persisted field to `EvidenceStance.SUPPORTS` when the stub carries no stance,
so a file reading `stance: supports` would have been titled "evidence …". The title must describe
the record, and the record's own default is the only honest source for it. Changing this string is
a behaviour change and is mutation-tested.

`" ".join(part.split())` is applied to each result, so no title carries doubled or leading
whitespace.

**Non-emptiness is NOT guaranteed by the row model, and an earlier draft claimed it was.**
`WorkbenchRow`'s `subject`/`predicate`/`object` are plain `str` with no `min_length`; verified,
`WorkbenchRow(subject="", predicate="", object="", patch="p")` is **accepted**. What actually
protects the proposition title is the later `Predicate(row.predicate)` conversion, which raises
`ValueError` on `""`. That leaves empty `subject` and `object` unguarded, so:

> `subject` and `object` gain `min_length=1` on `WorkbenchRow`, failing at parse time with the
> row named — not at title construction, and not at base validation.

For the evidence line, `target_id` is computed and always present, so `head` is non-empty
regardless of `stance`. Both formats are **the ruling**, not an implementation choice, and are
**mutation-tested**: changing either must fail a named test rather than silently re-titling
future records.

These titles are deliberately mechanical. They are durable authored source, so they must be
stable and derivable — not good prose. Nothing prevents an author replacing one afterwards; the
update path preserves fields the workbench does not own (§5.3).

### 5.3 New-file serialization vs. update preservation

The defect is specifically the **new-file** path. `render_entity_text` (`entities.py:444`) does:

```python
entity.model_dump(mode="json", exclude_none=True, exclude_defaults=False)
```

`exclude_none=True` is why the skeleton carries `title: ''`, `accessions: []`, `datapackage: ''`
rather than `null` — `None` fields drop, but empty-string and empty-list defaults survive.

**The defect is full-model serialization on the new-file path, not the flag.**

**CORRECTED 2026-07-27.** An earlier revision argued that `exclude_defaults=True` would discard
`belief_eligible=False` as if it were a default. Measured, that is wrong twice over:
`belief_eligible` defaults to **`True`**, so a deliberate `False` survives the flag untouched.

The real reason the flag does not fix this is simpler and stronger. The skeleton fields are
**required**, not defaulted: constructing `EvidenceLineEntity` without `project`,
`ontology_terms`, `related`, `source_refs`, `content_preview` or `file_path` raises `Field
required` for every one of them. A required field has no default to be excluded *by*, so
`exclude_defaults=True` emits them regardless — it would still write the skeleton. The lift path
must keep supplying them for in-memory construction; what must change is what gets **persisted**.

The fix is therefore an explicit writer-owned allowlist, and it has to be: no dump-mode flag can
express "required for the model, not for the file."

Updates already preserve existing frontmatter and overwrite only writer-owned keys.

- **New file:** emit only the explicit writer-owned allowlist, plus base identity and dates.
- **Existing file:** preserve fields the workbench does not own. Never erase authored metadata
  merely because this writer does not generate it.
- **Both paths:** validate the final persisted mapping before planning or writing.

This contains new skeleton dumps without turning an ordinary workbench update into an implicit
migration of old records.

**The exact positive sets, frozen.** `workbench_apply.py:56-87` already declares the per-kind
key sets — `_PROPOSITION_WORKBENCH_FRONTMATTER_KEYS` (14 keys) and
`_EVIDENCE_LINE_WORKBENCH_FRONTMATTER_KEYS` (10 keys) — and **`title` is in neither**. That is
the authority, and the rule is:

| path | set |
|---|---|
| **update** | the existing per-kind frozenset, **unchanged** — `title` stays out |
| **create** | the same frozenset **∪ `{title, status}`** |

`title` is therefore **create-only** by construction. Adding it to the shared update set would
overwrite an author's replacement on the next apply and contradict §5.2. A test asserts the two
sets differ by exactly `{title, status}`, so the distinction cannot erode.

The lift path's remaining "safe empties" — `project`, `ontology_terms`, `related`,
`source_refs`, `content_preview`, `file_path` (`workbench.py:288-296`) — are simply not in either
set and stop being emitted. (`content_preview`, `file_path`, `type` and `canonical_id` are
already stripped as derived keys by `render_entity_text`; the others are the skeleton.)

### 5.4 Updating a record that predates containment — the ruling

§§5.2–5.4 together imply a case that must not be left to the implementer. Generated titles are
create-time only; updates preserve `title` because the workbench does not own it; no existing
record is backfilled; and **both** paths validate the final base shape. So an update targeting
one of the 769 existing empty-title records has three plausible implementations — reject, skip
validation, or backfill — and the design must pick one.

**THE RULING: reject, and say why.** The update fails `validate_persisted_base_shape` (§5.5) with an
error naming the record, the offending field, and the remediation. Rationale:

- **Skipping validation** re-creates the exact defect being closed: a write path that persists
  source it did not check. It would also make the containment regressions pass while the
  behaviour they describe is not enforced.
- **Backfilling** turns an ordinary workbench update into a silent migration of a record the
  author did not ask to touch — and §5.3's whole point is that updates must not do that. It
  would also repair records piecemeal, in an order determined by which ones someone happened to
  edit, leaving the population unmeasurable.

Rejecting is fail-early and it is honest: the record is genuinely incompatible with the durable
contract, and piece 3 is where it gets repaired. **This is tested**, with a fixture carrying an
empty title, asserting the error names the record and does not write.

**Accepted cost, stated plainly:** until piece 3 lands, a workbench apply touching any of the 432
evidence-line or 337 proposition records fails. That is a real ergonomic regression for mm30 in
particular, and it is the argument for sequencing piece 3 promptly rather than for weakening the
rule. **(judgment)**

### 5.5 A separately named base-shape check

`EntityValidator.validate_as` deliberately rejects base-only profiles
(`validator.py:51-55`) — passing the base is not proof that an entity satisfies its kind schema.
Writer containment nevertheless lands before `proposition` and `evidence-line` mixins exist.

Add a separately named operation, `validate_persisted_base_shape`, whose contract states:

> Necessary validation of durable source shape, not sufficient entity-schema validation.

It loads base 2.0 directly, checks the final frontmatter **after** dates and titles are added,
and does **not** apply `unevaluatedProperties: false`. `validate_as` is not weakened, and
title/date rules are not re-implemented by hand.

### 5.6 Regressions

Proposition and evidence-line writes contain neither empty titles nor dataset-shaped skeleton
fields (`datapackage`, `accessions`, `parent_dataset`, `license`, `local_path`, `xrefs`,
`siblings`, `consumed_by`, `produced_by`, `scope`, `provisional`, `pre_registered`,
`deprecated_ids`, `profile`, `project` — the 391-document uniform set).

---

## 6. Testing

### 6.1 Architectural gates — split by package

Adapter reachability depends on `science_tool.graph.sources`, which `science-model` must not
import. The gates therefore live in two suites:

| suite | gates |
|---|---|
| **model** (`science/model/tests/`) | generation equality (1), armed-resource resolution (2), descriptor prerequisites (4), explicit declaration over 53 kinds, external-manifest rejection |
| **toolkit** (`science/tests/`) | adapter reachability (3) — every adapter capable of emitting a closed kind validates raw input before projection |

### 6.2 The mutation matrix

Every gate must be shown to fail by a **named** gate, not merely "something goes red."

| # | mutation | must fail |
|---|---|---|
| 1 | remove a generation-row entry for a closed kind | gate 1 |
| 2 | add a `schema_closed` declaration with no generation rows | gate 1 |
| 3 | leave a project mixin in a row with no closed declaration | gate 1 |
| 4 | remove a packaged mixin file armed by a row | gate 2 |
| 5a | restore `extra="ignore"` on `StructuredEntitySource` | gate 3 **behavioural**: an unknown key on a structured `finding` row is dropped instead of refused |
| 5b | drop the schema check from `registry.build` | gate 3 behavioural: a structured `finding` row missing `updated` materializes instead of failing |
| 5c | obtain an entity class outside `registry.build` and construct from it | gate 3 **import-surface** AST guard, naming the offending file and line |
| 5d | add an undeclared key to the normalization drop set | gate 3 drop-set equality |
| 6 | closed descriptor with `home=None` | gate 4 |
| 7 | closed descriptor with `entity_class=None` | gate 4 |
| 8 | external manifest authors `schema_closed: true` | manifest-scope rejection (parse fails) |
| 9 | change one mixin's `promoted_from` shape | §4.3 literal-oracle gate (not pairwise agreement) |
| 10 | backfill natural-systems' `updated` with the migration date, mtime, or today | §2.2 `updated = created` provenance test — all three produce valid dates |
| 11 | add `title` to a per-kind **update** key set | §5.3 create-vs-update delta test (`{title, status}`) |
| 12 | let an update of an empty-title record pass, by skipping validation or backfilling | §5.6 rejection test |
| 13 | change either derived title format string | §5.2 format test |
| 14 | remove `min_length=1` from `WorkbenchRow.subject`/`object` | §5.2 parse-time test — empty strings are accepted today |

Mutations 5a and 5b are **both** required and are not redundant: 5a proves the *loss* is
prevented, 5b proves the *check* runs. An earlier draft had only the second, which would have
passed against a pipeline that faithfully validated a mapping the toolkit had already stripped —
a check that cannot fail. That is the S2 lesson in its exact form: an assertion both sides satisfy
by construction proves nothing.

### 6.3 Corpus certification

Opt-in, under the existing `real_projects` marker. It composes each project's candidate profile
**with that project's own declared extensions**, not merely the package-default mixin — mm30's
`mm30.assessment`, evolution's `evolution.provenance`, protein-landscape's
`protein-landscape.promotion` are the reason `unevaluatedProperties: false` does not reject the
files of projects that did nothing wrong.

**The expected 20 project identities and the encountered adapter population are frozen.** When
`-m real_projects` is explicitly selected, a missing project **fails** rather than skips —
otherwise "all 20 passed" silently becomes "the 17 available passed."

This is the layer that would have caught the 432 empty titles, and it runs **per adapter**, not
per format.

---

## 7. Two implementation plans

The two pieces have different risk profiles and different merge cadences, so they get separate
plans and separate branches:

| plan | branch | scope | mergeable |
|---|---|---|---|
| **1. Writer containment** | `workbench-writer-containment` | §5 in full — deterministic titles, writer-owned allowlist, `validate_persisted_base_shape`, regressions | **immediately, on its own** |
| **2. Closure mechanism + tranche** | `schema-first-gap` | §3 declaration and four gates, the §3.4 choke point and structured-source validation, then five atomic kind slices (§4) | after plan 1; ~7 tasks |

Plan 1 depends on nothing in plan 2. It is stop-the-bleeding repair, it touches one writer, and
holding it behind a seven-task closure program would let the 769-document population keep growing
for no reason. Plan 2 depends on plan 1 only in the sense that both touch entity persistence; it
does not require containment to have merged, since `proposition` and `evidence-line` are not in
the tranche.

## 8. Out of scope, stated in the file

- **`proposition` and `evidence-line` closure.** Piece 3. Their 769 incompatible documents are
  a producer-repair and source-migration problem; they close as separate atomic kind slices
  after remediation, even though they share one producer fix.
- **Backfilling the 769 documents.** Writer containment stops new ones; it repairs none.
- **The remaining 44 unclosed core kinds.** `paper` (30 observed non-base fields), `question` (19, with
  15 singletons), `dataset` (28), `interpretation` (34), `report` (23) and the rest carry
  genuine idiosyncratic tails that need per-field adjudication. Nothing here clears them.
- **The 16 authored kinds that are not core kinds** — `meta`, `design`, `note`, `analysis-plan`,
  `review`, `bias-audit`, `paper-review`, `citation`, `audit`, `probe`, `paper-synthesis`,
  `latent`, `critique`, `guide`, `modality-guide`, `commentary` (700+ documents). They cannot be
  closed without first being registered as kinds.
- **Widening `REFERENCE_FIELD_NAMES` or the `undeclared_key` diagnostic.** A warning surface is
  not the mechanism this design builds; a wrong answer should become unreachable, not
  discouraged.
- **Re-aligning `hypothesis` to the §4.3 `promoted_from` ruling.** Its mixin is versioned and the
  kind is already closed; changing it needs a versioned mixin bump. protein-landscape's extension
  stays until then. **Open debt, created by this design.**
- **The 6 unclosed core kinds carrying `promoted_from` outside the tranche** — `topic` (64),
  `decision` (18), `paper` (17), `proposition` (9), `dataset` (4), `workflow` (3). The ruling
  covers them; the declarations land when those kinds close. **Open debt.** `hypothesis` (3) is
  *not* in this list — it is already closed and needs a versioned mixin bump, which is the
  separate debt item above.
- **The structured-source rows of non-tranche kinds.** `morphism-edge` (70 rows, missing both
  `created` and `updated`) and `limit-relation` (131 rows) are project-**local** kinds in
  natural-systems; `workflow` (6 rows, seq-feats) is core but not in the tranche. Gate 3 makes
  their load path validating, but nothing closes those kinds here, so no profile applies to them
  and the rows are untouched. **Named so gate 3 is not mistaken for having repaired them.**
- **The `legacy_relation_label` / `legacy_patch` / `legacy_edge_id` triple** (1,011 occurrences,
  3 projects). Compat projections get deleted, not documented — but that deletion belongs to the
  `proposition` slice in piece 3.

---

## 9. Success criteria

1. `schema_closed` is declared explicitly on all 53 shipped kinds; `PROJECT_MIXIN_NAMES` is
   derived and no consumer changed.
2. All four gates pass in their own mode — gate 1 **exact equality** per generation (commons
   excluded), gate 2 **armed-resource resolution** (forward-only), gate 3 **adapter reachability**
   via the choke point, gate 4 **implication** — and every row of the §6.2 mutation matrix fails
   its named gate.
3. `concept`, `method`, `search`, `finding`, `observation` are closed, each by its own atomic
   slice, each certified over all 20 projects and every source adapter.
4. Every entity-producing site routes through the `build_entity` choke point, proved by AST
   guard; a structured `finding` row missing `updated` fails at load rather than materializing,
   and natural-systems' 149 rows carry the field.
5. Workbench writes produce no empty titles and no dataset-shaped skeleton fields, proved by
   regression.
6. The `promoted_from` ownership ruling is written down with its scope, and the prior
   hypothesis-slice ruling is explicitly named as revisited.

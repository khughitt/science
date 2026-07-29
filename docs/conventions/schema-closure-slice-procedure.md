# Per-Kind Schema-Closure Slice Procedure

Schema closure is adopted one entity kind at a time. A slice must reconcile every
surface that can prescribe, emit, preserve, consume, or reject fields before it
turns enforcement on. This procedure is the durable ruling for future slices;
observed corpus success alone is not evidence that a kind is closed.

## Merge Boundary

One kind's slice is one branch and is merged as a unit. Steps 1–6 below land as
separate, reviewable commits. Step 7 is the only edit that arms enforcement.
There is no partial release: merging steps 1–6 without step 7 leaves templates
and writers emitting a declared field set that nothing enforces, recreating this
design's defect in miniature.

Atomicity is therefore merge scope, not a requirement to hide the work in one
commit. The reviewable commits expose each decision while the branch boundary
keeps the declaration and enforcement inseparable in a release.

## The Seven-Step Slice

1. **Freeze the field-surface inventory and dispositions.** Build the candidate
   universe as the union described below. Record each field's disposition and
   rationale before writing the mixin.
2. **Author the dormant mixin and its probes.** Add projection, value, and
   mutation probes while the mixin is not yet selected by generation.
3. **Align every production surface.** Update sources, templates, writers,
   readers, and adapter-specific records to the frozen disposition.
4. **Certify the candidate composed profile.** Exercise it over all projects and
   all source paths, composing project extensions exactly as production does.
5. **Reconcile the contracts.** Compare schema fields with the Pydantic
   projection and with every explicit reader or omit decision; unexplained
   fields on either side block the slice. For a kind with no typed subclass,
   see "Untyped kinds" below — the gap direction has a manifest, and the
   surplus direction has nothing to explain.
6. **Diff derived behavior.** Compare graph, validation, dashboard, and other
   derived outputs against an explicit intended-change allowlist. Unlisted
   drift blocks the slice.
7. **Arm enforcement atomically.** In one final edit, add both generation
   entries and set `schema_closed=True`. Neither generation entry nor the
   closure flag may land alone.

## Candidate Universe and Refusal

The candidate universe is a union, not the observed corpus. It includes fields
from all of these surfaces:

- every authored source format;
- template output and every writer-emitted record;
- keyed consumer reads;
- Pydantic projection fields and defaults;
- existing base and schema fields applicable to the kind; and
- known retired or tombstoned fields.

A zero-occurrence field can still be prescribed by a template. Conversely, a
corpus containing no bad key cannot prove rejection behavior. Inventorying only
observed records would therefore certify accidents of the current corpus rather
than the complete contract.

Omission is the default refusal. Explicit `false` is reserved for a
base-admitted field that the kind deliberately narrows away, or for a tested
tombstone whose rejection is itself part of the contract. The 231-key shadow
schema must not become a 231-entry deny list: that would duplicate the very
vocabulary the composed schema is meant to derive.

## `promoted_from` Ownership and Shape

`promoted_from` is a **per-kind core field**. Its fixed semantics are the
authored artifact this entity was promoted out of: a source location, not an
idea origin. Each kind that admits it declares the shape inline in its own
mixin, matching this frozen literal oracle from
`~/d/protein-landscape/schemas/extension-protein-landscape-promotion-1.0.json`:

```json
{"type": "string", "minLength": 1,
 "description": "Path of the source file this entity was promoted from, e.g. knowledge/sources/local/entities.yaml"}
```

The gate compares every admitting mixin with that literal. Pairwise equality
between mixins is insufficient: all mixins could drift to the same wrong value,
repeating the tautology defect one level down.

The ownership alternatives are closed:

| Alternative | Ruling |
|---|---|
| Per-kind core field | **Selected.** Admissibility belongs to the kind and is decided inside that kind's atomic slice. |
| Universal base field | Rejected. It requires a versioned base change and makes the field reachable on every composed project kind, including kinds where the concept is meaningless. |
| Delete the field | Rejected. It carries real provenance and toolkit code writes it when promoting a decision-log section. |
| Project extension | Refuted. `science/src/science_tool/graph/decision_log.py` writes it onto a core kind; requiring every project to declare protein-landscape's extension merely to survive that toolkit write is inverted ownership. |

Four of the five tranche kinds carry the field: `concept` (132), `finding`
(26), `observation` (25), and `method` (20).

This ownership correction does not turn the field into an idea origin.
`promoted_from` is not migratable into `origins`: `OriginRecord.type` names
*who* had the idea, while `promoted_from` values name *where* the entity came
from. Any chosen origin type would fabricate provenance.

## `finding`: Source Migration and Gate 3

The `finding` slice is the one tranche slice that carries a source migration.
In
`~/d/natural-systems/knowledge/sources/project_specific/finding.yaml`, 149
generated rows have `created: 2026-04-30` and no `updated`.

The migration rule is exactly:

```text
updated = created
```

Migration date, file mtime, and current date are each rejected **by name**.
Those three alternatives and the correct value all produce a schema-valid
`format: date` string, so schema validation cannot distinguish honest
provenance from fabrication. The test must assert the provenance semantics
directly and mutation-test all three rejected alternatives.

Gate 3 is a hard prerequisite for this migration. The backfill is a one-time
edit to the source file, not a loader default. The loader must continue to fail
when a row genuinely lacks `updated`; defaulting it during load would make gate
3's behavioral test unfalsifiable.

## Corpus Certification

Corpus certification runs per adapter, not per format, under the
`real_projects` marker. For each project, compose the candidate profile with
that project's own declared extensions. In particular, certification must
preserve:

- mm30's `mm30.assessment`;
- evolution's `evolution.provenance`; and
- protein-landscape's `protein-landscape.promotion`.

These combinations demonstrate that `unevaluatedProperties: false` rejects
undeclared fields without rejecting projects that did nothing wrong.

The 20 expected project identities are frozen. When `-m real_projects` is
explicitly selected, a missing project fails rather than skips. Otherwise,
"all 20 passed" can silently degrade into "the 17 available passed."

## Untyped Kinds

Four of the five tranche kinds — `concept`, `search`, `finding`, `observation` —
have no entry in `CORE_KIND_MODELS` and project onto the generic `ProjectEntity`,
70 fields shared with 29 other kinds. Only `method` is typed, and `hypothesis`, the
kind the procedure was drafted against, is typed. So this is the common case, not
the exception, and step 5 means something different for it.

**The gap direction — schema admits, model does not declare — is not free.**
`science/tests/test_kind_reconciliation.py` holds a frozen `UNHELD` manifest: every
admitted-but-undeclared field needs either a `Reader` (a named symbol, AST-verified to
perform a keyed read of that field) or a `PendingRuling` (explicit debt, written after
looking for a reader and finding none). Equality is checked in both directions, so a
stale exemption fails as loudly as a new gap. Search for the reader per field; do not
infer one from a neighbouring kind's entry. The concept slice found five fields with
no reader and one — `tags` — with a real kind-agnostic one, which no amount of
reasoning by analogy from the commons entries would have produced.

**The surplus direction — model declares, schema never admits — is not a finding.**
`taxon` on a concept is dead weight in a shared model, and requiring an explanation per
field would mean writing the same sentence fifty times.

## A Slice Owes Its Value Battery

`science/model/tests/test_value_reconciliation.py` requires every declared mixin to be
either value-reconciled or listed in `PENDING_PROFILES`. A closing slice owes the
battery in the same branch: `PENDING_PROFILES` is the debt list for mixins that exist
and enforce nothing, which is exactly what a closed kind is not. S1b's four are the
commons kinds; a tranche kind has no owner there.

The battery covers the intersection of the composed schema with the model's declared
fields, per generation, and every entry needs at least one value the schema refuses and
one it admits. Compare against `model_dump(mode="json")`: `created` and `updated` are
`datetime.date` on the model, so a plain dump reports preservation loss against the
authored ISO string where there is none.

## Slice Order

1. `concept` — **DONE** (2026-07-28). 329 documents, 4 non-base fields, the reference
   class. See
   [`../plans/2026-07-28-schema-closure-concept-slice-inventory.md`](../plans/2026-07-28-schema-closure-concept-slice-inventory.md).
2. `method` — **DONE** (2026-07-29). 51 documents, the only tranche kind with a typed
   subclass (`MethodEntity`), so step 5 was the two-directional check as originally
   written. See
   [`../plans/2026-07-29-schema-closure-method-slice-inventory.md`](../plans/2026-07-29-schema-closure-method-slice-inventory.md).
3. `search`.
4. `observation`.
5. `finding` last, because it alone carries a source migration.

## A Mixin May Not Enum-Lock `status` Before Its Kind Is Certified

`status` is the one field where closure and vocabulary certification collide, and they
are different instruments on different axes.

`validate/kind_severity.py` holds `_CERTIFIED_KINDS`, and
`validate/checks/status_vocabulary.py` rules that an uncertified instrument may not fail
anyone's build — which is why `<kind>.status-vocabulary` is a WARN for every kind but
`hypothesis`. **A schema enum fails the build harder than a validate ERROR: it refuses
the record at load, with no warning stage at all.** So a mixin may declare
`status: {"type": "string"}` — shape, which is closure's business — and may enum-lock the
vocabulary only once its kind joins `_CERTIFIED_KINDS`.

`mixin-hypothesis-2.0` is the certified case, not a counterexample. `mixin-concept-1.0`
enum-locked an *uncertified* vocabulary; it was latent rather than live only because all
329 concepts are `active`. The `method` corpus made the same choice immediately visible:
one real record carries `status: proposed`.

**That debt is now closed.** `mixin-concept-1.1` drops the enum and changes nothing else,
and both generation rows move together. Two things about the shape of that fix generalize
to any mixin correction:

- **The old version stays on disk.** `GATE 2` is deliberately not biconditional, so a
  historical version armed by no row is legitimate — four already sit there
  (`dataset-1.0`, `paper-1.0`, `theme-1.0`, `topic-1.0`). Do not delete the superseded
  file; a consumer pinned to an older toolkit revision has its own copy either way, and
  the retained file is what makes the version number mean something.
- **"Only X changed" is a test, not a `$comment`.**
  `test_1_1_differs_from_1_0_in_STATUS_ALONE` compares the two packaged files
  property-by-property, excluding `$id` and `$comment` because those are *required* to
  differ — comparing them would make the test unfailable in the wrong direction. A bump
  that quietly carried a second change is otherwise indistinguishable from an honest one
  by its version number alone.

Note what the bump is *not*: a relaxation of what the corpus may say. All 329 records were
already `active` and none changes meaning. What changes is where the vocabulary is
enforced — validate's WARN rather than a load-time refusal — and the derived profile
string in `graph.trig`, which moves from `concept/1.0` to `concept/1.1`.

There is a third, independent reason. `status_vocabulary.py` deliberately keeps no
per-kind table because "the two would drift" — and a JSON enum in a mixin is exactly that
second table, one file further away and versioned on a different axis, so correcting a
vocabulary would require a mixin version bump.

## Step 5's Declarations Cannot Land Before Step 7

The procedure above reads as though steps 1–6 land as six independent commits. Three of
step 5's artifacts cannot:

- `test_kind_reconciliation.py`'s `UNHELD` entries — `test_every_exemption_names_a_live_profile`
  rejects a manifest entry for a `(generation, kind)` the profile table does not yet have.
- `test_value_reconciliation.py`'s `VALUE_RECONCILED_KINDS` —
  `test_the_declared_kinds_are_all_real_mixin_kinds` rejects a kind with no mixin.
- The value battery file itself, which calls `default_profile_for_kind(kind, generation=…)`
  and raises `ProfileParseError` until the generation rows exist.

All three are guards working correctly: each refuses to track debt for something that does
not exist. The consequence is that step 5's *declarations* belong in the step-7 commit,
even though the reconciliation work and its findings belong to step 5. What can land at
step 5 is the contract-reconciliation test, which reads the schema JSON and the registry
directly and needs no resolved profile.

## Unquoted YAML Dates Are a Standing Corpus Defect

`created: 2026-04-07` without quotes parses as a `datetime.date`, which base 2.0 refuses
as `{"type": "string", "format": "date"}`. **169 records across 7 projects** carry one, so
every remaining slice inherits a share; the `method` slice hit 2 and repaired them.

No `hypothesis` or `concept` record is affected, which is why `main` is sound rather than
quietly broken — verify that per kind rather than assuming, since two armed kinds passing
is also what "nobody has looked" produces.

The systemic alternative is normalizing dates to ISO strings before
`validate_against_schema`. It is defensible — the model already coerces both forms — but it
is kind-agnostic and belongs in its own branch, not inside a kind's slice.

### What the second slice added

- **A byte-identical graph diff is not evidence.** It is exactly what a slice that armed
  nothing produces. Pair it with a control in BOTH directions — one record carrying an
  undeclared key, refused while armed and loading while unarmed — or step 6 proves only
  that the sweep ran.
- **Certify with the project's own extension declarations read, not assumed.** Both
  extensions in the `method` corpus (`mm30.assessment`, `protein-landscape.promotion`)
  turned out to be `hypothesis`-scoped, so protein-landscape's promotion extension does
  not admit `promoted_from` on protein-landscape's own methods. The mixin carries all 20.
- **A zero-occurrence field can be load-bearing.** `stochasticity` and `seed_params` are
  authored by no record in any project, and are declared by `MethodEntity`, prescribed by
  the template under `{ omit: true }`, and read by six production modules. Omitting them
  would have passed every corpus check while making the shipped method-stochasticity
  program unauthorable. Inventory the template's `omit: true` fields explicitly.
- **Test FIXTURES author records too, and they are the least complete records in the
  tree.** Arming broke `test_dataset_register_run.py`, whose seed wrote a `method` with no
  `status`/`created`/`updated` — legal only while the kind was open. Budget for fixtures
  alongside the guards that enumerate the armed set; a corpus sweep does not see them.
  (That same fixture authors `stochasticity`, which no real record does — corroborating
  that the zero-occurrence admission above was load-bearing.)
- The Markdown authored-injected-key blind spot is **not** the one-line fix the first
  slice recorded. `validate_canonical_markdown_record` gets one merged dict from
  `adapter.load_raw(ref)` and cannot separate authored from injected keys; fixing it means
  the adapter reports what it injected per record — a `StorageAdapter` protocol change.

### What the first slice cost that the procedure did not predict

Arming broke four guards outside the schema layer, none of them in the graph:
`test_value_reconciliation` (×2, the battery above), `test_kind_reconciliation` (×2,
the manifest above), `test_entity_construction_boundary`'s open-kind example (it was
hard-coded to `concept`; it now derives an open kind, so the next slice will not break
it), and `science entity sections`, which starts listing frontmatter fields for a kind
once its profile resolves. Budget for guards that enumerate the armed set — the graph
diff was byte-identical and told us none of this.

## Debt This Tranche Does Not Close

Closing a tranche kind does not imply that adjacent populations have been
repaired:

- `hypothesis` realignment to the `promoted_from` ruling remains open debt. Its
  already-closed schema needs a versioned mixin bump.
- Six unclosed core kinds carrying `promoted_from` remain open debt and receive
  declarations only when their own kinds close: `topic` (64), `decision` (18),
  `paper` (17), `proposition` (9), `dataset` (4), and `workflow` (3).
- Three non-tranche structured-row populations stay untouched:
  `morphism-edge` (70), `limit-relation` (131), and `workflow` (6). Gate 3 makes
  their load path validating, but no closed profile applies to them; validation
  must not be mistaken for repair.

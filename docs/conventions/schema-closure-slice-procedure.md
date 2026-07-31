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
(26), `observation` (**14**, corrected from 25 by the slice-4 measurement — the earlier
figure predates the count over authored markdown frontmatter), and `method` (20).

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
   Its mixin was corrected after the fact by `mixin-concept-1.1` (2026-07-29) — see the
   `status` ruling below. **A slice being DONE does not mean its mixin is final.**
2. `method` — **DONE** (2026-07-29). 51 documents, the only tranche kind with a typed
   subclass (`MethodEntity`), so step 5 was the two-directional check as originally
   written. See
   [`../plans/2026-07-29-schema-closure-method-slice-inventory.md`](../plans/2026-07-29-schema-closure-method-slice-inventory.md).
3. `search` — **DONE** (2026-07-30). 36 documents across **seven** project roots, no typed
   subclass, no template, markdown-only. The first slice to carry a CORPUS migration. See
   [`../plans/2026-07-30-schema-closure-search-slice-inventory.md`](../plans/2026-07-30-schema-closure-search-slice-inventory.md).
4. `observation` — **DONE** (2026-07-30). 21 documents in a **single** project root, no typed
   subclass, markdown-only, and the first slice whose substantive finding came from the WRITER
   surface rather than the corpus. See
   [`../plans/2026-07-30-schema-closure-observation-slice-inventory.md`](../plans/2026-07-30-schema-closure-observation-slice-inventory.md).
5. `finding` — **DONE** (2026-07-30), and last. 201 records across 3 project roots by **two**
   structurally different authoring paths — 52 markdown and 149 structured source rows — the only
   core kind routed through the structured-source loader, and the only slice carrying a source
   migration. See
   [`../plans/2026-07-30-schema-closure-finding-slice-inventory.md`](../plans/2026-07-30-schema-closure-finding-slice-inventory.md).

**THE TRANCHE IS COMPLETE.** All five tranche kinds are armed, alongside `hypothesis`:
`PROJECT_MIXIN_NAMES == {hypothesis, concept, method, search, observation, finding}`. This is
not the end of schema closure — 47 of the 53 shipped kinds remain open, and everything under
"Debt This Tranche Does Not Close" is untouched.

> **Corrected by slice 3:** this list used to say `finding` "alone carries a migration".
> `finding` alone carries a *source* migration (`updated = created` over structured rows).
> `search` carried a *corpus* migration — 7 records in 2 repos authored `task`/`task_ref`,
> keys no production code read — and any slice can turn out to need one. The question step 1
> must ask is not "is this the `finding` slice?" but "does any authored field have to move
> before the mixin can refuse it?"

Rough populations for the three remaining kinds, measured 2026-07-30 by scanning `kind:`
declarations across the 7 projects. **These are scoping estimates, not inventories** — step
1 owns the real count, over the candidate universe rather than the observed corpus:

| kind | ≈records | where |
|---|---|---|
| `search` | 36 | cancer 19, health 10, natural-systems 7 |
| `observation` | 21 | **confirmed exactly by slice 4**, and narrower than "health": all 21 are in the single root `health/processes/cycles`, one of health's five projects. The other 16 roots were each asserted empty |
| `finding` | **52 markdown + 149 source rows = 201** | **confirmed exactly by slice 5**, correcting this row's estimate: protein-landscape 26 ✓, cancer 3 ✓, natural-systems **23** (not 24), plus 149 structured rows in natural-systems alone. The estimate was a `kind:` grep; the inventory is a frontmatter parse |

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
as `{"type": "string", "format": "date"}`. The `method` slice hit 2 and repaired them.

**Re-measured 2026-07-30, superseding the "169 records" figure recorded during the
`method` slice.** 187 markdown files across the 7 projects carry an unquoted
`created`/`updated` in frontmatter. They split two ways, and the split matters:

| | count | |
|---|---|---|
| entity records (carry a `kind:`) | 166 | plan 44, question 31, report 25, evidence-line 21, interpretation 19, discussion 12, topic 8, probe 5, paper 1 |
| non-entity process artifacts (no `kind:`) | 21 | all under `natural-systems/pipeline/**` — verdicts, source notes, integration patches |

The earlier figure counted the 2 since-repaired `method` records and did not separate the
21 kind-less files, which are not entities and no slice will ever close.

**No `hypothesis`, `concept`, `search`, `observation` or `finding` record is affected** —
checked in markdown frontmatter *and* in the YAML sources, since `finding` is partly
source-backed. So `main` is sound, and — correcting what this section previously said —
**the remaining slices do not each inherit a share: they inherit none.** Every affected
kind is outside the tranche. Do not budget slice time for this, and do not treat a clean
certification run as evidence the defect was fixed.

Verify per kind rather than assuming, in either direction: armed kinds passing is also
what "nobody has looked" produces, and so is a tranche that happens to be clean.

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

### What the third slice added

- **Certify per PROJECT ROOT, not per repo.** A repo-level scan reported "cancer 19" for
  `search`; that is four projects (`multiple-myeloma` 8, `cbioportal` 8,
  `mechanisms/evolution` 2, `meta` 1). The project root is the unit that owns a
  `science.yaml` and therefore the unit whose extensions compose, so a repo-level count
  can hide a project whose extensions were never checked.
- **A migration target must be verified by RESOLUTION, not by grep.** Step 1 read
  `t01`/`t02`/`t03` in mm30's `tasks/archive.md` — a file whose stated purpose is to
  "preserve reference integrity" — and concluded `task:t01` was a valid ref. It is not:
  `archive.md` declares aliases in prose and the resolver loads *entities*, so the
  migration produced three `unresolved_reference` errors. The contrast made it visible —
  `task:t828`, `task:t021`, `task:t761`, `task:t072` all resolve, because those name real
  task records. The plausible-sounding file was what made the wrong answer attractive.
- **`science validate` MUTATES the project it validates.** Repeated runs created ten
  untracked topic entities (each a local copy of an existing commons overlay, each then
  producing `overlay-local-duplicate` plus a cascade of `ambiguous_reference`), so the
  reported error count climbed 3 → 24 → 109 → 168 across *identical* runs. A run also
  modified a tracked task file, which then flipped that task's status in a rebuilt
  `graph.trig`. Consequences: a before/after `validate` comparison is only valid between
  restored-identical tree states, and a certification run's `knowledge/*.trig` must never
  be committed — it absorbs unrelated mutations. Tracked as F6.
- **Count the UNHELD entries, do not copy the block.** `search` needs FIVE, where
  `concept` and `method` each need six: `promoted_from` is absent because the mixin never
  admits it, so it cannot be admitted-but-undeclared. Copying the neighbouring block
  would have added a sixth entry, and the manifest's two-way equality would have failed —
  loudly, this time, but only because that guard exists.
- **A mutation that does not apply looks exactly like a guard that does not fire.**
  Mutating `extra="allow"` "on `ProjectEntity`" was a no-op — `ProjectEntity` does not
  declare it, it inherits from `Entity` — and the clean run read as a blind guard. It also
  exposed a false claim that both this slice and the shipped `concept` slice carried:
  `Entity` is `extra="allow"` by D3.3, not `extra="ignore"`. **Verify that a mutation
  changed what you think it changed before concluding anything from the result.**

### What the fourth slice added

- **Inventory the kind-agnostic MUTATORS, not just the kind's own surfaces.** The candidate
  universe already says "every writer-emitted record", and the first three slices applied that
  to the kind's template and corpus — neither of which can show what a kind-agnostic mutator
  writes. `consolidate.py:183` stamps `consolidated_into` onto any member's frontmatter and
  `unarchive` restored it to a live, schema-validated path, **failing the whole project load
  for `hypothesis`, `method` and `search` — all already armed.** `concept` escaped only by
  accident (its status vocabulary omits `archived`, so the consolidate gate refuses it
  upstream), and `hypothesis` escaped the sibling `superseded_by` defect only because
  `HypothesisEntity` declares the field as a typed model field, so its mixin inherited the
  coverage from the model rather than from anyone's inventory. The step-1 question to add:
  **which kind-agnostic mutators can write to this kind's frontmatter?** Answer it from the
  mutators and the descriptor flags (`supersedable`; whether `statuses` contains `archived`),
  never from the corpus — which by construction cannot contain a key that would have refused it.
- **A field's ruling can be "the writer is wrong".** Omission and admission are not the only
  moves. `consolidated_into` has no frontmatter reader — `entities.py:1004` and
  `big_picture/digests.py:77` both read `ArchiveRow.consolidated_into` from the archive index —
  so admitting it in four mixins would have enshrined duplicated bookkeeping in versioned
  schemas. The slice fixed `unarchive` to strip it instead. Ask who READS the value before
  deciding which authority should change.
- **"Budget for fixtures" is too coarse; intersect with the generation declaration.** Step 1
  predicted arming would break two `observation` fixtures that author no `status`. It broke
  **zero**: `validate_against_schema` returns early when `project_schema is None`, and a
  fixture project that declares no `entity_schema_version` is not leniently validated but
  *unvalidated*. Measured across the tree: 20 fixture files declare a generation and none of
  them authors an observation; the 2 that author observations declare none. The `method`
  slice's casualty declared `entity_schema_version: 3` explicitly. **A fixture is exposed only
  if its project declares a generation.**
- **Verify what reaches the SCHEMA by watching the schema.** Slice 3 admitted `profile` on
  `search` because it read a `setdefault("profile", …)` in the loader and inferred injection.
  That call is on the structured-row path, and enrichment runs *after* `validate_against_schema`
  in any case, so nothing it adds can face the schema. Instrumenting the validator on a real
  gen-3 load shows the validated key set is the authored frontmatter minus exactly
  `{canonical_id, content, file_path}`. The admission is harmless but its rationale was wrong,
  and a rationale is what the next slice copies.
- **A single-project kind cannot certify itself, and the tests should say which claims it
  cannot support.** All 21 records live in one root. This slice's certification therefore
  enumerates the other 16 roots and asserts each empty, so "one project owns the corpus" is
  distinguishable from "only one project was examined" — and names, in the tests themselves,
  that no probe over this corpus can distinguish a correct `status` vocabulary from an
  over-tight one.
- **The corpus's own project may not be loadable.** `~/d/health/processes/cycles` fails to
  load because its aggregate task store predates the storage split — on `main` too, so it is
  pre-existing — which makes step 6's end-to-end half impossible for the very project holding
  every record. The
  `search` slice hit this with `post-acute-infection`. When it happens, say so, run step 6 on
  a synthetic project of the same shape, and pair the byte-identical graph diff with a control
  run against **both real toolkits** rather than one patched one.

### What the fifth slice added

- **A kind can reach the schema by more than one PATH, and the authored boundary differs per
  path.** `finding` is the only core kind a project routes through the structured-source loader
  (`core_structured_sources` in `~/d/natural-systems`), so 149 of its 201 records arrive with a
  different injected-key contract (`_STRUCTURED_INJECTED_KEYS - authored`) than the other 52. The
  same key, `file_path`, is *declared injected* on markdown and *faces the schema as authored* on
  structured rows — correctly, because those rows author `source_path` and normalization renames
  it. Step 1's question is therefore not "what does the corpus contain?" but **"by which paths do
  records of this kind reach `validate_against_schema`, and what does each one hide?"**
- **The procedure's own scoping note can under-describe the migration.** It said the `finding`
  rows "have `created: 2026-04-30` and no `updated`". True — and they also author no `status`,
  which no one had measured. Requiring `status` (as all four other armed mixins do) turned a
  one-field migration into a two-field one. A scoping estimate names what someone noticed, never
  what step 1 owes.
- **`extra="allow"` on a nested model is not the same forgiveness as on the entity.** The schema
  admits `relations: [{predicate, target, note}]`-shaped input only if the mixin says so, but
  `AuthoredTargetedRelation` declares three fields and **discards** anything else — so 3 records
  had been authoring multi-line prose into a black hole. Found by reading the projection's output
  on a real load, not the model definition. Ruled a corpus migration after checking that each
  `note` restated its own record's `## Summary`; the mixin reuses `$defs/authored_relation`
  verbatim so the discard becomes a refusal.
- **A "preservation" test must distinguish a lost value from a materialized default.** The value
  battery's strict `dumped[field] == value` is correct for scalars and string lists and WRONG for
  a field whose items are typed objects: `graph_layer` defaults to `graph/knowledge`, so an
  authored `{predicate, target}` dumps with a third key. Relaxing it needs its own guard —
  otherwise "a default was materialized" becomes an unfalsifiable excuse for any projection
  change.
- **F1 was already closed and the follow-up table still said it blocked every slice.** The
  per-call-site `injected` contract exists, is required (no default), and is documented at
  `entity_registry.py:255-291`. A tracked follow-up is a claim about the tree, and it ages the
  same way a memory's "NEXT = phase X" does. **Re-verify a follow-up against the code before
  planning around it** — this slice nearly designed work that was already done.
- **Both generation rows carried real corpus for the first time.** Earlier slices moved rows 2
  and 3 together on principle, with the risk theoretical. Here 172 of 201 records live in a
  generation-2 project and 29 in generation-3 ones, so a row-3-only arming would have left the
  majority of the corpus resolving an unclosed profile.

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

### Tracked follow-ups, with the shape each one actually needs

Ordered by what blocks slice work, not by size. Each names its known shape so the next
reader does not re-derive it — and two of these were re-sized *after* being filed, which
is why the shape is recorded rather than just the title.

| # | Item | Shape | Blocks a slice? |
|---|---|---|---|
| F1 | ~~Markdown adapter cannot separate authored from injected keys~~ | **CLOSED**, verified by the `finding` slice 2026-07-30. `EntityRegistry.build` takes a **required** `injected` frozenset with no safe default, and four call sites each pass their own contribution (`MarkdownAdapter.INJECTED_KEYS`, `_STRUCTURED_INJECTED_KEYS - authored`, `_LEGACY_INJECTED_KEYS - authored`, `_COMMONS_INJECTED_KEYS - frozenset(fm)`). Rationale at `entity_registry.py:255-291`. | No — and it had been listed as the highest-value blocker after it was already fixed |
| F2 | `hypothesis` realignment to the `promoted_from` ruling | Versioned mixin bump, exactly like `mixin-concept-1.1`. The bump procedure is now demonstrated. | No |
| F3 | Unquoted YAML dates | 166 entity records + 21 kind-less process files. Either a corpus repair or normalizing dates before `validate_against_schema`. Kind-agnostic; needs its own branch and a design call between the two. | **No** — zero tranche-kind records affected (measured both markdown and YAML) |
| F4 | `render_update`'s stale-owned-key hole | `final.pop(key, None)`, but that also drops the `legacy_*` triple, so it needs its own pass rather than a one-liner. | No |
| F5 | Six unclosed core kinds carrying `promoted_from` | Resolved by their own slices; no separate work. | No |
| F6 | `science validate` writes to the project it validates | Creates local topic entities duplicating commons overlays (one per run) and appends to tracked task files. Needs the topic-materialisation path traced to its writer; `validate` should be read-only. | Not a blocker, but it makes step-4/6 measurement untrustworthy unless the tree is restored between runs |
| F7 | ~~`mixin-method-1.0` omits `superseded_by` on a `supersedable` kind~~ | **CLOSED** 2026-07-30 by `mixin-method-1.1`, a versioned bump exactly like `mixin-concept-1.1` (new file, 1.0 retained as a historical version armed by no row, both generation rows repointed, probe file renamed). **The filing was one key short.** 1.0 admitted neither `superseded_by` *nor* `relations`, and the inverse was unreachable *because* its carrier was: with no `relations` declaration under `unevaluatedProperties: false`, the canonical `sci:supersedes` edge could not be authored on a method at all, so `mark_superseded` raised at the **superseder's** file (`'relations' was unexpected`) before it ever reached the member it wanted to stamp. That is LEG 1 of the D4 supersedable gate — the same defect `mixin-hypothesis-1.0` was written to close. Prospective, not corrective: all 38 live methods carry zero `relations`, zero `superseded_by`, zero `status: superseded`. Generalized into **GATE 5** (`test_schema_closed_gate.py`), which derives its scope from `supersedable ∧ schema_closed` and asserts both carriers, so the remaining 47 kinds cannot repeat it. | No, but it was a **reachable defect in shipped work**, like the `consolidated_into` one the `observation` slice fixed |
| F9 | `_STRUCTURED_INJECTED_KEYS`' comment generalizes a per-kind fact | `sources.py:122-125` justifies exposing `profile`, `aliases`, `ontology_terms`, `related`, `source_refs` as authored because they "are admitted (measured)". Measured across all 16 packaged schemas: `ontology_terms` is base-wide; `related`/`source_refs` are admitted by all five armed mixins; **`profile` is not admitted by `observation`**, and **`aliases` is not admitted by `concept`, `search` or `observation`**, nor by any base or overlay. Fix is to widen the frozenset or restate the comment as the per-kind claim it is. | Not today — no armed kind but `finding` takes the structured path, and `finding` admits both keys. Blocks the **next** kind that takes it without authoring them |
| F10 | `interpretation` records author `relations[].note` | 19 records in `~/d/natural-systems`, the same silently-discarded key the `finding` slice migrated out of 3 records. That slice deliberately left them: each kind's slice owns its own corpus. Needs the same duplicate check (is the note restated in the body?) rather than copying the ruling. | No — `interpretation` is not a tranche kind and is not armed |
| F8 | `~/d/health/processes/cycles` cannot be loaded | Its aggregate task store predates the storage split; the fix is `science tasks migrate-storage --apply` in that project. Fails on `main` too, so it is not slice-induced. | Not a slice blocker, but it cost the `observation` slice the end-to-end half of step 6 for the only project holding its corpus, and will cost `finding` the same wherever it overlaps |

**What the two corrections to shipped work taught, stated once here because both were
the same failure:** a slice certifies its mixin against the corpus, and the corpus cannot
certify what it does not vary. `mixin-concept-1.0`'s `status` enum survived step 4 because
all 329 records are `active`; F1 was mis-sized because the filing described the fix from
the outside without opening `validate_canonical_markdown_record`. In both cases the
artifact was written from a plausible model rather than a read. **Where a population is
uniform or a fix is described rather than traced, reason from the declaration and the
code, not from the measurement.**

**What closing F7 added to that (2026-07-30).** The filing named `superseded_by` because
that is the key someone had *watched a writer stamp*. It did not name `relations`, because
nothing observable pointed at it — the carrier's absence produces no stamped key to notice,
only an operation that fails earlier and elsewhere. Reproducing the defect took thirty
lines and found the real shape in one run; reasoning from the filing would have shipped a
`1.1` that admitted the inverse and left the kind exactly as unsupersedable as before, with
a green test suite over it.

Two rules follow, and the second is the general one:

1. **Reproduce a filed defect before fixing it, even when the filing looks precise.** A
   filing records the symptom its author reached, not the boundary of the defect. F7 was
   written by the `finding` slice, which was doing everything right and still under-named
   the thing by half.
2. **A capability flag is a claim about a whole path, so check the whole path.**
   `supersedable=True` asserts that a kind can be superseded — which needs the carrier, the
   endpoint pair, the writer, the terminal status, *and* the schema admitting both ends.
   Checking any one leg proves nothing about the others. GATE 5 now holds the schema half
   of this for every armed kind, derived from the flag rather than enumerated, because a
   guard that lists its scope has a hole by construction — and `method` fell through exactly
   such a hole while `hypothesis` and `finding` sat beside it with both carriers.

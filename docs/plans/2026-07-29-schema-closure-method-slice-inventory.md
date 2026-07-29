# Schema-Closure Slice 2 — `method` Field-Surface Inventory

Step 1 of the seven-step slice procedure
([`../conventions/schema-closure-slice-procedure.md`](../conventions/schema-closure-slice-procedure.md)).
This document freezes the candidate universe and the disposition of every field
before the mixin is written.

`method` is the second tranche kind and the only one with a typed subclass
(`MethodEntity`), so step 5 is the two-directional check as originally written
rather than the `UNHELD`-manifest form the `concept` slice needed.

## Corpus Measurement

51 authored `method` records across five projects. The count independently
confirms two existing claims in the tree: `MethodEntity`'s docstring ("46 of the
51 authored `method` entities are glossary terms or design documents") and the
procedure's `promoted_from` tally for this kind (20).

| field | mm30 | protein-landscape | post-acute-infection | seq-feats | cbioportal | total |
|---|---:|---:|---:|---:|---:|---:|
| `id`, `kind`, `title`, `status`, `created`, `updated` | 25 | 13 | 6 | 5 | 2 | **51** |
| `related` | 8 | 9 | 6 | 0 | 2 | 25 |
| `promoted_from` | 16 | 4 | 0 | 0 | 0 | 20 |
| `ontology_terms` | 1 | 6 | 0 | 5 | 0 | 12 |
| `source_refs` | 3 | 7 | 0 | 0 | 0 | 10 |
| `datasets` | 1 | 6 | 0 | 0 | 0 | 7 |
| `profile` | 0 | 4 | 0 | 0 | 0 | 4 |
| `description` | 0 | 4 | 0 | 0 | 0 | 4 |
| `aliases` | 0 | 4 | 0 | 0 | 0 | 4 |

All five projects pin `entity_schema_version: 3`. Two declare project
extensions: mm30's `mm30.assessment` and protein-landscape's
`protein-landscape.promotion`.

**All 20 `promoted_from` records depend on this mixin declaring the field.** They
are admitted today only because the kind is open. mm30 (16) declares no promotion
extension at all, and protein-landscape's `protein-landscape.promotion` — the
frozen literal oracle's own home — is scoped to `hypothesis`, so it does not
reach that project's own 4 methods. This is the sharpest single argument for the
disposition below.

(An earlier revision of this document said "16 of 20", on the assumption that
protein-landscape's extension covered its own 4. Step 4 read the declaration and
found it `hypothesis`-scoped.)

Sweep exclusions applied, per the trap the `concept` slice recorded: `.venv` /
`site-packages` (the packaged `science_model/templates/method.md` carries
`kind: method` frontmatter and reads as a record) and any document with a
`_template:` block. Projects were enumerated by discovery — 39 `science.yaml`
roots under `~/d`, of which 18 are toolkit test fixtures and contribute zero
`method` records.

## Candidate Universe

The union of surfaces, not the observed corpus.

### Authored source formats

No structured-source path. Zero `knowledge/sources/**/*.yaml` files declare a
`method` entity in any project, so unlike `finding` this slice carries no source
migration.

### Template output

`science/model/src/science_model/templates/method.md` (and its `templates/`
mirror) prescribes ten frontmatter keys, and its rendered output was measured
rather than read off the file — `build_entity_markdown(kind="method", …)` emits
exactly `id`, `kind`, `title`, `status`, `ontology_terms`, `datasets`,
`source_refs`, `related`, `created`, `updated`.

The template additionally declares `stochasticity` and `seed_params` under
`{ omit: true }`. Per `templates.py:243`, `omit` means the field is part of the
kind's declared frontmatter contract but is not rendered. **This is the
procedure's zero-occurrence case exactly**: both fields are prescribed by the
template, declared on the model, and read by production code, while no record in
any project authors either one.

### Writer-emitted records

`create_entity` accepts an arbitrary `extra_frontmatter` mapping, but the only
callers that inject provenance keys (`origins`, `added_by`) are the typed CLIs —
`hypotheses_cli`, `questions_cli`, `discussions_cli`, `propositions_cli`,
`evidence_lines_cli`, `interpretations_cli`. `entities_cli` imports only
`emit_entity_show` / `emit_entity_warnings` from `typed_entity_cli`, so the
generic `science entity add` does not wire `--origin` / `--added-by`. **No
toolkit writer emits `origins` or `added_by` onto a `method`**, and neither is
declared.

`create_entity` also calls `_validate_status`, so CLI writes enforce the kind's
status vocabulary. Every out-of-vocabulary status in the corpus is therefore
hand-authored — which is the case the `status` ruling below turns on.

### Keyed consumer reads

- `stochasticity` — `seed_policy_derivation.py:90,103,105,120`,
  `datasets_stochasticity.py:156`, `validate/checks/methods.py:38`,
  `validate/checks/workflow_steps.py`.
- `seed_params` — `seed_policy_derivation.py:107,110,125`,
  `validate/checks/methods.py:38`.
- `aliases` — kind-agnostic and widely read: `entity_identity.py:73`,
  `entities_inventory.py:88,97`, `labnote_export.py:320,352`, `archive.py:137`,
  `spec_paths.py:74`, `consolidate.py:184`, `migrate_specs.py:438,650`.
- `related`, `source_refs` — `graph/migrate.py:_AUDITED_REFERENCE_FIELDS`.
- The graph reads a method only as the target of a workflow-step's `sci:applies`
  edge (`materialize.py:1193`), which keys on `kind` alone.

### Pydantic projection

`MethodEntity(ProjectEntity)` adds exactly two fields — `stochasticity`,
`seed_params` — to `ProjectEntity`'s 70, with `extra="allow"`.

Of the fields this slice proposes to admit, only **`promoted_from`** is not a
declared model field; it survives as an extra. Every other admitted field is
declared.

### Base schema fields

`science-entity-base-2.0.json` admits 16 properties. `description` (4 records)
and `ontology_terms` (12) are base-admitted and need no mixin declaration.

### Retired / tombstoned fields

None. No `method` field has been retired, and no tombstone is required.

## Dispositions

| field | disposition | basis |
|---|---|---|
| `id` | admit, `pattern: ^method:` | PREFIX only, per the `mixin-hypothesis-2.0` ruling — base 2.0 owns the id's shape, the mixin owns its identity. All 51 ids carry the prefix |
| `kind` | admit, `const: method` | |
| `status` | admit, `{"type": "string"}` — **no enum**, see the ruling below | 50 `active`, 1 `proposed` |
| `related` | admit, array of string | 25 records |
| `promoted_from` | admit, frozen literal oracle | 20 records, 16 of them in a project with no promotion extension |
| `source_refs` | admit, array of string | 10 records |
| `datasets` | admit, array of string | 7 records |
| `profile` | admit, string | 4 records, all `local`. Authored and honored, same as `mixin-hypothesis-2.0` and `mixin-concept-1.0` |
| `aliases` | admit, array of string | 4 records; heavily read across nine modules |
| `stochasticity` | admit, `enum: [deterministic, seedable, nondeterministic]` | **0 authored**; template-prescribed, model-declared, six production readers |
| `seed_params` | admit, array of string | **0 authored**; same three surfaces |
| `description`, `ontology_terms` | inherit from base | base admits them; nothing justifies narrowing a kind-agnostic base field for this kind |
| `schema_profile` | narrow to `false` | Precedent: `mixin-hypothesis-2.0` and `mixin-concept-1.0` both narrow it. `profile` is the authored field, `schema_profile` its serialized counterpart |
| `contributors`, `dataset_usage`, `licenses`, `same_as`, `sources`, `tags`, `version` | inherit from base | 0 occurrences; no kind-specific reason to narrow |

Everything else is refused by omission.

### `stochasticity` and `seed_params` — the zero-occurrence admission

These two fields are the reason the procedure insists the candidate universe is
a union of surfaces rather than the observed corpus. Inventorying only what the
corpus authors would omit both, and closing the kind would then make the entire
shipped method-stochasticity program unreachable: the first author to classify a
method's randomness would find the record refused at load.

`stochasticity` is declared as the three-value enum and **does not admit an
explicit `null`**. The model types it `Stochasticity | None = None`, and absence
already means *unclassified*. Admitting `stochasticity: null` would create a
second spelling of absence — the defect `mixin-hypothesis-2.0` refuses by name
when it excludes `proposed` / `under-investigation` from `verdict`.

### Proposed ruling: `status` carries no enum

This is the one disposition that departs from the `concept` slice, and it is
load-bearing enough to state separately.

`mixin-concept-1.0.json` declares `status` with
`enum: ["active", "deprecated"]`, sourced from the kind descriptor. Applying the
same pattern to `method` would mean
`enum: ["active", "superseded", "retired", "archived"]` — the descriptor's
vocabulary at `profiles/core.py:504`.

That enum refuses a real record today:
`~/d/cancer/data-sources/cbioportal/entities/methods/length-aware-geneset-enrichment.md`
carries `status: proposed`. Three facts decide the ruling:

1. **The vocabulary is uncertified.** `validate/kind_severity.py:24` holds
   `_CERTIFIED_KINDS = frozenset({"hypothesis"})`. `method` is not in it, so
   `method.status-vocabulary` is a WARN by policy. `status_vocabulary.py` states
   the doctrine directly: *"an UNCERTIFIED instrument cannot refute … it may not
   fail anyone's build."* A schema enum fails the build harder than a validate
   ERROR — it refuses the record at load, with no warning stage at all.

2. **The observed conflict is the documented failure mode.** That module records
   what happened when this check first shipped grading on the wrong axis: 472
   entities errored, *"~3 in 4 of them because the vocabulary was wrong, not the
   entity (`report` had no terminal state; `plan` had no `draft`;
   `pre-registration` had no `committed`, the very state our own template and
   command prescribe)."* A designed-but-unbuilt method is a real state and the
   `method` vocabulary has no word for it. On the evidence, the vocabulary is
   the more likely defect — and deciding that belongs to the D5 certification
   arc, not to a schema-closure slice.

3. **An enum in the mixin is a second definition of the vocabulary.**
   `status_vocabulary.py:20-22` rules that there is deliberately *"NO table
   here: a per-kind list in this file would be a second definition of the
   vocabulary, and the two would drift."* A JSON enum in the mixin is precisely
   that second definition, one file further away, and versioned on a different
   axis — correcting a vocabulary would require a mixin version bump.

`hypothesis` is not a counterexample. Its mixin carries a six-value `status`
enum *and* it is the single certified kind; the enum was earned in its D5 slice.
The rule is therefore: **a mixin may enum-lock `status` once its kind joins
`_CERTIFIED_KINDS`, and not before.** Closure refuses fields nobody declared;
certifying a value vocabulary is a different instrument on a different axis.

Under this ruling the `proposed` record keeps loading and keeps producing its
existing `method.status-vocabulary` warning — the finding stays visible on the
surface that owns it, and closure adds no new verdict.

### Consequence for the shipped `concept` mixin

> **Closed 2026-07-29 by `mixin-concept-1.1`** (branch `mixin-concept-1-1`), which
> drops the enum and changes nothing else. The finding below is the filing that
> produced it; it is kept as written because it is the measurement, not the fix.

The same reasoning applies retroactively. `concept` is not in `_CERTIFIED_KINDS`
either, so `mixin-concept-1.0.json`'s enum escalated an uncertified vocabulary
to a load refusal. Verified against `main` rather than assumed:

```
concept status=proposed -> REFUSED: 'proposed' is not one of ['active', 'deprecated']
concept status=active   -> ACCEPTED
```

No concept record is affected today — all 329 are `active` — so this is latent,
not live. It is recorded here as a defect of slice 1 and deliberately **not**
fixed in this branch: the merge boundary is one kind per branch, and correcting
`concept` means a versioned mixin bump that belongs to its own change.

## Step 3 — Production-Surface Alignment: No Change Required

Recorded rather than skipped, because "nothing needed changing" is a claim and
each surface was checked:

| surface | evidence |
|---|---|
| authored sources | zero `knowledge/sources/**/*.yaml` files declare a `method` entity in any project. Unlike `finding`, this slice carries no source migration |
| template | `templates/method.md` emits exactly the ten keys the mixin admits, measured by rendering it, and its two `{ omit: true }` fields are both admitted |
| writers | `build_entity_markdown(kind="method", …)` was executed; it emits the same ten keys. No caller injects `origins`/`added_by` for this kind |
| readers | every field a reader consumes is admitted; no reader keys on a field the mixin refuses |
| adapter records | validation runs on the authored view, before enrichment — `EntityRegistry.build` orders `validate_against_schema` → `enrich` → `model_validate`, so the eighteen enrichment keys are never shown to the schema |

## Step 4 — Certification

All 51 records validate against the composed candidate with
`unevaluatedProperties: false` armed, after one repair.

No project declares a `method` extension, so base + mixin **is** the production
composition for this kind — asserted rather than assumed, since a future
extension would silently widen what certification covers.

### The repair: two unquoted YAML dates

`~/d/protein-landscape`'s `coverage-denominators-and-claims` and
`embedding-report-card` carried `created: 2026-04-07` unquoted. YAML parses that
as `datetime.date`, and base 2.0 declares `created` as
`{"type": "string", "format": "date"}`, so both were refused. Both records
already quoted `updated` on the adjacent line, so the repair made each record
self-consistent rather than imposing a new convention. Verified before the edit
that the date was the *sole* defect: with the value coerced to an ISO string and
nothing else changed, both records validate.

Committed separately, in that repo (`6796628`).

### The 167 records this slice leaves behind

The two repaired records are not a protein-landscape quirk. A corpus sweep found
**169 records across 7 projects** carrying an unquoted `created` or `updated`:

| kind | records | | kind | records |
|---|---:|---|---|---:|
| `plan` | 44 | | `discussion` | 12 |
| `question` | 31 | | `topic` | 8 |
| `report` | 25 | | `probe` | 5 |
| `evidence-line` | 21 | | `method` | **2** |
| `interpretation` | 19 | | `paper` | 1 |

**No `hypothesis` or `concept` record is affected**, which is why `main` is sound
today rather than quietly broken — checked, because the alternative explanation
for two armed kinds passing was that nobody had looked.

Every remaining slice inherits a share of this. `topic` (8) and `paper` (1) are
the immediate ones; `plan`, `question`, and `report` are not tranche kinds but
carry 100 records between them.

The systemic alternative — normalizing `datetime.date` to an ISO string before
`validate_against_schema` — is a real candidate and deliberately not taken here.
`created: 2026-04-07` is idiomatic YAML, the model already coerces both forms,
and `model_dump(mode="json")` already round-trips through the ISO string, so the
schema is arguably checking the serialization rather than the value. But that
change is kind-agnostic: it alters the load path for `hypothesis` and `concept`
too, and belongs in its own branch with its own certification, not inside one
kind's slice.

## Step 6 — Derived-Behaviour Diff

**Intended-change allowlist: empty.** Closure is an admission gate; it is not
supposed to move a single derived output. Anything that moved would block the
slice.

Measured by making the real arming edit in the worktree, running the four
loadable method-carrying projects, reverting, and comparing — not by
monkeypatching. Six modules bind `PROJECT_MIXIN_NAMES` by value at import, so a
patched simulation can certify nothing while looking green.

| project | graph.trig | composite.trig | validate findings |
|---|---|---|---|
| mm30 | identical (20,220,294 B) | identical (22,657,244 B) | 0e/60w → 0e/60w, +0 −0 |
| protein-landscape | identical (1,672,234 B) | n/a | pre-existing crash, both runs |
| seq-feats | identical (962,473 B) | n/a | 383e/557w → 383e/557w, +0 −0 |
| cbioportal | identical (2,321,140 B) | identical (4,695,787 B) | 21e/100w → 21e/100w, +0 −0 |

Findings were compared **one by one** on
`(severity, rule, path, line, message)`, never by summary count: a substitution
that preserved the totals would read as "no change".

### The control that makes the table mean something

A byte-identical graph is exactly what a slice that armed *nothing* would also
produce. So the arming was tested directly, in both directions, with one record
carrying an undeclared `shadow_key` dropped into seq-feats:

- **armed** → `entities/methods/_zz-arming-control.md: method frontmatter does
  not satisfy its schema … 'shadow_key' was unexpected`, build refused;
- **unarmed** (same file, arming stashed) → build succeeds and materializes.

The corpus is therefore clean *and* the check is live. Without the second half,
the first is unfalsifiable.

### Pre-existing conditions, all reproduced identically before and after

- **cbioportal cannot build**: `tasks/active.md predates the storage split`. The
  same blocker `~/d/health/processes/post-acute-infection` carries, so **two** of
  the five method-carrying projects are graph-blocked for a reason unrelated to
  this slice. Their 8 methods are certified at the schema boundary only.
- **protein-landscape's `science validate` crashes** in that project's own
  `validate_local.py:66`, which constructs `Result(...)` without the required
  `qualifiers` argument — a project-side hook that has fallen behind the toolkit
  signature. Its graph diff is clean, which is the substantive evidence for that
  project; its finding-level diff could not be taken.

## Step 7 — Arming

Two edits arm enforcement: `schema_closed=True` on the `method` descriptor, and
`"method": "1.0"` in **both** generation rows. `PROJECT_MIXIN_NAMES` and
`TYPE_MIXIN_NAMES` both derive from the first, so the two lookups arming depends on
cannot drift apart.

Landing with them, because three guards refuse to exist before the profile does
(see the procedure's "Step 5's Declarations Cannot Land Before Step 7"):

- the six `UNHELD` entries;
- `VALUE_RECONCILED_KINDS`, plus the complement assertion;
- `test_method_entity.py`, the 17-field value battery.

And three that had to move because the armed set grew:

- `test_schema_closed_gate.py`'s hand-written roster — `{hypothesis, concept, method}`;
- `entities.py`'s docstring naming the closed kinds;
- **`test_dataset_register_run.py`'s fixture**, which seeded a `method` with no
  `status`/`created`/`updated`. Legal while the kind was open; not a record any real
  project has. Fixtures are the least complete records in the tree and a corpus sweep
  does not see them.

The four dormant assertions in `test_mixin_method_1_0.py` were flipped here, which is
what makes the two-line arming edit impossible to land silently.

## What This Slice Does Not Close

- `hypothesis`'s realignment to the `promoted_from` ownership ruling. Its mixin
  still does not declare the field.
- The `concept` status enum above.
- The `method` status vocabulary itself. Whether `proposed` should join the
  descriptor's four values is a D5 certification question; this slice
  deliberately leaves the record loading and the warning firing.
- The 167 unquoted-date records in kinds this slice does not close, and the
  load-path normalization that would retire the whole class.
- The Markdown adapter's authored-injected-key blind spot. `sources.py:434`
  passes `MarkdownAdapter.INJECTED_KEYS` unconditionally while every other call
  site passes `INJECTED_KEYS - authored`, so a record authoring `content:` has it
  hidden from the schema rather than judged by it — the exact failure
  `EntityRegistry.build`'s docstring names. The concept slice recorded this as a
  one-line fix; it is not. `validate_canonical_markdown_record` receives one
  merged `raw` dict from `adapter.load_raw(ref)` and cannot separate authored
  from injected keys, so the fix requires the adapter to report what it injected
  per record — a `StorageAdapter` protocol change. No `method` record exercises
  it, and a certification test pins that fact.

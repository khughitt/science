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

**16 of the 20 `promoted_from` records live in mm30, which declares no promotion
extension.** They are admitted today only because the kind is open. This is the
sharpest single argument for the mixin declaring the field: closing `method`
without it fails 16 mm30 records at load.

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

## What This Slice Does Not Close

- `hypothesis`'s realignment to the `promoted_from` ownership ruling. Its mixin
  still does not declare the field.
- The `concept` status enum above.
- The `method` status vocabulary itself. Whether `proposed` should join the
  descriptor's four values is a D5 certification question; this slice
  deliberately leaves the record loading and the warning firing.

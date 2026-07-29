# `concept` Slice — Step 1: Frozen Field-Surface Inventory

Step 1 of the seven-step procedure in
[`docs/conventions/schema-closure-slice-procedure.md`](../conventions/schema-closure-slice-procedure.md).
This document freezes the candidate universe and each field's disposition
**before** the mixin is written. It closes no kind and changes no behaviour.

Measured on `main` at `31ae8005`.

## Why `concept` is slice 1

Largest corpus, simplest tail, and the reference class (`EntityClass.REFERENCE`,
`profiles/core.py:420`) — so it proves the mechanism against the archetype
rather than a one-off.

## Corpus measurement

Swept `~/d` for markdown files whose frontmatter carries `kind: concept`,
excluding `.venv`, `site-packages`, `.worktrees`, `.git`, `node_modules`,
`__pycache__`, `.tox`.

| project | records |
|---|---|
| `~/d/cancer/cancer-types/multiple-myeloma` | 285 |
| `~/d/health` | 37 |
| `~/d/natural-systems` | 7 |
| **total authored** | **329** |

This reproduces the design's 329 exactly.

**Two measurement traps this sweep hit, recorded so the next slice avoids
them.** An unfiltered `rglob` first returned 331: the extra two are
`science_model/templates/concept.md` copies living inside consumer projects'
`.venv/lib/.../site-packages/`. The packaged template is a *record-shaped file
that is not a record* — it carries `kind: concept` and a `_template:` block, and
it inflated `related` by 2 and `source_refs` by 2 before exclusion. A sweep that
counts it is measuring the toolkit's own shipped scaffold as corpus. Separately,
a first pass over mm30 and natural-systems alone missed `~/d/health` entirely
(37 records, 11% of the corpus, and the sole carrier of `ontology_terms`) —
enumerate projects by discovery, never from recall.

## Candidate universe

The union of surfaces, per the procedure. Not the observed corpus.

### 1. Authored source formats

**Markdown frontmatter only.** A sweep of every `*.yaml` / `*.yml` under a
`sources` path in `~/d` found **zero** structured `concept` rows. `concept`
therefore has no structured-source path, no adapter split, and no analogue of
the `finding` slice's source migration.

Observed keys, with value types and cardinality over the 329:

| key | records | type | values |
|---|---|---|---|
| `id` | 329 | `str` | — |
| `kind` | 329 | `str` | `concept` |
| `title` | 329 | `str` | — |
| `status` | 329 | `str` | `active` (329) |
| `created` | 329 | `str` | — |
| `updated` | 329 | `str` | — |
| `profile` | 179 | `str` | `local` (177), `project_specific` (2) |
| `promoted_from` | 132 | `str` | 3 distinct paths, below |
| `related` | 42 | `list[str]` | 61 items |
| `source_refs` | 37 | `list[str]` | 5 items |
| `ontology_terms` | 37 | `list` | **all empty** |

`promoted_from` values:

| count | value |
|---|---|
| 108 | `knowledge/sources/local/terms.yaml` |
| 22 | `knowledge/sources/local/entities.yaml` |
| 2 | `knowledge/sources/project_specific/entities.yaml` |

All three are source-file paths, matching the frozen literal oracle's stated
semantics. None is an idea origin, so the ruling that `promoted_from` is not
migratable into `origins` holds against the actual values, not just in
principle.

### 2. Template output

[`templates/concept.md`](../../templates/concept.md) prescribes, via its
`_template.frontmatter` block: `id`, `kind`, `title`, `status`, `related`,
`source_refs`, `created`, `updated`.

**The template also prescribes a ninth field in prose that its own
`frontmatter` block omits.** The `## Notes` comment instructs the author to
"author ontology CURIEs via `ontology_terms:` for a `sci:about` bridge edge."
This is exactly the case the procedure's candidate-universe rule exists for: a
field a template prescribes but never emits. The corpus bears it out in the
strangest possible way — 37 records carry `ontology_terms`, and **all 37 are
empty lists**. The instruction is followed structurally and never populated.

`ontology_terms` is base-admitted, so closure does not threaten those 37
records. It is recorded here because a reader of the frontmatter block alone
would conclude the field is not part of the kind's contract.

### 3. Writer-emitted records

The toolkit has **no writer that emits a `concept` record.** A tree sweep for
`promoted_from` outside tests returns three hits:
`graph/decision_log.py:136` and `:157` (`render_owner_file`, which writes
`type: decision` — a different kind), and a comment at
`migrate_hypothesis.py:78`.

So the 132 `promoted_from` values on concepts were written outside this
toolkit. This is a disposition input, not a defect: the mixin must admit the
field because the corpus carries it, but no toolkit surface prescribes its
shape for this kind, which is why the frozen literal oracle — not a
toolkit writer — is the authority the gate compares against.

### 4. Keyed consumer reads

| surface | reads | applies to `concept`? |
|---|---|---|
| `health_checks/identity_policy.py:207` | `canonical_id` local-id syntax (lowercase kebab-case) | **yes**, explicitly named |
| `health_checks/identity_policy.py:187` | `primary_external_id` | no — `_IDENTITY_REQUIRED_KINDS` is gene/protein/disease/drug/chemical/cell_type/phenotype/anatomy/pathway/process/function |
| `health_checks/identity_policy.py:197` | `taxon` | no — `_TAXON_REQUIRED_KINDS` is `{gene, protein}` |
| `graph/store/constants.py:127`, `refs.py:91`, `references.py:205`, `validate/checks/id_prefixes.py:31`, `validate/checks/cross_references.py:17,211` | the `concept:` id prefix | prefix membership only; no field reads |

No consumer reads a `concept` field that the corpus does not carry.

### 5. Pydantic projection

**`concept` has no typed subclass.** `CORE_KIND_MODELS` has no entry for it, so
`EntityRegistry.with_core_types()` registers it against the generic
`ProjectEntity` (`entity_registry.py:135`) — 70 fields, `extra="allow"`, the
union of everything any untyped kind might carry (`dataset_class='deposit'`,
`datapackage`, `accessions`, `taxon`, `benchmark`, `pre_registered`, …).

This is not incidental to `concept`. **30 of the 50 core kinds are untyped**,
including four of the five tranche kinds:

| kind | projection |
|---|---|
| `concept` | `ProjectEntity` (generic) |
| `search` | `ProjectEntity` (generic) |
| `finding` | `ProjectEntity` (generic) |
| `observation` | `ProjectEntity` (generic) |
| `method` | `MethodEntity` (typed) |

`hypothesis` — the only closed kind, and the sole precedent the mechanism was
proved against — is typed. See "Open question" below.

Two projection facts that bear directly on the mixin:

- **`promoted_from` is not a declared field on `ProjectEntity`.** Verified: it
  survives `model_validate` only as a pydantic *extra*, landing in
  `model_extra` and in `model_dump()`. Closure does not break it, and the
  contract still holds — the schema is what vouches for its shape
  (`{"type": "string", "minLength": 1}`), the projection only preserves what
  the schema admitted. But the preservation is by `extra="allow"`, not by
  declaration.
- **`ProjectEntity.profile` defaults to `'core'`**, a value **no** concept
  record carries. The corpus uses `local` (177) and `project_specific` (2).
  Any probe asserting a loaded concept has `profile == 'core'` would be
  passing on the default, not on authored data.

### 6. Base schema fields

`science-entity-base-2.0.json` declares 16 properties and requires
`id, kind, title, created, updated`.

| base property | concept records carrying it |
|---|---|
| `id`, `kind`, `title`, `created`, `updated` | 329 |
| `status` | 329 |
| `ontology_terms` | 37 (all empty) |
| `contributors`, `dataset_usage`, `description`, `licenses`, `same_as`, `schema_profile`, `sources`, `tags`, `version` | **0** |

The four observed non-base fields are `profile`, `promoted_from`, `related`,
`source_refs` — reproducing the design's "4 non-base fields" exactly.

### 7. Retired / tombstoned fields

None found for `concept`. No superseded field name appears in the corpus, in
the template, or in a migration path. `supersedable=False` on the descriptor
(`profiles/core.py:427`), and every record is `status: active`.

## Dispositions

Base-admitted fields stay admitted through the composed `allOf` unless the
mixin narrows them with an explicit `false`. Omission is refusal only for
fields base does not admit — so this table is not a deny list.

| field | disposition | rationale |
|---|---|---|
| `id` | required | 329/329; base-required |
| `kind` | required, `{"const": "concept"}` | gate 2 requires every armed mixin to pin its own kind |
| `title` | required | 329/329; base-required |
| `created`, `updated` | required | 329/329; base-required |
| `status` | admit, `enum: ["active", "deprecated"]` | the descriptor declares both (`profiles/core.py:426`); the corpus is 329/329 `active`. The enum comes from the **descriptor**, not the corpus — a corpus that never exercised `deprecated` cannot prove it invalid |
| `profile` | admit, `{"type": "string"}` | 179 records. Authored and honoured, same rationale as `mixin-hypothesis-2.0` records |
| `promoted_from` | admit, frozen literal oracle | 132 records; per-kind core field per the ownership ruling. Shape copied verbatim from `~/d/protein-landscape/schemas/extension-protein-landscape-promotion-1.0.json` |
| `related` | admit, `{"type": "array", "items": {"type": "string"}}` | 42 records, 61 items, all `str` |
| `source_refs` | admit, `{"type": "array", "items": {"type": "string"}}` | 37 records, 5 items, all `str` |
| `ontology_terms` | inherit from base | 37 records; template prescribes it in prose |
| `schema_profile` | **narrow to `false`** — proposed, see below | `mixin-hypothesis-2.0` narrows it away; 0 concept records carry it |
| `contributors`, `dataset_usage`, `description`, `licenses`, `same_as`, `sources`, `tags`, `version` | inherit from base | 0 occurrences, but base admits them and nothing justifies narrowing a kind-agnostic base field for this kind specifically |

### Proposed ruling: `schema_profile: false`

`mixin-hypothesis-2.0.json` sets `schema_profile: false` — the reserved
explicit-`false` case, a base-admitted field the kind deliberately narrows
away. `profile` is the authored field; `schema_profile` is its serialized
counterpart, and authoring it directly is what the narrowing refuses.

The same reasoning applies to `concept` unchanged, and no concept record
carries it. Proposed: narrow it, matching hypothesis.

This is the one disposition in the table decided by precedent rather than
by measurement, so it is called out rather than folded in silently.

## Open question — blocks step 5, not step 2

Step 5 ("Reconcile the contracts") says: *compare schema fields with the
Pydantic projection and with every explicit reader or omit decision;
unexplained fields on either side block the slice.*

That step was written against `hypothesis`, whose projection is a
kind-specific `HypothesisEntity`. For `concept` the projection is the generic
70-field `ProjectEntity` shared with 29 other untyped kinds, so a literal
reading makes ~59 fields "unexplained on the projection side" — and the
explanation for every one of them is the same sentence: *`ProjectEntity` is not
concept's model.*

The asymmetry appears to be the resolution rather than a problem:

- **schema admits X, projection drops X** → a real defect. The schema vouched
  for something the projection silently discarded. This direction must be
  checked, and for `concept` it passes: every proposed admitted field either is
  declared on `ProjectEntity` or survives via `extra="allow"` (verified above
  for `promoted_from`).
- **projection declares Y, schema never admits Y** → not a defect. `Y` is
  unreachable for this kind. `taxon` on a concept is dead weight in a shared
  model, not an unvouched field.

If that reading is right, step 5 for an untyped kind is the first direction
only, and the procedure's wording should say so — otherwise the next four
slices each re-derive it, and one of them will get it wrong in the direction
that matters. Recording it here rather than assuming it.

## Production-surface alignment (step 3)

Step 3 required **no production edit**: every surface already emits a subset of the
frozen field set. That is a measurement, not an assumption, and each item below is
now asserted by a guard so a later edit cannot silently undo it.

| surface | state | guard |
|---|---|---|
| packaged `science_model/templates/concept.md` | renders 8 keys, all admitted | `test_the_rendered_template_validates_under_the_candidate`, `test_the_template_emits_no_field_outside_the_frozen_set` |
| repo-root `templates/concept.md` | byte-identical copy; renders nothing | pre-existing `test_root_and_packaged_migrated_templates_match` |
| structured sources | none exist for this kind | the zero-row sweep above |
| writers | none emit a concept record | the `promoted_from` sweep above |
| readers | no undeclared-field reads | the consumer-read table above |
| `_enrich_raw` profile defaulting | runs **after** validation | `build` validates, then enriches, then projects |
| project extensions | **no project declares one for `concept`** | measured across all 39 `science.yaml` roots |

Two facts worth stating separately, because both were assumptions until measured.

**The packaged template is the one that renders.** `entities.py:796` imports
`Renderer` from `science_model.templates`; the repo-root copy is a second file with
its own inode. They are byte-identical today only because an existing parity guard
holds them so. A step-3 edit to the root copy alone would have changed nothing.

**`profile` is loader-defaulted, but only after validation.** `sources.py:1043`
fills it inside `_enrich_raw`, which `build` runs *after* the schema check, so the
schema sees the 179 authored values and never the 150 defaulted ones. The mixin
therefore admits `profile` without requiring it.

### Project distribution, and what step 7 must do about it

Exactly three of the 39 `science.yaml` roots carry concepts:

| project | records | `entity_schema_version` |
|---|---|---|
| `~/d/cancer/cancer-types/multiple-myeloma` | 285 | 3 |
| `~/d/health/processes/post-acute-infection` | 37 | 3 |
| `~/d/natural-systems` | 7 | 2 |

**`concept` must be added to BOTH generation rows at `1.0`.** natural-systems is on
generation 2; arming only generation 3 would leave its 7 records outside the closed
profile while mm30's 285 were inside — a split contract across one kind, which is
exactly what a generation row exists to prevent. The two rows carrying the same
version also keeps `sources.py:1704` honest: it calls
`default_profile_for_kind(entity.kind)` with **no** generation argument, so it always
resolves the generation-2 row regardless of what the project declared.

That call is also a step-6 item. It sits in a `try/except ProfileParseError` whose
comment is explicit that the except branch is not a fallback. `concept` takes that
branch today; once it appears in a generation row it will resolve, and a merge policy
will be registered where none was before. That is intended, and it is a derived
behaviour change that step 6's diff must show rather than discover.

## Certification (step 4)

**All 329 authored records satisfy the candidate profile with
`unevaluatedProperties: false` armed.** Certified at the markdown adapter's authored
boundary (`raw` minus `MarkdownAdapter.INJECTED_KEYS = {content, file_path,
canonical_id}`), not at raw frontmatter, because the boundary is what `build` hands
the schema. No record authors any of those three keys, so the subtraction is a no-op
for this kind — asserted, not assumed, so the Markdown blind spot cannot be exercised
here unnoticed.

The full load path was verified by hand, with `concept` **temporarily armed for
real** — `schema_closed=True` plus both generation rows — rather than monkeypatched.
Six modules bind `PROJECT_MIXIN_NAMES` by value at import time
(`graph/entity_schema_validation.py`, `entities.py`, `graph/sources.py`,
`datasets/capability_migration.py`, `entity_schema/validator.py`, and `loader.py` for
`TYPE_MIXIN_NAMES`), so a patch-based simulation that missed one would certify
nothing while looking green.

| project | before | after |
|---|---|---|
| mm30 | 4028 entities, 285 concepts | 4028 entities, 285 concepts |
| natural-systems | 4160 entities, 7 concepts | 4160 entities, 7 concepts |

Byte-identical, and a virtual record carrying an undeclared key was refused through
the real adapter with a path-anchored error. The arming was then reverted and the
branch re-verified inert.

### The certification gap, stated rather than smoothed over

`~/d/health/processes/post-acute-infection` **cannot be loaded at all**:

```text
ValueError: tasks/active.md predates the storage split;
run `science tasks migrate-storage --apply`.
```

This reproduces on `main`, is unrelated to schema closure, and pre-dates this branch —
the project has a `tasks/active.md` file where migrated projects have a `tasks/active/`
directory. Its 37 concepts are therefore certified at the schema boundary only, not
through the adapter. That is 11% of the corpus, and the gap closes when that project
is migrated. It is recorded here rather than skipped past, because "the two projects
that load, load fine" is not the same claim as "the corpus certifies".

### Behaviour change to carry into step 6's allowlist

A closure violation is a **hard load failure**, not a degradable one.
`sources.py:603` raises `validation.error` for a `PROJECT_SCHEMA` rejection
unconditionally — `strict_core_schema=False`, the mode documented to record a
`SkippedEntity` so one bad entity cannot take a report offline, applies to the
`ENTITY_SCHEMA` (Pydantic projection) rejection only.

Verified this is the **established contract, not a new consequence**: an armed
`hypothesis` record carrying an undeclared key raises identically today. `concept`
joins an existing ruling rather than introducing a failure mode. It belongs on the
allowlist all the same, because after step 7 a single malformed concept record takes
`science health` down for the whole project where today it would not.

## What this slice does not close

Per the procedure's debt section, and confirmed against the tree:

- `hypothesis`'s own realignment to the `promoted_from` ruling.
  `mixin-hypothesis-2.0.json` does **not** declare `promoted_from`; that needs
  a versioned mixin bump and is not this slice's work.
- The Markdown adapter's authored-`content` blind spot. No concept record
  carries `content`, so this slice neither exercises nor closes it.
- The six unclosed core kinds carrying `promoted_from` outside the tranche.

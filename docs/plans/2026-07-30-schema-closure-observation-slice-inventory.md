# Schema-Closure Slice 4 — `observation`: Field-Surface Inventory (Step 1)

Fourth slice of the per-kind schema-closure tranche, following `concept` (2026-07-28),
`method` (2026-07-29) and `search` (2026-07-30). Procedure:
[`../conventions/schema-closure-slice-procedure.md`](../conventions/schema-closure-slice-procedure.md).

This document freezes the candidate universe and the disposition of every field before
any mixin is written. It is step 1 and nothing here is armed.

## What makes this slice different

| | `concept` | `method` | `search` | `observation` |
|---|---|---|---|---|
| records | 329 | 51 | 36 | **21** |
| project roots | 3 | 4 | 7 | **1** |
| typed subclass | no | `MethodEntity` | no | **no** — `ProjectEntity` |
| packaged template | yes | yes | none | **yes** |
| YAML source rows | yes | yes | none | **none — markdown only** |
| `status` values in corpus | all `active` | 4 + `proposed` | all `active` | **all `active`** |
| `supersedable` | no | **yes** | no | **no** |
| consolidatable | no | yes | yes | **yes** |

The corpus is the smallest and most uniform of the tranche: **one project root owns every
record.** That is the `status`-uniformity trap in its strongest form — no probe over this
corpus can distinguish a correct field set from an over-tight one, so almost nothing below
is decided by measuring the corpus.

Accordingly this slice's substantive finding did not come from the corpus at all. It came
from the **writer** surface, and it is a defect in already-shipped slices. See
"RULING (decided): `consolidated_into`".

## Corpus measurement

21 markdown records, **0** YAML source rows, measured 2026-07-30 across all 17 project
roots in the 4 repos:

| project root | records |
|---|---|
| `~/d/health/processes/cycles` | 21 |
| every other root | 0 |

Field occurrence over those 21:

| field | count | base 2.0? | note |
|---|---|---|---|
| `id`, `kind`, `title`, `status`, `created`, `updated` | 21 (all) | yes | the base-required set + `status` |
| `related` | 21 (all) | no | **mixin must admit** |
| `source_refs` | 21 (all) | no | **mixin must admit** |
| `promoted_from` | 14 | no | **mixin must admit** — see below |

There is no ninth field. `status` is `active` in all 21; per the standing ruling that
uniformity is not evidence.

Shapes verified rather than assumed: all 21 ids match `^observation:[a-z0-9][a-z0-9-]*$`
(the descriptor's `strategy="slug"`), `related`/`source_refs` are string lists in every
record, and `created`/`updated` are **quoted** strings in every record. That last one
confirms the procedure's F3 claim for this kind by measurement: `observation` inherits no
share of the unquoted-YAML-date defect.

## Candidate universe

The union of surfaces, not the observed corpus:

1. **Authored formats** — markdown frontmatter only. No `observation` row exists in any
   project's `knowledge/sources/**.yaml`, so there is no source migration here.
2. **Template output** — `templates/observation.md`, byte-identical to the packaged
   `science/model/src/science_model/templates/observation.md` (checked, not assumed — the
   pre-registration precedent is that the packaged shadow is what renders). It prescribes
   exactly `id, kind, title, status, related, source_refs, created, updated` and has **no
   `{ omit: true }` entries**, so the `method` slice's zero-occurrence template lesson
   finds nothing here. Note the template does **not** prescribe `promoted_from`, which 14
   records nonetheless carry.
3. **Writer-emitted records** — three, and this is where the slice's finding lives:
   - `entity_import.py:221` writes `kind, title, status, created, updated, id`. All within
     the frozen set.
   - `consolidate.py:183` writes `consolidated_into` (plus `status: archived`). **Ruled
     on below.**
   - `consolidation.py` `mark_superseded` writes `superseded_by` — but only for
     `supersedable` kinds, and `observation` is `supersedable=False`. Not admitted.
   - `decision_log.py:157` also writes `promoted_from`, but only onto `type: decision`
     records. It is **not** the writer of this kind's `promoted_from`; see below.
4. **Keyed consumer reads** — none observation-specific. Note the name collision:
   almost every `observation` hit in `science/src` is `CheckObservation` /
   `ValidationMetricObservation` / `validate/observations.py`, which have nothing to do
   with the entity kind. The genuine hits (`refs.py:105`, `labnote_export.py:85`,
   `numeric_provenance.py:498`, `cross_references.py`, `graph/store/constants.py:126`) are
   all kind-membership lists, not field reads.
5. **Pydantic projection** — `ProjectEntity` (70 fields). There is no `ObservationEntity`;
   `CORE_KIND_MODELS` (`graph/entity_registry.py:87`) has no `observation` entry, so step 5
   is the untyped variant.
6. **Base 2.0** — admits `contributors`, `created`, `dataset_usage`, `description`, `id`,
   `kind`, `licenses`, `ontology_terms`, `same_as`, `schema_profile`, `sources`, `status`,
   `tags`, `title`, `updated`, `version`. Requires `id`, `kind`, `title`, `created`,
   `updated`.
7. **Loader-injected keys** — exactly `{canonical_id, content, file_path}`. **Measured, not
   read off a constant**: see the `profile` correction below.
8. **Retired/tombstoned fields** — the 14 promoted records came out of a retired aggregate,
   `doc/observations/observations.yaml`, whose rows carried `id`, `title`, `description`,
   `related`, `source_refs`. The promotion put `description` in the **body**, not in
   frontmatter, so no record carries it. `description` is base-admitted anyway, so it needs
   no mixin entry either way.

### `promoted_from` — admit

All 14 occurrences carry the identical value `doc/observations/observations.yaml`. Per the
procedure's ownership ruling, `promoted_from` is a per-kind core field and each admitting
mixin declares the frozen literal oracle inline. `observation` is one of the four tranche
kinds the procedure lists as carrying it.

Two things worth recording because both are counter-intuitive:

- **The path does not exist.** `~/d/health/processes/cycles` commit `433ad02`
  ("retire observations.yaml to owner files") deleted it in the same commit that created
  the 14 owner files. This is *correct* provenance, not a dangling reference:
  `promoted_from` names where the entity came from, and it came from a file that was
  deliberately retired. The frozen oracle is `{"type": "string", "minLength": 1}` — there
  is no existence check and there should not be one.
- **The writer is gone.** That commit used
  `science entities triage-aggregate --promote-coined --apply`. No such command exists in
  the toolkit today (`science entities` now offers `archive`, `audit-identifiers`,
  `consolidate`, `generate-decisions`, `import`, `inventory`, `mark-superseded`,
  `register-kind`, `unarchive`). So `promoted_from` on this kind has **no live writer** and
  is authored only historically. That is a reason to admit it — the records exist and must
  keep loading — not a reason to think the field is live.

### `profile` — OMIT, and a correction to the `search` slice

`observation` does not admit `profile`. Three independent grounds:

- **Zero of 21 records author it.**
- **Zero of the 539 entity records in `health/cycles` author it** — across all 19 kinds
  present in that project. The one project that owns this entire corpus does not use entity
  profiles at all.
- **It is not injected.** This is the correction.

> **⚠️ Correction to
> [`2026-07-30-schema-closure-search-slice-inventory.md`](2026-07-30-schema-closure-search-slice-inventory.md).**
> That document admitted `profile` on `search` at zero occurrences, on the stated ground
> that "the loader injects it — `sources.py:1041` writes `raw["profile"]` whenever the
> author did not, so the key reaches the composed schema regardless." **The key does not
> reach the composed schema.** Two reasons, both verified by instrumenting the real load
> path rather than by reading the source:
>
> 1. The `setdefault("profile", …)` call is on the **structured-row** path
>    (`sources.py:1268`), not the markdown path. `search` and `observation` are
>    markdown-only.
> 2. Enrichment runs **after** validation regardless. `entity_registry.build` calls
>    `validate_against_schema(raw, …)` and only then `enrich(raw)`, so nothing enrichment
>    adds can face the schema.
>
> Instrumenting `validate_against_schema` on a real gen-3 project load of a `search`
> record authored without `profile` gives the validated key set exactly:
>
> ```
> keys reaching validate_against_schema: [canonical_id, content, created, file_path,
>                                         id, kind, related, source_refs, status, title, updated]
> injected (subtracted):                 [canonical_id, content, file_path]
> -> validated key set:                  [created, id, kind, related, source_refs, status, title, updated]
> ```
>
> No `profile`. The slice-3 admission is **harmless but unjustified** — it admits a key no
> `search` record authors — and tightening it would need a version bump to remove a field,
> which is not this slice's business. What must not survive is the *rationale*, because the
> next slice would copy it. `mixin-concept-1.1` admits `profile` legitimately for a
> different reason the search doc also gave: 179 of 329 concepts genuinely **author** it.
>
> The generalizable lesson is the one this arc keeps relearning in new costume: slice 3
> reasoned from a `setdefault` it read to a validated key set it did not measure. Verify
> what reaches the schema by watching the schema, not by reading the loader.

## The `status` ruling — no enum

The descriptor (`profiles/core.py:139-152`) declares `["active", "retired", "archived"]`.
The mixin declares `{"type": "string"}` with **no enum**, per the standing ruling:
`observation` is not in `_CERTIFIED_KINDS` (`validate/kind_severity.py:24` is
`frozenset({"hypothesis"})`), and a schema enum refuses at load with no warning stage —
harder than the validate ERROR the doctrine already forbids for an uncertified kind.

All 21 records are `active`, which is the uniform-corpus condition that let
`mixin-concept-1.0`'s premature enum survive its own certification. The corpus is not
consulted for this field.

`status` **is** required by the mixin, as it is for all four shipped tranche mixins. That is
grounded here rather than copied: the packaged template prescribes `status`, so a record
without one is a record the toolkit never produces.

## `schema_profile: false`

Not a copied pattern — a rule stated by base 2.0 itself, in the `$comment` on its own
`schema_profile` property: *"Optional here, and DERIVED for project kinds
(`default_profile_for_kind`). It stays declared because commons records … legitimately
author it. A project kind's mixin sets this to `false`."* `observation` is a project kind.

## RULING (decided): `consolidated_into` — omit, and fix the writer

**Decision: option B.** `consolidated_into` is omitted from the mixin, and
`unarchive_entities` is changed to strip archive-tier bookkeeping keys on restore so the key
cannot reach a schema-validated path. This is the slice's substantive finding, and it is a
defect in **already-shipped** slices, not in this one.

### The reachable path

`consolidate.py:183` writes `fm["consolidated_into"] = digest_id` onto each *member's*
frontmatter, then relocates the file to `entities/_archive/`. That is safe on its own:
`entity_scan.iter_entity_markdown` skips `_`-prefixed segments, so archived files are never
loaded, and `--include-archived` reads the **archive index**, not the files.

`unarchive_entities` (`archive.py:290`) is a bare `shutil.move`. It does not touch
frontmatter. So consolidate-then-unarchive restores a file to its **live, scanned,
schema-validated** path with `consolidated_into` still in it.

Verified end-to-end against armed `search` in a gen-3 project — not argued from the source:

```
AFTER UNARCHIVE -> LOAD FAILED: ValueError
entities/searches/0001-a.md: search frontmatter does not satisfy its schema
  (project is pinned to entity_schema_version: 3)
  entity failed schema validation: <root>: Unevaluated properties are not allowed
  ('consolidated_into' was unexpected)
```

That is a **whole-project load failure**, not a single-record rejection.

### Blast radius, measured

`_is_consolidatable` (`consolidate.py:44`) admits a kind whose status vocabulary is open or
contains `archived`:

| kind | consolidatable | mixin admits `consolidated_into` | reachable? |
|---|---|---|---|
| `hypothesis` | yes | no | **yes** |
| `method` | yes | no | **yes** |
| `search` | yes | no | **yes** |
| `concept` | **no** — vocab is `["active","deprecated"]` | no | no |
| `observation` | yes | this slice | — |
| `finding` | yes | unarmed | — |

`concept`'s immunity is accidental. It is not protected by its mixin; it is protected by a
status vocabulary that happens to omit `archived`, which makes `_validate_members` refuse it
upstream. Nothing about that was designed.

### Why B rather than admitting the field

The frontmatter copy has **no semantic reader**. Both consumers read the archive index:
`entities.py:1004` (`row.consolidated_into`) and `big_picture/digests.py:77` (`digest =
row.consolidated_into`). The only frontmatter-side mention is
`_REMOVABLE_FRONTMATTER_REF_KEYS` (`entities.py:1385`), a scrubber, not a consumer. So the
frontmatter key is duplicated bookkeeping whose authority already lives elsewhere, and
admitting it in four mixins would enshrine that duplication in versioned schemas.

Rejected alternatives:

| | Effect | Cost |
|---|---|---|
| **A. Admit in every consolidatable kind's mixin** | Honest to what the writer does today | Three version bumps (`search` 1.1, `method` 1.1, `hypothesis` 2.1) and archive-tier bookkeeping permanently in the live-record schema |
| **B. Omit; strip on unarchive** | One authority (the index); no shipped mixin changes | Slice 4 grows by one writer fix and its tests |
| **C. Omit; file as debt** | Slice 4 stays a pure closure slice | Knowingly leaves three armed kinds with a project-breaking path |

**Chosen: B.**

### The sibling defect this exposes: `superseded_by` on `method`

The same class, found the same way, but it resolves the other direction and is **not** this
slice's to fix.

`mark_superseded` writes `superseded_by` into the frontmatter of superseded members, and
`consolidation.py:147` states that frontmatter "is … the only place an authored
`superseded_by` can live" — so unlike `consolidated_into`, this one genuinely belongs in the
schema of any kind that can be superseded.

`mixin-hypothesis-2.0` admits it. `mixin-method-1.0` does **not**, and `method` is
`supersedable=True`, so `mark_superseded` can stamp a record its own mixin then refuses
(verified: `Unevaluated properties are not allowed ('superseded_by' was unexpected)`).
`search` and `concept` are `supersedable=False`, so their refusal is correct — there the
schema is enforcing the descriptor's policy.

`observation` is `supersedable=False`, so **this mixin omits `superseded_by`** and the
omission is load-bearing policy, not an oversight.

`method` needs a `mixin-method-1.1` bump. It is a different kind, so by the procedure's
one-kind-one-branch rule it is a separate branch. Filed as **F7**.

### What this says about the procedure

The candidate universe already lists "template output and every writer-emitted record". The
first three slices applied the template half and under-applied the writer half, because a
kind's *own* corpus and template never show what a kind-agnostic mutator writes. `hypothesis`
escaped only because `HypothesisEntity` declares `superseded_by` and
`resynthesized_into` as typed fields, so its mixin inherited the coverage from the model
rather than from an inventory of writers.

The step-1 question to add is: **which kind-agnostic mutators can write to this kind's
frontmatter, and what do they write?** Answering it requires enumerating the mutators, then
checking each against the kind's descriptor flags (`supersedable`, and whether the status
vocabulary contains `archived`) — not scanning the corpus, which by construction cannot
contain a key that would have refused it.

## Field dispositions (frozen)

| field | disposition | ground |
|---|---|---|
| `id` | admit, `pattern: ^observation:` | prefix-only, per the `mixin-hypothesis-2.0` ruling; all 21 ids also satisfy the slug shape but that is not pinned here |
| `kind` | admit, `const: observation` | |
| `status` | admit, `{"type": "string"}`, **no enum**, required | uncertified kind; template prescribes it |
| `related` | admit, `array` of `string` | 21/21 |
| `source_refs` | admit, `array` of `string` | 21/21 |
| `promoted_from` | admit, frozen literal oracle | 14/21; procedure's ownership ruling |
| `schema_profile` | `false` | base 2.0's own stated rule for project kinds |
| `profile` | **omit** | 0/21 authored, 0/539 project-wide, and not injected (measured) |
| `consolidated_into` | **omit** | writer defect; fixed in step 3 per ruling B |
| `superseded_by` | **omit** | `supersedable=False` — the omission enforces the descriptor |
| everything base 2.0 admits | no mixin entry | `title`, `created`, `updated`, `description`, `tags`, … |

Required: `["id", "kind", "status"]`.

## Known cost at step 7

`test_graph_freshness_integration.py` authors two `observation` fixtures (lines 190 and
474) with **no `status`** — legal only while the kind is open. Arming will break both. This
is the `method` slice's fixture lesson arriving on schedule, and it is found here at step 1
rather than at step 7 because the lesson was written down. An exhaustive scan of
`science/tests` and `science/model/tests` finds exactly these two sites.

## What this slice does not close

- **F7** (`mixin-method-1.1` for `superseded_by`) is filed, not fixed — different kind,
  different branch.
- The `search` mixin keeps its unjustified `profile` admission; only the rationale is
  corrected. Removing a field needs a version bump on its own grounds.
- F1 (the Markdown authored-vs-injected-key blind spot) still weakens step 4 here, exactly
  as it did for `concept`, `method` and `search`. Note that this slice's `profile`
  measurement was possible *despite* F1 because it instrumented the validator directly
  rather than the adapter.
- `concept`'s accidental immunity to the consolidate path is left as-is. Under ruling B the
  writer no longer produces the key on a live path for any kind, so the accident stops
  mattering.

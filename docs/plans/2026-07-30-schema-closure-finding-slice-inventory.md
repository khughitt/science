# Schema-Closure Slice 5 — `finding`: Frozen Field-Surface Inventory

Step 1 of [the seven-step slice procedure](../conventions/schema-closure-slice-procedure.md).
`finding` is the fifth and last tranche kind. It is the **only** slice that carries a
*source* migration, and — measured here, not predicted — the only tranche kind whose
records reach the schema by two structurally different paths.

## Corpus Measurement

Counted over authored records, per **project root** (the unit that owns a `science.yaml`),
not per repo. 18 roots scanned; 15 hold no `finding` at all and are enumerated in the
certification test rather than implied.

| surface | records | where |
|---|---|---|
| markdown frontmatter | **52** | `~/d/protein-landscape` 26, `~/d/natural-systems` 23, `~/d/cancer/cancer-types/multiple-myeloma` 3 |
| structured source rows | **149** | `~/d/natural-systems/knowledge/sources/project_specific/finding.yaml` |
| **total** | **201** | 3 project roots |

Corrections to the scoping estimate in the procedure doc (which said 53 markdown,
"protein-landscape 26, natural-systems 24, cancer 3"): protein-landscape and cancer are
exact; natural-systems is **23**, not 24. The estimate was a `kind:` grep; this is a
frontmatter parse.

### Every finding-bearing project declares a generation

| root | `entity_schema_version` | `entity_extensions` |
|---|---|---|
| `~/d/cancer/cancer-types/multiple-myeloma` | 3 | `hypothesis: [mm30.assessment/1.0]` |
| `~/d/natural-systems` | 2 | **none declared** |
| `~/d/protein-landscape` | 3 | `hypothesis: [protein-landscape.promotion/1.0]` |

Two consequences, both load-bearing:

- **All three are exposed.** Slice 4's refinement — "a fixture is exposed only if its
  project declares a generation" — cuts the other way here. There is no unvalidated
  project holding findings.
- **No project extension covers `finding`.** Both declared extensions are
  `hypothesis`-scoped. So every field in the corpus must be admitted by the core
  `mixin-finding-1.0` or by base 2.0; there is no project-side escape hatch, unlike the
  `method` slice where the mixin could lean on nothing and still had 20 roots to satisfy.

## `finding` Reaches the Schema by TWO Paths

This is the structural fact that makes slice 5 unlike its four predecessors.
`~/d/natural-systems/knowledge/sources/project_specific/manifest.yaml` declares:

```yaml
core_structured_sources:
  - kind: finding
    structured_source: finding.yaml
```

`finding` is the **only core kind anywhere in the tree routed through the structured-source
loader**. `morphism-edge` and `limit-relation` also take that path but are project-local
kinds no slice will close. So arming `finding` arms the structured path for the first time.

Measured by instrumenting `validate_against_schema` on a real `load_project_sources` of
`~/d/natural-systems` (gen 2) — not inferred from reading the loader:

| | markdown (23 records) | structured (149 rows) |
|---|---|---|
| declared `injected` | `{canonical_id, content, file_path}` | `{canonical_id, type}` |
| authored keys facing the schema | 13 | 12 |
| authors `status` | 23 / 23 | **0 / 149** |
| authors `updated` | 23 / 23 | **0 / 149** |

The two paths disagree about `file_path`: it is *declared injected* on markdown and
*faces the schema as authored* on structured rows, in one load of one project. That is not
a bug. `_STRUCTURED_INJECTED_KEYS` is `{canonical_id, type, file_path, evidence_refs}` and
the call site subtracts what the author actually wrote (`sources.py:1300`,
`injected=_STRUCTURED_INJECTED_KEYS - authored`). The 149 rows author `source_path`, which
`normalize_structured_row` renames to `file_path` — so it is genuinely authored content
under a normalized name, and hiding it would be the fail-silent the subtraction exists to
prevent. **`file_path` must therefore be admitted by the mixin.**

### F1 is closed — the procedure doc is stale

The procedure's follow-up table lists F1 ("Markdown adapter cannot separate authored from
injected keys") as open and as the "highest-value follow-up", weakening every slice's
step-4 certification. It is **closed in the tree**: `EntityRegistry.build` takes a
required `injected` frozenset, four call sites each pass their own contribution, and
`entity_registry.py:255-291` documents why there is no safe default. Slice 6 of anything
should not re-file it. Corrected in the procedure doc by this slice.

## Candidate Universe and Dispositions

The union of: markdown frontmatter, structured source rows, `templates/finding.md`,
base 2.0 properties, keyed consumer reads, and kind-agnostic mutators. Counts are
`markdown / structured`.

### Admitted by `mixin-finding-1.0`

| field | count | why it is admitted |
|---|---|---|
| `id` | 52 / 149 | base-required; mixin adds the `^finding:` prefix pattern |
| `kind` | 52 / 149 | `const: finding` |
| `status` | 52 / **0** | **ruling below**; `{"type": "string"}`, NO enum |
| `profile` | 26 / 149 | authored on both paths |
| `file_path` | 0 / 149 | authored as `source_path`, normalized; see above |
| `related` | 44 / 149 | authored on markdown; backfilled `[]` on structured |
| `source_refs` | 26 / 149 | same |
| `aliases` | 26 / 149 | authored on 26 protein-landscape records; backfilled `[]` on structured |
| `evidence_refs` | 0 / 149 | authored on every structured row |
| `propositions` | 25 / 0 | template-prescribed |
| `observations` | 25 / 0 | template-prescribed |
| `mode` | 23 / 0 | natural-systems; values `empirical-measurement` (19), `confirmatory` (2), `structural-audit`, `literature-synthesis` |
| `input` | 22 / 0 | natural-systems; a declared provenance field (`project_config.py:101` `DEFAULT_PROVENANCE_FIELDS`) |
| `relations` | 3 / 0 | the `sci:amends` amendment chain; reuses `$defs/authored_relation` verbatim — see the `note` ruling |
| `promoted_from` | 26 / 0 | the per-kind ownership ruling; shape copied from the frozen literal oracle |
| `superseded_by` | **0 / 0** | zero-occurrence and load-bearing — see the mutator section |
| `schema_profile` | — | `false`, as every mixin declares |

Supplied by **base 2.0**, so the mixin declares none of them: `title`, `created`,
`updated`, `description`, `ontology_terms`, `tags`, `same_as`, `version`, `contributors`,
`licenses`, `sources`, `dataset_usage`.

### Refused by omission

`consolidated_into` — see the mutator section. No other tombstoned or retired `finding`
field exists: the 52 markdown records carry exactly 17 distinct keys between them and the
migration modules define no `finding` retirement.

## Kind-Agnostic Mutators — Slice 4's Question, Asked Again

The descriptor (`profiles/core.py:155`) makes `finding` the first tranche kind exposed to
**both** mutator vectors at once:

```
statuses    = ["active", "superseded", "retired", "archived"]   -> consolidate reachable
supersedable = True                                              -> mark_superseded reachable
```

**`superseded_by` — ADMIT.** `consolidation.py:147` rules frontmatter is "the only place
an authored `superseded_by` can live", and `mark_superseded` stamps it. `finding` is
`supersedable=True`, so the writer can produce a record its own mixin would refuse. This
is exactly the shipped defect filed as **F7** against `mixin-method-1.0` — caught here
*before* arming rather than after. Zero records author it today; that is precisely why the
first three slices' corpus-driven method would have missed it.

**`consolidated_into` — OMIT, and the writer is already fixed.** `finding`'s statuses
include `archived`, so `consolidate.py:48` admits it and `apply_consolidation` stamps
`consolidated_into` onto a member's frontmatter. Slice 4 ruled the frontmatter copy a
writer defect (the archive *index* holds the authority) and made `unarchive` strip it via
`ARCHIVE_TIER_FRONTMATTER_KEYS` (`archive.py:292`). `finding` inherits that fix rather
than needing a mixin entry. Step 3 owes a test that the strip actually covers this kind —
inheritance is a claim about code, and this slice checks it.

## RULING: `status` on the 149 Structured Rows

The procedure anticipated one migration for this slice (`updated = created`). Measurement
found a second gap it did not: the 149 rows author **no `status`** either. Base 2.0 does
not require `status`; all four already-armed project mixins do.

**Ruling: require it, and backfill.** `mixin-finding-1.0` declares
`required: [id, kind, status]`, consistent with `hypothesis`, `concept`, `method`,
`search` and `observation`. The source migration covers two fields in one edit.

Rejected alternatives, by name:

| Alternative | Ruling |
|---|---|
| Require `status`, backfill `status: active` | **Selected.** `finding` does not become the one armed kind whose contract is weaker, and a hand-authored finding that omits `status` is refused — which is the programme's purpose. |
| Drop the requirement (`required: [id, kind]`, like `paper`/`topic`) | Rejected. All 52 markdown records author `status` and the template prescribes it; admitting a record without one is "preserved unvouched" — the defect this programme closes. |
| Loader backfills from `default_status`, declared injected | Rejected. A silent default, against the project's fail-early rule, and it changes behaviour for **every** structured kind — scope beyond this slice. |

Honest scope of the backfill, stated because the schema cannot tell: `is_default_visible`
(`entities.py:330`) documents that a missing status is *visible*, explicitly "NOT
`status == 'active'`". So writing `active` asserts marginally more than absence did. It is
still the correct value — the descriptor declares `default_status="active"`, the creation
path already setdefaults it (`entities.py:469`), and all 52 markdown findings are `active`
— but the step-3 test must assert this semantics directly rather than leaning on schema
validity, for the same reason the `updated` migration must.

## RULING: `relations[].note` — A Corpus Migration

`mixin-hypothesis-2.0` defines `$defs/authored_relation` as
`{predicate, target, graph_layer}` with `additionalProperties: false`, and says why: "a
typo'd key INSIDE a relation is silently dropped today, which is the class of defect this
arc exists to end." Its oracle is `AuthoredTargetedRelation`
(`science/model/src/science_model/source_contracts.py:18`), which declares exactly those
three fields.

All 3 `finding` records that author `relations` also author a fourth key, `note`, carrying
several lines of prose. Verified empirically on a real load of `~/d/natural-systems` — not
inferred from the model definition — the constructed entity keeps:

```python
[{'predicate': 'sci:amends', 'target': 'finding:0016-...', 'graph_layer': 'graph/knowledge'}]
```

**The `note` is silently discarded today.** It is the exact defect the `$comment` names,
sitting in the corpus of the kind being closed.

**Ruling: migrate the corpus; reuse `authored_relation` verbatim.** The 3 records drop
`note:` from their `relations` entries, and the mixin carves no finding-specific exception.
After the migration the schema **refuses** `note`, converting a silent discard into a
load-time failure.

Nothing is lost, and that was checked rather than assumed: each of the 3 notes is a
compressed restatement of that same record's `## Summary`, which already states the
amendment in full. Read side by side for all three (`0017`, `0018`, `0019`) before ruling.
The prose survives where it is actually rendered and read.

Rejected alternatives, by name:

| Alternative | Ruling |
|---|---|
| Drop `note` from the 3 records; reuse `authored_relation` | **Selected.** Nothing reads it, the model discards it, and the content is already in the body. |
| Add `note` to `AuthoredTargetedRelation` | Rejected. It stores prose no consumer reads, and it is a kind-agnostic model change made inside a kind's slice — the same objection the procedure raises against doing date normalization here. |
| Declare a finding-local relation `$def` admitting `note` | Rejected. The schema would vouch for a key the projection drops — "vouched but not preserved", the exact mirror of the defect this arc closes, and it would weaken a deliberate `additionalProperties: false` ruling for one kind. |

**Recorded for the `interpretation` slice:** 19 `interpretation` records in the same project
author `relations[].note` the same way. They are untouched here — each kind's slice owns its
own corpus — and that slice owes the same duplicate check rather than copying this ruling.
This is why the ruling is stated as "verified duplicates of the body", not as "`note` is
worthless".

## The Source Migration

One edit to `~/d/natural-systems/knowledge/sources/project_specific/finding.yaml`,
149 rows, two fields:

```text
updated = created        # all 149 rows: created == "2026-04-30"
status  = "active"
```

`updated = created` is the procedure's frozen rule. Migration date, file mtime, and
current date are rejected **by name**: all four candidates produce a schema-valid
`format: date` string, so schema validation cannot distinguish honest provenance from
fabrication. Step 3 must mutation-test all three rejected alternatives and assert the
provenance semantics directly.

This is a one-time edit to the source file, **never a loader default**. The loader must
keep failing when a row genuinely lacks `updated`; defaulting during load would make the
behavioural test unfalsifiable.

## `status` Vocabulary Cannot Be Certified by This Corpus

All 52 markdown records are `status: active`, and the 149 structured rows become `active`
by the migration. `finding` is not in `_CERTIFIED_KINDS`
(`validate/kind_severity.py:24` — still `{"hypothesis"}`), so the mixin declares
`status: {"type": "string"}` with **no enum**, per the standing rule that a schema enum
fails harder than a validate ERROR.

Recorded so no later reader mistakes uniformity for evidence: **no probe over this corpus
can distinguish a correct `status` vocabulary from an over-tight one.** `superseded` in
particular is declared by the descriptor and authored by nobody — on a `supersedable=True`
kind, which is exactly where a wrong vocabulary would hurt.

## Not This Slice's Surface

`science/src/science_tool/findings/` is **`AuditFinding`** machinery — the QA audit
registry, storage, ingestion and CLI, keyed on `doc_kind`, not on entity `kind: finding`.
A name collision only. It writes no entity frontmatter and is not part of this candidate
universe. Recorded because the package name makes it the first place a future reader will
look.

## Follow-Up Filed by This Slice

**F9 — `_STRUCTURED_INJECTED_KEYS`' comment generalizes from the armed kinds that happen
to admit these keys.** `sources.py:122-125` justifies not hiding `profile`, `aliases`,
`ontology_terms`, `related` and `source_refs` on the grounds that they "are admitted
(measured)". Measured per key across every packaged schema:

| key | admitted by |
|---|---|
| `ontology_terms` | base 2.0 — every kind |
| `related`, `source_refs` | the mixins that declare them (all five armed kinds do) |
| `profile` | `concept`, `search`, `hypothesis`, `method` — **not** `observation` |
| `aliases` | `hypothesis` 1.0/2.0, `method` 1.0 — **not** `concept`, `search`, `observation`; and no base, no overlay |

So the claim holds for the kinds it was measured against and does **not** generalize. It
does not bite this slice — 26 protein-landscape records author `aliases` on markdown, so
`mixin-finding-1.0` admits it regardless — and it cannot bite today, because until
`finding` is armed no armed kind takes the structured path at all. But the next kind routed
through the structured loader that does not itself author `aliases` or `profile` will have
100% of its rows refused for keys the loader backfilled as `[]`. The fix is either to widen
`_STRUCTURED_INJECTED_KEYS` or to restate the comment as the per-kind claim it actually is;
the choice needs the "who reads it?" analysis slice 4 applied to `consolidated_into`.

*(Filed first as the stronger claim "`aliases` is admitted by no mixin in the package",
which was wrong — `mixin-hypothesis-2.0` admits it. Corrected here by reading all sixteen
packaged schemas rather than the three this slice had already opened.)*

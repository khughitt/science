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
2. `method` — and it is the odd one out: the only tranche kind with a typed subclass
   (`MethodEntity`), so step 5 is the two-directional check as originally written.
3. `search`.
4. `observation`.
5. `finding` last, because it alone carries a source migration.

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

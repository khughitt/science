# Audit `undeclared_key` diagnostic — fb-2026-07-16-003

## Status

**Decision-ready.** Design approved; implementation plan pending. Fixes the
`_audit_entity` getattr misfire introduced when D5 flipped `Entity` to
`extra="allow"`, and adds a narrow `undeclared_key` diagnostic so a misplaced
reference field reports the real defect instead of a phantom
`unresolved_reference`.

## The defect

`fb-2026-07-16-003` (project `science`, target `graph:migrate._audit_reference`,
category `friction`) reports:

> `graph/migrate.py:332` audits the `method` ref via a bare
> `getattr(entity, "method", "")`. Its own comment documents the assumption that
> `method` is declared only by `WorkflowStepEntity` — true of the schema, but no
> longer true of the projection. Before `ae83241b` (2026-07-14, D5 "the schema
> goes first"), `Entity` was `extra="ignore"`, so a stray `method:` key on a
> workflow entity was dropped before `getattr` could see it. With
> `extra="allow"` the key is preserved, `getattr` finds it, and it is resolved
> against method entities that do not exist. cancer/mechanisms/evolution now gets
> 9 hard `validate` errors, all of the form `unresolved_reference — workflow:t007-gates
> method -> t007-gates-snakemake`.

The report identifies two problems:

1. **The diagnostic is misleading.** The real defect is "this field is not
   declared on this kind", not "this reference does not resolve". It sends a
   reader looking for missing `method` entities rather than at a stray key.
2. **The audit should be gated on the field being declared by the kind**, not on
   bare `getattr`. Nearby audits share the pattern and misfire the same way.

### Root cause, confirmed against the code

- Entities load as **concrete subclasses**: `registry.resolve(kind)` →
  `schema.model_validate(raw)` (`graph/sources.py:392,409`).
- The base class carries `model_config = ConfigDict(extra="allow")`
  (`science_model/entities.py:321`) — the D3.3 ruling ("Projections MUST preserve
  schema-valid extension fields. Never return to `extra="ignore"`").
- Under `extra="allow"`, a stray key lands in `entity.__pydantic_extra__` /
  `entity.model_extra`, **not** in the class's declared `model_fields`. Bare
  `getattr` reads both; the declared-field set reads only the former.
- `_audit_entity` (`graph/migrate.py:285`) audits reference fields via
  `getattr(entity, "<field>", <default>)` for the non-base fields, so any stray
  known reference-field name is audited as if it were a real reference.

### Which fields actually misfire

Field-by-field, mapping each audited reference field to the entity classes that
declare it (`model_fields`, inheritance-aware):

| Field | Declared by | Misfire-prone? |
|---|---|---|
| `method` | `workflow-step` only | **yes** (reported) |
| `workflow` | `workflow-run`, `workflow-step` | **yes** |
| `chain` | `structural-chain` only | **yes** |
| `audits` | `chain-audit` only | **yes** |
| `proposition_refs` | `chain-audit` only | **yes** |
| `blocked_by` | most kinds, **not** `chain-audit`/`domain` | **yes** (onto those two) |
| `related`, `source_refs`, `same_as`, `evidence_refs`, `dataset_usage`, `derivation`, `commits_to` | base `Entity` (every kind) | no — always declared |

The report named `commits_to` as vulnerable. It is a **base-`Entity` field**
(declared by every kind), so it can never be a stray extra key and cannot
misfire. Only the six fields marked "yes" need the gate.

## Resolution — Approach A

Gate the narrow sites; diagnose the misplacement once. Two independent pieces
plus a drift guard.

### Piece 1 — declared-by-kind gate

At each of the six narrow getattr sites in `_audit_entity`, read the field only
when the concrete class declares it:

```python
field_name in type(entity).model_fields
```

Declared → audit exactly as today (no behavior change). Undeclared → do not read
it as a reference (no phantom). The seven base-field sites (`related`,
`source_refs`, `same_as`, `evidence_refs`, `dataset_usage`, `derivation`,
`commits_to`) are left untouched — they are declared on every kind and provably
cannot misfire.

`type(entity).model_fields` is the established codebase idiom for
"class-declared fields" (used in `project_config.py`, `run_fingerprint_policy.py`,
`commons/geneset.py`, and elsewhere) and respects inheritance, so `blocked_by`
stays audited on every `ProjectEntity` subclass while being gated out on
`chain-audit`/`domain`.

### Piece 2 — the `undeclared_key` diagnostic

A new helper called once from `_audit_entity`:

```python
def _audit_undeclared_reference_keys(entity: Entity) -> list[AuditRow]:
    rows: list[AuditRow] = []
    for key in (entity.model_extra or {}):
        if key not in REFERENCE_FIELD_NAMES:
            continue  # a legitimate extension field (D3.3) — not our concern
        declaring = _kinds_declaring(key)
        rows.append({
            "check": "undeclared_key",
            "status": "warn",
            "source": entity.canonical_id,
            "field": key,
            "target": _stringify_extra_value(entity.model_extra[key]),
            "details": (
                f"`{key}` is not a declared field of kind `{entity.kind}`; "
                f"it is declared by {declaring}. Preserved as an extension field "
                f"but not wired into the graph — move it to the owning kind or remove it."
            ),
        })
    return rows
```

- `status: "warn"` — `audit_project_sources` computes
  `has_failures = any(row["status"] == "fail" for row in rows)`, so a `warn` row
  does not block `validate`. Evolution's 9 phantom ERRORs become 9 accurate
  WARNs and its `validate` unblocks.
- `_kinds_declaring(field_name)` maps entity classes whose `model_fields`
  contain `field_name` back to their registered kind strings, so the message
  names the owning kind (`workflow-step` for `method`). This is the actionable
  part of the diagnostic.
- `_stringify_extra_value` renders the preserved raw value (str / list / scalar)
  for the `target` column without assuming a shape.
- Only keys whose name is a **known reference field** are flagged. A genuine
  project extension field (any other name) is preserved silently, honoring D3.3.

### Piece 3 — deriving `REFERENCE_FIELD_NAMES` (no hole-by-construction)

A module-level `REFERENCE_FIELD_NAMES: frozenset[str]` holds every reference
field name `_audit_entity` audits. A guard test collects the field-name literals
actually passed to `_audit_reference` / `_audit_dataset_reference` inside
`_audit_entity` (AST walk over the function) and asserts equality with
`REFERENCE_FIELD_NAMES`. Adding an audit site without updating the set — or the
reverse — fails the test. The known-field set cannot silently drift from the
audits it is meant to mirror (the "derive the guard's scope, don't hand-list it"
rule).

## Testing

1. `WorkflowEntity` built with a stray `method: some-target` → `_audit_entity`
   yields exactly one row (`check="undeclared_key"`, `status="warn"`,
   `field="method"`) and **zero** `unresolved_reference` rows.
2. `WorkflowStepEntity` with a genuinely-unresolved `method:` → still yields
   `unresolved_reference` (regression guard: the gate must not suppress declared
   audits).
3. `WorkflowStepEntity` with a resolvable `method:` → no rows.
4. A legitimate non-reference extension key (e.g. `custom_note: hi`) on any kind
   → no `undeclared_key` row.
5. `blocked_by` stray on a `chain-audit` entity → `undeclared_key` WARN, no
   `unresolved_reference`.
6. Drift guard: `REFERENCE_FIELD_NAMES` equals the field names audited in
   `_audit_entity`.
7. Integration: `audit_project_sources` over a fixture carrying the stray key →
   `has_failures` stays `False`, and the WARN row is present.

Plus the existing migrate / audit suite for regressions:
`cd science && uv run --frozen pytest`.

## Record-corrections (nothing silently dropped)

1. **fb-2026-07-16-003** — resolved by this diagnostic; the misleading
   `unresolved_reference` is replaced by an accurate `undeclared_key` WARN.
2. **The feedback over-scoped `commits_to`.** It is a base-`Entity` field
   (declared by every kind) and cannot misfire; only the six subset-declared
   fields are affected. Recorded here so the correction is not lost.
3. **D5 design's undeclared-key inventory** (`2026-07-12-authoritative-entity-schema-design.md`,
   ~line 453, listing `role`, `input`, `report_kind`, `committed`, `spec`,
   `promoted_from`) — add a pointer noting that misplaced **known reference
   fields** are now handled generally by the `undeclared_key` diagnostic rather
   than needing a per-field inventory entry. This is the uninventoried instance
   D5:456-458 anticipated ("wiring a previously-dropped field still changes
   rebuilt graphs and validation output").

## Recorded follow-ups (out of scope here)

- **Ratchet.** `undeclared_key` should ratchet WARN → ERROR after a corpus sweep
  confirms no legitimate misplaced-reference keys remain — the standard
  certification path (a new check lands as WARN, the population is certified,
  then it hardens).
- **Evolution project data.** The 9 `workflow` entities carrying `method:` should
  relocate it to a `workflow-step` entity or drop it. A project-level decision,
  not a toolkit change; the WARN surfaces it.

## Out of scope

- The seven base-field sites (cannot misfire; untouched).
- Any `model_validate`-time rejection of the keys (fights D3.3 `extra="allow"`,
  wrong layer, and we chose WARN not hard-fail).
- The table-driven refactor of `_audit_entity` (Approach B) — larger diff, real
  regression risk, no benefit to the base fields; YAGNI for this defect.
- `curate/cli.py` and the composite-instrument guard-blindness item (unrelated,
  tracked separately).
```

# Audit `undeclared_key` diagnostic — fb-2026-07-16-003

## Status

**Decision-ready.** Design approved in principle; revised after review to make the
diagnostic pin-aware, thread the registry context it needs, and correct the
drift-guard, tests, and row format. Fixes the `_audit_entity` getattr misfire
introduced when D5 flipped `Entity` to `extra="allow"`, and adds a narrow,
pin-aware `undeclared_key` diagnostic so a misplaced reference field reports the
real defect instead of a phantom `unresolved_reference`.

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

### Two kinds of extra key — the pin decides which

`model_extra` does not hold one thing. Per the `Entity` docstring
(`entities.py:302-318`), it holds **schema-valid project extension fields**
(mm30's `identification`, evolution's `source_stated_evidence`) *and* raw
passthrough. The two are told apart by whether the composed profile schema
vouched for the key — and that check is **project-level, keyed on the pin**:

> This is safe ONLY because the schema is checked FIRST. … `unevaluatedProperties:
> false` on the composed profile is what refuses them, and `load_project_sources`
> runs it before constructing this model on any project pinned to
> `entity_schema_version: 2`.

So:

- **Pinned project (`entity_schema_version: 2`).** Every entity passed
  `unevaluatedProperties: false` at load. A stray key the profile does *not*
  declare is refused there and never reaches `_audit_entity`. Therefore any key
  present in `model_extra` at audit time is **schema-blessed for that kind** — a
  legitimate extension. Flagging it would be a false positive.
- **Unpinned project.** No schema pre-check ran; `extra="allow"` preserved
  everything, typos included. A key in `model_extra` is *not* vouched for by any
  schema.

This is why the diagnostic must be **pin-aware**: it fires only on unpinned
projects. A key named `method` on a `workflow` entity is a schema-declared
extension on a pinned project (leave it alone) but an unvouched, misplaced
reference name on an unpinned one (worth a WARN).

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
misfire. Only the six fields marked "yes" need the gate — but the gate is
applied uniformly (below) so the *set* is derived, never hand-classified.

## Resolution — Approach A

Gate every audited reference read through one helper; diagnose an unvouched
misplacement once, pin-aware. Three pieces plus a drift guard.

### Piece 1 — universal declared-by-kind gate

Introduce one helper and route **every** audited reference-field read through it:

```python
def _declared(entity: Entity, name: str, default: object) -> object:
    """Read a reference field only when the entity's concrete kind declares it.

    Under extra="allow" a stray same-named key lives in model_extra, not in
    model_fields; reading it via getattr would audit it as a real reference.
    """
    if name in type(entity).model_fields:
        return getattr(entity, name, default)
    return default
```

Applied uniformly:

- For the six subset-declared fields, `_declared` returns the default on a kind
  that does not declare the field, so a stray key is never audited as a
  reference (kills the misfire).
- For the seven base fields it is a no-op (`name` is always in `model_fields`),
  so their audits are behavior-identical. Routing them through the same helper
  means the drift guard (Piece 3) has a single, uniform call to collect and no
  site can be added that bypasses the gate.

`type(entity).model_fields` is the established codebase idiom for
"class-declared fields" (`project_config.py`, `run_fingerprint_policy.py`,
`commons/geneset.py`) and respects inheritance, so `blocked_by` stays audited on
every `ProjectEntity` subclass while being gated out on `chain-audit`/`domain`.

### Piece 2 — the pin-aware `undeclared_key` diagnostic

A new helper called once from `_audit_entity`, only when the project is
**unpinned**:

```python
def _audit_undeclared_reference_keys(
    entity: Entity,
    *,
    declaring_kinds: Mapping[str, tuple[str, ...]],
) -> list[AuditRow]:
    rows: list[AuditRow] = []
    for key in sorted(entity.model_extra or {}):        # deterministic order
        if key not in REFERENCE_FIELD_NAMES:
            continue  # a project extension field (D3.3) — not our concern
        owners = declaring_kinds.get(key, ())
        owner_clause = (
            f"; it is declared by {_format_kinds(owners)}" if owners else ""
        )
        rows.append({
            "check": "undeclared_key",
            "status": "warn",
            "source": entity.canonical_id,
            "field": key,
            "target": _stringify_extra_value(entity.model_extra[key]),
            "details": (
                f"`{key}` is not a declared field of kind `{entity.kind}`{owner_clause}. "
                f"Preserved as an extension field but not wired into the graph — "
                f"move it to the owning kind or remove it."
            ),
        })
    return rows
```

Caller (`_audit_entity`) skips this entirely when `schema_pinned` is `True`:

```python
if not schema_pinned:
    rows.extend(_audit_undeclared_reference_keys(entity, declaring_kinds=declaring_kinds))
```

- `status: "warn"` — `audit_project_sources` computes
  `has_failures = any(row["status"] == "fail" for row in rows)`, so a `warn` row
  does not block `validate`. On an unpinned project the phantom ERRORs become
  accurate WARNs and `validate` unblocks; on a pinned project the misfire simply
  stops (Piece 1) and no WARN is emitted.
- Only keys whose name is a **known reference field** are flagged
  (`REFERENCE_FIELD_NAMES`, derived in Piece 3). A genuine extension field of any
  other name is preserved silently, honoring D3.3.

### Piece 3 — threaded context and derived sets (no hole-by-construction)

Two facts `_audit_entity` does not currently receive must be threaded from
`audit_project_sources`, which holds `sources`:

1. **Pin status.** `ProjectSources` currently exposes no pin flag; the pin is
   computed in `load_project_sources` (`sources.py:247`) and discarded. Add a
   defaulted field `entity_schema_pinned: bool = False` to `ProjectSources`
   (`sources.py:163`), set it at the single construction site (`sources.py:663`)
   from the already-computed pin (`config.get("entity_schema_version") ==
   ENTITY_SCHEMA_VERSION`). `audit_project_sources` reads
   `sources.entity_schema_pinned` and passes it to each `_audit_entity` call.

2. **Declaring-kinds map.** `_kinds_declaring` cannot be computed from a bare
   `Entity`; it needs the active registry (core + profile + catalog + extension
   kinds), which lives on `sources.registry`. `EntityRegistry` exposes no
   all-kinds enumeration, so add one:

   ```python
   def registered_kinds(self) -> dict[str, type[Entity]]:
       """All registered kind -> bound model, deterministic by kind."""
       merged = {**self._core, **self._profile, **self._catalog, **self._extensions}
       return dict(sorted(merged.items()))
   ```

   `audit_project_sources` precomputes the map once and passes it down:

   ```python
   declaring_kinds: dict[str, tuple[str, ...]] = {
       field: tuple(
           kind for kind, cls in sources.registry.registered_kinds().items()
           if field in cls.model_fields
       )
       for field in REFERENCE_FIELD_NAMES
   }
   ```

   Kind order is deterministic (the map is sorted); a field with no declaring
   kind maps to `()` and the message omits the owner clause. For the six narrow
   fields the tuple is always non-empty (a core class declares each), but the
   empty case is handled rather than assumed.

3. **`REFERENCE_FIELD_NAMES` — derived, not hand-listed.** The eligible extra-key
   set is exactly the audited **top-level attribute names** that are *not*
   base-`Entity` fields:

   ```python
   REFERENCE_FIELD_NAMES = frozenset(_AUDITED_REFERENCE_FIELDS) - set(Entity.model_fields)
   ```

   where `_AUDITED_REFERENCE_FIELDS` is the tuple of attribute names passed as
   the first argument to `_declared(...)` in `_audit_entity`. This is a
   **top-level attribute name** (`derivation`), never an audit *label*
   (`derivation.inputs` — that string is only the `field_name` argument to
   `_audit_dataset_reference`, describing the nested path, and is not a Pydantic
   field, so it can never appear as a `model_extra` key). The drift guard (below)
   pins `_AUDITED_REFERENCE_FIELDS` to reality.

### Drift guard

A test AST-walks `_audit_entity` and collects the string literal first argument
of every `_declared(entity, "<name>", ...)` call. It asserts that set equals
`_AUDITED_REFERENCE_FIELDS`. Because every audited read now goes through
`_declared`, a new audit site that forgets the gate — or a name added to
`_AUDITED_REFERENCE_FIELDS` without a corresponding site — fails the test. The
audited-field set (and thus `REFERENCE_FIELD_NAMES`) cannot silently drift from
the audits it mirrors.

## Row format (deterministic)

Both rendered fields are defined so the row is fully assertable and stable for
sorting on `target`:

- `_stringify_extra_value(value)`:
  - `str` → the string as-is.
  - `list` / `tuple` → `", ".join(_stringify_extra_value(v) for v in value)`.
  - `dict` → `json.dumps(value, sort_keys=True, ensure_ascii=False)`.
  - anything else → `str(value)`.
- `_format_kinds(kinds)`: backtick-quote each already-sorted kind and join with
  `", "` (e.g. `` `workflow-step` `` or `` `workflow-run`, `workflow-step` ``).
  Empty input is never passed (the owner clause is omitted upstream).

## Testing

1. **Gate, parameterized across all six narrow fields.** For each of `method`,
   `workflow`, `chain`, `audits`, `proposition_refs`, `blocked_by`: build an
   entity of a kind that does *not* declare that field, with a stray key of that
   name and a non-resolvable value; assert `_audit_entity` (unpinned) yields
   **zero** `unresolved_reference` rows for that field and exactly one
   `undeclared_key` WARN row. This proves every gate, not just `method`.
2. **Declared audits preserved (regression).** `WorkflowStepEntity` with a
   genuinely-unresolved `method:` → still yields `unresolved_reference`.
3. `WorkflowStepEntity` with a resolvable `method:` → no rows.
4. **Legitimate non-reference extension key** (e.g. `custom_note: hi`) on any
   kind, unpinned → no `undeclared_key` row (name not in
   `REFERENCE_FIELD_NAMES`).
5. **Pin suppression.** The same stray `method:` on a `workflow` entity, with
   `schema_pinned=True` → **no** `undeclared_key` row (a pinned project's extra
   key is schema-blessed). Confirms Piece 2's pin gate.
6. **Full-row assertion.** Assert the complete `undeclared_key` row for the
   `method`-on-`workflow` case: `check`, `status`, `source`, `field`, `target`
   (rendered value), and `details` (including the `` `workflow-step` `` owner
   clause). Locks `_stringify_extra_value` and `_format_kinds`.
7. **Drift guard.** `_AUDITED_REFERENCE_FIELDS` equals the `_declared` call
   arguments in `_audit_entity` (AST walk).
8. **Integration, unpinned fixture.** `audit_project_sources` over an **unpinned**
   fixture project carrying the stray key → `has_failures` stays `False`, and the
   WARN row is present. The fixture must be unpinned: a pinned project's
   `unevaluatedProperties: false` would reject a genuinely-undeclared key at load,
   before `_audit_entity` runs.
9. **`registered_kinds` enumeration.** A registry with core + one extension kind
   returns all of them in sorted order.

Plus the existing migrate / audit suite for regressions:
`cd science && uv run --frozen pytest`.

## Record-corrections (nothing silently dropped)

1. **fb-2026-07-16-003** — resolved by this diagnostic; the misleading
   `unresolved_reference` is replaced by an accurate, pin-aware `undeclared_key`
   WARN.
2. **The feedback over-scoped `commits_to`.** It is a base-`Entity` field
   (declared by every kind) and cannot misfire; only the six subset-declared
   fields are affected. Recorded here so the correction is not lost.
3. **D5 design's undeclared-key inventory** (`2026-07-12-authoritative-entity-schema-design.md`,
   ~line 453, listing `role`, `input`, `report_kind`, `committed`, `spec`,
   `promoted_from`) — add a pointer noting that misplaced **known reference
   fields** are now handled generally by the pin-aware `undeclared_key`
   diagnostic rather than needing a per-field inventory entry. This is the
   uninventoried instance D5:456-458 anticipated ("wiring a previously-dropped
   field still changes rebuilt graphs and validation output").

## Recorded follow-ups (out of scope here)

- **Ratchet.** `undeclared_key` should ratchet WARN → ERROR after a corpus sweep
  confirms no unpinned project relies on a reference-named extension key — the
  standard certification path (a new check lands as WARN, the population is
  certified, then it hardens). The ratchet applies only to unpinned projects;
  pinned projects never emit it.
- **Evolution project data.** The 9 `workflow` entities carrying `method:` should
  relocate it to a `workflow-step` entity or drop it. A project-level decision,
  not a toolkit change; the WARN surfaces it (evolution is unpinned, so the WARN
  fires there).

## Alternatives considered

- **Reserve reference-field names globally** and enforce it in extension
  resolution, so any such name in `model_extra` is unambiguously a misplacement
  (pin-independent). Rejected: it touches profile composition, is a larger blast
  radius, and would retroactively invalidate any pinned project that legitimately
  declares an extension field of a reference name. The pin-aware skip achieves
  the same correctness with a smaller change.

## Out of scope

- The seven base-field reads' *behavior* (routed through `_declared` for
  uniformity, but unchanged — they cannot misfire).
- Any `model_validate`-time rejection of the keys (fights D3.3 `extra="allow"`,
  wrong layer, and we chose WARN not hard-fail).
- The table-driven refactor of `_audit_entity` (Approach B) — larger diff, real
  regression risk, no benefit to the base fields; YAGNI for this defect.
- `curate/cli.py` and the composite-instrument guard-blindness item (unrelated,
  tracked separately).

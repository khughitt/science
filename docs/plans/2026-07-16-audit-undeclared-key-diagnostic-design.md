# Audit `undeclared_key` diagnostic — fb-2026-07-16-003

## Status

**Decision-ready.** Design approved in principle; revised three times after
review. The diagnostic is gated on the **strict-schema kind set** (the kinds
whose extra-preserving load is schema-checked — not a project-wide pin boolean),
threads the registry context it needs, and has a drift guard that independently
rediscovers audited sites and fails closed on non-literal labels. Fixes the
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

### Two kinds of extra key — the strict-schema kind set decides

`model_extra` does not hold one thing. Per the `Entity` docstring
(`entities.py:302-318`), it holds **schema-valid project extension fields**
(mm30's `identification`, evolution's `source_stated_evidence`) *and* raw
passthrough. The two are told apart by whether the composed profile schema
vouched for the key. That check is **per-kind**, and its scope is narrower than
"pinned":

`_validate_against_schema` (`graph/sources.py`) returns early unless
`project_schema is not None` **and** `kind in PROJECT_MIXIN_NAMES`. And
`PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})`
(`science_model/entity_schema/profile.py:24`). So even on a **pinned** project,
today only `hypothesis` entities are checked with `unevaluatedProperties: false`;
`workflow`, `workflow-step`, `chain-audit`, etc. are **not** schema-validated at
all. A stray `method:` on a `workflow` entity is therefore *never* refused at
load — pinned or not — and reaches `_audit_entity` unvouched.

The load-bearing fact is thus **the set of kinds whose extra-preserving load the
loader schema-checks** — the strict-schema policy set — not the project-wide pin:

- If `entity.kind` **is** in that set, a stray unknown key would have been refused
  at load (`unevaluatedProperties: false`), so any key present in `model_extra` at
  audit time is schema-blessed for that kind — a legitimate extension. Do not
  flag it.
- If `entity.kind` is **not** in that set (every kind but `hypothesis` today, and
  every kind on an unpinned project), no schema vouched for its extra keys. A key
  named like a reference field is an unvouched misplacement — worth a WARN.

This is why the diagnostic is gated on `entity.kind not in strict_schema_kinds`
rather than on a `schema_pinned` boolean: a boolean would wrongly suppress the
WARN for a stray `method` on a pinned project's `workflow`. As `PROJECT_MIXIN_NAMES`
grows over the migration, this gate auto-narrows — a kind that starts being
schema-validated stops emitting the WARN, because its extra keys are then vouched.

### Why the strict-schema kind set is a sound gate — the extra-preserving-path invariant

`strict_schema_kinds` is a **strict-schema policy** set, not literal per-entity
validation provenance: `_validate_against_schema` runs only inside the
markdown-adapter loop (`sources.py:365`), while structured-source entities load by
a separate path (`sources.py:1000+`) that never calls it. The gate is still exact
because of an invariant on which load paths can produce a `model_extra` key at all:

- The **markdown adapter** projects frontmatter onto `Entity` (`extra="allow"`),
  so it is the only path that preserves unknown keys — and it is exactly the path
  `_validate_against_schema` guards.
- **Structured sources** load through `StructuredEntitySource`, whose
  `model_config = ConfigDict(extra="ignore")` (`source_contracts.py:71`) **drops**
  unknown fields. A structured-source entity of any kind therefore has an empty
  (of stray keys) `model_extra`, so `_audit_undeclared_reference_keys` finds
  nothing to flag regardless of whether its kind is in the set.

So the only entities that can carry an unvouched extra key are precisely the ones
the strict-schema policy governs. The set is named `strict_schema_kinds` (not
`schema_validated_kinds`) to state this honestly, and a regression test pins the
invariant (a structured-source entity has no stray `model_extra`), so a future
extra-preserving load path cannot silently defeat the gate.

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
misplacement once, gated on the strict-schema kind set. Three pieces plus a
drift guard.

### Piece 1 — universal declared-by-kind gate

Introduce one helper and route **every** audited reference-field read through it:

```python
def _declared(entity: Entity, name: str, default: Any) -> Any:
    """Read a reference field only when the entity's concrete kind declares it.

    Under extra="allow" a stray same-named key lives in model_extra, not in
    model_fields; reading it via getattr would audit it as a real reference.

    Returns Any deliberately: it replaces `getattr(entity, name, default)`, which
    is already typed Any, so the audited call sites (list iteration, str args to
    _audit_reference, Derivation access) keep their existing typing with no casts
    and no new Pyright suppressions. Type safety here is no worse than the getattr
    it replaces.
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
  means the drift guard (below) can assert that no reference read bypasses the
  gate.

`type(entity).model_fields` is the established codebase idiom for
"class-declared fields" (`project_config.py`, `run_fingerprint_policy.py`,
`commons/geneset.py`) and respects inheritance, so `blocked_by` stays audited on
every `ProjectEntity` subclass while being gated out on `chain-audit`/`domain`.

### Piece 2 — the `undeclared_key` diagnostic, gated on the strict-schema kind set

A new helper called once from `_audit_entity`, only when the entity's kind is
outside the strict-schema set:

```python
def _audit_undeclared_reference_keys(
    entity: Entity,
    *,
    declaring_kinds: Mapping[str, tuple[str, ...]],
) -> list[AuditRow]:
    rows: list[AuditRow] = []
    for key in sorted(entity.model_extra or {}):        # deterministic order
        if key not in REFERENCE_FIELD_NAMES:
            continue  # a non-reference-named extra key — never our concern
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
                f"It is an unvouched extra key on this kind, not wired into the graph — "
                f"move it to the owning kind or remove it."
            ),
        })
    return rows
```

Caller (`_audit_entity`) runs it only for kinds outside the strict-schema set:

```python
if entity.kind not in strict_schema_kinds:
    rows.extend(_audit_undeclared_reference_keys(entity, declaring_kinds=declaring_kinds))
```

- `status: "warn"` — `audit_project_sources` computes
  `has_failures = any(row["status"] == "fail" for row in rows)`, so a `warn` row
  does not block `validate`. On the affected projects the phantom ERRORs become
  accurate WARNs and `validate` unblocks; where the kind is under the strict
  schema the misfire simply stops (Piece 1) and no WARN is emitted.
- Only keys whose name is a **known reference field** are flagged
  (`REFERENCE_FIELD_NAMES`, derived in Piece 3). A `hypothesis`'s vouched
  extension field never reaches here (its kind is in the set); an unvouched extra
  key of any non-reference name is preserved silently, honoring D3.3.

### Piece 3 — threaded context and derived sets (no hole-by-construction)

`_audit_entity` gains **two required parameters** (no defaults, so a caller
cannot silently pass the conservative-but-wrong empty value), both threaded from
`audit_project_sources`, which holds `sources`. The eligible-key set
`REFERENCE_FIELD_NAMES` is *not* threaded — it is a module-level constant derived
at import (item 3 below).

1. **The strict-schema kind set.** `ProjectSources` exposes no record of what the
   loader strict-checked. Add a field
   `strict_schema_kinds: frozenset[str] = frozenset()` to `ProjectSources`
   (`sources.py:163`), set at the single construction site (`sources.py:663`) to
   `PROJECT_MIXIN_NAMES if project_schema is not None else frozenset()` — exactly
   the kinds `_validate_against_schema` enforced. The empty default is the
   conservative one (nothing vouched ⇒ diagnostic can fire), so a forgotten
   constructor never silently suppresses. `audit_project_sources` reads
   `sources.strict_schema_kinds` and passes it to each `_audit_entity` call. This
   auto-tracks `PROJECT_MIXIN_NAMES`: when the migration slice grows, pinned
   projects strict-check more kinds and the set widens with no code change here.

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

3. **`REFERENCE_FIELD_NAMES` — a derived module constant, not hand-listed.** The
   eligible extra-key set is exactly the audited **top-level attribute names**
   that are *not* base-`Entity` fields:

   ```python
   REFERENCE_FIELD_NAMES = frozenset(_AUDITED_REFERENCE_FIELDS) - set(Entity.model_fields)
   ```

   where `_AUDITED_REFERENCE_FIELDS` is the tuple of attribute names read for
   auditing in `_audit_entity`. These are **top-level attribute names**
   (`derivation`), never audit *labels* (`derivation.inputs` — that string is only
   the `field_name` argument to `_audit_dataset_reference`, describing the nested
   path; it is not a Pydantic field and can never appear as a `model_extra` key).
   The drift guard pins `_AUDITED_REFERENCE_FIELDS` to reality.

### Drift guard — independently rediscovers audited sites, fails closed

A `{_declared args} == _AUDITED_REFERENCE_FIELDS` equality alone is blind to a
future bare `getattr(entity, "foo")` feeding an audit call, or an audit call whose
`field_name` is a keyword or a non-literal: neither side moves, so the test would
pass while the gate is bypassed. The guard therefore checks the gate from the
audit side and fails closed on anything it cannot statically read. It AST-walks
`_audit_entity` and asserts **all four**:

1. **No bare entity getattr.** `_audit_entity` contains zero
   `getattr(entity, <literal>, ...)` calls. Every reference read must go through
   `_declared`; entity metadata (`entity.kind`, `entity.canonical_id`,
   `entity.file_path`) uses plain attribute access and is unaffected.
2. **Every audit call exposes a literal label.** For each call to
   `_audit_reference` / `_audit_dataset_reference`, resolve `field_name` from
   positional index 1 **or** the `field_name=` keyword. If it is absent or not an
   `ast.Constant` string, the guard **fails** ("audit call with a non-literal
   field_name cannot be verified"). This is the fail-closed rule the reviewer
   required.
3. **Every audited field is gated.** Collect `AUDITED` = the top-level prefixes of
   those literal labels (`"derivation.inputs"` → `"derivation"`). Collect `GATED`
   = the first-arg literals of `_declared(entity, "<name>", ...)`. Assert
   `AUDITED <= GATED`. A `getattr`/direct-attribute read feeding
   `_audit_reference(entity, "foo", ...)` puts `"foo"` in `AUDITED` but not
   `GATED` → fail.
4. **The named constant is honest.** Assert `GATED == set(_AUDITED_REFERENCE_FIELDS)`,
   so `REFERENCE_FIELD_NAMES` (derived from it) cannot drift from the reads.

Negative cases the guard test exercises against synthetic function bodies: a bare
`getattr(entity, "foo")` feeding an audit call (assertions 1 & 3); a
keyword-form bypass `_audit_reference(entity, field_name="foo", target=entity.foo, ...)`
(assertion 3); and a non-literal label `_audit_reference(entity, some_var, ...)`
(assertion 2). Each must be rejected.

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
   entity of a kind that does *not* declare that field (and outside
   `strict_schema_kinds`), with a stray key of that name and a non-resolvable
   value; assert `_audit_entity` yields **zero** `unresolved_reference` rows for
   that field and exactly one `undeclared_key` WARN row. Proves every gate.
2. **Declared audits preserved (regression).** `WorkflowStepEntity` with a
   genuinely-unresolved `method:` → still yields `unresolved_reference`.
3. `WorkflowStepEntity` with a resolvable `method:` → no rows.
4. **Non-reference extra key** (e.g. `custom_note: hi`) on a kind outside the set
   → no `undeclared_key` row (name not in `REFERENCE_FIELD_NAMES`).
5. **Strict-schema-kind suppression.** Stray `method:` on an entity whose
   `entity.kind` **is** in `strict_schema_kinds` (e.g. `hypothesis`) → **no**
   `undeclared_key` row (its extra keys are schema-vouched). Constructed directly
   at the audit layer, since a real load would have refused the key.
6. **Unvalidated kind on a pinned project still warns (the P1 regression this
   design turns on).** `strict_schema_kinds = frozenset({"hypothesis"})`
   (a pinned project) and a `workflow` entity with a stray `method:` → the
   `undeclared_key` WARN **fires**, because `workflow` is not strict-checked even
   when pinned. A `schema_pinned` boolean would have wrongly suppressed this.
7. **Structured-source invariant.** A structured-source entity of a kind outside
   the set, loaded with an unknown reference-named key in its row, has an empty
   (of stray keys) `model_extra` — `StructuredEntitySource` drops it — so
   `_audit_undeclared_reference_keys` emits nothing. Pins the extra-preserving-path
   invariant the gate relies on.
8. **Full-row assertion.** Assert the complete `undeclared_key` row for the
   `method`-on-`workflow` case: `check`, `status`, `source`, `field`, `target`
   (rendered value), and `details` (including the `` `workflow-step` `` owner
   clause and the "unvouched extra key" wording). Locks `_stringify_extra_value`
   and `_format_kinds`.
9. **Drift guard (all four assertions + negatives).** No `getattr(entity, ...)` in
   `_audit_entity`; every audit call has a literal `field_name`; `AUDITED <= GATED`;
   `GATED == set(_AUDITED_REFERENCE_FIELDS)`. Plus the three synthetic negative
   bodies (bare getattr, keyword-form bypass, non-literal label) are each rejected.
10. **Integration, unpinned fixture.** `audit_project_sources` over an **unpinned**
    fixture project (`strict_schema_kinds` empty) carrying the stray key →
    `has_failures` stays `False`, WARN row present.
11. **`registered_kinds` enumeration.** A registry with core + one extension kind
    returns all of them in sorted order.

Plus the existing migrate / audit suite for regressions:
`cd science && uv run --frozen pytest`.

## Record-corrections (nothing silently dropped)

1. **fb-2026-07-16-003** — resolved by this diagnostic; the misleading
   `unresolved_reference` is replaced by an accurate `undeclared_key` WARN gated
   on the strict-schema kind set.
2. **The feedback over-scoped `commits_to`.** It is a base-`Entity` field
   (declared by every kind) and cannot misfire; only the six subset-declared
   fields are affected. Recorded here so the correction is not lost.
3. **The `Entity` docstring overstates schema-first coverage.**
   `entities.py:314-317` says `unevaluatedProperties: false` "runs before
   constructing this model on any project pinned to `entity_schema_version: 2`."
   The reality is per-kind: it runs only for `kind in PROJECT_MIXIN_NAMES`
   (`hypothesis` today). The implementation updates that docstring to the
   per-kind reality, so the source contract stops asserting the whole-project
   premise this design rejected.
4. **D5 design's undeclared-key inventory** (`2026-07-12-authoritative-entity-schema-design.md`,
   ~line 453, listing `role`, `input`, `report_kind`, `committed`, `spec`,
   `promoted_from`) — add a pointer noting that misplaced **known reference
   fields** are now handled generally by the `undeclared_key` diagnostic rather
   than needing a per-field inventory entry. This is the uninventoried instance
   D5:456-458 anticipated ("wiring a previously-dropped field still changes
   rebuilt graphs and validation output").

## Recorded follow-ups (out of scope here)

- **Ratchet.** `undeclared_key` should ratchet WARN → ERROR after a corpus sweep
  confirms no project relies on a reference-named extra key on a non-strict-checked
  kind — the standard certification path. The ratchet applies only to kinds
  outside `strict_schema_kinds`.
- **Evolution project data.** The 9 `workflow` entities carrying `method:` should
  relocate it to a `workflow-step` entity or drop it. A project-level decision,
  not a toolkit change; the WARN surfaces it (`workflow` is not strict-checked, so
  the WARN fires regardless of the project's pin).

## Alternatives considered

- **Reserve reference-field names globally** and enforce it in extension
  resolution, so any such name in `model_extra` is unambiguously a misplacement
  (kind-set-independent). Rejected: it touches profile composition, is a larger
  blast radius, and would retroactively invalidate any project that legitimately
  declares an extension field of a reference name once its kind joins
  `PROJECT_MIXIN_NAMES`. The kind-set gate achieves the same correctness with a
  smaller change.
- **A project-wide `schema_pinned` boolean.** Rejected per P1 above: pinning does
  not imply every kind was strict-checked (`PROJECT_MIXIN_NAMES` is currently just
  `hypothesis`), so a boolean suppresses WARNs it must emit.
- **Tracking validated entity IDs for exact provenance.** Unnecessary: the only
  load path that preserves extras is the strict-checked markdown adapter;
  structured sources drop unknowns (`extra="ignore"`), so a kind-set gate plus the
  invariant test is exact without per-entity bookkeeping.

## Out of scope

- The seven base-field reads' *behavior* (routed through `_declared` for
  uniformity, but unchanged — they cannot misfire).
- Any `model_validate`-time rejection of the keys (fights D3.3 `extra="allow"`,
  wrong layer, and we chose WARN not hard-fail).
- The table-driven refactor of `_audit_entity` (Approach B) — larger diff, real
  regression risk, no benefit to the base fields; YAGNI for this defect.
- `curate/cli.py` and the composite-instrument guard-blindness item (unrelated,
  tracked separately).

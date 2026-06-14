# Typed Dataset Resource Schema + Science Profile — Design (Spec 1)

**Goal:** Establish the typed Data Resource schema as the single source of truth for a
dataset's shape and quality contract — native Frictionless Table Schema for *invariants*,
a tiny `qa:` extension for *review-grade distribution checks* — modelled in Pydantic,
published as an offline `$schema` profile, and enforced additively by `science datasets validate`.

**Architecture:** Pydantic models in `science_tool/datasets/schema.py` are the source of
truth. They model the subset of the Frictionless Data Resource / Table Schema we consume,
plus a small `qa:` custom-property extension. The published JSON Schema profile is *emitted*
from those models (no hand-maintained second artifact) and ships in-package for offline
validation. `science_qa` is **not** touched here — schema *consumption* is Spec 2.

**Tech Stack:** Python, Pydantic v2 (already a core `science_tool` dependency), Frictionless
Data Package / Table Schema (already the on-disk datapackage format).

---

## 1. Background & motivation

Dogfooding the `science_qa` check-library (2026-06-13) against a real pipeline output
(`~/d/protein-landscape/results/phase3/lens-disagreement.parquet`) showed the data-agnostic
aspects work, but that the QA config re-declares per-column information (types, required
columns, ranges) by hand — laborious, and disconnected from the dataset's own schema.

Meanwhile the framework **already** types columns: real datapackages carry a Frictionless
Table Schema (`resources[].schema.fields[].name` + `.type`), and `science datasets validate`
(`datasets/validate.py` → `_validate_resource_schema`) already checks field presence and
per-row type conformance against it. But `fields[].constraints` is supported-yet-unused, and
QA's column declarations live in a *separate* config. Two disconnected systems do column
typing.

This spec unifies them: make the dataset's typed schema the **single source of truth** that
both `datasets validate` and (later) `science_qa` consume. Spec 1 builds the contract; it is
the first of three layered specs:

- **Spec 1 (this doc)** — typed Resource schema + science profile + additive `datasets validate`.
- **Spec 2** — schema→checks compiler + generic-`tabular` program in `science_qa` (delivers the
  dogfood payoff: QA driven by the declared schema, no hand-written column config).
- **Spec 3** — unification/cleanup: dedupe `datasets validate` ↔ `science_qa` against the one
  schema; backfill existing datapackage schemas; retire standalone qa-config column declarations.

## 2. Scope

**In scope (Spec 1):**
- Pydantic models for the Data Resource descriptor subset we consume + the `qa:` extension.
- Emission of the `$schema` JSON Schema profile from those models, with a determinism contract
  and a golden drift test.
- Additive descriptor validation in `science datasets validate`: well-formedness +
  self-consistency guardrails.

**Out of scope (deferred to later specs):**
- Schema *inference* from a produced parquet/arrow file (later).
- Reusable domain *policy presets* / soft QC thresholds, e.g. scRNA gates (later).
- `science_qa` reading the schema and compiling checks (Spec 2).
- Deduping `datasets validate`'s existing data-conformance pass against QA (Spec 3).

## 3. Core concept: two zones = two severities

A Resource's `schema` carries two semantically distinct zones that map exactly onto
`science_qa`'s existing structural-vs-distribution severity split:

| Zone | Lives in | Maps to QA severity | Meaning |
|---|---|---|---|
| **Invariants** | native Table Schema: `type`, `constraints`, `primaryKey`, `uniqueKeys`, `foreignKeys`, `missingValues` | **structural** (build-fatal) | data violating this is a *bug* |
| **Distribution** | a small `qa:` custom property (field-level + table-level) | **distribution** (domain review) | a statistical / relational *smell* |

The Frictionless standard absorbs almost everything as invariants, so the `qa:` extension is
deliberately **tiny**. The severity each declaration maps to is fixed by which zone it lives
in; the actual mapping to runnable checks is Spec 2's concern.

## 4. The vocabulary

### 4.1 Invariants (native Table Schema → structural)

| Declaration | Native feature | Check it implies (Spec 2) |
|---|---|---|
| column type | `fields[].type` (omitted ⇒ `any` per DP v2) | type-conformance |
| non-null | `fields[].constraints.required` | required-complete |
| column-unique | `fields[].constraints.unique` | unique-key (single column) |
| row identity | `primaryKey` (`str \| list[str]`) | unique-key (composite) |
| extra uniqueness | `uniqueKeys` (`list[list[str]]`, **Frictionless-native**, null-per-SQL) | unique-key (composite) |
| bounded value | `fields[].constraints.minimum / maximum / exclusiveMinimum / exclusiveMaximum` | **hard bound — structural** |
| inline domain | `fields[].constraints.enum` | categorical (inline allowed-values) |
| referenced domain | `foreignKeys` → another resource's field | categorical (reference-backed; the commons-resource case, native) |
| null sentinels | table-level `missingValues` (field-level override accepted, consumed later) | declared-null parsing directive |

**Severity decision (confirmed): declared `minimum`/`maximum` are invariants → structural
(build-fatal), not distribution.** Once a bound is declared in the resource schema, a value
outside it is invalid data, not a statistical smell. This is a deliberate shift from the
current `science_qa` `ranges` aspect (distribution severity); Spec 2 honours the new mapping.
Soft QC thresholds (e.g. scRNA `min_counts: 500`, where sub-threshold rows are *filtered*, not
*wrong*) are **not** schema constraints — they are deferred domain policy.

`polarity` (non-negative) collapses into `constraints.minimum: 0`, and `ranges` collapse into
native `minimum`/`maximum`, so neither appears in the `qa:` extension.

### 4.2 Distribution (`qa:` extension → distribution) — the entire residue

The only checks Frictionless cannot express are statistical (per-column) and relational
(cross-column). They form the whole extension:

- **field-level** `qa: { low_variance: bool, zero_fraction: bool }`
  - `low_variance` — flag a (near-)constant column.
  - `zero_fraction` — flag an entirely/mostly-zero column.
- **table-level** `qa: { exclusive_flags: [[colA, colB], ...] }`
  - mutually-exclusive boolean/flag column pairs.

These are **boolean enables** in Spec 1 (no thresholds). Tunable thresholds (variance epsilon,
max zero fraction) are policy and are deferred; the Spec 2 executor uses sensible defaults.

## 5. Pydantic models (`datasets/schema.py`, the SSOT)

Design notes baked into the models:

- **`$schema` is modelled explicitly** (not merely tolerated via `extra="allow"`), so the
  marker is documented in the emitted profile and an invalid marker fails validation rather
  than passing silently.
- **`extra="allow"` is applied consistently** at every descriptor level — Frictionless
  descriptors commonly grow additional *standard* properties below the resource, and we must
  never reject a valid-but-unmodelled property.
- **No mutable defaults** — every container uses `default_factory`.
- **External key is always `schema`**; `schema_` is a Python-only attribute name (Pydantic
  alias) to avoid shadowing `BaseModel.schema`. All (de)serialization uses the external key.

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

FrictionlessType = Literal[
    "string", "number", "integer", "boolean", "object", "array", "list",
    "datetime", "date", "time", "year", "yearmonth", "duration",
    "geopoint", "geojson", "any",
]


class MissingValue(BaseModel):
    """A null sentinel: a bare string, or a labelled object (DP v2)."""
    model_config = ConfigDict(extra="allow")
    value: str
    label: str = ""


class FieldConstraints(BaseModel):
    model_config = ConfigDict(extra="allow")
    required: bool = False
    unique: bool = False
    # Bounds apply to numeric AND temporal types; values may be strings castable
    # with the field type (e.g. "2020-01-01", "P1Y"). Applicability to the declared
    # type is enforced by a self-consistency guardrail (§7), not by the value type.
    minimum: str | int | float | None = None
    maximum: str | int | float | None = None
    exclusiveMinimum: str | int | float | None = None
    exclusiveMaximum: str | int | float | None = None
    enum: list[object] | None = None
    pattern: str | None = None


class FieldQA(BaseModel):
    """The distribution-severity extension carried per field."""
    model_config = ConfigDict(extra="forbid")  # closed: our namespace, typo-protected
    low_variance: bool = False
    zero_fraction: bool = False


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    type: FrictionlessType = "any"          # DP v2: omitted type ⇒ "any" (NOT "string")
    constraints: FieldConstraints = Field(default_factory=FieldConstraints)
    # Field-level missingValues override (DP v2) — accepted/round-tripped, but not
    # *consumed* until a later spec; table-level missingValues remains the primary path.
    missingValues: list[str | MissingValue] | None = None
    qa: FieldQA = Field(default_factory=FieldQA)


class ForeignKeyReference(BaseModel):
    model_config = ConfigDict(extra="allow")
    resource: str = ""                       # "" (or absent) = self-reference
    fields: str | list[str]


class ForeignKey(BaseModel):
    model_config = ConfigDict(extra="allow")
    fields: str | list[str]
    reference: ForeignKeyReference

    @model_validator(mode="after")
    def _cardinality(self) -> "ForeignKey":
        local = [self.fields] if isinstance(self.fields, str) else self.fields
        ref = ([self.reference.fields] if isinstance(self.reference.fields, str)
               else self.reference.fields)
        if len(local) != len(ref):
            raise ValueError(
                f"foreignKey cardinality mismatch: {len(local)} local field(s) "
                f"vs {len(ref)} reference field(s)")
        return self


class TableQA(BaseModel):
    """The distribution-severity extension carried at table level."""
    model_config = ConfigDict(extra="forbid")
    exclusive_flags: list[tuple[str, str]] = Field(default_factory=list)


class TableSchema(BaseModel):
    model_config = ConfigDict(extra="allow")
    fields: list[FieldSpec]
    primaryKey: str | list[str] | None = None
    # `None` = absent. When present, DP v2 requires uniqueKeys non-empty and each inner
    # key-group non-empty — enforced by a validator (distinguishes absent from `[]`).
    uniqueKeys: list[list[str]] | None = None
    foreignKeys: list[ForeignKey] = Field(default_factory=list)
    missingValues: list[str | MissingValue] = Field(default_factory=lambda: [""])
    qa: TableQA = Field(default_factory=TableQA)

    @model_validator(mode="after")
    def _unique_keys_non_empty(self) -> "TableSchema":
        if self.uniqueKeys is not None:
            if not self.uniqueKeys:
                raise ValueError("uniqueKeys, when present, must be non-empty")
            if any(not group for group in self.uniqueKeys):
                raise ValueError("each uniqueKeys group must be non-empty")
        return self


class ResourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    profile: Literal["science-data-resource/v1"] | None = Field(default=None, alias="$schema")
    name: str
    path: str
    schema_: TableSchema | None = Field(default=None, alias="schema")
```

Notes:
- **This profile targets Data Package Standard v2, while accepting v1 compatibility forms for
  `primaryKey` and `foreignKeys`.** That makes the `uniqueKeys`, `list` type, exclusive bounds,
  and omitted-`type`-⇒-`any` choices unambiguous (all v2), while a single-string `primaryKey`
  or the v1 self-reference `foreignKey` form still parse.
- `FieldQA` / `TableQA` use `extra="forbid"` (closed): the `qa:` namespace is *ours*, so a typo
  like `qa: { low_varianse: true }` should fail loudly rather than be silently retained.
  Everything else uses `extra="allow"` for forward-compatibility with the evolving standard.
- `populate_by_name=True` lets internal code construct with `schema_=...`/`profile=...` while
  descriptors on disk use `schema`/`$schema`.
- `missingValues` entries must be **unique** (DP v2); a validator enforces uniqueness across the
  bare-string and labelled-object forms.
- We model only the subset we consume; deeper Frictionless features (dialects, `fieldsMatch`,
  `jsonSchema`, etc.) pass through via `extra="allow"` untouched.

## 6. The `$schema` profile (offline, versioned)

- **Emitted** from `ResourceDescriptor.model_json_schema(by_alias=True)` and committed to
  `science/src/science_tool/datasets/profiles/science-data-resource-v1.json`. It ships in the
  package and is resolved **offline** — the light `science_qa` (Spec 2) never needs the
  network, and `datasets validate` validates via the bundled Pydantic model, not by fetching a
  URL.
- **Version marker:** descriptors may carry `"$schema": "science-data-resource/v1"`. It records
  which profile version the author targeted and is validated by the explicit `profile` field
  (Literal). It is not dereferenced.
- **Emission determinism (golden-test contract):** the committed file is produced by
  `model_json_schema(by_alias=True)` serialized with `json.dumps(..., indent=2, sort_keys=True)`
  + trailing newline. A test asserts the committed file byte-equals freshly-emitted output, so
  the published profile can never drift from the models. `by_alias=True` guarantees `schema_`
  emits as `schema` and the `$schema` marker emits correctly.
- A small CLI/utility regenerates the file: `python -m science_tool.datasets.schema --emit`
  (exact entrypoint finalized in the plan).

## 7. `science datasets validate` integration (additive)

Extend `validate_data_packages()` with a descriptor-validation pass that runs **before** the
existing data-conformance checks and never replaces them (consolidation is Spec 3):

1. **Well-formedness** — parse each resource via `ResourceDescriptor.model_validate(...)`;
   surface Pydantic's located errors as validation rows.
2. **Self-consistency guardrails** (the real authoring value — checks the *descriptor* is
   internally coherent, using only the declared schema, no data access):
   - `primaryKey` / `uniqueKeys` / `qa.exclusive_flags` reference declared field names.
   - `foreignKeys[].fields` reference declared field names; when `reference.resource` is named,
     it matches another resource declared in the same package, and `reference.fields` exist on
     that target's schema (self-reference when `resource == ""`).
   - `enum`, when present, is non-empty; `uniqueKeys`, when present, is non-empty with no empty
     inner group (absent ≠ explicit `[]`); `missingValues` *values* are unique (labels are
     descriptive and intentionally not required to be unique).
   - **No duplicate field names** within a schema, and **no duplicate resource names** within a
     package (otherwise field/FK resolution silently collapses on the last definition).
   - **Bounds applicability**: `minimum` / `maximum` / `exclusiveMinimum` / `exclusiveMaximum`
     only on numeric (`integer`, `number`) or temporal (`date`, `datetime`, `time`, `year`,
     `yearmonth`, `duration`) declared types.
   - **Declared-type applicability of `qa:` checks** (see §8): `low_variance` / `zero_fraction`
     only on `integer | number | boolean` fields; `exclusive_flags` pairs only on
     `boolean | integer` fields.

The existing per-row type-conformance pass is unchanged. Spec 1 is purely additive: a package
with no `constraints`/`qa:` blocks validates exactly as before.

## 8. Type-applicability boundary (named, per review)

Applicability of a `qa:` check to a column is validated in **two** places, deliberately split:

- **Spec 1 — declared-type applicability.** Cheap and authoring-time: the field's declared
  `type` is right there in the schema, so `datasets validate` rejects nonsensical declarations
  (e.g. `low_variance` on a `string` field, `exclusive_flags` over a `datetime`). This catches
  author errors before any data is produced.
- **Spec 2 — runtime-dtype applicability.** The compiler/executor inspects the *loaded* column's
  actual pandas dtype and performs selector matching (consistent with the existing
  `selector={"dtype": "numeric"}` mechanism). Declared type and realized dtype can diverge
  (e.g. an all-null column, an int-coded flag); the executor is the final arbiter of whether a
  check runs, is `blocked`, or is `not-applicable`.

## 9. Error handling

- Malformed descriptor → a `datasets validate` **`fail`** row (located Pydantic message), per the
  command's existing `pass|fail|warn` row contract (the CLI exits non-zero only on `fail`); the
  command continues across other resources (existing behaviour).
- Invalid `$schema` marker → rejected by the `profile` Literal (well-formedness failure).
- Unknown standard property below resource level → accepted (`extra="allow"`); unknown property
  inside the `qa:` namespace → rejected (`extra="forbid"`).

## 10. Testing strategy

- **Model unit tests:** valid descriptors (minimal; full; with `constraints`/`qa:`/`foreignKeys`);
  alias round-trip (`schema`/`$schema` ↔ `schema_`/`profile`); `extra="allow"` passthrough at
  each level; `qa:` `extra="forbid"` rejects typos; foreignKey cardinality validator.
- **Self-consistency guardrail tests:** dangling `exclusive_flags` / `primaryKey` /
  `foreignKeys` references; empty `enum`; `qa:` check on an inapplicable declared type.
- **Golden profile-emission test:** committed `science-data-resource-v1.json` byte-equals
  `model_json_schema(by_alias=True)` serialized per the determinism contract.
- **`datasets validate` integration test:** a real fixture datapackage with a rich resource
  schema validates clean; a deliberately broken one yields the expected `fail` rows; a legacy
  name/type-only resource still validates (additive, non-breaking).

## 11. Open questions / risks

- **`minimum/maximum` severity shift (decided: structural).** Spec 2 must implement the new
  mapping; any existing data with declared bounds it violates will newly fail structurally —
  intended, but worth surfacing during the Spec 2 rollout.
- **`missingValues` semantics.** Spec 1 models it as the native parsing directive only;
  heuristic *undeclared-sentinel detection* (a distribution smell) is deferred.
- **Profile versioning.** Only `v1` exists. A future `v2` adds a new Literal value + a second
  committed profile file; the version marker selects the model. No migration machinery in Spec 1.

## 12. Next steps

1. User reviews this spec.
2. `writing-plans` → TDD implementation plan for Spec 1.
3. Implement on a feature branch created off local `main` (kept clear of the unrelated
   `feat/review-books` working state), via subagent-driven development.
4. Spec 2 (schema→checks compiler + generic-`tabular` program) follows.

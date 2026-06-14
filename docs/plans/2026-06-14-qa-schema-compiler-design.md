# Schema→Checks Compiler + Generic `tabular` Program — Design (Spec 2)

**Status:** approved design (2026-06-14). Second of the three-spec schema-driven-QA
decomposition. Spec 1 (typed Data Resource schema) shipped 2026-06-13 (local `main`
`5a4b6168`). Spec 3 (unification: dedupe `datasets validate` ↔ QA, backfill schemas,
retire hand-written qa-config) remains future work.

**Goal:** Let `science_qa` run directly off a Frictionless `datapackage.json` by
compiling a resource's typed Table Schema (the Spec 1 contract) plus its `qa:`
distribution extension into the existing `QAConfig`, and ship a generic `tabular`
program so QA runs usefully on ordinary tables without the false build-fatal flags
that the single scRNA program produces on non-scRNA data (the 2026-06-13 dogfood
finding).

**Non-goals (deferred):** `pattern` constraints; richer per-dtype type conformance;
Spec 3 unification. `science_qa` and `science_tool` remain non-importing.

---

## 1. Architecture & data flow

A new plain-dict module `science_qa/compile.py` reads a Frictionless resource
descriptor (parsed from `datapackage.json` as an ordinary `dict`) and produces a
`QAConfig` — the very dataclass the YAML path already yields. No pydantic; the QA
distribution stays `pandas`/`pyarrow`/`pyyaml`-only. The on-disk schema is the single
source of truth, consumed at run time; nothing is pre-generated to a derived artifact.

```
datapackage.json  {resources: [{name, path, schema: {fields, qa, ...}}]}
        │  compile.py: schema_to_config(resource, package_dir, package) → QAConfig   (contract checks)
        │  optional qa.yaml: QAConfig.from_file(...)                     → QAConfig   (run-knobs)
        ▼                                                                   │
            merge_configs(contract, runknobs) ──────────────────────────────┘
        ▼
  resolve_program(merged.program or "tabular") + merged QAConfig
        ▼
  existing runner (run_qa internals) → flags / coverage / qa_report.{json,md}
```

The compiler's output is *only* a `QAConfig`. Everything downstream — program
resolution, family expansion, invocation running, coverage, dispositions, reporting,
exit codes — is the existing, unchanged runner.

## 2. The generic `tabular` program

A new hand-declared `Program` named `tabular`, bound to `TableContext`, composed of
the `general` + `tabular` + `numeric-column` aspects **only**. It deliberately omits
the `gene-expression-qc-table` and `scrna-qc-table` required-column checks — those
`required_column`/`gates` checks are exactly what make every non-scRNA table trip
build-fatal structural flags today.

It declares every family/required slot the compiler can fill:

- `general/non_empty` (required), `general/missing_fraction` (required, threshold via run-knob)
- `tabular/unique_key` (family), `tabular/required_complete` (family),
  `tabular/categoricals` (family), `tabular/exclusive_flags` (family),
  `tabular/type_conformance` (family)
- `numeric-column/bounds` (family, **new**, structural),
  `numeric-column/range` (family, distribution — run-knob only),
  `numeric-column/polarity` (family, run-knob only),
  `numeric-column/zero_fraction` (required, selector `dtype: numeric`, distribution),
  `numeric-column/low_variance` (required, selector `dtype: numeric`, distribution),
  `numeric-column/missing_sentinel` (family, selector `dtype: numeric`)

Registered in `PROGRAMS` alongside `scrna-qc-table`. The static program↔substrate
check in the runner is satisfied because every aspect fn accepts `TableContext`.

## 3. The compiler mapping (schema → QAConfig)

`schema_to_config(resource: dict, package_dir: Path, package: dict) -> QAConfig`.
`resource["schema"]` is the Spec 1 Table Schema; `resource["schema"].get("qa", {})`
is the table-level `qa:` extension. Field-level constraints live under each
`schema["fields"][i]` as `type`, `constraints`, and `qa`.

### Native constraints → **structural** checks

| Schema element | QAConfig field | Check |
|---|---|---|
| field `constraints.required: true` | `required_complete += [name]` | `tabular/required_complete` |
| field `constraints.unique: true`; table `primaryKey`; table `uniqueKeys[*]` | `unique_key` invocation(s) (composite-aware, §6) | `tabular/unique_key` |
| field `type` → `"numeric"` if `integer`/`number` else `"non-numeric"` | `expected_types[name]` | `tabular/type_conformance` |

> **`type: any` produces no entry.** Spec 1 defaults an omitted `type` to `any`. A field
> typed `any` (or absent) carries no type assertion, so the compiler emits **no**
> `expected_types` entry for it — only a committed `integer`/`number`/non-numeric type
> compiles to a conformance check.
| field `constraints.minimum`/`maximum`/`exclusiveMinimum`/`exclusiveMaximum` | `bounds[name] = {present keys}` | `numeric-column/bounds` (new) |
| field `constraints.enum` | `categoricals[name] = {"allowed": [...]}` | `tabular/categoricals` |
| table `missingValues` (normalized; minus the empty-string default) | `missing_sentinels = [...]` | `numeric-column/missing_sentinel` |

> **Normalize object entries.** Spec 1 allows each `missingValues` entry to be a bare
> string *or* an object `{"value": …, "label": …}`. Read as plain JSON, the compiler maps
> each entry to its sentinel value (`entry` if a string, else `entry["value"]`) and drops
> only the empty-string sentinel (Spec 1's default), passing the rest into
> `missing_sentinels`.
| table `foreignKeys[*]` (**single-column only**) | `categoricals[localfield] = {"allowed_from": "<target path>#<ref field>"}` | `tabular/categoricals` |

> **Composite FKs are rejected, not weakened.** Spec 1 accepts `fields: str | list[str]`,
> but `tabular/categoricals` loads exactly one target column and tests per-column
> membership — a composite FK compiled to single-column `allowed_from` would test each
> column independently and pass invalid tuples. A FK whose `fields`/`reference.fields`
> has length > 1 → `CompileError` (exit 2). Tuple-aware FK checking is deferred.

### `qa:` extension → **distribution** checks

| Schema element | Check | Note |
|---|---|---|
| table `qa.exclusive_flags` | `tabular/exclusive_flags` | severity stays **structural** (its current behavior; the `qa:` zone is about authoring locus, not a severity change — see §7) |
| field `qa.low_variance` / `qa.zero_fraction` | `numeric-column/low_variance` / `zero_fraction` | **not separately compiled** — run blanket on all numeric columns by the program (§6) |

`polarity` is **not** schema-derived (no Frictionless field expresses sign
expectation); it is supplied only via `qa.yaml` and runs `numeric-column/polarity`.
`pattern` is unmapped (deferred). `constraints.minimum`/`maximum` bound *values* may be
numbers or ISO date/datetime strings — passed through verbatim into `bounds` params.

## 4. New `numeric-column/bounds` check (structural)

```python
def bounds(ctx: TableContext, params: dict) -> list[Flag]:
    """Hard structural bounds from native Frictionless constraints (Spec 1 invariants).

    params["bounds"] = subset of {minimum, maximum, exclusiveMinimum, exclusiveMaximum}.
    Emits one SEVERITY_STRUCTURAL Flag per violated bound (count of offending rows).
    Distinct from numeric-column/range (distribution soft-review band).
    """
```

- Coerces the column with `pd.to_numeric(..., errors="coerce")` when the bound is
  numeric; for ISO date/datetime bounds, coerces with `pd.to_datetime` and compares.
  If the *column* cannot be coerced to the bound's kind (e.g. a string column under a
  numeric bound), the aspect raises `RunnerError` (exit 2) — runtime fail-early, the same
  policy the runner already applies when a configured family names an unusable column.
  This is a **run-time** condition (it needs the table), distinct from the compile-time
  validation in §8 (which sees only the descriptor).
- `minimum`: values `< min` violate. `exclusiveMinimum`: values `<= xmin` violate.
  `maximum`: values `> max`. `exclusiveMaximum`: values `>= xmax`. One `Flag` per
  violated bound, `column` = field name, `qualifier` = the bound key, severity
  `SEVERITY_STRUCTURAL`.
- Expanded in `program.py` by `_expand_bounds(config)` → one `Invocation` per
  `config.bounds` entry, `requires=(col,)`, `params={"bounds": spec}`.

`QAConfig` gains one field: `bounds: dict[str, dict] = field(default_factory=dict)`.

## 5. Input / merge model & CLI

`run` gains `--datapackage P` and `--resource R` (a mutually-required pair),
preserving the existing `--config`/`--table` pair. Exactly one mode must be supplied.

- **Datapackage mode** (`--datapackage P --resource R`): load `P` (JSON), find the
  resource named `R`, derive the table path from `resource["path"]` relative to `P`'s
  directory, and `schema_to_config(resource, package_dir, package)`. Program defaults
  to `"tabular"`.
- **+ run-knobs** (`--config qa.yaml`, optional in datapackage mode): parse with a
  **program-optional loader** — `QAConfig.from_file` gains a `require_program: bool = True`
  parameter; datapackage mode calls it with `require_program=False` (a run-knobs yaml
  legitimately omits `program:`, since `tabular` is the default), while legacy mode keeps
  the default `True`. Then `merge_configs(contract, runknobs)`:
  - **Scalars** (`program`, `unique_key`): run-knob wins when set.
  - **List/dict contract fields** (`required_complete`, `bounds`, `categoricals`,
    `expected_types`, `exclusive_flags`, `missing_sentinels`): **union**, with run-knob
    entries overriding the schema on key collision (so an author can tighten/loosen a
    specific column).
  - **Run-knob-only fields** (`polarity`, `ranges`, `project_local`, `aspect_params`,
    `column_sets`): overlay directly (schema never sets these).
- **Legacy mode** (`--config qa.yaml --table T`): unchanged; `program` comes from the
  yaml (no implicit `tabular` default), exactly as today.

Supplying neither pair, both `--table` and `--datapackage`, or a `--config` whose
`program:` is required-but-absent in legacy mode → `UsageError` (exit 2). In
datapackage mode a `qa.yaml` with no `program:` is fine — `tabular` is the default.

## 6. Behavioral rules

- **Composite keys.** Extend `tabular/unique_key` to accept N columns and count
  duplicate row-tuples (`table[cols].duplicated().sum()`); single-column behavior is
  byte-identical to today. `_expand_unique_key` emits one `Invocation` for
  `constraints.unique` columns and for `primaryKey`, plus one per `uniqueKeys` group.
  `QAConfig` keeps the legacy scalar `unique_key: str | None` (back-compat for existing
  yaml + the scrna program) **and** gains `unique_keys: list[list[str]]` for the compiled
  composite path; `_expand_unique_key` emits one group for the scalar (when set) plus one
  per `unique_keys` group.
- **Type mapping.** Coarse numeric-vs-non-numeric only, matching the existing
  `type_conformance` check. Richer per-type (date/boolean/string) dtype checking is
  deferred.
- **FK resolution.** Single-column FKs only. `reference.resource` (or `""` ⇒ self)
  resolves to that resource's `path` within the same package; the `allowed_from` pointer
  is `"<that path>#<reference field>"`, consumed by the existing `tabular/categoricals`
  `allowed_from` machinery at run time. A composite FK (`len(fields) > 1`), or one whose
  target resource or field is absent → `CompileError` (exit 2, fail-early).
- **`low_variance` / `zero_fraction` = blanket (decided).** In `tabular` these run as
  required, selector-`dtype: numeric` checks over *all* numeric columns (the zero-config
  behavior the dogfood validated — it caught the real all-zero `is_dark` signal),
  distribution severity, low noise. The schema's per-field `qa.low_variance`/
  `qa.zero_fraction` are therefore **not separately compiled** for `tabular` (blanket
  already covers them); they remain meaningful for narrower programs.

## 7. Severity & coverage

Each mapping targets a check whose aspect already emits the intended severity, so the
structural/distribution split falls out without per-flag severity plumbing:

- **Structural:** `required_complete`, `unique_key`, `type_conformance`, `categoricals`,
  **`bounds`** (new), `missing_sentinel`.
- **Distribution:** `low_variance`, `zero_fraction`, `range`, `missing_fraction`.
- **`exclusive_flags` stays structural** (its current severity). It lives in the table
  `qa:` extension as an *authoring* convenience (co-located with the data contract), but
  that placement is about where it's declared, not a reclassification of its severity.
  Decided: do not silently change it.

Coverage (`ran`/`empty`/`blocked`/`not-applicable`, executable denominator, narrow-signal
readout) is produced by the normal runner and works unchanged, because the compiled
`QAConfig` flows through the same `run_qa` path.

## 8. Error handling (fail-early, explicit)

A new `CompileError` (caught by the CLI and surfaced as `UsageError` → exit 2, like
`QAConfigError`). These are all **descriptor-only** checks — the compiler never reads the
table:

- resource missing `schema` or `path`; resource `R` not found in the package
- FK target resource or reference field absent from the package; composite FK
  (`len(fields) > 1`)
- a bound *value* that is itself malformed — neither a number nor a parseable ISO
  date/datetime string

Run-time conditions that need the table are **not** `CompileError`s: a configured family
column absent from the table, or a column that cannot be coerced to a declared bound's
kind (§4), are raised by the runner/aspect as `RunnerError` (exit 2) — the existing
fail-early path.

A schema that is valid but carries no constraints/qa compiles to a near-empty
`QAConfig`; only `general/non_empty` (and the blanket numeric distribution checks, if
numeric columns exist) run — an honest zero-config minimum, never a crash.

## 9. File structure

| File | Change | Responsibility |
|---|---|---|
| `science/qa/src/science_qa/compile.py` | **create** | `schema_to_config`, `merge_configs`, `CompileError` |
| `science/qa/src/science_qa/config.py` | modify | add `bounds` + `unique_keys` fields; add `from_file(require_program: bool = True)` so datapackage-mode run-knobs may omit `program:` |
| `science/qa/src/science_qa/program.py` | modify | declare `tabular` Program; `_expand_bounds`; composite `_expand_unique_key` |
| `science/qa/src/science_qa/aspects/numeric_column.py` | modify | add `bounds` check fn |
| `science/qa/src/science_qa/aspects/tabular.py` | modify | composite-aware `unique_key` |
| `science/qa/src/science_qa/cli.py` | modify | `--datapackage`/`--resource` mode + mode validation |
| `science/qa/src/science_qa/runner.py` | modify | accept a pre-built `QAConfig` (datapackage path) alongside `from_file` |

## 10. Testing strategy

- `tests/test_compile.py` (**new**): each mapping row (unit); composite key (PK + a
  `uniqueKeys` group); single-column FK→`allowed_from` resolution incl. self-ref;
  **composite-FK → `CompileError`**; missing-target-resource/field `CompileError`;
  **`missingValues` object-entry normalization to `.value` + empty-string drop**;
  malformed-bound-value `CompileError`; `merge_configs` precedence (scalar override, dict
  union, run-knob-only overlay); empty-schema → minimal config.
- `tests/test_config.py`: **`from_file(require_program=False)`** accepts a yaml with no
  `program:`; default `require_program=True` still raises.
- `tests/test_aspect_numeric_column.py`: `bounds` below/above/exclusive/temporal/clean;
  **uncoercible column → `RunnerError`**.
- `tests/test_program.py`: `tabular` registration, substrate, and that it carries no
  gene-expression/scrna required-column checks.
- `tests/test_cli_run.py` / `tests/test_runner.py`: end-to-end `--datapackage/--resource`
  (zero-config and with-yaml overlay); a **non-scRNA** table runs green (no false
  build-fatal flags — the dogfood regression, now fixed); mode-validation `UsageError`s.

## 11. Scope boundaries (deferred to later specs)

`pattern` checks; richer per-dtype type conformance; Spec 3 unification (dedupe
`science datasets validate`'s descriptor pass against the QA contract, backfill real
datapackages with schemas, retire hand-written qa-config columns). `science_qa` and
`science_tool` remain non-importing.

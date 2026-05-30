# Dataset `license` as a first-class checkable property (+ `tier`/`update_cadence` validation)

- **Date:** 2026-05-30
- **Status:** design (approved, pre-implementation)
- **Branch:** `feat/dataset-license-metadata-validation`
- **Origin:** Surfaced from a `science health` triage in the `meta` project — a dataset
  note carried an `[UNVERIFIED]` license, prompting the question "is `license` even a
  field, and is it validated?" It is neither captured nor validated today.

## Problem

The dataset authoring surface declares a `license` field, but it never reaches the
graph and is never checked. Two distinct failure modes are in play:

1. **Vestigial field (silent data loss).** `Entity` is a Pydantic model with the
   default `extra="ignore"`, so any frontmatter key absent from the Python model is
   silently dropped at load. `license` is declared in the template
   (`model/src/science_model/templates/dataset.md:9` — `license: "" # SPDX identifier
   or "unknown"`) and the entity JSON schema
   (`model/src/science_model/schemas/science-pkg-entity-1.0.json:19`), but it is **not**
   a field on `Entity` or `DatasetEntity` (`model/src/science_model/entities.py`) and
   is **not** in the datapackage adapter's `_ENTITY_FIELDS` allow-list
   (`src/science_tool/graph/storage_adapters/datapackage.py:15`). A `license:` the
   author writes is therefore captured nowhere.

2. **Modeled-but-unvalidated fields.** `tier` and `update_cadence` *are* on
   `DatasetEntity` (`entities.py:590-591`) as plain `str`, so they are captured — but
   no `validate/checks/` rule enforces their vocabulary. Any string passes.

This design fixes `license` (failure mode 1) and adds vocabulary checks for `license`,
`tier`, and `update_cadence` (failure mode 2), as one cohesive "dataset metadata
validation" unit.

### Scope

In scope: `license`, `tier`, `update_cadence` on `kind: dataset` entities.

Out of scope (flagged for a future effort, not built here):

- `profiles` (plural) vestigial gap on **all** entities — template writes a list
  (`profiles: ["science-pkg-entity-1.0"]`) but the model only has singular
  `profile: str`. Needs confirmation it isn't intentional before touching.
- Wider unvalidated fields across other kinds: `status` enum, `doi`/`pmid` format on
  papers, ISO-date format on `created`/`updated`/`access.last_reviewed`,
  reference-prefix format on `parent_dataset`/`siblings`/`related`, and
  `evidence_role`/`dispute_scope` enums on evidence-lines.

## Approach

**Capture-in-model + check-in-validation-layer.** Add the missing field to the model
so it is *captured* (fixing the silent drop), but enforce the vocabulary in a
`validate/checks` rule that emits **warnings** — not via a Pydantic `Literal`.

Rejected alternative — `Literal` on the model: a bad value would become a hard
Pydantic load error that crashes `science health` / `graph build` for the entire
project (the same class of whole-run crash the toolkit has already been bitten by).
The existing dataset checks (`source_class`, `derived_kind`, `dataset_usage` in
`validate/checks/dataset_taxonomy.py`) already follow the check-layer pattern and
read **raw frontmatter** via the `dataset_frontmatters` helper precisely so a
malformed entity cannot crash the strict loader. This design matches that pattern.

This means the model field and the check serve complementary purposes:

- Model field + adapter extraction → `license` becomes a first-class, queryable,
  materialized graph property.
- Check (over raw frontmatter) → friendly, non-fatal vocabulary warnings.

## Design

### 1. Data model + extraction

- `model/src/science_model/entities.py`: add `license: str = ""` to `DatasetEntity`
  (beside `tier`, `update_cadence`). This alone makes markdown-authored datasets
  capture it (the strict loader will now keep the key instead of dropping it).
- `src/science_tool/graph/storage_adapters/datapackage.py`: add `"license"` to
  `_ENTITY_FIELDS` so datapackage-sourced datasets carry it into the graph too.
- `tier` / `update_cadence` already exist on the model — no model change, checks only.

### 2. License vocabulary (new module)

`model/src/science_model/licenses.py`:

- `KNOWN_LICENSES: frozenset[str]` — a curated, SPDX-aligned set relevant to research
  data: `CC-BY-4.0`, `CC-BY-SA-4.0`, `CC-BY-NC-4.0`, `CC0-1.0`, `ODbL-1.0`,
  `ODC-BY-1.0`, `PDDL-1.0`, `MIT`, `Apache-2.0`, `BSD-3-Clause`, `GPL-3.0-only`,
  `LGPL-3.0-only`.
- `LICENSE_SENTINELS: frozenset[str]` — `{"unknown", "proprietary", "custom"}`.
  Sentinels record an honest non-license state and satisfy presence (consistent with
  the project's `[UNVERIFIED]` philosophy: state the gap rather than fake a value).
- `suggest(value: str) -> str | None` — closest known identifier for a "did you mean"
  hint (case-insensitive / small-edit-distance match against `KNOWN_LICENSES`).

One file, deliberately easy to extend. Project-level extensibility (per-project extra
licenses) is explicitly a future enhancement, not built here.

### 3. Validation checks (new `validate/checks/dataset_metadata.py`)

Follows `dataset_taxonomy.py`: a pure `evaluate_dataset_metadata(datasets)` core that
takes raw frontmatter dicts (each carrying `_path`), wrapped by a `@Check`-decorated
function that feeds it `dataset_frontmatters(ctx)`. Only `kind`/`type == "dataset"`
rows are considered.

Rules (all `WARN`, never `ERROR` — nothing blocks `validate` by default; the
`--fail-on` ladder can promote later if desired):

- **`dataset.license-missing`** — `origin == "external"` and `license` is empty/absent.
  Derived datasets (`origin == "derived"`) are exempt (license inherits from inputs).
- **`dataset.license-unrecognized`** — `license` present and not in
  `KNOWN_LICENSES ∪ LICENSE_SENTINELS`. Message includes `suggest()` output when
  available ("did you mean `CC-BY-4.0`?").
- **`dataset.tier-unrecognized`** — `tier` present and not in
  `{use-now, evaluate-next, track}`.
- **`dataset.cadence-unrecognized`** — `update_cadence` present and not in the
  *recommended* set `{static, rolling, daily, weekly, monthly, quarterly, annual,
  irregular}`. Soft by design: the template defines `update_cadence` as open-ended
  (`static | rolling | monthly | ...`), so this is a recommendation nudge, kept
  trivially extensible, not a closed enum.

Empty/absent `tier` and `update_cadence` are **not** flagged (optional metadata);
only a *present, unrecognized* value warns. `license` is the only one with a
missing-value warning, and only for external datasets.

### 4. Health surfacing

`science health` already sources its `validation` array from the validate checks, so
the new rules appear automatically (exactly as `code.ghost` did) and
`science validate --verbose` lists per-file locations. No bespoke health plumbing.

### 5. Testing

- **Vocabulary unit tests**: membership, sentinel handling, and `suggest()` behaviour
  (e.g. `cc-by-4.0` / `CC_BY_4.0` → suggests `CC-BY-4.0`; gibberish → `None`).
- **Check-function tests** over fixture raw-frontmatter dicts:
  external + missing license → `license-missing`; derived + missing → no warning;
  valid id → clean; `unknown` sentinel → clean; unrecognized id → `license-unrecognized`
  with suggestion; bad `tier` → `tier-unrecognized`; odd `update_cadence` → soft warn;
  absent `tier`/`cadence` → clean.
- **Regression test (guards the vestigial bug)**: parse a dataset markdown with a
  `license:` value through the model and assert the field survives onto the
  `DatasetEntity` (would have been silently dropped before this change).

### 6. Backward compatibility / migration

No data migration. Existing external datasets with an empty `license` will begin
emitting a `dataset.license-missing` warning — the intended nudge. No errors, nothing
blocks. Authors clear it by setting a real license or an explicit sentinel
(`unknown`/`proprietary`/`custom`).

## Files touched (summary)

| File | Change |
|---|---|
| `model/src/science_model/entities.py` | add `license: str = ""` to `DatasetEntity` |
| `model/src/science_model/licenses.py` | **new** — `KNOWN_LICENSES`, `LICENSE_SENTINELS`, `suggest()` |
| `src/science_tool/graph/storage_adapters/datapackage.py` | add `"license"` to `_ENTITY_FIELDS` |
| `src/science_tool/validate/checks/dataset_metadata.py` | **new** — license/tier/cadence checks |
| `model/src/science_model/templates/dataset.md` | (minor) note sentinels in the `license` comment |
| tests | vocabulary, check-function, and parse-regression tests |

## Success criteria

- A dataset markdown with `license: CC-BY-4.0` round-trips: the value is on the parsed
  `DatasetEntity` and is materialized into `graph.trig`.
- `science validate` / `science health` warn on: external dataset with no license,
  unrecognized license (with suggestion), unrecognized `tier`, unrecognized
  `update_cadence`.
- `unknown`/`proprietary`/`custom` clear the missing-license warning without being
  flagged as unrecognized.
- No new `ERROR`s; no path can crash the loader on a malformed value.
- New + existing test suites green.

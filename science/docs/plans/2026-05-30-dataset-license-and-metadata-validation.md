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

- **Capturing/materializing `tier` and `update_cadence`.** They are validated here
  (raw-frontmatter check) but remain on `DatasetEntity` only and are not threaded into
  the markdown parse path, so they are neither reliably captured on the parse-path
  `Entity` nor materialized. Promoting them to `Entity` + threading + emitting
  `sci:tier`/`sci:updateCadence` is a separate consistency fix, deliberately deferred.
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

- `Entity` field + frontmatter threading + adapter extraction + explicit
  materialization + predicate registration → `license` becomes a first-class,
  queryable, materialized graph property (see §1 — capture, materialization, and
  query-registration are three separate steps, none implied by the others).
- Check (over raw frontmatter) → friendly, non-fatal vocabulary warnings.

## Design

### 1. Data model + extraction

**`license` must live on `Entity`, not `DatasetEntity`.** The markdown parse path
(`parse_entity_file`, `model/src/science_model/frontmatter.py:404`) returns a plain
`Entity(**entity_kwargs)` for datasets — it never constructs `DatasetEntity`. This is
deliberate and documented: the existing dataset field `source_class` lives on `Entity`
(gated to `kind == "dataset"`) "so it also covers the parse_entity_file path"
(`entities.py:265-268`). `DatasetEntity` is used only on the typed/graph-load path, not
the markdown parse. So a `license` added only to `DatasetEntity` would be silently
dropped (Entity is `extra="ignore"`) for every markdown-authored dataset — and the §5
regression test would fail. Concretely:

- `model/src/science_model/entities.py`: add `license: str = ""` to **`Entity`**
  (alongside `source_class` and the other dataset-unification fields). `DatasetEntity`
  inherits it; no separate field there.
- `model/src/science_model/frontmatter.py`: thread it into the `entity_kwargs` dict
  (built ~line 331), i.e. `"license": fm.get("license", "")`, mirroring how
  `source_class` is threaded (~line 371).
- `src/science_tool/graph/storage_adapters/datapackage.py`: add `"license"` to
  `_ENTITY_FIELDS` so datapackage-sourced datasets carry it into the graph too.

`tier` / `update_cadence` get **validation only** (the check reads raw frontmatter, so
their model placement is irrelevant to it). They are *not* moved or materialized here:
they currently live on `DatasetEntity` only and are likewise absent from the parse-path
`Entity` and from `entity_kwargs`, so emitting `sci:tier`/`sci:updateCadence` from
`_add_entity` would read attributes that don't exist on the object materialization
actually sees. Making them captured+materialized is a separate consistency fix, noted
in *Out of scope*.

**Capture is not materialization.** Adding the `Entity` field makes `license`
available on the parsed entity, but it does **not** put it in `graph.trig`:
`materialize.py`'s `_add_entity` emits only a hand-picked predicate set, and for
datasets it currently stops at `sci:sourceClass`
(`src/science_tool/graph/materialize.py:240-241`). To meet the "first-class,
queryable" goal we emit it explicitly:

- `src/science_tool/graph/materialize.py`: in `_add_entity`, inside the existing
  `entity.kind == "dataset"` block, emit `sci:license` when present. A graph-assertion
  test must confirm the triple lands.
- `src/science_tool/graph/store/constants.py`: register `sci:license` as a first-class
  query predicate — add `SCI_NS.license` to `GRAPH_EXPORT_EDGE_METADATA_PREDICATES`
  (beside `SCI_NS.sourceClass`) so graph export does not misclassify the literal
  metadata as an edge, and add a `PREDICATE_REGISTRY` entry with description/layer
  (beside the `sci:sourceClass` entry) so it shows up in `science graph predicates`.
  A test asserts both registrations.

### 1a. Schema + template synchronization

`license` is already declared on the legacy entity-schema surface
(`science-pkg-entity-1.0.json:19`, `license: {"type": "string"}`) and in both dataset
templates, but is **absent** from the mixin-profile surface. Both surfaces must agree:

- `model/src/science_model/schemas/mixin-dataset-1.0.json`: add
  `"license": {"type": "string"}` (the `schema_profile:
  science-entity-base/1.0+dataset/1.0` validator uses this file; it currently has
  `tier` and `update_cadence` but no `license`, so a first-class `license` would be
  undeclared there).
- Dataset templates — **two byte-identical copies** exist and a quick search found no
  generator that produces one from the other, so both are hand-maintained and both
  must be updated: `model/src/science_model/templates/dataset.md` (packaged) and
  `templates/dataset.md` at the workspace root (the shared dir referenced by project
  `AGENTS.md` files as `../templates/`). Update the `license` comment to mention the
  sentinels in both. **Implementation note:** confirm during the plan whether a
  generation/sync step exists; if one is found, regenerate rather than hand-editing
  both.

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
  `{use-now, evaluate-next, track}` (matches both schema surfaces).
- **`dataset.cadence-unrecognized`** — `update_cadence` present and not in
  `{static, rolling, monthly, quarterly, annual, versioned-releases}`.

**The cadence set must equal the schema enum, not a separately-invented set.** The
authoritative closed enum is in `science-pkg-entity-1.0.json:20`
(`["", "static", "rolling", "monthly", "quarterly", "annual",
"versioned-releases"]`). The dataset template's comment (`static | rolling | monthly |
...`) reads as open-ended, but the schema is what actually enforces, and it is closed.
An earlier draft of this plan invented `daily`/`weekly`/`irregular` and dropped
`versioned-releases` — that would make a dataset pass this check yet fail schema
validation (and vice versa). To prevent that divergence, the check's allowed-cadence
constant is defined to equal the schema enum (minus `""`), and a **sync test**
(see §5) loads the schema JSON and asserts equality. If the cadence vocabulary should
genuinely grow (e.g. add `daily`), the schema enum is updated first and the check
follows — never the reverse.

Empty/absent `tier` and `update_cadence` are **not** flagged (optional metadata);
only a *present, unrecognized* value warns. `license` is the only one with a
missing-value warning, and only for external datasets.

**Registration (required — checks are not auto-discovered).** A `@Check`-decorated
function only runs if its module is imported, and the canonical import list is a
hard-coded tuple in `_load_canonical_checks`
(`src/science_tool/validate/checks/__init__.py:42`). The new `dataset_metadata`
module **must be added to that tuple** (next to `dataset_taxonomy`), or it silently
never runs. This is covered by the integration test in §5.

### 4. Health surfacing

Once the module is registered (§3), `science health` sources its `validation` array
from the validate checks, so the new rules appear in health output (exactly as
`code.ghost` did) and `science validate --verbose` lists per-file locations. No
bespoke health plumbing — but the surfacing is contingent on registration, not
automatic from file creation alone.

### 5. Testing

- **Vocabulary unit tests**: membership, sentinel handling, and `suggest()` behaviour
  (e.g. `cc-by-4.0` / `CC_BY_4.0` → suggests `CC-BY-4.0`; gibberish → `None`).
- **Check-function tests** over fixture raw-frontmatter dicts:
  external + missing license → `license-missing`; derived + missing → no warning;
  valid id → clean; `unknown` sentinel → clean; unrecognized id → `license-unrecognized`
  with suggestion; bad `tier` → `tier-unrecognized`; unrecognized `update_cadence` →
  `cadence-unrecognized`; `versioned-releases` → clean; absent `tier`/`cadence` → clean.
- **Registration / integration test**: run the full check suite through `runner.run`
  (or `science health`) on a fixture project and assert a `dataset_metadata` finding
  appears — proves the module is wired into `_load_canonical_checks`, not just that
  the pure core works in isolation.
- **Datapackage-extraction test**: load a `science-pkg-entity-1.0` datapackage source
  with a `license` through `DatapackageAdapter` and assert `license` survives into the
  entity — guards the `_ENTITY_FIELDS` allow-list change independently of the markdown
  path. (May be folded into the materialization test by sourcing the fixture dataset
  from a datapackage rather than markdown.)
- **Graph-materialization test**: materialize a fixture dataset with
  `license: CC-BY-4.0` and assert the `sci:license` triple is present in the emitted
  graph — guards the capture-vs-materialization gap.
- **Predicate-registry test**: assert `sci:license` is visible via
  `science graph predicates` (i.e. registered in `PREDICATE_REGISTRY` + allow-list).
- **Schema-sync test**: load `science-pkg-entity-1.0.json` and assert the check's
  allowed-cadence constant equals its `update_cadence` enum (minus `""`), and that
  `tier` agrees across the check and both schema surfaces — prevents vocabulary drift.
- **Regression test (guards the vestigial bug)**: parse a dataset markdown with a
  `license:` value through `parse_entity_file` and assert the field survives onto the
  returned `Entity` (would have been silently dropped before this change — and would
  still drop if `license` were added only to `DatasetEntity`).

### 6. Backward compatibility / migration

No data migration. Existing external datasets with an empty `license` will begin
emitting a `dataset.license-missing` warning — the intended nudge. No errors, nothing
blocks. Authors clear it by setting a real license or an explicit sentinel
(`unknown`/`proprietary`/`custom`).

## Files touched (summary)

| File | Change |
|---|---|
| `model/src/science_model/entities.py` | add `license: str = ""` to **`Entity`** (gated to datasets, like `source_class`) |
| `model/src/science_model/frontmatter.py` | thread `"license": fm.get("license", "")` into `entity_kwargs` |
| `model/src/science_model/licenses.py` | **new** — `KNOWN_LICENSES`, `LICENSE_SENTINELS`, `suggest()` |
| `src/science_tool/graph/storage_adapters/datapackage.py` | add `"license"` to `_ENTITY_FIELDS` |
| `src/science_tool/graph/materialize.py` | emit `sci:license` for datasets in `_add_entity` |
| `src/science_tool/graph/store/constants.py` | register `sci:license` in `PREDICATE_REGISTRY` + metadata allow-list |
| `src/science_tool/validate/checks/dataset_metadata.py` | **new** — license/tier/cadence checks |
| `src/science_tool/validate/checks/__init__.py` | register `dataset_metadata` in `_load_canonical_checks` |
| `model/src/science_model/schemas/mixin-dataset-1.0.json` | add `"license": {"type": "string"}` |
| `model/src/science_model/templates/dataset.md` | (minor) note sentinels in the `license` comment |
| `templates/dataset.md` (workspace root) | same comment update (byte-identical copy; confirm no generator) |
| tests | vocabulary, check-function, registration/integration, graph-materialization, schema-sync, and parse-regression tests |

## Success criteria

- A dataset markdown with `license: CC-BY-4.0` round-trips: the value is on the
  parsed `Entity` (via `parse_entity_file`) **and** a `sci:license` triple is present
  in `graph.trig` **and** `sci:license` is visible in `science graph predicates`.
- The check runs as part of the full suite (`runner.run` / `science health`), i.e. it
  is registered — not merely importable.
- `science validate` / `science health` warn on: external dataset with no license,
  unrecognized license (with suggestion), unrecognized `tier`, unrecognized
  `update_cadence`.
- `unknown`/`proprietary`/`custom` clear the missing-license warning without being
  flagged as unrecognized; `versioned-releases` is an accepted cadence.
- The check's cadence vocabulary equals the schema enum (sync test passes); no value
  passes the check while failing schema validation or vice versa.
- No new `ERROR`s; no path can crash the loader on a malformed value.
- New + existing test suites green.

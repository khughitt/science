# Phase D2: Commons inventory_v2 contract + inventory builder integration — design

**Parent design:** `docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` (§6.2 inventory contract v2, §2.1 resource projection)
**Predecessor:** `docs/plans/2026-05-14-commons-overlay-merge-design.md` (Phase D1 — merged)
**Status:** approved 2026-05-14
**Depends on:** Phase A (entity_schema layer — merged), Phase B (commons scaffolding — merged), Phase C (data resolver — merged), Phase D1 (overlay merge layer — merged)

---

## 1. Goal

Add the `inventory_v2` export contract and wire two producers to it — a new
commons-store inventory builder and v2 support in the existing project builder —
so the dashboard can consume the shared (commons) tier and overlay-merged views
without scanning files directly.

At the end of D2:

- `science commons inventory` emits one `inventory_v2` payload describing the
  whole commons store: every commons entity as `scope: "cross-project"`, with
  dataset resources projected into `InventoryEntity.data["resources"]`.
- `science entities inventory --schema-version 2` (the default) emits a v2
  project payload — the existing v1 content plus a new top-level `overlays[]`
  list describing the project's overlay files.
- `science entities inventory --schema-version 1` still emits the unchanged v1
  payload.
- `science_model.contracts.inventory_v2` is a sibling contract module that
  imports the unchanged v1 models and adds only what is new.

## 2. Scope decomposition

Parent §9 bundles "Phase D" as overlay merge **plus** `inventory_v2` and
inventory-builder integration. Phase D1 (merged) took the overlay merge layer.
D2 (this design) is the inventory half: the `inventory_v2` contract module and
its two producers.

D2 consumes D1's `OverlayAdapter` (to scan a project's overlay files) and Phase
B's `CommonsEntityAdapter` (to walk the commons store). It does **not** use D1's
`merge_entity` / `resolve_entity` — the inventory exports the *unmerged* pieces
(canonical commons entities in one payload, overlay projections in another) and
leaves the join to the consumer (§3.1).

## 3. Architecture

### 3.1 Key decision: standalone commons inventory, overlays on project payloads

Parent §6.2 says shared entities should "appear in the same `entities:` list" of
each project payload, distinguished by `scope: "cross-project"`. D2 **deviates**
from that literal reading. Commons entities live **only** in a standalone
commons inventory payload; project payloads carry **only** their own
`overlays[]`. Two reasons:

1. **Content-hash stability.** The contract has `content_hash` / `audit_hash`
   for change detection. Inlining commons entities into project payloads means
   editing one commons paper invalidates the `content_hash` of every project
   that overlays it — even though nothing about those projects changed. A
   payload's hash should reflect exactly its own subject.
2. **No duplication, no coverage gap.** "Inline only overlaid entities" yields N
   copies of each commons entity for consumers to dedup, and a commons entity no
   project overlays would appear nowhere. A standalone commons inventory carries
   each commons entity exactly once and covers the whole store.

The dashboard reconstructs a merged view by joining `overlays[]` entries (from
project payloads) to commons entities (from the commons payload) on
`overlay_of` == `InventoryEntity.id`. `InventoryEntity.scope` still earns its
keep: both payload kinds use the same `InventoryEntity` model and `entities[]`
list, so any consumer can read an entity's scope without knowing which payload
it came from.

### 3.2 Code layout

```
science/model/src/science_model/contracts/
├── inventory_v1.py     # UNCHANGED
└── inventory_v2.py     # NEW — InventoryOverlay, InventoryPayload (v2),
                        #       SCHEMA_VERSION="2", compute_content_hash /
                        #       compute_audit_hash / finalize (v2 variants)

science/src/science_tool/commons/
├── adapter.py          # MODIFY — scan() yields a CommonsEntityError per-entity
│                       #          instead of raising mid-walk (§3.6)
├── datapackage.py      # MODIFY — DataResource gains bytes/format/mediatype;
│                       #          read_datapackage captures them
├── inventory.py        # NEW — build_commons_inventory()
├── cli.py              # MODIFY — `science commons inventory` subcommand
└── __init__.py         # MODIFY — export build_commons_inventory

science/src/science_tool/
├── entities_inventory.py  # MODIFY — build_inventory gains schema_version param;
│                          #          v2 path scans overlays -> overlays[]
└── cli.py                 # MODIFY — `entities inventory --schema-version`
```

Approach A (chosen over a fully self-contained copy or a shared-core refactor):
`inventory_v2.py` imports the genuinely-unchanged v1 pieces and defines only
what is new. This makes **zero** changes to `inventory_v1.py` — no risk to the
existing strict v1 consumers and their tests — at the cost of one ~25-line
duplicated function (`_payload_for_content_hash`, which v1 cannot share because
it has no knowledge of `overlays`).

No new third-party dependencies.

### 3.3 Data flow — commons inventory

`build_commons_inventory()` → `resolve_commons_root()` →
`CommonsEntityAdapter(root).scan()` yields `CommonsEntityRecord | CommonsEntityError`
→ each record becomes an `InventoryEntity` (`scope="cross-project"`); for
datasets, `read_datapackage(record.datapackage_path)` projects resources into
`data["resources"]` → assemble a v2 `InventoryPayload` (`project_id="commons"`,
`overlays=[]`) → `finalize_inventory_payload`.

### 3.4 Data flow — project inventory v2

`build_inventory(project_root, schema_version="2")` → the existing v1 entity /
alias / dag-record / project-metadata assembly runs identically → additionally
`OverlayAdapter(project_root, project_id).scan()` yields
`OverlayRecord | OverlayValidationError` → records become `InventoryOverlay`s
(fields split by `read_overlay_merge_policy()`), errors become
`InventoryWarning`s → emit a v2 `InventoryPayload` with `overlays[]`.

The project builder needs only the project's own `doc/` tree and the overlay
schema bundled in `science_model` — **no commons-store access**. A project's v2
inventory builds even when the commons store is absent.

### 3.5 Dependency direction

`commons/inventory.py` imports from `commons.adapter`, `commons.config`,
`commons.datapackage`, and `science_model.contracts.inventory_v2` — no cycle.
`entities_inventory.py` adds imports of `commons.overlay` (`OverlayAdapter`) and
`science_model.entity_schema` (`read_overlay_merge_policy`) — no cycle
(`commons.overlay` does not import `entities_inventory`).

### 3.6 Phase B prerequisite: make `CommonsEntityAdapter.scan()` walk-safe

`CommonsEntityAdapter._scan_type` currently **raises** `CommonsLayoutError`
mid-generator (`science/src/science_tool/commons/adapter.py:74`) when a dataset
directory has `entity.md` but no `datapackage.yaml` sibling. A raised exception
aborts the generator, so the commons inventory build would lose every entity
discovered *after* the bad dataset — and the same raise crashes `commons
validate` and `commons index rebuild` today, since `CommonsValidator` and
`RegistryBuilder` iterate the same `scan()`.

D2 carries a small Phase B change: for that per-entity case `_scan_type`
**yields a `CommonsEntityError`** instead of raising. Crucially it yields the
*existing* `CommonsEntityError` type — not a new one, and not a bare
`CommonsLayoutError` — with its `cause` set to a `CommonsLayoutError`:

```python
yield CommonsEntityError(
    child,
    canonical_id=f"dataset:{child.name}",
    cause=CommonsLayoutError(
        child,
        reason="dataset directory missing required datapackage.yaml sibling",
    ),
)
```

Because the yielded item is a `CommonsEntityError`, **every existing `scan()`
consumer already handles it correctly with zero code change**:

- `scan()` / `_scan_type()` keep their return type
  `Iterator[CommonsEntityRecord | CommonsEntityError]` — no widening.
- `CommonsValidator.validate()` already routes `CommonsEntityError` items into
  `ValidationReport.errors`; `commons validate` / `validate --json` keep working
  (`CommonsEntityError` carries the `path` / `canonical_id` / `cause` the JSON
  path reads).
- `RegistryBuilder.rebuild()` already routes `CommonsEntityError` items into
  `RebuildReport.errors`; `commons index rebuild` / `index rebuild --json` keep
  working.
- `build_commons_inventory` (§6) discriminates the layout case from a schema
  failure by inspecting `item.cause`: `isinstance(item.cause,
  CommonsLayoutError)` → `commons-datapackage-invalid`, otherwise
  `commons-entity-invalid`.

`load()`'s own `raise CommonsLayoutError` path is untouched — `load` is a
single-id lookup where raising is correct. `CommonsLayoutError` remains a
distinct class (still raised by `load`, now also used as a `cause`); it is
simply never the top-level *yielded* item.

## 4. The `inventory_v2` contract module

`science/model/src/science_model/contracts/inventory_v2.py`.

### 4.1 Imports from v1

```python
from science_model.contracts.inventory_v1 import (
    InventoryAlias,
    InventoryEntity,
    InventoryFindingCandidate,
    InventoryGraphAddress,
    InventoryProjectMetadata,
    InventoryReference,
    InventorySourceLocation,
    InventoryWarning,
    _InventoryContractModel,
    _validate_json_value,
    canonical_json_bytes,
    _normalize_entity_for_content_hash,
    _normalize_project_for_content_hash,
    _normalize_finding_candidate_for_content_hash,
    _sort_key_with_canonical_tie_breaker,
)

SCHEMA_VERSION: Final = "2"
```

All v1 models except `InventoryPayload` are reused verbatim. The `_`-prefixed
helpers are module-internal to `inventory_v1` but are deliberately imported here
— D2's contract test asserts they remain importable so a future v1 refactor
that renames them fails loudly.

### 4.2 `InventoryOverlay`

```python
class InventoryOverlay(_InventoryContractModel):   # extra="forbid", strict
    overlay_of: str                       # canonical id of the commons entity
    project_id: str                       # owning project's inventory id
    source: InventorySourceLocation       # adapter="commons-overlay"
    pin_version: str | None = None
    pin_effective_version: str | None = None
    project_only_fields: dict[str, Any] = Field(default_factory=dict)
    append_fields: dict[str, Any] = Field(default_factory=dict)
    body_sections: list[str] = Field(default_factory=list)
```

- `overlay_of` gets a field validator mirroring
  `InventoryEntity.canonical_id_has_separator` — it must contain `:`.
- `project_only_fields` and `append_fields` each get a field validator running
  the imported `_validate_json_value` (the same guard `InventoryEntity.data`
  uses), so the payload stays JSON-serializable.
- `project_only_fields` — overlay frontmatter fields whose merge policy is
  `project_only` (or the unannotated `read_overlay_merge_policy()` default),
  carried as a `name -> value` map.
- `append_fields` — overlay frontmatter fields whose merge policy is `append`
  (e.g. `tags`, `ontology_terms`), carried as a `name -> value` map. The value
  is the overlay's contribution; the consumer concatenates it onto the canonical
  field.
- `body_sections` — D1 treats an overlay body as one opaque string and does not
  split it on markdown headers. D2 follows suit: `body_sections` is
  `[overlay.body]` when the body is non-empty after `strip()`, else `[]`. The
  list shape honors the parent's field name and leaves header-splitting as a
  possible future refinement.

### 4.3 `InventoryPayload` (v2)

Mirrors v1 field-for-field with exactly two changes: `schema_version` is pinned
to `Literal["2"]` and a new `overlays` list is added.

```python
class InventoryPayload(_InventoryContractModel):
    schema_version: Literal["2"] = SCHEMA_VERSION
    generated_at: str
    project_id: str
    project_path: str | None = None
    project: InventoryProjectMetadata | None = None
    content_hash: str | None = None
    audit_hash: str | None = None
    entities: list[InventoryEntity] = Field(default_factory=list)
    aliases: list[InventoryAlias] = Field(default_factory=list)
    graph_addresses: list[InventoryGraphAddress] = Field(default_factory=list)
    finding_candidates: list[InventoryFindingCandidate] = Field(default_factory=list)
    warnings: list[InventoryWarning] = Field(default_factory=list)
    watch_paths: list[str] = Field(default_factory=list)
    overlays: list[InventoryOverlay] = Field(default_factory=list)   # NEW in v2
```

**Commons payload convention** (documented in the module docstring): the commons
inventory is an `InventoryPayload` with `project_id="commons"` (a fixed
sentinel — the commons store is not a project), `project=None`, `project_path`
set to the commons root, and `overlays=[]`. A project payload conversely always
has `entities` of `scope="project"` only and may have a non-empty `overlays`.

### 4.4 Hash machinery

v2 defines its own variants. `_payload_for_content_hash` reuses the imported
`_normalize_*` helpers for `entities` / `project` / `finding_candidates` exactly
as v1 does, and **additionally** sorts `overlays` by `(overlay_of, project_id)`
with the canonical-json tie-breaker. Within an overlay the dict fields are
key-sorted by `canonical_json_bytes`; `body_sections` and `append_fields` list
values are left in order (their order is content-meaningful).

`_payload_for_audit_hash` mirrors v1 and adds `overlays` to its drop set —
overlays are content, not audit metadata, so an overlay change must not move the
audit hash.

`compute_content_hash`, `compute_audit_hash`, and `finalize_inventory_payload`
are thin v2 wrappers over those two functions, structurally identical to v1's.

v1's `_payload_for_content_hash` cannot be reused directly: it pops a fixed key
set and never sorts `overlays`, so a v2 payload run through it would carry an
unsorted `overlays` list into the hash. v2 therefore owns its orchestration —
the one accepted duplication of Approach A.

## 5. Datapackage reader extension

`science/src/science_tool/commons/datapackage.py`. Additive — no behavior change
for existing callers (Phase C's resolver reads only `.path` / `.hash`).

```python
@dataclass(frozen=True, slots=True)
class DataResource:
    path: str
    hash: str
    bytes: int | None = None       # NEW — resources[].bytes if present
    format: str | None = None      # NEW — resources[].format if present
    mediatype: str | None = None   # NEW — resources[].mediatype if present
```

`read_datapackage` changes, applied after the existing `path` + `hash` parsing
for each resource:

- `bytes`: if present and not an `int`, or a `bool`, → `CommonsDatapackageError`
  naming the descriptor and the resource. Absent → `None`.
- `format`, `mediatype`: if present and not a `str` → `CommonsDatapackageError`.
  Absent → `None`.

These three are **optional in the reader**. Parent §3.2 marks `bytes` as
required "from v1", but requiredness is enforced by the commons `validate` path,
not the inventory reader — the reader must not reject an older datapackage that
predates the rule. Missing fields project as `null`.

The existing `path` / `hash` validation, duplicate-path detection, and all
existing error messages are untouched.

## 6. `build_commons_inventory()`

`science/src/science_tool/commons/inventory.py`.

```python
def build_commons_inventory() -> InventoryPayload:   # inventory_v2.InventoryPayload
```

1. `root = resolve_commons_root()`. If `not root.is_dir()` →
   `CommonsRootNotFoundError`.
2. Iterate `CommonsEntityAdapter(root).scan()` — yields
   `CommonsEntityRecord | CommonsEntityError`:
   - **`CommonsEntityError`** → an `InventoryWarning` with `severity="error"`,
     `message=str(err)`, `path=str(err.path)`, `canonical_id=err.canonical_id`.
     The `code` is chosen by the error's `cause`: `isinstance(err.cause,
     CommonsLayoutError)` (a dataset directory missing its `datapackage.yaml`
     sibling, per §3.6) → `code="commons-datapackage-invalid"`; otherwise (a
     schema or parse failure) → `code="commons-entity-invalid"`. A missing
     `datapackage.yaml` is conceptually a datapackage problem, so it shares the
     warning code with `read_datapackage` failures (step 3). The build does not
     abort — it mirrors the project builder's collect-warnings behavior.
   - **`CommonsEntityRecord`** → an `InventoryEntity`:
     - `id = record.canonical_id`, `kind = record.type`, `local_id = record.slug`
     - `title` / `status` from `record.frontmatter` (absent → `None`)
     - `scope = "cross-project"`
     - `registration_state = "unknown"` — the core / ontology / local axis does
       not apply to commons entities; `scope` carries the meaningful
       distinction.
     - `source = InventorySourceLocation(adapter="commons-entity",
       path=str(record.body_path))`
     - `aliases` from `record.frontmatter.get("aliases", [])`
     - `related` projected from `record.frontmatter["related"]` if present, each
       as `InventoryReference(relation="related", target_id=...)`
     - `data` = `record.frontmatter` minus the promoted keys (`id`, `type`,
       `title`, `status`, `aliases`, `related`) — so `schema_profile`,
       `version`, `created`, `updated`, `tags`, `ontology_terms`, etc. all land
       in `data`.
3. **Dataset resource projection.** When `record.type == "dataset"` and
   `record.datapackage_path is not None`, call
   `read_datapackage(record.datapackage_path)` and set `data["resources"]` to a
   list of `{path, hash, bytes, format, mediatype}` dicts (each key always
   present; absent Frictionless fields are `null`). A `CommonsDatapackageError`
   here → `InventoryWarning(code="commons-datapackage-invalid",
   severity="error", ...)`; the entity is still emitted, just without
   `data["resources"]`.
4. Assemble the v2 `InventoryPayload`:
   - `schema_version="2"`,
     `generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")`
   - `project_id="commons"`, `project=None`, `project_path=str(root)`
   - `entities` sorted by `id`
   - `aliases` collected from any entity `aliases` (sorted by `alias`)
   - `overlays=[]`
   - `watch_paths` = the type subdirectories (`datasets`, `papers`, `topics`,
     `themes`) that exist under `root`
   - `warnings` collected in steps 2–3
   - `graph_addresses` / `finding_candidates` stay empty
5. Return `finalize_inventory_payload(payload)`.

`build_commons_inventory` does no printing — warnings ride in the payload.

## 7. Project builder v2 integration

`science/src/science_tool/entities_inventory.py`.

```python
def build_inventory(
    project_root: Path, schema_version: Literal["1", "2"] = "2"
) -> inventory_v1.InventoryPayload | inventory_v2.InventoryPayload:
```

- **`schema_version == "1"`** → current behavior, unchanged, returns the v1
  payload. No overlay scan.
- **`schema_version == "2"`** → all existing v1 assembly (entities, aliases, dag
  records, project metadata, warnings, watch_paths) runs **identically**, then:
  1. `OverlayAdapter(project_root, project_metadata.id).scan()` — yields
     `OverlayRecord | OverlayValidationError`. Needs only the project's `doc/`
     tree; no commons-store access.
  2. `OverlayValidationError` → `InventoryWarning(code="overlay-invalid",
     severity="error", message=str(err), path=str(err.overlay_path),
     canonical_id=err.canonical_id)` — appended to the same `warnings` list.
  3. `OverlayRecord` → `InventoryOverlay`:
     - `overlay_of = record.canonical_id`, `project_id = project_metadata.id`
     - `source = InventorySourceLocation(adapter="commons-overlay",
       path=str(record.overlay_path))`
     - `pin_version` / `pin_effective_version` carried verbatim
     - Field split: `policy = read_overlay_merge_policy()`; for each frontmatter
       key except `id` / `overlay_of` / `pin_version` /
       `pin_effective_version`, `policy.get(key) == MergePolicy.APPEND` →
       `append_fields[key]`, everything else (including
       `read_overlay_merge_policy`'s `PROJECT_ONLY` default for unannotated
       fields) → `project_only_fields[key]`.
     - `body_sections = [record.body] if record.body.strip() else []`
  4. Emit a v2 `InventoryPayload` with `overlays` sorted by
     `(overlay_of, project_id)`, finalized via v2's `finalize_inventory_payload`.

**Call-site impact.** The function default flips to `"2"`. Existing
`build_inventory` call sites and tests that assert the v1 payload shape are
updated to pass `schema_version="1"` explicitly. New imports:
`science_model.contracts.inventory_v2`, `OverlayAdapter` (from
`science_tool.commons.overlay`), `read_overlay_merge_policy` and `MergePolicy`
(from `science_model.entity_schema`).

## 8. CLI

### 8.1 `science commons inventory`

New subcommand in `science/src/science_tool/commons/cli.py`, mirroring the
`entities inventory` shape:

```
science commons inventory [--output FILE]
```

Calls `build_commons_inventory()`, renders `payload.model_dump_json(indent=2)`
plus a trailing newline, writes to `--output` or stdout. `CommonsError` (base of
`CommonsRootNotFoundError`) → `click.ClickException`. No stderr warning chatter —
warnings ride in the payload, same as `entities inventory`.

### 8.2 `science entities inventory --schema-version`

Modify `entities_inventory_command` in `science/src/science_tool/cli.py`:

```python
@click.option("--schema-version", type=click.Choice(["1", "2"]), default="2")
```

Passed straight through to `build_inventory(project_path,
schema_version=schema_version)`. Rendering is unchanged.

### 8.3 Public API

`science/src/science_tool/commons/__init__.py` — add `build_commons_inventory`
to `__all__` and the import block.

## 9. Error handling

D2 introduces **no new error classes**. The two builders never raise on a
per-entity, per-resource, or per-overlay problem — those become `InventoryWarning`
entries:

| Code | Raised by | Severity |
| --- | --- | --- |
| `commons-entity-invalid` | `scan` yields a `CommonsEntityError` whose `cause` is a schema/parse failure | error |
| `commons-datapackage-invalid` | `scan` yields a `CommonsEntityError` whose `cause` is a `CommonsLayoutError` (missing `datapackage.yaml`), **or** `read_datapackage` raises a `CommonsDatapackageError` for a sidecar | error |
| `overlay-invalid` | `OverlayAdapter.scan` yields an `OverlayValidationError` | error |

The §3.6 walk-safe change is what makes the `commons-datapackage-invalid` row's
first source non-fatal — without it, a missing `datapackage.yaml` would abort
the whole scan rather than producing a warning.

The only hard failure is pre-flight: `CommonsRootNotFoundError` from
`resolve_commons_root()` in the commons builder, surfaced by the CLI as a
`click.ClickException`. The contract models raise `pydantic.ValidationError` on
a malformed payload, which is a builder bug, not a user-facing path.

## 10. Testing

### 10.1 New test files

- `science/model/tests/test_inventory_contract_v2.py` — mirrors
  `test_inventory_contract_v1.py`:
  - `InventoryOverlay` validation: `overlay_of` must contain `:`;
    `project_only_fields` / `append_fields` reject non-JSON-serializable values;
    `extra="forbid"` rejects unknown keys.
  - `InventoryPayload` `schema_version` is pinned to `"2"`; `extra="forbid"`
    still enforced.
  - Hash machinery: identical payload → identical `content_hash` /
    `audit_hash`; reordering `overlays` → **same** `content_hash` (sorted); an
    overlay field change → **different** `content_hash`; an overlay change →
    **same** `audit_hash` (overlays dropped from audit).
  - `finalize_inventory_payload` populates both hashes.
  - The imported v1 helpers (`canonical_json_bytes`, `_normalize_*`,
    `_validate_json_value`) are importable — guards against a silent v1 rename.
- `science/tests/test_commons_inventory.py` — `build_commons_inventory()`:
  - Clean store → every entity has `scope="cross-project"`; a dataset entity
    carries `data["resources"]` with `bytes` / `format` / `mediatype`.
  - Malformed entity → `InventoryWarning` (`commons-entity-invalid`); build
    continues and still emits the valid entities.
  - Malformed `datapackage.yaml` → `InventoryWarning`
    (`commons-datapackage-invalid`); the dataset entity is emitted without
    `data["resources"]`.
  - Dataset directory missing its `datapackage.yaml` sibling → `InventoryWarning`
    (`commons-datapackage-invalid`); entities discovered after it are still
    emitted (proves the §3.6 walk-safe change).
  - Missing commons root → `CommonsRootNotFoundError`.
  - Payload `project_id == "commons"`, `project is None`, `overlays == []`.

### 10.2 Extended test files

- `science/tests/test_commons_adapter.py` — `CommonsEntityAdapter.scan` **yields**
  a `CommonsEntityError` (with a `CommonsLayoutError` `cause`) for a dataset
  directory missing `datapackage.yaml` (no longer raises), and continues to
  yield records for entities discovered after it.
- `science/tests/test_commons_cli.py` — regression coverage that the §3.6 change
  needs no consumer code change: `commons index rebuild --json` and `commons
  validate --json` each report a dataset missing `datapackage.yaml` as an error
  item (exit 1) rather than crashing.
- `science/tests/test_commons_datapackage.py` — `read_datapackage` captures
  `bytes` / `format` / `mediatype`; non-int (or `bool`) `bytes` and non-str
  `format` / `mediatype` → `CommonsDatapackageError`; absent → `None`; existing
  `path` / `hash` cases untouched.
- `science/tests/test_entities_inventory.py` — `build_inventory(...,
  schema_version="2")` emits `overlays[]` with the correct project-only / append
  split and `body_sections`; an `OverlayValidationError` → `InventoryWarning`
  (`overlay-invalid`); `schema_version="1"` returns the unchanged v1 payload.
  Existing v1 assertions updated to pass `schema_version="1"` explicitly.
- `science/tests/test_commons_cli.py` — `science commons inventory` to stdout and
  to `--output FILE`; missing commons root → exit 1.
- The CLI test covering `entities inventory` — `--schema-version 1` vs `2`
  selects the payload shape; the default is `2`.

### 10.3 Fixtures

- Reuse the Phase B / C commons fixtures (`science/tests/fixtures/commons/valid/`,
  which already seeds `datasets/rnaseq-example/`, `datasets/cath-domains/`,
  papers, topics, themes) and D1's overlay fixtures
  (`science/tests/fixtures/overlays/proj-alpha/...`).
- Add `bytes` / `format` / `mediatype` to one dataset fixture's
  `datapackage.yaml` so resource projection has concrete values to assert.

### 10.4 Conventions

- TDD throughout; one commit per task.
- Test invocation: `cd ~/d/science/science && uv run pytest <path> -v`.
- Full `science` suite + the `science/model` suite green before D2 is done.

## 11. Follow-on phases

- **Dashboard pivot** (parent §6.4, parent §9.I) — migrate `~/d/dashboard/` from
  `inventory_v1` to `inventory_v2`, joining `overlays[]` to the commons
  inventory's entities. Sequenced after D2 and the 2026-05-12 inventory plan.
- **Phase E** — `science promote` + git tagging; activates `pin_version`
  resolution. D2 already carries `pin_version` / `pin_effective_version`
  verbatim on `InventoryOverlay`; nothing resolves them yet.
- **Drop v1** — once the dashboard and all downstream consumers are on v2,
  `inventory_v1` and the `--schema-version 1` path are removed.

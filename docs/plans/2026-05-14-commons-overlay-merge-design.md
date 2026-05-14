# Phase D1: Commons overlay merge layer — design

**Parent design:** `docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` (§5 Project overlays, §9 Phase D)
**Predecessor:** `docs/plans/2026-05-14-commons-data-resolver-design.md` (Phase C — merged)
**Status:** approved 2026-05-14
**Depends on:** Phase A (entity_schema layer — merged), Phase B (commons scaffolding — merged)

---

## 1. Goal

Add read-time project-overlay merge to `science_tool.commons`. A project carries
a thin overlay file for a commons entity; D1 merges the overlay's
project-specific fields and body sections onto the canonical entity per the
schema's `science:merge` policy.

At the end of D1:

- `science commons show <type>:<slug> --project <name>` prints the canonical
  entity with the project's overlay merged in.
- `science commons validate --project <name>` checks every overlay file in a
  registered project against the overlay schema and confirms each `overlay_of`
  resolves to a real canonical entity.
- A Python entry point `science_tool.commons.resolve_entity(canonical_id,
  project=None)` returns a `MergedEntity` for programmatic use.

## 2. Scope decomposition

Parent §9 bundles "Phase D" as overlay merge **plus** `inventory_v2` and
inventory-builder integration. These are independent subsystems: the overlay
merge layer is fully working, testable software on its own and never touches the
inventory contract. Phase D is therefore split:

- **D1 (this design)** — overlay merge layer inside `science_tool.commons`.
- **D2 (separate spec)** — `science_model.contracts.inventory_v2` + inventory
  builder integration. D2 consumes D1's `OverlayAdapter` and `merge_entity`, and
  lands closer to the dashboard pivot that is its real consumer.

## 3. Scope

### In scope
- `OverlayAdapter` — discover, parse, and validate overlay files in a registered
  project (`load` for a single id, `scan` for all overlays).
- `OverlayRecord` / `MergedEntity` dataclasses.
- Policy-driven `merge_entity()` — applies `science:merge` annotations
  generically.
- `resolve_entity(canonical_id, project=None)` — shared entry point for the CLI
  and the Python API.
- `validate_project_overlays(project)` — driver for `validate --project`.
- `resolve_project_root(name)` — registered-project-name → root path lookup.
- CLI: `science commons show --project` (replaces the Phase B rejection) and
  `science commons validate --project`.

### Out of scope (deferred)
- **Git `pin_version` resolution — Phase E.** D1 parses and validates the
  `pin_version` / `pin_effective_version` fields (the overlay schema already
  permits them), but the merge always uses the live working-tree canonical
  entity. When an overlay sets `pin_version`, the CLI prints a stderr warning
  that pinning is inactive until Phase E. Git tag resolution
  (`git show <type>/<slug>/<semver>:...`) lands in Phase E alongside the
  `science promote` flow that creates those tags — there is nothing to resolve
  against until tags exist.
- **`inventory_v2` contract + inventory builder integration — D2.**
- **SQLite overlay table.** Overlays are on-demand filesystem reads. There is no
  registry analogue for overlays in D1; a persisted overlay collection is a D2
  concern (the inventory contract is its consumer).
- **`science fork`, `science promote`, `.migrations/` writes — Phase E/F/G.**
- **`science find --project`.** Parent §6.3 scopes `--project` to `show` only.

## 4. Architecture

### 4.1 Code layout

```
science/src/science_tool/commons/
├── overlay.py        # NEW — OverlayAdapter, OverlayRecord, MergedEntity,
│                     #       OverlayValidationReport, merge_entity(),
│                     #       resolve_entity(), validate_project_overlays()
├── errors.py         # MODIFY — add ProjectNotRegisteredError,
│                     #          OverlayValidationError, OverlayMergeError
├── config.py         # MODIFY — add resolve_project_root(name)
├── cli.py            # MODIFY — show --project, validate --project
└── __init__.py       # MODIFY — export the new public surface
```

Approach A (single `overlay.py`): all overlay machinery is one cohesive unit.
The adapter feeds the merge feeds the resolver — they are tightly coupled and
evolve together. A separate `merge.py` was rejected because it collides by name
with `science_model.entity_schema.merge` (the policy *reader*).

No new third-party dependencies. Phase A's `science_model.entity_schema` already
provides everything the merge needs:

- `read_merge_policy(profile)` → `dict[str, MergePolicy]` for a canonical
  schema_profile.
- `read_overlay_merge_policy()` → `dict[str, MergePolicy]` for the overlay-only
  fields.
- `MergePolicy` enum: `REPLACE`, `APPEND`, `FORBIDDEN`, `PROJECT_ONLY`.
- `EntityValidator.validate_overlay(overlay)` — overlay schema validation plus
  the `id == overlay_of` check.

### 4.2 Overlay file location

```
<project_root>/doc/<type_plural>/<slug>.md
```

`type_plural` ∈ `{datasets, papers, topics, themes}` — uniform even for
datasets. The canonical dataset is a directory (`entity.md` + `datapackage.yaml`
sibling), but its overlay is always a single `.md` file. This mirrors the Phase B
`_TYPE_DIR_TO_TYPE` mapping.

A project simply not having an overlay for a given entity is **not an error** —
`OverlayAdapter.load` returns `None`, and the merge falls through to a
canonical-only result.

### 4.3 Discovery order for the project root

`--project <name>` resolves by **registered name only**:

1. Look up `name` in `load_global_config().projects` (matched on the `name`
   field).
2. Return `Path(project.path).expanduser()`.
3. No match → `ProjectNotRegisteredError` (carries the name).

`resolve_project_root` does not assert the path exists on disk. A registered
project whose directory is missing surfaces as "no overlay found" (`load`
returns `None`) or as an OS error wrapped in `CommonsError` (`scan`).

## 5. Components

### 5.1 `resolve_project_root` (`config.py`)

```python
def resolve_project_root(name: str) -> Path:
    """Look up a registered project by name; return its root path.

    Raises ProjectNotRegisteredError if no projects[] entry matches `name`.
    Does not check that the path exists on disk.
    """
```

Reads `load_global_config().projects` (a `list[RegisteredProject]`, each with
`name` and `path`). Lives in `config.py` next to `resolve_commons_root` /
`resolve_commons_data_root` — the commons-config resolver family.

### 5.2 `OverlayRecord` (`overlay.py`)

Frozen, `slots=True` — matches `CommonsEntityRecord` / `ResolvedDataResource`.

```python
@dataclass(frozen=True, slots=True)
class OverlayRecord:
    canonical_id: str               # from overlay_of; == path-derived id
    type: str                       # dataset | paper | topic | theme
    slug: str
    project: str                    # registered project name
    overlay_path: Path
    frontmatter: dict[str, Any]
    body: str                       # overlay markdown body text
    pin_version: str | None
    pin_effective_version: str | None
```

### 5.3 `OverlayAdapter` (`overlay.py`)

Constructed with a project root and the project name:

```python
class OverlayAdapter:
    def __init__(self, project_root: Path, project: str,
                 validator: EntityValidator | None = None) -> None: ...

    def load(self, canonical_id: str) -> OverlayRecord | None: ...
    def scan(self) -> Iterator[OverlayRecord | OverlayValidationError]: ...
```

`load(canonical_id)`:
1. Parse `<type>:<slug>` (reject malformed ids — same contract as the Phase B
   adapter).
2. Compute `<project_root>/doc/<type_plural>/<slug>.md`. If the file does not
   exist → return `None` (not an error).
3. Parse frontmatter + body via `parse_frontmatter`.
4. Run `EntityValidator.validate_overlay(frontmatter)` — schema +
   `id == overlay_of`.
5. Assert `frontmatter["overlay_of"]` equals the path-derived canonical id.
6. Any failure in 3–5 → `OverlayValidationError` (carries `overlay_path` +
   `canonical_id`). Success → `OverlayRecord`.

`scan()`:
- Walk `<project_root>/doc/{datasets,papers,topics,themes}/*.md`.
- Yield an `OverlayRecord` or an `OverlayValidationError` per file. A missing
  `doc/` directory or a missing type subdirectory yields nothing (not an error —
  a project need not overlay every type). An unreadable directory raises
  `CommonsError`.

### 5.4 `merge_entity` (`overlay.py`)

Near-pure: the only I/O is reading the canonical body text from
`canonical.body_path`. The frontmatter merge is pure.

```python
def merge_entity(
    canonical: CommonsEntityRecord,
    overlay: OverlayRecord | None,
    merge_policy: dict[str, MergePolicy],
) -> MergedEntity:
```

`merge_policy` is `read_merge_policy(canonical.schema_profile)`.

- **`overlay is None`** → `merged_frontmatter = dict(canonical.frontmatter)`,
  `merged_body` = canonical body text, every entry in `field_sources` is
  `"canonical"`.
- **`overlay` present** — start from `dict(canonical.frontmatter)`, then for each
  field in `overlay.frontmatter` *except* `id`, `overlay_of`, `pin_version`,
  `pin_effective_version`:
  - **`APPEND`** → `merged[field] = _dedup(canonical.get(field, []) +
    overlay[field])`, canonical order first then new overlay items. Source
    `"overlay"`.
  - **`PROJECT_ONLY`** → `merged[field] = overlay[field]` (the canonical schema
    does not define the field). Source `"overlay"`.
  - **`REPLACE` / `FORBIDDEN`** → cannot occur in a validated overlay: the
    overlay schema (`overlay-1.0.json`, `additionalProperties: false`) permits
    only `project_only` / `append` / id-version fields, and `validate_overlay`
    runs before merge. As a defense-in-depth corrupt-state guard, `merge_entity`
    raises `OverlayMergeError` (carries `field` + `canonical_id`) if it ever
    sees one. This is not a user-facing path.
  - The field's policy is looked up first in `merge_policy`; a field absent
    there (overlay-only field such as `relevance`) is resolved via
    `read_overlay_merge_policy()`, which defaults unannotated overlay fields to
    `PROJECT_ONLY`.
- **Body** — `merged_body = canonical_body + "\n\n" + overlay.body` when
  `overlay.body` is non-empty (after strip), else just the canonical body.
  Overlay sections are appended verbatim; no header rewriting.
- `field_sources` covers every key in `merged_frontmatter`.

The merge is fully policy-driven: a new `science:merge`-annotated schema field
needs zero changes here.

`pin_version` is carried on `MergedEntity.overlay` but is **not acted on** in D1
— the "pinning inactive" warning is the CLI's responsibility (§6.1).

### 5.5 `MergedEntity` (`overlay.py`)

```python
@dataclass(frozen=True, slots=True)
class MergedEntity:
    canonical: CommonsEntityRecord
    overlay: OverlayRecord | None        # None: project given, no overlay file
    merged_frontmatter: dict[str, Any]
    merged_body: str
    field_sources: dict[str, str]        # field -> "canonical" | "overlay"
```

A `MergedEntity` with `overlay=None` is a valid "canonical-only" result — callers
of `resolve_entity` always get one consistent type whether or not a project (or
overlay) was supplied.

### 5.6 `resolve_entity` (`overlay.py`)

```python
def resolve_entity(canonical_id: str, project: str | None = None) -> MergedEntity:
```

1. `root = resolve_commons_root()`. If `not root.is_dir()` →
   `CommonsRootNotFoundError`.
2. `record = CommonsQuery(root).show(canonical_id)` — goes through the registry,
   inheriting Phase B's staleness warning and `CommonsEntityError` on unknown id.
3. **`project is None`** → `merge_entity(record, None,
   read_merge_policy(record.schema_profile))`.
4. **`project` given:**
   - `project_root = resolve_project_root(project)` → `ProjectNotRegisteredError`
     on unknown name.
   - `overlay = OverlayAdapter(project_root, project).load(canonical_id)` →
     `OverlayRecord | None`.
   - `merge_entity(record, overlay, read_merge_policy(record.schema_profile))`.

`resolve_entity` does **no printing**. Warnings (inactive `pin_version`,
registry staleness) are surfaced by its callees or by the CLI, keeping the
Python API quiet and composable.

### 5.7 `validate_project_overlays` (`overlay.py`)

```python
@dataclass(frozen=True)
class OverlayValidationReport:
    checked: int
    errors: list[OverlayValidationError]

def validate_project_overlays(project: str) -> OverlayValidationReport:
```

Separate orchestration (not via `resolve_entity`):

1. `root = resolve_commons_root()` (must be a dir → `CommonsRootNotFoundError`).
2. `project_root = resolve_project_root(project)`.
3. Run `OverlayAdapter(project_root, project).scan()`. For each item:
   - `OverlayValidationError` → count + collect.
   - `OverlayRecord` → additionally confirm `overlay_of` resolves to a real
     canonical entity via `CommonsEntityAdapter(root).load(record.canonical_id)`;
     a `CommonsEntityError` there becomes an `OverlayValidationError` (dangling
     `overlay_of`). Count either way.

Report shape mirrors Phase B's `ValidationReport`.

## 6. CLI

### 6.1 `science commons show <id> --project <name>`

- Delete the Phase B rejection block.
- No `--project` → unchanged Phase B path (`CommonsQuery.show` →
  `CommonsEntityRecord`).
- With `--project` → `resolve_entity(entity_id, project=...)`.
  - If `m.overlay` and `m.overlay.pin_version` → stderr:
    `warning: pin_version <v> on overlay is inactive until Phase E; merged from
    live entity`.
  - Human output: canonical fields, then an `overlay:` block (project name +
    the fields it contributed, read from `field_sources`), then the merged body.
  - `--json`: a new `_merged_to_json(m, root)` emitting `canonical_id`,
    `merged_frontmatter`, `merged_body`, `field_sources`, and an `overlay`
    sub-object (`project`, `overlay_path` relative to the project root,
    `pin_version`, `pin_effective_version`) or `null`.
- `CommonsError` (base of every new subclass) → `click.ClickException`.

### 6.2 `science commons validate --project <name>`

- Add a `--project` option to `validate_cmd`.
- With `--project` → call `validate_project_overlays(project)`; report `checked`
  + per-file errors; exit 1 on any error. (`--type` / `--slug` are ignored on
  this path; they filter the canonical-validation path only.)
- Without `--project` → unchanged Phase B canonical-validation path.

## 7. Error handling

New classes in `errors.py`, all subclassing `CommonsError`:

| Class | Raised when | Carries |
| --- | --- | --- |
| `ProjectNotRegisteredError` | `--project <name>` has no `projects[]` entry | `name` |
| `OverlayValidationError` | overlay fails `validate_overlay`; `overlay_of` ≠ path-derived id; `overlay_of` points to no canonical entity | `overlay_path`, `canonical_id` |
| `OverlayMergeError` | defense-in-depth: a `replace`/`forbidden` field slipped past overlay validation into `merge_entity` | `field`, `canonical_id` |

Edge cases:
- Missing overlay file → `OverlayAdapter.load` returns `None` (not an error).
- Registered project path absent on disk → `load` returns `None`; `scan` surfaces
  the OS error wrapped as `CommonsError`.
- Canonical entity missing while an overlay exists → `OverlayValidationError`
  from the `overlay_of` resolvability check (`validate --project`), or
  `CommonsEntityError` from `CommonsQuery.show` (`show --project`).

## 8. Testing

### 8.1 Fixtures (`science/tests/fixtures/`)

- `commons/valid/` — confirm/add one paper and one dataset canonical entity
  usable as merge targets (Phase B already seeds `datasets/rnaseq-example/`).
- `overlays/proj-alpha/doc/papers/<slug>.md` — valid paper overlay: sets
  `relevance`, `hypothesis_links`, `project_tags` (project-only), an `append`
  field (`tags`), plus a project-specific body section.
- `overlays/proj-alpha/doc/datasets/<slug>.md` — valid dataset overlay.
- `overlays/proj-broken/doc/papers/<slug>.md` — overlay that fails the overlay
  schema (sets a `forbidden` field).
- `overlays/proj-broken/doc/topics/<slug>.md` — overlay whose `overlay_of`
  points to no canonical entity.
- Config: tests `monkeypatch` `SCIENCE_CONFIG_DIR` to a tmp dir holding a
  `config.yaml` registering `proj-alpha` / `proj-broken` with `path` pointing at
  the fixture dirs, and `SCIENCE_COMMONS_ROOT` at the commons fixture.

### 8.2 Test files

- `tests/test_commons_overlay.py` — `OverlayAdapter.load` (hit, miss→`None`,
  schema-fail, `overlay_of` mismatch); `OverlayAdapter.scan` (mixed records +
  errors); `merge_entity` units (`None` overlay; `append` dedup + order;
  `project_only` copy; body concatenation; `field_sources`; `OverlayMergeError`
  guard); `resolve_entity` (no project; project with overlay; project, no
  overlay; unknown project; unknown id); `validate_project_overlays` (clean,
  broken, dangling `overlay_of`).
- `tests/test_commons_config.py` — extend: `resolve_project_root` (hit; unknown
  name → `ProjectNotRegisteredError`).
- `tests/test_commons_cli.py` — extend: `show --project` (human + `--json`,
  with/without overlay); inactive-`pin_version` stderr warning; unknown-project
  exit code; `validate --project` (clean exit 0, broken exit 1).
- `tests/test_commons_public_api.py` — add to the expected export set:
  `OverlayAdapter`, `OverlayRecord`, `MergedEntity`, `OverlayValidationReport`,
  `merge_entity`, `resolve_entity`, `validate_project_overlays`,
  `resolve_project_root`, `ProjectNotRegisteredError`, `OverlayValidationError`,
  `OverlayMergeError`.

### 8.3 Conventions

- TDD throughout; one commit per task.
- Test invocation: `cd ~/d/science/science && uv run pytest <path> -v`.
- Full suite + model suite green before D1 is done.

## 9. Public API surface (`__init__.py`)

Added to `science_tool.commons.__all__`:

- `OverlayAdapter`, `OverlayRecord`, `MergedEntity`, `OverlayValidationReport`
- `merge_entity`, `resolve_entity`, `validate_project_overlays`
- `resolve_project_root`
- `ProjectNotRegisteredError`, `OverlayValidationError`, `OverlayMergeError`

## 10. Follow-on phases

- **D2** — `science_model.contracts.inventory_v2` (`SCHEMA_VERSION = "2"`,
  top-level `overlays[]`, shared entities as `scope: "cross-project"`, dataset
  resources projected into `InventoryEntity.data["resources"]`) + inventory
  builder integration (`--schema-version` flag, walking the commons store).
  Consumes D1's `OverlayAdapter` and `merge_entity`.
- **Phase E** — `science promote` + git tagging; activates `pin_version`
  resolution (D1 already parses and validates the field).

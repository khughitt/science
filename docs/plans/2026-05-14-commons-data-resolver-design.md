# Phase C: Commons data resolver — design

**Parent design:** `docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` (§4 Bulk data resolution, §9 Phase C)
**Predecessor:** `docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md` (Phase B — commons scaffolding, merged at `7f5c8f5`)

## 1. Goal

Add a **bulk-data resolver** to `science_tool.commons`: an in-process library plus a
`science commons data resolve` CLI command that maps `(dataset_id, logical_path)` to a
**verified absolute filesystem path**.

The commons store (Phase B) is the source of truth for *what the bytes should be* — each
dataset's sibling `datapackage.yaml` carries `resources[]` with a required `hash:`. The
resolver finds the actual bytes on the local machine and proves they match that hash. Bulk
data lives **outside** the Dropbox-synced metadata tree, content-addressed by hash.

**Guiding principle (inherited from parent §1):** *metadata is small, versioned, and shared;
bulk data is large, hashed, and out-of-tree.* Phase C builds the read path for that bulk data.

## 2. Scope

### In scope
- `resolve_commons_data_root()` config helper + `$SCIENCE_COMMONS_DATA_ROOT` env var.
- Per-machine override file `~/.config/science/data.yaml` (slug → absolute directory).
- `commons/datapackage.py` — a thin Frictionless descriptor reader (`resources[].path` + `hash`).
- `commons/resolver.py` — the lookup chain + sha256 hash verification.
- `science commons data resolve <dataset:slug> <logical_path> [--json]` CLI command.
- New errors: `CommonsDatapackageError`, `DataResourceNotFoundError`, `DataIntegrityError`.
- Per-module unit tests + fixture extensions.

### Out of scope (deferred)
- **`science commons data fetch` and recipe-driven regeneration — Phase E.** Recipes
  (`recipe/Snakefile`, `recipe/lockfile.yaml`) are written into the store by `science promote`,
  which is Phase E. In Phase C no dataset has a `recipe/` directory, so `fetch` has nothing to
  operate on. Shipping `resolve` alone is the honest scope for this phase.
- **Recipe pinning / `lockfile.yaml`** (parent §4.5) — Phase E, alongside `fetch`.
- **Local CAS object store** `$SCIENCE_COMMONS_DATA_ROOT/objects/<hash>` (parent §4.1 step 4) — v2.
- **Remote object store** (S3-compatible / rsync) (parent §4.1 step 5) — v2.
- **Hash result caching** — every `resolve` call re-hashes. Parent §4.2 mandates verification on
  every resolution; the Phase C store is small so a full re-hash is cheap. A cache is a later
  concern if real volume justifies it.
- **Overlay-aware / version-pinned resolution** (`--project`, `pin_version`) — Phase D.
- **Inventory integration** — Phase D, with `inventory_v2`.

## 3. Naming

Phase B renamed the user-facing surface from "shared store" to **commons**. Phase C follows
that consistently:

| Parent design (§4) | Phase C |
| --- | --- |
| `$SCIENCE_DATA_ROOT` | `$SCIENCE_COMMONS_DATA_ROOT` |
| default `/data/science-shared/` | default `/data/science-commons/` |
| `data_root:` (top-level config) | `commons.data_root` (under the existing `commons:` block) |

The default data root is an absolute system path (`/data/...`), **not** under `~/d/` — bulk
data is explicitly not Dropbox-synced (parent §1, §2).

## 4. Architecture

### 4.1 Code layout

```
science/src/science_tool/commons/
├── datapackage.py      # NEW — Frictionless descriptor reader
├── resolver.py         # NEW — lookup chain + hash verification
├── config.py           # MODIFIED — resolve_commons_data_root() + load_data_overrides()
├── errors.py           # MODIFIED — CommonsDatapackageError, DataResourceNotFoundError,
│                       #            DataIntegrityError
├── cli.py              # MODIFIED — `data` subgroup with `resolve`
└── __init__.py         # MODIFIED — export new public surface
```

Nothing outside `commons/` is touched. The resolver consumes the existing
`CommonsEntityAdapter.load()` (Phase B) to locate a dataset's `datapackage.yaml` — no new
store-walking logic.

### 4.2 On-disk layout (read by the resolver)

```
$SCIENCE_COMMONS_ROOT/datasets/<slug>/
├── entity.md               # surface metadata (Phase B)
└── datapackage.yaml        # Frictionless descriptor — resources[].path + resources[].hash

$SCIENCE_COMMONS_DATA_ROOT/<slug>/
└── <logical_path>          # the actual bytes (NOT Dropbox-synced)
```

## 5. Components

### 5.1 Config (`commons/config.py`)

Extend `CommonsSettings` with a new optional field:

```python
class CommonsSettings(BaseModel):
    root: Path | None = None        # existing (Phase B)
    data_root: Path | None = None   # NEW — None means "use built-in default"
```

```yaml
# ~/.config/science/config.yaml
commons:
  root: ~/d/science-commons          # Phase B
  data_root: /data/science-commons   # NEW — optional; default applied if missing
```

**Data root resolver:**

```python
def resolve_commons_data_root() -> Path:
    # 1. $SCIENCE_COMMONS_DATA_ROOT env var
    # 2. commons.data_root in the global config file
    # 3. default: /data/science-commons/
```

**Per-machine override loader.** A separate file `~/.config/science/data.yaml` (sibling of
`config.yaml`, located via the existing `get_science_config_dir()`):

```yaml
# ~/.config/science/data.yaml — slug → absolute directory
cath-domains: /data/legacy/cath/
```

```python
def load_data_overrides() -> dict[str, Path]:
    """Slug → absolute directory. Returns {} if the file is missing.
    Raises a loud error if the file exists but is malformed."""
```

It is a deliberately **separate file** from `config.yaml` because it is machine-local and not
synced; keeping it out of `config.yaml` avoids accidentally committing machine-specific paths.

### 5.2 Datapackage reader (`commons/datapackage.py`)

A thin reader for the Frictionless sidecar. Phase C only needs `path` + `hash` per resource;
schemas, dialects, and other Frictionless fields are ignored.

```python
@dataclass(frozen=True, slots=True)
class DataResource:
    path: str          # logical path within the dataset (resources[].path)
    hash: str          # full "sha256:..." string, verbatim from resources[].hash

@dataclass(frozen=True, slots=True)
class DatapackageDescriptor:
    resources: tuple[DataResource, ...]

    def resource(self, logical_path: str) -> DataResource:
        """Look up one resource by logical path. Raises CommonsDatapackageError if absent."""

def read_datapackage(path: Path) -> DatapackageDescriptor:
    """Parse a datapackage.yaml. Raises CommonsDatapackageError on malformed YAML,
    missing resources[], or any resource with a missing/empty hash."""
```

**Invariants enforced:**
- The file must parse as YAML and contain a `resources` list.
- Every resource must carry a non-empty `path` and a non-empty `hash`. A resource with no
  hash is unusable (it cannot be integrity-verified), so this is a loud failure, not a skip.

**Why not reuse `DatapackageAdapter`?** `science_tool.graph.storage_adapters.datapackage.DatapackageAdapter`
is entity-profile focused — it filters to an `_ENTITY_FIELDS` allowlist and *deliberately
strips* `resources[]` (project-side entity surfaces do not carry resources). It is the wrong
tool for reading resource hashes; reusing it would mean bending it away from its purpose.
`commons/datapackage.py` is a new, focused reader.

### 5.3 Resolver (`commons/resolver.py`)

```python
def resolve(
    dataset_id: str,                    # "dataset:<slug>"
    logical_path: str,
    *,
    commons_root: Path | None = None,   # default: resolve_commons_root()
    data_root: Path | None = None,      # default: resolve_commons_data_root()
) -> Path:
    """Map (dataset_id, logical_path) to a verified absolute filesystem path."""
```

**Steps:**

1. `CommonsEntityAdapter(commons_root).load(dataset_id)` → `CommonsEntityRecord`. A
   non-dataset id (e.g. `paper:...`) or a dataset with no `datapackage_path` is an error.
2. `read_datapackage(record.datapackage_path)` → `.resource(logical_path)` → the expected
   `hash`.
3. **Lookup chain**, in order (parent §4.1 steps 1–2; step 3 recipe regen is Phase E):
   1. `data_root / slug / logical_path` — if the file exists, this is the candidate.
   2. else `load_data_overrides().get(slug)` → `<override_dir> / logical_path` — if it
      exists, this is the candidate.
   3. neither exists → `DataResourceNotFoundError`, listing both paths tried.
4. **Hash-verify** the candidate: stream sha256 over the file, compare to the expected hash.
   Mismatch → `DataIntegrityError`. Verification runs on **every** call, for **both** lookup
   sources — there is no silent fall-through (parent §4.2).
5. Return the absolute, verified path.

The `data_root` directory takes precedence over the per-machine override: the override is a
migration aid for legacy layouts, and the canonical location should win when both are present.

### 5.4 CLI (`commons/cli.py`)

A new `data` subgroup under the existing `commons_group`:

```
science commons data resolve <dataset:slug> <logical_path> [--json]
```

- **Default output:** the verified absolute path on stdout, one line — composable into shell
  pipelines, e.g. `cat "$(science commons data resolve dataset:cath-domains domains.tsv)"`.
- **`--json`:** `{"dataset_id", "logical_path", "resolved_path", "hash", "source"}` where
  `source` is `"data_root"` or `"override"`.
- Errors map to the repo's `click.ClickException` convention (the Phase B CLI realignment),
  exiting non-zero with a clear message.
- **No `data fetch` command** — deferred to Phase E (see §2).

## 6. Error model

Added to `commons/errors.py`, under the existing `CommonsError` base:

```python
class CommonsDatapackageError(CommonsError):
    """datapackage.yaml is malformed, missing resources[], or has a resource
    with a missing/empty hash."""
    def __init__(self, path: Path, *, reason: str) -> None: ...

class DataResourceNotFoundError(CommonsError):
    """The bytes for a resource were not found in any lookup source."""
    def __init__(self, dataset_id: str, logical_path: str, *, tried: list[Path]) -> None: ...

class DataIntegrityError(CommonsError):
    """A resource file was found but its sha256 does not match the expected hash."""
    def __init__(self, path: Path, *, expected: str, actual: str) -> None: ...
```

All three are **raised** (layout / integrity invariants), not yielded. The resolver is a
single-entity operation, so there is no scan-style error collection as in the Phase B adapter.

## 7. Testing strategy

Per-module unit tests, fixture-driven, all under `science/tests/`:

| File | Coverage |
| --- | --- |
| `test_commons_datapackage.py` | valid descriptor parse; missing `resources`; resource with missing/empty `hash` → `CommonsDatapackageError`; `resource()` lookup hit + miss |
| `test_commons_resolver.py` | resolve from `data_root`; resolve from override; precedence (`data_root` wins when both present); not-found → `DataResourceNotFoundError`; hash mismatch → `DataIntegrityError`; non-dataset id; missing `logical_path` |
| `test_commons_cli_data.py` | `resolve` happy path (plain + `--json`); each error class → non-zero exit with clear message |
| `test_commons_config.py` (extend) | `resolve_commons_data_root()` discovery order; `load_data_overrides()` missing-file → `{}`, malformed-file → loud error |

**Fixtures.** Extend Phase B's `science/tests/fixtures/commons/` with a dataset whose
`datapackage.yaml` carries real `resources[]` + sha256 hashes, plus matching byte files in a
fixture data root. Tests use `tmp_path` for synthetic commons stores and data roots where
mutation is needed.

The full `science` suite and the `science_model` suite must stay green.

## 8. Deliverables checklist

1. `commons/config.py` — `data_root` field, `resolve_commons_data_root()`, `load_data_overrides()`.
2. `commons/datapackage.py` — `DataResource`, `DatapackageDescriptor`, `read_datapackage()`.
3. `commons/resolver.py` — `resolve()`.
4. `commons/errors.py` — three new error classes.
5. `commons/cli.py` — `data` subgroup with `resolve`.
6. `commons/__init__.py` — public surface exports.
7. Test coverage: four test files (three new, one extended) + fixture extensions.

## 9. Follow-on phases

- **Phase D — Overlay merge + inventory_v2.** Overlay-aware and version-pinned resolution
  (`--project`, `pin_version` reads `datapackage.yaml` at a pinned commit); the
  `CommonsEntityRecord → InventoryEntity` projection.
- **Phase E — Migration + `fetch`.** `science promote` writes `recipe/` + `lockfile.yaml` and
  computes resource hashes; `science commons data fetch` runs recipe-driven regeneration
  (parent §4.1 step 3, §4.5) and the per-machine override `--relocate` workflow.
- **v2 — CAS.** Local content-addressed object store and pluggable remote backends
  (parent §4.1 steps 4–5).

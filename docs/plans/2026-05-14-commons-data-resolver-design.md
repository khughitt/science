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
data lives **outside** the Dropbox-synced metadata tree.

Phase C is **path-addressed and hash-verified**: bytes are located by a conventional
`<data_root>/<slug>/<logical_path>` layout (or a per-machine override) and then verified
against the descriptor hash. It is *not* content-addressed — a content-addressed object store
(CAS), where the hash *is* the lookup key, is explicitly a v2 concern (parent §4.1 steps 4–5,
§10). The hash in Phase C is an integrity check on a path lookup, not the lookup mechanism.

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
├── adapter.py          # MODIFIED — load() raises CommonsLayoutError for a dataset
│                       #            missing datapackage.yaml (mirrors scan())
├── errors.py           # MODIFIED — CommonsDatapackageError, DataLogicalPathError,
│                       #            DataResourceNotFoundError, DataIntegrityError
├── cli.py              # MODIFIED — `data` subgroup with `resolve`
└── __init__.py         # MODIFIED — export new public surface
```

Nothing outside `commons/` is touched. The resolver consumes the existing
`CommonsEntityAdapter.load()` (Phase B) to locate a dataset's `datapackage.yaml` — no new
store-walking logic, plus the small `load()` consistency patch noted in §5.3.

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

**Validation contract.** A missing file yields `{}`. If the file exists it must parse as a
YAML mapping of `str → str`, and **every value must be an absolute path** (after
`~`-expansion) — a relative path is a loud error, not a silently-resolved-against-cwd value.
The path is *not* required to exist on disk at load time (the resolver checks existence per
lookup); the contract is only that it is well-formed and absolute. A non-mapping document, a
non-string key or value, or a relative value each raise a clear error naming the offending
entry.

It is a deliberately **separate file** from `config.yaml` because it is machine-local and not
synced; keeping it out of `config.yaml` avoids accidentally committing machine-specific paths.

### 5.2 Datapackage reader (`commons/datapackage.py`)

A thin reader for the Frictionless sidecar. Phase C only needs `path` + `hash` per resource;
schemas, dialects, and other Frictionless fields are ignored.

```python
@dataclass(frozen=True, slots=True)
class DataResource:
    path: str          # logical path within the dataset (resources[].path), validated
    hash: str          # full "sha256:<64 hex>" string, verbatim from resources[].hash

@dataclass(frozen=True, slots=True)
class DatapackageDescriptor:
    resources: tuple[DataResource, ...]

    def resource(self, logical_path: str) -> DataResource:
        """Look up one resource by logical path. Raises CommonsDatapackageError if absent."""

def read_datapackage(path: Path) -> DatapackageDescriptor:
    """Parse a datapackage.yaml. Raises CommonsDatapackageError on malformed YAML,
    missing resources[], a resource with an invalid path, a duplicate logical
    path, or a resource with a missing/malformed hash."""

def validate_logical_path(logical_path: str) -> str:
    """Assert a logical path is a safe forward-slash relative path within a
    dataset. Returns it unchanged on success; raises DataLogicalPathError
    otherwise. Shared by read_datapackage (for resources[].path) and the resolver
    (for the CLI arg)."""

def parse_resource_hash(raw: str) -> tuple[str, str]:
    """Parse a 'sha256:<64 hex>' string into (algorithm, hexdigest).
    Raises CommonsDatapackageError on a missing prefix, an unsupported algorithm,
    or a malformed digest."""
```

**Logical-path validation (`validate_logical_path`).** Both the descriptor's
`resources[].path` values *and* the `logical_path` CLI argument are joined onto a filesystem
root, so both are an injection surface. A logical path is **rejected** if it is:
- empty or whitespace-only;
- absolute (`Path(p).is_absolute()`, which also catches POSIX `/foo`);
- a Windows drive/root form (`C:\...`, `\\server\share`, leading backslash) — rejected
  explicitly so behavior does not depend on the host OS;
- containing **any** backslash (`\`) — the accepted form is forward-slash only, so
  `raw\file.tsv` is rejected even though it is not a drive/root form;
- containing a `..` parent-traversal segment, or a `.` segment;
- not normalized (any path that does not round-trip cleanly as a forward-slash relative path).

The accepted form is a forward-slash relative path with no traversal — e.g. `domains.tsv`,
`raw/chains.csv`. Validation is purely lexical (no filesystem access), so it runs before any
join. On rejection it raises `DataLogicalPathError` (§6), which carries the offending logical
path string — not a `Path` — so the message never has to pretend a bad CLI argument is a
datapackage file. The resolver calls it on the CLI argument *before* the descriptor lookup,
so a hostile input fails fast with a clear message rather than a confusing not-found.

**Hash contract (`parse_resource_hash`).** Phase C accepts exactly one algorithm:
`sha256:<64 lowercase hex chars>`. The prefix is **required** (parent §4.2 keeps it for
future algorithm migration). A bare hex digest, an unsupported algorithm
(`md5:...`, `sha1:...`), or a malformed digest (wrong length, non-hex) is a loud
`CommonsDatapackageError` — there is no lenient fallback. Verification compares the computed
sha256 hexdigest of the on-disk file to the parsed expected hexdigest; the comparison is on
the parsed `(algorithm, hexdigest)` pair, never on raw strings.

**Invariants enforced by `read_datapackage`:**
- The file must parse as YAML and contain a `resources` list.
- Every resource must carry a `path` that passes `validate_logical_path`. A
  `DataLogicalPathError` from that check is caught and re-raised as a
  `CommonsDatapackageError` naming the datapackage file — so a descriptor-level error points
  at the descriptor, while a CLI-arg error (raised by the resolver, not here) stays a
  `DataLogicalPathError`.
- Logical paths must be **unique** across `resources[]`. Two resources sharing a `path` make
  `DatapackageDescriptor.resource()` ambiguous (and could carry conflicting hashes), so a
  duplicate is a `CommonsDatapackageError`, not a last-wins silent pick.
- Every resource must carry a `hash` that passes `parse_resource_hash`. A resource with no
  hash (or an unverifiable one) is unusable, so this is a loud failure, not a skip.

**Why not reuse `DatapackageAdapter`?** `science_tool.graph.storage_adapters.datapackage.DatapackageAdapter`
is entity-profile focused — it filters to an `_ENTITY_FIELDS` allowlist and *deliberately
strips* `resources[]` (project-side entity surfaces do not carry resources). It is the wrong
tool for reading resource hashes; reusing it would mean bending it away from its purpose.
`commons/datapackage.py` is a new, focused reader.

### 5.3 Resolver (`commons/resolver.py`)

```python
@dataclass(frozen=True, slots=True)
class ResolvedDataResource:
    path: Path         # absolute, verified filesystem path to the bytes
    hash: str          # the expected "sha256:<hex>" the bytes were verified against
    source: str        # "data_root" | "override" — which lookup branch matched
    logical_path: str  # the (validated) logical path that was resolved
    dataset_id: str    # "dataset:<slug>"

def resolve(
    dataset_id: str,                    # "dataset:<slug>"
    logical_path: str,
    *,
    commons_root: Path | None = None,   # default: resolve_commons_root()
    data_root: Path | None = None,      # default: resolve_commons_data_root()
) -> ResolvedDataResource:
    """Map (dataset_id, logical_path) to a verified resource. The .path field is
    an absolute, hash-verified filesystem path."""
```

`resolve` returns a `ResolvedDataResource`, not a bare `Path`: the CLI's `--json` output
needs `hash` and `source`, and any future programmatic consumer benefits from the same. The
resolver is the single place that knows all of these — the CLI must not re-derive them.

**Steps:**

1. `validate_logical_path(logical_path)` — reject hostile input (absolute paths, backslashes,
   `..` traversal, Windows drive forms; see §5.2) *before* any filesystem join or store
   access. A bad argument surfaces as `DataLogicalPathError`.
2. `CommonsEntityAdapter(commons_root).load(dataset_id)` → `CommonsEntityRecord`. A
   non-dataset id (e.g. `paper:...`) raises `CommonsEntityError` (existing Phase B behavior).
   A dataset whose `datapackage.yaml` is missing raises `CommonsLayoutError` — see the
   adapter patch below.
3. `read_datapackage(record.datapackage_path)` → `.resource(logical_path)` → the expected
   `hash`.
4. **Lookup chain**, in order (parent §4.1 steps 1–2; step 3 recipe regen is Phase E):
   1. `data_root / slug / logical_path` — if it is a regular file (`is_file()`), this is the
      candidate, `source="data_root"`.
   2. else `load_data_overrides().get(slug)` → `<override_dir> / logical_path` — if it is a
      regular file (`is_file()`), this is the candidate, `source="override"`.
   3. neither is a regular file → `DataResourceNotFoundError`, listing both paths tried.
   `is_file()` (not `exists()`) is used deliberately: a directory or special file at the
   target path is not a resolvable resource and must not be hashed.
5. **Hash-verify** the candidate: stream sha256 over the file, compare the computed hexdigest
   to the digest from `parse_resource_hash(expected)`. Mismatch → `DataIntegrityError`.
   Verification runs on **every** call, for **both** lookup sources — there is no silent
   fall-through (parent §4.2).
6. Return a `ResolvedDataResource` with the absolute, verified path.

The `data` directory takes precedence over the per-machine override: the override is a
migration aid for legacy layouts, and the canonical location should win when both are present.

**Adapter patch — `CommonsEntityAdapter.load()` (`commons/adapter.py`).** Phase B's `scan()`
raises `CommonsLayoutError` for a dataset directory missing its `datapackage.yaml`, but
`load()` does not: it constructs the `dp` path unconditionally and `_build()` then calls
`datapackage_path.stat()` *outside* its `try/except`, so a missing sidecar surfaces as a raw
`FileNotFoundError`. Phase C patches `load()` to mirror `scan()` — for a `datasets/` entity,
check `dp.is_file()` and raise `CommonsLayoutError` before calling `_build()`. This is a
small, targeted fix to a Phase B inconsistency that Phase C directly depends on (the resolver
calls `load()`); the resolver then lets `CommonsLayoutError` propagate and the CLI maps it to
a non-zero exit.

### 5.4 CLI (`commons/cli.py`)

A new `data` subgroup under the existing `commons_group`:

```
science commons data resolve <dataset:slug> <logical_path> [--json]
```

- **Default output:** `ResolvedDataResource.path` on stdout, one line — composable into shell
  pipelines, e.g. `cat "$(science commons data resolve dataset:cath-domains domains.tsv)"`.
- **`--json`:** the `ResolvedDataResource` serialized — `{"dataset_id", "logical_path",
  "resolved_path", "hash", "source"}`, where `source` is `"data_root"` or `"override"`. Every
  field comes straight off the dataclass; the CLI derives nothing itself.
- Errors map to the repo's `click.ClickException` convention (the Phase B CLI realignment),
  exiting non-zero with a clear message.
- **No `data fetch` command** — deferred to Phase E (see §2).

## 6. Error model

Added to `commons/errors.py`, under the existing `CommonsError` base:

```python
class CommonsDatapackageError(CommonsError):
    """datapackage.yaml is malformed, missing resources[], has a resource with an
    invalid logical path, has duplicate logical paths, or has a resource with a
    missing/malformed hash. Always names a real datapackage file path."""
    def __init__(self, path: Path, *, reason: str) -> None: ...

class DataLogicalPathError(CommonsError):
    """A logical path string is not a safe forward-slash relative path. Raised by
    validate_logical_path. Carries the offending string, not a Path — so a bad CLI
    argument is not forced to masquerade as a datapackage file."""
    def __init__(self, logical_path: str, *, reason: str) -> None: ...

class DataResourceNotFoundError(CommonsError):
    """The bytes for a resource were not found in any lookup source."""
    def __init__(self, dataset_id: str, logical_path: str, *, tried: list[Path]) -> None: ...

class DataIntegrityError(CommonsError):
    """A resource file was found but its sha256 does not match the expected hash."""
    def __init__(self, path: Path, *, expected: str, actual: str) -> None: ...
```

All four are **raised** (layout / integrity invariants), not yielded. The resolver is a
single-entity operation, so there is no scan-style error collection as in the Phase B adapter.
`read_datapackage` catches a `DataLogicalPathError` from a `resources[].path` and re-raises it
as a `CommonsDatapackageError` (so descriptor errors name the descriptor); a `DataLogicalPathError`
from the CLI argument propagates unwrapped.

## 7. Testing strategy

Per-module unit tests, fixture-driven, all under `science/tests/`:

| File | Coverage |
| --- | --- |
| `test_commons_datapackage.py` | valid descriptor parse; missing `resources`; duplicate `resources[].path` → `CommonsDatapackageError`; `resource()` lookup hit + miss; **`validate_logical_path`**: accepts `a.tsv` / `raw/b.csv`, rejects (→ `DataLogicalPathError`) empty, absolute (`/x`), backslash relative (`raw\x.tsv`), `..` traversal, leading `./`, Windows drive (`C:\x`) and UNC (`\\s\share`); **`parse_resource_hash`**: accepts `sha256:<64 hex>`, rejects bare hex, unsupported algo (`md5:`), wrong-length / non-hex digest; resource with missing/malformed `hash` or invalid `path` → `CommonsDatapackageError` (descriptor-named) |
| `test_commons_resolver.py` | resolve from `data_root`; resolve from override; precedence (`data_root` wins when both present); `source` field correct per branch; not-found → `DataResourceNotFoundError`; hash mismatch → `DataIntegrityError`; non-dataset id → `CommonsEntityError`; dataset missing `datapackage.yaml` → `CommonsLayoutError`; missing `logical_path` in descriptor; hostile `logical_path` arg → `DataLogicalPathError` before store access; target path is a directory → `DataResourceNotFoundError` (not hashed) |
| `test_commons_cli_data.py` | `resolve` happy path (plain path output + `--json` with all five fields); each error class (incl. missing-datapackage) → non-zero exit with clear message |
| `test_commons_config.py` (extend) | `resolve_commons_data_root()` discovery order; `load_data_overrides()` missing-file → `{}`, malformed (non-mapping / non-string entry) → loud error, **relative-path value → loud error** |
| `test_commons_adapter.py` (extend) | `load()` on a dataset with `entity.md` but no `datapackage.yaml` → `CommonsLayoutError` (not raw `FileNotFoundError`) |

**Fixtures.** Extend Phase B's `science/tests/fixtures/commons/` with a dataset whose
`datapackage.yaml` carries real `resources[]` + sha256 hashes, plus matching byte files in a
fixture data root. Tests use `tmp_path` for synthetic commons stores and data roots where
mutation is needed.

The full `science` suite and the `science_model` suite must stay green.

## 8. Deliverables checklist

1. `commons/config.py` — `data_root` field, `resolve_commons_data_root()`, `load_data_overrides()`
   (with absolute-path validation).
2. `commons/datapackage.py` — `DataResource`, `DatapackageDescriptor`, `read_datapackage()`,
   `validate_logical_path()`, `parse_resource_hash()`.
3. `commons/resolver.py` — `ResolvedDataResource`, `resolve()`.
4. `commons/errors.py` — four new error classes (`CommonsDatapackageError`,
   `DataLogicalPathError`, `DataResourceNotFoundError`, `DataIntegrityError`).
5. `commons/adapter.py` — `load()` raises `CommonsLayoutError` for a dataset missing
   `datapackage.yaml` (mirrors `scan()`).
6. `commons/cli.py` — `data` subgroup with `resolve`.
7. `commons/__init__.py` — public surface exports.
8. Test coverage: five test files (three new, two extended) + fixture extensions.

## 9. Follow-on phases

- **Phase D — Overlay merge + inventory_v2.** Overlay-aware and version-pinned resolution
  (`--project`, `pin_version` reads `datapackage.yaml` at a pinned commit); the
  `CommonsEntityRecord → InventoryEntity` projection.
- **Phase E — Migration + `fetch`.** `science promote` writes `recipe/` + `lockfile.yaml` and
  computes resource hashes; `science commons data fetch` runs recipe-driven regeneration
  (parent §4.1 step 3, §4.5) and the per-machine override `--relocate` workflow.
- **v2 — CAS.** Local content-addressed object store and pluggable remote backends
  (parent §4.1 steps 4–5).

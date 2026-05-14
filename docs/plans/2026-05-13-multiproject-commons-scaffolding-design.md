# Phase B: Commons scaffolding — design

**Parent design:** `docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` (§9 Phase B)
**Status:** approved 2026-05-13
**Depends on:** Phase A (entity_schema layer — merged)

---

## 1. Goal

Stand up the shared knowledge store as a queryable, validatable, CLI-accessible component without yet adding overlays, the data resolver, or migration. At the end of Phase B:

- A user can run `science commons init` to create `~/d/science-commons/` as a standalone git repo with the expected layout.
- A user can place valid entity files into that store and run `science commons index rebuild` to build a SQLite index.
- A user can run `science commons find dataset --tag scrna`, `science commons show paper:adams2025`, and `science commons validate` against that index.
- The existing inventory builder can optionally include shared entities (`scope="cross-project"`) in `inventory_v1` output via a new `--include-shared` flag, with no changes to the v1 contract.

## 2. Naming

The parent design uses "shared store" / "shared entity" throughout. Phase B renames the user-facing surface to **`commons`** to reflect the actual mental model: a curated, open, citable pool of data and knowledge entities ("Creative Commons" / "data commons" framing — not "shared volume").

| Surface | Name |
| --- | --- |
| CLI group | `science commons` |
| Bootstrap | `science commons init` |
| Subpackage | `science_tool/commons/` |
| Directory on disk | `~/d/science-commons/` |
| Env var (root override) | `$SCIENCE_COMMONS_ROOT` |
| Config key | `commons.root` |
| Adapter class | `CommonsEntityAdapter` |
| Record dataclass | `CommonsEntityRecord` |
| Errors | `Commons*Error` |
| Settings model | `CommonsSettings` |

**What does NOT rename:** `EntityScope.SHARED` (model-layer nomenclature), the inventory `scope="cross-project"` export label (external contract — already abstracted from the internal enum), and `science_model.entity_schema` (the parent design's name for the schema layer).

## 3. Scope

### In scope
- Directory bootstrap with `git init`, README, `.gitignore`.
- `CommonsEntityAdapter` — walks the store, parses entities into `science_model.Entity` instances.
- SQLite registry with three tables (`entities`, `entity_tags`, `entity_ontology_terms`).
- CLI: `science commons {init, index rebuild, show, find, validate}`.
- Inventory builder integration via opt-in `--include-shared` flag.
- Global config extension (`commons.root`).
- Test fixtures under `science/model/tests/fixtures/commons/`.

### Out of scope (deferred)
- Data resolver, `$SCIENCE_COMMONS_DATA_ROOT`, hash verification, recipe regeneration — Phase C.
- Overlay reading and read-time merge — Phase D.
- `inventory_v2` and the `overlays[]` field — Phase D.
- `science promote`, `science fork`, `.migrations/` audit log writes — Phase E/F/G.
- CAS object store — out of scope per parent §10.
- Dashboard changes — sequenced after E/F/G.
- Incremental rebuild — Phase E follow-on; Phase B always does a full rebuild.
- Multi-host config sync edge cases.

## 4. Architecture

### 4.1 Code layout

```
science/src/science_tool/
├── commons/                              # NEW subpackage
│   ├── __init__.py                       # public surface (re-exports)
│   ├── config.py                         # CommonsSettings (extends GlobalConfig)
│   ├── errors.py                         # CommonsError hierarchy
│   ├── bootstrap.py                      # `science commons init`
│   ├── adapter.py                        # CommonsEntityAdapter
│   ├── registry.py                       # SQLite schema + RegistryBuilder
│   ├── query.py                          # find/show search logic
│   ├── validator.py                      # `science commons validate` driver
│   └── cli.py                            # Typer subcommands
├── registry/config.py                    # MODIFY — add commons: CommonsSettings to GlobalConfig
├── entities_inventory.py                 # MODIFY — opt-in include_shared flag wires
│                                         # CommonsEntityAdapter into inventory_v1 build
└── cli.py                                # MODIFY — register `science commons` group
```

### 4.2 Store layout on disk

```
~/d/science-commons/                      # separate git repo (independent history)
├── .git/
├── .gitignore                            # registry.sqlite, .migrations/, __pycache__/
├── README.md
├── datasets/.gitkeep                     # empty after bootstrap; populated in Phase E
├── papers/.gitkeep
├── topics/.gitkeep
├── themes/.gitkeep
├── registry.sqlite                       # gitignored, regenerable
└── .migrations/                          # gitignored, populated in Phase E
```

### 4.3 Discovery order for store root

1. `$SCIENCE_COMMONS_ROOT` env var (test override / non-Dropbox setups).
2. `commons.root` in `~/.config/science/config.yaml`.
3. Default: `~/d/science-commons/`.

If no path matches an existing directory, CLI commands print **"commons store not found; run `science commons init` to create it"** and exit non-zero. No silent fallback.

## 5. Components

### 5.1 Config (`commons/config.py`)

Extends `science_tool.registry.config.GlobalConfig` with a new optional block:

```yaml
# ~/.config/science/config.yaml
sync:
  stale_after_days: 14
projects: [...]
commons:                                   # NEW
  root: ~/d/science-commons                # optional; default applied if missing
```

```python
class CommonsSettings(BaseModel):
    root: Path | None = None               # None means "use default"

class GlobalConfig(BaseModel):
    sync: SyncSettings = ...
    projects: list[RegisteredProject] = ...
    commons: CommonsSettings = Field(default_factory=CommonsSettings)
```

Resolution helper:

```python
def resolve_commons_root() -> Path:
    if env := os.environ.get("SCIENCE_COMMONS_ROOT"):
        return Path(env).expanduser()
    cfg = load_global_config()
    if cfg.commons.root is not None:
        return cfg.commons.root.expanduser()
    return Path.home() / "d" / "science-commons"
```

### 5.2 Bootstrap (`commons/bootstrap.py`)

```python
def init_commons(root: Path, *, force: bool = False) -> None:
    """Create the commons store at `root`. Idempotent if layout already valid."""
```

Behavior:
- If `root` doesn't exist: create it, `git init`, write README + .gitignore, create the four type directories with `.gitkeep`, return.
- If `root` exists and looks like a commons store (has `.git` and the four type dirs): print "already initialized" and exit 0.
- If `root` exists but doesn't look like a commons store: raise `CommonsRootMalformedError` listing what's missing. Refuses to operate.
- `--force` skips the malformed check (still doesn't clobber existing files).

### 5.3 Adapter (`commons/adapter.py`)

```python
@dataclass(frozen=True, slots=True)
class CommonsEntityRecord:
    entity: Entity                         # science_model.Entity, scope=EntityScope.SHARED
    body_path: Path                        # absolute path to entity.md
    datapackage_path: Path | None          # absolute path to sibling datapackage.yaml (datasets only)
    mtime_ns: int                          # max(entity.md, datapackage.yaml) mtime
    schema_profile: str

class CommonsEntityAdapter:
    def __init__(self, root: Path) -> None: ...
    def scan(self) -> Iterator[CommonsEntityRecord | CommonsEntityError]: ...
    def load(self, canonical_id: str) -> CommonsEntityRecord: ...
```

**Walking rules:**
- `datasets/<slug>/entity.md` — required. Missing sibling `datapackage.yaml` → `CommonsLayoutError` (this is a structural invariant, not a per-entity error).
- `papers/<bibkey>.md` — single-file.
- `topics/<slug>.md`, `themes/<slug>.md` — single-file.
- Skipped: `.git`, `.migrations`, `__pycache__`, `registry.sqlite`, any other dotfile.

**Parsing:**
- Frontmatter parsing delegates to the existing `MarkdownAdapter` frontmatter helper if cleanly importable. If extraction is non-trivial, vendor a thin re-implementation in `commons/adapter.py`. (Decided in design: vendoring is acceptable.)
- For datasets, `datapackage.yaml` is **not** materialized into `Entity` (no `resources` field on the model — per parent §2.1). Path captured separately for Phase C.
- `schema_profile` parsed via `science_model.entity_schema.parse_profile`; entity validated via `EntityValidator.validate`.
- Per-entity failures (bad frontmatter, schema violation, invalid profile) become `CommonsEntityError` records yielded from `scan()` — the registry builder collects them rather than aborting.

**What it does NOT do:**
- No overlay reading (Phase D).
- No registry writes (separation of concerns).
- No data hash verification (Phase C).

### 5.4 Registry (`commons/registry.py`)

**Location:** `<store_root>/registry.sqlite`, gitignored, regenerable.

**Schema:**

```sql
CREATE TABLE schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- rows: ('schema_version', '1'), ('built_at', ISO-8601), ('store_root', absolute path)

CREATE TABLE entities (
    canonical_id     TEXT PRIMARY KEY,     -- "dataset:cath-domains"
    type             TEXT NOT NULL,        -- "dataset" | "paper" | "topic" | "theme"
    slug             TEXT NOT NULL,
    title            TEXT,
    schema_profile   TEXT NOT NULL,
    body_path        TEXT NOT NULL,        -- relative to store_root
    datapackage_path TEXT,                 -- relative; NULL for non-datasets
    mtime_ns         INTEGER NOT NULL,
    frontmatter_json TEXT NOT NULL         -- full frontmatter, for fields not promoted to columns
);
CREATE INDEX idx_entities_type_slug ON entities (type, slug);

CREATE TABLE entity_tags (
    canonical_id TEXT NOT NULL REFERENCES entities(canonical_id) ON DELETE CASCADE,
    tag          TEXT NOT NULL,
    PRIMARY KEY (canonical_id, tag)
);
CREATE INDEX idx_entity_tags_tag ON entity_tags (tag);

CREATE TABLE entity_ontology_terms (
    canonical_id TEXT NOT NULL REFERENCES entities(canonical_id) ON DELETE CASCADE,
    term         TEXT NOT NULL,            -- e.g., "UBERON:0000178"
    PRIMARY KEY (canonical_id, term)
);
CREATE INDEX idx_entity_ontology_terms_term ON entity_ontology_terms (term);
```

**Builder API:**

```python
@dataclass(frozen=True)
class RebuildReport:
    entities_indexed: int
    errors: list[CommonsEntityError]
    duration_ms: int

class RegistryBuilder:
    def __init__(self, root: Path, adapter: CommonsEntityAdapter) -> None: ...
    def rebuild(self) -> RebuildReport: ...        # full: drop + recreate
    def is_stale(self) -> bool: ...                # built_at vs max(file mtime)
```

**Semantics:**
- Always full rebuild — drop tables, recreate, repopulate. Phase B does not implement incremental updates.
- Per-entity errors are **collected**, not raised; the registry still indexes successful entities. CLI prints a non-zero exit if `errors` is non-empty.
- Atomic write: build into `registry.sqlite.new`, `fsync`, rename. Prevents partial-index reads.
- `is_stale()` is cheap: walk the store, compare each file's `st_mtime` against `schema_meta.built_at`.

**Auto-rebuild:**
- `query.py` calls `is_stale()` before each query; rebuilds first if stale.
- `SCIENCE_COMMONS_NO_AUTO_REBUILD=1` disables auto-rebuild (CI / debugging).

### 5.5 Query (`commons/query.py`)

```python
class CommonsQuery:
    def __init__(self, root: Path) -> None: ...
    def show(self, canonical_id: str) -> CommonsEntityRecord: ...
    def find(self, type: str, *, tags: Sequence[str] = (), ontology_terms: Sequence[str] = (),
             year_from: int | None = None, year_to: int | None = None,
             slug_glob: str | None = None) -> list[CommonsEntityRecord]: ...
```

- `show` raises `CommonsEntityError` (subclass) if the id isn't in the registry.
- `find` filter semantics: repeated `--tag` and repeated `--ontology` use **AND** across repeats. `--tag-any` deferred.
- `year_from`/`year_to` are only meaningful for `type == "paper"` (validated; otherwise rejected with a CLI parse error).
- `slug_glob` uses fnmatch semantics.
- Each query call `is_stale()` checks first; rebuild is transparent.

### 5.6 Validator driver (`commons/validator.py`)

```python
class CommonsValidator:
    def __init__(self, adapter: CommonsEntityAdapter) -> None: ...
    def validate(self, *, type: str | None = None, slug: str | None = None) -> ValidationReport: ...

@dataclass(frozen=True)
class ValidationReport:
    checked: int
    errors: list[CommonsEntityError]
```

- Walks the store **without** consulting the registry (registry could be stale or absent).
- Runs `EntityValidator.validate` on each entity.
- `--type` and `--slug` filters narrow the walk.

### 5.7 CLI (`commons/cli.py`)

Typer subcommands, registered as a `science commons` group in `science_tool.cli`. Mirrors the existing `graph init` / `inquiry init` precedent — `init` lives inside the subgroup, not as a top-level command.

| Subcommand | Behavior |
| --- | --- |
| `science commons init` | `init_commons(resolve_commons_root())`. `--force` available. |
| `science commons index rebuild` | `RegistryBuilder.rebuild()`. `--json` for machine output. Exit 1 if errors. |
| `science commons show <type>:<slug>` | `CommonsQuery.show()`. `--json` for full dump (default human). `--project` rejected with **"overlay merge lands in Phase D"** (explicit, not silent). |
| `science commons find <type> [filters]` | `CommonsQuery.find()`. Default: `<canonical_id>\t<title>` lines. `--json` for arrays. |
| `science commons validate` | `CommonsValidator.validate()`. `--type T` / `--slug S` filters. Exit 1 if errors. |

**Exit code contract:**
- 0 — success.
- 1 — operational error (validation failures, missing store, no matches).
- 2 — usage error (bad CLI args).
- 64-78 reserved for future structured exit codes (sysexits.h).

## 6. Error model

```python
# science_tool/commons/errors.py

class CommonsError(Exception):
    """Base for all commons-layer errors."""

class CommonsRootNotFoundError(CommonsError):
    """Store root path does not exist. Suggests `science commons init`."""
    root: Path

class CommonsRootMalformedError(CommonsError):
    """Path exists but does not look like a commons store."""
    root: Path
    missing: list[str]

class CommonsLayoutError(CommonsError):
    """Filesystem layout violation (e.g., dataset missing datapackage.yaml sibling)."""
    path: Path
    reason: str

class CommonsEntityError(CommonsError):
    """A single entity failed parsing or schema validation."""
    path: Path
    canonical_id: str | None              # None if id couldn't be determined
    cause: Exception

class CommonsRegistryError(CommonsError):
    """SQLite-level failure (corruption, locked file, schema mismatch)."""
    db_path: Path
    cause: Exception
```

**Propagation:**

| Origin | Behavior |
| --- | --- |
| Adapter scan, layout invariant | `CommonsLayoutError` raised immediately. |
| Adapter parse, single entity | Wrapped in `CommonsEntityError` and yielded; collected by builder. |
| Registry rebuild | Collects `CommonsEntityError`s into `RebuildReport.errors`; does not abort. |
| Registry corruption | `CommonsRegistryError` raised — fatal. |
| CLI entry point | Catches `CommonsError`, prints `<error-type>: <message>` to stderr, exits 1. No traceback unless `--debug`. |

## 7. Inventory integration

`science_tool.entities_inventory.build_inventory` gains a new keyword (and a corresponding CLI flag in whichever entry point currently drives it):

```python
def build_inventory(
    project_root: Path,
    *,
    include_shared: bool = False,
    commons_root: Path | None = None,
    ...,
) -> InventoryPayload:
```

When `include_shared=True`:
- `CommonsEntityAdapter(commons_root or resolve_commons_root()).scan()` is invoked.
- Each successful `CommonsEntityRecord` is projected to an `InventoryEntity` with `scope="cross-project"`. Existing v1 projection logic is reused.
- The store's relative path becomes `source.path`; `source.adapter = "commons"`.
- `CommonsEntityError`s are surfaced as `InventoryWarning` entries with `severity="error"` and a stable warning code (e.g., `commons-entity-invalid`).
- Existing per-project entities continue to be emitted exactly as before.

**Contract guarantee:** no fields are added to `InventoryPayload` or `InventoryEntity`. The v1 contract stays intact; this is purely additive content, not additive structure. `inventory_v2` (and the `overlays[]` field) remains a Phase D concern.

## 8. Testing strategy

**Per-module unit tests** under `science/model/tests/` or `science/tests/` as appropriate to where the code lives:

| Layer | What's tested |
| --- | --- |
| `commons/config.py` | YAML round-trip, env var override, default fallback. |
| `commons/bootstrap.py` | Directory creation, idempotence, refuse-on-malformed. |
| `commons/adapter.py` | Frontmatter parsing, pair invariant, scope assignment, profile validation, per-entity error wrapping. |
| `commons/registry.py` | Schema creation, atomic rebuild, error collection, staleness detection. |
| `commons/query.py` | Each filter, AND-semantics across repeats, year range, slug-glob. |
| `commons/validator.py` | Walks store without registry; surfaces EntityValidator errors. |
| `commons/cli.py` | Typer CliRunner — arg parsing, exit codes, JSON output shape. |
| Inventory wiring | `include_shared=True` emits `scope="cross-project"` rows; `inventory_v1` content-hash machinery unchanged. |

**Fixture layout** under `science/model/tests/fixtures/commons/`:

```
valid/
├── datasets/cath-domains/{entity.md, datapackage.yaml}
├── datasets/rnaseq-example/{entity.md, datapackage.yaml}    # bio.rnaseq extension
├── papers/Adams2025.md
├── topics/single-cell-foundation-models.md
└── themes/research-hygiene.md
invalid/
├── dataset-missing-datapackage/entity.md                    # pair invariant
├── paper-bad-bibkey/badname.md                              # slug regex
└── topic-bad-profile/x.md                                   # invalid schema_profile
```

Adapter/registry tests build tmp stores by **copying** from `valid/` and adding/removing files per test — never mutate static fixtures.

**Integration test:** one end-to-end test in the `science_tool` suite that builds a real inventory with `include_shared=True` over a tmp commons store + a tmp project, asserts shared and project entities both appear, and asserts content-hash machinery still works.

## 9. Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| `MarkdownAdapter` frontmatter helper isn't cleanly extractable | medium | Allowed fallback: vendor a thin re-implementation in `commons/adapter.py`. |
| `registry.sqlite` corruption mid-rebuild | low | Atomic rename; auto-rebuild on staleness self-heals. |
| Adapter races with concurrent `science promote` (later phases) | deferred | Phase E will add a writer lock; Phase B reads only. |
| Performance: full rebuild on every staleness check | low | Phase B store is empty/small. Re-evaluate when Phase E lands real volume. |
| Existing `~/d/science-commons/` from prior experiments | low | `science commons init` refuses to operate on a non-empty path that doesn't match layout. |

## 10. Deliverables checklist

1. `~/d/science-commons/` bootstrappable via `science commons init`.
2. `CommonsEntityAdapter`, `RegistryBuilder`, `CommonsQuery`, `CommonsValidator` working against fixtures and an empty real store.
3. `science commons {init, index rebuild, show, find, validate}` subcommands wired in.
5. `entities_inventory.build_inventory` gains `include_shared` flag emitting `scope="cross-project"` rows in `inventory_v1`.
6. `~/.config/science/config.yaml` extended with optional `commons.root`.
7. Test fixtures under `science/model/tests/fixtures/commons/{valid,invalid}/`.
8. Test coverage: per-module unit tests + one integration test for inventory wiring.

## 11. Follow-on phases

- **Phase C — Data resolver.** Reuses `CommonsEntityAdapter` to locate `datapackage.yaml`. Adds `$SCIENCE_COMMONS_DATA_ROOT`, hash verification, `science commons data {resolve, fetch}`.
- **Phase D — Overlay merge.** Adds `OverlayAdapter`, extends registry with an `overlays` table, introduces `inventory_v2` with top-level `overlays[]`, enables `science commons show --project <name>`.
- **Phase E/F/G — Migration.** `science promote` writes into `.migrations/`, calls `RegistryBuilder.rebuild()` after each promotion.

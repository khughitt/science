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

Phase B is intentionally standalone: nothing else in the existing `science_tool` pipeline (inventory builder, dashboard, sync) is touched. Inventory integration lands in Phase D when `inventory_v2` introduces the contract changes that shared rows require.

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

**What does NOT rename:** `EntityScope.SHARED` (model-layer nomenclature, used by Phase D inventory integration but not by Phase B itself), the inventory `scope="cross-project"` export label (Phase D concern), and `science_model.entity_schema` (the parent design's name for the schema layer).

## 3. Scope

### In scope
- Directory bootstrap with `git init`, README, `.gitignore`.
- `CommonsEntityAdapter` — walks the store, parses each entity into a record holding the validated schema frontmatter dict plus filesystem metadata (no `Entity` materialization in Phase B).
- SQLite registry with three tables (`entities`, `entity_tags`, `entity_ontology_terms`).
- CLI: `science commons {init, index rebuild, show, find, validate}`.
- Global config extension (`commons.root`).
- Test fixtures under `science/model/tests/fixtures/commons/`.

### Out of scope (deferred)
- Data resolver, `$SCIENCE_COMMONS_DATA_ROOT`, hash verification, recipe regeneration — Phase C.
- Overlay reading and read-time merge — Phase D.
- `inventory_v2`, the `overlays[]` field, and any inventory builder modification (including `--include-shared`) — Phase D. `inventory_v1`'s path semantics (single `project_path`, source paths resolved as `project_root / source.path`) and content-hash determinism do not accommodate shared rows; v2 is the right layer.
- Transparent auto-rebuild on stale registry — Phase E (when migration traffic justifies the writer-lock + concurrency primitives). Phase B requires explicit `science commons index rebuild`.
- Per-`Entity` projection of shared frontmatter (`project`, `related`, `source_refs`, `content_preview`, `file_path` defaults) — Phase D, alongside `inventory_v2`.
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
    canonical_id: str                      # "<type>:<slug>", e.g. "dataset:cath-domains"
    type: str                              # "dataset" | "paper" | "topic" | "theme"
    slug: str
    schema_profile: str
    frontmatter: dict[str, Any]            # validated against schema_profile by EntityValidator
    body_path: Path                        # absolute path to entity.md
    datapackage_path: Path | None          # absolute path to sibling datapackage.yaml (datasets only)
    mtime_ns: int                          # max(st_mtime_ns of entity.md, datapackage.yaml)

class CommonsEntityAdapter:
    def __init__(self, root: Path) -> None: ...
    def scan(self) -> Iterator[CommonsEntityRecord | CommonsEntityError]: ...
    def load(self, canonical_id: str) -> CommonsEntityRecord: ...
```

**Why not `science_model.Entity`?** `Entity` requires fields not present in shared frontmatter (`project`, `related`, `source_refs`, `content_preview`, `file_path`) that project-side loaders fill via enrichment defaults. Phase B does not need an `Entity` (it has no inventory integration), so it carries the validated frontmatter dict directly — the most honest representation of what's actually in the store. Phase D adds the projection step (synthetic defaults + `scope=EntityScope.SHARED`) when `inventory_v2` requires it.

**Walking rules:**
- `datasets/<slug>/entity.md` — required. Missing sibling `datapackage.yaml` → `CommonsLayoutError` (this is a structural invariant, not a per-entity error).
- `papers/<bibkey>.md` — single-file.
- `topics/<slug>.md`, `themes/<slug>.md` — single-file.
- Skipped: `.git`, `.migrations`, `__pycache__`, `registry.sqlite`, any other dotfile.

**Parsing:**
- Frontmatter parsing delegates to the existing `MarkdownAdapter` frontmatter helper if cleanly importable. If extraction is non-trivial, vendor a thin re-implementation in `commons/adapter.py`. (Decided in design: vendoring is acceptable.)
- For datasets, `datapackage.yaml` is **not** loaded into the record (no `resources` field — per parent §2.1). Path captured separately for Phase C.
- `schema_profile` is parsed via `science_model.entity_schema.parse_profile`; the entity is validated via `EntityValidator.validate`. The validated frontmatter dict is then stored as-is.
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
-- rows:
--   ('schema_version', '1')
--   ('max_source_mtime_ns', '<integer-as-decimal-string>')  -- max st_mtime_ns across all indexed source files at rebuild
--   ('built_at', '<ISO-8601 UTC>')                          -- human-readable only; NOT used for staleness comparison
--   ('store_root', '<absolute path>')

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
    def is_stale(self) -> bool: ...                # current max st_mtime_ns vs schema_meta.max_source_mtime_ns
```

**Semantics:**
- Always full rebuild — drop tables, recreate, repopulate. Phase B does not implement incremental updates.
- Per-entity errors are **collected**, not raised; the registry still indexes successful entities. CLI prints a non-zero exit if `errors` is non-empty.
- Atomic write: build into a unique temp file inside the store dir (`tempfile.NamedTemporaryFile(dir=root, prefix='.registry-', suffix='.sqlite', delete=False)`), `fsync`, then `os.replace()` onto `registry.sqlite`. Multiple concurrent explicit rebuilds do not collide on a fixed temp name; the second rename wins atomically.
- `is_stale()` compares `max(os.stat(p).st_mtime_ns for p in source_files)` against the integer stored in `schema_meta.max_source_mtime_ns`. Returns `True` if the registry is missing, the meta row is missing, or current max exceeds stored max. Nanosecond integers avoid float-precision and timezone bugs.

**Staleness handling (no auto-rebuild in Phase B):**
- Queries do **not** mutate state. `query.py` calls `is_stale()` before each query; if stale, emits a one-line warning to stderr — `"warning: registry is stale (N source files newer than last rebuild); run `science commons index rebuild`"` — then queries the existing index against possibly-stale data.
- This deliberately removes the concurrency footgun a transparent auto-rebuild would introduce (two `find` processes racing on the same temp file + rename). Phase E adds proper auto-rebuild with a writer lock when migration traffic justifies it.
- `SCIENCE_COMMONS_QUIET_STALE=1` suppresses the stderr warning (CI / scripted use).

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
- Each query checks `is_stale()` first; if stale, emits the stderr warning (per §5.4) and continues querying — no rebuild.

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

## 7. Inventory integration — deferred to Phase D

`inventory_v1`'s contract assumes a single project root (`project_path`) and resolves source paths as `project_root / source.path` (per the dashboard-consumption design at `docs/plans/2026-05-12-science-entity-inventory-and-dashboard-consumption.md`). Commons-rooted paths do not fit either branch of that resolution: relative-to-commons-root produces wrong paths under `project_root /`, and absolute paths break `compute_content_hash`'s machine-portability guarantee (since `source` is included in the canonical-bytes hash). Either form is effectively a v1 contract change.

The right answer is to land shared rows in **`inventory_v2`** (Phase D), which already needs new structure for `overlays[]` and can carry the path semantics shared rows require. Phase B therefore does **not** modify `entities_inventory.py` and does **not** introduce a `--include-shared` flag. The CLI commands (`science commons {init, index rebuild, show, find, validate}`) operate against `registry.sqlite` directly and are the sole consumers of `CommonsEntityAdapter` until Phase D.

## 8. Testing strategy

**Per-module unit tests** under `science/model/tests/` or `science/tests/` as appropriate to where the code lives:

| Layer | What's tested |
| --- | --- |
| `commons/config.py` | YAML round-trip, env var override, default fallback. |
| `commons/bootstrap.py` | Directory creation, idempotence, refuse-on-malformed. |
| `commons/adapter.py` | Frontmatter parsing, pair invariant, profile validation, per-entity error wrapping, mtime_ns capture. |
| `commons/registry.py` | Schema creation, atomic rebuild via unique temp file, error collection, `is_stale()` semantics using `max_source_mtime_ns`. |
| `commons/query.py` | Each filter, AND-semantics across repeats, year range, slug-glob, stale-warning emission (and suppression via env var). |
| `commons/validator.py` | Walks store without registry; surfaces EntityValidator errors. |
| `commons/cli.py` | Typer CliRunner — arg parsing, exit codes, JSON output shape, `--project` rejection on `show`. |

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

No inventory-integration test in Phase B (inventory wiring is a Phase D concern, see §7).

## 9. Risks

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| `MarkdownAdapter` frontmatter helper isn't cleanly extractable | medium | Allowed fallback: vendor a thin re-implementation in `commons/adapter.py`. |
| `registry.sqlite` corruption mid-rebuild | low | Unique temp file per rebuild + atomic `os.replace()`. A second concurrent rebuild succeeds atomically (last writer wins); neither sees partial state. |
| Concurrent explicit `science commons index rebuild` calls | low | Each rebuild writes its own temp file (`.registry-XXX.sqlite`) and atomically replaces `registry.sqlite`. Wasted work, but no corruption and no lock needed. |
| Stale registry queried silently | medium | `is_stale()` warns to stderr before each query; user knows to run `science commons index rebuild`. Phase E adds auto-rebuild + writer lock. |
| Performance: stat-walking the store on every query | low | Phase B store is small; full mtime walk is cheap. Re-evaluate when Phase E lands real volume. |
| Existing `~/d/science-commons/` from prior experiments | low | `science commons init` refuses to operate on a non-empty path that doesn't match layout. |

## 10. Deliverables checklist

1. `~/d/science-commons/` bootstrappable via `science commons init`.
2. `CommonsEntityAdapter`, `RegistryBuilder`, `CommonsQuery`, `CommonsValidator` working against fixtures and an empty real store.
3. `science commons {init, index rebuild, show, find, validate}` subcommands wired in.
4. `~/.config/science/config.yaml` extended with optional `commons.root`.
5. Test fixtures under `science/model/tests/fixtures/commons/{valid,invalid}/`.
6. Test coverage: per-module unit tests. No inventory-integration test (deferred to Phase D per §7).

## 11. Follow-on phases

- **Phase C — Data resolver.** Reuses `CommonsEntityAdapter` to locate `datapackage.yaml`. Adds `$SCIENCE_COMMONS_DATA_ROOT`, hash verification, `science commons data {resolve, fetch}`.
- **Phase D — Overlay merge + inventory_v2.** Adds `OverlayAdapter`, extends the registry with an `overlays` table, introduces `inventory_v2` with the top-level `overlays[]` field and the path-semantics needed to carry commons-rooted source paths. Adds `--include-shared` (or its v2-named equivalent) to the inventory builder so shared entities flow to consumers. Defines the `CommonsEntityRecord → InventoryEntity` projection (synthetic defaults for `project`, `related`, `source_refs`, `content_preview`, `file_path`; `scope=EntityScope.SHARED`). Enables `science commons show --project <name>` and overlay-aware rendering.
- **Phase E/F/G — Migration.** `science promote` writes into `.migrations/`, calls `RegistryBuilder.rebuild()` after each promotion.

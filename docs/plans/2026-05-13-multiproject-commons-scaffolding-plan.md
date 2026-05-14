# Phase B (Commons Scaffolding) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `~/d/science-commons/` as a queryable, validatable, CLI-accessible store for shared entities (datasets, papers, topics, themes) with a SQLite index and the `science commons {init, index rebuild, show, find, validate}` command surface. No inventory integration, no overlays, no data resolver — those are Phases C/D/E.

**Architecture:** New subpackage `science_tool.commons` with focused modules (errors, config, bootstrap, adapter, registry, query, validator, cli). The adapter walks `~/d/science-commons/` and yields `CommonsEntityRecord`s holding validated schema frontmatter (no `Entity` materialization in Phase B). The registry is a regenerable SQLite index with three tables; queries warn-but-don't-mutate on staleness. CLI is Click, registered into the existing `science_tool.cli.main` group.

**Tech Stack:** Python 3.11+, Click 8.1, Pydantic 2, jsonschema 4.26, pyyaml 6.0.3, sqlite3 (stdlib), pytest. Reuses Phase A's `science_model.entity_schema.EntityValidator` and the existing `science_tool.markdown_utils.parse_frontmatter` helper.

**Spec:** `docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md`

---

## File Structure

### New files

```
science/src/science_tool/commons/
├── __init__.py                      # public surface (final re-exports added in Task 16)
├── errors.py                        # CommonsError hierarchy
├── config.py                        # CommonsSettings + resolve_commons_root
├── bootstrap.py                     # init_commons
├── adapter.py                       # CommonsEntityRecord + CommonsEntityAdapter
├── registry.py                      # RegistryBuilder + RebuildReport + schema_meta helpers
├── query.py                         # CommonsQuery
├── validator.py                     # CommonsValidator + ValidationReport
└── cli.py                           # commons_group (Click) — init / index / show / find / validate
```

### Modified files

- `science/src/science_tool/registry/config.py` — add `commons: CommonsSettings` field to `GlobalConfig` (Task 2)
- `science/src/science_tool/cli.py` — `main.add_command(commons_group)` (Task 16)

### New test files (under `science/tests/`)

- `test_commons_config.py`
- `test_commons_bootstrap.py`
- `test_commons_adapter.py`
- `test_commons_registry.py`
- `test_commons_query.py`
- `test_commons_validator.py`
- `test_commons_cli.py`

### Test fixtures (under `science/tests/fixtures/commons/`)

Per the spec §8, fixtures could live under `science/model/tests/fixtures/commons/`. We place them in `science/tests/fixtures/commons/` instead so they sit next to their only consumer (the `science_tool` test suite). The deviation is purely organizational; the fixtures themselves are unchanged.

```
science/tests/fixtures/commons/
├── valid/
│   ├── datasets/cath-domains/{entity.md, datapackage.yaml}
│   ├── datasets/rnaseq-example/{entity.md, datapackage.yaml}
│   ├── papers/Adams2025.md
│   ├── topics/single-cell-foundation-models.md
│   └── themes/research-hygiene.md
└── invalid/
    ├── dataset-missing-datapackage/datasets/no-dp/entity.md
    ├── paper-bad-bibkey/papers/badname.md
    └── topic-bad-profile/topics/x.md
```

### Conventions

- Test invocation: `cd ~/d/science/science && uv run pytest <path>::<name> -v`
- All commits target the current working branch (the implementer should create a feature branch before Task 1 if not already on one — see Pre-task note below).
- Each task has its own commit; no batching.

### Pre-task note (controller / implementer)

Before Task 1, ensure the implementation runs on a fresh feature branch off `main` (e.g., `feat/commons-scaffolding`). Each task commits onto that branch. After Task 16, the controller will hand off to `superpowers:finishing-a-development-branch` (or the equivalent).

---

## Task 1: Subpackage skeleton + error hierarchy

**Files:**
- Create: `science/src/science_tool/commons/__init__.py`
- Create: `science/src/science_tool/commons/errors.py`
- Create: `science/tests/test_commons_errors.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_errors.py`:

```python
"""Tests for science_tool.commons.errors."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
)


def test_all_errors_subclass_commons_error() -> None:
    assert issubclass(CommonsRootNotFoundError, CommonsError)
    assert issubclass(CommonsRootMalformedError, CommonsError)
    assert issubclass(CommonsLayoutError, CommonsError)
    assert issubclass(CommonsEntityError, CommonsError)
    assert issubclass(CommonsRegistryError, CommonsError)


def test_root_not_found_carries_path() -> None:
    err = CommonsRootNotFoundError(Path("/nope"))
    assert err.root == Path("/nope")
    assert "/nope" in str(err)


def test_root_malformed_lists_missing() -> None:
    err = CommonsRootMalformedError(Path("/x"), missing=["datasets", ".git"])
    assert err.root == Path("/x")
    assert err.missing == ["datasets", ".git"]
    assert "datasets" in str(err)
    assert ".git" in str(err)


def test_layout_error_carries_path_and_reason() -> None:
    err = CommonsLayoutError(Path("/x/datasets/foo"), reason="missing datapackage.yaml sibling")
    assert err.path == Path("/x/datasets/foo")
    assert "missing datapackage.yaml sibling" in str(err)


def test_entity_error_wraps_cause() -> None:
    inner = ValueError("bad yaml")
    err = CommonsEntityError(Path("/x/papers/bad.md"), canonical_id="paper:bad", cause=inner)
    assert err.path == Path("/x/papers/bad.md")
    assert err.canonical_id == "paper:bad"
    assert err.cause is inner
    assert "bad.md" in str(err)


def test_entity_error_allows_unknown_canonical_id() -> None:
    err = CommonsEntityError(Path("/x/papers/bad.md"), canonical_id=None, cause=RuntimeError("x"))
    assert err.canonical_id is None


def test_registry_error_carries_db_path() -> None:
    inner = RuntimeError("locked")
    err = CommonsRegistryError(Path("/x/registry.sqlite"), cause=inner)
    assert err.db_path == Path("/x/registry.sqlite")
    assert err.cause is inner
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.commons'`

- [ ] **Step 3: Create the subpackage skeleton**

Create `science/src/science_tool/commons/__init__.py`:

```python
"""Shared knowledge store (commons) for Science multi-project entities.

Phase B (scaffolding): directory bootstrap, schema-validated entity adapter,
SQLite index, and CLI surface for `science commons {init, index rebuild,
show, find, validate}`. No inventory integration, no overlay merge, no data
resolver — those land in Phases C/D/E.

See docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md.
"""

from __future__ import annotations
```

- [ ] **Step 4: Create the error hierarchy**

Create `science/src/science_tool/commons/errors.py`:

```python
"""Error hierarchy for the commons subpackage."""

from __future__ import annotations

from pathlib import Path


class CommonsError(Exception):
    """Base class for all commons-layer errors."""


class CommonsRootNotFoundError(CommonsError):
    """The configured commons store root does not exist on disk."""

    def __init__(self, root: Path) -> None:
        super().__init__(
            f"commons store not found at {root}; run `science commons init` to create it"
        )
        self.root = root


class CommonsRootMalformedError(CommonsError):
    """The root exists but does not look like a commons store."""

    def __init__(self, root: Path, *, missing: list[str]) -> None:
        super().__init__(
            f"commons store at {root} is malformed; missing: {', '.join(missing)}"
        )
        self.root = root
        self.missing = missing


class CommonsLayoutError(CommonsError):
    """Filesystem layout invariant violated (e.g., dataset missing datapackage.yaml)."""

    def __init__(self, path: Path, *, reason: str) -> None:
        super().__init__(f"commons layout error at {path}: {reason}")
        self.path = path
        self.reason = reason


class CommonsEntityError(CommonsError):
    """A single entity failed parsing or schema validation."""

    def __init__(
        self,
        path: Path,
        *,
        canonical_id: str | None,
        cause: Exception,
    ) -> None:
        super().__init__(f"commons entity {path} failed: {cause}")
        self.path = path
        self.canonical_id = canonical_id
        self.cause = cause


class CommonsRegistryError(CommonsError):
    """SQLite-level failure (corruption, locked file, schema mismatch)."""

    def __init__(self, db_path: Path, *, cause: Exception) -> None:
        super().__init__(f"commons registry at {db_path} failed: {cause}")
        self.db_path = db_path
        self.cause = cause
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_errors.py -v`
Expected: PASS — 6 passed

- [ ] **Step 6: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/__init__.py src/science_tool/commons/errors.py tests/test_commons_errors.py
git commit -m "feat(commons): add subpackage skeleton + error hierarchy"
```

---

## Task 2: Config — extend GlobalConfig + resolver

**Files:**
- Create: `science/src/science_tool/commons/config.py`
- Modify: `science/src/science_tool/registry/config.py` (add `commons: CommonsSettings` to `GlobalConfig`)
- Create: `science/tests/test_commons_config.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_config.py`:

```python
"""Tests for science_tool.commons.config."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.commons.config import CommonsSettings, resolve_commons_root
from science_tool.registry.config import GlobalConfig, load_global_config, save_global_config


def test_default_settings_root_is_none() -> None:
    assert CommonsSettings().root is None


def test_global_config_includes_commons_with_default() -> None:
    cfg = GlobalConfig()
    assert isinstance(cfg.commons, CommonsSettings)
    assert cfg.commons.root is None


def test_global_config_roundtrip_with_commons(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.dump(
            {
                "sync": {"stale_after_days": 14},
                "projects": [],
                "commons": {"root": "/tmp/example-commons"},
            }
        ),
        encoding="utf-8",
    )
    cfg = load_global_config(cfg_path)
    assert cfg.commons.root == Path("/tmp/example-commons")
    save_global_config(cfg, cfg_path)
    reloaded = load_global_config(cfg_path)
    assert reloaded.commons.root == Path("/tmp/example-commons")


def test_global_config_missing_commons_block_uses_default(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({"sync": {"stale_after_days": 14}, "projects": []}), encoding="utf-8")
    cfg = load_global_config(cfg_path)
    assert cfg.commons.root is None


def test_resolve_env_var_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "from-env"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert resolve_commons_root() == tmp_path / "from-env"


def test_resolve_config_used_when_env_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_ROOT", raising=False)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump({"commons": {"root": str(tmp_path / "from-config")}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert resolve_commons_root() == tmp_path / "from-config"


def test_resolve_default_when_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_ROOT", raising=False)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()  # empty config dir
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    expected = tmp_path / "home" / "d" / "science-commons"
    assert resolve_commons_root() == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'CommonsSettings' from 'science_tool.commons.config'`

- [ ] **Step 3: Create the commons config module**

Create `science/src/science_tool/commons/config.py`:

```python
"""Commons-store configuration: settings model + root resolver."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel


class CommonsSettings(BaseModel):
    """Settings for the shared knowledge store."""

    root: Path | None = None  # None means "use built-in default"


def resolve_commons_root() -> Path:
    """Resolve the commons store root.

    Discovery order:
    1. `$SCIENCE_COMMONS_ROOT` environment variable.
    2. `commons.root` in the global config file.
    3. Default: `~/d/science-commons/`.
    """
    if env := os.environ.get("SCIENCE_COMMONS_ROOT"):
        return Path(env).expanduser()

    from science_tool.registry.config import load_global_config

    cfg = load_global_config()
    if cfg.commons.root is not None:
        return Path(cfg.commons.root).expanduser()

    return Path.home() / "d" / "science-commons"
```

- [ ] **Step 4: Wire `CommonsSettings` into `GlobalConfig`**

Modify `science/src/science_tool/registry/config.py`. Import `CommonsSettings` from the commons subpackage at the top of the file (the one-way dependency does not create a cycle — `commons.config` only imports `load_global_config` lazily inside `resolve_commons_root`). Add this import near the existing pydantic import:

```python
from science_tool.commons.config import CommonsSettings
```

Then update `GlobalConfig` (currently around lines 55-59) to:

```python
class GlobalConfig(BaseModel):
    """Top-level configuration for Science multi-project sync."""

    sync: SyncSettings = Field(default_factory=SyncSettings)
    projects: list[RegisteredProject] = Field(default_factory=list)
    commons: CommonsSettings = Field(default_factory=CommonsSettings)
```

Do not redefine `CommonsSettings` here. There is one class — the test in step 1 asserts `isinstance(cfg.commons, CommonsSettings)` using the import from `science_tool.commons.config`, and `GlobalConfig` must reference that same class for the check to pass.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_config.py -v`
Expected: PASS — 7 passed

- [ ] **Step 6: Run the existing registry/config test suite to confirm no regressions**

Run: `cd ~/d/science/science && uv run pytest tests/ -k "registry or config" -v`
Expected: All existing tests still pass.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/config.py src/science_tool/registry/config.py tests/test_commons_config.py
git commit -m "feat(commons): config — CommonsSettings + resolve_commons_root + GlobalConfig wiring"
```

---

## Task 3: Bootstrap — `init_commons`

**Files:**
- Create: `science/src/science_tool/commons/bootstrap.py`
- Create: `science/tests/test_commons_bootstrap.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_bootstrap.py`:

```python
"""Tests for science_tool.commons.bootstrap."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.bootstrap import init_commons
from science_tool.commons.errors import CommonsRootMalformedError


def test_init_creates_layout_in_empty_directory(tmp_path: Path) -> None:
    root = tmp_path / "new-commons"
    init_commons(root)
    assert root.is_dir()
    assert (root / ".git").is_dir()
    assert (root / ".gitignore").is_file()
    assert (root / "README.md").is_file()
    for sub in ("datasets", "papers", "topics", "themes"):
        assert (root / sub).is_dir()
        assert (root / sub / ".gitkeep").is_file()


def test_gitignore_excludes_registry_and_migrations(tmp_path: Path) -> None:
    root = tmp_path / "commons"
    init_commons(root)
    text = (root / ".gitignore").read_text(encoding="utf-8")
    assert "registry.sqlite" in text
    assert ".migrations/" in text
    assert "__pycache__/" in text


def test_init_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "commons"
    init_commons(root)
    readme_before = (root / "README.md").read_text(encoding="utf-8")
    init_commons(root)  # second call should not modify
    readme_after = (root / "README.md").read_text(encoding="utf-8")
    assert readme_before == readme_after


def test_init_refuses_non_empty_non_commons_dir(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    (root / "some-other-file.txt").write_text("hello")
    with pytest.raises(CommonsRootMalformedError) as exc_info:
        init_commons(root)
    assert "datasets" in exc_info.value.missing or ".git" in exc_info.value.missing


def test_init_force_skips_malformed_check(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    (root / "stray.txt").write_text("hello")
    init_commons(root, force=True)
    # After force-init, stray file is preserved and layout exists:
    assert (root / "stray.txt").is_file()
    assert (root / "datasets").is_dir()
    assert (root / ".git").is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_bootstrap.py -v`
Expected: FAIL — `ImportError: cannot import name 'init_commons'`

- [ ] **Step 3: Implement `init_commons`**

Create `science/src/science_tool/commons/bootstrap.py`:

```python
"""Bootstrap a new commons store on disk."""

from __future__ import annotations

import subprocess
from pathlib import Path

from science_tool.commons.errors import CommonsRootMalformedError

_TYPE_DIRS = ("datasets", "papers", "topics", "themes")

_README_TEXT = """# Science Commons

This directory is a shared knowledge store for the Science framework. It holds
curated, citable entities — datasets, papers, topics, themes — consumed across
projects via the `science commons` CLI.

Files are the source of truth. `registry.sqlite` is a regenerable index built
by `science commons index rebuild`; `.migrations/` is an audit log written by
`science promote` (Phase E and later). Both are gitignored.

See `~/d/science/docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md`
for the design.
"""

_GITIGNORE_TEXT = """# Regenerable index (rebuild from filesystem with `science commons index rebuild`)
registry.sqlite
registry.sqlite-journal
.registry-*.sqlite

# Promotion audit log (written by `science promote`, Phase E+)
.migrations/

# Python build artifacts
__pycache__/
"""


def _has_layout(root: Path) -> list[str]:
    """Return the list of expected layout entries that are missing under root."""
    missing: list[str] = []
    if not (root / ".git").is_dir():
        missing.append(".git")
    for sub in _TYPE_DIRS:
        if not (root / sub).is_dir():
            missing.append(sub)
    return missing


def init_commons(root: Path, *, force: bool = False) -> None:
    """Create or verify the commons store layout at `root`.

    - If `root` does not exist, create it and the full layout.
    - If `root` exists and has the layout, no-op (idempotent).
    - If `root` exists but lacks the layout, raise CommonsRootMalformedError
      unless `force=True`.
    """
    if root.exists():
        missing = _has_layout(root)
        if not missing:
            return  # already initialized
        if not force and any(root.iterdir()):
            raise CommonsRootMalformedError(root, missing=missing)
    else:
        root.mkdir(parents=True)

    if not (root / ".git").is_dir():
        subprocess.run(
            ["git", "init", "--quiet", str(root)],
            check=True,
        )

    readme = root / "README.md"
    if not readme.is_file():
        readme.write_text(_README_TEXT, encoding="utf-8")

    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        gitignore.write_text(_GITIGNORE_TEXT, encoding="utf-8")

    for sub in _TYPE_DIRS:
        sub_dir = root / sub
        sub_dir.mkdir(exist_ok=True)
        gitkeep = sub_dir / ".gitkeep"
        if not gitkeep.is_file():
            gitkeep.write_text("", encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_bootstrap.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/bootstrap.py tests/test_commons_bootstrap.py
git commit -m "feat(commons): bootstrap — init_commons creates store layout"
```

---

## Task 4: Test fixtures

**Files:**
- Create: `science/tests/fixtures/commons/valid/datasets/cath-domains/entity.md`
- Create: `science/tests/fixtures/commons/valid/datasets/cath-domains/datapackage.yaml`
- Create: `science/tests/fixtures/commons/valid/datasets/rnaseq-example/entity.md`
- Create: `science/tests/fixtures/commons/valid/datasets/rnaseq-example/datapackage.yaml`
- Create: `science/tests/fixtures/commons/valid/papers/Adams2025.md`
- Create: `science/tests/fixtures/commons/valid/topics/single-cell-foundation-models.md`
- Create: `science/tests/fixtures/commons/valid/themes/research-hygiene.md`
- Create: `science/tests/fixtures/commons/invalid/dataset-missing-datapackage/datasets/no-dp/entity.md`
- Create: `science/tests/fixtures/commons/invalid/paper-bad-bibkey/papers/badname.md`
- Create: `science/tests/fixtures/commons/invalid/topic-bad-profile/topics/x.md`
- Create: `science/tests/fixtures/commons/README.md`
- Create: `science/tests/test_commons_fixtures.py`

This task has no TDD loop in the implementation sense — the fixtures ARE test infrastructure. The "test" is a sanity check that each `valid/` entity round-trips through Phase A's `EntityValidator` and each `invalid/` entity fails for the reason its directory name claims.

- [ ] **Step 1: Write the verification test**

Create `science/tests/test_commons_fixtures.py`:

```python
"""Sanity checks: commons test fixtures match the labels on their directories."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_model.entity_schema import EntityValidationError, EntityValidator

FIXTURES = Path(__file__).parent / "fixtures" / "commons"
VALID = FIXTURES / "valid"
INVALID = FIXTURES / "invalid"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} missing frontmatter")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_fixtures_dir_exists() -> None:
    assert VALID.is_dir()
    assert INVALID.is_dir()


@pytest.mark.parametrize(
    "rel_path",
    [
        "datasets/cath-domains/entity.md",
        "datasets/rnaseq-example/entity.md",
        "papers/Adams2025.md",
        "topics/single-cell-foundation-models.md",
        "themes/research-hygiene.md",
    ],
)
def test_valid_fixtures_validate(rel_path: str) -> None:
    validator = EntityValidator()
    validator.validate(_frontmatter(VALID / rel_path))


def test_dataset_missing_datapackage_lacks_sibling() -> None:
    entity = INVALID / "dataset-missing-datapackage" / "datasets" / "no-dp" / "entity.md"
    assert entity.is_file()
    assert not (entity.parent / "datapackage.yaml").exists()
    # Frontmatter itself is schema-valid; the failure is filesystem layout.
    EntityValidator().validate(_frontmatter(entity))


def test_paper_bad_bibkey_fails_schema() -> None:
    fm = _frontmatter(INVALID / "paper-bad-bibkey" / "papers" / "badname.md")
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(fm)


def test_topic_bad_profile_fails_schema() -> None:
    fm = _frontmatter(INVALID / "topic-bad-profile" / "topics" / "x.md")
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(fm)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_fixtures.py -v`
Expected: FAIL — fixture directory does not exist.

- [ ] **Step 3: Create the README**

Create `science/tests/fixtures/commons/README.md`:

```markdown
# Commons test fixtures

Synthetic stores used by Phase B's commons-layer tests. Each directory under
`valid/` is a self-contained snippet of a `~/d/science-commons/` store laid
out exactly as the real one would be. Directories under `invalid/` capture
one specific failure mode per directory; the directory name describes the
expected failure.

Tests in `science/tests/test_commons_*.py` copy from these into a `tmp_path`
to avoid mutating the fixtures.
```

- [ ] **Step 4: Create dataset fixtures**

Create `science/tests/fixtures/commons/valid/datasets/cath-domains/entity.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:cath-domains"
type: "dataset"
title: "CATH domain database"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
datapackage: "datapackage.yaml"
origin: "external"
tier: "use-now"
access:
  level: "public"
  verified: true
  source_url: "https://www.cathdb.info/"
accessions: ["CATH:v4_3_0"]
ontology_terms: []
tags: ["structure", "domain"]
---

# CATH domain database

Hierarchical classification of protein domain structures.
```

Create `science/tests/fixtures/commons/valid/datasets/cath-domains/datapackage.yaml`:

```yaml
name: cath-domains
profile: "data-package"
resources:
  - name: cath_domains
    path: cath_domains.parquet
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 4521339201
    format: "parquet"
```

Create `science/tests/fixtures/commons/valid/datasets/rnaseq-example/entity.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0"
id: "dataset:rnaseq-example"
type: "dataset"
title: "Example bulk RNA-seq dataset"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
datapackage: "datapackage.yaml"
origin: "external"
tier: "use-now"
access:
  level: "public"
  verified: true
  source_url: "https://example.org/rnaseq"
species: "Homo sapiens"
assay: "bulk-rnaseq"
ontology_terms: ["UBERON:0000178"]
tags: ["rnaseq", "bulk"]
---

# Example bulk RNA-seq dataset

Sample bulk RNA-seq from whole blood.
```

Create `science/tests/fixtures/commons/valid/datasets/rnaseq-example/datapackage.yaml`:

```yaml
name: rnaseq-example
profile: "data-package"
resources:
  - name: counts
    path: counts.parquet
    hash: "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    bytes: 12345678
    format: "parquet"
```

- [ ] **Step 5: Create paper/topic/theme fixtures**

Create `science/tests/fixtures/commons/valid/papers/Adams2025.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+paper/1.0"
id: "paper:Adams2025"
type: "paper"
title: "A representative paper about homology-aware evaluation"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
bibkey: "Adams2025"
authors: ["Adams, A.", "Baker, B."]
year: 2025
journal: "Nature Methods"
doi: "10.1038/example"
url: "https://example.org/Adams2025"
ontology_terms: []
tags: ["evaluation", "homology"]
---

# A representative paper about homology-aware evaluation

Sample paper abstract.
```

Create `science/tests/fixtures/commons/valid/topics/single-cell-foundation-models.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+topic/1.0"
id: "topic:single-cell-foundation-models"
type: "topic"
title: "Single-cell foundation models"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
ontology_terms: ["UBERON:0000178"]
tags: ["single-cell", "foundation-model"]
---

# Single-cell foundation models

Topic body.
```

Create `science/tests/fixtures/commons/valid/themes/research-hygiene.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+theme/1.0"
id: "theme:research-hygiene"
type: "theme"
title: "Research hygiene"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
theme_kind: "methodology"
theme_scope: "cross-domain"
ontology_terms: []
tags: ["methodology"]
---

# Research hygiene

Theme body.
```

- [ ] **Step 6: Create invalid fixtures**

Create `science/tests/fixtures/commons/invalid/dataset-missing-datapackage/datasets/no-dp/entity.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:no-dp"
type: "dataset"
title: "Dataset whose datapackage.yaml sibling is missing"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
datapackage: "datapackage.yaml"
origin: "external"
tier: "use-now"
access:
  level: "public"
  verified: true
  source_url: "https://example.org"
ontology_terms: []
tags: []
---

# No datapackage

Frontmatter is valid but the sibling datapackage.yaml is absent on disk.
```

Create `science/tests/fixtures/commons/invalid/paper-bad-bibkey/papers/badname.md`:

```markdown
---
schema_profile: "science-entity-base/1.0+paper/1.0"
id: "paper:badname"
type: "paper"
title: "Paper with non-camelcase bibkey"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
bibkey: "badname"
authors: ["X"]
year: 2025
journal: "Test"
ontology_terms: []
tags: []
---

# Bad bibkey

`bibkey` and `id` slug do not match the camelcase regex (e.g., `Adams2025`).
```

Create `science/tests/fixtures/commons/invalid/topic-bad-profile/topics/x.md`:

```markdown
---
schema_profile: "not-a-real-profile/1.0"
id: "topic:x"
type: "topic"
title: "Topic with an unrecognized schema profile"
version: "1.0.0"
status: "active"
created: "2026-05-13"
updated: "2026-05-13"
ontology_terms: []
tags: []
---

# Bad profile

`schema_profile` does not start with `science-entity-base`.
```

- [ ] **Step 7: Run sanity test**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_fixtures.py -v`
Expected: PASS — all parametrized valid fixtures validate, and all three invalid markers fail or lack their sibling as documented.

- [ ] **Step 8: Commit**

```bash
cd ~/d/science/science
git add tests/fixtures/commons tests/test_commons_fixtures.py
git commit -m "test(commons): add valid/invalid store fixtures"
```

---

## Task 5: Adapter — record + scan walking

**Files:**
- Create: `science/src/science_tool/commons/adapter.py` (partial — record + walking, no parsing)
- Create: `science/tests/test_commons_adapter.py`

- [ ] **Step 1: Write the failing test (walking + layout invariant)**

Create `science/tests/test_commons_adapter.py`:

```python
"""Tests for science_tool.commons.adapter."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError, CommonsLayoutError

FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _make_store(tmp_path: Path, source_subdir: str) -> Path:
    """Copy a fixture subtree into tmp_path/commons and return that root."""
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / source_subdir, root)
    return root


def test_scan_yields_records_for_all_valid_entities(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    canonical_ids = {r.canonical_id for r in records}
    assert canonical_ids == {
        "dataset:cath-domains",
        "dataset:rnaseq-example",
        "paper:Adams2025",
        "topic:single-cell-foundation-models",
        "theme:research-hygiene",
    }
    assert errors == []


def test_scan_skips_hidden_and_meta_files(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    # Sprinkle distractors
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("ignore me")
    (root / ".migrations").mkdir()
    (root / ".migrations" / "log.json").write_text("[]")
    (root / "registry.sqlite").write_text("ignore me")
    (root / "datasets" / "__pycache__").mkdir()
    (root / "datasets" / "__pycache__" / "x.pyc").write_text("x")

    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    assert len(records) == 5  # same as the clean valid case


def test_scan_raises_layout_error_for_dataset_missing_datapackage(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "invalid/dataset-missing-datapackage")
    adapter = CommonsEntityAdapter(root)
    with pytest.raises(CommonsLayoutError) as exc_info:
        list(adapter.scan())
    assert "datapackage.yaml" in exc_info.value.reason
    assert exc_info.value.path == root / "datasets" / "no-dp"


def test_record_captures_paths_and_mtime(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    by_id = {
        r.canonical_id: r
        for r in adapter.scan()
        if isinstance(r, CommonsEntityRecord)
    }
    cath = by_id["dataset:cath-domains"]
    assert cath.body_path == root / "datasets" / "cath-domains" / "entity.md"
    assert cath.datapackage_path == root / "datasets" / "cath-domains" / "datapackage.yaml"
    assert cath.type == "dataset"
    assert cath.slug == "cath-domains"
    assert cath.mtime_ns > 0

    paper = by_id["paper:Adams2025"]
    assert paper.body_path == root / "papers" / "Adams2025.md"
    assert paper.datapackage_path is None
    assert paper.type == "paper"
    assert paper.slug == "Adams2025"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_adapter.py -v`
Expected: FAIL — `ImportError: cannot import name 'CommonsEntityAdapter'`

- [ ] **Step 3: Implement the adapter (walking only, no parsing yet)**

Create `science/src/science_tool/commons/adapter.py`:

```python
"""Walk a commons store and produce validated entity records.

In Phase B the adapter parses frontmatter, validates against
Phase A's EntityValidator, and emits CommonsEntityRecord (or
CommonsEntityError) per entity. The validated frontmatter dict is
carried as-is — no `science_model.Entity` materialization (deferred
to Phase D, see the design spec).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.errors import CommonsEntityError, CommonsLayoutError

_TYPE_DIRS = ("datasets", "papers", "topics", "themes")
_SKIP_NAMES = frozenset({".git", ".migrations", "__pycache__", "registry.sqlite"})


@dataclass(frozen=True, slots=True)
class CommonsEntityRecord:
    """One validated entity from the commons store."""

    canonical_id: str           # "<type>:<slug>", e.g. "dataset:cath-domains"
    type: str                   # "dataset" | "paper" | "topic" | "theme"
    slug: str
    schema_profile: str
    frontmatter: dict[str, Any]  # validated against schema_profile
    body_path: Path             # absolute path to entity.md
    datapackage_path: Path | None  # sibling datapackage.yaml (datasets only)
    mtime_ns: int               # max st_mtime_ns over (body_path, datapackage_path)


class CommonsEntityAdapter:
    """Walk the commons store and yield records or per-entity errors."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def scan(self) -> Iterator[CommonsEntityRecord | CommonsEntityError]:
        for type_name in _TYPE_DIRS:
            type_dir = self._root / type_name
            if not type_dir.is_dir():
                continue
            yield from self._scan_type(type_name, type_dir)

    def _scan_type(
        self, type_name: str, type_dir: Path
    ) -> Iterator[CommonsEntityRecord | CommonsEntityError]:
        if type_name == "datasets":
            for child in sorted(type_dir.iterdir()):
                if child.name in _SKIP_NAMES or child.name.startswith("."):
                    continue
                if not child.is_dir():
                    continue
                entity_path = child / "entity.md"
                dp_path = child / "datapackage.yaml"
                if not entity_path.is_file():
                    # Empty dataset directory (e.g., .gitkeep'd); skip silently.
                    continue
                if not dp_path.is_file():
                    raise CommonsLayoutError(
                        child,
                        reason=f"dataset directory missing required datapackage.yaml sibling",
                    )
                yield self._make_record(type_name, child.name, entity_path, dp_path)
        else:
            for child in sorted(type_dir.iterdir()):
                if child.name in _SKIP_NAMES or child.name.startswith("."):
                    continue
                if child.is_dir():
                    continue
                if child.suffix != ".md":
                    continue
                slug = child.stem
                yield self._make_record(type_name, slug, child, None)

    def _make_record(
        self,
        type_dir: str,
        slug: str,
        body_path: Path,
        datapackage_path: Path | None,
    ) -> CommonsEntityRecord | CommonsEntityError:
        # Parsing/validation arrives in Task 6. For now, build a stub record so
        # the walking tests pass.
        canonical_id = f"{_TYPE_DIR_TO_TYPE[type_dir]}:{slug}"
        mtime_ns = body_path.stat().st_mtime_ns
        if datapackage_path is not None:
            mtime_ns = max(mtime_ns, datapackage_path.stat().st_mtime_ns)
        return CommonsEntityRecord(
            canonical_id=canonical_id,
            type=_TYPE_DIR_TO_TYPE[type_dir],
            slug=slug,
            schema_profile="",  # filled in Task 6
            frontmatter={},     # filled in Task 6
            body_path=body_path,
            datapackage_path=datapackage_path,
            mtime_ns=mtime_ns,
        )


_TYPE_DIR_TO_TYPE = {
    "datasets": "dataset",
    "papers": "paper",
    "topics": "topic",
    "themes": "theme",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_adapter.py -v`
Expected: PASS — 4 passed (walking + layout-invariant tests; parsing not yet exercised).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/adapter.py tests/test_commons_adapter.py
git commit -m "feat(commons): adapter — record dataclass + filesystem walk + dataset layout invariant"
```

---

## Task 6: Adapter — frontmatter parsing + schema validation

**Files:**
- Modify: `science/src/science_tool/commons/adapter.py` (fill in `_make_record` with parsing + validation)
- Modify: `science/tests/test_commons_adapter.py` (add parsing assertions + invalid-fixture tests)

- [ ] **Step 1: Add the failing parsing tests**

Append to `science/tests/test_commons_adapter.py`:

```python
def test_scan_populates_frontmatter_and_schema_profile(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    by_id = {
        r.canonical_id: r
        for r in adapter.scan()
        if isinstance(r, CommonsEntityRecord)
    }
    paper = by_id["paper:Adams2025"]
    assert paper.schema_profile == "science-entity-base/1.0+paper/1.0"
    assert paper.frontmatter["bibkey"] == "Adams2025"
    assert paper.frontmatter["year"] == 2025

    rnaseq = by_id["dataset:rnaseq-example"]
    assert rnaseq.schema_profile.endswith("+bio.rnaseq/1.0")
    assert rnaseq.frontmatter["species"] == "Homo sapiens"


def test_scan_yields_error_for_bad_bibkey(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "invalid/paper-bad-bibkey")
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    assert records == []
    assert len(errors) == 1
    assert errors[0].path == root / "papers" / "badname.md"


def test_scan_yields_error_for_bad_schema_profile(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "invalid/topic-bad-profile")
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    assert len(errors) == 1
    assert errors[0].path == root / "topics" / "x.md"


def test_scan_continues_after_per_entity_error(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    # Inject a bad paper alongside good ones
    bad = root / "papers" / "badname.md"
    bad.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "badname"\n'  # invalid casing
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    # Adams2025 still parses; badname yields an error
    assert "paper:Adams2025" in {r.canonical_id for r in records}
    assert len(errors) == 1
    assert errors[0].path == bad


def test_scan_rejects_id_path_mismatch(tmp_path: Path) -> None:
    """A schema-valid paper at papers/Adams2025.md whose frontmatter says
    id: paper:Other2025 must be reported as an error — not silently indexed
    under the path-derived id."""
    root = _make_store(tmp_path, "valid")
    impostor = root / "papers" / "Adams2025.md"
    impostor.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:Other2025"\n'        # contradicts path-derived paper:Adams2025
        'type: "paper"\n'
        'title: "Impostor"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "Other2025"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    paper_records = [
        r for r in items
        if isinstance(r, CommonsEntityRecord) and r.type == "paper"
    ]
    paper_errors = [
        e for e in items
        if isinstance(e, CommonsEntityError) and e.path == impostor
    ]
    assert paper_records == [], "impostor should not appear in records"
    assert len(paper_errors) == 1
    assert "does not match path-derived" in str(paper_errors[0].cause)


def test_scan_rejects_type_path_mismatch(tmp_path: Path) -> None:
    """An entity in papers/Foo2025.md claiming type: dataset must error."""
    root = _make_store(tmp_path, "valid")
    impostor = root / "papers" / "Adams2025.md"
    impostor.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:Adams2025"\n'
        'type: "dataset"\n'              # contradicts path-derived type "paper"
        'title: "Misfiled"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "Adams2025"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    errors = [e for e in items if isinstance(e, CommonsEntityError) and e.path == impostor]
    # Either the schema mixin guards this directly, or our consistency check fires.
    # Either way, it must not appear as a record.
    assert errors, "type mismatch must produce an error"
    records = [r for r in items if isinstance(r, CommonsEntityRecord) and r.body_path == impostor]
    assert records == []
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_adapter.py -v`
Expected: 4 prior tests PASS; 4 new tests FAIL (schema_profile is empty, no validation happening).

- [ ] **Step 3: Implement parsing + validation**

Modify `science/src/science_tool/commons/adapter.py`. Update the import block and the `_make_record` method (and add helpers). Replace the existing module body with:

```python
"""Walk a commons store and produce validated entity records.

In Phase B the adapter parses frontmatter, validates against
Phase A's EntityValidator, and emits CommonsEntityRecord (or
CommonsEntityError) per entity. The validated frontmatter dict is
carried as-is — no `science_model.Entity` materialization (deferred
to Phase D, see the design spec).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_model.entity_schema import EntityValidationError, EntityValidator

from science_tool.commons.errors import CommonsEntityError, CommonsLayoutError
from science_tool.markdown_utils import parse_frontmatter

_TYPE_DIRS = ("datasets", "papers", "topics", "themes")
_SKIP_NAMES = frozenset({".git", ".migrations", "__pycache__", "registry.sqlite"})

_TYPE_DIR_TO_TYPE = {
    "datasets": "dataset",
    "papers": "paper",
    "topics": "topic",
    "themes": "theme",
}


@dataclass(frozen=True, slots=True)
class CommonsEntityRecord:
    """One validated entity from the commons store."""

    canonical_id: str
    type: str
    slug: str
    schema_profile: str
    frontmatter: dict[str, Any]
    body_path: Path
    datapackage_path: Path | None
    mtime_ns: int


class CommonsEntityAdapter:
    """Walk the commons store and yield records or per-entity errors."""

    def __init__(self, root: Path, validator: EntityValidator | None = None) -> None:
        self._root = root
        self._validator = validator or EntityValidator()

    def scan(self) -> Iterator[CommonsEntityRecord | CommonsEntityError]:
        for type_name in _TYPE_DIRS:
            type_dir = self._root / type_name
            if not type_dir.is_dir():
                continue
            yield from self._scan_type(type_name, type_dir)

    def _scan_type(
        self, type_name: str, type_dir: Path
    ) -> Iterator[CommonsEntityRecord | CommonsEntityError]:
        if type_name == "datasets":
            for child in sorted(type_dir.iterdir()):
                if child.name in _SKIP_NAMES or child.name.startswith("."):
                    continue
                if not child.is_dir():
                    continue
                entity_path = child / "entity.md"
                dp_path = child / "datapackage.yaml"
                if not entity_path.is_file():
                    continue
                if not dp_path.is_file():
                    raise CommonsLayoutError(
                        child,
                        reason="dataset directory missing required datapackage.yaml sibling",
                    )
                yield self._build(type_name, child.name, entity_path, dp_path)
        else:
            for child in sorted(type_dir.iterdir()):
                if child.name in _SKIP_NAMES or child.name.startswith("."):
                    continue
                if child.is_dir():
                    continue
                if child.suffix != ".md":
                    continue
                yield self._build(type_name, child.stem, child, None)

    def _build(
        self,
        type_dir: str,
        slug: str,
        body_path: Path,
        datapackage_path: Path | None,
    ) -> CommonsEntityRecord | CommonsEntityError:
        type_name = _TYPE_DIR_TO_TYPE[type_dir]
        canonical_id = f"{type_name}:{slug}"
        try:
            frontmatter, _ = parse_frontmatter(body_path)
            if not frontmatter:
                raise EntityValidationError(
                    f"{body_path} has no parseable frontmatter"
                )
            self._validator.validate(frontmatter)
            # Path/frontmatter consistency: an entity in papers/Adams2025.md
            # claiming id: paper:Other2025 must be a hard error, not silently
            # indexed under the path-derived id.
            declared_id = frontmatter.get("id")
            if declared_id != canonical_id:
                raise EntityValidationError(
                    f"frontmatter id {declared_id!r} does not match path-derived "
                    f"canonical id {canonical_id!r}"
                )
            declared_type = frontmatter.get("type")
            if declared_type != type_name:
                raise EntityValidationError(
                    f"frontmatter type {declared_type!r} does not match path-derived "
                    f"type {type_name!r}"
                )
        except EntityValidationError as exc:
            return CommonsEntityError(
                body_path, canonical_id=canonical_id, cause=exc
            )
        except Exception as exc:  # pragma: no cover — unexpected I/O / yaml errors
            return CommonsEntityError(
                body_path, canonical_id=canonical_id, cause=exc
            )

        mtime_ns = body_path.stat().st_mtime_ns
        if datapackage_path is not None:
            mtime_ns = max(mtime_ns, datapackage_path.stat().st_mtime_ns)
        return CommonsEntityRecord(
            canonical_id=canonical_id,
            type=type_name,
            slug=slug,
            schema_profile=str(frontmatter["schema_profile"]),
            frontmatter=frontmatter,
            body_path=body_path,
            datapackage_path=datapackage_path,
            mtime_ns=mtime_ns,
        )
```

- [ ] **Step 4: Run all adapter tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_adapter.py -v`
Expected: PASS — 8 tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/adapter.py tests/test_commons_adapter.py
git commit -m "feat(commons): adapter — frontmatter parsing + EntityValidator integration"
```

---

## Task 7: Adapter — `load()` single-entity lookup

**Files:**
- Modify: `science/src/science_tool/commons/adapter.py` (add `load`)
- Modify: `science/tests/test_commons_adapter.py` (add load tests)

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_commons_adapter.py`:

```python
def test_load_returns_record_for_known_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    record = adapter.load("paper:Adams2025")
    assert isinstance(record, CommonsEntityRecord)
    assert record.canonical_id == "paper:Adams2025"


def test_load_raises_entity_error_for_unknown_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    with pytest.raises(CommonsEntityError) as exc_info:
        adapter.load("paper:DoesNotExist")
    assert exc_info.value.canonical_id == "paper:DoesNotExist"


def test_load_raises_on_malformed_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    with pytest.raises(CommonsEntityError):
        adapter.load("not-a-canonical-id")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_adapter.py -v`
Expected: 3 new tests FAIL — `AttributeError: 'CommonsEntityAdapter' object has no attribute 'load'`.

- [ ] **Step 3: Implement `load`**

Add to `CommonsEntityAdapter` in `science/src/science_tool/commons/adapter.py`:

```python
    def load(self, canonical_id: str) -> CommonsEntityRecord:
        """Load one entity by canonical id. Raises CommonsEntityError on failure."""
        if ":" not in canonical_id:
            raise CommonsEntityError(
                self._root,
                canonical_id=canonical_id,
                cause=ValueError(
                    f"canonical id {canonical_id!r} is not in '<type>:<slug>' form"
                ),
            )
        type_name, slug = canonical_id.split(":", 1)
        type_dir = next(
            (k for k, v in _TYPE_DIR_TO_TYPE.items() if v == type_name),
            None,
        )
        if type_dir is None:
            raise CommonsEntityError(
                self._root,
                canonical_id=canonical_id,
                cause=ValueError(f"unknown entity type {type_name!r}"),
            )
        if type_dir == "datasets":
            body = self._root / "datasets" / slug / "entity.md"
            dp = self._root / "datasets" / slug / "datapackage.yaml"
        else:
            body = self._root / type_dir / f"{slug}.md"
            dp = None
        if not body.is_file():
            raise CommonsEntityError(
                body,
                canonical_id=canonical_id,
                cause=FileNotFoundError(str(body)),
            )
        result = self._build(type_dir, slug, body, dp)
        if isinstance(result, CommonsEntityError):
            raise result
        return result
```

- [ ] **Step 4: Run all adapter tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_adapter.py -v`
Expected: PASS — 11 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/adapter.py tests/test_commons_adapter.py
git commit -m "feat(commons): adapter — load() single-entity lookup with error semantics"
```

---

## Task 8: Registry — schema + meta helpers + rebuild

**Files:**
- Create: `science/src/science_tool/commons/registry.py`
- Create: `science/tests/test_commons_registry.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_registry.py`:

```python
"""Tests for science_tool.commons.registry."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import (
    REGISTRY_FILENAME,
    REGISTRY_SCHEMA_VERSION,
    RebuildReport,
    RegistryBuilder,
)

FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _make_store(tmp_path: Path, subdir: str = "valid") -> Path:
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / subdir, root)
    return root


def test_rebuild_creates_registry_file(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    assert (root / REGISTRY_FILENAME).is_file()


def test_rebuild_report_counts_indexed_entities(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    report = builder.rebuild()
    assert isinstance(report, RebuildReport)
    assert report.entities_indexed == 5
    assert report.errors == []
    assert report.duration_ms >= 0


def test_rebuild_populates_entities_table(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    conn = sqlite3.connect(root / REGISTRY_FILENAME)
    try:
        rows = conn.execute(
            "SELECT canonical_id, type, slug, title, schema_profile, datapackage_path "
            "FROM entities ORDER BY canonical_id"
        ).fetchall()
    finally:
        conn.close()
    by_id = {r[0]: r for r in rows}
    assert by_id["paper:Adams2025"][1] == "paper"
    assert by_id["paper:Adams2025"][2] == "Adams2025"
    assert by_id["dataset:cath-domains"][5] is not None  # datapackage_path
    assert by_id["paper:Adams2025"][5] is None


def test_rebuild_populates_tags_and_ontology_terms(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    conn = sqlite3.connect(root / REGISTRY_FILENAME)
    try:
        tag_rows = conn.execute(
            "SELECT canonical_id, tag FROM entity_tags WHERE canonical_id = ?",
            ("dataset:rnaseq-example",),
        ).fetchall()
        ont_rows = conn.execute(
            "SELECT canonical_id, term FROM entity_ontology_terms "
            "WHERE canonical_id = ?",
            ("dataset:rnaseq-example",),
        ).fetchall()
    finally:
        conn.close()
    assert {row[1] for row in tag_rows} == {"rnaseq", "bulk"}
    assert {row[1] for row in ont_rows} == {"UBERON:0000178"}


def test_rebuild_writes_schema_meta(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    conn = sqlite3.connect(root / REGISTRY_FILENAME)
    try:
        meta = dict(conn.execute("SELECT key, value FROM schema_meta").fetchall())
    finally:
        conn.close()
    assert meta["schema_version"] == REGISTRY_SCHEMA_VERSION
    assert meta["store_root"] == str(root.resolve())
    assert int(meta["source_count"]) > 0
    assert int(meta["max_source_mtime_ns"]) > 0
    assert len(meta["source_paths_digest"]) == 64  # sha256 hex
    assert "T" in meta["built_at"]  # ISO-8601


def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    first = builder.rebuild()
    second = builder.rebuild()
    assert first.entities_indexed == second.entities_indexed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_registry.py -v`
Expected: FAIL — `ImportError: cannot import name 'RegistryBuilder'`

- [ ] **Step 3: Implement the registry**

Create `science/src/science_tool/commons/registry.py`:

```python
"""SQLite index over a commons store.

The registry is regenerable: filesystem is the source of truth. Phase B
always does a full rebuild (drop + recreate); incremental rebuilds are
deferred to Phase E.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError, CommonsRegistryError

REGISTRY_FILENAME = "registry.sqlite"
REGISTRY_SCHEMA_VERSION = "1"

_DDL = """
CREATE TABLE schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE entities (
    canonical_id     TEXT PRIMARY KEY,
    type             TEXT NOT NULL,
    slug             TEXT NOT NULL,
    title            TEXT,
    schema_profile   TEXT NOT NULL,
    body_path        TEXT NOT NULL,
    datapackage_path TEXT,
    mtime_ns         INTEGER NOT NULL,
    frontmatter_json TEXT NOT NULL
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
    term         TEXT NOT NULL,
    PRIMARY KEY (canonical_id, term)
);
CREATE INDEX idx_entity_ontology_terms_term ON entity_ontology_terms (term);
"""


@dataclass(frozen=True)
class RebuildReport:
    entities_indexed: int
    errors: list[CommonsEntityError]
    duration_ms: int


class RegistryBuilder:
    """Build (and rebuild) the commons SQLite registry."""

    def __init__(self, root: Path, adapter: CommonsEntityAdapter) -> None:
        self._root = root
        self._adapter = adapter

    @property
    def db_path(self) -> Path:
        return self._root / REGISTRY_FILENAME

    def rebuild(self) -> RebuildReport:
        start = time.perf_counter()
        records: list[CommonsEntityRecord] = []
        errors: list[CommonsEntityError] = []
        for item in self._adapter.scan():
            if isinstance(item, CommonsEntityError):
                errors.append(item)
            else:
                records.append(item)

        # Write to a unique temp file, then atomically rename.
        with tempfile.NamedTemporaryFile(
            dir=self._root, prefix=".registry-", suffix=".sqlite", delete=False
        ) as handle:
            temp_path = Path(handle.name)
        try:
            conn = sqlite3.connect(temp_path)
            try:
                conn.executescript(_DDL)
                self._insert_records(conn, records)
                self._write_schema_meta(conn, records)
                conn.commit()
            finally:
                conn.close()
            temp_path.replace(self.db_path)
        except Exception as exc:
            if temp_path.exists():
                temp_path.unlink()
            raise CommonsRegistryError(self.db_path, cause=exc) from exc

        duration_ms = int((time.perf_counter() - start) * 1000)
        return RebuildReport(
            entities_indexed=len(records),
            errors=errors,
            duration_ms=duration_ms,
        )

    def _insert_records(
        self,
        conn: sqlite3.Connection,
        records: Iterable[CommonsEntityRecord],
    ) -> None:
        for record in records:
            body_rel = record.body_path.relative_to(self._root).as_posix()
            dp_rel = (
                record.datapackage_path.relative_to(self._root).as_posix()
                if record.datapackage_path is not None
                else None
            )
            conn.execute(
                "INSERT INTO entities (canonical_id, type, slug, title, schema_profile, "
                "body_path, datapackage_path, mtime_ns, frontmatter_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.canonical_id,
                    record.type,
                    record.slug,
                    record.frontmatter.get("title"),
                    record.schema_profile,
                    body_rel,
                    dp_rel,
                    record.mtime_ns,
                    json.dumps(record.frontmatter, sort_keys=True),
                ),
            )
            tags = record.frontmatter.get("tags") or []
            for tag in tags:
                conn.execute(
                    "INSERT OR IGNORE INTO entity_tags (canonical_id, tag) VALUES (?, ?)",
                    (record.canonical_id, str(tag)),
                )
            terms = record.frontmatter.get("ontology_terms") or []
            for term in terms:
                conn.execute(
                    "INSERT OR IGNORE INTO entity_ontology_terms (canonical_id, term) "
                    "VALUES (?, ?)",
                    (record.canonical_id, str(term)),
                )

    def _write_schema_meta(
        self,
        conn: sqlite3.Connection,
        records: list[CommonsEntityRecord],
    ) -> None:
        source_files = sorted(self._source_files())
        rel_posix = [p.relative_to(self._root).as_posix() for p in source_files]
        digest = hashlib.sha256("\n".join(rel_posix).encode("utf-8")).hexdigest()
        max_mtime = max((p.stat().st_mtime_ns for p in source_files), default=0)
        rows = {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "store_root": str(self._root.resolve()),
            "source_count": str(len(source_files)),
            "max_source_mtime_ns": str(max_mtime),
            "source_paths_digest": digest,
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        for key, value in rows.items():
            conn.execute(
                "INSERT INTO schema_meta (key, value) VALUES (?, ?)",
                (key, value),
            )

    def _source_files(self) -> list[Path]:
        """Same walk the adapter uses, but flattened to file paths."""
        from science_tool.commons.adapter import (
            _SKIP_NAMES,
            _TYPE_DIRS,
        )

        files: list[Path] = []
        for type_dir in _TYPE_DIRS:
            base = self._root / type_dir
            if not base.is_dir():
                continue
            if type_dir == "datasets":
                for child in base.iterdir():
                    if child.name in _SKIP_NAMES or child.name.startswith("."):
                        continue
                    if not child.is_dir():
                        continue
                    body = child / "entity.md"
                    dp = child / "datapackage.yaml"
                    if body.is_file():
                        files.append(body)
                    if dp.is_file():
                        files.append(dp)
            else:
                for child in base.iterdir():
                    if child.name in _SKIP_NAMES or child.name.startswith("."):
                        continue
                    if child.is_dir():
                        continue
                    if child.suffix != ".md":
                        continue
                    files.append(child)
        return files
```

- [ ] **Step 4: Run tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_registry.py -v`
Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/registry.py tests/test_commons_registry.py
git commit -m "feat(commons): registry — schema + rebuild + atomic write + schema_meta"
```

---

## Task 9: Registry — `is_stale()` for add / modify / delete / rename

**Files:**
- Modify: `science/src/science_tool/commons/registry.py` (add `is_stale`)
- Modify: `science/tests/test_commons_registry.py` (add staleness tests)

- [ ] **Step 1: Write failing tests**

Append to `science/tests/test_commons_registry.py`:

```python
def test_is_stale_false_immediately_after_rebuild(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    assert builder.is_stale() is False


def test_is_stale_true_when_registry_missing(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    assert builder.is_stale() is True


def test_is_stale_detects_file_modification(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    paper = root / "papers" / "Adams2025.md"
    # bump mtime by writing the same content one nanosecond later
    paper.write_text(paper.read_text(encoding="utf-8"), encoding="utf-8")
    import os
    os.utime(paper, ns=(paper.stat().st_atime_ns, paper.stat().st_mtime_ns + 1_000_000))
    assert builder.is_stale() is True


def test_is_stale_detects_addition(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    new_topic = root / "topics" / "another-topic.md"
    new_topic.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+topic/1.0"\n'
        'id: "topic:another-topic"\n'
        'type: "topic"\n'
        'title: "Another"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    assert builder.is_stale() is True


def test_is_stale_detects_deletion(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    (root / "topics" / "single-cell-foundation-models.md").unlink()
    assert builder.is_stale() is True


def test_is_stale_detects_rename(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    src = root / "topics" / "single-cell-foundation-models.md"
    dst = root / "topics" / "renamed-topic.md"
    # Keep mtime identical so only the path-digest signal fires
    src_mtime = src.stat().st_mtime_ns
    src.rename(dst)
    import os
    os.utime(dst, ns=(src_mtime, src_mtime))
    assert builder.is_stale() is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_registry.py -v`
Expected: 6 new tests FAIL — `AttributeError: 'RegistryBuilder' object has no attribute 'is_stale'`.

- [ ] **Step 3: Implement `is_stale`**

Add to `RegistryBuilder` in `science/src/science_tool/commons/registry.py`:

```python
    def is_stale(self) -> bool:
        """Return True if the registry needs a rebuild.

        Triggers on:
        1. Missing registry or missing schema_meta rows.
        2. source_count mismatch (add or delete).
        3. max source mtime advance (in-place modification).
        4. source_paths_digest mismatch (rename — count + mtime can both be
           unchanged).
        """
        if not self.db_path.is_file():
            return True
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                meta = dict(conn.execute("SELECT key, value FROM schema_meta").fetchall())
            finally:
                conn.close()
        except sqlite3.Error:
            return True
        required = (
            "source_count",
            "max_source_mtime_ns",
            "source_paths_digest",
        )
        if any(k not in meta for k in required):
            return True

        source_files = sorted(self._source_files())
        current_count = len(source_files)
        if current_count != int(meta["source_count"]):
            return True

        rel_posix = [p.relative_to(self._root).as_posix() for p in source_files]
        current_digest = hashlib.sha256("\n".join(rel_posix).encode("utf-8")).hexdigest()
        if current_digest != meta["source_paths_digest"]:
            return True

        current_max = max((p.stat().st_mtime_ns for p in source_files), default=0)
        if current_max > int(meta["max_source_mtime_ns"]):
            return True
        return False
```

- [ ] **Step 4: Run tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_registry.py -v`
Expected: PASS — 12 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/registry.py tests/test_commons_registry.py
git commit -m "feat(commons): registry — is_stale detects add/modify/delete/rename"
```

---

## Task 10: Query — `show` + `find` with stale warning

**Files:**
- Create: `science/src/science_tool/commons/query.py`
- Create: `science/tests/test_commons_query.py`

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_commons_query.py`:

```python
"""Tests for science_tool.commons.query."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.errors import CommonsEntityError
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import RegistryBuilder

FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _make_store(tmp_path: Path) -> Path:
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    return root


def test_show_returns_record_for_known_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    record = q.show("paper:Adams2025")
    assert record.canonical_id == "paper:Adams2025"
    assert record.frontmatter["bibkey"] == "Adams2025"


def test_show_raises_for_unknown_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    with pytest.raises(CommonsEntityError):
        q.show("paper:DoesNotExist")


def test_find_filters_by_type(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    results = q.find("dataset")
    ids = {r.canonical_id for r in results}
    assert ids == {"dataset:cath-domains", "dataset:rnaseq-example"}


def test_find_filters_by_tag(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    results = q.find("dataset", tags=("rnaseq",))
    assert [r.canonical_id for r in results] == ["dataset:rnaseq-example"]


def test_find_tags_use_and_semantics(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    # rnaseq-example has both tags; cath-domains has neither.
    results = q.find("dataset", tags=("rnaseq", "bulk"))
    assert [r.canonical_id for r in results] == ["dataset:rnaseq-example"]
    # AND across tags excludes anything not matching both
    none = q.find("dataset", tags=("rnaseq", "structure"))
    assert none == []


def test_find_filters_by_ontology_term(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    results = q.find("dataset", ontology_terms=("UBERON:0000178",))
    assert [r.canonical_id for r in results] == ["dataset:rnaseq-example"]


def test_find_filters_paper_by_year_range(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    in_range = q.find("paper", year_from=2024, year_to=2026)
    assert [r.canonical_id for r in in_range] == ["paper:Adams2025"]
    out_of_range = q.find("paper", year_from=2027, year_to=2030)
    assert out_of_range == []


def test_find_year_rejects_non_paper(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    with pytest.raises(ValueError, match="year"):
        q.find("dataset", year_from=2020)


def test_find_slug_glob(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    results = q.find("dataset", slug_glob="rnaseq-*")
    assert [r.canonical_id for r in results] == ["dataset:rnaseq-example"]


def test_show_warns_on_stale(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_store(tmp_path)
    # Add a new file post-rebuild
    (root / "topics" / "new-topic.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+topic/1.0"\n'
        'id: "topic:new-topic"\n'
        'type: "topic"\n'
        'title: "New"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    q = CommonsQuery(root)
    q.show("paper:Adams2025")  # still works against old index
    err = capsys.readouterr().err
    assert "stale" in err
    assert "science commons index rebuild" in err


def test_show_without_registry_raises_registry_error(tmp_path: Path) -> None:
    """Querying before `index rebuild` must raise CommonsRegistryError,
    not a bare sqlite3.OperationalError from a phantom auto-created DB."""
    import shutil
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    # Note: no rebuild — registry.sqlite does not exist.
    from science_tool.commons.errors import CommonsRegistryError
    q = CommonsQuery(root)
    with pytest.raises(CommonsRegistryError):
        q.show("paper:Adams2025")


def test_find_without_registry_raises_registry_error(tmp_path: Path) -> None:
    import shutil
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    from science_tool.commons.errors import CommonsRegistryError
    q = CommonsQuery(root)
    with pytest.raises(CommonsRegistryError):
        q.find("paper")


def test_show_with_empty_registry_raises_registry_error(tmp_path: Path) -> None:
    """If registry.sqlite exists but lacks the entities table (e.g., the file
    was created by a stray sqlite3.connect call), surface a CommonsRegistryError."""
    import shutil
    import sqlite3
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    # Touch an empty DB at registry.sqlite (simulates partial init)
    conn = sqlite3.connect(root / "registry.sqlite")
    conn.close()
    from science_tool.commons.errors import CommonsRegistryError
    q = CommonsQuery(root)
    with pytest.raises(CommonsRegistryError):
        q.find("paper")


def test_stale_warning_suppressed_by_env(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _make_store(tmp_path)
    (root / "topics" / "x.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+topic/1.0"\n'
        'id: "topic:x"\n'
        'type: "topic"\n'
        'title: "X"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    q = CommonsQuery(root)
    q.show("paper:Adams2025")
    err = capsys.readouterr().err
    assert "stale" not in err
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_query.py -v`
Expected: FAIL — `ImportError: cannot import name 'CommonsQuery'`.

- [ ] **Step 3: Implement the query layer**

Create `science/src/science_tool/commons/query.py`:

```python
"""Query the commons registry."""

from __future__ import annotations

import fnmatch
import json
import os
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError, CommonsRegistryError
from science_tool.commons.registry import (
    REGISTRY_FILENAME,
    RegistryBuilder,
)


class CommonsQuery:
    """Read-only access to the commons registry. Warns (does not rebuild) on staleness."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._adapter = CommonsEntityAdapter(root)
        self._builder = RegistryBuilder(root, self._adapter)

    def show(self, canonical_id: str) -> CommonsEntityRecord:
        self._require_registry()
        self._warn_if_stale()
        row = self._row_for(canonical_id)
        if row is None:
            raise CommonsEntityError(
                self._root,
                canonical_id=canonical_id,
                cause=KeyError(canonical_id),
            )
        return self._hydrate(row)

    def find(
        self,
        type: str,
        *,
        tags: Sequence[str] = (),
        ontology_terms: Sequence[str] = (),
        year_from: int | None = None,
        year_to: int | None = None,
        slug_glob: str | None = None,
    ) -> list[CommonsEntityRecord]:
        if (year_from is not None or year_to is not None) and type != "paper":
            raise ValueError(
                f"year filters are only valid for type='paper', got type={type!r}"
            )
        self._require_registry()
        self._warn_if_stale()
        clauses = ["type = ?"]
        params: list[object] = [type]
        for tag in tags:
            clauses.append(
                "canonical_id IN (SELECT canonical_id FROM entity_tags WHERE tag = ?)"
            )
            params.append(tag)
        for term in ontology_terms:
            clauses.append(
                "canonical_id IN (SELECT canonical_id FROM entity_ontology_terms WHERE term = ?)"
            )
            params.append(term)
        sql = (
            "SELECT canonical_id, type, slug, title, schema_profile, body_path, "
            "datapackage_path, mtime_ns, frontmatter_json FROM entities "
            f"WHERE {' AND '.join(clauses)} ORDER BY canonical_id"
        )
        try:
            conn = sqlite3.connect(self._root / REGISTRY_FILENAME)
            try:
                rows = conn.execute(sql, params).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise CommonsRegistryError(
                self._root / REGISTRY_FILENAME, cause=exc
            ) from exc
        records = [self._hydrate(row) for row in rows]
        if slug_glob is not None:
            records = [r for r in records if fnmatch.fnmatch(r.slug, slug_glob)]
        if year_from is not None or year_to is not None:
            records = [
                r
                for r in records
                if _year_in_range(r.frontmatter.get("year"), year_from, year_to)
            ]
        return records

    def _require_registry(self) -> None:
        """Raise CommonsRegistryError if the registry is absent or malformed.

        sqlite3.connect() creates an empty database when the file is missing,
        so a naive query against a non-existent registry would surface as a
        bare `OperationalError: no such table: entities` rather than a
        CommonsError. Probe explicitly.
        """
        db_path = self._root / REGISTRY_FILENAME
        if not db_path.is_file():
            raise CommonsRegistryError(
                db_path,
                cause=FileNotFoundError(
                    f"registry not found at {db_path}; "
                    "run `science commons index rebuild`"
                ),
            )
        try:
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'entities'"
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise CommonsRegistryError(db_path, cause=exc) from exc
        if row is None:
            raise CommonsRegistryError(
                db_path,
                cause=RuntimeError(
                    "registry exists but is missing the entities table; "
                    "run `science commons index rebuild`"
                ),
            )

    def _row_for(self, canonical_id: str) -> tuple | None:
        try:
            conn = sqlite3.connect(self._root / REGISTRY_FILENAME)
            try:
                return conn.execute(
                    "SELECT canonical_id, type, slug, title, schema_profile, body_path, "
                    "datapackage_path, mtime_ns, frontmatter_json FROM entities "
                    "WHERE canonical_id = ?",
                    (canonical_id,),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            raise CommonsRegistryError(
                self._root / REGISTRY_FILENAME, cause=exc
            ) from exc

    def _hydrate(self, row: tuple) -> CommonsEntityRecord:
        (
            canonical_id,
            type_,
            slug,
            _title,
            schema_profile,
            body_path,
            dp_path,
            mtime_ns,
            frontmatter_json,
        ) = row
        return CommonsEntityRecord(
            canonical_id=canonical_id,
            type=type_,
            slug=slug,
            schema_profile=schema_profile,
            frontmatter=json.loads(frontmatter_json),
            body_path=self._root / body_path,
            datapackage_path=(self._root / dp_path) if dp_path else None,
            mtime_ns=int(mtime_ns),
        )

    def _warn_if_stale(self) -> None:
        if os.environ.get("SCIENCE_COMMONS_QUIET_STALE"):
            return
        if self._builder.is_stale():
            print(
                "warning: commons registry is stale; run `science commons index rebuild`",
                file=sys.stderr,
            )


def _year_in_range(year: object, lo: int | None, hi: int | None) -> bool:
    if not isinstance(year, int):
        return False
    if lo is not None and year < lo:
        return False
    if hi is not None and year > hi:
        return False
    return True
```

- [ ] **Step 4: Run tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_query.py -v`
Expected: PASS — 11 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/query.py tests/test_commons_query.py
git commit -m "feat(commons): query — show/find with AND-tag filters and stale warning"
```

---

## Task 11: Validator driver

**Files:**
- Create: `science/src/science_tool/commons/validator.py`
- Create: `science/tests/test_commons_validator.py`

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_commons_validator.py`:

```python
"""Tests for science_tool.commons.validator."""
from __future__ import annotations

import shutil
from pathlib import Path

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.validator import CommonsValidator, ValidationReport

FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _make_store(tmp_path: Path, subdir: str) -> Path:
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / subdir, root)
    return root


def test_validate_clean_store_reports_no_errors(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    report = CommonsValidator(CommonsEntityAdapter(root)).validate()
    assert isinstance(report, ValidationReport)
    assert report.errors == []
    assert report.checked == 5


def test_validate_collects_per_entity_errors(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    # Drop in an invalid paper
    bad = root / "papers" / "badname.md"
    bad.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "badname"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    report = CommonsValidator(CommonsEntityAdapter(root)).validate()
    assert report.checked == 6
    assert len(report.errors) == 1
    assert report.errors[0].path == bad


def test_validate_filters_by_type(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    report = CommonsValidator(CommonsEntityAdapter(root)).validate(type="paper")
    assert report.checked == 1
    assert report.errors == []


def test_validate_filters_by_slug(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    report = CommonsValidator(CommonsEntityAdapter(root)).validate(slug="Adams2025")
    assert report.checked == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_validator.py -v`
Expected: FAIL — `ImportError: cannot import name 'CommonsValidator'`.

- [ ] **Step 3: Implement the validator driver**

Create `science/src/science_tool/commons/validator.py`:

```python
"""`science commons validate` driver: walk store + run EntityValidator.

Reads the filesystem directly (does not consult the registry, which may be
stale or absent).
"""

from __future__ import annotations

from dataclasses import dataclass

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError


@dataclass(frozen=True)
class ValidationReport:
    checked: int
    errors: list[CommonsEntityError]


class CommonsValidator:
    """Walk the commons store and surface EntityValidator errors."""

    def __init__(self, adapter: CommonsEntityAdapter) -> None:
        self._adapter = adapter

    def validate(self, *, type: str | None = None, slug: str | None = None) -> ValidationReport:
        checked = 0
        errors: list[CommonsEntityError] = []
        for item in self._adapter.scan():
            if isinstance(item, CommonsEntityError):
                if not self._matches_error(item, type=type, slug=slug):
                    continue
                checked += 1
                errors.append(item)
                continue
            if not self._matches_record(item, type=type, slug=slug):
                continue
            checked += 1
        return ValidationReport(checked=checked, errors=errors)

    @staticmethod
    def _matches_record(
        record: CommonsEntityRecord, *, type: str | None, slug: str | None
    ) -> bool:
        if type is not None and record.type != type:
            return False
        if slug is not None and record.slug != slug:
            return False
        return True

    @staticmethod
    def _matches_error(
        err: CommonsEntityError, *, type: str | None, slug: str | None
    ) -> bool:
        if type is None and slug is None:
            return True
        canonical = err.canonical_id or ""
        err_type, _, err_slug = canonical.partition(":")
        if type is not None and err_type != type:
            return False
        if slug is not None and err_slug != slug:
            return False
        return True
```

- [ ] **Step 4: Run tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_validator.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/validator.py tests/test_commons_validator.py
git commit -m "feat(commons): validator driver — walk store + surface EntityValidator errors"
```

---

## Task 12: CLI — `commons` group with `init` and `index rebuild`

**Files:**
- Create: `science/src/science_tool/commons/cli.py` (commons_group with init + index rebuild)
- Create: `science/tests/test_commons_cli.py`

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_commons_cli.py`:

```python
"""Tests for science_tool.commons.cli."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.commons.cli import commons_group


def test_init_creates_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "commons"))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "commons" / "datasets").is_dir()
    assert (tmp_path / "commons" / ".git").is_dir()


def test_init_force_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "commons"
    root.mkdir()
    (root / "stray.txt").write_text("hi")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["init", "--force"])
    assert result.exit_code == 0, result.output
    assert (root / "datasets").is_dir()


def test_index_rebuild_with_valid_fixtures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 0, result.output
    assert "indexed 5" in result.output
    assert (root / "registry.sqlite").is_file()


def test_index_rebuild_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["entities_indexed"] == 5
    assert payload["errors"] == []
    assert payload["duration_ms"] >= 0


def test_index_rebuild_exit_1_when_entity_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    # Drop in a bad paper
    (root / "papers" / "badname.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "badname"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 1


def test_missing_store_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["index", "rebuild"])
    assert result.exit_code == 1
    assert "commons store not found" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'commons_group'`.

- [ ] **Step 3: Implement the CLI skeleton**

Create `science/src/science_tool/commons/cli.py`:

```python
"""Click CLI for `science commons`."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.bootstrap import init_commons
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.registry import RegistryBuilder


@click.group("commons")
def commons_group() -> None:
    """Manage the shared knowledge store."""


@commons_group.command("init")
@click.option("--force", is_flag=True, help="Initialize even if the path is non-empty.")
def init_cmd(force: bool) -> None:
    """Create or verify the commons store layout."""
    root = resolve_commons_root()
    try:
        init_commons(root, force=force)
    except CommonsError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    click.echo(f"commons initialized at {root}")


@commons_group.group("index")
def index_group() -> None:
    """Manage the commons registry index."""


@index_group.command("rebuild")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON report.")
def index_rebuild_cmd(as_json: bool) -> None:
    """Rebuild registry.sqlite from filesystem state."""
    root = _require_root()
    adapter = CommonsEntityAdapter(root)
    report = RegistryBuilder(root, adapter).rebuild()
    if as_json:
        click.echo(
            json.dumps(
                {
                    "entities_indexed": report.entities_indexed,
                    "errors": [
                        {
                            "path": str(e.path),
                            "canonical_id": e.canonical_id,
                            "message": str(e.cause),
                        }
                        for e in report.errors
                    ],
                    "duration_ms": report.duration_ms,
                }
            )
        )
    else:
        click.echo(f"indexed {report.entities_indexed} entities in {report.duration_ms} ms")
        for err in report.errors:
            click.echo(f"  error: {err}", err=True)
    sys.exit(1 if report.errors else 0)


def _require_root() -> Path:
    """Resolve the commons root and exit cleanly if missing."""
    root = resolve_commons_root()
    if not root.is_dir():
        click.echo(
            f"error: commons store not found at {root}; run `science commons init`",
            err=True,
        )
        sys.exit(1)
    return root
```

- [ ] **Step 4: Run tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -v`
Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/cli.py tests/test_commons_cli.py
git commit -m "feat(commons): CLI — init + index rebuild subcommands"
```

---

## Task 13: CLI — `show` and `find` subcommands

**Files:**
- Modify: `science/src/science_tool/commons/cli.py` (add `show` and `find`)
- Modify: `science/tests/test_commons_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `science/tests/test_commons_cli.py`:

```python
def _seeded_store(tmp_path: Path) -> Path:
    import shutil
    fixtures = Path(__file__).parent / "fixtures" / "commons" / "valid"
    root = tmp_path / "commons"
    shutil.copytree(fixtures, root)
    return root


def test_show_human(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:Adams2025"])
    assert result.exit_code == 0, result.output
    assert "paper:Adams2025" in result.output
    assert "Adams, A." in result.output  # author from frontmatter


def test_show_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:Adams2025", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["canonical_id"] == "paper:Adams2025"
    assert payload["frontmatter"]["bibkey"] == "Adams2025"
    assert "commons_metadata" in payload


def test_show_rejects_project_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(
        commons_group, ["show", "paper:Adams2025", "--project", "foo"]
    )
    assert result.exit_code == 1
    assert "Phase D" in result.output


def test_show_missing_entity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["show", "paper:DoesNotExist"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower() or "failed" in result.output.lower()


def test_find_default_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["find", "dataset"])
    assert result.exit_code == 0
    assert "dataset:cath-domains" in result.output
    assert "dataset:rnaseq-example" in result.output


def test_find_with_tag_and(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(
        commons_group, ["find", "dataset", "--tag", "rnaseq", "--tag", "bulk"]
    )
    assert result.exit_code == 0
    assert "dataset:rnaseq-example" in result.output
    assert "dataset:cath-domains" not in result.output


def test_find_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(commons_group, ["find", "paper", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload[0]["canonical_id"] == "paper:Adams2025"


def test_find_year_filter_only_for_papers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    runner = CliRunner()
    runner.invoke(commons_group, ["index", "rebuild"])
    result = runner.invoke(
        commons_group, ["find", "dataset", "--year-from", "2020"]
    )
    assert result.exit_code != 0


def test_show_before_rebuild_exits_1_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Show must surface CommonsRegistryError as a clean exit-1 message,
    not a raw sqlite3.OperationalError traceback."""
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    # Note: no `index rebuild` invocation — registry.sqlite is absent.
    runner = CliRunner()
    result = runner.invoke(commons_group, ["show", "paper:Adams2025"])
    assert result.exit_code == 1
    assert "OperationalError" not in result.output
    # The error message either references the registry or suggests rebuilding.
    assert (
        "registry" in result.output.lower()
        or "index rebuild" in result.output
    )


def test_find_before_rebuild_exits_1_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["find", "paper"])
    assert result.exit_code == 1
    assert "OperationalError" not in result.output
    assert (
        "registry" in result.output.lower()
        or "index rebuild" in result.output
    )
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -v`
Expected: 8 new tests FAIL — show/find subcommands don't exist yet.

- [ ] **Step 3: Add `show` and `find` to cli.py**

Append to `science/src/science_tool/commons/cli.py`:

```python
from science_tool.commons.adapter import CommonsEntityRecord
from science_tool.commons.query import CommonsQuery


@commons_group.command("show")
@click.argument("entity_id")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.option(
    "--project",
    default=None,
    help="(reserved) Overlay-merged view; rejected in Phase B.",
)
def show_cmd(entity_id: str, as_json: bool, project: str | None) -> None:
    """Print one entity by canonical id."""
    if project is not None:
        click.echo(
            "error: --project is rejected in Phase B; overlay merge lands in Phase D",
            err=True,
        )
        sys.exit(1)
    root = _require_root()
    try:
        record = CommonsQuery(root).show(entity_id)
    except CommonsError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    if as_json:
        click.echo(json.dumps(_record_to_json(record, root)))
    else:
        _print_record_human(record)


@commons_group.command("find")
@click.argument(
    "entity_type", type=click.Choice(["dataset", "paper", "topic", "theme"])
)
@click.option("--tag", "tags", multiple=True, help="Filter by tag (repeatable; AND).")
@click.option(
    "--ontology",
    "ontology_terms",
    multiple=True,
    help="Filter by ontology term (repeatable; AND).",
)
@click.option("--year-from", type=int, default=None, help="(paper only) Inclusive lower bound.")
@click.option("--year-to", type=int, default=None, help="(paper only) Inclusive upper bound.")
@click.option("--slug-glob", default=None, help="fnmatch pattern over slug.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def find_cmd(
    entity_type: str,
    tags: tuple[str, ...],
    ontology_terms: tuple[str, ...],
    year_from: int | None,
    year_to: int | None,
    slug_glob: str | None,
    as_json: bool,
) -> None:
    """Filter the commons registry."""
    root = _require_root()
    try:
        records = CommonsQuery(root).find(
            entity_type,
            tags=tags,
            ontology_terms=ontology_terms,
            year_from=year_from,
            year_to=year_to,
            slug_glob=slug_glob,
        )
    except ValueError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)
    except CommonsError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)
    if as_json:
        click.echo(json.dumps([_record_to_json(r, root) for r in records]))
    else:
        for record in records:
            title = record.frontmatter.get("title", "")
            click.echo(f"{record.canonical_id}\t{title}")


def _record_to_json(record: CommonsEntityRecord, root: Path) -> dict:
    return {
        "canonical_id": record.canonical_id,
        "type": record.type,
        "slug": record.slug,
        "schema_profile": record.schema_profile,
        "frontmatter": record.frontmatter,
        "commons_metadata": {
            "body_path": str(record.body_path.relative_to(root)),
            "datapackage_path": (
                str(record.datapackage_path.relative_to(root))
                if record.datapackage_path is not None
                else None
            ),
            "mtime_ns": record.mtime_ns,
        },
    }


def _print_record_human(record: CommonsEntityRecord) -> None:
    click.echo(f"{record.canonical_id}")
    click.echo(f"  title:          {record.frontmatter.get('title', '')}")
    click.echo(f"  schema_profile: {record.schema_profile}")
    tags = record.frontmatter.get("tags") or []
    if tags:
        click.echo(f"  tags:           {', '.join(tags)}")
    terms = record.frontmatter.get("ontology_terms") or []
    if terms:
        click.echo(f"  ontology_terms: {', '.join(terms)}")
    if record.type == "paper":
        authors = record.frontmatter.get("authors") or []
        click.echo(f"  authors:        {', '.join(authors)}")
        click.echo(f"  year:           {record.frontmatter.get('year', '')}")
```

- [ ] **Step 4: Run tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -v`
Expected: PASS — 14 tests total.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/cli.py tests/test_commons_cli.py
git commit -m "feat(commons): CLI — show + find subcommands (with --project rejection)"
```

---

## Task 14: CLI — `validate` subcommand

**Files:**
- Modify: `science/src/science_tool/commons/cli.py` (add `validate`)
- Modify: `science/tests/test_commons_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `science/tests/test_commons_cli.py`:

```python
def test_validate_clean_store_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate"])
    assert result.exit_code == 0, result.output
    assert "5 entities" in result.output or "checked 5" in result.output


def test_validate_reports_per_entity_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    (root / "papers" / "badname.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "badname"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate"])
    assert result.exit_code == 1
    assert "badname.md" in result.output


def test_validate_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _seeded_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    runner = CliRunner()
    result = runner.invoke(commons_group, ["validate", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["checked"] == 5
    assert payload["errors"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -v`
Expected: 3 new tests FAIL — `validate` subcommand doesn't exist.

- [ ] **Step 3: Add `validate` to cli.py**

Append to `science/src/science_tool/commons/cli.py`:

```python
from science_tool.commons.validator import CommonsValidator


@commons_group.command("validate")
@click.option("--type", "entity_type", default=None, help="Filter to one type.")
@click.option("--slug", default=None, help="Filter to one slug.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def validate_cmd(entity_type: str | None, slug: str | None, as_json: bool) -> None:
    """Validate every entity in the commons store against its schema_profile."""
    root = _require_root()
    adapter = CommonsEntityAdapter(root)
    report = CommonsValidator(adapter).validate(type=entity_type, slug=slug)
    if as_json:
        click.echo(
            json.dumps(
                {
                    "checked": report.checked,
                    "errors": [
                        {
                            "path": str(e.path),
                            "canonical_id": e.canonical_id,
                            "message": str(e.cause),
                        }
                        for e in report.errors
                    ],
                }
            )
        )
    else:
        click.echo(f"checked {report.checked} entities")
        for err in report.errors:
            click.echo(f"  error: {err}", err=True)
    sys.exit(1 if report.errors else 0)
```

- [ ] **Step 4: Run tests**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli.py -v`
Expected: PASS — 17 tests total.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/cli.py tests/test_commons_cli.py
git commit -m "feat(commons): CLI — validate subcommand"
```

---

## Task 15: Public surface — finalize `commons/__init__.py`

**Files:**
- Modify: `science/src/science_tool/commons/__init__.py`
- Create: `science/tests/test_commons_public_api.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_public_api.py`:

```python
"""Public API surface of science_tool.commons."""
from __future__ import annotations


def test_public_api_exports() -> None:
    import science_tool.commons as pkg
    expected = {
        "CommonsEntityAdapter",
        "CommonsEntityError",
        "CommonsEntityRecord",
        "CommonsError",
        "CommonsLayoutError",
        "CommonsRegistryError",
        "CommonsRootMalformedError",
        "CommonsRootNotFoundError",
        "CommonsQuery",
        "CommonsSettings",
        "CommonsValidator",
        "RebuildReport",
        "RegistryBuilder",
        "ValidationReport",
        "commons_group",
        "init_commons",
        "resolve_commons_root",
    }
    assert expected.issubset(set(pkg.__all__))
    for name in expected:
        assert hasattr(pkg, name), f"missing public name: {name}"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_public_api.py -v`
Expected: FAIL — exports missing.

- [ ] **Step 3: Replace `commons/__init__.py` with the full public surface**

Overwrite `science/src/science_tool/commons/__init__.py`:

```python
"""Shared knowledge store (commons) for Science multi-project entities.

Phase B (scaffolding): directory bootstrap, schema-validated entity adapter,
SQLite index, and CLI surface for `science commons {init, index rebuild,
show, find, validate}`. No inventory integration, no overlay merge, no data
resolver — those land in Phases C/D/E.

See docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md.
"""

from __future__ import annotations

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.bootstrap import init_commons
from science_tool.commons.cli import commons_group
from science_tool.commons.config import CommonsSettings, resolve_commons_root
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
)
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import RebuildReport, RegistryBuilder
from science_tool.commons.validator import CommonsValidator, ValidationReport

__all__ = [
    "CommonsEntityAdapter",
    "CommonsEntityError",
    "CommonsEntityRecord",
    "CommonsError",
    "CommonsLayoutError",
    "CommonsQuery",
    "CommonsRegistryError",
    "CommonsRootMalformedError",
    "CommonsRootNotFoundError",
    "CommonsSettings",
    "CommonsValidator",
    "RebuildReport",
    "RegistryBuilder",
    "ValidationReport",
    "commons_group",
    "init_commons",
    "resolve_commons_root",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_public_api.py -v`
Expected: PASS — 1 test.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/commons/__init__.py tests/test_commons_public_api.py
git commit -m "feat(commons): finalize public API surface"
```

---

## Task 16: Wire `commons_group` into the top-level `science` CLI

**Files:**
- Modify: `science/src/science_tool/cli.py` (add the import + `main.add_command`)
- Create: `science/tests/test_commons_cli_top_level.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_cli_top_level.py`:

```python
"""Verify `science commons` is reachable from the top-level CLI."""
from __future__ import annotations

from click.testing import CliRunner

from science_tool.cli import main


def test_commons_subcommand_listed_in_main_help() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "commons" in result.output


def test_commons_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["commons", "--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "show" in result.output
    assert "find" in result.output
    assert "validate" in result.output


def test_commons_index_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["commons", "index", "--help"])
    assert result.exit_code == 0
    assert "rebuild" in result.output
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli_top_level.py -v`
Expected: FAIL — `commons` not in main help output.

- [ ] **Step 3: Register the group in cli.py**

Modify `science/src/science_tool/cli.py`:

(a) Add the import near the other subgroup imports (around line 95-108). Find the block ending with `from science_tool.wander.cli import wander_command` and add **above** it:

```python
from science_tool.commons import commons_group
```

(b) Add the registration to the `main.add_command(...)` block (around lines 202-214). After the last existing `main.add_command(...)` line, add:

```python
main.add_command(commons_group)
```

- [ ] **Step 4: Run the new test**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli_top_level.py -v`
Expected: PASS — 3 tests.

- [ ] **Step 5: Run the full commons-related test suite**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_*.py -v`
Expected: PASS — full Phase B suite green.

- [ ] **Step 6: Run the full project test suite to confirm no regressions**

Run: `cd ~/d/science/science && uv run pytest tests/ -q`
Expected: All passing.

Also run the model suite to confirm Phase A is undisturbed:

Run: `cd ~/d/science/science/model && uv run pytest tests/ -q`
Expected: All passing.

- [ ] **Step 7: Commit**

```bash
cd ~/d/science/science
git add src/science_tool/cli.py tests/test_commons_cli_top_level.py
git commit -m "feat(commons): wire commons_group into top-level science CLI"
```

---

## After all tasks

Hand off to `superpowers:finishing-a-development-branch` (controller does this, not the implementer). Options will be the standard set: merge to main, push and create PR, keep as-is, or discard.

Once merged, the next pieces of follow-on work (Phase C / D / E) are described in §11 of the design spec.

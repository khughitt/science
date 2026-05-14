# Phase C (Commons Data Resolver) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bulk-data resolver to `science_tool.commons` — an in-process `resolve()` library plus a `science commons data resolve` CLI command that maps `(dataset_id, logical_path)` to a hash-verified absolute filesystem path.

**Architecture:** Two new focused modules in the existing `science_tool.commons` subpackage. `datapackage.py` is a thin Frictionless-sidecar reader (logical-path validation, hash parsing, `resources[]` extraction). `resolver.py` runs the lookup chain — `$SCIENCE_COMMONS_DATA_ROOT/<slug>/<logical_path>` then a per-machine override file — and verifies the on-disk bytes' sha256 against the descriptor hash on every call. The resolver reuses Phase B's `CommonsEntityAdapter.load()` to locate a dataset's `datapackage.yaml`; one small Phase B consistency patch to `load()` is included.

**Tech Stack:** Python 3.11+, Click 8.1, Pydantic 2, pyyaml, `hashlib` (stdlib), pytest. Reuses Phase B's `CommonsEntityAdapter`, `commons.config`, and `commons.errors`.

**Spec:** `docs/plans/2026-05-14-commons-data-resolver-design.md`

**Parent design:** `docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` (§4)

---

## Deviations from the design spec

Two small refinements, both consistent with the spec's intent (round-2 review finding #4 — errors should not fabricate a `Path` for inputs that have no datapackage file):

1. **`parse_resource_hash` raises `ValueError`, not `CommonsDatapackageError`.** The spec's §5.2 signature comment says it raises `CommonsDatapackageError`, but that error's constructor requires a `Path` and a standalone hash string has none. `parse_resource_hash` raises a plain `ValueError`; its only real caller, `read_datapackage`, catches it and re-raises as `CommonsDatapackageError` naming the descriptor file — exactly mirroring the `validate_logical_path` / `DataLogicalPathError` wrapping the spec already specifies.
2. **`DatapackageDescriptor` carries a `source_path: Path` field.** The spec shows only `resources`, but `DatapackageDescriptor.resource()` must raise a `CommonsDatapackageError` that names a real file. Storing the descriptor's source path makes that error honest without the resolver having to catch-and-wrap.

---

## File Structure

### New files

```
science/src/science_tool/commons/
├── datapackage.py    # validate_logical_path, parse_resource_hash, DataResource,
│                     #   DatapackageDescriptor, read_datapackage
└── resolver.py       # ResolvedDataResource, resolve()
```

### Modified files

- `science/src/science_tool/commons/errors.py` — add `CommonsDatapackageError`, `DataLogicalPathError`, `DataResourceNotFoundError`, `DataIntegrityError` (Task 1)
- `science/src/science_tool/commons/config.py` — add `data_root` field, `resolve_commons_data_root()`, `load_data_overrides()` (Task 2)
- `science/src/science_tool/commons/adapter.py` — `load()` raises `CommonsLayoutError` for a dataset missing `datapackage.yaml`, mirroring `scan()` (Task 5)
- `science/src/science_tool/commons/cli.py` — add the `data` subgroup with `resolve` (Task 7)
- `science/src/science_tool/commons/__init__.py` — export the new public surface (Task 8)

### New test files (under `science/tests/`)

- `test_commons_datapackage.py` (Tasks 3, 4)
- `test_commons_resolver.py` (Task 6)
- `test_commons_cli_data.py` (Task 7)

### Extended test files (under `science/tests/`)

- `test_commons_errors.py` (Task 1)
- `test_commons_config.py` (Task 2)
- `test_commons_adapter.py` (Task 5)
- `test_commons_public_api.py` (Task 8)

### Conventions

- Test invocation: `cd ~/d/science/science && uv run pytest <path>::<name> -v`
- Each task has its own commit; no batching.
- All commits target the current working branch.

### Pre-task note (controller / implementer)

Before Task 1, ensure the implementation runs on a fresh feature branch off `main` (e.g., `feat/commons-data-resolver`). Each task commits onto that branch. After Task 9, the controller hands off to `superpowers:finishing-a-development-branch`.

---

## Task 1: Error classes

**Files:**
- Modify: `science/src/science_tool/commons/errors.py`
- Test: `science/tests/test_commons_errors.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_errors.py`. First add these names to the existing import block at the top of the file:

```python
from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
    DataIntegrityError,
    DataLogicalPathError,
    DataResourceNotFoundError,
)
```

Then append these tests to the end of the file:

```python
def test_phase_c_errors_subclass_commons_error() -> None:
    assert issubclass(CommonsDatapackageError, CommonsError)
    assert issubclass(DataLogicalPathError, CommonsError)
    assert issubclass(DataResourceNotFoundError, CommonsError)
    assert issubclass(DataIntegrityError, CommonsError)


def test_datapackage_error_carries_path_and_reason() -> None:
    err = CommonsDatapackageError(Path("/x/datapackage.yaml"), reason="missing resources[]")
    assert err.path == Path("/x/datapackage.yaml")
    assert err.reason == "missing resources[]"
    assert "missing resources[]" in str(err)
    assert "/x/datapackage.yaml" in str(err)


def test_logical_path_error_carries_string_not_path() -> None:
    err = DataLogicalPathError("../escape", reason="path may not contain '..' segments")
    assert err.logical_path == "../escape"
    assert err.reason == "path may not contain '..' segments"
    assert "../escape" in str(err)


def test_resource_not_found_lists_tried_paths() -> None:
    tried = [Path("/data/foo/x.tsv"), Path("/legacy/foo/x.tsv")]
    err = DataResourceNotFoundError("dataset:foo", "x.tsv", tried=tried)
    assert err.dataset_id == "dataset:foo"
    assert err.logical_path == "x.tsv"
    assert err.tried == tried
    assert "/data/foo/x.tsv" in str(err)
    assert "/legacy/foo/x.tsv" in str(err)


def test_integrity_error_carries_expected_and_actual() -> None:
    err = DataIntegrityError(
        Path("/data/foo/x.tsv"),
        expected="sha256:aaaa",
        actual="sha256:bbbb",
    )
    assert err.path == Path("/data/foo/x.tsv")
    assert err.expected == "sha256:aaaa"
    assert err.actual == "sha256:bbbb"
    assert "sha256:aaaa" in str(err)
    assert "sha256:bbbb" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_errors.py -v`
Expected: FAIL — `ImportError: cannot import name 'CommonsDatapackageError'`

- [ ] **Step 3: Add the four error classes**

Append to `science/src/science_tool/commons/errors.py` (after `CommonsRegistryError`):

```python
class CommonsDatapackageError(CommonsError):
    """A datapackage.yaml is malformed, missing resources[], has an invalid or
    duplicate resource path, or has a resource with a missing/malformed hash."""

    def __init__(self, path: Path, *, reason: str) -> None:
        super().__init__(f"commons datapackage error at {path}: {reason}")
        self.path = path
        self.reason = reason


class DataLogicalPathError(CommonsError):
    """A logical path string is not a safe forward-slash relative path.

    Carries the offending string (not a Path) so a bad CLI argument is not
    forced to masquerade as a datapackage file.
    """

    def __init__(self, logical_path: str, *, reason: str) -> None:
        super().__init__(f"invalid logical path {logical_path!r}: {reason}")
        self.logical_path = logical_path
        self.reason = reason


class DataResourceNotFoundError(CommonsError):
    """The bytes for a resource were not found in any lookup source."""

    def __init__(
        self, dataset_id: str, logical_path: str, *, tried: list[Path]
    ) -> None:
        tried_str = ", ".join(str(p) for p in tried)
        super().__init__(
            f"data resource {dataset_id} / {logical_path} not found; tried: {tried_str}"
        )
        self.dataset_id = dataset_id
        self.logical_path = logical_path
        self.tried = tried


class DataIntegrityError(CommonsError):
    """A resource file was found but its sha256 does not match the expected hash."""

    def __init__(self, path: Path, *, expected: str, actual: str) -> None:
        super().__init__(
            f"data integrity error at {path}: expected {expected}, got {actual}"
        )
        self.path = path
        self.expected = expected
        self.actual = actual
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_errors.py -v`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/errors.py science/tests/test_commons_errors.py
git commit -m "feat(commons): Phase C error classes"
```

---

## Task 2: Config — data root resolver + override loader

**Files:**
- Modify: `science/src/science_tool/commons/config.py`
- Test: `science/tests/test_commons_config.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_config.py`. Update the import line at the top of the file to:

```python
from science_tool.commons.config import (
    CommonsSettings,
    load_data_overrides,
    resolve_commons_data_root,
    resolve_commons_root,
)
from science_tool.commons.errors import CommonsError
```

Then append these tests to the end of the file:

```python
def test_data_root_default_is_none() -> None:
    assert CommonsSettings().data_root is None


def test_resolve_data_root_env_var_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "from-env"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert resolve_commons_data_root() == tmp_path / "from-env"


def test_resolve_data_root_config_used_when_env_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_DATA_ROOT", raising=False)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump({"commons": {"data_root": str(tmp_path / "from-config")}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert resolve_commons_data_root() == tmp_path / "from-config"


def test_resolve_data_root_default_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_DATA_ROOT", raising=False)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert resolve_commons_data_root() == Path("/data/science-commons")


def test_load_data_overrides_missing_file_returns_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert load_data_overrides() == {}


def test_load_data_overrides_reads_absolute_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(
        yaml.dump({"cath-domains": "/data/legacy/cath"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert load_data_overrides() == {"cath-domains": Path("/data/legacy/cath")}


def test_load_data_overrides_rejects_relative_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(
        yaml.dump({"cath-domains": "legacy/cath"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(CommonsError, match="absolute"):
        load_data_overrides()


def test_load_data_overrides_rejects_non_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(yaml.dump(["not", "a", "mapping"]), encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(CommonsError, match="mapping"):
        load_data_overrides()


def test_load_data_overrides_rejects_non_string_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(yaml.dump({"cath-domains": 123}), encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(CommonsError):
        load_data_overrides()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_data_overrides'`

- [ ] **Step 3: Implement the config additions**

In `science/src/science_tool/commons/config.py`, add `yaml` to the imports and `CommonsError` from the errors module. The top of the file becomes:

```python
"""Commons-store configuration: settings model + root resolvers."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel

from science_tool.commons.errors import CommonsError
```

Add the `data_root` field to `CommonsSettings`:

```python
class CommonsSettings(BaseModel):
    """Settings for the shared knowledge store."""

    root: Path | None = None  # None means "use built-in default"
    data_root: Path | None = None  # None means "use built-in default"
```

Append these two functions to the end of the file:

```python
def resolve_commons_data_root() -> Path:
    """Resolve the bulk-data root for commons datasets.

    Discovery order:
    1. `$SCIENCE_COMMONS_DATA_ROOT` environment variable.
    2. `commons.data_root` in the global config file.
    3. Default: `/data/science-commons/`.
    """
    if env := os.environ.get("SCIENCE_COMMONS_DATA_ROOT"):
        return Path(env).expanduser()

    from science_tool.registry.config import load_global_config

    cfg = load_global_config()
    if cfg.commons.data_root is not None:
        return Path(cfg.commons.data_root).expanduser()

    return Path("/data/science-commons")


def load_data_overrides() -> dict[str, Path]:
    """Load the per-machine data-override map from `~/.config/science/data.yaml`.

    Maps `<dataset-slug>` to an absolute directory. Returns `{}` if the file is
    missing. Raises `CommonsError` if the file exists but is not a mapping of
    string slugs to absolute-path strings.
    """
    from science_tool.registry.config import get_science_config_dir

    overrides_path = get_science_config_dir() / "data.yaml"
    if not overrides_path.is_file():
        return {}

    raw = yaml.safe_load(overrides_path.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CommonsError(
            f"{overrides_path}: expected a mapping of slug -> absolute path"
        )

    result: dict[str, Path] = {}
    for slug, value in raw.items():
        if not isinstance(slug, str) or not isinstance(value, str):
            raise CommonsError(
                f"{overrides_path}: entry {slug!r} -> {value!r} must be "
                f"a string slug mapped to a string path"
            )
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise CommonsError(
                f"{overrides_path}: override for {slug!r} must be an absolute "
                f"path, got {value!r}"
            )
        result[slug] = path
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_config.py -v`
Expected: PASS — all tests green (including the existing Phase B tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/config.py science/tests/test_commons_config.py
git commit -m "feat(commons): data-root resolver + per-machine override loader"
```

---

## Task 3: Datapackage reader — `validate_logical_path` + `parse_resource_hash`

**Files:**
- Create: `science/src/science_tool/commons/datapackage.py`
- Test: `science/tests/test_commons_datapackage.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_datapackage.py`:

```python
"""Tests for science_tool.commons.datapackage."""
from __future__ import annotations

import pytest

from science_tool.commons.datapackage import (
    parse_resource_hash,
    validate_logical_path,
)
from science_tool.commons.errors import DataLogicalPathError

_GOOD_HASH = "sha256:" + "a" * 64


def test_validate_logical_path_accepts_plain_and_nested() -> None:
    assert validate_logical_path("domains.tsv") == "domains.tsv"
    assert validate_logical_path("raw/chains.csv") == "raw/chains.csv"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "/etc/passwd",
        "raw\\chains.csv",
        "C:/data/x.tsv",
        "C:x.tsv",
        "\\\\server\\share\\x",
        "../escape.tsv",
        "raw/../../escape.tsv",
        "./relative.tsv",
        "raw//double.tsv",
        "trailing/",
    ],
)
def test_validate_logical_path_rejects_unsafe(bad: str) -> None:
    with pytest.raises(DataLogicalPathError):
        validate_logical_path(bad)


def test_parse_resource_hash_accepts_sha256() -> None:
    assert parse_resource_hash(_GOOD_HASH) == ("sha256", "a" * 64)


@pytest.mark.parametrize(
    "bad",
    [
        "a" * 64,                       # bare hex, no prefix
        "md5:" + "a" * 32,              # unsupported algorithm
        "sha1:" + "a" * 40,             # unsupported algorithm
        "sha256:" + "a" * 63,           # too short
        "sha256:" + "a" * 65,           # too long
        "sha256:" + "A" * 64,           # uppercase not allowed
        "sha256:" + "g" * 64,           # non-hex
        "sha256:",                      # empty digest
    ],
)
def test_parse_resource_hash_rejects_bad(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_resource_hash(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_datapackage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.commons.datapackage'`

- [ ] **Step 3: Create `datapackage.py` with the two validators**

Create `science/src/science_tool/commons/datapackage.py`:

```python
"""Reader for the Frictionless datapackage.yaml sidecar of a commons dataset.

Phase C only needs resources[].path + resources[].hash; schemas, dialects and
other Frictionless fields are ignored. See
docs/plans/2026-05-14-commons-data-resolver-design.md §5.2.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from science_tool.commons.errors import DataLogicalPathError

_SHA256_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_DRIVE_LETTER = re.compile(r"^[A-Za-z]:")


def validate_logical_path(logical_path: str) -> str:
    """Assert a logical path is a safe forward-slash relative path within a dataset.

    Returns the path unchanged on success. Raises `DataLogicalPathError` on any
    unsafe form: empty/whitespace, backslash-containing, a Windows drive-letter
    form, absolute, containing a `..` parent-traversal segment, or any path that
    does not round-trip cleanly as a normalized forward-slash relative path
    (this catches `.` segments, trailing slashes, and doubled slashes).
    """
    if not logical_path or not logical_path.strip():
        raise DataLogicalPathError(logical_path, reason="path is empty")
    if "\\" in logical_path:
        raise DataLogicalPathError(
            logical_path,
            reason="backslashes are not allowed; use forward slashes",
        )
    if _DRIVE_LETTER.match(logical_path):
        raise DataLogicalPathError(
            logical_path, reason="Windows drive-letter paths are not allowed"
        )
    if PurePosixPath(logical_path).is_absolute():
        raise DataLogicalPathError(logical_path, reason="path must be relative")
    if ".." in PurePosixPath(logical_path).parts:
        raise DataLogicalPathError(
            logical_path, reason="path may not contain '..' segments"
        )
    if str(PurePosixPath(logical_path)) != logical_path:
        raise DataLogicalPathError(
            logical_path,
            reason="path must be a normalized forward-slash relative path",
        )
    return logical_path


def parse_resource_hash(raw: str) -> tuple[str, str]:
    """Parse a 'sha256:<64 lowercase hex>' string into (algorithm, hexdigest).

    Phase C accepts only sha256. Raises `ValueError` on a missing prefix, an
    unsupported algorithm, or a malformed digest. (`read_datapackage` wraps this
    into a `CommonsDatapackageError` that names the descriptor file.)
    """
    if not isinstance(raw, str) or ":" not in raw:
        raise ValueError(
            f"hash {raw!r} must be of the form 'sha256:<64 hex chars>'"
        )
    algorithm, _, digest = raw.partition(":")
    if algorithm != "sha256":
        raise ValueError(
            f"unsupported hash algorithm {algorithm!r}; Phase C accepts only sha256"
        )
    if not _SHA256_DIGEST.match(digest):
        raise ValueError(
            f"malformed sha256 digest {digest!r}; expected 64 lowercase hex chars"
        )
    return (algorithm, digest)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_datapackage.py -v`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/datapackage.py science/tests/test_commons_datapackage.py
git commit -m "feat(commons): logical-path + resource-hash validators"
```

---

## Task 4: Datapackage reader — `DataResource`, `DatapackageDescriptor`, `read_datapackage`

**Files:**
- Modify: `science/src/science_tool/commons/datapackage.py`
- Test: `science/tests/test_commons_datapackage.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_datapackage.py`. Update the imports at the top of the file to:

```python
from pathlib import Path

import pytest

from science_tool.commons.datapackage import (
    DataResource,
    DatapackageDescriptor,
    parse_resource_hash,
    read_datapackage,
    validate_logical_path,
)
from science_tool.commons.errors import CommonsDatapackageError, DataLogicalPathError
```

Then append these tests to the end of the file:

```python
def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_read_datapackage_parses_valid(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "name: rnaseq-example\n"
        'profile: "data-package"\n'
        "resources:\n"
        "  - name: counts\n"
        "    path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "  - name: meta\n"
        "    path: raw/meta.csv\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    descriptor = read_datapackage(dp)
    assert isinstance(descriptor, DatapackageDescriptor)
    assert descriptor.source_path == dp
    assert descriptor.resources == (
        DataResource(path="counts.parquet", hash=_GOOD_HASH),
        DataResource(path="raw/meta.csv", hash=_GOOD_HASH),
    )


def test_resource_lookup_hit_and_miss(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    descriptor = read_datapackage(dp)
    assert descriptor.resource("counts.parquet").path == "counts.parquet"
    with pytest.raises(CommonsDatapackageError, match="no resource"):
        descriptor.resource("missing.parquet")


def test_read_datapackage_rejects_malformed_yaml(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", "resources: [unclosed\n")
    with pytest.raises(CommonsDatapackageError, match="YAML"):
        read_datapackage(dp)


def test_read_datapackage_rejects_missing_resources(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", "name: x\n")
    with pytest.raises(CommonsDatapackageError, match="resources"):
        read_datapackage(dp)


def test_read_datapackage_rejects_empty_resources(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", "resources: []\n")
    with pytest.raises(CommonsDatapackageError, match="resources"):
        read_datapackage(dp)


def test_read_datapackage_rejects_duplicate_path(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n'
        "  - path: counts.parquet\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="duplicate"):
        read_datapackage(dp)


def test_read_datapackage_rejects_invalid_resource_path(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: ../escape.tsv\n"
        f'    hash: "{_GOOD_HASH}"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="invalid path"):
        read_datapackage(dp)


def test_read_datapackage_rejects_missing_hash(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n  - path: counts.parquet\n",
    )
    with pytest.raises(CommonsDatapackageError, match="hash"):
        read_datapackage(dp)


def test_read_datapackage_rejects_malformed_hash(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        "resources:\n"
        "  - path: counts.parquet\n"
        '    hash: "md5:abc"\n',
    )
    with pytest.raises(CommonsDatapackageError, match="invalid hash"):
        read_datapackage(dp)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_datapackage.py -v`
Expected: FAIL — `ImportError: cannot import name 'read_datapackage'`

- [ ] **Step 3: Implement the descriptor + reader**

In `science/src/science_tool/commons/datapackage.py`, update the imports at the top to add `dataclass`, `Path`, and `yaml`, and the new error class:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from science_tool.commons.errors import CommonsDatapackageError, DataLogicalPathError
```

Append to the end of the file:

```python
@dataclass(frozen=True, slots=True)
class DataResource:
    """One resource entry from a datapackage.yaml — path + hash only."""

    path: str  # validated forward-slash relative logical path
    hash: str  # full "sha256:<hex>" string, verbatim from resources[].hash


@dataclass(frozen=True, slots=True)
class DatapackageDescriptor:
    """The Phase C view of a datapackage.yaml: its source path + its resources."""

    source_path: Path
    resources: tuple[DataResource, ...]

    def resource(self, logical_path: str) -> DataResource:
        """Return the resource with the given logical path.

        Raises `CommonsDatapackageError` (naming `source_path`) if absent.
        """
        for resource in self.resources:
            if resource.path == logical_path:
                return resource
        raise CommonsDatapackageError(
            self.source_path,
            reason=f"no resource with logical path {logical_path!r}",
        )


def read_datapackage(path: Path) -> DatapackageDescriptor:
    """Parse a datapackage.yaml into a `DatapackageDescriptor`.

    Raises `CommonsDatapackageError` on unreadable/malformed YAML, a missing or
    empty `resources` list, a resource with a missing/invalid `path`, a
    duplicate logical path, or a resource with a missing/malformed `hash`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommonsDatapackageError(path, reason=f"cannot read file: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CommonsDatapackageError(path, reason=f"malformed YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise CommonsDatapackageError(path, reason="top level is not a mapping")
    raw_resources = raw.get("resources")
    if not isinstance(raw_resources, list) or not raw_resources:
        raise CommonsDatapackageError(
            path, reason="missing or empty 'resources' list"
        )

    resources: list[DataResource] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_resources):
        if not isinstance(entry, dict):
            raise CommonsDatapackageError(
                path, reason=f"resources[{index}] is not a mapping"
            )

        raw_path = entry.get("path")
        if not isinstance(raw_path, str):
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] has a missing or non-string 'path'",
            )
        try:
            logical_path = validate_logical_path(raw_path)
        except DataLogicalPathError as exc:
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] has an invalid path: {exc.reason}",
            ) from exc
        if logical_path in seen:
            raise CommonsDatapackageError(
                path, reason=f"duplicate resource path {logical_path!r}"
            )
        seen.add(logical_path)

        raw_hash = entry.get("hash")
        if not isinstance(raw_hash, str):
            raise CommonsDatapackageError(
                path,
                reason=(
                    f"resources[{index}] ({logical_path}) has a missing or "
                    f"non-string 'hash'"
                ),
            )
        try:
            parse_resource_hash(raw_hash)
        except ValueError as exc:
            raise CommonsDatapackageError(
                path,
                reason=f"resources[{index}] ({logical_path}) has an invalid hash: {exc}",
            ) from exc

        resources.append(DataResource(path=logical_path, hash=raw_hash))

    return DatapackageDescriptor(source_path=path, resources=tuple(resources))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_datapackage.py -v`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/datapackage.py science/tests/test_commons_datapackage.py
git commit -m "feat(commons): datapackage.yaml descriptor reader"
```

---

## Task 5: Adapter patch — `load()` raises `CommonsLayoutError` for a missing datapackage

**Files:**
- Modify: `science/src/science_tool/commons/adapter.py`
- Test: `science/tests/test_commons_adapter.py`

**Context:** Phase B's `scan()` raises `CommonsLayoutError` for a dataset directory missing its `datapackage.yaml`, but `load()` does not — it builds the `dp` path unconditionally and `_build()` then calls `datapackage_path.stat()` *outside* its `try/except`, so a missing sidecar surfaces as a raw `FileNotFoundError`. This task makes `load()` mirror `scan()`.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_commons_adapter.py` (the file already imports `CommonsLayoutError` and defines `_make_store` / `FIXTURES`):

```python
def test_load_dataset_missing_datapackage_raises_layout_error(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "invalid/dataset-missing-datapackage")
    adapter = CommonsEntityAdapter(root)
    with pytest.raises(CommonsLayoutError, match="datapackage.yaml"):
        adapter.load("dataset:no-dp")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_adapter.py::test_load_dataset_missing_datapackage_raises_layout_error -v`
Expected: FAIL — raises `FileNotFoundError` (or `CommonsEntityError` wrapping it), not `CommonsLayoutError`.

- [ ] **Step 3: Patch `load()`**

In `science/src/science_tool/commons/adapter.py`, find this block in the `load()` method:

```python
        if not body.is_file():
            raise CommonsEntityError(
                body,
                canonical_id=canonical_id,
                cause=FileNotFoundError(str(body)),
            )
        result = self._build(type_dir, slug, body, dp)
```

Insert a datapackage-existence check between the `body` check and the `_build` call:

```python
        if not body.is_file():
            raise CommonsEntityError(
                body,
                canonical_id=canonical_id,
                cause=FileNotFoundError(str(body)),
            )
        if dp is not None and not dp.is_file():
            raise CommonsLayoutError(
                self._root / "datasets" / slug,
                reason="dataset directory missing required datapackage.yaml sibling",
            )
        result = self._build(type_dir, slug, body, dp)
```

(`CommonsLayoutError` is already imported at the top of `adapter.py`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_adapter.py -v`
Expected: PASS — the new test passes and all existing adapter tests stay green.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/adapter.py science/tests/test_commons_adapter.py
git commit -m "fix(commons): load() raises CommonsLayoutError for missing datapackage"
```

---

## Task 6: Resolver — `ResolvedDataResource` + `resolve()`

**Files:**
- Create: `science/src/science_tool/commons/resolver.py`
- Test: `science/tests/test_commons_resolver.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_resolver.py`:

```python
"""Tests for science_tool.commons.resolver."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
import yaml

from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsEntityError,
    CommonsLayoutError,
    DataIntegrityError,
    DataLogicalPathError,
    DataResourceNotFoundError,
)
from science_tool.commons.resolver import ResolvedDataResource, resolve

FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_SLUG = "rnaseq-example"
_LOGICAL = "counts.parquet"
_CONTENT = b"counts-data\n"


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point SCIENCE_CONFIG_DIR at an isolated dir so load_data_overrides() does
    not read the developer's real ~/.config/science/data.yaml. Tests that need a
    data.yaml write it into `tmp_path / "cfg"`."""
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))


def _make_commons(tmp_path: Path, *, content: bytes = _CONTENT) -> Path:
    """Copy the valid fixture store into tmp_path and rewrite the rnaseq-example
    datapackage.yaml so its single resource points at `_LOGICAL` with the real
    sha256 of `content`. Returns the commons root."""
    commons_root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", commons_root)
    digest = hashlib.sha256(content).hexdigest()
    dp = commons_root / "datasets" / _SLUG / "datapackage.yaml"
    dp.write_text(
        yaml.dump(
            {
                "name": _SLUG,
                "profile": "data-package",
                "resources": [
                    {"name": "counts", "path": _LOGICAL, "hash": f"sha256:{digest}"}
                ],
            }
        ),
        encoding="utf-8",
    )
    return commons_root


def _write_data(root: Path, content: bytes = _CONTENT) -> Path:
    """Write <root>/<slug>/<logical> with `content`. Returns the file path."""
    target = root / _SLUG / _LOGICAL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def test_resolve_from_data_root(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    target = _write_data(data_root)
    result = resolve(
        f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root
    )
    assert isinstance(result, ResolvedDataResource)
    assert result.path == target.resolve()
    assert result.source == "data_root"
    assert result.logical_path == _LOGICAL
    assert result.dataset_id == f"dataset:{_SLUG}"
    assert result.hash == f"sha256:{hashlib.sha256(_CONTENT).hexdigest()}"


def test_resolve_from_override(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"  # intentionally empty
    override_dir = tmp_path / "legacy"
    _write_data(override_dir)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(
        yaml.dump({_SLUG: str(override_dir)}), encoding="utf-8"
    )
    result = resolve(
        f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root
    )
    assert result.path == (override_dir / _SLUG / _LOGICAL).resolve()
    assert result.source == "override"


def test_resolve_data_root_takes_precedence_over_override(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    data_target = _write_data(data_root)
    override_dir = tmp_path / "legacy"
    _write_data(override_dir)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(
        yaml.dump({_SLUG: str(override_dir)}), encoding="utf-8"
    )
    result = resolve(
        f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root
    )
    assert result.path == data_target.resolve()
    assert result.source == "data_root"


def test_resolve_not_found(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"  # nothing written
    with pytest.raises(DataResourceNotFoundError):
        resolve(
            f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root
        )


def test_resolve_hash_mismatch(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    _write_data(data_root, content=b"corrupted-bytes\n")
    with pytest.raises(DataIntegrityError):
        resolve(
            f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root
        )


def test_resolve_rejects_non_dataset_id(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    with pytest.raises(CommonsEntityError):
        resolve(
            "paper:Adams2025", _LOGICAL, commons_root=commons_root, data_root=data_root
        )


def test_resolve_rejects_hostile_logical_path(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    with pytest.raises(DataLogicalPathError):
        resolve(
            f"dataset:{_SLUG}",
            "../../etc/passwd",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_missing_logical_path_in_descriptor(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    with pytest.raises(CommonsDatapackageError, match="no resource"):
        resolve(
            f"dataset:{_SLUG}",
            "not-in-descriptor.tsv",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_missing_datapackage_raises_layout_error(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    (commons_root / "datasets" / _SLUG / "datapackage.yaml").unlink()
    data_root = tmp_path / "data"
    with pytest.raises(CommonsLayoutError):
        resolve(
            f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root
        )


def test_resolve_directory_at_target_is_not_resolved(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    # A directory sits where the resource file should be.
    (data_root / _SLUG / _LOGICAL).mkdir(parents=True)
    with pytest.raises(DataResourceNotFoundError):
        resolve(
            f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_resolver.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.commons.resolver'`

- [ ] **Step 3: Create `resolver.py`**

Create `science/src/science_tool/commons/resolver.py`:

```python
"""Map (dataset_id, logical_path) to a hash-verified absolute filesystem path.

The commons store holds the source of truth for what the bytes should be (the
resources[].hash in datapackage.yaml); this module finds the actual bytes via a
path lookup chain and verifies them. See
docs/plans/2026-05-14-commons-data-resolver-design.md §5.3.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import (
    load_data_overrides,
    resolve_commons_data_root,
    resolve_commons_root,
)
from science_tool.commons.datapackage import (
    parse_resource_hash,
    read_datapackage,
    validate_logical_path,
)
from science_tool.commons.errors import (
    CommonsEntityError,
    DataIntegrityError,
    DataResourceNotFoundError,
)

_HASH_CHUNK_BYTES = 1 << 20  # 1 MiB streaming chunk


@dataclass(frozen=True, slots=True)
class ResolvedDataResource:
    """The result of a successful resolve: a verified resource and its provenance."""

    path: Path  # absolute, hash-verified filesystem path to the bytes
    hash: str  # the expected "sha256:<hex>" the bytes were verified against
    source: str  # "data_root" | "override" — which lookup branch matched
    logical_path: str  # the validated logical path that was resolved
    dataset_id: str  # "dataset:<slug>"


def _sha256_file(path: Path) -> str:
    """Stream the file and return its lowercase hex sha256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def resolve(
    dataset_id: str,
    logical_path: str,
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ResolvedDataResource:
    """Resolve a commons dataset resource to a verified absolute filesystem path.

    Lookup order: `<data_root>/<slug>/<logical_path>`, then the per-machine
    override directory from `~/.config/science/data.yaml`. The chosen file's
    sha256 is verified against the datapackage hash on every call.

    Raises `DataLogicalPathError` for an unsafe `logical_path`; `CommonsEntityError`
    for a non-dataset id or an unknown dataset; `CommonsLayoutError` for a dataset
    missing its datapackage.yaml; `CommonsDatapackageError` for a malformed
    descriptor or an unknown `logical_path`; `DataResourceNotFoundError` when no
    lookup source has the file; `DataIntegrityError` on a hash mismatch.
    """
    logical_path = validate_logical_path(logical_path)
    commons_root = commons_root or resolve_commons_root()
    data_root = data_root or resolve_commons_data_root()

    if not dataset_id.startswith("dataset:"):
        raise CommonsEntityError(
            commons_root,
            canonical_id=dataset_id,
            cause=ValueError(
                f"data resolve requires a 'dataset:' id, got {dataset_id!r}"
            ),
        )

    record = CommonsEntityAdapter(commons_root).load(dataset_id)
    # load() guarantees a dataset record carries a datapackage path (it raises
    # CommonsLayoutError otherwise); this narrows the type for the reader.
    if record.datapackage_path is None:
        raise CommonsEntityError(
            record.body_path,
            canonical_id=dataset_id,
            cause=ValueError("dataset record is missing its datapackage path"),
        )

    descriptor = read_datapackage(record.datapackage_path)
    resource = descriptor.resource(logical_path)
    _, expected_digest = parse_resource_hash(resource.hash)

    data_root_candidate = data_root / record.slug / logical_path
    override_dir = load_data_overrides().get(record.slug)
    override_candidate = (
        override_dir / logical_path if override_dir is not None else None
    )

    if data_root_candidate.is_file():
        candidate, source = data_root_candidate, "data_root"
    elif override_candidate is not None and override_candidate.is_file():
        candidate, source = override_candidate, "override"
    else:
        tried = [data_root_candidate]
        if override_candidate is not None:
            tried.append(override_candidate)
        raise DataResourceNotFoundError(dataset_id, logical_path, tried=tried)

    actual_digest = _sha256_file(candidate)
    if actual_digest != expected_digest:
        raise DataIntegrityError(
            candidate,
            expected=resource.hash,
            actual=f"sha256:{actual_digest}",
        )

    return ResolvedDataResource(
        path=candidate.resolve(),
        hash=resource.hash,
        source=source,
        logical_path=logical_path,
        dataset_id=dataset_id,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_resolver.py -v`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/resolver.py science/tests/test_commons_resolver.py
git commit -m "feat(commons): data resolver — lookup chain + hash verification"
```

---

## Task 7: CLI — `science commons data resolve`

**Files:**
- Modify: `science/src/science_tool/commons/cli.py`
- Test: `science/tests/test_commons_cli_data.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_commons_cli_data.py`:

```python
"""Tests for the `science commons data` CLI subgroup."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.commons.cli import commons_group

FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_SLUG = "rnaseq-example"
_LOGICAL = "counts.parquet"
_CONTENT = b"counts-data\n"


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, write_data: bool = True) -> None:
    """Build a commons store + data root and point the env at them."""
    commons_root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", commons_root)
    digest = hashlib.sha256(_CONTENT).hexdigest()
    dp = commons_root / "datasets" / _SLUG / "datapackage.yaml"
    dp.write_text(
        yaml.dump(
            {
                "name": _SLUG,
                "profile": "data-package",
                "resources": [
                    {"name": "counts", "path": _LOGICAL, "hash": f"sha256:{digest}"}
                ],
            }
        ),
        encoding="utf-8",
    )
    data_root = tmp_path / "data"
    if write_data:
        target = data_root / _SLUG / _LOGICAL
        target.parent.mkdir(parents=True)
        target.write_bytes(_CONTENT)
    data_root.mkdir(exist_ok=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))


def test_data_resolve_plain_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL])
    assert result.exit_code == 0, result.output
    printed = Path(result.output.strip())
    assert printed == (tmp_path / "data" / _SLUG / _LOGICAL).resolve()


def test_data_resolve_json_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL, "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dataset_id"] == f"dataset:{_SLUG}"
    assert payload["logical_path"] == _LOGICAL
    assert payload["source"] == "data_root"
    assert payload["hash"] == f"sha256:{hashlib.sha256(_CONTENT).hexdigest()}"
    assert payload["resolved_path"] == str((tmp_path / "data" / _SLUG / _LOGICAL).resolve())


def test_data_resolve_not_found_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch, write_data=False)
    runner = CliRunner()
    result = runner.invoke(commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_data_resolve_hostile_path_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["data", "resolve", f"dataset:{_SLUG}", "../../etc/passwd"]
    )
    assert result.exit_code != 0
    assert "invalid logical path" in result.output


def test_data_resolve_non_dataset_id_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(commons_group, ["data", "resolve", "paper:Adams2025", _LOGICAL])
    assert result.exit_code != 0
    assert "dataset" in result.output


def test_data_resolve_missing_datapackage_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    (tmp_path / "commons" / "datasets" / _SLUG / "datapackage.yaml").unlink()
    runner = CliRunner()
    result = runner.invoke(commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL])
    assert result.exit_code != 0
    assert "datapackage.yaml" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli_data.py -v`
Expected: FAIL — `Error: No such command 'data'.`

- [ ] **Step 3: Add the `data` subgroup to `cli.py`**

In `science/src/science_tool/commons/cli.py`, add the resolver import to the import block at the top of the file (after the `from science_tool.commons.registry import RegistryBuilder` line):

```python
from science_tool.commons.resolver import resolve
```

Append to the end of `science/src/science_tool/commons/cli.py`:

```python
@commons_group.group("data")
def data_group() -> None:
    """Resolve bulk data for commons datasets."""


@data_group.command("resolve")
@click.argument("dataset_id")
@click.argument("logical_path")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def data_resolve_cmd(dataset_id: str, logical_path: str, as_json: bool) -> None:
    """Resolve DATASET_ID + LOGICAL_PATH to a verified absolute filesystem path."""
    try:
        resolved = resolve(dataset_id, logical_path)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        click.echo(
            json.dumps(
                {
                    "dataset_id": resolved.dataset_id,
                    "logical_path": resolved.logical_path,
                    "resolved_path": str(resolved.path),
                    "hash": resolved.hash,
                    "source": resolved.source,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        click.echo(str(resolved.path))
```

(`CommonsError` is already imported in `cli.py`, and every Phase C error class subclasses it, so the single `except CommonsError` covers all failure modes.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_cli_data.py -v`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/cli.py science/tests/test_commons_cli_data.py
git commit -m "feat(commons): science commons data resolve CLI command"
```

---

## Task 8: Public surface — finalize `commons/__init__.py`

**Files:**
- Modify: `science/src/science_tool/commons/__init__.py`
- Test: `science/tests/test_commons_public_api.py`

- [ ] **Step 1: Write the failing test**

Replace the `expected` set in `science/tests/test_commons_public_api.py::test_public_api_exports` with the full Phase B + Phase C surface:

```python
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
        # Phase C
        "CommonsDatapackageError",
        "DataLogicalPathError",
        "DataResourceNotFoundError",
        "DataIntegrityError",
        "resolve_commons_data_root",
        "load_data_overrides",
        "DataResource",
        "DatapackageDescriptor",
        "read_datapackage",
        "validate_logical_path",
        "parse_resource_hash",
        "ResolvedDataResource",
        "resolve",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_public_api.py -v`
Expected: FAIL — `missing public name: ResolvedDataResource` (or similar).

- [ ] **Step 3: Update `commons/__init__.py`**

Replace the entire contents of `science/src/science_tool/commons/__init__.py` with:

```python
"""Shared knowledge store (commons) for Science multi-project entities.

Phase B (scaffolding): directory bootstrap, schema-validated entity adapter,
SQLite index, and CLI surface for `science commons {init, index rebuild,
show, find, validate}`.

Phase C (data resolver): datapackage.yaml reader, hash-verified bulk-data
resolution, and the `science commons data resolve` CLI command.

See docs/plans/2026-05-13-multiproject-commons-scaffolding-design.md and
docs/plans/2026-05-14-commons-data-resolver-design.md.
"""

from __future__ import annotations

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.bootstrap import init_commons
from science_tool.commons.cli import commons_group
from science_tool.commons.config import (
    CommonsSettings,
    load_data_overrides,
    resolve_commons_data_root,
    resolve_commons_root,
)
from science_tool.commons.datapackage import (
    DatapackageDescriptor,
    DataResource,
    parse_resource_hash,
    read_datapackage,
    validate_logical_path,
)
from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
    DataIntegrityError,
    DataLogicalPathError,
    DataResourceNotFoundError,
)
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import RebuildReport, RegistryBuilder
from science_tool.commons.resolver import ResolvedDataResource, resolve
from science_tool.commons.validator import CommonsValidator, ValidationReport

__all__ = [
    "CommonsDatapackageError",
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
    "DataIntegrityError",
    "DataLogicalPathError",
    "DataResource",
    "DataResourceNotFoundError",
    "DatapackageDescriptor",
    "RebuildReport",
    "RegistryBuilder",
    "ResolvedDataResource",
    "ValidationReport",
    "commons_group",
    "init_commons",
    "load_data_overrides",
    "parse_resource_hash",
    "read_datapackage",
    "resolve",
    "resolve_commons_data_root",
    "resolve_commons_root",
    "validate_logical_path",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_public_api.py -v`
Expected: PASS — the export set matches.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/__init__.py science/tests/test_commons_public_api.py
git commit -m "feat(commons): export Phase C public surface"
```

---

## Task 9: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full `science` test suite**

Run: `cd ~/d/science/science && uv run pytest -q`
Expected: PASS — the entire suite is green, including all `test_commons_*` files.

- [ ] **Step 2: Run the `science_model` suite**

Run: `cd ~/d/science/science/model && uv run pytest -q`
Expected: PASS — Phase A's model suite is undisturbed (Phase C touches nothing in `science_model`).

- [ ] **Step 3: Smoke-test the CLI is wired**

Run: `cd ~/d/science/science && uv run science commons data resolve --help`
Expected: prints the `resolve` command help (`DATASET_ID`, `LOGICAL_PATH`, `--json`), exit 0. This confirms the `data` subgroup is reachable through the top-level `science` entry point (wired in Phase B's `main.add_command(commons_group)`).

- [ ] **Step 4: Final commit (if anything changed) / handoff**

If Steps 1–3 surfaced no changes, there is nothing to commit — proceed to handoff. Otherwise commit the fix with a descriptive message.

Hand off to `superpowers:finishing-a-development-branch`.

---

## Self-review notes

- **Spec coverage:** every §5 component (config §5.1, datapackage reader §5.2, resolver §5.3, CLI §5.4), all four §6 error classes, the §5.3 adapter patch, and every row of the §7 test matrix maps to a task (Task 1 → errors; Task 2 → config; Tasks 3–4 → datapackage; Task 5 → adapter patch; Task 6 → resolver; Task 7 → CLI; Task 8 → public surface; Task 9 → full-suite + model-suite green).
- **Deviations:** the two refinements documented in the "Deviations from the design spec" section above (`parse_resource_hash` raises `ValueError`; `DatapackageDescriptor` carries `source_path`). Both keep the spec's intent that errors never fabricate a `Path`.
- **Type consistency:** `ResolvedDataResource` fields (`path`, `hash`, `source`, `logical_path`, `dataset_id`) are used identically in Task 6 and Task 7. `DataResource` (`path`, `hash`) and `DatapackageDescriptor` (`source_path`, `resources`) are consistent across Tasks 4, 6. `validate_logical_path`, `parse_resource_hash`, `read_datapackage`, `resolve`, `resolve_commons_data_root`, `load_data_overrides` signatures match between definition and call sites.
